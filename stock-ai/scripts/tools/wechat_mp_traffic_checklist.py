#!/usr/bin/env python3
"""公众号阅读量优化清单（自动项 + 后台人工项）。"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

from scripts.tools.wechat_mp_eval import (
    BANNED_TITLE_WORDS,
    DIGEST_MAX,
    TITLE_MAX,
    _count_section_heads,
    _opening_block,
    _paragraphs,
    strip_html,
)
from scripts.tools.wechat_mp_monetization import (
    _ENGAGEMENT_POOL,
    count_vertical_hits,
    vertical_hints_for_kind,
    vertical_words_min,
)
from scripts.tools.wechat_mp_seo import (
    DIGEST_SEO_CORE,
    recommended_hashtags,
    title_front_has_search_keywords,
    title_has_search_keywords,
)

# 移动端约 3 分钟阅读（纯文字，不含 HTML）
READ_MIN_CHARS = 400
READ_MAX_CHARS = 3200
OPENING_MIN_CHARS = 35


@dataclass
class TrafficCheckItem:
    id: str
    label: str
    passed: bool
    hint: str = ""
    manual: bool = False


@dataclass
class TrafficChecklistReport:
    kind: str
    title: str
    edition: str | None
    items: list[TrafficCheckItem] = field(default_factory=list)

    @property
    def auto_passed(self) -> int:
        return sum(1 for i in self.items if not i.manual and i.passed)

    @property
    def auto_total(self) -> int:
        return sum(1 for i in self.items if not i.manual)

    @property
    def manual_pending(self) -> list[TrafficCheckItem]:
        return [i for i in self.items if i.manual and not i.passed]

    @property
    def verdict(self) -> str:
        failed = [i for i in self.items if not i.manual and not i.passed]
        if not failed:
            return "自动项通过"
        return f"待优化 {len(failed)} 项"

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["auto_passed"] = self.auto_passed
        d["auto_total"] = self.auto_total
        d["verdict"] = self.verdict
        return d


def _body_plain(body: str, *, content_html: str = "") -> str:
    plain = strip_html(body)
    if content_html and "<p" in content_html.lower():
        plain = re.sub(r"</p>\s*", "\n\n", plain, flags=re.I)
        plain = re.sub(r"<br\s*/?>", "\n", plain, flags=re.I)
        plain = re.sub(r"\n{3,}", "\n\n", plain).strip()
    return plain


def _has_engagement_hook(body: str, *, kind: str) -> bool:
    pool = _ENGAGEMENT_POOL.get(kind.strip().lower(), ())
    tail = body[-400:]
    if "？" in tail and "留言" in tail:
        return True
    return any(p[:10] in body for p in pool)


def _has_recommend_hook(body: str) -> bool:
    from scripts.tools.wechat_mp_monetization import _RECOMMEND_HOOK_MARKERS

    return any(m in body for m in _RECOMMEND_HOOK_MARKERS)


def _digest_has_seo(digest: str, kind: str, *, edition: str | None) -> bool:
    core = DIGEST_SEO_CORE.get(kind, ())
    if kind == "market" and edition:
        from scripts.tools.wechat_mp_seo import market_digest_core

        core = market_digest_core(edition)
    return any(k and k in digest for k in core)


def run_traffic_checklist(
    *,
    title: str,
    digest: str,
    body: str,
    kind: str,
    edition: str | None = None,
    content_html: str = "",
    recommended_tags: list[str] | None = None,
) -> TrafficChecklistReport:
    plain = _body_plain(body, content_html=content_html)
    opening = _opening_block(plain)
    items: list[TrafficCheckItem] = []

    t = (title or "").strip()
    items.append(
        TrafficCheckItem(
            id="title_len",
            label="标题 ≤32 字",
            passed=len(t) <= TITLE_MAX and len(t) >= 8,
            hint=f"当前 {len(t)} 字" if t else "标题为空",
        )
    )
    items.append(
        TrafficCheckItem(
            id="title_hook",
            label="标题含 ？ 或 ！",
            passed=bool(re.search(r"[？?！!]", t)),
            hint="疑问/感叹句更易点开",
        )
    )
    items.append(
        TrafficCheckItem(
            id="title_front",
            label="标题前 15 字有信息",
            passed=len(t[:15].strip()) >= 6,
            hint=f"列表截断处：{t[:15]!r}",
        )
    )
    items.append(
        TrafficCheckItem(
            id="title_banned",
            label="无标题党禁词",
            passed=not any(w in t for w in BANNED_TITLE_WORDS),
            hint="禁：震惊/重磅/100倍 等",
        )
    )
    if kind in {"market", "news", "top5", "dragons"}:
        items.append(
            TrafficCheckItem(
                id="title_search_seo",
                label="标题含搜一搜词（前 15 字优先）",
                passed=title_has_search_keywords(t, kind, edition=edition)
                and title_front_has_search_keywords(t, kind, edition=edition),
                hint=f"列表截断：{t[:15]!r}；宜含 A股/选股/龙头/快讯 等",
            )
        )

    d = (digest or "").strip()
    items.append(
        TrafficCheckItem(
            id="digest_len",
            label="摘要 ≤128 字",
            passed=0 < len(d) <= DIGEST_MAX,
            hint=f"当前 {len(d)} 字",
        )
    )
    items.append(
        TrafficCheckItem(
            id="digest_seo",
            label="摘要含稿型 SEO 词",
            passed=_digest_has_seo(d, kind, edition=edition),
            hint="脚本 enrich_digest 会补 A股/盘前/收盘复盘 等",
        )
    )

    items.append(
        TrafficCheckItem(
            id="opening_conclusion",
            label="开头结论先行",
            passed=bool(opening)
            and len(opening) >= OPENING_MIN_CHARS
            and bool(re.search(r"\d|指数|涨|跌|外围|结构|收盘|盘前|午间", opening)),
            hint="首段宜含数字或盘面关键词，40 字以上",
        )
    )

    sections = _count_section_heads(plain, html=content_html or body)
    items.append(
        TrafficCheckItem(
            id="sections",
            label="至少 2 个分节标题",
            passed=sections >= 2,
            hint=f"当前 {sections} 个（> 引用块）",
        )
    )

    long_paras = [p for p in _paragraphs(plain) if len(p) > 180 and not p.startswith(">")]
    items.append(
        TrafficCheckItem(
            id="short_para",
            label="无超长段落",
            passed=len(long_paras) == 0,
            hint=f"{len(long_paras)} 段超 180 字，移动端难跳读",
        )
    )

    char_len = len(re.sub(r"\s+", "", plain))
    items.append(
        TrafficCheckItem(
            id="read_length",
            label="正文长度利于完读（约 3 分钟）",
            passed=READ_MIN_CHARS <= char_len <= READ_MAX_CHARS,
            hint=f"纯文字约 {char_len} 字（建议 {READ_MIN_CHARS}–{READ_MAX_CHARS}）",
        )
    )

    v_min = vertical_words_min()
    vertical_hits = count_vertical_hits(plain, kind)
    items.append(
        TrafficCheckItem(
            id="vertical_words",
            label=f"垂直词 ≥{v_min} 个（稿型优先表）",
            passed=len(vertical_hits) >= v_min,
            hint=(
                f"已命中：{', '.join(vertical_hits) or '无'}；"
                f"可参考稿型词表补：{', '.join(vertical_hints_for_kind(kind)[:6])}"
                if len(vertical_hits) < v_min
                else f"已命中：{', '.join(vertical_hits)}"
            ),
        )
    )

    opening_head = plain[:220]
    items.append(
        TrafficCheckItem(
            id="opening_digit",
            label="开篇 220 字内含具体数字",
            passed=bool(re.search(r"\d", opening_head)),
            hint="炸板率/涨跌家数/指数点位/涨跌幅等，提高完读与流量主曝光",
        )
    )

    items.append(
        TrafficCheckItem(
            id="engagement_hook",
            label="文末互动问句",
            passed=_has_engagement_hook(plain, kind=kind),
            hint="WECHAT_MP_ENGAGEMENT_HOOK=1 时自动追加",
        )
    )

    tags = recommended_tags or recommended_hashtags(kind, edition=edition)
    items.append(
        TrafficCheckItem(
            id="hashtags_ready",
            label="已生成推荐 #话题",
            passed=len(tags) >= 2,
            hint=" ".join(f"#{t}" for t in tags[:5]),
        )
    )

    # 后台人工项（API 无法代做）
    items.extend(
        [
            TrafficCheckItem(
                id="manual_original",
                label="发布时勾选原创（财经/科技）",
                passed=False,
                hint="mp.weixin.qq.com 发布页手动勾选",
                manual=True,
            ),
            TrafficCheckItem(
                id="manual_hashtag",
                label="原创通过后加 #话题",
                passed=False,
                hint="正文文末已写入 # 行；发布成功后仍可在后台再点 # 微调",
                manual=True,
            ),
            TrafficCheckItem(
                id="manual_recommend",
                label="引导读者点「推荐 ♡」",
                passed=_has_recommend_hook(plain),
                hint="比单纯点赞更影响朋友推荐流；`WECHAT_MP_RECOMMEND_HOOK=0` 可关",
                manual=not _has_recommend_hook(plain),
            ),
        ]
    )

    return TrafficChecklistReport(
        kind=kind,
        title=title,
        edition=edition,
        items=items,
    )


def format_traffic_report(report: TrafficChecklistReport, *, verbose: bool = True) -> str:
    lines = [
        f"【阅读量清单】{report.kind}"
        + (f" · {report.edition}" if report.edition else "")
        + f" · {report.verdict}（自动 {report.auto_passed}/{report.auto_total}）",
    ]
    if verbose:
        for item in report.items:
            mark = "✓" if item.passed else ("○" if item.manual else "✗")
            suffix = f" — {item.hint}" if item.hint else ""
            tag = " [后台]" if item.manual else ""
            lines.append(f"  {mark} {item.label}{tag}{suffix}")
    else:
        failed = [i.label for i in report.items if not i.passed and not i.manual]
        if failed:
            lines.append("待优化: " + "、".join(failed))
    return "\n".join(lines)


def print_traffic_checklist(
    kind: str,
    article: dict[str, Any],
    *,
    edition: str | None = None,
) -> TrafficChecklistReport:
    rep = run_traffic_checklist(
        title=str(article.get("title") or ""),
        digest=str(article.get("digest") or ""),
        body=str(article.get("body_text") or article.get("content") or ""),
        kind=kind,
        edition=edition,
        content_html=str(article.get("content") or ""),
        recommended_tags=list(article.get("recommended_hashtags") or []),
    )
    print(format_traffic_report(rep))
    return rep
