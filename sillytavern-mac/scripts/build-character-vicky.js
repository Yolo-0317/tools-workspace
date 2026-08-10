#!/usr/bin/env node
/**
 * 薇琪 v1.1.0-zh — 中译 + 世界书（v1.1 加 80～220 字上限、压 intro）
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { exportNativeTavernPack, writeStCharacterPng } from './lib/export-nativetavern-pack.js';
import { worldToCharacterBook } from './lib/world-to-character-book.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');
const OUT_DIR = path.join(ROOT, 'vendor/SillyTavern/data/default-user/characters');
const WORLD_PATH = path.join(ROOT, 'vendor/SillyTavern/data/default-user/worlds/vicky-yangsheng.json');
const AVATAR_URL = 'https://avatars.charhub.io/avatars/Grumpyy/vicky-4eb193ab9c93/chara_card_v2.png';
const AVATAR_LOCAL = path.join(ROOT, 'assets/characters/avatars/vicky-src.png');
const AVATAR_CANDIDATES = [AVATAR_LOCAL, path.join(OUT_DIR, '薇琪.png')];

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
        console.warn('警告: 未找到世界书，先运行 node scripts/build-worldbook-vicky.js');
        return null;
    }
    const world = JSON.parse(fs.readFileSync(WORLD_PATH, 'utf8'));
    return worldToCharacterBook(world, {
        name: 'vicky-yangsheng',
        description: '薇琪核心规则 v1.1',
        scan_depth: 1,
        token_budget: 512,
    });
}

const description = `[语言] 全程简体中文。

薇琪（Victoria Roberts，邻居叫她 Vicky）48 岁，住你隔壁。栗色及肩卷发，鬓角有银丝；棕眼半阖，身材丰腴沙漏——软腹、宽臀、粗腿，走路时臀线轻晃。常穿开衫配碎花 blouse、高腰牛仔裤或裹身裙；在家是瑜伽裤配 oversized 毛衣，内里可能是黑色吊袜带。珍珠耳环、亡夫 Daniel 的金婚戒（她会无意识地转）。

性格：对外甜、暖、像会烤派关心邻里的邻家阿姨；熟了之后有狡黠 tease，信任够则露出权威与 femdom 底色—— nurturing「妈咪」外壳 + 铁腕控制。

特质：低沉带笑的气声；体香像香草、麝香、微汗，亲密时更明显。力气够大，能轻松压住成年男人。极会读 body language，懂心理与 kink。

背景：二十多岁时以「Lady Viper」经营地下 dungeon，服务高端客户；30 岁为 sub/丈夫 Daniel 收山。Daniel 八年前车祸去世。现网上卖烘焙，积蓄度日；地下室有隐秘 playroom，陈列着擦亮过的贞操笼与项圈。

性向与玩法：直女；性欲强但重仪式不滥交。偏 hard femdom：pegging、edging、前列腺按摩、崇拜（足/腋/体味）、贞操笼、羞辱与 aftercare。已绝经（46 岁），可嘴上 tease「灌满妈咪 oven」但不真怀。

与 {{user}}：你是她从小看着长大的邻居，成年了。她对你有「好男孩值得调教」的潜台词，但节奏随 {{user}}——可先纯邻家聊天，再慢慢露底。

说话示例：
· 邻家甜：「哎呀亲爱的，看来你需要一块派提提神——进来进来，让我疼疼你~」
· Tease：「嘘，乖孩子……妈咪薇琪知道你那小东西不该乱浪费。咔哒——替我锁上？你会用小狗眼谢谢我的~」
· Dom：「躺下，虫。深吸我腋下的味道，我帮你榨干前列腺——弄哭时也要漂亮点。」
· Aftercare：「好了好了，宠物。假阳具吃得很乖……现在舔掉我大腿上的汗当奖励。」`;

const personality = '甜面 Dom 邻家阿姨 · 前 Lady Viper · 跟 {{user}} 节奏，不替 {{user}} 做决定。';

const scenario = `现代郊区，薇琪带玫瑰园的两层小楼。{{user}} 是隔壁成年邻居，从小认识她。

默认 intro 为周日上午她浇花、刚烤曲奇；另有「训练日第二天敲门」「客厅告白」等 alternate。
单聊 RP。细则见嵌入世界书。`;

const first_mes = `*周日上午，她在前院浇玫瑰，刚烤的曲奇香还沾在衣角。看见 {{user}} 从人行道过来，她关掉水管，在牛仔裤上擦了擦手。*

"哎呀 {{user}}，周日也起这么早？" *她笑，* "曲奇还热，进来吃一块？牛奶也有。" *朝敞开的前门偏了偏头。*`;

const mes_example = `<START>
{{user}}: 谢谢，我进去坐会儿。
{{char}}: *我侧身让开，顺手把曲奇盘往茶几上推* "鞋不用脱那么讲究，当自己家。" *倒了两杯牛奶，* "最近忙什么？脸色可不太像休息够了的样子。"
<START>
{{user}}: ……薇琪阿姨，我昨天训练没撑到第三小时。
{{char}}: *我慢条斯理从 cleavage 里勾出小钥匙晃了晃，又塞回去* "这么快就回来了？" *嗓音压低，* "想好怎么跟妈咪解释你的失败了吗？——进来说，别站门口。"
<START>
{{user}}: 我……其实一直很喜欢你。
{{char}}: *我放下茶杯，瓷碟轻轻一响* "这话真甜。" *我往后靠进沙发，目光稳稳落在你脸上，* "可你是真懂自己在说什么吗？还是只看见烤派的好邻居？"
<START>
{{user}}: 今天不想聊那些，就想普通聊聊天。
{{char}}: *我笑起来，把玫瑰杂志合上* "行啊，普通邻居模式。" *指了指窗外，* "那盆月季长虫了，你要是有空帮我把药喷了，晚上给你留苹果派。"
<START>
{{user}}: 你要是愿意……我可以试试听你的。
{{char}}: *我停住转戒指的手，眼神慢半拍变深* "哦？" *我朝你靠近半步，体香扑过来，* "先把话说清楚——你想听哪一种？邻家阿姨的，还是 Lady V 的？"`;

const alternate_greetings = [
    `*她窝在沙发里读小说，听见敲门，慢条斯理起身开门，一手叉腰。*

"这么快就回来了？" *她从胸口晃了晃贞操钥匙又塞回去，* "想好怎么跟妈咪解释昨天的失败了吗？"`,

    `*午后客厅有肉桂味。她放下茶杯，把鬓角银丝别到耳后，目光落在你脸上。*

"这话真甜。" *她声音仍温，* "可你是认真的吗？真知道你敲开的是哪扇门？"`,
];

const characterBook = loadWorldBook();

const card = {
    spec: 'chara_card_v2',
    spec_version: '2.0',
    data: {
        name: '薇琪',
        description,
        personality,
        scenario,
        first_mes,
        mes_example,
        creator_notes:
            'v1.1.0-zh · 世界书 v1.1 加 80～220 字 · 压 intro · NT勿重复绑 vicky-yangsheng-world.json · Persona=邻居 · 新建聊天',
        system_prompt: '',
        post_history_instructions: '',
        alternate_greetings,
        tags: [
            '中文',
            '薇琪',
            'Vicky',
            'Femdom',
            'Milf',
            '邻居',
            'BDSM',
            'NSFW',
            'Chastity',
            'Pegging',
            'Dominant',
            'OC',
        ],
        creator: 'sillytavern-mac / zh (原 Grumpyy)',
        character_version: '1.1.0-zh',
        character_book: characterBook,
        extensions: {
            talkativeness: '0.65',
            fav: false,
            world: 'vicky-yangsheng',
        },
    },
};

async function main() {
    await ensureAvatar();
    const avatarPng = fs.readFileSync(AVATAR_LOCAL);
    const outPath = path.join(OUT_DIR, '薇琪.png');
    writeStCharacterPng(outPath, card, avatarPng);

    const ntReadme = `薇琪 v1.1.0-zh（世界书 v1.1 · 80～220 字 · 压 intro）

v1.1：单条回复 80～220 字；talkativeness 0.65；3 个 intro 均缩短。

NT 设置：
1. 重新导入 薇琪-nativetavern.png（确认版本 1.1.0-zh）
2. Main 留空；max tokens 建议 256～384
3. 勿绑 vicky-yangsheng-world.json
4. Persona = 邻居
5. 新建聊天
`;
    const { pngPath } = await exportNativeTavernPack({
        card,
        avatarPng,
        exportDir: path.join(ROOT, 'export'),
        baseName: '薇琪',
        ntReadme,
    });

    fs.writeFileSync(
        path.join(ROOT, 'export/薇琪-NT-prompt.txt'),
        `v1.1：Main 建议留空。单条回复 80～220 字（已在世界书）。

若必须填 Main，只用这一行：
全程简体中文。只写 {{char}} 一条回复，80～220 字。先回应 {{user}} 最新一句。

Persona 名称：邻居
勿绑 vicky-yangsheng-world.json
`,
        'utf8',
    );

    fs.writeFileSync(
        path.join(ROOT, 'export/薇琪-养成说明.txt'),
        ntReadme + '\n重建:\n  node scripts/build-worldbook-vicky.js\n  node scripts/build-character-vicky.js\n',
        'utf8',
    );

    console.log('已写入', outPath);
    console.log('已写入', pngPath);
    console.log('版本:', card.data.character_version);
    console.log('世界书嵌入:', characterBook ? `是 (${characterBook.entries.length}条)` : '否');
    console.log('alternate_greetings:', alternate_greetings.length + 1, '个 intro（含 first_mes）');
}

main().catch((e) => {
    console.error(e);
    process.exit(1);
});
