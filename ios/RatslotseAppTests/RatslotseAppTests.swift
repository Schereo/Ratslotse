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
@Test func appearanceSelectionSurvivesARelaunch() throws {
    let suiteName = "de.ratslotse.tests.appearance.\(UUID().uuidString)"
    let defaults = try #require(UserDefaults(suiteName: suiteName))
    defer { defaults.removePersistentDomain(forName: suiteName) }

    let model = AppModel(defaults: defaults)
    #expect(model.appearance == .system)
    model.setAppearance(.dark)

    let relaunched = AppModel(defaults: defaults)
    #expect(relaunched.appearance == .dark)
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

@MainActor
@Test func activeConversationIsScopedToTheSignedInAccount() async throws {
    let suiteName = "de.ratslotse.tests.conversation.\(UUID().uuidString)"
    let defaults = try #require(UserDefaults(suiteName: suiteName))
    defer { defaults.removePersistentDomain(forName: suiteName) }
    let userData = try #require(
        #"{"id":17,"email":"chat@example.org","role":"user","status":"pending","delivery_channel":"email","email_verified":false,"apple_linked":false,"has_password":true,"access_token":null,"display_name":"Chat Test","qa_speichern":1}"#.data(using: .utf8)
    )
    let user = try JSONDecoder().decode(User.self, from: userData)

    let first = AppModel(defaults: defaults)
    first.session = .pending(user)
    first.setActiveConversationID(812)

    let relaunched = AppModel(defaults: defaults)
    try await relaunched.adopt(user: user)
    #expect(relaunched.activeConversationID == 812)

    let disabledData = try #require(
        #"{"id":17,"email":"chat@example.org","role":"user","status":"pending","delivery_channel":"email","email_verified":false,"apple_linked":false,"has_password":true,"access_token":null,"display_name":"Chat Test","qa_speichern":0}"#.data(using: .utf8)
    )
    let disabledUser = try JSONDecoder().decode(User.self, from: disabledData)
    try await relaunched.adopt(user: disabledUser)
    #expect(relaunched.activeConversationID == nil)

    let cleared = AppModel(defaults: defaults)
    try await cleared.adopt(user: user)
    #expect(cleared.activeConversationID == nil)
}

@Test func citedSourcesExcludeUnrelatedSearchHitsAndMapPinsAreDeduplicated() throws {
    let data = Data(
        #"[{"id":20947,"title":"Stadionneubau","committee":"Rat","session_date":"2026-06-01","lat":53.143,"lon":8.214},{"id":42,"title":"Fahrradstraße Haareneschstraße","committee":"Verkehrsausschuss","session_date":"2026-08-20","lat":53.143,"lon":8.214},{"id":43,"title":"Radverkehrsprogramm","committee":"Verkehrsausschuss","session_date":"2026-07-01","lat":53.143,"lon":8.214}]"#.utf8
    )
    let sources = try JSONDecoder().decode([DecisionSummary].self, from: data)
    let index = QuestionCitationIndex(
        text: "Die Fahrradstraße wurde beschlossen [42, 43].",
        sources: sources
    )

    #expect(index.numberByID == [42: 1, 43: 2])
    #expect(index.citedSources.map(\.id) == [42, 43])
    #expect(index.uncitedSources.map(\.id) == [20947])
    #expect(questionMapPins(for: index.citedSources).count == 1)

    let markdown = questionCitationMarkdown(
        text: "Die **Fahrradstraße** ist beschlossen [42].Für diesen Abschnitt gilt Tempo 30 [999].",
        sources: sources
    )
    #expect(markdown.contains("**Fahrradstraße**"))
    #expect(markdown.contains("[①](ratslotse://decision/42). Für"))
    #expect(questionCitationLabel(10) == "⑩")
    #expect(questionCitationLabel(18) == "⑱")
    #expect(questionCitationLabel(21) == "[21]")
    #expect(!markdown.contains("20947"))
    #expect(!markdown.contains("999"))
}

@Test func decisionSummaryUsesTheSharedBackendImportanceScore() throws {
    let data = Data(#"{"id":17,"title":"Haushaltsplan 2026","importance":82}"#.utf8)
    let decision = try JSONDecoder().decode(DecisionSummary.self, from: data)
    #expect(decision.importance == 82)

    let encoded = try JSONEncoder().encode(decision)
    let roundTrip = try JSONDecoder().decode(DecisionSummary.self, from: encoded)
    #expect(roundTrip.importance == 82)
}

@MainActor
@Test func recentlyViewedDecisionsKeepOrderAndDeduplicate() throws {
    let suiteName = "de.ratslotse.tests.recent.\(UUID().uuidString)"
    let defaults = try #require(UserDefaults(suiteName: suiteName))
    defer { defaults.removePersistentDomain(forName: suiteName) }
    let first = try JSONDecoder().decode(
        DecisionSummary.self,
        from: Data(#"{"id":17,"title":"Sichere Schulwege"}"#.utf8)
    )
    let second = try JSONDecoder().decode(
        DecisionSummary.self,
        from: Data(#"{"id":18,"title":"Neue Busspuren"}"#.utf8)
    )

    RecentDecisionStore.track(first, defaults: defaults)
    RecentDecisionStore.track(second, defaults: defaults)
    RecentDecisionStore.track(first, defaults: defaults)

    let loaded = RecentDecisionStore.load(defaults: defaults)
    #expect(loaded.map(\.id) == [17, 18])
}

@Test func decisionDetailKeepsTheWebParityFields() throws {
    let data = Data(#"""
    {
      "decision": {
        "id": 17,
        "title": "Haushaltsplan 2026",
        "simple_summary": "Lotti erklärt den Beschluss.",
        "beschluss": "Der amtliche Wortlaut.",
        "parties": ["SPD"],
        "policy_tags": ["Haushalt"],
        "raw_result": "mehrheitlich",
        "protocol_url": "https://example.test/protokoll.pdf"
      },
      "attendance": [{"name":"Erika Beispiel","party":"SPD","role":"mitglied"}],
      "entities": [{"slug":"haushalt-2026","name":"Haushalt 2026"}],
      "present_parties": [],
      "similar": [],
      "plan_bild": 44
    }
    """#.utf8)
    let detail = try JSONDecoder().decode(DecisionDetail.self, from: data)

    #expect(detail.decision.simpleSummary == "Lotti erklärt den Beschluss.")
    #expect(detail.decision.officialText == "Der amtliche Wortlaut.")
    #expect(detail.decision.parties == ["SPD"])
    #expect(detail.decision.policyTags == ["Haushalt"])
    #expect(detail.attendance.first?.party == "SPD")
    #expect(detail.entities.first?.slug == "haushalt-2026")
    #expect(detail.planImageID == 44)
}

@Test func personAffiliationChipsFollowDesktopDisambiguationRules() {
    let ulf = QuestionPerson(
        slug: "ulf-prange",
        name: "Ulf Prange",
        vorname: "ulf",
        nachname: "prange",
        art: "rat",
        partei: "SPD",
        aktiv: true
    )
    let oldUlf = QuestionPerson(
        slug: "ulf-prange-alt",
        name: "Ulf Prange",
        vorname: "ulf",
        nachname: "prange-alt",
        art: "rat",
        partei: "SPD",
        aktiv: false
    )
    let anna = QuestionPerson(
        slug: "anna-oltmanns",
        name: "Anna Oltmanns",
        vorname: "anna",
        nachname: "oltmanns",
        art: "rat",
        partei: "Bündnis 90/Die Grünen",
        aktiv: true
    )
    let bernd = QuestionPerson(
        slug: "bernd-oltmanns",
        name: "Bernd Oltmanns",
        vorname: "bernd",
        nachname: "oltmanns",
        art: "blocker",
        partei: nil,
        aktiv: false
    )

    let marked = questionPersonBadgeMarkdown(
        text: "Ulf Prange (SPD) sagte es. Prange ergänzte später.",
        people: [ulf, oldUlf]
    )
    #expect(marked.contains("Prange [● SPD](ratslotse://person/ulf-prange) sagte"))
    #expect(marked.components(separatedBy: "ratslotse://person/ulf-prange").count == 2)
    #expect(!marked.contains("(SPD)"))

    let ambiguous = questionPersonBadgeMarkdown(text: "Oltmanns äußerte sich.", people: [anna, bernd])
    #expect(ambiguous == "Oltmanns äußerte sich.")

    let identified = questionPersonBadgeMarkdown(text: "Anna Oltmanns äußerte sich.", people: [anna, bernd])
    #expect(identified.contains("Oltmanns [● Grüne](ratslotse://person/anna-oltmanns)"))
    #expect(questionPersonBadgeLabel(oldUlf) == "ehem.")
}

@Test func extraEvidenceFollowsBackendSelectedChannels() {
    let generic = QuestionEvidenceAvailability(fields: ["qtype": .string("thema")])
    #expect(!generic.showsPartyOpinions)
    #expect(!generic.showsDebates)
    #expect(!generic.showsPress)
    #expect(!generic.showsAttachments)
    #expect(!generic.showsPlanning)
    #expect(!generic.showsBriefs)
    #expect(!generic.showsChart)
    #expect(!generic.showsSessions)

    let party = QuestionEvidenceAvailability(fields: [
        "qtype": .string("partei"),
        "debatten": .array([.object(["sprecher": .string("Muster")])]),
    ])
    #expect(party.showsPartyOpinions)
    #expect(party.showsDebates)
    #expect(!party.showsPress)

    let documents = QuestionEvidenceAvailability(fields: [
        "anlagen": .array([.object(["nr": .number(1)])]),
    ])
    #expect(documents.showsAttachments)

    let status = QuestionEvidenceAvailability(fields: [
        "planungen": .array([.object(["datum": .string("2026-09-01")])]),
    ])
    #expect(status.showsPlanning)

    let budget = QuestionEvidenceAvailability(fields: ["grafik": .object([:])])
    #expect(budget.showsChart)

    let current = QuestionEvidenceAvailability(fields: [
        "presse": .array([.object(["titel": .string("Mitteilung")])]),
    ])
    #expect(current.showsPress)

    let session = QuestionEvidenceAvailability(fields: [
        "sitzungen": .array([.object(["committee": .string("Rat")])]),
    ])
    #expect(session.showsSessions)
}

@Test func conversationDatesUseTodayAndYesterday() throws {
    var calendar = Calendar(identifier: .gregorian)
    calendar.timeZone = try #require(TimeZone(identifier: "Europe/Berlin"))
    let parser = ISO8601DateFormatter()
    let now = try #require(parser.date(from: "2026-08-28T12:00:00Z"))

    #expect(conversationDateLabel("2026-08-28T08:30:00", now: now, calendar: calendar) == "Heute")
    #expect(conversationDateLabel("2026-08-27T21:30:00", now: now, calendar: calendar) == "Gestern")
    #expect(conversationDateLabel("2026-08-26T12:00:00", now: now, calendar: calendar) == "26. Aug. 2026")
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
          "faction_timeline": [{
            "label": "Grüne", "kind": "partei", "parties": ["Grüne"],
            "first": "2021-11-22", "last": "2026-06-16", "n": 136
          }],
          "ris": {
            "kpenr": 17, "name": "Tim Ebbeke Harms", "fraktion_aktuell": "Grüne",
            "memberships": [{"kgrnr": 2, "gremium": "Rat", "rolle": "Mitglied", "von": "2021-11-01", "bis": null}]
          },
          "committees": [{"committee": "Rat", "n": 39, "chair": true}],
          "recent": [{"ksinr": 4599, "committee": "Kulturausschuss", "session_date": "2026-06-16"}],
          "wortbeitraege": [{"art": "rede", "top": "TOP 5", "text": "Beitrag", "committee": "Rat", "session_date": "2026-06-16"}],
          "wortbeitraege_gesamt": 18,
          "wortbeitraege_gremien": [{"committee": "Rat", "n": 18}]
        }
        """.data(using: .utf8)
    )

    let profile = try JSONDecoder().decode(PublicPersonProfile.self, from: data)
    #expect(profile.currentAffiliation?.label == "Grüne")
    #expect(profile.currentAffiliation?.kind == "partei")
    #expect(profile.nSessions == 136)
    #expect(profile.committees.count == 1)
    #expect(profile.recent.count == 1)
    #expect(profile.factionTimeline.first?.n == 136)
    #expect(profile.ris?.memberships.first?.committee == "Rat")
    #expect(profile.speeches.first?.agendaItem == "TOP 5")
    #expect(profile.speechCount == 18)
}

@Test func administrationPersonProfileDecodesWithoutCouncilMetrics() throws {
    let data = try #require(
        """
        {
          "typ": "verwaltung",
          "name": "Jürgen Krogmann",
          "slug": "juergen-krogmann",
          "rolle": "Oberbürgermeister",
          "aktiv": true,
          "von": "2014",
          "bis": "2026",
          "wortbeitraege": [],
          "wortbeitraege_gesamt": 0,
          "wortbeitraege_gremien": []
        }
        """.data(using: .utf8)
    )

    let profile = try JSONDecoder().decode(PublicPersonProfile.self, from: data)
    #expect(profile.type == "verwaltung")
    #expect(profile.roleLabel == "Oberbürgermeister")
    #expect(profile.nSessions == 0)
    #expect(profile.committees.isEmpty)
}

@Test func councilSessionKeepsAgendaCountForNativeCards() throws {
    let data = try #require(
        """
        {
          "ksinr": 8101,
          "committee": "Ausschuss für Allgemeine Angelegenheiten",
          "session_date": "2026-08-31",
          "session_time": "16:00",
          "location": "Kulturzentrum PFL",
          "title": "Ausschuss für Allgemeine Angelegenheiten",
          "n_items": 9,
          "my_topic_items": []
        }
        """.data(using: .utf8)
    )

    let session = try JSONDecoder().decode(CouncilSession.self, from: data)
    #expect(session.itemCount == 9)
    #expect(session.sessionTime == "16:00")
    #expect(session.location == "Kulturzentrum PFL")
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
