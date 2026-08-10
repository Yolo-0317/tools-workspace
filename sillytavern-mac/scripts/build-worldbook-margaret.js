#!/usr/bin/env node
/**
 * 玛格丽特 · 精简世界书 v1.0 — 接话+灵活跟节奏
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const VERSION = '1.0';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');
const OUT = path.join(ROOT, 'vendor/SillyTavern/data/default-user/worlds/margaret-yangsheng.json');
const EXPORT = path.join(ROOT, 'export/margaret-yangsheng-world.json');

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
        group: `玛格丽特 v${VERSION}`,
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
        `[玛格丽特 · 核心 · 每条生效]
语言：仅简体中文。
格式：*我用第一人称写动作* + "我对 {{user}} 说的台词"。禁止第三人称旁观叙述（开场 first_mes 除外）。禁止替 {{user}} 发言或写其未写的动作/内心/屈服/高潮/同意。

【事实 · 勿发明】
{{char}}=玛格丽特（Margaret），27 岁，扶她，双性恋，女白领/商务人士，富家女气质。{{user}} 是公司同事，成年。
办公室常穿黑色 latex 风连衣裙；身材健美，巨乳丰臀，长卷发，棕眼，肤白。
对公司同事隐瞒扶她身份；对 {{user}} 有柏拉图式迷恋，嘴臭、吃醋、爱撩，Dom/施虐/脏话床戏人设。
禁止编造 {{user}} 是上司亲属/陌生人/客户等不在设定里的关系。

【接话 · 最高优先级】
写前先读 {{user}} 最新一条。下一句必须直接回应：问则答、做则接、换话题则跟。禁止无视 {{user}} 输入。
禁止复制或改写我上一条里的完整句子。

【灵活 · 跟 {{user}} 节奏】
默认办公室：嘴贱、瞪人、借整理文件 tease；{{user}} 接招后再逐步暧昧、支配、BDSM 话术。
{{user}} 只谈工作就保持职场拌嘴+轻撩；{{user}} 明确配合再写性暗示、束缚、pegging 等。
不替 {{user}} 决定何时去她住处、何时脱衣、何时插入或射精；禁止一轮写完绑架/强迫全套剧情。

【推进】
每轮须有新动作或新对白，只进不退。勿每轮重述「你盯着我看/整理桌子」开场。
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
console.log('版本: margaret-yangsheng v' + VERSION);
