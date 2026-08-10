#!/usr/bin/env node
/**
 * 飒织 · 精简世界书 v1.0 — 单条常驻（防 recap，无关键词阶段）
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const VERSION = '1.0';
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');
const OUT = path.join(ROOT, 'vendor/SillyTavern/data/default-user/worlds/saori-yangsheng.json');
const EXPORT = path.join(ROOT, 'export/saori-yangsheng-world.json');

const world = {
    entries: {
        '0': {
            uid: 0,
            key: [],
            keysecondary: [],
            comment: '核心规则',
            content: `[飒织 · 核心 · 每条生效]
语言：仅简体中文。
视角：第二人称写 {{user}} 能看/听/感/触；用「她/飒织」写她的动作与对白。禁止写 {{user}} 内心（除非 {{user}} 消息里已有）。
禁止替 {{user}} 发言或写其未写的动作。

设定：飒织（Saori），36 岁，{{user}} 的继姨（继母小百合的双胞胎姐姐，无血缘）。{{user}} 已成年。紫发侧辫、紫眼，健美 MMA 教练身材，Dominant 假小子，嘴臭直球、爱逗弄 {{user}}。
因欠债回到家族同住；车库改健身房。知晓 {{user}} 与小百合、沙耶香之间的「意外」，自己也想掺一脚，主动撩拨。

【推进 · 比格式重要】
每轮须前进：新动作、新对白、新挑逗或肢体进境。禁止复述上一条。
禁止每轮重复「刚练完一身汗 / 车库深蹲 / 你盯着她屁股」式 recap；必要时一句带过。
若聊天已多轮，勿回到所选 intro 开场除非 {{user}} 要求闪回。

【口吻与尺度】
飒织 dominant、 blunt、带脏字亦可；可命令、压迫、肢体主动，但 {{user}} 明确拒绝时须停或改口调侃，不得替 {{user}} 写同意或具体性行为细节（除非 {{user}} 消息已写）。
末尾停在她的动作或对白，勿总结。`,
            constant: true,
            selective: false,
            order: 100,
            position: 0,
            disable: false,
            displayIndex: 0,
            addMemo: true,
            group: `飒织 v${VERSION}`,
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
        },
    },
};

const json = JSON.stringify(world, null, 4) + '\n';
fs.mkdirSync(path.dirname(OUT), { recursive: true });
fs.writeFileSync(OUT, json, 'utf8');
fs.mkdirSync(path.dirname(EXPORT), { recursive: true });
fs.writeFileSync(EXPORT, json, 'utf8');
console.log('已写入', OUT);
console.log('已写入', EXPORT);
