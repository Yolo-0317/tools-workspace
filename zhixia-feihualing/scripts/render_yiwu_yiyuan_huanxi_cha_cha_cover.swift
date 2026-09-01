#!/usr/bin/env swift

import AppKit
import CoreText
import Foundation

enum CoverError: Error, CustomStringConvertible {
    case usage, invalidImage, unavailableFont, bitmapCreation, pngEncoding

    var description: String {
        switch self {
        case .usage: return "usage: render_yiwu_yiyuan_huanxi_cha_cha_cover.swift <reference.png> <output.png>"
        case .invalidImage: return "unable to load heavenly cha-cha cover reference"
        case .unavailableFont: return "required Chinese fonts are unavailable"
        case .bitmapCreation: return "unable to create cover bitmap"
        case .pngEncoding: return "unable to encode cover PNG"
        }
    }
}

let canvasWidth: CGFloat = 1080
let canvasHeight: CGFloat = 1920
let warmGold = NSColor(calibratedRed: 0.99, green: 0.90, blue: 0.65, alpha: 1)
let quietGold = NSColor(calibratedRed: 0.95, green: 0.88, blue: 0.71, alpha: 0.98)

func textAttributes(font: NSFont, color: NSColor, tracking: CGFloat, blur: CGFloat) -> [NSAttributedString.Key: Any] {
    let shadow = NSShadow()
    shadow.shadowColor = NSColor(calibratedRed: 0.16, green: 0.10, blue: 0.04, alpha: 0.90)
    shadow.shadowBlurRadius = blur
    shadow.shadowOffset = NSSize(width: 2, height: -3)

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

func drawCentered(_ text: String, top: CGFloat, font: NSFont, color: NSColor, tracking: CGFloat, blur: CGFloat) {
    let attributed = NSAttributedString(
        string: text,
        attributes: textAttributes(font: font, color: color, tracking: tracking, blur: blur)
    )
    let measuredHeight = attributed.size().height + 18
    attributed.draw(in: NSRect(x: 70, y: canvasHeight - top - measuredHeight, width: canvasWidth - 140, height: measuredHeight))
}

func drawVerticalTitle(_ text: String, left: CGFloat, top: CGFloat, font: NSFont) {
    var currentTop = top
    for character in text {
        let glyph = NSAttributedString(
            string: String(character),
            attributes: textAttributes(font: font, color: warmGold, tracking: 0, blur: 15)
        )
        let size = glyph.size()
        glyph.draw(in: NSRect(
            x: left,
            y: canvasHeight - currentTop - size.height,
            width: 220,
            height: size.height + 10
        ))
        currentTop += 174
    }
}

do {
    guard CommandLine.arguments.count == 3 else { throw CoverError.usage }
    let referenceURL = URL(fileURLWithPath: CommandLine.arguments[1])
    let outputURL = URL(fileURLWithPath: CommandLine.arguments[2])
    guard let reference = NSImage(contentsOf: referenceURL) else { throw CoverError.invalidImage }

    let xingkaiURL = URL(fileURLWithPath: "/System/Library/AssetsV2/com_apple_MobileAsset_Font7/aa99d0b2bad7f797f38b49d46cde28fd4b58876e.asset/AssetData/Xingkai.ttc")
    let kaitiURL = URL(fileURLWithPath: "/System/Library/AssetsV2/com_apple_MobileAsset_Font7/54a2ad3dac6cac875ad675d7d273dc425010a877.asset/AssetData/Kaiti.ttc")
    CTFontManagerRegisterFontsForURL(xingkaiURL as CFURL, .process, nil)
    CTFontManagerRegisterFontsForURL(kaitiURL as CFURL, .process, nil)

    guard let titleFont = NSFont(name: "STXingkaiSC-Bold", size: 176),
          let seriesFont = NSFont(name: "STKaitiSC-Regular", size: 42) else {
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
        throw CoverError.bitmapCreation
    }

    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.current = context

    let sourceSize = reference.size
    let scale = max(canvasWidth / sourceSize.width, canvasHeight / sourceSize.height)
    let drawSize = NSSize(width: sourceSize.width * scale, height: sourceSize.height * scale)
    let drawRect = NSRect(
        x: (canvasWidth - drawSize.width) / 2,
        y: (canvasHeight - drawSize.height) / 2,
        width: drawSize.width,
        height: drawSize.height
    )
    reference.draw(in: drawRect, from: .zero, operation: .copy, fraction: 1)

    drawCentered("栀夏｜一舞一愿", top: 82, font: seriesFont, color: quietGold, tracking: 9, blur: 9)
    drawVerticalTitle("欢喜", left: 54, top: 252, font: titleFont)

    NSGraphicsContext.restoreGraphicsState()

    guard let png = bitmap.representation(using: .png, properties: [:]) else {
        throw CoverError.pngEncoding
    }
    try FileManager.default.createDirectory(at: outputURL.deletingLastPathComponent(), withIntermediateDirectories: true)
    try png.write(to: outputURL, options: .atomic)
} catch {
    FileHandle.standardError.write(Data("error: \(error)\n".utf8))
    exit(1)
}
