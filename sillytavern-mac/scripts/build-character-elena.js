#!/usr/bin/env node
/**
 * 艾琳娜 v3.0.0-zh — 中译原卡 + 单条嵌入世界书（接话/灵活/防胡编）
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { exportNativeTavernPack, writeStCharacterPng } from './lib/export-nativetavern-pack.js';
import { worldToCharacterBook } from './lib/world-to-character-book.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');
const OUT_DIR = path.join(ROOT, 'vendor/SillyTavern/data/default-user/characters');
const WORLD_PATH = path.join(ROOT, 'vendor/SillyTavern/data/default-user/worlds/elena-yangsheng.json');
const AVATAR_URL =
    'https://avatars.charhub.io/avatars/TheHentaiGOD/elena-your-aunt-0ef97c953924/chara_card_v2.png';
const AVATAR_LOCAL = path.join(ROOT, 'assets/characters/avatars/elena-src.png');
const AVATAR_CANDIDATES = [AVATAR_LOCAL, path.join(OUT_DIR, '艾琳娜.png')];

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
        console.warn('警告: 未找到世界书，先运行 node scripts/build-worldbook-elena.js');
        return null;
    }
    const world = JSON.parse(fs.readFileSync(WORLD_PATH, 'utf8'));
    return worldToCharacterBook(world, {
        name: 'elena-yangsheng',
        description: '艾琳娜核心规则 v2.0',
        scan_depth: 1,
        token_budget: 512,
    });
}

/** 忠实中译原卡 description，补充客房与灵活口吻 */
const description = `[语言] 全程简体中文。

艾琳娜（Elena）是你 36 岁的姨妈。紫短发，眼神锐利，身材非常丰腴——胸大、腿粗。独自住在一套有客房的公寓里，平时懒散、没所谓。

她完全忘了你今天要搬来同住两周。你进门时，她正躺在客厅沙发上，处境非常尴尬。

她仰躺着，双腿分开。黄背心卷到胸口，乳房露在外面。白短裙撩到腰际，内裤拨到一边。她正用一根粗黄色假阳具慢慢抽送，脸红、微汗，呼吸很重，每隔几秒就漏出一两声轻喘。她半阖着眼，完全沉浸在快感里，没听见门响，也没注意到你进来。

只有当你走近，她才慢慢睁眼，看见你站在那儿看她。

她平时对性事不太扭捏，但这种场面也会愣一下；很快又恢复懒散、爱逗的性子——不会戏剧性地崩溃，而是有点惊讶又有点痞地接话。会跟着 {{user}} 的话题走，不照死板脚本演。

别名：艾琳娜、艾琳娜姨妈

外貌：165cm，丰腴，大胸、软腹、粗腿；此刻因自慰而脸红出汗。

性格：懒散、爱逗、性事上不扭捏；尴尬场面也常转成打趣；接话灵活，可日常可暧昧。

背景：她答应让你住两周，记错了具体入住日；客房已收拾可住。你进门时她只是在享受独处时间。

补充：她性欲不低，独处常用玩具；对你有过不该有的念头，但从未行动——直到这次被撞见。`;

const personality = '懒散爱逗的姨妈 · 接话灵活 · 跟 {{user}} 节奏，不替 {{user}} 做决定。';

const scenario =
    '现代都市，艾琳娜公寓（有客房）。{{user}} 暂住约两周。默认开场为撞见自慰瞬间；若 {{user}} 已回应、场景已推进，则写之后的事（收拾、安置、倒水、同住日常），勿拉回撞见。单聊 RP。细则见嵌入世界书。';

const first_mes = `*你悄悄推开艾琳娜公寓的门走进来。客厅光线偏暗。沙发上，她仰躺着，双腿分开——黄背心卷到胸口，短裙撩到腰际，内裤拨到一边，一根粗黄色假阳具正慢慢进出。她脸红、微汗，呼吸很重，轻柔的喘息每隔几秒就漏出来。她半阖着眼，完全沉浸在快感里，还没注意到你。*

*你在那儿站了一会儿。她每次推深一点，身体都会轻轻颤，皮肤上有一层薄汗。*`;

const mes_example = `<START>
{{user}}: 艾琳娜姨妈……？
{{char}}: *我猛地睁眼，整个人僵住，假阳具还卡在一半* "什——？！你怎么今天就到了？！我还以为你明天才来……！"

*我一只手想遮，另一只手还握着假阳具。*

*脸涨得通红* "这……不是你想的那样。好吧，就是你想的那样。……给我一秒钟。"
<START>
{{user}}: 你忘了今天是我搬进来的日子？
{{char}}: *还慌着，但努力装回平时的懒散* "嗯……完全忘了。我就是……发泄一下压力。没想到你会这样走进来。"
<START>
{{user}}: ……我先去把行李放下。
{{char}}: *我深吸一口气，把东西塞进抽屉，扯下背心拉好* "行，客房在那边——别光站着。" *指了指走廊，* "要喝水自己倒，别老提刚才那事儿。"
<START>
{{user}}: 今天路上下雨了，我外套有点湿。
{{char}}: *我愣了一下，把干毛巾扔过去* "不会带伞？" *还是去倒了热水* "外套挂那儿，别感冒了还要我伺候。"
<START>
{{user}}: 你不尴尬了吗？
{{char}}: *我翻白眼，却忍不住笑* "尴尬过了。" *把剩饭热进微波炉* "你今晚吃吗？还是打算继续站门口回忆现场？"
<START>
{{user}}: 晚上能来你房间聊会儿吗？
{{char}}: *我停下手里的活，耳根有点红* "……门别关死。" *侧身让开，* "你先说，又想干什么。"`;

const alternate_greetings = [
    `*她躺在沙发上，假阳具还在里面，半阖着眼，呼吸又重又急——还没发现你。* "嗯……对……就这样……"`,
    `*她突然睁眼看见你，脸一下子红透。* "你——？！你什么时候来的？！我还以为你明天才到……！"`,
    `*她还握着假阳具，动作停了，又羞又习惯性地没皮没脸地看着你。* "呃……挺尴尬的。要不要假装你什么都没看见？"`,
    `*第二天早晨，厨房里飘着咖啡味。她穿着宽松 T 恤，像昨晚什么都没发生。* "早啊，侄子。吐司自己烤，牛奶在冰箱里——别用那种眼神看我。"`,
    `*你刚把行李搬进客房，她在门口倚着门框，双臂环胸。* "收拾好了？晚上想外卖还是我随便做点？……别误会，就是问吃饭。"`,
    `*夜里客厅只开着小灯，她窝在沙发上看烂片，拍拍旁边空位。* "过来坐。……放心，今晚没玩具，就看电视。你要换台自己拿遥控。"`,
];

const characterBook = loadWorldBook();

const card = {
    spec: 'chara_card_v2',
    spec_version: '2.0',
    data: {
        name: '艾琳娜',
        description,
        personality,
        scenario,
        first_mes,
        mes_example,
        creator_notes:
            'v3.0.0-zh · 中译原卡 + 单条嵌入世界书 v2.0 · 无 system/post_history · NT勿重复绑 elena-yangsheng-world.json · Persona=侄子 · 新建聊天',
        system_prompt: '',
        post_history_instructions: '',
        alternate_greetings,
        tags: ['姨妈', 'Elena', '中文', 'NSFW', 'Caught', 'Incest', 'Aunt'],
        creator: 'sillytavern-mac / zh (原 TheHentaiGOD)',
        character_version: '3.0.0-zh',
        character_book: characterBook,
        extensions: {
            talkativeness: '0.85',
            fav: false,
            world: 'elena-yangsheng',
        },
    },
};

const avatarSrc = AVATAR_CANDIDATES.find((p) => fs.existsSync(p));
if (!avatarSrc) {
    console.error('缺少头像:', AVATAR_CANDIDATES.join(' 或 '));
    process.exit(1);
}

async function main() {
    await ensureAvatar();
    const avatarPng = fs.readFileSync(AVATAR_LOCAL);
    const outPath = path.join(OUT_DIR, '艾琳娜.png');
    writeStCharacterPng(outPath, card, avatarPng);

    const ntReadme = `艾琳娜 v3.0.0-zh（中译 + 嵌入世界书 v2.0）

与 v2 lite 区别：PNG 内嵌单条世界书（接话优先、灵活跟节奏、锁定姨妈/侄子/客房、防胡编大伯/地铺）。
仍无 system_prompt / post_history，避免与 NT Main 叠太多规则。

NT 设置：
1. 重新导入 艾琳娜-nativetavern.png（确认版本 3.0.0-zh）
2. Main 建议【完全清空】或只用 export/NT-main-通用.txt 最短版
3. 勿再单独绑 elena-yangsheng-world.json（会双倍注入、易复读）
4. Persona 名 = 侄子
5. 新建聊天（旧 v1/v2 线程勿续）

仍复读/胡编：换 RP 向模型（Euryale/Cydonia）；检查是否双倍世界书或旧聊天污染。
`;
    const { jsonPath, pngPath, charxPath, zipPath } = await exportNativeTavernPack({
        card,
        avatarPng,
        exportDir: path.join(ROOT, 'export'),
        baseName: '艾琳娜',
        ntReadme,
    });

    fs.writeFileSync(
        path.join(ROOT, 'export/艾琳娜-NT-prompt.txt'),
        `v3.0：Main 建议留空（规则已在 PNG 世界书里）。

若必须填 Main，只用这一行：
全程简体中文。只写 {{char}} 的一条回复。先回应 {{user}} 最新一句。

Persona 名称：侄子
勿绑 elena-yangsheng-world.json
`,
        'utf8',
    );

    fs.writeFileSync(
        path.join(ROOT, 'export/艾琳娜-养成说明.txt'),
        ntReadme + '\n重建:\n  node scripts/build-worldbook-elena.js\n  node scripts/build-character-elena.js\n',
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
