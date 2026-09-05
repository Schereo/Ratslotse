import Foundation
import RatslotseAPI
import RatslotseDesign
import SwiftUI

#if DEBUG
func ratsDebugValue(_ key: String) -> String? {
    if let value = ProcessInfo.processInfo.environment[key] { return value }
    let prefix = key + "="
    if let value = CommandLine.arguments.first(where: { $0.hasPrefix(prefix) }).map({
        String($0.dropFirst(prefix.count))
    }) { return value }
    if let index = CommandLine.arguments.firstIndex(of: "-" + key),
       CommandLine.arguments.indices.contains(index + 1) {
        return CommandLine.arguments[index + 1]
    }
    return nil
}
#else
func ratsDebugValue(_: String) -> String? { nil }
#endif

public struct NativeRootView: View {
    @Bindable private var model: AppModel
    @Namespace private var zoomNamespace

    public init(model: AppModel) { self.model = model }

    public var body: some View {
        NavigationStack(path: $model.navigation) {
            Group {
                if showsDebugPersonProfile {
                    PublicProfileView(model: model, kind: .person, key: "anne-beispiel")
                } else {
                if model.updateRequired {
                    UpdateRequiredView(notice: model.updateNotice)
                } else {
                    switch model.session {
                    case .loading:
                        LaunchLoadingView()
                    case .loggedOut:
                        if model.onboardingStep == 0 {
                            NativeOnboardingWelcomeView(model: model)
                        } else {
                            WelcomeView(model: model)
                        }
                    case .pending(let user):
                        VerificationPendingView(model: model, user: user)
                    case .active:
                        if model.onboardingStep == 0 {
                            NativeOnboardingWelcomeView(model: model)
                        } else if model.onboardingStep != nil {
                            NativeOnboardingFlow(model: model)
                        } else {
                            MainTabsView(model: model)
                        }
                    }
                }
                }
            }
            .navigationDestination(for: AppRoute.self) { route in
                RatsRouteScaffold(model: model) {
                    RouteDestinationView(model: model, route: route)
                }
                .ratsZoomDestination(RatsZoomID.forRoute(route))
            }
        }
        .environment(\.ratsZoomNamespace, zoomNamespace)
        .sensoryFeedback(.success, trigger: model.actionFeedback)
        .font(RatsFont.body())
        .foregroundStyle(RatsColor.text)
        .background(RatsColor.page.ignoresSafeArea())
        .preferredColorScheme(preferredColorScheme)
        .overlay(alignment: .top) {
            if model.isOffline {
                RatsLabel("Offline", .wifiOff)
                    .font(RatsFont.body(11, weight: .semibold))
                    .padding(.horizontal, 10)
                    .padding(.vertical, 5)
                    .background(.ultraThinMaterial)
                    .clipShape(Capsule())
                    .padding(.top, 6)
                    .accessibilityLabel("Keine Internetverbindung")
            }
        }
        .overlay {
            if let badge = model.badgeCelebration {
                BadgeCelebrationOverlay(model: model, badge: badge)
            }
        }
        .animation(.snappy, value: model.badgeCelebration?.id)
        .sheet(item: $model.authPresentation) { presentation in
            AuthFlowView(model: model, initial: presentation)
                .ratsLargeSheet()
        }
        .alert("Ratslotse", isPresented: Binding(
            get: { model.alertMessage != nil },
            set: { if !$0 { model.alertMessage = nil } }
        )) {
            Button("OK", role: .cancel) { model.alertMessage = nil }
        } message: {
            Text(model.alertMessage ?? "")
        }
        .task {
#if DEBUG
            if ratsDebugValue("RATSLOTSE_DEBUG_ACTIVE_SESSION") == "1",
               let user = debugActiveUser() {
                model.session = .active(user)
                model.onboardingStep = nil
            } else {
                await model.bootstrap()
            }
            if ratsDebugValue("RATSLOTSE_DEBUG_BADGES") == "1",
               let snapshot = debugBadgeSnapshot() {
                model.badgeSnapshot = snapshot
            }
            switch ratsDebugValue("RATSLOTSE_DEBUG_AUTH") {
            case "login": model.authPresentation = .login
            case "register": model.authPresentation = .register
            case "forgot": model.authPresentation = .forgotPassword
            case "reset": model.authPresentation = .resetPassword(token: "visual-qa")
            default: break
            }
            if let rawStep = ratsDebugValue("RATSLOTSE_DEBUG_ONBOARDING"),
               let step = Int(rawStep), (0...3).contains(step) {
                model.onboardingStep = step
            }
#else
            await model.bootstrap()
#endif
        }
    }

    private var showsDebugPersonProfile: Bool {
#if DEBUG
        ratsDebugValue("RATSLOTSE_DEBUG_MAIN") == "person-detail"
#else
        false
#endif
    }

    private var preferredColorScheme: ColorScheme? {
        switch model.appearance {
        case .system: nil
        case .light: .light
        case .dark: .dark
        }
    }

#if DEBUG
    private func debugActiveUser() -> User? {
        let savesConversations = ratsDebugValue("RATSLOTSE_DEBUG_CONVERSATIONS") == "1" ? 1 : 0
        let role = ratsDebugValue("RATSLOTSE_DEBUG_MAIN") == "admin" ? "admin" : "user"
        let json = #"{"id":1,"email":"visual-qa@ratslotse.de","role":""# + role + #"","status":"active","delivery_channel":"push","email_verified":true,"apple_linked":false,"has_password":false,"access_token":null,"display_name":"Visual QA","saves_conversations":"#
            + String(savesConversations)
            + "}"
        return try? JSONDecoder().decode(User.self, from: Data(json.utf8))
    }

    private func debugBadgeSnapshot() -> BadgeSnapshot? {
        let json = #"{"badges":[{"id":"erste-frage","title":"Erste Frage","hint":"Stell dem Rat deine erste KI-Frage.","earned":true},{"id":"themen-lotse","title":"Themen-Lotse","hint":"Lege dein erstes Thema an.","earned":true},{"id":"quiz-serie","title":"Quiz-Serie ×5","hint":"Spiele das Quiz an 5 Tagen in Folge.","earned":false,"progress":{"current":4,"target":5}},{"id":"kartograf","title":"Kartograf","hint":"Öffne 3 Orte auf der Stadtkarte.","earned":true},{"id":"analyst","title":"Analyst","hint":"Erkunde die Analyse-Seite.","earned":true},{"id":"sitzungsgast","title":"Sitzungsgast","hint":"Klapp eine Tagesordnung auf.","earned":true},{"id":"fruehwarner","title":"Frühwarner","hint":"Aktiviere Push-Mitteilungen.","earned":true},{"id":"kompass","title":"Kompass","hint":"Mach die Lotti-Tour einmal ganz durch.","earned":false}],"earned_count":6,"total":8,"next":{"id":"quiz-serie","title":"Quiz-Serie ×5","hint":"Spiele das Quiz an 5 Tagen in Folge."},"newly_earned":[]}"#
        return try? JSONDecoder().decode(BadgeSnapshot.self, from: Data(json.utf8))
    }
#endif
}

private struct RatsRouteScaffold<Content: View>: View {
    @Bindable var model: AppModel
    @ViewBuilder let content: Content
    @Environment(\.horizontalSizeClass) private var horizontalSizeClass
    @Environment(\.dynamicTypeSize) private var dynamicTypeSize

    init(model: AppModel, @ViewBuilder content: () -> Content) {
        self.model = model
        self.content = content()
    }

    var body: some View {
        Group {
            if horizontalSizeClass == .regular {
                HStack(spacing: 0) {
                    RatsSidebarNavigation(
                        model: model,
                        active: activeDestination,
                        select: select
                    )
                    .frame(width: dynamicTypeSize.isAccessibilitySize ? 280 : 224)
                    Divider().overlay(RatsColor.border)
                    routeContent
                }
            } else {
                routeContent
            }
        }
    }

    private var routeContent: some View {
        VStack(spacing: 0) {
            HStack {
                Button {
                    if !model.navigation.isEmpty { model.navigation.removeLast() }
                } label: {
                    RatsGlyphView(glyph: .back, color: RatsColor.bodyText)
                        .frame(width: 20, height: 20)
                        .frame(width: 38, height: 38)
                        .background(RatsColor.card)
                        .overlay(Circle().stroke(RatsColor.border))
                        .clipShape(Circle())
                }
                .buttonStyle(RatsRouteButtonStyle())
                .accessibilityLabel("Zurück")
                Spacer()
                Text("Ratslotse")
                    .font(RatsFont.title(17))
                    .foregroundStyle(RatsColor.text)
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
        // Die ausgeblendete Leiste nimmt UIKit die Rand-Geste mit — s.
        // SwipeBack.swift. Ohne das hier gäbe es den Weg zurück nur über den
        // Knopf oben links.
        .ratsSwipeBack()
    }

    private var activeDestination: MainNavigationDestination {
        if let tabletPage = model.tabletPage {
            return MainNavigationDestination(tabletPage)
        }
        return switch model.selectedTab {
        case .today: .today
        case .questions: .questions
        case .council:
            switch model.councilSection {
            case .decisions: .decisions
            case .sessions: .sessions
            case .map: .map
            }
        case .topics: .topics
        case .account: .account
        }
    }

    private func select(_ destination: MainNavigationDestination) {
        navigate(to: destination, model: model)
    }
}

private struct RatsRouteButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .scaleEffect(configuration.isPressed ? 0.94 : 1)
            .opacity(configuration.isPressed ? 0.72 : 1)
            .animation(.easeOut(duration: 0.12), value: configuration.isPressed)
    }
}

private struct LaunchLoadingView: View {
    var body: some View {
        ZStack {
            RatsColor.page.ignoresSafeArea()
            // The exact same full-screen artwork is used by UILaunchScreen.
            // Keeping it here prevents Lotti from changing size while the
            // session is restored. Real in-app loading states animate her.
            Image("Splash")
                .renderingMode(.original)
                .accessibilityHidden(true)
        }
    }
}

private struct UpdateRequiredView: View {
    let notice: String?

    var body: some View {
        ZStack {
            RatsColor.page.ignoresSafeArea()
            VStack(spacing: 0) {
                Lotti3DView(scene: .questions)
                    .frame(width: 174, height: 128)
                    .padding(.bottom, -14)
                    .zIndex(1)
                    .accessibilityHidden(true)
                VStack(alignment: .leading, spacing: 14) {
                    MonoKicker("Neue Version verfügbar")
                    Text("Update erforderlich")
                        .font(RatsFont.title(30))
                    Text(notice ?? "Diese Version ist zu alt, um verlässlich mit Ratslotse zu arbeiten.")
                        .font(RatsFont.body(15))
                        .foregroundStyle(RatsColor.bodyText)
                        .lineSpacing(4)
                    Link(destination: URL(string: "https://apps.apple.com/app/id6786553049")!) {
                        RatsLabel("Im App Store aktualisieren", .download)
                            .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(PrimaryButtonStyle())
                    .frame(maxWidth: .infinity)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .ratsCard()
            }
            .frame(maxWidth: 480)
            .padding(22)
        }
    }
}

private struct MainTabsView: View {
    @Bindable var model: AppModel
    @Environment(\.horizontalSizeClass) private var horizontalSizeClass
    @Environment(\.dynamicTypeSize) private var dynamicTypeSize
    @State private var showsMore = ProcessInfo.processInfo.environment["RATSLOTSE_DEBUG_MORE"] == "1"
    @State private var showsTour = ratsDebugValue("RATSLOTSE_DEBUG_TOUR") == "1"
    @State private var accountReturnTab: AppTab = .today

    var body: some View {
        Group {
            if horizontalSizeClass == .regular {
                HStack(spacing: 0) {
                    RatsSidebarNavigation(
                        model: model,
                        active: activeDestination,
                        select: select
                    )
                    .frame(width: dynamicTypeSize.isAccessibilitySize ? 280 : 224)
                    Divider().overlay(RatsColor.border)
                    tabContent
                }
            } else {
                tabContent
                    .safeAreaInset(edge: .bottom, spacing: 0) {
                        RatsBottomNavigation(
                            active: activeDestination,
                            select: select,
                            openMore: { showsMore = true }
                        )
                    }
            }
        }
        .sheet(isPresented: $showsMore) {
            MoreHubView(
                model: model,
                openCouncil: { section in
                    model.navigation.removeAll()
                    model.tabletPage = nil
                    model.councilSection = section
                    model.selectedTab = .council
                },
                openAccount: {
                    if model.selectedTab != .account {
                        accountReturnTab = model.selectedTab
                    }
                    model.navigation.removeAll()
                    model.tabletPage = nil
                    model.selectedTab = .account
                },
                openTour: {
                    showsMore = false
                    DispatchQueue.main.async { showsTour = true }
                }
            )
            .ratsLargeSheet()
        }
        .fullScreenCover(isPresented: $showsTour) {
            GuidedTourView(model: model, open: openTourTarget)
        }
        .onAppear {
            if horizontalSizeClass == .regular { showsMore = false }
#if DEBUG
            switch ratsDebugValue("RATSLOTSE_DEBUG_MAIN") {
            case "decision-detail":
                model.selectedTab = .council
                model.navigation = [.decision(id: 1)]
            case "person-detail":
                model.selectedTab = .council
                model.navigation = [.person(slug: "anne-beispiel")]
            case "topic-detail":
                model.selectedTab = .council
                model.navigation = [.topic(slug: "sichere-schulwege")]
            case "place-detail":
                model.selectedTab = .council
                model.navigation = [.place(id: "pferdemarkt")]
            case "decisions":
                model.navigation.removeAll()
                model.councilSection = .decisions
                model.selectedTab = .council
            case "questions":
                model.navigation.removeAll()
                model.selectedTab = .questions
            case "sessions":
                model.navigation.removeAll()
                model.councilSection = .sessions
                model.selectedTab = .council
            case "session-detail":
                model.councilSection = .sessions
                model.selectedTab = .council
                // Mit hervorgehobenem Punkt: Ein geteilter Link trägt den TOP
                // mit, und die Sichtprobe soll genau diesen Zustand zeigen.
                model.navigation = [.sessions(ksinr: 42, tops: ["Ö 7"])]
            case "map":
                model.navigation.removeAll()
                model.councilSection = .map
                model.selectedTab = .council
            case "topics":
                model.navigation.removeAll()
                model.selectedTab = .topics
            case "account":
                model.navigation.removeAll()
                model.selectedTab = .account
            case "analysis":
                model.navigation.removeAll()
                model.tabletPage = .analysis
            case "admin":
                model.navigation = [.admin]
            case "subscriptions":
                model.navigation.removeAll()
                model.tabletPage = .subscriptions
            case "saved":
                model.navigation.removeAll()
                model.tabletPage = .saved
            case "quiz":
                model.navigation.removeAll()
                if horizontalSizeClass == .regular {
                    model.tabletPage = .quiz
                } else {
                    model.selectedTab = .questions
                    model.navigation.append(.quiz(area: nil))
                }
            default: break
            }
#endif
        }
        .onChange(of: horizontalSizeClass) { _, sizeClass in
            if sizeClass == .regular { showsMore = false }
        }
    }

    @ViewBuilder
    private var tabContent: some View {
        if usesDebugSavedLayout {
            SavedCouncilView(model: model)
                .toolbar(.hidden, for: .navigationBar)
        } else if horizontalSizeClass == .regular, let tabletPage = model.tabletPage {
            tabletContent(tabletPage)
                .toolbar(.hidden, for: .navigationBar)
        } else {
            TabView(selection: $model.selectedTab) {
                TodayView(model: model)
                    .tag(AppTab.today)
                    .toolbar(.hidden, for: .tabBar)
                QuestionsView(model: model)
                    .tag(AppTab.questions)
                    .toolbar(.hidden, for: .tabBar)
                CouncilBrowserView(model: model)
                    .tag(AppTab.council)
                    .toolbar(.hidden, for: .tabBar)
                TopicsView(model: model)
                    .tag(AppTab.topics)
                    .toolbar(.hidden, for: .tabBar)
                AccountView(model: model) {
                    model.selectedTab = accountReturnTab
                    showsMore = true
                }
                    .tag(AppTab.account)
                    .toolbar(.hidden, for: .tabBar)
            }
            .toolbar(.hidden, for: .tabBar)
        }
    }

    private var usesDebugSavedLayout: Bool {
#if DEBUG
        horizontalSizeClass == .compact && ratsDebugValue("RATSLOTSE_DEBUG_MAIN") == "saved"
#else
        false
#endif
    }

    @ViewBuilder
    private func tabletContent(_ page: TabletPage) -> some View {
        switch page {
        case .analysis: CouncilInsightsView(model: model)
        case .subscriptions: CommitteeSubscriptionsView(model: model)
        case .saved: SavedCouncilView(model: model)
        case .quiz: QuizView(model: model, area: nil)
        }
    }

    private var activeDestination: MainNavigationDestination {
        if horizontalSizeClass == .regular, let tabletPage = model.tabletPage {
            return MainNavigationDestination(tabletPage)
        }
        return switch model.selectedTab {
        case .today: .today
        case .questions: .questions
        case .council:
            switch model.councilSection {
            case .decisions: .decisions
            case .sessions: .sessions
            case .map: .map
            }
        case .topics: .topics
        case .account: .account
        }
    }

    private func select(_ destination: MainNavigationDestination) {
        navigate(to: destination, model: model) { showsMore = true }
    }

    private func openTourTarget(_ target: GuidedTourTarget) {
        switch target {
        case .questions: select(.questions)
        case .decisions: select(.decisions)
        case .analysis:
            if horizontalSizeClass == .regular { select(.analysis) }
            else {
                model.navigation.append(.analysis)
            }
        case .map: select(.map)
        case .topics: select(.topics)
        }
    }
}

private enum MainNavigationDestination: Identifiable {
    case today
    case questions
    case decisions
    case sessions
    case map
    case topics
    case analysis
    case subscriptions
    case saved
    case quiz
    case account
    case more

    static let phoneCases: [Self] = [.today, .questions, .sessions, .topics, .more]
    static let tabletCouncilCases: [Self] = [.today, .questions, .decisions, .sessions, .map, .analysis]
    static let tabletPersonalCases: [Self] = [.topics, .subscriptions, .saved, .quiz]

    init(_ page: TabletPage) {
        switch page {
        case .analysis: self = .analysis
        case .subscriptions: self = .subscriptions
        case .saved: self = .saved
        case .quiz: self = .quiz
        }
    }

    var id: String { label }

    var label: String {
        switch self {
        case .today: "Start"
        case .questions: "Fragen"
        case .decisions: "Beschlüsse"
        case .sessions: "Sitzungen"
        case .map: "Stadtkarte"
        case .topics: "Themen"
        case .analysis: "Analyse"
        case .subscriptions: "Abos"
        case .saved: "Merkliste"
        case .quiz: "Quiz"
        case .account: "Konto"
        case .more: "Mehr"
        }
    }

    var glyph: RatsGlyph {
        switch self {
        case .today: .home
        case .questions: .ask
        case .decisions: .decisions
        case .sessions: .calendar
        case .map: .map
        case .topics: .topics
        case .analysis: .analysis
        case .subscriptions: .subscriptions
        case .saved: .saved
        case .quiz: .quiz
        case .account: .profile
        case .more: .more
        }
    }
}

@MainActor
private func navigate(
    to destination: MainNavigationDestination,
    model: AppModel,
    openMore: () -> Void = {}
) {
    model.navigation.removeAll()
    switch destination {
    case .today:
        model.tabletPage = nil
        model.selectedTab = .today
    case .questions:
        model.tabletPage = nil
        model.selectedTab = .questions
    case .decisions:
        model.tabletPage = nil
        model.councilSection = .decisions
        model.selectedTab = .council
    case .sessions:
        model.tabletPage = nil
        model.councilSection = .sessions
        model.selectedTab = .council
    case .map:
        model.tabletPage = nil
        model.councilSection = .map
        model.selectedTab = .council
    case .topics:
        model.tabletPage = nil
        model.selectedTab = .topics
    case .analysis: model.tabletPage = .analysis
    case .subscriptions: model.tabletPage = .subscriptions
    case .saved: model.tabletPage = .saved
    case .quiz: model.tabletPage = .quiz
    case .account:
        model.tabletPage = nil
        model.selectedTab = .account
    case .more: openMore()
    }
}

private struct RatsSidebarNavigation: View {
    let model: AppModel
    let active: MainNavigationDestination
    let select: (MainNavigationDestination) -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack(spacing: 9) {
                Lotti3DView(scene: .wave, animated: false)
                    .frame(width: 64, height: 56)
                    .accessibilityHidden(true)
                VStack(alignment: .leading, spacing: 2) {
                    Text("Ratslotse")
                        .font(RatsFont.title(21, weight: .heavy))
                        .foregroundStyle(RatsColor.text)
                        .lineLimit(1)
                        .minimumScaleFactor(0.8)
                    Text("OLDENBURGS RAT")
                        .font(RatsFont.mono(8.5, weight: .semibold))
                        .tracking(1.1)
                        .foregroundStyle(RatsColor.secondary)
                }
            }
            .padding(.horizontal, 16)
            .padding(.top, 12)
            .padding(.bottom, 15)

            MonoKicker("Bereiche")
                .padding(.horizontal, 17)
                .padding(.bottom, 7)

            VStack(spacing: 4) {
                ForEach(MainNavigationDestination.tabletCouncilCases) { destination in
                    sidebarButton(destination)
                }
            }
            .padding(.horizontal, 10)

            MonoKicker("Für dich")
                .padding(.horizontal, 17)
                .padding(.top, 13)
                .padding(.bottom, 7)

            VStack(spacing: 4) {
                ForEach(MainNavigationDestination.tabletPersonalCases) { destination in
                    sidebarButton(destination)
                }
            }
            .padding(.horizontal, 10)

            Spacer(minLength: 14)

            Button { select(.account) } label: {
                HStack(spacing: 10) {
                    LottiProfileAvatar(
                        accountID: model.user?.id ?? 0,
                        size: 38,
                        isSelected: active == .account
                    )
                    VStack(alignment: .leading, spacing: 2) {
                        Text(model.user?.displayName ?? "Mein Konto")
                            .font(RatsFont.body(12.5, weight: .semibold))
                            .foregroundStyle(RatsColor.text)
                            .lineLimit(1)
                        Text(model.user?.email ?? "Einstellungen")
                            .font(RatsFont.body(9.5))
                            .foregroundStyle(RatsColor.secondary)
                            .lineLimit(1)
                    }
                    Spacer(minLength: 0)
                }
                .padding(10)
                .background(active == .account ? RatsColor.primary.opacity(0.08) : RatsColor.stage)
                .overlay(RoundedRectangle(cornerRadius: 14).stroke(active == .account ? RatsColor.primary.opacity(0.22) : RatsColor.border))
                .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
            }
            .buttonStyle(RatsNavigationButtonStyle())
            .padding(.horizontal, 10)
            .padding(.bottom, 12)
        }
        .background(RatsColor.card.ignoresSafeArea())
    }

    private func sidebarButton(_ destination: MainNavigationDestination) -> some View {
        Button { select(destination) } label: {
            HStack(spacing: 11) {
                RatsGlyphView(
                    glyph: destination.glyph,
                    color: active == destination ? RatsColor.primaryText : RatsColor.secondary
                )
                .frame(width: 20, height: 20)
                .frame(width: 34, height: 34)
                .background(active == destination ? RatsColor.primary : RatsColor.stage)
                .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
                Text(destination.label)
                    .font(RatsFont.body(13.5, weight: active == destination ? .semibold : .medium))
                    .foregroundStyle(active == destination ? RatsColor.text : RatsColor.bodyText)
                    .lineLimit(1)
                    .minimumScaleFactor(0.8)
                Spacer(minLength: 0)
                if active == destination {
                    Circle().fill(RatsColor.signal).frame(width: 6, height: 6)
                }
            }
            .padding(.horizontal, 8)
            .frame(minHeight: 45)
            .background(active == destination ? RatsColor.primary.opacity(0.08) : Color.clear)
            .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
            .contentShape(Rectangle())
        }
        .buttonStyle(RatsNavigationButtonStyle())
        .accessibilityLabel(destination.label)
        .accessibilityAddTraits(active == destination ? .isSelected : [])
    }
}

private struct RatsBottomNavigation: View {
    let active: MainNavigationDestination
    let select: (MainNavigationDestination) -> Void
    let openMore: () -> Void

    @Namespace private var selectionAnimation

    var body: some View {
        navigationItems
            .padding(6)
            .frame(maxWidth: 430)
            .bottomNavigationGlassSurface()
            .padding(.horizontal, 12)
            .padding(.top, 7)
            .padding(.bottom, 4)
            .frame(maxWidth: .infinity)
    }

    private var navigationItems: some View {
        HStack(spacing: 2) {
            ForEach(MainNavigationDestination.phoneCases) { destination in
                Button {
                    withAnimation(.snappy(duration: 0.28, extraBounce: 0.08)) {
                        if destination == .more { openMore() }
                        else { select(destination) }
                    }
                } label: {
                    VStack(spacing: 3) {
                        RatsGlyphView(
                            glyph: destination.glyph,
                            color: active == destination ? RatsColor.primary : RatsColor.secondary
                        )
                        .frame(width: 20, height: 20)

                        Text(destination.label)
                            .font(RatsFont.body(9.5, weight: active == destination ? .semibold : .medium))
                            .foregroundStyle(active == destination ? RatsColor.primary : RatsColor.secondary)
                            .lineLimit(1)
                    }
                    .frame(maxWidth: .infinity, minHeight: 48)
                    .background {
                        if active == destination {
                            RoundedRectangle(cornerRadius: 17, style: .continuous)
                                .fill(RatsColor.primary.opacity(0.10))
                                .overlay {
                                    RoundedRectangle(cornerRadius: 17, style: .continuous)
                                        .stroke(.white.opacity(0.32), lineWidth: 0.75)
                                }
                                .matchedGeometryEffect(id: "active-navigation", in: selectionAnimation)
                        }
                    }
                    .contentShape(Rectangle())
                }
                .buttonStyle(RatsNavigationButtonStyle())
                .accessibilityLabel(destination.label)
                .accessibilityAddTraits(active == destination ? .isSelected : [])
            }
        }
    }
}

private extension View {
    @ViewBuilder
    func bottomNavigationGlassSurface() -> some View {
        if #available(iOS 26.0, *) {
            self
                .glassEffect(
                    .regular.tint(RatsColor.card.opacity(0.16)),
                    in: .rect(cornerRadius: 27)
                )
                .overlay {
                    RoundedRectangle(cornerRadius: 27, style: .continuous)
                        .stroke(.white.opacity(0.30), lineWidth: 0.75)
                }
                .shadow(color: RatsColor.primary.opacity(0.13), radius: 18, y: 8)
        } else {
            self
                .background {
                    ZStack {
                        RoundedRectangle(cornerRadius: 27, style: .continuous)
                            .fill(.ultraThinMaterial)
                        RoundedRectangle(cornerRadius: 27, style: .continuous)
                            .fill(RatsColor.card.opacity(0.62))
                    }
                }
                .overlay {
                    RoundedRectangle(cornerRadius: 27, style: .continuous)
                        .stroke(.white.opacity(0.44), lineWidth: 1)
                }
                .shadow(color: RatsColor.primary.opacity(0.11), radius: 16, y: 7)
        }
    }
}

private struct RatsNavigationButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .scaleEffect(configuration.isPressed ? 0.94 : 1)
            .opacity(configuration.isPressed ? 0.72 : 1)
            .animation(.easeOut(duration: 0.12), value: configuration.isPressed)
    }
}

struct RouteDestinationView: View {
    let model: AppModel
    let route: AppRoute

    @ViewBuilder
    var body: some View {
        switch route {
        case .decision(let id): DecisionDetailView(model: model, decisionID: id)
        case let .sessions(ksinr, tops): SessionRouteView(model: model, ksinr: ksinr, tops: tops)
        case .person(let slug): PublicProfileView(model: model, kind: .person, key: slug)
        case .topic(let slug): PublicProfileView(model: model, kind: .topic, key: slug)
        case .place(let id): PublicProfileView(model: model, kind: .place, key: id)
        case .quiz(let area): QuizView(model: model, area: area)
        case .analysis: CouncilInsightsView(model: model)
        case .admin: AdminView(model: model)
        case .sharedAnswer(let token): SharedAnswerView(model: model, token: token)
        case .web(let url): ExternalWebView(url: url)
        default: EmptyView()
        }
    }
}
