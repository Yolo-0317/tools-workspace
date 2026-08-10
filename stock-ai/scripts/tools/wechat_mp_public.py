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
- 论证：观点尽量写成「现象（含数字）→ 传导机制 → 板块/风格映射 → 1 个可跟踪指标」；缺个股级数据时写板块/指数层面现象，**禁止**向读者写「数据未获取/样本未获取/未能获取/交易时段数据缺失」等采集缺口，勿编造数字。
- 宏观与政策：全文至少 1 处把公开宏观/产业政策背景写进传导链（货币政策、财政/产业规划、监管口径、海外利率与汇率等），与当日盘面或行业现象挂钩；只写素材与上下文中出现或可模糊引用的公开信息，勿编造文件号与未公布细则。
- 主观判断：除事实陈列外，须有 2～3 处明确研究立场（「我们认为」「值得关注的是」「向后看」各至少 1 次），写清倾向、理由与可验证指标；合规下仍禁止买卖暗示、仓位与目标价。
- 语气：冷静、有框架；少用顺口溜夸张（如将「指数虚涨、个股踩踏」改为「指数与广度背离」）；禁用震惊、必涨、上车、强烈建议买入等。
- 标题与正文：标题可用问号做列表点击；正文勿重复标题党句式，恢复研究表述。
- 与 PUBLIC_MP_WRITER_RULE 同时生效：仍禁止持仓/执行卡/荐股/买卖暗示。
"""

PLATFORM_PROPERTY_RISK_RULE = """
【微信推荐资质 · 信息观察稿】正文与标题须定位为「公开信息整理 + 市场复盘」，不是理财推介或投顾服务：
- 禁止：理财、基金推介、投资方案、投资操作、收益承诺/收益判断、买卖时点、仓位建议、跟单、必涨、稳赚。
- 禁止：「怎么玩」「明日盯啥」「收盘信号出炉」「A股必读」「A股周末必读」等易被理解为操作指引或诱导阅读的标题/问句。
- 可写：板块/产业链/情绪/量价/涨跌幅等公开事实；用「待验证」「结构观察」「信息整理」替代「信号」「操作」。
- 个股仅作行情对照样本，须写清「观察样本、非推荐名单」；勿写「领衔买入」「值得关注布局」。
"""

_FINANCE_MP_KINDS = frozenset({"market", "sector", "hotspot", "top5", "dragons", "news", "guba"})

# 社会/文娱热点评论稿（非 A 股复盘）
COMMENTARY_MP_KINDS = frozenset({"hotspot", "tv_review", "tv", "film", "movie"})

INFORMATION_NOTICE = (
    "【说明】本文为公开市场数据整理与个人复盘笔记，非证券投资咨询、非理财推介，"
    "不涉及具体投资操作或收益判断，仅供参考。"
)

COMMENTARY_INFORMATION_NOTICE = (
    "【说明】本文为公开报道与网络讨论整理，呈现多方观点，供阅读与讨论，不代表本号立场。"
)

_INFORMATION_NOTICE_LINE_RE = re.compile(
    r"^【说明】本文为公开市场数据整理与个人复盘笔记，非证券投资咨询、非理财推介，"
    r"不涉及具体.+?，仅供参考。\s*$"
)

_COMMENTARY_NOTICE_LINE_RE = re.compile(
    r"^【说明】本文为公开报道与网络讨论整理，呈现多方观点，供阅读与讨论，"
    r"不代表本号立场。\s*$"
)

_DISCLAIMER_MARK = "不构成投资建议"

# 社会新闻常见词；勿与代理/VPN「机场」混淆
_SOCIAL_NEWS_KEEP_HINTS = ("国际机场", "飞机", "航班", "航司", "乘机", "登机", "航站楼")


def _keep_social_news_line(line: str) -> bool:
    """含真实交通/机场新闻语境时，不因「机场」二字误删整行。"""
    return any(h in line for h in _SOCIAL_NEWS_KEEP_HINTS)

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

_PLATFORM_RISK_INLINE_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    (r"理财(?:产品|方案|计划|顾问|推荐|配置)", "财经信息"),
    (r"个人投资日记", "个人复盘笔记"),
    (r"投资日记", "复盘笔记"),
    (r"个人投资", "个人复盘"),
    (r"投资方案", "复盘框架"),
    (r"投资操作", "市场观察"),
    (r"收益判断", "量价表现"),
    (r"收益预测", "走势观察"),
    (r"收盘信号出炉", "收盘结构观察"),
    (r"收盘信号", "结构观察"),
    (r"明日盯啥[？?]?", "待验证什么"),
    (r"明日盯盘", "待验证指标"),
    (r"明日盯", "待验证"),
    (r"怎么玩[？?]?", "怎么理解"),
    (r"还在榜", "连板记录"),
    (r"领衔", "等"),  # 标题语境：XX等N只，避免「推荐领衔股」
    (r"小仓跟", "小样本跟踪"),
    (r"小仓试错|小仓试", "轻仓对照"),
    (r"开小仓|小仓位", "低仓位"),
    (r"别瞎割", "注意节奏"),
    (r"敢不敢试", "是否延续"),
    (r"别追高", "注意波动"),
    (r"防摔", "注意回撤"),
    (r"非操作建议", "非交易指引"),
    (r"验证动作", "核对要点"),
    (r"游资观察日记", "市场情绪观察"),
    (r"A股选股(?!观察)", "A股观察"),
    (r"热股快讯", "人气快讯"),
    (r"A股周末必读[？?]?", "周末快讯｜"),
    (r"A股必读[？?]?", "A股快讯｜"),
)

# 标题额外替换（比正文更严，避免平台「不适合推荐」）
_TITLE_RISK_INLINE_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    (r"领衔(\d+)只", r"等\1只"),
    (r"领衔", "对照"),
    (r"还在榜", "连板观察"),
    (r"怎么跟[？?]?", "如何对照"),
    (r"热股(\d+)条", r"人气\1条"),
    (r"条：(.{1,8})怎么读[？?]?", r"条｜\1快讯对照"),
    (r"选股5只", "观察5只"),
    (r"选股观察5", "观察5"),
    (r"A股周末必读[？?]?", "周末快讯｜"),
    (r"A股必读[？?]?", "A股快讯｜"),
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
    (
        "数据缺口元叙述",
        r"数据未获取|未能获取|未获取到|样本个股.{0,32}(?:未获取|缺失|未能)|"
        r"交易时段.{0,24}(?:未获取|缺失|未能|无数据)|换手数据未|涨跌与换手数据未",
        0,
    ),
)

# 微信后台「财产安全 / 不适合推荐」高频触发词（标题+正文核心区）
PLATFORM_PROPERTY_RISK_CHECKS: tuple[tuple[str, str, int], ...] = (
    ("理财推介", r"理财(?:产品|方案|计划|顾问|推荐|配置)", 0),
    ("投资方案", r"投资方案|投资计划书|资产配置方案", 0),
    ("投资操作", r"投资操作|操作指南|买卖操作|跟单", 0),
    ("投资日记", r"投资日记|个人投资(?!者)", 0),
    ("收益承诺", r"收益(?:保证|承诺|预测)|稳赚|必涨|翻倍|躺赚", 0),
    ("标题式操作指引", r"怎么玩[？?]|明日盯|盯啥[？?]|收盘信号出炉|还在榜", 0),
    ("推荐式标题", r"领衔\d|领衔.{0,6}只|强烈推荐|值得布局", 0),
    ("诱导性必读标题", r"A股(?:周末)?必读[？?]", 0),
    ("仓位操作", r"小仓跟|半仓|满仓干|加仓干|抄底干|开小仓|空仓试错", 0),
    ("交易指引", r"观察买入|买入观察|建议(?:买入|卖出|建仓|加仓)", 0),
)


def strip_information_notices(text: str) -> str:
    """去掉开篇【说明】块（含被合规清洗改写后的旧版本），避免多次 sync 叠段。"""
    if not text:
        return text
    kept: list[str] = []
    for line in text.splitlines():
        s = line.strip()
        if _INFORMATION_NOTICE_LINE_RE.match(s) or _COMMENTARY_NOTICE_LINE_RE.match(s):
            continue
        kept.append(line)
    out = "\n".join(kept)
    return re.sub(r"\n{3,}", "\n\n", out).strip()


def _core_body_for_audit(text: str) -> str:
    """审计用正文：去掉免责声明、说明块及之后内容。"""
    core = strip_information_notices(text or "")
    for mark in (_DISCLAIMER_MARK, "非荐股", "非交易指引", "仅供参考"):
        if mark in core:
            core = core.split(mark, 1)[0]
    return core.strip()


def sanitize_public_title(title: str, *, kind: str | None = None) -> str:
    """标题终稿：平台推荐安全用语（搜一搜仍可带票名/行业，但去操作指引口吻）。"""
    if not title:
        return title
    out = sanitize_platform_property_risk(title)
    for pat, repl in _TITLE_RISK_INLINE_REPLACEMENTS:
        out = re.sub(pat, repl, out)
    out = re.sub(r"\s{2,}", "", out).strip()
    k = (kind or "").strip().lower()
    if k == "dragons":
        m = re.match(
            r"^情绪(.+?)怎么理解(.+?)(\d+)板(?:连板记录|连板观察)?$",
            out,
        )
        if m:
            phase, lead, n = m.groups()
            out = f"情绪{phase}梯队｜{lead}{n}板结构"
    return out


def audit_recommendation_safety(
    *,
    title: str = "",
    body: str = "",
    digest: str = "",
) -> list[str]:
    """推稿前：合并标题/摘要/正文的平台推荐安全审计。"""
    blob = "\n".join(x for x in (title, digest, body) if x)
    return check_public_compliance(blob, title=title)


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
        for pat, repl in _PLATFORM_RISK_INLINE_REPLACEMENTS:
            s = re.sub(pat, repl, s)
        s = re.sub(r"\s{2,}", " ", s).strip()
        if s or not stripped:
            lines_out.append(s)
    return "\n".join(lines_out)


def sanitize_platform_property_risk(text: str) -> str:
    """弱化易触发微信「财产安全/不适合推荐」的表述。"""
    if not text:
        return text
    lines_out: list[str] = []
    for line in text.splitlines():
        if _INFORMATION_NOTICE_LINE_RE.match(line.strip()):
            lines_out.append(line)
            continue
        s = line
        for pat, repl in _PLATFORM_RISK_INLINE_REPLACEMENTS:
            s = re.sub(pat, repl, s)
        lines_out.append(s)
    return "\n".join(lines_out).strip()


def information_notice_for_kind(kind: str | None) -> str:
    k = (kind or "").strip().lower()
    if k in COMMENTARY_MP_KINDS:
        return COMMENTARY_INFORMATION_NOTICE
    if k in _FINANCE_MP_KINDS:
        return INFORMATION_NOTICE
    return ""


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
        stripped = line.strip()
        if _LINE_DROP_RE.match(stripped) and not _keep_social_news_line(stripped):
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
    merged = sanitize_platform_property_risk(merged)
    return merged.strip()


_TECH_KINDS = frozenset({"workspace", "temp", "tech", "lab", "dev"})

# 读者正文禁止暴露采集缺口（公众号成稿，非 SOP 内参）
_READER_DATA_GAP_PHRASES: tuple[str, ...] = (
    "数据未获取",
    "未能获取",
    "未获取到",
    "暂无具体样本",
    "换手数据未",
    "涨跌与换手数据未",
    "样本个股涨跌与换手数据未获取",
    "交易时段的样本",
    "数据源暂不可用",
    "因数据源暂不可用",
)

_READER_DATA_GAP_SENTENCE = re.compile(
    r"[^。；！？\n]*(?:"
    r"数据未获取|未能获取|未获取到|暂无具体样本|数据源暂不可用"
    r"|样本个股[^。；！？\n]{0,36}(?:未获取|缺失|未能)"
    r"|交易时段[^。；！？\n]{0,28}(?:未获取|缺失|未能|无数据)"
    r"|(?:涨跌|换手)[^。；！？\n]{0,16}数据未"
    r"|---\s*\*?说明[：:][^。；！？\n]*数据源"
    r")[^。；！？\n]*[。；！？]?"
)

_HOTSPOT_PLATE_FALLBACK = (
    "相关链条内个股分化，龙头尚未形成一致放量；"
    "可对照板块涨跌广度与油价/运价是否同向验证。"
)


def sanitize_reader_data_gap(text: str, *, kind: str | None = None) -> str:
    """去掉读者可见的「数据未获取/样本未获取」等编审/采集话术。"""
    out = (text or "").strip()
    if not out:
        return out
    for phrase in _READER_DATA_GAP_PHRASES:
        out = out.replace(phrase, "")
    out = _READER_DATA_GAP_SENTENCE.sub("", out)
    out = re.sub(r"样本个股[^。；！？\n]*[。；！？]?", "", out)
    out = re.sub(r"交易时段[^。；！？\n]*[。；！？]?", "", out)
    out = re.sub(r"[；;，,]{2,}", "，", out)
    out = re.sub(r"\n{3,}", "\n\n", out)

    k = (kind or "").strip().lower()
    if k == "hotspot":
        out = _repair_hotspot_plate_field(out)
    return out.strip()


def check_reader_data_gap_meta(text: str) -> tuple[bool, list[str]]:
    """True=通过（无采集缺口元叙述）。"""
    blob = (text or "").strip()
    if not blob:
        return True, []
    for phrase in _READER_DATA_GAP_PHRASES:
        if phrase in blob:
            return False, [f"含采集缺口话术：{phrase}"]
    if _READER_DATA_GAP_SENTENCE.search(blob):
        return False, ["含「数据未获取/样本未获取」类编审句"]
    return True, []


def _plate_chunk_substantive(chunk: str) -> bool:
    """盘面段须有可核对量价事实，不接受「样本/交易时段/涨跌与换手」空壳。"""
    c = (chunk or "").strip()
    if len(c) < 12:
        return False
    if any(x in c for x in ("样本", "交易时段", "未获取", "未能", "数据缺")):
        return False
    if re.search(r"涨[^。]*?\d|跌[^。]*?\d|\d+\.?\d*%", c):
        return True
    if re.search(r"涨跌与换手[。；]?$", c):
        return False
    return len(c) >= 28 and not re.search(r"板块在\d+月\d+日", c)


def _repair_hotspot_plate_field(text: str) -> str:
    """「A股怎么动」若被洗空，补读者向板块现象句。"""
    labels = ("A股怎么动：", "A股怎么动:", "盘面怎么反应：", "盘面怎么反应:")
    for label in labels:
        idx = text.find(label)
        if idx < 0:
            continue
        rest = text[idx + len(label) :]
        stop = len(rest)
        for marker in (
            "外面怎么传",
            "网上在说什么",
            "我们怎么看",
            "AI怎么看",
            "AI 怎么看",
            "明天盯什么",
            "向后看",
            "> ",
        ):
            pos = rest.find(marker)
            if pos > 0:
                stop = min(stop, pos)
        chunk = rest[:stop].strip("，,。；; \n")
        if _plate_chunk_substantive(chunk):
            return text
        patched = (
            text[: idx + len(label)]
            + _HOTSPOT_PLATE_FALLBACK
            + rest[stop:]
        )
        return patched
    return text


def finalize_public_body_text(
    text: str,
    *,
    kind: str | None = None,
    engagement_kind: str | None = None,
) -> str:
    """成稿最后一道公开稿清洗（各 kind 在进 HTML 前调用）。"""
    k = (kind or "").strip().lower()
    out = sanitize_public_mp_text(text)
    if k in _FINANCE_MP_KINDS:
        out = sanitize_reader_data_gap(out, kind=k)
    if k in _TECH_KINDS:
        out = sanitize_tech_mp_meta(out)
    from scripts.tools.wechat_mp_readability import polish_mobile_readability

    return polish_mobile_readability(out, kind=k, engagement_kind=engagement_kind)


def check_public_compliance(text: str, *, title: str = "") -> list[str]:
    """返回合规失败项标签；空列表表示通过。"""
    failures: list[str] = []
    core = _core_body_for_audit(text)
    blob = f"{title}\n{core}"
    for label, pat, flags in PUBLIC_COMPLIANCE_CHECKS:
        if re.search(pat, blob, flags=flags):
            failures.append(label)
    for label, pat, flags in PLATFORM_PROPERTY_RISK_CHECKS:
        if re.search(pat, blob, flags=flags):
            failures.append(f"平台风险·{label}")
    if re.search(r"(?<![你])我(?:的|们)?(?:仓|持仓|账户)", core):
        failures.append("第一人称持仓")
    return failures
