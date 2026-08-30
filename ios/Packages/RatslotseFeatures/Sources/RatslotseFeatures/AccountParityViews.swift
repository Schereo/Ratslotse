import RatslotseAPI
import RatslotseDesign
import SwiftUI

struct ConversationSettingsCard: View {
    let model: AppModel
    @State private var setting: Int?
    @State private var conversationCount = 0
    @State private var isLoading = true
    @State private var isSaving = false
    @State private var asksAboutExisting = false
    @State private var confirmsDeletion = false
    @State private var error: String?

    var body: some View {
        RatsSectionPanel(
            "Gespräche",
            detail: "Deine Ratsgespräche können auf allen Geräten im Konto bereitstehen.",
            symbol: "bubble.left.and.bubble.right.fill"
        ) {
            if isLoading {
                HStack(spacing: 10) {
                    ProgressView().tint(RatsColor.primary)
                    Text("Einstellung wird geladen …")
                        .font(RatsFont.body(12))
                        .foregroundStyle(RatsColor.secondary)
                }
                .frame(minHeight: 46)
            } else {
                HStack(alignment: .center, spacing: 12) {
                    VStack(alignment: .leading, spacing: 3) {
                        Text("Gespräche speichern")
                            .font(RatsFont.body(14, weight: .semibold))
                            .foregroundStyle(RatsColor.text)
                        Text(conversationCount == 1 ? "1 Gespräch gespeichert" : "\(conversationCount) Gespräche gespeichert")
                            .font(RatsFont.body(11))
                            .foregroundStyle(RatsColor.secondary)
                    }
                    Spacer(minLength: 8)
                    HStack(spacing: 3) {
                        choice("An", value: 1)
                        choice("Aus", value: 0)
                    }
                    .padding(3)
                    .background(RatsColor.stage)
                    .clipShape(Capsule())
                }

                if setting == nil {
                    Text("Noch nicht entschieden – Lotti fragt dich beim nächsten Ratsgespräch.")
                        .font(RatsFont.body(11))
                        .foregroundStyle(RatsColor.muted)
                }

                if asksAboutExisting {
                    VStack(alignment: .leading, spacing: 9) {
                        Text("Speichern ist aus")
                            .font(RatsFont.body(13, weight: .semibold))
                            .foregroundStyle(RatsColor.text)
                        Text("Sollen die bisherigen \(conversationCount) Gespräche im Konto bleiben?")
                            .font(RatsFont.body(11))
                            .foregroundStyle(RatsColor.secondary)
                        HStack(spacing: 8) {
                            Button("Behalten") { asksAboutExisting = false }
                                .buttonStyle(SecondaryButtonStyle())
                            Button(role: .destructive) { confirmsDeletion = true } label: {
                                Text("Alle löschen")
                            }
                            .buttonStyle(SecondaryButtonStyle())
                        }
                    }
                    .padding(12)
                    .background(RatsColor.stage)
                    .overlay(RoundedRectangle(cornerRadius: 12).stroke(RatsColor.border))
                    .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
                } else if conversationCount > 0 {
                    Button(role: .destructive) { confirmsDeletion = true } label: {
                        Label("Alle gespeicherten Gespräche löschen", systemImage: "trash")
                            .font(RatsFont.body(12, weight: .semibold))
                    }
                    .foregroundStyle(RatsColor.danger)
                }

                Divider().overlay(RatsColor.separator)
                HStack(alignment: .top, spacing: 9) {
                    Image(systemName: "sparkles")
                        .font(.system(size: 11, weight: .semibold))
                        .foregroundStyle(RatsColor.signal)
                        .padding(.top, 2)
                    Text("Frage und passende Ratsauszüge werden über OpenRouter extern verarbeitet; eine Drittlandverarbeitung ist möglich. Bitte keine personenbezogenen oder sensiblen Daten eingeben.")
                        .font(RatsFont.body(10))
                        .foregroundStyle(RatsColor.muted)
                        .lineSpacing(2)
                }
            }

            if let error {
                Text(error)
                    .font(RatsFont.body(11, weight: .medium))
                    .foregroundStyle(RatsColor.danger)
            }
        }
        .task { await load() }
        .confirmationDialog(
            "Alle Gespräche löschen?",
            isPresented: $confirmsDeletion,
            titleVisibility: .visible
        ) {
            Button("Alle Gespräche löschen", role: .destructive) {
                Task { await deleteAll() }
            }
            Button("Abbrechen", role: .cancel) {}
        } message: {
            Text("Die gespeicherten Gespräche werden dauerhaft aus deinem Konto entfernt.")
        }
    }

    private func choice(_ title: String, value: Int) -> some View {
        Button {
            Task { await set(value) }
        } label: {
            Text(title)
                .font(RatsFont.body(11, weight: .semibold))
                .foregroundStyle(setting == value ? RatsColor.primaryText : RatsColor.secondary)
                .padding(.horizontal, 12)
                .frame(minHeight: 30)
                .background(setting == value ? RatsColor.primary : Color.clear)
                .clipShape(Capsule())
        }
        .buttonStyle(RatsPlainButtonStyle())
        .disabled(isSaving)
        .accessibilityAddTraits(setting == value ? .isSelected : [])
    }

    private func load() async {
        isLoading = true
        defer { isLoading = false }
        do {
            let response: JSONValue = try await model.api.get("/api/council/gespraeche")
            setting = response.object?["einstellung"]?.int ?? model.conversationSavingPreference
            conversationCount = response.object?["gespraeche"]?.array?.count ?? 0
            error = nil
        } catch {
            self.error = error.localizedDescription
        }
    }

    private func set(_ value: Int) async {
        guard setting != value, !isSaving else { return }
        let previous = setting
        setting = value
        isSaving = true
        defer { isSaving = false }
        do {
            try await model.setConversationSaving(value == 1)
            asksAboutExisting = value == 0 && conversationCount > 0
            error = nil
        } catch {
            setting = previous
            self.error = "Die Einstellung konnte nicht gespeichert werden."
        }
    }

    private func deleteAll() async {
        isSaving = true
        defer { isSaving = false }
        do {
            try await model.api.sendVoid("/api/council/gespraeche", method: .delete)
            conversationCount = 0
            asksAboutExisting = false
            error = nil
        } catch {
            self.error = "Die Gespräche konnten nicht gelöscht werden."
        }
    }
}

struct AppearanceSettingsCard: View {
    let model: AppModel
    private let columns = [GridItem(.adaptive(minimum: 96), spacing: 9)]

    var body: some View {
        RatsSectionPanel(
            "Erscheinungsbild",
            detail: "Automatisch folgt der Einstellung deines Geräts.",
            symbol: "circle.lefthalf.filled"
        ) {
            LazyVGrid(columns: columns, spacing: 9) {
                ForEach(AppAppearance.allCases) { appearance in
                    Button { model.setAppearance(appearance) } label: {
                        VStack(spacing: 7) {
                            AppearancePreview(appearance: appearance)
                            HStack(spacing: 4) {
                                if model.appearance == appearance {
                                    Image(systemName: "checkmark")
                                        .font(.system(size: 9, weight: .bold))
                                }
                                Text(label(appearance))
                            }
                            .font(RatsFont.body(10, weight: .semibold))
                            .foregroundStyle(model.appearance == appearance ? RatsColor.primary : RatsColor.secondary)
                        }
                        .padding(7)
                        .background(RatsColor.stage)
                        .overlay(
                            RoundedRectangle(cornerRadius: 12, style: .continuous)
                                .stroke(model.appearance == appearance ? RatsColor.primary : RatsColor.border, lineWidth: model.appearance == appearance ? 2 : 1)
                        )
                        .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
                    }
                    .buttonStyle(RatsPlainButtonStyle())
                    .accessibilityLabel("Erscheinungsbild \(label(appearance))")
                    .accessibilityAddTraits(model.appearance == appearance ? .isSelected : [])
                }
            }
        }
    }

    private func label(_ appearance: AppAppearance) -> String {
        switch appearance {
        case .system: "Automatisch"
        case .light: "Hell"
        case .dark: "Dunkel"
        }
    }
}

private struct AppearancePreview: View {
    let appearance: AppAppearance

    var body: some View {
        GeometryReader { proxy in
            ZStack {
                if appearance == .system {
                    HStack(spacing: 0) {
                        Color.white
                        Color(red: 0.05, green: 0.10, blue: 0.15)
                    }
                } else {
                    appearance == .light ? Color.white : Color(red: 0.05, green: 0.10, blue: 0.15)
                }
                VStack(alignment: .leading, spacing: 4) {
                    Capsule().fill(Color(red: 0.16, green: 0.50, blue: 0.68)).frame(width: proxy.size.width * 0.38, height: 5)
                    Capsule().fill(Color.gray.opacity(0.45)).frame(width: proxy.size.width * 0.68, height: 3)
                    Capsule().fill(Color.gray.opacity(0.3)).frame(width: proxy.size.width * 0.52, height: 3)
                }
                .padding(9)
                .frame(maxWidth: .infinity, alignment: .leading)
            }
        }
        .frame(height: 52)
        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
    }
}
