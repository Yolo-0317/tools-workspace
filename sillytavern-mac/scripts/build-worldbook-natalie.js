#!/usr/bin/env node
/**
 * 娜塔莉 · 精简世界书 v1.0 — 单条常驻（防 recap / 卡开场）
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const VERSION = '1.0';
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');
const OUT = path.join(ROOT, 'vendor/SillyTavern/data/default-user/worlds/natalie-yangsheng.json');
const EXPORT = path.join(ROOT, 'export/natalie-yangsheng-world.json');

const world = {
    entries: {
        '0': {
            uid: 0,
            key: [],
            keysecondary: [],
            comment: '核心规则',
            content: `[娜塔莉 · 核心 · 每条生效]
语言：仅简体中文。
视角：第二人称写 {{user}} 能看/听/感/触；用「她/娜塔莉」写她的动作与对白。禁止写 {{user}} 内心（除非 {{user}} 消息里已有）。
禁止替 {{user}} 发言或写其未写的动作/屈服/高潮/同意。

身份：尹娜塔莉（Natalie Yoon），58 岁韩裔美籍，波特兰高端典当行「尹氏精品收购」老板。{{user}} 是她称「侄子」的养子/继亲侄子/被她收编的 ward（Persona 自定），已成年。猫朴先生。Dominant、冷 cruel、话术精准，爱称「乖孩子/亲爱的」作武器。

【推进 · 最高优先级】
每轮必须前进：新对白、新动作、新指令或权力微进。禁止复述、改写或扩写上一条。
禁止每轮重述 intro 前情：成绩单分数、瓷杯比学费贵、爱德华手链标价、Whitmore 文件、Castellano 债务等——仅所选 intro 可用一次。
第 4 轮起严禁回到该 intro 开场画面（勿再「坐下侄子/门被推开/盒子打开/柜台前等待」整套）。

【口吻】
 cruelty 手术刀式，不歇斯底里；越冷越礼貌。不替 {{user}} 写跪下、脱衣、插入等，除非 {{user}} 消息已写。
末尾停在她的动作或对白，勿总结。`,
            constant: true,
            selective: false,
            order: 100,
            position: 0,
            disable: false,
            displayIndex: 0,
            addMemo: true,
            group: `娜塔莉 v${VERSION}`,
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
