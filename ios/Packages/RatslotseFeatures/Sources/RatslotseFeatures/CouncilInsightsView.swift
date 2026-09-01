import RatslotseAPI
import RatslotseDesign
import Charts
import SwiftUI

private enum InsightSection: String, CaseIterable, Identifiable {
    case trends = "Trends"
    case parties = "Parteien"
    case people = "Personen"
    case finance = "Finanzen"
    case goals = "Ziele"

    var id: String { rawValue }
}

private struct TrendResponse: Decodable, Sendable {
    let quarters: [String]
    let fields: [String]
    let byField: [String: [Int]]
    let money: [Double]
    let moneyDrivers: [MoneyDriver?]
    let emerging: [EmergingTopic]
    let fieldLabels: [String: String]

    enum CodingKeys: String, CodingKey {
        case quarters, fields, money, emerging
        case moneyDrivers = "money_drivers"
        case byField = "by_field"
        case fieldLabels = "field_labels"
    }
}

private struct MoneyDriver: Decodable, Sendable {
    let id: Int
    let title: String
    let eur: Double
}

private struct EmergingTopic: Decodable, Sendable, Identifiable {
    var id: String { tag }
    let tag: String
    let n: Int
}

private struct PartyAnalysisResponse: Decodable, Sendable {
    let coverage: Coverage
    let topicMatrix: TopicMatrix
    let successRates: [PartySuccess]
    let applicationStats: ApplicationStats?
    let contention: [Contention]
    let alliances: [Alliance]
    let fieldLabels: [String: String]

    enum CodingKeys: String, CodingKey {
        case coverage, contention, alliances
        case topicMatrix = "topic_matrix"
        case successRates = "success_rates"
        case applicationStats = "antrag_stats"
        case fieldLabels = "field_labels"
    }
}

private struct TopicMatrix: Decodable, Sendable {
    let parties: [String]
    let fields: [String]
    let matrix: [String: [String: Int]]
}

private struct ApplicationStats: Decodable, Sendable {
    let parties: [ApplicationParty]
    let applicationCount: Int
    let decidedCount: Int

    enum CodingKeys: String, CodingKey {
        case parties
        case applicationCount = "n_antraege"
        case decidedCount = "n_mit_beschluss"
    }
}

private struct ApplicationParty: Decodable, Sendable, Identifiable {
    var id: String { party }
    let party: String
    let n: Int
    let angenommen: Int
    let abgelehnt: Int
}

private struct Coverage: Decodable, Sendable {
    let withFactions: Int
    let total: Int
    enum CodingKeys: String, CodingKey { case withFactions = "with_factions", total }
}

private struct PartySuccess: Decodable, Sendable, Identifiable {
    var id: String { party }
    let party: String
    let motions: Int
    let angenommen: Int
    let abgelehnt: Int
    let vertagt: Int
    let rate: Double?
}

private struct Contention: Decodable, Sendable, Identifiable {
    var id: String { field }
    let field: String
    let total: Int
    let contested: Int
    let contestedRate: Double
    enum CodingKeys: String, CodingKey { case field, total, contested; case contestedRate = "contested_rate" }
}

private struct Alliance: Decodable, Sendable, Identifiable {
    var id: String { "\(a)-\(b)" }
    let a: String
    let b: String
    let count: Int
}

private struct MembersResponse: Decodable, Sendable { let members: [CouncilMember] }

private struct CouncilMember: Decodable, Sendable, Identifiable {
    var id: String { slug }
    let slug: String
    let name: String
    let party: String?
    let art: String
    let organisation: String?
    let filterParties: [String]
    let forms: [String]
    let n: Int
    let committees: Int

    enum CodingKeys: String, CodingKey {
        case slug, name, party, art, organisation, n, committees
        case filterParties = "filter_parteien"
        case forms = "formen"
    }

    init(from decoder: Decoder) throws {
        let values = try decoder.container(keyedBy: CodingKeys.self)
        slug = try values.decode(String.self, forKey: .slug)
        name = try values.decode(String.self, forKey: .name)
        party = try values.decodeIfPresent(String.self, forKey: .party)
        art = try values.decodeIfPresent(String.self, forKey: .art) ?? "rat"
        organisation = try values.decodeIfPresent(String.self, forKey: .organisation)
        filterParties = try values.decodeIfPresent([String].self, forKey: .filterParties) ?? party.map { [$0] } ?? []
        forms = try values.decodeIfPresent([String].self, forKey: .forms) ?? []
        n = try values.decodeIfPresent(Int.self, forKey: .n) ?? 0
        committees = try values.decodeIfPresent(Int.self, forKey: .committees) ?? 0
    }

    init(slug: String, name: String, party: String?, art: String, organisation: String?, filterParties: [String] = [], forms: [String] = [], n: Int, committees: Int) {
        self.slug = slug; self.name = name; self.party = party; self.art = art
        self.organisation = organisation; self.filterParties = filterParties
        self.forms = forms; self.n = n; self.committees = committees
    }
}

private struct PeopleLexiconResponse: Decodable, Sendable { let personen: [AdministrationPerson] }

private struct AdministrationPerson: Decodable, Sendable, Identifiable {
    var id: String { slug }
    let slug: String
    let name: String?
    let art: String
    let role: String?
}

private struct FinanceResponse: Decodable, Sendable {
    let decisions: [DecisionSummary]
    let byField: [FinanceField]
    let fieldLabels: [String: String]
    enum CodingKeys: String, CodingKey {
        case decisions
        case byField = "by_field"
        case fieldLabels = "field_labels"
    }
}

private struct FinanceField: Decodable, Sendable, Identifiable {
    var id: String { field }
    let field: String
    let total: Double
    let n: Int
}

private struct GoalsResponse: Decodable, Sendable { let goals: [CouncilGoal] }

private struct GoalDetailResponse: Decodable, Sendable {
    let decisions: [GoalDecision]
}

private struct GoalDecision: Decodable, Sendable, Identifiable {
    let id: Int
    let title: String?
    let summary: String?
    let policyField: String?
    let outcome: String?
    let sessionDate: String?
    let committee: String?
    let stance: String
    let rationale: String?

    enum CodingKeys: String, CodingKey {
        case id, title, summary, outcome, committee, stance, rationale
        case policyField = "policy_field"
        case sessionDate = "session_date"
    }
}

private struct FieldRecapsResponse: Decodable, Sendable { let recaps: [FieldRecap] }

private struct FieldRecap: Decodable, Sendable, Identifiable {
    var id: String { policyField }
    let policyField: String
    let fieldLabel: String
    let summary: String
    let decisionCount: Int
    let periodFrom: String
    let periodTo: String

    enum CodingKeys: String, CodingKey {
        case summary
        case policyField = "policy_field"
        case fieldLabel = "field_label"
        case decisionCount = "n_decisions"
        case periodFrom = "period_from"
        case periodTo = "period_to"
    }
}

private struct AnalysisDrilldown: Identifiable {
    let id = UUID()
    let title: String
    let query: [URLQueryItem]
}

private struct CouncilGoal: Decodable, Sendable, Identifiable {
    var id: String { key }
    let key: String
    let label: String
    let description: String
    let voran: Int
    let bremst: Int
    let neutral: Int
    let total: Int
}

struct CouncilInsightsView: View {
    let model: AppModel
    @Environment(\.dynamicTypeSize) private var dynamicTypeSize
    @State private var section: InsightSection = {
        switch ProcessInfo.processInfo.environment["RATSLOTSE_DEBUG_ANALYSIS_SECTION"] {
        case "parties": .parties
        case "people": .people
        case "finance": .finance
        case "goals": .goals
        default: .trends
        }
    }()
    @State private var trends: TrendResponse?
    @State private var parties: PartyAnalysisResponse?
    @State private var members: [CouncilMember] = []
    @State private var finance: FinanceResponse?
    @State private var goals: [CouncilGoal] = []
    @State private var fieldRecaps: [FieldRecap] = []
    @State private var administrationPeople: [AdministrationPerson] = []
    @State private var partyFilter = ""
    @State private var expandedRecaps: Set<String> = []
    @State private var recapFilter: String?
    @State private var expandedGoals: Set<String> = []
    @State private var goalDetails: [String: [GoalDecision]] = [:]
    @State private var goalLoading: Set<String> = []
    @State private var drilldown: AnalysisDrilldown?
    @State private var isLoading = true
    @State private var error: String?
    @State private var personQuery = ""

    var body: some View {
        ScrollView {
            LazyVStack(alignment: .leading, spacing: 16) {
                VStack(alignment: .leading, spacing: 5) {
                    MonoKicker("Ratsdaten verstehen")
                    Text("Analyse")
                        .font(RatsFont.title(28))
                    Text("Trends, Parteien, Personen, Finanzen und Stadtziele – aus den öffentlichen Unterlagen des Rats.")
                        .font(RatsFont.body(13))
                        .foregroundStyle(RatsColor.secondary)
                        .lineSpacing(2)
                }

                sectionPicker

                if isLoading {
                    RatsLoadingState(message: "Analyse wird aufbereitet …")
                } else if let error {
                    ErrorCard(message: error) { Task { await load() } }
                } else {
                    switch section {
                    case .trends: trendsView
                    case .parties: partiesView
                    case .people: peopleView
                    case .finance: financeView
                    case .goals: goalsView
                    }
                }
            }
            .frame(maxWidth: 760, alignment: .leading)
            .padding(18)
        }
        .background(RatsColor.page)
        .navigationTitle("Analyse")
        .navigationBarTitleDisplayMode(.inline)
        .refreshable { await load() }
        .task {
            await load()
            await model.markExplorationStep("analyse")
        }
        .sheet(item: $drilldown) { item in
            AnalysisDecisionSheet(model: model, drilldown: item)
                .ratsLargeSheet()
        }
    }

    private var sectionPicker: some View {
        Group {
            if dynamicTypeSize.isAccessibilitySize {
                LazyVGrid(columns: [GridItem(.adaptive(minimum: 135), spacing: 7)], spacing: 7) {
                    ForEach(InsightSection.allCases) { sectionButton($0) }
                }
            } else {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 7) {
                        ForEach(InsightSection.allCases) { sectionButton($0) }
                    }
                }
            }
        }
    }

    private func sectionButton(_ item: InsightSection) -> some View {
        Button { withAnimation(.easeOut(duration: 0.18)) { section = item } } label: {
            Text(item.rawValue)
                .font(RatsFont.body(12, weight: .semibold))
                .foregroundStyle(section == item ? RatsColor.primaryText : RatsColor.bodyText)
                .padding(.horizontal, 13)
                .frame(maxWidth: dynamicTypeSize.isAccessibilitySize ? .infinity : nil)
                .frame(minHeight: 34)
                .background(section == item ? RatsColor.primary : RatsColor.card)
                .overlay(Capsule().stroke(section == item ? Color.clear : RatsColor.border))
                .clipShape(Capsule())
        }
        .buttonStyle(RatsPlainButtonStyle())
    }

    private var analysisGridMinimum: CGFloat {
        dynamicTypeSize.isAccessibilitySize ? 520 : 250
    }

    private var peopleGridMinimum: CGFloat {
        dynamicTypeSize.isAccessibilitySize ? 520 : 260
    }

    @ViewBuilder
    private var trendsView: some View {
        if let trends, !trends.quarters.isEmpty {
            analysisIntro(
                title: "Was bewegt den Rat?",
                detail: "Rückblicke und neue Themen zeigen, womit sich der Rat zuletzt beschäftigt hat – ohne daraus automatisch Wirkung abzuleiten."
            )
            if !fieldRecaps.isEmpty { fieldRecapsView }
            if !trends.emerging.isEmpty {
                RatsSectionPanel("Neue Themen", detail: "Begriffe, die zuletzt häufiger auftauchen.", symbol: nil) {
                    FlowLayout(spacing: 7) {
                        ForEach(trends.emerging) { topic in
                            Button {
                                drilldown = AnalysisDrilldown(
                                    title: topic.tag,
                                    query: [.init(name: "q", value: topic.tag)]
                                )
                            } label: {
                                RatsLabel("\(topic.tag) · \(topic.n)", .arrowUpRight)
                                .font(RatsFont.body(11, weight: .semibold))
                                .foregroundStyle(RatsColor.primary)
                                .padding(.horizontal, 10)
                                .padding(.vertical, 6)
                                .background(RatsColor.primary.opacity(0.08))
                                .clipShape(Capsule())
                            }
                            .buttonStyle(RatsPlainButtonStyle())
                        }
                    }
                }
            }
        } else {
            empty("Noch keine Trends", "Es sind noch nicht genug datierte, klassifizierte Beschlüsse vorhanden.")
        }
    }

    private var fieldRecapsView: some View {
        RatsSectionPanel("Rückblick je Themenfeld", detail: "Automatische Kurzfassungen der neuesten Beschlüsse.", symbol: nil) {
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 7) {
                    recapChip("Alle", selected: recapFilter == nil) { recapFilter = nil }
                    ForEach(fieldRecaps) { recap in
                        recapChip(recap.fieldLabel, selected: recapFilter == recap.policyField) {
                            recapFilter = recapFilter == recap.policyField ? nil : recap.policyField
                        }
                    }
                }
            }
            LazyVGrid(columns: [GridItem(.adaptive(minimum: analysisGridMinimum), spacing: 10)], spacing: 10) {
                ForEach(filteredRecaps) { recap in
                    Button {
                        withAnimation(.snappy) {
                            if expandedRecaps.contains(recap.id) { expandedRecaps.remove(recap.id) }
                            else { expandedRecaps.insert(recap.id) }
                        }
                    } label: {
                        VStack(alignment: .leading, spacing: 8) {
                            HStack {
                                Text(recap.fieldLabel).font(RatsFont.body(13, weight: .semibold))
                                Spacer()
                                Text("\(recap.decisionCount)")
                                    .font(RatsFont.mono(10, weight: .semibold))
                                    .foregroundStyle(RatsColor.primary)
                                    .padding(.horizontal, 7).padding(.vertical, 3)
                                    .background(RatsColor.primary.opacity(0.08)).clipShape(Capsule())
                                RatsIcon(.chevronDown, size: 11.5)
                                    .rotationEffect(.degrees(expandedRecaps.contains(recap.id) ? 180 : 0))
                                    .foregroundStyle(RatsColor.muted)
                            }
                            Text(recap.summary)
                                .font(RatsFont.body(11.5))
                                .foregroundStyle(RatsColor.bodyText)
                                .lineSpacing(2)
                                .lineLimit(expandedRecaps.contains(recap.id) ? nil : 3)
                            if expandedRecaps.contains(recap.id) {
                                HStack {
                                    Text("\(RatsDate.short(recap.periodFrom) ?? recap.periodFrom) – \(RatsDate.short(recap.periodTo) ?? recap.periodTo)")
                                        .font(RatsFont.mono(9)).foregroundStyle(RatsColor.muted)
                                    Spacer()
                                    Button("Beschlüsse") {
                                        drilldown = AnalysisDrilldown(title: recap.fieldLabel, query: [.init(name: "field", value: recap.policyField)])
                                    }
                                    .font(RatsFont.body(10.5, weight: .semibold))
                                }
                            }
                        }
                        .padding(12)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .background(RatsColor.stage)
                        .overlay(RoundedRectangle(cornerRadius: 13).stroke(RatsColor.border))
                        .clipShape(RoundedRectangle(cornerRadius: 13))
                    }
                    .buttonStyle(RatsPlainButtonStyle())
                }
            }
        }
    }

    @ViewBuilder
    private var partiesView: some View {
        if let parties, parties.coverage.withFactions > 0 {
            analysisIntro(
                title: "Wer bringt welche Anträge ein?",
                detail: "Grundlage sind \(parties.coverage.withFactions) von \(parties.coverage.total) klassifizierten Beschlüssen – nicht das individuelle Abstimmungsverhalten."
            )
            RatsSectionPanel("Wer bringt welche Themen ein?", detail: "Anträge je Partei und Themenfeld – dunkler bedeutet häufiger.", symbol: nil) {
                PartyTopicHeatmap(data: parties)
            }
            RatsSectionPanel("Erfolgsquote der Anträge", detail: "Grün angenommen, rot abgelehnt, orange vertagt.", symbol: nil) {
                VStack(spacing: 13) {
                    if let stats = parties.applicationStats,
                       stats.parties.contains(where: { $0.n >= 5 }) {
                        ForEach(stats.parties.filter { $0.n >= 5 }) { row in
                            ApplicationOutcomeRow(row: row)
                        }
                        Text("Original-Antragsdokumente · \(stats.decidedCount) von \(stats.applicationCount) mit Beschluss")
                            .font(RatsFont.body(9.5)).foregroundStyle(RatsColor.muted)
                    } else {
                        ForEach(parties.successRates) { row in
                            PartyOutcomeRow(row: row)
                        }
                    }
                }
            }
            RatsSectionPanel("Streitgrad nach Themenfeld", detail: "Anteil nicht einstimmiger Abstimmungen.", symbol: nil) {
                VStack(spacing: 12) {
                    ForEach(parties.contention.prefix(10)) { row in
                        MetricBar(
                            label: parties.fieldLabels[row.field] ?? row.field,
                            value: row.contestedRate,
                            valueLabel: "\(Int((row.contestedRate * 100).rounded())) %"
                        )
                    }
                }
            }
            if !parties.alliances.isEmpty {
                RatsSectionPanel("Häufige Allianzen", detail: "Parteien, die Anträge gemeinsam einbringen.", symbol: nil) {
                    FlowLayout(spacing: 7) {
                        ForEach(parties.alliances) { alliance in
                            Text("\(alliance.a) + \(alliance.b) · \(alliance.count)×")
                                .font(RatsFont.body(11, weight: .semibold))
                                .padding(.horizontal, 10)
                                .padding(.vertical, 7)
                                .background(RatsColor.stage)
                                .overlay(Capsule().stroke(RatsColor.border))
                                .clipShape(Capsule())
                        }
                    }
                }
            }
        } else {
            empty("Noch keine Parteianalyse", "Für eine belastbare Einordnung fehlen derzeit genügend klassifizierte Anträge.")
        }
    }

    @ViewBuilder
    private var peopleView: some View {
        if members.isEmpty {
            empty("Noch keine Ratsmitglieder", "Es wurden noch keine Anwesenheiten aus den Protokollen erfasst.")
        } else {
            analysisIntro(
                title: "Wer sitzt im Rat?",
                detail: "Präsenz aus öffentlichen Anwesenheitslisten – keine Bewertung des Abstimmungsverhaltens."
            )
            HStack(spacing: 9) {
                RatsGlyphView(glyph: .search, color: RatsColor.secondary)
                    .frame(width: 18, height: 18)
                TextField("Name oder Fraktion suchen", text: $personQuery)
                    .font(RatsFont.body(14))
                    .textFieldStyle(.plain)
            }
            .padding(.horizontal, 13)
            .frame(height: 44)
            .background(RatsColor.card)
            .overlay(RoundedRectangle(cornerRadius: 12).stroke(RatsColor.border))
            .clipShape(RoundedRectangle(cornerRadius: 12))

            Menu {
                Button("Alle Fraktionen") { partyFilter = "" }
                ForEach(memberParties, id: \.self) { party in
                    Button(party) { partyFilter = party }
                }
            } label: {
                HStack {
                    RatsGlyphView(glyph: .profile, color: RatsColor.primary).frame(width: 17, height: 17)
                    Text(partyFilter.isEmpty ? "Alle Fraktionen" : partyFilter)
                    Spacer()
                    RatsIcon(.chevronsUpDown, size: 12)
                }
                .font(RatsFont.body(12, weight: .semibold))
                .foregroundStyle(RatsColor.bodyText)
                .padding(.horizontal, 12)
                .frame(height: 42)
                .background(RatsColor.card)
                .overlay(RoundedRectangle(cornerRadius: 12).stroke(RatsColor.border))
                .clipShape(RoundedRectangle(cornerRadius: 12))
            }

            let councilMembers = filteredMembers.filter { $0.art != "beratend" }
            let advisors = filteredMembers.filter { $0.art == "beratend" }
            MonoKicker("Ratsmitglieder", trailing: "\(councilMembers.count)")
            peopleGrid(councilMembers)
            if !advisors.isEmpty {
                MonoKicker("Beratende Mitglieder", trailing: "\(advisors.count)")
                Text("Sie beraten Ausschüsse, besitzen aber kein Ratsmandat.")
                    .font(RatsFont.body(10.5)).foregroundStyle(RatsColor.secondary)
                peopleGrid(advisors)
            }
            let administration = filteredAdministration
            if partyFilter.isEmpty, !administration.isEmpty {
                MonoKicker("Stadtverwaltung", trailing: "\(administration.count)")
                LazyVGrid(columns: [GridItem(.adaptive(minimum: peopleGridMinimum), spacing: 10)], spacing: 10) {
                    ForEach(administration) { person in
                        NavigationLink(value: AppRoute.person(slug: person.slug)) {
                            HStack {
                                VStack(alignment: .leading, spacing: 3) {
                                    Text(person.name ?? "Amtsträger*in").font(RatsFont.body(13.5, weight: .semibold))
                                    Text(person.role ?? "Stadtverwaltung").font(RatsFont.body(10.5)).foregroundStyle(RatsColor.secondary)
                                }
                                Spacer()
                                Text("Stadt").font(RatsFont.body(9.5, weight: .semibold)).foregroundStyle(RatsColor.primary)
                                    .padding(.horizontal, 7).padding(.vertical, 4).background(RatsColor.primary.opacity(0.08)).clipShape(Capsule())
                            }
                            .ratsCard()
                        }.buttonStyle(RatsPlainButtonStyle())
                    }
                }
            }
        }
    }

    @ViewBuilder
    private var financeView: some View {
        if let finance, !finance.byField.isEmpty || !finance.decisions.isEmpty {
            let total = finance.byField.reduce(0) { $0 + $1.total }
            analysisIntro(
                title: "≈ \(formatEuro(total)) erkannt",
                detail: "Summen aus Beschlusstexten – eine Orientierung, ausdrücklich nicht der offizielle Haushalt."
            )
            if !finance.byField.isEmpty {
                RatsSectionPanel("Wofür fließt das Geld?", detail: "Erkanntes Finanzvolumen je Themenfeld.", symbol: nil) {
                    let maximum = max(1, finance.byField.map(\.total).max() ?? 1)
                    VStack(spacing: 12) {
                        ForEach(finance.byField) { row in
                            Button {
                                drilldown = AnalysisDrilldown(title: finance.fieldLabels[row.field] ?? row.field, query: [.init(name: "field", value: row.field)])
                            } label: {
                                MetricBar(
                                    label: finance.fieldLabels[row.field] ?? row.field,
                                    value: row.total / maximum,
                                    valueLabel: "\(formatEuro(row.total)) · \(row.n)",
                                    color: RatsColor.success
                                )
                            }.buttonStyle(RatsPlainButtonStyle())
                        }
                    }
                }
            }
            if !finance.decisions.isEmpty {
                MonoKicker("Größte Finanzbeschlüsse")
                ForEach(finance.decisions.prefix(12)) { decision in
                    NavigationLink(value: AppRoute.decision(id: decision.id)) {
                        DecisionRow(decision: decision).ratsCard()
                    }
                    .buttonStyle(RatsPlainButtonStyle())
                }
            }
        } else {
            empty("Noch keine Finanzdaten", "Es wurden noch keine Euro-Beträge aus Beschlüssen erkannt.")
        }
    }

    @ViewBuilder
    private var goalsView: some View {
        if goals.contains(where: { $0.total > 0 }) {
            analysisIntro(
                title: "Oldenburgs Ziele im Blick",
                detail: "Wie viele Beschlüsse ein Stadtziel voranbringen, bremsen oder neutral berühren – nicht die reale Zielerreichung."
            )
            ForEach(goals) { goal in
                VStack(alignment: .leading, spacing: 10) {
                    Button { toggleGoal(goal) } label: {
                    HStack(alignment: .top, spacing: 10) {
                        RatsGlyphView(glyph: .analysis)
                            .frame(width: 18, height: 18)
                            .frame(width: 34, height: 34)
                            .background(RatsColor.primary.opacity(0.08))
                            .clipShape(RoundedRectangle(cornerRadius: 10))
                        VStack(alignment: .leading, spacing: 3) {
                            Text(goal.label).font(RatsFont.body(14, weight: .semibold))
                            Text(goal.description).font(RatsFont.body(10.5)).foregroundStyle(RatsColor.secondary).lineLimit(3)
                        }
                        Spacer()
                        RatsIcon(.chevronDown, size: 16)
                            .rotationEffect(.degrees(expandedGoals.contains(goal.key) ? 180 : 0))
                            .foregroundStyle(RatsColor.muted)
                    }
                    }.buttonStyle(RatsPlainButtonStyle())
                    GoalBalanceBar(goal: goal)
                    HStack {
                        Text("\(goal.bremst) bremsen").foregroundStyle(RatsColor.danger)
                        Spacer()
                        Text("\(goal.neutral) neutral").foregroundStyle(RatsColor.muted)
                        Spacer()
                        Text("\(goal.voran) voran").foregroundStyle(RatsColor.success)
                    }
                    .font(RatsFont.body(9.5, weight: .semibold))
                    if expandedGoals.contains(goal.key) {
                        Divider().overlay(RatsColor.separator)
                        if goalLoading.contains(goal.key) {
                            RatsLoadingState(message: "Beschlüsse werden geladen …")
                        } else if let decisions = goalDetails[goal.key] {
                            ForEach(decisions) { decision in
                                Button { model.navigation.append(.decision(id: decision.id)) } label: {
                                    VStack(alignment: .leading, spacing: 4) {
                                        HStack {
                                            Text(stanceLabel(decision.stance))
                                                .font(RatsFont.mono(9, weight: .semibold))
                                                .foregroundStyle(stanceColor(decision.stance))
                                            Spacer()
                                            Text(RatsDate.short(decision.sessionDate) ?? "")
                                                .font(RatsFont.mono(9)).foregroundStyle(RatsColor.muted)
                                        }
                                        Text(decision.title ?? "Beschluss").font(RatsFont.body(12.5, weight: .semibold))
                                        if let rationale = decision.rationale {
                                            Text(rationale).font(RatsFont.body(10.5)).foregroundStyle(RatsColor.secondary).lineLimit(3)
                                        }
                                    }
                                    .padding(.vertical, 4)
                                }.buttonStyle(RatsPlainButtonStyle())
                            }
                        }
                    }
                }
                .ratsCard()
            }
        } else {
            empty("Ziel-Tracking wird vorbereitet", "Die Beschlüsse werden gerade den Stadtzielen zugeordnet.")
        }
    }

    private func analysisIntro(title: String, detail: String) -> some View {
        HStack(alignment: .top, spacing: 13) {
            Lotti3DView(scene: .explain, animated: false)
                .frame(width: 140, height: 86)
            VStack(alignment: .leading, spacing: 4) {
                Text(title).font(RatsFont.title(18))
                Text(detail).font(RatsFont.body(11.5)).foregroundStyle(RatsColor.secondary).lineSpacing(2)
            }
            Spacer(minLength: 0)
        }
        .padding(14)
        .background(RatsColor.primary.opacity(0.06))
        .overlay(RoundedRectangle(cornerRadius: 15).stroke(RatsColor.primary.opacity(0.16)))
        .clipShape(RoundedRectangle(cornerRadius: 15))
    }

    private func empty(_ title: String, _ message: String) -> some View {
        VStack(spacing: 8) {
            Lotti3DView(scene: .reading, animated: false)
                .frame(width: 124, height: 132)
            Text(title).font(RatsFont.title(20))
            Text(message).font(RatsFont.body(12.5)).foregroundStyle(RatsColor.secondary).multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity)
        .ratsCard()
    }

    private var filteredMembers: [CouncilMember] {
        let needle = personQuery.trimmingCharacters(in: .whitespacesAndNewlines)
        return members.filter { member in
            let matchesParty = partyFilter.isEmpty || member.filterParties.contains(partyFilter)
            let matchesText = needle.isEmpty
                || member.name.localizedCaseInsensitiveContains(needle)
                || member.forms.contains(where: { $0.localizedCaseInsensitiveContains(needle) })
                || member.party?.localizedCaseInsensitiveContains(needle) == true
                || member.organisation?.localizedCaseInsensitiveContains(needle) == true
            return matchesParty && matchesText
        }
    }

    private var filteredAdministration: [AdministrationPerson] {
        let needle = personQuery.trimmingCharacters(in: .whitespacesAndNewlines)
        return administrationPeople.filter {
            needle.isEmpty
                || $0.name?.localizedCaseInsensitiveContains(needle) == true
                || $0.role?.localizedCaseInsensitiveContains(needle) == true
        }
    }

    private var memberParties: [String] {
        Array(Set(members.flatMap(\.filterParties))).sorted()
    }

    private var filteredRecaps: [FieldRecap] {
        guard let recapFilter else { return fieldRecaps }
        return fieldRecaps.filter { $0.policyField == recapFilter }
    }

    private func recapChip(_ title: String, selected: Bool, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Text(title)
                .font(RatsFont.body(10.5, weight: .semibold))
                .foregroundStyle(selected ? RatsColor.primaryText : RatsColor.bodyText)
                .padding(.horizontal, 10).frame(height: 30)
                .background(selected ? RatsColor.primary : RatsColor.stage)
                .overlay(Capsule().stroke(selected ? Color.clear : RatsColor.border))
                .clipShape(Capsule())
        }.buttonStyle(RatsPlainButtonStyle())
    }

    private func peopleGrid(_ entries: [CouncilMember]) -> some View {
        LazyVGrid(columns: [GridItem(.adaptive(minimum: peopleGridMinimum), spacing: 10)], spacing: 10) {
            ForEach(entries) { member in
                NavigationLink(value: AppRoute.person(slug: member.slug)) {
                    HStack(spacing: 12) {
                        RoundedRectangle(cornerRadius: 11)
                            .fill(partyColor(member.party ?? member.organisation ?? "Stadt").opacity(0.12))
                            .frame(width: 40, height: 40)
                            .overlay(Text(initials(member.name)).font(RatsFont.body(11, weight: .bold)).foregroundStyle(partyColor(member.party ?? "Stadt")))
                        VStack(alignment: .leading, spacing: 3) {
                            Text(member.name).font(RatsFont.body(13.5, weight: .semibold)).lineLimit(1)
                            Text(member.art == "beratend"
                                 ? [member.organisation, "\(member.n) Sitzungen"].compactMap { $0 }.joined(separator: " · ")
                                 : "\(member.n) Sitzungen · \(member.committees) Gremien")
                                .font(RatsFont.body(10.5)).foregroundStyle(RatsColor.secondary).lineLimit(2)
                        }
                        Spacer(minLength: 4)
                        if let party = member.party {
                            Text(party).font(RatsFont.body(9, weight: .semibold)).foregroundStyle(partyColor(party))
                                .padding(.horizontal, 7).padding(.vertical, 4).background(partyColor(party).opacity(0.10)).clipShape(Capsule())
                        }
                    }
                    .ratsCard()
                }.buttonStyle(RatsPlainButtonStyle())
            }
        }
    }

    private func toggleGoal(_ goal: CouncilGoal) {
        withAnimation(.snappy) {
            if expandedGoals.contains(goal.key) { expandedGoals.remove(goal.key); return }
            expandedGoals.insert(goal.key)
        }
        guard goalDetails[goal.key] == nil, !goalLoading.contains(goal.key) else { return }
        goalLoading.insert(goal.key)
        Task {
            defer { goalLoading.remove(goal.key) }
            do {
                let detail: GoalDetailResponse = try await model.api.get("/api/council/goal/\(goal.key)")
                goalDetails[goal.key] = detail.decisions
            } catch { self.error = error.localizedDescription }
        }
    }

    private func stanceLabel(_ stance: String) -> String {
        switch stance { case "voran": "BRINGT VORAN"; case "bremst": "BREMST"; default: "BERÜHRT DAS ZIEL" }
    }

    private func stanceColor(_ stance: String) -> Color {
        switch stance { case "voran": RatsColor.success; case "bremst": RatsColor.danger; default: RatsColor.muted }
    }

    private func partyColor(_ party: String) -> Color {
        let value = party.lowercased()
        if value.contains("spd") { return Color(red: 0.86, green: 0.12, blue: 0.16) }
        if value.contains("cdu") { return Color(red: 0.18, green: 0.20, blue: 0.22) }
        if value.contains("grün") { return Color(red: 0.16, green: 0.55, blue: 0.22) }
        if value.contains("fdp") { return Color(red: 0.95, green: 0.73, blue: 0.10) }
        if value.contains("link") { return Color(red: 0.70, green: 0.12, blue: 0.40) }
        if value.contains("afd") { return Color(red: 0.14, green: 0.45, blue: 0.76) }
        if value.contains("volt") { return Color(red: 0.38, green: 0.16, blue: 0.66) }
        return RatsColor.primary
    }

    private func load() async {
        isLoading = true
        defer { isLoading = false }
#if DEBUG
        if ProcessInfo.processInfo.environment["RATSLOTSE_DEBUG_ANALYSIS_FIXTURE"] == "1" {
            trends = TrendResponse(
                quarters: ["2026-Q1", "2026-Q2", "2026-Q3"],
                fields: ["verkehr", "soziales"],
                byField: ["verkehr": [4, 7, 9], "soziales": [3, 5, 4]],
                money: [1_200_000, 2_800_000, 4_100_000],
                moneyDrivers: [
                    MoneyDriver(id: 1, title: "Neue Busspuren für Oldenburg", eur: 1_200_000),
                    MoneyDriver(id: 2, title: "Umbau der Alten Fleiwa", eur: 2_800_000),
                    MoneyDriver(id: 3, title: "Schulbauprogramm", eur: 4_100_000),
                ],
                emerging: [EmergingTopic(tag: "Velorouten", n: 5)],
                fieldLabels: ["verkehr": "Verkehr", "soziales": "Soziales"]
            )
            parties = PartyAnalysisResponse(
                coverage: Coverage(withFactions: 38, total: 44),
                topicMatrix: TopicMatrix(
                    parties: ["SPD", "CDU", "GRÜNE"],
                    fields: ["verkehr", "soziales"],
                    matrix: ["SPD": ["verkehr": 6, "soziales": 8], "CDU": ["verkehr": 7, "soziales": 3], "GRÜNE": ["verkehr": 9, "soziales": 5]]
                ),
                successRates: [
                    PartySuccess(party: "SPD", motions: 14, angenommen: 9, abgelehnt: 3, vertagt: 2, rate: 0.64),
                    PartySuccess(party: "CDU", motions: 11, angenommen: 6, abgelehnt: 4, vertagt: 1, rate: 0.55),
                    PartySuccess(party: "GRÜNE", motions: 9, angenommen: 6, abgelehnt: 2, vertagt: 1, rate: 0.67),
                ],
                applicationStats: ApplicationStats(
                    parties: [
                        ApplicationParty(party: "SPD", n: 12, angenommen: 8, abgelehnt: 4),
                        ApplicationParty(party: "CDU", n: 10, angenommen: 6, abgelehnt: 4),
                    ],
                    applicationCount: 28,
                    decidedCount: 22
                ),
                contention: [
                    Contention(field: "verkehr", total: 17, contested: 8, contestedRate: 0.47),
                    Contention(field: "soziales", total: 13, contested: 4, contestedRate: 0.31),
                ],
                alliances: [Alliance(a: "SPD", b: "GRÜNE", count: 5), Alliance(a: "CDU", b: "FDP", count: 3)],
                fieldLabels: ["verkehr": "Verkehr", "soziales": "Soziales"]
            )
            members = [
                CouncilMember(slug: "anne-beispiel", name: "Anne Beispiel", party: "SPD", art: "rat", organisation: nil, filterParties: ["SPD"], n: 18, committees: 3),
                CouncilMember(slug: "bernd-muster", name: "Bernd Muster", party: "CDU", art: "rat", organisation: nil, filterParties: ["CDU"], n: 16, committees: 2),
                CouncilMember(slug: "cem-kaya", name: "Cem Kaya", party: "GRÜNE", art: "rat", organisation: nil, filterParties: ["GRÜNE"], n: 15, committees: 4),
            ]
            administrationPeople = [AdministrationPerson(slug: "stadtbaurat-beispiel", name: "Dr. Lena Beispiel", art: "stadt", role: "Stadtbaurätin")]
            fieldRecaps = [
                FieldRecap(policyField: "verkehr", fieldLabel: "Verkehr", summary: "Der Rat hat sichere Querungen und den Ausbau des Busverkehrs beraten. Mehrere Vorhaben gehen nun in die konkrete Planung.", decisionCount: 11, periodFrom: "2026-05-01", periodTo: "2026-08-28"),
                FieldRecap(policyField: "soziales", fieldLabel: "Soziales", summary: "Im Mittelpunkt standen zusätzliche Betreuungsplätze und barrierefreie Angebote in den Stadtteilen.", decisionCount: 8, periodFrom: "2026-05-01", periodTo: "2026-08-28"),
            ]
            finance = FinanceResponse(
                decisions: [],
                byField: [
                    FinanceField(field: "verkehr", total: 4_800_000, n: 8),
                    FinanceField(field: "soziales", total: 2_400_000, n: 6),
                    FinanceField(field: "kultur", total: 1_100_000, n: 4),
                ],
                fieldLabels: ["verkehr": "Verkehr", "soziales": "Soziales", "kultur": "Kultur"]
            )
            goals = [
                CouncilGoal(key: "klima", label: "Klimaneutrale Stadt", description: "Emissionen senken und Oldenburg an den Klimawandel anpassen.", voran: 18, bremst: 3, neutral: 7, total: 28),
                CouncilGoal(key: "teilhabe", label: "Soziale Teilhabe", description: "Gute Zugänge zu Wohnen, Bildung und öffentlichem Leben schaffen.", voran: 14, bremst: 2, neutral: 5, total: 21),
            ]
            goalDetails["klima"] = [GoalDecision(id: 1, title: "Neue Busspuren für Oldenburg", summary: "Busverkehr beschleunigen.", policyField: "verkehr", outcome: "angenommen", sessionDate: "2026-08-26", committee: "Rat", stance: "voran", rationale: "Stärkt den öffentlichen Verkehr.")]
            return
        }
#endif
        do {
            async let trendRequest: TrendResponse = model.api.get("/api/council/trends")
            async let partyRequest: PartyAnalysisResponse = model.api.get("/api/council/analysis")
            async let memberRequest: MembersResponse = model.api.get("/api/council/members")
            async let financeRequest: FinanceResponse = model.api.get("/api/council/finance")
            async let goalRequest: GoalsResponse = model.api.get("/api/council/goals")
            async let recapRequest: FieldRecapsResponse = model.api.get("/api/council/field-recaps")
            async let peopleRequest: PeopleLexiconResponse = model.api.get("/api/council/personen-lexikon")
            let responses = try await (trendRequest, partyRequest, memberRequest, financeRequest, goalRequest, recapRequest, peopleRequest)
            trends = responses.0
            parties = responses.1
            members = responses.2.members
            finance = responses.3
            goals = responses.4.goals
            fieldRecaps = responses.5.recaps
            administrationPeople = responses.6.personen.filter { $0.art == "stadt" && $0.role != nil }
            error = nil
        } catch { self.error = error.localizedDescription }
    }

    private func initials(_ name: String) -> String {
        name.split(separator: " ").prefix(2).compactMap(\.first).map(String.init).joined().uppercased()
    }

    private func formatEuro(_ amount: Double) -> String {
        if amount >= 1_000_000 { return String(format: "%.1f Mio. €", amount / 1_000_000) }
        if amount >= 1_000 { return String(format: "%.0f Tsd. €", amount / 1_000) }
        return String(format: "%.0f €", amount)
    }
}

private struct MiniBarChart: View {
    let labels: [String]
    let values: [Double]
    let color: Color

    var body: some View {
        let maximum = max(1, values.max() ?? 1)
        HStack(alignment: .bottom, spacing: 7) {
            ForEach(values.indices, id: \.self) { index in
                VStack(spacing: 5) {
                    Spacer(minLength: 0)
                    RoundedRectangle(cornerRadius: 3, style: .continuous)
                        .fill(color.opacity(0.82))
                        .frame(height: max(3, 112 * values[index] / maximum))
                    Text(labels[safe: index] ?? "")
                        .font(RatsFont.mono(8))
                        .foregroundStyle(RatsColor.muted)
                        .lineLimit(1)
                }
                .frame(maxWidth: .infinity)
                .accessibilityElement(children: .ignore)
                .accessibilityLabel("\(labels[safe: index] ?? "Zeitraum"): \(values[index].formatted())")
            }
        }
        .frame(height: 145)
    }
}

private struct PartyTopicHeatmap: View {
    let data: PartyAnalysisResponse
    @State private var selected: (party: String, field: String, count: Int)?

    var body: some View {
        let matrix = data.topicMatrix
        let maximum = max(1, matrix.parties.flatMap { party in matrix.fields.map { matrix.matrix[party]?[$0] ?? 0 } }.max() ?? 1)
        VStack(alignment: .leading, spacing: 10) {
            ScrollView(.horizontal, showsIndicators: false) {
                Grid(horizontalSpacing: 5, verticalSpacing: 5) {
                    GridRow {
                        Color.clear.frame(width: 88, height: 1)
                        ForEach(matrix.fields, id: \.self) { field in
                            Text(data.fieldLabels[field] ?? field)
                                .font(RatsFont.mono(8.5)).foregroundStyle(RatsColor.muted)
                                .frame(width: 72).lineLimit(2)
                        }
                    }
                    ForEach(matrix.parties, id: \.self) { party in
                        GridRow {
                            Text(party).font(RatsFont.body(10.5, weight: .semibold)).frame(width: 88, alignment: .leading).lineLimit(1)
                            ForEach(matrix.fields, id: \.self) { field in
                                let count = matrix.matrix[party]?[field] ?? 0
                                Button { selected = (party, field, count) } label: {
                                    Text(count == 0 ? "" : "\(count)")
                                        .font(RatsFont.mono(10, weight: .semibold))
                                        .foregroundStyle(Double(count) / Double(maximum) > 0.55 ? RatsColor.primaryText : RatsColor.text)
                                        .frame(width: 72, height: 34)
                                        .background(RatsColor.primary.opacity(count == 0 ? 0.025 : 0.10 + 0.78 * Double(count) / Double(maximum)))
                                        .clipShape(RoundedRectangle(cornerRadius: 7))
                                }.buttonStyle(RatsPlainButtonStyle())
                            }
                        }
                    }
                }
            }
            if let selected {
                Text("\(selected.party): \(selected.count) \(selected.count == 1 ? "Antrag" : "Anträge") im Feld \(data.fieldLabels[selected.field] ?? selected.field)")
                    .font(RatsFont.body(10.5, weight: .semibold)).foregroundStyle(RatsColor.primary)
                    .padding(9).frame(maxWidth: .infinity, alignment: .leading)
                    .background(RatsColor.primary.opacity(0.07)).clipShape(RoundedRectangle(cornerRadius: 9))
            }
        }
    }
}

private struct ApplicationOutcomeRow: View {
    let row: ApplicationParty

    var body: some View {
        let total = max(1, row.n)
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Text(row.party).font(RatsFont.body(12, weight: .semibold))
                Spacer()
                Text("\(Int((Double(row.angenommen) / Double(total) * 100).rounded())) % angenommen · \(row.n)")
                    .font(RatsFont.body(10)).foregroundStyle(RatsColor.secondary)
            }
            GeometryReader { proxy in
                HStack(spacing: 1) {
                    Rectangle().fill(RatsColor.success).frame(width: proxy.size.width * Double(row.angenommen) / Double(total))
                    Rectangle().fill(RatsColor.danger).frame(width: proxy.size.width * Double(row.abgelehnt) / Double(total))
                }.clipShape(Capsule())
            }.frame(height: 10)
        }
    }
}

private struct AnalysisDecisionSheet: View {
    let model: AppModel
    let drilldown: AnalysisDrilldown
    @Environment(\.dismiss) private var dismiss
    @State private var decisions: [DecisionSummary] = []
    @State private var total = 0
    @State private var isLoading = true
    @State private var error: String?

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                RatsSheetHeader(drilldown.title, leadingTitle: "Schließen", leadingAction: { dismiss() })
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 11) {
                        MonoKicker("Beschlüsse", trailing: total > 0 ? "\(total) gefunden" : nil)
                        if isLoading { RatsLoadingState(message: "Beschlüsse werden geladen …") }
                        if let error { ErrorCard(message: error) { Task { await load() } } }
                        ForEach(decisions) { decision in
                            NavigationLink(value: AppRoute.decision(id: decision.id)) {
                                DecisionRow(decision: decision).ratsCard()
                            }.buttonStyle(RatsPlainButtonStyle())
                        }
                    }.padding(18)
                }.background(RatsColor.page)
            }
            .toolbar(.hidden, for: .navigationBar)
            .navigationDestination(for: AppRoute.self) { route in
                RouteDestinationView(model: model, route: route)
            }
        }
        .task { await load() }
    }

    private func load() async {
        isLoading = true; error = nil; defer { isLoading = false }
        do {
            let page: DecisionPage = try await model.api.get(
                "/api/council/decisions",
                query: drilldown.query + [.init(name: "sort", value: "date_desc"), .init(name: "limit", value: "100")]
            )
            decisions = page.decisions; total = page.total
        } catch { self.error = error.localizedDescription }
    }
}

private struct MetricBar: View {
    let label: String
    let value: Double
    let valueLabel: String
    var color: Color = RatsColor.primary

    var body: some View {
        VStack(alignment: .leading, spacing: 5) {
            HStack {
                Text(label).lineLimit(1)
                Spacer()
                Text(valueLabel).foregroundStyle(RatsColor.secondary)
            }
            .font(RatsFont.body(11.5, weight: .semibold))
            GeometryReader { proxy in
                ZStack(alignment: .leading) {
                    Capsule().fill(RatsColor.separator)
                    Capsule().fill(color.opacity(0.78)).frame(width: proxy.size.width * min(1, max(0, value)))
                }
            }
            .frame(height: 8)
        }
    }
}

private struct PartyOutcomeRow: View {
    let row: PartySuccess

    var body: some View {
        let total = max(1, row.angenommen + row.abgelehnt + row.vertagt)
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Text(row.party).font(RatsFont.body(12, weight: .semibold))
                Spacer()
                Text(row.rate.map { "\(Int(($0 * 100).rounded())) % angenommen" } ?? "\(row.motions) Anträge")
                    .font(RatsFont.body(10)).foregroundStyle(RatsColor.secondary)
            }
            GeometryReader { proxy in
                HStack(spacing: 1) {
                    Rectangle().fill(RatsColor.success).frame(width: proxy.size.width * Double(row.angenommen) / Double(total))
                    Rectangle().fill(RatsColor.danger).frame(width: proxy.size.width * Double(row.abgelehnt) / Double(total))
                    Rectangle().fill(RatsColor.signal).frame(width: proxy.size.width * Double(row.vertagt) / Double(total))
                }
                .clipShape(Capsule())
            }
            .frame(height: 10)
        }
    }
}

private struct GoalBalanceBar: View {
    let goal: CouncilGoal

    var body: some View {
        let total = max(1, goal.total)
        GeometryReader { proxy in
            HStack(spacing: 1) {
                Rectangle().fill(RatsColor.danger.opacity(0.78)).frame(width: proxy.size.width * Double(goal.bremst) / Double(total))
                Rectangle().fill(RatsColor.muted.opacity(0.35)).frame(width: proxy.size.width * Double(goal.neutral) / Double(total))
                Rectangle().fill(RatsColor.success.opacity(0.78)).frame(width: proxy.size.width * Double(goal.voran) / Double(total))
            }
            .clipShape(Capsule())
        }
        .frame(height: 11)
    }
}

private struct FlowLayout: Layout {
    let spacing: CGFloat

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let width = proposal.width ?? 0
        var x: CGFloat = 0
        var y: CGFloat = 0
        var rowHeight: CGFloat = 0
        for view in subviews {
            let size = view.sizeThatFits(.unspecified)
            if x > 0, x + size.width > width { x = 0; y += rowHeight + spacing; rowHeight = 0 }
            x += size.width + spacing
            rowHeight = max(rowHeight, size.height)
        }
        return CGSize(width: width, height: y + rowHeight)
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        var x = bounds.minX
        var y = bounds.minY
        var rowHeight: CGFloat = 0
        for view in subviews {
            let size = view.sizeThatFits(.unspecified)
            if x > bounds.minX, x + size.width > bounds.maxX { x = bounds.minX; y += rowHeight + spacing; rowHeight = 0 }
            view.place(at: CGPoint(x: x, y: y), anchor: .topLeading, proposal: ProposedViewSize(size))
            x += size.width + spacing
            rowHeight = max(rowHeight, size.height)
        }
    }
}

private extension Collection {
    subscript(safe index: Index) -> Element? { indices.contains(index) ? self[index] : nil }
}
