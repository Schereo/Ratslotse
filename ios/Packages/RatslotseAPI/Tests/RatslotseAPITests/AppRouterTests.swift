import Foundation
import Testing
@testable import RatslotseAPI

private let router = AppRouter()

@Test(arguments: [
    ("https://ratslotse.de/dashboard", AppRoute.tab(.today)),
    ("https://ratslotse.de/fragen?q=Was%20wird%20gebaut%3F", .question(prefill: "Was wird gebaut?", share: nil)),
    ("https://ratslotse.de/council/decision?id=42", .decision(id: 42)),
    // Eine Bewegung — dieselbe Idee in mehreren anderen Räten (Plan PR 54).
    ("https://ratslotse.de/council/ideen/bewegung?id=14", .movement(id: 14)),
    // Die Ideen-Übersicht — bis 10/2026 fiel sie auf `.web` und aus der App.
    ("https://ratslotse.de/council/ideen", .ideas),
    ("https://ratslotse.de/council/ideen/", .ideas),
    ("https://ratslotse.de/council?tab=sessions&ksinr=123&top=%C3%96%206%2CN%206", .sessions(ksinr: 123, tops: ["Ö 6", "N 6"])),
    // Die geteilte Sitzungs-Seite — sie liest sich ohne Konto und ist deshalb
    // das Ziel der Teilen-Knöpfe; die Listen-Adresse darüber bleibt gültig
    // (sie steht in Mails und Push).
    ("https://ratslotse.de/council/sitzung?ksinr=123", .sessions(ksinr: 123, tops: [])),
    ("https://ratslotse.de/council/sitzung?ksinr=123&top=%C3%96%206", .sessions(ksinr: 123, tops: ["Ö 6"])),
    ("https://ratslotse.de/council/person?slug=anna-muster", .person(slug: "anna-muster")),
    ("https://ratslotse.de/council/thema?slug=radverkehr", .topic(slug: "radverkehr")),
    ("https://ratslotse.de/council/ort?id=stadtteil%3Aeversten", .place(id: "stadtteil:eversten")),
    ("https://ratslotse.de/viertel", .district(id: nil)),
    ("https://ratslotse.de/viertel?id=kreyenbrueck", .district(id: "kreyenbrueck")),
    // Die vereinte Stadtkarte (Schritt 5): dieselbe Ansicht, neue Adresse.
    ("https://ratslotse.de/karte", .district(id: nil)),
    // `v` öffnet das Vorhaben (bis 10/2026 fiel es weg); ohne Ort zählt es nicht.
    ("https://ratslotse.de/karte?ort=kreyenbrueck&v=94", .district(id: "kreyenbrueck", project: 94)),
    ("https://ratslotse.de/karte?ort=kreyenbrueck&v=abc", .district(id: "kreyenbrueck")),
    ("https://ratslotse.de/karte?v=94", .district(id: nil)),
    ("https://ratslotse.de/viertel?id=kreyenbrueck&v=7", .district(id: "kreyenbrueck", project: 7)),
    ("https://ratslotse.de/topics", .tab(.topics)),
    // Ziel der Kalender-Neuerung auf der Karte „Neu bei Ratslotse" — bis
    // 09/2026 landete /abos im Browser statt auf dem eigenen Screen.
    ("https://ratslotse.de/abos", .subscriptions),
    ("https://ratslotse.de/g?t=abc", .sharedAnswer(token: "abc")),
])
func mapsHistoricalUniversalLinks(input: String, expected: AppRoute) throws {
    let url = try #require(URL(string: input))
    #expect(router.route(for: url) == expected)
}

@Test func authLinksRequireTokens() throws {
    let verify = try #require(URL(string: "https://ratslotse.de/verify-email?token=abc"))
    let reset = try #require(URL(string: "https://ratslotse.de/reset-password?token=def"))
    #expect(router.route(for: verify) == .verifyEmail(token: "abc"))
    #expect(router.route(for: reset) == .resetPassword(token: "def"))
}

@Test func foreignHostStaysOnWeb() throws {
    let url = try #require(URL(string: "https://example.org/council/decision?id=42"))
    #expect(router.route(for: url) == .web(url))
}

@Test func routesRoundTripThroughCanonicalLinks() {
    let routes: [AppRoute] = [
        .tab(.today), .tab(.questions), .tab(.council), .tab(.topics),
        .question(prefill: "Was kostet das?", share: nil),
        .decision(id: 91), .sessions(ksinr: 8, tops: ["Ö 2"]),
        .person(slug: "max-muster"), .topic(slug: "wohnen"), .place(id: "ort:1"),
        .sharedAnswer(token: "share-token"),
        .district(id: nil), .district(id: "eversten"), .district(id: "eversten", project: 12),
        .ideas, .movement(id: 14),
    ]
    for route in routes {
        let link = router.universalLink(for: route)
        #expect(link != nil)
        #expect(router.route(for: link!) == route)
    }
}

/** Ein geteilter Link zeigt auf die ohne Konto lesbare Sitzungs-Seite — nicht
 *  auf die Liste, die eine Anmeldung verlangt. */
@Test func sharedSessionLinkPointsToThePublicPage() throws {
    let link = try #require(router.universalLink(for: .sessions(ksinr: 8, tops: ["Ö 2"])))
    #expect(link.path == "/council/sitzung")
    #expect(link.absoluteString.contains("ksinr=8"))
    #expect(router.route(for: link) == .sessions(ksinr: 8, tops: ["Ö 2"]))
}

/** Der neue Rat gibt es nur im Web — ausdrücklich, nicht über den Rückfall.
 *  Die Universal-Link-Datei nimmt die Adresse mit `NOT` aus
 *  (`tests/test_universal_links.py` hält beides zusammen). */
@Test func newCouncilStaysOnTheWeb() throws {
    let url = try #require(URL(string: "https://ratslotse.de/council/neuer-rat"))
    #expect(router.route(for: url) == .web(url))
}

/** Die Merkliste hat seit 10/2026 eine Route, aber nur nach außen: Ihre Adresse
 *  ist die Web-Seite, gelesen wird sie nicht. Die Universal-Link-Datei lässt
 *  `/bookmarks` nicht in die App — nähme sie es auf, schickte die
 *  ausgelieferte App (ohne `.saved`) jeden solchen Link gleich wieder hinaus. */
@Test func savedListLinksToTheWebPageOnly() throws {
    let link = try #require(router.universalLink(for: .saved))
    #expect(link.path == "/bookmarks")
    #expect(router.route(for: link) == .web(link))
}
