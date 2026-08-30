import Foundation
import Security

public enum KeychainError: Error, Sendable, Equatable {
    case unexpectedStatus(OSStatus)
}

/// Minimal keychain wrapper shared by the app and its API actor.
public struct KeychainStore: Sendable {
    public static let accessTokenAccount = "access_token"

    private let service: String

    public init(service: String = "de.ratslotse.app.auth") {
        self.service = service
    }

    public func read(account: String = accessTokenAccount) throws -> String? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne,
        ]
        var result: CFTypeRef?
        let status = SecItemCopyMatching(query as CFDictionary, &result)
        if status == errSecItemNotFound { return nil }
        guard status == errSecSuccess else { throw KeychainError.unexpectedStatus(status) }
        guard let data = result as? Data else { return nil }
        return String(data: data, encoding: .utf8)
    }

    public func write(_ value: String, account: String = accessTokenAccount) throws {
        let data = Data(value.utf8)
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
        ]
        let update: [String: Any] = [
            kSecValueData as String: data,
            kSecAttrAccessible as String: kSecAttrAccessibleAfterFirstUnlock,
        ]
        let status = SecItemUpdate(query as CFDictionary, update as CFDictionary)
        if status == errSecItemNotFound {
            var insert = query
            insert.merge(update) { _, new in new }
            let addStatus = SecItemAdd(insert as CFDictionary, nil)
            guard addStatus == errSecSuccess else { throw KeychainError.unexpectedStatus(addStatus) }
        } else if status != errSecSuccess {
            throw KeychainError.unexpectedStatus(status)
        }
    }

    public func delete(account: String = accessTokenAccount) throws {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
        ]
        let status = SecItemDelete(query as CFDictionary)
        guard status == errSecSuccess || status == errSecItemNotFound else {
            throw KeychainError.unexpectedStatus(status)
        }
    }

    /// Capacitor Preferences used this UserDefaults key in TestFlight builds.
    /// Moving it once keeps testers logged in during the native cutover.
    @discardableResult
    public func migrateCapacitorToken(defaults: UserDefaults = .standard) throws -> String? {
        if let existing = try read(), !existing.isEmpty { return existing }
        let legacyKey = "CapacitorStorage.access_token"
        guard let legacy = defaults.string(forKey: legacyKey), !legacy.isEmpty else { return nil }
        try write(legacy)
        defaults.removeObject(forKey: legacyKey)
        return legacy
    }
}
