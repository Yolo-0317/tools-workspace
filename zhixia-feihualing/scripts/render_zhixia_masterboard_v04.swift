import AppKit

let arguments = CommandLine.arguments
guard arguments.count == 3 else {
    fputs("Usage: render_zhixia_masterboard_v04.swift input.png output.png\n", stderr)
    exit(2)
}

let inputURL = URL(fileURLWithPath: arguments[1])
let outputURL = URL(fileURLWithPath: arguments[2])
guard let source = NSImage(contentsOf: inputURL) else {
    fputs("Cannot load input image.\n", stderr)
    exit(1)
}

let size = source.size
let canvas = NSImage(size: size)
canvas.lockFocus()
source.draw(in: NSRect(origin: .zero, size: size))

let scale = size.width / 941.0
func rect(_ x: CGFloat, _ y: CGFloat, _ width: CGFloat, _ height: CGFloat) -> NSRect {
    NSRect(x: x * scale, y: y * scale, width: width * scale, height: height * scale)
}

let fontName = "PingFang SC"
func textAttributes(size: CGFloat, weight: NSFont.Weight, color: NSColor) -> [NSAttributedString.Key: Any] {
    [
        .font: NSFont(name: fontName, size: size * scale) ?? NSFont.systemFont(ofSize: size * scale, weight: weight),
        .foregroundColor: color,
        .kern: 0.35 * scale
    ]
}

func drawLabel(title: String, detail: String, at box: NSRect) {
    let background = NSBezierPath(roundedRect: box, xRadius: 7 * scale, yRadius: 7 * scale)
    NSColor(calibratedWhite: 1.0, alpha: 0.86).setFill()
    background.fill()
    NSColor(calibratedRed: 0.60, green: 0.47, blue: 0.28, alpha: 0.68).setStroke()
    background.lineWidth = 0.75 * scale
    background.stroke()

    let paragraph = NSMutableParagraphStyle()
    paragraph.lineSpacing = 1.5 * scale
    let titleRect = NSRect(x: box.minX + 10 * scale, y: box.maxY - 25 * scale, width: box.width - 20 * scale, height: 18 * scale)
    title.draw(in: titleRect, withAttributes: textAttributes(size: 13, weight: .semibold, color: NSColor(calibratedRed: 0.24, green: 0.29, blue: 0.30, alpha: 1)))
    var attributes = textAttributes(size: 9.5, weight: .regular, color: NSColor(calibratedRed: 0.30, green: 0.34, blue: 0.35, alpha: 1))
    attributes[.paragraphStyle] = paragraph
    detail.draw(in: NSRect(x: box.minX + 10 * scale, y: box.minY + 7 * scale, width: box.width - 20 * scale, height: box.height - 30 * scale), withAttributes: attributes)
}

let headerRect = rect(30, 1590, 881, 56)
let headerPath = NSBezierPath(roundedRect: headerRect, xRadius: 8 * scale, yRadius: 8 * scale)
NSColor(calibratedWhite: 1, alpha: 0.90).setFill()
headerPath.fill()
let title = "栀夏｜角色母板 v04"
title.draw(in: NSRect(x: headerRect.minX + 16 * scale, y: headerRect.minY + 23 * scale, width: 330 * scale, height: 28 * scale), withAttributes: textAttributes(size: 20, weight: .semibold, color: NSColor(calibratedRed: 0.20, green: 0.29, blue: 0.31, alpha: 1)))
let subtitle = "Seedance 固定参考 · 原创虚构数字角色 · 电影级高写实 CG"
subtitle.draw(in: NSRect(x: headerRect.minX + 345 * scale, y: headerRect.minY + 26 * scale, width: 515 * scale, height: 18 * scale), withAttributes: textAttributes(size: 10.5, weight: .regular, color: NSColor(calibratedRed: 0.45, green: 0.38, blue: 0.30, alpha: 1)))

drawLabel(title: "01 正面全身主卡", detail: "锁定身材比例、自然站姿、黑色高马尾与白花银枝发冠；盛唐高腰造型，脚踝与云头履完整可见。", at: rect(38, 1190, 330, 63))
drawLabel(title: "02 三视图", detail: "锁定正面、侧面、背面轮廓；裙长、薄罗大袖、腰封位置与鞋履比例全角度一致。", at: rect(28, 570, 330, 62))
drawLabel(title: "03 面部特写", detail: "锁定柔和鹅蛋脸、自然杏仁眼、轻甜浅笑、细碎发与发冠佩戴位置；不幼态、不成熟艳丽。", at: rect(480, 570, 405, 62))
drawLabel(title: "04 饰品与服装细节", detail: "白花银枝发冠、月白绣花抹胸、浅水青透明薄罗、藕粉蝴蝶结腰封、青绿云头履。", at: rect(28, 48, 390, 62))
drawLabel(title: "05 色彩与材质", detail: "暖象牙白、浅水青、雾青绿、柔和藕粉、哑光暖金；丝绢、薄罗与克制金线刺绣，清透略高饱和。", at: rect(480, 48, 405, 62))

canvas.unlockFocus()
guard let tiff = canvas.tiffRepresentation,
      let bitmap = NSBitmapImageRep(data: tiff),
      let png = bitmap.representation(using: .png, properties: [:]) else {
    fputs("Cannot encode PNG.\n", stderr)
    exit(1)
}
try png.write(to: outputURL)
