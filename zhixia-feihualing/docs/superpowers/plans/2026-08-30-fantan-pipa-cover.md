# 《月照反弹琵琶》封面 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 从《月照反弹琵琶》无字幕高清配音版 1.250 秒精确截帧，制作带系列化竖排标题的 1080×1920 正式发布封面。

**Architecture:** 构建脚本负责输入校验、精确截帧和调用渲染器；Swift/AppKit 渲染器只在原始帧上绘制确定性文字。Shell 测试先验证缺失实现时会失败，再构建封面并检查 PNG 规格、不透明度、关键文案与资产登记。

**Tech Stack:** zsh、FFmpeg/ffprobe、Swift、AppKit、CoreText、PNG、CSV。

## Global Constraints

- 唯一底图为 `exports/fantan-pipa-15s-voiced-v01.mp4` 的 1.250 秒帧，不从烧录字幕成片取帧。
- 输出固定为 `exports/fantan-pipa-dance-cover-v01.png`，1080×1920，无透明像素。
- 左侧竖排双列为小字“栀夏”和大字“月照反弹琵琶”，题署为“唐·王昌龄《从军行七首·其二》”。
- 文字延续上一支封面的暖象牙白行楷、楷体和轻微深色柔影，不遮挡脸、躯干、上举手臂、抬起腿部、主要飘带或右下角 AI 标识。
- 不调用图片生成，不重绘人物，不改变画面、调色、服装、飘带、长城或满月，不加入琵琶、完整诗句、标签、额外水印和边框。
- 只提交本次封面脚本、测试、计划和资产记录，保留工作区其他改动。

---

### Task 1: 建立失败测试

**Files:**
- Create: `zhixia-feihualing/tests/test_fantan_pipa_dance_cover.sh`
- Test: `zhixia-feihualing/exports/fantan-pipa-dance-cover-v01.png`

**Interfaces:**
- Consumes: 已存在的无字幕高清配音版、预期构建脚本、渲染器和资产清单路径。
- Produces: 一个可执行验收入口，验证构建、关键文字、PNG 规格、完全不透明和资产清单记录。

- [ ] **Step 1: 写失败测试**

```zsh
#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
source_video="$project_dir/exports/fantan-pipa-15s-voiced-v01.mp4"
builder="$project_dir/scripts/build_fantan_pipa_dance_cover.sh"
renderer="$project_dir/scripts/render_fantan_pipa_dance_cover.swift"
output="$project_dir/exports/fantan-pipa-dance-cover-v01.png"
inventory="$project_dir/assets/inventory.csv"

for required in "$source_video" "$builder" "$renderer" "$inventory"; do
  [[ -s "$required" ]] || { print -u2 -r -- "FAIL: missing required Fantan Pipa cover component $required"; exit 1; }
done

[[ -x "$builder" ]] || { print -u2 "FAIL: Fantan Pipa cover builder is not executable"; exit 1; }
rg -qF 'drawVertical("栀夏"' "$renderer" || { print -u2 "FAIL: renderer lacks 栀夏 label"; exit 1; }
rg -qF 'drawVertical("月照反弹琵琶"' "$renderer" || { print -u2 "FAIL: renderer lacks 月照反弹琵琶 title"; exit 1; }
rg -qF 'drawVertical("唐·王昌龄《从军行七首·其二》"' "$renderer" || { print -u2 "FAIL: renderer lacks poem attribution"; exit 1; }

"$builder" >/dev/null
[[ -s "$output" ]] || { print -u2 "FAIL: Fantan Pipa cover was not generated"; exit 1; }

media_spec="$(ffprobe -v error -select_streams v:0 -show_entries stream=codec_name,width,height -of default=noprint_wrappers=1 "$output")"
[[ "$media_spec" == *"codec_name=png"* ]] || { print -u2 "FAIL: cover codec is not PNG"; exit 1; }
[[ "$media_spec" == *"width=1080"* ]] || { print -u2 "FAIL: cover width is not 1080"; exit 1; }
[[ "$media_spec" == *"height=1920"* ]] || { print -u2 "FAIL: cover height is not 1920"; exit 1; }

ffmpeg -v error -i "$output" -frames:v 1 -f null -
alpha_min="$(ffmpeg -hide_banner -loglevel error -i "$output" -vf "alphaextract,signalstats,metadata=print:file=-" -frames:v 1 -f null - | awk -F= '/lavfi.signalstats.YMIN/ { print $2; exit }')"
[[ "$alpha_min" == "255" ]] || { print -u2 "FAIL: cover contains transparent pixels"; exit 1; }

rg -qF "fantan-pipa-dance-cover-v01" "$inventory" || { print -u2 "FAIL: Fantan Pipa cover is not registered in asset inventory"; exit 1; }
print -r -- "PASS: Fantan Pipa dance cover is valid, 1080x1920, and inventoried"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd zhixia-feihualing && zsh tests/test_fantan_pipa_dance_cover.sh`

Expected: FAIL，报告缺少 `build_fantan_pipa_dance_cover.sh`，而不是语法错误。

### Task 2: 实现确定性封面渲染

**Files:**
- Create: `zhixia-feihualing/scripts/build_fantan_pipa_dance_cover.sh`
- Create: `zhixia-feihualing/scripts/render_fantan_pipa_dance_cover.swift`
- Create: `zhixia-feihualing/exports/fantan-pipa-dance-cover-v01.png`

**Interfaces:**
- Consumes: `exports/fantan-pipa-15s-voiced-v01.mp4` 中 1.250 秒的 1080×1920 帧。
- Produces: `render_fantan_pipa_dance_cover.swift <base.png> <output.png>` 和无透明底的正式 PNG。

- [ ] **Step 1: 写最小构建脚本**

```zsh
#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
source_video="$project_dir/exports/fantan-pipa-15s-voiced-v01.mp4"
renderer="$project_dir/scripts/render_fantan_pipa_dance_cover.swift"
output="$project_dir/exports/fantan-pipa-dance-cover-v01.png"
build_dir="$(mktemp -d /tmp/zhixia-fantan-pipa-cover.XXXXXX)"
base="$build_dir/base.png"
trap 'rm -rf "$build_dir"' EXIT

for required in "$source_video" "$renderer"; do
  [[ -s "$required" ]] || { print -u2 -r -- "missing required Fantan Pipa cover component: $required"; exit 1; }
done

mkdir -p "${output:h}"
ffmpeg -hide_banner -loglevel error -y -ss 1.250 -i "$source_video" -frames:v 1 -vf "format=rgb24" "$base"
export CLANG_MODULE_CACHE_PATH="$build_dir/clang-module-cache"
export SWIFT_MODULECACHE_PATH="$build_dir/swift-module-cache"
swift "$renderer" "$base" "$output"
print -r -- "$output"
```

- [ ] **Step 2: 写本地文字渲染器**

创建以下完整渲染器；它只注册本地字体、原样绘制底图并叠加三列竖排文字：

```swift
#!/usr/bin/env swift

import AppKit
import CoreText
import Foundation

enum CoverError: Error, CustomStringConvertible {
    case usage, invalidImage, unavailableFont, bitmapCreation, pngEncoding

    var description: String {
        switch self {
        case .usage: return "usage: render_fantan_pipa_dance_cover.swift <base.png> <output.png>"
        case .invalidImage: return "unable to load Fantan Pipa cover base image"
        case .unavailableFont: return "required Chinese fonts are unavailable"
        case .bitmapCreation: return "unable to create cover bitmap"
        case .pngEncoding: return "unable to encode cover PNG"
        }
    }
}

let width: CGFloat = 1080
let height: CGFloat = 1920
let titleIvory = NSColor(calibratedRed: 0.97, green: 0.92, blue: 0.82, alpha: 1)
let quietIvory = NSColor(calibratedRed: 0.91, green: 0.86, blue: 0.76, alpha: 0.96)

func attributes(font: NSFont, color: NSColor, blur: CGFloat) -> [NSAttributedString.Key: Any] {
    let shadow = NSShadow()
    shadow.shadowColor = NSColor(calibratedWhite: 0.02, alpha: 0.72)
    shadow.shadowBlurRadius = blur
    shadow.shadowOffset = NSSize(width: 2, height: -2)
    return [.font: font, .foregroundColor: color, .shadow: shadow]
}

func drawVertical(_ text: String, x: CGFloat, top: CGFloat, step: CGFloat, font: NSFont, color: NSColor) {
    for (index, character) in text.enumerated() {
        let glyph = NSAttributedString(
            string: String(character),
            attributes: attributes(font: font, color: color, blur: 6)
        )
        let size = glyph.size()
        let yFromTop = top + CGFloat(index) * step
        glyph.draw(in: NSRect(
            x: x - size.width / 2,
            y: height - yFromTop - size.height,
            width: size.width + 12,
            height: size.height + 12
        ))
    }
}

do {
    guard CommandLine.arguments.count == 3 else { throw CoverError.usage }
    let baseURL = URL(fileURLWithPath: CommandLine.arguments[1])
    let outputURL = URL(fileURLWithPath: CommandLine.arguments[2])
    guard let base = NSImage(contentsOf: baseURL) else { throw CoverError.invalidImage }

    let xingkaiURL = URL(fileURLWithPath: "/System/Library/AssetsV2/com_apple_MobileAsset_Font7/aa99d0b2bad7f797f38b49d46cde28fd4b58876e.asset/AssetData/Xingkai.ttc")
    let kaitiURL = URL(fileURLWithPath: "/System/Library/AssetsV2/com_apple_MobileAsset_Font7/54a2ad3dac6cac875ad675d7d273dc425010a877.asset/AssetData/Kaiti.ttc")
    CTFontManagerRegisterFontsForURL(xingkaiURL as CFURL, .process, nil)
    CTFontManagerRegisterFontsForURL(kaitiURL as CFURL, .process, nil)

    guard let titleFont = NSFont(name: "STXingkaiSC-Bold", size: 78),
          let nameFont = NSFont(name: "STKaitiSC-Regular", size: 46),
          let creditFont = NSFont(name: "STKaitiSC-Regular", size: 29) else {
        throw CoverError.unavailableFont
    }

    guard let bitmap = NSBitmapImageRep(
        bitmapDataPlanes: nil,
        pixelsWide: Int(width),
        pixelsHigh: Int(height),
        bitsPerSample: 8,
        samplesPerPixel: 4,
        hasAlpha: true,
        isPlanar: false,
        colorSpaceName: .deviceRGB,
        bytesPerRow: 0,
        bitsPerPixel: 0
    ), let context = NSGraphicsContext(bitmapImageRep: bitmap) else {
        throw CoverError.bitmapCreation
    }

    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.current = context
    base.draw(in: NSRect(x: 0, y: 0, width: width, height: height))

drawVertical("栀夏", x: 96, top: 250, step: 62, font: nameFont, color: quietIvory)
drawVertical("月照反弹琵琶", x: 218, top: 232, step: 102, font: titleFont, color: titleIvory)
drawVertical("唐·王昌龄《从军行七首·其二》", x: 342, top: 700, step: 38, font: creditFont, color: quietIvory)

    NSGraphicsContext.restoreGraphicsState()

    guard let png = bitmap.representation(using: .png, properties: [:]) else {
        throw CoverError.pngEncoding
    }
    try FileManager.default.createDirectory(at: outputURL.deletingLastPathComponent(), withIntermediateDirectories: true)
    try png.write(to: outputURL, options: .atomic)
} catch {
    FileHandle.standardError.write(Data("error: \(error)\n".utf8))
    exit(1)
}
```

- [ ] **Step 3: 赋予构建脚本执行权限并运行测试**

Run:

```bash
chmod +x zhixia-feihualing/scripts/build_fantan_pipa_dance_cover.sh zhixia-feihualing/tests/test_fantan_pipa_dance_cover.sh
cd zhixia-feihualing && zsh tests/test_fantan_pipa_dance_cover.sh
```

Expected: PNG 媒体检查通过，仅因资产清单尚无 `fantan-pipa-dance-cover-v01` 而失败。

### Task 3: 视觉验收与归档

**Files:**
- Modify: `zhixia-feihualing/assets/inventory.csv`
- Modify: `zhixia-feihualing/docs/superpowers/plans/2026-08-30-fantan-pipa-cover.md`

**Interfaces:**
- Consumes: Task 2 的正式封面。
- Produces: 视觉确认、唯一资产记录和可重复验证的正式交付。

- [ ] **Step 1: 查看原尺寸封面**

使用本地原尺寸预览检查：栀夏侧脸、高抬腿、反弓、上举手臂和蓝橙飘带完整；满月与长城可辨；三组文字未遮挡人物或 AI 标识；不存在诗句字幕残留、乱码、边框、琵琶或新增图像元素。

- [ ] **Step 2: 若文字遮挡，仅调整三列坐标**

只允许修改 `x`、`top`、`step` 和既有字号；重新运行构建脚本并再次原尺寸预览。不得修改取帧时间、底图内容或调用图像生成。

- [ ] **Step 3: 登记资产清单**

向 `assets/inventory.csv` 新增唯一 ID `fantan-pipa-dance-cover-v01`；备注写明“1080×1920；取自无字幕配音版 1.250 秒；左侧竖排栀夏与月照反弹琵琶；附唐·王昌龄《从军行七首·其二》题署；保留 AI 生成标识；无图像模型重绘”。

- [ ] **Step 4: 运行最终验证**

Run:

```bash
cd zhixia-feihualing
zsh tests/test_fantan_pipa_dance_cover.sh
ffmpeg -v error -i exports/fantan-pipa-dance-cover-v01.png -frames:v 1 -f null -
awk -F, 'NF != 9 { print NR ":" NF; bad=1 } END { exit bad }' assets/inventory.csv
test "$(rg -c '^fantan-pipa-dance-cover-v01,' assets/inventory.csv)" = "1"
git diff --check
```

Expected: 专用测试输出 PASS；PNG 解码无错误；CSV 每行九列；资产 ID 唯一；差异检查无错误。

- [ ] **Step 5: 提交封面**

只暂存本次脚本、渲染器、测试、计划和资产清单中的本次记录，使用中文提交：

```bash
git commit -m '制作月照反弹琵琶封面'
```
