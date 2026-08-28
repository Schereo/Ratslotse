import RatslotseAPI
import RatslotseDesign
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
    let emerging: [EmergingTopic]
    let fieldLabels: [String: String]

    enum CodingKeys: String, CodingKey {
        case quarters, fields, money, emerging
        case byField = "by_field"
        case fieldLabels = "field_labels"
    }
}

private struct EmergingTopic: Decodable, Sendable, Identifiable {
    var id: String { tag }
    let tag: String
    let n: Int
}

private struct PartyAnalysisResponse: Decodable, Sendable {
    let coverage: Coverage
    let successRates: [PartySuccess]
    let contention: [Contention]
    let alliances: [Alliance]
    let fieldLabels: [String: String]

    enum CodingKeys: String, CodingKey {
        case coverage, contention, alliances
        case successRates = "success_rates"
        case fieldLabels = "field_labels"
    }
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
    let n: Int
    let committees: Int
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
    @State private var section: InsightSection = .trends
    @State private var trends: TrendResponse?
    @State private var parties: PartyAnalysisResponse?
    @State private var members: [CouncilMember] = []
    @State private var finance: FinanceResponse?
    @State private var goals: [CouncilGoal] = []
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
        .task { await load() }
    }

    private var sectionPicker: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 7) {
                ForEach(InsightSection.allCases) { item in
                    Button { withAnimation(.easeOut(duration: 0.18)) { section = item } } label: {
                        Text(item.rawValue)
                            .font(RatsFont.body(12, weight: .semibold))
                            .foregroundStyle(section == item ? RatsColor.primaryText : RatsColor.bodyText)
                            .padding(.horizontal, 13)
                            .frame(height: 34)
                            .background(section == item ? RatsColor.primary : RatsColor.card)
                            .overlay(Capsule().stroke(section == item ? Color.clear : RatsColor.border))
                            .clipShape(Capsule())
                    }
                    .buttonStyle(.plain)
                }
            }
        }
    }

    @ViewBuilder
    private var trendsView: some View {
        if let trends, !trends.quarters.isEmpty {
            analysisIntro(
                title: "Was bewegt den Rat?",
                detail: "Die letzten Quartale zeigen Aktivität und erkanntes Finanzvolumen – ohne daraus automatisch Wirkung abzuleiten."
            )
            RatsSectionPanel("Beschlüsse je Quartal", detail: "Tippe in der Web-Version auf einen Balken für die Beschlüsse des Zeitraums.", symbol: nil) {
                let totals = trends.quarters.indices.map { index in
                    trends.fields.reduce(0) { $0 + (trends.byField[$1]?[safe: index] ?? 0) }
                }
                MiniBarChart(labels: trends.quarters.map(shortQuarter), values: totals.map(Double.init), color: RatsColor.primary)
            }
            RatsSectionPanel("Erkanntes Finanzvolumen", detail: "Grobe Größenordnung aus den Beschlusstexten; kein offizieller Haushalt.", symbol: nil) {
                MiniBarChart(labels: trends.quarters.map(shortQuarter), values: trends.money, color: RatsColor.success)
            }
            if !trends.emerging.isEmpty {
                RatsSectionPanel("Neue Themen", detail: "Begriffe, die zuletzt häufiger auftauchen.", symbol: nil) {
                    FlowLayout(spacing: 7) {
                        ForEach(trends.emerging) { topic in
                            Text("\(topic.tag) · \(topic.n)")
                                .font(RatsFont.body(11, weight: .semibold))
                                .foregroundStyle(RatsColor.primary)
                                .padding(.horizontal, 10)
                                .padding(.vertical, 6)
                                .background(RatsColor.primary.opacity(0.08))
                                .clipShape(Capsule())
                        }
                    }
                }
            }
        } else {
            empty("Noch keine Trends", "Es sind noch nicht genug datierte, klassifizierte Beschlüsse vorhanden.")
        }
    }

    @ViewBuilder
    private var partiesView: some View {
        if let parties, parties.coverage.withFactions > 0 {
            analysisIntro(
                title: "Wer bringt welche Anträge ein?",
                detail: "Grundlage sind \(parties.coverage.withFactions) von \(parties.coverage.total) klassifizierten Beschlüssen – nicht das individuelle Abstimmungsverhalten."
            )
            RatsSectionPanel("Erfolgsquote der Anträge", detail: "Grün angenommen, rot abgelehnt, orange vertagt.", symbol: nil) {
                VStack(spacing: 13) {
                    ForEach(parties.successRates) { row in
                        PartyOutcomeRow(row: row)
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

            let shown = filteredMembers
            MonoKicker("Personen", trailing: "\(shown.count)")
            ForEach(shown) { member in
                NavigationLink(value: AppRoute.person(slug: member.slug)) {
                    HStack(spacing: 12) {
                        Circle()
                            .fill(RatsColor.primary.opacity(0.10))
                            .frame(width: 38, height: 38)
                            .overlay(
                                Text(initials(member.name))
                                    .font(RatsFont.body(11, weight: .bold))
                                    .foregroundStyle(RatsColor.primary)
                            )
                        VStack(alignment: .leading, spacing: 3) {
                            Text(member.name).font(RatsFont.body(14, weight: .semibold))
                            Text("\(member.n) Sitzungen · \(member.committees) Gremien")
                                .font(RatsFont.body(10.5)).foregroundStyle(RatsColor.secondary)
                        }
                        Spacer()
                        Text(member.party ?? member.organisation ?? (member.art == "beratend" ? "beratend" : "parteilos"))
                            .font(RatsFont.body(9.5, weight: .semibold))
                            .foregroundStyle(RatsColor.primary)
                            .padding(.horizontal, 7).padding(.vertical, 4)
                            .background(RatsColor.primary.opacity(0.08)).clipShape(Capsule())
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .ratsCard()
                }
                .buttonStyle(.plain)
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
                            MetricBar(
                                label: finance.fieldLabels[row.field] ?? row.field,
                                value: row.total / maximum,
                                valueLabel: formatEuro(row.total),
                                color: RatsColor.success
                            )
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
                    .buttonStyle(.plain)
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
                    }
                    GoalBalanceBar(goal: goal)
                    HStack {
                        Text("\(goal.bremst) bremsen").foregroundStyle(RatsColor.danger)
                        Spacer()
                        Text("\(goal.neutral) neutral").foregroundStyle(RatsColor.muted)
                        Spacer()
                        Text("\(goal.voran) voran").foregroundStyle(RatsColor.success)
                    }
                    .font(RatsFont.body(9.5, weight: .semibold))
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
        guard !needle.isEmpty else { return Array(members.prefix(80)) }
        return members.filter {
            $0.name.localizedCaseInsensitiveContains(needle)
                || $0.party?.localizedCaseInsensitiveContains(needle) == true
                || $0.organisation?.localizedCaseInsensitiveContains(needle) == true
        }
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
                emerging: [EmergingTopic(tag: "Velorouten", n: 5)],
                fieldLabels: ["verkehr": "Verkehr", "soziales": "Soziales"]
            )
            return
        }
#endif
        do {
            async let trendRequest: TrendResponse = model.api.get("/api/council/trends")
            async let partyRequest: PartyAnalysisResponse = model.api.get("/api/council/analysis")
            async let memberRequest: MembersResponse = model.api.get("/api/council/members")
            async let financeRequest: FinanceResponse = model.api.get("/api/council/finance")
            async let goalRequest: GoalsResponse = model.api.get("/api/council/goals")
            let responses = try await (trendRequest, partyRequest, memberRequest, financeRequest, goalRequest)
            trends = responses.0
            parties = responses.1
            members = responses.2.members
            finance = responses.3
            goals = responses.4.goals
            error = nil
        } catch { self.error = error.localizedDescription }
    }

    private func shortQuarter(_ raw: String) -> String {
        let parts = raw.split(separator: "-")
        guard parts.count == 2 else { return raw }
        return "\(parts[1]) ’\(parts[0].suffix(2))"
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
