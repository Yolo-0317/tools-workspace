# 星轨六爻盘矢量母板与召唤资产实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立严格正圆、六爻拓扑可验证的“星轨六爻盘”矢量母板，并由同一几何源输出道具设计板、栀夏动作卡叠加层和 3 秒召唤模板视频所需的确定性资产。

**Architecture:** SVG 是卦盘几何的唯一事实来源，Python 生成器负责正圆、同心轨道、六个空爻槽及阴阳爻状态，Swift/AppKit 只把 SVG 无损栅格化为 PNG。GPT 或视频模型只生成人物动作与非结构性氛围，圆盘、爻线和准确状态始终在本地确定性合成。

**Tech Stack:** Python 3 标准库、SVG 1.1、Swift/AppKit、PNG、FFmpeg/FFprobe、Zsh 验收脚本、CSV 资产清单。

## Global Constraints

- 设计依据：`docs/superpowers/specs/2026-08-26-ai-divination-disc-and-summoning-template-design.md`。
- 卦盘名称固定为“星轨六爻盘”，召唤动作固定为“引弧起盘”。
- 所有主盘与流程盘必须引用同一个 SVG 母盘，横纵直径相等、所有同心轨道共用圆心。
- 母盘中心恰好六个等宽、等距、低亮度空爻槽，不得出现第七槽，不得预填六条阳爻。
- 最内侧圆环以内是盘心净空信息区，只保留六个空爻槽、极淡底色和状态光；任何星座连线、星点网络或方位射线都不得进入。
- 阳爻为一条完整横线；阴爻为左右两段等长横线且中央断口清楚。
- 第四格自下而上固定为阳、阴、阴，第四至第六槽保持空白。
- 首集“山雷颐”自下而上固定为阳、阴、阴、阴、阴、阳。
- 卦盘为单层平面，不做 3D 分层、透视压缩、椭圆或厚重实体结构。
- 配色固定为月白、浅青、暖金与极少朱砂，不使用蓝紫霓虹或强光柱。
- GPT 与视频模型不得负责圆盘轮廓、六爻数量、阴阳结构或准确文字。
- 用户未明确确认的候选资产不得登记为 `approved`。

---

### Task 1: 建立矢量几何与六爻拓扑测试

**Files:**
- Create: `zhixia-feihualing/tests/test_divination_disc_vectors.py`
- Create: `zhixia-feihualing/scripts/generate_divination_disc_vectors.py`

**Interfaces:**
- Consumes: 无；几何常量直接来自已确认设计规范。
- Produces: `build_assets(output_root: Path) -> None`，生成空爻母盘、阴阳组件、流程状态和设计板 SVG。

- [ ] **Step 1: 写入预期失败的几何测试**

测试用 Python 标准库 `xml.etree.ElementTree` 读取 SVG，并覆盖以下断言：

```python
from pathlib import Path
import importlib.util
import tempfile
import unittest
import xml.etree.ElementTree as ET
import re

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/generate_divination_disc_vectors.py"

def load_generator():
    spec = importlib.util.spec_from_file_location("disc_vectors", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def elements(path: Path, role: str):
    root = ET.parse(path).getroot()
    return [node for node in root.iter() if node.attrib.get("data-role") == role]

def segment_distance_from_center(x1, y1, x2, y2, center=512):
    dx, dy = x2 - x1, y2 - y1
    length_squared = dx * dx + dy * dy
    t = ((center - x1) * dx + (center - y1) * dy) / length_squared
    t = max(0.0, min(1.0, t))
    nearest_x, nearest_y = x1 + t * dx, y1 + t * dy
    return ((nearest_x - center) ** 2 + (nearest_y - center) ** 2) ** 0.5

class DivinationDiscVectorTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.output = Path(self.temp_dir.name)
        load_generator().build_assets(self.output)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_blank_master_is_circular_and_has_exactly_six_empty_slots(self):
        master = self.output / "disc-master.svg"
        rings = elements(master, "disc-ring")
        slots = elements(master, "empty-slot")
        self.assertGreaterEqual(len(rings), 5)
        self.assertTrue(all(r.attrib["cx"] == r.attrib["cy"] for r in rings))
        self.assertEqual(len(slots), 6)
        self.assertFalse(elements(master, "filled-yao"))

    def test_partial_state_is_bottom_up_yang_yin_yin(self):
        lines = elements(self.output / "state-partial-3.svg", "filled-yao")
        self.assertEqual([line.attrib["data-kind"] for line in lines], ["yang", "yin", "yin"])
        self.assertEqual([line.attrib["data-position"] for line in lines], ["1", "2", "3"])

    def test_shanlei_yi_has_exact_six_line_topology(self):
        lines = elements(self.output / "state-shanlei-yi.svg", "filled-yao")
        self.assertEqual(
            [line.attrib["data-kind"] for line in lines],
            ["yang", "yin", "yin", "yin", "yin", "yang"],
        )

    def test_constellation_links_stay_outside_inner_clear_zone(self):
        links = elements(self.output / "disc-master.svg", "constellation-link")
        self.assertGreaterEqual(len(links), 8)
        for link in links:
            values = [float(value) for value in re.findall(r"-?\d+(?:\.\d+)?", link.attrib["d"])]
            points = list(zip(values[0::2], values[1::2]))
            for start, end in zip(points, points[1:]):
                self.assertGreaterEqual(segment_distance_from_center(*start, *end), 224)
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `python3 -m unittest zhixia-feihualing/tests/test_divination_disc_vectors.py -v`

Expected: FAIL because `scripts/generate_divination_disc_vectors.py` does not exist.

- [ ] **Step 3: 实现最小 SVG 生成器**

生成器固定使用 `viewBox="0 0 1024 1024"`、圆心 `(512, 512)`，并公开以下常量：

```python
CENTER = 512
RING_RADII = (440, 414, 354, 292, 224)
YAO_Y_BOTTOM_UP = (632, 584, 536, 488, 440, 392)
YAO_X1 = 390
YAO_X2 = 634
YIN_GAP = 34
SHANLEI_YI = ("yang", "yin", "yin", "yin", "yin", "yang")
```

`build_assets(output_root)` 必须生成：

```text
disc-master.svg
component-yang.svg
component-yin.svg
state-empty.svg
state-partial-3.svg
state-shanlei-yi.svg
design-board.svg
```

所有几何节点写入可测试的 `data-role`，爻线额外写入 `data-kind` 与 `data-position`。圆环只能使用 `<circle>`，不得用椭圆或透视变换模拟圆盘；六个空槽作为母盘固定结构，状态层使用独立发光爻线覆盖对应槽位。

- [ ] **Step 4: 运行测试并确认通过**

Run: `python3 -m unittest zhixia-feihualing/tests/test_divination_disc_vectors.py -v`

Expected: 4 tests PASS.

- [ ] **Step 5: 提交矢量生成器与测试**

```bash
git add zhixia-feihualing/scripts/generate_divination_disc_vectors.py zhixia-feihualing/tests/test_divination_disc_vectors.py
git commit -m "建立六爻盘矢量几何生成器"
```

### Task 2: 输出并验收正圆空爻母盘

**Files:**
- Create: `zhixia-feihualing/scripts/rasterize_svg.swift`
- Create: `zhixia-feihualing/scripts/build_divination_disc_assets.sh`
- Create: `zhixia-feihualing/tests/test_divination_disc_assets.sh`
- Create: `zhixia-feihualing/assets/props/ai-divination-disk-v01/vector/disc-master.svg`
- Create: `zhixia-feihualing/assets/props/ai-divination-disk-v01/previews/disc-master.png`

**Interfaces:**
- Consumes: `build_assets(output_root: Path) -> None` 生成的 SVG。
- Produces: 可人工审阅的 2048×2048 正圆空爻母盘 PNG，以及后续状态和设计板的统一构建入口。

- [ ] **Step 1: 写入预期失败的构建验收脚本**

```zsh
#!/bin/zsh
set -euo pipefail

project_dir="$(cd "$(dirname "$0")/.." && pwd)"
vector="$project_dir/assets/props/ai-divination-disk-v01/vector/disc-master.svg"
preview="$project_dir/assets/props/ai-divination-disk-v01/previews/disc-master.png"

test -s "$vector"
test -s "$preview"
python3 -m unittest "$project_dir/tests/test_divination_disc_vectors.py" -v

dimensions="$(sips -g pixelWidth -g pixelHeight "$preview" 2>/dev/null \
  | awk '/pixelWidth/{w=$2}/pixelHeight/{h=$2}END{print w" "h}')"
test "$dimensions" = "2048 2048"
ffmpeg -v error -i "$preview" -frames:v 1 -f null -
echo "divination disc vector assets: PASS"
```

- [ ] **Step 2: 运行脚本并确认失败**

Run: `zsh zhixia-feihualing/tests/test_divination_disc_assets.sh`

Expected: FAIL because the vector and preview files do not exist.

- [ ] **Step 3: 实现通用 SVG 栅格化工具**

`rasterize_svg.swift` 的命令接口固定为：

```text
swift scripts/rasterize_svg.swift <input.svg> <output.png> <width> <height>
```

工具用 `NSImage(contentsOf:)` 读取 SVG，用 `NSBitmapImageRep` 绘制指定尺寸，再以 PNG 写出；输入不能解码、尺寸不是正整数或 PNG 写入失败时返回非零状态。

- [ ] **Step 4: 实现统一构建脚本**

`build_divination_disc_assets.sh` 依次运行 Python 生成器，并将 `disc-master.svg` 栅格化为 2048×2048 PNG。构建脚本必须从自身位置计算项目根目录，不依赖调用者当前目录。

- [ ] **Step 5: 构建并运行自动验收**

Run: `zsh zhixia-feihualing/scripts/build_divination_disc_assets.sh`

Run: `zsh zhixia-feihualing/tests/test_divination_disc_assets.sh`

Expected: `divination disc vector assets: PASS`.

- [ ] **Step 6: 人工验收第一阶段母盘**

打开 `assets/props/ai-divination-disk-v01/previews/disc-master.png`，只检查：标准正圆、严格同心、八方均匀、恰好六个空槽、无填充爻、无第七槽、无透视和无文字。若结构未通过，只修改 SVG 生成器参数并重新构建，不进入状态层。

- [ ] **Step 7: 提交通过验收的空爻母盘**

```bash
git add zhixia-feihualing/scripts/rasterize_svg.swift \
  zhixia-feihualing/scripts/build_divination_disc_assets.sh \
  zhixia-feihualing/tests/test_divination_disc_assets.sh \
  zhixia-feihualing/assets/props/ai-divination-disk-v01/vector/disc-master.svg \
  zhixia-feihualing/assets/props/ai-divination-disk-v01/previews/disc-master.png
git commit -m "绘制星轨六爻盘正圆空爻母板"
```

### Task 3: 生成阴阳组件、状态图与最终设计板

**Files:**
- Modify: `zhixia-feihualing/scripts/generate_divination_disc_vectors.py`
- Modify: `zhixia-feihualing/tests/test_divination_disc_vectors.py`
- Modify: `zhixia-feihualing/scripts/build_divination_disc_assets.sh`
- Create: `zhixia-feihualing/assets/props/ai-divination-disk-v01/vector/component-yang.svg`
- Create: `zhixia-feihualing/assets/props/ai-divination-disk-v01/vector/component-yin.svg`
- Create: `zhixia-feihualing/assets/props/ai-divination-disk-v01/vector/state-partial-3.svg`
- Create: `zhixia-feihualing/assets/props/ai-divination-disk-v01/vector/state-shanlei-yi.svg`
- Create: `zhixia-feihualing/assets/props/ai-divination-disk-v01/master.png`

**Interfaces:**
- Consumes: 用户确认的 `disc-master.svg` 与固定六爻拓扑常量。
- Produces: 两个标准爻组件、第四格中间态、完整山雷颐状态以及 1920×1080 最终道具设计板。

- [ ] **Step 1: 扩充测试以锁定组件与设计板复用关系**

新增断言：阴爻左右段等长、中央断口为 34；阳爻总宽度为 244；设计板中所有圆盘实例使用 `<use href="#disc-master">`；第四格只包含第 1—3 爻；第五、六格包含准确的六爻结果。

```python
def test_design_board_reuses_one_disc_symbol(self):
    root = ET.parse(self.output / "design-board.svg").getroot()
    uses = [n for n in root.iter() if n.attrib.get("data-role") == "disc-instance"]
    self.assertEqual(len(uses), 6)
    self.assertEqual({n.attrib["href"] for n in uses}, {"#disc-master"})
```

- [ ] **Step 2: 运行新增测试并确认失败**

Run: `python3 -m unittest zhixia-feihualing/tests/test_divination_disc_vectors.py -v`

Expected: FAIL because component measurements and board symbol reuse are not implemented.

- [ ] **Step 3: 完成状态层与 16:9 设计板 SVG**

设计板固定为 `viewBox="0 0 1920 1080"`：左侧放置一枚最大空爻主盘；右侧为 3×2 六格流程；底部只放一枚阳爻和一枚阴爻。第一格只有星点，第二、三格复用空盘，第四格叠加 `state-partial-3`，第五、六格叠加 `state-shanlei-yi`。所有盘面必须通过 `<symbol id="disc-master">` 和 `<use>` 复用，不复制不同版本的圆盘路径。

- [ ] **Step 4: 构建所有 SVG 和 1920×1080 PNG**

Run: `zsh zhixia-feihualing/scripts/build_divination_disc_assets.sh`

构建脚本将 `design-board.svg` 栅格化为 `assets/props/ai-divination-disk-v01/master.png`，同时保留全部 SVG 作为后期和视频合成源。

- [ ] **Step 5: 运行自动测试并逐项人工验收**

Run: `python3 -m unittest zhixia-feihualing/tests/test_divination_disc_vectors.py -v`

Run: `zsh zhixia-feihualing/tests/test_divination_disc_assets.sh`

Expected: 全部通过。随后按 `assets/props/ai-divination-disk-v01/qa-checklist.md` 人工核对正圆、六槽、第四格和山雷颐拓扑；用户明确确认前不登记 approved。

- [ ] **Step 6: 提交确定性状态资产与设计板**

```bash
git add zhixia-feihualing/scripts/generate_divination_disc_vectors.py \
  zhixia-feihualing/tests/test_divination_disc_vectors.py \
  zhixia-feihualing/scripts/build_divination_disc_assets.sh \
  zhixia-feihualing/assets/props/ai-divination-disk-v01/vector \
  zhixia-feihualing/assets/props/ai-divination-disk-v01/master.png
git commit -m "生成六爻盘状态组件与设计板"
```

### Task 4: 合成栀夏动作卡与视频精确叠加层

**Files:**
- Reference: `zhixia-feihualing/assets/characters/栀夏角色卡电影半写实-v02.png`
- Reference: `zhixia-feihualing/assets/characters/栀夏全身比例卡电影半写实-v02.png`
- Create after user approval: `zhixia-feihualing/assets/characters/栀夏引弧起盘人物动作底图电影半写实-v01.png`
- Create: `zhixia-feihualing/scripts/render_divination_summon_composites.swift`
- Create: `zhixia-feihualing/tests/test_divination_summon_composites.sh`
- Create: `zhixia-feihualing/assets/characters/栀夏引弧起盘动作卡电影半写实-v01.png`
- Create: `zhixia-feihualing/assets/props/ai-divination-disk-v01/overlays/video-empty.png`
- Create: `zhixia-feihualing/assets/props/ai-divination-disk-v01/overlays/video-partial-3.png`
- Create: `zhixia-feihualing/assets/props/ai-divination-disk-v01/overlays/video-shanlei-yi.png`

**Interfaces:**
- Consumes: approved 栀夏人物动作底图、同一个 `disc-master.svg` 和三个确定性状态。
- Produces: 六格动作卡以及可直接叠加到 1080×1920 视频的透明 PNG 状态层。

- [ ] **Step 1: 生成人物动作底图，不让模型绘制卦盘**

向 GPT 提供栀夏身份卡和全身比例卡，只生成 16:9 六格“引弧起盘”人物动作底图：浅暖灰背景、固定中近景、六格身份和机位一致；卦盘区域完整留空；不得生成圆盘、爻线、星轨、文字或结构性光效。用户确认人物、服装、双手和动作连续性后再归档底图。

- [ ] **Step 2: 写入预期失败的合成验收脚本**

检查动作卡为 1920×1080，三个视频叠加层为 1080×1920 RGBA PNG，并再次运行矢量拓扑测试。脚本还必须通过实际解码信息确认叠加层保留 alpha 通道。

- [ ] **Step 3: 运行验收并确认失败**

Run: `zsh zhixia-feihualing/tests/test_divination_summon_composites.sh`

Expected: FAIL because the compositor and output files do not exist.

- [ ] **Step 4: 实现确定性合成器**

`render_divination_summon_composites.swift` 接收人物六格底图、SVG 状态目录和输出目录。动作卡只把同一正圆母盘按六段状态叠加到预留区域；视频叠加层使用同一位置、同一缩放和透明背景，分别输出空盘、中间态与完整卦象。合成器不得对圆盘做非等比缩放。

- [ ] **Step 5: 构建并验收动作卡与视频叠加层**

Run: `swift zhixia-feihualing/scripts/render_divination_summon_composites.swift zhixia-feihualing/assets/characters/栀夏引弧起盘人物动作底图电影半写实-v01.png zhixia-feihualing/assets/props/ai-divination-disk-v01/vector zhixia-feihualing/assets/characters/栀夏引弧起盘动作卡电影半写实-v01.png zhixia-feihualing/assets/props/ai-divination-disk-v01/overlays`

Run: `zsh zhixia-feihualing/tests/test_divination_summon_composites.sh`

Expected: PASS；第四格的下三爻仍为阳、阴、阴，所有盘面仍为正圆。

- [ ] **Step 6: 提交动作合成资产**

```bash
git add zhixia-feihualing/scripts/render_divination_summon_composites.swift \
  zhixia-feihualing/tests/test_divination_summon_composites.sh \
  zhixia-feihualing/assets/characters/栀夏引弧起盘人物动作底图电影半写实-v01.png \
  zhixia-feihualing/assets/characters/栀夏引弧起盘动作卡电影半写实-v01.png \
  zhixia-feihualing/assets/props/ai-divination-disk-v01/overlays
git commit -m "合成栀夏引弧起盘动作资产"
```

### Task 5: 组装 3 秒召唤模板并登记母板

**Files:**
- Create after user approval: `zhixia-feihualing/assets/generated-video/templates/zhixia-summon-gesture-base-v01.mp4`
- Create: `zhixia-feihualing/scripts/build_divination_summon_template.sh`
- Modify: `zhixia-feihualing/tests/test_cyber_divination_summon_assets.sh`
- Create: `zhixia-feihualing/assets/generated-video/templates/zhixia-summon-divination-disc-template-v01.mp4`
- Modify: `zhixia-feihualing/assets/inventory.csv`

**Interfaces:**
- Consumes: 用户确认的无卦盘人物动作视频，以及 1080×1920 的确定性圆盘状态层。
- Produces: 约 3 秒召唤模板视频和三项 approved 资产登记。

- [ ] **Step 1: 生成人物动作视频底片，不让模型绘制卦盘**

视频模型只生成栀夏 3 秒“引弧起盘”动作、衣袖轻摆与非结构性星点；卦盘区域保持空白，不生成圆形界面、爻线、文字或强光。付费调用前展示平台、次数与成本并取得用户确认。

- [ ] **Step 2: 更新统一验收脚本并确认失败**

验收脚本检查：最终视频为 1080×1920、时长 2.8—3.2 秒、可以完整解码；三项 inventory 记录均为 approved；矢量拓扑测试和动作叠加测试继续通过。

Run: `zsh zhixia-feihualing/tests/test_cyber_divination_summon_assets.sh`

Expected: FAIL because the final template and approved inventory rows do not exist.

- [ ] **Step 3: 实现模板合成时间轴**

`build_divination_summon_template.sh` 使用 FFmpeg 等比叠加：0.0—0.3 秒只有人物与星点；0.3—0.8 秒淡入空盘外环；0.8—1.3 秒完整空盘稳定；1.3—2.1 秒按自下而上顺序显示六爻；2.1—2.5 秒完整结果锁定；2.5—3.0 秒只减弱外围光效，不改变六爻。输出使用 H.264、`yuv420p`、AAC 48 kHz。

- [ ] **Step 4: 抽帧核对状态和几何**

Run: 在 0.0、0.5、0.8、1.1、1.5、1.8、2.3、2.9 秒抽帧。

Expected: 圆盘全程等比且保持正圆；1.3 秒前为空槽；1.3—2.1 秒自下而上填充；2.1 秒后为准确山雷颐；人物身份和五指稳定；无模型生成的错误爻线。

- [ ] **Step 5: 用户确认后登记 approved**

在 `assets/inventory.csv` 登记：`ai-divination-disk-v01`、`zhixia-summon-divination-disc-action-v01` 和 `zhixia-summon-divination-disc-template-v01`。备注必须说明圆盘与六爻来自确定性矢量源，人物与氛围为 AI 辅助生成。

- [ ] **Step 6: 运行全量验收并提交**

Run: `python3 -m unittest zhixia-feihualing/tests/test_divination_disc_vectors.py -v`

Run: `zsh zhixia-feihualing/tests/test_divination_disc_assets.sh`

Run: `zsh zhixia-feihualing/tests/test_divination_summon_composites.sh`

Run: `zsh zhixia-feihualing/tests/test_cyber_divination_summon_assets.sh`

Expected: 所有测试 PASS。

```bash
git add zhixia-feihualing/scripts/build_divination_summon_template.sh \
  zhixia-feihualing/tests/test_cyber_divination_summon_assets.sh \
  zhixia-feihualing/assets/generated-video/templates/zhixia-summon-divination-disc-template-v01.mp4 \
  zhixia-feihualing/assets/inventory.csv
git commit -m "归档栀夏起卦召唤模板"
```
