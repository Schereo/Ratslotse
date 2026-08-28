import Foundation
import Testing
@testable import RatslotseAPI

@Test func recordedAskStreamParsesAllFrames() throws {
    let url = try #require(Bundle.module.url(
        forResource: "ask", withExtension: "sse", subdirectory: "Fixtures"
    ))
    let raw = try String(contentsOf: url, encoding: .utf8)
    var parser = SSEParser()
    var payloads = raw.split(separator: "\n", omittingEmptySubsequences: false)
        .compactMap { parser.consume(line: String($0)) }
    if let finalPayload = parser.finish() {
        payloads.append(finalPayload)
    }
    let decoder = JSONDecoder()
    let events = try payloads.map { try decoder.decode(SSEEvent.self, from: Data($0.utf8)) }

    #expect(events.map(\.type) == ["step", "sources", "token", "token", "suggestions", "done"])
    #expect(events.filter { $0.type == "token" }.compactMap(\.text).joined() == "Die Stadt baut aus [42].")
    #expect(events.last?.conversationID == 7)
}

@Test func parserJoinsDataLinesAndIgnoresKeepalive() {
    var parser = SSEParser()
    #expect(parser.consume(line: ": ping") == nil)
    #expect(parser.consume(line: "data: first") == nil)
    #expect(parser.consume(line: "data: second") == nil)
    #expect(parser.consume(line: "") == "first\nsecond")
}
