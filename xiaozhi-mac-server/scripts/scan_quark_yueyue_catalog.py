#!/usr/bin/env python3
"""Scan Quark Drive (玥玥 folder) and build quark_content_aliases.json."""

from __future__ import annotations

import hashlib
import json
import re
import time
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parent
HERMES_CONFIG = WORKSPACE / ".cursor/skills/quarkclouddrive/hermes/config.json"
ALIASES_PATH = ROOT / "data/quark_content_aliases.json"
REPORT_PATH = ROOT / "data/quark_yueyue_scan_report.json"

YUEYUE = "玥玥"
BBC = "002.BBC英语动画【小优趣系列精选20部】"
BBC_PREFIX = f"{YUEYUE}/{BBC}"

_CLIENT_ID = "third_party_agent"
_SIGN_KEY = "cf134812e2de4032bd1cb7c3727e84b3"
_API_BASE = "https://open-api-drive.quark.cn"

# Folder discovery seeds (Quark search needs meaningful keywords, not bare "11-").
FOLDER_SEEDS = [
    "玥玥",
    "002.BBC",
    "小优趣",
    "11-积木",
    "12-儿童",
    "10- 高清版Big",
    "15-雨果",
    "06.儿歌",
    "19 - 小贝",
    "06- BBC数字积木",
    "07- 阅读树",
    "01-开口",
    "09-蓝色",
    "03-布鲁伊",
    "Numberblocks",
    "Alphablocks",
    "Abadas",
    "Muzzy",
    "Steve and Maggie",
    "Magic Key",
    "神奇之钥",
    "Bitz",
    "Penelope",
    "Yakka",
    "Bluey",
    "冰雪奇缘",
    "哈利波特",
    "童老师",
    "牛津树",
    "ORT",
    "Susan教英语",
    "微观小世界",
    "昆虫总动员",
    "小猪佩奇",
    "Peppa",
    "Maisy",
]

# Hand-curated playable mappings (path segments under 玥玥/).
CATALOG_SPECS: list[dict[str, Any]] = [
    {
        "key": "abadas",
        "title": "Abadas 儿童学单词",
        "aliases": ["abadas", "阿巴达斯"],
        "path_hint": f"{BBC_PREFIX}/12-儿童学习单词 Abadas【BBC系列】",
        "search_queries": ["Abadas mp3", "儿童学习单词 Abadas 音频", "玥玥 Abadas"],
        "filename_boost": ["abadas", "Abadas"],
        "media_hint": "story_audio",
    },
    {
        "key": "steve_maggie",
        "title": "Steve and Maggie 儿歌",
        "aliases": [
            "steve and maggie",
            "steve maggie",
            "wow english",
            "史蒂夫和玛吉",
            "玛吉",
        ],
        "path_hint": f"{BBC_PREFIX}/06.儿歌  Songs for kids  Sing with Steve and Maggie更新至30集",
        "search_queries": [
            "Steve and Maggie mp3",
            "Wow English 音频",
            "Songs for kids Steve mp3",
            "玥玥 Steve and Maggie",
        ],
        "filename_boost": ["steve", "maggie", "wow english"],
        "media_hint": "story_audio",
    },
    {
        "key": "bitz_bob",
        "title": "Bitz and Bob 小贝大发明",
        "aliases": ["bitz and bob", "bitz bob", "小贝大发明"],
        "path_hint": f"{BBC_PREFIX}/19 - 小贝大发明STEM动画Bitz.&.Bob",
        "search_queries": ["Bitz Bob mp3", "小贝大发明 音频"],
        "filename_boost": ["bitz", "bob", "小贝"],
        "media_hint": "story_audio",
    },
    {
        "key": "yakka_dee",
        "title": "Yakka Dee 开口说单词",
        "aliases": ["yakka dee", "yakkadee", "开口说单词"],
        "path_hint": f"{BBC_PREFIX}/01-开口说单词 Yakka Dee（1-5季）",
        "search_queries": ["Yakka Dee mp3", "开口说单词 音频"],
        "filename_boost": ["yakka", "dee"],
        "media_hint": "story_audio",
    },
    {
        "key": "penelope",
        "title": "Penelope 蓝色小考拉",
        "aliases": ["penelope", "蓝色小考拉", "小考拉"],
        "path_hint": f"{BBC_PREFIX}/09-蓝色小考拉Penelope【中英双版+绘本台词+译文+故事会】",
        "search_queries": ["Penelope mp3", "蓝色小考拉 音频"],
        "filename_boost": ["penelope", "小考拉"],
        "media_hint": "story_audio",
    },
    {
        "key": "barbapapa",
        "title": "巴巴爸爸",
        "aliases": ["巴巴爸爸", "barbapapa", "巴巴爸", "巴巴妈妈"],
        "path_hint": f"{YUEYUE}/巴巴爸爸",
        "search_queries": ["001.01巴巴爸爸的诞生", "巴巴爸爸 mp3"],
        "filename_boost": ["巴巴爸爸", "巴巴"],
        "media_hint": "story_audio",
    },
    {
        "key": "popo_detective",
        "title": "屁屁侦探",
        "aliases": ["屁屁侦探", "屁屁偵探", "おしりたんてい", "butt detective", "屁股侦探"],
        "path_hint": f"{YUEYUE}/屁屁侦探",
        "search_queries": ["1_屁屁侦探-消失的人气甜点", "屁屁侦探 mp3"],
        "filename_boost": ["屁屁侦探"],
        "media_hint": "story_audio",
    },
    {
        "key": "bluey",
        "title": "Bluey 布鲁伊",
        "aliases": ["bluey", "布鲁伊"],
        "path_hint": f"{BBC_PREFIX}/03-布鲁伊Bluey（中文版+英文版）",
        "search_queries": ["Bluey mp3", "布鲁伊 音频"],
        "filename_boost": ["bluey", "布鲁伊"],
        "media_hint": "story_audio",
    },
    {
        "key": "frozen",
        "title": "冰雪奇缘 Frozen",
        "aliases": ["frozen", "冰雪奇缘", "艾莎", "安娜"],
        "path_hint": f"{YUEYUE}/冰雪奇缘",
        "search_queries": ["冰雪奇缘 mp3", "Frozen 音频", "玥玥 冰雪奇缘"],
        "filename_boost": ["frozen", "冰雪奇缘"],
        "media_hint": "movie",
    },
    {
        "key": "harry_potter",
        "title": "哈利波特",
        "aliases": ["harry potter", "哈利波特", "魔法石", "霍格沃茨"],
        "path_hint": f"{YUEYUE}/《哈利波特》1-8合集 1080P 人人影视内嵌中英硬字幕",
        "search_queries": ["哈利波特 有声", "Harry Potter mp3", "玥玥 哈利波特 音频"],
        "filename_boost": ["harry", "potter", "哈利波特"],
        "media_hint": "movie",
    },
    {
        "key": "tong_laoshi",
        "title": "童老师 牛津树精讲",
        "aliases": [
            "童老师",
            "童老师音频",
            "童老师牛津树",
            "牛津树童老师",
            "牛津树",
            "牛津阅读树",
            "牛津树精讲",
            "精讲音频",
        ],
        "path_hint": f"{YUEYUE}/童老师精讲音频/童老师音频课1阶",
        "search_queries": [
            "01【正课】Look at Me",
            "童老师音频课1阶 正课",
            "童老师 Look at Me 双语讲解",
        ],
        "filename_boost": ["童老师", "牛津树"],
        "media_hint": "story_audio",
    },
    {
        "key": "microcosmos",
        "title": "微观小世界 昆虫总动员",
        "aliases": ["微观小世界", "昆虫总动员", "microcosmos", "minuscule"],
        "path_hint": f"{YUEYUE}/001.微观小世界V昆虫总动员 第一季 78集 高清",
        "search_queries": [
            "微观小世界 mp3",
            "昆虫总动员 音频",
            "Minuscule 音频",
        ],
        "filename_boost": ["微观小世界", "昆虫", "minuscule"],
        "media_hint": "movie",
    },
    {
        "key": "peppa",
        "title": "小猪佩奇 Peppa Pig",
        "aliases": ["peppa", "peppa pig", "小猪佩奇", "佩奇"],
        "path_hint": f"{YUEYUE}/小猪佩奇",
        "search_queries": ["小猪佩奇 mp3", "Peppa Pig 音频", "玥玥 佩奇 故事"],
        "filename_boost": ["peppa", "佩奇", "小猪佩奇"],
        "media_hint": "story_audio",
    },
    {
        "key": "journey_west",
        "title": "西游记儿童广播剧",
        "aliases": [
            "西游记",
            "西游记广播剧",
            "美猴王",
            "孙悟空",
            "唐僧",
            "journey to the west",
            "xiyouji",
        ],
        "path_hint": f"{YUEYUE}/04.【完结】西游记儿童广播剧",
        "search_queries": [
            "第一回 美猴王",
            "第六十回 孙悟空",
            "第一百七十回",
            "西游记儿童广播剧",
            "满到归根",
        ],
        "filename_boost": ["回", "孙悟空", "唐僧", "美猴王"],
        "media_hint": "story_audio",
    },
]


def _load_token() -> str:
    data = json.loads(HERMES_CONFIG.read_text(encoding="utf-8"))
    uid = data["currentUserId"]
    token = (data.get(uid) or {}).get("accessToken")
    if not token:
        raise SystemExit(f"Quark not logged in: {HERMES_CONFIG}")
    return str(token)


def _search(token: str, keyword: str, *, category: int | None = None, size: int = 100) -> list[dict[str, Any]]:
    path = "/agent/v1/file/search"
    tm = str(int(time.time() * 1000))
    pan_token = hashlib.sha256(f"POST&{path}&{tm}&{_SIGN_KEY}".encode()).hexdigest()
    req_id = str(uuid.uuid4())
    url = f"{_API_BASE}{path}?req_id={req_id}&access_token={quote(token, safe='')}"
    headers = {
        "x-pan-client-id": _CLIENT_ID,
        "x-pan-tm": tm,
        "x-pan-token": pan_token,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    body: dict[str, Any] = {"search_type": "mix", "keyword": keyword, "size": size}
    if category is not None:
        body["category"] = category
    resp = httpx.post(url, headers=headers, json=body, timeout=60)
    resp.raise_for_status()
    payload = resp.json()
    return list((payload.get("data") or {}).get("file_list") or [])


def scan_folders(token: str) -> dict[str, dict[str, Any]]:
    folders: dict[str, dict[str, Any]] = {}
    for seed in FOLDER_SEEDS:
        try:
            rows = _search(token, seed, category=0)
        except httpx.HTTPError as exc:
            folders.setdefault(f"__error__:{seed}", {"error": str(exc), "seed": seed})
            continue
        for row in rows:
            if row.get("file", True):
                continue
            name = str(row.get("filename") or "").strip()
            if not name:
                continue
            folders[name] = {
                "seed": seed,
                "include_items": row.get("include_items") or row.get("includeItems"),
                "fid": row.get("fid"),
            }
        time.sleep(0.15)
    return folders


def build_catalog() -> dict[str, dict[str, Any]]:
    catalog: dict[str, dict[str, Any]] = {}
    for spec in CATALOG_SPECS:
        key = spec["key"]
        catalog[key] = {
            "title": spec["title"],
            "aliases": spec["aliases"],
            "path_hint": spec["path_hint"],
            "search_queries": spec["search_queries"],
            "filename_boost": spec.get("filename_boost") or [],
            "media_hint": spec.get("media_hint") or "story_audio",
        }
    return catalog


def main() -> None:
    token = _load_token()
    print("Scanning Quark folders (search-based)...")
    folders = scan_folders(token)
    catalog = build_catalog()

    yueyue_meta = folders.get(YUEYUE, {})
    report = {
        "scanned_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "yueyue_folder": yueyue_meta,
        "yueyue_child_count_hint": yueyue_meta.get("include_items"),
        "discovered_folder_count": len([k for k in folders if not k.startswith("__error__")]),
        "catalog_entry_count": len(catalog),
        "note": (
            "Quark Open API has no folder-list command; this scan uses keyword search. "
            "path_hint values are curated under 玥玥/; verify playback for each series."
        ),
        "folders": dict(sorted(folders.items())),
        "catalog_keys": sorted(catalog.keys()),
    }

    ALIASES_PATH.parent.mkdir(parents=True, exist_ok=True)
    ALIASES_PATH.write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    REPORT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"Wrote {len(catalog)} catalog entries -> {ALIASES_PATH}")
    print(f"Wrote scan report ({len(folders)} folders) -> {REPORT_PATH}")
    if yueyue_meta:
        print(f"玥玥 include_items={yueyue_meta.get('include_items')}")


if __name__ == "__main__":
    main()
