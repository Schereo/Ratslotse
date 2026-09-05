import RatslotseDesign

/// Was die App über ein Gremium weiß — Kurzname, ein Satz zum Inhalt, sein
/// Zeichen und seine Familie. Spiegel von `web/frontend/lib/committees.ts`,
/// damit beide Frontends dasselbe Zeichen und denselben Kurznamen zeigen;
/// wer dort eine Zeile ergänzt, ergänzt sie hier.
///
/// Die Oldenburger Gremienliste ist endlich (~15 aktuell plus ein paar
/// historische Umbenennungen). Gepflegte Tabelle zuerst, Heuristik nur als
/// Rückfall — nie ein hartes Abschneiden nach n Zeichen.
enum Committee {
    /// Vier Familien, vier Farben (Tims Entscheidung 04.09.2026): Farbe
    /// klassifiziert, statt zu dekorieren — siebzehn Farben wären ein
    /// Regenbogen, vier sagen etwas.
    enum Family: Sendable {
        /// Die Stadt als Ganzes — Rat, Verwaltung, Finanzen, Wirtschaft.
        case city
        /// Das Gebaute — Stadtplanung, Gebäudewirtschaft, Verkehr.
        case built
        /// Grün und Umwelt — Stadtgrün, Klima, Abfall.
        case green
        /// Die Menschen — Soziales, Jugend, Schule, Integration, Kultur, Sport.
        case people

        var accent: RatsWidgetAccent {
            switch self {
            case .city: .harbor
            case .built: .brick
            case .green: .marsh
            case .people: .plum
            }
        }
    }

    struct Entry {
        let short: String
        let explains: String?
        let glyph: RatsGlyph
        let family: Family
    }

    private static let entries: [String: Entry] = {
        func e(_ short: String, _ explains: String?, _ glyph: RatsGlyph, _ family: Family) -> Entry {
            Entry(short: short, explains: explains, glyph: glyph, family: family)
        }
        let council = e("Rat", "Entscheidet die großen Linien: Haushalt, Satzungen und Grundsatzbeschlüsse.", .landmark, .city)
        let green = e("Stadtgrün & Klima", "Grünflächen, Klimaschutz, Energie und Naturschutz in der Stadt.", .leaf, .green)
        let environment = e("Umwelt & Klima", "Grünflächen, Klimaschutz, Energie und Naturschutz in der Stadt.", .leaf, .green)
        let buildings = e("Betrieb Gebäudewirtschaft", "Bau und Unterhalt der städtischen Gebäude — Schulen, Kitas, Verwaltung.", .hammer, .built)
        let economy = e("Wirtschaft & Digitales", "Wirtschaftsförderung, Digitalisierung und internationale Zusammenarbeit.", .laptop, .city)
        return [
            "Rat": council,
            "Rat der Stadt Oldenburg": council,
            "Rat der Stadt Oldenburg (Oldb)": council,
            "Verwaltungsausschuss": e("Verwaltungsausschuss", "Bereitet die Ratsbeschlüsse vor und entscheidet Eilfälle — tagt nichtöffentlich.", .gavel, .city),
            "Ausschuss für Allgemeine Angelegenheiten": e("Allgemeine Angelegenheiten", "Verwaltung, Personal, Ordnung und alles, was in keinen Fachausschuss fällt.", .clipboardList, .city),
            "Ausschuss für Finanzen und Beteiligungen": e("Finanzen & Beteiligungen", "Haushalt, Zuwendungen und die städtischen Beteiligungen.", .coins, .city),
            "Ausschuss für Integration und Migration": e("Integration & Migration", "Zuwanderung, Teilhabe und interkulturelle Arbeit in der Stadt.", .globe, .people),
            "Ausschuss für Stadtgrün, Umwelt und Klima": green,
            "Ausschuss für Stadtplanung und Bauen": e("Stadtplanung & Bauen", "Bebauungspläne, Bauprojekte und wie sich Viertel entwickeln.", .building2, .built),
            "Ausschuss für Wirtschaftsförderung, Digitalisierung und internationale Zusammenarbeit": economy,
            "Betriebsausschuss Abfallwirtschaftsbetrieb": e("Abfallwirtschaft", "Müllabfuhr, Recycling und der städtische Abfallbetrieb.", .recycle, .green),
            "Betriebsausschuss Eigenbetrieb Gebäudewirtschaft und Hochbau": buildings,
            "Jugendhilfeausschuss": e("Jugendhilfe", "Kitas, Jugendarbeit und Hilfen für Familien.", .baby, .people),
            "Kulturausschuss": e("Kultur", "Museen, Theater, Bibliotheken und die Förderung der freien Szene.", .drama, .people),
            "Schulausschuss": e("Schule", "Schulen, Ganztagsbetreuung und neue Bildungsstandorte.", .graduationCap, .people),
            "Sozialausschuss": e("Soziales", "Wohnen, Pflege, Teilhabe und soziale Angebote der Stadt.", .heartHandshake, .people),
            "Sportausschuss": e("Sport", "Sportstätten, Vereinsförderung und Bäder.", .quiz, .people),
            "Verkehrsausschuss": e("Verkehr", "Radwege, Straßen, Bus & Bahn, Parken und Verkehrsberuhigung.", .bus, .built),
            // historische Umbenennungen (Bestand seit 2018)
            "Ausschuss für Umwelt, Grünflächen und Klimaschutz": environment,
            "Ausschuss für Umwelt und Klimaschutz": environment,
            "Betriebsausschuss Gebäudewirtschaft und Hochbau": buildings,
            "Ausschuss für Wirtschaftsförderung und Digitalisierung": economy,
            "Ausschuss für Wirtschaftsförderung und internationale Zusammenarbeit": economy,
            "Ausschuss für Bahnangelegenheiten": e("Bahnangelegenheiten", nil, .bus, .built),
        ]
    }()

    /// Der gepflegte Eintrag — oder ein aus dem Namen gebauter: Kurzname per
    /// Heuristik, Gruppe als Zeichen (ein Gremium sind Menschen, die
    /// zusammensitzen; das ist nie falsch, nur allgemein), Familie „Stadt".
    static func entry(_ name: String) -> Entry {
        let key = name.trimmingCharacters(in: .whitespacesAndNewlines)
        if let known = entries[key] { return known }
        return Entry(short: heuristicShort(key), explains: nil, glyph: .users, family: .city)
    }

    static func short(_ name: String) -> String { entry(name).short }
    static func glyph(_ name: String) -> RatsGlyph { entry(name).glyph }
    static func accent(_ name: String) -> RatsWidgetAccent { entry(name).family.accent }

    /// Der Rat selbst — nicht Ortsrat, Beirat oder Verwaltungsausschuss.
    static func isCouncil(_ name: String) -> Bool {
        RatslotseFeatures.isCouncil(name)
    }

    /// Präfix „Ausschuss für …" streichen, „und" → „&", „…ausschuss" → Kern —
    /// dieselben Regeln wie `shortCommittee` im Web.
    private static func heuristicShort(_ key: String) -> String {
        var s = key
        for prefix in ["Ausschuss für den ", "Ausschuss für die ", "Ausschuss für das ", "Ausschuss für ",
                       "Betriebsausschuss Eigenbetrieb ", "Betriebsausschuss "] where s.hasPrefix(prefix) {
            s.removeFirst(prefix.count)
            break
        }
        if !s.contains(" "), s.lowercased().hasSuffix("ausschuss") {
            s.removeLast("ausschuss".count)
            if s.hasSuffix("s") { s.removeLast() }
        }
        s = s.replacingOccurrences(of: " und ", with: " & ").trimmingCharacters(in: .whitespaces)
        return s.count >= 2 ? s : key
    }
}
