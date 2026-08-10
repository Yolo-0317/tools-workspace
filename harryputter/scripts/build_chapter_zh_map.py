#!/usr/bin/env python3
"""Build en→zh mapping for a chapter using monotonic anchor points + proportional split."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# hp01 ch04 · Keeper of the Keys — (en_sentence_index, zh_sentence_index) story anchors
HP01_CH04_ANCHORS: list[tuple[int, int]] = [
    (0, 0),
    (8, 8),
    (16, 16),
    (24, 24),
    (31, 29),
    (40, 34),
    (47, 41),
    (56, 48),
    (64, 56),
    (72, 64),
    (84, 72),
    (96, 78),
    (105, 82),
    (108, 85),
    (118, 93),
    (125, 104),
    (128, 106),
    (132, 109),
    (138, 113),
    (140, 114),
    (147, 117),
    (148, 118),
    (151, 120),
    (156, 122),
    (159, 123),
    (164, 125),
    (165, 126),
    (166, 129),
    (168, 131),
    (176, 132),
    (178, 133),
    (192, 134),
    (195, 135),
    (198, 136),
    (199, 137),
    (209, 139),
    (210, 140),
    (212, 141),
    (213, 142),
    (215, 143),
    (218, 146),
    (222, 150),
    (223, 151),
    (228, 151),
    (236, 152),
    (240, 153),
    (246, 160),
    (250, 164),
    (254, 167),
    (256, 168),
    (259, 170),
    (264, 172),
    (270, 176),
    (277, 181),
    (283, 185),
    (285, 187),
    (287, 187),
]

# Narrative beats: same complete ZH on each EN line in range (avoid char-level shards)
HP01_CH04_COARSE_GROUPS: list[tuple[int, int, str]] = [
    (
        168,
        169,
        "“对那些狂奔的戈耳工们，哈利，人们到现在还心有余悸。哎呀，难哪。”",
    ),
    (
        170,
        175,
        "当时有一名巫师，他后来……变坏了，变得坏透了，坏得不能再坏了。他的名字叫……”海格咽了一口唾沫，可还是说不出一个字来。",
    ),
    (176, 177, "“你能写出来吗？”哈利提醒说。"),
    (
        178,
        181,
        "“不行，这个字我不会拼。好吧……他叫伏地魔。”海格打了个寒噤，“别再逼我重复他的名字了。”",
    ),
    (
        182,
        183,
        "总之，这个……这个巫师，大概二十年前吧，他开始为自己找门徒。他也找到了一些人……他们有些是因为怕他，有些是想从他那里学到些功法，因为他法力高强。",
    ),
    (184, 184, "好了，那段日子可真是黑暗啊。"),
    (
        185,
        188,
        "哈利，你不知道应该相信谁，也不敢跟陌生的男女巫师交朋友……还发生了许多可怕的事情。他接管了我们这个世界。当然有些人反对他，他就把他们都杀掉了。太可怕了。",
    ),
    (
        189,
        191,
        "当时惟一安全的地方就只有霍格沃茨。那个神秘人最害怕的就是邓布利多。横竖不敢动那所学校，至少当时是这样。",
    ),
    (
        192,
        194,
        "“现在来说说你的父母，他们是我知道的最优秀的男女巫师了。他们当年在霍格沃茨还分别担任男女学生会的主席呢！叫人弄不明白的是当初那个神秘人为什么没有把他们拉到他那边去……也许他知道他们和邓布利多很接近，不想与黑势力有关系吧。",
    ),
    (
        195,
        197,
        "“也许他认为他可以说服他们，也许想干脆把他们干掉。大家都知道，十年前万圣节②前夕，他来到你们住的村庄，当时你只有一岁。他来到你们家就……就……”",
    ),
    (198, 198, "海格突然掏出一块污渍斑斑的、脏得要命的手帕擤鼻涕，那声音响得像在吹晨号。"),
    (
        199,
        207,
        "“对不起，”他说，“这是一个不幸的消息。我认识你的父母，再也找不到比他们再好的人了，不管怎么说……神秘人把他们杀了，可是叫人弄不明白的是他也要去杀你。也许是想斩尽杀绝吧。可他没有杀成。你就从来没有想过你脑门上那道伤疤是怎么来的吗？那不是一般的刀疤。那是一道很厉害的魔咒，它杀了你的父母，毁了你的家，可是碰到你身上却没有起作用。于是你也就因为这出名了，哈利。只要他决定要杀的人，没有一个能躲过劫难，只有你大难不死。他杀掉了当时一些优秀的男女巫师，比如麦金农夫妇、彭斯夫妇、普成特夫妇。你是惟一大难不死，活下来的人。”",
    ),
    (208, 208, "哈利的脑海里出现了一些非常悲惨的景象。"),
    (
        140,
        141,
        "“老早就知道，”佩妮姨妈突然尖着嗓子喊起来，“老早就知道！我们当然老早就知道！我那个该死的妹妹既然是，你怎么可能不是？哦，她就是收到了同样的一封信，然后就不见了……进了那所学校……每逢放假回来，口袋里装满了蟾蜍蛋，把茶杯都变成了老鼠。只有我一个人，算是把她看透了——十足一个怪物！可是我的父母却看不清，整天莉莉长、莉莉短，家里有个巫婆他们还美滋滋的！”",
    ),
    (
        147,
        148,
        "“然后她就在学校里遇到了那个波特，毕业后他们结了婚，有了你。当然，我也知道你会跟他们一样，一样古怪，一样……一样……不正常……后来，对不起。她走了，自我爆炸了，我们只好收养你！”",
    ),
    (218, 218, "他像拿着一把剑那样用伞指着弗农姨父说：“我警告你，德思礼，我警告你……敢再说一个字……”"),
    (219, 219, "弗农姨父怕被这个大胡子巨人的伞头戳伤，又泄气了，紧贴着墙不敢再说话了。"),
    (220, 220, "“这样才好。”海格说着，大口喘气，坐到沙发上，这回沙发整个塌到地板上了。"),
    (221, 221, "这时哈利还有许多问题，成百上千的问题要问。"),
    (236, 236, "“我们大多数人都认为他还在这一带，不过已经失去了法力，已经虚弱得成不了气候了。因为你身上具有的某种力量把他毁了，哈利。那天晚上肯定发生了一件他没有预料到的事……我不知道会是什么，没有人知道……不过你身上具有的某种力量使他受挫了，就是这样。”"),
]

# hp01 ch05 · Diagon Alley — hand-tuned story anchors (EN 392 · ZH 778)
HP01_CH05_ANCHORS: list[tuple[int, int]] = [
    (0, 0),
    (1, 1),
    (5, 4),
    (10, 8),
    (15, 12),
    (20, 19),
    (25, 26),
    (28, 55),
    (29, 63),
    (31, 65),
    (35, 71),
    (37, 73),
    (43, 81),
    (45, 86),
    (50, 97),
    (53, 106),
    (58, 115),
    (65, 139),
    (69, 149),
    (70, 154),
    (75, 165),
    (84, 183),
    (92, 192),
    (100, 217),
    (108, 222),
    (122, 228),
    (131, 244),
    (135, 260),
    (139, 284),
    (147, 317),
    (153, 323),
    (160, 336),
    (162, 339),
    (164, 342),
    (168, 349),
    (174, 358),
    (176, 360),
    (182, 368),
    (184, 374),
    (185, 377),
    (192, 380),
    (196, 384),
    (200, 394),
    (202, 397),
    (204, 400),
    (210, 409),
    (212, 411),
    (214, 414),
    (216, 418),
    (217, 419),
    (248, 497),
    (249, 500),
    (250, 501),
    (251, 502),
    (264, 543),
    (266, 546),
    (268, 554),
    (271, 560),
    (272, 563),
    (273, 565),
    (276, 571),
    (281, 574),
    (290, 585),
    (294, 589),
    (313, 614),
    (315, 616),
    (320, 629),
    (330, 649),
    (337, 663),
    (350, 688),
    (353, 703),
    (358, 712),
    (364, 724),
    (365, 725),
    (366, 727),
    (367, 729),
    (368, 731),
    (370, 735),
    (372, 738),
    (374, 741),
    (380, 755),
    (388, 768),
    (391, 776),
]

HP01_CH05_COARSE_GROUPS: list[tuple[int, int, str]] = [
    (1, 1, "第二天一大早哈利就醒了。"),
    (
        28,
        28,
        "“我一个钱也没有，昨天晚上你已经听弗农姨父说过了，他不会花钱让我去学魔法的。”",
    ),
    (
        29,
        30,
        "“这个你不用担心，”海格说，站起来搔了搔头，“你以为你父母什么也没有给你留下吗？”",
    ),
    (
        75,
        91,
        "（制服）一年级新生需要：1．三套素面工作袍（黑色）2．一顶日间戴的素面尖顶帽（黑色）3．一双防护手套（龙皮或同类材料制作）4．一件冬用斗篷（黑色，银扣）请注意：学生全部服装均须缀有姓名标牌（课本）全部学生均需准备下列图书：《标准咒语（初级）》 米兰达戈沙克著《魔法史》 巴希达巴沙特著《魔法理论》 阿德贝沃夫林著《初学变形指南》 埃默瑞斯威奇著《千种神奇草药及蕈类》 菲利达斯波尔著《魔法药剂与药水》 阿森尼吉格著《怪兽及其产地》 纽特斯卡曼著《黑暗力量：自卫指南》 昆丁特林布著（其他装备）一支魔杖一只大锅（锡镀制，标准尺寸2号） 一套玻璃或水晶小药瓶一架望远镜一台黄铜天平学生可携带一只猫头鹰或一只猫或一只蟾蜍，在此特别提请家长注意，一年级新生不准自带飞天扫帚①",
    ),
    (
        153,
        153,
        "之后他们面前出现了第二道门，是银色的，两扇门上镌刻着如下的文字：请进，陌生人，不过你要当心贪得无厌会是什么下场，一味索取，不劳而获，必将受到最严厉的惩罚，因此如果你想从我们的地下金库取走一份从来不属于你的财富，窃贼啊，你已经受到警告，当心招来的不是宝藏，而是恶报。",
    ),
    (
        251,
        263,
        "当他们走出店铺时，哈利问：“海格，什么是魁地奇？”“哎呀，我的天哪，哈利，我忘记你知道得太少了，竟然连什么是魁地奇都不知道。”“劳驾，别让我的情绪变得更坏好不好？”他向海格说起在摩金夫人店里碰到的那个面色苍白的男孩。“……他还说甚至不应该准许麻瓜家庭出身的人入学……”“你又不是麻瓜家庭出来的。如果他父母是男女巫师——你在破釜酒吧就已经看到了——那么他就该是听着你的名字长大的。其实，他又知道多少，我看见许多最优秀的巫师都是出自麻瓜家庭里惟一懂法术的人——看看你母亲！看看她有一个什么样的姐姐！”“那魁地奇到底是什么呢？”“那是我们的一种运动，一种巫师们玩的球类运动。它像——麻瓜世界的足球——人人都喜欢玩魁地奇——骑飞天扫帚在空中打，有四个球——至于玩球的规则嘛，解释起来还真有点儿困难。",
    ),
    (
        380,
        387,
        "“别担心，哈利。你很快就会学会的。在霍格沃茨，人人都是从基础开始学的。你会很好的。打起精神来。我知道这对于你很难。你一直孤零零一个人，总是很难过的。不过你在霍格沃茨一定会很愉快，像我……说实话……过去和现在都很愉快。”",
    ),
    (
        388,
        391,
        "海格把哈利送上可以回德思礼家的火车，然后递给他一封信。“这是你去霍格沃茨的车票。”他说，“九月一日——国王十字车站——票上都有。德思礼夫妇要是欺负你，就写封信让猫头鹰给我送来，它知道到什么地方去找我……下次再见了，哈利。”火车驶出了车站。哈利想目送海格离去，他跪到座位上，鼻子紧贴着车窗，一眨眼工夫，海格就不见了。",
    ),
]

# hp01 ch01 · The Boy Who Lived — EN 242 · ZH 526
HP01_CH01_ANCHORS: list[tuple[int, int]] = [
    (0, 0),
    (1, 1),
    (3, 4),
    (5, 9),
    (10, 17),
    (11, 18),
    (12, 20),
    (13, 21),
    (15, 24),
    (17, 26),
    (26, 35),
    (59, 82),
    (64, 88),
    (86, 118),
    (110, 190),
    (115, 198),
    (116, 199),
    (118, 201),
    (119, 202),
    (121, 204),
    (125, 209),
    (135, 218),
    (139, 223),
    (170, 310),
    (210, 436),
    (216, 453),
    (223, 473),
    (236, 511),
    (241, 525),
]

# Opening: US EPUB splits Vernon job / physique / Petunia; ZH merges differently.
HP01_CH01_COARSE_GROUPS: list[tuple[int, int, str]] = [
    (2, 2, "拜托，拜托了。他们从来跟神秘古怪的事不沾边，因为他们根本不相信那些邪门歪道。"),
    (3, 3, "弗农德思礼先生在一家名叫格朗宁的公司做主管，公司生产钻机。"),
    (4, 4, "德思礼太太是个瘦削的金发女人。她的脖子几乎比正常人长一倍。这样每当她花许多时间隔着篱墙引颈而望、窥探左邻右舍时，她的长脖子可就派上了大用场。"),
]

def proportional_anchors(n_en: int, n_zh: int, *, step: int = 6) -> list[tuple[int, int]]:
    """Evenly spaced (en, zh) anchors for chapters without hand-tuned story points."""
    if n_en < 2 or n_zh < 2:
        return [(0, 0)]
    anchors = [(0, 0)]
    for en_i in range(step, n_en, step):
        zh_i = min(n_zh - 1, round(en_i * (n_zh - 1) / (n_en - 1)))
        anchors.append((en_i, zh_i))
    if anchors[-1] != (n_en - 1, n_zh - 1):
        anchors.append((n_en - 1, n_zh - 1))
    return sorted(set(anchors))


def _apply_coarse_groups(mapping: dict[int, str], groups: list[tuple[int, int, str]]) -> None:
    """Only the first EN index in each group carries ZH; rest inherit at playback."""
    for start, end, text in groups:
        mapping[start] = text
        for i in range(start + 1, end + 1):
            mapping[i] = ""


def _snap_zh_split(zh: str, target: int) -> int:
    if target <= 0:
        return 0
    if target >= len(zh):
        return len(zh)
    punct = "。！？；，、："
    best, rank = target, 10**9
    for pos in range(max(1, target - 14), min(len(zh), target + 14)):
        ch = zh[pos - 1]
        if ch not in punct:
            continue
        r = abs(pos - target) + (0 if ch in "。！？" else 4)
        if r < rank:
            rank, best = r, pos
    return best


def _split_zh(zh: str, parts: int, weights: list[int]) -> list[str]:
    if parts <= 1 or not zh:
        return [zh]
    weights = [max(1, w) for w in weights]
    total = sum(weights)
    cuts = [0]
    acc = 0
    for w in weights[:-1]:
        acc += w
        cuts.append(_snap_zh_split(zh, round(len(zh) * acc / total)))
    cuts.append(len(zh))
    chunks = [zh[cuts[i] : cuts[i + 1]].strip() for i in range(parts)]
    for i, ch in enumerate(chunks):
        if ch:
            continue
        if i > 0 and chunks[i - 1]:
            prev = chunks[i - 1]
            mid = max(1, len(prev) // 2)
            chunks[i] = prev[mid:].strip()
            chunks[i - 1] = prev[:mid].strip()
        elif i + 1 < len(chunks) and chunks[i + 1]:
            nxt = chunks[i + 1]
            mid = max(1, len(nxt) // 2)
            chunks[i] = nxt[:mid].strip()
            chunks[i + 1] = nxt[mid:].strip()
    return [c for c in chunks if c] or [zh]


def map_segment(
    en_sents: list[str],
    zh_sents: list[str],
    en_a: int,
    en_b: int,
    zh_a: int,
    zh_b: int,
) -> dict[int, str]:
    en_idx = list(range(en_a, en_b))
    zh_idx = list(range(zh_a, zh_b)) if zh_b > zh_a else ([zh_a] if zh_a < len(zh_sents) else [])
    if not en_idx:
        return {}
    if not zh_idx:
        return {}

    out: dict[int, str] = {}
    n_en, n_zh = len(en_idx), len(zh_idx)

    if n_en == n_zh:
        for ei, zi in zip(en_idx, zh_idx):
            out[ei] = zh_sents[zi]
        return out

    if n_en > n_zh:
        # Put full ZH on the first EN in each group; attach_translation merges trailing EN rows.
        for zj, zi in enumerate(zh_idx):
            e_start = zj * n_en // n_zh
            e_end = (zj + 1) * n_en // n_zh if zj < n_zh - 1 else n_en
            group = en_idx[e_start:e_end]
            zh = zh_sents[zi]
            if not group:
                continue
            out[group[0]] = zh
            for g in group[1:]:
                out[g] = ""
        return out

    # n_en < n_zh: group zh onto each en
    for ej, ei in enumerate(en_idx):
        z_start = ej * n_zh // n_en
        z_end = (ej + 1) * n_zh // n_en if ej < n_en - 1 else n_zh
        out[ei] = "".join(zh_sents[z] for z in zh_idx[z_start:z_end])
    return out


def build_map(en_sents: list[str], zh_sents: list[str], anchors: list[tuple[int, int]]) -> dict[int, str]:
    anchors = sorted(set(anchors))
    out: dict[int, str] = {}
    for i, (en_a, zh_a) in enumerate(anchors):
        en_b = anchors[i + 1][0] if i + 1 < len(anchors) else len(en_sents)
        zh_b = anchors[i + 1][1] if i + 1 < len(anchors) else len(zh_sents)
        out.update(map_segment(en_sents, zh_sents, en_a, en_b, zh_a, zh_b))
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--book", default="hp01")
    parser.add_argument("--chapter", type=int, default=4)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    from chapters import sentences_path, zh_extract_path  # noqa: E402

    en = json.loads(sentences_path(args.book, args.chapter).read_text(encoding="utf-8"))
    zh = json.loads(zh_extract_path(args.book, args.chapter).read_text(encoding="utf-8"))
    es, zs = en["sentences"], zh["sentences"]

    coarse: list[tuple[int, int, str]] = []
    if args.book == "hp01" and args.chapter == 4:
        anchors = HP01_CH04_ANCHORS
        coarse = HP01_CH04_COARSE_GROUPS
    elif args.book == "hp01" and args.chapter == 5:
        anchors = HP01_CH05_ANCHORS
        coarse = HP01_CH05_COARSE_GROUPS
    elif args.book == "hp01" and args.chapter == 1:
        anchors = HP01_CH01_ANCHORS
        coarse = HP01_CH01_COARSE_GROUPS
    else:
        anchors = proportional_anchors(len(es), len(zs), step=8)
    if not anchors:
        raise SystemExit("No anchors for this chapter")

    mapping = build_map(es, zs, anchors)
    if coarse:
        _apply_coarse_groups(mapping, coarse)
    for i in range(len(es)):
        mapping.setdefault(i, "")
    out_path = ROOT / "data/translation_fixes" / f"{args.book}_ch{args.chapter:02d}.json"
    prior_splits: list = []
    prior_overrides: list = []
    if out_path.is_file():
        prior = json.loads(out_path.read_text(encoding="utf-8"))
        prior_splits = prior.get("line_splits", [])
        prior_overrides = prior.get("line_zh_overrides", [])
    fixes = {
        "comment": f"{args.book} ch{args.chapter:02d} · anchor-based en→zh map (full override)",
        "en_to_zh_text": {str(k): v for k, v in sorted(mapping.items())},
        "line_splits": prior_splits,
        "line_zh_overrides": prior_overrides,
    }
    if args.book == "hp01" and args.chapter == 4:
        fixes["en_to_zh_text"]["114"] = (
            "霍格沃茨魔法学校校长：阿不思邓布利多（国际魔法联合会会长、巫师协会会长、梅林爵士团一级魔法师）。"
            "亲爱的波特先生：我们愉快地通知您，您已获准在霍格沃茨魔法学校就读。"
        )
    if args.book == "hp01" and args.chapter == 1:
        fixes["en_to_zh_text"]["0"] = "第一章 大难不死的男孩"
    if args.dry_run:
        print(json.dumps(fixes, ensure_ascii=False, indent=2)[:2000])
        print(f"... {len(fixes['en_to_zh_text'])} entries")
        return
    out_path.write_text(json.dumps(fixes, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {out_path} — {len(fixes['en_to_zh_text'])} en_to_zh_text entries")


if __name__ == "__main__":
    main()
