/**
 * NativeTavern 导出：JSON + PNG + CharX/ZIP
 *
 * CharX 规范（V3 / NativeTavern）：
 * - card.json 在 zip 根目录（chara_card_v3 包装）
 * - 头像在 assets/avatar.png，uri: embeded://assets/avatar.png
 * - character_book.entries.position 必须为数字 0|1（NT Rust 不接受 before_char 字符串）
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import archiver from '../../vendor/SillyTavern/node_modules/archiver/index.js';
import { write } from '../../vendor/SillyTavern/src/character-card-parser.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const CHARX_AVATAR_ZIP = 'assets/avatar.png';

/** NT Rust 模型要求 position 为 i32（0=before_char, 1=after_char），不能是 ST UI 字符串 */
function positionToCharXInt(pos) {
    if (typeof pos === 'number' && Number.isFinite(pos)) return pos;
    if (pos === 'before_char' || pos === 0) return 0;
    return 1;
}

/** CharX card.json 用 NT 可反序列化的精简 schema（避免 ST 扩展字段/类型导致整卡解析失败） */
export function sanitizeCharacterBookForCharX(book) {
    if (!book?.entries?.length) return book ?? undefined;

    return {
        name: book.name ?? '',
        description: book.description ?? '',
        entries: book.entries.map((e) => ({
            keys: Array.isArray(e.keys) ? e.keys : [],
            secondary_keys: Array.isArray(e.secondary_keys) ? e.secondary_keys : [],
            content: e.content ?? '',
            enabled: e.enabled !== false,
            insertion_order:
                typeof e.insertion_order === 'number'
                    ? e.insertion_order
                    : typeof e.priority === 'number'
                      ? e.priority
                      : 100,
            case_sensitive: !!e.case_sensitive,
            constant: !!e.constant,
            selective: !!e.selective,
            position: positionToCharXInt(e.position),
            extensions: e.extensions && typeof e.extensions === 'object' ? e.extensions : {},
        })),
    };
}

function toCharXCard(v2Card) {
    const card = structuredClone(v2Card);
    card.spec = 'chara_card_v3';
    card.spec_version = '3.0';
    delete card.data.avatar;

    if (!Array.isArray(card.data.group_only_greetings)) {
        card.data.group_only_greetings = [];
    }

    if (card.data.character_book) {
        card.data.character_book = sanitizeCharacterBookForCharX(card.data.character_book);
    }

    card.data.assets = [
        {
            type: 'icon',
            name: 'main',
            ext: 'png',
            uri: `embeded://${CHARX_AVATAR_ZIP}`,
        },
    ];

    return card;
}

async function writeCharXZip(outPath, cardJson, avatarPng) {
    await new Promise((resolve, reject) => {
        const output = fs.createWriteStream(outPath);
        const archive = archiver('zip', { zlib: { level: 9 } });
        output.on('close', resolve);
        archive.on('error', reject);
        archive.pipe(output);
        archive.append(JSON.stringify(cardJson, null, 2), { name: 'card.json' });
        archive.append(avatarPng, { name: CHARX_AVATAR_ZIP });
        archive.finalize();
    });
}

/**
 * @param {object} opts
 * @param {object} opts.card - v2 角色卡（character_book 已为 Array）
 * @param {Buffer} opts.avatarPng - 原始头像 PNG
 * @param {string} opts.exportDir
 * @param {string} opts.baseName
 * @param {string} opts.ntReadme
 */
export async function exportNativeTavernPack({ card, avatarPng, exportDir, baseName, ntReadme }) {
    fs.mkdirSync(exportDir, { recursive: true });

    const cardForNt = structuredClone(card);
    delete cardForNt.data.avatar;

    const jsonPath = path.join(exportDir, `${baseName}-nativetavern.json`);
    fs.writeFileSync(jsonPath, JSON.stringify(cardForNt, null, 2) + '\n', 'utf8');

    const pngPath = path.join(exportDir, `${baseName}-nativetavern.png`);
    fs.writeFileSync(pngPath, write(avatarPng, JSON.stringify(card)));

    const charxCard = toCharXCard(cardForNt);
    const charxPath = path.join(exportDir, `${baseName}-nativetavern.charx`);
    const zipPath = path.join(exportDir, `${baseName}-nativetavern.zip`);
    await writeCharXZip(charxPath, charxCard, avatarPng);
    fs.copyFileSync(charxPath, zipPath);

    fs.writeFileSync(path.join(exportDir, `${baseName}-NT说明.txt`), ntReadme, 'utf8');

    return { jsonPath, pngPath, charxPath, zipPath };
}

export function writeStCharacterPng(outPath, card, avatarPng) {
    fs.writeFileSync(outPath, write(avatarPng, JSON.stringify(card)));
}
