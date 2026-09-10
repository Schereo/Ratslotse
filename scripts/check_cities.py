#!/usr/bin/env python3
"""Wöchentlich: Ratsdokumente der Vergleichsstädte holen — und Oldenburg dazu.

Crontab (Prod)::

    0 5 * * 0  cd ~/app && .venv/bin/python scripts/check_cities.py \\
                 >> ~/app/data/check_cities.log 2>&1

**Fünf Uhr und nicht drei**, weil ``weekly_enrich.py`` sonntags um drei läuft
und zwei Läufe, die beide ein Embedding-Modell laden, nicht auf dieselbe
Stunde einer VM mit zwei Kernen gehören.

**Nur auf Prod.** Auf dev laufen per Entscheidung keine Crons; sie bekommt
den Stand über ``scripts/lokale_daten.py schieb --staedte --nach dev``.

**Warum 60 Tage Rückschau und nicht „seit dem letzten Lauf".** Ergebnisse und
Beschlussausfertigungen werden Wochen nach der Sitzung nachgetragen; wer nur
nach vorne schaut, bekommt sie nie. Die Rohablage dedupliziert unveränderte
Objekte ohnehin, ein zweiter Blick kostet also nur Abrufe, keine Zeilen.

**Oldenburg läuft ohne Zeitfenster und ohne Netz** — der Adapter liest die
Rats-Datenbank, die der tägliche Protokoll-Cron ohnehin füllt.
"""
from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from council.cities import default_paths, pipeline  # noqa: E402
from council.cities.registry import active_bodies  # noqa: E402
from council.cities.store import CitiesStore  # noqa: E402
from kern.alerts import run_guarded  # noqa: E402

logger = logging.getLogger("check_cities")

#: Wie weit ein Lauf zurückschaut. Über die Umgebung verstellbar, damit ein
#: Nachlauf nach einer Panne mehr aufholen kann, ohne dass jemand Code ändert.
RUECKSCHAU_TAGE = int(os.environ.get("CITIES_SINCE_DAYS", "60"))

#: Wie viele Vorlagen ein Lauf höchstens einordnen lässt. Ein Rückstau wird
#: über mehrere Wochen abgebaut, statt dass ein einzelner Sonntag teuer wird.
#: Gemessen: 0,31 $ je 1.000 Vorlagen.
ANNOTATE_MAX = int(os.environ.get("CITIES_ANNOTATE_MAX", "3000"))

#: Wie viele Niederschrift-Abschnitte je Lauf ein „Warum" bekommen. Der Deckel
#: ist niedriger als bei den Vorlagen, weil ein Abschnitt sechsmal so lang ist
#: — und weil nur Punkte gefragt werden, deren Idee mindestens eine andere
#: Stadt teilt: Nur dort zeigt die Karte das „Warum" überhaupt an.
REASON_MAX = int(os.environ.get("CITIES_REASON_MAX", "400"))


def main() -> dict:
    from datetime import date, timedelta

    db, files_dir, raw_dir = default_paths()
    seit = (date.today() - timedelta(days=RUECKSCHAU_TAGE)).isoformat()
    # Zahlen und Fehlertexte getrennt: So bleibt der Zähler-Teil ein
    # sauberes dict[str, int], und die Klartext-Gründe kommen erst am Ende dazu.
    zaehler = {"bodies": 0, "papers_new": 0, "files_fetched": 0, "files_failed": 0,
               "texts_new": 0, "errors": 0, "papers_total": 0}
    gruende: dict[str, str] = {}
    t0 = time.time()

    main_store = CitiesStore(db)
    try:
        vorher = {z["id"]: z["papers"] for z in main_store.stats()}
        for spec in active_bodies():
            # Oldenburg kennt kein Zeitfenster: Der Adapter liest ohnehin nur,
            # was die Rats-Datenbank hergibt, und das ist billig.
            fenster = None if spec.dialect == "oldenburg" else seit
            try:
                ernte = pipeline.fetch(spec, raw_dir, files_dir, fenster)
                pipeline.normalize(spec, raw_dir, main_store)
                pipeline.extract_inline(main_store, spec, raw_dir)
                text = pipeline.extract(main_store, files_dir, spec.id)
                # Die frisch geholten Niederschriften gleich schneiden: Der
                # Schnitt ist Regelarbeit ohne Modell und ohne Netz, und der
                # `reason`-Lauf weiter unten braucht die Abschnitte.
                schnitt = pipeline.split_protocols(main_store, spec.id)
                zaehler["bodies"] += 1
                zaehler["files_fetched"] += ernte.get("files_fetched", 0)
                zaehler["files_failed"] += ernte.get("files_failed", 0)
                zaehler["protocols_fetched"] = (zaehler.get("protocols_fetched", 0)
                                                + ernte.get("protocols_fetched", 0))
                zaehler["texts_new"] += text.get("ok", 0) + text.get("thin", 0)
                zaehler["sections"] = zaehler.get("sections", 0) + schnitt["sections"]
            except Exception as e:  # noqa: BLE001 — eine Stadt kippt nicht den Lauf
                zaehler["errors"] += 1
                gruende[f"error_{spec.id}"] = f"{type(e).__name__}: {e}"
                logger.warning("%s: %s", spec.id, e)

        # Einordnen läuft über ALLE Städte zusammen — der Deckel gilt für den
        # Lauf, nicht je Stadt, sonst bekäme die erste Stadt alles.
        try:
            for schluessel, ergebnis in pipeline.annotate(
                    main_store, limit=ANNOTATE_MAX).items():
                zaehler["annotated"] = zaehler.get("annotated", 0) + ergebnis["annotated"]
                zaehler["annotate_errors"] = (zaehler.get("annotate_errors", 0)
                                              + ergebnis["errors"])
                gruende[f"cost_{schluessel}"] = f"${ergebnis['cost_usd']:.4f}"
        except Exception as e:  # noqa: BLE001
            zaehler["errors"] += 1
            gruende["error_annotate"] = f"{type(e).__name__}: {e}"

        # Dann der Index: Er baut auf Text UND Einordnung auf.
        try:
            for name, wert in pipeline.index_all(main_store).items():
                zaehler[f"index_{name}"] = wert
        except Exception as e:  # noqa: BLE001
            zaehler["errors"] += 1
            gruende["error_index"] = f"{type(e).__name__}: {e}"

        # Ideen-Cluster über Stadtgrenzen: Sie brauchen die Einordnung (sie
        # sagt, was eine Idee ist) und liefern die Zahl, die kein Einzelurteil
        # liefern kann — in wie vielen Städten dieselbe Sache vorkommt.
        try:
            for name, wert in pipeline.cluster_all(main_store).items():
                zaehler[f"cluster_{name}"] = wert
        except Exception as e:  # noqa: BLE001
            zaehler["errors"] += 1
            gruende["error_cluster"] = f"{type(e).__name__}: {e}"

        # Zuletzt, was den Index BRAUCHT: `fit` urteilt über Oldenburg und
        # belegt das mit den nächsten Oldenburger Vorlagen — die entstehen
        # eine Zeile weiter oben. Vorher gefragt, urteilte es ins Leere.
        try:
            for schluessel, ergebnis in pipeline.annotate(
                    main_store, limit=ANNOTATE_MAX, nach_index=True).items():
                zaehler["judged"] = zaehler.get("judged", 0) + ergebnis["annotated"]
                for name in ("skipped_no_evidence", "hallucinated_evidence",
                             "claim_without_evidence"):
                    if ergebnis.get(name):
                        zaehler[name] = zaehler.get(name, 0) + ergebnis[name]
                gruende[f"cost_{schluessel}"] = f"${ergebnis['cost_usd']:.4f}"
        except Exception as e:  # noqa: BLE001
            zaehler["errors"] += 1
            gruende["error_fit"] = f"{type(e).__name__}: {e}"
        # Nach jedem `fit`-Lauf noch einmal: Die Mehrheit je Gruppe hängt an den
        # Urteilen, und die sind gerade neu. Der Cluster-Schritt hat sie schon
        # einmal geschrieben — aber VOR `fit`, mit dem Stand der Vorwoche.
        try:
            from council.cities.annotators import get as get_annotator
            from council.cities.clusters import CLUSTER_VERSION
            from council.cities.index import EMBED_MODEL
            zaehler["group_status"] = main_store.rebuild_group_status(
                EMBED_MODEL, CLUSTER_VERSION, get_annotator("fit").version)
        except Exception as e:  # noqa: BLE001 — Kennzahl, nicht der Lauf
            gruende["error_group_status"] = f"{type(e).__name__}: {e}"

        # Das „Warum": Was stand in der Niederschrift zu den Punkten, die eine
        # Idee mit mindestens einer anderen Stadt teilen? Läuft NACH
        # `group_status`, weil die Arbeitsliste genau daran hängt — vorher
        # gefragt, wüsste sie noch nicht, welche Punkte auf der Karte landen.
        try:
            from council.cities import reasons
            from council.cities.annotators import get as get_annotator
            # Der Annotator steht auf `active=False`, solange sein Prüfstand
            # keinen belastbaren Maßstab hat (s. dort). Ein Cron, der Geld
            # ausgibt, ohne dass jemand die Qualität messen kann, ist genau
            # das, was `gut_wenn` verhindern soll.
            ergebnis = (reasons.run(main_store, limit=REASON_MAX)
                        if get_annotator("reason").active
                        else {"annotated": 0, "grounded": 0, "cost_usd": 0.0})
            zaehler["reasons"] = ergebnis["annotated"]
            zaehler["reasons_grounded"] = ergebnis["grounded"]
            gruende["cost_reason"] = f"${ergebnis['cost_usd']:.4f}"
        except Exception as e:  # noqa: BLE001
            zaehler["errors"] += 1
            gruende["error_reason"] = f"{type(e).__name__}: {e}"

        # Zuletzt: Ist der Bestand je Stadt überhaupt plausibel? Am 08.09.2026
        # lagen vier Ernte-Fehler gleichzeitig darin, und keiner hat sich
        # gemeldet — kein Absturz, kein roter Test, keine auffällige Zahl
        # (council/cities/pruefung.py zählt sie auf). Ein Befund hier ist der
        # einzige Weg, auf dem so etwas künftig von selbst auffällt.
        try:
            from council.cities import pruefung
            from council.cities.index import EMBED_MODEL

            befunde = pruefung.pruefe(main_store, EMBED_MODEL)
            zaehler["implausibel"] = len(befunde)
            for b in befunde:
                logger.warning("unplausibel: %s", b)
                gruende[f"pruefung_{b.body_id}_{b.regel}"] = f"{b.wert:.2f}"
        except Exception as e:  # noqa: BLE001 — eine Prüfung kippt den Lauf nicht
            zaehler["errors"] += 1
            gruende["error_pruefung"] = f"{type(e).__name__}: {e}"

        nachher = {z["id"]: z["papers"] for z in main_store.stats()}
        zaehler["papers_new"] = sum(nachher.get(k, 0) - vorher.get(k, 0) for k in nachher)
        zaehler["papers_total"] = sum(nachher.values())
        # Oldenburg eigens: Es ist die Stadt, gegen die alles verglichen wird,
        # und der Adapter liest ohne Zeitfenster aus der Rats-Datenbank. Fällt
        # die Zahl (Bestand 09/2026: 5.945), fehlt dem Vergleich die eine
        # Seite — und zwar still, weil die anderen Städte weiterlaufen.
        zaehler["papers_oldenburg"] = nachher.get("oldenburg", 0)
    finally:
        main_store.close()

    zahlen: dict[str, object] = dict(zaehler)
    zahlen.update(gruende)
    zahlen["seconds"] = round(time.time() - t0)
    return zahlen


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    run_guarded("check_cities", main)
