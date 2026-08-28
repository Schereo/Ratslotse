import Foundation

public struct SSEEvent: Codable, Sendable, Equatable {
    public let type: String
    public let fields: [String: JSONValue]

    public init(from decoder: Decoder) throws {
        fields = try decoder.singleValueContainer().decode([String: JSONValue].self)
        type = fields["type"]?.string ?? "message"
    }

    public func encode(to encoder: Encoder) throws {
        try fields.encode(to: encoder)
    }

    public var text: String? { fields["text"]?.string }
    public var step: String? { fields["step"]?.string }
    public var conversationID: Int? { fields["gespraech_id"]?.int }
    public var suggestions: [String] {
        (fields["questions"] ?? fields["suggestions"])?.array?.compactMap(\.string) ?? []
    }
}

/// Incremental, spec-shaped parser. It deliberately ignores comments such as
/// `: ping`, joins repeated data lines, and dispatches only on a blank line.
public struct SSEParser: Sendable {
    private var dataLines: [String] = []

    public init() {}

    public mutating func consume(line: String) -> String? {
        if line.isEmpty {
            guard !dataLines.isEmpty else { return nil }
            defer { dataLines.removeAll(keepingCapacity: true) }
            return dataLines.joined(separator: "\n")
        }
        if line.hasPrefix(":") { return nil }
        guard line.hasPrefix("data:") else { return nil }
        var value = String(line.dropFirst(5))
        if value.first == " " { value.removeFirst() }
        dataLines.append(value)
        return nil
    }

    public mutating func finish() -> String? {
        consume(line: "")
    }
}

public struct SSEClient: Sendable {
    private let session: URLSession
    private let decoder = JSONDecoder()

    public init(session: URLSession = .shared) {
        self.session = session
    }

    public func events(for request: URLRequest) -> AsyncThrowingStream<SSEEvent, Error> {
        AsyncThrowingStream { continuation in
            let task = Task {
                do {
                    let (bytes, response) = try await session.bytes(for: request)
                    guard let http = response as? HTTPURLResponse else {
                        throw APIError(statusCode: 0, message: "Der Stream antwortet nicht.", retryAfter: nil)
                    }
                    guard (200..<300).contains(http.statusCode) else {
                        throw APIError(
                            statusCode: http.statusCode,
                            message: HTTPURLResponse.localizedString(forStatusCode: http.statusCode),
                            retryAfter: http.value(forHTTPHeaderField: "Retry-After").flatMap(TimeInterval.init)
                        )
                    }
                    var parser = SSEParser()
                    for try await line in bytes.lines {
                        try Task.checkCancellation()
                        if let payload = parser.consume(line: line) {
                            try yield(payload: payload, to: continuation)
                        }
                    }
                    if let payload = parser.finish() {
                        try yield(payload: payload, to: continuation)
                    }
                    continuation.finish()
                } catch is CancellationError {
                    continuation.finish()
                } catch {
                    continuation.finish(throwing: error)
                }
            }
            continuation.onTermination = { _ in task.cancel() }
        }
    }

    private func yield(
        payload: String,
        to continuation: AsyncThrowingStream<SSEEvent, Error>.Continuation
    ) throws {
        guard let data = payload.data(using: .utf8) else { return }
        continuation.yield(try decoder.decode(SSEEvent.self, from: data))
    }
}
