import CommonCrypto
import CryptoKit
import Foundation

/// Verschlüsselung der Notizen — dieselben Bytes wie im Web
/// (`web/frontend/lib/notiz-krypto.ts`, Plan `docs/plan-notizen-app.md` § 2).
///
/// - Datenschlüssel (DK): 32 Byte, AES-256-GCM.
/// - Verpackt mit AES-KW (RFC 3394) — einmal mit einem Schlüssel aus der
///   Notiz-Passphrase (PBKDF2-SHA-256), einmal mit einem aus dem
///   Wiederherstellungscode (HKDF-SHA-256).
/// - Jede Notiz: AES-GCM, 12-Byte-IV, das Ziel als Zusatzdaten. Geheimtext
///   wie bei WebCrypto: Chiffrat und 16-Byte-Tag hintereinander.
///
/// CryptoKit kennt weder PBKDF2 noch AES-KW; beides kommt aus CommonCrypto.
/// Die Testvektoren in `NotesCryptoTests` sind dieselben wie im Web — ohne sie
/// wäre „Web und App lesen dieselben Daten" eine Behauptung.
public enum NotesCrypto {
    public static let kdf = "pbkdf2-sha256"
    public static let iterations = 600_000
    public static let keyVersion = 1
    static let recoveryInfo = Data("ratslotse-notizen-wiederherstellung".utf8)
    /// Crockford-Base32 ohne I, L, O, U.
    static let alphabet = Array("0123456789ABCDEFGHJKMNPQRSTVWXYZ")

    public struct WrappedKeys: Codable, Sendable, Equatable {
        public var key_version: Int
        public var kdf: String
        public var iterations: Int
        public var salt: String
        public var wrapped_passphrase: String
        public var wrapped_recovery: String
    }

    // MARK: Ableitung

    /// PBKDF2-HMAC-SHA-256, 32 Byte.
    public static func passphraseKek(_ passphrase: String, salt: Data, iterations: Int = iterations) -> Data? {
        let pw = Data(passphrase.precomposedStringWithCanonicalMapping.utf8)
        var out = Data(count: 32)
        let status = out.withUnsafeMutableBytes { outPtr in
            salt.withUnsafeBytes { saltPtr in
                pw.withUnsafeBytes { pwPtr in
                    CCKeyDerivationPBKDF(
                        CCPBKDFAlgorithm(kCCPBKDF2),
                        pwPtr.baseAddress?.assumingMemoryBound(to: CChar.self), pw.count,
                        saltPtr.baseAddress?.assumingMemoryBound(to: UInt8.self), salt.count,
                        CCPseudoRandomAlgorithm(kCCPRFHmacAlgSHA256), UInt32(iterations),
                        outPtr.baseAddress?.assumingMemoryBound(to: UInt8.self), 32)
                }
            }
        }
        return status == kCCSuccess ? out : nil
    }

    /// HKDF-SHA-256 aus den 20 Byte des Codes.
    public static func recoveryKek(_ code: Data, salt: Data) -> Data {
        let key = HKDF<SHA256>.deriveKey(inputKeyMaterial: SymmetricKey(data: code), salt: salt,
                                         info: recoveryInfo, outputByteCount: 32)
        return key.withUnsafeBytes { Data($0) }
    }

    // MARK: AES-KW

    public static func wrap(_ dk: Data, kek: Data) -> Data? {
        var out = Data(count: CCSymmetricWrappedSize(CCWrappingAlgorithm(kCCWRAPAES), dk.count))
        var outLen = out.count
        let status = out.withUnsafeMutableBytes { o in
            dk.withUnsafeBytes { d in
                kek.withUnsafeBytes { k in
                    CCSymmetricKeyWrap(CCWrappingAlgorithm(kCCWRAPAES), CCrfc3394_iv, CCrfc3394_ivLen,
                                       k.baseAddress?.assumingMemoryBound(to: UInt8.self), kek.count,
                                       d.baseAddress?.assumingMemoryBound(to: UInt8.self), dk.count,
                                       o.baseAddress?.assumingMemoryBound(to: UInt8.self), &outLen)
                }
            }
        }
        return status == kCCSuccess ? out.prefix(outLen) : nil
    }

    /// `nil` bei falschem Schlüssel — AES-KW prüft die Unversehrtheit selbst.
    public static func unwrap(_ wrapped: Data, kek: Data) -> Data? {
        guard wrapped.count >= 24 else { return nil }
        var out = Data(count: CCSymmetricUnwrappedSize(CCWrappingAlgorithm(kCCWRAPAES), wrapped.count))
        var outLen = out.count
        let status = out.withUnsafeMutableBytes { o in
            wrapped.withUnsafeBytes { w in
                kek.withUnsafeBytes { k in
                    CCSymmetricKeyUnwrap(CCWrappingAlgorithm(kCCWRAPAES), CCrfc3394_iv, CCrfc3394_ivLen,
                                         k.baseAddress?.assumingMemoryBound(to: UInt8.self), kek.count,
                                         w.baseAddress?.assumingMemoryBound(to: UInt8.self), wrapped.count,
                                         o.baseAddress?.assumingMemoryBound(to: UInt8.self), &outLen)
                }
            }
        }
        return status == kCCSuccess ? out.prefix(outLen) : nil
    }

    // MARK: Code

    /// 20 Byte → „ABCD-EFGH-…", 8 Gruppen zu 4.
    public static func encodeRecovery(_ code: Data) -> String {
        var bits = 0, wert = 0
        var out = ""
        for b in code {
            wert = (wert << 8 | Int(b)) & 0xFFFF
            bits += 8
            while bits >= 5 {
                out.append(alphabet[(wert >> (bits - 5)) & 31])
                bits -= 5
            }
        }
        if bits > 0 { out.append(alphabet[(wert << (5 - bits)) & 31]) }
        return stride(from: 0, to: out.count, by: 4).map { i -> String in
            let start = out.index(out.startIndex, offsetBy: i)
            return String(out[start..<out.index(start, offsetBy: min(4, out.count - i))])
        }.joined(separator: "-")
    }

    /// Abgetippter Code → 20 Byte, oder `nil`. O liest sich als 0, I und L als 1.
    public static func parseRecovery(_ eingabe: String) -> Data? {
        let s = eingabe.uppercased().filter { !$0.isWhitespace && $0 != "-" }
            .map { $0 == "O" ? Character("0") : ($0 == "I" || $0 == "L") ? Character("1") : $0 }
        guard s.count == 32 else { return nil }
        var out = Data()
        var bits = 0, wert = 0
        for ch in s {
            guard let v = alphabet.firstIndex(of: ch) else { return nil }
            wert = (wert << 5 | v) & 0xFFFF
            bits += 5
            if bits >= 8 {
                out.append(UInt8((wert >> (bits - 8)) & 0xFF))
                bits -= 8
            }
        }
        return out
    }

    // MARK: Einrichten und Entsperren

    public static func random(_ n: Int) -> Data {
        var d = Data(count: n)
        _ = d.withUnsafeMutableBytes { SecRandomCopyBytes(kSecRandomDefault, n, $0.baseAddress!) }
        return d
    }

    public static func setup(passphrase: String, dk: Data? = nil, salt: Data? = nil, code: Data? = nil,
                             iterations: Int = iterations) -> (keys: WrappedKeys, recoveryCode: String, dk: Data)? {
        let salt = salt ?? random(16)
        let code = code ?? random(20)
        let dk = dk ?? random(32)
        guard let kekP = passphraseKek(passphrase, salt: salt, iterations: iterations),
              let wp = wrap(dk, kek: kekP),
              let wr = wrap(dk, kek: recoveryKek(code, salt: salt)) else { return nil }
        let keys = WrappedKeys(key_version: keyVersion, kdf: kdf, iterations: iterations,
                               salt: salt.base64EncodedString(), wrapped_passphrase: wp.base64EncodedString(),
                               wrapped_recovery: wr.base64EncodedString())
        return (keys, encodeRecovery(code), dk)
    }

    public static func unlock(passphrase: String, salt: String, iterations: Int, wrappedPassphrase: String) -> Data? {
        guard let s = Data(base64Encoded: salt), let w = Data(base64Encoded: wrappedPassphrase),
              let kek = passphraseKek(passphrase, salt: s, iterations: iterations) else { return nil }
        return unwrap(w, kek: kek)
    }

    public static func unlock(recoveryCode: String, salt: String, wrappedRecovery: String) -> Data? {
        guard let code = parseRecovery(recoveryCode), let s = Data(base64Encoded: salt),
              let w = Data(base64Encoded: wrappedRecovery) else { return nil }
        return unwrap(w, kek: recoveryKek(code, salt: s))
    }

    /// Neue Passphrase: nur die eine Verpackung; das Salz bleibt (der Code ist mit demselben verpackt).
    public static func rewrap(dk: Data, passphrase: String, salt: String, iterations: Int = iterations) -> String? {
        guard let s = Data(base64Encoded: salt), let kek = passphraseKek(passphrase, salt: s, iterations: iterations),
              let w = wrap(dk, kek: kek) else { return nil }
        return w.base64EncodedString()
    }

    // MARK: Notizen

    public static func aad(targetKind: String, targetKey: String, kind: String) -> Data {
        Data("\(targetKind)|\(targetKey)|\(kind)".utf8)
    }

    /// `(iv, ciphertext)` als Base64; der Klartext ist das JSON-Dokument.
    public static func encrypt(_ plaintext: Data, dk: Data, aad: Data, iv: Data? = nil) -> (iv: String, ciphertext: String)? {
        let ivData = iv ?? random(12)
        guard let nonce = try? AES.GCM.Nonce(data: ivData),
              let box = try? AES.GCM.seal(plaintext, using: SymmetricKey(data: dk), nonce: nonce, authenticating: aad)
        else { return nil }
        return (ivData.base64EncodedString(), (box.ciphertext + box.tag).base64EncodedString())
    }

    /// `nil`, wenn der Schlüssel nicht passt oder Ziel/Text verändert wurden.
    public static func decrypt(iv: String, ciphertext: String, dk: Data, aad: Data) -> Data? {
        guard let ivData = Data(base64Encoded: iv), let ct = Data(base64Encoded: ciphertext), ct.count >= 16,
              let nonce = try? AES.GCM.Nonce(data: ivData),
              let box = try? AES.GCM.SealedBox(nonce: nonce, ciphertext: ct.prefix(ct.count - 16), tag: ct.suffix(16))
        else { return nil }
        return try? AES.GCM.open(box, using: SymmetricKey(data: dk), authenticating: aad)
    }
}
