#!/usr/bin/env swift

import AppKit
import CoreText
import Foundation

enum CoverError: Error, CustomStringConvertible {
    case usage, invalidImage, unavailableFont, bitmapCreation, pngEncoding

    var description: String {
        switch self {
        case .usage: return "usage: render_quzhong_huteng_dance_cover.swift <base.png> <output.png>"
        case .invalidImage: return "unable to load 曲终胡腾 cover base image"
        case .unavailableFont: return "required Chinese fonts are unavailable"
        case .bitmapCreation: return "unable to create cover bitmap"
        case .pngEncoding: return "unable to encode cover PNG"
        }
    }
}

let width: CGFloat = 1080
let height: CGFloat = 1920
let titleIvory = NSColor(calibratedRed: 0.97, green: 0.91, blue: 0.78, alpha: 1)
let quietIvory = NSColor(calibratedRed: 0.92, green: 0.85, blue: 0.72, alpha: 0.98)

func textAttributes(font: NSFont, color: NSColor, blur: CGFloat) -> [NSAttributedString.Key: Any] {
    let shadow = NSShadow()
    shadow.shadowColor = NSColor(calibratedWhite: 0.01, alpha: 0.82)
    shadow.shadowBlurRadius = blur
    shadow.shadowOffset = NSSize(width: 2, height: -2)
    return [.font: font, .foregroundColor: color, .shadow: shadow]
}

func drawVertical(_ text: String, x: CGFloat, top: CGFloat, step: CGFloat, font: NSFont, color: NSColor) {
    for (index, character) in text.enumerated() {
        let glyph = NSAttributedString(
            string: String(character),
            attributes: textAttributes(font: font, color: color, blur: 7)
        )
        let size = glyph.size()
        let yFromTop = top + CGFloat(index) * step
        glyph.draw(in: NSRect(
            x: x - size.width / 2,
            y: height - yFromTop - size.height,
            width: size.width + 14,
            height: size.height + 14
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

    guard let titleFont = NSFont(name: "STXingkaiSC-Bold", size: 88),
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
        bitsPerPixel: 0
    ), let context = NSGraphicsContext(bitmapImageRep: bitmap) else {
        throw CoverError.bitmapCreation
    }

    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.current = context
    base.draw(in: NSRect(x: 0, y: 0, width: width, height: height))

    drawVertical("栀夏", x: 88, top: 186, step: 62, font: nameFont, color: quietIvory)
    drawVertical("曲终胡腾", x: 210, top: 178, step: 112, font: titleFont, color: titleIvory)
    drawVertical("唐·李端《胡腾儿》", x: 326, top: 630, step: 39, font: creditFont, color: quietIvory)

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
