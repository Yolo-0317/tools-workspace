#!/usr/bin/env swift

import AppKit
import CoreText
import Foundation

struct Subtitle: Decodable {
    let id: String
    let text: String
    let start: Double
    let end: Double
    let highlight: String
    let attribution: String?
}

enum RenderError: Error, CustomStringConvertible {
    case usage, unavailableFont, bitmapCreation, pngEncoding
    case missingFont(String)

    var description: String {
        switch self {
        case .usage: return "usage: render_subtitle_cards.swift <manifest.json> <output-directory>"
        case .missingFont(let path): return "subtitle font does not exist: \(path)"
        case .unavailableFont: return "Xingkai SC is unavailable"
        case .bitmapCreation: return "unable to create RGBA bitmap"
        case .pngEncoding: return "unable to encode subtitle PNG"
        }
    }
}

let canvasWidth = 720
let canvasHeight = 1280

func verticalColumns(from text: String) -> [String] {
    let separators = CharacterSet(charactersIn: "，。！？、｜|\n")
    return text.components(separatedBy: separators).filter { !$0.isEmpty }
}

func drawVerticalColumn(
    _ text: String,
    x: CGFloat,
    top: CGFloat,
    font: NSFont,
    highlight: String,
    step: CGFloat = 75
) {
    let normalColor = NSColor(calibratedRed: 1.0, green: 0.98, blue: 0.92, alpha: 1)
    let highlightColor = NSColor(calibratedRed: 1.0, green: 0.10, blue: 0.035, alpha: 1)
    let shadow = NSShadow()
    shadow.shadowColor = NSColor(calibratedWhite: 0.01, alpha: 0.92)
    shadow.shadowBlurRadius = 3.5
    shadow.shadowOffset = NSSize(width: 2.2, height: -2.2)

    for (index, character) in text.enumerated() {
        let string = String(character)
        let isHighlight = !highlight.isEmpty && highlight.contains(character)
        let attributed = NSAttributedString(string: string, attributes: [
            .font: font,
            .foregroundColor: isHighlight ? highlightColor : normalColor,
            .strokeColor: isHighlight
                ? NSColor(calibratedRed: 0.34, green: 0.01, blue: 0.0, alpha: 0.94)
                : NSColor(calibratedWhite: 0.01, alpha: 0.90),
            .strokeWidth: -1.6,
            .shadow: shadow
        ])
        let size = attributed.size()
        let screenY = top + CGFloat(index) * step
        attributed.draw(in: NSRect(
            x: x - size.width / 2,
            y: CGFloat(canvasHeight) - screenY - size.height,
            width: size.width + 4,
            height: size.height + 4
        ))
    }
}

func render(_ subtitle: Subtitle, font: NSFont, attributionFont: NSFont, to outputURL: URL) throws {
    guard let bitmap = NSBitmapImageRep(
        bitmapDataPlanes: nil, pixelsWide: canvasWidth, pixelsHigh: canvasHeight,
        bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false,
        colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0
    ), let context = NSGraphicsContext(bitmapImageRep: bitmap) else {
        throw RenderError.bitmapCreation
    }

    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.current = context
    NSColor.clear.setFill()
    NSRect(x: 0, y: 0, width: canvasWidth, height: canvasHeight).fill()
    let columns = verticalColumns(from: subtitle.text)
    let hasAttribution = !(subtitle.attribution ?? "").isEmpty
    let rightmostX = (hasAttribution ? 160 : 84) + CGFloat(columns.count - 1) * 82
    for (index, column) in columns.enumerated() {
        drawVerticalColumn(column, x: rightmostX - CGFloat(index) * 82, top: 94, font: font, highlight: subtitle.highlight)
    }
    if let attribution = subtitle.attribution, !attribution.isEmpty {
        drawVerticalColumn(
            attribution,
            x: 66,
            top: 112,
            font: attributionFont,
            highlight: "",
            step: 39
        )
    }
    NSGraphicsContext.restoreGraphicsState()

    guard let png = bitmap.representation(using: .png, properties: [:]) else {
        throw RenderError.pngEncoding
    }
    try png.write(to: outputURL, options: .atomic)
}

do {
    guard CommandLine.arguments.count == 3 else { throw RenderError.usage }
    let manifestURL = URL(fileURLWithPath: CommandLine.arguments[1])
    let outputDirectory = URL(fileURLWithPath: CommandLine.arguments[2], isDirectory: true)
    let fontPath = ProcessInfo.processInfo.environment["SUBTITLE_FONT"]
        ?? "/System/Library/AssetsV2/com_apple_MobileAsset_Font7/aa99d0b2bad7f797f38b49d46cde28fd4b58876e.asset/AssetData/Xingkai.ttc"
    guard FileManager.default.fileExists(atPath: fontPath) else { throw RenderError.missingFont(fontPath) }
    CTFontManagerRegisterFontsForURL(URL(fileURLWithPath: fontPath) as CFURL, .process, nil)
    guard let font = NSFont(name: "STXingkaiSC-Light", size: 70),
          let attributionFont = NSFont(name: "STXingkaiSC-Light", size: 31) else {
        throw RenderError.unavailableFont
    }

    let subtitles = try JSONDecoder().decode([Subtitle].self, from: Data(contentsOf: manifestURL))
    try FileManager.default.createDirectory(at: outputDirectory, withIntermediateDirectories: true)
    for subtitle in subtitles {
        try render(
            subtitle,
            font: font,
            attributionFont: attributionFont,
            to: outputDirectory.appendingPathComponent("\(subtitle.id).png")
        )
    }
} catch {
    FileHandle.standardError.write(Data("error: \(error)\n".utf8))
    exit(1)
}
