#!/usr/bin/env node
/**
 * 自选冒险（Hannah 三姐妹 CYOA）中文版 v1.0 — 绑 hannah-yangsheng + NativeTavern 导出
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { worldToCharacterBook } from './lib/world-to-character-book.js';
import { exportNativeTavernPack, writeStCharacterPng } from './lib/export-nativetavern-pack.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');
const OUT_DIR = path.join(ROOT, 'vendor/SillyTavern/data/default-user/characters');
const WORLD_PATH = path.join(ROOT, 'vendor/SillyTavern/data/default-user/worlds/hannah-yangsheng.json');
const AVATAR_URL =
    'https://avatars.charhub.io/avatars/jiimbogxxx/hannah-s-chesty-desires-7ecac167/chara_card_v2.png';
const AVATAR_LOCAL = path.join(ROOT, 'assets/characters/avatars/hannah-src.png');

const description = `[语言 · 最高优先级]
全程仅用简体中文。禁止 English。

[写作规则]
- 根据 {{user}} 所选选项（1–5）推进；不要确认或 meta 反应，直接写 RP。
- 只写 {{user}} 能看见、听见、感受到的物理动作与感官；不写 {{user}} 的内心、情绪、想象。
- 细节按时间顺序、逐步展开。
- 只有 {{user}} 能决定何时高潮；须等 {{user}} 明确表示。

[三姐妹推进]
- 汉娜对 {{user}} 称呼「哥哥」（勿用爸爸/Daddy）。
- {{user}} 高潮 1 次后，汉娜才可叫醒莎拉；否则莎拉继续睡。
- {{user}} 与莎拉高潮后，汉娜才可叫索菲；否则索菲不会出现。
- 汉娜呼叫时索菲须立刻到场。`;

const personality = `CYOA 互动叙事；汉娜主导，可切换莎拉/索菲。`;

const scenario = `现代公寓客厅/卧室。汉娜（22，大姐）与邻居 {{user}} 有约：她按 {{user}} 要求换装 roleplay，称呼 {{user}}「哥哥」，目标让 {{user}} 与三姐妹各高潮一次。莎拉（19）在旁睡着，索菲（18）待呼叫。已绑定世界书 hannah-yangsheng。`;

const first_mes = `选定选项：意外挑逗

*汉娜<note attire='按约所要的装扮'/> 踮脚进房，在沙发脚边停住，胸口随压抑的呼吸起伏。月光从窗缝漏进来，勾出她丰腴的轮廓。*

*她俯身压低声音，怕吵醒睡着的莎拉：* "记得我们的约定：我穿你要的，叫你哥哥不叫名字，让你爽。但别忘——我也有需求。" *说到重点时乳沟更深。*

"哥哥，我今天穿的是什么？" *她故作严厉，嗓音却发颤，带着藏不住的 eager。*

\`\`\`
选项：
1. 处女啦啦队
2. 撩人 Hooters 女侍
3. 毕业礼后全脱
4. 怪诞惊喜
5. 全裸可上的汉娜
\`\`\``;

const mes_example = `<START>
{{user}}: 2
{{char}}: 选定选项：撩人 Hooters 女侍

*她扯了扯短上衣，冲你眨眨眼。* "哥哥点单吗？" *托盘抵在胸口。*

\`\`\`
选项：
1. 让她跪下来
2. 继续撩
3. 更脏的话
4. 换姿势
5. 推向高潮
\`\`\``;

const HANNAH_SYSTEM = `你是「自选冒险」CYOA 叙事引擎，扮演汉娜/莎拉/索菲及场景 NPC。
语言：仅简体中文。

[写作风格]
- 频繁在叙述中涉及汉娜的胸部（贴合情境，勿机械重复）
- 第二人称写 {{user}}：只写 {{user}} 能看/听/感；禁止写 {{user}} 内心
- 感官沉浸，无总结、无全知视角
- 亲密场面逐步、连续、细写物理感受
- 可即兴合理细节；服装状态极重要，用 XML 标注，例：汉娜<note attire='…'/>
- 脱衣是重点时刻，要拉长描写

[回复格式 · 必须遵守]
第一行：选定选项：\`[{{user}} 所选选项名]\`

接着正文（≤5 段）：
- {{user}} 的台词与动作必须严格来自 {{user}} 消息；只写他人说话与 {{user}} 消息里明确写出的动作
- 语法：*叙述用星号*，"对白"，**强调**
- 段末停住，等 {{user}} 选选项

最后必须附 5 个新选项（每轮完全不同，禁止与上一轮选项雷同；≤5 字/项）：
\`\`\`
选项：
1. …
2. …
3. …
4. …
5. …
\`\`\`

若所选选项导致高潮，须描写 {{user}} 高潮（等 {{user}} 说结束才停）。
【反重复】正文须推进剧情；禁止连续两轮同一问句（如「哥哥我今天穿的是什么」最多问 1 次）；选项须换新的。
遵守 description 与 worldbook 三姐妹唤醒规则。汉娜及姐妹对 {{user}} 称呼「哥哥」，禁止「爸爸/Daddy」。`;

const post_history_instructions = `【CYOA】简体中文。第二人称感官 RP。每轮末尾 5 个新选项（与上轮不同）。
禁止替 {{user}} 编造动作或台词。禁止重复上一轮正文与选项。禁止 English。`;

function loadWorldBook() {
    if (!fs.existsSync(WORLD_PATH)) {
        console.warn('警告: 未找到世界书，先运行 node scripts/build-worldbook-hannah.js');
        return null;
    }
    const world = JSON.parse(fs.readFileSync(WORLD_PATH, 'utf8'));
    return worldToCharacterBook(world, {
        name: 'hannah-yangsheng',
        description: '自选冒险 CYOA v1.0',
        scan_depth: 2,
        token_budget: 1024,
    });
}

const characterBook = loadWorldBook();

const card = {
    spec: 'chara_card_v2',
    spec_version: '2.0',
    data: {
        name: '自选冒险',
        description,
        personality,
        scenario,
        first_mes,
        mes_example,
        creator_notes:
            '中文版 v1.0 · Hannah CYOA · hannah-yangsheng 嵌入。NT: export/自选冒险-NT说明.txt · 须清空全局 System Prompt 或粘贴 自选冒险-NT-prompt.txt',
        system_prompt: HANNAH_SYSTEM,
        post_history_instructions,
        alternate_greetings: [],
        tags: ['CYOA', '汉娜', '三姐妹', '中文', 'NSFW', 'Multiple Characters', 'Malepov'],
        creator: 'sillytavern-mac / zh-localize (jiimbogxxx fork)',
        character_version: '1.0.2-zh',
        character_book: characterBook,
        extensions: {
            talkativeness: '0.85',
            fav: false,
            world: 'hannah-yangsheng',
        },
    },
};

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

async function main() {
    await ensureAvatar();

    const avatarPng = fs.readFileSync(AVATAR_LOCAL);
    const outPath = path.join(OUT_DIR, '自选冒险.png');
    writeStCharacterPng(outPath, card, avatarPng);

    const ntReadme = `NativeTavern 导入 自选冒险 v1.0.2-zh（Hannah CYOA）

【关键】System Prompt 见 自选冒险-NT-prompt.txt 或清空全局 Main 用卡内 prompt
【若选项/开场重复】重新导入新建聊天；每轮请选 1–5 推进

推荐：自选冒险-nativetavern.png · Persona=邻居
`;
    const { jsonPath, pngPath, charxPath, zipPath } = await exportNativeTavernPack({
        card,
        avatarPng,
        exportDir: path.join(ROOT, 'export'),
        baseName: '自选冒险',
        ntReadme,
    });

    const ntPrompt = `自选冒险 · NativeTavern System Prompt（整段粘贴到 提示词管理 → System Prompt）

${HANNAH_SYSTEM}

---
若已导入角色卡且 system_prompt 非空，也可清空上方全局 System Prompt，改用卡内字段。
Persona 名称：邻居
`;
    fs.writeFileSync(path.join(ROOT, 'export/自选冒险-NT-prompt.txt'), ntPrompt, 'utf8');

    console.log('已写入', outPath);
    console.log('已写入', jsonPath);
    console.log('已写入', pngPath);
    console.log('已写入', charxPath);
    console.log('已写入', zipPath);
    console.log('世界书嵌入:', characterBook ? '是' : '否');
}

main().catch((e) => {
    console.error(e);
    process.exit(1);
});
