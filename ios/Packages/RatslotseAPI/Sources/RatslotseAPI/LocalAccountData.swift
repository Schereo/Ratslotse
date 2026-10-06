import Foundation

/// Was die App außer dem Token noch über ein Konto auf dem Gerät ablegt — und
/// beim Abmelden (und damit auch beim Löschen des Kontos) wieder vergisst.
///
/// Bis 10/2026 räumte `AppModel.logout()` nur den zwischengespeicherten
/// Nutzer weg. Liegen blieben die zuletzt angesehenen Beschlüsse, die
/// gewählten Karten-Ebenen und Lottis Anstupser-Zähler — wer sich danach mit
/// einem anderen Konto anmeldete oder das Telefon weitergab, sah den Verlauf
/// der Vorgängerin. Die Schlüssel stehen hier an EINER Stelle; die Ansichten
/// lesen sie von hier, damit eine neue Ablage nicht am Abmelden vorbeiläuft.
///
/// **Nicht** hier: was zum Gerät gehört statt zum Konto — Erscheinungsbild,
/// „Einrichtung schon gesehen", die Push-Schlummerfrist.
public enum LocalAccountData {
    /// Zuletzt angesehene Beschlüsse (`RecentDecisionStore`).
    public static let recentDecisionsKey = "ratslotse.recent-decisions"
    /// Gewählte Ebenen der Stadtkarte (`CityMapView`, `@AppStorage`).
    public static let mapLayersKey = "karte.ebenen"
    /// Lottis Anstupser: Stand und „schon benutzt auf" (`NudgeStore`).
    public static let nudgeStateKey = "ratslotse.lotti.nudge"
    public static let nudgeUsedKey = "ratslotse.lotti.usedOn"
    /// Das offene Ratsgespräch je Konto: Präfix + Konto-Id.
    public static let activeConversationPrefix = "ratslotse.qa.active-conversation."

    public static let keys = [recentDecisionsKey, mapLayersKey, nudgeStateKey, nudgeUsedKey]

    /// Alles Kontobezogene löschen — auch das offene Gespräch JEDES Kontos,
    /// das hier einmal angemeldet war, nicht nur des letzten.
    public static func clear(_ defaults: UserDefaults) {
        for key in keys { defaults.removeObject(forKey: key) }
        for key in defaults.dictionaryRepresentation().keys where key.hasPrefix(activeConversationPrefix) {
            defaults.removeObject(forKey: key)
        }
    }
}
