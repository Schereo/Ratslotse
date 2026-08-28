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
        List {
            Section {
                if topics.isEmpty && error == nil {
                    ContentUnavailableView(
                        "Noch keine Themen",
                        systemImage: "bell",
                        description: Text("Lege ein Thema an. Ratslotse meldet dir neue passende Beschlüsse.")
                    )
                }
                ForEach(topics) { topic in
                    Button {
                        if let id = topic.lastHitID { model.navigation.append(.decision(id: id)) }
                        else { editing = topic; isPresentingEditor = true }
                    } label: {
                        VStack(alignment: .leading, spacing: 7) {
                            HStack {
                                Text(topic.name).font(RatsFont.body(16, weight: .semibold))
                                Spacer()
                                Text(topic.matched ? "\(topic.decisionCount)\(topic.decisionCountCapped ? "+" : "")" : "…")
                                    .font(RatsFont.mono(11)).foregroundStyle(RatsColor.primary)
                            }
                            Text(topic.description)
                                .font(RatsFont.body(13)).foregroundStyle(RatsColor.secondary).lineLimit(2)
                            if topic.unreadCount > 0 { Pill("\(topic.unreadCount) neu", symbol: "bell.badge") }
                            else if let title = topic.lastHitTitle { Text("Zuletzt: \(title)").font(RatsFont.body(11)).foregroundStyle(RatsColor.muted).lineLimit(1) }
                        }
                        .padding(.vertical, 5)
                    }
                    .buttonStyle(.plain)
                    .swipeActions(edge: .trailing) {
                        Button("Löschen", role: .destructive) { remove(topic) }
                        Button("Bearbeiten") { editing = topic; isPresentingEditor = true }.tint(RatsColor.primary)
                    }
                }
            } header: {
                MonoKicker("Meine Themen", trailing: topics.isEmpty ? nil : "\(topics.count)")
            }
            if let error { Section { ErrorCard(message: error) { Task { await load() } } } }
        }
        .scrollContentBackground(.hidden)
        .background(RatsColor.page)
        .navigationTitle("Meine Themen")
        .toolbarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .primaryAction) {
                Button { editing = nil; isPresentingEditor = true } label: { Label("Thema anlegen", systemImage: "plus") }
            }
        }
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
