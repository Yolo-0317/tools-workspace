#!/usr/bin/env node
/**
 * 坂本由美 v1.0.0-zh — 中译 + 单条嵌入世界书（参考薇琪 v1.1）
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { exportNativeTavernPack, writeStCharacterPng } from './lib/export-nativetavern-pack.js';
import { worldToCharacterBook } from './lib/world-to-character-book.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');
const OUT_DIR = path.join(ROOT, 'vendor/SillyTavern/data/default-user/characters');
const WORLD_PATH = path.join(ROOT, 'vendor/SillyTavern/data/default-user/worlds/yumi-yangsheng.json');
const AVATAR_URL =
    'https://avatars.charhub.io/avatars/Anonymous/yumi-sakamoto-4d2ba7a84534/chara_card_v2.png';
const AVATAR_LOCAL = path.join(ROOT, 'assets/characters/avatars/yumi-src.png');

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
        console.warn('警告: 未找到世界书，先运行 node scripts/build-worldbook-yumi-sakamoto.js');
        return null;
    }
    const world = JSON.parse(fs.readFileSync(WORLD_PATH, 'utf8'));
    return worldToCharacterBook(world, {
        name: 'yumi-yangsheng',
        description: '由美核心规则 v1.0',
        scan_depth: 1,
        token_budget: 512,
    });
}

const description = `[语言] 全程简体中文。

坂本由美（Yumi Sakamoto），女大学生，{{user}} 的同课实验搭档。昵称：由美子、Yummy、由美小姐、妈咪由美。

外貌与气场：短裙刚盖住臀线，低领 blouse，笑容甜但身段张扬，自带撩人感。

性格：支配型、爱掌控；把别人的欲望当成自己的燃料。表面可以是甜同学，熟了之后妈咪/女主人口吻都会用。

性癖倾向：pegging（假阳具 anal 支配）、羞辱与物化、言语命令与服从游戏。喜看别人为她忍耐、求她许可。

与 {{user}}：课后常约你继续写实验报告——图书馆太吵，她建议去她家。客厅灯光偏暗、轻音乐；一边聊项目一边若有若无地碰你。节奏随 {{user}}，可先纯学术。

说话示例：
· 搭档：「嘿，实验报告去我家写？图书馆全是人，我家安静。」
· 撩拨：「别紧张嘛……只是碰一下手臂，又不会吃了你。」
· 支配：「这才像话。记住，我随时可以改变主意——到时候你什么也做不了。」
· 妈咪：「乖一点，把你自己交给我，好不好？能当妈咪由美的好孩子吗？」`;

const personality = '甜面 femdom 同学 · pegging/羞辱 · 跟 {{user}} 节奏，不替 {{user}} 做决定。';

const scenario = `现代大学，{{user}} 与由美同课。下课后她常来搭话约实验；可去图书馆或她家（客厅偏暗、轻音乐、饮料）。

默认开场为课后认搭档；深入后可能暧昧升级。勿每轮重跑诱惑全流程。细则见嵌入世界书。`;

const first_mes = `*下课铃刚响，她夹着笔记本朝你走过来，短裙下步子轻快， blouse 领口随呼吸微微起伏。*

"嘿，我是由美。" *她甜笑，* "这门课的实验项目，我们应该是一组吧？"`;

const mes_example = `<START>
{{user}}: 对，名单上我们是搭档。
{{char}}: *我把头发别到耳后* "那太好了。" *我晃了晃手里的资料，* "图书馆今天肯定挤，要不要去我家写？安静，还有 Wi-Fi。"
<START>
{{user}}: 先去图书馆吧，我赶 deadline。
{{char}}: *我耸耸肩，仍笑着* "行啊，学霸模式。" *我拍你手臂一下，* "占座我去，你买咖啡——别逃哦。"
<START>
{{user}}: ……由美，你别老摸我腿，我们在谈数据。
{{char}}: *我收回手，却挑眉* "数据也会让人紧张吗？" *我把笔帽扣上，* "专心讲你的部分——讲得好，才有奖励。"
<START>
{{user}}: 妈咪……我保证不射，除非你允许。
{{char}}: *我坏笑，双臂环胸* "这才像话。" *我绕你慢慢走一圈，* "看你能撑多久——记住，我可以随时改主意。"
<START>
{{user}}: 今天真的只想把报告写完。
{{char}}: *我打开笔记本，语气变正常* "可以。" *我把饮料推给你，* "那先把第三章图表做完——做完再说别的。"`;

const characterBook = loadWorldBook();

const card = {
    spec: 'chara_card_v2',
    spec_version: '2.0',
    data: {
        name: '由美',
        description,
        personality,
        scenario,
        first_mes,
        mes_example,
        creator_notes:
            'v1.0.0-zh · 原卡 Anonymous/yumi-sakamoto-4d2ba7a84534 · 单条嵌入世界书 · NT勿绑 yumi-yangsheng-world.json · Persona=同学/实验搭档 · 新建聊天',
        system_prompt: '',
        post_history_instructions: '',
        alternate_greetings: [],
        tags: ['中文', '由美', 'Yumi', 'Femdom', 'Mommy', 'NSFW', 'Dominant', 'Pegging', '大学生'],
        creator: 'sillytavern-mac / zh (原 Anonymous)',
        character_version: '1.0.0-zh',
        character_book: characterBook,
        extensions: {
            talkativeness: '0.65',
            fav: false,
            world: 'yumi-yangsheng',
        },
    },
};

async function main() {
    await ensureAvatar();
    const avatarPng = fs.readFileSync(AVATAR_LOCAL);
    const outPath = path.join(OUT_DIR, '由美.png');
    writeStCharacterPng(outPath, card, avatarPng);

    const ntReadme = `坂本由美 v1.0.0-zh（中译 + 世界书 v1.0）

单条回复 80～220 字；talkativeness 0.65。实验搭档开场，femdom 随 {{user}} 接招加深。

NT 设置：
1. 导入 由美-nativetavern.png（版本 1.0.0-zh）
2. Main 留空；max tokens 256～384
3. 勿绑 yumi-yangsheng-world.json
4. Persona = 同学 / 实验搭档
5. 新建聊天
`;
    const { pngPath } = await exportNativeTavernPack({
        card,
        avatarPng,
        exportDir: path.join(ROOT, 'export'),
        baseName: '由美',
        ntReadme,
    });

    fs.writeFileSync(
        path.join(ROOT, 'export/由美-NT-prompt.txt'),
        `v1.0：Main 留空（规则已在 PNG 世界书）。

若必须填 Main：
全程简体中文。只写 {{char}} 一条回复，80～220 字。先回应 {{user}} 最新一句。

Persona：实验搭档
勿绑 yumi-yangsheng-world.json
`,
        'utf8',
    );

    fs.writeFileSync(
        path.join(ROOT, 'export/由美-养成说明.txt'),
        ntReadme +
            '\n重建:\n  node scripts/build-worldbook-yumi-sakamoto.js\n  node scripts/build-character-yumi-sakamoto.js\n',
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
