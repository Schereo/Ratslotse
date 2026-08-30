import MapKit
import RatslotseAPI
import RatslotseDesign
import SwiftUI

struct QuizMapView: View {
    let model: AppModel
    @Environment(\.dismiss) private var dismiss
    @State private var position: MapCameraPosition = .region(
        MKCoordinateRegion(
            center: CLLocationCoordinate2D(latitude: 53.1435, longitude: 8.2146),
            span: MKCoordinateSpan(latitudeDelta: 0.20, longitudeDelta: 0.28)
        )
    )
    @State private var areas: [NamedPolygon] = []
    @State private var targets: [String] = []
    @State private var index = 0
    @State private var selected: String?
    @State private var result: MapAnswer?
    @State private var correct = 0
    @State private var points = 0
    @State private var error: String?

    var body: some View {
        VStack(spacing: 0) {
            RatsSheetHeader(
                "Oldenburg verorten",
                leadingTitle: "Schließen",
                leadingAction: { dismiss() }
            )
            if targets.indices.contains(index) {
                VStack(alignment: .leading, spacing: 7) {
                    MonoKicker("Karten-Quiz", trailing: "\(index + 1) von \(targets.count)")
                    Text("Wo liegt \(targets[index])?").font(RatsFont.title(22))
                    if let result {
                        Label(
                            result.correct ? "Richtig – \(result.points) Punkte" : "Das war \(selected ?? "ein anderer Stadtteil").",
                            systemImage: result.correct ? "checkmark.circle.fill" : "xmark.circle.fill"
                        )
                        .font(RatsFont.body(13, weight: .semibold))
                        .foregroundStyle(result.correct ? RatsColor.success : RatsColor.danger)
                    } else {
                        Text("Tippe den gesuchten Ortsbereich auf der Karte an.")
                            .font(RatsFont.body(13)).foregroundStyle(RatsColor.secondary)
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(16)
            } else if !targets.isEmpty {
                VStack(spacing: 8) {
                    Text("\(correct) von \(targets.count) richtig").font(RatsFont.title(24))
                    Text("\(points) Punkte").foregroundStyle(RatsColor.secondary)
                    Button("Noch eine Runde") { Task { await loadRound() } }
                        .buttonStyle(PrimaryButtonStyle())
                }
                .frame(maxWidth: .infinity)
                .padding(18)
            }

            if areas.isEmpty || targets.isEmpty {
                if let error {
                    ErrorCard(message: error) { Task { await load() } }.padding(18)
                } else {
                    RatsLoadingState(message: "Stadtkarte wird geladen …")
                        .padding(18)
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                }
            } else {
                MapReader { proxy in
                    Map(position: $position, interactionModes: [.pan, .zoom]) {
                        ForEach(areas) { area in
                            MapPolygon(area.polygon)
                                .foregroundStyle(fill(for: area.name))
                                .stroke(RatsColor.primary.opacity(0.55), lineWidth: 0.8)
                        }
                    }
                    .mapStyle(.standard(elevation: .flat, emphasis: .muted, pointsOfInterest: .excludingAll))
                    .onTapGesture { point in
                        guard result == nil, targets.indices.contains(index),
                              let coordinate = proxy.convert(point, from: .local),
                              let area = areas.first(where: { contains(coordinate, polygon: $0.polygon) })
                        else { return }
                        selected = area.name
                        Task { await answer(clicked: area.name) }
                    }
                }
                .overlay(alignment: .bottom) {
                    if result != nil {
                        Button(index + 1 == targets.count ? "Ergebnis ansehen" : "Nächster Stadtteil") {
                            index += 1
                            selected = nil
                            result = nil
                        }
                        .buttonStyle(PrimaryButtonStyle())
                        .padding(16)
                    }
                }
            }
        }
        .background(RatsColor.page)
        .toolbar(.hidden, for: .navigationBar)
        .task { await load() }
    }

    private func fill(for name: String) -> Color {
        guard let selected else { return RatsColor.primary.opacity(0.08) }
        if name == selected { return result?.correct == true ? RatsColor.success.opacity(0.45) : RatsColor.danger.opacity(0.4) }
        if result != nil, targets.indices.contains(index), name == targets[index] { return RatsColor.success.opacity(0.45) }
        return RatsColor.primary.opacity(0.06)
    }

    private func load() async {
        if areas.isEmpty {
            do { areas = try loadPolygons() }
            catch { self.error = "Die Stadtteilkarte konnte nicht geladen werden."; return }
        }
        await loadRound()
    }

    private func loadRound() async {
        struct Question: Codable, Sendable { let target: String }
        struct Response: Codable, Sendable { let questions: [Question] }
        do {
            let response: Response = try await model.api.get(
                "/api/quiz/map-round", query: [.init(name: "n", value: "5")]
            )
            targets = response.questions.map(\.target)
            index = 0
            selected = nil
            result = nil
            correct = 0
            points = 0
            error = nil
        } catch { self.error = error.localizedDescription }
    }

    private func answer(clicked: String) async {
        struct Body: Codable, Sendable { let target: String; let clicked: String }
        guard targets.indices.contains(index) else { return }
        do {
            let response: MapAnswer = try await model.api.send(
                "/api/quiz/map-answer", body: Body(target: targets[index], clicked: clicked)
            )
            result = response
            points += response.points
            if response.correct { correct += 1 }
        } catch { self.error = error.localizedDescription }
    }

    private func loadPolygons() throws -> [NamedPolygon] {
        guard let url = Bundle.main.url(forResource: "stadtteile-oldenburg", withExtension: "json") else {
            throw CocoaError(.fileNoSuchFile)
        }
        let objects = try MKGeoJSONDecoder().decode(Data(contentsOf: url))
        var result: [NamedPolygon] = []
        for feature in objects.compactMap({ $0 as? MKGeoJSONFeature }) {
            guard
                let data = feature.properties,
                let properties = try? JSONDecoder().decode(AreaProperties.self, from: data)
            else { continue }
            for geometry in feature.geometry {
                if let polygon = geometry as? MKPolygon {
                    result.append(NamedPolygon(name: properties.name, polygon: polygon))
                } else if let multi = geometry as? MKMultiPolygon {
                    result += multi.polygons.map { NamedPolygon(name: properties.name, polygon: $0) }
                }
            }
        }
        return result
    }

    private func contains(_ coordinate: CLLocationCoordinate2D, polygon: MKPolygon) -> Bool {
        let renderer = MKPolygonRenderer(polygon: polygon)
        renderer.createPath()
        return renderer.path.contains(renderer.point(for: MKMapPoint(coordinate)))
    }
}

private struct AreaProperties: Codable { let name: String }

private struct NamedPolygon: Identifiable {
    let id = UUID()
    let name: String
    let polygon: MKPolygon
}

private struct MapAnswer: Codable, Sendable {
    let correct: Bool
    let target: String
    let points: Int
}
