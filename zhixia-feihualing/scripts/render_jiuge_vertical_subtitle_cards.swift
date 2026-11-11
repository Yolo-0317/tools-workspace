#!/usr/bin/env swift

import AppKit
import CoreText
import Foundation

struct Subtitle: Decodable {
    let id: String
    let kind: String
    let text: String
    let attribution: String?
    let side: String
}

enum RenderError: Error {
    case usage, unavailableFont, invalidSide, bitmapCreation, pngEncoding
}

let width: CGFloat = 1080
let height: CGFloat = 1920
let poemIvory = NSColor(calibratedRed: 0.94, green: 0.89, blue: 0.79, alpha: 1)
let oldGold = NSColor(calibratedRed: 0.48, green: 0.37, blue: 0.22, alpha: 0.92)

func attributes(font: NSFont, color: NSColor) -> [NSAttributedString.Key: Any] {
    let shadow = NSShadow()
    shadow.shadowColor = NSColor(calibratedWhite: 0.01, alpha: 0.68)
    shadow.shadowBlurRadius = 7
    shadow.shadowOffset = NSSize(width: 2, height: -2)
    return [
        .font: font,
        .foregroundColor: color,
        .strokeColor: oldGold,
        .strokeWidth: -1.2,
        .shadow: shadow
    ]
}

func drawVertical(
    _ text: String,
    x: CGFloat,
    top: CGFloat,
    step: CGFloat,
    font: NSFont,
    color: NSColor
) {
    for (index, character) in text.enumerated() {
        let glyph = NSAttributedString(
            string: String(character),
            attributes: attributes(font: font, color: color)
        )
        let size = glyph.size()
        let screenY = top + CGFloat(index) * step
        glyph.draw(in: NSRect(
            x: x - size.width / 2,
            y: height - screenY - size.height,
            width: size.width + 12,
            height: size.height + 12
        ))
    }
}

func render(_ item: Subtitle, poemFont: NSFont, creditFont: NSFont, to url: URL) throws {
    let mainX: CGFloat
    let creditX: CGFloat
    switch item.side {
    case "right":
        mainX = 872
        creditX = 994
    case "left":
        mainX = 168
        creditX = 64
    default:
        throw RenderError.invalidSide
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
        throw RenderError.bitmapCreation
    }

    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.current = context
    NSColor.clear.setFill()
    NSRect(x: 0, y: 0, width: width, height: height).fill()
    drawVertical(item.text, x: mainX, top: 245, step: 94, font: poemFont, color: poemIvory)
    if let attribution = item.attribution {
        drawVertical(
            attribution,
            x: creditX,
            top: 250,
            step: 38,
            font: creditFont,
            color: poemIvory
        )
    }
    NSGraphicsContext.restoreGraphicsState()

    guard let png = bitmap.representation(using: .png, properties: [:]) else {
        throw RenderError.pngEncoding
    }
    try png.write(to: url, options: .atomic)
}

do {
    guard CommandLine.arguments.count == 3 else { throw RenderError.usage }
    let manifestURL = URL(fileURLWithPath: CommandLine.arguments[1])
    let outputURL = URL(fileURLWithPath: CommandLine.arguments[2], isDirectory: true)
    let fontURL = URL(fileURLWithPath: "/System/Library/AssetsV2/com_apple_MobileAsset_Font7/54a2ad3dac6cac875ad675d7d273dc425010a877.asset/AssetData/Kaiti.ttc")
    CTFontManagerRegisterFontsForURL(fontURL as CFURL, .process, nil)
    guard let poemFont = NSFont(name: "STKaitiSC-Regular", size: 82),
          let creditFont = NSFont(name: "STKaitiSC-Regular", size: 30) else {
        throw RenderError.unavailableFont
    }

    let items = try JSONDecoder().decode(
        [Subtitle].self,
        from: Data(contentsOf: manifestURL)
    )
    try FileManager.default.createDirectory(at: outputURL, withIntermediateDirectories: true)
    for item in items {
        try render(
            item,
            poemFont: poemFont,
            creditFont: creditFont,
            to: outputURL.appendingPathComponent("\(item.id).png")
        )
    }
} catch {
    FileHandle.standardError.write(Data("error: \(error)\n".utf8))
    exit(1)
}
