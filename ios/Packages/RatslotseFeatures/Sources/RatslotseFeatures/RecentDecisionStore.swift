import Foundation
import RatslotseAPI

@MainActor
enum RecentDecisionStore {
    private static let key = "ratslotse.recent-decisions"
    private static let maximumCount = 8

    static func load(defaults: UserDefaults = .standard) -> [DecisionSummary] {
        guard let data = defaults.data(forKey: key) else { return [] }
        return (try? JSONDecoder().decode([DecisionSummary].self, from: data)) ?? []
    }

    static func track(_ decision: DecisionSummary, defaults: UserDefaults = .standard) {
        var decisions = load(defaults: defaults).filter { $0.id != decision.id }
        decisions.insert(decision, at: 0)
        if decisions.count > maximumCount {
            decisions.removeLast(decisions.count - maximumCount)
        }
        if let data = try? JSONEncoder().encode(decisions) {
            defaults.set(data, forKey: key)
        }
    }
}
