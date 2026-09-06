import SwiftUI

/// Die Bewegungs-Grammatik der Designsprache (`DESIGNSPRACHE.md`, § 7),
/// eins zu eins aus `app/globals.css` übernommen: vier Dauern, keine fünfte,
/// und zu jeder Dauer die Kurve, die dazugehört. Wer eine Bewegung baut,
/// nimmt einen dieser Takte — eine frei gewählte Zahl macht die App
/// uneinheitlich, ohne dass jemand sagen könnte, warum.
public enum RatsMotion {
    /// 120 ms — der Zustand unter dem Finger (Tipp-Feedback).
    public static let tap: Animation = .easeOut(duration: 0.12)

    /// 180 ms — der Normalfall: Ein Zustand wechselt, etwas blendet um.
    public static let flow: Animation = .timingCurve(0.23, 1, 0.32, 1, duration: 0.18)

    /// 260 ms — eine sichtbare Strecke: Die Markierung fährt vom alten Ziel
    /// zum neuen.
    public static let travel: Animation = .timingCurve(0.77, 0, 0.175, 1, duration: 0.26)

    /// 340 ms — etwas betritt die Seite.
    public static let stage: Animation = .timingCurve(0.23, 1, 0.32, 1, duration: 0.34)

    /// 200 ms — der Abgang ist kürzer als der Auftritt: Wer schließt, hat
    /// sich entschieden und wartet nur noch.
    public static let exit: Animation = .easeIn(duration: 0.20)

    /// Überschwinger — nur für Kleinteile bis etwa 40 pt; größer wirkt
    /// Überschwingen wie Wackelpudding.
    public static let backOut: Animation = .timingCurve(0.34, 1.56, 0.64, 1, duration: 0.26)

    /// Versatz zwischen zwei gestaffelt einlaufenden Zeilen.
    public static let staggerStep: Double = 0.045

    /// Gestaffelt heißt gedeckelt: Der Versatz wächst bis zur sechsten
    /// Zeile (Index 5, 0–225 ms) und bleibt dann stehen — sonst käme die
    /// 40. Zeile einer Trefferliste 1,8 s nach der ersten. Derselbe Deckel
    /// wie `components/staffel.tsx` im Web.
    public static let staggerCap = 5

    /// Dauer des Zählers auf einer Anzeigetafel (600 ms, ease-out³).
    public static let countDuration: Double = 0.6
}

/// Läuft gestaffelt ein: leicht angehoben und unsichtbar, dann auf die
/// Endlage. Der Endzustand ist `offset 0` / `opacity 1` — kein gehaltenes
/// Transform, das nachher als Bezugsrahmen stört. Bei reduzierter Bewegung
/// steht sofort der Endwert.
public struct RatsStaggeredEntrance: ViewModifier {
    private let index: Int
    private let enabled: Bool
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var shown = false

    public init(index: Int, enabled: Bool) {
        self.index = index
        self.enabled = enabled
    }

    private var settled: Bool { shown || reduceMotion || !enabled }

    public func body(content: Content) -> some View {
        content
            .opacity(settled ? 1 : 0)
            .offset(y: settled ? 0 : 8)
            .onAppear {
                guard !shown else { return }
                let delay = Double(min(max(index, 0), RatsMotion.staggerCap)) * RatsMotion.staggerStep
                withAnimation(RatsMotion.stage.delay(delay)) { shown = true }
            }
    }
}

public extension View {
    /// Zeile `index` einer Liste, die gerade erscheint. `enabled: false`
    /// lässt die Zeile ohne Bewegung stehen — für Zeilen jenseits des ersten
    /// Bildschirms, die beim Scrollen nachkommen und dort nicht nachhinken
    /// sollen.
    func ratsStaggered(_ index: Int, enabled: Bool = true) -> some View {
        modifier(RatsStaggeredEntrance(index: index, enabled: enabled))
    }
}

/// Eine Zahl, die beim ersten Sichtkontakt zählt: 600 ms, ease-out³,
/// einmal je Erscheinen. Bei reduzierter Bewegung steht sofort der Endwert.
/// `format` macht aus dem Zwischenwert den Text — Rundung und Einheit
/// gehören dorthin, damit „9,5 Mio. €" nicht als „9,4837 Mio. €" zählt.
public struct RatsCountingNumber: View {
    private let value: Double
    private let format: (Double) -> String
    @State private var shown: Double = 0
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    public init(_ value: Double, format: @escaping (Double) -> String) {
        self.value = value
        self.format = format
    }

    public var body: some View {
        Text(format(value))
            .hidden()
            .overlay(alignment: .leading) {
                Text(format(reduceMotion ? value : shown))
                    .lineLimit(1)
                    .fixedSize(horizontal: true, vertical: false)
            }
            .monospacedDigit()
            .accessibilityLabel(format(value))
            .task(id: value) {
                guard !reduceMotion else { shown = value; return }
                let start = Date.now
                let from = shown
                while !Task.isCancelled {
                    let t = min(1, Date.now.timeIntervalSince(start) / RatsMotion.countDuration)
                    let eased = 1 - pow(1 - t, 3)
                    shown = from + (value - from) * eased
                    if t >= 1 { break }
                    try? await Task.sleep(for: .milliseconds(16))
                }
                shown = value
            }
    }
}

/// Die gleitende Aktiv-Markierung: Ein Segment-Schalter, dessen gefüllte
/// Fläche beim Wechsel vom alten zum neuen Ziel FÄHRT, statt umzuspringen.
/// Der erste Auftritt bewegt sich nicht — bewegt wird erst, wenn es einen
/// Vorgängerstand gibt.
public struct RatsSegmentedControl<Option: Hashable & Identifiable>: View {
    @Binding private var selection: Option
    private let options: [Option]
    private let label: (Option) -> String
    @Namespace private var marker
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    public init(selection: Binding<Option>, options: [Option], label: @escaping (Option) -> String) {
        _selection = selection
        self.options = options
        self.label = label
    }

    public var body: some View {
        HStack(spacing: 4) {
            ForEach(options) { option in
                let selected = option == selection
                Button {
                    withAnimation(reduceMotion ? nil : RatsMotion.travel) { selection = option }
                } label: {
                    Text(label(option))
                        .font(RatsFont.body(12.5, weight: .semibold))
                        .foregroundStyle(selected ? RatsColor.primaryText : RatsColor.bodyText)
                        .lineLimit(1)
                        .minimumScaleFactor(0.85)
                        .frame(maxWidth: .infinity, minHeight: 34)
                        .background {
                            if selected {
                                RoundedRectangle(cornerRadius: 10, style: .continuous)
                                    .fill(RatsColor.primary)
                                    .matchedGeometryEffect(id: "marker", in: marker)
                            }
                        }
                        .contentShape(Rectangle())
                }
                .buttonStyle(RatsPlainButtonStyle())
                .accessibilityAddTraits(selected ? .isSelected : [])
            }
        }
        .padding(4)
        .background(RatsColor.separator)
        .overlay(RoundedRectangle(cornerRadius: 13, style: .continuous).stroke(RatsColor.border))
        .clipShape(RoundedRectangle(cornerRadius: 13, style: .continuous))
        // Der Wechsel bestätigt sich in der Hand, wie beim System-Picker.
        .sensoryFeedback(.selection, trigger: selection)
    }
}
