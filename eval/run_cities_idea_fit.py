#!/usr/bin/env python3
"""Trifft ``idea_fit`` den Stand Oldenburgs je IDEE?

**Warum es den Prüfstand braucht.** ``idea_fit`` ersetzt auf der Übersicht
der Bewegungen das Einzelurteil je Vorlage (Plan PR 48). Ein falsches
„vorhanden" nimmt eine Idee von der Liste, die Oldenburg fehlt — genau die
Liste, für die es das Feature gibt.

```bash
# auf dev, gegen eine Wegwerf-Kopie (Belege brauchen die Vektoren):
python eval/run_cities_idea_fit.py --cities ~/idea_probe/data/cities.sqlite \\
    --council ~/idea_probe/data/council.sqlite            # ~0,10 $
python eval/run_cities_idea_fit.py … --zeigen             # Sätze lesen
```

**Drei Schranken.**

1. Erfundene Kennungen: **0** — unter ``evidence`` UND ``related``.
2. Falsches „vorhanden" (erwartet ist eine Stufe, die „vorhanden" nicht
   zulässt): **0**. Dieselbe Asymmetrie wie bei ``fit``.
3. Status-Trefferquote **über 70 %**, gezählt streng gegen ``status``.
   Daneben die nachsichtige Quote gegen ``akzeptiert`` — die Grenze zwischen
   „teilweise" und den Nachbarn ist auch unter Menschen strittig.

Eine eigene Fehlerklasse ohne Schranke: Kennungen unter ``evidence``, die
der Maßstab als „nur verwandt" führt. Sie sind der Fehler, gegen den die
Trennung von Beleg und Verwandtem gebaut ist (Plan §2.10).

**Der Maßstab ist VORLÄUFIG** — von Claude gesetzt, nicht von Tim
(``eval/cases_cities_idea_fit.json``, ``_hinweis``). Solange das so ist,
sagt eine rote Quote so viel über den Maßstab wie über das Modell.

Der Lauf schreibt NICHTS in die Datenbank: Er ruft ``idea_fit.Richter``,
denselben Weg wie der Betrieb, ohne dessen Schreiber.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(WURZEL / ".env")

from council.cities import idea_fit  # noqa: E402
from council.cities.annotators import get as get_annotator  # noqa: E402
from council.cities.clusters import CLUSTER_VERSION  # noqa: E402
from council.cities.index import EMBED_MODEL  # noqa: E402
from council.cities.store import CitiesStore  # noqa: E402
from council.store import CouncilStore  # noqa: E402

FAELLE = WURZEL / "eval" / "cases_cities_idea_fit.json"

SCHWELLE_STATUS = 0.70
SCHWELLE_ERFUNDEN = 0
SCHWELLE_FALSCH_VORHANDEN = 0


def main() -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    ap.add_argument("--cities", default=str(WURZEL / "data" / "cities.sqlite"))
    ap.add_argument("--council", default=str(WURZEL / "data" / "council.sqlite"))
    ap.add_argument("--zeigen", action="store_true", help="Urteile ausschreiben")
    ap.add_argument("--nur", nargs="*", help="nur Fälle, deren Label so beginnt")
    args = ap.parse_args()

    faelle = json.loads(FAELLE.read_text())["faelle"]
    if args.nur:
        faelle = [f for f in faelle if any(f["label"].startswith(n) for n in args.nur)]
    ann = get_annotator("idea_fit")
    stand: dict = {}
    rats = CouncilStore(args.council)
    with CitiesStore(args.cities) as main_store:
        einordnung = main_store.annotations_for("classify", "2")
        richter = idea_fit.Richter(ann, einordnung, stand)
        matrix = main_store.chunk_matrix(EMBED_MODEL, "oldenburg")
        papier_matrix = main_store.paper_matrix(EMBED_MODEL, "oldenburg")
        begriffe = main_store.evidence_terms()

        streng = nachsichtig = gezaehlt = 0
        falsch_vorhanden: list[str] = []
        nur_verwandt_als_beleg: list[str] = []
        fehlt_gruppe: list[str] = []
        for fall in faelle:
            zeilen = main_store.cluster_of(fall["anker"], EMBED_MODEL, CLUSTER_VERSION)
            gruppe = (main_store.idea_group(EMBED_MODEL, CLUSTER_VERSION,
                                            zeilen[0]["cluster_id"]) if zeilen else None)
            if not gruppe:
                fehlt_gruppe.append(fall["label"])
                continue
            mitglieder = main_store.idea_group_members(EMBED_MODEL, CLUSTER_VERSION,
                                                       gruppe["cluster_id"])
            belege = idea_fit.belege_fuer(
                main_store, rats, mitglieder, einordnung, EMBED_MODEL,
                chunk_matrix=matrix, paper_matrix=papier_matrix, begriffe=begriffe)
            urteil, _kosten = richter.urteil(gruppe, mitglieder, belege)
            gezaehlt += 1
            if urteil is None:
                print(f"  ✗ {fall['label']}: kein Urteil")
                continue
            treffer = urteil.status == fall["status"]
            streng += treffer
            nachsichtig += urteil.status in fall["akzeptiert"]
            if urteil.status == "present" and "present" not in fall["akzeptiert"]:
                falsch_vorhanden.append(fall["label"])
            verwandt_falsch = [k for k in urteil.evidence if k in fall["nur_verwandt"]]
            nur_verwandt_als_beleg += [f"{fall['label']}: {k}" for k in verwandt_falsch]
            zeichen = "✓" if treffer else ("~" if urteil.status in fall["akzeptiert"] else "✗")
            print(f"  {zeichen} {fall['label']}: {urteil.status} (erwartet {fall['status']})")
            if args.zeigen:
                titel = {e.id: e.title for e in belege}
                print(f"      {urteil.situation}")
                for k in urteil.evidence:
                    print(f"      Beleg:     {k} — {titel.get(k, '')[:80]}")
                for k in urteil.related:
                    print(f"      Verwandt:  {k} — {titel.get(k, '')[:80]}")

    rats.close()
    if fehlt_gruppe:
        print(f"\nOhne Gruppe (Anker nicht gefunden): {fehlt_gruppe}")
    n = max(gezaehlt, 1)
    erfunden = int(stand.get("hallucinated_evidence", 0))
    print(f"\nStatus streng:      {streng}/{gezaehlt} = {streng / n:.0%}  (Schranke {SCHWELLE_STATUS:.0%})")
    print(f"Status nachsichtig: {nachsichtig}/{gezaehlt} = {nachsichtig / n:.0%}")
    print(f"Erfundene Kennungen (Stimmen): {erfunden}  (Schranke {SCHWELLE_ERFUNDEN})")
    print(f"Falsches „vorhanden“: {len(falsch_vorhanden)} {falsch_vorhanden or ''}")
    print(f"Nur-verwandt als Beleg: {len(nur_verwandt_als_beleg)} {nur_verwandt_als_beleg or ''}")
    print(f"Stimmen: {stand.get('votes', 0)}, uneins: {stand.get('split', 0)}, "
          f"Fehler: {stand.get('errors', 0)}, Kosten ${stand.get('cost_usd', 0.0):.4f}")
    gut = (streng / n >= SCHWELLE_STATUS and erfunden <= SCHWELLE_ERFUNDEN
           and len(falsch_vorhanden) <= SCHWELLE_FALSCH_VORHANDEN)
    return 0 if gut else 1


if __name__ == "__main__":
    raise SystemExit(main())
