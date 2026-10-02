#!/usr/bin/env swift

import AppKit
import Foundation

struct Subtitle: Decodable {
    let id: String
    let text: String
}

enum RenderError: Error { case usage, bitmap, encode }

func render(_ item: Subtitle, to output: URL) throws {
    let width = 720
    let height = 1280
    guard let bitmap = NSBitmapImageRep(
        bitmapDataPlanes: nil, pixelsWide: width, pixelsHigh: height,
        bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false,
        colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0
    ), let context = NSGraphicsContext(bitmapImageRep: bitmap) else { throw RenderError.bitmap }

    let font = NSFont.systemFont(ofSize: 38, weight: .bold)
    let shadow = NSShadow()
    shadow.shadowColor = NSColor(calibratedWhite: 0.0, alpha: 0.72)
    shadow.shadowBlurRadius = 2
    shadow.shadowOffset = NSSize(width: 1, height: -1)
    let outline = NSAttributedString(string: item.text, attributes: [
        .font: font,
        .foregroundColor: NSColor.white,
        .strokeColor: NSColor(calibratedWhite: 0.06, alpha: 0.94),
        .strokeWidth: -2.4,
        .shadow: shadow
    ])
    let fill = NSAttributedString(string: item.text, attributes: [
        .font: font,
        .foregroundColor: NSColor.white
    ])
    let size = outline.size()

    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.current = context
    NSColor.clear.setFill()
    NSRect(x: 0, y: 0, width: width, height: height).fill()
    let point = NSPoint(x: (CGFloat(width) - size.width) / 2, y: CGFloat(height) - 142 - size.height)
    outline.draw(at: point)
    fill.draw(at: point)
    NSGraphicsContext.restoreGraphicsState()

    guard let png = bitmap.representation(using: .png, properties: [:]) else { throw RenderError.encode }
    try png.write(to: output, options: .atomic)
}

do {
    guard CommandLine.arguments.count == 3 else { throw RenderError.usage }
    let manifest = URL(fileURLWithPath: CommandLine.arguments[1])
    let output = URL(fileURLWithPath: CommandLine.arguments[2], isDirectory: true)
    let items = try JSONDecoder().decode([Subtitle].self, from: Data(contentsOf: manifest))
    try FileManager.default.createDirectory(at: output, withIntermediateDirectories: true)
    for item in items {
        try render(item, to: output.appendingPathComponent("\(item.id).png"))
    }
} catch {
    FileHandle.standardError.write(Data("Subtitle render error: \(error)\n".utf8))
    exit(1)
}
