#!/usr/bin/env python3
"""影视试跑正文剧照：豆瓣剧照 + 评分文字 + 分节注入。"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.wechat_mp_figures import (
    FIGURE_LINE_RE,
    _figure_marker_lines,
    _find_section_line_fuzzy,
    _section_bare,
)

ROOT = Path(__file__).resolve().parents[2]
INLINE_TV_ROOT = ROOT / "assets" / "wechat_mp" / "inline-tv"

TV_ATTRIBUTION = "（配图：豆瓣条目剧照，剧评引用；评分数据为公开页面整理。）"

CURATED_TV_STILLS: dict[str, dict[str, Any]] = {
    "euphoria": {
        "source": "douban",
        "douban_subject_id": "34874603",
        "files": {
            "douban-still-01.jpg": "2560512988",
            "douban-still-02.jpg": "2560326143",
            "douban-still-03.jpg": "2560512989",
        },
        "slots": [
            ("douban-still-01.jpg", "after", "about", ""),
            ("douban-still-02.jpg", "after", "merits", ""),
            ("douban-still-03.jpg", "after", "audience", ""),
        ],
    },
    "beef": {
        "source": "douban",
        "douban_subject_id": "35413042",
        "files": {
            "douban-still-01.jpg": "2890856178",
            "douban-still-02.jpg": "2890495381",
            "douban-still-03.jpg": "2890862607",
        },
        "slots": [
            ("douban-still-01.jpg", "after", "about", ""),
            ("douban-still-02.jpg", "after", "merits", ""),
            ("douban-still-03.jpg", "after", "audience", ""),
        ],
    },
    "avatar-last-airbender": {
        "source": "tmdb",
        "tmdb_id": 82452,
        "figure_source_caption": "图源：TMDB 宣传物料（剧评引用）",
        "files": {
            "still-01.jpg": "lzZpWEaqzP0qVA5nkCc5ASbNcSy.jpg",
            "still-02.jpg": "xUB3xFMgsHgPmdWnUWkHTJ03vHa.jpg",
            "still-03.jpg": "imlTCObfzISogbvcwB1dokoXAIc.jpg",
            "still-04.jpg": "u62XtaV8Iski2CgAUM8Yp0ZgKxD.jpg",
            "still-05.jpg": "syc4jp5vlEBlI4QX3RSTUk52EUN.jpg",
            "still-06.jpg": "VRFzLzh8jI6AbvOZUa7WUlwU4c.jpg",
        },
        "slots": [
            ("still-01.jpg", "after", "about", ""),
            ("still-02.jpg", "after_anchor", "第2集 A Fight, Once Begun", ""),
            ("still-03.jpg", "after_anchor", "第3集 City of Walls and Secrets", ""),
            ("still-04.jpg", "after_anchor", "Toph", ""),
            ("still-05.jpg", "after_anchor", "第7集 Something Broken", ""),
            ("still-06.jpg", "after_anchor", "一次性迷你三部曲", ""),
        ],
    },
    "teach-you-a-lesson": {
        "source": "tmdb",
        "tmdb_id": 276161,
        "douban_subject_id": "",
        "figure_source_caption": "图源：TMDB 宣传物料 + 剧评场景卡（引用）",
        "slots": [
            (
                "still-01.jpg",
                "after_anchor",
                "第1集（议员儿子案）",
                "楼顶跳下后走廊死寂，罗华振第一次硬介入",
            ),
            (
                "still-07.jpg",
                "after_anchor",
                "第1集（议员儿子案）",
                "议员权力被扒掉，霸凌者从神坛跌落",
            ),
            (
                "still-02.jpg",
                "after_anchor",
                "教权保护局",
                "政府授权的非常规校园督导组挂牌",
            ),
            (
                "still-08.jpg",
                "after_anchor",
                "金武烈演罗华振",
                "武力督察与部长崔康石的理想拉扯",
            ),
            (
                "still-03.jpg",
                "after_anchor",
                "第2集（汽车科帮派案）",
                "补习班挤掉正常上课，帮派混入汽车科",
            ),
            (
                "still-10.jpg",
                "after_anchor",
                "第3集（黑道学生案）",
                "签字与越界之间的停顿，手段谁来收尾",
            ),
            (
                "still-04.jpg",
                "after_anchor",
                "第4集（朴贤雄案）",
                "千相烈操控成绩，校园成政治利益场",
            ),
            (
                "still-09.jpg",
                "after_anchor",
                "第5集（恐龙家长案）",
                "罗华振用电话轰炸反向治胡搅蛮缠",
            ),
            (
                "still-05.jpg",
                "after_anchor",
                "以暴制暴",
                "爽感来自秩序被扳回，不安也来自此",
            ),
            (
                "still-06.jpg",
                "after_anchor",
                "拿不准就开前两集",
                "楼顶与教室两场，定要不要继续追",
            ),
        ],
    },
    "spider-man-brand-new-day": {
        "source": "tmdb_movie",
        "tmdb_id": 969681,
        "figure_source_caption": "图源：TMDB 宣传剧照（剧评引用）",
        "files": {
            "still-01.jpg": "vjMvFSmGUxEtqVdaZgvFee9XkZl.jpg",
            "still-02.jpg": "sYsaVy047cfGTLMfcRihee3ShnM.jpg",
            "still-03.jpg": "5glivQffWJkRJttJ5g5LW14kmeC.jpg",
            "still-04.jpg": "still-04.jpg",
        },
        "slots": [
            ("still-01.jpg", "after_anchor", "制服还得", ""),
            ("still-02.jpg", "after_anchor", "送外卖那段", ""),
            ("still-03.jpg", "after_anchor", "补战衣", ""),
            ("still-04.jpg", "after_anchor", "台灯底下", ""),
        ],
    },
    "michael-jackson-the-verdict": {
        "source": "local",
        "tmdb_id": 323111,
        "poster_tmdb": "8R40yI5AJ931Hd3P4Yf8pdFgwJ1.jpg",
        "figure_source_caption": "图源：纪录片预告片帧（剧评引用）",
        "x_cards": [
            {
                "file": "twitter-01.jpg",
                "display_name": "MJ Fan",
                "handle": "@fan · X",
                "body": (
                    "That Michael Jackson documentary on Netflix is disgusting. "
                    "They're still trying to smear a man who was cleared multiple times, "
                    "even after his death, just to make money off his name."
                ),
                "meta": "Public posts · Jun 2026",
            },
            {
                "file": "twitter-02.jpg",
                "display_name": "迈克尔·杰克逊粉丝",
                "handle": "@网友 · X",
                "body": (
                    "身为迈克尔·杰克逊粉丝，看了很受伤。平台在司法无罪定论之外又用纪录片挖坟，"
                    "我直接用退订表达态度。"
                ),
                "meta": "中文社媒整理 · 2026-06",
            },
        ],
        "slots": [
            (
                "poster.jpg",
                "after_anchor",
                "窗外已经泛白",
                "官方竖版海报",
                "图源：Netflix 官方海报（剧评引用）",
            ),
            (
                "twitter-01.jpg",
                "after_anchor",
                "才华绝无仅有",
                "英文圈「smear / disgusting」代表帖",
                "图源：X 平台公开讨论截图整理（剧评引用）",
            ),
            (
                "twitter-02.jpg",
                "after_anchor",
                "二次消费、二次审判",
                "中文粉丝退订抵制声",
                "图源：X 平台公开讨论截图整理（剧评引用）",
            ),
            (
                "still-01.jpg",
                "after_anchor",
                "6月3日《迈克尔·杰克逊：审判》",
                "Neverland 航拍搜查镜头",
            ),
            (
                "still-02.jpg",
                "after_anchor",
                "传记片《Michael》",
                "传记片热映同期上线纪录片",
            ),
            (
                "still-03.jpg",
                "after_anchor",
                "第1集（开场炸弹）",
                "第一集末尾信息把审判拉回公众视野",
            ),
            (
                "still-04.jpg",
                "after_anchor",
                "第2集（辩方叙事）",
                "辩方如何把「合理怀疑」讲成完整故事",
            ),
            (
                "still-05.jpg",
                "after_anchor",
                "第3集（宣判之后）",
                "无罪宣判之后争议为何没结束",
            ),
            (
                "still-06.jpg",
                "after_anchor",
                "撑到第一集末尾",
                "第一集末尾那场戏，定你要不要追完",
            ),
        ],
    },
}

TV_FIGURE_STYLE = "max-h=420;fit=contain;mb=22"

# 分节语义 → 标题模糊匹配（兼容旧稿说明书式标题）
TV_SECTION_ROLES: dict[str, list[str]] = {
    "conclusion": ["先说结论", "直说", "结论", "撂结论", "值不值", "先聊清楚", "先把话说", "还值得", "上线", "热搜", "吵翻", "全球", "连夜", "发虚", "刷完", "痛快"],
    "about": ["它是什么", "讲啥", "讲什么", "什么剧", "怎么回事", "搞懂", "背景", "干嘛", "没看过", "补课", "一部", "在 HBO", "在 Netflix", "架空", "教权", "揍人", "老师", "失了势", "网漫", "保护局"],
    "merits": ["为什么值得看", "好看在哪", "戳我", "几个点", "为啥", "值得追", "真正", "亮点", "耐嚼", "停下来", "打戏", "三处", "分集", "一案", "速写", "前面几集", "几乎没废场"],
    "episode_guide": ["分集速写", "分集", "按集", "各有场面", "各有侧重", "几乎没废场", "第1集", "第2集", "第3集"],
    "audience": ["适合谁", "劝退", "入坑", "跳过", "谁该", "不适合", "略过", "爱死", "会追", "谨慎", "敏感", "熬夜", "糟心", "趁早", "这口的", "拍板", "指望"],
    "try_it": ["怎么判断", "试一集", "拿不准", "犹豫", "撑过", "20 分钟", "验证", "试两集", "前两集", "楼顶", "定去留", "结尾那场"],
}

_BOLD_NUM_RE = re.compile(r"^\*\*(\d+)[\.、:]?\s*(.+?)\*\*$")
_BOLD_LINE_RE = re.compile(r"^\*\*(.+?)\*\*$")
_STILL_PLACEHOLDER_RE = re.compile(r"^\[剧照\s*\d+[^\]]*\]\s*$")

_STIFF_SECTION_PREFIXES = (
    "简单交代",
    "直说",
    "先说",
    "戳我的就",
    "戳我的",
    "没看过",
    "没背景",
    "一句话",
    "背景介绍",
    "科普",
    "简单说一下",
    "交代一下",
    "总结一下",
    "开个场",
)


def resolve_tv_inline_path(filename: str) -> Path:
    raw = (filename or "").strip().replace("\\", "/")
    parts = [p for p in Path(raw).parts if p and p not in {".", ".."}]
    if not parts:
        raise FileNotFoundError(f"无效影视插图路径: {filename}")
    if parts[0] == "tv":
        parts = parts[1:]
    path = INLINE_TV_ROOT.joinpath(*parts)
    if not path.is_file():
        raise FileNotFoundError(f"影视正文插图不存在: {path}")
    return path


def _slug(topic: dict[str, Any]) -> str:
    slug = str(topic.get("cover_slug") or "").strip().lower()
    en = str(topic.get("title_en") or "").strip().lower()
    if slug == "euphoria" or en == "euphoria":
        return "euphoria"
    if slug == "beef" or en == "beef":
        return "beef"
    if slug in {"teach-you-a-lesson", "teach_you_a_lesson"} or en in {
        "teach you a lesson",
        "get schooled",
    }:
        return "teach-you-a-lesson"
    if slug in {"michael-jackson-the-verdict", "michael_jackson_the_verdict"} or en in {
        "michael jackson: the verdict",
    }:
        return "michael-jackson-the-verdict"
    if slug in {"avatar-last-airbender", "avatar_the_last_airbender"} or en in {
        "avatar: the last airbender",
    }:
        return "avatar-last-airbender"
    return slug


def _douban_cap(subject_id: str) -> str:
    sid = (subject_id or "").strip()
    if sid:
        return f"图源：豆瓣 movie.douban.com/subject/{sid}"
    return "图源：豆瓣条目剧照"


def _is_figure_line(line: str) -> bool:
    return bool(FIGURE_LINE_RE.match(line.strip()))


def _figure_lines(rel: str, *, style: str, cap: str) -> list[str]:
    return _figure_marker_lines(rel, style, cap)


def _find_section_by_role(lines: list[str], role: str) -> int | None:
    keys = TV_SECTION_ROLES.get(role) or [role]
    for key in keys:
        hit = _find_section_line_fuzzy(lines, key)
        if hit is not None:
            return hit
    return None


def _section_content_end(lines: list[str], role: str) -> int | None:
    """节标题后、下一节之前的插入点（须该节内已有正文行）。"""
    start = _find_section_by_role(lines, role)
    if start is None:
        return None
    j = start + 1
    has_text = False
    while j < len(lines):
        bare = _section_bare(lines[j])
        if bare is not None:
            break
        s = lines[j].strip()
        if s.startswith(">"):
            break
        if s and not _is_figure_line(lines[j]):
            has_text = True
        j += 1
    return j if has_text else None


def _tv_figure_marker_lines(
    fname: str,
    style: str,
    *,
    scene_caption: str = "",
    source_caption: str = "",
) -> list[str]:
    tokens: list[str] = []
    if style:
        tokens.append(style.strip().rstrip(";"))
    if scene_caption:
        tokens.append(f"scene={scene_caption.strip()}")
    if source_caption:
        tokens.append(f"cap={source_caption.strip()}")
    cap_str = ";".join(tokens)
    return ["", f"[[fig:{fname}|{cap_str}]]", ""]


def _paragraph_end_after_anchor(lines: list[str], anchor: str) -> int | None:
    """含 anchor 的段落结束后插入（单条 bullet 或连续正文）。"""
    key = (anchor or "").strip()
    if not key:
        return None
    for i, line in enumerate(lines):
        if key not in line or _is_figure_line(line) or not line.strip():
            continue
        j = i + 1
        while j < len(lines):
            s = lines[j].strip()
            if not s:
                return j
            if _section_bare(lines[j]) is not None:
                return j
            if s.startswith("·"):
                return j
            if s.startswith("[[fig:"):
                return j
            j += 1
        return j
    return None


def _inject_after_anchor(
    lines: list[str],
    anchor: str,
    rel: str,
    *,
    style: str,
    cap: str,
    scene_caption: str = "",
) -> tuple[list[str], int | None]:
    end = _paragraph_end_after_anchor(lines, anchor)
    if end is None:
        return lines, None
    block = _tv_figure_marker_lines(
        rel,
        style,
        scene_caption=scene_caption.strip(),
        source_caption=cap,
    )
    return lines[:end] + block + lines[end:], end


def _inject_after_section_content(
    lines: list[str],
    role: str,
    rel: str,
    *,
    style: str,
    cap: str,
    scene_caption: str = "",
) -> list[str]:
    end = _section_content_end(lines, role)
    if end is None:
        return lines
    block = _tv_figure_marker_lines(
        rel,
        style,
        scene_caption=scene_caption.strip(),
        source_caption=cap,
    )
    return lines[:end] + block + lines[end:]


def _apply_tv_figure_slots(
    lines: list[str],
    slots: list[tuple],
    *,
    slug: str,
    still_cap: str,
) -> list[str]:
    """按锚点/分节注入；同位置多图合并，自下而上插入避免错位。"""
    pending: dict[int, list[str]] = {}
    for slot in slots:
        if len(slot) < 3:
            continue
        fname, mode = slot[0], slot[1]
        target = slot[2]
        scene_caption = str(slot[3]).strip() if len(slot) > 3 else ""
        cap = str(slot[4]).strip() if len(slot) > 4 else still_cap
        rel = f"tv/{slug}/{fname}"
        block = _tv_figure_marker_lines(
            rel,
            TV_FIGURE_STYLE,
            scene_caption=scene_caption,
            source_caption=cap,
        )
        if mode == "after_anchor":
            end = _paragraph_end_after_anchor(lines, str(target))
        elif mode == "after":
            end = _section_content_end(lines, str(target))
        else:
            continue
        if end is None:
            continue
        pending.setdefault(end, []).extend(block)

    for end in sorted(pending.keys(), reverse=True):
        lines = lines[:end] + pending[end] + lines[end:]
    return lines


def normalize_tv_review_body(body: str) -> str:
    """DeepSeek 偶发 ** 加粗 → 移动端可读 bullet；剥掉「简单交代：」类标签头。"""
    out: list[str] = []
    for line in body.splitlines():
        bare = _section_bare(line)
        if bare is not None:
            cleaned = _clean_section_title(bare)
            if cleaned != bare:
                out.append(f"> {cleaned}")
                continue
        s = line.strip()
        if _STILL_PLACEHOLDER_RE.match(s):
            continue
        if not s:
            out.append(line)
            continue
        m = _BOLD_NUM_RE.match(s)
        if m:
            out.append(f"· {m.group(2).strip()}")
            continue
        m = _BOLD_LINE_RE.match(s)
        if m:
            inner = m.group(1).strip()
            m2 = re.match(r"^(\d+)[\.、:]\s*(.+)$", inner)
            out.append(f"· {m2.group(2).strip()}" if m2 else f"· {inner}")
            continue
        if "**" in line:
            cleaned = re.sub(r"\*\*([^*]+)\*\*", r"\1", line).strip()
            m2 = re.match(r"^(\d+)[\.、:]\s*(.+)$", cleaned)
            if m2:
                out.append(f"· {m2.group(2).strip()}")
                continue
            out.append(cleaned)
            continue
        out.append(line)
    text = re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()
    lines = text.splitlines()
    lines = _fix_merits_duplicate_character_bullets(lines)
    text = re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()
    from scripts.tools.wechat_mp_monetization import strip_recommend_hook
    from scripts.tools.wechat_mp_tv_polish import finalize_tv_review_body

    return finalize_tv_review_body(strip_recommend_hook(text))


_MERITS_ALT_LABELS = ("叙事", "镜头", "节奏", "表演", "视觉")
_CHAR_BULLET_BODY_RE = re.compile(r"^·\s*人物[^：:]*[：:]\s*(.+)$")


def _fix_merits_duplicate_character_bullets(lines: list[str]) -> list[str]:
    """「戳我的」段：两条都以人物开头时，第二条起改标其他维度。"""
    start = _find_section_by_role(lines, "merits")
    if start is None:
        return lines
    end = start + 1
    while end < len(lines) and _section_bare(lines[end]) is None:
        end += 1
    out = lines[:]
    char_idxs: list[int] = []
    for i in range(start + 1, end):
        s = out[i].strip()
        if s.startswith("·") and s.lstrip("·").strip().startswith("人物"):
            char_idxs.append(i)
    if len(char_idxs) <= 1:
        return out
    for n, idx in enumerate(char_idxs[1:]):
        label = _MERITS_ALT_LABELS[n % len(_MERITS_ALT_LABELS)]
        s = out[idx].strip()
        m = _CHAR_BULLET_BODY_RE.match(s)
        if m:
            out[idx] = f"· {label}：{m.group(1).strip()}"
        else:
            rest = re.sub(r"^人物[^：:]*[：:]\s*", "", s.lstrip("·").strip(), count=1)
            if rest:
                out[idx] = f"· {label}：{rest}"
    return out


def _clean_section_title(title: str) -> str:
    t = (title or "").strip()
    if not t:
        return t
    for prefix in _STIFF_SECTION_PREFIXES:
        for sep in ("：", ":"):
            head = f"{prefix}{sep}"
            if t.startswith(head):
                rest = t[len(head) :].strip()
                if rest:
                    return rest
    m = re.match(r"^([^《》]{2,8})[：:]\s*(.+)$", t)
    if m:
        head, rest = m.group(1).strip(), m.group(2).strip()
        if len(rest) >= 6 and re.search(
            r"(交代|直说|先说|背景|总结|介绍|讲明|科普|结论|建议|补充|提醒)",
            head,
        ):
            return rest
    return t


def _rating_insert_after_first_paragraph(lines: list[str]) -> int | None:
    """第一段正文之后插入评分（无 `> ` 小标题时取首段）。"""
    i = 0
    while i < len(lines) and not lines[i].strip():
        i += 1
    if i >= len(lines):
        return None
    # 旧稿：首段是 `> ` 小标题，跳过
    if _section_bare(lines[i]) is not None:
        i += 1
        while i < len(lines) and not lines[i].strip():
            i += 1
    if i >= len(lines) or _section_bare(lines[i]) is not None:
        return None
    j = i
    while j < len(lines):
        if not lines[j].strip():
            return j
        if _section_bare(lines[j]) is not None:
            return j
        j += 1
    return j


def ensure_tv_stills(topic: dict[str, Any]) -> None:
    from scripts.tools.wechat_mp_douban_stills import ensure_douban_stills, ensure_tmdb_tv_stills
    from scripts.tools.wechat_mp_tv_cover import ensure_tv_cover
    from scripts.tools.wechat_mp_tv_press_cards import ensure_x_cards

    slug = _slug(topic)
    spec = CURATED_TV_STILLS.get(slug)
    if not spec:
        return
    if spec.get("source") == "tmdb":
        ensure_tmdb_tv_stills(topic, spec)
    elif spec.get("source") == "tmdb_movie":
        from scripts.tools.wechat_mp_douban_stills import ensure_tmdb_movie_stills

        ensure_tmdb_movie_stills(topic, spec)
    elif spec.get("source") == "local":
        from scripts.tools.wechat_mp_douban_stills import INLINE_TV_ROOT

        out_dir = INLINE_TV_ROOT / slug
        out_dir.mkdir(parents=True, exist_ok=True)
        poster_tmdb = str(spec.get("poster_tmdb") or "").strip()
        if poster_tmdb:
            from scripts.tools.wechat_mp_douban_stills import download_tmdb_image

            download_tmdb_image(poster_tmdb, out_dir / "poster.jpg", size="w780")
        ensure_x_cards(spec, out_dir)
        ensure_tv_cover(slug)
    else:
        ensure_douban_stills(topic)


def inject_tv_review_figures(body: str, topic: dict[str, Any]) -> str:
    from scripts.tools.wechat_mp_tv_ratings import format_ratings_lines

    slug = _slug(topic)
    spec = CURATED_TV_STILLS.get(slug)
    subject_id = str((spec or {}).get("douban_subject_id") or "").strip()

    lines = body.splitlines()
    score_bullets, score_foot = format_ratings_lines(topic)
    insert_at = _rating_insert_after_first_paragraph(lines)

    if score_bullets and insert_at is not None:
        block: list[str] = [""] + score_bullets + [""]
        if score_foot:
            block.extend(["", score_foot, ""])
        lines = lines[:insert_at] + block + lines[insert_at:]

    if spec:
        still_cap = str(spec.get("figure_source_caption") or "").strip() or _douban_cap(subject_id)
        lines = _apply_tv_figure_slots(
            lines,
            list(spec.get("slots") or []),
            slug=slug,
            still_cap=still_cap,
        )

    out = "\n".join(lines).strip()
    foot = TV_ATTRIBUTION
    if spec and str(spec.get("figure_source_caption") or "").strip():
        cap = str(spec["figure_source_caption"]).strip().removeprefix("图源：").removesuffix("（剧评引用）").strip()
        foot = f"（配图：{cap}，剧评引用；评分数据为公开页面整理。）"
    if foot not in out:
        out = f"{out}\n\n{foot}"
    return out + "\n"
