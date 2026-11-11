import RatslotseAPI
import RatslotseDesign
import SwiftUI

/// Ein Tagesordnungspunkt auf seiner eigenen Seite — wie im Web
/// (`app/(app)/council/punkt/`, Schalter `punkt-seite`): Kurzfassung,
/// Vorgeschichte, Unterlagen und „Meine Notiz" (Schalter `notizen`). Hat der
/// Punkt einen Beschluss, führt ein Hinweis dorthin.
///
/// Ohne den Schalter landet man beim Punkt in der Sitzung — dort, wo er heute
/// schon steht (wie die Web-Seite ohne Schalter).
struct AgendaItemDetailView: View {
    let model: AppModel
    let ksinr: Int
    let itemNumber: String

    @State private var detail: AgendaItemDetail?
    @State private var error: String?

    var body: some View {
        if !model.featuresLoaded {
            RatsLoadingState(message: "Punkt wird geladen …")
        } else if !model.feature("punkt-seite") {
            SessionRouteView(model: model, ksinr: ksinr, tops: [itemNumber])
        } else {
            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    if let detail {
                        inhalt(detail)
                    } else if let error {
                        ErrorCard(message: error) { Task { await load() } }
                    } else {
                        RatsLoadingState(message: "Punkt wird geladen …")
                    }
                }
                .padding(20)
            }
            .background(RatsColor.page)
            .task(id: "\(ksinr)|\(itemNumber)") { await load() }
        }
    }

    @ViewBuilder
    private func inhalt(_ d: AgendaItemDetail) -> some View {
        let kicker = [d.item.itemNumber, d.courseItem.typeLabel, d.item.templateNumber.map { "Vorlage \($0)" },
                      "\(RatsDate.short(d.sessionDate) ?? d.sessionDate) · \(d.committee)"].compactMap { $0 }.joined(separator: " · ")
        VStack(alignment: .leading, spacing: 6) {
            Text(kicker.uppercased()).font(RatsFont.mono(10)).foregroundStyle(RatsColor.muted)
            Text(d.courseItem.shortTitle).font(RatsFont.title(26)).foregroundStyle(RatsColor.text)
                .fixedSize(horizontal: false, vertical: true)
            if let applicant = d.courseItem.applicant {
                Text("Antrag von \(applicant)").font(RatsFont.body(14)).foregroundStyle(RatsColor.secondary)
            }
        }

        if let id = d.decisionId {
            Button { model.navigation.append(.decision(id: id)) } label: {
                HStack {
                    Text("Zu diesem Punkt gibt es inzwischen einen Beschluss.").font(RatsFont.body(14))
                    Spacer()
                    RatsIcon(.arrowRight, size: 14)
                }
                .foregroundStyle(RatsColor.primary)
                .padding(12)
                .background(RatsColor.primary.opacity(0.07), in: RoundedRectangle(cornerRadius: 12, style: .continuous))
            }
            .buttonStyle(RatsPlainButtonStyle())
        }

        if let summary = d.item.summary, !summary.isEmpty {
            VStack(alignment: .leading, spacing: 6) {
                MonoKicker("Kurzfassung")
                Text(summary).font(RatsFont.body(16)).foregroundStyle(RatsColor.bodyText)
                    .fixedSize(horizontal: false, vertical: true)
                Text("Automatische Kurzfassung. Verbindlich sind die Unterlagen im Ratsinfo.")
                    .font(RatsFont.body(12)).foregroundStyle(RatsColor.muted)
            }
            .ratsCard()
        }

        if d.history.count > 1 {
            VStack(alignment: .leading, spacing: 12) {
                MonoKicker("Vorgeschichte", trailing: "\(d.history.count) Stationen")
                ForEach(d.history) { s in
                    HStack(alignment: .top, spacing: 10) {
                        Circle().fill(s.current ? RatsColor.primary : RatsColor.border).frame(width: 9, height: 9).padding(.top, 5)
                        VStack(alignment: .leading, spacing: 4) {
                            Text("\(RatsDate.short(s.sessionDate) ?? s.sessionDate) · \(s.committee)\(s.current ? " · diese Sitzung" : "")")
                                .font(RatsFont.mono(10)).foregroundStyle(s.current ? RatsColor.primary : RatsColor.muted)
                            if let o = s.outcome { OutcomeBadge(o) }
                            if let t = s.text { Text(t).font(RatsFont.body(14)).foregroundStyle(RatsColor.bodyText) }
                            if let id = s.decisionId {
                                Button("Zum Beschluss") { model.navigation.append(.decision(id: id)) }
                                    .font(RatsFont.body(13, weight: .medium)).foregroundStyle(RatsColor.primary)
                            }
                        }
                    }
                }
            }
            .ratsCard()
        }

        if !d.documents.isEmpty {
            VStack(alignment: .leading, spacing: 10) {
                MonoKicker("Unterlagen", trailing: "\(d.documents.count)")
                ForEach(d.documents) { doc in
                    if let url = URL(string: doc.url) {
                        Link(destination: url) {
                            HStack {
                                Text(doc.label).font(RatsFont.body(14, weight: .medium)).multilineTextAlignment(.leading)
                                Spacer()
                                RatsIcon(.externalLink, size: 13)
                            }
                            .foregroundStyle(RatsColor.primary)
                        }
                    }
                }
            }
            .ratsCard()
        }

        if model.feature("notizen") {
            NoteCard(model: model, targetKind: "agenda_item", targetKey: "\(d.ksinr)|\(d.item.itemNumber)",
                     wofuer: "Punkt")
        }
    }

    private func load() async {
        error = nil
        do {
            let d: AgendaItemDetail = try await model.api.get("/api/council/session/\(ksinr)/item",
                                                              query: [URLQueryItem(name: "nr", value: itemNumber)])
            detail = d
        } catch {
            self.error = (error as? APIError)?.message ?? "Dieser Tagesordnungspunkt lässt sich gerade nicht laden."
        }
    }
}
