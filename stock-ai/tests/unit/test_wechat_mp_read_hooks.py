"""晚间稿型完读钩子。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.tools.wechat_mp_dragons_polish import _finalize_dragons_read_hooks
from scripts.tools.wechat_mp_market_polish import _finalize_market_read_hooks
from scripts.tools.wechat_mp_news_polish import finalize_news_body
from scripts.tools.wechat_mp_prose import (
    DRAGON_SECTION_TITLES,
    MARKET_SECTION_TITLES,
    NEWS_SECTION_TITLES,
    SECTOR_SECTION_TITLES,
)
from scripts.tools.wechat_mp_sector_polish import finalize_sector_body


def test_sector_section_bridges() -> None:
    body = "\n".join(f"> {t}\n内容{t}。" for t in SECTOR_SECTION_TITLES)
    out = finalize_sector_body(body, trade_label="6月4日收盘", primary_theme="化工")
    assert out.count("·") >= 2
    assert "往下看" not in out
    assert "露馅" in out or "若" in out


def test_market_read_hooks() -> None:
    s0, s1, s2 = MARKET_SECTION_TITLES
    body = f"> {s0}\n上证涨1%。\n\n> {s1}\n美元。\n\n> {s2}\n结构。"
    out = _finalize_market_read_hooks(body, edition="close")
    assert "·" in out
    assert "往下看" not in out
    assert "验证" in out or "若" in out


def test_dragons_read_hooks() -> None:
    body = "\n".join(
        [
            f"> {DRAGON_SECTION_TITLES[0]}",
            "涨停50。",
            f"> {DRAGON_SECTION_TITLES[1]}",
            "1. 甲股（000001）",
            "   逻辑",
            "2. 乙股（000002）",
            "   逻辑",
            f"> {DRAGON_SECTION_TITLES[2]}",
            "梯队",
            f"> {DRAGON_SECTION_TITLES[3]}",
            "纪律",
        ]
    )
    hdr = {"phase": "发酵", "main_theme": "算力"}
    out = _finalize_dragons_read_hooks(body, hdr=hdr)
    assert "·" in out
    assert "往下看" not in out
    assert "展开" in out or "·" in out


def test_news_item_transitions() -> None:
    sec = NEWS_SECTION_TITLES[0]
    body = (
        f"> {sec}\n"
        "1. 摘要一\n   AI点评：一\n"
        "2. 摘要二\n   AI点评：二\n"
        "3. 摘要三\n   AI点评：三\n"
    )
    out = finalize_news_body(body)
    assert out.count("·") >= 1
    assert "往下看" not in out
