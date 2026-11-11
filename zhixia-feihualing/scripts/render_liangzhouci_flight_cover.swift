#!/usr/bin/env swift

import AppKit
import CoreText
import Foundation

enum CoverError: Error, CustomStringConvertible {
    case usage, invalidImage, unavailableFont, bitmapCreation, pngEncoding

    var description: String {
        switch self {
        case .usage: return "usage: render_liangzhouci_flight_cover.swift <base.png> <output.png>"
        case .invalidImage: return "unable to load Liangzhouci flight cover base image"
        case .unavailableFont: return "required Chinese fonts are unavailable"
        case .bitmapCreation: return "unable to create cover bitmap"
        case .pngEncoding: return "unable to encode cover PNG"
        }
    }
}

let width: CGFloat = 1080
let height: CGFloat = 1920
let titleIvory = NSColor(calibratedRed: 0.99, green: 0.94, blue: 0.82, alpha: 1)
let quietIvory = NSColor(calibratedRed: 0.94, green: 0.88, blue: 0.75, alpha: 1)

func attributes(font: NSFont, color: NSColor, shadowAlpha: CGFloat) -> [NSAttributedString.Key: Any] {
    let shadow = NSShadow()
    shadow.shadowColor = NSColor(calibratedWhite: 0.02, alpha: shadowAlpha)
    shadow.shadowBlurRadius = 9
    shadow.shadowOffset = NSSize(width: 2, height: -3)
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

    guard let titleFont = NSFont(name: "STXingkaiSC-Bold", size: 90),
          let roleFont = NSFont(name: "STKaitiSC-Regular", size: 39),
          let creditFont = NSFont(name: "STKaitiSC-Regular", size: 28) else {
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
        "王之涣《凉州词》",
        x: 54, top: 176, step: 33,
        font: creditFont, color: quietIvory, shadowAlpha: 0.62
    )
    drawVertical(
        "飞越玉门关",
        x: 170, top: 168, step: 111,
        font: titleFont, color: titleIvory, shadowAlpha: 0.76
    )
    drawVertical(
        "栀夏与阿砚",
        x: 288, top: 182, step: 48,
        font: roleFont, color: quietIvory, shadowAlpha: 0.66
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
