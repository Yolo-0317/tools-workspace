import AppKit
import CoreText
import Foundation

struct Cue: Decodable {
    let id: String
    let text: String
    let start: Double
    let end: Double
}
enum ArtworkError: Error { case usage, image, bitmap, encode, font }

func canvas(_ w: Int, _ h: Int, draw: () -> Void, output: URL) throws {
    guard let bmp = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: w, pixelsHigh: h,
        bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false,
        colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0),
        let ctx = NSGraphicsContext(bitmapImageRep: bmp) else { throw ArtworkError.bitmap }
    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.current = ctx
    NSColor.clear.setFill()
    NSRect(x: 0, y: 0, width: w, height: h).fill()
    draw()
    NSGraphicsContext.restoreGraphicsState()
    guard let data = bmp.representation(using: .png, properties: [:]) else { throw ArtworkError.encode }
    try data.write(to: output, options: .atomic)
}

func lettering(_ text: String, size: CGFloat, color: NSColor, outline: CGFloat, fontName: String? = nil) throws -> NSAttributedString {
    let font: NSFont
    if let name = fontName {
        guard let selected = NSFont(name: name, size: size) else { throw ArtworkError.font }
        font = selected
    } else { font = NSFont.systemFont(ofSize: size, weight: .bold) }
    let shadow = NSShadow()
    shadow.shadowColor = NSColor(calibratedRed: 0.16, green: 0.10, blue: 0.07, alpha: 0.75)
    shadow.shadowBlurRadius = size > 70 ? 8 : 3
    shadow.shadowOffset = NSSize(width: 1, height: -2)
    return NSAttributedString(string: text, attributes: [
        .font: font, .foregroundColor: color, .strokeColor: NSColor(calibratedRed: 0.20, green: 0.13, blue: 0.09, alpha: 1),
        .strokeWidth: -outline, .shadow: shadow
    ])
}

func drawFilled(_ text: NSAttributedString, at point: NSPoint) {
    text.draw(at: point)
    let fill = NSMutableAttributedString(attributedString: text)
    let range = NSRange(location: 0, length: fill.length)
    fill.removeAttribute(.strokeWidth, range: range)
    fill.removeAttribute(.strokeColor, range: range)
    fill.removeAttribute(.shadow, range: range)
    fill.draw(at: point)
}

do {
    guard CommandLine.arguments.count == 4 else { throw ArtworkError.usage }
    let manifest = URL(fileURLWithPath: CommandLine.arguments[1])
    let baseURL = URL(fileURLWithPath: CommandLine.arguments[2])
    let out = URL(fileURLWithPath: CommandLine.arguments[3], isDirectory: true)
    try FileManager.default.createDirectory(at: out, withIntermediateDirectories: true)
    let cues = try JSONDecoder().decode([Cue].self, from: Data(contentsOf: manifest))
    for cue in cues {
        let text = try lettering(cue.text, size: 36, color: .white, outline: 4)
        try canvas(720, 1280, draw: {
            let size = text.size()
            drawFilled(text, at: NSPoint(x: (720 - size.width) / 2, y: 1280 - 1080 - size.height))
        }, output: out.appendingPathComponent(cue.id + ".png"))
    }
    guard let base = NSImage(contentsOf: baseURL), base.size.width == 1080, base.size.height == 1920 else { throw ArtworkError.image }
    for path in [
        "/System/Library/AssetsV2/com_apple_MobileAsset_Font7/aa99d0b2bad7f797f38b49d46cde28fd4b58876e.asset/AssetData/Xingkai.ttc",
        "/System/Library/AssetsV2/com_apple_MobileAsset_Font7/54a2ad3dac6cac875ad675d7d273dc425010a877.asset/AssetData/Kaiti.ttc"
    ] { CTFontManagerRegisterFontsForURL(URL(fileURLWithPath: path) as CFURL, .process, nil) }
    let ivory = NSColor(calibratedRed: 1, green: 0.96, blue: 0.88, alpha: 1)
    let series = try lettering("天宫日常", size: 40, color: ivory, outline: 1, fontName: "STKaitiSC-Regular")
    let title1 = try lettering("仙女", size: 130, color: ivory, outline: 0.8, fontName: "STXingkaiSC-Bold")
    let title2 = try lettering("借个火", size: 155, color: ivory, outline: 0.8, fontName: "STXingkaiSC-Bold")
    try canvas(1080, 1920, draw: {
        base.draw(in: NSRect(x: 0, y: 0, width: 1080, height: 1920), from: .zero, operation: .copy, fraction: 1)
        for (text, top) in [(series, CGFloat(1235)), (title1, CGFloat(1310)), (title2, CGFloat(1460))] {
            drawFilled(text, at: NSPoint(x: 68, y: 1920 - top - text.size().height))
        }
    }, output: out.appendingPathComponent("cover-rgba.png"))
} catch {
    FileHandle.standardError.write(Data("Artwork error: \(error)\n".utf8))
    exit(1)
}
