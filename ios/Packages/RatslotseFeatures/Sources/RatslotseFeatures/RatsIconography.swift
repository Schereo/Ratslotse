import RatslotseDesign
import SwiftUI

enum RatsGlyph: Sendable {
    case home
    case ask
    case calendar
    case decisions
    case topics
    case more
    case search
    case map
    case analysis
    case subscriptions
    case saved
    case quiz
    case profile
    case feedback
    case help
    case legal
    case logout
    case filter
    case back
    case history
    case research

    fileprivate var lucideAssetName: String {
        switch self {
        case .home: "LucideHouse"
        case .ask: "LucideSparkles"
        case .calendar: "LucideCalendarDays"
        case .decisions, .search: "LucideSearch"
        case .topics: "LucideTags"
        case .more: "LucideMoreHorizontal"
        case .map: "LucideMap"
        case .analysis: "LucideBarChart3"
        case .subscriptions: "LucideBell"
        case .saved: "LucideBookmark"
        case .quiz: "LucideTrophy"
        case .profile: "LucideUserCircle"
        case .feedback: "LucideMessageSquarePlus"
        case .help: "LucideCircleHelp"
        case .legal: "LucideScale"
        case .logout: "LucideLogOut"
        case .filter: "LucideSlidersHorizontal"
        case .back: "LucideArrowLeft"
        case .history: "LucideHistory"
        case .research: "LucideFileSearch2"
        }
    }
}

/// The exact Lucide 0.451.0 vectors used by the web app. Keeping the assets
/// local makes rendering deterministic and gives web and native one visual
/// language without introducing a runtime dependency.
struct RatsGlyphView: View {
    let glyph: RatsGlyph
    var color: Color = RatsColor.primary

    var body: some View {
        Image(glyph.lucideAssetName)
            .resizable()
            .renderingMode(.template)
            .scaledToFit()
            .foregroundStyle(color)
            .accessibilityHidden(true)
    }
}
