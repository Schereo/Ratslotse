#!/usr/bin/env python3
"""Kennen die erzeugten Beschlusstexte das Ergebnis? — buchstäbliche Prüfung.

Anlass (23.09.2026): Die „Einfach erklärt"-Kurzfassung bekam Titel, Gremium,
Datum und Beschlusstext, aber nicht das Ergebnis. Bei einem ABGELEHNTEN
Antrag ist der Beschlusstext der Wortlaut des Antrags — das Modell erklärte
ihn als gefassten Beschluss: „Der Satz für die Grundsteuer B steigt von 445
auf 490 Prozent" (5988, einstimmig abgelehnt). Behoben in
``council/outcome_note.py`` (#1497) für ``simple_summary`` und ``summary``;
die Themen-Beschreibungen, die auf ``summary`` aufbauen, danach.

Geprüft wird je Textart:

* ``simple_summary``  — ``council.simple_summary.generate_one``
* ``summary``         — der Einzeiler der Klassifikation
  (``council.topics.classify_batch``, ein Stapel wie im Betrieb)
* ``themen``          — die Beschreibung einer Themen-Seite
  (``council.entities.describe``)

**Beschluss-Fälle** (``simple_summary``, ``summary``): 10 echte abgelehnte und
5 echte vertagte Beschlüsse, deren Abstimmungssatz (``raw_result``) das
Ergebnis wörtlich trägt — der Parser kann sich bei ihnen also nicht geirrt
haben —, dazu 5 angenommene als Gegenprobe. Ein Text besteht, wenn er das
Ergebnis nennt UND nicht behauptet, es sei beschlossen worden („hat
beschlossen", „beschließt", bei 5988 „steigt"). Ein angenommener besteht,
wenn er weder „abgelehnt" noch „vertagt" sagt.

**Themen-Fälle**: die 20 Themen des dev-Abzugs, deren Beschlüsse ALLE nicht
angenommen wurden (mindestens einer abgelehnt) — mit den Einzeilern, wie sie
vor dem Nachlauf dastanden, also teils falsch. Eine Beschreibung besteht,
wenn sie die Ablehnung nennt und nichts als beschlossen oder beauftragt
darstellt („nicht beschlossen" zählt nicht).

Keine Modell-Jury: Die Frage ist ja/nein und steht im Wortlaut. Die Probe
von #1497 (``outcome_note.states_outcome``) prüft nur, OB das Ergebnis
vorkommt — diese Eval prüft zusätzlich, dass nichts Gegenteiliges dasteht.

    python eval/run_ergebnis_texte.py                  # alle Textarten, 1 Lauf
    python eval/run_ergebnis_texte.py --laeufe 2 --save --etikett nachher
    python eval/run_ergebnis_texte.py --textart themen
    python eval/run_ergebnis_texte.py --bauen --db <abzug.sqlite>   # Fälle neu schneiden

Braucht OPENROUTER_API_KEY und ruft die HEUTIGEN Modelle der Module.
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(WURZEL / ".env")

FAELLE = WURZEL / "eval" / "cases_ergebnis_texte.json"
ERGEBNISSE = WURZEL / "eval" / "results" / "ergebnis_texte"

#: Abgelehnt: darunter die drei aus dem Befund (5988 Grundsteuer, 5914
#: VBN-Tarif, 5253 Eigenreinigung). Vertagt: alle mit „vertagt" im
#: Abstimmungssatz und Beschlusstext ≥ 200 Zeichen, bis auf die zwei Doppel
#: des Fliegerhorst-Plans (523, 2420 — gleicher Wortlaut wie 522/2419).
ABGELEHNT = (481, 1583, 2737, 5253, 5914, 5988, 5993, 6061, 9097, 9118)
VERTAGT = (522, 1008, 2419, 2592, 3747)
#: Gegenprobe: angenommene Beschlüsse dürfen durch die Regel nicht plötzlich
#: „abgelehnt" oder „vertagt" heißen.
ANGENOMMEN = (1552, 1843, 3075, 3104, 7462)
#: Themen, deren Beschlüsse alle nicht angenommen wurden (dev-Abzug 23.09.2026).
THEMEN = ("baederstrategiekonzept", "foerderschule-lernen", "heidbrook", "kreyenbrueck",
          "staendelweg", "zweckentfremdungssatzung", "infanterieweg", "gelbe-tonne",
          "tweelbaeker-see", "ruz", "btb", "eversten", "service-center", "quartiersgaragen",
          "stadtteilbaeder-eversten", "stadtteilbaeder-kreyenbrueck", "tsh-konzept-berlin",
          "e-scooter", "oli-bikes", "kuhbrook")

#: Woran man das Ergebnis erkennt. Großzügig in den Formen, streng im Sinn.
NENNT = {
    "rejected": re.compile(
        r"abgelehnt|lehnte|lehnt\b|lehnen\b|Ablehnung|keine Mehrheit|gescheitert|scheiterte",
        re.I),
    "postponed": re.compile(
        r"vertagt|vertagte|verschoben|verschob|noch nicht (entschieden|beschlossen)|"
        r"zurückgestellt|später (entschieden|beraten|weiter)|verwiesen", re.I),
}
#: Was ein Text über einen NICHT gefassten Beschluss nie sagen darf.
BEHAUPTET = re.compile(
    r"hat beschlossen|haben beschlossen|wurde beschlossen|wurden beschlossen|"
    r"\bbeschließt\b|\bbeschloss\b|hat entschieden:", re.I)
#: Fallbezogen: die Folge, die nur einträte, wenn der Antrag durchgegangen wäre.
FOLGE = {5988: re.compile(r"\bsteigt\b|\bsteigen\b|erhöht", re.I)}
_KONJUNKTIV = re.compile(r"\b(sollte|sollten|wäre|wären|hätte|hätten|würde|würden|"
                         r"vorgeschlagen|beantragt|Vorschlag|Antrag|abgelehnt)\b", re.I)
#: Themen: ein Beschluss oder Auftrag, der nicht verneint ist.
THEMA_BEHAUPTET = re.compile(r"\b(beschlossen|beschloss|beschließt|beauftragt\w*|zugestimmt)\b", re.I)
_VERNEINT = re.compile(r"\b(nicht|kein\w*|nie)\b[^.]{0,40}$", re.I)


def bauen(db: Path) -> None:
    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    faelle: list[dict] = []
    for did in ABGELEHNT + VERTAGT + ANGENOMMEN:
        r = con.execute(
            """SELECT d.id, d.title, d.official_text, d.outcome, d.vote, d.no_votes,
                      d.abstentions, d.raw_result, cs.committee, cs.session_date
               FROM council_decisions d JOIN council_sessions cs ON cs.ksinr = d.ksinr
               WHERE d.id = ?""", (did,)).fetchone()
        if r is None:
            raise SystemExit(f"Beschluss {did} fehlt in {db}")
        faelle.append({"art": "beschluss", **dict(r)})
    for slug in THEMEN:
        e = con.execute("SELECT id, name, kind FROM council_entities WHERE slug = ?", (slug,)).fetchone()
        if e is None:
            raise SystemExit(f"Thema {slug} fehlt in {db}")
        # Dieselbe Abfrage wie store.entity_decisions_brief, mit den Einzeilern
        # von damals — die Beschreibung muss auch aus falschen Einzeilern das
        # Richtige machen, solange der Nachlauf nicht durch ist.
        decs = [dict(r) for r in con.execute(
            """SELECT d.title, d.summary, d.policy_field, d.outcome, cs.session_date
               FROM council_entity_links el
               JOIN council_decisions d ON d.id = el.decision_id
               JOIN council_sessions cs ON cs.ksinr = d.ksinr
               WHERE el.entity_id = ? ORDER BY cs.session_date DESC LIMIT 40""", (e["id"],))]
        faelle.append({"art": "thema", "id": slug, "name": e["name"], "kind": e["kind"],
                       "outcome": "rejected", "decisions": decs})
    FAELLE.write_text(json.dumps(faelle, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(faelle)} Fälle → {FAELLE.relative_to(WURZEL)}")


def urteil(fall: dict, text: str | None) -> tuple[bool, str]:
    """(bestanden, Grund) für einen erzeugten Text."""
    if not text:
        return False, "kein Text"
    if fall["art"] == "thema":
        if not NENNT["rejected"].search(text):
            return False, "nennt keine Ablehnung"
        for m in THEMA_BEHAUPTET.finditer(text):
            if not _VERNEINT.search(text[max(0, m.start() - 60):m.start()]):
                return False, f"behauptet: „{m.group(0)}“"
        return True, ""
    if fall["outcome"] == "accepted":
        m = NENNT["rejected"].search(text) or NENNT["postponed"].search(text)
        return (False, f"angenommen, aber „{m.group(0)}“") if m else (True, "")
    if not NENNT[fall["outcome"]].search(text):
        return False, "nennt das Ergebnis nicht"
    m = BEHAUPTET.search(text)
    if m:
        return False, f"behauptet: „{m.group(0)}“"
    # Die Folge zählt nur als Aussage: „sollte … steigen" beschreibt den
    # Vorschlag und ist richtig, „Der Satz steigt" behauptet die Folge.
    if fall["id"] in FOLGE:
        for satz in re.split(r"(?<=[.!?])\s+", text):
            m = FOLGE[fall["id"]].search(satz)
            if m and not _KONJUNKTIV.search(satz):
                return False, f"behauptet: „{m.group(0)}“"
    return True, ""


def texte_simple(faelle: list[dict]) -> dict:
    from concurrent.futures import ThreadPoolExecutor

    from council import simple_summary

    with ThreadPoolExecutor(max_workers=5) as pool:
        return dict(zip((f["id"] for f in faelle), pool.map(simple_summary.generate_one, faelle)))


def texte_summary(faelle: list[dict]) -> dict:
    from council import topics

    ergebnis, _usage = topics.classify_batch(faelle)
    return {f["id"]: (ergebnis.get(f["id"]) or {}).get("summary") for f in faelle}


def texte_themen(faelle: list[dict]) -> dict:
    from concurrent.futures import ThreadPoolExecutor

    from council import entities

    def eins(f: dict) -> str | None:
        return entities.describe(f["name"], f["kind"], f["decisions"])

    with ThreadPoolExecutor(max_workers=5) as pool:
        return dict(zip((f["id"] for f in faelle), pool.map(eins, faelle)))


#: Textart → (Erzeuger, Fallart)
TEXTARTEN = {"simple_summary": (texte_simple, "beschluss"),
             "summary": (texte_summary, "beschluss"),
             "themen": (texte_themen, "thema")}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bauen", action="store_true", help="Fälle aus einer Ratsdatenbank neu schneiden")
    ap.add_argument("--db", type=Path, default=WURZEL / "data" / "council.sqlite")
    ap.add_argument("--textart", default=",".join(TEXTARTEN))
    ap.add_argument("--laeufe", type=int, default=1)
    ap.add_argument("--save", action="store_true")
    ap.add_argument("--etikett", default="", help="Name des Laufs im gespeicherten Ergebnis (z. B. vorher)")
    ap.add_argument("--neu-urteilen", type=Path, metavar="ERGEBNIS",
                    help="gespeicherte Texte mit den heutigen Regeln neu urteilen, ohne Modell")
    args = ap.parse_args()
    if args.bauen:
        bauen(args.db)
        return

    alle = json.loads(FAELLE.read_text(encoding="utf-8"))
    if args.neu_urteilen:
        # Vergleichbar bleiben vorher und nachher nur mit DENSELBEN Regeln.
        faelle_nach_id = {f["id"]: f for f in alle}
        alt = json.loads(args.neu_urteilen.read_text(encoding="utf-8"))
        for art, laeufe in alt["textarten"].items():
            for lauf in laeufe:
                n = sum(urteil(faelle_nach_id[z["id"]], z["text"])[0] for z in lauf["zeilen"])
                print(f"{art}: {n}/{len(lauf['zeilen'])}")
        return
    gesamt: dict = {"etikett": args.etikett, "zeit": datetime.now().isoformat(timespec="seconds"),
                    "textarten": {}}
    for art in args.textart.split(","):
        erzeuge, fallart = TEXTARTEN[art]
        faelle = [f for f in alle if f["art"] == fallart]
        laeufe = []
        for lauf in range(1, args.laeufe + 1):
            texte = erzeuge(faelle)
            zeilen = []
            for f in faelle:
                ok, grund = urteil(f, texte.get(f["id"]))
                zeilen.append({"id": f["id"], "outcome": f["outcome"], "ok": ok,
                               "grund": grund, "text": texte.get(f["id"])})
            n_ok = sum(z["ok"] for z in zeilen)
            print(f"\n== {art} · Lauf {lauf}: {n_ok}/{len(zeilen)} bestanden")
            for z in zeilen:
                if not z["ok"]:
                    print(f"  ✗ {z['id']} ({z['outcome']}): {z['grund']} — {(z['text'] or '')[:160]}")
            laeufe.append({"bestanden": n_ok, "faelle": len(zeilen), "zeilen": zeilen})
        gesamt["textarten"][art] = laeufe
    if args.save:
        ERGEBNISSE.mkdir(parents=True, exist_ok=True)
        ziel = ERGEBNISSE / f"{datetime.now():%Y%m%d-%H%M%S}{'-' + args.etikett if args.etikett else ''}.json"
        ziel.write_text(json.dumps(gesamt, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"\n→ {ziel.relative_to(WURZEL)}")


if __name__ == "__main__":
    main()
