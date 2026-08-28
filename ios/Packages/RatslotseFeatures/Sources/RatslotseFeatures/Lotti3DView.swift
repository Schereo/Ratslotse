import RatslotseDesign
import SwiftUI

/// Original renders from the procedural Three.js model in the
/// `ratslotse-social/studio` repository. Keeping the scene mapping here makes
/// it explicit which source pose belongs to each app illustration.
enum Lotti3DScene: Sendable {
    case wave
    case questions
    case reading
    case explain
    case celebrate
    case children

    var assetName: String {
        switch self {
        case .wave: "Lotti3DWave"
        case .questions: "Lotti3DQuestions"
        case .reading: "Lotti3DReading"
        case .explain: "Lotti3DExplain"
        case .celebrate: "Lotti3DCelebrate"
        case .children: "Lotti3DChildren"
        }
    }

    var accessibilityLabel: String {
        switch self {
        case .wave: "Lotti, die Lotsenmöwe, winkt."
        case .questions: "Lotti und ein Küken haben eine Frage."
        case .reading: "Lotti liest Ratsunterlagen."
        case .explain: "Lotti erklärt zwei Küken eine Grafik."
        case .celebrate: "Lotti jubelt mit einem Küken und einer Krabbe."
        case .children: "Lotti hört zwei Küken zu."
        }
    }
}

struct Lotti3DView: View {
    let scene: Lotti3DScene
    var animated = true

    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var isFloating = false

    var body: some View {
        Image(scene.assetName)
            .resizable()
            .renderingMode(.original)
            .interpolation(.high)
            .scaledToFit()
            .offset(y: isFloating ? -2.5 : 2.5)
            .accessibilityElement(children: .ignore)
            .accessibilityLabel(scene.accessibilityLabel)
            .task(id: scene.assetName) {
                guard animated, !reduceMotion else { return }
                withAnimation(.easeInOut(duration: 1.75).repeatForever(autoreverses: true)) {
                    isFloating = true
                }
            }
    }
}

/// A compact, account-stable profile portrait made from the existing Lotti
/// scenes. The account id deliberately selects a pose deterministically so
/// the avatar feels personal without changing unexpectedly between launches.
struct LottiProfileAvatar: View {
    let accountID: Int
    var size: CGFloat = 54
    var isSelected = false

    private var scene: Lotti3DScene {
        let scenes: [Lotti3DScene] = [.wave, .reading, .questions]
        let index = Int(accountID.magnitude % UInt(scenes.count))
        return scenes[index]
    }

    private var shape: RoundedRectangle {
        RoundedRectangle(cornerRadius: size * 0.30, style: .continuous)
    }

    var body: some View {
        ZStack {
            shape
                .fill(RatsColor.primary.opacity(isSelected ? 0.20 : 0.11))

            Image(scene.assetName)
                .resizable()
                .renderingMode(.original)
                .interpolation(.high)
                .scaledToFit()
                .padding(size * 0.055)
        }
        .frame(width: size, height: size)
        .clipShape(shape)
        .overlay {
            shape.stroke(
                isSelected ? RatsColor.primary.opacity(0.42) : RatsColor.primary.opacity(0.20),
                lineWidth: 1
            )
        }
        .overlay(alignment: .bottomTrailing) {
            Circle()
                .fill(RatsColor.signal)
                .frame(width: size * 0.24, height: size * 0.24)
                .overlay(Circle().stroke(RatsColor.card, lineWidth: size < 44 ? 1.5 : 2))
                .padding(size * 0.035)
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("Lotti als Profilbild")
    }
}
