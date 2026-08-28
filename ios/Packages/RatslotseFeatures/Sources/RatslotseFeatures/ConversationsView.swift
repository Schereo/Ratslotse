import RatslotseAPI
import RatslotseDesign
import SwiftUI

struct ConversationsView: View {
    let model: AppModel
    @Environment(\.dismiss) private var dismiss
    @State private var conversations: [ConversationSummary] = []
    @State private var selected: JSONValue?
    @State private var error: String?
    @State private var isLoading = true
    @State private var search = ""
    @State private var renameTarget: ConversationSummary?
    @State private var renameTitle = ""

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                RatsSheetHeader(
                    "Meine Gespräche",
                    leadingTitle: selected == nil ? "Schließen" : "Zurück",
                    leadingAction: {
                        if selected == nil { dismiss() } else { selected = nil }
                    }
                )
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 14) {
                    if selected == nil {
                        RatsModalIntro(
                            kicker: "Frag den Rat",
                            title: "Meine Gespräche",
                            message: "Hier findest du deine bisherigen Fragen samt Antworten und amtlichen Quellen wieder.",
                            symbol: "bubble.left.and.bubble.right.fill"
                        )
                    }

                    if let selected {
                        RatsSectionPanel("Gespräch", symbol: "text.bubble") {
                            ConversationTranscript(payload: selected)
                        }
                    } else if isLoading {
                        RatsLoadingState(message: "Gespräche werden geladen …")
                    } else if conversations.isEmpty && error == nil {
                        RatsEmptyState(
                            title: "Noch keine Gespräche",
                            message: "Sobald du dem Rat eine Frage stellst, kannst du die Unterhaltung hier erneut öffnen.",
                            symbol: "bubble.left.and.bubble.right"
                        )
                    } else {
                        if conversations.count >= 8 {
                            HStack(spacing: 9) {
                                Image(systemName: "magnifyingglass")
                                    .foregroundStyle(RatsColor.muted)
                                TextField("In Gesprächen suchen …", text: $search)
                                    .textInputAutocapitalization(.never)
                                    .autocorrectionDisabled()
                            }
                            .font(RatsFont.body(14))
                            .padding(.horizontal, 13)
                            .frame(minHeight: 46)
                            .background(RatsColor.card)
                            .overlay(RoundedRectangle(cornerRadius: 13).stroke(RatsColor.border))
                            .clipShape(RoundedRectangle(cornerRadius: 13, style: .continuous))
                        }
                        MonoKicker("Verlauf", trailing: "\(conversations.count)")
                        if filteredConversations.isEmpty {
                            RatsEmptyState(
                                title: "Kein Treffer",
                                message: "Kein Gespräch passt zu „\(search.trimmingCharacters(in: .whitespacesAndNewlines))“.",
                                symbol: "text.magnifyingglass"
                            )
                        }
                        ForEach(filteredConversations) { conversation in
                            HStack(spacing: 10) {
                                Button { Task { await open(conversation.id) } } label: {
                                    HStack(spacing: 12) {
                                        Image(systemName: "bubble.left.and.text.bubble.right.fill")
                                            .font(.system(size: 16))
                                            .foregroundStyle(RatsColor.primary)
                                            .frame(width: 38, height: 38)
                                            .background(RatsColor.primary.opacity(0.08))
                                            .clipShape(RoundedRectangle(cornerRadius: 11, style: .continuous))
                                            .accessibilityHidden(true)
                                        VStack(alignment: .leading, spacing: 4) {
                                            Text(conversation.title)
                                                .font(RatsFont.body(15, weight: .semibold))
                                                .foregroundStyle(RatsColor.text)
                                                .multilineTextAlignment(.leading)
                                            Text(conversationMeta(conversation))
                                                .font(RatsFont.mono(10))
                                                .foregroundStyle(RatsColor.muted)
                                        }
                                        Spacer(minLength: 4)
                                        Image(systemName: "chevron.right")
                                            .font(.caption)
                                            .foregroundStyle(RatsColor.muted)
                                    }
                                }
                                .buttonStyle(.plain)
                                Menu {
                                    Button("Umbenennen", systemImage: "pencil") {
                                        renameTitle = conversation.title
                                        renameTarget = conversation
                                    }
                                    Button("Gespräch löschen", systemImage: "trash", role: .destructive) {
                                        remove(conversation.id)
                                    }
                                } label: {
                                    Image(systemName: "ellipsis")
                                        .foregroundStyle(RatsColor.secondary)
                                        .frame(width: 30, height: 34)
                                }
                                .accessibilityLabel("Gespräch verwalten")
                            }
                            .ratsCard()
                        }
                    }
                    if let error { ErrorCard(message: error) { Task { await load() } } }
                    }
                    .frame(maxWidth: 720, alignment: .leading)
                    .padding(.horizontal, 18)
                    .padding(.vertical, 22)
                }
                .background(RatsColor.page)
            }
            .toolbar(.hidden, for: .navigationBar)
        }
        .task { await load() }
        .alert("Gespräch umbenennen", isPresented: Binding(
            get: { renameTarget != nil },
            set: { if !$0 { renameTarget = nil } }
        )) {
            TextField("Titel", text: $renameTitle)
            Button("Abbrechen", role: .cancel) { renameTarget = nil }
            Button("Speichern") {
                guard let target = renameTarget else { return }
                renameTarget = nil
                Task { await rename(target) }
            }
            .disabled(renameTitle.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
        } message: {
            Text("Ein kurzer, eindeutiger Titel macht den Verlauf später leichter auffindbar.")
        }
    }

    private var filteredConversations: [ConversationSummary] {
        let term = search.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !term.isEmpty else { return conversations }
        return conversations.filter { $0.title.localizedCaseInsensitiveContains(term) }
    }

    private func conversationMeta(_ conversation: ConversationSummary) -> String {
        let turns = "\(conversation.turnCount) \(conversation.turnCount == 1 ? "Frage" : "Fragen")"
        guard let date = RatsDate.short(conversation.updatedAt) else { return turns }
        return "\(turns) · \(date)"
    }

    private func load() async {
        isLoading = true
        defer { isLoading = false }
        do {
            let response: JSONValue = try await model.api.get("/api/council/gespraeche")
            conversations = response.object?["gespraeche"]?.array?.compactMap {
                try? $0.decoded(ConversationSummary.self)
            } ?? []
            error = nil
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

    private func rename(_ conversation: ConversationSummary) async {
        struct Body: Codable, Sendable { let titel: String }
        let clean = renameTitle.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !clean.isEmpty else { return }
        do {
            try await model.api.sendVoid(
                "/api/council/gespraeche/\(conversation.id)",
                method: .patch,
                body: Body(titel: clean)
            )
            if let index = conversations.firstIndex(where: { $0.id == conversation.id }) {
                conversations[index] = ConversationSummary(
                    id: conversation.id,
                    title: clean,
                    updatedAt: conversation.updatedAt,
                    turnCount: conversation.turnCount
                )
            }
            error = nil
        } catch {
            self.error = error.localizedDescription
        }
    }
}
private struct ConversationTranscript: View {
    let payload: JSONValue

    var body: some View {
        let turns = payload.object?["turns"]?.array ?? []
        VStack(alignment: .leading, spacing: 24) {
            ForEach(Array(turns.enumerated()), id: \.offset) { index, turn in
                if let fields = turn.object {
                    let question = fields["frage"]?.string ?? fields["question"]?.string ?? "Frage"
                    let answer = fields["antwort"]?.string ?? fields["answer"]?.string ?? ""
                    VStack(alignment: .leading, spacing: 13) {
                        MonoKicker("Frage \(index + 1)")
                        Text(question)
                            .font(RatsFont.body(14, weight: .semibold))
                            .padding(.horizontal, 13)
                            .padding(.vertical, 10)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .background(RatsColor.primary.opacity(0.08))
                            .overlay(RoundedRectangle(cornerRadius: 12).stroke(RatsColor.primary.opacity(0.16)))
                            .clipShape(RoundedRectangle(cornerRadius: 12))
                        Text((try? AttributedString(markdown: answer)) ?? AttributedString(answer))
                            .font(RatsFont.body(14))
                            .foregroundStyle(RatsColor.bodyText)
                            .lineSpacing(5)
                        let sources = fields["quellen"]?.object?["sources"]?.array ?? []
                        if !sources.isEmpty {
                            VStack(alignment: .leading, spacing: 8) {
                                MonoKicker("Quellen", trailing: "\(sources.count)")
                                ForEach(Array(sources.enumerated()), id: \.offset) { _, source in
                                    if let source = source.object {
                                        Label {
                                            VStack(alignment: .leading, spacing: 2) {
                                                Text(source["title"]?.string ?? "Ratsunterlage")
                                                    .font(RatsFont.body(12, weight: .semibold))
                                                Text([source["committee"]?.string, RatsDate.short(source["session_date"]?.string)]
                                                    .compactMap { $0 }.joined(separator: " · "))
                                                    .font(RatsFont.mono(9))
                                                    .foregroundStyle(RatsColor.muted)
                                            }
                                        } icon: {
                                            Image(systemName: "doc.text").foregroundStyle(RatsColor.primary)
                                        }
                                    }
                                }
                            }
                            .padding(12)
                            .background(RatsColor.card)
                            .overlay(RoundedRectangle(cornerRadius: 11).stroke(RatsColor.border))
                            .clipShape(RoundedRectangle(cornerRadius: 11))
                        }
                    }
                }
            }
        }
        .padding(.vertical, 6)
    }
}
