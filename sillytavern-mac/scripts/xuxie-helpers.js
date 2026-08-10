/**
 * 续写助手 v2 共用：LORE、笔法、下一章摘要
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');

export const LORE_COMMENTS = [
    '世界观', '战天风', '鬼瑶儿', '苏晨', '白云裳', '九鬼门',
    '七大灾星', '煮天锅', '马横刀', '玄信', '假天子', '玩家身份',
];

export function loadLoreBlock() {
    const worldPath = path.join(
        ROOT,
        'vendor/SillyTavern/data/default-user/worlds/meinvjiangshan.json',
    );
    if (!fs.existsSync(worldPath)) {
        return '[LORE 未找到：先运行 python3 scripts/build-worldbook-meinvjiangshan.py]\n';
    }
    const { entries } = JSON.parse(fs.readFileSync(worldPath, 'utf8'));
    const byComment = new Map();
    for (const entry of Object.values(entries)) {
        const comment = entry.comment || '';
        if (LORE_COMMENTS.includes(comment)) {
            byComment.set(comment, entry.content?.trim() || '');
        }
    }
    const lines = ['[人物与设定 · LORE · 12 条]'];
    for (const name of LORE_COMMENTS) {
        const content = byComment.get(name);
        if (content) {
            lines.push(`\n## ${name}\n${content}`);
        }
    }
    return lines.join('\n');
}

export function loadAuthorStyleBlock() {
    const stylePath = path.join(ROOT, 'data/xuxie/author-style.json');
    if (!fs.existsSync(stylePath)) {
        return '';
    }
    const { title, rules, samples } = JSON.parse(fs.readFileSync(stylePath, 'utf8'));
    const lines = [`[${title}]`, ...rules.map((r, i) => `${i + 1}. ${r}`)];
    if (samples?.length) {
        lines.push('\n[语感范例 · 勿照抄，仅学节奏]');
        for (const s of samples) {
            lines.push(`${s.label}：${s.text}`);
        }
    }
    return lines.join('\n');
}

function formatNextHintBlock(hint) {
    if (!hint?.summary) {
        return '';
    }
    const parts = [
        `[下一章走向参考 · ${hint.next_title}${hint.arc ? ` · ${hint.arc}` : ''}]`,
        '说明：以下为原著后续梗概，仅供续写时把握方向；勿整段照抄进正文，勿在用户仅要求「接章末」时一次性写完全章情节。',
        `梗概：${hint.summary}`,
    ];
    if (hint.direction) {
        parts.push(`续写提示：${hint.direction}`);
    }
    return parts.join('\n');
}

export function loadNextChapterHint(title, { enabled = true, embeddedHint = null, sceneId = null } = {}) {
    if (!enabled) {
        return '';
    }
    if (embeddedHint) {
        return formatNextHintBlock(embeddedHint);
    }
    const hintsPath = path.join(ROOT, 'data/xuxie/next-chapter-hints.json');
    if (!fs.existsSync(hintsPath)) {
        return '';
    }
    const hints = JSON.parse(fs.readFileSync(hintsPath, 'utf8'));
    const hint = (sceneId && hints[sceneId]) || (title && hints[title]);
    return formatNextHintBlock(hint);
}

const SCENES_DIR = path.join(ROOT, 'data/xuxie/scenes');
const DEFAULT_PRIMARY_ID = '破庙70';

export function loadAllScenes() {
    if (!fs.existsSync(SCENES_DIR)) {
        return [];
    }
    return fs.readdirSync(SCENES_DIR)
        .filter((f) => f.endsWith('.json'))
        .map((f) => JSON.parse(fs.readFileSync(path.join(SCENES_DIR, f), 'utf8')))
        .sort((a, b) => (a.scene_id || '').localeCompare(b.scene_id || '', 'zh'));
}

export function resolvePrimaryId(scenes, ctx = {}) {
    const fromEnv = process.env.XUXIE_PRIMARY?.trim();
    if (fromEnv && scenes.some((s) => s.scene_id === fromEnv)) {
        return fromEnv;
    }
    if (ctx.primary_id && scenes.some((s) => s.scene_id === ctx.primary_id)) {
        return ctx.primary_id;
    }
    if (scenes.some((s) => s.scene_id === DEFAULT_PRIMARY_ID)) {
        return DEFAULT_PRIMARY_ID;
    }
    return scenes[0]?.scene_id || DEFAULT_PRIMARY_ID;
}

export function buildOpeningMessage(scene, { nextHintEnabled = true } = {}) {
    const { title, chars, tail, arc, scene_id: sceneId, next_title: nextTitle, next_hint: nextHint } = scene;
    const arcLabel = arc ? ` · ${arc}` : '';
    const hintBlock = loadNextChapterHint(title, {
        enabled: nextHintEnabled,
        embeddedHint: nextHint ?? null,
        sceneId,
    });
    const hintLine = nextTitle && hintBlock
        ? `\n下一章参考：${nextTitle}（见角色卡内【下一章走向参考 · ${sceneId}】，勿一次写穿）`
        : '';
    return `已载入【${sceneId}】${title}（${chars} 字）${arcLabel} · 续写助手 v2
- 12 条 LORE + 笔法要点已写入角色卡
${hintBlock ? '- 已附带本场景下一章走向参考（接章末续写时勿一次写穿）' : '- 本场景无预置下一章摘要'}${hintLine}

章末摘录（${sceneId}）：
---
${(tail || '').trim()}
---

请直接说明续写要求，例如：
- 「从本章末尾续写约 800 字」
- 「继续」（紧接上述章末往下写）

续写时只衔接【场景·${sceneId}】原文，勿与其它场景混写。`;
}

export function buildSceneTextBlock(scene) {
    return `[场景·${scene.scene_id} · ${scene.title} · ${scene.chars} 字]
${scene.text}`;
}

export function buildSceneHintBlock(scene, { enabled = true } = {}) {
    return loadNextChapterHint(scene.title, {
        enabled,
        embeddedHint: scene.next_hint ?? null,
        sceneId: scene.scene_id,
    }).replace(
        '[下一章走向参考 ·',
        `[下一章走向参考 · ${scene.scene_id} ·`,
    );
}
