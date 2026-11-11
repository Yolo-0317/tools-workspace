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
    let background = NSColor(calibratedRed: 0.18, green: 0.14, blue: 0.11, alpha: 1)
    background.setFill()
    NSRect(x: 0, y: 0, width: 1080, height: 1920).fill()

    // Preserve the whole source frame: TV, fan, gamepad and the small AI mark.
    frame.draw(in: NSRect(x: 70, y: 0, width: 940, height: 1637),
               from: .zero, operation: .copy, fraction: 1)

    let gold = NSColor(calibratedRed: 0.94, green: 0.75, blue: 0.48, alpha: 1)
    NSAttributedString(string: "那个暑假的下午", attributes: [
        .font: NSFont(name: "PingFangSC-Medium", size: 34) ?? NSFont.systemFont(ofSize: 34, weight: .medium),
        .foregroundColor: gold
    ]).draw(at: NSPoint(x: 70, y: 1860))

    NSAttributedString(string: "小霸王一开", attributes: [
        .font: NSFont(name: "PingFangSC-Semibold", size: 91) ?? NSFont.systemFont(ofSize: 91, weight: .semibold),
        .foregroundColor: NSColor.white
    ]).draw(at: NSPoint(x: 65, y: 1743))

    NSAttributedString(string: "暑假好像过不完", attributes: [
        .font: NSFont(name: "PingFangSC-Medium", size: 57) ?? NSFont.systemFont(ofSize: 57, weight: .medium),
        .foregroundColor: gold
    ]).draw(at: NSPoint(x: 70, y: 1660))
    NSGraphicsContext.restoreGraphicsState()

    guard let png = bitmap.representation(using: .png, properties: [:]) else { throw CoverError.encode }
    try png.write(to: output, options: .atomic)
} catch {
    FileHandle.standardError.write(Data("Cover render failed: \(error)\n".utf8))
    exit(1)
}
