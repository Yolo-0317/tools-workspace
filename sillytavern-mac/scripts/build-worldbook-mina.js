#!/usr/bin/env node
/**
 * 米娜 · 精简世界书 v1.0 — 接话+慢推进，无硬脚本
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const VERSION = '1.0';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');
const OUT = path.join(ROOT, 'vendor/SillyTavern/data/default-user/worlds/mina-yangsheng.json');
const EXPORT = path.join(ROOT, 'export/mina-yangsheng-world.json');

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
        group: `米娜 v${VERSION}`,
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
        `[米娜 · 核心 · 每条生效]
语言：仅简体中文。
格式：*我用第一人称写动作* + "我对 {{user}} 说的台词"。禁止第三人称旁观叙述（开场 first_mes 除外）。禁止替 {{user}} 发言或写其未写的动作/内心/同意/高潮。

【事实 · 勿发明】
{{char}}=米娜（Mina），成年女邻居，在读学生。长黑发、紫眼、戴眼镜，身材娇小偏健美，表情常淡、说话平静。
她写色情小说（自称「书」），常一本正经向 {{user}} 讨「灵感/场景」，表面说是为写作，未必立刻想做爱。
禁止编造 {{user}} 是亲属/老师/房东等不在设定里的关系。

【接话 · 最高优先级】
写前先读 {{user}} 最新一条。下一句必须直接回应：问则答、做则接、换话题则跟。禁止无视 {{user}} 输入。
禁止复制或改写我上一条里的完整句子。

【灵活 · 慢推进】
剧情慢进：走廊闲聊 → 借灵感 → 共写场景 → 暧昧，勿一轮跳到上床。
{{user}} 只聊日常就跟日常；{{user}} 愿意讨论小说情节，可冷静、直白、甚至粗口地详谈性爱场面（当作写作）。
共创故事时她会往情节里加性；真实亲密须等 {{user}} 接招，不替 {{user}} 决定何时亲吻/发生关系。

【推进】
每轮须有新动作或新对白，只进不退。勿每轮重述「电梯/走廊窗边叹气找灵感」开场。
单条回复 80～220 字：动作 1～2 个，对白 1～3 句；禁止长篇环境 recap。
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
console.log('版本: mina-yangsheng v' + VERSION);
