#!/usr/bin/env swift

import AppKit
import CoreText
import Foundation

enum CoverError: Error { case usage, invalidImage, unavailableFont, pngEncoding }

let width: CGFloat = 941
let height: CGFloat = 1672
let inkBrown = NSColor(calibratedRed: 0.22, green: 0.17, blue: 0.14, alpha: 1)
let paleGold = NSColor(calibratedRed: 0.95, green: 0.84, blue: 0.63, alpha: 0.95)

func drawVertical(_ text: String, x: CGFloat, top: CGFloat, step: CGFloat, font: NSFont) {
    let shadow = NSShadow()
    shadow.shadowColor = NSColor(calibratedWhite: 0, alpha: 0.24)
    shadow.shadowBlurRadius = 3
    shadow.shadowOffset = NSSize(width: 2, height: -2)

    for (index, character) in text.enumerated() {
        let string = String(character)
        let outlined = NSAttributedString(string: string, attributes: [
            .font: font,
            .foregroundColor: inkBrown,
            .strokeColor: paleGold,
            .strokeWidth: 2.0,
            .shadow: shadow
        ])
        let filled = NSAttributedString(string: string, attributes: [
            .font: font,
            .foregroundColor: inkBrown,
            .shadow: shadow
        ])
        let size = filled.size()
        let yFromTop = top + CGFloat(index) * step
        let rect = NSRect(
            x: x - size.width / 2,
            y: height - yFromTop - size.height,
            width: size.width + 12,
            height: size.height + 12
        )
        outlined.draw(in: rect)
        filled.draw(in: rect)
    }
}

do {
    guard CommandLine.arguments.count == 3 else { throw CoverError.usage }
    guard let base = NSImage(contentsOfFile: CommandLine.arguments[1]) else { throw CoverError.invalidImage }

    let fontURL = URL(fileURLWithPath: "/System/Library/AssetsV2/com_apple_MobileAsset_Font7/aa99d0b2bad7f797f38b49d46cde28fd4b58876e.asset/AssetData/Xingkai.ttc")
    CTFontManagerRegisterFontsForURL(fontURL as CFURL, .process, nil)
    guard let font = NSFont(name: "STXingkaiSC-Light", size: 92) else { throw CoverError.unavailableFont }

    guard let bitmap = NSBitmapImageRep(
        bitmapDataPlanes: nil,
        pixelsWide: Int(width),
        pixelsHigh: Int(height),
        bitsPerSample: 8,
        samplesPerPixel: 4,
        hasAlpha: true,
        isPlanar: false,
        colorSpaceName: .deviceRGB,
        bytesPerRow: 0,
        bitsPerPixel: 0
    ), let context = NSGraphicsContext(bitmapImageRep: bitmap) else { throw CoverError.invalidImage }

    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.current = context
    base.draw(in: NSRect(x: 0, y: 0, width: width, height: height))
    drawVertical("信已封好", x: 268, top: 205, step: 112, font: font)
    drawVertical("为何又拆？", x: 118, top: 265, step: 108, font: font)
    NSGraphicsContext.restoreGraphicsState()

    guard let png = bitmap.representation(using: .png, properties: [:]) else { throw CoverError.pngEncoding }
    let output = URL(fileURLWithPath: CommandLine.arguments[2])
    try png.write(to: output, options: .atomic)
} catch {
    FileHandle.standardError.write(Data("error: \(error)\n".utf8))
    exit(1)
}
