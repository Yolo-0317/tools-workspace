"""龙头公众号成稿（交易员 + SOP）。"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.wechat_mp_dragons_article import (
    DragonSopPack,
    SOP_CACHE_ROOT,
    _load_sop_cache,
    _save_sop_cache,
    _template_trader_body,
    generate_dragons_trader_body,
    sanitize_dragons_public_text,
    strip_dragon_title_echo,
)


def _sample_bundle() -> dict:
    return {
        "header": {
            "trade_date": "2026-06-02",
            "checklist_slot": "eod",
            "phase": "分歧",
            "phase_vs_yesterday": "持平",
            "main_theme": "电力",
            "limit_up_count": 45,
            "limit_down_count": 12,
            "up_down_ratio": "1.2",
            "max_board_height": 4,
            "explode_rate_pct": 28.5,
            "total_amount_yi": 9800,
            "position_cap_pct": 30,
            "action_summary": "收缩试错",
            "tomorrow_plan": "只看龙头分歧回封",
        },
        "dragon_items": [
            {
                "rank_no": 1,
                "ts_code": "600000.SH",
                "name": "测试龙一",
                "board_height": 3,
                "main_theme": "电力",
                "checklist_pass": 5,
                "notes": "换手充分",
            },
        ],
    }


def test_template_has_trader_sections() -> None:
    bundle = _sample_bundle()
    hdr = bundle["header"]
    packs = [
        DragonSopPack(
            rank=1,
            code="600000",
            name="测试龙一",
            boards=3,
            theme="电力",
            checklist_pass=5,
            notes="换手充分",
            preliminary="基本面数据充足",
            technical="MA5上穿MA10",
            sop_ok=True,
        )
    ]
    body = _template_trader_body(
        hdr=hdr,
        metrics_block="· 情绪阶段：分歧",
        packs=packs,
        td_s="2026-06-02",
        slot_label="eod",
    )
    assert "> 龙头拆解" in body
    assert "地位：" in body
    assert "博弈：" in body
    assert "/7" not in body
    assert "系统筛选用分" not in body
    assert "内部认可" not in body


def test_strip_dragon_title_echo_removes_title_line() -> None:
    title = "情绪发酵怎么玩？大有能源5板还在榜"
    body = (
        f"{title}\n"
        "> 情绪与盘面\n"
        "数据日 2026-06-05（eod）\n"
        "· 情绪阶段：发酵"
    )
    out = strip_dragon_title_echo(body, title=title)
    assert title not in out
    assert out.startswith("> 情绪与盘面")
    assert "数据日 2026-06-05" in out


def test_sanitize_dragons_strips_internal_approval_wording() -> None:
    raw = "龙头确认 7/7 内部是认可的，值得推荐买入。"
    out = sanitize_dragons_public_text(raw)
    assert "内部认可" not in out
    assert "龙头确认" not in out
    assert "/7" not in out
    assert "系统筛选用分" not in out
    assert "推荐" not in out


@patch("scripts.tools.wechat_mp_dragons_article.is_llm_configured", return_value=False)
@patch("scripts.tools.wechat_mp_dragons_article.collect_dragon_sop_packages")
def test_generate_without_llm(mock_sop, _mock_llm) -> None:
    mock_sop.return_value = []
    body = generate_dragons_trader_body(_sample_bundle(), checklist_slot="eod")
    assert "> 情绪与盘面" in body
    assert "> 明日计划与纪律" in body


def test_sop_cache_isolated_from_top5_preliminary() -> None:
    assert "wechat_mp_dragon_sop" in str(SOP_CACHE_ROOT)
    assert "sop_preliminary" not in str(SOP_CACHE_ROOT)


def test_sop_cache_roundtrip(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        "scripts.tools.wechat_mp_dragons_article.SOP_CACHE_ROOT",
        tmp_path,
    )
    _save_sop_cache("600000", "2026-06-02", "缓存正文", "MA5上穿")
    hit = _load_sop_cache("600000", "2026-06-02")
    assert hit is not None
    assert hit[0] == "缓存正文"
    assert "MA5" in hit[1]
    assert (tmp_path / "2026-06-02" / "600000_fast.md").is_file()
