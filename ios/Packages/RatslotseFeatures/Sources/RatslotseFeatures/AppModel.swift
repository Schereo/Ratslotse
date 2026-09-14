import Foundation
import Network
import Observation
import RatslotseAPI
import UIKit
import UserNotifications

public enum SessionState: Sendable, Equatable {
    case loading
    case loggedOut
    /// Wartet auf die eigene E-Mail-Bestätigung.
    case pending(User)
    /// Von einem Admin abgeschaltet. Eigener Fall, weil die App sonst zum
    /// Bestätigen einer längst bestätigten Adresse auffordert.
    case disabled(User)
    case active(User)
}

public enum AuthPresentation: Sendable, Equatable, Identifiable {
    case login
    case register
    case forgotPassword
    case resetPassword(token: String)
    /// Der Nachtrag nach „Mit Apple anmelden": Apple liefert den Namen nur bei
    /// der allerersten Autorisierung und nur, wenn man ihn nicht verbirgt —
    /// das Pflichtfeld der Registrierung erreicht diese Konten also nie.
    /// Steht hier und nicht als eigener Schirm, weil es dieselbe Bühne ist:
    /// Man ist gerade angekommen und noch nicht durch.
    case displayName

    public var id: String {
        switch self {
        case .login: "login"
        case .register: "register"
        case .forgotPassword: "forgot"
        case .resetPassword: "reset"
        case .displayName: "name"
        }
    }
}

public enum AppAppearance: String, CaseIterable, Sendable, Identifiable {
    case system
    case light
    case dark

    public var id: String { rawValue }
}

enum CouncilSection: String, CaseIterable, Identifiable, Sendable {
    case decisions = "Beschlüsse"
    case sessions = "Sitzungen"
    case map = "Stadtkarte"

    var id: String { rawValue }
}

struct LocationFilter: Equatable, Sendable {
    let slug: String
    let name: String
}

enum TabletPage: String, Sendable, Equatable {
    case analysis
    case subscriptions
    case saved
    case quiz
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
    var tabletPage: TabletPage?
    public var navigation: [AppRoute] = []
    /// Eingeschaltete Feature-Schalter aus `/api/app-config`. Ein Schalter
    /// sagt, ob etwas schon so weit ist — keine Rechteprüfung (kern/features.py).
    public var features: Set<String> = []
    public func feature(_ key: String) -> Bool { features.contains(key) }
    /// Ein Beschlussort von der Stadtkarte (Ebene „Themen-Orte"), den die
    /// Beschluss-Suche als Filter übernehmen soll — wie `punktHref` im Web,
    /// das auf `/council?location=…` zeigt. Die Suche liest ihn beim Erscheinen
    /// und setzt ihn zurück.
    var pendingLocationFilter: LocationFilter?
    public var authPresentation: AuthPresentation?
    public var questionPrefill = ""
    /// Eine Frage, die auf der Heute-Seite getippt und abgeschickt wurde:
    /// „Frag den Rat“ stellt sie beim Öffnen sofort, statt sie nur ins Feld
    /// zu legen (Tim, 09.09.2026 — vorher wechselte ein Tipp in die Kachel
    /// nur die Ansicht).
    public var pendingQuestion: String?
    public var questionShareToken: String?
    public var isOffline = false
    public var updateRequired = false
    public var updateNotice: String?
    public var alertMessage: String?
    /// Zählt bestätigte Kartenaktionen (Merken aus dem Kontextmenü) — der
    /// Auslöser für das Erfolgs-Feedback in der Hand.
    public var actionFeedback = 0
    public var hasRecoverableResearch = false
    public var onboardingStep: Int?
    public var badgeSnapshot: BadgeSnapshot?
    public var badgeCelebration: EarnedBadge?
    public var appearance: AppAppearance
    public var activeConversationID: Int?

    private let network = NetworkMonitor()
    private let defaults: UserDefaults
    private var pendingPushToken: String?
    private var conversationSavingPreferenceOverride: Int?
    private var badgeCelebrationQueue: [EarnedBadge] = []

    private static let onboardingDoneKey = "ratslotse.onboarding.done"
    private static let onboardingStepKey = "ratslotse.onboarding.step"
    private static let legacyIntroKey = "ratslotse.intro.done"
    private static let pushPrimerSnoozeKey = "ratslotse.push-primer.snoozed-until"
    private static let appearanceKey = "ratslotse.appearance"
    private static let activeConversationKeyPrefix = "ratslotse.qa.active-conversation."
    private static let cachedUserKey = "ratslotse.account.offline-user"

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
        appearance = AppAppearance(rawValue: defaults.string(forKey: Self.appearanceKey) ?? "") ?? .system
        activeConversationID = nil
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

    public func setAppearance(_ appearance: AppAppearance) {
        self.appearance = appearance
        defaults.set(appearance.rawValue, forKey: Self.appearanceKey)
    }

    var conversationSavingPreference: Int? {
        conversationSavingPreferenceOverride ?? user?.savesConversations
    }

    public func bootstrap() async {
        let hasStoredToken = await api.restoreAccessToken() != nil
        let offlineUser = hasStoredToken ? cachedUserForOffline() : nil
        // Render the last verified shell immediately. Configuration and
        // account refresh continue below without holding the launch screen.
        if let offlineUser { applyLocalUser(offlineUser) }

        do {
            let config: AppConfiguration = try await api.get("/api/app-config")
            updateNotice = config.notice
            features = Set(config.features)
            let build = Int(Bundle.main.object(forInfoDictionaryKey: "CFBundleVersion") as? String ?? "0") ?? 0
            if config.minBuild > build {
                updateRequired = true
                session = .loggedOut
                return
            }
        } catch {
            // Compatibility config is a safeguard, never a launch dependency.
        }

        guard hasStoredToken else {
            session = .loggedOut
            return
        }
        do {
            let me: User = try await api.get("/api/auth/me")
            try await accept(user: me)
        } catch let error as APIError where error.isUnauthorized {
            try? await api.setAccessToken(nil)
            defaults.removeObject(forKey: Self.cachedUserKey)
            session = .loggedOut
        } catch {
            // Keep the last verified local account active while the server is
            // unreachable. The access token itself remains exclusively in the
            // Keychain and a real 401 still logs the account out above.
            if let offlineUser {
                applyLocalUser(offlineUser)
            } else {
                session = .loggedOut
                if !isOffline { alertMessage = error.localizedDescription }
            }
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
        // Ohne Namen ist die Anmeldung noch nicht fertig: Der Name ist seit
        // 09/2026 Pflicht, und dieser Weg führt an dem Formular vorbei, das
        // ihn verlangt. Ein Apple-Konto OHNE Namen ist dabei praktisch immer
        // ein frisch entstandenes — der Alt-Bestand trägt einen.
        authPresentation = (user.displayName ?? "").trimmingCharacters(in: .whitespaces).isEmpty
            ? .displayName
            : nil
    }

    /// Anzeigename setzen. Eine Stelle für beide Aufrufer (Konto-Seite und der
    /// Nachtrag nach der Apple-Anmeldung) — der Endpunkt weist einen leeren
    /// Namen ab, also wird hier gar nicht erst einer geschickt.
    public func setDisplayName(_ name: String) async throws {
        struct Body: Codable, Sendable { let display_name: String }
        let sauber = name.trimmingCharacters(in: .whitespaces)
        guard !sauber.isEmpty else { return }
        let _: JSONValue = try await api.send(
            "/api/account/display-name", body: Body(display_name: sauber)
        )
        await refreshAccount()
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

    /// Einen Adresswechsel anstoßen. Bestätigt wird mit dem Passwort oder —
    /// bei Apple-Konten ohne eigenes Passwort — mit einem frischen
    /// Apple-Identity-Token. Bis der Link in der neuen Mailbox geklickt ist,
    /// ändert sich nichts; `user.pendingEmail` trägt so lange das Ziel.
    public func changeEmail(newEmail: String, password: String = "",
                            appleIdentityToken: String = "") async throws {
        struct Body: Codable, Sendable {
            let new_email: String
            let current_password: String
            let apple_identity_token: String
        }
        let user: User = try await api.send(
            "/api/account/change-email",
            body: Body(new_email: newEmail, current_password: password,
                       apple_identity_token: appleIdentityToken)
        )
        try await accept(user: user)
    }

    /// Einen schwebenden Adresswechsel verwerfen — der Link wird ungültig.
    public func cancelEmailChange() async throws {
        let user: User = try await api.sendWithoutBody("/api/account/change-email", method: .delete)
        try await accept(user: user)
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
            defaults.removeObject(forKey: Self.cachedUserKey)
            session = .loggedOut
        } catch {
            if user == nil && !isOffline { alertMessage = error.localizedDescription }
        }
    }

    func setConversationSaving(_ enabled: Bool) async throws {
        struct Body: Codable, Sendable { let an: Bool }
        struct Response: Codable, Sendable {
            let setting: Int

            enum CodingKeys: String, CodingKey {
                case setting = "saves_conversations"
            }
        }

        let response: Response = try await api.send(
            "/api/council/conversations/setting",
            body: Body(an: enabled)
        )
        conversationSavingPreferenceOverride = response.setting
        if !enabled { setActiveConversationID(nil) }
    }

    public func setActiveConversationID(_ id: Int?) {
        activeConversationID = id
        guard let user else { return }
        let key = Self.activeConversationKeyPrefix + String(user.id)
        if let id { defaults.set(id, forKey: key) }
        else { defaults.removeObject(forKey: key) }
    }

    public func refreshBadges(celebrate: Bool = true) async {
        guard user?.isActive == true else { return }
        do {
            let snapshot: BadgeSnapshot = try await api.get("/api/badges")
            badgeSnapshot = snapshot
            guard celebrate else { return }
            let queued = Set(badgeCelebrationQueue.map(\.id) + [badgeCelebration?.id].compactMap { $0 })
            badgeCelebrationQueue.append(contentsOf: snapshot.newlyEarned.filter { !queued.contains($0.id) })
            showNextBadgeCelebrationIfNeeded()
        } catch {
            // Abzeichen sind eine motivierende Zusatzfunktion. Ein Fehler darf
            // Anmeldung, Navigation oder die eigentliche Aktion nie blockieren.
        }
    }

    public func reportBadgeEvent(_ type: String, key: String? = nil) async {
        struct Body: Codable, Sendable { let type: String; let key: String? }
        do {
            try await api.sendVoid("/api/badges/event", body: Body(type: type, key: key))
            await refreshBadges()
        } catch {
            // Fire-and-forget wie im Web: Die Nutzerhandlung bleibt maßgeblich.
        }
    }

    public func markExplorationStep(_ step: String) async {
        struct Body: Codable, Sendable { let steps: [String]; let celebrated: Bool? }
        guard let current: JSONValue = try? await api.get("/api/onboarding") else { return }
        var steps = current.object?["steps"]?.array?.compactMap(\.string) ?? []
        guard !steps.contains(step) else {
            await refreshBadges()
            return
        }
        steps.append(step)
        let _: JSONValue? = try? await api.send(
            "/api/onboarding", body: Body(steps: steps, celebrated: nil)
        )
        await refreshBadges()
    }

    public func dismissBadgeCelebration() {
        badgeCelebration = nil
        showNextBadgeCelebrationIfNeeded()
    }

    private func showNextBadgeCelebrationIfNeeded() {
        guard badgeCelebration == nil, !badgeCelebrationQueue.isEmpty else { return }
        badgeCelebration = badgeCelebrationQueue.removeFirst()
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
        conversationSavingPreferenceOverride = nil
        badgeSnapshot = nil
        badgeCelebration = nil
        badgeCelebrationQueue.removeAll()
        activeConversationID = nil
        tabletPage = nil
        navigation.removeAll()
        defaults.removeObject(forKey: Self.cachedUserKey)
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
        tabletPage = nil
        switch route {
        case .tab(let tab):
            selectedTab = tab
            if tab == .council { councilSection = .decisions }
            navigation.removeAll()
        case .question(let prefill, let share):
            selectedTab = .questions
            questionPrefill = prefill ?? ""
            questionShareToken = share
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
        await refreshBadges()
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
        await reportBadgeEvent("tour")
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
        applyLocalUser(user)
        cacheUserForOffline(user)
        if tokenPersistenceFailed {
            alertMessage = "Du bist angemeldet. Die Sitzung konnte auf diesem Gerät jedoch nicht dauerhaft gespeichert werden."
        }
        if user.isActive {
            let settings = await UNUserNotificationCenter.current().notificationSettings()
            if settings.authorizationStatus == .authorized {
                UIApplication.shared.registerForRemoteNotifications()
            }
            if let pendingPushToken { await registerPushToken(pendingPushToken) }
            if let current: JSONValue = try? await api.get("/api/council/deep-research/current") {
                hasRecoverableResearch = current.object?["job"] != .null && current.object?["job"] != nil
            }
            await refreshBadges()
        }
    }

    private func applyLocalUser(_ user: User) {
        conversationSavingPreferenceOverride = nil
        let conversationKey = Self.activeConversationKeyPrefix + String(user.id)
        if user.savesConversations == 1,
           defaults.object(forKey: conversationKey) != nil {
            activeConversationID = defaults.integer(forKey: conversationKey)
        } else {
            activeConversationID = nil
            if user.savesConversations == 0 {
                defaults.removeObject(forKey: conversationKey)
            }
        }
        session = user.isActive ? .active(user) : (user.isDisabled ? .disabled(user) : .pending(user))
    }

    func cacheUserForOffline(_ user: User) {
        guard let encoded = try? JSONEncoder().encode(user),
              var object = try? JSONSerialization.jsonObject(with: encoded) as? [String: Any]
        else { return }
        // Never duplicate the bearer token outside the Keychain.
        object["access_token"] = NSNull()
        guard let safeData = try? JSONSerialization.data(withJSONObject: object) else { return }
        defaults.set(safeData, forKey: Self.cachedUserKey)
    }

    func cachedUserForOffline() -> User? {
        guard let data = defaults.data(forKey: Self.cachedUserKey) else { return nil }
        return try? JSONDecoder().decode(User.self, from: data)
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
        case .quiz, .subscriptions: .today
        case .analysis: .council
        case .admin: .account
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
