# 《一舞一愿·九月好运》天宫双人热舞成片 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将已确认的10.08秒天宫双人热舞、原音乐、三句栀夏朗诵和上方横排加左侧竖排字幕合成为1080×1920视频号成片。

**Architecture:** 先把用户原片保存为项目源素材并建立字幕时间清单，再用独立Swift渲染器生成透明字幕卡。单一FFmpeg构建脚本负责保真放大、原声侧链闪避、尾部余韵、配音混合与字幕覆盖，并同时产出无字幕有声版和最终字幕版；Shell验收脚本从输入、结构、时间、解码、音轨一致性和关键帧六个方面验证。

**Tech Stack:** zsh、Swift/AppKit/CoreText、FFmpeg、ffprobe、jq、SHA-256。

## Global Constraints

- 输入视频完整保留10.080秒，不删除动作，不覆盖用户下载原件。
- 输出固定H.264、1080×1920、24fps、AAC 48kHz双声道并启用快速起播。
- 画面只做Lanczos放大、居中裁切、克制降噪与轻锐化；不美颜、不重绘、不补帧。
- 原音乐保留；朗诵出现时平滑压低约4至6dB，最后0.756秒由原音乐余韵收势。
- 朗诵使用现有10.080秒三句WAV，不变速、不变调、不截断。
- 现代祝福为上方暖象牙白横排；诗句为左侧暖象牙白竖排，题署固定为“清·曹雪芹《临江仙·柳絮》”。
- 字幕画面省略标点，同一时刻只显示一条，不增加栏目名、标题或贴纸。
- 原片AI生成标识保留，不遮盖。

---

### Task 1: 固定源视频与字幕时间清单

**Files:**
- Create: `episodes/tiangong-hot-dance-zhixia-ayan-duet-10s/assets/video/content-seedance-v01.mp4`
- Create: `episodes/tiangong-hot-dance-zhixia-ayan-duet-10s/subtitle-plan-jiuyue-haoyun-v01.json`

**Interfaces:**
- Consumes: `/Users/huan.yu/Downloads/9f8429ad-6817-4244-bb6f-c3827c476779.mp4` 与 `audio-timing-jiuyue-haoyun-v02.json`。
- Produces: 构建脚本使用的稳定源视频路径和三条字幕清单。

- [ ] **Step 1: 保存原片副本并核对哈希**

```bash
mkdir -p episodes/tiangong-hot-dance-zhixia-ayan-duet-10s/assets/video
cp /Users/huan.yu/Downloads/9f8429ad-6817-4244-bb6f-c3827c476779.mp4 \
  episodes/tiangong-hot-dance-zhixia-ayan-duet-10s/assets/video/content-seedance-v01.mp4
shasum -a 256 /Users/huan.yu/Downloads/9f8429ad-6817-4244-bb6f-c3827c476779.mp4 \
  episodes/tiangong-hot-dance-zhixia-ayan-duet-10s/assets/video/content-seedance-v01.mp4
```

Expected: 两个SHA-256完全一致。

- [ ] **Step 2: 写入字幕清单**

```json
[
  {"id":"01-modern-blessing","kind":"modern","text":"九月 愿所有美好 久久相伴","start":0.42,"end":3.70},
  {"id":"02-middle-wish","kind":"modern","text":"所念 皆能如愿","start":4.57,"end":6.10},
  {"id":"03-poem","kind":"poem","text":"好风凭借力，送我上青云","attribution":"清·曹雪芹《临江仙·柳絮》","start":6.96,"end":9.52}
]
```

- [ ] **Step 3: 验证清单内容**

```bash
jq -e '
  length == 3 and
  .[0].text == "九月 愿所有美好 久久相伴" and
  .[1].text == "所念 皆能如愿" and
  .[2].text == "好风凭借力，送我上青云" and
  .[2].attribution == "清·曹雪芹《临江仙·柳絮》" and
  .[0].start < .[0].end and .[0].end < .[1].start and
  .[1].start < .[1].end and .[1].end < .[2].start and
  .[2].start < .[2].end and .[2].end <= 10.08
' episodes/tiangong-hot-dance-zhixia-ayan-duet-10s/subtitle-plan-jiuyue-haoyun-v01.json
```

Expected: exit 0。

### Task 2: 以TDD建立专用字幕卡渲染器

**Files:**
- Create: `tests/test_tiangong_hot_dance_jiuyue_haoyun_final.sh`
- Create: `scripts/render_jiuyue_haoyun_subtitle_cards.swift`

**Interfaces:**
- Consumes: Task 1字幕清单。
- Produces: 720×1280透明PNG字幕卡 `01-modern-blessing.png`、`02-middle-wish.png`、`03-poem.png`。

- [ ] **Step 1: 写入失败验收脚本**

验收脚本首先检查源视频、三句WAV、字幕清单、渲染器和构建脚本均存在；调用构建脚本后检查两条输出的视频流、音频流、10.04至10.12秒时长、1080×1920、24fps、48kHz双声道以及可完整解码；最后提取两版AAC并断言SHA-256一致。

- [ ] **Step 2: 运行测试并确认失败**

```bash
zsh tests/test_tiangong_hot_dance_jiuyue_haoyun_final.sh
```

Expected: FAIL，原因是渲染器或构建脚本尚不存在。

- [ ] **Step 3: 实现最小字幕渲染器**

渲染器读取Task 1清单并输出720×1280透明PNG：

- `modern` 使用 `STXingkaiSC-Bold` 42pt，暖象牙白，水平居中，屏幕顶部约180px。
- `poem` 使用 `STXingkaiSC-Bold` 62pt，按标点拆成两列，从右向左排列在左侧x=184与x=100，顶部约190px，字距68px。
- 题署使用 `STKaitiSC-Regular` 26pt，位于x=42、顶部约192px，字距34px。
- 所有文字使用黑色52%透明度、4px模糊的轻阴影，不绘制底框。

- [ ] **Step 4: 单独生成字幕卡并验证**

```bash
cards_dir="$(mktemp -d /tmp/zhixia-jiuyue-cards.XXXXXX)"
swift scripts/render_jiuyue_haoyun_subtitle_cards.swift \
  episodes/tiangong-hot-dance-zhixia-ayan-duet-10s/subtitle-plan-jiuyue-haoyun-v01.json \
  "$cards_dir"
file "$cards_dir"/*.png
```

Expected: 三个非空720×1280 RGBA PNG。

- [ ] **Step 5: 提交字幕组件**

```bash
git add \
  zhixia-feihualing/episodes/tiangong-hot-dance-zhixia-ayan-duet-10s/subtitle-plan-jiuyue-haoyun-v01.json \
  zhixia-feihualing/scripts/render_jiuyue_haoyun_subtitle_cards.swift \
  zhixia-feihualing/tests/test_tiangong_hot_dance_jiuyue_haoyun_final.sh
git diff --cached --check
git commit -m "功能：增加九月好运热舞字幕组件"
```

### Task 3: 构建混音与最终字幕视频

**Files:**
- Create: `scripts/build_tiangong_hot_dance_jiuyue_haoyun_final.sh`
- Create: `exports/tiangong-hot-dance-zhixia-ayan-duet-10s-jiuyue-haoyun-voiced-v01.mp4`
- Create: `exports/tiangong-hot-dance-zhixia-ayan-duet-10s-jiuyue-haoyun-subtitled-v01.mp4`

**Interfaces:**
- Consumes: Task 1源视频与字幕计划、Task 2字幕渲染器、现有三句WAV。
- Produces: 无字幕有声中间版和最终字幕版。

- [ ] **Step 1: 实现构建脚本**

脚本使用临时目录生成字幕卡和有声母版。视频滤镜固定为：`trim=duration=10.08`、Lanczos缩放至高1920、居中裁切1080×1920、`hqdn3d=0.6:0.6:1.8:1.8`、`unsharp=5:5:0.22:3:3:0`、24fps与yuv420p。

人声滤镜固定使用48kHz双声道、高通90Hz、2600Hz提升1.8dB、温和压缩和1.08倍音量。原声先转48kHz双声道并降至0.90倍，再增加低强度多重回声余韵覆盖原片约9.4秒后的尾部；使用人声副本驱动侧链压缩，混合后限幅并严格裁至10.08秒。

字幕覆盖区间固定为0.42—3.70秒、4.57—6.10秒、6.96—9.52秒，每张卡使用0.10秒淡入和0.12秒淡出。最终字幕版直接复制有声母版AAC音轨，禁止二次编码音频。

- [ ] **Step 2: 运行完整测试**

```bash
zsh tests/test_tiangong_hot_dance_jiuyue_haoyun_final.sh
```

Expected: `PASS: 九月好运天宫双人热舞成片已就绪`。

- [ ] **Step 3: 提交构建脚本**

```bash
git add zhixia-feihualing/scripts/build_tiangong_hot_dance_jiuyue_haoyun_final.sh
git diff --cached --check
git commit -m "功能：合成九月好运热舞成片"
```

### Task 4: 视觉与声音终检

**Files:**
- Modify: `assets/inventory.csv`

**Interfaces:**
- Consumes: Task 3两条视频输出。
- Produces: 最终视觉检查证据和资产登记。

- [ ] **Step 1: 抽取关键帧联系表**

```bash
ffmpeg -y -v error \
  -i exports/tiangong-hot-dance-zhixia-ayan-duet-10s-jiuyue-haoyun-subtitled-v01.mp4 \
  -vf "select='eq(n,12)+eq(n,60)+eq(n,116)+eq(n,174)+eq(n,228)',scale=270:480,tile=5x1" \
  -frames:v 1 /tmp/zhixia-jiuyue-haoyun-final-contact-sheet.png
```

目视确认现代字幕位于上方且不遮脸，诗句位于左侧且不遮腿、髋部或换位，结尾AI标识仍可见。

- [ ] **Step 2: 检查混音响度与尾部**

```bash
ffmpeg -hide_banner \
  -i exports/tiangong-hot-dance-zhixia-ayan-duet-10s-jiuyue-haoyun-subtitled-v01.mp4 \
  -af ebur128=peak=true -f null -
```

确认无削波；抽听三句清晰、原鼓点仍可辨识、9.4至10.08秒存在自然余韵而非突然静音。

- [ ] **Step 3: 登记源视频与两条输出**

在 `assets/inventory.csv` 追加源视频、有声版和最终字幕版三条记录，包含时长、分辨率、帧率、音轨、来源和最终状态。该文件已有不相关未提交改动，只追加本任务三行，不在无法隔离时暂存整份文件。

- [ ] **Step 4: 重新运行最终验收**

```bash
zsh tests/test_tiangong_hot_dance_jiuyue_haoyun_final.sh
```

Expected: exit 0，零失败。
