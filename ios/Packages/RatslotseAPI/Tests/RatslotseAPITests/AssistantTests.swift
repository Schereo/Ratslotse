import Foundation
import Testing
@testable import RatslotseAPI

// MARK: - Der Bildschirm als Web-Route

@Test("Jeder erklärbare Screen nennt seine Route und seine Kennung")
func explainScreenAbbildung() throws {
    #expect(ExplainScreen.from(.decision(id: 42))?.route == "/council/decision")
    #expect(ExplainScreen.from(.decision(id: 42))?.refs.decisionID == 42)
    #expect(ExplainScreen.from(.sessions(ksinr: 7, tops: []))?.route == "/council/sitzung")
    #expect(ExplainScreen.from(.sessions(ksinr: 7, tops: []))?.refs.ksinr == 7)
    #expect(ExplainScreen.from(.topic(slug: "radverkehr"))?.refs.slug == "radverkehr")
    #expect(ExplainScreen.from(.person(slug: "anna-muster"))?.refs.slug == "anna-muster")
    #expect(ExplainScreen.from(.analysis)?.route == "/council?tab=analysis")
    #expect(ExplainScreen.from(.tab(.today))?.route == "/dashboard")
}

@Test("Auf der Ortsseite ist die Kennung ein Kürzel, keine Zahl")
func ortsKennung() throws {
    let screen = try #require(ExplainScreen.from(.place(id: "stadtteil:eversten")))
    #expect(screen.refs.placeID == "stadtteil:eversten")
    // Sonst läge eine Zahl im falschen Feld und das Backend schlüge den
    // falschen Datensatz nach — genau der Fehler, den das Web schon hatte.
    #expect(screen.refs.decisionID == nil)
}

@Test("Wo es Lotti nicht gibt, gibt es auch keinen Bildschirm")
func gesperrteScreens() throws {
    #expect(ExplainScreen.from(.tab(.account)) == nil)
    #expect(ExplainScreen.from(.admin) == nil)
    #expect(ExplainScreen.from(.web(URL(string: "https://example.org")!)) == nil)
}

// MARK: - Der Auftrag

@Test("Der Auftrag trägt die Kennungen als das, was sie sind")
func auftragKodiert() throws {
    let daten = try JSONEncoder().encode(ExplainRequest(
        route: "/council/decision", pageTitle: "Beschluss", heading: "Stadion",
        question: "Was ist das?", refs: ExplainRefs(decisionID: 8525)))
    let roh = try #require(try JSONSerialization.jsonObject(with: daten) as? [String: Any])
    #expect(roh["page_title"] as? String == "Beschluss")
    let refs = try #require(roh["refs"] as? [String: Any])
    #expect(refs["decision_id"] as? Int == 8525)
    // Leere Felder bleiben weg — das Backend prüft jeden Wert, und ein
    // ausdrückliches `null` wäre nur mehr Papier.
    #expect(refs["ksinr"] == nil)
    // `conversation_id` dagegen MUSS auch als null mitgehen: Ein Client ohne
    // das Feld speichert gar nichts (dieselbe Regel wie bei der Frage).
    #expect(roh.keys.contains("conversation_id"))
}

// MARK: - Der Schluss-Rahmen

@Test("Der Schluss-Rahmen wird mit und ohne Anschluss gelesen")
func schlussRahmen() throws {
    let mit = try JSONDecoder().decode(ExplainDone.self, from: Data("""
    {"type":"done","mode":"explain","next":"ratsfrage","glossary":["Tilgung"],
     "conversation_id":12,"timings":{"total_ms":900}}
    """.utf8))
    #expect(mit.mode == "explain")
    #expect(mit.leadsToCouncilQuestion)
    #expect(mit.glossary == ["Tilgung"])
    #expect(mit.conversationID == 12)

    let ohne = try JSONDecoder().decode(ExplainDone.self, from: Data("""
    {"type":"done","mode":"deterministic","next":null,"glossary":[]}
    """.utf8))
    #expect(ohne.mode == "deterministic")
    #expect(!ohne.leadsToCouncilQuestion)
    #expect(ohne.conversationID == nil)
}

@Test("Ein unvollständiger Schluss-Rahmen kippt die Antwort nicht")
func schlussRahmenGehaertet() throws {
    // Ohne `mode` bliebe sonst die Tipp-Anzeige stehen, obwohl der Text
    // vollständig da ist — ein Ende, das nur am Decoder scheitert.
    let sparsam = try JSONDecoder().decode(ExplainDone.self, from: Data(#"{"type":"done"}"#.utf8))
    #expect(sparsam.mode == "explain")
    #expect(sparsam.glossary.isEmpty)
}
