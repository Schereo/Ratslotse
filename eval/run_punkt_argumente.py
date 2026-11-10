#!/usr/bin/env python3
"""Argumente zum Tagesordnungspunkt — die Messung vor dem Ausrollen.

Plan: ``docs/plan-punkt-argumente.md`` § 5. Zwanzig feste Punkte mit Stoff
(mindestens vier Wortbeiträge aus mindestens zwei Fraktionen), gemischt nach
Gremium und Ergebnis, dazu die Fälle aus dem Entwurf: das Soziale
D-Ticket (Vorgänger 25/0397 — 26/0719 hat im Abzug noch keine Debatte),
die Grundsteuer C (Debatte mit nur EINER genannten Fraktion) und die
Weißenmoorstraße als Leerprobe (dreimal vertagt, keine Wortbeiträge: Es darf
gar nichts entstehen).

**Geurteilt wird von Hand**, je Aussage drei Fragen:

1. ``belegt`` — steht sie in der genannten Quelle?
2. ``zugeordnet`` — gehört sie der genannten Person/Fraktion? (Urheber kommen
   aus der Quelle, nicht vom Modell — falsch kann hier vor allem die SEITE
   sein, also „dafür" statt „dagegen")
3. ``treu`` — stimmt die Paraphrase inhaltlich?

Dazu je Punkt ``streitpunkt_erfunden`` (eine Frage, an der sich niemand
scheidet). Die Urteile stehen in ``eval/punkt_argumente_gold.json`` unter der
Kennung des Laufs; ``--auswerten`` rechnet das Tor aus: 100 % belegt, ≥ 95 %
zugeordnet, ≥ 90 % treu, höchstens ein erfundener Streitpunkt.

    python eval/run_punkt_argumente.py --limit 1      # Kostenprobe
    python eval/run_punkt_argumente.py                # alle zwanzig, schreibt Lauf + Checkliste
    python eval/run_punkt_argumente.py --auswerten <lauf>

Braucht OPENROUTER_API_KEY und den Abzug (``scripts/lokale_daten.py``).
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(WURZEL / ".env")

ERGEBNISSE = WURZEL / "eval" / "results" / "punkt_argumente"
GOLD = WURZEL / "eval" / "punkt_argumente_gold.json"

#: (ksinr, Punkt, warum er drin ist) — dev-Abzug vom 08.11.2026.
STICHPROBE: tuple[tuple[int, str, str], ...] = (
    (4417, "Ö 8.7", "Entwurf: Soziales D-Ticket (Vorgänger 25/0397), Verkehr"),
    (4708, "Ö 9.1", "Entwurf: Grundsteuer C, Rat, vertagt, nur eine Fraktion genannt"),
    (4654, "Ö 11.1", "Entwurf: Weißenmoorstraße — Leerprobe ohne Wortbeiträge"),
    (4705, "Ö 13.3", "Rat, angenommen: Geschäftsordnung, transparente Dokumentation"),
    (4695, "Ö 14.4", "Rat, abgelehnt: Bau-Turbo-Grundsatzbeschluss"),
    (4625, "Ö 8.1", "Rat, vertagt: Entgelte P+R-Parkhaus ZOB"),
    (4702, "Ö 8.1", "Rat, angenommen: VBN-Tarifanpassung 2027"),
    (4648, "Ö 14.1", "Verkehr, abgelehnt: P+R-Konzept"),
    (4650, "Ö 10.3", "Verkehr, vertagt: Anwohnergenehmigung Junkerstraße"),
    (4650, "Ö 10.2", "Verkehr, ohne Beschluss: Bushaltestelle BBS 3"),
    (4479, "Ö 8", "Stadtplanung, vertagt: Bauturbo im Baugesetzbuch"),
    (4607, "Ö 6", "Stadtplanung, angenommen: Zweckentfremdungssatzung"),
    (4603, "Ö 5", "Stadtplanung, angenommen: Teilflächennutzungsplan Windenergie"),
    (4632, "Ö 6", "Soziales, Bericht: Kidstime"),
    (4630, "Ö 5", "Soziales, Bericht: Aktionsplan gegen Gewalt (47 Beiträge)"),
    (4640, "Ö 17.3", "Finanzen, angenommen: Preiswerte Wohnungen Klävemann-Stiftung"),
    (4637, "Ö 12.2", "Finanzen, ohne Beschluss: Sondervermögen Straßensanierung (ohne Vorlage)"),
    (4589, "Ö 6.2", "Sport, vertagt: Zweifeldausbau Hundsmühler Höhe"),
    (4589, "Ö 6.3", "Sport, abgelehnt: BIKU Mädchen an den Ball (ohne Vorlage)"),
    (4600, "Ö 6", "Kultur, Bericht: Neuausrichtung Kultursommer"),
)

TOR = {"belegt": 1.0, "zugeordnet": 0.95, "treu": 0.90}
TOR_ERFUNDEN = 1


def _aussagen(payload: dict) -> list[tuple[str, dict]]:
    """Alle Aussagen in fester Reihenfolge, mit ihrem Platz (für die Urteile)."""
    out = []
    for i, iss in enumerate(payload.get("issues") or []):
        for seite in ("pro", "contra"):
            out += [(f"S{i + 1}-{seite}", a) for a in iss[seite]]
    for seite in ("pro", "contra"):
        out += [(f"W-{seite}", a) for a in (payload.get("further") or {}).get(seite, [])]
    return out


def laufen(limit: int | None) -> Path:
    from council import arguments
    from council.store import CouncilStore
    from kern import llm

    store = CouncilStore(str(WURZEL / "data" / "council.sqlite"))
    faelle = []
    vorher = llm.session_cost()["usd"]
    for ksinr, nr, warum in STICHPROBE[:limit]:
        m = store.item_argument_material(ksinr, nr)
        if not m:
            faelle.append({"ksinr": ksinr, "item_number": nr, "warum": warum, "fehlt": True})
            continue
        start = llm.session_cost()["usd"]
        payload = arguments.generate(m["title"], m["speeches"], m["template"], m["outcome_note"])
        _, quellen = arguments.build_input(m["title"], m["speeches"], m["template"], m["outcome_note"])
        faelle.append({
            "ksinr": ksinr, "item_number": nr, "warum": warum, "subject_key": m["subject_key"],
            "title": m["title"], "speeches": len(m["speeches"]),
            "factions": [g["party"] for g in arguments.factions(m["speeches"])],
            "outcome_note": m["outcome_note"], "payload": payload,
            "shown": arguments.zeigen(payload),
            "quellen": {k: (q.get("text") or "") for k, q in quellen.items()},
            "usd": round(llm.session_cost()["usd"] - start, 5),
        })
        print(f"{ksinr} {nr}: {len(m['speeches'])} Beiträge → "
              f"{'nichts' if not payload else '%d Streitpunkte, %d/%d' % (len(payload['issues']), *arguments.counts(payload))}"
              f" · {faelle[-1]['usd']:.4f} $", flush=True)
    kosten = llm.session_cost()
    lauf = datetime.now().strftime("%Y%m%d-%H%M")
    ERGEBNISSE.mkdir(parents=True, exist_ok=True)
    pfad = ERGEBNISSE / f"{lauf}.json"
    pfad.write_text(json.dumps({"lauf": lauf, "modell": arguments.MODEL,
                                "usd": round(kosten["usd"] - vorher, 4),
                                "calls_ohne_kosten": kosten["calls_ohne"], "faelle": faelle},
                               ensure_ascii=False, indent=1))
    checkliste(pfad)
    print(f"\n{pfad.relative_to(WURZEL)} · {kosten['usd'] - vorher:.4f} $"
          + (f" (Untergrenze: {kosten['calls_ohne']} Aufrufe ohne Kostenangabe)" if kosten["calls_ohne"] else ""))
    return pfad


def checkliste(pfad: Path) -> None:
    """Die Tabelle zum Abhaken: je Aussage Paraphrase und Quelle nebeneinander."""
    d = json.loads(pfad.read_text())
    z = [f"# Argumente — Lauf {d['lauf']} ({d['modell']}, {d['usd']} $)", ""]
    for f in d["faelle"]:
        z.append(f"## {f['ksinr']} {f['item_number']} — {f.get('title') or '(fehlt)'}")
        z.append(f"*{f['warum']}* · {f.get('speeches', 0)} Beiträge · Fraktionen: "
                 f"{', '.join(p or '—' for p in f.get('factions') or [])}")
        p = f.get("payload")
        if not p:
            z += ["", "Nichts erzeugt.", ""]
            continue
        z.append(f"Reiter sichtbar: {'ja' if f['shown'] else 'nein'}")
        for i, iss in enumerate(p["issues"]):
            z.append(f"- Streitpunkt S{i + 1}: {iss['question']}")
        z += ["", "| Platz | Kennung | Urheber | Paraphrase | Quelle |", "|---|---|---|---|---|"]
        for platz, a in _aussagen(p):
            k = a["source"]["ref"]
            original = f["quellen"].get(k, "")
            wer = f"{a.get('speaker') or 'Verwaltung'} ({a.get('party') or '—'})"
            z.append(f"| {platz} | {k} | {wer} | {a['text']} | {original[:300].replace('|', '/')} |")
        z.append("")
    pfad.with_suffix(".md").write_text("\n".join(z))


def auswerten(lauf: str) -> int:
    """Das Tor aus den Urteilen in ``punkt_argumente_gold.json``."""
    d = json.loads((ERGEBNISSE / f"{lauf}.json").read_text())
    gold = json.loads(GOLD.read_text()).get(lauf) or {}
    summe = {k: [0, 0] for k in TOR}
    erfunden = 0
    offen = 0
    for f in d["faelle"]:
        p = f.get("payload")
        if not p:
            continue
        g = gold.get(f"{f['ksinr']} {f['item_number']}") or {}
        erfunden += int(g.get("streitpunkt_erfunden", 0))
        for platz, a in _aussagen(p):
            u = (g.get("aussagen") or {}).get(f"{platz}|{a['source']['ref']}")
            if not u:
                offen += 1
                continue
            for k in TOR:
                summe[k][0] += int(bool(u.get(k)))
                summe[k][1] += 1
    ok = True
    for k, (ja, n) in summe.items():
        anteil = ja / n if n else 0.0
        ok &= anteil >= TOR[k]
        print(f"{k:11} {ja}/{n} = {anteil:.0%} (Tor {TOR[k]:.0%})")
    print(f"erfundene Streitpunkte: {erfunden} (Tor ≤ {TOR_ERFUNDEN})")
    ok &= erfunden <= TOR_ERFUNDEN
    if offen:
        print(f"{offen} Aussagen ohne Urteil — erst abhaken.")
        ok = False
    print("TOR ERREICHT" if ok else "Tor nicht erreicht")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--limit", type=int, help="nur die ersten N Punkte (Kostenprobe)")
    ap.add_argument("--auswerten", metavar="LAUF", help="Tor aus den Urteilen rechnen")
    a = ap.parse_args()
    if a.auswerten:
        return auswerten(a.auswerten)
    laufen(a.limit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
