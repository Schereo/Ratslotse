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

        // Der Kartentext kennt Vorlage und Anlagen, `summary` nur den Titel —
        // dieselbe Wahl wie im Web (Plan Vorlagen aufbereiten, Schritt 5).
        if let kurz = (d.item.socialText ?? d.item.summary), !kurz.isEmpty {
            VStack(alignment: .leading, spacing: 8) {
                HStack(spacing: 6) {
                    Text("Das Wichtigste in Kürze").font(RatsFont.body(16, weight: .semibold)).foregroundStyle(RatsColor.text)
                    RatsIcon(.sparkles, size: 13).foregroundStyle(RatsColor.signal)
                        .accessibilityLabel("Automatisch erstellt")
                }
                Text(kurz).font(RatsFont.body(16)).foregroundStyle(RatsColor.bodyText)
                    .fixedSize(horizontal: false, vertical: true)
                if d.courseItem.important == true, let grund = d.courseItem.importantReason {
                    (Text("Warum wichtig: ").bold().foregroundColor(RatsColor.primary) + Text(grund))
                        .font(RatsFont.body(14)).foregroundStyle(RatsColor.bodyText)
                        .fixedSize(horizontal: false, vertical: true)
                        .padding(10)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .background(RatsColor.primary.opacity(0.07), in: RoundedRectangle(cornerRadius: 10, style: .continuous))
                        .overlay(alignment: .leading) { Rectangle().fill(RatsColor.primary).frame(width: 3) }
                }
                Text("Automatisch erstellt. Verbindlich sind die Unterlagen im Ratsinfo.")
                    .font(RatsFont.body(12)).foregroundStyle(RatsColor.muted)
            }
            .ratsCard()
        }

        if model.feature("aus-den-unterlagen"), let f = d.templateFields {
            AusDenUnterlagenCard(f: f)
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


/// „Aus den Unterlagen" — wie im Web (`components/session/aus-den-unterlagen.tsx`):
/// amtlicher Wortlaut aus der Vorlage, als Zitat gesetzt und ohne KI-Zeichen.
private struct AusDenUnterlagenCard: View {
    let f: AgendaItemDetail.TemplateFields
    @State private var vorschlagOffen = false

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack(alignment: .firstTextBaseline) {
                Text("Aus den Unterlagen").font(RatsFont.body(16, weight: .semibold)).foregroundStyle(RatsColor.text)
                Spacer()
                if let nr = f.templateNumber, let s = f.documentUrl, let url = URL(string: s) {
                    Link(destination: url) {
                        HStack(spacing: 4) {
                            Text("Vorlage \(nr)").font(RatsFont.body(13))
                            RatsIcon(.externalLink, size: 12)
                        }
                        .foregroundStyle(RatsColor.secondary)
                    }
                }
            }
            if let v = f.proposedDecision {
                abschnitt("Was beschlossen werden soll") {
                    zitat(v, lineLimit: vorschlagOffen ? nil : 6)
                    if v.count > 420 {
                        Button(vorschlagOffen ? "Weniger zeigen" : "Ganzen Wortlaut zeigen") { vorschlagOffen.toggle() }
                            .font(RatsFont.body(13, weight: .medium)).foregroundStyle(RatsColor.primary)
                    }
                }
            }
            if !f.motions.isEmpty {
                abschnitt(f.motions.count == 1 ? "Antrag dazu" : "\(f.motions.count) Anträge dazu") {
                    ForEach(f.motions) { m in
                        if let s = m.url, let url = URL(string: s) {
                            Link(destination: url) { antrag(m) }
                        } else {
                            antrag(m)
                        }
                    }
                }
            }
            if let c = f.cost {
                abschnitt("Was es kostet") {
                    if c.status == "none" {
                        Text("Laut Vorlage keine Kosten.").font(RatsFont.body(15)).foregroundStyle(RatsColor.bodyText)
                    } else {
                        zitat(c.text, lineLimit: nil)
                    }
                }
            }
            if let k = f.climate {
                abschnitt("Klima-Check") {
                    if let r = k.relevant {
                        Text(r ? "Klimarelevant" : "Laut Vorlage nicht klimarelevant")
                            .font(RatsFont.body(14, weight: .medium)).foregroundStyle(RatsColor.text)
                    }
                    zitat(k.text, lineLimit: 4)
                }
            }
            if let amt = f.office {
                abschnitt("Federführung") {
                    Text(amt).font(RatsFont.body(14)).foregroundStyle(RatsColor.bodyText)
                }
            }
        }
        .ratsCard()
    }

    private func abschnitt<C: View>(_ titel: String, @ViewBuilder _ inhalt: () -> C) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            MonoKicker(titel)
            inhalt()
        }
    }

    private func zitat(_ text: String, lineLimit: Int?) -> some View {
        Text("„\(text.trimmingCharacters(in: .whitespacesAndNewlines))“")
            .font(RatsFont.body(15)).foregroundStyle(RatsColor.bodyText)
            .lineLimit(lineLimit)
            .fixedSize(horizontal: false, vertical: true)
            .padding(.leading, 10)
            .overlay(alignment: .leading) { Rectangle().fill(RatsColor.border).frame(width: 2) }
    }

    private func antrag(_ m: AgendaItemDetail.TemplateFields.Motion) -> some View {
        HStack(alignment: .top, spacing: 8) {
            Circle().fill(RatsColor.primary).frame(width: 7, height: 7).padding(.top, 6)
            VStack(alignment: .leading, spacing: 2) {
                if !m.applicants.isEmpty {
                    Text(m.applicants.joined(separator: ", ")).font(RatsFont.body(14, weight: .semibold)).foregroundStyle(RatsColor.text)
                }
                Text(m.label).font(RatsFont.body(14)).foregroundStyle(RatsColor.bodyText).multilineTextAlignment(.leading)
            }
            Spacer(minLength: 0)
            if m.url != nil { RatsIcon(.externalLink, size: 12).foregroundStyle(RatsColor.muted) }
        }
        .padding(10)
        .overlay(RoundedRectangle(cornerRadius: 10, style: .continuous).strokeBorder(RatsColor.border, style: StrokeStyle(lineWidth: 1, dash: [4, 3])))
    }
}
