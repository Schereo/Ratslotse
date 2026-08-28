import AuthenticationServices
import RatslotseAPI
import RatslotseDesign
import SwiftUI

struct WelcomeView: View {
    let model: AppModel
    @Environment(\.horizontalSizeClass) private var horizontalSizeClass

    var body: some View {
        ScrollView {
            Group {
                if horizontalSizeClass == .regular {
                    HStack(alignment: .center, spacing: 54) {
                        Lotti3DView(scene: .wave)
                            .frame(width: 300, height: 260)
                            .accessibilityHidden(true)
                        welcomeContent
                            .frame(maxWidth: 480, alignment: .leading)
                    }
                    .frame(maxWidth: 960)
                    .padding(.horizontal, 42)
                    .padding(.vertical, 60)
                } else {
                    welcomeContent
                        .frame(maxWidth: 560, alignment: .leading)
                        .padding(28)
                }
            }
            .frame(maxWidth: .infinity)
        }
        .background(RatsColor.page)
    }

    private var welcomeContent: some View {
        VStack(alignment: .leading, spacing: 28) {
            Image("AppIconPreview")
                .resizable()
                .scaledToFit()
                .frame(width: 74, height: 74)
                .clipShape(RoundedRectangle(cornerRadius: 17, style: .continuous))
                .accessibilityHidden(true)
            VStack(alignment: .leading, spacing: 12) {
                MonoKicker("Oldenburgs Rat verstehen")
                Text("Was entscheidet die Stadt?")
                    .font(RatsFont.title(36))
                    .foregroundStyle(RatsColor.text)
                Text("Ratslotse macht Beschlüsse, Sitzungen und deine Themen verständlich – mit den amtlichen Quellen direkt dabei.")
                    .font(RatsFont.body(17))
                    .foregroundStyle(RatsColor.secondary)
                    .lineSpacing(4)
            }
            VStack(spacing: 12) {
                Button { model.authPresentation = .login } label: {
                    Text("Anmelden").frame(maxWidth: .infinity)
                }
                .buttonStyle(PrimaryButtonStyle())
                .frame(maxWidth: .infinity)
                Button { model.authPresentation = .register } label: {
                    Text("Konto anlegen").frame(maxWidth: .infinity)
                }
                .buttonStyle(SecondaryButtonStyle())
                .frame(maxWidth: .infinity)
            }
            Text("Geteilte Beschlüsse und Personenprofile kannst du auch ohne Konto lesen.")
                .font(RatsFont.body(12))
                .foregroundStyle(RatsColor.muted)
        }
    }
}

struct AuthFlowView: View {
    let model: AppModel
    @State private var mode: AuthPresentation

    init(model: AppModel, initial: AuthPresentation) {
        self.model = model
        _mode = State(initialValue: initial)
    }

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                HStack {
                    Text("Ratslotse")
                        .font(RatsFont.title(20))
                        .foregroundStyle(RatsColor.text)
                    Spacer()
                    Button { model.authPresentation = nil } label: {
                        Text("×")
                            .font(RatsFont.body(23, weight: .medium))
                            .foregroundStyle(RatsColor.bodyText)
                            .frame(width: 38, height: 38)
                            .background(RatsColor.card)
                            .overlay(Circle().stroke(RatsColor.border))
                            .clipShape(Circle())
                    }
                    .buttonStyle(AuthCloseButtonStyle())
                    .accessibilityLabel("Anmeldung schließen")
                }
                .padding(.horizontal, 18)
                .padding(.vertical, 11)
                .background(RatsColor.page)
                Divider().overlay(RatsColor.separator)

                Group {
                    switch mode {
                    case .login: CredentialsView(model: model, mode: .login, switchMode: { mode = $0 })
                    case .register: CredentialsView(model: model, mode: .register, switchMode: { mode = $0 })
                    case .forgotPassword: ForgotPasswordView(model: model, switchMode: { mode = $0 })
                    case .resetPassword(let token): ResetPasswordView(model: model, token: token)
                    }
                }
            }
            .toolbar(.hidden, for: .navigationBar)
        }
    }
}

private struct AuthCloseButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .scaleEffect(configuration.isPressed ? 0.94 : 1)
            .opacity(configuration.isPressed ? 0.72 : 1)
            .animation(.easeOut(duration: 0.12), value: configuration.isPressed)
    }
}

private struct CredentialsView: View {
    enum Mode { case login, register }
    let model: AppModel
    let mode: Mode
    let switchMode: (AuthPresentation) -> Void

    @State private var name = ""
    @State private var email = ""
    @State private var password = ""
    @State private var showsPassword = false
    @State private var error: String?
    @State private var isWorking = false

    var body: some View {
        AuthScaffold(
            scene: .wave,
            title: mode == .login ? "Moin!" : "Leinen los!",
            subtitle: mode == .login
                ? "Willkommen zurück – melde dich an, um fortzufahren."
                : "Erstelle dein kostenloses Konto. Danach lotst Lotti dich durch die ersten Schritte."
        ) {
            VStack(spacing: 16) {
                SignInWithAppleButton(mode == .login ? .signIn : .signUp) { request in
                    request.requestedScopes = [.fullName, .email]
                } onCompletion: { result in
                    completeApple(result)
                }
                .signInWithAppleButtonStyle(.black)
                .frame(height: 48)
                .clipShape(RoundedRectangle(cornerRadius: RatsRadius.button))

                AuthDivider()

                if mode == .register {
                    AuthLabeledField(label: "Anzeigename", hint: "optional") {
                        TextField("Dein Vorname genügt", text: $name)
                            .textContentType(.name)
                            .textFieldStyle(.plain)
                    }
                }

                AuthLabeledField(label: "E-Mail") {
                    TextField("du@example.org", text: $email)
                        .textContentType(.emailAddress)
                        .textInputAutocapitalization(.never)
                        .keyboardType(.emailAddress)
                        .textFieldStyle(.plain)
                }

                AuthLabeledField(label: "Passwort", hint: mode == .register ? "mindestens 8 Zeichen" : nil) {
                    HStack {
                        Group {
                            if showsPassword {
                                TextField("Passwort", text: $password)
                            } else {
                                SecureField("Passwort", text: $password)
                            }
                        }
                        .textContentType(mode == .login ? .password : .newPassword)
                        .textFieldStyle(.plain)
                        Button { showsPassword.toggle() } label: {
                            Image(systemName: showsPassword ? "eye.slash" : "eye")
                                .foregroundStyle(RatsColor.secondary)
                        }
                        .accessibilityLabel(showsPassword ? "Passwort ausblenden" : "Passwort anzeigen")
                    }
                }

                if let error {
                    Label(error, systemImage: "exclamationmark.triangle")
                        .font(RatsFont.body(12))
                        .foregroundStyle(RatsColor.danger)
                        .frame(maxWidth: .infinity, alignment: .leading)
                }

                Group {
                    if mode == .login {
                        Button(action: submit) {
                            Text(isWorking ? "Einen Moment …" : "Anmelden").frame(maxWidth: .infinity)
                        }
                            .buttonStyle(PrimaryButtonStyle())
                    } else {
                        Button(action: submit) {
                            Text(isWorking ? "Einen Moment …" : "Konto erstellen").frame(maxWidth: .infinity)
                        }
                            .buttonStyle(SignalButtonStyle())
                    }
                }
                .frame(maxWidth: .infinity)
                .disabled(isWorking || email.isEmpty || password.count < 8)
                .opacity(isWorking || email.isEmpty || password.count < 8 ? 0.5 : 1)

                if mode == .register {
                    Text("Mit der Registrierung akzeptierst du die Datenschutzerklärung. Danach bestätigst du kurz deine E-Mail-Adresse.")
                        .font(RatsFont.body(11))
                        .foregroundStyle(RatsColor.muted)
                        .multilineTextAlignment(.center)
                }

                VStack(spacing: 11) {
                    if mode == .login {
                        Button("Passwort vergessen?") { switchMode(.forgotPassword) }
                        Button("Noch kein Konto? Konto anlegen") { switchMode(.register) }
                    } else {
                        Button("Schon registriert? Anmelden") { switchMode(.login) }
                    }
                }
                .font(RatsFont.body(13, weight: .medium))
                .foregroundStyle(RatsColor.primary)
            }
        }
        .navigationBarTitleDisplayMode(.inline)
    }

    private func submit() {
        isWorking = true
        error = nil
        Task {
            do {
                if mode == .login { try await model.login(email: email, password: password) }
                else { try await model.register(email: email, password: password, displayName: name.isEmpty ? nil : name) }
            } catch { self.error = error.localizedDescription }
            isWorking = false
        }
    }

    private func completeApple(_ result: Result<ASAuthorization, Error>) {
        guard
            case .success(let authorization) = result,
            let credential = authorization.credential as? ASAuthorizationAppleIDCredential,
            let data = credential.identityToken,
            let token = String(data: data, encoding: .utf8)
        else {
            if case .failure(let failure) = result { error = failure.localizedDescription }
            return
        }
        isWorking = true
        Task {
            do {
                try await model.signInWithApple(
                    identityToken: token,
                    givenName: credential.fullName?.givenName,
                    familyName: credential.fullName?.familyName
                )
            } catch { self.error = error.localizedDescription }
            isWorking = false
        }
    }
}

private struct ForgotPasswordView: View {
    let model: AppModel
    let switchMode: (AuthPresentation) -> Void
    @State private var email = ""
    @State private var message: String?

    var body: some View {
        AuthScaffold(
            scene: .questions,
            title: "Passwort über Bord?",
            subtitle: "Gib deine E-Mail-Adresse ein – wir schicken dir einen Link zum Zurücksetzen."
        ) {
            VStack(spacing: 16) {
                AuthLabeledField(label: "E-Mail") {
                    TextField("du@example.org", text: $email)
                        .textContentType(.emailAddress)
                        .keyboardType(.emailAddress)
                        .textInputAutocapitalization(.never)
                        .textFieldStyle(.plain)
                }
                Button {
                    Task {
                        do {
                            try await model.forgotPassword(email: email)
                            message = "Wenn es dieses Konto gibt, ist der Link unterwegs."
                        } catch { message = error.localizedDescription }
                    }
                } label: {
                    Text("Link anfordern").frame(maxWidth: .infinity)
                }
                .buttonStyle(PrimaryButtonStyle())
                .frame(maxWidth: .infinity)
                .disabled(email.isEmpty)
                .opacity(email.isEmpty ? 0.5 : 1)
                if let message {
                    Text(message)
                        .font(RatsFont.body(12))
                        .foregroundStyle(RatsColor.secondary)
                }
                Button("Zurück zur Anmeldung") { switchMode(.login) }
                    .font(RatsFont.body(13, weight: .medium))
            }
        }
    }
}

private struct ResetPasswordView: View {
    let model: AppModel
    let token: String
    @State private var password = ""
    @State private var repeated = ""
    @State private var showsPassword = false
    @State private var error: String?

    var body: some View {
        AuthScaffold(
            scene: .reading,
            title: "Neues Passwort",
            subtitle: "Wähle mindestens acht Zeichen und bestätige die Eingabe einmal."
        ) {
            VStack(spacing: 16) {
                AuthLabeledField(label: "Neues Passwort", hint: "mindestens 8 Zeichen") {
                    HStack {
                        Group {
                            if showsPassword { TextField("Passwort", text: $password) }
                            else { SecureField("Passwort", text: $password) }
                        }
                        .textContentType(.newPassword)
                        .textFieldStyle(.plain)
                        Button { showsPassword.toggle() } label: {
                            Image(systemName: showsPassword ? "eye.slash" : "eye")
                        }
                    }
                }
                AuthLabeledField(label: "Passwort wiederholen") {
                    SecureField("Noch einmal", text: $repeated)
                        .textContentType(.newPassword)
                        .textFieldStyle(.plain)
                }
                if let error { Text(error).font(RatsFont.body(12)).foregroundStyle(RatsColor.danger) }
                Button {
                    guard password == repeated else { error = "Die Passwörter stimmen nicht überein."; return }
                    Task {
                        do { try await model.resetPassword(token: token, password: password) }
                        catch { self.error = error.localizedDescription }
                    }
                } label: {
                    Text("Passwort speichern").frame(maxWidth: .infinity)
                }
                .buttonStyle(PrimaryButtonStyle())
                .frame(maxWidth: .infinity)
                .disabled(password.count < 8 || password != repeated)
                .opacity(password.count < 8 || password != repeated ? 0.5 : 1)
            }
        }
    }
}

struct VerificationPendingView: View {
    let model: AppModel
    let user: User
    @State private var feedback: String?

    var body: some View {
        AuthScaffold(
            scene: .wave,
            title: "Fast an Bord!",
            subtitle: "Bestätige deine E-Mail-Adresse. Sobald der Link geöffnet ist, geht es hier automatisch weiter."
        ) {
            VStack(spacing: 16) {
                Label(user.email, systemImage: "envelope.badge")
                    .font(RatsFont.body(14, weight: .semibold))
                    .foregroundStyle(RatsColor.primary)
                Button {
                    Task {
                        do { try await model.resendVerification(); feedback = "Der Link ist unterwegs." }
                        catch { feedback = error.localizedDescription }
                    }
                } label: {
                    Text("Erneut senden").frame(maxWidth: .infinity)
                }
                .buttonStyle(PrimaryButtonStyle())
                .frame(maxWidth: .infinity)
                Button { Task { await model.refreshAccount() } } label: {
                    Text("Ich habe bestätigt").frame(maxWidth: .infinity)
                }
                    .buttonStyle(SecondaryButtonStyle())
                    .frame(maxWidth: .infinity)
                if let feedback { Text(feedback).font(RatsFont.body(12)).foregroundStyle(RatsColor.secondary) }
                Button("Abmelden", role: .destructive) { Task { await model.logout() } }
            }
        }
        .task(id: user.id) {
            while !Task.isCancelled {
                try? await Task.sleep(for: .seconds(8))
                guard !Task.isCancelled else { return }
                await model.refreshAccount()
                if case .active = model.session { return }
            }
        }
    }
}

private struct AuthScaffold<Content: View>: View {
    let scene: Lotti3DScene
    let title: String
    let subtitle: String
    @ViewBuilder let content: Content
    @Environment(\.horizontalSizeClass) private var horizontalSizeClass

    init(
        scene: Lotti3DScene,
        title: String,
        subtitle: String,
        @ViewBuilder content: () -> Content
    ) {
        self.scene = scene
        self.title = title
        self.subtitle = subtitle
        self.content = content()
    }

    var body: some View {
        ZStack {
            RatsColor.page.ignoresSafeArea()
            AuthWaves()
                .stroke(RatsColor.primary.opacity(0.07), lineWidth: 1.2)
                .ignoresSafeArea()
                .accessibilityHidden(true)
            ScrollView {
                Group {
                    if horizontalSizeClass == .regular {
                        HStack(alignment: .center, spacing: 28) {
                            VStack(alignment: .leading, spacing: 13) {
                                Lotti3DView(scene: scene)
                                    .frame(width: 260, height: 210)
                                    .accessibilityHidden(true)
                                MonoKicker("Sicher an Bord")
                                Text(title).font(RatsFont.title(36, weight: .heavy))
                                Text(subtitle)
                                    .font(RatsFont.body(15))
                                    .foregroundStyle(RatsColor.secondary)
                                    .lineSpacing(4)
                            }
                            .frame(width: 310, alignment: .leading)
                            .padding(24)
                            .background(RatsColor.primary.opacity(0.07))
                            .overlay(RoundedRectangle(cornerRadius: 22).stroke(RatsColor.primary.opacity(0.17)))
                            .clipShape(RoundedRectangle(cornerRadius: 22, style: .continuous))

                            content
                                .frame(maxWidth: .infinity, alignment: .leading)
                                .ratsCard()
                                .frame(width: 420)
                        }
                        .frame(maxWidth: 900)
                        .padding(.horizontal, 28)
                        .padding(.vertical, 30)
                    } else {
                        VStack(spacing: 0) {
                            Lotti3DView(scene: scene)
                                .frame(width: 138, height: 122)
                                .padding(.bottom, -13)
                                .zIndex(1)
                                .accessibilityHidden(true)
                            VStack(alignment: .leading, spacing: 17) {
                                VStack(alignment: .leading, spacing: 8) {
                                    Text(title).font(RatsFont.title(30))
                                    Text(subtitle)
                                        .font(RatsFont.body(14))
                                        .foregroundStyle(RatsColor.secondary)
                                        .lineSpacing(3)
                                }
                                content
                            }
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .ratsCard()
                        }
                        .frame(maxWidth: 460)
                        .padding(.horizontal, 18)
                        .padding(.top, 12)
                        .padding(.bottom, 32)
                    }
                }
                .frame(maxWidth: .infinity)
            }
        }
    }
}

private struct AuthLabeledField<Content: View>: View {
    let label: String
    let hint: String?
    @ViewBuilder let content: Content

    init(label: String, hint: String? = nil, @ViewBuilder content: () -> Content) {
        self.label = label
        self.hint = hint
        self.content = content()
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Text(label)
                Spacer()
                if let hint { Text(hint).foregroundStyle(RatsColor.muted) }
            }
            .font(RatsFont.body(12, weight: .semibold))
            content
                .font(RatsFont.body(15))
                .padding(.horizontal, 12)
                .frame(minHeight: 46)
                .background(RatsColor.card)
                .overlay(RoundedRectangle(cornerRadius: 10).stroke(RatsColor.border))
                .clipShape(RoundedRectangle(cornerRadius: 10))
        }
    }
}

private struct AuthDivider: View {
    var body: some View {
        HStack(spacing: 10) {
            Rectangle().fill(RatsColor.border).frame(height: 1)
            Text("oder mit E-Mail")
                .font(RatsFont.body(11))
                .foregroundStyle(RatsColor.muted)
            Rectangle().fill(RatsColor.border).frame(height: 1)
        }
    }
}

private struct AuthWaves: Shape {
    func path(in rect: CGRect) -> Path {
        var path = Path()
        let rowHeight: CGFloat = 46
        let amplitude: CGFloat = 5
        var y: CGFloat = 14
        while y < rect.maxY + rowHeight {
            path.move(to: CGPoint(x: rect.minX - 20, y: y))
            var x = rect.minX - 20
            while x < rect.maxX + 40 {
                path.addCurve(
                    to: CGPoint(x: x + 42, y: y),
                    control1: CGPoint(x: x + 12, y: y - amplitude),
                    control2: CGPoint(x: x + 29, y: y + amplitude)
                )
                x += 42
            }
            y += rowHeight
        }
        return path
    }
}
