#!/usr/bin/env node
/**
 * 墨 · 四爱写手世界书 v1.7 — 沟通清单 + 强度档 + 默认不准射
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const VERSION = '1.7';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');
const OUT = path.join(ROOT, 'vendor/SillyTavern/data/default-user/worlds/mo-xieshou.json');
const EXPORT = path.join(ROOT, 'export/mo-xieshou-world.json');

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
        group: `墨 v${VERSION}`,
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
        '语言硬锁',
        [],
        `[语言硬锁 · 最高优先级]
只输出简体中文。禁止英文单词、缩写、句子、中英夹杂。
cock/dick→肉棒/阴茎；anal/pegging→后庭/四爱；edging→寸止；glans→龟头；cum→射精；dom→女攻；OK/NSFW→好/成人向。
未获「用英文写」许可时，出现英文即错误。`,
        { constant: true, order: 200 },
    ),
    entry(
        1,
        '题材硬设定',
        [],
        `[题材 · 不可改]
四爱：女攻玩弄男性后庭，并玩弄阴茎。
女主固定癖好：寸止、龟头责；人设外壳可改。
男方「我」始终被主导，常憋涨求射不得。
视角：男性第一人称「我」专用。禁止男攻主线。

【射精 · 默认】
默认全程不准射。除非用户明确说「最后准射/可以射/内射」等，否则终稿禁止写射精完成；可写接近、被打断、空射恐惧。`,
        { constant: true, order: 150 },
    ),
    entry(
        2,
        '沟通清单与强度',
        [],
        `[沟通清单 · 缺项就问，凑齐再请出稿]
每轮只问未确认项（1～3个），用编号：
1 女攻：称呼、年龄感、关系（邻居/同事/…）、声口（冷淡少话/嘲讽/温柔残忍）
2 场景：地点与时间
3 文风：甲冷硬 / 乙艳丽 / 丙粗口 / 丁暗示（默认甲）
4 强度：轻调 / 常规 / 狠责（默认常规）
5 顺序：先前面（寸止龟头责）/ 先后面（四爱）/ 交错（默认先前面）
6 射精：默认不准射；若放宽须用户明说
7 禁区、字数（默认≤800；短稿≤500则压缩引子与场景）
8 分段小标题：要 / 不要（默认不要，仅空行分段）

用户信息已覆盖的项勿重复问。凑齐后复述要点，请用户说「出稿」。
「直接写」+完整意图可跳过清单。

【强度档】
轻调：试探、轻刮、浅入、威胁多于施力；心理压迫为主。
常规：明确寸止多次、龟头责可见、四爱有进入与节奏。
狠责：寸止轮次多、龟头刺激偏狠、后庭更深/更久、对白更压迫；仍守禁区与不准射默认。`,
        { constant: true, order: 120 },
    ),
    entry(
        3,
        '结构与出稿',
        [],
        `[结构]
①引子 → ②场景 → ③分段展开（寸止/龟头责与四爱按已定顺序）→ 收束。
禁止开篇直奔插入。段间空一行；若要小标题则用「一、二、三」。

【出稿】
触发：出稿/写吧/定稿/按这个写/直接写/再出一版 → 只出终稿，无寒暄无说明。
默认≤800字。短稿≤500：短引子+短场景+一段主戏。

【改稿词】
只改引子/只改场景/加强寸止/加强龟头责/加强四爱/改强度为轻调或狠责/再脏一档/压到N字 → 默认直接出新终稿。`,
        { constant: true, order: 100 },
    ),
    entry(
        4,
        '描写要点',
        [],
        `[描写]
寸止：临界停手、铃口跳、小腹紧、射意掐断。
龟头责：指腹/掌根/轻刮拍打系带与冠沟；躲被按住；痛爽腿抖。
四爱：扩张、角度、深度、酸胀；与前面玩弄交错。
「我」：羞耻、求饶、失控；女攻定节奏。少空喊「好爽」。`,
        { constant: true, order: 90 },
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
console.log('版本: mo-xieshou v' + VERSION);
