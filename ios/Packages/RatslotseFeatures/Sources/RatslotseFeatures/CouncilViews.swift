import EventKit
import EventKitUI
import RatslotseAPI
import RatslotseDesign
import SwiftUI

private enum CouncilSection: String, CaseIterable, Identifiable {
    case decisions = "Beschlüsse"
    case sessions = "Sitzungen"
    var id: String { rawValue }
}

struct CouncilBrowserView: View {
    let model: AppModel
    @State private var section: CouncilSection = .decisions
    @State private var query = ""
    @State private var outcome = ""
    @State private var decisions: [DecisionSummary] = []
    @State private var sessions: [CouncilSession] = []
    @State private var total = 0
    @State private var isLoading = false
    @State private var error: String?

    var body: some View {
        VStack(spacing: 0) {
            Picker("Ansicht", selection: $section) {
                ForEach(CouncilSection.allCases) { Text($0.rawValue).tag($0) }
            }
            .pickerStyle(.segmented)
            .padding(.horizontal, 18)
            .padding(.vertical, 12)

            if section == .decisions {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 7) {
                        FilterChip(label: "Alle", selected: outcome.isEmpty) { outcome = "" }
                        FilterChip(label: "Angenommen", selected: outcome == "angenommen") { outcome = "angenommen" }
                        FilterChip(label: "Abgelehnt", selected: outcome == "abgelehnt") { outcome = "abgelehnt" }
                        FilterChip(label: "Vertagt", selected: outcome == "vertagt") { outcome = "vertagt" }
                    }
                    .padding(.horizontal, 18)
                    .padding(.bottom, 9)
                }
            }

            ScrollView {
                LazyVStack(alignment: .leading, spacing: 12) {
                    HStack {
                        MonoKicker(section.rawValue, trailing: total > 0 ? "\(total) gefunden" : nil)
                        if isLoading { ProgressView().controlSize(.small) }
                    }
                    if let error { ErrorCard(message: error) { Task { await load() } } }
                    if section == .decisions {
                        ForEach(decisions) { decision in
                            Button { model.navigation.append(.decision(id: decision.id)) } label: {
                                DecisionRow(decision: decision).ratsCard()
                            }
                            .buttonStyle(.plain)
                        }
                    } else {
                        ForEach(sessions) { session in
                            Button {
                                if let id = session.ksinr { model.navigation.append(.sessions(ksinr: id, tops: [])) }
                            } label: {
                                SessionRow(session: session).ratsCard()
                            }
                            .buttonStyle(.plain)
                            .disabled(session.ksinr == nil)
                        }
                    }
                }
                .frame(maxWidth: 860, alignment: .leading)
                .padding(18)
            }
            .refreshable { await load() }
        }
        .background(RatsColor.page)
        .navigationTitle("Im Rat stöbern")
        .toolbarTitleDisplayMode(.inline)
        .searchable(text: $query, prompt: section == .decisions ? "Beschlüsse durchsuchen" : "Sitzungen durchsuchen")
        .onSubmit(of: .search) { Task { await load() } }
        .onChange(of: section) { _, _ in Task { await load() } }
        .onChange(of: outcome) { _, _ in Task { await load() } }
        .task { if decisions.isEmpty && sessions.isEmpty { await load() } }
    }

    private func load() async {
        isLoading = true
        error = nil
        defer { isLoading = false }
        do {
            if section == .decisions {
                let page: DecisionPage = try await model.api.get(
                    "/api/council/decisions",
                    query: [
                        .init(name: "q", value: query),
                        .init(name: "outcome", value: outcome),
                        .init(name: "limit", value: "100"),
                    ]
                )
                decisions = page.decisions
                total = page.total
            } else {
                let page: SessionPage = try await model.api.get(
                    "/api/council/sessions",
                    query: [.init(name: "q", value: query), .init(name: "limit", value: "100")]
                )
                sessions = page.sessions
                total = page.total
            }
        } catch { self.error = error.localizedDescription }
    }
}

private struct FilterChip: View {
    let label: String
    let selected: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            Text(label)
                .font(RatsFont.body(12, weight: .semibold))
                .foregroundStyle(selected ? RatsColor.primaryText : RatsColor.secondary)
                .padding(.horizontal, 11)
                .padding(.vertical, 6)
                .background(selected ? RatsColor.primary : RatsColor.card)
                .overlay(Capsule().stroke(selected ? RatsColor.primary : RatsColor.border))
                .clipShape(Capsule())
        }
        .buttonStyle(.plain)
    }
}

private struct SessionRow: View {
    let session: CouncilSession

    var body: some View {
        VStack(alignment: .leading, spacing: 7) {
            MonoKicker(session.sessionDate, trailing: session.sessionTime)
            Text(session.committee)
                .font(RatsFont.body(16, weight: .semibold))
            if let location = session.location, !location.isEmpty {
                Label(location, systemImage: "mappin.and.ellipse")
                    .font(RatsFont.body(12))
                    .foregroundStyle(RatsColor.secondary)
            }
            if let matches = session.myTopicItems, !matches.isEmpty {
                Pill("\(matches.count) zu deinen Themen", symbol: "bell")
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

struct DecisionDetailView: View {
    let model: AppModel
    let decisionID: Int
    @State private var detail: DecisionDetail?
    @State private var error: String?
    @State private var bookmarked = false

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                if let detail {
                    let decision = detail.decision
                    VStack(alignment: .leading, spacing: 10) {
                        MonoKicker(
                            [decision.committee, decision.sessionDate].compactMap { $0 }.joined(separator: " · ")
                        )
                        Text(decision.title).font(RatsFont.title(28))
                        if let outcome = decision.outcome { OutcomeBadge(outcome) }
                    }

                    if let summary = decision.summary, !summary.isEmpty {
                        VStack(alignment: .leading, spacing: 9) {
                            MonoKicker("Kurz erklärt")
                            Text(summary).font(RatsFont.body(16)).foregroundStyle(RatsColor.bodyText).lineSpacing(5)
                        }
                        .ratsCard()
                    }

                    if !detail.presentParties.isEmpty {
                        VStack(alignment: .leading, spacing: 10) {
                            MonoKicker("Anwesende Fraktionen", trailing: "\(detail.presentParties.count)")
                            FlexibleChips(items: detail.presentParties)
                        }
                        .ratsCard()
                    }

                    if !detail.similar.isEmpty {
                        VStack(alignment: .leading, spacing: 13) {
                            MonoKicker("Im Zusammenhang")
                            ForEach(detail.similar) { similar in
                                Button { model.navigation.append(.decision(id: similar.id)) } label: {
                                    DecisionRow(decision: similar)
                                }
                                .buttonStyle(.plain)
                            }
                        }
                        .ratsCard()
                    }

                    HStack(spacing: 12) {
                        Button {
                            toggleBookmark()
                        } label: {
                            Label(bookmarked ? "Gemerkt" : "Merken", systemImage: bookmarked ? "bookmark.fill" : "bookmark")
                        }
                        .buttonStyle(SecondaryButtonStyle())
                        if let link = model.router.universalLink(for: .decision(id: decisionID)) {
                            ShareLink(item: link) { Label("Teilen", systemImage: "square.and.arrow.up") }
                                .buttonStyle(SecondaryButtonStyle())
                        }
                    }

                    if let raw = detail.ratsinfoURL, let url = URL(string: raw) {
                        Link(destination: url) {
                            Label("Amtliche Quelle im Ratsinfosystem", systemImage: "arrow.up.right.square")
                                .frame(maxWidth: .infinity, alignment: .leading)
                        }
                        .font(RatsFont.body(13, weight: .medium))
                    }
                } else if let error {
                    ErrorCard(message: error) { Task { await load() } }
                } else {
                    ProgressView("Beschluss laden …").frame(maxWidth: .infinity, minHeight: 260)
                }
            }
            .frame(maxWidth: 760, alignment: .leading)
            .padding(18)
        }
        .background(RatsColor.page)
        .navigationTitle("Beschluss")
        .navigationBarTitleDisplayMode(.inline)
        .task { await load() }
    }

    private func load() async {
        do {
            detail = try await model.api.get("/api/council/decision/\(decisionID)")
        } catch { self.error = error.localizedDescription }
    }

    private func toggleBookmark() {
        guard model.user != nil else { model.authPresentation = .login; return }
        struct Body: Codable, Sendable { let kind: String; let decision_id: Int }
        Task {
            do {
                let _: JSONValue = try await model.api.send(
                    "/api/bookmarks", body: Body(kind: "decision", decision_id: decisionID)
                )
                bookmarked = true
            } catch { self.error = error.localizedDescription }
        }
    }
}

struct SessionRouteView: View {
    let model: AppModel
    let ksinr: Int?
    let tops: [String]

    var body: some View {
        if let ksinr { SessionDetailView(model: model, ksinr: ksinr, highlightedTops: Set(tops)) }
        else { SessionListView(model: model) }
    }
}

private struct SessionListView: View {
    let model: AppModel
    @State private var sessions: [CouncilSession] = []
    @State private var error: String?

    var body: some View {
        List(sessions) { session in
            if let ksinr = session.ksinr {
                NavigationLink(value: AppRoute.sessions(ksinr: ksinr, tops: [])) { SessionRow(session: session) }
            } else { SessionRow(session: session) }
        }
        .navigationTitle("Sitzungen")
        .task {
            do {
                let page: SessionPage = try await model.api.get(
                    "/api/council/sessions", query: [.init(name: "limit", value: "100")]
                )
                sessions = page.sessions
            } catch { self.error = error.localizedDescription }
        }
        .overlay { if let error { ErrorCard(message: error) {}.padding() } }
    }
}

private struct SessionDetailView: View {
    let model: AppModel
    let ksinr: Int
    let highlightedTops: Set<String>
    @State private var detail: SessionDetail?
    @State private var error: String?
    @State private var calendarDraft: CalendarDraft?

    var body: some View {
        ScrollViewReader { proxy in
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    if let detail {
                        VStack(alignment: .leading, spacing: 9) {
                            MonoKicker([detail.sessionDate, detail.sessionTime].compactMap { $0 }.joined(separator: " · "))
                            Text(detail.committee).font(RatsFont.title(28))
                            if let location = detail.location { Label(location, systemImage: "mappin.and.ellipse") }
                            Button { prepareCalendar(detail) } label: {
                                Label("In Kalender", systemImage: "calendar.badge.plus")
                            }
                            .buttonStyle(SecondaryButtonStyle())
                        }
                        VStack(alignment: .leading, spacing: 12) {
                            MonoKicker("Tagesordnung", trailing: "\(detail.agendaItems.filter { $0.isPublic != 0 }.count) öffentlich")
                            ForEach(detail.agendaItems.filter { $0.isPublic != 0 }) { item in
                                VStack(alignment: .leading, spacing: 5) {
                                    Text(item.itemNumber).font(RatsFont.mono(10)).foregroundStyle(RatsColor.primary)
                                    Text(item.title).font(RatsFont.body(15, weight: .semibold))
                                    if let summary = item.summary { Text(summary).font(RatsFont.body(13)).foregroundStyle(RatsColor.secondary) }
                                }
                                .padding(12)
                                .background(highlightedTops.contains(item.itemNumber) ? RatsColor.primary.opacity(0.09) : Color.clear)
                                .clipShape(RoundedRectangle(cornerRadius: 10))
                                .id(item.itemNumber)
                            }
                        }
                        .ratsCard()
                        if let raw = detail.url, let url = URL(string: raw) {
                            Link("Sitzung im Ratsinfosystem öffnen", destination: url)
                        }
                    } else if let error {
                        ErrorCard(message: error) { Task { await load() } }
                    } else {
                        ProgressView("Sitzung laden …").frame(maxWidth: .infinity, minHeight: 260)
                    }
                }
                .frame(maxWidth: 760, alignment: .leading)
                .padding(18)
            }
            .onChange(of: detail != nil) { _, loaded in
                guard loaded, let first = highlightedTops.first else { return }
                withAnimation { proxy.scrollTo(first, anchor: .center) }
            }
        }
        .background(RatsColor.page)
        .navigationTitle("Sitzung")
        .navigationBarTitleDisplayMode(.inline)
        .task { await load() }
        .sheet(item: $calendarDraft) { draft in CalendarEditSheet(draft: draft, isPresented: Binding(
            get: { calendarDraft != nil }, set: { if !$0 { calendarDraft = nil } }
        )) }
    }

    private func load() async {
        do { detail = try await model.api.get("/api/council/session/\(ksinr)") }
        catch { self.error = error.localizedDescription }
    }

    private func prepareCalendar(_ detail: SessionDetail) {
        Task {
            let store = EKEventStore()
            guard (try? await store.requestFullAccessToEvents()) == true else {
                error = "Kalenderzugriff wurde nicht erlaubt. Du kannst ihn in den Einstellungen freigeben."
                return
            }
            let parser = DateFormatter()
            parser.locale = Locale(identifier: "de_DE")
            parser.dateFormat = "yyyy-MM-dd HH:mm"
            let start = parser.date(from: "\(detail.sessionDate) \(detail.sessionTime ?? "17:00")") ?? .now
            calendarDraft = CalendarDraft(
                title: detail.committee,
                start: start,
                end: start.addingTimeInterval(3 * 3600),
                location: detail.location,
                notes: detail.url
            )
        }
    }
}

private struct FlexibleChips: View {
    let items: [String]
    var body: some View {
        ViewThatFits(in: .horizontal) {
            HStack { ForEach(items, id: \.self) { Pill($0) } }
            VStack(alignment: .leading) { ForEach(items, id: \.self) { Pill($0) } }
        }
    }
}

private struct CalendarDraft: Identifiable {
    let id = UUID()
    let title: String
    let start: Date
    let end: Date
    let location: String?
    let notes: String?
}

private struct CalendarEditSheet: UIViewControllerRepresentable {
    let draft: CalendarDraft
    @Binding var isPresented: Bool

    func makeCoordinator() -> Coordinator { Coordinator(isPresented: $isPresented) }

    func makeUIViewController(context: Context) -> EKEventEditViewController {
        let store = EKEventStore()
        let event = EKEvent(eventStore: store)
        event.title = draft.title
        event.startDate = draft.start
        event.endDate = draft.end
        event.location = draft.location
        event.notes = draft.notes
        event.calendar = store.defaultCalendarForNewEvents
        let controller = EKEventEditViewController()
        controller.eventStore = store
        controller.event = event
        controller.editViewDelegate = context.coordinator
        return controller
    }

    func updateUIViewController(_ uiViewController: EKEventEditViewController, context: Context) {}

    final class Coordinator: NSObject, EKEventEditViewDelegate {
        @Binding var isPresented: Bool
        init(isPresented: Binding<Bool>) { _isPresented = isPresented }
        func eventEditViewController(_ controller: EKEventEditViewController, didCompleteWith action: EKEventEditViewAction) {
            isPresented = false
        }
    }
}
