"""Die Wahlergebnisse als Baustein für „Frag den Rat".

Am 28.09.2026 fragte jemand „Wie sind die Sitzverteilung nach der
Ratswahl?" und bekam: „geht aus den Unterlagen nicht hervor". Die Antwort
stand zwei Wochen nach der Wahl auf ``/wahlen`` — aber die KI-Frage las nur
Ratsbeschlüsse, und in denen steht ein Wahlergebnis erst, wenn der neue Rat
getagt hat (Auswertung der echten Fragen, 11.10.2026).

**Gerechnet wird nichts neu.** Der Baustein nimmt dieselben eingefrorenen
Stände wie der Wahlabend und der Rückblick (``archive.night`` für die
Ratswahl, die Darstellung des Votemanagers für die OB-Wahlen). Gerundet wird
genau einmal, hier, auf eine Stelle (``rounding.half_up``).

Er liegt in der App-Schicht, weil die Wahl dort liegt; ``council/qa.py``
erkennt nur am Wortlaut, ob er gebraucht wird (``qa.wahlfrage``), und bekommt
ihn fertig gereicht — derselbe Weg wie die Geschäftsordnung.
"""
from __future__ import annotations

import json
import logging

from . import archive, elections, mayor
from .elected import term_start
from .rounding import half_up

_log = logging.getLogger("ratslotse.web.wahlabend")


def _pct(v: float | None) -> str:
    return "–" if v is None else f"{half_up(v):.1f} %".replace(".", ",")


def _sitze(n: int) -> str:
    return f"{n} Sitz" if n == 1 else f"{n} Sitze"


def _datum(iso: str | None) -> str:
    if not iso or len(iso) < 10:
        return iso or "?"
    return f"{iso[8:10]}.{iso[5:7]}.{iso[:4]}"


def _stand(wahl: elections.Election) -> str:
    return ("amtliches Endergebnis" if archive.result_status(wahl) == "amtlich"
            else "vorläufiges Ergebnis")


def _ratswahl(wahl: elections.Election) -> list[str]:
    nacht = archive.night(wahl.slug)
    if not nacht or not nacht.get("parties"):
        return []
    t = nacht.get("totals") or {}
    zeilen = [f"- Ratswahl am {_datum(wahl.date)} ({_stand(wahl)}): {wahl.seats} Sitze, "
              f"Wahlbeteiligung {_pct(t.get('turnout_pct'))}. Sitze und Stimmenanteile "
              f"(in Klammern die Ratswahl davor):"]
    for p in sorted(nacht["parties"], key=lambda p: (-(p.get("seats") or 0),
                                                     -(p.get("share_pct") or 0))):
        if not p.get("seats") and not p.get("seats_previous"):
            continue
        vorher = []
        if p.get("seats_previous") is not None:
            vorher.append(_sitze(p["seats_previous"]))
        if p.get("share_previous_pct") is not None:
            vorher.append(_pct(p["share_previous_pct"]))
        zeilen.append(f"  - {p['short']}: {_sitze(p.get('seats') or 0)}, "
                      f"{_pct(p.get('share_pct'))}"
                      + (f" ({', '.join(vorher)})" if vorher else " (kein Vergleichswert)"))
    zeilen.append(f"- Die Wahlperiode des neuen Rats beginnt am {_datum(term_start(wahl.date))}; "
                  "bis dahin ist der bisherige Rat im Amt. Wie sich Fraktionen und Gruppen "
                  "bilden, steht in diesem Ergebnis nicht.")
    return zeilen


def _ob(wahl: elections.Election) -> list[str]:
    ordner = wahl.archive_folder
    datei = ordner / "praesentation-ob.json" if ordner else None
    if datei is None or not datei.is_file():
        return []
    stand = mayor.parse(json.loads(datei.read_text(encoding="utf-8")), mayor.candidates(wahl))
    if stand is None or not stand.candidates:
        return []
    kand = sorted(stand.candidates, key=lambda c: -(c.votes or 0))
    titel = "Stichwahl um das Amt des Oberbürgermeisters" if wahl.first_round else \
        "Wahl des Oberbürgermeisters"
    zeilen = [f"- {titel} am {_datum(wahl.date)} ({_stand(wahl)}, Wahlbeteiligung "
              f"{_pct(stand.turnout_pct)}): " + "; ".join(
                  f"{c.name}{f' ({c.party})' if getattr(c, 'party', None) else ''} {_pct(c.share_pct)}"
                  for c in kand[:6])]
    if stand.runoff:
        namen = [c.name for c in kand if c.slug in stand.runoff]
        zeilen.append(f"  - Niemand erreichte mehr als die Hälfte; in die Stichwahl gingen "
                      f"{' und '.join(namen)}.")
    elif wahl.first_round or (kand[0].share_pct or 0) > 50:
        zeilen.append(f"  - Gewählt ist {kand[0].name}.")
    return zeilen


def prompt_block() -> str:
    """Alle Wahlen mit eingefrorenem Ergebnis, jüngste zuerst — ``""`` ohne."""
    zeilen: list[str] = []
    for wahl in sorted(elections.all().values(), key=lambda w: w.date or "", reverse=True):
        if wahl.kind == "council" and not archive.verfuegbar(wahl):
            continue
        try:
            teil = _ratswahl(wahl) if wahl.kind == "council" else _ob(wahl)
        except Exception:  # noqa: BLE001 — ein Ergebnis, nicht die Antwort
            _log.exception("Wahl-Baustein: „%s“ nicht lesbar", wahl.slug)
            continue
        zeilen += teil
    if not zeilen:
        return ""
    return ("\nWAHLERGEBNISSE IN OLDENBURG (aus den eingefrorenen Ergebnissen des Votemanagers\n"
            "der Stadt, dieselben Zahlen wie unter ratslotse.de/wahlen). Nie mit [id]:\n"
            + "\n".join(zeilen) + "\n")
