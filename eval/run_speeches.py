#!/usr/bin/env python3
"""Wortbeiträge: Findet das Modell alle Redner*innen eines Protokollabschnitts?

    python eval/run_speeches.py                  # heutiges Modell (COUNCIL_WORTBEITRAG_MODEL)
    python eval/pruefstand.py --suite wortbeitraege --modell google/gemini-3.1-flash-lite --laeufe 2

**Was gemessen wird.** 16 echte Abschnitte aus Niederschriften von acht
Gremien (``eval/cases_speeches.json``, gebaut von
``eval/build_speeches_cases.py``), je zwei bis drei Tagesordnungspunkte, durch
denselben Weg wie im Cron (``council.wortbeitraege.extract_wortbeitraege``:
Fenster, zwei Versuche, Dubletten-Abgleich).

**Hauptkennzahl: F1 über die Beiträge je Person.** Je Nachname steht im Fall
eine Spanne [mindestens, höchstens] — das Protokoll-Muster und die
gespeicherte Extraktion zählen denselben Redner nicht immer gleich oft (eine
Rückfrage im selben Absatz: ein Beitrag oder zwei?). Innerhalb der Spanne
ist alles richtig; darunter fehlen Beiträge, darüber sind zu viele. So misst
die eine Zahl Namen UND Anzahl, und wer eine Person ganz übersieht, verliert
alle ihre Beiträge.

**Harter Befund: ein Name, der im Abschnitt gar nicht vorkommt.** Der Prompt
sagt „nichts erraten, nichts erfinden"; ein Nachname, der im Text nicht
steht, ist erfunden oder aus dem Weltwissen ergänzt. Das lässt sich
buchstäblich prüfen, ohne Modell als Richter.

**Nebenkennzahlen:** die Zuordnung zum Tagesordnungspunkt (Anteil der
Beiträge bekannter Redner*innen, deren ``top`` mit einer Nummer des
Abschnitts beginnt) und die Fraktion ohne Beleg (``party`` gesetzt, aber
weder die Bezeichnung noch ihr Kürzel steht im Abschnitt).

**Nachgelesen am 23.09.2026.** Muster und gespeicherte Extraktion nennen
156 von 158 Redner*innen übereinstimmend; die zwei Abweichungen sind eine
Präsentation („Frau Molnár und Herr Schwierin berichten …") und eine
Sitzungsleitung, die an etwas erinnert. Beide stehen als „erlaubt" im Fall.
In 19 Fällen weicht die Anzahl ab, die Spanne deckt beide Lesarten.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL))

from eval.build_speeches_cases import FAELLE, falte, nachname, top_nummer  # noqa: E402


def lade() -> list[dict]:
    if not FAELLE.exists():
        raise SystemExit(f"{FAELLE} fehlt: python eval/build_speeches_cases.py")
    return json.loads(FAELLE.read_text(encoding="utf-8"))


def bewerten(fall: dict, beitraege: list[dict]) -> dict:
    """Ein Fall gegen die Ausgabe — rein, ohne Modell (offline testbar)."""
    text_gefaltet = falte(fall["text"])
    gezaehlt: Counter = Counter()
    erfunden: list[str] = []
    ohne_beleg: list[str] = []
    top_ok = top_alle = 0
    for b in beitraege:
        n = nachname(b.get("speaker"))
        if not n:
            continue
        gezaehlt[n] += 1
        if n not in text_gefaltet:
            erfunden.append(str(b.get("speaker")))
        partei = falte(b.get("party"))
        if partei and partei not in text_gefaltet:
            ohne_beleg.append(f"{b.get('speaker')}: {b.get('party')}")
        if n in fall["erwartet"]:
            top_alle += 1
            top_ok += top_nummer(b.get("top")) in fall["tops"]
    tp = fp = fn = 0
    for n, (lo, hi) in fall["erwartet"].items():
        p = gezaehlt.get(n, 0)
        if lo:
            tp += min(p, hi)
            fn += max(0, lo - p)
        fp += max(0, p - hi)
    fp += sum(p for n, p in gezaehlt.items() if n not in fall["erwartet"])
    pflicht = {n for n, (lo, _) in fall["erwartet"].items() if lo}
    return {"id": fall["id"], "tp": tp, "fp": fp, "fn": fn,
            "verpasst": sorted(pflicht - set(gezaehlt)),
            "fremd": sorted(set(gezaehlt) - set(fall["erwartet"])),
            "erfunden": erfunden, "partei_ohne_beleg": ohne_beleg,
            "top_ok": top_ok, "top_alle": top_alle, "beitraege": len(beitraege)}


def zusammenfassen(zeilen: list[dict]) -> dict:
    tp = sum(z["tp"] for z in zeilen)
    fp = sum(z["fp"] for z in zeilen)
    fn = sum(z["fn"] for z in zeilen)
    bewertet = [z for z in zeilen if "fehler" not in z]
    top_alle = sum(z.get("top_alle", 0) for z in bewertet)
    return {
        "n_cases": len(zeilen),
        "f1": round(2 * tp / (2 * tp + fp + fn), 4) if tp else 0.0,
        "precision": round(tp / (tp + fp), 4) if tp + fp else None,
        "recall": round(tp / (tp + fn), 4) if tp + fn else None,
        "erfunden": sum(len(z.get("erfunden", [])) for z in bewertet),
        "partei_ohne_beleg": sum(len(z.get("partei_ohne_beleg", [])) for z in bewertet),
        "top_richtig": round(sum(z.get("top_ok", 0) for z in bewertet) / top_alle, 4) if top_alle else None,
        "fehlgeschlagen": len(zeilen) - len(bewertet),
        "faelle": zeilen,
    }


def ein_lauf(faelle: list[dict], modell: str | None = None) -> dict:
    from council import wortbeitraege
    zeilen = []
    for fall in faelle:
        try:
            beitraege = wortbeitraege.extract_wortbeitraege(fall["text"], modell or wortbeitraege.MODEL)
        except Exception as e:  # noqa: BLE001 — ein Fall, nicht der Lauf
            # Alle Pflicht-Beiträge gelten als verpasst: Im Cron bliebe das
            # Protokoll offen, auf der Seite fehlten sie genauso.
            fn = sum(lo for lo, _ in fall["erwartet"].values())
            zeilen.append({"id": fall["id"], "tp": 0, "fp": 0, "fn": fn,
                           "fehler": f"{type(e).__name__}: {str(e)[:200]}"})
            continue
        zeilen.append(bewerten(fall, beitraege))
    return zusammenfassen(zeilen)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--modell")
    a = ap.parse_args()
    from dotenv import load_dotenv
    load_dotenv(WURZEL / ".env")
    erg = ein_lauf(lade(), a.modell)
    for z in erg["faelle"]:
        print(f"  {z['id']:22} tp {z['tp']:3} fp {z['fp']:2} fn {z['fn']:2} "
              f"{'verpasst ' + ','.join(z.get('verpasst', [])) if z.get('verpasst') else ''}"
              f"{' ERFUNDEN ' + ','.join(z['erfunden']) if z.get('erfunden') else ''}"
              f"{' ' + z['fehler'] if z.get('fehler') else ''}")
    print({k: v for k, v in erg.items() if k != "faelle"})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
