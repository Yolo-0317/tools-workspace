# 《莲台天乐》15 秒 Seedance 提示词 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立《栀夏·敦煌十六舞》第六支《莲台天乐》的单集说明、可直接提交 Seedance 2.0 的 15 秒正式提示词、自动门禁和跨集舞蹈去重记录。

**Architecture:** 单集 README 保存诗文、唯一上传图、视线情绪弧线、局部特写回退条件和原片验收重点；单一 Markdown 提示词保存上传说明与纯正向模型正文；zsh 门禁检查 0.800 秒全身揭示、三次高潮、人物占比、视线对象、空手、飘带连接、香雾三方向和诚实命名边界。舞蹈台账追加一条 25 列记录，使后续敦煌舞能够读取本集视觉指纹并避开重复。

**Tech Stack:** Markdown、zsh、ripgrep、awk、CSV

## Global Constraints

- 系列编号固定为《栀夏·敦煌十六舞》06，工作标题固定为《莲台天乐》。
- 唯一上传图为 `assets/characters/栀夏敦煌十六舞角色母板-v03-单张大脸锁定-Seedance上传版.jpg`。
- 视频固定为 15 秒、9:16、一镜到底、电影级高写实东方 CG，只有栀夏，无阿砚和其他人物。
- 四句固定为“霜清东林钟，水白虎溪月。天香生虚空，天乐鸣不歇。”；朗诵与字幕留给后期。
- 本集定位为原创敦煌供养舞意象，不宣称历史舞谱、洞窟壁画动作或文物复原。
- 开头 0.000—0.500 秒为璎珞与指尖特写，0.800 秒前恢复完整全身，1.000 秒内进入主体舞句；身份、脚下承重或第一高潮受损时回退为第一帧完整全身强起势。
- 视线依次指向近处璎珞与指尖、上方天窗月影、斜前上方天乐来处；不直视镜头，不露齿甜笑，不眨眼互动。
- 三次高潮固定为纵向应钟、横向追月、纵深迎乐；时间窗为 0.800—1.800、4.800—7.000、10.000—13.200 秒。
- 唯一环境承接物为极薄真实香雾，三次分别形成向上窄柱、贴地横向薄带、由近向斜前长线。
- 第一、第二、第三高潮人物高度分别约 70%、68%—72%、约 70%；10 秒后镜头不后撤，13—15 秒保持近距离与舞动余势。
- 栀夏双手始终空着，不合掌，不持莲花、香炉、油灯、钟、箜篌或其他器物；全片零完整旋转、零悬浮、零施法手势。
- 蓝橙双层飘带固定连接在左右上臂后外侧，保持与 v03 母板一致的服装、妆发、配饰和鞋履。
- 原片不生成可辨识人声、诗句、字幕或标题；正式模型正文采用纯正向表达，内部路径、版本、验收与禁止项留在代码块外。
- 朗诵后期继续使用栀夏固定女声；本计划不提前生成朗诵、字幕、高清成片、封面或发布文案。

---

### Task 1: 建立失败门禁

**Files:**
- Create: `zhixia-feihualing/tests/test_liantai_tianyue_15s_prompt.sh`

**Interfaces:**
- Consumes: `docs/superpowers/specs/2026-08-31-liantai-tianyue-15s-dance-design.md` 的已确认约束。
- Produces: 在单集说明、正式提示词或去重台账缺失时失败的可执行门禁。

- [ ] **Step 1: 写入测试脚本**

创建以下完整 zsh 门禁：

```zsh
#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
readme="$project_dir/episodes/liantai-tianyue-15s/README.md"
prompt="$project_dir/episodes/liantai-tianyue-15s/prompts/seedance-v01.md"
history_file="$project_dir/operations/dance-design-history.csv"

for required in "$readme" "$prompt" "$history_file"; do
  [[ -s "$required" ]] || { print -u2 -r -- "FAIL: missing required Liantai Tianyue component $required"; exit 1; }
done

for required_text in \
  '参考上传图片中的栀夏' \
  '0.000—0.500秒' \
  '0.500—0.800秒' \
  '0.800—1.800秒' \
  '4.800—7.000秒' \
  '10.000—13.200秒' \
  '纵向应钟' \
  '横向追月' \
  '纵深迎乐' \
  '向上拔高的窄柱' \
  '贴近地面的横向薄带' \
  '由近向斜前方延伸的长线' \
  '左右上臂后外侧' \
  '沿原轴迎面推近' \
  '13.200—15.000秒' \
  '声音仅包含钟声、箜篌、低沉鼓点、衣料声、脚步声与石窟空间回响'; do
  rg -qF "$required_text" "$prompt" || { print -u2 -r -- "FAIL: prompt lacks $required_text"; exit 1; }
done

rg -qF '<!-- SEEDANCE_PROMPT_START -->' "$prompt" || { print -u2 "FAIL: prompt start marker missing"; exit 1; }
rg -qF '<!-- SEEDANCE_PROMPT_END -->' "$prompt" || { print -u2 "FAIL: prompt end marker missing"; exit 1; }

for required_text in \
  '霜清东林钟' \
  '天乐鸣不歇' \
  '近处璎珞与指尖' \
  '上方天窗月影' \
  '斜前上方不可见的天乐来处' \
  '0.800 秒前恢复完整全身' \
  '回退为第一帧完整全身强起势' \
  '原创敦煌供养舞意象' \
  '约 68%—72%'; do
  rg -qF "$required_text" "$readme" || { print -u2 -r -- "FAIL: README lacks $required_text"; exit 1; }
done

for forbidden_claim in '历史舞谱复原' '壁画舞姿复原' 'AI活化文物' '数字敦煌复原' '某窟原舞复原'; do
  ! rg -qF "$forbidden_claim" "$readme" || { print -u2 -r -- "FAIL: README contains misleading claim $forbidden_claim"; exit 1; }
done

awk -F, 'NF != 25 { print NR ":" NF; bad=1 } END { exit bad }' "$history_file"
[[ "$(rg -c '^liantai-tianyue-15s,' "$history_file")" == "1" ]] || { print -u2 "FAIL: Liantai Tianyue history row is missing or duplicated"; exit 1; }
[[ "$(awk -F, '$1=="liantai-tianyue-15s" {print $19}' "$history_file")" == "designed" ]] || { print -u2 "FAIL: Liantai Tianyue history status must be designed"; exit 1; }

prompt_body="$(sed -n '/SEEDANCE_PROMPT_START/,/SEEDANCE_PROMPT_END/p' "$prompt")"
for forbidden in '基础级' '视觉指纹' 'v03' '文件名' '历史复原' '文物复原' '图片2' '真实人物' '艺人' '18岁'; do
  [[ "$prompt_body" != *"$forbidden"* ]] || { print -u2 -r -- "FAIL: prompt body contains forbidden token $forbidden"; exit 1; }
done

for negative_expression in '只有一个' '没有其他人物' '不得' '禁止' '不生成' '不要' '不拿' '不抓' '不出现' '无阿砚'; do
  [[ "$prompt_body" != *"$negative_expression"* ]] || { print -u2 -r -- "FAIL: positive prompt body contains negative expression $negative_expression"; exit 1; }
done

print -r -- "PASS: Liantai Tianyue 15s prompt and history are complete"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `zsh tests/test_liantai_tianyue_15s_prompt.sh`

Expected: FAIL，首先报告缺少《莲台天乐》README 或正式提示词，而不是 zsh 语法错误。

- [ ] **Step 3: 提交门禁**

```zsh
git add tests/test_liantai_tianyue_15s_prompt.sh
git commit -m "建立莲台天乐提示词门禁"
```

### Task 2: 写入单集说明和 Seedance 正式提示词

**Files:**
- Create: `zhixia-feihualing/episodes/liantai-tianyue-15s/README.md`
- Create: `zhixia-feihualing/episodes/liantai-tianyue-15s/prompts/seedance-v01.md`

**Interfaces:**
- Consumes: 已确认设计中的诗文、角色、场景、视线情绪、局部特写试验、三高潮、摄影机、声音和生成边界。
- Produces: 项目可追溯的单集说明，以及用户可直接复制提交的完整 Seedance 提示词。

- [ ] **Step 1: 写入 README**

README 使用以下固定内容：

```markdown
# 《莲台天乐》15 秒敦煌舞

## 单集定位

- 系列：《栀夏·敦煌十六舞》06。
- 舞蹈：原创敦煌供养舞意象，不复刻具体壁画姿态或历史舞谱。
- 规格：15 秒、9:16 竖屏、一镜到底、三次同等强度高潮。
- 状态：正式提示词已完成，等待生成原片。

## 诗文

唐·李白《庐山东林寺夜怀》：

> 霜清东林钟，水白虎溪月。
>
> 天香生虚空，天乐鸣不歇。

## 唯一上传图

只上传 `assets/characters/栀夏敦煌十六舞角色母板-v03-单张大脸锁定-Seedance上传版.jpg`。

## 视线与情绪

- 视线对象依次为近处璎珞与指尖、上方天窗月影、斜前上方不可见的天乐来处。
- 表情从静心闻钟转为望月时的克制欣悦，最后进入明净庄严。
- 全片不直视镜头，不露齿甜笑，不眨眼互动，不做服装展示式摆拍。

## 局部特写试验

- 0.000—0.500 秒为旧金璎珞、浅青玉珠与自然掌指尖特写。
- 0.500—0.800 秒沿手臂连续后撤，0.800 秒前恢复完整全身，1.000 秒内进入主体舞句。
- 若出现换脸、冠饰突变、服装重组、鞋履不可见、脚下承重不清或第一高潮延迟，回退为第一帧完整全身强起势。

## 三次高潮

| 时间 | 动作 | 香雾反馈 | 镜头反馈 | 人物高度 |
| --- | --- | --- | --- | --- |
| 0.800—1.800 秒 | 纵向应钟：单膝低位骤然提身 | 向上拔高的窄柱 | 完整揭示后轻微抬升 | 约 70% |
| 4.800—7.000 秒 | 横向追月：两次换重后侧倾回弹 | 贴近地面的横向薄带 | 同速横移并短促推近 | 约 68%—72% |
| 10.000—13.200 秒 | 纵深迎乐：斜前三步深沉再提展 | 由近向斜前方延伸的长线 | 沿原轴迎面推近 | 约 70% |

13.200—15.000 秒继续斜向换重，并在双臂和飘带余势中切断画面。

## 生成边界

- 全片为栀夏单人主体，双手空置，固定 v03 面部、妆发、服装、配饰与鞋履。
- 蓝橙双层飘带根部固定连接在左右上臂后外侧。
- 极薄真实香雾是唯一环境承接物；地面莲纹是磨损浅刻，不发光。
- 全片零完整旋转、零悬浮、零施法手势、零手持器物。
- 原片只生成钟声、箜篌、低沉鼓点和自然环境声，不生成可辨识人声、诗句、字幕或标题。
- 本片对外使用“原创敦煌供养舞意象”或“原创敦煌乐舞意象”，不使用复原、活化文物或官方数字敦煌表述。

## 原片验收重点

1. 0.500 秒局部特写结束后连续拉到全身，0.800 秒时头顶至鞋履完整可见。
2. 三次高潮分别落在 0.800—1.800、4.800—7.000、10.000—13.200 秒，强度、人物占比、飘带和镜头响应相当。
3. 三次香雾分别向上、横向贴地、斜前纵深运动，不发光、不环身、不遮挡脸和四肢。
4. 栀夏视线依次对应璎珞与指尖、月影和天乐来处，全片不直视镜头。
5. 栀夏面部、冠饰、服装、人体结构、脚底接触和上臂飘带连接稳定，双手始终空置。
6. 第三高潮人物约占画面 70%，10 秒后镜头不后撤，13—15 秒人物继续运动。
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

场景是深蓝月夜中的石窟莲台前庭。狭长天窗投下真实冷月光柱，赭褐风化石壁带低饱和石绿、朱砂与旧金装饰纹样，磨损的浅刻莲纹铺在石面，两侧少量固定油灯提供暖金辅光。极薄真实香雾是全片唯一环境承接物，空间、月光、油灯、莲纹和石壁保持连续一致。

0.000—0.500秒：第一记钟声响起。旧金璎珞、浅青玉珠与自然掌指尖处于同一动态近景，璎珞轻微颤动，指尖完成一次清楚的整掌方向变化。栀夏视线落向近处璎珞与指尖，表情安静专注。

0.500—0.800秒：摄影机沿手臂连续快速后撤，完整揭示栀夏从头顶、冠饰、正脸、躯干、双腿到鞋履，以及莲纹石面与石窟空间。0.800秒时栀夏处于三分之四正面的单膝低位，躯干向侧前方拧倾，另一腿形成稳定斜线，脚下承重清楚。

0.800—1.800秒，纵向应钟：栀夏由单膝低位骤然蹬地提身，胸腰从收拢转为向上打开，一臂从脸侧安全区上穿，另一臂向斜下方反展，形成高低错落的大弧线。蓝橙飘带延迟扬起，极薄香雾形成向上拔高的窄柱。摄影机在全身揭示后随提身轻微抬升，人物高度约占画面70%，头顶与鞋履完整可见。

1.800—4.800秒：栀夏落脚稳定，视线先转向上方天窗月影，完成一次呼吸、横向预备换重和双臂回落。动作保持连续，服装、冠饰、飘带连接和石窟空间稳定一致。

4.800—7.000秒，横向追月：栀夏沿莲纹石面连续完成两次有力横向换重，身体先向月影方向大幅侧倾，再向相反方向突然回弹；双臂形成上下反向的两道月弧，蓝橙飘带向左右完全展开。极薄香雾形成贴近地面的横向薄带，油灯火焰产生同向轻微偏转。摄影机与人物同速横移并短促推近，人物高度保持约68%—72%，双脚接触和承重变化清楚。

7.000—10.000秒：栀夏以落脚急停分隔舞句，视线从月影转向斜前上方不可见的天乐来处，完成斜向踏进所需的蓄力、胸腰收拢和前后重心准备。人物保持三分之四正面，双眼、肩肘手腕、双腿和鞋履持续可见。

10.000—13.200秒，纵深迎乐：栀夏朝斜前方连续踏进三步，第三步突然深沉身，随后胸腰反向提展；一臂指向斜前上方天乐来处，另一臂向身后下方拉成长线。身体、双臂、蓝橙飘带与极薄香雾共同形成贯穿近景和斜前纵深的前后错层长线，香雾由近向斜前方延伸。摄影机沿原轴迎面推近，人物高度保持约70%，第三次动作、飘带、香雾与镜头反馈和前两次同等强烈。

13.200—15.000秒：栀夏落脚后继续斜向换重，目光停在天窗上方，双臂仍在回收途中，蓝橙飘带保留前后错层余势。人物保持近距离完整全身，在持续舞势中结束。

人物视线依次落在璎珞与指尖、天窗月影和斜前上方天乐来处；情绪从静心闻钟转为望月时的克制欣悦，最后进入明净庄严。摄影机沿“指尖近景后撤至侧前完整全身，再以小范围伴随保持近距离”的单一主路径运动。三次高能舞姿同等强烈，方向分别为纵向、左右横向和斜前纵深。

声音仅包含钟声、箜篌、低沉鼓点、衣料声、脚步声与石窟空间回响。第一记钟声对应指尖近景，箜篌在横向追月时展开，低沉鼓点在纵深迎乐时增强；声音保持纯器乐与自然环境质感。画面保持真实人体、真实布料重量、真实石材、真实香雾、统一月光方向、稳定人物身份和纯净电影构图。
```

模型正文只保留正向可观察结果。内部资产路径、母板版本、设计分类、生产状态、回退条件、历史边界与负面清单全部留在代码块外。

- [ ] **Step 4: 运行测试确认失败点前移到台账**

Run: `zsh tests/test_liantai_tianyue_15s_prompt.sh`

Expected: README 和提示词检查通过，只因缺少 `liantai-tianyue-15s` 台账行而失败。

### Task 3: 登记去重台账并完成验收

**Files:**
- Modify: `zhixia-feihualing/operations/dance-design-history.csv`

**Interfaces:**
- Consumes: Task 2 的最终开场、动作、香雾反馈、视线和摄影机设计。
- Produces: 一条完整 25 列、状态为 `designed` 的第六支视觉指纹记录。

- [ ] **Step 1: 追加唯一台账行**

追加以下完整 25 列记录：

```csv
liantai-tianyue-15s,李白《庐山东林寺夜怀》,璎珞指尖特写转单膝供养低位,单膝提身转横向双换重再斜前三步,三高潮供养回应序列,零完整旋转,单膝低位转纵向提身；横向大侧倾回弹；深沉身转纵深提展,指尖近景转三分之四正面单膝低位斜线,高低供养大弧；上下反向月弧；前上后下纵深长线,单膝支撑转双脚落地；横向双换重；斜前三步深沉提展,蓝橙双层飘带与极薄香雾,纵向高低双弧；横向月弧；前后错层长线,真实极薄香雾,向上窄柱；贴地横向薄带；由近向斜前长线,0.800—1.800秒；4.800—7.000秒；10.000—13.200秒,近景沿手臂后撤转侧前伴随主路径,后撤后轻微抬升；同速横移并短促推近；沿原轴迎面推近,斜向换重并在双臂与飘带余势中切断,designed,敦煌十六舞06；仅上传栀夏v03；局部特写单变量测试；0.800秒前恢复全身；不直视镜头；徒手供养舞意象；回退条件已定义,纵向应钟；横向追月；纵深迎乐,纵向；左右横向；斜前纵深,0.800—1.800秒；4.800—7.000秒；10.000—13.200秒,香雾向上窄柱；贴地横向薄带；由近向斜前长线,完整揭示后轻微抬升；同速横移并短促推近；沿原轴迎面推近
```

- [ ] **Step 2: 运行完整门禁**

Run: `zsh tests/test_liantai_tianyue_15s_prompt.sh`

Expected: PASS，输出 `PASS: Liantai Tianyue 15s prompt and history are complete`。

- [ ] **Step 3: 执行最终验证**

Run:

```zsh
zsh tests/test_liantai_tianyue_15s_prompt.sh
git diff --check -- episodes/liantai-tianyue-15s tests/test_liantai_tianyue_15s_prompt.sh operations/dance-design-history.csv
awk -F, 'NF != 25 {print NR ":" NF; bad=1} END {exit bad}' operations/dance-design-history.csv
test "$(rg -c '^liantai-tianyue-15s,' operations/dance-design-history.csv)" = "1"
```

Expected: 门禁输出 PASS；目标文件无空白错误；台账全部 25 列；`liantai-tianyue-15s` 恰有一条记录。

- [ ] **Step 4: 提交单集与台账**

```zsh
git add episodes/liantai-tianyue-15s/README.md episodes/liantai-tianyue-15s/prompts/seedance-v01.md operations/dance-design-history.csv
git commit -m "制作敦煌莲台天乐视频提示词"
```

若舞蹈台账同时包含其他用户未提交改动，只暂存本次新增的 `liantai-tianyue-15s` 行并单独提交；不暂存角色母板、资产清单、其他计划、其他单集文件或其他工作区修改。
