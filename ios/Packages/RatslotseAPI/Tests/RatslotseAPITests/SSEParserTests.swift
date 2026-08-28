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

@Test func streamingErrorsKeepBackendMessageAndRetryDelay() async throws {
    let configuration = URLSessionConfiguration.ephemeral
    configuration.protocolClasses = [RateLimitURLProtocol.self]
    let client = SSEClient(session: URLSession(configuration: configuration))
    let request = URLRequest(url: try #require(URL(string: "https://ratslotse.test/stream")))

    do {
        for try await _ in client.events(for: request) {}
        Issue.record("Der Fehlerstream hätte fehlschlagen müssen.")
    } catch let error as APIError {
        #expect(error.statusCode == 429)
        #expect(error.message == "Bitte kurz warten.")
        #expect(error.retryAfter == 17)
    }
}

private final class RateLimitURLProtocol: URLProtocol {
    override class func canInit(with request: URLRequest) -> Bool { true }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }
    override func startLoading() {
        guard let url = request.url, let response = HTTPURLResponse(
            url: url, statusCode: 429, httpVersion: "HTTP/1.1",
            headerFields: ["Content-Type": "application/json", "Retry-After": "17"]
        ) else {
            client?.urlProtocol(self, didFailWithError: URLError(.badURL))
            return
        }
        client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
        client?.urlProtocol(self, didLoad: Data(#"{"detail":"Bitte kurz warten."}"#.utf8))
        client?.urlProtocolDidFinishLoading(self)
    }
    override func stopLoading() {}
}
