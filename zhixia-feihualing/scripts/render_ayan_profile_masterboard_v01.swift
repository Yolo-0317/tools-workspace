import AppKit

let args = CommandLine.arguments
guard args.count == 3, let source = NSImage(contentsOfFile: args[1]) else {
    fputs("Usage: render_ayan_profile_masterboard_v01.swift input.png output.png\n", stderr)
    exit(2)
}

let size = source.size
let canvas = NSImage(size: size)
let scale = size.width / 1023.0

func topRect(_ x: CGFloat, _ y: CGFloat, _ width: CGFloat, _ height: CGFloat) -> NSRect {
    NSRect(x: x * scale, y: size.height - (y + height) * scale, width: width * scale, height: height * scale)
}

let cinnabar = NSColor(calibratedRed: 181 / 255, green: 68 / 255, blue: 50 / 255, alpha: 1)
let ink = NSColor(calibratedRed: 37 / 255, green: 37 / 255, blue: 37 / 255, alpha: 1)
let subInk = NSColor(calibratedRed: 92 / 255, green: 88 / 255, blue: 82 / 255, alpha: 1)
let warmGold = NSColor(calibratedRed: 185 / 255, green: 154 / 255, blue: 93 / 255, alpha: 1)
let paper = NSColor(calibratedRed: 242 / 255, green: 238 / 255, blue: 229 / 255, alpha: 1)
let fontName = "PingFang SC"

func attrs(_ fontSize: CGFloat, _ weight: NSFont.Weight = .regular, _ color: NSColor = ink, _ tracking: CGFloat = 0) -> [NSAttributedString.Key: Any] {
    [
        .font: NSFont(name: fontName, size: fontSize * scale) ?? NSFont.systemFont(ofSize: fontSize * scale, weight: weight),
        .foregroundColor: color,
        .kern: tracking * scale
    ]
}

func draw(_ string: String, x: CGFloat, y: CGFloat, width: CGFloat, height: CGFloat, fontSize: CGFloat, weight: NSFont.Weight = .regular, color: NSColor = ink, tracking: CGFloat = 0, wrap: Bool = false, centered: Bool = false) {
    let paragraph = NSMutableParagraphStyle()
    paragraph.alignment = centered ? .center : .left
    paragraph.lineBreakMode = wrap ? .byWordWrapping : .byTruncatingTail
    var attributes = attrs(fontSize, weight, color, tracking)
    attributes[.paragraphStyle] = paragraph
    let options: NSString.DrawingOptions = wrap ? [.usesLineFragmentOrigin, .usesFontLeading] : []
    (string as NSString).draw(with: topRect(x, y, width, height), options: options, attributes: attributes, context: nil)
}

func section(_ cn: String, _ en: String, x: CGFloat, y: CGFloat, width: CGFloat) {
    draw(cn, x: x, y: y, width: width, height: 18, fontSize: 11, weight: .semibold, color: cinnabar, tracking: 1.1)
    draw(en, x: x, y: y + 18, width: width, height: 13, fontSize: 6.8, weight: .medium, color: subInk, tracking: 0.55)
}

func drawChip(_ x: CGFloat, _ y: CGFloat, _ width: CGFloat, _ height: CGFloat, _ text: String) {
    let box = NSBezierPath(roundedRect: topRect(x, y, width, height), xRadius: 4 * scale, yRadius: 4 * scale)
    NSColor(calibratedWhite: 1, alpha: 0.27).setFill()
    box.fill()
    cinnabar.withAlphaComponent(0.23).setStroke()
    box.lineWidth = 0.7 * scale
    box.stroke()
    draw(text, x: x + 4, y: y + 8, width: width - 8, height: 16, fontSize: 8.1, color: subInk, tracking: 0.2, centered: true)
}

func expressionLabel(_ text: String, x: CGFloat, y: CGFloat) {
    let plate = NSBezierPath(roundedRect: topRect(x, y, 128, 17), xRadius: 2.5 * scale, yRadius: 2.5 * scale)
    paper.withAlphaComponent(0.78).setFill()
    plate.fill()
    draw(text, x: x + 2, y: y + 4, width: 124, height: 11, fontSize: 6.3, weight: .medium, color: subInk, tracking: 0.15, centered: true)
}

func drawPawMark(centerX: CGFloat, centerY: CGFloat) {
    cinnabar.setFill()
    let pad = NSBezierPath(ovalIn: topRect(centerX - 11, centerY - 2, 22, 17))
    pad.fill()
    let toes: [(CGFloat, CGFloat, CGFloat)] = [(-15, -12, 5), (-5, -18, 5.2), (6, -18, 5.2), (16, -12, 5)]
    for (dx, dy, radius) in toes {
        NSBezierPath(ovalIn: topRect(centerX + dx - radius, centerY + dy - radius, radius * 2, radius * 2)).fill()
    }
}

canvas.lockFocus()
source.draw(in: NSRect(origin: .zero, size: size))

// Header identity.
draw("A YAN", x: 42, y: 22, width: 470, height: 55, fontSize: 45, weight: .light, color: cinnabar, tracking: 3.2)
draw("阿砚", x: 44, y: 76, width: 220, height: 43, fontSize: 34, weight: .light, color: cinnabar, tracking: 4)
draw("墨痕落纸，它便从诗里醒来。", x: 45, y: 119, width: 600, height: 23, fontSize: 15, weight: .regular, color: cinnabar, tracking: 1.1)
draw("WHEN INK TOUCHES PAPER, IT AWAKENS FROM POETRY.", x: 47, y: 145, width: 620, height: 13, fontSize: 7.2, weight: .medium, color: subInk, tracking: 1)
draw("No. 02", x: 833, y: 34, width: 95, height: 18, fontSize: 12, weight: .medium, color: cinnabar, tracking: 1)
draw("CHARACTER\nPROFILE", x: 823, y: 62, width: 115, height: 39, fontSize: 10, weight: .medium, color: cinnabar, tracking: 1.4, wrap: true, centered: true)
draw("栀夏飞花令", x: 809, y: 126, width: 142, height: 18, fontSize: 10.5, weight: .medium, color: cinnabar, tracking: 2, centered: true)

// Main profile area.
section("基础信息", "BASIC INFORMATION", x: 28, y: 185, width: 160)
section("表情参考", "EXPRESSIONS", x: 294, y: 185, width: 145)

let profile = [
    ("角色名 / NAME", "阿砚  Ayan"),
    ("身份 / ROLE", "原创东方墨灵"),
    ("高度 / HEIGHT", "约 9 cm"),
    ("结构 / STRUCTURE", "双耳 · 四足 · 单尾"),
    ("眼睛 / EYES", "暖琥珀色"),
    ("固定标记 / MARKS", "额间朱砂印\n肩胸暖金云纹"),
    ("性格关键词 / KEYWORDS", "聪明 · 独立 · 克制\n好奇 · 灵动 · 顽皮")
]
var py: CGFloat = 236
for (index, item) in profile.enumerated() {
    draw(item.0, x: 30, y: py, width: 210, height: 13, fontSize: 7, weight: .medium, color: subInk, tracking: 0.35)
    draw(item.1, x: 30, y: py + 14, width: 220, height: 31, fontSize: 9.4, color: ink, wrap: true)
    py += index >= 5 ? 69 : 58
}

section("三视图", "MODEL SHEET", x: 30, y: 707, width: 145)
draw("正面 / FRONT", x: 74, y: 1063, width: 150, height: 14, fontSize: 7.4, color: subInk, tracking: 0.4, centered: true)
draw("右侧 / SIDE", x: 435, y: 1063, width: 150, height: 14, fontSize: 7.4, color: subInk, tracking: 0.4, centered: true)
draw("背面 / BACK", x: 789, y: 1063, width: 150, height: 14, fontSize: 7.4, color: subInk, tracking: 0.4, centered: true)

let expressions = ["平静 / NEUTRAL", "好奇 / CURIOUS", "警觉 / ALERT", "惊讶 / SURPRISED", "得意 / PROUD", "顽皮 / PLAYFUL"]
let expressionPoints: [(CGFloat, CGFloat)] = [(340, 395), (579, 395), (817, 395), (340, 648), (579, 648), (817, 648)]
for (index, text) in expressions.enumerated() {
    expressionLabel(text, x: expressionPoints[index].0, y: expressionPoints[index].1)
}

// Lower reference area.
section("结构拆解", "STRUCTURE BREAKDOWN", x: 28, y: 1115, width: 190)
section("固定标记", "FIXED MARKS", x: 356, y: 1115, width: 150)
section("细节特写", "DETAIL CLOSE-UP", x: 542, y: 1115, width: 150)
section("色彩材质", "COLOR PALETTE", x: 854, y: 1115, width: 150)

draw("双笔锋耳 · 严格四足\n唯一开放式 S 形墨尾", x: 28, y: 1340, width: 292, height: 35, fontSize: 7.5, color: subInk, tracking: 0.1, wrap: true)

let paletteLabels = [
    ("宣纸白  #F2EEE5", ink),
    ("淡墨灰  #A9A5A0", ink),
    ("深墨黑  #252525", NSColor.white),
    ("哑光暖金  #B99A5D", ink),
    ("朱砂红  #B54432", NSColor.white)
]
let paletteY: [CGFloat] = [1127, 1178, 1229, 1280, 1331]
for (index, item) in paletteLabels.enumerated() {
    draw(item.0, x: 870, y: paletteY[index] + 20, width: 106, height: 12, fontSize: 5.7, weight: .medium, color: item.1, tracking: 0.02, centered: true)
}

// Footer.
section("角色介绍", "CHARACTER INTRODUCTION", x: 30, y: 1402, width: 190)
draw("阿砚是从墨痕与诗句间醒来的东方墨灵。它聪明、独立而克制，面对未知先观察、再试探，偶尔露出一点顽皮。", x: 30, y: 1449, width: 280, height: 70, fontSize: 8.3, color: ink, tracking: 0.08, wrap: true)

section("关键词", "KEYWORDS", x: 370, y: 1402, width: 110)
let chips = ["聪明独立", "纸墨灵性", "克制敏锐", "试探好奇", "守护诗句", "轻巧灵动"]
let chipPoints: [(CGFloat, CGFloat)] = [(375, 1444), (523, 1444), (375, 1475), (523, 1475), (375, 1506), (523, 1506)]
for (index, chip) in chips.enumerated() {
    drawChip(chipPoints[index].0, chipPoints[index].1, 136, 25, chip)
}

section("角色签名", "SIGNATURE", x: 732, y: 1402, width: 140)
draw("阿砚", x: 895, y: 1446, width: 100, height: 35, fontSize: 24, weight: .light, color: ink, tracking: 3, centered: true)
draw("—— 诗里见", x: 890, y: 1484, width: 110, height: 15, fontSize: 8.3, color: subInk, tracking: 0.8, centered: true)

canvas.unlockFocus()

guard let tiff = canvas.tiffRepresentation,
      let bitmap = NSBitmapImageRep(data: tiff),
      let png = bitmap.representation(using: .png, properties: [:]) else {
    fputs("Cannot encode PNG.\n", stderr)
    exit(1)
}

try png.write(to: URL(fileURLWithPath: args[2]))
