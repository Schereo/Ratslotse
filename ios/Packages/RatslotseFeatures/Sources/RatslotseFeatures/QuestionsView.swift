import AVFoundation
import Charts
import MapKit
import RatslotseAPI
import RatslotseDesign
import SwiftUI
import UIKit

private struct ResearchCurrentResponse: Codable, Sendable {
    let job: ResearchSnapshot?
    let frei: Int?
}

private struct ResearchStartResponse: Codable, Sendable {
    let jobID: String
    let frei: Int?

    enum CodingKeys: String, CodingKey {
        case jobID = "job_id"
        case frei
    }
}

private struct ResearchSnapshot: Codable, Sendable {
    let id: String
    let frage: String
    let status: String
    let bericht: String?
    let quellen: JSONValue?
}

private struct ResearchFacet: Identifiable {
    let id = UUID()
    let name: String
    var hits: Int?
}

private struct ResearchState {
    var jobID: String?
    var status = "laeuft"
    var phase = "zerlegen"
    var facets: [ResearchFacet] = []
    var eventsSeen = 0
    var partialPossible = false
}

private struct QuestionTurn: Identifiable {
    let id = UUID()
    let question: String
    var answer = ""
    var sources: [DecisionSummary] = []
    var evidence: [String: JSONValue] = [:]
    var suggestions: [String] = []
    var status: String?
    var error: String?
    var research: ResearchState?
}

struct QuestionsView: View {
    let model: AppModel
    @Environment(\.scenePhase) private var scenePhase
    @Environment(\.horizontalSizeClass) private var horizontalSizeClass
    @State private var input = ""
    @State private var turns: [QuestionTurn] = []
    @State private var streamTask: Task<Void, Never>?
    @State private var researchStreamTask: Task<Void, Never>?
    @State private var rateLimitUntil: Date?
    @State private var researchMode = false
    @State private var researchRemaining: Int?
    @State private var showConversations = false
    @State private var isSavingConversationPreference = false
    @State private var conversationPreferenceError: String?

    private var isSending: Bool {
        streamTask != nil || turns.contains { $0.research?.status == "laeuft" }
    }
    private var composerBottomPadding: CGFloat {
        horizontalSizeClass == .compact ? 96 : 18
    }
    private var shouldAutoScroll: Bool {
#if DEBUG
        ratsDebugValue("RATSLOTSE_DEBUG_QUESTION_FIXTURE") != "1"
#else
        true
#endif
    }

    var body: some View {
        GeometryReader { geometry in
            let showsEvidenceSidebar = geometry.size.width >= 1_040
            let usesCompactWelcome = geometry.size.width < 600 && geometry.size.height < 950

            HStack(spacing: 0) {
                chatColumn(
                    showsEvidenceInline: !showsEvidenceSidebar,
                    usesCompactWelcome: usesCompactWelcome
                )
                    .frame(maxWidth: showsEvidenceSidebar ? 744 : .infinity)

                if showsEvidenceSidebar {
                    Rectangle()
                        .fill(RatsColor.separator)
                        .frame(width: 1)
                        .padding(.vertical, 14)

                    QuestionEvidenceSidebar(turn: turns.last, model: model)
                        .frame(width: 376)
                }
            }
            .frame(maxWidth: showsEvidenceSidebar ? 1_121 : .infinity)
            .frame(maxWidth: .infinity)
        }
        .background(RatsColor.stage)
        .toolbar(.hidden, for: .navigationBar)
        .onAppear {
            if !model.questionPrefill.isEmpty {
                input = model.questionPrefill
                model.questionPrefill = ""
            }
#if DEBUG
            if turns.isEmpty,
               ratsDebugValue("RATSLOTSE_DEBUG_QUESTION_FIXTURE") == "1",
               let fixture = debugQuestionFixture() {
                turns = [fixture]
            }
            researchMode = ratsDebugValue("RATSLOTSE_DEBUG_RESEARCH_MODE") == "1"
            showConversations = ratsDebugValue("RATSLOTSE_DEBUG_QUESTION_SHEET") == "conversations"
#endif
        }
        .task { await restoreCurrentResearch() }
        .task { await restoreActiveConversationIfNeeded() }
        .onChange(of: scenePhase) { _, phase in
            if phase == .active { reconnectRunningResearchIfNeeded() }
            else { researchStreamTask?.cancel(); researchStreamTask = nil }
        }
        .onDisappear {
            streamTask?.cancel()
            streamTask = nil
            researchStreamTask?.cancel()
            researchStreamTask = nil
        }
        .sheet(isPresented: $showConversations) {
            ConversationsView(
                model: model,
                activeConversationID: model.activeConversationID,
                currentTitle: turns.first?.question,
                currentTurnCount: turns.count,
                onNew: startNewConversation,
                onOpen: loadConversation,
                onDeletedActive: startNewConversation
            )
                .ratsLargeSheet()
        }
    }

    private func chatColumn(showsEvidenceInline: Bool, usesCompactWelcome: Bool) -> some View {
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
                if model.conversationSavingPreference == 1 {
                    if !turns.isEmpty || model.activeConversationID != nil {
                        Button(action: startNewConversation) {
                            Label("Neu", systemImage: "square.and.pencil")
                                .font(RatsFont.body(12, weight: .semibold))
                                .padding(.horizontal, 12)
                                .frame(height: 40)
                                .background(RatsColor.card)
                                .overlay(Capsule().stroke(RatsColor.border))
                                .clipShape(Capsule())
                        }
                        .buttonStyle(.plain)
                        .accessibilityLabel("Neues Gespräch")
                    }
                    Button { showConversations = true } label: {
                        RatsGlyphView(glyph: .history, color: RatsColor.bodyText)
                            .frame(width: 20, height: 20)
                            .frame(width: 40, height: 40)
                            .background(RatsColor.card)
                            .overlay(Circle().stroke(RatsColor.border))
                            .clipShape(Circle())
                    }
                    .accessibilityLabel("Gespräche")
                }
            }
            .foregroundStyle(RatsColor.text)
            .padding(.horizontal, 18)
            .padding(.top, 16)
            .padding(.bottom, 5)

            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 26) {
                        if turns.isEmpty {
                            if model.conversationSavingPreference == nil {
                                ConversationMemoryConsentCard(
                                    isSaving: isSavingConversationPreference,
                                    error: conversationPreferenceError,
                                    choose: saveConversationPreference
                                )
                                .transition(.opacity.combined(with: .move(edge: .top)))
                            } else {
                                EmptyQuestionsView(
                                    usesCompactLayout: usesCompactWelcome,
                                    select: askUsingSelectedMode
                                )
                            }
                        }
                        ForEach(turns) { turn in
                            QuestionTurnView(
                                turn: turn,
                                model: model,
                                ask: askUsingSelectedMode,
                                stopResearch: stopResearch,
                                requestPartialResearch: requestPartialResearch,
                                reconnectResearch: reconnectResearch,
                                showsEvidenceInline: showsEvidenceInline
                            )
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

        }
        .safeAreaInset(edge: .bottom, spacing: 0) {
            VStack(spacing: 7) {
                if let rateLimitUntil, rateLimitUntil > .now {
                    TimelineView(.periodic(from: .now, by: 1)) { context in
                        let seconds = max(1, Int(rateLimitUntil.timeIntervalSince(context.date).rounded(.up)))
                        Label("Neue Frage in \(seconds) s", systemImage: "hourglass")
                            .font(RatsFont.body(11, weight: .semibold))
                            .foregroundStyle(RatsColor.warning)
                    }
                }
                RatsQuestionComposer(
                    text: $input,
                    researchMode: $researchMode,
                    researchRemaining: researchRemaining,
                    isSending: isSending,
                    action: submitOrStop
                )
            }
            .frame(maxWidth: 780)
            .padding(.horizontal, 16)
            .padding(.top, 8)
            .padding(.bottom, composerBottomPadding)
            .frame(maxWidth: .infinity)
        }
    }

    private func submitOrStop() {
        if streamTask != nil {
            streamTask?.cancel()
            streamTask = nil
            if let last = turns.indices.last { turns[last].status = "Abgebrochen – deine Frage bleibt erhalten." }
            return
        }
        if let running = turns.last(where: { $0.research?.status == "laeuft" }) {
            stopResearch(running.id)
            return
        }
        askUsingSelectedMode(input)
    }

    private func askUsingSelectedMode(_ raw: String) {
        if researchMode { askResearch(raw) }
        else { ask(raw) }
    }

    private func saveConversationPreference(_ enabled: Bool) {
        guard !isSavingConversationPreference else { return }
        isSavingConversationPreference = true
        conversationPreferenceError = nil
        Task {
            defer { isSavingConversationPreference = false }
            do {
                try await model.setConversationSaving(enabled)
            } catch {
                conversationPreferenceError = "Deine Wahl konnte nicht gespeichert werden. Bitte versuche es noch einmal."
            }
        }
    }

    private func startNewConversation() {
        streamTask?.cancel()
        streamTask = nil
        researchStreamTask?.cancel()
        researchStreamTask = nil
        turns.removeAll()
        input = ""
        rateLimitUntil = nil
        model.setActiveConversationID(nil)
    }

    private func loadConversation(_ id: Int, payload: JSONValue) {
        streamTask?.cancel()
        streamTask = nil
        researchStreamTask?.cancel()
        researchStreamTask = nil
        let restored = (payload.object?["turns"]?.array ?? []).compactMap { value -> QuestionTurn? in
            guard let fields = value.object else { return nil }
            let question = fields["frage"]?.string ?? fields["question"]?.string ?? ""
            guard !question.isEmpty else { return nil }
            let answer = fields["antwort"]?.string ?? fields["answer"]?.string ?? ""
            let evidence = fields["quellen"]?.object ?? [:]
            let sources = evidence["sources"]?.array?.compactMap {
                try? $0.decoded(DecisionSummary.self)
            } ?? []
            let research = evidence["recherche"]?.bool == true
                ? ResearchState(status: "fertig")
                : nil
            return QuestionTurn(
                question: question,
                answer: answer,
                sources: sources,
                evidence: evidence,
                research: research
            )
        }
        turns = restored
        model.setActiveConversationID(id)
    }

    private func restoreActiveConversationIfNeeded() async {
        guard model.conversationSavingPreference == 1,
              turns.isEmpty,
              let id = model.activeConversationID
        else { return }
        do {
            let payload: JSONValue = try await model.api.get("/api/council/gespraeche/\(id)")
            guard turns.isEmpty else { return }
            loadConversation(id, payload: payload)
        } catch let error as APIError where error.statusCode == 404 || error.isUnauthorized {
            model.setActiveConversationID(nil)
        } catch {
            // Offline bleibt die Referenz erhalten; beim nächsten Öffnen kann
            // das Gespräch wiederhergestellt werden.
        }
    }

    private func ask(_ raw: String) {
        let question = raw.trimmingCharacters(in: .whitespacesAndNewlines)
        guard question.count >= 4 else { return }
        if let rateLimitUntil, rateLimitUntil > .now { return }
        input = ""
        Task { await model.reportBadgeEvent("frage") }
        let history = turns.suffix(4).map {
            AskRound(frage: $0.question, antwort: String($0.answer.prefix(600)))
        }
        turns.append(QuestionTurn(question: question, status: "Beschlüsse durchsuchen …"))
        let index = turns.count - 1
        streamTask = Task {
            defer { streamTask = nil }
            do {
                let request = try await model.api.makeStreamingRequest(
                    "/api/council/ask",
                    body: AskRequest(
                        question: question,
                        verlauf: history,
                        gespraechID: model.activeConversationID
                    )
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
                    case "done":
                        turns[index].status = nil
                        if let conversationID = event.conversationID {
                            model.setActiveConversationID(conversationID)
                        }
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

    private func askResearch(_ raw: String) {
        let question = raw.trimmingCharacters(in: .whitespacesAndNewlines)
        guard question.count >= 4, researchRemaining != 0 else { return }
        input = ""
        researchMode = false
        let turn = QuestionTurn(
            question: question,
            status: nil,
            research: ResearchState()
        )
        turns.append(turn)
        startResearch(turn.id)
    }

    private func startResearch(_ turnID: UUID) {
        researchStreamTask?.cancel()
        researchStreamTask = Task {
            defer { researchStreamTask = nil }
            guard let index = turns.firstIndex(where: { $0.id == turnID }) else { return }
            let question = turns[index].question
            do {
                let response: ResearchStartResponse = try await model.api.send(
                    "/api/council/deep-research",
                    body: DeepResearchRequest(
                        frage: question,
                        gespraechID: model.activeConversationID
                    )
                )
                guard let current = turns.firstIndex(where: { $0.id == turnID }) else { return }
                turns[current].research?.jobID = response.jobID
                researchRemaining = response.frei
                model.hasRecoverableResearch = true
                await streamResearch(turnID: turnID, jobID: response.jobID)
            } catch is CancellationError {
                return
            } catch let apiError as APIError where apiError.statusCode == 429 {
                researchRemaining = 0
                researchMode = false
                if let current = turns.firstIndex(where: { $0.id == turnID }) {
                    turns[current].research?.status = "fehler"
                    turns[current].error = "Deine Recherchen für heute sind aufgebraucht. Ab Mitternacht kannst du wieder gründlich recherchieren; schnelle Fragen bleiben verfügbar."
                }
            } catch {
                if let current = turns.firstIndex(where: { $0.id == turnID }) {
                    turns[current].research?.status = "fehler"
                    turns[current].error = error.localizedDescription
                }
            }
        }
    }

    private func streamResearch(turnID: UUID, jobID: String) async {
        var retryDelay = 1.0
        while !Task.isCancelled {
            guard
                let index = turns.firstIndex(where: { $0.id == turnID }),
                turns[index].research?.status == "laeuft"
            else { return }
            let eventsSeen = turns[index].research?.eventsSeen ?? 0
            do {
                let request = try await model.api.makeStreamingRequest(
                    "/api/council/deep-research/\(jobID)/events",
                    query: [.init(name: "ab", value: String(eventsSeen))]
                )
                for try await event in model.sse.events(for: request) {
                    guard !Task.isCancelled else { return }
                    guard let current = turns.firstIndex(where: { $0.id == turnID }) else { return }
                    turns[current].research?.eventsSeen += 1
                    applyResearch(event: event, to: turnID)
                    if turns[current].research?.status != "laeuft" { return }
                    retryDelay = 1
                }
                try await Task.sleep(for: .seconds(1))
            } catch let apiError as APIError where apiError.statusCode == 410 {
                await loadResearchSnapshot(turnID: turnID, jobID: jobID)
                return
            } catch is CancellationError {
                return
            } catch {
                if let current = turns.firstIndex(where: { $0.id == turnID }) {
                    turns[current].error = "Verbindung unterbrochen – Ratslotse verbindet sich erneut."
                }
                try? await Task.sleep(for: .seconds(retryDelay))
                retryDelay = min(8, retryDelay * 2)
            }
        }
    }

    private func applyResearch(event: SSEEvent, to turnID: UUID) {
        guard let index = turns.firstIndex(where: { $0.id == turnID }) else { return }
        switch event.type {
        case "phase":
            turns[index].research?.phase = event.fields["phase"]?.string ?? turns[index].research?.phase ?? "zerlegen"
        case "facetten":
            turns[index].research?.facets = event.fields["facetten"]?.array?.compactMap(\.string).map {
                ResearchFacet(name: $0)
            } ?? []
            turns[index].research?.phase = "suchen"
        case "facette":
            let name = event.fields["name"]?.string
            if let facetIndex = turns[index].research?.facets.firstIndex(where: { $0.name == name }) {
                turns[index].research?.facets[facetIndex].hits = event.fields["treffer"]?.int
            }
        case "sources":
            turns[index].evidence = event.fields
            turns[index].sources = event.fields["sources"]?.array?.compactMap {
                try? $0.decoded(DecisionSummary.self)
            } ?? []
            turns[index].error = nil
        case "token":
            turns[index].answer += event.text ?? ""
            turns[index].error = nil
        case "replace":
            turns[index].answer = event.text ?? turns[index].answer
            turns[index].error = nil
        case "gestoppt":
            turns[index].research?.status = "gestoppt"
            turns[index].research?.partialPossible = event.fields["teilbericht_moeglich"]?.bool ?? false
        case "fehler":
            turns[index].research?.status = "fehler"
            turns[index].error = "Die Recherche ist abgebrochen. Der Versuch zählt nicht gegen dein Kontingent."
        case "done":
            let jobID = turns[index].research?.jobID
            turns[index].research?.status = "fertig"
            turns[index].error = nil
            model.hasRecoverableResearch = false
            if let conversationID = event.conversationID {
                model.setActiveConversationID(conversationID)
            }
            if let jobID {
                Task { try? await model.api.sendVoid("/api/council/deep-research/\(jobID)/gesehen") }
            }
        default:
            break
        }
    }

    private func stopResearch(_ turnID: UUID) {
        Task {
            guard
                let index = turns.firstIndex(where: { $0.id == turnID }),
                let jobID = turns[index].research?.jobID
            else { return }
            do {
                let response: JSONValue = try await model.api.sendWithoutBody(
                    "/api/council/deep-research/\(jobID)/stop"
                )
                guard let current = turns.firstIndex(where: { $0.id == turnID }) else { return }
                turns[current].research?.status = "gestoppt"
                turns[current].research?.partialPossible = response.object?["teilbericht_moeglich"]?.bool ?? false
                researchStreamTask?.cancel()
                researchStreamTask = nil
            } catch {
                if let current = turns.firstIndex(where: { $0.id == turnID }) {
                    turns[current].error = "Die Recherche konnte nicht abgebrochen werden und läuft weiter."
                }
            }
        }
    }

    private func requestPartialResearch(_ turnID: UUID) {
        Task {
            guard
                let index = turns.firstIndex(where: { $0.id == turnID }),
                let jobID = turns[index].research?.jobID
            else { return }
            do {
                let _: JSONValue = try await model.api.sendWithoutBody(
                    "/api/council/deep-research/\(jobID)/teilbericht"
                )
                guard let current = turns.firstIndex(where: { $0.id == turnID }) else { return }
                turns[current].research?.status = "laeuft"
                turns[current].research?.phase = "schreiben"
                turns[current].error = nil
                reconnectResearch(turnID)
            } catch {
                if let current = turns.firstIndex(where: { $0.id == turnID }) {
                    turns[current].error = error.localizedDescription
                }
            }
        }
    }

    private func reconnectResearch(_ turnID: UUID) {
        guard let index = turns.firstIndex(where: { $0.id == turnID }) else { return }
        guard let jobID = turns[index].research?.jobID else {
            guard researchRemaining != 0 else { return }
            startResearch(turnID)
            return
        }
        turns[index].research?.status = "laeuft"
        turns[index].error = nil
        researchStreamTask?.cancel()
        researchStreamTask = Task {
            defer { researchStreamTask = nil }
            await streamResearch(turnID: turnID, jobID: jobID)
        }
    }

    private func restoreCurrentResearch() async {
        do {
            let current: ResearchCurrentResponse = try await model.api.get("/api/council/deep-research/aktuell")
            researchRemaining = current.frei
            guard let snapshot = current.job else { return }

            let turnID: UUID
            if let existing = turns.first(where: { $0.research?.jobID == snapshot.id }) {
                turnID = existing.id
            } else {
                let turn = QuestionTurn(
                    question: snapshot.frage,
                    status: nil,
                    research: ResearchState(jobID: snapshot.id, status: snapshot.status)
                )
                turns.append(turn)
                turnID = turn.id
            }
            applyResearch(snapshot: snapshot, to: turnID)
            if snapshot.status == "laeuft" { reconnectResearch(turnID) }
            else if snapshot.bericht == nil { await loadResearchSnapshot(turnID: turnID, jobID: snapshot.id) }
        } catch {
            // The questions screen remains fully usable if restoring a server job fails.
        }
    }

    private func loadResearchSnapshot(turnID: UUID, jobID: String) async {
        do {
            let snapshot: ResearchSnapshot = try await model.api.get("/api/council/deep-research/\(jobID)")
            applyResearch(snapshot: snapshot, to: turnID)
        } catch {
            if let index = turns.firstIndex(where: { $0.id == turnID }) {
                turns[index].research?.status = "fehler"
                turns[index].error = error.localizedDescription
            }
        }
    }

    private func applyResearch(snapshot: ResearchSnapshot, to turnID: UUID) {
        guard let index = turns.firstIndex(where: { $0.id == turnID }) else { return }
        turns[index].research?.jobID = snapshot.id
        turns[index].research?.status = snapshot.status == "teilbericht" ? "fertig" : snapshot.status
        turns[index].answer = snapshot.bericht ?? turns[index].answer
        if let root = snapshot.quellen?.object {
            turns[index].evidence = root
            turns[index].sources = root["sources"]?.array?.compactMap {
                try? $0.decoded(DecisionSummary.self)
            } ?? []
        }
        model.hasRecoverableResearch = snapshot.status == "laeuft" || snapshot.bericht != nil
    }

    private func reconnectRunningResearchIfNeeded() {
        guard researchStreamTask == nil,
              let running = turns.last(where: { $0.research?.status == "laeuft" })
        else { return }
        reconnectResearch(running.id)
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
            "id": 20947,
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
            "factions": ["SPD", "GRÜNE"],
            "lat": 53.143,
            "lon": 8.214
          },
          "other_source": {
            "id": 30001,
            "title": "Stadionneubau an der Maastrichter Straße",
            "committee": "Rat der Stadt",
            "session_date": "2026-07-01",
            "outcome": "angenommen",
            "lat": 53.151,
            "lon": 8.229
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
            let otherSourceValue = object["other_source"],
            let otherSource = try? otherSourceValue.decoded(DecisionSummary.self),
            let evidence = object["evidence"]?.object
        else { return nil }
        return QuestionTurn(
            question: "Was bringen die neuen Busspuren?",
            answer: "Der Rat hat **zwei neue Busspuren** und bessere Ampelvorrangschaltungen beschlossen. Dafür sind 8,9 Millionen Euro vorgesehen [20947].Für diesen Abschnitt sind kürzere und verlässlichere Fahrzeiten das Ziel.",
            sources: [source, otherSource],
            evidence: evidence,
            suggestions: ["Wann beginnt der Bau?", "Welche Linien profitieren?"],
            status: nil,
            error: nil
        )
    }
#endif
}

private struct EmptyQuestionsView: View {
    let usesCompactLayout: Bool
    let select: (String) -> Void
    private let examples = [
        "Was hat der Rat zuletzt zum Radverkehr beschlossen?",
        "Welche Bauvorhaben sind gerade umstritten?",
        "Wofür gibt Oldenburg dieses Jahr besonders viel Geld aus?",
    ]

    var body: some View {
        VStack(alignment: .leading, spacing: usesCompactLayout ? 12 : 18) {
            if usesCompactLayout {
                HStack(spacing: 14) {
                    Lotti3DView(scene: .questions)
                        .frame(width: 124, height: 104)
                        .accessibilityHidden(true)

                    welcomeTitle
                        .frame(maxWidth: .infinity, alignment: .leading)
                }
            } else {
                Lotti3DView(scene: .questions)
                    .frame(maxWidth: .infinity)
                    .frame(height: 164)
                    .accessibilityHidden(true)
                welcomeTitle
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
                    .padding(.horizontal, 13)
                    .padding(.vertical, usesCompactLayout ? 10 : 13)
                    .background(RatsColor.card)
                    .overlay(RoundedRectangle(cornerRadius: 11).stroke(RatsColor.primary.opacity(0.24)))
                    .clipShape(RoundedRectangle(cornerRadius: 11))
                }
                .buttonStyle(.plain)
            }
        }
        .padding(.top, usesCompactLayout ? 4 : 30)
    }

    private var welcomeTitle: some View {
        Text("Frag, wie du sprechen würdest.")
            .font(RatsFont.title(usesCompactLayout ? 24 : 26))
            .fixedSize(horizontal: false, vertical: true)
    }
}

private struct ConversationMemoryConsentCard: View {
    let isSaving: Bool
    let error: String?
    let choose: (Bool) -> Void

    var body: some View {
        HStack(alignment: .top, spacing: 14) {
            Lotti3DView(scene: .wave, animated: false)
                .frame(width: 62, height: 62)
                .accessibilityHidden(true)

            VStack(alignment: .leading, spacing: 10) {
                MonoKicker("Einmal kurz")
                Text("Soll Lotti sich deine Gespräche merken?")
                    .font(RatsFont.title(19))
                    .foregroundStyle(RatsColor.text)
                Text("Wenn du möchtest, speichert Ratslotse deine Verläufe im Konto. Dann findest du sie auf all deinen Geräten unter „Gespräche“. Ohne Speicherung bleibt ein Gespräch nur geöffnet, bis du es schließt.")
                    .font(RatsFont.body(13))
                    .foregroundStyle(RatsColor.secondary)
                    .lineSpacing(2)

                ViewThatFits(in: .horizontal) {
                    HStack(spacing: 8) { choiceButtons }
                    VStack(spacing: 8) { choiceButtons }
                }

                Divider().overlay(RatsColor.separator)

                Label {
                    Text("KI-Hinweis: Antworten können Fehler enthalten. Prüfe wichtige Angaben an den verlinkten Quellen und gib keine personenbezogenen Daten ein.")
                } icon: {
                    Image(systemName: "sparkles")
                        .foregroundStyle(RatsColor.signal)
                }
                .font(RatsFont.body(10))
                .foregroundStyle(RatsColor.muted)
                .lineSpacing(2)

                if let error {
                    Label(error, systemImage: "exclamationmark.triangle")
                        .font(RatsFont.body(11, weight: .medium))
                        .foregroundStyle(RatsColor.danger)
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .padding(16)
        .background(RatsColor.card)
        .overlay {
            RoundedRectangle(cornerRadius: 16, style: .continuous)
                .stroke(RatsColor.primary.opacity(0.24), lineWidth: 1)
        }
        .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
        .shadow(color: RatsColor.primary.opacity(0.07), radius: 14, y: 6)
        .animation(.snappy(duration: 0.22), value: isSaving)
    }

    @ViewBuilder
    private var choiceButtons: some View {
        Button { choose(true) } label: {
            Label(isSaving ? "Wird gespeichert …" : "Ja, merken", systemImage: "checkmark")
                .frame(maxWidth: .infinity)
        }
        .buttonStyle(PrimaryButtonStyle())
        .disabled(isSaving)

        Button { choose(false) } label: {
            Label("Nein, nicht merken", systemImage: "xmark")
                .frame(maxWidth: .infinity)
        }
        .buttonStyle(SecondaryButtonStyle())
        .disabled(isSaving)
    }
}

private struct RatsQuestionComposer: View {
    @Binding var text: String
    @Binding var researchMode: Bool
    let researchRemaining: Int?
    let isSending: Bool
    let action: () -> Void

    private var trimmedText: String {
        text.trimmingCharacters(in: .whitespacesAndNewlines)
    }

    private var researchUnavailable: Bool {
        researchRemaining == 0 && !researchMode
    }

    var body: some View {
        VStack(spacing: 0) {
            HStack(spacing: 9) {
                TextField(
                    researchMode ? "Was soll gründlich untersucht werden?" : "Was möchtest du über den Rat wissen?",
                    text: $text,
                    axis: .vertical
                )
                .font(RatsFont.body())
                .lineLimit(1...4)
                .submitLabel(.send)
                .onSubmit(action)

                Button(action: action) {
                    Image(systemName: isSending ? "stop.fill" : "arrow.up")
                        .font(.system(size: 15, weight: .bold))
                        .foregroundStyle(RatsColor.primaryText)
                        .frame(width: 40, height: 40)
                        .background(
                            RatsColor.primary.opacity(trimmedText.count < 4 && !isSending ? 0.35 : 1)
                        )
                        .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
                        .shadow(color: RatsColor.primary.opacity(isSending ? 0 : 0.2), radius: 8, y: 3)
                }
                .buttonStyle(.plain)
                .disabled(trimmedText.count < 4 && !isSending)
                .accessibilityLabel(isSending ? "Vorgang abbrechen" : "Frage senden")
            }
            .padding(.horizontal, 12)
            .padding(.top, 9)
            .padding(.bottom, 5)

            HStack(spacing: 8) {
                Toggle(isOn: $researchMode) {
                    HStack(spacing: 7) {
                        RatsGlyphView(
                            glyph: .research,
                            color: researchMode ? RatsColor.primary : RatsColor.secondary,
                            lineWidth: 1.7
                        )
                        .frame(width: 16, height: 16)
                        Text(researchUnavailable ? "Heute ausgeschöpft" : "Gründlich recherchieren")
                            .font(RatsFont.body(12, weight: .semibold))
                    }
                }
                .toggleStyle(ResearchPillToggleStyle())
                .disabled(researchUnavailable || isSending)

                if researchMode {
                    Text(researchRemaining.map { "~30 Sek. · noch \($0) heute" } ?? "dauert etwa 30 Sek.")
                        .font(RatsFont.body(10))
                        .foregroundStyle(RatsColor.muted)
                        .lineLimit(1)
                        .transition(.opacity.combined(with: .move(edge: .leading)))
                }
                Spacer(minLength: 0)
            }
            .padding(.horizontal, 9)
            .padding(.bottom, 8)
        }
        .floatingComposerSurface(isActive: researchMode)
        .animation(.snappy(duration: 0.24), value: researchMode)
    }
}

private extension View {
    @ViewBuilder
    func floatingComposerSurface(isActive: Bool) -> some View {
        if #available(iOS 26.0, *) {
            self
                .glassEffect(
                    .regular.tint(RatsColor.card.opacity(0.18)),
                    in: .rect(cornerRadius: 18)
                )
                .overlay {
                    RoundedRectangle(cornerRadius: 18, style: .continuous)
                        .stroke(
                            isActive ? RatsColor.primary.opacity(0.42) : .white.opacity(0.34),
                            lineWidth: 0.8
                        )
                }
                .shadow(color: RatsColor.primary.opacity(0.14), radius: 20, y: 9)
        } else {
            self
                .background {
                    ZStack {
                        RoundedRectangle(cornerRadius: 18, style: .continuous)
                            .fill(.ultraThinMaterial)
                        RoundedRectangle(cornerRadius: 18, style: .continuous)
                            .fill(RatsColor.card.opacity(0.70))
                    }
                }
                .overlay {
                    RoundedRectangle(cornerRadius: 18, style: .continuous)
                        .stroke(
                            isActive ? RatsColor.primary.opacity(0.42) : .white.opacity(0.50),
                            lineWidth: 0.9
                        )
                }
                .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
                .shadow(color: RatsColor.primary.opacity(0.12), radius: 18, y: 8)
        }
    }
}

private struct ResearchPillToggleStyle: ToggleStyle {
    func makeBody(configuration: Configuration) -> some View {
        Button {
            withAnimation(.snappy(duration: 0.24)) { configuration.isOn.toggle() }
        } label: {
            HStack(spacing: 7) {
                configuration.label
                Image(systemName: configuration.isOn ? "xmark" : "plus")
                    .font(.system(size: 9, weight: .bold))
            }
            .foregroundStyle(configuration.isOn ? RatsColor.primary : RatsColor.secondary)
            .padding(.horizontal, 11)
            .frame(minHeight: 34)
            .background(configuration.isOn ? RatsColor.primary.opacity(0.10) : RatsColor.stage)
            .overlay(
                Capsule().stroke(
                    configuration.isOn ? RatsColor.primary.opacity(0.5) : RatsColor.border,
                    lineWidth: 1
                )
            )
            .clipShape(Capsule())
            .contentShape(Capsule())
        }
        .buttonStyle(.plain)
        .accessibilityValue(configuration.isOn ? "Ein" : "Aus")
    }
}

private struct ResearchProgressCard: View {
    let state: ResearchState
    let stop: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 13) {
            HStack(spacing: 12) {
                Lotti3DView(scene: .reading)
                    .frame(width: 54, height: 54)
                    .accessibilityHidden(true)
                VStack(alignment: .leading, spacing: 3) {
                    Text(phaseLabel)
                        .font(RatsFont.body(14, weight: .semibold))
                    Text("Du kannst die App zwischendurch schließen.")
                        .font(RatsFont.body(11))
                        .foregroundStyle(RatsColor.secondary)
                }
                Spacer(minLength: 0)
            }

            ProgressView(value: progress)
                .tint(RatsColor.primary)

            if !state.facets.isEmpty {
                VStack(alignment: .leading, spacing: 8) {
                    ForEach(state.facets) { facet in
                        HStack(spacing: 8) {
                            Image(systemName: facet.hits == nil ? "circle.dotted" : "checkmark.circle.fill")
                                .foregroundStyle(facet.hits == nil ? RatsColor.muted : RatsColor.success)
                            Text(facet.name)
                                .font(RatsFont.body(12, weight: .medium))
                            Spacer(minLength: 0)
                            if let hits = facet.hits {
                                Text("\(hits) Treffer")
                                    .font(RatsFont.mono(9))
                                    .foregroundStyle(RatsColor.muted)
                            }
                        }
                    }
                }
            }

            Button("Recherche abbrechen", role: .destructive, action: stop)
                .font(RatsFont.body(12, weight: .semibold))
        }
        .ratsCard()
    }

    private var phaseLabel: String {
        switch state.phase {
        case "zerlegen": "Frage in Facetten zerlegen …"
        case "suchen": "Passende Beschlüsse durchsuchen …"
        case "lesen": "Ratsunterlagen lesen …"
        default: "Bericht schreiben …"
        }
    }

    private var progress: Double {
        switch state.phase {
        case "zerlegen": 0.08
        case "suchen":
            state.facets.isEmpty
                ? 0.2
                : 0.1 + Double(state.facets.filter { $0.hits != nil }.count) / Double(state.facets.count) * 0.45
        case "lesen": 0.62
        default: 0.82
        }
    }
}

private struct ResearchStoppedCard: View {
    let state: ResearchState
    let requestPartial: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 9) {
            Text("Recherche abgebrochen")
                .font(RatsFont.body(14, weight: .semibold))
            Text(
                state.partialPossible
                    ? "Aus den bereits gelesenen Facetten kann Ratslotse noch einen Teilbericht schreiben."
                    : "Für einen belastbaren Teilbericht war noch nicht genug Material vorhanden."
            )
            .font(RatsFont.body(12))
            .foregroundStyle(RatsColor.secondary)
            if state.partialPossible {
                Button("Teilbericht schreiben", action: requestPartial)
                    .buttonStyle(PrimaryButtonStyle())
            }
        }
        .ratsCard()
    }
}

private struct QuestionTurnView: View {
    let turn: QuestionTurn
    let model: AppModel
    let ask: (String) -> Void
    let stopResearch: (UUID) -> Void
    let requestPartialResearch: (UUID) -> Void
    let reconnectResearch: (UUID) -> Void
    let showsEvidenceInline: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            VStack(alignment: .trailing, spacing: 5) {
                Text(turn.question)
                    .font(RatsFont.body(15, weight: .medium))
                    .padding(.horizontal, 14)
                    .padding(.vertical, 10)
                    .background(RatsColor.primary.opacity(0.08))
                    .overlay(RoundedRectangle(cornerRadius: 14).stroke(RatsColor.primary.opacity(0.18)))
                    .clipShape(RoundedRectangle(cornerRadius: 14))
                if turn.research != nil {
                    HStack(spacing: 5) {
                        RatsGlyphView(glyph: .research, color: RatsColor.primary, lineWidth: 1.65)
                            .frame(width: 13, height: 13)
                        Text("Gründliche Recherche")
                    }
                    .font(RatsFont.body(10, weight: .medium))
                    .foregroundStyle(RatsColor.secondary)
                }
            }
            .frame(maxWidth: .infinity, alignment: .trailing)

            if let research = turn.research, research.status == "laeuft" {
                ResearchProgressCard(state: research) { stopResearch(turn.id) }
            }
            if let research = turn.research, research.status == "gestoppt" {
                ResearchStoppedCard(state: research) {
                    requestPartialResearch(turn.id)
                }
            }

            if let status = turn.status {
                HStack(spacing: 9) {
                    ProgressView().controlSize(.small).tint(RatsColor.primary)
                    Text(status).font(RatsFont.body(13)).foregroundStyle(RatsColor.secondary)
                }
            }
            if !turn.answer.isEmpty {
                CitedAnswerText(
                    text: turn.answer,
                    model: model,
                    sources: turn.sources,
                    evidence: turn.evidence
                )
                    .font(RatsFont.body(15))
                    .foregroundStyle(RatsColor.bodyText)
                    .lineSpacing(6)
            }
            if let error = turn.error {
                ErrorCard(message: error) {
                    if turn.research != nil { reconnectResearch(turn.id) }
                    else { ask(turn.question) }
                }
            }
            if showsEvidenceInline, !turn.sources.isEmpty {
                QuestionSourcesCard(turn: turn, model: model)
            }
            if evidenceVisibility.showsPartyOpinions {
                PartyOpinionsView(turn: turn, model: model)
            }
            CouncilEvidenceBlocks(
                fields: turn.evidence,
                model: model,
                placement: showsEvidenceInline ? .all : .answer
            )
            if !mapPins.isEmpty {
                QuestionEvidenceMap(pins: mapPins)
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
        questionMapPins(for: citationIndex.citedSources)
    }

    private var citationIndex: QuestionCitationIndex {
        QuestionCitationIndex(text: turn.answer, sources: turn.sources)
    }

    private var evidenceVisibility: QuestionEvidenceAvailability {
        QuestionEvidenceAvailability(fields: turn.evidence)
    }
}

struct QuestionCitationIndex {
    let numberByID: [Int: Int]
    let citedSources: [DecisionSummary]
    let uncitedSources: [DecisionSummary]

    init(text: String, sources: [DecisionSummary]) {
        var seenSources = Set<Int>()
        let uniqueSources = sources.filter { seenSources.insert($0.id).inserted }
        let validIDs = Set(uniqueSources.map(\.id))
        var orderedIDs: [Int] = []
        var seenIDs = Set<Int>()
        for id in questionCitationIDs(in: text) where validIDs.contains(id) && seenIDs.insert(id).inserted {
            orderedIDs.append(id)
        }
        let numbers = Dictionary(uniqueKeysWithValues: orderedIDs.enumerated().map { ($0.element, $0.offset + 1) })
        numberByID = numbers
        let sourcesByID = Dictionary(uniqueKeysWithValues: uniqueSources.map { ($0.id, $0) })
        citedSources = orderedIDs.compactMap { sourcesByID[$0] }
        uncitedSources = uniqueSources.filter { numbers[$0.id] == nil }
    }
}

struct QuestionEvidenceAvailability {
    let showsPartyOpinions: Bool
    let showsDebates: Bool
    let showsPress: Bool
    let showsAttachments: Bool
    let showsPlanning: Bool
    let showsBriefs: Bool
    let showsChart: Bool
    let showsSessions: Bool

    init(fields: [String: JSONValue] = [:]) {
        let type = fields["qtype"]?.string?.lowercased() ?? ""
        let debates = fields["debatten"]?.array ?? []

        // Dieselbe Zuständigkeit wie im Web: Der validierte Rechercheplan im
        // Backend schaltet diese Kanäle einzeln frei. Die Oberfläche zeigt nur
        // die tatsächlich gelieferten Ergebnisse und erfindet keine zweite,
        // abweichende Stichwort-Heuristik.
        showsDebates = !debates.isEmpty
        showsPartyOpinions = type != "person" && showsDebates
        showsPress = !(fields["presse"]?.array ?? []).isEmpty
        showsAttachments = !(fields["anlagen"]?.array ?? []).isEmpty
        showsPlanning = !(fields["planungen"]?.array ?? []).isEmpty
        showsBriefs = !(fields["steckbriefe"]?.array ?? []).isEmpty
        showsChart = fields["grafik"] != nil
        showsSessions = !(fields["sitzungen"]?.array ?? []).isEmpty
    }
}

func questionCitationIDs(in text: String) -> [Int] {
    guard let regex = try? NSRegularExpression(pattern: #"\[\d[^\]\n]{0,160}\]"#) else { return [] }
    let ns = text as NSString
    return regex.matches(in: text, range: NSRange(location: 0, length: ns.length)).flatMap { match -> [Int] in
        let marker = ns.substring(with: match.range)
        let inner = String(marker.dropFirst().dropLast())
        if inner.range(of: #"^[\d,\s]+$"#, options: .regularExpression) != nil {
            guard let digits = try? NSRegularExpression(pattern: #"\d+"#) else { return [] }
            let innerNS = inner as NSString
            return digits.matches(in: inner, range: NSRange(location: 0, length: innerNS.length)).compactMap {
                Int(innerNS.substring(with: $0.range))
            }
        }
        guard let first = try? NSRegularExpression(pattern: #"^\s*(\d+)"#),
              let match = first.firstMatch(in: inner, range: NSRange(location: 0, length: (inner as NSString).length))
        else { return [] }
        return [Int((inner as NSString).substring(with: match.range(at: 1)))].compactMap { $0 }
    }
}

func questionCitationMarkdown(
    text: String,
    sources: [DecisionSummary],
    attachmentNumbers: Set<Int> = []
) -> String {
    let normalized = text.replacingOccurrences(
        of: #"(\[(?:A\d{1,2}|\d[^\]\n]{0,160})\])([.!?])(?=\p{Lu})"#,
        with: "$1$2 ",
        options: .regularExpression
    )
    guard let regex = try? NSRegularExpression(
        pattern: #"\[(?:A\d{1,2}|\d[^\]\n]{0,160})\]"#
    ) else { return normalized }
    let ns = normalized as NSString
    let citationIndex = QuestionCitationIndex(text: normalized, sources: sources)
    var attachmentLetters: [Int: String] = [:]
    var result = ""
    var cursor = 0
    for match in regex.matches(in: normalized, range: NSRange(location: 0, length: ns.length)) {
        guard match.range.location >= cursor else { continue }
        result += ns.substring(with: NSRange(location: cursor, length: match.range.location - cursor))
        let marker = ns.substring(with: match.range)
        if marker.hasPrefix("[A"), let number = Int(marker.dropFirst(2).dropLast()),
           attachmentNumbers.contains(number) {
            let scalar = UnicodeScalar(97 + attachmentLetters.count) ?? UnicodeScalar(97)!
            let letter = attachmentLetters[number] ?? String(Character(scalar))
            attachmentLetters[number] = letter
            result += "[\(letter)](ratslotse://attachment/\(number))"
        } else {
            let links = questionCitationIDs(in: marker).compactMap { id -> String? in
                guard let number = citationIndex.numberByID[id] else { return nil }
                return "[\(questionCitationLabel(number))](ratslotse://decision/\(id))"
            }
            result += links.joined(separator: " ")
        }
        cursor = NSMaxRange(match.range)
    }
    if cursor < ns.length {
        result += ns.substring(from: cursor)
    }
    return result
}

func questionCitationLabel(_ number: Int) -> String {
    let circled = [
        "①", "②", "③", "④", "⑤", "⑥", "⑦", "⑧", "⑨", "⑩",
        "⑪", "⑫", "⑬", "⑭", "⑮", "⑯", "⑰", "⑱", "⑲", "⑳",
    ]
    guard circled.indices.contains(number - 1) else { return "[\(number)]" }
    return circled[number - 1]
}

private struct QuestionSourcesCard: View {
    let turn: QuestionTurn
    let model: AppModel
    @State private var showsSearchResults = false

    private var index: QuestionCitationIndex {
        QuestionCitationIndex(text: turn.answer, sources: turn.sources)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            MonoKicker(
                "Amtliche Quellen",
                trailing: "\(index.citedSources.count) zitiert · \(index.citedSources.count + index.uncitedSources.count) gefunden"
            )

            if index.citedSources.isEmpty {
                Text("Die Suche hat Ratsunterlagen gefunden, aber die Antwort zitiert noch keine davon direkt.")
                    .font(RatsFont.body(11.5))
                    .foregroundStyle(RatsColor.secondary)
                    .lineSpacing(2)
            } else {
                ForEach(Array(index.citedSources.enumerated()), id: \.element.id) { position, source in
                    Button { model.navigation.append(.decision(id: source.id)) } label: {
                        SourceRow(
                            number: index.numberByID[source.id] ?? position + 1,
                            title: source.title,
                            meta: questionSourceMeta(source)
                        )
                    }
                    .buttonStyle(.plain)
                    if position < index.citedSources.count - 1 {
                        Divider().overlay(RatsColor.separator)
                    }
                }
            }

            if !index.uncitedSources.isEmpty {
                DisclosureGroup(isExpanded: $showsSearchResults) {
                    VStack(spacing: 10) {
                        Text("Diese Unterlagen wurden gefunden, im Antworttext aber nicht als Beleg verwendet.")
                            .font(RatsFont.body(10.5))
                            .foregroundStyle(RatsColor.muted)
                            .frame(maxWidth: .infinity, alignment: .leading)
                        ForEach(Array(index.uncitedSources.enumerated()), id: \.element.id) { position, source in
                            Button { model.navigation.append(.decision(id: source.id)) } label: {
                                UncitedQuestionSourceRow(source: source)
                            }
                            .buttonStyle(.plain)
                            if position < index.uncitedSources.count - 1 {
                                Divider().overlay(RatsColor.separator)
                            }
                        }
                    }
                    .padding(.top, 10)
                } label: {
                    Text("\(index.uncitedSources.count) weitere Suchtreffer")
                        .font(RatsFont.body(12, weight: .semibold))
                        .foregroundStyle(RatsColor.secondary)
                }
            }
        }
        .ratsCard()
    }
}

private struct UncitedQuestionSourceRow: View {
    let source: DecisionSummary

    var body: some View {
        HStack(spacing: 10) {
            Circle()
                .fill(RatsColor.border)
                .frame(width: 6, height: 6)
            VStack(alignment: .leading, spacing: 2) {
                Text(source.title)
                    .font(RatsFont.body(12.5, weight: .medium))
                    .foregroundStyle(RatsColor.text)
                    .lineLimit(2)
                Text(questionSourceMeta(source))
                    .font(RatsFont.mono(9))
                    .foregroundStyle(RatsColor.muted)
            }
            Spacer(minLength: 0)
            Image(systemName: "chevron.right")
                .font(.caption)
                .foregroundStyle(RatsColor.muted)
        }
        .contentShape(Rectangle())
    }
}

private func questionSourceMeta(_ source: DecisionSummary) -> String {
    let type: String = {
        let kind = source.kind?.lowercased() ?? ""
        if kind.contains("beschluss") || source.outcome != nil { return "Beschluss" }
        if kind.contains("vorlage") || source.templateNumber != nil { return "Vorlage" }
        return "Ratsunterlage"
    }()
    return [type, source.committee, RatsDate.short(source.sessionDate)]
        .compactMap { value in
            guard let value, !value.isEmpty else { return nil }
            return value
        }
        .joined(separator: " · ")
}

struct QuestionMapPin: Identifiable {
    let id: Int
    let name: String
    let coordinate: CLLocationCoordinate2D
}

private struct QuestionEvidenceMap: View {
    let pins: [QuestionMapPin]

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            MonoKicker("Orte aus zitierten Quellen", trailing: "\(pins.count)")
            Map(initialPosition: .region(questionMapRegion(for: pins))) {
                ForEach(pins) { pin in
                    Marker(pin.name, coordinate: pin.coordinate).tint(RatsColor.signal)
                }
            }
            .frame(height: 190)
            .clipShape(RoundedRectangle(cornerRadius: 11))
            .accessibilityLabel("Karte der in der Antwort genannten Orte")
        }
        .ratsCard()
    }
}

func questionMapPins(for sources: [DecisionSummary]) -> [QuestionMapPin] {
    var seen = Set<String>()
    return sources.compactMap { source in
        guard let latitude = source.latitude, let longitude = source.longitude else { return nil }
        let key = String(format: "%.4f,%.4f", latitude, longitude)
        guard seen.insert(key).inserted else { return nil }
        return QuestionMapPin(
            id: source.id,
            name: source.placeName ?? source.title,
            coordinate: CLLocationCoordinate2D(latitude: latitude, longitude: longitude)
        )
    }
}

private func questionMapRegion(for pins: [QuestionMapPin]) -> MKCoordinateRegion {
    let latitudes = pins.map(\.coordinate.latitude)
    let longitudes = pins.map(\.coordinate.longitude)
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

private struct QuestionEvidenceSidebar: View {
    let turn: QuestionTurn?
    let model: AppModel

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                HStack(spacing: 11) {
                    RatsGlyphView(glyph: .analysis, color: RatsColor.primary, lineWidth: 1.65)
                        .frame(width: 19, height: 19)
                        .frame(width: 38, height: 38)
                        .background(RatsColor.primary.opacity(0.09))
                        .clipShape(RoundedRectangle(cornerRadius: 11, style: .continuous))
                        .accessibilityHidden(true)
                    VStack(alignment: .leading, spacing: 1) {
                        Text("Quellen & Belege")
                            .font(RatsFont.title(19))
                            .foregroundStyle(RatsColor.text)
                        Text("Direkt neben deiner Antwort")
                            .font(RatsFont.body(11.5))
                            .foregroundStyle(RatsColor.secondary)
                    }
                }

                if let turn {
                    evidence(for: turn)
                } else {
                    emptyState
                }
            }
            .padding(.horizontal, 18)
            .padding(.top, 18)
            .padding(.bottom, 28)
        }
        .scrollIndicators(.hidden)
        .background(RatsColor.card.opacity(0.42))
    }

    @ViewBuilder
    private func evidence(for turn: QuestionTurn) -> some View {
        Text(turn.question)
            .font(RatsFont.body(13, weight: .semibold))
            .foregroundStyle(RatsColor.bodyText)
            .lineLimit(3)
            .padding(.bottom, 2)

        if turn.status != nil || turn.research?.status == "laeuft" {
            RatsLoadingState(message: "Belege werden zusammengestellt …")
        }

        if !turn.sources.isEmpty {
            QuestionSourcesCard(turn: turn, model: model)
        }
        CouncilEvidenceBlocks(fields: turn.evidence, model: model, placement: .sources)

        if turn.status == nil,
           turn.research?.status != "laeuft",
           turn.sources.isEmpty,
           !hasSourceEvidence(turn.evidence) {
            VStack(alignment: .leading, spacing: 8) {
                MonoKicker("Beleglage")
                Text(turn.answer.isEmpty ? "Stell links eine Frage – passende Ratsunterlagen erscheinen dann hier." : "Zu dieser Antwort wurden keine zusätzlichen Ratsunterlagen gefunden.")
                    .font(RatsFont.body(12.5))
                    .foregroundStyle(RatsColor.secondary)
                    .lineSpacing(2)
            }
            .padding(14)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(RatsColor.card)
            .overlay(RoundedRectangle(cornerRadius: 13, style: .continuous).stroke(RatsColor.border))
            .clipShape(RoundedRectangle(cornerRadius: 13, style: .continuous))
        }
    }

    private var emptyState: some View {
        VStack(spacing: 9) {
            Lotti3DView(scene: .reading, animated: false)
                .frame(width: 116, height: 100)
            Text("Lotti legt die Unterlagen bereit")
                .font(RatsFont.body(14, weight: .semibold))
                .foregroundStyle(RatsColor.text)
            Text("Sobald du links eine Frage stellst, bleiben Quellen, Sitzungen und weitere Belege hier beim Lesen sichtbar.")
                .font(RatsFont.body(12))
                .foregroundStyle(RatsColor.secondary)
                .multilineTextAlignment(.center)
                .lineSpacing(2)
        }
        .frame(maxWidth: .infinity)
        .padding(.horizontal, 12)
        .padding(.vertical, 28)
    }

    private func hasSourceEvidence(_ fields: [String: JSONValue]) -> Bool {
        ["anlagen", "presse", "debatten"].contains {
            !(fields[$0]?.array ?? []).isEmpty
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

    @ViewBuilder
    var body: some View {
        Group {
            if error != nil {
                EmptyView()
            } else if let response, response.parties.count < 2 {
                EmptyView()
            } else {
                DisclosureGroup {
                    VStack(alignment: .leading, spacing: 12) {
                        if let response {
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
                                if opinion.id != response.parties.last?.id {
                                    Divider().overlay(RatsColor.separator)
                                }
                            }
                            if !response.withoutContributions.isEmpty {
                                Text("Ohne zuordenbaren Beitrag: \(response.withoutContributions.joined(separator: ", "))")
                                    .font(RatsFont.body(11)).foregroundStyle(RatsColor.muted)
                            }
                        } else {
                            ProgressView("Debatten werden automatisch ausgewertet …")
                        }
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
        }
        .task(id: turn.id) {
            await load()
        }
    }

    private func load() async {
        struct Body: Codable, Sendable { let frage: String; let beschluss_ids: [Int] }
        let citedIDs = QuestionCitationIndex(text: turn.answer, sources: turn.sources)
            .citedSources
            .map(\.id)
        let decisionIDs = citedIDs.isEmpty
            ? Array(turn.sources.prefix(20).map(\.id))
            : citedIDs
        guard response == nil, !isLoading else { return }
        error = nil
        isLoading = true
        defer { isLoading = false }
        do {
            response = try await model.api.send(
                "/api/council/partei-meinungen",
                body: Body(frage: String(turn.question.prefix(300)), beschluss_ids: decisionIDs)
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

enum CouncilEvidencePlacement {
    case all
    case answer
    case sources
}

struct CouncilEvidenceBlocks: View {
    let fields: [String: JSONValue]
    let model: AppModel
    var placement: CouncilEvidencePlacement = .all

    private var visibility: QuestionEvidenceAvailability {
        QuestionEvidenceAvailability(fields: fields)
    }
    private var attachments: [[String: JSONValue]] {
        visibility.showsAttachments ? objects("anlagen") : []
    }
    private var press: [[String: JSONValue]] {
        visibility.showsPress ? objects("presse") : []
    }
    private var debates: [[String: JSONValue]] {
        visibility.showsDebates ? objects("debatten") : []
    }
    private var sessions: [[String: JSONValue]] {
        let rows = objects("sitzungen")
        return visibility.showsSessions ? rows : []
    }
    private var planning: [[String: JSONValue]] {
        visibility.showsPlanning ? objects("planungen") : []
    }
    private var briefs: [[String: JSONValue]] {
        visibility.showsBriefs ? objects("steckbriefe") : []
    }
    private var includesAnswerInsights: Bool { placement != .sources }
    private var includesSourceEvidence: Bool { placement != .answer }

    @ViewBuilder
    var body: some View {
        if includesAnswerInsights, fields["beleglage"]?.string == "duenn" {
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

        if includesAnswerInsights, !briefs.isEmpty {
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

        if includesAnswerInsights, !sessions.isEmpty {
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

        if includesSourceEvidence, !attachments.isEmpty {
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

        if includesSourceEvidence, !press.isEmpty {
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

        if includesSourceEvidence, !debates.isEmpty {
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

        if includesAnswerInsights, !planning.isEmpty {
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

        if includesAnswerInsights,
           visibility.showsChart,
           let chart = EvidenceChartData(fields["grafik"]) {
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
    var sources: [DecisionSummary] = []
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
        let markdown = citationMarkdown
        var output = (try? AttributedString(markdown: markdown)) ?? AttributedString(markdown)
        for run in output.runs {
            guard let link = run.link, link.scheme == "ratslotse" else { continue }
            output[run.range].foregroundColor = RatsColor.primary
            if link.host == "decision" {
                output[run.range].font = .system(size: 12, weight: .semibold, design: .rounded)
                output[run.range].baselineOffset = 1
            } else {
                output[run.range].font = RatsFont.body(10, weight: .bold)
            }
        }
        return output
    }

    private var citationMarkdown: String {
        let attachmentNumbers = Set(
            (evidence["anlagen"]?.array ?? []).enumerated().map { offset, value in
                value.object?["nr"]?.int ?? offset + 1
            }
        )
        return questionCitationMarkdown(
            text: text,
            sources: sources,
            attachmentNumbers: attachmentNumbers
        )
    }

    private func attachmentURL(number: Int) -> URL? {
        let rows = evidence["anlagen"]?.array?.compactMap(\.object) ?? []
        guard let raw = rows.first(where: { $0["nr"]?.int == number })?["url"]?.string else { return nil }
        return URL(string: raw)
    }
}
