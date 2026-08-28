import Foundation
import MapKit
import Testing
@testable import Ratslotse
@testable import RatslotseFeatures

@MainActor
@Test func appTargetCanBeConstructed() {
    let app = RatslotseApp()
    #expect(String(describing: type(of: app)) == "RatslotseApp")
}

@Test func bundledOldenburgMapIsValidGeoJSON() throws {
    let url = try #require(Bundle.main.url(forResource: "stadtteile-oldenburg", withExtension: "json"))
    let objects = try MKGeoJSONDecoder().decode(Data(contentsOf: url))
    let features = objects.compactMap { $0 as? MKGeoJSONFeature }
    #expect(features.count == 31)
    #expect(features.allSatisfy { !$0.geometry.isEmpty })
}

@MainActor
@Test func onboardingProgressSurvivesARelaunch() throws {
    let suiteName = "de.ratslotse.tests.onboarding.\(UUID().uuidString)"
    let defaults = try #require(UserDefaults(suiteName: suiteName))
    defer { defaults.removePersistentDomain(forName: suiteName) }

    let fresh = AppModel(defaults: defaults)
    #expect(fresh.onboardingStep == 0)
    fresh.beginOnboarding()
    #expect(fresh.onboardingStep == 1)
    #expect(fresh.authPresentation == .register)

    let resumed = AppModel(defaults: defaults)
    #expect(resumed.onboardingStep == 1)
    defaults.set(true, forKey: "ratslotse.onboarding.done")
    let completed = AppModel(defaults: defaults)
    #expect(completed.onboardingStep == nil)
}

@MainActor
@Test func incomingRouteLeavesAnAuxiliaryTabletPage() {
    let model = AppModel()
    model.tabletPage = .saved

    model.handle(route: .tab(.questions))

    #expect(model.tabletPage == nil)
    #expect(model.selectedTab == .questions)
}

@Test func productionPersonProfileDecodesStructuredAffiliation() throws {
    let data = try #require(
        """
        {
          "name": "Tim Ebbeke Harms",
          "party": "Grüne",
          "current_affiliation": {
            "label": "Grüne",
            "kind": "partei",
            "parties": ["Grüne"]
          },
          "art": "rat",
          "organisation": null,
          "n_sessions": 136,
          "active_from": "2021-11-22",
          "active_to": "2026-06-16",
          "committees": [{"committee": "Rat", "n": 39, "chair": true}],
          "recent": [{"ksinr": 4599, "committee": "Kulturausschuss", "session_date": "2026-06-16"}]
        }
        """.data(using: .utf8)
    )

    let profile = try JSONDecoder().decode(PublicPersonProfile.self, from: data)
    #expect(profile.currentAffiliation?.label == "Grüne")
    #expect(profile.currentAffiliation?.kind == "partei")
    #expect(profile.nSessions == 136)
    #expect(profile.committees.count == 1)
    #expect(profile.recent.count == 1)
}

@Test func personProfileStillDecodesLegacyStringAffiliation() throws {
    let data = try #require(
        """
        {
          "name": "Anne Beispiel",
          "party": null,
          "current_affiliation": "SPD-Fraktion",
          "art": "rat",
          "organisation": null,
          "n_sessions": 1,
          "active_from": null,
          "active_to": null,
          "committees": [],
          "recent": []
        }
        """.data(using: .utf8)
    )

    let profile = try JSONDecoder().decode(PublicPersonProfile.self, from: data)
    #expect(profile.currentAffiliation?.label == "SPD-Fraktion")
}
