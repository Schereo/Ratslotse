import RatslotseAPI
import RatslotseDesign
import SwiftUI

/// „Aus der Geschäftsordnung des Rates" — der Wortlaut, auf den eine
/// Verfahrensfrage antwortet. Dieselbe Karte wie `RulesOfProcedureBlock` im
/// Web (`components/qa-bausteine.tsx`).
///
/// Gestrichelt und ohne Fläche: Die Geschäftsordnung ist ein Dokument der
/// Stadt, kein Beschluss aus dem Archiv, und bekommt deshalb auch keine
/// Fußnoten-Nummer (DESIGNSPRACHE § 4 und § 8, „Externes nie wie Beschlüsse
/// stylen"). Der Wortlaut steht DA, nicht nur ein Link: Die Karte ist der
/// Beleg — wer prüfen will, was die Antwort sagt, liest den Absatz hier und
/// muss nicht das PDF öffnen.
struct RulesOfProcedureCardView: View {
    let card: RulesOfProcedureCard
    @State private var showsContents = false

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            MonoKicker("Aus der Geschäftsordnung des Rates")
            ForEach(card.sections) { section in
                RulesOfProcedureParagraph(section: section)
            }
            if !card.contents.isEmpty {
                contents
            }
            footer
        }
        .padding(RatsSpacing.lg)
        .frame(maxWidth: .infinity, alignment: .leading)
        .overlay(
            RoundedRectangle(cornerRadius: RatsRadius.card, style: .continuous)
                .strokeBorder(RatsColor.border, style: StrokeStyle(lineWidth: 1, dash: [4, 3]))
        )
        .accessibilityElement(children: .contain)
    }

    /// Nur bei der Frage nach dem Ganzen: das Inhaltsverzeichnis, jede Zeile
    /// ein Sprung auf ihre Seite im PDF.
    private var contents: some View {
        VStack(alignment: .leading, spacing: 0) {
            Button {
                withAnimation(.snappy(duration: 0.22)) { showsContents.toggle() }
            } label: {
                HStack(spacing: 5) {
                    RatsIcon(.chevronDown, size: 12)
                        .rotationEffect(.degrees(showsContents ? 180 : 0))
                    Text("Alle \(card.contents.count) Paragrafen")
                }
                .font(RatsFont.notice(weight: .semibold))
                .foregroundStyle(RatsColor.primary)
                .frame(minHeight: 44, alignment: .leading)
                .contentShape(Rectangle())
            }
            .buttonStyle(RatsPlainButtonStyle())
            .padding(.vertical, -8)
            .accessibilityValue(showsContents ? "aufgeklappt" : "zugeklappt")
            if showsContents {
                VStack(alignment: .leading, spacing: 0) {
                    ForEach(card.contents) { entry in
                        if let url = entry.url {
                            Link(destination: url) { RulesOfProcedureContentsRow(entry: entry) }
                                .buttonStyle(RatsPlainButtonStyle())
                        } else {
                            RulesOfProcedureContentsRow(entry: entry)
                        }
                    }
                }
                .padding(.top, 10)
            }
        }
    }

    /// Welche Fassung, und ob sie noch gilt — fertiger Text vom Server. Gilt
    /// sie nicht mehr (die Wahlperiode ist vorbei, oder der Rat hat eine
    /// neuere beschlossen), steht die Zeile in Warnfarbe.
    private var footer: some View {
        VStack(alignment: .leading, spacing: 0) {
            Rectangle()
                .fill(RatsColor.separator)
                .frame(height: 1)
                .padding(.bottom, 10)
            if !card.version.isEmpty {
                Text(card.version)
                    .font(RatsFont.notice())
                    .foregroundStyle(card.isCurrent ? RatsColor.muted : RatsColor.warning)
                    .fixedSize(horizontal: false, vertical: true)
            }
            if let url = card.url {
                Link(destination: url) {
                    HStack(spacing: 5) {
                        Text("PDF auf oldenburg.de")
                        RatsIcon(.externalLink, size: 12)
                    }
                    .font(RatsFont.notice(weight: .semibold))
                    .foregroundStyle(RatsColor.primary)
                    .frame(minHeight: 44, alignment: .leading)
                    .contentShape(Rectangle())
                }
                .buttonStyle(RatsPlainButtonStyle())
                // Die Tippfläche bleibt 44 pt, ragt aber in den Abstand
                // hinein — sonst stünde unter jeder Textzeile ein Loch.
                .padding(.vertical, -8)
                .accessibilityHint("Öffnet die Geschäftsordnung als PDF")
            }
        }
    }
}

/// Ein Paragraf: Kopf als Sprung auf die Seite im PDF, darunter der Wortlaut.
/// Lange Paragrafen (§ 23 hat 2.900 Zeichen) beginnen als Vorschau.
private struct RulesOfProcedureParagraph: View {
    let section: RulesOfProcedureCard.Section
    @State private var expanded = false

    /// Dieselbe Grenze wie im Web: Kürzere Paragrafen (§ 30 hat 86 Zeichen)
    /// stehen ganz da, ein Knopf für drei Zeilen wäre Lärm.
    private var isLong: Bool { section.text.count > 420 }

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            header
            Text(section.text)
                .font(RatsFont.notice())
                .foregroundStyle(RatsColor.muted)
                .lineSpacing(3)
                .lineLimit(isLong && !expanded ? 5 : nil)
                .fixedSize(horizontal: false, vertical: true)
            if isLong {
                Button {
                    withAnimation(.snappy(duration: 0.22)) { expanded.toggle() }
                } label: {
                    HStack(spacing: 5) {
                        RatsIcon(.chevronDown, size: 12)
                            .rotationEffect(.degrees(expanded ? 180 : 0))
                        Text(expanded ? "Weniger anzeigen" : "Ganzen Wortlaut lesen")
                    }
                    .font(RatsFont.notice(weight: .semibold))
                    .foregroundStyle(RatsColor.primary)
                    .frame(minHeight: 44, alignment: .leading)
                    .contentShape(Rectangle())
                }
                .buttonStyle(RatsPlainButtonStyle())
                // Die Tippfläche bleibt 44 pt, ragt aber in den Abstand
                // hinein — sonst stünde unter jeder Textzeile ein Loch.
                .padding(.vertical, -8)
                .accessibilityHint(expanded ? "Zeigt nur den Anfang" : "Zeigt den ganzen Paragrafen")
            }
        }
    }

    @ViewBuilder private var header: some View {
        if let url = section.url {
            Link(destination: url) { headerLabel(linked: true) }
                .buttonStyle(RatsPlainButtonStyle())
                .accessibilityHint("Öffnet die Seite im PDF der Stadt")
        } else {
            headerLabel(linked: false)
        }
    }

    private func headerLabel(linked: Bool) -> some View {
        HStack(alignment: .top, spacing: 8) {
            VStack(alignment: .leading, spacing: 2) {
                Text([section.label, section.title].filter { !$0.isEmpty }.joined(separator: " "))
                    .font(RatsFont.sourceTitle())
                    .foregroundStyle(RatsColor.text)
                if let part = section.part, !part.isEmpty {
                    Text("Abschnitt \(part)")
                        .font(RatsFont.metadata())
                        .foregroundStyle(RatsColor.muted)
                }
            }
            .fixedSize(horizontal: false, vertical: true)
            Spacer(minLength: 0)
            if linked {
                RatsIcon(.externalLink, size: 13)
                    .foregroundStyle(RatsColor.muted)
                    .padding(.top, 4)
                    .accessibilityHidden(true)
            }
        }
        .multilineTextAlignment(.leading)
        .contentShape(Rectangle())
    }
}

private struct RulesOfProcedureContentsRow: View {
    let entry: RulesOfProcedureCard.Entry
    /// Breit genug für „§ 33" — und wächst mit der Schrift, sonst bräche das
    /// Paragrafenzeichen bei großer Schrift von seiner Zahl.
    @ScaledMetric(relativeTo: .caption) private var labelWidth: CGFloat = 46

    var body: some View {
        HStack(alignment: .firstTextBaseline, spacing: 8) {
            Text(entry.label)
                .font(RatsFont.metadata())
                .foregroundStyle(RatsColor.muted)
                .frame(width: labelWidth, alignment: .leading)
            Text(entry.title)
                .font(RatsFont.notice())
                .foregroundStyle(RatsColor.text)
                .fixedSize(horizontal: false, vertical: true)
            Spacer(minLength: 0)
        }
        .multilineTextAlignment(.leading)
        .frame(minHeight: 44)
        .contentShape(Rectangle())
    }
}

#if DEBUG
/// Sichtprobe ohne Server (`RATSLOTSE_DEBUG_QUESTION_FIXTURE=geschaeftsordnung`
/// bzw. `…-alt`): Wortlaut und Fassungszeilen, wie
/// `council/rules_of_procedure.py::card` sie ausliefert — erzeugt am 03.10.2026.
enum RulesOfProcedureDebugFixture {
    private static let pdf = "https://www.oldenburg.de/fileadmin/oldenburg/Benutzer/Dateien/22_Rechtsamt/1.02_20210719.pdf"
    private static let current = "Fassung vom 19.07.2021, vom Rat am 01.11.2021 bestätigt · gilt für die Wahlperiode 2021–2026"
    private static let ended = "Fassung vom 19.07.2021, vom Rat am 01.11.2021 bestätigt. Sie galt für die Wahlperiode 2021–2026; die neue Fassung des neuen Rates liegt hier noch nicht vor."

    /// `overview: false` — „Wie lange darf ein Ratsmitglied reden?": § 15 und § 32,
    /// Fassung gilt. `overview: true` — „Was steht in der Geschäftsordnung?":
    /// § 9 und § 15 mit Verzeichnis, die Wahlperiode ist vorbei.
    static func card(overview: Bool) -> JSONValue {
        let sections = (try? JSONDecoder().decode([String: JSONValue].self, from: Data(paragraphs.utf8))) ?? [:]
        let chosen = (overview ? ["9", "15"] : ["15", "32"]).compactMap { sections[$0] }
        return .object([
            "title": .string("Geschäftsordnung des Rates"),
            "full_title": .string("Geschäftsordnung für den Rat, den Verwaltungsausschuss und die Ratsausschüsse der Stadt Oldenburg (Oldb)"),
            "version": .string(overview ? ended : current),
            "state": .string(overview ? "term_ended" : "current"),
            "url": .string(pdf),
            "sections": .array(chosen),
            "contents": .array(overview ? contents.map { label, title, page in
                .object(["label": .string(label), "title": .string(title), "url": .string("\(pdf)#page=\(page)")])
            } : []),
        ])
    }

    private static let contents: [(String, String, Int)] = [
        ("§ 1", "Einberufung", 2),
        ("§ 2", "Ladung", 2),
        ("§ 3", "Tagesordnung", 2),
        ("§ 4", "Öffentlichkeit der Sitzungen", 3),
        ("§ 5", "Teilnahme an den Sitzungen", 4),
        ("§ 6", "Mitwirkungsverbot", 4),
        ("§ 7", "Vorsitz und Vertretung", 4),
        ("§ 8", "Beschlussfähigkeit", 5),
        ("§ 9", "Abwicklung der Tagesordnung", 5),
        ("§ 10", "Vorbereitung von Ratsbeschlüssen", 6),
        ("§ 11", "Dringlichkeitsanträge", 6),
        ("§ 12", "Änderungsanträge", 6),
        ("§ 13", "Anträge zur Geschäftsordnung", 6),
        ("§ 14", "Anfragen, Akteneinsicht", 7),
        ("§ 15", "Redeordnung, Redezeit", 7),
        ("§ 16", "Persönliche Erklärungen", 8),
        ("§ 17", "Ordnungsmaßnahmen", 8),
        ("§ 18", "Abstimmungen", 9),
        ("§ 19", "Wahlen", 9),
        ("§ 20", "Protokoll", 9),
        ("§ 21", "Fraktionen und Gruppen", 10),
        ("§ 22", "Anhörung", 10),
        ("§ 23", "Einwohnerfragestunde", 10),
        ("§ 24", "Einberufung und Ladung", 11),
        ("§ 25", "Sitzungen", 12),
        ("§ 26", "Sonstige Verfahrensvorschriften", 12),
        ("§ 27", "Ausschüsse des Rates", 13),
        ("§ 28", "Einberufung und Ladung", 13),
        ("§ 28a", "Besonderer Verweisungsantrag für Ratsausschüsse", 14),
        ("§ 29", "Öffentlichkeit der Sitzungen", 14),
        ("§ 30", "Abstimmungen", 14),
        ("§ 31", "Gemeinsame Sitzungen", 14),
        ("§ 32", "Sonstige Verfahrensvorschriften", 15),
        ("§ 33", "In Kraft treten", 15),
    ]

    private static let paragraphs = #"""
    {
      "9": {
        "number": "9",
        "label": "§ 9",
        "title": "Abwicklung der Tagesordnung",
        "part": "Rat",
        "url": "https://www.oldenburg.de/fileadmin/oldenburg/Benutzer/Dateien/22_Rechtsamt/1.02_20210719.pdf#page=5",
        "text": "(1) Die Tagesordnung wird in der Regel in folgender Reihenfolge abgewickelt:\n1. Feststellung der Beschlussfähigkeit,\n2. Genehmigung der Tagesordnung,\n3. Genehmigung des Protokolls,\n4. Mitteilungen des Oberbürgermeisters,\n5. Einwohnerfragestunde nach § 62 NKomVG\n6. Einwohneranträge nach § 31 NKomVG\n7. Verwaltungsausschuss und Fachausschüsse,\n8. Anträge der Fraktionen und Gruppen (nach Eingang)\n9. Anträge einzelner Ratsmitglieder (nach Eingang).\n10. Anfragen und Anregungen\n11. Verschiedenes (nur nichtöffentliche Sitzung).\n(2) Der Rat kann die Reihenfolge der Tagesordnung ändern."
      },
      "15": {
        "number": "15",
        "label": "§ 15",
        "title": "Redeordnung, Redezeit",
        "part": "Rat",
        "url": "https://www.oldenburg.de/fileadmin/oldenburg/Benutzer/Dateien/22_Rechtsamt/1.02_20210719.pdf#page=7",
        "text": "(1) Die/Der Ratsvorsitzende erteilt das Wort. Sie/Er bestimmt die Rednerinnen und Redner nach der Reihenfolge der Wortmeldungen; der oder dem Vorsitzenden des vorbereitenden Ratsausschusses soll auf Wunsch das Wort als erste Rednerin oder als erster Redner erteilt werden.\n(2) Will die/der Ratsvorsitzende selbst zur Sache sprechen, hat sie/er den Vorsitz abzugeben.\n(3) Außerhalb der Reihenfolge der Wortmeldungen wird das Wort nur zu Anträgen zur Geschäftsordnung (§ 13) sowie an die Oberbürgermeisterin/den Oberbürgermeister und an die Beamtinnen und Beamten auf Zeit erteilt.\n(4) Jedes Ratsmitglied darf grundsätzlich zu einem Beratungsgegenstand im Rahmen der Ratssitzung nur einmal sprechen; ausgenommen sind\na) Anträge und Einwendungen zur Geschäftsordnung\nb) Wortmeldungen des Oberbürgermeisters\nDie/der Ratsvorsitzende kann im Einzelfall zulassen, dass ein Ratsmitglied mehr als einmal zu einer Sache sprechen darf. Bei Widerspruch entscheidet der Rat.\n(5) Die Redezeit jeder Ratsfrau und jedes Ratsherrn beträgt für jede Wortmeldung bis zu fünf Minuten, soweit der Rat keine Ausnahme zulässt.\n(6) Die/Der Ratsvorsitzende ist berechtigt, eine/n Redner/in auf den Gegenstand der Beratung zu verweisen. Fährt der/die Redner/in fort, nicht zur Sache zu sprechen, obgleich er/sie zweimal auf den Gegenstand verwiesen worden ist, so entzieht ihm/ihr die/der Ratsvorsitzende das Wort. Ist einem/einer Redner/in das Wort entzogen worden, so darf er/sie es in derselben Aussprache zum selben Gegenstand nicht wieder erhalten."
      },
      "32": {
        "number": "32",
        "label": "§ 32",
        "title": "Sonstige Verfahrensvorschriften",
        "part": "Ratsausschüsse",
        "url": "https://www.oldenburg.de/fileadmin/oldenburg/Benutzer/Dateien/22_Rechtsamt/1.02_20210719.pdf#page=15",
        "text": "(1) Die Vorschriften über das Verfahren im Rat gelten sinngemäß auch für die Ratsausschüsse, soweit diese Geschäftsordnung nicht etwas anderes bestimmt. Der § 15 Absatz 4 (einmaliges Rederecht) findet keine Anwendung.\n(2) Wird in einem Ausschuss ein Antrag beraten, den eine Ratsfrau oder ein Ratsherr gestellt hat, die/der dem Ausschuss nicht angehört, so kann sie/er sich an der Beratung beteiligen.\n(3) Die oder der Ausschussvorsitzende kann einer Ratsfrau/ einem Ratsherrn, die/der nicht dem Ausschuss angehört, das Wort erteilen.\n(4) Die oder der Ausschussvorsitzende kann mit Zustimmung der Mehrheit der stimmberechtigten Ausschussmitglieder einer anwesenden Einwohnerin oder einem anwesenden Einwohner der Stadt zu einem bestimmten Tagesordnungspunkt kurz das Wort erteilen.\n(5) Kommunale Beiräte erhalten in Angelegenheiten, die ihre satzungsgemäßen Aufgaben betreffen das Recht zu einzelnen Tagesordnungspunkten Stellung zu nehmen und ihre Belange vorzutragen."
      }
    }
    """#
}
#endif
