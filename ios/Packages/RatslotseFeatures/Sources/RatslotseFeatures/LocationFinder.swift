import CoreLocation
import Foundation
import Observation

/// „Wo bin ich?" auf der Stadtkarte: holt EINMAL den Standort, sobald der
/// Knopf gedrückt wird — keine laufende Verfolgung, kein Hintergrund. Die
/// Karte sucht dann den Ortsbereich, in dem der Punkt liegt, und öffnet ihn;
/// das Web macht dasselbe mit „Meinen Standort nehmen".
///
/// Die Erlaubnis-Frage stellt das System beim ersten Druck; ein `denied`
/// erreicht die Karte als Zustand, sie sagt dann, wo man es umstellt.
@MainActor
@Observable
final class LocationFinder: NSObject, CLLocationManagerDelegate {
    var coordinate: CLLocationCoordinate2D?
    var denied = false
    var isSearching = false
    /// Zählt hoch, sobald ein Standort NACH einem Druck eintrifft — die Karte
    /// reagiert darauf, nicht auf den Wert (derselbe Ort zweimal ist zweimal
    /// ein Druck).
    var arrivals = 0

    private let manager = CLLocationManager()

    override init() {
        super.init()
        manager.delegate = self
        manager.desiredAccuracy = kCLLocationAccuracyHundredMeters
    }

    var isAuthorized: Bool {
        switch manager.authorizationStatus {
        case .authorizedWhenInUse, .authorizedAlways: true
        default: false
        }
    }

    func locate() {
        switch manager.authorizationStatus {
        case .notDetermined:
            isSearching = true
            manager.requestWhenInUseAuthorization()
        case .denied, .restricted:
            denied = true
        default:
            isSearching = true
            manager.requestLocation()
        }
    }

    nonisolated func locationManagerDidChangeAuthorization(_ manager: CLLocationManager) {
        Task { @MainActor in self.authorizationChanged() }
    }

    nonisolated func locationManager(_ manager: CLLocationManager, didUpdateLocations locations: [CLLocation]) {
        let latest = locations.last?.coordinate
        Task { @MainActor in self.arrived(latest) }
    }

    nonisolated func locationManager(_ manager: CLLocationManager, didFailWithError error: Error) {
        Task { @MainActor in self.isSearching = false }
    }

    private func authorizationChanged() {
        switch manager.authorizationStatus {
        case .authorizedWhenInUse, .authorizedAlways:
            if isSearching { manager.requestLocation() }
        case .denied, .restricted:
            denied = isSearching
            isSearching = false
        default:
            break
        }
    }

    private func arrived(_ latest: CLLocationCoordinate2D?) {
        guard let latest else { isSearching = false; return }
        coordinate = latest
        if isSearching { arrivals += 1 }
        isSearching = false
    }
}
