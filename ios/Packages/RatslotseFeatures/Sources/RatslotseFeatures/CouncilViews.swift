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
    @State private var includeSubvotes = false
    @State private var hasDateFrom = false
    @State private var hasDateTo = false
    @State private var dateFrom = Date()
    @State private var dateTo = Date()
    @State private var page = 0
    @State private var committees: [String] = []
    @State private var fields: [PolicyFieldOption] = []
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
                if model.councilSection != .map {
                    Button { showsFilters = true } label: {
                        ZStack(alignment: .topTrailing) {
                            RatsGlyphView(
                                glyph: .filter,
                                color: activeFilterCount > 0 ? RatsColor.primary : RatsColor.bodyText
                            )
                                .frame(width: 19, height: 19)
                                .frame(width: 40, height: 40)
                                .background(RatsColor.card)
                                .overlay(Circle().stroke(RatsColor.border))
                                .clipShape(Circle())
                            if activeFilterCount > 0 {
                                Text("\(activeFilterCount)")
                                    .font(RatsFont.body(9, weight: .bold))
                                    .foregroundStyle(.white)
                                    .frame(width: 17, height: 17)
                                    .background(RatsColor.signal)
                                    .clipShape(Circle())
                            }
                        }
                    }
                    .accessibilityLabel("Filter und Sortierung")
                }
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

            HStack(spacing: 9) {
                RatsGlyphView(glyph: .search, color: RatsColor.secondary)
                    .frame(width: 18, height: 18)
                TextField(searchPrompt, text: $query)
                    .font(RatsFont.body(14))
                    .submitLabel(.search)
                    .onSubmit {
                        if model.councilSection != .map { page = 0; Task { await load() } }
                    }
                if !query.isEmpty {
                    Button { query = ""; if model.councilSection != .map { Task { await load() } } } label: {
                        Text("×")
                            .font(RatsFont.body(20, weight: .medium))
                            .foregroundStyle(RatsColor.muted)
                    }
                    .accessibilityLabel("Suche leeren")
                }
            }
            .padding(.horizontal, 13)
            .frame(height: 44)
            .background(RatsColor.card)
            .overlay(RoundedRectangle(cornerRadius: 12).stroke(RatsColor.border))
            .clipShape(RoundedRectangle(cornerRadius: 12))
            .padding(.horizontal, 18)
            .padding(.top, horizontalSizeClass == .regular ? 12 : 0)
            .padding(.bottom, 10)

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
                    } else if model.councilSection == .sessions {
                        ForEach(sessions) { session in
                            Button {
                                if let id = session.ksinr { model.navigation.append(.sessions(ksinr: id, tops: [])) }
                            } label: {
                                SessionRow(session: session).ratsCard()
                            }
                            .buttonStyle(.plain)
                            .disabled(session.ksinr == nil)
                        }
                    } else {
                        NativeCouncilMap(points: filteredMapPoints) { point in
                            openMapPoint(point)
                        }
                        .frame(minHeight: 440, idealHeight: 560)
                        .clipShape(RoundedRectangle(cornerRadius: RatsRadius.card))
                        .overlay(RoundedRectangle(cornerRadius: RatsRadius.card).stroke(RatsColor.border))
                        Text("Nahe Punkte werden gebündelt. Tippe eine Zahl zum Heranzoomen oder einen Punkt für Details.")
                            .font(RatsFont.body(11)).foregroundStyle(RatsColor.muted)
                    }
                    if total > pageSize && model.councilSection != .map {
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

    private var activeFilterCount: Int {
        [committee, policyField, party, district].filter { !$0.isEmpty }.count
            + (location.isEmpty ? 0 : 1)
            + (hasDateFrom ? 1 : 0) + (hasDateTo ? 1 : 0) + (includeSubvotes ? 1 : 0)
    }

    private var searchPrompt: String {
        switch model.councilSection {
        case .decisions: "Beschlüsse durchsuchen"
        case .sessions: "Sitzungen durchsuchen"
        case .map: "Orte und Themen auf der Karte"
        }
    }

    private var filteredMapPoints: [CouncilMapPoint] {
        let needle = query.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !needle.isEmpty else { return mapPoints }
        return mapPoints.filter { $0.name.localizedCaseInsensitiveContains(needle) }
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

    private func load() async {
        isLoading = true
        error = nil
        defer { isLoading = false }
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
                let page: SessionPage = try await model.api.get(
                    "/api/council/sessions",
                    query: [
                        .init(name: "q", value: query),
                        .init(name: "committee", value: committee),
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
        async let districtRequest: DistrictOptions = model.api.get("/api/council/districts")
        if let response = try? await committeeRequest { committees = response.committees }
        if let response = try? await fieldRequest { fields = response.fields }
        if let response = try? await districtRequest { districts = response.districts }
    }

    private static let apiDate: DateFormatter = {
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.dateFormat = "yyyy-MM-dd"
        return formatter
    }()
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
                            RatsLabeledField(label: "Antragsteller-Partei", hint: "optional") {
                                TextField("z. B. SPD", text: $party)
                                    .textInputAutocapitalization(.characters)
                                    .textFieldStyle(.plain)
                            }
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
            MonoKicker(RatsDate.weekday(session.sessionDate) ?? session.sessionDate, trailing: session.sessionTime)
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
    @State private var bookmarkID: Int?
    @State private var isWorking = false
    @State private var previewAttachment: CouncilAttachment?

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                if let detail {
                    let decision = detail.decision
                    VStack(alignment: .leading, spacing: 10) {
                        MonoKicker(
                            [decision.committee, RatsDate.short(decision.sessionDate)].compactMap { $0 }.joined(separator: " · ")
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

                    if let importance = detail.importance,
                       let reason = importance.impactReason, !reason.isEmpty {
                        VStack(alignment: .leading, spacing: 8) {
                            MonoKicker("Warum das wichtig ist", trailing: importance.score.map { "\($0) / 100" })
                            Text(reason).font(RatsFont.body(14)).foregroundStyle(RatsColor.bodyText)
                        }
                        .ratsCard()
                    }

                    if decision.vote != nil || decision.noVotes != nil || decision.abstentions != nil || !decision.factions.isEmpty {
                        VStack(alignment: .leading, spacing: 10) {
                            MonoKicker("Abstimmung")
                            if let vote = decision.vote { Text(vote).font(RatsFont.body(15, weight: .semibold)) }
                            HStack(spacing: 8) {
                                if let noVotes = decision.noVotes { Pill("\(noVotes) Gegenstimmen", symbol: "hand.thumbsdown") }
                                if let abstentions = decision.abstentions { Pill("\(abstentions) Enthaltungen", symbol: "minus") }
                            }
                            if !decision.factions.isEmpty {
                                Text("Eingebracht von").font(RatsFont.mono(10)).foregroundStyle(RatsColor.muted)
                                FlexibleChips(items: decision.factions)
                            }
                        }
                        .ratsCard()
                    }

                    if !detail.subVotes.isEmpty {
                        VStack(alignment: .leading, spacing: 13) {
                            MonoKicker("Änderungsanträge & Teilabstimmungen", trailing: "\(detail.subVotes.count)")
                            ForEach(detail.subVotes) { subVote in
                                VStack(alignment: .leading, spacing: 5) {
                                    Text(subVote.title).font(RatsFont.body(14, weight: .semibold))
                                    if let outcome = subVote.outcome { OutcomeBadge(outcome) }
                                    if !subVote.factions.isEmpty {
                                        Text(subVote.factions.joined(separator: " · "))
                                            .font(RatsFont.mono(10)).foregroundStyle(RatsColor.muted)
                                    }
                                }
                                if subVote.id != detail.subVotes.last?.id { Divider() }
                            }
                        }
                        .ratsCard()
                    }

                    if let participation = detail.participation,
                       let url = URL(string: participation.url) {
                        VStack(alignment: .leading, spacing: 9) {
                            MonoKicker("Du kannst dich beteiligen", trailing: participation.status)
                            Text(participation.title).font(RatsFont.body(16, weight: .semibold))
                            if let until = participation.until { Text("Frist: \(until)").font(RatsFont.body(12)).foregroundStyle(RatsColor.secondary) }
                            Link(destination: url) { Label("Beteiligung öffnen", systemImage: "arrow.up.right.square") }
                                .font(RatsFont.body(13, weight: .semibold))
                        }
                        .ratsCard()
                    }

                    if let template = detail.template {
                        VStack(alignment: .leading, spacing: 10) {
                            MonoKicker(template.kind ?? "Beschlussvorlage", trailing: template.number)
                            if let title = template.title, title != decision.title {
                                Text(title).font(RatsFont.body(16, weight: .semibold))
                            }
                            if let excerpt = template.excerpt, !excerpt.isEmpty {
                                Text(excerpt).font(RatsFont.body(14)).foregroundStyle(RatsColor.bodyText).lineSpacing(4)
                            }
                            if let department = template.department { Label(department, systemImage: "building.2").font(RatsFont.body(12)) }
                            if let raw = template.documentURL, let url = URL(string: raw) {
                                Link(destination: url) { Label("Vorlage öffnen", systemImage: "doc.text") }
                            }
                        }
                        .ratsCard()
                    }

                    if !detail.attachments.isEmpty {
                        VStack(alignment: .leading, spacing: 12) {
                            MonoKicker("Anlagen & Anträge", trailing: "\(detail.attachments.count)")
                            ForEach(detail.attachments) { attachment in
                                Button { previewAttachment = attachment } label: {
                                    HStack(alignment: .top, spacing: 10) {
                                        Image(systemName: attachment.isMotion == 1 ? "doc.badge.plus" : "doc.richtext")
                                            .foregroundStyle(RatsColor.primary)
                                        VStack(alignment: .leading, spacing: 3) {
                                            Text(attachment.label).font(RatsFont.body(13, weight: .semibold)).multilineTextAlignment(.leading)
                                            if !attachment.applicants.isEmpty {
                                                Text(attachment.applicants.joined(separator: " · "))
                                                    .font(RatsFont.mono(10)).foregroundStyle(RatsColor.muted)
                                            }
                                        }
                                        Spacer()
                                        Image(systemName: "eye")
                                    }
                                }
                                .buttonStyle(.plain)
                                if attachment.id != detail.attachments.last?.id { Divider() }
                            }
                        }
                        .ratsCard()
                    }

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
                            Label(bookmarkID == nil ? "Merken" : "Gemerkt", systemImage: bookmarkID == nil ? "bookmark" : "bookmark.fill")
                        }
                        .buttonStyle(SecondaryButtonStyle())
                        .disabled(isWorking)
                        if let follow = detail.follow {
                            Button { toggleFollow(follow) } label: {
                                Label(follow.following ? "Wird verfolgt" : "Vorgang folgen", systemImage: follow.following ? "bell.fill" : "bell")
                            }
                            .buttonStyle(SecondaryButtonStyle())
                            .disabled(isWorking)
                        }
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
        .sheet(item: $previewAttachment) { attachment in
            CouncilAttachmentPreview(attachment: attachment)
        }
    }

    private func load() async {
        do {
            async let detailRequest: DecisionDetail = model.api.get("/api/council/decision/\(decisionID)")
            if model.user != nil {
                async let bookmarksRequest: BookmarkPage = model.api.get("/api/bookmarks")
                let (loadedDetail, bookmarks) = try await (detailRequest, bookmarksRequest)
                detail = loadedDetail
                bookmarkID = bookmarks.bookmarks.first { $0.decision?.id == decisionID }?.id
            } else {
                detail = try await detailRequest
            }
            error = nil
        } catch { self.error = error.localizedDescription }
    }

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
            decision: decision, presentParties: presentParties, ratsinfoURL: ratsinfoURL,
            similar: similar, subVotes: subVotes, templateJourney: templateJourney,
            consultations: consultations, templateURL: templateURL, template: template,
            attachments: attachments, participation: participation, importance: importance,
            follow: follow
        )
    }
}

private struct CouncilAttachmentPreview: View {
    let attachment: CouncilAttachment
    @Environment(\.dismiss) private var dismiss
    @State private var localURL: URL?
    @State private var error: String?

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                RatsSheetHeader(
                    attachment.label,
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
                            if let url = URL(string: attachment.url) {
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
        guard localURL == nil, let remoteURL = URL(string: attachment.url) else {
            error = "Die Dokumentadresse ist ungültig."
            return
        }
        do {
            let (temporaryURL, response) = try await URLSession.shared.download(from: remoteURL)
            guard let http = response as? HTTPURLResponse, (200..<300).contains(http.statusCode) else {
                throw URLError(.badServerResponse)
            }
            let suffix = remoteURL.pathExtension.isEmpty ? "pdf" : remoteURL.pathExtension
            let destination = FileManager.default.temporaryDirectory
                .appending(path: "ratslotse-\(attachment.documentID)-\(UUID().uuidString).\(suffix)")
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

struct SavedCouncilView: View {
    let model: AppModel
    @State private var bookmarks: [BookmarkEntry] = []
    @State private var follows: [FollowEntry] = []
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
                    MonoKicker("Merkliste", trailing: "\(bookmarks.count)")
                    ForEach(bookmarks) { bookmark in
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
                        .ratsCard()
                    }
                }

                if !follows.isEmpty {
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
            Pill(bookmark.decision?.outcome ?? bookmark.state, symbol: bookmark.decision == nil ? "clock" : "checkmark")
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .contentShape(Rectangle())
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

    private func load() async {
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
                    ForEach(sessions) { session in
                        if let ksinr = session.ksinr {
                            NavigationLink(value: AppRoute.sessions(ksinr: ksinr, tops: [])) {
                                HStack(alignment: .center, spacing: 10) {
                                    SessionRow(session: session)
                                    Image(systemName: "chevron.right")
                                        .font(.caption)
                                        .foregroundStyle(RatsColor.muted)
                                }
                                .ratsCard()
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
                "/api/council/sessions", query: [.init(name: "limit", value: "100")]
            )
            sessions = page.sessions
            error = nil
        } catch { self.error = error.localizedDescription }
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
                            MonoKicker([RatsDate.weekday(detail.sessionDate), detail.sessionTime].compactMap { $0 }.joined(separator: " · "))
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
