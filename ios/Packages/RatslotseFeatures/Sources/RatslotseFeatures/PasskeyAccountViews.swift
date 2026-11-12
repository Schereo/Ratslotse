import RatslotseAPI
import RatslotseDesign
import SwiftUI

/// „Passkeys" im Konto (Schalter `passkey-anmeldung`): auflisten, hinzufügen,
/// entfernen — wie `components/konto-passkeys.tsx` im Web. Den letzten Weg ins
/// Konto lässt der Server nicht entfernen; seine Meldung steht dann hier.
struct AccountPasskeysView: View {
    let model: AppModel
    @Environment(\.dismiss) private var dismiss
    @State private var liste: [AccountPasskey]?
    @State private var busy = false
    @State private var error: String?
    @State private var weg: AccountPasskey?

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                RatsSheetHeader("Passkeys", leadingTitle: "Fertig", leadingAction: { dismiss() })
                ScrollView {
                    VStack(alignment: .leading, spacing: 18) {
                        RatsModalIntro(
                            kicker: "Sicherheit",
                            title: "Ohne Passwort",
                            message: "Anmelden mit Face ID, Touch ID oder dem Gerätecode, ohne Passwort. "
                                + "Derselbe Passkey öffnet auch deine Notizen.",
                            symbol: .key
                        )
                        RatsSectionPanel("Deine Passkeys", symbol: .shieldCheck) {
                            if let liste {
                                if liste.isEmpty {
                                    Text("Noch keiner. Leg einen an, dann brauchst du hier kein Passwort mehr.")
                                        .font(RatsFont.body(13))
                                        .foregroundStyle(RatsColor.secondary)
                                }
                                ForEach(liste) { passkey in
                                    zeile(passkey)
                                    if passkey.id != liste.last?.id { Divider().overlay(RatsColor.separator) }
                                }
                            } else if error == nil {
                                ProgressView().tint(RatsColor.primary)
                            }
                        }
                        if let error {
                            RatsLabel(error, .triangleAlert)
                                .font(RatsFont.body(12))
                                .foregroundStyle(RatsColor.danger)
                        }
                        Button { hinzufuegen() } label: {
                            RatsLabel(busy ? "Wartet auf den Passkey …" : "Passkey hinzufügen", .key)
                                .frame(maxWidth: .infinity)
                        }
                        .buttonStyle(PrimaryButtonStyle())
                        .disabled(busy)
                    }
                    .frame(maxWidth: 560, alignment: .leading)
                    .padding(18)
                }
                .background(RatsColor.page)
            }
            .toolbar(.hidden, for: .navigationBar)
            .task { await laden() }
            .confirmationDialog(
                "Passkey „\(weg?.label.isEmpty == false ? weg!.label : "Passkey")“ entfernen?",
                isPresented: Binding(get: { weg != nil }, set: { if !$0 { weg = nil } }),
                titleVisibility: .visible
            ) {
                Button("Entfernen", role: .destructive) { if let weg { entfernen(weg) } }
            } message: {
                Text("Mit ihm kannst du dich danach nicht mehr anmelden. Öffnet er auch deine Notizen, bleibt das — dort entfernst du ihn eigens.")
            }
        }
    }

    private func zeile(_ p: AccountPasskey) -> some View {
        HStack(spacing: 12) {
            RatsIcon(.key, size: 16).foregroundStyle(RatsColor.muted)
            VStack(alignment: .leading, spacing: 2) {
                Text(p.label.isEmpty ? "Passkey" : p.label)
                    .font(RatsFont.body(14, weight: .semibold))
                    .foregroundStyle(RatsColor.text)
                Text(Self.detail(p))
                    .font(RatsFont.body(12))
                    .foregroundStyle(RatsColor.secondary)
            }
            Spacer(minLength: 8)
            Button { weg = p } label: {
                RatsIcon(.trash2, size: 16)
                    .foregroundStyle(RatsColor.muted)
                    .frame(width: 44, height: 44)
            }
            .buttonStyle(RatsPlainButtonStyle())
            .accessibilityLabel("Passkey „\(p.label.isEmpty ? "Passkey" : p.label)“ entfernen")
        }
    }

    /// „Zuletzt 12.11.2026 · auch für Notizen" — die Daten kommen als
    /// ISO-Zeichenkette ohne Zone, für das Datum genügt der Anfang.
    static func detail(_ p: AccountPasskey) -> String {
        let datum = { (iso: String) -> String in
            let teile = iso.prefix(10).split(separator: "-")
            return teile.count == 3 ? "\(teile[2]).\(teile[1]).\(teile[0])" : String(iso.prefix(10))
        }
        var text = p.lastUsedAt.map { "Zuletzt \(datum($0))" } ?? "Seit \(datum(p.createdAt))"
        if p.notes { text += " · auch für Notizen" }
        return text
    }

    private func laden() async {
        do { liste = try await model.loadAccountPasskeys().passkeys }
        catch { self.error = PasskeyError.message(for: error) }
    }

    private func hinzufuegen() {
        busy = true
        error = nil
        Task {
            do {
                liste = try await model.addAccountPasskey().passkeys
                model.alertMessage = "Passkey hinzugefügt."
            } catch { self.error = PasskeyError.message(for: error) }
            busy = false
        }
    }

    private func entfernen(_ p: AccountPasskey) {
        error = nil
        Task {
            do { liste = try await model.removeAccountPasskey(id: p.id).passkeys }
            catch { self.error = PasskeyError.message(for: error) ?? "Entfernen hat nicht geklappt." }
        }
    }
}

/// „Mit Passkey bestätigen" — für Konten ohne Passwort und ohne Apple beim
/// Löschen und beim Adresswechsel. Das Ergebnis geht in denselben Aufruf wie
/// sonst das Passwort.
struct PasskeyConfirmButton: View {
    let model: AppModel
    @Binding var credential: PasskeyAssertionCredential?
    @State private var busy = false
    @State private var error: String?

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            if credential != nil {
                RatsLabel("Mit Passkey bestätigt", .circleCheckBig)
                    .font(RatsFont.body(14, weight: .semibold))
                    .foregroundStyle(RatsColor.success)
            } else {
                Button { bestaetigen() } label: {
                    RatsLabel(busy ? "Wartet auf den Passkey …" : "Mit Passkey bestätigen", .key)
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(SecondaryButtonStyle())
                .disabled(busy)
            }
            if let error {
                Text(error).font(RatsFont.body(12)).foregroundStyle(RatsColor.danger)
            }
        }
    }

    private func bestaetigen() {
        busy = true
        error = nil
        Task {
            do { credential = try await model.passkeyConfirmation() }
            catch { self.error = PasskeyError.message(for: error) }
            busy = false
        }
    }
}
