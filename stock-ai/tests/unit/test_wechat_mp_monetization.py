"""流量主成稿优化。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.wechat_mp_monetization import (
    append_follow_hook,
    append_recommend_hook,
    polish_for_traffic,
    split_disclaimer,
    strip_follow_hook,
    strip_recommend_hook,
    strip_writing_reply_inducement,
)


def test_polish_for_traffic_no_ad_marker_by_default() -> None:
    body = "> 盘面速览\n指数涨0.4%\n\n> 外围与资金\n美股小涨"
    out = polish_for_traffic(body, kind="market")
    assert "· · ·" not in out


def test_append_recommend_hook() -> None:
    body = "> 盘面速览\n内容"
    out = append_recommend_hook(body, kind="market")
    assert "点文章下方「推荐」" in out
    assert "♡" not in out


def test_tv_review_skips_recommend_hook() -> None:
    body = "> 四年空窗后回来\n内容\n\n所以，你站开刷还是囤着？"
    out = polish_for_traffic(body, kind="tv_review")
    assert "点文章下方「推荐」" not in out
    assert "复盘的朋友" not in out
    assert "星标本号" in out


def test_strip_recommend_hook() -> None:
    body = "正文\n\n若这篇对你有用，欢迎点文章下方「推荐 ♡」，也方便推给同样在复盘的朋友。"
    out = strip_recommend_hook(body)
    assert "复盘的朋友" not in out
    assert out == "正文"


def test_append_follow_hook_hotspot() -> None:
    body = "8月2日，《天才女友》开播引发选角讨论。"
    out = append_follow_hook(body, kind="hotspot")
    assert "星标本号" in out
    assert "回复「写作」" not in out
    assert "大模型辅助写作" not in out
    assert "收盘" not in out
    assert "复盘" not in out
    assert append_follow_hook(out, kind="hotspot") == out


def test_append_follow_hook_tv_review() -> None:
    body = "暑期档票房破70亿，八仙成黑马。"
    out = append_follow_hook(body, kind="tv_review")
    assert "星标本号" in out


def test_polish_for_traffic_hotspot_follow_before_recommend() -> None:
    body = "伪造结婚证做试管案引发多方讨论。"
    out = polish_for_traffic(body, kind="hotspot")
    assert "星标本号" in out
    assert "点文章下方「推荐」" not in out
    assert "回复「写作」" not in out


def test_strip_follow_hook() -> None:
    body = (
        "正文\n\n"
        "我们会继续整理社会与文娱热点；星标本号，下一篇不易漏看。"
        "关注后回复「写作」，可领大模型辅助写作技巧笔记。"
    )
    out = strip_follow_hook(body)
    assert "关注本号" not in out
    assert "回复「写作」" not in out
    assert out == "正文"


def test_strip_writing_reply_inducement_inline() -> None:
    body = (
        "我们会继续整理社会与文娱热点；星标本号，下一篇不易漏看。"
        "关注后回复「写作」，可领大模型辅助写作技巧笔记。"
    )
    out = strip_writing_reply_inducement(body)
    assert "回复「写作」" not in out
    assert "星标本号" in out


def test_engagement_before_disclaimer() -> None:
    disc = "本文为作者个人投资日记与信息整理，不构成投资建议。市场有风险，决策自负。"
    body = f"> 盘面速览\n内容\n\n{disc}"
    core, tail = split_disclaimer(body)
    polished = polish_for_traffic(core, kind="market")
    merged = f"{polished}\n\n{tail}"
    assert ("留言" in merged) or ("交流" in merged)
    assert "点文章下方「推荐」" in merged
    assert merged.index("交流" if "交流" in merged else "留言") < merged.index("本文为作者")
    assert merged.index("点文章下方「推荐」") < merged.index("本文为作者")
