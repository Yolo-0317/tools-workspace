#!/usr/bin/env swift

import AppKit
import CoreText
import Foundation

enum CoverError: Error, CustomStringConvertible {
    case usage
    case invalidImage
    case invalidDimensions
    case unavailableFont
    case bitmapCreation
    case pngEncoding

    var description: String {
        switch self {
        case .usage:
            return "usage: render_tiangong_hot_dance_jiuyue_haoyun_cover.swift <base.png> <output.png>"
        case .invalidImage:
            return "unable to load 九月好运 cover base image"
        case .invalidDimensions:
            return "cover base image must be 1080x1920"
        case .unavailableFont:
            return "required Chinese fonts are unavailable"
        case .bitmapCreation:
            return "unable to create cover bitmap"
        case .pngEncoding:
            return "unable to encode cover PNG"
        }
    }
}

let width: CGFloat = 1080
let height: CGFloat = 1920
let warmIvory = NSColor(
    calibratedRed: 246.0 / 255.0,
    green: 235.0 / 255.0,
    blue: 211.0 / 255.0,
    alpha: 1
)
let blessingGold = NSColor(
    calibratedRed: 247.0 / 255.0,
    green: 214.0 / 255.0,
    blue: 145.0 / 255.0,
    alpha: 1
)
let seriesGold = NSColor(
    calibratedRed: 236.0 / 255.0,
    green: 208.0 / 255.0,
    blue: 155.0 / 255.0,
    alpha: 0.98
)

func attributes(
    font: NSFont,
    color: NSColor,
    tracking: CGFloat,
    shadowBlur: CGFloat
) -> [NSAttributedString.Key: Any] {
    let shadow = NSShadow()
    shadow.shadowColor = NSColor(
        calibratedRed: 0.15,
        green: 0.10,
        blue: 0.04,
        alpha: 0.82
    )
    shadow.shadowBlurRadius = shadowBlur
    shadow.shadowOffset = NSSize(width: 1.5, height: -2.5)

    let paragraph = NSMutableParagraphStyle()
    paragraph.alignment = .center

    return [
        .font: font,
        .foregroundColor: color,
        .kern: tracking,
        .shadow: shadow,
        .paragraphStyle: paragraph,
    ]
}

func drawCentered(
    _ text: String,
    top: CGFloat,
    horizontalInset: CGFloat,
    font: NSFont,
    color: NSColor,
    tracking: CGFloat,
    shadowBlur: CGFloat
) {
    let attributed = NSAttributedString(
        string: text,
        attributes: attributes(
            font: font,
            color: color,
            tracking: tracking,
            shadowBlur: shadowBlur
        )
    )
    let measuredHeight = attributed.size().height + 24
    attributed.draw(in: NSRect(
        x: horizontalInset,
        y: height - top - measuredHeight,
        width: width - horizontalInset * 2,
        height: measuredHeight
    ))
}

func drawSeries(
    _ text: String,
    left: CGFloat,
    top: CGFloat,
    font: NSFont
) {
    let attributed = NSAttributedString(
        string: text,
        attributes: attributes(
            font: font,
            color: seriesGold,
            tracking: 8,
            shadowBlur: 7
        )
    )
    let size = attributed.size()
    attributed.draw(in: NSRect(
        x: left,
        y: height - top - size.height - 12,
        width: size.width + 20,
        height: size.height + 16
    ))
}

do {
    guard CommandLine.arguments.count == 3 else {
        throw CoverError.usage
    }
    let baseURL = URL(fileURLWithPath: CommandLine.arguments[1])
    let outputURL = URL(fileURLWithPath: CommandLine.arguments[2])
    guard let base = NSImage(contentsOf: baseURL) else {
        throw CoverError.invalidImage
    }
    guard Int(base.size.width) == Int(width),
          Int(base.size.height) == Int(height) else {
        throw CoverError.invalidDimensions
    }

    let xingkaiURL = URL(
        fileURLWithPath: "/System/Library/AssetsV2/com_apple_MobileAsset_Font7/aa99d0b2bad7f797f38b49d46cde28fd4b58876e.asset/AssetData/Xingkai.ttc"
    )
    let kaitiURL = URL(
        fileURLWithPath: "/System/Library/AssetsV2/com_apple_MobileAsset_Font7/54a2ad3dac6cac875ad675d7d273dc425010a877.asset/AssetData/Kaiti.ttc"
    )
    CTFontManagerRegisterFontsForURL(xingkaiURL as CFURL, .process, nil)
    CTFontManagerRegisterFontsForURL(kaitiURL as CFURL, .process, nil)

    guard let titleFont = NSFont(name: "STXingkaiSC-Bold", size: 134),
          let blessingFont = NSFont(name: "STXingkaiSC-Bold", size: 68),
          let seriesFont = NSFont(name: "STKaitiSC-Regular", size: 38) else {
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
    base.draw(
        in: NSRect(x: 0, y: 0, width: width, height: height),
        from: .zero,
        operation: .copy,
        fraction: 1
    )

    drawCentered(
        "天宫双姝",
        top: 112,
        horizontalInset: 90,
        font: titleFont,
        color: warmIvory,
        tracking: 18,
        shadowBlur: 14
    )
    drawCentered(
        "九月好运",
        top: 292,
        horizontalInset: 220,
        font: blessingFont,
        color: blessingGold,
        tracking: 12,
        shadowBlur: 10
    )
    drawSeries(
        "一舞一愿",
        left: 42,
        top: 1734,
        font: seriesFont
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
