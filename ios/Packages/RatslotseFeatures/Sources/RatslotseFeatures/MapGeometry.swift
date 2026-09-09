import MapKit
import RatslotseAPI

// Geometrie-Helfer der Stadtkarte: GeoJSON aus dem Vertrag → MapKit-Koordinaten,
// die 31 Umrisse aus dem gebündelten GeoJSON, Punkt-in-Fläche. Bis 09/2026
// standen sie in `DistrictView.swift`; seit die vereinte Karte (`CityMapView`)
// und die Tafel getrennt sind, brauchen beide sie.

/// Außenringe aus Polygon/MultiPolygon-GeoJSON — der Geltungsbereich eines
/// Bebauungsplans. Löcher (innere Ringe) fallen weg; die Umringe der Stadt
/// haben keine, und ein Loch würde als eigene Fläche gezeichnet.
func polygons(_ geometry: JSONValue?) -> [[CLLocationCoordinate2D]] {
    guard case let .object(object)? = geometry,
          case let .string(type)? = object["type"],
          case let .array(coordinates)? = object["coordinates"] else { return [] }
    func ring(_ value: JSONValue) -> [CLLocationCoordinate2D] {
        guard case let .array(points) = value else { return [] }
        return points.compactMap { point in
            guard case let .array(pair) = point, pair.count >= 2,
                  case let .number(lon) = pair[0], case let .number(lat) = pair[1] else { return nil }
            return CLLocationCoordinate2D(latitude: lat, longitude: lon)
        }
    }
    func outer(_ polygon: JSONValue) -> [CLLocationCoordinate2D] {
        guard case let .array(rings) = polygon, let first = rings.first else { return [] }
        return ring(first)
    }
    switch type {
    case "Polygon": return [outer(.array(coordinates))].filter { $0.count > 2 }
    case "MultiPolygon": return coordinates.map(outer).filter { $0.count > 2 }
    default: return []
    }
}

/// LineString/MultiLineString aus dem durchgereichten GeoJSON — für die
/// Straßenlinie auf der Karte. Alles andere (Flächen) bleibt beim Pin.
func lineStrings(_ geometry: JSONValue?) -> [[CLLocationCoordinate2D]] {
    guard case let .object(object)? = geometry,
          case let .string(type)? = object["type"],
          case let .array(coordinates)? = object["coordinates"] else { return [] }
    func line(_ value: JSONValue) -> [CLLocationCoordinate2D] {
        guard case let .array(points) = value else { return [] }
        return points.compactMap { point in
            guard case let .array(pair) = point, pair.count >= 2,
                  case let .number(lon) = pair[0], case let .number(lat) = pair[1] else { return nil }
            return CLLocationCoordinate2D(latitude: lat, longitude: lon)
        }
    }
    switch type {
    case "LineString": return [line(.array(coordinates))].filter { $0.count > 1 }
    case "MultiLineString": return coordinates.map(line).filter { $0.count > 1 }
    default: return []
    }
}

func regionAround(_ points: [CLLocationCoordinate2D], minSpan: Double) -> MKCoordinateRegion? {
    guard let first = points.first else { return nil }
    var minLat = first.latitude, maxLat = first.latitude, minLon = first.longitude, maxLon = first.longitude
    for p in points {
        minLat = min(minLat, p.latitude); maxLat = max(maxLat, p.latitude)
        minLon = min(minLon, p.longitude); maxLon = max(maxLon, p.longitude)
    }
    let center = CLLocationCoordinate2D(latitude: (minLat + maxLat) / 2, longitude: (minLon + maxLon) / 2)
    let span = MKCoordinateSpan(
        latitudeDelta: max(minSpan, (maxLat - minLat) * 1.35),
        longitudeDelta: max(minSpan * 1.5, (maxLon - minLon) * 1.35)
    )
    return MKCoordinateRegion(center: center, span: span)
}

/// Ein Ortsbereich der Stadt: Name und der Außenring seiner größten Fläche.
struct DistrictShape: Identifiable, Sendable {
    let name: String
    let ring: [CLLocationCoordinate2D]
    var id: String { name }

    /// Der Schwerpunkt des Rings — für den Zahlen-Pin auf der Stadt-Stufe.
    var centroid: CLLocationCoordinate2D {
        guard !ring.isEmpty else { return CLLocationCoordinate2D(latitude: 53.1435, longitude: 8.2146) }
        let lat = ring.map(\.latitude).reduce(0, +) / Double(ring.count)
        let lon = ring.map(\.longitude).reduce(0, +) / Double(ring.count)
        return CLLocationCoordinate2D(latitude: lat, longitude: lon)
    }

    /// Liegt der Punkt in der Fläche? Strahl nach rechts, Kanten zählen
    /// (even-odd) — für die 31 Umrisse ohne Löcher reicht das.
    func contains(_ point: CLLocationCoordinate2D) -> Bool {
        guard ring.count > 2 else { return false }
        var inside = false
        var j = ring.count - 1
        for i in 0..<ring.count {
            let a = ring[i], b = ring[j]
            if (a.latitude > point.latitude) != (b.latitude > point.latitude) {
                let x = (b.longitude - a.longitude) * (point.latitude - a.latitude) / (b.latitude - a.latitude) + a.longitude
                if point.longitude < x { inside.toggle() }
            }
            j = i
        }
        return inside
    }
}

/// Die 31 Umrisse aus dem gebündelten GeoJSON, einmal gelesen. Bei einer
/// MultiPolygon-Fläche zählt die größte — die Karte färbt Flächen, keine
/// Inselchen.
enum DistrictShapes {
    nonisolated(unsafe) private static var cache: [DistrictShape]?

    static func all() -> [DistrictShape] {
        if let cache { return cache }
        var shapes: [DistrictShape] = []
        if let url = Bundle.main.url(forResource: "stadtteile-oldenburg", withExtension: "json"),
           let data = try? Data(contentsOf: url),
           let objects = try? MKGeoJSONDecoder().decode(data) {
            for case let feature as MKGeoJSONFeature in objects {
                guard let properties = feature.properties,
                      let json = try? JSONSerialization.jsonObject(with: properties) as? [String: Any],
                      let name = json["name"] as? String else { continue }
                for geometry in feature.geometry {
                    if let polygon = geometry as? MKPolygon {
                        shapes.append(DistrictShape(name: name, ring: polygon.coordinates)); break
                    }
                    if let multi = geometry as? MKMultiPolygon,
                       let largest = multi.polygons.max(by: { $0.pointCount < $1.pointCount }) {
                        shapes.append(DistrictShape(name: name, ring: largest.coordinates)); break
                    }
                }
            }
        }
        cache = shapes
        return shapes
    }

    static func named(_ name: String) -> DistrictShape? {
        all().first { $0.name == name }
    }

    /// Welcher Ortsbereich einen Punkt enthält — für die Ebene „Themen-Orte"
    /// auf der Viertel-Stufe und den Tipp auf die Stadt-Stufe.
    static func containing(_ point: CLLocationCoordinate2D) -> DistrictShape? {
        all().first { $0.contains(point) }
    }
}

/// Der Umriss des Ortsbereichs aus dem gebündelten GeoJSON (31 Flächen).
func districtOutline(named name: String) -> [CLLocationCoordinate2D] {
    DistrictShapes.named(name)?.ring ?? []
}

extension MKPolygon {
    var coordinates: [CLLocationCoordinate2D] {
        var out = [CLLocationCoordinate2D](repeating: kCLLocationCoordinate2DInvalid, count: pointCount)
        getCoordinates(&out, range: NSRange(location: 0, length: pointCount))
        return out
    }
}
