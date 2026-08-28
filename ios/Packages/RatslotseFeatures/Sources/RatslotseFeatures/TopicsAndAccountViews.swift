import AuthenticationServices
import RatslotseAPI
import RatslotseDesign
import SwiftUI

struct TopicsView: View {
    let model: AppModel
    @State private var topics: [Topic] = []
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
                        Label("Neu", systemImage: "plus")
                    }
                    .buttonStyle(PrimaryButtonStyle())
                    .tint(RatsColor.signal)
                }

                if topics.isEmpty && error == nil {
                    VStack(spacing: 13) {
                        LottiMascot(pose: .wave)
                            .frame(width: 92, height: 92)
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
                    Label("Neues Thema anlegen", systemImage: "plus")
                        .font(RatsFont.body(14, weight: .semibold))
                        .foregroundStyle(RatsColor.primary)
                        .frame(maxWidth: .infinity, minHeight: 96)
                        .background(RatsColor.card.opacity(0.65))
                        .overlay(
                            RoundedRectangle(cornerRadius: RatsRadius.card)
                                .stroke(RatsColor.primary.opacity(0.32), style: StrokeStyle(lineWidth: 1.5, dash: [7]))
                        )
                        .clipShape(RoundedRectangle(cornerRadius: RatsRadius.card))
                }
                .buttonStyle(.plain)

                if let error { ErrorCard(message: error) { Task { await load() } } }

                HStack(alignment: .top, spacing: 10) {
                    Image(systemName: "building.columns")
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
            .frame(maxWidth: 760, alignment: .leading)
            .padding(.horizontal, 18)
            .padding(.vertical, 24)
        }
        .background(RatsColor.page)
        .navigationTitle("Meine Themen")
        .toolbarTitleDisplayMode(.inline)
        .refreshable { await load() }
        .task { if topics.isEmpty { await load() } }
        .sheet(isPresented: $isPresentingEditor) {
            TopicEditorView(model: model, topic: editing) {
                isPresentingEditor = false
                Task { await load() }
            }
        }
    }

    private func load() async {
        do {
            topics = try await model.api.get("/api/topics")
            error = nil
            try? await model.api.sendVoid("/api/topics/uebersicht-gesehen")
        } catch { self.error = error.localizedDescription }
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

private struct TopicCard: View {
    let topic: Topic
    let open: (TopicHit) -> Void
    let edit: () -> Void
    let remove: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 13) {
            HStack(alignment: .firstTextBaseline, spacing: 8) {
                Text(topic.name).font(RatsFont.title(20))
                if topic.unreadCount > 0 {
                    Text(topic.unreadCount == 1 ? "1 neuer" : "\(topic.unreadCount) neue")
                        .font(RatsFont.body(11, weight: .semibold))
                        .foregroundStyle(RatsColor.signal)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 4)
                        .background(RatsColor.signal.opacity(0.08))
                        .clipShape(Capsule())
                }
                Spacer(minLength: 0)
                Menu {
                    Button("Bearbeiten", systemImage: "pencil", action: edit)
                    Button("Löschen", systemImage: "trash", role: .destructive, action: remove)
                } label: {
                    Image(systemName: "ellipsis")
                        .foregroundStyle(RatsColor.secondary)
                        .frame(width: 32, height: 32)
                }
                .accessibilityLabel("\(topic.name) bearbeiten oder löschen")
            }

            Text(topic.description)
                .font(RatsFont.body(13))
                .foregroundStyle(RatsColor.secondary)

            if !topic.recentHits.isEmpty {
                MonoKicker(
                    "Zuletzt gefunden",
                    trailing: "\(countLabel) · \(topic.hits30Days) in 30 Tagen"
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
                                        .font(RatsFont.body(14, weight: .semibold))
                                        .foregroundStyle(RatsColor.text)
                                        .lineLimit(2)
                                        .multilineTextAlignment(.leading)
                                    Text([RatsDate.short(hit.sessionDate), hit.committee].compactMap { $0 }.joined(separator: " · "))
                                        .font(RatsFont.mono(9))
                                        .foregroundStyle(RatsColor.muted)
                                }
                                Spacer(minLength: 4)
                                if let outcome = hit.outcome { OutcomeBadge(outcome) }
                            }
                            .padding(.vertical, 10)
                        }
                        .buttonStyle(.plain)
                        if index < min(topic.recentHits.count, 3) - 1 {
                            Divider().overlay(RatsColor.separator)
                        }
                    }
                }
            } else {
                Text(topic.matched ? "Noch kein passender Beschluss." : "Die passenden Beschlüsse werden gerade gezählt …")
                    .font(RatsFont.body(12))
                    .foregroundStyle(RatsColor.muted)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .ratsCard()
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
            Form {
                Section("Worum geht es?") {
                    TextField("z. B. Cäcilienbrücke", text: $name)
                    TextField("Was daran möchtest du verfolgen?", text: $description, axis: .vertical)
                        .lineLimit(3...8)
                }
                Section {
                    Button("Beschreibung aus Ratsdaten vorschlagen") { suggest() }
                        .disabled(name.trimmingCharacters(in: .whitespaces).isEmpty || isWorking)
                } footer: {
                    Text("Der Vorschlag wird aus vorhandenen Beschlüssen formuliert. Du kannst ihn vor dem Speichern ändern.")
                }
                if let error { Section { Text(error).foregroundStyle(RatsColor.danger) } }
            }
            .navigationTitle(topic == nil ? "Neues Thema" : "Thema bearbeiten")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Abbrechen") { dismiss() } }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Speichern") { save() }
                        .disabled(name.isEmpty || description.isEmpty || isWorking)
                }
            }
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
                completed()
            } catch { self.error = error.localizedDescription }
        }
    }
}

struct AccountView: View {
    let model: AppModel
    @State private var notifications: NotificationSettings?
    @State private var prefs: [String: Bool] = [:]
    @State private var displayName = ""
    @State private var isChangingPassword = false
    @State private var isDeletingAccount = false
    @State private var error: String?

    var body: some View {
        VStack(spacing: 0) {
            HStack {
                VStack(alignment: .leading, spacing: 3) {
                    Text("Mein Konto")
                        .font(RatsFont.title(28))
                    if let email = model.user?.email {
                        Text(email)
                            .font(RatsFont.body(12))
                            .foregroundStyle(RatsColor.secondary)
                    }
                }
                Spacer()
            }
            .padding(.horizontal, 18)
            .padding(.top, 18)
            .padding(.bottom, 7)

            Form {
                if let user = model.user {
                Section {
                    HStack(spacing: 12) {
                        Image(systemName: "person.crop.circle.fill")
                            .font(.system(size: 42)).foregroundStyle(RatsColor.primary)
                        VStack(alignment: .leading, spacing: 3) {
                            Text(user.displayName ?? "Dein Konto").font(RatsFont.body(17, weight: .semibold))
                            Text(user.email).font(RatsFont.body(12)).foregroundStyle(RatsColor.secondary)
                        }
                    }
                    TextField("Anzeigename", text: $displayName)
                    Button("Anzeigename speichern") { saveDisplayName() }
                }

                Section("Zustellweg") {
                    Picker("Benachrichtigungen", selection: deliveryBinding(user: user)) {
                        Text("E-Mail").tag("email")
                        Text("Push").tag("push")
                        Text("E-Mail und Push").tag("both")
                        Text("Aus").tag("off")
                    }
                }

                if let notifications {
                    Section {
                        ForEach(notifications.kinds) { kind in
                            Toggle(isOn: Binding(
                                get: { prefs[kind.key, default: kind.enabled] },
                                set: { prefs[kind.key] = $0; saveNotifications() }
                            )) {
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(kind.label)
                                    Text(kind.hint).font(RatsFont.body(11)).foregroundStyle(RatsColor.secondary)
                                }
                            }
                            .disabled(kind.parent.map { prefs[$0] == false } ?? false)
                        }
                    } header: {
                        Text("Wozu du Hinweise bekommst")
                    } footer: {
                        Text("Höchstens \(notifications.limits.perDay) Hinweise pro Tag; nachts bleibt Ratslotse still.")
                    }
                }

                Section("Push testen") {
                    Button("Push-Mitteilungen erlauben") { requestPush() }
                    Button("Test-Benachrichtigung senden") {
                        Task {
                            do { let _: JSONValue = try await model.api.sendWithoutBody("/api/account/test-notification") }
                            catch { self.error = error.localizedDescription }
                        }
                    }
                }

                Section("Sicherheit") {
                    if user.hasPassword { Button("Passwort ändern") { isChangingPassword = true } }
                    if user.appleLinked { Label("Mit Apple verknüpft", systemImage: "apple.logo") }
                }

                Section("Hilfe & Rechtliches") {
                    Button("Einrichtung mit Lotti erneut ansehen") { model.restartOnboarding() }
                    Link("Hilfe und Kontakt", destination: URL(string: "https://ratslotse.de/hilfe")!)
                    Link("Datenschutz", destination: URL(string: "https://ratslotse.de/datenschutz")!)
                    Link("Impressum", destination: URL(string: "https://ratslotse.de/impressum")!)
                    if user.isAdmin { Link("Admin-Bereich im Web", destination: URL(string: "https://ratslotse.de/admin")!) }
                }

                Section {
                    Button("Abmelden", role: .destructive) { Task { await model.logout() } }
                    Button("Konto löschen", role: .destructive) { isDeletingAccount = true }
                }
                }
                if let error { Section { Text(error).foregroundStyle(RatsColor.danger) } }
            }
            .scrollContentBackground(.hidden)
        }
        .background(RatsColor.page)
        .navigationTitle("Konto")
        .toolbarTitleDisplayMode(.inline)
        .task { await load() }
        .sheet(isPresented: $isChangingPassword) { ChangePasswordView(model: model) }
        .sheet(isPresented: $isDeletingAccount) { DeleteAccountView(model: model) }
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

    private func saveDisplayName() {
        struct Body: Codable, Sendable { let display_name: String? }
        Task {
            do {
                let _: JSONValue = try await model.api.send(
                    "/api/account/display-name",
                    body: Body(display_name: displayName.trimmingCharacters(in: .whitespaces).isEmpty ? nil : displayName)
                )
                await model.refreshAccount()
            } catch { self.error = error.localizedDescription }
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
            Form {
                SecureField("Aktuelles Passwort", text: $current).textContentType(.password)
                SecureField("Neues Passwort", text: $new).textContentType(.newPassword)
                SecureField("Neues Passwort wiederholen", text: $repeated).textContentType(.newPassword)
                if let error { Text(error).foregroundStyle(RatsColor.danger) }
            }
            .navigationTitle("Passwort ändern")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Abbrechen") { dismiss() } }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Speichern") { change() }.disabled(new.count < 8 || new != repeated)
                }
            }
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
    @State private var confirmation = ""
    @State private var error: String?

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    Text("Dabei werden Themen, Merkliste, Gespräche und Geräte endgültig gelöscht.")
                }
                if model.user?.hasPassword == true {
                    Section("Bestätigung") { SecureField("Aktuelles Passwort", text: $password) }
                } else {
                    Section("Bestätigung") {
                        SignInWithAppleButton(.continue) { request in request.requestedScopes = [] } onCompletion: { result in
                            if case .success(let auth) = result,
                               let credential = auth.credential as? ASAuthorizationAppleIDCredential,
                               let data = credential.identityToken,
                               let token = String(data: data, encoding: .utf8) { appleToken = token }
                        }
                        .frame(height: 46)
                    }
                }
                Section {
                    TextField("LÖSCHEN eingeben", text: $confirmation)
                        .textInputAutocapitalization(.characters)
                    if let error { Text(error).foregroundStyle(RatsColor.danger) }
                }
            }
            .navigationTitle("Konto löschen")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Abbrechen") { dismiss() } }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Endgültig löschen", role: .destructive) { remove() }
                        .disabled(confirmation != "LÖSCHEN" || (password.isEmpty && appleToken.isEmpty))
                }
            }
        }
    }

    private func remove() {
        struct Body: Codable, Sendable { let current_password: String; let apple_identity_token: String }
        Task {
            do {
                try await model.api.sendVoid(
                    "/api/account", method: .delete,
                    body: Body(current_password: password, apple_identity_token: appleToken)
                )
                await model.logout()
                dismiss()
            } catch { self.error = error.localizedDescription }
        }
    }
}
