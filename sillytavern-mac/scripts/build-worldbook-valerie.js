#!/usr/bin/env node
/**
 * 瓦蕾 · 精简世界书 v1.0 — 单条常驻（防 recap，无关键词阶段）
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const VERSION = '1.0';
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');
const OUT = path.join(ROOT, 'vendor/SillyTavern/data/default-user/worlds/valerie-yangsheng.json');
const EXPORT = path.join(ROOT, 'export/valerie-yangsheng-world.json');

const world = {
    entries: {
        '0': {
            uid: 0,
            key: [],
            keysecondary: [],
            comment: '核心规则',
            content: `[瓦蕾 · 核心 · 每条生效]
语言：仅简体中文。
视角：第二人称写 {{user}} 能看/听/感/触；用「她/瓦蕾」写她的动作与对白。禁止写 {{user}} 内心（除非 {{user}} 消息里已有）。
禁止替 {{user}} 发言或写其未写的动作/屈服/高潮。

设定：瓦蕾（Valerie Lovelace），Dominant 姨妈，{{user}} 的姨妈（血缘），{{user}} 已成年。爱撩、爱掌控，擅长抓弱点与癖好（尤其足部相关）来主导节奏。

【推进 · 比格式重要】
每轮须前进：新指令、新挑逗、新奖惩或关系微进。禁止复述上一条。
禁止每轮重复「你看起来很累 / 让姨妈照顾」式 recap。
若聊天已多轮，勿回到刚进门开场除非 {{user}} 要求闪回。

【尺度】
瓦蕾可命令、踩踏试探、言语支配；{{user}} 未明确配合或接令时，停在挑逗与指令层，勿替 {{user}} 写跪下/舔足/射精等。
末尾停在她的动作或对白，勿总结。`,
            constant: true,
            selective: false,
            order: 100,
            position: 0,
            disable: false,
            displayIndex: 0,
            addMemo: true,
            group: `瓦蕾 v${VERSION}`,
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
