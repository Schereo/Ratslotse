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
    @State private var error: String?

    var body: some View {
        ScrollView {
            LazyVStack(alignment: .leading, spacing: RatsSpacing.xl) {
                VStack(alignment: .leading, spacing: 7) {
                    MonoKicker(dayLabel)
                    Text(greeting)
                        .font(RatsFont.title(31))
                    Text("Das Wichtigste aus Oldenburgs Rat – kurz eingeordnet und mit Quellen.")
                        .font(RatsFont.body())
                        .foregroundStyle(RatsColor.secondary)
                }

                if let today { TodayStatusCard(today: today, openSessions: openSessions) }
                if let preview, preview.found {
                    WeekPreviewCard(preview: preview) { sessionID, itemNumber in
                        model.navigation.append(.sessions(ksinr: sessionID, tops: [itemNumber]))
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
            .frame(maxWidth: 760, alignment: .leading)
            .padding(.horizontal, 18)
            .padding(.vertical, 24)
        }
        .background(RatsColor.page)
        .navigationTitle("Heute")
        .toolbarTitleDisplayMode(.inline)
        .refreshable { await load() }
        .task { if today == nil { await load() } }
    }

    private var greeting: String {
        let hour = Calendar.current.component(.hour, from: .now)
        let prefix = hour < 11 ? "Moin" : hour < 18 ? "Guten Tag" : "Guten Abend"
        guard let name = model.user?.displayName?.split(separator: " ").first else { return prefix }
        return "\(prefix), \(name)"
    }

    private var dayLabel: String {
        Date.now.formatted(.dateTime.locale(Locale(identifier: "de_DE")).weekday(.wide).day().month(.wide))
    }

    private func openSessions() { model.navigation.append(.sessions(ksinr: nil, tops: [])) }

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
            let (newToday, newWeek, newPreview, newFound, page) = try await (
                todayRequest, weekRequest, previewRequest, foundRequest, decisionsRequest
            )
            today = newToday
            week = newWeek
            preview = newPreview
            foundPiece = newFound
            recent = page.decisions
        } catch {
            self.error = error.localizedDescription
        }
    }
}

private struct WeekPreviewCard: View {
    let preview: WeekPreview
    let open: (Int, String) -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            MonoKicker(
                "Die Woche im Rat",
                trailing: preview.personalMatches.map { $0 == 1 ? "1 für dich" : "\($0) für dich" }
            )
            Text("\(date(preview.from)) – \(date(preview.through))")
                .font(RatsFont.title(20))
            if preview.items.isEmpty {
                ForEach(preview.sessions.prefix(4)) { session in
                    Button {
                        if let id = session.ksinr { open(id, "") }
                    } label: {
                        HStack {
                            VStack(alignment: .leading, spacing: 3) {
                                Text(session.committee).font(RatsFont.body(14, weight: .semibold))
                                Text(session.sessionDate).font(RatsFont.body(12)).foregroundStyle(RatsColor.secondary)
                            }
                            Spacer()
                            Image(systemName: "chevron.right").foregroundStyle(RatsColor.muted)
                        }
                    }
                    .buttonStyle(.plain)
                }
            } else {
                ForEach(preview.items.prefix(5)) { item in
                    Button { open(item.sessionID, item.itemNumber) } label: {
                        HStack(alignment: .top, spacing: 10) {
                            Circle()
                                .fill(item.topicName == nil ? RatsColor.muted.opacity(0.5) : RatsColor.signal)
                                .frame(width: 8, height: 8)
                                .padding(.top, 5)
                            VStack(alignment: .leading, spacing: 4) {
                                Text(item.shortTitle ?? item.title)
                                    .font(RatsFont.body(14, weight: .semibold))
                                    .multilineTextAlignment(.leading)
                                Text("\(item.sessionDate) · \(item.committee)")
                                    .font(RatsFont.body(11))
                                    .foregroundStyle(RatsColor.secondary)
                                if let reason = item.impactReason, item.featured == true {
                                    Text(reason).font(RatsFont.body(12)).foregroundStyle(RatsColor.secondary)
                                }
                            }
                            Spacer(minLength: 0)
                        }
                    }
                    .buttonStyle(.plain)
                    if item.id != preview.items.prefix(5).last?.id { Divider().overlay(RatsColor.separator) }
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .ratsCard()
    }

    private func date(_ iso: String) -> String {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        guard let value = formatter.date(from: iso) else { return iso }
        return value.formatted(.dateTime.locale(Locale(identifier: "de_DE")).day().month(.abbreviated))
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
            return [today.sessionDate, today.sessionTime].compactMap { $0 }.joined(separator: " · ")
        }
        return today.until.map { "Bis \($0)" }
    }
}

struct DecisionRow: View {
    let decision: DecisionSummary

    var body: some View {
        VStack(alignment: .leading, spacing: 7) {
            if let outcome = decision.outcome { OutcomeBadge(outcome) }
            Text(decision.title)
                .font(RatsFont.body(15, weight: .semibold))
                .foregroundStyle(RatsColor.text)
                .multilineTextAlignment(.leading)
            Text([decision.committee, decision.sessionDate].compactMap { $0 }.joined(separator: " · "))
                .font(RatsFont.mono(10))
                .foregroundStyle(RatsColor.muted)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .contentShape(Rectangle())
    }
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
