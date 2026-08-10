#!/usr/bin/env node
/**
 * 生成「续写助手」角色卡 v2：
 * - description 嵌入 data/xuxie/scenes/ 下全部场景原文
 * - first_mes = 主开场（默认破庙70）；alternate_greetings = 其余场景开场
 * 依赖: chapter-continue.sh 更新 current.json / 场景文件后调用
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { write } from '../vendor/SillyTavern/src/character-card-parser.js';
import {
    buildOpeningMessage,
    buildSceneHintBlock,
    buildSceneTextBlock,
    loadAllScenes,
    loadAuthorStyleBlock,
    loadLoreBlock,
    resolvePrimaryId,
} from './xuxie-helpers.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');
const OUT_DIR = path.join(ROOT, 'vendor/SillyTavern/data/default-user/characters');
const CONTEXT = path.join(ROOT, 'data/chapter-context/current.json');
const AVATAR_SRC = path.join(ROOT, 'vendor/SillyTavern/data/default-user/characters/default_Assistant.png');

const nextHintEnabled = process.env.CONTINUE_NEXT_HINT !== '0';

const ctx = fs.existsSync(CONTEXT)
    ? JSON.parse(fs.readFileSync(CONTEXT, 'utf8'))
    : {};

const scenes = loadAllScenes();
if (!scenes.length) {
    console.error('缺少场景文件。先运行: bash scripts/chapter-continue.sh 70');
    process.exit(1);
}

const primaryId = resolvePrimaryId(scenes, ctx);
const primary = scenes.find((s) => s.scene_id === primaryId) || scenes[0];
const alternates = scenes.filter((s) => s.scene_id !== primary.scene_id);

const loreBlock = loadLoreBlock();
const styleBlock = loadAuthorStyleBlock();

const sceneBlocks = scenes.flatMap((scene) => {
    const parts = [buildSceneTextBlock(scene)];
    const hint = buildSceneHintBlock(scene, { enabled: nextHintEnabled });
    if (hint) {
        parts.push(hint);
    }
    return parts;
});

const blocks = [
    `[任务]
你是《美女江山一锅煮》的续写助手（v2）。角色卡内按【场景·id】收录多段原文；用户选定开场后，只续写对应场景，勿与其它场景混写。

[续写规则]
- 简体中文武侠白话，第三人称全知视角，贴近原作者叙述节奏。
- 不得篡改所选【场景·id】原文已发生的事实；续写须自然衔接该场景章末。
- 人物口吻见 LORE 与笔法要点；战天风滑头贫嘴，鬼瑶儿冷傲嘴硬（破庙线尤甚）。
- 禁止：现代网络梗、日语、出戏说明、元评论、小标题、Markdown、网站广告句。
- 每次只输出小说正文；用户说「继续」则接着写，不重复已写段落。
- 用户未指定字数时，每次约 600～1000 字。`,

    styleBlock,
    loreBlock,
    '[收录场景 · 按 id 选用，勿跨场景混写]',
    ...sceneBlocks,
].filter(Boolean);

const description = blocks.join('\n\n');

const personality = `严谨、熟悉原著 LORE 与笔法；续写时注重衔接、人设与武侠语感；不扮演单一角色，而是叙述者/作者续笔。`;

const scenario = `章节续写 v2 · 多场景。主开场【${primary.scene_id}】；备选开场 ${alternates.map((s) => s.scene_id).join('、') || '无'}。用户 {{user}} 为执笔者。`;

const first_mes = buildOpeningMessage(primary, { nextHintEnabled });
const alternate_greetings = alternates.map((scene) =>
    buildOpeningMessage(scene, { nextHintEnabled }),
);

const system_prompt = `You continue the Chinese wuxia novel 《美女江山一锅煮》 as a literary co-author (v2).
Follow LORE, author style rules, and the scene text in {{char}} description matching the user's chosen opening.
Output ONLY new prose in Chinese. No OOC. No English.`;

const post_history_instructions = `Stay in novel-narrator mode. Honor LORE character voices. Continue only from the scene the user selected; do not restart or mix scenes. No meta commentary.`;

const card = {
    spec: 'chara_card_v2',
    spec_version: '2.0',
    data: {
        name: '续写助手',
        description,
        personality,
        scenario,
        first_mes,
        alternate_greetings,
        mes_example: `<START>
{{user}}: 从本章末尾续写约 800 字
{{char}}: *（接章末情节，以原著笔法续写正文，第三人称，约 800 字）*`,
        creator_notes: `续写助手 v2 多场景。主开场=${primary.scene_id}；备选=${alternates.map((s) => s.scene_id).join(',') || '无'}。data/xuxie/scenes/ 增场景后重跑 chapter-continue.sh。`,
        system_prompt,
        post_history_instructions,
        tags: ['续写', '美女江山一锅煮', '写作', 'v2'],
        creator: 'sillytavern-mac',
        character_version: '2.1',
        extensions: {
            talkativeness: '0.5',
            fav: false,
            world: 'meinvjiangshan',
        },
    },
};

if (!fs.existsSync(AVATAR_SRC)) {
    console.error('缺少头像:', AVATAR_SRC);
    process.exit(1);
}

const png = fs.readFileSync(AVATAR_SRC);
const out = write(png, JSON.stringify(card));
const outPath = path.join(OUT_DIR, '续写助手.png');
fs.writeFileSync(outPath, out);

console.log(`已写入 ${outPath}`);
console.log(`  主开场: ${primary.scene_id}（${primary.title}）`);
console.log(`  备选开场: ${alternates.map((s) => s.scene_id).join(', ') || '无'}`);
console.log(`  description 约 ${description.length} 字（${scenes.length} 个场景）`);
console.log('ST: 选「续写助手」-> 新建聊天 -> 点开场旁切换按钮选备选场景');
