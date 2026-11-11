import AppKit

let args = CommandLine.arguments
guard args.count == 3, let source = NSImage(contentsOfFile: args[1]) else {
    fputs("Usage: render_zhixia_profile_masterboard_v04.swift input.png output.png\n", stderr)
    exit(2)
}

let size = source.size
let canvas = NSImage(size: size)
let scale = size.width / 1021.0

func topRect(_ x: CGFloat, _ y: CGFloat, _ width: CGFloat, _ height: CGFloat) -> NSRect {
    NSRect(x: x * scale, y: size.height - (y + height) * scale, width: width * scale, height: height * scale)
}

let rose = NSColor(calibratedRed: 0.63, green: 0.40, blue: 0.43, alpha: 1)
let ink = NSColor(calibratedRed: 0.28, green: 0.27, blue: 0.27, alpha: 1)
let subInk = NSColor(calibratedRed: 0.45, green: 0.41, blue: 0.40, alpha: 1)
let fontName = "PingFang SC"

func attrs(_ fontSize: CGFloat, _ weight: NSFont.Weight = .regular, _ color: NSColor = ink, _ tracking: CGFloat = 0) -> [NSAttributedString.Key: Any] {
    [
        .font: NSFont(name: fontName, size: fontSize * scale) ?? NSFont.systemFont(ofSize: fontSize * scale, weight: weight),
        .foregroundColor: color,
        .kern: tracking * scale
    ]
}

func draw(_ string: String, x: CGFloat, y: CGFloat, width: CGFloat, height: CGFloat, fontSize: CGFloat, weight: NSFont.Weight = .regular, color: NSColor = ink, tracking: CGFloat = 0, wrap: Bool = false) {
    let options: NSString.DrawingOptions = wrap ? [.usesLineFragmentOrigin, .usesFontLeading] : []
    (string as NSString).draw(with: topRect(x, y, width, height), options: options, attributes: attrs(fontSize, weight, color, tracking), context: nil)
}

func clear(_ x: CGFloat, _ y: CGFloat, _ width: CGFloat, _ height: CGFloat) {
    NSColor(calibratedWhite: 1.0, alpha: 1.0).setFill()
    topRect(x, y, width, height).fill()
}

func rule(_ x1: CGFloat, _ y1: CGFloat, _ x2: CGFloat, _ y2: CGFloat) {
    let path = NSBezierPath()
    path.move(to: NSPoint(x: x1 * scale, y: size.height - y1 * scale))
    path.line(to: NSPoint(x: x2 * scale, y: size.height - y2 * scale))
    NSColor(calibratedRed: 0.76, green: 0.57, blue: 0.59, alpha: 0.42).setStroke()
    path.lineWidth = 0.7 * scale
    path.stroke()
}

func drawChip(_ x: CGFloat, _ y: CGFloat, _ width: CGFloat, _ height: CGFloat) {
    let box = NSBezierPath(roundedRect: topRect(x, y, width, height), xRadius: 4 * scale, yRadius: 4 * scale)
    NSColor(calibratedWhite: 1.0, alpha: 0.35).setFill()
    box.fill()
    NSColor(calibratedRed: 0.76, green: 0.57, blue: 0.59, alpha: 0.34).setStroke()
    box.lineWidth = 0.65 * scale
    box.stroke()
}

canvas.lockFocus()
source.draw(in: NSRect(origin: .zero, size: size))

// Remove AI-rendered copy while preserving the confirmed saturated artwork.
// Exact typography is redrawn below.
clear(23, 25, 760, 235)
clear(802, 35, 145, 188)
clear(20, 315, 174, 640)
clear(244, 315, 160, 46)
clear(270, 893, 420, 30)
clear(706, 315, 174, 46)
for point in [(706.0, 519.0), (858.0, 519.0), (706.0, 725.0), (858.0, 725.0), (706.0, 931.0), (858.0, 931.0)] {
    clear(CGFloat(point.0), CGFloat(point.1), 145, 22)
}
clear(20, 960, 318, 44)
clear(364, 960, 162, 44)
clear(538, 960, 260, 44)
clear(811, 960, 188, 44)
clear(20, 1254, 320, 34)
clear(365, 1252, 82, 36)
clear(874, 1004, 130, 196)
clear(18, 1300, 987, 227)

// Restore guide rules erased together with the bad copy.
rule(25, 382, 190, 382)
rule(25, 462, 190, 462)
rule(25, 538, 190, 538)
rule(25, 604, 190, 604)
rule(25, 675, 190, 675)
rule(25, 757, 190, 757)
rule(25, 837, 190, 837)
rule(15, 1302, 1006, 1302)
rule(375, 1302, 375, 1530)
rule(698, 1302, 698, 1530)

// Header identity.
draw("ZHI XIA", x: 38, y: 32, width: 540, height: 78, fontSize: 58, weight: .light, color: rose, tracking: 2.2)
draw("栀夏", x: 42, y: 111, width: 270, height: 61, fontSize: 48, weight: .light, color: rose, tracking: 4)
draw("在诗与风之间，她是温柔而坚定的光。", x: 43, y: 185, width: 640, height: 28, fontSize: 18, weight: .regular, color: rose, tracking: 1.1)
draw("IN POETRY AND WIND, SHE IS A GENTLE, STEADFAST LIGHT.", x: 45, y: 224, width: 690, height: 18, fontSize: 8.5, weight: .regular, color: rose, tracking: 1.2)
draw("No. 01", x: 842, y: 43, width: 100, height: 22, fontSize: 14, weight: .medium, color: rose, tracking: 1.1)
draw("CHARACTER\nPROFILE", x: 838, y: 82, width: 125, height: 54, fontSize: 12, weight: .medium, color: rose, tracking: 1.6, wrap: true)
draw("栀夏飞花令", x: 814, y: 187, width: 160, height: 22, fontSize: 13, weight: .medium, color: rose, tracking: 2)

// Section titles.
draw("基础信息", x: 26, y: 322, width: 140, height: 20, fontSize: 12, weight: .medium, color: rose, tracking: 1.5)
draw("BASIC INFORMATION", x: 26, y: 341, width: 170, height: 15, fontSize: 7.5, color: subInk, tracking: 0.7)
draw("三视图", x: 250, y: 322, width: 100, height: 20, fontSize: 12, weight: .medium, color: rose, tracking: 1.5)
draw("MODEL SHEET", x: 250, y: 341, width: 140, height: 15, fontSize: 7.5, color: subInk, tracking: 0.7)
draw("表情参考", x: 711, y: 322, width: 150, height: 20, fontSize: 12, weight: .medium, color: rose, tracking: 1.5)
draw("EXPRESSIONS", x: 711, y: 341, width: 130, height: 15, fontSize: 7.5, color: subInk, tracking: 0.7)

// Left profile column.
let profile = [
    ("角色名 / NAME", "栀夏  Zhixia"),
    ("身份 / ROLE", "飞花令行者"),
    ("年龄 / AGE", "18"),
    ("身高 / HEIGHT", "160 cm"),
    ("体型 / BODY", "自然修长，约 7 头身"),
    ("外貌特征 / APPEARANCE", "墨黑高马尾 · 杏仁眼\n白花银枝发冠 · 轻甜浅笑"),
    ("气质关键词 / KEYWORDS", "温柔 · 灵动 · 聪慧\n坚定 · 书卷气 · 诗意")
]
var py: CGFloat = 375
for (label, value) in profile {
    draw(label, x: 29, y: py, width: 150, height: 15, fontSize: 7.5, weight: .medium, color: subInk, tracking: 0.5)
    draw(value, x: 29, y: py + 16, width: 162, height: 37, fontSize: 10.5, weight: .regular, color: ink, wrap: true)
    py += label == "气质关键词 / KEYWORDS" ? 67 : 57
}

// Model sheet labels and six expressions.
draw("正面 / FRONT", x: 277, y: 904, width: 110, height: 16, fontSize: 8, color: subInk, tracking: 0.5)
draw("右侧 / SIDE", x: 437, y: 904, width: 110, height: 16, fontSize: 8, color: subInk, tracking: 0.5)
draw("背面 / BACK", x: 575, y: 904, width: 110, height: 16, fontSize: 8, color: subInk, tracking: 0.5)
let expressions = ["平静 / NEUTRAL", "微笑 / SMILE", "专注 / ATTENTIVE", "惊喜 / SURPRISED", "思考 / THINKING", "轻笑 / SOFT LAUGH"]
let expressionPoints: [(CGFloat, CGFloat)] = [(715, 521), (866, 521), (715, 728), (866, 728), (715, 934), (866, 934)]
for (index, text) in expressions.enumerated() {
    draw(text, x: expressionPoints[index].0, y: expressionPoints[index].1, width: 120, height: 15, fontSize: 7.1, color: subInk, tracking: 0.25)
}

// Lower content section.
draw("服装拆解", x: 28, y: 963, width: 130, height: 18, fontSize: 11, weight: .medium, color: rose, tracking: 1)
draw("OUTFIT BREAKDOWN", x: 28, y: 981, width: 160, height: 13, fontSize: 7.2, color: subInk, tracking: 0.6)
draw("饰品", x: 374, y: 963, width: 90, height: 18, fontSize: 11, weight: .medium, color: rose, tracking: 1)
draw("ACCESSORIES", x: 374, y: 981, width: 130, height: 13, fontSize: 7.2, color: subInk, tracking: 0.6)
draw("细节特写", x: 546, y: 963, width: 130, height: 18, fontSize: 11, weight: .medium, color: rose, tracking: 1)
draw("DETAIL CLOSE-UP", x: 546, y: 981, width: 140, height: 13, fontSize: 7.2, color: subInk, tracking: 0.6)
draw("色彩材质", x: 817, y: 963, width: 130, height: 18, fontSize: 11, weight: .medium, color: rose, tracking: 1)
draw("COLOR PALETTE", x: 817, y: 981, width: 130, height: 13, fontSize: 7.2, color: subInk, tracking: 0.6)

draw("月白绣花抹胸 · 浅水青薄罗 · 雾青绿高腰裙 · 云头履", x: 28, y: 1263, width: 316, height: 15, fontSize: 7.1, color: subInk, tracking: 0.05)
draw("白花银枝发冠\n藕粉腰封", x: 374, y: 1259, width: 70, height: 25, fontSize: 6.8, color: subInk, wrap: true)
let palette = ["暖象牙白  #F1ECE2", "浅水青  #C7DDE0", "雾青绿  #9ABDBB", "柔藕粉  #E3BDC1", "哑光暖金  #C6A474"]
for (i, text) in palette.enumerated() {
    draw(text, x: 880, y: 1017 + CGFloat(i) * 36, width: 112, height: 13, fontSize: 6.6, color: subInk, tracking: 0.1)
}

// Footer.
draw("角色介绍", x: 29, y: 1304, width: 130, height: 18, fontSize: 11, weight: .medium, color: rose, tracking: 1)
draw("CHARACTER INTRODUCTION", x: 29, y: 1322, width: 180, height: 13, fontSize: 7.2, color: subInk, tracking: 0.6)
draw("栀夏，是穿行诗境的少女。她温柔而坚定，\n善于在风、花、山水间聆听诗句。面对未知，\n她先观察，再轻轻伸手触碰光。", x: 29, y: 1353, width: 300, height: 78, fontSize: 9, color: ink, wrap: true)
draw("关键词", x: 396, y: 1304, width: 100, height: 18, fontSize: 11, weight: .medium, color: rose, tracking: 1)
draw("KEYWORDS", x: 396, y: 1322, width: 100, height: 13, fontSize: 7.2, color: subInk, tracking: 0.6)
let chips = ["温柔坚定", "诗意感知", "灵动克制", "自然亲和", "书卷气", "轻甜笑意"]
let chipPoints: [(CGFloat, CGFloat)] = [(396, 1360), (535, 1360), (396, 1397), (535, 1397), (396, 1434), (535, 1434)]
for (i, chip) in chips.enumerated() {
    drawChip(chipPoints[i].0, chipPoints[i].1, 128, 30)
    draw(chip, x: chipPoints[i].0 + 13, y: chipPoints[i].1 + 8, width: 108, height: 18, fontSize: 8.2, color: subInk, tracking: 0.3)
}
draw("角色签名", x: 709, y: 1304, width: 120, height: 18, fontSize: 11, weight: .medium, color: rose, tracking: 1)
draw("SIGNATURE", x: 709, y: 1322, width: 100, height: 13, fontSize: 7.2, color: subInk, tracking: 0.6)
draw("栀夏", x: 760, y: 1372, width: 180, height: 45, fontSize: 31, weight: .light, color: ink, tracking: 5)
draw("—— 诗里见", x: 770, y: 1421, width: 160, height: 17, fontSize: 10, color: subInk, tracking: 1.5)

canvas.unlockFocus()
guard let tiff = canvas.tiffRepresentation,
      let bitmap = NSBitmapImageRep(data: tiff),
      let png = bitmap.representation(using: .png, properties: [:]) else {
    fputs("Cannot encode PNG.\n", stderr)
    exit(1)
}
try png.write(to: URL(fileURLWithPath: args[2]))
