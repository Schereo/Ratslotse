import MapKit
import RatslotseAPI
import RatslotseDesign
import SafariServices
import SwiftUI

enum PublicProfileKind: String {
    case person
    case topic = "thema"
    case place = "ort"
}

struct PublicProfileView: View {
    let model: AppModel
    let kind: PublicProfileKind
    let key: String
    @Environment(\.horizontalSizeClass) private var horizontalSizeClass
    @State private var preview: LinkPreview?
    @State private var payload: JSONValue?
    @State private var decisions: [DecisionSummary] = []
    @State private var coordinate: CLLocationCoordinate2D?
    @State private var person: PublicPersonProfile?
    @State private var topicDetail: TopicProfileDetail?
    @State private var placeDetail: PlaceProfileDetail?
    @State private var error: String?

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                if let preview {
                    profileOverview(preview)

                    if let topicDetail {
                        TopicProfileMetadata(model: model, detail: topicDetail)
                    }

                    if let placeDetail {
                        PlaceProfileMetadata(model: model, detail: placeDetail)
                    }

                    if !decisions.isEmpty {
                        VStack(alignment: .leading, spacing: 13) {
                            MonoKicker("Beschlüsse", trailing: "\(decisions.count) gezeigt")
                            ForEach(decisions) { decision in
                                Button { model.navigation.append(.decision(id: decision.id)) } label: {
                                    DecisionRow(decision: decision)
                                }
                                .buttonStyle(.plain)
                                if decision.id != decisions.last?.id { Divider().overlay(RatsColor.separator) }
                            }
                        }
                        .ratsCard()
                    }

                    if let link = model.router.universalLink(for: route) {
                        ShareLink(item: link) { Label("Profil teilen", systemImage: "square.and.arrow.up") }
                            .buttonStyle(SecondaryButtonStyle())
                    }
                } else if let error {
                    ErrorCard(message: error) { Task { await load() } }
                } else {
                    ProgressView("Profil laden …").frame(maxWidth: .infinity, minHeight: 260)
                }
            }
            .frame(maxWidth: usesWidePersonLayout ? 1120 : usesTabletOverview ? 1040 : 760, alignment: .leading)
            .padding(18)
        }
        .background(RatsColor.page)
        .navigationTitle(kicker.capitalized)
        .navigationBarTitleDisplayMode(.inline)
        .task {
            await load()
            if kind == .place { await model.reportBadgeEvent("map_place", key: key) }
        }
    }

    @ViewBuilder
    private func profileOverview(_ preview: LinkPreview) -> some View {
        if usesTabletOverview {
            HStack(alignment: .top, spacing: 20) {
                profileIntro(preview)
                    .frame(maxWidth: .infinity, alignment: .topLeading)
                tabletVisual(preview)
                    .frame(maxWidth: .infinity, alignment: .topLeading)
            }
        } else {
            profileIntro(preview)
            if let coordinate {
                profileMap(title: preview.title, coordinate: coordinate, height: 250)
            }
        }
    }

    private func profileIntro(_ preview: LinkPreview) -> some View {
        VStack(alignment: .leading, spacing: 14) {
            if let person {
                PersonProfileOverview(
                    model: model,
                    person: person,
                    usesWideLayout: usesWidePersonLayout
                )
            } else {
                MonoKicker(kicker)
                Text(preview.title)
                    .font(RatsFont.title(usesTabletOverview ? 34 : 28))
                if kind == .topic && !usesTabletOverview {
                    HStack(alignment: .center, spacing: 12) {
                        Lotti3DView(scene: .reading, animated: false)
                            .frame(width: 78, height: 72)
                            .accessibilityHidden(true)
                        profileDescriptionText(preview)
                    }
                    .ratsCard()
                } else {
                    profileDescriptionText(preview)
                        .ratsCard()
                }
            }
        }
    }

    private func profileDescriptionText(_ preview: LinkPreview) -> some View {
        Text(profileDescription ?? preview.description)
            .font(RatsFont.body(16))
            .foregroundStyle(RatsColor.bodyText)
            .lineSpacing(4)
            .frame(maxWidth: .infinity, alignment: .leading)
    }

    @ViewBuilder
    private func tabletVisual(_ preview: LinkPreview) -> some View {
        if let coordinate {
            profileMap(title: preview.title, coordinate: coordinate, height: 300)
        } else {
            VStack(alignment: .leading, spacing: 8) {
                Lotti3DView(scene: .explain, animated: false)
                    .frame(maxWidth: .infinity, minHeight: 180, maxHeight: 230)
                    .accessibilityHidden(true)
                MonoKicker("Lotti erklärt")
                Text("Hier bündelt Ratslotse Beschlüsse, Projekte und Debatten, die zu diesem Thema gehören.")
                    .font(RatsFont.body(14))
                    .foregroundStyle(RatsColor.secondary)
                    .lineSpacing(3)
            }
            .ratsCard()
        }
    }

    private func profileMap(
        title: String,
        coordinate: CLLocationCoordinate2D,
        height: CGFloat
    ) -> some View {
        Map(initialPosition: .region(MKCoordinateRegion(
            center: coordinate,
            span: MKCoordinateSpan(latitudeDelta: 0.025, longitudeDelta: 0.025)
        ))) {
            Marker(title, coordinate: coordinate)
                .tint(RatsColor.signal)
        }
        .frame(height: height)
        .clipShape(RoundedRectangle(cornerRadius: RatsRadius.card))
        .overlay(RoundedRectangle(cornerRadius: RatsRadius.card).stroke(RatsColor.border))
    }

    private var usesTabletOverview: Bool {
        guard UIDevice.current.userInterfaceIdiom == .pad,
              horizontalSizeClass != .compact else { return false }
        switch kind {
        case .person: return false
        case .topic, .place: return true
        }
    }

    private var usesWidePersonLayout: Bool {
        kind == .person && UIDevice.current.userInterfaceIdiom == .pad && horizontalSizeClass != .compact
    }

    private var kicker: String {
        switch kind { case .person: "Person"; case .topic: "Thema im Rat"; case .place: "Ort in Oldenburg" }
    }

    private var route: AppRoute {
        switch kind { case .person: .person(slug: key); case .topic: .topic(slug: key); case .place: .place(id: key) }
    }

    private func load() async {
#if DEBUG
        if ProcessInfo.processInfo.environment["RATSLOTSE_DEBUG_PROFILE_FIXTURE"] == "1" {
            switch kind {
            case .person:
                preview = LinkPreview(
                    title: "Anne Beispiel",
                    description: "Ratsmitglied mit Schwerpunkten in Verkehr, Bildung und sozialer Teilhabe."
                )
                person = PublicPersonProfile(
                    name: "Anne Beispiel",
                    slug: "anne-beispiel",
                    type: "rat",
                    party: "SPD",
                    currentAffiliation: .init(
                        label: "SPD-Fraktion",
                        kind: "fraktion",
                        parties: ["SPD"]
                    ),
                    art: "rat",
                    organisation: nil,
                    nSessions: 18,
                    activeFrom: "2021-11-01",
                    activeTo: nil,
                    factionTimeline: [
                        .init(label: "SPD-Fraktion", kind: "partei", parties: ["SPD"], first: "2021-11-01", last: "2026-08-28", n: 18),
                    ],
                    ris: .init(kpenr: 42, name: "Anne Beispiel", currentFaction: "SPD-Fraktion", memberships: [
                        .init(kgrnr: 1, committee: "Verkehrsausschuss", role: "Vorsitzende", from: "2021-11-01", until: nil),
                        .init(kgrnr: 2, committee: "Sozialausschuss", role: "Mitglied", from: "2023-03-01", until: nil),
                        .init(kgrnr: 3, committee: "Schulausschuss", role: "Mitglied", from: "2018-01-01", until: "2021-10-31"),
                    ]),
                    committees: [
                        .init(committee: "Verkehrsausschuss", n: 9, chair: true),
                        .init(committee: "Sozialausschuss", n: 7, chair: false),
                    ],
                    recent: [
                        .init(ksinr: 8101, committee: "Verkehrsausschuss", sessionDate: "2026-08-28"),
                        .init(ksinr: 8102, committee: "Sozialausschuss", sessionDate: "2026-08-21"),
                    ],
                    speeches: [
                        .init(kind: "rede", agendaItem: "Fahrradstraßen in Oldenburg", text: "Anne Beispiel hebt hervor, dass sichere Schulwege und durchgehende Radverbindungen gemeinsam geplant werden müssen.", committee: "Verkehrsausschuss", sessionDate: "2026-08-28"),
                        .init(kind: "anfrage", agendaItem: "Ganztagsbetreuung", text: "Sie fragt nach dem Zeitplan für zusätzliche Betreuungsplätze und der Beteiligung der Schulen.", committee: "Sozialausschuss", sessionDate: "2026-08-21"),
                    ],
                    speechCount: 24,
                    speechCommittees: [
                        .init(committee: "Verkehrsausschuss", n: 15),
                        .init(committee: "Sozialausschuss", n: 9),
                    ],
                    administrationRole: nil,
                    isActive: nil,
                    mentionedFrom: nil,
                    mentionedUntil: nil
                )
            case .topic:
                preview = LinkPreview(
                    title: "Sichere Schulwege",
                    description: "Beschlüsse, Projekte und Debatten rund um sichere Wege zu Oldenburgs Schulen."
                )
                topicDetail = try? JSONDecoder().decode(TopicProfileDetail.self, from: Data(#"""
                {
                  "money": 1850000,
                  "parties": ["SPD", "GRÜNE", "CDU", "Volt"],
                  "fields": [
                    {"field": "verkehr", "n": 17},
                    {"field": "bildung", "n": 9},
                    {"field": "stadtplanung", "n": 6}
                  ],
                  "field_labels": {
                    "verkehr": "Verkehr & Mobilität",
                    "bildung": "Schule & Bildung",
                    "stadtplanung": "Stadtplanung"
                  },
                  "related": [
                    {"slug": "radverkehr", "name": "Radverkehr", "kind": "thema", "rel_type": "belegt", "evidence": 12},
                    {"slug": "grundschulen", "name": "Grundschulen", "kind": "thema", "rel_type": "belegt", "evidence": 7},
                    {"slug": "verkehrssicherheit", "name": "Verkehrssicherheit", "kind": "thema", "rel_type": "aehnlich", "evidence": 0}
                  ]
                }
                """#.utf8))
            case .place:
                preview = LinkPreview(
                    title: "Pferdemarkt",
                    description: "Was der Rat für den Pferdemarkt und sein direktes Umfeld plant und entscheidet."
                )
                coordinate = CLLocationCoordinate2D(latitude: 53.1466, longitude: 8.2147)
                placeDetail = try? JSONDecoder().decode(PlaceProfileDetail.self, from: Data(#"""
                {
                  "place": {
                    "id": "pferdemarkt",
                    "name": "Pferdemarkt",
                    "kind_label": "Platz",
                    "parents": [{"id": "innenstadt", "name": "Innenstadt", "kind": "Stadtteil"}],
                    "sources": [{"id": "stadtplan", "title": "Stadtplan Oldenburg", "url": "https://www.oldenburg.de/"}]
                  },
                  "children": [
                    {"id": "pferdemarkt-haltestelle", "name": "ZOB Pferdemarkt", "kind": "Haltestelle"},
                    {"id": "pferdemarkt-parkplatz", "name": "Parkplatz Pferdemarkt", "kind": "Verkehrsfläche"}
                  ],
                  "decision_count": 14
                }
                """#.utf8))
            }
            return
        }
#endif
        do {
            async let previewRequest: LinkPreview = model.api.get("/api/council/preview/\(kind.rawValue)/\(key)")
            async let payloadRequest: JSONValue = model.api.get(detailPath)
            let (newPreview, newPayload) = try await (previewRequest, payloadRequest)
            preview = newPreview
            payload = newPayload
            decisions = extractDecisions(from: newPayload)
            coordinate = extractCoordinate(from: newPayload)
            person = kind == .person ? try? newPayload.decoded(PublicPersonProfile.self) : nil
            topicDetail = kind == .topic ? try? newPayload.decoded(TopicProfileDetail.self) : nil
            placeDetail = kind == .place ? try? newPayload.decoded(PlaceProfileDetail.self) : nil
        } catch { self.error = error.localizedDescription }
    }

    private var profileDescription: String? {
        guard kind == .topic else { return nil }
        return payload?.object?["description"]?.string
    }

    private var detailPath: String {
        switch kind {
        case .person: "/api/council/person/\(key)"
        case .topic: "/api/council/entity/\(key)"
        case .place: "/api/council/place/\(key)"
        }
    }

    private func extractDecisions(from payload: JSONValue) -> [DecisionSummary] {
        guard let object = payload.object else { return [] }
        let candidates = ["decisions", "recent_decisions", "beschluesse"]
        for key in candidates {
            if let rows = object[key]?.array {
                return rows.compactMap { try? $0.decoded(DecisionSummary.self) }
            }
        }
        return []
    }

    private func extractCoordinate(from payload: JSONValue) -> CLLocationCoordinate2D? {
        guard let root = payload.object else { return nil }
        let geo: [String: JSONValue]
        switch kind {
        case .place: geo = root["place"]?.object ?? root
        case .topic: geo = root["geo"]?.object ?? [:]
        case .person: return nil
        }
        guard case .number(let lat)? = geo["lat"], case .number(let lon)? = geo["lon"] else { return nil }
        return CLLocationCoordinate2D(latitude: lat, longitude: lon)
    }
}

private struct TopicProfileDetail: Decodable, Sendable {
    struct Field: Decodable, Sendable, Identifiable {
        var id: String { field }
        let field: String
        let n: Int
    }

    struct Related: Decodable, Sendable, Identifiable {
        var id: String { slug }
        let slug: String
        let name: String
        let kind: String
        let relType: String
        let evidence: Int

        enum CodingKeys: String, CodingKey {
            case slug, name, kind, evidence
            case relType = "rel_type"
        }
    }

    let money: Double
    let parties: [String]
    let fields: [Field]
    let fieldLabels: [String: String]
    let related: [Related]

    enum CodingKeys: String, CodingKey {
        case money, parties, fields, related
        case fieldLabels = "field_labels"
    }

    init(from decoder: Decoder) throws {
        let values = try decoder.container(keyedBy: CodingKeys.self)
        money = try values.decodeIfPresent(Double.self, forKey: .money) ?? 0
        parties = try values.decodeIfPresent([String].self, forKey: .parties) ?? []
        fields = try values.decodeIfPresent([Field].self, forKey: .fields) ?? []
        fieldLabels = try values.decodeIfPresent([String: String].self, forKey: .fieldLabels) ?? [:]
        related = try values.decodeIfPresent([Related].self, forKey: .related) ?? []
    }
}

private struct PlaceProfileDetail: Decodable, Sendable {
    struct Place: Decodable, Sendable {
        struct Relative: Decodable, Sendable, Identifiable {
            let id: String
            let name: String
            let kind: String
        }

        struct Source: Decodable, Sendable, Identifiable {
            let id: String
            let title: String
            let url: String
        }

        let id: String
        let name: String
        let kindLabel: String
        let parents: [Relative]
        let sources: [Source]

        enum CodingKeys: String, CodingKey {
            case id, name, parents, sources
            case kindLabel = "kind_label"
        }
    }

    let place: Place
    let children: [Place.Relative]
    let decisionCount: Int

    enum CodingKeys: String, CodingKey {
        case place, children
        case decisionCount = "decision_count"
    }
}

private struct TopicProfileMetadata: View {
    let model: AppModel
    let detail: TopicProfileDetail

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            if detail.money > 0 || !detail.fields.isEmpty {
                ViewThatFits(in: .horizontal) {
                    HStack(alignment: .top, spacing: 12) { facts }
                    VStack(alignment: .leading, spacing: 12) { facts }
                }
            }

            if !detail.parties.isEmpty {
                VStack(alignment: .leading, spacing: 8) {
                    MonoKicker("Beteiligte Fraktionen", trailing: "\(detail.parties.count)")
                    LazyVGrid(
                        columns: [GridItem(.adaptive(minimum: 86), spacing: 7)],
                        alignment: .leading,
                        spacing: 7
                    ) {
                        ForEach(detail.parties, id: \.self) { ProfilePartyChip(party: $0) }
                    }
                }
                .ratsCard()
            }

            let proven = detail.related.filter { $0.relType == "belegt" }
            let similar = detail.related.filter { $0.relType != "belegt" }
            if !proven.isEmpty || !similar.isEmpty {
                VStack(alignment: .leading, spacing: 13) {
                    relatedRow("Hängt zusammen mit", detail: "gemeinsam behandelt", entries: proven, showsEvidence: true)
                    relatedRow("Thematisch ähnlich", detail: "inhaltlich verwandt", entries: similar, showsEvidence: false)
                }
                .ratsCard()
            }
        }
    }

    @ViewBuilder
    private var facts: some View {
        if detail.money > 0 {
            VStack(alignment: .leading, spacing: 5) {
                MonoKicker("Erkanntes Finanzvolumen")
                Text(formatProfileAmount(detail.money))
                    .font(RatsFont.title(24))
                    .foregroundStyle(RatsColor.success)
                Text("Automatisch aus den Beschlusstexten erkannt.")
                    .font(RatsFont.body(10.5))
                    .foregroundStyle(RatsColor.muted)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .ratsCard()
        }
        if !detail.fields.isEmpty {
            VStack(alignment: .leading, spacing: 8) {
                MonoKicker("Themenfelder")
                ForEach(detail.fields.prefix(6)) { field in
                    HStack(spacing: 8) {
                        Circle().fill(RatsColor.primary).frame(width: 6, height: 6)
                        Text(detail.fieldLabels[field.field] ?? field.field)
                            .font(RatsFont.body(12.5, weight: .medium))
                        Spacer()
                        Text("\(field.n)").font(RatsFont.mono(10)).foregroundStyle(RatsColor.muted)
                    }
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .ratsCard()
        }
    }

    @ViewBuilder
    private func relatedRow(
        _ title: String,
        detail: String,
        entries: [TopicProfileDetail.Related],
        showsEvidence: Bool
    ) -> some View {
        if !entries.isEmpty {
            VStack(alignment: .leading, spacing: 7) {
                Text("\(title) · \(detail)")
                    .font(RatsFont.body(12, weight: .semibold))
                    .foregroundStyle(RatsColor.secondary)
                LazyVGrid(
                    columns: [GridItem(.adaptive(minimum: 145), spacing: 7)],
                    alignment: .leading,
                    spacing: 7
                ) {
                    ForEach(entries) { entry in
                        Button { model.navigation.append(.topic(slug: entry.slug)) } label: {
                            HStack(spacing: 7) {
                                Image(systemName: "point.3.filled.connected.trianglepath.dotted")
                                    .font(.caption)
                                Text(entry.name).lineLimit(2)
                                Spacer(minLength: 0)
                                if showsEvidence {
                                    Text("\(entry.evidence)")
                                        .font(RatsFont.mono(9))
                                        .foregroundStyle(RatsColor.muted)
                                }
                            }
                            .font(RatsFont.body(11.5, weight: .medium))
                            .foregroundStyle(RatsColor.bodyText)
                            .padding(.horizontal, 10)
                            .frame(maxWidth: .infinity, minHeight: 38, alignment: .leading)
                            .background(RatsColor.stage)
                            .overlay(RoundedRectangle(cornerRadius: 10).stroke(RatsColor.border))
                            .clipShape(RoundedRectangle(cornerRadius: 10))
                        }
                        .buttonStyle(.plain)
                    }
                }
            }
        }
    }
}

private struct PlaceProfileMetadata: View {
    let model: AppModel
    let detail: PlaceProfileDetail

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack(spacing: 10) {
                Image(systemName: "mappin.and.ellipse")
                    .foregroundStyle(RatsColor.primary)
                VStack(alignment: .leading, spacing: 2) {
                    MonoKicker(detail.place.kindLabel)
                    Text("\(detail.decisionCount) \(detail.decisionCount == 1 ? "Beschluss" : "Beschlüsse") mit belegtem Ortsbezug")
                        .font(RatsFont.body(12.5, weight: .medium))
                }
            }
            .ratsCard()

            if !detail.place.parents.isEmpty || !detail.children.isEmpty {
                VStack(alignment: .leading, spacing: 13) {
                    placeLinks("Gehört zu", entries: detail.place.parents)
                    placeLinks("Orte in diesem Bereich", entries: detail.children)
                }
                .ratsCard()
            }

            ViewThatFits(in: .horizontal) {
                HStack(spacing: 9) { actions }
                VStack(spacing: 9) { actions }
            }

            if !detail.place.sources.isEmpty {
                VStack(alignment: .leading, spacing: 9) {
                    MonoKicker("Stammdaten-Quellen")
                    ForEach(detail.place.sources) { source in
                        if let url = URL(string: source.url) {
                            Link(destination: url) {
                                HStack(spacing: 8) {
                                    Image(systemName: "doc.text")
                                    Text(source.title)
                                    Spacer()
                                    Image(systemName: "arrow.up.right")
                                        .font(.caption)
                                }
                                .font(RatsFont.body(12, weight: .medium))
                                .foregroundStyle(RatsColor.primary)
                            }
                        }
                    }
                }
                .ratsCard()
            }
        }
    }

    @ViewBuilder
    private var actions: some View {
        Button {
            model.questionPrefill = "Was wurde zu \(detail.place.name) beschlossen?"
            model.navigation.removeAll()
            model.selectedTab = .questions
        } label: {
            Label("Lotti dazu fragen", systemImage: "sparkles")
                .frame(maxWidth: .infinity)
        }
        .buttonStyle(PrimaryButtonStyle())

        Button {
            model.navigation.removeAll()
            model.councilSection = .map
            model.selectedTab = .council
        } label: {
            Label("Auf der Stadtkarte", systemImage: "map")
                .frame(maxWidth: .infinity)
        }
        .buttonStyle(SecondaryButtonStyle())
    }

    @ViewBuilder
    private func placeLinks(_ title: String, entries: [PlaceProfileDetail.Place.Relative]) -> some View {
        if !entries.isEmpty {
            VStack(alignment: .leading, spacing: 7) {
                MonoKicker(title)
                LazyVGrid(
                    columns: [GridItem(.adaptive(minimum: 145), spacing: 7)],
                    alignment: .leading,
                    spacing: 7
                ) {
                    ForEach(entries) { entry in
                        Button { model.navigation.append(.place(id: entry.id)) } label: {
                            VStack(alignment: .leading, spacing: 2) {
                                Text(entry.name)
                                    .font(RatsFont.body(12, weight: .semibold))
                                    .foregroundStyle(RatsColor.text)
                                Text(entry.kind)
                                    .font(RatsFont.body(9.5))
                                    .foregroundStyle(RatsColor.muted)
                            }
                            .frame(maxWidth: .infinity, minHeight: 40, alignment: .leading)
                            .padding(.horizontal, 10)
                            .background(RatsColor.stage)
                            .overlay(RoundedRectangle(cornerRadius: 10).stroke(RatsColor.border))
                            .clipShape(RoundedRectangle(cornerRadius: 10))
                        }
                        .buttonStyle(.plain)
                    }
                }
            }
        }
    }
}

private struct ProfilePartyChip: View {
    let party: String

    var body: some View {
        HStack(spacing: 6) {
            Circle().fill(color).frame(width: 8, height: 8)
            Text(party)
                .font(RatsFont.body(10.5, weight: .semibold))
                .lineLimit(1)
        }
        .foregroundStyle(RatsColor.bodyText)
        .padding(.horizontal, 9)
        .padding(.vertical, 6)
        .background(color.opacity(0.11))
        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
    }

    private var color: Color {
        let value = party.lowercased()
        if value.contains("spd") { return Color(red: 0.82, green: 0.10, blue: 0.15) }
        if value.contains("cdu") { return RatsColor.bodyText }
        if value.contains("grün") { return Color(red: 0.18, green: 0.55, blue: 0.25) }
        if value.contains("fdp") { return Color(red: 0.93, green: 0.71, blue: 0.08) }
        if value.contains("link") { return Color(red: 0.72, green: 0.10, blue: 0.43) }
        if value.contains("volt") { return Color(red: 0.42, green: 0.17, blue: 0.62) }
        return RatsColor.primary
    }
}

private func formatProfileAmount(_ value: Double) -> String {
    if value >= 1_000_000 {
        return "\((value / 1_000_000).formatted(.number.precision(.fractionLength(0...1)))) Mio. €"
    }
    if value >= 1_000 { return "\((value / 1_000).formatted(.number.precision(.fractionLength(0)))) Tsd. €" }
    return value.formatted(.currency(code: "EUR").precision(.fractionLength(0)))
}

private struct LinkPreview: Codable, Sendable {
    let title: String
    let description: String
}

struct PublicPersonProfile: Codable, Sendable {
    struct Affiliation: Codable, Sendable {
        let label: String
        let kind: String?
        let parties: [String]

        init(label: String, kind: String? = nil, parties: [String] = []) {
            self.label = label
            self.kind = kind
            self.parties = parties
        }

        init(from decoder: Decoder) throws {
            let singleValue = try decoder.singleValueContainer()
            if let label = try? singleValue.decode(String.self) {
                self.init(label: label)
                return
            }

            let object = try decoder.container(keyedBy: CodingKeys.self)
            self.init(
                label: try object.decode(String.self, forKey: .label),
                kind: try object.decodeIfPresent(String.self, forKey: .kind),
                parties: try object.decodeIfPresent([String].self, forKey: .parties) ?? []
            )
        }

        private enum CodingKeys: String, CodingKey {
            case label, kind, parties
        }
    }

    struct Committee: Codable, Sendable, Identifiable {
        var id: String { committee }
        let committee: String
        let n: Int
        let chair: Bool
    }

    struct RecentSession: Codable, Sendable, Identifiable {
        var id: Int { ksinr }
        let ksinr: Int
        let committee: String
        let sessionDate: String

        enum CodingKeys: String, CodingKey {
            case ksinr, committee
            case sessionDate = "session_date"
        }
    }

    struct FactionPhase: Codable, Sendable, Identifiable {
        var id: String { "\(label)-\(first)" }
        let label: String
        let kind: String
        let parties: [String]
        let first: String
        let last: String
        let n: Int
    }

    struct RISProfile: Codable, Sendable {
        struct Membership: Codable, Sendable, Identifiable {
            var id: String { "\(committee)-\(from ?? "")-\(until ?? "")" }
            let kgrnr: Int?
            let committee: String
            let role: String?
            let from: String?
            let until: String?

            enum CodingKeys: String, CodingKey {
                case kgrnr
                case committee = "gremium"
                case role = "rolle"
                case from = "von"
                case until = "bis"
            }
        }

        let kpenr: Int
        let name: String
        let currentFaction: String?
        let memberships: [Membership]

        enum CodingKeys: String, CodingKey {
            case kpenr, name, memberships
            case currentFaction = "fraktion_aktuell"
        }
    }

    struct Speech: Codable, Sendable, Identifiable {
        var id: String { "\(sessionDate)-\(agendaItem ?? "")-\(text.prefix(24))" }
        let kind: String
        let agendaItem: String?
        let text: String
        let committee: String?
        let sessionDate: String

        enum CodingKeys: String, CodingKey {
            case text, committee
            case kind = "art"
            case agendaItem = "top"
            case sessionDate = "session_date"
        }
    }

    struct SpeechCommittee: Codable, Sendable, Identifiable {
        var id: String { committee }
        let committee: String
        let n: Int
    }

    let name: String
    let slug: String
    let type: String
    let party: String?
    let currentAffiliation: Affiliation?
    let art: String?
    let organisation: String?
    let nSessions: Int
    let activeFrom: String?
    let activeTo: String?
    let factionTimeline: [FactionPhase]
    let ris: RISProfile?
    let committees: [Committee]
    let recent: [RecentSession]
    let speeches: [Speech]
    let speechCount: Int
    let speechCommittees: [SpeechCommittee]
    let administrationRole: String?
    let isActive: Bool?
    let mentionedFrom: String?
    let mentionedUntil: String?

    enum CodingKeys: String, CodingKey {
        case name, slug, party, art, organisation, committees, recent, ris
        case type = "typ"
        case currentAffiliation = "current_affiliation"
        case nSessions = "n_sessions"
        case activeFrom = "active_from"
        case activeTo = "active_to"
        case factionTimeline = "faction_timeline"
        case speeches = "wortbeitraege"
        case speechCount = "wortbeitraege_gesamt"
        case speechCommittees = "wortbeitraege_gremien"
        case administrationRole = "rolle"
        case isActive = "aktiv"
        case mentionedFrom = "von"
        case mentionedUntil = "bis"
    }

    init(
        name: String,
        slug: String,
        type: String,
        party: String?,
        currentAffiliation: Affiliation?,
        art: String?,
        organisation: String?,
        nSessions: Int,
        activeFrom: String?,
        activeTo: String?,
        factionTimeline: [FactionPhase],
        ris: RISProfile?,
        committees: [Committee],
        recent: [RecentSession],
        speeches: [Speech],
        speechCount: Int,
        speechCommittees: [SpeechCommittee],
        administrationRole: String?,
        isActive: Bool?,
        mentionedFrom: String?,
        mentionedUntil: String?
    ) {
        self.name = name
        self.slug = slug
        self.type = type
        self.party = party
        self.currentAffiliation = currentAffiliation
        self.art = art
        self.organisation = organisation
        self.nSessions = nSessions
        self.activeFrom = activeFrom
        self.activeTo = activeTo
        self.factionTimeline = factionTimeline
        self.ris = ris
        self.committees = committees
        self.recent = recent
        self.speeches = speeches
        self.speechCount = speechCount
        self.speechCommittees = speechCommittees
        self.administrationRole = administrationRole
        self.isActive = isActive
        self.mentionedFrom = mentionedFrom
        self.mentionedUntil = mentionedUntil
    }

    init(from decoder: Decoder) throws {
        let values = try decoder.container(keyedBy: CodingKeys.self)
        name = try values.decode(String.self, forKey: .name)
        slug = try values.decodeIfPresent(String.self, forKey: .slug) ?? ""
        type = try values.decodeIfPresent(String.self, forKey: .type) ?? "rat"
        party = try values.decodeIfPresent(String.self, forKey: .party)
        currentAffiliation = try values.decodeIfPresent(Affiliation.self, forKey: .currentAffiliation)
        art = try values.decodeIfPresent(String.self, forKey: .art)
        organisation = try values.decodeIfPresent(String.self, forKey: .organisation)
        nSessions = try values.decodeIfPresent(Int.self, forKey: .nSessions) ?? 0
        activeFrom = try values.decodeIfPresent(String.self, forKey: .activeFrom)
        activeTo = try values.decodeIfPresent(String.self, forKey: .activeTo)
        factionTimeline = try values.decodeIfPresent([FactionPhase].self, forKey: .factionTimeline) ?? []
        ris = try values.decodeIfPresent(RISProfile.self, forKey: .ris)
        committees = try values.decodeIfPresent([Committee].self, forKey: .committees) ?? []
        recent = try values.decodeIfPresent([RecentSession].self, forKey: .recent) ?? []
        speeches = try values.decodeIfPresent([Speech].self, forKey: .speeches) ?? []
        speechCount = try values.decodeIfPresent(Int.self, forKey: .speechCount) ?? speeches.count
        speechCommittees = try values.decodeIfPresent([SpeechCommittee].self, forKey: .speechCommittees) ?? []
        administrationRole = try values.decodeIfPresent(String.self, forKey: .administrationRole)
        isActive = try values.decodeIfPresent(Bool.self, forKey: .isActive)
        mentionedFrom = try values.decodeIfPresent(String.self, forKey: .mentionedFrom)
        mentionedUntil = try values.decodeIfPresent(String.self, forKey: .mentionedUntil)
    }

    var roleLabel: String {
        if type == "verwaltung" { return administrationRole ?? "Stadtverwaltung" }
        return switch art {
        case "rat": "Ratsmitglied"
        case "beratend": "Beratendes Mitglied"
        case "verwaltung": "Stadtverwaltung"
        default: "Person im Oldenburger Rat"
        }
    }

    var affiliation: String? {
        if type == "verwaltung" { return "Stadt Oldenburg" }
        return [currentAffiliation?.label, party, organisation]
            .compactMap { $0?.trimmingCharacters(in: .whitespacesAndNewlines) }
            .first { !$0.isEmpty }
    }
}

private struct PersonProfileOverview: View {
    let model: AppModel
    let person: PublicPersonProfile
    let usesWideLayout: Bool
    @State private var speeches: [PublicPersonProfile.Speech]
    @State private var selectedCommittee = ""
    @State private var totalSpeeches: Int
    @State private var isLoadingSpeeches = false
    @State private var speechError: String?
    @State private var showsPastOffices = false
    @State private var showsMethodology = false

    init(model: AppModel, person: PublicPersonProfile, usesWideLayout: Bool) {
        self.model = model
        self.person = person
        self.usesWideLayout = usesWideLayout
        _speeches = State(initialValue: person.speeches)
        _totalSpeeches = State(initialValue: person.speechCount)
    }

    @ViewBuilder
    var body: some View {
        if usesWideLayout {
            HStack(alignment: .top, spacing: 20) {
                VStack(alignment: .leading, spacing: 16) {
                    hero
                    officesCard
                    affiliationTimeline
                }
                .frame(maxWidth: 430, alignment: .topLeading)

                VStack(alignment: .leading, spacing: 16) {
                    presenceChart
                    speechesCard
                    recentSessionsCard
                }
                .frame(maxWidth: .infinity, alignment: .topLeading)
            }
        } else {
            hero
            officesCard
            affiliationTimeline
            presenceChart
            speechesCard
            recentSessionsCard
        }
    }

    private var hero: some View {
        VStack(alignment: .leading, spacing: 18) {
            HStack(alignment: .top, spacing: 15) {
                Text(initials)
                    .font(RatsFont.title(21))
                    .foregroundStyle(partyForeground)
                    .frame(width: 64, height: 64)
                    .background(partyColor)
                    .clipShape(Circle())
                    .overlay(Circle().stroke(Color.white.opacity(0.48), lineWidth: 1))
                    .shadow(color: partyColor.opacity(0.20), radius: 10, y: 4)

                VStack(alignment: .leading, spacing: 6) {
                    Text(person.name)
                        .font(RatsFont.title(28))
                        .foregroundStyle(RatsColor.text)
                        .fixedSize(horizontal: false, vertical: true)
                    Text(person.roleLabel)
                        .font(RatsFont.body(14, weight: .semibold))
                        .foregroundStyle(RatsColor.bodyText)
                    if let affiliation = person.affiliation {
                        partyBadge(affiliation, parties: person.currentAffiliation?.parties ?? [person.party].compactMap { $0 })
                    }
                }
                Spacer(minLength: 0)
                Button { showsMethodology = true } label: {
                    Image(systemName: "info")
                        .font(.system(size: 13, weight: .bold))
                        .foregroundStyle(partyColor)
                        .frame(width: 36, height: 36)
                        .background(RatsColor.card.opacity(0.82))
                        .clipShape(Circle())
                        .overlay(Circle().stroke(partyColor.opacity(0.22)))
                }
                .buttonStyle(.plain)
                .accessibilityLabel("Wie wird dieses Profil erfasst?")
                .popover(isPresented: $showsMethodology) {
                    methodologyPopover
                        .presentationCompactAdaptation(.popover)
                }
            }

            if let period {
                Label(period, systemImage: "calendar.badge.clock")
                    .font(RatsFont.mono(10))
                    .foregroundStyle(RatsColor.secondary)
            }

            if person.type != "verwaltung" {
                HStack(spacing: 0) {
                    metric(value: person.nSessions, label: "Sitzungen")
                    metricDivider
                    metric(value: person.committees.count, label: "Gremien")
                    let chaired = person.committees.filter(\.chair).count
                    metricDivider
                    metric(value: chaired, label: chaired == 1 ? "Vorsitz" : "Vorsitze")
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(20)
        .background(
            LinearGradient(
                colors: [partyColor.opacity(0.18), RatsColor.card, RatsColor.card],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
        )
        .overlay(alignment: .top) { Rectangle().fill(partyColor).frame(height: 5) }
        .overlay(RoundedRectangle(cornerRadius: RatsRadius.card).stroke(partyColor.opacity(0.30)))
        .clipShape(RoundedRectangle(cornerRadius: RatsRadius.card, style: .continuous))
    }

    @ViewBuilder
    private var officesCard: some View {
        let current = person.ris?.memberships.filter { $0.until == nil } ?? []
        let past = person.ris?.memberships.filter { $0.until != nil } ?? []
        if !current.isEmpty || !past.isEmpty {
            RatsSectionPanel("Ämter im Rat", detail: "Offizielle Mitgliedschaften im Zeitverlauf", symbol: "building.columns") {
                if !current.isEmpty {
                    VStack(spacing: 13) {
                        ForEach(current) { membership in
                            officeTimelineRow(membership)
                        }
                    }
                }

                if !past.isEmpty {
                    DisclosureGroup(isExpanded: $showsPastOffices) {
                        VStack(spacing: 10) {
                            ForEach(past) { membership in pastOfficeRow(membership) }
                        }
                        .padding(.top, 10)
                    } label: {
                        Text("Frühere Ämter · \(past.count)")
                            .font(RatsFont.body(13, weight: .semibold))
                            .foregroundStyle(RatsColor.bodyText)
                    }
                    .tint(partyColor)
                }
            }
        }
    }

    @ViewBuilder
    private var affiliationTimeline: some View {
        if !person.factionTimeline.isEmpty {
            RatsSectionPanel("Zugehörigkeit im Zeitverlauf", detail: "Fraktion, Gruppe oder parteilos – so, wie es die Protokolle zur jeweiligen Zeit führen.", symbol: "point.3.connected.trianglepath.dotted") {
                VStack(alignment: .leading, spacing: 10) {
                    ForEach(Array(person.factionTimeline.enumerated()), id: \.element.id) { index, phase in
                        HStack(alignment: .top, spacing: 10) {
                            VStack(spacing: 0) {
                                Circle().fill(color(for: phase.label)).frame(width: 12, height: 12)
                                if index < person.factionTimeline.count - 1 {
                                    Rectangle().fill(RatsColor.border).frame(width: 2, height: 42)
                                }
                            }
                            VStack(alignment: .leading, spacing: 4) {
                                partyBadge(phase.label, parties: phase.parties)
                                Text("\(year(phase.first)) – \(year(phase.last)) · \(phase.n) Sitzungen")
                                    .font(RatsFont.mono(9.5))
                                    .foregroundStyle(RatsColor.muted)
                            }
                        }
                    }
                }
            }
        }
    }

    @ViewBuilder
    private var presenceChart: some View {
        if !person.committees.isEmpty {
            let maximum = max(1, person.committees.map(\.n).max() ?? 1)
            RatsSectionPanel("Präsenz je Gremium", detail: "Besuchte Sitzungen im Vergleich", symbol: "chart.bar.xaxis") {
                VStack(spacing: 14) {
                    ForEach(person.committees) { committee in
                        VStack(alignment: .leading, spacing: 6) {
                            HStack(alignment: .firstTextBaseline, spacing: 8) {
                                Text(shortCommittee(committee.committee))
                                    .font(RatsFont.body(13, weight: .semibold))
                                    .lineLimit(2)
                                if committee.chair {
                                    Label("Vorsitz", systemImage: "gavel")
                                        .font(RatsFont.body(9.5, weight: .semibold))
                                        .foregroundStyle(RatsColor.signal)
                                }
                                Spacer()
                                Text("\(committee.n)").font(RatsFont.mono(10)).foregroundStyle(RatsColor.secondary)
                            }
                            GeometryReader { proxy in
                                ZStack(alignment: .leading) {
                                    Capsule().fill(RatsColor.stage)
                                    Capsule()
                                        .fill(LinearGradient(colors: [partyColor, partyColor.opacity(0.58)], startPoint: .leading, endPoint: .trailing))
                                        .frame(width: max(10, proxy.size.width * CGFloat(committee.n) / CGFloat(maximum)))
                                }
                            }
                            .frame(height: 9)
                            .accessibilityLabel("\(committee.committee): \(committee.n) besuchte Sitzungen")
                        }
                    }
                }
            }
        }
    }

    @ViewBuilder
    private var speechesCard: some View {
        if person.speechCount > 0 || !speeches.isEmpty {
            RatsSectionPanel("Aus den Protokollen", detail: "Sinngemäß zusammengefasste Wortbeiträge – direkt aus den Niederschriften.", symbol: "quote.bubble") {
                if person.speechCommittees.count > 1 {
                    Menu {
                        Button("Alle Gremien (\(person.speechCount))") { selectSpeechCommittee("") }
                        ForEach(person.speechCommittees) { entry in
                            Button("\(shortCommittee(entry.committee)) (\(entry.n))") { selectSpeechCommittee(entry.committee) }
                        }
                    } label: {
                        HStack {
                            Image(systemName: "line.3.horizontal.decrease")
                            Text(selectedCommittee.isEmpty ? "Alle Gremien" : shortCommittee(selectedCommittee))
                                .lineLimit(1)
                            Spacer()
                            Image(systemName: "chevron.up.chevron.down")
                        }
                        .font(RatsFont.body(12, weight: .semibold))
                        .foregroundStyle(RatsColor.bodyText)
                        .padding(.horizontal, 12)
                        .frame(minHeight: 40)
                        .background(RatsColor.stage)
                        .clipShape(RoundedRectangle(cornerRadius: 11))
                    }
                }

                VStack(spacing: 0) {
                    ForEach(Array(speeches.enumerated()), id: \.element.id) { index, speech in
                        speechRow(speech)
                        if index < speeches.count - 1 { Divider().overlay(RatsColor.separator) }
                    }
                }

                if isLoadingSpeeches {
                    ProgressView().frame(maxWidth: .infinity).padding(.vertical, 8)
                } else if speeches.count < totalSpeeches {
                    Button { Task { await loadSpeeches(reset: false) } } label: {
                        Text("Mehr anzeigen · noch \(totalSpeeches - speeches.count)")
                            .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(SecondaryButtonStyle())
                }
                if let speechError {
                    Text(speechError).font(RatsFont.body(11)).foregroundStyle(RatsColor.danger)
                }
                Text("Niederschriften sind Verlaufsprotokolle: Nicht jede Wortmeldung wird erfasst.")
                    .font(RatsFont.body(10.5))
                    .foregroundStyle(RatsColor.muted)
                    .lineSpacing(2)
            }
        }
    }

    @ViewBuilder
    private var recentSessionsCard: some View {
        if !person.recent.isEmpty {
            RatsSectionPanel("Zuletzt anwesend", detail: "Die jüngsten protokollierten Teilnahmen", symbol: "clock.arrow.circlepath") {
                ForEach(person.recent.prefix(5)) { session in
                    Button {
                        model.navigation.append(.sessions(ksinr: session.ksinr, tops: []))
                    } label: {
                        HStack {
                            VStack(alignment: .leading, spacing: 3) {
                                Text(session.committee)
                                    .font(RatsFont.body(14, weight: .semibold))
                                Text(RatsDate.short(session.sessionDate) ?? session.sessionDate)
                                    .font(RatsFont.mono(10))
                                    .foregroundStyle(RatsColor.muted)
                            }
                            Spacer()
                            Image(systemName: "chevron.right")
                                .font(.caption)
                                .foregroundStyle(RatsColor.muted)
                        }
                    }
                    .buttonStyle(.plain)
                    if session.id != person.recent.prefix(5).last?.id { Divider().overlay(RatsColor.separator) }
                }
            }
        }
    }

    private var period: String? {
        if person.type == "verwaltung" {
            switch (person.mentionedFrom, person.mentionedUntil, person.isActive) {
            case let (start?, _, true): return "In Protokollen erwähnt seit \(start)"
            case let (start?, end?, _): return "In Protokollen erwähnt \(start)–\(end)"
            default: return nil
            }
        }
        let start = person.activeFrom.flatMap(RatsDate.short)
        let end = person.activeTo.flatMap(RatsDate.short)
        return switch (start, end) {
        case let (start?, end?): "Aktiv: \(start) – \(end)"
        case let (start?, nil): "Aktiv seit \(start)"
        default: nil
        }
    }

    private func metric(value: Int, label: String) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text("\(value)").font(RatsFont.title(22))
            Text(label).font(RatsFont.mono(9)).foregroundStyle(RatsColor.muted)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private var methodologyPopover: some View {
        HStack(alignment: .top, spacing: 14) {
            Lotti3DView(scene: .reading, animated: false)
                .frame(width: 82, height: 92)
                .accessibilityHidden(true)
            VStack(alignment: .leading, spacing: 8) {
                Text("So entsteht das Profil")
                    .font(RatsFont.title(18))
                Text(methodologyText)
                    .font(RatsFont.body(12.5))
                    .foregroundStyle(RatsColor.secondary)
                    .lineSpacing(3)
            }
        }
        .padding(18)
        .frame(idealWidth: 390)
        .background(RatsColor.card)
    }

    private var methodologyText: String {
        if person.type == "verwaltung" {
            return "Amt und Zeitraum stammen aus den Anwesenheitslisten der Protokolle. Der Zeitraum beschreibt Erwähnungen – keine amtliche Amtszeit."
        }
        return "Präsenz stammt aus den Anwesenheitslisten der Protokolle ab 2018. Offizielle Gremien-Zeiträume reichen – soweit verfügbar – bis 2001 zurück. Präsenz zeigt Aktivität, nicht das Stimmverhalten."
    }

    private var metricDivider: some View {
        Rectangle().fill(RatsColor.border).frame(width: 1, height: 35).padding(.horizontal, 10)
    }

    private var initials: String {
        person.name.split(separator: " ").prefix(2).compactMap(\.first).map(String.init).joined().uppercased()
    }

    private var partyColor: Color { color(for: person.affiliation ?? person.party ?? "Stadt") }
    private var partyForeground: Color {
        let folded = (person.affiliation ?? person.party ?? "").lowercased()
        return folded.contains("fdp") ? Color.black.opacity(0.78) : .white
    }

    private func color(for label: String) -> Color {
        let value = label.lowercased()
        if value.contains("grün") { return Color(red: 0.24, green: 0.56, blue: 0.16) }
        if value.contains("linke") { return Color(red: 0.90, green: 0.00, blue: 0.49) }
        if value.contains("spd") { return Color(red: 0.89, green: 0.00, blue: 0.06) }
        if value.contains("cdu") { return Color(red: 0.20, green: 0.22, blue: 0.24) }
        if value.contains("bsw") { return Color(red: 0.49, green: 0.15, blue: 0.31) }
        if value.contains("afd") { return Color(red: 0.00, green: 0.52, blue: 0.74) }
        if value.contains("volt") { return Color(red: 0.31, green: 0.14, blue: 0.47) }
        if value.contains("fdp") { return Color(red: 1.00, green: 0.84, blue: 0.00) }
        if value.contains("pirat") { return Color(red: 0.95, green: 0.45, blue: 0.05) }
        return RatsColor.primary
    }

    private func partyBadge(_ label: String, parties: [String]) -> some View {
        HStack(spacing: 6) {
            Circle().fill(color(for: label)).frame(width: 8, height: 8)
            Text(label).lineLimit(1)
            if parties.count > 1 {
                HStack(spacing: -2) {
                    ForEach(parties.prefix(3), id: \.self) { party in
                        Circle().fill(color(for: party)).frame(width: 9, height: 9)
                            .overlay(Circle().stroke(RatsColor.card, lineWidth: 1))
                    }
                }
            }
        }
        .font(RatsFont.body(11, weight: .semibold))
        .foregroundStyle(RatsColor.bodyText)
        .padding(.horizontal, 9)
        .padding(.vertical, 5)
        .background(color(for: label).opacity(0.10))
        .overlay(Capsule().stroke(color(for: label).opacity(0.26)))
        .clipShape(Capsule())
    }

    private func officeTimelineRow(_ membership: PublicPersonProfile.RISProfile.Membership) -> some View {
        let startYear = Int(membership.from?.prefix(4) ?? "") ?? Calendar.current.component(.year, from: .now) - 4
        let currentYear = Calendar.current.component(.year, from: .now)
        let earliest = person.ris?.memberships.compactMap { Int($0.from?.prefix(4) ?? "") }.min() ?? startYear
        let span = max(1, currentYear - earliest)
        let offset = min(0.9, max(0, Double(startYear - earliest) / Double(span)))
        let isChair = membership.role?.localizedCaseInsensitiveContains("vorsitz") == true
        return VStack(alignment: .leading, spacing: 6) {
            HStack(alignment: .firstTextBaseline) {
                if isChair { Image(systemName: "gavel").font(.caption).foregroundStyle(RatsColor.signal) }
                Text(shortCommittee(membership.committee)).font(RatsFont.body(13, weight: isChair ? .semibold : .regular))
                Spacer()
                Text("seit " + String(startYear)).font(RatsFont.mono(9.5)).foregroundStyle(RatsColor.secondary)
            }
            GeometryReader { proxy in
                ZStack(alignment: .leading) {
                    Capsule().fill(RatsColor.stage)
                    Capsule().fill(isChair ? RatsColor.signal : partyColor)
                        .frame(width: max(14, proxy.size.width * (1 - offset)))
                        .offset(x: proxy.size.width * offset)
                }
            }
            .frame(height: 9)
        }
    }

    private func pastOfficeRow(_ membership: PublicPersonProfile.RISProfile.Membership) -> some View {
        HStack(alignment: .firstTextBaseline, spacing: 8) {
            Text(shortCommittee(membership.committee)).font(RatsFont.body(12.5)).lineLimit(2)
            Spacer()
            Text("\(year(membership.from)) – \(year(membership.until))")
                .font(RatsFont.mono(9.5)).foregroundStyle(RatsColor.muted)
        }
    }

    private func speechRow(_ speech: PublicPersonProfile.Speech) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(alignment: .firstTextBaseline, spacing: 6) {
                Text(speechKind(speech.kind))
                    .font(RatsFont.mono(9.5)).foregroundStyle(partyColor)
                if let agendaItem = speech.agendaItem, !agendaItem.isEmpty {
                    Text("· \(agendaItem)").font(RatsFont.body(11.5, weight: .semibold)).lineLimit(1)
                }
                Spacer()
                Text(RatsDate.short(speech.sessionDate) ?? speech.sessionDate)
                    .font(RatsFont.mono(9)).foregroundStyle(RatsColor.muted)
            }
            Text(speech.text)
                .font(RatsFont.body(13))
                .foregroundStyle(RatsColor.bodyText)
                .lineSpacing(3)
                .fixedSize(horizontal: false, vertical: true)
            if let committee = speech.committee {
                Text(shortCommittee(committee)).font(RatsFont.mono(9)).foregroundStyle(RatsColor.muted)
            }
        }
        .padding(.vertical, 11)
    }

    private func speechKind(_ kind: String) -> String {
        switch kind {
        case "rede": "REDE"
        case "anfrage": "ANFRAGE"
        case "einwohnerfrage": "EINWOHNERFRAGE"
        case "zusage": "ZUSAGE"
        default: kind.uppercased()
        }
    }

    private func selectSpeechCommittee(_ committee: String) {
        selectedCommittee = committee
        Task { await loadSpeeches(reset: true) }
    }

    private func loadSpeeches(reset: Bool) async {
        guard !isLoadingSpeeches, !person.slug.isEmpty else { return }
        isLoadingSpeeches = true
        speechError = nil
        defer { isLoadingSpeeches = false }
        do {
            let offset = reset ? 0 : speeches.count
            var query = [
                URLQueryItem(name: "offset", value: String(offset)),
                URLQueryItem(name: "limit", value: "20"),
            ]
            if !selectedCommittee.isEmpty {
                query.append(URLQueryItem(name: "gremium", value: selectedCommittee))
            }
            let page: SpeechPage = try await model.api.get(
                "/api/council/person/\(person.slug)/wortbeitraege",
                query: query
            )
            speeches = reset ? page.items : speeches + page.items
            totalSpeeches = page.total
        } catch {
            speechError = "Die Wortbeiträge konnten nicht geladen werden."
        }
    }

    private func year(_ value: String?) -> String {
        guard let value, value.count >= 4 else { return "?" }
        return String(value.prefix(4))
    }

    private func shortCommittee(_ value: String) -> String {
        value
            .replacingOccurrences(of: "Ausschuss für ", with: "")
            .replacingOccurrences(of: "Ausschuss ", with: "")
    }

    private struct SpeechPage: Codable {
        let items: [PublicPersonProfile.Speech]
        let total: Int
    }
}

struct ExternalWebView: View {
    let url: URL
    var body: some View { SafariController(url: url).ignoresSafeArea() }
}

private struct SafariController: UIViewControllerRepresentable {
    let url: URL
    func makeUIViewController(context: Context) -> SFSafariViewController { SFSafariViewController(url: url) }
    func updateUIViewController(_ uiViewController: SFSafariViewController, context: Context) {}
}

struct QuizArea: Codable, Sendable, Identifiable {
    var id: String { key }
    let key: String
    let label: String?
    let questions: Int
    let points: Int?
    let stadtteile: [String]?
    let stadtteil: String?
}

struct QuizAreas: Codable, Sendable {
    let wahlbereiche: [QuizArea]
    let stadtteile: [QuizArea]
    let themen: [QuizArea]
    let categories: [String]
}

private func quizCategoryLabel(_ category: String) -> String {
    switch category {
    case "geschichte": "Geschichte"
    case "orte": "Orte"
    case "menschen": "Menschen"
    case "ratspolitik": "Ratspolitik"
    case "schaetzen": "Schätzfrage"
    default: category.capitalized
    }
}

private struct QuizQuestion: Codable, Sendable, Identifiable {
    let id: Int
    let areaType: String
    let areaKey: String
    let category: String
    let difficulty: String
    let question: String
    let options: [String]
    let qtype: String?
    let unit: String?
    let rangeMin: Double?
    let rangeMax: Double?
    let hint: String?

    enum CodingKeys: String, CodingKey {
        case id, category, difficulty, question, options, qtype, unit, hint
        case areaType = "area_type"
        case areaKey = "area_key"
        case rangeMin = "range_min"
        case rangeMax = "range_max"
    }
}

private struct QuizRound: Codable, Sendable { let questions: [QuizQuestion] }

private struct QuizResult: Codable, Sendable {
    let correct: Bool
    let correctIndex: Int
    let points: Int
    let answerValue: Double?
    let unit: String?
    let explanation: String?
    let sourceType: String?
    let sourceRef: String?

    enum CodingKeys: String, CodingKey {
        case correct, points, unit, explanation
        case correctIndex = "correct_index"
        case answerValue = "answer_value"
        case sourceType = "source_type"
        case sourceRef = "source_ref"
    }
}

private enum QuizMode: String {
    case normal
    case review
    case daily
    case own

    var title: String {
        switch self {
        case .normal: "Neues Spiel"
        case .review: "Meine Fehler"
        case .daily: "Tägliche Challenge"
        case .own: "Eigene Karten"
        }
    }
}

private struct QuizStats: Codable, Sendable {
    struct Total: Codable, Sendable { let points: Int; let answered: Int; let correct: Int }
    struct Area: Codable, Sendable, Identifiable {
        var id: String { "\(areaType):\(areaKey)" }
        let areaType: String
        let areaKey: String
        let points: Int
        let answered: Int
        let correct: Int
        let lastAt: String?

        enum CodingKeys: String, CodingKey {
            case points, answered, correct
            case areaType = "area_type"
            case areaKey = "area_key"
            case lastAt = "last_at"
        }
    }
    struct Badge: Codable, Sendable, Identifiable {
        var id: String { key }
        let key: String
        let label: String
        let tier: String
    }

    let byArea: [Area]
    let total: Total
    let wrong: Int
    let streak: Int
    let badges: [Badge]
    let dailyDone: Bool

    enum CodingKeys: String, CodingKey {
        case total, wrong, streak, badges
        case byArea = "by_area"
        case dailyDone = "daily_done"
    }
}

private struct QuizDaily: Codable, Sendable {
    let day: String
    let done: JSONValue?
    let questions: [QuizQuestion]
}

struct OwnQuizQuestion: Codable, Sendable, Identifiable {
    let id: Int
    let question: String
    let options: [String]
    let correctIndex: Int
    let stadtteil: String?
    let category: String
    let explanation: String?
    let qtype: String?
    let answerValue: Double?
    let unit: String?
    let rangeMin: Double?
    let rangeMax: Double?
    let practiced: Int
    let correctCount: Int

    enum CodingKeys: String, CodingKey {
        case id, question, options, stadtteil, category, explanation, qtype, unit, practiced
        case correctIndex = "correct_index"
        case answerValue = "answer_value"
        case rangeMin = "range_min"
        case rangeMax = "range_max"
        case correctCount = "correct_count"
    }
}

private struct OwnQuizQuestions: Codable, Sendable { let questions: [OwnQuizQuestion] }

struct QuizView: View {
    let model: AppModel
    let area: String?
    @Environment(\.horizontalSizeClass) private var horizontalSizeClass
    @State private var areas: QuizAreas?
    @State private var selectedAreas: Set<String> = []
    @State private var selectedCategories: Set<String> = []
    @State private var placeSearch = ""
    @State private var showAllPlaces = false
    @State private var isStarting = false
    @State private var round: [QuizQuestion] = []
    @State private var index = 0
    @State private var result: QuizResult?
    @State private var selectedAnswer: Int?
    @State private var selectedEstimate: Double?
    @State private var points = 0
    @State private var correct = 0
    @State private var error: String?
    @State private var mode: QuizMode = .normal
    @State private var stats: QuizStats?
    @State private var daily: QuizDaily?
    @State private var own: [OwnQuizQuestion] = []
    @State private var showOwnEditor = ProcessInfo.processInfo.environment["RATSLOTSE_DEBUG_QUIZ_OWN"] != nil
    @State private var showMapQuiz = false
    @State private var showStats = false

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                if showStats, let stats {
                    QuizStatsScreen(
                        stats: stats,
                        labels: quizAreaLabels,
                        back: { withAnimation(.snappy) { showStats = false } },
                        practice: { area in Task { await practice(area) } }
                    )
                } else if round.isEmpty {
                    setup
                } else if index < round.count {
                    questionView(round[index])
                } else {
                    resultView
                }
                if let error { ErrorCard(message: error) { Task { await loadAreas() } } }
            }
            .frame(maxWidth: usesWideLayout ? 1040 : 680, alignment: .leading)
            .padding(18)
        }
        .background(RatsColor.page)
        .navigationTitle("Oldenburg-Quiz")
        .navigationBarTitleDisplayMode(.inline)
        .task {
#if DEBUG
            if ProcessInfo.processInfo.environment["RATSLOTSE_DEBUG_QUIZ_RESULT"] == "1" {
                installDebugResult()
                return
            }
            if ProcessInfo.processInfo.environment["RATSLOTSE_DEBUG_QUIZ_SETUP"] == "1" {
                installDebugSetup()
                return
            }
#endif
            await loadAreas()
        }
        .sheet(isPresented: $showOwnEditor) {
            OwnQuizEditor(model: model) { await loadDashboard() }
                .ratsLargeSheet()
        }
        .sheet(isPresented: $showMapQuiz) {
            NavigationStack { QuizMapView(model: model) }
        }
    }

    private var setup: some View {
        VStack(alignment: .leading, spacing: 18) {
            MonoKicker("Wissen, was vor Ort passiert")
            Text("Wie gut kennst du Oldenburg?").font(RatsFont.title(28))
            Text("Die Antworten stammen aus Ratsunterlagen und verlässlichen Stadtquellen.")
                .foregroundStyle(RatsColor.secondary)
            if let stats, stats.total.answered > 0 {
                Button { withAnimation(.snappy) { showStats = true } } label: {
                    QuizStatsSummary(stats: stats)
                }
                .buttonStyle(.plain)
            }
            LazyVGrid(columns: quizModeColumns, spacing: 10) {
                QuizModeButton(title: "Täglich", detail: daily?.done == nil ? "Heute offen" : "Heute erledigt", symbol: "bolt.fill") {
                    Task { await startDaily() }
                }
                QuizModeButton(title: "Fehler üben", detail: "\(stats?.wrong ?? 0) offen", symbol: "arrow.counterclockwise") {
                    Task { await startSpecial(path: "/api/quiz/review", mode: .review) }
                }
                QuizModeButton(title: "Karten-Quiz", detail: "Stadtteile finden", symbol: "map") {
                    showMapQuiz = true
                }
                QuizModeButton(title: "Eigene Karten", detail: "\(own.count) gespeichert", symbol: "pencil") {
                    if own.isEmpty { showOwnEditor = true }
                    else { Task { await startSpecial(path: "/api/quiz/own/round", mode: .own) } }
                }
            }
            Button { showOwnEditor = true } label: {
                Label(own.isEmpty ? "Erste eigene Karte erstellen" : "Eigene Karten verwalten", systemImage: "rectangle.stack.badge.plus")
            }
            .buttonStyle(SecondaryButtonStyle())
            Divider().overlay(RatsColor.separator)
            if let areas {
                quizConfiguration(areas)
            } else { ProgressView("Gebiete laden …") }
        }
    }

    private func quizConfiguration(_ catalog: QuizAreas) -> some View {
        RatsSectionPanel(
            "Deine Runde",
            detail: "Kombiniere mehrere Wahlbereiche, Orte und Themen. Kategorien sind optional.",
            symbol: "slider.horizontal.3"
        ) {
            VStack(alignment: .leading, spacing: 17) {
                if !catalog.wahlbereiche.isEmpty {
                    quizChoiceSection(
                        title: "Wahlbereiche",
                        detail: "Große Auswahl mit einem Tipp",
                        entries: catalog.wahlbereiche,
                        prefix: "wahlbereich:"
                    )
                }

                quizPlaces(catalog.stadtteile)

                if !catalog.themen.isEmpty {
                    quizChoiceSection(
                        title: "Themen",
                        detail: "Projekte und Debatten gezielt üben",
                        entries: catalog.themen,
                        prefix: "thema:"
                    )
                }

                if !catalog.categories.isEmpty {
                    VStack(alignment: .leading, spacing: 8) {
                        quizSectionHeader("Kategorien", detail: "optional – ohne Auswahl ist alles dabei")
                        QuizFlowLayout(spacing: 7) {
                            ForEach(catalog.categories, id: \.self) { category in
                                QuizChoiceChip(
                                    title: quizCategoryLabel(category),
                                    detail: nil,
                                    selected: selectedCategories.contains(category)
                                ) { toggleCategory(category) }
                            }
                        }
                    }
                }

                HStack(alignment: .center, spacing: 12) {
                    VStack(alignment: .leading, spacing: 3) {
                        Text(selectionSummary)
                            .font(RatsFont.body(14, weight: .semibold))
                            .foregroundStyle(RatsColor.text)
                        Text(selectedCategories.isEmpty ? "Alle Fragearten" : selectedCategories.sorted().map(quizCategoryLabel).joined(separator: ", "))
                            .font(RatsFont.body(11))
                            .foregroundStyle(RatsColor.secondary)
                            .lineLimit(2)
                    }
                    Spacer(minLength: 8)
                    Button { Task { await start() } } label: {
                        if isStarting {
                            HStack(spacing: 7) {
                                ProgressView().tint(.white)
                                Text("Lädt …")
                            }
                        } else {
                            Label("Quiz starten", systemImage: "play.fill")
                        }
                    }
                    .buttonStyle(PrimaryButtonStyle())
                    .disabled(selectedAreas.isEmpty || isStarting)
                }
                .padding(13)
                .background(RatsColor.stage)
                .overlay(RoundedRectangle(cornerRadius: 13, style: .continuous).stroke(RatsColor.border))
                .clipShape(RoundedRectangle(cornerRadius: 13, style: .continuous))
            }
        }
    }

    private func quizChoiceSection(
        title: String,
        detail: String,
        entries: [QuizArea],
        prefix: String
    ) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            quizSectionHeader(title, detail: detail)
            QuizFlowLayout(spacing: 7) {
                ForEach(entries) { entry in
                    let key = prefix + entry.key
                    QuizChoiceChip(
                        title: entry.label ?? entry.key,
                        detail: "\(entry.questions)",
                        selected: selectedAreas.contains(key)
                    ) { toggleArea(key) }
                }
            }
        }
    }

    private func quizPlaces(_ entries: [QuizArea]) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            quizSectionHeader("Orte", detail: "einzelne Stadtteile frei kombinieren")
            HStack(spacing: 8) {
                Image(systemName: "magnifyingglass")
                    .foregroundStyle(RatsColor.muted)
                TextField("Ort suchen", text: $placeSearch)
                    .textFieldStyle(.plain)
                    .textInputAutocapitalization(.never)
                if !placeSearch.isEmpty {
                    Button { placeSearch = "" } label: {
                        Image(systemName: "xmark.circle.fill")
                            .foregroundStyle(RatsColor.muted)
                    }
                    .buttonStyle(.plain)
                    .accessibilityLabel("Suche leeren")
                }
            }
            .font(RatsFont.body(14))
            .padding(.horizontal, 12)
            .frame(minHeight: 42)
            .background(RatsColor.stage)
            .overlay(RoundedRectangle(cornerRadius: 11, style: .continuous).stroke(RatsColor.border))
            .clipShape(RoundedRectangle(cornerRadius: 11, style: .continuous))

            QuizFlowLayout(spacing: 7) {
                ForEach(visiblePlaces(entries)) { entry in
                    let key = "stadtteil:" + entry.key
                    QuizChoiceChip(
                        title: entry.label ?? entry.key,
                        detail: "\(entry.questions)",
                        selected: selectedAreas.contains(key)
                    ) { toggleArea(key) }
                }
            }
            if placeSearch.isEmpty && entries.count > 12 {
                Button(showAllPlaces ? "Weniger Orte zeigen" : "Alle \(entries.count) Orte zeigen") {
                    withAnimation(.easeInOut(duration: 0.2)) { showAllPlaces.toggle() }
                }
                .font(RatsFont.body(12, weight: .semibold))
                .foregroundStyle(RatsColor.primary)
            }
        }
    }

    private func quizSectionHeader(_ title: String, detail: String) -> some View {
        HStack(alignment: .firstTextBaseline, spacing: 7) {
            Text(title)
                .font(RatsFont.body(13, weight: .semibold))
                .foregroundStyle(RatsColor.text)
            Text(detail)
                .font(RatsFont.body(11))
                .foregroundStyle(RatsColor.muted)
            Spacer(minLength: 0)
        }
    }

    private func visiblePlaces(_ entries: [QuizArea]) -> [QuizArea] {
        let needle = placeSearch.trimmingCharacters(in: .whitespacesAndNewlines)
        if !needle.isEmpty {
            return entries.filter { ($0.label ?? $0.key).localizedCaseInsensitiveContains(needle) }
        }
        if showAllPlaces { return entries }
        let selected = entries.filter { selectedAreas.contains("stadtteil:" + $0.key) }
        let unselected = entries.filter { !selectedAreas.contains("stadtteil:" + $0.key) }
        return Array((selected + unselected).prefix(max(12, selected.count)))
    }

    private var selectionSummary: String {
        if selectedAreas.isEmpty { return "Wähle mindestens ein Gebiet" }
        return "\(selectedAreas.count) \(selectedAreas.count == 1 ? "Gebiet" : "Gebiete") ausgewählt"
    }

    private var quizAreaLabels: [String: String] {
        guard let areas else { return [:] }
        let rows = areas.wahlbereiche.map { ("wahlbereich:\($0.key)", $0.label ?? $0.key) }
            + areas.stadtteile.map { ("stadtteil:\($0.key)", $0.label ?? $0.key) }
            + areas.themen.map { ("thema:\($0.key)", $0.label ?? $0.key) }
        return Dictionary(uniqueKeysWithValues: rows)
    }

    private var usesWideLayout: Bool {
        UIDevice.current.userInterfaceIdiom == .pad && horizontalSizeClass != .compact
    }

    private var quizModeColumns: [GridItem] {
        Array(repeating: GridItem(.flexible(), spacing: 10), count: usesWideLayout ? 4 : 2)
    }

    private func toggleArea(_ key: String) {
        if selectedAreas.contains(key) { selectedAreas.remove(key) }
        else { selectedAreas.insert(key) }
    }

    private func toggleCategory(_ key: String) {
        if selectedCategories.contains(key) { selectedCategories.remove(key) }
        else { selectedCategories.insert(key) }
    }

    private func practice(_ area: QuizStats.Area) async {
        showStats = false
        selectedAreas = ["\(area.areaType):\(area.areaKey)"]
        selectedCategories.removeAll()
        await start()
    }

    @ViewBuilder
    private func questionView(_ question: QuizQuestion) -> some View {
        VStack(alignment: .leading, spacing: 16) {
            MonoKicker(question.category, trailing: "\(index + 1) von \(round.count)")
            ProgressView(value: Double(index + 1), total: Double(round.count)).tint(RatsColor.primary)
            Text(question.question).font(RatsFont.title(24))
            if question.qtype == "estimate" {
                let minimum = question.rangeMin ?? 0
                let maximum = max(question.rangeMax ?? 100, minimum + 1)
                let value = Binding(
                    get: { selectedEstimate ?? (minimum + maximum) / 2 },
                    set: { selectedEstimate = $0 }
                )
                VStack(spacing: 10) {
                    Text("\(value.wrappedValue.formatted(.number.precision(.fractionLength(0...1)))) \(question.unit ?? "")")
                        .font(RatsFont.title(22))
                    Slider(value: value, in: minimum...maximum).tint(RatsColor.primary)
                    HStack {
                        Text(minimum.formatted()).font(RatsFont.body(11))
                        Spacer()
                        Text(maximum.formatted()).font(RatsFont.body(11))
                    }
                    .foregroundStyle(RatsColor.secondary)
                    Button("Schätzung abgeben") {
                        Task { await submitEstimate(question: question, value: value.wrappedValue) }
                    }
                    .buttonStyle(PrimaryButtonStyle())
                    .disabled(result != nil)
                }
                .ratsCard()
            } else {
                ForEach(Array(question.options.enumerated()), id: \.offset) { answerIndex, option in
                    Button {
                        Task { await submitAnswer(question: question, selected: answerIndex) }
                    } label: {
                        HStack {
                            Text(option).multilineTextAlignment(.leading)
                            Spacer()
                            if let result, answerIndex == result.correctIndex {
                                Image(systemName: "checkmark.circle.fill").foregroundStyle(RatsColor.success)
                            } else if selectedAnswer == answerIndex, result != nil {
                                Image(systemName: "xmark.circle.fill").foregroundStyle(RatsColor.danger)
                            }
                        }
                        .font(RatsFont.body(15, weight: .medium))
                        .padding(14)
                        .background(RatsColor.card)
                        .overlay(RoundedRectangle(cornerRadius: 11).stroke(RatsColor.border))
                        .clipShape(RoundedRectangle(cornerRadius: 11))
                    }
                    .buttonStyle(.plain)
                    .disabled(result != nil)
                }
            }
            if let result {
                VStack(alignment: .leading, spacing: 9) {
                    Label(result.correct ? "Richtig – \(result.points) Punkte" : "Nicht ganz", systemImage: result.correct ? "checkmark" : "lightbulb")
                        .font(RatsFont.body(15, weight: .semibold))
                        .foregroundStyle(result.correct ? RatsColor.success : RatsColor.warning)
                    if let explanation = result.explanation { Text(explanation).foregroundStyle(RatsColor.secondary) }
                    Button(index + 1 == round.count ? "Ergebnis ansehen" : "Nächste Frage") {
                        advance()
                    }
                    .buttonStyle(PrimaryButtonStyle())
                }
                .ratsCard()
            }
        }
    }

    private var resultView: some View {
        VStack(spacing: 16) {
            Lotti3DView(scene: .celebrate)
                .frame(width: 220, height: 176)
                .accessibilityHidden(true)
            Text("\(correct) von \(round.count) richtig").font(RatsFont.title(28))
            Text("\(points) Punkte").foregroundStyle(RatsColor.secondary)
            Text(mode.title).font(RatsFont.body(12)).foregroundStyle(RatsColor.muted)
            Button("Neue Runde") {
                round = []; index = 0; points = 0; correct = 0; mode = .normal
                Task { await loadDashboard() }
            }
            .buttonStyle(PrimaryButtonStyle())
        }
        .frame(maxWidth: .infinity)
        .ratsCard()
    }

#if DEBUG
    private func installDebugResult() {
        round = (0..<4).map { number in
            QuizQuestion(
                id: number,
                areaType: "stadtteil",
                areaKey: "Osternburg",
                category: "Oldenburg",
                difficulty: "mittel",
                question: "Vorschaufrage",
                options: ["Antwort A", "Antwort B"],
                qtype: nil,
                unit: nil,
                rangeMin: nil,
                rangeMax: nil,
                hint: nil
            )
        }
        index = round.count
        correct = 3
        points = 240
    }

    private func installDebugSetup() {
        areas = QuizAreas(
            wahlbereiche: (1...6).map {
                QuizArea(
                    key: "\($0)",
                    label: "Wahlbereich \($0)",
                    questions: 18 + $0 * 3,
                    points: $0 * 4,
                    stadtteile: nil,
                    stadtteil: nil
                )
            },
            stadtteile: ["Bloherfelde", "Bürgerfelde", "Donnerschwee", "Eversten", "Kreyenbrück", "Nadorst", "Ofenerdiek", "Osternburg", "Tweelbäke", "Wechloy", "Zentrum", "Etzhorn", "Ohmstede", "Alexandersfeld"].enumerated().map { offset, name in
                QuizArea(
                    key: name,
                    label: name,
                    questions: 7 + offset,
                    points: offset,
                    stadtteile: nil,
                    stadtteil: nil
                )
            },
            themen: [
                QuizArea(key: "schulwege", label: "Sichere Schulwege", questions: 12, points: 8, stadtteile: nil, stadtteil: "Kreyenbrück"),
                QuizArea(key: "wohnen", label: "Wohnen & Bauen", questions: 16, points: 5, stadtteile: nil, stadtteil: nil),
                QuizArea(key: "klima", label: "Klima & Energie", questions: 14, points: 3, stadtteile: nil, stadtteil: nil),
                QuizArea(key: "innenstadt", label: "Lebendige Innenstadt", questions: 9, points: 2, stadtteile: nil, stadtteil: "Zentrum"),
            ],
            categories: ["geschichte", "orte", "menschen", "ratspolitik", "schaetzen"]
        )
        selectedAreas = ["wahlbereich:3", "thema:schulwege"]
        selectedCategories = ["ratspolitik", "orte"]
        stats = QuizStats(
            byArea: [
                .init(areaType: "stadtteil", areaKey: "Osternburg", points: 18, answered: 14, correct: 7, lastAt: "2026-08-28"),
                .init(areaType: "thema", areaKey: "schulwege", points: 22, answered: 12, correct: 10, lastAt: "2026-08-27"),
                .init(areaType: "stadtteil", areaKey: "Nadorst", points: 31, answered: 18, correct: 14, lastAt: "2026-08-26"),
            ],
            total: .init(points: 148, answered: 63, correct: 47),
            wrong: 6,
            streak: 4,
            badges: [
                .init(key: "punkte", label: "100 Punkte", tier: "silber"),
                .init(key: "serie", label: "3-Tage-Serie", tier: "silber"),
            ],
            dailyDone: false
        )
        daily = QuizDaily(day: "2026-08-28", done: nil, questions: [])
        own = []
    }

#endif

    private func loadAreas() async {
        guard areas == nil else { return }
        do {
            areas = try await model.api.get("/api/quiz/areas")
            if let area { selectedAreas = [area] }
            else if let first = areas?.wahlbereiche.first { selectedAreas = ["wahlbereich:\(first.key)"] }
            await loadDashboard()
        } catch { self.error = error.localizedDescription }
    }

    private func start() async {
        guard !selectedAreas.isEmpty, !isStarting else { return }
        isStarting = true
        defer { isStarting = false }
        do {
            let response: QuizRound = try await model.api.get(
                "/api/quiz/round",
                query: [
                    .init(name: "areas", value: selectedAreas.sorted().joined(separator: ",")),
                    .init(name: "categories", value: selectedCategories.sorted().joined(separator: ",")),
                    .init(name: "n", value: "10"),
                ]
            )
            guard !response.questions.isEmpty else {
                error = "Für diese Auswahl gibt es gerade keine offenen Fragen. Probiere ein weiteres Gebiet oder eine andere Kategorie."
                return
            }
            error = nil
            round = response.questions
            index = 0
            mode = .normal
        } catch { self.error = error.localizedDescription }
    }

    private func submitAnswer(question: QuizQuestion, selected: Int) async {
        struct Body: Codable, Sendable { let question_id: Int; let selected_index: Int?; let value: Double? }
        selectedAnswer = selected
        do {
            let response: QuizResult = try await model.api.send(
                mode == .own ? "/api/quiz/own/answer" : "/api/quiz/answer",
                body: Body(question_id: question.id, selected_index: selected, value: nil)
            )
            result = response
            points += response.points
            if response.correct { correct += 1 }
        } catch { self.error = error.localizedDescription }
    }

    private func submitEstimate(question: QuizQuestion, value: Double) async {
        struct Body: Codable, Sendable { let question_id: Int; let selected_index: Int?; let value: Double? }
        do {
            let response: QuizResult = try await model.api.send(
                mode == .own ? "/api/quiz/own/answer" : "/api/quiz/answer",
                body: Body(question_id: question.id, selected_index: nil, value: value)
            )
            result = response
            points += response.points
            if response.correct { correct += 1 }
        } catch { self.error = error.localizedDescription }
    }

    private func advance() {
        let completesDaily = mode == .daily && index + 1 == round.count
        index += 1
        selectedAnswer = nil
        selectedEstimate = nil
        result = nil
        if completesDaily {
            struct Body: Codable, Sendable { let correct: Int; let total: Int; let points: Int }
            Task {
                try? await model.api.sendVoid(
                    "/api/quiz/daily/complete",
                    body: Body(correct: correct, total: round.count, points: points)
                )
            }
        }
    }

    private func loadDashboard() async {
        do {
            async let statsRequest: QuizStats = model.api.get("/api/quiz/stats")
            async let dailyRequest: QuizDaily = model.api.get("/api/quiz/daily")
            async let ownRequest: OwnQuizQuestions = model.api.get("/api/quiz/own")
            let (newStats, newDaily, newOwn) = try await (statsRequest, dailyRequest, ownRequest)
            stats = newStats
            daily = newDaily
            own = newOwn.questions
            await model.refreshBadges()
        } catch {
            // Die Modi sind Zusatzinformationen; die normale Runde bleibt nutzbar.
        }
    }

    private func startSpecial(path: String, mode: QuizMode) async {
        do {
            let response: QuizRound = try await model.api.get(path, query: [.init(name: "n", value: "10")])
            guard !response.questions.isEmpty else {
                error = mode == .review ? "Keine offenen Fehler – stark!" : "Noch keine eigenen Fragen zum Üben."
                return
            }
            self.mode = mode
            round = response.questions
            index = 0
            points = 0
            correct = 0
        } catch { self.error = error.localizedDescription }
    }

    private func startDaily() async {
        guard let daily else { return }
        guard daily.done == nil else {
            error = "Die heutige Challenge ist schon erledigt. Morgen gibt es neue Fragen."
            return
        }
        guard !daily.questions.isEmpty else { return }
        mode = .daily
        round = daily.questions
        index = 0
        points = 0
        correct = 0
    }
}

private struct QuizStatsSummary: View {
    let stats: QuizStats

    var body: some View {
        HStack(spacing: 14) {
            Image(systemName: "chart.line.uptrend.xyaxis")
                .font(.system(size: 17, weight: .semibold))
                .foregroundStyle(RatsColor.primaryText)
                .frame(width: 44, height: 44)
                .background(RatsColor.primary)
                .clipShape(RoundedRectangle(cornerRadius: 13, style: .continuous))
            VStack(alignment: .leading, spacing: 5) {
                Text("Meine Quiz-Statistik")
                    .font(RatsFont.body(15, weight: .semibold))
                    .foregroundStyle(RatsColor.text)
                Text("\(stats.total.points) Punkte · \(rate)% richtig · \(stats.streak)-Tage-Serie")
                    .font(RatsFont.body(11))
                    .foregroundStyle(RatsColor.secondary)
            }
            Spacer(minLength: 4)
            Image(systemName: "chevron.right")
                .font(.caption)
                .foregroundStyle(RatsColor.muted)
        }
        .padding(13)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(RatsColor.primary.opacity(0.055))
        .overlay(RoundedRectangle(cornerRadius: 15).stroke(RatsColor.primary.opacity(0.18)))
        .clipShape(RoundedRectangle(cornerRadius: 15, style: .continuous))
    }

    private var rate: Int {
        guard stats.total.answered > 0 else { return 0 }
        return Int((Double(stats.total.correct) / Double(stats.total.answered) * 100).rounded())
    }
}

private struct QuizStatsScreen: View {
    let stats: QuizStats
    let labels: [String: String]
    let back: () -> Void
    let practice: (QuizStats.Area) -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Button(action: back) {
                Label("Zurück zum Quiz", systemImage: "chevron.left")
                    .font(RatsFont.body(12, weight: .semibold))
                    .foregroundStyle(RatsColor.primary)
            }
            .buttonStyle(.plain)
            VStack(alignment: .leading, spacing: 5) {
                MonoKicker("Dein Wissen über Oldenburg")
                Text("Meine Quiz-Statistik")
                    .font(RatsFont.title(28))
                Text("Fortschritt je Gebiet, schwächste zuerst – plus Serie und Abzeichen.")
                    .font(RatsFont.body(13))
                    .foregroundStyle(RatsColor.secondary)
            }
            QuizProgressPanel(stats: stats, labels: labels, practice: practice)
        }
    }
}

private struct QuizProgressPanel: View {
    let stats: QuizStats
    let labels: [String: String]
    let practice: (QuizStats.Area) -> Void

    private let metricColumns = [GridItem(.adaptive(minimum: 106), spacing: 12)]
    private let areaColumns = [GridItem(.adaptive(minimum: 250), spacing: 10)]

    var body: some View {
        RatsSectionPanel(
            "Mein Fortschritt",
            detail: "Schwächere Gebiete stehen zuerst – von dort kannst du direkt weiterüben.",
            symbol: "chart.line.uptrend.xyaxis"
        ) {
            LazyVGrid(columns: metricColumns, alignment: .leading, spacing: 12) {
                QuizMetric(value: "\(stats.total.points)", label: "Punkte")
                QuizMetric(value: "\(hitRate(stats.total.correct, stats.total.answered)) %", label: "Trefferquote")
                QuizMetric(value: "\(stats.total.answered)", label: "gespielt")
                QuizMetric(value: "\(stats.streak)", label: "Tage-Serie")
            }
            .padding(13)
            .background(RatsColor.primary.opacity(0.055))
            .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))

            if !stats.badges.isEmpty {
                VStack(alignment: .leading, spacing: 8) {
                    MonoKicker("Quiz-Abzeichen", trailing: "\(stats.badges.count)")
                    QuizFlowLayout(spacing: 7) {
                        ForEach(stats.badges) { badge in
                            Label(badge.label, systemImage: badge.tier == "gold" ? "trophy.fill" : "medal.fill")
                                .font(RatsFont.body(11, weight: .semibold))
                                .foregroundStyle(badgeColor(badge.tier))
                                .padding(.horizontal, 10)
                                .frame(minHeight: 30)
                                .background(badgeColor(badge.tier).opacity(0.10))
                                .overlay(Capsule().stroke(badgeColor(badge.tier).opacity(0.22)))
                                .clipShape(Capsule())
                        }
                    }
                }
            }

            if stats.wrong > 0 {
                HStack(spacing: 10) {
                    Image(systemName: "arrow.counterclockwise")
                        .foregroundStyle(RatsColor.warning)
                    Text("\(stats.wrong) \(stats.wrong == 1 ? "Frage wartet" : "Fragen warten") auf einen zweiten Versuch.")
                        .font(RatsFont.body(12, weight: .medium))
                        .foregroundStyle(RatsColor.bodyText)
                }
                .padding(11)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(RatsColor.warningTint)
                .clipShape(RoundedRectangle(cornerRadius: 11, style: .continuous))
            }

            if !stats.byArea.isEmpty {
                VStack(alignment: .leading, spacing: 9) {
                    MonoKicker("Nach Gebiet", trailing: "schwächste zuerst")
                    LazyVGrid(columns: areaColumns, alignment: .leading, spacing: 10) {
                        ForEach(sortedAreas) { area in
                            QuizAreaProgressTile(
                                area: area,
                                label: labels[area.id] ?? area.areaKey,
                                practice: { practice(area) }
                            )
                        }
                    }
                }
            }
        }
    }

    private var sortedAreas: [QuizStats.Area] {
        stats.byArea.sorted {
            let lhs = Double($0.correct) / Double(max(1, $0.answered))
            let rhs = Double($1.correct) / Double(max(1, $1.answered))
            return lhs == rhs ? $0.answered > $1.answered : lhs < rhs
        }
    }

    private func hitRate(_ correct: Int, _ answered: Int) -> Int {
        guard answered > 0 else { return 0 }
        return Int((Double(correct) / Double(answered) * 100).rounded())
    }

    private func badgeColor(_ tier: String) -> Color {
        switch tier {
        case "gold": RatsColor.warning
        case "silber": RatsColor.secondary
        default: RatsColor.signal
        }
    }
}

private struct QuizAreaProgressTile: View {
    let area: QuizStats.Area
    let label: String
    let practice: () -> Void

    private var rate: Double {
        guard area.answered > 0 else { return 0 }
        return Double(area.correct) / Double(area.answered)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 9) {
            HStack(alignment: .top, spacing: 8) {
                Image(systemName: area.areaType == "thema" ? "sparkles" : "mappin.and.ellipse")
                    .font(.system(size: 12, weight: .semibold))
                    .foregroundStyle(RatsColor.primary)
                    .frame(width: 28, height: 28)
                    .background(RatsColor.primary.opacity(0.08))
                    .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
                VStack(alignment: .leading, spacing: 2) {
                    Text(label)
                        .font(RatsFont.body(12, weight: .semibold))
                        .foregroundStyle(RatsColor.text)
                        .lineLimit(1)
                    Text("\(area.correct) von \(area.answered) richtig")
                        .font(RatsFont.mono(9))
                        .foregroundStyle(RatsColor.muted)
                }
                Spacer(minLength: 4)
                Button("Üben", action: practice)
                    .font(RatsFont.body(10, weight: .semibold))
                    .foregroundStyle(RatsColor.primary)
                    .buttonStyle(.plain)
            }
            GeometryReader { proxy in
                ZStack(alignment: .leading) {
                    Capsule().fill(RatsColor.separator)
                    Capsule()
                        .fill(progressColor)
                        .frame(width: max(4, proxy.size.width * rate))
                }
            }
            .frame(height: 6)
        }
        .padding(11)
        .background(RatsColor.stage)
        .overlay(RoundedRectangle(cornerRadius: 12).stroke(RatsColor.border))
        .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
    }

    private var progressColor: Color {
        if rate >= 0.67 { return RatsColor.success }
        if rate >= 0.34 { return RatsColor.warning }
        return RatsColor.danger
    }
}

private struct QuizMetric: View {
    let value: String
    let label: String
    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(value).font(RatsFont.title(19))
            Text(label).font(RatsFont.body(10)).foregroundStyle(RatsColor.secondary)
        }
    }
}

private struct QuizModeButton: View {
    let title: String
    let detail: String
    let symbol: String
    let action: () -> Void
    var body: some View {
        Button(action: action) {
            VStack(alignment: .leading, spacing: 8) {
                Image(systemName: symbol).foregroundStyle(RatsColor.signal)
                Text(title).font(RatsFont.body(14, weight: .semibold))
                Text(detail).font(RatsFont.body(11)).foregroundStyle(RatsColor.secondary)
            }
            .frame(maxWidth: .infinity, minHeight: 76, alignment: .leading)
            .padding(12)
            .background(RatsColor.card)
            .overlay(RoundedRectangle(cornerRadius: 12).stroke(RatsColor.border))
            .clipShape(RoundedRectangle(cornerRadius: 12))
        }
        .buttonStyle(.plain)
    }
}

private struct QuizChoiceChip: View {
    let title: String
    let detail: String?
    let selected: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 6) {
                Image(systemName: selected ? "checkmark" : "plus")
                    .font(.system(size: 10, weight: .bold))
                Text(title)
                    .lineLimit(1)
                if let detail {
                    Text(detail)
                        .font(RatsFont.mono(9))
                        .opacity(0.72)
                }
            }
            .font(RatsFont.body(12, weight: .semibold))
            .foregroundStyle(selected ? Color.white : RatsColor.text)
            .padding(.horizontal, 11)
            .frame(minHeight: 34)
            .background(selected ? RatsColor.primary : RatsColor.stage)
            .overlay(Capsule().stroke(selected ? RatsColor.primary : RatsColor.border))
            .clipShape(Capsule())
            .contentShape(Capsule())
        }
        .buttonStyle(.plain)
        .accessibilityAddTraits(selected ? .isSelected : [])
    }
}

private struct QuizFlowLayout: Layout {
    let spacing: CGFloat

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let width = proposal.width ?? 0
        var x: CGFloat = 0
        var y: CGFloat = 0
        var rowHeight: CGFloat = 0
        for view in subviews {
            let size = view.sizeThatFits(.unspecified)
            if x > 0, x + size.width > width {
                x = 0
                y += rowHeight + spacing
                rowHeight = 0
            }
            x += size.width + spacing
            rowHeight = max(rowHeight, size.height)
        }
        return CGSize(width: width, height: y + rowHeight)
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        var x = bounds.minX
        var y = bounds.minY
        var rowHeight: CGFloat = 0
        for view in subviews {
            let size = view.sizeThatFits(.unspecified)
            if x > bounds.minX, x + size.width > bounds.maxX {
                x = bounds.minX
                y += rowHeight + spacing
                rowHeight = 0
            }
            view.place(at: CGPoint(x: x, y: y), anchor: .topLeading, proposal: ProposedViewSize(size))
            x += size.width + spacing
            rowHeight = max(rowHeight, size.height)
        }
    }
}

private struct OwnQuizEditor: View {
    let model: AppModel
    let onChange: () async -> Void
    @Environment(\.dismiss) private var dismiss
    @State private var questions: [OwnQuizQuestion] = []
    @State private var areas: QuizAreas?
    @State private var showForm = false
    @State private var editingID: Int?
    @State private var question = ""
    @State private var answers = ["", ""]
    @State private var correctIndex = 0
    @State private var category = "geschichte"
    @State private var stadtteil = ""
    @State private var explanation = ""
    @State private var answerValue = ""
    @State private var unit = ""
    @State private var rangeManual = false
    @State private var rangeMin = ""
    @State private var rangeMax = ""
    @State private var isSaving = false
    @State private var error: String?
    @State private var pendingDelete: OwnQuizQuestion?

    private let categories = ["geschichte", "orte", "menschen", "ratspolitik", "schaetzen"]

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                RatsSheetHeader("Eigene Karten", trailingTitle: "Fertig", trailingAction: { dismiss() })
                ScrollView {
                    VStack(alignment: .leading, spacing: 18) {
                    RatsModalIntro(
                        kicker: "Dein Lernbereich",
                        title: "Eigene Karten",
                        message: "Baue dein persönliches Oldenburg-Quiz – mit Auswahlfragen oder Zahlen zum Schätzen.",
                        symbol: "rectangle.stack.badge.plus"
                    )

                    HStack(spacing: 10) {
                        Button { beginNew() } label: {
                            Label("Neue Karte", systemImage: "plus")
                        }
                        .buttonStyle(PrimaryButtonStyle())
                        if !questions.isEmpty {
                            Text("\(questions.count) gespeichert")
                                .font(RatsFont.mono(10))
                                .foregroundStyle(RatsColor.muted)
                        }
                    }

                    if showForm {
                        editorPanel
                    }

                    MonoKicker("Deine Karten", trailing: "\(questions.count)")
                    if questions.isEmpty {
                        RatsEmptyState(
                            title: "Noch keine eigenen Karten",
                            message: "Lege eine Auswahl- oder Schätzfrage an. Deine Karten sind nur in deinem Konto sichtbar.",
                            symbol: "rectangle.stack.badge.plus"
                        )
                    }
                    ForEach(questions) { entry in
                        ownQuestionCard(entry)
                    }
                    if let error { ErrorCard(message: error) { Task { await load() } } }
                    }
                    .frame(maxWidth: 760, alignment: .leading)
                    .padding(.horizontal, 18)
                    .padding(.vertical, 22)
                }
                .background(RatsColor.page)
            }
            .toolbar(.hidden, for: .navigationBar)
            .task { await load() }
            .confirmationDialog(
                "Karte löschen?",
                isPresented: Binding(
                    get: { pendingDelete != nil },
                    set: { if !$0 { pendingDelete = nil } }
                ),
                titleVisibility: .visible
            ) {
                Button("Karte löschen", role: .destructive) {
                    if let pendingDelete { Task { await delete(pendingDelete) } }
                }
                Button("Abbrechen", role: .cancel) { pendingDelete = nil }
            } message: {
                Text("Die Karte wird dauerhaft aus deinem persönlichen Quiz entfernt.")
            }
        }
    }

    private var editorPanel: some View {
        RatsSectionPanel(
            editingID == nil ? "Neue Karte" : "Karte bearbeiten",
            detail: category == "schaetzen"
                ? "Lege eine Zahl und einen sinnvollen Ratebereich fest."
                : "Fülle zwei bis vier Antworten aus und markiere die richtige.",
            symbol: editingID == nil ? "plus.bubble" : "pencil.line"
        ) {
            VStack(alignment: .leading, spacing: 14) {
                RatsLabeledField(label: "Frage", hint: "mindestens 5 Zeichen") {
                    TextField("Wie hieß der Hafenkran …?", text: $question, axis: .vertical)
                        .lineLimit(2...5)
                        .textFieldStyle(.plain)
                        .padding(.vertical, 9)
                }

                RatsLabeledField(label: "Kategorie") {
                    Picker("Kategorie", selection: $category) {
                        ForEach(categories, id: \.self) { value in
                            Text(quizCategoryLabel(value)).tag(value)
                        }
                    }
                    .pickerStyle(.menu)
                    .tint(RatsColor.primary)
                    .frame(maxWidth: .infinity, alignment: .leading)
                }

                if category == "schaetzen" {
                    estimateFields
                } else {
                    answerFields
                }

                RatsLabeledField(label: "Ort", hint: "optional") {
                    Picker("Ort", selection: $stadtteil) {
                        Text("Stadtweit").tag("")
                        ForEach(areas?.stadtteile ?? []) { place in
                            Text(place.label ?? place.key).tag(place.key)
                        }
                    }
                    .pickerStyle(.menu)
                    .tint(RatsColor.primary)
                    .frame(maxWidth: .infinity, alignment: .leading)
                }

                RatsLabeledField(label: "Erklärung", hint: "erscheint nach der Antwort") {
                    TextField("Warum ist diese Antwort richtig?", text: $explanation, axis: .vertical)
                        .lineLimit(2...5)
                        .textFieldStyle(.plain)
                        .padding(.vertical, 9)
                }

                HStack(spacing: 10) {
                    Button("Abbrechen") { cancelEditing() }
                        .buttonStyle(SecondaryButtonStyle())
                    Button { Task { await save() } } label: {
                        Label(isSaving ? "Speichert …" : editingID == nil ? "Karte speichern" : "Änderungen speichern", systemImage: "tray.and.arrow.down")
                            .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(PrimaryButtonStyle())
                    .disabled(isSaving || !isValid)
                    .opacity(isSaving || !isValid ? 0.5 : 1)
                }
            }
        }
    }

    private var answerFields: some View {
        VStack(alignment: .leading, spacing: 9) {
            HStack(alignment: .firstTextBaseline) {
                Text("Antworten")
                    .font(RatsFont.body(12, weight: .semibold))
                Spacer()
                Text("richtige Antwort markieren")
                    .font(RatsFont.body(10))
                    .foregroundStyle(RatsColor.muted)
            }
            ForEach(answers.indices, id: \.self) { index in
                HStack(spacing: 8) {
                    Button { correctIndex = index } label: {
                        Image(systemName: correctIndex == index ? "checkmark.circle.fill" : "circle")
                            .font(.system(size: 20))
                            .foregroundStyle(correctIndex == index ? RatsColor.success : RatsColor.muted)
                    }
                    .buttonStyle(.plain)
                    .accessibilityLabel("Antwort \(index + 1) als richtig markieren")
                    TextField("Antwort \(index + 1)", text: answerBinding(index))
                        .textFieldStyle(.plain)
                    if answers.count > 2 {
                        Button { removeAnswer(at: index) } label: {
                            Image(systemName: "minus.circle")
                                .foregroundStyle(RatsColor.muted)
                        }
                        .buttonStyle(.plain)
                        .accessibilityLabel("Antwort \(index + 1) entfernen")
                    }
                }
                .font(RatsFont.body(15))
                .padding(.horizontal, 12)
                .frame(minHeight: 46)
                .background(correctIndex == index ? RatsColor.successTint : RatsColor.stage)
                .overlay(
                    RoundedRectangle(cornerRadius: 10, style: .continuous)
                        .stroke(correctIndex == index ? RatsColor.success.opacity(0.45) : RatsColor.border)
                )
                .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
            }
            if answers.count < 4 {
                Button { answers.append("") } label: {
                    Label("Antwort hinzufügen", systemImage: "plus")
                }
                .font(RatsFont.body(12, weight: .semibold))
                .foregroundStyle(RatsColor.primary)
            }
        }
    }

    private var estimateFields: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(alignment: .top, spacing: 10) {
                RatsLabeledField(label: "Richtige Zahl") {
                    TextField("172000", text: $answerValue)
                        .keyboardType(.decimalPad)
                        .textFieldStyle(.plain)
                }
                RatsLabeledField(label: "Einheit", hint: "optional") {
                    TextField("Einwohner", text: $unit)
                        .textFieldStyle(.plain)
                }
            }
            Toggle(isOn: $rangeManual.animation(.easeInOut(duration: 0.2))) {
                VStack(alignment: .leading, spacing: 2) {
                    Text("Ratebereich selbst festlegen")
                        .font(RatsFont.body(13, weight: .semibold))
                    Text(rangeManual ? "Die richtige Zahl muss zwischen beiden Grenzen liegen." : autoRangeDescription)
                        .font(RatsFont.body(10))
                        .foregroundStyle(RatsColor.secondary)
                }
            }
            .tint(RatsColor.primary)
            if rangeManual {
                HStack(alignment: .top, spacing: 10) {
                    RatsLabeledField(label: "Von") {
                        TextField("0", text: $rangeMin)
                            .keyboardType(.decimalPad)
                            .textFieldStyle(.plain)
                    }
                    RatsLabeledField(label: "Bis") {
                        TextField("350000", text: $rangeMax)
                            .keyboardType(.decimalPad)
                            .textFieldStyle(.plain)
                    }
                }
            }
        }
        .padding(13)
        .background(RatsColor.primary.opacity(0.045))
        .overlay(RoundedRectangle(cornerRadius: 13, style: .continuous).stroke(RatsColor.primary.opacity(0.16)))
        .clipShape(RoundedRectangle(cornerRadius: 13, style: .continuous))
    }

    private func ownQuestionCard(_ entry: OwnQuizQuestion) -> some View {
        VStack(alignment: .leading, spacing: 11) {
            HStack(alignment: .top, spacing: 10) {
                VStack(alignment: .leading, spacing: 6) {
                    Text(entry.question)
                        .font(RatsFont.body(15, weight: .semibold))
                    QuizFlowLayout(spacing: 6) {
                        Pill(quizCategoryLabel(entry.category), symbol: entry.qtype == "estimate" ? "slider.horizontal.3" : "checkmark.circle")
                        if let place = entry.stadtteil { Pill(place, symbol: "mappin") }
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                HStack(spacing: 2) {
                    Button { beginEdit(entry) } label: {
                        Image(systemName: "pencil")
                            .frame(width: 34, height: 34)
                    }
                    .buttonStyle(.plain)
                    .foregroundStyle(RatsColor.primary)
                    .accessibilityLabel("Karte bearbeiten")
                    Button { pendingDelete = entry } label: {
                        Image(systemName: "trash")
                            .frame(width: 34, height: 34)
                    }
                    .buttonStyle(.plain)
                    .foregroundStyle(RatsColor.danger)
                    .accessibilityLabel("Karte löschen")
                }
            }
            HStack(spacing: 7) {
                Image(systemName: "chart.line.uptrend.xyaxis")
                Text(practiceLabel(entry))
            }
            .font(RatsFont.body(11))
            .foregroundStyle(RatsColor.secondary)
        }
        .ratsCard()
    }

    private func practiceLabel(_ entry: OwnQuizQuestion) -> String {
        guard entry.practiced > 0 else { return "Noch nie geübt" }
        let percentage = Int((Double(entry.correctCount) / Double(entry.practiced) * 100).rounded())
        return "\(entry.practiced)× geübt · \(percentage) % richtig"
    }

    private var validAnswers: [String] {
        answers.map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }.filter { !$0.isEmpty }
    }

    private var parsedAnswerValue: Double? { parseNumber(answerValue) }
    private var parsedRangeMin: Double? { parseNumber(rangeMin) }
    private var parsedRangeMax: Double? { parseNumber(rangeMax) }

    private var isValid: Bool {
        guard question.trimmingCharacters(in: .whitespacesAndNewlines).count >= 5 else { return false }
        if category == "schaetzen" {
            guard let value = parsedAnswerValue else { return false }
            if rangeManual {
                guard let lower = parsedRangeMin, let upper = parsedRangeMax else { return false }
                return upper > lower && lower <= value && value <= upper
            }
            return true
        }
        return validAnswers.count >= 2 && answers.indices.contains(correctIndex)
            && !answers[correctIndex].trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
    }

    private var autoRangeDescription: String {
        guard let value = parsedAnswerValue else { return "Ratslotse berechnet passende Grenzen aus der Zahl." }
        let range = automaticRange(for: value, unit: unit)
        return "Automatisch: \(range.lower.formatted()) bis \(range.upper.formatted()) \(unit)"
    }

    private func answerBinding(_ index: Int) -> Binding<String> {
        Binding(
            get: { answers.indices.contains(index) ? answers[index] : "" },
            set: { if answers.indices.contains(index) { answers[index] = $0 } }
        )
    }

    private func removeAnswer(at index: Int) {
        guard answers.count > 2, answers.indices.contains(index) else { return }
        answers.remove(at: index)
        if correctIndex == index { correctIndex = 0 }
        else if correctIndex > index { correctIndex -= 1 }
    }

    private func beginNew() {
        editingID = nil
        question = ""
        answers = ["", ""]
        correctIndex = 0
        category = "geschichte"
        stadtteil = ""
        explanation = ""
        answerValue = ""
        unit = ""
        rangeManual = false
        rangeMin = ""
        rangeMax = ""
        error = nil
        withAnimation(.easeInOut(duration: 0.2)) { showForm = true }
    }

    private func beginEdit(_ entry: OwnQuizQuestion) {
        editingID = entry.id
        question = entry.question
        answers = entry.options.isEmpty ? ["", ""] : entry.options
        while answers.count < 2 { answers.append("") }
        correctIndex = min(entry.correctIndex, answers.count - 1)
        category = entry.category
        stadtteil = entry.stadtteil ?? ""
        explanation = entry.explanation ?? ""
        answerValue = entry.answerValue.map { String($0) } ?? ""
        unit = entry.unit ?? ""
        rangeManual = entry.qtype == "estimate" && entry.rangeMin != nil && entry.rangeMax != nil
        rangeMin = entry.rangeMin.map { String($0) } ?? ""
        rangeMax = entry.rangeMax.map { String($0) } ?? ""
        error = nil
        withAnimation(.easeInOut(duration: 0.2)) { showForm = true }
    }

    private func cancelEditing() {
        withAnimation(.easeInOut(duration: 0.2)) { showForm = false }
        editingID = nil
        error = nil
    }

    private func load() async {
#if DEBUG
        if let debugMode = ProcessInfo.processInfo.environment["RATSLOTSE_DEBUG_QUIZ_OWN"] {
            areas = QuizAreas(
                wahlbereiche: [],
                stadtteile: ["Bloherfelde", "Eversten", "Kreyenbrück", "Nadorst", "Osternburg", "Zentrum"].enumerated().map { offset, name in
                    QuizArea(key: name, label: name, questions: 8 + offset, points: offset, stadtteile: nil, stadtteil: nil)
                },
                themen: [],
                categories: categories
            )
            questions = [
                OwnQuizQuestion(
                    id: 1,
                    question: "Welcher Platz liegt direkt vor dem Oldenburger Rathaus?",
                    options: ["Schlossplatz", "Marktplatz", "Pferdemarkt"],
                    correctIndex: 1,
                    stadtteil: "Zentrum",
                    category: "orte",
                    explanation: "Der Marktplatz bildet gemeinsam mit Rathaus und Lambertikirche das historische Zentrum.",
                    qtype: "mc",
                    answerValue: nil,
                    unit: nil,
                    rangeMin: nil,
                    rangeMax: nil,
                    practiced: 7,
                    correctCount: 5
                ),
                OwnQuizQuestion(
                    id: 2,
                    question: "Wie viele Einwohnerinnen und Einwohner hat Oldenburg ungefähr?",
                    options: [],
                    correctIndex: 0,
                    stadtteil: nil,
                    category: "schaetzen",
                    explanation: nil,
                    qtype: "estimate",
                    answerValue: 176_000,
                    unit: "Einwohner",
                    rangeMin: 0,
                    rangeMax: 350_000,
                    practiced: 3,
                    correctCount: 2
                ),
            ]
            if debugMode == "new" { beginNew() }
            if debugMode == "edit", let first = questions.first { beginEdit(first) }
            if debugMode == "estimate", let estimate = questions.last { beginEdit(estimate) }
            return
        }
#endif
        do {
            async let ownRequest: OwnQuizQuestions = model.api.get("/api/quiz/own")
            async let areaRequest: QuizAreas = model.api.get("/api/quiz/areas")
            let (ownResponse, areaResponse) = try await (ownRequest, areaRequest)
            questions = ownResponse.questions
            areas = areaResponse
            if questions.isEmpty && editingID == nil { showForm = true }
        } catch { self.error = error.localizedDescription }
    }

    private func save() async {
        struct Body: Codable, Sendable {
            let question: String
            let options: [String]
            let correct_index: Int
            let stadtteil: String?
            let category: String
            let explanation: String?
            let answer_value: Double?
            let unit: String?
            let range_min: Double?
            let range_max: Double?
        }

        guard isValid else { return }
        let isEstimate = category == "schaetzen"
        let options = isEstimate ? [] : validAnswers
        let mappedCorrectIndex: Int
        if isEstimate {
            mappedCorrectIndex = 0
        } else {
            mappedCorrectIndex = answers[..<correctIndex]
                .filter { !$0.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty }.count
        }
        let autoRange = parsedAnswerValue.map { automaticRange(for: $0, unit: unit) }
        let body = Body(
            question: question.trimmingCharacters(in: .whitespacesAndNewlines),
            options: options,
            correct_index: mappedCorrectIndex,
            stadtteil: stadtteil.isEmpty ? nil : stadtteil,
            category: category,
            explanation: explanation.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ? nil : explanation.trimmingCharacters(in: .whitespacesAndNewlines),
            answer_value: isEstimate ? parsedAnswerValue : nil,
            unit: isEstimate && !unit.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ? unit.trimmingCharacters(in: .whitespacesAndNewlines) : nil,
            range_min: isEstimate ? (rangeManual ? parsedRangeMin : autoRange?.lower) : nil,
            range_max: isEstimate ? (rangeManual ? parsedRangeMax : autoRange?.upper) : nil
        )

        isSaving = true
        defer { isSaving = false }
        do {
            if let editingID {
                try await model.api.sendVoid("/api/quiz/own/\(editingID)", method: .put, body: body)
            } else {
                try await model.api.sendVoid("/api/quiz/own", body: body)
            }
            cancelEditing()
            await load()
            await onChange()
        } catch { self.error = error.localizedDescription }
    }

    private func delete(_ entry: OwnQuizQuestion) async {
        pendingDelete = nil
        do {
            try await model.api.sendVoid("/api/quiz/own/\(entry.id)", method: .delete)
            if editingID == entry.id { cancelEditing() }
            await load()
            await onChange()
        } catch { self.error = error.localizedDescription }
    }

    private func parseNumber(_ value: String) -> Double? {
        Double(value.replacingOccurrences(of: ",", with: "."))
    }

    private func automaticRange(for value: Double, unit: String) -> (lower: Double, upper: Double) {
        let normalizedUnit = unit.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        if ["jahr", "jahre"].contains(normalizedUnit), abs(value) >= 100 {
            let rounded = value.rounded()
            return (max(0, rounded - 50), rounded + 50)
        }
        let rawUpper = max(abs(value) * 2, 1)
        let exponent = max(0, floor(log10(rawUpper)) - 1)
        let step = pow(10, exponent)
        let upper = max((rawUpper / step).rounded() * step, abs(value) + step)
        return (0, upper)
    }
}
