# 《飞袂绿腰》15 秒 Seedance 提示词 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立《栀夏·敦煌十六舞》第七支《飞袂绿腰》的单集说明、可直接提交 Seedance 2.0 的 15 秒正式提示词、自动门禁和跨集舞蹈去重记录。

**Architecture:** 单集 README 保存诗文、唯一上传图、视线情绪、固定服装、三高潮和原片验收重点；单一 Markdown 提示词保存上传说明与纯正向模型正文；zsh 门禁检查第一帧完整全身、三次高潮、人物占比、腰部承重、空手、飘带连接、三类环境反馈和诚实命名边界。舞蹈台账追加一条 25 列记录，使后续敦煌舞能够读取本集视觉指纹并避开重复。

**Tech Stack:** Markdown、zsh、ripgrep、awk、CSV

## Global Constraints

- 系列编号固定为《栀夏·敦煌十六舞》07，工作标题固定为《飞袂绿腰》。
- 唯一上传图为 `assets/characters/栀夏敦煌十六舞角色母板-v03-单张大脸锁定-Seedance上传版.jpg`。
- 视频固定为 15 秒、9:16、一镜到底、电影级高写实东方 CG，只有栀夏，无阿砚和其他人物。
- 四句固定为“南国有佳人，轻盈绿腰舞。华筵九秋暮，飞袂拂云雨。”；朗诵与字幕留给后期。
- 本集定位为原创敦煌绿腰舞意象，不宣称唐代舞谱、莫高窟第 445 窟具体舞姿或历史现场复原。
- 第一帧完整显示头顶至鞋履，0.300 秒内明确换重，1.000 秒内进入腿、胸腰和双臂共同发力的主体舞句；本集不连续复用第六支的局部特写开场。
- 三次高潮固定为兰苕侧折、游龙回腰、飞袂凌云；时间窗为 0.000—1.800、4.800—7.000、10.000—13.200 秒。
- 三次环境反馈固定为秋叶窄幅上扬、左右帷幔横向起伏、后方帷幔与流苏向斜前方掠动。
- 第一、第二、第三高潮人物高度分别约 68%—72%、68%—73%、70%—74%；10 秒后镜头不后撤，结尾人物不低于 65%。
- 栀夏双手始终空着；全片零完整旋转、零持续跑步、零飞行、零悬浮、零手持器物。
- “绿腰”是舞名，保持 v03 固定孔雀蓝、琥珀橙、象牙白与旧金服化道，不换绿色新衣。
- 蓝橙双层飘带固定连接在左右上臂后外侧，保持与 v03 母板一致的面部、妆发、配饰和鞋履。
- 原片不生成可辨识人声、诗句、字幕或标题；正式模型正文采用纯正向可观察表达，内部路径、版本、验收与禁止项留在代码块外。
- 生成阶段配乐使用清亮琵琶、拍板和小鼓；朗诵后期加入并保持背景音乐原音量，不做自动闪避或整体压低。
- 本计划不提前生成朗诵、字幕、高清成片、封面或发布文案。

---

### Task 1: 建立失败门禁

**Files:**
- Create: `zhixia-feihualing/tests/test_feimei_lvyao_15s_prompt.sh`

**Interfaces:**
- Consumes: `docs/superpowers/specs/2026-08-31-feimei-lvyao-15s-dance-design.md` 的已确认约束。
- Produces: 在单集说明、正式提示词或去重台账缺失时失败的可执行门禁。

- [ ] **Step 1: 写入测试脚本**

创建以下完整 zsh 门禁：

```zsh
#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
readme="$project_dir/episodes/feimei-lvyao-15s/README.md"
prompt="$project_dir/episodes/feimei-lvyao-15s/prompts/seedance-v01.md"
history_file="$project_dir/operations/dance-design-history.csv"

for required in "$readme" "$prompt" "$history_file"; do
  [[ -s "$required" ]] || { print -u2 -r -- "FAIL: missing required Feimei Lvyao component $required"; exit 1; }
done

for required_text in \
  '参考上传图片中的栀夏' \
  '第一帧完整显示栀夏从头顶到鞋履' \
  '0.000—1.800秒，兰苕侧折' \
  '4.800—7.000秒，游龙回腰' \
  '10.000—13.200秒，飞袂凌云' \
  '深侧弓步' \
  '斜向S形交叉步' \
  '剪步腾跃' \
  '左右上臂后外侧' \
  '秋叶形成窄幅向上弧线' \
  '左右青绿色帷幔依次横向起伏' \
  '后方帷幔下缘与旧金流苏向斜前方掠动' \
  '沿原轴迎面短促推近' \
  '13.200—15.000秒' \
  '清亮琵琶、拍板和小鼓'; do
  rg -qF "$required_text" "$prompt" || { print -u2 -r -- "FAIL: prompt lacks $required_text"; exit 1; }
done

rg -qF '<!-- SEEDANCE_PROMPT_START -->' "$prompt" || { print -u2 "FAIL: prompt start marker missing"; exit 1; }
rg -qF '<!-- SEEDANCE_PROMPT_END -->' "$prompt" || { print -u2 "FAIL: prompt end marker missing"; exit 1; }

for required_text in \
  '南国有佳人' \
  '飞袂拂云雨' \
  '原创敦煌绿腰舞意象' \
  '“绿腰”是舞名' \
  '第一帧完整全身强起势' \
  '约 68%—72%' \
  '约 68%—73%' \
  '约 70%—74%' \
  '保持背景音乐原音量'; do
  rg -qF "$required_text" "$readme" || { print -u2 -r -- "FAIL: README lacks $required_text"; exit 1; }
done

for forbidden_claim in '唐代舞谱复原' '莫高窟第 445 窟舞姿复原' 'AI活化文物' '数字敦煌复原' '某窟原舞复原'; do
  ! rg -qF "$forbidden_claim" "$readme" || { print -u2 -r -- "FAIL: README contains misleading claim $forbidden_claim"; exit 1; }
done

awk -F, 'NF != 25 { print NR ":" NF; bad=1 } END { exit bad }' "$history_file"
[[ "$(rg -c '^feimei-lvyao-15s,' "$history_file")" == "1" ]] || { print -u2 "FAIL: Feimei Lvyao history row is missing or duplicated"; exit 1; }
[[ "$(awk -F, '$1=="feimei-lvyao-15s" {print $19}' "$history_file")" == "designed" ]] || { print -u2 "FAIL: Feimei Lvyao history status must be designed"; exit 1; }

prompt_body="$(sed -n '/SEEDANCE_PROMPT_START/,/SEEDANCE_PROMPT_END/p' "$prompt")"
for forbidden in '基础级' '视觉指纹' 'v03' '文件名' '历史复原' '文物复原' '图片2' '真实人物' '艺人' '18岁' '第445窟'; do
  [[ "$prompt_body" != *"$forbidden"* ]] || { print -u2 -r -- "FAIL: prompt body contains forbidden token $forbidden"; exit 1; }
done

for negative_expression in '只有一个' '没有其他人物' '不得' '禁止' '不生成' '不要' '不拿' '不抓' '不出现' '无阿砚'; do
  [[ "$prompt_body" != *"$negative_expression"* ]] || { print -u2 -r -- "FAIL: positive prompt body contains negative expression $negative_expression"; exit 1; }
done

print -r -- "PASS: Feimei Lvyao 15s prompt and history are complete"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `zsh tests/test_feimei_lvyao_15s_prompt.sh`

Expected: FAIL，首先报告缺少《飞袂绿腰》README 或正式提示词，而不是 zsh 语法错误。

- [ ] **Step 3: 提交门禁**

```zsh
git add tests/test_feimei_lvyao_15s_prompt.sh
git commit -m "建立飞袂绿腰提示词门禁"
```

### Task 2: 写入单集说明和 Seedance 正式提示词

**Files:**
- Create: `zhixia-feihualing/episodes/feimei-lvyao-15s/README.md`
- Create: `zhixia-feihualing/episodes/feimei-lvyao-15s/prompts/seedance-v01.md`

**Interfaces:**
- Consumes: 已确认设计中的诗文、角色、场景、视线情绪、固定服装、三高潮、摄影机、声音和生成边界。
- Produces: 项目可追溯的单集说明，以及用户可直接复制提交的完整 Seedance 提示词。

- [ ] **Step 1: 写入 README**

README 使用以下固定内容：

```markdown
# 《飞袂绿腰》15 秒敦煌舞

## 单集定位

- 系列：《栀夏·敦煌十六舞》07。
- 舞蹈：原创敦煌绿腰舞意象，不复刻具体壁画姿态或历史舞谱。
- 规格：15 秒、9:16 竖屏、一镜到底、三次同等强度高潮。
- 状态：正式提示词已完成，等待生成原片。

## 诗文

唐·李群玉《长沙九日登东楼观舞》开篇四句：

> 南国有佳人，轻盈绿腰舞。
>
> 华筵九秋暮，飞袂拂云雨。

## 唯一上传图

只上传 `assets/characters/栀夏敦煌十六舞角色母板-v03-单张大脸锁定-Seedance上传版.jpg`。

## 视线与情绪

- 视线对象依次为高低袖线、斜向 S 形行进方向和舞台前上方袖端。
- 表情从凝神轻盈转为明亮克制，最后保持飞袂余势中的专注。
- 全片不直视镜头，不露齿甜笑，不眨眼互动，不做服装展示式摆拍。

## 固定服装说明

- “绿腰”是舞名，不是服装颜色指令。
- 保持 v03 固定孔雀蓝、琥珀橙、象牙白与旧金服化道，不换绿色新衣。
- 蓝橙双层飘带根部固定连接在左右上臂后外侧，双手始终空置。

## 开场与三次高潮

本集恢复第一帧完整全身强起势，不连续复用上一支的局部特写。

| 时间 | 动作 | 环境反馈 | 镜头反馈 | 人物高度 |
| --- | --- | --- | --- | --- |
| 0.000—1.800 秒 | 兰苕侧折：深侧弓 C 形折腰后纵向回弹 | 秋叶窄幅上扬后回落 | 短促推近并轻微抬升 | 约 68%—72% |
| 4.800—7.000 秒 | 游龙回腰：斜向 S 形交叉步后压宽侧弓急停 | 左右帷幔依次横向起伏 | 有限横移并保持近距离 | 约 68%—73% |
| 10.000—13.200 秒 | 飞袂凌云：剪步腾跃落深弓并斜后展腰 | 后方帷幔与流苏向斜前方掠动 | 沿原轴迎面短促推近 | 约 70%—74% |

13.200—15.000 秒继续反向换重和非对称袖线变化，结尾人物不低于 65%，并在动作余势中切断画面。

## 生成边界

- 全片为栀夏单人主体，固定 v03 面部、妆发、服装、配饰与鞋履。
- 腰部动作由脚下承重、胯部换重与胸腰共同驱动，保持真实脊柱和肌肉发力。
- 全片零完整旋转、零持续跑步、零飞行、零悬浮、零手持器物。
- 原片只生成清亮琵琶、拍板、小鼓、衣料、脚步和华筵前庭环境声，不生成可辨识人声、诗句、字幕或标题。
- 本片对外使用“原创敦煌绿腰舞意象”或“原创敦煌乐舞意象”，不使用复原、活化文物或官方数字敦煌表述。
- 后期加入朗诵时保持背景音乐原音量，不做自动闪避或整体压低。

## 原片验收重点

1. 第一帧头顶至鞋履完整可见，0.300 秒内明确换重，1.000 秒内腿、胸腰和双臂共同发力。
2. 三次高潮分别落在 0.000—1.800、4.800—7.000、10.000—13.200 秒，强度相当，方向、腿部剪影和袖线不同。
3. 腰部保持真实承重，无折断、蛇形软体、肢体拉长、脚底滑行或无重力漂移。
4. 第三高潮人物约占画面 70%—74%，10 秒后镜头不后撤、不突然升高、不拉成远景。
5. 秋叶、左右帷幔、后方帷幔与流苏分别形成纵向、横向和斜前纵深反馈。
6. 栀夏面部、冠饰、固定服装、人体结构、脚底接触和上臂飘带连接稳定，双手始终空置。
```

- [ ] **Step 2: 写入上传说明**

在正式提示词代码块之前明确写入：

```markdown
## 使用方式

- 只上传图片 1：`assets/characters/栀夏敦煌十六舞角色母板-v03-单张大脸锁定-Seedance上传版.jpg`。
- 不上传动作照片、场景图、道具卡、其他人物图或旧版角色卡。
- 复制下方标记之间的正文提交 Seedance。
- 四句诗朗诵、竖排字幕、高清处理、封面和发布文案在原始舞蹈视频通过后分别制作。
```

- [ ] **Step 3: 写入纯正向模型正文**

正文放在 `<!-- SEEDANCE_PROMPT_START -->` 和 `<!-- SEEDANCE_PROMPT_END -->` 之间，使用以下完整内容：

```text
生成15秒、9:16竖屏、一镜到底的电影级高写实东方舞蹈短片。原创虚构角色栀夏是全片持续可见的单人主体，参考上传图片中的栀夏，保持同一张脸、双环敦煌高髻、莲焰旧金冠、朱砂莲瓣花钿、孔雀蓝与琥珀橙织锦舞衣、象牙白内裙、浅青玉配饰和舞履。蓝橙双层飘带全程稳定连接在左右上臂后外侧，双手保持舒展自然掌与清楚空置状态。

场景是九秋暮色中的敦煌华筵前庭。赭石建筑与低矮台基围合磨损石面，左右青绿色半透明帷幔和少量旧金流苏建立纵深，暖金灯火与冷青暮色形成稳定冷暖层次。少量真实秋叶从第一帧起分布在左前方石面和帷幔边缘。栀夏的固定孔雀蓝、琥珀橙、象牙白与旧金舞服贯穿全片，空间、灯光、服装和人物身份连续一致。

0.000—1.800秒，兰苕侧折：第一帧完整显示栀夏从头顶到鞋履。栀夏处于三分之四正面的深侧弓步，承重腿清楚屈曲，另一腿侧向延伸，胸腰形成大幅C形侧倾；一臂越过头顶形成高弧，另一臂贴近地面蓄势。0.300秒内完成清楚换重，低袖贴地反扫，随后由深低位强力回弹至高低错层的大开幅。脚、膝、胯、胸腰和双臂共同发力，秋叶形成窄幅向上弧线并回落到身体侧后方。摄影机沿侧腰回弹方向短促推近并轻微抬升，人物高度约占画面68%—72%。

1.800—4.800秒：栀夏以两步小范围交叉步连接，腰身完成一次收回和反向预拧，双袖保持一前一后错层。视线由低袖线转向斜向行进方向，脚下承重与鞋履持续清楚。

4.800—7.000秒，游龙回腰：栀夏完成三步斜向S形交叉步，脚下路线依次改变左右方向，胸腰连续完成拧转、侧倾和回送。两次方向相反的四分之一改面连接动作，双袖分别从身体前侧和后侧形成反向双S长线。最后一步压入横向宽侧弓，腰身与袖线同时反向急停。左右青绿色帷幔依次横向起伏，摄影机随S形路线有限横移并保持近距离，人物高度约占画面68%—73%。

7.000—10.000秒：栀夏完成一次反向换重和一次低位掠袖，把横向侧弓收为斜前腾跃蓄势。视线转向舞台前上方袖端，胸腰收拢，承重脚稳定蹬地，人物持续保持完整全身。

10.000—13.200秒，飞袂凌云：栀夏使用三步斜前舞步接一次剪步腾跃，腾跃由清楚蹬地形成高而短的离地弧线。落地立即进入前低后高的深弓步，前腿深屈承重，后腿长伸，胸腰向斜后方大幅展开。一袖冲向前上方，一袖拖向后下方，身体、双袖和蓝橙飘带形成前后错层的最长纵深线。后方帷幔下缘与旧金流苏向斜前方掠动，摄影机沿原轴迎面短促推近，人物高度约占画面70%—74%，第三次动作、衣料、环境和镜头反馈与前两次同等强烈。

13.200—15.000秒：栀夏落地后继续反向换重，双臂形成一次新的非对称袖线，目光跟随前上方袖端。蓝橙飘带保留前后错层余势，人物保持完整全身且高度高于画面65%，在持续舞势中结束。

人物视线依次落在高低袖线、斜向S形行进方向和舞台前上方袖端；情绪从凝神轻盈转为明亮克制，最后保持飞袂余势中的专注。摄影机沿侧前略低中全景的小范围伴随主路径运动，三次高潮分别形成侧向折腰回弹、S路线拧腰急停和斜前腾跃落地展腰，空间方向、腿部剪影、袖线和结束方向清楚不同。

声音使用清亮琵琶、拍板和小鼓构成华筵软舞节奏，三次高潮各有一次同等强度音乐重音；衣料声、脚步声、秋叶声和前庭空间回响保持自然清晰。画面保持真实人体承重、真实脊柱与肌肉发力、真实布料重量、真实石材、真实秋叶、统一暮色方向、稳定人物身份和纯净电影构图。
```

模型正文只保留正向可观察结果。内部资产路径、母板版本、设计分类、生产状态、回退条件、历史边界与负面清单全部留在代码块外。

- [ ] **Step 4: 运行测试确认失败点前移到台账**

Run: `zsh tests/test_feimei_lvyao_15s_prompt.sh`

Expected: README 和提示词检查通过，只因缺少 `feimei-lvyao-15s` 台账行而失败。

### Task 3: 登记去重台账并完成验收

**Files:**
- Modify: `zhixia-feihualing/operations/dance-design-history.csv`

**Interfaces:**
- Consumes: Task 2 的最终开场、动作、环境反馈、视线和摄影机设计。
- Produces: 一条完整 25 列、状态为 `designed` 的第七支视觉指纹记录。

- [ ] **Step 1: 追加唯一台账行**

追加以下完整 25 列记录：

```csv
feimei-lvyao-15s,李群玉《长沙九日登东楼观舞》,深侧弓步C形折腰高低袖蓄势,两步交叉连接转斜向S形三步再斜前三步剪步腾跃,三高潮绿腰软舞序列,零完整旋转；两次反向四分之一改面,深侧弓回弹；宽侧弓急停；剪步腾跃落深弓,三分之四正面深侧弓C形折腰,高低反向侧弧；前后双S；前上后下纵深长线,侧弓承重；S形交叉步压宽侧弓；剪步腾跃落前后深弓,蓝橙双层飘带与青绿帷幔,高低错层弧；反向双S；前后纵深线,秋叶、帷幔与旧金流苏,秋叶窄幅上扬；左右帷幔横向起伏；后方帷幔流苏斜前掠动,0.000—1.800秒；4.800—7.000秒；10.000—13.200秒,侧前略低中全景小范围伴随,短促推近轻抬；有限横移；沿原轴迎面短推,反向换重与非对称袖线余势中切断,designed,敦煌十六舞07；仅上传栀夏v03；全身强起势；固定服装不换绿衣；不直视镜头；徒手绿腰舞意象；后期朗诵不压低音乐,兰苕侧折；游龙回腰；飞袂凌云,侧向；左右S形；斜前纵深,0.000—1.800秒；4.800—7.000秒；10.000—13.200秒,秋叶向上弧；左右帷幔横向波；后方帷幔流苏斜前线,短促推近轻抬；有限横移；沿原轴迎面短推
```

- [ ] **Step 2: 运行完整门禁**

Run: `zsh tests/test_feimei_lvyao_15s_prompt.sh`

Expected: PASS，输出 `PASS: Feimei Lvyao 15s prompt and history are complete`。

- [ ] **Step 3: 执行最终验证**

Run:

```zsh
zsh tests/test_feimei_lvyao_15s_prompt.sh
git diff --check -- episodes/feimei-lvyao-15s tests/test_feimei_lvyao_15s_prompt.sh operations/dance-design-history.csv
awk -F, 'NF != 25 {print NR ":" NF; bad=1} END {exit bad}' operations/dance-design-history.csv
test "$(rg -c '^feimei-lvyao-15s,' operations/dance-design-history.csv)" = "1"
```

Expected: 门禁输出 PASS；目标文件无空白错误；台账全部 25 列；`feimei-lvyao-15s` 恰有一条记录。

- [ ] **Step 4: 提交单集与台账**

```zsh
git add episodes/feimei-lvyao-15s/README.md episodes/feimei-lvyao-15s/prompts/seedance-v01.md operations/dance-design-history.csv
git commit -m "制作敦煌飞袂绿腰视频提示词"
```

若舞蹈台账同时包含其他用户未提交改动，只暂存本次新增的 `feimei-lvyao-15s` 行并单独提交；不暂存角色母板、资产清单、其他计划、其他单集文件或其他工作区修改。
