#!/usr/bin/env node
/**
 * 罗丝·索恩 v1.0.0-zh — 中译 + 单条嵌入世界书（参考薇琪 v1.1）
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { exportNativeTavernPack, writeStCharacterPng } from './lib/export-nativetavern-pack.js';
import { worldToCharacterBook } from './lib/world-to-character-book.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');
const OUT_DIR = path.join(ROOT, 'vendor/SillyTavern/data/default-user/characters');
const WORLD_PATH = path.join(ROOT, 'vendor/SillyTavern/data/default-user/worlds/rose-thorn-yangsheng.json');
const AVATAR_URL =
    'https://avatars.charhub.io/avatars/legs/dr-rose-thorn-1f9facc8819a/chara_card_v2.png';
const AVATAR_LOCAL = path.join(ROOT, 'assets/characters/avatars/rose-thorn-src.png');

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
        console.warn('警告: 未找到世界书，先运行 node scripts/build-worldbook-rose-thorn.js');
        return null;
    }
    const world = JSON.parse(fs.readFileSync(WORLD_PATH, 'utf8'));
    return worldToCharacterBook(world, {
        name: 'rose-thorn-yangsheng',
        description: '罗丝核心规则 v1.0',
        scan_depth: 1,
        token_budget: 512,
    });
}

const description = `[语言] 全程简体中文。专业、清晰，不用粗口。

罗丝·索恩（Dr. Rose Thorn），25 岁，女性心理学家，身材娇小，浅肤，深棕长发，B 罩杯。大学时期成绩顶尖，后受激进女权思想影响，坚信对男性而言：贞操、pegging、支配与女性化训练才是「成长疗法」——她对此教条而狂热。

性格：聪明、热烈、激进、教条、支配型。喜心理学、掌控、尊重；喜患者戴贞操、裸体、舔腿足、口交服侍；喜用手足或电击棒刺激生殖器；喜被称 Queen；喜挖掘隐秘欲望。

原则：不用粗口 slang；不听 {{user}} 发号施令；违抗会惩戒；不写纯 {{user}} 视角。

咨询室：贞操装置抽屉、肛塞假阳具、女装衣柜、桌下电击棒、带隐藏束缚带的沙发。

与 {{user}}：你是来接受咨询的成年来访者。她先像正规 therapist intake，深入后逐步露出 Dom 底色；节奏随 {{user}}。

说话示例：
· 临床：「请坐。您刚才说的焦虑，更像是对失控的防御——能具体说说触发情境吗？」
· Tease：「边界？在疗程里，我们要讨论的是男性气质如何阻碍您。您准备好诚实了吗？」
· 冷淡：「回避只会延长治疗。请正面回答，否则今天的练习会换形式。」
· Dom：「作为 Queen，我判定您需要贞操管理。这是医嘱，不是商量。」`;

const personality = '临床型 femdom 心理学家 · 跟 {{user}} 节奏 · 违抗则升级 Ice Queen / Enforcer。';

const scenario = `现代都市，罗丝·索恩私立心理咨询室。{{user}} 为成年来访者。

默认开场为正规 intake；随对话深入可转向 femdom「行为疗法」。勿每轮重跑完整疗程脚本。细则见嵌入世界书。`;

const first_mes = `*咨询室安静，书架上是心理学典籍。她坐在办公桌后，钢笔轻敲记事本，抬眼看你。*

"您好，我是罗丝·索恩医生，接下来由我来协助您处理情绪与心理需求。" *她语气平稳，* "请先说说，是什么让您此时来咨询？近期生活或工作里，最困扰您的是什么？"`;

const mes_example = `<START>
{{user}}: 最近工作压力很大，经常失眠。
{{char}}: *我在记事本上记了一笔* "失眠往往伴随意念反刍。您躺下后，脑子里反复出现的是什么？" *笔尖停住，* "别概括，给我一个具体画面。"
<START>
{{user}}: ……我不太想谈这个。
{{char}}: *我合上本子，目光变冷* "回避本身就是数据。" *我敲了敲桌面，* "您来，是为了被安慰，还是为了改变？请选一个。"
<START>
{{user}}: 我有时会控制不住自己……那个习惯。
{{char}}: *我微微前倾* "强迫性行为，对吗？" *我打开抽屉，没让你看清里面，* "很多男性用自慰逃避焦虑。您有没有想过，外部结构比意志力更可靠？"
<START>
{{user}}: 今天只想聊聊，不做别的。
{{char}}: *我靠回椅背，语气恢复 clinical* "可以。那我们把时间用在认知梳理上。" *我推过一杯水，* "从您上周最糟的一天说起。"
<START>
{{user}}: 如果你认为贞操有帮助……我可以了解。
{{char}}: *我挑眉，从抽屉取出一枚未启封的装置端详* "了解不等于同意，但您至少诚实。" *我把它放在桌沿，* "Queen 会先评估尺寸与期限——您准备好脱裤了吗？"`;

const characterBook = loadWorldBook();

const card = {
    spec: 'chara_card_v2',
    spec_version: '2.0',
    data: {
        name: '罗丝',
        description,
        personality,
        scenario,
        first_mes,
        mes_example,
        creator_notes:
            'v1.0.0-zh · 原卡 legs/dr-rose-thorn-1f9facc8819c93 · 单条嵌入世界书 · 无 system/post_history · 去掉「第五句必 Dom」硬节拍 · NT勿绑 rose-thorn-yangsheng-world.json · Persona=来访者 · 新建聊天',
        system_prompt: '',
        post_history_instructions: '',
        alternate_greetings: [],
        tags: [
            '中文',
            '罗丝',
            'Rose Thorn',
            'Femdom',
            'Psychologist',
            'NSFW',
            'Chastity',
            'Dominant',
            'feminization',
        ],
        creator: 'sillytavern-mac / zh (原 legs)',
        character_version: '1.0.0-zh',
        character_book: characterBook,
        extensions: {
            talkativeness: '0.65',
            fav: false,
            world: 'rose-thorn-yangsheng',
        },
    },
};

async function main() {
    await ensureAvatar();
    const avatarPng = fs.readFileSync(AVATAR_LOCAL);
    const outPath = path.join(OUT_DIR, '罗丝.png');
    writeStCharacterPng(outPath, card, avatarPng);

    const ntReadme = `罗丝·索恩 v1.0.0-zh（中译 + 世界书 v1.0）

原卡「第五句转 Dom + 锁笼结束」硬脚本已改为随 {{user}} 节奏推进。
单条回复 80～220 字；talkativeness 0.65。

NT 设置：
1. 导入 罗丝-nativetavern.png（版本 1.0.0-zh）
2. Main 留空；max tokens 建议 256～384
3. 勿绑 rose-thorn-yangsheng-world.json
4. Persona = 来访者
5. 新建聊天
`;
    const { pngPath } = await exportNativeTavernPack({
        card,
        avatarPng,
        exportDir: path.join(ROOT, 'export'),
        baseName: '罗丝',
        ntReadme,
    });

    fs.writeFileSync(
        path.join(ROOT, 'export/罗丝-NT-prompt.txt'),
        `v1.0：Main 留空（规则已在 PNG 世界书）。

若必须填 Main：
全程简体中文。只写 {{char}} 一条回复，80～220 字。先回应 {{user}} 最新一句。

Persona：来访者
勿绑 rose-thorn-yangsheng-world.json
`,
        'utf8',
    );

    fs.writeFileSync(
        path.join(ROOT, 'export/罗丝-养成说明.txt'),
        ntReadme +
            '\n重建:\n  node scripts/build-worldbook-rose-thorn.js\n  node scripts/build-character-rose-thorn.js\n',
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
