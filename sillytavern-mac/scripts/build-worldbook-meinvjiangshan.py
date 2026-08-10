#!/usr/bin/env python3
"""从 source/meinvjiangshan.txt 生成 SillyTavern 世界书（分块索引，非整本单次注入）。"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "source" / "meinvjiangshan.txt"
OUT = ROOT / "vendor" / "SillyTavern" / "data" / "default-user" / "worlds" / "meinvjiangshan.json"

CHUNK_MAX = 480
TERMS = [
    "战天风", "鬼瑶儿", "苏晨", "白云裳", "壶七公", "马横刀", "纪苇", "刑天道人",
    "九鬼门", "七大灾星", "天鼠星", "天厨星", "天困星", "天算星", "天巧星",
    "煮天锅", "装天篓", "玄天九变", "鬼牙石", "五犬", "天安城", "七喜国", "吞舟国",
    "天朝", "赤虎", "苍陵王", "东海", "三神僧", "仙女湖", "蜜雪儿",
    "玄信", "假天子", "真天子", "传国玉玺", "永乐公主", "玄琪", "田国舅", "红雪王", "逸参",
    "纪胜", "公羊角", "苏大将军", "马王爷", "横刀立马",
]

LORE = [
    (
        "世界观",
        ["美女江山", "一锅煮", "背景", "世界观", "天元"],
        """《美女江山一锅煮》为传统武侠背景。天元年间五犬之乱扰天下，各国诸侯并立。
江湖有三大邪门之首九鬼门，另有七大灾星等异人体系。主角战天风出身街头混混，
凭机缘得灾星传艺、奇功煮天锅，在鬼瑶儿、苏晨、白云裳等人与江山权谋之间成长。
本书为长篇连载，对话与剧情以章回推进；角色应贴合武侠口语，勿现代网络梗。""",
        True,
    ),
    (
        "战天风",
        ["战天风", "主角", "混混"],
        "战天风：滑头机变的街头混混出身，后得天厨星等传艺。擅诡谋与临场应变，重义气的江湖混世风格，后期涉军政天下大事。",
        False,
    ),
    (
        "鬼瑶儿",
        ["鬼瑶儿", "九鬼门小姐"],
        "鬼瑶儿：九鬼门门主之女，行事泼辣骄傲，与战天风从敌对、追杀到情愫暗生与并肩。关键词：鬼牙石、九次追杀、婚礼抢亲。",
        False,
    ),
    (
        "苏晨",
        ["苏晨", "苏小姐", "苏大将军", "吞舟国", "撞天婚"],
        """苏晨：吞舟国苏大将军之女，将门虎女。幼时体弱，佛前许撞天婚——抛绣球打着谁便嫁谁，
以拒纪奸之子纪胜（苏门虎女，不嫁犬子）。绣球击中战天风（当时冒七喜王太子公羊角），拜天地成亲。
后战天风被鬼瑶儿掳走，苏父忧愤病亡；苏晨随七喜使臣入七喜国摄政称王妃。
西风国线：战天风在西风国为天子（假天子博弈），苏晨来朝认得出却不能当众相认；此后每夜三更，
战天风溜出王宫至苏晨行宫相会，她总在等候，二人以风弟、晨姐相称，缠绵依偎（鬼瑶儿曾立百日期限掣肘）。
结局：苏晨被换回救归，得信急奔而来，战天风牵鬼瑶儿、白云裳两女迎上，三美共聚；后随战天风弃位隐居。
性情温婉重义，亦练拳习剑；与战天风、鬼瑶儿、白云裳、卢江等有情感纠葛。""",
        False,
    ),
    (
        "白云裳",
        ["白云裳", "奇女子"],
        "白云裳：心系天下的奇女子，促战天风涉国事、抗五犬、匡正气，后嫁战天风。智略宏观，常推动大场面剧情。",
        False,
    ),
    (
        "九鬼门",
        ["九鬼门", "邪门", "鬼牙石"],
        "九鬼门：三大邪门之首，镇庄之宝鬼牙石。门规狠辣，鬼瑶儿一脉与战天风主线强相关。",
        False,
    ),
    (
        "七大灾星",
        ["七大灾星", "灾星", "壶七公"],
        "七大灾星：江湖异人体系，含天鼠星壶七公、天厨星等。天厨星授战天风煮天锅、装天篓后阵亡；另有天困、天算、天巧等传承线。",
        False,
    ),
    (
        "煮天锅",
        ["煮天锅", "装天篓", "玄天九变", "武功"],
        "煮天锅/装天篓/玄天九变：天厨星一脉奇功，战天风核心武学与道具体系，战斗与智斗的重要依仗。",
        False,
    ),
    (
        "马横刀",
        ["马横刀", "马王爷", "马大哥", "横刀立马"],
        """马横刀：号横刀立马，天朝马王爷，正道大侠。心系天朝一统、黎民免战祸，
助真天子玄信寻传国玉玺，曾四天三夜奔袭救百夜王子。战天风敬称马大哥，受其感召。
魔心刃，武功绝顶，待战天风如弟。后为玄信/帝位之争所害；战天风为之冷狠复仇，
鬼瑶儿恐其成复仇狂神。百姓与战天风皆敬其替天下操心。""",
        False,
    ),
    (
        "玄信",
        ["玄信", "真天子", "泥马渡江", "十四王子", "皇十四子"],
        """玄信：天朝皇十四子，五犬破城时单骑至江，泥马渡江得救，为正统真天子。
城破失传国玉玺，诸国不认，多年流亡；姐永乐公主玄琪曾托战天风立誓送玺。
马横刀为其复统奔走；但玄信后为帝位害马横刀。战天风言「椅子是我让的」，誓杀之、
抢位踩烂。终有红雪王废假迎真，天朝重归一统。""",
        False,
    ),
    (
        "假天子",
        ["假天子", "立天子", "传国玉玺", "田国舅", "雪狼王", "逸参"],
        """假天子：五犬之乱后天朝分裂，诸候拥立新主，假天子林立。
田国舅勾结雪狼王，立冒充玄信之假天子（无传国玉玺），借逸参（吞舟国）权势压真天子。
天下认印不认人；有玺则诏令一出假天子难坐。战天风持玺周旋，曾言认印不认人可假充；
后夺位主要为马横刀复仇毁椅，非久恋龙椅。爱美人不爱江山为其江湖名声。""",
        False,
    ),
    (
        "玩家身份",
        ["玩家", "user", "扮演", "身份", "Persona", "战天风"],
        """使用世界书 meinvjiangshan 时，{{user}} 默认即战天风——《美女江山一锅煮》男主，滑头机变、嘴甜讲义气、江湖混混口吻。
除非用户在对话中明确改扮他人，所有角色须按此理解 {{user}}，勿将 {{user}} 写成路人、现代访客或无名客。
群聊时 {{user}} 仍为战天风本人，鬼瑶儿、苏晨等为独立 AI 角色，禁止由任一角色代写战天风台词。""",
        True,
    ),
]


def load_text() -> str:
    raw = SOURCE.read_bytes()
    for enc in ("gb18030", "gbk", "utf-8"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    raise SystemExit(f"无法解码: {SOURCE}")


def chunk_paragraphs(text: str, max_len: int = CHUNK_MAX) -> list[str]:
    parts: list[str] = []
    buf = ""
    for para in re.split(r"\r?\n+", text):
        para = para.strip()
        if not para:
            continue
        if len(para) > max_len:
            if buf:
                parts.append(buf)
                buf = ""
            for i in range(0, len(para), max_len):
                parts.append(para[i : i + max_len])
            continue
        if len(buf) + len(para) + 2 <= max_len:
            buf = f"{buf}\n\n{para}" if buf else para
        else:
            if buf:
                parts.append(buf)
            buf = para
    if buf:
        parts.append(buf)
    return parts


def keys_for(text: str, extra: list[str] | None = None) -> list[str]:
    found = [t for t in TERMS if t in text]
    if extra:
        for e in extra:
            if e not in found:
                found.append(e)
    if not found:
        found = ["美女江山"]
    return found[:10]


def base_entry(uid: int, keys: list[str], content: str, comment: str, *, constant: bool = False) -> dict:
    return {
        "uid": uid,
        "key": keys,
        "keysecondary": [],
        "comment": comment,
        "content": content.strip(),
        "constant": constant,
        "selective": not constant,
        "order": 100,
        "position": 0,
        "disable": False,
        "displayIndex": uid,
        "addMemo": True,
        "group": "一锅煮",
        "groupOverride": False,
        "groupWeight": 100,
        "sticky": 0,
        "cooldown": 0,
        "delay": 0,
        "probability": 100,
        "depth": 4,
        "useProbability": True,
        "role": None,
        "vectorized": False,
        "excludeRecursion": False,
        "preventRecursion": False,
        "delayUntilRecursion": False,
        "scanDepth": None,
        "caseSensitive": None,
        "matchWholeWords": None,
        "useGroupScoring": None,
        "automationId": "",
    }


def main() -> None:
    if not SOURCE.exists():
        raise SystemExit(f"缺少源文件: {SOURCE}")

    text = load_text()
    entries: dict[str, dict] = {}
    uid = 0

    for comment, keys, content, constant in LORE:
        entries[str(uid)] = base_entry(uid, keys, content, comment, constant=constant)
        uid += 1

    markers = list(re.finditer(r"正文\s*(第[一二三四五六七八九十百千零〇两]+章)", text))
    for i, m in enumerate(markers):
        title = m.group(1)
        start = m.end()
        end = markers[i + 1].start() if i + 1 < len(markers) else len(text)
        body = text[start:end].strip()
        if not body:
            continue
        chunks = chunk_paragraphs(body)
        for j, chunk in enumerate(chunks):
            comment = f"{title}-{j + 1}" if len(chunks) > 1 else title
            keys = keys_for(chunk, [title, title.replace("第", "").replace("章", ""), "章节"])
            e = base_entry(uid, keys, chunk, comment)
            e["disable"] = True  # 默认禁用章节 chunk；LORE 轻量注入见 configure-meinvjiangshan-lore-light.sh
            entries[str(uid)] = e
            uid += 1

    # 前言（第一章前）单独切块
    if markers:
        pre = text[: markers[0].start()].strip()
        pre = re.sub(r"^《美女江山一锅煮》全集.*?声明.*?使用,.*?\n", "", pre, flags=re.S)
        for j, chunk in enumerate(chunk_paragraphs(pre, 400)):
            e = base_entry(uid, keys_for(chunk, ["序", "开篇", "五犬之乱"]), chunk, f"序-{j + 1}")
            e["disable"] = True
            entries[str(uid)] = e
            uid += 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"entries": entries}, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")
    print(f"已写入 {OUT}")
    print(f"条目数: {len(entries)}")
    print(f"源文字数: {len(text)}")
    print("刷新 ST 后：世界书 -> 导入/选择 meinvjiangshan -> 绑定角色")


if __name__ == "__main__":
    main()
