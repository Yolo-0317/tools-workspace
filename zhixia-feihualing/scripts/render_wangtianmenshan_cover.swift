#!/usr/bin/env swift
import AppKit
import CoreText
import Foundation

enum CoverError: Error { case usage, invalidImage, unavailableFont, bitmapCreation, pngEncoding }
let width: CGFloat = 1080
let height: CGFloat = 1920
let titleIvory = NSColor(calibratedRed: 0.99, green: 0.94, blue: 0.82, alpha: 1)
let quietIvory = NSColor(calibratedRed: 0.94, green: 0.88, blue: 0.75, alpha: 1)

func attrs(_ font: NSFont, _ color: NSColor, _ alpha: CGFloat) -> [NSAttributedString.Key: Any] {
    let shadow = NSShadow()
    shadow.shadowColor = NSColor(calibratedWhite: 0.01, alpha: alpha)
    shadow.shadowBlurRadius = 9
    shadow.shadowOffset = NSSize(width: 2, height: -3)
    return [.font: font, .foregroundColor: color, .shadow: shadow]
}

func drawVertical(_ text: String, x: CGFloat, top: CGFloat, step: CGFloat, font: NSFont, color: NSColor, shadow: CGFloat) {
    for (index, character) in text.enumerated() {
        let glyph = NSAttributedString(string: String(character), attributes: attrs(font, color, shadow))
        let size = glyph.size()
        glyph.draw(in: NSRect(x: x - size.width / 2, y: height - top - CGFloat(index) * step - size.height, width: size.width + 12, height: size.height + 12))
    }
}

do {
    guard CommandLine.arguments.count == 3 else { throw CoverError.usage }
    guard let base = NSImage(contentsOfFile: CommandLine.arguments[1]) else { throw CoverError.invalidImage }
    let xingkai = URL(fileURLWithPath: "/System/Library/AssetsV2/com_apple_MobileAsset_Font7/aa99d0b2bad7f797f38b49d46cde28fd4b58876e.asset/AssetData/Xingkai.ttc")
    let kaiti = URL(fileURLWithPath: "/System/Library/AssetsV2/com_apple_MobileAsset_Font7/54a2ad3dac6cac875ad675d7d273dc425010a877.asset/AssetData/Kaiti.ttc")
    CTFontManagerRegisterFontsForURL(xingkai as CFURL, .process, nil)
    CTFontManagerRegisterFontsForURL(kaiti as CFURL, .process, nil)
    guard let titleFont = NSFont(name: "STXingkaiSC-Bold", size: 90), let creditFont = NSFont(name: "STKaitiSC-Regular", size: 29) else { throw CoverError.unavailableFont }
    guard let bitmap = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: Int(width), pixelsHigh: Int(height), bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false, colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 32), let context = NSGraphicsContext(bitmapImageRep: bitmap) else { throw CoverError.bitmapCreation }
    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.current = context
    base.draw(in: NSRect(x: 0, y: 0, width: width, height: height))
    drawVertical("李白《望天门山》", x: 55, top: 176, step: 33, font: creditFont, color: quietIvory, shadow: 0.62)
    drawVertical("一舞入青山", x: 170, top: 168, step: 111, font: titleFont, color: titleIvory, shadow: 0.76)
    NSGraphicsContext.restoreGraphicsState()
    guard let png = bitmap.representation(using: .png, properties: [:]) else { throw CoverError.pngEncoding }
    try png.write(to: URL(fileURLWithPath: CommandLine.arguments[2]), options: .atomic)
} catch {
    FileHandle.standardError.write(Data("error: \(error)\n".utf8))
    exit(1)
}
