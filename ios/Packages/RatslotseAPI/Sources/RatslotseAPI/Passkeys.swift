import CryptoKit
import Foundation

// Mit Passkey anmelden und registrieren (seit 11/2026, Schalter
// `passkey-anmeldung`) — die Teile ohne AuthenticationServices, damit sie
// hier ohne Simulator testbar sind. Die Abfrage am Gerät steht in
// `RatslotseFeatures/PasskeyAuthenticator.swift`.
//
// Der Server prüft per WebAuthn (`web/backend/app/passkeys.py`). Seine
// Optionen kommen als JSON der Norm in `public_key` (Binärfelder Base64url);
// zurück gehen nur `id`, `rawId`, `type` und `response`. Das PRF-Geheimnis,
// das dieselbe Abfrage liefert, bleibt auf dem Gerät und schließt die
// Notizen auf — genau wie im Web (`web/frontend/lib/passkey.ts`).

public enum Base64URL {
    public static func encode(_ data: Data) -> String {
        data.base64EncodedString()
            .replacingOccurrences(of: "+", with: "-")
            .replacingOccurrences(of: "/", with: "_")
            .replacingOccurrences(of: "=", with: "")
    }

    public static func decode(_ text: String) -> Data? {
        var s = text.replacingOccurrences(of: "-", with: "+").replacingOccurrences(of: "_", with: "/")
        s += String(repeating: "=", count: (4 - s.count % 4) % 4)
        return Data(base64Encoded: s)
    }
}

// MARK: - Optionen vom Server

/// `PasskeyOptions` im Vertrag, zum Anlegen. `public_key` ist dort bewusst
/// ein offenes Objekt (die Form gibt die Norm vor) — die App liest daraus
/// nur, was die Abfrage am Gerät braucht.
public struct PasskeyCreationEnvelope: Decodable, Sendable {
    public let publicKey: PasskeyCreationOptions

    enum CodingKeys: String, CodingKey {
        case publicKey = "public_key"
    }
}

/// `PasskeyOptions` im Vertrag, zum Bestätigen.
public struct PasskeyRequestEnvelope: Decodable, Sendable {
    public let publicKey: PasskeyRequestOptions

    enum CodingKeys: String, CodingKey {
        case publicKey = "public_key"
    }
}

public struct PasskeyCredentialDescriptor: Codable, Sendable, Equatable {
    public let id: String

    public init(id: String) { self.id = id }
}

/// `PublicKeyCredentialCreationOptionsJSON`, soweit die App es braucht.
public struct PasskeyCreationOptions: Decodable, Sendable, Equatable {
    public struct RelyingParty: Decodable, Sendable, Equatable {
        public let id: String
    }

    public struct UserEntity: Decodable, Sendable, Equatable {
        public let id: String
        public let name: String
        public let displayName: String?
    }

    public let challenge: String
    public let rp: RelyingParty
    public let user: UserEntity
    public let excludeCredentials: [PasskeyCredentialDescriptor]

    enum CodingKeys: String, CodingKey {
        case challenge, rp, user, excludeCredentials
    }

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        challenge = try c.decode(String.self, forKey: .challenge)
        rp = try c.decode(RelyingParty.self, forKey: .rp)
        user = try c.decode(UserEntity.self, forKey: .user)
        excludeCredentials = try c.decodeIfPresent([PasskeyCredentialDescriptor].self, forKey: .excludeCredentials) ?? []
    }

    public var challengeData: Data? { Base64URL.decode(challenge) }
    public var userID: Data? { Base64URL.decode(user.id) }
}

/// `PublicKeyCredentialRequestOptionsJSON`, soweit die App es braucht.
public struct PasskeyRequestOptions: Decodable, Sendable, Equatable {
    public let challenge: String
    public let rpId: String
    public let allowCredentials: [PasskeyCredentialDescriptor]

    enum CodingKeys: String, CodingKey {
        case challenge, rpId, allowCredentials
    }

    public init(challenge: String, rpId: String, allowCredentials: [PasskeyCredentialDescriptor] = []) {
        self.challenge = challenge
        self.rpId = rpId
        self.allowCredentials = allowCredentials
    }

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        challenge = try c.decode(String.self, forKey: .challenge)
        // Fehlt die RP-ID, gilt die Seite selbst — für die App also die
        // Domain, mit der sie verknüpft ist.
        rpId = try c.decodeIfPresent(String.self, forKey: .rpId) ?? Passkeys.relyingParty
        allowCredentials = try c.decodeIfPresent([PasskeyCredentialDescriptor].self, forKey: .allowCredentials) ?? []
    }

    public var challengeData: Data? { Base64URL.decode(challenge) }
}

// MARK: - Was an den Server geht (ohne PRF)

/// `PasskeyRegistration` im Vertrag.
public struct PasskeyRegistrationCredential: Codable, Sendable, Equatable {
    public struct Response: Codable, Sendable, Equatable {
        public let clientDataJSON: String
        public let attestationObject: String
        public let transports: [String]
    }

    public let id: String
    public let rawId: String
    public let type: String
    public let response: Response

    public init(credentialID: Data, clientDataJSON: Data, attestationObject: Data,
                transports: [String] = Passkeys.platformTransports) {
        id = Base64URL.encode(credentialID)
        rawId = id
        type = "public-key"
        response = Response(clientDataJSON: Base64URL.encode(clientDataJSON),
                            attestationObject: Base64URL.encode(attestationObject),
                            transports: transports)
    }
}

/// `PasskeyAssertion` im Vertrag.
public struct PasskeyAssertionCredential: Codable, Sendable, Equatable {
    public struct Response: Codable, Sendable, Equatable {
        public let clientDataJSON: String
        public let authenticatorData: String
        public let signature: String
        public let userHandle: String?
    }

    public let id: String
    public let rawId: String
    public let type: String
    public let response: Response

    public init(credentialID: Data, clientDataJSON: Data, authenticatorData: Data, signature: Data, userID: Data?) {
        id = Base64URL.encode(credentialID)
        rawId = id
        type = "public-key"
        response = Response(clientDataJSON: Base64URL.encode(clientDataJSON),
                            authenticatorData: Base64URL.encode(authenticatorData),
                            signature: Base64URL.encode(signature),
                            userHandle: userID.flatMap { $0.isEmpty ? nil : Base64URL.encode($0) })
    }
}

/// `PasskeySignupOptionsRequest`.
public struct PasskeySignupOptionsBody: Encodable, Sendable {
    public let email: String
    public let display_name: String

    public init(email: String, displayName: String) {
        self.email = email
        display_name = displayName
    }
}

/// `PasskeySignupRequest` und `PasskeyAddRequest` — dieselbe Form.
public struct PasskeyRegistrationBody: Encodable, Sendable {
    public let credential: PasskeyRegistrationCredential
    public let label: String

    public init(credential: PasskeyRegistrationCredential, label: String) {
        self.credential = credential
        self.label = label
    }
}

/// `PasskeyLoginRequest`.
public struct PasskeyLoginBody: Encodable, Sendable {
    public let credential: PasskeyAssertionCredential

    public init(credential: PasskeyAssertionCredential) { self.credential = credential }
}

// MARK: - Passkeys im Konto

/// `AccountPasskey`: ein Passkey zum Anmelden. `notes`: er schließt auch die
/// Notizen auf.
public struct AccountPasskey: Codable, Sendable, Equatable, Identifiable {
    public let id: Int
    public let credentialId: String
    public let label: String
    public let createdAt: String
    public let lastUsedAt: String?
    public let backedUp: Bool
    public let notes: Bool

    enum CodingKeys: String, CodingKey {
        case id, label, notes
        case credentialId = "credential_id"
        case createdAt = "created_at"
        case lastUsedAt = "last_used_at"
        case backedUp = "backed_up"
    }
}

/// `AccountPasskeyList`.
public struct AccountPasskeyList: Codable, Sendable, Equatable {
    public let passkeys: [AccountPasskey]
}

// MARK: - Notizen mit derselben Abfrage

public enum Passkeys {
    /// Die Domain, mit der die App verknüpft ist (`webcredentials:` im
    /// Entitlement, `webcredentials` in der AASA-Datei). Der Server setzt die
    /// RP-ID aus `APP_BASE_URL`, wenn eine Anfrage — wie die der App — keine
    /// `Origin` mitbringt.
    public static let relyingParty = "ratslotse.de"
    /// Was das Gerät für einen Passkey im iCloud-Schlüsselbund meldet; Safari
    /// schickt dieselben beiden.
    public static let platformTransports = ["hybrid", "internal"]
    /// SHA-256 von „ratslotse-passkey-notizen-v1" — dasselbe feste Salz wie
    /// `ANMELDE_SALZ_B64` im Web. Bei der Anmeldung weiß niemand vorher,
    /// welcher Passkey kommt; ein Salz je Passkey ginge also nicht.
    public static let loginSaltB64 = "5MnwhF9xlXWJRKjXOzZmPPe88kNNx+zhKCJHRsu15G4="
    public static var loginSalt: Data { Data(base64Encoded: loginSaltB64)! }
    static let kekInfo = Data("ratslotse-notizen-passkey".utf8)

    /// Aus dem PRF-Geheimnis der Schlüssel, der den Notiz-Datenschlüssel
    /// verpackt — HKDF-SHA-256 ohne Salz, wie `passkeyKek` im Web.
    public static func kek(prf: Data) -> Data {
        let key = HKDF<SHA256>.deriveKey(inputKeyMaterial: SymmetricKey(data: prf), salt: Data(),
                                         info: kekInfo, outputByteCount: 32)
        return key.withUnsafeBytes { Data($0) }
    }

    /// Ein Name für die Liste im Konto — wie `geraeteName` im Web nur grob.
    public static func deviceLabel(isPad: Bool) -> String { isPad ? "iPad" : "iPhone" }
}

/// Was die Abfrage am Gerät außer dem Ergebnis für den Server liefert.
public struct PasskeyHit: Sendable, Equatable {
    public let credentialId: String
    /// `nil`, wo das Gerät kein PRF kann (vor iOS 18) oder es beim Anlegen
    /// nicht mitliefert.
    public let prf: Data?

    public init(credentialId: String, prf: Data?) {
        self.credentialId = credentialId
        self.prf = prf
    }
}

/// Ein Anmelde-Passkey, dessen Schlüssel für die Notizen bereitliegt, aber
/// noch nicht verpackt ist (Konto unbestätigt, oder die Notizen hängen an
/// einem anderen Schlüssel). Nur im Speicher.
public struct PendingNotesPasskey: Sendable, Equatable {
    public let owner: Int
    public let credentialId: String
    public let kek: Data

    public init(owner: Int, credentialId: String, kek: Data) {
        self.owner = owner
        self.credentialId = credentialId
        self.kek = kek
    }
}

/// Die drei Lagen aus `notizenMitPasskey` im Web.
public enum NotesPasskeyPlan: Equatable, Sendable {
    /// Mit diesem Passkey eingerichtet — der Datenschlüssel ist offen.
    case unlock(Data)
    /// Eingerichtet, aber mit einem anderen Schlüssel: merken, beim nächsten
    /// Entsperren kommt der Passkey dazu.
    case remember
    /// Noch keine Notiz-Schlüssel: still einrichten.
    case setup

    public static func decide(state: NoteKeysState, credentialId: String, kek: Data) -> NotesPasskeyPlan {
        guard state.configured, state.keys != nil else { return .setup }
        let zeile = (state.passkeys ?? []).first {
            $0.credentialId == credentialId && $0.prfSalt == Passkeys.loginSaltB64
        }
        if let zeile, let wrapped = Data(base64Encoded: zeile.wrappedKey),
           let dk = NotesCrypto.unwrap(wrapped, kek: kek) {
            return .unlock(dk)
        }
        return .remember
    }
}

/// `PasskeyIn` in `NoteKeysIn` und, mit `key_version`, `PasskeyAddIn`.
public struct NotePasskeyWrap: Encodable, Sendable, Equatable {
    public let credential_id: String
    public let prf_salt: String
    public let wrapped_key: String
    public let label: String

    public init?(credentialId: String, dk: Data, kek: Data, label: String) {
        guard let wrapped = NotesCrypto.wrap(dk, kek: kek) else { return nil }
        credential_id = credentialId
        prf_salt = Passkeys.loginSaltB64
        wrapped_key = wrapped.base64EncodedString()
        self.label = label
    }
}

/// Notizen nur mit einem Passkey einrichten (`PUT /api/notes/keys`): Salz und
/// Runden stehen schon da, falls später eine Passphrase oder ein Code dazukommt.
public struct NoteKeysWithPasskey: Encodable, Sendable {
    public let key_version: Int
    public let kdf: String
    public let iterations: Int
    public let salt: String
    public let passkey: NotePasskeyWrap

    public init(passkey: NotePasskeyWrap, salt: Data = NotesCrypto.random(16)) {
        key_version = NotesCrypto.keyVersion
        kdf = NotesCrypto.kdf
        iterations = NotesCrypto.iterations
        self.salt = salt.base64EncodedString()
        self.passkey = passkey
    }
}

/// `PasskeyAddIn` (`POST /api/notes/passkeys`).
public struct NotePasskeyAdd: Encodable, Sendable {
    public let credential_id: String
    public let prf_salt: String
    public let wrapped_key: String
    public let label: String
    public let key_version: Int

    public init(_ wrap: NotePasskeyWrap, keyVersion: Int) {
        credential_id = wrap.credential_id
        prf_salt = wrap.prf_salt
        wrapped_key = wrap.wrapped_key
        label = wrap.label
        key_version = keyVersion
    }
}
