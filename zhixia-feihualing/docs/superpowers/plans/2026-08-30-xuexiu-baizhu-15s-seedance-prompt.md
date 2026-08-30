# 《雪袖白纻》15 秒 Seedance 提示词 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立《栀夏·敦煌十六舞》第五支《雪袖白纻》的单集说明、可直接提交 Seedance 2.0 的 15 秒正式提示词、自动门禁和跨集舞蹈去重记录。

**Architecture:** 单集 README 保存诗文、唯一上传图和验收重点；单一 Markdown 提示词保存上传说明与纯正向模型正文；zsh 门禁检查三高潮、人物占比、空手、飘带连接、长影方向及敏感表达边界。舞蹈台账追加一条 25 列记录，使后续敦煌舞能够读取本集视觉指纹并避开重复。

**Tech Stack:** Markdown、zsh、ripgrep、awk、CSV

## Global Constraints

- 系列编号固定为《栀夏·敦煌十六舞》05，工作标题固定为《雪袖白纻》。
- 唯一上传图为 `assets/characters/栀夏敦煌十六舞角色母板-v03-单张大脸锁定-Seedance上传版.jpg`。
- 视频固定为 15 秒、9:16、一镜到底、电影级高写实东方 CG，只有栀夏，无阿砚和其他人物。
- 四句固定为“吴刀剪彩缝舞衣，明妆丽服夺春晖。扬眉转袖若雪飞，倾城独立世所稀。”；朗诵与字幕留给后期。
- 栀夏双手始终空着，不增加白布、手绢、团扇、琵琶、鼓、剑或花枝。
- 三次高潮固定为纵向掩袖冲顶、横向双袖交剪、纵深折腰再独立；时间窗为 0.000—1.800、4.800—7.000、10.000—13.200 秒。
- 唯一环境反馈为真实长影，三次分别沿立柱向上、横扫左右壁面、沿舞坪由远及近运动。
- 全程保持地面舞，不腾空、不飞行、不连续旋转；不增加飞沙、花瓣、飘雪、粒子或第二种主要特效。
- 第一、第二、第三高潮人物高度分别约 68%—72%、66%—71%、68%—73%；13—15 秒不得低于约 60%。
- 第三高潮镜头保持或微推，禁止后撤；蓝橙双层飘带固定在左右上臂后外侧。
- 原片无人声、无诗句、无字幕、无标题、无水印；正式模型正文采用纯正向表达，禁用容易触发审核的否定式长清单。
- 朗诵后期不得压低或闪避原片背景音乐，本计划不提前生成朗诵和字幕。

---

### Task 1: 建立失败门禁

**Files:**
- Create: `zhixia-feihualing/tests/test_xuexiu_baizhu_15s_prompt.sh`

**Interfaces:**
- Consumes: `docs/superpowers/specs/2026-08-30-xuexiu-baizhu-15s-dance-design.md` 的已确认约束。
- Produces: 在单集说明、正式提示词或台账记录缺失时失败的可执行门禁。

- [ ] **Step 1: 写入测试脚本**

创建以下完整 zsh 门禁：

```zsh
#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
readme="$project_dir/episodes/xuexiu-baizhu-15s/README.md"
prompt="$project_dir/episodes/xuexiu-baizhu-15s/prompts/seedance-v01.md"
history_file="$project_dir/operations/dance-design-history.csv"

for required in "$readme" "$prompt" "$history_file"; do
  [[ -s "$required" ]] || { print -u2 -r -- "FAIL: missing required Xuexiu Baizhu component $required"; exit 1; }
done

for required_text in \
  '参考上传图片中的栀夏' \
  '三次高能舞姿同等强烈' \
  '0.000—1.800秒' \
  '4.800—7.000秒' \
  '10.000—13.200秒' \
  '纵向掩袖冲顶' \
  '横向双袖交剪' \
  '纵深折腰再独立' \
  '沿立柱向上拔高' \
  '横扫左右壁面' \
  '沿舞坪由远及近' \
  '左右上臂后外侧' \
  '第三段保持近距离并短促微推' \
  '13.200—15.000秒' \
  '无人声敦煌乐舞配乐'; do
  rg -qF "$required_text" "$prompt" || { print -u2 -r -- "FAIL: prompt lacks $required_text"; exit 1; }
done

rg -qF '<!-- SEEDANCE_PROMPT_START -->' "$prompt" || { print -u2 "FAIL: prompt start marker missing"; exit 1; }
rg -qF '<!-- SEEDANCE_PROMPT_END -->' "$prompt" || { print -u2 "FAIL: prompt end marker missing"; exit 1; }
rg -qF '吴刀剪彩缝舞衣' "$readme" || { print -u2 "FAIL: README lacks opening poem line"; exit 1; }
rg -qF '倾城独立世所稀' "$readme" || { print -u2 "FAIL: README lacks final poem line"; exit 1; }
rg -qF '68%—72%' "$readme" || { print -u2 "FAIL: README lacks first peak scale"; exit 1; }
rg -qF '66%—71%' "$readme" || { print -u2 "FAIL: README lacks second peak scale"; exit 1; }
rg -qF '68%—73%' "$readme" || { print -u2 "FAIL: README lacks third peak scale"; exit 1; }
rg -qF '13—15 秒不得低于约 60%' "$readme" || { print -u2 "FAIL: README lacks ending scale"; exit 1; }

awk -F, 'NF != 25 { print NR ":" NF; bad=1 } END { exit bad }' "$history_file"
[[ "$(rg -c '^xuexiu-baizhu-15s,' "$history_file")" == "1" ]] || { print -u2 "FAIL: Xuexiu Baizhu history row is missing or duplicated"; exit 1; }
[[ "$(awk -F, '$1=="xuexiu-baizhu-15s" {print $19}' "$history_file")" == "designed" ]] || { print -u2 "FAIL: Xuexiu Baizhu history status must be designed"; exit 1; }

prompt_body="$(sed -n '/SEEDANCE_PROMPT_START/,/SEEDANCE_PROMPT_END/p' "$prompt")"
for forbidden in '基础级' '视觉指纹' 'v03' '文件名' '历史复原' '图片2' '真实人物' '艺人' '18岁'; do
  [[ "$prompt_body" != *"$forbidden"* ]] || { print -u2 -r -- "FAIL: prompt body contains forbidden token $forbidden"; exit 1; }
done

for negative_expression in '只有一个' '没有其他人物' '不得' '禁止' '不生成' '不要' '不拿' '不抓' '不出现' '无阿砚'; do
  [[ "$prompt_body" != *"$negative_expression"* ]] || { print -u2 -r -- "FAIL: positive prompt body contains negative expression $negative_expression"; exit 1; }
done

print -r -- "PASS: Xuexiu Baizhu 15s prompt and history are complete"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `zsh tests/test_xuexiu_baizhu_15s_prompt.sh`

Expected: FAIL，首先报告缺少《雪袖白纻》README 或正式提示词，而不是 zsh 语法错误。

- [ ] **Step 3: 提交门禁**

```zsh
git add tests/test_xuexiu_baizhu_15s_prompt.sh
git commit -m "建立雪袖白纻提示词门禁"
```

### Task 2: 写入单集说明和 Seedance 正式提示词

**Files:**
- Create: `zhixia-feihualing/episodes/xuexiu-baizhu-15s/README.md`
- Create: `zhixia-feihualing/episodes/xuexiu-baizhu-15s/prompts/seedance-v01.md`

**Interfaces:**
- Consumes: 已确认设计中的角色、场景、动作、摄影机、声音、人物占比和生成边界。
- Produces: 项目可追溯的单集说明，以及用户可直接复制提交的完整 Seedance 提示词。

- [ ] **Step 1: 写入 README**

README 使用以下固定结构和状态：

```markdown
# 《雪袖白纻》15 秒敦煌舞

## 单集定位

- 系列：《栀夏·敦煌十六舞》05。
- 舞蹈：敦煌巾舞视觉语汇下的原创白纻长袖舞意象。
- 规格：15 秒、9:16 竖屏、一镜到底、三次同等强度高潮。
- 状态：正式提示词已完成，等待生成原片。

## 诗文

唐·李白《白纻辞三首·其三》：

> 吴刀剪彩缝舞衣，
>
> 明妆丽服夺春晖。
>
> 扬眉转袖若雪飞，
>
> 倾城独立世所稀。

## 唯一上传图

只上传 `assets/characters/栀夏敦煌十六舞角色母板-v03-单张大脸锁定-Seedance上传版.jpg`。

## 三次高潮

| 时间 | 动作 | 影子反馈 | 镜头反馈 | 人物高度 |
| --- | --- | --- | --- | --- |
| 0.000—1.800 秒 | 纵向掩袖冲顶 | 沿立柱向上拔高 | 短促推近并抬升 | 约 68%—72% |
| 4.800—7.000 秒 | 横向双袖交剪 | 横扫左右壁面 | 有限横移并微推 | 约 66%—71% |
| 10.000—13.200 秒 | 纵深折腰再独立 | 沿舞坪由远及近 | 保持或短促微推 | 约 68%—73% |

13—15 秒人物高度不得低于约 60%，结尾在持续舞动中切断。

## 生成边界

- 全片为栀夏单人主体，双手空置，固定 v03 面部、妆发、服装、配饰与鞋履。
- 全程保持地面长袖舞；蓝橙双层飘带根部固定在左右上臂后外侧。
- 真实长影是唯一环境反馈，画面维持同一座敦煌壁画舞殿。
- 原片使用无人声敦煌乐舞配乐，无朗诵、字幕、标题和水印。
- 正式模型正文采用纯正向表达；四句朗诵与字幕在原片通过后制作，背景音乐保持原音量。

## 原片验收重点

1. 第一帧是低位交叉沉身与脸下半开袖门，0.200 秒内开始冲袖拔起。
2. 三次高潮严格落在三个时间窗，分别形成纵向冲顶、横向交剪、纵深深折反提单足独立。
3. 三次长影分别向上、左右、由远及近运动，不产生第二人物。
4. 栀夏面部、妆发、服装、人体结构、脚底接触和上臂飘带连接稳定，双手始终空置。
5. 三个高潮人物高度依次达到约 68%—72%、66%—71%、68%—73%，第三次镜头保持或微推。
6. 13.200—15.000 秒继续落脚、换重、回正和双臂展开，人物高度保持约 60% 以上。
```

- [ ] **Step 2: 写入上传说明**

在正式提示词代码块之前明确写入：

```markdown
## 使用方式

- 只上传图片 1：`assets/characters/栀夏敦煌十六舞角色母板-v03-单张大脸锁定-Seedance上传版.jpg`。
- 不上传动作照片、白布图、道具卡、场景图、其他人物图或旧版角色卡。
- 复制下方标记之间的正文提交 Seedance。
- 四句诗朗诵与字幕在原始舞蹈视频通过后另行加入，届时不压低背景音乐。
```

- [ ] **Step 3: 写入纯正向模型正文**

正文放在 `<!-- SEEDANCE_PROMPT_START -->` 和 `<!-- SEEDANCE_PROMPT_END -->` 之间，只使用正向描述，按以下六段组织：

```text
0.000—1.800秒：第一帧低位交叉沉身，脸下半开袖门，立即蹬地打开胸腰，完成纵向掩袖冲顶；人物约占画面68%—72%，长影沿立柱向上拔高。

1.800—4.800秒：落臂穿袖、前后换重、两步交叉踏步完成四分之一转面，飘带回落到身体左右。

4.800—7.000秒：宽幅侧弓压低，手臂在胸前交叉后反向爆发打开，完成横向双袖交剪；人物约占画面66%—71%，长影横扫左右壁面。

7.000—10.000秒：回袖、反向换重、半跪式低位折腰，前后错层蓄势。

10.000—13.200秒：斜前接近，先深折腰，再反向拔起到单足独立，完成纵深折腰再独立；人物约占画面68%—73%，长影沿舞坪由远及近。

13.200—15.000秒：落脚、反向换重、躯干回正、双臂再展开，人物约占画面60%以上，在未完成舞势中结束。
```

正文开头正向声明：15 秒、9:16、一镜到底、原创虚构角色栀夏单人主体、双手自然空置、人物造型全程一致、蓝橙双层飘带连接在左右上臂后外侧。正文结尾正向限定固定舞殿、真实长影、近距离摄影机、三次同强度音乐重音、无人声敦煌乐舞配乐和纯净电影画面。内部文件路径、母板版本、设计分类、历史复原措辞和否定式长清单均留在代码块外。

- [ ] **Step 4: 运行测试确认失败点前移到台账**

Run: `zsh tests/test_xuexiu_baizhu_15s_prompt.sh`

Expected: README 和提示词检查通过，只因缺少 `xuexiu-baizhu-15s` 台账行而失败。

### Task 3: 登记去重台账并完成验收

**Files:**
- Modify: `zhixia-feihualing/operations/dance-design-history.csv`

**Interfaces:**
- Consumes: Task 2 的最终动作、影子反馈和摄影机设计。
- Produces: 一条完整 25 列、状态为 `designed` 的第五支视觉指纹记录。

- [ ] **Step 1: 追加唯一台账行**

追加以下完整 25 列记录：

```csv
xuexiu-baizhu-15s,李白《白纻辞三首·其三》,低位交叉沉身脸下半开袖门,交叉踏步转侧弓再斜前折腰提身,三高潮长袖序列,零完整旋转；四分之一转面,低位沉身转纵向拔起；宽幅侧弓；深折腰转单足独立,三分之四正面低位交叉沉身转高低双袖冲顶,脸下半开袖门转高低冲顶；胸前交叉后左右反抽；前低后高纵深大开幅,深屈腿蹬直；宽幅侧弓压低反蹬；前腿深屈后腿长伸转单足独立,蓝橙双层飘带与真实长影,高低冲顶双线；横向交剪双扇；前后错层长线,衣袖与飘带投下的真实长影,立柱向上拔高；左右壁面横扫；舞坪由远及近,0.000—1.800秒；4.800—7.000秒；10.000—13.200秒,侧前略低中全景小范围伴随,短促推近并抬升；有限横移并微推；保持或短促微推,落脚反向换重回正并在双臂再展开中切断,designed,敦煌十六舞05；仅上传栀夏v03；单人空手固定服装；地面舞；三高潮人物68%—72%及66%—71%及68%—73%；13—15秒约60%；不复用沙琵琶旋转飞天莲瓣,纵向掩袖冲顶；横向双袖交剪；纵深折腰再独立,纵向；左右横向；斜前纵深,0.000—1.800秒；4.800—7.000秒；10.000—13.200秒,双带高低冲顶；双带横向交剪；双带前后错层长线,短促推近并抬升；有限横移并微推；保持或短促微推
```

- [ ] **Step 2: 运行完整门禁**

Run: `zsh tests/test_xuexiu_baizhu_15s_prompt.sh`

Expected: PASS，输出 `PASS: Xuexiu Baizhu 15s prompt and history are complete`。

- [ ] **Step 3: 执行最终验证**

Run:

```zsh
zsh tests/test_xuexiu_baizhu_15s_prompt.sh
git diff --check -- episodes/xuexiu-baizhu-15s tests/test_xuexiu_baizhu_15s_prompt.sh operations/dance-design-history.csv
awk -F, 'NF != 25 {print NR ":" NF; bad=1} END {exit bad}' operations/dance-design-history.csv
```

Expected: 测试 PASS、目标文件无空白错误、台账全部 25 列。

- [ ] **Step 4: 提交单集与台账**

```zsh
git add episodes/xuexiu-baizhu-15s/README.md episodes/xuexiu-baizhu-15s/prompts/seedance-v01.md operations/dance-design-history.csv docs/superpowers/plans/2026-08-30-xuexiu-baizhu-15s-seedance-prompt.md
git commit -m "制作敦煌雪袖白纻视频提示词"
```

若舞蹈台账同时包含其他用户未提交改动，只暂存本次新增的 `xuexiu-baizhu-15s` 行并单独提交；不暂存角色母板、资产清单、其他计划或其他单集文件。
