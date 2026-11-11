import AppKit
import Foundation

struct Cue: Decodable {
    let id: String
    let text: String
    let start: Double
    let end: Double
    let kind: String
}

enum ArtworkError: Error { case usage, bitmap, encode }

func canvas(_ w: Int, _ h: Int, draw: () -> Void, output: URL) throws {
    guard let bitmap = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: w, pixelsHigh: h,
        bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false,
        colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0),
        let context = NSGraphicsContext(bitmapImageRep: bitmap) else { throw ArtworkError.bitmap }
    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.current = context
    NSColor.clear.setFill()
    NSRect(x: 0, y: 0, width: w, height: h).fill()
    draw()
    NSGraphicsContext.restoreGraphicsState()
    guard let data = bitmap.representation(using: .png, properties: [:]) else { throw ArtworkError.encode }
    try data.write(to: output, options: .atomic)
}

func label(_ value: String, kind: String) -> NSAttributedString {
    let paragraph = NSMutableParagraphStyle()
    paragraph.alignment = .center
    paragraph.lineSpacing = 3
    let size: CGFloat = kind == "commentary" ? 44 : 42
    let shadow = NSShadow()
    shadow.shadowColor = NSColor(calibratedWhite: 0, alpha: 0.75)
    shadow.shadowBlurRadius = 3
    shadow.shadowOffset = NSSize(width: 1, height: -1)
    return NSAttributedString(string: value, attributes: [
        .font: NSFont.systemFont(ofSize: size, weight: .bold),
        .foregroundColor: NSColor.white,
        .strokeColor: NSColor(calibratedWhite: 0.05, alpha: 1),
        .strokeWidth: -4,
        .shadow: shadow,
        .paragraphStyle: paragraph
    ])
}

do {
    guard CommandLine.arguments.count == 3 else { throw ArtworkError.usage }
    let manifest = URL(fileURLWithPath: CommandLine.arguments[1])
    let output = URL(fileURLWithPath: CommandLine.arguments[2], isDirectory: true)
    try FileManager.default.createDirectory(at: output, withIntermediateDirectories: true)
    let cues = try JSONDecoder().decode([Cue].self, from: Data(contentsOf: manifest))
    for cue in cues {
        let text = label(cue.text, kind: cue.kind)
        try canvas(720, 1280, draw: {
            let bounds = NSRect(x: 45, y: 1280 - 1080 - 130, width: 630, height: 130)
            text.draw(with: bounds, options: [.usesLineFragmentOrigin, .usesFontLeading])
            let fill = NSMutableAttributedString(attributedString: text)
            let range = NSRange(location: 0, length: fill.length)
            fill.removeAttribute(.strokeWidth, range: range)
            fill.removeAttribute(.strokeColor, range: range)
            fill.removeAttribute(.shadow, range: range)
            fill.draw(with: bounds, options: [.usesLineFragmentOrigin, .usesFontLeading])
        }, output: output.appendingPathComponent(cue.id + ".png"))
    }
} catch {
    FileHandle.standardError.write(Data("Artwork error: \(error)\n".utf8))
    exit(1)
}
