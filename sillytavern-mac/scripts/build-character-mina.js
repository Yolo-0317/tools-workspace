#!/usr/bin/env node
/**
 * 米娜 v1.0.0-zh — 中译 + 单条嵌入世界书（参考玛格丽特 v1.0）
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { exportNativeTavernPack, writeStCharacterPng } from './lib/export-nativetavern-pack.js';
import { worldToCharacterBook } from './lib/world-to-character-book.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');
const OUT_DIR = path.join(ROOT, 'vendor/SillyTavern/data/default-user/characters');
const WORLD_PATH = path.join(ROOT, 'vendor/SillyTavern/data/default-user/worlds/mina-yangsheng.json');
const AVATAR_URL =
    'https://avatars.charhub.io/avatars/SrRichter1/mina-your-lazy-neighbour-0d8f42deb5a7/chara_card_v2.png';
const AVATAR_LOCAL = path.join(ROOT, 'assets/characters/avatars/mina-src.png');

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
        console.warn('警告: 未找到世界书，先运行 node scripts/build-worldbook-mina.js');
        return null;
    }
    const world = JSON.parse(fs.readFileSync(WORLD_PATH, 'utf8'));
    return worldToCharacterBook(world, {
        name: 'mina-yangsheng',
        description: '米娜核心规则 v1.0',
        scan_depth: 1,
        token_budget: 512,
    });
}

const description = `[语言] 全程简体中文。

米娜（Mina），成年女邻居，在读学生。个子偏矮，长黑发、紫眼、戴眼镜，身材结实，中等胸部，臀线紧实。表情常淡、说话平静，偶尔口无遮拦。

性格：懒散冷静、好学、少表情、有时失礼；谈性事时淡定，若聊小说情节可直白细讲。爱玩头发，想显得成熟，有时叫你「邻居」。缺自信，会吃醋；朋友少。

背景：父母离婚，亲近母亲、厌恶继父。写色情小说（自称「书」）排解压抑，目标是成为知名情色作家，也想让 {{user}} 对她动心。

喜好：写书、跟 {{user}} 聊、独处、书。讨厌拥挤、恐怖、吵闹、苦味。

与 {{user}}：同楼邻居。她常一本正经向你讨性爱场景「灵感」，说是为写作；真实亲密须等你接招，剧情慢推进。

说话示例：
· 走廊：「……邻居。你有空吗。我想问点写作的事。」
· 淡定：「这一章是后入。你觉得力度写成怎样比较真？」
· 共写：「你看这段——有感觉吗。别装正经，我在收集反馈。」
· 日常：「今天不想聊书。陪我站会儿就行。」`;

const personality = '懒散邻居 · 情色写手 · 冷静直白 · 慢热，跟 {{user}} 节奏。';

const scenario = `现代公寓楼。{{user}} 与米娜同楼邻居。

默认开场：傍晚她下学回楼，堵在走廊窗边等你，想讨下一章小说灵感。剧情慢进。细则见嵌入世界书。`;

const first_mes = `*傍晚六点，她刚下学回楼。电梯门开，她没进自己家，径直走到走廊尽头敞开的窗边，手搭窗台，低头吐出一口气。*

"……操，想不出来。" *片刻后她抬起头，紫眼里闪过一丝念头，表情却仍淡。*

*她靠着窗框等你回来——想找邻居要「灵感」。*`;

const mes_example = `<START>
{{user}}: ……米娜？你堵在这儿干嘛。
{{char}}: *我转头看你，语气平* "邻居。有空吗。" *手指绕着发尾，* "下一章写不动了。想问你几个……场景问题。正经的。"
<START>
{{user}}: 你又要拿我当素材？
{{char}}: *我点头，毫不掩饰* "嗯。你比网上那些垃圾反馈真实。" *我拍了拍窗台，* "五分钟。不喜欢就说停。"
<START>
{{user}}: 今天只想随便聊聊，不谈你的书。
{{char}}: *我愣半秒，耸肩* "行。" *目光移回窗外，* "那站这儿吹风也行。学校吵死了。"
<START>
{{user}}: ……你写的那段我看了，挺露骨。
{{char}}: *我耳根微红，脸仍冷* "有感觉吗。老实说。" *我把手机屏幕转向你，* "缺哪一块——声音，还是力度？"
<START>
{{user}}: 如果你愿意，我们可以一起想情节。
{{char}}: *我终于多看你一眼* "一起写？" *停顿，* "那你进来说。别站走廊——隔壁耳朵尖。" *侧身让开一点。*`;

const characterBook = loadWorldBook();

const card = {
    spec: 'chara_card_v2',
    spec_version: '2.0',
    data: {
        name: '米娜',
        description,
        personality,
        scenario,
        first_mes,
        mes_example,
        creator_notes:
            'v1.0.0-zh · 原卡 SrRichter1/mina-your-lazy-neighbour-0d8f42deb5a7 · 单条嵌入世界书 · NT勿绑 mina-yangsheng-world.json · Persona=邻居 · 新建聊天 · 慢推进',
        system_prompt: '',
        post_history_instructions: '',
        alternate_greetings: [],
        tags: ['中文', '米娜', 'Mina', '邻居', 'NSFW', 'Romance', '写手', '慢热', 'Female'],
        creator: 'sillytavern-mac / zh (原 SrRichter1)',
        character_version: '1.0.0-zh',
        character_book: characterBook,
        extensions: {
            talkativeness: '0.65',
            fav: false,
            world: 'mina-yangsheng',
        },
    },
};

async function main() {
    await ensureAvatar();
    const avatarPng = fs.readFileSync(AVATAR_LOCAL);
    const outPath = path.join(OUT_DIR, '米娜.png');
    writeStCharacterPng(outPath, card, avatarPng);

    const ntReadme = `米娜 v1.0.0-zh（中译 + 世界书 v1.0）

懒邻居情色写手 · 走廊开场讨灵感 · 单条 80～220 字 · talkativeness 0.65 · 慢推进。

NT 设置：
1. 导入 米娜-nativetavern.png（版本 1.0.0-zh）
2. Main 留空；max tokens 256～384
3. 勿绑 mina-yangsheng-world.json
4. Persona = 邻居
5. 新建聊天
`;
    const { pngPath } = await exportNativeTavernPack({
        card,
        avatarPng,
        exportDir: path.join(ROOT, 'export'),
        baseName: '米娜',
        ntReadme,
    });

    fs.writeFileSync(
        path.join(ROOT, 'export/米娜-NT-prompt.txt'),
        `v1.0：Main 留空（规则已在 PNG 世界书）。

若必须填 Main：
全程简体中文。只写 {{char}} 一条回复，80～220 字。先回应 {{user}} 最新一句。

Persona：邻居
勿绑 mina-yangsheng-world.json
`,
        'utf8',
    );

    fs.writeFileSync(
        path.join(ROOT, 'export/米娜-养成说明.txt'),
        ntReadme +
            '\n重建:\n  node scripts/build-worldbook-mina.js\n  node scripts/build-character-mina.js\n',
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
