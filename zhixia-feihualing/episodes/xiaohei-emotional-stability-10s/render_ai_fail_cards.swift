#!/usr/bin/env swift

import AppKit
import Foundation

struct Card: Decodable { let id: String; let text: String }
enum RenderError: Error { case usage, bitmap, encode }

func render(_ card: Card, to output: URL) throws {
    let width = 1080
    let height = 283
    guard let bitmap = NSBitmapImageRep(
        bitmapDataPlanes: nil, pixelsWide: width, pixelsHigh: height,
        bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false,
        colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0
    ), let context = NSGraphicsContext(bitmapImageRep: bitmap) else { throw RenderError.bitmap }

    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.current = context
    NSColor(calibratedRed: 0.08, green: 0.10, blue: 0.11, alpha: 1).setFill()
    NSRect(x: 0, y: 0, width: width, height: height).fill()

    let label = NSAttributedString(string: "小黑片场  /  AI 废片实录", attributes: [
        .font: NSFont(name: "PingFangSC-Medium", size: 31) ?? NSFont.systemFont(ofSize: 31, weight: .medium),
        .foregroundColor: NSColor(calibratedRed: 0.92, green: 0.69, blue: 0.40, alpha: 1)
    ])
    label.draw(at: NSPoint(x: 70, y: 224))
    NSColor(calibratedRed: 0.45, green: 0.39, blue: 0.31, alpha: 1).setFill()
    NSRect(x: 70, y: 208, width: 940, height: 2).fill()

    let lines = card.text.components(separatedBy: "\n")
    let font = NSFont(name: "PingFangSC-Semibold", size: 66) ?? NSFont.systemFont(ofSize: 66, weight: .semibold)
    for (index, line) in lines.enumerated() {
        let text = NSAttributedString(string: line, attributes: [
            .font: font,
            .foregroundColor: NSColor(calibratedWhite: 0.98, alpha: 1)
        ])
        let y: CGFloat = lines.count == 1 ? 83 : (index == 0 ? 122 : 41)
        text.draw(at: NSPoint(x: 70, y: y))
    }
    NSGraphicsContext.restoreGraphicsState()

    guard let png = bitmap.representation(using: .png, properties: [:]) else { throw RenderError.encode }
    try png.write(to: output, options: .atomic)
}

do {
    guard CommandLine.arguments.count == 3 else { throw RenderError.usage }
    let manifest = URL(fileURLWithPath: CommandLine.arguments[1])
    let output = URL(fileURLWithPath: CommandLine.arguments[2], isDirectory: true)
    let cards = try JSONDecoder().decode([Card].self, from: Data(contentsOf: manifest))
    try FileManager.default.createDirectory(at: output, withIntermediateDirectories: true)
    for card in cards { try render(card, to: output.appendingPathComponent("\(card.id).png")) }
} catch {
    FileHandle.standardError.write(Data("Render failed: \(error)\n".utf8))
    exit(1)
}
