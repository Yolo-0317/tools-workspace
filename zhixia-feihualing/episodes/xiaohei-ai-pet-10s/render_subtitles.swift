import AppKit
import Foundation

struct Cue: Decodable {
    let id: String
    let text: String
}

guard CommandLine.arguments.count == 3 else {
    fatalError("Usage: render_subtitles.swift subtitles.json output-directory")
}

let manifest = URL(fileURLWithPath: CommandLine.arguments[1])
let output = URL(fileURLWithPath: CommandLine.arguments[2], isDirectory: true)
let cues = try JSONDecoder().decode([Cue].self, from: Data(contentsOf: manifest))

for cue in cues {
    guard let bitmap = NSBitmapImageRep(
        bitmapDataPlanes: nil, pixelsWide: 720, pixelsHigh: 1280,
        bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true,
        isPlanar: false, colorSpaceName: .deviceRGB,
        bytesPerRow: 0, bitsPerPixel: 0
    ), let context = NSGraphicsContext(bitmapImageRep: bitmap) else {
        fatalError("Cannot create subtitle canvas")
    }
    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.current = context
    NSColor.clear.setFill()
    NSRect(x: 0, y: 0, width: 720, height: 1280).fill()

    let shadow = NSShadow()
    shadow.shadowColor = NSColor(calibratedRed: 0.16, green: 0.10, blue: 0.07, alpha: 0.75)
    shadow.shadowBlurRadius = 3
    shadow.shadowOffset = NSSize(width: 1, height: -2)
    let text = NSAttributedString(string: cue.text, attributes: [
        .font: NSFont.systemFont(ofSize: 36, weight: .bold),
        .foregroundColor: NSColor.white,
        .strokeColor: NSColor(calibratedRed: 0.20, green: 0.13, blue: 0.09, alpha: 1),
        .strokeWidth: -4.0,
        .shadow: shadow
    ])
    let size = text.size()
    let point = NSPoint(x: (720 - size.width) / 2, y: 1280 - 1080 - size.height)
    text.draw(at: point)
    let fill = NSMutableAttributedString(attributedString: text)
    let range = NSRange(location: 0, length: fill.length)
    fill.removeAttribute(.strokeWidth, range: range)
    fill.removeAttribute(.strokeColor, range: range)
    fill.removeAttribute(.shadow, range: range)
    fill.draw(at: point)

    NSGraphicsContext.restoreGraphicsState()
    guard let data = bitmap.representation(using: .png, properties: [:]) else {
        fatalError("Cannot encode subtitle PNG")
    }
    try data.write(to: output.appendingPathComponent(cue.id + ".png"), options: .atomic)
}
