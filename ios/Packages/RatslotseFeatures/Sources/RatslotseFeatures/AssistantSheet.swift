import RatslotseAPI
import RatslotseDesign
import SwiftUI

/// Lotti als Assistentin in der App — der schwebende Knopf und sein Blatt.
///
/// **Dieselbe Regel wie im Web** (`docs/plan-lotti-assistentin.md`): Sie
/// erklärt, was gerade auf dem Bildschirm steht, und sie sucht dabei nicht.
/// Wo die Frage ins Ratsarchiv gehört, sagt sie das und reicht weiter an
/// „Frag den Rat" — den Weg dorthin schlägt der Server vor (`next`), nicht
/// diese Ansicht.
///
/// **Was in v1 fehlt und warum.** Kein markierter Text (Textauswahl in
/// SwiftUI-Listen gibt es nicht) und kein Erklär-Modus (die Abzeichen im Web
/// hängen an `data-erklaer`-Ankern im DOM; in SwiftUI bräuchte jede Ansicht
/// eine eigene Ankerkonvention). Beides ist ein eigener Plan, kein
/// Nebenbei — die Seite selbst erklärt sie vollständig.

// MARK: - Der schwebende Knopf

/// Der Knopf unten rechts, über der Tab-Leiste.
///
/// Er ist **immer** da, nicht nur auf Detailseiten: Das ist der Unterschied
/// zwischen einer Hilfe, die man sucht, und einer, die man findet.
struct LottiFloatingButton: View {
    let open: () -> Void
    /// Abstand zur Tab-Leiste — sie sitzt als `safeAreaInset` außen am
    /// TabView, ein Overlay darüber erbt ihn nicht (derselbe Befund wie bei
    /// den Seiten selbst, NativeRootView).
    var bottomClearance: CGFloat = 0

    var body: some View {
        Button(action: open) {
            LottiSpriteView(animation: .question, animated: false)
                .frame(width: 40, height: 40)
                .padding(6)
                .background(Circle().fill(RatsColor.card))
                .overlay(Circle().stroke(RatsColor.border))
                .shadow(color: .black.opacity(0.18), radius: 10, y: 4)
        }
        .buttonStyle(.plain)
        .accessibilityLabel("Lotti fragen")
        .accessibilityHint("Sie erklärt, was gerade auf dem Bildschirm steht.")
        .padding(.trailing, RatsSpacing.lg)
        .padding(.bottom, bottomClearance + RatsSpacing.md)
    }
}

/// Ein offenes Lotti-Blatt samt dem Bildschirm, zu dem es gehört.
struct LottiSitzung: Identifiable {
    let id = UUID()
    let screen: ExplainScreen
    let title: String
    /// Nur für die Sichtprobe: eine fertige Runde ohne Server.
    var fixture = false
}

// MARK: - Eine Runde im Blatt

struct AssistantTurn: Identifiable {
    let id = UUID()
    let question: String
    var answer: String = ""
    var status: String?
    var error: String?
    /// Gehört die Frage ins Ratsarchiv? Dann steht unter der Antwort der Weg
    /// dorthin — und die Frage wandert mit, sie soll niemand zweimal tippen.
    var leadsToCouncilQuestion = false
}

// MARK: - Das Blatt

struct AssistantSheet: View {
    @Bindable var model: AppModel
    /// Was der Bildschirm zeigt, in der Sprache des Backends. Ermittelt beim
    /// Öffnen und festgehalten: Wer im Blatt weiterfragt, fragt weiter zu der
    /// Seite, von der er kam.
    let screen: ExplainScreen
    let title: String
    var fixture = false

    @Environment(\.dismiss) private var dismiss
    @State private var turns: [AssistantTurn] = []
    @State private var input = ""
    @State private var streaming: Task<Void, Never>?
    @FocusState private var composerFocused: Bool

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                ScrollViewReader { proxy in
                    ScrollView {
                        VStack(alignment: .leading, spacing: RatsSpacing.lg) {
                            kontextZeile
                            if turns.isEmpty { leeresBlatt }
                            ForEach(turns) { turn in
                                runde(turn).id(turn.id)
                            }
                        }
                        .padding(RatsSpacing.lg)
                    }
                    .onChange(of: turns.last?.answer) { _, _ in
                        guard let letzte = turns.last?.id else { return }
                        withAnimation(RatsMotion.flow) { proxy.scrollTo(letzte, anchor: .bottom) }
                    }
                }
                Divider().overlay(RatsColor.border)
                composer
            }
            .background(RatsColor.page)
            .navigationTitle("Lotti")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Fertig") { dismiss() }
                }
            }
        }
        .onAppear {
#if DEBUG
            guard fixture, turns.isEmpty else { return }
            turns = [AssistantTurn(
                question: "Was bedeutet die Rate-Treppe?",
                answer: """
                Die Rate-Treppe zeigt, wie viel die Stadt in den nächsten \
                Jahren für alte Kredite zurückzahlen muss. Jede Stufe ist ein \
                Jahr; je höher sie steht, desto mehr Geld ist in diesem Jahr \
                schon vergeben.

                Die Zahlen stammen aus dem Jahresabschluss 2024 — was danach \
                aufgenommen wurde, steht noch nicht darin.
                """,
                leadsToCouncilQuestion: true
            )]
#endif
        }
        .onDisappear { streaming?.cancel() }
    }

    // MARK: Bausteine

    private var kontextZeile: some View {
        HStack(spacing: RatsSpacing.xs) {
            RatsIcon(.fileText, size: 13)
                .foregroundStyle(RatsColor.muted)
            Text("Du bist auf: \(title)")
                .font(.footnote)
                .foregroundStyle(RatsColor.muted)
                .lineLimit(1)
        }
        .accessibilityElement(children: .combine)
    }

    private var leeresBlatt: some View {
        VStack(alignment: .leading, spacing: RatsSpacing.md) {
            HStack(alignment: .top, spacing: RatsSpacing.sm) {
                LottiSpriteView(animation: .wave)
                    .frame(width: 44, height: 44)
                Text("Moin! Frag mich, was du hier gerade siehst.")
                    .font(.callout)
                    .foregroundStyle(RatsColor.text)
            }
            Button("Was sehe ich hier?") { frage("") }
                .buttonStyle(SecondaryButtonStyle())
        }
    }

    private func runde(_ turn: AssistantTurn) -> some View {
        VStack(alignment: .leading, spacing: RatsSpacing.sm) {
            // Die eigene Frage als Blase rechts, Lottis Antwort als Karte
            // links: Wer nach oben scrollt, sieht an der Form, wer spricht —
            // ohne dass irgendwo „Du" oder „Lotti" davorstehen muss.
            if !turn.question.isEmpty {
                Text(turn.question)
                    .font(.callout)
                    .foregroundStyle(RatsColor.text)
                    .multilineTextAlignment(.leading)
                    .padding(.horizontal, RatsSpacing.md)
                    .padding(.vertical, RatsSpacing.sm)
                    .background(RatsColor.stage, in: RoundedRectangle(cornerRadius: RatsRadius.card))
                    .frame(maxWidth: .infinity, alignment: .trailing)
            }
            if let status = turn.status {
                HStack(spacing: RatsSpacing.xs) {
                    ProgressView().controlSize(.small)
                    Text(status).font(.footnote).foregroundStyle(RatsColor.muted)
                }
            }
            if !turn.answer.isEmpty {
                HStack(alignment: .top, spacing: RatsSpacing.sm) {
                    LottiSpriteView(animation: .explain, animated: false)
                        .frame(width: 28, height: 28)
                        .accessibilityHidden(true)
                    Text(turn.answer)
                        .font(.callout)
                        .foregroundStyle(RatsColor.text)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .textSelection(.enabled)
                }
            }
            if turn.leadsToCouncilQuestion {
                Button {
                    // Die Frage wandert MIT: Sie noch einmal zu tippen wäre
                    // der Preis dafür, dass Lotti sie nicht beantworten kann.
                    let frage = turn.question
                    dismiss()
                    model.navigation.removeAll()
                    model.selectedTab = .questions
                    model.questionPrefill = frage
                } label: {
                    RatsLabel("Im Ratsarchiv nachsehen", .search)
                }
                .buttonStyle(SecondaryButtonStyle())
            }
            if let fehler = turn.error {
                Text(fehler).font(.footnote).foregroundStyle(RatsColor.danger)
            }
        }
    }

    private var composer: some View {
        HStack(spacing: RatsSpacing.sm) {
            TextField("Frag Lotti zu dieser Seite …", text: $input, axis: .vertical)
                .lineLimit(1...4)
                .focused($composerFocused)
                .submitLabel(.send)
                .onSubmit { frage(input) }
            Button {
                frage(input)
            } label: {
                RatsIcon(.arrowUp, size: 20)
                    // Leer ist leer: Ein voll deckender Pfeil sieht aus, als
                    // ließe sich etwas abschicken.
                    .foregroundStyle(input.trimmed.isEmpty
                                     ? RatsColor.muted.opacity(0.35) : RatsColor.primary)
            }
            .disabled(input.trimmed.isEmpty || streaming != nil)
            .accessibilityLabel("Fragen")
        }
        .padding(RatsSpacing.lg)
        .background(RatsColor.card)
    }

    // MARK: Die Frage

    private func frage(_ roh: String) {
        guard streaming == nil else { return }
        let frage = roh.trimmed
        input = ""
        composerFocused = false
        // Die letzten drei Runden als Gedächtnis — mehr nicht: Das Blatt ist
        // ein Gespräch über EINE Seite, kein Protokoll.
        let verlauf = turns.suffix(3).map {
            AskRound(question: $0.question, answer: String($0.answer.prefix(600)))
        }
        turns.append(AssistantTurn(question: frage, status: "Lotti liest die Seite …"))
        let index = turns.count - 1
        streaming = Task {
            defer { streaming = nil }
            do {
                let request = try await model.api.makeStreamingRequest(
                    "/api/council/explain",
                    body: ExplainRequest(
                        route: screen.route,
                        pageTitle: title,
                        heading: screen.heading,
                        question: frage,
                        refs: screen.refs,
                        history: verlauf,
                        conversationID: model.activeConversationID
                    )
                )
                for try await event in model.sse.events(for: request) {
                    guard !Task.isCancelled, turns.indices.contains(index) else { break }
                    switch event.type {
                    case "step":
                        turns[index].status = event.step == "answer"
                            ? "Lotti formuliert …" : "Lotti liest die Seite …"
                    case "token":
                        turns[index].status = nil
                        turns[index].answer += event.text ?? ""
                    case "replace":
                        turns[index].status = nil
                        turns[index].answer = event.text ?? turns[index].answer
                    case "error":
                        throw APIError(statusCode: 0,
                                       message: event.text ?? "Die Erklärung ist abgebrochen.",
                                       retryAfter: nil)
                    case "done":
                        turns[index].status = nil
                        let done = try? event.decodedDone()
                        turns[index].leadsToCouncilQuestion = done?.leadsToCouncilQuestion ?? false
                        if let id = event.conversationID { model.setActiveConversationID(id) }
                    default: break
                    }
                }
            } catch is CancellationError {
                // Blatt zu, Frage weg — nichts zu melden.
            } catch let fehler as APIError {
                turns[index].status = nil
                turns[index].error = fehler.message
            } catch {
                turns[index].status = nil
                turns[index].error = "Die Verbindung riss ab. Frag es gern noch einmal."
            }
        }
    }
}

extension SSEEvent {
    /// Der Schluss-Rahmen als Modell — `mode`, `next`, `glossary`.
    func decodedDone() throws -> ExplainDone {
        try JSONDecoder().decode(ExplainDone.self, from: JSONEncoder().encode(fields))
    }
}

private extension String {
    var trimmed: String { trimmingCharacters(in: .whitespacesAndNewlines) }
}
