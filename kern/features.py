"""Welche Features an sind — die eine Stelle, an der das steht.

**Wozu.** Ein Feature fährt heute in dem Moment nach Prod, in dem sein PR
gemergt wird. Wer etwas Größeres baut, hat drei Möglichkeiten, und alle drei
sind unangenehm: den Zweig wochenlang offen halten (und mit jedem Tag
schwerer mergen), auf `feature.ratslotse.de` ausweichen (wo niemand
mitliest), oder es einfach live schalten und hoffen.

Ein Schalter trennt **Ausliefern** von **Freischalten**. Der Code fährt
fertig nach `main`, bleibt aber dunkel, bis jemand ihn anschaltet — und lässt
sich in derselben Minute wieder ausschalten, ohne Revert und ohne Deploy.

**Warum über ``/api/app-config`` und nicht über ``NEXT_PUBLIC_``.** Eine
``NEXT_PUBLIC_``-Variable wird zur BAUZEIT einkompiliert; sie umzulegen heißt,
neu zu bauen und neu zu deployen — also genau das, was der Schalter ersparen
soll. Dieselbe Falle hat den CARTO-Kartenschlüssel erwischt (s. ``CLAUDE.md``).
``/api/app-config`` fragt jede Oberfläche ohnehin vor allem anderen ab, das
Web wie die native App; ein Neustart des Dienstes genügt.

**Was ein Schalter NICHT ist.** Er ist keine Rechteprüfung. Wer eine Fläche
vor bestimmten Konten schützen will, nimmt ein Recht (``kern/roles.py``) — das
Backend setzt es durch. Ein Feature-Schalter regelt, ob etwas **schon so
weit** ist, nicht, **wer** es sehen darf. Deshalb reicht es, wenn die
Oberfläche ihn liest: Was hinter ihm liegt, ist ohnehin unfertig und nicht
geheim. Braucht ein halbfertiges Feature zusätzlich Schutz, gehört ein Recht
davor, nicht ein zweiter Schalter.

**Eintragen, benutzen, wieder entfernen.** Ein Schalter ist eine Schuld wie
eine Ausnahme im Linter: Sobald das Feature steht, fliegt er raus und der Code
bleibt. ``tests/test_features.py`` hält beide Richtungen — kein Schalter ohne
Nutzung, keine Nutzung ohne Schalter.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Feature:
    key: str
    #: Ein Satz: Was schaltet dieser Schalter frei? Menschentext.
    description: str
    #: Woran man erkennt, dass er weg kann. Ohne das bleibt jeder Schalter für
    #: immer stehen — „vielleicht braucht ihn noch jemand".
    fertig_wenn: str


#: Alle Schalter, die es gibt. Ein Name, der hier nicht steht, ist ein
#: Tippfehler — und ein Tippfehler in einem Schalter schaltet lautlos NIE ein.
#:
#: **Absichtlich leer.** Die Mechanik steht bereit; der erste Schalter kommt
#: mit dem ersten Feature, das ihn braucht. Ein Beispiel-Eintrag „auf Vorrat"
#: wäre schon die Schuld, gegen die `fertig_wenn` geschrieben ist.
#:
#: So sieht ein Eintrag aus::
#:
#:     "neue-suche": Feature(
#:         key="neue-suche",
#:         description="Die überarbeitete Beschluss-Suche mit Facetten.",
#:         fertig_wenn="Die Stadion-Fragen liefern mindestens so gute Treffer "
#:                     "wie vorher (tests/…/eval).",
#:     ),
FEATURES: dict[str, Feature] = {
    "akten-suche": Feature(
        key="akten-suche",
        description="„Frag den Rat“ liest zu den besten Treffern die ganze Akte des "
                    "Vorgangs mit — die neuesten Beschlüsse, die passenden Wortbeiträge "
                    "samt jüngster Aussagen der Verwaltung, die neuesten "
                    "Pressemitteilungen (council/akte_suche.py, docs/plan-akte.md).",
        fertig_wenn="Phase 3 hat ihr Tor erreicht (Gold „Frag den Rat“ +10 Pp und "
                    "mindestens drei Fälle mehr bestanden, Retrieval ohne Rückschritt) "
                    "und lag zwei Wochen auf Prod an; dann ist die Akte der Normalweg.",
    ),
    "akten-zeitleiste": Feature(
        key="akten-zeitleiste",
        description="„Frag den Rat“ bekommt den Vorgang als datierte Zeitleiste (Block "
                    "„AKTE“) samt angekündigter Stationen, erzählt ihn in zeitlicher Folge "
                    "und nennt den aktuellen Stand; fehlt er, hängt der Server ihn an "
                    "(Plan „Akte“, Phase 4). Unter der Antwort stehen der Verlauf als "
                    "Zeitleiste und die Eckdaten (Abstimmung, Betrag, Stand, nächster "
                    "Termin). Wirkt nur zusammen mit `akten-suche`.",
        fertig_wenn="Phase 4 hat ihr Tor erreicht (Gold „Frag den Rat“: +10 Pp bei "
                    "„Fakt genannt, wenn Material vorhanden“ gegenüber Phase 3, Fakten-Eval "
                    "ohne Zunahme) und lag zwei Wochen auf Prod an.",
    ),
    "mein-viertel": Feature(
        key="mein-viertel",
        description="„Mein Viertel“: Was sich in einem Ortsbereich in den nächsten "
                    "Jahren ändert — Vorhaben aus Beschlüssen, gebündelt und geprüft.",
        fertig_wenn="Das Vorhaben-Register läuft einige Wochen ohne „Gehört nicht "
                    "hierher“-Treffer auf Prod, und Tim hat die Tafel freigegeben.",
    ),
    "andere-staedte": Feature(
        key="andere-staedte",
        description="„In anderen Städten“: Auf Beschluss-Seiten, was andere Städte "
                    "zu derselben Sache beantragt, beraten oder beschlossen haben — aus "
                    "deren Ratsinformationssystemen (council/cities).",
        fertig_wenn="Der Block lag vier Wochen auf dev, und mindestens zwei Nutzer*innen "
                    "mit Mandat haben die Treffer als brauchbar bestätigt.",
    ),
    "ideen-anderswo": Feature(
        key="ideen-anderswo",
        description="„Ideen aus anderen Städten“: je Themenfeld, was andere Räte "
                    "beantragt oder beschlossen haben und Oldenburg fehlt — mit Urteil, Belegen "
                    "und dem Weg zum Original (council/cities, Annotator `fit`).",
        fertig_wenn="Tim hat zwei Themenfelder durchgesehen und die Urteile für "
                    "tragfähig erklärt. Bis dahin ist die Seite auf dev sichtbar "
                    "und auf Prod nicht.",
    ),
    "wahlabend": Feature(
        key="wahlabend",
        description="Der Wahlabend zur Ratswahl am 13.09.2026: Auszählungsstand, "
                    "Sitze je Liste und Wahlbereich, wer nach NKWG gerade drin wäre "
                    "— aus den Open-Data-CSVs des Votemanagers der Stadt.",
        # Seit 10/2026 regelt dieser Schalter NICHT mehr, wie laut die Wahl ist —
        # das tut der Kalender (`elections.prominent`: Hinweis auf Heute und
        # Streifen auf der Startseite nur eine Woche vor bis drei Tage nach dem
        # Wahlschluss). Er ist nur noch der Notaus für den ganzen Bereich:
        # /wahlen, /wahlabend, Stichwahl, Wahlkarte in Mein Viertel.
        fertig_wenn="Die Wahlseiten sind ein dauerhafter Bereich (/wahlen, Reiter "
                    "„Wahlen“ in der Analyse); die Prominenz kommt aus der Wahl-Phase. "
                    "Er kann weg, sobald keine App-Fassung im Store mehr `wahlabend` "
                    "abfragt (Karten-Ebene in CityMapView, Mehr-Zeile) — dann alle "
                    "Abfragen entfernen und APP_MIN_BUILD nachziehen.",
    ),
    "lotti-assistentin": Feature(
        key="lotti-assistentin",
        description="Lotti als Assistentin: ein Knopf auf jeder Seite, der erklärt, was "
                    "gerade auf dem Bildschirm steht — die Seite, ein angeklicktes "
                    "Element oder markierter Text — und Ratsfragen an „Frag den Rat“ "
                    "weiterreicht.",
        fertig_wenn="Zwei Wochen auf dev; die Probe-Aufrufe aus docs/plan-lotti-assistentin.md "
                    "kosten im Mittel unter 0,3 Cent; der Eval (eval/run_assistant.py) ist "
                    "grün, die sechs Injektions-Fälle eingeschlossen; Tim hat den Knopf "
                    "freigegeben.",
    ),
    "lotti-anstupser": Feature(
        key="lotti-anstupser",
        description="Lotti klopft selten von selbst an („Hast du eine Frage zu dem, "
                    "was du siehst?“) — auf Leseseiten, nach 45 s Lesezeit, höchstens "
                    "einmal am Tag und dreimal in 30 Tagen.",
        fertig_wenn="Vier Wochen gemessen (Admin-Panel, Reiter „Lotti“): Liegt die "
                    "Ja-Quote unter 5 %, wird er seltener oder abgeschafft — Tims "
                    "Entscheidung. Bleibt er, fliegt der Schalter raus.",
    ),
    "lotti-selbstpruefung": Feature(
        key="lotti-selbstpruefung",
        description="Lottis Selbstprüfung als stille Stichprobe: Ein Anteil der Erklärungen "
                    "(COUNCIL_ASSISTANT_PRUEFER_ANTEIL, Vorgabe 10 %) wird NACH der Antwort "
                    "geprüft — erst ohne Modell, dann von einem Prüfer-Modell einer anderen "
                    "Familie; das Urteil zählt der Admin-Reiter „Lotti“ (council/self_check.py). "
                    "Niemand wartet darauf, nichts wird ersetzt.",
        fertig_wenn="Vier Wochen Stichprobe auf dev: Zeigt der Admin-Reiter Seiten mit "
                    "auffällig vielen Beanstandungen, gehen sie als Aufgaben an die Kontext- "
                    "und Regelarbeit; dann entscheidet Tim, ob die Stichprobe dauerhaft läuft "
                    "(Schalter raus) oder wegfällt (docs/lotti-selbstpruefung.md).",
    ),
    "lotti-werkzeuge": Feature(
        key="lotti-werkzeuge",
        description="Lotti darf nachschlagen: Zeitreihen, Haushaltszahlen anderer Seiten, "
                    "Ratsbeschlüsse, und rechnen nur mit belegten Zahlen — höchstens drei "
                    "Runden je Antwort, nur lesend (council/lotti_werkzeuge.py).",
        fertig_wenn="Die mehrstufigen Fälle der Fakten-Eval (haushalt/mehrstufig) liegen "
                    "deutlich über dem Stand ohne Werkzeuge, die übrigen Haushaltsfälle und "
                    "die Wartezeit nicht schlechter — dann auf Prod an und Schalter raus.",
    ),
    "neuer-rat": Feature(
        key="neuer-rat",
        description="Der gewählte Rat vor seiner ersten Sitzung: die Liste der 52 "
                    "Gewählten aus dem Wahlergebnis, dazu eine Personen-Seite für "
                    "alle, die noch in keinem Protokoll stehen.",
        fertig_wenn="Tim hat die Liste nach dem amtlichen Endergebnis freigegeben. "
                    "Nach der konstituierenden Sitzung (02.11.2026) prüfen, ob die "
                    "Vorab-Liste noch gebraucht wird.",
    ),
    "tippspiel": Feature(
        key="tippspiel",
        description="Das Tippspiel zu den Wahlen 2026: zur Ratswahl am 13.09. Sitze je "
                    "Liste, zur OB-Stichwahl am 27.09. die Prozente der beiden Kandidaturen, "
                    "jeweils dazu die Wahlbeteiligung; Live-Vergleich und Scoreboard "
                    "(docs/plan-tippspiel-ratswahl.md) — ohne Konto, per QR-Link.",
        # Seit 10/2026: Die Einladungen zum Tippen hängen an der Wahl-Phase
        # (nur, solange die Wahl prominent ist bzw. in /wahlen noch nicht vorbei),
        # die Scoreboards bleiben als Rückblick erreichbar.
        fertig_wenn="Die Scoreboards 2026 sind Rückblick, Einladungen kommen nur noch "
                    "aus der Wahl-Phase. Er kann weg, wenn das Tippspiel zu einer "
                    "künftigen Wahl ohne Freischaltung starten darf — dann die "
                    "Abfragen in /tipp und /api/tipp entfernen.",
    ),
}


def aktive(roh: str | None = None) -> list[str]:
    """Die eingeschalteten Schalter, aus ``FEATURE_FLAGS``.

    Kommagetrennt, Leerraum egal: ``FEATURE_FLAGS=haushalt-labor, neue-suche``.
    ``FEATURE_FLAGS=*`` heißt: alle — die Vorgabe für dev.
    Ein Name, den ``FEATURES`` nicht kennt, wird **verworfen** und nicht
    durchgereicht — sonst schaltete ein Tippfehler in der ``.env`` etwas frei,
    das es nicht gibt, und niemand sähe den Unterschied zu „ist eben aus".

    Die Reihenfolge folgt der Registry, nicht der ``.env``: So ist die Antwort
    von ``/api/app-config`` stabil und taugt als Cache-Schlüssel.
    """
    wert = os.environ.get("FEATURE_FLAGS", "") if roh is None else roh
    gewuenscht = {t.strip() for t in wert.split(",") if t.strip()}
    # ``*`` schaltet ALLE Schalter an — für dev, wo jedes Feature sichtbar
    # sein soll, sobald es gemergt ist (Tim, 07.09.2026), statt dass jeder PR
    # einen Eintrag in der ``.env`` der VM nachzieht. Auf Prod bleibt die
    # Liste explizit; ein ``*`` dort wäre eine Entscheidung, kein Versehen.
    if "*" in gewuenscht:
        return list(FEATURES)
    return [k for k in FEATURES if k in gewuenscht]


def an(key: str, roh: str | None = None) -> bool:
    """Ist dieser Schalter an? Für den Gebrauch im Backend."""
    return key in aktive(roh)
