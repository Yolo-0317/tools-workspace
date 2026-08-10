#!/usr/bin/env python3
"""推稿前质量门禁：eval 打分 + traffic 清单（路线 A 闭环）。"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass, field
from typing import Any

from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.wechat_mp_eval import EvalReport, evaluate_article, format_report, AI_FLAVOR_DRAFT_MAX
from scripts.tools.wechat_mp_traffic_checklist import (
    TrafficChecklistReport,
    format_traffic_report,
    run_traffic_checklist,
)


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name) or default)
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name, "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def quality_gate_min_score() -> int:
    return max(0, min(100, _env_int("WECHAT_MP_QUALITY_MIN_SCORE", 75)))


def quality_gate_max_ai_flavor() -> int:
    return max(0, min(100, _env_int("WECHAT_MP_QUALITY_MAX_AI_FLAVOR", AI_FLAVOR_DRAFT_MAX)))


def quality_gate_enabled() -> bool:
    """evening 批次默认开启；`WECHAT_MP_PUSH_QUALITY_GATE=0` 关闭。"""
    raw = os.getenv("WECHAT_MP_PUSH_QUALITY_GATE", "").strip().lower()
    if raw in {"0", "false", "no", "off"}:
        return False
    if raw in {"1", "true", "yes", "on"}:
        return True
    batch = os.getenv("WECHAT_MP_NEWS_BATCH", "").strip()
    return batch == "evening"


def quality_gate_strict() -> bool:
    """未过门禁是否阻断 upsert（默认阻断）。"""
    return _env_bool("WECHAT_MP_QUALITY_GATE_STRICT", True)


def quality_gate_traffic_block() -> bool:
    """traffic 自动项失败是否算硬失败（默认仅告警）。"""
    return _env_bool("WECHAT_MP_QUALITY_TRAFFIC_BLOCK", False)


@dataclass
class QualityGateResult:
    kind: str
    title: str
    eval_report: EvalReport
    traffic_report: TrafficChecklistReport | None = None
    traffic_failures: list[str] = field(default_factory=list)
    ok: bool = False
    block_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["eval_report"] = self.eval_report.to_dict()
        if self.traffic_report:
            d["traffic_report"] = self.traffic_report.to_dict()
        return d


def assess_article_for_push(
    article: dict[str, Any],
    kind: str,
    *,
    edition: str | None = None,
    min_score: int | None = None,
    max_ai_flavor: int | None = None,
    with_traffic: bool = True,
) -> QualityGateResult:
    """对已构建 article dict 跑 eval + traffic。"""
    min_s = quality_gate_min_score() if min_score is None else min_score
    max_ai = quality_gate_max_ai_flavor() if max_ai_flavor is None else max_ai_flavor
    title = str(article.get("title") or "")
    digest = str(article.get("digest") or "")
    body_text = str(article.get("body_text") or "")
    content_html = str(article.get("content") or "")

    rep = evaluate_article(
        title=title,
        digest=digest,
        body=body_text or content_html,
        kind=kind,
        content_html=content_html,
    )

    traffic: TrafficChecklistReport | None = None
    traffic_failures: list[str] = []
    if with_traffic:
        traffic = run_traffic_checklist(
            title=title,
            digest=digest,
            body=body_text or content_html,
            kind=kind,
            edition=edition if kind in {"market", "sector", "hotspot"} else None,
            content_html=content_html,
            recommended_tags=list(article.get("recommended_hashtags") or []),
        )
        traffic_failures = [
            f"{i.id}:{i.label}" for i in traffic.items if not i.manual and not i.passed
        ]

    ok = True
    reasons: list[str] = []
    if rep.compliance_failures:
        ok = False
        reasons.append("合规：" + "、".join(rep.compliance_failures))
    if rep.total_score < min_s:
        ok = False
        reasons.append(f"总分 {rep.total_score} < {min_s}")
    if rep.ai_flavor_score > max_ai:
        ok = False
        reasons.append(f"AI味 {rep.ai_flavor_score} > {max_ai}")
    if traffic_failures and quality_gate_traffic_block():
        ok = False
        reasons.append("traffic：" + "、".join(traffic_failures[:5]))

    return QualityGateResult(
        kind=kind,
        title=title,
        eval_report=rep,
        traffic_report=traffic,
        traffic_failures=traffic_failures,
        ok=ok,
        block_reason="；".join(reasons),
    )


def format_quality_gate_report(result: QualityGateResult, *, verbose: bool = True) -> str:
    lines = [
        format_report(result.eval_report, verbose=verbose),
    ]
    if result.traffic_report:
        lines.append(format_traffic_report(result.traffic_report))
        if result.traffic_failures and not quality_gate_traffic_block():
            lines.append(
                "【traffic 提示】未过自动项（未阻断推稿）："
                + "、".join(result.traffic_failures[:8])
            )
    status = "通过" if result.ok else f"未通过 — {result.block_reason}"
    lines.insert(0, f"【质量门禁·{result.kind}】{status}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="公众号推稿前质量门禁")
    parser.add_argument(
        "--batch",
        choices=["evening", "weekend"],
        help="评估批次内全部 kinds（会 build_article）",
    )
    parser.add_argument(
        "--kinds",
        nargs="+",
        help="指定 kind 列表（与 --batch 二选一）",
    )
    parser.add_argument("--edition", choices=("pre", "midday", "close"), default="close")
    parser.add_argument("--min-score", type=int, default=None)
    parser.add_argument("--max-ai-flavor", type=int, default=None)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--no-traffic", action="store_true")
    args = parser.parse_args()

    if args.batch:
        from scripts.tools.wechat_mp_draft_batch import (
            SCHEDULE_BATCHES,
            _apply_batch_env,
            resolve_evening_kinds,
        )

        _apply_batch_env(args.batch)
        spec = SCHEDULE_BATCHES[args.batch]
        kinds = tuple(resolve_evening_kinds()) if args.batch == "evening" else tuple(spec["kinds"])
        edition = spec.get("edition") or args.edition
    elif args.kinds:
        kinds = tuple(args.kinds)
        edition = args.edition
        os.environ.setdefault("WECHAT_MP_NEWS_BATCH", "evening")
    else:
        parser.error("请指定 --batch 或 --kinds")

    if args.min_score is not None:
        os.environ["WECHAT_MP_QUALITY_MIN_SCORE"] = str(args.min_score)
    if args.max_ai_flavor is not None:
        os.environ["WECHAT_MP_QUALITY_MAX_AI_FLAVOR"] = str(args.max_ai_flavor)
    if args.no_traffic:
        os.environ["WECHAT_MP_QUALITY_TRAFFIC_BLOCK"] = "0"

    results: list[QualityGateResult] = []
    for kind in kinds:
        from scripts.tools.wechat_mp_content import build_article

        try:
            if kind == "news":
                from scripts.tools.wechat_mp_draft_batch import _peer_market_title

                article = build_article(kind, peer_market_title=_peer_market_title())
            elif kind in {"market", "sector", "hotspot"}:
                article = build_article(kind, edition=edition)
            else:
                article = build_article(kind)
        except Exception as exc:  # noqa: BLE001
            print(f"FAIL [{kind}] 构建失败: {exc}", file=sys.stderr)
            return 1
        result = assess_article_for_push(
            article,
            kind,
            edition=edition,
            with_traffic=not args.no_traffic,
        )
        results.append(result)
        if args.json:
            print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        else:
            print(format_quality_gate_report(result))
            print()

    return 0 if all(r.ok for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
