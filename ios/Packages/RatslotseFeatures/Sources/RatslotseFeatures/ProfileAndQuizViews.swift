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
    @State private var error: String?

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                if let preview {
                    profileOverview(preview)

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
        .task { await load() }
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
            MonoKicker(kicker)
            Text(person?.name ?? preview.title)
                .font(RatsFont.title(usesTabletOverview ? 34 : 28))
            if let person {
                PersonProfileOverview(
                    model: model,
                    person: person,
                    usesWideLayout: usesWidePersonLayout
                )
            } else {
                Text(profileDescription ?? preview.description)
                    .font(RatsFont.body(16))
                    .foregroundStyle(RatsColor.bodyText)
                    .lineSpacing(4)
                    .ratsCard()
            }
        }
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
                    committees: [
                        .init(committee: "Verkehrsausschuss", n: 9, chair: true),
                        .init(committee: "Sozialausschuss", n: 7, chair: false),
                    ],
                    recent: [
                        .init(ksinr: 8101, committee: "Verkehrsausschuss", sessionDate: "2026-08-28"),
                        .init(ksinr: 8102, committee: "Sozialausschuss", sessionDate: "2026-08-21"),
                    ]
                )
            case .topic:
                preview = LinkPreview(
                    title: "Sichere Schulwege",
                    description: "Beschlüsse, Projekte und Debatten rund um sichere Wege zu Oldenburgs Schulen."
                )
            case .place:
                preview = LinkPreview(
                    title: "Pferdemarkt",
                    description: "Was der Rat für den Pferdemarkt und sein direktes Umfeld plant und entscheidet."
                )
                coordinate = CLLocationCoordinate2D(latitude: 53.1466, longitude: 8.2147)
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

    let name: String
    let party: String?
    let currentAffiliation: Affiliation?
    let art: String?
    let organisation: String?
    let nSessions: Int
    let activeFrom: String?
    let activeTo: String?
    let committees: [Committee]
    let recent: [RecentSession]

    enum CodingKeys: String, CodingKey {
        case name, party, art, organisation, committees, recent
        case currentAffiliation = "current_affiliation"
        case nSessions = "n_sessions"
        case activeFrom = "active_from"
        case activeTo = "active_to"
    }

    var roleLabel: String {
        switch art {
        case "rat": "Ratsmitglied"
        case "beratend": "Beratendes Mitglied"
        case "verwaltung": "Stadtverwaltung"
        default: "Person im Oldenburger Rat"
        }
    }

    var affiliation: String? {
        [party, currentAffiliation?.label, organisation]
            .compactMap { $0?.trimmingCharacters(in: .whitespacesAndNewlines) }
            .first { !$0.isEmpty }
    }
}

private struct PersonProfileOverview: View {
    let model: AppModel
    let person: PublicPersonProfile
    let usesWideLayout: Bool

    @ViewBuilder
    var body: some View {
        if usesWideLayout {
            HStack(alignment: .top, spacing: 20) {
                VStack(alignment: .leading, spacing: 16) {
                    identityCard
                    recentSessionsCard
                }
                .frame(maxWidth: 390, alignment: .topLeading)

                VStack(alignment: .leading, spacing: 16) {
                    committeesCard
                }
                .frame(maxWidth: .infinity, alignment: .topLeading)
            }
        } else {
            identityCard
            committeesCard
            recentSessionsCard
        }
    }

    private var identityCard: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack(spacing: 14) {
                RatsGlyphView(glyph: .profile, color: RatsColor.primaryText, lineWidth: 1.55)
                    .frame(width: 34, height: 34)
                    .frame(width: 58, height: 58)
                    .background(RatsColor.primary)
                    .clipShape(Circle())
                    .accessibilityHidden(true)
                VStack(alignment: .leading, spacing: 5) {
                    Text(person.roleLabel)
                        .font(RatsFont.body(16, weight: .semibold))
                    if let affiliation = person.affiliation {
                        Pill(affiliation, symbol: "person.3")
                    }
                    if let period {
                        Text(period)
                            .font(RatsFont.mono(10))
                            .foregroundStyle(RatsColor.muted)
                    }
                }
            }

            HStack(spacing: 24) {
                metric(value: person.nSessions, label: "Sitzungen")
                metric(value: person.committees.count, label: "Gremien")
                let chaired = person.committees.filter(\.chair).count
                if chaired > 0 { metric(value: chaired, label: "Vorsitze") }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .ratsCard()
    }

    @ViewBuilder
    private var committeesCard: some View {
        if !person.committees.isEmpty {
            VStack(alignment: .leading, spacing: 12) {
                MonoKicker("Gremien", trailing: "\(person.committees.count)")
                ForEach(person.committees) { committee in
                    HStack(alignment: .firstTextBaseline) {
                        VStack(alignment: .leading, spacing: 3) {
                            Text(committee.committee)
                                .font(RatsFont.body(14, weight: .semibold))
                            Text("\(committee.n) \(committee.n == 1 ? "Sitzung" : "Sitzungen")")
                                .font(RatsFont.mono(10))
                                .foregroundStyle(RatsColor.muted)
                        }
                        Spacer()
                        if committee.chair { Pill("Vorsitz", symbol: "star") }
                    }
                    if committee.id != person.committees.last?.id { Divider().overlay(RatsColor.separator) }
                }
            }
            .ratsCard()
        }
    }

    @ViewBuilder
    private var recentSessionsCard: some View {
        if !person.recent.isEmpty {
            VStack(alignment: .leading, spacing: 12) {
                MonoKicker("Letzte Sitzungen")
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
            .ratsCard()
        }
    }

    private var period: String? {
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
    let total: Total
    let wrong: Int
    let streak: Int
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

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                if round.isEmpty {
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
                HStack(spacing: 18) {
                    QuizMetric(value: "\(stats.total.points)", label: "Punkte")
                    QuizMetric(value: "\(Int((Double(stats.total.correct) / Double(stats.total.answered)) * 100)) %", label: "richtig")
                    QuizMetric(value: "\(stats.streak)", label: "Tage-Serie")
                }
                .padding(14)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(RatsColor.primary.opacity(0.06))
                .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
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
        stats = QuizStats(total: .init(points: 148, answered: 63, correct: 47), wrong: 6, streak: 4)
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
