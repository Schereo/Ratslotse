import MapKit
import RatslotseAPI
import RatslotseDesign
import SwiftUI

// „Mein Viertel": Was sich in einem Ortsbereich in den nächsten Jahren ändert.
//
// Seit dem Umzug auf die vereinte Stadtkarte (STADTKARTE-PLAN.md, Schritt 6)
// liegt hier nur noch die TAFEL: die Auswahl der Stadt-Stufe
// (`DistrictChooserPanel`) und die Tafel eines Viertels (`DistrictBoardPanel`)
// — Stufenleiste, Liste, Karten, das Detail-Sheet. Die Karte selbst ist
// `CityMapView`; sie und die Tafel teilen sich `DistrictBoardState`. Ein Pin
// oder eine Zeile öffnet das Vorhaben als Sheet mit zwei Rasten.
//
// Gerechnet wird alles im Backend (`council/viertel.py`); die Web-Seite
// `/karte` zeigt dieselben Daten. Wer hier ein Feld ergänzt, zieht
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

func stageOf(_ project: DistrictProject) -> DistrictStage {
    DistrictStage(rawValue: project.stage) ?? .planning
}

func categoryLabel(_ raw: String) -> String {
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

func sortedProjects(_ projects: [DistrictProject]) -> [DistrictProject] {
    projects.sorted { a, b in
        let ra = DistrictStage.allCases.firstIndex(of: stageOf(a)) ?? 9
        let rb = DistrictStage.allCases.firstIndex(of: stageOf(b)) ?? 9
        if ra != rb { return ra < rb }
        return (a.lastDate ?? "") > (b.lastDate ?? "")
    }
}

// MARK: - Auswahl (Stadt-Stufe)

/// Die Tafel der Stadt-Stufe: Stadtzahl, die eigenen Stadtteile, was gerade
/// heraussticht, alle Ortsbereiche nach Zahl. Die Daten hält die Karte —
/// sie färbt damit die Flächen.
struct DistrictChooserPanel: View {
    let model: AppModel
    let overview: DistrictProjectsOverview?
    let topics: [Topic]
    let error: String?
    let retry: () -> Void
    let open: (String) -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: RatsSpacing.lg) {
            VStack(alignment: .leading, spacing: 6) {
                MonoKicker("Mein Viertel")
                Text("Was sich bei dir ändert")
                    .font(RatsFont.title(26))
                Text("Vorhaben aus den Beschlüssen des Stadtrats, je Ortsbereich gebündelt und gegengeprüft — tippe eine Fläche auf der Karte oder wähle unten.")
                    .font(RatsFont.body(14))
                    .foregroundStyle(RatsColor.secondary)
            }
            .ratsStaggered(0)

            if let error {
                ErrorCard(message: error, retry: retry)
            } else if let overview {
                if let total = overview.total, total > 0 {
                    cityNumbers(total: total, stages: overview.stages ?? [:], districts: overview.districts)
                        .ratsStaggered(1)
                }
                let mine = overview.districts.filter { district in
                    topics.contains { $0.name.lowercased() == district.name.lowercased() }
                }
                if !mine.isEmpty {
                    VStack(alignment: .leading, spacing: 8) {
                        MonoKicker("Deine Stadtteile")
                        ForEach(mine) { district in
                            DistrictRow(district: district, highlighted: true) { open(district.placeID) }
                        }
                    }
                    .ratsStaggered(1)
                }
                if let highlights = overview.highlights, !highlights.isEmpty {
                    highlightsCard(highlights).ratsStaggered(2)
                }
                VStack(alignment: .leading, spacing: 8) {
                    MonoKicker("Alle Ortsbereiche")
                    ForEach(Array(overview.districts.sorted { $0.count > $1.count || ($0.count == $1.count && $0.name < $1.name) }.enumerated()), id: \.element.id) { index, district in
                        DistrictRow(district: district, highlighted: false) { open(district.placeID) }
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
    }

    /// Die Stadtzahl mit den drei Ständen — der Blickfang der Anzeigetafel.
    private func cityNumbers(total: Int, stages: [String: Int], districts: [DistrictProjectsOverviewEntry]) -> some View {
        let occupied = districts.filter { $0.count > 0 }.count
        return VStack(alignment: .leading, spacing: 10) {
            MonoKicker("Ganz Oldenburg · Beschlüsse der letzten zwei Jahre")
            HStack(alignment: .firstTextBaseline, spacing: 8) {
                Text("\(total)")
                    .font(RatsFont.title(34))
                    .monospacedDigit()
                Text("Vorhaben")
                    .font(RatsFont.body(16, weight: .semibold))
                    .foregroundStyle(RatsColor.secondary)
            }
            Text("in \(occupied) von \(districts.count) Ortsbereichen")
                .font(RatsFont.body(13))
                .foregroundStyle(RatsColor.secondary)
            HStack(spacing: 14) {
                ForEach([DistrictStage.building, .decided, .planning], id: \.self) { stage in
                    VStack(alignment: .leading, spacing: 2) {
                        HStack(spacing: 5) {
                            Circle().fill(stage.color).frame(width: 7, height: 7)
                            Text(stage.label).font(RatsFont.body(11)).foregroundStyle(RatsColor.secondary)
                        }
                        Text("\(stages[stage.rawValue] ?? 0)")
                            .font(RatsFont.body(18, weight: .bold))
                            .monospacedDigit()
                    }
                }
            }
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(RatsColor.board)
        .overlay(RoundedRectangle(cornerRadius: RatsRadius.panel, style: .continuous).stroke(RatsColor.boardBorder))
        .clipShape(RoundedRectangle(cornerRadius: RatsRadius.panel, style: .continuous))
    }

    /// „Gerade in der Stadt": die Vorhaben, die stadtweit herausstechen — ein
    /// Tipp öffnet das Viertel mit genau diesem Vorhaben.
    private func highlightsCard(_ items: [DistrictHighlight]) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            MonoKicker("Gerade in der Stadt", trailing: "\(items.count) Vorhaben")
            VStack(spacing: 0) {
                ForEach(Array(items.enumerated()), id: \.element.id) { index, item in
                    let stage = DistrictStage(rawValue: item.stage) ?? .planning
                    Button { open(item.placeID) } label: {
                        HStack(spacing: 12) {
                            Circle().fill(stage.color).frame(width: 10, height: 10)
                            VStack(alignment: .leading, spacing: 2) {
                                Text(item.name)
                                    .font(RatsFont.body(14, weight: .semibold))
                                    .foregroundStyle(RatsColor.text)
                                    .lineLimit(1)
                                Text([item.placeName, stage.label, item.when].compactMap { $0 }.joined(separator: " · "))
                                    .font(RatsFont.body(12))
                                    .foregroundStyle(RatsColor.secondary)
                                    .lineLimit(1)
                            }
                            Spacer(minLength: 8)
                            RatsIcon(.chevronRight, size: 14).foregroundStyle(RatsColor.muted)
                        }
                        .padding(.horizontal, 14)
                        .padding(.vertical, 10)
                        .contentShape(Rectangle())
                    }
                    .buttonStyle(RatsPlainButtonStyle())
                    if index < items.count - 1 {
                        Divider().overlay(RatsColor.separator).padding(.leading, 36)
                    }
                }
            }
            .background(RatsColor.card)
            .overlay(RoundedRectangle(cornerRadius: RatsRadius.panel, style: .continuous).stroke(RatsColor.border))
            .clipShape(RoundedRectangle(cornerRadius: RatsRadius.panel, style: .continuous))
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

// MARK: - Tafel (Viertel-Stufe)

/// Die Tafel eines Viertels — alles außer der Karte: Kopf, Stufenleiste,
/// Liste, die Karten der Stadt-Quellen, Nachbarn. Den Zustand (Daten, Filter,
/// Auswahl) hält `DistrictBoardState`, den die Karte teilt.
struct DistrictBoardPanel: View {
    let model: AppModel
    @Bindable var board: DistrictBoardState

    private var projects: [DistrictProject] { board.projects }
    private var visible: [DistrictProject] { board.visible }

    var body: some View {
        VStack(alignment: .leading, spacing: RatsSpacing.lg) {
            if let error = board.error {
                ErrorCard(message: error) { Task { await board.load() } }
            } else if let data = board.data {
                header(data)
                if !projects.isEmpty {
                    stageBar
                        .ratsStaggered(1)
                }
                if !data.upcoming.isEmpty { upcomingCard(data.upcoming).ratsStaggered(2) }
                if projects.isEmpty {
                    // Ohne Zeitstempel hat das Register dieses Viertel noch nie
                    // gerechnet — ein Zustand des Laufs, kein Befund über den Rat.
                    RatsEmptyState(
                        title: data.updatedAt == nil ? "Noch nicht gerechnet" : "Noch kein Vorhaben",
                        message: data.updatedAt == nil
                            ? "Die Tafel für \(data.place.name) ist noch nicht gerechnet — der nächste Lauf füllt sie. Nebenan ist mehr los."
                            : "Für \(data.place.name) hat der Rat in den letzten zwei Jahren nichts beschlossen, was sich als Vorhaben zeigen ließe. Nebenan ist mehr los.",
                        symbol: .mapPin,
                        animation: .searching
                    )
                } else {
                    projectList.ratsStaggered(3)
                }
                if !data.closures.isEmpty { closuresCard(data.closures).ratsStaggered(3) }
                if !data.participations.isEmpty { participationsCard(data.participations).ratsStaggered(3) }
                if !data.investments.isEmpty { investmentsCard(data.investments).ratsStaggered(4) }
                if !data.press.isEmpty { pressCard(data.press).ratsStaggered(4) }
                if !data.neighbours.isEmpty { neighbours(data.neighbours).ratsStaggered(5) }
                Text("Ein Sprachmodell prüft je Beschluss, ob er wirklich dieses Viertel betrifft, und fasst zusammengehörige Beschlüsse zu einem Vorhaben zusammen. Termine stehen nur, wenn ein Beschluss sie nennt.")
                    .font(RatsFont.body(12))
                    .foregroundStyle(RatsColor.muted)
            } else {
                RatsLoadingState(message: "Vorhaben werden geladen …")
            }
        }
        .sheet(item: $board.selected) { project in
            DistrictProjectSheet(
                model: model,
                project: project,
                reported: board.reported.contains(project.projectKey) || project.reported,
                report: { await board.report(project) }
            )
            .presentationDetents([.medium, .large])
            .presentationDragIndicator(.visible)
            .presentationBackground(RatsColor.page)
        }
        .sensoryFeedback(.selection, trigger: board.selected?.id)
    }

    private func header(_ data: DistrictProjects) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            MonoKicker("Mein Viertel")
            Text(data.place.name)
                .font(RatsFont.title(26))
            Text(projects.isEmpty
                 ? (data.updatedAt == nil ? "Die Tafel ist noch nicht gerechnet." : "Noch kein Vorhaben aus den Beschlüssen der letzten zwei Jahre.")
                 : "\(projects.count) Vorhaben aus den Beschlüssen der letzten zwei Jahre")
                .font(RatsFont.body(14))
                .foregroundStyle(RatsColor.secondary)
        }
        .ratsStaggered(0)
    }

    // MARK: Stufen

    private var stageBar: some View {
        let counts = Dictionary(grouping: projects, by: stageOf).mapValues(\.count)
        return ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 6) {
                ForEach(DistrictStage.allCases.filter { counts[$0] != nil }, id: \.self) { candidate in
                    let on = board.stage == candidate
                    Button {
                        withAnimation(RatsMotion.flow) { board.stage = on ? nil : candidate }
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
        .sensoryFeedback(.selection, trigger: board.stage)
    }

    // MARK: Liste

    private var projectList: some View {
        VStack(spacing: 0) {
            ForEach(Array(visible.enumerated()), id: \.element.id) { index, project in
                let stage = stageOf(project)
                let active = board.selected?.id == project.id
                Button { board.selected = project } label: {
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
                    .background(active ? RatsColor.board : Color.clear)
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

    private var closureColor: Color { Color(red: 0.71, green: 0.33, blue: 0.04) }

    private func closuresCard(_ items: [DistrictClosure]) -> some View {
        RatsWidget("Gesperrt und im Bau", accent: .buoy, glyph: .triangleAlert, note: "Stand der Verkehrsbehörde") {
            VStack(alignment: .leading, spacing: 10) {
                ForEach(items) { item in
                    VStack(alignment: .leading, spacing: 2) {
                        HStack(spacing: 6) {
                            Text(item.street).font(RatsFont.body(14, weight: .semibold)).foregroundStyle(RatsColor.text)
                            if let label = item.kindLabel {
                                Text(label).font(RatsFont.body(11, weight: .semibold))
                                    .foregroundStyle(closureColor)
                                    .padding(.horizontal, 7).padding(.vertical, 2)
                                    .background(closureColor.opacity(0.12), in: Capsule())
                            }
                        }
                        Text([item.reason,
                              item.validUntil.flatMap { RatsDate.short($0) }.map { "bis \($0)" }
                              ?? item.validFrom.flatMap { RatsDate.short($0) }.map { "seit \($0)" }]
                            .compactMap { $0 }.joined(separator: " · "))
                            .font(RatsFont.body(12)).foregroundStyle(RatsColor.secondary)
                    }
                }
            }
        }
    }

    /// „Mitreden — Beteiligung läuft": die laufenden Bauleitplan-Beteiligungen
    /// der Stadt mit Schritt und Frist; ein Tipp öffnet sie bei der Stadt.
    private func participationsCard(_ items: [DistrictParticipation]) -> some View {
        RatsWidget("Mitreden — Beteiligung läuft", accent: .buoy, glyph: .messageSquareQuote, note: "planungsbeteiligung.de") {
            VStack(alignment: .leading, spacing: 10) {
                ForEach(items) { item in
                    let inner = VStack(alignment: .leading, spacing: 2) {
                        Text(item.title ?? "Beteiligung").font(RatsFont.body(14, weight: .semibold))
                            .foregroundStyle(RatsColor.text).multilineTextAlignment(.leading)
                        Text([item.step, item.validUntil.flatMap { RatsDate.short($0) }.map { "bis \($0)" },
                              item.geometry != nil ? "Fläche auf der Karte" : nil]
                            .compactMap { $0 }.joined(separator: " · "))
                            .font(RatsFont.body(12)).foregroundStyle(RatsColor.secondary)
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                    if let url = item.url.flatMap(URL.init(string:)) {
                        Link(destination: url) { inner }
                    } else {
                        inner
                    }
                }
            }
        }
    }

    private func pressCard(_ items: [DistrictPressItem]) -> some View {
        RatsWidget("Aktuelles von der Stadt", accent: .marsh, glyph: .newspaper, note: "Pressemitteilungen · 4 Monate") {
            VStack(alignment: .leading, spacing: 10) {
                ForEach(items) { item in
                    if let url = URL(string: item.url) {
                        Link(destination: url) {
                            HStack(alignment: .top, spacing: 8) {
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(item.title).font(RatsFont.body(14, weight: .semibold))
                                        .foregroundStyle(RatsColor.text).multilineTextAlignment(.leading)
                                    Text([item.date.flatMap { RatsDate.short($0) }, item.evidence, "oldenburg.de"]
                                        .compactMap { $0 }.joined(separator: " · "))
                                        .font(RatsFont.body(12)).foregroundStyle(RatsColor.secondary)
                                }
                                Spacer(minLength: 6)
                                RatsIcon(.externalLink, size: 13).foregroundStyle(RatsColor.muted).padding(.top, 3)
                            }
                            .frame(maxWidth: .infinity, alignment: .leading)
                        }
                    }
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

}

// MARK: - Pin

struct DistrictPin: View {
    let color: Color
    let active: Bool
    let dimmed: Bool
    var hollow = false

    var body: some View {
        ZStack {
            if active {
                Circle().stroke(color.opacity(0.45), lineWidth: 5).frame(width: 30, height: 30)
            }
            Circle()
                .fill(hollow ? RatsColor.card : color)
                .frame(width: hollow ? 12 : active ? 20 : 15, height: hollow ? 12 : active ? 20 : 15)
                .overlay(Circle().stroke(hollow ? color : RatsColor.card, style: StrokeStyle(lineWidth: 2, dash: hollow ? [2, 2] : [])))
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
                    let subjects = project.locations.filter { $0.role == "subject" }.map(\.name)
                    let boundaries = project.locations.filter { $0.role == "boundary" }.map(\.name)
                    let context = project.locations.filter { $0.role == "context" }.map(\.name)
                    RatsLabel(
                        (subjects.isEmpty ? "Fläche" : subjects.joined(separator: " · "))
                        + (boundaries.isEmpty ? "" : " · \(subjects.isEmpty ? "zwischen" : "Abschnitt"): \(boundaries.joined(separator: ", "))")
                        + (context.isEmpty ? "" : " · Umfeld: \(context.joined(separator: ", "))"),
                        .mapPin
                    )
                    .font(RatsFont.body(12))
                    .foregroundStyle(RatsColor.secondary)
                }

                // Der Bebauungsplan hinter der Fläche: Nummer, Name, die drei
                // Stationen des Verfahrens — aus den offenen Geodaten der Stadt.
                ForEach(project.locations.filter { $0.plan != nil }) { location in
                    if let plan = location.plan {
                        VStack(alignment: .leading, spacing: 3) {
                            Text("Bebauungsplan \(plan.nr)")
                                .font(RatsFont.body(13, weight: .semibold))
                                .foregroundStyle(RatsColor.text)
                            + Text(" · \(plan.name)")
                                .font(RatsFont.body(13))
                                .foregroundStyle(RatsColor.secondary)
                            Text([
                                plan.status == "in_procedure" ? "In Aufstellung" : nil,
                                plan.resolutionDate.flatMap { RatsDate.short($0) }.map { "Aufstellung \($0)" },
                                plan.adoptionDate.flatMap { RatsDate.short($0) }.map { "Satzung \($0)" },
                                plan.effectiveDate.flatMap { RatsDate.short($0) }.map { "rechtskräftig seit \($0)" },
                            ].compactMap { $0 }.joined(separator: " · "))
                                .font(RatsFont.body(12))
                                .foregroundStyle(RatsColor.secondary)
                            Text("Fläche: Geltungsbereich laut \(plan.source)")
                                .font(RatsFont.body(11))
                                .foregroundStyle(RatsColor.muted)
                        }
                        .padding(.horizontal, 12)
                        .padding(.vertical, 8)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .background(RatsColor.separator, in: RoundedRectangle(cornerRadius: 10))
                        .overlay(RoundedRectangle(cornerRadius: 10).stroke(RatsColor.border, style: StrokeStyle(lineWidth: 1, dash: [4, 3])))
                    }
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
