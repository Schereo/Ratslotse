#!/usr/bin/env python3
"""Was fehlt Oldenburg — und in wie vielen anderen Räten liegt es?

**Die Zahl, um die es beim Städtevergleich geht.** Bis Fassung 2 hieß die
Frage „fehlt und lohnt sich" — mit einem Werturteil, das das Modell zu
46–58 % traf, während es den Status zu 62–69 % trifft. Fassung 3 fragt es
nicht mehr (``council/cities/annotators.py``), und damit ändert sich auch
das Maß hier: Nicht „das Modell hält es für lohnend", sondern **in wie
vielen anderen Städten dieselbe Idee schon einmal auf dem Tisch lag**. Das
ist nachprüfbar, und es sortiert die Liste auch besser.

```bash
python scripts/cities_bilanz.py                 # die Bilanz
python scripts/cities_bilanz.py --ab 3          # nur Ideen aus 3+ anderen Städten
python scripts/cities_bilanz.py --zeigen 40     # die Spitze der Liste lesen
```

**Warum das kein Test ist.** Es gibt keine Schranke, gegen die man prüfen
könnte — die Verteilung IST das Ergebnis. Der Prüfstand für die Qualität des
Urteils ist ``eval/run_cities_fit.py`` gegen die vierzig Handfälle; hier geht
es um den Bestand.
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))

from council.cities import default_paths  # noqa: E402
from council.cities.annotators import get as get_annotator  # noqa: E402
from council.cities.clusters import CLUSTER_VERSION  # noqa: E402
from council.cities.index import EMBED_MODEL  # noqa: E402
from council.cities.store import CitiesStore  # noqa: E402

#: Wie ein Status auf Deutsch heißt, und was er für die Liste bedeutet.
STATUS = {
    "missing": "fehlt in Oldenburg",
    "partial": "in Teilen da",
    "present": "hat Oldenburg",
}


def urteile(main: CitiesStore, version: str) -> list[dict]:
    """Jede fremde Vorlage mit einem Urteil dieser Fassung, samt Themenfeld.

    Ganze statische Anweisung (``tests/test_sql_spalten.py``).
    """
    rows = main._conn.execute(
        "SELECT p.id, p.body_id, p.name, p.date, p.kind, "
        "       json_extract(f.payload, '$.status') AS status, "
        "       json_extract(f.payload, '$.confidence') AS confidence, "
        "       json_extract(c.payload, '$.field') AS field, "
        "       json_extract(c.payload, '$.instrument') AS instrument, "
        "       json_extract(e.payload, '$.effort') AS effort, "
        "       (SELECT k.cluster_id FROM idea_clusters k "
        "        WHERE k.paper_id = p.id AND k.model = ? AND k.version = ?) AS cluster_id "
        "FROM annotations f "
        "JOIN papers p ON p.id = f.object_id "
        "LEFT JOIN annotations c ON c.object_kind='paper' AND c.object_id=p.id "
        "  AND c.annotator='classify' AND c.version='2' "
        "LEFT JOIN annotations e ON e.object_kind='paper' AND e.object_id=p.id "
        "  AND e.annotator='effort' AND e.version='1' "
        "WHERE f.object_kind='paper' AND f.annotator='fit' AND f.version=?",
        (EMBED_MODEL, CLUSTER_VERSION, version))
    return [dict(r) for r in rows]


def ohne_dubletten(zeilen: list[dict]) -> list[dict]:
    """Je Stadt und Idee eine Zeile — dieselbe Regel wie `CitiesStore.ideas`.

    **Die Abfrage im Store ist die Wahrheit**, nicht diese Funktion: Dort
    entscheidet SQL, hier Python, und zwei Fassungen laufen auseinander. Sie
    steht trotzdem hier, weil dieser Bericht über ALLE Themenfelder auf
    einmal rechnet und die Ideen-Abfrage je Feld einzeln antwortet.

    Es bleibt die jüngste; bei gleichem Datum entscheidet die Kennung.
    """
    beste: dict[tuple, dict] = {}
    frei: list[dict] = []
    for z in zeilen:
        if z.get("cluster_id") is None:
            frei.append(z)
            continue
        k = (z["body_id"], z["cluster_id"])
        vorher = beste.get(k)
        schluessel = (z.get("date") or "", z["id"])
        if vorher is None or schluessel > (vorher.get("date") or "", vorher["id"]):
            beste[k] = z
    return frei + list(beste.values())


def bilanz(zeilen: list[dict], peers: dict[str, int], ab: int) -> None:
    verteilung = Counter(z["status"] or "?" for z in zeilen)
    gesamt = len(zeilen)
    print(f"\n{gesamt} beurteilte fremde Vorlagen.\n")
    print(f"{'Urteil':22} {'Zahl':>7} {'Anteil':>8}   davon mit {ab}+ anderen Städten")
    print("-" * 76)
    for status in ("missing", "partial", "present"):
        n = verteilung.get(status, 0)
        viele = sum(1 for z in zeilen
                    if z["status"] == status and peers.get(z["id"], 0) >= ab)
        print(f"{STATUS[status]:22} {n:7} {n / max(gesamt, 1):7.0%}   {viele:7}"
              f" ({viele / max(n, 1):.0%})")

    fehlt = [z for z in zeilen if z["status"] == "missing"]
    print("\nDie Ideen, die fehlen, nach Zahl der anderen Städte:")
    staffel = Counter(min(peers.get(z["id"], 0), 6) for z in fehlt)
    for n in range(6, -1, -1):
        if not staffel.get(n):
            continue
        etikett = f"{n}+ andere Städte" if n == 6 else (
            f"{n} andere Städte" if n != 1 else "1 andere Stadt")
        print(f"  {etikett:22} {staffel[n]:6}")
    print(f"\n  Einzelstücke (nur diese eine Stadt): "
          f"{staffel.get(0, 0)} von {len(fehlt)}")

    print("\nJe Themenfeld — was fehlt und in mehreren Räten liegt:")
    je_feld = Counter(z["field"] or "—" for z in fehlt
                      if peers.get(z["id"], 0) >= ab)
    for feld, n in je_feld.most_common(12):
        print(f"  {feld[:34]:36} {n:5}")

    print("\nJe Aufwandsklasse (was es bräuchte, um es hier anzustoßen):")
    je_aufwand = Counter(z["effort"] or "—" for z in fehlt
                         if peers.get(z["id"], 0) >= ab)
    for stufe, n in je_aufwand.most_common():
        print(f"  {stufe[:20]:22} {n:5}")


def spitze(zeilen: list[dict], peers: dict[str, int], wie_viele: int) -> None:
    """Die Liste, die die Karte zeigt — sortiert wie dort."""
    fehlt = [z for z in zeilen if z["status"] == "missing"]
    fehlt.sort(key=lambda z: (-peers.get(z["id"], 0),
                              {"high": 0, "medium": 1}.get(z["confidence"], 2),
                              z["date"] or ""), reverse=False)
    print(f"\nDie {wie_viele} obersten:\n")
    for z in fehlt[:wie_viele]:
        print(f"  {peers.get(z['id'], 0):2} Städte  {z['body_id'][:11]:12} "
              f"{(z['date'] or '')[:7]}  {(z['instrument'] or z['name'] or '')[:66]}")


def main() -> int:
    p = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    p.add_argument("--version", default=None,
                   help="Fassung des Annotators (Vorgabe: die aktuelle)")
    p.add_argument("--ab", type=int, default=2,
                   help="ab wie vielen ANDEREN Städten eine Idee zählt (Vorgabe 2)")
    p.add_argument("--vorlagen", action="store_true",
                   help="je VORLAGE zählen statt je Idee. Die Karte zeigt Ideen "
                        "(eine Zeile je Stadt und Gruppe); dieser Schalter macht "
                        "sichtbar, wie viele Wiederholungen dahinterstehen.")
    p.add_argument("--zeigen", type=int, default=0,
                   help="zusätzlich die obersten N Ideen auflisten")
    a = p.parse_args()

    version = a.version or get_annotator("fit").version
    db, _f, _r = default_paths()
    store = CitiesStore(db)
    try:
        zeilen = urteile(store, version)
        roh = len(zeilen)
        if not a.vorlagen:
            zeilen = ohne_dubletten(zeilen)
        if not zeilen:
            print(f"Kein Urteil in Fassung {version}. Läuft der Bestandslauf noch?")
            return 1
        peers = store.peers_by_paper(EMBED_MODEL, CLUSTER_VERSION)
        print(f"fit-Fassung {version}, Cluster-Fassung {CLUSTER_VERSION}")
        if not a.vorlagen:
            print(f"Je Stadt und Idee eine Zeile: {roh} Vorlagen → {len(zeilen)} Ideen "
                  f"({roh - len(zeilen)} Wiederholungen). --vorlagen zeigt die rohe Zahl.")
        bilanz(zeilen, peers, a.ab)
        if a.zeigen:
            spitze(zeilen, peers, a.zeigen)
        return 0
    finally:
        store.close()


if __name__ == "__main__":
    raise SystemExit(main())
