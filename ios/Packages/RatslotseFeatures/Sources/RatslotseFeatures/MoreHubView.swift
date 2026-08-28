import RatslotseAPI
import RatslotseDesign
import SwiftUI

private enum MoreDestination: Hashable {
    case analysis
    case subscriptions
    case saved
    case quiz
}

struct MoreHubView: View {
    let model: AppModel
    let openCouncil: (CouncilSection) -> Void
    @Environment(\.dismiss) private var dismiss
    @State private var path: NavigationPath = {
        var path = NavigationPath()
        switch ProcessInfo.processInfo.environment["RATSLOTSE_DEBUG_MORE_DESTINATION"] {
        case "analysis": path.append(MoreDestination.analysis)
        case "subscriptions": path.append(MoreDestination.subscriptions)
        case "saved": path.append(MoreDestination.saved)
        case "quiz": path.append(MoreDestination.quiz)
        default: break
        }
        return path
    }()

    var body: some View {
        NavigationStack(path: $path) {
            VStack(spacing: 0) {
                HStack {
                    Text("Mehr entdecken")
                        .font(RatsFont.title(22))
                        .foregroundStyle(RatsColor.text)
                    Spacer()
                    Button { dismiss() } label: {
                        Text("×")
                            .font(RatsFont.body(23, weight: .medium))
                            .foregroundStyle(RatsColor.bodyText)
                            .frame(width: 38, height: 38)
                            .background(RatsColor.card)
                            .overlay(Circle().stroke(RatsColor.border))
                            .clipShape(Circle())
                    }
                    .buttonStyle(RatsPressButtonStyle())
                    .accessibilityLabel("Mehr schließen")
                }
                .padding(.horizontal, 18)
                .padding(.vertical, 12)
                .background(RatsColor.page)
                Divider().overlay(RatsColor.separator)

                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 20) {
                        profileCard
                        destinationGroup(
                            title: "Im Rat",
                            subtitle: "Suchen, einordnen und vor Ort entdecken",
                            rows: [
                                .action("Suche", "Beschlüsse und Vorlagen finden", .search) { open(.decisions) },
                                .action("Stadtkarte", "Was der Rat an welchen Orten bewegt", .map) { open(.map) },
                                .link("Analyse", "Trends, Parteien, Personen, Finanzen und Ziele", .analysis, .analysis),
                            ]
                        )
                        destinationGroup(
                            title: "Für dich",
                            subtitle: "Beobachten, merken und spielerisch entdecken",
                            rows: [
                                .link("Ausschuss-Abos", "Neue und geänderte Tagesordnungen", .subscriptions, .subscriptions),
                                .link("Merkliste", "Beschlüsse und Vorgänge wiederfinden", .saved, .saved),
                                .link("Oldenburg-Quiz", "Dein Wissen über Stadt und Rat", .quiz, .quiz),
                            ]
                        )
                        ratslotseGroup
                        logoutButton
                        legalFooter
                    }
                    .frame(maxWidth: 680, alignment: .leading)
                    .padding(.horizontal, 18)
                    .padding(.top, 16)
                    .padding(.bottom, 30)
                }
                .background(RatsColor.page)
            }
            .toolbar(.hidden, for: .navigationBar)
            .navigationDestination(for: MoreDestination.self) { destination in
                switch destination {
                case .analysis:
                    MoreDestinationScaffold(title: "Mehr", back: goBack) {
                        CouncilInsightsView(model: model)
                    }
                case .subscriptions:
                    MoreDestinationScaffold(title: "Mehr", back: goBack) {
                        CommitteeSubscriptionsView(model: model)
                    }
                case .saved:
                    MoreDestinationScaffold(title: "Mehr", back: goBack) {
                        SavedCouncilView(model: model)
                    }
                case .quiz:
                    MoreDestinationScaffold(title: "Mehr", back: goBack) {
                        QuizView(model: model, area: nil)
                    }
                }
            }
            .navigationDestination(for: AppRoute.self) { route in
                MoreDestinationScaffold(title: "Mehr", back: goBack) {
                    RouteDestinationView(model: model, route: route)
                }
            }
        }
        .presentationDragIndicator(.hidden)
    }

    private var profileCard: some View {
        Button {
            model.selectedTab = .account
            dismiss()
        } label: {
            HStack(spacing: 14) {
                ZStack(alignment: .bottomTrailing) {
                    Circle()
                        .fill(RatsColor.primary)
                        .frame(width: 54, height: 54)
                    RatsGlyphView(glyph: .profile, color: RatsColor.primaryText, lineWidth: 1.65)
                        .frame(width: 27, height: 27)
                    Circle()
                        .fill(RatsColor.signal)
                        .frame(width: 13, height: 13)
                        .overlay(Circle().stroke(RatsColor.card, lineWidth: 2))
                }
                VStack(alignment: .leading, spacing: 3) {
                    MonoKicker("Dein Ratslotse")
                    Text(model.user?.displayName ?? "Moin Oldenburg")
                        .font(RatsFont.title(21))
                        .foregroundStyle(RatsColor.text)
                    Text(model.user?.email ?? "Konto und Einstellungen")
                        .font(RatsFont.body(11))
                        .foregroundStyle(RatsColor.secondary)
                        .lineLimit(1)
                }
                Spacer(minLength: 8)
                Text("Konto")
                    .font(RatsFont.body(11, weight: .semibold))
                    .foregroundStyle(RatsColor.primary)
                    .padding(.horizontal, 10)
                    .padding(.vertical, 6)
                    .background(RatsColor.primary.opacity(0.08))
                    .clipShape(Capsule())
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(16)
            .background(
                LinearGradient(
                    colors: [RatsColor.primary.opacity(0.10), RatsColor.card],
                    startPoint: .topLeading,
                    endPoint: .bottomTrailing
                )
            )
            .overlay(RoundedRectangle(cornerRadius: 18, style: .continuous).stroke(RatsColor.primary.opacity(0.20)))
            .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
        }
        .buttonStyle(RatsPressButtonStyle())
        .accessibilityLabel("Konto von \(model.user?.displayName ?? model.user?.email ?? "Ratslotse") öffnen")
    }

    private func destinationGroup(title: String, subtitle: String, rows: [MoreRow]) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            VStack(alignment: .leading, spacing: 2) {
                MonoKicker(title)
                Text(subtitle)
                    .font(RatsFont.body(12))
                    .foregroundStyle(RatsColor.secondary)
            }
            VStack(spacing: 0) {
                ForEach(Array(rows.enumerated()), id: \.offset) { index, row in
                    if let destination = row.destination {
                        NavigationLink(value: destination) { MoreRowLabel(row: row) }
                            .buttonStyle(RatsPressButtonStyle())
                    } else {
                        Button(action: row.action ?? {}) { MoreRowLabel(row: row) }
                            .buttonStyle(RatsPressButtonStyle())
                    }
                    if index < rows.count - 1 {
                        Divider().overlay(RatsColor.separator).padding(.leading, 58)
                    }
                }
            }
            .padding(.horizontal, 12)
            .background(RatsColor.card)
            .overlay(RoundedRectangle(cornerRadius: 16, style: .continuous).stroke(RatsColor.border))
            .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
        }
    }

    private var ratslotseGroup: some View {
        VStack(alignment: .leading, spacing: 10) {
            MonoKicker("Ratslotse")
            VStack(spacing: 0) {
                Link(destination: URL(string: "mailto:post@ratslotse.de?subject=Feedback%20zur%20iOS-App")!) {
                    MoreRowLabel(row: .action("Feedback geben", "Was können wir besser machen?", .feedback) {})
                }
                .buttonStyle(RatsPressButtonStyle())
                Divider().overlay(RatsColor.separator).padding(.leading, 58)
                Link(destination: URL(string: "https://ratslotse.de/hilfe")!) {
                    MoreRowLabel(row: .action("Hilfe & Kontakt", "Antworten und Kontaktmöglichkeiten", .help) {})
                }
                .buttonStyle(RatsPressButtonStyle())
            }
            .padding(.horizontal, 12)
            .background(RatsColor.card)
            .overlay(RoundedRectangle(cornerRadius: 16, style: .continuous).stroke(RatsColor.border))
            .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
        }
    }

    private var logoutButton: some View {
        Button {
            Task {
                dismiss()
                await model.logout()
            }
        } label: {
            HStack(spacing: 12) {
                RatsGlyphView(glyph: .logout, color: RatsColor.danger)
                    .frame(width: 20, height: 20)
                Text("Abmelden")
                Spacer()
            }
            .font(RatsFont.body(14, weight: .semibold))
            .foregroundStyle(RatsColor.danger)
            .padding(.horizontal, 16)
            .frame(minHeight: 50)
            .background(RatsColor.dangerTint)
            .overlay(RoundedRectangle(cornerRadius: 14, style: .continuous).stroke(RatsColor.danger.opacity(0.18)))
            .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
        }
        .buttonStyle(RatsPressButtonStyle())
    }

    private var legalFooter: some View {
        HStack(spacing: 7) {
            Link("Impressum", destination: URL(string: "https://ratslotse.de/impressum")!)
            Text("·")
            Link("Datenschutz", destination: URL(string: "https://ratslotse.de/datenschutz")!)
            Text("·")
            Link("Changelog", destination: URL(string: "https://ratslotse.de/changelog")!)
        }
        .font(RatsFont.body(10))
        .foregroundStyle(RatsColor.muted)
        .frame(maxWidth: .infinity)
    }

    private func open(_ section: CouncilSection) {
        dismiss()
        model.navigation.removeAll()
        model.councilSection = section
        model.selectedTab = .council
    }

    private func goBack() {
        guard !path.isEmpty else { return }
        path.removeLast()
    }
}

private struct MoreDestinationScaffold<Content: View>: View {
    let title: String
    let back: () -> Void
    @ViewBuilder let content: Content

    init(title: String, back: @escaping () -> Void, @ViewBuilder content: () -> Content) {
        self.title = title
        self.back = back
        self.content = content()
    }

    var body: some View {
        VStack(spacing: 0) {
            HStack {
                Button(action: back) {
                    RatsGlyphView(glyph: .back, color: RatsColor.bodyText, lineWidth: 2)
                        .frame(width: 20, height: 20)
                        .frame(width: 38, height: 38)
                        .background(RatsColor.card)
                        .overlay(Circle().stroke(RatsColor.border))
                        .clipShape(Circle())
                }
                .buttonStyle(RatsPressButtonStyle())
                .accessibilityLabel("Zurück")
                Spacer()
                Text(title)
                    .font(RatsFont.title(17))
                    .foregroundStyle(RatsColor.text)
                    .lineLimit(1)
                Spacer()
                Color.clear.frame(width: 38, height: 38)
            }
            .padding(.horizontal, 18)
            .padding(.vertical, 10)
            .background(RatsColor.page)
            Divider().overlay(RatsColor.separator)
            content
        }
        .background(RatsColor.page)
        .toolbar(.hidden, for: .navigationBar)
    }
}

private struct MoreRow {
    let title: String
    let detail: String
    let glyph: RatsGlyph
    let destination: MoreDestination?
    let action: (() -> Void)?

    static func link(
        _ title: String,
        _ detail: String,
        _ glyph: RatsGlyph,
        _ destination: MoreDestination
    ) -> MoreRow {
        MoreRow(title: title, detail: detail, glyph: glyph, destination: destination, action: nil)
    }

    static func action(
        _ title: String,
        _ detail: String,
        _ glyph: RatsGlyph,
        _ action: @escaping () -> Void
    ) -> MoreRow {
        MoreRow(title: title, detail: detail, glyph: glyph, destination: nil, action: action)
    }
}

private struct MoreRowLabel: View {
    let row: MoreRow

    var body: some View {
        HStack(spacing: 12) {
            RatsGlyphView(glyph: row.glyph)
                .frame(width: 21, height: 21)
                .frame(width: 34, height: 34)
                .background(RatsColor.primary.opacity(0.08))
                .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
            VStack(alignment: .leading, spacing: 2) {
                Text(row.title)
                    .font(RatsFont.body(14, weight: .semibold))
                    .foregroundStyle(RatsColor.text)
                Text(row.detail)
                    .font(RatsFont.body(10.5))
                    .foregroundStyle(RatsColor.secondary)
                    .lineLimit(2)
            }
            Spacer(minLength: 8)
            Text("›")
                .font(RatsFont.body(22))
                .foregroundStyle(RatsColor.muted)
        }
        .frame(maxWidth: .infinity, minHeight: 58, alignment: .leading)
        .contentShape(Rectangle())
    }
}

private struct RatsPressButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .scaleEffect(configuration.isPressed ? 0.985 : 1)
            .opacity(configuration.isPressed ? 0.76 : 1)
            .animation(.easeOut(duration: 0.12), value: configuration.isPressed)
    }
}

private struct SubscriptionEnvelope: Decodable, Sendable {
    let subscriptions: [String]
}

struct CommitteeSubscriptionsView: View {
    let model: AppModel
    @State private var committees: [CommitteeDetail] = []
    @State private var subscriptions: Set<String> = []
    @State private var working: Set<String> = []
    @State private var isLoading = true
    @State private var error: String?

    var body: some View {
        ScrollView {
            LazyVStack(alignment: .leading, spacing: 16) {
                VStack(alignment: .leading, spacing: 5) {
                    MonoKicker("Deine Frühwarnung")
                    Text("Ausschuss-Abos")
                        .font(RatsFont.title(28))
                    Text("Ratslotse meldet neue Tagesordnungen – und Änderungen, die danach noch dazukommen.")
                        .font(RatsFont.body(13))
                        .foregroundStyle(RatsColor.secondary)
                        .lineSpacing(2)
                }

                if isLoading {
                    RatsLoadingState(message: "Gremien werden geladen …")
                } else {
                    if subscriptions.isEmpty {
                        RatsEmptyState(
                            title: "Noch kein Gremium abonniert",
                            message: "Wähle unten die Ausschüsse, die Ratslotse für dich im Blick behalten soll.",
                            symbol: "bell"
                        )
                    } else {
                        MonoKicker("Abonniert", trailing: "\(subscriptions.count)")
                        committeeList(committees.filter { subscriptions.contains($0.name) })
                    }

                    let remaining = committees.filter { !subscriptions.contains($0.name) }
                    if !remaining.isEmpty {
                        MonoKicker("Weitere Gremien", trailing: "\(remaining.count)")
                            .padding(.top, 4)
                        committeeList(remaining)
                    }
                }
                if let error { ErrorCard(message: error) { Task { await load() } } }

                VStack(alignment: .leading, spacing: 8) {
                    Text("Nur ein bestimmtes Anliegen verfolgen?")
                        .font(RatsFont.body(14, weight: .semibold))
                    Text("Lege dafür ein Thema an. Ratslotse durchsucht jede neue Sitzung danach – auch ohne Ausschuss-Abo.")
                        .font(RatsFont.body(12))
                        .foregroundStyle(RatsColor.secondary)
                }
                .ratsCard()
            }
            .frame(maxWidth: 700, alignment: .leading)
            .padding(18)
        }
        .background(RatsColor.page)
        .navigationTitle("Ausschuss-Abos")
        .navigationBarTitleDisplayMode(.inline)
        .refreshable { await load() }
        .task { await load() }
    }

    private func committeeList(_ entries: [CommitteeDetail]) -> some View {
        VStack(spacing: 0) {
            ForEach(Array(entries.enumerated()), id: \.element.id) { index, committee in
                HStack(alignment: .center, spacing: 12) {
                    RatsGlyphView(glyph: .subscriptions)
                        .frame(width: 21, height: 21)
                        .frame(width: 38, height: 38)
                        .background(RatsColor.primary.opacity(0.08))
                        .clipShape(RoundedRectangle(cornerRadius: 11, style: .continuous))
                    VStack(alignment: .leading, spacing: 3) {
                        Text(committeeLabel(committee.name))
                            .font(RatsFont.body(14, weight: .semibold))
                        Text(committeeDetail(committee))
                            .font(RatsFont.body(10.5))
                            .foregroundStyle(RatsColor.secondary)
                            .lineLimit(3)
                    }
                    Spacer(minLength: 8)
                    Button {
                        toggle(committee.name)
                    } label: {
                        if working.contains(committee.name) {
                            ProgressView().tint(subscriptions.contains(committee.name) ? RatsColor.primary : RatsColor.primaryText)
                        } else {
                            Text(subscriptions.contains(committee.name) ? "Abonniert" : "Abonnieren")
                        }
                    }
                    .font(RatsFont.body(11, weight: .semibold))
                    .foregroundStyle(subscriptions.contains(committee.name) ? RatsColor.primary : RatsColor.primaryText)
                    .padding(.horizontal, 11)
                    .frame(minWidth: 84, minHeight: 34)
                    .background(subscriptions.contains(committee.name) ? RatsColor.primary.opacity(0.08) : RatsColor.primary)
                    .overlay(Capsule().stroke(RatsColor.primary.opacity(0.22)))
                    .clipShape(Capsule())
                    .disabled(working.contains(committee.name))
                }
                .padding(.vertical, 11)
                if index < entries.count - 1 {
                    Divider().overlay(RatsColor.separator).padding(.leading, 50)
                }
            }
        }
        .padding(.horizontal, 13)
        .background(RatsColor.card)
        .overlay(RoundedRectangle(cornerRadius: 16, style: .continuous).stroke(RatsColor.border))
        .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
    }

    private func load() async {
        isLoading = true
        defer { isLoading = false }
        do {
            async let committeeRequest: CommitteeOptions = model.api.get("/api/council/committees")
            async let subscriptionRequest: SubscriptionEnvelope = model.api.get("/api/subscriptions")
            let (options, current) = try await (committeeRequest, subscriptionRequest)
            let details = options.details ?? []
            committees = options.committees.map { name in
                details.first(where: { $0.name == name })
                    ?? CommitteeDetail.fallback(name: name)
            }
            subscriptions = Set(current.subscriptions)
            error = nil
        } catch { self.error = error.localizedDescription }
    }

    private func toggle(_ name: String) {
        let wasSubscribed = subscriptions.contains(name)
        struct Body: Codable, Sendable { let committee_name: String }
        working.insert(name)
        Task {
            defer { working.remove(name) }
            do {
                try await model.api.sendVoid(
                    "/api/subscriptions",
                    method: wasSubscribed ? .delete : .post,
                    body: Body(committee_name: name)
                )
                if wasSubscribed { subscriptions.remove(name) }
                else { subscriptions.insert(name) }
            } catch { self.error = error.localizedDescription }
        }
    }

    private func committeeLabel(_ name: String) -> String {
        name
            .replacingOccurrences(of: "Verkehrsausschuss", with: "Verkehr")
            .replacingOccurrences(of: "Sozialausschuss", with: "Soziales")
            .replacingOccurrences(of: "Kulturausschuss", with: "Kultur")
    }

    private func committeeDetail(_ committee: CommitteeDetail) -> String {
        let descriptions = [
            "Verkehrsausschuss": "Radwege, Straßen, Bus & Bahn und Parken",
            "Sozialausschuss": "Wohnen, Pflege, Teilhabe und soziale Angebote",
            "Kulturausschuss": "Museen, Theater, Bibliotheken und freie Szene",
        ]
        let date = RatsDate.weekday(committee.nextDate)
        let next = [date, committee.nextTime].compactMap { $0 }.joined(separator: " · ")
        return [descriptions[committee.name], next.isEmpty ? nil : "Nächster Termin: \(next)"]
            .compactMap { $0 }
            .joined(separator: " · ")
    }
}

private extension CommitteeDetail {
    static func fallback(name: String) -> CommitteeDetail {
        CommitteeDetail(name: name, nextDate: nil, nextTime: nil, decisionsYear: 0)
    }
}
