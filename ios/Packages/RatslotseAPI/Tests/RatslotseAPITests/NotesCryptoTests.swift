import Foundation
import Testing
@testable import RatslotseAPI

/// Dieselben Testvektoren wie `web/frontend/lib/notiz-krypto.test.ts` — der
/// Vertrag zwischen Web und App (Plan `docs/plan-notizen-app.md` § 2).
/// Eingaben: DK = 32 × 0x11, Salz = 16 × 0x22, Code = 20 × 0x33,
/// IV = 12 × 0x44, 600.000 Runden.
struct NotesCryptoTests {
    static let pass = "korrekt Pferd Batterie Heftklammer"
    static let salt = "IiIiIiIiIiIiIiIiIiIiIg=="
    static let wrappedPassphrase = "KZBQ5RLifL4peGycImj2c/TFMBLLQD6pyJn5xC+fiNRbFyGjeDlT9A=="
    static let wrappedRecovery = "9HwcefHPWDI9QlFn+K8vRoyz3naFbfeXB9Ea5l/dfpcD/68sZgdhgw=="
    static let code = "6CSK-6CSK-6CSK-6CSK-6CSK-6CSK-6CSK-6CSK"
    static let iv = "RERERERERERERERE"
    static let ciphertext = "t2c8CzJMBg3L3v7+QIwFjf+vogGYRlCkozaPQw77GOslQbf6gzCYHfo/jpJlYbwJEEk5"
    static let ziel = NotesCrypto.aad(targetKind: "agenda_item", targetKey: "4654|Ö 11.1", kind: "note")
    /// Genau die Bytes von `JSON.stringify({ text: … })` im Web.
    static let klar = Data(#"{"text":"Nachfragen: Kosten 2027?"}"#.utf8)

    static func fill(_ n: Int, _ b: UInt8) -> Data { Data(repeating: b, count: n) }
    static func hex(_ s: String) -> Data {
        var d = Data()
        var i = s.startIndex
        while i < s.endIndex {
            let j = s.index(i, offsetBy: 2)
            d.append(UInt8(s[i..<j], radix: 16)!)
            i = j
        }
        return d
    }

    @Test func pbkdf2NachRFC7914() {
        let out = NotesCrypto.passphraseKek("passwd", salt: Data("salt".utf8), iterations: 1)
        // RFC 7914 § 11 nennt 64 Byte; die ersten 32 sind dieselben.
        #expect(out == Self.hex("55ac046e56e3089fec1691c22544b605f94185216dde0465e68b9d57c20dacbc"))
    }

    @Test func aesKwNachRFC3394() {
        let kek = Self.hex("000102030405060708090A0B0C0D0E0F101112131415161718191A1B1C1D1E1F")
        let daten = Self.hex("00112233445566778899AABBCCDDEEFF000102030405060708090A0B0C0D0E0F")
        let erwartet = Self.hex("28C9F404C4B810F4CBCCB35CFB87F8263F5786E2D80ED326CBC7F0E71A99F43BFB988B9B7A02DD21")
        #expect(NotesCrypto.wrap(daten, kek: kek) == erwartet)
        #expect(NotesCrypto.unwrap(erwartet, kek: kek) == daten)
    }

    @Test func dieselbenBytesWieImWeb() throws {
        let r = try #require(NotesCrypto.setup(passphrase: Self.pass, dk: Self.fill(32, 0x11),
                                               salt: Self.fill(16, 0x22), code: Self.fill(20, 0x33)))
        #expect(r.keys.salt == Self.salt)
        #expect(r.keys.wrapped_passphrase == Self.wrappedPassphrase)
        #expect(r.keys.wrapped_recovery == Self.wrappedRecovery)
        #expect(r.recoveryCode == Self.code)
        let n = try #require(NotesCrypto.encrypt(Self.klar, dk: r.dk, aad: Self.ziel, iv: Self.fill(12, 0x44)))
        #expect(n.iv == Self.iv)
        #expect(n.ciphertext == Self.ciphertext)
    }

    @Test func eineImWebGeschriebeneNotizLesen() throws {
        let dk = try #require(NotesCrypto.unlock(passphrase: Self.pass, salt: Self.salt, iterations: 600_000,
                                                 wrappedPassphrase: Self.wrappedPassphrase))
        #expect(NotesCrypto.decrypt(iv: Self.iv, ciphertext: Self.ciphertext, dk: dk, aad: Self.ziel) == Self.klar)
        #expect(NotesCrypto.unlock(passphrase: "korrekt Pferd Batterie", salt: Self.salt, iterations: 600_000,
                                   wrappedPassphrase: Self.wrappedPassphrase) == nil)
    }

    @Test func wiederherstellungUndNeuePassphrase() throws {
        let dk = try #require(NotesCrypto.unlock(recoveryCode: "6csk 6csk-6CSK6CSK 6CSK-6CSK-6CSK-6CSK",
                                                 salt: Self.salt, wrappedRecovery: Self.wrappedRecovery))
        #expect(NotesCrypto.unlock(recoveryCode: "6CSK-6CSK-6CSK-6CSK-6CSK-6CSK-6CSK-6CSM",
                                   salt: Self.salt, wrappedRecovery: Self.wrappedRecovery) == nil)
        let neu = try #require(NotesCrypto.rewrap(dk: dk, passphrase: "ganz neue Passphrase", salt: Self.salt))
        let wieder = try #require(NotesCrypto.unlock(passphrase: "ganz neue Passphrase", salt: Self.salt,
                                                     iterations: 600_000, wrappedPassphrase: neu))
        #expect(NotesCrypto.decrypt(iv: Self.iv, ciphertext: Self.ciphertext, dk: wieder, aad: Self.ziel) == Self.klar)
    }

    @Test func umgehaengteNotizBleibtZu() throws {
        let dk = Self.fill(32, 0x11)
        let fremd = NotesCrypto.aad(targetKind: "agenda_item", targetKey: "4654|Ö 9", kind: "note")
        #expect(NotesCrypto.decrypt(iv: Self.iv, ciphertext: Self.ciphertext, dk: dk, aad: fremd) == nil)
    }

    @Test func codeHinUndZurueck() {
        let roh = NotesCrypto.random(20)
        let code = NotesCrypto.encodeRecovery(roh)
        #expect(code.count == 39)
        #expect(NotesCrypto.parseRecovery(code) == roh)
        #expect(NotesCrypto.parseRecovery("UUUU-UUUU-UUUU-UUUU-UUUU-UUUU-UUUU-UUUU") == nil)
    }
}
