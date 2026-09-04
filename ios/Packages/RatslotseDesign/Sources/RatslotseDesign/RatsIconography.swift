import SwiftUI
import UIKit

public enum RatsGlyph: Sendable, Equatable {
    /// Die EINZIGE Ausnahme im Pack: Apples Wortbildmarke.
    ///
    /// „Sign in with Apple" darf laut Apples Richtlinien nur mit Apples
    /// eigenem Zeichen beworben werden — ein nachgezeichnetes Lucide-Icha
    /// wäre ein Markenverstoß und ein Ablehnungsgrund im App Review.
    /// Deshalb rendert dieser Fall weiter ein SF Symbol.
    case appleLogo

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
    case tag
    case committee
    case location
    case people
    case chevronDown

    // Aus dem Lucide-Satz der Web-App, eins zu eins.
    case alignLeft
    case arrowRight
    case arrowUpDown
    case arrowUpRight
    case badgeCheck
    case bell
    case bellDot
    case bellOff
    case bellRing
    case book
    case bookmark
    case building2
    case calendarCheck
    case calendarClock
    case calendarDays
    case calendarPlus
    case chartColumn
    case check
    case chevronLeft
    case chevronRight
    case chevronsUpDown
    case circle
    case circleCheck
    case circleCheckBig
    case circleHelp
    case circleMinus
    case clock
    case contact
    case contrast
    case copy
    case copyPlus
    case cornerDownRight
    case crosshair
    case doorOpen
    case download
    case ellipsis
    case euro
    case externalLink
    case eye
    case fileClock
    case fileDown
    case fileSearch
    case fileText
    case flame
    case gavel
    case gitBranch
    case hand
    case hourglass
    case inbox
    case info
    case key
    case landmark
    case leaf
    case lifeBuoy
    case compass
    case baby
    case bus
    case clipboardList
    case coins
    case drama
    case globe
    case graduationCap
    case hammer
    case heartHandshake
    case laptop
    case recycle
    case list
    case listFilter
    case listOrdered
    case lock
    case mailWarning
    case mapPin
    case medal
    case messageCircleMore
    case messageCircleWarning
    case messageSquareQuote
    case messagesSquare
    case minus
    case monitorPlay
    case navigation
    case newspaper
    case paperclip
    case pencil
    case play
    case plus
    case rotateCcw
    case searchX
    case send
    case share
    case shieldCheck
    case slidersHorizontal
    case smartphoneNfc
    case sparkle
    case sparkles
    case squarePen
    case textSearch
    case thumbsDown
    case trash2
    case trendingUp
    case triangleAlert
    case userCog
    case users
    case usersRound
    case wandSparkles
    case waypoints
    case wifiOff
    case wrench
    case zap
    case arrowUp
    case circleDashed
    case circleX
    case eyeOff
    case filePlus
    case square
    case thumbsUp
    case volume2
    case x
    case bug

    /// SF-Symbol-Name statt Asset — nur für `appleLogo` gesetzt.
    fileprivate var systemSymbolName: String? {
        self == .appleLogo ? "apple.logo" : nil
    }
    case lightbulb

    fileprivate var lucideAssetName: String {
        switch self {
        case .appleLogo: ""    // rendert über `systemSymbolName`
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
        case .tag: "LucideTag"
        case .committee: "LucideLandmark"
        case .location: "LucideMapPin"
        case .people: "LucideUsersRound"
        case .chevronDown: "LucideChevronDown"
        case .alignLeft: "LucideAlignLeft"
        case .arrowRight: "LucideArrowRight"
        case .arrowUpDown: "LucideArrowUpDown"
        case .arrowUpRight: "LucideArrowUpRight"
        case .badgeCheck: "LucideBadgeCheck"
        case .bell: "LucideBell"
        case .bellDot: "LucideBellDot"
        case .bellOff: "LucideBellOff"
        case .bellRing: "LucideBellRing"
        case .book: "LucideBook"
        case .bookmark: "LucideBookmark"
        case .building2: "LucideBuilding2"
        case .calendarCheck: "LucideCalendarCheck"
        case .calendarClock: "LucideCalendarClock"
        case .calendarDays: "LucideCalendarDays"
        case .calendarPlus: "LucideCalendarPlus"
        case .chartColumn: "LucideChartColumn"
        case .check: "LucideCheck"
        case .chevronLeft: "LucideChevronLeft"
        case .chevronRight: "LucideChevronRight"
        case .chevronsUpDown: "LucideChevronsUpDown"
        case .circle: "LucideCircle"
        case .circleCheck: "LucideCircleCheck"
        case .circleCheckBig: "LucideCircleCheckBig"
        case .circleHelp: "LucideCircleHelp"
        case .circleMinus: "LucideCircleMinus"
        case .clock: "LucideClock"
        case .contact: "LucideContact"
        case .contrast: "LucideContrast"
        case .copy: "LucideCopy"
        case .copyPlus: "LucideCopyPlus"
        case .cornerDownRight: "LucideCornerDownRight"
        case .crosshair: "LucideCrosshair"
        case .doorOpen: "LucideDoorOpen"
        case .download: "LucideDownload"
        case .ellipsis: "LucideEllipsis"
        case .euro: "LucideEuro"
        case .externalLink: "LucideExternalLink"
        case .eye: "LucideEye"
        case .fileClock: "LucideFileClock"
        case .fileDown: "LucideFileDown"
        case .fileSearch: "LucideFileSearch"
        case .fileText: "LucideFileText"
        case .flame: "LucideFlame"
        case .gavel: "LucideGavel"
        case .gitBranch: "LucideGitBranch"
        case .hand: "LucideHand"
        case .hourglass: "LucideHourglass"
        case .inbox: "LucideInbox"
        case .info: "LucideInfo"
        case .key: "LucideKey"
        case .landmark: "LucideLandmark"
        case .leaf: "LucideLeaf"
        case .lifeBuoy: "LucideLifeBuoy"
        case .compass: "LucideCompass"
        case .baby: "LucideBaby"
        case .bus: "LucideBus"
        case .clipboardList: "LucideClipboardList"
        case .coins: "LucideCoins"
        case .drama: "LucideDrama"
        case .globe: "LucideGlobe"
        case .graduationCap: "LucideGraduationCap"
        case .hammer: "LucideHammer"
        case .heartHandshake: "LucideHeartHandshake"
        case .laptop: "LucideLaptop"
        case .recycle: "LucideRecycle"
        case .list: "LucideList"
        case .listFilter: "LucideListFilter"
        case .listOrdered: "LucideListOrdered"
        case .lock: "LucideLock"
        case .mailWarning: "LucideMailWarning"
        case .mapPin: "LucideMapPin"
        case .medal: "LucideMedal"
        case .messageCircleMore: "LucideMessageCircleMore"
        case .messageCircleWarning: "LucideMessageCircleWarning"
        case .messageSquareQuote: "LucideMessageSquareQuote"
        case .messagesSquare: "LucideMessagesSquare"
        case .minus: "LucideMinus"
        case .monitorPlay: "LucideMonitorPlay"
        case .navigation: "LucideNavigation"
        case .newspaper: "LucideNewspaper"
        case .paperclip: "LucidePaperclip"
        case .pencil: "LucidePencil"
        case .play: "LucidePlay"
        case .plus: "LucidePlus"
        case .rotateCcw: "LucideRotateCcw"
        case .searchX: "LucideSearchX"
        case .send: "LucideSend"
        case .share: "LucideShare"
        case .shieldCheck: "LucideShieldCheck"
        case .slidersHorizontal: "LucideSlidersHorizontal"
        case .smartphoneNfc: "LucideSmartphoneNfc"
        case .sparkle: "LucideSparkle"
        case .sparkles: "LucideSparkles"
        case .squarePen: "LucideSquarePen"
        case .textSearch: "LucideTextSearch"
        case .thumbsDown: "LucideThumbsDown"
        case .trash2: "LucideTrash2"
        case .trendingUp: "LucideTrendingUp"
        case .triangleAlert: "LucideTriangleAlert"
        case .userCog: "LucideUserCog"
        case .users: "LucideUsers"
        case .usersRound: "LucideUsersRound"
        case .wandSparkles: "LucideWandSparkles"
        case .waypoints: "LucideWaypoints"
        case .wifiOff: "LucideWifiOff"
        case .wrench: "LucideWrench"
        case .zap: "LucideZap"
        case .lightbulb: "LucideLightbulb"
        case .arrowUp: "LucideArrowUp"
        case .circleDashed: "LucideCircleDashed"
        case .circleX: "LucideCircleX"
        case .eyeOff: "LucideEyeOff"
        case .filePlus: "LucideFilePlus"
        case .square: "LucideSquare"
        case .thumbsUp: "LucideThumbsUp"
        case .volume2: "LucideVolume2"
        case .x: "LucideX"
        case .bug: "LucideBug"
        }
    }
}

/// Ein Icon dort, wo früher ein SF-Symbol stand.
///
/// Zwei Unterschiede zu `Image(systemName:)`, die jede Umstellung betreffen:
/// Die Größe steht in Punkt statt als Schriftgrad (ein Vektor-Asset hört nicht
/// auf `.font`), und die Farbe erbt das Icon von außen — `.foregroundStyle`
/// an der Aufrufstelle wirkt weiter wie bisher.
public extension RatsGlyph {
    /// Dasselbe Icon für UIKit-Stellen — auf der Karte trägt eine
    /// `MKMarkerAnnotationView` ihr Glyph als `UIImage`, nicht als View.
    /// `alwaysTemplate` sorgt dafür, dass die Marker-Tönung durchschlägt.
    static func uiImage(_ glyph: RatsGlyph) -> UIImage? {
        UIImage(named: glyph.lucideAssetName)?.withRenderingMode(.alwaysTemplate)
    }
}

public struct RatsIcon: View {
    public let glyph: RatsGlyph
    /// Kantenlänge in Punkt. 16 entspricht ungefähr dem, was ein SF-Symbol bei
    /// Schriftgrad 16 belegte.
    public var size: CGFloat = 16

    public init(_ glyph: RatsGlyph, size: CGFloat = 16) {
        self.glyph = glyph
        self.size = size
    }

    public var body: some View {
        if let system = glyph.systemSymbolName {
            Image(systemName: system)
                .font(.system(size: size, weight: .semibold))
        } else {
            Image(glyph.lucideAssetName)
                .resizable()
                .renderingMode(.template)
                .scaledToFit()
                .frame(width: size, height: size)
        }
    }
}

/// The exact Lucide 0.451.0 vectors used by the web app. Keeping the assets
/// local makes rendering deterministic and gives web and native one visual
/// language without introducing a runtime dependency.
/// `Label` mit einem Icon aus dem Pack statt aus SF Symbols.
///
/// SwiftUIs `Label(_:systemImage:)` nimmt ausschließlich SF-Symbol-Namen —
/// diese Bauform nimmt stattdessen einen `RatsGlyph` und behält sonst alles,
/// was ein Label ausmacht (Ausrichtung, Menü-Darstellung, Dynamic Type).
public struct RatsLabel: View {
    private let title: String
    private let glyph: RatsGlyph
    private let size: CGFloat

    public init(_ title: String, _ glyph: RatsGlyph, size: CGFloat = 15) {
        self.title = title
        self.glyph = glyph
        self.size = size
    }

    public var body: some View {
        Label { Text(title) } icon: { RatsIcon(glyph, size: size) }
    }
}

public struct RatsGlyphView: View {
    public let glyph: RatsGlyph
    public var color: Color

    public init(glyph: RatsGlyph, color: Color = RatsColor.primary) {
        self.glyph = glyph
        self.color = color
    }

    public var body: some View {
        Image(glyph.lucideAssetName)
            .resizable()
            .renderingMode(.template)
            .scaledToFit()
            .foregroundStyle(color)
            .accessibilityHidden(true)
    }
}
