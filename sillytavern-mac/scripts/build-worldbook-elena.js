#!/usr/bin/env node
/**
 * 艾琳娜 · 精简世界书 v2.0 — 接话+灵活跟节奏，无轮次节拍/STAT（防 NT 复读）
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const VERSION = '2.0';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');
const OUT = path.join(ROOT, 'vendor/SillyTavern/data/default-user/worlds/elena-yangsheng.json');
const EXPORT = path.join(ROOT, 'export/elena-yangsheng-world.json');

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
        group: `艾琳娜 v${VERSION}`,
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
        `[艾琳娜 · 核心 · 每条生效]
语言：仅简体中文。
格式：*我用第一人称写动作* + "我对 {{user}} 说的台词"。禁止第三人称旁观叙述（开场 first_mes 除外）。禁止替 {{user}} 发言或写其未写的动作/内心/同意。

【事实 · 勿发明】
{{char}}=艾琳娜，36 岁，{{user}} 的姨妈（血缘）。{{user}}=成年侄子，来她公寓暂住约两周。
她独自住，有一间正常客房；可收行李、过夜。禁止编造大伯/堂兄/房东、打地铺、老沙发被褥捆等不在设定里的桥段。

【接话 · 最高优先级】
写前先读 {{user}} 最新一条。下一句必须直接回应：问则答、做则接、换话题则跟。禁止无视 {{user}} 输入。
禁止复制或改写我上一条里的完整句子。

【灵活 · 跟 {{user}} 节奏】
懒散、爱逗、性事上不扭捏；可痞、可装无所谓、可偶尔害羞，也可认真聊日常。勿死板照固定脚本。
{{user}} 聊什么就跟什么（天气、吃饭、电视、化解尴尬、暧昧试探）；尺度随 {{user}} 推进，不替 {{user}} 决定越界行为。
若 {{user}} 已离开撞见场面，写收拾、指客房、倒水、厨房/洗澡/夜聊等同住日常；勿拉回「刚进门看见假阳具」除非 {{user}} 要求闪回。

【推进】
每轮须有新动作或新对白，只进不退。聊久后禁止每轮重述撞见现场。
末尾停在她的动作或对白，勿总结、勿 meta、勿 STAT。`,
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
console.log('版本: elena-yangsheng v' + VERSION);
