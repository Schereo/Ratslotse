#!/usr/bin/env swift

import CoreGraphics
import Foundation
import ImageIO
import UniformTypeIdentifiers

struct AnimationSheet {
    let source: String
    let sourceColumns: Int
    let start: Int
    let count: Int
    let asset: String
}

let sheets = [
    // Aus lotti.json des 384-px-Backens vom 01.09.26 (sechs Gruppen statt
    // vier — die Blätter durften bei doppelter Kachelkante nicht über
    // 4096 px wachsen). Wer neu backt, gleicht start/count/sourceColumns
    // gegen ratslotse-social/assets/lotti/lotti.json ab.
    AnimationSheet(source: "lotti-kern.png", sourceColumns: 5, start: 0, count: 1, asset: "LottiSpriteRest"),
    .init(source: "lotti-kern.png", sourceColumns: 5, start: 1, count: 6, asset: "LottiSpriteBlink"),
    .init(source: "lotti-kern.png", sourceColumns: 5, start: 7, count: 13, asset: "LottiSpriteNod"),
    .init(source: "lotti-gesten.png", sourceColumns: 10, start: 0, count: 18, asset: "LottiSpriteCelebrate"),
    .init(source: "lotti-gesten.png", sourceColumns: 10, start: 18, count: 16, asset: "LottiSpriteAmazed"),
    .init(source: "lotti-gesten.png", sourceColumns: 10, start: 34, count: 24, asset: "LottiSpriteWave"),
    .init(source: "lotti-zustaende.png", sourceColumns: 10, start: 0, count: 21, asset: "LottiSpriteThinking"),
    .init(source: "lotti-zustaende.png", sourceColumns: 10, start: 21, count: 20, asset: "LottiSpriteSleeping"),
    .init(source: "lotti-haltung.png", sourceColumns: 10, start: 0, count: 17, asset: "LottiSpriteShakeHead"),
    .init(source: "lotti-zustaende.png", sourceColumns: 10, start: 41, count: 26, asset: "LottiSpriteSearching"),
    .init(source: "lotti-haltung.png", sourceColumns: 10, start: 17, count: 19, asset: "LottiSpriteBow"),
    .init(source: "lotti-zustaende.png", sourceColumns: 10, start: 67, count: 12, asset: "LottiSpriteJuggling"),
    .init(source: "lotti-zeigen.png", sourceColumns: 7, start: 0, count: 10, asset: "LottiSpritePointRight"),
    .init(source: "lotti-zeigen.png", sourceColumns: 7, start: 10, count: 10, asset: "LottiSpritePointLeft"),
    .init(source: "lotti-zeigen.png", sourceColumns: 7, start: 20, count: 10, asset: "LottiSpritePointUp"),
    .init(source: "lotti-zeigen.png", sourceColumns: 7, start: 30, count: 10, asset: "LottiSpritePointDown"),
    .init(source: "lotti-gesten.png", sourceColumns: 10, start: 58, count: 16, asset: "LottiSpriteLaugh"),
    .init(source: "lotti-haltung.png", sourceColumns: 10, start: 36, count: 12, asset: "LottiSpriteSigh"),
    .init(source: "lotti-gesten.png", sourceColumns: 10, start: 74, count: 18, asset: "LottiSpriteClap"),
    .init(source: "lotti-zeigen.png", sourceColumns: 7, start: 40, count: 8, asset: "LottiSpritePointSelf"),
    .init(source: "lotti-haltung.png", sourceColumns: 10, start: 48, count: 8, asset: "LottiSpriteRaiseHand"),
    .init(source: "lotti-haltung.png", sourceColumns: 10, start: 56, count: 22, asset: "LottiSpriteExplain"),
    .init(source: "lotti-zustaende.png", sourceColumns: 10, start: 79, count: 18, asset: "LottiSpriteWaiting"),
    .init(source: "lotti-haltung.png", sourceColumns: 10, start: 78, count: 8, asset: "LottiSpriteSad"),
    .init(source: "lotti-haltung.png", sourceColumns: 10, start: 86, count: 13, asset: "LottiSpriteStartled"),
    .init(source: "lotti-symbole.png", sourceColumns: 6, start: 0, count: 10, asset: "LottiSpriteIdea"),
    .init(source: "lotti-symbole.png", sourceColumns: 6, start: 10, count: 10, asset: "LottiSpriteQuestion"),
    .init(source: "lotti-symbole.png", sourceColumns: 6, start: 20, count: 10, asset: "LottiSpriteLike"),
]

guard CommandLine.arguments.count == 3 else {
    FileHandle.standardError.write(Data("Usage: make_lotti_ios_sprites.swift <rendered-png-directory> <Assets.xcassets>\n".utf8))
    exit(64)
}

let sourceDirectory = URL(fileURLWithPath: CommandLine.arguments[1], isDirectory: true)
let assetCatalog = URL(fileURLWithPath: CommandLine.arguments[2], isDirectory: true)
let manager = FileManager.default
var decoded: [String: CGImage] = [:]

for sheet in sheets {
    let sourceImage: CGImage
    if let cached = decoded[sheet.source] {
        sourceImage = cached
    } else {
        let url = sourceDirectory.appendingPathComponent(sheet.source)
        guard let source = CGImageSourceCreateWithURL(url as CFURL, nil),
              let image = CGImageSourceCreateImageAtIndex(source, 0, nil) else {
            fatalError("Could not decode \(url.path)")
        }
        decoded[sheet.source] = image
        sourceImage = image
    }

    let tile = sourceImage.width / sheet.sourceColumns
    let outputColumns = min(8, sheet.count)
    let outputRows = Int(ceil(Double(sheet.count) / Double(outputColumns)))
    let width = outputColumns * tile
    let height = outputRows * tile
    guard let context = CGContext(
        data: nil,
        width: width,
        height: height,
        bitsPerComponent: 8,
        bytesPerRow: 0,
        space: CGColorSpaceCreateDeviceRGB(),
        bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue
    ) else { fatalError("Could not create output context") }

    for offset in 0..<sheet.count {
        let index = sheet.start + offset
        let sourceRect = CGRect(
            x: (index % sheet.sourceColumns) * tile,
            y: (index / sheet.sourceColumns) * tile,
            width: tile,
            height: tile
        )
        guard let frame = sourceImage.cropping(to: sourceRect) else {
            fatalError("Could not crop frame \(index) from \(sheet.source)")
        }
        let outputRow = offset / outputColumns
        let outputColumn = offset % outputColumns
        context.draw(frame, in: CGRect(
            x: outputColumn * tile,
            y: (outputRows - outputRow - 1) * tile,
            width: tile,
            height: tile
        ))
    }

    guard let output = context.makeImage() else { fatalError("Could not create \(sheet.asset)") }
    let imageSet = assetCatalog.appendingPathComponent("\(sheet.asset).imageset", isDirectory: true)
    try manager.createDirectory(at: imageSet, withIntermediateDirectories: true)
    let png = imageSet.appendingPathComponent("\(sheet.asset).png")
    guard let destination = CGImageDestinationCreateWithURL(
        png as CFURL,
        UTType.png.identifier as CFString,
        1,
        nil
    ) else { fatalError("Could not create PNG destination") }
    CGImageDestinationAddImage(destination, output, nil)
    guard CGImageDestinationFinalize(destination) else { fatalError("Could not write \(png.path)") }

    let contents = """
    {
      "images" : [
        {
          "filename" : "\(sheet.asset).png",
          "idiom" : "universal",
          "scale" : "1x"
        }
      ],
      "info" : {
        "author" : "xcode",
        "version" : 1
      }
    }
    """
    try Data(contents.utf8).write(to: imageSet.appendingPathComponent("Contents.json"))
    print("\(sheet.asset): \(sheet.count) frames, \(outputColumns) columns, \(tile) px")
}
