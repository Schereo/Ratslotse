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

@Test func parserAcceptsCRLFFrames() {
    var parser = SSEParser()
    #expect(parser.consume(line: #"data: {"type":"done"}"# + "\r") == nil)
    #expect(parser.consume(line: "\r") == #"{"type":"done"}"#)
}

@Test(arguments: ["\n", "\r\n", "\r"])
func byteParserPreservesEmptyEventSeparators(lineEnding: String) {
    var parser = SSEParser()
    let stream = [
        #"data: {"type":"step","step":"search"}"#,
        "",
        #"data: {"type":"done"}"#,
        "",
    ].joined(separator: lineEnding)
    var payloads: [String] = []
    for byte in stream.utf8 {
        if let payload = parser.consume(byte: byte) { payloads.append(payload) }
    }
    if let payload = parser.finish() { payloads.append(payload) }

    #expect(payloads == [
        #"{"type":"step","step":"search"}"#,
        #"{"type":"done"}"#,
    ])
}

@Test func malformedFrameDoesNotAbortFollowingAnswerEvents() {
    let client = SSEClient()
    let payloads = [
        #"{"type":"step","step":"expand"}"#,
        #"{this frame is not json}"#,
        #"{"type":"token","text":"Die Antwort bleibt erhalten."}"#,
        #"{"type":"done"}"#,
    ]
    let events = payloads.compactMap { client.decode(payload: $0) }

    #expect(events.map(\.type) == ["step", "token", "done"])
    #expect(events.compactMap(\.text).joined() == "Die Antwort bleibt erhalten.")
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
