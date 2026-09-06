import MapKit
import RatslotseAPI
import RatslotseDesign
import SwiftUI

// „Mein Viertel": Was sich in einem Ortsbereich in den nächsten Jahren ändert.
//
// Die Karte ist die Bühne (Tims Entscheidung 06.09.2026): oben das Viertel
// als Umriss auf MapKit, ein Pin je Vorhaben in seiner Stand-Farbe, Straßen
// als Linie. Darunter die Stufenleiste als Filter und eine knappe Liste. Ein
// Pin oder eine Zeile öffnet das Vorhaben als Sheet mit zwei Rasten — kein
// Seitwärts-Blättern unter einer Karte, das wären zwei Gesten in einer Fläche.
//
// Gerechnet wird alles im Backend (`council/viertel.py`); die Web-Seite
// `/viertel` zeigt dieselben Daten. Wer hier ein Feld ergänzt, zieht
// `Models.swift` nach und lässt `scripts/ios_vertrag.py` laufen.

// MARK: - Stand und Kategorie

enum DistrictStage: String, CaseIterable {
    case building, decided, planning, idea, done, rejected

    var label: String {
        switch self {
        case .building: "Im Bau"
        case .decided: "Beschlossen"
        case .planning: "In Planung"
        case .idea: "Idee"
        case .done: "Fertig"
        case .rejected: "Abgelehnt"
        }
    }

    var color: Color {
        switch self {
        case .building: RatsColor.signal
        case .decided: RatsColor.success
        case .planning: RatsColor.primary
        case .idea: RatsColor.muted
        case .done: RatsColor.muted
        case .rejected: RatsColor.danger
        }
    }

    /// Der Weg eines Vorhabens; „abgelehnt" ist keine Stufe, sondern ein Ende.
    static let path: [DistrictStage] = [.idea, .planning, .decided, .building, .done]
}

private func stageOf(_ project: DistrictProject) -> DistrictStage {
    DistrictStage(rawValue: project.stage) ?? .planning
}

private func categoryLabel(_ raw: String) -> String {
    switch raw {
    case "housing": "Wohnen & Bauen"
    case "traffic": "Verkehr"
    case "school_childcare": "Schule & Kita"
    case "green": "Grün & Umwelt"
    case "culture_sport_social": "Kultur, Sport & Soziales"
    default: "Sonstiges"
    }
}

private func outcomeLabel(_ raw: String?) -> String? {
    switch raw {
    case "accepted": "Angenommen"
    case "rejected": "Abgelehnt"
    case "postponed": "Vertagt"
    case "noted": "Zur Kenntnis"
    case "no_decision": "Kein Beschluss"
    default: raw
    }
}

private func sortedProjects(_ projects: [DistrictProject]) -> [DistrictProject] {
    projects.sorted { a, b in
        let ra = DistrictStage.allCases.firstIndex(of: stageOf(a)) ?? 9
        let rb = DistrictStage.allCases.firstIndex(of: stageOf(b)) ?? 9
        if ra != rb { return ra < rb }
        return (a.lastDate ?? "") > (b.lastDate ?? "")
    }
}

// MARK: - Auswahl

struct DistrictChooserView: View {
    let model: AppModel
    @State private var overview: DistrictProjectsOverview?
    @State private var topics: [Topic] = []
    @State private var error: String?

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: RatsSpacing.lg) {
                VStack(alignment: .leading, spacing: 6) {
                    MonoKicker("Mein Viertel")
                    Text("Was sich bei dir ändert")
                        .font(RatsFont.title(28))
                    Text("Vorhaben aus den Beschlüssen des Stadtrats, je Ortsbereich gebündelt und gegengeprüft.")
                        .font(RatsFont.body(14))
                        .foregroundStyle(RatsColor.secondary)
                }
                .ratsStaggered(0)

                if let error {
                    ErrorCard(message: error) { Task { await load() } }
                } else if let overview {
                    let mine = overview.districts.filter { district in
                        topics.contains { $0.name.lowercased() == district.name.lowercased() }
                    }
                    if !mine.isEmpty {
                        VStack(alignment: .leading, spacing: 8) {
                            MonoKicker("Deine Stadtteile")
                            ForEach(mine) { district in
                                DistrictRow(district: district, highlighted: true) {
                                    model.navigation.append(.district(id: district.placeID))
                                }
                            }
                        }
                        .ratsStaggered(1)
                    }
                    VStack(alignment: .leading, spacing: 8) {
                        MonoKicker("Alle Ortsbereiche")
                        ForEach(Array(overview.districts.enumerated()), id: \.element.id) { index, district in
                            DistrictRow(district: district, highlighted: false) {
                                model.navigation.append(.district(id: district.placeID))
                            }
                            .ratsStaggered(min(index + 2, 5))
                        }
                    }
                    Text("Die Zahl nennt die Vorhaben der letzten zwei Jahre.")
                        .font(RatsFont.body(12))
                        .foregroundStyle(RatsColor.muted)
                } else {
                    RatsLoadingState(message: "Ortsbereiche werden geladen …")
                }
            }
            .frame(maxWidth: 680, alignment: .leading)
            .padding(.horizontal, 18)
            .padding(.vertical, 20)
        }
        .background(RatsColor.page)
        .navigationTitle("Mein Viertel")
        .toolbarTitleDisplayMode(.inline)
        .task { await load() }
    }

    private func load() async {
        error = nil
        do {
            async let overviewRequest: DistrictProjectsOverview = model.api.get("/api/districts/projects")
            async let topicsRequest: [Topic]? = try? await model.api.get("/api/topics")
            overview = try await overviewRequest
            topics = await topicsRequest ?? []
        } catch {
            self.error = "Die Übersicht lässt sich gerade nicht laden."
        }
    }
}

private struct DistrictRow: View {
    let district: DistrictProjectsOverviewEntry
    let highlighted: Bool
    let open: () -> Void

    var body: some View {
        Button(action: open) {
            HStack(spacing: 12) {
                RatsIcon(.mapPin, size: 16)
                    .foregroundStyle(highlighted ? RatsColor.primary : RatsColor.muted)
                Text(district.name)
                    .font(RatsFont.body(15, weight: .semibold))
                    .foregroundStyle(district.count == 0 && !highlighted ? RatsColor.secondary : RatsColor.text)
                Spacer(minLength: 8)
                Text("\(district.count)")
                    .font(RatsFont.body(13, weight: .semibold))
                    .monospacedDigit()
                    .foregroundStyle(district.count > 0 ? RatsColor.primary : RatsColor.muted)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 2)
                    .background(district.count > 0 ? RatsColor.primary.opacity(0.1) : RatsColor.separator)
                    .clipShape(Capsule())
                RatsIcon(.chevronRight, size: 14)
                    .foregroundStyle(RatsColor.muted)
            }
            .padding(.horizontal, 14)
            .padding(.vertical, 11)
            .background(highlighted ? RatsColor.board : RatsColor.card)
            .overlay(RoundedRectangle(cornerRadius: RatsRadius.card, style: .continuous)
                .stroke(highlighted ? RatsColor.boardBorder : RatsColor.border))
            .clipShape(RoundedRectangle(cornerRadius: RatsRadius.card, style: .continuous))
        }
        .buttonStyle(RatsPlainButtonStyle())
        .accessibilityLabel("\(district.name), \(district.count) Vorhaben")
    }
}

// MARK: - Tafel

struct DistrictBoardView: View {
    let model: AppModel
    let placeID: String
    @State private var data: DistrictProjects?
    @State private var error: String?
    @State private var stage: DistrictStage?
    @State private var selected: DistrictProject?
    @State private var reported: Set<String> = []
    @State private var camera: MapCameraPosition = .automatic
    @State private var outline: [CLLocationCoordinate2D] = []

    private var projects: [DistrictProject] { sortedProjects(data?.projects ?? []) }
    private var visible: [DistrictProject] {
        guard let stage else { return projects }
        return projects.filter { stageOf($0) == stage }
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: RatsSpacing.lg) {
                if let error {
                    ErrorCard(message: error) { Task { await load() } }
                } else if let data {
                    header(data)
                    if !projects.isEmpty {
                        map
                            .frame(height: 300)
                            .clipShape(RoundedRectangle(cornerRadius: RatsRadius.panel, style: .continuous))
                            .overlay(RoundedRectangle(cornerRadius: RatsRadius.panel, style: .continuous)
                                .stroke(RatsColor.border))
                            .ratsStaggered(1)
                        stageBar
                            .ratsStaggered(2)
                    }
                    if !data.upcoming.isEmpty { upcomingCard(data.upcoming).ratsStaggered(2) }
                    if projects.isEmpty {
                        RatsEmptyState(
                            title: "Noch kein Vorhaben",
                            message: "Für \(data.place.name) hat der Rat in den letzten zwei Jahren nichts beschlossen, was sich als Vorhaben zeigen ließe. Nebenan ist mehr los.",
                            symbol: .mapPin,
                            animation: .searching
                        )
                    } else {
                        projectList.ratsStaggered(3)
                    }
                    if !data.investments.isEmpty { investmentsCard(data.investments).ratsStaggered(4) }
                    if !data.neighbours.isEmpty { neighbours(data.neighbours).ratsStaggered(5) }
                    Text("Ein Sprachmodell prüft je Beschluss, ob er wirklich dieses Viertel betrifft, und fasst zusammengehörige Beschlüsse zu einem Vorhaben zusammen. Termine stehen nur, wenn ein Beschluss sie nennt.")
                        .font(RatsFont.body(12))
                        .foregroundStyle(RatsColor.muted)
                } else {
                    RatsLoadingState(message: "Vorhaben werden geladen …")
                }
            }
            .frame(maxWidth: 760, alignment: .leading)
            .padding(.horizontal, 18)
            .padding(.vertical, 20)
        }
        .background(RatsColor.page)
        .navigationTitle(data?.place.name ?? "Mein Viertel")
        .toolbarTitleDisplayMode(.inline)
        .task(id: placeID) { await load() }
        .sheet(item: $selected) { project in
            DistrictProjectSheet(
                model: model,
                project: project,
                reported: reported.contains(project.projectKey) || project.reported,
                report: { await report(project) }
            )
            .presentationDetents([.medium, .large])
            .presentationDragIndicator(.visible)
            .presentationBackground(RatsColor.page)
        }
        .sensoryFeedback(.selection, trigger: selected?.id)
    }

    private func header(_ data: DistrictProjects) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            MonoKicker("Mein Viertel")
            Text(data.place.name)
                .font(RatsFont.title(28))
            Text(projects.isEmpty
                 ? "Noch kein Vorhaben aus den Beschlüssen der letzten zwei Jahre."
                 : "\(projects.count) Vorhaben aus den Beschlüssen der letzten zwei Jahre")
                .font(RatsFont.body(14))
                .foregroundStyle(RatsColor.secondary)
        }
        .ratsStaggered(0)
    }

    // MARK: Karte

    private var map: some View {
        Map(position: $camera, interactionModes: [.pan, .zoom]) {
            if outline.count > 2 {
                MapPolygon(coordinates: outline)
                    .foregroundStyle(RatsColor.primary.opacity(0.06))
                    .stroke(RatsColor.primary.opacity(0.8), lineWidth: 2)
            }
            ForEach(projects) { project in
                let stage = stageOf(project)
                let dimmed = self.stage != nil && self.stage != stage
                let active = selected?.id == project.id
                ForEach(project.locations) { location in
                    ForEach(Array(lineStrings(location.geometry).enumerated()), id: \.offset) { _, line in
                        MapPolyline(coordinates: line)
                            .stroke(stage.color.opacity(dimmed ? 0.18 : 0.75),
                                    style: StrokeStyle(lineWidth: active ? 7 : 5, lineCap: .round, lineJoin: .round))
                    }
                    Annotation(project.name, coordinate: CLLocationCoordinate2D(
                        latitude: location.latitude, longitude: location.longitude
                    ), anchor: .center) {
                        Button {
                            selected = project
                        } label: {
                            DistrictPin(color: stage.color, active: active, dimmed: dimmed)
                        }
                        .buttonStyle(.plain)
                        .accessibilityLabel("\(project.name), \(stage.label)")
                    }
                    .annotationTitles(.hidden)
                }
            }
        }
        .mapStyle(.standard(elevation: .flat, pointsOfInterest: .excludingAll))
        .mapControlVisibility(.hidden)
        .onChange(of: selected?.id) { _, _ in focusSelected() }
    }

    private func focusSelected() {
        guard let selected else { return }
        var points = selected.locations.map { CLLocationCoordinate2D(latitude: $0.latitude, longitude: $0.longitude) }
        for location in selected.locations { points += lineStrings(location.geometry).flatMap { $0 } }
        guard let region = regionAround(points, minSpan: 0.012) else { return }
        withAnimation(.easeInOut(duration: 0.45)) { camera = .region(region) }
    }

    // MARK: Stufen

    private var stageBar: some View {
        let counts = Dictionary(grouping: projects, by: stageOf).mapValues(\.count)
        return ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 6) {
                ForEach(DistrictStage.allCases.filter { counts[$0] != nil }, id: \.self) { candidate in
                    let on = stage == candidate
                    Button {
                        withAnimation(RatsMotion.flow) { stage = on ? nil : candidate }
                    } label: {
                        HStack(spacing: 6) {
                            Circle().fill(candidate.color).frame(width: 8, height: 8)
                            Text(candidate.label)
                            Text("\(counts[candidate] ?? 0)")
                                .monospacedDigit()
                                .foregroundStyle(on ? RatsColor.text : RatsColor.muted)
                        }
                        .font(RatsFont.body(12, weight: .semibold))
                        .foregroundStyle(on ? RatsColor.text : RatsColor.secondary)
                        .padding(.horizontal, 11)
                        .padding(.vertical, 7)
                        .background(RatsColor.card)
                        .overlay(Capsule().stroke(on ? RatsColor.text : RatsColor.border))
                        .clipShape(Capsule())
                    }
                    .buttonStyle(RatsPlainButtonStyle())
                    .accessibilityAddTraits(on ? .isSelected : [])
                }
            }
        }
        .sensoryFeedback(.selection, trigger: stage)
    }

    // MARK: Liste

    private var projectList: some View {
        VStack(spacing: 0) {
            ForEach(Array(visible.enumerated()), id: \.element.id) { index, project in
                let stage = stageOf(project)
                Button { selected = project } label: {
                    HStack(spacing: 12) {
                        Circle().fill(stage.color).frame(width: 10, height: 10)
                        VStack(alignment: .leading, spacing: 2) {
                            Text(project.name)
                                .font(RatsFont.body(15, weight: .semibold))
                                .foregroundStyle(RatsColor.text)
                                .lineLimit(1)
                            Text([stage.label, project.when, categoryLabel(project.category)].compactMap { $0 }.joined(separator: " · "))
                                .font(RatsFont.body(12))
                                .foregroundStyle(RatsColor.secondary)
                                .lineLimit(1)
                        }
                        Spacer(minLength: 8)
                        RatsIcon(.chevronRight, size: 14)
                            .foregroundStyle(RatsColor.muted)
                    }
                    .padding(.horizontal, 14)
                    .padding(.vertical, 11)
                    .contentShape(Rectangle())
                }
                .buttonStyle(RatsPlainButtonStyle())
                if index < visible.count - 1 {
                    Divider().overlay(RatsColor.separator).padding(.leading, 36)
                }
            }
            if visible.isEmpty {
                Text("Kein Vorhaben in dieser Stufe.")
                    .font(RatsFont.body(13))
                    .foregroundStyle(RatsColor.secondary)
                    .padding(16)
            }
        }
        .background(RatsColor.card)
        .overlay(RoundedRectangle(cornerRadius: RatsRadius.panel, style: .continuous).stroke(RatsColor.border))
        .clipShape(RoundedRectangle(cornerRadius: RatsRadius.panel, style: .continuous))
    }

    // MARK: Weitere Quellen

    private func upcomingCard(_ items: [DistrictUpcomingItem]) -> some View {
        RatsWidget("Demnächst im Rat", accent: .buoy, glyph: .calendarDays, note: "hier wird entschieden") {
            VStack(alignment: .leading, spacing: 10) {
                ForEach(items) { item in
                    Button {
                        model.navigation.append(.sessions(ksinr: item.ksinr, tops: item.itemNumber.map { [$0] } ?? []))
                    } label: {
                        VStack(alignment: .leading, spacing: 2) {
                            Text("\(RatsDate.short(item.sessionDate) ?? item.sessionDate)\(item.sessionTime.map { ", \($0) Uhr" } ?? "") · \(Committee.entry(item.committee ?? "").short)")
                                .font(RatsFont.body(12))
                                .foregroundStyle(RatsColor.secondary)
                            Text(item.title)
                                .font(RatsFont.body(14, weight: .semibold))
                                .foregroundStyle(RatsColor.text)
                                .multilineTextAlignment(.leading)
                        }
                        .frame(maxWidth: .infinity, alignment: .leading)
                    }
                    .buttonStyle(RatsPlainButtonStyle())
                }
            }
        }
    }

    private func investmentsCard(_ items: [DistrictInvestment]) -> some View {
        RatsWidget("Im Investitionsprogramm \(items[0].programmeYear)", accent: .marsh, glyph: .hammer,
                   note: "Summe über die Programmjahre") {
            VStack(alignment: .leading, spacing: 8) {
                ForEach(items, id: \.label) { item in
                    HStack(alignment: .firstTextBaseline) {
                        Text(item.label).font(RatsFont.body(14))
                        Spacer(minLength: 8)
                        Text(euro(item.totalEUR))
                            .font(RatsFont.body(13, weight: .semibold))
                            .monospacedDigit()
                            .foregroundStyle(RatsColor.secondary)
                    }
                }
            }
        }
    }

    private func neighbours(_ items: [DistrictNeighbour]) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            MonoKicker("Nebenan")
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 8) {
                    ForEach(items) { neighbour in
                        Button { model.navigation.append(.district(id: neighbour.placeID)) } label: {
                            HStack(spacing: 6) {
                                Text(neighbour.name).font(RatsFont.body(13, weight: .semibold))
                                Text("\(neighbour.count)").font(RatsFont.body(12)).monospacedDigit()
                                    .foregroundStyle(RatsColor.muted)
                            }
                            .foregroundStyle(RatsColor.text)
                            .padding(.horizontal, 12)
                            .padding(.vertical, 8)
                            .background(RatsColor.card)
                            .overlay(Capsule().stroke(RatsColor.border))
                            .clipShape(Capsule())
                        }
                        .buttonStyle(RatsPlainButtonStyle())
                    }
                }
            }
        }
    }

    // MARK: Laden

    private func load() async {
        error = nil
        do {
            let loaded: DistrictProjects = try await model.api.get("/api/districts/\(placeID)/projects")
            data = loaded
            outline = districtOutline(named: loaded.place.name)
            let points = outline.isEmpty
                ? loaded.projects.flatMap { $0.locations.map { CLLocationCoordinate2D(latitude: $0.latitude, longitude: $0.longitude) } }
                : outline
            if let region = regionAround(points, minSpan: 0.02) { camera = .region(region) }
        } catch {
            self.error = "Die Tafel lässt sich gerade nicht laden."
        }
    }

    private func report(_ project: DistrictProject) async {
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

// MARK: - Pin

private struct DistrictPin: View {
    let color: Color
    let active: Bool
    let dimmed: Bool

    var body: some View {
        ZStack {
            if active {
                Circle().stroke(color.opacity(0.45), lineWidth: 5).frame(width: 30, height: 30)
            }
            Circle()
                .fill(color)
                .frame(width: active ? 20 : 15, height: active ? 20 : 15)
                .overlay(Circle().stroke(RatsColor.card, lineWidth: 2))
                .shadow(color: .black.opacity(0.25), radius: 3, y: 1)
        }
        .opacity(dimmed ? 0.3 : 1)
        .animation(RatsMotion.flow, value: active)
        .animation(RatsMotion.flow, value: dimmed)
    }
}

// MARK: - Detail-Sheet

private struct DistrictProjectSheet: View {
    let model: AppModel
    let project: DistrictProject
    let reported: Bool
    let report: () async -> Void
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        let stage = stageOf(project)
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                HStack(spacing: 8) {
                    Text(stage.label)
                        .font(RatsFont.body(11, weight: .semibold))
                        .foregroundStyle(stage == .building ? RatsColor.primaryText : stage.color)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 3)
                        .background(stage == .building ? stage.color : stage.color.opacity(0.14))
                        .clipShape(Capsule())
                    if let when = project.when {
                        Text(when).font(RatsFont.body(12, weight: .semibold)).foregroundStyle(RatsColor.signal)
                    }
                    Spacer()
                    Text(categoryLabel(project.category))
                        .font(RatsFont.body(12))
                        .foregroundStyle(RatsColor.secondary)
                }
                Text(project.name)
                    .font(RatsFont.title(22))
                    .fixedSize(horizontal: false, vertical: true)
                Text(project.what)
                    .font(RatsFont.body(15))
                    .foregroundStyle(RatsColor.bodyText)
                    .fixedSize(horizontal: false, vertical: true)

                if stage != .rejected { stagePath(stage) }

                if !project.locations.isEmpty {
                    RatsLabel(project.locations.map(\.name).joined(separator: " · "), .mapPin)
                        .font(RatsFont.body(12))
                        .foregroundStyle(RatsColor.secondary)
                }

                VStack(alignment: .leading, spacing: 0) {
                    MonoKicker("\(project.decisions.count) \(project.decisions.count == 1 ? "Beschluss" : "Beschlüsse")")
                        .padding(.bottom, 6)
                    ForEach(Array(project.decisions.enumerated()), id: \.element.id) { index, decision in
                        Button {
                            dismiss()
                            model.navigation.append(.decision(id: decision.id))
                        } label: {
                            HStack(alignment: .top, spacing: 10) {
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(decision.title)
                                        .font(RatsFont.body(14))
                                        .foregroundStyle(RatsColor.text)
                                        .multilineTextAlignment(.leading)
                                    Text("\(RatsDate.short(decision.date) ?? decision.date) · \(Committee.entry(decision.committee ?? "").short)\(outcomeLabel(decision.outcome).map { " · \($0)" } ?? "")")
                                        .font(RatsFont.body(12))
                                        .foregroundStyle(RatsColor.secondary)
                                }
                                Spacer(minLength: 6)
                                RatsIcon(.arrowRight, size: 14).foregroundStyle(RatsColor.muted).padding(.top, 3)
                            }
                            .padding(.vertical, 8)
                            .contentShape(Rectangle())
                        }
                        .buttonStyle(RatsPlainButtonStyle())
                        if index < project.decisions.count - 1 {
                            Divider().overlay(RatsColor.separator)
                        }
                    }
                }

                if model.user != nil {
                    Divider().overlay(RatsColor.separator)
                    if reported {
                        RatsLabel("Gemeldet — danke.", .check)
                            .font(RatsFont.body(12))
                            .foregroundStyle(RatsColor.secondary)
                    } else {
                        Button { Task { await report() } } label: {
                            RatsLabel("Gehört nicht hierher", .mailWarning)
                                .font(RatsFont.body(12))
                                .foregroundStyle(RatsColor.secondary)
                        }
                        .buttonStyle(RatsPlainButtonStyle())
                    }
                }
            }
            .padding(.horizontal, 20)
            .padding(.top, 26)
            .padding(.bottom, 30)
        }
    }

    private func stagePath(_ current: DistrictStage) -> some View {
        let reached = DistrictStage.path.firstIndex(of: current) ?? 0
        return HStack(spacing: 4) {
            ForEach(Array(DistrictStage.path.enumerated()), id: \.element) { index, step in
                let full = index <= reached
                ZStack {
                    Circle()
                        .fill(full ? step.color : Color.clear)
                        .overlay(Circle().stroke(full ? Color.clear : RatsColor.border))
                        .frame(width: 20, height: 20)
                    if full {
                        RatsIcon(.check, size: 11).foregroundStyle(RatsColor.primaryText)
                    }
                }
                .accessibilityLabel(step.label + (full ? ", erreicht" : ""))
                if index < DistrictStage.path.count - 1 {
                    Capsule()
                        .fill(index < reached ? RatsColor.primary.opacity(0.6) : RatsColor.border)
                        .frame(height: 2)
                }
            }
        }
        .accessibilityElement(children: .combine)
    }
}

// MARK: - Geometrie-Helfer

/// LineString/MultiLineString aus dem durchgereichten GeoJSON — für die
/// Straßenlinie auf der Karte. Alles andere (Flächen) bleibt beim Pin.
private func lineStrings(_ geometry: JSONValue?) -> [[CLLocationCoordinate2D]] {
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

private func regionAround(_ points: [CLLocationCoordinate2D], minSpan: Double) -> MKCoordinateRegion? {
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

/// Der Umriss des Ortsbereichs aus dem gebündelten GeoJSON (31 Flächen).
private func districtOutline(named name: String) -> [CLLocationCoordinate2D] {
    guard let url = Bundle.main.url(forResource: "stadtteile-oldenburg", withExtension: "json"),
          let data = try? Data(contentsOf: url),
          let objects = try? MKGeoJSONDecoder().decode(data) else { return [] }
    for case let feature as MKGeoJSONFeature in objects {
        guard let properties = feature.properties,
              let json = try? JSONSerialization.jsonObject(with: properties) as? [String: Any],
              json["name"] as? String == name else { continue }
        for geometry in feature.geometry {
            if let polygon = geometry as? MKPolygon { return polygon.coordinates }
            if let multi = geometry as? MKMultiPolygon, let largest = multi.polygons.max(by: { $0.pointCount < $1.pointCount }) {
                return largest.coordinates
            }
        }
    }
    return []
}

private extension MKPolygon {
    var coordinates: [CLLocationCoordinate2D] {
        var out = [CLLocationCoordinate2D](repeating: kCLLocationCoordinate2DInvalid, count: pointCount)
        getCoordinates(&out, range: NSRange(location: 0, length: pointCount))
        return out
    }
}

private func euro(_ value: Double) -> String {
    if value >= 1_000_000 {
        return String(format: "%.2f Mio. €", value / 1_000_000).replacingOccurrences(of: ".", with: ",")
    }
    let formatter = NumberFormatter()
    formatter.numberStyle = .decimal
    formatter.locale = Locale(identifier: "de_DE")
    formatter.maximumFractionDigits = 0
    return (formatter.string(from: NSNumber(value: value)) ?? "\(Int(value))") + " €"
}
