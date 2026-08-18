from __future__ import annotations

import argparse
from dataclasses import replace
from datetime import date
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

from stock_ai.buy_point_selection.five_day_ranking_v3 import (
    build_five_day_ranking_v3_train_review,
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
    / "analyze_five_day_ranking_v3_attribution.py"
)


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "analyze_five_day_ranking_v3_attribution",
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


def _write_inputs(
    tmp_path: Path,
    *,
    research_fingerprint: str = "f",
) -> tuple[Path, Path]:
    research = _recompute_review(
        replace(
            make_v3_research_review(()),
            input_fingerprint=research_fingerprint * 64,
        )
    )
    research_path = write_five_day_research(research, tmp_path)
    parent_identity = str(
        five_day_research_payload(research)["artifact_identity"]
    )
    train_review = build_five_day_ranking_v3_train_review(
        research,
        parent_research_identity=parent_identity,
    )
    train_path = write_five_day_ranking_v3_train(train_review, tmp_path)
    return train_path, research_path


def _argv(train_path: Path, research_path: Path, output: Path) -> tuple[str, ...]:
    return (
        "diagnose-train-attribution",
        "--train-artifact",
        str(train_path),
        "--research-artifact",
        str(research_path),
        "--output-dir",
        str(output),
    )


def test_parser_exposes_one_manual_aggregate_only_command() -> None:
    module = _load_module()
    parser = module.build_parser()
    subparsers = next(
        action
        for action in parser._actions
        if isinstance(action, argparse._SubParsersAction)
    )

    assert tuple(subparsers.choices) == ("diagnose-train-attribution",)
    assert _option_strings(parser) == {
        "-h",
        "--help",
        "--train-artifact",
        "--research-artifact",
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


def test_parser_requires_and_converts_all_three_paths() -> None:
    module = _load_module()

    args = module.build_parser().parse_args(
        (
            "diagnose-train-attribution",
            "--train-artifact",
            "train.json",
            "--research-artifact",
            "research.json",
            "--output-dir",
            "output",
        )
    )

    assert args.train_artifact == Path("train.json")
    assert args.research_artifact == Path("research.json")
    assert args.output_dir == Path("output")


def test_lineage_mismatch_stops_before_any_market_io(
    tmp_path: Path,
) -> None:
    module = _load_module()
    train_path, _ = _write_inputs(tmp_path / "train", research_fingerprint="f")
    _, wrong_parent = _write_inputs(
        tmp_path / "wrong-parent",
        research_fingerprint="e",
    )
    args = module.build_parser().parse_args(
        _argv(train_path, wrong_parent, tmp_path / "output")
    )

    def forbidden_loader(*_args, **_kwargs):
        pytest.fail("market I/O must not run before lineage validation")

    with pytest.raises(ValueError, match="parent lineage mismatch"):
        module.dispatch_command(
            args,
            stock_loader=forbidden_loader,
            benchmark_loader=forbidden_loader,
        )


def test_dispatch_builds_once_and_returns_one_written_path(tmp_path: Path) -> None:
    module = _load_module()
    train_path, research_path = _write_inputs(tmp_path / "inputs")
    output = tmp_path / "output"
    expected = output / "attribution.json"
    writer_calls: list[object] = []
    benchmark_calls: list[tuple[tuple[str, ...], date, date]] = []

    def benchmark_loader(index_ids, start, end):
        benchmark_calls.append((index_ids, start, end))
        return {}

    def writer(review, output_dir):
        writer_calls.append(review)
        assert output_dir == output
        return expected

    result = module.dispatch_command(
        module.build_parser().parse_args(_argv(train_path, research_path, output)),
        stock_loader=lambda _start, _end: {},
        benchmark_loader=benchmark_loader,
        writer=writer,
    )

    assert result == expected
    assert len(writer_calls) == 1
    assert writer_calls[0].status == "COMPLETE"
    assert benchmark_calls == []


def test_dispatch_default_stock_loader_uses_shared_injection_seam(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    train_path, research_path = _write_inputs(tmp_path / "inputs")
    calls: list[tuple[date, date]] = []

    def shared_stock_loader(start: date, end: date):
        calls.append((start, end))
        return {}

    monkeypatch.setattr(
        module,
        "load_mysql_stock_closes",
        shared_stock_loader,
    )

    module.dispatch_command(
        module.build_parser().parse_args(
            _argv(train_path, research_path, tmp_path / "output")
        ),
        writer=lambda _review, output: output / "attribution.json",
    )

    assert len(calls) == 1
    assert calls[0][0] < calls[0][1]


def test_dispatch_passes_incomplete_review_to_writer(tmp_path: Path) -> None:
    module = _load_module()
    train_path, research_path = _write_inputs(tmp_path / "inputs")
    output = tmp_path / "output"
    incomplete = SimpleNamespace(status="MARKET_DATA_INCOMPLETE")
    written: list[object] = []

    module.build_five_day_ranking_v3_attribution_review = (
        lambda *_args, **_kwargs: incomplete
    )

    result = module.dispatch_command(
        module.build_parser().parse_args(_argv(train_path, research_path, output)),
        stock_loader=lambda _start, _end: {},
        benchmark_loader=lambda _ids, _start, _end: {},
        writer=lambda review, _output: written.append(review)
        or output / "incomplete.json",
    )

    assert result == output / "incomplete.json"
    assert written == [incomplete]


def test_main_sanitizes_all_dependency_details(
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
                "mysql://reader:secret@192.168.1.13/stock "
                "600001 2024-01-02 SQL-row observation-key"
            )
        ),
    )

    result = module.main(
        _argv(
            tmp_path / "train.json",
            tmp_path / "research.json",
            tmp_path / "output",
        )
    )
    captured = capsys.readouterr()

    assert result == 2
    assert captured.out == ""
    assert captured.err == "五日排名V3市场归因失败\n"
