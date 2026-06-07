"""公众号公开稿：与作者个人持仓/账户隔离 + 全局禁荐股/买卖暗示。"""

from __future__ import annotations

import re

# 注入各篇 LLM prompt / system
PUBLIC_MP_WRITER_RULE = """
【公众号公开稿】面向不特定读者发布，与作者个人无关。严禁出现：
作者持仓、已持仓/非持仓、我的仓位、个人账户、执行卡、P0～P4、结合持仓、第一人称「我」的仓位配置。
可将纪律写成「短线选手」「观望者」的通用规则；仓位用「情绪周期风控参考」等市场语言。
严禁出现：翻墙、代理订阅、Clash、Mihomo、机场节点、substore 等敏感网络工具描述。
严禁荐股与买卖暗示：推荐买入/卖出、建议建仓/加仓/抄底、观察买入、低吸埋伏、目标价喊单、强烈推荐某股等。
只可写结构、量价、板块观察与「待核实」；文末须有免责声明。
"""

# 行情四槽 LLM 共用：专业研究员口吻（与标题吸睛并存，正文恢复研究语气）
RESEARCHER_VOICE_RULE = """
【专业研究员口吻】面向不特定读者的收盘观察备忘录，不是荐股博主或聊天机器人。
- 身份：A 股宏观/策略研究岗（10～15 年经验），熟悉情绪周期与量价结构，输出为公开观察稿。
- 主语：第三人称；用「市场」「盘面」「资金」「结构」作主语；可用「我们认为」「值得关注的是」「向后看」「从数据上看」「这一链条」「尚待验证」。
- 论证：观点尽量写成「现象（含数字）→ 传导机制 → 板块/风格映射 → 1 个可跟踪指标」；缺数据写「数据未获取」，勿编造。
- 语气：冷静、有框架；少用顺口溜夸张（如将「指数虚涨、个股踩踏」改为「指数与广度背离」）；禁用震惊、必涨、上车、强烈建议买入等。
- 标题与正文：标题可用问号做列表点击；正文勿重复标题党句式，恢复研究表述。
- 与 PUBLIC_MP_WRITER_RULE 同时生效：仍禁止持仓/执行卡/荐股/买卖暗示。
"""

_DISCLAIMER_MARK = "不构成投资建议"

# 成稿后兜底清洗 — 整行删除
_LINE_DROP_RE = re.compile(
    r"^(.*(?:结合持仓|执行卡|P[0-4]\s|我的持仓|作者持仓|个人仓位|"
    r"clash|mihomo|substore|机场|订阅合并).*)$",
    re.I,
)

_INVESTMENT_DROP_LINE_RE = re.compile(
    r"^(?:"
    r"操作建议|投资建议|买卖建议|荐股建议|"
    r"(?:强烈)?推荐(?:买入|卖出|关注)|"
    r"建议(?:买入|卖出|买进|建仓|加仓|减仓|清仓|抄底)"
    r")[：:\s].*$",
    re.I,
)

# 含下列词且整行较短 → 多为操作建议句，删除
_INVESTMENT_DROP_SHORT_LINE_RE = re.compile(
    r"^(?:.*)(?:观察买入|买入观察|小仓埋伏|低吸试错|强势关注|持有观望|"
    r"继续加仓|满仓干|半仓进)(?:.*)$",
    re.I,
)

_INLINE_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    (r"（已持仓）", ""),
    (r"（非持仓）", ""),
    (r"📌已持仓", ""),
    (r"已持仓", ""),
    (r"非持仓标的", "筛选标的"),
    (r"非持仓", ""),
    (r"结合持仓", "结合盘面"),
    (r"持仓与计划", "观察与纪律"),
    (r"以执行卡为准", "按技术纪律"),
    (r"持仓标的", "筛选标的"),
    (r"不与新信号冲突加仓", "不与原策略冲突追高"),
    (r"已写入次日盘中监控", "纳入次日数据跟踪"),
    (r"个人研究笔记", "研究笔记"),
    (r"仓位上限", "情绪风控仓位参考"),
    (r"是否持仓、", ""),
    (r"是否持仓", ""),
    (r"已持仓如何处理", "标的优先级如何排序"),
    (r"仍遵守不追高、不满仓新开仓", "仍建议不追高、控制单票仓位"),
    (r"执行卡", "规则文件"),
    (r"hub\.yoloworld\.site[^\s]*", "自有看板"),
    (r"yoloworld\.site", "自有域名"),
)

_INVESTMENT_INLINE_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    (r"强烈推荐", "关注度较高"),
    (r"强力推荐", "关注度较高"),
    (r"推荐买入|推荐买进", "结构上偏强"),
    (r"推荐卖出", "结构上偏弱"),
    (r"建议买入|建议买进", "量价偏强"),
    (r"建议卖出|建议减仓|建议清仓", "量价偏弱"),
    (r"建议建仓|建议加仓", "结构待确认"),
    (r"可以买入|可以买|值得买入|值得布局", "可继续跟踪结构"),
    (r"观察买入|买入观察", "跟踪结构"),
    (r"观察为主", "以跟踪为主"),
    (r"小仓埋伏|低吸试错|低吸介入", "小仓位跟踪"),
    (r"强势关注", "波动较大"),
    (r"继续持有|持有观望", "继续跟踪"),
    (r"荐股", ""),
    (r"目标价\s*[:：]?\s*([\d.]+)\s*元", r"前高约\1元"),
)

# 合规扫描（正文核心区，排除免责声明里的「不构成投资建议」「非荐股」）
PUBLIC_COMPLIANCE_CHECKS: tuple[tuple[str, str, int], ...] = (
    ("结合持仓", r"结合持仓", 0),
    ("执行卡", r"执行卡", 0),
    ("个人持仓表述", r"我的持仓|作者持仓|个人仓位", 0),
    ("敏感网络工具", r"clash|mihomo|substore", re.I),
    ("机场/订阅", r"机场节点|订阅合并", 0),
    ("已持仓标记", r"📌已持仓|（已持仓）", 0),
    ("荐股", r"(?<!非)荐股", 0),
    ("建议买入", r"(?<!禁止)(?<!勿)建议\s*(?:买入|买进)", 0),
    ("建议卖出", r"(?<!禁止)(?<!勿)建议\s*(?:卖出|减仓|清仓)", 0),
    ("强烈推荐", r"强烈\s*推荐(?:\s*(?:买入|关注))?", 0),
    ("观察买入", r"观察\s*买入|买入\s*观察", 0),
    ("低吸埋伏", r"低吸\s*(?:试错|介入|建仓)|小仓\s*埋伏", 0),
    ("建仓建议", r"(?<!禁止)(?:建议|可以|适宜)\s*建仓", 0),
    ("加仓建议", r"(?<!禁止)建议\s*加仓", 0),
    ("值得买入", r"值得\s*(?:买入|布局)", 0),
    ("目标价喊单", r"目标价\s*[:：]?\s*[\d.]+\s*元", 0),
)


def _core_body_for_audit(text: str) -> str:
    """审计用正文：去掉免责声明及之后内容。"""
    if _DISCLAIMER_MARK in text:
        return text.split(_DISCLAIMER_MARK, 1)[0]
    return text


def strip_investment_advice(text: str) -> str:
    """全局去掉/弱化荐股与买卖暗示用语。"""
    if not text:
        return text
    lines_out: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if _INVESTMENT_DROP_LINE_RE.match(stripped):
            continue
        if _INVESTMENT_DROP_SHORT_LINE_RE.match(stripped) and len(stripped) < 80:
            continue
        s = line
        for pat, repl in _INVESTMENT_INLINE_REPLACEMENTS:
            s = re.sub(pat, repl, s)
        s = re.sub(r"\s{2,}", " ", s).strip()
        if s or not stripped:
            lines_out.append(s)
    return "\n".join(lines_out)


_TECH_META_LINE_DROP_RE = re.compile(
    r"^(.*(?:临稿栏|不碰日更|日更五槽|临时槽|给\s*Agent\s*用[：:]).*)$",
    re.I,
)

_TECH_META_INLINE: tuple[tuple[str, str], ...] = (
    (r"把授权链接转给用户[^\n。]*", "在浏览器里自己完成授权即可"),
    (r"链接给用户点完再继续", "本人点完授权再继续"),
    (r"链接给用户", "本人打开链接"),
    (r"给 Cursor 等 Agent 的四步", "在 Cursor 里怎么配"),
    (r"给 Cursor 等 Agent", "在 Cursor 里"),
)


def sanitize_tech_mp_meta(text: str) -> str:
    """技术稿：去掉 Agent/槽位/临稿等运维话术（读者向）。"""
    if not text:
        return text
    lines_out: list[str] = []
    for line in text.splitlines():
        if _TECH_META_LINE_DROP_RE.match(line.strip()):
            continue
        s = line
        for pat, repl in _TECH_META_INLINE:
            s = re.sub(pat, repl, s)
        lines_out.append(s)
    return "\n".join(lines_out)


def sanitize_public_mp_text(text: str) -> str:
    """公开稿终稿清洗：持仓/敏感词 + 荐股买卖暗示。"""
    if not text:
        return text
    lines_out: list[str] = []
    for line in text.splitlines():
        if _LINE_DROP_RE.match(line.strip()):
            continue
        s = line
        for pat, repl in _INLINE_REPLACEMENTS:
            s = re.sub(pat, repl, s)
        s = re.sub(r"P[0-5][^\n]*", "", s)
        s = re.sub(r"\s{2,}", " ", s).strip()
        if s or not line.strip():
            lines_out.append(s)
    merged = "\n".join(lines_out)
    merged = re.sub(r"\n{3,}", "\n\n", merged)
    merged = strip_investment_advice(merged)
    return merged.strip()


_TECH_KINDS = frozenset({"workspace", "temp", "tech", "lab", "dev"})


def finalize_public_body_text(text: str, *, kind: str | None = None) -> str:
    """成稿最后一道公开稿清洗（各 kind 在进 HTML 前调用）。"""
    out = sanitize_public_mp_text(text)
    if (kind or "").strip().lower() in _TECH_KINDS:
        out = sanitize_tech_mp_meta(out)
    from scripts.tools.wechat_mp_readability import polish_mobile_readability

    return polish_mobile_readability(out)


def check_public_compliance(text: str, *, title: str = "") -> list[str]:
    """返回合规失败项标签；空列表表示通过。"""
    failures: list[str] = []
    core = _core_body_for_audit(text)
    blob = f"{title}\n{core}"
    for label, pat, flags in PUBLIC_COMPLIANCE_CHECKS:
        if re.search(pat, blob, flags=flags):
            failures.append(label)
    if re.search(r"(?<![你])我(?:的|们)?(?:仓|持仓|账户)", core):
        failures.append("第一人称持仓")
    return failures
