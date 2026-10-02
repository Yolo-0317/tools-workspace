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

func caption(_ value: String, size: CGFloat, fontName: String?, stroke: CGFloat) -> NSAttributedString {
    let font = fontName.flatMap { NSFont(name: $0, size: size) } ?? NSFont.systemFont(ofSize: size, weight: .bold)
    let shadow = NSShadow()
    shadow.shadowColor = NSColor(calibratedRed: 0.07, green: 0.05, blue: 0.04, alpha: 0.75)
    shadow.shadowBlurRadius = 6
    shadow.shadowOffset = NSSize(width: 2, height: -3)
    return NSAttributedString(string: value, attributes: [
        .font: font,
        .foregroundColor: NSColor(calibratedRed: 1, green: 0.96, blue: 0.88, alpha: 1),
        .strokeColor: NSColor(calibratedRed: 0.15, green: 0.10, blue: 0.07, alpha: 1),
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

for row in 0..<455 {
    let depth = 1 - CGFloat(row) / 455
    NSColor(calibratedRed: 0.08, green: 0.06, blue: 0.05, alpha: 0.56 * depth * depth).setFill()
    NSRect(x: 0, y: 1920 - CGFloat(row) - 1, width: 1080, height: 1).fill()
}

NSColor(calibratedRed: 0.90, green: 0.73, blue: 0.47, alpha: 1).setFill()
NSRect(x: 70, y: 1920 - 132, width: 60, height: 4).fill()
draw(caption("走失多年的小黑 · AI影像重逢", size: 36, fontName: "STKaitiSC-Regular", stroke: 0.8), x: 70, top: 142)
draw(caption("小黑上天宫", size: 96, fontName: "STXingkaiSC-Bold", stroke: 1.6), x: 65, top: 215)
draw(caption("蟠桃能续碗不？", size: 78, fontName: "STXingkaiSC-Bold", stroke: 1.5), x: 69, top: 338)

NSGraphicsContext.restoreGraphicsState()
guard let png = bitmap.representation(using: .png, properties: [:]) else {
    fatalError("Cannot encode cover")
}
try png.write(to: output, options: .atomic)
