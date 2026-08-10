#!/usr/bin/env python3
"""公众号龙头稿：情绪周期 + 东财 SOP（最多 3 只）+ 交易员视角成稿。"""

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.analysis.eastmoney_sop_extract import build_fast_preliminary_report
from scripts.tools.deepseek_client import call_wechat_mp_llm, is_wechat_mp_llm_configured
from scripts.tools.portfolio_db import load_stock_names_by_codes
from scripts.tools.wechat_mp_public import PUBLIC_MP_WRITER_RULE, RESEARCHER_VOICE_RULE, PLATFORM_PROPERTY_RISK_RULE
from scripts.tools.wechat_mp_monetization import monetization_prompt_block

TZ = ZoneInfo("Asia/Shanghai")
ROOT = Path(__file__).resolve().parents[2]
# 公众号龙头稿专用缓存（与 output/sop_preliminary Top5/单股 SOP 隔离）
SOP_CACHE_ROOT = ROOT / "output" / "wechat_mp_dragon_sop"


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name) or default)
    except ValueError:
        return default


def _env_bool(name: str, default: bool = True) -> bool:
    raw = os.getenv(name, "").strip().lower()
    if not raw:
        return default
    return raw not in ("0", "false", "no", "off")


def dragon_sop_enabled() -> bool:
    return _env_bool("WECHAT_MP_DRAGON_SOP", True)


def dragon_sop_max() -> int:
    return max(1, min(3, _env_int("WECHAT_MP_DRAGON_SOP_MAX", 3)))


def dragons_write_max() -> int:
    """正文「龙头拆解」深度写的只数（默认 2，利于完读与搜一搜）。"""
    return max(1, min(3, _env_int("WECHAT_MP_DRAGON_WRITE_MAX", 2)))


def dragon_sop_cache_hours() -> float:
    try:
        return float(os.getenv("WECHAT_MP_DRAGON_SOP_CACHE_HOURS", "12"))
    except ValueError:
        return 12.0


def dragon_sop_wait_seconds() -> float:
    try:
        return float(os.getenv("WECHAT_MP_DRAGON_SOP_WAIT", "1.5"))
    except ValueError:
        return 1.5


def _sop_cache_dir(trade_date: str) -> Path:
    return SOP_CACHE_ROOT / trade_date[:10]


def _cache_paths(code: str, trade_date: str) -> tuple[Path, Path]:
    d = _sop_cache_dir(trade_date)
    return d / f"{code}_fast.md", d / f"{code}_technical.txt"


def _load_sop_cache(code: str, trade_date: str) -> tuple[str, str] | None:
    prelim_path, tech_path = _cache_paths(code, trade_date)
    if not prelim_path.is_file():
        return None
    age_h = (time.time() - prelim_path.stat().st_mtime) / 3600.0
    if age_h > dragon_sop_cache_hours():
        return None
    prelim = prelim_path.read_text(encoding="utf-8").strip()
    if not prelim or prelim.startswith("（东财 SOP 未获取"):
        return None
    tech = tech_path.read_text(encoding="utf-8").strip() if tech_path.is_file() else ""
    return prelim, tech


def _save_sop_cache(code: str, trade_date: str, preliminary: str, technical: str) -> None:
    prelim_path, tech_path = _cache_paths(code, trade_date)
    prelim_path.parent.mkdir(parents=True, exist_ok=True)
    prelim_path.write_text(preliminary, encoding="utf-8")
    tech_path.write_text(technical or "（未获取）", encoding="utf-8")


def _fetch_dragon_sop_fast(codes: list[str]) -> tuple[dict[str, str], dict[str, str], str]:
    """公众号专用快采（行情+资金+K线），不调用八维度 F10、不写 sop_preliminary。"""
    from scripts.tools.fetch_eastmoney_quotes import (
        fetch_sop_snapshots,
        fetch_technical_summaries_batch_opencli,
    )

    wait = dragon_sop_wait_seconds()
    prelim_map: dict[str, str] = {}
    snaps = fetch_sop_snapshots(
        codes,
        wait_seconds=wait,
        close_browser=False,
        reset_browser=True,
    )
    tech_map = fetch_technical_summaries_batch_opencli(
        codes,
        reset_browser=False,
        close_browser=True,
    )
    for code in codes:
        snap = snaps.get(code)
        if not snap:
            continue
        tech = tech_map.get(code) or "（技术面补充未获取）"
        prelim_map[code] = build_fast_preliminary_report(code, snap, technical=tech)
    return prelim_map, tech_map, ""


def _truncate(text: str, limit: int = 3800) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text or "（无）"
    return text[:limit] + "\n…（下文已截断）"


def _fmt_hdr_val(label: str, val: Any) -> str:
    if val is None or val == "":
        return ""
    return f"· {label}：{val}"


def build_metrics_block(hdr: dict[str, Any]) -> str:
    metrics = [
        _fmt_hdr_val("情绪阶段", hdr.get("phase")),
        _fmt_hdr_val("较昨日", hdr.get("phase_vs_yesterday")),
        _fmt_hdr_val("主线题材", hdr.get("main_theme")),
        _fmt_hdr_val("涨停/跌停", f"{hdr.get('limit_up_count')}/{hdr.get('limit_down_count')}"),
        _fmt_hdr_val("涨跌比", hdr.get("up_down_ratio")),
        _fmt_hdr_val("连板高度", hdr.get("max_board_height")),
        _fmt_hdr_val("炸板率", hdr.get("explode_rate_pct")),
        _fmt_hdr_val("全A成交额(亿)", hdr.get("total_amount_yi")),
        _fmt_hdr_val("情绪风控仓位参考(%)", hdr.get("position_cap_pct")),
        _fmt_hdr_val("动作", hdr.get("action_summary")),
    ]
    return "\n".join(x for x in metrics if x)


def _trade_date_str(hdr: dict[str, Any]) -> str:
    td = hdr.get("trade_date")
    if isinstance(td, date):
        return td.isoformat()
    return str(td)[:10]


@dataclass
class DragonSopPack:
    rank: int
    code: str
    name: str
    boards: Any
    theme: str
    checklist_pass: Any
    notes: str
    preliminary: str
    technical: str
    sop_ok: bool


def _resolve_dragons(
    dragons: list[dict[str, Any]],
    hdr: dict[str, Any],
    *,
    limit: int,
) -> list[dict[str, Any]]:
    ordered = sorted(dragons, key=lambda d: int(d.get("rank_no") or 99))
    return ordered[:limit]


def collect_dragon_sop_packages(
    dragons: list[dict[str, Any]],
    hdr: dict[str, Any],
    *,
    limit: int | None = None,
) -> list[DragonSopPack]:
    """公众号专用东财快采 + 技术面；缓存目录独立，不影响 Top5/单股八维度 SOP。"""
    limit = limit or dragon_sop_max()
    picked = _resolve_dragons(dragons, hdr, limit=limit)
    if not picked:
        return []

    codes = [
        str(d.get("ts_code") or d.get("code") or "").split(".")[0].zfill(6) for d in picked
    ]
    name_map = load_stock_names_by_codes(codes)
    td_s = _trade_date_str(hdr)

    prelim_by_code: dict[str, str] = {}
    tech_by_code: dict[str, str] = {}
    sop_err = ""

    if dragon_sop_enabled():
        need_fetch: list[str] = []
        for code in codes:
            cached = _load_sop_cache(code, td_s)
            if cached:
                prelim_by_code[code], tech_by_code[code] = cached
            else:
                need_fetch.append(code)
        if need_fetch:
            try:
                fresh_prelim, fresh_tech, sop_err = _fetch_dragon_sop_fast(need_fetch)
                for code in need_fetch:
                    prelim = fresh_prelim.get(code, "")
                    tech = fresh_tech.get(code) or "（技术面补充未获取）"
                    if prelim:
                        prelim_by_code[code] = prelim
                        tech_by_code[code] = tech
                        _save_sop_cache(code, td_s, prelim, tech)
            except Exception as exc:  # noqa: BLE001
                sop_err = str(exc)

    packs: list[DragonSopPack] = []
    for d in picked:
        code = str(d.get("ts_code") or "").split(".")[0].zfill(6)
        name = (d.get("name") or "").strip() or name_map.get(code) or code
        preliminary = prelim_by_code.get(code, "")
        technical = tech_by_code.get(code) or "（技术面补充未获取）"
        if preliminary and not preliminary.startswith("（东财 SOP 未获取"):
            sop_ok = True
        else:
            preliminary = (
                f"（东财 SOP 未获取：{sop_err or '页面无数据'}）\n"
                f"池内备注：{(d.get('notes') or '').strip() or '无'}"
            )
            sop_ok = False
        packs.append(
            DragonSopPack(
                rank=int(d.get("rank_no") or len(packs) + 1),
                code=code,
                name=name,
                boards=d.get("board_height"),
                theme=str(d.get("main_theme") or hdr.get("main_theme") or ""),
                checklist_pass=d.get("checklist_pass"),
                notes=str(d.get("notes") or "").strip(),
                preliminary=preliminary,
                technical=technical,
                sop_ok=sop_ok,
            )
        )
    return packs


_DRAGON_PUBLIC_BANNED = """
【筛选用分】checklist_pass（X/7）为情绪周期脚本内部计数，**禁止**出现在公众号正文、标题、摘要。
禁止写法：6/7、7/7、X/7、系统筛选用分、龙头确认、内部认可、系统认可、值得推荐、可买 等。
正文只写连板高度、板块地位、量价与博弈结构。
"""


def _sop_context_blob(packs: list[DragonSopPack]) -> str:
    if not packs:
        return "（龙头池为空，无 SOP 数据）"
    chunks: list[str] = []
    for p in packs:
        boards_s = f"{p.boards}板" if p.boards is not None else "连板未知"
        chunks.append(
            f"### {p.rank}. {p.name}（{p.code}）\n"
            f"池内标签：{boards_s}，主线 {p.theme or '—'}\n"
            f"池内备注：{p.notes or '无'}\n"
            f"技术面（OpenCLI）：\n{_truncate(p.technical, 1200)}\n"
            f"东财 SOP 初步报告：\n{_truncate(p.preliminary, 3600)}"
        )
    return "\n\n".join(chunks)


_DRAGON_CHECKLIST_BAD_RE = re.compile(
    r"(?:内部(?:系统)?(?:认可|确认)|系统认可|龙头确认(?:通过|满分)?|"
    r"系统筛选用分|值得推荐|值得跟踪买入|可(?:以)?(?:买入|关注)|通过确认)"
)

_DRAGON_SCORE_FRACTION_RE = re.compile(
    r"(?:系统筛选用分\s*)?\d+\s*/\s*7(?:\s*[（(][^）)]*[）)])?"
)
# 标题句式误入正文（LLM 常把「情绪发酵怎么玩？XX5板还在榜」写在「情绪与盘面」前）
_DRAGON_TITLE_ECHO_RE = re.compile(
    r"^[\s>]*.{0,14}怎么玩[？?].*(?:还在榜|还在线)"
)
_DRAGON_TITLE_ECHO_LOOSE_RE = re.compile(
    r"^[\s>]*(?:情绪|A股龙头|连板梯队|情绪周期).*(?:怎么玩|还在榜)"
)


def _normalize_title_echo_line(line: str) -> str:
    s = re.sub(r"^[\s>]+", "", (line or "").strip())
    s = re.sub(r"[！!？?，,。.\s｜|]", "", s)
    return s


def strip_dragon_title_echo(text: str, *, title: str = "") -> str:
    """去掉正文中误贴的公众号龙头标题句式（与 `_dragon_title` 生成的标题同构）。"""
    if not text:
        return text
    title_norm = _normalize_title_echo_line(title) if title else ""
    out: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            out.append(raw)
            continue
        if title_norm and _normalize_title_echo_line(line) == title_norm:
            continue
        if _DRAGON_TITLE_ECHO_RE.match(line):
            continue
        if _DRAGON_TITLE_ECHO_LOOSE_RE.match(line) and (
            "怎么玩" in line or "还在榜" in line
        ):
            continue
        out.append(raw)
    merged = "\n".join(out)
    # 正文须以「> 情绪与盘面」起笔；其前的标题 echo 行一并剔除
    marker = "> 情绪与盘面"
    if marker in merged:
        head, tail = merged.split(marker, 1)
        head_lines = [ln for ln in head.splitlines() if ln.strip()]
        if head_lines and all(
            _DRAGON_TITLE_ECHO_RE.match(ln.strip())
            or _DRAGON_TITLE_ECHO_LOOSE_RE.match(ln.strip())
            or (title_norm and _normalize_title_echo_line(ln) == title_norm)
            for ln in head_lines
        ):
            merged = marker + tail
    return re.sub(r"\n{3,}", "\n\n", merged).strip()


def sanitize_dragons_public_text(text: str) -> str:
    """龙头公开稿：剔除 X/7 筛选用分及内部认可类表述。"""
    from scripts.tools.wechat_mp_public import finalize_public_body_text, sanitize_public_mp_text

    cleaned = sanitize_public_mp_text(text or "")
    cleaned = finalize_public_body_text(cleaned)
    out: list[str] = []
    for raw in cleaned.splitlines():
        line = raw
        line = _DRAGON_SCORE_FRACTION_RE.sub("", line)
        line = re.sub(r"龙头确认\s*\d+\s*/\s*7", "", line)
        line = _DRAGON_CHECKLIST_BAD_RE.sub("", line)
        line = re.sub(r"[，,；;：:]\s*[，,；;：:]", "，", line)
        line = re.sub(r"\s{2,}", " ", line).strip()
        line = line.strip("，,；;：:")
        if line:
            out.append(line)
    merged = "\n".join(out)
    merged = re.sub(r"\n{3,}", "\n\n", merged)
    return merged.strip()


def _plan_context(hdr: dict[str, Any]) -> str:
    """情绪周期库内字段；成稿时须改写成公开市场语言，不得照搬第一人称计划。"""
    parts: list[str] = []
    if hdr.get("tomorrow_plan"):
        parts.append(f"盘面跟踪要点（库）：{hdr['tomorrow_plan']}")
    if hdr.get("review_notes"):
        parts.append(f"复盘摘要（库）：{hdr['review_notes']}")
    if hdr.get("exclude_list"):
        parts.append(f"回避方向（库）：{hdr['exclude_list']}")
    return "\n".join(parts) if parts else "（无单独计划字段）"


def _template_trader_body(
    *,
    hdr: dict[str, Any],
    metrics_block: str,
    packs: list[DragonSopPack],
    td_s: str,
    slot_label: str,
) -> str:
    """无 LLM 时的交易员体例（仍避免逐条照搬 SOP 原文）。"""
    phase = hdr.get("phase") or "—"
    theme = hdr.get("main_theme") or "—"
    lines = [
        "> 情绪与盘面",
        f"数据日 {td_s}（{slot_label}）",
        "",
        metrics_block,
        "",
        (
            f"盘面定性：情绪处于「{phase}」阶段，主线围绕 {theme}。"
            "涨停家数、炸板率与涨跌比需结合看——高炸板率说明接力意愿不足，"
            "此时高位龙头更宜观察分歧而非盲目追涨。"
        ),
        "",
        "> 龙头拆解",
    ]
    if not packs:
        lines.append("今日龙头池为空，暂无逐只拆解。")
    else:
        for p in packs:
            boards_s = f"{p.boards}板" if p.boards is not None else "高度待核"
            lines.append(f"{p.rank}. {p.name}（{p.code}）")
            lines.append(
                f"   地位：{boards_s}，{p.theme or '主线待核'}方向池内标的。"
            )
            if p.sop_ok:
                snippet = _first_nonempty_line(p.preliminary, min_len=12)
                lines.append(
                    f"   量价资金：{snippet[:120]}…（完整 SOP 已采集，待 LLM 成稿）"
                    if len(snippet) > 120
                    else f"   量价资金：{snippet or '见东财采集'}"
                )
            else:
                lines.append("   量价资金：东财 SOP 未获取，仅依据池内标签跟踪。")
            lines.append(
                "   博弈：高位接力需量能与板块共振；分歧日关注换手与回封质量，"
                "结构不满足时情绪易退潮。"
            )
            lines.append("   待核实：次日核对量能、板块联动与龙头地位是否仍成立。")
            lines.append("")

    lines.extend(
        [
            "> 主线与梯队",
            (
                f"当前主线 {theme}：龙头负责打开空间，补涨与跟风决定持续性。"
                "若龙头断板而跟风仍强，多为轮动而非新周期；若全线退潮，应收缩试错仓位。"
            ),
            "",
            "> 明日计划与纪律",
            _plan_context(hdr),
            "",
            "纪律：单日涨幅超 5% 不追；炸板率抬升时减少高位接力；参考情绪风控仓位，控制试错仓位。",
        ]
    )
    return "\n".join(lines)


def _first_nonempty_line(text: str, *, min_len: int = 8) -> str:
    for line in text.splitlines():
        s = line.strip()
        if len(s) >= min_len and not s.startswith(("#", "```", "---")):
            s = re.sub(r"^[\-*\d.]+\s*", "", s)
            if s:
                return s
    return ""


def generate_dragons_trader_body(
    bundle: dict[str, Any],
    *,
    checklist_slot: str | None = None,
) -> str:
    """生成龙头公众号正文（交易员视角，非网页搬运）。"""
    hdr = bundle["header"]
    dragons = bundle.get("dragon_items") or []
    slot_label = (checklist_slot or hdr.get("checklist_slot") or "eod").strip()
    td_s = _trade_date_str(hdr)
    metrics_block = build_metrics_block(hdr)

    packs_all = collect_dragon_sop_packages(dragons, hdr) if dragons else []
    write_n = min(len(packs_all), dragons_write_max())
    packs = packs_all[:write_n]
    sop_blob = _sop_context_blob(packs)
    plan_ctx = _plan_context(hdr)
    align = ""
    try:
        from scripts.tools.wechat_mp_evening_align import sector_alignment_prompt_block

        align = sector_alignment_prompt_block()
    except Exception:
        align = ""

    if not is_wechat_mp_llm_configured():
        return sanitize_dragons_public_text(
            _template_trader_body(
                hdr=hdr,
                metrics_block=metrics_block,
                packs=packs,
                td_s=td_s,
                slot_label=slot_label,
            )
        )

    n = len(packs)
    pool_extra = ""
    if len(packs_all) > n:
        names = "、".join(f"{p.name}{p.boards}板" if p.boards else p.name for p in packs_all[n:])
        pool_extra = f"\n（池内另有 {names}，仅在「主线与梯队」一句带过，**勿**在「龙头拆解」展开。）"
    prompt = f"""你是有 10 年经验的 A 股情绪周期与龙头策略研究员，为微信公众号撰写「龙头跟踪」盘后观察稿。
读者是活跃交易者：用博弈框架写清梯队与情绪位置，语言偏研究备忘录，不是游资喊单体。
{PUBLIC_MP_WRITER_RULE}
{RESEARCHER_VOICE_RULE}
{PLATFORM_PROPERTY_RISK_RULE}
{_DRAGON_PUBLIC_BANNED}
{align}

## 数据日与时段
{td_s}（{slot_label}）

## 情绪周期指标
{metrics_block}

## 龙头池（共 {len(dragons)} 只，本次须拆解前 {n} 只）
{chr(10).join(
    f"- {p.rank}. {p.name}（{p.code}）"
    + (f" {p.boards}板" if p.boards is not None else "")
    for p in packs
) or "- （池为空）"}

## 东财 SOP + 技术面（事实来源，禁止大段粘贴原文）
{sop_blob}

## 情绪周期库内备注（须改写成第三人称市场语言，勿写成作者个人计划；勿把「库内」写成「内部认可」）
{plan_ctx}

## 输出结构（严格按节，禁止 emoji、禁止 markdown 表格、禁止「研究员札记 |」；**小标题禁止「一、二、三」序号**，只用 `> 标题`）
> 情绪与盘面
（**开篇 2～3 句必须含至少 2 个数字**：涨停/跌停、炸板率、涨跌比、连板高度等；**可补 1 句宏观流动性或政策预期对情绪的影响**（公开信息）；再写 1～2 短段解读接力环境；总篇幅控制在 4 段以内，不给买卖意见）

> 龙头拆解
（**仅**前 {n} 只独立 4 行块，标题行格式必须为「1. 股票名（000001）」；每只「量价资金」≤3 句）
地位：（连板高度、板块核心度、与主线关系；禁止写 X/7 或筛选用分）
量价资金：（从 SOP/技术面提炼主力、换手、关键价位，写事实不写原文）
博弈：（追涨/分歧/兑现风险，结构描述）
待核实：（还缺哪些结构信息，禁止观察买入/内部认可类措辞）

> 主线与梯队
（板块联动、补涨与跟风、龙头断板后的结构变化）

> 明日计划与纪律
（盘面跟踪要点 + 通用纪律表述，禁止个人仓位计划）

## 硬性要求
1. 必须覆盖龙头池中前 {n} 只（不足 {n} 只则全覆盖）；SOP 缺失的标的注明「数据未获取」但仍给结构推演
2. 禁止逐段复述东财网页原文；每条「量价资金」不超过 3 句
3. 禁止投资建议、内部认可、系统认可、推荐买入；**禁止**「龙头确认」及 **任何 X/7 筛选用分**
4. 全文 **650～1100 字**（短于旧版，优先完读率），中文，只使用上文数据，勿编造数字
5. **移动端排版**：叙述段每段约 120 字内；`1. 2. 3.` 列表每项单独一行，禁止同一行多个序号
6. **标题由系统单独生成**；正文禁止出现「情绪XX怎么玩？XXN板还在榜」或与之同构的问句
7. 「情绪与盘面」开篇只写数据日、涨停/炸板率等数字事实，勿写标题党钩子
8. 「龙头拆解」只写前 {n} 只；其余标的仅在「主线与梯队」一句点名{pool_extra}
{monetization_prompt_block("dragons")}"""

    try:
        content = call_wechat_mp_llm(
            [
                {
                    "role": "system",
                    "content": (
                        "你是情绪周期与龙头策略研究员，文风干脆、有盘感但有论证链条。"
                        "从 SOP 数据里提炼结论，绝不粘贴网页。"
                        "面向公开读者，禁止作者持仓与第一人称仓位。"
                        "禁止正文出现 X/7、系统筛选用分、龙头确认、内部认可。"
                        "小标题用 `> 标题`，禁止「一、二、三」序号。"
                        "输出直接从「> 情绪与盘面」开始。"
                        "禁止把公众号标题句式写进正文首段。"
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.35,
            max_tokens=3200,
            timeout=(10, 240),
        )
        return sanitize_dragons_public_text(strip_dragon_title_echo(content.strip()))
    except Exception as exc:  # noqa: BLE001
        base = _template_trader_body(
            hdr=hdr,
            metrics_block=metrics_block,
            packs=packs,
            td_s=td_s,
            slot_label=slot_label,
        )
        return sanitize_dragons_public_text(
            f"{base}\n\n（交易员成稿失败：{exc}，以上为模板正文）"
        )
