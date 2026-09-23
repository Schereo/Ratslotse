#!/usr/bin/env python3
"""Baut ``eval/cases_speeches.json``: echte Protokollabschnitte mit Rednerliste.

    python eval/build_speeches_cases.py            # schreibt die Fälle
    python eval/build_speeches_cases.py --zeigen   # dazu jede Abweichung zum Nachlesen

**Woher die Erwartung kommt.** Nicht aus der alten Modellausgabe allein. Je
Abschnitt gibt es zwei unabhängige Zählungen der Redner*innen:

1. **Das Protokoll selbst.** Oldenburger Niederschriften leiten jeden Beitrag
   gleich ein: „Ratsfrau Hufeland schließt sich … an", „Stadtrat Denckmann
   ergänzt …", „Frau Wilken teilt mit …". Ein Muster über Anrede, Name und
   Verb zählt diese Einleitungen (:data:`WECHSEL`).
2. **Die gespeicherten Wortbeiträge** (``council_speeches``, Gemini 2.5 Flash
   im Cron), dem Abschnitt über die TOP-Nummer zugeordnet.

**Pflicht** ist, wen BEIDE nennen. Wen nur eine Seite nennt, der steht als
**erlaubt** im Fall: Ihn zu nennen oder wegzulassen kostet nichts. Das sind
fast immer Sitzungsleitungen („Die Ausschussvorsitzende Averbeck erkundigt
sich …" — Frage oder Formalie?) und Vortragende („Frau Molnár und Herr
Schwierin berichten anhand einer Präsentation"). Mit ``--zeigen`` steht jede
Abweichung mit ihrem Satz da; nachgelesen am 23.09.2026, siehe
``eval/run_speeches.py``.

**Eine Falle der PDF-Textschicht:** Die Niederschriften brechen den ersten
Buchstaben eines Absatzes gern in eine eigene Zeile („R\\natsfrau Hufeland").
Das Muster sieht den Text deshalb mit geflickten Zeilen; das MODELL bekommt
den Rohtext, wie im Betrieb.
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from collections import Counter
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
FAELLE = WURZEL / "eval" / "cases_speeches.json"

#: (Sitzung, TOP-Nummern) — je Fall zwei bis drei aufeinanderfolgende Punkte,
#: damit die Zuordnung zum Punkt mitgeprüft wird. Ausgewählt über acht
#: Gremien, Rat und Fachausschüsse; nur Abschnitte, in denen das Muster
#: überhaupt greift (Niederschriften der Planungsausschüsse sind anders
#: gesetzt und bleiben draußen, bis jemand ihr Muster baut).
AUSWAHL: tuple[tuple[int, tuple[str, ...]], ...] = (
    (4695, ("5", "6.9")),
    (4695, ("7.1", "7.2")),
    (4695, ("10.1", "11.1", "12.1")),
    (4687, ("6.1",)),
    (4687, ("6.3", "6.4")),
    (4650, ("3.2", "4")),
    (4650, ("10.1", "10.2")),
    (4598, ("5", "6", "7.1")),
    (4592, ("5", "6")),
    (4592, ("8.1", "8.2")),
    (4631, ("9.3", "9.4", "9.5")),
    (4631, ("9.6",)),
    (4664, ("11.5", "11.6", "11.7")),
    (4591, ("7", "8.1")),
    (4671, ("7", "8")),
    (4678, ("5", "9")),
)

_ROLLE = (r"(?:Ratsherr|Ratsfrau|Ratsmitglied|Stadtrat|Stadträtin|Oberbürgermeister|"
          r"Bürgermeisterin|Bürgermeister|Erste Stadträtin|Frau|Herr|"
          r"(?:Die|Der) (?:stellvertretende )?(?:Ausschussvorsitzende|Ratsvorsitzende|Vorsitzende)|"
          r"Beratendes Mitglied|Ausschussmitglied)")
_NAME = (r"((?:Dr\.\s*|Prof\.\s*)*(?:von\s+|van\s+|de\s+)?[A-ZÄÖÜ][\wäöüß]+"
         r"(?:-[A-ZÄÖÜ][\wäöüß]+)?)")
#: Eine Beitrags-Einleitung: Satzanfang, Anrede, Name, (Fraktion), kleines Wort.
WECHSEL = re.compile(r"(?:^|(?<=[.!?:“\"]\s)|(?<=\n))\s*" + _ROLLE + r"\s+" + _NAME
                     + r"\s+(?:\([^)]*\)\s+)?(?:[a-zäöü]\w+)")
_KOPF = re.compile(r"(?m)^\s*zu\s+((?:[ÖN]\s*)?\d+(?:\.\d+)*)\b")
_TITEL = {"dr", "prof", "herr", "frau", "ratsherr", "ratsfrau", "stadtrat", "stadträtin"}


def falte(s: str | None) -> str:
    return re.sub(r"[^a-zäöüß]", "", (s or "").lower())


def nachname(sprecher: str | None) -> str:
    """„Dr. Chahine" → „chahine", „von Sydow" → „sydow", „Schober-Stockmann" →
    „schoberstockmann". Dieselbe Faltung für Erwartung und Ausgabe."""
    teile = [t for t in re.split(r"\s+", (sprecher or "").strip())
             if t and t.rstrip(".").lower() not in _TITEL]
    return falte(teile[-1]) if teile else ""


def top_nummer(top: str | None) -> str | None:
    m = re.match(r"\s*(?:TOP\s*)?(?:[ÖN]\s+)?(\d+(?:\.\d+)*)", str(top or ""), re.I)
    return m.group(1) if m else None


def flicken(text: str) -> str:
    return re.sub(r"(?m)^([A-ZÄÖÜ])\n(?=[a-zäöü])", r"\1", text)


def abschnitte(raw: str) -> dict[str, str]:
    koepfe = [(m.start(), m.group(1)) for m in _KOPF.finditer(raw)]
    return {nr: raw[s:(koepfe[i + 1][0] if i + 1 < len(koepfe) else len(raw))]
            for i, (s, nr) in enumerate(koepfe)}


def bauen(con: sqlite3.Connection, zeigen: bool = False) -> list[dict]:
    faelle = []
    for ksinr, tops in AUSWAHL:
        raw = con.execute("SELECT raw_text FROM council_protocols WHERE ksinr = ?",
                          (ksinr,)).fetchone()[0]
        sitzung = con.execute("SELECT committee, session_date FROM council_sessions WHERE ksinr = ?",
                              (ksinr,)).fetchone()
        teile = abschnitte(raw)
        fehlt = [t for t in tops if t not in teile]
        if fehlt:
            raise SystemExit(f"{ksinr}: TOP {fehlt} nicht im Protokoll gefunden")
        text = "".join(teile[t] for t in tops)
        muster: Counter = Counter()
        saetze: dict[str, str] = {}
        for t in tops:
            for m in WECHSEL.finditer(flicken(teile[t])):
                n = nachname(m.group(1))
                muster[n] += 1
                saetze.setdefault(n, " ".join(m.group(0).split()))
        gespeichert: Counter = Counter(
            nachname(sp) for top, sp in con.execute(
                "SELECT top, speaker FROM council_speeches WHERE ksinr = ? ORDER BY position",
                (ksinr,))
            if sp and top_nummer(top) in tops and nachname(sp))
        erwartet: dict[str, list[int]] = {}
        for n in sorted(set(muster) | set(gespeichert)):
            a, b = muster.get(n, 0), gespeichert.get(n, 0)
            pflicht = a > 0 and b > 0
            erwartet[n] = [min(a, b) if pflicht else 0, max(a, b)]
            if zeigen and not pflicht:
                quelle = "nur Muster" if a else "nur gespeichert"
                print(f"  {ksinr} {'+'.join(tops)}: {n} ({quelle}, {a}/{b}) — "
                      f"{saetze.get(n, '(kein Einleitungssatz)')[:110]}")
        faelle.append({
            "id": f"{ksinr}-{'+'.join(tops)}",
            "ksinr": ksinr, "gremium": sitzung[0], "datum": sitzung[1],
            "tops": list(tops),
            # [mindestens, höchstens] Beiträge je Nachname; 0 = erlaubt, nicht Pflicht.
            "erwartet": erwartet,
            "text": text,
        })
    return faelle


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=str(WURZEL / "data" / "council.sqlite"))
    ap.add_argument("--zeigen", action="store_true")
    a = ap.parse_args()
    con = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True)
    faelle = bauen(con, zeigen=a.zeigen)
    FAELLE.write_text(json.dumps(faelle, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    pflicht = sum(1 for f in faelle for lo, _ in f["erwartet"].values() if lo)
    print(f"{len(faelle)} Fälle, {sum(len(f['text']) for f in faelle)} Zeichen, "
          f"{pflicht} Pflicht-Redner*innen → {FAELLE.relative_to(WURZEL)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
