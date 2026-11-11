#!/usr/bin/env swift

import AppKit
import CoreText
import Foundation

enum CoverError: Error, CustomStringConvertible {
    case usage, invalidZoom, invalidImage, unavailableFont, bitmapCreation, pngEncoding

    var description: String {
        switch self {
        case .usage: return "usage: render_yiwu_yiyuan_restart_12s_cover.swift <base.png> <output.png> [zoom]"
        case .invalidZoom: return "zoom must be greater than 1"
        case .invalidImage: return "unable to load 一舞一愿 restart cover base image"
        case .unavailableFont: return "required Chinese fonts are unavailable"
        case .bitmapCreation: return "unable to create cover bitmap"
        case .pngEncoding: return "unable to encode cover PNG"
        }
    }
}

let width: CGFloat = 1080
let height: CGFloat = 1920
let defaultSubjectZoom: CGFloat = 1.15
let warmGold = NSColor(calibratedRed: 0.98, green: 0.91, blue: 0.70, alpha: 1)
let quietGold = NSColor(calibratedRed: 0.94, green: 0.87, blue: 0.70, alpha: 0.98)

func attributes(font: NSFont, color: NSColor, tracking: CGFloat, blur: CGFloat) -> [NSAttributedString.Key: Any] {
    let shadow = NSShadow()
    shadow.shadowColor = NSColor(calibratedRed: 0.20, green: 0.12, blue: 0.03, alpha: 0.78)
    shadow.shadowBlurRadius = blur
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

func drawCentered(_ text: String, top: CGFloat, font: NSFont, color: NSColor, tracking: CGFloat, blur: CGFloat) {
    let attributed = NSAttributedString(
        string: text,
        attributes: attributes(font: font, color: color, tracking: tracking, blur: blur)
    )
    let textHeight = attributed.size().height + 20
    attributed.draw(in: NSRect(x: 70, y: height - top - textHeight, width: width - 140, height: textHeight))
}

do {
    guard CommandLine.arguments.count == 3 || CommandLine.arguments.count == 4 else { throw CoverError.usage }
    let baseURL = URL(fileURLWithPath: CommandLine.arguments[1])
    let outputURL = URL(fileURLWithPath: CommandLine.arguments[2])
    let subjectZoom: CGFloat
    if CommandLine.arguments.count == 4 {
        guard let parsedZoom = Double(CommandLine.arguments[3]), parsedZoom > 1 else {
            throw CoverError.invalidZoom
        }
        subjectZoom = CGFloat(parsedZoom)
    } else {
        subjectZoom = defaultSubjectZoom
    }
    guard let base = NSImage(contentsOf: baseURL) else { throw CoverError.invalidImage }

    let xingkaiURL = URL(fileURLWithPath: "/System/Library/AssetsV2/com_apple_MobileAsset_Font7/aa99d0b2bad7f797f38b49d46cde28fd4b58876e.asset/AssetData/Xingkai.ttc")
    let kaitiURL = URL(fileURLWithPath: "/System/Library/AssetsV2/com_apple_MobileAsset_Font7/54a2ad3dac6cac875ad675d7d273dc425010a877.asset/AssetData/Kaiti.ttc")
    CTFontManagerRegisterFontsForURL(xingkaiURL as CFURL, .process, nil)
    CTFontManagerRegisterFontsForURL(kaitiURL as CFURL, .process, nil)

    guard let titleFont = NSFont(name: "STXingkaiSC-Bold", size: 142),
          let seriesFont = NSFont(name: "STKaitiSC-Regular", size: 42),
          let blessingFont = NSFont(name: "STKaitiSC-Regular", size: 48) else {
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

    let baseSize = base.size
    let aspectFillScale = max(width / baseSize.width, height / baseSize.height)
    let scale = aspectFillScale * subjectZoom
    let drawSize = NSSize(width: baseSize.width * scale, height: baseSize.height * scale)
    let drawRect = NSRect(
        x: (width - drawSize.width) / 2,
        y: (height - drawSize.height) / 2,
        width: drawSize.width,
        height: drawSize.height
    )
    base.draw(in: drawRect, from: .zero, operation: .copy, fraction: 1)

    drawCentered("一舞一愿", top: 112, font: seriesFont, color: quietGold, tracking: 12, blur: 7)
    drawCentered("重新出发", top: 190, font: titleFont, color: warmGold, tracking: 14, blur: 12)
    drawCentered("愿你每一步，都算数", top: 382, font: blessingFont, color: quietGold, tracking: 5, blur: 8)

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
