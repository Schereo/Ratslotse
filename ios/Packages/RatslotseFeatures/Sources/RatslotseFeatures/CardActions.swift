import EventKit
import RatslotseAPI
import RatslotseDesign
import SwiftUI

// MARK: - Zoom-Übergang Karte → Detail (iOS 18)

private struct RatsZoomNamespaceKey: EnvironmentKey {
    static let defaultValue: Namespace.ID? = nil
}

extension EnvironmentValues {
    /// Der gemeinsame Namensraum für den Zoom-Übergang: gesetzt am
    /// NavigationStack der Wurzel; Quelle (Karte) und Ziel (Detail) finden
    /// sich darüber, ohne dass jede Liste einen eigenen Namensraum durchreicht.
    var ratsZoomNamespace: Namespace.ID? {
        get { self[RatsZoomNamespaceKey.self] }
        set { self[RatsZoomNamespaceKey.self] = newValue }
    }
}

/// Die Kennung, unter der Karte und Detail sich beim Zoom-Übergang finden —
/// aus der Route gerechnet, damit jede Karte zu einem Beschluss dieselbe
/// Kennung trägt wie die Detailseite, die sie öffnet.
enum RatsZoomID {
    static func decision(_ id: Int) -> String { "decision-\(id)" }
    static func session(_ ksinr: Int) -> String { "session-\(ksinr)" }

    static func forRoute(_ route: AppRoute) -> String? {
        switch route {
        case .decision(let id): decision(id)
        case .sessions(let ksinr?, _): session(ksinr)
        default: nil
        }
    }
}

private struct RatsZoomSource: ViewModifier {
    let id: String?
    @Environment(\.ratsZoomNamespace) private var namespace

    func body(content: Content) -> some View {
        if #available(iOS 18.0, *), let namespace, let id {
            content.matchedTransitionSource(id: id, in: namespace)
        } else {
            content
        }
    }
}

private struct RatsZoomDestination: ViewModifier {
    let id: String?
    @Environment(\.ratsZoomNamespace) private var namespace

    func body(content: Content) -> some View {
        if #available(iOS 18.0, *), let namespace, let id {
            content.navigationTransition(.zoom(sourceID: id, in: namespace))
        } else {
            content
        }
    }
}

extension View {
    /// Die Karte, aus der das Detail aufgeht — ab iOS 18 wächst sie zur
    /// Seite auf wie in Fotos, davor bleibt der gewohnte Schub.
    func ratsZoomSource(_ id: String?) -> some View { modifier(RatsZoomSource(id: id)) }

    /// Das Detail, das aus seiner Karte aufgeht.
    func ratsZoomDestination(_ id: String?) -> some View { modifier(RatsZoomDestination(id: id)) }
}

// MARK: - Kontextmenüs mit Vorschau

/// Lange drücken auf eine Beschluss-Karte: die Karte als Vorschau, dazu
/// Merken und Teilen — die Aktionen der Detailseite, ohne hinzugehen.
private struct DecisionCardContextMenu: ViewModifier {
    let decision: DecisionSummary
    let model: AppModel

    func body(content: Content) -> some View {
        content.contextMenu {
            Button { model.bookmark(decisionID: decision.id) } label: {
                RatsLabel("Merken", .bookmark)
            }
            if let link = model.router.universalLink(for: .decision(id: decision.id)) {
                ShareLink(item: link) { RatsLabel("Teilen", .share) }
            }
        } preview: {
            DecisionRow(decision: decision)
                .padding(RatsSpacing.lg)
                .frame(width: 360)
                .background(RatsColor.card)
        }
    }
}

/// Lange drücken auf eine Sitzungskarte: Vorschau, Merken, Teilen und der
/// Termin in den Kalender — wie auf der Detailseite.
private struct SessionCardContextMenu: ViewModifier {
    let session: CouncilSession
    let model: AppModel
    let addToCalendar: () -> Void

    func body(content: Content) -> some View {
        content.contextMenu {
            if let ksinr = session.ksinr {
                Button { model.bookmark(sessionID: ksinr) } label: {
                    RatsLabel("Merken", .bookmark)
                }
                if let link = model.router.universalLink(for: .sessions(ksinr: ksinr, tops: [])) {
                    ShareLink(item: link) { RatsLabel("Teilen", .share) }
                }
            }
            Button(action: addToCalendar) { RatsLabel("In den Kalender", .calendarPlus) }
        } preview: {
            SessionRow(session: session)
                .frame(width: 360)
                .padding(10)
                .background(RatsColor.page)
        }
    }
}

extension View {
    func decisionContextMenu(_ decision: DecisionSummary, model: AppModel) -> some View {
        modifier(DecisionCardContextMenu(decision: decision, model: model))
    }

    func sessionContextMenu(
        _ session: CouncilSession,
        model: AppModel,
        addToCalendar: @escaping () -> Void
    ) -> some View {
        modifier(SessionCardContextMenu(session: session, model: model, addToCalendar: addToCalendar))
    }
}

// MARK: - Aktionen hinter den Menüs

extension AppModel {
    /// Merken aus dem Kontextmenü — dieselbe Anfrage wie der Knopf der
    /// Detailseite. Der Server kennt den Eintrag über seinen Zielschlüssel;
    /// ein zweites Merken legt keinen zweiten an.
    func bookmark(decisionID: Int) {
        bookmark(kind: "decision", decisionID: decisionID, ksinr: nil)
    }

    func bookmark(sessionID: Int) {
        bookmark(kind: "session", decisionID: nil, ksinr: sessionID)
    }

    private func bookmark(kind: String, decisionID: Int?, ksinr: Int?) {
        guard user != nil else { authPresentation = .login; return }
        struct Body: Codable, Sendable {
            let kind: String
            let decision_id: Int?
            let ksinr: Int?
        }
        Task { @MainActor in
            do {
                let _: BookmarkEntry = try await api.send(
                    "/api/bookmarks",
                    body: Body(kind: kind, decision_id: decisionID, ksinr: ksinr)
                )
                actionFeedback += 1
            } catch {
                alertMessage = error.localizedDescription
            }
        }
    }
}

/// Der Kalender-Entwurf zu einer Sitzung aus der Liste — fragt wie die
/// Detailseite erst den Zugriff ab und baut dann den Termin: drei Stunden ab
/// Beginn, der Ort aus dem Ratsinfo, der Link zur Sitzung in den Notizen.
/// `nil`, wenn der Zugriff nicht erlaubt wurde.
@MainActor
func sessionCalendarDraft(for session: CouncilSession, link: URL?) async -> CalendarDraft? {
    let store = EKEventStore()
    guard (try? await store.requestFullAccessToEvents()) == true else { return nil }
    let parser = DateFormatter()
    parser.locale = Locale(identifier: "de_DE")
    parser.dateFormat = "yyyy-MM-dd HH:mm"
    let time = session.sessionTime.map { String($0.prefix(5)) } ?? "17:00"
    let start = parser.date(from: "\(session.sessionDate.prefix(10)) \(time)") ?? .now
    return CalendarDraft(
        title: Committee.short(session.committee),
        start: start,
        end: start.addingTimeInterval(3 * 3600),
        location: session.location,
        notes: link?.absoluteString
    )
}

let calendarAccessDeniedMessage = "Kalenderzugriff wurde nicht erlaubt. Du kannst ihn in den Einstellungen freigeben."
