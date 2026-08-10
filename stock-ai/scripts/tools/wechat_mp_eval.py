#!/usr/bin/env python3
"""公众号正文质量评分（标题 / 开头 / 正文 / 去AI / 结尾 + 合规）。"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from html import unescape
from pathlib import Path
from typing import Any

from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

TITLE_MAX = 32
DIGEST_MAX = 128
AI_FLAVOR_DRAFT_MAX = 20  # 可进草稿箱 / 推稿门禁默认 AI 味上限（0–100，越低越好）

# 与 writing-guide / test_wechat_mp_workspace_article 对齐
BANNED_AI_PHRASES: tuple[str, ...] = (
    "目标很直白",
    "一站式",
    "助力",
    "赋能",
    "生态",
    "链路",
    "②",
    "智能体",
    "体例",
    "流水线",
    "物理隔开",
    "强绑",
    "编码助手",
    "留言即可",
    "铺全景",
    "幕后",
    "四槽",
    "行情查询工具接口",
    "综上所述",
    "值得注意的是",
    "值得一提的是",
    "在当今",
    "随着时代的发展",
    "不可否认",
    "颠覆认知",
    "遥遥领先",
    "今天给大家分享",
    "本文将为大家介绍",
)

BANNED_TITLE_WORDS = ("震惊", "重磅", "炸裂", "逆天", "100倍", "100%")

COMPLIANCE_CHECKS: tuple[tuple[str, str, int], ...] = ()  # 见 wechat_mp_public.PUBLIC_COMPLIANCE_CHECKS

_OPENING_FLUFF = re.compile(r"^(在当今|随着|近年来|不可否认)")
_TRANSITION_AI = re.compile(r"首先|其次|最后|综上")
_DEGREE_WORDS = re.compile(r"非常|极其|十分|相当")
_SYMMETRIC = re.compile(r"既要.+也要|不仅要.+还要")
_EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001FAFF"
    "\u2600-\u27BF"
    "\uFE0F"
    "]+",
    flags=re.UNICODE,
)
_HTML_TAG_RE = re.compile(r"<[^>]+>")


@dataclass
class DimensionScore:
    name: str
    score: int
    max_score: int
    notes: list[str] = field(default_factory=list)


@dataclass
class EvalReport:
    title: str
    digest: str
    kind: str
    dimensions: list[DimensionScore]
    compliance_failures: list[str]
    ai_flavor_score: int  # 0=真人感强, 100=AI味重（与 Qson8 量表一致）
    total_score: int
    max_total: int
    verdict: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def strip_html(text: str) -> str:
    text = _HTML_TAG_RE.sub("", text)
    return unescape(text).strip()


def _paragraphs(body: str) -> list[str]:
    blocks = [b.strip() for b in re.split(r"\n\s*\n", body.strip()) if b.strip()]
    return blocks


def _opening_block(body: str) -> str:
    paras = _paragraphs(body)
    if not paras:
        return ""
    first = paras[0]
    if first.startswith(">") or re.match(r"^[一二三四五六七八九十]、", first):
        return ""
    return first


def _score_title(title: str, *, kind: str) -> DimensionScore:
    notes: list[str] = []
    score = 0
    t = (title or "").strip()
    if not t:
        return DimensionScore("标题", 0, 15, ["标题为空"])

    if len(t) <= TITLE_MAX:
        score += 5
    else:
        notes.append(f"标题 {len(t)} 字，超过 {TITLE_MAX}")

    if re.search(r"[？?！!]", t):
        score += 3
    elif kind not in {"workspace", "temp"}:
        notes.append("建议含 ？ 或 ！ 提升点击率")

    if not any(w in t for w in BANNED_TITLE_WORDS):
        score += 3
    else:
        notes.append("含标题党禁词")

    if "tools-workspace" not in t.lower() and "stock-ai" not in t.lower():
        score += 2
    else:
        notes.append("标题勿用 git 目录名")

    core = t[:15]
    if len(core) >= 4:
        score += 2
    else:
        notes.append("标题过短，信息不足")

    score = min(score, 15)
    from scripts.tools.wechat_mp_sousou_eval import sousou_title_score_adjust

    score, sousou_notes = sousou_title_score_adjust(title, base_score=score)
    notes.extend(sousou_notes)

    return DimensionScore("标题", score, 15, notes)


def _score_opening(body: str) -> DimensionScore:
    notes: list[str] = []
    score = 0
    opening = _opening_block(body)
    if not opening:
        return DimensionScore("开头", 0, 15, ["缺少独立开头段（首段不应仅为分块标题）"])

    if len(opening) >= 40:
        score += 4
    else:
        notes.append("开头过短，建议 40 字以上写清场景或结果")

    if re.search(r"\d|一刻钟|收盘|MySQL|微信|工具工作区", opening):
        score += 4
    else:
        notes.append("开头宜含数字、时间线或具体名词")

    if not _OPENING_FLUFF.search(opening):
        score += 4
    else:
        notes.append("开头像套话，改为具体场景")

    if len(_TRANSITION_AI.findall(opening)) == 0:
        score += 3
    else:
        notes.append("开头勿用 首先/其次/综上")

    return DimensionScore("开头", min(score, 15), 15, notes)


def _count_section_heads(body: str, *, html: str = "") -> int:
    paras = _paragraphs(body)
    n = sum(
        1
        for p in paras
        if p.startswith(">") or re.match(r"^[一二三四五六七八九十]、", p)
    )
    if html:
        n += len(re.findall(r"<blockquote\b", html, re.I))
    return n


def _score_body(body: str, *, kind: str, html: str = "", title: str = "") -> DimensionScore:
    notes: list[str] = []
    score = 0
    paras = _paragraphs(body)
    if not paras:
        return DimensionScore("正文", 0, 25, ["正文为空"])

    section_heads = _count_section_heads(body, html=html)
    if section_heads >= 2:
        score += 6
    elif section_heads == 1:
        score += 3
        notes.append("建议至少 2 个分块标题（> 或 一、）")
    else:
        notes.append("缺少分块标题，移动端难跳读")

    long_paras = [p for p in paras if len(p) > 180 and not p.startswith(">")]
    if not long_paras:
        score += 5
    else:
        notes.append(f"{len(long_paras)} 段过长，建议拆成 3 行以内短段")
        score += 2

    concrete = re.search(
        r"MySQL|微信|Tushare|docker|pytest|草稿|东财|涨跌幅|情绪|选股|工具工作区",
        body,
    )
    if concrete:
        score += 5
    else:
        notes.append("正文缺少可验证的具体名词（库名/工具/流程）")

    if len(paras) >= 4:
        score += 4
    else:
        notes.append("段落偏少，结构偏薄")

    if kind in {"workspace", "temp"} and "工具工作区" in body:
        score += 3
    elif kind in {"market", "top5", "dragons", "sector", "news", "hotspot"} and re.search(
        r"[一二三四五六]、|^\s*>", body, re.M
    ):
        score += 3
    else:
        score += 1

    if re.search(r"^·\s", body, re.M) or section_heads >= 2:
        score += 2

    score = min(score, 25)
    from scripts.tools.wechat_mp_sousou_eval import sousou_body_score_adjust

    score, sousou_notes = sousou_body_score_adjust(
        body, title=title, kind=kind, base_score=score
    )
    notes.extend(sousou_notes)

    return DimensionScore("正文", score, 25, notes)


def _ai_flavor_penalty(body: str) -> tuple[int, list[str]]:
    """返回 0–100，越高 AI 味越重。"""
    penalty = 0
    notes: list[str] = []

    trans = len(_TRANSITION_AI.findall(body))
    if trans:
        penalty += min(trans * 8, 24)
        notes.append(f"机械连接词约 {trans} 处")

    for phrase in BANNED_AI_PHRASES:
        if phrase in body:
            penalty += 8
            notes.append(f"含禁词：{phrase}")

    deg = len(_DEGREE_WORDS.findall(body))
    if deg > 3:
        penalty += 10
        notes.append(f"程度词 {deg} 处")

    sym = len(_SYMMETRIC.findall(body))
    if sym:
        penalty += sym * 6
        notes.append(f"对称句式 {sym} 处")

    if _EMOJI_RE.search(body):
        penalty += 15
        notes.append("含 emoji（本账号禁止）")

    if re.search(r"感谢您的阅读|希望对您有帮助|点赞让我知道|欢迎留言", body):
        penalty += 10
        notes.append("模板化互动结语")

    if not re.search(r"\d", body):
        penalty += 8
        notes.append("全文无数字，缺乏具体感")

    return min(penalty, 100), notes


def _score_de_ai(body: str) -> DimensionScore:
    flavor, notes = _ai_flavor_penalty(body)
    # 30 分制：AI 味 0 → 30 分，AI 味 100 → 0 分
    score = max(0, 30 - int(flavor * 0.3))
    return DimensionScore("去AI", score, 30, notes)


def _score_closing(body: str) -> DimensionScore:
    notes: list[str] = []
    score = 0
    tail = "\n".join(_paragraphs(body)[-2:]) if body else ""

    tail_blob = tail + body[-200:]
    if re.search(r"不构成投资|决策自负|市场有风险", tail_blob):
        score += 5
    elif re.search(r"不代表本号立场|公开报道与网络讨论", tail_blob):
        score += 5
    elif re.search(r"个人工程笔记|工程记录|技术分享", tail_blob):
        score += 5
    else:
        notes.append("建议文末合规一句（行情稿投资免责 / 技术稿工程说明）")

    if not re.search(r"点赞|转发|在看|留言即可", tail):
        score += 3
    else:
        notes.append("弱化模板互动话术")

    if 10 <= len(tail) <= 200:
        score += 2

    return DimensionScore("结尾", min(score, 10), 10, notes)


def check_compliance(body: str, *, title: str = "") -> list[str]:
    from scripts.tools.wechat_mp_public import check_public_compliance

    return check_public_compliance(body, title=title)


def evaluate_article(
    *,
    title: str,
    digest: str,
    body: str,
    kind: str = "unknown",
    content_html: str = "",
) -> EvalReport:
    html_src = content_html or body
    body_plain = strip_html(body)
    if content_html and "<p" in content_html.lower():
        body_plain = re.sub(r"</p>\s*", "\n\n", body_plain, flags=re.I)
        body_plain = re.sub(r"<br\s*/?>", "\n", body_plain, flags=re.I)
        body_plain = re.sub(r"\n{3,}", "\n\n", body_plain).strip()
    dims = [
        _score_title(title, kind=kind),
        _score_opening(body_plain),
        _score_body(body_plain, kind=kind, html=html_src, title=title),
        _score_de_ai(body_plain),
        _score_closing(body_plain),
    ]
    flavor, _ = _ai_flavor_penalty(body_plain)
    total = sum(d.score for d in dims)
    max_total = sum(d.max_score for d in dims)
    compliance = check_compliance(body_plain, title=title)

    if compliance:
        verdict = "不合规（须先修）"
    elif total >= 75 and flavor <= AI_FLAVOR_DRAFT_MAX:
        verdict = "可进草稿箱"
    elif total >= 60:
        verdict = "建议改稿后再推"
    else:
        verdict = "建议重写"

    if len(digest) > DIGEST_MAX:
        dims[0].notes.append(f"摘要 {len(digest)} 字，超过 {DIGEST_MAX}")

    return EvalReport(
        title=title,
        digest=digest,
        kind=kind,
        dimensions=dims,
        compliance_failures=compliance,
        ai_flavor_score=flavor,
        total_score=total,
        max_total=max_total,
        verdict=verdict,
    )


def format_report(report: EvalReport, *, verbose: bool = True) -> str:
    lines = [
        f"【{report.kind}】{report.title}",
        f"【总分】{report.total_score}/{report.max_total} · AI味 {report.ai_flavor_score}/100 · {report.verdict}",
    ]
    if report.compliance_failures:
        lines.append("【合规失败】" + "、".join(report.compliance_failures))
    if verbose:
        for d in report.dimensions:
            note = f" — {'; '.join(d.notes)}" if d.notes else ""
            lines.append(f"  · {d.name}: {d.score}/{d.max_score}{note}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="公众号文章质量评分")
    parser.add_argument(
        "--kind",
        choices=[
            "market",
            "news",
            "sector",
            "hotspot",
            "top5",
            "dragons",
            "workspace",
            "temp",
            "guba",
            "tv_review",
            "all",
        ],
    )
    parser.add_argument("--file", type=str, help="纯文本/Markdown 正文文件")
    parser.add_argument("--title", type=str, default="")
    parser.add_argument("--digest", type=str, default="")
    parser.add_argument("--min-score", type=int, default=0, help="低于此分返回 exit 1")
    parser.add_argument("--max-ai-flavor", type=int, default=100, help="AI味高于此返回 exit 1")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--quiet", action="store_true", help="只输出总分与结论")
    parser.add_argument("--traffic", action="store_true", help="附加阅读量优化清单")
    parser.add_argument(
        "--edition",
        choices=("pre", "midday", "close"),
        default=None,
        help="market 时段（配合 --kind market）",
    )
    args = parser.parse_args()

    reports: list[tuple[EvalReport, dict[str, Any]]] = []

    if args.kind:
        from scripts.tools.wechat_mp_content import DAILY_DRAFT_KINDS, build_article

        kinds = list(DAILY_DRAFT_KINDS) if args.kind == "all" else [args.kind]
        for k in kinds:
            try:
                if k == "news":
                    from scripts.tools.wechat_mp_draft_batch import _peer_market_title

                    art = build_article(k, peer_market_title=_peer_market_title())
                elif k in {"market", "sector", "hotspot"} and args.edition:
                    art = build_article(k, edition=args.edition)
                else:
                    art = build_article(k)
            except Exception as exc:
                print(f"❌ [{k}] 无法构建: {exc}", file=sys.stderr)
                return 1
            html = art.get("content", "")
            rep = evaluate_article(
                title=art["title"],
                digest=art.get("digest", ""),
                body=html,
                content_html=html,
                kind=k,
            )
            reports.append((rep, art))
    elif args.file:
        path = Path(args.file)
        body = path.read_text(encoding="utf-8")
        rep = evaluate_article(
            title=args.title,
            digest=args.digest,
            body=body,
            kind="file",
        )
        reports.append((rep, {"body_text": body, "content": body}))
    else:
        parser.error("请指定 --kind 或 --file")

    ok = True
    for rep, art in reports:
        if args.json:
            print(json.dumps(rep.to_dict(), ensure_ascii=False, indent=2))
        elif args.quiet:
            print(f"{rep.kind}: {rep.total_score}/{rep.max_total} {rep.verdict}")
        else:
            print(format_report(rep))
            if args.traffic:
                from scripts.tools.wechat_mp_traffic_checklist import (
                    format_traffic_report,
                    run_traffic_checklist,
                )

                edition = (
                    args.edition if rep.kind in {"market", "sector", "hotspot"} else None
                )
                traffic = run_traffic_checklist(
                    title=rep.title,
                    digest=rep.digest,
                    body=str(art.get("body_text") or art.get("content") or ""),
                    kind=rep.kind,
                    edition=edition,
                    content_html=str(art.get("content") or ""),
                    recommended_tags=list(art.get("recommended_hashtags") or []),
                )
                print(format_traffic_report(traffic))
            print()

        if rep.total_score < args.min_score or rep.ai_flavor_score > args.max_ai_flavor:
            ok = False
        if rep.compliance_failures:
            ok = False

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
