from __future__ import annotations

from datetime import date
import os
import uuid

import pytest
from sqlalchemy import text

from scripts.tools.portfolio_db import (
    finish_limit_up_research_run,
    get_engine,
    save_limit_up_research_bundle,
    start_limit_up_research_run,
)
from stock_ai.limit_up_research.models import ForwardLabel, PoolFact, SelectionAttribution


pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_MYSQL_INTEGRATION") != "1",
    reason="set RUN_MYSQL_INTEGRATION=1 to exercise the configured MySQL ledger",
)


def test_same_fixture_upserts_without_duplicate_research_rows() -> None:
    engine = get_engine()
    assert engine is not None
    offset = int(uuid.uuid4().hex[:4], 16) % 300
    fixture_date = date(1901, 1, 1).replace(day=1)  # fixed non-production year
    code = f"{900000 + offset:06d}"
    run_id = start_limit_up_research_run(
        fixture_date, source="mysql-integration-test", engine=engine
    )
    fact = PoolFact(
        fixture_date, "LIMIT_UP", code, "集成测试", 10.0, 100.0, 1,
        "测试", None, None, 0, 10.0, (), {"c": code},
    )
    attribution = SelectionAttribution(
        fixture_date, code, "combined", False, None, None, None,
        "EXPLAINER_UNAVAILABLE", "EXPLAINER_UNAVAILABLE",
        ("EXPLAINER_UNAVAILABLE",), {}, "integration-test",
        selection_date=fixture_date,
    )
    label = ForwardLabel(
        fixture_date, code, "T1", fixture_date, 1.0, 1.0, 0.0, 0.0, 0.0,
        False, 1, True, (),
    )
    try:
        for _ in range(2):
            save_limit_up_research_bundle(
                run_id, fixture_date, (fact,), (attribution,), (label,), engine=engine
            )
        with engine.connect() as conn:
            counts = (
                conn.execute(text(
                    "SELECT COUNT(*) FROM limit_up_research_pool "
                    "WHERE trade_date=:d AND ts_code=:c"
                ), {"d": fixture_date, "c": code}).scalar_one(),
                conn.execute(text(
                    "SELECT COUNT(*) FROM limit_up_selection_attribution "
                    "WHERE trade_date=:d AND ts_code=:c"
                ), {"d": fixture_date, "c": code}).scalar_one(),
                conn.execute(text(
                    "SELECT COUNT(*) FROM limit_up_forward_labels "
                    "WHERE signal_date=:d AND ts_code=:c"
                ), {"d": fixture_date, "c": code}).scalar_one(),
            )
        assert counts == (1, 1, 1)
        finish_limit_up_research_run(run_id, status="SUCCEEDED", engine=engine)
    finally:
        with engine.begin() as conn:
            conn.execute(text(
                "DELETE FROM limit_up_selection_attribution WHERE source_run_id=:run_id"
            ), {"run_id": run_id})
            conn.execute(text(
                "DELETE FROM limit_up_research_pool WHERE source_run_id=:run_id"
            ), {"run_id": run_id})
            conn.execute(text(
                "DELETE FROM limit_up_forward_labels WHERE signal_date=:d AND ts_code=:c"
            ), {"d": fixture_date, "c": code})
            conn.execute(text(
                "DELETE FROM limit_up_research_runs WHERE run_id=:run_id"
            ), {"run_id": run_id})
