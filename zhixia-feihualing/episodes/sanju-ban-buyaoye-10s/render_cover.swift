import AppKit
import Foundation

let args = CommandLine.arguments
guard args.count == 3, let frame = NSImage(contentsOfFile: args[1]),
      let bitmap = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: 1080, pixelsHigh: 1920,
        bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false,
        colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0),
      let context = NSGraphicsContext(bitmapImageRep: bitmap) else { exit(1) }
NSGraphicsContext.saveGraphicsState()
NSGraphicsContext.current = context
NSColor(calibratedRed: 0.84, green: 0.80, blue: 0.74, alpha: 1).setFill()
NSRect(x: 0, y: 0, width: 1080, height: 1920).fill()
frame.draw(in: NSRect(x: 0, y: 19.35, width: 1080, height: 1881.3),
           from: .zero, operation: .copy, fraction: 1)
func centered(_ content: String, _ size: CGFloat, _ y: CGFloat, _ color: NSColor) {
    let text = NSAttributedString(string: content, attributes: [
        .font: NSFont(name: "PingFangSC-Semibold", size: size) ?? NSFont.systemFont(ofSize: size, weight: .semibold),
        .foregroundColor: color
    ])
    text.draw(at: NSPoint(x: (1080 - text.size().width) / 2, y: y))
}
centered("栀夏 · 三句半", 34, 1830, NSColor(calibratedRed: 0.40, green: 0.36, blue: 0.31, alpha: 1))
centered("今晚不熬夜", 112, 1674, NSColor(calibratedRed: 0.20, green: 0.22, blue: 0.20, alpha: 1))
centered("明天再说！", 112, 1534, NSColor(calibratedRed: 0.65, green: 0.25, blue: 0.17, alpha: 1))
NSGraphicsContext.restoreGraphicsState()
guard let png = bitmap.representation(using: .png, properties: [:]) else { exit(1) }
try png.write(to: URL(fileURLWithPath: args[2]), options: .atomic)
