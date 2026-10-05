import Foundation
import RatslotseAPI

/// Der Zustand einer Viertel-Tafel: die Daten, der Stand-Filter, das gewählte
/// Vorhaben. Karte (`CityMapView`) und Tafel (`DistrictBoardPanel`) teilen ihn
/// sich — ein Tipp auf einen Pin hebt die Zeile, ein Tipp auf die Zeile den
/// Pin. Bis 09/2026 lag das als `@State` in einer View, die beides war.
@MainActor
@Observable
final class DistrictBoardState {
    let model: AppModel
    let placeID: String
    var data: DistrictProjects?
    var error: String?
    var stage: DistrictStage?
    var selected: DistrictProject?
    /// Was dieses Konto hier gemeldet (`true`) oder zurückgenommen (`false`)
    /// hat — gilt vor `project.reported`, bis die Tafel neu geladen ist.
    var reported: [String: Bool] = [:]
    /// Ein Vorhaben aus dem Link (`?v=`), das nach dem Laden geöffnet wird.
    var pendingProject: Int?

    func isReported(_ project: DistrictProject) -> Bool {
        reported[project.projectKey] ?? project.reported
    }

    init(model: AppModel, placeID: String) {
        self.model = model
        self.placeID = placeID
    }

    var projects: [DistrictProject] { sortedProjects(data?.projects ?? []) }
    var visible: [DistrictProject] {
        guard let stage else { return projects }
        return projects.filter { stageOf($0) == stage }
    }

    func load() async {
        error = nil
        do {
            data = try await model.api.get("/api/districts/\(placeID)/projects")
        } catch {
            self.error = "Die Tafel lässt sich gerade nicht laden."
            return
        }
        // Ein Vorhaben aus dem Link öffnen. Kennt die Tafel es nicht (alter
        // Link, inzwischen ausgeblendet), bleibt das Viertel offen und sagt es.
        if let wanted = pendingProject {
            pendingProject = nil
            if let project = projects.first(where: { $0.id == wanted }) {
                // Kommt der Link per Push in den Stapel, läuft die Animation
                // noch, wenn die Tafel lokal schon da ist — ein Sheet, das in
                // dieser Zeit aufgehen soll, verwirft SwiftUI still.
                try? await Task.sleep(for: .milliseconds(600))
                selected = project
            } else {
                model.alertMessage = "Dieses Vorhaben steht so nicht mehr auf der Tafel — hier ist das Viertel."
            }
        }
    }

    /// Erst nach der Rückfrage im Detail. Eine Meldung blendet nichts aus;
    /// sie geht an die Redaktion, und die entscheidet.
    func report(_ project: DistrictProject, reason: String?) async {
        let trimmed = String((reason ?? "").trimmingCharacters(in: .whitespacesAndNewlines).prefix(300))
        do {
            let _: DistrictProjectReportOut = try await model.api.send(
                "/api/districts/projects/\(project.id)/report",
                body: ["reason": trimmed.isEmpty ? nil : trimmed]
            )
            reported[project.projectKey] = true
            model.actionFeedback += 1
        } catch {
            model.alertMessage = "Die Meldung ist gerade nicht durchgegangen."
        }
    }

    func withdraw(_ project: DistrictProject) async {
        do {
            let _: DistrictProjectReportOut = try await model.api.sendWithoutBody(
                "/api/districts/projects/\(project.id)/report", method: .delete
            )
            reported[project.projectKey] = false
            model.actionFeedback += 1
        } catch {
            model.alertMessage = "Die Meldung ließ sich gerade nicht zurücknehmen."
        }
    }
}
