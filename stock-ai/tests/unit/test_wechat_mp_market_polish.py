"""market 成稿优化。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.wechat_mp_eval import evaluate_article
from scripts.tools.wechat_mp_market_polish import (
    align_market_title_mood,
    detect_market_mood,
    finalize_market_body,
    inject_market_opening_lede,
    split_long_paragraphs,
)


SAMPLE = """> 盘面速览

截至午间收盘，上证指数报4097.94点，涨0.56%；深证成指涨2.31%；创业板指涨3.97%；科创50指数大涨4.78%。全市场涨跌家数比为1927:3270，个股层面跌多涨少，指数与个股未形成共振。权重股托底，中小盘及科技类主题显著活跃。半日结构显示，市场资金集中涌入科创及成长方向，大盘指数温和上行，午后需警惕分化加剧，指数能否站稳取决于科技主线是否扩散。

> 外围与资金

隔夜美股三大指数小幅收涨。

> 结构判断

我们认为，指数强、个股弱。值得关注的是，科技主线集中。向后看，盯涨跌家数修复。"""


def test_inject_opening_lede_before_market_section() -> None:
    out = inject_market_opening_lede(SAMPLE, edition="midday")
    lines = [ln for ln in out.splitlines() if ln.strip()]
    assert not lines[0].startswith(">")
    assert "4097" in lines[0] or "0.56" in lines[0]
    assert any("盘面速览" in ln for ln in lines)


def test_finalize_passes_opening_eval() -> None:
    out = finalize_market_body(SAMPLE, edition="midday")
    rep = evaluate_article(
        title="周三午间｜创业板+情绪，午后怎么走？",
        digest="摘要",
        body=out,
        kind="market",
    )
    opening = rep.dimensions[1]
    assert opening.score >= 10, opening.notes


def test_align_title_mood_fixes_misleading_pudie() -> None:
    title = "收盘复盘：今日市场呈普跌格局牵动哪些线？"
    fixed = align_market_title_mood(title, SAMPLE)
    assert "普跌" not in fixed
    assert detect_market_mood(SAMPLE) == "index_up_breadth_weak"


def test_split_long_paragraphs() -> None:
    long_para = "。".join(["这是一句足够长的测试内容" + str(i) for i in range(12)])
    body = f"> 结构判断\n\n{long_para}。"
    out = split_long_paragraphs(body, max_chars=80)
    paras = [ln for ln in out.splitlines() if ln.strip() and not ln.startswith(">")]
    assert len(paras) >= 2
