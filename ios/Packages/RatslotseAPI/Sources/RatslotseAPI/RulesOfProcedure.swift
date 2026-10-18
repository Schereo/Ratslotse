import Foundation

/// Die Karte „Aus der Geschäftsordnung des Rates" — der Wortlaut, auf den eine
/// Verfahrensfrage antwortet („Wie lange darf ein Ratsmitglied reden?").
/// Gebaut von `council/rules_of_procedure.py::card`; sie reist im
/// `sources`-Rahmen von `/api/council/ask` und unter demselben Schlüssel im
/// gespeicherten Snapshot eines Gesprächs.
///
/// Gehärtet wie jedes Zusatzfeld: Ältere Server senden die Karte gar nicht,
/// eine Frage, die keine Regel meint, sendet `null`. Ein kaputter Paragraf
/// fällt einzeln heraus, statt die Karte mitzunehmen — und ohne einen
/// einzigen Paragrafen und ohne Verzeichnis gibt es keine Karte: Eine
/// Fassungszeile allein belegt nichts.
public struct RulesOfProcedureCard: Decodable, Sendable, Hashable {
    public struct Section: Decodable, Sendable, Hashable, Identifiable {
        public let number: String
        /// „§ 15"
        public let label: String
        /// „Redeordnung, Redezeit"
        public let title: String
        /// Der Abschnitt der Geschäftsordnung: „Rat", „Ratsausschüsse", …
        public let part: String?
        /// Die Seite im PDF der Stadt (`…pdf#page=7`).
        public let url: URL?
        /// Der Wortlaut, Absätze je auf einer Zeile („(1) …\n(2) …").
        public let text: String

        public var id: String { number }

        enum CodingKeys: String, CodingKey {
            case number, label, title, part, url, text
        }

        public init(from decoder: Decoder) throws {
            let c = try decoder.container(keyedBy: CodingKeys.self)
            label = try c.decode(String.self, forKey: .label)
            text = try c.decode(String.self, forKey: .text)
            number = try c.decodeIfPresent(String.self, forKey: .number) ?? label
            title = try c.decodeIfPresent(String.self, forKey: .title) ?? ""
            part = try c.decodeIfPresent(String.self, forKey: .part)
            url = (try c.decodeIfPresent(String.self, forKey: .url)).flatMap(URL.init(string:))
        }
    }

    /// Eine Zeile des Inhaltsverzeichnisses — nur bei der Frage nach dem Ganzen.
    public struct Entry: Decodable, Sendable, Hashable, Identifiable {
        public let label: String
        public let title: String
        public let url: URL?

        public var id: String { label }

        enum CodingKeys: String, CodingKey {
            case label, title, url
        }

        public init(from decoder: Decoder) throws {
            let c = try decoder.container(keyedBy: CodingKeys.self)
            label = try c.decode(String.self, forKey: .label)
            title = try c.decodeIfPresent(String.self, forKey: .title) ?? ""
            url = (try c.decodeIfPresent(String.self, forKey: .url)).flatMap(URL.init(string:))
        }
    }

    public let title: String
    public let fullTitle: String?
    /// Fertiger Text vom Server: Fassung, Beschluss, Wahlperiode — und, wenn
    /// sie nicht mehr gilt, warum.
    public let version: String
    /// `current`, `term_ended` oder `superseded`. Bewusst kein Enum: Ein
    /// Zustand, den die App noch nicht kennt, heißt ebenfalls „gilt nicht
    /// sicher" und färbt die Fassungszeile — statt den Decode zu kippen.
    public let state: String
    /// Das ganze PDF auf oldenburg.de.
    public let url: URL?
    public let sections: [Section]
    public let contents: [Entry]

    /// Gilt die gespeicherte Fassung noch? Sonst steht die Fassungszeile in
    /// Warnfarbe — dieselbe Regel wie im Web (`state !== "current"`).
    public var isCurrent: Bool { state == "current" }

    enum CodingKeys: String, CodingKey {
        case title
        case fullTitle = "full_title"
        case version, state, url, sections, contents
    }

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        title = try c.decodeIfPresent(String.self, forKey: .title) ?? "Geschäftsordnung des Rates"
        fullTitle = try c.decodeIfPresent(String.self, forKey: .fullTitle)
        version = try c.decodeIfPresent(String.self, forKey: .version) ?? ""
        state = try c.decodeIfPresent(String.self, forKey: .state) ?? "current"
        url = (try c.decodeIfPresent(String.self, forKey: .url)).flatMap(URL.init(string:))
        sections = (try c.decodeIfPresent([JSONValue].self, forKey: .sections) ?? [])
            .compactMap { try? $0.decoded(Section.self) }
        contents = (try c.decodeIfPresent([JSONValue].self, forKey: .contents) ?? [])
            .compactMap { try? $0.decoded(Entry.self) }
    }
}
