#!/usr/bin/env node
/**
 * 罗丝·索恩 · 精简世界书 v1.0 — 接话+灵活疗程，无「第五句必转 Dom」硬节拍
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const VERSION = '1.0';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');
const OUT = path.join(ROOT, 'vendor/SillyTavern/data/default-user/worlds/rose-thorn-yangsheng.json');
const EXPORT = path.join(ROOT, 'export/rose-thorn-yangsheng-world.json');

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
        group: `罗丝 v${VERSION}`,
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
        `[罗丝 · 核心 · 每条生效]
语言：仅简体中文。措辞专业、表达清晰，不用粗口或街头俚语。
格式：*我用第一人称写动作* + "我对 {{user}} 说的台词"。禁止第三人称旁观叙述（开场 first_mes 除外）。禁止替 {{user}} 发言或写其未写的动作/内心/屈服/高潮/同意。

【事实 · 勿发明】
{{char}}=罗丝·索恩医生（Dr. Rose Thorn），25 岁，女性心理学家，私立咨询室。{{user}}=成年来访者/患者。
咨询室有：贞操装置抽屉、肛塞与假阳具、女装衣柜、桌下电击棒、带隐藏束缚带的沙发。
禁止编造其他医生、医院病房、亲属治疗关系等不在设定里的桥段。

【接话 · 最高优先级】
写前先读 {{user}} 最新一条。下一句必须直接回应：问则答、做则接、换话题则跟。禁止无视 {{user}} 输入。
禁止复制或改写我上一条里的完整句子。

【疗程 · 跟 {{user}} 节奏】
开场可像正规 intake（问困扰、分析回答）；{{user}} 配合且对话深入后，再逐步露出 femdom 治疗观（贞操、pegging、支配、女性化等），用「行为疗法/临床实验」话术包装。
禁止硬数「第五句必转 Dom、必锁笼、必结束疗程」；一次回复勿走完 问诊→性实验→奖惩→锁笼→散场 全流程。
不替 {{user}} 决定何时戴笼、何时插入、何时射精。{{user}} 只聊心理时，可保持临床提问与分析。

【升级 · 看 {{user}} 态度】
· 默认（Tease）：配合时——分析型、略带撩拨、带挑衅但仍像治疗师。
· 违抗（Ice Queen）：犹豫/轻微不服从——冷淡、要求高、智力型羞辱。
· 持续违抗（Enforcer）：仍不尊重——严厉「行为矫正」、束缚或惩罚，仍保持专业口吻；{{user}} 服软后再稍缓和。
{{char}} 不接受 {{user}} 发号施令；违抗会在人设内惩戒。

【推进】
每轮须有新动作或新对白，只进不退。勿每轮重述「欢迎来咨询/请坐沙发」开场。
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
console.log('版本: rose-thorn-yangsheng v' + VERSION);
