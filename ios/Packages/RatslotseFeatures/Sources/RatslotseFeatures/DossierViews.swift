import PDFKit
import RatslotseAPI
import RatslotseDesign
import SwiftUI

/// „Aus den Unterlagen" in der App — wie im Web (`components/session/dossier.tsx`):
/// je Abschnitt kurze Sätze mit [n]; ein Tipp öffnet den Beleg mit Zitat,
/// Dokument und Seite, und „Im Dokument" springt per PDFKit auf genau diese Seite
/// (QuickLook kann das nicht).
struct DossierCard: View {
    let dossier: AgendaItemDetail.Dossier
    let amendments: [AgendaItemDetail.Amendment]
    @State private var beleg: AgendaItemDetail.Statement?

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack(spacing: 6) {
                Text("Aus den Unterlagen").font(RatsFont.body(16, weight: .semibold)).foregroundStyle(RatsColor.text)
                RatsIcon(.sparkles, size: 13).foregroundStyle(RatsColor.signal).accessibilityLabel("Automatisch erstellt, jede Angabe belegt")
            }
            ForEach(Array(dossier.sections.enumerated()), id: \.element.id) { i, s in
                VStack(alignment: .leading, spacing: 6) {
                    MonoKicker(s.title)
                    if s.statements.isEmpty && s.status == "stated_none" {
                        Text("Laut Vorlage keine.").font(RatsFont.body(15)).foregroundStyle(RatsColor.bodyText)
                    }
                    ForEach(s.statements) { a in
                        Button { beleg = a } label: {
                            HStack(alignment: .firstTextBaseline, spacing: 6) {
                                Text(a.text).font(RatsFont.body(15)).foregroundStyle(RatsColor.bodyText)
                                    .multilineTextAlignment(.leading).fixedSize(horizontal: false, vertical: true)
                                Spacer(minLength: 0)
                                Text("\(a.listNo.map(String.init) ?? "·")").font(RatsFont.mono(10)).foregroundStyle(RatsColor.muted)
                                    .padding(.horizontal, 5).padding(.vertical, 1)
                                    .background(RatsColor.border.opacity(0.5), in: RoundedRectangle(cornerRadius: 4))
                            }
                        }
                        .buttonStyle(RatsPlainButtonStyle())
                        .accessibilityHint("Zeigt den Beleg")
                    }
                }
                if i == 0 && !amendments.isEmpty {
                    AmendmentsSection(amendments: amendments)
                }
            }
        }
        .ratsCard()
        .sheet(item: $beleg) { a in BelegSheet(a: a) }
    }
}

struct AmendmentsSection: View {
    let amendments: [AgendaItemDetail.Amendment]

    private func muster(_ p: String?) -> String? {
        ["replace": "ersetzt", "delete": "streicht", "add": "ergänzt", "rewrite": "fasst neu", "counter": "Gegenvorschlag"][p ?? ""]
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            MonoKicker(amendments.count == 1 ? "Was der Änderungsantrag will" : "Was die \(amendments.count) Anträge wollen")
            ForEach(amendments) { a in
                VStack(alignment: .leading, spacing: 6) {
                    HStack(spacing: 6) {
                        Text(a.applicants.joined(separator: ", ").isEmpty ? "Antrag" : a.applicants.joined(separator: ", "))
                            .font(RatsFont.body(14, weight: .semibold)).foregroundStyle(RatsColor.text)
                        if let m = muster(a.pattern) {
                            Text(m).font(RatsFont.body(11)).foregroundStyle(RatsColor.text)
                                .padding(.horizontal, 5).padding(.vertical, 1)
                                .overlay(RoundedRectangle(cornerRadius: 4).strokeBorder(RatsColor.border))
                        }
                        if let o = a.outcome { OutcomeBadge(o) }
                        Spacer()
                        if let url = URL(string: a.url) {
                            Link(destination: url) { Text("[\(a.listNo)]").font(RatsFont.mono(11)).foregroundStyle(RatsColor.muted) }
                        }
                    }
                    if let t = a.target { Text(t.uppercased()).font(RatsFont.mono(10)).foregroundStyle(RatsColor.muted) }
                    if let m = a.meaning { Text(m.text).font(RatsFont.body(15, weight: .medium)).foregroundStyle(RatsColor.text) }
                    if let diff = a.diff, diff.contains(where: { $0.first != "=" }) {
                        Text(diffText(diff)).font(RatsFont.body(15)).fixedSize(horizontal: false, vertical: true)
                    } else {
                        if let b = a.before { zitat("Bisher", b.quote, alt: true) }
                        if let n = a.after { zitat(a.pattern == "add" ? "Ergänzung" : "Neu", n.quote, alt: false) }
                    }
                    if let r = a.reason { Text(r.text).font(RatsFont.body(13).italic()).foregroundStyle(RatsColor.muted) }
                }
                .padding(10)
                .overlay(RoundedRectangle(cornerRadius: 10, style: .continuous).strokeBorder(RatsColor.border))
            }
        }
    }

    private func zitat(_ titel: String, _ text: String, alt: Bool) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(titel.uppercased()).font(RatsFont.mono(10)).foregroundStyle(RatsColor.muted)
            Text("„\(text)“").font(RatsFont.body(14)).foregroundStyle(alt ? RatsColor.muted : RatsColor.bodyText)
                .lineLimit(6).padding(.leading, 8)
                .overlay(alignment: .leading) { Rectangle().fill(alt ? RatsColor.border : RatsColor.signal.opacity(0.6)).frame(width: 2) }
        }
    }

    /// Wortdiff wie im Web: alt durchgestrichen, neu hervorgehoben, Kontext gekürzt.
    private func diffText(_ diff: [[String]]) -> AttributedString {
        var out = AttributedString()
        for (i, teil) in diff.enumerated() where teil.count == 2 {
            var text = teil[1]
            if teil[0] == "=" {
                let w = text.split(separator: " ")
                if w.count > 16 {
                    text = i == 0 ? "… " + w.suffix(8).joined(separator: " ")
                        : i == diff.count - 1 ? w.prefix(8).joined(separator: " ") + " …"
                        : w.prefix(8).joined(separator: " ") + " … " + w.suffix(8).joined(separator: " ")
                }
            }
            var s = AttributedString((i > 0 ? " " : "") + text)
            if teil[0] == "-" { s.strikethroughStyle = .single; s.foregroundColor = RatsColor.muted }
            if teil[0] == "+" { s.backgroundColor = RatsColor.signal.opacity(0.12); s.font = RatsFont.body(15, weight: .medium) }
            out += s
        }
        return out
    }
}

/// Der Beleg zu einer Aussage: Zitat, Dokument, Seite — und der Sprung ins PDF.
struct BelegSheet: View {
    let a: AgendaItemDetail.Statement
    @State private var pdfOffen = false

    var body: some View {
        NavigationStack {
            VStack(alignment: .leading, spacing: 14) {
                Text(a.text).font(RatsFont.body(16, weight: .semibold)).foregroundStyle(RatsColor.text)
                Text("„\(a.quote)“").font(RatsFont.body(15)).foregroundStyle(RatsColor.bodyText)
                    .padding(.leading, 10)
                    .overlay(alignment: .leading) { Rectangle().fill(RatsColor.primary.opacity(0.5)).frame(width: 2) }
                Text([a.docLabel, a.page.map { "S. \($0)" }].compactMap { $0 }.joined(separator: " · "))
                    .font(RatsFont.body(13)).foregroundStyle(RatsColor.muted)
                if a.url != nil {
                    Button("Im Dokument öffnen") { pdfOffen = true }
                        .font(RatsFont.body(15, weight: .medium)).foregroundStyle(RatsColor.primary)
                }
                Spacer()
            }
            .padding(20)
            .navigationTitle("Beleg").navigationBarTitleDisplayMode(.inline)
            .sheet(isPresented: $pdfOffen) {
                if let s = a.url, let url = URL(string: s.components(separatedBy: "#").first ?? s) {
                    PDFSeitenView(url: url, seite: a.page ?? 1).ignoresSafeArea()
                }
            }
        }
        .presentationDetents([.medium, .large])
    }
}

/// Ein PDF aus dem Ratsinfo, geöffnet auf einer bestimmten Seite.
struct PDFSeitenView: UIViewRepresentable {
    let url: URL
    let seite: Int

    func makeUIView(context: Context) -> PDFView {
        let view = PDFView()
        view.autoScales = true
        Task.detached {
            guard let (daten, _) = try? await URLSession.shared.data(from: url),
                  let dokument = PDFDocument(data: daten) else { return }
            await MainActor.run {
                view.document = dokument
                if let s = dokument.page(at: max(0, seite - 1)) { view.go(to: s) }
            }
        }
        return view
    }

    func updateUIView(_ uiView: PDFView, context: Context) {}
}
