import AuthenticationServices
import RatslotseAPI
import UIKit

/// Ein Fehlschlag der Abfrage am Gerät — übersetzt wie `PasskeyFehler` im Web.
enum PasskeyError: LocalizedError, Equatable {
    /// Selbst abgebrochen: Niemand braucht dazu eine Meldung.
    case cancelled
    case alreadyThere
    case unsupported
    case failed(String)

    var errorDescription: String? {
        switch self {
        case .cancelled: "Abgebrochen."
        case .alreadyThere: "Auf diesem Gerät gibt es schon einen Passkey für dein Konto."
        case .unsupported: "Dieses Gerät kann hier keinen Passkey benutzen."
        case .failed(let text): text
        }
    }

    /// Die Meldung für die Oberfläche, oder `nil` beim eigenen Abbruch.
    static func message(for error: Error) -> String? {
        if let error = error as? PasskeyError { return error == .cancelled ? nil : error.localizedDescription }
        return (error as? APIError)?.message ?? error.localizedDescription
    }
}

/// Welches Salz die Abfrage für PRF mitschickt.
enum PasskeyPRFRequest {
    /// Das feste Anmelde-Salz (`Passkeys.loginSalt`): Anmelden, Registrieren.
    case login
    /// Je Passkey sein eigenes Salz (Notiz-Passkeys aus dem Web tragen eins).
    case perCredential([String: Data])
}

/// Die Abfrage am Gerät: `ASAuthorizationPlatformPublicKeyCredentialProvider`
/// mit der Erweiterung PRF (ab iOS 18; davor geht die Anmeldung, nur die
/// Notizen bleiben bis zum ersten Notieren zu).
///
/// Ein Objekt je Abfrage — `ASAuthorizationController` hält seinen Delegate
/// nur schwach, deshalb hält sich die Abfrage selbst, bis sie fertig ist.
@MainActor
final class PasskeyAuthenticator: NSObject {
    private var controller: ASAuthorizationController?
    private var continuation: CheckedContinuation<ASAuthorization, Error>?
    private var keepAlive: PasskeyAuthenticator?

    /// Einen Passkey anlegen. `prf` ist das Geheimnis zum Anmelde-Salz, falls
    /// das Gerät es schon beim Anlegen liefert.
    static func register(_ options: PasskeyCreationOptions) async throws -> (PasskeyRegistrationCredential, PasskeyHit) {
        guard let challenge = options.challengeData, let userID = options.userID else {
            throw PasskeyError.failed("Die Anfrage des Servers ist unvollständig. Bitte noch einmal.")
        }
        let provider = ASAuthorizationPlatformPublicKeyCredentialProvider(relyingPartyIdentifier: options.rp.id)
        let request = provider.createCredentialRegistrationRequest(challenge: challenge, name: options.user.name, userID: userID)
        request.displayName = options.user.displayName
        request.userVerificationPreference = .required
        if #available(iOS 17.4, *) {
            request.excludedCredentials = options.excludeCredentials.compactMap {
                Base64URL.decode($0.id).map(ASAuthorizationPlatformPublicKeyCredentialDescriptor.init(credentialID:))
            }
        }
        if #available(iOS 18.0, *) {
            request.prf = .inputValues(.init(saltInput1: Passkeys.loginSalt))
        }
        let authorization = try await PasskeyAuthenticator().perform(request)
        guard let credential = authorization.credential as? ASAuthorizationPlatformPublicKeyCredentialRegistration,
              let attestation = credential.rawAttestationObject else {
            throw PasskeyError.failed("Der Passkey ließ sich nicht anlegen.")
        }
        var prf: Data?
        if #available(iOS 18.0, *) {
            prf = credential.prf?.first.map { $0.withUnsafeBytes { Data($0) } }
        }
        let result = PasskeyRegistrationCredential(credentialID: credential.credentialID,
                                                   clientDataJSON: credential.rawClientDataJSON,
                                                   attestationObject: attestation)
        return (result, PasskeyHit(credentialId: result.id, prf: prf))
    }

    /// Mit einem Passkey bestätigen. Ohne `allowCredentials` bietet das Gerät
    /// von selbst an, was es für die Domain hat.
    static func assert(_ options: PasskeyRequestOptions, prf: PasskeyPRFRequest?) async throws -> (PasskeyAssertionCredential, PasskeyHit) {
        guard let challenge = options.challengeData else {
            throw PasskeyError.failed("Die Anfrage des Servers ist unvollständig. Bitte noch einmal.")
        }
        let provider = ASAuthorizationPlatformPublicKeyCredentialProvider(relyingPartyIdentifier: options.rpId)
        let request = provider.createCredentialAssertionRequest(challenge: challenge)
        request.userVerificationPreference = .required
        request.allowedCredentials = options.allowCredentials.compactMap {
            Base64URL.decode($0.id).map(ASAuthorizationPlatformPublicKeyCredentialDescriptor.init(credentialID:))
        }
        if #available(iOS 18.0, *), let prf {
            switch prf {
            case .login:
                request.prf = .inputValues(.init(saltInput1: Passkeys.loginSalt))
            case .perCredential(let salts):
                var values: [Data: ASAuthorizationPublicKeyCredentialPRFAssertionInput.InputValues] = [:]
                for (id, salt) in salts {
                    if let raw = Base64URL.decode(id) { values[raw] = .init(saltInput1: salt) }
                }
                request.prf = .perCredentialInputValues(values)
            }
        }
        let authorization = try await PasskeyAuthenticator().perform(request)
        guard let credential = authorization.credential as? ASAuthorizationPlatformPublicKeyCredentialAssertion else {
            throw PasskeyError.failed("Der Passkey ließ sich nicht bestätigen.")
        }
        var secret: Data?
        if #available(iOS 18.0, *) {
            secret = credential.prf.map { $0.first.withUnsafeBytes { Data($0) } }
        }
        let result = PasskeyAssertionCredential(credentialID: credential.credentialID,
                                                clientDataJSON: credential.rawClientDataJSON,
                                                authenticatorData: credential.rawAuthenticatorData,
                                                signature: credential.signature,
                                                userID: credential.userID)
        return (result, PasskeyHit(credentialId: result.id, prf: secret))
    }

    /// Eine zufällige Challenge für eine Abfrage, die nur PRF braucht — die
    /// Notizen öffnen sich auf dem Gerät, der Server prüft dabei nichts.
    static func localRequest(_ credentialIds: [String]) -> PasskeyRequestOptions {
        PasskeyRequestOptions(challenge: Base64URL.encode(NotesCrypto.random(32)), rpId: Passkeys.relyingParty,
                              allowCredentials: credentialIds.map(PasskeyCredentialDescriptor.init(id:)))
    }

    /// PRF (und damit die Notizen mit derselben Abfrage) gibt es ab iOS 18.
    static var supportsPRF: Bool {
        if #available(iOS 18.0, *) { return true }
        return false
    }

    static var deviceLabel: String {
        Passkeys.deviceLabel(isPad: UIDevice.current.userInterfaceIdiom == .pad)
    }

    private func perform(_ request: ASAuthorizationRequest) async throws -> ASAuthorization {
        try await withCheckedThrowingContinuation { continuation in
            self.continuation = continuation
            let controller = ASAuthorizationController(authorizationRequests: [request])
            controller.delegate = self
            controller.presentationContextProvider = self
            self.controller = controller
            keepAlive = self
            controller.performRequests()
        }
    }

    private func finish(_ result: Result<ASAuthorization, Error>) {
        continuation?.resume(with: result)
        continuation = nil
        controller = nil
        keepAlive = nil
    }

    private static func translate(_ error: Error) -> Error {
        guard let error = error as? ASAuthorizationError else { return error }
        if #available(iOS 18.0, *), error.code == .matchedExcludedCredential { return PasskeyError.alreadyThere }
        switch error.code {
        case .canceled: return PasskeyError.cancelled
        case .notHandled, .notInteractive: return PasskeyError.unsupported
        default:
            // „Application not associated with domain" landet hier — ohne
            // `webcredentials` in der AASA-Datei der Domain gibt es keinen
            // Passkey für die App.
            return PasskeyError.failed("Der Passkey hat nicht geklappt. Bitte versuch es noch einmal.")
        }
    }
}

extension PasskeyAuthenticator: ASAuthorizationControllerDelegate {
    nonisolated func authorizationController(controller _: ASAuthorizationController,
                                             didCompleteWithAuthorization authorization: ASAuthorization) {
        MainActor.assumeIsolated { finish(.success(authorization)) }
    }

    nonisolated func authorizationController(controller _: ASAuthorizationController, didCompleteWithError error: Error) {
        MainActor.assumeIsolated { finish(.failure(Self.translate(error))) }
    }
}

extension PasskeyAuthenticator: ASAuthorizationControllerPresentationContextProviding {
    nonisolated func presentationAnchor(for _: ASAuthorizationController) -> ASPresentationAnchor {
        MainActor.assumeIsolated {
            let scenes = UIApplication.shared.connectedScenes.compactMap { $0 as? UIWindowScene }
            let scene = scenes.first { $0.activationState == .foregroundActive } ?? scenes.first
            return scene?.keyWindow ?? scene?.windows.first ?? ASPresentationAnchor()
        }
    }
}
