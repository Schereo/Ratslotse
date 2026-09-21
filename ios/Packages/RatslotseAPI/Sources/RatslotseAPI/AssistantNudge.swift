import Foundation

/// Wann Lotti von selbst anklopfen darf — die Grenzen, und sonst nichts.
///
/// **Dieselben Zahlen wie im Web** (`web/frontend/lib/anstupser.ts`). Das Wort,
/// an dem alles hängt, ist *selten*: Eine Blase, die zu oft kommt, ist eine
/// Werbeeinblendung, und danach drückt sie niemand mehr.
///
/// **Warum in `RatslotseAPI` und nicht bei der Ansicht.** Das hier ist reine
/// Logik ohne SwiftUI und damit ohne Simulator prüfbar — genau wie ihr
/// Gegenstück im Web eine reine Funktion ist und nicht in der Komponente
/// steckt.
public enum NudgeLimits {
    public static let tag: TimeInterval = 24 * 60 * 60
    /// Erst nach so viel sichtbarer Lesezeit.
    public static let readingTime: TimeInterval = 45
    /// … und nur, wenn kurz vorher etwas passiert ist — sonst ist niemand da.
    public static let sinceInteraction: TimeInterval = 10
    /// Die ersten beiden Screens einer Sitzung bleiben in Ruhe.
    public static let firstScreens = 2
    /// Höchstens einmal am Tag.
    public static let perDay: TimeInterval = tag
    /// Höchstens dreimal in 30 Tagen.
    public static let per30Days = 3
    /// Nach zwei „×" zwei Monate Ruhe.
    public static let dismissalsUntilPause = 2
    public static let pauseAfterDismissal: TimeInterval = 60 * tag
    /// Nach einem „Ja" zwei Wochen Ruhe — die Person kennt Lotti jetzt.
    public static let pauseAfterAccept: TimeInterval = 14 * tag
}

/// Was sich die App über das Anklopfen merkt. Vier Zahlen, keine Inhalte.
public struct NudgeState: Codable, Sendable, Equatable {
    /// Wann zuletzt angeklopft wurde (Sekunden seit 1970).
    public var last: TimeInterval
    /// Die Zeitpunkte der letzten 30 Tage.
    public var within30Days: [TimeInterval]
    /// Wie oft hintereinander weggeklickt.
    public var dismissals: Int
    /// Wann zuletzt angenommen.
    public var accepted: TimeInterval

    public static let empty = NudgeState(last: 0, within30Days: [], dismissals: 0, accepted: 0)

    public init(last: TimeInterval = 0, within30Days: [TimeInterval] = [],
                dismissals: Int = 0, accepted: TimeInterval = 0) {
        self.last = last
        self.within30Days = within30Days
        self.dismissals = dismissals
        self.accepted = accepted
    }
}

/// Was gerade auf dem Screen los ist.
public struct NudgeContext: Sendable {
    /// Darf auf DIESEM Screen angeklopft werden? (`PageKnowledge.nudge`)
    public var screenAllowed: Bool
    /// Sichtbare Lesezeit auf diesem Screen.
    public var readingTime: TimeInterval
    /// Wie lange seit der letzten Berührung.
    public var sinceInteraction: TimeInterval
    /// Der wievielte Screen dieser Sitzung.
    public var screensThisSession: Int
    /// War Lottis Blatt in dieser Sitzung schon offen?
    public var sheetWasOpen: Bool
    /// Wurde Lotti heute schon benutzt?
    public var usedToday: Bool
    /// Tippt die Person gerade, oder ist ein Blatt offen?
    public var busy: Bool

    public init(screenAllowed: Bool, readingTime: TimeInterval, sinceInteraction: TimeInterval,
                screensThisSession: Int, sheetWasOpen: Bool, usedToday: Bool, busy: Bool) {
        self.screenAllowed = screenAllowed
        self.readingTime = readingTime
        self.sinceInteraction = sinceInteraction
        self.screensThisSession = screensThisSession
        self.sheetWasOpen = sheetWasOpen
        self.usedToday = usedToday
        self.busy = busy
    }
}

public enum AssistantNudge {
    /// Darf Lotti jetzt anklopfen? **Alle** Bedingungen müssen gelten.
    public static func mayAppear(_ state: NudgeState, _ context: NudgeContext,
                                 now: TimeInterval) -> Bool {
        guard context.screenAllowed, !context.busy else { return false }
        guard !context.sheetWasOpen, !context.usedToday else { return false }
        guard context.screensThisSession > NudgeLimits.firstScreens else { return false }
        guard context.readingTime >= NudgeLimits.readingTime else { return false }
        guard context.sinceInteraction <= NudgeLimits.sinceInteraction else { return false }
        guard now - state.last >= NudgeLimits.perDay else { return false }
        guard now - state.accepted >= NudgeLimits.pauseAfterAccept else { return false }
        if state.dismissals >= NudgeLimits.dismissalsUntilPause,
           now - state.last < NudgeLimits.pauseAfterDismissal { return false }
        return within30Days(state.within30Days, now: now).count < NudgeLimits.per30Days
    }

    /// Die Zeitpunkte der letzten 30 Tage — ältere fallen heraus.
    public static func within30Days(_ stamps: [TimeInterval], now: TimeInterval) -> [TimeInterval] {
        stamps.filter { now - $0 < 30 * NudgeLimits.tag }
    }

    public static func afterShowing(_ state: NudgeState, now: TimeInterval) -> NudgeState {
        var neu = state
        neu.last = now
        neu.within30Days = within30Days(state.within30Days, now: now) + [now]
        return neu
    }

    /// Nach einem „Ja" beginnt der Ablehnungs-Zähler von vorn.
    public static func afterAccept(_ state: NudgeState, now: TimeInterval) -> NudgeState {
        var neu = state
        neu.accepted = now
        neu.dismissals = 0
        return neu
    }

    public static func afterDismissal(_ state: NudgeState) -> NudgeState {
        var neu = state
        neu.dismissals += 1
        return neu
    }
}
