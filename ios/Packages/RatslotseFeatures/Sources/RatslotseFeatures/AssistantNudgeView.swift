import RatslotseAPI
import RatslotseDesign
import SwiftUI

/// Lotti klopft an: „Hast du eine Frage zu dem, was du siehst?"
///
/// **Tims Auftrag vom 21.09.2026**, und das Wort, an dem alles hängt, ist
/// *selten*. Die Grenzen stehen in `RatslotseAPI` (`AssistantNudge`), sind
/// dieselben wie im Web und dort wie hier ohne Oberfläche geprüft. Diese
/// Datei misst nur: Lesezeit, letzte Berührung, der wievielte Screen.
///
/// **Was sie nicht tut:** Sie öffnet das Blatt nicht. Sie ist ein Angebot mit
/// zwei Knöpfen; erst ein „Ja" öffnet. Kein Ton, keine Vibration, kein Zähler
/// am Knopf.

// MARK: - Was sich die App merkt

/// Der Stand des Anklopfens in den `UserDefaults` — vier Zahlen, keine Inhalte.
@MainActor
struct NudgeStore {
    private static let stateKey = "ratslotse.lotti.nudge"
    private static let usedKey = "ratslotse.lotti.usedOn"

    let defaults: UserDefaults

    init(defaults: UserDefaults = .standard) { self.defaults = defaults }

    var state: NudgeState {
        get {
            guard let daten = defaults.data(forKey: Self.stateKey),
                  let stand = try? JSONDecoder().decode(NudgeState.self, from: daten)
            else { return .empty }
            return stand
        }
        nonmutating set {
            guard let daten = try? JSONEncoder().encode(newValue) else { return }
            defaults.set(daten, forKey: Self.stateKey)
        }
    }

    /// Wurde Lotti heute schon benutzt? Dann klopft sie heute nicht mehr an.
    var usedToday: Bool {
        defaults.string(forKey: Self.usedKey) == Self.heute
    }

    func markUsed() {
        defaults.set(Self.heute, forKey: Self.usedKey)
    }

    private static var heute: String {
        let f = DateFormatter()
        f.dateFormat = "yyyy-MM-dd"
        return f.string(from: .now)
    }
}

// MARK: - Die Uhr je Screen

/// Misst, wie lange jemand auf DIESEM Screen liest und ob er noch da ist.
///
/// **Nur sichtbare Zeit zählt.** Eine App im Hintergrund liest nicht; ohne
/// diese Unterscheidung klopfte Lotti an, sobald man das Telefon wieder
/// aufnimmt — also im schlechtesten Moment.
@MainActor
@Observable
final class NudgeClock {
    private(set) var readingTime: TimeInterval = 0
    private(set) var lastInteraction: Date = .now
    private(set) var screensThisSession = 0
    /// War Lottis Blatt in dieser Sitzung schon offen?
    var sheetWasOpen = false

    private var lastTick: Date = .now

    /// Ein neuer Screen: Die Uhr beginnt von vorn, der Zähler steigt.
    func enteredScreen() {
        readingTime = 0
        lastTick = .now
        lastInteraction = .now
        screensThisSession += 1
    }

    func touched() { lastInteraction = .now }

    /// Ein Takt der Uhr; `visible` ist `scenePhase == .active`.
    func tick(visible: Bool) {
        let jetzt = Date.now
        if visible { readingTime += jetzt.timeIntervalSince(lastTick) }
        lastTick = jetzt
    }

    var sinceInteraction: TimeInterval { Date.now.timeIntervalSince(lastInteraction) }
}

// MARK: - Die Blase

struct LottiNudgeBubble: View {
    let accept: () -> Void
    let dismiss: () -> Void
    var bottomClearance: CGFloat = 0

    var body: some View {
        VStack(alignment: .leading, spacing: RatsSpacing.sm) {
            HStack(alignment: .top, spacing: RatsSpacing.sm) {
                LottiSpriteView(animation: .raiseHand, animated: false)
                    .frame(width: 32, height: 32)
                    .accessibilityHidden(true)
                Text("Hast du eine Frage zu dem, was du siehst?")
                    .font(.footnote)
                    .foregroundStyle(RatsColor.text)
                    .fixedSize(horizontal: false, vertical: true)
                Button(action: dismiss) {
                    RatsIcon(.x, size: 13).foregroundStyle(RatsColor.muted)
                }
                .buttonStyle(.plain)
                .accessibilityLabel("Nicht jetzt")
            }
            // Der Knopf umschließt seine Beschriftung, statt die Blase
            // auszufüllen: Ein randbreiter Knopf in einer Sprechblase liest
            // sich wie eine Aufforderung, nicht wie ein Angebot.
            Button("Ja, frag Lotti", action: accept)
                .buttonStyle(PrimaryButtonStyle())
                .controlSize(.small)
                .fixedSize()
        }
        .padding(RatsSpacing.md)
        .frame(maxWidth: 260, alignment: .leading)
        .background(RatsColor.card, in: RoundedRectangle(cornerRadius: RatsRadius.panel))
        .overlay(RoundedRectangle(cornerRadius: RatsRadius.panel).stroke(RatsColor.border))
        .shadow(color: .black.opacity(0.16), radius: 12, y: 5)
        .padding(.trailing, RatsSpacing.lg)
        // Über dem Knopf, der seinerseits über der Tab-Leiste sitzt.
        .padding(.bottom, bottomClearance + 64)
        // `isStatusElement` meldet sie, ohne den Fokus zu nehmen: Wer gerade
        // tippt, soll nicht mitten im Wort woanders landen.
        .accessibilityElement(children: .contain)
        .accessibilityAddTraits(.isStaticText)
        .transition(.opacity.combined(with: .move(edge: .bottom)))
    }
}
