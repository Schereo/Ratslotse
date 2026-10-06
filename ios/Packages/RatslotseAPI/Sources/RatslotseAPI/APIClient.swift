import Foundation

public enum HTTPMethod: String, Sendable {
    case get = "GET"
    case post = "POST"
    case put = "PUT"
    case patch = "PATCH"
    case delete = "DELETE"
}

public struct APIError: Error, Sendable, Equatable, LocalizedError {
    public let statusCode: Int
    public let message: String
    public let retryAfter: TimeInterval?

    public init(statusCode: Int, message: String, retryAfter: TimeInterval? = nil) {
        self.statusCode = statusCode
        self.message = message
        self.retryAfter = retryAfter
    }

    public var errorDescription: String? { message }
    public var isUnauthorized: Bool { statusCode == 401 }
    public var isAccountBlocked: Bool { statusCode == 403 }
    public var isRateLimited: Bool { statusCode == 429 }
}

private struct ValidationDetail: Decodable {
    let loc: [JSONValue]?
    let msg: String?
}

private struct ErrorEnvelope: Decodable {
    let detail: JSONValue?
}

public actor APIClient {
    public static let productionURL = URL(string: "https://ratslotse.de")!

    private let baseURL: URL
    private let session: URLSession
    private let encoder: JSONEncoder
    private let decoder: JSONDecoder
    private let keychain: KeychainStore
    private var accessToken: String?
    /// Wird gerufen, wenn der Server ein mitgeschicktes Token mit 401
    /// ablehnt — s. `onUnauthorized(_:)`.
    private var unauthorizedHandler: (@Sendable () async -> Void)?

    public init(
        baseURL: URL = productionURL,
        session: URLSession = .shared,
        keychain: KeychainStore = KeychainStore()
    ) {
        self.baseURL = baseURL
        self.session = session
        self.keychain = keychain
        encoder = JSONEncoder()
        decoder = JSONDecoder()
    }

    @discardableResult
    public func restoreAccessToken() -> String? {
#if DEBUG
        if let token = ProcessInfo.processInfo.environment["RATSLOTSE_DEBUG_ACCESS_TOKEN"],
           !token.isEmpty {
            accessToken = token
            return token
        }
#endif
        do {
            let token = try keychain.migrateCapacitorToken()
            accessToken = token
            return token
        } catch {
            accessToken = nil
            return nil
        }
    }

    public func setAccessToken(_ token: String?) throws {
        accessToken = token
#if DEBUG
        if ProcessInfo.processInfo.environment["RATSLOTSE_DEBUG_ACCESS_TOKEN"] != nil {
            return
        }
#endif
        if let token, !token.isEmpty { try keychain.write(token) }
        else { try keychain.delete() }
    }

    public func hasAccessToken() -> Bool { accessToken != nil }

    /// Meldet ein abgelaufenes oder widerrufenes Token an EINER Stelle.
    ///
    /// Bis 10/2026 meldeten nur `bootstrap` und `refreshAccount` ab. Lief die
    /// Sitzung mitten im Gebrauch ab (Passwort auf einem anderen Gerät
    /// geändert, Konto gesperrt, Token widerrufen), zeigte jede weitere
    /// Ansicht nur noch ihren eigenen Fehler — angemeldet sah die App aus,
    /// nichts ging mehr.
    ///
    /// **Keine Schleife:** Gemeldet wird nur, wenn die abgelehnte Anfrage
    /// GENAU das aktuelle Token trug, und das Token fällt dabei sofort aus dem
    /// Speicher. Jede Anfrage danach — auch die Abmelde-Aufrufe des Handlers —
    /// geht ohne Token hinaus und kann nichts mehr auslösen. Ein 401 ohne
    /// Token (falsches Passwort bei der Anmeldung) meldet ebenfalls nichts.
    public func onUnauthorized(_ handler: (@Sendable () async -> Void)?) {
        unauthorizedHandler = handler
    }

    /// Nur für Tests: ein Token setzen, ohne den Schlüsselbund anzufassen.
    func setAccessTokenInMemory(_ token: String?) { accessToken = token }

    /// Absenden, prüfen, und ein 401 auf das eigene Token melden.
    private func perform(_ request: URLRequest) async throws -> Data {
        let (data, response) = try await session.data(for: request)
        do {
            try validate(response: response, data: data)
        } catch let error as APIError where error.isUnauthorized {
            reportUnauthorized(sent: request.value(forHTTPHeaderField: "Authorization"))
            throw error
        }
        return data
    }

    private func reportUnauthorized(sent: String?) {
        guard let sent, let token = accessToken, sent == "Bearer \(token)" else { return }
        accessToken = nil
        guard let handler = unauthorizedHandler else { return }
        Task { await handler() }
    }

    /// Die volle Adresse eines Pfads, den der Server relativ nennt — Medien
    /// wie `/neuigkeiten/2.2.0/teilen-ios.mp4`. Auf Prod ist das dieselbe
    /// Adresse wie die der Website, lokal die des Backends.
    nonisolated public func url(forPath path: String) -> URL {
        baseURL.appending(path: path.hasPrefix("/") ? String(path.dropFirst()) : path)
    }

    /// Ein Wert als EIN Pfadstück — vollständig kodiert, auch „/", „:" und „?".
    ///
    /// Für Kennungen, die selbst Adressen sind: Die Vorlagen der OParl-Städte
    /// heißen `https://…/papers/1`. Roh in den Pfad gesetzt, wurde aus dem
    /// `//` unterwegs ein `/`, und „Stimmt das?" an jeder Idee endete mit
    /// 404 „unbekannte Vorlage" (Review 3.0.0).
    public nonisolated static func pathSegment(_ value: String) -> String {
        value.addingPercentEncoding(withAllowedCharacters: segmentAllowed) ?? value
    }

    private static let segmentAllowed = CharacterSet(
        charactersIn: "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~")

    /// Basis plus Pfad. Der Pfad wird kodiert wie bisher (Leerzeichen, „?",
    /// Umlaute) — nur was schon kodiert ist (`%2F` aus `pathSegment`), bleibt
    /// stehen. `URL.appending(path:)` kodierte das „%" ein zweites Mal, ein
    /// vorab kodiertes Pfadstück kam so nie heil beim Server an.
    static func endpointURL(base: URL, path: String) -> URL? {
        let relativ = path.hasPrefix("/") ? String(path.dropFirst()) : path
        guard var components = URLComponents(url: base, resolvingAgainstBaseURL: false) else {
            return nil
        }
        var basis = components.percentEncodedPath
        if !basis.hasSuffix("/") { basis += "/" }
        components.percentEncodedPath = basis + encodePath(relativ)
        return components.url
    }

    private static func encodePath(_ path: String) -> String {
        var aus = ""
        var i = path.startIndex
        while i < path.endIndex {
            let zeichen = path[i]
            if zeichen == "%",
               let a = path.index(i, offsetBy: 1, limitedBy: path.endIndex), a < path.endIndex,
               let b = path.index(i, offsetBy: 2, limitedBy: path.endIndex), b < path.endIndex,
               path[a].isHexDigit, path[b].isHexDigit {
                aus += String(path[i...b])
                i = path.index(after: b)
                continue
            }
            aus += String(zeichen).addingPercentEncoding(withAllowedCharacters: .urlPathAllowed)
                ?? ""
            i = path.index(after: i)
        }
        return aus
    }

    public func get<Response: Decodable & Sendable>(
        _ path: String,
        query: [URLQueryItem] = [],
        as type: Response.Type = Response.self
    ) async throws -> Response {
        try await request(path, method: .get, query: query, body: Optional<String>.none, as: type)
    }

    public func send<Response: Decodable & Sendable, Body: Encodable & Sendable>(
        _ path: String,
        method: HTTPMethod = .post,
        query: [URLQueryItem] = [],
        body: Body,
        as type: Response.Type = Response.self
    ) async throws -> Response {
        try await request(path, method: method, query: query, body: body, as: type)
    }

    public func sendWithoutBody<Response: Decodable & Sendable>(
        _ path: String,
        method: HTTPMethod = .post,
        query: [URLQueryItem] = [],
        as type: Response.Type = Response.self
    ) async throws -> Response {
        try await request(path, method: method, query: query, body: Optional<String>.none, as: type)
    }

    public func sendVoid<Body: Encodable & Sendable>(
        _ path: String,
        method: HTTPMethod = .post,
        body: Body
    ) async throws {
        let request = try makeRequest(path, method: method, query: [], body: encoder.encode(body))
        _ = try await perform(request)
    }

    /// Ein Aufruf ohne Körper und ohne Antwort — mit Abfrageparametern.
    ///
    /// `query` gehört hierher und NICHT in den Pfad: Ein „?" im Pfad wird
    /// prozentkodiert, der Server sieht es als Teil des Namens und antwortet
    /// mit 404. Die Ansicht lädt dann ewig, ohne dass irgendwo ein Fehler
    /// steht — genau so ist die Ideen-Liste einmal ausgefallen.
    public func sendVoid(_ path: String, method: HTTPMethod = .post,
                         query: [URLQueryItem] = []) async throws {
        let request = try makeRequest(path, method: method, query: query)
        _ = try await perform(request)
    }

    public func makeStreamingRequest<Body: Encodable & Sendable>(
        _ path: String,
        method: HTTPMethod = .post,
        query: [URLQueryItem] = [],
        body: Body
    ) throws -> URLRequest {
        try makeRequest(path, method: method, query: query, body: encoder.encode(body), acceptsSSE: true)
    }

    public func makeStreamingRequest(
        _ path: String,
        method: HTTPMethod = .get,
        query: [URLQueryItem] = []
    ) throws -> URLRequest {
        try makeRequest(path, method: method, query: query, acceptsSSE: true)
    }

    private func request<Response: Decodable & Sendable, Body: Encodable & Sendable>(
        _ path: String,
        method: HTTPMethod,
        query: [URLQueryItem],
        body: Body?,
        as type: Response.Type
    ) async throws -> Response {
        let bodyData = try body.map(encoder.encode)
        let request = try makeRequest(path, method: method, query: query, body: bodyData)
        let data = try await perform(request)
        do {
            return try decoder.decode(type, from: data)
        } catch {
            throw APIError(statusCode: 0, message: "Die Antwort des Servers hat ein unerwartetes Format.", retryAfter: nil)
        }
    }

    private func makeRequest(
        _ path: String,
        method: HTTPMethod,
        query: [URLQueryItem] = [],
        body: Data? = nil,
        acceptsSSE: Bool = false
    ) throws -> URLRequest {
        guard let endpoint = Self.endpointURL(base: baseURL, path: path),
              var components = URLComponents(url: endpoint, resolvingAgainstBaseURL: false)
        else {
            throw APIError(statusCode: 0, message: "Die Serveradresse ist ungültig.", retryAfter: nil)
        }
        if !query.isEmpty { components.queryItems = query }
        guard let url = components.url else {
            throw APIError(statusCode: 0, message: "Die Anfrageadresse ist ungültig.", retryAfter: nil)
        }
        var request = URLRequest(url: url)
        request.httpMethod = method.rawValue
        request.httpBody = body
        request.timeoutInterval = acceptsSSE ? 300 : 30
        // Bis 09/2026 stand hier "app" — das sagte nur „nativ", nicht welche
        // Plattform. Das Backend nimmt beides an (app.clients), zählt aber nur
        // mit dem genaueren Wert getrennt: Sonst stünde die native App in der
        // Statistik im selben Topf wie die Capacitor-Hülle.
        request.setValue("ios", forHTTPHeaderField: "X-Client")
        request.setValue(acceptsSSE ? "text/event-stream" : "application/json", forHTTPHeaderField: "Accept")
        if body != nil { request.setValue("application/json", forHTTPHeaderField: "Content-Type") }
        if let accessToken { request.setValue("Bearer \(accessToken)", forHTTPHeaderField: "Authorization") }
        return request
    }

    private func validate(response: URLResponse, data: Data) throws {
        guard let http = response as? HTTPURLResponse else {
            throw APIError(statusCode: 0, message: "Der Server hat nicht geantwortet.", retryAfter: nil)
        }
        guard (200..<300).contains(http.statusCode) else {
            let retryAfter = http.value(forHTTPHeaderField: "Retry-After").flatMap(TimeInterval.init)
            throw APIError(
                statusCode: http.statusCode,
                message: Self.errorMessage(from: data, fallbackStatus: http.statusCode),
                retryAfter: retryAfter
            )
        }
    }

    private static func errorMessage(from data: Data, fallbackStatus: Int) -> String {
        guard
            let envelope = try? JSONDecoder().decode(ErrorEnvelope.self, from: data),
            let detail = envelope.detail
        else { return HTTPURLResponse.localizedString(forStatusCode: fallbackStatus) }
        switch detail {
        case .string(let message): return message
        case .array(let rows):
            let messages = rows.compactMap { row -> String? in
                guard case .object(let fields) = row else { return nil }
                return fields["msg"]?.string
            }
            return messages.isEmpty ? "Bitte prüfe deine Eingaben." : messages.joined(separator: "\n")
        default: return "Die Anfrage konnte nicht verarbeitet werden."
        }
    }
}

public extension Encodable where Self: Sendable {
    func asJSONData() throws -> Data { try JSONEncoder().encode(self) }
}
