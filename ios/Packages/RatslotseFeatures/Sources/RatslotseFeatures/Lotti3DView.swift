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
