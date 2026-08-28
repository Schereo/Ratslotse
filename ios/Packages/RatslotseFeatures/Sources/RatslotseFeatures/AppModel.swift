import Foundation
import Network
import Observation
import RatslotseAPI
import UIKit
import UserNotifications

public enum SessionState: Sendable, Equatable {
    case loading
    case loggedOut
    case pending(User)
    case active(User)
}

public enum AuthPresentation: Sendable, Equatable, Identifiable {
    case login
    case register
    case forgotPassword
    case resetPassword(token: String)

    public var id: String {
        switch self {
        case .login: "login"
        case .register: "register"
        case .forgotPassword: "forgot"
        case .resetPassword: "reset"
        }
    }
}

enum CouncilSection: String, CaseIterable, Identifiable, Sendable {
    case decisions = "Beschlüsse"
    case sessions = "Sitzungen"
    case map = "Stadtkarte"

    var id: String { rawValue }
}

@MainActor
@Observable
public final class AppModel {
    public let api: APIClient
    public let sse: SSEClient
    public let router: AppRouter

    public var session: SessionState = .loading
    public var selectedTab: AppTab = .today
    var councilSection: CouncilSection = .decisions
    public var navigation: [AppRoute] = []
    public var authPresentation: AuthPresentation?
    public var questionPrefill = ""
    public var isOffline = false
    public var updateRequired = false
    public var updateNotice: String?
    public var alertMessage: String?
    public var hasRecoverableResearch = false
    public var onboardingStep: Int?

    private let network = NetworkMonitor()
    private let defaults: UserDefaults
    private var pendingPushToken: String?

    private static let onboardingDoneKey = "ratslotse.onboarding.done"
    private static let onboardingStepKey = "ratslotse.onboarding.step"
    private static let legacyIntroKey = "ratslotse.intro.done"
    private static let pushPrimerSnoozeKey = "ratslotse.push-primer.snoozed-until"

    public init(
        api: APIClient = APIClient(),
        sse: SSEClient = SSEClient(),
        router: AppRouter = AppRouter(),
        defaults: UserDefaults = .standard
    ) {
        self.api = api
        self.sse = sse
        self.router = router
        self.defaults = defaults
        if defaults.object(forKey: Self.onboardingDoneKey) != nil
            || defaults.object(forKey: Self.legacyIntroKey) != nil {
            onboardingStep = nil
        } else {
            onboardingStep = min(3, max(0, defaults.integer(forKey: Self.onboardingStepKey)))
        }
        network.onStatusChange = { [weak self] available in
            Task { @MainActor in self?.isOffline = !available }
        }
        network.start()
    }

    public var user: User? {
        switch session {
        case .pending(let user), .active(let user): user
        default: nil
        }
    }

    public func bootstrap() async {
        do {
            let config: AppConfiguration = try await api.get("/api/app-config")
            updateNotice = config.notice
            let build = Int(Bundle.main.object(forInfoDictionaryKey: "CFBundleVersion") as? String ?? "0") ?? 0
            if config.minBuild > build {
                updateRequired = true
                session = .loggedOut
                return
            }
        } catch {
            // Compatibility config is a safeguard, never a launch dependency.
        }

        guard await api.restoreAccessToken() != nil else {
            session = .loggedOut
            return
        }
        do {
            let me: User = try await api.get("/api/auth/me")
            try await accept(user: me)
        } catch let error as APIError where error.isUnauthorized {
            try? await api.setAccessToken(nil)
            session = .loggedOut
        } catch {
            // An offline start keeps the token. The shell remains usable and
            // retries bootstrap as soon as the user pulls to refresh.
            session = .loggedOut
            if !isOffline { alertMessage = error.localizedDescription }
        }
    }

    public func login(email: String, password: String) async throws {
        struct Body: Codable, Sendable { let email: String; let password: String }
        let user: User = try await api.send(
            "/api/auth/login", body: Body(email: email, password: password)
        )
        try await accept(user: user)
        authPresentation = nil
    }

    public func register(email: String, password: String, displayName: String?) async throws {
        struct Body: Codable, Sendable {
            let email: String
            let password: String
            let display_name: String?
        }
        let user: User = try await api.send(
            "/api/auth/register",
            body: Body(email: email, password: password, display_name: displayName)
        )
        try await accept(user: user)
        authPresentation = nil
    }

    public func signInWithApple(
        identityToken: String,
        givenName: String?,
        familyName: String?
    ) async throws {
        struct Body: Codable, Sendable {
            let identity_token: String
            let given_name: String?
            let family_name: String?
        }
        let user: User = try await api.send(
            "/api/auth/apple",
            body: Body(identity_token: identityToken, given_name: givenName, family_name: familyName)
        )
        try await accept(user: user)
        authPresentation = nil
    }

    public func forgotPassword(email: String) async throws {
        struct Body: Codable, Sendable { let email: String }
        struct Response: Codable, Sendable { let ok: Bool }
        let _: Response = try await api.send("/api/auth/forgot-password", body: Body(email: email))
    }

    public func resetPassword(token: String, password: String) async throws {
        struct Body: Codable, Sendable { let token: String; let new_password: String }
        let user: User = try await api.send(
            "/api/auth/reset-password", body: Body(token: token, new_password: password)
        )
        try await accept(user: user)
        authPresentation = nil
    }

    public func verifyEmail(token: String) async {
        struct Body: Codable, Sendable { let token: String }
        do {
            let user: User = try await api.send("/api/auth/verify-email", body: Body(token: token))
            try await accept(user: user)
            alertMessage = "Deine E-Mail-Adresse ist bestätigt."
        } catch {
            alertMessage = error.localizedDescription
            authPresentation = .login
        }
    }

    public func resendVerification() async throws {
        struct Response: Codable, Sendable { let ok: Bool }
        let _: Response = try await api.sendWithoutBody("/api/auth/resend-verification")
    }

    public func refreshAccount() async {
        do {
            let me: User = try await api.get("/api/auth/me")
            try await accept(user: me)
        } catch let error as APIError where error.isUnauthorized {
            try? await api.setAccessToken(nil)
            session = .loggedOut
        } catch {
            alertMessage = error.localizedDescription
        }
    }

    public func adopt(user: User) async throws {
        try await accept(user: user)
    }

    public func logout() async {
        if let token = pendingPushToken {
            struct Body: Codable, Sendable { let token: String }
            try? await api.sendVoid("/api/push/unregister", body: Body(token: token))
        }
        try? await api.sendVoid("/api/auth/logout")
        try? await api.setAccessToken(nil)
        pendingPushToken = nil
        navigation.removeAll()
        session = .loggedOut
    }

    public func handle(url: URL) {
        guard let route = router.route(for: url) else { return }
        handle(route: route)
    }

    public func handle(pushPath: String) {
        guard pushPath.hasPrefix("/"), let route = router.route(forPath: pushPath) else { return }
        handle(route: route)
    }

    public func handle(route: AppRoute) {
        switch route {
        case .tab(let tab):
            selectedTab = tab
            if tab == .council { councilSection = .decisions }
            navigation.removeAll()
        case .question(let prefill, _):
            selectedTab = .questions
            questionPrefill = prefill ?? ""
            navigation.removeAll()
        case .verifyEmail(let token):
            Task { await verifyEmail(token: token) }
        case .resetPassword(let token): authPresentation = .resetPassword(token: token)
        case .web(let url): UIApplication.shared.open(url)
        case .sessions:
            selectedTab = .council
            councilSection = .sessions
            navigation = [route]
        default:
            selectedTab = tab(for: route)
            navigation = [route]
        }
    }

    public func registerPushToken(_ token: String) async {
        pendingPushToken = token
        guard case .active = session else { return }
        struct Body: Codable, Sendable { let token: String; let platform: String }
        try? await api.sendVoid("/api/push/register", body: Body(token: token, platform: "ios"))
    }

    public func requestPushPermission() async -> Bool {
        do {
            let granted = try await UNUserNotificationCenter.current().requestAuthorization(
                options: [.alert, .badge, .sound]
            )
            if granted { UIApplication.shared.registerForRemoteNotifications() }
            return granted
        } catch { return false }
    }

    public func beginOnboarding(with presentation: AuthPresentation = .register) {
        persistOnboarding(step: 1)
        guard user?.isActive != true else { return }
        authPresentation = presentation
    }

    public func advanceOnboarding(to step: Int) async {
        let next = min(3, max(1, step))
        persistOnboarding(step: next)
        await reportOnboarding(step: next)
    }

    public func completeOnboarding() async {
        defaults.set(true, forKey: Self.onboardingDoneKey)
        defaults.set(true, forKey: Self.legacyIntroKey)
        defaults.removeObject(forKey: Self.onboardingStepKey)
        // The regular reminder on "Heute" should not ask again immediately
        // after this flow has already offered the system permission dialog.
        defaults.set(
            Date().addingTimeInterval(7 * 24 * 60 * 60).timeIntervalSince1970 * 1000,
            forKey: Self.pushPrimerSnoozeKey
        )
        onboardingStep = nil
        await reportOnboarding(step: 3, done: true)
    }

    public func restartOnboarding() {
        defaults.removeObject(forKey: Self.onboardingDoneKey)
        defaults.removeObject(forKey: Self.legacyIntroKey)
        persistOnboarding(step: 0)
    }

    private func accept(user: User) async throws {
        var tokenPersistenceFailed = false
        if let token = user.accessToken {
            do {
                try await api.setAccessToken(token)
            } catch {
                // APIClient setzt den Token vor dem Keychain-Schreibversuch
                // bereits für die laufende Sitzung. Ein lokaler
                // Keychain-Ausfall darf deshalb einen erfolgreichen
                // Server-Login nicht in einen Loginfehler verwandeln.
                tokenPersistenceFailed = true
            }
        }
        if user.isActive { await synchronizeOnboarding() }
        session = user.isActive ? .active(user) : .pending(user)
        if tokenPersistenceFailed {
            alertMessage = "Du bist angemeldet. Die Sitzung konnte auf diesem Gerät jedoch nicht dauerhaft gespeichert werden."
        }
        if user.isActive {
            let settings = await UNUserNotificationCenter.current().notificationSettings()
            if settings.authorizationStatus == .authorized {
                UIApplication.shared.registerForRemoteNotifications()
            }
            if let pendingPushToken { await registerPushToken(pendingPushToken) }
            if let current: JSONValue = try? await api.get("/api/council/deep-research/aktuell") {
                hasRecoverableResearch = current.object?["job"] != .null && current.object?["job"] != nil
            }
        }
    }

    private func persistOnboarding(step: Int) {
        onboardingStep = step
        defaults.set(step, forKey: Self.onboardingStepKey)
    }

    private func reportOnboarding(step: Int, done: Bool = false) async {
        struct Body: Codable, Sendable { let step: Int; let done: Bool }
        let _: SetupProgress? = try? await api.send(
            "/api/onboarding/setup", body: Body(step: step, done: done)
        )
    }

    private func synchronizeOnboarding() async {
        guard let localStep = onboardingStep,
              let remote: SetupProgress = try? await api.get("/api/onboarding/setup")
        else { return }
        if remote.doneAt != nil {
            defaults.set(true, forKey: Self.onboardingDoneKey)
            defaults.set(true, forKey: Self.legacyIntroKey)
            defaults.removeObject(forKey: Self.onboardingStepKey)
            onboardingStep = nil
        } else if remote.step > localStep {
            persistOnboarding(step: min(3, remote.step))
        } else if localStep > remote.step {
            await reportOnboarding(step: localStep)
        }
    }

    private func tab(for route: AppRoute) -> AppTab {
        switch route {
        case .decision, .sessions, .person, .topic, .place: .council
        case .quiz: .today
        default: selectedTab
        }
    }
}

private final class NetworkMonitor: @unchecked Sendable {
    private let monitor = NWPathMonitor()
    private let queue = DispatchQueue(label: "de.ratslotse.network")
    var onStatusChange: (@Sendable (Bool) -> Void)?

    func start() {
        monitor.pathUpdateHandler = { [weak self] path in
            self?.onStatusChange?(path.status == .satisfied)
        }
        monitor.start(queue: queue)
    }

    deinit { monitor.cancel() }
}
