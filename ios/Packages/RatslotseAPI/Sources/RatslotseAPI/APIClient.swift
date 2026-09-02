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
        let (data, response) = try await session.data(for: request)
        try validate(response: response, data: data)
    }

    public func sendVoid(_ path: String, method: HTTPMethod = .post) async throws {
        let request = try makeRequest(path, method: method)
        let (data, response) = try await session.data(for: request)
        try validate(response: response, data: data)
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
        let (data, response) = try await session.data(for: request)
        try validate(response: response, data: data)
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
        guard var components = URLComponents(
            url: baseURL.appending(path: path.hasPrefix("/") ? String(path.dropFirst()) : path),
            resolvingAgainstBaseURL: false
        ) else {
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
