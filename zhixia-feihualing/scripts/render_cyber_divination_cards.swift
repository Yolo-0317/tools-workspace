#!/usr/bin/env swift

import AppKit
import CoreText
import Foundation

struct CyberCard: Decodable {
    let id: String
    let kind: String
    let text: String
    let secondary: String?
    let attribution: String?
}

enum RenderError: Error {
    case usage, bitmapCreation, pngEncoding, unavailableFont, unknownKind(String)
}

let canvasWidth = 720
let canvasHeight = 1280

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
let cyberCyan = NSColor(
    calibratedRed: 178.0 / 255.0,
    green: 226.0 / 255.0,
    blue: 220.0 / 255.0,
    alpha: 0.96
)
let cyberGold = NSColor(
    calibratedRed: 218.0 / 255.0,
    green: 194.0 / 255.0,
    blue: 132.0 / 255.0,
    alpha: 0.96
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

func drawCentered(_ text: String, font: NSFont, color: NSColor, screenY: CGFloat) {
    let value = NSAttributedString(
        string: text,
        attributes: attributes(font: font, color: color)
    )
    let size = value.size()
    value.draw(in: NSRect(
        x: (CGFloat(canvasWidth) - size.width) / 2,
        y: CGFloat(canvasHeight) - screenY - size.height,
        width: size.width + 6,
        height: size.height + 6
    ))
}

func fillScreenRect(
    x: CGFloat,
    screenY: CGFloat,
    width: CGFloat,
    rectHeight: CGFloat,
    color: NSColor
) {
    color.setFill()
    NSRect(
        x: x,
        y: CGFloat(canvasHeight) - screenY - rectHeight,
        width: width,
        height: rectHeight
    ).fill()
}

func drawDialogue(_ text: String, font: NSFont) {
    drawCentered(text, font: font, color: poemIvory, screenY: 940)
}

func drawHexagram(
    title: String,
    quote: String,
    attribution: String?,
    titleFont: NSFont,
    quoteFont: NSFont,
    attributionFont: NSFont
) {
    drawCentered(title, font: titleFont, color: cyberGold, screenY: 270)

    let topToBottomYang = [true, false, false, false, false, true]
    let fullWidth: CGFloat = 240
    let segmentWidth: CGFloat = 98
    let gap: CGFloat = fullWidth - segmentWidth * 2
    let x = (CGFloat(canvasWidth) - fullWidth) / 2
    for (index, isYang) in topToBottomYang.enumerated() {
        let y = 360 + CGFloat(index) * 42
        if isYang {
            fillScreenRect(
                x: x,
                screenY: y,
                width: fullWidth,
                rectHeight: 12,
                color: cyberCyan
            )
        } else {
            fillScreenRect(
                x: x,
                screenY: y,
                width: segmentWidth,
                rectHeight: 12,
                color: cyberCyan
            )
            fillScreenRect(
                x: x + segmentWidth + gap,
                screenY: y,
                width: segmentWidth,
                rectHeight: 12,
                color: cyberCyan
            )
        }
    }

    drawCentered(quote, font: quoteFont, color: poemIvory, screenY: 650)
    if let attribution, !attribution.isEmpty {
        drawCentered(
            attribution,
            font: attributionFont,
            color: attributionIvory,
            screenY: 705
        )
    }
}

func render(
    _ card: CyberCard,
    dialogueFont: NSFont,
    titleFont: NSFont,
    quoteFont: NSFont,
    smallFont: NSFont,
    to url: URL
) throws {
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
        throw RenderError.bitmapCreation
    }

    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.current = context
    NSColor.clear.setFill()
    NSRect(x: 0, y: 0, width: canvasWidth, height: canvasHeight).fill()

    switch card.kind {
    case "dialogue":
        drawDialogue(card.text, font: dialogueFont)
    case "hexagram":
        drawHexagram(
            title: card.text,
            quote: card.secondary ?? "",
            attribution: card.attribution,
            titleFont: titleFont,
            quoteFont: quoteFont,
            attributionFont: smallFont
        )
    case "disclaimer":
        drawCentered(card.text, font: smallFont, color: attributionIvory, screenY: 1160)
    case "title":
        drawCentered(card.text, font: dialogueFont, color: cyberGold, screenY: 92)
    default:
        throw RenderError.unknownKind(card.kind)
    }

    NSGraphicsContext.restoreGraphicsState()
    guard let png = bitmap.representation(using: .png, properties: [:]) else {
        throw RenderError.pngEncoding
    }
    try png.write(to: url, options: .atomic)
}

do {
    guard CommandLine.arguments.count == 3 else {
        throw RenderError.usage
    }
    let manifest = URL(fileURLWithPath: CommandLine.arguments[1])
    let output = URL(fileURLWithPath: CommandLine.arguments[2], isDirectory: true)
    let fontPath = ProcessInfo.processInfo.environment["SUBTITLE_FONT"]
        ?? "/System/Library/AssetsV2/com_apple_MobileAsset_Font7/aa99d0b2bad7f797f38b49d46cde28fd4b58876e.asset/AssetData/Xingkai.ttc"
    let smallFontPath = ProcessInfo.processInfo.environment["SUBTITLE_CREDIT_FONT"]
        ?? "/System/Library/AssetsV2/com_apple_MobileAsset_Font7/54a2ad3dac6cac875ad675d7d273dc425010a877.asset/AssetData/Kaiti.ttc"
    CTFontManagerRegisterFontsForURL(URL(fileURLWithPath: fontPath) as CFURL, .process, nil)
    CTFontManagerRegisterFontsForURL(URL(fileURLWithPath: smallFontPath) as CFURL, .process, nil)
    guard let dialogueFont = NSFont(name: "STXingkaiSC-Bold", size: 48),
          let titleFont = NSFont(name: "STXingkaiSC-Bold", size: 66),
          let quoteFont = NSFont(name: "STKaitiSC-Regular", size: 30),
          let smallFont = NSFont(name: "STKaitiSC-Regular", size: 22) else {
        throw RenderError.unavailableFont
    }

    let cards = try JSONDecoder().decode(
        [CyberCard].self,
        from: Data(contentsOf: manifest)
    )
    try FileManager.default.createDirectory(at: output, withIntermediateDirectories: true)
    for card in cards {
        try render(
            card,
            dialogueFont: dialogueFont,
            titleFont: titleFont,
            quoteFont: quoteFont,
            smallFont: smallFont,
            to: output.appendingPathComponent("\(card.id).png")
        )
    }
} catch {
    FileHandle.standardError.write(Data("error: \(error)\n".utf8))
    exit(1)
}
