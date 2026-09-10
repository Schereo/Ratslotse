import AuthenticationServices
import RatslotseAPI
import RatslotseDesign
import SwiftUI

struct WelcomeView: View {
    let model: AppModel
    @Environment(\.horizontalSizeClass) private var horizontalSizeClass

    var body: some View {
        GeometryReader { proxy in
        ScrollView {
            Group {
                // 300 + 54 + 480 + 2×42 = 918 pt. Ein iPad Pro 11" hat im
                // Hochformat 834 — dort blieb für die Textspalte so wenig,
                // dass die Überschrift „Was entscheidet die Stadt?" zu „Was
                // entscheidet die…" abgeschnitten wurde. Die gemessene Breite
                // entscheidet deshalb mit, nicht die Größenklasse allein.
                if horizontalSizeClass == .regular && proxy.size.width >= 918 {
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
            .frame(minHeight: proxy.size.height)
        }
        .background(RatsColor.page)
        }
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
                    // Umbrechen statt abschneiden, falls die Spalte doch
                    // einmal schmaler ausfällt als die Überschrift breit ist.
                    .fixedSize(horizontal: false, vertical: true)
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
            VStack(alignment: .leading, spacing: 7) {
                Text("Geteilte Beschlüsse und Personenprofile kannst du auch ohne Konto lesen.")
                Text("Ratslotse ist ein privates Bürgerprojekt und kein Angebot der Stadt Oldenburg.")
                    .fontWeight(.semibold)
            }
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
                    // Kein Ausgang, solange der Name fehlt: Der Nachtrag hat
                    // genau einen Weg nach vorn, sonst stünde das Konto doch
                    // wieder namenlos da.
                    if mode != .displayName {
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
                    case .displayName: DisplayNameGateView(model: model)
                    }
                }
            }
            .interactiveDismissDisabled(mode == .displayName)
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
                    // Pflicht seit 09/2026 (Tims Entscheidung): Ohne Namen
                    // fiel jede Anrede still auf „Moin!" zurück, und im
                    // Admin-Panel war ein Konto nur eine Adresse.
                    AuthLabeledField(label: "Anzeigename") {
                        TextField("Dein Vorname genügt", text: $name)
                            .textContentType(.name)
                            .textFieldStyle(.plain)
                    }
                }

                AuthLabeledField(label: "E-Mail") {
                    TextField(
                        "",
                        text: $email,
                        prompt: Text("E-Mail-Adresse").foregroundStyle(RatsColor.muted)
                    )
                        .foregroundStyle(RatsColor.text)
                        .textContentType(.emailAddress)
                        .textInputAutocapitalization(.never)
                        .keyboardType(.emailAddress)
                        .textFieldStyle(.plain)
                        .accessibilityLabel("E-Mail")
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
                            RatsIcon(showsPassword ? .eyeOff : .eye, size: 16)
                                .foregroundStyle(RatsColor.secondary)
                        }
                        .accessibilityLabel(showsPassword ? "Passwort ausblenden" : "Passwort anzeigen")
                    }
                }

                if let error {
                    RatsLabel(error, .triangleAlert)
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
                .disabled(isWorking || unvollstaendig)
                .opacity(isWorking || unvollstaendig ? 0.5 : 1)

                if mode == .register {
                    VStack(spacing: 6) {
                        Text("Mit der Registrierung akzeptierst du die Datenschutzerklärung. Danach bestätigst du kurz deine E-Mail-Adresse.")
                        Link("Datenschutz öffnen", destination: URL(string: "https://ratslotse.de/datenschutz")!)
                            .foregroundStyle(RatsColor.primary)
                    }
                    .font(RatsFont.body(11))
                    .foregroundStyle(RatsColor.muted)
                    .multilineTextAlignment(.center)
                }

                Text("Privates Bürgerprojekt · kein Angebot der Stadt Oldenburg")
                    .font(RatsFont.body(10.5, weight: .semibold))
                    .foregroundStyle(RatsColor.muted)
                    .multilineTextAlignment(.center)

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

    /// Fehlt noch etwas? Beim Registrieren gehört der Name dazu — der Server
    /// weist ein leeres Feld ab, der Knopf muss das also vorher wissen.
    private var unvollstaendig: Bool {
        if email.isEmpty || password.count < 8 { return true }
        return mode == .register && name.trimmingCharacters(in: .whitespaces).isEmpty
    }

    private func submit() {
        isWorking = true
        error = nil
        Task {
            do {
                if mode == .login { try await model.login(email: email, password: password) }
                else { try await model.register(email: email, password: password, displayName: name.trimmingCharacters(in: .whitespaces)) }
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

/// „Wie sollen wir dich nennen?" — der Nachtrag nach einer Apple-Anmeldung.
///
/// Apple liefert den Namen **nur bei der allerersten Autorisierung**, und auch
/// dann nur, wenn man ihn nicht verbirgt. Das Pflichtfeld im Registrierungs-
/// formular erreicht diese Konten also nie; gefragt wird deshalb hier, direkt
/// nachdem die Anmeldung durch ist. Am 10.09.2026 gemessen: Auf Prod trägt
/// jedes bestehende Apple-Konto einen Namen — „Apple-Konto ohne Namen" heißt
/// also „gerade eben entstanden", der Alt-Bestand wird nicht behelligt.
///
/// Ohne Ausgang: kein „Überspringen", kein × in der Kopfzeile, kein Wegwischen
/// (`interactiveDismissDisabled` in `AuthFlowView`).
private struct DisplayNameGateView: View {
    let model: AppModel
    @State private var name = ""
    @State private var error: String?
    @State private var isWorking = false

    private var leer: Bool { name.trimmingCharacters(in: .whitespaces).isEmpty }

    var body: some View {
        AuthScaffold(
            scene: .wave,
            title: "Wie sollen wir dich nennen?",
            subtitle: "Apple gibt uns deinen Namen nicht mit. Er steht in der Anrede auf „Heute“ und in deinen E-Mails – dein Vorname genügt."
        ) {
            VStack(spacing: 16) {
                AuthLabeledField(label: "Anzeigename") {
                    TextField("Dein Vorname genügt", text: $name)
                        .textContentType(.name)
                        .textFieldStyle(.plain)
                }

                if let error {
                    RatsLabel(error, .triangleAlert)
                        .font(RatsFont.body(12))
                        .foregroundStyle(RatsColor.danger)
                        .frame(maxWidth: .infinity, alignment: .leading)
                }

                Button(action: submit) {
                    Text(isWorking ? "Einen Moment …" : "Weiter").frame(maxWidth: .infinity)
                }
                .buttonStyle(SignalButtonStyle())
                .frame(maxWidth: .infinity)
                .disabled(isWorking || leer)
                .opacity(isWorking || leer ? 0.5 : 1)
            }
        }
        .navigationBarTitleDisplayMode(.inline)
    }

    private func submit() {
        isWorking = true
        error = nil
        Task {
            do {
                try await model.setDisplayName(name)
                model.authPresentation = nil
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
                    TextField(
                        "",
                        text: $email,
                        prompt: Text("E-Mail-Adresse").foregroundStyle(RatsColor.muted)
                    )
                        .foregroundStyle(RatsColor.text)
                        .textContentType(.emailAddress)
                        .keyboardType(.emailAddress)
                        .textInputAutocapitalization(.never)
                        .textFieldStyle(.plain)
                        .accessibilityLabel("E-Mail")
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
                            RatsIcon(showsPassword ? .eyeOff : .eye, size: 16)
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
    // Der Ausweg beim Tippfehler. Er steht HIER, weil dieser Bildschirm die
    // ganze App ersetzt: Ein unbestätigtes Konto kommt gar nicht bis zur
    // Konto-Ansicht. Ohne ihn wäre eine vertippte Adresse eine Sackgasse.
    @State private var aendern = false
    @State private var neu = ""
    @State private var passwort = ""
    @State private var busy = false

    /// Wohin der Link zuletzt ging — die neue Adresse, sobald einer schwebt.
    private var zieladresse: String { model.user?.pendingEmail ?? user.email }

    var body: some View {
        AuthScaffold(
            scene: .wave,
            title: "Fast an Bord!",
            subtitle: "Bestätige deine E-Mail-Adresse. Sobald der Link geöffnet ist, geht es hier automatisch weiter."
        ) {
            VStack(spacing: 16) {
                RatsLabel(zieladresse, .mailWarning)
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

                if aendern {
                    VStack(spacing: 10) {
                        TextField("name@example.org", text: $neu)
                            .textContentType(.emailAddress)
                            .keyboardType(.emailAddress)
                            .textInputAutocapitalization(.never)
                            .autocorrectionDisabled()
                        SecureField("Dein Passwort", text: $passwort)
                            .textContentType(.password)
                        Button {
                            busy = true
                            Task {
                                do {
                                    try await model.changeEmail(
                                        newEmail: neu.trimmingCharacters(in: .whitespacesAndNewlines),
                                        password: passwort)
                                    feedback = model.user?.pendingEmail.map {
                                        "Bestätigungslink an \($0) unterwegs."
                                    } ?? "Deine E-Mail-Adresse wurde geändert."
                                    aendern = false
                                    neu = ""
                                    passwort = ""
                                } catch { feedback = error.localizedDescription }
                                busy = false
                            }
                        } label: {
                            Text(busy ? "Wird geändert …" : "Adresse ändern").frame(maxWidth: .infinity)
                        }
                        .buttonStyle(SecondaryButtonStyle())
                        .disabled(busy || !neu.contains("@") || passwort.isEmpty)
                    }
                    .frame(maxWidth: .infinity)
                } else {
                    Button("Falsche Adresse? Ändern") { aendern = true }
                        .font(RatsFont.body(13, weight: .semibold))
                        .foregroundStyle(RatsColor.primary)
                }

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

/// Die Kontaktadresse des Betreibers.
///
/// Eigene Kopie, weil Swift aus `web/frontend/lib/kontakt.ts` nichts
/// importieren kann. Wer eine der beiden ändert, ändert beide;
/// `tests/test_kontaktadresse.py` hält sie zusammen.
enum RatslotseKontakt {
    static let email = "ratslotse@timsigl.de"
}

/// Das Konto wurde von einem Admin abgeschaltet.
///
/// Eigener Bildschirm, weil hier vorher `VerificationPendingView` stand: Die
/// App forderte eine gesperrte Person auf, ihre E-Mail-Adresse zu bestätigen —
/// die sie längst bestätigt hatte. Der Knopf „Erneut senden" meldete dann
/// „Der Link ist unterwegs" und verschickte nichts, weil der Endpunkt für ein
/// bestätigtes Konto folgenlos zurückkehrt.
///
/// Anders als dort wird hier NICHT im Hintergrund gepollt: Eine Freischaltung
/// hängt an einem Menschen, nicht an einer Mail, die in Sekunden ankommt.
struct AccountDisabledView: View {
    let model: AppModel
    let user: User

    var body: some View {
        AuthScaffold(
            scene: .wave,
            title: "Konto ist deaktiviert",
            subtitle: "Dieses Konto wurde vorübergehend abgeschaltet. Melde dich gern bei uns, wenn das ein Irrtum ist."
        ) {
            VStack(spacing: 16) {
                RatsLabel(user.email, .shieldCheck)
                    .font(RatsFont.body(14, weight: .semibold))
                    .foregroundStyle(RatsColor.primary)
                Button { Task { await model.refreshAccount() } } label: {
                    Text("Erneut prüfen").frame(maxWidth: .infinity)
                }
                .buttonStyle(SecondaryButtonStyle())
                .frame(maxWidth: .infinity)
                // Die Adresse direkt statt eines Verweises aufs Impressum: Wer
                // gesperrt ist, sieht nur noch diesen Bildschirm.
                Link(destination: URL(string: "mailto:\(RatslotseKontakt.email)")!) {
                    Text(RatslotseKontakt.email)
                        .font(RatsFont.body(13, weight: .semibold))
                        .foregroundStyle(RatsColor.primary)
                }
                Button("Abmelden", role: .destructive) { Task { await model.logout() } }
            }
        }
    }
}
