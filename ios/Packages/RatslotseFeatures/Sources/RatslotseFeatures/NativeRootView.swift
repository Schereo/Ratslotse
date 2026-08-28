import RatslotseAPI
import RatslotseDesign
import SwiftUI

public struct NativeRootView: View {
    @Bindable private var model: AppModel

    public init(model: AppModel) { self.model = model }

    public var body: some View {
        NavigationStack(path: $model.navigation) {
            Group {
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
            .navigationDestination(for: AppRoute.self) { route in
                RatsRouteScaffold(model: model) {
                    RouteDestinationView(model: model, route: route)
                }
            }
        }
        .font(RatsFont.body())
        .foregroundStyle(RatsColor.text)
        .background(RatsColor.page.ignoresSafeArea())
        .overlay(alignment: .top) {
            if model.isOffline {
                Label("Offline", systemImage: "wifi.slash")
                    .font(RatsFont.body(11, weight: .semibold))
                    .padding(.horizontal, 10)
                    .padding(.vertical, 5)
                    .background(.ultraThinMaterial)
                    .clipShape(Capsule())
                    .padding(.top, 6)
                    .accessibilityLabel("Keine Internetverbindung")
            }
        }
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
            await model.bootstrap()
#if DEBUG
            switch ProcessInfo.processInfo.environment["RATSLOTSE_DEBUG_AUTH"] {
            case "login": model.authPresentation = .login
            case "register": model.authPresentation = .register
            case "forgot": model.authPresentation = .forgotPassword
            case "reset": model.authPresentation = .resetPassword(token: "visual-qa")
            default: break
            }
            if let rawStep = ProcessInfo.processInfo.environment["RATSLOTSE_DEBUG_ONBOARDING"],
               let step = Int(rawStep), (0...3).contains(step) {
                model.onboardingStep = step
            }
#endif
        }
    }
}

private struct RatsRouteScaffold<Content: View>: View {
    @Bindable var model: AppModel
    @ViewBuilder let content: Content
    @Environment(\.horizontalSizeClass) private var horizontalSizeClass
    @State private var showsMore = false

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
                        active: showsMore ? .more : activeDestination,
                        select: select,
                        openMore: { showsMore = true }
                    )
                    .frame(width: 224)
                    Divider().overlay(RatsColor.border)
                    routeContent
                }
            } else {
                routeContent
            }
        }
        .sheet(isPresented: $showsMore) {
            MoreHubView(model: model) { section in
                model.navigation.removeAll()
                model.councilSection = section
                model.selectedTab = .council
            }
            .ratsLargeSheet()
        }
    }

    private var routeContent: some View {
        VStack(spacing: 0) {
            HStack {
                Button {
                    if !model.navigation.isEmpty { model.navigation.removeLast() }
                } label: {
                    RatsGlyphView(glyph: .back, color: RatsColor.bodyText, lineWidth: 2)
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
    }

    private var activeDestination: MainNavigationDestination {
        switch model.selectedTab {
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
        model.navigation.removeAll()
        switch destination {
        case .today: model.selectedTab = .today
        case .questions: model.selectedTab = .questions
        case .decisions:
            model.councilSection = .decisions
            model.selectedTab = .council
        case .sessions:
            model.councilSection = .sessions
            model.selectedTab = .council
        case .map:
            model.councilSection = .map
            model.selectedTab = .council
        case .topics: model.selectedTab = .topics
        case .account: model.selectedTab = .account
        case .more: showsMore = true
        }
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
    @Environment(\.horizontalSizeClass) private var horizontalSizeClass

    var body: some View {
        VStack(spacing: 0) {
            Lotti3DView(scene: .celebrate)
                .frame(
                    width: horizontalSizeClass == .regular ? 360 : 300,
                    height: horizontalSizeClass == .regular ? 300 : 250
                )
                .accessibilityHidden(true)

            Text("Ratslotse")
                .font(RatsFont.title(horizontalSizeClass == .regular ? 42 : 36, weight: .heavy))
                .foregroundStyle(RatsColor.text)
                .padding(.top, 4)

            Text("OLDENBURGS RAT VERSTEHEN")
                .font(RatsFont.mono(10.5, weight: .semibold))
                .tracking(1.7)
                .foregroundStyle(RatsColor.signal)
                .padding(.top, 7)

            HStack(spacing: 9) {
                ProgressView()
                    .controlSize(.small)
                    .tint(RatsColor.primary)
                Text("Ratslotse wird vorbereitet …")
                    .font(RatsFont.body(13, weight: .medium))
                    .foregroundStyle(RatsColor.secondary)
            }
            .padding(.top, 22)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(RatsColor.page)
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
                        Label("Im App Store aktualisieren", systemImage: "arrow.down.app")
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
    @State private var showsMore = ProcessInfo.processInfo.environment["RATSLOTSE_DEBUG_MORE"] == "1"

    var body: some View {
        Group {
            if horizontalSizeClass == .regular {
                HStack(spacing: 0) {
                    RatsSidebarNavigation(
                        model: model,
                        active: showsMore ? .more : activeDestination,
                        select: select,
                        openMore: { showsMore = true }
                    )
                    .frame(width: 224)
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
            MoreHubView(model: model) { section in
                model.navigation.removeAll()
                model.councilSection = section
                model.selectedTab = .council
            }
            .ratsLargeSheet()
        }
        .onAppear {
#if DEBUG
            switch ProcessInfo.processInfo.environment["RATSLOTSE_DEBUG_MAIN"] {
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
            default: break
            }
#endif
        }
    }

    private var tabContent: some View {
        TabView(selection: $model.selectedTab) {
            TodayView(model: model)
                .tag(AppTab.today)
            QuestionsView(model: model)
                .tag(AppTab.questions)
            CouncilBrowserView(model: model)
                .tag(AppTab.council)
            TopicsView(model: model)
                .tag(AppTab.topics)
            AccountView(model: model)
                .tag(AppTab.account)
        }
        .toolbar(.hidden, for: .tabBar)
    }

    private var activeDestination: MainNavigationDestination {
        switch model.selectedTab {
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
        model.navigation.removeAll()
        switch destination {
        case .today: model.selectedTab = .today
        case .questions: model.selectedTab = .questions
        case .decisions:
            model.councilSection = .decisions
            model.selectedTab = .council
        case .sessions:
            model.councilSection = .sessions
            model.selectedTab = .council
        case .map:
            model.councilSection = .map
            model.selectedTab = .council
        case .topics: model.selectedTab = .topics
        case .account: model.selectedTab = .account
        case .more: showsMore = true
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
    case account
    case more

    static let phoneCases: [Self] = [.today, .questions, .sessions, .topics, .more]
    static let tabletCases: [Self] = [.today, .questions, .decisions, .sessions, .map, .topics, .more]

    var id: String { label }

    var label: String {
        switch self {
        case .today: "Start"
        case .questions: "Fragen"
        case .decisions: "Beschlüsse"
        case .sessions: "Sitzungen"
        case .map: "Stadtkarte"
        case .topics: "Themen"
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
        case .account: .profile
        case .more: .more
        }
    }
}

private struct RatsSidebarNavigation: View {
    let model: AppModel
    let active: MainNavigationDestination
    let select: (MainNavigationDestination) -> Void
    let openMore: () -> Void

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
                ForEach(MainNavigationDestination.tabletCases) { destination in
                    sidebarButton(destination)
                }
            }
            .padding(.horizontal, 10)

            Spacer(minLength: 14)

            Button { select(.account) } label: {
                HStack(spacing: 10) {
                    Circle()
                        .fill(active == .account ? RatsColor.primary : RatsColor.primary.opacity(0.10))
                        .frame(width: 38, height: 38)
                        .overlay(
                            RatsGlyphView(
                                glyph: .profile,
                                color: active == .account ? RatsColor.primaryText : RatsColor.primary,
                                lineWidth: 1.7
                            )
                            .frame(width: 19, height: 19)
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
        Button {
            if destination == .more { openMore() }
            else { select(destination) }
        } label: {
            HStack(spacing: 11) {
                RatsGlyphView(
                    glyph: destination.glyph,
                    color: active == destination ? RatsColor.primaryText : RatsColor.secondary,
                    lineWidth: active == destination ? 1.95 : 1.7
                )
                .frame(width: 20, height: 20)
                .frame(width: 34, height: 34)
                .background(active == destination ? RatsColor.primary : RatsColor.stage)
                .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
                Text(destination.label)
                    .font(RatsFont.body(13.5, weight: active == destination ? .semibold : .medium))
                    .foregroundStyle(active == destination ? RatsColor.text : RatsColor.bodyText)
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
                            color: active == destination ? RatsColor.primary : RatsColor.secondary,
                            lineWidth: active == destination ? 2.05 : 1.65
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
        case .sharedAnswer:
            if let url = model.router.universalLink(for: route) { ExternalWebView(url: url) }
        case .web(let url): ExternalWebView(url: url)
        default: EmptyView()
        }
    }
}
