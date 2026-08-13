from __future__ import annotations

import json
from datetime import date

from scripts.tools import selection_results
from scripts.tools.selection_results import DEFAULT_WECHAT_TOP5_STRATEGIES, wechat_top5_strategies


def test_unpromoted_gene_lane_is_not_in_default_top5(monkeypatch) -> None:
    monkeypatch.delenv("WECHAT_MP_TOP5_STRATEGIES", raising=False)
    monkeypatch.delenv("LIMIT_UP_GENE_PROMOTION_ARTIFACT", raising=False)

    assert "limit_up_gene_watch" not in DEFAULT_WECHAT_TOP5_STRATEGIES
    assert "limit_up_gene_watch" not in wechat_top5_strategies()


def test_promoted_current_gene_lane_enters_top5_sources(monkeypatch, tmp_path) -> None:
    path = tmp_path / "gene.json"
    payload = {
        "schema_version": "limit-up-gene-watch-validation-v1",
        "rule_version": "limit-up-gene-watch-1.0.0",
        "generated_at": "2026-08-13T01:00:00+00:00",
        "data_bounds": {"start": "2023-01-03", "end": "2026-08-12"},
        "split_bounds": {
            "train": {"start": "2023-01-03", "end": "2024-08-01"},
            "validation": {"start": "2024-08-02", "end": "2025-06-01"},
            "test": {"start": "2025-06-02", "end": "2026-08-12"},
        },
        "costs": {"commission_rate": 0.0008, "slippage_rate": 0.001},
        "hold_days": 5,
        "selected_profile": "limit_up_gene_watch",
        "metrics": {
            "baseline_test": {"trade_count": 200, "wins": 80, "expectancy": 0.1, "shape_counts": {"COMBINED": 200}, "max_drawdown_pct": 10, "profit_loss_ratio": 1.2},
            "candidate_test": {"trade_count": 120, "wins": 72, "expectancy": 0.8, "shape_counts": {"LIMIT_UP_GENE": 120}, "max_drawdown_pct": 10, "profit_loss_ratio": 1.8},
        },
        "promoted": True,
        "reasons": [],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.delenv("WECHAT_MP_TOP5_STRATEGIES", raising=False)
    monkeypatch.setenv("LIMIT_UP_GENE_PROMOTION_ARTIFACT", str(path))
    monkeypatch.setattr(selection_results, "latest_selection_trade_date", lambda **kwargs: date(2026, 8, 12))

    assert "limit_up_gene_watch" in wechat_top5_strategies()
