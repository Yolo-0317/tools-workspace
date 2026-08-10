#!/usr/bin/env python3
"""公众号文末 stock-ai / home-hub 引流（合规：工具说明，非荐股）。"""

from __future__ import annotations

import os
from typing import Literal
from urllib.parse import urljoin

DraftKind = Literal["sector", "market", "news", "top5", "dragons", "workspace", "temp", "guba"]

_DEFAULT_HUB = "https://hub.yoloworld.site:8883"

# 公开页：/news 为 meta.public；其余需登录，CTA 文案说明「登录后」
_KIND_PATHS: dict[str, str] = {
    "news": "/news",
    "selection": "/selection",
    "emotion": "/emotion",
    "advisor": "/advisor",
    "monitor": "/monitor",
}

# 稿型 → hub 路径 + 一句说明
_KIND_CTA: dict[str, tuple[str, str]] = {
    "news": (
        "/news",
        "同名快讯与筛选在工具看板可对照（浏览器打开，需登录）：",
    ),
    "dragons": (
        "/emotion",
        "连板梯队与情绪日检卡可在看板对照（需登录）：",
    ),
    "sector": (
        "/selection",
        "行业样本与选股池可在看板展开（需登录）：",
    ),
    "market": (
        "/advisor",
        "收盘后投顾看板含盘面与持仓快照（需登录）：",
    ),
}


def stock_ai_cta_enabled() -> bool:
    raw = os.getenv("WECHAT_MP_STOCK_AI_CTA", "").strip().lower()
    if raw in ("1", "true", "yes", "on"):
        return True
    if raw in ("0", "false", "no", "off"):
        return False
    try:
        from scripts.tools.wechat_mp_growth import load_growth_focus

        return load_growth_focus().stock_ai_cta_enabled
    except Exception:
        return False


def hub_base_url() -> str:
    base = (
        os.getenv("WECHAT_MP_STOCK_AI_HUB_URL", "").strip()
        or os.getenv("WECHAT_MP_SOURCE_URL", "").strip().rsplit("/", 1)[0]
        or _DEFAULT_HUB
    )
    if not base.startswith(("http://", "https://")):
        return _DEFAULT_HUB
    return base.rstrip("/")


def hub_url_for_kind(kind: str | None) -> str:
    k = (kind or "").strip().lower()
    path = _KIND_CTA.get(k, ("/advisor", ""))[0]
    return urljoin(hub_base_url() + "/", path.lstrip("/"))


def stock_ai_cta_paragraph(*, kind: str | None) -> str:
    k = (kind or "").strip().lower()
    if k not in _KIND_CTA:
        return ""
    path, lead = _KIND_CTA[k]
    url = urljoin(hub_base_url() + "/", path.lstrip("/"))
    return f"{lead}\n{url}\n（个人工具台，非投顾服务；不构成投资建议。）"


def attach_stock_ai_cta(article: dict, *, kind: str | None = None) -> dict:
    """在免责前插入一行 hub 引流（growth 模型）。"""
    if not stock_ai_cta_enabled():
        return article
    k = kind or str(article.get("kind") or "")
    kinds_raw = os.getenv("WECHAT_MP_STOCK_AI_CTA_KINDS", "").strip()
    if kinds_raw:
        allowed = {x.strip().lower() for x in kinds_raw.split(",") if x.strip()}
    else:
        try:
            from scripts.tools.wechat_mp_growth import load_growth_focus

            allowed = set(load_growth_focus().stock_ai_cta_kinds)
        except Exception:
            allowed = {"news", "dragons"}
    if k.lower() not in allowed:
        return article
    para = stock_ai_cta_paragraph(kind=k)
    if not para:
        return article
    body = str(article.get("body_text") or "")
    marker = "本文为作者个人复盘笔记"
    if para.strip() in body:
        return article
    if marker in body:
        article = {**article, "body_text": body.replace(marker, f"{para}\n\n{marker}", 1)}
    else:
        article = {**article, "body_text": f"{body.rstrip()}\n\n{para}\n"}
    return article


def read_source_url_for_kind(kind: str | None) -> str:
    """news 可开「阅读原文」→ hub /news（公开页）。"""
    if not stock_ai_cta_enabled():
        return ""
    k = (kind or "").strip().lower()
    if k != "news":
        return ""
    if os.getenv("WECHAT_MP_STOCK_AI_NEWS_SOURCE", "1").strip().lower() in ("0", "false", "no"):
        return ""
    return hub_url_for_kind("news")
