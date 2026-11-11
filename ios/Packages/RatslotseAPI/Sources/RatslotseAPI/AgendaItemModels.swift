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

    enum CodingKeys: String, CodingKey {
        case ksinr, committee, item, history, documents
        case sessionDate = "session_date"
        case courseItem = "course_item"
        case decisionId = "decision_id"
    }

    public struct Row: Decodable, Sendable {
        public let itemNumber: String
        public let title: String
        public let templateNumber: String?
        public let summary: String?

        enum CodingKeys: String, CodingKey {
            case title, summary
            case itemNumber = "item_number"
            case templateNumber = "template_number"
        }
    }

    public struct Course: Decodable, Sendable {
        public let shortTitle: String
        public let typeLabel: String?
        public let applicant: String?

        enum CodingKeys: String, CodingKey {
            case applicant
            case shortTitle = "short_title"
            case typeLabel = "type_label"
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
}
