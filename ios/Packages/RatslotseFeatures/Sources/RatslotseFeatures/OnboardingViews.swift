import RatslotseAPI
import RatslotseDesign
import SwiftUI

struct NativeOnboardingWelcomeView: View {
    let model: AppModel

    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var appeared = false
    @State private var ringsExpanded = false

    var body: some View {
        GeometryReader { proxy in
            ScrollView {
                VStack(spacing: 0) {
                    Spacer(minLength: 26)
                    ZStack {
                        Circle()
                            .stroke(Color(red: 0.96, green: 0.35, blue: 0.13).opacity(0.75), lineWidth: 2)
                            .frame(width: 154, height: 154)
                            .scaleEffect(ringsExpanded ? 1.13 : 0.94)
                            .opacity(ringsExpanded ? 0.15 : 0.85)
                        Circle()
                            .stroke(Color(red: 0.20, green: 0.68, blue: 0.90).opacity(0.7), lineWidth: 2)
                            .frame(width: 154, height: 154)
                            .scaleEffect(ringsExpanded ? 0.94 : 1.13)
                            .opacity(ringsExpanded ? 0.8 : 0.2)
                        LottiMascot(pose: .wave)
                            .frame(width: 138, height: 138)
                    }
                    .accessibilityHidden(true)

                    Text("MOIN & WILLKOMMEN")
                        .font(RatsFont.mono(11, weight: .semibold))
                        .tracking(2)
                        .foregroundStyle(Color(red: 0.98, green: 0.42, blue: 0.20))
                        .padding(.top, 20)
                    Text("Willkommen bei\nRatslotse")
                        .font(RatsFont.title(32, weight: .heavy))
                        .multilineTextAlignment(.center)
                        .foregroundStyle(.white)
                        .lineSpacing(-2)
                        .padding(.top, 8)

                    VStack(spacing: 10) {
                        WelcomePromise(
                            symbol: "sparkles",
                            color: Color(red: 0.98, green: 0.42, blue: 0.20),
                            title: "Frag den Rat",
                            detail: "Antworten mit Quellen"
                        )
                        WelcomePromise(
                            symbol: "bell.fill",
                            color: Color(red: 0.35, green: 0.76, blue: 0.95),
                            title: "Bleib informiert",
                            detail: "Mitteilung bei neuen Beschlüssen"
                        )
                        WelcomePromise(
                            symbol: "building.columns.fill",
                            color: .white.opacity(0.82),
                            title: "Aus der amtlichen Quelle",
                            detail: "Rat Oldenburg"
                        )
                    }
                    .padding(.top, 22)

                    VStack(spacing: 9) {
                        Button("Los geht’s") { model.beginOnboarding() }
                            .buttonStyle(WelcomePrimaryButtonStyle())
                        Button("Schon registriert? Anmelden") {
                            model.beginOnboarding(with: .login)
                        }
                        .font(RatsFont.body(13, weight: .medium))
                        .foregroundStyle(.white.opacity(0.72))
                        .padding(.vertical, 5)
                    }
                    .padding(.top, 24)
                    Spacer(minLength: 18)
                }
                .padding(.horizontal, 26)
                .frame(maxWidth: 560)
                .frame(maxWidth: .infinity)
                .frame(minHeight: proxy.size.height)
                .opacity(appeared ? 1 : 0)
                .offset(y: appeared ? 0 : 12)
            }
            .scrollIndicators(.hidden)
        }
        .background {
            ZStack {
                LinearGradient(
                    colors: [
                        Color(red: 0.03, green: 0.10, blue: 0.17),
                        Color(red: 0.06, green: 0.18, blue: 0.29),
                        Color(red: 0.07, green: 0.27, blue: 0.39),
                    ],
                    startPoint: .topLeading,
                    endPoint: .bottomTrailing
                )
                OnboardingWaves()
                    .stroke(.white.opacity(0.055), lineWidth: 1)
                Circle().fill(Color(red: 0.75, green: 0.89, blue: 0.97).opacity(0.65))
                    .frame(width: 3, height: 3).offset(x: -130, y: -260)
                Circle().fill(Color(red: 0.75, green: 0.89, blue: 0.97).opacity(0.5))
                    .frame(width: 2, height: 2).offset(x: 130, y: -210)
            }
            .ignoresSafeArea()
        }
        .preferredColorScheme(.dark)
        .task {
            if reduceMotion {
                appeared = true
                ringsExpanded = true
            } else {
                withAnimation(.easeOut(duration: 0.55)) { appeared = true }
                withAnimation(.easeInOut(duration: 1.8).repeatForever(autoreverses: true)) {
                    ringsExpanded = true
                }
            }
        }
    }
}

private struct WelcomePromise: View {
    let symbol: String
    let color: Color
    let title: String
    let detail: String

    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: symbol)
                .font(.system(size: 15, weight: .semibold))
                .foregroundStyle(color)
                .frame(width: 34, height: 34)
                .background(color.opacity(0.13))
                .clipShape(RoundedRectangle(cornerRadius: 9, style: .continuous))
            (Text(title).fontWeight(.semibold) + Text(" — \(detail)"))
                .lineLimit(2)
                .fixedSize(horizontal: false, vertical: true)
                .layoutPriority(1)
            Spacer(minLength: 0)
        }
        .font(RatsFont.body(13.5))
        .foregroundStyle(.white.opacity(0.92))
        .multilineTextAlignment(.leading)
        .padding(.horizontal, 13)
        .padding(.vertical, 11)
        .background(.white.opacity(0.075))
        .overlay(RoundedRectangle(cornerRadius: 13).stroke(.white.opacity(0.13)))
        .clipShape(RoundedRectangle(cornerRadius: 13, style: .continuous))
    }
}

private struct WelcomePrimaryButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(RatsFont.body(15, weight: .semibold))
            .foregroundStyle(.white)
            .frame(maxWidth: .infinity, minHeight: 50)
            .background(Color(red: 0.02, green: 0.44, blue: 0.68).opacity(configuration.isPressed ? 0.72 : 1))
            .clipShape(RoundedRectangle(cornerRadius: 13, style: .continuous))
            .scaleEffect(configuration.isPressed ? 0.985 : 1)
    }
}

private struct OnboardingWaves: Shape {
    func path(in rect: CGRect) -> Path {
        var path = Path()
        for index in 0..<8 {
            let baseY = rect.height * (0.18 + CGFloat(index) * 0.11)
            path.move(to: CGPoint(x: -20, y: baseY))
            path.addCurve(
                to: CGPoint(x: rect.width + 20, y: baseY + 8),
                control1: CGPoint(x: rect.width * 0.28, y: baseY - 24),
                control2: CGPoint(x: rect.width * 0.70, y: baseY + 31)
            )
        }
        return path
    }
}

struct NativeOnboardingFlow: View {
    let model: AppModel

    var body: some View {
        VStack(spacing: 0) {
            OnboardingProgressHeader(step: model.onboardingStep ?? 1) {
                Task {
                    let step = model.onboardingStep ?? 1
                    if step >= 3 { await model.completeOnboarding() }
                    else { await model.advanceOnboarding(to: step + 1) }
                }
            }
            Group {
                switch model.onboardingStep ?? 1 {
                case 1: CommitteeOnboardingStep(model: model)
                case 2: TopicOnboardingStep(model: model)
                default: PushOnboardingStep(model: model)
                }
            }
            .id(model.onboardingStep)
            .transition(.asymmetric(insertion: .move(edge: .trailing), removal: .move(edge: .leading)))
        }
        .background(RatsColor.page.ignoresSafeArea())
        .animation(.easeInOut(duration: 0.24), value: model.onboardingStep)
    }
}

private struct OnboardingProgressHeader: View {
    let step: Int
    let skip: () -> Void

    var body: some View {
        HStack(spacing: 13) {
            HStack(spacing: 6) {
                ForEach(1...3, id: \.self) { number in
                    Capsule()
                        .fill(number <= step ? RatsColor.primary : RatsColor.separator)
                        .frame(height: 4)
                }
            }
            .accessibilityElement(children: .ignore)
            .accessibilityLabel("Schritt \(step) von 3")
            Button("Überspringen", action: skip)
                .font(RatsFont.body(13))
                .foregroundStyle(RatsColor.secondary)
        }
        .padding(.horizontal, 18)
        .padding(.vertical, 11)
    }
}

private struct OnboardingStepPage<Content: View, Footer: View>: View {
    let title: String
    let lead: String
    let pose: LottiPose
    @ViewBuilder let content: Content
    @ViewBuilder let footer: Footer

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 0) {
                HStack(spacing: 12) {
                    LottiMascot(pose: pose)
                        .frame(width: 54, height: 54)
                        .accessibilityHidden(true)
                    Text(title)
                        .font(RatsFont.title(22, weight: .heavy))
                        .foregroundStyle(RatsColor.text)
                        .fixedSize(horizontal: false, vertical: true)
                }
                Text(lead)
                    .font(RatsFont.body(13.5))
                    .foregroundStyle(RatsColor.secondary)
                    .lineSpacing(3)
                    .padding(.top, 9)
                content.padding(.top, 16)
            }
            .frame(maxWidth: 620, alignment: .leading)
            .frame(maxWidth: .infinity)
            .padding(.horizontal, 18)
            .padding(.bottom, 16)
        }
        .safeAreaInset(edge: .bottom, spacing: 0) {
            footer
                .frame(maxWidth: 620)
                .frame(maxWidth: .infinity)
                .padding(.horizontal, 18)
                .padding(.vertical, 12)
                .background(.ultraThinMaterial)
        }
    }
}

private struct CommitteeResponse: Decodable, Sendable { let committees: [String] }
private struct SubscriptionResponse: Decodable, Sendable { let subscriptions: [String] }

private struct CommitteeOnboardingStep: View {
    let model: AppModel
    @State private var committees: [String] = []
    @State private var subscriptions: Set<String> = []
    @State private var changing: Set<String> = []
    @State private var error: String?
    @State private var loading = true

    var body: some View {
        OnboardingStepPage(
            title: "Welche Gremien interessieren dich?",
            lead: "Du bekommst eine Mitteilung, sobald eine Tagesordnung erscheint. Jederzeit änderbar.",
            pose: .point,
            content: { Group {
                if loading { ProgressView("Gremien werden geladen …").tint(RatsColor.primary) }
                if let error { ErrorCard(message: error) { Task { await load() } } }
                LazyVStack(spacing: 8) {
                    ForEach(committees, id: \.self) { committee in
                        CommitteeChoiceRow(
                            committee: committee,
                            selected: subscriptions.contains(committee),
                            disabled: changing.contains(committee)
                        ) { toggle(committee) }
                    }
                }
            } },
            footer: {
                Button(subscriptions.isEmpty ? "Weiter" : "\(subscriptions.count) abonniert · Weiter") {
                    Task { await model.advanceOnboarding(to: 2) }
                }
                .buttonStyle(PrimaryButtonStyle())
                .frame(maxWidth: .infinity)
            }
        )
        .task { await load() }
    }

    private func load() async {
        loading = true
        error = nil
        do {
            async let committeeRequest: CommitteeResponse = model.api.get("/api/council/committees")
            async let subscriptionRequest: SubscriptionResponse = model.api.get("/api/subscriptions")
            let (committeeResult, subscriptionResult) = try await (committeeRequest, subscriptionRequest)
            committees = committeeResult.committees.sorted {
                CommitteeCopy.rank($0) == CommitteeCopy.rank($1)
                    ? CommitteeCopy.short($0).localizedStandardCompare(CommitteeCopy.short($1)) == .orderedAscending
                    : CommitteeCopy.rank($0) < CommitteeCopy.rank($1)
            }
            subscriptions = Set(subscriptionResult.subscriptions)
        } catch { self.error = error.localizedDescription }
        loading = false
    }

    private func toggle(_ committee: String) {
        guard !changing.contains(committee) else { return }
        struct Body: Codable, Sendable { let committee_name: String }
        let wasSelected = subscriptions.contains(committee)
        changing.insert(committee)
        if wasSelected { subscriptions.remove(committee) } else { subscriptions.insert(committee) }
        Task {
            do {
                try await model.api.sendVoid(
                    "/api/subscriptions",
                    method: wasSelected ? .delete : .post,
                    body: Body(committee_name: committee)
                )
            } catch {
                if wasSelected { subscriptions.insert(committee) } else { subscriptions.remove(committee) }
                self.error = error.localizedDescription
            }
            changing.remove(committee)
        }
    }
}

private struct CommitteeChoiceRow: View {
    let committee: String
    let selected: Bool
    let disabled: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(alignment: .top, spacing: 12) {
                Image(systemName: selected ? "checkmark.square.fill" : "square")
                    .font(.system(size: 20, weight: .medium))
                    .foregroundStyle(selected ? RatsColor.primary : RatsColor.muted)
                VStack(alignment: .leading, spacing: 3) {
                    Text(CommitteeCopy.short(committee))
                        .font(RatsFont.body(14, weight: .semibold))
                        .foregroundStyle(RatsColor.text)
                    if let explanation = CommitteeCopy.explanation(committee) {
                        Text(explanation)
                            .font(RatsFont.body(12))
                            .foregroundStyle(RatsColor.secondary)
                            .lineSpacing(2)
                    }
                }
                Spacer(minLength: 0)
                if disabled { ProgressView().controlSize(.small) }
            }
            .padding(12)
            .background(selected ? RatsColor.primary.opacity(0.05) : RatsColor.card)
            .overlay(
                RoundedRectangle(cornerRadius: 12)
                    .stroke(selected ? RatsColor.primary : RatsColor.border)
            )
            .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
        }
        .buttonStyle(.plain)
        .disabled(disabled)
        .accessibilityValue(selected ? "Abonniert" : "Nicht abonniert")
    }
}

private struct TopicSuggestionResponse: Decodable, Sendable {
    let suggestions: [TopicSuggestion]
}

private struct TopicSuggestion: Decodable, Sendable, Identifiable {
    var id: String { name }
    let name: String
    let description: String
    let n: Int
}

private struct TopicDescriptionResult: Decodable, Sendable {
    let name: String
    let description: String
    let matches: Int
    let verdict: String
    let reason: String
}

private struct TopicOnboardingStep: View {
    let model: AppModel
    @State private var name = ""
    @State private var topics: [Topic] = []
    @State private var suggestions: [TopicSuggestion] = []
    @State private var isWorking = false
    @State private var error: String?
    @State private var note: String?

    var body: some View {
        OnboardingStepPage(
            title: "Worüber willst du Bescheid wissen?",
            lead: "Lege Themen an — Lotti meldet sich, sobald der Rat dazu entscheidet.",
            pose: .search,
            content: { VStack(alignment: .leading, spacing: 14) {
                HStack(spacing: 8) {
                    TextField("z. B. Cäcilienbrücke", text: $name)
                        .textInputAutocapitalization(.sentences)
                        .submitLabel(.done)
                        .onSubmit { addCustomTopic() }
                        .padding(.horizontal, 12)
                        .frame(minHeight: 44)
                        .background(RatsColor.card)
                        .overlay(RoundedRectangle(cornerRadius: 11).stroke(RatsColor.border))
                    Button(action: addCustomTopic) {
                        Group {
                            if isWorking { ProgressView().tint(RatsColor.primaryText) }
                            else { Image(systemName: "sparkles") }
                        }
                        .frame(width: 44, height: 44)
                    }
                    .buttonStyle(PrimaryButtonStyle())
                    .disabled(name.trimmingCharacters(in: .whitespacesAndNewlines).count < 2 || isWorking)
                    .accessibilityLabel("Thema anlegen")
                }
                Text("Beschreibung nicht nötig — Lotti formuliert sie automatisch aus passenden Beschlüssen.")
                    .font(RatsFont.body(11.5))
                    .foregroundStyle(RatsColor.secondary)

                if let error {
                    Text(error)
                        .font(RatsFont.body(12))
                        .foregroundStyle(RatsColor.warning)
                        .padding(10)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .background(RatsColor.warningTint)
                        .clipShape(RoundedRectangle(cornerRadius: 9))
                }
                if let note {
                    Text(note)
                        .font(RatsFont.body(12))
                        .foregroundStyle(RatsColor.secondary)
                        .padding(10)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .background(RatsColor.separator.opacity(0.6))
                        .clipShape(RoundedRectangle(cornerRadius: 9))
                }

                if !suggestions.isEmpty {
                    VStack(alignment: .leading, spacing: 9) {
                        MonoKicker("Gerade aktuell im Rat")
                        LazyVGrid(columns: [GridItem(.adaptive(minimum: 145), spacing: 8)], spacing: 8) {
                            ForEach(suggestions) { suggestion in
                                let exists = topics.contains { $0.name == suggestion.name }
                                Button {
                                    addSuggestion(suggestion)
                                } label: {
                                    Label(
                                        suggestion.name,
                                        systemImage: exists ? "checkmark" : "plus"
                                    )
                                    .font(RatsFont.body(12.5, weight: .medium))
                                    .lineLimit(2)
                                    .frame(maxWidth: .infinity, alignment: .leading)
                                    .padding(.horizontal, 10)
                                    .padding(.vertical, 8)
                                    .background(exists ? RatsColor.primary.opacity(0.06) : RatsColor.card)
                                    .overlay(Capsule().stroke(exists ? RatsColor.primary.opacity(0.35) : RatsColor.border))
                                    .clipShape(Capsule())
                                }
                                .buttonStyle(.plain)
                                .foregroundStyle(exists ? RatsColor.primary : RatsColor.text)
                                .disabled(exists || isWorking)
                            }
                        }
                    }
                }

                if !topics.isEmpty {
                    VStack(alignment: .leading, spacing: 9) {
                        MonoKicker("Deine Themen", trailing: "\(topics.count)")
                        ForEach(topics) { topic in
                            HStack(alignment: .top, spacing: 9) {
                                VStack(alignment: .leading, spacing: 5) {
                                    Text(topic.name).font(RatsFont.body(14, weight: .semibold))
                                    Text(topic.description)
                                        .font(RatsFont.body(11.5))
                                        .foregroundStyle(RatsColor.secondary)
                                        .lineLimit(3)
                                    if topic.matched {
                                        Text("\(topic.decisionCount)\(topic.decisionCountCapped ? "+" : "") passende Beschlüsse")
                                            .font(RatsFont.mono(9))
                                            .foregroundStyle(RatsColor.primary)
                                    }
                                }
                                Spacer(minLength: 0)
                                Button(role: .destructive) { remove(topic) } label: {
                                    Image(systemName: "xmark").font(.caption.weight(.semibold))
                                }
                                .accessibilityLabel("\(topic.name) entfernen")
                            }
                            .padding(11)
                            .background(RatsColor.card)
                            .overlay(RoundedRectangle(cornerRadius: 11).stroke(RatsColor.border))
                            .clipShape(RoundedRectangle(cornerRadius: 11))
                        }
                    }
                }
            } },
            footer: {
                Button("Weiter") { Task { await model.advanceOnboarding(to: 3) } }
                    .buttonStyle(PrimaryButtonStyle())
                    .frame(maxWidth: .infinity)
            }
        )
        .task { await load() }
    }

    private func load() async {
        do {
            async let topicRequest: [Topic] = model.api.get("/api/topics")
            async let suggestionRequest: TopicSuggestionResponse = model.api.get("/api/topics/suggestions")
            let result = try await (topicRequest, suggestionRequest)
            topics = result.0
            suggestions = result.1.suggestions
        } catch { self.error = error.localizedDescription }
    }

    private func addCustomTopic() {
        let clean = name.trimmingCharacters(in: .whitespacesAndNewlines)
        guard clean.count >= 2, !isWorking else { return }
        isWorking = true
        error = nil
        note = nil
        Task {
            defer { isWorking = false }
            do {
                struct DescribeBody: Codable, Sendable { let name: String; let description: String }
                let described: TopicDescriptionResult = try await model.api.send(
                    "/api/topics/describe", body: DescribeBody(name: clean, description: "")
                )
                guard described.verdict != "ungeeignet" else {
                    error = described.reason.isEmpty
                        ? "Das sieht nicht nach einem Thema des Oldenburger Stadtrats aus."
                        : described.reason
                    return
                }
                if described.verdict == "plausibel" {
                    note = "Über „\(clean)“ hat der Rat bisher nichts entschieden — Lotti meldet sich, sobald es so weit ist."
                } else if described.matches > 0 {
                    note = "\(described.matches) passende Beschlüsse gefunden."
                }
                try await createTopic(name: described.name, description: described.description)
                name = ""
            } catch { self.error = error.localizedDescription }
        }
    }

    private func addSuggestion(_ suggestion: TopicSuggestion) {
        guard !isWorking else { return }
        isWorking = true
        error = nil
        Task {
            defer { isWorking = false }
            do {
                try await createTopic(name: suggestion.name, description: suggestion.description)
                note = suggestion.n > 0 ? "\(suggestion.n) Erwähnungen im letzten Jahr." : nil
            } catch { self.error = error.localizedDescription }
        }
    }

    private func createTopic(name: String, description: String) async throws {
        struct Body: Codable, Sendable { let name: String; let description: String }
        let topic: Topic = try await model.api.send(
            "/api/topics", body: Body(name: name, description: description)
        )
        topics.append(topic)
        suggestions.removeAll { $0.name == topic.name }
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

private struct PushOnboardingStep: View {
    let model: AppModel
    @State private var isWorking = false
    @State private var error: String?

    var body: some View {
        OnboardingStepPage(
            title: "Soll Lotti sich melden?",
            lead: "Nur wenn der Rat zu deinen Themen entscheidet oder eine Tagesordnung erscheint. Kein Spam — versprochen.",
            pose: .wave,
            content: { VStack(alignment: .leading, spacing: 12) {
                HStack(alignment: .top, spacing: 12) {
                    LottiMascot(pose: .point)
                        .frame(width: 45, height: 45)
                        .accessibilityHidden(true)
                    VStack(alignment: .leading, spacing: 3) {
                        Text("NEU ZU DEINEN THEMEN")
                            .font(RatsFont.mono(9, weight: .semibold))
                            .foregroundStyle(RatsColor.muted)
                        Text("Veloroute 4 beschlossen — 1,1 Mio. €")
                            .font(RatsFont.body(14, weight: .medium))
                            .foregroundStyle(RatsColor.text)
                    }
                    Spacer(minLength: 0)
                }
                .ratsCard()
                if let error { Text(error).font(RatsFont.body(12)).foregroundStyle(RatsColor.warning) }
            } },
            footer: { VStack(spacing: 7) {
                Button {
                    allowNotifications()
                } label: {
                    if isWorking { ProgressView().tint(RatsColor.primaryText) }
                    else { Text("Mitteilungen erlauben") }
                }
                .buttonStyle(PrimaryButtonStyle())
                .disabled(isWorking)
                Button("Vielleicht später") { Task { await model.completeOnboarding() } }
                    .font(RatsFont.body(14))
                    .foregroundStyle(RatsColor.secondary)
                    .padding(.vertical, 7)
            } }
        )
    }

    private func allowNotifications() {
        guard !isWorking else { return }
        isWorking = true
        error = nil
        Task {
            if await model.requestPushPermission() {
                do {
                    struct Body: Codable, Sendable { let delivery_channel: String }
                    let current = model.user?.deliveryChannel
                    let channel = current == "push" || current == "off" ? "push" : "both"
                    let updated: User = try await model.api.send(
                        "/api/account/delivery", method: .put, body: Body(delivery_channel: channel)
                    )
                    try await model.adopt(user: updated)
                } catch { self.error = error.localizedDescription }
            }
            isWorking = false
            await model.completeOnboarding()
        }
    }
}

private enum CommitteeCopy {
    private static let shortNames = [
        "Rat der Stadt Oldenburg": "Rat",
        "Rat der Stadt Oldenburg (Oldb)": "Rat",
        "Ausschuss für Allgemeine Angelegenheiten": "Allgemeine Angelegenheiten",
        "Ausschuss für Finanzen und Beteiligungen": "Finanzen & Beteiligungen",
        "Ausschuss für Integration und Migration": "Integration & Migration",
        "Ausschuss für Stadtgrün, Umwelt und Klima": "Stadtgrün & Klima",
        "Ausschuss für Stadtplanung und Bauen": "Stadtplanung & Bauen",
        "Ausschuss für Wirtschaftsförderung, Digitalisierung und internationale Zusammenarbeit": "Wirtschaft & Digitales",
        "Betriebsausschuss Abfallwirtschaftsbetrieb": "Abfallwirtschaft",
        "Betriebsausschuss Eigenbetrieb Gebäudewirtschaft und Hochbau": "Betrieb Gebäudewirtschaft",
        "Jugendhilfeausschuss": "Jugendhilfe",
        "Kulturausschuss": "Kultur",
        "Schulausschuss": "Schule",
        "Sozialausschuss": "Soziales",
        "Sportausschuss": "Sport",
        "Verkehrsausschuss": "Verkehr",
    ]

    private static let explanations = [
        "Rat": "Entscheidet die großen Linien: Haushalt, Satzungen und Grundsatzbeschlüsse.",
        "Verwaltungsausschuss": "Bereitet die Ratsbeschlüsse vor und entscheidet Eilfälle — tagt nichtöffentlich.",
        "Allgemeine Angelegenheiten": "Verwaltung, Personal, Ordnung und alles, was in keinen Fachausschuss fällt.",
        "Finanzen & Beteiligungen": "Haushalt, Zuwendungen und die städtischen Beteiligungen.",
        "Integration & Migration": "Zuwanderung, Teilhabe und interkulturelle Arbeit in der Stadt.",
        "Stadtgrün & Klima": "Grünflächen, Klimaschutz, Energie und Naturschutz in der Stadt.",
        "Stadtplanung & Bauen": "Bebauungspläne, Bauprojekte und wie sich Viertel entwickeln.",
        "Wirtschaft & Digitales": "Wirtschaftsförderung, Digitalisierung und internationale Zusammenarbeit.",
        "Abfallwirtschaft": "Müllabfuhr, Recycling und der städtische Abfallbetrieb.",
        "Betrieb Gebäudewirtschaft": "Bau und Unterhalt der städtischen Gebäude — Schulen, Kitas, Verwaltung.",
        "Jugendhilfe": "Kitas, Jugendarbeit und Hilfen für Familien.",
        "Kultur": "Museen, Theater, Bibliotheken und die Förderung der freien Szene.",
        "Schule": "Schulen, Ganztagsbetreuung und neue Bildungsstandorte.",
        "Soziales": "Wohnen, Pflege, Teilhabe und soziale Angebote der Stadt.",
        "Sport": "Sportstätten, Vereinsförderung und Bäder.",
        "Verkehr": "Radwege, Straßen, Bus & Bahn, Parken und Verkehrsberuhigung.",
    ]

    private static let ranks = [
        "Rat": 0, "Stadtplanung & Bauen": 1, "Verkehr": 2, "Stadtgrün & Klima": 3,
        "Schule": 4, "Soziales": 5, "Jugendhilfe": 6, "Finanzen & Beteiligungen": 7,
        "Kultur": 8, "Sport": 9, "Wirtschaft & Digitales": 10,
        "Integration & Migration": 11, "Verwaltungsausschuss": 12,
        "Allgemeine Angelegenheiten": 13, "Betrieb Gebäudewirtschaft": 14,
        "Abfallwirtschaft": 15,
    ]

    static func short(_ committee: String) -> String {
        if let known = shortNames[committee] { return known }
        var value = committee
        for prefix in ["Ausschuss für die ", "Ausschuss für den ", "Ausschuss für das ", "Ausschuss für ", "Betriebsausschuss Eigenbetrieb ", "Betriebsausschuss "] where value.hasPrefix(prefix) {
            value.removeFirst(prefix.count)
            break
        }
        return value.replacingOccurrences(of: " und ", with: " & ")
    }

    static func explanation(_ committee: String) -> String? { explanations[short(committee)] }
    static func rank(_ committee: String) -> Int { ranks[short(committee)] ?? 50 }
}
