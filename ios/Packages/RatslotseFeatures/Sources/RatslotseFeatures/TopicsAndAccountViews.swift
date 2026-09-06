import AuthenticationServices
import RatslotseAPI
import RatslotseDesign
import SwiftUI

struct TopicsView: View {
    let model: AppModel
    @State private var topics: [Topic] = []
    @State private var suggestions: [TopicSuggestion] = []
    @State private var addingSuggestions: Set<String> = []
    @State private var addedTopics = 0
    @State private var isPresentingEditor = false
    @State private var editing: Topic?
    @State private var error: String?

    var body: some View {
        ScrollView {
            LazyVStack(alignment: .leading, spacing: 16) {
                HStack(alignment: .top, spacing: 14) {
                    VStack(alignment: .leading, spacing: 5) {
                        Text("Meine Themen")
                            .font(RatsFont.title(29))
                        Text("Deine Suchaufträge an den Rat – neue Treffer landen direkt hier.")
                            .font(RatsFont.body(14))
                            .foregroundStyle(RatsColor.secondary)
                    }
                    Spacer(minLength: 4)
                    Button {
                        editing = nil
                        isPresentingEditor = true
                    } label: {
                        RatsLabel("Neu", .plus)
                    }
                    .buttonStyle(PrimaryButtonStyle())
                    .tint(RatsColor.signal)
                }

                // Vorschläge als schmale Chip-Zeile statt als Kachelfeld: Sie
                // sind ein Angebot, nicht der Inhalt der Seite (Tims Befund
                // 05.09.2026: „oben so groß"). Die Zahl am Chip ist die
                // Häufigkeit im letzten Jahr; der Satz dazu steht im
                // Accessibility-Label statt als Fußnote.
                if !suggestions.isEmpty {
                    VStack(alignment: .leading, spacing: 8) {
                        MonoKicker("Gerade aktuell im Rat", trailing: "Tipp übernimmt")
                        ScrollView(.horizontal, showsIndicators: false) {
                            HStack(spacing: 7) {
                                ForEach(suggestions) { suggestion in
                                    TopicSuggestionChip(
                                        suggestion: suggestion,
                                        isWorking: addingSuggestions.contains(suggestion.name),
                                        action: { add(suggestion) }
                                    )
                                }
                            }
                            .padding(.horizontal, 18)
                        }
                        .padding(.horizontal, -18)
                    }
                }

                if topics.isEmpty && error == nil {
                    VStack(spacing: 13) {
                        Lotti3DView(scene: .questions)
                            .frame(width: 154, height: 112)
                            .accessibilityHidden(true)
                        Text("Noch keine Themen").font(RatsFont.title(22))
                        Text("Lege ein Thema an. Ratslotse meldet dir neue passende Beschlüsse.")
                            .font(RatsFont.body(14))
                            .foregroundStyle(RatsColor.secondary)
                            .multilineTextAlignment(.center)
                        Button("Erstes Thema anlegen") {
                            editing = nil
                            isPresentingEditor = true
                        }
                        .buttonStyle(PrimaryButtonStyle())
                    }
                    .frame(maxWidth: .infinity)
                    .ratsCard()
                }

                LazyVGrid(columns: [GridItem(.adaptive(minimum: 330), spacing: 16)], alignment: .leading, spacing: 16) {
                    ForEach(topics) { topic in
                        TopicCard(
                            topic: topic,
                            open: { hit in open(hit, in: topic) },
                            edit: { editing = topic; isPresentingEditor = true },
                            remove: { remove(topic) }
                        )
                    }

                    Button {
                        editing = nil
                        isPresentingEditor = true
                    } label: {
                        RatsLabel("Neues Thema anlegen", .plus)
                            .font(RatsFont.body(14, weight: .semibold))
                            .foregroundStyle(RatsColor.primary)
                            .frame(maxWidth: .infinity, minHeight: 56)
                            .background(RatsColor.card.opacity(0.65))
                            .overlay(
                                RoundedRectangle(cornerRadius: RatsRadius.card)
                                    .stroke(RatsColor.primary.opacity(0.32), style: StrokeStyle(lineWidth: 1.5, dash: [7]))
                            )
                            .clipShape(RoundedRectangle(cornerRadius: RatsRadius.card))
                    }
                    .buttonStyle(RatsPlainButtonStyle())
                }

                if let error { ErrorCard(message: error) { Task { await load() } } }

                HStack(alignment: .top, spacing: 10) {
                    RatsIcon(.landmark, size: 12)
                        .foregroundStyle(RatsColor.primary)
                    Text("Ganze Gremien behältst du im Onboarding oder über die Benachrichtigungseinstellungen im Blick.")
                        .font(RatsFont.body(12))
                        .foregroundStyle(RatsColor.secondary)
                }
                .padding(14)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(RatsColor.primary.opacity(0.05))
                .clipShape(RoundedRectangle(cornerRadius: RatsRadius.card))
            }
            .frame(maxWidth: 980, alignment: .leading)
            .padding(.horizontal, 18)
            .padding(.vertical, 24)
        }
        .background(RatsColor.page)
        .navigationTitle("Meine Themen")
        .toolbarTitleDisplayMode(.inline)
        // Ein übernommener Vorschlag bestätigt sich in der Hand — wie das
        // System es bei einem Erfolg tut.
        .sensoryFeedback(.success, trigger: addedTopics)
        .refreshable { await load() }
        .task {
#if DEBUG
            if ProcessInfo.processInfo.environment["RATSLOTSE_DEBUG_TOPIC_SUGGESTIONS"] == "1" {
                suggestions = [
                    .init(name: "Untere Nadorster Straße", description: "Umbau und Verkehr an der Unteren Nadorster Straße", n: 14),
                    .init(name: "Stadion Maastrichter Straße", description: "Planung und Finanzierung des Stadionneubaus", n: 9),
                    .init(name: "Alte Fleiwa", description: "Entwicklung des früheren Fleiwa-Geländes", n: 7),
                    .init(name: "Quartier am Krusenbusch", description: "Bauleitplanung am Krusenbusch", n: 5),
                ]
                return
            }
            if ProcessInfo.processInfo.environment["RATSLOTSE_DEBUG_TOPICS_EMPTY"] == "1" { return }
#endif
            if topics.isEmpty { await load() }
        }
        .onAppear {
#if DEBUG
            if ProcessInfo.processInfo.environment["RATSLOTSE_DEBUG_TOPIC_EDITOR"] == "1" {
                editing = nil
                isPresentingEditor = true
            }
#endif
        }
        .sheet(isPresented: $isPresentingEditor) {
            TopicEditorView(model: model, topic: editing) {
                isPresentingEditor = false
                Task { await load() }
            }
            .ratsLargeSheet()
        }
    }

    private func load() async {
        do {
            async let topicsRequest: [Topic] = model.api.get("/api/topics")
            async let suggestionsRequest: TopicSuggestionsResponse? = try? await model.api.get("/api/topics/suggestions")
            topics = try await topicsRequest
            suggestions = await suggestionsRequest?.suggestions ?? []
            error = nil
            try? await model.api.sendVoid("/api/topics/overview-seen")
        } catch { self.error = error.localizedDescription }
    }

    private func add(_ suggestion: TopicSuggestion) {
        guard addingSuggestions.insert(suggestion.name).inserted else { return }
        struct Body: Codable, Sendable { let name: String; let description: String }
        Task {
            defer { addingSuggestions.remove(suggestion.name) }
            do {
                let topic: Topic = try await model.api.send(
                    "/api/topics",
                    body: Body(name: suggestion.name, description: suggestion.description)
                )
                topics.append(topic)
                suggestions.removeAll { $0.name == suggestion.name }
                addedTopics += 1
                await model.refreshBadges()
            } catch { self.error = error.localizedDescription }
        }
    }

    private func remove(_ topic: Topic) {
        Task {
            do {
                try await model.api.sendVoid("/api/topics/\(topic.id)", method: .delete)
                topics.removeAll { $0.id == topic.id }
            } catch { self.error = error.localizedDescription }
        }
    }

    private func open(_ hit: TopicHit, in topic: Topic) {
        model.navigation.append(.decision(id: hit.id))
        guard hit.isNew else { return }
        struct Body: Codable, Sendable { let decision_id: Int }
        Task {
            try? await model.api.sendVoid(
                "/api/topics/\(topic.id)/seen",
                body: Body(decision_id: hit.id)
            )
        }
    }
}

private struct TopicSuggestionsResponse: Decodable, Sendable {
    let suggestions: [TopicSuggestion]
}

private struct TopicSuggestion: Decodable, Sendable, Identifiable {
    var id: String { name }
    let name: String
    let description: String
    let n: Int
}

/// Ein Vorschlag als Chip: Plus, Name, Häufigkeit. Eine Zeile hoch, damit
/// die Angebote nicht über den eigenen Themen thronen.
private struct TopicSuggestionChip: View {
    let suggestion: TopicSuggestion
    let isWorking: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 6) {
                if isWorking {
                    ProgressView()
                        .controlSize(.mini)
                        .tint(RatsColor.primary)
                } else {
                    RatsIcon(.plus, size: 11)
                }
                Text(suggestion.name)
                    .font(RatsFont.body(12.5, weight: .semibold))
                    .lineLimit(1)
                Text("\(suggestion.n)×")
                    .font(RatsFont.mono(9, weight: .semibold))
                    .foregroundStyle(RatsColor.muted)
            }
            .foregroundStyle(RatsColor.primary)
            .padding(.horizontal, 11)
            .frame(height: 32)
            .background(RatsColor.card)
            .overlay(Capsule().stroke(RatsColor.primary.opacity(0.24)))
            .clipShape(Capsule())
        }
        .buttonStyle(RatsPlainButtonStyle())
        .disabled(isWorking)
        .accessibilityLabel("\(suggestion.name) als Thema anlegen, \(suggestion.n) Erwähnungen im letzten Jahr")
    }
}

/// Ein Thema als Tide-Widget in Boje-Orange — dieselbe Hülle wie „Neu zu
/// deinen Themen" auf der Startseite, damit ein Thema überall gleich
/// aussieht. Kopfleiste: Zeichen, Name, rechts „2 neue" und das Menü;
/// Körper: Beschreibung und die letzten Treffer.
private struct TopicCard: View {
    let topic: Topic
    let open: (TopicHit) -> Void
    let edit: () -> Void
    let remove: () -> Void

    var body: some View {
        RatsWidget(topic.name, accent: .buoy, glyph: .tag, trailing: {
            HStack(spacing: 6) {
                if topic.unreadCount > 0 {
                    Text(topic.unreadCount == 1 ? "1 neuer" : "\(topic.unreadCount) neue")
                        .font(RatsFont.body(10.5, weight: .semibold))
                        .foregroundStyle(RatsColor.signalInk)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 4)
                        .background(RatsColor.signal.opacity(0.10))
                        .clipShape(Capsule())
                        .fixedSize()
                }
                Menu {
                    Button(action: edit) { RatsLabel("Bearbeiten", .pencil) }
                    Button(role: .destructive, action: remove) { RatsLabel("Löschen", .trash2) }
                } label: {
                    RatsIcon(.ellipsis, size: 15)
                        .foregroundStyle(RatsColor.secondary)
                        .frame(width: 30, height: 30)
                        .contentShape(Rectangle())
                }
                .accessibilityLabel("\(topic.name) bearbeiten oder löschen")
            }
        }) {
            VStack(alignment: .leading, spacing: 12) {
                if !topic.description.isEmpty {
                    Text(topic.description)
                        .font(RatsFont.body(12.5))
                        .foregroundStyle(RatsColor.secondary)
                        .lineSpacing(2)
                }

                if !topic.recentHits.isEmpty {
                    VStack(alignment: .leading, spacing: 4) {
                        MonoKicker(
                            "Zuletzt gefunden",
                            trailing: "\(countLabel) · \(topic.hits6Months) in 6 Monaten"
                        )
                        VStack(spacing: 0) {
                            ForEach(Array(topic.recentHits.prefix(3).enumerated()), id: \.element.id) { index, hit in
                                Button { open(hit) } label: {
                                    HStack(alignment: .top, spacing: 9) {
                                        Circle()
                                            .fill(hit.isNew ? RatsColor.signal : RatsColor.muted.opacity(0.45))
                                            .frame(width: 7, height: 7)
                                            .padding(.top, 6)
                                        VStack(alignment: .leading, spacing: 3) {
                                            Text(hit.title)
                                                .font(RatsFont.body(13.5, weight: .semibold))
                                                .foregroundStyle(RatsColor.text)
                                                .lineLimit(2)
                                                .multilineTextAlignment(.leading)
                                            Text([RatsDate.short(hit.sessionDate), hit.committee.map(Committee.short)].compactMap { $0 }.joined(separator: " · "))
                                                .font(RatsFont.mono(9))
                                                .foregroundStyle(RatsColor.muted)
                                        }
                                        Spacer(minLength: 4)
                                        if let outcome = hit.outcome { OutcomeBadge(outcome) }
                                    }
                                    .padding(.vertical, 9)
                                    .contentShape(Rectangle())
                                }
                                .buttonStyle(RatsPlainButtonStyle())
                                if index < min(topic.recentHits.count, 3) - 1 {
                                    Divider().overlay(RatsColor.separator)
                                }
                            }
                        }
                    }
                } else {
                    Text(topic.matched ? "Noch kein passender Beschluss." : "Die passenden Beschlüsse werden gerade gezählt …")
                        .font(RatsFont.body(12))
                        .foregroundStyle(RatsColor.muted)
                }
            }
        }
    }

    private var countLabel: String {
        topic.matched ? "\(topic.decisionCount)\(topic.decisionCountCapped ? "+" : "") gesamt" : "wird gezählt"
    }
}

private struct TopicDescription: Codable, Sendable {
    let name: String
    let description: String
}

private struct TopicEditorView: View {
    let model: AppModel
    let topic: Topic?
    let completed: () -> Void
    @Environment(\.dismiss) private var dismiss
    @State private var name: String
    @State private var description: String
    @State private var isWorking = false
    @State private var error: String?

    init(model: AppModel, topic: Topic?, completed: @escaping () -> Void) {
        self.model = model
        self.topic = topic
        self.completed = completed
        _name = State(initialValue: topic?.name ?? "")
        _description = State(initialValue: topic?.description ?? "")
    }

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                RatsSheetHeader("Thema", leadingTitle: "Abbrechen", leadingAction: { dismiss() })
                ScrollView {
                    VStack(alignment: .leading, spacing: 18) {
                    RatsModalIntro(
                        kicker: "Themenradar",
                        title: topic == nil ? "Neues Thema" : "Thema bearbeiten",
                        message: "Beschreibe, was dich interessiert. Ratslotse hält danach passende Ratsentscheidungen für dich im Blick.",
                        symbol: .crosshair
                    )

                    RatsSectionPanel("Worum geht es?", symbol: .textSearch) {
                        RatsLabeledField(label: "Thema", hint: "kurz & eindeutig") {
                            TextField("z. B. Cäcilienbrücke", text: $name)
                                .textFieldStyle(.plain)
                        }
                        RatsLabeledField(label: "Was möchtest du verfolgen?") {
                            TextField("Beschreibe deinen Suchauftrag", text: $description, axis: .vertical)
                                .lineLimit(3...8)
                                .textFieldStyle(.plain)
                                .padding(.vertical, 10)
                        }
                    }

                    RatsSectionPanel(
                        "Lotti hilft beim Formulieren",
                        detail: "Der Vorschlag entsteht aus vorhandenen Beschlüssen und bleibt vor dem Speichern vollständig editierbar.",
                        symbol: .sparkles
                    ) {
                        Button { suggest() } label: {
                            RatsLabel(isWorking ? "Lotti schaut nach …" : "Beschreibung vorschlagen", .wandSparkles)
                                .frame(maxWidth: .infinity)
                        }
                        .buttonStyle(SecondaryButtonStyle())
                        .disabled(name.trimmingCharacters(in: .whitespaces).isEmpty || isWorking)
                        .opacity(name.trimmingCharacters(in: .whitespaces).isEmpty || isWorking ? 0.5 : 1)
                    }

                    if let error {
                        ErrorCard(message: error) { suggest() }
                    }

                    Button { save() } label: {
                        Text(isWorking ? "Wird gespeichert …" : "Thema speichern")
                            .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(PrimaryButtonStyle())
                    .disabled(name.isEmpty || description.isEmpty || isWorking)
                    .opacity(name.isEmpty || description.isEmpty || isWorking ? 0.5 : 1)
                    }
                    .frame(maxWidth: 620, alignment: .leading)
                    .padding(.horizontal, 18)
                    .padding(.vertical, 22)
                }
                .background(RatsColor.page)
            }
            .toolbar(.hidden, for: .navigationBar)
        }
    }

    private func suggest() {
        struct Body: Codable, Sendable { let name: String; let description: String }
        isWorking = true
        Task {
            defer { isWorking = false }
            do {
                let response: TopicDescription = try await model.api.send(
                    "/api/topics/describe", body: Body(name: name, description: description)
                )
                name = response.name
                description = response.description
            } catch { self.error = error.localizedDescription }
        }
    }

    private func save() {
        struct Body: Codable, Sendable { let name: String; let description: String }
        isWorking = true
        Task {
            defer { isWorking = false }
            do {
                let body = Body(name: name, description: description)
                let _: Topic = if let topic {
                    try await model.api.send("/api/topics/\(topic.id)", method: .put, body: body)
                } else {
                    try await model.api.send("/api/topics", body: body)
                }
                await model.refreshBadges()
                completed()
            } catch { self.error = error.localizedDescription }
        }
    }
}

struct AccountView: View {
    let model: AppModel
    let back: () -> Void
    @Environment(\.horizontalSizeClass) private var horizontalSizeClass
    @State private var notifications: NotificationSettings?
    @State private var prefs: [String: Bool] = [:]
    @State private var displayName = ""
    @State private var isSavingDisplayName = false
    @State private var displayNameSaved = false
    @State private var displayNameSuccessPulse = 0
    @State private var displayNameErrorPulse = 0
    @State private var isChangingPassword = false
    @State private var isDeletingAccount = false
    @State private var error: String?

    var body: some View {
        ScrollViewReader { proxy in
            VStack(spacing: 0) {
                if horizontalSizeClass == .compact {
                    accountHeader
                }
                ScrollView {
                LazyVStack(alignment: .leading, spacing: 16) {
                if let user = model.user {
                    HStack(alignment: .center, spacing: 14) {
                        LottiProfileAvatar(accountID: user.id, size: 58)
                        VStack(alignment: .leading, spacing: 4) {
                            MonoKicker("Dein Ratslotse")
                            Text(user.displayName ?? "Moin!")
                                .font(RatsFont.title(28))
                            Text(user.email)
                                .font(RatsFont.body(12))
                                .foregroundStyle(RatsColor.secondary)
                        }
                        Spacer(minLength: 0)
                    }
                    .padding(.vertical, 4)

                    RatsSectionPanel("Profil", detail: "So spricht Ratslotse dich an.", symbol: .contact) {
                        RatsLabeledField(label: "Anzeigename") {
                            TextField("Dein Name", text: $displayName)
                                .textContentType(.name)
                                .textFieldStyle(.plain)
                        }
                        Button { saveDisplayName() } label: {
                            HStack(spacing: 9) {
                                if isSavingDisplayName {
                                    ProgressView()
                                        .controlSize(.small)
                                        .tint(RatsColor.primary)
                                    Text("Wird gespeichert …")
                                } else if displayNameSaved {
                                    RatsIcon(.circleCheckBig, size: 16)
                                        .symbolEffect(.bounce, value: displayNameSuccessPulse)
                                    Text("Name gespeichert")
                                } else {
                                    RatsIcon(.check, size: 16)
                                    Text("Anzeigename speichern")
                                }
                            }
                            .font(RatsFont.body(15, weight: .semibold))
                            .foregroundStyle(displayNameSaved ? RatsColor.success : RatsColor.primary)
                            .frame(maxWidth: .infinity, minHeight: 42)
                            .background(displayNameSaved ? RatsColor.successTint : RatsColor.card)
                            .overlay(
                                RoundedRectangle(cornerRadius: RatsRadius.button, style: .continuous)
                                    .stroke(displayNameSaved ? RatsColor.success.opacity(0.36) : RatsColor.border)
                            )
                            .clipShape(RoundedRectangle(cornerRadius: RatsRadius.button, style: .continuous))
                            .contentTransition(.opacity)
                        }
                        .buttonStyle(RatsPlainButtonStyle())
                        .disabled(isSavingDisplayName)
                        .accessibilityLabel(displayNameSaved ? "Anzeigename wurde gespeichert" : "Anzeigename speichern")
                        .animation(.spring(response: 0.36, dampingFraction: 0.76), value: displayNameSaved)
                    }

                    BadgeCollectionCard(model: model)

                    RatsSectionPanel(
                        "Benachrichtigungen",
                        detail: "Du bestimmst, wo und zu welchen Themen Ratslotse sich meldet.",
                        symbol: .bellDot
                    ) {
                        RatsSettingsRow("Zustellweg", detail: "E-Mail, Push oder beides", symbol: .send) {
                            Menu {
                                Button("E-Mail") { deliveryBinding(user: user).wrappedValue = "email" }
                                Button("Push") { deliveryBinding(user: user).wrappedValue = "push" }
                                Button("Beides") { deliveryBinding(user: user).wrappedValue = "both" }
                                Button("Aus") { deliveryBinding(user: user).wrappedValue = "off" }
                            } label: {
                                HStack(spacing: 5) {
                                    Text(deliveryLabel(model.user?.deliveryChannel ?? user.deliveryChannel))
                                    Text("⌄").font(RatsFont.body(13, weight: .bold))
                                }
                                .font(RatsFont.body(12, weight: .semibold))
                                .foregroundStyle(RatsColor.primary)
                                .padding(.horizontal, 10)
                                .frame(minHeight: 32)
                                .background(RatsColor.primary.opacity(0.08))
                                .overlay(Capsule().stroke(RatsColor.primary.opacity(0.18)))
                                .clipShape(Capsule())
                            }
                        }

                        if notifications != nil { Divider().overlay(RatsColor.separator) }
                        if let notifications {
                        ForEach(notifications.kinds) { kind in
                                RatsSettingsRow(kind.label, detail: kind.hint, symbol: notificationSymbol(kind.key)) {
                                    Toggle("", isOn: Binding(
                                        get: { prefs[kind.key, default: kind.enabled] },
                                        set: { prefs[kind.key] = $0; saveNotifications() }
                                    ))
                                    .labelsHidden()
                                    .tint(RatsColor.primary)
                                    .accessibilityLabel(kind.label)
                                }
                                .disabled(kind.parent.map { prefs[$0] == false } ?? false)
                                if kind.id != notifications.kinds.last?.id {
                                    Divider().overlay(RatsColor.separator)
                                }
                            }
                            Text("Höchstens \(notifications.limits.perDay) Hinweise pro Tag; nachts bleibt Ratslotse still.")
                                .font(RatsFont.body(11))
                                .foregroundStyle(RatsColor.muted)
                        } else if error == nil {
                            HStack(spacing: 10) {
                                ProgressView().tint(RatsColor.primary)
                                Text("Einstellungen werden geladen …")
                                    .font(RatsFont.body(12))
                                    .foregroundStyle(RatsColor.secondary)
                            }
                        }
                    }

                    RatsSectionPanel("Push ausprobieren", detail: "Prüfe direkt, ob Hinweise auf diesem Gerät ankommen.", symbol: .smartphoneNfc) {
                        Button { requestPush() } label: {
                            RatsSettingsRow("Push-Mitteilungen erlauben", symbol: .bellDot) {
                                RatsIcon(.chevronRight, size: 16).foregroundStyle(RatsColor.muted)
                            }
                        }
                        .buttonStyle(RatsPlainButtonStyle())
                        Divider().overlay(RatsColor.separator)
                        Button {
                            Task {
                                do { let _: JSONValue = try await model.api.sendWithoutBody("/api/account/test-notification") }
                                catch { self.error = error.localizedDescription }
                            }
                        } label: {
                            RatsSettingsRow("Test-Benachrichtigung senden", symbol: .send) {
                                RatsIcon(.chevronRight, size: 16).foregroundStyle(RatsColor.muted)
                            }
                        }
                        .buttonStyle(RatsPlainButtonStyle())
                    }

                    ConversationSettingsCard(model: model)
                        .id("conversation-settings")

                    AppearanceSettingsCard(model: model)

                    RatsSectionPanel("Sicherheit", symbol: .shieldCheck) {
                        if user.hasPassword {
                            Button { isChangingPassword = true } label: {
                                RatsSettingsRow("Passwort ändern", symbol: .key) {
                                    RatsIcon(.chevronRight, size: 16).foregroundStyle(RatsColor.muted)
                                }
                            }
                            .buttonStyle(RatsPlainButtonStyle())
                        }
                        if user.hasPassword && user.appleLinked { Divider().overlay(RatsColor.separator) }
                        if user.appleLinked {
                            RatsSettingsRow("Mit Apple verknüpft", detail: "Schnelle und sichere Anmeldung", symbol: .appleLogo) {
                                RatsIcon(.circleCheckBig, size: 16).foregroundStyle(RatsColor.success)
                            }
                        }
                        if !user.hasPassword {
                            if user.appleLinked { Divider().overlay(RatsColor.separator) }
                            Button {
                                Task {
                                    do {
                                        try await model.forgotPassword(email: user.email)
                                        model.alertMessage = "Der Link zum Einrichten eines Passworts ist unterwegs."
                                    } catch {
                                        self.error = error.localizedDescription
                                    }
                                }
                            } label: {
                                RatsSettingsRow(
                                    "Passwort per E-Mail einrichten",
                                    detail: "Ergänzt die Apple-Anmeldung um ein eigenes Passwort",
                                    symbol: .mailWarning
                                ) {
                                    RatsIcon(.chevronRight, size: 16).foregroundStyle(RatsColor.muted)
                                }
                            }
                            .buttonStyle(RatsPlainButtonStyle())
                        }
                    }

                    RatsSectionPanel("Hilfe & Rechtliches", symbol: .lifeBuoy) {
                        accountButton("Einrichtung mit Lotti erneut ansehen", symbol: .sparkles) { model.restartOnboarding() }
                        Divider().overlay(RatsColor.separator)
                        accountLink("Hilfe und Kontakt", symbol: .circleHelp, url: "https://ratslotse.de/hilfe")
                        Divider().overlay(RatsColor.separator)
                        accountLink("Datenschutz", symbol: .hand, url: "https://ratslotse.de/datenschutz")
                        Divider().overlay(RatsColor.separator)
                        accountLink("Impressum", symbol: .fileText, url: "https://ratslotse.de/impressum")
                        if user.isAdmin {
                            Divider().overlay(RatsColor.separator)
                            accountButton("Admin-Bereich", symbol: .wrench) {
                                model.navigation.append(.admin)
                            }
                        }
                    }

                    RatsSectionPanel("Sitzung beenden", detail: "Deine gespeicherten Inhalte bleiben erhalten.", symbol: .doorOpen) {
                        Button { Task { await model.logout() } } label: {
                            Text("Abmelden").frame(maxWidth: .infinity)
                        }
                        .buttonStyle(SecondaryButtonStyle())
                        Button(role: .destructive) { isDeletingAccount = true } label: {
                            RatsLabel("Konto löschen", .trash2)
                                .font(RatsFont.body(13, weight: .semibold))
                                .frame(maxWidth: .infinity, minHeight: 40)
                        }
                    }
                    .padding(.bottom, horizontalSizeClass == .compact ? 148 : 0)
                    .id("session-end")
                }
                if let error { ErrorCard(message: error) { Task { await load() } } }
            }
                .frame(maxWidth: 920, alignment: .leading)
                .padding(.horizontal, 18)
                .padding(.top, 22)
                .padding(.bottom, 22)
                }
            }
            .background(RatsColor.page)
            .toolbar(.hidden, for: .navigationBar)
            .task {
                await load()
#if DEBUG
                if ProcessInfo.processInfo.environment["RATSLOTSE_DEBUG_ACCOUNT_ANCHOR"] == "preferences" {
                    try? await Task.sleep(for: .milliseconds(250))
                    proxy.scrollTo("conversation-settings", anchor: .top)
                } else if ProcessInfo.processInfo.environment["RATSLOTSE_DEBUG_ACCOUNT_ANCHOR"] == "session-end" {
                    try? await Task.sleep(for: .milliseconds(250))
                    proxy.scrollTo("session-end", anchor: .bottom)
                }
#endif
            }
            .onAppear {
#if DEBUG
                switch ProcessInfo.processInfo.environment["RATSLOTSE_DEBUG_ACCOUNT_SHEET"] {
                case "password": isChangingPassword = true
                case "delete": isDeletingAccount = true
                default: break
                }
#endif
            }
            .sheet(isPresented: $isChangingPassword) {
                ChangePasswordView(model: model)
                    .ratsLargeSheet()
            }
            .sheet(isPresented: $isDeletingAccount) {
                DeleteAccountView(model: model)
                    .ratsLargeSheet()
            }
            .sensoryFeedback(.success, trigger: displayNameSuccessPulse)
            .sensoryFeedback(.error, trigger: displayNameErrorPulse)
        }
    }

    private var accountHeader: some View {
        HStack {
            Button(action: back) {
                RatsGlyphView(glyph: .back, color: RatsColor.bodyText)
                    .frame(width: 20, height: 20)
                    .frame(width: 42, height: 42)
                    .background(RatsColor.card)
                    .overlay(Circle().stroke(RatsColor.border))
                    .clipShape(Circle())
            }
            .buttonStyle(RatsPlainButtonStyle())
            .accessibilityLabel("Zurück zu Mehr")

            Spacer()
            Text("Konto")
                .font(RatsFont.title(18))
                .foregroundStyle(RatsColor.text)
            Spacer()
            Color.clear.frame(width: 42, height: 42)
        }
        .padding(.horizontal, 18)
        .padding(.vertical, 10)
        .background(RatsColor.page)
        .overlay(alignment: .bottom) {
            Divider().overlay(RatsColor.separator)
        }
    }

    private func load() async {
        displayName = model.user?.displayName ?? ""
        do {
            notifications = try await model.api.get("/api/account/notifications")
            prefs = Dictionary(uniqueKeysWithValues: notifications?.kinds.map { ($0.key, $0.enabled) } ?? [])
        } catch { self.error = error.localizedDescription }
    }

    private func deliveryBinding(user: User) -> Binding<String> {
        Binding(get: { model.user?.deliveryChannel ?? user.deliveryChannel }, set: { channel in
            Task {
                struct Body: Codable, Sendable { let delivery_channel: String }
                do {
                    if channel == "push" || channel == "both" {
                        guard await model.requestPushPermission() else { return }
                    }
                    let updated: User = try await model.api.send(
                        "/api/account/delivery", method: .put, body: Body(delivery_channel: channel)
                    )
                    try await model.adopt(user: updated)
                } catch { self.error = error.localizedDescription }
            }
        })
    }

    private func deliveryLabel(_ channel: String) -> String {
        switch channel {
        case "push": "Push"
        case "both": "Beides"
        case "off": "Aus"
        default: "E-Mail"
        }
    }

    private func saveDisplayName() {
        struct Body: Codable, Sendable { let display_name: String? }
        guard !isSavingDisplayName else { return }
        isSavingDisplayName = true
        withAnimation(.easeOut(duration: 0.16)) { displayNameSaved = false }
        Task {
            do {
                let _: JSONValue = try await model.api.send(
                    "/api/account/display-name",
                    body: Body(display_name: displayName.trimmingCharacters(in: .whitespaces).isEmpty ? nil : displayName)
                )
                await model.refreshAccount()
                isSavingDisplayName = false
                withAnimation(.spring(response: 0.36, dampingFraction: 0.74)) {
                    displayNameSaved = true
                    displayNameSuccessPulse += 1
                }
                try? await Task.sleep(for: .seconds(2.4))
                withAnimation(.easeOut(duration: 0.22)) { displayNameSaved = false }
            } catch {
                isSavingDisplayName = false
                displayNameErrorPulse += 1
                self.error = error.localizedDescription
            }
        }
    }

    private func saveNotifications() {
        struct Body: Codable, Sendable { let prefs: [String: Bool] }
        Task {
            do {
                notifications = try await model.api.send(
                    "/api/account/notifications", method: .put, body: Body(prefs: prefs)
                )
            } catch { self.error = error.localizedDescription }
        }
    }

    private func requestPush() {
        Task {
            let granted = await model.requestPushPermission()
            if !granted { error = "Push-Mitteilungen sind nicht erlaubt. Öffne die Systemeinstellungen, um sie einzuschalten." }
        }
    }

    private func notificationSymbol(_ key: String) -> RatsGlyph {
        if key.contains("topic") || key.contains("thema") { return .crosshair }
        if key.contains("session") || key.contains("sitzung") { return .calendar }
        if key.contains("follow") || key.contains("vorlage") { return .gitBranch }
        return .bell
    }

    private func accountButton(_ title: String, symbol: RatsGlyph, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            RatsSettingsRow(title, symbol: symbol) {
                RatsIcon(.chevronRight, size: 16).foregroundStyle(RatsColor.muted)
            }
        }
        .buttonStyle(RatsPlainButtonStyle())
    }

    private func accountLink(_ title: String, symbol: RatsGlyph, url: String) -> some View {
        Link(destination: URL(string: url)!) {
            RatsSettingsRow(title, symbol: symbol) {
                RatsIcon(.arrowUpRight, size: 16).foregroundStyle(RatsColor.muted)
            }
        }
        .buttonStyle(RatsPlainButtonStyle())
    }
}

private struct ChangePasswordView: View {
    let model: AppModel
    @Environment(\.dismiss) private var dismiss
    @State private var current = ""
    @State private var new = ""
    @State private var repeated = ""
    @State private var error: String?

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                RatsSheetHeader("Passwort", leadingTitle: "Abbrechen", leadingAction: { dismiss() })
                ScrollView {
                    VStack(alignment: .leading, spacing: 18) {
                    RatsModalIntro(
                        kicker: "Sicherheit",
                        title: "Passwort ändern",
                        message: "Ein gutes Passwort ist einzigartig und mindestens acht Zeichen lang.",
                        symbol: .key
                    )
                    RatsSectionPanel("Deine Zugangsdaten", symbol: .lock) {
                        RatsLabeledField(label: "Aktuelles Passwort") {
                            SecureField("Bisheriges Passwort", text: $current)
                                .textContentType(.password)
                                .textFieldStyle(.plain)
                        }
                        RatsLabeledField(label: "Neues Passwort", hint: "mindestens 8 Zeichen") {
                            SecureField("Neues Passwort", text: $new)
                                .textContentType(.newPassword)
                                .textFieldStyle(.plain)
                        }
                        RatsLabeledField(label: "Wiederholen") {
                            SecureField("Noch einmal eingeben", text: $repeated)
                                .textContentType(.newPassword)
                                .textFieldStyle(.plain)
                        }
                    }
                    if let error { ErrorCard(message: error) { change() } }
                    Button { change() } label: {
                        Text("Neues Passwort speichern").frame(maxWidth: .infinity)
                    }
                    .buttonStyle(PrimaryButtonStyle())
                    .disabled(new.count < 8 || new != repeated || current.isEmpty)
                    .opacity(new.count < 8 || new != repeated || current.isEmpty ? 0.5 : 1)
                    }
                    .frame(maxWidth: 560, alignment: .leading)
                    .padding(18)
                }
                .background(RatsColor.page)
            }
            .toolbar(.hidden, for: .navigationBar)
        }
    }

    private func change() {
        struct Body: Codable, Sendable { let current_password: String; let new_password: String }
        Task {
            do {
                let user: User = try await model.api.send(
                    "/api/account/change-password",
                    body: Body(current_password: current, new_password: new)
                )
                try await model.adopt(user: user)
                dismiss()
            } catch { self.error = error.localizedDescription }
        }
    }
}

private struct DeleteAccountView: View {
    let model: AppModel
    @Environment(\.dismiss) private var dismiss
    @State private var password = ""
    @State private var appleToken = ""
    @State private var appleAuthorizationCode = ""
    @State private var confirmation = ""
    @State private var error: String?

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                RatsSheetHeader("Konto löschen", leadingTitle: "Abbrechen", leadingAction: { dismiss() })
                ScrollView {
                    VStack(alignment: .leading, spacing: 18) {
                    RatsModalIntro(
                        kicker: "Achtung",
                        title: "Konto löschen",
                        message: "Themen, Merkliste, Gespräche und Geräte werden endgültig gelöscht. Dieser Schritt lässt sich nicht rückgängig machen.",
                        symbol: .triangleAlert
                    )
                    RatsSectionPanel("Identität bestätigen", symbol: .userCog) {
                        if model.user?.appleLinked != true {
                            RatsLabeledField(label: "Aktuelles Passwort") {
                                SecureField("Passwort", text: $password)
                                    .textContentType(.password)
                                    .textFieldStyle(.plain)
                            }
                        } else {
                            SignInWithAppleButton(.continue) { request in request.requestedScopes = [] } onCompletion: { result in
                                if case .success(let auth) = result,
                                   let credential = auth.credential as? ASAuthorizationAppleIDCredential,
                                   let data = credential.identityToken,
                                   let token = String(data: data, encoding: .utf8) {
                                    appleToken = token
                                    if let codeData = credential.authorizationCode,
                                       let code = String(data: codeData, encoding: .utf8) {
                                        appleAuthorizationCode = code
                                    }
                                }
                            }
                            .frame(height: 46)
                            .clipShape(RoundedRectangle(cornerRadius: RatsRadius.button))
                        }
                    }

                    RatsSectionPanel("Letzte Bestätigung", detail: "Tippe LÖSCHEN in das Feld.", symbol: .trash2) {
                        RatsLabeledField(label: "Bestätigungswort") {
                            TextField("LÖSCHEN", text: $confirmation)
                                .textInputAutocapitalization(.characters)
                                .textFieldStyle(.plain)
                        }
                    }
                    if let error { ErrorCard(message: error) { remove() } }
                    Button(role: .destructive) { remove() } label: {
                        RatsLabel("Konto endgültig löschen", .trash2)
                            .font(RatsFont.body(15, weight: .semibold))
                            .foregroundStyle(Color.white)
                            .frame(maxWidth: .infinity, minHeight: 46)
                            .background(RatsColor.danger)
                            .clipShape(RoundedRectangle(cornerRadius: RatsRadius.button, style: .continuous))
                    }
                    .disabled(!canDelete)
                    .opacity(canDelete ? 1 : 0.5)
                    }
                    .frame(maxWidth: 560, alignment: .leading)
                    .padding(18)
                }
                .background(RatsColor.page)
            }
            .toolbar(.hidden, for: .navigationBar)
        }
    }

    private var canDelete: Bool {
        guard confirmation == "LÖSCHEN" else { return false }
        if model.user?.appleLinked == true {
            return !appleToken.isEmpty && !appleAuthorizationCode.isEmpty
        }
        return !password.isEmpty
    }

    private func remove() {
        struct Body: Codable, Sendable {
            let current_password: String
            let apple_identity_token: String
            let apple_authorization_code: String
        }
        Task {
            do {
                try await model.api.sendVoid(
                    "/api/account", method: .delete,
                    body: Body(
                        current_password: password,
                        apple_identity_token: appleToken,
                        apple_authorization_code: appleAuthorizationCode
                    )
                )
                await model.logout()
                dismiss()
            } catch { self.error = error.localizedDescription }
        }
    }
}
