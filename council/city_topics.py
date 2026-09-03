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
Meldungen im Monat.
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
)

_COMPILED = {t.key: re.compile(t.pattern, re.IGNORECASE) for t in CITY_TOPICS}


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
    """Die Stadtthemen mit Substanz, die aktivsten zuerst.

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
    out.sort(key=lambda e: -e["n"])
    return out
