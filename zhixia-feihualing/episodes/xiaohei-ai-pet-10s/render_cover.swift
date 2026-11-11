import AppKit
import CoreText
import Foundation

guard CommandLine.arguments.count == 3 else {
    fatalError("Usage: render_cover.swift base.png output.png")
}

let source = URL(fileURLWithPath: CommandLine.arguments[1])
let output = URL(fileURLWithPath: CommandLine.arguments[2])
guard let base = NSImage(contentsOf: source),
      let bitmap = NSBitmapImageRep(
        bitmapDataPlanes: nil, pixelsWide: 1080, pixelsHigh: 1920,
        bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true,
        isPlanar: false, colorSpaceName: .deviceRGB,
        bytesPerRow: 0, bitsPerPixel: 0
      ), let context = NSGraphicsContext(bitmapImageRep: bitmap) else {
    fatalError("Cannot open cover image")
}

for path in [
    "/System/Library/AssetsV2/com_apple_MobileAsset_Font7/aa99d0b2bad7f797f38b49d46cde28fd4b58876e.asset/AssetData/Xingkai.ttc",
    "/System/Library/AssetsV2/com_apple_MobileAsset_Font7/54a2ad3dac6cac875ad675d7d273dc425010a877.asset/AssetData/Kaiti.ttc"
] {
    CTFontManagerRegisterFontsForURL(URL(fileURLWithPath: path) as CFURL, .process, nil)
}

func text(_ value: String, size: CGFloat, fontName: String? = nil, stroke: CGFloat = 2) -> NSAttributedString {
    let font = fontName.flatMap { NSFont(name: $0, size: size) } ?? NSFont.systemFont(ofSize: size, weight: .bold)
    let shadow = NSShadow()
    shadow.shadowColor = NSColor(calibratedRed: 0.07, green: 0.05, blue: 0.04, alpha: 0.8)
    shadow.shadowBlurRadius = 7
    shadow.shadowOffset = NSSize(width: 2, height: -3)
    return NSAttributedString(string: value, attributes: [
        .font: font,
        .foregroundColor: NSColor(calibratedRed: 1, green: 0.96, blue: 0.88, alpha: 1),
        .strokeColor: NSColor(calibratedRed: 0.16, green: 0.10, blue: 0.07, alpha: 1),
        .strokeWidth: -stroke,
        .shadow: shadow
    ])
}

func draw(_ value: NSAttributedString, x: CGFloat, top: CGFloat) {
    let point = NSPoint(x: x, y: 1920 - top - value.size().height)
    value.draw(at: point)
    let fill = NSMutableAttributedString(attributedString: value)
    let range = NSRange(location: 0, length: fill.length)
    fill.removeAttribute(.strokeWidth, range: range)
    fill.removeAttribute(.strokeColor, range: range)
    fill.removeAttribute(.shadow, range: range)
    fill.draw(at: point)
}

NSGraphicsContext.saveGraphicsState()
NSGraphicsContext.current = context
base.draw(in: NSRect(x: 0, y: 0, width: 1080, height: 1920), from: .zero, operation: .copy, fraction: 1)

for y in 0..<830 {
    let depth = 1 - CGFloat(y) / 830
    let alpha = 0.90 * depth * depth
    NSColor(calibratedRed: 0.075, green: 0.055, blue: 0.045, alpha: alpha).setFill()
    NSRect(x: 0, y: CGFloat(y), width: 1080, height: 1).fill()
}

let accent = NSColor(calibratedRed: 0.85, green: 0.66, blue: 0.43, alpha: 1)
accent.setFill()
NSRect(x: 78, y: 1920 - 1325, width: 68, height: 4).fill()

draw(text("走失多年的小黑", size: 48, fontName: "STKaitiSC-Regular", stroke: 1), x: 78, top: 1350)
draw(text("借着 AI，", size: 106, fontName: "STXingkaiSC-Bold", stroke: 1.5), x: 70, top: 1430)
draw(text("又回来了", size: 142, fontName: "STXingkaiSC-Bold", stroke: 1.6), x: 70, top: 1550)
draw(text("一段 10 秒的影像重逢", size: 37, fontName: "STKaitiSC-Regular", stroke: 0.8), x: 79, top: 1775)

NSGraphicsContext.restoreGraphicsState()
guard let png = bitmap.representation(using: .png, properties: [:]) else {
    fatalError("Cannot encode cover")
}
try png.write(to: output, options: .atomic)
