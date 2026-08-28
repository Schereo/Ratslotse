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
                    MonoKicker(kicker)
                    Text(person?.name ?? preview.title).font(RatsFont.title(28))
                    if let person {
                        PersonProfileOverview(model: model, person: person)
                    } else {
                        Text(profileDescription ?? preview.description)
                            .font(RatsFont.body(16))
                            .foregroundStyle(RatsColor.bodyText)
                            .lineSpacing(4)
                            .ratsCard()
                    }

                    if let coordinate {
                        Map(initialPosition: .region(MKCoordinateRegion(
                            center: coordinate,
                            span: MKCoordinateSpan(latitudeDelta: 0.025, longitudeDelta: 0.025)
                        ))) {
                            Marker(preview.title, coordinate: coordinate)
                                .tint(RatsColor.signal)
                        }
                        .frame(height: 250)
                        .clipShape(RoundedRectangle(cornerRadius: RatsRadius.card))
                        .overlay(RoundedRectangle(cornerRadius: RatsRadius.card).stroke(RatsColor.border))
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
            .frame(maxWidth: 760, alignment: .leading)
            .padding(18)
        }
        .background(RatsColor.page)
        .navigationTitle(kicker.capitalized)
        .navigationBarTitleDisplayMode(.inline)
        .task { await load() }
    }

    private var kicker: String {
        switch kind { case .person: "Person"; case .topic: "Thema im Rat"; case .place: "Ort in Oldenburg" }
    }

    private var route: AppRoute {
        switch kind { case .person: .person(slug: key); case .topic: .topic(slug: key); case .place: .place(id: key) }
    }

    private func load() async {
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

private struct PublicPersonProfile: Codable, Sendable {
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
    let currentAffiliation: String?
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
        [party, currentAffiliation, organisation]
            .compactMap { $0?.trimmingCharacters(in: .whitespacesAndNewlines) }
            .first { !$0.isEmpty }
    }
}

private struct PersonProfileOverview: View {
    let model: AppModel
    let person: PublicPersonProfile

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack(spacing: 14) {
                Image(systemName: "person.crop.circle.fill")
                    .font(.system(size: 50))
                    .foregroundStyle(RatsColor.primary)
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

private struct QuizArea: Codable, Sendable, Identifiable {
    var id: String { key }
    let key: String
    let label: String?
    let questions: Int
}

private struct QuizAreas: Codable, Sendable {
    let wahlbereiche: [QuizArea]
    let stadtteile: [QuizArea]
    let themen: [QuizArea]
    let categories: [String]
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
        case .own: "Eigene Fragen"
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

private struct OwnQuizQuestion: Codable, Sendable, Identifiable {
    let id: Int
    let question: String
    let options: [String]
    let correctIndex: Int
    let explanation: String?
    let practiced: Int
    let correctCount: Int

    enum CodingKeys: String, CodingKey {
        case id, question, options, explanation, practiced
        case correctIndex = "correct_index"
        case correctCount = "correct_count"
    }
}

private struct OwnQuizQuestions: Codable, Sendable { let questions: [OwnQuizQuestion] }

struct QuizView: View {
    let model: AppModel
    let area: String?
    @State private var areas: QuizAreas?
    @State private var selectedArea: String?
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
    @State private var showOwnEditor = false
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
            .frame(maxWidth: 620, alignment: .leading)
            .padding(18)
        }
        .background(RatsColor.page)
        .navigationTitle("Oldenburg-Quiz")
        .navigationBarTitleDisplayMode(.inline)
        .task { await loadAreas() }
        .sheet(isPresented: $showOwnEditor) {
            OwnQuizEditor(model: model) { await loadDashboard() }
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
            }
            LazyVGrid(columns: [.init(.flexible()), .init(.flexible())], spacing: 10) {
                QuizModeButton(title: "Täglich", detail: daily?.done == nil ? "Heute offen" : "Heute erledigt", symbol: "bolt.fill") {
                    Task { await startDaily() }
                }
                QuizModeButton(title: "Fehler üben", detail: "\(stats?.wrong ?? 0) offen", symbol: "arrow.counterclockwise") {
                    Task { await startSpecial(path: "/api/quiz/review", mode: .review) }
                }
                QuizModeButton(title: "Karten-Quiz", detail: "Stadtteile finden", symbol: "map") {
                    showMapQuiz = true
                }
                QuizModeButton(title: "Eigene Fragen", detail: "\(own.count) gespeichert", symbol: "pencil") {
                    if own.isEmpty { showOwnEditor = true }
                    else { Task { await startSpecial(path: "/api/quiz/own/round", mode: .own) } }
                }
            }
            if !own.isEmpty {
                Button("Eigene Fragen verwalten") { showOwnEditor = true }
                    .font(RatsFont.body(13, weight: .semibold))
            }
            Divider().overlay(RatsColor.separator)
            MonoKicker("Neues Spiel")
            if let areas {
                Picker("Gebiet", selection: $selectedArea) {
                    Text("Gebiet wählen").tag(Optional<String>.none)
                    ForEach(areas.wahlbereiche) { entry in
                        Text(entry.label ?? "Wahlbereich \(entry.key)").tag(Optional("wahlbereich:\(entry.key)"))
                    }
                    ForEach(areas.stadtteile.prefix(30)) { entry in
                        Text(entry.label ?? entry.key).tag(Optional("stadtteil:\(entry.key)"))
                    }
                }
                .pickerStyle(.menu)
                Button("Quiz starten") { Task { await start() } }
                    .buttonStyle(PrimaryButtonStyle())
                    .disabled(selectedArea == nil)
            } else { ProgressView("Gebiete laden …") }
        }
        .ratsCard()
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
            Image(systemName: correct * 2 >= round.count ? "trophy.fill" : "flag.checkered")
                .font(.system(size: 44)).foregroundStyle(RatsColor.signal)
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

    private func loadAreas() async {
        guard areas == nil else { return }
        do {
            areas = try await model.api.get("/api/quiz/areas")
            selectedArea = area ?? areas?.wahlbereiche.first.map { "wahlbereich:\($0.key)" }
            await loadDashboard()
        } catch { self.error = error.localizedDescription }
    }

    private func start() async {
        guard let selectedArea else { return }
        do {
            let response: QuizRound = try await model.api.get(
                "/api/quiz/round",
                query: [.init(name: "areas", value: selectedArea), .init(name: "n", value: "10")]
            )
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

private struct OwnQuizEditor: View {
    let model: AppModel
    let onChange: () async -> Void
    @Environment(\.dismiss) private var dismiss
    @State private var questions: [OwnQuizQuestion] = []
    @State private var question = ""
    @State private var answers = ["", "", "", ""]
    @State private var correctIndex = 0
    @State private var explanation = ""
    @State private var isSaving = false
    @State private var error: String?

    var body: some View {
        NavigationStack {
            List {
                Section("Neue Frage") {
                    TextField("Frage", text: $question, axis: .vertical)
                        .lineLimit(2...5)
                    ForEach(answers.indices, id: \.self) { index in
                        HStack {
                            Button {
                                correctIndex = index
                            } label: {
                                Image(systemName: correctIndex == index ? "checkmark.circle.fill" : "circle")
                                    .foregroundStyle(correctIndex == index ? RatsColor.success : RatsColor.muted)
                            }
                            .buttonStyle(.plain)
                            TextField("Antwort \(index + 1)", text: $answers[index])
                        }
                    }
                    TextField("Erklärung (optional)", text: $explanation, axis: .vertical)
                    Button(isSaving ? "Speichert …" : "Frage speichern") { Task { await save() } }
                        .disabled(isSaving || question.trimmingCharacters(in: .whitespacesAndNewlines).count < 5 || validAnswers.count < 2)
                }
                Section("Gespeichert") {
                    if questions.isEmpty {
                        Text("Noch keine eigenen Fragen.").foregroundStyle(RatsColor.secondary)
                    }
                    ForEach(questions) { entry in
                        VStack(alignment: .leading, spacing: 4) {
                            Text(entry.question).font(RatsFont.body(14, weight: .semibold))
                            Text("\(entry.practiced)× geübt · \(entry.correctCount)× richtig")
                                .font(RatsFont.body(11)).foregroundStyle(RatsColor.secondary)
                        }
                    }
                    .onDelete { offsets in Task { await delete(offsets) } }
                }
                if let error { Section { Text(error).foregroundStyle(RatsColor.danger) } }
            }
            .navigationTitle("Eigene Fragen")
            .toolbar {
                ToolbarItem(placement: .confirmationAction) { Button("Fertig") { dismiss() } }
            }
            .task { await load() }
        }
    }

    private var validAnswers: [String] {
        answers.map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }.filter { !$0.isEmpty }
    }

    private func load() async {
        do {
            let response: OwnQuizQuestions = try await model.api.get("/api/quiz/own")
            questions = response.questions
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
        }
        let options = validAnswers
        let chosen = answers[correctIndex].trimmingCharacters(in: .whitespacesAndNewlines)
        guard !chosen.isEmpty else {
            error = "Bitte markiere eine ausgefüllte Antwort als richtig."
            return
        }
        let mappedCorrectIndex = answers[..<correctIndex]
            .filter { !$0.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty }.count
        isSaving = true
        defer { isSaving = false }
        do {
            try await model.api.sendVoid(
                "/api/quiz/own",
                body: Body(
                    question: question.trimmingCharacters(in: .whitespacesAndNewlines),
                    options: options,
                    correct_index: mappedCorrectIndex,
                    stadtteil: nil,
                    category: "ratspolitik",
                    explanation: explanation.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ? nil : explanation
                )
            )
            question = ""
            answers = ["", "", "", ""]
            correctIndex = 0
            explanation = ""
            await load()
            await onChange()
        } catch { self.error = error.localizedDescription }
    }

    private func delete(_ offsets: IndexSet) async {
        for index in offsets {
            try? await model.api.sendVoid("/api/quiz/own/\(questions[index].id)", method: .delete)
        }
        await load()
        await onChange()
    }
}
