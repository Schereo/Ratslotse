import Foundation
import Testing
@testable import RatslotseAPI

/// 17:00 in Oldenburg ist 15:00 UTC im Sommer und 16:00 UTC im Winter —
/// unabhängig davon, in welcher Zone das Gerät gerade steht.
@Test(arguments: [
    ("2026-07-01", "17:00", "2026-07-01T15:00:00Z"),
    ("2026-07-01", "17:00:00", "2026-07-01T15:00:00Z"),
    ("2026-12-03", "16:30", "2026-12-03T15:30:00Z"),
    ("2026-12-03T00:00:00", nil, "2026-12-03T16:00:00Z"),
    ("2026-12-03", "", "2026-12-03T16:00:00Z"),
])
func sessionStartIsBerlinTime(day: String, time: String?, utc: String) throws {
    let erwartet = try #require(ISO8601DateFormatter().date(from: utc))
    #expect(SessionClock.start(day: day, time: time) == erwartet)
}

@Test func unreadableDayGivesNil() {
    #expect(SessionClock.start(day: "irgendwann", time: "17:00") == nil)
}
