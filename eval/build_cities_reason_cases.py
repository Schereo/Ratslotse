#!/usr/bin/env python3
"""Aus echten Niederschrift-Abschnitten Fälle für ``run_cities_reason.py`` bauen.

Der Prüfstand misst zwei Dinge automatisch, und beide brauchen eine **von Hand
gesetzte** Erwartung:

- ``has_reason``: Steht im Abschnitt eine Begründung — ein Argument, ein
  Einwand, eine Wortmeldung — oder nur ein Ergebnis? Daran hängt die harte
  Zusage „keine erfundenen Begründungen".
- ``vote``: Das Abstimmungsergebnis im Wortlaut, oder ``null``.

Dieses Skript **zieht die Stichprobe und schlägt beides vor**; die Vorschläge
kommen aus Regeln, nicht aus einem Modell (ein Golden Set, das ein Modell
gesetzt hat, misst das Modell an sich selbst — die Lehre aus PR 10). Wer die
Fälle benutzt, geht sie durch und korrigiert, was die Regel danebengreift.

```bash
python eval/build_cities_reason_cases.py --anzahl 40
python eval/run_cities_reason.py
```

**Gezogen wird geschichtet**: je Stadt gleich viele, und innerhalb einer Stadt
die Hälfte mit und die Hälfte ohne erkennbare Begründung. Eine zufällige
Stichprobe bestünde zu vier Fünfteln aus „einstimmig beschlossen" — und
prüfte damit genau den Fall nicht, für den es den Annotator gibt.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL))

from council.cities.protocol import SPLITTER_VERSION  # noqa: E402
from council.cities.store import CitiesStore  # noqa: E402

ZIEL = WURZEL / "eval" / "cases_cities_reason.json"

#: Wörter, an denen eine Begründung im Text hängt. Grob und mit Absicht: Der
#: Vorschlag soll die Handdurchsicht abkürzen, nicht ersetzen.
#:
#: **Keine Wortgrenze am Ende** — deutsche Verben beugen sich („erläutert",
#: „begründete"), und ein `\b` dahinter lässt jede gebeugte Form durchfallen.
#: Am Anfang bleibt sie, sonst trifft „bedenken" auch „Bedenkenträger".
_GRUND = re.compile(
    r"\b(weil |da hierfür|da die |begründ|kritisier|verwies |argumentier|"
    r"gibt zu bedenken|gab zu bedenken|ohne Bedenken|Einwand|wandte ein|"
    r"befürwort|sprach sich|spricht sich|äußert sich skeptisch|"
    r"hielt .{0,14}für|hält .{0,14}für|lehnt .{0,14}ab|lehnte .{0,14}ab)", re.I)

#: Das Abstimmungsergebnis, wie es in den vier Dialekten dasteht. Nur
#: EINDEUTIGE Formen: „einstimmig über" ist ein abgeschnittener Halbsatz und
#: taugt nicht als Maßstab — ein Prüfstand mit unscharfen Erwartungen misst
#: das Modell an seinem eigenen Rauschen.
_VOTE = re.compile(
    r"(?:Abstimmungsergebnis|Abstimmung)\s*:?\s*\n?\s*([^\n]{3,80})"
    r"|(\d+\s*(?:dafür|Ja-Stimmen)\s*[,/]?\s*\d+\s*(?:dagegen|Nein-Stimmen)[^\n]{0,40})"
    r"|(\d+\s*/\s*\d+\s*/\s*\d+)"
    r"|\b(einstimmig beschlossen|einstimmig angenommen|einstimmig zugestimmt|"
    r"mehrheitlich beschlossen|mehrheitlich angenommen|mehrheitlich abgelehnt|"
    r"ungeändert beschlossen|geändert beschlossen|einstimmig)\b", re.I)


def vote_aus(text: str) -> str | None:
    m = _VOTE.search(text)
    if not m:
        return None
    roh = " ".join(next((g for g in m.groups() if g), "").split()).strip(" .:,;")
    # Ein Fetzen wie „einstimmig über" hilft niemandem — lieber nichts.
    if len(roh) < 5 or roh.lower().endswith((" über", " mit", " und", " zu", " der", " die")):
        return None
    return roh[:80] or None


def main() -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--anzahl", type=int, default=40)
    ap.add_argument("--samen", type=int, default=7, help="damit die Auswahl wiederholbar ist")
    a = ap.parse_args()

    pfad = Path(os.environ.get("CITIES_DB", "data/cities.sqlite"))
    if not pfad.exists():
        print(f"Keine Städte-Datenbank unter {pfad}.")
        return 2

    store = CitiesStore(pfad)
    try:
        zeilen = store._conn.execute(
            "SELECT s.agenda_item_id, s.number, s.title, s.text, "
            "       m.body_id, m.start, m.name AS meeting_name, "
            "       o.name AS organization_name "
            "FROM protocol_sections s "
            "JOIN meetings m ON m.id = s.meeting_id "
            "LEFT JOIN organizations o ON o.id = m.organization_id "
            "WHERE s.splitter=? AND length(s.text) > 200",
            (SPLITTER_VERSION,)).fetchall()
    finally:
        store.close()
    if not zeilen:
        print("Keine geschnittenen Abschnitte da — erst `--stage fetch` und "
              "`pipeline.split_protocols` laufen lassen.")
        return 2

    je_stadt: dict[str, list[dict]] = {}
    for r in zeilen:
        je_stadt.setdefault(r["body_id"], []).append(dict(r))

    rnd = random.Random(a.samen)
    faelle: list[dict] = []
    je = max(1, a.anzahl // max(1, len(je_stadt)))
    for stadt, kandidaten in sorted(je_stadt.items()):
        mit = [k for k in kandidaten if _GRUND.search(k["text"])]
        ohne = [k for k in kandidaten if not _GRUND.search(k["text"])]
        rnd.shuffle(mit); rnd.shuffle(ohne)
        for k in (mit[:je // 2 + je % 2] + ohne[:je // 2]):
            faelle.append({
                "agenda_item_id": k["agenda_item_id"],
                "body": stadt,
                "organization": k.get("organization_name") or k.get("meeting_name") or "",
                "date": (k.get("start") or "")[:10],
                "item": f"{k['number']} {k['title']}".strip(),
                "section": k["text"],
                # --- ab hier von Hand prüfen ---
                "has_reason": bool(_GRUND.search(k["text"])),
                "vote": vote_aus(k["text"]),
                "geprueft": False,
            })
    rnd.shuffle(faelle)
    ZIEL.write_text(json.dumps(faelle[:a.anzahl], ensure_ascii=False, indent=1),
                    encoding="utf-8")
    mit = sum(1 for f in faelle[:a.anzahl] if f["has_reason"])
    print(f"{ZIEL}: {min(len(faelle), a.anzahl)} Fälle aus {len(je_stadt)} Städten, "
          f"{mit} davon mit vermuteter Begründung.")
    print("Jetzt durchgehen: `has_reason` und `vote` prüfen, `geprueft` auf true "
          "setzen. Erst dann misst der Prüfstand etwas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
