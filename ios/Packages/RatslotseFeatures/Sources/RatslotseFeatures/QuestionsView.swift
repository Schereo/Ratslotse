import AVFoundation
import RatslotseAPI
import RatslotseDesign
import SwiftUI
import UIKit

private struct QuestionTurn: Identifiable {
    let id = UUID()
    let question: String
    var answer = ""
    var sources: [DecisionSummary] = []
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

    var body: some View {
        VStack(spacing: 0) {
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
                    if let id = turns.last?.id { withAnimation { proxy.scrollTo(id, anchor: .bottom) } }
                }
            }

            VStack(spacing: 0) {
                Divider().overlay(RatsColor.border)
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
        .toolbar {
            ToolbarItemGroup(placement: .topBarTrailing) {
                Button { showConversations = true } label: {
                    Label("Gespräche", systemImage: "clock.arrow.circlepath")
                }
                Button { showDeepResearch = true } label: {
                    Label("Gründlich recherchieren", systemImage: model.hasRecoverableResearch ? "flask.fill" : "flask")
                }
            }
        }
        .onAppear {
            if !model.questionPrefill.isEmpty {
                input = model.questionPrefill
                model.questionPrefill = ""
            }
        }
        .onDisappear { streamTask?.cancel(); streamTask = nil }
        .sheet(isPresented: $showDeepResearch) {
            DeepResearchView(model: model, initialQuestion: input)
        }
        .sheet(isPresented: $showConversations) {
            ConversationsView(model: model)
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
                    case "abbruch": turns[index].status = "Die Verbindung brach ab. Die bisherige Antwort bleibt sichtbar."
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
            Image(systemName: "sparkles")
                .font(.system(size: 30))
                .foregroundStyle(RatsColor.signal)
            Text("Frag, wie du sprechen würdest.")
                .font(RatsFont.title(26))
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
                CitedAnswerText(text: turn.answer, model: model)
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

private struct CitedAnswerText: View {
    let text: String
    let model: AppModel

    var body: some View {
        Text(attributed)
            .environment(\.openURL, OpenURLAction { url in
                guard url.scheme == "ratslotse", url.host == "decision", let id = Int(url.lastPathComponent) else {
                    return .systemAction
                }
                model.navigation.append(.decision(id: id))
                return .handled
            })
    }

    private var attributed: AttributedString {
        var output = (try? AttributedString(markdown: text)) ?? AttributedString(text)
        guard let regex = try? NSRegularExpression(pattern: #"\[(\d+)\]"#) else { return output }
        let ns = text as NSString
        for match in regex.matches(in: text, range: NSRange(location: 0, length: ns.length)).reversed() {
            guard
                let range = Range(match.range, in: text),
                let idRange = Range(match.range(at: 1), in: text),
                let lower = AttributedString.Index(range.lowerBound, within: output),
                let upper = AttributedString.Index(range.upperBound, within: output),
                let url = URL(string: "ratslotse://decision/\(text[idRange])")
            else { continue }
            output[lower..<upper].link = url
            output[lower..<upper].foregroundColor = RatsColor.primary
            output[lower..<upper].font = RatsFont.body(11, weight: .bold)
        }
        return output
    }
}
