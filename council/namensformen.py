"""Namensformen, die zu **einer** Person gehören.

Manche Menschen erscheinen in den Quellen unter zwei Namensformen — „Tim
Harms" und „Tim Ebbeke Harms" stehen in den Anwesenheitslisten desselben
Gremiums, „Jan Freede" und „Jan Reinder Freede" in denen des Schulausschusses.
Mehr sagen die Daten nicht: **warum** eine Quelle die Form wechselt, steht
nirgends, und deshalb behauptet es hier auch niemand.

Ohne diese Zuordnung zerfällt eine Person in zwei Profile: zwei Einträge im
Verzeichnis, zwei Personen-Seiten mit je einem Teil der Sitzungen, kein Badge
in den KI-Antworten (bei zwei gleich benannten Kandidaten gibt der Matcher
absichtlich auf) — und die ältere Form verliert obendrein ihre Stammdaten,
weil das Ratsinformationssystem nur die heutige Schreibweise führt.

Gepflegte Liste statt automatischer Regel
-----------------------------------------
Erkennen ließen sich die Fälle: gleicher Vorname, gleicher Nachname, ein
Namensteil mehr. Gemessen am Bestand (17.08.2026) findet diese Bedingung acht
Paare — darunter „Jan-Eike Meyer" (Gast der HTI Betriebs GmbH) und „Jan-Martin
Meyer" (Ratsmitglied der Gruppe Linke/Piraten), also **zwei verschiedene
Menschen**. Eine falsch zusammengeführte Gruppe wäre die Behauptung, zwei
reale Personen seien eine; sie fiele niemandem auf, weil sie wie ein normales
Profil aussieht. Deshalb entscheidet hier ein Mensch, und
:func:`verdachtsfaelle` liefert nur die Vorschlagsliste
(``scripts/check_namensformen.py``).

Die jüngste Fundstelle entscheidet
----------------------------------
Angezeigt wird die Form, die zuletzt in einer Anwesenheitsliste stand — **nie**
die längere, nie die häufigere, nie eine Annahme darüber, welche Form die
„richtige" ist. Das ist die einzige Regel, die ohne Ursachenwissen auskommt,
und sie zieht von selbst mit, wenn eine Quelle die Form erneut wechselt.

Gegenprobe am Bestand: Für die beiden Ratsmitglieder unten führt das
Ratsinformationssystem seine Stammdaten (``council_persons``, ein Eintrag je
Mandat) unter genau der Form, die auch die jüngste Fundstelle nennt.
"""
from __future__ import annotations

from collections.abc import Mapping

#: Namensformen einer Person, je Zeile eine Gruppe. Slugs wie
#: :meth:`council.store.CouncilStore._person_slug` sie bildet.
#:
#: Aufgenommen wird nur, was der Bestand für **eine** Person belegt. Geprüft
#: wurde je Gruppe: dieselbe Fraktion bzw. dieselbe Rolle, Auftritte in
#: denselben Gremien, **keine gemeinsame Anwesenheitsliste** (zwei Menschen
#: säßen irgendwann einmal zusammen im Rat) — und bei Ratsmitgliedern zusätzlich
#: ein einziges, durchgehendes Mandat im Ratsinformationssystem, das beide
#: Zeiträume überspannt.
GRUPPEN: tuple[tuple[str, ...], ...] = (
    # 133 + 2 Sitzungen, Grüne, dieselben Gremien, keine gemeinsame
    # Anwesenheitsliste; Ratsmandat seit 2021-11-01, offen.
    ("tim-harms", "tim-ebbeke-harms"),
    # 30 + 31 Sitzungen als Verwaltung, beide im Schul- und
    # Jugendhilfeausschuss, keine gemeinsame Anwesenheitsliste.
    ("jan-freede", "jan-reinder-freede"),
    # 183 + 31 Sitzungen, Grüne, sechs gemeinsame Gremien (darunter der Rat),
    # keine gemeinsame Anwesenheitsliste; Ratsmandat seit 2016-11-01, offen.
    # Hier ist die kürzere Form die jüngste — die Regel oben löst auch das
    # richtig, weil sie nur auf das Datum sieht.
    ("christine-wolff", "christine-berta-wolff"),
    # Geprüft am Bestand 21.08.2026 (Tims Befund, dass dieselbe Person zweimal
    # im Verzeichnis steht). Die vier folgenden Gruppen kommen aus derselben
    # Prüfung, decken aber einen Fall ab, den `verdachtsfaelle` bewusst nicht
    # vorschlägt: eine Form OHNE Vornamen bzw. mit Initiale (die Bedingung dort
    # verlangt zwei Namensteile auf beiden Seiten). Je Gruppe geprüft:
    # dieselbe Rolle, dasselbe Gremium, keine gemeinsame Anwesenheitsliste.
    #
    # 158 + 1 Sitzung, beide SPD, Ausschuss für Finanzen und Beteiligungen;
    # Ratsmandat seit 2021-11-01, offen. Die kurze Form steht an genau einem
    # Tag (13.05.2025).
    ("thomas-klein", "klein"),
    # 17 + 3 Sitzungen als Verwaltung/Beschäftigtenvertretung, dasselbe
    # Gremium; „U." ist die Initiale von Ulrich.
    ("ulrich-helpertz", "u-helpertz"),
    # 2 + 2 Sitzungen als Verwaltung, dasselbe Gremium, getrennte Zeiträume
    # (2018/19 als „Dr. Götte", 2021–2024 mit Vornamen).
    ("walter-goette", "goette"),
    # 1 + 1 Sitzung als Verwaltung, dasselbe Gremium, 2019 ohne, 2024 mit
    # Vornamen.
    ("tim-streit", "streit"),
)

_ZU_GRUPPE: dict[str, tuple[str, ...]] = {s: g for g in GRUPPEN for s in g}


def gruppe(slug: str) -> tuple[str, ...]:
    """Alle Namensformen der Person zu ``slug`` — leer, wenn keine geführt wird."""
    return _ZU_GRUPPE.get(slug, ())


def kanonisch(fundstellen: Mapping[str, tuple[str, int]]) -> dict[str, str]:
    """``{Namensform → kanonische Form}`` für jede geführte Gruppe.

    ``fundstellen`` = ``{slug: (Datum der jüngsten Fundstelle, Anzahl)}``.
    Zurück kommen nur die **abweichenden** Formen (die kanonische zeigt nicht
    auf sich selbst), damit ein leeres Ergebnis heißt: nichts zusammenzuführen.

    Es entscheidet das Datum. Anzahl und Slug stehen nur im Schlüssel, damit
    zwei Formen mit demselben jüngsten Datum (zwei Gremien an einem Tag) nicht
    von der Laune der Sortierung abhängen — sie kommen nie zum Zuge, solange
    die Daten sich unterscheiden.

    Formen, die im Bestand (noch) gar nicht vorkommen, zeigen auf die
    kanonische Form mit: Ein alter Link soll auch dann ankommen, wenn seine
    Namensform aus den Daten verschwunden ist.
    """
    aus: dict[str, str] = {}
    for gr in GRUPPEN:
        belegt = [s for s in gr if fundstellen.get(s)]
        if not belegt:
            continue
        kanon = max(belegt, key=lambda s: (fundstellen[s][0], fundstellen[s][1], s))
        for s in gr:
            if s != kanon:
                aus[s] = kanon
    return aus


def verdachtsfaelle(sitzungen: Mapping[str, set]) -> list[dict]:
    """Paare von Namensformen, die **eine** Person sein könnten — Vorschläge,
    keine Zusammenführung.

    ``sitzungen`` = ``{slug: {ksinr, …}}`` aus den Anwesenheitslisten.

    Zwei Bedingungen, beide notwendig:

    1. **Gleicher Nachname**, dazu gleicher Vorname *oder* alle Namensteile der
       einen Form in der anderen enthalten (ein Namensteil mehr).
    2. **Keine gemeinsame Anwesenheitsliste.** Wer je zusammen in einer Sitzung
       saß, ist nicht dieselbe Person — das schließt Namensvettern aus, die
       nebeneinander im Rat sitzen.

    Was durchkommt, ist damit *nicht* geprüft: Gäste verschiedener Firmen
    teilen sich Nachnamen, ohne sich je zu begegnen. Die Entscheidung trifft
    ein Mensch und trägt sie in :data:`GRUPPEN` ein.
    """
    slugs = sorted(sitzungen)
    teile = {s: s.split("-") for s in slugs}
    aus: list[dict] = []
    for i, a in enumerate(slugs):
        for b in slugs[i + 1:]:
            ta, tb = teile[a], teile[b]
            if ta[-1] != tb[-1] or len(ta) < 2 or len(tb) < 2:
                continue
            gleicher_vorname = ta[0] == tb[0]
            teilmenge = set(ta) <= set(tb) or set(tb) <= set(ta)
            if not (gleicher_vorname or teilmenge):
                continue
            gemeinsam = sitzungen[a] & sitzungen[b]
            if gemeinsam:
                continue
            aus.append({"a": a, "b": b,
                        "gleicher_vorname": gleicher_vorname,
                        "teilmenge": teilmenge,
                        "gefuehrt": _ZU_GRUPPE.get(a) is not None
                                    and _ZU_GRUPPE.get(a) == _ZU_GRUPPE.get(b)})
    return aus
