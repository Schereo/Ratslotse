#!/usr/bin/env python3
"""Einmalige, reproduzierbare Redaktion des Ortskandidaten-Backlogs.

Ohne ``--apply`` läuft die vollständige Prüfung auf einer temporären Kopie der
Datenbank. Der produktive Lauf legt vor dem Schreiben einen kompakten
Wiederherstellungs-Snapshot der betroffenen Redaktionstabellen an.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from council.store import CouncilStore


LSG = ("https://www.oldenburg.de/startseite/stadtraum/umwelt/"
       "naturschutz-und-landschaftspflege/schutzgebiete-und-schutzobjekte/"
       "landschaftsschutzgebiete-lsg.html")
LSG_DESCRIPTIONS = ("https://www.oldenburg.de/startseite/stadtraum/umwelt/"
                    "naturschutz-und-landschaftspflege/schutzgebiete-und-schutzobjekte/"
                    "landschaftsschutzgebiete-lsg/schutzgebietsbeschreibungen.html")
NSG = ("https://www.oldenburg.de/startseite/stadtraum/umwelt/"
       "naturschutz-und-landschaftspflege/schutzgebiete-und-schutzobjekte/"
       "naturschutzgebiete-nsg.html")
BPLANS = ("https://www.oldenburg.de/startseite/stadtraum/planen-bauen/"
          "stadterneuerung-gestaltung-bau/stadtplanung/bauleitplanung.html")
SPORTS = ("https://www.oldenburg.de/fileadmin/oldenburg/Benutzer/Dateien/"
          "30_Amt_fuer_Kultur_Museen_und_Sport/304_Sport/Sportstaetten/"
          "Sportplaetze/UEbersicht_Sportplaetze_Stadt_Oldenburg_b.pdf")


# Exakte physische Orte. Optional kann nach dem Typ ein bereinigter Anzeigename
# stehen; ansonsten bleibt der beobachtete Name erhalten.
CONCRETE: dict[str, tuple[str, str | None]] = {
    "lindenhofsgarten": ("strasse", None),
    "kuestenkanal": ("gewaesser", None),
    "sperberweg": ("strasse", None),
    "stadion-maastrichter-strasse": ("anlage", None),
    "offizierskasino": ("gebaeude", None),
    "esskamp-126": ("gebaeude", None),
    "haus-der-jugend": ("gebaeude", None),
    "skateanlage-eversten": ("anlage", None),
    "schiessstand": ("anlage", None),
    "amalienbruecke": ("bauwerk", None),
    "schlosshoefe": ("gebaeude", None),
    "zob": ("anlage", None),
    "rauhehorst": ("strasse", None),
    "standesamt": ("gebaeude", None),
    "kloster-blankenburg": ("anlage", None),
    "buemmersteder-tredde": ("strasse", None),
    "drielaker-see": ("gewaesser", None),
    "baekeplacken": ("strasse", None),
    "am-festungsgraben": ("strasse", None),
    "skatehalle-oldenburg": ("gebaeude", None),
    "bahnhof": ("gebaeude", None),
    "schellenberg": ("strasse", None),
    "finanzamtsgelaende": ("anlage", None),
    "am-tweelbaeker-see": ("strasse", None),
    "sporthalle-maastrichter-strasse": ("anlage", None),
    "westkreuz": ("anlage", None),
    "tonkuhle": ("gewaesser", None),
    "oldenburger-kompostwerk": ("anlage", None),
    "oldenburg-osnabrueck": ("verkehrsweg", "Bahnstrecke Oldenburg–Osnabrück"),
    "am-apfelhof": ("strasse", None),
    "sport-und-gesundheitsbad-am-floetenteich": ("anlage", None),
    "wasserwerk-alexandersfeld": ("anlage", None),
    "esskamp-72": ("gebaeude", None),
    "olantis": ("anlage", "OLantis"),
    "schuetzenweg-34": ("gebaeude", None),
    "am-schiessstand": ("strasse", None),
    "sporthalle-haarenesch": ("anlage", None),
    "tiefgarage-am-stadtmuseum": ("bauwerk", None),
    "fahrradstation-nord": ("anlage", None),
    "park-und-kramermarktsflaeche": ("anlage", None),
    "kunstrasenplatz-ofenerdiek": ("anlage", None),
    "altes-gymnasium-oldenburg": ("gebaeude", None),
    "bahnuebergang-am-stadtrand": ("bauwerk", None),
    "tiefgarage-cco": ("bauwerk", None),
    "a-293": ("verkehrsweg", None),
    "feldkamp": ("strasse", None),
    "oldenburg-ost": ("verkehrsweg", "Autobahnkreuz Oldenburg-Ost"),
    "patentbusch": ("strasse", None),
    "autobahn-a-29": ("verkehrsweg", None),
    "gedenkstein-fuer-wilhelm-den-grossen": ("bauwerk", None),
    "rosa-lazarus-strasse": ("strasse", None),
    "tami-oelfken-strasse": ("strasse", None),
    "aeg-motorenwerk": ("anlage", None),
    "sportanlage-kennedystrasse": ("anlage", None),
    "pflegeeinrichtung-schinkelstrasse": ("gebaeude", None),
}


# Flächige, wiederverwendbare Teilräume des gemeinsamen Ortskatalogs.
APPROVED: dict[str, dict] = {
    "dobbenanlagen": dict(
        place_id="dobbenanlage", name="Dobbenanlage", kind="park",
        parent_id="dobbenviertel", aliases=["Dobbenanlagen"],
        description="Historische öffentliche Grünanlage im Dobbenviertel.",
        source_url=("https://www.oldenburg.de/startseite/leben-in-oldenburg/"
                    "sport-freizeit/gruen-und-parkanlagen/dobbenanlage.html")),
    "heidbrook": dict(
        place_id="heidbrook", name="Heidbrook", kind="schutzgebiet",
        parent_id="wechloy", aliases=["Landschaftsraum Heidbrook"],
        description="Landschaftsraum zwischen Wechloy und Bürgerfelde; als Landschaftsschutzgebiet vorgesehen.",
        source_url=("https://www.oldenburg.de/startseite/stadtraum/umwelt/"
                    "naturschutz-und-landschaftspflege/schutzgebiete-und-schutzobjekte/"
                    "landschaftsschutzgebiete-lsg/landschaftsschutzgebiet-heidbrook-geplant.html")),
    "alexanderstrasse-nord": dict(
        place_id="alexanderstrasse-nord", name="Alexanderstraße-Nord",
        kind="entwicklungsgebiet", parent_id="buergerfelde",
        aliases=["Vergnügungsstätten Alexanderstraße Nord"],
        description="Geltungsbereich des Bebauungsplans 843 zur Alexanderstraße-Nord.",
        source_url=("https://www.oldenburg.de/fileadmin/oldenburg/Benutzer/Dateien/"
                    "22_Rechtsamt/Bekanntmachungen/Bebauungsplan_843_"
                    "Vergnuegungsstaetten_Alexanderstrasse-Nord.pdf")),
    "mittlere-innenstadt": dict(
        place_id="mittlere-innenstadt", name="Mittlere Innenstadt",
        kind="sanierungsgebiet", parent_id="innenstadt",
        aliases=["Sanierungsgebiet Mittlere Innenstadt"],
        description="Stadterneuerungsgebiet zur Stärkung der mittleren Innenstadt.",
        source_url=("https://www.oldenburg.de/startseite/stadtraum/planen-bauen/"
                    "stadterneuerung-gestaltung-bau/stadterneuerung/mittlere-innenstadt.html")),
    "buergerbusch": dict(
        place_id="buergerbusch", name="Bürgerbusch", kind="park",
        parent_id="buergerfelde", aliases=["Großer Bürgerbusch", "Kleiner Bürgerbusch"],
        description="Zusammenhängender Grün- und Waldraum im Oldenburger Nordwesten.",
        source_url=LSG),
    "mittelweg-fliegerhorst": dict(
        place_id="mittelweg-fliegerhorst", name="Mittelweg/Fliegerhorst",
        kind="wohngebiet", parent_id="fliegerhorst",
        aliases=["Baugebiet Mittelweg/Fliegerhorst", "N-777 D"],
        description="Wohnbauabschnitt N-777 D auf dem ehemaligen Fliegerhorst.",
        source_url=("https://www.oldenburg.de/startseite/stadtraum/zentrale-projekte/"
                    "fliegerhorst/bauabschnitte/n-777-d-mittelweg.html")),
    "ludwig-quidde-hof": dict(
        place_id="ludwig-quidde-hof", name="Ludwig-Quidde-Hof",
        kind="wohngebiet", parent_id="ohmstede", aliases=[],
        description="Wohnprojekt und Geltungsbereich des vorhabenbezogenen Bebauungsplans 56.",
        source_url="https://buergerinfo.oldenburg.de/getfile.php?id=235687&type=do"),
    "haarenniederung": dict(
        place_id="haarenniederung", name="Haarenniederung", kind="schutzgebiet",
        parent_id="bloherfelde", aliases=["LSG Haarenniederung"],
        description="Landschaftsschutzgebiet im Westen Oldenburgs.", source_url=LSG),
    "everstenmoor": dict(
        place_id="everstenmoor", name="Everstenmoor", kind="schutzgebiet",
        parent_id="nordmoslesfehn", aliases=["Everstener Moor", "NSG Everstenmoor"],
        description="Naturschutzgebiet und Hochmoorrest am westlichen Stadtrand.", source_url=NSG),
    "mittlere-hunte": dict(
        place_id="mittlere-hunte", name="Mittlere Hunte", kind="schutzgebiet",
        aliases=["Naturschutzgebiet Mittlere Hunte", "LSG Mittlere Hunte"],
        description="Landschaftsschutzraum entlang der mittleren Hunte mit Anteilen im Stadtgebiet.",
        source_url=LSG_DESCRIPTIONS),
    "buschhagenniederung": dict(
        place_id="buschhagenniederung", name="Buschhagenniederung", kind="schutzgebiet",
        parent_id="kreyenbrueck", aliases=["LSG Buschhagenniederung"],
        description="Nördlicher Teil des Landschaftsschutzraums Mittlere Hunte im Oldenburger Stadtgebiet.",
        source_url=LSG_DESCRIPTIONS),
    "quartier-am-krusenbusch": dict(
        place_id="quartier-am-krusenbusch", name="Quartier am Krusenbusch",
        kind="wohngebiet", parent_id="krusenbusch", aliases=["Bebauungsplan 865"],
        description="Geplantes Wohnquartier zwischen Am Schmeel, Tweelbäker Tredde und Brahmweg.",
        source_url=("https://www.oldenburg.de/startseite/stadtraum/planen-bauen/"
                    "stadterneuerung-gestaltung-bau/stadtplanung/aktuelles/"
                    "neues-wohnquartier-am-krusenbusch.html")),
    "stadthafen-sued": dict(
        place_id="stadthafen-sued", name="Stadthafen Süd", kind="wohngebiet",
        parent_id="osternburg", aliases=["Alter Stadthafen Süd", "O-782 B"],
        description="Wohn- und Entwicklungsbereich auf der Südseite des Alten Stadthafens.",
        source_url=("https://www.oldenburg.de/startseite/stadtraum/planen-bauen/"
                    "stadterneuerung-gestaltung-bau/stadterneuerung/"
                    "aktuelle-stadterneuerungsgebiete/alter-stadthafen.html")),
    "sportpark-kreyenbrueck": dict(
        place_id="sportpark-kreyenbrueck", name="Sportpark Kreyenbrück",
        kind="sportgebiet", parent_id="kreyenbrueck", aliases=[],
        description="Öffentliche Sport- und Freizeitanlage an der Brandenburger Straße.",
        source_url=("https://www.oldenburg.de/startseite/leben-in-oldenburg/sport-freizeit/"
                    "sport/sportbuero/aktuelles/sportpark-kreyenbrueck.html")),
    "hunteniederung": dict(
        place_id="hunteniederung", name="Hunteniederung", kind="schutzgebiet",
        parent_id="bornhorst", aliases=["EU-Vogelschutzgebiet V11 Hunteniederung"],
        description="EU-Vogelschutzgebiet der Hunteniederung mit Flächen im Oldenburger Nordosten.",
        source_url=NSG),
    "moorhauser-polder": dict(
        place_id="moorhauser-polder", name="Moorhauser Polder", kind="schutzgebiet",
        parent_id="bornhorst", aliases=["NSG Moorhauser Polder"],
        description="Naturschutzgebiet im Verbund der Hunteniederung.", source_url=NSG),
    "dede-dragoner-und-schulstrasse": dict(
        place_id="dede-dragoner-schulstrasse", name="Quartier Dede-, Dragoner- und Schulstraße",
        kind="quartier", parent_id="osternburg",
        aliases=["Quartier rund um Dede-, Dragoner- und Schulstraße"],
        description="In den Ratsunterlagen gemeinsam betrachtetes Quartier um drei Straßen.",
        source_url=("https://www.oldenburg.de/metanavigation/presse/pressemitteilung/"
                    "news/am-montag-21-maerz-tagt-der-verkehrsausschuss.html")),
    "sportpark-osternburg": dict(
        place_id="sportpark-osternburg", name="Sportpark Osternburg", kind="sportgebiet",
        parent_id="tweelbaeke", aliases=[],
        description="Städtische Sportanlage an der Gerhard-Stalling-Straße.", source_url=SPORTS),
    "meerkamp-mittagsweg": dict(
        place_id="meerkamp-mittagsweg", name="Meerkamp/Mittagsweg",
        kind="entwicklungsgebiet", parent_id="kreyenbrueck", aliases=[],
        description="Nach den angrenzenden Straßen benannter städtebaulicher Planungsbereich.",
        source_url="https://buergerinfo.oldenburg.de/getfile.php?id=246577&type=do"),
    "wunderburgpark": dict(
        place_id="wunderburgpark", name="Wunderburgpark", kind="park",
        parent_id="osternburg", aliases=["Landschaftsschutzgebiet Wunderburgpark"],
        description="Geschützte Park- und Grünanlage in Osternburg.", source_url=LSG),
    "gewerbegebiet-brokhausen": dict(
        place_id="gewerbegebiet-brokhausen", name="Gewerbegebiet Brokhausen",
        kind="entwicklungsgebiet", parent_id="fliegerhorst", aliases=["Bebauungsplan 869"],
        description="Planungsbereich für das Gewerbegebiet Brokhausen.",
        source_url="https://buergerinfo.oldenburg.de/getfile.php?id=308544&type=do"),
    "sportpark-dornstede": dict(
        place_id="sportpark-dornstede", name="Sportpark Dornstede", kind="sportgebiet",
        parent_id="ohmstede", aliases=[], description="Städtische Sportanlage in Dornstede.",
        source_url=SPORTS),
    "helleheide": dict(
        place_id="helleheide", name="Helleheide", kind="wohngebiet",
        parent_id="fliegerhorst", aliases=["Quartier Helleheide", "N-777 F"],
        description="Smart-City-Wohnquartier auf dem ehemaligen Fliegerhorst.",
        source_url=("https://www.oldenburg.de/metanavigation/presse/pressemitteilung/news/"
                    "schoene-aussichten-wie-sich-der-fliegerhorst-veraendert.html")),
    "fussgaengerzone": dict(
        place_id="fussgaengerzone", name="Fußgängerzone", kind="quartier",
        parent_id="innenstadt", aliases=["Oldenburger Fußgängerzone"],
        description="Weitgehend autofreier Einkaufs- und Aufenthaltsbereich der Innenstadt.",
        source_url=("https://www.oldenburg.de/startseite/wirtschaft/standort-oldenburg/"
                    "innenstadtmanagement/virtuelle-innenstadt.html")),
    "gertrudenfriedhof": dict(
        place_id="gertrudenfriedhof", name="Gertrudenfriedhof", kind="park",
        parent_id="ehnernviertel", aliases=["Gertrudenkirchhof"],
        description="Historischer, parkartig gestalteter Friedhof zwischen Alexander- und Nadorster Straße.",
        source_url=("https://www.oldenburg.de/startseite/tourist/touristische-informationen/"
                    "sehenswuerdigkeiten/parks-und-gaerten.html")),
    "doktorsklappe": dict(
        place_id="doktorsklappe", name="Doktorsklappe", kind="wohngebiet",
        parent_id="bahnhofsviertel", aliases=["Vorhabenbezogener Bebauungsplan 55"],
        description="Nach dem Bebauungsplan 55 benannter Wohn- und Entwicklungsbereich.",
        source_url=BPLANS),
    "bahndammgelaende-krusenbusch": dict(
        place_id="bahndammgelaende-krusenbusch", name="Bahndammgelände Krusenbusch",
        kind="schutzgebiet", parent_id="krusenbusch",
        aliases=["NSG Bahndammgelände Krusenbusch"],
        description="Naturschutzgebiet auf dem ehemaligen Verschiebebahnhof Krusenbusch.",
        source_url=("https://www.oldenburg.de/startseite/stadtraum/umwelt/"
                    "naturschutz-und-landschaftspflege/schutzgebiete-und-schutzobjekte/"
                    "naturschutzgebiete-nsg/bahndammgelaende-krusenbusch.html")),
    "haaren-und-wold-bei-wechloy": dict(
        place_id="haaren-und-wold-bei-wechloy", name="Haaren und Wold bei Wechloy",
        kind="schutzgebiet", parent_id="wechloy", aliases=["FFH 237"],
        description="FFH-Gebiet mit Teilflächen innerhalb der Stadt Oldenburg.", source_url=NSG),
    "mittlere-und-untere-hunte": dict(
        place_id="mittlere-und-untere-hunte", name="Mittlere und Untere Hunte",
        kind="schutzgebiet", aliases=["FFH 174"],
        description="Überregionales FFH-Gebiet mit Teilflächen und Bezügen im Oldenburger Stadtgebiet.",
        source_url=NSG),
    "hellmskamp": dict(
        place_id="hellmskamp", name="Hellmskamp", kind="entwicklungsgebiet",
        parent_id="etzhorn", aliases=["Bebauungsplan N-817"],
        description="Geltungsbereich des Bebauungsplans N-817 in Etzhorn.", source_url=BPLANS),
    "klaevemann-siedlung": dict(
        place_id="klaevemann-siedlung", name="Klävemann-Siedlung", kind="wohngebiet",
        parent_id="bloherfelde", aliases=["Klävemann-Siedlung Schramperweg"],
        description="Historische Siedlung am Schramperweg.",
        source_url=("https://www.oldenburg.de/fileadmin/oldenburg/Benutzer/Dateien/"
                    "20_Controlling_und_Finanzen/200_Finanzen/Tautz_Ausarbeitung.pdf")),
    "havekant": dict(
        place_id="havekant", name="Havekant", kind="wohngebiet",
        parent_id="osternburg", aliases=["Neubaugebiet Havekant"],
        description="Wohngebiet an der Uferstraße südlich des Alten Stadthafens.",
        source_url=("https://www.oldenburg.de/metanavigation/presse/pressemitteilung/"
                    "news/sperrung-der-uferstrasse.html")),
    "alten-krusenbusch": dict(
        place_id="alter-krusenbusch", name="Alter Krusenbusch", kind="schutzgebiet",
        parent_id="krusenbusch", aliases=["Rest des Alten Krusenbusches", "Alten Krusenbusch"],
        description="Bewaldeter Hochmoorrest im nördlichen Krusenbusch.",
        source_url=("https://www.oldenburg.de/fileadmin/oldenburg/Benutzer/Dateien/"
                    "43_Amt_fuer_Umweltschutz_und_Bauordnung/432_Naturschutz_technischer_Umweltschutz/"
                    "Naturschutz/Natur_und_Landschaft_Gruene_Vielfalt_web.pdf")),
}


# Schreibvarianten bereits katalogisierter Orte. Flächige Zielorte werden vor
# diesen Einträgen angelegt, damit der Lauf auch auf einer frischen DB gelingt.
ALIASES: dict[str, tuple[str, str]] = {
    "haarentorviertel": ("haarentor", "Gebräuchliche Bezeichnung für den Ortsbereich Haarentor."),
    "brokhausen": ("gewerbegebiet-brokhausen", "Fundstellen beziehen sich überwiegend auf das Gewerbegebiet Brokhausen."),
    "quartier-haarentor": ("haarentor", "Namensvariante des Ortsbereichs Haarentor."),
    "hallensichel": ("hallensichel-ost", "Kurzform des bereits katalogisierten Entwicklungsgebiets Hallensichel-Ost."),
    "fliegerhorstgelaende": ("fliegerhorst", "Bezeichnung für das Gelände des Ortsbereichs Fliegerhorst."),
    "fliegerhorst-gelaende": ("fliegerhorst", "Schreibvariante für das Gelände des Ortsbereichs Fliegerhorst."),
    "alten-stadthafen": ("alter-stadthafen", "Deklinierten Namensform des Alten Stadthafens."),
    "innenstadtbereich": ("innenstadt", "Beschreibt den vorhandenen Ortsbereich Innenstadt."),
}


# Keine belastbaren Oldenburger Orte: Institutionen, Ereignisse, Partnerstädte,
# überregionale Räume, generische Begriffe oder gemischte Streckenbezeichnungen.
REJECTED: dict[str, str] = {
    "fliegerhorst-innenstadt": "Fahrradachsen- beziehungsweise Projektname, kein eigener Ort.",
    "kramermarkt": "Veranstaltung; die konkrete Park- und Kramermarktsfläche wird separat geführt.",
    "hafen": "Mischt den physischen Hafen mit dem städtischen Eigenbetrieb.",
    "niedersachsen": "Überregionales Bundesland, kein Oldenburger Ortsbereich.",
    "baederbetrieb-oldenburg": "Städtischer Eigenbetrieb, kein Ort.",
    "stadtsueden": "Unbestimmter Sammelbegriff ohne stabile Abgrenzung.",
    "wendehafen": "In den Stichproben ein Team- beziehungsweise Projektname, kein Ort.",
    "untere-hunte": "Historische Schutzgebietsbezeichnung; die damalige Verordnung ist aufgehoben.",
    "machatschkala": "Partnerstadt außerhalb Oldenburgs.",
    "fliegerhorst-offizierskasino": "Gemischte Dublette aus Ortsbereich und Gebäude.",
    "mateh-asher": "Partnerregion außerhalb Oldenburgs.",
    "gebaeudewirtschaft-und-hochbau": "Städtischer Eigenbetrieb, kein Ort.",
    "metropolregion-nordwest": "Überregionale Organisation und Raumbezeichnung.",
    "hude": "Nachbargemeinde außerhalb Oldenburgs.",
    "hafen-der-stadt-oldenburg-oldb": "Name des Eigenbetriebs, nicht des physischen Orts.",
    "kompostwerk": "Unspezifische Dublette des separat bestätigten Oldenburger Kompostwerks.",
    "oldenburger-stadtgebiet": "Bezeichnet die gesamte Stadt und ist kein Teilraum.",
    "cholet": "Partnerstadt außerhalb Oldenburgs.",
    "egh": "Abkürzung des Eigenbetriebs Gebäudewirtschaft und Hochbau, kein Ort.",
    "stadtgebiet": "Generischer Begriff ohne eigene räumliche Abgrenzung.",
    "stadtteil": "Generischer Gattungsbegriff.",
    "oldenburger-land": "Überregionale Bezeichnung und Bestandteil von Institutionsnamen.",
    "abfallwirtschaft": "Städtischer Eigenbetrieb beziehungsweise Aufgabenbereich, kein Ort.",
    "vapiano": "Ehemaliger Gastronomiebetrieb; kein dauerhafter kommunalpolitischer Ortsbereich.",
    "ipweger-moor-gellener-torfmoeoerte": "Überwiegend außerhalb des Oldenburger Stadtgebiets.",
    "sager-meer-ahlhorner-fischteiche-und-lethe": "Schutzgebiet außerhalb des Oldenburger Stadtgebiets.",
    "hafen-iprump": "Hafen in der Gemeinde Hude und damit außerhalb des Oldenburger Stadtgebiets.",
}


def review_manifest() -> dict[str, dict]:
    reviews: dict[str, dict] = {}
    for slug, (kind, name) in CONCRETE.items():
        reviews[slug] = {
            "status": "concrete", "kind": kind, "name": name,
            "note": "Als wiederkehrender konkreter physischer Ort bestätigt.",
        }
    for slug, values in APPROVED.items():
        reviews[slug] = {
            "status": "approved", **values,
            "note": "Als flächiger Ratslotse-Katalogort anhand amtlicher Quellen bestätigt.",
        }
    for slug, (target, reason) in ALIASES.items():
        reviews[slug] = {
            "status": "alias", "canonical_place_id": target, "note": reason,
        }
    for slug, reason in REJECTED.items():
        reviews[slug] = {"status": "rejected", "note": reason}
    expected = len(CONCRETE) + len(APPROVED) + len(ALIASES) + len(REJECTED)
    if len(reviews) != expected:
        raise ValueError("Doppelte Slugs im Review-Manifest")
    return reviews


def apply_reviews(db_path: str, updated_by: str, *, refresh_reviewed: bool = False) -> dict:
    reviews = review_manifest()
    store = CouncilStore(db_path)
    try:
        pending = {row["slug"] for row in store.location_candidates("pending", limit=500)}
        uncovered = sorted(pending - reviews.keys())
        if uncovered:
            raise ValueError(f"Offene Kandidaten ohne Urteil: {', '.join(uncovered)}")
        if refresh_reviewed:
            observed = {row["slug"] for row in store.location_candidates(
                "all", limit=500, min_decisions=1)}
            applicable = observed & reviews.keys()
        else:
            applicable = pending & reviews.keys()
        order = {"approved": 0, "concrete": 1, "alias": 2, "rejected": 3}
        saved = Counter()
        for slug in sorted(applicable, key=lambda key: (order[reviews[key]["status"]], key)):
            body = {key: value for key, value in reviews[slug].items() if value is not None}
            store.review_location_candidate(slug, updated_by=updated_by, **body)
            saved[body["status"]] += 1
        backfilled = store.backfill_location_place_ids()
        remaining = store.location_candidates("pending", limit=500)
        if remaining:
            raise ValueError(f"Nach dem Lauf noch offen: {', '.join(r['slug'] for r in remaining)}")
        return {
            "manifest": len(reviews), "applied": sum(saved.values()),
            "statuses": dict(saved), "place_ids_backfilled": backfilled,
            "map_points": len(store.decision_location_map_points()),
        }
    finally:
        store.close()


def snapshot(db_path: str) -> str:
    path = Path(db_path)
    backup_dir = path.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = backup_dir / f"place_reviews_before_full_review_{stamp}.json"
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    data = {
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "reviews": [dict(row) for row in conn.execute("SELECT * FROM council_place_reviews")],
        "locations": [dict(row) for row in conn.execute(
            "SELECT slug,place_id,ortsbereich_id,stadtteil,lat,lon,geojson,geo_tried,updated_at "
            "FROM council_locations")],
    }
    conn.close()
    backup_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(backup_path)


def dry_run(db_path: str, updated_by: str, *, refresh_reviewed: bool = False) -> dict:
    fd, temp_path = tempfile.mkstemp(prefix="ratslotse-location-review-", suffix=".sqlite")
    os.close(fd)
    source = sqlite3.connect(db_path)
    target = sqlite3.connect(temp_path)
    source.backup(target)
    target.close()
    source.close()
    try:
        return apply_reviews(temp_path, updated_by, refresh_reviewed=refresh_reviewed)
    finally:
        os.remove(temp_path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="data/council.sqlite")
    parser.add_argument("--updated-by", default="codex-redaktion")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--refresh-reviewed", action="store_true")
    args = parser.parse_args()
    result = dry_run(args.db, args.updated_by, refresh_reviewed=args.refresh_reviewed)
    result["mode"] = "dry-run"
    if args.apply:
        result["backup"] = snapshot(args.db)
        result = {**apply_reviews(args.db, args.updated_by,
                                  refresh_reviewed=args.refresh_reviewed),
                  "mode": "applied", "backup": result["backup"]}
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
