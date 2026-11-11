#!/usr/bin/env swift

import AppKit
import CoreText
import Foundation

enum CoverError: Error {
    case usage, sourceImage, bitmapCreation, pngEncoding, unavailableFont
}

let width = 720
let height = 1280

func screenRect(x: CGFloat, y: CGFloat, width: CGFloat, height: CGFloat) -> NSRect {
    NSRect(x: x, y: CGFloat(1280) - y - height, width: width, height: height)
}

func textAttributes(font: NSFont, color: NSColor) -> [NSAttributedString.Key: Any] {
    let shadow = NSShadow()
    shadow.shadowColor = NSColor(calibratedWhite: 0.0, alpha: 0.72)
    shadow.shadowBlurRadius = 6
    shadow.shadowOffset = NSSize(width: 1, height: -2)
    return [.font: font, .foregroundColor: color, .shadow: shadow]
}

func drawText(_ text: String, x: CGFloat, y: CGFloat, font: NSFont, color: NSColor) {
    let value = NSAttributedString(string: text, attributes: textAttributes(font: font, color: color))
    let size = value.size()
    value.draw(in: screenRect(x: x, y: y, width: size.width + 12, height: size.height + 10))
}

func drawPill(x: CGFloat, y: CGFloat, width: CGFloat, height: CGFloat) {
    let path = NSBezierPath(roundedRect: screenRect(x: x, y: y, width: width, height: height), xRadius: height / 2, yRadius: height / 2)
    NSColor(calibratedRed: 18 / 255, green: 35 / 255, blue: 38 / 255, alpha: 0.76).setFill()
    path.fill()
    NSColor(calibratedRed: 199 / 255, green: 225 / 255, blue: 214 / 255, alpha: 0.76).setStroke()
    path.lineWidth = 1.5
    path.stroke()
}

do {
    guard CommandLine.arguments.count == 3 else { throw CoverError.usage }
    let sourceURL = URL(fileURLWithPath: CommandLine.arguments[1])
    let outputURL = URL(fileURLWithPath: CommandLine.arguments[2])
    guard let source = NSImage(contentsOf: sourceURL) else { throw CoverError.sourceImage }

    let fontPath = "/System/Library/AssetsV2/com_apple_MobileAsset_Font7/aa99d0b2bad7f797f38b49d46cde28fd4b58876e.asset/AssetData/Xingkai.ttc"
    let smallFontPath = "/System/Library/AssetsV2/com_apple_MobileAsset_Font7/54a2ad3dac6cac875ad675d7d273dc425010a877.asset/AssetData/Kaiti.ttc"
    CTFontManagerRegisterFontsForURL(URL(fileURLWithPath: fontPath) as CFURL, .process, nil)
    CTFontManagerRegisterFontsForURL(URL(fileURLWithPath: smallFontPath) as CFURL, .process, nil)
    guard let mainFont = NSFont(name: "STXingkaiSC-Bold", size: 72),
          let tagFont = NSFont(name: "STKaitiSC-Regular", size: 27),
          let infoFont = NSFont(name: "STKaitiSC-Regular", size: 27) else {
        throw CoverError.unavailableFont
    }

    guard let bitmap = NSBitmapImageRep(
        bitmapDataPlanes: nil,
        pixelsWide: width,
        pixelsHigh: height,
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
    source.draw(in: NSRect(x: 0, y: 0, width: width, height: height), from: .zero, operation: .copy, fraction: 1.0)

    let topShade = NSGradient(colors: [
        NSColor(calibratedWhite: 0.0, alpha: 0.42),
        NSColor(calibratedWhite: 0.0, alpha: 0.0)
    ])!
    topShade.draw(in: screenRect(x: 0, y: 0, width: 720, height: 430), angle: -90)

    drawPill(x: 42, y: 54, width: 286, height: 50)
    drawText("AI美女·周易起卦", x: 63, y: 64, font: tagFont, color: NSColor(calibratedWhite: 0.97, alpha: 1.0))

    let ivory = NSColor(calibratedRed: 246 / 255, green: 230 / 255, blue: 196 / 255, alpha: 1.0)
    drawText("最后一块", x: 42, y: 136, font: mainFont, color: ivory)
    drawText("能吃吗？", x: 42, y: 218, font: mainFont, color: ivory)

    drawPill(x: 370, y: 1171, width: 304, height: 54)
    drawText("第01卦｜山雷颐", x: 392, y: 1182, font: infoFont, color: ivory)

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
