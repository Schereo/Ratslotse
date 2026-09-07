import MapKit
import RatslotseAPI
import RatslotseDesign
import SwiftUI

// Die vereinte Stadtkarte — Richtung A aus STADTKARTE-PLAN.md, Schritt 6:
// EINE MapKit-Karte mit zwei Stufen (Stadt ↔ Ortsbereich), Ebenen als Chips
// über der Karte, die Tafel daneben (iPad) oder darunter (iPhone), das
// Vorhaben als Sheet. Die Routen `.district(id)` und der Abschnitt
// „Stadtkarte" im Rats-Tab zeigen beide hierher.
//
// Stadt-Stufe: die 31 Ortsbereiche als Flächen, getönt nach Zahl der
// Vorhaben (Wärme), ein Zahlen-Pin je Fläche; ein Tipp zoomt hinein.
// Viertel-Stufe: der Umriss, Pins, Straßenlinien, Planflächen, Sperrungen,
// Beteiligungs-Flächen — die Ebenen aus `DistrictBoardState`, den die Tafel
// teilt. Die Ebene „Themen-Orte" (die Punkte der alten Stadtkarte) liegt auf
// beiden Stufen; SwiftUIs `Map` bündelt nicht selbst, deshalb ein einfaches
// Raster nach Zoom (`clusters`).
//
// Alles additiv: kein `APP_MIN_BUILD`, die ausgelieferte App läuft weiter.

// MARK: - Ebenen

/// Die Ebenen der Karte — dieselbe Registry wie `lib/karten-ebenen.ts` im Web,
/// mit denselben Kennungen, damit `?ebenen=` in geteilten Links passt.
enum MapLayer: String, CaseIterable, Identifiable {
    case projects = "vorhaben"
    case plans = "plaene"
    case closures = "sperrungen"
    case participations = "mitreden"
    case topicPlaces = "themen-orte"

    var id: String { rawValue }

    var label: String {
        switch self {
        case .projects: "Vorhaben"
        case .plans: "Bebauungspläne"
        case .closures: "Sperrungen"
        case .participations: "Mitreden"
        case .topicPlaces: "Themen-Orte"
        }
    }

    var color: Color {
        switch self {
        case .projects: RatsColor.primary
        case .plans: RatsColor.success
        case .closures: Color(red: 0.71, green: 0.33, blue: 0.04)
        case .participations: RatsColor.signal
        case .topicPlaces: Color(red: 0.49, green: 0.23, blue: 0.84)
        }
    }

    /// Nur auf der Viertel-Stufe: Was nur dort Geometrie hat, hat auf der
    /// Stadt-Stufe keinen Chip — er wäre hohl und ohne Wirkung.
    var districtOnly: Bool {
        switch self {
        case .plans, .closures, .participations: true
        case .projects, .topicPlaces: false
        }
    }

    /// Die Vorgabe wie im Web: alles außer den Themen-Orten.
    static let defaults: Set<MapLayer> = [.projects, .plans, .closures, .participations]
}

// MARK: - Bühne

struct CityMapView: View {
    let model: AppModel
    /// Aus dem Rats-Tab („Stadtkarte"): die Themen-Orte sind dort an — das
    /// war die Karte, die man dort kannte.
    var topicsFirst = false

    @AppStorage("karte.ebenen") private var storedLayers = ""

    @State private var placeID: String?
    @State private var layers: Set<MapLayer> = MapLayer.defaults
    @State private var overview: DistrictProjectsOverview?
    @State private var overviewError: String?
    @State private var topics: [Topic] = []
    @State private var board: DistrictBoardState?
    @State private var camera: MapCameraPosition = .region(CityMapView.cityRegion)
    @State private var visibleRegion: MKCoordinateRegion = CityMapView.cityRegion
    @State private var mapPoints: [CouncilMapPoint] = []
    @State private var mapPointsLoaded = false

    static let cityRegion = MKCoordinateRegion(
        center: CLLocationCoordinate2D(latitude: 53.1435, longitude: 8.2146),
        span: MKCoordinateSpan(latitudeDelta: 0.17, longitudeDelta: 0.24)
    )

    init(model: AppModel, placeID: String?, topicsFirst: Bool = false) {
        self.model = model
        self.topicsFirst = topicsFirst
        _placeID = State(initialValue: placeID)
    }

    private var districtName: String? {
        guard let placeID else { return nil }
        return board?.data?.place.name ?? overview?.districts.first { $0.placeID == placeID }?.name
    }

    var body: some View {
        // Breit genug für zwei Spalten (iPad quer, Sidebar abgezogen): Karte
        // und Tafel nebeneinander. Sonst — Telefon UND iPad hochkant, wo die
        // Sidebar schon ein Drittel nimmt — Karte oben, Tafel darunter, Detail
        // als Sheet, wie im Web. Ein ständiges Sheet als Tafel läge sonst über
        // jeder Seite, die ein Tipp öffnet. Gemessen: bei 834 pt Breite blieb
        // der Karte neben einer 400-pt-Tafel ein Streifen von 350 pt.
        GeometryReader { geo in
            if geo.size.width >= 900 {
                HStack(spacing: 0) {
                    stage
                    Divider().overlay(RatsColor.border)
                    ScrollView { panel.padding(.horizontal, 18).padding(.vertical, 20) }
                        .frame(width: 400)
                        .background(RatsColor.page)
                }
            } else {
                ScrollView {
                    VStack(spacing: 0) {
                        stage
                            .frame(height: max(300, geo.size.height * 0.46))
                        panel
                            .padding(.horizontal, 18)
                            .padding(.vertical, 18)
                    }
                }
            }
        }
        .background(RatsColor.page)
        .navigationTitle(districtName ?? "Mein Viertel")
        .toolbarTitleDisplayMode(.inline)
        .onAppear(perform: restoreLayers)
        .task { await loadOverview() }
        .task(id: placeID) { await enterStage() }
        .task(id: layers.contains(.topicPlaces)) { await loadPoints() }
        .onChange(of: board?.selected?.id) { _, _ in focusSelected() }
    }

    // MARK: Karte

    private var stage: some View {
        ZStack(alignment: .topLeading) {
            MapReader { proxy in
                Map(position: $camera, interactionModes: [.pan, .zoom]) {
                    mapContent
                }
                .mapStyle(.standard(elevation: .flat, pointsOfInterest: .excludingAll))
                .mapControlVisibility(.hidden)
                .onMapCameraChange(frequency: .onEnd) { context in visibleRegion = context.region }
                .onTapGesture { point in
                    // Ein Tipp auf eine Fläche der Stadt-Stufe zoomt ins Viertel —
                    // die Fläche selbst ist in SwiftUI nicht tippbar, der Punkt wird
                    // gegen die 31 Umrisse geprüft.
                    guard placeID == nil, let coordinate = proxy.convert(point, from: .local),
                          let shape = DistrictShapes.containing(coordinate),
                          let entry = overview?.districts.first(where: { $0.name == shape.name }) else { return }
                    select(entry.placeID)
                }
            }
            layerChips
                .padding(10)
            breadcrumb
                .padding(10)
                .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .bottomLeading)
        }
        .accessibilityHint(placeID == nil
            ? "Tippe einen Ortsbereich, um hineinzuzoomen."
            : "Tippe einen Pin für das Vorhaben. Nahe Themen-Orte werden gebündelt.")
    }

    @MapContentBuilder
    private var mapContent: some MapContent {
        if let board, placeID != nil {
            districtContent(board)
        } else {
            cityContent
        }
        if layers.contains(.topicPlaces) {
            topicContent
        }
    }

    /// Stadt-Stufe: Wärmekarte der Ortsbereiche plus Zahlen-Pin.
    @MapContentBuilder
    private var cityContent: some MapContent {
        let counts = Dictionary(uniqueKeysWithValues: (overview?.districts ?? []).map { ($0.name, $0.count) })
        let maxCount = max(1, counts.values.max() ?? 1)
        let showProjects = layers.contains(.projects)
        ForEach(DistrictShapes.all()) { shape in
            let count = counts[shape.name] ?? 0
            let heat = showProjects ? 0.08 + 0.5 * Double(count) / Double(maxCount) : 0.06
            MapPolygon(coordinates: shape.ring)
                .foregroundStyle(RatsColor.primary.opacity(heat))
                .stroke(RatsColor.card.opacity(0.95), lineWidth: 1)
        }
        if showProjects {
            ForEach(DistrictShapes.all().filter { (counts[$0.name] ?? 0) > 0 }) { shape in
                Annotation(shape.name, coordinate: shape.centroid, anchor: .center) {
                    Button {
                        if let entry = overview?.districts.first(where: { $0.name == shape.name }) { select(entry.placeID) }
                    } label: {
                        // Klein, damit die 31 Zahlen im Weitzoom nicht übereinander
                        // liegen — die Fläche ist das Ziel, der Pin nur die Zahl.
                        Text("\(counts[shape.name] ?? 0)")
                            .font(RatsFont.body(11, weight: .bold))
                            .monospacedDigit()
                            .foregroundStyle(RatsColor.primaryText)
                            .frame(minWidth: 22, minHeight: 22)
                            .padding(.horizontal, 3)
                            .background(RatsColor.primary, in: Capsule())
                            .overlay(Capsule().stroke(RatsColor.card, lineWidth: 1.5))
                            .shadow(color: .black.opacity(0.25), radius: 2, y: 1)
                    }
                    .buttonStyle(.plain)
                    .accessibilityLabel("\(shape.name), \(counts[shape.name] ?? 0) Vorhaben")
                }
                .annotationTitles(.hidden)
            }
        }
    }

    /// Viertel-Stufe: der Umriss und die Ebenen der Tafel.
    @MapContentBuilder
    private func districtContent(_ board: DistrictBoardState) -> some MapContent {
        let outline = board.data.map { districtOutline(named: $0.place.name) } ?? []
        if outline.count > 2 {
            MapPolygon(coordinates: outline)
                .foregroundStyle(RatsColor.primary.opacity(0.06))
                .stroke(RatsColor.primary.opacity(0.8), lineWidth: 2)
        }
        if layers.contains(.closures) { closureLayers(board) }
        if layers.contains(.participations) { participationLayers(board) }
        ForEach(board.projects) { project in
            projectLayers(project, board: board)
        }
    }

    /// Sperrungen der Stadt: gestrichelt in Warnfarbe, blass, sobald ein
    /// Vorhaben gewählt ist — dann steht dessen Linie allein.
    @MapContentBuilder
    private func closureLayers(_ board: DistrictBoardState) -> some MapContent {
        let dimmed = board.selected != nil
        ForEach(board.data?.closures ?? []) { closure in
            ForEach(Array(lineStrings(closure.geometry).enumerated()), id: \.offset) { _, line in
                MapPolyline(coordinates: line)
                    .stroke(MapLayer.closures.color.opacity(dimmed ? 0.3 : 0.9),
                            style: StrokeStyle(lineWidth: 4, lineCap: .round, dash: [8, 6]))
            }
        }
    }

    /// Laufende Beteiligungen: der Geltungsbereich des Plans, punktiert in
    /// Signal-Orange — blass, sobald ein Vorhaben gewählt ist.
    @MapContentBuilder
    private func participationLayers(_ board: DistrictBoardState) -> some MapContent {
        let dimmed = board.selected != nil
        ForEach(board.data?.participations ?? []) { item in
            ForEach(Array(polygons(item.geometry).enumerated()), id: \.offset) { _, ring in
                MapPolygon(coordinates: ring)
                    .foregroundStyle(RatsColor.signal.opacity(dimmed ? 0.03 : 0.1))
                    .stroke(RatsColor.signal.opacity(dimmed ? 0.3 : 0.95),
                            style: StrokeStyle(lineWidth: 3, lineCap: .round, dash: [2, 7]))
            }
        }
    }

    /// Alles, was ein Vorhaben auf der Karte hat: Planflächen (Ebene
    /// „Bebauungspläne"), Straßenlinien und Pins (Ebene „Vorhaben").
    /// Abschnittsgrenzen und Bezugsstraßen sind nicht betroffen: keine Linie,
    /// kein Pin, solange das Vorhaben einen Gegenstand hat; sonst hohle Punkte.
    @MapContentBuilder
    private func projectLayers(_ project: DistrictProject, board: DistrictBoardState) -> some MapContent {
        let stage = stageOf(project)
        let active = board.selected?.id == project.id
        let dimmed = ((board.stage != nil && board.stage != stage) || board.selected != nil) && !active
        let hasSubject = project.locations.contains { $0.role == "subject" }
        ForEach(project.locations.filter { $0.role == "subject" || !hasSubject }) { location in
            locationLayers(location, project: project, stage: stage, active: active, dimmed: dimmed, board: board)
        }
    }

    @MapContentBuilder
    private func locationLayers(_ location: DistrictProjectLocation, project: DistrictProject,
                                stage: DistrictStage, active: Bool, dimmed: Bool,
                                board: DistrictBoardState) -> some MapContent {
        let boundary = location.role != "subject"
        let inProcedure = location.plan?.status == "in_procedure"
        let fill: Double = dimmed ? 0.04 : (active ? (inProcedure ? 0.14 : 0.22) : (inProcedure ? 0.08 : 0.14))
        let dash: [CGFloat] = inProcedure ? [6, 4] : []
        let rings: [[CLLocationCoordinate2D]] = layers.contains(.plans) && location.kind == "bplan" ? polygons(location.geometry) : []
        ForEach(Array(rings.enumerated()), id: \.offset) { _, ring in
            MapPolygon(coordinates: ring)
                .foregroundStyle(stage.color.opacity(fill))
                .stroke(stage.color.opacity(dimmed ? 0.2 : 0.85),
                        style: StrokeStyle(lineWidth: active ? 3 : 2, dash: dash))
        }
        if layers.contains(.projects) {
            let lines: [[CLLocationCoordinate2D]] = boundary ? [] : lineStrings(location.geometry)
            ForEach(Array(lines.enumerated()), id: \.offset) { _, line in
                MapPolyline(coordinates: line)
                    .stroke(stage.color.opacity(dimmed ? 0.18 : 0.75),
                            style: StrokeStyle(lineWidth: active ? 7 : 5, lineCap: .round, lineJoin: .round))
            }
            Annotation(project.name, coordinate: CLLocationCoordinate2D(
                latitude: location.latitude, longitude: location.longitude
            ), anchor: .center) {
                Button {
                    board.selected = project
                } label: {
                    DistrictPin(color: stage.color, active: active, dimmed: dimmed, hollow: boundary)
                }
                .buttonStyle(.plain)
                .accessibilityLabel("\(project.name), \(stage.label)")
            }
            .annotationTitles(.hidden)
        }
    }

    // MARK: Themen-Orte

    /// Die Punkte, die auf dieser Stufe zählen: stadtweit alle, im Viertel
    /// nur die im Umriss.
    private var stagePoints: [CouncilMapPoint] {
        guard let name = districtName, let shape = DistrictShapes.named(name) else { return mapPoints }
        return mapPoints.filter { shape.contains(CLLocationCoordinate2D(latitude: $0.latitude, longitude: $0.longitude)) }
    }

    private struct PointCluster: Identifiable {
        let id: String
        let coordinate: CLLocationCoordinate2D
        let members: [CouncilMapPoint]
    }

    /// Bündel nach Raster: Je weiter herausgezoomt, desto größer die Zelle.
    /// Ab einem Zoom nahe an den Straßen steht jeder Punkt für sich.
    private var clusters: [PointCluster] {
        let points = stagePoints
        let span = visibleRegion.span.longitudeDelta
        guard span > 0.02 else {
            return points.map { PointCluster(id: $0.id, coordinate: CLLocationCoordinate2D(latitude: $0.latitude, longitude: $0.longitude), members: [$0]) }
        }
        let cell = span / 9
        var buckets: [String: [CouncilMapPoint]] = [:]
        for p in points {
            let key = "\(Int((p.latitude / cell).rounded(.down)))|\(Int((p.longitude / cell).rounded(.down)))"
            buckets[key, default: []].append(p)
        }
        return buckets.map { key, members in
            let lat = members.map(\.latitude).reduce(0, +) / Double(members.count)
            let lon = members.map(\.longitude).reduce(0, +) / Double(members.count)
            return PointCluster(id: key, coordinate: CLLocationCoordinate2D(latitude: lat, longitude: lon), members: members)
        }
    }

    @MapContentBuilder
    private var topicContent: some MapContent {
        ForEach(clusters) { cluster in
            if cluster.members.count == 1, let point = cluster.members.first {
                Annotation(point.name, coordinate: cluster.coordinate, anchor: .center) {
                    Button { open(point) } label: {
                        TopicPointMark(point: point)
                    }
                    .buttonStyle(.plain)
                    .accessibilityLabel("\(point.name), \(point.count) \(point.count == 1 ? "Beschluss" : "Beschlüsse")")
                }
                .annotationTitles(visibleRegion.span.longitudeDelta < 0.03 ? .visible : .hidden)
            } else {
                Annotation("\(cluster.members.count)", coordinate: cluster.coordinate, anchor: .center) {
                    Button { zoom(to: cluster) } label: {
                        Text("\(cluster.members.count)")
                            .font(RatsFont.body(12, weight: .bold))
                            .monospacedDigit()
                            .foregroundStyle(RatsColor.primaryText)
                            .frame(width: cluster.members.count >= 100 ? 40 : cluster.members.count >= 10 ? 34 : 28,
                                   height: cluster.members.count >= 100 ? 40 : cluster.members.count >= 10 ? 34 : 28)
                            .background(MapLayer.topicPlaces.color, in: Circle())
                            .overlay(Circle().stroke(RatsColor.card, lineWidth: 2))
                            .shadow(color: .black.opacity(0.25), radius: 3, y: 1)
                    }
                    .buttonStyle(.plain)
                    .accessibilityLabel("\(cluster.members.count) Themen-Orte, zum Heranzoomen tippen")
                }
                .annotationTitles(.hidden)
            }
        }
    }

    private func zoom(to cluster: PointCluster) {
        let points = cluster.members.map { CLLocationCoordinate2D(latitude: $0.latitude, longitude: $0.longitude) }
        guard let region = regionAround(points, minSpan: 0.012) else { return }
        withAnimation(.easeInOut(duration: 0.4)) { camera = .region(region) }
    }

    /// Wohin ein Punkt führt — wie `punktHref` im Web: Ortsseite, Thema, oder
    /// die Beschluss-Suche mit dem Ort als Filter.
    private func open(_ point: CouncilMapPoint) {
        switch point.target {
        case "ort":
            if let placeID = point.placeID { model.navigation.append(.place(id: placeID)) }
        case "location":
            model.pendingLocationFilter = LocationFilter(slug: point.locationSlug ?? point.slug, name: point.name)
            model.navigation.removeAll()
            model.tabletPage = nil
            model.councilSection = .decisions
            model.selectedTab = .council
        default:
            model.navigation.append(.topic(slug: point.slug))
        }
    }

    // MARK: Chips und Brotkrumen

    private var layerChips: some View {
        let onStage = MapLayer.allCases.filter { placeID != nil || !$0.districtOnly }
        return ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 6) {
                ForEach(onStage) { layer in
                    let on = layers.contains(layer)
                    Button {
                        withAnimation(RatsMotion.flow) {
                            if on { layers.remove(layer) } else { layers.insert(layer) }
                        }
                        storedLayers = layers.map(\.rawValue).sorted().joined(separator: ",")
                    } label: {
                        HStack(spacing: 5) {
                            Circle()
                                .fill(on ? layer.color : Color.clear)
                                .overlay(Circle().stroke(layer.color, lineWidth: 1.5))
                                .frame(width: 8, height: 8)
                            Text(layer.label)
                            if let n = layerCount(layer) {
                                Text("\(n)")
                                    .font(RatsFont.mono(9.5, weight: .semibold))
                                    .foregroundStyle(on ? RatsColor.secondary : RatsColor.muted)
                            }
                        }
                        .font(RatsFont.body(12, weight: .semibold))
                        .foregroundStyle(on ? RatsColor.text : RatsColor.secondary)
                        .padding(.horizontal, 10)
                        .frame(height: 30)
                        .councilMapGlassSurface(cornerRadius: 15)
                    }
                    .buttonStyle(RatsPlainButtonStyle())
                    .accessibilityAddTraits(on ? .isSelected : [])
                    .accessibilityLabel("Ebene \(layer.label), \(on ? "an" : "aus")")
                }
            }
            .padding(.trailing, 60)
        }
        .sensoryFeedback(.selection, trigger: layers)
    }

    /// Der Zähler eines Chips: was gerade auf dieser Stufe liegt.
    private func layerCount(_ layer: MapLayer) -> Int? {
        switch layer {
        case .projects: placeID == nil ? overview?.total : board?.projects.count
        case .plans: board?.projects.reduce(0) { $0 + $1.locations.filter { $0.kind == "bplan" }.count }
        case .closures: board?.data?.closures.count
        case .participations: board?.data?.participations.filter { $0.geometry != nil }.count
        case .topicPlaces: layers.contains(.topicPlaces) ? stagePoints.count : nil
        }
    }

    private var breadcrumb: some View {
        HStack(spacing: 6) {
            if let districtName {
                Button { select(nil) } label: {
                    Text("Oldenburg").foregroundStyle(RatsColor.secondary)
                }
                .buttonStyle(RatsPlainButtonStyle())
                RatsIcon(.chevronRight, size: 11).foregroundStyle(RatsColor.muted)
                Text(districtName).fontWeight(.bold)
                Button { select(nil) } label: {
                    Text("Stadt zeigen").foregroundStyle(RatsColor.primary).fontWeight(.semibold)
                }
                .buttonStyle(RatsPlainButtonStyle())
                .padding(.leading, 4)
            } else {
                Text("Oldenburg · \(DistrictShapes.all().count) Ortsbereiche").fontWeight(.bold)
            }
        }
        .font(RatsFont.body(12))
        .foregroundStyle(RatsColor.text)
        .padding(.horizontal, 12)
        .frame(height: 32)
        .councilMapGlassSurface(cornerRadius: 12)
        .accessibilityElement(children: .contain)
        .accessibilityLabel(districtName.map { "Stufe: \($0). Stadt zeigen." } ?? "Stufe: Stadt")
    }

    // MARK: Tafel

    @ViewBuilder
    private var panel: some View {
        if let board, placeID != nil {
            DistrictBoardPanel(model: model, board: board)
        } else {
            DistrictChooserPanel(
                model: model, overview: overview, topics: topics, error: overviewError,
                retry: { Task { await loadOverview() } },
                open: { select($0) }
            )
        }
    }

    // MARK: Zustand

    private func restoreLayers() {
        var set = MapLayer.defaults
        if !storedLayers.isEmpty {
            set = Set(storedLayers.split(separator: ",").compactMap { MapLayer(rawValue: String($0)) })
        }
        if topicsFirst { set.insert(.topicPlaces) }
        layers = set
    }

    private func select(_ id: String?) {
        withAnimation(RatsMotion.flow) { placeID = id }
    }

    private func loadOverview() async {
        overviewError = nil
        do {
            async let overviewRequest: DistrictProjectsOverview = model.api.get("/api/districts/projects")
            async let topicsRequest: [Topic]? = try? await model.api.get("/api/topics")
            overview = try await overviewRequest
            topics = await topicsRequest ?? []
        } catch {
            overviewError = "Die Übersicht lässt sich gerade nicht laden."
        }
    }

    /// Stufenwechsel: ins Viertel (Tafel laden, Kamera auf den Umriss) oder
    /// zurück in die Stadt.
    private func enterStage() async {
        guard let placeID else {
            board = nil
            withAnimation(.easeInOut(duration: 0.45)) { camera = .region(Self.cityRegion) }
            return
        }
        let state = DistrictBoardState(model: model, placeID: placeID)
        board = state
        await state.load()
        guard let data = state.data else { return }
        let outline = districtOutline(named: data.place.name)
        let points = outline.isEmpty
            ? data.projects.flatMap { $0.locations.map { CLLocationCoordinate2D(latitude: $0.latitude, longitude: $0.longitude) } }
            : outline
        if let region = regionAround(points, minSpan: 0.02) {
            withAnimation(.easeInOut(duration: 0.45)) { camera = .region(region) }
        }
    }

    private func loadPoints() async {
        guard layers.contains(.topicPlaces), !mapPointsLoaded else { return }
        if let cached: CouncilMapPoints = await CouncilBrowserCache.shared.load(.map) {
            mapPoints = cached.entities
        }
        do {
            let response: CouncilMapPoints = try await model.api.get("/api/council/entities-map")
            mapPoints = response.entities
            mapPointsLoaded = true
            await CouncilBrowserCache.shared.store(response, for: .map)
        } catch {
            // Der Zwischenspeicher trägt, was er hat; ohne ihn bleibt die Ebene leer.
        }
    }

    private func focusSelected() {
        guard let selected = board?.selected else { return }
        var points = selected.locations.map { CLLocationCoordinate2D(latitude: $0.latitude, longitude: $0.longitude) }
        for location in selected.locations {
            points += lineStrings(location.geometry).flatMap { $0 }
            if location.kind == "bplan" { points += polygons(location.geometry).flatMap { $0 } }
        }
        guard let region = regionAround(points, minSpan: 0.012) else { return }
        withAnimation(.easeInOut(duration: 0.45)) { camera = .region(region) }
    }
}

// MARK: - Punkt der Themen-Orte

/// Ein Themen-Ort: Kreis in der Farbe seiner Art, Größe nach Zahl der
/// Beschlüsse — dieselbe Legende wie `KIND_COLOR` im Web.
private struct TopicPointMark: View {
    let point: CouncilMapPoint

    private var color: Color {
        switch point.kind {
        case "place": Color(red: 0.03, green: 0.39, blue: 0.65)
        case "organisation": Color(red: 0.49, green: 0.23, blue: 0.84)
        case "beschlussort": Color(red: 0.86, green: 0.39, blue: 0.10)
        default: Color(red: 0.03, green: 0.59, blue: 0.42)
        }
    }

    var body: some View {
        let size = min(24, 10 + 2 * sqrt(Double(point.count)))
        Circle()
            .fill(point.target == "location" ? Color(red: 0.86, green: 0.39, blue: 0.10) : color)
            .frame(width: size, height: size)
            .overlay(Circle().stroke(RatsColor.card, lineWidth: 2))
            .shadow(color: .black.opacity(0.25), radius: 3, y: 1)
    }
}
