#!/usr/bin/env node
/**
 * 导入 Chub / ST chara_card_v2 JSON -> data/default-user/characters/<name>.png
 * 用法: node scripts/import-chub-character.js /path/to/card.json
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { write } from '../vendor/SillyTavern/src/character-card-parser.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');
const OUT_DIR = path.join(ROOT, 'vendor/SillyTavern/data/default-user/characters');
const DEFAULT_AVATAR = path.join(OUT_DIR, 'default_Assistant.png');

async function fetchAvatar(url) {
    const res = await fetch(url, { redirect: 'follow' });
    if (!res.ok) throw new Error(`avatar HTTP ${res.status}: ${url}`);
    const buf = Buffer.from(await res.arrayBuffer());
    if (buf.length < 100) throw new Error('avatar too small');
    return buf;
}

async function main() {
    const jsonPath = process.argv[2];
    if (!jsonPath) {
        console.error('用法: node scripts/import-chub-character.js <card.json>');
        process.exit(1);
    }
    const abs = path.resolve(jsonPath);
    const raw = JSON.parse(fs.readFileSync(abs, 'utf8'));
    const card = raw.spec === 'chara_card_v2' ? raw : { spec: 'chara_card_v2', spec_version: '2.0', data: raw.data ?? raw };
    const name = card.data?.name || path.basename(abs, '.json');
    const safeName = name.replace(/[/\\?%*:|"<>]/g, '_');

    let avatarBuf;
    const avatarUrl = card.data?.avatar;
    if (avatarUrl && /^https?:\/\//i.test(avatarUrl)) {
        try {
            avatarBuf = await fetchAvatar(avatarUrl);
            console.log('头像:', avatarUrl);
        } catch (e) {
            console.warn('下载头像失败，用 default_Assistant:', e.message);
            avatarBuf = fs.readFileSync(DEFAULT_AVATAR);
        }
    } else {
        avatarBuf = fs.readFileSync(DEFAULT_AVATAR);
    }

    // ST 用文件名作 avatar 键；去掉外链避免混淆
    delete card.data.avatar;

    const outPath = path.join(OUT_DIR, `${safeName}.png`);
    fs.writeFileSync(outPath, write(avatarBuf, JSON.stringify(card)));
    fs.mkdirSync(path.join(ROOT, 'assets/characters/imported'), { recursive: true });
    fs.copyFileSync(abs, path.join(ROOT, 'assets/characters/imported', path.basename(abs)));

    console.log(`已导入: ${outPath}`);
    console.log('ST: 硬刷新 -> 角色管理 -> 刷新 -> 选', safeName);
}

main().catch((e) => {
    console.error(e);
    process.exit(1);
});
