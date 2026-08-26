# AI Divination Disc Summoning Assets Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 生成、验收并归档“星轨六爻盘”道具卡、栀夏“引弧起盘”六段综合动作卡和 3 秒召唤模板视频，作为《栀夏赛博起卦》后续单集的固定母板。

**Architecture:** 三项资产按依赖关系串行完成：先锁定卦盘，再用卦盘与栀夏 approved 母板生成动作卡，最后用两张 approved 卡生成模板视频。每项资产必须经用户明确确认后才能归档并成为下一项的输入；单集卦象、卦名和卦辞不固化进模板视频。

**Tech Stack:** ChatGPT 网页图片生成、Seedance 或同级图生视频工具、PNG、H.264 MP4、`sips`、`ffmpeg`、`ffprobe`、shell 验收脚本、CSV 资产清单。

## Global Constraints

- 设计依据：`docs/superpowers/specs/2026-08-26-ai-divination-disc-and-summoning-template-design.md`。
- 栀夏身份唯一依据：`assets/characters/栀夏角色卡电影半写实-v02.png`。
- 栀夏身体与服装结构依据：`assets/characters/栀夏全身比例卡电影半写实-v02.png`。
- 栀夏表情与口型依据：`assets/characters/栀夏表情口型综合卡电影半写实-v01.png`。
- 卦盘名称固定为“星轨六爻盘”，召唤动作固定为“引弧起盘”。
- 卦盘不依附古籍、桌面、手掌或其他实体道具。
- 卦盘为单层平面悬浮光盘，不做 3D 分层结构。
- 卦盘配色固定为月白、浅青、暖金与极少朱砂，不使用蓝紫霓虹、强光柱或游戏法阵。
- 主视图中心恰好六个等宽、等距的空爻槽，不得出现第七槽，不得预填六条阳爻。
- 阳爻为一条完整横线，阴爻为中央断开的两段等长横线；首集“山雷颐”自下而上为阳、阴、阴、阴、阴、阳。
- 六段流程固定为星点聚拢、星轨显现、能量汇聚、六爻生成、卦象稳定、余光收束。
- 所有准确中文、卦名和卦辞均由后期透明卡叠加，图片与模板视频不得生成乱码文字。
- 任何付费生成调用前必须先展示调用计划并获得用户确认。
- 用户未明确确认的候选图或视频不得写入 `assets/inventory.csv` 的 `approved` 状态。

---

### Task 1: 建立三项资产的自动验收门槛

**Files:**
- Create: `zhixia-feihualing/tests/test_cyber_divination_summon_assets.sh`
- Modify: `zhixia-feihualing/tests/test_cyber_divination_prop.sh`

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
awk -v w="$disc_w" -v h="$disc_h" 'BEGIN { exit !(w >= 1280 && h >= 720 && w / h >= 1.70 && w / h <= 1.90) }'

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

- [ ] **Step 2: 把现有道具测试的画幅门槛改为 16:9**

将 `test_cyber_divination_prop.sh` 中原有的 9:16 判断替换为：

```zsh
awk -v w="$width" -v h="$height" \
  'BEGIN { exit !(w >= 1280 && h >= 720 && w / h >= 1.70 && w / h <= 1.90) }'
```

- [ ] **Step 3: 运行脚本并确认因资产尚未完成而失败**

Run: `zsh zhixia-feihualing/tests/test_cyber_divination_summon_assets.sh`

Expected: FAIL at missing `assets/props/ai-divination-disk-v01/master.png`，且不得提前在 inventory 中写入 approved 记录。

- [ ] **Step 4: 提交验收门槛**

```bash
git add zhixia-feihualing/tests/test_cyber_divination_summon_assets.sh zhixia-feihualing/tests/test_cyber_divination_prop.sh
git commit -m "增加卦盘召唤资产验收门槛"
```

### Task 2: 生成并确认星轨六爻盘道具卡

**Files:**
- Reference: 用户提供的卦盘构思参考图
- Create after approval: `zhixia-feihualing/assets/props/ai-divination-disk-v01/master.png`
- Modify after approval: `zhixia-feihualing/assets/inventory.csv`

**Interfaces:**
- Consumes: 参考图的青金半透明质感与 approved 设计稿。
- Produces: 唯一卦盘母板 `ai-divination-disk-v01`，供动作卡和后续单集引用。

- [ ] **Step 1: 在 ChatGPT 中附上参考图并使用完整提示词生成一张候选图**

```text
请以我上传的“D. 星象轨迹·天机卦盘”及其右侧六格起卦动画流程图为主要视觉参考，重新设计一张能够直接作为后续短视频母板的最终卦盘设计板。参考图只用于理解星象轨迹卦面、同心圆环、青金色光效和六段流程，不复制其中标题、说明文字、错误爻位数量、现成汉字或具体版式文字。

最终道具名为“星轨六爻盘”。生成一张 16:9 横版、电影级半写实东方幻想概念设计板。背景为纯净深墨黑，整体清楚、克制、精密。左侧约占画面 46%，展示同一面卦盘最大的严格 90 度正俯视正交投影主视图；右侧约占画面 54%，用 3 列×2 行六个等大画格展示六段起卦流程；底部保留一条窄区域展示尺寸比例以及阳爻、阴爻两个标准组件。不要生成标题、编号、标签、说明文字、Logo、水印或任何可辨识汉字、英文字母和数字。

星轨六爻盘是一面直径约 28—32 厘米的单层平面悬浮光盘，视觉上近乎无厚度，不做 3D 立体结构，不上下分层，不做玻璃托盘、厚重铜盘、机械罗盘、盾牌或地面法阵。卦面参考方案 D：多重同心星象轨迹、八个均匀方位区、极细暖金刻度、少量星点连线、抽象天干地支式刻痕、浅青色数据微光。所有圆环和纹路处于同一个平面。配色调整为适合栀夏的低饱和月白、浅青和暖金，只保留一枚极小朱砂定位点；不要大面积深蓝霓虹。

圆形几何是最高优先级：左侧主盘必须是严格标准正圆，横向直径与纵向直径完全相等；所有内外同心环必须共享同一圆心并保持标准正圆。右侧第二至第六格出现的卦盘也全部采用严格 90 度正俯视正交投影。不得出现三分之四视角、倾斜视角、透视缩短、横向拉伸、纵向压缩、椭圆或扁圆。

最高优先级结构要求：左侧主卦盘中心必须只有、并且恰好只有六个横向空爻槽。六个空槽等宽、等距、上下对齐、低亮度、尚未填入任何阴阳爻。不得出现第七条槽；不得出现五条或七条；不得把六个空槽画成六条完整发光横线；不得在主视图预先显示固定卦象。请在生成前先数清楚，从下到上总数必须为 6。

底部组件区只展示两种标准爻线：阳爻是一条完整连续的发光横线；阴爻是左右两段等长发光横线，中间有清楚断口。两个组件总宽度、线宽、端点形状和光效一致。只出现一个阳爻样例和一个阴爻样例，不出现第三种样例，不附文字标签。

右侧六个画格严格使用同一面卦盘、同一轮廓、同一星轨、同一配色、同一组六个空槽，依次展示：
第一格，星点聚拢：只有少量浅青星点与淡墨光粒聚集，卦盘尚未完整出现。
第二格，星轨显现：外圈与同心星轨从无到有闭合，六个空爻槽刚刚显现，仍未填充。
第三格，能量汇聚：少量浅青数据微光由外环向盘心汇聚，卦盘结构完整，六个空槽仍清楚可见。
第四格，六爻生成：固定展示生成到第三爻的中间状态。最下面第一槽填入完整阳爻，倒数第二槽填入断开阴爻，倒数第三槽填入断开阴爻；上面三个槽继续保持低亮度空槽。第四格不得仍是六槽全空，也不得提前显示完整六爻。
第五格，卦象稳定：同一组“山雷颐”六爻全部稳定，上下卦所在星轨短暂亮起，周边光效减弱。
第六格，余光收束：外围星点和数据微光向内收束，正确六爻继续保留，不让卦盘消失。

光效为月白柔光、浅青星轨微光与极细暖金锁定线；具有东方星象演算气质，但不要蓝紫游戏法阵、强光柱、爆闪、雷电、浓烟、巨大粒子漩涡或电子游戏 HUD。不要人物、手、栀夏、阿砚、古籍、桌面和建筑场景。

最终检查：左侧主视图和右侧第二至第六格的所有卦盘都是横纵直径相等的标准正圆，所有星轨严格同心；左侧主视图恰好六个空爻槽且完全未填充；右侧每一格也只有同样六个槽；第四格仅下三槽填入阳、阴、阴且上三槽保持空白；第五、六格的完整山雷颐自下而上为完整阳爻、断开阴爻、断开阴爻、断开阴爻、断开阴爻、完整阳爻；所有画格中的卦盘必须是同一设计；不得出现椭圆、透视压缩、第七条线、六条固定阳爻、3D 分层、乱码文字、说明文字、Logo 或水印。
```

- [ ] **Step 2: 按道具清单逐项人工验收**

Run: 打开 `assets/props/ai-divination-disk-v01/qa-checklist.md`，逐项检查 16:9 版式、同一平面结构、恰好六个空爻槽、阴阳组件、六段流程、配色和无水印。

Expected: 所有项目通过；若任一状态结构漂移、六爻错误或出现乱码，只提供定向修改提示词，不归档。

- [ ] **Step 3: 用户明确确认后归档原图**

Run: 将用户确认的原始 PNG 原样复制为 `zhixia-feihualing/assets/props/ai-divination-disk-v01/master.png`，不得重编码或调整尺寸；使用 `cmp` 与 `shasum -a 256` 核对复制前后文件一致。

- [ ] **Step 4: 在 inventory 追加 approved 记录**

```csv
ai-divination-disk-v01,prop,AI卦盘,identity-master,assets/props/ai-divination-disk-v01/master.png,approved,ChatGPT web image generation,original AI-assisted asset,16:9；星轨六爻盘唯一母板；单层平面星象轨迹卦面；主视图恰好六个空爻槽；含阴阳爻组件与六段起卦流程
```

- [ ] **Step 5: 运行现有道具测试并提交**

Run: `zsh zhixia-feihualing/tests/test_cyber_divination_prop.sh`

Expected: `cyber divination prop: PASS`

```bash
git add zhixia-feihualing/assets/props/ai-divination-disk-v01/master.png zhixia-feihualing/assets/inventory.csv
git commit -m "归档星轨六爻盘道具母板"
```

### Task 3: 生成并确认栀夏“引弧起盘”动作卡

**Files:**
- Reference: `zhixia-feihualing/assets/characters/栀夏角色卡电影半写实-v02.png`
- Reference: `zhixia-feihualing/assets/characters/栀夏全身比例卡电影半写实-v02.png`
- Reference: `zhixia-feihualing/assets/props/ai-divination-disk-v01/master.png`
- Create after approval: `zhixia-feihualing/assets/characters/栀夏引弧起盘动作卡电影半写实-v01.png`
- Modify after approval: `zhixia-feihualing/assets/inventory.csv`

**Interfaces:**
- Consumes: approved 栀夏身份与服装母板、approved 星轨六爻盘母板。
- Produces: 四格召唤动作母板 `zhixia-summon-divination-disc-action-v01`，供模板视频引用。

- [ ] **Step 1: 在 ChatGPT 中同时附上三张 approved 参考图并使用完整提示词**

```text
请严格参考我上传的栀夏身份卡、栀夏全身比例卡和“星轨六爻盘”道具卡，生成一张 16:9 横版、3列×2行六格的电影级半写实东方幻想动作与起卦效果综合卡。人物必须是同一个栀夏，脸型、五官、黑色高马尾、白花暖金发饰、胸部体态、抹胸上缘高度和服装全部保持一致：月白抹胸、敞开的浅青半透明薄纱大袖衫、浅粉腰带、浅青高腰长裙上缘。不要重新设计人物或服装。

背景为浅暖灰无缝影棚，固定中近景、正面略偏左三分之四机位，完整拍到头部、上半身、左右双手和桌面上方的卦盘空间。四格中的人物大小、机位、光线、发型、服装和表情必须一致；栀夏全程神情平静专注，不微笑、不闭眼、不夸张施法。

动作名为“引弧起盘”，从左到右严格分为四格：
第一格，起势：右手从腰侧抬至胸腰之间，手肘贴近身体，掌心仍偏向侧面；左手自然稳定，不参与动作。
第二格，翻腕：右腕平稳外翻，掌心斜向上；拇指放松，无名指与小指自然微弯，五指全部清楚可见。
第三格，引弧：右手食指与中指自然并拢向前伸出，在桌面上空顺时针划出约四分之三圆的短弧；指尖留下克制的月白浅青光迹，弧线末端只有少量暖金；此格尚未出现完整卦盘。
六格依次对应星点聚拢、星轨显现、能量汇聚、六爻生成、卦象稳定、余光收束。前三格完成起势、翻腕、双指引弧和六个空爻槽显现；第四格固定为下三槽已经填入阳、阴、阴而上三槽仍为空；第五格锁定完整结果；第六格收束余光并保持卦盘稳定。卦盘不接触手掌，不被手托住。

手部必须严格正确：每只手恰好五指，没有多指、少指、融合指、交叉指或粘连手掌；食指与中指只是并拢而不是融合；两只手不互相遮挡。右侧薄纱大袖随抬臂轻微后滑，露出完整手腕和手指，但服装结构不变。左手四格保持同一自然姿势。

不要阿砚，不要古籍，不要桌面剧情道具，不要字幕、标题、格子编号、说明文字、Logo、水印、蓝紫霓虹、强光柱或复杂粒子。四格之间只用细窄浅灰分隔线。重点是角色一致、手势清楚、动作连续、卦盘身份准确。
```

- [ ] **Step 2: 人工检查人物、双手与动作连续性**

Expected: 四格人物身份一致；右手各五指正确；左手稳定；动作从起势到起盘连续；只有第四格出现完整的未起卦卦盘。

- [ ] **Step 3: 用户明确确认后原样归档并登记**

```csv
zhixia-summon-divination-disc-action-v01,character,栀夏,summoning-action-master,assets/characters/栀夏引弧起盘动作卡电影半写实-v01.png,approved,ChatGPT web image generation,original AI-assisted asset,16:9六格动作效果综合卡；引弧起盘与六段流程统一；严格引用栀夏v02与星轨六爻盘母板；模板视频唯一动作依据
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
- Consumes: approved 栀夏身份卡、动作卡和星轨六爻盘道具卡。
- Produces: 无对白、无具体卦象的 3 秒动作模板，末帧供所有单集衔接六爻生成。

- [ ] **Step 1: 付费生成前向用户展示调用计划并获得确认**

Expected: 用户明确确认生成平台、调用次数和预计成本后才调用；若用户自行在网页生成，则跳过 API 调用，只交付提示词。

- [ ] **Step 2: 使用三张 approved 参考图和完整视频提示词**

```text
生成一段 9:16 竖屏、3 秒、单镜头、电影级半写实东方幻想人物动作模板视频。严格绑定参考图中的栀夏身份、服装和“引弧起盘”六格综合动作，严格绑定参考图中的“星轨六爻盘”外观。浅暖灰无缝影棚背景，固定中近景静止机位，完整拍到栀夏头部、上半身、左右双手和她前方的卦盘空间。镜头不推拉、不摇移、不环绕、不切换。

时间必须清楚：0.0—0.3 秒，栀夏右手起势，少量星点在双指附近聚拢；0.3—0.8 秒，右腕外翻并以并拢双指引弧，卦盘星轨沿弧线显现；0.8—1.3 秒，双指轻挑，同一面单层平面星轨六爻盘悬浮展开，中心恰好六个空爻槽；1.3—2.1 秒，六爻由后期透明卡自下而上填充；2.1—2.5 秒，卦象与星轨稳定；2.5—3.0 秒，外围余光收束，人物和卦盘稳定停留。

视频模型只生成六个空爻槽、人物动作和通用星轨光效，不负责生成具体阴阳爻、卦名、卦辞、汉字或数字；准确结果由后期透明卡覆盖。卦盘不接触手掌，不跟随手掌漂移。栀夏神情平静专注，不微笑、不闭眼；左手全程保持自然稳定；每只手恰好五指，食指与中指只并拢不融合。浅青薄纱大袖随抬臂产生轻微真实布料运动，发型、发饰、抹胸、腰带和身体比例不改变。

无对白、无口型表演、无字幕、无标题、无Logo、无水印、无阿砚、无古籍、无桌面道具、无蓝紫霓虹、无强光柱、无爆闪、无雷电、无烟雾漩涡、无镜头运动、无多指、无手部变形、无人物身份漂移、无卦盘结构漂移。允许极轻衣袖声、单次墨滴声和短促数字脉冲，不生成可辨识人声。最后至少 0.5 秒必须是稳定静止的可衔接末帧。
```

- [ ] **Step 3: 抽帧验收动作连续性与末帧**

Run: 抽检 0.0、0.5、0.8、1.1、1.8、2.3、2.9 秒。

Expected: 栀夏身份与五指稳定；动作和六段效果顺序正确；1.3 秒后星轨盘中心恰好六个空爻槽；具体阴阳爻仅来自后期覆盖；2.5—3.0 秒卦盘稳定；无文字。

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
