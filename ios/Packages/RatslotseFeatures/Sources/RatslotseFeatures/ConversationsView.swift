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
                        MonoKicker("Verlauf", trailing: "\(conversations.count)")
                        ForEach(conversations) { conversation in
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
