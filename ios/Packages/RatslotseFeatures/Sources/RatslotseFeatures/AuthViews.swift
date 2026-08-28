import AuthenticationServices
import RatslotseAPI
import RatslotseDesign
import SwiftUI

struct WelcomeView: View {
    let model: AppModel

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 28) {
                Spacer(minLength: 50)
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
                    Button("Anmelden") { model.authPresentation = .login }
                        .buttonStyle(PrimaryButtonStyle())
                        .frame(maxWidth: .infinity)
                    Button("Konto anlegen") { model.authPresentation = .register }
                        .buttonStyle(SecondaryButtonStyle())
                        .frame(maxWidth: .infinity)
                }
                Text("Geteilte Beschlüsse und Personenprofile kannst du auch ohne Konto lesen.")
                    .font(RatsFont.body(12))
                    .foregroundStyle(RatsColor.muted)
            }
            .frame(maxWidth: 560, alignment: .leading)
            .padding(28)
        }
        .background(RatsColor.page)
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
            Group {
                switch mode {
                case .login: CredentialsView(model: model, mode: .login, switchMode: { mode = $0 })
                case .register: CredentialsView(model: model, mode: .register, switchMode: { mode = $0 })
                case .forgotPassword: ForgotPasswordView(model: model, switchMode: { mode = $0 })
                case .resetPassword(let token): ResetPasswordView(model: model, token: token)
                }
            }
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Schließen") { model.authPresentation = nil }
                }
            }
        }
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
    @State private var error: String?
    @State private var isWorking = false

    var body: some View {
        Form {
            Section {
                if mode == .register {
                    TextField("Anzeigename (optional)", text: $name)
                        .textContentType(.name)
                }
                TextField("E-Mail-Adresse", text: $email)
                    .textContentType(.emailAddress)
                    .textInputAutocapitalization(.never)
                    .keyboardType(.emailAddress)
                SecureField("Passwort", text: $password)
                    .textContentType(mode == .login ? .password : .newPassword)
            }

            if let error {
                Section { Text(error).foregroundStyle(RatsColor.danger) }
            }

            Section {
                Button(isWorking ? "Einen Moment …" : mode == .login ? "Anmelden" : "Konto anlegen") {
                    submit()
                }
                .disabled(isWorking || email.isEmpty || password.count < 8)
            }

            Section {
                SignInWithAppleButton(.continue) { request in
                    request.requestedScopes = [.fullName, .email]
                } onCompletion: { result in
                    completeApple(result)
                }
                .signInWithAppleButtonStyle(.black)
                .frame(height: 46)
                .clipShape(RoundedRectangle(cornerRadius: RatsRadius.button))
            }

            Section {
                if mode == .login {
                    Button("Passwort vergessen?") { switchMode(.forgotPassword) }
                    Button("Noch kein Konto? Konto anlegen") { switchMode(.register) }
                } else {
                    Button("Schon dabei? Anmelden") { switchMode(.login) }
                }
            }
        }
        .navigationTitle(mode == .login ? "Anmelden" : "Konto anlegen")
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
        Form {
            Section("E-Mail-Adresse") {
                TextField("du@example.org", text: $email)
                    .textContentType(.emailAddress)
                    .keyboardType(.emailAddress)
                    .textInputAutocapitalization(.never)
            }
            Section {
                Button("Link anfordern") {
                    Task {
                        do {
                            try await model.forgotPassword(email: email)
                            message = "Wenn es dieses Konto gibt, ist der Link unterwegs."
                        } catch { message = error.localizedDescription }
                    }
                }
                .disabled(email.isEmpty)
            }
            if let message { Section { Text(message) } }
            Section { Button("Zurück zur Anmeldung") { switchMode(.login) } }
        }
        .navigationTitle("Passwort vergessen")
    }
}

private struct ResetPasswordView: View {
    let model: AppModel
    let token: String
    @State private var password = ""
    @State private var repeated = ""
    @State private var error: String?

    var body: some View {
        Form {
            Section("Neues Passwort") {
                SecureField("Mindestens 8 Zeichen", text: $password)
                    .textContentType(.newPassword)
                SecureField("Noch einmal", text: $repeated)
                    .textContentType(.newPassword)
            }
            if let error { Section { Text(error).foregroundStyle(RatsColor.danger) } }
            Section {
                Button("Passwort speichern") {
                    guard password == repeated else { error = "Die Passwörter stimmen nicht überein."; return }
                    Task {
                        do { try await model.resetPassword(token: token, password: password) }
                        catch { self.error = error.localizedDescription }
                    }
                }
                .disabled(password.count < 8 || password != repeated)
            }
        }
        .navigationTitle("Passwort zurücksetzen")
    }
}

struct VerificationPendingView: View {
    let model: AppModel
    let user: User
    @State private var feedback: String?

    var body: some View {
        VStack(spacing: 20) {
            Image(systemName: "envelope.badge")
                .font(.system(size: 46))
                .foregroundStyle(RatsColor.primary)
            Text("Bestätige deine E-Mail")
                .font(RatsFont.title())
            Text("Wir haben den Link an \(user.email) geschickt. Sobald du ihn öffnest, geht es hier weiter.")
                .multilineTextAlignment(.center)
                .foregroundStyle(RatsColor.secondary)
            Button("Erneut senden") {
                Task {
                    do { try await model.resendVerification(); feedback = "Der Link ist unterwegs." }
                    catch { feedback = error.localizedDescription }
                }
            }
            .buttonStyle(PrimaryButtonStyle())
            Button("Ich habe bestätigt") { Task { await model.refreshAccount() } }
                .buttonStyle(SecondaryButtonStyle())
            if let feedback { Text(feedback).font(RatsFont.body(12)).foregroundStyle(RatsColor.secondary) }
            Button("Abmelden", role: .destructive) { Task { await model.logout() } }
        }
        .padding(28)
        .frame(maxWidth: 520, maxHeight: .infinity)
    }
}
