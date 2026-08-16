from __future__ import annotations

import importlib.util
from datetime import date, timedelta
import json
from pathlib import Path

import pytest

from stock_ai.buy_point_selection.five_day_return_runtime import (
    FiveDayRuntimeInputs,
)
from stock_ai.buy_point_selection.models import MarketSnapshot
from stock_ai.buy_point_selection.reference_data import ReferenceCoverage
from stock_ai.buy_point_selection.validation import chronological_split


SCRIPT = (
    Path(__file__).parents[2]
    / "scripts"
    / "analysis"
    / "research_five_day_return_shadow.py"
)


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "research_five_day_return_shadow",
        SCRIPT,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _option_strings(parser) -> set[str]:
    found: set[str] = set()
    stack = [parser]
    seen: set[int] = set()
    while stack:
        current = stack.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        for action in current._actions:
            found.update(action.option_strings)
            choices = getattr(action, "choices", None)
            if isinstance(choices, dict):
                stack.extend(choices.values())
    return found


def test_parser_exposes_only_five_manual_no_trade_stages() -> None:
    module = _load_module()
    parser = module.build_parser()
    subparsers = next(
        action
        for action in parser._actions
        if getattr(action, "choices", None)
    )

    assert tuple(subparsers.choices) == (
        "research",
        "freeze",
        "test",
        "forward-screen",
        "forward-settlement",
    )
    assert {
        "--schedule",
        "--notify",
        "--push",
        "--shares",
        "--executable-shares",
        "--write-holdings",
        "--advisor-memory",
        "--force",
        "--bypass-gate",
    }.isdisjoint(_option_strings(parser))


@pytest.mark.parametrize(
    ("argv", "stage"),
    (
        (
            (
                "research",
                "--signal-start",
                "2024-01-02",
                "--signal-end",
                "2026-08-04",
            ),
            "research",
        ),
        (("freeze", "--research-artifact", "research.json"), "freeze"),
        (
            (
                "test",
                "--freeze-artifact",
                "freeze.json",
                "--research-artifact",
                "research.json",
            ),
            "test",
        ),
        (
            (
                "forward-screen",
                "--signal-date",
                "2026-08-14",
                "--freeze-artifact",
                "freeze.json",
                "--test-artifact",
                "test.json",
            ),
            "forward-screen",
        ),
        (
            (
                "forward-settlement",
                "--screen-artifact",
                "screen.json",
                "--outcome-cutoff",
                "2026-08-24",
            ),
            "forward-settlement",
        ),
    ),
)
def test_parser_requires_the_declared_stage_inputs(
    argv: tuple[str, ...],
    stage: str,
) -> None:
    module = _load_module()

    args = module.build_parser().parse_args(argv)

    assert args.stage == stage
    assert args.output_dir == Path(
        "output/research/buy_point_five_day_returns"
    )


@pytest.mark.parametrize(
    "argv",
    (
        ("research", "--signal-start", "2024-01-02"),
        ("freeze",),
        ("test", "--freeze-artifact", "freeze.json"),
        (
            "forward-screen",
            "--signal-date",
            "2026-08-14",
            "--freeze-artifact",
            "freeze.json",
        ),
        ("forward-settlement", "--screen-artifact", "screen.json"),
    ),
)
def test_parser_rejects_missing_required_inputs(
    argv: tuple[str, ...],
) -> None:
    module = _load_module()

    with pytest.raises(SystemExit) as exc:
        module.build_parser().parse_args(argv)

    assert exc.value.code == 2


@pytest.mark.parametrize(
    "loader_name",
    ("_load_mysql_research_inputs", "_load_mysql_range_inputs"),
)
def test_mysql_input_loaders_share_benchmark_fallback(
    monkeypatch,
    loader_name: str,
) -> None:
    """Catches either runtime path silently reverting to BaoStock-only input."""
    module = _load_module()
    signal_dates = tuple(
        date(2024, 1, 1) + timedelta(days=index)
        for index in range(630)
    )
    expected_benchmarks = {"sh.000688": ("fallback-bar",)}

    monkeypatch.setattr(
        module,
        "_mysql_signal_dates",
        lambda start, end: signal_dates,
    )

    def benchmark_loader(start: date, end: date):
        del start, end
        return expected_benchmarks

    monkeypatch.setattr(
        module,
        "_load_benchmark_index_bars",
        benchmark_loader,
        raising=False,
    )

    def fake_mysql_loader(*args, benchmark_loader=None):
        if benchmark_loader is None:
            return None
        return benchmark_loader(args[1], args[3])

    monkeypatch.setattr(
        module,
        "load_mysql_five_day_inputs",
        fake_mysql_loader,
    )

    loaded = getattr(module, loader_name)(
        signal_dates[0],
        signal_dates[-1],
        signal_dates[-1] + timedelta(days=10),
    )

    assert loaded == expected_benchmarks


def _runtime_inputs(
    signal_dates: tuple[date, ...],
    trading_dates: tuple[date, ...],
    fingerprint: str,
) -> FiveDayRuntimeInputs:
    return FiveDayRuntimeInputs(
        signal_dates=signal_dates,
        trading_dates=trading_dates,
        bars_by_code={},
        memberships=(),
        risk_flags=(),
        coverage_by_date={
            value: ReferenceCoverage(value, True, True, True)
            for value in trading_dates
        },
        market_snapshots={
            value: MarketSnapshot(3, 60.0, 1.0, True)
            for value in trading_dates
        },
        input_fingerprint=fingerprint,
    )


def _injected_loaders():
    signal_dates = tuple(
        date(2024, 1, 1) + timedelta(days=index) for index in range(630)
    )
    split = chronological_split(signal_dates)

    def research_loader(start: date, end: date, cutoff: date):
        assert (start, end) == (signal_dates[0], signal_dates[-1])
        assert cutoff == signal_dates[-1]
        return _runtime_inputs(
            signal_dates,
            tuple(value for value in signal_dates if value <= cutoff),
            "a" * 64,
        )

    def test_loader(start: date, end: date, cutoff: date):
        assert (start, end) == (split.test[0], split.test[-1])
        assert cutoff > split.test[-1]
        return _runtime_inputs(
            split.test,
            tuple(
                split.test[0] + timedelta(days=index)
                for index in range((cutoff - split.test[0]).days + 1)
            ),
            "b" * 64,
        )

    def forward_loader(start: date, end: date, cutoff: date):
        assert start == end
        trading_dates = tuple(
            start + timedelta(days=index)
            for index in range((cutoff - start).days + 1)
        )
        return _runtime_inputs(
            (start,),
            trading_dates,
            "c" * 64,
        )

    return signal_dates, research_loader, test_loader, forward_loader


def _run_empty_lineage(module, tmp_path: Path):
    signal_dates, research_loader, test_loader, forward_loader = (
        _injected_loaders()
    )
    output = tmp_path / "artifacts"
    common = {
        "research_input_loader": research_loader,
        "test_input_loader": test_loader,
        "forward_input_loader": forward_loader,
    }
    assert module.main(
        [
            "research",
            "--signal-start",
            signal_dates[0].isoformat(),
            "--signal-end",
            signal_dates[-1].isoformat(),
            "--output-dir",
            str(output),
        ],
        **common,
    ) == 0
    research = next(output.glob("research-*.json"))
    assert module.main(
        [
            "freeze",
            "--research-artifact",
            str(research),
            "--output-dir",
            str(output),
        ],
        **common,
    ) == 0
    freeze = next(output.glob("freeze-*.json"))
    assert module.main(
        [
            "test",
            "--freeze-artifact",
            str(freeze),
            "--research-artifact",
            str(research),
            "--output-dir",
            str(output),
        ],
        **common,
    ) == 0
    test = next(output.glob("test-*.json"))
    signal_date = signal_dates[-1] + timedelta(days=1)
    assert module.main(
        [
            "forward-screen",
            "--signal-date",
            signal_date.isoformat(),
            "--freeze-artifact",
            str(freeze),
            "--test-artifact",
            str(test),
            "--output-dir",
            str(output),
        ],
        **common,
    ) == 0
    screen = next(output.glob("forward-screen-*.json"))
    return common, output, research, freeze, test, screen, signal_date


def test_injected_cli_runs_all_five_empty_safe_stages(
    tmp_path: Path,
) -> None:
    module = _load_module()
    common, output, _, freeze, test, screen, signal_date = (
        _run_empty_lineage(module, tmp_path)
    )
    screen_bytes = screen.read_bytes()
    cutoff = signal_date + timedelta(days=6)

    result = module.main(
        [
            "forward-settlement",
            "--screen-artifact",
            str(screen),
            "--outcome-cutoff",
            cutoff.isoformat(),
            "--output-dir",
            str(output),
        ],
        **common,
    )

    assert result == 0
    assert json.loads(freeze.read_text(encoding="utf-8"))["empty"] is True
    assert json.loads(test.read_text(encoding="utf-8"))[
        "forward_eligible_profile_ids"
    ] == []
    assert json.loads(screen.read_text(encoding="utf-8"))[
        "candidates"
    ] == []
    settlement = next(output.glob("forward-settlement-*.json"))
    assert json.loads(settlement.read_text(encoding="utf-8"))[
        "outcomes"
    ] == []
    assert screen.read_bytes() == screen_bytes


def test_repeated_test_returns_two_without_changing_artifact(
    tmp_path: Path,
    capsys,
) -> None:
    module = _load_module()
    common, output, research, freeze, test, _, _ = _run_empty_lineage(
        module,
        tmp_path,
    )
    before = test.read_bytes()

    result = module.main(
        [
            "test",
            "--freeze-artifact",
            str(freeze),
            "--research-artifact",
            str(research),
            "--output-dir",
            str(output),
        ],
        **common,
    )

    assert result == 2
    assert test.read_bytes() == before
    assert "五日净收益影子研究失败" in capsys.readouterr().err


def test_malformed_parent_returns_two_with_concise_chinese_error(
    tmp_path: Path,
    capsys,
) -> None:
    module = _load_module()
    malformed = tmp_path / "research.json"
    malformed.write_text("{}\n", encoding="utf-8")
    _, research_loader, test_loader, forward_loader = _injected_loaders()

    result = module.main(
        [
            "freeze",
            "--research-artifact",
            str(malformed),
            "--output-dir",
            str(tmp_path / "out"),
        ],
        research_input_loader=research_loader,
        test_input_loader=test_loader,
        forward_input_loader=forward_loader,
    )

    assert result == 2
    error = capsys.readouterr().err
    assert error.startswith("五日净收益影子研究失败：")
    assert len(error.splitlines()) == 1
