#!/usr/bin/env swift

import AppKit
import CoreText
import Foundation

struct StorySubtitle: Decodable {
    let id: String
    let kind: String
    let text: String
    let attribution: String?
}

enum RenderError: Error {
    case usage, bitmapCreation, pngEncoding, unavailableFont
}

let width = 720
let height = 1280

let poemIvory = NSColor(
    calibratedRed: 228.0 / 255.0,
    green: 215.0 / 255.0,
    blue: 192.0 / 255.0,
    alpha: 1
)
let attributionIvory = NSColor(
    calibratedRed: 210.0 / 255.0,
    green: 203.0 / 255.0,
    blue: 180.0 / 255.0,
    alpha: 1
)

func attributes(font: NSFont, color: NSColor) -> [NSAttributedString.Key: Any] {
    let shadow = NSShadow()
    shadow.shadowColor = NSColor(calibratedWhite: 0.0, alpha: 0.52)
    shadow.shadowBlurRadius = 4
    shadow.shadowOffset = NSSize(width: 1, height: -1)
    return [
        .font: font,
        .foregroundColor: color,
        .shadow: shadow
    ]
}

func drawHorizontal(_ text: String, font: NSFont) {
    let value = NSAttributedString(string: text, attributes: attributes(font: font, color: poemIvory))
    let size = value.size()
    value.draw(in: NSRect(
        x: (CGFloat(width) - size.width) / 2,
        y: CGFloat(height) - 940 - size.height,
        width: size.width + 6,
        height: size.height + 6
    ))
}

func columns(_ text: String) -> [String] {
    text.components(separatedBy: CharacterSet(charactersIn: "，。！？、|｜\n")).filter { !$0.isEmpty }
}

func drawVertical(_ text: String, x: CGFloat, top: CGFloat, font: NSFont, color: NSColor, step: CGFloat) {
    for (index, character) in text.enumerated() {
        let value = NSAttributedString(string: String(character), attributes: attributes(font: font, color: color))
        let size = value.size()
        let screenY = top + CGFloat(index) * step
        value.draw(in: NSRect(
            x: x - size.width / 2,
            y: CGFloat(height) - screenY - size.height,
            width: size.width + 5,
            height: size.height + 5
        ))
    }
}

func render(_ subtitle: StorySubtitle, dialogueFont: NSFont, poemFont: NSFont, creditFont: NSFont, to url: URL) throws {
    guard let bitmap = NSBitmapImageRep(
        bitmapDataPlanes: nil, pixelsWide: width, pixelsHigh: height,
        bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false,
        colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0
    ), let context = NSGraphicsContext(bitmapImageRep: bitmap) else { throw RenderError.bitmapCreation }

    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.current = context
    NSColor.clear.setFill()
    NSRect(x: 0, y: 0, width: width, height: height).fill()
    if subtitle.kind == "poem" {
        let lines = columns(subtitle.text)
        for (index, line) in lines.enumerated() {
            drawVertical(line, x: 184 - CGFloat(index) * 84, top: 126, font: poemFont, color: poemIvory, step: 70)
        }
        if let attribution = subtitle.attribution {
            drawVertical(attribution, x: 48, top: 128, font: creditFont, color: attributionIvory, step: 35)
        }
    } else {
        drawHorizontal(subtitle.text, font: dialogueFont)
    }
    NSGraphicsContext.restoreGraphicsState()

    guard let png = bitmap.representation(using: .png, properties: [:]) else { throw RenderError.pngEncoding }
    try png.write(to: url, options: .atomic)
}

do {
    guard CommandLine.arguments.count == 3 else { throw RenderError.usage }
    let manifest = URL(fileURLWithPath: CommandLine.arguments[1])
    let output = URL(fileURLWithPath: CommandLine.arguments[2], isDirectory: true)
    let fontPath = ProcessInfo.processInfo.environment["SUBTITLE_FONT"]
        ?? "/System/Library/AssetsV2/com_apple_MobileAsset_Font7/aa99d0b2bad7f797f38b49d46cde28fd4b58876e.asset/AssetData/Xingkai.ttc"
    CTFontManagerRegisterFontsForURL(URL(fileURLWithPath: fontPath) as CFURL, .process, nil)
    let creditFontPath = ProcessInfo.processInfo.environment["SUBTITLE_CREDIT_FONT"]
        ?? "/System/Library/AssetsV2/com_apple_MobileAsset_Font7/54a2ad3dac6cac875ad675d7d273dc425010a877.asset/AssetData/Kaiti.ttc"
    CTFontManagerRegisterFontsForURL(URL(fileURLWithPath: creditFontPath) as CFURL, .process, nil)
    guard let dialogueFont = NSFont(name: "STXingkaiSC-Bold", size: 48),
          let poemFont = NSFont(name: "STXingkaiSC-Bold", size: 66),
          let creditFont = NSFont(name: "STKaitiSC-Regular", size: 28) else { throw RenderError.unavailableFont }
    let items = try JSONDecoder().decode([StorySubtitle].self, from: Data(contentsOf: manifest))
    try FileManager.default.createDirectory(at: output, withIntermediateDirectories: true)
    for item in items {
        try render(item, dialogueFont: dialogueFont, poemFont: poemFont, creditFont: creditFont,
                   to: output.appendingPathComponent("\(item.id).png"))
    }
} catch {
    FileHandle.standardError.write(Data("error: \(error)\n".utf8))
    exit(1)
}
