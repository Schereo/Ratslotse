import RatslotseAPI
import RatslotseDesign
import SwiftUI

/// „Ideen aus anderen Städten" — was andere Räte beschlossen haben und
/// Oldenburg fehlt.
///
/// **Zwei Zustände, eine Ansicht.** Ohne gewähltes Feld die Übersicht, mit
/// Feld die Liste darin. Ein Fließband über alle zwölf Felder wäre eine Liste
/// ohne Anfang; die Übersicht sagt zuerst, wo etwas liegt.
///
/// **Das Urteil steht mit seinen Belegen da.** Was das Modell über Oldenburg
/// sagt, ist nachprüfbar: Die Beschlüsse, auf die es sich stützt, führen auf
/// ihre Seite. Ohne sie wäre es eine Behauptung.
struct IdeasView: View {
    let model: AppModel
    @State private var felder: [IdeaFieldSummary] = []
    @State private var gewaehlt: String?
    @State private var ideen: IdeasResponse?
    @State private var laedt = true
    @State private var fehler: String?
    @State private var frage = ""
    @State private var treffer: IdeaSearchResponse?

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                kopf
                suchzeile
                if let treffer {
                    suchergebnis(treffer)
                } else if let gewaehlt {
                    feldListe(gewaehlt)
                } else {
                    uebersicht
                }
            }
            .padding(.horizontal, 16)
            .padding(.bottom, 32)
        }
        .background(RatsColor.page)
        // Eigener Takt am Schalter: Der kommt aus `/api/app-config` und ist
        // beim ersten Aufbau der Ansicht oft noch nicht da (Lehre aus dem
        // Block „Anderswo beschlossen").
        .task(id: model.feature("ideen-anderswo")) { await ladeFelder() }
    }

    private var kopf: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("Ideen aus anderen Städten")
                .font(RatsFont.body(20, weight: .semibold))
                .foregroundStyle(RatsColor.text)
            Text("Was Räte in Osnabrück, Braunschweig, Münster, Potsdam und "
                 + "Magdeburg beschlossen haben — und ob Oldenburg dasselbe schon "
                 + "hat. Die Einschätzung stammt von einem Sprachmodell; die "
                 + "Beschlüsse, auf die sie sich stützt, stehen unter jeder Idee.")
                .font(RatsFont.body(12.5))
                .foregroundStyle(RatsColor.muted)
                .fixedSize(horizontal: false, vertical: true)
        }
        .padding(.top, 8)
    }

    // ---------------------------------------------------------------- Suche

    /// Eine Zeile, keine eigene Ansicht: Der Volltextindex hat kein Fenster
    /// nach vorn, und wer eine Sache im Kopf hat, soll nicht erst das
    /// richtige Themenfeld raten müssen.
    private var suchzeile: some View {
        HStack(spacing: 8) {
            RatsIcon(.search, size: 15).foregroundStyle(RatsColor.muted)
            TextField("Was haben andere Städte zu …?", text: $frage)
                .font(RatsFont.body(14))
                .submitLabel(.search)
                .autocorrectionDisabled()
                .onSubmit { Task { await suche() } }
            if !frage.isEmpty {
                Button {
                    frage = ""
                    treffer = nil
                } label: {
                    RatsIcon(.x, size: 14).foregroundStyle(RatsColor.muted)
                }
                .buttonStyle(RatsPlainButtonStyle())
            }
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 10)
        .background(RatsColor.card)
        .overlay(RoundedRectangle(cornerRadius: 10, style: .continuous)
                    .stroke(RatsColor.border))
        .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
    }

    @ViewBuilder
    private func suchergebnis(_ antwort: IdeaSearchResponse) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(antwort.query)
                .font(RatsFont.body(17, weight: .semibold))
                .foregroundStyle(RatsColor.text)
            Text("\(antwort.total) Treffer in den Ratsinformationssystemen der "
                 + "anderen Städte.")
                .font(RatsFont.body(11.5))
                .foregroundStyle(RatsColor.muted)
                .fixedSize(horizontal: false, vertical: true)
            ForEach(antwort.items) { idee in
                IdeaCard(model: model, idee: idee)
            }
            if antwort.items.isEmpty {
                Text("Dazu haben die anderen Städte nichts — jedenfalls nicht mit "
                     + "diesen Wörtern.")
                    .font(RatsFont.body(13))
                    .foregroundStyle(RatsColor.muted)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
    }

    private func suche() async {
        let text = frage.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { treffer = nil; return }
        do {
            // Wie bei der Liste: Der Parameter geht über `query:`, nicht in
            // den Pfad — sonst wird das „?" mitkodiert und der Server
            // antwortet mit 404.
            let antwort: IdeaSearchResponse = try await model.api.get(
                "/api/council/cities/search", query: [URLQueryItem(name: "q", value: text)])
            treffer = antwort
        } catch {
            fehler = error.localizedDescription
        }
    }

    // ------------------------------------------------------------ Übersicht

    @ViewBuilder
    private var uebersicht: some View {
        if laedt {
            ProgressView().frame(maxWidth: .infinity).padding(.top, 24)
        } else if let fehler {
            Text(fehler).font(RatsFont.body(13)).foregroundStyle(RatsColor.danger)
        } else if felder.isEmpty {
            Text("Noch keine Ideen eingelesen. Sobald der wöchentliche Abgleich "
                 + "mit den anderen Städten gelaufen ist, steht hier etwas.")
                .font(RatsFont.body(13))
                .foregroundStyle(RatsColor.muted)
                .fixedSize(horizontal: false, vertical: true)
        } else {
            LazyVGrid(columns: [GridItem(.adaptive(minimum: 150), spacing: 12)], spacing: 12) {
                ForEach(felder) { f in
                    Button {
                        gewaehlt = f.field
                        Task { await ladeIdeen(f.field) }
                    } label: {
                        feldKachel(f)
                    }
                    .buttonStyle(RatsPlainButtonStyle())
                }
            }
        }
    }

    private func feldKachel(_ f: IdeaFieldSummary) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(Self.feldLabel(f.field))
                .font(RatsFont.body(13, weight: .semibold))
                .foregroundStyle(RatsColor.text)
                .multilineTextAlignment(.leading)
            // Die große Zahl ist eine TATSACHE: Ideen, die mehrere andere
            // Städte haben und Oldenburg nicht. Vorher stand hier „Ideen, die
            // sich lohnen könnten" — gezählt aus einem Werturteil.
            Text("\(f.multiCity)")
                .font(RatsFont.body(24, weight: .semibold))
                .foregroundStyle(RatsColor.primary)
                .monospacedDigit()
            Text(f.multiCity == 1 ? "Idee aus mehreren Städten, die Oldenburg fehlt"
                                  : "Ideen aus mehreren Städten, die Oldenburg fehlen")
                .font(RatsFont.body(10.5))
                .foregroundStyle(RatsColor.muted)
                .multilineTextAlignment(.leading)
            Text("\(f.missing + f.partial) fehlen ganz oder halb · \(f.present) hat Oldenburg schon")
                .font(RatsFont.body(10))
                .foregroundStyle(RatsColor.muted.opacity(0.8))
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .ratsCard()
    }

    // -------------------------------------------------------------- Ein Feld

    @ViewBuilder
    private func feldListe(_ feld: String) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Button {
                gewaehlt = nil
                ideen = nil
            } label: {
                RatsLabel("Alle Themenfelder", .chevronLeft)
                    .font(RatsFont.body(12, weight: .medium))
                    .foregroundStyle(RatsColor.muted)
            }
            .buttonStyle(RatsPlainButtonStyle())

            Text(Self.feldLabel(feld))
                .font(RatsFont.body(17, weight: .semibold))
                .foregroundStyle(RatsColor.text)
            if let ideen {
                Text("\(ideen.total) Ideen aus anderen Städten, sortiert nach dem, "
                     + "was sich am ehesten lohnen könnte.")
                    .font(RatsFont.body(11.5))
                    .foregroundStyle(RatsColor.muted)
                    .fixedSize(horizontal: false, vertical: true)
                ForEach(ideen.items) { idee in
                    IdeaCard(model: model, idee: idee)
                }
                if ideen.items.isEmpty {
                    Text("In diesem Themenfeld ist noch nichts geprüft.")
                        .font(RatsFont.body(13))
                        .foregroundStyle(RatsColor.muted)
                }
            } else {
                ProgressView().frame(maxWidth: .infinity).padding(.top, 16)
            }
        }
    }

    // ----------------------------------------------------------------- Laden

    private func ladeFelder() async {
        guard model.feature("ideen-anderswo") else { laedt = false; return }
        do {
            // Die Typangabe steht ausgeschrieben, weil `scripts/ios_vertrag.py`
            // die Bindung an der Aufrufstelle abliest — `try?` und ein
            // abgeleiteter Typ wären für den Wächter unsichtbar.
            let antwort: IdeaFields = try await model.api.get("/api/council/cities/ideas/fields")
            felder = antwort.fields
            fehler = nil
        } catch {
            fehler = error.localizedDescription
        }
        laedt = false
    }

    private func ladeIdeen(_ feld: String) async {
        ideen = nil
        do {
            // Der Parameter geht über `query:`, nicht in den Pfad: `request`
            // kodiert den Pfad als Ganzes, ein „?" darin würde zu „%3F" und
            // der Server antwortete mit 404. Im Simulator gesehen.
            let antwort: IdeasResponse = try await model.api.get(
                "/api/council/cities/ideas", query: [URLQueryItem(name: "field", value: feld)])
            ideen = antwort
        } catch {
            fehler = error.localizedDescription
        }
    }

    /// Die Kurzlabels der Themenfelder — dieselben wie im Web
    /// (`POLICY_FIELD_LABELS`), damit beide Oberflächen gleich heißen.
    static func feldLabel(_ feld: String) -> String {
        [
            "verkehr": "Verkehr", "klima_umwelt": "Klima & Umwelt",
            "bauen_wohnen": "Bauen & Wohnen", "soziales_gesundheit": "Soziales",
            "bildung": "Bildung", "finanzen": "Finanzen",
            "kultur_sport": "Kultur & Sport", "wirtschaft": "Wirtschaft",
            "sicherheit_ordnung": "Sicherheit", "verwaltung_digital": "Verwaltung",
            "migration_integration": "Migration", "sonstiges": "Sonstiges",
        ][feld] ?? feld
    }
}

// ------------------------------------------------------------------ Karte

private struct IdeaCard: View {
    let model: AppModel
    let idee: Idea

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(alignment: .top, spacing: 6) {
                RatsLabel(idee.bodyName, .building2)
                    .font(RatsFont.body(11.5, weight: .semibold))
                    .foregroundStyle(RatsColor.text)
                    .layoutPriority(1)
                if !kopfzeile.isEmpty {
                    Text(kopfzeile)
                        .font(RatsFont.mono(10))
                        .foregroundStyle(RatsColor.muted)
                        .fixedSize(horizontal: false, vertical: true)
                }
                Spacer(minLength: 0)
            }
            if let originator = idee.originator, !originator.isEmpty {
                Text(originator).font(RatsFont.body(10.5)).foregroundStyle(RatsColor.muted)
            }
            // Aufwand und Verbreitung ordnen den Rest der Karte ein, bevor man
            // ihn liest: „Anfrage, auch in drei anderen Städten" sagt schon
            // fast alles. Leise gesetzt — die Aussage macht das Urteil.
            if !aufwandUndVerbreitung.isEmpty {
                Text(aufwandUndVerbreitung)
                    .font(RatsFont.body(10.5))
                    .foregroundStyle(RatsColor.muted)
            }

            Text(idee.name)
                .font(RatsFont.body(14, weight: .semibold))
                .foregroundStyle(RatsColor.text)
                .multilineTextAlignment(.leading)
            if let summary = idee.summary, !summary.isEmpty {
                Text(summary)
                    .font(RatsFont.body(12))
                    .foregroundStyle(RatsColor.secondary)
                    .multilineTextAlignment(.leading)
            }

            urteil

            if !idee.evidence.isEmpty {
                VStack(alignment: .leading, spacing: 5) {
                    Text("Worauf sich das stützt")
                        .font(RatsFont.body(11, weight: .medium))
                        .foregroundStyle(RatsColor.muted)
                    ForEach(idee.evidence) { beleg in
                        if let id = beleg.decisionID {
                            Button {
                                model.navigation.append(.decision(id: id))
                            } label: {
                                belegZeile(beleg, tippbar: true)
                            }
                            .buttonStyle(RatsPlainButtonStyle())
                        } else {
                            belegZeile(beleg, tippbar: false)
                        }
                    }
                }
                .padding(.top, 2)
            }

            if let raw = idee.web, let url = URL(string: raw) {
                Link(destination: url) {
                    RatsLabel("Im Ratsinformationssystem von \(idee.bodyName)", .externalLink)
                        .font(RatsFont.body(11.5, weight: .medium))
                        .foregroundStyle(RatsColor.primary)
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .ratsCard()
    }

    /// Das Urteil. Anzeigetafel-Tönung, nie eine dunkle Karte im Hellmodus.
    /// Was die Idee kostet und wie verbreitet sie ist — eine Zeile.
    private var aufwandUndVerbreitung: String {
        var teile: [String] = []
        if let aufwand = Self.aufwand[idee.effort] { teile.append(aufwand) }
        if idee.peers == 1 {
            teile.append("auch in 1 anderen Stadt")
        } else if idee.peers > 1 {
            teile.append("auch in \(idee.peers) anderen Städten")
        }
        return teile.joined(separator: " · ")
    }

    private var urteil: some View {
        VStack(alignment: .leading, spacing: 5) {
            HStack(spacing: 6) {
                if let text = Self.status[idee.status] {
                    Text(text)
                        .font(RatsFont.body(10.5, weight: .medium))
                        .foregroundStyle(idee.status == "missing" ? RatsColor.primary
                                                                  : RatsColor.secondary)
                        .padding(.horizontal, 6)
                        .padding(.vertical, 2)
                        .background(idee.status == "missing"
                                    ? RatsColor.primary.opacity(0.1) : RatsColor.separator)
                        .clipShape(RoundedRectangle(cornerRadius: 5, style: .continuous))
                }
                if idee.confidence == "low" {
                    Text("unsicher")
                        .font(RatsFont.body(10.5))
                        .foregroundStyle(RatsColor.muted.opacity(0.8))
                }
                Spacer(minLength: 0)
            }
            if !idee.reason.isEmpty {
                Text(idee.reason).font(RatsFont.body(11.5)).foregroundStyle(RatsColor.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
            if let addressee = idee.addressee, !addressee.isEmpty {
                Text("Entscheidet nicht die Stadt allein: \(addressee)")
                    .font(RatsFont.body(11)).foregroundStyle(RatsColor.muted)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(10)
        .background(RatsColor.separator.opacity(0.55))
        .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
    }

    private func belegZeile(_ beleg: IdeaEvidence, tippbar: Bool) -> some View {
        HStack(alignment: .top, spacing: 6) {
            VStack(alignment: .leading, spacing: 2) {
                Text(beleg.title)
                    .font(RatsFont.body(11.5))
                    .foregroundStyle(RatsColor.text)
                    .multilineTextAlignment(.leading)
                if let datum = Self.datum(beleg.date) {
                    Text(datum).font(RatsFont.mono(10)).foregroundStyle(RatsColor.muted)
                }
            }
            Spacer(minLength: 0)
            // Zeigerhand nur mit Ziel: Der Chevron steht nur da, wo es eine
            // Beschluss-Seite gibt.
            if tippbar {
                RatsIcon(.chevronRight, size: 12)
                    .foregroundStyle(RatsColor.muted.opacity(0.7))
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .contentShape(Rectangle())
    }

    private var kopfzeile: String {
        [Self.art[idee.kind], Self.datum(idee.date)]
            .compactMap { $0 }.joined(separator: " · ")
    }

    private static let status: [String: String] = [
        "missing": "In Oldenburg nicht gefunden",
        "partial": "Teilweise vorhanden",
        "present": "Oldenburg hat das",
    ]
    /// Dieselben fünf Wörter wie im Web (`ideen/view.tsx`). Web und App
    /// zeigen dieselbe Sache; zwei Vokabulare wären zwei Produkte.
    private static let aufwand: [String: String] = [
        "inquiry": "Anfrage", "review": "Prüfauftrag", "resolution": "Resolution",
        "decision": "Beschluss", "budget": "kostet Geld",
    ]
    private static let art: [String: String] = [
        "motion": "Antrag", "amendment": "Änderungsantrag", "inquiry": "Anfrage",
        "answer": "Antwort", "proposal": "Beschlussvorlage", "report": "Bericht",
        "notice": "Mitteilung", "petition": "Eingabe",
    ]

    private static func datum(_ iso: String?) -> String? {
        guard let iso, iso.count >= 10 else { return nil }
        let teile = iso.prefix(10).split(separator: "-")
        guard teile.count == 3 else { return nil }
        return "\(teile[2]).\(teile[1]).\(teile[0])"
    }
}
