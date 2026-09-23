import Foundation

// `GET /api/wahlabend/karte` — das Wahlergebnis je Urnenbezirk für die
// Stadtkarte (docs/plan-viertel-wahlkarte.md). Gerechnet hat der Server: wer
// vorn lag, wie deutlich, in welchen Ortsbereichen ein Bezirk liegt. Die App
// zeichnet nur.
//
// Alles gehärtet (`decodeIfPresent` mit Vorgabe): Die Ebene ist eine Zugabe
// zur Karte — ein fehlendes Feld darf sie leer lassen, nie die Karte kippen.

public struct ElectionMapChoice: Codable, Sendable, Hashable, Identifiable {
    public var id: String { slug }
    public let slug: String
    public let label: String
    public let kind: String
    public let date: String

    public init(slug: String, label: String, kind: String, date: String) {
        self.slug = slug; self.label = label; self.kind = kind; self.date = date
    }
}

public struct ElectionMapContestant: Codable, Sendable, Hashable, Identifiable {
    public var id: String { slug }
    public let slug: String
    public let short: String
    public let name: String
    public let color: String
    public let colorDark: String

    enum CodingKeys: String, CodingKey {
        case slug, short, name, color
        case colorDark = "color_dark"
    }

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        slug = try c.decode(String.self, forKey: .slug)
        short = try c.decodeIfPresent(String.self, forKey: .short) ?? slug
        name = try c.decodeIfPresent(String.self, forKey: .name) ?? short
        color = try c.decodeIfPresent(String.self, forKey: .color) ?? "#64748b"
        colorDark = try c.decodeIfPresent(String.self, forKey: .colorDark) ?? color
    }
}

public struct ElectionMapShare: Codable, Sendable, Hashable {
    public let slug: String
    public let votes: Int?
    public let sharePct: Double?

    enum CodingKeys: String, CodingKey {
        case slug, votes
        case sharePct = "share_pct"
    }
}

public struct ElectionMapPlace: Codable, Sendable, Hashable {
    public let name: String
    public let share: Double
}

public struct ElectionMapDistrict: Codable, Sendable, Hashable, Identifiable {
    public var id: Int { number }
    public let number: Int
    public let name: String
    public let area: Int
    public let counted: Bool
    public let leader: String?
    public let runnerUp: String?
    public let marginPct: Double?
    public let turnoutPct: Double?
    public let validVotes: Int?
    public let places: [ElectionMapPlace]
    public let parties: [ElectionMapShare]

    enum CodingKeys: String, CodingKey {
        case number, name, area, counted, leader, places, parties
        case runnerUp = "runner_up"
        case marginPct = "margin_pct"
        case turnoutPct = "turnout_pct"
        case validVotes = "valid_votes"
    }

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        number = try c.decode(Int.self, forKey: .number)
        name = try c.decodeIfPresent(String.self, forKey: .name) ?? "Wahlbezirk \(number)"
        area = try c.decodeIfPresent(Int.self, forKey: .area) ?? number / 100
        counted = try c.decodeIfPresent(Bool.self, forKey: .counted) ?? false
        leader = try c.decodeIfPresent(String.self, forKey: .leader)
        runnerUp = try c.decodeIfPresent(String.self, forKey: .runnerUp)
        marginPct = try c.decodeIfPresent(Double.self, forKey: .marginPct)
        turnoutPct = try c.decodeIfPresent(Double.self, forKey: .turnoutPct)
        validVotes = try c.decodeIfPresent(Int.self, forKey: .validVotes)
        places = try c.decodeIfPresent([ElectionMapPlace].self, forKey: .places) ?? []
        parties = try c.decodeIfPresent([ElectionMapShare].self, forKey: .parties) ?? []
    }

    /// Wie viel der Fläche im Ortsbereich liegt (0…1).
    public func share(in place: String) -> Double {
        places.first { $0.name == place }?.share ?? 0
    }
}

public struct ElectionMapArea: Codable, Sendable, Hashable, Identifiable {
    public var id: Int { number }
    public let number: Int
    public let roman: String
    public let counted: Int
    public let total: Int
    public let validVotes: Int?
    public let leader: String?
    public let parties: [ElectionMapShare]

    enum CodingKeys: String, CodingKey {
        case number, roman, counted, total, leader, parties
        case validVotes = "valid_votes"
    }

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        number = try c.decode(Int.self, forKey: .number)
        roman = try c.decodeIfPresent(String.self, forKey: .roman) ?? "\(number)"
        counted = try c.decodeIfPresent(Int.self, forKey: .counted) ?? 0
        total = try c.decodeIfPresent(Int.self, forKey: .total) ?? 0
        validVotes = try c.decodeIfPresent(Int.self, forKey: .validVotes)
        leader = try c.decodeIfPresent(String.self, forKey: .leader)
        parties = try c.decodeIfPresent([ElectionMapShare].self, forKey: .parties) ?? []
    }
}

public struct ElectionMapWin: Codable, Sendable, Hashable {
    public let slug: String
    public let districts: Int
}

public struct ElectionMap: Codable, Sendable {
    public let election: ElectionMapChoice
    public let elections: [ElectionMapChoice]
    public let phase: String
    public let contestants: [ElectionMapContestant]
    public let postalSharePct: Double?
    public let total: Int
    public let counted: Int
    public let wins: [ElectionMapWin]
    public let ties: Int
    public let place: String?
    public let districts: [ElectionMapDistrict]
    public let areas: [ElectionMapArea]

    enum CodingKeys: String, CodingKey {
        case election, elections, phase, contestants, total, counted, wins, ties, place, districts, areas
        case postalSharePct = "postal_share_pct"
    }

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        election = try c.decode(ElectionMapChoice.self, forKey: .election)
        elections = try c.decodeIfPresent([ElectionMapChoice].self, forKey: .elections) ?? [election]
        phase = try c.decodeIfPresent(String.self, forKey: .phase) ?? "complete"
        contestants = try c.decodeIfPresent([ElectionMapContestant].self, forKey: .contestants) ?? []
        postalSharePct = try c.decodeIfPresent(Double.self, forKey: .postalSharePct)
        total = try c.decodeIfPresent(Int.self, forKey: .total) ?? 0
        counted = try c.decodeIfPresent(Int.self, forKey: .counted) ?? 0
        wins = try c.decodeIfPresent([ElectionMapWin].self, forKey: .wins) ?? []
        ties = try c.decodeIfPresent(Int.self, forKey: .ties) ?? 0
        place = try c.decodeIfPresent(String.self, forKey: .place)
        districts = try c.decodeIfPresent([ElectionMapDistrict].self, forKey: .districts) ?? []
        areas = try c.decodeIfPresent([ElectionMapArea].self, forKey: .areas) ?? []
    }

    public func contestant(_ slug: String?) -> ElectionMapContestant? {
        guard let slug else { return nil }
        return contestants.first { $0.slug == slug }
    }

    /// Die Bezirke, die einen Ortsbereich berühren — größter Anteil zuerst.
    public func districts(in place: String) -> [ElectionMapDistrict] {
        districts
            .filter { $0.share(in: place) > 0 }
            .sorted { ($0.share(in: place), -$0.number) > ($1.share(in: place), -$1.number) }
    }

    /// Die Deckkraft einer Bezirksfläche aus dem Vorsprung — dieselbe Formel
    /// wie im Web (`lib/wahlkarte.ts::deckkraft`): ab 20 Punkten satt.
    public static func opacity(margin: Double?) -> Double {
        guard let margin else { return 0 }
        return 0.15 + 0.6 * min(1, max(0, margin) / 20)
    }
}
