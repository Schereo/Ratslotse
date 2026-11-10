import RatslotseAPI
import RatslotseDesign
import SwiftUI

/// „Meine Notiz" am Beschluss (Schalter `notizen`, Plan
/// `docs/plan-notizen-app.md` § 3). Dieselben vier Zustände wie im Web:
/// ohne Konto, einrichten, gesperrt, offen. Verschlüsselt wird in
/// `NotesCrypto`; der Server sieht nur Blobs.
struct NoteCard: View {
    let model: AppModel
    let targetKind: String
    let targetKey: String

    @State private var keys: NoteKeysState?
    @State private var fehler: String?

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Text("Meine Notiz").font(RatsFont.body(16, weight: .semibold)).foregroundStyle(RatsColor.text)
                Spacer()
                if model.notesKey != nil, model.user != nil {
                    Button { model.lockNotes() } label: { RatsLabel("Sperren", .lock) }
                        .font(RatsFont.body(12)).foregroundStyle(RatsColor.muted)
                        .accessibilityHint("Sperrt die Notizen auf diesem Gerät")
                } else {
                    Text("MIT KONTO").font(RatsFont.mono(10)).foregroundStyle(RatsColor.muted)
                }
            }
            inhalt
            Label {
                Text("Wird auf deinem Gerät verschlüsselt, bevor sie gespeichert wird. Ratslotse sieht nur den verschlüsselten Text.")
            } icon: { RatsIcon(.lock, size: 12) }
                .font(RatsFont.body(12)).foregroundStyle(RatsColor.muted)
        }
        .ratsCard()
        .task(id: model.user?.id) { await laden() }
    }

    @ViewBuilder private var inhalt: some View {
        if model.user == nil {
            Text("Mit einem Konto kannst du dir zu diesem Beschluss etwas notieren — nur für dich lesbar.")
                .font(RatsFont.body(14)).foregroundStyle(RatsColor.secondary)
        } else if let fehler {
            Text(fehler).font(RatsFont.body(14)).foregroundStyle(RatsColor.secondary)
        } else if let keys {
            if let k = keys.keys, keys.configured {
                if let dk = model.notesKey {
                    NoteEditor(model: model, dk: dk, keyVersion: k.keyVersion, targetKind: targetKind, targetKey: targetKey)
                } else {
                    NoteUnlock(model: model, keys: k) { neu in self.keys = neu }
                }
            } else {
                NoteSetup(model: model) { neu in self.keys = neu }
            }
        } else {
            ProgressView()
        }
    }

    private func laden() async {
        #if DEBUG
        // Visual QA ohne Backend (`RATSLOTSE_DEBUG_NOTES=einrichten|gesperrt`,
        // wie die übrigen `RATSLOTSE_DEBUG_*`-Schalter in NativeRootView).
        if let stand = ratsDebugValue("RATSLOTSE_DEBUG_NOTES") {
            let json = stand == "einrichten" ? #"{"configured":false,"keys":null}"#
                : #"{"configured":true,"keys":{"key_version":1,"kdf":"pbkdf2-sha256","iterations":600000,"salt":"IiIiIiIiIiIiIiIiIiIiIg==","wrapped_passphrase":"KZBQ5RLifL4peGycImj2c/TFMBLLQD6pyJn5xC+fiNRbFyGjeDlT9A==","wrapped_recovery":"9HwcefHPWDI9QlFn+K8vRoyz3naFbfeXB9Ea5l/dfpcD/68sZgdhgw==","updated_at":"2026-11-10T17:00:00"}}"#
            keys = try? JSONDecoder().decode(NoteKeysState.self, from: Data(json.utf8))
            return
        }
        #endif
        guard let owner = model.user?.id else { return }
        model.restoreNotesKey(owner: owner)
        do {
            let state: NoteKeysState = try await model.api.get("/api/notes/keys")
            keys = state
        } catch {
            fehler = (error as? APIError)?.message ?? "Notizen lassen sich gerade nicht laden."
        }
    }
}

private let feld = RoundedRectangle(cornerRadius: 12, style: .continuous)

private struct NoteSetup: View {
    let model: AppModel
    let fertig: (NoteKeysState) -> Void
    @State private var offen = false
    @State private var p1 = ""
    @State private var p2 = ""
    @State private var merken = true
    @State private var entwurf: (keys: NotesCrypto.WrappedKeys, recoveryCode: String, dk: Data)?
    @State private var abgetippt = ""
    @State private var arbeit = false
    @State private var fehler: String?

    var body: some View {
        if !offen {
            VStack(alignment: .leading, spacing: 10) {
                Text("Notiere dir, was du zu diesem Beschluss wissen oder nachfragen willst. Nur du kannst es lesen.")
                    .font(RatsFont.body(14)).foregroundStyle(RatsColor.secondary)
                Button("Notizen einrichten") { offen = true }.buttonStyle(PrimaryButtonStyle())
            }
        } else if let entwurf {
            VStack(alignment: .leading, spacing: 10) {
                Text("Dein Wiederherstellungscode. Schreib ihn auf. Wer Passphrase und Code verliert, verliert die Notizen — niemand kann sie zurückholen.")
                    .font(RatsFont.body(14)).foregroundStyle(RatsColor.bodyText)
                Text(entwurf.recoveryCode).font(RatsFont.mono(14)).textSelection(.enabled)
                    .frame(maxWidth: .infinity).padding(10).background(RatsColor.stage, in: feld)
                    .accessibilityLabel("Wiederherstellungscode \(entwurf.recoveryCode)")
                TextField("Zur Sicherheit einmal abtippen", text: $abgetippt)
                    .textInputAutocapitalization(.characters).autocorrectionDisabled()
                    .font(RatsFont.mono(14)).padding(10).overlay(feld.stroke(RatsColor.border))
                if let fehler { Text(fehler).font(RatsFont.body(13)).foregroundStyle(RatsColor.danger) }
                Button(arbeit ? "Speichert …" : "Notizen einrichten") {
                    Task { await einrichten(entwurf) }
                }
                .buttonStyle(PrimaryButtonStyle())
                .disabled(arbeit || NotesCrypto.parseRecovery(abgetippt) != NotesCrypto.parseRecovery(entwurf.recoveryCode))
            }
        } else {
            VStack(alignment: .leading, spacing: 10) {
                Text("Deine Notizen schließt eine eigene Notiz-Passphrase auf — nicht dein Anmeldepasswort.")
                    .font(RatsFont.body(14)).foregroundStyle(RatsColor.bodyText)
                SecureField("Notiz-Passphrase (mindestens 10 Zeichen)", text: $p1)
                    .textContentType(.newPassword).padding(10).overlay(feld.stroke(RatsColor.border))
                SecureField("Noch einmal", text: $p2)
                    .textContentType(.newPassword).padding(10).overlay(feld.stroke(RatsColor.border))
                Toggle("Auf diesem Gerät merken", isOn: $merken).font(RatsFont.body(14))
                Button(arbeit ? "Rechnet …" : "Weiter") {
                    arbeit = true
                    let pass = p1
                    Task.detached {
                        let r = NotesCrypto.setup(passphrase: pass)
                        await MainActor.run { entwurf = r; arbeit = false }
                    }
                }
                .buttonStyle(PrimaryButtonStyle())
                .disabled(arbeit || p1.count < 10 || p1 != p2)
                .opacity(arbeit || p1.count < 10 || p1 != p2 ? 0.55 : 1)
            }
        }
    }

    private func einrichten(_ e: (keys: NotesCrypto.WrappedKeys, recoveryCode: String, dk: Data)) async {
        arbeit = true
        defer { arbeit = false }
        do {
            let state: NoteKeysState = try await model.api.send("/api/notes/keys", method: .put, body: e.keys)
            model.setNotesKey(e.dk, remember: merken)
            fertig(state)
        } catch {
            fehler = (error as? APIError)?.message ?? "Einrichten hat nicht geklappt."
        }
    }
}

private struct NoteUnlock: View {
    let model: AppModel
    let keys: NoteKeys
    let neueKeys: (NoteKeysState) -> Void
    @State private var pass = ""
    @State private var merken = true
    @State private var vergessen = false
    @State private var code = ""
    @State private var neu = ""
    @State private var arbeit = false
    @State private var fehler: String?

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            if vergessen {
                TextField("Wiederherstellungscode", text: $code)
                    .textInputAutocapitalization(.characters).autocorrectionDisabled()
                    .font(RatsFont.mono(14)).padding(10).overlay(feld.stroke(RatsColor.border))
                SecureField("Neue Notiz-Passphrase (mindestens 10 Zeichen)", text: $neu)
                    .textContentType(.newPassword).padding(10).overlay(feld.stroke(RatsColor.border))
            } else {
                SecureField("Notiz-Passphrase", text: $pass)
                    .textContentType(.password).padding(10).overlay(feld.stroke(RatsColor.border))
            }
            Toggle("Auf diesem Gerät merken", isOn: $merken).font(RatsFont.body(14))
            if let fehler { Text(fehler).font(RatsFont.body(13)).foregroundStyle(RatsColor.danger) }
            HStack {
                Button(arbeit ? "Rechnet …" : (vergessen ? "Neue Passphrase setzen" : "Entsperren")) {
                    Task { await los() }
                }
                .buttonStyle(PrimaryButtonStyle())
                .disabled(arbeit || (vergessen ? neu.count < 10 || code.isEmpty : pass.isEmpty))
                .opacity(arbeit || (vergessen ? neu.count < 10 || code.isEmpty : pass.isEmpty) ? 0.55 : 1)
                Button(vergessen ? "Zurück" : "Passphrase vergessen?") { vergessen.toggle(); fehler = nil }
                    .font(RatsFont.body(14, weight: .medium)).foregroundStyle(RatsColor.primary)
            }
        }
    }

    private func los() async {
        arbeit = true
        defer { arbeit = false }
        fehler = nil
        let k = keys
        if vergessen {
            let (c, n) = (code, neu)
            let dk: Data? = await Task.detached {
                NotesCrypto.unlock(recoveryCode: c, salt: k.salt, wrappedRecovery: k.wrappedRecovery)
            }.value
            guard let dk else { fehler = "Dieser Code passt nicht."; return }
            let neuVerpackt: String? = await Task.detached {
                NotesCrypto.rewrap(dk: dk, passphrase: n, salt: k.salt, iterations: k.iterations)
            }.value
            guard let w = neuVerpackt else { fehler = "Das hat nicht geklappt."; return }
            do {
                let body = NoteKeysRewrap(keyVersion: k.keyVersion, iterations: k.iterations, salt: k.salt, wrappedPassphrase: w)
                let state: NoteKeysState = try await model.api.send("/api/notes/keys", method: .put, body: body)
                neueKeys(state)
                model.setNotesKey(dk, remember: merken)
            } catch {
                fehler = (error as? APIError)?.message ?? "Das hat nicht geklappt."
            }
        } else {
            let p = pass
            let dk: Data? = await Task.detached {
                NotesCrypto.unlock(passphrase: p, salt: k.salt, iterations: k.iterations, wrappedPassphrase: k.wrappedPassphrase)
            }.value
            guard let dk else { fehler = "Diese Passphrase passt nicht."; return }
            pass = ""
            model.setNotesKey(dk, remember: merken)
        }
    }
}

private struct NoteEditor: View {
    let model: AppModel
    let dk: Data
    let keyVersion: Int
    let targetKind: String
    let targetKey: String

    @State private var text = ""
    @State private var gespeichert = ""
    @State private var version = 0
    @State private var status: String?
    @State private var geladen = false
    @State private var konflikt = false

    private var pfad: String { "/api/notes/\(targetKind)/\(targetKey)/note" }
    private var aad: Data { NotesCrypto.aad(targetKind: targetKind, targetKey: targetKey, kind: "note") }

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            TextEditor(text: $text)
                .font(RatsFont.body(14)).frame(minHeight: 110).padding(6)
                .overlay(feld.stroke(RatsColor.border))
                .disabled(!geladen)
                .accessibilityLabel("Meine Notiz zu diesem Beschluss")
            if konflikt {
                VStack(alignment: .leading, spacing: 6) {
                    Text("Auf einem anderen Gerät wurde diese Notiz inzwischen geändert.").font(RatsFont.body(13))
                    HStack {
                        Button("Diese Fassung laden") { Task { await laden() } }
                        Button("Meine behalten") { Task { await speichern(erzwingen: true) } }
                    }
                    .font(RatsFont.body(13, weight: .medium)).foregroundStyle(RatsColor.primary)
                }
                .padding(10).background(RatsColor.warningTint, in: feld)
            }
            if let status { Text(status).font(RatsFont.mono(10)).foregroundStyle(RatsColor.muted) }
        }
        .task(id: targetKey) { await laden() }
        .task(id: text) {
            // 1,5 s Ruhe nach dem Tippen, dann verschlüsselt hinaus.
            guard geladen, text != gespeichert else { return }
            try? await Task.sleep(for: .milliseconds(1500))
            guard !Task.isCancelled else { return }
            await speichern()
        }
    }

    private func laden() async {
        konflikt = false
        do {
            let list: NoteList = try await model.api.get(
                "/api/notes", query: [URLQueryItem(name: "target_kind", value: targetKind),
                                      URLQueryItem(name: "target_key", value: targetKey)])
            if let n = list.notes.first(where: { $0.kind == "note" }),
               let klar = NotesCrypto.decrypt(iv: n.iv, ciphertext: n.ciphertext, dk: dk, aad: aad),
               let doc = try? JSONDecoder().decode(NoteDocument.self, from: klar) {
                text = doc.text
                version = n.version
            } else {
                text = ""
                version = list.notes.first(where: { $0.kind == "note" })?.version ?? 0
            }
            gespeichert = text
            geladen = true
        } catch {
            status = "Die Notiz lässt sich gerade nicht laden."
        }
    }

    private func speichern(erzwingen: Bool = false) async {
        if erzwingen {
            // Den aktuellen Stand holen, nur um seine Version zu kennen.
            if let list: NoteList = try? await model.api.get(
                "/api/notes", query: [URLQueryItem(name: "target_kind", value: targetKind),
                                      URLQueryItem(name: "target_key", value: targetKey)]) {
                version = list.notes.first(where: { $0.kind == "note" })?.version ?? 0
            }
            konflikt = false
        }
        status = "Speichert …"
        do {
            if text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                if version > 0 { try await model.api.sendVoid(pfad, method: .delete) }
                version = 0
                gespeichert = text
                status = "Gelöscht"
                return
            }
            let klar = try JSONEncoder().encode(NoteDocument(text: text))
            guard let blob = NotesCrypto.encrypt(klar, dk: dk, aad: aad) else { status = "Nicht gespeichert."; return }
            let upload = NoteUpload(iv: blob.iv, ciphertext: blob.ciphertext, keyVersion: keyVersion, version: version)
            let entry: NoteEntry = try await model.api.send(pfad, method: .put, body: upload)
            version = entry.version
            gespeichert = text
            status = "Gespeichert"
        } catch let e as APIError where e.statusCode == 409 {
            konflikt = true
            status = nil
        } catch {
            status = "Nicht gespeichert — Verbindung prüfen."
        }
    }
}
