import CryptoKit
import Foundation
import Testing
@testable import RatslotseAPI

/// Mit Passkey anmelden (`Passkeys.swift`). Die Vektoren sind dieselben wie im
/// Web (`web/frontend/lib/passkey.test.ts`, `lib/notiz-passkey.test.ts`) —
/// sonst schlösse derselbe Passkey im Browser auf und in der App nicht.
struct PasskeysTests {
    /// So schickt `py_webauthn` 3.0.1 die Optionen (`options_to_json`), mit
    /// festen Bytes erzeugt — keine Nachbildung von Hand.
    static let erstellOptionen = #"{"public_key":{"rp": {"name": "Ratslotse", "id": "ratslotse.de"}, "user": {"id": "AAECAwQFBgcICQoLDA0ODw", "name": "lotti@example.org", "displayName": "Lotti"}, "challenge": "BwcHBwcHBwcHBwcHBwcHBwcHBwcHBwcHBwcHBwcHBwc", "pubKeyCredParams": [{"type": "public-key", "alg": -8}, {"type": "public-key", "alg": -7}, {"type": "public-key", "alg": -257}], "timeout": 120000, "excludeCredentials": [{"id": "AQID-_8", "type": "public-key"}], "authenticatorSelection": {"residentKey": "required", "requireResidentKey": true, "userVerification": "required"}, "attestation": "none"}}"#
    static let abfrageOptionen = #"{"public_key":{"challenge": "CQkJCQkJCQkJCQkJCQkJCQkJCQkJCQkJCQkJCQkJCQk", "timeout": 120000, "rpId": "ratslotse.de", "allowCredentials": [], "userVerification": "required"}}"#

    static func fill(_ n: Int, _ b: UInt8) -> Data { Data(repeating: b, count: n) }

    @Test func anmeldeSalzIstDasDesWebs() {
        let roh = Data(SHA256.hash(data: Data("ratslotse-passkey-notizen-v1".utf8)))
        #expect(Passkeys.loginSalt == roh)
        #expect(Passkeys.loginSaltB64 == "5MnwhF9xlXWJRKjXOzZmPPe88kNNx+zhKCJHRsu15G4=")
    }

    @Test func schluesselAusDemPrfGeheimnisWieImBrowser() throws {
        // WebCrypto: HKDF-SHA-256 (Salz leer, Info „ratslotse-notizen-passkey“)
        // aus 32 × 0x5a, damit DK = 32 × 0x11 per AES-KW verpackt.
        let kek = Passkeys.kek(prf: Self.fill(32, 0x5a))
        let verpackt = try #require(NotesCrypto.wrap(Self.fill(32, 0x11), kek: kek))
        #expect(verpackt.base64EncodedString() == "waaUYZJ0tt9nEz/QzsW1KcByiM15SL79fCqUXiHHzi+Kn7T2/i5PwA==")
        #expect(NotesCrypto.unwrap(verpackt, kek: Passkeys.kek(prf: Self.fill(32, 0x5b))) == nil)
    }

    @Test func base64urlOhneAuffuellung() {
        #expect(Base64URL.encode(Data([1, 2, 3])) == "AQID")
        #expect(Base64URL.encode(Data([0xfb, 0xff])) == "-_8")
        #expect(Base64URL.encode(Data([0xff, 0xfe])) == "__4")
        #expect(Base64URL.decode("AQID-_8") == Data([1, 2, 3, 0xfb, 0xff]))
        #expect(Base64URL.decode("AAECAwQFBgcICQoLDA0ODw") == Data(0..<16))
    }

    @Test func optionenDesServersLesen() throws {
        let erstellen = try JSONDecoder().decode(PasskeyCreationEnvelope.self,
                                                 from: Data(Self.erstellOptionen.utf8)).publicKey
        #expect(erstellen.rp.id == "ratslotse.de")
        #expect(erstellen.challengeData == Self.fill(32, 7))
        #expect(erstellen.userID == Data(0..<16))
        #expect(erstellen.user.name == "lotti@example.org" && erstellen.user.displayName == "Lotti")
        #expect(erstellen.excludeCredentials.map(\.id) == ["AQID-_8"])

        let abfragen = try JSONDecoder().decode(PasskeyRequestEnvelope.self,
                                                from: Data(Self.abfrageOptionen.utf8)).publicKey
        #expect(abfragen.rpId == "ratslotse.de")
        #expect(abfragen.challengeData == Self.fill(32, 9))
        #expect(abfragen.allowCredentials.isEmpty)
    }

    @Test func registrierungGehtOhnePrfAnDenServer() throws {
        let c = PasskeyRegistrationCredential(credentialID: Data([1, 2, 3]), clientDataJSON: Data([123, 125]),
                                              attestationObject: Data([0xa0]))
        let json = try JSONEncoder().encode(PasskeyRegistrationBody(credential: c, label: "iPhone"))
        let obj = try #require(try JSONSerialization.jsonObject(with: json) as? [String: Any])
        let cred = try #require(obj["credential"] as? [String: Any])
        #expect(Set(cred.keys) == ["id", "rawId", "type", "response"])
        #expect(cred["id"] as? String == "AQID" && cred["rawId"] as? String == "AQID")
        #expect(cred["type"] as? String == "public-key")
        let response = try #require(cred["response"] as? [String: Any])
        #expect(response["clientDataJSON"] as? String == "e30")
        #expect(response["attestationObject"] as? String == "oA")
        #expect(response["transports"] as? [String] == ["hybrid", "internal"])
        #expect(!String(decoding: json, as: UTF8.self).contains("prf"))
    }

    @Test func anmeldungGehtOhnePrfAnDenServer() throws {
        let c = PasskeyAssertionCredential(credentialID: Data([1, 2, 3]), clientDataJSON: Data([123, 125]),
                                           authenticatorData: Data([1]), signature: Data([0xfb, 0xff]),
                                           userID: Data([0xff, 0xfe]))
        let json = try JSONEncoder().encode(PasskeyLoginBody(credential: c))
        let obj = try #require(try JSONSerialization.jsonObject(with: json) as? [String: Any])
        let cred = try #require(obj["credential"] as? [String: Any])
        #expect(Set(cred.keys) == ["id", "rawId", "type", "response"])
        let response = try #require(cred["response"] as? [String: String])
        #expect(response == ["clientDataJSON": "e30", "authenticatorData": "AQ", "signature": "-_8", "userHandle": "__4"])
        #expect(!String(decoding: json, as: UTF8.self).contains("prf"))
    }

    @Test func kontoPasskeysLesen() throws {
        let json = #"{"passkeys":[{"id":4,"credential_id":"AQID-_8xxxxxxxxxxxxx","label":"iPhone","created_at":"2026-11-12T08:00:00","last_used_at":null,"backed_up":true,"notes":true}]}"#
        let liste = try JSONDecoder().decode(AccountPasskeyList.self, from: Data(json.utf8))
        #expect(liste.passkeys.first?.label == "iPhone")
        #expect(liste.passkeys.first?.lastUsedAt == nil && liste.passkeys.first?.notes == true)
    }

    // MARK: Notizen mit derselben Abfrage

    static func state(configured: Bool, passkeys: [NotePasskey]) -> NoteKeysState {
        let keys = NoteKeys(keyVersion: 1, kdf: NotesCrypto.kdf, iterations: NotesCrypto.iterations,
                            salt: "IiIiIiIiIiIiIiIiIiIiIg==", wrappedPassphrase: nil, wrappedRecovery: nil,
                            updatedAt: "2026-11-12T08:00:00")
        return NoteKeysState(configured: configured, keys: configured ? keys : nil, passkeys: passkeys)
    }

    static func zeile(_ credentialId: String, salt: String = Passkeys.loginSaltB64, wrapped: String) -> NotePasskey {
        NotePasskey(id: 1, credentialId: credentialId, prfSalt: salt, wrappedKey: wrapped,
                    label: "iPhone", createdAt: "2026-11-12T08:00:00")
    }

    @Test func nochNichtsEingerichtetHeisstStillEinrichten() {
        let kek = Passkeys.kek(prf: Self.fill(32, 0x5a))
        #expect(NotesPasskeyPlan.decide(state: Self.state(configured: false, passkeys: []), credentialId: "a", kek: kek) == .setup)
    }

    @Test func mitDiesemPasskeyEingerichtetHeisstOffen() throws {
        let dk = Self.fill(32, 0x11)
        let kek = Passkeys.kek(prf: Self.fill(32, 0x5a))
        let wrap = try #require(NotePasskeyWrap(credentialId: "cred-a", dk: dk, kek: kek, label: "iPhone"))
        let state = Self.state(configured: true, passkeys: [Self.zeile("cred-a", wrapped: wrap.wrapped_key)])
        #expect(NotesPasskeyPlan.decide(state: state, credentialId: "cred-a", kek: kek) == .unlock(dk))
        // Ein anderer Passkey, oder derselbe als reiner Notiz-Passkey mit
        // eigenem Salz: merken, nicht öffnen.
        #expect(NotesPasskeyPlan.decide(state: state, credentialId: "cred-b", kek: kek) == .remember)
        let anderesSalz = Self.state(configured: true, passkeys: [Self.zeile("cred-a", salt: "BwcH", wrapped: wrap.wrapped_key)])
        #expect(NotesPasskeyPlan.decide(state: anderesSalz, credentialId: "cred-a", kek: kek) == .remember)
        // Und ein Geheimnis, das nicht passt, öffnet nichts.
        #expect(NotesPasskeyPlan.decide(state: state, credentialId: "cred-a",
                                        kek: Passkeys.kek(prf: Self.fill(32, 0x5b))) == .remember)
    }

    @Test func einrichtenHaeltDieFormDesServers() throws {
        let wrap = try #require(NotePasskeyWrap(credentialId: "cred-a", dk: Self.fill(32, 0x11),
                                                kek: Passkeys.kek(prf: Self.fill(32, 0x5a)), label: "iPhone"))
        let setup = try JSONSerialization.jsonObject(with: JSONEncoder().encode(NoteKeysWithPasskey(passkey: wrap))) as? [String: Any]
        #expect(Set(setup?.keys.map { $0 } ?? []) == ["key_version", "kdf", "iterations", "salt", "passkey"])
        #expect(Data(base64Encoded: setup?["salt"] as? String ?? "")?.count == 16)
        let passkey = setup?["passkey"] as? [String: String]
        #expect(Set(passkey?.keys.map { $0 } ?? []) == ["credential_id", "prf_salt", "wrapped_key", "label"])
        #expect(passkey?["prf_salt"] == Passkeys.loginSaltB64)

        let add = try JSONSerialization.jsonObject(with: JSONEncoder().encode(NotePasskeyAdd(wrap, keyVersion: 2))) as? [String: Any]
        #expect(Set(add?.keys.map { $0 } ?? []) == ["credential_id", "prf_salt", "wrapped_key", "label", "key_version"])
        #expect(add?["key_version"] as? Int == 2)
    }
}
