import Foundation
import RatslotseAPI

/// Mit Passkey anmelden und registrieren, Passkeys im Konto, und mit
/// derselben Abfrage die Notizen (seit 11/2026, Schalter `passkey-anmeldung`).
///
/// Dieselben Wege wie im Web (`web/frontend/lib/passkey.ts`): Der Server prüft
/// die Anmeldung, das PRF-Geheimnis bleibt auf dem Gerät und schließt hier
/// die Notizen auf. Scheitert dabei etwas, ist die Anmeldung trotzdem
/// gelungen — die Notizen fragen dann beim ersten Notieren selbst.
extension AppModel {
    static let passkeyFeature = "passkey-anmeldung"

    /// Ist der Passkey-Weg anzubieten? Der Schalter kommt aus `/api/app-config`;
    /// ohne ihn antworten die Endpunkte mit 404, und ohne die AASA-Datei mit
    /// `webcredentials`, die mit demselben Release live geht, gäbe es auf dem
    /// Gerät gar keinen Passkey für die App.
    var passkeysEnabled: Bool { feature(Self.passkeyFeature) }

    // MARK: Anmelden und registrieren

    func loginWithPasskey() async throws {
        let options: PasskeyRequestEnvelope = try await api.sendWithoutBody("/api/auth/passkey/login/options")
        let (credential, hit) = try await PasskeyAuthenticator.assert(options.publicKey, prf: .login)
        let user: User = try await api.send("/api/auth/passkey/login", body: PasskeyLoginBody(credential: credential))
        try await adopt(user: user)
        authPresentation = nil
        await openNotes(with: hit, owner: user.id)
    }

    /// Name und Adresse prüft der Server VOR der Abfrage am Gerät — wer eine
    /// vergebene Adresse tippt, muss nicht erst Face ID bemühen. Das Konto
    /// beginnt unbestätigt wie mit Passwort (Tims Entscheidung 11.11.2026).
    func registerWithPasskey(email: String, displayName: String) async throws {
        let options: PasskeyCreationEnvelope = try await api.send(
            "/api/auth/passkey/signup/options",
            body: PasskeySignupOptionsBody(email: email, displayName: displayName))
        let (credential, hit) = try await PasskeyAuthenticator.register(options.publicKey)
        let user: User = try await api.send(
            "/api/auth/passkey/signup",
            body: PasskeyRegistrationBody(credential: credential, label: PasskeyAuthenticator.deviceLabel))
        try await adopt(user: user)
        authPresentation = nil
        await openNotes(with: hit, owner: user.id)
    }

    /// Bestätigen beim Löschen oder Adresswechsel — ohne PRF, es geht nur um
    /// „bist du es".
    func passkeyConfirmation() async throws -> PasskeyAssertionCredential {
        let options: PasskeyRequestEnvelope = try await api.sendWithoutBody("/api/auth/passkey/login/options")
        return try await PasskeyAuthenticator.assert(options.publicKey, prf: nil).0
    }

    // MARK: Im Konto

    func loadAccountPasskeys() async throws -> AccountPasskeyList {
        try await api.get("/api/account/passkeys")
    }

    /// Einen weiteren Passkey anlegen. Wie im Web schließt er, wo das Gerät
    /// es kann, gleich auch die Notizen auf.
    func addAccountPasskey() async throws -> AccountPasskeyList {
        let (list, hit) = try await createAccountPasskey()
        if let owner = user?.id { await openNotes(with: hit, owner: owner) }
        return list
    }

    func removeAccountPasskey(id: Int) async throws -> AccountPasskeyList {
        try await api.sendWithoutBody("/api/account/passkeys/\(id)", method: .delete)
    }

    private func createAccountPasskey() async throws -> (AccountPasskeyList, PasskeyHit) {
        let options: PasskeyCreationEnvelope = try await api.sendWithoutBody("/api/account/passkeys/options")
        let (credential, hit) = try await PasskeyAuthenticator.register(options.publicKey)
        let list: AccountPasskeyList = try await api.send(
            "/api/account/passkeys",
            body: PasskeyRegistrationBody(credential: credential, label: PasskeyAuthenticator.deviceLabel))
        return (list, hit)
    }

    // MARK: Notizen mit derselben Abfrage

    enum NotesPasskeyOutcome: Equatable {
        case unlocked, setUp, remembered, nothing
    }

    /// `notizenMitPasskey` aus dem Web:
    /// - mit diesem Passkey eingerichtet → gleich entsperren,
    /// - noch gar nicht eingerichtet → still einrichten,
    /// - mit einem anderen Schlüssel eingerichtet, oder das Konto ist noch
    ///   unbestätigt (403) → für diese Sitzung merken.
    /// Offen bleiben sie dann auf diesem Gerät bis zum Abmelden.
    @discardableResult
    func openNotes(with hit: PasskeyHit, owner: Int) async -> NotesPasskeyOutcome {
        guard let prf = hit.prf else { return .nothing }
        let kek = Passkeys.kek(prf: prf)
        let remember = PendingNotesPasskey(owner: owner, credentialId: hit.credentialId, kek: kek)
        let state: NoteKeysState
        do {
            state = try await api.get("/api/notes/keys")
        } catch let error as APIError where error.statusCode == 403 {
            pendingNotesPasskey = remember
            return .remembered
        } catch {
            // 404: Notizen sind aus.
            return .nothing
        }
        switch NotesPasskeyPlan.decide(state: state, credentialId: hit.credentialId, kek: kek) {
        case .unlock(let dk):
            setNotesKey(dk, remember: true)
            return .unlocked
        case .remember:
            pendingNotesPasskey = remember
            return .remembered
        case .setup:
            return (try? await setupNotesWithPasskey(credentialId: hit.credentialId, kek: kek)) != nil ? .setUp : .nothing
        }
    }

    /// Neue Notiz-Schlüssel, verpackt nur mit dem Schlüssel aus einem
    /// Anmelde-Passkey — keine Passphrase, kein Pflicht-Code.
    @discardableResult
    func setupNotesWithPasskey(credentialId: String, kek: Data) async throws -> NoteKeysState {
        let dk = NotesCrypto.random(32)
        guard let wrap = NotePasskeyWrap(credentialId: credentialId, dk: dk, kek: kek,
                                         label: PasskeyAuthenticator.deviceLabel) else {
            throw PasskeyError.failed("Das Einrichten hat nicht geklappt.")
        }
        let state: NoteKeysState = try await api.send("/api/notes/keys", method: .put, body: NoteKeysWithPasskey(passkey: wrap))
        setNotesKey(dk, remember: true)
        pendingNotesPasskey = nil
        return state
    }

    /// Den gemerkten Anmelde-Passkey zu den Notizen legen, sobald der
    /// Datenschlüssel offen ist (`anmeldePasskeyNachtragen` im Web). Danach
    /// öffnet die nächste Anmeldung die Notizen ohne Passphrase.
    func attachPendingNotesPasskey(dk: Data, keyVersion: Int) async -> NoteKeysState? {
        guard let pending = pendingNotesPasskey, pending.owner == user?.id,
              let wrap = NotePasskeyWrap(credentialId: pending.credentialId, dk: dk, kek: pending.kek,
                                         label: PasskeyAuthenticator.deviceLabel) else { return nil }
        let state: NoteKeysState? = try? await api.send("/api/notes/passkeys", body: NotePasskeyAdd(wrap, keyVersion: keyVersion))
        if state != nil { pendingNotesPasskey = nil }
        return state
    }

    /// Für das Einrichten der Notizen einen Passkey besorgen, der zugleich
    /// anmeldet (`notizPasskeyBesorgen` im Web): erst der aus dieser Sitzung
    /// (keine Abfrage), dann einer der vorhandenen, sonst ein neuer.
    func obtainNotesPasskey(owner: Int) async throws -> PendingNotesPasskey {
        if let pending = pendingNotesPasskey, pending.owner == owner { return pending }
        let vorhanden = try await loadAccountPasskeys().passkeys
        if !vorhanden.isEmpty {
            let (_, hit) = try await PasskeyAuthenticator.assert(
                PasskeyAuthenticator.localRequest(vorhanden.map(\.credentialId)), prf: .login)
            return try Self.pending(owner: owner, hit: hit)
        }
        let (_, neu) = try await createAccountPasskey()
        if neu.prf != nil { return try Self.pending(owner: owner, hit: neu) }
        // Liefert das Gerät das Geheimnis beim Anlegen nicht, einmal nachfragen.
        let (_, hit) = try await PasskeyAuthenticator.assert(
            PasskeyAuthenticator.localRequest([neu.credentialId]), prf: .login)
        return try Self.pending(owner: owner, hit: hit)
    }

    /// Mit einem der Notiz-Passkeys entsperren — jeder mit seinem Salz. Die
    /// Challenge ist zufällig: Geprüft wird hier nur auf dem Gerät.
    func unlockNotesWithPasskey(_ passkeys: [NotePasskey]) async throws -> Data {
        var salts: [String: Data] = [:]
        for p in passkeys { salts[p.credentialId] = Data(base64Encoded: p.prfSalt) }
        let (_, hit) = try await PasskeyAuthenticator.assert(
            PasskeyAuthenticator.localRequest(passkeys.map(\.credentialId)), prf: .perCredential(salts))
        guard let prf = hit.prf else { throw PasskeyError.failed(Self.keinSchluessel) }
        guard let zeile = passkeys.first(where: { $0.credentialId == hit.credentialId }),
              let wrapped = Data(base64Encoded: zeile.wrappedKey),
              let dk = NotesCrypto.unwrap(wrapped, kek: Passkeys.kek(prf: prf)) else {
            throw PasskeyError.failed("Dieser Passkey öffnet die Notizen nicht.")
        }
        return dk
    }

    private static let keinSchluessel = "Dieser Passkey liefert keinen Schlüssel. Auf dem iPhone geht das ab iOS 18."

    private static func pending(owner: Int, hit: PasskeyHit) throws -> PendingNotesPasskey {
        guard let prf = hit.prf else { throw PasskeyError.failed(keinSchluessel) }
        return PendingNotesPasskey(owner: owner, credentialId: hit.credentialId, kek: Passkeys.kek(prf: prf))
    }
}
