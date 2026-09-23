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

// MARK: - Der Anstupser

private let jetzt: TimeInterval = 1_758_000_000
private let tag = NudgeLimits.tag

/// Ein Kontext, der alle Bedingungen erfüllt — jeder Test verletzt genau eine.
private func erfuellt(
    screenAllowed: Bool = true, readingTime: TimeInterval = 50,
    sinceInteraction: TimeInterval = 3, screensThisSession: Int = 3,
    sheetWasOpen: Bool = false, usedToday: Bool = false, busy: Bool = false
) -> NudgeContext {
    NudgeContext(screenAllowed: screenAllowed, readingTime: readingTime,
                 sinceInteraction: sinceInteraction, screensThisSession: screensThisSession,
                 sheetWasOpen: sheetWasOpen, usedToday: usedToday, busy: busy)
}

@Test("Sind alle Bedingungen erfüllt, klopft Lotti an")
func anstupserGrundfall() {
    #expect(AssistantNudge.mayAppear(.empty, erfuellt(), now: jetzt))
}

@Test("Jede einzelne Grenze hält für sich")
func anstupserGrenzen() {
    // Die Reihenfolge ist die der Funktion — jede Zeile ist eine Bedingung.
    #expect(!AssistantNudge.mayAppear(.empty, erfuellt(screenAllowed: false), now: jetzt))
    #expect(!AssistantNudge.mayAppear(.empty, erfuellt(busy: true), now: jetzt))
    #expect(!AssistantNudge.mayAppear(.empty, erfuellt(sheetWasOpen: true), now: jetzt))
    #expect(!AssistantNudge.mayAppear(.empty, erfuellt(usedToday: true), now: jetzt))
    // Die ersten beiden Screens einer Sitzung bleiben in Ruhe.
    #expect(!AssistantNudge.mayAppear(.empty, erfuellt(screensThisSession: 2), now: jetzt))
    #expect(!AssistantNudge.mayAppear(.empty, erfuellt(readingTime: 44), now: jetzt))
    // Wer 30 s nichts angefasst hat, ist ein liegengelassener Screen.
    #expect(!AssistantNudge.mayAppear(.empty, erfuellt(sinceInteraction: 30), now: jetzt))
}

@Test("Genau an der Grenze wird angeklopft, nicht knapp davor")
func anstupserGenauAnDerGrenze() {
    #expect(AssistantNudge.mayAppear(.empty, erfuellt(readingTime: 45), now: jetzt))
    #expect(AssistantNudge.mayAppear(.empty, erfuellt(sinceInteraction: 10), now: jetzt))
}

@Test("Höchstens einmal am Tag")
func anstupserProTag() {
    let heute = NudgeState(last: jetzt - 3600, within30Days: [jetzt - 3600])
    #expect(!AssistantNudge.mayAppear(heute, erfuellt(), now: jetzt))
    let gestern = NudgeState(last: jetzt - tag - 1, within30Days: [jetzt - tag - 1])
    #expect(AssistantNudge.mayAppear(gestern, erfuellt(), now: jetzt))
}

@Test("Höchstens dreimal in 30 Tagen — ältere zählen nicht mit")
func anstupserPro30Tage() {
    let drei = NudgeState(last: jetzt - 2 * tag,
                          within30Days: [jetzt - 2 * tag, jetzt - 5 * tag, jetzt - 9 * tag])
    #expect(!AssistantNudge.mayAppear(drei, erfuellt(), now: jetzt))
    let zweiPlusAlt = NudgeState(last: jetzt - 2 * tag,
                                 within30Days: [jetzt - 2 * tag, jetzt - 5 * tag,
                                                jetzt - 40 * tag])
    #expect(AssistantNudge.mayAppear(zweiPlusAlt, erfuellt(), now: jetzt))
}

@Test("Nach zwei × ist zwei Monate Ruhe")
func anstupserNachAblehnung() {
    let zweimalNein = NudgeState(last: jetzt - 10 * tag, within30Days: [jetzt - 10 * tag],
                                 dismissals: 2)
    #expect(!AssistantNudge.mayAppear(zweimalNein, erfuellt(), now: jetzt))
    let langeHer = NudgeState(last: jetzt - 70 * tag, within30Days: [], dismissals: 2)
    #expect(AssistantNudge.mayAppear(langeHer, erfuellt(), now: jetzt))
}

@Test("Nach einem Ja sind zwei Wochen Ruhe — und der Zähler beginnt von vorn")
func anstupserNachJa() {
    let ja = AssistantNudge.afterAccept(NudgeState(dismissals: 2), now: jetzt - 3 * tag)
    #expect(ja.dismissals == 0)
    #expect(!AssistantNudge.mayAppear(ja, erfuellt(), now: jetzt))
    #expect(AssistantNudge.mayAppear(ja, erfuellt(), now: jetzt + 12 * tag))
}

@Test("Ein gezeigter Anstupser schreibt sich in beide Zähler")
func anstupserNachAnzeige() {
    let neu = AssistantNudge.afterShowing(.empty, now: jetzt)
    #expect(neu.last == jetzt)
    #expect(neu.within30Days == [jetzt])
    // Und er zählt NICHT als Ablehnung: Wer nicht hinsieht, hat nicht Nein gesagt.
    #expect(neu.dismissals == 0)
}

@Test("Die App klopft nur dort an, wo es erlaubt ist")
func anstupserSeiten() {
    #expect(ExplainScreen(route: "/haushalt/schulden").allowsNudge)
    #expect(ExplainScreen(route: "/council/decision").allowsNudge)
    // Auf der Fragen-Seite fragt man schon — eine Blase daneben wäre eine
    // zweite Aufforderung zu derselben Sache.
    #expect(!ExplainScreen(route: "/fragen").allowsNudge)
    #expect(!ExplainScreen(route: "/dashboard").allowsNudge)
    #expect(!ExplainScreen(route: "/topics").allowsNudge)
}
