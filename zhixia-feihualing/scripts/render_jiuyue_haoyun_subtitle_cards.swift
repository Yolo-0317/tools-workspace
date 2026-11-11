#!/usr/bin/env swift

import AppKit
import CoreText
import Foundation

struct SubtitleItem: Decodable {
    let id: String
    let kind: String
    let text: String
    let attribution: String?
}

enum RenderError: Error {
    case usage
    case unavailableFont
    case bitmapCreation
    case pngEncoding
}

let width = 720
let height = 1280
let ivory = NSColor(
    calibratedRed: 238.0 / 255.0,
    green: 226.0 / 255.0,
    blue: 204.0 / 255.0,
    alpha: 1
)
let attributionIvory = NSColor(
    calibratedRed: 220.0 / 255.0,
    green: 211.0 / 255.0,
    blue: 190.0 / 255.0,
    alpha: 0.94
)

func textAttributes(font: NSFont, color: NSColor) -> [NSAttributedString.Key: Any] {
    let shadow = NSShadow()
    shadow.shadowColor = NSColor(calibratedWhite: 0.0, alpha: 0.52)
    shadow.shadowBlurRadius = 4
    shadow.shadowOffset = NSSize(width: 1, height: -1)
    return [
        .font: font,
        .foregroundColor: color,
        .shadow: shadow,
        .kern: 1.2
    ]
}

func drawHorizontal(
    _ text: String,
    top: CGFloat,
    font: NSFont,
    color: NSColor = ivory
) {
    let value = NSAttributedString(
        string: text,
        attributes: textAttributes(font: font, color: color)
    )
    let size = value.size()
    value.draw(in: NSRect(
        x: (CGFloat(width) - size.width) / 2,
        y: CGFloat(height) - top - size.height,
        width: size.width + 8,
        height: size.height + 8
    ))
}

func poemColumns(_ text: String) -> [String] {
    text.components(
        separatedBy: CharacterSet(charactersIn: "，。！？、|｜\n")
    ).filter { !$0.isEmpty }
}

func render(
    _ subtitle: SubtitleItem,
    modernFont: NSFont,
    poemFont: NSFont,
    creditFont: NSFont,
    to outputURL: URL
) throws {
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
        throw RenderError.bitmapCreation
    }

    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.current = context
    NSColor.clear.setFill()
    NSRect(x: 0, y: 0, width: width, height: height).fill()

    if subtitle.kind == "poem" {
        let lines = poemColumns(subtitle.text)
        for (index, line) in lines.enumerated() {
            drawHorizontal(
                line,
                top: 150 + CGFloat(index) * 65,
                font: poemFont
            )
        }
        if let attribution = subtitle.attribution {
            drawHorizontal(
                attribution,
                top: 285,
                font: creditFont,
                color: attributionIvory
            )
        }
    } else {
        drawHorizontal(subtitle.text, top: 180, font: modernFont)
    }

    NSGraphicsContext.restoreGraphicsState()
    guard let png = bitmap.representation(using: .png, properties: [:]) else {
        throw RenderError.pngEncoding
    }
    try png.write(to: outputURL, options: .atomic)
}

do {
    guard CommandLine.arguments.count == 3 else {
        throw RenderError.usage
    }
    let manifestURL = URL(fileURLWithPath: CommandLine.arguments[1])
    let outputURL = URL(
        fileURLWithPath: CommandLine.arguments[2],
        isDirectory: true
    )
    let xingkaiURL = URL(
        fileURLWithPath: "/System/Library/AssetsV2/com_apple_MobileAsset_Font7/aa99d0b2bad7f797f38b49d46cde28fd4b58876e.asset/AssetData/Xingkai.ttc"
    )
    let kaitiURL = URL(
        fileURLWithPath: "/System/Library/AssetsV2/com_apple_MobileAsset_Font7/54a2ad3dac6cac875ad675d7d273dc425010a877.asset/AssetData/Kaiti.ttc"
    )
    CTFontManagerRegisterFontsForURL(xingkaiURL as CFURL, .process, nil)
    CTFontManagerRegisterFontsForURL(kaitiURL as CFURL, .process, nil)

    guard let modernFont = NSFont(name: "STXingkaiSC-Bold", size: 42),
          let poemFont = NSFont(name: "STXingkaiSC-Bold", size: 56),
          let creditFont = NSFont(name: "STKaitiSC-Regular", size: 26) else {
        throw RenderError.unavailableFont
    }

    let subtitles = try JSONDecoder().decode(
        [SubtitleItem].self,
        from: Data(contentsOf: manifestURL)
    )
    try FileManager.default.createDirectory(
        at: outputURL,
        withIntermediateDirectories: true
    )
    for subtitle in subtitles {
        try render(
            subtitle,
            modernFont: modernFont,
            poemFont: poemFont,
            creditFont: creditFont,
            to: outputURL.appendingPathComponent("\(subtitle.id).png")
        )
    }
} catch {
    FileHandle.standardError.write(Data("error: \(error)\n".utf8))
    exit(1)
}
