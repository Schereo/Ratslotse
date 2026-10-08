import Foundation

/// Welche Adressen die App aus fremdem Inhalt heraus öffnen darf.
///
/// Antworten und Belege kommen nicht nur aus dem eigenen Gespräch: Eine
/// geteilte Antwort (`/g?t=…`, `/fragen?share=…`) hat ein anderes Konto
/// angelegt, und ihr Text wird als Markdown gerendert. Bis 10/2026 öffnete die
/// App jeden Link darin über das System — `tel:`, `sms:`, fremde App-Schemata
/// oder eine Phishing-Seite, die wie eine Quelle aussah (Sicherheitsprüfung
/// 10/2026, F4).
enum ExterneLinks {
    /// Links IM ANTWORTTEXT: nur https auf die Stadt oder auf Ratslotse. Eine
    /// Antwort trägt ihre Quellen strukturiert, freie Links darin sind nie echt.
    static func imAntworttextErlaubt(_ url: URL) -> Bool {
        guard istSauberesHttps(url), let host = url.host?.lowercased() else { return false }
        return host == "ratslotse.de" || host == "www.ratslotse.de"
            || host == "oldenburg.de" || host.hasSuffix(".oldenburg.de")
    }

    /// Links an Belegen (Anlagen, Presse, Protokolle): https ohne Zugangsdaten.
    static func istSauberesHttps(_ url: URL) -> Bool {
        url.scheme?.lowercased() == "https" && url.user == nil && url.password == nil
            && url.host?.isEmpty == false
    }

    /// Eine Beleg-Adresse aus den Daten — nur, wenn sie sauberes https ist.
    static func beleg(_ raw: String?) -> URL? {
        guard let raw, !raw.contains("\\"), let url = URL(string: raw),
              istSauberesHttps(url) else { return nil }
        return url
    }

    /// Links aus einem gerenderten Markdown-Text entfernen, die nicht erlaubt sind.
    static func bereinigt(_ text: AttributedString) -> AttributedString {
        var text = text
        for run in text.runs {
            if let link = run.link, link.scheme != "ratslotse", !imAntworttextErlaubt(link) {
                text[run.range].link = nil
            }
        }
        return text
    }
}
