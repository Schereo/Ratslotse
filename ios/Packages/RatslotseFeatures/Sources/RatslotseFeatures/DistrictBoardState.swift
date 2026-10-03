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
    /// Der Server kennt den Ortsbereich nicht (404) — dann hilft kein
    /// zweiter Versuch, und die Tafel sagt das, statt „Erneut versuchen"
    /// anzubieten.
    var notFound = false
    var stage: DistrictStage?
    var selected: DistrictProject?
    var reported: Set<String> = []

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
        notFound = false
        do {
            data = try await model.api.get("/api/districts/\(placeID)/projects")
        } catch let failure as APIError where failure.statusCode == 404 {
            notFound = true
            self.error = "Diesen Ortsbereich gibt es nicht."
        } catch {
            self.error = "Die Tafel lässt sich gerade nicht laden."
        }
    }

    func report(_ project: DistrictProject) async {
        do {
            let out: DistrictProjectReportOut = try await model.api.send(
                "/api/districts/projects/\(project.id)/report", body: ["reason": nil as String?]
            )
            reported.insert(project.projectKey)
            model.actionFeedback += 1
            if out.hidden { model.alertMessage = "Danke — das Vorhaben ist jetzt ausgeblendet." }
        } catch {
            model.alertMessage = "Die Meldung ist gerade nicht durchgegangen."
        }
    }
}
