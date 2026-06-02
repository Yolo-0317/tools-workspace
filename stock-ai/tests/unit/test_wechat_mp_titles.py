"""公众号草稿标题长度与格式。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from datetime import date, datetime
from zoneinfo import ZoneInfo

from scripts.tools.wechat_mp_content import (
    TITLE_MAX,
    _clip_wechat_title,
    _dragon_title,
    _extract_market_hook,
    _market_title,
    _top5_title,
)


class _Pick:
    def __init__(self, name: str) -> None:
        self.name = name


def test_clip_respects_max_len() -> None:
    long = "六月二日收盘｜中东局势与半导体板块情绪回暖观察"
    assert len(_clip_wechat_title(long)) <= TITLE_MAX


def test_market_title_from_ai() -> None:
    ai = """【AI 综合解读】
📊 大盘与外围
中东仍是主要外部变量。
📰 国内要闻
· 联芸科技向特定对象发行A股申请获上交所受理
· 华为韬定律引发热议，半导体产业范式升温
"""
    hook = _extract_market_hook(ai)
    assert "半导体" in hook or "联芸" in hook or "华为" in hook
    title = _market_title(ai, now=datetime(2026, 6, 2, 17, 45, tzinfo=ZoneInfo("Asia/Shanghai")), slot="17:45")
    assert len(title) <= TITLE_MAX
    assert "？" in title or "！" in title


def test_top5_title_with_names() -> None:
    picks = [_Pick("京东方A"), _Pick("江苏国信"), _Pick("莱宝高科")]
    title = _top5_title(picks, trade_date=date(2026, 6, 2))
    assert len(title) <= TITLE_MAX
    assert "京东方" in title
    assert "？" in title or "！" in title


def test_dragon_title() -> None:
    hdr = {"phase": "退潮", "main_theme": "动力煤"}
    dragons = [{"name": "中京电子", "ts_code": "000539", "board_height": 4}]
    title = _dragon_title(hdr, dragons, trade_date=date(2026, 6, 1))
    assert len(title) <= TITLE_MAX
    assert "退潮" in title or "别" in title
