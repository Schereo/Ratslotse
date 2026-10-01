"""Kuratierte Stadtthemen für die Themen-Vorschläge (Onboarding, Schritt 3).

Die Vorschläge aus der Entitäts-Erkennung sind das, was der Rat zuletzt
*benannt* hat — und das sind Straßen und Plannummern. Wer neu ist, kennt die
Nadorster Straße nicht als Vorgang, wohl aber Radverkehr oder Kitas: Das sind
die Interessen, mit denen Menschen kommen (Tims Befund, 03.09.2026: „das holt
einen wahrscheinlich mehr ab als irgendwelche random Straßennamen").

Die Liste steht als Code, wie die Prompts: Jeder Eintrag ist ein Name für
Menschen, ein Suchmuster für die Zählung und die Beschreibung, an der der
Themen-Wächter später jeden neuen Beschluss misst. Ein Eintrag ist damit im
Pull Request sichtbar, mit Diff und Historie.

**Nichts anbieten, was der Rat nicht liefert.** Jeder Eintrag wird bei jedem
Aufruf gegen die Beschlüsse der letzten zwölf Monate gezählt und fällt unter
``MIN_DECISIONS`` still weg. Am dev-Abzug vom 03.09.2026 nachgemessen: Parken
(1), Barrierefreiheit (2), Geflüchtete (0) und Tempo 30 (2) klingen populär,
kommen im Rat aber kaum vor — sie stehen deshalb nicht hier. Die Zahl an der
Kachel ist eine Wortsuche in Titel und Zusammenfassung; der Wächter rechnet
mit Embeddings und Cross-Encoder, die Richtung ist dieselbe.

Zwei Grenzen nach oben, beide bewusst: Bebauungspläne (65 im Jahr) und
„Sport" allgemein (38) wären als Thema eine Meldung pro Woche — das ist kein
Interesse mehr, das ist ein Feed. Die Einträge hier liegen bei ein bis zwei
Meldungen im Monat. Deshalb steht „Sport" nur als *Sporthallen und
Sportplätze* da (Wortsuche enger, Beschreibung enger), „Kultur" als Häuser
und Förderung.

**Mischung statt Rangliste** (Tims Befund, 30.09.2026: Neue Konten nahmen fast
nur Stadtteile). Die Liste wächst deshalb über Verkehr und Bauen hinaus, und
angezeigt wird sie in ``ANZEIGE`` — von Hand so gemischt, dass schon die erste
Reihe Verkehr, Freizeit, Kinder und Stadtentwicklung zeigt. Nach Zahl zu
sortieren hätte Schulen, Haushalts- und Bauthemen nach vorn gespült.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta

#: Unter so vielen Beschlüssen in ``WINDOW_DAYS`` wird ein Thema nicht
#: angeboten: Wer es anklickt, soll in den nächsten Wochen etwas hören.
MIN_DECISIONS = 6

#: Zeitfenster der Zählung. EIN Fenster, kein gleitendes wie bei den
#: Stadtteilen: Die Überschrift heißt „gerade in Oldenburg", und ein Thema,
#: das nur über drei Jahre auf seine Zahl kommt, ist nicht „gerade".
WINDOW_DAYS = 365


@dataclass(frozen=True)
class CityTopic:
    key: str
    #: Name für Menschen — wird der Themen-Name im Konto.
    name: str
    #: Suchmuster über Titel und Zusammenfassung (case-insensitiv).
    pattern: str
    #: Die Themen-Beschreibung: Sie wandert in den Wächter-Prompt, also
    #: konkret, mit den Wörtern, die in den Vorlagen wirklich stehen.
    description: str
    #: Kurze Einordnung für die Anzeige (wie ``context`` der Entitäten).
    context: str


CITY_TOPICS: tuple[CityTopic, ...] = (
    CityTopic(
        "stadium", "Stadion-Neubau",
        r"stadion",
        "Neubau des Fußballstadions an der Maastrichter Straße in Oldenburg: "
        "Planung, Kosten und Finanzierung, Verkehrs- und Lärmkonzept, "
        "Bebauungsplan und Umfeld, Berichte und Beschlüsse dazu.",
        "Maastrichter Straße, Kosten, Verkehr",
    ),
    CityTopic(
        "schools", "Schulen",
        r"(?<!hoch)(?<!fach)schul(?!d)(?!ung)|gymnasium|oberschule|\bigs\b|schulzentrum",
        "Schulen in Oldenburg: Neubau, Sanierung und Erweiterung von "
        "Schulgebäuden, Schulentwicklungsplanung, Ganztagsbetreuung, "
        "Ausstattung und Schulbezirke.",
        "Neubau, Sanierung, Ganztag",
    ),
    CityTopic(
        "green", "Bäume und Stadtgrün",
        r"\bbaum\b|\bbäume|\bbaumschutz|\bbaumfäll|\bbaumpflanz|stadtgrün|grünfläche|grünanlage|\bparks?\b|parkanlage",
        "Bäume und Grünflächen in Oldenburg: Baumschutz und Baumfällungen, "
        "Neupflanzungen, Parks und Grünanlagen, Pflege und Umgestaltung "
        "öffentlicher Grünflächen.",
        "Baumschutz, Parks, Neupflanzungen",
    ),
    CityTopic(
        "housing", "Wohnungsbau",
        r"wohnungsbau|wohnraum|bezahlbar|sozialwohnung|mietwohnung|wohnungsmarkt|wohnbau",
        "Wohnungsbau und bezahlbarer Wohnraum in Oldenburg: neue Wohngebiete, "
        "geförderter und sozialer Wohnungsbau, Quoten für preisgünstige "
        "Wohnungen, Wohnungsmarkt und Nachverdichtung.",
        "Bezahlbarer Wohnraum, neue Wohngebiete",
    ),
    CityTopic(
        "climate", "Klimaschutz und Klimaanpassung",
        r"klimaschutz|klimaanpassung|klimaneutral|klimaplan|klimawandel|hitze|starkregen|hochwasser",
        "Klimaschutz und Klimaanpassung in Oldenburg: Klimaschutzmaßnahmen "
        "und Klimaneutralität, Hitzevorsorge, Starkregen- und "
        "Hochwasserschutz, Entsiegelung und Förderprogramme.",
        "Klimaneutralität, Hitze, Starkregen",
    ),
    CityTopic(
        "cycling", "Radverkehr",
        r"radverkehr|radweg|fahrrad|radschnell|radroute|radfahr|radstation",
        "Radverkehr in Oldenburg: neue und sanierte Radwege, Fahrradstraßen, "
        "Radschnellwege, Fahrradabstellanlagen und Radverkehrsplanung.",
        "Radwege, Fahrradstraßen, Abstellanlagen",
    ),
    CityTopic(
        "downtown", "Innenstadt",
        r"innenstadt|fußgängerzone|citymanagement|city-management|schlossplatz|lange straße|achternstraße",
        "Innenstadt von Oldenburg: Umgestaltung von Plätzen und Straßen, "
        "Fußgängerzone, Einzelhandel und Leerstand, Aufenthaltsqualität, "
        "Veranstaltungen und Verkehr in der City.",
        "Plätze, Einzelhandel, Fußgängerzone",
    ),
    CityTopic(
        "heat", "Wärmewende und Solar",
        r"wärmeplan|fernwärme|photovoltaik|\bsolar|wärmewende|wärmenetz|energetische sanierung",
        "Wärmewende und erneuerbare Energie in Oldenburg: kommunale "
        "Wärmeplanung, Fernwärme und Wärmenetze, Photovoltaik auf "
        "städtischen Dächern, energetische Sanierung städtischer Gebäude.",
        "Wärmeplanung, Fernwärme, Photovoltaik",
    ),
    CityTopic(
        "transit", "Bus und Bahn",
        r"öpnv|buslinie|busverkehr|stadtbahn|\bvwg\b|nahverkehr|bahnhof|haltestelle|bushaltestelle",
        "Bus und Bahn in Oldenburg: Nahverkehrsplan, Buslinien und Takte, "
        "Haltestellen, Verkehr und Wasser GmbH (VWG), Bahnhof und "
        "Bahnübergänge, Tickets und Tarife.",
        "Buslinien, Haltestellen, Bahnhof",
    ),
    CityTopic(
        "childcare", "Kitas",
        r"\bkita|kindertagesst|\bkrippe|kindergarten|kindertagespflege",
        "Kindertagesstätten in Oldenburg: neue Kitas und Krippenplätze, "
        "Kita-Bedarfsplanung, Gebühren und Beiträge, Träger und "
        "Personal in der Kinderbetreuung.",
        "Plätze, Gebühren, Neubauten",
    ),
    CityTopic(
        "digital", "Digitale Verwaltung",
        r"digitalisierung|digitale verwaltung|onlinedienst|online-dienst|open data|bürgerservice|smart city",
        "Digitale Verwaltung in Oldenburg: Online-Dienste und Bürgerservice, "
        "Digitalisierung der Stadtverwaltung und der Schulen, Open Data und "
        "Smart-City-Vorhaben.",
        "Online-Dienste, Bürgerservice",
    ),
    CityTopic(
        "pools", "Schwimmbäder",
        r"schwimmbad|hallenbad|freibad|schwimmhalle|\bbäder|olantis|dobbenbad|nordbad|\bbad\b",
        "Schwimmbäder in Oldenburg: Hallen- und Freibäder, OLantis Huntebad, "
        "Sanierung und Betrieb durch die Bäderbetriebsgesellschaft, "
        "Eintrittspreise, Öffnungszeiten und Schwimmkurse.",
        "Hallenbäder, Freibäder, Bäderbetrieb",
    ),
    CityTopic(
        "sports", "Sporthallen und Sportplätze",
        r"sporthalle|sportplatz|sportplätze|sportstätte|sportanlage|turnhalle|kunstrasen|sportförder",
        "Sporthallen und Sportplätze in Oldenburg: Sanierung und Neubau von "
        "Hallen und Plätzen, Vergabe an Vereine, Kunstrasen und die "
        "Richtlinien der Sportförderung.",
        "Hallen, Plätze, Vereinsförderung",
    ),
    CityTopic(
        "culture", "Theater, Museen und Kultur",
        r"theater|museum|museen|bibliothek|kulturförder|kulturbüro|kulturzentrum|musikschule|nachtkultur",
        "Kultur in Oldenburg: Staatstheater, Museen und Stadtbibliothek, "
        "Kulturförderung, Kulturzentren und Musikschule, Nachtkultur und "
        "Veranstaltungsorte.",
        "Theater, Museen, Kulturförderung",
    ),
    CityTopic(
        "youth", "Kinder, Jugend und Spielplätze",
        r"jugendzentrum|jugendtreff|jugendarbeit|jugendförder|spielplatz|spielplätze|spielgerät|jugendparlament",
        "Kinder und Jugend in Oldenburg: Spielplätze und Spielgeräte, "
        "Jugendzentren und Jugendtreffs, Jugendarbeit und Jugendhilfe, "
        "Beteiligung junger Menschen.",
        "Spielplätze, Jugendzentren, Jugendarbeit",
    ),
    CityTopic(
        "fire", "Feuerwehr und Rettungsdienst",
        r"feuerwehr|rettungsdienst|brandschutz|katastrophenschutz|rettungswache|feuerwache",
        "Feuerwehr und Rettungsdienst in Oldenburg: Feuerwachen und "
        "Fahrzeuge, Freiwillige Feuerwehren, Rettungsdienst und "
        "Rettungswachen, Brand- und Katastrophenschutz.",
        "Feuerwachen, Fahrzeuge, Rettungsdienst",
    ),
    CityTopic(
        "airfield", "Fliegerhorst",
        r"fliegerhorst",
        "Das Gelände des ehemaligen Fliegerhorsts in Oldenburg: "
        "Konversion zum neuen Quartier, Bebauungspläne, Sanierungsgebiet, "
        "Gewerbe, Wohnen und Altlasten-Monitoring.",
        "Neues Quartier, Gewerbe, Sanierungsgebiet",
    ),
    CityTopic(
        "waste", "Müll und Sauberkeit",
        r"abfallwirtschaft|abfallgebühr|müllgebühr|\bmüll|straßenreinigung|sauberkeit|recycling|wertstoff|\bgbo\b",
        "Müll und Sauberkeit in Oldenburg: Abfallwirtschaft und "
        "Abfallgebühren, Wertstoffhöfe und Recycling, Straßenreinigung, "
        "Sauberkeit im öffentlichen Raum.",
        "Abfallgebühren, Recycling, Straßenreinigung",
    ),
    CityTopic(
        "roads", "Straßen und Brücken",
        r"straßenbau|straßensanierung|straßenausbau|straßenunterhaltung|brückenbau|\bbrücke|sanierung der straße|ausbaubeitrag|fahrbahn",
        "Straßen und Brücken in Oldenburg: Straßenbau und -sanierung, "
        "Kreuzungsumbauten, Brückenneubau und -sanierung, "
        "Ausbaubeiträge und Verkehrsführung bei Baustellen.",
        "Straßenbau, Brücken, Kreuzungen",
    ),
    CityTopic(
        "business", "Wirtschaft und Gewerbe",
        r"gewerbegebiet|gewerbefläche|wirtschaftsförder|ansiedlung|einzelhandel|gewerbeansiedlung",
        "Wirtschaft und Gewerbe in Oldenburg: Gewerbegebiete und "
        "-flächen, Wirtschaftsförderung, Unternehmensansiedlungen und "
        "Einzelhandel.",
        "Gewerbegebiete, Ansiedlungen, Einzelhandel",
    ),
)

#: Die Reihenfolge der Anzeige. Die Reihenfolge von ``CITY_TOPICS`` bleibt davon
#: unberührt: Sie entscheidet bei ``match_question``, welches Thema eine Frage
#: bekommt, die mehrere trifft. ``tests/test_stadtthemen.py`` hält fest, dass
#: hier jeder Schlüssel genau einmal steht.
ANZEIGE: tuple[str, ...] = (
    "cycling", "stadium", "pools", "green", "childcare", "culture",
    "transit", "sports", "housing", "fire", "downtown", "airfield",
    "schools", "youth", "climate", "waste", "heat", "roads",
    "business", "digital",
)

_COMPILED = {t.key: re.compile(t.pattern, re.IGNORECASE) for t in CITY_TOPICS}


def match_question(frage: str) -> CityTopic | None:
    """Das kuratierte Stadtthema, zu dem eine FRAGE passt — oder ``None``.

    Dieselben Muster wie ``count_topics``, nur auf den Text einer Nutzerfrage
    statt auf einen Beschluss. Das ist die Brücke von „ich habe etwas gefragt"
    zu „das Produkt meldet sich bei mir": Wer nach dem Radverkehr fragt,
    bekommt das fertige Thema *Radverkehr* mit einer Beschreibung, die am
    Bestand kalibriert ist — statt eines Formulars, in das er eine Frage
    tippt, die als Thema nicht funktioniert.

    **Wie oft das trifft, ist gemessen, nicht geschätzt:** An den fünfzehn
    echten Fragen vom 08.09.2026 traf es bei vieren (Radverkehr, Kitas,
    Stadion, Klimaschutz). Haushalt und „Sport" allgemein haben bewusst
    kein kuratiertes Thema — sie waren als Dauerabo zu laut (s. Modul-Kopf). Für den Rest bleibt der vorbefüllte Weg über das
    Themen-Formular; dieser hier ist die Abkürzung, nicht der einzige Weg.

    Bei mehreren Treffern gewinnt der ERSTE aus ``CITY_TOPICS``: Die Liste ist
    von Hand sortiert, und eine Frage, die „Schule" und „Kita" enthält, ist
    eher eine Schulfrage — geraten wäre hier schlechter als eine feste Regel,
    die man nachlesen kann.
    """
    text = (frage or "").strip()
    if len(text) < 4:
        return None
    for t in CITY_TOPICS:
        if _COMPILED[t.key].search(text):
            return t
    return None


def bild_key(name: str | None) -> str | None:
    """Der Schlüssel des kuratierten Stadtthemas, das so heißt — oder ``None``.

    Daran hängt das Bild (``public/themen/<key>.webp``) auf der Themen-Karte:
    Ein Thema, das über die Kachel im Assistenten angelegt wurde, trägt genau
    den Namen der Registry. Gleichheit statt Wortsuche, weil ein selbst
    getipptes „Schulwegsicherheit" kein Stadtthema „Schulen" ist und sein Bild
    nicht tragen soll.
    """
    wanted = (name or "").strip().casefold()
    return next((t.key for t in CITY_TOPICS if t.name.casefold() == wanted), None)


def count_topics(texts: list[str]) -> dict[str, int]:
    """Wie viele der Texte jedes Thema trifft — ein Text zählt je Thema einmal."""
    counts = {t.key: 0 for t in CITY_TOPICS}
    for text in texts:
        for key, rx in _COMPILED.items():
            if rx.search(text):
                counts[key] += 1
    return counts


def city_topic_suggestions(council, today: date | None = None,
                           minimum: int = MIN_DECISIONS) -> list[dict]:
    """Die Stadtthemen mit Substanz, in der Reihenfolge von ``ANZEIGE``.

    Jeder Eintrag hat die Form der Entitäts-Vorschläge (``name``,
    ``description``, ``context``, ``n``) plus ``key`` und ``months`` — dieselbe
    Kachel in der Oberfläche, ein Klick legt das Thema an.
    """
    cutoff = ((today or date.today()) - timedelta(days=WINDOW_DAYS)).isoformat()
    counts = count_topics(council.decision_texts_since(cutoff))
    out = [{
        "key": t.key, "name": t.name, "description": t.description,
        "context": t.context, "n": counts[t.key], "months": round(WINDOW_DAYS / 30.4),
    } for t in CITY_TOPICS if counts[t.key] >= minimum]
    out.sort(key=lambda e: ANZEIGE.index(e["key"]) if e["key"] in ANZEIGE else len(ANZEIGE))
    return out
