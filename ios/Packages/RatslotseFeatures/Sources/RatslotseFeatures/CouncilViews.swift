import EventKit
import EventKitUI
import QuickLook
import RatslotseAPI
import RatslotseDesign
import SwiftUI

struct CouncilBrowserView: View {
    @Bindable var model: AppModel
    @Environment(\.horizontalSizeClass) private var horizontalSizeClass
    @State private var query = ""
    @State private var outcome = ""
    @State private var committee = ""
    @State private var policyField = ""
    @State private var party = ""
    @State private var district = ""
    @State private var location = ""
    @State private var locationName = ""
    @State private var sort = "date_desc"
    @State private var sessionScope = "upcoming"
    @State private var includeSubvotes = false
    @State private var hasDateFrom = false
    @State private var hasDateTo = false
    @State private var dateFrom = Date()
    @State private var dateTo = Date()
    @State private var page = 0
    @State private var committees: [String] = []
    @State private var fields: [PolicyFieldOption] = []
    @State private var parties: [PartyOption] = []
    @State private var districts: [DistrictOption] = []
    @State private var decisions: [DecisionSummary] = []
    @State private var sessions: [CouncilSession] = []
    @State private var mapPoints: [CouncilMapPoint] = []
    @State private var total = 0
    @State private var isLoading = false
    @State private var error: String?
    @State private var showsFilters = ProcessInfo.processInfo.environment["RATSLOTSE_DEBUG_COUNCIL_FILTER"] == "1"

    private let pageSize = 50

    var body: some View {
        VStack(spacing: 0) {
            HStack(alignment: .center, spacing: 12) {
                VStack(alignment: .leading, spacing: 2) {
                    Text("Im Rat stöbern")
                        .font(RatsFont.title(24))
                    Text("Beschlüsse, Sitzungen und Orte")
                        .font(RatsFont.body(12))
                        .foregroundStyle(RatsColor.secondary)
                }
                Spacer(minLength: 0)
                NavigationLink {
                    SavedCouncilView(model: model)
                } label: {
                    RatsGlyphView(glyph: .saved, color: RatsColor.bodyText)
                        .frame(width: 19, height: 19)
                        .frame(width: 40, height: 40)
                        .background(RatsColor.card)
                        .overlay(Circle().stroke(RatsColor.border))
                        .clipShape(Circle())
                }
                .accessibilityLabel("Merkliste")
            }
            .foregroundStyle(RatsColor.text)
            .padding(.horizontal, 18)
            .padding(.top, 16)
            .padding(.bottom, 4)

            if horizontalSizeClass != .regular {
                HStack(spacing: 4) {
                    ForEach(CouncilSection.allCases) { item in
                        Button {
                            withAnimation(.easeOut(duration: 0.16)) { model.councilSection = item }
                        } label: {
                            Text(item.rawValue)
                                .font(RatsFont.body(12.5, weight: .semibold))
                                .foregroundStyle(model.councilSection == item ? RatsColor.primaryText : RatsColor.bodyText)
                                .frame(maxWidth: .infinity, minHeight: 34)
                                .background(model.councilSection == item ? RatsColor.primary : Color.clear)
                                .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
                        }
                        .buttonStyle(.plain)
                    }
                }
                .padding(4)
                .background(RatsColor.separator)
                .overlay(RoundedRectangle(cornerRadius: 13, style: .continuous).stroke(RatsColor.border))
                .clipShape(RoundedRectangle(cornerRadius: 13, style: .continuous))
                .padding(.horizontal, 18)
                .padding(.vertical, 12)
            }

            if model.councilSection != .map {
                councilSearchControls
                    .padding(.horizontal, 13)
                    .frame(height: 44)
                    .background(RatsColor.card)
                    .overlay(RoundedRectangle(cornerRadius: 12).stroke(RatsColor.border))
                    .clipShape(RoundedRectangle(cornerRadius: 12))
                    .padding(.horizontal, 18)
                    .padding(.top, horizontalSizeClass == .regular ? 12 : 0)
                    .padding(.bottom, 10)
            }

            if model.councilSection == .decisions {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 7) {
                        FilterChip(label: "Alle", selected: outcome.isEmpty) { outcome = "" }
                        FilterChip(label: "Angenommen", selected: outcome == "angenommen") { outcome = "angenommen" }
                        FilterChip(label: "Abgelehnt", selected: outcome == "abgelehnt") { outcome = "abgelehnt" }
                        FilterChip(label: "Vertagt", selected: outcome == "vertagt") { outcome = "vertagt" }
                        if !location.isEmpty {
                            FilterChip(label: "Ort: \(locationName.isEmpty ? location : locationName)", selected: true) {
                                location = ""
                                locationName = ""
                                page = 0
                                Task { await load() }
                            }
                        }
                    }
                    .padding(.horizontal, 18)
                    .padding(.bottom, 9)
                }
            }

            if model.councilSection != .map {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 7) {
                        if model.councilSection == .decisions {
                            CouncilQuickFilterMenu(
                                title: "Thema",
                                symbol: "tag",
                                selection: policyField,
                                options: [CouncilFilterOption(value: "", label: "Alle Themen")]
                                    + fields.map {
                                        CouncilFilterOption(value: $0.key, label: "\($0.label) (\($0.count))")
                                    },
                                onSelect: { value in
                                    policyField = value
                                    reloadFromFirstPage()
                                }
                            )
                        }

                        if model.councilSection == .sessions {
                            FilterChip(label: "Anstehend", selected: sessionScope == "upcoming" && query.isEmpty && committee.isEmpty) {
                                selectSessionScope("upcoming")
                            }
                            FilterChip(label: "Vergangen", selected: sessionScope == "recent" && query.isEmpty && committee.isEmpty) {
                                selectSessionScope("recent")
                            }
                            FilterChip(label: "Alle", selected: sessionScope == "all" && query.isEmpty && committee.isEmpty) {
                                selectSessionScope("all")
                            }
                        }

                        CouncilQuickFilterMenu(
                            title: "Ausschuss",
                            symbol: "building.columns",
                            selection: committee,
                            options: [CouncilFilterOption(value: "", label: "Alle Ausschüsse")]
                                + committees.map { CouncilFilterOption(value: $0, label: $0) },
                            onSelect: { value in
                                committee = value
                                reloadFromFirstPage()
                            }
                        )

                        if model.councilSection == .decisions {
                            CouncilQuickFilterMenu(
                                title: "Ort",
                                symbol: "mappin.and.ellipse",
                                selection: district,
                                options: [CouncilFilterOption(value: "", label: "Alle Orte")]
                                    + districts.map {
                                        CouncilFilterOption(value: $0.placeID, label: "\($0.name) (\($0.count))")
                                    },
                                onSelect: { value in
                                    district = value
                                    reloadFromFirstPage()
                                }
                            )
                            CouncilQuickFilterMenu(
                                title: "Partei",
                                symbol: "person.2",
                                selection: party,
                                options: [CouncilFilterOption(value: "", label: "Alle Parteien")]
                                    + parties.map {
                                        CouncilFilterOption(value: $0.key, label: "\($0.label) (\($0.count))")
                                    },
                                onSelect: { value in
                                    party = value
                                    reloadFromFirstPage()
                                }
                            )
                        }

                        if model.councilSection == .decisions {
                            FilterChip(
                                label: advancedFilterCount > 0 ? "Weitere · \(advancedFilterCount)" : "Weitere Filter",
                                selected: advancedFilterCount > 0,
                                action: { showsFilters = true }
                            )
                        }
                    }
                    .padding(.horizontal, 18)
                    .padding(.bottom, 10)
                }
                .accessibilityLabel("Schnellfilter")
            }

            if model.councilSection == .map {
                councilMapStage
            } else {
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 12) {
                        HStack {
                            MonoKicker(model.councilSection.rawValue, trailing: total > 0 ? "\(total) gefunden" : nil)
                            if isLoading { ProgressView().controlSize(.small) }
                        }
                        if let error { ErrorCard(message: error) { Task { await load() } } }
                        if model.councilSection == .decisions {
                        ForEach(decisions) { decision in
                            Button { model.navigation.append(.decision(id: decision.id)) } label: {
                                DecisionRow(decision: decision).ratsCard()
                            }
                            .buttonStyle(.plain)
                        }
                        } else {
                            ForEach(Array(sessions.enumerated()), id: \.element.id) { index, session in
                                if isFirstSessionInYear(at: index) {
                                    SessionYearDivider(year: sessionYear(session.sessionDate))
                                }
                                if let id = session.ksinr {
                                    Button { model.navigation.append(.sessions(ksinr: id, tops: [])) } label: {
                                        SessionRow(session: session).ratsCard()
                                    }
                                    .buttonStyle(.plain)
                                } else {
                                    SessionRow(session: session).ratsCard()
                                }
                            }
                        }
                        if total > pageSize {
                            HStack {
                                Button("Zurück") { page -= 1; Task { await load() } }
                                    .disabled(page == 0 || isLoading)
                                Spacer()
                                Text("Seite \(page + 1) von \(max(1, Int(ceil(Double(total) / Double(pageSize)))))")
                                    .font(RatsFont.mono(10)).foregroundStyle(RatsColor.muted)
                                Spacer()
                                Button("Weiter") { page += 1; Task { await load() } }
                                    .disabled((page + 1) * pageSize >= total || isLoading)
                            }
                            .buttonStyle(SecondaryButtonStyle())
                            .padding(.top, 5)
                        }
                    }
                    .frame(maxWidth: 860, alignment: .leading)
                    .padding(18)
                }
                .refreshable { await load() }
            }
        }
        .background(RatsColor.page)
        .navigationTitle("Im Rat stöbern")
        .toolbarTitleDisplayMode(.inline)
        .onChange(of: model.councilSection) { _, _ in page = 0; Task { await load() } }
        .onChange(of: outcome) { _, _ in page = 0; Task { await load() } }
        .task {
            if committees.isEmpty { await loadFilterOptions() }
            if decisions.isEmpty && sessions.isEmpty { await load() }
        }
        .sheet(isPresented: $showsFilters) {
            CouncilFilterSheet(
                section: model.councilSection,
                committee: $committee,
                policyField: $policyField,
                party: $party,
                district: $district,
                location: $location,
                locationName: $locationName,
                sort: $sort,
                includeSubvotes: $includeSubvotes,
                hasDateFrom: $hasDateFrom,
                hasDateTo: $hasDateTo,
                dateFrom: $dateFrom,
                dateTo: $dateTo,
                committees: committees,
                fields: fields,
                parties: parties,
                districts: districts,
                clear: clearFilters,
                apply: {
                    showsFilters = false
                    page = 0
                    Task { await load() }
                }
            )
            .ratsLargeSheet()
        }
    }

    private var advancedFilterCount: Int {
        (location.isEmpty ? 0 : 1)
            + (hasDateFrom ? 1 : 0)
            + (hasDateTo ? 1 : 0)
            + (includeSubvotes ? 1 : 0)
            + (sort == "date_desc" ? 0 : 1)
    }

    private var searchPrompt: String {
        switch model.councilSection {
        case .decisions: "Beschlüsse durchsuchen"
        case .sessions: "Sitzungen durchsuchen"
        case .map: "Orte und Themen auf der Karte"
        }
    }

    private var councilSearchControls: some View {
        HStack(spacing: 9) {
            RatsGlyphView(glyph: .search, color: RatsColor.secondary)
                .frame(width: 18, height: 18)
            TextField(
                "",
                text: $query,
                prompt: Text(searchPrompt).foregroundStyle(RatsColor.secondary.opacity(0.82))
            )
                .font(RatsFont.body(14))
                .submitLabel(.search)
                .onSubmit {
                    if model.councilSection != .map { page = 0; Task { await load() } }
                }
            if !query.isEmpty {
                Button {
                    query = ""
                    if model.councilSection != .map { Task { await load() } }
                } label: {
                    Image(systemName: "xmark.circle.fill")
                        .font(.system(size: 16, weight: .semibold))
                        .foregroundStyle(RatsColor.muted)
                }
                .buttonStyle(.plain)
                .accessibilityLabel("Suche leeren")
            }
        }
    }

    private var councilMapStage: some View {
        ZStack(alignment: .top) {
            NativeCouncilMap(points: filteredMapPoints) { point in
                openMapPoint(point)
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)

            VStack(spacing: 8) {
                councilSearchControls
                    .padding(.horizontal, 13)
                    .frame(height: 46)
                    .councilMapGlassSurface(cornerRadius: 16)

                HStack(spacing: 8) {
                    if isLoading { ProgressView().controlSize(.small) }
                    Spacer(minLength: 0)
                    Text("\(filteredMapPoints.count) Treffer")
                        .font(RatsFont.mono(9.5, weight: .semibold))
                        .foregroundStyle(RatsColor.secondary)
                        .padding(.horizontal, 10)
                        .frame(height: 28)
                        .councilMapGlassSurface(cornerRadius: 11)
                }

                if let error {
                    ErrorCard(message: error) { Task { await load() } }
                }
            }
            .padding(12)
        }
        .clipShape(RoundedRectangle(cornerRadius: RatsRadius.card, style: .continuous))
        .overlay {
            RoundedRectangle(cornerRadius: RatsRadius.card, style: .continuous)
                .stroke(RatsColor.border, lineWidth: 1)
        }
        .padding(.horizontal, 18)
        // MKMapView zeichnet als UIKit-View auch unter das transparente
        // safeAreaInset der schwebenden Phone-Navigation. Der eigene Abstand
        // hält die komplette Karte sichtbar; auf iPad übernimmt die Sidebar.
        .padding(.bottom, horizontalSizeClass == .regular ? 10 : 72)
        .accessibilityHint("Nahe Punkte werden gebündelt. Tippe eine Zahl zum Heranzoomen oder einen Punkt für Details.")
    }

    private var filteredMapPoints: [CouncilMapPoint] {
        let needle = query.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !needle.isEmpty else { return mapPoints }
        return mapPoints.filter { $0.name.localizedCaseInsensitiveContains(needle) }
    }

    private func isFirstSessionInYear(at index: Int) -> Bool {
        guard sessions.indices.contains(index) else { return false }
        return index == 0 || sessionYear(sessions[index - 1].sessionDate) != sessionYear(sessions[index].sessionDate)
    }

    private func clearFilters() {
        committee = ""
        policyField = ""
        party = ""
        district = ""
        location = ""
        locationName = ""
        sort = "date_desc"
        includeSubvotes = false
        hasDateFrom = false
        hasDateTo = false
    }

    private func reloadFromFirstPage() {
        page = 0
        Task { await load() }
    }

    private func selectSessionScope(_ scope: String) {
        sessionScope = scope
        query = ""
        committee = ""
        reloadFromFirstPage()
    }

    private func load() async {
        isLoading = true
        error = nil
        defer { isLoading = false }
#if DEBUG
        if model.councilSection == .decisions,
           ratsDebugValue("RATSLOTSE_DEBUG_COUNCIL_CARDS") == "1",
           let fixture = Self.debugDecisionPage() {
            decisions = fixture.decisions
            total = fixture.total
            return
        }
        if model.councilSection == .sessions,
           ratsDebugValue("RATSLOTSE_DEBUG_COUNCIL_SESSIONS") == "1",
           let fixture = Self.debugSessionPage() {
            sessions = fixture.sessions
            total = fixture.total
            return
        }
#endif
        do {
            if model.councilSection == .decisions {
                let page: DecisionPage = try await model.api.get(
                    "/api/council/decisions",
                    query: [
                        .init(name: "q", value: query),
                        .init(name: "outcome", value: outcome),
                        .init(name: "committee", value: committee),
                        .init(name: "field", value: policyField),
                        .init(name: "party", value: party),
                        .init(name: "district", value: district),
                        .init(name: "location", value: location),
                        .init(name: "sort", value: sort),
                        .init(name: "date_from", value: hasDateFrom ? Self.apiDate.string(from: dateFrom) : ""),
                        .init(name: "date_to", value: hasDateTo ? Self.apiDate.string(from: dateTo) : ""),
                        .init(name: "include_subvotes", value: includeSubvotes ? "true" : "false"),
                        .init(name: "limit", value: String(pageSize)),
                        .init(name: "offset", value: String(page * pageSize)),
                    ]
                )
                decisions = page.decisions
                total = page.total
            } else if model.councilSection == .sessions {
                // Wie im Web: ohne Suche beginnt die Liste bei den nächsten
                // Terminen (aufsteigend). Suche/Ausschussfilter wechseln in
                // den Gesamtbestand, dessen Treffer das Backend neueste zuerst
                // liefert. So stimmen Reihenfolge und Pagination miteinander.
                let effectiveScope = query.isEmpty && committee.isEmpty ? sessionScope : "all"
                let page: SessionPage = try await model.api.get(
                    "/api/council/sessions",
                    query: [
                        .init(name: "q", value: query),
                        .init(name: "committee", value: committee),
                        .init(name: "scope", value: effectiveScope),
                        .init(name: "limit", value: String(pageSize)),
                        .init(name: "offset", value: String(page * pageSize)),
                    ]
                )
                sessions = page.sessions
                total = page.total
            } else {
                let response: CouncilMapPoints = try await model.api.get("/api/council/entities-map")
                mapPoints = response.entities
                total = response.entities.count
            }
        } catch { self.error = error.localizedDescription }
    }

    private func openMapPoint(_ point: CouncilMapPoint) {
        switch point.target {
        case "ort":
            if let placeID = point.placeID { model.navigation.append(.place(id: placeID)) }
        case "location":
            location = point.locationSlug ?? point.slug
            locationName = point.name
            query = ""
            model.councilSection = .decisions
            page = 0
        default:
            model.navigation.append(.topic(slug: point.slug))
        }
    }

    private func loadFilterOptions() async {
        async let committeeRequest: CommitteeOptions = model.api.get("/api/council/committees")
        async let fieldRequest: PolicyFieldOptions = model.api.get("/api/council/fields")
        async let partyRequest: PartyOptions = model.api.get("/api/council/parties")
        async let districtRequest: DistrictOptions = model.api.get("/api/council/districts")
        if let response = try? await committeeRequest { committees = response.committees }
        if let response = try? await fieldRequest { fields = response.fields }
        if let response = try? await partyRequest { parties = response.parties }
        if let response = try? await districtRequest { districts = response.districts }
    }

    private static let apiDate: DateFormatter = {
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.dateFormat = "yyyy-MM-dd"
        return formatter
    }()

#if DEBUG
    private static func debugDecisionPage() -> DecisionPage? {
        let raw = #"""
        {
          "total": 3,
          "decisions": [
            {
              "id": 1,
              "title": "Haushaltssatzung und Haushaltsplan 2026 (Kernhaushalt) mit der mittelfristigen Ergebnis- und Finanzplanung und dem Investitionsprogramm 2027–2029",
              "summary": "Haushaltssatzung und Haushaltsplan 2026 mit mittelfristiger Planung und Investitionsprogramm beschlossen.",
              "committee": "Rat der Stadt",
              "session_date": "2026-02-09",
              "item_number": "6.5",
              "outcome": "angenommen",
              "vote": "mehrheitlich",
              "gegenstimmen": 20,
              "amount_eur": 12400000,
              "importance": 82,
              "factions": []
            },
            {
              "id": 2,
              "title": "Neue sichere Querung an der Cloppenburger Straße",
              "summary": "Die Planung für eine sicherere Querung wird weitergeführt und mit dem Radverkehr abgestimmt.",
              "committee": "Verkehrsausschuss",
              "session_date": "2026-09-03",
              "item_number": "7",
              "outcome": "angenommen",
              "vote": "einstimmig",
              "importance": 58,
              "factions": ["Grüne", "SPD"]
            },
            {
              "id": 3,
              "title": "Bebauungsplan 851 – Prüfung der Abwägungsvorschläge",
              "summary": "Der Satzungsbeschluss wird bis zur nächsten Beratung zurückgestellt.",
              "committee": "Ausschuss für Stadtplanung und Bauen",
              "session_date": "2026-08-31",
              "item_number": "4",
              "outcome": "vertagt",
              "importance": 41,
              "factions": []
            }
          ]
        }
        """#
        return try? JSONDecoder().decode(DecisionPage.self, from: Data(raw.utf8))
    }

    private static func debugSessionPage() -> SessionPage? {
        let raw = #"""
        {
          "count": 4,
          "total": 4,
          "sessions": [
            {
              "ksinr": 8101,
              "committee": "Ausschuss für Allgemeine Angelegenheiten",
              "session_date": "2026-08-31",
              "session_time": "16:00",
              "location": "Kulturzentrum PFL",
              "title": "Ausschuss für Allgemeine Angelegenheiten",
              "n_items": 9,
              "my_topic_items": []
            },
            {
              "ksinr": 8102,
              "committee": "Rat der Stadt",
              "session_date": "2026-08-31",
              "session_time": "17:00",
              "location": "Alte Fleiwa, Sitzungssaal 1/2",
              "title": "Rat der Stadt",
              "n_items": 13,
              "my_topic_items": [{"item_number":"7","topic_name":"Sichere Schulwege"}]
            },
            {
              "ksinr": 8103,
              "committee": "Ausschuss für Stadtplanung und Bauen",
              "session_date": "2026-09-03",
              "session_time": "18:00",
              "location": "Technisches Rathaus",
              "title": "Ausschuss für Stadtplanung und Bauen",
              "n_items": 7,
              "my_topic_items": []
            },
            {
              "calendar_id": 99,
              "committee": "Verkehrsausschuss",
              "session_date": "2027-01-14",
              "session_time": "17:00",
              "location": "Alte Fleiwa",
              "title": "Verkehrsausschuss",
              "n_items": 0,
              "my_topic_items": []
            }
          ]
        }
        """#
        return try? JSONDecoder().decode(SessionPage.self, from: Data(raw.utf8))
    }
#endif
}

private struct CouncilFilterSheet: View {
    let section: CouncilSection
    @Binding var committee: String
    @Binding var policyField: String
    @Binding var party: String
    @Binding var district: String
    @Binding var location: String
    @Binding var locationName: String
    @Binding var sort: String
    @Binding var includeSubvotes: Bool
    @Binding var hasDateFrom: Bool
    @Binding var hasDateTo: Bool
    @Binding var dateFrom: Date
    @Binding var dateTo: Date
    let committees: [String]
    let fields: [PolicyFieldOption]
    let parties: [PartyOption]
    let districts: [DistrictOption]
    let clear: () -> Void
    let apply: () -> Void

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                RatsSheetHeader(
                    "Filter",
                    leadingTitle: "Zurücksetzen",
                    leadingAction: clear,
                    trailingTitle: "Fertig",
                    trailingAction: apply
                )
                ScrollView {
                    VStack(alignment: .leading, spacing: 18) {
                    RatsModalIntro(
                        kicker: "Rat durchsuchen",
                        title: "Filter & Sortierung",
                        message: "Grenze die Ratsdaten ein, ohne dabei den Überblick zu verlieren.",
                        symbol: "line.3.horizontal.decrease"
                    )

                    RatsSectionPanel("Gremium", detail: "Wähle einen Ausschuss oder sieh alle gemeinsam.", symbol: "building.columns") {
                        RatsSettingsRow("Ausschuss", symbol: "person.3") {
                            CouncilFilterMenu(
                                title: "Ausschuss",
                                selection: $committee,
                                options: [CouncilFilterOption(value: "", label: "Alle Ausschüsse")]
                                    + committees.map { CouncilFilterOption(value: $0, label: $0) }
                            )
                        }
                    }

                    if section == .decisions {
                        RatsSectionPanel("Inhalt", detail: "Themen, Orte und Antragsteller kombinieren.", symbol: "doc.text.magnifyingglass") {
                        if !location.isEmpty {
                                HStack(alignment: .center, spacing: 10) {
                                    Image(systemName: "mappin.circle.fill")
                                        .foregroundStyle(RatsColor.signal)
                                    VStack(alignment: .leading, spacing: 2) {
                                        Text("Exakter Beschlussort")
                                            .font(RatsFont.body(11, weight: .semibold))
                                            .foregroundStyle(RatsColor.secondary)
                                        Text(locationName.isEmpty ? location : locationName)
                                            .font(RatsFont.body(14, weight: .semibold))
                                    }
                                    Spacer()
                                    Button {
                                        location = ""
                                        locationName = ""
                                    } label: {
                                        Image(systemName: "xmark")
                                            .font(.system(size: 11, weight: .bold))
                                            .frame(width: 28, height: 28)
                                            .background(RatsColor.dangerTint)
                                            .clipShape(Circle())
                                    }
                                    .foregroundStyle(RatsColor.danger)
                                    .accessibilityLabel("Beschlussort-Filter entfernen")
                                }
                                .padding(12)
                                .background(RatsColor.stage)
                                .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
                            }

                            RatsSettingsRow("Themenfeld", symbol: "tag") {
                                CouncilFilterMenu(
                                    title: "Themenfeld",
                                    selection: $policyField,
                                    options: [CouncilFilterOption(value: "", label: "Alle Themenfelder")]
                                        + fields.map {
                                            CouncilFilterOption(value: $0.key, label: "\($0.label) (\($0.count))")
                                        }
                                )
                            }
                            Divider().overlay(RatsColor.separator)
                            RatsSettingsRow("Ortsbezug", symbol: "mappin.and.ellipse") {
                                CouncilFilterMenu(
                                    title: "Ortsbezug",
                                    selection: $district,
                                    options: [CouncilFilterOption(value: "", label: "Alle Orte")]
                                        + districts.map {
                                            CouncilFilterOption(value: $0.placeID, label: "\($0.name) (\($0.count))")
                                        }
                                )
                            }
                            Divider().overlay(RatsColor.separator)
                            RatsSettingsRow("Partei", symbol: "person.2.badge.gearshape") {
                                CouncilFilterMenu(
                                    title: "Antragsteller-Partei",
                                    selection: $party,
                                    options: [CouncilFilterOption(value: "", label: "Alle Parteien")]
                                        + parties.map {
                                            CouncilFilterOption(value: $0.key, label: "\($0.label) (\($0.count))")
                                        }
                                )
                            }
                            Divider().overlay(RatsColor.separator)
                            RatsSettingsRow("Änderungsanträge einzeln", detail: "Zusätzliche Einzelbeschlüsse anzeigen", symbol: "doc.on.doc") {
                                Toggle("", isOn: $includeSubvotes)
                                    .labelsHidden()
                                    .tint(RatsColor.primary)
                            }
                        }

                        RatsSectionPanel("Zeitraum", detail: "Aktiviere nur die Grenzen, die du wirklich brauchst.", symbol: "calendar") {
                            RatsSettingsRow("Startdatum", symbol: "calendar.badge.plus") {
                                Toggle("", isOn: $hasDateFrom)
                                    .labelsHidden()
                                    .tint(RatsColor.primary)
                            }
                            if hasDateFrom {
                                DatePicker("Von", selection: $dateFrom, displayedComponents: .date)
                                    .font(RatsFont.body(13))
                                    .tint(RatsColor.primary)
                                    .padding(12)
                                    .background(RatsColor.stage)
                                    .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
                            }
                            Divider().overlay(RatsColor.separator)
                            RatsSettingsRow("Enddatum", symbol: "calendar.badge.checkmark") {
                                Toggle("", isOn: $hasDateTo)
                                    .labelsHidden()
                                    .tint(RatsColor.primary)
                            }
                            if hasDateTo {
                                DatePicker("Bis", selection: $dateTo, displayedComponents: .date)
                                    .font(RatsFont.body(13))
                                    .tint(RatsColor.primary)
                                    .padding(12)
                                    .background(RatsColor.stage)
                                    .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
                            }
                        }

                        RatsSectionPanel("Sortierung", symbol: "arrow.up.arrow.down") {
                            RatsSettingsRow("Reihenfolge", symbol: "list.number") {
                                CouncilFilterMenu(
                                    title: "Reihenfolge",
                                    selection: $sort,
                                    options: [
                                        CouncilFilterOption(value: "date_desc", label: "Neueste zuerst"),
                                        CouncilFilterOption(value: "date_asc", label: "Älteste zuerst"),
                                        CouncilFilterOption(value: "importance", label: "Wichtigkeit"),
                                        CouncilFilterOption(value: "interest", label: "Persönliche Relevanz"),
                                    ]
                                )
                            }
                        }
                    }

                    Button(action: apply) {
                        Label("Ergebnisse anzeigen", systemImage: "checkmark")
                            .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(PrimaryButtonStyle())
                    }
                    .frame(maxWidth: 620, alignment: .leading)
                    .padding(.horizontal, 18)
                    .padding(.vertical, 22)
                }
                .background(RatsColor.page)
            }
            .toolbar(.hidden, for: .navigationBar)
        }
    }
}

private struct CouncilFilterOption: Identifiable {
    let value: String
    let label: String
    var id: String { value }
}

private struct CouncilFilterMenu: View {
    let title: String
    @Binding var selection: String
    let options: [CouncilFilterOption]

    private var selectedLabel: String {
        options.first(where: { $0.value == selection })?.label ?? options.first?.label ?? "Auswählen"
    }

    var body: some View {
        Menu {
            ForEach(options) { option in
                Button {
                    selection = option.value
                } label: {
                    if option.value == selection {
                        Label(option.label, systemImage: "checkmark")
                    } else {
                        Text(option.label)
                    }
                }
            }
        } label: {
            HStack(spacing: 5) {
                Text(selectedLabel)
                    .lineLimit(1)
                    .truncationMode(.tail)
                    .minimumScaleFactor(0.78)
                Image(systemName: "chevron.up.chevron.down")
                    .font(.system(size: 9, weight: .bold))
            }
            .font(RatsFont.body(13, weight: .semibold))
            .foregroundStyle(RatsColor.primary)
            .frame(width: 170, alignment: .trailing)
            .contentShape(Rectangle())
        }
        .accessibilityLabel(title)
        .accessibilityValue(selectedLabel)
    }
}

private struct CouncilQuickFilterMenu: View {
    let title: String
    let symbol: String
    let selection: String
    let options: [CouncilFilterOption]
    let onSelect: (String) -> Void

    private var selected: Bool { !selection.isEmpty }

    private var selectedLabel: String {
        guard selected else { return title }
        return options.first(where: { $0.value == selection })?.label ?? selection
    }

    var body: some View {
        Menu {
            ForEach(options) { option in
                Button {
                    onSelect(option.value)
                } label: {
                    if option.value == selection {
                        Label(option.label, systemImage: "checkmark")
                    } else {
                        Text(option.label)
                    }
                }
            }
        } label: {
            HStack(spacing: 6) {
                Image(systemName: symbol)
                    .font(.system(size: 11, weight: .semibold))
                Text(selectedLabel)
                    .lineLimit(1)
                    .truncationMode(.tail)
                Image(systemName: "chevron.down")
                    .font(.system(size: 8, weight: .bold))
            }
            .font(RatsFont.body(12, weight: .semibold))
            .foregroundStyle(selected ? RatsColor.primary : RatsColor.secondary)
            .padding(.horizontal, 11)
            .frame(maxWidth: 190, minHeight: 34)
            .background(selected ? RatsColor.primary.opacity(0.10) : RatsColor.card)
            .overlay(Capsule().stroke(selected ? RatsColor.primary.opacity(0.32) : RatsColor.border))
            .clipShape(Capsule())
            .contentShape(Capsule())
        }
        .accessibilityLabel(title)
        .accessibilityValue(selected ? selectedLabel : "Alle")
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
        HStack(alignment: .center, spacing: 13) {
            SessionDateTile(date: session.sessionDate)

            VStack(alignment: .leading, spacing: 5) {
                Text(shortCommittee)
                    .font(RatsFont.body(16, weight: .bold))
                    .foregroundStyle(RatsColor.text)
                    .lineLimit(2)
                    .multilineTextAlignment(.leading)

                if shortCommittee != session.committee {
                    Text(session.committee)
                        .font(RatsFont.body(12.5))
                        .foregroundStyle(RatsColor.secondary)
                        .lineLimit(2)
                }

                Label {
                    Text(scheduleMetadata)
                } icon: {
                    Image(systemName: "clock")
                }
                .font(RatsFont.body(11.5, weight: .medium))
                .foregroundStyle(RatsColor.secondary)
                .lineLimit(1)

                if let location = cleanLocation {
                    Label {
                        Text(location)
                    } icon: {
                        Image(systemName: "mappin.and.ellipse")
                    }
                    .font(RatsFont.body(11.5))
                    .foregroundStyle(RatsColor.secondary)
                    .lineLimit(1)
                }

                if let matches = session.myTopicItems, !matches.isEmpty {
                    Label("\(matches.count) für dich", systemImage: "bell.fill")
                        .font(RatsFont.body(10.5, weight: .semibold))
                        .foregroundStyle(RatsColor.signal)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 4)
                        .background(RatsColor.signal.opacity(0.09))
                        .clipShape(Capsule())
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)

            HStack(spacing: 8) {
                Text(agendaLabel)
                    .font(RatsFont.body(11.5, weight: .semibold))
                    .foregroundStyle(session.ksinr == nil ? RatsColor.secondary : RatsColor.primary)
                    .padding(.horizontal, 9)
                    .padding(.vertical, 5)
                    .background(session.ksinr == nil ? RatsColor.stage : RatsColor.primary.opacity(0.10))
                    .clipShape(Capsule())
                    .fixedSize()

                Image(systemName: session.ksinr == nil ? "calendar.badge.clock" : "chevron.right")
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundStyle(RatsColor.muted)
                    .frame(width: 18, height: 18)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .contentShape(Rectangle())
        .accessibilityElement(children: .combine)
        .accessibilityLabel(accessibilityLabel)
    }

    private var shortCommittee: String {
        session.committee
            .replacingOccurrences(of: "Ausschuss für ", with: "")
            .replacingOccurrences(of: "Rat der Stadt", with: "Rat")
    }

    private var scheduleMetadata: String {
        let weekday = (RatsDate.weekday(session.sessionDate) ?? "")
            .split(separator: ",").first.map(String.init)
        let time = session.sessionTime.map { "\($0) Uhr" }
        return [weekday, time].compactMap { value in
            guard let value, !value.isEmpty else { return nil }
            return value
        }.joined(separator: " · ")
    }

    private var cleanLocation: String? {
        guard let location = session.location?.trimmingCharacters(in: .whitespacesAndNewlines),
              !location.isEmpty else { return nil }
        return location
    }

    private var agendaLabel: String {
        guard session.ksinr != nil else { return "folgt" }
        return "\(session.itemCount) \(session.itemCount == 1 ? "TOP" : "TOPs")"
    }

    private var accessibilityLabel: String {
        [
            session.committee,
            RatsDate.short(session.sessionDate),
            scheduleMetadata,
            cleanLocation,
            session.ksinr == nil ? "Tagesordnung folgt" : agendaLabel,
        ].compactMap { $0 }.joined(separator: ", ")
    }
}

private struct SessionDateTile: View {
    let date: String

    var body: some View {
        VStack(spacing: 0) {
            Text(month)
                .font(RatsFont.mono(9.5, weight: .semibold))
                .foregroundStyle(RatsColor.secondary)
                .textCase(.uppercase)
            Text(day)
                .font(RatsFont.title(21))
                .foregroundStyle(RatsColor.text)
        }
        .frame(width: 54, height: 62)
        .background {
            LinearGradient(
                colors: [RatsColor.primary.opacity(0.10), RatsColor.stage],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
        }
        .overlay(RoundedRectangle(cornerRadius: 14).stroke(RatsColor.primary.opacity(0.18)))
        .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
        .accessibilityHidden(true)
    }

    private var components: [Substring] { date.prefix(10).split(separator: "-") }
    private var day: String { components.count == 3 ? String(Int(components[2]) ?? 0) : "–" }
    private var month: String {
        guard components.count == 3, let number = Int(components[1]), (1...12).contains(number) else { return "" }
        return ["JAN", "FEB", "MÄR", "APR", "MAI", "JUN", "JUL", "AUG", "SEP", "OKT", "NOV", "DEZ"][number - 1]
    }
}

private struct SessionYearDivider: View {
    let year: String

    var body: some View {
        HStack(spacing: 12) {
            Text(year)
                .font(RatsFont.mono(11, weight: .semibold))
                .foregroundStyle(RatsColor.secondary)
                .tracking(1.5)
            Rectangle().fill(RatsColor.border).frame(height: 1)
        }
        .accessibilityAddTraits(.isHeader)
    }
}

struct DecisionDetailView: View {
    let model: AppModel
    let decisionID: Int
    @State private var detail: DecisionDetail?
    @State private var error: String?
    @State private var bookmarkID: Int?
    @State private var isWorking = false
    @State private var previewAttachment: CouncilAttachment?

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                if let detail {
                    let decision = detail.decision
                    DecisionDetailHeader(detail: detail)

                    DecisionActionBar(
                        isBookmarked: bookmarkID != nil,
                        follow: detail.follow,
                        shareLink: model.router.universalLink(for: .decision(id: decisionID)),
                        isWorking: isWorking,
                        toggleBookmark: toggleBookmark,
                        toggleFollow: toggleFollow
                    )

                    if let participation = detail.participation,
                       let url = URL(string: participation.url) {
                        DecisionParticipationBanner(participation: participation, url: url)
                    }

                    DecisionDetailPrimaryLayout(detail: detail) { previewAttachment = $0 }

                    let stops = detail.consultations.isEmpty
                        ? detail.templateJourney.map(CouncilConsultationStop.init(journey:))
                        : detail.consultations
                    if !stops.isEmpty {
                        VStack(alignment: .leading, spacing: 13) {
                            MonoKicker("Weg durch die Gremien", trailing: "\(stops.count) Stationen")
                            ForEach(Array(stops.enumerated()), id: \.element.id) { index, stop in
                                HStack(alignment: .top, spacing: 10) {
                                    Image(systemName: stop.future == true ? "clock" : "checkmark.circle.fill")
                                        .foregroundStyle(stop.future == true ? RatsColor.warning : RatsColor.primary)
                                    VStack(alignment: .leading, spacing: 3) {
                                        Text(stop.committee).font(RatsFont.body(14, weight: .semibold))
                                        Text([stop.date, stop.itemNumber, stop.result].compactMap { $0 }.joined(separator: " · "))
                                            .font(RatsFont.mono(10)).foregroundStyle(RatsColor.muted)
                                    }
                                }
                                if index < stops.count - 1 { Divider().padding(.leading, 30) }
                            }
                        }
                        .ratsCard()
                    }

                    if !detail.presentParties.isEmpty {
                        DecisionPartyCard(title: "Anwesende Fraktionen", parties: detail.presentParties)
                    }

                    if !detail.attendance.isEmpty {
                        DecisionAttendanceCard(attendance: detail.attendance)
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

                    if let raw = detail.ratsinfoURL, let url = URL(string: raw) {
                        Link(destination: url) {
                            Label("Amtliche Quelle im Ratsinfosystem", systemImage: "arrow.up.right.square")
                                .frame(maxWidth: .infinity, alignment: .leading)
                        }
                        .font(RatsFont.body(13, weight: .medium))
                    }

                    if let pressURL = Self.pressURL(for: decision.title) {
                        Link(destination: pressURL) {
                            Label("Bei NWZonline nach Berichten suchen", systemImage: "newspaper")
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
            .frame(maxWidth: 1040, alignment: .leading)
            .padding(18)
        }
        .background(RatsColor.page)
        .navigationTitle("Beschluss")
        .navigationBarTitleDisplayMode(.inline)
        .task { await load() }
        .sheet(item: $previewAttachment) { attachment in
            CouncilAttachmentPreview(attachment: attachment)
        }
    }

    private func load() async {
#if DEBUG
        if ratsDebugValue("RATSLOTSE_DEBUG_DECISION_DETAIL") == "1",
           let fixture = Self.debugDetail() {
            detail = fixture
            error = nil
            return
        }
#endif
        do {
            async let detailRequest: DecisionDetail = model.api.get("/api/council/decision/\(decisionID)")
            if model.user != nil {
                async let bookmarksRequest: BookmarkPage = model.api.get("/api/bookmarks")
                let (loadedDetail, bookmarks) = try await (detailRequest, bookmarksRequest)
                detail = loadedDetail
                RecentDecisionStore.track(loadedDetail.decision)
                bookmarkID = bookmarks.bookmarks.first { $0.decision?.id == decisionID }?.id
            } else {
                let loadedDetail = try await detailRequest
                detail = loadedDetail
                RecentDecisionStore.track(loadedDetail.decision)
            }
            error = nil
        } catch { self.error = error.localizedDescription }
    }

    private static func pressURL(for title: String) -> URL? {
        var components = URLComponents(string: "https://www.nwzonline.de/suche/")
        components?.queryItems = [URLQueryItem(name: "q", value: title)]
        return components?.url
    }

#if DEBUG
    private static func debugDetail() -> DecisionDetail? {
        let raw = #"""
        {
          "decision": {
            "id": 1,
            "ksinr": 88,
            "kind": "decision",
            "item_number": "6.5",
            "title": "Haushaltssatzung und Haushaltsplan 2026 mit der mittelfristigen Ergebnis- und Finanzplanung",
            "summary": "Der Rat hat den Haushalt für 2026 beschlossen und damit festgelegt, wofür Oldenburg im kommenden Jahr Geld ausgeben darf.",
            "simple_summary": "Der Rat hat den Haushalt für 2026 beschlossen. Darin steht, welche Projekte Oldenburg bezahlen kann und wo die Stadt im kommenden Jahr Schwerpunkte setzt.",
            "beschluss": "Die Haushaltssatzung und der Haushaltsplan 2026 werden einschließlich der mittelfristigen Ergebnis- und Finanzplanung sowie des Investitionsprogramms beschlossen.",
            "committee": "Rat der Stadt",
            "session_date": "2026-02-09",
            "outcome": "angenommen",
            "vote": "mehrheitlich",
            "gegenstimmen": 20,
            "enthaltungen": 2,
            "factions": ["SPD", "Grüne"],
            "parties": ["SPD", "Grüne"],
            "vorlage_nr": "26/0456",
            "raw_result": "mehrheitlich bei 20 Gegenstimmen und 2 Enthaltungen",
            "protocol_url": "https://ratslotse.de",
            "policy_field": "finanzen",
            "policy_tags": ["Haushalt", "Investitionen"],
            "amount_eur": 12400000,
            "importance": 82,
            "abweichung": "stark"
          },
          "attendance": [
            {"name":"A","party":"SPD","role":"mitglied"},
            {"name":"B","party":"SPD","role":"mitglied"},
            {"name":"C","party":"CDU","role":"mitglied"},
            {"name":"D","party":"Grüne","role":"mitglied"}
          ],
          "entities": [{"slug":"haushalt-2026","name":"Haushalt 2026"}],
          "present_parties": ["SPD", "CDU", "Grüne", "FDP"],
          "ratsinfo_url": "https://ratslotse.de",
          "vorlage_url": "https://ratslotse.de",
          "vorlage": {
            "vorlage_nr":"26/0456",
            "title":"Haushaltssatzung und Haushaltsplan 2026",
            "art":"Beschlussvorlage",
            "document_url":"https://ratslotse.de",
            "excerpt":"Die Verwaltung legt den Entwurf des Haushaltsplans vor. Er bündelt laufende Aufgaben und geplante Investitionen der Stadt.",
            "amt":"Amt für Finanzen",
            "klima_check":"Mehrere Investitionen betreffen energetische Sanierungen und klimafreundliche Mobilität.",
            "finanz_check":"Die vorgesehenen Investitionen sind in der mittelfristigen Finanzplanung berücksichtigt."
          },
          "anlagen": [
            {"document_id":77,"label":"Haushaltsplan 2026 – Gesamtfassung","url":"https://ratslotse.de","is_antrag":0,"antragsteller":[],"status":"ok"},
            {"document_id":78,"label":"Änderungsantrag zum Investitionsprogramm","url":"https://ratslotse.de","is_antrag":1,"antragsteller":["SPD","Grüne"],"status":"ok"}
          ],
          "importance_breakdown": {"score":82,"impact_reason":"Der Beschluss betrifft nahezu alle Aufgaben der Stadt und legt den finanziellen Rahmen für das ganze Jahr fest."},
          "beratungsfolge": [
            {"datum":"2026-01-21","gremium":"Finanzen und Beteiligungen","top":"4","ergebnis":"empfohlen","ksinr":87,"future":false},
            {"datum":"2026-02-09","gremium":"Rat der Stadt","top":"6.5","ergebnis":"angenommen","ksinr":88,"future":false}
          ],
          "follow":{"kvonr":901,"following":false},
          "similar": [],
          "sub_votes": []
        }
        """#
        return try? JSONDecoder().decode(DecisionDetail.self, from: Data(raw.utf8))
    }
#endif

    private func toggleBookmark() {
        guard model.user != nil else { model.authPresentation = .login; return }
        struct Body: Codable, Sendable { let kind: String; let decision_id: Int }
        Task {
            isWorking = true
            defer { isWorking = false }
            do {
                if let bookmarkID {
                    try await model.api.sendVoid("/api/bookmarks/\(bookmarkID)", method: .delete)
                    self.bookmarkID = nil
                } else {
                    let bookmark: BookmarkEntry = try await model.api.send(
                        "/api/bookmarks", body: Body(kind: "decision", decision_id: decisionID)
                    )
                    bookmarkID = bookmark.id
                }
            } catch { self.error = error.localizedDescription }
        }
    }

    private func toggleFollow(_ follow: FollowStatus) {
        guard model.user != nil else { model.authPresentation = .login; return }
        Task {
            isWorking = true
            defer { isWorking = false }
            do {
                let updated: FollowStatus = try await model.api.sendWithoutBody(
                    "/api/council/vorlage/\(follow.templateID)/follow",
                    method: follow.following ? .delete : .post
                )
                guard let current = detail else { return }
                detail = current.replacing(follow: updated)
            } catch { self.error = error.localizedDescription }
        }
    }
}

private struct DecisionActionBar: View {
    let isBookmarked: Bool
    let follow: FollowStatus?
    let shareLink: URL?
    let isWorking: Bool
    let toggleBookmark: () -> Void
    let toggleFollow: (FollowStatus) -> Void

    var body: some View {
        HStack(spacing: 10) {
            if let follow {
                Button { toggleFollow(follow) } label: {
                    HStack(spacing: 9) {
                        Image(systemName: follow.following ? "bell.fill" : "bell.badge")
                            .font(.system(size: 16, weight: .semibold))
                        Text(follow.following ? "Wird verfolgt" : "Vorgang folgen")
                            .font(RatsFont.body(14, weight: .semibold))
                            .lineLimit(1)
                        Spacer(minLength: 0)
                        Image(systemName: follow.following ? "checkmark" : "plus")
                            .font(.system(size: 12, weight: .bold))
                    }
                    .foregroundStyle(follow.following ? RatsColor.primary : RatsColor.primaryText)
                    .padding(.horizontal, 16)
                    .frame(maxWidth: .infinity, minHeight: 50)
                    .background(follow.following ? RatsColor.primary.opacity(0.10) : RatsColor.primary)
                    .overlay {
                        RoundedRectangle(cornerRadius: 15, style: .continuous)
                            .stroke(RatsColor.primary.opacity(follow.following ? 0.28 : 0), lineWidth: 1)
                    }
                    .clipShape(RoundedRectangle(cornerRadius: 15, style: .continuous))
                }
                .buttonStyle(DecisionActionPressStyle())
                .disabled(isWorking)
                .accessibilityHint(follow.following ? "Beendet die Verfolgung dieses Vorgangs" : "Meldet neue Stationen dieses Vorgangs")
            }

            Button(action: toggleBookmark) {
                DecisionUtilityAction(
                    symbol: isBookmarked ? "bookmark.fill" : "bookmark",
                    active: isBookmarked
                )
            }
            .buttonStyle(DecisionActionPressStyle())
            .disabled(isWorking)
            .accessibilityLabel(isBookmarked ? "Aus Merkliste entfernen" : "Beschluss merken")
            .accessibilityValue(isBookmarked ? "Gemerkt" : "Nicht gemerkt")

            if let shareLink {
                ShareLink(item: shareLink) {
                    DecisionUtilityAction(symbol: "square.and.arrow.up", active: false)
                }
                .buttonStyle(DecisionActionPressStyle())
                .accessibilityLabel("Beschluss teilen")
            }
        }
        .frame(maxWidth: 560, alignment: .leading)
    }
}

private struct DecisionUtilityAction: View {
    let symbol: String
    let active: Bool

    var body: some View {
        Image(systemName: symbol)
            .font(.system(size: 17, weight: .semibold))
            .foregroundStyle(active ? RatsColor.primaryText : RatsColor.primary)
            .frame(width: 50, height: 50)
            .decisionUtilitySurface(active: active)
    }
}

private struct DecisionActionPressStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .scaleEffect(configuration.isPressed ? 0.96 : 1)
            .opacity(configuration.isPressed ? 0.78 : 1)
            .animation(.snappy(duration: 0.16), value: configuration.isPressed)
    }
}

private extension View {
    @ViewBuilder
    func councilMapGlassSurface(cornerRadius: CGFloat) -> some View {
        if #available(iOS 26.0, *) {
            self
                .glassEffect(
                    .regular.tint(RatsColor.card.opacity(0.16)),
                    in: .rect(cornerRadius: cornerRadius)
                )
                .overlay {
                    RoundedRectangle(cornerRadius: cornerRadius, style: .continuous)
                        .stroke(.white.opacity(0.38), lineWidth: 0.8)
                }
                .shadow(color: RatsColor.primary.opacity(0.12), radius: 14, y: 5)
        } else {
            self
                .background {
                    ZStack {
                        RoundedRectangle(cornerRadius: cornerRadius, style: .continuous)
                            .fill(.ultraThinMaterial)
                        RoundedRectangle(cornerRadius: cornerRadius, style: .continuous)
                            .fill(RatsColor.card.opacity(0.68))
                    }
                }
                .overlay {
                    RoundedRectangle(cornerRadius: cornerRadius, style: .continuous)
                        .stroke(.white.opacity(0.48), lineWidth: 1)
                }
                .clipShape(RoundedRectangle(cornerRadius: cornerRadius, style: .continuous))
                .shadow(color: RatsColor.primary.opacity(0.10), radius: 12, y: 4)
        }
    }

    @ViewBuilder
    func decisionUtilitySurface(active: Bool) -> some View {
        if #available(iOS 26.0, *) {
            self
                .glassEffect(
                    .regular.tint(active ? RatsColor.primary.opacity(0.72) : RatsColor.card.opacity(0.22)),
                    in: .rect(cornerRadius: 15)
                )
                .overlay {
                    RoundedRectangle(cornerRadius: 15, style: .continuous)
                        .stroke(active ? RatsColor.primary.opacity(0.36) : .white.opacity(0.30), lineWidth: 0.8)
                }
        } else {
            self
                .background(active ? RatsColor.primary : RatsColor.card)
                .overlay {
                    RoundedRectangle(cornerRadius: 15, style: .continuous)
                        .stroke(active ? RatsColor.primary : RatsColor.border, lineWidth: 1)
                }
                .clipShape(RoundedRectangle(cornerRadius: 15, style: .continuous))
        }
    }
}

private struct DecisionDetailPrimaryLayout: View {
    let detail: DecisionDetail
    let preview: (CouncilAttachment) -> Void

    var body: some View {
        ViewThatFits(in: .horizontal) {
            HStack(alignment: .top, spacing: 18) {
                DecisionNarrativeColumn(detail: detail)
                    .frame(minWidth: 440, maxWidth: .infinity, alignment: .topLeading)
                DecisionFactsColumn(detail: detail, preview: preview)
                    .frame(width: 310, alignment: .topLeading)
            }
            VStack(alignment: .leading, spacing: 20) {
                DecisionNarrativeColumn(detail: detail)
                DecisionFactsColumn(detail: detail, preview: preview)
            }
        }
    }
}

private struct DecisionNarrativeColumn: View {
    let detail: DecisionDetail

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            if let summary = detail.decision.simpleSummary ?? detail.decision.summary,
               !summary.isEmpty {
                LottiDecisionSummary(text: summary)
            }
            if let officialText = detail.decision.officialText, !officialText.isEmpty {
                DecisionOfficialText(text: officialText)
            }
            if let imageID = detail.planImageID {
                DecisionPlanImage(documentID: imageID)
            }
            if !detail.subVotes.isEmpty {
                DecisionSubvotesCard(subVotes: detail.subVotes)
            }
            if let template = detail.template {
                DecisionTemplateStory(template: template, decisionTitle: detail.decision.title)
            }
        }
    }
}

private struct DecisionFactsColumn: View {
    let detail: DecisionDetail
    let preview: (CouncilAttachment) -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            DecisionGlanceCard(detail: detail)
            DecisionDocumentsCard(detail: detail, preview: preview)
        }
    }
}

private struct DecisionSubvotesCard: View {
    let subVotes: [DecisionSummary]

    var body: some View {
        VStack(alignment: .leading, spacing: 13) {
            MonoKicker("Änderungsanträge & Teilabstimmungen", trailing: "\(subVotes.count)")
            ForEach(subVotes) { subVote in
                VStack(alignment: .leading, spacing: 5) {
                    Text(subVote.title).font(RatsFont.body(14, weight: .semibold))
                    if let outcome = subVote.outcome { OutcomeBadge(outcome) }
                    if !subVote.factions.isEmpty {
                        Text(subVote.factions.joined(separator: " · "))
                            .font(RatsFont.mono(10)).foregroundStyle(RatsColor.muted)
                    }
                }
                if subVote.id != subVotes.last?.id { Divider() }
            }
        }
        .ratsCard()
    }
}

private struct DecisionTemplateStory: View {
    let template: CouncilTemplate
    let decisionTitle: String

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Label("Verlauf & Begründung", systemImage: "text.book.closed")
                .font(RatsFont.body(15, weight: .bold))
                .foregroundStyle(RatsColor.text)
            MonoKicker(template.kind ?? "Beschlussvorlage", trailing: template.number)
            if let title = template.title, title != decisionTitle {
                Text(title).font(RatsFont.body(16, weight: .semibold))
            }
            if let excerpt = template.excerpt, !excerpt.isEmpty {
                Text(excerpt).font(RatsFont.body(14)).foregroundStyle(RatsColor.bodyText).lineSpacing(4)
            }
            if let department = template.department {
                Label(department, systemImage: "building.2")
                    .font(RatsFont.body(12))
                    .foregroundStyle(RatsColor.secondary)
            }
            if let climate = template.climateCheck, !climate.isEmpty {
                DecisionDisclosureLine(symbol: "leaf", title: "Klima-Check", text: climate)
            }
            if let finances = template.financialCheck, !finances.isEmpty {
                DecisionDisclosureLine(symbol: "eurosign", title: "Was kostet das?", text: finances)
            }
        }
        .ratsCard()
    }
}

private struct DecisionDetailHeader: View {
    let detail: DecisionDetail

    var body: some View {
        let decision = detail.decision
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 8) {
                if let outcome = decision.outcome {
                    DecisionDetailOutcome(outcome: outcome)
                }
                Text(metadata)
                    .font(RatsFont.mono(9.5))
                    .foregroundStyle(RatsColor.muted)
                    .lineLimit(2)
                Spacer(minLength: 0)
                if let score = detail.importance?.score, score >= 55 {
                    Label("\(score)", systemImage: "flame.fill")
                        .font(RatsFont.body(10, weight: .bold))
                        .foregroundStyle(RatsColor.warning)
                        .padding(.horizontal, 7)
                        .padding(.vertical, 4)
                        .background(RatsColor.warning.opacity(0.12))
                        .clipShape(RoundedRectangle(cornerRadius: 7, style: .continuous))
                        .accessibilityLabel("Wichtigkeit \(score) von 100")
                }
            }

            Text(decision.title)
                .font(RatsFont.title(24))
                .foregroundStyle(RatsColor.text)
                .lineSpacing(1)
                .fixedSize(horizontal: false, vertical: true)

            if !tags.isEmpty {
                LazyVGrid(
                    columns: [GridItem(.adaptive(minimum: 145), spacing: 7)],
                    alignment: .leading,
                    spacing: 7
                ) {
                    ForEach(tags, id: \.self) { tag in
                        Label(tag, systemImage: "tag")
                            .font(RatsFont.body(10.5, weight: .semibold))
                            .foregroundStyle(RatsColor.primary)
                            .lineLimit(1)
                            .padding(.horizontal, 9)
                            .padding(.vertical, 6)
                            .background(RatsColor.primary.opacity(0.08))
                            .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
                    }
                }
            }
        }
        .padding(17)
        .background {
            LinearGradient(
                colors: [RatsColor.primary.opacity(0.10), RatsColor.card.opacity(0.94)],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
        }
        .clipShape(RoundedRectangle(cornerRadius: 22, style: .continuous))
        .overlay {
            RoundedRectangle(cornerRadius: 22, style: .continuous)
                .stroke(RatsColor.primary.opacity(0.18), lineWidth: 1)
        }
    }

    private var metadata: String {
        let decision = detail.decision
        let item = decision.itemNumber.map { "TOP \($0)" }
        let template = decision.templateNumber
        return [decision.committee.map(shortCouncilCommittee), RatsDate.short(decision.sessionDate), item, template]
            .compactMap { $0 }
            .joined(separator: " · ")
    }

    private var tags: [String] {
        let decision = detail.decision
        let field = decision.policyField.map {
            $0.replacingOccurrences(of: "_", with: " ").capitalized
        }
        return Array(([field].compactMap { $0 } + decision.policyTags + detail.entities.map(\.name)).prefix(7))
    }
}

private struct DecisionDetailOutcome: View {
    let outcome: String

    var body: some View {
        HStack(spacing: 5) {
            Circle().fill(color).frame(width: 7, height: 7)
            Text(label)
                .font(RatsFont.body(10.5, weight: .semibold))
                .foregroundStyle(RatsColor.bodyText)
        }
        .fixedSize()
    }

    private var label: String {
        switch outcome {
        case "angenommen": "Angenommen"
        case "abgelehnt": "Abgelehnt"
        case "vertagt": "Vertagt"
        case "zur_kenntnis": "Zur Kenntnis"
        default: outcome.replacingOccurrences(of: "_", with: " ").capitalized
        }
    }

    private var color: Color {
        switch outcome {
        case "angenommen": RatsColor.success
        case "abgelehnt": RatsColor.danger
        case "vertagt": RatsColor.warning
        default: RatsColor.primary
        }
    }
}

private struct LottiDecisionSummary: View {
    let text: String

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 11) {
                Lotti3DView(scene: .explain, animated: false)
                    .frame(width: 72, height: 64)
                VStack(alignment: .leading, spacing: 2) {
                    Text("LOTTI ERKLÄRT'S EINFACH")
                        .font(RatsFont.mono(9.5))
                        .tracking(1.1)
                        .foregroundStyle(RatsColor.signal)
                    Text("Das Wichtigste in Kürze")
                        .font(RatsFont.body(16, weight: .bold))
                        .foregroundStyle(RatsColor.text)
                }
            }
            Text(text)
                .font(RatsFont.body(15))
                .foregroundStyle(RatsColor.bodyText)
                .lineSpacing(5)
            Label("Automatische Kurzfassung – verbindlich ist der amtliche Wortlaut.", systemImage: "sparkles")
                .font(RatsFont.body(10.5))
                .foregroundStyle(RatsColor.muted)
        }
        .padding(17)
        .background(RatsColor.signal.opacity(0.065))
        .clipShape(RoundedRectangle(cornerRadius: 20, style: .continuous))
        .overlay {
            RoundedRectangle(cornerRadius: 20, style: .continuous)
                .stroke(RatsColor.signal.opacity(0.23), lineWidth: 1)
        }
    }
}

private struct DecisionOfficialText: View {
    let text: String
    @State private var isExpanded = true

    var body: some View {
        DisclosureGroup(isExpanded: $isExpanded) {
            Text(text)
                .font(RatsFont.body(13.5))
                .foregroundStyle(RatsColor.secondary)
                .lineSpacing(4)
                .padding(.top, 10)
        } label: {
            Label {
                VStack(alignment: .leading, spacing: 1) {
                    Text("Amtlicher Wortlaut")
                        .font(RatsFont.body(13.5, weight: .semibold))
                        .foregroundStyle(RatsColor.text)
                    Text("Aus dem Sitzungsprotokoll")
                        .font(RatsFont.body(10.5))
                        .foregroundStyle(RatsColor.muted)
                }
            } icon: {
                Image(systemName: "doc.text")
                    .foregroundStyle(RatsColor.primary)
            }
        }
        .tint(RatsColor.primary)
        .ratsCard()
    }
}

private struct DecisionGlanceCard: View {
    let detail: DecisionDetail

    var body: some View {
        let decision = detail.decision
        VStack(alignment: .leading, spacing: 0) {
            Label("Auf einen Blick", systemImage: "scope")
                .font(RatsFont.body(15, weight: .bold))
                .foregroundStyle(RatsColor.text)

            if let amount = decision.amountEUR {
                DecisionGlanceDivider()
                Text("BETRAG").font(RatsFont.mono(9.5)).foregroundStyle(RatsColor.muted)
                Text(formatDecisionAmount(amount))
                    .font(RatsFont.title(25))
                    .foregroundStyle(RatsColor.signal)
                Text("Im Beschlusstext genannt – automatisch erkannt")
                    .font(RatsFont.body(10)).foregroundStyle(RatsColor.muted)
            }

            if hasVote {
                DecisionGlanceDivider()
                Text("ABSTIMMUNG").font(RatsFont.mono(9.5)).foregroundStyle(RatsColor.muted)
                if let vote = decision.vote {
                    Text(vote.capitalized)
                        .font(RatsFont.body(16, weight: .bold))
                        .foregroundStyle(RatsColor.text)
                        .padding(.top, 3)
                }
                HStack(spacing: 7) {
                    if let noVotes = decision.noVotes { Pill("\(noVotes) dagegen", symbol: "hand.thumbsdown") }
                    if let abstentions = decision.abstentions { Pill("\(abstentions) enthalten", symbol: "minus") }
                }
                if let result = decision.rawResult, !result.isEmpty {
                    Text("„\(result.trimmingCharacters(in: .whitespacesAndNewlines))“")
                        .font(RatsFont.body(11))
                        .italic()
                        .foregroundStyle(RatsColor.secondary)
                        .padding(.top, 5)
                }
            }

            if !decision.parties.isEmpty {
                DecisionGlanceDivider()
                Text("ANTRAG VON").font(RatsFont.mono(9.5)).foregroundStyle(RatsColor.muted)
                DecisionPartyGrid(parties: decision.parties)
                    .padding(.top, 5)
            }

            if decision.deviation == "stark" {
                DecisionGlanceDivider()
                Label("Vom Vorschlag deutlich abgewichen", systemImage: "arrow.triangle.branch")
                    .font(RatsFont.body(12, weight: .semibold))
                    .foregroundStyle(RatsColor.primary)
            }

            if let importance = detail.importance, let score = importance.score {
                DecisionGlanceDivider()
                HStack {
                    Text("WICHTIGKEIT").font(RatsFont.mono(9.5)).foregroundStyle(RatsColor.muted)
                    Spacer()
                    Text("\(score) / 100").font(RatsFont.mono(10)).foregroundStyle(RatsColor.muted)
                }
                ProgressView(value: Double(score), total: 100)
                    .tint(score >= 70 ? RatsColor.warning : RatsColor.primary)
                    .padding(.vertical, 7)
                if let reason = importance.impactReason, !reason.isEmpty {
                    Text(reason)
                        .font(RatsFont.body(12.5))
                        .foregroundStyle(RatsColor.bodyText)
                        .lineSpacing(3)
                }
            }
        }
        .ratsCard()
    }

    private var hasVote: Bool {
        let decision = detail.decision
        return decision.vote != nil || decision.noVotes != nil || decision.abstentions != nil
    }
}

private struct DecisionGlanceDivider: View {
    var body: some View { Divider().padding(.vertical, 13) }
}

private struct DecisionParticipationBanner: View {
    let participation: CouncilParticipation
    let url: URL

    var body: some View {
        Link(destination: url) {
            HStack(alignment: .top, spacing: 11) {
                Image(systemName: "person.2.wave.2")
                    .font(.title3)
                    .foregroundStyle(RatsColor.primary)
                VStack(alignment: .leading, spacing: 4) {
                    Text("Hier kannst du dich beteiligen")
                        .font(RatsFont.body(14, weight: .bold))
                    Text(participation.title)
                        .font(RatsFont.body(13, weight: .medium))
                    Text([participation.step, participation.until.map { "bis \($0)" }].compactMap { $0 }.joined(separator: " · "))
                        .font(RatsFont.body(10.5))
                        .foregroundStyle(RatsColor.secondary)
                }
                Spacer(minLength: 4)
                Image(systemName: "arrow.up.right")
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(14)
            .background(RatsColor.primary.opacity(0.08))
            .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
        }
        .buttonStyle(.plain)
    }
}

private struct DecisionDisclosureLine: View {
    let symbol: String
    let title: String
    let text: String
    @State private var isExpanded = false

    var body: some View {
        DisclosureGroup(isExpanded: $isExpanded) {
            Text(text)
                .font(RatsFont.body(12))
                .foregroundStyle(RatsColor.secondary)
                .lineSpacing(3)
                .padding(.top, 6)
        } label: {
            Label(title, systemImage: symbol)
                .font(RatsFont.body(12.5, weight: .semibold))
                .foregroundStyle(RatsColor.text)
        }
        .tint(RatsColor.primary)
        .padding(.top, 5)
    }
}

private struct DecisionDocumentsCard: View {
    let detail: DecisionDetail
    let preview: (CouncilAttachment) -> Void

    var body: some View {
        if hasDocuments {
            VStack(alignment: .leading, spacing: 11) {
                Label("Dokumente & Anlagen", systemImage: "doc.on.doc")
                    .font(RatsFont.body(15, weight: .bold))
                    .foregroundStyle(RatsColor.text)

                if let raw = detail.templateURL, let url = URL(string: raw) {
                    DecisionDocumentLink(title: "Vorlage im Ratsinfosystem", symbol: "doc.text", url: url)
                }
                if let raw = detail.template?.documentURL, let url = URL(string: raw) {
                    DecisionDocumentLink(title: "Vorlage als PDF", symbol: "arrow.down.doc", url: url)
                }
                if let raw = detail.decision.protocolURL, let url = URL(string: raw) {
                    DecisionDocumentLink(title: "Sitzungsprotokoll", symbol: "text.document", url: url)
                }
                if let raw = detail.ratsinfoURL, let url = URL(string: raw) {
                    DecisionDocumentLink(title: "Amtliche Quelle", symbol: "building.columns", url: url)
                }

                if !detail.attachments.isEmpty {
                    Divider()
                    MonoKicker("Anlagen zum Beschluss", trailing: "\(detail.attachments.count)")
                    ForEach(detail.attachments) { attachment in
                        Button { preview(attachment) } label: {
                            HStack(spacing: 9) {
                                Image(systemName: attachment.isMotion == 1 ? "doc.badge.plus" : "doc.richtext")
                                    .foregroundStyle(RatsColor.primary)
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(attachment.label)
                                        .font(RatsFont.body(12.5, weight: .medium))
                                        .lineLimit(2)
                                        .multilineTextAlignment(.leading)
                                    if !attachment.applicants.isEmpty {
                                        Text(attachment.applicants.joined(separator: " · "))
                                            .font(RatsFont.mono(9.5))
                                            .foregroundStyle(RatsColor.muted)
                                    }
                                }
                                Spacer(minLength: 5)
                                Image(systemName: "eye").foregroundStyle(RatsColor.muted)
                            }
                            .padding(.vertical, 2)
                        }
                        .buttonStyle(.plain)
                    }
                }
            }
            .ratsCard()
        }
    }

    private var hasDocuments: Bool {
        detail.templateURL != nil || detail.template?.documentURL != nil
            || detail.decision.protocolURL != nil || detail.ratsinfoURL != nil
            || !detail.attachments.isEmpty
    }
}

private struct DecisionDocumentLink: View {
    let title: String
    let symbol: String
    let url: URL

    var body: some View {
        Link(destination: url) {
            HStack(spacing: 9) {
                Image(systemName: symbol).foregroundStyle(RatsColor.primary)
                Text(title).font(RatsFont.body(12.5, weight: .medium))
                Spacer()
                Image(systemName: "arrow.up.right").font(.caption)
            }
            .foregroundStyle(RatsColor.bodyText)
        }
    }
}

private struct DecisionAttendanceCard: View {
    let attendance: [CouncilAttendee]

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            MonoKicker("Anwesenheit", trailing: "\(attendance.count)")
            LazyVGrid(columns: [GridItem(.adaptive(minimum: 90), spacing: 7)], alignment: .leading, spacing: 7) {
                ForEach(Array(partyCounts.enumerated()), id: \.offset) { _, entry in
                    DecisionPartyChip(party: entry.party, suffix: "\(entry.count)")
                }
            }
        }
        .ratsCard()
    }

    private var partyCounts: [(party: String, count: Int)] {
        let excluded = Set(["verwaltung", "protokoll", "gast"])
        let counts = attendance.reduce(into: [String: Int]()) { result, attendee in
            guard !excluded.contains(attendee.role?.lowercased() ?? ""),
                  let party = attendee.party, !party.isEmpty else { return }
            result[party, default: 0] += 1
        }
        return counts.sorted { lhs, rhs in
            lhs.value == rhs.value ? lhs.key < rhs.key : lhs.value > rhs.value
        }.map { (party: $0.key, count: $0.value) }
    }
}

private struct DecisionPartyCard: View {
    let title: String
    let parties: [String]

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            MonoKicker(title, trailing: "\(parties.count)")
            DecisionPartyGrid(parties: parties)
        }
        .ratsCard()
    }
}

private struct DecisionPartyGrid: View {
    let parties: [String]

    var body: some View {
        LazyVGrid(columns: [GridItem(.adaptive(minimum: 82), spacing: 7)], alignment: .leading, spacing: 7) {
            ForEach(parties, id: \.self) { DecisionPartyChip(party: $0) }
        }
    }
}

private struct DecisionPartyChip: View {
    let party: String
    var suffix: String? = nil

    var body: some View {
        HStack(spacing: 6) {
            Circle().fill(color).frame(width: 8, height: 8)
            Text(suffix.map { "\(party) · \($0)" } ?? party)
                .font(RatsFont.body(10.5, weight: .semibold))
                .foregroundStyle(RatsColor.bodyText)
                .lineLimit(1)
        }
        .padding(.horizontal, 9)
        .padding(.vertical, 6)
        .background(color.opacity(0.11))
        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
    }

    private var color: Color {
        let normalized = party.lowercased()
        if normalized.contains("spd") { return Color(red: 0.82, green: 0.10, blue: 0.15) }
        if normalized.contains("cdu") { return RatsColor.bodyText }
        if normalized.contains("grün") { return Color(red: 0.18, green: 0.55, blue: 0.25) }
        if normalized.contains("fdp") { return Color(red: 0.93, green: 0.71, blue: 0.08) }
        if normalized.contains("link") { return Color(red: 0.72, green: 0.10, blue: 0.43) }
        if normalized.contains("volt") { return Color(red: 0.42, green: 0.17, blue: 0.62) }
        return RatsColor.primary
    }
}

private struct DecisionPlanImage: View {
    let documentID: Int

    var body: some View {
        if let url = URL(string: "https://ratslotse.de/api/council/plan-bild/\(documentID)") {
            Link(destination: url) {
                VStack(alignment: .leading, spacing: 0) {
                    AsyncImage(url: url) { phase in
                        switch phase {
                        case .success(let image):
                            image.resizable().scaledToFit()
                        case .failure:
                            RatsEmptyState(
                                title: "Planzeichnung nicht verfügbar",
                                message: "Das Bild kann gerade nicht geladen werden.",
                                symbol: "map"
                            )
                            .padding(14)
                        default:
                            RatsLoadingState(message: "Planzeichnung wird geladen …")
                                .frame(minHeight: 180)
                        }
                    }
                    Text("Planzeichnung aus der Vorlage – antippen für das vollständige Dokument.")
                        .font(RatsFont.body(10.5))
                        .foregroundStyle(RatsColor.muted)
                        .padding(12)
                }
            }
            .buttonStyle(.plain)
            .background(RatsColor.card)
            .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
            .overlay {
                RoundedRectangle(cornerRadius: 18, style: .continuous)
                    .stroke(RatsColor.border, lineWidth: 1)
            }
        }
    }
}

private func formatDecisionAmount(_ value: Double) -> String {
    if value >= 1_000_000 {
        let number = String(format: "%.1f", value / 1_000_000)
            .replacingOccurrences(of: ".", with: ",")
        return "\(number) Mio. €"
    }
    if value >= 1_000 { return "\(Int(value / 1_000)) Tsd. €" }
    return "\(Int(value)) €"
}

private func shortCouncilCommittee(_ name: String) -> String {
    name
        .replacingOccurrences(of: "Ausschuss für ", with: "")
        .replacingOccurrences(of: "Rat der Stadt", with: "Rat")
}

private extension CouncilConsultationStop {
    init(journey: CouncilJourneyStop) {
        self.init(
            date: journey.sessionDate, committee: journey.committee,
            itemNumber: journey.itemNumber, result: nil,
            sessionID: journey.sessionID, future: nil
        )
    }
}

private extension DecisionDetail {
    func replacing(follow: FollowStatus) -> DecisionDetail {
        DecisionDetail(
            decision: decision, attendance: attendance, entities: entities,
            presentParties: presentParties, ratsinfoURL: ratsinfoURL,
            similar: similar, subVotes: subVotes, templateJourney: templateJourney,
            consultations: consultations, templateURL: templateURL, template: template,
            attachments: attachments, participation: participation, importance: importance,
            follow: follow, planImageID: planImageID
        )
    }
}

private struct CouncilAttachmentPreview: View {
    let label: String
    let remoteURLString: String
    @Environment(\.dismiss) private var dismiss
    @State private var localURL: URL?
    @State private var error: String?

    init(attachment: CouncilAttachment) {
        label = attachment.label
        remoteURLString = attachment.url
    }

    init(agendaAttachment: AgendaAttachment) {
        label = agendaAttachment.label
        remoteURLString = agendaAttachment.url
    }

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                RatsSheetHeader(
                    label,
                    trailingTitle: "Fertig",
                    trailingAction: { dismiss() }
                )
                Group {
                    if let localURL {
                        QuickLookPreview(url: localURL)
                    } else if let error {
                        VStack(spacing: 14) {
                            RatsEmptyState(
                                title: "Dokument nicht verfügbar",
                                message: error,
                                symbol: "doc.badge.ellipsis"
                            )
                            if let url = URL(string: remoteURLString) {
                                Link(destination: url) {
                                    Label("Im Browser öffnen", systemImage: "arrow.up.right")
                                        .frame(maxWidth: .infinity)
                                }
                                .buttonStyle(SecondaryButtonStyle())
                            }
                        }
                        .frame(maxWidth: 520)
                        .padding(18)
                    } else {
                        RatsLoadingState(message: "Dokument wird geladen …")
                            .frame(maxWidth: 520)
                            .padding(18)
                    }
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .background(RatsColor.page)
            }
            .toolbar(.hidden, for: .navigationBar)
        }
        .task { await download() }
    }

    private func download() async {
        guard localURL == nil, let remoteURL = URL(string: remoteURLString) else {
            error = "Die Dokumentadresse ist ungültig."
            return
        }
        do {
            let (temporaryURL, response) = try await URLSession.shared.download(from: remoteURL)
            guard let http = response as? HTTPURLResponse, (200..<300).contains(http.statusCode) else {
                throw URLError(.badServerResponse)
            }
            let suggestedSuffix = response.suggestedFilename
                .map { URL(fileURLWithPath: $0).pathExtension }
                .flatMap { $0.isEmpty ? nil : $0 }
            let remoteSuffix = remoteURL.pathExtension.lowercased()
            let suffix = suggestedSuffix
                ?? (response.mimeType == "application/pdf" || remoteSuffix == "php" || remoteSuffix.isEmpty
                    ? "pdf"
                    : remoteSuffix)
            let destination = FileManager.default.temporaryDirectory
                .appending(path: "ratslotse-\(UUID().uuidString).\(suffix)")
            try FileManager.default.moveItem(at: temporaryURL, to: destination)
            localURL = destination
        } catch {
            self.error = "Die Anlage konnte nicht geladen werden. \(error.localizedDescription)"
        }
    }
}

private struct QuickLookPreview: UIViewControllerRepresentable {
    let url: URL

    func makeCoordinator() -> Coordinator { Coordinator(url: url) }

    func makeUIViewController(context: Context) -> QLPreviewController {
        let controller = QLPreviewController()
        controller.dataSource = context.coordinator
        return controller
    }

    func updateUIViewController(_ uiViewController: QLPreviewController, context: Context) {}

    final class Coordinator: NSObject, QLPreviewControllerDataSource {
        let url: URL
        init(url: URL) { self.url = url }
        func numberOfPreviewItems(in controller: QLPreviewController) -> Int { 1 }
        func previewController(_ controller: QLPreviewController, previewItemAt index: Int) -> QLPreviewItem {
            url as NSURL
        }
    }
}

private enum SavedCouncilFilter: String, CaseIterable, Identifiable {
    case all = "Alle"
    case open = "Offen"
    case decided = "Entschieden"
    case sessions = "Sitzungen"

    var id: String { rawValue }
}

struct SavedCouncilView: View {
    let model: AppModel
    @State private var bookmarks: [BookmarkEntry] = []
    @State private var follows: [FollowEntry] = []
    @State private var search = ""
    @State private var filter: SavedCouncilFilter = .all
    @State private var workingBookmarks: Set<Int> = []
    @State private var isLoading = true
    @State private var error: String?

    var body: some View {
        ScrollView {
            LazyVStack(alignment: .leading, spacing: 14) {
                HStack(alignment: .top, spacing: 12) {
                    VStack(alignment: .leading, spacing: 5) {
                        MonoKicker("Deine Ratsakte")
                        Text("Gespeichert")
                            .font(RatsFont.title(28))
                        Text("Beschlüsse und Vorlagen, die du später wiederfinden möchtest.")
                            .font(RatsFont.body(13))
                            .foregroundStyle(RatsColor.secondary)
                    }
                    Spacer()
                    RatsGlyphView(glyph: .saved, color: RatsColor.primaryText, lineWidth: 1.8)
                        .frame(width: 20, height: 20)
                        .frame(width: 44, height: 44)
                        .background(RatsColor.primary)
                        .clipShape(RoundedRectangle(cornerRadius: 13, style: .continuous))
                }

                if isLoading {
                    RatsLoadingState(message: "Merkliste wird geladen …")
                } else if bookmarks.isEmpty && follows.isEmpty && error == nil {
                    RatsEmptyState(
                        title: "Noch nichts gespeichert",
                        message: "Gemerkte Beschlüsse und verfolgte Vorlagen erscheinen hier.",
                        symbol: "bookmark"
                    )
                }

                if !bookmarks.isEmpty {
                    savedControls
                    if filteredBookmarks.isEmpty {
                        RatsEmptyState(
                            title: "Nichts Passendes gespeichert",
                            message: "Ändere den Filter oder suche mit einem anderen Begriff.",
                            symbol: "magnifyingglass"
                        )
                    } else {
                        MonoKicker("Merkliste", trailing: "\(filteredBookmarks.count) von \(bookmarks.count)")
                        ForEach(filteredBookmarks) { bookmark in
                            savedBookmarkCard(bookmark)
                        }
                    }
                }

                if !follows.isEmpty && filter == .all && search.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                    MonoKicker("Verfolgte Vorgänge", trailing: "\(follows.count)")
                    ForEach(follows) { follow in
                        HStack(alignment: .top, spacing: 10) {
                            VStack(alignment: .leading, spacing: 7) {
                                Text(follow.title.isEmpty ? follow.templateNumber : follow.title)
                                    .font(RatsFont.body(15, weight: .semibold))
                                Text("\(follow.templateNumber) · \(follow.stationCount) Stationen")
                                    .font(RatsFont.mono(10)).foregroundStyle(RatsColor.muted)
                                if let next = follow.next {
                                    Text("Als Nächstes: \([next.committee, RatsDate.short(next.date)].compactMap { $0 }.joined(separator: " · "))")
                                        .font(RatsFont.body(12)).foregroundStyle(RatsColor.secondary)
                                }
                                if let url = URL(string: follow.url) {
                                    Link(destination: url) {
                                        Label("Vorlage im Ratsinfosystem", systemImage: "arrow.up.right")
                                            .font(RatsFont.body(12, weight: .semibold))
                                    }
                                }
                            }
                            .frame(maxWidth: .infinity, alignment: .leading)
                            Menu {
                                Button("Nicht mehr folgen", systemImage: "bell.slash", role: .destructive) {
                                    removeFollow(follow)
                                }
                            } label: {
                                Image(systemName: "ellipsis")
                                    .foregroundStyle(RatsColor.secondary)
                                    .frame(width: 32, height: 32)
                            }
                            .accessibilityLabel("Vorgang verwalten")
                        }
                        .ratsCard()
                    }
                }
                if let error { ErrorCard(message: error) { Task { await load() } } }
            }
            .frame(maxWidth: 760, alignment: .leading)
            .padding(18)
        }
        .background(RatsColor.page)
        .navigationTitle("Gespeichert")
        .navigationBarTitleDisplayMode(.inline)
        .refreshable { await load() }
        .task { await load() }
    }

    private var savedControls: some View {
        VStack(spacing: 11) {
            HStack(spacing: 9) {
                Image(systemName: "magnifyingglass")
                    .foregroundStyle(RatsColor.muted)
                TextField("Merkliste durchsuchen …", text: $search)
                    .font(RatsFont.body(13))
                    .textFieldStyle(.plain)
                    .submitLabel(.search)
                if !search.isEmpty {
                    Button { search = "" } label: {
                        Image(systemName: "xmark.circle.fill")
                            .foregroundStyle(RatsColor.muted)
                    }
                    .buttonStyle(.plain)
                    .accessibilityLabel("Suche leeren")
                }
            }
            .padding(.horizontal, 12)
            .frame(minHeight: 42)
            .background(RatsColor.stage)
            .overlay(RoundedRectangle(cornerRadius: 12, style: .continuous).stroke(RatsColor.border))
            .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))

            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 7) {
                    ForEach(SavedCouncilFilter.allCases) { item in
                        Button { filter = item } label: {
                            Text("\(item.rawValue)  \(filterCount(item))")
                                .font(RatsFont.body(11, weight: .semibold))
                                .foregroundStyle(filter == item ? RatsColor.primaryText : RatsColor.bodyText)
                                .padding(.horizontal, 11)
                                .frame(height: 32)
                                .background(filter == item ? RatsColor.primary : RatsColor.card)
                                .overlay(Capsule().stroke(filter == item ? Color.clear : RatsColor.border))
                                .clipShape(Capsule())
                        }
                        .buttonStyle(.plain)
                    }
                }
            }
        }
        .padding(12)
        .background(RatsColor.card)
        .overlay(RoundedRectangle(cornerRadius: 16, style: .continuous).stroke(RatsColor.border))
        .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
    }

    private func savedBookmarkCard(_ bookmark: BookmarkEntry) -> some View {
        VStack(spacing: 0) {
            HStack(alignment: .top, spacing: 10) {
                savedDestination(bookmark)
                Menu {
                    Button("Aus Merkliste entfernen", systemImage: "trash", role: .destructive) {
                        removeBookmark(bookmark)
                    }
                } label: {
                    Image(systemName: "ellipsis")
                        .foregroundStyle(RatsColor.secondary)
                        .frame(width: 32, height: 32)
                }
                .accessibilityLabel("Eintrag verwalten")
            }
            .padding(14)

            if canNotify(bookmark) {
                Divider().overlay(RatsColor.separator)
                HStack(spacing: 10) {
                    Image(systemName: "bell")
                        .foregroundStyle(RatsColor.primary)
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Beim Ergebnis benachrichtigen")
                            .font(RatsFont.body(12.5, weight: .semibold))
                        Text("Sobald das öffentliche Protokoll verarbeitet ist.")
                            .font(RatsFont.body(10))
                            .foregroundStyle(RatsColor.secondary)
                    }
                    Spacer(minLength: 4)
                    Toggle("", isOn: Binding(
                        get: { bookmark.notifyResult },
                        set: { setNotification(bookmark, enabled: $0) }
                    ))
                    .labelsHidden()
                    .disabled(workingBookmarks.contains(bookmark.id))
                    .accessibilityLabel("Beim Ergebnis benachrichtigen")
                }
                .padding(.horizontal, 14)
                .padding(.vertical, 11)
                .background(RatsColor.stage.opacity(0.75))
            }
        }
        .background(RatsColor.card)
        .overlay(RoundedRectangle(cornerRadius: RatsRadius.card, style: .continuous).stroke(RatsColor.border))
        .clipShape(RoundedRectangle(cornerRadius: RatsRadius.card, style: .continuous))
    }

    @ViewBuilder
    private func savedDestination(_ bookmark: BookmarkEntry) -> some View {
        if let decision = bookmark.decision {
            NavigationLink(value: AppRoute.decision(id: decision.id)) { savedLabel(bookmark) }
        } else if let sessionID = bookmark.sessionID {
            NavigationLink(value: AppRoute.sessions(ksinr: sessionID, tops: bookmark.itemNumber.map { [$0] } ?? [])) {
                savedLabel(bookmark)
            }
        } else if let url = URL(string: bookmark.url) {
            Link(destination: url) { savedLabel(bookmark) }
        } else {
            savedLabel(bookmark)
        }
    }

    private func savedLabel(_ bookmark: BookmarkEntry) -> some View {
        VStack(alignment: .leading, spacing: 5) {
            Text(bookmark.title).font(RatsFont.body(15, weight: .semibold))
            Text(savedSubtitle(bookmark)).font(RatsFont.body(11)).foregroundStyle(RatsColor.secondary)
            if let preview = bookmark.decision?.simpleSummary ?? bookmark.decision?.summary,
               !preview.isEmpty {
                Text(preview)
                    .font(RatsFont.body(12))
                    .foregroundStyle(RatsColor.secondary)
                    .lineLimit(3)
                    .padding(.top, 2)
            }
            Pill(savedStateLabel(bookmark), symbol: bookmark.decision == nil ? "clock" : "checkmark")
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .contentShape(Rectangle())
    }

    private var filteredBookmarks: [BookmarkEntry] {
        let needle = search.trimmingCharacters(in: .whitespacesAndNewlines).localizedLowercase
        return bookmarks.filter { bookmark in
            if filter != .all && category(bookmark) != filter { return false }
            guard !needle.isEmpty else { return true }
            let haystack = [
                bookmark.title, bookmark.subtitle, bookmark.itemNumber,
                bookmark.session?.committee, bookmark.session?.location,
                bookmark.decision?.simpleSummary, bookmark.decision?.summary,
            ].compactMap { $0 }.joined(separator: " ").localizedLowercase
            return haystack.contains(needle)
        }
    }

    private func category(_ bookmark: BookmarkEntry) -> SavedCouncilFilter? {
        if bookmark.kind == "session" { return .sessions }
        if bookmark.decision != nil { return .decided }
        if bookmark.kind == "agenda_item" { return .open }
        return nil
    }

    private func filterCount(_ item: SavedCouncilFilter) -> Int {
        guard item != .all else { return bookmarks.count }
        return bookmarks.filter { category($0) == item }.count
    }

    private func canNotify(_ bookmark: BookmarkEntry) -> Bool {
        bookmark.kind == "agenda_item" && bookmark.decision == nil && bookmark.state != "group"
    }

    private func savedSubtitle(_ bookmark: BookmarkEntry) -> String {
        if let decision = bookmark.decision {
            return [decision.committee, RatsDate.short(decision.sessionDate), decision.itemNumber]
                .compactMap { $0 }
                .joined(separator: " · ")
        }
        if let session = bookmark.session {
            return [session.committee, RatsDate.short(session.sessionDate), bookmark.itemNumber]
                .compactMap { $0 }
                .joined(separator: " · ")
        }
        return bookmark.subtitle
    }

    private func savedStateLabel(_ bookmark: BookmarkEntry) -> String {
        if let outcome = bookmark.decision?.outcome { return outcome }
        switch bookmark.state {
        case "upcoming", "open": return "bevorstehend"
        case "decided": return "entschieden"
        case "group": return "Sitzung"
        default: return bookmark.state
        }
    }

    private func load() async {
#if DEBUG
        if ProcessInfo.processInfo.environment["RATSLOTSE_DEBUG_SAVED_FIXTURE"] == "1" {
            installDebugSavedFixture()
            return
        }
#endif
        guard model.user != nil else {
            isLoading = false
            error = "Melde dich an, um deine Merkliste zu sehen."
            return
        }
        isLoading = true
        defer { isLoading = false }
        do {
            async let bookmarkRequest: BookmarkPage = model.api.get("/api/bookmarks")
            async let followRequest: FollowPage = model.api.get("/api/council/follows")
            let responses = try await (bookmarkRequest, followRequest)
            bookmarks = responses.0.bookmarks
            follows = responses.1.follows
            error = nil
        } catch { self.error = error.localizedDescription }
    }

#if DEBUG
    private func installDebugSavedFixture() {
        let data = Data(#"""
        {
          "bookmarks": [
            {
              "id": 701,
              "kind": "agenda_item",
              "title": "Sichere Querung an der Cloppenburger Straße",
              "subtitle": "Verkehrsausschuss · TOP 6",
              "state": "upcoming",
              "url": "https://ratsinfo.oldenburg.de/",
              "ksinr": 8801,
              "item_number": "Ö 6",
              "notify_result": true,
              "session": {
                "ksinr": 8801,
                "committee": "Verkehrsausschuss",
                "session_date": "2026-09-03",
                "session_time": "17:00",
                "location": "Alte Fleiwa",
                "title": "Verkehrsausschuss",
                "n_items": 8
              }
            },
            {
              "id": 702,
              "kind": "decision",
              "title": "Neue Busspuren für Oldenburg",
              "subtitle": "Rat · 26. Aug. 2026",
              "state": "decided",
              "url": "https://ratsinfo.oldenburg.de/",
              "notify_result": false,
              "decision": {
                "id": 9201,
                "title": "Neue Busspuren für Oldenburg",
                "simple_summary": "Der Rat schafft die Grundlage für schnellere und verlässlichere Busverbindungen.",
                "committee": "Rat",
                "session_date": "2026-08-26",
                "outcome": "angenommen",
                "item_number": "Ö 10"
              }
            },
            {
              "id": 703,
              "kind": "session",
              "title": "Stadtplanung & Bauen",
              "subtitle": "31. Aug. · 18:00 · 9 TOPs",
              "state": "upcoming",
              "url": "https://ratsinfo.oldenburg.de/",
              "ksinr": 8802,
              "notify_result": false,
              "session": {
                "ksinr": 8802,
                "committee": "Stadtplanung & Bauen",
                "session_date": "2026-08-31",
                "session_time": "18:00",
                "location": "Alte Fleiwa",
                "title": "Stadtplanung & Bauen",
                "n_items": 9
              }
            }
          ]
        }
        """#.utf8)
        bookmarks = (try? JSONDecoder().decode(BookmarkPage.self, from: data).bookmarks) ?? []
        follows = []
        error = nil
        isLoading = false
    }
#endif

    private func removeBookmark(_ bookmark: BookmarkEntry) {
        Task {
            do {
                try await model.api.sendVoid("/api/bookmarks/\(bookmark.id)", method: .delete)
                bookmarks.removeAll { $0.id == bookmark.id }
            } catch { self.error = error.localizedDescription }
        }
    }

    private func removeFollow(_ follow: FollowEntry) {
        Task {
            do {
                let _: FollowStatus = try await model.api.sendWithoutBody(
                    "/api/council/vorlage/\(follow.templateID)/follow", method: .delete
                )
                follows.removeAll { $0.id == follow.id }
            } catch { self.error = error.localizedDescription }
        }
    }

    private func setNotification(_ bookmark: BookmarkEntry, enabled: Bool) {
        guard workingBookmarks.insert(bookmark.id).inserted else { return }
        struct Body: Codable, Sendable { let notify_result: Bool }
        Task {
            defer { workingBookmarks.remove(bookmark.id) }
            do {
                let _: JSONValue = try await model.api.send(
                    "/api/bookmarks/\(bookmark.id)/notification",
                    method: .put,
                    body: Body(notify_result: enabled)
                )
                let page: BookmarkPage = try await model.api.get("/api/bookmarks")
                bookmarks = page.bookmarks
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
    @State private var isLoading = true

    var body: some View {
        ScrollView {
            LazyVStack(alignment: .leading, spacing: 12) {
                HStack(alignment: .top) {
                    VStack(alignment: .leading, spacing: 5) {
                        MonoKicker("Termine im Rathaus")
                        Text("Sitzungen")
                            .font(RatsFont.title(28))
                        Text("Tagesordnungen, Orte und Zeiten auf einen Blick.")
                            .font(RatsFont.body(13))
                            .foregroundStyle(RatsColor.secondary)
                    }
                    Spacer()
                    RatsGlyphView(glyph: .calendar, color: RatsColor.primaryText, lineWidth: 1.8)
                        .frame(width: 20, height: 20)
                        .frame(width: 44, height: 44)
                        .background(RatsColor.primary)
                        .clipShape(RoundedRectangle(cornerRadius: 13, style: .continuous))
                }
                if isLoading {
                    RatsLoadingState(message: "Sitzungen werden geladen …")
                } else if sessions.isEmpty && error == nil {
                    RatsEmptyState(
                        title: "Keine Sitzungen gefunden",
                        message: "Sobald neue Termine vorliegen, erscheinen sie an dieser Stelle.",
                        symbol: "calendar.badge.clock"
                    )
                } else {
                    ForEach(Array(sessions.enumerated()), id: \.element.id) { index, session in
                        if isFirstSessionInYear(at: index) {
                            SessionYearDivider(year: sessionYear(session.sessionDate))
                        }
                        if let ksinr = session.ksinr {
                            NavigationLink(value: AppRoute.sessions(ksinr: ksinr, tops: [])) {
                                SessionRow(session: session).ratsCard()
                            }
                            .buttonStyle(.plain)
                        } else {
                            SessionRow(session: session).ratsCard()
                        }
                    }
                }
                if let error { ErrorCard(message: error) { Task { await loadSessions() } } }
            }
            .frame(maxWidth: 760, alignment: .leading)
            .padding(18)
        }
        .background(RatsColor.page)
        .navigationTitle("Sitzungen")
        .navigationBarTitleDisplayMode(.inline)
        .task { await loadSessions() }
    }

    private func loadSessions() async {
        isLoading = true
        defer { isLoading = false }
        do {
            let page: SessionPage = try await model.api.get(
                "/api/council/sessions",
                query: [
                    .init(name: "scope", value: "upcoming"),
                    .init(name: "limit", value: "100"),
                ]
            )
            sessions = page.sessions
            error = nil
        } catch { self.error = error.localizedDescription }
    }

    private func isFirstSessionInYear(at index: Int) -> Bool {
        guard sessions.indices.contains(index) else { return false }
        return index == 0 || sessionYear(sessions[index - 1].sessionDate) != sessionYear(sessions[index].sessionDate)
    }
}

private func sessionYear(_ raw: String) -> String {
    guard raw.count >= 4 else { return "–" }
    return String(raw.prefix(4))
}

private struct SessionDetailView: View {
    let model: AppModel
    let ksinr: Int
    let highlightedTops: Set<String>
    @State private var detail: SessionDetail?
    @State private var error: String?
    @State private var calendarDraft: CalendarDraft?
    @State private var previewAttachment: AgendaAttachment?

    var body: some View {
        ScrollViewReader { proxy in
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    if let detail {
                        VStack(alignment: .leading, spacing: 9) {
                            MonoKicker([RatsDate.weekday(detail.sessionDate), detail.sessionTime].compactMap { $0 }.joined(separator: " · "))
                            Text(detail.committee).font(RatsFont.title(28))
                            if let location = detail.location { Label(location, systemImage: "mappin.and.ellipse") }
                            Button { prepareCalendar(detail) } label: {
                                Label("In Kalender", systemImage: "calendar.badge.plus")
                            }
                            .buttonStyle(SecondaryButtonStyle())
                        }
                        agenda(detail)
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
        .task {
            await load()
            await model.reportBadgeEvent("sitzung")
        }
        .sheet(item: $calendarDraft) { draft in CalendarEditSheet(draft: draft, isPresented: Binding(
            get: { calendarDraft != nil }, set: { if !$0 { calendarDraft = nil } }
        )) }
        .sheet(item: $previewAttachment) { attachment in
            CouncilAttachmentPreview(agendaAttachment: attachment)
        }
    }

    private func load() async {
        do { detail = try await model.api.get("/api/council/session/\(ksinr)") }
        catch { self.error = error.localizedDescription }
    }

    private func agenda(_ detail: SessionDetail) -> some View {
        let publicItems = detail.agendaItems.filter { $0.isPublic != 0 }
        return VStack(alignment: .leading, spacing: 0) {
            MonoKicker("Tagesordnung", trailing: "\(publicItems.count) öffentlich")
                .padding(.bottom, 7)

            ForEach(Array(publicItems.enumerated()), id: \.element.id) { index, item in
                SessionAgendaRow(
                    item: item,
                    isHighlighted: highlightedTops.contains(item.itemNumber),
                    openAttachment: { previewAttachment = $0 }
                )
                    .id(item.itemNumber)

                if index < publicItems.count - 1 {
                    Divider()
                        .overlay(RatsColor.separator)
                        .padding(.leading, 52)
                }
            }
        }
        .ratsCard()
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

private struct SessionAgendaRow: View {
    let item: AgendaItem
    let isHighlighted: Bool
    let openAttachment: (AgendaAttachment) -> Void

    var body: some View {
        HStack(alignment: .firstTextBaseline, spacing: 12) {
            Text(item.itemNumber)
                .font(RatsFont.mono(9, weight: .semibold))
                .tracking(0.4)
                .foregroundStyle(isHighlighted ? RatsColor.primaryText : RatsColor.primary)
                .frame(minWidth: 31)
                .padding(.horizontal, 6)
                .padding(.vertical, 5)
                .background(isHighlighted ? RatsColor.primary : RatsColor.primary.opacity(0.08))
                .clipShape(RoundedRectangle(cornerRadius: 6, style: .continuous))
                .fixedSize()

            VStack(alignment: .leading, spacing: 5) {
                Text(item.title)
                    .font(RatsFont.body(15, weight: .semibold))
                    .foregroundStyle(RatsColor.text)
                    .fixedSize(horizontal: false, vertical: true)
                if let summary = item.summary, !summary.isEmpty {
                    Text(summary)
                        .font(RatsFont.body(13))
                        .foregroundStyle(RatsColor.secondary)
                        .fixedSize(horizontal: false, vertical: true)
                }
                if !item.attachments.isEmpty {
                    VStack(alignment: .leading, spacing: 5) {
                        ForEach(item.attachments) { attachment in
                            Button { openAttachment(attachment) } label: {
                                HStack(spacing: 6) {
                                    Image(systemName: "paperclip")
                                        .font(.system(size: 10, weight: .semibold))
                                    Text(attachment.label)
                                        .font(RatsFont.body(11, weight: .semibold))
                                        .lineLimit(1)
                                        .truncationMode(.tail)
                                    Image(systemName: "arrow.up.right")
                                        .font(.system(size: 8, weight: .bold))
                                }
                                .foregroundStyle(RatsColor.primary)
                                .frame(maxWidth: .infinity, alignment: .leading)
                                .contentShape(Rectangle())
                            }
                            .buttonStyle(.plain)
                            .accessibilityLabel("Anlage öffnen: \(attachment.label)")
                        }
                    }
                    .padding(.top, 3)
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .padding(.horizontal, isHighlighted ? 10 : 0)
        .padding(.vertical, 14)
        .background(isHighlighted ? RatsColor.primary.opacity(0.07) : Color.clear)
        .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
        .accessibilityElement(children: .combine)
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
