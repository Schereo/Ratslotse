import Foundation
import Testing
@testable import RatslotseAPI

private let router = AppRouter()

@Test(arguments: [
    ("https://ratslotse.de/dashboard", AppRoute.tab(.today)),
    ("https://ratslotse.de/fragen?q=Was%20wird%20gebaut%3F", .question(prefill: "Was wird gebaut?", share: nil)),
    ("https://ratslotse.de/council/decision?id=42", .decision(id: 42)),
    ("https://ratslotse.de/council?tab=sessions&ksinr=123&top=%C3%96%206%2CN%206", .sessions(ksinr: 123, tops: ["Ö 6", "N 6"])),
    // Die geteilte Sitzungs-Seite — sie liest sich ohne Konto und ist deshalb
    // das Ziel der Teilen-Knöpfe; die Listen-Adresse darüber bleibt gültig
    // (sie steht in Mails und Push).
    ("https://ratslotse.de/council/sitzung?ksinr=123", .sessions(ksinr: 123, tops: [])),
    ("https://ratslotse.de/council/sitzung?ksinr=123&top=%C3%96%206", .sessions(ksinr: 123, tops: ["Ö 6"])),
    ("https://ratslotse.de/council/person?slug=anna-muster", .person(slug: "anna-muster")),
    ("https://ratslotse.de/council/thema?slug=radverkehr", .topic(slug: "radverkehr")),
    ("https://ratslotse.de/council/ort?id=stadtteil%3Aeversten", .place(id: "stadtteil:eversten")),
    ("https://ratslotse.de/topics", .tab(.topics)),
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
