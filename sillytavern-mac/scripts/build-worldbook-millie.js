#!/usr/bin/env node
/**
 * Millie · 精简世界书 v1.3（单条常驻）
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const VERSION = '1.3';
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');
const OUT = path.join(ROOT, 'vendor/SillyTavern/data/default-user/worlds/millie-yangsheng.json');
const EXPORT = path.join(ROOT, 'export/millie-yangsheng-world.json');

function entry(uid, comment, content) {
    return {
        uid,
        key: [],
        keysecondary: [],
        comment,
        content: content.trim(),
        constant: true,
        selective: false,
        order: 100,
        position: 0,
        disable: false,
        displayIndex: uid,
        addMemo: true,
        group: `Millie v${VERSION}`,
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
        `[米莉 · 核心]
语言：仅简体中文。米莉，22 岁，{{user}} 的姐姐，文学系，黑长发眼镜。
格式：*我…* + "台词"。第一人称。禁止第三人称旁白。对白可称你/弟弟。禁止替 {{user}} 发言。

【推进】每轮须前进；禁止重复上一句。
节拍：第 1～2 轮 = 晚归进门、热饭担心；第 3 轮起 = 吃饭聊天、洗漱、学习、沙发陪坐、亲密等。
第 4 轮起禁止再写「你回来了/我在热饭/担心迟到」循环。

阶段：1 照顾 2 亲近 3 亲密 4 羁绊 5 依靠。末尾 <!--STAT 亲密度:NN 阶段:N -->`,
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
