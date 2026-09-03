import Foundation
import Testing
@testable import RatslotseAPI

@Test func richDecisionDetailDecodesWithoutDiscardingNativeSections() throws {
    let json = #"""
    {
      "decision": {
        "id": 42, "ksinr": 88, "kind": "decision", "item_number": "Ö 2",
        "title": "Radweg bauen", "summary": "Der Radweg wird gebaut.",
        "committee": "Verkehrsausschuss", "session_date": "2026-02-01",
        "outcome": "accepted", "vote": "majority", "no_votes": 2,
        "abstentions": 1, "factions": ["SPD"], "template_number": "26/0400"
      },
      "present_parties": ["CDU", "SPD"],
      "ratsinfo_url": "https://buergerinfo.oldenburg.de/si0057.php?__ksinr=88",
      "sub_votes": [{
        "id": 43, "title": "Änderungsantrag", "committee": "Verkehrsausschuss",
        "session_date": "2026-02-01", "outcome": "rejected", "factions": ["CDU"]
      }],
      "template_journey": [{
        "ksinr": 87, "committee": "Ausschuss", "session_date": "2026-01-20", "item_number": "Ö 3"
      }],
      "deliberation_path": [{
        "date": "2026-02-01", "committee": "Rat", "top": "Ö 2", "result": "angenommen",
        "ksinr": 88, "future": false
      }],
      "template_url": "https://buergerinfo.oldenburg.de/vo0050.php?__kvonr=901",
      "template": {
        "template_number": "26/0400", "title": "Radweg", "kind": "Beschlussvorlage",
        "document_url": "https://example.test/vorlage.pdf", "n_pages": 3,
        "excerpt": "Sachverhalt: Die Stadt plant einen Radweg.", "office": "Amt für Verkehr"
      },
      "attachments": [{
        "document_id": 77, "label": "Antrag der SPD", "url": "https://example.test/77.pdf",
        "is_motion": 1, "applicants": ["SPD"], "status": "ok"
      }],
      "participation": {
        "title": "Beteiligung zum Plan", "schritt": "Entwurf", "valid_from": "2026-01-01",
        "valid_until": "2026-02-15", "url": "https://example.test/beteiligung", "status": "laufend"
      },
      "importance_breakdown": {"score": 81, "impact_reason": "Betrifft viele Menschen."},
      "follow": {"kvonr": 901, "following": true},
      "similar": []
    }
    """#

    let detail = try JSONDecoder().decode(DecisionDetail.self, from: Data(json.utf8))
    #expect(detail.decision.sessionID == 88)
    #expect(detail.decision.noVotes == 2)
    #expect(detail.subVotes.first?.factions == ["CDU"])
    #expect(detail.consultations.first?.result == "angenommen")
    #expect(detail.template?.department == "Amt für Verkehr")
    // Beide Felder haben beim Umbau ihren Namen auf der Leitung geändert
    // (`art`→`kind`, `von`/`bis`→`valid_from`/`valid_until`). Ohne diese
    // zwei Zeilen dekodierte die App still `nil` und zeigte nichts an.
    #expect(detail.template?.kind == "Beschlussvorlage")
    #expect(detail.participation?.from == "2026-01-01")
    #expect(detail.attachments.first?.applicants == ["SPD"])
    #expect(detail.participation?.until == "2026-02-15")
    #expect(detail.importance?.score == 81)
    #expect(detail.follow == FollowStatus(templateID: 901, following: true))
}

@Test func sparsePublicDecisionDetailUsesSafeEmptyDefaults() throws {
    let json = #"""
    {
      "decision": {"id": 1, "title": null},
      "present_parties": [], "ratsinfo_url": null, "similar": []
    }
    """#
    let detail = try JSONDecoder().decode(DecisionDetail.self, from: Data(json.utf8))
    #expect(detail.decision.title == "Beschluss")
    #expect(detail.subVotes.isEmpty)
    #expect(detail.templateJourney.isEmpty)
    #expect(detail.attachments.isEmpty)
    #expect(detail.follow == nil)
}

@Test func badgeSnapshotDecodesCollectionProgressAndCelebrations() throws {
    let json = #"""
    {
      "badges": [
        {"id":"erste-frage","title":"Erste Frage","hint":"Stell eine Frage.","earned":true,"progress":null},
        {"id":"quiz-serie","title":"Quiz-Serie ×5","hint":"Spiele an fünf Tagen.","earned":false,"progress":{"current":3,"target":5}}
      ],
      "earned_count": 1,
      "total": 2,
      "next": {"id":"quiz-serie","title":"Quiz-Serie ×5","hint":"Spiele an fünf Tagen."},
      "newly_earned": [{"id":"erste-frage","title":"Erste Frage"}]
    }
    """#

    let snapshot = try JSONDecoder().decode(BadgeSnapshot.self, from: Data(json.utf8))
    #expect(snapshot.earnedCount == 1)
    #expect(snapshot.badges.last?.progress == BadgeProgress(current: 3, target: 5))
    #expect(snapshot.next?.id == "quiz-serie")
    #expect(snapshot.newlyEarned == [EarnedBadge(id: "erste-frage", title: "Erste Frage")])
}

@Test func savedCouncilResponsesDecodeCurrentServerShape() throws {
    let bookmarksJSON = #"""
    {"bookmarks":[{
      "id":5,"kind":"decision","title":"Radweg","subtitle":"Rat · 2026-02-01",
      "state":"decided","url":"/council/decision?id=42","ksinr":88,"item_number":"Ö 2",
      "notify_result":false,"decision":{"id":42,"title":"Radweg","outcome":"accepted"},
      "session":null
    }]}
    """#
    let followsJSON = #"""
    {"follows":[{
      "id":7,"kvonr":901,"template_number":"26/0400","title":"Radweg","url":"https://example.test/vorlage",
      "n_stationen":2,"naechste":{"date":"2026-10-01","committee":"Rat","result":null},
      "letzte":{"date":"2026-02-01","committee":"Ausschuss","result":"angenommen"}
    }]}
    """#
    let bookmarks = try JSONDecoder().decode(BookmarkPage.self, from: Data(bookmarksJSON.utf8))
    let follows = try JSONDecoder().decode(FollowPage.self, from: Data(followsJSON.utf8))
    #expect(bookmarks.bookmarks.first?.decision?.id == 42)
    #expect(follows.follows.first?.next?.committee == "Rat")
}

@Test func enrichedListModelsDecodeVisualMetadataAndSafeDefaults() throws {
    let decisionJSON = #"""
    {
      "id": 42,
      "title": "Neue Busspuren",
      "simple_summary": "Zwei Busspuren verbessern den Nahverkehr.",
      "session_date": "2026-08-26",
      "amount_eur": 8900000,
      "interest": 82,
      "interest_reason": "Viele Menschen sind täglich betroffen.",
      "impact": 76,
      "impact_reason": "Fahrzeiten werden verlässlicher."
    }
    """#
    let topicJSON = #"""
    {
      "id": 7,
      "name": "Verkehrswende",
      "description": "Bus und Radverkehr",
      "matched": true,
      "decision_count": 12,
      "recent_hits": [{
        "id": 42,
        "title": "Neue Busspuren",
        "committee": "Rat der Stadt",
        "session_date": "2026-08-26",
        "outcome": "accepted",
        "is_new": true
      }],
      "hits_6m": 3
    }
    """#

    let decision = try JSONDecoder().decode(DecisionSummary.self, from: Data(decisionJSON.utf8))
    let topic = try JSONDecoder().decode(Topic.self, from: Data(topicJSON.utf8))

    #expect(decision.summary == "Zwei Busspuren verbessern den Nahverkehr.")
    #expect(decision.amountEUR == 8_900_000)
    #expect(decision.interest == 82)
    #expect(decision.impactReason == "Fahrzeiten werden verlässlicher.")
    #expect(decision.factions.isEmpty)
    #expect(topic.recentHits.first?.id == 42)
    #expect(topic.recentHits.first?.isNew == true)
    #expect(topic.hits6Months == 3)
    #expect(topic.unreadCount == 0)
}

@Test func partyFilterOptionsDecodeCanonicalLabelsAndCounts() throws {
    let json = #"""
    {"parties":[
      {"key":"Grüne","label":"Grüne","count":31},
      {"key":"SPD","label":"SPD","count":24}
    ]}
    """#

    let options = try JSONDecoder().decode(PartyOptions.self, from: Data(json.utf8))
    #expect(options.parties.map(\.key) == ["Grüne", "SPD"])
    #expect(options.parties.first?.count == 31)
}

@Test func weekPreviewDecodesTheFullEditorialHierarchy() throws {
    let json = #"""
    {
      "found": true,
      "from_date": "2026-08-28",
      "to_date": "2026-09-04",
      "sessions": [{
        "ksinr": 88,
        "committee": "Ausschuss für Stadtplanung und Bauen",
        "session_date": "2026-08-31",
        "session_time": "17:00:00",
        "location": "Altes Rathaus",
        "n_items": 14
      }],
      "items": [{
        "ksinr": 88,
        "item_number": "Ö 6",
        "title": "Bebauungsplan 851 – Satzungsbeschluss",
        "titel_kurz": "Bebauungsplan 851",
        "summary": "Neue Wohnungen am Krusenbusch.",
        "committee": "Ausschuss für Stadtplanung und Bauen",
        "session_date": "2026-08-31",
        "applicants": "SPD-Fraktion",
        "topic_name": "Wohnen",
        "wichtig_grund": "Legt langfristig fest, was gebaut werden darf.",
        "top": true
      }],
      "relevant_per_session": {"88": 3},
      "further_per_session": {"88": [{
        "ksinr": 88,
        "item_number": "Ö 7",
        "title": "Quartier am Krusenbusch",
        "titel_kurz": "Quartier am Krusenbusch",
        "summary": null,
        "committee": "Ausschuss für Stadtplanung und Bauen",
        "session_date": "2026-08-31",
        "applicants": null,
        "topic_name": null,
        "wichtig_grund": null
      }]},
      "matches_per_session": {"88": 1},
      "matches_total": 1,
      "substantive_total": 11,
      "substantive_per_session": {"88": 8}
    }
    """#

    let preview = try JSONDecoder().decode(WeekPreview.self, from: Data(json.utf8))
    #expect(preview.sessions.first?.itemCount == 14)
    #expect(preview.items.first?.applicant == "SPD-Fraktion")
    #expect(preview.relevantItemsPerSession?["88"] == 3)
    #expect(preview.additionalItemsPerSession?["88"]?.first?.itemNumber == "Ö 7")
    #expect(preview.personalMatchesPerSession?["88"] == 1)
    #expect(preview.contentItemCount == 11)
    #expect(preview.contentItemsPerSession?["88"] == 8)
}

@Test func newAskRequestEncodesAnExplicitNullConversationID() throws {
    let data = try JSONEncoder().encode(AskRequest(question: "Was wurde beschlossen?"))
    let object = try #require(JSONSerialization.jsonObject(with: data) as? [String: Any])

    #expect(object.keys.contains("conversation_id"))
    #expect(object["conversation_id"] is NSNull)
}

@Test func newDeepResearchRequestEncodesAnExplicitNullConversationID() throws {
    let data = try JSONEncoder().encode(
        DeepResearchRequest(question: "Wie entwickelt sich der Radverkehr?", conversationID: nil)
    )
    let object = try #require(JSONSerialization.jsonObject(with: data) as? [String: Any])

    #expect(object["conversation_id"] is NSNull)
}
