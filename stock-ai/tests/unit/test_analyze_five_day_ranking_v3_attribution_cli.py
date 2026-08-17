from __future__ import annotations

import argparse
from dataclasses import replace
from datetime import date
from decimal import Decimal
import importlib.util
import os
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
from stock_ai.buy_point_selection.reference_sources import IndexBar

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


class _FakeMappings:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self._rows = rows

    def all(self) -> list[dict[str, object]]:
        return self._rows


class _FakeResult:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self._rows = rows

    def mappings(self) -> _FakeMappings:
        return _FakeMappings(self._rows)


class _FakeConnection:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self._rows = rows
        self.statement = ""
        self.parameters: dict[str, object] = {}

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None

    def execute(self, statement, parameters):
        self.statement = " ".join(str(statement).split())
        self.parameters = dict(parameters)
        return _FakeResult(self._rows)


class _FakeEngine:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.connection = _FakeConnection(rows)

    def connect(self) -> _FakeConnection:
        return self.connection


def test_stock_loader_uses_bounded_close_only_query_and_main_board_filter() -> None:
    module = _load_module()
    start = date(2024, 1, 2)
    end = date(2024, 1, 5)
    engine = _FakeEngine(
        [
            {"ts_code": "600001.SH", "trade_date": start, "close": "10.2"},
            {"ts_code": "000001.SZ", "trade_date": end, "close": "9.8"},
            {"ts_code": "300001.SZ", "trade_date": end, "close": "12"},
            {"ts_code": "600002.SH", "trade_date": end, "close": "NaN"},
            {
                "ts_code": "600003.SH",
                "trade_date": date(2024, 1, 8),
                "close": "11",
            },
        ]
    )

    loaded = module._load_stock_closes(engine, start, end)

    assert engine.connection.statement == (
        "SELECT ts_code, trade_date, close FROM stock_daily "
        "WHERE trade_date BETWEEN :start AND :end "
        "ORDER BY ts_code, trade_date"
    )
    assert engine.connection.parameters == {"start": start, "end": end}
    assert loaded == {
        "000001": {end: Decimal("9.8")},
        "600001": {start: Decimal("10.2")},
    }


def test_configured_engine_is_pre_ping_and_rewrites_only_docker_host(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    seen: dict[str, object] = {}
    monkeypatch.setenv(
        "MYSQL_URL",
        "mysql+pymysql://reader:secret@host.docker.internal:3306/stock",
    )

    def engine_factory(url: str, **kwargs):
        seen.update(url=url, kwargs=kwargs)
        return "engine"

    assert module._configured_engine(engine_factory=engine_factory) == "engine"
    assert seen == {
        "url": "mysql+pymysql://reader:secret@127.0.0.1:3306/stock",
        "kwargs": {"pool_pre_ping": True},
    }
    assert os.environ["MYSQL_URL"].endswith("host.docker.internal:3306/stock")


def test_required_indexes_follow_only_mapped_train_plan_boards() -> None:
    module = _load_module()
    base_payload = {
        "variants": [
            {
                "segment": {
                    "admitted_trade_keys": [{"code": "600001.SH"}],
                    "ranked_plan_keys": [{"code": "000001.SZ"}],
                }
            }
        ]
    }

    assert module._required_index_ids(SimpleNamespace(payload=base_payload)) == (
        "sh.000001",
        "sz.399001",
    )

    star_payload = {
        "variants": [
            *base_payload["variants"],
            {
                "segment": {
                    "admitted_trade_keys": [],
                    "ranked_plan_keys": [{"code": "688001.SH"}],
                }
            },
        ]
    }
    assert module._required_index_ids(SimpleNamespace(payload=star_payload)) == (
        "sh.000001",
        "sz.399001",
        "sh.000688",
    )


def test_benchmark_loader_returns_only_requested_indexes_at_same_bound() -> None:
    module = _load_module()
    start = date(2024, 1, 2)
    end = date(2024, 1, 5)
    calls: list[tuple[date, date]] = []

    def raw_loader(received_start: date, received_end: date):
        calls.append((received_start, received_end))
        return {
            code: (
                IndexBar(code, start, Decimal("10"), Decimal("0")),
                IndexBar(code, end, Decimal("11"), Decimal("10")),
            )
            for code in ("sh.000001", "sz.399001", "sh.000688")
        }

    loaded = module._load_required_benchmark_closes(
        ("sh.000001", "sz.399001"),
        start,
        end,
        benchmark_loader=raw_loader,
    )

    assert calls == [(start, end)]
    assert set(loaded) == {"sh.000001", "sz.399001"}
    assert loaded["sh.000001"] == {
        start: Decimal("10"),
        end: Decimal("11"),
    }


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
