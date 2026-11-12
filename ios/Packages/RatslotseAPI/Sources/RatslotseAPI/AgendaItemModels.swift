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
    /// „Aus den Unterlagen" mit Belegen (Schalter `aus-den-unterlagen`).
    public let dossier: Dossier?
    /// Gelesene Anträge (Schalter `aenderungsantraege`).
    public let amendments: [Amendment]?

    enum CodingKeys: String, CodingKey {
        case ksinr, committee, item, history, documents, dossier, amendments
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
        /// Gegenlese-Liste: Nummer wie in den Belegen, Art, Antragsteller, Seiten.
        public let listNo: Int?
        public let docType: String?
        public let applicants: [String]?
        public let pages: Int?
        public let isScan: Bool?
        public let afterSession: Bool?
        public var id: String { url }

        enum CodingKeys: String, CodingKey {
            case kind, label, url, date, applicants, pages
            case listNo = "list_no"
            case docType = "doc_type"
            case isScan = "is_scan"
            case afterSession = "after_session"
        }
    }

    /// Eine belegte Aussage: Satz, wörtliches Zitat, Dokument, Seite, PDF-Sprung.
    public struct Statement: Decodable, Sendable, Identifiable, Hashable {
        public let text: String
        public let quote: String
        public let page: Int?
        public let kind: String?
        public let listNo: Int?
        public let docLabel: String?
        public let url: String?
        public var id: String { "\(text)|\(quote.prefix(40))" }

        enum CodingKeys: String, CodingKey {
            case text, quote, page, kind, url
            case listNo = "list_no"
            case docLabel = "doc_label"
        }
    }

    public struct Dossier: Decodable, Sendable {
        public let form: String?
        public let createdAt: String?
        public let sections: [Section]
        public let documentsRead: Int?

        enum CodingKeys: String, CodingKey {
            case form, sections
            case createdAt = "created_at"
            case documentsRead = "documents_read"
        }

        public struct Section: Decodable, Sendable, Identifiable {
            public let key: String
            public let title: String
            public let status: String?
            public let statements: [Statement]
            public var id: String { key }
        }
    }

    public struct Amendment: Decodable, Sendable, Identifiable {
        public let documentId: Int
        public let listNo: Int
        public let label: String
        public let url: String
        public let applicants: [String]
        public let read: Bool
        public let outcome: String?
        public let target: String?
        public let pattern: String?
        public let before: Quote?
        public let after: Quote?
        public let diff: [[String]]?
        public let meaning: Quote?
        public let reason: Quote?
        public var id: Int { documentId }

        /// Aussage am Antrag: Satz, Zitat, Seite — die Nummer trägt der Antrag selbst.
        public struct Quote: Decodable, Sendable {
            public let text: String
            public let quote: String
            public let page: Int?
        }

        enum CodingKeys: String, CodingKey {
            case label, url, applicants, read, outcome, target, pattern, before, after, diff, meaning, reason
            case documentId = "document_id"
            case listNo = "list_no"
        }
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
