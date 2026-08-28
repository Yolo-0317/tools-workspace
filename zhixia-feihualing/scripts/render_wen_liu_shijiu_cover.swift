#!/usr/bin/env swift

import AppKit
import CoreText
import Foundation

enum CoverError: Error { case usage, invalidImage, unavailableFont, pngEncoding }
let width: CGFloat = 941
let height: CGFloat = 1672
let warmWhite = NSColor(calibratedRed: 1.0, green: 0.97, blue: 0.88, alpha: 1)
let warmGold = NSColor(calibratedRed: 0.92, green: 0.72, blue: 0.39, alpha: 1)
let vermilion = NSColor(calibratedRed: 0.96, green: 0.16, blue: 0.07, alpha: 1)

func drawCharacter(_ character: Character, x: CGFloat, yFromTop: CGFloat, font: NSFont, color: NSColor) {
    let shadow = NSShadow()
    shadow.shadowColor = NSColor(calibratedWhite: 0, alpha: 0.9)
    shadow.shadowBlurRadius = 6
    shadow.shadowOffset = NSSize(width: 2, height: -2)
    let text = String(character)
    let outline = NSAttributedString(string: text, attributes: [
        .font: font, .foregroundColor: color,
        .strokeColor: NSColor(calibratedWhite: 0.01, alpha: 0.9), .strokeWidth: 2.0,
        .shadow: shadow
    ])
    let fill = NSAttributedString(string: text, attributes: [.font: font, .foregroundColor: color, .shadow: shadow])
    let size = fill.size()
    let rect = NSRect(x: x - size.width / 2, y: height - yFromTop - size.height, width: size.width + 10, height: size.height + 10)
    outline.draw(in: rect)
    fill.draw(in: rect)
}

func drawVertical(_ text: String, x: CGFloat, top: CGFloat, step: CGFloat, font: NSFont, firstRed: Bool = false, color: NSColor = warmWhite) {
    for (index, character) in text.enumerated() {
        drawCharacter(character, x: x, yFromTop: top + CGFloat(index) * step, font: font,
                      color: firstRed && index == 0 ? vermilion : color)
    }
}

do {
    guard CommandLine.arguments.count == 3 else { throw CoverError.usage }
    guard let base = NSImage(contentsOfFile: CommandLine.arguments[1]) else { throw CoverError.invalidImage }
    let fontURL = URL(fileURLWithPath: "/System/Library/AssetsV2/com_apple_MobileAsset_Font7/aa99d0b2bad7f797f38b49d46cde28fd4b58876e.asset/AssetData/Xingkai.ttc")
    CTFontManagerRegisterFontsForURL(fontURL as CFURL, .process, nil)
    guard let hookFont = NSFont(name: "STXingkaiSC-Light", size: 82),
          let titleFont = NSFont(name: "STXingkaiSC-Light", size: 48) else { throw CoverError.unavailableFont }
    guard let bitmap = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: Int(width), pixelsHigh: Int(height), bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false, colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0), let context = NSGraphicsContext(bitmapImageRep: bitmap) else { throw CoverError.invalidImage }
    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.current = context
    base.draw(in: NSRect(x: 0, y: 0, width: width, height: height))
    drawVertical("雪都下了", x: 410, top: 105, step: 88, font: hookFont, firstRed: true)
    drawVertical("他还会来吗？", x: 285, top: 105, step: 76, font: hookFont)
    drawVertical("问刘十九", x: 710, top: 120, step: 58, font: titleFont, color: warmGold)
    NSGraphicsContext.restoreGraphicsState()
    guard let png = bitmap.representation(using: .png, properties: [:]) else { throw CoverError.pngEncoding }
    let output = URL(fileURLWithPath: CommandLine.arguments[2])
    try FileManager.default.createDirectory(at: output.deletingLastPathComponent(), withIntermediateDirectories: true)
    try png.write(to: output, options: .atomic)
} catch {
    FileHandle.standardError.write(Data("error: \(error)\n".utf8))
    exit(1)
}
