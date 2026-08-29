#!/usr/bin/env swift

import AppKit
import CoreText
import Foundation

enum CoverError: Error, CustomStringConvertible {
    case usage, invalidImage, unavailableFont, bitmapCreation, pngEncoding

    var description: String {
        switch self {
        case .usage: return "usage: render_jingci_lotus_cover.swift <base.png> <output.png>"
        case .invalidImage: return "unable to load Jingci lotus cover base image"
        case .unavailableFont: return "required Chinese fonts are unavailable"
        case .bitmapCreation: return "unable to create cover bitmap"
        case .pngEncoding: return "unable to encode cover PNG"
        }
    }
}

let width: CGFloat = 1080
let height: CGFloat = 1920
let titleIvory = NSColor(calibratedRed: 0.98, green: 0.93, blue: 0.83, alpha: 1)
let quietIvory = NSColor(calibratedRed: 0.92, green: 0.87, blue: 0.77, alpha: 1)

func attributes(font: NSFont, color: NSColor, shadowAlpha: CGFloat) -> [NSAttributedString.Key: Any] {
    let shadow = NSShadow()
    shadow.shadowColor = NSColor(calibratedWhite: 0.01, alpha: shadowAlpha)
    shadow.shadowBlurRadius = 7
    shadow.shadowOffset = NSSize(width: 2, height: -2)
    return [.font: font, .foregroundColor: color, .shadow: shadow]
}

func drawVertical(
    _ text: String,
    x: CGFloat,
    top: CGFloat,
    step: CGFloat,
    font: NSFont,
    color: NSColor,
    shadowAlpha: CGFloat
) {
    for (index, character) in text.enumerated() {
        let glyph = NSAttributedString(
            string: String(character),
            attributes: attributes(font: font, color: color, shadowAlpha: shadowAlpha)
        )
        let size = glyph.size()
        let yFromTop = top + CGFloat(index) * step
        glyph.draw(in: NSRect(
            x: x - size.width / 2,
            y: height - yFromTop - size.height,
            width: size.width + 12,
            height: size.height + 12
        ))
    }
}

do {
    guard CommandLine.arguments.count == 3 else { throw CoverError.usage }
    let baseURL = URL(fileURLWithPath: CommandLine.arguments[1])
    let outputURL = URL(fileURLWithPath: CommandLine.arguments[2])
    guard let base = NSImage(contentsOf: baseURL) else { throw CoverError.invalidImage }

    let xingkaiURL = URL(fileURLWithPath: "/System/Library/AssetsV2/com_apple_MobileAsset_Font7/aa99d0b2bad7f797f38b49d46cde28fd4b58876e.asset/AssetData/Xingkai.ttc")
    let kaitiURL = URL(fileURLWithPath: "/System/Library/AssetsV2/com_apple_MobileAsset_Font7/54a2ad3dac6cac875ad675d7d273dc425010a877.asset/AssetData/Kaiti.ttc")
    CTFontManagerRegisterFontsForURL(xingkaiURL as CFURL, .process, nil)
    CTFontManagerRegisterFontsForURL(kaitiURL as CFURL, .process, nil)

    guard let titleFont = NSFont(name: "STXingkaiSC-Bold", size: 86),
          let nameFont = NSFont(name: "STKaitiSC-Regular", size: 46),
          let creditFont = NSFont(name: "STKaitiSC-Regular", size: 29) else {
        throw CoverError.unavailableFont
    }

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
        bitsPerPixel: 32
    ), let context = NSGraphicsContext(bitmapImageRep: bitmap) else {
        throw CoverError.bitmapCreation
    }

    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.current = context
    base.draw(in: NSRect(x: 0, y: 0, width: width, height: height))

    drawVertical(
        "杨万里《晓出净慈寺送林子方》",
        x: 738, top: 150, step: 34,
        font: creditFont, color: quietIvory, shadowAlpha: 0.58
    )
    drawVertical(
        "荷花一舞",
        x: 884, top: 166, step: 110,
        font: titleFont, color: titleIvory, shadowAlpha: 0.70
    )
    drawVertical(
        "栀夏",
        x: 1010, top: 170, step: 62,
        font: nameFont, color: quietIvory, shadowAlpha: 0.62
    )

    NSGraphicsContext.restoreGraphicsState()

    guard let png = bitmap.representation(using: .png, properties: [:]) else {
        throw CoverError.pngEncoding
    }
    try FileManager.default.createDirectory(
        at: outputURL.deletingLastPathComponent(),
        withIntermediateDirectories: true
    )
    try png.write(to: outputURL, options: .atomic)
} catch {
    FileHandle.standardError.write(Data("error: \(error)\n".utf8))
    exit(1)
}
