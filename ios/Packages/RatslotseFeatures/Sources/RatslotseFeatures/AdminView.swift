import Charts
import RatslotseAPI
import RatslotseDesign
import SwiftUI

private enum AdminSection: String, CaseIterable, Identifiable {
    case stats = "Statistik"
    case feedback = "Feedback"
    case llm = "LLM-Kosten"
    case prompts = "Prompts"
    case users = "Nutzer*innen"
    case quiz = "Quiz"
    case places = "Orte"
    case aliases = "Dubletten"
    var id: String { rawValue }
}

struct AdminView: View {
    let model: AppModel
    @State private var section: AdminSection = .stats

    var body: some View {
        Group {
            if model.user?.isAdmin == true {
                ScrollView {
                    VStack(alignment: .leading, spacing: 18) {
                        HStack(alignment: .top, spacing: 16) {
                            VStack(alignment: .leading, spacing: 5) {
                                MonoKicker("Nur für Admins")
                                Text("Admin")
                                    .font(RatsFont.title(32, weight: .heavy))
                                Text("Betrieb, Inhalte und Konten – nativ und mit denselben Endpunkten wie im Web.")
                                    .font(RatsFont.body(14))
                                    .foregroundStyle(RatsColor.bodyText)
                            }
                            Spacer()
                            Lotti3DView(scene: .reading, animated: false)
                                .frame(width: 118, height: 88)
                                .accessibilityHidden(true)
                        }

                        ScrollView(.horizontal, showsIndicators: false) {
                            HStack(spacing: 8) {
                                ForEach(AdminSection.allCases) { item in
                                    Button(item.rawValue) { section = item }
                                        .font(RatsFont.body(12, weight: .semibold))
                                        .foregroundStyle(section == item ? Color.white : RatsColor.bodyText)
                                        .padding(.horizontal, 13)
                                        .frame(minHeight: 39)
                                        .background(section == item ? RatsColor.primary : RatsColor.card)
                                        .overlay(Capsule().stroke(section == item ? .clear : RatsColor.border))
                                        .clipShape(Capsule())
                                }
                            }
                        }

                        adminContent
                    }
                    .frame(maxWidth: 980, alignment: .leading)
                    .padding(20)
                }
                .background(RatsColor.page)
            } else {
                VStack(spacing: 14) {
                    Lotti3DView(scene: .reading, animated: false).frame(width: 150, height: 120)
                    MonoKicker("Geschützter Bereich")
                    Text("Kein Zugriff").font(RatsFont.title(26))
                    Text("Dieser Bereich ist ausschließlich für Admin-Konten freigeschaltet.")
                        .font(RatsFont.body(14)).foregroundStyle(RatsColor.secondary).multilineTextAlignment(.center)
                }
                .frame(maxWidth: 440)
                .ratsCard()
                .padding(24)
            }
        }
        .toolbar(.hidden, for: .navigationBar)
    }

    @ViewBuilder private var adminContent: some View {
        switch section {
        case .stats: AdminStatsView(model: model)
        case .feedback: AdminFeedbackView(model: model)
        case .llm: AdminLLMView(model: model)
        case .prompts: AdminPromptsView(model: model)
        case .users: AdminUsersView(model: model)
        case .quiz: AdminQuizView(model: model)
        case .places: AdminPlacesView(model: model)
        case .aliases: AdminAliasesView(model: model)
        }
    }
}

private struct AdminGrowth: Decodable, Sendable {
    struct Series: Decodable, Sendable { let total: Int; let series: [Double]; let delta: Int; let days: [String] }
    struct Council: Decodable, Sendable {
        let sessions: Int; let agendaItems: Int; let decisionsWithKi: Int
        let hoursSinceFetch: Double?; let nextSession: String?
        enum CodingKeys: String, CodingKey { case sessions; case agendaItems = "agenda_items"; case decisionsWithKi = "decisions_with_ki"; case hoursSinceFetch = "hours_since_fetch"; case nextSession = "next_session" }
    }
    let users: Series; let topics: Series; let wau: [Double]; let council: Council
}

private struct AdminStatsView: View {
    let model: AppModel
    @State private var data: AdminGrowth?
    @State private var range = "90d"
    @State private var error: String?

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack { Text("Wachstum").font(RatsFont.title(20)); Spacer(); rangeMenu }
            if let data {
                LazyVGrid(columns: [GridItem(.adaptive(minimum: 230), spacing: 12)], spacing: 12) {
                    growthCard("Registrierte Nutzer*innen", data.users)
                    growthCard("Angelegte Themen", data.topics)
                    statCard("Sitzungen", value: data.council.sessions)
                    statCard("Tagesordnungspunkte", value: data.council.agendaItems)
                    statCard("Beschlüsse mit KI-Feldern", value: data.council.decisionsWithKi)
                    VStack(alignment: .leading, spacing: 8) {
                        MonoKicker("Ratsinfo-Import")
                        Label(importLabel(data.council.hoursSinceFetch), systemImage: "circle.fill")
                            .font(RatsFont.body(13, weight: .semibold))
                            .foregroundStyle(importColor(data.council.hoursSinceFetch))
                        if let next = data.council.nextSession { Text("Nächste Sitzung: \(next)").font(RatsFont.body(12)).foregroundStyle(RatsColor.secondary) }
                    }.ratsCard()
                }
            } else if let error { ErrorCard(message: error) { Task { await load() } } }
            else { ProgressView().frame(maxWidth: .infinity).padding(40) }
        }.task(id: range) { await load() }
    }

    private var rangeMenu: some View {
        Menu {
            ForEach([("30d", "30 Tage"), ("90d", "90 Tage"), ("12m", "12 Monate"), ("all", "Alles")], id: \.0) { value, label in Button(label) { range = value } }
        } label: { Label(range == "all" ? "Alles" : range.uppercased(), systemImage: "calendar").font(RatsFont.body(12, weight: .semibold)).padding(.horizontal, 11).frame(minHeight: 38).background(RatsColor.card).clipShape(Capsule()) }
    }

    private func growthCard(_ title: String, _ series: AdminGrowth.Series) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack { MonoKicker(title); Spacer(); if series.delta > 0 { Text("+\(series.delta)").foregroundStyle(RatsColor.success).font(RatsFont.body(11, weight: .bold)) } }
            Text(series.total.formatted(.number.locale(Locale(identifier: "de_DE")))).font(RatsFont.title(28))
            Chart(Array(series.series.enumerated()), id: \.offset) { item in AreaMark(x: .value("Tag", item.offset), y: .value("Anzahl", item.element)).foregroundStyle(RatsColor.primary.opacity(0.16)); LineMark(x: .value("Tag", item.offset), y: .value("Anzahl", item.element)).foregroundStyle(RatsColor.primary).lineStyle(.init(lineWidth: 2)) }.chartXAxis(.hidden).chartYAxis(.hidden).frame(height: 60)
        }.ratsCard()
    }

    private func statCard(_ title: String, value: Int) -> some View { VStack(alignment: .leading, spacing: 7) { MonoKicker(title); Text(value.formatted(.number.locale(Locale(identifier: "de_DE")))).font(RatsFont.title(27)) }.frame(maxWidth: .infinity, alignment: .leading).ratsCard() }
    private func importLabel(_ hours: Double?) -> String { guard let hours else { return "Noch kein Lauf" }; return hours < 26 ? "Läuft · vor \(Int(hours)) h" : "Überfällig · vor \(Int(hours)) h" }
    private func importColor(_ hours: Double?) -> Color { guard let hours else { return RatsColor.muted }; return hours < 26 ? RatsColor.success : hours < 72 ? RatsColor.warning : RatsColor.danger }
    private func load() async { do { data = try await model.api.get("/api/admin/stats/growth", query: [.init(name: "range", value: range)]); error = nil } catch { self.error = error.localizedDescription } }
}

private struct AdminFeedback: Decodable, Sendable, Identifiable { let id: Int; let email: String?; let kind: String; let message: String; let createdAt: String; let readAt: String?; enum CodingKeys: String, CodingKey { case id, email, kind, message; case createdAt = "created_at"; case readAt = "read_at" } }
private struct AdminFeedbackEnvelope: Decodable, Sendable { let items: [AdminFeedback]; let unread: Int }

private struct AdminFeedbackView: View {
    let model: AppModel
    @State private var envelope: AdminFeedbackEnvelope?
    @State private var error: String?
    var body: some View { adminList(title: "Feedback", subtitle: envelope.map { "\($0.unread) offen" }) {
        ForEach(envelope?.items ?? []) { item in
            VStack(alignment: .leading, spacing: 9) {
                HStack { Text(item.kind == "bug" ? "Fehler" : item.kind == "feature" ? "Idee" : "Sonstiges").font(RatsFont.body(11, weight: .bold)).foregroundStyle(item.kind == "bug" ? RatsColor.danger : RatsColor.primary); Spacer(); Text(item.createdAt.prefix(10)).font(RatsFont.mono(10)).foregroundStyle(RatsColor.secondary) }
                Text(item.message).font(RatsFont.body(14)).lineSpacing(3)
                HStack { Text(item.email ?? "Anonym").font(RatsFont.body(11)).foregroundStyle(RatsColor.secondary); Spacer(); Button(item.readAt == nil ? "Erledigt" : "Wieder öffnen") { Task { await toggle(item) } }.buttonStyle(.bordered) }
            }.ratsCard()
        }
        if let error { ErrorCard(message: error) { Task { await load() } } }
    }.task { await load() } }
    private func load() async { do { envelope = try await model.api.get("/api/admin/feedback"); error = nil } catch { self.error = error.localizedDescription } }
    private func toggle(_ item: AdminFeedback) async { do { try await model.api.sendVoid("/api/admin/feedback/\(item.id)/read?read=\(item.readAt == nil)"); await load() } catch { self.error = error.localizedDescription } }
}

private struct LLMUsage: Decodable, Sendable {
    struct Feature: Decodable, Sendable, Identifiable { var id: String { feature }; let feature: String; let calls: Int; let cost: Double; let models: [String] }
    struct Point: Decodable, Sendable, Identifiable { var id: String { date }; let date: String; let cost: Double; let calls: Int }
    let features: [Feature]; let series: [Point]; let costMonth: Double; let projectedMonth: Double; let calls30d: Int; let budgetMonthly: Double; let budgetPct: Double
    enum CodingKeys: String, CodingKey { case features, series; case costMonth = "cost_month"; case projectedMonth = "projected_month"; case calls30d = "calls_30d"; case budgetMonthly = "budget_monthly"; case budgetPct = "budget_pct" }
}

private struct AdminLLMView: View {
    let model: AppModel; @State private var data: LLMUsage?; @State private var error: String?
    var body: some View { adminList(title: "LLM-Kosten", subtitle: "Schätzwerte aus Token-Nutzung") {
        if let data {
            LazyVGrid(columns: [GridItem(.adaptive(minimum: 210), spacing: 12)], spacing: 12) {
                metric("Diesen Monat", String(format: "$%.2f", data.costMonth), String(format: "Hochrechnung $%.2f", data.projectedMonth))
                metric("Aufrufe · 30 Tage", data.calls30d.formatted(), "")
                metric("Budget", "\(Int(data.budgetPct)) %", "$\(Int(data.budgetMonthly)) / Monat")
            }
            Chart(data.series) { point in LineMark(x: .value("Tag", point.date), y: .value("Kosten", point.cost)).foregroundStyle(RatsColor.primary); AreaMark(x: .value("Tag", point.date), y: .value("Kosten", point.cost)).foregroundStyle(RatsColor.primary.opacity(0.12)) }.frame(height: 180).ratsCard()
            ForEach(data.features) { feature in HStack { VStack(alignment: .leading) { Text(feature.feature.replacingOccurrences(of: "_", with: " ")).font(RatsFont.body(14, weight: .semibold)); Text(feature.models.joined(separator: ", ")).font(RatsFont.body(10)).foregroundStyle(RatsColor.secondary) }; Spacer(); Text("\(feature.calls) · $\(feature.cost, specifier: "%.2f")").font(RatsFont.mono(11)) }.ratsCard() }
        } else if let error { ErrorCard(message: error) { Task { await load() } } } else { ProgressView().padding(40) }
    }.task { await load() } }
    private func metric(_ title: String, _ value: String, _ detail: String) -> some View { VStack(alignment: .leading, spacing: 6) { MonoKicker(title); Text(value).font(RatsFont.title(27)); if !detail.isEmpty { Text(detail).font(RatsFont.body(11)).foregroundStyle(RatsColor.secondary) } }.frame(maxWidth: .infinity, alignment: .leading).ratsCard() }
    private func load() async { do { data = try await model.api.get("/api/admin/llm-usage"); error = nil } catch { self.error = error.localizedDescription } }
}

private struct AdminPrompt: Decodable, Sendable, Identifiable { var id: String { key }; let key: String; let title: String; let description: String; var content: String; let `default`: String; let isOverridden: Bool; enum CodingKeys: String, CodingKey { case key, title, description, content, `default`; case isOverridden = "is_overridden" } }
private struct AdminPromptsView: View {
    let model: AppModel; @State private var prompts: [AdminPrompt] = []; @State private var error: String?
    var body: some View { adminList(title: "Prompts", subtitle: "Änderungen gelten sofort im gemeinsamen Backend") {
        ForEach($prompts) { $prompt in PromptEditor(model: model, prompt: $prompt, reload: load) }
        if let error { ErrorCard(message: error) { Task { await load() } } }
    }.task { await load() } }
    private func load() async { do { prompts = try await model.api.get("/api/admin/prompts"); error = nil } catch { self.error = error.localizedDescription } }
}

private struct PromptEditor: View {
    let model: AppModel; @Binding var prompt: AdminPrompt; let reload: () async -> Void
    @State private var expanded = false; @State private var busy = false; @State private var message: String?
    var body: some View { DisclosureGroup(isExpanded: $expanded) {
        TextEditor(text: $prompt.content).font(.system(.caption, design: .monospaced)).frame(minHeight: 220).padding(8).background(RatsColor.page).clipShape(RoundedRectangle(cornerRadius: 12))
        HStack { Button("Speichern") { Task { await save() } }.buttonStyle(.borderedProminent).disabled(busy); if prompt.isOverridden { Button("Standard") { Task { await reset() } }.buttonStyle(.bordered).disabled(busy) }; if let message { Text(message).font(RatsFont.body(11)).foregroundStyle(RatsColor.secondary) } }.padding(.top, 8)
    } label: { VStack(alignment: .leading, spacing: 3) { HStack { Text(prompt.title).font(RatsFont.body(15, weight: .bold)); if prompt.isOverridden { Text("angepasst").font(RatsFont.body(9, weight: .bold)).foregroundStyle(RatsColor.warning) } }; Text(prompt.description).font(RatsFont.body(11)).foregroundStyle(RatsColor.secondary); Text(prompt.key).font(RatsFont.mono(9)).foregroundStyle(RatsColor.muted) } }.ratsCard() }
    private func save() async { busy = true; defer { busy = false }; struct Body: Encodable, Sendable { let content: String }; do { try await model.api.sendVoid("/api/admin/prompts/\(prompt.key)", method: .put, body: Body(content: prompt.content)); message = "Gespeichert"; await reload() } catch { message = error.localizedDescription } }
    private func reset() async { busy = true; defer { busy = false }; do { try await model.api.sendVoid("/api/admin/prompts/\(prompt.key)/reset"); await reload() } catch { message = error.localizedDescription } }
}

private struct AdminUserRow: Decodable, Sendable, Identifiable { let id: Int; let email: String; let role: String; let status: String; let lastSeen: String?; let nTopics: Int; let nAbos: Int; let nQuiz: Int; let nKi: Int; enum CodingKeys: String, CodingKey { case id,email,role,status; case lastSeen = "last_seen"; case nTopics = "n_topics"; case nAbos = "n_abos"; case nQuiz = "n_quiz"; case nKi = "n_ki" } }
private struct AdminUsersView: View {
    let model: AppModel; @State private var users: [AdminUserRow] = []; @State private var query = ""; @State private var error: String?
    var filtered: [AdminUserRow] { query.isEmpty ? users : users.filter { $0.email.localizedCaseInsensitiveContains(query) } }
    var body: some View { adminList(title: "Nutzer*innen", subtitle: "\(users.count) Konten") {
        TextField("E-Mail suchen", text: $query).textFieldStyle(.roundedBorder)
        ForEach(filtered) { user in VStack(alignment: .leading, spacing: 10) { HStack { Text(user.email).font(RatsFont.body(14, weight: .semibold)).lineLimit(1); Spacer(); Text(user.role).font(RatsFont.mono(9)).foregroundStyle(user.role == "admin" ? RatsColor.signal : RatsColor.secondary) }; Text("\(user.nTopics) Themen · \(user.nAbos) Abos · \(user.nKi) KI-Fragen · \(user.nQuiz) Quiz").font(RatsFont.body(11)).foregroundStyle(RatsColor.secondary); HStack { Menu(user.role == "admin" ? "Admin" : "Nutzer*in") { Button("Nutzer*in") { Task { await update(user, key: "role", value: "user") } }; Button("Admin") { Task { await update(user, key: "role", value: "admin") } } }.buttonStyle(.bordered); Button(user.status == "active" ? "Sperren" : "Freischalten") { Task { await update(user, key: "status", value: user.status == "active" ? "pending" : "active") } }.buttonStyle(.bordered).disabled(user.id == model.user?.id) } }.ratsCard() }
        if let error { ErrorCard(message: error) { Task { await load() } } }
    }.task { await load() } }
    private func load() async { do { users = try await model.api.get("/api/admin/users"); error = nil } catch { self.error = error.localizedDescription } }
    private func update(_ user: AdminUserRow, key: String, value: String) async { do { let body = JSONValue.object([key: .string(value)]); try await model.api.sendVoid("/api/admin/users/\(user.id)/\(key)", method: .put, body: body); await load() } catch { self.error = error.localizedDescription } }
}

private struct QuizEnvelope: Decodable, Sendable { let flagged: [FlaggedQuiz] }
private struct FlaggedQuiz: Decodable, Sendable, Identifiable { var id: Int { questionID }; let questionID: Int; let bad: Int; let good: Int; let comments: String?; let question: String; let areaType: String; let areaKey: String; let options: [String]; let correctIndex: Int; enum CodingKeys: String, CodingKey { case bad,good,comments,question,options; case questionID = "question_id"; case areaType = "area_type"; case areaKey = "area_key"; case correctIndex = "correct_index" } }
private struct AdminQuizView: View {
    let model: AppModel; @State private var items: [FlaggedQuiz] = []; @State private var error: String?
    var body: some View { adminList(title: "Quizmoderation", subtitle: "Schlecht bewertete Fragen") { ForEach(items) { item in VStack(alignment: .leading, spacing: 9) { HStack { Text("\(item.areaType): \(item.areaKey)").font(RatsFont.mono(9)); Spacer(); Text("👎 \(item.bad) · 👍 \(item.good)").font(RatsFont.body(11)) }; Text(item.question).font(RatsFont.body(14, weight: .semibold)); if item.options.indices.contains(item.correctIndex) { Text("Richtig: \(item.options[item.correctIndex])").font(RatsFont.body(11)).foregroundStyle(RatsColor.secondary) }; Button("Ausmustern", role: .destructive) { Task { await retire(item) } }.buttonStyle(.bordered) }.ratsCard() }; if items.isEmpty && error == nil { Text("Keine gemeldeten Fragen.").foregroundStyle(RatsColor.secondary).ratsCard() }; if let error { ErrorCard(message: error) { Task { await load() } } } }.task { await load() } }
    private func load() async { do { let value: QuizEnvelope = try await model.api.get("/api/admin/quiz/flagged"); items = value.flagged; error = nil } catch { self.error = error.localizedDescription } }
    private func retire(_ item: FlaggedQuiz) async { do { try await model.api.sendVoid("/api/admin/quiz/\(item.questionID)/retire"); await load() } catch { self.error = error.localizedDescription } }
}

private struct PlaceEnvelope: Decodable, Sendable { let candidates: [PlaceCandidate] }
private struct PlaceCandidate: Decodable, Sendable, Identifiable { var id: String { slug }; let slug: String; let name: String; let kind: String; let status: String; let decisionCount: Int; let lastDate: String; let avgConfidence: Double; enum CodingKeys: String, CodingKey { case slug,name,kind,status; case decisionCount = "decision_count"; case lastDate = "last_date"; case avgConfidence = "avg_confidence" } }
private struct AdminPlacesView: View {
    let model: AppModel; @State private var items: [PlaceCandidate] = []; @State private var status = "pending"; @State private var error: String?
    var body: some View { adminList(title: "Ortskandidaten", subtitle: "Redaktionelle Prüfung der automatisch erkannten Orte") { Picker("Status", selection: $status) { Text("Offen").tag("pending"); Text("Konkrete Orte").tag("concrete"); Text("Freigegeben").tag("approved"); Text("Verworfen").tag("rejected") }.pickerStyle(.segmented); ForEach(items) { item in VStack(alignment: .leading, spacing: 9) { HStack { Text(item.name).font(RatsFont.body(15, weight: .bold)); Spacer(); Text("\(item.decisionCount) Belege").font(RatsFont.mono(9)).foregroundStyle(RatsColor.primary) }; Text("\(item.kind) · \(Int(item.avgConfidence * 100)) % · \(item.lastDate)").font(RatsFont.body(11)).foregroundStyle(RatsColor.secondary); HStack { if status == "pending" { Button("Als konkreten Ort bestätigen") { Task { await review(item, value: "concrete") } }.buttonStyle(.borderedProminent); Button("Verwerfen", role: .destructive) { Task { await review(item, value: "rejected") } }.buttonStyle(.bordered) } else { Button("Prüfung wieder öffnen") { Task { await reopen(item) } }.buttonStyle(.bordered) } } }.ratsCard() }; if let error { ErrorCard(message: error) { Task { await load() } } } }.task(id: status) { await load() } }
    private func load() async { do { let value: PlaceEnvelope = try await model.api.get("/api/admin/place-candidates", query: [.init(name: "status", value: status), .init(name: "limit", value: "300")]); items = value.candidates; error = nil } catch { self.error = error.localizedDescription } }
    private func review(_ item: PlaceCandidate, value: String) async { struct Body: Encodable, Sendable { let status: String }; do { try await model.api.sendVoid("/api/admin/place-candidates/\(item.slug.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? item.slug)", method: .put, body: Body(status: value)); await load() } catch { self.error = error.localizedDescription } }
    private func reopen(_ item: PlaceCandidate) async { do { try await model.api.sendVoid("/api/admin/place-candidates/\(item.slug.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? item.slug)", method: .delete); await load() } catch { self.error = error.localizedDescription } }
}

private struct AliasEnvelope: Decodable, Sendable { let aliases: [EntityAlias] }
private struct EntityAlias: Decodable, Sendable, Identifiable { var id: String { slug }; let slug: String; let canonicalSlug: String; let source: String; let reason: String?; let aliasName: String?; let canonicalName: String?; enum CodingKeys: String, CodingKey { case slug,source,reason; case canonicalSlug = "canonical_slug"; case aliasName = "alias_name"; case canonicalName = "canonical_name" } }
private struct AdminAliasesView: View {
    let model: AppModel; @State private var items: [EntityAlias] = []; @State private var error: String?
    var body: some View { adminList(title: "Themen-Dubletten", subtitle: "Zusammenführungen sind vollständig umkehrbar") { ForEach(items) { item in HStack(alignment: .top, spacing: 12) { VStack(alignment: .leading, spacing: 5) { Text(item.aliasName ?? item.slug).font(RatsFont.body(14, weight: .bold)); Text("→ \(item.canonicalName ?? item.canonicalSlug)").font(RatsFont.body(12)).foregroundStyle(RatsColor.primary); if let reason = item.reason { Text(reason).font(RatsFont.body(11)).foregroundStyle(RatsColor.secondary) } }; Spacer(); Button("Trennen", role: .destructive) { Task { await undo(item) } }.buttonStyle(.bordered) }.ratsCard() }; if let error { ErrorCard(message: error) { Task { await load() } } } }.task { await load() } }
    private func load() async { do { let value: AliasEnvelope = try await model.api.get("/api/admin/entity-aliases"); items = value.aliases; error = nil } catch { self.error = error.localizedDescription } }
    private func undo(_ item: EntityAlias) async { do { try await model.api.sendVoid("/api/admin/entity-aliases/\(item.slug.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? item.slug)", method: .delete); await load() } catch { self.error = error.localizedDescription } }
}

private func adminList<Content: View>(title: String, subtitle: String?, @ViewBuilder content: () -> Content) -> some View {
    VStack(alignment: .leading, spacing: 12) {
        VStack(alignment: .leading, spacing: 3) { Text(title).font(RatsFont.title(20)); if let subtitle { Text(subtitle).font(RatsFont.body(12)).foregroundStyle(RatsColor.secondary) } }
        content()
    }
}
