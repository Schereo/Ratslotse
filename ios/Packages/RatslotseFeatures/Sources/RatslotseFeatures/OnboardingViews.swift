import RatslotseAPI
import RatslotseDesign
import SwiftUI

struct NativeOnboardingWelcomeView: View {
    let model: AppModel

    @Environment(\.horizontalSizeClass) private var horizontalSizeClass
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var appeared = false
    @State private var ringsExpanded = false

    var body: some View {
        GeometryReader { proxy in
            ScrollView {
                Group {
                    // Die zweispaltige Fassung braucht 370 + 62 + 440 + 2×44 =
                    // 960 pt. Ein iPad Pro 11" hat im HOCHFORMAT nur 834 —
                    // dort quetschte der HStack beide Spalten auf je ~342 pt,
                    // und die Karten brachen mitten im Satz um („… Mitteilung
                    // bei / neuen Beschlüssen"). Deshalb entscheidet die
                    // gemessene Breite mit, nicht die Größenklasse allein.
                    if horizontalSizeClass == .regular && proxy.size.width >= 960 {
                        HStack(spacing: 62) {
                            VStack(spacing: 0) {
                                mascot
                                    .scaleEffect(1.28)
                                    .padding(.bottom, 26)
                                welcomeTitle
                            }
                            .frame(maxWidth: 370)

                            VStack(spacing: 0) {
                                promises
                                actions
                            }
                            .frame(maxWidth: 440)
                        }
                        .padding(.horizontal, 44)
                        .padding(.vertical, 38)
                    } else {
                        VStack(spacing: 0) {
                            Spacer(minLength: 26)
                            mascot
                            welcomeTitle
                            promises
                            actions
                            Spacer(minLength: 18)
                        }
                        .padding(.horizontal, 26)
                        .frame(maxWidth: 560)
                    }
                }
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

    private var mascot: some View {
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
            Lotti3DView(scene: .wave)
                .frame(width: 158, height: 144)
        }
        .accessibilityHidden(true)
    }

    private var welcomeTitle: some View {
        VStack(spacing: 0) {
            Text("MOIN & WILLKOMMEN")
                .font(RatsFont.mono(11, weight: .semibold))
                .tracking(2)
                .foregroundStyle(Color(red: 0.98, green: 0.42, blue: 0.20))
                .padding(.top, 20)
            Text("Willkommen bei\nRatslotse")
                .font(RatsFont.title(horizontalSizeClass == .regular ? 38 : 32, weight: .heavy))
                .multilineTextAlignment(.center)
                .foregroundStyle(.white)
                .lineSpacing(-2)
                .padding(.top, 8)
        }
    }

    private var promises: some View {
        VStack(spacing: 10) {
            WelcomePromise(
                symbol: .sparkles,
                color: Color(red: 0.98, green: 0.42, blue: 0.20),
                title: "Frag den Rat",
                detail: "Antworten mit Quellen"
            )
            WelcomePromise(
                symbol: .bellRing,
                color: Color(red: 0.35, green: 0.76, blue: 0.95),
                title: "Bleib informiert",
                detail: "Mitteilung bei neuen Beschlüssen"
            )
            WelcomePromise(
                symbol: .landmark,
                color: .white.opacity(0.82),
                title: "Aus der amtlichen Quelle",
                detail: "Rat Oldenburg"
            )
        }
        .padding(.top, 22)
    }

    private var actions: some View {
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
    }
}

private struct WelcomePromise: View {
    let symbol: RatsGlyph
    let color: Color
    let title: String
    let detail: String

    var body: some View {
        HStack(spacing: 12) {
            RatsIcon(symbol, size: 15)
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
    let scene: Lotti3DScene
    @ViewBuilder let content: Content
    @ViewBuilder let footer: Footer
    @Environment(\.horizontalSizeClass) private var horizontalSizeClass

    var body: some View {
        GeometryReader { proxy in
            ScrollView {
                Group {
                    if horizontalSizeClass == .regular {
                        HStack(alignment: .top, spacing: 34) {
                            VStack(alignment: .leading, spacing: 12) {
                                Lotti3DView(scene: scene)
                                    .frame(width: 240, height: 190)
                                    .accessibilityHidden(true)
                                Text(title)
                                    .font(RatsFont.title(30, weight: .heavy))
                                    .foregroundStyle(RatsColor.text)
                                    .fixedSize(horizontal: false, vertical: true)
                                Text(lead)
                                    .font(RatsFont.body(15))
                                    .foregroundStyle(RatsColor.secondary)
                                    .lineSpacing(4)
                            }
                            .frame(width: 284, alignment: .leading)

                            content
                                .frame(maxWidth: 620, alignment: .leading)
                                .padding(.top, 10)
                        }
                        .frame(maxWidth: 980, alignment: .topLeading)
                    } else {
                        VStack(alignment: .leading, spacing: 0) {
                            HStack(spacing: 12) {
                                Lotti3DView(scene: scene)
                                    .frame(width: 92, height: 70)
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
                    }
                }
                .frame(maxWidth: .infinity)
                .frame(minHeight: max(0, proxy.size.height - 28), alignment: .center)
                .padding(.horizontal, horizontalSizeClass == .regular ? 28 : 18)
                .padding(.vertical, 14)
            }
        }
        .safeAreaInset(edge: .bottom, spacing: 0) {
            Group {
                if horizontalSizeClass == .regular {
                    HStack(alignment: .center, spacing: 34) {
                        Color.clear.frame(width: 284, height: 1)
                        footer.frame(maxWidth: 620, alignment: .trailing)
                    }
                    .frame(maxWidth: 980)
                } else {
                    footer.frame(maxWidth: 620, alignment: .trailing)
                }
            }
            .frame(maxWidth: .infinity)
            .padding(.horizontal, 18)
            .padding(.top, 7)
            .padding(.bottom, 10)
        }
    }
}

private struct OnboardingActionLabel: View {
    let title: String
    let systemImage: RatsGlyph

    var body: some View {
        HStack(spacing: 9) {
            Text(title)
            RatsIcon(systemImage, size: 14)
                .accessibilityHidden(true)
        }
        .font(RatsFont.body(15, weight: .semibold))
        .padding(.horizontal, 5)
        .frame(minHeight: 34)
    }
}

private struct OnboardingGlassFallbackButtonStyle: ButtonStyle {
    let prominent: Bool

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .foregroundStyle(prominent ? RatsColor.primaryText : RatsColor.primary)
            .padding(.horizontal, prominent ? 14 : 10)
            .frame(minHeight: prominent ? 48 : 42)
            .background {
                ZStack {
                    Capsule().fill(.regularMaterial)
                    Capsule().fill(
                        prominent
                            ? RatsColor.primary.opacity(configuration.isPressed ? 0.72 : 0.9)
                            : RatsColor.card.opacity(configuration.isPressed ? 0.55 : 0.72)
                    )
                }
            }
            .overlay {
                Capsule()
                    .stroke(.white.opacity(prominent ? 0.28 : 0.42), lineWidth: 1)
            }
            .shadow(
                color: RatsColor.primary.opacity(prominent ? 0.18 : 0.08),
                radius: configuration.isPressed ? 3 : 9,
                y: configuration.isPressed ? 1 : 4
            )
            .scaleEffect(configuration.isPressed ? 0.975 : 1)
            .animation(.snappy(duration: 0.18), value: configuration.isPressed)
    }
}

private extension View {
    @ViewBuilder
    func onboardingGlassButton(prominent: Bool = true) -> some View {
        if #available(iOS 26.0, *) {
            if prominent {
                self
                    .buttonStyle(.glassProminent)
                    .buttonBorderShape(.capsule)
                    .tint(RatsColor.primary)
                    .foregroundStyle(Color.white)
            } else {
                self
                    .buttonStyle(.glass)
                    .buttonBorderShape(.capsule)
                    .tint(RatsColor.primary)
            }
        } else {
            self.buttonStyle(OnboardingGlassFallbackButtonStyle(prominent: prominent))
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
            scene: .children,
            content: { Group {
                if loading { RatsInlineLoadingState(message: "Gremien werden geladen …") }
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
                Button {
                    Task { await model.advanceOnboarding(to: 2) }
                } label: {
                    OnboardingActionLabel(
                        title: subscriptions.isEmpty ? "Weiter" : "\(subscriptions.count) abonniert",
                        systemImage: .arrowRight
                    )
                }
                .onboardingGlassButton()
                .accessibilityLabel(
                    subscriptions.isEmpty
                        ? "Weiter"
                        : "\(subscriptions.count) abonniert, weiter"
                )
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
                ZStack {
                    RoundedRectangle(cornerRadius: 5, style: .continuous)
                        .fill(selected ? RatsColor.primary : RatsColor.card)
                    RoundedRectangle(cornerRadius: 5, style: .continuous)
                        .stroke(selected ? RatsColor.primary : RatsColor.muted, lineWidth: 1.6)
                    if disabled {
                        ProgressView()
                            .controlSize(.mini)
                            .tint(selected ? RatsColor.primaryText : RatsColor.primary)
                    } else if selected {
                        RatsIcon(.check, size: 11)
                            .foregroundStyle(RatsColor.primaryText)
                    }
                }
                .frame(width: 22, height: 22)
                .accessibilityHidden(true)
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
            }
            .padding(12)
            .background(selected ? RatsColor.primary.opacity(0.05) : RatsColor.card)
            .overlay(
                RoundedRectangle(cornerRadius: 12)
                    .stroke(selected ? RatsColor.primary : RatsColor.border)
            )
            .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
        }
        .buttonStyle(RatsPlainButtonStyle())
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
    let context: String?
    let n: Int
}

private struct TopicSuggestionChoice: View {
    let suggestion: TopicSuggestion
    let exists: Bool
    let disabled: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(alignment: .top, spacing: 9) {
                ZStack {
                    Circle()
                        .fill(exists ? RatsColor.primary : RatsColor.primary.opacity(0.1))
                    RatsIcon(exists ? .check : .plus, size: 12)
                        .foregroundStyle(exists ? RatsColor.primaryText : RatsColor.primary)
                }
                .frame(width: 25, height: 25)
                .accessibilityHidden(true)

                VStack(alignment: .leading, spacing: 4) {
                    Text(suggestion.name)
                        .font(RatsFont.body(12.5, weight: .semibold))
                        .multilineTextAlignment(.leading)
                        .lineLimit(3)
                    if let context = visibleContext {
                        Text(context)
                            .font(RatsFont.body(10.5))
                            .foregroundStyle(RatsColor.secondary)
                            .multilineTextAlignment(.leading)
                            .lineLimit(2)
                    }
                    Text(suggestion.n == 1 ? "1 Erwähnung" : "\(suggestion.n) Erwähnungen")
                        .font(RatsFont.mono(8.5))
                        .foregroundStyle(exists ? RatsColor.primary.opacity(0.72) : RatsColor.muted)
                }

                Spacer(minLength: 0)
            }
            .frame(maxWidth: .infinity, minHeight: visibleContext == nil ? 58 : 82, alignment: .topLeading)
            .padding(11)
            .background(exists ? RatsColor.primary.opacity(0.06) : RatsColor.card)
            .overlay(
                RoundedRectangle(cornerRadius: 14, style: .continuous)
                    .stroke(exists ? RatsColor.primary.opacity(0.35) : RatsColor.border)
            )
            .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
        }
        .buttonStyle(RatsPlainButtonStyle())
        .foregroundStyle(exists ? RatsColor.primary : RatsColor.text)
        .disabled(disabled)
        .accessibilityLabel("\(suggestion.name), \(suggestion.n) Erwähnungen im letzten Jahr")
    }

    private var visibleContext: String? {
        let value = (suggestion.context ?? suggestion.description)
            .trimmingCharacters(in: .whitespacesAndNewlines)
        return value.isEmpty ? nil : value
    }
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
    @Environment(\.horizontalSizeClass) private var horizontalSizeClass
    @State private var name = ""
    @State private var topics: [Topic] = []
    @State private var suggestions: [TopicSuggestion] = []
    @State private var districts: [DistrictOption] = []
    @State private var selectedDistrictID = ""
    @State private var addingDistrict = false
    @State private var isWorking = false
    @State private var error: String?
    @State private var note: String?
    @State private var successMessage: String?
    @State private var successPulse = 0

    var body: some View {
        OnboardingStepPage(
            title: "Worüber willst du Bescheid wissen?",
            lead: "Lege Themen an — Lotti meldet sich, sobald der Rat dazu entscheidet.",
            scene: .questions,
            content: { VStack(alignment: .leading, spacing: 14) {
                Group {
                    if horizontalSizeClass == .regular {
                        HStack(spacing: 10) {
                            topicNameField
                            addTopicButton
                        }
                    } else {
                        VStack(spacing: 10) {
                            topicNameField
                            addTopicButton
                        }
                    }
                }
                Text("Beschreibung nicht nötig — Lotti formuliert sie automatisch aus passenden Beschlüssen.")
                    .font(RatsFont.body(11.5))
                    .foregroundStyle(RatsColor.secondary)

                if !districts.isEmpty {
                    favoriteDistrictPicker
                }

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
                if let successMessage {
                    TopicAddedConfirmation(message: successMessage)
                        .transition(.move(edge: .top).combined(with: .opacity))
                }

                if !suggestions.isEmpty {
                    VStack(alignment: .leading, spacing: 9) {
                        MonoKicker("Gerade aktuell im Rat", trailing: "letzte 12 Monate")
                        LazyVGrid(columns: suggestionColumns, spacing: 10) {
                            ForEach(suggestions) { suggestion in
                                let exists = topics.contains { $0.name == suggestion.name }
                                TopicSuggestionChoice(
                                    suggestion: suggestion,
                                    exists: exists,
                                    disabled: exists || isWorking
                                ) { addSuggestion(suggestion) }
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
                                    RatsIcon(.x, size: 12)
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
                Button { Task { await model.advanceOnboarding(to: 3) } } label: {
                    OnboardingActionLabel(title: "Weiter", systemImage: .arrowRight)
                }
                .onboardingGlassButton()
            }
        )
        .task { await load() }
        .sensoryFeedback(.success, trigger: successPulse)
    }

    private var topicNameField: some View {
        TextField("z. B. Cäcilienbrücke", text: $name)
            .textInputAutocapitalization(.sentences)
            .submitLabel(.done)
            .onSubmit { addCustomTopic() }
            .padding(.horizontal, 14)
            .frame(minHeight: 48)
            .background(RatsColor.card)
            .overlay(RoundedRectangle(cornerRadius: 12).stroke(RatsColor.border))
            .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
    }

    private var addTopicButton: some View {
        Button(action: addCustomTopic) {
            HStack(spacing: 9) {
                if isWorking {
                    ProgressView().tint(RatsColor.primaryText)
                    Text("Lotti formuliert …")
                } else {
                    RatsIcon(.sparkles, size: 16)
                        .accessibilityHidden(true)
                    Text("Mit Lotti anlegen")
                }
            }
            .frame(maxWidth: .infinity)
        }
        .buttonStyle(PrimaryButtonStyle())
        .disabled(!canAddTopic)
        .opacity(name.trimmingCharacters(in: .whitespacesAndNewlines).count < 2 ? 0.7 : 1)
        .accessibilityLabel("Thema mit Lotti anlegen")
    }

    private var favoriteDistrictPicker: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(alignment: .top, spacing: 11) {
                RatsGlyphView(glyph: .location, color: RatsColor.primary)
                    .frame(width: 21, height: 21)
                    .padding(8)
                    .background(RatsColor.primary.opacity(0.09))
                    .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
                VStack(alignment: .leading, spacing: 3) {
                    HStack(spacing: 6) {
                        Text("Dein Stadtteil")
                            .font(RatsFont.body(13.5, weight: .semibold))
                        Text("optional")
                            .font(RatsFont.mono(8.5))
                            .foregroundStyle(RatsColor.muted)
                    }
                    Text("Lotti beobachtet dort neue Beschlüsse und Planungen für dich.")
                        .font(RatsFont.body(11.5))
                        .foregroundStyle(RatsColor.secondary)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }

            Menu {
                ForEach(districts) { district in
                    Button {
                        addFavoriteDistrict(district)
                    } label: {
                        if district.placeID == selectedDistrictID {
                            RatsLabel(district.name, .check)
                        } else {
                            Text(district.name)
                        }
                    }
                }
            } label: {
                HStack(spacing: 10) {
                    Text(selectedDistrict?.name ?? "Stadtteil auswählen")
                        .font(RatsFont.body(13, weight: .semibold))
                        .foregroundStyle(selectedDistrict == nil ? RatsColor.secondary : RatsColor.text)
                        .lineLimit(1)
                    Spacer(minLength: 8)
                    if addingDistrict {
                        ProgressView().controlSize(.small).tint(RatsColor.primary)
                    } else if selectedDistrict != nil {
                        RatsIcon(.circleCheckBig, size: 16)
                            .foregroundStyle(RatsColor.success)
                    } else {
                        RatsGlyphView(glyph: .chevronDown, color: RatsColor.primary)
                            .frame(width: 14, height: 14)
                    }
                }
                .padding(.horizontal, 13)
                .frame(maxWidth: .infinity, minHeight: 44)
                .background(RatsColor.card)
                .overlay(
                    RoundedRectangle(cornerRadius: 11, style: .continuous)
                        .stroke(selectedDistrict == nil ? RatsColor.border : RatsColor.success.opacity(0.4))
                )
                .clipShape(RoundedRectangle(cornerRadius: 11, style: .continuous))
            }
            .disabled(addingDistrict || isWorking)
            .accessibilityLabel("Bevorzugten Stadtteil auswählen")

            if let selectedDistrict {
                Text("\(selectedDistrict.name) steht jetzt unter „Deine Themen“ und löst passende Hinweise aus.")
                    .font(RatsFont.body(10.5))
                    .foregroundStyle(RatsColor.success)
            }
        }
        .padding(12)
        .background(RatsColor.stage)
        .overlay(RoundedRectangle(cornerRadius: 14).stroke(RatsColor.border))
        .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
    }

    private var selectedDistrict: DistrictOption? {
        districts.first { $0.placeID == selectedDistrictID }
    }

    private var canAddTopic: Bool {
        name.trimmingCharacters(in: .whitespacesAndNewlines).count >= 2 && !isWorking
    }

    private var suggestionColumns: [GridItem] {
        if horizontalSizeClass == .regular {
            [GridItem(.adaptive(minimum: 230), spacing: 10)]
        } else {
            [GridItem(.flexible(), spacing: 10), GridItem(.flexible(), spacing: 10)]
        }
    }

    private func load() async {
#if DEBUG
        if ratsDebugValue("RATSLOTSE_DEBUG_TOPIC_SUGGESTIONS") == "1" {
            suggestions = [
                TopicSuggestion(name: "Untere Nadorster Straße", description: "", context: "Umbau und neue Verkehrsführung", n: 12),
                TopicSuggestion(name: "Stadion Maastrichter Straße", description: "", context: "Planung des neuen Fußballstadions", n: 9),
                TopicSuggestion(name: "Alte Fleiwa", description: "", context: "Quartiersentwicklung an der Industriestraße", n: 7),
                TopicSuggestion(name: "Bebauungsplan 851", description: "", context: "Östlich Schützenweg / nördlich Hamelmannstraße", n: 5),
                TopicSuggestion(name: "Quartier am Krusenbusch", description: "", context: "Wohnen und Infrastruktur im Süden", n: 4),
                TopicSuggestion(name: "Weser-Ems-Hallen", description: "", context: "Veranstaltungszentrum und Umfeld", n: 3),
            ]
            return
        }
#endif
        do {
            async let topicRequest: [Topic] = model.api.get("/api/topics")
            async let suggestionRequest: TopicSuggestionResponse = model.api.get("/api/topics/suggestions")
            async let districtRequest: DistrictOptions? = try? await model.api.get("/api/council/districts")
            let result = try await (topicRequest, suggestionRequest, districtRequest)
            topics = result.0
            suggestions = result.1.suggestions
            districts = (result.2?.districts ?? []).sorted {
                $0.name.localizedStandardCompare($1.name) == .orderedAscending
            }
            if selectedDistrictID.isEmpty,
               let district = districts.first(where: { district in
                   topics.contains { $0.name.localizedCaseInsensitiveCompare(district.name) == .orderedSame }
               }) {
                selectedDistrictID = district.placeID
            }
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
                showSuccess("„\(described.name)“ wird jetzt beobachtet.")
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
                note = nil
                showSuccess("„\(suggestion.name)“ wurde zu deinen Themen hinzugefügt.")
            } catch { self.error = error.localizedDescription }
        }
    }

    private func addFavoriteDistrict(_ district: DistrictOption) {
        guard !addingDistrict, !isWorking else { return }
        if topics.contains(where: { $0.name.localizedCaseInsensitiveCompare(district.name) == .orderedSame }) {
            selectedDistrictID = district.placeID
            showSuccess("„\(district.name)“ wird bereits als Stadtteil beobachtet.")
            return
        }
        let previousSelection = selectedDistrictID
        selectedDistrictID = district.placeID
        addingDistrict = true
        error = nil
        note = nil
        Task {
            defer { addingDistrict = false }
            do {
                let detail = district.description?.trimmingCharacters(in: .whitespacesAndNewlines)
                let description: String
                if let detail, !detail.isEmpty {
                    description = "\(detail) Neue Beschlüsse, Planungen und Maßnahmen mit Bezug zu \(district.name)."
                } else {
                    description = "Neue Beschlüsse, Planungen und Maßnahmen des Oldenburger Stadtrats mit Bezug zu \(district.name)."
                }
                try await createTopic(name: district.name, description: description)
                showSuccess("\(district.name) ist jetzt dein beobachteter Stadtteil.")
            } catch {
                selectedDistrictID = previousSelection
                self.error = error.localizedDescription
            }
        }
    }

    private func showSuccess(_ message: String) {
        successPulse += 1
        withAnimation(.snappy(duration: 0.28)) { successMessage = message }
        Task {
            try? await Task.sleep(for: .seconds(4))
            guard successMessage == message else { return }
            withAnimation(.easeOut(duration: 0.2)) { successMessage = nil }
        }
    }

    private func createTopic(name: String, description: String) async throws {
        struct Body: Codable, Sendable { let name: String; let description: String }
        let topic: Topic = try await model.api.send(
            "/api/topics", body: Body(name: name, description: description)
        )
        topics.append(topic)
        suggestions.removeAll { $0.name == topic.name }
        await model.refreshBadges()
    }

    private func remove(_ topic: Topic) {
        Task {
            do {
                try await model.api.sendVoid("/api/topics/\(topic.id)", method: .delete)
                topics.removeAll { $0.id == topic.id }
                if let district = selectedDistrict,
                   district.name.localizedCaseInsensitiveCompare(topic.name) == .orderedSame {
                    selectedDistrictID = ""
                }
            } catch { self.error = error.localizedDescription }
        }
    }
}

private struct TopicAddedConfirmation: View {
    let message: String

    var body: some View {
        HStack(alignment: .top, spacing: 10) {
            RatsIcon(.circleCheckBig, size: 20)
                .foregroundStyle(RatsColor.success)
                .accessibilityHidden(true)
            VStack(alignment: .leading, spacing: 2) {
                Text("Thema hinzugefügt")
                    .font(RatsFont.body(12.5, weight: .bold))
                    .foregroundStyle(RatsColor.success)
                Text(message)
                    .font(RatsFont.body(11.5))
                    .foregroundStyle(RatsColor.bodyText)
            }
            Spacer(minLength: 0)
        }
        .padding(11)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(RatsColor.successTint)
        .overlay(RoundedRectangle(cornerRadius: 11).stroke(RatsColor.success.opacity(0.3)))
        .clipShape(RoundedRectangle(cornerRadius: 11, style: .continuous))
        .accessibilityElement(children: .combine)
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
            scene: .wave,
            content: { VStack(alignment: .leading, spacing: 12) {
                HStack(alignment: .top, spacing: 12) {
                    Lotti3DView(scene: .reading, animated: false)
                        .frame(width: 46, height: 50)
                        .accessibilityHidden(true)
                    VStack(alignment: .leading, spacing: 3) {
                        Text("NEU ZU DEINEN THEMEN")
                            .font(RatsFont.mono(9, weight: .semibold))
                            .foregroundStyle(RatsColor.muted)
                        Text("Cäcilienbrücke: Rat fordert schnelleren Neubau")
                            .font(RatsFont.body(14, weight: .medium))
                            .foregroundStyle(RatsColor.text)
                            .lineLimit(2)
                            .fixedSize(horizontal: false, vertical: true)
                            .layoutPriority(1)
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
                    Group {
                        if isWorking {
                            HStack(spacing: 9) {
                                ProgressView().tint(RatsColor.primaryText)
                                Text("Wird aktiviert …")
                            }
                            .font(RatsFont.body(15, weight: .semibold))
                            .frame(minHeight: 34)
                        } else {
                            OnboardingActionLabel(
                                title: "Mitteilungen erlauben",
                                systemImage: .bellDot
                            )
                        }
                    }
                }
                .onboardingGlassButton()
                .disabled(isWorking)
                Button { Task { await model.completeOnboarding() } } label: {
                    RatsLabel("Vielleicht später", .clock)
                }
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
