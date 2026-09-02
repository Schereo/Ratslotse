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
    public var conversationID: Int? { fields["conversation_id"]?.int }
    /// Der Server sendet die Anschlussfragen als `questions` — und hat sie nie
    /// anders genannt (nachgesehen 02.09.2026). Der Rückfall auf `suggestions`
    /// stand hier trotzdem, und die aufgezeichnete Probe benutzte ihn: Sie
    /// prüfte damit gegen eine Nutzlast, die es nirgends gibt.
    public var suggestions: [String] {
        fields["questions"]?.array?.compactMap(\.string) ?? []
    }
}

/// Incremental, spec-shaped parser. It deliberately ignores comments such as
/// `: ping`, joins repeated data lines, and dispatches only on a blank line.
public struct SSEParser: Sendable {
    private var dataLines: [String] = []
    private var lineBytes: [UInt8] = []
    private var previousByteWasCarriageReturn = false

    public init() {}

    public mutating func consume(line: String) -> String? {
        var line = line
        // Proxys dürfen SSE mit CRLF statt nur LF ausliefern. Behandeln wir
        // das verbleibende CR nicht als Zeileninhalt, kleben sonst mehrere
        // JSON-Frames aneinander und der Decoder verwirft den ganzen Stream.
        if line.last == "\r" { line.removeLast() }
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

    /// Verarbeitet den Stream byteweise, damit leere SSE-Trennzeilen nicht
    /// von `AsyncBytes.lines` verschluckt werden können. Unterstützt LF,
    /// CRLF und reine CR-Zeilenenden.
    public mutating func consume(byte: UInt8) -> String? {
        if byte == 0x0A { // LF
            if previousByteWasCarriageReturn {
                previousByteWasCarriageReturn = false
                return nil
            }
            return consumeBufferedLine()
        }
        if byte == 0x0D { // CR
            previousByteWasCarriageReturn = true
            return consumeBufferedLine()
        }

        previousByteWasCarriageReturn = false
        lineBytes.append(byte)
        return nil
    }

    public mutating func finish() -> String? {
        if !lineBytes.isEmpty {
            _ = consumeBufferedLine()
        }
        return consume(line: "")
    }

    private mutating func consumeBufferedLine() -> String? {
        defer { lineBytes.removeAll(keepingCapacity: true) }
        return consume(line: String(decoding: lineBytes, as: UTF8.self))
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
                        var body = Data()
                        for try await byte in bytes {
                            body.append(byte)
                            if body.count >= 64 * 1024 { break }
                        }
                        throw APIError(
                            statusCode: http.statusCode,
                            message: Self.errorMessage(from: body, statusCode: http.statusCode),
                            retryAfter: http.value(forHTTPHeaderField: "Retry-After").flatMap(TimeInterval.init)
                        )
                    }
                    var parser = SSEParser()
                    for try await byte in bytes {
                        try Task.checkCancellation()
                        if let payload = parser.consume(byte: byte) {
                            yield(payload: payload, to: continuation)
                        }
                    }
                    if let payload = parser.finish() {
                        yield(payload: payload, to: continuation)
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
    ) {
        // Ein beschädigtes Zusatz-Frame darf eine bereits laufende Antwort
        // nicht beenden. Der Web-Client behandelt den Stream genauso: Nicht
        // parsebare Frames werden verworfen, spätere Token/Done-Events aber
        // weiterhin gelesen. Netzwerk- und HTTP-Fehler bleiben echte Fehler.
        guard let event = decode(payload: payload) else { return }
        continuation.yield(event)
    }

    func decode(payload: String) -> SSEEvent? {
        guard let data = payload.data(using: .utf8) else { return nil }
        return try? decoder.decode(SSEEvent.self, from: data)
    }

    private static func errorMessage(from data: Data, statusCode: Int) -> String {
        guard let root = try? JSONDecoder().decode(JSONValue.self, from: data),
              let detail = root.object?["detail"]
        else { return HTTPURLResponse.localizedString(forStatusCode: statusCode) }
        switch detail {
        case .string(let message): return message
        case .array(let rows):
            let messages = rows.compactMap { $0.object?["msg"]?.string }
            return messages.isEmpty ? "Bitte prüfe deine Eingaben." : messages.joined(separator: "\n")
        default: return "Die Anfrage konnte nicht verarbeitet werden."
        }
    }
}
