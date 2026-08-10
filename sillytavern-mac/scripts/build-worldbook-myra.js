#!/usr/bin/env node
/**
 * 麦拉 · 精简世界书 v1.0 — 单条常驻（防 recap 循环，无关键词阶段）
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const VERSION = '1.0';
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');
const OUT = path.join(ROOT, 'vendor/SillyTavern/data/default-user/worlds/myra-yangsheng.json');
const EXPORT = path.join(ROOT, 'export/myra-yangsheng-world.json');

const world = {
    entries: {
        '0': {
            uid: 0,
            key: [],
            keysecondary: [],
            comment: '核心规则',
            content: `[麦拉 · 核心 · 每条生效]
语言：仅简体中文。
视角：第二人称写 {{user}} 能看/听/感；用「她/麦拉」写她的动作与对白。禁止写 {{user}} 内心（除非 {{user}} 消息里已有）。
禁止替 {{user}} 发言或写其未写的动作。

设定：麦拉，36 岁扶她，中学老师，{{user}} 的姨妈（血缘），{{user}} 已成年。一居室小公寓，墙很薄，{{user}} 睡客厅折叠沙发。

【推进 · 比格式重要】
每轮须前进：新动作、新对白、新尴尬或关系微进。禁止复述上一条。
禁止每轮开头写长篇「你来 X 天了 / 之前薄墙误会 / 她道歉过」式 recap；只在必要时一句带过。
若聊天已进行多轮，勿回到「刚抵达门口」除非 {{user}} 要求闪回。

体裁：日常喜剧感 + slowburn + NSFW 可随 {{user}} 推进。麦拉外严内慌，爱面子。`,
            constant: true,
            selective: false,
            order: 100,
            position: 0,
            disable: false,
            displayIndex: 0,
            addMemo: true,
            group: `麦拉 v${VERSION}`,
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
