import AppKit
import CoreText
import Foundation

enum CoverError: Error { case usage, image, bitmap, encode, font }

func styledText(_ value: String, size: CGFloat, fontName: String, outline: CGFloat) throws -> NSAttributedString {
    guard let font = NSFont(name: fontName, size: size) else { throw CoverError.font }
    let shadow = NSShadow()
    shadow.shadowColor = NSColor(calibratedRed: 0.16, green: 0.10, blue: 0.07, alpha: 0.78)
    shadow.shadowBlurRadius = size > 80 ? 8 : 4
    shadow.shadowOffset = NSSize(width: 2, height: -3)
    return NSAttributedString(string: value, attributes: [
        .font: font,
        .foregroundColor: NSColor(calibratedRed: 1.0, green: 0.96, blue: 0.88, alpha: 1.0),
        .strokeColor: NSColor(calibratedRed: 0.20, green: 0.13, blue: 0.09, alpha: 1.0),
        .strokeWidth: -outline,
        .shadow: shadow
    ])
}

func drawFilled(_ value: NSAttributedString, at point: NSPoint) {
    value.draw(at: point)
    let fill = NSMutableAttributedString(attributedString: value)
    let range = NSRange(location: 0, length: fill.length)
    fill.removeAttribute(.strokeWidth, range: range)
    fill.removeAttribute(.strokeColor, range: range)
    fill.removeAttribute(.shadow, range: range)
    fill.draw(at: point)
}

do {
    guard CommandLine.arguments.count == 3 else { throw CoverError.usage }
    let input = URL(fileURLWithPath: CommandLine.arguments[1])
    let output = URL(fileURLWithPath: CommandLine.arguments[2])
    guard let base = NSImage(contentsOf: input) else { throw CoverError.image }

    for path in [
        "/System/Library/AssetsV2/com_apple_MobileAsset_Font7/aa99d0b2bad7f797f38b49d46cde28fd4b58876e.asset/AssetData/Xingkai.ttc",
        "/System/Library/AssetsV2/com_apple_MobileAsset_Font7/54a2ad3dac6cac875ad675d7d273dc425010a877.asset/AssetData/Kaiti.ttc"
    ] {
        CTFontManagerRegisterFontsForURL(URL(fileURLWithPath: path) as CFURL, .process, nil)
    }

    guard let bitmap = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: 1080, pixelsHigh: 1920,
        bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false,
        colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0),
        let context = NSGraphicsContext(bitmapImageRep: bitmap) else { throw CoverError.bitmap }

    let series = try styledText("天宫采访", size: 44, fontName: "STKaitiSC-Regular", outline: 1.6)
    let title1 = try styledText("仙女的", size: 116, fontName: "STXingkaiSC-Bold", outline: 1.2)
    let title2 = try styledText("年终奖", size: 164, fontName: "STXingkaiSC-Bold", outline: 1.2)

    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.current = context
    base.draw(in: NSRect(x: 0, y: 0, width: 1080, height: 1920), from: .zero, operation: .copy, fraction: 1)
    for (line, top) in [(series, CGFloat(1240)), (title1, CGFloat(1312)), (title2, CGFloat(1450))] {
        drawFilled(line, at: NSPoint(x: 62, y: 1920 - top - line.size().height))
    }
    NSGraphicsContext.restoreGraphicsState()

    guard let data = bitmap.representation(using: .png, properties: [:]) else { throw CoverError.encode }
    try data.write(to: output, options: .atomic)
} catch {
    FileHandle.standardError.write(Data("Cover error: \(error)\n".utf8))
    exit(1)
}
