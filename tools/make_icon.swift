// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 hap67 and contributors. Part of indigo-weathercat; see LICENSE.
import AppKit

// Draws the plugin icon (Contents/Resources/icon.png): a cloud with cat ears in front of a sun, on a blue rounded square,
// with a small thermometer. Usage: swift tools/make_icon.swift WeatherCat.indigoPlugin/Contents/Resources/icon.png
let size: CGFloat = 256
let rep = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: Int(size), pixelsHigh: Int(size),
                           bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false,
                           colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0)!
NSGraphicsContext.saveGraphicsState()
NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: rep)

func rgb(_ r: CGFloat, _ g: CGFloat, _ b: CGFloat, _ a: CGFloat = 1) -> NSColor {
    NSColor(calibratedRed: r, green: g, blue: b, alpha: a)
}

// Background.
let bg = NSBezierPath(roundedRect: NSRect(x: 8, y: 8, width: 240, height: 240), xRadius: 54, yRadius: 54)
NSGraphicsContext.saveGraphicsState()
bg.addClip()
NSGradient(starting: rgb(0.38, 0.70, 0.99), ending: rgb(0.06, 0.32, 0.74))!
    .draw(in: NSRect(x: 0, y: 0, width: size, height: size), angle: -90)
NSGraphicsContext.restoreGraphicsState()

// Sun with rays, upper right.
let sun = rgb(1.0, 0.80, 0.20)
let sunC = CGPoint(x: 178, y: 180)
sun.setStroke()
for i in 0..<8 {
    let a = CGFloat(i) * .pi / 4
    let ray = NSBezierPath()
    ray.lineWidth = 8
    ray.lineCapStyle = .round
    ray.move(to: CGPoint(x: sunC.x + cos(a) * 40, y: sunC.y + sin(a) * 40))
    ray.line(to: CGPoint(x: sunC.x + cos(a) * 54, y: sunC.y + sin(a) * 54))
    ray.stroke()
}
sun.setFill()
NSBezierPath(ovalIn: NSRect(x: sunC.x - 30, y: sunC.y - 30, width: 60, height: 60)).fill()

// Cloud body with two cat ears, drawn with a soft shadow.
let cloud = NSBezierPath()
cloud.appendOval(in: NSRect(x: 30, y: 52, width: 86, height: 86))
cloud.appendOval(in: NSRect(x: 76, y: 70, width: 110, height: 110))
cloud.appendOval(in: NSRect(x: 146, y: 52, width: 82, height: 82))
cloud.appendRoundedRect(NSRect(x: 52, y: 52, width: 156, height: 56), xRadius: 28, yRadius: 28)
let earL = NSBezierPath()
earL.move(to: CGPoint(x: 92, y: 150))
earL.line(to: CGPoint(x: 98, y: 210))
earL.line(to: CGPoint(x: 134, y: 172))
earL.close()
let earR = NSBezierPath()
earR.move(to: CGPoint(x: 168, y: 150))
earR.line(to: CGPoint(x: 162, y: 210))
earR.line(to: CGPoint(x: 126, y: 172))
earR.close()

NSGraphicsContext.saveGraphicsState()
let shadow = NSShadow()
shadow.shadowColor = rgb(0, 0.1, 0.3, 0.35)
shadow.shadowOffset = NSSize(width: 0, height: -5)
shadow.shadowBlurRadius = 10
shadow.set()
NSColor.white.setFill()
cloud.fill()
earL.fill()
earR.fill()
NSGraphicsContext.restoreGraphicsState()
NSColor.white.setFill()
cloud.fill(); earL.fill(); earR.fill()

// Inner ears.
rgb(0.98, 0.72, 0.78).setFill()
let innerL = NSBezierPath()
innerL.move(to: CGPoint(x: 101, y: 166)); innerL.line(to: CGPoint(x: 104, y: 196)); innerL.line(to: CGPoint(x: 122, y: 175)); innerL.close()
innerL.fill()
let innerR = NSBezierPath()
innerR.move(to: CGPoint(x: 159, y: 166)); innerR.line(to: CGPoint(x: 156, y: 196)); innerR.line(to: CGPoint(x: 138, y: 175)); innerR.close()
innerR.fill()

// Face: eyes and a small nose.
let face = rgb(0.10, 0.22, 0.42)
face.setFill()
NSBezierPath(ovalIn: NSRect(x: 106, y: 120, width: 13, height: 17)).fill()
NSBezierPath(ovalIn: NSRect(x: 141, y: 120, width: 13, height: 17)).fill()
let nose = NSBezierPath()
nose.move(to: CGPoint(x: 124, y: 112)); nose.line(to: CGPoint(x: 136, y: 112)); nose.line(to: CGPoint(x: 130, y: 104)); nose.close()
rgb(0.95, 0.55, 0.62).setFill()
nose.fill()
face.setStroke()
let mouth = NSBezierPath()
mouth.lineWidth = 3; mouth.lineCapStyle = .round
mouth.move(to: CGPoint(x: 130, y: 104)); mouth.curve(to: CGPoint(x: 118, y: 98), controlPoint1: CGPoint(x: 128, y: 98), controlPoint2: CGPoint(x: 122, y: 96))
mouth.move(to: CGPoint(x: 130, y: 104)); mouth.curve(to: CGPoint(x: 142, y: 98), controlPoint1: CGPoint(x: 132, y: 98), controlPoint2: CGPoint(x: 138, y: 96))
mouth.stroke()

// Thermometer, lower left.
let tube = NSBezierPath(roundedRect: NSRect(x: 40, y: 34, width: 18, height: 64), xRadius: 9, yRadius: 9)
let bulb = NSBezierPath(ovalIn: NSRect(x: 33, y: 22, width: 32, height: 32))
face.setFill()
NSBezierPath(roundedRect: NSRect(x: 36, y: 30, width: 26, height: 72), xRadius: 13, yRadius: 13).fill()
NSBezierPath(ovalIn: NSRect(x: 29, y: 18, width: 40, height: 40)).fill()
NSColor.white.setFill()
tube.fill(); bulb.fill()
rgb(0.85, 0.20, 0.20).setFill()
NSBezierPath(roundedRect: NSRect(x: 45, y: 40, width: 8, height: 40), xRadius: 4, yRadius: 4).fill()
NSBezierPath(ovalIn: NSRect(x: 38, y: 27, width: 22, height: 22)).fill()

NSGraphicsContext.restoreGraphicsState()
let png = rep.representation(using: .png, properties: [:])!
try! png.write(to: URL(fileURLWithPath: CommandLine.arguments[1]))
print("wrote", CommandLine.arguments[1])
