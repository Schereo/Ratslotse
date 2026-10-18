#!/usr/bin/env python3
"""Täglich Oldenburg, sonntags alle Städte — schlank, gedeckelt, unterbrechbar.

Crontab (Prod)::

    15 10 * * 1-6  cd ~/app && .venv/bin/python scripts/check_cities.py --nur-oldenburg \\
                     >> ~/app/data/check_cities.log 2>&1
    0 5 * * 0      cd ~/app && .venv/bin/python scripts/check_cities.py \\
                     >> ~/app/data/check_cities.log 2>&1

**Warum zwei Takte (seit 10/2026).** Der Lauf war vom 20.09. bis 10/2026
pausiert, und in der Zeit bekam kein einziger neuer Oldenburger Beschluss
seinen Block „Anderswo": Der hängt an den Nachbarn der Oldenburger Vorlage im
Städte-Speicher, und die entstehen nur hier. Eine Woche Verzug wäre dafür zu
viel — ein Beschluss ist am Tag nach der Sitzung am interessantesten. Die
fremden Städte dagegen täglich zu holen hieße, ihre Ratsinformationssysteme
siebenmal so oft abzufragen, für dieselbe Erkenntnis. Also:

- **werktags 10:15, ``--nur-oldenburg``**: nach ``check_protocols`` (9 Uhr),
  ohne Netz und ohne Sprachmodell — Oldenburg aus der Rats-Datenbank
  übernehmen, Text, Vektoren, Nachbarn. Minuten, nicht Stunden.
- **sonntags 5 Uhr, alles**: erst Oldenburg wie werktags, dann die fremden
  Städte, Einordnung, Gruppen, Urteile.

**Fünf Uhr und nicht drei**, weil ``weekly_enrich.py`` sonntags um drei läuft
und zwei Läufe, die beide ein Embedding-Modell laden, nicht auf dieselbe
Stunde einer VM mit zwei Kernen gehören.

**Nur auf Prod.** Auf dev laufen per Entscheidung keine Crons; sie bekommt
den Stand über ``scripts/lokale_daten.py schieb --staedte --nach dev``.

**Warum 60 Tage Rückschau und nicht „seit dem letzten Lauf".** Ergebnisse und
Beschlussausfertigungen werden Wochen nach der Sitzung nachgetragen; wer nur
nach vorne schaut, bekommt sie nie. Die Rohablage dedupliziert unveränderte
Objekte ohnehin, ein zweiter Blick kostet also nur Abrufe, keine Zeilen.

**Oldenburg läuft zuerst, ohne Zeitfenster und ohne Netz** — der Adapter
liest die Rats-Datenbank, die der tägliche Protokoll-Cron ohnehin füllt.
Zuerst, weil es das ist, was die Nutzer*innen sehen: Tritt der Lauf später
zur Seite (Deploy, Frist, Kosten), ist Oldenburg trotzdem fertig.

**Geurteilt wird nur über NEUES** (``schlank``). Seit 10/2026 heißt das für
``fit``: Vorlagen ohne Urteil und solche, deren Einordnung jünger ist als ihr
Urteil. Dass Oldenburg einen neuen Beschluss hat, öffnet kein altes Urteil
mehr — vorher rechnete jeder Lauf die Belege für alle 12.000 Kandidaten neu
(eine Stunde, bevor das erste Urteil fiel), und jede neue Oldenburger Zeile
in einem Beleg-Pool hieß ein neues Urteil. Ein Versionssprung entwertet
ebenfalls nichts mehr stillschweigend: Am 15.09.2026 hob #1370 den
``fit``-Annotator von 3 auf 4, und der Sonntag darauf urteilte 9.560 Vorlagen
neu — vierzehn Stunden, rund sechs Dollar, und entschieden hatte das
niemand. Wie viele Urteile eine ältere Version tragen, steht als Kennzahl
``veraltet_<annotator>`` im Lauf. Nachgeholt wird so ein Bestand von Hand::

    python scripts/cities_backfill.py --run --stage annotate

**Drei Gründe, freiwillig aufzuhören** (``kern/stopp.py``): Ein Deploy wartet
(``data/.deploy-wartet``), ``CITIES_MAX_SECONDS`` ist um, oder
``CITIES_MAX_USD`` ist ausgegeben — EIN Betrag für den ganzen Lauf, über alle
Stufen. Das Geschriebene bleibt, der nächste Lauf macht weiter — die
Arbeitslisten fragen ohnehin „was fehlt noch?", nicht „wo war ich?".

**Was ein Lauf kostet** (gemessen, je Stück, Lauf vom 03.10.2026 in #1651):
Einordnung 0,0008 $, Aufwand 0,0004 $, Richtung 0,0007 $, Urteil (drei
Stimmen) 0,0023 $, Urteil je Idee 0,0044 $ — zwei- bis fünfmal so viel wie
im September gemessen (Einordnung 0,00016 $, Richtung 0,00013 $). Ein
gewöhnlicher Sonntag (13.09.2026, noch ohne ``schlank``): 1,62 $. Der erste
Lauf nach der Pause hat rund vier Wochen Rückstand, s. den Trockenlauf::

    python scripts/check_cities.py --trocken
"""
from __future__ import annotations

import argparse
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
from kern.alerts import JobFehler, run_guarded  # noqa: E402
from kern.stopp import aus_umgebung  # noqa: E402

logger = logging.getLogger("check_cities")

#: Wie weit ein Lauf zurückschaut. Über die Umgebung verstellbar, damit ein
#: Nachlauf nach einer Panne mehr aufholen kann, ohne dass jemand Code ändert.
RUECKSCHAU_TAGE = int(os.environ.get("CITIES_SINCE_DAYS", "60"))

#: Wie viele Vorlagen ein Lauf höchstens einordnen lässt — und wie viele
#: höchstens ein Urteil über Oldenburg bekommen. Ein Rückstau wird über
#: mehrere Wochen abgebaut, statt dass ein einzelner Sonntag teuer wird. Die
#: Kostengrenze unten ist die eigentliche Schranke; dieser Deckel hält die
#: LAUFZEIT eines Stapels überschaubar.
ANNOTATE_MAX = int(os.environ.get("CITIES_ANNOTATE_MAX", "3000"))

#: Wie viele Niederschrift-Abschnitte je Lauf ein „Warum" bekommen. Der Deckel
#: ist niedriger als bei den Vorlagen, weil ein Abschnitt sechsmal so lang ist
#: — und weil nur Punkte gefragt werden, deren Idee mindestens eine andere
#: Stadt teilt: Nur dort zeigt die Karte das „Warum" überhaupt an.
REASON_MAX = int(os.environ.get("CITIES_REASON_MAX", "400"))

#: **Wie lange dieser Lauf höchstens dauern darf.** Der Deckel oben begrenzt
#: die STÜCKZAHL, nicht die Uhr. Am 20.09.2026 lief der Sonntagslauf vierzehn
#: Stunden und blockierte solange jeden Prod-Deploy: sechs an einem Tag.
#: `0` hebt die Frist auf (für einen Nachlauf von Hand).
MAX_SEKUNDEN = "CITIES_MAX_SECONDS"
MAX_SEKUNDEN_VORGABE = 4 * 3600

#: **Wie viel dieser Lauf höchstens kosten darf** — über ALLE Stufen. Ein
#: gewöhnlicher Sonntag kostete 1,62 $ (13.09.2026); zwei Dollar lassen
#: einem normalen Lauf Luft und schneiden einen Ausreißer ab, bevor er teuer
#: wird. Wird die Grenze erreicht, tritt der Lauf zur Seite wie bei einem
#: Deploy; der Rest kommt nächsten Sonntag. `0` hebt sie auf.
MAX_USD = "CITIES_MAX_USD"
MAX_USD_VORGABE = 2.0

#: Was ein Stück je Stufe kostet — für den Trockenlauf. Gemessen am Lauf
#: vom 03.10.2026 (#1651, Osnabrück, ``--limit 30``): classify 30 Stück für
#: 0,023 $, effort 30 für 0,012 $, stance 760 für 0,55 $, fit 22 für 0,051 $,
#: idea_fit 86 für 0,375 $. Die Werte vom September (classify 0,00016,
#: stance 0,00013, fit 0,0011, idea_fit 0,0016) lagen um den Faktor 2–5
#: darunter; mit ihnen hätte der Trockenlauf den Rückstau so weit
#: unterschätzt, dass die 2-$-Grenze überraschend früh griff. Bei
#: ``classify`` streute es zwischen 0,0003 und 0,0008 $ — die Schätzung nimmt
#: den oberen Wert.
KOSTEN_JE_STUECK = {"classify": 0.0008, "effort": 0.0004, "stance": 0.0007,
                    "fit": 0.0023, "idea_fit": 0.0044}


def _oldenburg(main_store: CitiesStore, raw_dir: Path, files_dir: Path,
               zaehler: dict, gruende: dict) -> None:
    """Oldenburg übernehmen, Text, Vektoren, Nachbarn — ohne Netz und Modell.

    Das ist alles, was „Anderswo" unter einem neuen Oldenburger Beschluss
    braucht: Der Block liest die Nachbarn der Vorlage im Städte-Speicher
    (``decision_elsewhere``), und die Einordnung der FREMDEN Treffer liegt
    längst vor.
    """
    from council.cities.registry import get

    spec = get("oldenburg")
    try:
        pipeline.fetch(spec, raw_dir, files_dir, None)
        normal = pipeline.normalize(spec, raw_dir, main_store)
        pipeline.extract_inline(main_store, spec, raw_dir)
        text = pipeline.extract(main_store, files_dir, spec.id)
        zaehler["oldenburg_papers_seen"] = int(normal.get("papers", 0) or 0)
        zaehler["texts_new"] = (zaehler.get("texts_new", 0)
                                + text.get("ok", 0) + text.get("thin", 0))
        for name, wert in pipeline.index_all(main_store, "oldenburg").items():
            zaehler[f"oldenburg_index_{name}"] = wert
    except Exception as e:  # noqa: BLE001 — Kennzahl und Fehlertext, kein Abbruch
        zaehler["errors"] = zaehler.get("errors", 0) + 1
        gruende["error_oldenburg"] = f"{type(e).__name__}: {e}"
        logger.warning("oldenburg: %s", e)


def trocken(main_store: CitiesStore) -> dict:
    """Was der nächste volle Lauf zu tun hätte — und was das kostet.

    Ohne Netz und ohne Modell; die Ernte selbst kann er nicht vorhersagen
    (dafür müsste er die Städte fragen), wohl aber, was im Bestand offen ist.
    """
    from council.cities import auswahl
    from council.cities import fit as fit_modul
    from council.cities.annotators import USABLE, active_annotators
    from council.cities.annotators import get as get_annotator

    kandidaten = {p["id"] for p in auswahl.papiere(main_store)}
    einordnung = main_store.annotations_for("classify", "2")
    nutzbar = {k for k in kandidaten
               if (einordnung.get(k) or {}).get("transfer") in USABLE}
    aus: dict[str, object] = {"auswahl": len(kandidaten), "uebertragbar": len(nutzbar)}
    kosten = 0.0
    for ann in active_annotators("paper"):
        ohne = {p["id"] for p in main_store.annotations_missing(
            "paper", ann.key, ann.version, nur_neu=True)}
        menge = kandidaten if not ann.only_usable else nutzbar
        offen = len(menge & ohne)
        if ann.key == "fit":
            fit_kand = {p["id"] for p in fit_modul.candidates_for(main_store)}
            offen = len(fit_kand & (ohne | set(main_store.annotations_newer_than(
                "classify", "2", "fit"))))
        aus[f"offen_{ann.key}"] = offen
        kosten += min(offen, ANNOTATE_MAX) * KOSTEN_JE_STUECK.get(ann.key, 0.0)
    haltung = main_store.annotations_for("stance", get_annotator("stance").version)
    ohne_haltung = sum(1 for g in main_store.cluster_members()
                       if g["paper_id"] not in haltung and g["body_id"] != "oldenburg")
    aus["offen_stance_hoechstens"] = ohne_haltung
    kosten += ohne_haltung * KOSTEN_JE_STUECK["stance"]
    aus["geschaetzt_usd_ohne_ernte"] = round(kosten, 2)
    return aus


def main(nur_oldenburg: bool = False, staedte: list[str] | None = None,
         limit: int | None = None) -> dict:
    from datetime import date, timedelta

    db, files_dir, raw_dir = default_paths()
    seit = (date.today() - timedelta(days=RUECKSCHAU_TAGE)).isoformat()
    deckel = limit or ANNOTATE_MAX
    stopp = aus_umgebung(db.parent, MAX_SEKUNDEN, MAX_SEKUNDEN_VORGABE,
                         kosten_variable=MAX_USD, kosten_vorgabe=MAX_USD_VORGABE)
    # Zahlen und Fehlertexte getrennt: So bleibt der Zähler-Teil ein
    # sauberes dict[str, int], und die Klartext-Gründe kommen erst am Ende dazu.
    zaehler: dict[str, int] = {"bodies": 0, "papers_new": 0, "files_fetched": 0,
                               "files_failed": 0, "texts_new": 0, "errors": 0,
                               "papers_total": 0}
    gruende: dict[str, str] = {"mode": "oldenburg" if nur_oldenburg else "full"}
    t0 = time.time()

    def wartet() -> bool:
        """Wartet jemand auf diesen Prozess? Dann keine Stufe mehr BEGINNEN."""
        grund = stopp.grund()
        if grund:
            zaehler[f"abgebrochen_{grund.schluessel}"] = 1
            gruende["abgebrochen"] = grund.text
            logger.info("%s", grund.text)
        return grund is not None

    main_store = CitiesStore(db)
    try:
        vorher = {z["id"]: z["papers"] for z in main_store.stats()}

        # 1. Oldenburg — immer, zuerst, ohne Netz und ohne Modell.
        _oldenburg(main_store, raw_dir, files_dir, zaehler, gruende)

        if not nur_oldenburg:
            _voller_lauf(main_store, raw_dir, files_dir, seit, deckel, staedte,
                         stopp, wartet, zaehler, gruende)

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
    zahlen["cost_usd"] = round(stopp.kosten, 4)
    zahlen["seconds"] = round(time.time() - t0)
    # Ein Teilausfall ist kein „ok". Bis 10/2026 zählte jede Stufe ihren
    # Fehler nur in `errors`, und `run_guarded` buchte den Lauf als gelungen —
    # ein fehlendes Embedding-Modell stand so als `status=ok, errors: 1` im
    # Panel, ohne Mail. Jetzt endet der Lauf rot, die Kennzahlen bleiben
    # (Muster `check_presse`): Das Geschriebene ist geschrieben, der Alarm geht raus.
    if zaehler.get("errors"):
        fehler = "; ".join(f"{k}: {v}" for k, v in gruende.items() if k.startswith("error_"))
        raise JobFehler(f"Städte-Speicher: {zaehler['errors']} Stufe(n) gescheitert — "
                        f"{fehler[:600]}", zahlen)
    return zahlen


def _voller_lauf(main_store: CitiesStore, raw_dir: Path, files_dir: Path, seit: str,
                 deckel: int, staedte: list[str] | None, stopp, wartet,
                 zaehler: dict, gruende: dict) -> None:
    """Die fremden Städte, Einordnung, Gruppen und Urteile — der Sonntag."""
    # 2. Die fremden Städte, eine nach der anderen.
    for spec in active_bodies():
        if spec.dialect == "oldenburg" or (staedte and spec.id not in staedte):
            continue
        if wartet():
            break
        try:
            ernte = pipeline.fetch(spec, raw_dir, files_dir, seit)
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
            # Eine abgebrochene Ernte ist kein Absturz — sie bekommt trotzdem
            # eine Zahl, sonst fällt sie nur dem auf, der das Log liest.
            if ernte.get("abgebrochen"):
                zaehler["harvest_stopped"] = zaehler.get("harvest_stopped", 0) + 1
                gruende[f"stopped_{spec.id}"] = str(ernte["abgebrochen"])
                logger.warning("%s: %s", spec.id, ernte["abgebrochen"])
        except Exception as e:  # noqa: BLE001 — eine Stadt kippt nicht den Lauf
            zaehler["errors"] += 1
            gruende[f"error_{spec.id}"] = f"{type(e).__name__}: {e}"
            logger.warning("%s: %s", spec.id, e)

    # 3. Einordnen über ALLE Städte zusammen — der Deckel gilt für den Lauf,
    #    nicht je Stadt, sonst bekäme die erste Stadt alles.
    try:
        for schluessel, ergebnis in ({} if wartet() else pipeline.annotate(
                main_store, limit=deckel, stopp=stopp, nur_neu=True)).items():
            zaehler["annotated"] = zaehler.get("annotated", 0) + ergebnis["annotated"]
            zaehler["annotate_errors"] = (zaehler.get("annotate_errors", 0)
                                          + ergebnis["errors"])
            gruende[f"cost_{schluessel}"] = f"${ergebnis['cost_usd']:.4f}"
    except Exception as e:  # noqa: BLE001
        zaehler["errors"] += 1
        gruende["error_annotate"] = f"{type(e).__name__}: {e}"

    # 4. Der Index über alle Städte: Text UND Einordnung der neuen Vorlagen.
    try:
        for name, wert in ({} if wartet() else pipeline.index_all(main_store)).items():
            zaehler[f"index_{name}"] = wert
    except Exception as e:  # noqa: BLE001
        zaehler["errors"] += 1
        gruende["error_index"] = f"{type(e).__name__}: {e}"

    # 5. Gruppen über Stadtgrenzen: einbetten, gruppieren (mit festen
    #    Nummern), neue Gruppen gegenlesen, Richtung je Vorlage, Mehrheit je
    #    Stadt — und am Ende `idea_groups` neu (Überschrift, Städte,
    #    Zeitleiste samt Kurztiteln). Nur Zählen; die Modellaufrufe darin
    #    betreffen ausschließlich, was noch kein Urteil hat.
    try:
        for name, wert in ({} if wartet()
                           else pipeline.cluster_all(main_store, stopp=stopp)).items():
            zaehler[f"cluster_{name}"] = wert
    except Exception as e:  # noqa: BLE001
        zaehler["errors"] += 1
        gruende["error_cluster"] = f"{type(e).__name__}: {e}"

    # 6. Das Urteil über Oldenburg — schlank: nur ohne Urteil oder mit neuer
    #    Einordnung. `_fit` rechnet danach den Gruppen-Status und das Urteil
    #    je Idee (Quell-Hash: Was sich nicht geändert hat, kostet nichts).
    try:
        for schluessel, ergebnis in ({} if wartet() else pipeline.annotate(
                main_store, limit=deckel, nach_index=True, stopp=stopp,
                nur_neu=True, schlank=True)).items():
            zaehler["judged"] = zaehler.get("judged", 0) + ergebnis["annotated"]
            for name in ("skipped_no_evidence", "hallucinated_evidence",
                         "claim_without_evidence"):
                if ergebnis.get(name):
                    zaehler[name] = zaehler.get(name, 0) + ergebnis[name]
            idee = ergebnis.get("idea_fit") or {}
            if idee:
                zaehler["ideas_judged"] = idee.get("annotated", 0)
                zaehler["ideas_unchanged"] = idee.get("unchanged", 0)
                gruende["cost_idea_fit"] = f"${idee.get('cost_usd', 0.0):.4f}"
            gruende[f"cost_{schluessel}"] = f"${ergebnis['cost_usd']:.4f}"
    except Exception as e:  # noqa: BLE001
        zaehler["errors"] += 1
        gruende["error_fit"] = f"{type(e).__name__}: {e}"
    # Nach jedem `fit`-Lauf noch einmal: Die Mehrheit je Gruppe hängt an den
    # Urteilen. `_fit` rechnet sie nur, wenn es selbst geurteilt hat.
    try:
        from council.cities.annotators import get as get_annotator
        from council.cities.clusters import CLUSTER_VERSION
        from council.cities.index import EMBED_MODEL
        if not wartet():
            zaehler["group_status"] = main_store.rebuild_group_status(
                EMBED_MODEL, CLUSTER_VERSION, get_annotator("fit").version)
    except Exception as e:  # noqa: BLE001 — Kennzahl, nicht der Lauf
        zaehler["errors"] += 1
        gruende["error_group_status"] = f"{type(e).__name__}: {e}"

    # 7. Das „Warum" — nach `group_status`, weil die Arbeitsliste daran hängt.
    try:
        from council.cities import reasons
        from council.cities.annotators import get as get_annotator
        # Der Annotator steht auf `active=False`, solange sein Prüfstand
        # keinen belastbaren Maßstab hat (s. dort).
        ergebnis = (reasons.run(main_store, limit=REASON_MAX, stopp=stopp)
                    if get_annotator("reason").active and not wartet()
                    else {"annotated": 0, "grounded": 0, "cost_usd": 0.0})
        zaehler["reasons"] = ergebnis["annotated"]
        zaehler["reasons_grounded"] = ergebnis["grounded"]
        gruende["cost_reason"] = f"${ergebnis['cost_usd']:.4f}"
    except Exception as e:  # noqa: BLE001
        zaehler["errors"] += 1
        gruende["error_reason"] = f"{type(e).__name__}: {e}"

    # 8. Ist der Bestand je Stadt plausibel? Am 08.09.2026 lagen vier
    #    Ernte-Fehler gleichzeitig darin, und keiner hat sich gemeldet
    #    (council/cities/pruefung.py zählt sie auf).
    try:
        from council.cities import pruefung
        from council.cities.index import EMBED_MODEL

        befunde = [] if wartet() else pruefung.pruefe(main_store, EMBED_MODEL)
        zaehler["implausibel"] = len(befunde)
        for b in befunde:
            logger.warning("unplausibel: %s", b)
            gruende[f"pruefung_{b.body_id}_{b.regel}"] = f"{b.wert:.2f}"
    except Exception as e:  # noqa: BLE001 — eine Prüfung kippt den Lauf nicht
        zaehler["errors"] += 1
        gruende["error_pruefung"] = f"{type(e).__name__}: {e}"

    # 9. Was ein Versionssprung entwertet hat — als ZAHL, nicht als
    #    Nebenwirkung, die erst in der Laufzeit des nächsten Sonntags auffällt.
    try:
        from council.cities.annotators import active_annotators
        for ann in active_annotators("paper"):
            veraltet = main_store.annotations_altversion(ann.key, ann.version)
            if veraltet:
                zaehler[f"veraltet_{ann.key}"] = veraltet
    except Exception as e:  # noqa: BLE001 — Kennzahl, nicht der Lauf
        zaehler["errors"] += 1
        gruende["error_veraltet"] = f"{type(e).__name__}: {e}"


def _argumente(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Städte-Speicher nachziehen (Cron).")
    p.add_argument("--nur-oldenburg", action="store_true",
                   help="werktags: nur Oldenburg übernehmen, einbetten, Nachbarn — "
                        "ohne Netz und ohne Modell")
    p.add_argument("--staedte", default="",
                   help="nur diese fremden Städte holen (kommagetrennt) — zum Messen")
    p.add_argument("--limit", type=int, default=None,
                   help="Deckel je Stufe statt CITIES_ANNOTATE_MAX — zum Messen")
    p.add_argument("--trocken", action="store_true",
                   help="nur zählen, was offen ist, und die Kosten schätzen")
    return p.parse_args(argv)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    args = _argumente()
    if args.trocken:
        import json
        with CitiesStore(default_paths()[0]) as s:
            print(json.dumps(trocken(s), indent=2, ensure_ascii=False))
        raise SystemExit(0)
    staedte = [x.strip() for x in args.staedte.split(",") if x.strip()] or None
    run_guarded("check_cities", lambda: main(nur_oldenburg=args.nur_oldenburg,
                                             staedte=staedte, limit=args.limit))
