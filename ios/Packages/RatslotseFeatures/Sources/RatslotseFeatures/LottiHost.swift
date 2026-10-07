import RatslotseAPI
import RatslotseDesign
import SwiftUI
import UIKit

/// Wo Lotti wohnt: EINMAL über dem ganzen Navigations-Stapel.
///
/// **Warum hier und nicht in der Tab-Ansicht.** Bis 10/2026 hingen Knopf,
/// Blase und Blatt an `MainTabsView` — der Wurzel des Stapels. Jede
/// geschobene Seite legte sich darüber: Beschluss, Sitzung, Person, Thema,
/// Ort, Bewegung, Mein Viertel, Analyse. Der Knopf lag unerreichbar darunter,
/// ausgerechnet auf den Seiten, die am meisten zu erklären haben (gefunden
/// beim Drehen der Clips für 3.0.0). Und die Uhr des Anklopfens lief dort
/// weiter: Sie zeigte eine Blase, die niemand sah, und meldete sie als
/// gezeigt.
///
/// Was Lotti erklärt, weiß `AppModel.currentExplainScreen` — die oberste
/// Route des Stapels, sonst die Seite des Tabs. Der Knopf steht also auf
/// jeder Seite, und er trägt deren Kennung mit (`ExplainScreen.from`, wie
/// im Web `route` plus Kennung).
///
/// Wo er genau steht, rechnet `LottiPlacement` (ohne Oberfläche geprüft).
/// `tests/test_ios_lotti_blatt.py` hält fest, dass er hier hängt und
/// nirgends sonst.
@MainActor
@Observable
final class LottiPresence {
    /// Das offene Blatt samt dem Bildschirm, zu dem es gehört. Der Bildschirm
    /// wird beim ÖFFNEN festgehalten: Wer im Blatt weiterfragt, fragt weiter
    /// zu der Seite, von der er kam.
    var sitzung: LottiSitzung?
    var nudgeVisible = false
    /// Höhe der Tab-Leiste, wie die Tab-Ansicht sie misst; 0, wo keine
    /// steht (iPad, offene Tastatur).
    var tabBarHeight: CGFloat = 0
    /// Ein Blatt der Tab-Ansicht (Mehr) oder die Tour ist offen — dann
    /// klopft Lotti nicht an. Ihre Blase läge sonst unsichtbar darunter.
    var busy = false
    /// Steht die Tastatur? Gemeldet von den System-Nachrichten, also für
    /// jedes Feld in jedem Tab und auch in einem Blatt darüber.
    var keyboardVisible = false
    /// Lottis Anklopfen: die Uhr je Screen.
    let clock = NudgeClock()
}

struct LottiHost: ViewModifier {
    @Bindable var model: AppModel
    @Bindable var presence: LottiPresence
    /// Steht die App in ihrer Hauptansicht — nicht in Anmeldung,
    /// Einrichtung oder dem Aktualisieren-Schirm?
    let active: Bool
    @Environment(\.scenePhase) private var scenePhase

    /// Der Bildschirm, zu dem Lotti gerade etwas sagen kann — `nil` heißt:
    /// kein Knopf (Schalter aus, Konto, Admin, fremde Adresse).
    private var screen: ExplainScreen? {
        guard active, model.feature("lotti-assistentin") else { return nil }
        return model.currentExplainScreen
    }

    private var bottomClearance: CGFloat {
        LottiPlacement.bottomClearance(
            stackDepth: model.navigation.count,
            tabBarHeight: presence.tabBarHeight,
            keyboardVisible: presence.keyboardVisible)
    }

    func body(content: Content) -> some View {
        content
            // Der schwebende Knopf liegt ÜBER allem, auch über der
            // Tab-Leiste — wie im Web.
            .overlay(alignment: .bottomTrailing) {
                if let screen, !presence.keyboardVisible {
                    LottiFloatingButton(open: { open(screen) }, bottomClearance: bottomClearance)
                        .transition(.scale.combined(with: .opacity))
                }
            }
            // Die Blase über dem Knopf. Sie verschwindet von selbst wieder,
            // und **das zählt nicht als Ablehnung**: Wer nicht hinsieht, hat
            // nicht Nein gesagt.
            .overlay(alignment: .bottomTrailing) {
                if presence.nudgeVisible, let screen {
                    LottiNudgeBubble(
                        accept: {
                            let stand = AssistantNudge.afterAccept(NudgeStore().state,
                                                                   now: Date.now.timeIntervalSince1970)
                            NudgeStore().state = stand
                            presence.nudgeVisible = false
                            Task { await model.reportAssistantEvent("nudge_accepted") }
                            open(screen)
                        },
                        dismiss: {
                            NudgeStore().state = AssistantNudge.afterDismissal(NudgeStore().state)
                            presence.nudgeVisible = false
                            Task { await model.reportAssistantEvent("nudge_dismissed") }
                        },
                        bottomClearance: bottomClearance
                    )
                }
            }
            .animation(RatsMotion.flow, value: presence.nudgeVisible)
            .animation(RatsMotion.flow, value: bottomClearance)
            .animation(RatsMotion.flow, value: presence.keyboardVisible)
            // Jede Berührung ist ein Lebenszeichen — `simultaneousGesture`
            // nimmt sie mit, ohne sie zu verbrauchen: Listen scrollen weiter,
            // Knöpfe drücken weiter.
            .simultaneousGesture(DragGesture(minimumDistance: 0)
                .onChanged { _ in presence.clock.touched() })
            // Ein Screen-Wechsel setzt die Uhr zurück und nimmt die Blase
            // mit: Eine Frage zum ALTEN Screen wäre eine zur falschen Sache.
            // Ein anderer Beschluss ist ein anderer Screen — deshalb der
            // ganze Bildschirm samt Kennung, nicht nur die Route.
            // Gezählt wird nur in der Hauptansicht — Anmeldung und Einrichtung
            // sind keine Screens, die Lotti erklärt.
            .onChange(of: screen, initial: true) { _, neu in
                if active { presence.clock.enteredScreen() }
                presence.nudgeVisible = false
                // Das Blatt gehört zu EINEM Screen. Öffnet sich darunter ein
                // anderer (ein Push, ein Link von außen), geht es zu — sonst
                // läge die neue Seite unsichtbar dahinter.
                if let offen = presence.sitzung, offen.screen != neu { presence.sitzung = nil }
            }
            .task(id: "\(active)-\(model.feature("lotti-anstupser"))") { await klopfUhr() }
            .task {
                for await _ in NotificationCenter.default.notifications(named: UIResponder.keyboardWillShowNotification) {
                    presence.keyboardVisible = true
                }
            }
            .task {
                for await _ in NotificationCenter.default.notifications(named: UIResponder.keyboardWillHideNotification) {
                    presence.keyboardVisible = false
                }
            }
            .sheet(item: $presence.sitzung) { sitzung in
                AssistantSheet(model: model, screen: sitzung.screen, title: sitzung.title,
                               fixture: sitzung.fixture)
                    .ratsLargeSheet()
            }
    }

    /// Lottis Blatt öffnen — und sich merken, dass sie heute benutzt wurde.
    private func open(_ screen: ExplainScreen) {
        presence.nudgeVisible = false
        presence.clock.sheetWasOpen = true
        NudgeStore().markUsed()
        presence.sitzung = LottiSitzung(screen: screen, title: model.currentScreenTitle)
    }

    /// Die Uhr, die alle fünf Sekunden nachsieht, ob angeklopft werden darf.
    ///
    /// Sie läuft nur mit dem eigenen Schalter (`lotti-anstupser`): Auf Prod
    /// lässt sich das Anklopfen abstellen, ohne Lotti selbst abzuschalten.
    private func klopfUhr() async {
        guard active, model.feature("lotti-assistentin"), model.feature("lotti-anstupser") else { return }
        while !Task.isCancelled {
            try? await Task.sleep(for: .seconds(5))
            presence.clock.tick(visible: scenePhase == .active)
            guard !presence.nudgeVisible, let screen, presence.sitzung == nil else { continue }
            let store = NudgeStore()
            let kontext = NudgeContext(
                screenAllowed: screen.allowsNudge,
                readingTime: presence.clock.readingTime,
                sinceInteraction: presence.clock.sinceInteraction,
                screensThisSession: presence.clock.screensThisSession,
                sheetWasOpen: presence.clock.sheetWasOpen,
                usedToday: store.usedToday,
                busy: presence.keyboardVisible || presence.busy)
            let jetzt = Date.now.timeIntervalSince1970
            guard AssistantNudge.mayAppear(store.state, kontext, now: jetzt) else { continue }
            store.state = AssistantNudge.afterShowing(store.state, now: jetzt)
            presence.nudgeVisible = true
            await model.reportAssistantEvent("nudge_shown")
            // Nach 15 Sekunden ist sie von selbst wieder weg.
            let gezeigt = presence.nudgeVisible
            try? await Task.sleep(for: .seconds(15))
            if gezeigt { presence.nudgeVisible = false }
        }
    }
}

extension View {
    /// Lottis Knopf, Blase und Blatt — an den Navigations-Stapel der Wurzel,
    /// nirgends sonst (s. `LottiHost`).
    func lottiHost(model: AppModel, presence: LottiPresence, active: Bool) -> some View {
        modifier(LottiHost(model: model, presence: presence, active: active))
    }
}
