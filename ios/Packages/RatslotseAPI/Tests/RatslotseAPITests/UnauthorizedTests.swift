import Foundation
import Testing
@testable import RatslotseAPI

/// Ein 401 mitten in der Sitzung meldet sich an EINER Stelle — und nur, wenn
/// die abgelehnte Anfrage das aktuelle Token trug.

private actor Zaehler {
    private(set) var n = 0
    func hoch() { n += 1 }
}

private func client(_ status: Int) -> APIClient {
    let configuration = URLSessionConfiguration.ephemeral
    configuration.protocolClasses = [status == 401 ? Status401.self : Status200.self]
    return APIClient(baseURL: URL(string: "https://ratslotse.test")!,
                     session: URLSession(configuration: configuration),
                     keychain: KeychainStore(service: "de.ratslotse.test.unauthorized"))
}

private struct Leer: Codable, Sendable {}

@Test func a401OnTheOwnTokenIsReportedOnceAndDropsTheToken() async throws {
    let api = client(401)
    let zaehler = Zaehler()
    await api.onUnauthorized { await zaehler.hoch() }
    await api.setAccessTokenInMemory("abgelaufen")

    for _ in 0..<3 {
        do {
            let _: Leer = try await api.get("/api/auth/me")
            Issue.record("Hätte mit 401 scheitern müssen.")
        } catch let error as APIError {
            #expect(error.isUnauthorized)
        }
    }
    // Der Handler läuft in einer eigenen Aufgabe — kurz warten.
    for _ in 0..<50 where await zaehler.n == 0 { try await Task.sleep(nanoseconds: 10_000_000) }
    #expect(await zaehler.n == 1, "nur die erste Ablehnung trug das Token — keine Schleife")
    #expect(await api.hasAccessToken() == false)
}

@Test func a401WithoutTokenReportsNothing() async throws {
    // Falsches Passwort bei der Anmeldung: kein Token, also kein Abmelden.
    let api = client(401)
    let zaehler = Zaehler()
    await api.onUnauthorized { await zaehler.hoch() }
    do {
        try await api.sendVoid("/api/auth/login")
    } catch {}
    try await Task.sleep(nanoseconds: 50_000_000)
    #expect(await zaehler.n == 0)
}

@Test func successKeepsTheToken() async throws {
    let api = client(200)
    await api.setAccessTokenInMemory("gut")
    let _: Leer = try await api.get("/api/auth/me")
    #expect(await api.hasAccessToken())
}

private final class Status401: URLProtocol {
    override class func canInit(with request: URLRequest) -> Bool { true }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }
    override func startLoading() { antworte(self, 401, #"{"detail":"Nicht angemeldet."}"#) }
    override func stopLoading() {}
}

private final class Status200: URLProtocol {
    override class func canInit(with request: URLRequest) -> Bool { true }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }
    override func startLoading() { antworte(self, 200, "{}") }
    override func stopLoading() {}
}

private func antworte(_ p: URLProtocol, _ status: Int, _ body: String) {
    guard let url = p.request.url, let response = HTTPURLResponse(
        url: url, statusCode: status, httpVersion: "HTTP/1.1",
        headerFields: ["Content-Type": "application/json"]
    ) else { return }
    p.client?.urlProtocol(p, didReceive: response, cacheStoragePolicy: .notAllowed)
    p.client?.urlProtocol(p, didLoad: Data(body.utf8))
    p.client?.urlProtocolDidFinishLoading(p)
}
