# AI Divination Disc Summoning Assets Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 生成、验收并归档“月璃天衡盘”道具卡、栀夏“引弧起盘”动作卡和 3 秒召唤模板视频，作为《栀夏赛博起卦》后续单集的固定母板。

**Architecture:** 三项资产按依赖关系串行完成：先锁定卦盘，再用卦盘与栀夏 approved 母板生成动作卡，最后用两张 approved 卡生成模板视频。每项资产必须经用户明确确认后才能归档并成为下一项的输入；单集卦象、卦名和卦辞不固化进模板视频。

**Tech Stack:** ChatGPT 网页图片生成、Seedance 或同级图生视频工具、PNG、H.264 MP4、`sips`、`ffmpeg`、`ffprobe`、shell 验收脚本、CSV 资产清单。

## Global Constraints

- 设计依据：`docs/superpowers/specs/2026-08-26-ai-divination-disc-and-summoning-template-design.md`。
- 栀夏身份唯一依据：`assets/characters/栀夏角色卡电影半写实-v02.png`。
- 栀夏身体与服装结构依据：`assets/characters/栀夏全身比例卡电影半写实-v02.png`。
- 栀夏表情与口型依据：`assets/characters/栀夏表情口型综合卡电影半写实-v01.png`。
- 卦盘名称固定为“月璃天衡盘”，召唤动作固定为“引弧起盘”。
- 卦盘不依附古籍、桌面、手掌或其他实体道具。
- 卦盘配色固定为月白、浅青、暖金与极少朱砂，不使用蓝紫霓虹、强光柱或游戏法阵。
- 六爻恰好六位，自下而上生成；首集“山雷颐”自下而上为阳、阴、阴、阴、阴、阳。
- 所有准确中文、卦名和卦辞均由后期透明卡叠加，图片与模板视频不得生成乱码文字。
- 任何付费生成调用前必须先展示调用计划并获得用户确认。
- 用户未明确确认的候选图或视频不得写入 `assets/inventory.csv` 的 `approved` 状态。

---

### Task 1: 建立三项资产的自动验收门槛

**Files:**
- Create: `zhixia-feihualing/tests/test_cyber_divination_summon_assets.sh`
- Modify: `zhixia-feihualing/assets/inventory.csv`

**Interfaces:**
- Consumes: 三项设计中约定的文件名、画幅、时长和 inventory 资产标识。
- Produces: 一个在任意资产缺失、画幅错误、视频时长错误或 inventory 未批准时失败的统一验收命令。

- [ ] **Step 1: 写入预期失败的验收脚本**

```zsh
#!/bin/zsh
set -euo pipefail

project_dir="$(cd "$(dirname "$0")/.." && pwd)"
disc="$project_dir/assets/props/ai-divination-disk-v01/master.png"
action="$project_dir/assets/characters/栀夏引弧起盘动作卡电影半写实-v01.png"
video="$project_dir/assets/generated-video/templates/zhixia-summon-divination-disc-template-v01.mp4"
inventory="$project_dir/assets/inventory.csv"

test -s "$disc"
test -s "$action"
test -s "$video"

read disc_w disc_h <<< "$(sips -g pixelWidth -g pixelHeight "$disc" 2>/dev/null | awk '/pixelWidth/{w=$2}/pixelHeight/{h=$2}END{print w" "h}')"
awk -v w="$disc_w" -v h="$disc_h" 'BEGIN { exit !(w >= 720 && h >= 1280 && w / h >= 0.55 && w / h <= 0.57) }'

read action_w action_h <<< "$(sips -g pixelWidth -g pixelHeight "$action" 2>/dev/null | awk '/pixelWidth/{w=$2}/pixelHeight/{h=$2}END{print w" "h}')"
awk -v w="$action_w" -v h="$action_h" 'BEGIN { exit !(w >= 1280 && h >= 720 && w / h >= 1.70 && w / h <= 1.90) }'

ffmpeg -v error -i "$disc" -frames:v 1 -f null -
ffmpeg -v error -i "$action" -frames:v 1 -f null -
ffmpeg -v error -i "$video" -frames:v 1 -f null -

duration="$(ffprobe -v error -show_entries format=duration -of default=nk=1:nw=1 "$video")"
awk -v d="$duration" 'BEGIN { exit !(d >= 2.8 && d <= 3.2) }'

rg -q '^ai-divination-disk-v01,prop,AI卦盘,identity-master,assets/props/ai-divination-disk-v01/master.png,approved,' "$inventory"
rg -q '^zhixia-summon-divination-disc-action-v01,character,栀夏,summoning-action-master,assets/characters/栀夏引弧起盘动作卡电影半写实-v01.png,approved,' "$inventory"
rg -q '^zhixia-summon-divination-disc-template-v01,video,栀夏,summoning-video-template,assets/generated-video/templates/zhixia-summon-divination-disc-template-v01.mp4,approved,' "$inventory"

echo "cyber divination summon assets: PASS"
```

- [ ] **Step 2: 运行脚本并确认因资产尚未完成而失败**

Run: `zsh zhixia-feihualing/tests/test_cyber_divination_summon_assets.sh`

Expected: FAIL at missing `assets/props/ai-divination-disk-v01/master.png`，且不得提前在 inventory 中写入 approved 记录。

- [ ] **Step 3: 提交验收门槛**

```bash
git add zhixia-feihualing/tests/test_cyber_divination_summon_assets.sh
git commit -m "增加卦盘召唤资产验收门槛"
```

### Task 2: 生成并确认月璃天衡盘道具卡

**Files:**
- Reference: 用户提供的卦盘构思参考图
- Create after approval: `zhixia-feihualing/assets/props/ai-divination-disk-v01/master.png`
- Modify after approval: `zhixia-feihualing/assets/inventory.csv`

**Interfaces:**
- Consumes: 参考图的青金半透明质感与 approved 设计稿。
- Produces: 唯一卦盘母板 `ai-divination-disk-v01`，供动作卡和后续单集引用。

- [ ] **Step 1: 在 ChatGPT 中附上参考图并使用完整提示词生成一张候选图**

```text
请根据我上传的参考图，为东方幻想短视频系列设计一张全新的“AI 卦盘道具设计卡”。参考图只用于理解青金色半透明悬浮卦盘的气质，不要复制参考图中的标题、说明文字、六套候选方案、现有造型或具体构图。

最终道具名为“月璃天衡盘”。画面为 9:16 竖版、电影级半写实东方幻想道具设计图、浅暖灰无缝影棚背景、柔和中性布光。整张图只展示同一件卦盘在不同角度和状态下的严格一致设计，不出现人物、手、阿砚、古籍、桌面、建筑、标题、标签、说明文字、Logo 或水印。

卦盘主体是一面直径约 30 厘米、视觉厚度不足 1 厘米的单层轻薄悬浮圆盘。材质为月白半透明薄璃，边缘像磨砂玉片，内部有极淡的水墨纤维；绝不是厚重铜盘、机械罗盘、托盘、盾牌或地面法阵。配色以月白和低饱和浅青为主，暖金只用于极细轮廓、均匀刻度与结果锁定线，盘心上缘只有一枚很小的朱砂水滴形定位纹。

盘面结构必须统一：外环为暖金极细轮廓和八个均匀方位区；中环为浅青色环形数据轨道，带克制的点阵、断续线、书法飞白和细密刻度；中心为六个纵向爻位及上下卦、卦名、卦辞的干净留白信息区。不要生成任何可辨识汉字、英文字母或数字。

版式：上半部放一张最大的三分之四俯视主视图；中部并列放同一卦盘的正俯视图和低角度侧视图；下半部横向放三个较小状态图。三个状态必须是同一件道具、同一轮廓、同一材质、同一刻度和同一信息区：第一格为未起卦，中心完全留白；第二格为六爻生成中，由下向上已经亮起前三个爻位；第三格为卦象揭示，显示首集“山雷颐”的六条爻线，自下而上依次为完整横线、中央断开的横线、中央断开的横线、中央断开的横线、中央断开的横线、完整横线。第三格仍不显示卦名和卦辞文字。

光效必须克制：月白柔光、浅青沿线微光、结果确认时少量暖金；没有蓝紫霓虹、强光柱、爆闪、雷电、粒子漩涡、烟雾法术或电子游戏界面感。画面精致、古雅、清透、安静，能与栀夏的月白抹胸、浅青薄纱长袖、浅粉腰带和暖金花纹协调。

严格要求：只生成一张完整设计卡；所有视图中的卦盘结构必须一致；圆盘完整不裁切；六爻恰好六位；不要太厚；不要多层分离；不要文字乱码；不要人物；不要参考图中的说明排版。
```

- [ ] **Step 2: 按道具清单逐项人工验收**

Run: 打开 `assets/props/ai-divination-disk-v01/qa-checklist.md`，逐项检查三个状态、单层结构、六爻数量与方向、配色、文字留白和无水印。

Expected: 所有项目通过；若任一状态结构漂移、六爻错误或出现乱码，只提供定向修改提示词，不归档。

- [ ] **Step 3: 用户明确确认后归档原图**

Run: 将用户确认的原始 PNG 原样复制为 `zhixia-feihualing/assets/props/ai-divination-disk-v01/master.png`，不得重编码或调整尺寸；使用 `cmp` 与 `shasum -a 256` 核对复制前后文件一致。

- [ ] **Step 4: 在 inventory 追加 approved 记录**

```csv
ai-divination-disk-v01,prop,AI卦盘,identity-master,assets/props/ai-divination-disk-v01/master.png,approved,ChatGPT web image generation,original AI-assisted asset,9:16；月璃天衡盘唯一母板；月白薄璃浅青墨线暖金刻度与极少朱砂；含未起卦六爻生成中卦象揭示三个连续状态
```

- [ ] **Step 5: 运行现有道具测试并提交**

Run: `zsh zhixia-feihualing/tests/test_cyber_divination_prop.sh`

Expected: `cyber divination prop: PASS`

```bash
git add zhixia-feihualing/assets/props/ai-divination-disk-v01/master.png zhixia-feihualing/assets/inventory.csv
git commit -m "归档月璃天衡盘道具母板"
```

### Task 3: 生成并确认栀夏“引弧起盘”动作卡

**Files:**
- Reference: `zhixia-feihualing/assets/characters/栀夏角色卡电影半写实-v02.png`
- Reference: `zhixia-feihualing/assets/characters/栀夏全身比例卡电影半写实-v02.png`
- Reference: `zhixia-feihualing/assets/props/ai-divination-disk-v01/master.png`
- Create after approval: `zhixia-feihualing/assets/characters/栀夏引弧起盘动作卡电影半写实-v01.png`
- Modify after approval: `zhixia-feihualing/assets/inventory.csv`

**Interfaces:**
- Consumes: approved 栀夏身份与服装母板、approved 月璃天衡盘母板。
- Produces: 四格召唤动作母板 `zhixia-summon-divination-disc-action-v01`，供模板视频引用。

- [ ] **Step 1: 在 ChatGPT 中同时附上三张 approved 参考图并使用完整提示词**

```text
请严格参考我上传的栀夏身份卡、栀夏全身比例卡和“月璃天衡盘”道具卡，生成一张 16:9 横版、四列等宽的电影级半写实东方幻想动作分解卡。人物必须是同一个栀夏，脸型、五官、黑色高马尾、白花暖金发饰、胸部体态、抹胸上缘高度和服装全部保持一致：月白抹胸、敞开的浅青半透明薄纱大袖衫、浅粉腰带、浅青高腰长裙上缘。不要重新设计人物或服装。

背景为浅暖灰无缝影棚，固定中近景、正面略偏左三分之四机位，完整拍到头部、上半身、左右双手和桌面上方的卦盘空间。四格中的人物大小、机位、光线、发型、服装和表情必须一致；栀夏全程神情平静专注，不微笑、不闭眼、不夸张施法。

动作名为“引弧起盘”，从左到右严格分为四格：
第一格，起势：右手从腰侧抬至胸腰之间，手肘贴近身体，掌心仍偏向侧面；左手自然稳定，不参与动作。
第二格，翻腕：右腕平稳外翻，掌心斜向上；拇指放松，无名指与小指自然微弯，五指全部清楚可见。
第三格，引弧：右手食指与中指自然并拢向前伸出，在桌面上空顺时针划出约四分之三圆的短弧；指尖留下克制的月白浅青光迹，弧线末端只有少量暖金；此格尚未出现完整卦盘。
第四格，起盘：双指在圆弧缺口处轻轻向上一挑，光弧闭合；与参考道具卡完全一致的单层“月璃天衡盘”在人物前方约一臂距离处悬浮展开，只显示未起卦空白状态，不显示具体六爻或文字。卦盘不接触手掌，不被手托住。

手部必须严格正确：每只手恰好五指，没有多指、少指、融合指、交叉指或粘连手掌；食指与中指只是并拢而不是融合；两只手不互相遮挡。右侧薄纱大袖随抬臂轻微后滑，露出完整手腕和手指，但服装结构不变。左手四格保持同一自然姿势。

不要阿砚，不要古籍，不要桌面剧情道具，不要字幕、标题、格子编号、说明文字、Logo、水印、蓝紫霓虹、强光柱或复杂粒子。四格之间只用细窄浅灰分隔线。重点是角色一致、手势清楚、动作连续、卦盘身份准确。
```

- [ ] **Step 2: 人工检查人物、双手与动作连续性**

Expected: 四格人物身份一致；右手各五指正确；左手稳定；动作从起势到起盘连续；只有第四格出现完整的未起卦卦盘。

- [ ] **Step 3: 用户明确确认后原样归档并登记**

```csv
zhixia-summon-divination-disc-action-v01,character,栀夏,summoning-action-master,assets/characters/栀夏引弧起盘动作卡电影半写实-v01.png,approved,ChatGPT web image generation,original AI-assisted asset,16:9四列动作分解；起势翻腕双指引弧起盘；严格引用栀夏v02与月璃天衡盘母板；模板视频唯一动作依据
```

Run: 使用 `cmp` 和 `shasum -a 256` 确认归档文件与用户提供原图一致。

- [ ] **Step 4: 提交动作卡**

```bash
git add zhixia-feihualing/assets/characters/栀夏引弧起盘动作卡电影半写实-v01.png zhixia-feihualing/assets/inventory.csv
git commit -m "归档栀夏引弧起盘动作母板"
```

### Task 4: 生成并确认 3 秒召唤动作模板视频

**Files:**
- Reference: `zhixia-feihualing/assets/characters/栀夏角色卡电影半写实-v02.png`
- Reference: `zhixia-feihualing/assets/characters/栀夏引弧起盘动作卡电影半写实-v01.png`
- Reference: `zhixia-feihualing/assets/props/ai-divination-disk-v01/master.png`
- Create after approval: `zhixia-feihualing/assets/generated-video/templates/zhixia-summon-divination-disc-template-v01.mp4`
- Modify after approval: `zhixia-feihualing/assets/inventory.csv`

**Interfaces:**
- Consumes: approved 栀夏身份卡、动作卡和月璃天衡盘道具卡。
- Produces: 无对白、无具体卦象的 3 秒动作模板，末帧供所有单集衔接六爻生成。

- [ ] **Step 1: 付费生成前向用户展示调用计划并获得确认**

Expected: 用户明确确认生成平台、调用次数和预计成本后才调用；若用户自行在网页生成，则跳过 API 调用，只交付提示词。

- [ ] **Step 2: 使用三张 approved 参考图和完整视频提示词**

```text
生成一段 9:16 竖屏、3 秒、单镜头、电影级半写实东方幻想人物动作模板视频。严格绑定参考图中的栀夏身份、服装和“引弧起盘”四格动作，严格绑定参考图中的“月璃天衡盘”外观。浅暖灰无缝影棚背景，固定中近景静止机位，完整拍到栀夏头部、上半身、左右双手和她前方的卦盘空间。镜头不推拉、不摇移、不环绕、不切换。

时间必须清楚：0.0—0.5 秒，栀夏自然待机，双手稳定；0.5—0.8 秒，右手从腰侧抬至胸腰之间；0.8—1.1 秒，右腕平稳外翻，掌心斜向上；1.1—1.8 秒，右手食指与中指自然并拢，在前方顺时针划出约四分之三圆短弧，指尖只有克制的月白浅青光迹，末端出现极少暖金；1.8—2.3 秒，双指轻轻向上一挑，光弧闭合，同一面单层月璃天衡盘在人物前方约一臂距离处悬浮展开；2.3—3.0 秒，人物与卦盘完全稳定停留。

卦盘只显示未起卦空白状态，不生成六爻、卦名、卦辞、汉字、数字或其他具体结果。卦盘不接触手掌，不跟随手掌漂移。栀夏神情平静专注，不微笑、不闭眼；左手全程保持自然稳定；每只手恰好五指，食指与中指只并拢不融合。浅青薄纱大袖随抬臂产生轻微真实布料运动，发型、发饰、抹胸、腰带和身体比例不改变。

无对白、无口型表演、无字幕、无标题、无Logo、无水印、无阿砚、无古籍、无桌面道具、无蓝紫霓虹、无强光柱、无爆闪、无雷电、无烟雾漩涡、无镜头运动、无多指、无手部变形、无人物身份漂移、无卦盘结构漂移。允许极轻衣袖声、单次墨滴声和短促数字脉冲，不生成可辨识人声。最后至少 0.5 秒必须是稳定静止的可衔接末帧。
```

- [ ] **Step 3: 抽帧验收动作连续性与末帧**

Run: 抽检 0.0、0.5、0.8、1.1、1.8、2.3、2.9 秒。

Expected: 栀夏身份与五指稳定；动作顺序正确；卦盘在 1.8 秒前未完整出现；2.3—3.0 秒未起卦卦盘稳定；无具体六爻与文字。

- [ ] **Step 4: 用户明确确认后原样归档并登记**

```csv
zhixia-summon-divination-disc-template-v01,video,栀夏,summoning-video-template,assets/generated-video/templates/zhixia-summon-divination-disc-template-v01.mp4,approved,Seedance,original AI-assisted asset,9:16约3秒；固定中近景单镜头；引弧起盘完整动作；末段稳定未起卦卦盘；无对白无具体卦象；后续单集统一衔接模板
```

- [ ] **Step 5: 运行三项资产统一验收并提交**

Run: `zsh zhixia-feihualing/tests/test_cyber_divination_summon_assets.sh`

Expected: `cyber divination summon assets: PASS`

```bash
git add zhixia-feihualing/assets/generated-video/templates/zhixia-summon-divination-disc-template-v01.mp4 zhixia-feihualing/assets/inventory.csv
git commit -m "归档栀夏卦盘召唤模板视频"
```

### Task 5: 回写系列引用规则并完成最终复核

**Files:**
- Modify: `zhixia-feihualing/docs/superpowers/specs/2026-08-26-zhixia-cyber-divination-series-design.md`
- Modify: `zhixia-feihualing/episodes/cyber-divination-ep01/README.md`
- Test: `zhixia-feihualing/tests/test_cyber_divination_summon_assets.sh`
- Test: `zhixia-feihualing/tests/test_cyber_divination_ep01_manifest.py`

**Interfaces:**
- Consumes: 三项 approved 资产标识与归档路径。
- Produces: 第一集与后续单集都只引用固定母板、不再描述新卦盘或新召唤手势的制作规则。

- [ ] **Step 1: 在系列设计稿和第一集 README 写入三个固定引用路径**

```markdown
- 卦盘母板：`assets/props/ai-divination-disk-v01/master.png`。
- 召唤动作母板：`assets/characters/栀夏引弧起盘动作卡电影半写实-v01.png`。
- 召唤模板视频：`assets/generated-video/templates/zhixia-summon-divination-disc-template-v01.mp4`。
- 单集从模板视频的稳定末帧继续生成六爻，不重新设计人物手势或卦盘外观。
```

- [ ] **Step 2: 搜索并清除冲突设定**

Run: `rg -n '古籍上方|轻触古籍|轻触书页|重新设计卦盘|复杂结印' zhixia-feihualing/docs/superpowers/specs/2026-08-26-zhixia-cyber-divination-series-design.md zhixia-feihualing/episodes/cyber-divination-ep01/README.md`

Expected: 无匹配；文档中只保留“引弧起盘”和无实体依附悬浮卦盘。

- [ ] **Step 3: 运行最终验证**

Run: `zsh zhixia-feihualing/tests/test_cyber_divination_summon_assets.sh`

Expected: `cyber divination summon assets: PASS`

Run: `python3 -m unittest zhixia-feihualing/tests/test_cyber_divination_ep01_manifest.py`

Expected: 全部测试通过，无 failure 或 error。

- [ ] **Step 4: 提交引用规则**

```bash
git add zhixia-feihualing/docs/superpowers/specs/2026-08-26-zhixia-cyber-divination-series-design.md zhixia-feihualing/episodes/cyber-divination-ep01/README.md
git commit -m "固定赛博起卦召唤母板引用"
```
