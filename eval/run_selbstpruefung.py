#!/usr/bin/env python3
"""Kalibrierung von Lottis Selbstprüfung — trifft der Prüfer, was wir schon wissen?

**Wozu.** Ein Prüfer, der gute Antworten zurückweist, macht Lotti langsamer
und teurer und kann eine gute Antwort durch eine schlechtere ersetzen. Bevor
der Schalter ``lotti-selbstpruefung`` irgendwo an ist, muss deshalb gemessen
sein, wie oft er bekannte Mängel findet (Trefferquote) und wie oft er gute
Antworten beanstandet (Fehlalarme). Das hier misst beides an zwei Sätzen mit
bekanntem Urteil — **ohne neue Antworten**, nur mit neuen Prüfer-Aufrufen:

* ``fakten`` — ein Lauf der Fakten-Eval (``eval/run_fakten.py``), Lottis
  Fälle: ``ok`` gilt als gut, ``modell_*`` als mangelhaft. Kontextfehler
  bleiben draußen — dort stand die Antwort gar nicht im Prompt, ein Prüfer,
  der nur den Prompt sieht, kann sie nicht vermissen.
* ``laien`` — die 36 Laienfragen vom 24.09.2026 (Befund im PR), mit dem
  Mitschnitt der Prompts. Das Urteil je Frage steht in
  ``eval/cases_selbstpruefung_laien.json``: ``gut``, ``B`` (zu vorsichtig —
  der Prüfer SOLL anschlagen) und ``A`` (die Daten fehlten im Kontext — der
  Prüfer kann das nicht wissen; gezählt wird nur, wie oft er anschlägt).

Aufruf::

    python eval/run_selbstpruefung.py fakten ~/.cache/ratslotse/fakten-mitschnitt/<lauf>
    python eval/run_selbstpruefung.py laien <mitschnitt>/assistant_explain.jsonl
    python eval/run_selbstpruefung.py absage ~/.cache/ratslotse/fakten-mitschnitt/<lauf>
    … --modell google/gemini-3-flash-preview --limit 15

``absage`` ist die Gegenprobe zur Nachsicht des Prüfers: Die guten Fälle
eines Fakten-Laufs, deren Goldfakt im Kontext stand, bekommen statt ihrer
Antwort eine bloße Absage („Das geht aus den Angaben hier nicht hervor.“).
Jede davon MUSS der Prüfer beanstanden — der Kontext trägt die Zahl ja.

Stufe 1 (ohne Modell) läuft immer mit; ein Befund dort ersetzt den Prüfer
genau wie im Betrieb (``council.self_check.run``).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL))

from council import assistant as lotti  # noqa: E402
from council import self_check as sc  # noqa: E402

LAIEN = WURZEL / "eval" / "cases_selbstpruefung_laien.json"


def urteilen(frage: str, kontext: str, antwort: str, modell: str) -> dict:
    """Stufe 1, sonst der Prüfer — wie ``self_check.run``, ohne Neuschreiben."""
    text = lotti.split_next(antwort)[0]
    befunde = sc.rule_findings(text, kontext, frage)
    if befunde:
        return {"urteil": "poor", "stufe": "rules", "kategorien": [b.category for b in befunde],
                "gruende": [b.detail for b in befunde], "usd": 0.0, "ms": 0}
    v = sc.judge(frage, kontext, text, model=modell)
    return {"urteil": v.verdict, "stufe": "model", "kategorien": v.categories,
            "gruende": v.reasons, "fehlt": v.missing, "usd": v.cost_usd, "ms": v.ms}


def _perzentil(werte: list[float], p: float) -> float | None:
    w = sorted(werte)
    return w[min(len(w) - 1, int(round(p * (len(w) - 1))))] if w else None


def fakten_faelle(ordner: Path) -> list[dict]:
    lauf = json.loads((ordner / "lauf.json").read_text())
    aus = []
    for z in lauf["faelle"]:
        pfad = ordner / "kontexte" / f"{z['id']}.txt"
        if z.get("kanal") != "lotti" or z.get("weg") != "explain" or not pfad.exists():
            continue
        if z["fehlerart"].startswith("kontext_"):
            continue
        kontext = re.sub(r"^\[user\]\n", "", pfad.read_text(encoding="utf-8"))
        aus.append({"id": z["id"], "frage": z["frage"], "kontext": kontext,
                    "antwort": z["antwort"],
                    "soll": "gut" if z["fehlerart"] == "ok" else "mangelhaft",
                    "gruppe": z["fehlerart"]})
    return aus


ABSAGE = "Das geht aus den Angaben hier nicht hervor."


def absage_faelle(ordner: Path) -> list[dict]:
    """Die guten Fälle mit Goldfakt im Kontext — mit einer Absage als Antwort."""
    faelle: dict[str, dict] = {}
    for datei in (WURZEL / "eval").glob("cases_fakten_*.json"):
        faelle |= {c["id"]: c for c in json.loads(datei.read_text())}
    aus = []
    for f in fakten_faelle(ordner):
        fall = faelle.get(f["id"]) or {}
        # Nur, wo die Antwort in den Daten steht — bei „nicht in den Daten“
        # ist die Absage ja richtig.
        if f["soll"] == "gut" and fall.get("gold") and fall.get("antwort_in_daten", True):
            aus.append({**f, "id": f"{f['id']}+absage", "antwort": ABSAGE,
                        "soll": "mangelhaft", "gruppe": "absage"})
    return aus


def laien_faelle(mitschnitt: Path) -> list[dict]:
    """Die 36 Fragen: je Frage der LETZTE Aufruf im Mitschnitt (der Lauf im Fenster)."""
    befunde = {(f["route"], f["frage"]): f for f in json.loads(LAIEN.read_text())}
    letzte: dict[str, dict] = {}
    for zeile in mitschnitt.read_text(encoding="utf-8").splitlines():
        r = json.loads(zeile)
        p = r["messages"][0]["content"]
        m = re.search(r"<<<FRAGE\n(.*?)\nFRAGE", p, re.S)
        if m:
            letzte[m.group(1)] = {"kontext": p, "antwort": r.get("answer") or ""}
    aus = []
    for (_route, frage), f in befunde.items():
        r = letzte.get(frage)
        if r is None or f["befund"] is None:
            continue
        aus.append({"id": f"laie-{f['nr']:02}", "frage": frage, **r,
                    "soll": {"gut": "gut", "B": "mangelhaft", "A": "offen"}[f["befund"]],
                    "gruppe": f["befund"]})
    return aus


def auswerten(faelle: list[dict], modell: str, parallel: int = 4) -> dict:
    with ThreadPoolExecutor(parallel) as pool:
        urteile = list(pool.map(
            lambda f: urteilen(f["frage"], f["kontext"], f["antwort"], modell), faelle))
    zeilen = []
    for f, u in zip(faelle, urteile):
        zeilen.append({k: f[k] for k in ("id", "frage", "soll", "gruppe")} | u)
    def n(soll: str, urteil: str) -> int:
        return sum(1 for z in zeilen if z["soll"] == soll and z["urteil"] == urteil)
    mangel = sum(1 for z in zeilen if z["soll"] == "mangelhaft")
    gut = sum(1 for z in zeilen if z["soll"] == "gut")
    offen = sum(1 for z in zeilen if z["soll"] == "offen")
    ms = [z["ms"] for z in zeilen if z["stufe"] == "model" and z["ms"]]
    usd = [z["usd"] for z in zeilen if z["usd"] is not None]
    return {
        "modell": modell, "n": len(zeilen),
        "treffer": n("mangelhaft", "poor"), "mangelhaft": mangel,
        "fehlalarme": n("gut", "poor"), "gut": gut,
        "offen_beanstandet": n("offen", "poor"), "offen": offen,
        "unbekannt": sum(1 for z in zeilen if z["urteil"] == "unknown"),
        "p50_ms": _perzentil(ms, 0.5), "p95_ms": _perzentil(ms, 0.95),
        "usd_je_pruefung": round(sum(usd) / len(usd), 5) if usd else None,
        "zeilen": zeilen,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("satz", choices=("fakten", "laien", "absage"))
    ap.add_argument("quelle", type=Path, help="Lauf-Ordner (fakten) bzw. Mitschnitt-Datei (laien)")
    ap.add_argument("--modell", default=sc.MODEL)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--nur", help="Fall-ids, kommagetrennt")
    ap.add_argument("--aus", type=Path, help="Ergebnis als JSON hierhin")
    a = ap.parse_args(argv)
    faelle = {"fakten": fakten_faelle, "laien": laien_faelle,
              "absage": absage_faelle}[a.satz](a.quelle)
    if a.nur:
        nur = set(a.nur.split(","))
        faelle = [f for f in faelle if f["id"] in nur]
    if a.limit:
        faelle = faelle[:a.limit]
    erg = auswerten(faelle, a.modell)
    for z in erg["zeilen"]:
        zeichen = "✓" if (z["soll"] == "gut") == (z["urteil"] != "poor") or z["soll"] == "offen" else "✗"
        print(f"{zeichen} {z['id']:36} {z['gruppe']:28} {z['urteil']:7} "
              f"{','.join(z['kategorien'])[:40]:40} {z['ms']:6} ms")
    print(f"\n{erg['modell']}: Treffer {erg['treffer']}/{erg['mangelhaft']}, "
          f"Fehlalarme {erg['fehlalarme']}/{erg['gut']}, "
          f"A beanstandet {erg['offen_beanstandet']}/{erg['offen']}, unbekannt {erg['unbekannt']}, "
          f"p50 {erg['p50_ms']} ms, p95 {erg['p95_ms']} ms, {erg['usd_je_pruefung']} $ je Prüfung")
    if a.aus:
        a.aus.write_text(json.dumps(erg, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
