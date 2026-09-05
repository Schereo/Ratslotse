import Foundation
import RatslotseAPI

/// Wie die App den Live-Stand aus der Übertragung beschriftet — dieselben
/// Regeln wie `lib/live.ts` im Web (`liveTopLabel`, `partyShort`,
/// `liveSpeakerText`, `liveAgoText`, `liveStateFresh`, `liveItemKeys`):
/// Der Stand ist auf beiden Geräten dieselbe Sache und soll gleich heißen.
enum LiveStateText {
    /// Nach so vielen Minuten ohne neues Stück gilt der Mitschnitt als
    /// abgebrochen — dann lieber nichts behaupten.
    static let staleMinutes = 20

    /// „TOP 9.3" — oder „TOP 9.4–9.8", wenn ein Block von Formalien in
    /// einem Fenster durchlief (der Stand trägt dann nur den letzten).
    static func topLabel(_ state: LiveState) -> String? {
        guard let number = state.itemNumber else { return nil }
        if let start = state.blockStart, start != number { return "TOP \(start)–\(number)" }
        return "TOP \(number)"
    }

    /// Fraktionsnamen sind auf einer Karte zu lang — „Bündnis 90/Die Grünen"
    /// brach die Sprecherzeile um.
    static func partyShort(_ party: String?) -> String? {
        guard let party, !party.trimmingCharacters(in: .whitespaces).isEmpty else { return nil }
        let p = party.trimmingCharacters(in: .whitespaces)
        let lower = p.lowercased()
        if lower.hasPrefix("bündnis 90") || lower.hasSuffix("grünen") || lower.hasSuffix("grüne") { return "Grüne" }
        if lower.hasPrefix("die linke") { return "Linke" }
        return p
    }

    /// „Susanne Drügemöller (Grüne) spricht" — nil, wenn niemand bekannt ist.
    static func speakerText(_ state: LiveState) -> String? {
        guard let speaker = state.speaker, !speaker.isEmpty else { return nil }
        if let party = partyShort(state.party) { return "\(speaker) (\(party)) spricht" }
        return "\(speaker) spricht"
    }

    static func asOfDate(_ state: LiveState) -> Date? {
        let withFraction = ISO8601DateFormatter()
        withFraction.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return withFraction.date(from: state.asOf) ?? ISO8601DateFormatter().date(from: state.asOf)
    }

    /// „vor 2 Min." aus dem Audio-Stand und der eigenen Uhr; unter einer
    /// Minute „gerade eben", nie negativ.
    static func agoText(_ state: LiveState, now: Date) -> String {
        guard let then = asOfDate(state) else { return "" }
        let minutes = max(0, Int(now.timeIntervalSince(then) / 60))
        return minutes < 1 ? "gerade eben" : "vor \(minutes) Min."
    }

    /// Noch brauchbar? Nicht beendet und nicht älter als `staleMinutes`.
    static func isFresh(_ state: LiveState, now: Date) -> Bool {
        guard !state.finished, let then = asOfDate(state) else { return false }
        return now.timeIntervalSince(then) <= Double(staleMinutes) * 60
    }

    /// „Ö 9.3" → „9.3"; „DZT 1" bleibt (wie `videos.strip_prefix` im Backend).
    static func itemKey(_ itemNumber: String) -> String {
        var s = itemNumber.trimmingCharacters(in: .whitespaces)
        for prefix in ["Ö ", "ö ", "N ", "n "] where s.hasPrefix(prefix) {
            s = String(s.dropFirst(prefix.count))
            break
        }
        return s.trimmingCharacters(in: .whitespaces)
    }

    /// Welche Zeilen der Tagesordnung „laufen gerade": der Punkt selbst oder
    /// bei einem Block alle von `blockStart` bis `itemNumber` in der
    /// Reihenfolge der Tagesordnung. Schlüssel ohne Ö/N-Präfix.
    static func runningKeys(_ state: LiveState?, agendaKeys: [String]) -> Set<String> {
        guard let state, let number = state.itemNumber else { return [] }
        guard let end = agendaKeys.firstIndex(of: number) else { return [number] }
        var start = end
        if let block = state.blockStart, let index = agendaKeys.firstIndex(of: block), index <= end {
            start = index
        }
        return Set(agendaKeys[start...end])
    }
}
