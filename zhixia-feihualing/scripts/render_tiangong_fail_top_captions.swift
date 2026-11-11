import AppKit
import Foundation

struct Cue: Decodable {
    let id: String
    let text: String
    let start: Double
    let end: Double
    let kind: String
    let placement: String?
    let fontSize: Double?
}

enum ArtworkError: Error { case usage, bitmap, encode }

func attributedCaption(_ value: String, kind: String, fontSize: Double?) -> NSAttributedString {
    let paragraph = NSMutableParagraphStyle()
    paragraph.alignment = .center
    paragraph.lineSpacing = 4
    let shadow = NSShadow()
    shadow.shadowColor = NSColor(calibratedWhite: 0.05, alpha: 0.78)
    shadow.shadowBlurRadius = 4
    shadow.shadowOffset = NSSize(width: 1, height: -2)
    return NSAttributedString(string: value, attributes: [
        .font: NSFont.systemFont(ofSize: CGFloat(fontSize ?? (kind == "dialogue" ? 42 : 43)), weight: .bold),
        .foregroundColor: NSColor(calibratedRed: 1.0, green: 0.97, blue: 0.90, alpha: 1.0),
        .strokeColor: NSColor(calibratedRed: 0.16, green: 0.10, blue: 0.07, alpha: 1.0),
        .strokeWidth: -4.2,
        .shadow: shadow,
        .paragraphStyle: paragraph
    ])
}

func drawFilled(_ text: NSAttributedString, in bounds: NSRect) {
    text.draw(with: bounds, options: [.usesLineFragmentOrigin, .usesFontLeading])
    let fill = NSMutableAttributedString(attributedString: text)
    let range = NSRange(location: 0, length: fill.length)
    fill.removeAttribute(.strokeWidth, range: range)
    fill.removeAttribute(.strokeColor, range: range)
    fill.removeAttribute(.shadow, range: range)
    fill.draw(with: bounds, options: [.usesLineFragmentOrigin, .usesFontLeading])
}

do {
    guard CommandLine.arguments.count == 3 else { throw ArtworkError.usage }
    let manifestURL = URL(fileURLWithPath: CommandLine.arguments[1])
    let outputURL = URL(fileURLWithPath: CommandLine.arguments[2], isDirectory: true)
    try FileManager.default.createDirectory(at: outputURL, withIntermediateDirectories: true)
    let cues = try JSONDecoder().decode([Cue].self, from: Data(contentsOf: manifestURL))

    for cue in cues {
        guard let bitmap = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: 720, pixelsHigh: 1280,
            bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false,
            colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0),
            let context = NSGraphicsContext(bitmapImageRep: bitmap) else { throw ArtworkError.bitmap }
        NSGraphicsContext.saveGraphicsState()
        NSGraphicsContext.current = context
        NSColor.clear.setFill()
        NSRect(x: 0, y: 0, width: 720, height: 1280).fill()
        let caption = attributedCaption(cue.text, kind: cue.kind, fontSize: cue.fontSize)
        let top = cue.placement == "bottom" ? CGFloat(1080) : CGFloat(112)
        let bounds = NSRect(x: 38, y: 1280 - top - 150, width: 644, height: 150)
        drawFilled(caption, in: bounds)
        NSGraphicsContext.restoreGraphicsState()
        guard let data = bitmap.representation(using: .png, properties: [:]) else { throw ArtworkError.encode }
        try data.write(to: outputURL.appendingPathComponent(cue.id + ".png"), options: .atomic)
    }
} catch {
    FileHandle.standardError.write(Data("Artwork error: \(error)\n".utf8))
    exit(1)
}
