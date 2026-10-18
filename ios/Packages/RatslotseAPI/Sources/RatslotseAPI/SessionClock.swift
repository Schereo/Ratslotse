import Foundation

/// Wann eine Sitzung beginnt — als echter Zeitpunkt, nicht als Uhrzeit des
/// Telefons.
///
/// Das Ratsinfo nennt Tag und Uhrzeit in Oldenburger Ortszeit ohne Zone
/// („2026-10-08", „17:00:00"). Bis 10/2026 las die App das mit der Zeitzone
/// des **Geräts**: Wer in Lissabon den Kalendereintrag anlegte, bekam die
/// Sitzung eine Stunde zu früh, in New York sechs Stunden. Hier ist die Zone
/// fest Europe/Berlin — dieselbe, in der die Sitzung stattfindet; der
/// Kalender rechnet sie dann selbst in die Zone des Geräts um.
///
/// Ohne SwiftUI und EventKit, damit es in den Paket-Tests in Sekunden läuft.
public enum SessionClock {
    public static let zone = TimeZone(identifier: "Europe/Berlin")!

    /// Uhrzeit, wenn das Ratsinfo keine nennt.
    public static let fallbackTime = "17:00"

    private static let parser: DateFormatter = {
        let f = DateFormatter()
        f.calendar = Calendar(identifier: .gregorian)
        f.locale = Locale(identifier: "en_US_POSIX")
        f.timeZone = zone
        f.dateFormat = "yyyy-MM-dd HH:mm"
        return f
    }()

    /// `day` darf ein ISO-Datum oder ein Zeitstempel sein (es zählen die
    /// ersten zehn Zeichen), `time` „HH:mm" oder „HH:mm:ss". `nil`, wenn sich
    /// daraus kein Zeitpunkt lesen lässt.
    public static func start(day: String, time: String?) -> Date? {
        let uhr = time.map { String($0.trimmingCharacters(in: .whitespaces).prefix(5)) }
            .flatMap { $0.isEmpty ? nil : $0 } ?? fallbackTime
        return parser.date(from: "\(day.prefix(10)) \(uhr)")
    }
}
