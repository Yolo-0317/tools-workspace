from __future__ import annotations

from datetime import date, datetime, timezone
import importlib.util
from pathlib import Path

from stock_ai.buy_point_selection.reference_data import sync_reference_data
from stock_ai.buy_point_selection.reference_sources import ProviderFailure


SCRIPT = Path(__file__).parents[2] / "scripts" / "sync" / "sync_buy_point_reference_data.py"


class MemoryRepository:
    def __init__(self) -> None:
        self.memberships = []
        self.flags = []
        self.runs = []

    def upsert_sector_memberships(self, rows, captured_at) -> int:
        self.memberships.extend(rows)
        return len(rows)

    def upsert_risk_flags(self, rows, captured_at) -> int:
        self.flags.extend(rows)
        return len(rows)

    def save_sync_run(self, run) -> None:
        self.runs.append(run)


class FakePro:
    def __init__(self, *, fail_st: bool = False) -> None:
        self.fail_st = fail_st

    def index_classify(self, **kwargs):
        return [{"index_code": "801010.SI"}]

    def index_member_all(self, **kwargs):
        return [
            {
                "ts_code": "600000.SH",
                "l1_code": "801010.SI",
                "l1_name": "农林牧渔",
                "in_date": "20200102",
                "out_date": "20231229",
            },
            {
                "ts_code": "600001.SH",
                "l1_code": "801010.SI",
                "l1_name": "农林牧渔",
                "in_date": "20240102",
                "out_date": "",
            }
        ]

    def stock_st(self, **kwargs):
        if self.fail_st:
            raise RuntimeError("permission denied")
        return [{"ts_code": "600002.SH", "trade_date": "20250806", "type_name": "风险警示板"}]

    def anns_d(self, **kwargs):
        return [
            {
                "ts_code": "600003.SH",
                "ann_date": "20250806",
                "title": "公司收到中国证监会立案调查告知书",
                "url": "https://example.test/notice",
            }
        ]


class NoPermissionPro:
    def _deny(self):
        raise Exception("抱歉，您没有接口(stock_st)访问权限")

    def index_classify(self, **kwargs):
        self._deny()

    def stock_st(self, **kwargs):
        self._deny()

    def anns_d(self, **kwargs):
        self._deny()


NOW = datetime(2025, 8, 6, 10, tzinfo=timezone.utc)


def test_sync_persists_each_complete_point_in_time_dataset() -> None:
    """Catches a successful API fetch not becoming queryable reference facts."""
    repository = MemoryRepository()

    runs = sync_reference_data(
        FakePro(),
        repository,
        (date(2025, 8, 5), date(2025, 8, 6)),
        captured_at=NOW,
    )

    assert len(repository.memberships) == 1
    assert {(flag.code, flag.flag_type) for flag in repository.flags} == {
        ("600002", "ST"),
        ("600003", "REGULATORY_INVESTIGATION"),
    }
    assert [run.status for run in runs] == ["COMPLETE", "COMPLETE", "COMPLETE"]


def test_sync_failure_marks_only_failed_dataset_and_continues() -> None:
    """Catches one provider error falsely marking all coverage complete or aborting audit data."""
    repository = MemoryRepository()

    runs = sync_reference_data(
        FakePro(fail_st=True),
        repository,
        (date(2025, 8, 5), date(2025, 8, 6)),
        captured_at=NOW,
    )

    assert [run.status for run in runs] == ["COMPLETE", "FAILED", "COMPLETE"]
    assert runs[1].error_code == "RuntimeError"
    assert any(flag.flag_type == "REGULATORY_INVESTIGATION" for flag in repository.flags)


def test_sync_classifies_tushare_permission_denial_for_audit() -> None:
    """Catches Tushare's bare Exception hiding the actionable failure reason."""
    repository = MemoryRepository()

    runs = sync_reference_data(
        NoPermissionPro(),
        repository,
        (date(2025, 8, 5), date(2025, 8, 6)),
        captured_at=NOW,
    )

    assert [run.error_code for run in runs] == [
        "TUSHARE_PERMISSION_DENIED",
        "TUSHARE_PERMISSION_DENIED",
        "TUSHARE_PERMISSION_DENIED",
    ]


def test_manual_sync_accepts_latest_as_the_end_boundary() -> None:
    """Catches the documented safe refresh command diverging from its CLI parser."""
    spec = importlib.util.spec_from_file_location("sync_buy_point_reference_data", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    args = module.build_parser().parse_args(["--start", "2024-01-02", "--end", "latest"])
    assert args.end is None


def _load_script():
    spec = importlib.util.spec_from_file_location("sync_buy_point_reference_data_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_reference_cli_defaults_to_cninfo_baostock() -> None:
    module = _load_script()
    args = module.build_parser().parse_args(
        ["--start", "2024-01-02", "--end", "latest"]
    )
    assert args.provider == "cninfo-baostock"


def test_reference_cli_defaults_to_all_datasets() -> None:
    module = _load_script()

    args = module.build_parser().parse_args(
        ["--start", "2024-01-02", "--end", "latest"]
    )

    assert args.datasets == "all"


def test_reference_cli_accepts_announcement_only_dataset() -> None:
    module = _load_script()

    args = module.build_parser().parse_args(
        [
            "--start",
            "2023-12-26",
            "--end",
            "2026-08-04",
            "--datasets",
            "announcement",
            "--announcement-provider",
            "eastmoney",
        ]
    )

    assert args.datasets == "announcement"


def test_reference_cli_keeps_tushare_as_explicit_fallback() -> None:
    module = _load_script()
    args = module.build_parser().parse_args(
        [
            "--start",
            "2024-01-02",
            "--end",
            "latest",
            "--provider",
            "tushare",
        ]
    )
    assert args.provider == "tushare"


def test_reference_cli_accepts_raw_eastmoney_announcement_fallback() -> None:
    module = _load_script()
    args = module.build_parser().parse_args(
        [
            "--start",
            "2024-01-02",
            "--end",
            "latest",
            "--announcement-provider",
            "eastmoney",
        ]
    )
    assert args.announcement_provider == "eastmoney"


def test_reference_cli_help_lists_both_provider_modes(capsys) -> None:
    module = _load_script()
    try:
        module.build_parser().parse_args(["--help"])
    except SystemExit as exc:
        assert exc.code == 0
    output = capsys.readouterr().out
    assert "cninfo-baostock" in output
    assert "tushare" in output


class _Rows:
    def __init__(self, rows):
        self.rows = rows

    def mappings(self):
        return self

    def __iter__(self):
        return iter(self.rows)


class _Connection:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def execute(self, statement, parameters):
        self.calls.append((str(statement), parameters))
        return _Rows(self.rows)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None


class _Engine:
    def __init__(self, rows):
        self.connection = _Connection(rows)

    def connect(self):
        return self.connection


def test_universe_by_date_uses_one_query_and_keeps_recently_suspended_main_board() -> None:
    module = _load_script()
    start = date(2025, 8, 5)
    end = date(2025, 8, 6)
    engine = _Engine(
        [
            {
                "ts_code": "600001.SH",
                "first_date": date(2025, 2, 8),
                "last_date": date(2025, 2, 8),
            },
            {"ts_code": "600002.SH", "first_date": end, "last_date": end},
            {"ts_code": "300001.SZ", "first_date": end, "last_date": end},
        ]
    )

    universe = module._universe_by_date(engine, (start, end))

    assert len(engine.connection.calls) == 1
    statement, parameters = engine.connection.calls[0]
    assert "BETWEEN :lookback_start AND :end_date" in statement
    assert "MIN(trade_date) AS first_date" in statement
    assert "MAX(trade_date) AS last_date" in statement
    assert "GROUP BY ts_code" in statement
    assert parameters == {
        "lookback_start": date(2025, 2, 6),
        "end_date": end,
    }
    assert universe == {
        start: frozenset({"600001"}),
        end: frozenset({"600001", "600002"}),
    }


def test_universe_merges_suffixed_and_unsuffixed_code_lifespans() -> None:
    """Catches a short duplicate code history shrinking early PIT universe coverage."""
    module = _load_script()
    start = date(2023, 12, 26)
    end = date(2025, 2, 7)
    engine = _Engine(
        [
            {
                "ts_code": "600001",
                "first_date": date(2023, 6, 29),
                "last_date": end,
            },
            {
                "ts_code": "600001.SH",
                "first_date": date(2025, 1, 2),
                "last_date": end,
            },
        ]
    )

    universe = module._universe_by_date(engine, (start, end))

    assert universe[start] == frozenset({"600001"})
    assert universe[end] == frozenset({"600001"})


def test_provider_failure_prints_only_safe_error_code(monkeypatch, capsys) -> None:
    module = _load_script()
    engine = object()
    monkeypatch.setattr(module, "_engine", lambda: engine)
    monkeypatch.setattr(module, "_trade_dates", lambda *_: (date(2025, 8, 6),))
    monkeypatch.setattr(
        module,
        "_universe_by_date",
        lambda *_: {date(2025, 8, 6): frozenset({"600001"})},
    )
    monkeypatch.setattr(module, "_cninfo", lambda: object())
    monkeypatch.setattr(module, "_baostock", lambda: object())
    monkeypatch.setattr(
        module,
        "sync_alternative_reference_data",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            ProviderFailure("CNINFO", "announcements", "PROVIDER_UNAVAILABLE")
        ),
    )

    result = module.main(["--start", "2025-08-06", "--end", "2025-08-06"])

    output = capsys.readouterr().out
    assert result == 2
    assert output.strip() == "点时参考数据同步失败：PROVIDER_UNAVAILABLE"
    assert "announcements" not in output


def test_announcement_only_cli_does_not_build_universe_or_baostock(
    monkeypatch,
    capsys,
) -> None:
    module = _load_script()
    day = date(2025, 8, 6)
    engine = object()
    repository = object()

    monkeypatch.setattr(module, "_engine", lambda: engine)
    monkeypatch.setattr(module, "_trade_dates", lambda *_: (day,))
    monkeypatch.setattr(
        module,
        "_universe_by_date",
        lambda *_: (_ for _ in ()).throw(AssertionError("universe called")),
    )
    monkeypatch.setattr(
        module,
        "_baostock",
        lambda: (_ for _ in ()).throw(AssertionError("baostock called")),
    )
    monkeypatch.setattr(module, "_eastmoney", lambda: object())
    monkeypatch.setattr(module, "SQLReferenceRepository", lambda _: repository)

    def run_announcements(*args, progress, **kwargs):
        progress(module.AnnouncementSyncProgress(1, 1, 0, 0, 1, True))
        return ()

    monkeypatch.setattr(
        module,
        "sync_announcement_reference_data",
        run_announcements,
        raising=False,
    )

    result = module.main(
        [
            "--start",
            day.isoformat(),
            "--end",
            day.isoformat(),
            "--datasets",
            "announcement",
            "--announcement-provider",
            "eastmoney",
        ]
    )

    assert result == 0
    assert capsys.readouterr().out.splitlines() == [
        "announcement-progress: processed=1 complete=1 skipped=0 failed=0 total=1 terminal=true"
    ]


def test_announcement_only_cli_rejects_tushare_before_provider_setup(
    monkeypatch,
    capsys,
) -> None:
    module = _load_script()
    monkeypatch.setattr(
        module,
        "_engine",
        lambda: (_ for _ in ()).throw(AssertionError("engine called")),
    )

    result = module.main(
        [
            "--start",
            "2025-08-06",
            "--end",
            "2025-08-06",
            "--provider",
            "tushare",
            "--datasets",
            "announcement",
        ]
    )

    assert result == 2
    assert capsys.readouterr().out.strip() == "点时参考数据同步失败：ValueError"
