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
        "outcome": "angenommen", "vote": "mehrheitlich", "gegenstimmen": 2,
        "enthaltungen": 1, "factions": ["SPD"], "vorlage_nr": "26/0400"
      },
      "present_parties": ["CDU", "SPD"],
      "ratsinfo_url": "https://buergerinfo.oldenburg.de/si0057.php?__ksinr=88",
      "sub_votes": [{
        "id": 43, "title": "Änderungsantrag", "committee": "Verkehrsausschuss",
        "session_date": "2026-02-01", "outcome": "abgelehnt", "factions": ["CDU"]
      }],
      "vorlage_journey": [{
        "ksinr": 87, "committee": "Ausschuss", "session_date": "2026-01-20", "item_number": "Ö 3"
      }],
      "beratungsfolge": [{
        "datum": "2026-02-01", "gremium": "Rat", "top": "Ö 2", "ergebnis": "angenommen",
        "ksinr": 88, "future": false
      }],
      "vorlage_url": "https://buergerinfo.oldenburg.de/vo0050.php?__kvonr=901",
      "vorlage": {
        "vorlage_nr": "26/0400", "title": "Radweg", "art": "Beschlussvorlage",
        "document_url": "https://example.test/vorlage.pdf", "n_pages": 3,
        "excerpt": "Sachverhalt: Die Stadt plant einen Radweg.", "amt": "Amt für Verkehr"
      },
      "anlagen": [{
        "document_id": 77, "label": "Antrag der SPD", "url": "https://example.test/77.pdf",
        "is_antrag": 1, "antragsteller": ["SPD"], "status": "ok"
      }],
      "beteiligung": {
        "titel": "Beteiligung zum Plan", "schritt": "Entwurf", "von": "2026-01-01",
        "bis": "2026-02-15", "url": "https://example.test/beteiligung", "status": "laufend"
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

@Test func savedCouncilResponsesDecodeCurrentServerShape() throws {
    let bookmarksJSON = #"""
    {"bookmarks":[{
      "id":5,"kind":"decision","title":"Radweg","subtitle":"Rat · 2026-02-01",
      "state":"decided","url":"/council/decision?id=42","ksinr":88,"item_number":"Ö 2",
      "notify_result":false,"decision":{"id":42,"title":"Radweg","outcome":"angenommen"},
      "session":null
    }]}
    """#
    let followsJSON = #"""
    {"follows":[{
      "id":7,"kvonr":901,"vorlage_nr":"26/0400","title":"Radweg","url":"https://example.test/vorlage",
      "n_stationen":2,"naechste":{"datum":"2026-10-01","gremium":"Rat","ergebnis":null},
      "letzte":{"datum":"2026-02-01","gremium":"Ausschuss","ergebnis":"angenommen"}
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
        "outcome": "angenommen",
        "is_new": true
      }],
      "hits_30d": 3
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
    #expect(topic.hits30Days == 3)
    #expect(topic.unreadCount == 0)
}
