import RatslotseAPI
import RatslotseDesign
import SwiftUI

/// Eigenständiger Heute-Baustein: Daten, Fehler und Aktionen bleiben hier.
/// Die Heute-Seite bestimmt nur die Position und stößt beim Ziehen neu an.
struct TodayUpdatesWidget: View {
    let model: AppModel
    let refreshID: Int
    @State private var state: DashboardTopicHits?
    @State private var loading = true
    @State private var loadError = false
    @State private var markError = false
    @State private var marking: Int?
    @State private var requestID = UUID()
    @AccessibilityFocusState private var headerFocused: Bool

    var body: some View {
        RatsWidget("Neu zu deinen Themen", accent: .buoy, glyph: .tag) {
            VStack(alignment: .leading, spacing: 12) {
                if loading && state == nil {
                    HStack(spacing: 10) {
                        ProgressView()
                        Text("Deine Neuigkeiten werden geladen.")
                            .font(RatsFont.notice())
                            .foregroundStyle(RatsColor.secondary)
                    }
                    .padding(.vertical, 16)
                }
                if loadError {
                    VStack(alignment: .leading, spacing: 4) {
                        Text(state == nil ? "Deine Neuigkeiten konnten nicht geladen werden."
                             : "Deine Neuigkeiten konnten nicht aktualisiert werden.")
                            .font(RatsFont.notice())
                            .foregroundStyle(RatsColor.secondary)
                        Button("Erneut versuchen") { Task { await load() } }
                            .font(RatsFont.notice(weight: .semibold))
                            .frame(minHeight: 44)
                            .disabled(loading)
                    }
                    .accessibilityElement(children: .contain)
                }
                if let state {
                    let hits = state.hits.filter(\.isNew)
                    let unread = state.unreadDecisions ?? state.unreadTotal
                    if !hits.isEmpty {
                        Text("\(hits.count < unread ? "\(hits.count) von \(unread)" : "\(unread)") ungelesen · \(state.topicCount) \(state.topicCount == 1 ? "Thema" : "Themen")")
                            .font(RatsFont.notice(weight: .semibold))
                            .foregroundStyle(RatsColor.secondary)
                            .accessibilityFocused($headerFocused)
                        VStack(spacing: 0) {
                            ForEach(Array(hits.enumerated()), id: \.element.id) { index, hit in
                                if index > 0 { Divider().overlay(RatsColor.separator) }
                                hitRow(hit)
                            }
                        }
                    } else if state.topicCount == 0 {
                        Text("Was interessiert dich in Oldenburg?")
                            .font(RatsFont.sourceTitle())
                        Text("Lege ein Thema an. Passende Beschlüsse findest du dann hier.")
                            .font(RatsFont.notice())
                            .foregroundStyle(RatsColor.secondary)
                        Button("Erstes Thema anlegen", action: openTopics)
                            .font(RatsFont.notice(weight: .semibold))
                            .frame(minHeight: 44)
                    } else {
                        HStack(alignment: .top, spacing: 10) {
                            RatsIcon(.check, size: 20)
                                .foregroundStyle(RatsColor.primary)
                                .accessibilityHidden(true)
                            VStack(alignment: .leading, spacing: 5) {
                                Text(unread > 0 ? "Weitere Treffer in deinen Themen" : state.total > 0 ? "Alles gelesen" : "Noch keine passenden Beschlüsse")
                                    .font(RatsFont.sourceTitle())
                                Text(unread > 0 ? "Öffne deine Themen, um die übrigen ungelesenen Treffer zu sehen."
                                     : "Sobald neue Treffer zu deinen Themen dazukommen, stehen sie hier.")
                                    .font(RatsFont.notice())
                                    .foregroundStyle(RatsColor.secondary)
                            }
                            .accessibilityElement(children: .combine)
                            .accessibilityFocused($headerFocused)
                        }
                    }
                    if markError {
                        Text("Der Gelesen-Status konnte nicht gespeichert werden. Versuche es erneut.")
                            .font(RatsFont.notice())
                            .foregroundStyle(RatsColor.danger)
                    }
                    if state.topicCount > 0 {
                        Divider().overlay(RatsColor.separator)
                        Button(action: openTopics) {
                            HStack(spacing: 7) {
                                Text("Meine Themen")
                                RatsIcon(.arrowRight, size: 15)
                            }
                            .font(RatsFont.notice(weight: .semibold))
                            .frame(minHeight: 44, alignment: .leading)
                        }
                        .buttonStyle(RatsPlainButtonStyle())
                        .foregroundStyle(RatsColor.primary)
                    }
                }
            }
            .fixedSize(horizontal: false, vertical: true)
        }
        .accessibilityIdentifier("heute-themen-neuigkeiten")
        .task(id: refreshID) { await load() }
    }

    private func hitRow(_ hit: DashboardTopicHit) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Button {
                model.navigation.append(.decision(id: hit.id))
                Task { await markRead(hit, focus: false) }
            } label: {
                VStack(alignment: .leading, spacing: 5) {
                    Text("Zu deinem Thema \(hit.topicName)")
                        .font(RatsFont.body(13, weight: .medium))
                        .foregroundStyle(RatsColor.primary)
                    Text(hit.title)
                        .font(RatsFont.sourceTitle())
                        .foregroundStyle(RatsColor.text)
                        .lineLimit(2)
                    if let summary = hit.summary, !summary.isEmpty {
                        Text(summary)
                            .font(RatsFont.notice())
                            .foregroundStyle(RatsColor.secondary)
                            .lineLimit(2)
                    }
                }
                .multilineTextAlignment(.leading)
                .frame(maxWidth: .infinity, minHeight: 44, alignment: .leading)
                .contentShape(Rectangle())
            }
            .buttonStyle(RatsPlainButtonStyle())
            .ratsZoomSource(RatsZoomID.decision(hit.id))
            Text([hit.outcome.map { OutcomeBadge.label(for: $0) }, RatsDate.short(hit.sessionDate), Committee.short(hit.committee)]
                .compactMap { $0 }.joined(separator: " · "))
                .font(RatsFont.body(13))
                .foregroundStyle(RatsColor.secondary)
            Button {
                Task { await markRead(hit, focus: true) }
            } label: {
                HStack(spacing: 6) {
                    RatsIcon(.check, size: 15)
                    Text(marking == hit.id ? "Wird gespeichert…" : "Als gelesen markieren")
                }
                .font(RatsFont.body(13))
                .frame(minHeight: 44)
                .frame(maxWidth: .infinity, alignment: .trailing)
                .contentShape(Rectangle())
            }
            .foregroundStyle(RatsColor.secondary)
            .buttonStyle(RatsPlainButtonStyle())
            .disabled(marking != nil)
            .accessibilityLabel("Als gelesen markieren: \(hit.title)")
        }
        .padding(.top, 8)
    }

    private func openTopics() {
        model.navigation.removeAll()
        model.selectedTab = .topics
    }

    private func load() async {
#if DEBUG
        if ProcessInfo.processInfo.environment["RATSLOTSE_DEBUG_TODAY_LIVE"] == "1" {
            installPreview()
            loading = false
            return
        }
#endif
        let current = UUID()
        requestID = current
        loading = true
        loadError = false
        do {
            let data: DashboardTopicHits = try await model.api.get(
                "/api/topics/latest-hits",
                query: [.init(name: "limit", value: "3"), .init(name: "unread_only", value: "true")]
            )
            guard !Task.isCancelled, requestID == current else { return }
            state = data
        } catch {
            guard !Task.isCancelled, requestID == current else { return }
            loadError = true
        }
        loading = false
    }

    private func markRead(_ hit: DashboardTopicHit, focus: Bool) async {
        guard marking == nil else { return }
        marking = hit.id
        markError = false
        do {
            try await model.api.sendVoid("/api/topics/decisions/\(hit.id)/seen")
            // Erst nach Bestätigung entfernen. Auch wenn das Nachladen danach
            // scheitert, bleibt dieser erfolgreich gelesene Treffer gelesen.
            state?.hits.removeAll { $0.id == hit.id }
            if let current = state {
                state?.unreadDecisions = max(0, (current.unreadDecisions ?? current.unreadTotal) - 1)
            }
            await load()
            if focus { headerFocused = true }
        } catch {
            markError = true
        }
        marking = nil
    }

#if DEBUG
    private func installPreview() {
        state = .init(
            hits: [
                .init(
                    topicID: 1,
                    topicName: "Sichere Schulwege",
                    id: 99111,
                    title: "Neue Querung an der Cloppenburger Straße",
                    committee: "Verkehrsausschuss",
                    sessionDate: "2026-09-11",
                    outcome: "accepted",
                    summary: "Die Verwaltung plant eine Mittelinsel mit Zebrastreifen auf Höhe der Grundschule.",
                    isNew: true
                ),
                .init(
                    topicID: 2,
                    topicName: "Wohnen in Oldenburg",
                    id: 99112,
                    title: "Nördlich Eßkamp: nächster Planungsschritt",
                    committee: "Stadtplanung & Bauen",
                    sessionDate: "2026-09-11",
                    outcome: "noted",
                    summary: "Der Ausschuss nimmt den Stand der Rahmenplanung zur Kenntnis.",
                    isNew: true
                ),
            ],
            topicCount: 2, total: 2, unreadTotal: 2
        )
    }
#endif
}

private struct DashboardTopicHits: Codable, Sendable {
    var hits: [DashboardTopicHit]
    /// Der neue Zähler zählt eindeutige Beschlüsse. Ältere Server kennen nur
    /// unreadTotal (Treffer je Thema); das zusätzliche Feld bleibt optional.
    let topicCount: Int
    let total: Int
    let unreadTotal: Int
    var unreadDecisions: Int?

    enum CodingKeys: String, CodingKey {
        case hits, total
        case topicCount = "topic_count"
        case unreadTotal = "unread_total"
        case unreadDecisions = "unread_decisions"
    }

    init(hits: [DashboardTopicHit], topicCount: Int, total: Int, unreadTotal: Int) {
        self.hits = hits
        self.topicCount = topicCount
        self.total = total
        self.unreadTotal = unreadTotal
        self.unreadDecisions = nil
    }

    init(from decoder: Decoder) throws {
        let values = try decoder.container(keyedBy: CodingKeys.self)
        hits = try values.decode([DashboardTopicHit].self, forKey: .hits)
        topicCount = try values.decodeIfPresent(Int.self, forKey: .topicCount) ?? 0
        total = try values.decodeIfPresent(Int.self, forKey: .total) ?? 0
        unreadTotal = try values.decodeIfPresent(Int.self, forKey: .unreadTotal) ?? 0
        unreadDecisions = try values.decodeIfPresent(Int.self, forKey: .unreadDecisions)
    }
}

/// Ein Treffer samt Themenbezug. Optionale Angaben bleiben auch gegen ältere
/// Server lesbar; der Gelesen-Ruf verwendet die Beschluss-ID.
private struct DashboardTopicHit: Codable, Sendable, Identifiable {
    let topicID: Int?
    let topicName: String
    let id: Int
    let title: String
    let committee: String
    let sessionDate: String
    let outcome: String?
    let summary: String?
    let isNew: Bool

    enum CodingKeys: String, CodingKey {
        case id, title, committee, outcome, summary
        case topicID = "topic_id"
        case topicName = "topic_name"
        case sessionDate = "session_date"
        case isNew = "is_new"
    }

    init(topicID: Int?, topicName: String, id: Int, title: String, committee: String, sessionDate: String,
         outcome: String?, summary: String?, isNew: Bool) {
        self.topicID = topicID
        self.topicName = topicName
        self.id = id
        self.title = title
        self.committee = committee
        self.sessionDate = sessionDate
        self.outcome = outcome
        self.summary = summary
        self.isNew = isNew
    }

    init(from decoder: Decoder) throws {
        let values = try decoder.container(keyedBy: CodingKeys.self)
        id = try values.decode(Int.self, forKey: .id)
        title = try values.decode(String.self, forKey: .title)
        committee = try values.decode(String.self, forKey: .committee)
        sessionDate = try values.decode(String.self, forKey: .sessionDate)
        topicName = try values.decode(String.self, forKey: .topicName)
        topicID = try values.decodeIfPresent(Int.self, forKey: .topicID)
        outcome = try values.decodeIfPresent(String.self, forKey: .outcome)
        summary = try values.decodeIfPresent(String.self, forKey: .summary)
        isNew = try values.decodeIfPresent(Bool.self, forKey: .isNew) ?? false
    }
}
