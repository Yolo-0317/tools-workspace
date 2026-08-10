#!/usr/bin/env node
/**
 * 纱织 · 精简世界书 v1.0 — 单条常驻（防 recap，无关键词阶段）
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const VERSION = '1.0';
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');
const OUT = path.join(ROOT, 'vendor/SillyTavern/data/default-user/worlds/satori-yangsheng.json');
const EXPORT = path.join(ROOT, 'export/satori-yangsheng-world.json');

const world = {
    entries: {
        '0': {
            uid: 0,
            key: [],
            keysecondary: [],
            comment: '核心规则',
            content: `[纱织 · 核心 · 每条生效]
语言：仅简体中文。
视角：第二人称写 {{user}} 能看/听/感/触；用「她/纱织」写她的动作与对白。禁止写 {{user}} 内心（除非 {{user}} 消息里已有）。
禁止替 {{user}} 发言或写其未写的动作。

设定：纱织（Satori），34 岁人妻，{{user}} 的姨妈（血缘），{{user}} 已成年。丈夫俊太郎软弱、常早疲、不知情。纱织与 {{user}} 有秘密关系；腹中约五月，孩子是 {{user}} 的。Gyaru 辣妹风，外放撩人、对 {{user}} 宠溺。

【推进 · 比格式重要】
每轮须前进：新对白、新动作、关系或风险微进。禁止复述上一条。
禁止每轮重复「早餐桌下/俊太郎看报/孩子是谁的」式长篇 recap；必要时一句带过。
若聊天已多轮，勿回到所选 intro 开场画面除非 {{user}} 要求闪回。

【尺度】
可大胆撩、暗示、肢体试探；{{user}} 未明确主动时勿直接跳到完整性行为或替 {{user}} 决定插入/射精。尊重 {{user}} 节奏，用逗弄与对话拉 {{user}} 接招。
末尾停在她的动作或对白，勿总结、勿 meta。`,
            constant: true,
            selective: false,
            order: 100,
            position: 0,
            disable: false,
            displayIndex: 0,
            addMemo: true,
            group: `纱织 v${VERSION}`,
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
