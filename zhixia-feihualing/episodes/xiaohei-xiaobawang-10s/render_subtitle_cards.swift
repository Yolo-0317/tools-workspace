#!/usr/bin/env swift

import AppKit
import Foundation

struct Cue: Decodable { let id: String; let text: String }
enum RenderError: Error { case usage, bitmap, encode }

do {
    guard CommandLine.arguments.count == 3 else { throw RenderError.usage }
    let manifest = URL(fileURLWithPath: CommandLine.arguments[1])
    let output = URL(fileURLWithPath: CommandLine.arguments[2], isDirectory: true)
    let cues = try JSONDecoder().decode([Cue].self, from: Data(contentsOf: manifest))
    try FileManager.default.createDirectory(at: output, withIntermediateDirectories: true)

    for cue in cues {
        guard let bitmap = NSBitmapImageRep(
            bitmapDataPlanes: nil, pixelsWide: 1080, pixelsHigh: 1920,
            bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true,
            isPlanar: false, colorSpaceName: .deviceRGB,
            bytesPerRow: 0, bitsPerPixel: 0
        ), let context = NSGraphicsContext(bitmapImageRep: bitmap) else { throw RenderError.bitmap }
        NSGraphicsContext.saveGraphicsState()
        NSGraphicsContext.current = context
        NSColor.clear.setFill()
        NSRect(x: 0, y: 0, width: 1080, height: 1920).fill()

        let shadow = NSShadow()
        shadow.shadowColor = NSColor(calibratedRed: 0.16, green: 0.10, blue: 0.07, alpha: 0.75)
        shadow.shadowBlurRadius = 4
        shadow.shadowOffset = NSSize(width: 1, height: -2)
        let font = NSFont(name: "PingFangSC-Semibold", size: 58) ?? NSFont.systemFont(ofSize: 58, weight: .semibold)
        let text = NSAttributedString(string: cue.text, attributes: [
            .font: font,
            .foregroundColor: NSColor.white,
            .strokeColor: NSColor(calibratedRed: 0.20, green: 0.13, blue: 0.09, alpha: 1),
            .strokeWidth: -4.0,
            .shadow: shadow
        ])
        let size = text.size()
        let point = NSPoint(x: (1080 - size.width) / 2, y: 1920 - 1540 - size.height)
        text.draw(at: point)
        let fill = NSMutableAttributedString(attributedString: text)
        let range = NSRange(location: 0, length: fill.length)
        fill.removeAttribute(.strokeWidth, range: range)
        fill.removeAttribute(.strokeColor, range: range)
        fill.removeAttribute(.shadow, range: range)
        fill.draw(at: point)

        NSGraphicsContext.restoreGraphicsState()
        guard let png = bitmap.representation(using: .png, properties: [:]) else { throw RenderError.encode }
        try png.write(to: output.appendingPathComponent("\(cue.id).png"), options: .atomic)
    }
} catch {
    FileHandle.standardError.write(Data("Subtitle render failed: \(error)\n".utf8))
    exit(1)
}
