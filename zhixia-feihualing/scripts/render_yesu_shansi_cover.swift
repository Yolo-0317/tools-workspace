#!/usr/bin/env swift

import AppKit
import CoreText
import Foundation

enum CoverError: Error {
    case usage
    case unreadableInput
    case bitmapCreation
    case unavailableFont
    case pngEncoding
}

let canvasWidth = 1080
let canvasHeight = 1920
let title = "手可摘星辰"
let credit = "李白《夜宿山寺》· 15秒诗境"

func textAttributes(font: NSFont, color: NSColor, shadowAlpha: CGFloat) -> [NSAttributedString.Key: Any] {
    let shadow = NSShadow()
    shadow.shadowColor = NSColor(calibratedWhite: 0.0, alpha: shadowAlpha)
    shadow.shadowBlurRadius = 7
    shadow.shadowOffset = NSSize(width: 2, height: -2)
    return [
        .font: font,
        .foregroundColor: color,
        .shadow: shadow
    ]
}

func drawVerticalTitle(_ text: String, x: CGFloat, screenTop: CGFloat, font: NSFont) {
    let attributes = textAttributes(
        font: font,
        color: NSColor(calibratedRed: 236.0 / 255.0, green: 222.0 / 255.0, blue: 195.0 / 255.0, alpha: 1),
        shadowAlpha: 0.68
    )
    for (index, character) in text.enumerated() {
        let value = NSAttributedString(string: String(character), attributes: attributes)
        let size = value.size()
        let screenY = screenTop + CGFloat(index) * 118
        value.draw(in: NSRect(
            x: x - size.width / 2,
            y: CGFloat(canvasHeight) - screenY - size.height,
            width: size.width + 8,
            height: size.height + 8
        ))
    }
}

func drawCredit(_ text: String, screenY: CGFloat, font: NSFont) {
    let value = NSAttributedString(
        string: text,
        attributes: textAttributes(
            font: font,
            color: NSColor(calibratedRed: 218.0 / 255.0, green: 211.0 / 255.0, blue: 193.0 / 255.0, alpha: 0.96),
            shadowAlpha: 0.72
        )
    )
    let size = value.size()
    value.draw(in: NSRect(
        x: (CGFloat(canvasWidth) - size.width) / 2,
        y: CGFloat(canvasHeight) - screenY - size.height,
        width: size.width + 8,
        height: size.height + 8
    ))
}

do {
    guard CommandLine.arguments.count == 3 else { throw CoverError.usage }
    let inputURL = URL(fileURLWithPath: CommandLine.arguments[1])
    let outputURL = URL(fileURLWithPath: CommandLine.arguments[2])
    guard let inputImage = NSImage(contentsOf: inputURL) else { throw CoverError.unreadableInput }

    let titleFontPath = "/System/Library/AssetsV2/com_apple_MobileAsset_Font7/aa99d0b2bad7f797f38b49d46cde28fd4b58876e.asset/AssetData/Xingkai.ttc"
    let creditFontPath = "/System/Library/AssetsV2/com_apple_MobileAsset_Font7/54a2ad3dac6cac875ad675d7d273dc425010a877.asset/AssetData/Kaiti.ttc"
    CTFontManagerRegisterFontsForURL(URL(fileURLWithPath: titleFontPath) as CFURL, .process, nil)
    CTFontManagerRegisterFontsForURL(URL(fileURLWithPath: creditFontPath) as CFURL, .process, nil)
    guard let titleFont = NSFont(name: "STXingkaiSC-Bold", size: 96),
          let creditFont = NSFont(name: "STKaitiSC-Regular", size: 38) else {
        throw CoverError.unavailableFont
    }

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
        throw CoverError.bitmapCreation
    }

    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.current = context
    inputImage.draw(
        in: NSRect(x: 0, y: 0, width: canvasWidth, height: canvasHeight),
        from: NSRect(origin: .zero, size: inputImage.size),
        operation: .copy,
        fraction: 1
    )
    drawVerticalTitle(title, x: 145, screenTop: 250, font: titleFont)
    drawCredit(credit, screenY: 1810, font: creditFont)
    NSGraphicsContext.restoreGraphicsState()

    try FileManager.default.createDirectory(at: outputURL.deletingLastPathComponent(), withIntermediateDirectories: true)
    guard let png = bitmap.representation(using: .png, properties: [:]) else { throw CoverError.pngEncoding }
    try png.write(to: outputURL, options: .atomic)
} catch {
    FileHandle.standardError.write(Data("error: \(error)\n".utf8))
    exit(1)
}
