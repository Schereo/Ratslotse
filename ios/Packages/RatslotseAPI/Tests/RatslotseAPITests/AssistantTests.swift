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

// MARK: - Die Längengrenze (Release-Prüfung 03.10.2026)

@Test("Die Grenze spiegelt den Server, der Zähler kommt erst nahe daran")
func frageGrenze() {
    #expect(LottiFrage.maxZeichen == 300)
    #expect(LottiFrage.zaehler("kurz") == nil)
    #expect(LottiFrage.zaehler(String(repeating: "a", count: 262)) == "262/300")
    #expect(LottiFrage.gekuerzt(String(repeating: "a", count: 320)).count == 300)
    #expect(LottiFrage.gekuerzt("kurz") == "kurz")
}

@Test("Ein 422 wird ein Satz, keine englische Pydantic-Meldung")
func frageFehlerText() {
    let zuLang = APIError(statusCode: 422, message: "String should have at most 300 characters")
    #expect(LottiFrage.fehlerText(zuLang).contains("zu lang"))
    #expect(!LottiFrage.fehlerText(zuLang).contains("String should"))
    // Der Satz des Servers bleibt, wo er für Menschen geschrieben ist.
    let kontingent = APIError(statusCode: 429, message: "Für heute ist Schluss.")
    #expect(LottiFrage.fehlerText(kontingent) == "Für heute ist Schluss.")
}

@Test("Der Schluss-Rahmen einer Weiterreichung trägt mode handoff")
func handoffRahmen() throws {
    let json = Data(#"{"type":"done","mode":"handoff","kind":"archiv","next":"ratsfrage","evidence":[]}"#.utf8)
    let done = try JSONDecoder().decode(ExplainDone.self, from: json)
    #expect(done.mode == "handoff")
    #expect(done.leadsToCouncilQuestion)
}

// MARK: - Wo der Knopf steht

@Test("Die Merkliste ist ein eigener Screen mit eigener Route")
func merklisteHatEineRoute() throws {
    // Bis 10/2026 stand "/bookmarks" in AppModel von Hand — die Merkliste
    // hatte keine App-Route und lag am Stapel vorbei.
    #expect(ExplainScreen.from(.saved)?.route == "/bookmarks")
    #expect(ExplainScreen.from(.saved)?.refs == ExplainRefs())
}

@Test("Über der Tab-Leiste nur auf der Wurzel, auf einer geschobenen Seite ganz unten")
func knopfAbstand() {
    // Wurzel: über der Leiste.
    #expect(LottiPlacement.bottomClearance(stackDepth: 0, tabBarHeight: 72, keyboardVisible: false) == 72)
    // Beschluss, Bewegung, Sitzung …: Die Seite verdeckt die Leiste — ein
    // Knopf in ihrer Höhe schwebte mitten im Inhalt.
    #expect(LottiPlacement.bottomClearance(stackDepth: 1, tabBarHeight: 72, keyboardVisible: false) == 0)
    #expect(LottiPlacement.bottomClearance(stackDepth: 3, tabBarHeight: 72, keyboardVisible: false) == 0)
    // Tastatur offen: Die Leiste weicht.
    #expect(LottiPlacement.bottomClearance(stackDepth: 0, tabBarHeight: 72, keyboardVisible: true) == 0)
}

@Test("Jede erklärbare Seite hält unten Platz für den Knopf frei", arguments: [
    AppRoute.decision(id: 1), .sessions(ksinr: 7, tops: []), .person(slug: "anna-muster"),
    .topic(slug: "radverkehr"), .place(id: "stadtteil:eversten"), .movement(id: 5), .ideas,
    .district(id: "eversten"), .analysis, .subscriptions, .saved, .quiz(area: nil),
])
func seitenHaltenPlatzFrei(route: AppRoute) {
    #expect(LottiPlacement.pageInset(for: route, enabled: true, keyboardVisible: false)
            == LottiPlacement.pageInset)
    // Ohne Schalter oder mit Tastatur steht kein Knopf da — dann auch kein Loch.
    #expect(LottiPlacement.pageInset(for: route, enabled: false, keyboardVisible: false) == 0)
    #expect(LottiPlacement.pageInset(for: route, enabled: true, keyboardVisible: true) == 0)
}

@Test("Wo es Lotti nicht gibt, bleibt auch unten kein Loch")
func ohneLottiKeinRand() {
    #expect(LottiPlacement.pageInset(for: .admin, enabled: true, keyboardVisible: false) == 0)
    let fremd = AppRoute.web(URL(string: "https://example.org")!)
    #expect(LottiPlacement.pageInset(for: fremd, enabled: true, keyboardVisible: false) == 0)
}
