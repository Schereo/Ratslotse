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
                RouteDestinationView(model: model, route: route)
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
                .presentationDetents([.large])
        }
        .alert("Ratslotse", isPresented: Binding(
            get: { model.alertMessage != nil },
            set: { if !$0 { model.alertMessage = nil } }
        )) {
            Button("OK", role: .cancel) { model.alertMessage = nil }
        } message: {
            Text(model.alertMessage ?? "")
        }
        .task { await model.bootstrap() }
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
        ContentUnavailableView {
            Label("Update erforderlich", systemImage: "arrow.down.app")
        } description: {
            Text(notice ?? "Diese Version ist zu alt, um verlässlich mit Ratslotse zu arbeiten.")
        } actions: {
            Link("Im App Store aktualisieren", destination: URL(string: "https://apps.apple.com/app/id6786553049")!)
                .buttonStyle(PrimaryButtonStyle())
        }
    }
}

private struct MainTabsView: View {
    @Bindable var model: AppModel

    var body: some View {
        TabView(selection: $model.selectedTab) {
            TodayView(model: model)
                .tabItem { Label("Heute", systemImage: "sun.max") }
                .tag(AppTab.today)
            QuestionsView(model: model)
                .tabItem { Label("Fragen", systemImage: "sparkles") }
                .tag(AppTab.questions)
            CouncilBrowserView(model: model)
                .tabItem { Label("Rat", systemImage: "building.columns") }
                .tag(AppTab.council)
            TopicsView(model: model)
                .tabItem { Label("Themen", systemImage: "bell") }
                .tag(AppTab.topics)
            AccountView(model: model)
                .tabItem { Label("Konto", systemImage: "person.crop.circle") }
                .tag(AppTab.account)
        }
        .tint(RatsColor.primary)
    }
}

private struct RouteDestinationView: View {
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
