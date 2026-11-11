#!/usr/bin/env swift

import AppKit
import CoreText
import Foundation

enum CoverError: Error, CustomStringConvertible {
    case usage, invalidImage, unavailableFont, pngEncoding

    var description: String {
        switch self {
        case .usage: return "usage: render_ep08_flute_cover.swift <base.png> <output.png>"
        case .invalidImage: return "unable to load cover base image"
        case .unavailableFont: return "Xingkai SC is unavailable"
        case .pngEncoding: return "unable to encode cover PNG"
        }
    }
}

let canvasWidth: CGFloat = 941
let canvasHeight: CGFloat = 1672
let vermilion = NSColor(calibratedRed: 0.96, green: 0.12, blue: 0.045, alpha: 1)
let warmWhite = NSColor(calibratedRed: 1.0, green: 0.965, blue: 0.88, alpha: 1)

func drawVerticalColumn(_ text: String, highlightedIndexes: Set<Int>, x: CGFloat, top: CGFloat, step: CGFloat, font: NSFont) {
    let shadow = NSShadow()
    shadow.shadowColor = NSColor(calibratedWhite: 0.02, alpha: 0.68)
    shadow.shadowBlurRadius = 5
    shadow.shadowOffset = NSSize(width: 1.5, height: -2)

    for (index, character) in text.enumerated() {
        let color = highlightedIndexes.contains(index) ? vermilion : warmWhite
        let attributed = NSAttributedString(string: String(character), attributes: [
            .font: font,
            .foregroundColor: color,
            .strokeColor: NSColor(calibratedWhite: 0.08, alpha: 0.48),
            .strokeWidth: -1.7,
            .shadow: shadow
        ])
        let size = attributed.size()
        let yFromTop = top + CGFloat(index) * step
        attributed.draw(in: NSRect(x: x - size.width / 2, y: canvasHeight - yFromTop - size.height, width: size.width + 12, height: size.height + 12))
    }
}

do {
    guard CommandLine.arguments.count == 3 else { throw CoverError.usage }
    let baseURL = URL(fileURLWithPath: CommandLine.arguments[1])
    let outputURL = URL(fileURLWithPath: CommandLine.arguments[2])
    guard let base = NSImage(contentsOf: baseURL) else { throw CoverError.invalidImage }

    let fontURL = URL(fileURLWithPath: "/System/Library/AssetsV2/com_apple_MobileAsset_Font7/aa99d0b2bad7f797f38b49d46cde28fd4b58876e.asset/AssetData/Xingkai.ttc")
    CTFontManagerRegisterFontsForURL(fontURL as CFURL, .process, nil)
    guard let font = NSFont(name: "STXingkaiSC-Light", size: 91) else { throw CoverError.unavailableFont }

    guard let bitmap = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: Int(canvasWidth), pixelsHigh: Int(canvasHeight), bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false, colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0), let context = NSGraphicsContext(bitmapImageRep: bitmap) else {
        throw CoverError.invalidImage
    }

    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.current = context
    base.draw(in: NSRect(x: 0, y: 0, width: canvasWidth, height: canvasHeight))
    drawVerticalColumn("笛字飞花令", highlightedIndexes: [0], x: 300, top: 390, step: 119, font: font)
    drawVerticalColumn("第四句等你", highlightedIndexes: [0, 1], x: 154, top: 510, step: 119, font: font)
    NSGraphicsContext.restoreGraphicsState()

    guard let png = bitmap.representation(using: .png, properties: [:]) else { throw CoverError.pngEncoding }
    try FileManager.default.createDirectory(at: outputURL.deletingLastPathComponent(), withIntermediateDirectories: true)
    try png.write(to: outputURL, options: .atomic)
} catch {
    FileHandle.standardError.write(Data("error: \(error)\n".utf8))
    exit(1)
}
