#!/usr/bin/env python3
"""Die Messungen vor 11/2026 ins Laufformat übertragen (``kern/benchmarks.py``).

Bis zum Benchmark-Bereich im Admin-Panel schrieb jede Suite ihr eigenes JSON
nach ``eval/results/``, die Gold-Läufe standen nur im Messbuch
(``docs/gold-messbuch.md``). Dieses Skript macht aus jedem Rohergebnis einen
Lauf unter ``eval/runs/<benchmark>/`` — mit dem, was sich nachträglich noch
sagen lässt, und ohne etwas zu erfinden:

- **Code-Stand** ist der Commit, mit dem das Rohergebnis eingecheckt wurde
  (``code.checked_in``) — der Stand, auf dem gemessen wurde, liegt davor.
- **Fälle** sind die Falldatei in genau diesem Commit (Prüfsumme und Zahl);
  so erkennt das Panel, ob sich die Fälle seither geändert haben.
- **Modelle** stehen nur da, wo das Rohergebnis sie nennt. Fehlt eins, bleibt
  das Feld leer statt geraten.
- **Umgebung** ``unknown``, wo sie nirgends steht.

Läuft beliebig oft: Ein Rohergebnis, zu dem es schon einen Lauf gibt, wird
übersprungen — ein von Hand ergänztes Fazit überlebt also. Neue Ergebnisse
einer Suite, die ihre Läufe noch nicht selbst schreibt, holt derselbe Aufruf
nach; ``tests/test_benchmarks.py`` meldet jedes Rohergebnis ohne Lauf.

    python eval/runs_backfill.py              # zeigt, was entstünde
    python eval/runs_backfill.py --schreiben  # legt die Läufe an
"""
from __future__ import annotations

import argparse
import functools
import hashlib
import json
import re
import statistics
import subprocess
import sys
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import Any

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL))

from kern import benchmarks as bm  # noqa: E402

ERGEBNISSE = WURZEL / "eval" / "results"

#: Rohergebnisse ohne Lauf — mit Grund. ``tests/test_benchmarks.py`` hält die
#: Liste in beiden Richtungen.
OHNE_LAUF: dict[str, str] = {
    "eval/results/digest/": "Suite aus der Zeitungs-Zeit (bis 08/2026), den Code gibt es nicht mehr",
    "eval/results/verify/": "Suite aus der Zeitungs-Zeit (bis 08/2026), den Code gibt es nicht mehr",
}


# --------------------------------------------------------------------------- #
# Git: wann eingecheckt, und wie sahen die Fälle damals aus?
# --------------------------------------------------------------------------- #

def _git(*args: str) -> str | None:
    aus = subprocess.run(["git", *args], cwd=WURZEL, capture_output=True, text=True)
    return aus.stdout.strip() if aus.returncode == 0 and aus.stdout.strip() else None


@functools.cache
def eingecheckt(pfad: str) -> tuple[str, str] | None:
    """(Commit, ISO-Zeit) des Commits, der ``pfad`` angelegt hat."""
    zeile = _git("log", "--diff-filter=A", "--follow", "--format=%h %cI", "-1", "--", pfad)
    if not zeile:
        return None
    commit, zeit = zeile.split(" ", 1)
    return commit, zeit


@functools.cache
def faelle_damals(pfad: str, commit: str) -> dict[str, Any] | None:
    """Prüfsumme und Fallzahl der Falldatei in ``commit`` (wie ``bm.dataset_state``)."""
    aus = subprocess.run(["git", "show", f"{commit}:{pfad}"], cwd=WURZEL, capture_output=True)
    if aus.returncode != 0:
        return None
    roh = aus.stdout
    n = None
    try:
        inhalt = json.loads(roh)
        if isinstance(inhalt, dict):
            inhalt = next((inhalt[k] for k in ("cases", "faelle", "golden")
                           if isinstance(inhalt.get(k), list)), None)
        if isinstance(inhalt, list):
            n = len(inhalt)
    except ValueError:
        pass
    return {"path": pfad, "sha256": hashlib.sha256(roh).hexdigest()[:12], "cases": n}


def rel(pfad: Path) -> str:
    return pfad.relative_to(WURZEL).as_posix()


def lauf(benchmark: str, roh: Path | str, *, started_at: str, metrics: dict[str, Any],
         cases: str | None | bool = True, sample: int | None = None, **felder: Any) -> dict[str, Any]:
    """Ein Lauf aus einem Rohergebnis. ``cases=True``: die erste Falldatei des Katalogs."""
    raw = rel(roh) if isinstance(roh, Path) else roh
    b = bm.benchmark(benchmark)
    check = eingecheckt(raw) if not raw.startswith("server:") else None
    pfad = (b.cases[0] if b.cases else None) if cases is True else (cases or None)
    dataset = faelle_damals(pfad, check[0]) if (pfad and check) else None
    if sample:
        dataset = {**(dataset or {"path": None, "sha256": None, "cases": None}), "sample": sample}
    rec = bm.new_run(
        benchmark, metrics=metrics, started_at=datetime.fromisoformat(started_at),
        environment=felder.pop("environment", "unknown"),
        code=({"commit": check[0], "checked_in": True} if check else felder.pop("code", None)) or {},
        raw=raw, source=felder.pop("source", "eval/runs_backfill.py"), **felder)
    rec["dataset"] = dataset
    if not rec["code"]:
        rec["code"] = None
    return rec


def _iso_aus_stempel(text: str) -> str | None:
    for muster, fmt in ((r"(\d{8}-\d{6})", "%Y%m%d-%H%M%S"), (r"(\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})",
                        "%Y-%m-%d_%H-%M-%S"), (r"(\d{8}-\d{4})", "%Y%m%d-%H%M"), (r"(\d{8})", "%Y%m%d")):
        m = re.search(muster, text)
        if m:
            return datetime.strptime(m.group(1), fmt).isoformat()
    return None


# --------------------------------------------------------------------------- #
# Die Quellen
# --------------------------------------------------------------------------- #

def aus_pruefstand() -> Iterator[dict[str, Any]]:
    from eval import pruefstand as ps
    for pfad in sorted((ERGEBNISSE / "pruefstand").glob("*/**/*.json")):
        e = json.loads(pfad.read_text(encoding="utf-8"))
        if e.get("suite") not in ps.SUITEN:
            continue
        archiv = pfad.parent.name if pfad.parent.parent.name != "pruefstand" else None
        felder = ps.laufkarte_felder(e, archiv)
        start = felder.pop("started_at")
        yield lauf(e["suite"], pfad, started_at=start.isoformat() if start else _iso_aus_stempel(pfad.name) or "",
                   environment="local", source="eval/pruefstand.py", **felder)


def aus_fakten() -> Iterator[dict[str, Any]]:
    """Die Fakten-Läufe. Frühe Läufe mischten Haushalt und Rat — je Teil ein Lauf."""
    teile = {"fakten-haushalt": ("hh",), "fakten-rat": ("rat", "lotti")}
    for pfad in sorted((ERGEBNISSE / "fakten").glob("**/*.json")):
        if rel(pfad) in vom_pruefstand():
            continue  # der Prüfstand hat seinen Lauf schon geschrieben
        e = json.loads(pfad.read_text(encoding="utf-8"))
        start = _iso_aus_stempel(e.get("zeitstempel") or pfad.name) or ""
        stichprobe = pfad.parent.name == "stichprobe"
        if e.get("kanal") == "deep":
            k = e["kennzahlen"]
            yield lauf("fakten-deep", pfad, started_at=start, cases=None,
                       metrics={bm.QUALITY: k.get("quote_ok"), "cases": k.get("n_cases"),
                                **{x: k.get(x) for x in ("kontextfehler", "modellfehler", "erfunden")}},
                       models={"deep_report": e["modell"]}, variant=f"Aufwand {e['aufwand']}" if e.get("aufwand") else None,
                       label=e.get("etikett"), cost_usd=e.get("kosten_usd"), environment="local",
                       note="Fälle aus Haushalt und Rat gemischt")
            continue
        for benchmark, praefixe in teile.items():
            faelle = [f for f in e["faelle"] if f["id"].split("-")[0] in praefixe]
            if not faelle:
                continue
            ok = sum(1 for f in faelle if f.get("fehlerart") == "ok")
            arten = [f.get("fehlerart") or "" for f in faelle]
            gemischt = len(faelle) < len(e["faelle"])
            yield lauf(benchmark, pfad, started_at=start,
                       metrics={bm.QUALITY: round(ok / len(faelle), 4), "cases": len(faelle),
                                "kontextfehler": sum(a.startswith("kontext") for a in arten),
                                "modellfehler": sum(a.startswith("modell") for a in arten),
                                bm.HARD: sum(a == "modell_erfunden" for a in arten)},
                       models={"qa_answer": e["modell"], "assistant_explain": e["modell"]},
                       label=e.get("etikett"), environment="local", sample=len(faelle) if stichprobe else None,
                       comparable=not stichprobe,
                       cost_usd=None if gemischt else e.get("kosten_usd"),
                       note=" · ".join(t for t in (
                           "aus einem gemeinsamen Lauf über Haushalt und Rat herausgerechnet" if gemischt else None,
                           f"Stichprobe ({len(faelle)} Fälle)" if stichprobe else None,
                           "ohne ZDR gemessen" if e.get("ohne_zdr") else None) if t) or None)


@functools.cache
def vom_pruefstand() -> frozenset[str]:
    """Rohergebnisse, die ein Prüfstand-Lauf mitgeschrieben oder übernommen hat
    (``roh.datei`` der Fakten-Suiten, ``quelle`` der übernommenen Lotti-Läufe) —
    ihr Lauf ist der des Prüfstands, ein zweiter wäre eine Dublette."""
    aus: set[str] = set()
    for p in (ERGEBNISSE / "pruefstand").rglob("*.json"):
        e = json.loads(p.read_text(encoding="utf-8"))
        aus |= {x for x in (e.get("quelle"), (e.get("roh") or {}).get("datei")) if x}
    return frozenset(aus)


def aus_qa() -> Iterator[dict[str, Any]]:
    for pfad in sorted((ERGEBNISSE / "qa").glob("*.json")):
        e = json.loads(pfad.read_text(encoding="utf-8"))
        arm = (e.get("arms") or {}).get("mit_tragweite") or {}
        ret = e.get("retrieval") or {}
        yield lauf("ki-frage", pfad, started_at=e.get("timestamp") or _iso_aus_stempel(pfad.name) or "",
                   metrics={bm.QUALITY: arm.get("cite_expected_rate"), bm.HARD: arm.get("lead_formality_cases"),
                            "retrieval_hit_rate": ret.get("hit_rate"), "mrr": ret.get("mrr"),
                            "cases": e.get("cases")},
                   cost_usd=(e.get("kosten") or {}).get("lauf_usd"), note="Modelle nicht erfasst")


def aus_harness() -> Iterator[dict[str, Any]]:
    for ordner, benchmark in (("watcher", "watcher"), ("committee", "ausschuss")):
        for pfad in sorted((ERGEBNISSE / ordner).glob("*.json")):
            e = json.loads(pfad.read_text(encoding="utf-8"))
            q = e.get("f1") if ordner == "watcher" else (
                (e["tp"] + (e.get("tn") or 0)) / e["cases"] if e.get("cases") else None)
            yield lauf(benchmark, pfad, started_at=e["timestamp"],
                       metrics={bm.QUALITY: q, bm.HARD: e.get("fp") if ordner == "watcher" else e.get("fn"),
                                "cases": e.get("cases"), "precision": e.get("precision"),
                                "recall": e.get("recall")},
                       note="Modell nicht erfasst; Fallliste von damals (drei Fälle)")


def aus_cities() -> Iterator[dict[str, Any]]:
    for ordner, benchmark, schritt in (("cities_transfer", "cities-einordnung", "cities_classify"),
                                       ("cities_fit", "cities-fit", "cities_fit")):
        for pfad in sorted((ERGEBNISSE / ordner).glob("*.json")):
            e = json.loads(pfad.read_text(encoding="utf-8"))
            if ordner == "cities_transfer":
                m = {bm.QUALITY: e["usable_accuracy"] / 100, "transfer": e.get("transfer_accuracy"),
                     "field": e.get("field_accuracy")}
            else:
                m = {bm.QUALITY: e["status_accuracy"] / 100,
                     bm.HARD: (e.get("evidence_invented") or 0) + (e.get("false_present") or 0),
                     "evidence_discipline": e.get("evidence_discipline")}
            yield lauf(benchmark, pfad, started_at=_iso_aus_stempel(pfad.name) or "",
                       metrics={**m, "cases": e.get("n_cases")}, models={schritt: e["model"]},
                       cost_usd=e.get("cost_usd"), duration_s=e.get("seconds"), environment="local",
                       note=f"Prompt-Fassung {e.get('prompt_version')}")


def aus_deep_gold() -> Iterator[dict[str, Any]]:
    for pfad in sorted((ERGEBNISSE / "deep_gold").glob("*.json")):
        e = json.loads(pfad.read_text(encoding="utf-8"))
        faelle = e.get("cases") or []
        check = eingecheckt(rel(pfad))
        modelle = sorted({f.get("model") for f in faelle if f.get("model")})
        yield lauf("deep-gold", pfad, started_at=check[1][:19] if check else "",
                   label=e.get("label"), judge=e.get("judge"), sample=len(faelle), comparable=False,
                   metrics={"coverage": statistics.mean(f["wertung"]["abdeckung"] for f in faelle) if faelle else None,
                            "passed": sum(1 for f in faelle if f["wertung"].get("bestanden")), "cases": len(faelle)},
                   models={"deep_report": modelle[0]} if len(modelle) == 1 else {},
                   cost_usd=e.get("kosten_usd"), data=e.get("db"),
                   note=f"Teillauf ({len(faelle)} Fall) — Zeitpunkt = Commit, mit dem er eingecheckt wurde")


def aus_quality() -> Iterator[dict[str, Any]]:
    pfad = ERGEBNISSE / "quality" / "urteile-vorher-vs-nachher.json"
    if not pfad.exists():
        return
    urteile = json.loads(pfad.read_text(encoding="utf-8"))
    check = eingecheckt(rel(pfad))
    gesamt = [u.get("gesamt") for u in urteile]
    nachher = json.loads((ERGEBNISSE / "quality" / "nachher.json").read_text(encoding="utf-8"))
    yield lauf("qualitaet-vorher-nachher", pfad, started_at=check[1][:19] if check else "",
               metrics={"win_rate": round(gesamt.count("nachher") / len(gesamt), 4), "ties": gesamt.count("gleich"),
                        "cases": len(gesamt)},
               judge="google/gemini-3.5-flash", label="vorher gegen nachher", data=nachher.get("db"),
               raw_extra=[rel(ERGEBNISSE / "quality" / n) for n in
                          ("vorher.json", "nachher.json", "report-vorher-vs-nachher.md")],
               note="Zeitpunkt = Commit, mit dem er eingecheckt wurde")


def aus_ergebnis_texte() -> Iterator[dict[str, Any]]:
    for pfad in sorted((ERGEBNISSE / "ergebnis_texte").glob("*.json")):
        e = json.loads(pfad.read_text(encoding="utf-8"))
        arten = [a for t in e["textarten"].values() for a in t]
        bestanden, faelle = sum(a["bestanden"] for a in arten), sum(a["faelle"] for a in arten)
        yield lauf("ergebnis-texte", pfad, started_at=e["zeit"], label=e.get("etikett"),
                   metrics={"passed_share": round(bestanden / faelle, 4) if faelle else None, "cases": faelle},
                   environment="local", note=f"Textarten: {', '.join(e['textarten'])}")


def aus_punkt() -> Iterator[dict[str, Any]]:
    for pfad in sorted((ERGEBNISSE / "punkt_argumente").glob("*.json")):
        e = json.loads(pfad.read_text(encoding="utf-8"))
        faelle = e.get("faelle") or []
        md = pfad.with_suffix(".md")
        yield lauf("punkt-argumente", pfad, started_at=_iso_aus_stempel(e.get("lauf") or pfad.name) or "",
                   metrics={"shown": round(sum(1 for f in faelle if f.get("shown")) / len(faelle), 4) if faelle else None,
                            "cases": len(faelle)},
                   models={"item_arguments": e["modell"]}, cost_usd=e.get("usd"), environment="local",
                   raw_extra=[rel(md)] if md.exists() else None, note="Handprüfung anhand der Gegenüberstellung")
    for pfad in sorted((ERGEBNISSE / "punkt_bezug").glob("*.json")):
        e = json.loads(pfad.read_text(encoding="utf-8"))
        z = e.get("zusammen") or {}

        def anteil(text: str | None) -> float | None:
            m = re.match(r"(\d+)/(\d+)", text or "")
            return round(int(m.group(1)) / int(m.group(2)), 4) if m and int(m.group(2)) else None
        yield lauf("punkt-bezug", pfad, started_at=_iso_aus_stempel(pfad.name) or "",
                   metrics={"with_ref": anteil(z.get("mit")), "without_ref": anteil(z.get("ohne")),
                            "cases": len(e.get("zeilen") or []) // 2},
                   cost_usd=z.get("usd"), environment="local", cases=None,
                   note=f"mit Bezug {z.get('mit')}, ohne {z.get('ohne')} — gegen einen lokalen Server")
    for pfad in sorted((ERGEBNISSE / "sitzung_satz").glob("*.md")):
        yield lauf("sitzung-satz", pfad, started_at=_iso_aus_stempel(pfad.name) or "", metrics={},
                   label=pfad.stem.split("-", 1)[-1], environment="local", cases=None,
                   note="Gegenüberstellung zum Lesen")


def aus_lotti_save() -> Iterator[dict[str, Any]]:
    """``eval/run_assistant.py --save``-Läufe, die der Prüfstand nicht übernommen hat."""
    for pfad in sorted((ERGEBNISSE / "assistant").glob("*.json")):
        if rel(pfad) in vom_pruefstand():
            continue
        e = json.loads(pfad.read_text(encoding="utf-8"))
        k = e.get("kennzahlen") or {}
        faelle = [f for f in e.get("faelle", []) if "modus" in f]
        hart = sum(1 for f in faelle if any(not b.startswith("~ ") for b in f.get("befunde", [])))
        yield lauf("lotti", pfad, started_at=_iso_aus_stempel(pfad.name) or "",
                   metrics={bm.QUALITY: round(sum(1 for f in faelle if not f.get("befunde")) / len(faelle), 4)
                            if faelle else None, bm.HARD: hart, "cases": len(faelle)},
                   models={"assistant_explain": k["modell"]} if k.get("modell") else {},
                   environment="local", cost_usd=k.get("kosten_usd"),
                   latency_ms={"p50": k.get("p50_ms"), "p95": k.get("p95_ms")},
                   note="eval/run_assistant.py --save, nicht über den Prüfstand")


def aus_lotti_frueh() -> Iterator[dict[str, Any]]:
    """Die ersten Lotti-Läufe (21./22.09.2026), noch ohne Kennzahlen-Kopf."""
    for pfad in sorted(ERGEBNISSE.glob("assistant-*.json")):
        faelle = [f for f in json.loads(pfad.read_text(encoding="utf-8")) if "modus" in f]
        sauber = sum(1 for f in faelle if not f.get("befunde"))
        yield lauf("lotti", pfad, started_at=_iso_aus_stempel(pfad.name) or "",
                   metrics={bm.QUALITY: round(sauber / len(faelle), 4) if faelle else None, "cases": len(faelle)},
                   environment="local", comparable=False,
                   note="früher Lauf vor dem Prüfstand: ältere Fallliste, Modell nicht erfasst")


# --------------------------------------------------------------------------- #
# Das Gold-Messbuch (docs/gold-messbuch.md) — die Läufe liegen nur auf den Servern
# --------------------------------------------------------------------------- #

_OKT = {"qa_analysis": "google/gemini-3.1-flash-lite", "qa_query_expansion": "google/gemini-3.1-flash-lite",
        "qa_nachrecherche": "google/gemini-3.1-flash-lite", "qa_answer": "openai/gpt-6-luna"}
_NOV = {"qa_analysis": "openai/gpt-5.6-luna", "qa_query_expansion": "openai/gpt-5.6-luna",
        "qa_nachrecherche": "openai/gpt-5.6-luna", "qa_answer": "openai/gpt-6-luna"}

#: (Datum, Umgebung, Label, Stand, Abdeckung, bestanden, Belege im Prompt, Belege gesamt,
#:  weggelassen, Dauer s, Modelle, Fazit) — abgeschrieben aus der Tabelle „Läufe".
GOLD_MESSBUCH: tuple[tuple[Any, ...], ...] = (
    ("2026-10-17", "dev", "okt-basis-c", "Grundlinie, alle Schalter aus", .57, 11, 127, 198, 53, 32, _OKT, None),
    ("2026-10-17", "dev", "okt-basis-d", "Grundlinie, alle Schalter aus", .56, 12, 127, 198, 50, 30, _OKT, None),
    ("2026-10-17", "dev", "okt-diaet-a", "+ Kontext-Diät (#1725)", .55, 11, 127, 198, 55, 34, _OKT, None),
    ("2026-10-17", "dev", "okt-diaet-b", "+ Kontext-Diät (#1725)", .54, 9, 127, 198, 56, 32, _OKT, None),
    ("2026-10-18", "dev", "okt-notizen-a", "+ Belegnotizen und 24 statt 6 Beiträge Aussprache (#1726)",
     .59, 13, 126, 198, 45, 32, _OKT,
     "Misst zwei Änderungen auf einmal — der Gewinn ließ sich später nicht den Notizen zuschreiben."),
    ("2026-10-18", "dev", "okt-notizen-b2", "+ Belegnotizen und 24 statt 6 Beiträge Aussprache (#1726)",
     .60, 14, 126, 198, 41, 33, _OKT, None),
    ("2026-10-18", "dev", "okt-kontrolle-a", "+ Diät ohne Fraktionsfragen, mildere Punktfragen-Regel (#1733)",
     .60, 19, 126, 198, 42, 36, _OKT, "Ab hier ist „bestanden“ bei Punktfragen milder — vorher nicht vergleichbar."),
    ("2026-10-18", "dev", "okt-kontrolle-b", "+ Diät ohne Fraktionsfragen, mildere Punktfragen-Regel (#1733)",
     .61, 18, 126, 198, 40, 33, _OKT, None),
    ("2026-10-18", "dev", "okt-suche-a", "+ Suche-Ausbau, Vorgang als Zeitleiste (#1736)",
     .62, 19, 135, 198, 47, 33, _OKT, None),
    ("2026-10-18", "dev", "okt-suche-b", "+ Suche-Ausbau, Vorgang als Zeitleiste (#1736)",
     .62, 19, 135, 198, 45, 32, _OKT, None),
    ("2026-11-09", "prod", "nov09-prod-a", "v3.0.0: Suche-Ausbau, Diät, Akte; ohne Belegnotizen, ohne Nachrecherche",
     .62, 18, 153, 198, 52, 27, _NOV,
     "Erstes Wort nach 26,9 s (Median), gesamt 29,1 s — der größte Hebel liegt vor dem ersten Wort, nicht in der Suche."),
    ("2026-11-09", "prod", "nov09-prod-belegnotizen", "wie nov09-prod-a, mit Belegnotizen",
     .61, 18, 153, 198, 49, 35, _NOV,
     "Belegnotizen allein bringen nichts Messbares und kosten ≈ 8 s bis zum ersten Wort — auf Prod aus "
     "(09.11.2026), ganz ausgebaut (14.11.2026)."),
    ("2026-11-09", "dev", "nov09-dev-vor", "alle Schalter, Stand vor #1801", .57, 15, 135, 198, 47, 49, _NOV, None),
    ("2026-11-09", "dev", "nov09-dev-nach", "+ #1801: Personenreden, Komposita, „seitdem“ mit Datum, Gold-Pflege",
     .63, 19, 137, 200, 46, 48, _NOV,
     "Ohne die drei umgestellten Gold-Fälle 56,9 % → 61,4 %; größter Sprung behrens-baumschutz (18 % → 65 %)."),
)

#: Teilläufe: (Datum, Umgebung, Label, Stand, {Fall: Abdeckung}, Fazit)
GOLD_TEILLAEUFE: tuple[tuple[Any, ...], ...] = (
    ("2026-11-09", "dev", "nov09-dev-nach-1803", "+ jüngste Aussprache nach der Akte (#1803)",
     {"trinkwasserspender-draussen": .08, "bahnuebergang-am-stadtrand-verlauf": .40, "heidbrook-zusagen": .39,
      "behrens-baumschutz": .71, "parkgebuehren-mehreinnahmen": .62, "klinikum-buergschaften-stand": .62},
     "Griff bei den oberen drei nicht: Der Forschungsplan schaltete bei Termin- und Faktenfragen die Aussprache ab."),
    ("2026-11-09", "dev", "nov09-dev-nach-1811", "+ Zusagen auch bei Termin- und Faktenfragen (#1811)",
     {"trinkwasserspender-draussen": .33, "bahnuebergang-am-stadtrand-verlauf": .40, "heidbrook-zusagen": .33},
     "Bahnübergang und Heidbrook fehlt weiter Material in der Suche, nicht in den Zusagen."),
)


def aus_gold_messbuch() -> Iterator[dict[str, Any]]:
    """Uhrzeiten stehen im Messbuch nicht — die Reihenfolge der Tabelle schon.
    Je Tag fortlaufend ab 12:00 (eine Minute je Zeile), damit „der jüngste
    Lauf" der letzte der Tabelle ist."""
    quelle = "docs/gold-messbuch.md"
    minute: dict[str, int] = {}
    for (tag, umgebung, label, stand, abdeckung, bestanden, im_prompt, gesamt, wegg, dauer,
         modelle, fazit) in GOLD_MESSBUCH:
        minute[tag] = minute.get(tag, -1) + 1
        yield lauf("ask-gold", f"server:{umgebung}:data/eval_gold/ask-{label}.json",
                   started_at=f"{tag}T12:{minute[tag]:02d}:00",
                   metrics={"coverage": abdeckung, "passed": bestanden, "context_recall": round(im_prompt / gesamt, 4),
                            "evidence_in_prompt": im_prompt, "evidence_total": gesamt, "omitted": wegg,
                            "median_s": dauer, "cases": 27},
                   cases=None, environment=umgebung, label=label, purpose=stand, conclusion=fazit,
                   models=dict(modelle), judge="anthropic/claude-opus-5.5", source=quelle,
                   note="aus dem Messbuch übernommen; Uhrzeit nicht erfasst (Reihenfolge wie dort). Modelle laut Messbuch "
                        "(Analyse bis #1783 Gemini 3.1 Flash Lite, danach GPT-5.6 Luna).")
    for tag, umgebung, label, stand, faelle, fazit in GOLD_TEILLAEUFE:
        minute[tag] = minute.get(tag, -1) + 1
        yield lauf("ask-gold", f"server:{umgebung}:data/eval_gold/ask-{label}.json",
                   started_at=f"{tag}T12:{minute[tag]:02d}:00",
                   metrics={"coverage": round(statistics.mean(faelle.values()), 4), "cases": len(faelle)},
                   cases=None, environment=umgebung, label=label, purpose=stand, conclusion=fazit,
                   models=dict(_NOV), judge="anthropic/claude-opus-5.5", source=quelle, comparable=False,
                   sample=len(faelle),
                   note="Teillauf über die schwachen Fälle — nicht mit vollen Läufen vergleichen. Je Fall: "
                        + ", ".join(f"{k} {round(v * 100)} %" for k, v in faelle.items()))


QUELLEN = (aus_pruefstand, aus_fakten, aus_qa, aus_harness, aus_cities, aus_deep_gold, aus_quality,
           aus_ergebnis_texte, aus_punkt, aus_lotti_save, aus_lotti_frueh, aus_gold_messbuch)


def vorhandene(ordner: Path = bm.REPO_RUNS) -> set[tuple[str, str]]:
    return {(r["benchmark"], r.get("raw") or "") for r in bm.load_runs(ordner) if "benchmark" in r}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--schreiben", action="store_true", help="Läufe anlegen (sonst nur zeigen)")
    a = ap.parse_args(argv)
    schon = vorhandene()
    neu = fehler = 0
    for quelle in QUELLEN:
        for rec in quelle():
            if (rec["benchmark"], rec["raw"]) in schon:
                continue
            probleme = bm.problems(rec)
            if probleme:
                fehler += 1
                print(f"  ✗ {rec['benchmark']} {rec['raw']}: {'; '.join(probleme)}")
                continue
            neu += 1
            schon.add((rec["benchmark"], rec["raw"]))
            if a.schreiben:
                pfad = bm.write_run(rec, bm.REPO_RUNS)
                print(f"  + {pfad.relative_to(WURZEL)}")
            else:
                print(f"  + {rec['benchmark']}/{bm.run_filename(rec)}  ← {rec['raw']}")
    print(f"\n{neu} neue Läufe{'' if a.schreiben else ' (Trockenlauf — mit --schreiben anlegen)'}"
          f"{f', {fehler} ungültig' if fehler else ''}.")
    return 1 if fehler else 0


if __name__ == "__main__":
    raise SystemExit(main())
