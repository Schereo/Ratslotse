import Foundation

public struct AppConfiguration: Codable, Sendable, Equatable {
    public let minBuild: Int
    public let notice: String?

    enum CodingKeys: String, CodingKey {
        case minBuild = "min_build"
        case notice = "hinweis"
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
    public let role: String
    public let status: String
    public let deliveryChannel: String
    public let emailVerified: Bool
    public let appleLinked: Bool
    public let hasPassword: Bool
    public let accessToken: String?
    public let displayName: String?
    public let savesConversations: Int?

    public var isActive: Bool { status == "active" && emailVerified }
    public var isAdmin: Bool { role == "admin" }

    enum CodingKeys: String, CodingKey {
        case id, email, role, status
        case deliveryChannel = "delivery_channel"
        case emailVerified = "email_verified"
        case appleLinked = "apple_linked"
        case hasPassword = "has_password"
        case accessToken = "access_token"
        case displayName = "display_name"
        case savesConversations = "qa_speichern"
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

    enum CodingKeys: String, CodingKey {
        case id, name, description, matched
        case createdAt = "created_at"
        case decisionCount = "decision_count"
        case decisionCountCapped = "decision_count_capped"
        case lastHitID = "last_hit_id"
        case lastHitTitle = "last_hit_title"
        case lastHitDate = "last_hit_date"
        case unreadCount = "unread_count"
    }
}

public struct DecisionSummary: Codable, Sendable, Hashable, Identifiable {
    public let id: Int
    public let title: String
    public let summary: String?
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
    public let placeName: String?
    public let latitude: Double?
    public let longitude: Double?

    enum CodingKeys: String, CodingKey {
        case id, title, summary, committee, outcome, kind, vote, factions
        case placeName = "ort_name"
        case latitude = "lat"
        case longitude = "lon"
        case sessionID = "ksinr"
        case templateNumber = "vorlage_nr"
        case noVotes = "gegenstimmen"
        case abstentions = "enthaltungen"
        case sessionDate = "session_date"
        case policyField = "policy_field"
        case itemNumber = "item_number"
    }

    public init(from decoder: Decoder) throws {
        let values = try decoder.container(keyedBy: CodingKeys.self)
        id = try values.decode(Int.self, forKey: .id)
        title = try values.decodeIfPresent(String.self, forKey: .title) ?? "Beschluss"
        summary = try values.decodeIfPresent(String.self, forKey: .summary)
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
        placeName = try values.decodeIfPresent(String.self, forKey: .placeName)
        latitude = try values.decodeIfPresent(Double.self, forKey: .latitude)
        longitude = try values.decodeIfPresent(Double.self, forKey: .longitude)
    }
}

public struct DecisionPage: Codable, Sendable {
    public let total: Int
    public let decisions: [DecisionSummary]
}

public struct DecisionDetail: Codable, Sendable {
    public let decision: DecisionSummary
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

    enum CodingKeys: String, CodingKey {
        case decision, similar, participation = "beteiligung", follow
        case subVotes = "sub_votes"
        case templateJourney = "vorlage_journey"
        case consultations = "beratungsfolge"
        case templateURL = "vorlage_url"
        case template = "vorlage"
        case attachments = "anlagen"
        case importance = "importance_breakdown"
        case presentParties = "present_parties"
        case ratsinfoURL = "ratsinfo_url"
    }

    public init(
        decision: DecisionSummary,
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
        follow: FollowStatus?
    ) {
        self.decision = decision
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
    }

    public init(from decoder: Decoder) throws {
        let values = try decoder.container(keyedBy: CodingKeys.self)
        decision = try values.decode(DecisionSummary.self, forKey: .decision)
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
    }
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
        case date = "datum"
        case committee = "gremium"
        case itemNumber = "top"
        case result = "ergebnis"
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
        case title, excerpt
        case number = "vorlage_nr"
        case kind = "art"
        case documentURL = "document_url"
        case pageCount = "n_pages"
        case department = "amt"
        case climateCheck = "klima_check"
        case financialCheck = "finanz_check"
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
        case isMotion = "is_antrag"
        case applicants = "antragsteller"
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
    public let title: String
    public let step: String?
    public let from: String?
    public let until: String?
    public let url: String
    public let status: String?

    enum CodingKeys: String, CodingKey {
        case title = "titel"
        case step = "schritt"
        case from = "von"
        case until = "bis"
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

public struct DistrictOption: Codable, Sendable, Hashable, Identifiable {
    public var id: String { placeID }
    public let placeID: String
    public let name: String
    public let kindLabel: String
    public let count: Int

    enum CodingKeys: String, CodingKey {
        case name, count
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
    public let templateNumber: String
    public let title: String
    public let url: String
    public let stationCount: Int
    public let next: CouncilConsultationStop?
    public let last: CouncilConsultationStop?

    enum CodingKeys: String, CodingKey {
        case id, title, url
        case templateID = "kvonr"
        case templateNumber = "vorlage_nr"
        case stationCount = "n_stationen"
        case next = "naechste"
        case last = "letzte"
    }
}

public struct FollowPage: Codable, Sendable {
    public let follows: [FollowEntry]
}

public struct CouncilSession: Codable, Sendable, Hashable, Identifiable {
    public var id: Int { ksinr ?? calendarID ?? title.hashValue }
    public let ksinr: Int?
    public let calendarID: Int?
    public let committee: String
    public let sessionDate: String
    public let sessionTime: String?
    public let location: String?
    public let title: String
    public let myTopicItems: [JSONValue]?

    enum CodingKeys: String, CodingKey {
        case ksinr, committee, location, title
        case calendarID = "calendar_id"
        case sessionDate = "session_date"
        case sessionTime = "session_time"
        case myTopicItems = "my_topic_items"
    }

    public init(from decoder: Decoder) throws {
        let values = try decoder.container(keyedBy: CodingKeys.self)
        ksinr = try values.decodeIfPresent(Int.self, forKey: .ksinr)
        calendarID = try values.decodeIfPresent(Int.self, forKey: .calendarID)
        committee = try values.decodeIfPresent(String.self, forKey: .committee) ?? "Gremium"
        sessionDate = try values.decodeIfPresent(String.self, forKey: .sessionDate) ?? ""
        sessionTime = try values.decodeIfPresent(String.self, forKey: .sessionTime)
        location = try values.decodeIfPresent(String.self, forKey: .location)
        title = try values.decodeIfPresent(String.self, forKey: .title) ?? committee
        myTopicItems = try values.decodeIfPresent([JSONValue].self, forKey: .myTopicItems)
    }
}

public struct SessionPage: Codable, Sendable {
    public let count: Int
    public let total: Int
    public let sessions: [CouncilSession]
}

public struct AgendaItem: Codable, Sendable, Hashable, Identifiable {
    public var id: String { itemNumber }
    public let itemNumber: String
    public let title: String
    public let templateNumber: String?
    public let isPublic: Int
    public let summary: String?

    enum CodingKeys: String, CodingKey {
        case title, summary
        case itemNumber = "item_number"
        case templateNumber = "vorlage_nr"
        case isPublic = "is_public"
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

    enum CodingKeys: String, CodingKey {
        case ksinr, committee, location, decisions, url
        case sessionDate = "session_date"
        case sessionTime = "session_time"
        case agendaItems = "agenda_items"
        case hasProtocol = "has_protocol"
    }
}

public struct TodayCard: Codable, Sendable {
    public let state: String
    public let committee: String?
    public let sessionDate: String?
    public let sessionTime: String?
    public let tops: [String]?
    public let rest: Int?
    public let label: String?
    public let until: String?

    enum CodingKeys: String, CodingKey {
        case state, committee, tops, rest, label, until
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
    public let personalMatches: Int?

    enum CodingKeys: String, CodingKey {
        case found
        case from = "von"
        case through = "bis"
        case sessions = "sitzungen"
        case items = "punkte"
        case personalMatches = "treffer_gesamt"
    }
}

public struct WeekPreviewItem: Codable, Sendable, Identifiable {
    public var id: String { "\(sessionID):\(itemNumber)" }
    public let sessionID: Int
    public let itemNumber: String
    public let title: String
    public let shortTitle: String?
    public let summary: String?
    public let committee: String
    public let sessionDate: String
    public let topicName: String?
    public let impactReason: String?
    public let featured: Bool?

    enum CodingKeys: String, CodingKey {
        case title, summary, committee
        case sessionID = "ksinr"
        case itemNumber = "item_number"
        case shortTitle = "titel_kurz"
        case sessionDate = "session_date"
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

    enum CodingKeys: String, CodingKey {
        case id
        case title = "titel"
        case updatedAt = "updated"
        case turnCount = "n_turns"
    }
}

public struct AskRound: Codable, Sendable {
    public let frage: String
    public let antwort: String

    public init(frage: String, antwort: String) {
        self.frage = frage
        self.antwort = antwort
    }
}

public struct AskRequest: Codable, Sendable {
    public let question: String
    public let verlauf: [AskRound]
    public let gespraechID: Int?

    enum CodingKeys: String, CodingKey {
        case question, verlauf
        case gespraechID = "gespraech_id"
    }

    public init(question: String, verlauf: [AskRound] = [], gespraechID: Int? = nil) {
        self.question = question
        self.verlauf = verlauf
        self.gespraechID = gespraechID
    }
}
