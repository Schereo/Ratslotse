import RatslotseDesign
import SwiftUI
import UIKit

/// Regungen aus dem versionierten Sprite-Bündel in `ratslotse-social`.
/// Die Namen sind bewusst semantisch: Aufrufer wählen eine Aussage, nicht
/// ein bestimmtes Blatt oder eine Bildnummer.
enum LottiAnimation: String, CaseIterable, Sendable {
    case rest, blink, nod, celebrate, amazed, wave
    case thinking, sleeping, shakeHead, searching, bow, juggling
    case pointRight, pointLeft, pointUp, pointDown
    case laugh, sigh, clap, pointSelf, raiseHand, explain, waiting, sad, startled
    case idea, question, like

    fileprivate var descriptor: LottiSpriteDescriptor {
        switch self {
        case .rest: .init("LottiSpriteRest", columns: 1, start: 0, count: 1, fps: 12)
        case .blink: .init("LottiSpriteBlink", columns: 6, start: 0, count: 6, fps: 12)
        case .nod: .init("LottiSpriteNod", columns: 8, start: 0, count: 13, fps: 12)
        case .celebrate: .init("LottiSpriteCelebrate", columns: 8, start: 0, count: 18, fps: 12)
        case .amazed: .init("LottiSpriteAmazed", columns: 8, start: 0, count: 16, fps: 12)
        case .wave: .init("LottiSpriteWave", columns: 8, start: 0, count: 24, fps: 12)
        case .thinking: .init("LottiSpriteThinking", columns: 8, start: 0, count: 21, fps: 8, sourceLoops: true)
        case .sleeping: .init("LottiSpriteSleeping", columns: 8, start: 0, count: 20, fps: 6, sourceLoops: true)
        case .shakeHead: .init("LottiSpriteShakeHead", columns: 8, start: 0, count: 17, fps: 12)
        case .searching: .init("LottiSpriteSearching", columns: 8, start: 0, count: 26, fps: 8, sourceLoops: true)
        case .bow: .init("LottiSpriteBow", columns: 8, start: 0, count: 19, fps: 12)
        case .juggling: .init("LottiSpriteJuggling", columns: 8, start: 0, count: 12, fps: 12, sourceLoops: true)
        case .pointRight: .init("LottiSpritePointRight", columns: 8, start: 0, count: 10, fps: 12, autoreverses: true, hold: 9)
        case .pointLeft: .init("LottiSpritePointLeft", columns: 8, start: 0, count: 10, fps: 12, autoreverses: true, hold: 9)
        case .pointUp: .init("LottiSpritePointUp", columns: 8, start: 0, count: 10, fps: 12, autoreverses: true, hold: 9)
        case .pointDown: .init("LottiSpritePointDown", columns: 8, start: 0, count: 10, fps: 12, autoreverses: true, hold: 9)
        case .laugh: .init("LottiSpriteLaugh", columns: 8, start: 0, count: 16, fps: 12)
        case .sigh: .init("LottiSpriteSigh", columns: 8, start: 0, count: 12, fps: 6)
        case .clap: .init("LottiSpriteClap", columns: 8, start: 0, count: 18, fps: 12)
        case .pointSelf: .init("LottiSpritePointSelf", columns: 8, start: 0, count: 8, fps: 12, autoreverses: true, hold: 7)
        case .raiseHand: .init("LottiSpriteRaiseHand", columns: 8, start: 0, count: 8, fps: 12, autoreverses: true, hold: 7)
        case .explain: .init("LottiSpriteExplain", columns: 8, start: 0, count: 22, fps: 12)
        case .waiting: .init("LottiSpriteWaiting", columns: 8, start: 0, count: 18, fps: 6, sourceLoops: true)
        case .sad: .init("LottiSpriteSad", columns: 8, start: 0, count: 8, fps: 8, autoreverses: true, hold: 7)
        case .startled: .init("LottiSpriteStartled", columns: 8, start: 0, count: 13, fps: 12)
        case .idea: .init("LottiSpriteIdea", columns: 8, start: 0, count: 10, fps: 12, autoreverses: true, hold: 9)
        case .question: .init("LottiSpriteQuestion", columns: 8, start: 0, count: 10, fps: 12, autoreverses: true, hold: 9)
        case .like: .init("LottiSpriteLike", columns: 8, start: 0, count: 10, fps: 12, autoreverses: true, hold: 9)
        }
    }

    var accessibilityLabel: String {
        switch self {
        case .juggling: "Lotti jongliert während des Ladens."
        case .thinking: "Lotti denkt nach."
        case .searching: "Lotti sucht in den Ratsunterlagen."
        case .sleeping: "Lotti schläft."
        case .shakeHead, .sad: "Lotti ist traurig, weil etwas nicht geklappt hat."
        case .question: "Lotti stellt eine Frage."
        case .explain: "Lotti erklärt etwas."
        case .celebrate, .clap, .laugh: "Lotti freut sich."
        case .wave: "Lotti winkt."
        case .idea: "Lotti hat eine Idee."
        case .like: "Lotti zeigt ein Herz."
        case .nod: "Lotti nickt zustimmend."
        default: "Lotti, die Lotsenmöwe."
        }
    }

    var sourceFrameCount: Int { descriptor.count }
}

private struct LottiSpriteDescriptor: Sendable {
    let assetName: String
    let columns: Int
    let start: Int
    let count: Int
    let fps: Int
    let sourceLoops: Bool
    let autoreverses: Bool
    let hold: Int?

    init(
        _ assetName: String,
        columns: Int,
        start: Int,
        count: Int,
        fps: Int,
        sourceLoops: Bool = false,
        autoreverses: Bool = false,
        hold: Int? = nil
    ) {
        self.assetName = assetName
        self.columns = columns
        self.start = start
        self.count = count
        self.fps = fps
        self.sourceLoops = sourceLoops
        self.autoreverses = autoreverses
        self.hold = hold
    }
}

/// Spielt eine gebackene 3D-Regung ohne WebView oder Laufzeit-3D-Engine ab.
/// Nicht endlose Gesten kehren nach einer kurzen Ruhepause wieder, damit eine
/// länger sichtbare Illustration lebendig bleibt, aber nicht hektisch wirkt.
struct LottiSpriteView: View {
    let animation: LottiAnimation
    var animated = true
    var accessibilityLabel: String?

    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @Environment(\.scenePhase) private var scenePhase
    @State private var startedAt = Date.now

    var body: some View {
        let frames = LottiSpriteFrameStore.shared.frames(for: animation)
        Group {
            if frames.isEmpty {
                Image("Lotti3DWave")
                    .resizable()
                    .renderingMode(.original)
                    .scaledToFit()
            } else if animated && !reduceMotion {
                TimelineView(
                    .animation(
                        minimumInterval: 1 / Double(max(animation.descriptor.fps, 1)),
                        paused: scenePhase != .active
                    )
                ) { context in
                    spriteImage(frames[lottiSpriteFrameIndex(
                        elapsed: max(0, context.date.timeIntervalSince(startedAt)),
                        frameCount: frames.count,
                        fps: animation.descriptor.fps
                    )])
                }
            } else {
                spriteImage(LottiSpriteFrameStore.shared.representativeFrame(for: animation) ?? frames[0])
            }
        }
        .aspectRatio(1, contentMode: .fit)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(accessibilityLabel ?? animation.accessibilityLabel)
        .task(id: animation.rawValue) { startedAt = .now }
    }

    private func spriteImage(_ image: UIImage) -> some View {
        Image(uiImage: image)
            .resizable()
            .renderingMode(.original)
            .interpolation(.high)
            .scaledToFit()
    }
}

func lottiSpriteFrameIndex(elapsed: TimeInterval, frameCount: Int, fps: Int) -> Int {
    guard frameCount > 1, fps > 0 else { return 0 }
    return Int(elapsed * Double(fps)) % frameCount
}

private final class LottiSpriteFramesBox: NSObject {
    let frames: [UIImage]
    init(_ frames: [UIImage]) { self.frames = frames }
}

private final class LottiSpriteFrameStore: @unchecked Sendable {
    static let shared = LottiSpriteFrameStore()
    private let cache = NSCache<NSString, LottiSpriteFramesBox>()
    private let representativeCache = NSCache<NSString, UIImage>()

    private init() {
        // The source sheets stay compact on disk. Limit decoded animation
        // frames so screens that use many different gestures cannot grow the
        // process indefinitely during a long session.
        cache.totalCostLimit = 64 * 1_024 * 1_024
        cache.countLimit = 10
    }

    func frames(for animation: LottiAnimation) -> [UIImage] {
        let key = animation.rawValue as NSString
        if let cached = cache.object(forKey: key) { return cached.frames }

        let descriptor = animation.descriptor
        var frames = croppedFrames(for: descriptor)
        guard !frames.isEmpty else { return [] }
        representativeCache.setObject(
            frames[min(descriptor.hold ?? (frames.count - 1) / 2, frames.count - 1)],
            forKey: key
        )

        if descriptor.autoreverses, frames.count > 2 {
            frames.append(contentsOf: frames.dropFirst().dropLast().reversed())
        }
        if !descriptor.sourceLoops {
            let rest = croppedFrames(for: LottiAnimation.rest.descriptor).first ?? frames[0]
            frames.append(contentsOf: Array(repeating: rest, count: max(1, descriptor.fps * 2)))
        }
        cache.setObject(
            LottiSpriteFramesBox(frames),
            forKey: key,
            cost: frames.reduce(0) { total, frame in
                guard let image = frame.cgImage else { return total }
                return total + image.width * image.height * 4
            }
        )
        return frames
    }

    func representativeFrame(for animation: LottiAnimation) -> UIImage? {
        let key = animation.rawValue as NSString
        if let cached = representativeCache.object(forKey: key) { return cached }
        _ = frames(for: animation)
        return representativeCache.object(forKey: key)
    }

    private func croppedFrames(for descriptor: LottiSpriteDescriptor) -> [UIImage] {
        guard let sheet = UIImage(named: descriptor.assetName)?.cgImage else { return [] }
        let tile = sheet.width / descriptor.columns
        return (0..<descriptor.count).compactMap { offset in
            let index = descriptor.start + offset
            let rect = CGRect(
                x: (index % descriptor.columns) * tile,
                y: (index / descriptor.columns) * tile,
                width: tile,
                height: tile
            )
            guard let frame = sheet.cropping(to: rect) else { return nil }
            return UIImage(cgImage: frame, scale: 1, orientation: .up)
        }
    }
}

@MainActor
func lottiSpriteFramesAreAvailable(_ animation: LottiAnimation) -> Bool {
    LottiSpriteFrameStore.shared.frames(for: animation).count >= animation.sourceFrameCount
}
