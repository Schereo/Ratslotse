import RatslotseAPI
import RatslotseDesign
import SwiftUI

private struct DeepCurrent: Codable, Sendable {
    let job: DeepSnapshot?
    let frei: Int?
}

private struct DeepStart: Codable, Sendable {
    let jobID: String
    let frei: Int?
    enum CodingKeys: String, CodingKey { case jobID = "job_id"; case frei }
}

private struct DeepSnapshot: Codable, Sendable {
    let id: String
    let frage: String
    let status: String
    let bericht: String?
    let quellen: JSONValue?
}

private struct DeepFacet: Identifiable {
    let id = UUID()
    let name: String
    var hits: Int?
}

struct DeepResearchView: View {
    let model: AppModel
    @Environment(\.dismiss) private var dismiss
    @Environment(\.scenePhase) private var scenePhase
    @State private var question: String
    @State private var jobID: String?
    @State private var free: Int?
    @State private var phase = "zerlegen"
    @State private var facets: [DeepFacet] = []
    @State private var report = ""
    @State private var sources: [DecisionSummary] = []
    @State private var evidence: [String: JSONValue] = [:]
    @State private var eventsSeen = 0
    @State private var isRunning = false
    @State private var stopped = false
    @State private var partialPossible = false
    @State private var error: String?
    @State private var streamTask: Task<Void, Never>?

    init(model: AppModel, initialQuestion: String) {
        self.model = model
        _question = State(initialValue: initialQuestion)
    }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    if jobID == nil {
                        intro
                    } else {
                        researchContent
                    }
                }
                .frame(maxWidth: 720, alignment: .leading)
                .padding(18)
            }
            .background(RatsColor.stage)
            .navigationTitle("Gründliche Recherche")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Schließen") { dismiss() } }
            }
        }
        .task { await restoreCurrent() }
        .onDisappear { streamTask?.cancel() }
        .onChange(of: scenePhase) { _, phase in
            if phase == .active, isRunning, let jobID { connect(jobID: jobID) }
            else if phase != .active { streamTask?.cancel(); streamTask = nil }
        }
    }

    private var intro: some View {
        VStack(alignment: .leading, spacing: 16) {
            Image(systemName: "flask")
                .font(.system(size: 32)).foregroundStyle(RatsColor.primary)
            Text("Mehr als eine schnelle Antwort").font(RatsFont.title(26))
            Text("Ratslotse zerlegt die Frage in Facetten, liest mehr Beschlüsse und schreibt einen gegliederten Bericht. Das dauert meist rund 30 Sekunden.")
                .foregroundStyle(RatsColor.secondary).lineSpacing(4)
            TextField("Was soll gründlich untersucht werden?", text: $question, axis: .vertical)
                .lineLimit(3...8)
                .padding(13)
                .background(RatsColor.card)
                .overlay(RoundedRectangle(cornerRadius: 12).stroke(RatsColor.border))
                .clipShape(RoundedRectangle(cornerRadius: 12))
            Button("Recherche starten") { Task { await start() } }
                .buttonStyle(PrimaryButtonStyle())
                .disabled(question.trimmingCharacters(in: .whitespacesAndNewlines).count < 4 || free == 0)
            if let free { Text(free > 0 ? "Noch \(free) Recherchen heute" : "Heute ist das Kontingent aufgebraucht.").font(RatsFont.body(12)).foregroundStyle(RatsColor.muted) }
            if let error { ErrorCard(message: error) { Task { await start() } } }
        }
        .ratsCard()
    }

    @ViewBuilder
    private var researchContent: some View {
        MonoKicker("Gründliche Recherche", trailing: free.map { "noch \($0) heute" })
        Text(question).font(RatsFont.title(24))
        if isRunning {
            VStack(alignment: .leading, spacing: 14) {
                HStack {
                    ProgressView().tint(RatsColor.primary)
                    Text(phaseLabel).font(RatsFont.body(14, weight: .semibold))
                }
                ProgressView(value: progress).tint(RatsColor.primary)
                ForEach(facets) { facet in
                    HStack {
                        Image(systemName: facet.hits == nil ? "circle.dotted" : "checkmark.circle.fill")
                            .foregroundStyle(facet.hits == nil ? RatsColor.muted : RatsColor.success)
                        Text(facet.name)
                        Spacer()
                        if let hits = facet.hits { Text("\(hits) Treffer").font(RatsFont.mono(10)).foregroundStyle(RatsColor.muted) }
                    }
                    .font(RatsFont.body(13))
                }
                Text("Du kannst die App schließen. Der Job läuft auf dem Server weiter und Ratslotse meldet sich, wenn der Bericht fertig ist.")
                    .font(RatsFont.body(11)).foregroundStyle(RatsColor.muted)
                Button("Recherche abbrechen", role: .destructive) { Task { await stop() } }
            }
            .ratsCard()
        }
        if stopped {
            VStack(alignment: .leading, spacing: 10) {
                Text("Recherche abgebrochen").font(RatsFont.body(15, weight: .semibold))
                Text(partialPossible ? "Aus den fertigen Facetten kann noch ein Teilbericht entstehen." : "Es war noch nicht genug Material für einen Teilbericht vorhanden.")
                    .font(RatsFont.body(13)).foregroundStyle(RatsColor.secondary)
                if partialPossible {
                    Button("Teilbericht schreiben") { Task { await requestPartial() } }.buttonStyle(PrimaryButtonStyle())
                }
            }
            .ratsCard()
        }
        if !report.isEmpty {
            VStack(alignment: .leading, spacing: 14) {
                MonoKicker("Bericht")
                CitedAnswerText(text: report, model: model, evidence: evidence)
                    .font(RatsFont.body(15)).foregroundStyle(RatsColor.bodyText).lineSpacing(6)
                ShareLink(item: report) { Label("Bericht teilen", systemImage: "square.and.arrow.up") }
                    .buttonStyle(SecondaryButtonStyle())
            }
            .ratsCard()
        }
        CouncilEvidenceBlocks(fields: evidence, model: model)
        if !sources.isEmpty {
            VStack(alignment: .leading, spacing: 12) {
                MonoKicker("Quellen", trailing: "\(sources.count)")
                ForEach(sources) { source in
                    Button { model.navigation.append(.decision(id: source.id)); dismiss() } label: {
                        SourceRow(number: source.id, title: source.title, meta: source.committee)
                    }.buttonStyle(.plain)
                }
            }
            .ratsCard()
        }
        if let error { ErrorCard(message: error) { if let jobID { connect(jobID: jobID) } } }
    }

    private var phaseLabel: String {
        switch phase { case "zerlegen": "Frage in Facetten zerlegen …"; case "suchen": "Facetten durchsuchen …"; case "lesen": "Dokumente lesen …"; default: "Bericht schreiben …" }
    }

    private var progress: Double {
        switch phase {
        case "zerlegen": 0.08
        case "suchen": facets.isEmpty ? 0.2 : 0.1 + Double(facets.filter { $0.hits != nil }.count) / Double(facets.count) * 0.45
        case "lesen": 0.62
        default: 0.82
        }
    }

    private func restoreCurrent() async {
        do {
            let current: DeepCurrent = try await model.api.get("/api/council/deep-research/aktuell")
            free = current.frei
            guard let job = current.job else { return }
            apply(snapshot: job)
            if job.status == "laeuft" { connect(jobID: job.id) }
            else { await loadSnapshot(jobID: job.id) }
        } catch { self.error = error.localizedDescription }
    }

    private func start() async {
        struct Body: Codable, Sendable { let frage: String }
        error = nil
        do {
            let response: DeepStart = try await model.api.send(
                "/api/council/deep-research", body: Body(frage: question)
            )
            jobID = response.jobID
            free = response.frei
            isRunning = true
            stopped = false
            model.hasRecoverableResearch = true
            connect(jobID: response.jobID)
        } catch { self.error = error.localizedDescription }
    }

    private func connect(jobID: String) {
        streamTask?.cancel()
        streamTask = Task {
            var retryDelay = 1.0
            while isRunning, !Task.isCancelled {
                do {
                    let request = try await model.api.makeStreamingRequest(
                        "/api/council/deep-research/\(jobID)/events",
                        query: [.init(name: "ab", value: String(eventsSeen))]
                    )
                    for try await event in model.sse.events(for: request) {
                        eventsSeen += 1
                        apply(event: event)
                        retryDelay = 1
                    }
                    if isRunning { await loadSnapshot(jobID: jobID) }
                    return
                } catch let apiError as APIError where apiError.statusCode == 410 {
                    await loadSnapshot(jobID: jobID)
                    return
                } catch is CancellationError {
                    // Backgrounding is expected. scenePhase reconnects with `ab`.
                    return
                } catch {
                    self.error = "Verbindung unterbrochen – Ratslotse verbindet sich erneut."
                    guard isRunning else { return }
                    try? await Task.sleep(for: .seconds(retryDelay))
                    retryDelay = min(8, retryDelay * 2)
                }
            }
        }
    }

    private func apply(event: SSEEvent) {
        switch event.type {
        case "phase": phase = event.fields["phase"]?.string ?? phase
        case "facetten":
            facets = event.fields["facetten"]?.array?.compactMap(\.string).map { DeepFacet(name: $0) } ?? []
            phase = "suchen"
        case "facette":
            let name = event.fields["name"]?.string
            if let index = facets.firstIndex(where: { $0.name == name }) { facets[index].hits = event.fields["treffer"]?.int }
        case "sources":
            evidence = event.fields
            sources = event.fields["sources"]?.array?.compactMap { try? $0.decoded(DecisionSummary.self) } ?? []
        case "token": report += event.text ?? ""
        case "replace": report = event.text ?? report
        case "gestoppt":
            isRunning = false; stopped = true
            partialPossible = event.fields["teilbericht_moeglich"]?.bool ?? false
        case "fehler": isRunning = false; error = "Die Recherche ist abgebrochen. Der Versuch zählt nicht gegen dein Kontingent."
        case "done":
            isRunning = false
            model.hasRecoverableResearch = false
            Task { try? await model.api.sendVoid("/api/council/deep-research/\(jobID ?? "")/gesehen") }
        default: break
        }
    }

    private func loadSnapshot(jobID: String) async {
        do { apply(snapshot: try await model.api.get("/api/council/deep-research/\(jobID)")) }
        catch { self.error = error.localizedDescription }
    }

    private func apply(snapshot: DeepSnapshot) {
        jobID = snapshot.id
        question = snapshot.frage
        report = snapshot.bericht ?? report
        isRunning = snapshot.status == "laeuft"
        stopped = snapshot.status == "gestoppt"
        if let root = snapshot.quellen?.object {
            evidence = root
            sources = root["sources"]?.array?.compactMap { try? $0.decoded(DecisionSummary.self) } ?? []
        }
        model.hasRecoverableResearch = isRunning || (snapshot.bericht != nil)
    }

    private func stop() async {
        guard let jobID else { return }
        do {
            let response: JSONValue = try await model.api.sendWithoutBody(
                "/api/council/deep-research/\(jobID)/stop"
            )
            isRunning = false
            stopped = true
            partialPossible = response.object?["teilbericht_moeglich"]?.bool ?? false
        } catch { self.error = error.localizedDescription }
    }

    private func requestPartial() async {
        guard let jobID else { return }
        do {
            let _: JSONValue = try await model.api.sendWithoutBody(
                "/api/council/deep-research/\(jobID)/teilbericht"
            )
            stopped = false
            isRunning = true
            connect(jobID: jobID)
        } catch { self.error = error.localizedDescription }
    }
}

struct ConversationsView: View {
    let model: AppModel
    @Environment(\.dismiss) private var dismiss
    @State private var conversations: [ConversationSummary] = []
    @State private var selected: JSONValue?
    @State private var error: String?

    var body: some View {
        NavigationStack {
            List {
                if let selected {
                    Section("Gespräch") { ConversationTranscript(payload: selected) }
                } else if conversations.isEmpty && error == nil {
                    ContentUnavailableView("Noch keine Gespräche", systemImage: "bubble.left.and.bubble.right")
                } else {
                    ForEach(conversations) { conversation in
                        Button(conversation.title) { Task { await open(conversation.id) } }
                            .swipeActions {
                                Button("Löschen", role: .destructive) { remove(conversation.id) }
                            }
                    }
                }
                if let error { Text(error).foregroundStyle(RatsColor.danger) }
            }
            .navigationTitle("Meine Gespräche")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button(selected == nil ? "Schließen" : "Zurück") {
                        if selected == nil { dismiss() } else { selected = nil }
                    }
                }
            }
        }
        .task { await load() }
    }

    private func load() async {
        do {
            let response: JSONValue = try await model.api.get("/api/council/gespraeche")
            conversations = response.object?["gespraeche"]?.array?.compactMap {
                try? $0.decoded(ConversationSummary.self)
            } ?? []
        } catch { self.error = error.localizedDescription }
    }

    private func open(_ id: Int) async {
        do { selected = try await model.api.get("/api/council/gespraeche/\(id)") }
        catch { self.error = error.localizedDescription }
    }

    private func remove(_ id: Int) {
        Task {
            do {
                try await model.api.sendVoid("/api/council/gespraeche/\(id)", method: .delete)
                conversations.removeAll { $0.id == id }
            } catch { self.error = error.localizedDescription }
        }
    }
}

private struct ConversationTranscript: View {
    let payload: JSONValue
    var body: some View {
        let turns = payload.object?["turns"]?.array ?? []
        VStack(alignment: .leading, spacing: 16) {
            ForEach(Array(turns.enumerated()), id: \.offset) { _, turn in
                if let fields = turn.object {
                    Text(fields["frage"]?.string ?? fields["question"]?.string ?? "Frage")
                        .font(RatsFont.body(14, weight: .semibold))
                    Text(fields["antwort"]?.string ?? fields["answer"]?.string ?? "")
                        .font(RatsFont.body(13)).foregroundStyle(RatsColor.secondary)
                }
            }
        }
    }
}
