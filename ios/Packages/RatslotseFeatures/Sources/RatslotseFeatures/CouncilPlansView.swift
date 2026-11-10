import RatslotseAPI
import RatslotseDesign
import SwiftUI

// PLÄNE DER STADT (docs/plan-ziele-plaene.md, Phase 5): die Übersicht und die
// Planseite der Web-App. In der Analyse steht sie an der Stelle des Reiters
// „Ziele", solange der Schalter `plaene` an ist (`CouncilInsightsView`).
//
// Wie im Web gilt: keine Note, keine Quote, kein Ampelrot. Der Berichtsstand
// ist eine Aussage über die Berichte, nicht über die Arbeit — darum trägt er
// hier einen gefüllten oder einen leeren Punkt und keine Warnfarbe. Der Stand
// einer Maßnahme steht im WORTLAUT der Stadt; `status_norm` färbt nur.
//
// Alle Sätze kommen vom Server. Die App setzt sie, sie formuliert nichts.

// MARK: - Antwortformen (api/openapi.json: Plans, PlanDetail)

private struct CouncilPlansResponse: Decodable, Sendable {
    let asOfLabel: String
    let count: Int
    let groups: [CouncilPlanGroup]
    let followUps: [CouncilPlanFollowUp]
    let followUpCaveat: String

    enum CodingKeys: String, CodingKey {
        case count, groups
        case asOfLabel = "as_of_label"
        case followUps = "follow_ups"
        case followUpCaveat = "follow_up_caveat"
    }
}

private struct CouncilPlanGroup: Decodable, Sendable, Identifiable {
    var id: String { key }
    let key: String
    let label: String
    let plans: [CouncilPlanCard]
}

private struct CouncilPlanCard: Decodable, Sendable, Identifiable {
    var id: String { key }
    let key: String
    let title: String
    let kicker: String
    let reportNote: String?
    let reportState: CouncilPlanReportState
    let statusBrief: CouncilPlanStatusBrief?
    let measureCount: Int?

    enum CodingKeys: String, CodingKey {
        case key, title, kicker
        case reportNote = "report_note"
        case reportState = "report_state"
        case statusBrief = "status_brief"
        case measureCount = "measure_count"
    }
}

private struct CouncilPlanReportState: Decodable, Sendable {
    let state: String
    let label: String
    let hint: String?
}

private struct CouncilPlanStatusCount: Decodable, Sendable, Identifiable {
    var id: String { statusRaw }
    let statusRaw: String
    let statusNorm: String
    let count: Int

    enum CodingKeys: String, CodingKey {
        case count
        case statusRaw = "status_raw"
        case statusNorm = "status_norm"
    }
}

private struct CouncilPlanStatusBrief: Decodable, Sendable {
    let asOfLabel: String
    let total: Int
    let complete: Bool
    let counts: [CouncilPlanStatusCount]

    enum CodingKeys: String, CodingKey {
        case total, complete, counts
        case asOfLabel = "as_of_label"
    }
}

private struct CouncilPlanFollowUp: Decodable, Sendable, Identifiable {
    var id: String { key }
    let key: String
    let title: String
    let fact: String
    let question: String
}

private struct CouncilPlanDetail: Decodable, Sendable {
    let key: String
    let title: String
    let office: String?
    let kicker: String
    let statusLabel: String
    let horizonNote: String?
    let reviewLabel: String?
    let adoption: CouncilPlanDecisionRef?
    let website: String?
    let since: CouncilPlanFact?
    let remaining: CouncilPlanFact?
    let reportState: CouncilPlanReportState
    let reportNote: String?
    let reportCaveat: String?
    let reportCount: Int
    let measures: CouncilPlanMeasures?
    let cityStatus: CouncilPlanCityStatus?
    let indicators: [CouncilPlanIndicator]
    let review: CouncilPlanReview?
    let timeline: CouncilPlanTimeline
    let decisionGroups: [CouncilPlanDecisionGroup]

    enum CodingKeys: String, CodingKey {
        case key, title, office, kicker, adoption, website, since, remaining, measures, indicators, review, timeline
        case statusLabel = "status_label"
        case horizonNote = "horizon_note"
        case reviewLabel = "review_label"
        case reportState = "report_state"
        case reportNote = "report_note"
        case reportCaveat = "report_caveat"
        case reportCount = "report_count"
        case cityStatus = "city_status"
        case decisionGroups = "decision_groups"
    }
}

private struct CouncilPlanDecisionRef: Decodable, Sendable {
    let date: String
    let committee: String
    let mode: String
    let templateNumber: String?
    let url: String?
    let vote: String?

    enum CodingKeys: String, CodingKey {
        case date, committee, mode, url, vote
        case templateNumber = "template_number"
    }
}

private struct CouncilPlanFact: Decodable, Sendable {
    let label: String
    let value: String
}

private struct CouncilPlanMeasures: Decodable, Sendable {
    let count: Int
    let countNote: String?
    let statusCount: Int
    let statusAsOfLabel: String?
    let statusByModel: Bool
    let source: CouncilPlanMeasureSource
    let groups: [CouncilPlanMeasureGroup]

    enum CodingKeys: String, CodingKey {
        case count, source, groups
        case countNote = "count_note"
        case statusCount = "status_count"
        case statusAsOfLabel = "status_as_of_label"
        case statusByModel = "status_by_model"
    }
}

private struct CouncilPlanMeasureSource: Decodable, Sendable {
    let label: String
    let url: String
    let asOfLabel: String?

    enum CodingKeys: String, CodingKey {
        case label, url
        case asOfLabel = "as_of_label"
    }
}

private struct CouncilPlanMeasureGroup: Decodable, Sendable {
    let field: String?
    let measures: [CouncilPlanMeasure]
}

private struct CouncilPlanMeasure: Decodable, Sendable, Identifiable {
    var id: String { code }
    let code: String
    let title: String
    let statusRaw: String?
    let statusNorm: String?
    let statusQuote: String?
    let decisionCount: Int

    enum CodingKeys: String, CodingKey {
        case code, title
        case statusRaw = "status_raw"
        case statusNorm = "status_norm"
        case statusQuote = "status_quote"
        case decisionCount = "decision_count"
    }
}

private struct CouncilPlanStatusNote: Decodable, Sendable {
    let text: String
}

private struct CouncilPlanCityStatus: Decodable, Sendable {
    let asOfLabel: String
    let originLabel: String
    let total: Int
    let complete: Bool
    let counts: [CouncilPlanStatusCount]
    let sourceLabel: String
    let sourceUrl: String?
    let templateNumber: String?
    let notes: [CouncilPlanStatusNote]

    enum CodingKeys: String, CodingKey {
        case total, complete, counts, notes
        case asOfLabel = "as_of_label"
        case originLabel = "origin_label"
        case sourceLabel = "source_label"
        case sourceUrl = "source_url"
        case templateNumber = "template_number"
    }
}

private struct CouncilPlanIndicatorRow: Decodable, Sendable, Identifiable {
    var id: Int { year }
    let year: Int
    let target: Double?
    let actual: Double?
    let actualChange: Double?

    enum CodingKeys: String, CodingKey {
        case year, target, actual
        case actualChange = "actual_change"
    }
}

private struct CouncilPlanIndicatorNote: Decodable, Sendable {
    let text: String
}

private struct CouncilPlanIndicator: Decodable, Sendable, Identifiable {
    var id: String { key }
    let key: String
    let label: String
    let unit: String
    let baselineYear: Int
    let baselineValue: Double
    let baselineLabel: String
    let rows: [CouncilPlanIndicatorRow]
    let notes: [CouncilPlanIndicatorNote]

    enum CodingKeys: String, CodingKey {
        case key, label, unit, rows, notes
        case baselineYear = "baseline_year"
        case baselineValue = "baseline_value"
        case baselineLabel = "baseline_label"
    }
}

private struct CouncilPlanTemplateRef: Decodable, Sendable {
    let templateNumber: String
    let title: String?
    let url: String?

    enum CodingKeys: String, CodingKey {
        case title, url
        case templateNumber = "template_number"
    }
}

private struct CouncilPlanNeighbour: Decodable, Sendable {
    let key: String
    let title: String
    let adopted: Bool
}

private struct CouncilPlanReviewStatement: Decodable, Sendable {
    let kind: String
    let text: String
    let sourceLabel: String
    let templateNumber: String?

    enum CodingKeys: String, CodingKey {
        case kind, text
        case sourceLabel = "source_label"
        case templateNumber = "template_number"
    }
}

private struct CouncilPlanReview: Decodable, Sendable {
    let planned: [CouncilPlanFact]
    let evaluation: CouncilPlanTemplateRef?
    let noEvaluationNote: String?
    let statements: [CouncilPlanReviewStatement]
    let continuedBy: CouncilPlanNeighbour?
    let hasStatus: Bool

    enum CodingKeys: String, CodingKey {
        case planned, evaluation, statements
        case noEvaluationNote = "no_evaluation_note"
        case continuedBy = "continued_by"
        case hasStatus = "has_status"
    }
}

private struct CouncilPlanStation: Decodable, Sendable {
    let date: String
    let dateEnd: String?
    let kind: String
    let title: String
    let templateNumber: String?
    let oral: Bool
    let committees: [String]
    let decisionId: Int?

    enum CodingKeys: String, CodingKey {
        case date, kind, title, oral, committees
        case dateEnd = "date_end"
        case templateNumber = "template_number"
        case decisionId = "decision_id"
    }
}

private struct CouncilPlanTimeline: Decodable, Sendable {
    let span: String
    let stations: [CouncilPlanStation]
}

private struct CouncilPlanDecisionEntry: Decodable, Sendable {
    let title: String
    let date: String
    let committee: String?
    let decisionId: Int?
    let outcome: String?
    let templateNumber: String?
    let quote: String?

    enum CodingKeys: String, CodingKey {
        case title, date, committee, outcome, quote
        case decisionId = "decision_id"
        case templateNumber = "template_number"
    }
}

private struct CouncilPlanDecisionGroup: Decodable, Sendable, Identifiable {
    var id: String { key }
    let key: String
    let label: String
    let entries: [CouncilPlanDecisionEntry]
}

private struct CouncilPlanSelection: Identifiable {
    let key: String
    var id: String { key }
}

// MARK: - Farbton und Zahlen

/// Füllung nach `status_norm` — nur ein Farbton zum Wort der Stadt, keine Wertung.
private func planStatusFill(_ norm: String?) -> Color {
    switch norm {
    case "done": RatsColor.success.opacity(0.78)
    case "in_progress": RatsColor.primary.opacity(0.62)
    case "started": RatsColor.primary.opacity(0.2)
    case "paused": RatsColor.muted.opacity(0.32)
    default: Color.clear
    }
}

private func planStatusStroke(_ norm: String?) -> Color {
    switch norm {
    case "done": RatsColor.success.opacity(0.7)
    case "in_progress", "started": RatsColor.primary.opacity(0.5)
    default: RatsColor.muted.opacity(0.45)
    }
}

private let planLocale = Locale(identifier: "de_DE")

private func planNumber(_ value: Double) -> String {
    value.formatted(.number.locale(planLocale).precision(.fractionLength(0)))
}

/// `-0.179` → „−17,9 %". Der Server liefert den Anteil ungerundet; gerundet wird hier, einmal.
private func planChange(_ value: Double) -> String {
    (value * 100).formatted(.number.locale(planLocale).precision(.fractionLength(1)).sign(strategy: .always()))
        .replacingOccurrences(of: "-", with: "−") + " %"
}

/// Ein Bericht liegt vor: gefüllter Punkt. Sonst ein leerer — keine Warnfarbe,
/// denn die Lücke sagt etwas über die Berichte, nicht über die Arbeit.
private struct CouncilPlanReportDot: View {
    let state: String

    var body: some View {
        let filled = ["reported", "evaluated", "continued"].contains(state)
        Circle()
            .fill(filled ? RatsColor.primary : Color.clear)
            .overlay(Circle().stroke(filled ? RatsColor.primary : RatsColor.muted, lineWidth: 1.2))
            .frame(width: 8, height: 8)
            .accessibilityHidden(true)
    }
}

/// Die Verteilung als ein Band. Ordnet die Stadt nur einen Teil ein
/// (`total` größer als die Summe), bleibt der Rest sichtbar leer.
private struct CouncilPlanStatusStrip: View {
    let counts: [CouncilPlanStatusCount]
    let total: Int

    var body: some View {
        let shown = counts.filter { $0.count > 0 }
        let sum = shown.reduce(0) { $0 + $1.count }
        let whole = max(1, max(total, sum))
        GeometryReader { proxy in
            let gaps = CGFloat(max(0, shown.count - (sum < whole ? 0 : 1))) * 1.5
            let width = max(0, proxy.size.width - gaps)
            HStack(spacing: 1.5) {
                ForEach(shown) { item in
                    Rectangle()
                        .fill(planStatusFill(item.statusNorm))
                        .overlay(Rectangle().stroke(planStatusStroke(item.statusNorm), lineWidth: 0.5))
                        .frame(width: max(2, width * CGFloat(item.count) / CGFloat(whole)))
                }
                if sum < whole { Rectangle().fill(RatsColor.separator) }
            }
        }
        .frame(height: 8)
        .clipShape(Capsule())
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(shown.map { "\($0.count) \($0.statusRaw)" }.joined(separator: ", "))
    }
}

private struct CouncilPlanStatusChip: View {
    let raw: String
    let norm: String?

    var body: some View {
        HStack(spacing: 5) {
            RoundedRectangle(cornerRadius: 2)
                .fill(planStatusFill(norm))
                .overlay(RoundedRectangle(cornerRadius: 2).stroke(planStatusStroke(norm), lineWidth: 1))
                .frame(width: 9, height: 9)
            Text(raw)
                .font(RatsFont.body(11, weight: .medium))
                .foregroundStyle(RatsColor.bodyText)
                .multilineTextAlignment(.leading)
        }
        .padding(.horizontal, 8)
        .padding(.vertical, 4)
        .background(RatsColor.separator.opacity(0.7))
        .clipShape(RoundedRectangle(cornerRadius: 9))
    }
}

private struct CouncilPlanLink: View {
    let title: String
    let address: String?

    var body: some View {
        if let address, let url = URL(string: address) {
            Link(destination: url) {
                HStack(alignment: .firstTextBaseline, spacing: 4) {
                    Text(title).multilineTextAlignment(.leading)
                    RatsIcon(.externalLink, size: 11)
                }
                .font(RatsFont.body(12, weight: .semibold))
                .foregroundStyle(RatsColor.primary)
            }
        }
    }
}

// MARK: - Übersicht

struct CouncilPlansSection: View {
    let model: AppModel
    @State private var response: CouncilPlansResponse?
    @State private var isLoading = true
    @State private var error: String?
    @State private var selected: CouncilPlanSelection? = {
#if DEBUG
        // Sichtprobe ohne Simulator-Steuerung: `RATSLOTSE_DEBUG_PLAN=<key>` öffnet die Planseite.
        if let key = ProcessInfo.processInfo.environment["RATSLOTSE_DEBUG_PLAN"] { return CouncilPlanSelection(key: key) }
#endif
        return nil
    }()

    var body: some View {
        Group {
            if let response {
                content(response)
            } else if isLoading {
                RatsLoadingState(message: "Pläne werden geladen …")
            } else if let error {
                ErrorCard(message: error) { Task { await load() } }
            }
        }
        .task { await load() }
        .sheet(item: $selected) { item in
            CouncilPlanSheet(model: model, key: item.key)
                .ratsLargeSheet()
        }
    }

    @ViewBuilder
    private func content(_ response: CouncilPlansResponse) -> some View {
        VStack(alignment: .leading, spacing: 5) {
            Text("Pläne der Stadt").font(RatsFont.title(18))
            Text("Was der Rat beschlossen hat, was die Verwaltung darüber berichtet und wie die Stadt den Stand selbst einordnet. Ratslotse vergibt keine Note und rechnet keine Quote.")
                .font(RatsFont.body(11.5))
                .foregroundStyle(RatsColor.secondary)
                .lineSpacing(2)
            Text("\(response.count) Pläne · Stand \(response.asOfLabel)")
                .font(RatsFont.body(10.5))
                .foregroundStyle(RatsColor.muted)
                .padding(.top, 2)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(14)
        .background(RatsColor.primary.opacity(0.06))
        .overlay(RoundedRectangle(cornerRadius: 15).stroke(RatsColor.primary.opacity(0.16)))
        .clipShape(RoundedRectangle(cornerRadius: 15))

        ForEach(response.groups) { group in
            if !group.plans.isEmpty {
                MonoKicker(group.label, trailing: "\(group.plans.count)")
                    .padding(.top, 6)
                ForEach(group.plans) { plan in
                    Button { selected = CouncilPlanSelection(key: plan.key) } label: {
                        CouncilPlanCardView(plan: plan).ratsCard()
                    }
                    .buttonStyle(RatsPlainButtonStyle())
                    .accessibilityHint("Öffnet den Plan")
                }
            }
        }

        if !response.followUps.isEmpty {
            VStack(alignment: .leading, spacing: 10) {
                MonoKicker("Wo man nachfragen kann", trailing: "\(response.followUps.count)")
                Text(response.followUpCaveat)
                    .font(RatsFont.body(11.5))
                    .foregroundStyle(RatsColor.secondary)
                    .lineSpacing(2)
                ForEach(response.followUps) { item in
                    Divider().overlay(RatsColor.separator)
                    VStack(alignment: .leading, spacing: 4) {
                        Button { selected = CouncilPlanSelection(key: item.key) } label: {
                            Text(item.title)
                                .font(RatsFont.body(13, weight: .semibold))
                                .foregroundStyle(RatsColor.text)
                                .multilineTextAlignment(.leading)
                        }
                        .buttonStyle(RatsPlainButtonStyle())
                        Text(item.fact)
                            .font(RatsFont.body(11.5))
                            .foregroundStyle(RatsColor.secondary)
                        Button { model.navigation.append(.question(prefill: item.question, share: nil)) } label: {
                            HStack(spacing: 4) {
                                Text("Frag den Rat danach")
                                RatsIcon(.arrowRight, size: 12)
                            }
                            .font(RatsFont.body(12, weight: .semibold))
                            .foregroundStyle(RatsColor.primary)
                            .frame(minHeight: 30)
                        }
                        .buttonStyle(RatsPlainButtonStyle())
                    }
                }
            }
            .ratsCard()
            .padding(.top, 6)
        }
    }

    private func load() async {
        isLoading = true
        defer { isLoading = false }
#if DEBUG
        if ProcessInfo.processInfo.environment["RATSLOTSE_DEBUG_ANALYSIS_FIXTURE"] == "1" {
            do {
                response = try JSONDecoder().decode(CouncilPlansResponse.self, from: Data(CouncilPlanFixture.overview.utf8))
            } catch { self.error = "Fixture: \(error)" }
            return
        }
#endif
        do {
            let loaded: CouncilPlansResponse = try await model.api.get("/api/council/plans")
            response = loaded
            error = nil
        } catch { self.error = error.localizedDescription }
    }
}

private struct CouncilPlanCardView: View {
    let plan: CouncilPlanCard

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(alignment: .top, spacing: 8) {
                VStack(alignment: .leading, spacing: 5) {
                    MonoKicker(plan.kicker)
                    Text(plan.title)
                        .font(RatsFont.body(14.5, weight: .semibold))
                        .foregroundStyle(RatsColor.text)
                        .multilineTextAlignment(.leading)
                }
                Spacer(minLength: 4)
                RatsIcon(.chevronRight, size: 15)
                    .foregroundStyle(RatsColor.muted)
                    .padding(.top, 2)
            }
            HStack(alignment: .firstTextBaseline, spacing: 6) {
                CouncilPlanReportDot(state: plan.reportState.state)
                Text(plan.reportState.label)
                    .font(RatsFont.body(11.5, weight: .semibold))
                    .foregroundStyle(RatsColor.bodyText)
            }
            if let note = plan.reportNote ?? plan.reportState.hint {
                Text(note)
                    .font(RatsFont.body(11))
                    .foregroundStyle(RatsColor.secondary)
                    .multilineTextAlignment(.leading)
            }
            if let brief = plan.statusBrief {
                let sum = brief.counts.reduce(0) { $0 + $1.count }
                CouncilPlanStatusStrip(counts: brief.counts, total: brief.total)
                Text(brief.complete
                     ? "\(brief.total) Maßnahmen · Stand laut Stadt \(brief.asOfLabel)"
                     : "\(sum) von \(brief.total) Maßnahmen eingeordnet · Stand laut Stadt \(brief.asOfLabel)")
                    .font(RatsFont.body(10.5))
                    .foregroundStyle(RatsColor.muted)
            } else if let count = plan.measureCount {
                Text("\(count) Maßnahmen in der Liste")
                    .font(RatsFont.body(10.5))
                    .foregroundStyle(RatsColor.muted)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

// MARK: - Planseite

private struct CouncilPlanSheet: View {
    let model: AppModel
    @State private var key: String
    @Environment(\.dismiss) private var dismiss
    @State private var plan: CouncilPlanDetail?
    @State private var isLoading = true
    @State private var error: String?
    @State private var openFields: Set<String> = []

    init(model: AppModel, key: String) {
        self.model = model
        _key = State(initialValue: key)
    }

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                RatsSheetHeader("Plan der Stadt", leadingTitle: "Schließen", leadingAction: { dismiss() })
                ScrollViewReader { proxy in
                    ScrollView {
                        LazyVStack(alignment: .leading, spacing: 14) {
                            if isLoading { RatsLoadingState(message: "Plan wird geladen …") }
                            if let error { ErrorCard(message: error) { Task { await load() } } }
                            if let plan { sections(plan) }
                        }
                        .frame(maxWidth: 760, alignment: .leading)
                        .padding(18)
                    }
                    .background(RatsColor.page)
#if DEBUG
                    // Sichtprobe: `RATSLOTSE_DEBUG_PLAN_SECTION=review|timeline|status|measures|decisions`
                    // rollt zum Abschnitt; bei `measures` stehen alle Handlungsfelder offen.
                    .task(id: plan?.key) {
                        guard let plan, let anchor = ProcessInfo.processInfo.environment["RATSLOTSE_DEBUG_PLAN_SECTION"] else { return }
                        if anchor == "measures" { openFields = Set((plan.measures?.groups ?? []).map { $0.field ?? "Maßnahmen" }) }
                        try? await Task.sleep(for: .milliseconds(500))
                        proxy.scrollTo(anchor, anchor: .top)
                    }
#endif
                }
            }
            .toolbar(.hidden, for: .navigationBar)
        }
        .task { await load() }
    }

    private func load() async {
        isLoading = true
        error = nil
        defer { isLoading = false }
#if DEBUG
        if ProcessInfo.processInfo.environment["RATSLOTSE_DEBUG_ANALYSIS_FIXTURE"] == "1" {
            do {
                plan = try JSONDecoder().decode(CouncilPlanDetail.self, from: Data(CouncilPlanFixture.detail.utf8))
            } catch { self.error = "Fixture: \(error)" }
            return
        }
#endif
        do {
            let loaded: CouncilPlanDetail = try await model.api.get("/api/council/plan/\(key)")
            plan = loaded
        } catch { self.error = error.localizedDescription }
    }

    /// Blatt zu, Beschluss im Stapel der App auf — wie in der Analyse.
    private func open(decision id: Int) {
        dismiss()
        model.navigation.append(.decision(id: id))
    }

    @ViewBuilder
    private func sections(_ plan: CouncilPlanDetail) -> some View {
        header(plan)
        facts(plan)
        if let review = plan.review { reviewCard(review).id("review") }
        timelineCard(plan).id("timeline")
        if let status = plan.cityStatus { statusCard(status).id("status") }
        ForEach(plan.indicators) { indicatorCard($0) }
        if let measures = plan.measures { measuresCard(measures).id("measures") }
        decisionsCard(plan.decisionGroups.filter { !$0.entries.isEmpty }).id("decisions")
        Text("Gefunden über die Titel und Vorlagen der Tagesordnungspunkte im Ratsinformationssystem. Nichtöffentliche Sitzungen, Mitteilungen ohne Vorlage und Berichte außerhalb des Ratsinformationssystems sieht Ratslotse nicht.")
            .font(RatsFont.body(11))
            .foregroundStyle(RatsColor.secondary)
            .lineSpacing(2)
    }

    private func header(_ plan: CouncilPlanDetail) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            MonoKicker(plan.kicker)
            Text(plan.title)
                .font(RatsFont.title(22))
                .foregroundStyle(RatsColor.text)
            if let office = plan.office {
                Text(office).font(RatsFont.body(12.5)).foregroundStyle(RatsColor.secondary)
            }
            if let adoption = plan.adoption {
                Text(([adoption.mode == "noted" ? "Zur Kenntnis genommen" : "Beschlossen", adoption.committee,
                       RatsDate.short(adoption.date), adoption.vote.map(voteLabel), adoption.templateNumber] as [String?])
                    .compactMap { $0 }.joined(separator: " · "))
                    .font(RatsFont.body(12, weight: .medium))
                    .foregroundStyle(RatsColor.bodyText)
            }
            Text(plan.statusLabel.uppercased())
                .font(RatsFont.mono(9.5, weight: .semibold))
                .tracking(0.5)
                .foregroundStyle(RatsColor.muted)
            if let note = plan.horizonNote {
                Text("Laufzeit laut Plan: \(note)")
                    .font(RatsFont.body(11.5))
                    .foregroundStyle(RatsColor.secondary)
            }
            CouncilPlanLink(title: "Vorlage im Ratsinformationssystem", address: plan.adoption?.url)
            CouncilPlanLink(title: "Seite der Stadt", address: plan.website)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(16)
        .background(RatsColor.stage)
        .overlay(RoundedRectangle(cornerRadius: RatsRadius.panel).stroke(RatsColor.border))
        .clipShape(RoundedRectangle(cornerRadius: RatsRadius.panel))
    }

    private func facts(_ plan: CouncilPlanDetail) -> some View {
        var items: [CouncilPlanFact] = [plan.since, plan.remaining].compactMap { $0 }
        if let review = plan.reviewLabel { items.append(CouncilPlanFact(label: "Nächste Überprüfung", value: review)) }
        if let measures = plan.measures { items.append(CouncilPlanFact(label: "Maßnahmen", value: "\(measures.count)")) }
        return LazyVGrid(columns: [GridItem(.adaptive(minimum: 138), spacing: 8)], alignment: .leading, spacing: 8) {
            ForEach(Array(items.enumerated()), id: \.offset) { _, fact in
                VStack(alignment: .leading, spacing: 4) {
                    Text(fact.label.uppercased())
                        .font(RatsFont.mono(9))
                        .tracking(0.5)
                        .foregroundStyle(RatsColor.muted)
                    Text(fact.value)
                        .font(RatsFont.title(17))
                        .foregroundStyle(RatsColor.text)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(11)
                .background(RatsColor.card)
                .overlay(RoundedRectangle(cornerRadius: RatsRadius.card).stroke(RatsColor.border))
                .clipShape(RoundedRectangle(cornerRadius: RatsRadius.card))
            }
        }
    }

    private func part(_ label: String) -> some View {
        Text(label.uppercased())
            .font(RatsFont.mono(9))
            .tracking(0.5)
            .foregroundStyle(RatsColor.muted)
            .padding(.top, 2)
    }

    private func quote(_ statement: CouncilPlanReviewStatement) -> some View {
        VStack(alignment: .leading, spacing: 3) {
            Text("„\(statement.text)“")
                .font(RatsFont.body(12.5))
                .foregroundStyle(RatsColor.bodyText)
                .lineSpacing(2)
            Text(([statement.sourceLabel, statement.templateNumber] as [String?]).compactMap { $0 }.joined(separator: " · "))
                .font(RatsFont.mono(9.5))
                .foregroundStyle(RatsColor.muted)
        }
        .padding(.leading, 10)
        .overlay(alignment: .leading) { Rectangle().fill(RatsColor.border).frame(width: 2) }
    }

    private func reviewCard(_ review: CouncilPlanReview) -> some View {
        let results = review.statements.filter { $0.kind == "result" }
        let limits = review.statements.filter { $0.kind == "limit" }
        return VStack(alignment: .leading, spacing: 9) {
            MonoKicker("Rückblick", trailing: "Nach Angaben der Verwaltung")
            if !review.planned.isEmpty {
                part("Was vorgesehen war")
                Text(review.planned.map { "\($0.label): \($0.value)" }.joined(separator: " · "))
                    .font(RatsFont.body(12.5))
                    .foregroundStyle(RatsColor.bodyText)
            }
            Divider().overlay(RatsColor.separator)
            part("Was die Verwaltung meldet")
            if let evaluation = review.evaluation {
                Text("Ausgewertet in: \(evaluation.title ?? evaluation.templateNumber) · \(evaluation.templateNumber)")
                    .font(RatsFont.body(12.5))
                    .foregroundStyle(RatsColor.bodyText)
                CouncilPlanLink(title: "Vorlage öffnen", address: evaluation.url)
            } else if let note = review.noEvaluationNote {
                Text(note).font(RatsFont.body(12.5)).foregroundStyle(RatsColor.secondary).lineSpacing(2)
            }
            ForEach(Array(results.enumerated()), id: \.offset) { _, statement in quote(statement) }
            if review.hasStatus {
                Text("Die Verteilung steht unten unter „Stand laut Stadt“.")
                    .font(RatsFont.body(11.5))
                    .foregroundStyle(RatsColor.secondary)
            }
            if !limits.isEmpty {
                Divider().overlay(RatsColor.separator)
                part("Grenzen, die der Bericht selbst nennt")
                ForEach(Array(limits.enumerated()), id: \.offset) { _, statement in quote(statement) }
            }
            Divider().overlay(RatsColor.separator)
            part("Was weitergeführt wird")
            if let next = review.continuedBy {
                Button {
                    key = next.key
                    plan = nil
                    openFields = []
                    Task { await load() }
                } label: {
                    HStack(alignment: .firstTextBaseline, spacing: 4) {
                        Text(next.adopted ? next.title : "\(next.title) (in Arbeit)")
                            .multilineTextAlignment(.leading)
                        RatsIcon(.arrowRight, size: 12)
                    }
                    .font(RatsFont.body(12.5, weight: .semibold))
                    .foregroundStyle(RatsColor.primary)
                    .frame(minHeight: 30)
                }
                .buttonStyle(RatsPlainButtonStyle())
            } else {
                Text("Kein Nachfolger im Register der Pläne.")
                    .font(RatsFont.body(12.5))
                    .foregroundStyle(RatsColor.secondary)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .ratsCard()
    }

    private func stationKind(_ station: CouncilPlanStation) -> String {
        if station.oral { return "Mündlicher Bericht" }
        switch station.kind {
        case "adoption": return "Beschluss des Plans"
        case "amendment": return "Beschluss zum Plan"
        case "evaluation": return "Auswertung"
        case "preparation": return "Vor dem Beschluss"
        default: return "Bericht"
        }
    }

    private func stationDates(_ station: CouncilPlanStation) -> String {
        let first = RatsDate.short(station.date) ?? station.date
        guard let end = station.dateEnd, end != station.date else { return first }
        return "\(first) – \(RatsDate.short(end) ?? end)"
    }

    private func timelineCard(_ plan: CouncilPlanDetail) -> some View {
        let stations = plan.timeline.stations.sorted { $0.date > $1.date }
        return VStack(alignment: .leading, spacing: 9) {
            MonoKicker("Berichte im Rat",
                       trailing: plan.reportCount > 0
                           ? "\(plan.reportCount) \(plan.reportCount == 1 ? "Bericht" : "Berichte") · \(plan.timeline.span)"
                           : plan.timeline.span)
            HStack(alignment: .firstTextBaseline, spacing: 6) {
                CouncilPlanReportDot(state: plan.reportState.state)
                Text(plan.reportState.label)
                    .font(RatsFont.body(12.5, weight: .semibold))
                    .foregroundStyle(RatsColor.bodyText)
            }
            if let note = plan.reportNote ?? plan.reportState.hint {
                Text(note).font(RatsFont.body(12)).foregroundStyle(RatsColor.bodyText)
            }
            if let caveat = plan.reportCaveat {
                Text(caveat).font(RatsFont.body(11.5)).foregroundStyle(RatsColor.secondary).lineSpacing(2)
            }
            ForEach(Array(stations.enumerated()), id: \.offset) { _, station in
                Divider().overlay(RatsColor.separator)
                let row = VStack(alignment: .leading, spacing: 3) {
                    Text("\(stationDates(station)) · \(stationKind(station))".uppercased())
                        .font(RatsFont.mono(9))
                        .tracking(0.4)
                        .foregroundStyle(RatsColor.muted)
                    Text(station.title)
                        .font(RatsFont.body(12.5, weight: .semibold))
                        .foregroundStyle(RatsColor.text)
                        .multilineTextAlignment(.leading)
                    Text((station.committees + [station.templateNumber].compactMap { $0 }).joined(separator: " · "))
                        .font(RatsFont.body(11))
                        .foregroundStyle(RatsColor.secondary)
                        .multilineTextAlignment(.leading)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                if let id = station.decisionId {
                    Button { open(decision: id) } label: { row }.buttonStyle(RatsPlainButtonStyle())
                } else {
                    row
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .ratsCard()
    }

    private func statusCard(_ status: CouncilPlanCityStatus) -> some View {
        let most = max(1, status.counts.map(\.count).max() ?? 1)
        return VStack(alignment: .leading, spacing: 9) {
            MonoKicker("Stand laut Stadt", trailing: "\(status.originLabel) · Stand \(status.asOfLabel)")
            Text(status.complete
                 ? "So ordnet die Stadt ihre \(status.total) Maßnahmen selbst ein. Ratslotse rechnet daraus keine Quote und vergibt keine Note."
                 : "Die Stadt ordnet nur einen Teil ihrer \(status.total) Maßnahmen ein. Ratslotse rechnet daraus keine Quote und vergibt keine Note.")
                .font(RatsFont.body(11.5))
                .foregroundStyle(RatsColor.secondary)
                .lineSpacing(2)
            ForEach(status.counts) { item in
                VStack(alignment: .leading, spacing: 4) {
                    HStack(alignment: .firstTextBaseline) {
                        Text(item.statusRaw)
                            .font(RatsFont.body(12.5))
                            .foregroundStyle(RatsColor.bodyText)
                            .multilineTextAlignment(.leading)
                        Spacer(minLength: 8)
                        Text("\(item.count)")
                            .font(RatsFont.mono(11, weight: .semibold))
                            .foregroundStyle(RatsColor.text)
                    }
                    GeometryReader { proxy in
                        RoundedRectangle(cornerRadius: 3)
                            .fill(planStatusFill(item.statusNorm))
                            .overlay(RoundedRectangle(cornerRadius: 3).stroke(planStatusStroke(item.statusNorm), lineWidth: 1))
                            .frame(width: item.count == 0 ? 3 : max(3, proxy.size.width * CGFloat(item.count) / CGFloat(most)))
                    }
                    .frame(height: 8)
                }
                .accessibilityElement(children: .ignore)
                .accessibilityLabel("\(item.statusRaw): \(item.count)")
            }
            ForEach(Array(status.notes.enumerated()), id: \.offset) { _, note in
                Text(note.text).font(RatsFont.body(11.5)).foregroundStyle(RatsColor.secondary).lineSpacing(2)
            }
            if let url = status.sourceUrl {
                CouncilPlanLink(title: "Quelle: \(status.sourceLabel)", address: url)
            } else {
                Text(([("Quelle: " + status.sourceLabel), status.templateNumber] as [String?]).compactMap { $0 }.joined(separator: " · "))
                    .font(RatsFont.mono(9.5))
                    .foregroundStyle(RatsColor.muted)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .ratsCard()
    }

    private func indicatorCard(_ indicator: CouncilPlanIndicator) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            MonoKicker("Kennzahl", trailing: "in \(indicator.unit)")
            Text(indicator.label).font(RatsFont.body(13.5, weight: .semibold)).foregroundStyle(RatsColor.text)
            Text("Was der Plan messbar erreichen will, und was die Stadt gemessen hat. Die Zahl steht neben dem Plan — sie sagt nicht, was die Maßnahmen bewirkt haben.")
                .font(RatsFont.body(11.5))
                .foregroundStyle(RatsColor.secondary)
                .lineSpacing(2)
            Grid(alignment: .trailing, horizontalSpacing: 10, verticalSpacing: 6) {
                GridRow {
                    Text("JAHR").gridColumnAlignment(.leading)
                    Text("ZIEL")
                    Text("GEMESSEN")
                    Text("GGÜ. \(String(indicator.baselineYear))")
                }
                .font(RatsFont.mono(8.5))
                .foregroundStyle(RatsColor.muted)
                GridRow {
                    Text(String(indicator.baselineYear))
                    Text("–").foregroundStyle(RatsColor.muted)
                    Text(planNumber(indicator.baselineValue))
                    Text("Ausgang").foregroundStyle(RatsColor.muted)
                }
                ForEach(indicator.rows) { row in
                    GridRow {
                        Text(String(row.year))
                        Text(row.target.map(planNumber) ?? "–").foregroundStyle(RatsColor.secondary)
                        Text(row.actual.map(planNumber) ?? "–").fontWeight(.semibold)
                        Text(row.actualChange.map(planChange) ?? "–")
                    }
                }
            }
            .font(RatsFont.body(11.5).monospacedDigit())
            .foregroundStyle(RatsColor.bodyText)
            Text("\(indicator.baselineLabel).")
                .font(RatsFont.body(11))
                .foregroundStyle(RatsColor.secondary)
            ForEach(Array(indicator.notes.enumerated()), id: \.offset) { _, note in
                Text(note.text).font(RatsFont.body(11)).foregroundStyle(RatsColor.secondary).lineSpacing(2)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .ratsCard()
    }

    private func measuresCard(_ measures: CouncilPlanMeasures) -> some View {
        let alwaysOpen = measures.groups.count == 1 && measures.count <= 20
        return VStack(alignment: .leading, spacing: 9) {
            MonoKicker("Maßnahmen",
                       trailing: "\(measures.count)" + (measures.source.asOfLabel.map { " · Liste vom \($0)" } ?? ""))
            if let note = measures.countNote {
                Text(note).font(RatsFont.body(11.5)).foregroundStyle(RatsColor.secondary).lineSpacing(2)
            }
            if measures.statusCount > 0, let asOf = measures.statusAsOfLabel {
                Text(measures.statusByModel
                     ? "Stand laut Bericht, \(asOf). Ein Sprachmodell hat die Stellen herausgesucht; jedes Zitat steht wörtlich so im Bericht."
                     : "Stand laut Stadt, \(asOf) — im Wortlaut der Stadt.")
                    .font(RatsFont.body(11.5))
                    .foregroundStyle(RatsColor.secondary)
                    .lineSpacing(2)
            }
            ForEach(Array(measures.groups.enumerated()), id: \.offset) { _, group in
                let name = group.field ?? "Maßnahmen"
                let isOpen = alwaysOpen || openFields.contains(name)
                Divider().overlay(RatsColor.separator)
                Button {
                    withAnimation(.easeOut(duration: 0.18)) {
                        if openFields.contains(name) { openFields.remove(name) } else { openFields.insert(name) }
                    }
                } label: {
                    HStack(alignment: .firstTextBaseline, spacing: 8) {
                        Text(name)
                            .font(RatsFont.body(13, weight: .semibold))
                            .foregroundStyle(RatsColor.text)
                            .multilineTextAlignment(.leading)
                        Spacer(minLength: 6)
                        Text("\(group.measures.count)")
                            .font(RatsFont.mono(10))
                            .foregroundStyle(RatsColor.muted)
                        if !alwaysOpen {
                            RatsIcon(.chevronDown, size: 14)
                                .rotationEffect(.degrees(isOpen ? 180 : 0))
                                .foregroundStyle(RatsColor.muted)
                        }
                    }
                    .frame(minHeight: 30)
                }
                .buttonStyle(RatsPlainButtonStyle())
                .disabled(alwaysOpen)
                if isOpen {
                    ForEach(group.measures) { measure in
                        VStack(alignment: .leading, spacing: 4) {
                            HStack(alignment: .firstTextBaseline, spacing: 7) {
                                Text(measure.code)
                                    .font(RatsFont.mono(9.5, weight: .semibold))
                                    .foregroundStyle(RatsColor.muted)
                                Text(measure.title)
                                    .font(RatsFont.body(12.5))
                                    .foregroundStyle(RatsColor.bodyText)
                                    .multilineTextAlignment(.leading)
                            }
                            if let raw = measure.statusRaw {
                                CouncilPlanStatusChip(raw: raw, norm: measure.statusNorm)
                            }
                            if let quoted = measure.statusQuote {
                                Text("„\(quoted)“")
                                    .font(RatsFont.body(11.5))
                                    .foregroundStyle(RatsColor.secondary)
                                    .lineSpacing(2)
                            }
                            if measure.decisionCount > 0 {
                                Text(measure.decisionCount == 1
                                     ? "1 Beschluss nennt diese Maßnahme"
                                     : "\(measure.decisionCount) Beschlüsse nennen diese Maßnahme")
                                    .font(RatsFont.body(10.5))
                                    .foregroundStyle(RatsColor.muted)
                            }
                        }
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .padding(.vertical, 3)
                    }
                }
            }
            Divider().overlay(RatsColor.separator)
            CouncilPlanLink(title: "Quelle: \(measures.source.label)", address: measures.source.url)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .ratsCard()
    }

    @ViewBuilder
    private func decisionsCard(_ groups: [CouncilPlanDecisionGroup]) -> some View {
        if !groups.isEmpty {
            VStack(alignment: .leading, spacing: 9) {
                MonoKicker("Beschlüsse zum Plan")
                ForEach(groups) { group in
                    Text("\(group.label) · \(group.entries.count)")
                        .font(RatsFont.body(12.5, weight: .semibold))
                        .foregroundStyle(RatsColor.text)
                        .padding(.top, 2)
                    ForEach(Array(group.entries.prefix(12).enumerated()), id: \.offset) { _, entry in
                        Divider().overlay(RatsColor.separator)
                        let row = VStack(alignment: .leading, spacing: 4) {
                            Text(entry.title)
                                .font(RatsFont.body(12.5, weight: .medium))
                                .foregroundStyle(RatsColor.text)
                                .multilineTextAlignment(.leading)
                            HStack(alignment: .firstTextBaseline, spacing: 6) {
                                if let outcome = entry.outcome { OutcomeBadge(outcome) }
                                Text(([entry.committee, RatsDate.short(entry.date), entry.templateNumber] as [String?])
                                    .compactMap { $0 }.joined(separator: " · "))
                                    .font(RatsFont.body(11))
                                    .foregroundStyle(RatsColor.secondary)
                                    .multilineTextAlignment(.leading)
                            }
                            if let quoted = entry.quote {
                                Text("„\(quoted)“")
                                    .font(RatsFont.body(11.5))
                                    .foregroundStyle(RatsColor.secondary)
                                    .lineSpacing(2)
                            }
                        }
                        .frame(maxWidth: .infinity, alignment: .leading)
                        if let id = entry.decisionId {
                            Button { open(decision: id) } label: { row }.buttonStyle(RatsPlainButtonStyle())
                        } else {
                            row
                        }
                    }
                    if group.entries.count > 12 {
                        Text("und \(group.entries.count - 12) weitere")
                            .font(RatsFont.mono(9.5))
                            .foregroundStyle(RatsColor.muted)
                    }
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .ratsCard()
        }
    }
}
