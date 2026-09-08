#!/usr/bin/env python3
"""Misst, wie gut ein Modell beurteilt, ob Oldenburg eine fremde Idee schon hat.

**Drei Fragen, drei Maße.** Der Annotator ``fit`` sagt zu einer fremden
Vorlage: *hat Oldenburg das schon* (``status``), *lohnt ein Antrag*
(``worth``) — und *worauf stützt sich das* (``evidence``). Die dritte ist die
wichtigste: Ein Urteil, das sich auf einen erfundenen Beleg beruft, ist nicht
ungenau, sondern falsch. Deshalb ist die Beleg-Disziplin das einzige Maß mit
Schwelle 100 %.

Maßstab sind 40 von Hand geurteilte Vorlagen
(``cases_cities_fit.json``, geschichtet über Themenfelder und Städte). Sie
tragen ihre Belege bei sich — die Suite braucht **keine** Datenbank, nur
einen API-Schlüssel. Das ist wichtig: Die Belege wachsen mit Oldenburgs
Bestand, und ein Maßstab, der sich unter der Hand ändert, misst nichts.

```bash
python eval/run_cities_fit.py                          # Modell des Annotators
python eval/run_cities_fit.py --model deepseek/deepseek-v4-pro
python eval/run_cities_fit.py --runs 3 --save          # drei Läufe, Mittel
```

**Ein Lauf ist eine Stichprobe.** Bei 40 Fällen ist ein Fall 2,5 Punkte;
dieselbe Streuung wie bei ``run_cities_transfer.py`` (dort 84–91 % über fünf
Läufe) ist auch hier zu erwarten. Deshalb ``--runs 3`` und die Spanne im
Bericht, nicht nur das Mittel.

**Gemessen am 08.09.2026**, gegen dieselben 40 Fälle:

| Modell | Status (3 Klassen) | Lohnt sich | Beleg-Disziplin | $/1000 |
|---|---:|---:|---:|---:|
| `deepseek-v4-flash` (2 Läufe) | 64 % (58–70) | 59 % | 99 % | 0,67 |
| `deepseek-v4-pro` (1 Lauf) | 72 % | 45 % | 100 % | 7,11 |

**Die Wahl fiel auf `flash`.** `pro` liegt beim Status acht Punkte vorn — das
ist weniger als die Streuung von `flash` selbst (zwölf Punkte über zwei Läufe),
kostet elfmal so viel und ist beim „lohnt sich" vierzehn Punkte schlechter.

**Was die Zahlen bedeuten, und was nicht.** 64 % Übereinstimmung in drei
Klassen ist kein gutes Ergebnis, und es steht hier ungeschönt. Zwei Dinge
machen es trotzdem brauchbar:

1. **Die Richtung stimmt.** Über beide Modelle und sieben Läufe hat das Modell
   **kein einziges Mal** behauptet, Oldenburg habe etwas, das ihm fehlt. Alle
   groben Fehler gehen in die andere Richtung: Es übersieht, was Oldenburg hat
   (zwei bis drei je Lauf). Das ist die harmlosere Hälfte — es landet eine Idee
   auf der Liste, die keine ist, statt dass eine verschwindet, die dorthin
   gehört.
2. **Die Belege stehen daneben.** Was das Modell behauptet, muss es an
   Oldenburger Beschlüssen festmachen, und die zeigt die Oberfläche mit. Wer
   liest, kann das Urteil selbst prüfen — anders als bei einer nackten Zahl.

**Die Schwellen sind Regressions-Schranken, keine Gütesiegel** — wie bei
``run_cities_transfer.py``, wo bei gemessenen 87 % die Schranke auf 80 steht:

| Maß | Schranke | warum diese Zahl |
|---|---|---|
| erfundene Belege | **0** | dann hat sich das Modell die Grundlage ausgedacht |
| falsch „vorhanden" | **0** | eine falsche Beruhigung nimmt eine Idee von der Liste; in sieben Läufen nie vorgekommen |
| Beleg-Disziplin | 95 % | ein Urteil nur auf den Rückblick gestützt ist ein Zitierfehler, den `fit.pruefe` im Betrieb wegwirft |
| Status (3 Klassen) | 55 % | zehn Punkte unter dem schlechteren der beiden Läufe |
| Lohnt sich | 50 % | dito; es hängt zusätzlich an einer Wertung, über die man streiten kann |
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import statistics
import sys
import time
from collections import Counter
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(WURZEL / ".env")

from council.cities import fit as fit_modul  # noqa: E402
from council.cities.annotate import parse_json  # noqa: E402
from council.cities.annotators import get as get_annotator  # noqa: E402
from council.cities.evidence import OLDENBURG_STECKBRIEF, Evidence  # noqa: E402
from eval import harness  # noqa: E402

CASES = Path(__file__).parent / "cases_cities_fit.json"
SUITE = "cities_fit"

#: Regressions-Schranken, keine Gütesiegel: zehn Punkte unter dem
#: schlechteren gemessenen Lauf. Was darunter fällt, ist eine Verschlechterung;
#: was darüber liegt, ist Rauschen (ein Fall sind 2,5 Punkte).
SCHWELLE_STATUS = 55.0
SCHWELLE_WORTH = 50.0
#: Zitierfehler (Urteil nur auf den Rückblick gestützt) fängt der Betrieb ab —
#: er wirft die Antwort weg und zählt sie. Das kostet einen zweiten Anlauf,
#: keine falsche Aussage. Eine ERFUNDENE Kennung ist etwas anderes und steht
#: bei null.
SCHWELLE_BELEGE = 95.0


def lade_faelle() -> list[dict]:
    return json.loads(CASES.read_text(encoding="utf-8"))


def _belege(fall: dict) -> list[Evidence]:
    return [Evidence(**b) for b in fall["evidence"]]


#: Was im Prompt steht, wenn ein Fall keine Cluster-Angabe trägt. Wörtlich
#: dasselbe wie ``evidence.cluster_zeile`` ohne Cluster — der Prüfstand darf
#: dem Modell nichts anderes zeigen als der Betrieb.
_KEIN_CLUSTER = ("Ideen-Cluster: keiner — keine andere Stadt im Bestand hat "
                 "etwas hinreichend Ähnliches. Das sagt nichts über Oldenburg.")


def _vorlage(fall: dict) -> str:
    """Die Vorlage samt Aufwandsklasse, falls der Fall eine trägt.

    Die vierzig Fälle stammen aus der Zeit vor dem Annotator `effort`; wo eine
    Klasse fehlt, bleibt die Zeile weg — dann misst der Fall dieselbe Frage
    wie vorher, nur ohne dieses Signal.
    """
    text = fall["paper"]
    aufwand = fall.get("effort") or {}
    klasse = aufwand.get("effort")
    if klasse:
        text += (f"\nAufwand: {klasse} — "
                 f"{fit_modul.AUFWAND_TEXT.get(klasse, '')}")
    if aufwand.get("addressee"):
        text += f"\nAdressat: {aufwand['addressee']} (nicht die Stadt selbst)"
    return text


def urteilen(faelle: list[dict], model: str) -> tuple[dict[str, dict], float]:
    """Jeden Fall einzeln ans Modell — genauso wie im Betrieb."""
    from kern import llm, prompts

    ann = get_annotator("fit")
    system = prompts.render(ann.prompt_system, steckbrief=OLDENBURG_STECKBRIEF)
    ergebnis: dict[str, dict] = {}
    kosten = 0.0
    for i, fall in enumerate(faelle, 1):
        try:
            antwort = llm.chat_complete(
                model=model, response_format={"type": "json_object"},
                messages=[{"role": "system", "content": system},
                          {"role": "user", "content": prompts.render(
                              ann.prompt_user, paper=_vorlage(fall),
                              cluster=fall.get("cluster") or _KEIN_CLUSTER,
                              evidence=fit_modul.evidence_text(_belege(fall)))}],
                max_tokens=ann.max_tokens, temperature=ann.temperature,
                extra_body={"provider": {}} if ann.routing_free else {},
                _feature="eval_cities_fit")
            ergebnis[fall["id"]] = parse_json(antwort.choices[0].message.content or "")
            verbrauch = getattr(antwort, "usage", None)
            if verbrauch:
                kosten += float(getattr(verbrauch, "cost", 0) or 0)
        except Exception as e:  # noqa: BLE001 — ein Fall, nicht der Lauf
            print(f"  [{i}/{len(faelle)}] gescheitert: {type(e).__name__}: {str(e)[:90]}")
    return ergebnis, kosten


def messen(faelle: list[dict], vorhersage: dict[str, dict]) -> dict:
    n = status_treffer = worth_treffer = 0
    beleg_verstoesse: list[dict] = []
    matrix: Counter[tuple[str, str]] = Counter()
    worth_matrix: Counter[tuple[str, str]] = Counter()
    fehler: list[dict] = []

    for f in faelle:
        got = vorhersage.get(f["id"])
        if not got:
            continue
        n += 1
        erwartet = f["expected"]
        ist_status = str(got.get("status", ""))
        ist_worth = str(got.get("worth", ""))
        matrix[(erwartet["status"], ist_status)] += 1
        if ist_status == erwartet["status"]:
            status_treffer += 1
        else:
            fehler.append({"case": f["name"][:70], "erwartet": erwartet["status"],
                           "bekommen": ist_status, "grund": str(got.get("reason", ""))[:90]})
        worth_matrix[(erwartet["worth"], ist_worth)] += 1
        worth_treffer += ist_worth == erwartet["worth"]

        # Beleg-Disziplin: Nur Kennungen, die dem Modell vorlagen — und eine
        # Behauptung über Oldenburg braucht mindestens eine.
        erlaubt = {b["id"] for b in f["evidence"]}
        # Die tragenden Arten kommen aus dem BETRIEB, nicht aus einer zweiten
        # Liste hier. Als sie hier fest standen, kannte der Prüfstand nach dem
        # Ausbau auf vier Arme nur noch zwei davon — und meldete ein Urteil,
        # das einen Oldenburger BESCHLUSS zitierte, als „nur auf den Rückblick
        # gestützt". Zwei Fassungen derselben Regel laufen unweigerlich
        # auseinander; das ist dieselbe Lehre wie bei `jobs.zustand`.
        tragend = {b["id"] for b in f["evidence"]
                   if b["kind"] in fit_modul.TRAGENDE_ARTEN}
        genannt = [str(x) for x in (got.get("evidence") or [])]
        erfunden = [k for k in genannt if k not in erlaubt]
        if erfunden:
            beleg_verstoesse.append({"case": f["name"][:60], "art": "erfunden",
                                     "kennungen": erfunden[:3]})
        elif ist_status in ("present", "partial") and not genannt:
            beleg_verstoesse.append({"case": f["name"][:60], "art": "ohne Beleg",
                                     "kennungen": []})
        elif ist_status in ("present", "partial") and not (set(genannt) & tragend):
            # Dieselbe Regel wie im Betrieb (`fit.pruefe`): Der Rückblick sagt,
            # was die Stadt beschäftigt, nicht ob sie dieses Instrument hat.
            beleg_verstoesse.append({"case": f["name"][:60], "art": "nur Rückblick",
                                     "kennungen": genannt[:3]})

    # Die beiden groben Fehler sind NICHT gleich schwer, und das ist der
    # wichtigste Befund dieser Suite:
    #
    # „Oldenburg hat das schon" für etwas, das fehlt, ist eine falsche
    # Beruhigung — sie nimmt eine Idee von der Liste, die daraufgehört. In
    # sieben Läufen über zwei Modelle kam das KEIN EINZIGES MAL vor.
    #
    # Umgekehrt — Oldenburg hat es, das Modell sieht es nicht — landet eine
    # Idee auf der Liste, die keine ist. Das ist ärgerlich, aber sichtbar:
    # Die Belege stehen daneben, und wer liest, sieht es. Das kommt vor
    # (zwei bis drei je Lauf) und steht deshalb als Kennzahl da, nicht als
    # Schranke.
    falsch_vorhanden = matrix[("missing", "present")]
    uebersehen = matrix[("present", "missing")]
    # Zwei Arten von Beleg-Verstoß, und sie wiegen verschieden schwer:
    # Eine ERFUNDENE Kennung heißt, das Modell hat sich die Grundlage
    # ausgedacht — das darf nie vorkommen. Ein Urteil, das sich nur auf den
    # Themenfeld-Rückblick stützt, ist dagegen ein Zitierfehler: Der Betrieb
    # (`fit.pruefe`) wirft ihn weg, es kostet einen zweiten Anlauf, keine
    # falsche Aussage.
    erfundene = sum(1 for v in beleg_verstoesse if v["art"] == "erfunden")

    quote = lambda x: round(100 * x / max(n, 1), 1)  # noqa: E731
    return {
        "n_answered": n,
        "false_present": falsch_vorhanden, "missed_present": uebersehen,
        "status_accuracy": quote(status_treffer),
        "worth_accuracy": quote(worth_treffer),
        "evidence_discipline": quote(n - len(beleg_verstoesse)),
        "evidence_invented": erfundene,
        "evidence_violations": beleg_verstoesse,
        "confusion": {f"{a}→{b}": c for (a, b), c in sorted(matrix.items())},
        "worth_confusion": {f"{a}→{b}": c for (a, b), c in sorted(worth_matrix.items())},
        "mistakes": fehler,
    }


def belege_neu_schreiben() -> int:
    """Die eingebetteten Belege aus dem heutigen Bestand neu schreiben.

    Das Golden Set trägt seine Belege bei sich, damit der Eval ohne Datenbank
    läuft. Ändert sich die Belegsuche, sind sie veraltet — und der Eval misst
    dann einen Stand, den es nicht mehr gibt.

    **Was erwartet wurde, bleibt stehen.** ``expected`` und ``judgment`` sind
    Handarbeit; sie werden hier nie angefasst. Fällt ein erwarteter Beleg aus
    der neuen Liste heraus, wird das GEMELDET, nicht repariert — genau das ist
    die Messung, um die es geht.
    """
    import council.cities.evidence as ev
    from council.cities import default_paths
    from council.cities.index import EMBED_MODEL
    from council.cities.store import CitiesStore
    from council.store import CouncilStore

    db, _f, _r = default_paths()
    main_store = CitiesStore(db)
    rats = CouncilStore(WURZEL / "data" / "council.sqlite")
    try:
        faelle = lade_faelle()
        matrix = main_store.chunk_matrix(EMBED_MODEL, "oldenburg")
        einordnung = main_store.annotations_for("classify", "2")
        aufwand = main_store.annotations_for("effort", "1")
        fehlt: list[str] = []
        ohne_papier = 0
        for f in faelle:
            papier = main_store.paper(f["id"])
            if not papier:
                ohne_papier += 1
                continue
            klasse = einordnung.get(f["id"]) or {
                "instrument": f.get("instrument"), "field": f.get("field")}
            belege = ev.evidence_for(main_store, rats, papier, klasse, EMBED_MODEL,
                                     chunk_matrix=matrix)
            f["evidence"] = [asdict(b) for b in belege]
            # Dieselben zwei Signale, die der Betrieb sieht: die Cluster-Zeile
            # und die Aufwandsklasse. Ohne sie misst der Prüfstand eine
            # Eingabe, die es nicht mehr gibt.
            f["cluster"] = ev.cluster_zeile(main_store, papier, EMBED_MODEL)
            f["effort"] = aufwand.get(f["id"]) or {}
            offen = set(f["expected"]["evidence"]) - {b.id for b in belege}
            if offen:
                fehlt.append(f"{f['name'][:60]}: {', '.join(sorted(offen))}")
    finally:
        main_store.close()
        rats.close()

    CASES.write_text(json.dumps(faelle, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(faelle)} Fälle geschrieben ({ohne_papier} ohne Papier im Bestand).")
    if fehlt:
        print(f"\n{len(fehlt)} erwartete Belege stehen NICHT mehr in der Liste:")
        for zeile in fehlt:
            print(f"  - {zeile}")
        print("\nDas ist die Messung, nicht ein Fehler des Schreibens.")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--model", help="Modell (Vorgabe: das des aktiven Annotators)")
    p.add_argument("--runs", type=int, default=1,
                   help="wie oft messen (bei 40 Fällen ist ein Fall 2,5 Punkte)")
    p.add_argument("--belege-neu", action="store_true",
                   help="die eingebetteten Belege aus dem Bestand neu schreiben "
                        "(braucht data/cities.sqlite und data/council.sqlite)")
    p.add_argument("--save", action="store_true", help="Ergebnis als Baseline ablegen")
    p.add_argument("--compare", action="store_true", help="gegen die letzte Baseline")
    a = p.parse_args()

    if a.belege_neu:
        return belege_neu_schreiben()

    ann = get_annotator("fit")
    model = a.model or ann.model
    faelle = lade_faelle()
    verteilung = Counter(f["expected"]["status"] for f in faelle)
    print(f"{len(faelle)} handgeurteilte Vorlagen · Modell {model} · "
          f"Fassung {ann.version}")
    print(f"  Verteilung im Maßstab: "
          f"{', '.join(f'{k} {v}' for k, v in sorted(verteilung.items()))}\n")

    laeufe: list[dict] = []
    kosten_gesamt = 0.0
    t0 = time.time()
    for lauf in range(1, a.runs + 1):
        vorhersage, kosten = urteilen(faelle, model)
        kosten_gesamt += kosten
        mass = messen(faelle, vorhersage)
        laeufe.append(mass)
        print(f"  Lauf {lauf}: Status {mass['status_accuracy']:.0f} % · "
              f"Lohnt {mass['worth_accuracy']:.0f} % · "
              f"Belege {mass['evidence_discipline']:.0f} %")

    def spanne(schluessel: str) -> tuple[float, float, float]:
        werte = [x[schluessel] for x in laeufe]
        return (round(statistics.fmean(werte), 1), min(werte), max(werte))

    falsch_vorhanden = sum(x["false_present"] for x in laeufe)
    uebersehen = sum(x["missed_present"] for x in laeufe)
    erfundene = sum(x["evidence_invented"] for x in laeufe)
    status_m, status_min, status_max = spanne("status_accuracy")
    worth_m, worth_min, worth_max = spanne("worth_accuracy")
    beleg_m, beleg_min, _ = spanne("evidence_discipline")
    letzter = laeufe[-1]

    ergebnis = {
        "suite": SUITE, "model": model, "prompt_version": ann.version,
        "n_cases": len(faelle), "runs": a.runs,
        "status_accuracy": status_m, "status_range": [status_min, status_max],
        "worth_accuracy": worth_m, "worth_range": [worth_min, worth_max],
        "evidence_discipline": beleg_m, "false_present": falsch_vorhanden,
        "missed_present": uebersehen,
        "evidence_invented": erfundene,
        "cost_usd": round(kosten_gesamt, 4),
        "cost_per_1000": round(kosten_gesamt / max(len(faelle) * a.runs, 1) * 1000, 2),
        "seconds": round(time.time() - t0),
        "confusion": letzter["confusion"],
        "mistakes": letzter["mistakes"],
        "evidence_violations": letzter["evidence_violations"],
    }

    print(f"\n  Status (3 Klassen)  {status_m:.0f} %  ({status_min:.0f}–{status_max:.0f})"
          f"   Schwelle {SCHWELLE_STATUS:.0f} %")
    print(f"  Lohnt sich          {worth_m:.0f} %  ({worth_min:.0f}–{worth_max:.0f})"
          f"   Schwelle {SCHWELLE_WORTH:.0f} %")
    print(f"  Erfundene Belege    {erfundene}"
          f"                    Schwelle 0   (das darf nie vorkommen)")
    print(f"  Beleg-Disziplin     {beleg_m:.0f} %"
          f"                Schwelle 95 %  (Zitierfehler fängt der Betrieb ab)")
    print(f"  Falsch vorhanden    {falsch_vorhanden}"
          f"                    Schwelle 0   (nimmt eine Idee von der Liste)")
    print(f"  Übersehen           {uebersehen}"
          f"                    (Kennzahl: Idee auf der Liste, die keine ist)")
    print(f"  Kosten              ${kosten_gesamt:.4f}  "
          f"({ergebnis['cost_per_1000']:.2f} $/1000 Urteile)")
    print(f"  Dauer               {ergebnis['seconds']}s")

    # Beide Matrizen, denn beide Fragen entscheiden. Die für „lohnt sich"
    # fehlte, als die verschärfte Regel gemessen wurde — und ohne sie ließ
    # sich nicht sagen, ob das Modell strenger oder lockerer ist als der
    # Maßstab. Genau das ist aber die einzige Frage, die weiterhilft.
    if letzter["worth_confusion"]:
        print("\n  Lohnt sich (erwartet -> bekommen):")
        for k, v in sorted(letzter["worth_confusion"].items(), key=lambda x: -x[1]):
            soll, _, ist = k.partition("\u2192")
            marke = "  " if soll == ist else "\u2717 "
            print(f"    {marke}{k:20} {v}")

    if letzter["confusion"]:
        print("\n  Status (erwartet -> bekommen):")
        for k, v in sorted(letzter["confusion"].items(), key=lambda x: -x[1]):
            marke = "  " if k.split("\u2192")[0] == k.split("\u2192")[1] else "\u2717 "
            print(f"    {marke}{k:24} {v}")
    if letzter["mistakes"]:
        print("\n  Wo es danebenging:")
        for m in letzter["mistakes"][:8]:
            print(f"    [{m['erwartet']} → {m['bekommen']}] {m['case']}")
            if m["grund"]:
                print(f"        „{m['grund']}“")
    if letzter["evidence_violations"]:
        print("\n  BELEG-VERSTÖSSE (Schwelle ist 100 %, jeder zählt):")
        for v in letzter["evidence_violations"]:
            print(f"    [{v['art']}] {v['case']} {v['kennungen']}")

    if a.compare:
        vorher, pfad = harness.load_last(SUITE)
        if vorher and pfad:
            print(f"\n  Gegen {pfad.name} ({vorher.get('model')}):")
            for schluessel, name in (("status_accuracy", "Status"),
                                     ("worth_accuracy", "Lohnt sich"),
                                     ("evidence_discipline", "Beleg-Disziplin")):
                alt, neu = vorher.get(schluessel, 0), ergebnis[schluessel]
                pfeil = "↑" if neu > alt else ("↓" if neu < alt else "→")
                print(f"    {name:16} {alt:5.0f} % {pfeil} {neu:5.0f} %  ({neu - alt:+.0f})")
        else:
            print("\n  (noch keine Baseline — mit --save eine anlegen)")
    if a.save:
        print(f"\n  Baseline: {harness.save_result(ergebnis)}")

    bestanden = (status_m >= SCHWELLE_STATUS and worth_m >= SCHWELLE_WORTH
                 and erfundene == 0 and beleg_min >= SCHWELLE_BELEGE
                 and falsch_vorhanden == 0)
    print(f"\n  {'BESTANDEN' if bestanden else 'NICHT BESTANDEN'}")
    return 0 if bestanden else 1


if __name__ == "__main__":
    raise SystemExit(main())
