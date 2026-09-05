import SwiftUI

/// Die Akzentfarbe eines Widgets sagt, wovon es spricht (Designdoc „iOS
/// Charakter", Runden 1b und 2): Hafenblau = Termin, Watt-Grün = Beschluss,
/// Boje-Orange = dein Thema, Tinte = Ort und Verlauf. Nach drei Sekunden
/// Blick weiß man, was worum geht — Farbe klassifiziert, statt zu
/// dekorieren.
public enum RatsWidgetAccent: Sendable {
    case harbor
    case marsh
    case buoy
    case ink
    /// Das Gebaute — Stadtplanung, Gebäudewirtschaft, Verkehr.
    case brick
    /// Die Menschen — Soziales, Jugend, Schule, Integration, Kultur, Sport.
    case plum

    public var color: Color {
        switch self {
        case .harbor: RatsColor.primary
        case .marsh: RatsColor.marsh
        case .buoy: RatsColor.signalInk
        case .ink: RatsColor.bodyText
        case .brick: RatsColor.brick
        case .plum: RatsColor.plum
        }
    }
}

/// Die Wellenkante unter der Kopfleiste — derselbe Pfad wie im Entwurf
/// (`viewBox 0 0 360 8`), auf die Breite gestreckt. Die beiden S-Bögen des
/// SVG sind hier ausgerechnet: Ihr erster Kontrollpunkt ist die Spiegelung
/// des vorigen zweiten am Endpunkt.
public struct RatsWaveEdge: Shape {
    public init() {}

    public func path(in rect: CGRect) -> Path {
        let sx = rect.width / 360
        let sy = rect.height / 8
        func p(_ x: CGFloat, _ y: CGFloat) -> CGPoint {
            CGPoint(x: rect.minX + x * sx, y: rect.minY + y * sy)
        }
        var path = Path()
        path.move(to: p(0, 5))
        path.addCurve(to: p(135, 4), control1: p(45, 0), control2: p(90, 0))
        path.addCurve(to: p(270, 4), control1: p(180, 8), control2: p(225, 9))
        path.addCurve(to: p(360, 3), control1: p(315, -1), control2: p(335, -1))
        return path
    }
}

/// Die Widget-Hülle „Tide": getönte Kopfleiste mit Wellenkante in der
/// Akzentfarbe, darunter der Körper. Die Tönung liegt ÜBER der Kartenfarbe
/// (hell 6 %, dunkel 10 %), die Welle zieht im Dunkeln an (30 → 42 %) —
/// dieselbe Konstruktion auf Weiß wie auf #101E2C, deshalb hält sie beide
/// Modi. Die Kopfleiste sagt auf einen Blick, wofür das Widget da ist: Icon
/// in der Akzentfarbe plus Name halbfett; die Mono-Schrift trägt nur noch
/// die Nebenangabe rechts.
///
/// `board` ist das eine hervorgehobene Widget je Seite: Es steht auf der
/// Anzeigetafel — hell eine getönte Fläche mit Rand, dunkel eine Stufe
/// heller als die Nachbarn. Besonders, aber nie dunkel im hellen Design
/// (Tims Regel, s. `RatsColor.board`). Die Kopfleiste zieht darauf etwas
/// an, damit sie auf dem Tafel-Grund noch als Leiste liest.
public struct RatsWidget<Content: View, Trailing: View>: View {
    private let title: String
    private let accent: RatsWidgetAccent
    private let glyph: RatsGlyph?
    private let note: String?
    private let board: Bool
    private let trailing: Trailing
    private let content: Content
    @Environment(\.colorScheme) private var colorScheme

    /// `trailing` steht rechts in der Kopfleiste — für ein Menü oder eine
    /// Pille, die zum Widget gehört (Themen-Karte: „2 neue" und „…").
    public init(
        _ title: String,
        accent: RatsWidgetAccent,
        glyph: RatsGlyph? = nil,
        note: String? = nil,
        board: Bool = false,
        @ViewBuilder trailing: () -> Trailing,
        @ViewBuilder content: () -> Content
    ) {
        self.title = title
        self.accent = accent
        self.glyph = glyph
        self.note = note
        self.board = board
        self.trailing = trailing()
        self.content = content()
    }

    public var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            header
            content
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(EdgeInsets(top: 12, leading: 13, bottom: 13, trailing: 13))
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(board ? RatsColor.board : RatsColor.card)
        .overlay(
            RoundedRectangle(cornerRadius: 16, style: .continuous)
                .stroke(board ? RatsColor.boardBorder : RatsColor.border, lineWidth: 1)
        )
        .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
        .shadow(color: .black.opacity(0.04), radius: 2, y: 1)
    }

    private var isDark: Bool { colorScheme == .dark }
    private var accentColor: Color { accent.color }
    private var headerTint: Double { board ? 0.12 : (isDark ? 0.10 : 0.06) }
    private var tileTint: Double { isDark ? 0.20 : 0.13 }
    private var waveOpacity: Double { board ? 0.42 : (isDark ? 0.42 : 0.30) }

    private var header: some View {
        HStack(spacing: 9) {
            if let glyph {
                RatsIcon(glyph, size: 14)
                    .foregroundStyle(accentColor)
                    .frame(width: 26, height: 26)
                    .background(accentColor.opacity(tileTint))
                    .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
                    .accessibilityHidden(true)
            }
            Text(title)
                .font(RatsFont.body(14, weight: .bold))
                .tracking(-0.14)
                .foregroundStyle(RatsColor.text)
                .lineLimit(1)
                .minimumScaleFactor(0.85)
            Spacer(minLength: 8)
            if let note {
                Text(note.uppercased())
                    .font(RatsFont.mono(9.5))
                    .tracking(0.57)
                    .foregroundStyle(RatsColor.muted)
                    .lineLimit(1)
            }
            trailing
        }
        .padding(EdgeInsets(top: 10, leading: 13, bottom: 13, trailing: 13))
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(accentColor.opacity(headerTint))
        .overlay(alignment: .bottom) {
            RatsWaveEdge()
                .stroke(accentColor.opacity(waveOpacity), lineWidth: 1)
                .frame(height: 8)
                .offset(y: 1)
                .accessibilityHidden(true)
        }
        .accessibilityElement(children: .contain)
    }
}

public extension RatsWidget where Trailing == EmptyView {
    init(
        _ title: String,
        accent: RatsWidgetAccent,
        glyph: RatsGlyph? = nil,
        note: String? = nil,
        board: Bool = false,
        @ViewBuilder content: () -> Content
    ) {
        self.init(title, accent: accent, glyph: glyph, note: note, board: board, trailing: { EmptyView() }, content: content)
    }
}

/// Die Kopfleiste einer Sitzungskarte: Zeichen des Gremiums, Uhrzeit in
/// Mono plus Gremium — gleiche Hülle wie die Start-Widgets, andere Füllung,
/// so ist die Sitzungsliste erkennbar dieselbe App. `board` macht die Karte
/// zum einen Anker der Liste (die Ratssitzung): Sie steht auf der
/// Anzeigetafel, der Akzent bleibt der des Gremiums.
public struct RatsTimedWidget<Content: View>: View {
    private let time: String?
    private let title: String
    private let subtitle: String?
    private let accent: RatsWidgetAccent
    private let glyph: RatsGlyph?
    private let board: Bool
    private let content: Content
    @Environment(\.colorScheme) private var colorScheme

    public init(
        time: String?,
        title: String,
        subtitle: String? = nil,
        accent: RatsWidgetAccent = .harbor,
        glyph: RatsGlyph? = nil,
        board: Bool = false,
        @ViewBuilder content: () -> Content
    ) {
        self.time = time
        self.title = title
        self.subtitle = subtitle
        self.accent = accent
        self.glyph = glyph
        self.board = board
        self.content = content()
    }

    private var isDark: Bool { colorScheme == .dark }
    private var headerTint: Double { board ? 0.12 : (isDark ? 0.10 : 0.06) }
    private var tileTint: Double { isDark ? 0.20 : 0.13 }
    private var waveOpacity: Double { board ? 0.42 : (isDark ? 0.42 : 0.30) }

    public var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack(alignment: .center, spacing: 10) {
                if let glyph {
                    RatsIcon(glyph, size: 15)
                        .foregroundStyle(accent.color)
                        .frame(width: 30, height: 30)
                        .background(accent.color.opacity(tileTint))
                        .clipShape(RoundedRectangle(cornerRadius: 9, style: .continuous))
                        .accessibilityHidden(true)
                }
                VStack(alignment: .leading, spacing: 2) {
                    HStack(alignment: .firstTextBaseline, spacing: 8) {
                        if let time {
                            Text(time)
                                .font(RatsFont.mono(11, weight: .semibold))
                                .foregroundStyle(accent.color)
                                .fixedSize()
                        }
                        Text(title)
                            .font(RatsFont.body(14.5, weight: .bold))
                            .foregroundStyle(RatsColor.text)
                            .multilineTextAlignment(.leading)
                    }
                    if let subtitle {
                        Text(subtitle)
                            .font(RatsFont.body(11.5))
                            .foregroundStyle(RatsColor.secondary)
                            .lineLimit(2)
                            .multilineTextAlignment(.leading)
                    }
                }
                Spacer(minLength: 0)
            }
            .padding(EdgeInsets(top: 10, leading: 13, bottom: 13, trailing: 13))
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(accent.color.opacity(headerTint))
            .overlay(alignment: .bottom) {
                RatsWaveEdge()
                    .stroke(accent.color.opacity(waveOpacity), lineWidth: 1)
                    .frame(height: 8)
                    .offset(y: 1)
                    .accessibilityHidden(true)
            }

            content
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(EdgeInsets(top: 12, leading: 13, bottom: 13, trailing: 13))
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(board ? RatsColor.board : RatsColor.card)
        .overlay(
            RoundedRectangle(cornerRadius: 16, style: .continuous)
                .stroke(board ? RatsColor.boardBorder : RatsColor.border, lineWidth: 1)
        )
        .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
        .shadow(color: .black.opacity(0.04), radius: 2, y: 1)
    }
}

/// Eine Tages-Überschrift in einer Terminliste: „HEUTE, 4. SEPTEMBER" in
/// Signal-Orange, alle anderen Tage in Mono-Grau, dahinter eine Linie.
public struct RatsDayDivider: View {
    private let label: String
    private let highlighted: Bool

    public init(_ label: String, highlighted: Bool = false) {
        self.label = label
        self.highlighted = highlighted
    }

    public var body: some View {
        HStack(spacing: 9) {
            Text(label.uppercased())
                .font(RatsFont.mono(9, weight: .semibold))
                .tracking(0.8)
                .foregroundStyle(highlighted ? RatsColor.signal : RatsColor.muted)
                .fixedSize()
            Rectangle().fill(RatsColor.border).frame(height: 1)
        }
        .accessibilityElement(children: .combine)
        .accessibilityAddTraits(.isHeader)
    }
}
