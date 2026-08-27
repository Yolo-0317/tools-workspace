"""公众号同题报道取图与原创补图交接协议。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from scripts.tools import wechat_mp_discussion_figures as figures_mod

REQUEST_FILENAME = "codex-image-request.json"
READY_FILENAME = "codex-images-ready.json"
SOURCES_FILENAME = "image-sources.json"
SAFETY_RULES = (
    "原创新闻插画，不得伪造新闻现场",
    "不得添加可识别真实人物、机构标识、伤亡数字或未经证实的细节",
    "画面中不得出现文字、二维码、水印或品牌标识",
)


@dataclass(frozen=True)
class PreparedTopicImages:
    image_paths: tuple[Path, ...]
    sources_path: Path


class CodexImageGenerationRequired(RuntimeError):
    """报道图不足，需要按请求文件补齐原创图（保留旧名称兼容调用方）。"""

    def __init__(self, *, request_path: Path, missing_count: int) -> None:
        self.request_path = Path(request_path)
        self.missing_count = int(missing_count)
        super().__init__(
            f"仍缺 {self.missing_count} 张图片；请按 {self.request_path} 使用已登录的 "
            "ChatGPT 网页生成，保存到各 output_path 后重试；失败时停止并提示用户"
        )


def _topic_payload(
    topic: str,
    *,
    research_urls: Iterable[str] = (),
    slug: str = "",
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "title_zh": topic.strip(),
        "trend_title": topic.strip(),
        "from_trend": True,
        "research_urls": [
            str(url).strip()
            for url in research_urls
            if str(url).strip().startswith(("http://", "https://"))
        ],
    }
    if slug.strip():
        payload["cover_slug"] = slug.strip()
    return payload


def _out_dir(topic: dict[str, Any]) -> Path:
    return figures_mod.INLINE_DISCUSSION_ROOT / figures_mod._slug(topic)


def _valid_image(path: Path) -> bool:
    return (
        path.is_file()
        and path.stat().st_size >= 8000
        and path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
        and figures_mod._figure_dimensions_ok(path)
    )


def _report_assets(
    figures: Iterable[dict[str, str]],
    *,
    out_dir: Path,
) -> tuple[list[Path], dict[str, dict[str, str]]]:
    meta = figures_mod._load_figure_sources(out_dir)
    paths: list[Path] = []
    sources: dict[str, dict[str, str]] = {}
    for figure in figures:
        name = Path(str(figure.get("rel") or "").replace("\\", "/")).name
        path = out_dir / name
        source = meta.get(name) or {}
        page_url = str(source.get("page_url") or "").strip()
        if (
            not name
            or not _valid_image(path)
            or not page_url.startswith(("http://", "https://"))
        ):
            continue
        paths.append(path)
        sources[name] = {
            "source_type": "report",
            "page_url": page_url,
            "page_title": str(source.get("page_title") or "").strip(),
        }
    return paths, sources


def _manual_paths(out_dir: Path, *, limit: int) -> list[Path]:
    return [path for path in sorted(out_dir.glob("manual-*.*")) if _valid_image(path)][
        :limit
    ]


def _slot_prompt(*, article_type: str, topic: str, ordinal: int, cover: bool) -> str:
    if cover:
        composition = (
            "微信公众号长图文封面，2.35:1 横向构图，"
            "主体明确，留出自然视觉呼吸空间"
        )
    elif article_type == "newspic":
        composition = (
            f"微信公众号贴图第 {ordinal} 幅，3:4 竖向新闻插画，"
            "补充一个新的事件视角"
        )
    else:
        composition = (
            f"微信公众号长图文正文第 {ordinal} 幅，4:3 新闻插画，"
            "与前后图片不重复"
        )
    return (
        f"围绕“{topic}”创作{composition}。使用克制、写实但明确为插画的视觉语言；"
        "只呈现可泛化的事件主体、环境或处置线索，不还原未经核实的真实现场。"
    )


def _write_request(
    *,
    out_dir: Path,
    article_type: str,
    topic: str,
    target_count: int,
    report_image_count: int,
    slots: list[dict[str, str]],
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / REQUEST_FILENAME
    normalized_slots: list[dict[str, str]] = []
    has_cover = any(str(slot.get("slot") or "") == "cover" for slot in slots)
    for slot in slots:
        normalized = dict(slot)
        slot_id = str(normalized.pop("slot", "") or "").strip()
        normalized["slot_id"] = slot_id
        if has_cover and slot_id.startswith("body-"):
            normalized["reference_slot_id"] = "cover"
        normalized_slots.append(normalized)
    payload = {
        "schema_version": 2,
        "generator": "chatgpt_web",
        "failure_policy": "stop_and_prompt",
        "article_type": article_type,
        "topic": topic,
        "target_count": target_count,
        "report_image_count": report_image_count,
        "missing_count": len(slots),
        "safety_rules": list(SAFETY_RULES),
        "slots": normalized_slots,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _clear_request(out_dir: Path) -> None:
    (out_dir / REQUEST_FILENAME).unlink(missing_ok=True)


def _completed_request(out_dir: Path, *, article_type: str) -> bool:
    request_path = out_dir / REQUEST_FILENAME
    try:
        payload = json.loads(request_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if payload.get("article_type") != article_type:
        return False
    slots = payload.get("slots")
    if not isinstance(slots, list) or not slots:
        return False
    root = out_dir.resolve()
    for slot in slots:
        if not isinstance(slot, dict):
            return False
        output_path = Path(str(slot.get("output_path") or ""))
        if output_path.parent.resolve() != root or not _valid_image(output_path):
            return False
    return True


def _mark_ready(out_dir: Path, *, article_type: str, topic: str) -> None:
    (out_dir / READY_FILENAME).write_text(
        json.dumps(
            {"schema_version": 1, "article_type": article_type, "topic": topic},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    _clear_request(out_dir)


def _clear_ready(out_dir: Path) -> None:
    (out_dir / READY_FILENAME).unlink(missing_ok=True)


def _cached_report_figures(out_dir: Path, *, slug: str) -> list[dict[str, str]]:
    meta = figures_mod._load_figure_sources(out_dir)
    return [
        {
            "rel": f"discussion/{slug}/{path.name}",
            "cap": "图源：公开报道（引用）",
        }
        for path in sorted(out_dir.glob("still-*.*"))
        if _valid_image(path)
        and str((meta.get(path.name) or {}).get("page_url") or "").startswith(
            ("http://", "https://")
        )
    ]


def prepare_newspic_topic_images(
    *,
    topic: str,
    research_urls: Iterable[str] = (),
    target_count: int = 6,
    slug: str = "",
) -> PreparedTopicImages:
    """优先抓同题报道图；不足时为 Codex 写原创贴图请求。"""
    normalized_topic = topic.strip()
    if not normalized_topic:
        raise ValueError("贴图自动取图须提供非空 topic")
    if not 1 <= target_count <= 9:
        raise ValueError("贴图目标图片数须为 1-9")
    topic_dict = _topic_payload(
        normalized_topic,
        research_urls=research_urls,
        slug=slug,
    )
    out_dir = _out_dir(topic_dict)
    resumed = _completed_request(out_dir, article_type="newspic")
    if resumed:
        _mark_ready(out_dir, article_type="newspic", topic=normalized_topic)
        figures = _cached_report_figures(
            out_dir,
            slug=figures_mod._slug(topic_dict),
        )
    else:
        figures = figures_mod.ensure_discussion_figures(
            topic_dict,
            max_images=target_count,
        )
    report_paths, sources = _report_assets(figures, out_dir=out_dir)
    manual_paths = _manual_paths(
        out_dir,
        limit=max(0, target_count - len(report_paths)),
    )
    image_paths = (report_paths + manual_paths)[:target_count]
    for path in manual_paths:
        sources[path.name] = {
            "source_type": "original",
            "fallback_reason": "同题公开报道图不足，由 ChatGPT 网页原创补位",
        }
    if len(image_paths) < target_count:
        _clear_ready(out_dir)
        missing = target_count - len(image_paths)
        slots: list[dict[str, str]] = []
        next_index = 1
        existing_names = {path.name for path in manual_paths}
        while len(slots) < missing:
            name = f"manual-{next_index:02d}.jpg"
            next_index += 1
            if name in existing_names:
                continue
            slots.append(
                {
                    "slot": f"scene-{len(image_paths) + len(slots) + 1:02d}",
                    "output_path": str((out_dir / name).resolve()),
                    "prompt": _slot_prompt(
                        article_type="newspic",
                        topic=normalized_topic,
                        ordinal=len(image_paths) + len(slots) + 1,
                        cover=False,
                    ),
                }
            )
        request_path = _write_request(
            out_dir=out_dir,
            article_type="newspic",
            topic=normalized_topic,
            target_count=target_count,
            report_image_count=len(report_paths),
            slots=slots,
        )
        raise CodexImageGenerationRequired(
            request_path=request_path,
            missing_count=missing,
        )
    _mark_ready(out_dir, article_type="newspic", topic=normalized_topic)
    sources_path = out_dir / SOURCES_FILENAME
    sources_path.write_text(
        json.dumps(sources, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return PreparedTopicImages(tuple(image_paths), sources_path)


def prepare_hotspot_topic_images(
    topic: dict[str, Any],
    *,
    body_count: int = 3,
) -> None:
    """为长图文准备一张封面和正文图；只把缺口交给 Codex。"""
    if body_count < 0:
        raise ValueError("长图文正文图片数不能为负数")
    normalized_topic = str(
        topic.get("trend_title") or topic.get("title_zh") or ""
    ).strip()
    if not normalized_topic:
        raise ValueError("长图文自动取图须提供非空 topic")
    out_dir = _out_dir(topic)
    resumed = _completed_request(out_dir, article_type="hotspot")
    if resumed:
        _mark_ready(out_dir, article_type="hotspot", topic=normalized_topic)
        report_figures = _cached_report_figures(
            out_dir,
            slug=figures_mod._slug(topic),
        )
    else:
        report_figures = figures_mod.ensure_discussion_figures(
            topic,
            max_images=max(4, body_count + 2),
        )
    report_paths, _sources = _report_assets(report_figures, out_dir=out_dir)
    cover_ready = _valid_image(out_dir / "cover.jpg") or bool(report_paths)
    body_figures = figures_mod.ensure_discussion_body_figures(
        topic,
        max_images=body_count,
    )
    valid_body_names = {
        Path(str(figure.get("rel") or "").replace("\\", "/")).name
        for figure in body_figures
        if _valid_image(
            out_dir
            / Path(str(figure.get("rel") or "").replace("\\", "/")).name
        )
    }
    missing_body = max(0, body_count - len(valid_body_names))
    slots: list[dict[str, str]] = []
    if not cover_ready:
        slots.append(
            {
                "slot": "cover",
                "output_path": str((out_dir / "cover.jpg").resolve()),
                "prompt": _slot_prompt(
                    article_type="hotspot",
                    topic=normalized_topic,
                    ordinal=0,
                    cover=True,
                ),
            }
        )
    next_index = 1
    while missing_body > 0:
        name = f"manual-{next_index:02d}.jpg"
        next_index += 1
        if name in valid_body_names:
            continue
        ordinal = body_count - missing_body + 1
        slots.append(
            {
                "slot": f"body-{ordinal:02d}",
                "output_path": str((out_dir / name).resolve()),
                "prompt": _slot_prompt(
                    article_type="hotspot",
                    topic=normalized_topic,
                    ordinal=ordinal,
                    cover=False,
                ),
            }
        )
        missing_body -= 1
    if slots:
        _clear_ready(out_dir)
        request_path = _write_request(
            out_dir=out_dir,
            article_type="hotspot",
            topic=normalized_topic,
            target_count=body_count + 1,
            report_image_count=len(report_paths),
            slots=slots,
        )
        raise CodexImageGenerationRequired(
            request_path=request_path,
            missing_count=len(slots),
        )
    _mark_ready(out_dir, article_type="hotspot", topic=normalized_topic)
