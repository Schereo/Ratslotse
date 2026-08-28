import Foundation
import MapKit
import RatslotseFeatures
import Testing
@testable import Ratslotse

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
