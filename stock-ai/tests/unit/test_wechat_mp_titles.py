"""公众号草稿标题长度与格式。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from datetime import datetime
from zoneinfo import ZoneInfo

from scripts.tools.wechat_mp_content import (
    TITLE_MAX,
    _clip_wechat_title,
    _extract_market_hook,
    _market_title,
    _news_title,
    _titles_too_similar,
)


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


def test_market_title_by_edition() -> None:
    ai = "富时A50期货盘前微跌，煤化工煤油比走阔，MLCC产能缺口，半导体震荡。"
    now = datetime(2026, 6, 2, 17, 45, tzinfo=ZoneInfo("Asia/Shanghai"))
    peer = "收盘复盘：油价+半导体牵动哪些线？"
    pre = _market_title(ai, now=now, edition="pre", peer_title=peer)
    mid = _market_title(ai, now=now, edition="midday")
    close = _market_title(ai, now=now, slot="17:45", edition="close")
    assert "盘前" in pre or "开市" in pre or "开盘" in pre or "早读" in pre
    assert "牵动哪些线" not in pre
    assert not _titles_too_similar(pre, peer)
    assert "午间" in mid or "半日" in mid or "午盘" in mid
    assert "收盘" in close or "盘后" in close or "复盘" in close or "17:00" in close
    assert close[:15].find("A股") >= 0 or close[:15].find("收盘") >= 0 or close[:15].find("复盘") >= 0
    assert "+小金属" not in close and "+半" not in close
    assert len(close) <= TITLE_MAX


def test_market_news_titles_differ() -> None:
    now = datetime(2026, 6, 2, 17, 45, tzinfo=ZoneInfo("Asia/Shanghai"))
    market_blob = "半导体板块走强，指数与外围分化，结构判断偏震荡。"
    news_items = [
        {"title": "金饰克价已大降300元"},
        {"title": "宏观快讯与外围油价波动"},
        {"title": "某龙头公司发布年报"},
    ]
    market = _market_title(market_blob, now=now, slot="17:45", edition="close")
    news = _news_title(news_items, now=now, peer_title=market)
    assert len(market) <= TITLE_MAX
    assert len(news) <= TITLE_MAX
    assert not _titles_too_similar(market, news)
    assert any(w in news for w in ("10条", "快讯", "7×24", "要闻", "A股"))
    assert "A股" in news or "快讯" in news
    assert "别漏看" not in market
    assert "别漏看" not in news
