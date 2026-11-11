# 《一舞一愿·重新出发》曜金潮汐圣殿 Seedance 提示词 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 交付一份可直接复制到 Seedance 的 15 秒《重新出发》提示词，用曜金潮汐圣殿、三段同强度诗舞和唯一白帆表现“受阻—破浪—启程”。

**Architecture:** 以 `docs/superpowers/specs/2026-09-01-yi-wu-yi-yuan-qiancheng-01-seedance-design.md` 为设计真源，重写单集 `prompt.md`，只在可复制正文内保留模型可观察的角色、空间、动作、环境因果、摄影机和声音要求。新增一个独立契约测试，验证双图映射、六个时间窗、单事件、单白帆、无人声边界及内部信息隔离；提示词通过后向 25 列舞蹈台账追加唯一记录。实际 Seedance 调用继续由付费预览和用户当次确认门禁控制。

**Tech Stack:** Markdown、zsh、Python 3 标准库、CSV、Git、Seedance。

## Global Constraints

- 设计真源固定为 `docs/superpowers/specs/2026-09-01-yi-wu-yi-yuan-qiancheng-01-seedance-design.md`，不得退回旧海岸版 `0.000—7.441 秒` 三段语音映射。
- 使用两张日常栀夏 v04 图片：`assets/characters/归档/栀夏角色卡高写实CG-v04.png` 与 `assets/characters/栀夏角色母板高写实CG-v04-完整档案增彩版-Seedance上传版.jpg`。
- 15 秒、9:16、同一连续镜头、唯一人物栀夏、单人空手；不上传敦煌、九歌或阿砚母板。
- 场景固定为曜金潮汐圣殿：玄武岩海上长台、两座无门扉无发光结构的盐蚀巨石、低云、真实海面和破晓冷暖光。
- “圣殿”只表示庄严气质，不生成宗教建筑、仙侠宫殿、天门、祭坛或传送门。
- 三高潮固定为：`0.000—1.800 秒` 横向低位开潮、`4.800—7.200 秒` 斜向探海拉开纵深、`10.000—13.430 秒` 纵向提跃开云。
- 连接段固定为 `1.800—4.800 秒`、`7.200—10.000 秒`，动态余势固定为 `13.430—15.000 秒`。
- 13.430 秒后没有朗诵；提示词不得声称朗诵贯穿 15 秒，也不得要求人物生成逐字口型。
- Seedance 只生成无人声电影感国风音乐、海风、低浪、鞋履、衣袖和裙摆动作声；不得生成可辨识人声。
- 唯一环境事件是同一股潮雾与暗浪从封路到让路；曜金航路来自真实晨光的水面反射，尽头只出现一面白帆。
- 可复制正文不得包含朗诵文本、古诗原句、文件路径、版本号、内部动作分类、视觉指纹、验收说明或制作任务名。
- 不生成第二人物、阿砚、手持器物、第二场景、奔跑、连续多转、法阵、符文、传送门、粒子爆炸、巨型太阳、字幕、标题、logo 或水印。
- Seedance 是产生费用和外部状态的操作；提示词完成后只做预览。必须展示两张上传图、最终正文、15 秒、9:16、声音开且无人声、首轮 1 条和页面费用，并取得用户当次明确确认后才允许生成。
- 本计划不提交 `.superpowers/brainstorm/`、本地音频、未验收的 `audio-timing-v03.json` 或 `subtitle-plan-v03.json`，不带入工作区其他修改。

---

## File Structure

- `episodes/yiwu-yiyuan-qiancheng-01-restart-15s/prompt.md`：内部诗舞设计卡、两张上传图顺序、单一可复制 Seedance 正文、生成参数与调用门禁。
- `tests/test_yiwu_yiyuan_qiancheng_01_seedance_prompt.sh`：抽取唯一可复制正文，验证角色映射、六段时序、舞蹈与环境因果、无人声边界、内部信息隔离和台账唯一行。
- `operations/dance-design-history.csv`：追加本集 25 列视觉指纹，状态固定为 `designed`。

### Task 1: 先建立提示词与台账契约

**Files:**
- Create: `tests/test_yiwu_yiyuan_qiancheng_01_seedance_prompt.sh`
- Read: `episodes/yiwu-yiyuan-qiancheng-01-restart-15s/prompt.md`
- Read: `operations/dance-design-history.csv`

**Interfaces:**
- Consumes: Markdown 标记 `<!-- SEEDANCE_PROMPT_START -->` 与 `<!-- SEEDANCE_PROMPT_END -->`，以及 25 列 CSV 表头。
- Produces: 一个退出码为 0/1 的 zsh 契约测试；后续任务只在该测试通过时提交提示词。

- [ ] **Step 1: 创建失败测试**

测试脚本使用 `python3` 读取提示词与 CSV，核心逻辑固定为：

```python
start_marker = "<!-- SEEDANCE_PROMPT_START -->"
end_marker = "<!-- SEEDANCE_PROMPT_END -->"
if prompt_doc.count(start_marker) != 1 or prompt_doc.count(end_marker) != 1:
    raise SystemExit("FAIL: Seedance prompt must expose exactly one copyable block")

start = prompt_doc.index(start_marker) + len(start_marker)
end = prompt_doc.index(end_marker)
body = prompt_doc[start:end].strip()

expected_first_line = (
    "@图片1和@图片2都是本项目原创虚构数字角色栀夏，"
    "不对应任何现实人物、艺人或既有影视动漫角色。"
)
if body.splitlines()[0] != expected_first_line:
    raise SystemExit("FAIL: copyable prompt has the wrong original-character declaration")

image_refs = set(re.findall(r"@图片\d+", body))
if image_refs != {"@图片1", "@图片2"}:
    raise SystemExit(f"FAIL: unexpected upload references: {sorted(image_refs)}")
```

逐项要求以下短语出现在可复制正文：

```python
required_phrases = [
    "15 秒", "9:16", "同一连续镜头",
    "玄武岩海上长台", "两座盐蚀巨石构件", "唯一一面白帆",
    "深侧弓", "横向换重", "斜向探海", "纵向提跃",
    "真实晨光在海面的狭长金色反射", "同一股潮雾",
    "侧前方略低中全景", "沿玄武岩长台外缘斜向后退",
    "不生成任何可辨识人声",
]
```

六个时间窗必须各出现一次：

```python
windows = [
    "0.000—1.800 秒", "1.800—4.800 秒",
    "4.800—7.200 秒", "7.200—10.000 秒",
    "10.000—13.430 秒", "13.430—15.000 秒",
]
```

以下后期文本和内部信息不得进入可复制正文：

```python
for forbidden in [
    "送给重新出发的你", "这一程或许不轻松",
    "愿你所盼有期", "长风破浪会有时",
    "assets/", ".png", ".jpg", "v03", "v04",
    "视觉指纹", "高潮动作家族", "验收标准",
    "yiwu-yiyuan-qiancheng-01-restart-15s",
]:
    if forbidden in body:
        raise SystemExit(f"FAIL: forbidden production text leaked into prompt: {forbidden}")
```

用 `csv.DictReader` 断言表头恰有 25 列，本集 `episode` 恰有一行，并逐项匹配：

```python
expected_fields = {
    "poem": "李白《行路难·其一》",
    "climax_family": "三高潮潮雾开路序列",
    "peak_sequence": "横向低位开潮；斜向探海拉开纵深；纵向提跃开云",
    "peak_directions": "横向；斜向纵深；纵向",
    "peak_windows": "0.000—1.800秒；4.800—7.200秒；10.000—13.430秒",
    "status": "designed",
}
```

- [ ] **Step 2: 运行测试并确认红灯**

Run: `zsh tests/test_yiwu_yiyuan_qiancheng_01_seedance_prompt.sh`

Expected: FAIL；旧 `prompt.md` 仍含 7.441 秒后无人声旧结构，且台账不存在本集记录。

- [ ] **Step 3: 提交测试红灯基线**

不单独提交失败测试。它与 Task 2 的提示词及台账作为一个可审查单元共同提交。

### Task 2: 重写曜金潮汐圣殿可复制提示词

**Files:**
- Modify: `episodes/yiwu-yiyuan-qiancheng-01-restart-15s/prompt.md`
- Test: `tests/test_yiwu_yiyuan_qiancheng_01_seedance_prompt.sh`

**Interfaces:**
- Consumes: Task 1 的唯一正文标记和设计真源中的角色、场景、动作、摄影机与声音规则。
- Produces: 一个只需上传两张角色图即可复制使用的 Seedance 正文。

- [ ] **Step 1: 重写内部设计卡**

删除旧的普通石岸、`0.000—7.441 秒` 三段朗诵和 7.441 秒后长尾描述。内部卡固定记录：

```markdown
- 场景：曜金潮汐圣殿；玄武岩海上长台与两座盐蚀巨石构件。
- 唯一事件：同一股潮雾与暗浪从封路到让路。
- 最终结果：真实晨光在海面形成狭长曜金航路，尽头只出现一面白帆。
- 三高潮：横向低位开潮；斜向探海拉开纵深；纵向提跃开云。
- 三方向：横向；斜向纵深；纵向。
- 摄影机：侧前方略低中全景，沿长台外缘斜向后退；有限侧移、短促降低后拉、轻抬扩大景别。
- 声音：原片无人声；v03 后期朗诵在 13.430 秒结束，最后 1.570 秒为动态余势。
```

- [ ] **Step 2: 写入唯一可复制正文**

正文置于唯一一对标记之间，并按以下顺序完整书写：

```text
@图片1和@图片2都是本项目原创虚构数字角色栀夏，不对应任何现实人物、艺人或既有影视动漫角色。

【图片职责与作品条件】
图片1锁定同一张脸、年轻年龄感和身体比例；图片2锁定黑色高马尾、白花银枝发冠、盛唐高腰服装、浅青月白藕粉色板、鞋履和电影级高写实材质。两张图只锁定角色身份与造型，不复刻卡片排版、文字、分区或背景。本片为 15 秒、9:16、同一连续镜头的单场景原创国风诗舞，栀夏是唯一人物，双手空着。

【空间与第一帧】
天光将亮的海面上，一条潮湿深黑的玄武岩海上长台伸向地平线，两侧只有两座无门扉、无雕像、无发光结构的盐蚀巨石构件。它们只形成超尺度取景框和纵深视差，不构成宫殿、天门或传送门。右后方地平线是唯一主光源，低云和暗浪横断去路，远方白帆尚不可见。第一帧完整显示栀夏头顶至鞋履、双脚承重、长台边缘、真实海面和两侧巨石尺度；她已经处于未完成的深侧弓蓄势。

【唯一事件】
栀夏以连续舞蹈迎住并打开横断去路的同一股潮雾和暗浪。潮雾只在身体动作完成后响应，依次横向退开、沿斜向纵深拉开、向上抬离低云；最后真实晨光落在海面，形成狭长金色反射，尽头出现唯一一面白帆。
```

随后分别写明六个时间窗，每个窗口都包含进入、发展、离开、环境后响应和摄影机反馈：

- `0.000—1.800 秒`：深侧弓、0.300 秒内横向换重、胸腰反拧、低位宽横弧；潮雾形成低薄横带；镜头有限侧移。
- `1.800—4.800 秒`：一至两步换重和拧倾连接，目光越过暗浪，衣料延迟响应，不奔跑、不站住。
- `4.800—7.200 秒`：前脚承重、斜向探海、后腿受控抬伸、落脚改面；潮雾沿长台轴线拉开；镜头短促降低并后拉。
- `7.200—10.000 秒`：反向换重、降低身体、一臂回收一臂向远方延伸，为第三高潮蓄力。
- `10.000—13.430 秒`：深沉身、腿部蹬伸、一次短促纵向提跃、稳定落地、高低错层双臂；低云抬开、晨光形成曜金航路、唯一白帆出现；镜头轻抬扩大景别。
- `13.430—15.000 秒`：半步换重、降低高位手臂、胸腰与目光回到白帆方向，最后 0.300 秒才接近完成态。

正文末尾写齐：电影级高写实材质与物理、单一主路径、无人声音乐及环境声、角色稳定和禁止项。禁止项使用清楚自然语言，不得省略第二人物、阿砚、手持器物、奔跑、连续多转、法阵、符文、传送门、粒子爆炸、巨型太阳、字幕、标题、logo 和水印。

- [ ] **Step 3: 添加生成参数与门禁**

在可复制正文外记录：

```markdown
- 时长：15 秒
- 画幅：9:16
- 首轮条数：1 条
- 输入：图片1为日常栀夏主卡，图片2为日常栀夏完整母板
- 声音：开启，只保留无人声音乐、环境声和动作声
- 外部生成前：展示最终正文与页面费用，取得当次明确确认
```

### Task 3: 登记视觉指纹并验证提示词

**Files:**
- Modify: `operations/dance-design-history.csv`
- Test: `tests/test_yiwu_yiyuan_qiancheng_01_seedance_prompt.sh`
- Verify: `episodes/yiwu-yiyuan-qiancheng-01-restart-15s/prompt.md`

**Interfaces:**
- Consumes: Task 2 的最终三高潮、方向、窗口、衣料轨迹和镜头反馈。
- Produces: 一条状态为 `designed` 的 25 列去重记录，以及通过的提示词契约。

- [ ] **Step 1: 追加唯一台账行**

按现有表头追加以下 25 个字段；字段内部只使用中文分号，不增加逗号：

```text
yiwu-yiyuan-qiancheng-01-restart-15s
李白《行路难·其一》
深侧弓迎风不对称蓄势
玄武岩长台外缘小范围换重与两步交叉连接
三高潮潮雾开路序列
零完整旋转；两次改面
深侧弓横向换重；斜向探海；深沉纵向提跃
三分之四正面深侧弓低高错层
低位横弧；前下后上斜线；高低纵线
侧弓一屈一伸；前脚承重后腿抬伸；前后脚稳定落地
衣袖裙摆与潮雾
低位宽弧；前后斜向长线；上下错层长线
同一股潮雾与暗浪
横向薄带；斜向纵深通道；向上抬云并显曜金航路
0.000—1.800秒；4.800—7.200秒；10.000—13.430秒
侧前略低沿长台外缘斜向后退
有限侧移；短促降低并后拉；轻抬并扩大景别
半步换重并在白帆方向的动作余势中结束
designed
一舞一愿前程01；日常栀夏双图；单人空手；白帆唯一；13.430秒后无人声余势
横向低位开潮；斜向探海拉开纵深；纵向提跃开云
横向；斜向纵深；纵向
0.000—1.800秒；4.800—7.200秒；10.000—13.430秒
衣袖低位横弧；衣袖前后斜线；衣袖高低纵线
有限侧移；短促降低并后拉；轻抬并扩大景别
```

- [ ] **Step 2: 运行提示词契约并确认绿灯**

Run: `zsh tests/test_yiwu_yiyuan_qiancheng_01_seedance_prompt.sh`

Expected: PASS；唯一正文、双图、六个时间窗、单白帆、无人声和唯一 25 列台账行均通过。

- [ ] **Step 3: 运行项目级相关规则测试**

Run: `zsh tests/test_three_equal_climaxes_rules.sh && zsh tests/test_choreography_diversity_v2_rules.sh && zsh tests/test_late_pose_ending_rules.sh`

Expected: PASS；三高潮、方向去重和最后 0.300 秒完成态规则未被破坏。

- [ ] **Step 4: 检查正文泄漏与 Git 范围**

Run: `git diff --check -- episodes/yiwu-yiyuan-qiancheng-01-restart-15s/prompt.md tests/test_yiwu_yiyuan_qiancheng_01_seedance_prompt.sh operations/dance-design-history.csv`

Expected: 无输出、退出码 0；暂存范围只包含这三个文件。

- [ ] **Step 5: 提交提示词与台账**

```bash
git add episodes/yiwu-yiyuan-qiancheng-01-restart-15s/prompt.md \
  tests/test_yiwu_yiyuan_qiancheng_01_seedance_prompt.sh \
  operations/dance-design-history.csv
git commit -m "完成重新出发曜金潮汐圣殿提示词"
```

### Task 4: Seedance 调用前预览与暂停

**Files:**
- Read: `episodes/yiwu-yiyuan-qiancheng-01-restart-15s/prompt.md`
- Read: `assets/characters/归档/栀夏角色卡高写实CG-v04.png`
- Read: `assets/characters/栀夏角色母板高写实CG-v04-完整档案增彩版-Seedance上传版.jpg`

- [ ] **Step 1: 展示两张输入图及顺序**

向用户明确：图片1负责脸、年龄感和比例；图片2负责多角度、发型、发冠、服装、色板、鞋履和材质。不得临时替换为敦煌、九歌或阿砚母板。

- [ ] **Step 2: 展示完整可复制正文和生成参数**

逐字展示 `SEEDANCE_PROMPT_START/END` 之间的正文，并列出：15 秒、9:16、声音开启但无人声、首轮 1 条。说明后期 v03 朗诵只到 13.430 秒，最后 1.570 秒为舞蹈和音乐余势。

- [ ] **Step 3: 展示页面费用并等待明确确认**

打开 Seedance 页面后读取当前页面显示的模型、分辨率和预计费用。没有用户在看到最终正文、输入图、调用数量和页面费用后的当次明确确认，不得点击生成。

---

## Definition of Done

- `prompt.md` 只暴露一个可复制正文，且不含旧 7.441 秒结构。
- 正文完整表达曜金潮汐圣殿、三段不同方向高潮、同一潮雾因果、真实曜金反光和唯一白帆。
- 正文不泄漏朗诵文本、古诗、文件名、版本号、内部分类或验收说明。
- 台账保持 25 列，本集只有一行，方向顺序固定为“横向—斜向纵深—纵向”。
- 所有本地契约与相关规则测试通过。
- 在用户看到最终正文、双图、参数、调用数量和费用前，不发生 Seedance 生成。
