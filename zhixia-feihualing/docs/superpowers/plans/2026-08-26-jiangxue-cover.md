# 《江雪》视频号封面 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用《江雪》无字幕成片抽帧和新版庐山封面的文字体系生成可直接发布的视频号封面。

**Architecture:** 使用 Swift/AppKit 读取 720×1280 PNG 底图，通过系统 `STXingkaiSC-Light` 字体绘制栏目签、双列诗句和作者题名。构建脚本负责归档底图、调用渲染器并同步发布文件；Shell 测试验证尺寸、文件一致性和固定文案。

**Tech Stack:** Swift、AppKit、CoreText、zsh、sips

## Global Constraints

- 底图固定为 `episodes/jiangxue/work/frame-0.5.png`，保持 720×1280，不裁切人物。
- 文字体系参考 `episodes/lushan/assets/cover/lushan-cover-v01-poem-story.png`。
- 栏目签为“诗词小故事”。
- 主诗句按从左到右列顺序展示“孤舟蓑笠翁”“独钓寒江雪”。
- 作者题名为“唐·柳宗元《江雪》”。
- 使用 `STXingkaiSC-Light` 和暖白 `#F0DEC2`，不使用红色标题。
- 不添加“他怎么还不收竿？”、账号名、完整对白或其他说明文字。
- 保留成片原有 AI 内容标识，不修改人物和道具。

---

### Task 1: 实现可重复生成的《江雪》封面

**Files:**
- Create: `zhixia-feihualing/tests/test_jiangxue_cover.sh`
- Create: `zhixia-feihualing/scripts/render_jiangxue_cover.swift`
- Create: `zhixia-feihualing/scripts/build_jiangxue_cover.sh`
- Create: `zhixia-feihualing/episodes/jiangxue/assets/images/cover-base-v01.png`
- Create: `zhixia-feihualing/episodes/jiangxue/assets/images/cover-final-v01.png`
- Create: `zhixia-feihualing/exports/jiangxue-cover.png`

**Interfaces:**
- Consumes: `render_jiangxue_cover.swift <base.png> <output.png>` 读取 720×1280 PNG。
- Produces: `build_jiangxue_cover.sh` 生成内容一致的单集封面和发布封面。

- [ ] **Step 1: 写入失败测试**

创建 `tests/test_jiangxue_cover.sh`，验证以下具体条件：

```zsh
for file in "$base" "$final" "$exported" "$renderer"; do
  [[ -f "$file" ]] || { print -u2 "缺少文件：$file"; exit 1; }
done
[[ "$(sips -g pixelWidth "$final" | awk '/pixelWidth/ {print $2}')" == "720" ]]
[[ "$(sips -g pixelHeight "$final" | awk '/pixelHeight/ {print $2}')" == "1280" ]]
cmp -s "$final" "$exported"
cmp -s "$base" "$final" && exit 1
grep -q '诗词小故事' "$renderer"
grep -q '孤舟蓑笠翁' "$renderer"
grep -q '独钓寒江雪' "$renderer"
grep -q '唐·柳宗元《江雪》' "$renderer"
! grep -q '他怎么还不收竿' "$renderer"
```

- [ ] **Step 2: 运行测试并确认失败**

运行：`zsh zhixia-feihualing/tests/test_jiangxue_cover.sh`

预期：因封面或渲染脚本尚不存在而失败。

- [ ] **Step 3: 实现 Swift 渲染器**

创建 `scripts/render_jiangxue_cover.swift`：

- 注册 `/System/Library/AssetsV2/com_apple_MobileAsset_Font7/aa99d0b2bad7f797f38b49d46cde28fd4b58876e.asset/AssetData/Xingkai.ttc`。
- 创建 720×1280 RGBA 位图并铺满输入底图。
- 用逐字竖排函数绘制：
  - `诗词小故事`：x=50、top=54、step=34、font=28。
  - `孤舟蓑笠翁`：x=100、top=218、step=76、font=68。
  - `独钓寒江雪`：x=208、top=292、step=76、font=68。
  - `唐·柳宗元《江雪》`：x=52、top=680、step=35、font=26。
- 所有文字使用暖白色 `(240/255, 222/255, 194/255)`，深灰描边和黑色柔和阴影。
- 输入或字体不可用时返回非零状态，不生成残缺封面。

- [ ] **Step 4: 实现构建脚本并生成封面**

创建 `scripts/build_jiangxue_cover.sh`，完整执行顺序为：

```zsh
#!/bin/zsh
set -euo pipefail
root="${0:A:h:h}"
source="$root/episodes/jiangxue/work/frame-0.5.png"
base="$root/episodes/jiangxue/assets/images/cover-base-v01.png"
final="$root/episodes/jiangxue/assets/images/cover-final-v01.png"
exported="$root/exports/jiangxue-cover.png"
mkdir -p "${base:h}" "${exported:h}"
ditto "$source" "$base"
swift "$root/scripts/render_jiangxue_cover.swift" "$base" "$final"
ditto "$final" "$exported"
```

运行：`zsh zhixia-feihualing/scripts/build_jiangxue_cover.sh`

预期：生成底图归档、最终封面和发布文件。

- [ ] **Step 5: 运行自动验证**

运行：`zsh zhixia-feihualing/tests/test_jiangxue_cover.sh`

预期：输出 `PASS: 江雪视频号封面`。

### Task 2: 登记资产并完成视觉验收

**Files:**
- Modify: `zhixia-feihualing/assets/inventory.csv`
- Inspect: `zhixia-feihualing/episodes/jiangxue/assets/images/cover-final-v01.png`

**Interfaces:**
- Consumes: Task 1 生成的底图和最终封面。
- Produces: 资产清单中的可追溯记录和经视觉验收的发布文件。

- [ ] **Step 1: 登记底图和最终封面**

在 `assets/inventory.csv` 末尾增加：

```csv
jiangxue-cover-base-v01,image,江雪,cover-base,episodes/jiangxue/assets/images/cover-base-v01.png,available,video frame extraction,original project asset,720×1280；取自frame-0.5.png；无字幕成片抽帧
jiangxue-cover-final-v01,image,江雪,cover,episodes/jiangxue/assets/images/cover-final-v01.png,final,local Swift/AppKit typography,original project asset,720×1280；复用新版庐山诗词小故事字幕体系；发布文件exports/jiangxue-cover.png
```

- [ ] **Step 2: 视觉验收**

以原始分辨率和 25% 缩放检查最终封面：四组文字准确；双列诗句顺序正确；文字不遮挡栀夏面部、阿砚头部和孤舟老翁；主诗句在缩略图中清晰；画面没有新增生成缺陷。

- [ ] **Step 3: 运行最终验证**

运行测试和差异检查：

```bash
zsh zhixia-feihualing/tests/test_jiangxue_cover.sh
git diff --check -- zhixia-feihualing/scripts/render_jiangxue_cover.swift zhixia-feihualing/scripts/build_jiangxue_cover.sh zhixia-feihualing/tests/test_jiangxue_cover.sh zhixia-feihualing/assets/inventory.csv
```

预期：测试通过且 `git diff --check` 无输出。

- [ ] **Step 4: 提交封面资产**

提交渲染器、构建脚本、测试、底图、最终封面、发布文件和资产清单，提交信息为：

```bash
git commit -m '素材：生成江雪视频号封面'
```

