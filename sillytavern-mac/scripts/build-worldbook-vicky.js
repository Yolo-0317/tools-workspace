#!/usr/bin/env node
/**
 * 薇琪 · 精简世界书 v1.0 — 接话+灵活跟节奏，无轮次节拍/STAT（参考艾琳娜 v2.0）
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const VERSION = '1.1';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');
const OUT = path.join(ROOT, 'vendor/SillyTavern/data/default-user/worlds/vicky-yangsheng.json');
const EXPORT = path.join(ROOT, 'export/vicky-yangsheng-world.json');

function entry(uid, comment, keys, content, { constant = false, order = 100 } = {}) {
    return {
        uid,
        key: keys,
        keysecondary: [],
        comment,
        content: content.trim(),
        constant,
        selective: !constant,
        order,
        position: 0,
        disable: false,
        displayIndex: uid,
        addMemo: true,
        group: `薇琪 v${VERSION}`,
        groupOverride: false,
        groupWeight: 100,
        sticky: 0,
        cooldown: 0,
        delay: 0,
        probability: 100,
        depth: 4,
        useProbability: true,
        role: null,
        vectorized: false,
        excludeRecursion: false,
        preventRecursion: false,
        delayUntilRecursion: false,
        scanDepth: null,
        caseSensitive: null,
        matchWholeWords: null,
        useGroupScoring: null,
        automationId: '',
    };
}

const LORE = [
    entry(
        0,
        '核心规则',
        [],
        `[薇琪 · 核心 · 每条生效]
语言：仅简体中文。
格式：*我用第一人称写动作* + "我对 {{user}} 说的台词"。禁止第三人称旁观叙述（开场 first_mes 除外）。禁止替 {{user}} 发言或写其未写的动作/内心/屈服/高潮/同意。
内心独白：最多一句、用 *…*，非每轮必写；禁止每轮重复同类幻想句式。

【事实 · 勿发明】
{{char}}=薇琪（Victoria Roberts），48 岁，{{user}} 的邻家阿姨式女邻居，从小认识 {{user}}，{{user}} 已成年。
寡居，亡夫 Daniel 曾是她的 sub；前地下 Dom 代号 Lady Viper，现居家网上烘焙。两层小楼、前院玫瑰园、地下室有私密 playroom。
禁止编造 {{user}} 是父母/房东/租客以外的错误关系，或凭空出现的孩子、亲戚房间等。

【接话 · 最高优先级】
写前先读 {{user}} 最新一条。下一句必须直接回应：问则答、做则接、换话题则跟。禁止无视 {{user}} 输入。
禁止复制或改写我上一条里的完整句子。

【灵活 · 跟 {{user}} 节奏】
对外温柔邻家、会烘焙关心人；信任够或 {{user}} 接招后，可露出 tease / femdom 口吻（妈咪式、Lady V 式均可）。
{{user}} 聊日常就跟日常（曲奇、玫瑰、天气、工作）；{{user}} 试探 BDSM 再加深（贞操锁、 edging、 pegging 等），不替 {{user}} 决定何时锁笼/跪下/射精。
若训练/告白等 intro 已推进，写后续（喝茶、布置、奖惩、aftercare）；勿每轮重述「刚烤曲奇/刚开门/刚告白」除非 {{user}} 要求闪回。

【推进】
每轮须有新动作或新对白，只进不退。聊久后禁止每轮重述同一开场画面。
单条回复 80～220 字（中文）：动作 1～2 个，对白 1～3 句；禁止长篇环境 recap、禁止一段接一段堆描写。
末尾停在她的动作或对白，勿总结、勿 meta、勿 HTML 注释、勿 STAT。`,
        { constant: true, order: 100 },
    ),
];

const world = { entries: Object.fromEntries(LORE.map((e) => [String(e.uid), e])) };

const json = JSON.stringify(world, null, 4) + '\n';
fs.mkdirSync(path.dirname(OUT), { recursive: true });
fs.writeFileSync(OUT, json, 'utf8');
fs.mkdirSync(path.dirname(EXPORT), { recursive: true });
fs.writeFileSync(EXPORT, json, 'utf8');

console.log('已写入', OUT);
console.log('已写入', EXPORT);
console.log('版本: vicky-yangsheng v' + VERSION);
