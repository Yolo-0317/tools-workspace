#!/usr/bin/env python3
"""影视试跑稿：HBO / Netflix / 经典老片与新片安利（Composer 正文）。"""

from __future__ import annotations

import json
import os
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.deepseek_client import (
    call_wechat_mp_llm,
    is_wechat_mp_llm_configured,
    wechat_mp_llm_backend,
)
from scripts.tools.wechat_mp_public import (
    audit_recommendation_safety,
    sanitize_public_title,
)
from scripts.tools.wechat_mp_role_card import account_role_prompt_block
from scripts.tools.wechat_mp_tv_topics import (
    load_tv_trial_config,
    pick_tv_topic,
    tv_trial_active,
)


ROOT = Path(__file__).resolve().parents[2]
TRIAL_PATH = ROOT / "data/wechat_mp_tv_trial.json"
TZ = ZoneInfo("Asia/Shanghai")

_LAST_BUILT_TV_TOPIC: dict[str, Any] | None = None

def tv_llm_backend() -> str:
    return wechat_mp_llm_backend()


def get_last_built_tv_topic() -> dict[str, Any] | None:
    """build_tv_review_article 刚构建的 topic（封面须与正文同题）。"""
    return _LAST_BUILT_TV_TOPIC


def _platform_label(topic: dict[str, Any]) -> str:
    p = str(topic.get("platform") or "").strip()
    if p.upper() == "HBO":
        return "HBO"
    if "netflix" in p.lower():
        return "Netflix"
    return p or "流媒体"


def _show_label(topic: dict[str, Any]) -> str:
    zh = str(topic.get("title_zh") or "").strip()
    en = str(topic.get("title_en") or "").strip()
    if zh and en:
        return f"《{zh}》({en})"
    return f"《{zh or en}》"


from scripts.tools.wechat_mp_tv_title import (
    TV_TITLE_FORBIDDEN_RE,
    pick_tv_review_title,
)


def build_tv_review_title(topic: dict[str, Any], *, now: datetime | None = None) -> str:
    from scripts.tools.wechat_mp_content import _clip_wechat_title

    override = str(topic.get("title_override") or "").strip()
    if override:
        return sanitize_public_title(_clip_wechat_title(override), kind="tv_review")

    if str(topic.get("content_mode") or "").strip().lower() == "discussion":
        trend = str(topic.get("trend_title") or topic.get("title_zh") or "").strip()
        subject = str(topic.get("title_zh") or trend[:10]).strip()
        if len(trend) <= 26:
            title = trend if "？" in trend or "?" in trend else f"{trend}？"
        else:
            title = f"{subject}上热搜，大家在吵什么？"
        return sanitize_public_title(_clip_wechat_title(title), kind="tv_review")

    now = now or datetime.now(TZ)
    title = pick_tv_review_title(topic, now=now)
    if TV_TITLE_FORBIDDEN_RE.search(title):
        title = pick_tv_review_title(
            {**topic, "heat_score": int(topic.get("heat_score") or 0) + 3},
            now=now,
        )
    return sanitize_public_title(_clip_wechat_title(title), kind="tv_review")


def build_tv_review_digest(topic: dict[str, Any]) -> str:
    if str(topic.get("content_mode") or "").strip().lower() == "discussion":
        trend = str(topic.get("trend_title") or topic.get("title_zh") or "")[:60]
        return f"【话题讨论】{trend}。围观分歧，非官方通稿。"[:120]
    label = _show_label(topic)
    plat = _platform_label(topic)
    hook = str(topic.get("hook") or "一部值得聊的欧美剧/电影")[:60]
    return f"{plat} · {label}：{hook}。个人观感，非官方宣传。"[:120]


def _fallback_body(topic: dict[str, Any]) -> str:
    label = _show_label(topic)
    plat = _platform_label(topic)
    hook = str(topic.get("hook") or "")
    year = str(topic.get("year") or "")
    kind = "电影" if str(topic.get("type") or "") == "film" else "剧"
    return f"""> 四年空窗后回来，还值得开刷吗

如果你最近剧荒，{label} 值得放进清单里试一集——但别带着「神剧」预期。

> 一部 {kind}，约 {year} 年，在 {plat} 上

{hook}。这不是官方通稿，只是个人向安利。

> 戳我的就这几处

人物有弧线，不是纯爽点堆叠；节奏适合晚上一集一集往下刷。若你讨厌慢热，可以先看 20 分钟再决定留不留。

> 谁会很爱，谁可以略过

喜欢 HBO / Netflix 长剧或高质量电影的人；若只想 5 分钟刷完清单，这篇可能不适合你。

> 拿不准？先花 20 分钟试一集

今晚先开第一集（或前 15 分钟），看你能不能主动点下一集——这比任何评分都准。

你看过 {label} 吗？留言说说你站「立刻开刷」还是「先囤着」。"""


def _discussion_voice_prompt_block() -> str:
    return """## 角色（最先遵守）
你是**读者转述者**：像在群里转述热搜和评论区的吵法。你不是行业分析师、政策解读记者、产业观察员。
禁止：风向是在松、政策松绑、与其说/不如说、一拨问另一拨、对X来说、预期/去化/叙事等行业报告腔。
政策原文只放引用块；你的叙述用口语转述网友在传什么、在担心什么。

## 语气（朋友聊事，对齐蜘蛛侠金样——先事实，后议论）
- 首段**直接写人+事**（谁、在哪、发生了什么），禁止「刷到热搜」「第一反应」「往下翻才知道」「不是几句口水」等导读/meta 句
- 长短句交错；可用：说穿了（至多一处）、可爱聊归爱聊（慎用）、散场后顺嘴聊
- **硬禁假口语/空词**：挺寒的、从别的口子、基本盘、落锤、条线上、掰扯一摞、这茬
- **硬禁**：对称分述「一块…另一块」「一拨问…另一拨问」「两拨人」「底下其实是」「先说为什么」
- **硬禁行业/技术隐喻**：硬盘里、排期轮不上、播出许可、沉没库存、选择疲劳、库存去化——改用证、档期、放着等、钱回不来等日常说法
- **硬禁分析报告腔**：「与其说…不如说…」「对X来说」「不等于」「预期天然」「不补叙事/调节奏」「真正卡住的往往不是…而是…」——像转述网友在吵什么，不像行业观察报告
- **硬禁 Markdown 加粗** `**`（公众号不渲染）
- **硬禁**：「值得注意的是」「第一/二条线」「二次发酵」；段末总结腔
- **硬禁热榜播报**：「百度把…送上热搜」「微博词条#…#也在转」「热度破亿」「吵上热搜」——写观众在吵什么，勿念榜
- **硬禁抬格调**：「这事闹这么大」「也跟大背景有关」——剧集吐槽/选角争议用「吵了一架」「算不上大事」
- **硬禁压缩怪句**：叙述层不用「进度飞」「眼里没光」「演技能补」「一眼五年前」「一眼X年前」等弹幕缩写；须完整人话
- **硬禁分论点举例腔**：不用「有人举那种…」「有人拿…来论证」——改用「有帖子拿…举例」「网上有人贴…」「评论区在吵…」
- **硬禁制片行业词**（叙述层）：服化道、妆造道、叙事、调节奏、去化、人设服化——改用妆发、造型、台词、戏能不能看等观众说法
- **政策简称**：只写「广电21条」等口语称呼，不写总局文件全称；长引语勿用 `> ` 引用块（微信易吞字）
- **正反例（学写法，勿照抄）**：
  × 有人举那种压了多年的仙侠，服化道一眼五年前，台词还是「小奶狗」
  √ 有帖子拿压了好多年的仙侠举例：妆发还是几年前的样子，台词还在说「小奶狗」「霸总」
  × 风向是在松：四十集上限拟放开
  √ 最近帖子也在传：四十集上限可能要放开
- **社会民生排版**（案由、劳动者、公共事件）：极短段；用物件立人（风扇、挂面等）；先写通报模糊称谓再写民间记忆中的名字；第三方原话适合引用块；感情克制，禁「三观震碎」「泪如雨下」连发；司法未结不下定论
- **引流节奏**（推荐流陌生读者）：开篇 80 字内落地标题事件；一句一段为主；每 300–500 字用对照句、原话或轻问句做钩子；至少 2 处可转述细节（具体数字、原话、画面）方便读者转群；结尾名字+事实或一句站队问句；正文不写关注诱导
- **数字**：年份、刑期、金额、数据量用阿拉伯数字（2018年、6年、89TB），禁止「二〇一八年」「六年」等汉字数
- 社会争议：只写公开可核对信息；篇幅 **1800–2400 字**"""


def _rewrite_discussion_against_references(body: str, *, reference_block: str) -> str:
    if not reference_block or not is_wechat_mp_llm_configured():
        return body
    prompt = f"""{account_role_prompt_block()}

## 稿型任务：影视话题参考稿改写
对照【参考文章】的写法，重写下面这篇热搜讨论初稿。

要求：
- 学参考稿：首句直接写人物+事实，删掉「值得注意的是」「第一/二条线」「写到这儿就够」等 AI 套话
- 每段 2～4 句；保留正确事实，可补参考稿里有、初稿缺的可核对细节
- 纯段落，禁止小标题；口吻像跟朋友聊，但信息密度接近媒体报道
- 禁止编造；禁止第一人称「我」
- 禁止分析报告腔：有人举那种、服化道、一眼五年前、一拨/另一拨、与其说/不如说、风向松绑
- 转述网友用：有帖子拿…举例、网上也在吵、有人接话、也有人泼冷水

【参考文章】
{reference_block}

【初稿】
{body}

只输出重写后的正文，不要解释。"""
    try:
        raw = call_wechat_mp_llm(
            [
                {
                    "role": "system",
                    "content": "仿写社会新闻报道，口语但有细节，像人写的评论。只输出正文。",
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=4800,
            temperature=0.52,
        )
        out = re.sub(r"\n{3,}", "\n\n", raw.strip())
        if len(out) >= max(900, int(len(body) * 0.65)):
            return out
    except Exception:
        pass
    return body


def generate_tv_discussion_body(topic: dict[str, Any], *, now: datetime | None = None) -> str:
    """热搜话题讨论稿：朋友讨论口吻，纯段落，非五节剧评。"""
    trend = str(topic.get("trend_title") or topic.get("title_zh") or "").strip()
    subject = str(topic.get("title_zh") or "").strip()
    hook = str(topic.get("hook") or trend)[:200]
    refs = "\n".join(f"- {x}" for x in (topic.get("reference_angles") or [])[:4])

    research_block = ""
    reference_block = ""
    hits = []
    if os.getenv("WECHAT_MP_TV_RESEARCH", "1").strip().lower() not in ("0", "false", "no", "off"):
        from scripts.tools.wechat_mp_discussion_research import (
            fetch_discussion_research,
            format_discussion_research_bundle,
        )
        from scripts.tools.wechat_mp_tv_research import format_tv_trend_context_block

        hits = fetch_discussion_research(topic)
        research_block = format_discussion_research_bundle(topic, hits)
        if research_block:
            from scripts.tools.wechat_mp_discussion_research import format_discussion_imitation_block

            reference_block = format_discussion_imitation_block(hits)
        trend_ctx = format_tv_trend_context_block(topic)
        if trend_ctx:
            research_block = "\n\n".join(x for x in (trend_ctx, research_block) if x)
        if research_block:
            research_block = "\n\n" + research_block

    refs_block = f"- 参考角度：\n{refs}" if refs else ""
    prompt = f"""{account_role_prompt_block()}

## 稿型任务：影视话题讨论
为微信公众号「栀夏未完成」写一篇**热搜话题讨论稿**（社会观察，非剧评）。

## 热搜话题
- 主话题：{subject}
- 热搜原文：{trend}
- 背景线索：{hook}
{refs_block}{research_block}

## 稿型（必须遵守）
- **必须先读【参考文章·仿写】**，学同题报道怎么开头、怎么铺事实，再写；禁止整段照搬
- **纯段落**，禁止 `> ` / `#` / 「一、二、三」/「第一/二条线」小标题
- **1800–2400 汉字**，8–11 段
- 首段：人物+地点+冲突（谁、发生了什么），不要「今天我们来聊」
- 中段：2～4 个可核对细节（机构名、时间、律师/医院回应）
- 社会争议：只写公开报道、呈现多方观点，不人身攻击、不编造
- 末段：官司/舆论后续观察，非投资建议

{_discussion_voice_prompt_block()}

只输出正文，不要标题、摘要、免责声明。"""

    min_chars = 1700
    try:
        raw = call_wechat_mp_llm(
            [
                {
                    "role": "system",
                    "content": (
                        "你是读者转述者，不是行业分析师。像在群里转述热搜和评论区吵法："
                        "口语、有信息量。禁止服化道、有人举那种、一眼五年前、一拨另一拨、政策松绑等报告腔。"
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=4500,
            temperature=0.58,
        )
        body = re.sub(r"\n{3,}", "\n\n", raw.strip())
        if reference_block and os.getenv("WECHAT_MP_DISCUSSION_IMITATE_REWRITE", "0").strip().lower() not in (
            "0",
            "false",
            "no",
            "off",
        ):
            body = _rewrite_discussion_against_references(body, reference_block=reference_block)
        from scripts.tools.wechat_mp_report_voice import scan_report_voice

        voice_hits = scan_report_voice(body)
        if voice_hits and os.getenv(
            "WECHAT_MP_DISCUSSION_ALLOW_REPORT_VOICE", ""
        ).strip().lower() not in {"1", "true", "yes"}:
            labels = "、".join(h[0] for h in voice_hits[:5])
            raise RuntimeError(
                f"话题讨论稿含分析报告腔（{labels}），已拒绝保存：{subject}"
            )
        if len(body) >= min_chars:
            return body
        if len(body) >= 600:
            return body
    except Exception:
        pass
    body = _fallback_discussion_body(topic)
    if os.getenv("WECHAT_MP_DISCUSSION_ALLOW_FALLBACK", "").strip().lower() not in {
        "1",
        "true",
        "yes",
    }:
        raise RuntimeError(
            f"话题讨论稿生成失败（Composer 不可用或正文过短），已拒绝模板兜底：{subject}"
        )
    return body


_DISCUSSION_FALLBACK_MARKERS = (
    "评论区很快分成两拨",
    "当成热闹看过即可",
    "把吵点摊开，比急着下结论更接近真实舆论现场",
)


def is_discussion_template_fallback(body: str) -> bool:
    text = (body or "").strip()
    if not text:
        return False
    return sum(1 for m in _DISCUSSION_FALLBACK_MARKERS if m in text) >= 2


def _fallback_discussion_body(topic: dict[str, Any]) -> str:
    trend = str(topic.get("trend_title") or topic.get("title_zh") or "热搜话题")
    subject = str(topic.get("title_zh") or trend[:12])
    return f"""{trend}挂上热搜，评论区很快分成两拨：一拨觉得话题本身就有讨论价值，另一拨觉得热闹过去也就散了。说穿了，能上榜往往不是因为案情多离奇，而是情绪已经攒够，差一个出口。

先把能公开核对的信息摆在桌面上。大家反复提到的核心是「{subject}」——不是抽象概念，而是具体情节、一句话或一个场景带出来的语境。各家说法未必完全一致，讨论稿只能基于公开表述，不能替司法或伦理问题下定论。

回头细想，分歧往往不在「发生了什么」，而在「该怎么读」。有人从专业或审美角度挑刺，有人从公共讨论边界出发质疑；还有人纯粹把它当成消遣话题，看完就划走。三种读法在同一条热搜下并存，才是文娱话题的常态。

这类讨论很少能在一两天内有个定论。更常见的是当事人沉默，网友自行复盘，媒体补一两篇解读，然后榜单被下一条热点顶掉。对围观者来说，值得留下的不是站队结论，而是「这条热搜为什么能火」。

说到底，普通人不必为每一条热搜焦虑。可以问三个小问题：这条消息有没有可核对的事实？争论的是作品还是人身？三天后还会有人提吗？三个里有两个答不上来，就当热闹看过即可。

后续会不会还有二次发酵，要看有没有新物料或当事人回应。没有的话，讨论热度通常会按热搜曲线自然回落。把吵点摊开，比急着下结论更接近真实舆论现场。"""


def generate_tv_review_body(topic: dict[str, Any], *, now: datetime | None = None) -> str:
    if str(topic.get("content_mode") or "").strip().lower() == "discussion":
        return generate_tv_discussion_body(topic, now=now)
    now = now or datetime.now(TZ)
    if not is_wechat_mp_llm_configured():
        return _fallback_body(topic)

    label = _show_label(topic)
    plat = _platform_label(topic)
    kind = "电影" if str(topic.get("type") or "") == "film" else "剧集"
    hook = str(topic.get("hook") or "")
    year = str(topic.get("year") or "")
    refs = topic.get("reference_angles") or []
    srcs = topic.get("sources") or []
    ref_block = ""
    if refs or srcs:
        ref_block = "\n## 可参考讨论角度（融入判断，勿照搬营销号句式）\n"
        ref_block += "\n".join(f"- {x}" for x in refs[:5])
        if srcs:
            ref_block += "\n\n## 公开报道参考（可模糊引用，勿编造精确数字）\n"
            ref_block += "\n".join(f"- {x}" for x in srcs[:5])

    from scripts.tools.wechat_mp_tv_review_template import (
        template_prompt_block,
        template_system_message,
        tv_depth_prompt_block,
    )
    from scripts.tools.wechat_mp_tv_research import fetch_tv_research, format_tv_research_bundle

    research_block = ""
    if topic.get("from_trend") or os.getenv("WECHAT_MP_TV_RESEARCH", "1").strip().lower() not in ("0", "false", "no", "off"):
        hits = fetch_tv_research(topic)
        research_block = format_tv_research_bundle(topic, hits)
        if research_block:
            research_block = "\n\n" + research_block

    prompt = f"""{account_role_prompt_block()}

## 稿型任务：影视长文
为微信公众号「栀夏未完成」写一篇影视安利稿（个人观感，非官方通稿）。
排版遵循定稿模板 tv_review_v2，见 data/wechat_mp_tv_review_template.json 与 teach_you_a_lesson 金样。

## 作品
- 名称：{label}
- 平台：{plat}
- 类型：{kind}，约 {year} 年
- 安利角度：{hook}
{ref_block}{research_block}

## 深度要求
{tv_depth_prompt_block()}

## 要求
{template_prompt_block()}

**硬性**：五节必须写全，总字数 900–1400 汉字；第三节至少 4 条分场 bullet；禁止写到一半停止。

只输出正文 markdown，不要标题行、不要摘要、不要免责声明。"""

    min_chars = 850
    try:
        for attempt in range(2):
            raw = call_wechat_mp_llm(
                [
                    {
                        "role": "system",
                        "content": template_system_message(),
                    },
                    {"role": "user", "content": prompt},
                ],
                max_tokens=4000,
                temperature=0.55 if attempt == 0 else 0.62,
            )
            body = re.sub(r"\n{3,}", "\n\n", raw.strip())
            if len(body) >= min_chars:
                return body
        if len(body) >= 400:
            return body
        return _fallback_body(topic)
    except Exception:
        return _fallback_body(topic)


def build_tv_review_article(*, now: datetime | None = None) -> dict[str, str]:
    global _LAST_BUILT_TV_TOPIC
    now = now or datetime.now(TZ)
    topic = pick_tv_topic(when=now)
    _LAST_BUILT_TV_TOPIC = topic
    from scripts.tools.wechat_mp_tv_body_cache import load_tv_body_cache, save_tv_body_cache
    from scripts.tools.wechat_mp_tv_figures import (
        ensure_tv_stills,
        inject_tv_review_figures,
        normalize_tv_review_body,
    )

    ensure_tv_stills(topic)
    key = str(topic.get("cover_slug") or topic.get("title_en") or "").strip()
    cached = load_tv_body_cache(topic_key=key) if key else None
    is_discussion = str(topic.get("content_mode") or "").strip().lower() == "discussion"
    if cached and is_discussion and is_discussion_template_fallback(str(cached.get("body_core") or "")):
        cached = None
    if cached:
        title = str(cached.get("title") or build_tv_review_title(topic, now=now))
        digest = str(cached.get("digest") or build_tv_review_digest(topic))
        raw_core = str(cached.get("body_core") or "")
        if is_discussion:
            from scripts.tools.wechat_mp_discussion_polish import finalize_discussion_body

            body_core = finalize_discussion_body(raw_core)
        else:
            body_core = normalize_tv_review_body(raw_core)
    else:
        title = build_tv_review_title(topic, now=now)
        digest = build_tv_review_digest(topic)
        body = generate_tv_review_body(topic, now=now)
        if is_discussion:
            from scripts.tools.wechat_mp_discussion_polish import finalize_discussion_body

            body_core = finalize_discussion_body(body)
        else:
            body_core = normalize_tv_review_body(body)
        if is_discussion_template_fallback(body_core):
            raise RuntimeError(
                f"话题讨论稿为模板兜底正文，已拒绝推送：{topic.get('title_zh') or key}"
            )
        if not topic.get("from_trend") or is_discussion:
            save_tv_body_cache(
                topic,
                body_core=body_core,
                title=title,
                digest=digest,
            )
    if is_discussion:
        from scripts.tools.wechat_mp_discussion_figures import inject_discussion_figures

        body_with_figs = inject_discussion_figures(body_core, topic)
        if body_with_figs.count("[[fig:") < 1 and os.getenv(
            "WECHAT_MP_DISCUSSION_REQUIRE_FIGURES", "1"
        ).strip().lower() not in {"0", "false", "no", "off"}:
            raise RuntimeError(
                f"话题讨论稿正文配图不足 1 张可用事件图（当前 {body_with_figs.count('[[fig:')}），"
                f"已拒绝推送：{topic.get('title_zh') or key}"
            )
        from scripts.tools.wechat_mp_discussion_figures import ensure_discussion_cover

        ensure_discussion_cover(topic)
        body = f"{body_with_figs}\n\n"
        from scripts.tools.wechat_mp_content import disclaimer_for_kind

        body += disclaimer_for_kind("tv_review")
    else:
        body = inject_tv_review_figures(body_core, topic)

    issues = audit_recommendation_safety(title=title, digest=digest, body=body)
    if issues:
        title = sanitize_public_title(
            re.sub(r"[？?！!]", "？", title)[:32],
            kind="tv_review",
        )

    from scripts.tools.wechat_mp_content import _article_shell
    from scripts.tools.wechat_mp_seo import attach_publish_hints

    return attach_publish_hints(
        _article_shell(
            title=title,
            digest=digest,
            body_text=body,
            kind="tv_review",
            engagement_kind="discussion" if is_discussion else None,
        ),
        "tv_review",
    )
