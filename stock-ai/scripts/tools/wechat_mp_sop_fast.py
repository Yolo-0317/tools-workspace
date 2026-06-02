"""公众号专用东财快采（与 output/sop_preliminary 隔离）。"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.analysis.eastmoney_sop_extract import build_fast_preliminary_report

ROOT = Path(__file__).resolve().parents[2]


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


@dataclass(frozen=True)
class WechatSopProfile:
    cache_dir_name: str
    enabled_env: str
    max_env: str
    cache_hours_env: str
    wait_env: str
    default_max: int


DRAGON_SOP_PROFILE = WechatSopProfile(
    cache_dir_name="wechat_mp_dragon_sop",
    enabled_env="WECHAT_MP_DRAGON_SOP",
    max_env="WECHAT_MP_DRAGON_SOP_MAX",
    cache_hours_env="WECHAT_MP_DRAGON_SOP_CACHE_HOURS",
    wait_env="WECHAT_MP_DRAGON_SOP_WAIT",
    default_max=3,
)

TOP5_SOP_PROFILE = WechatSopProfile(
    cache_dir_name="wechat_mp_top5_sop",
    enabled_env="WECHAT_MP_TOP5_SOP",
    max_env="WECHAT_MP_TOP5_SOP_MAX",
    cache_hours_env="WECHAT_MP_TOP5_SOP_CACHE_HOURS",
    wait_env="WECHAT_MP_TOP5_SOP_WAIT",
    default_max=5,
)


@dataclass
class WechatSopPack:
    rank: int
    code: str
    name: str
    preliminary: str
    technical: str
    sop_ok: bool
    meta_line: str = ""


def sop_enabled(profile: WechatSopProfile) -> bool:
    return _env_bool(profile.enabled_env, True)


def sop_max(profile: WechatSopProfile) -> int:
    cap = max(1, min(5, profile.default_max))
    return max(1, min(5, _env_int(profile.max_env, cap)))


def sop_cache_hours(profile: WechatSopProfile) -> float:
    try:
        return float(os.getenv(profile.cache_hours_env, "12"))
    except ValueError:
        return 12.0


def sop_wait_seconds(profile: WechatSopProfile) -> float:
    try:
        return float(os.getenv(profile.wait_env, "1.5"))
    except ValueError:
        return 1.5


def _cache_root(profile: WechatSopProfile) -> Path:
    return ROOT / "output" / profile.cache_dir_name


def _cache_paths(profile: WechatSopProfile, code: str, trade_date: str) -> tuple[Path, Path]:
    d = _cache_root(profile) / trade_date[:10]
    return d / f"{code}_fast.md", d / f"{code}_technical.txt"


def load_sop_cache(
    profile: WechatSopProfile, code: str, trade_date: str
) -> tuple[str, str] | None:
    prelim_path, tech_path = _cache_paths(profile, code, trade_date)
    if not prelim_path.is_file():
        return None
    age_h = (time.time() - prelim_path.stat().st_mtime) / 3600.0
    if age_h > sop_cache_hours(profile):
        return None
    prelim = prelim_path.read_text(encoding="utf-8").strip()
    if not prelim or prelim.startswith("（东财 SOP 未获取"):
        return None
    tech = tech_path.read_text(encoding="utf-8").strip() if tech_path.is_file() else ""
    return prelim, tech


def save_sop_cache(
    profile: WechatSopProfile,
    code: str,
    trade_date: str,
    preliminary: str,
    technical: str,
) -> None:
    prelim_path, tech_path = _cache_paths(profile, code, trade_date)
    prelim_path.parent.mkdir(parents=True, exist_ok=True)
    prelim_path.write_text(preliminary, encoding="utf-8")
    tech_path.write_text(technical or "（未获取）", encoding="utf-8")


def fetch_fast_sop(
    profile: WechatSopProfile, codes: list[str]
) -> tuple[dict[str, str], dict[str, str], str]:
    from scripts.tools.fetch_eastmoney_quotes import (
        fetch_sop_snapshots,
        fetch_technical_summaries_batch_opencli,
    )

    wait = sop_wait_seconds(profile)
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


def collect_wechat_sop_packs(
    profile: WechatSopProfile,
    items: list[dict[str, Any]],
    *,
    trade_date: str,
) -> list[WechatSopPack]:
    """items: rank, code, name, meta_line（可选）。"""
    if not items:
        return []

    codes = [str(it["code"]).zfill(6) for it in items]
    prelim_by_code: dict[str, str] = {}
    tech_by_code: dict[str, str] = {}
    sop_err = ""

    if sop_enabled(profile):
        need_fetch: list[str] = []
        for code in codes:
            cached = load_sop_cache(profile, code, trade_date)
            if cached:
                prelim_by_code[code], tech_by_code[code] = cached
            else:
                need_fetch.append(code)
        if need_fetch:
            try:
                fresh_prelim, fresh_tech, sop_err = fetch_fast_sop(profile, need_fetch)
                for code in need_fetch:
                    prelim = fresh_prelim.get(code, "")
                    tech = fresh_tech.get(code) or "（技术面补充未获取）"
                    if prelim:
                        prelim_by_code[code] = prelim
                        tech_by_code[code] = tech
                        save_sop_cache(profile, code, trade_date, prelim, tech)
            except Exception as exc:  # noqa: BLE001
                sop_err = str(exc)

    packs: list[WechatSopPack] = []
    for it in items:
        code = str(it["code"]).zfill(6)
        preliminary = prelim_by_code.get(code, "")
        technical = tech_by_code.get(code) or "（技术面补充未获取）"
        if preliminary and not preliminary.startswith("（东财 SOP 未获取"):
            sop_ok = True
        else:
            preliminary = (
                f"（东财 SOP 未获取：{sop_err or '页面无数据'}）\n"
                f"选股备注：{it.get('meta_line') or '无'}"
            )
            sop_ok = False
        packs.append(
            WechatSopPack(
                rank=int(it.get("rank") or len(packs) + 1),
                code=code,
                name=str(it.get("name") or code),
                preliminary=preliminary,
                technical=technical,
                sop_ok=sop_ok,
                meta_line=str(it.get("meta_line") or ""),
            )
        )
    return packs
