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
            if ProcessInfo.processInfo.environment["RATSLOTSE_DEBUG_AUTH"] == "login" {
                model.authPresentation = .login
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

    init(model: AppModel, @ViewBuilder content: () -> Content) {
        self.model = model
        self.content = content()
    }

    var body: some View {
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
        VStack(spacing: 18) {
            Image("Splash")
                .resizable()
                .scaledToFit()
                .frame(width: 150, height: 150)
                .accessibilityHidden(true)
            ProgressView("Ratslotse wird vorbereitet …")
                .tint(RatsColor.primary)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

private struct UpdateRequiredView: View {
    let notice: String?

    var body: some View {
        ZStack {
            RatsColor.page.ignoresSafeArea()
            VStack(spacing: 0) {
                LottiMascot(pose: .point)
                    .frame(width: 112, height: 112)
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
    @State private var showsMore = ProcessInfo.processInfo.environment["RATSLOTSE_DEBUG_MORE"] == "1"

    var body: some View {
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
        .safeAreaInset(edge: .bottom, spacing: 0) {
            RatsBottomNavigation(
                active: activeDestination,
                select: select,
                openMore: { showsMore = true }
            )
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

    private var activeDestination: MainNavigationDestination {
        switch model.selectedTab {
        case .today: .today
        case .questions: .questions
        case .council: model.councilSection == .sessions ? .sessions : .more
        case .topics: .topics
        case .account: .more
        }
    }

    private func select(_ destination: MainNavigationDestination) {
        model.navigation.removeAll()
        switch destination {
        case .today: model.selectedTab = .today
        case .questions: model.selectedTab = .questions
        case .sessions:
            model.councilSection = .sessions
            model.selectedTab = .council
        case .topics: model.selectedTab = .topics
        case .more: showsMore = true
        }
    }
}

private enum MainNavigationDestination: CaseIterable, Identifiable {
    case today
    case questions
    case sessions
    case topics
    case more

    var id: String { label }

    var label: String {
        switch self {
        case .today: "Start"
        case .questions: "Fragen"
        case .sessions: "Sitzungen"
        case .topics: "Themen"
        case .more: "Mehr"
        }
    }

    var glyph: RatsGlyph {
        switch self {
        case .today: .home
        case .questions: .ask
        case .sessions: .calendar
        case .topics: .topics
        case .more: .more
        }
    }
}

private struct RatsBottomNavigation: View {
    let active: MainNavigationDestination
    let select: (MainNavigationDestination) -> Void
    let openMore: () -> Void

    var body: some View {
        HStack(spacing: 2) {
            ForEach(MainNavigationDestination.allCases) { destination in
                Button {
                    if destination == .more { openMore() }
                    else { select(destination) }
                } label: {
                    VStack(spacing: 3) {
                        ZStack {
                            if active == destination {
                                Capsule()
                                    .fill(RatsColor.primary.opacity(0.10))
                                    .frame(width: 43, height: 27)
                                    .overlay(
                                        Capsule()
                                            .stroke(RatsColor.primary.opacity(0.12), lineWidth: 0.75)
                                    )
                            }
                            RatsGlyphView(
                                glyph: destination.glyph,
                                color: active == destination ? RatsColor.primary : RatsColor.secondary,
                                lineWidth: active == destination ? 1.95 : 1.7
                            )
                            .frame(width: 20, height: 20)
                        }
                        .frame(height: 27)

                        Text(destination.label)
                            .font(RatsFont.body(9.5, weight: active == destination ? .semibold : .medium))
                            .foregroundStyle(active == destination ? RatsColor.primary : RatsColor.secondary)
                            .lineLimit(1)
                    }
                    .frame(maxWidth: .infinity, minHeight: 51)
                    .contentShape(Rectangle())
                }
                .buttonStyle(RatsNavigationButtonStyle())
                .accessibilityLabel(destination.label)
                .accessibilityAddTraits(active == destination ? .isSelected : [])
            }
        }
        .padding(.horizontal, 8)
        .padding(.top, 5)
        .padding(.bottom, 2)
        .background(.ultraThinMaterial)
        .overlay(alignment: .top) {
            Rectangle()
                .fill(RatsColor.border.opacity(0.72))
                .frame(height: 0.75)
        }
        .shadow(color: .black.opacity(0.06), radius: 12, y: -4)
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
