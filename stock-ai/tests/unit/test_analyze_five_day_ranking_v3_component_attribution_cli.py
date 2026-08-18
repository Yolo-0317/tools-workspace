from __future__ import annotations

import argparse
from dataclasses import replace
from datetime import date
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from stock_ai.buy_point_selection.five_day_ranking_v3 import (
    build_five_day_ranking_v3_train_review,
)
from stock_ai.buy_point_selection.five_day_ranking_v3_attribution import (
    MarketClosePanel,
    build_five_day_ranking_v3_attribution_review,
)
from stock_ai.buy_point_selection.five_day_ranking_v3_attribution_report import (
    write_five_day_ranking_v3_attribution,
)
from stock_ai.buy_point_selection.five_day_ranking_v3_report import (
    write_five_day_ranking_v3_train,
)
from stock_ai.buy_point_selection.five_day_return_report import (
    _recompute_review,
    five_day_research_payload,
    write_five_day_research,
)

from five_day_ranking_v3_fixtures import make_v3_research_review


SCRIPT = (
    Path(__file__).parents[2]
    / "scripts"
    / "analysis"
    / "analyze_five_day_ranking_v3_component_attribution.py"
)


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "analyze_five_day_ranking_v3_component_attribution",
        SCRIPT,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _option_strings(parser: argparse.ArgumentParser) -> set[str]:
    found: set[str] = set()
    stack = [parser]
    while stack:
        current = stack.pop()
        for action in current._actions:
            found.update(action.option_strings)
            choices = getattr(action, "choices", None)
            if isinstance(choices, dict):
                stack.extend(choices.values())
    return found


def test_parser_exposes_only_manual_component_diagnosis() -> None:
    module = _load_module()
    parser = module.build_parser()
    subparsers = next(
        action
        for action in parser._actions
        if isinstance(action, argparse._SubParsersAction)
    )

    assert tuple(subparsers.choices) == ("diagnose-ranking-components",)
    assert _option_strings(parser) == {
        "-h",
        "--help",
        "--train-artifact",
        "--research-artifact",
        "--market-attribution-artifact",
        "--output-dir",
    }
    assert {
        "--validation",
        "--test",
        "--freeze",
        "--forward",
        "--settlement",
        "--notification",
        "--holding",
        "--memory",
        "--order",
        "--trade",
    }.isdisjoint(_option_strings(parser))


def test_parser_requires_and_converts_all_four_paths() -> None:
    module = _load_module()

    args = module.build_parser().parse_args(
        (
            "diagnose-ranking-components",
            "--train-artifact",
            "train.json",
            "--research-artifact",
            "research.json",
            "--market-attribution-artifact",
            "market.json",
            "--output-dir",
            "output",
        )
    )

    assert args.train_artifact == Path("train.json")
    assert args.research_artifact == Path("research.json")
    assert args.market_attribution_artifact == Path("market.json")
    assert args.output_dir == Path("output")


def _write_inputs(
    directory: Path,
    *,
    research_fingerprint: str = "f",
) -> tuple[Path, Path, Path]:
    research = _recompute_review(
        replace(
            make_v3_research_review(()),
            input_fingerprint=research_fingerprint * 64,
        )
    )
    research_path = write_five_day_research(research, directory)
    parent_identity = str(
        five_day_research_payload(research)["artifact_identity"]
    )
    train_review = build_five_day_ranking_v3_train_review(
        research,
        parent_research_identity=parent_identity,
    )
    train_path = write_five_day_ranking_v3_train(train_review, directory)
    from stock_ai.buy_point_selection.five_day_ranking_v3_report import (
        load_five_day_ranking_v3_train,
    )

    train = load_five_day_ranking_v3_train(train_path)
    attribution = build_five_day_ranking_v3_attribution_review(
        train,
        research,
        parent_research_identity=parent_identity,
        market_panel=MarketClosePanel(
            train_dates=train.split.train,
            stock_closes={},
            index_closes={},
        ),
    )
    market_path = write_five_day_ranking_v3_attribution(
        attribution, directory
    )
    return train_path, research_path, market_path


def _argv(
    train_path: Path,
    research_path: Path,
    market_path: Path,
    output: Path,
) -> tuple[str, ...]:
    return (
        "diagnose-ranking-components",
        "--train-artifact",
        str(train_path),
        "--research-artifact",
        str(research_path),
        "--market-attribution-artifact",
        str(market_path),
        "--output-dir",
        str(output),
    )


def test_bad_lineage_stops_before_market_io(tmp_path: Path) -> None:
    module = _load_module()
    train_path, _, market_path = _write_inputs(
        tmp_path / "train", research_fingerprint="f"
    )
    _, wrong_research, _ = _write_inputs(
        tmp_path / "wrong", research_fingerprint="e"
    )

    def forbidden_loader(*_args, **_kwargs):
        pytest.fail("market I/O must not run before lineage validation")

    with pytest.raises(ValueError, match="parent lineage mismatch"):
        module.dispatch_command(
            module.build_parser().parse_args(
                _argv(
                    train_path,
                    wrong_research,
                    market_path,
                    tmp_path / "output",
                )
            ),
            stock_loader=forbidden_loader,
            benchmark_loader=forbidden_loader,
        )


def test_incomplete_parent_attribution_stops_before_market_io(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    train_path, research_path, market_path = _write_inputs(tmp_path / "inputs")
    monkeypatch.setattr(
        module,
        "load_five_day_ranking_v3_attribution",
        lambda *_args, **_kwargs: SimpleNamespace(
            status="MARKET_DATA_INCOMPLETE",
            parent_input_fingerprint="f" * 64,
            payload={},
        ),
    )

    def forbidden_loader(*_args, **_kwargs):
        pytest.fail("market I/O must not run for incomplete parent attribution")

    with pytest.raises(ValueError, match="parent attribution is incomplete"):
        module.dispatch_command(
            module.build_parser().parse_args(
                _argv(
                    train_path,
                    research_path,
                    market_path,
                    tmp_path / "output",
                )
            ),
            stock_loader=forbidden_loader,
            benchmark_loader=forbidden_loader,
        )


def test_dispatch_uses_train_bounds_required_indexes_and_no_trade_review(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    train_path, research_path, market_path = _write_inputs(tmp_path / "inputs")
    output = tmp_path / "output"
    stock_calls: list[tuple[date, date]] = []
    benchmark_calls: list[tuple[tuple[str, ...], date, date]] = []
    written: list[object] = []
    required = ("sh.000001", "sz.399001")
    monkeypatch.setattr(module, "required_index_ids", lambda _train: required)

    def stock_loader(start: date, end: date):
        stock_calls.append((start, end))
        return {}

    def benchmark_loader(index_ids, start: date, end: date):
        benchmark_calls.append((tuple(index_ids), start, end))
        return {}

    def writer(review, output_dir):
        assert output_dir == output
        written.append(review)
        return output / "component.json"

    result = module.dispatch_command(
        module.build_parser().parse_args(
            _argv(train_path, research_path, market_path, output)
        ),
        stock_loader=stock_loader,
        benchmark_loader=benchmark_loader,
        writer=writer,
    )

    assert result == output / "component.json"
    assert stock_calls == [(date(2023, 1, 2), date(2024, 6, 12))]
    assert benchmark_calls == [
        (required, date(2023, 1, 2), date(2024, 6, 12))
    ]
    assert len(written) == 1
    assert written[0].train_only is True
    assert written[0].validation_outcomes_read is False
    assert written[0].test_outcomes_read is False
    assert written[0].promotion_eligible is False
    assert written[0].trade_permission == "NO-TRADE"


def test_writer_failure_leaves_no_cli_partial_file(tmp_path: Path) -> None:
    module = _load_module()
    train_path, research_path, market_path = _write_inputs(tmp_path / "inputs")
    output = tmp_path / "output"

    def failing_writer(_review, _output):
        raise OSError("write failed")

    with pytest.raises(OSError, match="write failed"):
        module.dispatch_command(
            module.build_parser().parse_args(
                _argv(train_path, research_path, market_path, output)
            ),
            stock_loader=lambda _start, _end: {},
            benchmark_loader=lambda _ids, _start, _end: {},
            writer=failing_writer,
        )

    assert not output.exists()


def test_main_sanitizes_dependency_details(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = _load_module()
    monkeypatch.setattr(
        module,
        "dispatch_command",
        lambda _args: (_ for _ in ()).throw(
            RuntimeError(
                "mysql://reader:secret@192.168.1.13 stock 600001 row"
            )
        ),
    )

    result = module.main(
        _argv(
            tmp_path / "train.json",
            tmp_path / "research.json",
            tmp_path / "market.json",
            tmp_path / "output",
        )
    )
    captured = capsys.readouterr()

    assert result == 2
    assert captured.out == ""
    assert captured.err == "五日排名V3组件归因失败\n"


def test_main_success_prints_only_written_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = _load_module()
    expected = tmp_path / "component.json"
    monkeypatch.setattr(module, "dispatch_command", lambda _args: expected)

    result = module.main(
        _argv(
            tmp_path / "train.json",
            tmp_path / "research.json",
            tmp_path / "market.json",
            tmp_path / "output",
        )
    )
    captured = capsys.readouterr()

    assert result == 0
    assert captured.out == f"{expected}\n"
    assert captured.err == ""


def test_script_imports_no_trading_or_memory_side_effect_modules() -> None:
    code = f"""
import importlib.util, json, sys
spec = importlib.util.spec_from_file_location('component_cli', {str(SCRIPT)!r})
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
tokens = ('settlement', 'notification', 'advisor_memory', 'position', 'holding', 'order_execution')
print(json.dumps(sorted(name for name in sys.modules if any(token in name for token in tokens))))
"""
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(Path(__file__).parents[2])

    completed = subprocess.run(
        [str(Path(sys.executable)), "-c", code],
        cwd=Path(__file__).parents[2],
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(completed.stdout) == []
