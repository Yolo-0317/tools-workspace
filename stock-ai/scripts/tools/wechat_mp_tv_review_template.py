#!/usr/bin/env python3
"""影视试跑定稿模板 tv_review_v1（真源：data/wechat_mp_tv_review_template.json）。"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_PATH = ROOT / "data" / "wechat_mp_tv_review_template.json"
DEFAULT_TEMPLATE_ID = "tv_review_v2"

TV_DEPTH_RULE = """
【影视深度与见解】剧评不是剧情梗概或营销复述。
- 立意：写清作品想讨论的社会/人性命题，区分「爽点/话题」与「主题」。
- 见解：至少 2 处对剧情/表演/镜头的判断（可用「这片真正压人的是」「表演上成立」），须挂钩具体桥段，**不要**代入作者私生活（禁止「让我想起自己加班/发消息没人回」类假共情）。
- 口吻：**禁止第一人称叙事**（不用「我看的晚场」「我倒是先想起」）；客观剧评口吻，感情写在场面/表演/配乐上。
- 开头排序：**首段**写上映/场面意象/主题钩子，**不写**豆瓣/烂番茄具体分（由脚本在首段后注入竖排 bullet）；**第二段**再接「口碑/观感」判断进入剧评，避免开头念一遍、评分块又念一遍。
- 段落：每段 2～4 句，禁止单句成段；脚本 `merge_tv_short_paragraphs` 合并碎段。
- 感情色彩：让观众感到闷、紧、暖、空，而非「我哭了/我眼眶热了」或读者自传式假共情。
- 争议：两极作品写清「爽从哪来、不安从哪来」，勿只站一边。
- 仍禁止：盗版、资源帖、未核实八卦、引战踩一捧一、emoji。
- 去 AI 味：禁「剧情承接」「梗概也熟」「把设定当主线/开场工具」「这是客观缺点」「几场戏值得单独说」；前作背景用戏里场面带出，不写百科式复习。
- 大白话：禁影评腔/论文腔——「戏眼」「意象」「场面堆叠」「正向反馈」「遮羞布」「拍实」「耳目一新」「排片热度对得上」「预告片素材」；改用口语（「重点不是」「留到最后的画面」「大战一通堆」「好处/一声谢谢」「窗户纸」「演出来了」「算久违/算新鲜」）。
- 真人语感：先丢具体画面再下判断；用「翻日历才会发现」「内地没上那部」「说白了」「散场后吐槽也集中在这」；禁「不是A而是B」连用、禁半句话（「那种熟」）。仿写真源见 skill `tv-review-voice.md`。
- 讲故事聊天感：禁介绍体——「冲X来的会觉得」「拿不准值不值得：」「订票前最好补梗概：」「XXX那场：」；优缺点用散场后口碑/吐槽带出，像转述观众反应，不像导购清单。
- 朋友分享语气：可以稍啰嗦，用「说穿了」「可爱聊归爱聊」「有个段落特别好记」「散场门口聊天也很有意思」「说到底」；像看完电影顺嘴聊，不像说明书分点介绍。
"""


def tv_depth_prompt_block() -> str:
    return TV_DEPTH_RULE.strip()


@lru_cache(maxsize=1)
def load_tv_review_template(*, template_id: str = DEFAULT_TEMPLATE_ID) -> dict[str, Any]:
    if not TEMPLATE_PATH.is_file():
        raise FileNotFoundError(f"影视模板不存在: {TEMPLATE_PATH}")
    data = json.loads(TEMPLATE_PATH.read_text(encoding="utf-8"))
    if str(data.get("template_id") or "") != template_id:
        raise ValueError(f"模板 id 不匹配: {data.get('template_id')!r}")
    return data


def golden_body_core_path(template: dict[str, Any] | None = None) -> Path:
    tpl = template or load_tv_review_template()
    rel = str((tpl.get("reference") or {}).get("golden_body_core") or "")
    return ROOT / rel if rel else TEMPLATE_PATH


def load_golden_body_core(*, template_id: str = DEFAULT_TEMPLATE_ID) -> str:
    tpl = load_tv_review_template(template_id=template_id)
    path = golden_body_core_path(tpl)
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8").strip()


def template_prompt_block(*, template: dict[str, Any] | None = None) -> str:
    """DeepSeek 提示词中的结构与排版约束（与 euphoria 定稿一致）。"""
    tpl = template or load_tv_review_template()
    sections = tpl.get("sections") or []
    forbidden = (tpl.get("heading_style") or {}).get("forbidden_section_titles") or tpl.get("forbidden_section_titles") or []
    patterns = (tpl.get("heading_style") or {}).get("forbidden_heading_patterns") or tpl.get("forbidden_heading_patterns") or []
    discouraged = (tpl.get("heading_style") or {}).get("discouraged_heading_patterns") or []
    variation = str((tpl.get("heading_style") or {}).get("variation_note") or "").strip()
    layout = tpl.get("layout") if isinstance(tpl.get("layout"), dict) else {}

    lines = [
        "- 全文 900–1400 汉字，**纯段落**；移动端每段 2～4 句，段间空一行；`finalize_tv_review_body` 会合并过短段（&lt;100 字或单句）",
        "- 口吻：**禁止第一人称「我」**；客观剧评（IGN 中国 / 文娱号长评），感情挂在场面与表演上，**禁止**小编体、对称金句",
        "- **禁止** `> ` / `#` 小标题、禁止「简单交代：」「分集速写：」等节标签",
        "- **禁止**单独一行当段落（如只有一句「没看过前作也能进场」必须并入上下段）",
        f"- **禁止**模板式标题：{'、'.join(forbidden)}",
        f"- **禁止**标签冒号式标题：{' / '.join(patterns)}",
    ]
    if discouraged:
        lines.append(f"- **少用**套句式（勿照搬金样五节标题）：{' / '.join(str(x) for x in discouraged)}")
    if variation:
        lines.append(f"- {variation}")
    lines.extend(
        [
            "- 排版（脚本自动注入，正文里**不要**写评分行或 `[[fig:]]`）：",
            f"  · 无顶栏 banner；评分竖排 bullet，插在**第一节第一段正文之后**",
            f"  · 最多 {int(layout.get('figure_count') or 10)} 张配图，`after_anchor` 插在分集/关键段落后（见 teach-you-a-lesson 配置）",
            "  · 分节标题渲染为横幅底 + 标题（脚本 HTML）",
            "- 五节意思（参考《铁拳教育》金样 data/wechat_mp_tv_review_golden/teach_you_a_lesson.body_core.md，**勿照抄其小标题句式**）：",
        ]
    )
    for sec in sections:
        if not isinstance(sec, dict):
            continue
        ex = str(sec.get("example_heading") or "").strip()
        hint = str(sec.get("content_hint") or "").strip()
        if ex:
            lines.append(f"  > {ex}（{hint}）" if hint else f"  > {ex}")
    lines.extend(
        [
            tv_depth_prompt_block(),
            "- 第三节写 **按集 bullet**（小标题自拟，勿固定「分集速写：」前缀），用 `· 第N集（副标题）：` 逐集写具体桥段（单元剧/纪录片）；≤6 集写全，≥8 集可写重点集 + 汇总",
            "- 勿用《亢奋》式「人物/节奏/镜头」三条替代分集（除非非单元结构且 Agent 在 skill 中注明）",
            "- 禁止：盗版链接、免费资源、网盘、未核实明星八卦、引战踩一捧一",
            "- 禁止 emoji",
            "- **禁止**文末「推荐 ♡ / 推给同样在复盘的朋友」等财经号引导（脚本不会注入）",
            "- 末段互动问句（如「更吃街头彼得还是宇宙大活」）",
            "- 正文提及评分时用阿拉伯数字（7.8、90%），勿写「七点八」「九成」；精确分仍由脚本从 topic.ratings 注入竖排 bullet",
        ]
    )
    if layout.get("ratings_footnote"):
        lines.append(f"- 评分脚注格式：{layout['ratings_footnote']}")
    sens = tpl.get("sensitive_words")
    if isinstance(sens, dict):
        avoid = sens.get("avoid") or []
        repl = sens.get("preferred_replacements") or []
        if avoid:
            lines.append(
                "- **敏感词**：正文尽量避免 "
                + "、".join(str(x) for x in avoid[:12])
                + ("…" if len(avoid) > 12 else "")
            )
        for item in repl[:8]:
            if isinstance(item, dict) and item.get("avoid") and item.get("use"):
                lines.append(f"  · 勿写「{item['avoid']}」，可改用：{item['use']}")
        note = str(sens.get("policy") or "").strip()
        if note:
            lines.append(f"- {note}")
    return "\n".join(lines)


def template_system_message(*, template: dict[str, Any] | None = None) -> str:
    tpl = template or load_tv_review_template()
    ref = tpl.get("reference") if isinstance(tpl.get("reference"), dict) else {}
    title = str(ref.get("title") or "追完《铁拳教育》，爽完为什么没特痛快？")
    return (
        "你是影视评论编辑，写给普通中文读者（韩剧/美剧/电影均可）。"
        "文字有观点、有细节、能点出作品立意，拒绝空洞形容词与剧情流水账。"
        "小节标题要像朋友发微信：一句完整的话，每片自拟、贴合本片，"
        "不要照搬金样五节句式（如「看着像…其实是在…」「分集速写：」「拿不准就开…」）。"
        "不要「简单交代：」「直说：」这种标签冒号格式。"
        f"排版遵循模板 {tpl.get('template_id')}（定稿参考：《铁拳教育》· {title}）。"
    )
