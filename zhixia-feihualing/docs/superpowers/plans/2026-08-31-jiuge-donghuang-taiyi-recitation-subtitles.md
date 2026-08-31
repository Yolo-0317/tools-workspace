# 《九歌·东皇太一》朗诵字幕成片 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为已保留的 15.093 秒《九歌·东皇太一》祭舞原片加入四句栀夏女声朗诵、动态左右竖排字幕和高清后期，输出无字幕朗诵试听版与正式字幕版。

**Architecture:** `voice-lines.json` 驱动现有豆包 TTS 流程生成四条独立人声；独立的九歌字幕计划与 Swift/AppKit 渲染器生成四张 1080×1920 透明字幕卡；一个 FFmpeg 构建脚本完成无拉伸放大、轻度画质整理、人声时间定位、平滑侧链避让、字幕淡入淡出与两份成片输出。测试分成配置、字幕卡和最终成片三层，先失败后实现。

**Tech Stack:** Python 3、现有豆包 TTS 管线、JSON/jq、Swift/AppKit/CoreText、FFmpeg/ffprobe、zsh、sips。

## Global Constraints

- 原片固定使用 `episodes/jiuge-donghuang-taiyi-15s/assets/video/content-raw-v01.mp4`，不重绘、不重生成、不修复已接受偏差。
- 朗诵固定为四个分句：`吉日兮辰良`、`穆将愉兮上皇`、`五音纷兮繁会`、`君欣欣兮乐康`。
- 题署固定为 `屈原《九歌·东皇太一》节选`，不得省略“节选”。
- 使用 `zhixia` 固定音色；自然说诗、克制、低甜度、有空间感，禁止男声、播音腔、吟唱和神谕式夸张。
- 朗诵时间窗固定为 0.450—3.100、3.400—6.600、7.600—10.700、11.000—14.500 秒。
- 字幕固定按右、左、右、左切换；暖象牙白楷体、旧金细描边、玄黑柔影，避开脸、主要手势、躯干中心和右下角原标识。
- 原音乐与环境声全程连续；人声期间平滑避让约 3—4dB，句间自然回升。
- 两份输出均为约 15.093 秒、1080×1920、24fps、H.264、AAC 48kHz 双声道；正式版复用试听版音轨。

---

### Task 1: 配音与字幕配置

**Files:**
- Create: `zhixia-feihualing/tests/test_donghuang_taiyi_recitation_config.sh`
- Create: `zhixia-feihualing/episodes/jiuge-donghuang-taiyi-15s/voice-lines.json`
- Create: `zhixia-feihualing/episodes/jiuge-donghuang-taiyi-15s/subtitle-plan.json`

**Interfaces:**
- Consumes: `config/voices.json` 中的 `zhixia` 音色和已确认的四句时间轴。
- Produces: `generate_episode_audio.py` 可读取的 `one-poem-story` 清单，以及字幕渲染器可读取的 `[{id,kind,text,attribution?,start,end,side}]` 数组。

- [ ] **Step 1: 写配置失败测试**

创建可执行测试 `tests/test_donghuang_taiyi_recitation_config.sh`：

```zsh
#!/bin/zsh
set -euo pipefail
project_dir=${0:A:h:h}
voice="$project_dir/episodes/jiuge-donghuang-taiyi-15s/voice-lines.json"
subtitles="$project_dir/episodes/jiuge-donghuang-taiyi-15s/subtitle-plan.json"

[[ -s "$voice" ]] || { print -u2 "FAIL: missing Donghuang Taiyi voice manifest"; exit 1; }
[[ -s "$subtitles" ]] || { print -u2 "FAIL: missing Donghuang Taiyi subtitle plan"; exit 1; }

jq -e '
  .episode == "jiuge-donghuang-taiyi-15s" and
  .format == "one-poem-story" and
  .audio_slug == "jiuge-donghuang-taiyi-15s-v01" and
  [.lines[].role] == ["zhixia","zhixia","zhixia","zhixia"] and
  [.lines[].text] == [
    "吉日兮辰良。","穆将愉兮上皇。","五音纷兮繁会。","君欣欣兮乐康。"
  ]
' "$voice" >/dev/null

jq -e '
  length == 4 and
  [.[].text] == ["吉日兮辰良","穆将愉兮上皇","五音纷兮繁会","君欣欣兮乐康"] and
  [.[].side] == ["right","left","right","left"] and
  .[0].start == 0.450 and .[0].end == 3.100 and
  .[1].start == 3.400 and .[1].end == 6.600 and
  .[2].start == 7.600 and .[2].end == 10.700 and
  .[3].start == 11.000 and .[3].end == 14.500 and
  .[0].attribution == "屈原《九歌·东皇太一》节选" and
  ([.[1,2,3].attribution // ""] | all(. == ""))
' "$subtitles" >/dev/null

print "PASS: Donghuang Taiyi recitation configuration is ready"
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `zsh zhixia-feihualing/tests/test_donghuang_taiyi_recitation_config.sh`

Expected: `FAIL: missing Donghuang Taiyi voice manifest`。

- [ ] **Step 3: 创建配音清单**

创建 `voice-lines.json`：

```json
{
  "episode": "jiuge-donghuang-taiyi-15s",
  "format": "one-poem-story",
  "theme": "九歌东皇太一十五秒四句节选朗诵",
  "theme_slug": "jiuge-donghuang-taiyi-15s",
  "audio_slug": "jiuge-donghuang-taiyi-15s-v01",
  "lines": [
    {
      "id": "01-zhixia-line-one",
      "role": "zhixia",
      "text": "吉日兮辰良。",
      "revision": 1,
      "start_ms": 450,
      "context_texts": ["这是《九歌·东皇太一》祭舞的第一句画外朗诵。保持栀夏同一固定女声，克制、低甜度、清楚并有夜间祭坛的空间感；沉静启句，‘吉日’清楚，‘辰良’从容收住。自然说诗，不念题目、作者或其他内容，不使用播音腔、吟唱、耳语或神谕式夸张。"]
    },
    {
      "id": "02-zhixia-line-two",
      "role": "zhixia",
      "text": "穆将愉兮上皇。",
      "revision": 1,
      "start_ms": 3400,
      "context_texts": ["承接‘吉日兮辰良’，保持同一位栀夏、同一距离和同一克制女声。语气略微抬起迎神气势但不高喊；‘穆将愉兮’庄重连贯，‘上皇’清楚落下。自然说诗，不念题目、作者或其他内容，不使用播音腔、吟唱或神谕式夸张。"]
    },
    {
      "id": "03-zhixia-line-three",
      "role": "zhixia",
      "text": "五音纷兮繁会。",
      "revision": 1,
      "start_ms": 7600,
      "context_texts": ["这是《九歌·东皇太一》篇末节选的第一句，前面保留一秒鼓乐换气。保持同一位栀夏克制、低甜度、有空间感的固定女声；节奏比前两句稍密但不急促，让‘五音’与‘繁会’有鼓乐汇聚感。自然说诗，不添加解释，不吟唱。"]
    },
    {
      "id": "04-zhixia-line-four",
      "role": "zhixia",
      "text": "君欣欣兮乐康。",
      "revision": 1,
      "start_ms": 11000,
      "context_texts": ["承接‘五音纷兮繁会’，保持同一位栀夏、同一空间距离和克制女声。语气舒展安定，不甜笑、不高喊；‘君欣欣兮’自然推进，‘乐康’完整、温和地收住，并在视频结束前结束。自然说诗，不添加其他内容，不吟唱。"]
    }
  ]
}
```

- [ ] **Step 4: 创建字幕计划**

创建 `subtitle-plan.json`：

```json
[
  {"id":"01-poem-line-one","kind":"poem","text":"吉日兮辰良","attribution":"屈原《九歌·东皇太一》节选","start":0.450,"end":3.100,"side":"right"},
  {"id":"02-poem-line-two","kind":"poem","text":"穆将愉兮上皇","start":3.400,"end":6.600,"side":"left"},
  {"id":"03-poem-line-three","kind":"poem","text":"五音纷兮繁会","start":7.600,"end":10.700,"side":"right"},
  {"id":"04-poem-line-four","kind":"poem","text":"君欣欣兮乐康","start":11.000,"end":14.500,"side":"left"}
]
```

- [ ] **Step 5: 运行配置测试确认通过**

Run: `zsh zhixia-feihualing/tests/test_donghuang_taiyi_recitation_config.sh`

Expected: `PASS: Donghuang Taiyi recitation configuration is ready`。

---

### Task 2: 生成并核验四句朗诵

**Files:**
- Read: `zhixia-feihualing/episodes/jiuge-donghuang-taiyi-15s/voice-lines.json`
- Create via existing pipeline: `zhixia-feihualing/assets/audio/jiuge-donghuang-taiyi-15s-v01/*.mp3`
- Create via existing pipeline: `zhixia-feihualing/assets/audio/jiuge-donghuang-taiyi-15s-v01/audio-metadata.json`
- Create via existing pipeline: `zhixia-feihualing/episodes/jiuge-donghuang-taiyi-15s/subtitles-jiuge-donghuang-taiyi-15s.json`

**Interfaces:**
- Consumes: Task 1 的 `voice-lines.json` 和 `config/voices.json` 中的 `zhixia` 音色。
- Produces: 四条可解码 MP3，文件名依次为 `01-zhixia-zhixia-line-one.mp3` 至 `04-zhixia-zhixia-line-four.mp3`。

- [ ] **Step 1: 预览生成计划**

Run:

```zsh
cd zhixia-feihualing
python3 scripts/generate_episode_audio.py --episode jiuge-donghuang-taiyi-15s
```

Expected: 待生成 4 句、预计 4 次豆包 TTS 调用、输出目录为 `assets/audio/jiuge-donghuang-taiyi-15s-v01`，且预览模式不调用接口。

- [ ] **Step 2: 生成四句音频**

确认项目 `.env` 或环境变量已提供 `VOLCENGINE_SPEECH_API_KEY`，然后运行：

```zsh
cd zhixia-feihualing
printf 'GENERATE jiuge-donghuang-taiyi-15s\n' | \
  python3 scripts/generate_episode_audio.py \
    --episode jiuge-donghuang-taiyi-15s --generate
```

Expected: `生成完成：本次生成 4 句。`；不得在输出中暴露 API Key。

- [ ] **Step 3: 核验音频资产**

Run:

```zsh
for audio in zhixia-feihualing/assets/audio/jiuge-donghuang-taiyi-15s-v01/*.mp3; do
  ffprobe -v error -select_streams a:0 \
    -show_entries stream=codec_name,sample_rate,channels \
    -show_entries format=duration -of json "$audio" | jq -e '
      .streams[0].codec_name == "mp3" and
      (.format.duration | tonumber) > 0.4 and
      (.format.duration | tonumber) < 3.5
    ' >/dev/null
done
```

Expected: 四个文件全部通过；若某句超过其时间窗，只重生该句并把对应 `revision` 增加为 2，不修改其他三句。

---

### Task 3: 动态左右竖排字幕卡

**Files:**
- Create: `zhixia-feihualing/tests/test_donghuang_taiyi_subtitle_cards.sh`
- Create: `zhixia-feihualing/scripts/render_jiuge_vertical_subtitle_cards.swift`
- Create at build time: `zhixia-feihualing/assets/subtitles/jiuge-donghuang-taiyi-15s/*.png`

**Interfaces:**
- Consumes: Task 1 的 `subtitle-plan.json`。
- Produces: 四张 1080×1920 RGBA PNG；`side=right` 时主字中心 `x=872`，`side=left` 时主字中心 `x=168`。

- [ ] **Step 1: 写字幕卡失败测试**

创建可执行测试：

```zsh
#!/bin/zsh
set -euo pipefail
project_dir=${0:A:h:h}
renderer="$project_dir/scripts/render_jiuge_vertical_subtitle_cards.swift"
manifest="$project_dir/episodes/jiuge-donghuang-taiyi-15s/subtitle-plan.json"
output_dir=$(mktemp -d /tmp/zhixia-jiuge-cards.XXXXXX)
trap 'rm -rf "$output_dir"' EXIT

[[ -s "$renderer" ]] || { print -u2 "FAIL: missing Jiuge subtitle renderer"; exit 1; }
export CLANG_MODULE_CACHE_PATH="$output_dir/clang-cache"
export SWIFT_MODULECACHE_PATH="$output_dir/swift-cache"
swift "$renderer" "$manifest" "$output_dir"
[[ "$(find "$output_dir" -maxdepth 1 -name '*.png' -type f | wc -l | tr -d ' ')" == "4" ]]
for card in "$output_dir"/*.png; do
  properties=$(sips -g pixelWidth -g pixelHeight -g format "$card")
  print -r -- "$properties" | rg -q 'pixelWidth: 1080'
  print -r -- "$properties" | rg -q 'pixelHeight: 1920'
  print -r -- "$properties" | rg -q 'format: png'
  ffmpeg -v error -i "$card" -f null -
done
print "PASS: Donghuang Taiyi subtitle cards are ready"
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `zsh zhixia-feihualing/tests/test_donghuang_taiyi_subtitle_cards.sh`

Expected: `FAIL: missing Jiuge subtitle renderer`。

- [ ] **Step 3: 实现专用 Swift 渲染器**

创建 `render_jiuge_vertical_subtitle_cards.swift`；画布透明，字体加载、边位取值或 PNG 编码失败时退出非零：

```swift
import AppKit
import CoreText
import Foundation

struct Subtitle: Decodable {
    let id: String
    let kind: String
    let text: String
    let attribution: String?
    let side: String
}

let width: CGFloat = 1080
let height: CGFloat = 1920
let poemIvory = NSColor(calibratedRed: 0.94, green: 0.89, blue: 0.79, alpha: 1)
let oldGold = NSColor(calibratedRed: 0.48, green: 0.37, blue: 0.22, alpha: 0.92)

enum RenderError: Error {
    case usage, unavailableFont, invalidSide, bitmapCreation, pngEncoding
}

func attributes(font: NSFont, color: NSColor) -> [NSAttributedString.Key: Any] {
    let shadow = NSShadow()
    shadow.shadowColor = NSColor(calibratedWhite: 0.01, alpha: 0.68)
    shadow.shadowBlurRadius = 7
    shadow.shadowOffset = NSSize(width: 2, height: -2)
    return [.font: font, .foregroundColor: color, .strokeColor: oldGold,
            .strokeWidth: -1.2, .shadow: shadow]
}

func drawVertical(_ text: String, x: CGFloat, top: CGFloat,
                  step: CGFloat, font: NSFont, color: NSColor) {
    for (index, character) in text.enumerated() {
        let glyph = NSAttributedString(string: String(character),
            attributes: attributes(font: font, color: color))
        let size = glyph.size()
        let screenY = top + CGFloat(index) * step
        glyph.draw(in: NSRect(x: x - size.width / 2,
                             y: height - screenY - size.height,
                             width: size.width + 12, height: size.height + 12))
    }
}

func render(_ item: Subtitle, poemFont: NSFont, creditFont: NSFont, to url: URL) throws {
    let mainX: CGFloat
    let creditX: CGFloat
    switch item.side {
    case "right": mainX = 872; creditX = 994
    case "left": mainX = 168; creditX = 64
    default: throw RenderError.invalidSide
    }
    guard let bitmap = NSBitmapImageRep(
        bitmapDataPlanes: nil, pixelsWide: Int(width), pixelsHigh: Int(height),
        bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false,
        colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0
    ), let context = NSGraphicsContext(bitmapImageRep: bitmap) else {
        throw RenderError.bitmapCreation
    }
    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.current = context
    NSColor.clear.setFill()
    NSRect(x: 0, y: 0, width: width, height: height).fill()
    drawVertical(item.text, x: mainX, top: 245, step: 94,
                 font: poemFont, color: poemIvory)
    if let attribution = item.attribution {
        drawVertical(attribution, x: creditX, top: 250, step: 38,
                     font: creditFont, color: poemIvory)
    }
    NSGraphicsContext.restoreGraphicsState()
    guard let png = bitmap.representation(using: .png, properties: [:]) else {
        throw RenderError.pngEncoding
    }
    try png.write(to: url, options: .atomic)
}

do {
    guard CommandLine.arguments.count == 3 else { throw RenderError.usage }
    let manifestURL = URL(fileURLWithPath: CommandLine.arguments[1])
    let outputURL = URL(fileURLWithPath: CommandLine.arguments[2], isDirectory: true)
    let fontURL = URL(fileURLWithPath: "/System/Library/AssetsV2/com_apple_MobileAsset_Font7/54a2ad3dac6cac875ad675d7d273dc425010a877.asset/AssetData/Kaiti.ttc")
    CTFontManagerRegisterFontsForURL(fontURL as CFURL, .process, nil)
    guard let poemFont = NSFont(name: "STKaitiSC-Regular", size: 82),
          let creditFont = NSFont(name: "STKaitiSC-Regular", size: 30) else {
        throw RenderError.unavailableFont
    }
    let items = try JSONDecoder().decode([Subtitle].self, from: Data(contentsOf: manifestURL))
    try FileManager.default.createDirectory(at: outputURL, withIntermediateDirectories: true)
    for item in items {
        try render(item, poemFont: poemFont, creditFont: creditFont,
                   to: outputURL.appendingPathComponent("\(item.id).png"))
    }
} catch {
    FileHandle.standardError.write(Data("error: \(error)\n".utf8))
    exit(1)
}
```

- [ ] **Step 4: 运行字幕卡测试确认通过**

Run: `zsh zhixia-feihualing/tests/test_donghuang_taiyi_subtitle_cards.sh`

Expected: `PASS: Donghuang Taiyi subtitle cards are ready`。

---

### Task 4: 混音、字幕与高清成片

**Files:**
- Create: `zhixia-feihualing/tests/test_donghuang_taiyi_15s_final.sh`
- Create: `zhixia-feihualing/scripts/build_donghuang_taiyi_15s_final.sh`
- Create: `zhixia-feihualing/exports/jiuge-donghuang-taiyi-15s-voiced-v01.mp4`
- Create: `zhixia-feihualing/exports/jiuge-donghuang-taiyi-15s-subtitled-v01.mp4`

**Interfaces:**
- Consumes: 原片、四条 MP3、字幕计划、Task 3 渲染器。
- Produces: 同音轨的无字幕朗诵试听版和正式字幕版。

- [ ] **Step 1: 写最终成片失败测试**

创建测试，检查构建器存在、四条音频存在、四张字幕卡生成、两份输出参数正确、两份 AAC 裸流哈希一致：

```zsh
#!/bin/zsh
set -euo pipefail
project_dir=${0:A:h:h}
builder="$project_dir/scripts/build_donghuang_taiyi_15s_final.sh"
audio_dir="$project_dir/assets/audio/jiuge-donghuang-taiyi-15s-v01"
cards_dir="$project_dir/assets/subtitles/jiuge-donghuang-taiyi-15s"
voiced="$project_dir/exports/jiuge-donghuang-taiyi-15s-voiced-v01.mp4"
final="$project_dir/exports/jiuge-donghuang-taiyi-15s-subtitled-v01.mp4"

[[ -x "$builder" ]] || { print -u2 "FAIL: missing executable Donghuang Taiyi builder"; exit 1; }
for name in 01-zhixia-zhixia-line-one.mp3 02-zhixia-zhixia-line-two.mp3 03-zhixia-zhixia-line-three.mp3 04-zhixia-zhixia-line-four.mp3; do
  [[ -s "$audio_dir/$name" ]] || { print -u2 "FAIL: missing voice asset $name"; exit 1; }
done
"$builder" >/dev/null
[[ "$(find "$cards_dir" -maxdepth 1 -name '*.png' -type f | wc -l | tr -d ' ')" == "4" ]]

for output in "$voiced" "$final"; do
  probe=$(ffprobe -v error -show_entries stream=codec_type,codec_name,width,height,r_frame_rate,sample_rate,channels -show_entries format=duration -of json "$output")
  print -r -- "$probe" | jq -e '
    ([.streams[] | select(.codec_type == "video")][0]) as $v |
    ([.streams[] | select(.codec_type == "audio")][0]) as $a |
    $v.codec_name == "h264" and $v.width == 1080 and $v.height == 1920 and
    $v.r_frame_rate == "24/1" and $a.codec_name == "aac" and
    $a.sample_rate == "48000" and $a.channels == 2 and
    (.format.duration | tonumber) >= 15.0 and (.format.duration | tonumber) <= 15.2
  ' >/dev/null
  ffmpeg -v error -i "$output" -f null -
done

hash_dir=$(mktemp -d /tmp/zhixia-donghuang-audio-hash.XXXXXX)
trap 'rm -rf "$hash_dir"' EXIT
ffmpeg -v error -i "$voiced" -map 0:a:0 -c copy -f adts "$hash_dir/voiced.aac"
ffmpeg -v error -i "$final" -map 0:a:0 -c copy -f adts "$hash_dir/final.aac"
[[ "$(shasum -a 256 "$hash_dir/voiced.aac" | awk '{print $1}')" == "$(shasum -a 256 "$hash_dir/final.aac" | awk '{print $1}')" ]]
print "PASS: Donghuang Taiyi recitation subtitle finals are ready"
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `zsh zhixia-feihualing/tests/test_donghuang_taiyi_15s_final.sh`

Expected: `FAIL: missing executable Donghuang Taiyi builder`。

- [ ] **Step 3: 实现构建脚本**

创建 `build_donghuang_taiyi_15s_final.sh`：

```zsh
#!/bin/zsh
set -euo pipefail
project_dir=${0:A:h:h}
source_video="$project_dir/episodes/jiuge-donghuang-taiyi-15s/assets/video/content-raw-v01.mp4"
audio_dir="$project_dir/assets/audio/jiuge-donghuang-taiyi-15s-v01"
manifest="$project_dir/episodes/jiuge-donghuang-taiyi-15s/subtitle-plan.json"
renderer="$project_dir/scripts/render_jiuge_vertical_subtitle_cards.swift"
cards_dir="$project_dir/assets/subtitles/jiuge-donghuang-taiyi-15s"
voiced="$project_dir/exports/jiuge-donghuang-taiyi-15s-voiced-v01.mp4"
final="$project_dir/exports/jiuge-donghuang-taiyi-15s-subtitled-v01.mp4"
build_dir=$(mktemp -d /tmp/zhixia-donghuang-final.XXXXXX)
trap 'rm -rf "$build_dir"' EXIT

duration=$(ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 "$source_video")
line_one="$audio_dir/01-zhixia-zhixia-line-one.mp3"
line_two="$audio_dir/02-zhixia-zhixia-line-two.mp3"
line_three="$audio_dir/03-zhixia-zhixia-line-three.mp3"
line_four="$audio_dir/04-zhixia-zhixia-line-four.mp3"
for required in "$source_video" "$line_one" "$line_two" "$line_three" "$line_four" "$manifest" "$renderer"; do
  [[ -s "$required" ]] || { print -u2 -r -- "missing required input: $required"; exit 1; }
done
mkdir -p "$cards_dir" "$project_dir/exports"
find "$cards_dir" -maxdepth 1 -name '*.png' -type f -delete
export CLANG_MODULE_CACHE_PATH="$build_dir/clang-cache"
export SWIFT_MODULECACHE_PATH="$build_dir/swift-cache"
swift "$renderer" "$manifest" "$cards_dir"

ffmpeg -hide_banner -loglevel error -y \
  -i "$source_video" -i "$line_one" -i "$line_two" -i "$line_three" -i "$line_four" \
  -filter_complex "\
    [0:v]scale=-2:1920:flags=lanczos+accurate_rnd+full_chroma_int,\
      crop=1080:1920:(iw-1080)/2:0,hqdn3d=0.45:0.45:1.35:1.35,\
      unsharp=5:5:0.16:3:3:0,fps=24,format=yuv420p[vout];\
    [1:a]silenceremove=start_periods=1:start_duration=0.05:start_threshold=-42dB,\
      areverse,silenceremove=start_periods=1:start_duration=0.05:start_threshold=-42dB,areverse,\
      asetpts=PTS-STARTPTS,afade=t=in:st=0:d=0.04,apad,atrim=0:2.650,\
      aresample=48000,aformat=channel_layouts=stereo,adelay=450|450[a1];\
    [2:a]silenceremove=start_periods=1:start_duration=0.05:start_threshold=-42dB,\
      areverse,silenceremove=start_periods=1:start_duration=0.05:start_threshold=-42dB,areverse,\
      asetpts=PTS-STARTPTS,afade=t=in:st=0:d=0.04,apad,atrim=0:3.200,\
      aresample=48000,aformat=channel_layouts=stereo,adelay=3400|3400[a2];\
    [3:a]silenceremove=start_periods=1:start_duration=0.05:start_threshold=-42dB,\
      areverse,silenceremove=start_periods=1:start_duration=0.05:start_threshold=-42dB,areverse,\
      asetpts=PTS-STARTPTS,afade=t=in:st=0:d=0.04,apad,atrim=0:3.100,\
      aresample=48000,aformat=channel_layouts=stereo,adelay=7600|7600[a3];\
    [4:a]silenceremove=start_periods=1:start_duration=0.05:start_threshold=-42dB,\
      areverse,silenceremove=start_periods=1:start_duration=0.05:start_threshold=-42dB,areverse,\
      asetpts=PTS-STARTPTS,afade=t=in:st=0:d=0.04,apad,atrim=0:3.500,\
      aresample=48000,aformat=channel_layouts=stereo,adelay=11000|11000[a4];\
    [a1][a2][a3][a4]amix=inputs=4:duration=longest:dropout_transition=0:normalize=0,\
      highpass=f=90,equalizer=f=2500:t=q:w=1.0:g=1.4,\
      acompressor=threshold=0.08:ratio=2:attack=12:release=150:makeup=1.25,\
      loudnorm=I=-18:TP=-3:LRA=7,apad,atrim=0:${duration},asplit=2[voice_side][voice_mix];\
    [0:a]aresample=48000,aformat=channel_layouts=stereo[bed];\
    [bed][voice_side]sidechaincompress=threshold=0.025:ratio=1.8:attack=70:release=350[ducked];\
    [ducked][voice_mix]amix=inputs=2:duration=first:dropout_transition=0:normalize=0,\
      alimiter=limit=0.870964:attack=5:release=80:level=false[aout]" \
  -map "[vout]" -map "[aout]" -t "$duration" \
  -c:v libx264 -preset slow -crf 17 -pix_fmt yuv420p \
  -c:a aac -b:a 192k -ar 48000 -ac 2 -movflags +faststart "$voiced"

ffmpeg -hide_banner -loglevel error -y \
  -i "$voiced" \
  -loop 1 -framerate 24 -i "$cards_dir/01-poem-line-one.png" \
  -loop 1 -framerate 24 -i "$cards_dir/02-poem-line-two.png" \
  -loop 1 -framerate 24 -i "$cards_dir/03-poem-line-three.png" \
  -loop 1 -framerate 24 -i "$cards_dir/04-poem-line-four.png" \
  -filter_complex "\
    [1:v]format=rgba,fade=t=in:st=0.450:d=0.120:alpha=1,fade=t=out:st=2.980:d=0.120:alpha=1[c1];\
    [2:v]format=rgba,fade=t=in:st=3.400:d=0.120:alpha=1,fade=t=out:st=6.480:d=0.120:alpha=1[c2];\
    [3:v]format=rgba,fade=t=in:st=7.600:d=0.120:alpha=1,fade=t=out:st=10.580:d=0.120:alpha=1[c3];\
    [4:v]format=rgba,fade=t=in:st=11.000:d=0.120:alpha=1,fade=t=out:st=14.380:d=0.120:alpha=1[c4];\
    [0:v][c1]overlay=eof_action=pass:enable='between(t,0.450,3.100)'[v1];\
    [v1][c2]overlay=eof_action=pass:enable='between(t,3.400,6.600)'[v2];\
    [v2][c3]overlay=eof_action=pass:enable='between(t,7.600,10.700)'[v3];\
    [v3][c4]overlay=eof_action=pass:enable='between(t,11.000,14.500)',format=yuv420p[vout]" \
  -map "[vout]" -map 0:a:0 -t "$duration" \
  -c:v libx264 -preset slow -crf 17 -pix_fmt yuv420p \
  -c:a copy -movflags +faststart "$final"

print -r -- "$voiced"
print -r -- "$final"
```

不得使用硬切 `volume=...enable=between(...)` 代替脚本中的平滑侧链。

- [ ] **Step 4: 运行最终测试确认通过**

Run: `zsh zhixia-feihualing/tests/test_donghuang_taiyi_15s_final.sh`

Expected: `PASS: Donghuang Taiyi recitation subtitle finals are ready`。

---

### Task 5: 视听验收与归档

**Files:**
- Inspect: `zhixia-feihualing/exports/jiuge-donghuang-taiyi-15s-voiced-v01.mp4`
- Inspect: `zhixia-feihualing/exports/jiuge-donghuang-taiyi-15s-subtitled-v01.mp4`
- Modify if required: `zhixia-feihualing/episodes/jiuge-donghuang-taiyi-15s/qa-notes.md`

**Interfaces:**
- Consumes: Task 4 两份成片。
- Produces: 经人工视听与自动验证的正式发布文件和可复现构建流程。

- [ ] **Step 1: 抽取字幕验收接触表**

分别在 1.5、4.8、8.9、12.4 秒抽帧，生成 2×2 接触表并检查：文字准确，右、左、右、左切换成立，不遮脸、手势、躯干中心或右下角标识。

- [ ] **Step 2: 播放试听版并检查声音**

重点听四句是否同一声线、第三句前的一秒留白是否自然、“乐康”是否在 14.500 秒前收住；检查原鼓乐在人声出现时只轻度后退，句间无抽吸。

- [ ] **Step 3: 运行最终验证**

Run:

```zsh
zsh zhixia-feihualing/tests/test_donghuang_taiyi_recitation_config.sh
zsh zhixia-feihualing/tests/test_donghuang_taiyi_subtitle_cards.sh
zsh zhixia-feihualing/tests/test_donghuang_taiyi_15s_final.sh
git diff --check
```

Expected: 三个测试均 PASS，`git diff --check` 无输出。

- [ ] **Step 4: 记录结果并提交**

只暂存本任务新增的设计配置、渲染器、构建器、测试和必要 QA 记录；音频、字幕卡与成片按项目 `.gitignore` 留在本地归档。提交信息：

```bash
git commit -m "制作九歌东皇太一朗诵字幕成片"
```
