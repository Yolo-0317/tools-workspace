"""Online EN–ZH dictionary (Youdao EC + Collins, Free Dictionary fallback)."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = ROOT / "data" / "dict_cache"
USER_AGENT = "Mozilla/5.0 (compatible; readalong-dict/4.1)"
YOUDAO_URL = "https://dict.youdao.com/jsonapi"
DICTVOICE_URL = "https://dict.youdao.com/dictvoice"


def normalize_word(raw: str) -> str:
    w = raw.strip().lower()
    w = re.sub(r"^[^a-z']+|[^a-z'-]+$", "", w)
    return w


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text).strip()


def _http_json(url: str, *, timeout: float = 8.0) -> dict | list | None:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError, TimeoutError):
        return None


def _youdao_url(word: str) -> str:
    params = {
        "q": word,
        "le": "en",
        "dicts": json.dumps({"count": 2, "dicts": [["ec", "collins"]]}, separators=(",", ":")),
    }
    return f"{YOUDAO_URL}?{urllib.parse.urlencode(params)}"


def _parse_ec(head: dict) -> tuple[list[dict], list[str]]:
    meanings: list[dict] = []
    zh_all: list[str] = []
    for tr_group in head.get("trs") or []:
        for tr in tr_group.get("tr") or []:
            for item in tr.get("l", {}).get("i") or []:
                text = str(item).strip()
                if not text:
                    continue
                pos = ""
                body = text
                m = re.match(r"^([a-z]+\.)\s*(.+)$", text, re.I)
                if m:
                    pos = m.group(1).lower()
                    body = m.group(2)
                for part in re.split(r"[，,；;]", body):
                    part = part.strip()
                    if part:
                        zh_all.append(part)
                meanings.append(
                    {
                        "pos": pos,
                        "zh": [body],
                        "definitions": [{"def": body}],
                    }
                )
    return meanings, zh_all


def _parse_collins(data: dict) -> tuple[list[dict], list[str], int]:
    collins = data.get("collins") or {}
    blocks = collins.get("collins_entries") or []
    if not blocks:
        return [], [], 0

    head = blocks[0]
    star = int(head.get("star") or 0)
    meanings: list[dict] = []
    zh_all: list[str] = []

    for block in head.get("entries", {}).get("entry", []):
        for te in block.get("tran_entry", []):
            tran = _strip_html(te.get("tran") or "")
            if not tran:
                continue

            pos_entry = te.get("pos_entry") or {}
            pos = (pos_entry.get("pos") or "").strip()
            pos_tips = (pos_entry.get("pos_tips") or "").strip()
            if pos and pos_tips:
                pos = f"{pos} · {pos_tips}"
            elif pos_tips:
                pos = pos_tips

            zh_match = re.search(r"([\u4e00-\u9fff][\u4e00-\u9fff·，、；：\s\w'-]*)$", tran)
            zh = zh_match.group(1).strip() if zh_match else ""
            if zh:
                zh_all.append(zh)

            defs: list[dict] = [{"def": tran}]
            for sent in (te.get("exam_sents") or {}).get("sent") or []:
                eng = _strip_html(sent.get("eng_sent") or "")
                chn = _strip_html(sent.get("chn_sent") or "")
                if eng:
                    defs.append({"def": eng, "example": chn})

            meanings.append(
                {
                    "pos": pos,
                    "zh": [zh] if zh else [],
                    "definitions": defs[:4],
                }
            )

    return meanings, zh_all, star


def _parse_youdao(data: dict, word: str) -> dict | None:
    ec = data.get("ec") or {}
    entries = ec.get("word") or []
    head = entries[0] if entries else {}

    usphone = (head.get("usphone") or "").strip()
    ukphone = (head.get("ukphone") or "").strip()
    if usphone and ukphone and usphone != ukphone:
        phonetic = f"美 /{usphone}/  英 /{ukphone}/"
    elif usphone:
        phonetic = f"/{usphone}/"
    elif ukphone:
        phonetic = f"/{ukphone}/"
    else:
        phonetic = ""

    collins_meanings, collins_zh, collins_star = _parse_collins(data)
    ec_meanings, ec_zh = _parse_ec(head) if head else ([], [])

    meanings = collins_meanings or ec_meanings
    zh_all = collins_zh or ec_zh
    if not meanings:
        return None

    tags = ["有道词典", "online"]
    if collins_meanings:
        tags.insert(0, "Collins")

    audio = ""
    if head.get("usspeech") or usphone:
        audio = f"{DICTVOICE_URL}?audio={urllib.parse.quote(word)}&type=2"

    result: dict = {
        "ok": True,
        "word": word,
        "phonetic": phonetic,
        "zh": "；".join(dict.fromkeys(zh_all[:6])),
        "meanings": meanings[:8],
        "tags": tags,
        "source": "youdao",
        "audio": audio,
    }
    if collins_star > 0:
        result["collins"] = collins_star
    return result


def _fetch_youdao(word: str) -> dict | None:
    data = _http_json(_youdao_url(word))
    if not isinstance(data, dict):
        return None
    return _parse_youdao(data, word)


def _fetch_dictionaryapi(word: str) -> dict | None:
    url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{urllib.parse.quote(word)}"
    data = _http_json(url)
    if not isinstance(data, list) or not data:
        return None

    entry = data[0]
    phonetic = entry.get("phonetic") or ""
    audio = ""
    for ph in entry.get("phonetics") or []:
        if ph.get("text") and not phonetic:
            phonetic = ph["text"]
        if ph.get("audio") and not audio:
            audio = ph["audio"]

    meanings: list[dict] = []
    for m in entry.get("meanings") or []:
        pos = (m.get("partOfSpeech") or "").strip()
        defs = []
        for d in m.get("definitions") or []:
            item: dict = {"def": d.get("definition") or ""}
            if d.get("example"):
                item["example"] = d["example"]
            if item["def"]:
                defs.append(item)
        if defs:
            meanings.append({"pos": pos, "definitions": defs})

    if not meanings:
        return None

    return {
        "ok": True,
        "word": word,
        "phonetic": phonetic,
        "zh": "",
        "meanings": meanings[:8],
        "tags": ["Free Dictionary", "online"],
        "source": "dictionaryapi.dev",
        "audio": audio,
    }


def lookup(word: str, *, use_cache: bool = True) -> dict:
    w = normalize_word(word)
    if not w or len(w) < 2:
        return {"ok": False, "error": "invalid_word", "query": word}

    cache_path = CACHE_DIR / f"{w}.json"
    if use_cache and cache_path.is_file():
        try:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            if cached.get("ok") and cached.get("source") == "youdao":
                return cached
        except json.JSONDecodeError:
            pass

    result = _fetch_youdao(w)
    if not result:
        result = _fetch_dictionaryapi(w)

    if not result:
        return {
            "ok": False,
            "error": "not_found",
            "query": w,
            "hint": "未找到释义，请检查拼写或稍后重试",
        }

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result
