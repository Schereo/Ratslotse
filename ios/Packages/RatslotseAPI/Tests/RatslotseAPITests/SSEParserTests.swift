import Foundation
import Testing
@testable import RatslotseAPI

/// Liest eine aufgezeichnete Antwort und gibt die decodierten Ereignisse.
private func frames(_ name: String) throws -> [SSEEvent] {
    let url = try #require(Bundle.module.url(
        forResource: name, withExtension: "sse", subdirectory: "Fixtures"
    ))
    let raw = try String(contentsOf: url, encoding: .utf8)
    var parser = SSEParser()
    var payloads = raw.split(separator: "\n", omittingEmptySubsequences: false)
        .compactMap { parser.consume(line: String($0)) }
    if let finalPayload = parser.finish() {
        payloads.append(finalPayload)
    }
    let decoder = JSONDecoder()
    return try payloads.map { try decoder.decode(SSEEvent.self, from: Data($0.utf8)) }
}

@Test func recordedAskStreamParsesAllFrames() throws {
    let events = try frames("ask")

    #expect(events.map(\.type) == [
        "step", "step", "sources", "step", "token", "token",
        "replace", "suggestions", "done",
    ])
    #expect(events.filter { $0.type == "token" }.compactMap(\.text).joined() == "Die Stadt baut aus [42].")
    #expect(events.last?.conversationID == 7)
    #expect(events.last?.fields["cited"]?.array?.compactMap(\.int) == [42])
}

/// Die Anschlussfragen heißen auf der Leitung `questions`. Die Aufzeichnung
/// benutzte bis 02.09.2026 `suggestions` — ein Name, den der Server NIE
/// gesendet hat; die Probe prüfte damit gegen eine erfundene Nutzlast.
@Test func followUpQuestionsComeFromTheFieldTheServerSends() throws {
    let events = try frames("ask")
    let vorschlaege = try #require(events.first { $0.type == "suggestions" })
    #expect(vorschlaege.suggestions == ["Wann beginnt das?"])
}

/// Der Tagesordnungs-Baustein reist im `sources`-Rahmen mit und heißt seit
/// #913 `sessions`. Im Web stand danach an drei Stellen weiter `sitzungen`,
/// und der Baustein verschwand — deshalb hält die Probe den Namen fest.
@Test func sourcesFrameCarriesAgendaSessions() throws {
    let quellen = try #require(try frames("ask").first { $0.type == "sources" })
    let sitzungen = try #require(quellen.fields["sessions"]?.array)
    #expect(sitzungen.count == 1)
    #expect(sitzungen.first?.object?["committee"]?.string == "Verkehrsausschuss")
}

/// Die beiden Schluss-Rahmen, die es in keiner geglückten Antwort gibt — und
/// die deshalb bis 02.09.2026 in keiner Aufzeichnung standen.
@Test func abortAndErrorFramesDecode() throws {
    let abbruch = try frames("ask-abbruch")
    #expect(abbruch.map(\.type) == ["token", "abbruch"])

    let fehler = try frames("ask-fehler")
    #expect(fehler.map(\.type) == ["step", "error"])
    #expect(fehler.last?.fields["message"]?.string == "Frage fehlgeschlagen.")
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
