import Foundation
import Testing
@testable import RatslotseAPI

// `/api/wahlabend/karte`, aufgezeichnet vom Backend (dieselbe Abschrift wie
// im Browsertest `24-wahlkarte.spec.ts`, auf Krusenbusch gekürzt).

private func karte() throws -> ElectionMap {
    let url = try #require(Bundle.module.url(forResource: "wahlkarte-krusenbusch", withExtension: "json", subdirectory: "Fixtures"))
    return try JSONDecoder().decode(ElectionMap.self, from: Data(contentsOf: url))
}

@Test func electionMapDecodesTheRecordedAnswer() throws {
    let map = try karte()
    #expect(map.election.slug == "ratswahl-2026")
    #expect(map.total == 91 && map.ties == 1)
    #expect(map.wins.first?.slug == "spd")
    #expect(map.contestant("afd")?.short == "AfD")
    let district = try #require(map.districts.first { $0.number == 515 })
    #expect(district.leader == "afd")
    #expect(district.places.first?.name == "Krusenbusch")
}

@Test func districtsInPlaceSortByShare() throws {
    let map = try karte()
    let numbers = map.districts(in: "Krusenbusch").map(\.number)
    #expect(numbers.count == 3)
    #expect(numbers.last == 516)   // liegt nur zu einem Zehntel darin
}

@Test func opacityFollowsTheWebFormula() {
    #expect(ElectionMap.opacity(margin: nil) == 0)
    #expect(abs(ElectionMap.opacity(margin: 0) - 0.15) < 0.001)
    #expect(abs(ElectionMap.opacity(margin: 40) - 0.75) < 0.001)
}

@Test func electionMapToleratesMissingOptionalFields() throws {
    let json = #"{"election": {"slug": "ob-2026", "label": "OB-Wahl", "kind": "mayor", "date": "2026-09-13"}}"#
    let map = try JSONDecoder().decode(ElectionMap.self, from: Data(json.utf8))
    #expect(map.elections.count == 1 && map.districts.isEmpty && map.ties == 0)
}
