import Foundation

public struct AppConfiguration: Codable, Sendable, Equatable {
    public let minBuild: Int
    public let notice: String?

    enum CodingKeys: String, CodingKey {
        case minBuild = "min_build"
        case notice = "note"
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
        case savesConversations = "saves_conversations"
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
    public let hits30Days: Int

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
        case hits30Days = "hits_30d"
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
        hits30Days = try values.decodeIfPresent(Int.self, forKey: .hits30Days) ?? 0
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
        case decision, attendance, entities, similar, participation = "beteiligung", follow
        case subVotes = "sub_votes"
        case templateJourney = "vorlage_journey"
        case consultations = "beratungsfolge"
        case templateURL = "vorlage_url"
        case template = "vorlage"
        case attachments = "attachments"
        case importance = "importance_breakdown"
        case presentParties = "present_parties"
        case ratsinfoURL = "ratsinfo_url"
        case planImageID = "plan_bild"
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
    public let title: String
    public let step: String?
    public let from: String?
    public let until: String?
    public let url: String
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
    public let templateNumber: String
    public let title: String
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

public struct CouncilSession: Codable, Sendable, Hashable, Identifiable {
    public var id: Int { ksinr ?? calendarID ?? title.hashValue }
    public let ksinr: Int?
    public let calendarID: Int?
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
    public let location: String?
    public let title: String
    public let itemCount: Int
    public let myTopicItems: [JSONValue]?

    enum CodingKeys: String, CodingKey {
        case ksinr, committee, location, title
        case calendarID = "calendar_id"
        case sessionDate = "session_date"
        case sessionTime = "session_time"
        case liveUntil = "live_until"
        case itemCount = "n_items"
        case myTopicItems = "my_topic_items"
    }

    public init(from decoder: Decoder) throws {
        let values = try decoder.container(keyedBy: CodingKeys.self)
        ksinr = try values.decodeIfPresent(Int.self, forKey: .ksinr)
        calendarID = try values.decodeIfPresent(Int.self, forKey: .calendarID)
        committee = try values.decodeIfPresent(String.self, forKey: .committee) ?? "Gremium"
        sessionDate = try values.decodeIfPresent(String.self, forKey: .sessionDate) ?? ""
        sessionTime = try values.decodeIfPresent(String.self, forKey: .sessionTime)
        liveUntil = try values.decodeIfPresent(String.self, forKey: .liveUntil)
        location = try values.decodeIfPresent(String.self, forKey: .location)
        title = try values.decodeIfPresent(String.self, forKey: .title) ?? committee
        itemCount = try values.decodeIfPresent(Int.self, forKey: .itemCount) ?? 0
        myTopicItems = try values.decodeIfPresent([JSONValue].self, forKey: .myTopicItems)
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

    enum CodingKeys: String, CodingKey {
        case title, summary
        case itemNumber = "item_number"
        case templateNumber = "template_number"
        case isPublic = "is_public"
        case attachments = "attachments"
    }

    public init(from decoder: Decoder) throws {
        let values = try decoder.container(keyedBy: CodingKeys.self)
        itemNumber = try values.decodeIfPresent(String.self, forKey: .itemNumber) ?? "TOP"
        title = try values.decodeIfPresent(String.self, forKey: .title) ?? "Tagesordnungspunkt"
        templateNumber = try values.decodeIfPresent(String.self, forKey: .templateNumber)
        isPublic = try values.decodeIfPresent(Int.self, forKey: .isPublic) ?? 1
        summary = try values.decodeIfPresent(String.self, forKey: .summary)
        attachments = try values.decodeIfPresent([AgendaAttachment].self, forKey: .attachments) ?? []
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

    enum CodingKeys: String, CodingKey {
        case ksinr, committee, location, decisions, url
        case sessionDate = "session_date"
        case sessionTime = "session_time"
        case agendaItems = "agenda_items"
        case hasProtocol = "has_protocol"
        case agendaChanges = "aenderungen"
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

public struct WeekPreviewItem: Codable, Sendable, Identifiable {
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
