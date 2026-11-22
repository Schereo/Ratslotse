"""Welche Bereiche ein Konto an einem Tag besucht hat — grob, ohne Seiten.

**Warum es das gibt.** Das Admin-Panel zeigte je Konto nur einen Balken mit
der Zahl der API-Anfragen pro Tag. Daraus ließ sich weder lesen, wie lange
jemand da war, noch was er ungefähr gemacht hat (Tims Befund 09.11.2026):
Eine Seite löst ein Dutzend Anfragen aus, und „61" hieß damit „ein paar
Seiten", nicht „61 Mal etwas getan". Tim hat sich für diese Zählung
entschieden; die Datenschutzerklärung nennt sie.

**Was gezählt wird:** je Konto und Tag die BEREICHE aus der Liste unten
(Fragen, Beschlüsse, Karte, Haushalt …), als Feature ``area:<key>`` in
``user_activity``. Dazu zählt ``app.deps`` die aktiven Minuten.

**Was NICHT gezählt wird:** keine einzelne Seite, keine Kennung aus der Query
(welcher Beschluss, welche Suche), keine Uhrzeit. Der Pfad geht erst durch
``kern.seitenaufrufe.normalisieren`` (Positivliste, Query fällt weg) und dann
durch diese Liste; was hier nicht steht, wird nicht gezählt.
"""
from __future__ import annotations

from kern import seitenaufrufe

#: Feature-Präfix in ``user_activity``.
PREFIX = "area:"

#: (Schlüssel, Anzeige, Seitenmuster aus ``kern.seitenaufrufe``). Die
#: Reihenfolge ist die der Anzeige. Ein Muster gehört zu höchstens einem
#: Bereich (``tests/test_activity_areas.py``).
AREAS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("today", "Heute", ("/dashboard",)),
    ("questions", "Fragen", ("/fragen",)),
    ("search", "Suche", ("/council", "/council?tab=decisions", "/council?tab=themen")),
    ("decisions", "Beschlüsse", ("/council/decision", "/council/thema")),
    ("sessions", "Sitzungen", ("/council?tab=sessions", "/council/sitzung")),
    ("analysis", "Analyse", ("/council?tab=analysis", "/council/plan")),
    ("people", "Personen", ("/council/person", "/council/neuer-rat")),
    ("map", "Karte", ("/karte", "/council/ort")),
    ("district", "Mein Viertel", ("/viertel",)),
    ("ideas", "Ideen anderer Städte", ("/council/ideen", "/council/ideen/bewegung")),
    ("budget", "Haushalt", tuple(r for r in sorted(seitenaufrufe.ROUTEN) if r.startswith("/haushalt"))),
    ("topics", "Themen", ("/topics",)),
    ("subscriptions", "Abos", ("/abos",)),
    ("bookmarks", "Merkliste", ("/bookmarks",)),
    ("quiz", "Quiz", ("/quiz", "/quiz/stats")),
    ("elections", "Wahlen", tuple(r for r in sorted(seitenaufrufe.ROUTEN)
                                  if r.startswith(("/wahl", "/stichwahl", "/kommunalwahl"))
                                  or r in ("/tipp", "/tipp/live"))),
    ("account", "Konto", ("/account",)),
    ("admin", "Admin", ("/admin", "/tipp/admin")),
)

_BY_ROUTE: dict[str, str] = {r: key for key, _label, routes in AREAS for r in routes}
LABELS: dict[str, str] = {key: label for key, label, _routes in AREAS}


def area_for(route: str | None) -> str | None:
    """Der Bereich eines gemeldeten Pfads — oder ``None``, wenn er zu keinem
    gehört (öffentliche Seiten, Unbekanntes)."""
    return _BY_ROUTE.get(seitenaufrufe.normalisieren(route))


def ordered(keys: set[str]) -> list[dict[str, str]]:
    """Bereiche in Anzeige-Reihenfolge, mit Beschriftung."""
    return [{"key": key, "label": label} for key, label, _routes in AREAS if key in keys]
