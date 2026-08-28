import AVFoundation
import Charts
import MapKit
import RatslotseAPI
import RatslotseDesign
import SwiftUI
import UIKit

private struct QuestionTurn: Identifiable {
    let id = UUID()
    let question: String
    var answer = ""
    var sources: [DecisionSummary] = []
    var evidence: [String: JSONValue] = [:]
    var suggestions: [String] = []
    var status: String?
    var error: String?
}

struct QuestionsView: View {
    let model: AppModel
    @State private var input = ""
    @State private var turns: [QuestionTurn] = []
    @State private var streamTask: Task<Void, Never>?
    @State private var rateLimitUntil: Date?
    @State private var showDeepResearch = false
    @State private var showConversations = false

    private var isSending: Bool { streamTask != nil }
    private var shouldAutoScroll: Bool {
#if DEBUG
        ProcessInfo.processInfo.environment["RATSLOTSE_DEBUG_QUESTION_FIXTURE"] != "1"
#else
        true
#endif
    }

    var body: some View {
        VStack(spacing: 0) {
            HStack(spacing: 10) {
                VStack(alignment: .leading, spacing: 2) {
                    Text("Frag den Rat")
                        .font(RatsFont.title(24))
                    Text("Antworten mit amtlichen Quellen")
                        .font(RatsFont.body(12))
                        .foregroundStyle(RatsColor.secondary)
                }
                Spacer(minLength: 0)
                Button { showConversations = true } label: {
                    RatsGlyphView(glyph: .history, color: RatsColor.bodyText)
                        .frame(width: 20, height: 20)
                        .frame(width: 40, height: 40)
                        .background(RatsColor.card)
                        .overlay(Circle().stroke(RatsColor.border))
                        .clipShape(Circle())
                }
                .accessibilityLabel("Gespräche")
                Button { showDeepResearch = true } label: {
                    RatsGlyphView(
                        glyph: .research,
                        color: model.hasRecoverableResearch ? RatsColor.signal : RatsColor.bodyText
                    )
                        .frame(width: 20, height: 20)
                        .frame(width: 40, height: 40)
                        .background(RatsColor.card)
                        .overlay(Circle().stroke(RatsColor.border))
                        .clipShape(Circle())
                }
                .accessibilityLabel("Gründlich recherchieren")
            }
            .foregroundStyle(RatsColor.text)
            .padding(.horizontal, 18)
            .padding(.top, 16)
            .padding(.bottom, 5)

            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 26) {
                        if turns.isEmpty { EmptyQuestionsView(select: ask) }
                        ForEach(turns) { turn in
                            QuestionTurnView(turn: turn, model: model, ask: ask)
                                .id(turn.id)
                        }
                    }
                    .frame(maxWidth: 780, alignment: .leading)
                    .padding(.horizontal, 18)
                    .padding(.vertical, 24)
                }
                .onChange(of: turns.count) { _, _ in
                    guard shouldAutoScroll else { return }
                    if let id = turns.last?.id { withAnimation { proxy.scrollTo(id, anchor: .bottom) } }
                }
            }

            VStack(spacing: 0) {
                Divider().overlay(RatsColor.border)
                if let rateLimitUntil, rateLimitUntil > .now {
                    TimelineView(.periodic(from: .now, by: 1)) { context in
                        let seconds = max(1, Int(rateLimitUntil.timeIntervalSince(context.date).rounded(.up)))
                        Label("Neue Frage in \(seconds) s", systemImage: "hourglass")
                            .font(RatsFont.body(11, weight: .semibold))
                            .foregroundStyle(RatsColor.warning)
                    }
                    .padding(.top, 7)
                }
                QuestionComposer(text: $input, isSending: isSending, action: submitOrStop)
                    .frame(maxWidth: 780)
                    .padding(.horizontal, 14)
                    .padding(.top, 10)
                    .padding(.bottom, 8)
                    .background(.ultraThinMaterial)
            }
        }
        .background(RatsColor.stage)
        .navigationTitle("Frag den Rat")
        .toolbarTitleDisplayMode(.inline)
        .onAppear {
            if !model.questionPrefill.isEmpty {
                input = model.questionPrefill
                model.questionPrefill = ""
            }
#if DEBUG
            if turns.isEmpty,
               ProcessInfo.processInfo.environment["RATSLOTSE_DEBUG_QUESTION_FIXTURE"] == "1",
               let fixture = debugQuestionFixture() {
                turns = [fixture]
            }
            switch ProcessInfo.processInfo.environment["RATSLOTSE_DEBUG_QUESTION_SHEET"] {
            case "research": showDeepResearch = true
            case "conversations": showConversations = true
            default: break
            }
#endif
        }
        .onDisappear { streamTask?.cancel(); streamTask = nil }
        .sheet(isPresented: $showDeepResearch) {
            DeepResearchView(model: model, initialQuestion: input)
                .ratsLargeSheet()
        }
        .sheet(isPresented: $showConversations) {
            ConversationsView(model: model)
                .ratsLargeSheet()
        }
    }

    private func submitOrStop() {
        if isSending {
            streamTask?.cancel()
            streamTask = nil
            if let last = turns.indices.last { turns[last].status = "Abgebrochen – deine Frage bleibt erhalten." }
            return
        }
        ask(input)
    }

    private func ask(_ raw: String) {
        let question = raw.trimmingCharacters(in: .whitespacesAndNewlines)
        guard question.count >= 4 else { return }
        if let rateLimitUntil, rateLimitUntil > .now { return }
        input = ""
        let history = turns.suffix(4).map {
            AskRound(frage: $0.question, antwort: String($0.answer.prefix(600)))
        }
        turns.append(QuestionTurn(question: question, status: "Beschlüsse durchsuchen …"))
        let index = turns.count - 1
        streamTask = Task {
            defer { streamTask = nil }
            do {
                let request = try await model.api.makeStreamingRequest(
                    "/api/council/ask", body: AskRequest(question: question, verlauf: history)
                )
                for try await event in model.sse.events(for: request) {
                    guard !Task.isCancelled, turns.indices.contains(index) else { break }
                    switch event.type {
                    case "step": turns[index].status = progressText(event.step)
                    case "sources":
                        turns[index].evidence = event.fields
                        turns[index].sources = event.fields["sources"]?.array?.compactMap {
                            try? $0.decoded(DecisionSummary.self)
                        } ?? []
                        turns[index].status = "Antwort formulieren …"
                    case "token":
                        turns[index].status = nil
                        turns[index].answer += event.text ?? ""
                    case "replace":
                        turns[index].status = nil
                        turns[index].answer = event.text ?? turns[index].answer
                    case "suggestions": turns[index].suggestions = event.suggestions
                    case "abbruch":
                        turns[index].status = "Die Verbindung brach ab. Die bisherige Antwort bleibt sichtbar."
                        input = question
                    case "error": throw APIError(statusCode: 0, message: event.text ?? "Die Antwort ist abgebrochen.", retryAfter: nil)
                    case "done": turns[index].status = nil
                    default: break
                    }
                }
            } catch is CancellationError {
                input = question
            } catch let error as APIError {
                turns[index].error = error.message
                turns[index].status = nil
                input = question
                if let retry = error.retryAfter { rateLimitUntil = .now.addingTimeInterval(retry) }
            } catch {
                turns[index].error = error.localizedDescription
                turns[index].status = nil
                input = question
            }
        }
    }

    private func progressText(_ step: String?) -> String {
        switch step {
        case "expand": "Frage einordnen …"
        case "retrieve": "Protokolle querlesen …"
        case "rerank": "Die besten Belege auswählen …"
        default: "Im Rat nachsehen …"
        }
    }

#if DEBUG
    private func debugQuestionFixture() -> QuestionTurn? {
        let raw = #"""
        {
          "source": {
            "id": 1,
            "title": "Neue Busspuren für Oldenburg",
            "committee": "Rat der Stadt",
            "session_date": "2026-08-26",
            "item_number": "Ö 10",
            "outcome": "angenommen",
            "summary": "Zwei Busspuren sollen den Nahverkehr schneller und verlässlicher machen.",
            "amount_eur": 8900000,
            "vote": "mehrheitlich",
            "no_votes": 4,
            "abstentions": 2,
            "factions": ["SPD", "GRÜNE"]
          },
          "evidence": {
            "sources": [],
            "steckbriefe": [{
              "name": "Verkehrswende Oldenburg",
              "slug": "verkehrswende",
              "beschreibung": "Beschlüsse zu Bus, Radverkehr und klimafreundlicher Mobilität."
            }],
            "sitzungen": [{
              "ksinr": 8001,
              "committee": "Rat der Stadt",
              "session_date": "2026-08-26",
              "session_time": "18:00",
              "agenda": [{"item_number": "Ö 10", "title": "Neue Busspuren für Oldenburg"}]
            }],
            "anlagen": [{
              "nr": 1,
              "label": "Übersichtskarte der Busspuren",
              "vorlage_nr": "26/0801",
              "auszug": "Geplante Abschnitte am Innenstadtring.",
              "url": "https://example.org/karte.pdf"
            }],
            "presse": [{
              "titel": "Stadt stellt Maßnahmen für einen schnelleren Busverkehr vor",
              "datum": "2026-08-27",
              "url": "https://example.org/presse"
            }],
            "debatten": [{
              "sprecher": "Mara Beispiel",
              "partei": "GRÜNE",
              "art": "Wortbeitrag",
              "datum": "2026-08-26",
              "auszug": "Die Busspuren sollen Anschlüsse stabilisieren und den Umweltverbund stärken."
            }],
            "planungen": [{
              "vorlage_titel": "Umsetzung der Busspuren",
              "gremium": "Verkehrsausschuss",
              "datum": "2026-11-12"
            }],
            "grafik": {
              "titel": "Vorgesehene Investitionen",
              "einheit": "Mio. €",
              "hinweis": "Planwerte aus der Beschlussvorlage.",
              "reihe": [
                {"jahr": 2026, "wert": 2.1},
                {"jahr": 2027, "wert": 4.3},
                {"jahr": 2028, "wert": 2.5}
              ]
            }
          }
        }
        """#
        guard
            let data = raw.data(using: .utf8),
            let root = try? JSONDecoder().decode(JSONValue.self, from: data),
            let object = root.object,
            let sourceValue = object["source"],
            let source = try? sourceValue.decoded(DecisionSummary.self),
            let evidence = object["evidence"]?.object
        else { return nil }
        return QuestionTurn(
            question: "Was bringen die neuen Busspuren?",
            answer: "Der Rat hat **zwei neue Busspuren** und bessere Ampelvorrangschaltungen beschlossen. Dafür sind 8,9 Millionen Euro vorgesehen. Ziel sind kürzere und verlässlichere Fahrzeiten. [1]",
            sources: [source],
            evidence: evidence,
            suggestions: ["Wann beginnt der Bau?", "Welche Linien profitieren?"],
            status: nil,
            error: nil
        )
    }
#endif
}

private struct EmptyQuestionsView: View {
    let select: (String) -> Void
    private let examples = [
        "Was hat der Rat zuletzt zum Radverkehr beschlossen?",
        "Welche Bauvorhaben sind gerade umstritten?",
        "Wofür gibt Oldenburg dieses Jahr besonders viel Geld aus?",
    ]

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            HStack(alignment: .bottom, spacing: 12) {
                LottiMascot(pose: .point)
                    .frame(width: 72, height: 72)
                Text("Frag, wie du sprechen würdest.")
                    .font(RatsFont.title(26))
            }
            Text("Ratslotse sucht in Beschlüssen, Vorlagen und Debatten. Die Quellen stehen direkt an der Antwort.")
                .foregroundStyle(RatsColor.secondary)
                .lineSpacing(3)
            ForEach(examples, id: \.self) { example in
                Button { select(example) } label: {
                    HStack {
                        Text(example).multilineTextAlignment(.leading)
                        Spacer()
                        Image(systemName: "arrow.right")
                    }
                    .font(RatsFont.body(14, weight: .medium))
                    .padding(13)
                    .background(RatsColor.card)
                    .overlay(RoundedRectangle(cornerRadius: 11).stroke(RatsColor.primary.opacity(0.24)))
                    .clipShape(RoundedRectangle(cornerRadius: 11))
                }
                .buttonStyle(.plain)
            }
        }
        .padding(.top, 30)
    }
}

private struct QuestionTurnView: View {
    let turn: QuestionTurn
    let model: AppModel
    let ask: (String) -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text(turn.question)
                .font(RatsFont.body(15, weight: .medium))
                .padding(.horizontal, 14)
                .padding(.vertical, 10)
                .background(RatsColor.primary.opacity(0.08))
                .overlay(RoundedRectangle(cornerRadius: 14).stroke(RatsColor.primary.opacity(0.18)))
                .clipShape(RoundedRectangle(cornerRadius: 14))
                .frame(maxWidth: .infinity, alignment: .trailing)

            if let status = turn.status {
                HStack(spacing: 9) {
                    ProgressView().controlSize(.small).tint(RatsColor.primary)
                    Text(status).font(RatsFont.body(13)).foregroundStyle(RatsColor.secondary)
                }
            }
            if !turn.answer.isEmpty {
                CitedAnswerText(text: turn.answer, model: model, evidence: turn.evidence)
                    .font(RatsFont.body(15))
                    .foregroundStyle(RatsColor.bodyText)
                    .lineSpacing(6)
            }
            if let error = turn.error {
                ErrorCard(message: error) { ask(turn.question) }
            }
            if !turn.sources.isEmpty {
                DisclosureGroup {
                    VStack(spacing: 12) {
                        ForEach(Array(turn.sources.enumerated()), id: \.element.id) { index, source in
                            Button { model.navigation.append(.decision(id: source.id)) } label: {
                                SourceRow(
                                    number: source.id,
                                    title: source.title,
                                    meta: [source.committee, source.sessionDate].compactMap { $0 }.joined(separator: " · ")
                                )
                            }
                            .buttonStyle(.plain)
                            if index < turn.sources.count - 1 { Divider().overlay(RatsColor.separator) }
                        }
                    }
                    .padding(.top, 10)
                } label: {
                    MonoKicker("Quellen", trailing: "\(turn.sources.count) gefunden")
                }
                .padding(14)
                .background(RatsColor.card)
                .overlay(RoundedRectangle(cornerRadius: 12).stroke(RatsColor.border))
                .clipShape(RoundedRectangle(cornerRadius: 12))
                PartyOpinionsView(turn: turn, model: model)
            }
            CouncilEvidenceBlocks(fields: turn.evidence, model: model)
            if !mapPins.isEmpty {
                VStack(alignment: .leading, spacing: 10) {
                    MonoKicker("Orte in der Antwort", trailing: "\(mapPins.count)")
                    Map(initialPosition: .region(mapRegion)) {
                        ForEach(mapPins) { pin in
                            Marker(pin.name, coordinate: pin.coordinate).tint(RatsColor.signal)
                        }
                    }
                    .frame(height: 190)
                    .clipShape(RoundedRectangle(cornerRadius: 11))
                    .accessibilityLabel("Karte der in der Antwort genannten Orte")
                }
                .ratsCard()
            }
            if !turn.suggestions.isEmpty {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 8) {
                        ForEach(turn.suggestions, id: \.self) { suggestion in
                            Button { ask(suggestion) } label: { Pill(suggestion, symbol: "arrow.turn.down.right") }
                                .buttonStyle(.plain)
                        }
                    }
                }
            }
            if !turn.answer.isEmpty {
                QuestionAnswerActions(turn: turn, model: model)
            }
        }
    }

    private var mapPins: [QuestionMapPin] {
        turn.sources.compactMap { source in
            guard let latitude = source.latitude, let longitude = source.longitude else { return nil }
            return QuestionMapPin(
                id: source.id,
                name: source.placeName ?? source.title,
                coordinate: CLLocationCoordinate2D(latitude: latitude, longitude: longitude)
            )
        }
    }

    private var mapRegion: MKCoordinateRegion {
        let latitudes = mapPins.map(\.coordinate.latitude)
        let longitudes = mapPins.map(\.coordinate.longitude)
        let center = CLLocationCoordinate2D(
            latitude: latitudes.reduce(0, +) / Double(max(1, latitudes.count)),
            longitude: longitudes.reduce(0, +) / Double(max(1, longitudes.count))
        )
        let latitudeDelta = max(0.018, (latitudes.max() ?? center.latitude) - (latitudes.min() ?? center.latitude) + 0.012)
        let longitudeDelta = max(0.018, (longitudes.max() ?? center.longitude) - (longitudes.min() ?? center.longitude) + 0.012)
        return MKCoordinateRegion(
            center: center,
            span: MKCoordinateSpan(latitudeDelta: latitudeDelta, longitudeDelta: longitudeDelta)
        )
    }
}

private struct QuestionMapPin: Identifiable {
    let id: Int
    let name: String
    let coordinate: CLLocationCoordinate2D
}

private struct PartyOpinion: Codable, Sendable, Identifiable {
    var id: String { party }
    let party: String
    let stance: String?
    let position: String
    let united: Bool?

    enum CodingKeys: String, CodingKey {
        case position
        case party = "partei"
        case stance = "haltung"
        case united = "einig"
    }
}

private struct PartyOpinionsResponse: Codable, Sendable {
    let parties: [PartyOpinion]
    let withoutContributions: [String]

    enum CodingKeys: String, CodingKey {
        case parties = "parteien"
        case withoutContributions = "ohne_beitraege"
    }
}

private struct PartyOpinionsView: View {
    let turn: QuestionTurn
    let model: AppModel
    @State private var response: PartyOpinionsResponse?
    @State private var isLoading = false
    @State private var error: String?

    var body: some View {
        DisclosureGroup {
            VStack(alignment: .leading, spacing: 12) {
                if let response {
                    if response.parties.isEmpty {
                        Text("In den ausgewerteten Wortbeiträgen wurden keine klaren Fraktionspositionen gefunden.")
                            .foregroundStyle(RatsColor.secondary)
                    }
                    ForEach(response.parties) { opinion in
                        VStack(alignment: .leading, spacing: 5) {
                            HStack {
                                Text(opinion.party).font(RatsFont.body(14, weight: .semibold))
                                if let stance = opinion.stance { Pill(stance.capitalized) }
                            }
                            Text(opinion.position).font(RatsFont.body(13)).foregroundStyle(RatsColor.secondary)
                            if opinion.united == false {
                                Text("Innerhalb der Fraktion gab es unterschiedliche Beiträge.")
                                    .font(RatsFont.body(11)).foregroundStyle(RatsColor.muted)
                            }
                        }
                        if opinion.id != response.parties.last?.id { Divider().overlay(RatsColor.separator) }
                    }
                    if !response.withoutContributions.isEmpty {
                        Text("Ohne zuordenbaren Beitrag: \(response.withoutContributions.joined(separator: ", "))")
                            .font(RatsFont.body(11)).foregroundStyle(RatsColor.muted)
                    }
                } else if isLoading {
                    ProgressView("Debatten auswerten …")
                } else {
                    Button("Positionen aus den Debatten laden") { Task { await load() } }
                        .buttonStyle(SecondaryButtonStyle())
                }
                if let error { Text(error).font(RatsFont.body(12)).foregroundStyle(RatsColor.danger) }
            }
            .padding(.top, 10)
        } label: {
            MonoKicker("Fraktionen")
        }
        .padding(14)
        .background(RatsColor.card)
        .overlay(RoundedRectangle(cornerRadius: 12).stroke(RatsColor.border))
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }

    private func load() async {
        struct Body: Codable, Sendable { let frage: String; let beschluss_ids: [Int] }
        isLoading = true
        defer { isLoading = false }
        do {
            response = try await model.api.send(
                "/api/council/partei-meinungen",
                body: Body(frage: String(turn.question.prefix(300)), beschluss_ids: turn.sources.map(\.id))
            )
        } catch { self.error = error.localizedDescription }
    }
}

private struct QuestionAnswerActions: View {
    let turn: QuestionTurn
    let model: AppModel
    @StateObject private var speaker = AnswerSpeaker()
    @State private var rating: String?
    @State private var shareItem: SharedAnswer?
    @State private var isSharing = false

    var body: some View {
        HStack(spacing: 12) {
            Text("Aus Ratsunterlagen zusammengefasst")
            Spacer()
            Button {
                speaker.toggle(text: turn.answer)
            } label: {
                Image(systemName: speaker.isSpeaking ? "stop.fill" : "speaker.wave.2")
            }
            .accessibilityLabel(speaker.isSpeaking ? "Vorlesen stoppen" : "Antwort vorlesen")

            Button { rate("up") } label: {
                Image(systemName: rating == "up" ? "hand.thumbsup.fill" : "hand.thumbsup")
            }
            .accessibilityLabel("Antwort war hilfreich")

            Button { rate("down") } label: {
                Image(systemName: rating == "down" ? "hand.thumbsdown.fill" : "hand.thumbsdown")
            }
            .accessibilityLabel("Antwort war nicht hilfreich")

            Button { Task { await createShare() } } label: {
                if isSharing { ProgressView().controlSize(.mini) }
                else { Image(systemName: "square.and.arrow.up") }
            }
            .disabled(isSharing)
            .accessibilityLabel("Antwort als Link teilen")
        }
        .font(RatsFont.body(11))
        .foregroundStyle(RatsColor.muted)
        .sheet(item: $shareItem) { item in
            ActivityView(items: [item.url])
        }
        .onDisappear { speaker.stop() }
    }

    private func rate(_ value: String) {
        guard rating != value else { return }
        rating = value
        struct Body: Codable, Sendable {
            let frage: String
            let antwort_auszug: String?
            let bewertung: String
            let grund: String?
        }
        Task {
            try? await model.api.sendVoid(
                "/api/council/qa-feedback",
                body: Body(
                    frage: String(turn.question.prefix(300)),
                    antwort_auszug: String(turn.answer.prefix(500)),
                    bewertung: value,
                    grund: nil
                )
            )
        }
    }

    private func createShare() async {
        struct Source: Codable, Sendable {
            let id: Int
            let title: String
            let session_date: String?
            let committee: String?
            let outcome: String?
        }
        struct Body: Codable, Sendable {
            let frage: String
            let antwort: String
            let quellen: [Source]
        }
        struct Response: Codable, Sendable { let token: String }

        isSharing = true
        defer { isSharing = false }
        do {
            let response: Response = try await model.api.send(
                "/api/council/qa-share",
                body: Body(
                    frage: String(turn.question.prefix(300)),
                    antwort: String(turn.answer.prefix(8000)),
                    quellen: turn.sources.map {
                        Source(
                            id: $0.id,
                            title: String($0.title.prefix(300)),
                            session_date: $0.sessionDate,
                            committee: $0.committee,
                            outcome: $0.outcome
                        )
                    }
                )
            )
            guard let url = URL(string: "https://ratslotse.de/g?t=\(response.token)") else { return }
            shareItem = SharedAnswer(url: url)
        } catch {
            model.alertMessage = error.localizedDescription
        }
    }
}

private final class AnswerSpeaker: NSObject, ObservableObject, AVSpeechSynthesizerDelegate, @unchecked Sendable {
    @Published private(set) var isSpeaking = false
    private let synthesizer = AVSpeechSynthesizer()

    override init() {
        super.init()
        synthesizer.delegate = self
    }

    func toggle(text: String) {
        if synthesizer.isSpeaking {
            stop()
            return
        }
        let cleaned = text
            .replacingOccurrences(of: #"\[(\d+|A\d+)\]"#, with: "", options: .regularExpression)
            .replacingOccurrences(of: #"[*_#`]"#, with: "", options: .regularExpression)
        let utterance = AVSpeechUtterance(string: cleaned)
        utterance.voice = AVSpeechSynthesisVoice(language: "de-DE")
        utterance.rate = AVSpeechUtteranceDefaultSpeechRate * 0.92
        isSpeaking = true
        synthesizer.speak(utterance)
    }

    func stop() {
        synthesizer.stopSpeaking(at: .immediate)
        isSpeaking = false
    }

    func speechSynthesizer(_ synthesizer: AVSpeechSynthesizer, didFinish utterance: AVSpeechUtterance) {
        isSpeaking = false
    }

    func speechSynthesizer(_ synthesizer: AVSpeechSynthesizer, didCancel utterance: AVSpeechUtterance) {
        isSpeaking = false
    }
}

private struct SharedAnswer: Identifiable {
    let id = UUID()
    let url: URL
}

private struct ActivityView: UIViewControllerRepresentable {
    let items: [Any]

    func makeUIViewController(context: Context) -> UIActivityViewController {
        UIActivityViewController(activityItems: items, applicationActivities: nil)
    }

    func updateUIViewController(_ controller: UIActivityViewController, context: Context) {}
}

struct CouncilEvidenceBlocks: View {
    let fields: [String: JSONValue]
    let model: AppModel

    private var attachments: [[String: JSONValue]] { objects("anlagen") }
    private var press: [[String: JSONValue]] { objects("presse") }
    private var debates: [[String: JSONValue]] { objects("debatten") }
    private var sessions: [[String: JSONValue]] { objects("sitzungen") }
    private var planning: [[String: JSONValue]] { objects("planungen") }
    private var briefs: [[String: JSONValue]] { objects("steckbriefe") }

    @ViewBuilder
    var body: some View {
        if fields["beleglage"]?.string == "duenn" {
            Label(
                "Dünne Beschlusslage – die Antwort stützt sich nur auf wenige passende Ratsunterlagen.",
                systemImage: "exclamationmark.magnifyingglass"
            )
            .font(RatsFont.body(12))
            .foregroundStyle(RatsColor.warning)
            .padding(11)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(RatsColor.warningTint)
            .clipShape(RoundedRectangle(cornerRadius: 10))
        }

        if !briefs.isEmpty {
            VStack(alignment: .leading, spacing: 10) {
                MonoKicker("Worum es geht")
                ForEach(Array(briefs.enumerated()), id: \.offset) { _, item in
                    let name = item["name"]?.string ?? "Steckbrief"
                    if let slug = item["slug"]?.string {
                        Button { model.navigation.append(.topic(slug: slug)) } label: {
                            EvidenceTextRow(
                                title: name,
                                detail: item["beschreibung"]?.string,
                                meta: "Steckbrief",
                                symbol: "info.circle"
                            )
                        }
                        .buttonStyle(.plain)
                    } else {
                        EvidenceTextRow(
                            title: name,
                            detail: item["beschreibung"]?.string,
                            meta: "Steckbrief",
                            symbol: "info.circle"
                        )
                    }
                }
            }
            .ratsCard()
        }

        if !sessions.isEmpty {
            DisclosureGroup {
                VStack(alignment: .leading, spacing: 12) {
                    ForEach(Array(sessions.enumerated()), id: \.offset) { _, item in
                        let title = item["committee"]?.string ?? "Sitzung"
                        let date = [item["session_date"]?.string, item["session_time"]?.string]
                            .compactMap { $0 }.joined(separator: " · ")
                        VStack(alignment: .leading, spacing: 7) {
                            HStack {
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(title).font(RatsFont.body(13, weight: .semibold))
                                    Text(date).font(RatsFont.mono(9)).foregroundStyle(RatsColor.muted)
                                }
                                Spacer()
                                if let id = item["ksinr"]?.int {
                                    Button("Öffnen") {
                                        model.navigation.append(.sessions(ksinr: id, tops: []))
                                    }
                                    .font(RatsFont.body(11, weight: .semibold))
                                }
                            }
                            ForEach(Array((item["agenda"]?.array ?? []).prefix(6).enumerated()), id: \.offset) { _, row in
                                if let agenda = row.object {
                                    Text("\(agenda["item_number"]?.string ?? "·")  \(agenda["title"]?.string ?? "Tagesordnungspunkt")")
                                        .font(RatsFont.body(11.5))
                                        .foregroundStyle(RatsColor.secondary)
                                        .lineLimit(2)
                                }
                            }
                        }
                        if item != sessions.last { Divider().overlay(RatsColor.separator) }
                    }
                }
                .padding(.top, 10)
            } label: {
                MonoKicker("Tagesordnungen", trailing: "\(sessions.count)")
            }
            .ratsCard()
        }

        if !attachments.isEmpty {
            DisclosureGroup {
                VStack(alignment: .leading, spacing: 11) {
                    ForEach(Array(attachments.enumerated()), id: \.offset) { index, item in
                        let number = item["nr"]?.int ?? index + 1
                        let title = item["label"]?.string ?? "Anlage"
                        let row = EvidenceTextRow(
                            title: "[A\(number)] \(title)",
                            detail: item["auszug"]?.string,
                            meta: item["vorlage_nr"]?.string,
                            symbol: "doc.text"
                        )
                        if let raw = item["url"]?.string, let url = URL(string: raw) {
                            Link(destination: url) { row }.buttonStyle(.plain)
                        } else { row }
                    }
                }
                .padding(.top, 10)
            } label: {
                MonoKicker("Anlagen & Gutachten", trailing: "\(attachments.count)")
            }
            .ratsCard()
        }

        if !press.isEmpty {
            DisclosureGroup {
                VStack(alignment: .leading, spacing: 10) {
                    ForEach(Array(press.enumerated()), id: \.offset) { _, item in
                        let row = EvidenceTextRow(
                            title: item["titel"]?.string ?? "Mitteilung der Stadt",
                            detail: nil,
                            meta: item["datum"]?.string,
                            symbol: "newspaper"
                        )
                        if let raw = item["url"]?.string, let url = URL(string: raw) {
                            Link(destination: url) { row }.buttonStyle(.plain)
                        } else { row }
                    }
                }
                .padding(.top, 10)
            } label: {
                MonoKicker("Aktuelles von der Stadt", trailing: "extern")
            }
            .ratsCard()
        }

        if !debates.isEmpty {
            DisclosureGroup {
                VStack(alignment: .leading, spacing: 12) {
                    ForEach(Array(debates.enumerated()), id: \.offset) { _, item in
                        let speaker = item["sprecher"]?.string ?? "Ohne Namen"
                        let party = item["partei"]?.string
                        let kind = item["art"]?.string?.capitalized
                        let row = EvidenceTextRow(
                            title: [speaker, party].compactMap { $0 }.joined(separator: " · "),
                            detail: item["auszug"]?.string,
                            meta: [kind, item["datum"]?.string].compactMap { $0 }.joined(separator: " · "),
                            symbol: "quote.bubble"
                        )
                        if let url = debateURL(item) { Link(destination: url) { row }.buttonStyle(.plain) }
                        else { row }
                    }
                    Text("Ratsprotokolle fassen Beiträge sinngemäß zusammen; sie sind keine Wortprotokolle.")
                        .font(RatsFont.body(10.5)).foregroundStyle(RatsColor.muted)
                }
                .padding(.top, 10)
            } label: {
                MonoKicker("Aus den Ratsdebatten", trailing: "\(debates.count)")
            }
            .ratsCard()
        }

        if !planning.isEmpty {
            DisclosureGroup {
                VStack(alignment: .leading, spacing: 10) {
                    ForEach(Array(planning.enumerated()), id: \.offset) { _, item in
                        EvidenceTextRow(
                            title: item["vorlage_titel"]?.string ?? item["vorlage_nr"]?.string ?? "Vorlage",
                            detail: item["gremium"]?.string,
                            meta: item["datum"]?.string,
                            symbol: "arrow.triangle.branch"
                        )
                    }
                }
                .padding(.top, 10)
            } label: {
                MonoKicker("Wie es weitergeht", trailing: "\(planning.count) Stationen")
            }
            .ratsCard()
        }

        if let chart = EvidenceChartData(fields["grafik"]) {
            VStack(alignment: .leading, spacing: 12) {
                MonoKicker("Zahlen aus der Stadt")
                Text(chart.title).font(RatsFont.body(14, weight: .semibold))
                Chart(chart.points) { point in
                    LineMark(
                        x: .value("Zeit", point.label),
                        y: .value(chart.unit, point.value)
                    )
                    .foregroundStyle(RatsColor.primary)
                    PointMark(
                        x: .value("Zeit", point.label),
                        y: .value(chart.unit, point.value)
                    )
                    .foregroundStyle(RatsColor.signal)
                }
                .frame(height: 150)
                .chartYAxisLabel(chart.unit)
                if let note = chart.note { Text(note).font(RatsFont.body(10.5)).foregroundStyle(RatsColor.muted) }
            }
            .ratsCard()
        }
    }

    private func objects(_ key: String) -> [[String: JSONValue]] {
        fields[key]?.array?.compactMap(\.object) ?? []
    }

    private func debateURL(_ item: [String: JSONValue]) -> URL? {
        guard let raw = item["protokoll_url"]?.string else { return nil }
        if let page = item["protokoll_seite"]?.int {
            return URL(string: "\(raw)#page=\(page)")
        }
        return URL(string: raw)
    }
}

private struct EvidenceTextRow: View {
    let title: String
    let detail: String?
    let meta: String?
    let symbol: String

    var body: some View {
        HStack(alignment: .top, spacing: 9) {
            Image(systemName: symbol)
                .font(.system(size: 13, weight: .medium))
                .foregroundStyle(RatsColor.primary)
                .frame(width: 22)
            VStack(alignment: .leading, spacing: 3) {
                Text(title).font(RatsFont.body(12.5, weight: .semibold)).foregroundStyle(RatsColor.text)
                if let detail, !detail.isEmpty {
                    Text(detail).font(RatsFont.body(11.5)).foregroundStyle(RatsColor.secondary).lineLimit(5)
                }
                if let meta, !meta.isEmpty { Text(meta).font(RatsFont.mono(9)).foregroundStyle(RatsColor.muted) }
            }
            Spacer(minLength: 0)
        }
        .contentShape(Rectangle())
    }
}

private struct EvidenceChartData {
    struct Point: Identifiable {
        let id: Int
        let label: String
        let value: Double
    }

    let title: String
    let unit: String
    let note: String?
    let points: [Point]

    init?(_ value: JSONValue?) {
        guard let root = value?.object else { return nil }
        let rows = root["reihe"]?.array ?? []
        var parsed: [Point] = []
        parsed.reserveCapacity(rows.count)
        for (index, row) in rows.enumerated() {
            guard let fields = row.object else { continue }
            var number: Double?
            for key in ["wert", "value", "betrag"] {
                if case .number(let found)? = fields[key] {
                    number = found
                    break
                }
            }
            guard let number else { continue }
            let label: String
            if let explicit = fields["label"]?.string {
                label = explicit
            } else if let year = fields["jahr"]?.int {
                label = String(year)
            } else if let date = fields["datum"]?.string {
                label = date
            } else {
                label = "\(index + 1)"
            }
            parsed.append(Point(id: index, label: label, value: number))
        }
        points = parsed
        guard points.count >= 2 else { return nil }
        title = root["titel"]?.string ?? "Entwicklung"
        unit = root["einheit"]?.string ?? "Wert"
        note = root["hinweis"]?.string
    }
}

struct CitedAnswerText: View {
    let text: String
    let model: AppModel
    var evidence: [String: JSONValue] = [:]

    var body: some View {
        Text(attributed)
            .environment(\.openURL, OpenURLAction { url in
                guard url.scheme == "ratslotse" else { return .systemAction }
                if url.host == "decision", let id = Int(url.lastPathComponent) {
                    model.navigation.append(.decision(id: id))
                    return .handled
                }
                if url.host == "attachment", let number = Int(url.lastPathComponent),
                   let target = attachmentURL(number: number) {
                    UIApplication.shared.open(target)
                    return .handled
                }
                return .discarded
            })
    }

    private var attributed: AttributedString {
        var output = (try? AttributedString(markdown: text)) ?? AttributedString(text)
        applyLinks(pattern: #"\[(\d+)\]"#, host: "decision", in: &output)
        applyLinks(pattern: #"\[A(\d+)\]"#, host: "attachment", in: &output)
        return output
    }

    private func applyLinks(pattern: String, host: String, in output: inout AttributedString) {
        guard let regex = try? NSRegularExpression(pattern: pattern) else { return }
        let ns = text as NSString
        for match in regex.matches(in: text, range: NSRange(location: 0, length: ns.length)).reversed() {
            guard
                let range = Range(match.range, in: text),
                let idRange = Range(match.range(at: 1), in: text),
                let lower = AttributedString.Index(range.lowerBound, within: output),
                let upper = AttributedString.Index(range.upperBound, within: output),
                let url = URL(string: "ratslotse://\(host)/\(text[idRange])")
            else { continue }
            output[lower..<upper].link = url
            output[lower..<upper].foregroundColor = RatsColor.primary
            output[lower..<upper].font = RatsFont.body(11, weight: .bold)
        }
    }

    private func attachmentURL(number: Int) -> URL? {
        let rows = evidence["anlagen"]?.array?.compactMap(\.object) ?? []
        guard let raw = rows.first(where: { $0["nr"]?.int == number })?["url"]?.string else { return nil }
        return URL(string: raw)
    }
}
