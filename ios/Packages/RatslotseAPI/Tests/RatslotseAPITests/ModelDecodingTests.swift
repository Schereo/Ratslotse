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
        "n_items": 14,
        "highlights": [{
          "ksinr": 88,
          "item_number": "Ö 6",
          "title": "Bebauungsplan 851 – Satzungsbeschluss",
          "titel_kurz": "Bebauungsplan 851",
          "committee": "Ausschuss für Stadtplanung und Bauen",
          "session_date": "2026-08-31",
          "topic_name": null,
          "wichtig_grund": "Legt langfristig fest, was gebaut werden darf.",
          "top": true
        }]
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
    // Die Highlights je Sitzung tragen dieselbe Form wie `items` — ein Typ
    // für beide, damit die Sitzungsliste die Zeile der Wochenkarte nutzt.
    #expect(preview.sessions.first?.highlights?.first?.shortTitle == "Bebauungsplan 851")
    #expect(preview.sessions.first?.highlights?.first?.featured == true)
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

/// Die Tagesordnung liest die Anlagen unter dem Namen, den der SERVER benutzt.
///
/// Die App las bis 09/2026 `attachments`; auf der Leitung heißt das Feld
/// `anlagen`. `decodeIfPresent` machte daraus eine leere Liste — kein Fehler,
/// keine Meldung, nur eine Tagesordnung ohne Anlagen. Gerade Fraktionsanträge
/// ohne Vorlage hängen NUR dort. Genau die stille Sorte Fehler, vor der
/// `ios/CLAUDE.md` warnt; gefunden hat ihn ein Blick in die App.
///
/// Die Attrappe hier trägt deshalb bewusst den Feldnamen des Vertrags
/// (`api/openapi.json`, Schema `AgendaItemRow`) — vorher stand in der
/// Debug-Attrappe der App derselbe falsche Name und deckte den Fehler mit zu.
@Test func agendaItemReadsAttachmentsUnderTheNameTheServerUses() throws {
    let json = #"""
    {
      "ksinr": 88, "committee": "Verkehrsausschuss", "session_date": "2026-02-01",
      "agenda_items": [{
        "item_number": "Ö 4", "title": "Radverkehrskonzept", "is_public": 1,
        "template_number": "26/0400", "dringlich": false,
        "anlagen": [{"label": "Antrag der Fraktion", "url": "https://example.org/a.pdf"}]
      }, {
        "item_number": "Ö 7", "title": "Sichere Querung", "is_public": 1,
        "dringlich": true, "anlagen": []
      }],
      "decisions": [], "has_protocol": false
    }
    """#
    let detail = try JSONDecoder().decode(SessionDetail.self, from: Data(json.utf8))
    #expect(detail.agendaItems.count == 2)
    #expect(detail.agendaItems[0].attachments.count == 1)
    #expect(detail.agendaItems[0].attachments.first?.label == "Antrag der Fraktion")
    #expect(detail.agendaItems[0].isUrgent == false)
    // Ein Dringlichkeitsantrag steht nicht in der ursprünglichen Tagesordnung;
    // ohne die Marke liest er sich wie ein gewöhnlicher Punkt.
    #expect(detail.agendaItems[1].isUrgent == true)
    #expect(detail.agendaItems[1].attachments.isEmpty)
}

/// Fehlt das Feld ganz, bleibt die Zeile stehen — eine Tagesordnung ohne
/// Anlagen ist ein normaler Fall, kein Fehler.
@Test func agendaItemSurvivesMissingAttachments() throws {
    let json = #"""
    {"ksinr": 1, "committee": "Rat", "session_date": "2026-02-01",
     "agenda_items": [{"item_number": "Ö 1", "title": "Eröffnung", "is_public": 1}],
     "decisions": [], "has_protocol": false}
    """#
    let detail = try JSONDecoder().decode(SessionDetail.self, from: Data(json.utf8))
    #expect(detail.agendaItems[0].attachments.isEmpty)
    #expect(detail.agendaItems[0].isUrgent == false)
}


/// Der Live-Stand aus der Übertragung hängt an der heutigen Ratssitzung —
/// in der Liste UND im Detail. Fehlt er (jede andere Sitzung), bleibt beides
/// nil statt zu kippen.
@Test func liveStateDecodesOnSessionAndDetail() throws {
    let state = #"""
    {"item_number": "9.3", "item_title": "Radweg Alexanderstraße", "block_start": null,
     "phase": "aussprache", "speaker": "Susanne Drügemöller", "party": "Bündnis 90/Die Grünen",
     "since": "2026-09-03T18:12:00+02:00", "as_of": "2026-09-03T18:20:00+02:00",
     "updated_at": "2026-09-03T18:20:30+02:00", "finished": false}
    """#
    let session = try JSONDecoder().decode(CouncilSession.self, from: Data(#"""
    {"ksinr": 2, "committee": "Rat", "session_date": "2026-09-03", "session_time": "18:00",
     "live_until": "22:00", "n_items": 12, "live_state": \#(state)}
    """#.utf8))
    #expect(session.liveState?.itemNumber == "9.3")
    #expect(session.liveState?.speaker == "Susanne Drügemöller")
    #expect(session.liveState?.finished == false)

    let detail = try JSONDecoder().decode(SessionDetail.self, from: Data(#"""
    {"ksinr": 2, "committee": "Rat", "session_date": "2026-09-03",
     "agenda_items": [], "decisions": [], "has_protocol": false, "live_state": \#(state)}
    """#.utf8))
    #expect(detail.liveState?.itemTitle == "Radweg Alexanderstraße")

    let ohne = try JSONDecoder().decode(CouncilSession.self, from: Data(#"""
    {"ksinr": 3, "committee": "Bauausschuss", "session_date": "2026-09-04", "n_items": 4}
    """#.utf8))
    #expect(ohne.liveState == nil)
}

/// Das Kalender-Abo: drei Felder, zwei davon mit Unterstrich im Vertrag —
/// genau die Stelle, an der ein handgeschriebener Schlüssel still danebenliegt.
@Test func calendarSubscriptionDecodes() throws {
    let json = #"""
    {"url": "https://ratslotse.de/api/calendar/abc.ics",
     "webcal_url": "webcal://ratslotse.de/api/calendar/abc.ics",
     "subscribed_committees": 3}
    """#
    let abo = try JSONDecoder().decode(CalendarSubscription.self, from: Data(json.utf8))
    #expect(abo.url.hasSuffix("/abc.ics"))
    #expect(abo.webcalURL.hasPrefix("webcal://"))
    #expect(abo.subscribedCommittees == 3)
}

/// „Anderswo beschlossen": Sechs von sechzehn Feldern tragen einen
/// Unterstrich, und die Ratsinformationssysteme füllen sehr unterschiedlich
/// viel aus. Der zweite Eintrag hier ist der gemessene Münster-Fall — kein
/// `web`, keine Einordnung, kein Ergebnis.
@Test func elsewhereResponseDecodes() throws {
    let json = #"""
    {"decision_id": 8695, "bodies": ["Magdeburg", "Osnabrück"], "items": [
      {"body_id": "osnabrueck", "body_name": "Osnabrück", "paper_id": "os:p:1",
       "name": "Nachtkultur stärken", "reference": "VO/2026/1", "date": "2026-04-17",
       "kind": "motion", "paper_type_raw": "Antrag",
       "web": "https://example.org/vo/1", "outcome": "accepted", "outcome_raw": "beschlossen",
       "score": 0.856, "summary": "Koordinierungsstelle Nachtkultur.",
       "instrument": "Koordinierungsstelle schaffen", "transfer": "adaptable",
       "originator": "Gruppe Grüne/SPD/Volt"},
      {"body_id": "magdeburg", "body_name": "Magdeburg", "paper_id": "md:p:2",
       "name": "Projekt Nachtengel", "reference": null, "date": null,
       "kind": "motion", "paper_type_raw": null, "web": null, "outcome": "none",
       "outcome_raw": null, "score": 0.715, "summary": null, "instrument": null,
       "transfer": null, "originator": null}]}
    """#
    let antwort = try JSONDecoder().decode(ElsewhereResponse.self, from: Data(json.utf8))
    #expect(antwort.decisionID == 8695)
    #expect(antwort.bodies == ["Magdeburg", "Osnabrück"])
    #expect(antwort.items.count == 2)
    #expect(antwort.items[0].bodyName == "Osnabrück")
    #expect(antwort.items[0].outcome == "accepted")
    #expect(antwort.items[0].originator == "Gruppe Grüne/SPD/Volt")
    #expect(antwort.items[0].score == 0.856)
    // Ohne Adresse bleibt `web` leer — die Zeile bekommt dann keinen Link.
    #expect(antwort.items[1].web == nil)
    #expect(antwort.items[1].outcome == "none")
    #expect(antwort.items[1].id == "md:p:2")
}

/// Der leere Fall ist der Normalzustand vor dem ersten Cron-Lauf.
@Test func elsewhereResponseSurvivesEmptyPayload() throws {
    let leer = try JSONDecoder().decode(ElsewhereResponse.self,
                                        from: Data(#"{"decision_id": 1}"#.utf8))
    #expect(leer.items.isEmpty && leer.bodies.isEmpty)
}

/// „Ideen aus anderen Städten": Neun der zweiundzwanzig Felder tragen einen
/// Unterstrich, und die Belege sind verschachtelt. Der zweite Eintrag hier ist
/// der Fall, in dem das Modell nichts gefunden hat — dort ist die leere
/// Beleg-Liste die Aussage.
@Test func ideasResponseDecodes() throws {
    let json = #"""
    {"field": "klima_umwelt", "total": 44, "page": 1, "per_page": 30,
     "counts": {"missing": 39, "partial": 5}, "items": [
      {"paper_id": "bs:p:1", "body_id": "braunschweig", "body_name": "Braunschweig",
       "name": "Hitzeaktionsplan", "date": "2026-05-01", "kind": "motion",
       "web": "https://example.org/vo/1", "outcome": "accepted",
       "field": "klima_umwelt", "instrument": "Hitzeaktionsplan aufstellen",
       "summary": "Ein Plan gegen Hitze.", "transfer": "adaptable",
       "competence": "council", "originator": "SPD-Fraktion",
       "status": "partial", "reason": "Oldenburg hat den Wärmeplan, nicht den Hitzeplan.",
       "confidence": "high",
       "evidence": [{"decision_id": 8525, "kvonr": 4711, "title": "Kommunale Wärmeplanung",
                     "date": "2025-11-20", "outcome": "accepted"}]},
      {"paper_id": "md:p:2", "body_id": "magdeburg", "body_name": "Magdeburg",
       "name": "Hundewanderweg", "date": null, "kind": "motion",
       "web": null, "outcome": "none", "field": "klima_umwelt", "instrument": null,
       "summary": null, "transfer": "adaptable", "competence": null, "originator": null,
       "status": "missing", "reason": "Kein Beleg.",
       "confidence": "medium", "evidence": []}]}
    """#
    let antwort = try JSONDecoder().decode(IdeasResponse.self, from: Data(json.utf8))
    #expect(antwort.total == 44 && antwort.perPage == 30)
    #expect(antwort.counts["missing"] == 39)
    #expect(antwort.items.count == 2)
    let erste = antwort.items[0]
    #expect(erste.status == "partial")
    #expect(erste.reason.hasPrefix("Oldenburg"))
    #expect(erste.evidence.first?.decisionID == 8525)
    // Ohne Beschluss dahinter keine Zeigerhand — und ohne Beleg keine Liste.
    #expect(antwort.items[1].evidence.isEmpty)
    #expect(antwort.items[1].web == nil)
}

/// Der leere Fall ist der Normalzustand vor dem ersten Cron-Lauf.
@Test func ideaFieldsSurvivesEmptyPayload() throws {
    let leer = try JSONDecoder().decode(IdeaFields.self, from: Data(#"{}"#.utf8))
    #expect(leer.fields.isEmpty)
    let felder = try JSONDecoder().decode(IdeaFields.self, from: Data(#"""
    {"fields": [{"field": "verkehr", "total": 60, "missing": 40, "partial": 6,
                 "present": 8, "multi_city": 12}]}
    """#.utf8))
    #expect(felder.fields.first?.multiCity == 12)
    #expect(felder.fields.first?.id == "verkehr")
}

/// Die Karte „Neu bei Ratslotse": Bühne (mit Aufnahme) und Liste (ohne) in
/// derselben Antwort, dazu die Marke, die der Server für dieses Konto führt.
@Test func newsStateDecodesStageAndListForms() throws {
    let json = #"""
    {
      "releases": [{
        "version": "2.2.0", "date": "2026-09-07", "title": "Das Teilen-Update",
        "highlights": [
          {"title": "Sitzungen teilen", "text": "An jeder Zeile ein Teilen-Knopf.", "url": "/council?tab=sessions",
           "media": {"kind": "video", "src": "/neuigkeiten/2.2.0/teilen-ios.mp4", "alt": "Das Teilen-Blatt",
                     "aspect": "1206/2622", "poster": "/neuigkeiten/2.2.0/teilen-ios.webp"}},
          {"title": "Live", "text": "Welcher Punkt gerade dran ist.", "url": "/dashboard", "media": null}
        ]
      }],
      "older_count": 1,
      "seen_version": null
    }
    """#
    let state = try JSONDecoder().decode(NewsState.self, from: Data(json.utf8))
    let release = try #require(state.releases.first)
    #expect(release.title == "Das Teilen-Update")
    #expect(state.olderCount == 1)
    #expect(state.seenVersion == nil)
    let media = try #require(release.highlights.first?.media)
    #expect(media.isVideo)
    #expect(media.aspectRatio.map { $0 < 1 } == true)
    #expect(media.poster == "/neuigkeiten/2.2.0/teilen-ios.webp")
    #expect(release.highlights.last?.media == nil)
}
