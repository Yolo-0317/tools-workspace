from __future__ import annotations

from datetime import date, datetime, timezone

from stock_ai.buy_point_selection.reference_data import sync_reference_data


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
