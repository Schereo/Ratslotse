import RatslotseAPI
import RatslotseDesign
import SwiftUI

struct ConversationsView: View {
    let model: AppModel
    let activeConversationID: Int?
    let currentTitle: String?
    let currentTurnCount: Int
    let onNew: () -> Void
    let onOpen: (Int, JSONValue) -> Void
    let onDeletedActive: () -> Void
    @Environment(\.dismiss) private var dismiss
    @State private var conversations: [ConversationSummary] = []
    @State private var error: String?
    @State private var isLoading = true
    @State private var openingID: Int?
    @State private var search = ""
    @State private var renameTarget: ConversationSummary?
    @State private var renameTitle = ""

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                RatsSheetHeader(
                    "Meine Gespräche",
                    leadingTitle: "Schließen",
                    leadingAction: { dismiss() }
                )
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 14) {
                        RatsModalIntro(
                            kicker: "Frag den Rat",
                            title: "Meine Gespräche",
                            message: "Öffne einen früheren Chat oder beginne mit einer neuen, unabhängigen Frage.",
                            symbol: .messagesSquare
                        )

                        Button {
                            onNew()
                            dismiss()
                        } label: {
                            RatsLabel("Neues Gespräch", .squarePen)
                                .font(RatsFont.body(15, weight: .semibold))
                                .frame(maxWidth: .infinity)
                        }
                        .buttonStyle(PrimaryButtonStyle())

                        if let currentConversationTitle {
                            MonoKicker("Gerade geöffnet")
                            Button { dismiss() } label: {
                                HStack(spacing: 12) {
                                    RatsIcon(.messagesSquare, size: 16)
                                        .foregroundStyle(.white)
                                        .frame(width: 38, height: 38)
                                        .background(RatsColor.primary)
                                        .clipShape(RoundedRectangle(cornerRadius: 11, style: .continuous))
                                    VStack(alignment: .leading, spacing: 4) {
                                        Text(currentConversationTitle)
                                            .font(RatsFont.body(15, weight: .semibold))
                                            .foregroundStyle(RatsColor.text)
                                            .lineLimit(2)
                                        Text(currentConversationMeta)
                                            .font(RatsFont.mono(10))
                                            .foregroundStyle(RatsColor.muted)
                                    }
                                    Spacer(minLength: 4)
                                    VStack(alignment: .trailing, spacing: 10) {
                                        Pill("Aktuell")
                                        RatsIcon(.check, size: 12)
                                            .foregroundStyle(RatsColor.primary)
                                    }
                                }
                            }
                            .buttonStyle(RatsPlainButtonStyle())
                            .padding(14)
                            .background(RatsColor.primary.opacity(0.06))
                            .overlay(RoundedRectangle(cornerRadius: 14).stroke(RatsColor.primary.opacity(0.28)))
                            .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
                        }

                    if isLoading {
                        RatsLoadingState(message: "Gespräche werden geladen …")
                    } else if historicalConversations.isEmpty && currentConversationTitle == nil && error == nil {
                        RatsEmptyState(
                            title: "Noch keine Gespräche",
                            message: "Sobald du dem Rat eine Frage stellst, kannst du die Unterhaltung hier erneut öffnen.",
                            symbol: .messagesSquare
                        )
                    } else {
                        if historicalConversations.count >= 8 {
                            HStack(spacing: 9) {
                                RatsIcon(.search, size: 16)
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
                        if !historicalConversations.isEmpty {
                            MonoKicker("Frühere Gespräche", trailing: "\(historicalConversations.count)")
                        }
                        if filteredConversations.isEmpty,
                           !search.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                            RatsEmptyState(
                                title: "Kein Treffer",
                                message: "Kein Gespräch passt zu „\(search.trimmingCharacters(in: .whitespacesAndNewlines))“.",
                                symbol: .textSearch
                            )
                        }
                        ForEach(filteredConversations) { conversation in
                            HStack(spacing: 10) {
                                Button { Task { await open(conversation.id) } } label: {
                                    HStack(spacing: 12) {
                                        RatsIcon(.messagesSquare, size: 16)
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
                                        if openingID == conversation.id {
                                            ProgressView().controlSize(.small).tint(RatsColor.primary)
                                        } else {
                                            RatsIcon(.chevronRight, size: 12)
                                                .foregroundStyle(RatsColor.muted)
                                        }
                                    }
                                }
                                .buttonStyle(RatsPlainButtonStyle())
                                Menu {
                                    Button {
                                        renameTitle = conversation.title
                                        renameTarget = conversation
                                    } label: { RatsLabel("Umbenennen", .pencil) }
                                    Button(role: .destructive) {
                                        remove(conversation.id)
                                    } label: { RatsLabel("Gespräch löschen", .trash2) }
                                } label: {
                                    RatsIcon(.ellipsis, size: 16)
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
        guard !term.isEmpty else { return historicalConversations }
        return historicalConversations.filter { $0.title.localizedCaseInsensitiveContains(term) }
    }

    private var historicalConversations: [ConversationSummary] {
        conversations.filter { $0.id != activeConversationID }
    }

    private var currentConversationTitle: String? {
        if let currentTitle = currentTitle?.trimmingCharacters(in: .whitespacesAndNewlines), !currentTitle.isEmpty {
            return currentTitle
        }
        return conversations.first(where: { $0.id == activeConversationID })?.title
    }

    private var currentConversationMeta: String {
        let count = max(
            currentTurnCount,
            conversations.first(where: { $0.id == activeConversationID })?.turnCount ?? 0
        )
        if activeConversationID == nil {
            return count > 0 ? "\(count) \(count == 1 ? "Frage" : "Fragen") · wird nach der Antwort gespeichert" : "Neuer Chat"
        }
        return "\(count) \(count == 1 ? "Frage" : "Fragen") · in deinem Konto gespeichert"
    }

    private func conversationMeta(_ conversation: ConversationSummary) -> String {
        let turns = "\(conversation.turnCount) \(conversation.turnCount == 1 ? "Frage" : "Fragen")"
        guard let date = conversationDateLabel(conversation.updatedAt) else { return turns }
        return "\(turns) · \(date)"
    }

    private func load() async {
        isLoading = true
        defer { isLoading = false }
        do {
            let response: JSONValue = try await model.api.get("/api/council/gespraeche")
            conversations = response.object?["conversations"]?.array?.compactMap {
                try? $0.decoded(ConversationSummary.self)
            } ?? []
            error = nil
        } catch { self.error = error.localizedDescription }
    }

    private func open(_ id: Int) async {
        openingID = id
        defer { openingID = nil }
        do {
            let payload: JSONValue = try await model.api.get("/api/council/gespraeche/\(id)")
            onOpen(id, payload)
            dismiss()
        } catch { self.error = error.localizedDescription }
    }

    private func remove(_ id: Int) {
        Task {
            do {
                try await model.api.sendVoid("/api/council/gespraeche/\(id)", method: .delete)
                conversations.removeAll { $0.id == id }
                if id == activeConversationID {
                    onDeletedActive()
                    dismiss()
                }
            } catch { self.error = error.localizedDescription }
        }
    }

    private func rename(_ conversation: ConversationSummary) async {
        struct Body: Codable, Sendable { let title: String }
        let clean = renameTitle.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !clean.isEmpty else { return }
        do {
            try await model.api.sendVoid(
                "/api/council/gespraeche/\(conversation.id)",
                method: .patch,
                body: Body(title: clean)
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

func conversationDateLabel(
    _ raw: String?,
    now: Date = .now,
    calendar: Calendar = .current
) -> String? {
    guard let raw else { return nil }
    let hasTimeZone = raw.range(
        of: #"(?:[zZ]|[+-]\d{2}:?\d{2})$"#,
        options: .regularExpression
    ) != nil
    let normalized = hasTimeZone ? raw : raw + "Z"
    let formatter = ISO8601DateFormatter()
    formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
    let parsed = formatter.date(from: normalized) ?? {
        formatter.formatOptions = [.withInternetDateTime]
        return formatter.date(from: normalized)
    }()
    guard let date = parsed else { return RatsDate.short(raw) }
    if calendar.isDate(date, inSameDayAs: now) { return "Heute" }
    if let yesterday = calendar.date(byAdding: .day, value: -1, to: now),
       calendar.isDate(date, inSameDayAs: yesterday) {
        return "Gestern"
    }
    return RatsDate.short(raw)
}
