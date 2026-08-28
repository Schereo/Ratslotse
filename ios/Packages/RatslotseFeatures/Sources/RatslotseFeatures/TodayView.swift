import RatslotseAPI
import RatslotseDesign
import SwiftUI

struct TodayView: View {
    let model: AppModel
    @State private var today: TodayCard?
    @State private var week: WeekDecision?
    @State private var preview: WeekPreview?
    @State private var foundPiece: FoundPiece?
    @State private var recent: [DecisionSummary] = []
    @State private var upcomingSessions: [CouncilSession] = []
    @State private var latestTopicHits: [DashboardTopicHit] = []
    @State private var weekNumber: DashboardWeekNumber?
    @State private var now = Date.now
    @State private var error: String?

    var body: some View {
        ScrollView {
            LazyVStack(alignment: .leading, spacing: RatsSpacing.xl) {
                HStack(alignment: .center, spacing: 14) {
                    Lotti3DView(scene: .wave)
                        .frame(width: 92, height: 84)
                    VStack(alignment: .leading, spacing: 7) {
                        MonoKicker(dayLabel)
                        Text(greeting)
                            .font(RatsFont.title(31))
                        Text("Das Wichtigste aus Oldenburgs Rat – kurz eingeordnet und mit Quellen.")
                            .font(RatsFont.body())
                            .foregroundStyle(RatsColor.secondary)
                    }
                }

                Button {
                    model.navigation.removeAll()
                    model.selectedTab = .questions
                } label: {
                    HStack(spacing: 9) {
                        RatsGlyphView(glyph: .ask, color: .white, lineWidth: 1.7)
                            .frame(width: 19, height: 19)
                        Text("Frag den Rat")
                    }
                    .frame(maxWidth: .infinity)
                }
                .buttonStyle(SignalButtonStyle())

                ViewThatFits(in: .horizontal) {
                    HStack(alignment: .top, spacing: 16) {
                        VStack(alignment: .leading, spacing: RatsSpacing.xl) {
                            primaryColumn
                        }
                        .frame(minWidth: 350, maxWidth: .infinity, alignment: .topLeading)

                        VStack(alignment: .leading, spacing: RatsSpacing.xl) {
                            secondaryColumn
                        }
                        .frame(minWidth: 350, maxWidth: .infinity, alignment: .topLeading)
                    }

                    VStack(alignment: .leading, spacing: RatsSpacing.xl) {
                        primaryColumn
                        secondaryColumn
                    }
                }
            }
            .frame(maxWidth: 980, alignment: .leading)
            .padding(.horizontal, 18)
            .padding(.vertical, 24)
        }
        .background(RatsColor.page)
        .navigationTitle("Heute")
        .toolbarTitleDisplayMode(.inline)
        .refreshable { await load() }
        .task {
#if DEBUG
            if ProcessInfo.processInfo.environment["RATSLOTSE_DEBUG_TODAY_LIVE"] == "1" {
                installDebugDashboard()
                return
            }
#endif
            if today == nil { await load() }
        }
        .task {
            while !Task.isCancelled {
                try? await Task.sleep(for: .seconds(60))
                now = .now
            }
        }
    }

    @ViewBuilder
    private var primaryColumn: some View {
        if let liveSession {
            LiveCouncilCard(session: liveSession, now: now) {
                if let id = liveSession.ksinr { model.navigation.append(.sessions(ksinr: id, tops: [])) }
                else { openSessions() }
            }
        }
        if let today, liveSession == nil, today.state != "naechste" || preview?.found != true {
            TodayStatusCard(today: today, openSessions: openSessions)
        }
        if let preview, preview.found {
            WeekPreviewCard(preview: preview) { sessionID, itemNumber in
                model.navigation.append(.sessions(ksinr: sessionID, tops: [itemNumber]))
            }
        }
    }

    @ViewBuilder
    private var secondaryColumn: some View {
        if !latestTopicHits.isEmpty {
            LatestTopicHitsCard(hits: latestTopicHits) { model.navigation.append(.decision(id: $0)) }
        }

        if let weekNumber {
            DashboardWeekNumberCard(number: weekNumber) { decisionID in
                if let decisionID { model.navigation.append(.decision(id: decisionID)) }
                else {
                    model.navigation.removeAll()
                    model.selectedTab = .council
                    model.councilSection = .decisions
                }
            }
        }

        if let week, week.found, let id = week.decisionID {
            Button { model.navigation.append(.decision(id: id)) } label: {
                VStack(alignment: .leading, spacing: 9) {
                    MonoKicker("Diese Woche im Rat")
                    Text(week.title ?? "Aktueller Beschluss")
                        .font(RatsFont.title(20))
                        .multilineTextAlignment(.leading)
                    if let outcome = week.outcome { OutcomeBadge(outcome) }
                    if let reason = week.interestReason, !reason.isEmpty {
                        Text(reason).font(RatsFont.body(14)).foregroundStyle(RatsColor.secondary)
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .ratsCard()
            }
            .buttonStyle(.plain)
        }

        if let foundPiece, foundPiece.found, let id = foundPiece.decisionID {
            Button { model.navigation.append(.decision(id: id)) } label: {
                VStack(alignment: .leading, spacing: 10) {
                    MonoKicker(foundPiece.kicker ?? "Fundstück")
                    Text(foundPiece.title ?? "Aus dem Archiv")
                        .font(RatsFont.title(20))
                    if let story = foundPiece.story {
                        Text(story).font(RatsFont.body(14)).foregroundStyle(RatsColor.bodyText)
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .ratsCard()
            }
            .buttonStyle(.plain)
        }

        if !recent.isEmpty {
            VStack(alignment: .leading, spacing: 12) {
                MonoKicker("Letzte Beschlüsse", trailing: "\(recent.count) gezeigt")
                ForEach(recent) { decision in
                    Button { model.navigation.append(.decision(id: decision.id)) } label: {
                        DecisionRow(decision: decision)
                    }
                    .buttonStyle(.plain)
                    if decision.id != recent.last?.id { Divider().overlay(RatsColor.separator) }
                }
            }
            .ratsCard()
        }

        Button {
            model.navigation.append(.quiz(area: nil))
        } label: {
            Label("Oldenburg-Quiz spielen", systemImage: "checkmark.circle")
                .frame(maxWidth: .infinity)
        }
        .buttonStyle(SecondaryButtonStyle())

        if let error {
            ErrorCard(message: error) { Task { await load() } }
        }
    }

    private var greeting: String {
        let hour = Calendar.current.component(.hour, from: .now)
        let prefix = hour < 11 ? "Moin" : hour < 18 ? "Guten Tag" : "Guten Abend"
        guard let name = model.user?.displayName?.split(separator: " ").first else { return prefix }
        if name.localizedCaseInsensitiveCompare("Moin") == .orderedSame { return prefix }
        return "\(prefix), \(name)"
    }

    private var dayLabel: String {
        Date.now.formatted(.dateTime.locale(Locale(identifier: "de_DE")).weekday(.wide).day().month(.wide))
    }

    private func openSessions() { model.navigation.append(.sessions(ksinr: nil, tops: [])) }

    private var liveSession: CouncilSession? {
        upcomingSessions.first { session in
            guard session.sessionDate.prefix(10) == localISODate(now),
                  let time = session.sessionTime,
                  let start = sessionStart(time, on: now)
            else { return false }
            let age = now.timeIntervalSince(start)
            return age >= 0 && age <= 4 * 60 * 60
        }
    }

    private func load() async {
        error = nil
        do {
            async let todayRequest: TodayCard = model.api.get("/api/council/heute")
            async let weekRequest: WeekDecision = model.api.get("/api/council/diese-woche")
            async let previewRequest: WeekPreview = model.api.get("/api/council/wochenvorschau")
            async let foundRequest: FoundPiece = model.api.get("/api/council/fundstueck")
            async let decisionsRequest: DecisionPage = model.api.get(
                "/api/council/decisions", query: [.init(name: "limit", value: "5")]
            )
            async let sessionsRequest: SessionPage? = try? await model.api.get(
                "/api/council/sessions",
                query: [.init(name: "scope", value: "upcoming"), .init(name: "limit", value: "3")]
            )
            async let hitsRequest: DashboardTopicHits? = try? await model.api.get(
                "/api/topics/latest-hits", query: [.init(name: "limit", value: "2")]
            )
            async let numberRequest: DashboardWeekNumber? = try? await model.api.get("/api/council/zahl-der-woche")
            let (newToday, newWeek, newPreview, newFound, page) = try await (
                todayRequest, weekRequest, previewRequest, foundRequest, decisionsRequest
            )
            today = newToday
            week = newWeek
            preview = newPreview
            foundPiece = newFound
            recent = page.decisions
            if let sessions = await sessionsRequest { upcomingSessions = sessions.sessions }
            if let hits = await hitsRequest { latestTopicHits = hits.hits }
            if let number = await numberRequest { weekNumber = number }
        } catch {
            self.error = error.localizedDescription
        }
    }

#if DEBUG
    private func installDebugDashboard() {
        let calendar = Calendar.current
        let started = calendar.date(byAdding: .minute, value: -42, to: now) ?? now
        let time = started.formatted(.dateTime.locale(Locale(identifier: "de_DE")).hour(.twoDigits(amPM: .omitted)).minute(.twoDigits))
        let json = """
        {
          "ksinr": 99101,
          "committee": "Rat",
          "session_date": "\(localISODate(now))",
          "session_time": "\(time)",
          "location": "Altes Rathaus",
          "title": "Sitzung des Rates",
          "n_items": 18,
          "my_topic_items": [{"item_number":"Ö 7"}, {"item_number":"Ö 12"}]
        }
        """
        if let session = try? JSONDecoder().decode(CouncilSession.self, from: Data(json.utf8)) {
            upcomingSessions = [session]
        }
        latestTopicHits = [
            .init(
                topicName: "Sichere Schulwege",
                id: 99111,
                title: "Neue Querung an der Cloppenburger Straße",
                committee: "Verkehrsausschuss",
                sessionDate: localISODate(now)
            ),
            .init(
                topicName: "Wohnen in Oldenburg",
                id: 99112,
                title: "Nördlich Eßkamp: nächster Planungsschritt",
                committee: "Stadtplanung & Bauen",
                sessionDate: localISODate(now)
            ),
        ]
        weekNumber = .init(
            kind: "betrag",
            amountEUR: 9_512_500,
            decisionID: 99113,
            title: "Mehrbedarf für den Teilhaushalt 10",
            sessionDate: localISODate(now),
            count: nil,
            windowDays: 7
        )
    }
#endif
}

private struct DashboardTopicHits: Codable, Sendable {
    let hits: [DashboardTopicHit]
}

private struct DashboardTopicHit: Codable, Sendable, Identifiable {
    let topicName: String
    let id: Int
    let title: String
    let committee: String
    let sessionDate: String

    enum CodingKeys: String, CodingKey {
        case id, title, committee
        case topicName = "topic_name"
        case sessionDate = "session_date"
    }
}

private struct DashboardWeekNumber: Codable, Sendable {
    let kind: String
    let amountEUR: Double?
    let decisionID: Int?
    let title: String?
    let sessionDate: String?
    let count: Int?
    let windowDays: Int

    enum CodingKeys: String, CodingKey {
        case kind, title, count
        case amountEUR = "amount_eur"
        case decisionID = "decision_id"
        case sessionDate = "session_date"
        case windowDays = "window_days"
    }
}

private struct LiveCouncilCard: View {
    let session: CouncilSession
    let now: Date
    let openAgenda: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 13) {
            HStack(spacing: 8) {
                ZStack {
                    Circle().fill(RatsColor.danger.opacity(0.15)).frame(width: 16, height: 16)
                    Circle().fill(RatsColor.danger).frame(width: 8, height: 8)
                }
                .accessibilityHidden(true)
                Text("LIVE · SEIT \(runningTime.uppercased())")
                    .font(RatsFont.mono(9, weight: .semibold))
                    .tracking(0.8)
                    .foregroundStyle(RatsColor.danger)
                Spacer(minLength: 6)
                if let location = session.location, !location.isEmpty {
                    Text(location)
                        .font(RatsFont.body(10))
                        .foregroundStyle(RatsColor.muted)
                        .lineLimit(1)
                }
            }

            Text(isCouncil ? "Der Stadtrat tagt gerade" : "\(session.committee) tagt gerade")
                .font(RatsFont.title(22))
                .foregroundStyle(RatsColor.text)

            VStack(alignment: .leading, spacing: 5) {
                Text(liveMeta)
                    .font(RatsFont.body(13, weight: .medium))
                    .foregroundStyle(RatsColor.bodyText)
                Text("Welcher TOP gerade dran ist, veröffentlicht das Ratsinfo nicht. Ergebnisse folgen mit dem Protokoll.")
                    .font(RatsFont.body(10))
                    .foregroundStyle(RatsColor.secondary)
                    .lineSpacing(2)
            }
            .padding(11)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(RatsColor.stage)
            .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))

            ViewThatFits(in: .horizontal) {
                HStack(spacing: 9) { actions }
                VStack(alignment: .leading, spacing: 9) { actions }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(16)
        .background(RatsColor.card)
        .overlay(
            RoundedRectangle(cornerRadius: 18, style: .continuous)
                .stroke(RatsColor.danger.opacity(0.24))
        )
        .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
        .accessibilityElement(children: .contain)
    }

    @ViewBuilder
    private var actions: some View {
        Button(action: openAgenda) {
            Label("Tagesordnung", systemImage: "list.bullet.rectangle")
        }
        .buttonStyle(PrimaryButtonStyle())
        if isCouncil, let stream = URL(string: "https://oeins.de/tv-stream/") {
            Link(destination: stream) {
                Label("O1-Livestream", systemImage: "play.rectangle")
            }
            .buttonStyle(SecondaryButtonStyle())
        }
    }

    private var isCouncil: Bool {
        ["rat", "stadtrat"].contains(session.committee.trimmingCharacters(in: .whitespacesAndNewlines).lowercased())
    }

    private var topicItemCount: Int {
        Set((session.myTopicItems ?? []).compactMap { $0.object?["item_number"]?.string }).count
    }

    private var liveMeta: String {
        var parts = ["Begonnen um \(session.sessionTime ?? "–") Uhr"]
        if session.itemCount > 0 { parts.append("\(session.itemCount) \(session.itemCount == 1 ? "TOP" : "TOPs")") }
        if topicItemCount > 0 { parts.append("\(topicItemCount) zu deinen Themen") }
        return parts.joined(separator: " · ")
    }

    private var runningTime: String {
        guard let time = session.sessionTime, let start = sessionStart(time, on: now) else { return "kurzem" }
        let minutes = max(0, Int(now.timeIntervalSince(start) / 60))
        if minutes < 60 { return "\(minutes) \(minutes == 1 ? "Minute" : "Minuten")" }
        let halfHours = Double(Int((Double(minutes) / 30).rounded())) / 2
        if halfHours == 1 { return "1 Stunde" }
        return "\(halfHours.formatted(.number.precision(.fractionLength(0...1)))) Stunden"
    }
}

private struct LatestTopicHitsCard: View {
    let hits: [DashboardTopicHit]
    let open: (Int) -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            MonoKicker("Neu zu deinen Themen", trailing: "\(hits.count)")
            ForEach(Array(hits.enumerated()), id: \.element.id) { index, hit in
                Button { open(hit.id) } label: {
                    HStack(alignment: .top, spacing: 11) {
                        Image(systemName: "tag.fill")
                            .font(.system(size: 12, weight: .semibold))
                            .foregroundStyle(RatsColor.signal)
                            .frame(width: 30, height: 30)
                            .background(RatsColor.signal.opacity(0.08))
                            .clipShape(RoundedRectangle(cornerRadius: 9, style: .continuous))
                        VStack(alignment: .leading, spacing: 4) {
                            Text(hit.topicName)
                                .font(RatsFont.mono(9, weight: .semibold))
                                .foregroundStyle(RatsColor.signal)
                            Text(hit.title)
                                .font(RatsFont.body(14, weight: .semibold))
                                .foregroundStyle(RatsColor.text)
                                .multilineTextAlignment(.leading)
                                .lineLimit(3)
                            Text([shortCommittee(hit.committee), RatsDate.short(hit.sessionDate)].compactMap { $0 }.joined(separator: " · "))
                                .font(RatsFont.body(10))
                                .foregroundStyle(RatsColor.secondary)
                        }
                        Spacer(minLength: 2)
                        Image(systemName: "chevron.right")
                            .font(.caption)
                            .foregroundStyle(RatsColor.muted)
                            .padding(.top, 8)
                    }
                }
                .buttonStyle(.plain)
                if index < hits.count - 1 { Divider().overlay(RatsColor.separator) }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .ratsCard()
    }
}

private struct DashboardWeekNumberCard: View {
    let number: DashboardWeekNumber
    let open: (Int?) -> Void

    var body: some View {
        Button { open(number.decisionID) } label: {
            HStack(alignment: .center, spacing: 14) {
                VStack(alignment: .leading, spacing: 7) {
                    MonoKicker("Zahl der Woche")
                    Text(displayValue)
                        .font(RatsFont.title(34))
                        .foregroundStyle(RatsColor.signal)
                        .contentTransition(.numericText())
                    Text(description)
                        .font(RatsFont.body(12))
                        .foregroundStyle(RatsColor.secondary)
                        .lineLimit(3)
                        .multilineTextAlignment(.leading)
                }
                Spacer(minLength: 6)
                Image(systemName: "arrow.right")
                    .font(.system(size: 15, weight: .semibold))
                    .foregroundStyle(RatsColor.primary)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .ratsCard()
        }
        .buttonStyle(.plain)
    }

    private var displayValue: String {
        guard number.kind == "betrag", let amount = number.amountEUR else { return "\(number.count ?? 0)" }
        if amount >= 1_000_000 {
            return "\((amount / 1_000_000).formatted(.number.precision(.fractionLength(0...1)))) Mio. €"
        }
        if amount >= 1_000 { return "\((amount / 1_000).formatted(.number.precision(.fractionLength(0)))) Tsd. €" }
        return amount.formatted(.currency(code: "EUR").precision(.fractionLength(0)))
    }

    private var description: String {
        if number.kind == "betrag" { return "beschlossen für: \(number.title ?? "einen aktuellen Ratsbeschluss")" }
        let count = number.count ?? 0
        return "\(count == 1 ? "Beschluss" : "Beschlüsse") in den letzten \(number.windowDays) Tagen"
    }
}

private func localISODate(_ date: Date) -> String {
    let calendar = Calendar.current
    let components = calendar.dateComponents([.year, .month, .day], from: date)
    return String(format: "%04d-%02d-%02d", components.year ?? 0, components.month ?? 0, components.day ?? 0)
}

private func sessionStart(_ time: String, on date: Date) -> Date? {
    let parts = time.split(separator: ":").compactMap { Int($0) }
    guard let hour = parts.first else { return nil }
    var components = Calendar.current.dateComponents([.year, .month, .day], from: date)
    components.hour = hour
    components.minute = parts.count > 1 ? parts[1] : 0
    components.second = 0
    return Calendar.current.date(from: components)
}

private func shortCommittee(_ name: String) -> String {
    name
        .replacingOccurrences(of: "Ausschuss für ", with: "")
        .replacingOccurrences(of: "Rat der Stadt", with: "Rat")
}

private struct WeekPreviewCard: View {
    let preview: WeekPreview
    let open: (Int, String) -> Void

    @Environment(\.horizontalSizeClass) private var horizontalSizeClass
    @State private var expandedSessions: Set<Int> = []

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            header

            VStack(alignment: .leading, spacing: wideLayout ? 14 : 16) {
                ForEach(Array(preview.sessions.enumerated()), id: \.element.id) { index, session in
                    if wideLayout {
                        wideSession(session, at: index)
                    } else {
                        compactSession(session, at: index)
                    }
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .ratsCard()
    }

    private var wideLayout: Bool { horizontalSizeClass == .regular }

    private var header: some View {
        HStack(alignment: .center, spacing: 12) {
            VStack(alignment: .leading, spacing: 5) {
                Text("DEINE RATSWOCHE")
                    .font(RatsFont.mono(9, weight: .semibold))
                    .tracking(1.3)
                    .foregroundStyle(RatsColor.primary)
                Text("Die Woche im Rat")
                    .font(RatsFont.title(wideLayout ? 23 : 21))
                Text(headerMetadata)
                    .font(RatsFont.mono(10))
                    .foregroundStyle(RatsColor.secondary)

                if importantCount > 0 {
                    WeekCountBadge(text: importantCount == 1 ? "1 wichtiger Punkt" : "\(importantCount) wichtige Punkte")
                        .padding(.top, 3)
                }
            }
            Spacer(minLength: 4)
            ZStack {
                RoundedRectangle(cornerRadius: 16, style: .continuous)
                    .fill(RatsColor.primary.opacity(0.07))
                    .frame(width: wideLayout ? 76 : 68, height: wideLayout ? 70 : 62)
                Lotti3DView(scene: .reading, animated: false)
                    .frame(width: wideLayout ? 72 : 64, height: wideLayout ? 66 : 58)
            }
            .accessibilityHidden(true)
        }
        .padding(.bottom, 2)
        .overlay(alignment: .bottom) {
            Rectangle()
                .fill(RatsColor.separator)
                .frame(height: 1)
                .offset(y: 10)
        }
    }

    private var headerMetadata: String {
        let count = preview.sessions.count
        return "\(date(preview.from)) – \(date(preview.through))  ·  \(count) \(count == 1 ? "SITZUNG" : "SITZUNGEN")"
    }

    private var importantCount: Int {
        if let counts = preview.relevantItemsPerSession, !counts.isEmpty {
            return counts.values.reduce(0, +)
        }
        return preview.items.count
    }

    @ViewBuilder
    private func wideSession(_ session: CouncilSession, at index: Int) -> some View {
        HStack(alignment: .top, spacing: 13) {
            VStack(alignment: .leading, spacing: 7) {
                if startsNewDay(at: index) {
                    Text(dayLabel(session.sessionDate))
                        .font(RatsFont.mono(9, weight: .semibold))
                        .tracking(0.6)
                        .foregroundStyle(isToday(session.sessionDate) ? RatsColor.signal : RatsColor.muted)
                }
                Rectangle()
                    .fill(RatsColor.border)
                    .frame(width: 1)
                    .frame(maxHeight: .infinity)
                    .padding(.leading, 10)
            }
            .frame(width: 70, alignment: .leading)

            sessionContent(session, compact: false)
        }
    }

    private func compactSession(_ session: CouncilSession, at index: Int) -> some View {
        VStack(alignment: .leading, spacing: 11) {
            if startsNewDay(at: index) {
                HStack(spacing: 10) {
                    Text(daySectionLabel(session.sessionDate))
                        .font(RatsFont.mono(9, weight: .semibold))
                        .tracking(0.75)
                        .foregroundStyle(isToday(session.sessionDate) ? RatsColor.signal : RatsColor.muted)
                    Rectangle()
                        .fill(RatsColor.separator)
                        .frame(height: 1)
                }
            }

            sessionHeader(session, compact: true)

            let shown = shownItems(for: session, limit: 2)
            if !shown.isEmpty {
                HStack(alignment: .top, spacing: 10) {
                    RoundedRectangle(cornerRadius: 1.5)
                        .fill(RatsColor.border)
                        .frame(width: 2)
                    VStack(alignment: .leading, spacing: 7) {
                        agendaItems(shown, compact: true)
                        expansionControl(for: session, shown: shown.count)
                    }
                }
                .padding(.leading, 4)
            }
        }
        .padding(.bottom, 2)
        .overlay(alignment: .bottom) {
            if session.id != preview.sessions.last?.id {
                Rectangle().fill(RatsColor.separator).frame(height: 1).offset(y: 9)
            }
        }
    }

    private func sessionContent(_ session: CouncilSession, compact: Bool) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            sessionHeader(session, compact: compact)
            let shown = shownItems(for: session, limit: 3)
            if !shown.isEmpty {
                VStack(alignment: .leading, spacing: 7) {
                    agendaItems(shown, compact: compact)
                    expansionControl(for: session, shown: shown.count)
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private func sessionHeader(_ session: CouncilSession, compact: Bool) -> some View {
        Button {
            if let id = session.ksinr { open(id, "") }
        } label: {
            HStack(alignment: .top, spacing: 8) {
                VStack(alignment: .leading, spacing: 4) {
                    Text(shortCommittee(session.committee))
                        .font(RatsFont.body(compact ? 14 : 14.5, weight: .bold))
                        .foregroundStyle(RatsColor.text)
                        .multilineTextAlignment(.leading)
                    Text(sessionMetadata(session))
                        .font(RatsFont.body(11))
                        .foregroundStyle(RatsColor.secondary)
                }
                Spacer(minLength: 0)
                Text("Öffnen")
                    .font(RatsFont.body(10.5, weight: .semibold))
                    .foregroundStyle(RatsColor.muted)
                    .accessibilityHidden(true)
            }
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .accessibilityHint("Öffnet die Tagesordnung")
    }

    @ViewBuilder
    private func agendaItems(_ items: [WeekPreviewItem], compact: Bool) -> some View {
        ForEach(items) { item in
            Button { open(item.sessionID, item.itemNumber) } label: {
                WeekAgendaItemRow(item: item, compact: compact)
            }
            .buttonStyle(.plain)
        }
    }

    @ViewBuilder
    private func expansionControl(for session: CouncilSession, shown: Int) -> some View {
        let remaining = max(relevantCount(for: session) - shown, knownItems(for: session).count - shown)
        if let id = session.ksinr, remaining > 0, !expandedSessions.contains(id) {
            Button {
                withAnimation(.snappy(duration: 0.25)) { _ = expandedSessions.insert(id) }
            } label: {
                Text(remaining == 1 ? "+ 1 weiteres Highlight" : "+ \(remaining) weitere Highlights")
                    .font(RatsFont.body(11.5, weight: .semibold))
                    .foregroundStyle(RatsColor.primary)
                    .padding(.vertical, 2)
            }
            .buttonStyle(.plain)
        }
    }

    private func shownItems(for session: CouncilSession, limit: Int) -> [WeekPreviewItem] {
        let items = knownItems(for: session)
        guard let id = session.ksinr, expandedSessions.contains(id) else {
            return Array(items.prefix(limit))
        }
        return items
    }

    private func knownItems(for session: CouncilSession) -> [WeekPreviewItem] {
        guard let id = session.ksinr else { return [] }
        var result = preview.items.filter { $0.sessionID == id }
        var seen = Set(result.map(\.id))
        for item in preview.additionalItemsPerSession?[String(id)] ?? [] where seen.insert(item.id).inserted {
            result.append(item)
        }
        return result
    }

    private func relevantCount(for session: CouncilSession) -> Int {
        guard let id = session.ksinr else { return 0 }
        return preview.relevantItemsPerSession?[String(id)] ?? knownItems(for: session).count
    }

    private func sessionBadge(_ session: CouncilSession) -> String {
        let relevant = relevantCount(for: session)
        return relevant == 1 ? "1 wichtig" : "\(relevant) wichtig"
    }

    private func sessionMetadata(_ session: CouncilSession) -> String {
        var parts = [String]()
        if let time = session.sessionTime, !time.isEmpty { parts.append(String(time.prefix(5))) }
        let id = session.ksinr.map(String.init) ?? ""
        let topics = preview.contentItemsPerSession?[id] ?? session.itemCount
        if topics > 0 { parts.append("\(topics) \(topics == 1 ? "Thema" : "Themen")") }
        if relevantCount(for: session) > 0 { parts.append(sessionBadge(session)) }
        return parts.joined(separator: " · ")
    }

    private func startsNewDay(at index: Int) -> Bool {
        index == 0 || preview.sessions[index - 1].sessionDate != preview.sessions[index].sessionDate
    }

    private func isToday(_ iso: String) -> Bool {
        iso == Self.isoFormatter.string(from: .now)
    }

    private func dayLabel(_ iso: String) -> String {
        (RatsDate.weekday(iso) ?? iso).uppercased()
    }

    private func daySectionLabel(_ iso: String) -> String {
        guard let value = Self.isoFormatter.date(from: iso) else { return iso.uppercased() }
        return value.formatted(
            .dateTime
                .locale(Locale(identifier: "de_DE"))
                .weekday(.wide)
                .day()
                .month(.wide)
        ).uppercased()
    }

    private func shortCommittee(_ raw: String) -> String {
        var value = raw
        for prefix in ["Ausschuss für die ", "Ausschuss für den ", "Ausschuss für das ", "Ausschuss für ", "Betriebsausschuss Eigenbetrieb ", "Betriebsausschuss "] where value.hasPrefix(prefix) {
            value.removeFirst(prefix.count)
            break
        }
        if value == "Rat der Stadt Oldenburg" || value == "Rat der Stadt Oldenburg (Oldb)" { return "Rat" }
        return value.replacingOccurrences(of: " und ", with: " & ")
    }

    private func date(_ iso: String) -> String {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        guard let value = formatter.date(from: iso) else { return iso }
        return value.formatted(.dateTime.locale(Locale(identifier: "de_DE")).day().month(.abbreviated))
    }

    private static let isoFormatter: DateFormatter = {
        let formatter = DateFormatter()
        formatter.calendar = Calendar(identifier: .gregorian)
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.dateFormat = "yyyy-MM-dd"
        return formatter
    }()
}

private struct WeekCountBadge: View {
    let text: String

    var body: some View {
        Text(text)
            .font(RatsFont.body(9.5, weight: .bold))
            .foregroundStyle(RatsColor.primary)
            .padding(.horizontal, 7)
            .padding(.vertical, 3)
            .background(RatsColor.primary.opacity(0.08))
            .clipShape(Capsule())
            .fixedSize()
    }
}

private struct WeekAgendaItemRow: View {
    let item: WeekPreviewItem
    let compact: Bool

    var body: some View {
        HStack(alignment: .top, spacing: 9) {
            Circle()
                .fill(markerColor)
                .frame(width: item.featured == true ? 8 : 6, height: item.featured == true ? 8 : 6)
                .padding(.top, 5)
            VStack(alignment: .leading, spacing: 4) {
                if let kicker {
                    Text(kicker)
                        .font(RatsFont.mono(8.5, weight: .semibold))
                        .tracking(0.8)
                        .foregroundStyle(item.topicName == nil ? RatsColor.primary : RatsColor.signal)
                }
                Text(item.shortTitle ?? item.title)
                    .font(RatsFont.body(compact ? 13 : 13.5, weight: item.featured == true ? .bold : .medium))
                    .foregroundStyle(RatsColor.text)
                    .multilineTextAlignment(.leading)
                    .lineLimit(compact && item.featured != true ? 2 : 3)
                if item.featured == true, let reason = explanation {
                    Text(reason)
                        .font(RatsFont.body(compact ? 11.5 : 12))
                        .foregroundStyle(RatsColor.secondary)
                        .multilineTextAlignment(.leading)
                        .lineLimit(3)
                }
                if !compact, let applicant = item.applicant, !applicant.isEmpty {
                    Text("Antrag \(shortApplicant(applicant))")
                        .font(RatsFont.body(10.5, weight: .medium))
                        .foregroundStyle(RatsColor.muted)
                }
            }
            Spacer(minLength: 0)
        }
        .padding(.horizontal, item.featured == true ? 10 : 2)
        .padding(.vertical, item.featured == true ? 9 : 4)
        .background(item.featured == true ? RatsColor.primary.opacity(0.055) : Color.clear)
        .overlay {
            if item.featured == true {
                RoundedRectangle(cornerRadius: 11, style: .continuous)
                    .stroke(RatsColor.primary.opacity(0.14), lineWidth: 1)
            }
        }
        .clipShape(RoundedRectangle(cornerRadius: 11, style: .continuous))
        .contentShape(Rectangle())
        .accessibilityHint("Öffnet diesen Tagesordnungspunkt")
    }

    private var markerColor: Color {
        if item.topicName != nil { return RatsColor.signal }
        if item.featured == true { return RatsColor.primary }
        return RatsColor.muted.opacity(0.55)
    }

    private var kicker: String? {
        if let topic = item.topicName, !topic.isEmpty { return "WICHTIGES THEMA · \(topic.uppercased())" }
        if item.featured == true { return "HIGHLIGHT DER WOCHE" }
        return nil
    }

    private var explanation: String? {
        if let reason = item.impactReason, !reason.isEmpty { return reason }
        if let summary = item.summary, !summary.isEmpty { return summary }
        return nil
    }

    private func shortApplicant(_ raw: String) -> String {
        raw.replacingOccurrences(of: "-Fraktion", with: "")
            .replacingOccurrences(of: "Fraktion ", with: "")
    }
}

private struct TodayStatusCard: View {
    let today: TodayCard
    let openSessions: () -> Void

    var body: some View {
        Button(action: openSessions) {
            HStack(alignment: .top, spacing: 13) {
                Circle()
                    .fill(today.state == "heute" ? RatsColor.signal : RatsColor.muted.opacity(0.55))
                    .frame(width: 9, height: 9)
                    .padding(.top, 5)
                VStack(alignment: .leading, spacing: 6) {
                    MonoKicker(kicker)
                    Text(headline)
                        .font(RatsFont.body(16, weight: .semibold))
                        .multilineTextAlignment(.leading)
                    if let detail { Text(detail).font(RatsFont.body(13)).foregroundStyle(RatsColor.secondary) }
                }
                Spacer(minLength: 4)
                Image(systemName: "chevron.right").foregroundStyle(RatsColor.muted)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .ratsCard()
        }
        .buttonStyle(.plain)
    }

    private var kicker: String {
        switch today.state { case "heute": "Heute im Rat"; case "naechste": "Nächste Sitzung"; default: "Sitzungspause" }
    }

    private var headline: String {
        if today.state == "pause" { return today.label ?? "Der Rat macht Pause" }
        return today.committee ?? "Oldenburger Rat"
    }

    private var detail: String? {
        if today.state == "heute" {
            let count = (today.tops?.count ?? 0) + (today.rest ?? 0)
            return [today.sessionTime, count > 0 ? "\(count) öffentliche TOPs" : nil]
                .compactMap { $0 }.joined(separator: " · ")
        }
        if today.state == "naechste" {
            return [RatsDate.weekday(today.sessionDate), today.sessionTime].compactMap { $0 }.joined(separator: " · ")
        }
        return today.until.map { "Bis \($0)" }
    }
}

struct DecisionRow: View {
    let decision: DecisionSummary

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack(alignment: .top, spacing: 8) {
                if let outcome = decision.outcome {
                    DecisionOutcomeSignal(outcome: outcome)
                }
                if importanceScore >= 55, decision.kind != "subvote" {
                    Label("Wichtig", systemImage: "flame.fill")
                        .font(RatsFont.body(10.5, weight: .semibold))
                        .foregroundStyle(RatsColor.warning)
                        .padding(.horizontal, 7)
                        .padding(.vertical, 3)
                        .background(RatsColor.warning.opacity(importanceScore >= 70 ? 0.14 : 0.09))
                        .clipShape(RoundedRectangle(cornerRadius: 6, style: .continuous))
                }
                Spacer(minLength: 0)
                Image(systemName: "chevron.right")
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(RatsColor.muted.opacity(0.7))
            }

            if !metadata.isEmpty {
                Text(metadata)
                    .font(RatsFont.body(10.5, weight: .medium))
                    .foregroundStyle(RatsColor.muted)
                    .padding(.top, 5)
            }

            Text(decision.title)
                .font(RatsFont.body(15.5, weight: .semibold))
                .foregroundStyle(RatsColor.text)
                .multilineTextAlignment(.leading)
                .lineSpacing(1)
                .padding(.top, 9)

            if let summary = decision.summary, !summary.isEmpty {
                Text(summary)
                    .font(RatsFont.body(13))
                    .foregroundStyle(RatsColor.secondary)
                    .lineLimit(2)
                    .lineSpacing(2)
                    .multilineTextAlignment(.leading)
                    .padding(.top, 5)
            }

            if showsFooter {
                HStack(alignment: .bottom, spacing: 12) {
                    VStack(alignment: .leading, spacing: 5) {
                        if !voteLine.isEmpty {
                            Label(voteLine, systemImage: "checkmark.circle")
                                .font(RatsFont.body(11))
                                .foregroundStyle(RatsColor.secondary)
                        }
                        if !decision.factions.isEmpty {
                            Text("Antrag: \(decision.factions.prefix(2).joined(separator: ", "))")
                                .font(RatsFont.body(10.5, weight: .medium))
                                .foregroundStyle(RatsColor.secondary)
                                .lineLimit(2)
                        }
                    }
                    Spacer(minLength: 4)
                    if let amount = decision.amountEUR,
                       amount >= 100_000,
                       decision.kind != "subvote" {
                        VStack(alignment: .trailing, spacing: 2) {
                            Text(Self.amount(amount))
                                .font(RatsFont.body(14, weight: .bold))
                                .foregroundStyle(RatsColor.text)
                            Text("im Beschluss")
                                .font(RatsFont.body(9, weight: .medium))
                                .foregroundStyle(RatsColor.muted)
                        }
                    }
                }
                .padding(.top, 10)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .contentShape(Rectangle())
    }

    private var importanceScore: Int {
        decision.importance ?? max(decision.interest ?? 0, decision.impact ?? 0)
    }

    private var metadata: String {
        let committee = decision.committee.map(shortDecisionCommittee)
        let item = decision.itemNumber.map { "TOP \($0)" }
        return [committee, RatsDate.short(decision.sessionDate), item]
            .compactMap { $0 }
            .joined(separator: " · ")
    }

    private var showsFooter: Bool {
        !voteLine.isEmpty || !decision.factions.isEmpty
            || ((decision.amountEUR ?? 0) >= 100_000 && decision.kind != "subvote")
    }

    private var voteLine: String {
        var parts = [String]()
        if let vote = decision.vote, !vote.isEmpty { parts.append(vote) }
        if let no = decision.noVotes, no > 0 { parts.append("\(no) dagegen") }
        if let abstentions = decision.abstentions, abstentions > 0 { parts.append("\(abstentions) Enth.") }
        return parts.joined(separator: " · ")
    }

    private static func amount(_ value: Double) -> String {
        if value >= 1_000_000 {
            let number = String(format: "%.1f", value / 1_000_000)
                .replacingOccurrences(of: ".", with: ",")
            return "\(number) Mio. €"
        }
        return "\(Int(value / 1_000)) Tsd. €"
    }
}

private struct DecisionOutcomeSignal: View {
    let outcome: String

    var body: some View {
        HStack(spacing: 6) {
            Circle()
                .fill(color)
                .frame(width: 7, height: 7)
                .accessibilityHidden(true)
            Text(label)
                .font(RatsFont.body(11, weight: .semibold))
                .foregroundStyle(RatsColor.bodyText)
        }
    }

    private var label: String {
        switch outcome {
        case "angenommen": "Angenommen"
        case "abgelehnt": "Abgelehnt"
        case "vertagt": "Vertagt"
        case "zur_kenntnis": "Zur Kenntnis"
        case "kein_beschluss": "Kein Beschluss"
        default: outcome.replacingOccurrences(of: "_", with: " ").capitalized
        }
    }

    private var color: Color {
        switch outcome {
        case "angenommen": RatsColor.success
        case "abgelehnt": RatsColor.danger
        case "vertagt": RatsColor.warning
        case "zur_kenntnis": RatsColor.primary
        default: RatsColor.muted
        }
    }
}

private func shortDecisionCommittee(_ name: String) -> String {
    name
        .replacingOccurrences(of: "Ausschuss für ", with: "")
        .replacingOccurrences(of: "Rat der Stadt", with: "Rat")
}

struct ErrorCard: View {
    let message: String
    let retry: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Label("Das hat nicht geklappt", systemImage: "exclamationmark.triangle")
                .font(RatsFont.body(14, weight: .semibold))
                .foregroundStyle(RatsColor.warning)
            Text(message).font(RatsFont.body(13)).foregroundStyle(RatsColor.secondary)
            Button("Noch einmal versuchen", action: retry).buttonStyle(SecondaryButtonStyle())
        }
        .ratsCard()
    }
}
