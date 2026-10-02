#!/usr/bin/env swift

import AppKit
import Foundation

enum CoverError: Error { case usage, image, bitmap, encode }

do {
    guard CommandLine.arguments.count == 3 else { throw CoverError.usage }
    let input = URL(fileURLWithPath: CommandLine.arguments[1])
    let output = URL(fileURLWithPath: CommandLine.arguments[2])
    guard let frame = NSImage(contentsOf: input) else { throw CoverError.image }
    guard let bitmap = NSBitmapImageRep(
        bitmapDataPlanes: nil, pixelsWide: 1080, pixelsHigh: 1920,
        bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false,
        colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0
    ), let context = NSGraphicsContext(bitmapImageRep: bitmap) else { throw CoverError.bitmap }

    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.current = context
    NSColor(calibratedRed: 0.08, green: 0.10, blue: 0.11, alpha: 1).setFill()
    NSRect(x: 0, y: 0, width: 1080, height: 1920).fill()
    frame.draw(in: NSRect(x: 70, y: 0, width: 940, height: 1637), from: .zero, operation: .copy, fraction: 1)

    let label = NSAttributedString(string: "小黑片场  /  AI 废片实录", attributes: [
        .font: NSFont(name: "PingFangSC-Medium", size: 32) ?? NSFont.systemFont(ofSize: 32, weight: .medium),
        .foregroundColor: NSColor(calibratedRed: 0.92, green: 0.69, blue: 0.40, alpha: 1)
    ])
    label.draw(at: NSPoint(x: 70, y: 1877))
    let font = NSFont(name: "PingFangSC-Semibold", size: 101) ?? NSFont.systemFont(ofSize: 101, weight: .semibold)
    for (line, y) in [("嘴不动", CGFloat(1760)), ("饭照吃", CGFloat(1645))] {
        NSAttributedString(string: line, attributes: [
            .font: font,
            .foregroundColor: NSColor(calibratedWhite: 0.98, alpha: 1)
        ]).draw(at: NSPoint(x: 70, y: y))
    }
    NSGraphicsContext.restoreGraphicsState()

    guard let png = bitmap.representation(using: .png, properties: [:]) else { throw CoverError.encode }
    try png.write(to: output, options: .atomic)
} catch {
    FileHandle.standardError.write(Data("Cover render failed: \(error)\n".utf8))
    exit(1)
}
