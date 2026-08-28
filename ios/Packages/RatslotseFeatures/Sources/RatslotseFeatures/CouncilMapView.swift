import MapKit
import RatslotseAPI
import SwiftUI

struct NativeCouncilMap: UIViewRepresentable {
    let points: [CouncilMapPoint]
    let open: (CouncilMapPoint) -> Void

    func makeCoordinator() -> Coordinator { Coordinator(open: open) }

    func makeUIView(context: Context) -> MKMapView {
        let map = MKMapView()
        map.delegate = context.coordinator
        map.pointOfInterestFilter = .excludingAll
        map.register(MKMarkerAnnotationView.self, forAnnotationViewWithReuseIdentifier: "council-point")
        map.register(MKMarkerAnnotationView.self, forAnnotationViewWithReuseIdentifier: "council-cluster")
        if let url = Bundle.main.url(forResource: "stadtteile-oldenburg", withExtension: "json"),
           let data = try? Data(contentsOf: url),
           let objects = try? MKGeoJSONDecoder().decode(data) {
            let overlays = objects.compactMap { $0 as? MKGeoJSONFeature }
                .flatMap { $0.geometry.compactMap { $0 as? MKOverlay } }
            map.addOverlays(overlays)
        }
        return map
    }

    func updateUIView(_ map: MKMapView, context: Context) {
        context.coordinator.open = open
        let current = Dictionary(uniqueKeysWithValues: map.annotations.compactMap { annotation in
            (annotation as? CouncilPointAnnotation).map { ($0.point.id, $0) }
        })
        let incoming = Set(points.map(\.id))
        map.removeAnnotations(current.filter { !incoming.contains($0.key) }.map(\.value))
        let additions = points.filter { current[$0.id] == nil }.map(CouncilPointAnnotation.init)
        map.addAnnotations(additions)

        guard !context.coordinator.didFrame, !points.isEmpty else { return }
        context.coordinator.didFrame = true
        let core = map.annotations.compactMap { $0 as? CouncilPointAnnotation }.filter {
            abs($0.coordinate.latitude - 53.1435) < 0.08 && abs($0.coordinate.longitude - 8.2146) < 0.14
        }
        map.showAnnotations(core.isEmpty ? map.annotations : core, animated: false)
        map.setVisibleMapRect(
            map.visibleMapRect,
            edgePadding: UIEdgeInsets(top: 44, left: 28, bottom: 44, right: 28),
            animated: false
        )
    }

    final class Coordinator: NSObject, MKMapViewDelegate {
        var open: (CouncilMapPoint) -> Void
        var didFrame = false

        init(open: @escaping (CouncilMapPoint) -> Void) { self.open = open }

        func mapView(_ mapView: MKMapView, viewFor annotation: MKAnnotation) -> MKAnnotationView? {
            if let cluster = annotation as? MKClusterAnnotation {
                guard let view = mapView.dequeueReusableAnnotationView(
                    withIdentifier: "council-cluster", for: cluster
                ) as? MKMarkerAnnotationView else { return nil }
                view.markerTintColor = UIColor(red: 0.03, green: 0.39, blue: 0.65, alpha: 1)
                view.glyphText = String(cluster.memberAnnotations.count)
                view.titleVisibility = .adaptive
                return view
            }
            guard let annotation = annotation as? CouncilPointAnnotation else { return nil }
            guard let view = mapView.dequeueReusableAnnotationView(
                withIdentifier: "council-point", for: annotation
            ) as? MKMarkerAnnotationView else { return nil }
            view.clusteringIdentifier = "council"
            view.canShowCallout = true
            view.markerTintColor = annotation.color
            view.glyphImage = UIImage(systemName: annotation.point.target == "ort" ? "mappin" : "building.columns")
            view.displayPriority = annotation.point.count >= 10 ? .required : .defaultHigh
            let button = UIButton(type: .detailDisclosure)
            button.accessibilityLabel = "\(annotation.point.name) öffnen"
            view.rightCalloutAccessoryView = button
            return view
        }

        func mapView(_ mapView: MKMapView, didSelect view: MKAnnotationView) {
            guard let cluster = view.annotation as? MKClusterAnnotation else { return }
            mapView.showAnnotations(cluster.memberAnnotations, animated: true)
        }

        func mapView(
            _ mapView: MKMapView,
            annotationView view: MKAnnotationView,
            calloutAccessoryControlTapped control: UIControl
        ) {
            guard let annotation = view.annotation as? CouncilPointAnnotation else { return }
            open(annotation.point)
        }

        func mapView(_ mapView: MKMapView, rendererFor overlay: MKOverlay) -> MKOverlayRenderer {
            if let polygon = overlay as? MKPolygon {
                let renderer = MKPolygonRenderer(polygon: polygon)
                renderer.strokeColor = UIColor(red: 0.03, green: 0.39, blue: 0.65, alpha: 0.32)
                renderer.fillColor = UIColor(red: 0.03, green: 0.39, blue: 0.65, alpha: 0.035)
                renderer.lineWidth = 0.8
                return renderer
            }
            if let multiPolygon = overlay as? MKMultiPolygon {
                let renderer = MKMultiPolygonRenderer(multiPolygon: multiPolygon)
                renderer.strokeColor = UIColor(red: 0.03, green: 0.39, blue: 0.65, alpha: 0.32)
                renderer.fillColor = UIColor(red: 0.03, green: 0.39, blue: 0.65, alpha: 0.035)
                renderer.lineWidth = 0.8
                return renderer
            }
            return MKOverlayRenderer(overlay: overlay)
        }
    }
}

private final class CouncilPointAnnotation: NSObject, MKAnnotation {
    let point: CouncilMapPoint
    let coordinate: CLLocationCoordinate2D
    var title: String? { point.name }
    var subtitle: String? { "\(point.count) \(point.count == 1 ? "Beschluss" : "Beschlüsse")" }

    init(_ point: CouncilMapPoint) {
        self.point = point
        coordinate = CLLocationCoordinate2D(latitude: point.latitude, longitude: point.longitude)
    }

    var color: UIColor {
        switch point.kind {
        case "ort": UIColor(red: 0.03, green: 0.39, blue: 0.65, alpha: 1)
        case "organisation": UIColor(red: 0.49, green: 0.23, blue: 0.84, alpha: 1)
        case "beschlussort": UIColor(red: 0.86, green: 0.39, blue: 0.10, alpha: 1)
        default: UIColor(red: 0.03, green: 0.59, blue: 0.42, alpha: 1)
        }
    }
}
