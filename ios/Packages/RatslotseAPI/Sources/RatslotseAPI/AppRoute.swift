import Foundation

public enum AppTab: String, Codable, Sendable, Hashable {
    case today
    case questions
    case council
    case topics
    case account
}

public enum AppRoute: Sendable, Hashable {
    case tab(AppTab)
    case verifyEmail(token: String)
    case resetPassword(token: String)
    case question(prefill: String?, share: String?)
    case sharedAnswer(token: String?)
    case decision(id: Int)
    case sessions(ksinr: Int?, tops: [String])
    case person(slug: String)
    case topic(slug: String)
    case place(id: String)
    case quiz(area: String?)
    case web(URL)
}

public struct AppRouter: Sendable {
    public let canonicalHost: String

    public init(canonicalHost: String = "ratslotse.de") {
        self.canonicalHost = canonicalHost
    }

    public func route(for url: URL) -> AppRoute? {
        guard url.host == nil || url.host?.lowercased() == canonicalHost else { return .web(url) }
        let path = normalized(path: url.path)
        let query = URLComponents(url: url, resolvingAgainstBaseURL: false)?.queryItems ?? []
        func value(_ name: String) -> String? {
            query.first(where: { $0.name == name })?.value?.trimmingCharacters(in: .whitespacesAndNewlines)
        }

        switch path {
        case "/", "/dashboard": return .tab(.today)
        case "/login", "/register": return .tab(.account)
        case "/verify-email":
            guard let token = value("token"), !token.isEmpty else { return .tab(.account) }
            return .verifyEmail(token: token)
        case "/reset-password":
            guard let token = value("token"), !token.isEmpty else { return .tab(.account) }
            return .resetPassword(token: token)
        case "/fragen":
            let prefill = value("q"), share = value("share")
            return prefill == nil && share == nil ? .tab(.questions) : .question(prefill: prefill, share: share)
        case "/g": return .sharedAnswer(token: value("t"))
        case "/topics": return .tab(.topics)
        case "/quiz": return .quiz(area: value("area"))
        case "/council/decision":
            guard let raw = value("id"), let id = Int(raw), id > 0 else { return .tab(.council) }
            return .decision(id: id)
        case "/council/person":
            guard let slug = value("slug"), !slug.isEmpty else { return .tab(.council) }
            return .person(slug: slug)
        case "/council/thema":
            guard let slug = value("slug"), !slug.isEmpty else { return .tab(.council) }
            return .topic(slug: slug)
        case "/council/ort":
            guard let id = value("id"), !id.isEmpty else { return .tab(.council) }
            return .place(id: id)
        case "/council":
            if value("mode") == "fragen" {
                return .question(prefill: value("q"), share: value("share"))
            }
            if value("tab") == "sessions" {
                let ksinr = value("ksinr").flatMap(Int.init)
                let tops = value("top")?.split(separator: ",").map(String.init) ?? []
                return .sessions(ksinr: ksinr, tops: tops)
            }
            return .tab(.council)
        default: return .web(url)
        }
    }

    public func route(forPath path: String) -> AppRoute? {
        guard let url = URL(string: path, relativeTo: URL(string: "https://\(canonicalHost)"))?.absoluteURL else {
            return nil
        }
        return route(for: url)
    }

    public func universalLink(for route: AppRoute) -> URL? {
        var components = URLComponents()
        components.scheme = "https"
        components.host = canonicalHost
        switch route {
        case .tab(.today): components.path = "/dashboard"
        case .tab(.questions): components.path = "/fragen"
        case .tab(.council): components.path = "/council"
        case .tab(.topics): components.path = "/topics"
        case .tab(.account): return nil
        case .verifyEmail(let token):
            components.path = "/verify-email"; components.queryItems = [.init(name: "token", value: token)]
        case .resetPassword(let token):
            components.path = "/reset-password"; components.queryItems = [.init(name: "token", value: token)]
        case let .question(prefill, share):
            components.path = "/fragen"
            components.queryItems = [URLQueryItem(name: "q", value: prefill), .init(name: "share", value: share)]
                .filter { $0.value != nil }
        case .sharedAnswer(let token):
            components.path = "/g"; components.queryItems = [.init(name: "t", value: token)]
        case .decision(let id):
            components.path = "/council/decision"; components.queryItems = [.init(name: "id", value: String(id))]
        case let .sessions(ksinr, tops):
            components.path = "/council"
            components.queryItems = [.init(name: "tab", value: "sessions")]
            if let ksinr { components.queryItems?.append(.init(name: "ksinr", value: String(ksinr))) }
            if !tops.isEmpty { components.queryItems?.append(.init(name: "top", value: tops.joined(separator: ","))) }
        case .person(let slug):
            components.path = "/council/person"; components.queryItems = [.init(name: "slug", value: slug)]
        case .topic(let slug):
            components.path = "/council/thema"; components.queryItems = [.init(name: "slug", value: slug)]
        case .place(let id):
            components.path = "/council/ort"; components.queryItems = [.init(name: "id", value: id)]
        case .quiz(let area):
            components.path = "/quiz"; components.queryItems = [.init(name: "area", value: area)]
        case .web(let url): return url
        }
        return components.url
    }

    private func normalized(path: String) -> String {
        guard path.count > 1, path.hasSuffix("/") else { return path.isEmpty ? "/" : path }
        return String(path.dropLast())
    }
}
