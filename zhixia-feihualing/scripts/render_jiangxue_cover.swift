#!/usr/bin/env swift

import AppKit
import CoreText
import Foundation

enum CoverError: Error, CustomStringConvertible {
    case usage
    case invalidImage
    case unavailableFont
    case pngEncoding

    var description: String {
        switch self {
        case .usage:
            return "usage: render_jiangxue_cover.swift <base.png> <output.png>"
        case .invalidImage:
            return "unable to load Jiangxue cover base image"
        case .unavailableFont:
            return "Xingkai SC is unavailable"
        case .pngEncoding:
            return "unable to encode Jiangxue cover PNG"
        }
    }
}

let canvasWidth: CGFloat = 720
let canvasHeight: CGFloat = 1280
let poemIvory = NSColor(
    calibratedRed: 228.0 / 255.0,
    green: 215.0 / 255.0,
    blue: 192.0 / 255.0,
    alpha: 1
)
let labelIvory = NSColor(
    calibratedRed: 209.0 / 255.0,
    green: 200.0 / 255.0,
    blue: 182.0 / 255.0,
    alpha: 1
)
let attributionIvory = NSColor(
    calibratedRed: 210.0 / 255.0,
    green: 203.0 / 255.0,
    blue: 180.0 / 255.0,
    alpha: 1
)

func drawVerticalColumn(
    _ text: String,
    x: CGFloat,
    top: CGFloat,
    step: CGFloat,
    font: NSFont,
    color: NSColor,
    shadowBlur: CGFloat
) {
    let shadow = NSShadow()
    shadow.shadowColor = NSColor(calibratedWhite: 0.02, alpha: 0.72)
    shadow.shadowBlurRadius = shadowBlur
    shadow.shadowOffset = NSSize(width: 1.5, height: -2)

    for (index, character) in text.enumerated() {
        let attributed = NSAttributedString(
            string: String(character),
            attributes: [
                .font: font,
                .foregroundColor: color,
                .shadow: shadow,
            ]
        )
        let size = attributed.size()
        let yFromTop = top + CGFloat(index) * step
        attributed.draw(
            in: NSRect(
                x: x - size.width / 2,
                y: canvasHeight - yFromTop - size.height,
                width: size.width + 12,
                height: size.height + 12
            )
        )
    }
}

do {
    guard CommandLine.arguments.count == 3 else { throw CoverError.usage }
    let baseURL = URL(fileURLWithPath: CommandLine.arguments[1])
    let outputURL = URL(fileURLWithPath: CommandLine.arguments[2])
    guard let base = NSImage(contentsOf: baseURL) else { throw CoverError.invalidImage }

    let fontURL = URL(
        fileURLWithPath: "/System/Library/AssetsV2/com_apple_MobileAsset_Font7/aa99d0b2bad7f797f38b49d46cde28fd4b58876e.asset/AssetData/Xingkai.ttc"
    )
    CTFontManagerRegisterFontsForURL(fontURL as CFURL, .process, nil)
    guard let labelFont = NSFont(name: "STKaitiSC-Regular", size: 28),
          let poemFont = NSFont(name: "STXingkaiSC-Bold", size: 68),
          let attributionFont = NSFont(name: "STKaitiSC-Regular", size: 26)
    else {
        throw CoverError.unavailableFont
    }

    guard let bitmap = NSBitmapImageRep(
        bitmapDataPlanes: nil,
        pixelsWide: Int(canvasWidth),
        pixelsHigh: Int(canvasHeight),
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
    base.draw(in: NSRect(x: 0, y: 0, width: canvasWidth, height: canvasHeight))

    drawVerticalColumn("诗词小故事", x: 50, top: 54, step: 34, font: labelFont, color: labelIvory, shadowBlur: 3)
    drawVerticalColumn("孤舟蓑笠翁", x: 100, top: 218, step: 76, font: poemFont, color: poemIvory, shadowBlur: 4)
    drawVerticalColumn("独钓寒江雪", x: 208, top: 292, step: 76, font: poemFont, color: poemIvory, shadowBlur: 4)
    drawVerticalColumn("唐·柳宗元《江雪》", x: 52, top: 680, step: 35, font: attributionFont, color: attributionIvory, shadowBlur: 3)

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
