import Foundation
import RatslotseAPI
import RatslotseDesign
import SwiftUI

/// Ein kompakter Rückblick, auch nach Monaten: Arten → Gremien → Sitzungen.
struct TodayUpdatesWidget: View {
    let model: AppModel
    let refreshID: Int
    @Environment(\.scenePhase) private var scenePhase
    @State private var state: TodayUpdates?
    @State private var failed = false
    @State private var loading = false
    @State private var requestID = UUID()

    var body: some View {
        RatsWidget(state?.firstVisit == true ? "Neu bei Ratslotse" : "Seit deinem letzten Besuch", accent: .buoy, glyph: .history) {
            VStack(alignment: .leading, spacing: 12) {
                if state == nil && !failed {
                    HStack(spacing: 10) {
                        ProgressView()
                        Text("Dein Rückblick wird geladen.").font(RatsFont.notice())
                    }.foregroundStyle(RatsColor.secondary).padding(.vertical, 16)
                }
                if failed {
                    Text("Der Rückblick konnte nicht \(state == nil ? "geladen" : "aktualisiert") werden.")
                        .font(RatsFont.notice()).foregroundStyle(RatsColor.secondary)
                    Button("Erneut versuchen") { Task { await load() } }
                        .frame(minHeight: 44).disabled(loading)
                }
                if let state {
                    Text(state.firstVisit ? "Dein erster Rückblick: die letzten sieben Tage."
                         : "Seit \(dateLabel(state.since)) – auch außerhalb deiner Themen.")
                        .font(RatsFont.notice()).foregroundStyle(RatsColor.secondary)
                    if state.total > 0 {
                        VStack(spacing: 0) {
                            let kinds = ["agenda", "agenda_change", "protocol"].filter { kind in state.groups.contains { $0.kind == kind } }
                            ForEach(kinds, id: \.self) { kind in
                                if kind != kinds.first { Divider().overlay(RatsColor.separator) }
                                TodayUpdateSection(model: model, window: state, kind: kind, groups: state.groups.filter { $0.kind == kind })
                                    .id("\(state.until)-\(kind)")
                            }
                        }
                    } else {
                        Text("Keine neuen relevanten Ratsunterlagen in diesem Zeitraum.")
                            .font(RatsFont.sourceTitle(weight: .semibold))
                        Text("Hier erscheinen Tagesordnungen für Sitzungen ab heute und ergänzte Protokolle mit ihren Ergebnissen.")
                            .font(RatsFont.notice()).foregroundStyle(RatsColor.secondary)
                    }
                }
            }
        }
        .task(id: "\(refreshID)-\(scenePhase)") {
            guard scenePhase == .active else { return }
            await load()
        }
    }

    private func load() async {
        let request = UUID()
        requestID = request
        loading = true
        failed = false
        do {
            try await model.api.sendVoid("/api/today/visit")
            let result: TodayUpdates = try await model.api.get("/api/today/updates")
            guard !Task.isCancelled, requestID == request else { return }
            state = result
        } catch {
            guard !Task.isCancelled, requestID == request else { return }
            failed = true
        }
        loading = false
    }
}

private struct TodayUpdateSection: View {
    let model: AppModel
    let window: TodayUpdates
    let kind: String
    let groups: [TodayUpdateGroup]
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var expanded = false
    @State private var visible = 4
    @ScaledMetric(relativeTo: .title) private var countWidth: CGFloat = 54
    private var count: Int { groups.reduce(0) { $0 + $1.count } }
    private var firstDate: String { groups.map(\.firstSessionDate).min() ?? "" }
    private var lastDate: String { groups.map(\.lastSessionDate).max() ?? "" }
    private var title: String {
        kind == "protocol" ? "Protokolle & Ergebnisse" : kind == "agenda" ? "Neue Tagesordnungen" : "Tagesordnungen geändert"
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            Button { expanded.toggle() } label: {
                HStack(spacing: 12) {
                    Text("\(count)").font(RatsFont.title(28)).monospacedDigit().foregroundStyle(RatsColor.primary)
                        .frame(minWidth: countWidth, alignment: .leading)
                    VStack(alignment: .leading, spacing: 4) {
                        Text(title).font(RatsFont.sourceTitle(weight: .semibold)).foregroundStyle(RatsColor.text)
                        Text(kind == "protocol" ? "\(groups.count) \(groups.count == 1 ? "Gremium" : "Gremien") · \(dateRange(firstDate, lastDate))"
                             : "Für Sitzungen ab heute · nächster Termin \(dateLabel(firstDate))")
                            .font(RatsFont.metadata()).foregroundStyle(RatsColor.secondary)
                    }.frame(maxWidth: .infinity, alignment: .leading)
                    RatsIcon(.chevronDown, size: 15).rotationEffect(.degrees(expanded ? 180 : 0))
                        .foregroundStyle(RatsColor.secondary).accessibilityHidden(true)
                }.padding(.vertical, 16).contentShape(Rectangle())
            }.buttonStyle(UpdateButtonStyle()).accessibilityValue(expanded ? "Geöffnet" : "Geschlossen")
            if expanded {
                VStack(spacing: 0) {
                    ForEach(Array(groups.prefix(visible).enumerated()), id: \.element.committee) { index, group in
                        if index > 0 { Divider().overlay(RatsColor.separator) }
                        TodayUpdateGroupRow(model: model, window: window, group: group)
                    }
                    if visible < groups.count {
                        Button("Weitere Gremien (\(groups.count - visible))") { visible += 4 }
                            .font(RatsFont.notice(weight: .semibold)).frame(minHeight: 44)
                    }
                }.padding(.bottom, 10).transition(reduceMotion ? .identity : .opacity)
            }
        }.animation(reduceMotion ? nil : .easeInOut(duration: 0.2), value: expanded)
    }
}

private struct TodayUpdateGroupRow: View {
    let model: AppModel
    let window: TodayUpdates
    let group: TodayUpdateGroup
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var expanded = false

    var body: some View {
        if group.count == 1 {
            TodayUpdateLink(model: model, item: group.latest)
        } else {
            VStack(alignment: .leading, spacing: 0) {
                Button { expanded.toggle() } label: {
                    HStack(spacing: 12) {
                        VStack(alignment: .leading, spacing: 4) {
                            Text(RatsCommittee.short(group.committee)).font(RatsFont.sourceTitle(weight: .semibold)).foregroundStyle(RatsColor.text)
                            Text("\(group.count) \(group.kind == "protocol" ? "Protokolle" : "Sitzungen") · \(dateRange(group.firstSessionDate, group.lastSessionDate))")
                                .font(RatsFont.metadata()).foregroundStyle(RatsColor.secondary)
                        }.frame(maxWidth: .infinity, alignment: .leading)
                        RatsIcon(.chevronDown, size: 15).rotationEffect(.degrees(expanded ? 180 : 0))
                            .foregroundStyle(RatsColor.secondary).accessibilityHidden(true)
                    }.padding(.vertical, 12).contentShape(Rectangle())
                }.buttonStyle(UpdateButtonStyle()).accessibilityValue(expanded ? "Geöffnet" : "Geschlossen")
                    .accessibilityLabel("\(group.committee), \(group.count) \(group.kind == "protocol" ? "Protokolle" : "Sitzungen"), \(dateRange(group.firstSessionDate, group.lastSessionDate))")
                if expanded {
                    TodayGroupEntries(model: model, window: window, group: group)
                        .padding(.leading, 12).transition(reduceMotion ? .identity : .opacity)
                }
            }.animation(reduceMotion ? nil : .easeInOut(duration: 0.2), value: expanded)
        }
    }
}

private struct TodayGroupEntries: View {
    let model: AppModel
    let window: TodayUpdates
    let group: TodayUpdateGroup
    @State private var items: [TodayUpdate] = []
    @State private var total = 0
    @State private var loading = true
    @State private var failed = false
    @AccessibilityFocusState private var focusedUpdate: String?

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            if loading && items.isEmpty {
                HStack { ProgressView(); Text("Sitzungen werden geladen.").font(RatsFont.notice()) }.padding(.vertical, 12)
            }
            if failed {
                Text("Die Sitzungen konnten nicht geladen werden.").font(RatsFont.notice()).foregroundStyle(RatsColor.secondary)
                Button("Erneut versuchen") { Task { await load() } }.frame(minHeight: 44).disabled(loading)
            }
            ForEach(items) { item in
                TodayUpdateLink(model: model, item: item, inGroup: true)
                    .accessibilityFocused($focusedUpdate, equals: item.id)
                if item.id != items.last?.id { Divider().overlay(RatsColor.separator) }
            }
            if items.count < total {
                Button(loading ? "Wird geladen …" : "Weitere Sitzungen (\(total - items.count))") { Task { await load() } }
                    .font(RatsFont.notice(weight: .semibold)).frame(minHeight: 44).disabled(loading)
            }
        }.task { await load() }
    }

    private func load() async {
        loading = true
        failed = false
        do {
            let result: TodayUpdates = try await model.api.get("/api/today/updates", query: [
                .init(name: "since", value: window.since), .init(name: "until", value: window.until),
                .init(name: "kind", value: group.kind), .init(name: "committee", value: group.committee),
                .init(name: "offset", value: "\(items.count)"), .init(name: "limit", value: "3"),
            ])
            guard !Task.isCancelled else { return }
            let firstNew = items.isEmpty ? nil : result.items.first?.id
            items += result.items
            total = result.total
            if let firstNew { focusedUpdate = firstNew }
        } catch {
            guard !Task.isCancelled else { return }
            failed = true
        }
        loading = false
    }
}

private struct TodayUpdateLink: View {
    let model: AppModel
    let item: TodayUpdate
    var inGroup = false
    var body: some View {
        Button { model.navigation.append(.sessions(ksinr: item.ksinr, tops: [])) } label: {
            HStack(spacing: 12) {
                VStack(alignment: .leading, spacing: 4) {
                    Text(inGroup ? "Sitzung vom \(dateLabel(item.sessionDate))" : RatsCommittee.short(item.committee))
                        .font(RatsFont.sourceTitle(weight: .semibold)).foregroundStyle(RatsColor.text)
                    Text((inGroup ? "Ergänzt am \(dateLabel(item.arrived))" : "Sitzung vom \(dateLabel(item.sessionDate))") +
                         (item.kind == "protocol" && item.decisionCount > 0 ? " · \(item.decisionCount) \(item.decisionCount == 1 ? "Ergebnis" : "Ergebnisse")" : ""))
                        .font(RatsFont.metadata()).foregroundStyle(RatsColor.secondary)
                }.frame(maxWidth: .infinity, alignment: .leading)
                RatsIcon(.chevronRight, size: 15).foregroundStyle(RatsColor.secondary).accessibilityHidden(true)
            }.padding(.vertical, 12).contentShape(Rectangle())
        }.buttonStyle(UpdateButtonStyle())
            .accessibilityLabel("\(item.committee). Sitzung vom \(dateLabel(item.sessionDate)). \(item.decisionCount > 0 ? "\(item.decisionCount) Ergebnisse. " : "")Bei Ratslotse ergänzt am \(dateLabel(item.arrived)).")
            .accessibilityHint("Öffnet die Sitzung mit ihren Unterlagen.")
    }
}

private struct UpdateButtonStyle: ButtonStyle {
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    func makeBody(configuration: Configuration) -> some View {
        configuration.label.background(RatsColor.primary.opacity(configuration.isPressed ? 0.045 : 0))
            .clipShape(RoundedRectangle(cornerRadius: 8))
            .scaleEffect(configuration.isPressed && !reduceMotion ? 0.99 : 1)
            .animation(reduceMotion ? nil : .easeOut(duration: 0.16), value: configuration.isPressed)
    }
}

private func dateLabel(_ value: String) -> String { RatsDate.short(value) ?? value }
private func dateRange(_ first: String, _ last: String) -> String {
    first == last ? dateLabel(first) : "\(dateLabel(first)) – \(dateLabel(last))"
}

private struct TodayUpdates: Decodable, Sendable {
    let since: String
    let until: String
    let firstVisit: Bool
    let total: Int
    let counts: [String: Int]
    let items: [TodayUpdate]
    let groups: [TodayUpdateGroup]
    enum CodingKeys: String, CodingKey {
        case since, until, total, counts, items, groups
        case firstVisit = "first_visit"
    }
}
private struct TodayUpdateGroup: Decodable, Sendable {
    let kind: String
    let committee: String
    let count: Int
    let firstSessionDate: String
    let lastSessionDate: String
    let latest: TodayUpdate
    enum CodingKeys: String, CodingKey {
        case kind, committee, count, latest
        case firstSessionDate = "first_session_date"
        case lastSessionDate = "last_session_date"
    }
}
private struct TodayUpdate: Decodable, Sendable, Identifiable {
    let id: String
    let kind: String
    let ksinr: Int
    let arrived: String
    let committee: String
    let sessionDate: String
    let decisionCount: Int
    enum CodingKeys: String, CodingKey {
        case id, kind, ksinr, arrived, committee
        case sessionDate = "session_date"
        case decisionCount = "decision_count"
    }
}
