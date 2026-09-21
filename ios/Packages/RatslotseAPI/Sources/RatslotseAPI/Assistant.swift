import Foundation

/// Lotti als Assistentin — was die App ihr über den Bildschirm sagt.
///
/// **Warum hier und nicht in `Models.swift`.** Das Gegenstück im Backend ist
/// ein einziger Endpunkt (`POST /api/council/explain`) mit einem eigenen
/// Vertrag (`SSE_ERKLAERUNG`); die Regeln, was mitgehen darf, stehen in
/// `council/assistant.py` und `kern/knowledge.py`. Beisammen ist das
/// nachlesbar, verstreut zwischen zweitausend Zeilen Modellen nicht.
///
/// **Was NICHT mitgeht:** kein Element-Text (die App hat keine
/// `data-erklaer`-Anker und erntet nichts aus der Ansicht), keine Markierung
/// (Textauswahl in SwiftUI-Listen gibt es nicht). Beides ist in v1 bewusst
/// leer — siehe PR 6 im Plan.

/// Die Kennungen aus der Adresse — nie Inhalte.
public struct ExplainRefs: Codable, Sendable, Equatable {
    public var decisionID: Int?
    public var ksinr: Int?
    public var slug: String?
    public var placeID: String?
    public var year: Int?
    public var area: String?

    enum CodingKeys: String, CodingKey {
        case decisionID = "decision_id"
        case ksinr, slug, year, area
        case placeID = "place_id"
    }

    public init(decisionID: Int? = nil, ksinr: Int? = nil, slug: String? = nil,
                placeID: String? = nil, year: Int? = nil, area: String? = nil) {
        self.decisionID = decisionID
        self.ksinr = ksinr
        self.slug = slug
        self.placeID = placeID
        self.year = year
        self.area = area
    }

    /// Nur die gesetzten Felder gehen über die Leitung: Das Backend prüft
    /// jeden Wert (`ge=1`, Längen), und ein ausdrückliches `null` wäre kein
    /// kürzerer Weg, sondern nur mehr Papier.
    public func encode(to encoder: Encoder) throws {
        var values = encoder.container(keyedBy: CodingKeys.self)
        try values.encodeIfPresent(decisionID, forKey: .decisionID)
        try values.encodeIfPresent(ksinr, forKey: .ksinr)
        try values.encodeIfPresent(slug, forKey: .slug)
        try values.encodeIfPresent(placeID, forKey: .placeID)
        try values.encodeIfPresent(year, forKey: .year)
        try values.encodeIfPresent(area, forKey: .area)
    }

    public var isEmpty: Bool {
        decisionID == nil && ksinr == nil && slug == nil
            && placeID == nil && year == nil && area == nil
    }
}

/// Der Auftrag an `POST /api/council/explain`.
public struct ExplainRequest: Codable, Sendable {
    public let route: String
    public let pageTitle: String
    public let heading: String
    public let question: String
    public let refs: ExplainRefs
    public let history: [AskRound]
    public let conversationID: Int?

    enum CodingKeys: String, CodingKey {
        case route, heading, question, refs, history
        case pageTitle = "page_title"
        case conversationID = "conversation_id"
    }

    public init(route: String, pageTitle: String = "", heading: String = "",
                question: String = "", refs: ExplainRefs = ExplainRefs(),
                history: [AskRound] = [], conversationID: Int? = nil) {
        self.route = route
        self.pageTitle = pageTitle
        self.heading = heading
        self.question = question
        self.refs = refs
        self.history = history
        self.conversationID = conversationID
    }

    public init(from decoder: Decoder) throws {
        let values = try decoder.container(keyedBy: CodingKeys.self)
        route = try values.decode(String.self, forKey: .route)
        pageTitle = try values.decodeIfPresent(String.self, forKey: .pageTitle) ?? ""
        heading = try values.decodeIfPresent(String.self, forKey: .heading) ?? ""
        question = try values.decodeIfPresent(String.self, forKey: .question) ?? ""
        refs = try values.decodeIfPresent(ExplainRefs.self, forKey: .refs) ?? ExplainRefs()
        history = try values.decodeIfPresent([AskRound].self, forKey: .history) ?? []
        conversationID = try values.decodeIfPresent(Int.self, forKey: .conversationID)
    }

    public func encode(to encoder: Encoder) throws {
        var values = encoder.container(keyedBy: CodingKeys.self)
        try values.encode(route, forKey: .route)
        try values.encode(pageTitle, forKey: .pageTitle)
        try values.encode(heading, forKey: .heading)
        try values.encode(question, forKey: .question)
        try values.encode(refs, forKey: .refs)
        try values.encode(history, forKey: .history)
        // Wie bei der Frage: `null` heißt „neues Gespräch", ein fehlendes
        // Feld hieße „dieser Client speichert gar nicht".
        try values.encode(conversationID, forKey: .conversationID)
    }
}

/// Der Schluss-Rahmen des Erklär-Stroms (`type = "done"`).
///
/// Handgeschrieben gegen `SSE_ERKLAERUNG`; `scripts/ios_vertrag.py` kommt an
/// einen SSE-Strom nicht heran, deshalb steht die Probe in den Tests des
/// Pakets (`AssistantTests`).
public struct ExplainDone: Codable, Sendable, Equatable {
    /// `deterministic` für die Wege ohne Modell, sonst `explain`.
    public let mode: String
    /// `ratsfrage`, wenn die Frage ins Beschluss-Archiv gehört — sonst nil.
    public let next: String?
    public let glossary: [String]
    public let conversationID: Int?

    enum CodingKeys: String, CodingKey {
        case mode, next, glossary
        case conversationID = "conversation_id"
    }

    public init(mode: String, next: String? = nil, glossary: [String] = [],
                conversationID: Int? = nil) {
        self.mode = mode
        self.next = next
        self.glossary = glossary
        self.conversationID = conversationID
    }

    public init(from decoder: Decoder) throws {
        let values = try decoder.container(keyedBy: CodingKeys.self)
        // Jedes Feld gehärtet: Ein Schluss-Rahmen, der am fehlenden `mode`
        // scheitert, nähme der Antwort ihr Ende — der Text stünde da, und das
        // Fenster drehte weiter an der Tipp-Anzeige.
        mode = try values.decodeIfPresent(String.self, forKey: .mode) ?? "explain"
        next = try values.decodeIfPresent(String.self, forKey: .next)
        glossary = try values.decodeIfPresent([String].self, forKey: .glossary) ?? []
        conversationID = try values.decodeIfPresent(Int.self, forKey: .conversationID)
    }

    /// Gehört die Frage ins Ratsarchiv? Dann bietet das Fenster den Weg an.
    public var leadsToCouncilQuestion: Bool { next == "ratsfrage" }
}

// MARK: - Der Bildschirm als Web-Route

/// Was die App gerade zeigt, in der Sprache des Backends.
///
/// **Keine zweite Tabelle.** Welche Web-Adresse zu einem Screen gehört, weiß
/// `AppRouter.universalLink(for:)` bereits — dieselbe Abbildung, die das
/// Teilen benutzt. Hier wird sie nur zerlegt: Pfad (plus `tab`, das
/// `kern/knowledge.py` als Teil der Route führt) und die Kennungen. Eine
/// eigene Liste liefe binnen eines Releases auseinander, und zwar lautlos.
public struct ExplainScreen: Sendable, Equatable {
    public let route: String
    public let refs: ExplainRefs
    public let heading: String

    public init(route: String, refs: ExplainRefs = ExplainRefs(), heading: String = "") {
        self.route = route
        self.refs = refs
        self.heading = heading
    }

    /// Der Bildschirm zu einer App-Route — nil, wenn es zu ihr keine
    /// erklärbare Seite gibt (Konto, Admin, eine fremde Web-Adresse).
    public static func from(_ route: AppRoute, heading: String = "",
                            router: AppRouter = AppRouter()) -> ExplainScreen? {
        switch route {
        // Dieselbe Sperre wie im Web (`kern/knowledge.OHNE_ERKLAERUNG`):
        // Dort stehen eigene Kontodaten, die nicht in einen Prompt gehören.
        case .tab(.account), .admin, .web:
            return nil
        default:
            break
        }
        guard let url = router.universalLink(for: route),
              let parts = URLComponents(url: url, resolvingAgainstBaseURL: false)
        else { return nil }

        func query(_ name: String) -> String? {
            parts.queryItems?.first(where: { $0.name == name })?.value
        }

        var pfad = parts.path
        // `/council?tab=…` sind im Backend eigene Seiten mit eigenem Wissen —
        // die Liste der Beschlüsse erklärt etwas anderes als die Auswertung.
        if pfad == "/council", let tab = query("tab") { pfad = "/council?tab=\(tab)" }

        var refs = ExplainRefs()
        refs.decisionID = query("id").flatMap(Int.init)
        refs.ksinr = query("ksinr").flatMap(Int.init)
        refs.slug = query("slug")
        // Auf `/council/ort` ist `id` ein Kürzel, kein Zähler — dieselbe
        // Falle wie im Web (`refsAus` in `lib/assistentin.ts`).
        if pfad == "/council/ort" {
            refs.placeID = query("id")
            refs.decisionID = nil
        }
        // Wie die Kartenseite ihre Kennung nennt, steht in `universalLink` —
        // hier wird es nicht ein zweites Mal getippt. (Es ist auch das
        // einzige deutsche Wort in dieser Abbildung; `pruefe_alte_werte.py`
        // sähe es sonst ohne seinen Zusammenhang.)
        if pfad == "/karte" { refs.placeID = parts.queryItems?.first?.value }
        refs.area = query("area")
        return ExplainScreen(route: pfad, refs: refs, heading: heading)
    }
}
