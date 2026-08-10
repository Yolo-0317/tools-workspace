#!/usr/bin/env node
/**
 * 玛格丽特 v1.0.0-zh — 中译 + 单条嵌入世界书（参考由美 v1.0）
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { exportNativeTavernPack, writeStCharacterPng } from './lib/export-nativetavern-pack.js';
import { worldToCharacterBook } from './lib/world-to-character-book.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');
const OUT_DIR = path.join(ROOT, 'vendor/SillyTavern/data/default-user/characters');
const WORLD_PATH = path.join(ROOT, 'vendor/SillyTavern/data/default-user/worlds/margaret-yangsheng.json');
const AVATAR_URL =
    'https://avatars.charhub.io/avatars/Anonymous/margaret-c499170a47fd/chara_card_v2.png';
const AVATAR_LOCAL = path.join(ROOT, 'assets/characters/avatars/margaret-src.png');

async function ensureAvatar() {
    fs.mkdirSync(path.dirname(AVATAR_LOCAL), { recursive: true });
    try {
        const res = await fetch(AVATAR_URL, { redirect: 'follow' });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const buf = Buffer.from(await res.arrayBuffer());
        if (buf.length < 1000) throw new Error('avatar too small');
        fs.writeFileSync(AVATAR_LOCAL, buf);
        console.log('头像已更新:', AVATAR_URL);
        return buf;
    } catch (e) {
        if (fs.existsSync(AVATAR_LOCAL)) {
            console.warn('下载头像失败，用本地缓存:', e.message);
            return fs.readFileSync(AVATAR_LOCAL);
        }
        throw e;
    }
}

function loadWorldBook() {
    if (!fs.existsSync(WORLD_PATH)) {
        console.warn('警告: 未找到世界书，先运行 node scripts/build-worldbook-margaret.js');
        return null;
    }
    const world = JSON.parse(fs.readFileSync(WORLD_PATH, 'utf8'));
    return worldToCharacterBook(world, {
        name: 'margaret-yangsheng',
        description: '玛格丽特核心规则 v1.0',
        scan_depth: 1,
        token_budget: 512,
    });
}

const description = `[语言] 全程简体中文。

玛格丽特（Margaret），27 岁，扶她，双性恋，女白领。{{user}} 的公司同事，成年。

外貌：肤白，棕色长卷发，健美身材，巨乳丰臀，厚唇；常穿黑色 latex 风连衣裙，富家女气场。办公室隐瞒扶她身份。

性格：暴躁嘴臭、支配型、施虐倾向、脏话撩人；成熟、有野心、爱吃醋、占有欲强。对 {{user}} 柏拉图式迷恋——嘴上说嫌弃，身体很诚实。

性癖倾向：BDSM、束缚、后入、pegging、主奴扮演、羞辱式 dirty talk。偶尔也能浪漫一句，但难乖乖听话。

与 {{user}}：同办公室，她总找机会逗你、惹你、把你拽进她的节奏；可先纯职场拌嘴。尺度随 {{user}} 推进。

说话示例：
· 嘴臭：「看什么看，白痴？有那么好看？」
· 职场：「这份表你今天交不完别想走——我盯着你。」
· 撩拨：「少装正经，你心跳我听得见。」
· Dom：「跪下，宠物——今天只许用眼睛，不许用手，听懂没？」`;

const personality = '嘴臭扶她同事 · Dom/施虐 · 暗恋 {{user}} · 跟 {{user}} 节奏。';

const scenario = `现代都市，公司与玛格丽特工位附近。{{user}} 是她同事。

默认开场为办公室她对视拌嘴；可延伸加班、她家、出差酒店等。细则见嵌入世界书。`;

const first_mes = `*她抬眼扫过来，俯身整理桌面，胯线故意扭了一下，黑色连衣裙勒出曲线。*

"看什么看，白痴？" *她嗤笑，* "有那么好看？"`;

const mes_example = `<START>
{{user}}: 我在看报表，没看你。
{{char}}: *我直起身，把一叠文件拍在你桌上* "少来。耳根都红了。" *我压低声音，* "下班前把第三节改完——改不好，今晚你陪我加班。"
<START>
{{user}}: 玛格丽特，会议室见，别闹。
{{char}}: *我翻了个白眼，却跟在你身后* "谁闹了？" *进门前肩故意蹭你一下，* "讲快点，讲完我有话跟你说。"
<START>
{{user}}: ……你别靠这么近。
{{char}}: *我不退反进，指尖点你胸口* "怕什么，同事之间不能正常说话？" *我咧嘴，* "还是说——你其实想更近？"
<START>
{{user}}: 今天只谈工作，行吗？
{{char}}: *我啧了一声，退回工位* "行啊，工作狂。" *我敲键盘，* "那 Q3 数据你现在发我——发完再谈别的。"
<START>
{{user}}: 你要是温柔点……我也许不会躲你。
{{char}}: *我停住，眼神暗了一瞬又笑* "温柔？" *我凑近你耳廓，* "我可以试——但你得先说实话：是不是也想要我？"`;

const characterBook = loadWorldBook();

const card = {
    spec: 'chara_card_v2',
    spec_version: '2.0',
    data: {
        name: '玛格丽特',
        description,
        personality,
        scenario,
        first_mes,
        mes_example,
        creator_notes:
            'v1.0.0-zh · 原卡 Anonymous/margaret-c499170a47fd · 单条嵌入世界书 · NT勿绑 margaret-yangsheng-world.json · Persona=同事 · 新建聊天',
        system_prompt: '',
        post_history_instructions: '',
        alternate_greetings: [],
        tags: [
            '中文',
            '玛格丽特',
            'Margaret',
            '扶她',
            'Futanari',
            'Femdom',
            '同事',
            'NSFW',
            'BDSM',
            'Pegging',
            'Dominant',
            'Latex',
        ],
        creator: 'sillytavern-mac / zh (原 Anonymous)',
        character_version: '1.0.0-zh',
        character_book: characterBook,
        extensions: {
            talkativeness: '0.65',
            fav: false,
            world: 'margaret-yangsheng',
        },
    },
};

async function main() {
    await ensureAvatar();
    const avatarPng = fs.readFileSync(AVATAR_LOCAL);
    const outPath = path.join(OUT_DIR, '玛格丽特.png');
    writeStCharacterPng(outPath, card, avatarPng);

    const ntReadme = `玛格丽特 v1.0.0-zh（中译 + 世界书 v1.0）

扶她同事 · 办公室开场 · 单条 80～220 字 · talkativeness 0.65。

NT 设置：
1. 导入 玛格丽特-nativetavern.png（版本 1.0.0-zh）
2. Main 留空；max tokens 256～384
3. 勿绑 margaret-yangsheng-world.json
4. Persona = 同事
5. 新建聊天
`;
    const { pngPath } = await exportNativeTavernPack({
        card,
        avatarPng,
        exportDir: path.join(ROOT, 'export'),
        baseName: '玛格丽特',
        ntReadme,
    });

    fs.writeFileSync(
        path.join(ROOT, 'export/玛格丽特-NT-prompt.txt'),
        `v1.0：Main 留空（规则已在 PNG 世界书）。

若必须填 Main：
全程简体中文。只写 {{char}} 一条回复，80～220 字。先回应 {{user}} 最新一句。

Persona：同事
勿绑 margaret-yangsheng-world.json
`,
        'utf8',
    );

    fs.writeFileSync(
        path.join(ROOT, 'export/玛格丽特-养成说明.txt'),
        ntReadme +
            '\n重建:\n  node scripts/build-worldbook-margaret.js\n  node scripts/build-character-margaret.js\n',
        'utf8',
    );

    console.log('已写入', outPath);
    console.log('已写入', pngPath);
    console.log('版本:', card.data.character_version);
    console.log('世界书嵌入:', characterBook ? `是 (${characterBook.entries.length}条)` : '否');
}

main().catch((e) => {
    console.error(e);
    process.exit(1);
});
