import Foundation
import Testing
@testable import RatslotseAPI

/// Wie ein Pfad beim Server ankommt. Anlass (Review 3.0.0): „Stimmt das?" an
/// jeder Idee aus einer OParl-Stadt endete mit 404, weil die Kennung eine
/// Adresse ist und ihr `//` den Weg zum Server nicht überstand.

private let basis = URL(string: "https://ratslotse.de")!

@Test func eineAdresseAlsKennungGehtAlsEinPfadstueck() throws {
    let kennung = "https://www.stadt-hildesheim.de/allris/vo020.asp?VOLFDNR=6464"
    let url = try #require(APIClient.endpointURL(
        base: basis, path: "/api/council/cities/ideas/\(APIClient.pathSegment(kennung))/feedback"))
    #expect(url.absoluteString ==
        "https://ratslotse.de/api/council/cities/ideas/"
        + "https%3A%2F%2Fwww.stadt-hildesheim.de%2Fallris%2Fvo020.asp%3FVOLFDNR%3D6464/feedback")
    #expect(!url.absoluteString.dropFirst("https://".count).contains("//"))
}

@Test func gewoehnlichePfadeBleibenWieBisher() throws {
    // Was `URL.appending(path:)` vorher tat, gilt weiter: Leerzeichen und
    // „?" werden kodiert, Schrägstriche bleiben Trenner.
    let url = try #require(APIClient.endpointURL(base: basis, path: "/api/council/person/anna muster"))
    #expect(url.absoluteString == "https://ratslotse.de/api/council/person/anna%20muster")
    let frage = try #require(APIClient.endpointURL(base: basis, path: "api/x?y"))
    #expect(frage.absoluteString == "https://ratslotse.de/api/x%3Fy")
    let umlaut = try #require(APIClient.endpointURL(base: basis, path: "/api/council/place/ö"))
    #expect(umlaut.absoluteString == "https://ratslotse.de/api/council/place/%C3%B6")
}

@Test func einLoseProzentzeichenWirdKodiert() throws {
    // Nur ein echtes „%XX" gilt als schon kodiert; ein loses „%" darf die
    // Adresse nicht ungültig machen.
    let url = try #require(APIClient.endpointURL(base: basis, path: "/api/x/100%"))
    #expect(url.absoluteString == "https://ratslotse.de/api/x/100%25")
}

@Test func eineBasisMitPfadBehaeltIhn() throws {
    let lokal = URL(string: "http://127.0.0.1:8600/vorne")!
    let url = try #require(APIClient.endpointURL(base: lokal, path: "/api/health"))
    #expect(url.absoluteString == "http://127.0.0.1:8600/vorne/api/health")
}
