#!/usr/bin/env swift

import AppKit
import CoreText
import Foundation

enum PreviewError: Error {
    case usage
    case fontUnavailable
    case bitmapCreation
    case pngEncoding
}

let canvasWidth = 720
let canvasHeight = 1280

func makeBitmap() throws -> (NSBitmapImageRep, NSGraphicsContext) {
    guard let bitmap = NSBitmapImageRep(
        bitmapDataPlanes: nil,
        pixelsWide: canvasWidth,
        pixelsHigh: canvasHeight,
        bitsPerSample: 8,
        samplesPerPixel: 4,
        hasAlpha: true,
        isPlanar: false,
        colorSpaceName: .deviceRGB,
        bytesPerRow: 0,
        bitsPerPixel: 0
    ), let context = NSGraphicsContext(bitmapImageRep: bitmap) else {
        throw PreviewError.bitmapCreation
    }
    return (bitmap, context)
}

func drawVerticalColumn(
    _ text: String,
    x: CGFloat,
    top: CGFloat,
    font: NSFont,
    highlight: Character
) {
    let normalColor = NSColor(calibratedWhite: 1.0, alpha: 1)
    let highlightColor = NSColor(calibratedRed: 1.0, green: 0.12, blue: 0.08, alpha: 1)
    let shadow = NSShadow()
    shadow.shadowColor = NSColor(calibratedWhite: 0.02, alpha: 0.78)
    shadow.shadowBlurRadius = 2.5
    shadow.shadowOffset = NSSize(width: 1.8, height: -1.8)

    let step: CGFloat = 67
    for (index, character) in text.enumerated() {
        let string = String(character)
        let attributes: [NSAttributedString.Key: Any] = [
            .font: font,
            .foregroundColor: character == highlight ? highlightColor : normalColor,
            .strokeColor: character == highlight
                ? NSColor(calibratedRed: 0.42, green: 0.02, blue: 0.01, alpha: 0.72)
                : NSColor(calibratedWhite: 0.03, alpha: 0.62),
            .strokeWidth: -0.35,
            .shadow: shadow
        ]
        let attributed = NSAttributedString(string: string, attributes: attributes)
        let size = attributed.size()
        let screenY = top + CGFloat(index) * step
        let rect = NSRect(
            x: x - size.width / 2,
            y: CGFloat(canvasHeight) - screenY - size.height,
            width: size.width + 4,
            height: size.height + 4
        )
        attributed.draw(in: rect)
    }
}

do {
    guard CommandLine.arguments.count == 2 else { throw PreviewError.usage }
    let fontURL = URL(fileURLWithPath: "/System/Library/AssetsV2/com_apple_MobileAsset_Font7/aa99d0b2bad7f797f38b49d46cde28fd4b58876e.asset/AssetData/Xingkai.ttc")
    CTFontManagerRegisterFontsForURL(fontURL as CFURL, .process, nil)
    guard let font = NSFont(name: "STXingkaiSC-Light", size: 62) else {
        throw PreviewError.fontUnavailable
    }

    let (bitmap, context) = try makeBitmap()
    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.current = context
    NSColor.clear.setFill()
    NSRect(x: 0, y: 0, width: canvasWidth, height: canvasHeight).fill()

    // 竖排从上到下、列从右到左；视觉标点省略，让画面更克制。
    drawVerticalColumn("夜来风雨声", x: 151, top: 94, font: font, highlight: "花")
    drawVerticalColumn("花落知多少", x: 78, top: 94, font: font, highlight: "花")

    NSGraphicsContext.restoreGraphicsState()
    guard let png = bitmap.representation(using: .png, properties: [:]) else {
        throw PreviewError.pngEncoding
    }
    try png.write(to: URL(fileURLWithPath: CommandLine.arguments[1]), options: .atomic)
} catch {
    FileHandle.standardError.write(Data("error: \(error)\n".utf8))
    exit(1)
}
