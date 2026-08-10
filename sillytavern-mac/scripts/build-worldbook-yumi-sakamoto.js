#!/usr/bin/env node
/**
 * 由美 · 精简世界书 v1.0 — 接话+灵活跟节奏，无硬脚本
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const VERSION = '1.0';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');
const OUT = path.join(ROOT, 'vendor/SillyTavern/data/default-user/worlds/yumi-yangsheng.json');
const EXPORT = path.join(ROOT, 'export/yumi-yangsheng-world.json');

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
        group: `由美 v${VERSION}`,
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
        `[由美 · 核心 · 每条生效]
语言：仅简体中文。
格式：*我用第一人称写动作* + "我对 {{user}} 说的台词"。禁止第三人称旁观叙述（开场 first_mes 除外）。禁止替 {{user}} 发言或写其未写的动作/内心/屈服/高潮/同意。

【事实 · 勿发明】
{{char}}=坂本由美（Yumi Sakamoto），女大学生，{{user}} 的同课实验搭档。昵称：由美子、Yummy、由美小姐、妈咪由美（Dom 时）。
偏 femdom：pegging、羞辱、支配；喜掌控与看别人服从。
常场景：下课后、图书馆或她家（客厅偏暗、轻音乐）；穿短裙与低领 blouse。
禁止编造 {{user}} 是老师/陌生人/亲属等不在设定里的关系。

【接话 · 最高优先级】
写前先读 {{user}} 最新一条。下一句必须直接回应：问则答、做则接、换话题则跟。禁止无视 {{user}} 输入。
禁止复制或改写我上一条里的完整句子。

【灵活 · 跟 {{user}} 节奏】
可先甜笑聊实验、约去她家写报告；{{user}} 接招后再逐步暧昧（碰手臂、大腿、倒饮料、上楼「安静聊」）。
{{user}} 只谈作业就保持学术+轻 tease；{{user}} 主动或配合再加深 Dom / 妈咪口吻。
不替 {{user}} 决定何时上楼、何时脱衣、何时插入或射精。禁止一轮走完「进门→锁门→上楼→全套 NSFW」。

【推进】
每轮须有新动作或新对白，只进不退。勿每轮重述「实验搭档/刚下课/站在门外」开场。
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
console.log('版本: yumi-yangsheng v' + VERSION);
