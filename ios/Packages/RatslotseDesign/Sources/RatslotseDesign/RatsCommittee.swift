import Foundation

/// Kurznamen der Gremien, entsprechend web/frontend/lib/committees.ts.
/// Der amtliche Name bleibt am zugänglichen Link und auf der Sitzungsseite.
public enum RatsCommittee {
    public static func short(_ name: String) -> String {
        names[name] ?? name.replacingOccurrences(of: "Ausschuss für ", with: "")
    }
    private static let names: [String: String] = [
        "Rat": "Rat",
        "Rat der Stadt Oldenburg": "Rat",
        "Rat der Stadt Oldenburg (Oldb)": "Rat",
        "Verwaltungsausschuss": "Verwaltungsausschuss",
        "Ausschuss für Allgemeine Angelegenheiten": "Allgemeine Angelegenheiten",
        "Ausschuss für Finanzen und Beteiligungen": "Finanzen & Beteiligungen",
        "Ausschuss für Integration und Migration": "Integration & Migration",
        "Ausschuss für Stadtgrün, Umwelt und Klima": "Stadtgrün & Klima",
        "Ausschuss für Stadtplanung und Bauen": "Stadtplanung & Bauen",
        "Ausschuss für Wirtschaftsförderung, Digitalisierung und internationale Zusammenarbeit": "Wirtschaft & Digitales",
        "Betriebsausschuss Abfallwirtschaftsbetrieb": "Abfallwirtschaft",
        "Betriebsausschuss Eigenbetrieb Gebäudewirtschaft und Hochbau": "Betrieb Gebäudewirtschaft",
        "Jugendhilfeausschuss": "Jugendhilfe",
        "Kulturausschuss": "Kultur",
        "Schulausschuss": "Schule",
        "Sozialausschuss": "Soziales",
        "Sportausschuss": "Sport",
        "Verkehrsausschuss": "Verkehr",
        "Ausschuss für Umwelt, Grünflächen und Klimaschutz": "Umwelt & Klima",
        "Ausschuss für Umwelt und Klimaschutz": "Umwelt & Klima",
        "Betriebsausschuss Gebäudewirtschaft und Hochbau": "Betrieb Gebäudewirtschaft",
        "Ausschuss für Wirtschaftsförderung und Digitalisierung": "Wirtschaft & Digitales",
    ]
}
