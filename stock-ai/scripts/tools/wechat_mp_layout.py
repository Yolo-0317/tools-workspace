"""公众号正文排版预设（WECHAT_MP_LAYOUT）。"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class MpLayoutPreset:
    """间距单位 px；tight 用于插图紧接下一节标题。"""

    key: str
    label: str
    summary: str
    section_margin: str  # 普通节标题 margin
    section_margin_tight_top: str  # 紧跟插图后的节标题 margin-top
    section_first_margin_top: str
    para_margin: str
    news_margin: str
    news_title_margin: str
    news_summary_margin: str
    news_ai_margin: str
    news_title_size: str
    news_body_size: str
    news_line_height: str
    list_margin: str
    figure_margin: str
    figure_caption_margin: str
    figure_radius: str


PRESETS: dict[str, MpLayoutPreset] = {
    "pulse": MpLayoutPreset(
        key="pulse",
        label="专栏紧凑",
        summary="财经长文常用：左线小标题、段距紧、图贴上文、图后标题留白极小（默认）",
        section_margin="10px 0 2px",
        section_margin_tight_top="2px 0 2px",
        section_first_margin_top="8px",
        para_margin="0 0 5px",
        news_margin="0 0 2px",
        news_title_margin="12px 0 6px",
        news_summary_margin="0 0 8px",
        news_ai_margin="0 0 16px",
        news_title_size="18px",
        news_body_size="15px",
        news_line_height="1.78",
        list_margin="0 0 5px",
        figure_margin="2px 0 0",
        figure_caption_margin="2px 0 0",
        figure_radius="4px",
    ),
    "brief": MpLayoutPreset(
        key="brief",
        label="快讯简报",
        summary="信息密度最高：节标题仅加粗无左边框、段距最小、图注一行",
        section_margin="10px 0 2px",
        section_margin_tight_top="2px 0 2px",
        section_first_margin_top="0",
        para_margin="0 0 4px",
        news_margin="0 0 1px",
        news_title_margin="10px 0 5px",
        news_summary_margin="0 0 6px",
        news_ai_margin="0 0 12px",
        news_title_size="17px",
        news_body_size="15px",
        news_line_height="1.72",
        list_margin="0 0 4px",
        figure_margin="2px 0 0",
        figure_caption_margin="1px 0 0",
        figure_radius="2px",
    ),
    "chapter": MpLayoutPreset(
        key="chapter",
        label="章节导图",
        summary="节标题下先大图再正文（需插图插在标题后，见 inject_market_figures_chapter）",
        section_margin="14px 0 5px",
        section_margin_tight_top="6px 0 5px",
        section_first_margin_top="6px",
        para_margin="0 0 8px",
        news_margin="0 0 3px",
        news_title_margin="14px 0 8px",
        news_summary_margin="0 0 10px",
        news_ai_margin="0 0 18px",
        news_title_size="18px",
        news_body_size="15px",
        news_line_height="1.8",
        list_margin="0 0 8px",
        figure_margin="2px 0 8px",
        figure_caption_margin="4px 0 0",
        figure_radius="6px",
    ),
    "report": MpLayoutPreset(
        key="report",
        label="晨报体",
        summary="节标题左线略松、段距适中，要闻区适合列表（后续可接列表样式）",
        section_margin="16px 0 5px",
        section_margin_tight_top="6px 0 5px",
        section_first_margin_top="8px",
        para_margin="0 0 8px",
        news_margin="0 0 3px",
        news_title_margin="14px 0 8px",
        news_summary_margin="0 0 10px",
        news_ai_margin="0 0 18px",
        news_title_size="18px",
        news_body_size="15px",
        news_line_height="1.8",
        list_margin="0 0 8px",
        figure_margin="6px 0 4px",
        figure_caption_margin="4px 0 0",
        figure_radius="4px",
    ),
}


def active_layout() -> MpLayoutPreset:
    raw = os.environ.get("WECHAT_MP_LAYOUT", "pulse").strip().lower()
    return PRESETS.get(raw) or PRESETS["pulse"]


def list_preset_summaries() -> list[tuple[str, str, str]]:
    return [(p.key, p.label, p.summary) for p in PRESETS.values()]
