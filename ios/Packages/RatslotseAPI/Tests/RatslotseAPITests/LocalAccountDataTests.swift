import Foundation
import Testing
@testable import RatslotseAPI

@Test func logoutForgetsWhatBelongsToTheAccount() throws {
    let name = "de.ratslotse.test.local-account-\(UUID().uuidString)"
    let defaults = try #require(UserDefaults(suiteName: name))
    defer { defaults.removePersistentDomain(forName: name) }

    for key in LocalAccountData.keys { defaults.set("x", forKey: key) }
    defaults.set(42, forKey: LocalAccountData.activeConversationPrefix + "7")
    defaults.set(43, forKey: LocalAccountData.activeConversationPrefix + "8")
    // Was zum Gerät gehört, bleibt.
    defaults.set("dark", forKey: "ratslotse.appearance")

    LocalAccountData.clear(defaults)

    for key in LocalAccountData.keys { #expect(defaults.object(forKey: key) == nil, "\(key) blieb stehen") }
    #expect(defaults.object(forKey: LocalAccountData.activeConversationPrefix + "7") == nil)
    #expect(defaults.object(forKey: LocalAccountData.activeConversationPrefix + "8") == nil)
    #expect(defaults.string(forKey: "ratslotse.appearance") == "dark")
}
