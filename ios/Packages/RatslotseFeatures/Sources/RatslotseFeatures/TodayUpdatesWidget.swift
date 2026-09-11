import Foundation
import RatslotseAPI
import RatslotseDesign
import SwiftUI

/// Allgemeiner Rückblick, unabhängig von abonnierten Themen und Gelesen-Marken.
struct TodayUpdatesWidget: View {
    let model: AppModel
    let refreshID: Int
    @Environment(\.scenePhase) private var scenePhase
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var state: TodayUpdates?
    @State private var loading = false
    @State private var failed = false
    @State private var failedMore = false
    @State private var requestID = UUID()
    @AccessibilityFocusState private var focusedUpdate: String?

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
                    Button("Erneut versuchen") { Task { await load(more: failedMore) } }
                        .frame(minHeight: 44).disabled(loading)
                }
                if let state {
                    Text(state.firstVisit ? "Dein erster Rückblick: die letzten sieben Tage."
                         : "Seit \(RatsDate.short(state.since) ?? state.since) – auch außerhalb deiner Themen.")
                        .font(RatsFont.notice()).foregroundStyle(RatsColor.secondary)
                    if state.total > 0 {
                        HStack(alignment: .firstTextBaseline, spacing: 8) {
                            Text("\(state.total)").font(RatsFont.title(28)).monospacedDigit()
                            Text(state.total == 1 ? "Neuigkeit im Rat" : "Neuigkeiten im Rat")
                                .font(RatsFont.sourceTitle()).foregroundStyle(RatsColor.secondary)
                        }.accessibilityElement(children: .combine)
                        Text(summary(state.counts))
                            .font(RatsFont.metadata()).foregroundStyle(RatsColor.secondary)
                        VStack(spacing: 0) {
                            ForEach(Array(state.items.enumerated()), id: \.element.id) { index, item in
                                if index == 0 || item.arrived.prefix(10) != state.items[index - 1].arrived.prefix(10) {
                                    Text("\(RatsDate.short(item.arrived) ?? item.arrived) · Bei Ratslotse ergänzt")
                                        .font(RatsFont.metadata()).foregroundStyle(RatsColor.secondary)
                                        .frame(maxWidth: .infinity, alignment: .leading).padding(.top, 12)
                                }
                                updateRow(item)
                                if item.id != state.items.last?.id { Divider().overlay(RatsColor.separator) }
                            }
                        }
                        if state.items.count < state.total {
                            Button {
                                Task { await load(more: true) }
                            } label: {
                                HStack(spacing: 8) {
                                    Text(loading ? "Wird geladen …" : "Weitere Neuigkeiten (\(state.total - state.items.count))")
                                    if loading { ProgressView() } else { RatsIcon(.chevronDown, size: 15) }
                                }.font(RatsFont.notice(weight: .semibold)).frame(minHeight: 44)
                            }.disabled(loading)
                        }
                    } else {
                        Text("Keine neuen Ratsunterlagen in diesem Zeitraum.")
                            .font(RatsFont.sourceTitle(weight: .semibold))
                        Text("Hier erscheinen neue und geänderte Tagesordnungen sowie ergänzte Protokolle mit ihren Ergebnissen.")
                            .font(RatsFont.notice()).foregroundStyle(RatsColor.secondary)
                    }
                }
            }
            .animation(reduceMotion ? nil : .easeInOut(duration: 0.22), value: state?.items.map(\.id))
        }
        .task(id: "\(refreshID)-\(scenePhase)") {
            guard scenePhase == .active else { return }
            await load()
        }
    }

    private func updateRow(_ item: TodayUpdate) -> some View {
        Button {
            model.navigation.append(.sessions(ksinr: item.ksinr, tops: []))
        } label: {
            HStack(alignment: .top, spacing: 12) {
                RatsIcon(item.kind == "protocol" ? .fileText : .calendar, size: 17)
                    .foregroundStyle(RatsColor.primary).padding(.top, 3)
                    .accessibilityHidden(true)
                VStack(alignment: .leading, spacing: 4) {
                    Text(item.kind == "protocol" ? "Protokoll ergänzt" : item.kind == "agenda" ? "Neue Tagesordnung" : "Tagesordnung geändert")
                        .font(RatsFont.metadata()).foregroundStyle(RatsColor.primary)
                    Text(RatsCommittee.short(item.committee))
                        .font(RatsFont.sourceTitle(weight: .semibold)).foregroundStyle(RatsColor.text)
                    Text("Sitzung vom \(RatsDate.short(item.sessionDate) ?? item.sessionDate)" +
                         (item.kind == "protocol" && item.decisionCount > 0 ? " · \(item.decisionCount) \(item.decisionCount == 1 ? "Ergebnis" : "Ergebnisse")" : ""))
                        .font(RatsFont.metadata()).foregroundStyle(RatsColor.secondary)
                }.frame(maxWidth: .infinity, alignment: .leading)
                RatsIcon(.chevronRight, size: 15).foregroundStyle(RatsColor.secondary)
                    .padding(.top, 3).accessibilityHidden(true)
            }.padding(.vertical, 14).contentShape(Rectangle())
        }.buttonStyle(UpdateButtonStyle())
            .accessibilityFocused($focusedUpdate, equals: item.id)
            .accessibilityLabel("\(item.kind == "protocol" ? "Protokoll ergänzt" : item.kind == "agenda" ? "Neue Tagesordnung" : "Tagesordnung geändert"): \(item.committee). Sitzung vom \(RatsDate.short(item.sessionDate) ?? item.sessionDate). Bei Ratslotse seit \(RatsDate.short(item.arrived) ?? item.arrived).")
            .accessibilityHint("Öffnet die Sitzung mit ihren Unterlagen.")
            .transition(reduceMotion ? .identity : .opacity.combined(with: .move(edge: .top)))
    }

    private func summary(_ counts: [String: Int]) -> String {
        var parts: [String] = []
        if let n = counts["protocol"], n > 0 { parts.append("\(n) \(n == 1 ? "Protokoll" : "Protokolle") ergänzt") }
        if let n = counts["agenda"], n > 0 { parts.append("\(n) neue \(n == 1 ? "Tagesordnung" : "Tagesordnungen")") }
        if let n = counts["agenda_change"], n > 0 { parts.append("\(n) \(n == 1 ? "Tagesordnung" : "Tagesordnungen") geändert") }
        return parts.joined(separator: " · ")
    }

    private func load(more: Bool = false) async {
        let request = UUID()
        requestID = request
        loading = true
        failed = false
        failedMore = more
        do {
            if !more { try await model.api.sendVoid("/api/today/visit") }
            var query: [URLQueryItem] = [.init(name: "limit", value: "3")]
            if more, let state {
                query += [.init(name: "offset", value: "\(state.items.count)"),
                          .init(name: "since", value: state.since), .init(name: "until", value: state.until)]
            }
            var result: TodayUpdates = try await model.api.get("/api/today/updates", query: query)
            guard !Task.isCancelled, requestID == request else { return }
            let firstNewID = more ? result.items.first?.id : nil
            if more, let previous = state {
                result.items = previous.items + result.items
                result.firstVisit = previous.firstVisit
            }
            state = result
            if let firstNewID { focusedUpdate = firstNewID }
        } catch {
            guard !Task.isCancelled, requestID == request else { return }
            failed = true
        }
        loading = false
    }
}

private struct UpdateButtonStyle: ButtonStyle {
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .background(RatsColor.primary.opacity(configuration.isPressed ? 0.045 : 0))
            .clipShape(RoundedRectangle(cornerRadius: 8))
            .scaleEffect(configuration.isPressed && !reduceMotion ? 0.99 : 1)
            .animation(reduceMotion ? nil : .easeOut(duration: 0.16), value: configuration.isPressed)
    }
}

private struct TodayUpdates: Decodable, Sendable {
    let since: String
    let until: String
    var firstVisit: Bool
    let total: Int
    let counts: [String: Int]
    var items: [TodayUpdate]
    enum CodingKeys: String, CodingKey {
        case since, until, total, counts, items
        case firstVisit = "first_visit"
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
