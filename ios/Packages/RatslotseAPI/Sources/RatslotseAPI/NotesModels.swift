import Foundation
import Security

// Verschlüsselte Notizen (`/api/notes`, Plan `docs/plan-notizen-app.md`).
// Der Server kennt nur Blobs; die Felder unten sind genau die des Vertrags
// (`NoteKeysState`, `NoteEntry`, `NoteList` in `api/openapi.json`).

/// Seit 11/2026 sind Passphrase und Notfall-Code freiwillig: Im Web lassen
/// sich Notizen allein mit einem Passkey einrichten (WebAuthn-PRF). Dann sind
/// beide Verpackungen `nil` — die App kann solche Notizen nur mit dem Code
/// öffnen, bis sie selbst Passkeys kann.
public struct NoteKeys: Codable, Sendable, Equatable {
    public let keyVersion: Int
    public let kdf: String
    public let iterations: Int
    public let salt: String
    public let wrappedPassphrase: String?
    public let wrappedRecovery: String?
    public let updatedAt: String

    enum CodingKeys: String, CodingKey {
        case kdf, iterations, salt
        case keyVersion = "key_version"
        case wrappedPassphrase = "wrapped_passphrase"
        case wrappedRecovery = "wrapped_recovery"
        case updatedAt = "updated_at"
    }
}

/// Ein Passkey als Schlüssel zu den Notizen — die App zählt sie nur, sie
/// kann sie (noch) nicht benutzen.
public struct NotePasskey: Codable, Sendable, Equatable {
    public let id: Int
    public let label: String
    public let createdAt: String

    enum CodingKeys: String, CodingKey {
        case id, label
        case createdAt = "created_at"
    }
}

public struct NoteKeysState: Codable, Sendable, Equatable {
    public let configured: Bool
    public let keys: NoteKeys?
    /// Optional, weil ältere Server das Feld nicht schicken.
    public let passkeys: [NotePasskey]?
}

public struct NoteEntry: Codable, Sendable, Equatable {
    public let targetKind: String
    public let targetKey: String
    public let kind: String
    public let iv: String
    public let ciphertext: String
    public let keyVersion: Int
    public let version: Int
    public let updatedAt: String

    enum CodingKeys: String, CodingKey {
        case kind, iv, ciphertext, version
        case targetKind = "target_kind"
        case targetKey = "target_key"
        case keyVersion = "key_version"
        case updatedAt = "updated_at"
    }
}

public struct NoteList: Codable, Sendable {
    public let notes: [NoteEntry]
}

/// Was die App beim Speichern schickt (`NoteIn` im Backend).
public struct NoteUpload: Encodable, Sendable {
    public let iv: String
    public let ciphertext: String
    public let key_version: Int
    public let version: Int

    public init(iv: String, ciphertext: String, keyVersion: Int, version: Int) {
        self.iv = iv
        self.ciphertext = ciphertext
        self.key_version = keyVersion
        self.version = version
    }
}

/// Neue Passphrase (`NoteKeysIn` ohne `wrapped_recovery`).
public struct NoteKeysRewrap: Encodable, Sendable {
    public let key_version: Int
    public let kdf: String
    public let iterations: Int
    public let salt: String
    public let wrapped_passphrase: String

    public init(keyVersion: Int, iterations: Int, salt: String, wrappedPassphrase: String) {
        key_version = keyVersion
        kdf = NotesCrypto.kdf
        self.iterations = iterations
        self.salt = salt
        wrapped_passphrase = wrappedPassphrase
    }
}

/// Das Dokument einer Notiz. Kodiert genau wie `JSON.stringify({ text })` im
/// Web — die Schlüssel sind dieselben, die Reihenfolge spielt beim Lesen keine Rolle.
public struct NoteDocument: Codable, Sendable, Equatable {
    public var text: String
    public init(text: String) { self.text = text }
}

/// Der entsperrte Datenschlüssel in der Keychain — nur auf diesem Gerät, nur
/// bei entsperrtem Gerät, nie in iCloud oder im Backup.
public struct NoteKeyVault: Sendable {
    private let service: String

    public init(service: String = "de.ratslotse.app.notes") {
        self.service = service
    }

    private func query(_ owner: Int) -> [String: Any] {
        [kSecClass as String: kSecClassGenericPassword,
         kSecAttrService as String: service,
         kSecAttrAccount as String: "konto:\(owner)"]
    }

    public func load(owner: Int) -> Data? {
        var q = query(owner)
        q[kSecReturnData as String] = true
        q[kSecMatchLimit as String] = kSecMatchLimitOne
        var result: CFTypeRef?
        guard SecItemCopyMatching(q as CFDictionary, &result) == errSecSuccess else { return nil }
        return result as? Data
    }

    public func save(_ dk: Data, owner: Int) {
        let q = query(owner)
        SecItemDelete(q as CFDictionary)
        var insert = q
        insert[kSecValueData as String] = dk
        insert[kSecAttrAccessible as String] = kSecAttrAccessibleWhenUnlockedThisDeviceOnly
        insert[kSecAttrSynchronizable as String] = false
        SecItemAdd(insert as CFDictionary, nil)
    }

    /// Ohne `owner`: alle Notiz-Schlüssel dieses Geräts (Abmelden, Konto löschen).
    public func delete(owner: Int? = nil) {
        var q: [String: Any] = [kSecClass as String: kSecClassGenericPassword, kSecAttrService as String: service]
        if let owner { q[kSecAttrAccount as String] = "konto:\(owner)" }
        SecItemDelete(q as CFDictionary)
    }
}
