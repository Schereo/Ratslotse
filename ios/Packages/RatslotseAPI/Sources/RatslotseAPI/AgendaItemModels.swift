import Foundation

/// Ein Tagesordnungspunkt auf seiner eigenen Seite
/// (`GET /api/council/session/{ksinr}/item?nr=`, Form `SessionItemDetail`).
/// Nur die Felder, die die App zeigt; nullbare Felder des Vertrags sind optional.
public struct AgendaItemDetail: Decodable, Sendable {
    public let ksinr: Int
    public let committee: String
    public let sessionDate: String
    public let item: Row
    public let courseItem: Course
    public let decisionId: Int?
    public let history: [Station]
    public let documents: [Document]
    /// Was die Vorlage trägt, ohne Modell (Plan Vorlagen aufbereiten, Stufe 0).
    /// Optional: Ältere Server liefern das Feld nicht.
    public let templateFields: TemplateFields?

    enum CodingKeys: String, CodingKey {
        case ksinr, committee, item, history, documents
        case sessionDate = "session_date"
        case courseItem = "course_item"
        case decisionId = "decision_id"
        case templateFields = "template_fields"
    }

    public struct Row: Decodable, Sendable {
        public let itemNumber: String
        public let title: String
        public let templateNumber: String?
        public let summary: String?
        /// Der Kartentext: kennt Vorlage UND Anlagen, `summary` nur den Titel.
        public let socialText: String?

        enum CodingKeys: String, CodingKey {
            case title, summary
            case itemNumber = "item_number"
            case templateNumber = "template_number"
            case socialText = "social_text"
        }
    }

    public struct Course: Decodable, Sendable {
        public let shortTitle: String
        public let typeLabel: String?
        public let applicant: String?
        public let important: Bool?
        public let importantReason: String?

        enum CodingKeys: String, CodingKey {
            case applicant, important
            case shortTitle = "short_title"
            case typeLabel = "type_label"
            case importantReason = "important_reason"
        }
    }

    public struct Station: Decodable, Sendable, Identifiable {
        public let ksinr: Int
        public let committee: String
        public let sessionDate: String
        public let itemNumber: String
        public let outcome: String?
        public let text: String?
        public let decisionId: Int?
        public let current: Bool
        public var id: String { "\(ksinr)|\(itemNumber)" }

        enum CodingKeys: String, CodingKey {
            case ksinr, committee, outcome, text, current
            case sessionDate = "session_date"
            case itemNumber = "item_number"
            case decisionId = "decision_id"
        }
    }

    public struct Document: Decodable, Sendable, Identifiable {
        public let kind: String
        public let label: String
        public let url: String
        public let date: String?
        public var id: String { url }
    }

    public struct TemplateFields: Decodable, Sendable {
        public let templateNumber: String?
        public let documentUrl: String?
        public let office: String?
        public let proposedDecision: String?
        public let cost: Cost?
        public let climate: Climate?
        public let motions: [Motion]

        enum CodingKeys: String, CodingKey {
            case office, cost, climate, motions
            case templateNumber = "template_number"
            case documentUrl = "document_url"
            case proposedDecision = "proposed_decision"
        }

        public struct Cost: Decodable, Sendable {
            public let text: String
            /// `amount` · `none` · `text` — als String, damit ein neuer Wert nicht den Decode kippt.
            public let status: String
        }

        public struct Climate: Decodable, Sendable {
            public let text: String
            public let relevant: Bool?
        }

        public struct Motion: Decodable, Sendable, Identifiable {
            public let label: String
            public let applicants: [String]
            public let url: String?
            public var id: String { url ?? label }
        }
    }
}
