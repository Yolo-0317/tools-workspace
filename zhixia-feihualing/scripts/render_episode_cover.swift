#!/usr/bin/env swift

import AppKit
import CoreText
import Foundation

enum CoverError: Error, CustomStringConvertible {
    case usage, invalidImage, unavailableFont, pngEncoding

    var description: String {
        switch self {
        case .usage: return "usage: render_episode_cover.swift <base.png> <output.png> <theme>"
        case .invalidImage: return "unable to load cover base image"
        case .unavailableFont: return "Xingkai SC is unavailable"
        case .pngEncoding: return "unable to encode cover PNG"
        }
    }
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
    let shadow = NSShadow()
    shadow.shadowColor = NSColor(calibratedWhite: 0.04, alpha: shadowAlpha)
    shadow.shadowBlurRadius = 2.2
    shadow.shadowOffset = NSSize(width: 1.4, height: -1.4)

    for (index, character) in text.enumerated() {
        let attributed = NSAttributedString(string: String(character), attributes: [
            .font: font,
            .foregroundColor: color,
            .shadow: shadow
        ])
        let size = attributed.size()
        let yFromTop = top + CGFloat(index) * step
        attributed.draw(in: NSRect(
            x: x - size.width / 2,
            y: 1672 - yFromTop - size.height,
            width: size.width + 6,
            height: size.height + 6
        ))
    }
}

do {
    guard CommandLine.arguments.count == 4 else { throw CoverError.usage }
    let baseURL = URL(fileURLWithPath: CommandLine.arguments[1])
    let outputURL = URL(fileURLWithPath: CommandLine.arguments[2])
    let theme = CommandLine.arguments[3]
    guard let base = NSImage(contentsOf: baseURL) else { throw CoverError.invalidImage }

    let fontURL = URL(fileURLWithPath: "/System/Library/AssetsV2/com_apple_MobileAsset_Font7/aa99d0b2bad7f797f38b49d46cde28fd4b58876e.asset/AssetData/Xingkai.ttc")
    CTFontManagerRegisterFontsForURL(fontURL as CFURL, .process, nil)
    guard let seriesFont = NSFont(name: "STXingkaiSC-Light", size: 50),
          let themeFont = NSFont(name: "STXingkaiSC-Light", size: 104) else {
        throw CoverError.unavailableFont
    }

    guard let bitmap = NSBitmapImageRep(
        bitmapDataPlanes: nil,
        pixelsWide: 941,
        pixelsHigh: 1672,
        bitsPerSample: 8,
        samplesPerPixel: 4,
        hasAlpha: true,
        isPlanar: false,
        colorSpaceName: .deviceRGB,
        bytesPerRow: 0,
        bitsPerPixel: 0
    ), let context = NSGraphicsContext(bitmapImageRep: bitmap) else {
        throw CoverError.invalidImage
    }

    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.current = context
    base.draw(in: NSRect(x: 0, y: 0, width: 941, height: 1672))

    drawVertical(
        "栀夏飞花令",
        x: 146,
        top: 330,
        step: 64,
        font: seriesFont,
        color: NSColor(calibratedWhite: 0.30, alpha: 0.82),
        shadowAlpha: 0.20
    )
    drawVertical(
        theme,
        x: 78,
        top: 690,
        step: 110,
        font: themeFont,
        color: NSColor(calibratedRed: 0.96, green: 0.13, blue: 0.05, alpha: 1.0),
        shadowAlpha: 0.34
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
