"""Welche Städte im Speicher liegen — als Code, wie ``city_topics.py``.

Ein Eintrag ist damit im Pull Request sichtbar, mit Diff und Historie. Die
Endpunkte sind am 07.09.2026 gemessen worden: **keiner der drei
niedersächsischen steht in einem öffentlichen Verzeichnis** (``dev.oparl.org``
kennt Braunschweig nur unter dem alten Host), sie antworten trotzdem.

Faustregel für weitere Städte: ALLRIS-4-Instanzen laufen fast immer unter
``<stadt>.sitzung-online.de``, der Endpunkt ist ``/oparl/system``.
"""
from __future__ import annotations

from dataclasses import dataclass

#: Die Dialekte, für die es einen Adapter gibt.
DIALECTS = ("allris4", "allris4_html", "allris_classic", "session",
            "rubin", "oldenburg")


@dataclass(frozen=True)
class BodySpec:
    id: str
    name: str
    state: str
    dialect: str
    system_url: str | None = None
    #: Potsdam führt zwei Bodies („Landeshauptstadt Potsdam" und „Ortsbeirat");
    #: Index 0 ist überall die Stadt selbst.
    body_index: int = 0
    #: Ab wann geerntet wird. Weiter zurück geht immer, kostet aber Abrufe.
    since: str = "2023-01-01"
    #: Nur aktive Städte holt der Cron. Die übrigen sind gemessen erreichbar
    #: und warten darauf, dass jemand sie einschaltet.
    active: bool = True
    #: Holt der Lauf die PDF-Bytes? Aus für Quellen, deren Text schon
    #: vorliegt — Oldenburgs Vorlagentexte stehen längst in der
    #: Rats-Datenbank, sie ein zweites Mal herunterzuladen belastet nur
    #: unser eigenes Ratsinformationssystem (gemessen: 706 Abrufe,
    #: zwölf Minuten, für nichts).
    fetch_files: bool = True
    notes: str = ""


BODIES: dict[str, BodySpec] = {
    # --- Oldenburg selbst: Stadt Nummer null, damit jeder Vergleich
    #     symmetrisch ist („was fehlt uns?" und „was haben wir, was andere
    #     nicht haben?" sind dieselbe Rechnung mit vertauschten Rollen).
    "oldenburg": BodySpec(
        "oldenburg", "Oldenburg (Oldb)", "NI", "oldenburg", None,
        since="2018-01-01", fetch_files=False,
        notes="Kein OParl (SessionNet ohne Modul). Der Adapter liest council.sqlite."),

    # --- Ring 1: gleiches Kommunalverfassungsrecht (NKomVG)
    "osnabrueck": BodySpec(
        "osnabrueck", "Osnabrück", "NI", "allris4",
        "https://www.osnabrueck.sitzung-online.de/oparl/system",
        notes="CC BY 4.0. 19.543 Papiere. Ergebnis an 46 % der Tagesordnungspunkte."),
    "braunschweig": BodySpec(
        "braunschweig", "Braunschweig", "NI", "allris4",
        "https://www.ratsinfo.braunschweig.sitzung-online.de/oparl/system",
        notes="49.483 Papiere seit 1997. 128 von 267 Gremien sind Stadtbezirksräte."),

    # --- Ring 2: strukturell ähnlich, anderes Landesrecht
    "muenster": BodySpec(
        "muenster", "Münster", "NW", "session",
        "https://oparl.stadt-muenster.de/system",
        notes="Kein mainFile — Dokumente hängen unter auxiliaryFile."),
    "potsdam": BodySpec(
        "potsdam", "Potsdam", "BB", "allris4",
        "https://www.potsdam.sitzung-online.de/oparl/system",
        notes="Zwei Bodies; Index 0 ist die Landeshauptstadt."),
    "magdeburg": BodySpec(
        "magdeburg", "Magdeburg", "ST", "session",
        "https://ratsinfo.magdeburg.de/oparl/system",
        notes="DL-DE-Zero 2.0. Die Datei-URLs der Schnittstelle antworten 404; "
              "der Adapter schreibt sie auf getfile.asp um."),

    # --- Ring 3: gemessen erreichbar, noch nicht eingeschaltet
    "leipzig": BodySpec("leipzig", "Leipzig", "SN", "allris4",
                        "https://www.leipzig.sitzung-online.de/oparl/system",
                        active=False, notes="CC BY 4.0, 49.116 Papiere."),
    "bonn": BodySpec("bonn", "Bonn", "NW", "allris4",
                     "https://www.bonn.sitzung-online.de/oparl/system", active=False),
    "koeln": BodySpec("koeln", "Köln", "NW", "session",
                      "https://buergerinfo.stadt-koeln.de/oparl/system",
                      active=False, notes="Ergebnis an 72 % der Tagesordnungspunkte."),
    "dresden": BodySpec("dresden", "Dresden", "SN", "session",
                        "https://oparl.dresden.de/system",
                        active=False, notes="DL-DE-Zero 2.0. Langsam — Zeitlimit hochsetzen."),
    "wuppertal": BodySpec("wuppertal", "Wuppertal", "NW", "session",
                          "https://oparl.wuppertal.de/oparl/system", active=False),
    "duesseldorf": BodySpec("duesseldorf", "Düsseldorf", "NW", "session",
                            "https://ris-oparl.itk-rheinland.de/Oparl/system", active=False),
    "freiburg": BodySpec("freiburg", "Freiburg", "BW", "rubin",
                         "https://ris.freiburg.de/oparl/system",
                         active=False, notes="OParl 1.0: Volltext liegt im Dateiobjekt."),
    "darmstadt": BodySpec("darmstadt", "Darmstadt", "HE", "rubin",
                          "https://darmstadt.gremien.info/oparl/system", active=False),
    # Die einzigen zwei weiteren niedersächsischen Städte mit einer
    # OParl-Schnittstelle, die antwortet — von 340 geprüften Kommunen ab 5.000
    # Einwohnern (Erhebung 10.09.2026). Beide ALLRIS 4, also derselbe Adapter
    # wie Osnabrück und Braunschweig, beide CC BY 4.0.
    "langenhagen": BodySpec(
        "langenhagen", "Langenhagen", "NI", "allris4",
        "https://www.langenhagen.sitzung-online.de/oparl/system",
        active=False,
        notes="CC BY 4.0. Niederschriften an 4 von 8 geprüften Sitzungen — "
              "die einzige weitere NI-Stadt, die zum „Warum“ etwas beiträgt."),
    "peine": BodySpec(
        "peine", "Peine", "NI", "allris4",
        "https://ratsinfo.stadt-peine.de/public/oparl/system",
        active=False,
        notes="CC BY 4.0, 2.579 Vorlagen seit 2024. Keine Niederschriften an "
              "den Sitzungen. Die Schnittstelle liegt unter /public/."),

    # --- ALLRIS 4 ohne OParl: dieselbe Anwendung, Modul aus oder kaputt.
    #     Gelesen wird dann die Oberflaeche (Dialekt ``allris4_html``); die
    #     Adresse ist die Wurzel der Anwendung, nicht ein ``/oparl/system``.
    "laatzen": BodySpec(
        "laatzen", "Laatzen", "NI", "allris4_html",
        "https://ratsinfo.laatzen.de/public",
        active=False,
        notes="OParl antwortet mit HTTP 500. Gemessen 10.09.2026: 8 Sitzungen, "
              "154 Punkte, 74 Vorlagen, 241 Dateien, 83 Beratungen."),
    # **Der Domainname sagt nichts über das Produkt.** „buergerinfo" ist
    # sonst die Handschrift von Somacos; gemessen läuft dort ALLRIS 4
    # („ALLRIS - Sitzungen Kalender" auf si010). Dieselbe Falle wie
    # ``sitzung-online.de``, das nicht Somacos gehört, sondern CC e-gov.
    "lueneburg": BodySpec(
        "lueneburg", "Lüneburg", "NI", "allris4_html",
        "https://buergerinfo.stadt.lueneburg.de/public",
        active=False,
        notes="OParl antwortet mit HTTP 500. Verlinkt von "
              "hansestadt-lueneburg.de/rathaus/politik."),
    # **Der Host steht NICHT nach dem üblichen Muster.** Weder
    # ``ratsinfo.wolfsburg.de`` noch ``wolfsburg.sitzung-online.de`` lösen
    # überhaupt auf; die Stadt verlinkt von wolfsburg.de/politik auf
    # ``ratsinfob.stadt.wolfsburg.de``, ohne ``/public``. Ein geratener Host
    # hat am 10.09.2026 eine Stunde gekostet und zu dem Schluss geführt, die
    # Anwendung sei kaputt — sie ist es nicht.
    # --- ALLRIS classic: die ältere `.asp`-Bauform. Eigener Dialekt, weil sie
    #     mit ALLRIS 4 den Hersteller teilt und keine einzige Adresse.
    #     Der Host stammt von hildesheim.de (Schritt 0 im Rezept): Er heißt
    #     `stadt-hildesheim.de`, nicht `hildesheim.de` — und `bi.`, `ris.`
    #     und `allris.hildesheim.de` lösen alle auf dieselbe Platzhalter-IP
    #     auf, beweisen also nichts.
    "hildesheim": BodySpec(
        "hildesheim", "Hildesheim", "NI", "allris_classic",
        "https://www.stadt-hildesheim.de/allris",
        since="2018-01-01", active=False, fetch_files=False,
        notes="Kein OParl. Der Vorlagentext steht IN der Seite, es gibt keine "
              "Anlagen — deshalb fetch_files=False und Text über inline_texts. "
              "Zu jedem beratenen Punkt gibt es einen Auszug (to020.asp) mit "
              "Wortprotokoll und Beschluss - das Warum ohne PDF-Schnitt."),

    "wolfsburg": BodySpec(
        "wolfsburg", "Wolfsburg", "NI", "allris4_html",
        "https://ratsinfob.stadt.wolfsburg.de",
        active=False,
        notes="CC BY 4.0 (laut /oparl/system). OParl ist eingebaut, liefert "
              "aber nur /system — bodies und alles dahinter antworten mit "
              "HTTP 500. Gelesen wird deshalb die Oberfläche. 652 Sitzungen "
              "im Index (si018), gemessen 10.09.2026."),
}


def active_bodies() -> list[BodySpec]:
    return [b for b in BODIES.values() if b.active]


def get(body_id: str) -> BodySpec:
    if body_id not in BODIES:
        raise KeyError(f"unbekannte Stadt {body_id!r}; bekannt: {sorted(BODIES)}")
    return BODIES[body_id]
