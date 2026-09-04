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
    @State private var pause: CouncilPause?
    @State private var now = Date.now
    @State private var error: String?

    var body: some View {
        ScrollView {
            LazyVStack(alignment: .leading, spacing: RatsSpacing.xl) {
                HStack(alignment: .center, spacing: 14) {
                    headerLotti
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
                .ratsStaggered(0)

                AskCouncilEntry {
                    model.navigation.removeAll()
                    model.selectedTab = .questions
                }
                .ratsStaggered(1)

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
            recent = Array(RecentDecisionStore.load().prefix(5))
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
        if let pause, pause.active {
            CouncilPauseCard(pause: pause)
                .ratsStaggered(2)
        }
        if let liveSession {
            LiveCouncilCard(session: liveSession, now: now) {
                if let id = liveSession.ksinr { model.navigation.append(.sessions(ksinr: id, tops: [])) }
                else { openSessions() }
            }
            .ratsStaggered(2)
        }
        // Nur als Ersatz für die Wochenvorschau: Steht die Woche da, führt sie
        // den heutigen Termin schon in ihrer ersten Zeile — die Karte darüber
        // sagte dasselbe ein zweites Mal (Tims Befund 01.09.2026). Ohne
        // Vorschau (Ladefehler, Sitzungspause) bleibt sie die einzige Auskunft
        // und wird weiter gezeigt.
        if let today, liveSession == nil, preview?.found != true {
            TodayStatusCard(today: today, openSessions: openSessions)
                .ratsStaggered(3)
        }
        if let preview, preview.found {
            WeekPreviewCard(preview: preview) { sessionID, itemNumber in
                model.navigation.append(.sessions(ksinr: sessionID, tops: [itemNumber]))
            }
            .ratsStaggered(3)
        }
    }

    @ViewBuilder
    private var secondaryColumn: some View {
        if !latestTopicHits.isEmpty {
            LatestTopicHitsCard(hits: latestTopicHits) { model.navigation.append(.decision(id: $0)) }
                .ratsStaggered(4)
        }

        // Ein Widget verdient seinen Platz nur, wenn es heute etwas sagen
        // kann (Designdoc 3a): Eine Null ist keine Zahl der Woche.
        if let weekNumber, weekNumber.hasContent {
            DashboardWeekNumberCard(number: weekNumber) { decisionID in
                if let decisionID { model.navigation.append(.decision(id: decisionID)) }
                else {
                    model.navigation.removeAll()
                    model.selectedTab = .council
                    model.councilSection = .decisions
                }
            }
            .ratsStaggered(5)
        }

        if let week, week.found, let id = week.decisionID {
            Button { model.navigation.append(.decision(id: id)) } label: {
                RatsWidget("Diese Woche im Rat", accent: .marsh, glyph: .gavel, note: RatsDate.short(week.sessionDate)) {
                    VStack(alignment: .leading, spacing: 8) {
                        if let outcome = week.outcome { OutcomeBadge(outcome) }
                        Text(week.title ?? "Aktueller Beschluss")
                            .font(RatsFont.body(15, weight: .semibold))
                            .foregroundStyle(RatsColor.text)
                            .multilineTextAlignment(.leading)
                        if let reason = week.interestReason, !reason.isEmpty {
                            Text(reason)
                                .font(RatsFont.body(12.5))
                                .foregroundStyle(RatsColor.secondary)
                                .lineSpacing(2)
                                .multilineTextAlignment(.leading)
                        }
                    }
                }
            }
            .buttonStyle(RatsPlainButtonStyle())
            .ratsStaggered(5)
        }

        // Das eine dunkle Widget je Seite (Designdoc 3b3/4a): Das Fundstück
        // wird zum Farbtupfer und trägt den Humor, den der Rest nicht haben
        // darf.
        if let foundPiece, foundPiece.found, let id = foundPiece.decisionID {
            Button { model.navigation.append(.decision(id: id)) } label: {
                RatsWidget("Fundstück", accent: .buoy, glyph: .compass, deep: true) {
                    VStack(alignment: .leading, spacing: 8) {
                        if let kicker = foundPiece.kicker, !kicker.isEmpty {
                            Text(kicker.uppercased())
                                .font(RatsFont.mono(9, weight: .semibold))
                                .tracking(0.8)
                                .foregroundStyle(RatsColor.signal)
                        }
                        Text(foundPiece.title ?? "Aus dem Archiv")
                            .font(RatsFont.title(16.5, weight: .semibold))
                            .foregroundStyle(RatsColor.text)
                            .multilineTextAlignment(.leading)
                        if let story = foundPiece.story, !story.isEmpty {
                            Text(story)
                                .font(RatsFont.body(12.5))
                                .foregroundStyle(RatsColor.bodyText)
                                .lineSpacing(2)
                                .multilineTextAlignment(.leading)
                        }
                        if !foundPieceMeta.isEmpty {
                            Text(foundPieceMeta)
                                .font(RatsFont.body(11.5))
                                .foregroundStyle(RatsColor.secondary)
                        }
                    }
                }
            }
            .buttonStyle(RatsPlainButtonStyle())
            .ratsStaggered(5)
        }

        if !recent.isEmpty {
            RatsWidget("Zuletzt angesehen", accent: .ink, glyph: .history, note: "\(recent.count)") {
                VStack(alignment: .leading, spacing: 12) {
                    ForEach(recent) { decision in
                        Button { model.navigation.append(.decision(id: decision.id)) } label: {
                            DecisionRow(decision: decision)
                        }
                        .buttonStyle(RatsPlainButtonStyle())
                        if decision.id != recent.last?.id { Divider().overlay(RatsColor.separator) }
                    }
                }
            }
            .ratsStaggered(5)
        }

        // Kein Quiz zwischen Terminen, die heute gelten (Designdoc 3b5):
        // Es hat seinen Platz im Mehr-Hub.

        if let error {
            ErrorCard(message: error) { Task { await load() } }
        }
    }

    /// Lotti kommt in den Alltag (Designdoc „iOS Charakter", 1c): Sie winkt
    /// zur Begrüßung — und schläft, wenn der Rat Pause macht. Jede Regung ist
    /// an einen Zustand gebunden, nichts davon passiert zufällig.
    @ViewBuilder
    private var headerLotti: some View {
        if let pause, pause.active {
            LottiSpriteView(animation: .sleeping)
        } else {
            Lotti3DView(scene: .wave)
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

    private var foundPieceMeta: String {
        [foundPiece?.committee, RatsDate.short(foundPiece?.sessionDate)].compactMap { $0 }.joined(separator: " · ")
    }

    /// The one session running right now — at most one, because they wait for
    /// each other: council days run 16:00 general committee → 16:30
    /// administrative committee → 18:00 council in the same building, so
    /// whichever starts next ends the previous round. The server computes the
    /// end of every window and sends it as `live_until` (see `council/live.py`);
    /// the cap below only catches responses that predate that field. With
    /// several candidates the most recently started one wins.
    private var liveSession: CouncilSession? {
        upcomingSessions
            .compactMap { session -> (CouncilSession, Date)? in
                guard session.sessionDate.prefix(10) == localISODate(now),
                      let time = session.sessionTime,
                      let start = sessionStart(time, on: now),
                      now >= start
                else { return nil }
                if let until = session.liveUntil, let end = sessionStart(until, on: now), end > start {
                    guard now < end else { return nil }
                } else {
                    let cap = isCouncil(session.committee) ? liveCapHoursCouncil : liveCapHours
                    guard now.timeIntervalSince(start) <= Double(cap) * 60 * 60 else { return nil }
                }
                return (session, start)
            }
            .max { $0.1 < $1.1 }?.0
    }

    private func load() async {
        error = nil
        do {
            async let todayRequest: TodayCard = model.api.get("/api/council/heute")
            async let weekRequest: WeekDecision = model.api.get("/api/council/diese-woche")
            async let previewRequest: WeekPreview = model.api.get("/api/council/week-preview")
            async let foundRequest: FoundPiece = model.api.get("/api/council/daily-find")
            async let sessionsRequest: SessionPage? = try? await model.api.get(
                "/api/council/sessions",
                // Sechs statt drei: Ein Ratstag bringt drei Gremien nacheinander
                // (siehe `liveSession`) — mit einem knappen Limit fehlte die
                // laufende Sitzung in der Liste.
                query: [.init(name: "scope", value: "upcoming"), .init(name: "limit", value: "6")]
            )
            async let hitsRequest: DashboardTopicHits? = try? await model.api.get(
                "/api/topics/latest-hits", query: [.init(name: "limit", value: "2")]
            )
            async let numberRequest: DashboardWeekNumber? = try? await model.api.get("/api/council/zahl-der-woche")
            async let pauseRequest: CouncilPause? = try? await model.api.get("/api/council/session-break")
            let (newToday, newWeek, newPreview, newFound) = try await (
                todayRequest, weekRequest, previewRequest, foundRequest
            )
            today = newToday
            week = newWeek
            preview = newPreview
            foundPiece = newFound
            recent = Array(RecentDecisionStore.load().prefix(5))
            if let sessions = await sessionsRequest { upcomingSessions = sessions.sessions }
            if let hits = await hitsRequest { latestTopicHits = hits.hits }
            if let number = await numberRequest { weekNumber = number }
            if let newPause = await pauseRequest { pause = newPause }
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
            kind: "amount",
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

    var hasContent: Bool {
        if kind == "amount" { return (amountEUR ?? 0) > 0 }
        return (count ?? 0) > 0
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
            RatsLabel("Tagesordnung", .list)
        }
        .buttonStyle(PrimaryButtonStyle())
        if isCouncil, let stream = URL(string: "https://oeins.de/tv-stream/") {
            Link(destination: stream) {
                RatsLabel("O1-Livestream", .monitorPlay)
            }
            .buttonStyle(SecondaryButtonStyle())
        }
    }

    private var isCouncil: Bool { RatslotseFeatures.isCouncil(session.committee) }

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

/// Der Einstieg in „Frag den Rat" — als Composer, nicht als Knopf: Das
/// Eingabefeld mit dem Funken in Signal-Orange ist die Bauform, die von der
/// Fragen-Seite bekannt ist (Designsprache § 5, Composer). Der frühere
/// vollflächige Signal-Orange-Knopf verstieß gegen § 8: Signal-Orange ist
/// Akzent, nie Flächenfarbe.
private struct AskCouncilEntry: View {
    let action: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            MonoKicker("Frag den Rat")
            Button(action: action) {
                HStack(spacing: 10) {
                    RatsIcon(.sparkles, size: 17)
                        .foregroundStyle(RatsColor.signal)
                        .accessibilityHidden(true)
                    Text("Was möchtest du über den Rat wissen?")
                        .font(RatsFont.body(15))
                        .foregroundStyle(RatsColor.muted)
                        .lineLimit(1)
                        .minimumScaleFactor(0.85)
                    Spacer(minLength: 6)
                    RatsIcon(.arrowUp, size: 15)
                        .foregroundStyle(RatsColor.primaryText)
                        .frame(width: 38, height: 38)
                        .background(RatsColor.primary)
                        .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
                        .accessibilityHidden(true)
                }
                .padding(.leading, 14)
                .padding(.trailing, 7)
                .padding(.vertical, 7)
                .background(RatsColor.card)
                .overlay(RoundedRectangle(cornerRadius: 16, style: .continuous).stroke(RatsColor.border))
                .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
                .shadow(color: RatsColor.primary.opacity(0.10), radius: 14, y: 6)
                .contentShape(Rectangle())
            }
            .buttonStyle(RatsPlainButtonStyle())
            .accessibilityLabel("Frag den Rat")
            .accessibilityHint("Öffnet die Fragen-Seite")
        }
    }
}

private struct LatestTopicHitsCard: View {
    let hits: [DashboardTopicHit]
    let open: (Int) -> Void

    var body: some View {
        RatsWidget("Neu zu deinen Themen", accent: .buoy, glyph: .tag, note: "\(hits.count)") {
            VStack(alignment: .leading, spacing: 10) {
                ForEach(Array(hits.enumerated()), id: \.element.id) { index, hit in
                    Button { open(hit.id) } label: {
                        HStack(alignment: .top, spacing: 11) {
                            VStack(alignment: .leading, spacing: 4) {
                                Text(hit.topicName.uppercased())
                                    .font(RatsFont.mono(9, weight: .semibold))
                                    .tracking(0.7)
                                    .foregroundStyle(RatsColor.signalInk)
                                Text(hit.title)
                                    .font(RatsFont.body(14, weight: .semibold))
                                    .foregroundStyle(RatsColor.text)
                                    .multilineTextAlignment(.leading)
                                    .lineLimit(3)
                                Text([shortCommittee(hit.committee), RatsDate.short(hit.sessionDate)].compactMap { $0 }.joined(separator: " · "))
                                    .font(RatsFont.body(10.5))
                                    .foregroundStyle(RatsColor.secondary)
                            }
                            Spacer(minLength: 2)
                            RatsIcon(.chevronRight, size: 12)
                                .foregroundStyle(RatsColor.muted)
                                .padding(.top, 8)
                        }
                        .contentShape(Rectangle())
                    }
                    .buttonStyle(RatsPlainButtonStyle())
                    if index < hits.count - 1 { Divider().overlay(RatsColor.separator) }
                }
            }
        }
    }
}

private struct DashboardWeekNumberCard: View {
    let number: DashboardWeekNumber
    let open: (Int?) -> Void

    /// Watt-Grün, weil die Zahl aus einem Beschluss stammt. Sie zählt beim
    /// ersten Sichtkontakt hoch (600 ms, einmal je Erscheinen).
    var body: some View {
        Button { open(number.decisionID) } label: {
            RatsWidget(
                "Zahl der Woche",
                accent: .marsh,
                glyph: number.kind == "amount" ? .euro : .gavel,
                note: "letzte \(number.windowDays) Tage"
            ) {
                HStack(alignment: .center, spacing: 12) {
                    VStack(alignment: .leading, spacing: 4) {
                        RatsCountingNumber(rawValue, format: display)
                            .font(RatsFont.title(32))
                            .foregroundStyle(RatsColor.signal)
                        Text(description)
                            .font(RatsFont.body(12))
                            .foregroundStyle(RatsColor.secondary)
                            .lineLimit(3)
                            .multilineTextAlignment(.leading)
                    }
                    Spacer(minLength: 6)
                    RatsIcon(.arrowRight, size: 15)
                        .foregroundStyle(RatsColor.primary)
                        .accessibilityHidden(true)
                }
            }
        }
        .buttonStyle(RatsPlainButtonStyle())
    }

    private var rawValue: Double {
        if number.kind == "amount", let amount = number.amountEUR { return amount }
        return Double(number.count ?? 0)
    }

    private func display(_ value: Double) -> String {
        guard number.kind == "amount", number.amountEUR != nil else { return "\(Int(value.rounded()))" }
        if value >= 1_000_000 {
            return "\((value / 1_000_000).formatted(.number.precision(.fractionLength(0...1)))) Mio. €"
        }
        if value >= 1_000 { return "\((value / 1_000).formatted(.number.precision(.fractionLength(0)))) Tsd. €" }
        return value.formatted(.currency(code: "EUR").precision(.fractionLength(0)))
    }

    private var description: String {
        if number.kind == "amount" { return "beschlossen für: \(number.title ?? "einen aktuellen Ratsbeschluss")" }
        let count = number.count ?? 0
        return "\(count == 1 ? "Beschluss" : "Beschlüsse") in den letzten \(number.windowDays) Tagen"
    }
}

/// How long a session counts as running when no other follows it that day —
/// committees wrap up in about three hours, the council itself sits longer.
/// Mirrors `council.live`; normally the server sends the computed end.
let liveCapHours = 3
let liveCapHoursCouncil = 4

/// The council itself — not a district council, an advisory board or the
/// administrative committee. Matches `council.live._COUNCIL_NAMES`.
func isCouncil(_ committee: String) -> Bool {
    ["rat", "stadtrat", "rat der stadt", "rat der stadt oldenburg"]
        .contains(committee.trimmingCharacters(in: .whitespacesAndNewlines).lowercased())
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

    /// Die Ratswoche als Widget mit Wochenband (Designdoc 2a): sieben Spalten,
    /// heute gefüllt, ein Punkt nur, wo eine Sitzung liegt. Darunter wie
    /// bisher die Termine mit ihren wichtigen Punkten.
    var body: some View {
        RatsWidget("Deine Ratswoche", accent: .harbor, glyph: .calendar, note: rangeLabel) {
            VStack(alignment: .leading, spacing: 14) {
                WeekBand(from: preview.from, through: preview.through, sessions: preview.sessions)

                if importantCount > 0 {
                    WeekCountBadge(text: importantCount == 1 ? "1 wichtiger Punkt" : "\(importantCount) wichtige Punkte")
                }

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
        }
    }

    private var wideLayout: Bool { horizontalSizeClass == .regular }

    private var rangeLabel: String {
        "\(date(preview.from)) – \(date(preview.through))"
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
        .buttonStyle(RatsPlainButtonStyle())
        .accessibilityHint("Öffnet die Tagesordnung")
    }

    @ViewBuilder
    private func agendaItems(_ items: [WeekPreviewItem], compact: Bool) -> some View {
        ForEach(items) { item in
            Button { open(item.sessionID, item.itemNumber) } label: {
                WeekAgendaItemRow(item: item, compact: compact)
            }
            .buttonStyle(RatsPlainButtonStyle())
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
            .buttonStyle(RatsPlainButtonStyle())
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
        relativeDayName(iso) ?? (RatsDate.weekday(iso) ?? iso).uppercased()
    }

    private func daySectionLabel(_ iso: String) -> String {
        guard let value = Self.isoFormatter.date(from: iso) else { return iso.uppercased() }
        let german = Locale(identifier: "de_DE")
        let dayAndMonth = value.formatted(.dateTime.locale(german).day().month(.wide))
        let name = relativeDayName(iso)
            ?? value.formatted(.dateTime.locale(german).weekday(.wide)).uppercased()
        return "\(name), \(dayAndMonth)".uppercased()
    }

    /// „HEUTE" und „MORGEN" statt des Wochentags — auf dem Dashboard ist genau
    /// das die Auskunft, nach der man sucht; „Dienstag" muss man erst gegen
    /// den eigenen Kalender halten (Tims Wunsch 01.09.2026). Alle anderen Tage
    /// behalten ihren Wochentag.
    private func relativeDayName(_ iso: String) -> String? {
        guard let date = Self.isoFormatter.date(from: iso) else { return nil }
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = Self.isoFormatter.timeZone
        let offset = calendar.dateComponents(
            [.day],
            from: calendar.startOfDay(for: .now),
            to: calendar.startOfDay(for: date)
        ).day
        switch offset {
        case 0: return "HEUTE"
        case 1: return "MORGEN"
        default: return nil
        }
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

/// Das Wochenband (Designdoc 2a): sieben Spalten, heute gefüllt, ein Punkt
/// nur, wo eine Sitzung liegt — grau = gewesen, orange = zu deinen Themen,
/// blau = kommt noch.
private struct WeekBand: View {
    let from: String
    let through: String
    let sessions: [CouncilSession]

    private struct Day: Identifiable {
        let id: String
        let weekday: String
        let number: String
        let isToday: Bool
        let isPast: Bool
        let session: CouncilSession?
    }

    var body: some View {
        HStack(spacing: 2) {
            ForEach(days) { day in
                VStack(spacing: 5) {
                    Text(day.weekday)
                        .font(RatsFont.mono(9, weight: day.isToday ? .semibold : .medium))
                        .tracking(0.4)
                        .foregroundStyle(day.isToday ? RatsColor.signal : RatsColor.muted)
                    if day.isToday {
                        Text(day.number)
                            .font(RatsFont.body(13, weight: .bold))
                            .foregroundStyle(RatsColor.primaryText)
                            .frame(width: 24, height: 24)
                            .background(RatsColor.primary)
                            .clipShape(Circle())
                    } else {
                        Text(day.number)
                            .font(RatsFont.body(13, weight: .semibold))
                            .foregroundStyle(numberColor(day))
                            .frame(height: 24)
                    }
                    Circle()
                        .fill(dotColor(day))
                        .frame(width: 5, height: 5)
                }
                .frame(maxWidth: .infinity)
            }
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(accessibilityLabel)
    }

    /// Die Vorschau reicht von heute bis in sieben Tagen — das sind acht
    /// Spalten, nicht sieben. Ein Band, das den letzten Tag abschnitte,
    /// zeigte einen Termin unten, den oben kein Punkt trägt.
    private var days: [Day] {
        guard let start = Self.isoFormatter.date(from: from) else { return [] }
        let calendar = Calendar.current
        let today = calendar.startOfDay(for: .now)
        let german = Locale(identifier: "de_DE")
        let end = Self.isoFormatter.date(from: through) ?? start
        let span = calendar.dateComponents([.day], from: start, to: end).day ?? 6
        let count = min(max(span + 1, 7), 8)
        return (0..<count).compactMap { offset in
            guard let date = calendar.date(byAdding: .day, value: offset, to: start) else { return nil }
            let iso = Self.isoFormatter.string(from: date)
            let daySessions = sessions.filter { $0.sessionDate.prefix(10) == iso }
            let session = daySessions.first { !($0.myTopicItems ?? []).isEmpty } ?? daySessions.first
            return Day(
                id: iso,
                weekday: date.formatted(.dateTime.locale(german).weekday(.abbreviated))
                    .replacingOccurrences(of: ".", with: "")
                    .uppercased(),
                number: "\(calendar.component(.day, from: date))",
                isToday: calendar.isDate(date, inSameDayAs: today),
                isPast: date < today,
                session: session
            )
        }
    }

    private func numberColor(_ day: Day) -> Color {
        if day.session != nil { return RatsColor.secondary }
        return day.isPast ? RatsColor.muted : RatsColor.muted.opacity(0.7)
    }

    private func dotColor(_ day: Day) -> Color {
        guard let session = day.session else { return .clear }
        if !(session.myTopicItems ?? []).isEmpty { return RatsColor.signal }
        return day.isPast ? RatsColor.border : RatsColor.primary.opacity(0.55)
    }

    private var accessibilityLabel: String {
        let count = sessions.count
        return "Wochenband: \(count) \(count == 1 ? "Sitzung" : "Sitzungen") in dieser Woche"
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
            RatsWidget(kicker, accent: .harbor, glyph: today.state == "pause" ? .hourglass : .calendar) {
                HStack(alignment: .center, spacing: 12) {
                    VStack(alignment: .leading, spacing: 4) {
                        Text(headline)
                            .font(RatsFont.body(15, weight: .semibold))
                            .foregroundStyle(RatsColor.text)
                            .multilineTextAlignment(.leading)
                        if let detail {
                            Text(detail)
                                .font(RatsFont.body(12.5))
                                .foregroundStyle(RatsColor.secondary)
                                .multilineTextAlignment(.leading)
                        }
                    }
                    Spacer(minLength: 4)
                    RatsIcon(.chevronRight, size: 14)
                        .foregroundStyle(RatsColor.muted)
                        .accessibilityHidden(true)
                }
            }
        }
        .buttonStyle(RatsPlainButtonStyle())
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
            let count = (today.tops?.count ?? 0) + (today.remaining ?? 0)
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
                    RatsLabel("Wichtig", .flame)
                        .font(RatsFont.body(10.5, weight: .semibold))
                        .foregroundStyle(RatsColor.warning)
                        .padding(.horizontal, 7)
                        .padding(.vertical, 3)
                        .background(RatsColor.warning.opacity(importanceScore >= 70 ? 0.14 : 0.09))
                        .clipShape(RoundedRectangle(cornerRadius: 6, style: .continuous))
                }
                Spacer(minLength: 0)
                RatsIcon(.chevronRight, size: 12)
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
                            RatsLabel(voteLine, .circleCheck)
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
            RatsIcon(symbol, size: 10.5)
                .foregroundStyle(color)
                .accessibilityHidden(true)
            Text(label)
                .font(RatsFont.body(11, weight: .semibold))
                .foregroundStyle(RatsColor.bodyText)
        }
        .padding(.horizontal, 8)
        .padding(.vertical, 4)
        .background(color.opacity(0.10))
        .clipShape(RoundedRectangle(cornerRadius: 7, style: .continuous))
    }

    private var label: String {
        switch outcome {
        case "accepted": "Angenommen"
        case "rejected": "Abgelehnt"
        case "postponed": "Vertagt"
        case "noted": "Zur Kenntnis"
        case "no_decision": "Kein Beschluss"
        default: outcome.replacingOccurrences(of: "_", with: " ").capitalized
        }
    }

    private var color: Color {
        switch outcome {
        case "accepted": RatsColor.success
        case "rejected": RatsColor.danger
        case "postponed": RatsColor.warning
        case "noted": RatsColor.primary
        default: RatsColor.muted
        }
    }

    private var symbol: RatsGlyph {
        switch outcome {
        case "accepted": .check
        case "rejected": .x
        case "postponed": .history
        case "noted": .eye
        case "no_decision": .minus
        default: .circle
        }
    }
}

private func shortDecisionCommittee(_ name: String) -> String {
    name
        .replacingOccurrences(of: "Ausschuss für ", with: "")
        .replacingOccurrences(of: "Rat der Stadt", with: "Rat")
}

private struct CouncilPause: Decodable, Sendable {
    let active: Bool
    let label: String?
    let until: String?
    let nextSessionDate: String?
    let note: String

    enum CodingKeys: String, CodingKey {
        case active, label, until, note
        case nextSessionDate = "next_session_date"
    }
}

private struct CouncilPauseCard: View {
    let pause: CouncilPause
    @State private var isExpanded = false

    var body: some View {
        VStack(spacing: 0) {
            Button { withAnimation(.snappy) { isExpanded.toggle() } } label: {
                HStack(spacing: 12) {
                    Lotti3DView(scene: .reading, animated: false)
                        .frame(width: 54, height: 48)
                        .accessibilityHidden(true)
                    VStack(alignment: .leading, spacing: 3) {
                        MonoKicker("Sitzungspause")
                        Text(pause.label ?? "Der Rat macht gerade Pause")
                            .font(RatsFont.body(14, weight: .semibold))
                            .foregroundStyle(RatsColor.text)
                        if let returnLabel {
                            Text(returnLabel)
                                .font(RatsFont.body(11.5))
                                .foregroundStyle(RatsColor.secondary)
                        }
                    }
                    Spacer(minLength: 4)
                    RatsIcon(.chevronDown, size: 12)
                        .foregroundStyle(RatsColor.secondary)
                        .rotationEffect(.degrees(isExpanded ? 180 : 0))
                }
                .contentShape(Rectangle())
            }
            .buttonStyle(RatsPlainButtonStyle())

            if isExpanded, !pause.note.isEmpty {
                Divider().overlay(RatsColor.separator).padding(.vertical, 12)
                Text(pause.note)
                    .font(RatsFont.body(12.5))
                    .foregroundStyle(RatsColor.secondary)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .transition(.opacity.combined(with: .move(edge: .top)))
            }
        }
        .padding(14)
        .background {
            RoundedRectangle(cornerRadius: RatsRadius.card, style: .continuous)
                .fill(RatsColor.primary.opacity(0.075))
                .overlay(CouncilPauseWaves().stroke(RatsColor.primary.opacity(0.08), lineWidth: 1))
        }
        .overlay(RoundedRectangle(cornerRadius: RatsRadius.card).stroke(RatsColor.primary.opacity(0.18)))
        .clipShape(RoundedRectangle(cornerRadius: RatsRadius.card, style: .continuous))
        .accessibilityElement(children: .contain)
    }

    private var returnLabel: String? {
        if let next = pause.nextSessionDate {
            return "Nächste veröffentlichte Sitzung: \(RatsDate.short(next) ?? next)"
        }
        if let until = pause.until { return "Pause bis \(RatsDate.short(until) ?? until)" }
        return nil
    }
}

private struct CouncilPauseWaves: Shape {
    func path(in rect: CGRect) -> Path {
        var path = Path()
        for y in stride(from: CGFloat(18), through: rect.height, by: 28) {
            path.move(to: CGPoint(x: 0, y: y))
            for x in stride(from: CGFloat(0), through: rect.width, by: 32) {
                path.addCurve(
                    to: CGPoint(x: min(x + 32, rect.width), y: y),
                    control1: CGPoint(x: x + 8, y: y - 4),
                    control2: CGPoint(x: x + 24, y: y + 4)
                )
            }
        }
        return path
    }
}

/// „Fehler heißt Hinweis" (Designdoc „iOS Charakter", 5c): Lotti hebt die
/// Hand statt eines roten Dreiecks, und ein Ausweg ist immer dabei — der
/// Retry, oder für den Anmelde-Fall der Knopf, der bisher fehlte.
struct ErrorCard: View {
    let message: String
    var title = "Das hat nicht geklappt"
    var actionTitle = "Noch einmal versuchen"
    let retry: () -> Void

    var body: some View {
        HStack(alignment: .center, spacing: 14) {
            RatsStatePortrait(animation: .raiseHand, tint: RatsColor.signal)
            VStack(alignment: .leading, spacing: 3) {
                RatsStateKicker(text: "Hinweis", color: RatsColor.signalInk)
                Text(title)
                    .font(RatsFont.body(14, weight: .bold))
                    .foregroundStyle(RatsColor.text)
                Text(message)
                    .font(RatsFont.body(12))
                    .foregroundStyle(RatsColor.secondary)
                    .lineSpacing(2)
                Button(actionTitle, action: retry)
                    .buttonStyle(SecondaryButtonStyle())
                    .padding(.top, 6)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .ratsCard()
    }
}
