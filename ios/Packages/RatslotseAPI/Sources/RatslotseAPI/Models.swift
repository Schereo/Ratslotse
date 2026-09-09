import Foundation

public struct AppConfiguration: Codable, Sendable, Equatable {
    public let minBuild: Int
    public let notice: String?
    /// Eingeschaltete Feature-Schalter (`kern/features.py`). Im Vertrag
    /// voreingestellt leer — eine ältere App-Fassung kennt das Feld nicht und
    /// muss es auch nicht; deshalb hier mit Vorgabe statt Pflicht.
    public let features: [String]

    enum CodingKeys: String, CodingKey {
        case minBuild = "min_build"
        case notice = "note"
        case features
    }

    public init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        minBuild = try container.decode(Int.self, forKey: .minBuild)
        notice = try container.decodeIfPresent(String.self, forKey: .notice)
        features = try container.decodeIfPresent([String].self, forKey: .features) ?? []
    }

    public init(minBuild: Int, notice: String?, features: [String] = []) {
        self.minBuild = minBuild
        self.notice = notice
        self.features = features
    }
}

// MARK: - Mein Viertel

/// Ein Ortsbereich in der Übersicht von „Mein Viertel" — mit der Zahl seiner Vorhaben.
public struct DistrictProjectsOverviewEntry: Codable, Sendable, Hashable, Identifiable {
    public var id: String { placeID }
    public let placeID: String
    public let name: String
    public let count: Int
    public let lastDate: String?

    enum CodingKeys: String, CodingKey {
        case name, count
        case placeID = "place_id"
        case lastDate = "last_date"
    }
}

/// Ein Vorhaben, das stadtweit gerade heraussticht — für die Stadt-Stufe der Karte.
public struct DistrictHighlight: Codable, Sendable, Hashable, Identifiable {
    public let id: Int
    public let placeID: String
    public let placeName: String
    public let name: String
    public let what: String
    public let stage: String
    public let when: String?
    public let category: String
    public let lastDate: String?

    enum CodingKeys: String, CodingKey {
        case id, name, what, stage, when, category
        case placeID = "place_id"
        case placeName = "place_name"
        case lastDate = "last_date"
    }
}

public struct DistrictProjectsOverview: Codable, Sendable {
    public let districts: [DistrictProjectsOverviewEntry]
    /// Stadtzahlen und Highlights (seit der Auswahl-Anzeigetafel, 09/2026) —
    /// optional, damit ein älterer Server die Übersicht nicht leer lässt.
    public let total: Int?
    public let stages: [String: Int]?
    public let highlights: [DistrictHighlight]?
    public let updatedAt: String?

    enum CodingKeys: String, CodingKey {
        case districts, total, stages, highlights
        case updatedAt = "updated_at"
    }

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        districts = try c.decode([DistrictProjectsOverviewEntry].self, forKey: .districts)
        total = try c.decodeIfPresent(Int.self, forKey: .total)
        stages = try c.decodeIfPresent([String: Int].self, forKey: .stages)
        highlights = try c.decodeIfPresent([DistrictHighlight].self, forKey: .highlights)
        updatedAt = try c.decodeIfPresent(String.self, forKey: .updatedAt)
    }
}

public struct DistrictProjectDecision: Codable, Sendable, Hashable, Identifiable {
    public let id: Int
    public let title: String
    public let outcome: String?
    public let date: String
    public let committee: String?
}

/// Ein Bebauungsplan hinter einem Ort der Art `bplan`: Nummer, Name und die
/// Stationen des Verfahrens aus den offenen Geodaten der Stadt.
public struct DistrictPlanInfo: Codable, Sendable, Hashable {
    public let nr: String
    public let name: String
    /// `effective` (rechtsverbindlich) oder `in_procedure` (in Aufstellung).
    public let status: String
    public let resolutionDate: String?
    public let adoptionDate: String?
    public let effectiveDate: String?
    public let note: String?
    public let source: String
    public let sourceURL: String

    enum CodingKeys: String, CodingKey {
        case nr, name, status, note, source
        case resolutionDate = "resolution_date"
        case adoptionDate = "adoption_date"
        case effectiveDate = "effective_date"
        case sourceURL = "source_url"
    }
}

/// Ein Ort eines Vorhabens auf der Karte — Punkt, bei Straßen die Linie
/// (LineString/MultiLineString), bei Bebauungsplänen (`kind = bplan`) der
/// Geltungsbereich (Polygon/MultiPolygon) als GeoJSON, als `JSONValue`
/// durchgereicht.
public struct DistrictProjectLocation: Codable, Sendable, Hashable, Identifiable {
    public var id: String { slug }
    public let slug: String
    public let name: String
    public let kind: String
    public let latitude: Double
    public let longitude: Double
    public let geometry: JSONValue?
    /// `subject` — dort ändert sich etwas; `boundary` — nur Abschnittsgrenze
    /// („Am Schmeel bis Brahmweg"), auf der Karte keine Linie.
    public let role: String
    /// Nur bei `kind == "bplan"`: der Plan hinter der Fläche.
    public let plan: DistrictPlanInfo?

    enum CodingKeys: String, CodingKey {
        case slug, name, kind, geometry, role, plan
        case latitude = "lat"
        case longitude = "lon"
    }
}

/// Ein Vorhaben auf der Tafel „Mein Viertel" (`council/viertel.py`).
/// `stage` ∈ idea | planning | decided | building | done | rejected,
/// `category` ∈ housing | traffic | school_childcare | green | culture_sport_social | other.
public struct DistrictProject: Codable, Sendable, Hashable, Identifiable {
    public let id: Int
    public let projectKey: String
    public let placeID: String
    public let name: String
    public let what: String
    public let stage: String
    public let when: String?
    public let category: String
    public let confidence: Int
    public let firstDate: String?
    public let lastDate: String?
    public let reportCount: Int
    public let hidden: Bool
    public let reported: Bool
    public let decisions: [DistrictProjectDecision]
    public let locations: [DistrictProjectLocation]

    enum CodingKeys: String, CodingKey {
        case id, name, what, stage, when, category, confidence, hidden, reported, decisions, locations
        case projectKey = "project_key"
        case placeID = "place_id"
        case firstDate = "first_date"
        case lastDate = "last_date"
        case reportCount = "report_count"
    }
}

public struct DistrictUpcomingItem: Codable, Sendable, Hashable, Identifiable {
    public let id: Int
    public let ksinr: Int
    public let itemNumber: String?
    public let title: String
    public let kvonr: Int?
    public let sessionDate: String
    public let sessionTime: String?
    public let committee: String?
    public let location: String

    enum CodingKeys: String, CodingKey {
        case id, ksinr, title, kvonr, committee, location
        case itemNumber = "item_number"
        case sessionDate = "session_date"
        case sessionTime = "session_time"
    }
}

public struct DistrictInvestment: Codable, Sendable, Hashable {
    public let programmeYear: Int
    public let code: String?
    public let label: String
    public let totalEUR: Double
    public let location: String

    enum CodingKeys: String, CodingKey {
        case code, label, location
        case programmeYear = "programme_year"
        case totalEUR = "total_eur"
    }
}

public struct DistrictParticipation: Codable, Sendable, Hashable, Identifiable {
    public var id: String { (url ?? "") + (title ?? "") + (step ?? "") }
    public let title: String?
    public let place: String?
    public let step: String?
    public let validFrom: String?
    public let validUntil: String?
    public let url: String?
    public let planNrs: [String]
    /// Geltungsbereich des Plans (Polygon/MultiPolygon als GeoJSON) — nil,
    /// wenn das Geoportal den Plan (noch) nicht kennt. Optional dekodiert:
    /// ältere Server liefern das Feld nicht.
    public let geometry: JSONValue?
    public let latitude: Double?
    public let longitude: Double?
    public let planNr: String?
    public let planStatus: String?

    enum CodingKeys: String, CodingKey {
        case title, place, step, url, geometry
        case validFrom = "valid_from"
        case validUntil = "valid_until"
        case planNrs = "plan_nrs"
        case latitude = "lat"
        case longitude = "lon"
        case planNr = "plan_nr"
        case planStatus = "plan_status"
    }
}

public struct DistrictNeighbour: Codable, Sendable, Hashable, Identifiable {
    public var id: String { placeID }
    public let placeID: String
    public let name: String
    public let count: Int

    enum CodingKeys: String, CodingKey {
        case name, count
        case placeID = "place_id"
    }
}

/// Eine laufende Sperrung der Stadt (Geoportal) im Viertel — Linie als
/// GeoJSON (LineString/MultiLineString), Kontext, kein Vorhaben.
public struct DistrictClosure: Codable, Sendable, Hashable, Identifiable {
    public let id: Int
    public let street: String
    public let reason: String?
    public let kind: Int?
    public let kindLabel: String?
    public let validFrom: String?
    public let validUntil: String?
    public let description: String?
    public let geometry: JSONValue?
    public let latitude: Double?
    public let longitude: Double?

    enum CodingKeys: String, CodingKey {
        case id, street, reason, kind, description, geometry
        case kindLabel = "kind_label"
        case validFrom = "valid_from"
        case validUntil = "valid_until"
        case latitude = "lat"
        case longitude = "lon"
    }
}

/// Eine Pressemitteilung der Stadt mit Bezug auf das Viertel.
public struct DistrictPressItem: Codable, Sendable, Hashable, Identifiable {
    public let id: Int
    public let title: String
    public let date: String?
    public let url: String
    public let teaser: String
    public let evidence: String?
    public let via: String?
}

/// `GET /api/districts/{place_id}/projects` — die Tafel eines Ortsbereichs.
/// `place` ist die Ortsdarstellung des Katalogs; hier reichen id und name.
/// `closures` und `press` sind optional dekodiert: Die App im Store wurde
/// gegen einen Server ohne die beiden Felder gebaut (s. ios/CLAUDE.md).
public struct DistrictProjects: Codable, Sendable {
    public let place: DistrictPlace
    public let projects: [DistrictProject]
    public let upcoming: [DistrictUpcomingItem]
    public let investments: [DistrictInvestment]
    public let participations: [DistrictParticipation]
    public let closures: [DistrictClosure]
    public let press: [DistrictPressItem]
    public let neighbours: [DistrictNeighbour]
    public let updatedAt: String?

    enum CodingKeys: String, CodingKey {
        case place, projects, upcoming, investments, participations, closures, press, neighbours
        case updatedAt = "updated_at"
    }

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        place = try c.decode(DistrictPlace.self, forKey: .place)
        projects = try c.decode([DistrictProject].self, forKey: .projects)
        upcoming = try c.decode([DistrictUpcomingItem].self, forKey: .upcoming)
        investments = try c.decode([DistrictInvestment].self, forKey: .investments)
        participations = try c.decode([DistrictParticipation].self, forKey: .participations)
        closures = try c.decodeIfPresent([DistrictClosure].self, forKey: .closures) ?? []
        press = try c.decodeIfPresent([DistrictPressItem].self, forKey: .press) ?? []
        neighbours = try c.decode([DistrictNeighbour].self, forKey: .neighbours)
        updatedAt = try c.decodeIfPresent(String.self, forKey: .updatedAt)
    }
}

public struct DistrictPlace: Codable, Sendable, Hashable {
    public let id: String
    public let name: String
    public let description: String?
}

public struct DistrictProjectReportOut: Codable, Sendable {
    public let ok: Bool
    public let reportCount: Int
    public let hidden: Bool

    enum CodingKeys: String, CodingKey {
        case ok, hidden
        case reportCount = "report_count"
    }
}

public struct SetupProgress: Codable, Sendable, Equatable {
    public let step: Int
    public let startedAt: String?
    public let doneAt: String?

    enum CodingKeys: String, CodingKey {
        case step
        case startedAt = "started_at"
        case doneAt = "done_at"
    }
}

public struct User: Codable, Sendable, Equatable, Identifiable {
    public let id: Int
    public let email: String
    /// Die stärkste Rolle. Bleibt, weil ältere App-Fassungen sie so lesen —
    /// neuer Code fragt `can(_:)`.
    public let role: String
    /// Alle Rollen dieses Kontos. Optional mit Vorgabe, weil ein Backend im
    /// Stand vor 09/2026 sie nicht mitschickt: Ein nicht-optionales Feld ließe
    /// den `JSONDecoder` dort werfen, und die App käme nicht über die Anmeldung
    /// hinaus (die Falle steht in ios/CLAUDE.md).
    public let roles: [String]?
    /// Was dieses Konto DARF — gegen diese Liste wird geprüft, nie gegen einen
    /// Rollennamen. Eine neue Rolle im Backend wirkt damit ohne App-Update.
    public let permissions: [String]?
    public let status: String
    public let deliveryChannel: String
    public let emailVerified: Bool
    public let appleLinked: Bool
    public let hasPassword: Bool
    public let accessToken: String?
    public let displayName: String?
    public let savesConversations: Int?
    /// Ein SCHWEBENDER Adresswechsel: die Adresse, an die ein Bestätigungslink
    /// unterwegs ist (`nil` = keiner). Optional, weil ein Backend im Stand vor
    /// 09/2026 den Schlüssel nicht mitschickt — ein nicht-optionales Feld
    /// ließe den `JSONDecoder` dort werfen und die App käme nicht über die
    /// Anmeldung hinaus (die Falle steht in ios/CLAUDE.md).
    public let pendingEmail: String?

    public var isActive: Bool { status == "active" && emailVerified }

    /// Von einem Admin abgeschaltet — nicht zu verwechseln mit „wartet auf die
    /// eigene E-Mail-Bestätigung".
    ///
    /// Bis 09/2026 trugen beide Zustände serverseitig denselben Wert
    /// `pending`, und die App zeigte deshalb einer gesperrten Person „Bestätige
    /// deine E-Mail-Adresse" — die sie längst bestätigt hatte. Der zweite Teil
    /// der Bedingung fängt ein Backend im alten Stand ab: Dort ist ein
    /// bestätigtes, nicht aktives Konto genau dieser Fall.
    public var isDisabled: Bool {
        guard !isActive else { return false }
        return status == "disabled" || (status != "active" && emailVerified)
    }

    /// Trägt dieses Konto das Recht? Der eine Weg, Rechte zu prüfen.
    public func can(_ permission: String) -> Bool {
        if let permissions { return permissions.contains(permission) }
        // Backend ohne Rechte-Feld: auf die Alt-Spalte zurückfallen, damit ein
        // Admin nicht plötzlich vor verschlossenen Türen steht.
        return role == "admin"
    }

    public var isAdmin: Bool { can("admin") }
    /// Der Haushalts-Bereich (im Web 20 Seiten; die App zeigt ihn noch nicht).
    public var canSeeBudget: Bool { can("budget") }

    enum CodingKeys: String, CodingKey {
        case id, email, role, roles, permissions, status
        case deliveryChannel = "delivery_channel"
        case emailVerified = "email_verified"
        case appleLinked = "apple_linked"
        case hasPassword = "has_password"
        case accessToken = "access_token"
        case displayName = "display_name"
        case savesConversations = "saves_conversations"
        case pendingEmail = "pending_email"
    }
}

public struct Topic: Codable, Sendable, Equatable, Identifiable {
    public let id: Int
    public let name: String
    public let description: String
    public let createdAt: String
    public let decisionCount: Int
    public let decisionCountCapped: Bool
    public let matched: Bool
    public let lastHitID: Int?
    public let lastHitTitle: String?
    public let lastHitDate: String?
    public let unreadCount: Int
    public let recentHits: [TopicHit]
    /// Treffer der letzten sechs Monate. Hieß bis #826 `hits_30d` und zählte
    /// 30 Tage; die App las den alten Namen noch, bekam ihn nie und zeigte
    /// deshalb bei jedem Thema eine 0.
    public let hits6Months: Int

    enum CodingKeys: String, CodingKey {
        case id, name, description, matched
        case createdAt = "created_at"
        case decisionCount = "decision_count"
        case decisionCountCapped = "decision_count_capped"
        case lastHitID = "last_hit_id"
        case lastHitTitle = "last_hit_title"
        case lastHitDate = "last_hit_date"
        case unreadCount = "unread_count"
        case recentHits = "recent_hits"
        case hits6Months = "hits_6m"
    }

    public init(from decoder: Decoder) throws {
        let values = try decoder.container(keyedBy: CodingKeys.self)
        id = try values.decode(Int.self, forKey: .id)
        name = try values.decode(String.self, forKey: .name)
        description = try values.decode(String.self, forKey: .description)
        createdAt = try values.decodeIfPresent(String.self, forKey: .createdAt) ?? ""
        decisionCount = try values.decodeIfPresent(Int.self, forKey: .decisionCount) ?? 0
        decisionCountCapped = try values.decodeIfPresent(Bool.self, forKey: .decisionCountCapped) ?? false
        matched = try values.decodeIfPresent(Bool.self, forKey: .matched) ?? false
        lastHitID = try values.decodeIfPresent(Int.self, forKey: .lastHitID)
        lastHitTitle = try values.decodeIfPresent(String.self, forKey: .lastHitTitle)
        lastHitDate = try values.decodeIfPresent(String.self, forKey: .lastHitDate)
        unreadCount = try values.decodeIfPresent(Int.self, forKey: .unreadCount) ?? 0
        recentHits = try values.decodeIfPresent([TopicHit].self, forKey: .recentHits) ?? []
        hits6Months = try values.decodeIfPresent(Int.self, forKey: .hits6Months) ?? 0
    }
}

public struct TopicHit: Codable, Sendable, Equatable, Identifiable {
    public let id: Int
    public let title: String
    public let committee: String?
    public let sessionDate: String?
    public let outcome: String?
    public let isNew: Bool

    enum CodingKeys: String, CodingKey {
        case id, title, committee, outcome
        case sessionDate = "session_date"
        case isNew = "is_new"
    }
}

/// Ein Oldenburger Beleg unter einem Urteil — wo möglich mit Weg dorthin.
public struct IdeaEvidence: Codable, Sendable, Hashable, Identifiable {
    public var id: Int { kvonr ?? decisionID ?? title.hashValue }
    /// Die Beschluss-Id, wenn ein Beschluss dahintersteht. Dann führt die
    /// Zeile auf seine Seite; sonst bleibt sie eine Zeile ohne Ziel.
    public let decisionID: Int?
    public let kvonr: Int?
    public let title: String
    public let date: String?
    public let outcome: String?

    enum CodingKeys: String, CodingKey {
        case title, date, outcome, kvonr
        case decisionID = "decision_id"
    }

    public init(from decoder: Decoder) throws {
        let v = try decoder.container(keyedBy: CodingKeys.self)
        decisionID = try v.decodeIfPresent(Int.self, forKey: .decisionID)
        kvonr = try v.decodeIfPresent(Int.self, forKey: .kvonr)
        title = try v.decodeIfPresent(String.self, forKey: .title) ?? ""
        date = try v.decodeIfPresent(String.self, forKey: .date)
        outcome = try v.decodeIfPresent(String.self, forKey: .outcome)
    }

    public init(decisionID: Int? = nil, kvonr: Int? = nil, title: String,
                date: String? = nil, outcome: String? = nil) {
        self.decisionID = decisionID
        self.kvonr = kvonr
        self.title = title
        self.date = date
        self.outcome = outcome
    }
}

/// Eine fremde Vorlage samt Urteil, ob Oldenburg sie schon hat.
///
/// Alles außer der Kennung ist optional oder hat eine Vorgabe — dieselbe
/// Lehre wie bei ``ElsewhereItem``: Die Ratsinformationssysteme füllen sehr
/// unterschiedlich viel aus, und ein nicht-optionales Feld hieße,
/// `JSONDecoder` wirft und die ganze Liste bleibt leer statt unvollständig.
public struct IdeaSibling: Codable, Sendable, Hashable, Identifiable {
    public var id: String { paperID }
    public let paperID: String
    public let name: String
    public let date: String?

    enum CodingKeys: String, CodingKey {
        case name, date
        case paperID = "paper_id"
    }
}

public struct Idea: Codable, Sendable, Hashable, Identifiable {
    public var id: String { paperID }
    public let paperID: String
    public let bodyID: String
    public let bodyName: String
    public let name: String
    public let date: String?
    public let kind: String
    public let web: String?
    public let outcome: String
    public let field: String?
    public let instrument: String?
    public let summary: String?
    public let transfer: String
    public let competence: String?
    public let originator: String?
    /// Das Urteil aus `council/cities/fit.py`.
    public let status: String
    public let reason: String
    public let confidence: String
    public let evidence: [IdeaEvidence]
    /// Was die Idee den Rat kosten würde: inquiry < review < resolution <
    /// decision < budget. Leer, solange der Wochen-Cron sie nicht vergeben hat.
    public let effort: String
    /// Wer sie in Oldenburg tun müsste, wenn nicht die Stadt selbst.
    public let addressee: String?
    /// In wie vielen ANDEREN Städten dieselbe Idee vorkommt. 0 heißt: in
    /// keiner — kein Makel, sondern eine Aussage über die Idee.
    public let peers: Int
    /// Was DIESES Konto zum Urteil gesagt hat: "right", "wrong" oder leer.
    public let feedback: String
    /// Die weiteren Vorlagen DERSELBEN Stadt zu derselben Idee, älteste
    /// zuerst. Potsdam hat das Denkmalpflege-Konzept dreimal beantragt;
    /// gezeigt wird die jüngste, hier stehen die übrigen.
    public let siblings: [IdeaSibling]

    enum CodingKeys: String, CodingKey {
        case name, date, kind, web, outcome, field, instrument, summary
        case transfer, competence, originator, status, reason
        case confidence, evidence, effort, addressee, peers, feedback, siblings
        case paperID = "paper_id"
        case bodyID = "body_id"
        case bodyName = "body_name"
    }

    public init(from decoder: Decoder) throws {
        let v = try decoder.container(keyedBy: CodingKeys.self)
        paperID = try v.decode(String.self, forKey: .paperID)
        bodyID = try v.decodeIfPresent(String.self, forKey: .bodyID) ?? ""
        bodyName = try v.decodeIfPresent(String.self, forKey: .bodyName) ?? bodyID
        name = try v.decodeIfPresent(String.self, forKey: .name) ?? "Vorlage"
        date = try v.decodeIfPresent(String.self, forKey: .date)
        kind = try v.decodeIfPresent(String.self, forKey: .kind) ?? "other"
        web = try v.decodeIfPresent(String.self, forKey: .web)
        outcome = try v.decodeIfPresent(String.self, forKey: .outcome) ?? "none"
        field = try v.decodeIfPresent(String.self, forKey: .field)
        instrument = try v.decodeIfPresent(String.self, forKey: .instrument)
        summary = try v.decodeIfPresent(String.self, forKey: .summary)
        transfer = try v.decodeIfPresent(String.self, forKey: .transfer) ?? ""
        competence = try v.decodeIfPresent(String.self, forKey: .competence)
        originator = try v.decodeIfPresent(String.self, forKey: .originator)
        status = try v.decodeIfPresent(String.self, forKey: .status) ?? ""
        reason = try v.decodeIfPresent(String.self, forKey: .reason) ?? ""
        confidence = try v.decodeIfPresent(String.self, forKey: .confidence) ?? ""
        evidence = try v.decodeIfPresent([IdeaEvidence].self, forKey: .evidence) ?? []
        // Alle drei mit Rückfall: Die ausgelieferte App muss auch dann laufen,
        // wenn der Server sie noch nicht schickt (`ios_vertrag.py`).
        effort = try v.decodeIfPresent(String.self, forKey: .effort) ?? ""
        addressee = try v.decodeIfPresent(String.self, forKey: .addressee)
        peers = try v.decodeIfPresent(Int.self, forKey: .peers) ?? 0
        feedback = try v.decodeIfPresent(String.self, forKey: .feedback) ?? ""
        siblings = try v.decodeIfPresent([IdeaSibling].self, forKey: .siblings) ?? []
    }
}

public struct IdeasResponse: Codable, Sendable {
    public let field: String
    public let total: Int
    public let page: Int
    public let perPage: Int
    /// Je Status die Zahl der Ideen im Feld.
    public let counts: [String: Int]
    public let items: [Idea]

    enum CodingKeys: String, CodingKey {
        case field, total, page, counts, items
        case perPage = "per_page"
    }

    public init(from decoder: Decoder) throws {
        let v = try decoder.container(keyedBy: CodingKeys.self)
        field = try v.decodeIfPresent(String.self, forKey: .field) ?? ""
        total = try v.decodeIfPresent(Int.self, forKey: .total) ?? 0
        page = try v.decodeIfPresent(Int.self, forKey: .page) ?? 1
        perPage = try v.decodeIfPresent(Int.self, forKey: .perPage) ?? 30
        counts = try v.decodeIfPresent([String: Int].self, forKey: .counts) ?? [:]
        items = try v.decodeIfPresent([Idea].self, forKey: .items) ?? []
    }
}

/// Die freie Suche über die Vorlagen anderer Städte.
public struct IdeaSearchResponse: Codable, Sendable {
    public let query: String
    public let total: Int
    public let items: [Idea]

    public init(from decoder: Decoder) throws {
        let v = try decoder.container(keyedBy: CodingKeys.self)
        query = try v.decodeIfPresent(String.self, forKey: .query) ?? ""
        total = try v.decodeIfPresent(Int.self, forKey: .total) ?? 0
        items = try v.decodeIfPresent([Idea].self, forKey: .items) ?? []
    }

    enum CodingKeys: String, CodingKey { case query, total, items }
}


/// Ein Themenfeld auf der Übersicht.
public struct IdeaFieldSummary: Codable, Sendable, Hashable, Identifiable {
    public var id: String { field }
    public let field: String
    public let total: Int
    public let missing: Int
    public let partial: Int
    public let present: Int
    /// Ideen dieses Feldes, die in mindestens ZWEI anderen Städten liegen und
    /// Oldenburg fehlen. Eine Tatsache — vorher stand hier die Zahl der
    /// „lohnt sich"-Urteile, also eine Modellmeinung.
    public let multiCity: Int

    enum CodingKeys: String, CodingKey {
        case field, total, missing, partial, present
        case multiCity = "multi_city"
    }

    public init(from decoder: Decoder) throws {
        let v = try decoder.container(keyedBy: CodingKeys.self)
        field = try v.decodeIfPresent(String.self, forKey: .field) ?? ""
        total = try v.decodeIfPresent(Int.self, forKey: .total) ?? 0
        missing = try v.decodeIfPresent(Int.self, forKey: .missing) ?? 0
        partial = try v.decodeIfPresent(Int.self, forKey: .partial) ?? 0
        present = try v.decodeIfPresent(Int.self, forKey: .present) ?? 0
        multiCity = try v.decodeIfPresent(Int.self, forKey: .multiCity) ?? 0
    }
}

public struct IdeaFields: Codable, Sendable {
    public let fields: [IdeaFieldSummary]

    public init(from decoder: Decoder) throws {
        let v = try decoder.container(keyedBy: CodingKeys.self)
        fields = try v.decodeIfPresent([IdeaFieldSummary].self, forKey: .fields) ?? []
    }

    enum CodingKeys: String, CodingKey { case fields }
}


/// Eine Vorlage aus einer anderen Stadt, die zu einem Oldenburger Beschluss
/// passt — der Block „Anderswo beschlossen".
///
/// Alles außer der Kennung ist optional: Die Ratsinformationssysteme der
/// Städte füllen unterschiedlich viel aus. Münster etwa liefert über OParl
/// keine Ansichtsseite, also bleibt `web` leer und die Zeile bekommt keinen
/// Link. Ein nicht-optionales Feld hier hieße: `JSONDecoder` wirft, und der
/// ganze Abschnitt bleibt leer statt unvollständig.
public struct ElsewhereItem: Codable, Sendable, Hashable, Identifiable {
    public var id: String { paperID }
    public let bodyID: String
    public let bodyName: String
    public let paperID: String
    public let name: String
    public let reference: String?
    public let date: String?
    public let kind: String
    public let paperTypeRaw: String?
    public let web: String?
    /// Kanonisches Ergebnis; `none`, wenn die Stadt keins ausweist — bei rund
    /// der Hälfte der Tagesordnungspunkte der Normalfall, kein Fehler.
    public let outcome: String
    public let outcomeRaw: String?
    public let score: Double
    public let summary: String?
    public let instrument: String?
    public let transfer: String?
    public let originator: String?

    enum CodingKeys: String, CodingKey {
        case name, kind, web, outcome, score, summary, instrument, transfer, originator
        case date, reference
        case bodyID = "body_id"
        case bodyName = "body_name"
        case paperID = "paper_id"
        case paperTypeRaw = "paper_type_raw"
        case outcomeRaw = "outcome_raw"
    }

    public init(from decoder: Decoder) throws {
        let values = try decoder.container(keyedBy: CodingKeys.self)
        paperID = try values.decode(String.self, forKey: .paperID)
        bodyID = try values.decodeIfPresent(String.self, forKey: .bodyID) ?? ""
        bodyName = try values.decodeIfPresent(String.self, forKey: .bodyName) ?? bodyID
        name = try values.decodeIfPresent(String.self, forKey: .name) ?? "Vorlage"
        reference = try values.decodeIfPresent(String.self, forKey: .reference)
        date = try values.decodeIfPresent(String.self, forKey: .date)
        kind = try values.decodeIfPresent(String.self, forKey: .kind) ?? "other"
        paperTypeRaw = try values.decodeIfPresent(String.self, forKey: .paperTypeRaw)
        web = try values.decodeIfPresent(String.self, forKey: .web)
        outcome = try values.decodeIfPresent(String.self, forKey: .outcome) ?? "none"
        outcomeRaw = try values.decodeIfPresent(String.self, forKey: .outcomeRaw)
        score = try values.decodeIfPresent(Double.self, forKey: .score) ?? 0
        summary = try values.decodeIfPresent(String.self, forKey: .summary)
        instrument = try values.decodeIfPresent(String.self, forKey: .instrument)
        transfer = try values.decodeIfPresent(String.self, forKey: .transfer)
        originator = try values.decodeIfPresent(String.self, forKey: .originator)
    }

    public init(bodyID: String, bodyName: String, paperID: String, name: String,
                reference: String? = nil, date: String? = nil, kind: String = "other",
                paperTypeRaw: String? = nil, web: String? = nil, outcome: String = "none",
                outcomeRaw: String? = nil, score: Double = 0, summary: String? = nil,
                instrument: String? = nil, transfer: String? = nil, originator: String? = nil) {
        self.bodyID = bodyID
        self.bodyName = bodyName
        self.paperID = paperID
        self.name = name
        self.reference = reference
        self.date = date
        self.kind = kind
        self.paperTypeRaw = paperTypeRaw
        self.web = web
        self.outcome = outcome
        self.outcomeRaw = outcomeRaw
        self.score = score
        self.summary = summary
        self.instrument = instrument
        self.transfer = transfer
        self.originator = originator
    }
}

public struct ElsewhereResponse: Codable, Sendable {
    public let decisionID: Int
    public let items: [ElsewhereItem]
    /// Die Städte, aus denen Treffer stammen — für die Zeile „aus X und Y".
    public let bodies: [String]

    enum CodingKeys: String, CodingKey {
        case items, bodies
        case decisionID = "decision_id"
    }

    public init(from decoder: Decoder) throws {
        let values = try decoder.container(keyedBy: CodingKeys.self)
        decisionID = try values.decodeIfPresent(Int.self, forKey: .decisionID) ?? 0
        items = try values.decodeIfPresent([ElsewhereItem].self, forKey: .items) ?? []
        bodies = try values.decodeIfPresent([String].self, forKey: .bodies) ?? []
    }

    public init(decisionID: Int, items: [ElsewhereItem], bodies: [String]) {
        self.decisionID = decisionID
        self.items = items
        self.bodies = bodies
    }
}

public struct DecisionSummary: Codable, Sendable, Hashable, Identifiable {
    public let id: Int
    public let title: String
    public let summary: String?
    public let simpleSummary: String?
    public let officialText: String?
    public let committee: String?
    public let sessionDate: String?
    public let outcome: String?
    public let policyField: String?
    public let itemNumber: String?
    public let kind: String?
    public let sessionID: Int?
    public let templateNumber: String?
    public let vote: String?
    public let noVotes: Int?
    public let abstentions: Int?
    public let factions: [String]
    public let parties: [String]
    public let policyTags: [String]
    public let rawResult: String?
    public let protocolURL: String?
    public let deviation: String?
    public let placeName: String?
    public let latitude: Double?
    public let longitude: Double?
    public let amountEUR: Double?
    public let importance: Int?
    public let interest: Int?
    public let interestReason: String?
    public let impact: Int?
    public let impactReason: String?

    enum CodingKeys: String, CodingKey {
        case id, title, summary, committee, outcome, kind, vote, factions, parties, importance, interest, impact
        case simpleSummary = "simple_summary"
        case officialText = "official_text"
        case policyTags = "policy_tags"
        case rawResult = "raw_result"
        case protocolURL = "protocol_url"
        case deviation = "deviation"
        case amountEUR = "amount_eur"
        case interestReason = "interest_reason"
        case impactReason = "impact_reason"
        case placeName = "ort_name"
        case latitude = "lat"
        case longitude = "lon"
        case sessionID = "ksinr"
        case templateNumber = "template_number"
        case noVotes = "no_votes"
        case abstentions = "abstentions"
        case sessionDate = "session_date"
        case policyField = "policy_field"
        case itemNumber = "item_number"
    }

    public init(from decoder: Decoder) throws {
        let values = try decoder.container(keyedBy: CodingKeys.self)
        id = try values.decode(Int.self, forKey: .id)
        title = try values.decodeIfPresent(String.self, forKey: .title) ?? "Beschluss"
        simpleSummary = try values.decodeIfPresent(String.self, forKey: .simpleSummary)
        summary = try values.decodeIfPresent(String.self, forKey: .summary) ?? simpleSummary
        officialText = try values.decodeIfPresent(String.self, forKey: .officialText)
        committee = try values.decodeIfPresent(String.self, forKey: .committee)
        sessionDate = try values.decodeIfPresent(String.self, forKey: .sessionDate)
        outcome = try values.decodeIfPresent(String.self, forKey: .outcome)
        policyField = try values.decodeIfPresent(String.self, forKey: .policyField)
        itemNumber = try values.decodeIfPresent(String.self, forKey: .itemNumber)
        kind = try values.decodeIfPresent(String.self, forKey: .kind)
        sessionID = try values.decodeIfPresent(Int.self, forKey: .sessionID)
        templateNumber = try values.decodeIfPresent(String.self, forKey: .templateNumber)
        vote = try values.decodeIfPresent(String.self, forKey: .vote)
        noVotes = try values.decodeIfPresent(Int.self, forKey: .noVotes)
        abstentions = try values.decodeIfPresent(Int.self, forKey: .abstentions)
        factions = try values.decodeIfPresent([String].self, forKey: .factions) ?? []
        parties = try values.decodeIfPresent([String].self, forKey: .parties) ?? factions
        policyTags = try values.decodeIfPresent([String].self, forKey: .policyTags) ?? []
        rawResult = try values.decodeIfPresent(String.self, forKey: .rawResult)
        protocolURL = try values.decodeIfPresent(String.self, forKey: .protocolURL)
        deviation = try values.decodeIfPresent(String.self, forKey: .deviation)
        placeName = try values.decodeIfPresent(String.self, forKey: .placeName)
        latitude = try values.decodeIfPresent(Double.self, forKey: .latitude)
        longitude = try values.decodeIfPresent(Double.self, forKey: .longitude)
        amountEUR = try values.decodeIfPresent(Double.self, forKey: .amountEUR)
        importance = try values.decodeIfPresent(Int.self, forKey: .importance)
        interest = try values.decodeIfPresent(Int.self, forKey: .interest)
        interestReason = try values.decodeIfPresent(String.self, forKey: .interestReason)
        impact = try values.decodeIfPresent(Int.self, forKey: .impact)
        impactReason = try values.decodeIfPresent(String.self, forKey: .impactReason)
    }

    public func encode(to encoder: Encoder) throws {
        var values = encoder.container(keyedBy: CodingKeys.self)
        try values.encode(id, forKey: .id)
        try values.encode(title, forKey: .title)
        try values.encodeIfPresent(summary, forKey: .summary)
        try values.encodeIfPresent(simpleSummary, forKey: .simpleSummary)
        try values.encodeIfPresent(officialText, forKey: .officialText)
        try values.encodeIfPresent(committee, forKey: .committee)
        try values.encodeIfPresent(sessionDate, forKey: .sessionDate)
        try values.encodeIfPresent(outcome, forKey: .outcome)
        try values.encodeIfPresent(policyField, forKey: .policyField)
        try values.encodeIfPresent(itemNumber, forKey: .itemNumber)
        try values.encodeIfPresent(kind, forKey: .kind)
        try values.encodeIfPresent(sessionID, forKey: .sessionID)
        try values.encodeIfPresent(templateNumber, forKey: .templateNumber)
        try values.encodeIfPresent(vote, forKey: .vote)
        try values.encodeIfPresent(noVotes, forKey: .noVotes)
        try values.encodeIfPresent(abstentions, forKey: .abstentions)
        try values.encode(factions, forKey: .factions)
        try values.encode(parties, forKey: .parties)
        try values.encode(policyTags, forKey: .policyTags)
        try values.encodeIfPresent(rawResult, forKey: .rawResult)
        try values.encodeIfPresent(protocolURL, forKey: .protocolURL)
        try values.encodeIfPresent(deviation, forKey: .deviation)
        try values.encodeIfPresent(placeName, forKey: .placeName)
        try values.encodeIfPresent(latitude, forKey: .latitude)
        try values.encodeIfPresent(longitude, forKey: .longitude)
        try values.encodeIfPresent(amountEUR, forKey: .amountEUR)
        try values.encodeIfPresent(importance, forKey: .importance)
        try values.encodeIfPresent(interest, forKey: .interest)
        try values.encodeIfPresent(interestReason, forKey: .interestReason)
        try values.encodeIfPresent(impact, forKey: .impact)
        try values.encodeIfPresent(impactReason, forKey: .impactReason)
    }
}

public struct DecisionPage: Codable, Sendable {
    public let total: Int
    public let decisions: [DecisionSummary]
}

public struct DecisionDetail: Codable, Sendable {
    public let decision: DecisionSummary
    public let attendance: [CouncilAttendee]
    public let entities: [CouncilEntity]
    public let presentParties: [String]
    public let ratsinfoURL: String?
    public let similar: [DecisionSummary]
    public let subVotes: [DecisionSummary]
    public let templateJourney: [CouncilJourneyStop]
    public let consultations: [CouncilConsultationStop]
    public let templateURL: String?
    public let template: CouncilTemplate?
    public let attachments: [CouncilAttachment]
    public let participation: CouncilParticipation?
    public let importance: ImportanceBreakdown?
    public let follow: FollowStatus?
    public let planImageID: Int?

    enum CodingKeys: String, CodingKey {
        case decision, attendance, entities, similar, participation, follow, template
        case subVotes = "sub_votes"
        case templateJourney = "template_journey"
        case consultations = "deliberation_path"
        case templateURL = "template_url"
        case attachments = "attachments"
        case importance = "importance_breakdown"
        case presentParties = "present_parties"
        case ratsinfoURL = "ratsinfo_url"
        case planImageID = "plan_image"
    }

    public init(
        decision: DecisionSummary,
        attendance: [CouncilAttendee] = [],
        entities: [CouncilEntity] = [],
        presentParties: [String],
        ratsinfoURL: String?,
        similar: [DecisionSummary],
        subVotes: [DecisionSummary],
        templateJourney: [CouncilJourneyStop],
        consultations: [CouncilConsultationStop],
        templateURL: String?,
        template: CouncilTemplate?,
        attachments: [CouncilAttachment],
        participation: CouncilParticipation?,
        importance: ImportanceBreakdown?,
        follow: FollowStatus?,
        planImageID: Int? = nil
    ) {
        self.decision = decision
        self.attendance = attendance
        self.entities = entities
        self.presentParties = presentParties
        self.ratsinfoURL = ratsinfoURL
        self.similar = similar
        self.subVotes = subVotes
        self.templateJourney = templateJourney
        self.consultations = consultations
        self.templateURL = templateURL
        self.template = template
        self.attachments = attachments
        self.participation = participation
        self.importance = importance
        self.follow = follow
        self.planImageID = planImageID
    }

    public init(from decoder: Decoder) throws {
        let values = try decoder.container(keyedBy: CodingKeys.self)
        decision = try values.decode(DecisionSummary.self, forKey: .decision)
        attendance = try values.decodeIfPresent([CouncilAttendee].self, forKey: .attendance) ?? []
        entities = try values.decodeIfPresent([CouncilEntity].self, forKey: .entities) ?? []
        presentParties = try values.decodeIfPresent([String].self, forKey: .presentParties) ?? []
        ratsinfoURL = try values.decodeIfPresent(String.self, forKey: .ratsinfoURL)
        similar = try values.decodeIfPresent([DecisionSummary].self, forKey: .similar) ?? []
        subVotes = try values.decodeIfPresent([DecisionSummary].self, forKey: .subVotes) ?? []
        templateJourney = try values.decodeIfPresent([CouncilJourneyStop].self, forKey: .templateJourney) ?? []
        consultations = try values.decodeIfPresent([CouncilConsultationStop].self, forKey: .consultations) ?? []
        templateURL = try values.decodeIfPresent(String.self, forKey: .templateURL)
        template = try values.decodeIfPresent(CouncilTemplate.self, forKey: .template)
        attachments = try values.decodeIfPresent([CouncilAttachment].self, forKey: .attachments) ?? []
        participation = try values.decodeIfPresent(CouncilParticipation.self, forKey: .participation)
        importance = try values.decodeIfPresent(ImportanceBreakdown.self, forKey: .importance)
        follow = try values.decodeIfPresent(FollowStatus.self, forKey: .follow)
        planImageID = try values.decodeIfPresent(Int.self, forKey: .planImageID)
    }
}

public struct CouncilAttendee: Codable, Sendable, Hashable {
    public let name: String?
    public let party: String?
    public let role: String?
    public let note: String?
}

public struct CouncilEntity: Codable, Sendable, Hashable, Identifiable {
    public var id: String { slug }
    public let slug: String
    public let name: String
}

public struct CouncilJourneyStop: Codable, Sendable, Hashable, Identifiable {
    public var id: String { "\(sessionID)-\(itemNumber ?? "")" }
    public let sessionID: Int
    public let committee: String
    public let sessionDate: String
    public let itemNumber: String?

    enum CodingKeys: String, CodingKey {
        case committee
        case sessionID = "ksinr"
        case sessionDate = "session_date"
        case itemNumber = "item_number"
    }
}

public struct CouncilConsultationStop: Codable, Sendable, Hashable, Identifiable {
    public var id: String { "\(date ?? "")-\(committee)-\(sessionID ?? 0)" }
    public let date: String?
    public let committee: String
    public let itemNumber: String?
    public let result: String?
    public let sessionID: Int?
    public let future: Bool?

    enum CodingKeys: String, CodingKey {
        case date = "date"
        case committee = "committee"
        case itemNumber = "top"
        case result = "result"
        case sessionID = "ksinr"
        case future
    }

    public init(
        date: String?, committee: String, itemNumber: String?, result: String?,
        sessionID: Int?, future: Bool?
    ) {
        self.date = date
        self.committee = committee
        self.itemNumber = itemNumber
        self.result = result
        self.sessionID = sessionID
        self.future = future
    }
}

public struct CouncilTemplate: Codable, Sendable, Equatable {
    public let number: String?
    public let title: String?
    public let kind: String?
    public let documentURL: String?
    public let pageCount: Int?
    public let excerpt: String?
    public let department: String?
    public let climateCheck: String?
    public let financialCheck: String?

    enum CodingKeys: String, CodingKey {
        case title, excerpt, kind
        case number = "template_number"
        case documentURL = "document_url"
        case pageCount = "n_pages"
        case department = "office"
        case climateCheck = "climate_impact"
        case financialCheck = "financial_impact"
    }
}

public struct CouncilAttachment: Codable, Sendable, Hashable, Identifiable {
    public var id: Int { documentID }
    public let documentID: Int
    public let label: String
    public let url: String
    public let isMotion: Int?
    public let applicants: [String]
    public let status: String?

    enum CodingKeys: String, CodingKey {
        case label, url, status
        case documentID = "document_id"
        case isMotion = "is_motion"
        case applicants = "applicants"
    }

    public init(from decoder: Decoder) throws {
        let values = try decoder.container(keyedBy: CodingKeys.self)
        documentID = try values.decode(Int.self, forKey: .documentID)
        label = try values.decodeIfPresent(String.self, forKey: .label) ?? "Anlage"
        url = try values.decodeIfPresent(String.self, forKey: .url) ?? ""
        isMotion = try values.decodeIfPresent(Int.self, forKey: .isMotion)
        applicants = try values.decodeIfPresent([String].self, forKey: .applicants) ?? []
        status = try values.decodeIfPresent(String.self, forKey: .status)
    }
}

public struct CouncilParticipation: Codable, Sendable, Equatable {
    /// `title` und `url` stehen im Vertrag als `str | None` — eine
    /// Beteiligung ohne Titel oder Verweis hätte die Beschluss-Seite sonst
    /// gar nicht mehr geladen.
    public let title: String?
    public let step: String?
    public let from: String?
    public let until: String?
    public let url: String?
    public let status: String?

    enum CodingKeys: String, CodingKey {
        case title = "title"
        case step = "schritt"
        case from = "valid_from"
        case until = "valid_until"
        case url, status
    }
}

public struct ImportanceBreakdown: Codable, Sendable, Equatable {
    public let score: Int?
    public let impactReason: String?

    enum CodingKeys: String, CodingKey {
        case score
        case impactReason = "impact_reason"
    }
}

public struct FollowStatus: Codable, Sendable, Equatable {
    public let templateID: Int
    public let following: Bool

    enum CodingKeys: String, CodingKey {
        case templateID = "kvonr"
        case following
    }
}

public struct CommitteeOptions: Codable, Sendable {
    public let committees: [String]
    public let details: [CommitteeDetail]?
}

/// Die Kalender-Adresse eines Kontos (`/api/calendar/subscription`).
///
/// `webcalURL` öffnet auf dem iPhone direkt den Abo-Dialog von Apple
/// Kalender; `url` ist dieselbe Adresse als https zum Kopieren (Google,
/// Outlook). Das Token darin ist ein eigenes Geheimnis — „Neue Adresse"
/// (`POST /api/calendar/subscription/rotate`) macht die alte ungültig.
public struct CalendarSubscription: Decodable, Sendable, Equatable {
    public let url: String
    public let webcalURL: String
    public let subscribedCommittees: Int

    enum CodingKeys: String, CodingKey {
        case url
        case webcalURL = "webcal_url"
        case subscribedCommittees = "subscribed_committees"
    }

    public init(url: String, webcalURL: String, subscribedCommittees: Int) {
        self.url = url
        self.webcalURL = webcalURL
        self.subscribedCommittees = subscribedCommittees
    }
}

public struct CommitteeDetail: Codable, Sendable, Hashable, Identifiable {
    public var id: String { name }
    public let name: String
    public let nextDate: String?
    public let nextTime: String?
    public let decisionsYear: Int

    public init(name: String, nextDate: String?, nextTime: String?, decisionsYear: Int) {
        self.name = name
        self.nextDate = nextDate
        self.nextTime = nextTime
        self.decisionsYear = decisionsYear
    }

    enum CodingKeys: String, CodingKey {
        case name
        case nextDate = "next_date"
        case nextTime = "next_time"
        case decisionsYear = "decisions_year"
    }
}

public struct PolicyFieldOption: Codable, Sendable, Hashable, Identifiable {
    public var id: String { key }
    public let key: String
    public let label: String
    public let count: Int
}

public struct PolicyFieldOptions: Codable, Sendable {
    public let fields: [PolicyFieldOption]
}

public struct PartyOption: Codable, Sendable, Hashable, Identifiable {
    public var id: String { key }
    public let key: String
    public let label: String
    public let count: Int
}

public struct PartyOptions: Codable, Sendable {
    public let parties: [PartyOption]
}

public struct DistrictOption: Codable, Sendable, Hashable, Identifiable {
    public var id: String { placeID }
    public let placeID: String
    public let name: String
    public let kindLabel: String
    public let count: Int
    public let description: String?

    enum CodingKeys: String, CodingKey {
        case name, count, description
        case placeID = "place_id"
        case kindLabel = "kind_label"
    }
}

public struct DistrictOptions: Codable, Sendable {
    public let districts: [DistrictOption]
}

public struct CouncilMapPoint: Codable, Sendable, Hashable, Identifiable {
    public var id: String { slug }
    public let slug: String
    public let name: String
    public let kind: String
    public let count: Int
    public let latitude: Double
    public let longitude: Double
    public let target: String
    public let placeID: String?
    public let locationSlug: String?

    enum CodingKeys: String, CodingKey {
        case slug, name, kind, target
        case count = "n"
        case latitude = "lat"
        case longitude = "lon"
        case placeID = "place_id"
        case locationSlug = "location_slug"
    }
}

public struct CouncilMapPoints: Codable, Sendable {
    public let entities: [CouncilMapPoint]
}

public struct BookmarkEntry: Codable, Sendable, Identifiable {
    public let id: Int
    public let kind: String
    public let title: String
    public let subtitle: String
    public let state: String
    public let url: String
    public let sessionID: Int?
    public let itemNumber: String?
    public let notifyResult: Bool
    public let decision: DecisionSummary?
    public let session: CouncilSession?

    enum CodingKeys: String, CodingKey {
        case id, kind, title, subtitle, state, url, decision, session
        case sessionID = "ksinr"
        case itemNumber = "item_number"
        case notifyResult = "notify_result"
    }
}

public struct BookmarkPage: Codable, Sendable {
    public let bookmarks: [BookmarkEntry]
}

public struct FollowEntry: Codable, Sendable, Identifiable {
    public let id: Int
    public let templateID: Int
    /// Beide dürfen fehlen: Der Vertrag beschreibt sie als `str | None`, und
    /// im Bestand stehen Vorlagen ohne Titel (gemessen 02.09.2026: zwei von
    /// 5.083). Als Pflichtfelder gelesen hätte EINE davon gereicht, um die
    /// ganze Folgen-Liste beim Decodieren abbrechen zu lassen.
    public let templateNumber: String?
    public let title: String?
    public let url: String
    public let stationCount: Int
    public let next: CouncilConsultationStop?
    public let last: CouncilConsultationStop?

    enum CodingKeys: String, CodingKey {
        case id, title, url
        case templateID = "kvonr"
        case templateNumber = "template_number"
        case stationCount = "n_stationen"
        case next = "naechste"
        case last = "letzte"
    }
}

public struct FollowPage: Codable, Sendable {
    public let follows: [FollowEntry]
}

/// What is happening in the council chamber RIGHT NOW — from the transcript
/// of the O1 livestream (`council/livetracker.py`), rewritten every 30
/// seconds while the recording job runs. Only today's council session
/// carries one. `asOf` is the audio position the row reflects (ISO 8601 with
/// offset); the card derives "vor N Min." from it and says where it comes
/// from — it trails the room by under a minute.
public struct LiveState: Codable, Sendable, Hashable {
    /// Running item without the Ö/N prefix ("9.3"), nil before the first call.
    public let itemNumber: String?
    public let itemTitle: String?
    /// First item of a block that ran through in one window ("9.4" when the
    /// state says "9.8") — formalities are voted in seconds.
    public let blockStart: String?
    /// aufruf | aussprache | abstimmung | pause | unklar | ende
    public let phase: String
    public let speaker: String?
    public let party: String?
    public let since: String
    public let asOf: String
    public let updatedAt: String
    /// The chair closed the public part; the row stays for the record.
    public let finished: Bool

    enum CodingKeys: String, CodingKey {
        case phase, speaker, party, since, finished
        case itemNumber = "item_number"
        case itemTitle = "item_title"
        case blockStart = "block_start"
        case asOf = "as_of"
        case updatedAt = "updated_at"
    }

    public init(itemNumber: String?, itemTitle: String?, blockStart: String?, phase: String,
                speaker: String?, party: String?, since: String, asOf: String,
                updatedAt: String, finished: Bool) {
        self.itemNumber = itemNumber
        self.itemTitle = itemTitle
        self.blockStart = blockStart
        self.phase = phase
        self.speaker = speaker
        self.party = party
        self.since = since
        self.asOf = asOf
        self.updatedAt = updatedAt
        self.finished = finished
    }

    public init(from decoder: Decoder) throws {
        let values = try decoder.container(keyedBy: CodingKeys.self)
        itemNumber = try values.decodeIfPresent(String.self, forKey: .itemNumber)
        itemTitle = try values.decodeIfPresent(String.self, forKey: .itemTitle)
        blockStart = try values.decodeIfPresent(String.self, forKey: .blockStart)
        phase = try values.decodeIfPresent(String.self, forKey: .phase) ?? "unklar"
        speaker = try values.decodeIfPresent(String.self, forKey: .speaker)
        party = try values.decodeIfPresent(String.self, forKey: .party)
        since = try values.decodeIfPresent(String.self, forKey: .since) ?? ""
        asOf = try values.decodeIfPresent(String.self, forKey: .asOf) ?? ""
        updatedAt = try values.decodeIfPresent(String.self, forKey: .updatedAt) ?? ""
        finished = try values.decodeIfPresent(Bool.self, forKey: .finished) ?? false
    }
}

public struct CouncilSession: Codable, Sendable, Hashable, Identifiable {
    /// Terminierte Sitzungen aus dem Kalender haben noch keine `ksinr` — die
    /// bekommen sie erst mit der veröffentlichten Tagesordnung. Bis dahin
    /// identifiziert sie das, was die Antwort wirklich trägt: Gremium, Datum
    /// und Uhrzeit.
    ///
    /// Hier stand bis 09/2026 ein `calendarID`, das das Backend NIE geschickt
    /// hat. Der Rückfall war deshalb immer `title.hashValue` — und zwei
    /// Termine desselben Gremiums fielen in der Liste zusammen.
    public var id: Int {
        ksinr ?? "\(committee)|\(sessionDate)|\(sessionTime ?? "")".hashValue
    }
    public let ksinr: Int?
    public let committee: String
    public let sessionDate: String
    public let sessionTime: String?
    /// End of the LIVE window, computed by the server (`council/live.py`):
    /// the start of the next session that day, or a cap from the start —
    /// three hours for committees, four for the council. Council days run
    /// three bodies back to back (16:00 general committee, 16:30
    /// administrative committee, 18:00 council); they wait for each other
    /// instead of meeting in parallel. Only sent for today's sessions.
    public let liveUntil: String?
    /// Live state from the broadcast — only on today's council session while
    /// the recording job writes it (see `LiveState`).
    public let liveState: LiveState?
    public let location: String?
    public let itemCount: Int
    public let myTopicItems: [JSONValue]?
    /// Die wichtigsten Punkte der Sitzung — dieselbe Form wie die Punkte der
    /// Wochenvorschau, dieselbe Bewertung auf dem Server. Fehlt, wenn kein
    /// Punkt über der Schwelle liegt.
    public let highlights: [WeekPreviewItem]?

    enum CodingKeys: String, CodingKey {
        case ksinr, committee, location, highlights
        case sessionDate = "session_date"
        case sessionTime = "session_time"
        case liveUntil = "live_until"
        case liveState = "live_state"
        case itemCount = "n_items"
        case myTopicItems = "my_topic_items"
    }

    public init(from decoder: Decoder) throws {
        let values = try decoder.container(keyedBy: CodingKeys.self)
        ksinr = try values.decodeIfPresent(Int.self, forKey: .ksinr)
        committee = try values.decodeIfPresent(String.self, forKey: .committee) ?? "Gremium"
        sessionDate = try values.decodeIfPresent(String.self, forKey: .sessionDate) ?? ""
        sessionTime = try values.decodeIfPresent(String.self, forKey: .sessionTime)
        liveUntil = try values.decodeIfPresent(String.self, forKey: .liveUntil)
        liveState = try values.decodeIfPresent(LiveState.self, forKey: .liveState)
        location = try values.decodeIfPresent(String.self, forKey: .location)
        itemCount = try values.decodeIfPresent(Int.self, forKey: .itemCount) ?? 0
        myTopicItems = try values.decodeIfPresent([JSONValue].self, forKey: .myTopicItems)
        highlights = try values.decodeIfPresent([WeekPreviewItem].self, forKey: .highlights)
    }
}

public struct SessionPage: Codable, Sendable {
    public let count: Int
    public let total: Int
    public let sessions: [CouncilSession]
}

public struct AgendaAttachment: Codable, Sendable, Hashable, Identifiable {
    public var id: String { "\(label)|\(url)" }
    public let label: String
    public let url: String

    public init(from decoder: Decoder) throws {
        let values = try decoder.container(keyedBy: CodingKeys.self)
        label = try values.decodeIfPresent(String.self, forKey: .label) ?? "Anlage"
        url = try values.decodeIfPresent(String.self, forKey: .url) ?? ""
    }
}

public struct AgendaItem: Codable, Sendable, Hashable, Identifiable {
    public var id: String { itemNumber }
    public let itemNumber: String
    public let title: String
    public let templateNumber: String?
    public let isPublic: Int
    public let summary: String?
    public let attachments: [AgendaAttachment]
    /// Dringlichkeitsantrag — nachgereicht, nicht in der ursprünglichen
    /// Tagesordnung. Das Web markiert ihn an der Zeile; die App tat es nicht.
    public let isUrgent: Bool

    enum CodingKeys: String, CodingKey {
        case title, summary
        case itemNumber = "item_number"
        case templateNumber = "template_number"
        case isPublic = "is_public"
        // Der Server nennt das Feld `anlagen`. Die App las bis 09/2026
        // `attachments` — ein Name, den es auf der Leitung nie gab, also
        // immer eine leere Liste und nie eine Fehlermeldung. Genau der Fall,
        // vor dem ios/CLAUDE.md warnt; gefunden hat ihn Tim in der App, nicht
        // der Vertragsprüfer (er bindet nur die Typen, die an einer
        // Aufrufstelle stehen — `AgendaItem` hängt unter `SessionDetail`).
        case attachments = "anlagen"
        case isUrgent = "dringlich"
    }

    public init(from decoder: Decoder) throws {
        let values = try decoder.container(keyedBy: CodingKeys.self)
        itemNumber = try values.decodeIfPresent(String.self, forKey: .itemNumber) ?? "TOP"
        title = try values.decodeIfPresent(String.self, forKey: .title) ?? "Tagesordnungspunkt"
        templateNumber = try values.decodeIfPresent(String.self, forKey: .templateNumber)
        isPublic = try values.decodeIfPresent(Int.self, forKey: .isPublic) ?? 1
        summary = try values.decodeIfPresent(String.self, forKey: .summary)
        attachments = try values.decodeIfPresent([AgendaAttachment].self, forKey: .attachments) ?? []
        isUrgent = try values.decodeIfPresent(Bool.self, forKey: .isUrgent) ?? false
    }
}

public struct AgendaChangeLine: Codable, Sendable, Hashable {
    public let kind: String
    public let label: String
    public let title: String
    public let isNonPublic: Bool
    public let detail: String?

    enum CodingKeys: String, CodingKey {
        case label, detail
        case title = "title"
        case kind = "art"
        case isNonPublic = "nichtoeffentlich"
    }

    public init(from decoder: Decoder) throws {
        let values = try decoder.container(keyedBy: CodingKeys.self)
        kind = try values.decodeIfPresent(String.self, forKey: .kind) ?? "changed"
        label = try values.decodeIfPresent(String.self, forKey: .label) ?? "TOP"
        title = try values.decodeIfPresent(String.self, forKey: .title) ?? "Tagesordnung geändert"
        detail = try values.decodeIfPresent(String.self, forKey: .detail)
        if let value = try? values.decode(Bool.self, forKey: .isNonPublic) {
            isNonPublic = value
        } else {
            isNonPublic = (try? values.decode(Int.self, forKey: .isNonPublic)) == 1
        }
    }
}

public struct AgendaChange: Codable, Sendable, Hashable {
    public let changedAt: String
    public let summary: String
    public let lines: [AgendaChangeLine]

    enum CodingKeys: String, CodingKey {
        case summary = "satz"
        case lines = "zeilen"
        case changedAt = "changed_at"
    }

    public init(from decoder: Decoder) throws {
        let values = try decoder.container(keyedBy: CodingKeys.self)
        changedAt = try values.decodeIfPresent(String.self, forKey: .changedAt) ?? ""
        summary = try values.decodeIfPresent(String.self, forKey: .summary) ?? "Tagesordnung geändert"
        lines = try values.decodeIfPresent([AgendaChangeLine].self, forKey: .lines) ?? []
    }
}

public struct SessionDetail: Codable, Sendable {
    public let ksinr: Int
    public let committee: String
    public let sessionDate: String
    public let sessionTime: String?
    public let location: String?
    public let agendaItems: [AgendaItem]
    public let decisions: [DecisionSummary]
    public let hasProtocol: Bool
    public let url: String?
    public let agendaChanges: [AgendaChange]?
    /// Live state from the broadcast (see `LiveState`) — the agenda marks
    /// the running item with it; absent for every other session.
    public let liveState: LiveState?

    enum CodingKeys: String, CodingKey {
        case ksinr, committee, location, decisions, url
        case sessionDate = "session_date"
        case sessionTime = "session_time"
        case agendaItems = "agenda_items"
        case hasProtocol = "has_protocol"
        case agendaChanges = "agenda_changes"
        case liveState = "live_state"
    }
}

public struct TodayCard: Codable, Sendable {
    public let state: String
    public let committee: String?
    public let sessionDate: String?
    public let sessionTime: String?
    public let tops: [String]?
    /// Wie viele Punkte über die genannten hinaus noch auf der Tagesordnung
    /// stehen. Hieß bis #911 `rest`; die App las den alten Namen weiter und
    /// zählte die Punkte deshalb zu niedrig.
    public let remaining: Int?
    public let label: String?
    public let until: String?

    enum CodingKeys: String, CodingKey {
        case state, committee, tops, remaining, label, until
        case sessionDate = "session_date"
        case sessionTime = "session_time"
    }
}

public struct WeekDecision: Codable, Sendable {
    public let found: Bool
    public let decisionID: Int?
    public let title: String?
    public let outcome: String?
    public let committee: String?
    public let sessionDate: String?
    public let interestReason: String?

    enum CodingKeys: String, CodingKey {
        case found, title, outcome, committee
        case decisionID = "decision_id"
        case sessionDate = "session_date"
        case interestReason = "interest_reason"
    }
}

public struct WeekPreview: Codable, Sendable {
    public let found: Bool
    public let from: String
    public let through: String
    public let sessions: [CouncilSession]
    public let items: [WeekPreviewItem]
    public let relevantItemsPerSession: [String: Int]?
    public let additionalItemsPerSession: [String: [WeekPreviewItem]]?
    public let personalMatchesPerSession: [String: Int]?
    public let personalMatches: Int?
    public let contentItemCount: Int?
    public let contentItemsPerSession: [String: Int]?

    enum CodingKeys: String, CodingKey {
        case found
        case from = "from_date"
        case through = "to_date"
        case sessions = "sessions"
        case items = "items"
        case relevantItemsPerSession = "relevant_per_session"
        case additionalItemsPerSession = "further_per_session"
        case personalMatchesPerSession = "matches_per_session"
        case personalMatches = "matches_total"
        case contentItemCount = "substantive_total"
        case contentItemsPerSession = "substantive_per_session"
    }
}

public struct WeekPreviewItem: Codable, Sendable, Identifiable, Hashable {
    public var id: String { "\(sessionID):\(itemNumber)" }
    public let sessionID: Int
    public let itemNumber: String
    public let title: String
    public let shortTitle: String?
    public let summary: String?
    public let committee: String
    public let sessionDate: String
    public let applicant: String?
    public let topicName: String?
    public let impactReason: String?
    public let featured: Bool?

    enum CodingKeys: String, CodingKey {
        case title, summary, committee
        case sessionID = "ksinr"
        case itemNumber = "item_number"
        case shortTitle = "titel_kurz"
        case sessionDate = "session_date"
        case applicant = "applicants"
        case topicName = "topic_name"
        case impactReason = "wichtig_grund"
        case featured = "top"
    }
}

public struct FoundPiece: Codable, Sendable {
    public let found: Bool
    public let kicker: String?
    public let story: String?
    public let decisionID: Int?
    public let title: String?
    public let outcome: String?
    public let committee: String?
    public let sessionDate: String?

    enum CodingKeys: String, CodingKey {
        case found, kicker, story, title, outcome, committee
        case decisionID = "decision_id"
        case sessionDate = "session_date"
    }
}

public struct NotificationSettings: Codable, Sendable {
    public let kinds: [NotificationKind]
    public let limits: NotificationLimits
}

public struct NotificationKind: Codable, Sendable, Identifiable {
    public var id: String { key }
    public let key: String
    public let label: String
    public let hint: String
    public let `default`: Bool
    public let enabled: Bool
    public let parent: String?
}

public struct NotificationLimits: Codable, Sendable {
    public let perDay: Int
    public let quietFrom: Int
    public let quietTo: Int

    enum CodingKeys: String, CodingKey {
        case perDay = "per_day"
        case quietFrom = "quiet_from"
        case quietTo = "quiet_to"
    }
}

public struct ConversationSummary: Codable, Sendable, Identifiable {
    public let id: Int
    public let title: String
    public let updatedAt: String?
    public let turnCount: Int

    public init(id: Int, title: String, updatedAt: String?, turnCount: Int) {
        self.id = id
        self.title = title
        self.updatedAt = updatedAt
        self.turnCount = turnCount
    }

    enum CodingKeys: String, CodingKey {
        case id, title
        case updatedAt = "updated"
        case turnCount = "n_turns"
    }
}

public struct BadgeProgress: Codable, Sendable, Equatable {
    public let current: Int
    public let target: Int
}

public struct BadgeItem: Codable, Sendable, Equatable, Identifiable {
    public let id: String
    public let title: String
    public let hint: String
    public let earned: Bool
    public let progress: BadgeProgress?
}

public struct EarnedBadge: Codable, Sendable, Equatable, Identifiable {
    public let id: String
    public let title: String
}

public struct NextBadge: Codable, Sendable, Equatable, Identifiable {
    public let id: String
    public let title: String
    public let hint: String
}

public struct BadgeSnapshot: Codable, Sendable, Equatable {
    public let badges: [BadgeItem]
    public let earnedCount: Int
    public let total: Int
    public let next: NextBadge?
    public let newlyEarned: [EarnedBadge]

    enum CodingKeys: String, CodingKey {
        case badges, total, next
        case earnedCount = "earned_count"
        case newlyEarned = "newly_earned"
    }
}

public struct AskRound: Codable, Sendable {
    public let question: String
    public let answer: String

    public init(question: String, answer: String) {
        self.question = question
        self.answer = answer
    }
}

public struct AskRequest: Codable, Sendable {
    public let question: String
    public let history: [AskRound]
    public let conversationID: Int?

    enum CodingKeys: String, CodingKey {
        case question, history
        case conversationID = "conversation_id"
    }

    public init(question: String, history: [AskRound] = [], conversationID: Int? = nil) {
        self.question = question
        self.history = history
        self.conversationID = conversationID
    }

    public init(from decoder: Decoder) throws {
        let values = try decoder.container(keyedBy: CodingKeys.self)
        question = try values.decode(String.self, forKey: .question)
        history = try values.decodeIfPresent([AskRound].self, forKey: .history) ?? []
        conversationID = try values.decodeIfPresent(Int.self, forKey: .conversationID)
    }

    public func encode(to encoder: Encoder) throws {
        var values = encoder.container(keyedBy: CodingKeys.self)
        try values.encode(question, forKey: .question)
        try values.encode(history, forKey: .history)
        // Das Backend unterscheidet bewusst zwischen einem alten Client, der
        // `conversation_id` gar nicht kennt, und einem neuen Gespräch (`null`).
        // `encodeIfPresent` würde nil unterschlagen und damit das Speichern
        // des allerersten Turns unbemerkt deaktivieren.
        try values.encode(conversationID, forKey: .conversationID)
    }
}

public struct DeepResearchRequest: Encodable, Sendable {
    public let question: String
    public let conversationID: Int?

    enum CodingKeys: String, CodingKey {
        case question
        case conversationID = "conversation_id"
    }

    public init(question: String, conversationID: Int?) {
        self.question = question
        self.conversationID = conversationID
    }

    public func encode(to encoder: Encoder) throws {
        var values = encoder.container(keyedBy: CodingKeys.self)
        try values.encode(question, forKey: .question)
        // `null` bedeutet auch bei der Recherche: ein neues Gespräch beginnen.
        try values.encode(conversationID, forKey: .conversationID)
    }
}

// MARK: - Neu bei Ratslotse

/// Was `GET /api/news` liefert: die Ausgaben, die dieses Konto noch nicht
/// gesehen hat (neueste zuerst), und wie viele ältere darüber hinaus liegen.
/// **Wer die Karte sieht, entscheidet der Server** — dieselbe Regel wie beim
/// Einrichtungs-Assistenten: Web und App bekommen dieselbe Antwort, statt die
/// Bedingung je Client nachzubauen. Die Medien darin sind bereits die der App
/// (der Client meldet sich mit `X-Client: ios`).
public struct NewsState: Codable, Sendable {
    public let releases: [ReleaseNews]
    public let olderCount: Int
    public let seenVersion: String?

    enum CodingKeys: String, CodingKey {
        case releases
        case olderCount = "older_count"
        case seenVersion = "seen_version"
    }

    public init(releases: [ReleaseNews], olderCount: Int, seenVersion: String?) {
        self.releases = releases
        self.olderCount = olderCount
        self.seenVersion = seenVersion
    }

    public init(from decoder: Decoder) throws {
        let values = try decoder.container(keyedBy: CodingKeys.self)
        releases = try values.decode([ReleaseNews].self, forKey: .releases)
        olderCount = try values.decodeIfPresent(Int.self, forKey: .olderCount) ?? 0
        seenVersion = try values.decodeIfPresent(String.self, forKey: .seenVersion)
    }
}

/// Eine Ausgabe der Karte: Version, Name („Das Teilen-Update") und ihre
/// Highlights, kuratiert in `kern/releases.py`.
public struct ReleaseNews: Codable, Sendable {
    public let version: String
    public let date: String
    public let title: String
    public let highlights: [ReleaseHighlight]

    public init(version: String, date: String, title: String, highlights: [ReleaseHighlight]) {
        self.version = version
        self.date = date
        self.title = title
        self.highlights = highlights
    }
}

extension ReleaseNews: Identifiable {
    public var id: String { version }
}

/// Ein Highlight: Titel, Satz, Ziel in der App — und die Aufnahme dazu. Ohne
/// Aufnahme (`media` null) fällt die Karte auf die Listenform zurück; die
/// Registry verlangt je Ausgabe alle oder keines.
public struct ReleaseHighlight: Codable, Sendable {
    public let title: String
    public let text: String
    public let url: String
    public let media: ReleaseMedia?

    enum CodingKeys: String, CodingKey {
        case title, text, url, media
    }

    public init(title: String, text: String, url: String, media: ReleaseMedia?) {
        self.title = title
        self.text = text
        self.url = url
        self.media = media
    }

    public init(from decoder: Decoder) throws {
        let values = try decoder.container(keyedBy: CodingKeys.self)
        title = try values.decode(String.self, forKey: .title)
        text = try values.decode(String.self, forKey: .text)
        url = try values.decode(String.self, forKey: .url)
        media = try values.decodeIfPresent(ReleaseMedia.self, forKey: .media)
    }
}

extension ReleaseHighlight: Identifiable {
    public var id: String { url + "#" + title }
}

/// Bild oder Clip eines Highlights. `src` und `poster` sind Pfade auf dem
/// Server (`/neuigkeiten/<version>/…`), `aspect` ein CSS-Verhältnis wie
/// „16/9" oder „1206/2622" — im Browser querformatige Fenster, in der App das
/// ganze Telefon. Alle Medien einer Ausgabe teilen sich eines.
public struct ReleaseMedia: Codable, Sendable, Equatable {
    public let kind: String
    public let src: String
    public let alt: String
    public let aspect: String
    public let poster: String?

    enum CodingKeys: String, CodingKey {
        case kind, src, alt, aspect, poster
    }

    public init(kind: String, src: String, alt: String, aspect: String, poster: String?) {
        self.kind = kind
        self.src = src
        self.alt = alt
        self.aspect = aspect
        self.poster = poster
    }

    public init(from decoder: Decoder) throws {
        let values = try decoder.container(keyedBy: CodingKeys.self)
        kind = try values.decode(String.self, forKey: .kind)
        src = try values.decode(String.self, forKey: .src)
        alt = try values.decode(String.self, forKey: .alt)
        aspect = try values.decodeIfPresent(String.self, forKey: .aspect) ?? "16/9"
        poster = try values.decodeIfPresent(String.self, forKey: .poster)
    }
}

extension ReleaseMedia {
    public var isVideo: Bool { kind == "video" }

    /// Breite durch Höhe aus „16/9"; nil, wenn der Wert unlesbar ist.
    public var aspectRatio: Double? {
        let parts = aspect.split(separator: "/").compactMap { Double($0.trimmingCharacters(in: .whitespaces)) }
        guard parts.count == 2, parts[1] > 0 else { return nil }
        return parts[0] / parts[1]
    }
}
