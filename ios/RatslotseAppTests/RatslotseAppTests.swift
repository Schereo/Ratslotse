import Foundation
import MapKit
import RatslotseAPI
import Testing
@testable import Ratslotse
@testable import RatslotseFeatures

@MainActor
@Test func appTargetCanBeConstructed() {
    let app = RatslotseApp()
    #expect(String(describing: type(of: app)) == "RatslotseApp")
}

@Test func bundledOldenburgMapIsValidGeoJSON() throws {
    let url = try #require(Bundle.main.url(forResource: "stadtteile-oldenburg", withExtension: "json"))
    let objects = try MKGeoJSONDecoder().decode(Data(contentsOf: url))
    let features = objects.compactMap { $0 as? MKGeoJSONFeature }
    #expect(features.count == 31)
    #expect(features.allSatisfy { !$0.geometry.isEmpty })
}

@MainActor
@Test func onboardingProgressSurvivesARelaunch() throws {
    let suiteName = "de.ratslotse.tests.onboarding.\(UUID().uuidString)"
    let defaults = try #require(UserDefaults(suiteName: suiteName))
    defer { defaults.removePersistentDomain(forName: suiteName) }

    let fresh = AppModel(defaults: defaults)
    #expect(fresh.onboardingStep == 0)
    fresh.beginOnboarding()
    #expect(fresh.onboardingStep == 1)
    #expect(fresh.authPresentation == .register)

    let resumed = AppModel(defaults: defaults)
    #expect(resumed.onboardingStep == 1)
    defaults.set(true, forKey: "ratslotse.onboarding.done")
    let completed = AppModel(defaults: defaults)
    #expect(completed.onboardingStep == nil)
}

@MainActor
@Test func incomingRouteLeavesAnAuxiliaryTabletPage() {
    let model = AppModel()
    model.tabletPage = .saved

    model.handle(route: .tab(.questions))

    #expect(model.tabletPage == nil)
    #expect(model.selectedTab == .questions)
}

@MainActor
@Test func conversationSavingPreferenceComesFromTheAccount() throws {
    let data = try #require(
        """
        {
          "id": 17,
          "email": "test@example.org",
          "role": "user",
          "status": "active",
          "delivery_channel": "email",
          "email_verified": true,
          "apple_linked": false,
          "has_password": true,
          "access_token": null,
          "display_name": "Test",
          "qa_speichern": 0
        }
        """.data(using: .utf8)
    )
    let user = try JSONDecoder().decode(User.self, from: data)
    let model = AppModel()
    model.session = .active(user)

    #expect(model.conversationSavingPreference == 0)
}

@MainActor
@Test func conversationSavingChoiceUsesTheAccountEndpoint() async throws {
    let configuration = URLSessionConfiguration.ephemeral
    configuration.protocolClasses = [ConversationSettingURLProtocol.self]
    let api = APIClient(
        baseURL: try #require(URL(string: "https://native-test.ratslotse.invalid")),
        session: URLSession(configuration: configuration)
    )
    let model = AppModel(api: api)
    ConversationSettingURLProtocol.lastRequest = nil
    ConversationSettingURLProtocol.lastRequestBody = nil

    try await model.setConversationSaving(true)

    #expect(model.conversationSavingPreference == 1)
    #expect(ConversationSettingURLProtocol.lastRequest?.url?.path == "/api/council/gespraeche/einstellung")
    #expect(ConversationSettingURLProtocol.lastRequest?.httpMethod == "POST")
    let body = try #require(ConversationSettingURLProtocol.lastRequestBody)
    #expect(try JSONDecoder().decode(ConversationSettingRequest.self, from: body).an)
}

private struct ConversationSettingRequest: Decodable {
    let an: Bool
}

private final class ConversationSettingURLProtocol: URLProtocol {
    static var lastRequest: URLRequest?
    static var lastRequestBody: Data?

    override class func canInit(with request: URLRequest) -> Bool { true }

    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }

    override func startLoading() {
        Self.lastRequest = request
        Self.lastRequestBody = request.httpBody ?? request.httpBodyStream.flatMap(readAll)
        let response = HTTPURLResponse(
            url: request.url!,
            statusCode: 200,
            httpVersion: nil,
            headerFields: ["Content-Type": "application/json"]
        )!
        client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
        client?.urlProtocol(self, didLoad: Data(#"{"einstellung":1}"#.utf8))
        client?.urlProtocolDidFinishLoading(self)
    }

    override func stopLoading() {}

    private func readAll(_ stream: InputStream) -> Data? {
        stream.open()
        defer { stream.close() }
        var data = Data()
        var buffer = [UInt8](repeating: 0, count: 1_024)
        while true {
            let count = stream.read(&buffer, maxLength: buffer.count)
            if count < 0 { return nil }
            if count == 0 { return data }
            data.append(contentsOf: buffer[..<count])
        }
    }
}

@MainActor
@Test func nativeFeedbackUsesTheFeedbackEndpoint() async throws {
    let configuration = URLSessionConfiguration.ephemeral
    configuration.protocolClasses = [FeedbackURLProtocol.self]
    let api = APIClient(
        baseURL: try #require(URL(string: "https://native-test.ratslotse.invalid")),
        session: URLSession(configuration: configuration)
    )
    FeedbackURLProtocol.lastRequest = nil
    FeedbackURLProtocol.lastRequestBody = nil

    try await api.sendVoid(
        "/api/feedback",
        body: NativeFeedbackPayload(kind: "bug", message: "Der Knopf reagiert nicht.")
    )

    #expect(FeedbackURLProtocol.lastRequest?.url?.path == "/api/feedback")
    #expect(FeedbackURLProtocol.lastRequest?.httpMethod == "POST")
    let body = try #require(FeedbackURLProtocol.lastRequestBody)
    let payload = try JSONDecoder().decode(NativeFeedbackPayload.self, from: body)
    #expect(payload == NativeFeedbackPayload(kind: "bug", message: "Der Knopf reagiert nicht."))
}

private final class FeedbackURLProtocol: URLProtocol {
    static var lastRequest: URLRequest?
    static var lastRequestBody: Data?

    override class func canInit(with request: URLRequest) -> Bool { true }

    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }

    override func startLoading() {
        Self.lastRequest = request
        Self.lastRequestBody = request.httpBody ?? request.httpBodyStream.flatMap(readAll)
        let response = HTTPURLResponse(
            url: request.url!,
            statusCode: 200,
            httpVersion: nil,
            headerFields: ["Content-Type": "application/json"]
        )!
        client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
        client?.urlProtocol(self, didLoad: Data(#"{"ok":true}"#.utf8))
        client?.urlProtocolDidFinishLoading(self)
    }

    override func stopLoading() {}

    private func readAll(_ stream: InputStream) -> Data? {
        stream.open()
        defer { stream.close() }
        var data = Data()
        var buffer = [UInt8](repeating: 0, count: 1_024)
        while true {
            let count = stream.read(&buffer, maxLength: buffer.count)
            if count < 0 { return nil }
            if count == 0 { return data }
            data.append(contentsOf: buffer[..<count])
        }
    }
}

@Test func productionPersonProfileDecodesStructuredAffiliation() throws {
    let data = try #require(
        """
        {
          "name": "Tim Ebbeke Harms",
          "party": "Grüne",
          "current_affiliation": {
            "label": "Grüne",
            "kind": "partei",
            "parties": ["Grüne"]
          },
          "art": "rat",
          "organisation": null,
          "n_sessions": 136,
          "active_from": "2021-11-22",
          "active_to": "2026-06-16",
          "committees": [{"committee": "Rat", "n": 39, "chair": true}],
          "recent": [{"ksinr": 4599, "committee": "Kulturausschuss", "session_date": "2026-06-16"}]
        }
        """.data(using: .utf8)
    )

    let profile = try JSONDecoder().decode(PublicPersonProfile.self, from: data)
    #expect(profile.currentAffiliation?.label == "Grüne")
    #expect(profile.currentAffiliation?.kind == "partei")
    #expect(profile.nSessions == 136)
    #expect(profile.committees.count == 1)
    #expect(profile.recent.count == 1)
}

@Test func personProfileStillDecodesLegacyStringAffiliation() throws {
    let data = try #require(
        """
        {
          "name": "Anne Beispiel",
          "party": null,
          "current_affiliation": "SPD-Fraktion",
          "art": "rat",
          "organisation": null,
          "n_sessions": 1,
          "active_from": null,
          "active_to": null,
          "committees": [],
          "recent": []
        }
        """.data(using: .utf8)
    )

    let profile = try JSONDecoder().decode(PublicPersonProfile.self, from: data)
    #expect(profile.currentAffiliation?.label == "SPD-Fraktion")
}

@Test func nativeQuizCatalogDecodesAllDesktopFilters() throws {
    let data = try #require(
        """
        {
          "wahlbereiche": [{
            "key": "3",
            "label": "Wahlbereich 3",
            "stadtteile": ["Eversten", "Bloherfelde"],
            "questions": 27,
            "points": 12
          }],
          "stadtteile": [{
            "key": "Eversten",
            "label": "Eversten",
            "questions": 14,
            "points": 5
          }],
          "themen": [{
            "key": "schulwege",
            "label": "Sichere Schulwege",
            "stadtteil": "Kreyenbrück",
            "questions": 9,
            "points": 2
          }],
          "categories": ["geschichte", "orte", "menschen", "ratspolitik", "schaetzen"]
        }
        """.data(using: .utf8)
    )

    let catalog = try JSONDecoder().decode(QuizAreas.self, from: data)

    #expect(catalog.wahlbereiche.first?.stadtteile == ["Eversten", "Bloherfelde"])
    #expect(catalog.stadtteile.first?.points == 5)
    #expect(catalog.themen.first?.stadtteil == "Kreyenbrück")
    #expect(catalog.categories.count == 5)
}

@Test func nativeOwnQuizCardsDecodeChoiceAndEstimateFields() throws {
    let data = try #require(
        """
        [{
          "id": 41,
          "question": "Wie viele Einwohner hat Oldenburg ungefähr?",
          "options": [],
          "correct_index": 0,
          "stadtteil": null,
          "category": "schaetzen",
          "explanation": "Die Zahl verändert sich laufend.",
          "qtype": "estimate",
          "answer_value": 176000,
          "unit": "Einwohner",
          "range_min": 0,
          "range_max": 350000,
          "practiced": 4,
          "correct_count": 3,
          "created_at": "2026-08-28T12:00:00Z"
        }]
        """.data(using: .utf8)
    )

    let cards = try JSONDecoder().decode([OwnQuizQuestion].self, from: data)
    let card = try #require(cards.first)

    #expect(card.qtype == "estimate")
    #expect(card.answerValue == 176_000)
    #expect(card.rangeMax == 350_000)
    #expect(card.category == "schaetzen")
}

@Test func nativeAgendaItemsDecodeTopAttachmentsAndLegacyPayloads() throws {
    let data = try #require(
        """
        [{
          "item_number": "Ö 7",
          "title": "Sichere Querung an der Cloppenburger Straße",
          "vorlage_nr": "26/0412",
          "is_public": 1,
          "summary": "Der Ausschuss berät zwei Varianten.",
          "anlagen": [
            {"label": "Lageplan Querungsstelle", "url": "https://buergerinfo.oldenburg.de/getfile.php?id=310001"},
            {"label": "Verkehrsgutachten", "url": "https://buergerinfo.oldenburg.de/getfile.php?id=310002"}
          ]
        }, {
          "item_number": "Ö 8",
          "title": "Mitteilungen",
          "vorlage_nr": null,
          "is_public": 1,
          "summary": null
        }]
        """.data(using: .utf8)
    )

    let items = try JSONDecoder().decode([AgendaItem].self, from: data)

    #expect(items.first?.attachments.count == 2)
    #expect(items.first?.attachments.first?.label == "Lageplan Querungsstelle")
    #expect(items.first?.attachments.first?.url.contains("id=310001") == true)
    #expect(items.last?.attachments.isEmpty == true)
}
