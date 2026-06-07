#!/usr/bin/env python3
"""公众号草稿推送结果：微信 + 飞书通知。"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Asia/Shanghai")

BATCH_LABELS = {
    "evening": "交易日 19:00",
    "weekend": "休市日 18:20 周末要闻(热股Top10×快讯)",
    "weekend_skip": "周六休市(跳过)",
}


@dataclass
class DraftPushResult:
    kind: str
    title: str
    action: str
    ok: bool
    error: str = ""
    hashtags: tuple[str, ...] = ()


def _notify_enabled() -> bool:
    raw = os.getenv("WECHAT_MP_NOTIFY", "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


def _notify_wechat_enabled() -> bool:
    raw = os.getenv("WECHAT_MP_NOTIFY_WECHAT", "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


def _notify_feishu_enabled() -> bool:
    raw = os.getenv("WECHAT_MP_NOTIFY_FEISHU", "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


def format_batch_message(
    batch: str,
    results: list[DraftPushResult],
    *,
    failed_kinds: list[str] | None = None,
) -> str:
    label = BATCH_LABELS.get(batch, batch)
    now = datetime.now(TZ).strftime("%Y-%m-%d %H:%M")
    lines = [f"公众号草稿 · {label}", f"时间 {now}", ""]
    ok_items = [r for r in results if r.ok]
    if ok_items:
        lines.append("已推送草稿箱：")
        for r in ok_items:
            verb = "更新" if r.action == "updated" else "新建"
            line = f"· [{r.kind}] {verb} · {r.title}"
            if r.hashtags:
                tags = " ".join(f"#{t}" for t in r.hashtags)
                line += f"\n  #话题: {tags}"
            lines.append(line)
    else:
        lines.append("本批次无成功推送。")
    if failed_kinds:
        lines.append("")
        lines.append("跳过/失败：" + "、".join(failed_kinds))
    errs = [r for r in results if not r.ok and r.error]
    if errs:
        lines.append("")
        for r in errs:
            lines.append(f"· [{r.kind}] {r.error[:120]}")
    lines.append("")
    lines.append("请在 mp.weixin.qq.com 草稿箱审阅后发布。")
    if ok_items and any(r.hashtags for r in ok_items):
        lines.append("发布后：勾选原创(财经) → 文章右侧 # 粘贴各行推荐话题。")
    return "\n".join(lines)


def send_batch_notifications(
    batch: str,
    results: list[DraftPushResult],
    *,
    failed_kinds: list[str] | None = None,
    is_error: bool = False,
) -> tuple[bool, bool]:
    """返回 (微信是否成功, 飞书是否成功)。"""
    if not _notify_enabled():
        return False, False
    if not any(r.ok for r in results) and not is_error:
        return False, False

    text = format_batch_message(batch, results, failed_kinds=failed_kinds)
    prefix = f"【公众号·{BATCH_LABELS.get(batch, batch)}】"
    if is_error or not any(r.ok for r in results):
        prefix = f"【公众号·失败·{BATCH_LABELS.get(batch, batch)}】"

    wechat_ok = False
    feishu_ok = False

    if _notify_wechat_enabled():
        try:
            from scripts.tools.wechat_acp_push_text import send_wechat_acp_text

            send_wechat_acp_text(text)
            wechat_ok = True
        except Exception as exc:  # noqa: BLE001
            print(f"⚠️ 微信通知失败: {exc}", file=sys.stderr)

    if _notify_feishu_enabled():
        try:
            from stock_ai.notify import send_to_lark

            feishu_ok = send_to_lark(
                text,
                is_error=is_error or not any(r.ok for r in results),
                prefix=prefix,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"⚠️ 飞书通知失败: {exc}", file=sys.stderr)

    return wechat_ok, feishu_ok
