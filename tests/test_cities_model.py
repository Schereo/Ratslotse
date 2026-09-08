"""Die kanonischen Regeln des Städte-Speichers.

Die Reihenfolge der Muster IST die Regel: „Änderungsantrag" enthält „antrag",
„Beantwortung einer Anfrage" enthält „anfrage", „geändert beschlossen" enthält
„beschlossen". Wer die Listen in ``council/cities/model.py`` umsortiert,
ändert die Klassifikation des ganzen Bestands — diese Fälle halten das fest.

Alle Rohwerte stammen aus echten Vorlagenarten der fünf Städte (gemessen
07.09.2026).
"""
from __future__ import annotations

import pytest

from council.cities.model import (
    Batch, FileRole, OrgKind, Outcome, PaperKind, display_originator, file_role, org_kind,
    outcome, paper_kind,
)


@pytest.mark.parametrize("raw,erwartet", [
    # Die Reihenfolge-Fallen zuerst.
    ("Änderungsantrag", PaperKind.AMENDMENT),
    ("Änderungs- /Ergänzungsantrag", PaperKind.AMENDMENT),
    ("Antrag (öffentlich)", PaperKind.MOTION),
    ("Antrag an den Rat", PaperKind.MOTION),
    ("Beantwortung einer Anfrage (Ausschuss)", PaperKind.ANSWER),
    ("Antwort auf Kleine Anfrage", PaperKind.ANSWER),
    ("Stellungnahme (Antrag)", PaperKind.ANSWER),
    ("Anfrage (öffentlich)", PaperKind.INQUIRY),
    ("Kleine Anfrage", PaperKind.INQUIRY),
    # Verwaltungsvorlagen
    ("Beschlussvorlage", PaperKind.PROPOSAL),
    ("Entscheidungsvorlage", PaperKind.PROPOSAL),
    ("Vorlagen", PaperKind.PROPOSAL),          # so heißt es in Münster
    ("Vorlage", PaperKind.PROPOSAL),
    ("Beschlussvorlage (bis 31.12.2022)", PaperKind.PROPOSAL),   # Oldenburger Katalog-Klammer
    ("Berichtsvorlage (bis 31.12.2022)", PaperKind.REPORT),
    ("Informationsvorlage", PaperKind.REPORT),
    ("Kenntnisnahme", PaperKind.REPORT),
    ("Mitteilungsvorlage", PaperKind.NOTICE),
    ("Mitteilung außerhalb von Sitzungen", PaperKind.NOTICE),
    ("Einwohnerfragen", PaperKind.PETITION),
    ("Anregungen von BV an Rat", PaperKind.MOTION),
    ("Resolution", PaperKind.MOTION),
    (None, PaperKind.OTHER),
    ("", PaperKind.OTHER),
    ("Grundstücksangelegenheiten", PaperKind.OTHER),
])
def test_paper_kind(raw, erwartet):
    assert paper_kind(raw) is erwartet


@pytest.mark.parametrize("raw,erwartet", [
    # „geändert beschlossen" darf NICHT auf ACCEPTED fallen.
    ("geändert beschlossen", Outcome.AMENDED),
    ("einstimmig geändert beschlossen", Outcome.AMENDED),
    ("ungeänderte Empfehlung", Outcome.ACCEPTED),
    ("ungeändert abgelehnt", Outcome.REJECTED),
    ("geänderte Empfehlung", Outcome.AMENDED),
    ("ungeändert beschlossen", Outcome.ACCEPTED),
    ("einstimmig beschlossen", Outcome.ACCEPTED),
    ("mehrheitlich angenommen", Outcome.ACCEPTED),
    ("genehmigt OB", Outcome.ACCEPTED),
    ("empfohlen", Outcome.ACCEPTED),
    ("mehrheitlich abgelehnt", Outcome.REJECTED),
    ("abgelehnt", Outcome.REJECTED),
    ("vertagt", Outcome.POSTPONED),
    ("zurückgestellt", Outcome.POSTPONED),
    ("von der Tagesordnung abgesetzt", Outcome.POSTPONED),
    ("verwiesen", Outcome.REFERRED),
    ("zurückgezogen", Outcome.WITHDRAWN),
    ("Sache ist erledigt", Outcome.WITHDRAWN),
    ("zur Kenntnis genommen", Outcome.NOTED),
    ("Kenntnis genommen", Outcome.NOTED),
    ("ohne Votum behandelt", Outcome.NONE),
    (None, Outcome.NONE),
    ("", Outcome.NONE),
])
def test_outcome(raw, erwartet):
    assert outcome(raw) is erwartet


@pytest.mark.parametrize("name,typ,erwartet", [
    # Ortsteil-Ebene zuerst — sie entscheidet, was NICHT vergleichbar ist.
    ("Stadtbezirksrat im Stadtbezirk 112 Wabe-Schunter-Beberbach", "Gremium", OrgKind.DISTRICT),
    ("Bezirksvertretung Münster-Mitte", None, OrgKind.DISTRICT),
    ("Ortsbeirat Eiche", "Gremium", OrgKind.DISTRICT),
    ("Ortschaftsrat Randau-Calenberge", "Ortschaftsrat", OrgKind.DISTRICT),
    ("Bürgerforum Stadtteil Atter", "Gremium", OrgKind.DISTRICT),
    ("Bezirksverwaltung Münster-West", None, OrgKind.DISTRICT),
    # Fraktionen
    ("CDU-Fraktion im Rat der Stadt", "Gremium", OrgKind.FACTION),
    ("Gruppe FDP/UWG", None, OrgKind.FACTION),
    ("Fraktion Tierschutzpartei", "Fraktion", OrgKind.FACTION),
    # Rat und Ausschüsse
    ("Rat der Stadt Osnabrück", "Gremium", OrgKind.COUNCIL),
    ("Stadtverordnetenversammlung der Landeshauptstadt Potsdam", "Gremium", OrgKind.COUNCIL),
    ("Ausschuss für Finanzen, Liegenschaften und Beteiligungssteuerung", "Gremium", OrgKind.COMMITTEE),
    ("Jugendhilfeausschuss", "Gremium", OrgKind.COMMITTEE),
    ("Ältestenrat", "Gremium", OrgKind.COMMITTEE),
    ("Betriebsausschuss OsnabrückerServiceBetrieb", "Gremium", OrgKind.COMMITTEE),
    # Verwaltung
    ("Amt für Migration und Integration", None, OrgKind.ADMINISTRATION),
    ("Stabsstelle Finanzen und Controlling", None, OrgKind.ADMINISTRATION),
    ("Irgendwas Unbekanntes", "Verwaltungsbereich", OrgKind.ADMINISTRATION),
    ("Aufsichtsrat der Stadtwerke", "Aufsichtsrat", OrgKind.OTHER),
])
def test_org_kind(name, typ, erwartet):
    assert org_kind(name, typ) is erwartet


@pytest.mark.parametrize("name,key,erwartet", [
    ("Sammeldokument öffentlich", "mainFile", FileRole.MAIN),
    # Somacos hat kein mainFile — das Hauptdokument hängt unter auxiliaryFile.
    ("Antrag", "auxiliaryFile", FileRole.MAIN),
    ("Beschlussvorlage", "auxiliaryFile", FileRole.MAIN),
    ("Anlage 3 Lageplan", "auxiliaryFile", FileRole.AUXILIARY),
    ("Karte", "auxiliaryFile", FileRole.AUXILIARY),
    (None, "auxiliaryFile", FileRole.AUXILIARY),
    ("Beschluss", "resolutionFile", FileRole.RESOLUTION),
    ("Einladung", "invitation", FileRole.INVITATION),
    ("Niederschrift", "resultsProtocol", FileRole.PROTOCOL),
    ("Wortprotokoll", "verbatimProtocol", FileRole.PROTOCOL),
    ("Irgendwas", "sonstwas", FileRole.OTHER),
])
def test_file_role(name, key, erwartet):
    assert file_role(name, key) is erwartet


def test_batch_counts_und_extend():
    from council.cities.model import Paper

    a = Batch(papers=[Paper("a:1", "a", "Titel")])
    b = Batch(papers=[Paper("a:2", "a", "Zweiter")])
    a.extend(b)
    assert a.counts()["papers"] == 2
    assert a.counts()["meetings"] == 0


@pytest.mark.parametrize("roh,art,erwartet", [
    # Fraktionen und Verwaltung — der Normalfall, unverändert durch.
    ("CDU-Fraktion", "motion", "CDU-Fraktion"),
    ("Gruppe Grüne/SPD/Volt", "inquiry", "Gruppe Grüne/SPD/Volt"),
    ("Fraktion BÜNDNIS 90/DIE GRÜNEN & Volt", "amendment",
     "Fraktion BÜNDNIS 90/DIE GRÜNEN & Volt"),
    # Ratsmitglieder mit Namen bleiben stehen (Tim, 08.09.2026): Wer einen
    # Antrag stellt, tut das als Mandatsträgerin in einem öffentlichen
    # Verfahren, der Name gehört zur Sache.
    ("Ratsmitglied Alexander Garder", "motion", "Ratsmitglied Alexander Garder"),
    ("Stadtverordneter Woelki, Fraktion Die Linke", "inquiry",
     "Stadtverordneter Woelki, Fraktion Die Linke"),
    ("Dr. Rainer Buchwald", "motion", "Dr. Rainer Buchwald"),
    ("Jonas Wolf, Emma Volkers", "inquiry", "Jonas Wolf, Emma Volkers"),
    # Eine EINGABE kommt von einer Privatperson. Dort zählt die Sache, nicht
    # wer sie eingereicht hat.
    ("Anna Beispiel", "petition", None),
    ("Ratsmitglied Alexander Garder", "petition", None),
    # Das Wort „null" statt eines leeren Feldes schreiben Modelle gelegentlich.
    ("null", "motion", None),
    ("k.A.", "motion", None),
    (None, "motion", None),
    ("", "motion", None),
    ("   ", None, None),
])
def test_display_originator(roh, art, erwartet):
    """Ratsmitglieder ja, Eingaben von Privatleuten nein.

    Gemessen am Bestand: Alle 1.860 Urheber-Angaben stehen an Anträgen,
    Anfragen, Änderungsanträgen, Antworten, Berichten, Vorlagen und
    Mitteilungen — durchweg Papiere aus Rat und Verwaltung. Eine Eingabe gibt
    es dort heute nicht; die Regel greift für den Tag, an dem eine Stadt
    dazukommt, die welche veröffentlicht.
    """
    assert display_originator(roh, art) == erwartet
