#!/usr/bin/env swift

import AppKit
import CoreText
import Foundation

enum CoverError: Error, CustomStringConvertible {
    case usage, invalidImage, unavailableFont, bitmapCreation, pngEncoding

    var description: String {
        switch self {
        case .usage: return "usage: render_denggao_10s_cover.swift <base.png> <output.png>"
        case .invalidImage: return "unable to load cover base image"
        case .unavailableFont: return "required Chinese fonts are unavailable"
        case .bitmapCreation: return "unable to create cover bitmap"
        case .pngEncoding: return "unable to encode cover PNG"
        }
    }
}

let width: CGFloat = 1080
let height: CGFloat = 1920
let ivory = NSColor(calibratedRed: 0.95, green: 0.89, blue: 0.77, alpha: 1)
let mutedIvory = NSColor(calibratedRed: 0.88, green: 0.82, blue: 0.70, alpha: 0.96)
let cinnabar = NSColor(calibratedRed: 0.78, green: 0.18, blue: 0.08, alpha: 1)

func textAttributes(font: NSFont, color: NSColor, shadowAlpha: CGFloat) -> [NSAttributedString.Key: Any] {
    let shadow = NSShadow()
    shadow.shadowColor = NSColor(calibratedWhite: 0.02, alpha: shadowAlpha)
    shadow.shadowBlurRadius = 5
    shadow.shadowOffset = NSSize(width: 2, height: -2)
    return [
        .font: font,
        .foregroundColor: color,
        .shadow: shadow
    ]
}

func drawVertical(
    _ text: String,
    x: CGFloat,
    top: CGFloat,
    step: CGFloat,
    font: NSFont,
    defaultColor: NSColor,
    highlightedCharacter: Character? = nil
) {
    for (index, character) in text.enumerated() {
        let color = character == highlightedCharacter ? cinnabar : defaultColor
        let value = NSAttributedString(
            string: String(character),
            attributes: textAttributes(font: font, color: color, shadowAlpha: 0.62)
        )
        let size = value.size()
        let yFromTop = top + CGFloat(index) * step
        value.draw(in: NSRect(
            x: x - size.width / 2,
            y: height - yFromTop - size.height,
            width: size.width + 10,
            height: size.height + 10
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
    guard let poemFont = NSFont(name: "STXingkaiSC-Bold", size: 78),
          let creditFont = NSFont(name: "STKaitiSC-Regular", size: 38) else {
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
        bitsPerPixel: 0
    ), let context = NSGraphicsContext(bitmapImageRep: bitmap) else {
        throw CoverError.bitmapCreation
    }

    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.current = context
    base.draw(in: NSRect(x: 0, y: 0, width: width, height: height))

    drawVertical(
        "无边落木萧萧下",
        x: 246,
        top: 176,
        step: 100,
        font: poemFont,
        defaultColor: ivory
    )
    drawVertical(
        "不尽长江滚滚来",
        x: 108,
        top: 260,
        step: 100,
        font: poemFont,
        defaultColor: ivory,
        highlightedCharacter: "江"
    )
    drawVertical(
        "杜甫《登高》",
        x: 334,
        top: 820,
        step: 52,
        font: creditFont,
        defaultColor: mutedIvory
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
