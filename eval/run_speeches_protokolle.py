#!/usr/bin/env python3
"""Wortbeiträge an GANZEN Niederschriften: Wer fehlt, wem wird was zugeschrieben?

    python eval/run_speeches_protokolle.py --bauen      # Fälle aus der Ratsdatenbank schneiden
    python eval/run_speeches_protokolle.py              # heutiges Modell
    python eval/pruefstand.py --suite wortbeitraege-protokolle --modell … --laeufe 2

**Warum eine zweite Suite neben ``wortbeitraege``.** Deren 16 Fälle sind
Abschnitte von zwei, drei Tagesordnungspunkten (~6.700 Zeichen). Im Betrieb
laufen Fenster bis 48.000 Zeichen — und genau dort steckten die Modelle
bis 09/2026 die Antworten der Verwaltung in das answer-Feld der Frage davor
(ksinr 4664, TOP 7: Sprenger und Piening zum Schlossplatz; im Bestand 1.620
Mal). Die Abschnitts-Suite hätte das nicht gesehen. Hier läuft das ganze
Protokoll durch denselben Weg wie im Cron.

**Hauptkennzahl: F1 über die Wortmeldungen je Person**, erwartet ist je
Nachname die Zahl der Wortmeldungs-Anfänge im Rohtext („Herr Sprenger
antwortet …", Muster aus ``eval/build_speeches_cases.py``). Gezählt werden
Reden und Anfragen; Zusagen sind ein Auszug AUS einer Wortmeldung und
Einwohnerfragen tragen selten Namen.

**Nebenkennzahlen, alle ohne Modell als Richter:**

- ``recall_ohne_mandat`` — dieselbe Quote nur für Personen, die das
  Protokoll nie als Ratsherr/Ratsfrau/Vorsitz einführt: Verwaltung,
  beratende Mitglieder, Gäste. Hier lag der Fehler.
- ``antwort_in_rede`` — wie oft das Modell ROH eine Antwort in das
  answer-Feld einer Rede gelegt hat (die Pipeline trennt sie inzwischen,
  der Wert zeigt, wie sehr sie das muss).
- ``fremd_zugeschrieben`` — Anteil der Beiträge mit einem markanten Begriff,
  der im Protokoll nur in den Wortmeldungen ANDERER steht („Denkmalschutz"
  bei Sprenger, gesagt hat es Piening). Markant heißt: steht in höchstens
  zwei Wortmeldungen und nirgends sonst im Protokoll.
- ``zahlen_erhalten`` / ``begriffe_erhalten`` — Anteil der Zahlen und der
  markanten Begriffe einer Wortmeldung, die sich in den Beiträgen derselben
  Person wiederfinden. Der Prompt verlangt „bewahre konkrete Zahlen, Orte
  und Forderungen"; eine Paraphrase darf kürzen, aber die Frage des
  Nutzers hängt oft an genau diesem Detail.

Die Begriffs-Maße sind Näherungen über Wortstämme — sie vergleichen Modelle
untereinander, sie benoten keinen Einzelfall.
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL))

from eval.build_speeches_cases import WECHSEL, falte, flicken, nachname, top_nummer  # noqa: E402

FAELLE = WURZEL / "eval" / "cases_speeches_protokolle.json"

#: Ganze Niederschriften, in denen das Wortmeldungs-Muster greift — über
#: Gremien und Jahre gestreut, mit und ohne versteckte Antworten im Bestand
#: (Stand der Extraktion vom 08/2026, gemessen 30.09.2026).
AUSWAHL: tuple[int, ...] = (
    4664,  # ASUK 04/2026 — der Anlass: 18 versteckte Antworten, Schlossplatz
    4430,  # Verkehr 11/2025 — 24 versteckt, 74k Zeichen (zwei Fenster)
    4418,  # Sozial 06/2025 — 19 versteckt, kurz
    4446,  # Jugendhilfe 03/2025 — 19 versteckt
    4545,  # Stadtplanung 05/2025 — 24 versteckt
    4611,  # Schule 03/2026 — keine versteckt, aber nur 12 von 29 Verwaltungs-Wortmeldungen
    3717,  # ASUK 03/2021
    2855,  # Jugendhilfe 06/2018
    4441,  # ASUK 09/2025 — Kontrolle: im Bestand sauber
)

#: Einführungen, die ein Ratsmandat oder den Vorsitz anzeigen.
_RAT = re.compile(r"^\s*(?:Ratsherr|Ratsfrau|Ratsmitglied|Bürgermeister|(?:(?:Die|Der) )?"
                  r"(?:stellvertretende )?(?:Ausschussvorsitzende|Ratsvorsitzende|Vorsitzende))")
#: Wo eine Wortmeldung endet, ohne dass die nächste beginnt.
_ENDE = re.compile(r"(?m)^\s*(?:zu\s+(?:[ÖN]\s*)?\d+(?:\.\d+)*\b|Beschluss\s*:|-\s*(?:einstimmig|mehrheitlich|bei\s))")
#: Sammel-Punkte: Dort antwortet die Verwaltung laut Prompt im answer-Feld
#: der Anfrage bzw. Einwohnerfrage — ohne eigenen Namen. Sie zählen nicht mit.
_SAMMEL = re.compile(r"Einwohnerfrage|Anfragen und Anregungen|Mitteilung", re.I)
_KOPFZEILE = re.compile(r"(?m)^\s*zu\s+(?:[ÖN]\s*)?(\d+(?:\.\d+)*)\b(.*)$")
_SEITE = re.compile(r"(?m)^\s*Seite:\s*\d+/\d+\s*$")
_WORT = re.compile(r"[a-zäöüß]{7,}")
#: Substantive (groß geschrieben, nicht am Satzanfang) — Träger des Inhalts.
#: Verben wie „erachtet" stehen in vielen Wortmeldungen und sagten über die
#: Zuordnung nichts (gemessen am Bestand von 4664).
_SUBSTANTIV = re.compile(r"(?<![.!?:;]\s)(?<!^)(?<=\s|\()[A-ZÄÖÜ][a-zäöüß]{7,}")
#: Auch über Zeilenumbrüche der PDF-Textschicht hinweg („info@shp-\nverkehrsplanung.de").
_ADRESSE = re.compile(r"[\w.+-]+@[\w-]+(?:[ \t]*\n[ \t]*-?[ \t]*[\w-]+)*(?:\.[\w-]+)+")
_ZAHL = re.compile(r"\d+(?:[.,]\d+)*")


def _stamm(wort: str) -> str:
    """Grobe Endungskappe, damit „Denkmalschutzes" und „Denkmalschutz" zusammenfinden."""
    return wort[:-2] if len(wort) >= 9 else wort


def sammel_nummern(text: str) -> set[str]:
    return {m.group(1) for m in _KOPFZEILE.finditer(flicken(text)) if _SAMMEL.search(m.group(2))}


def zerlegen(text: str) -> tuple[list[dict], str]:
    """Rohtext → Wortmeldungen [{name, rat, sammel, text}] und der Rest
    (Überschriften, Beschlüsse, Anwesenheit)."""
    t = _SEITE.sub("", flicken(text))
    koepfe = [(m.start(), bool(_SAMMEL.search(m.group(2)))) for m in _KOPFZEILE.finditer(t)]
    starts = [(m.start(), m) for m in WECHSEL.finditer(t)]
    enden = sorted({m.start() for m in _ENDE.finditer(t)})
    meldungen, rest, pos = [], [], 0
    for i, (s, m) in enumerate(starts):
        if re.match(r"\s+(?:van|von|de)\s", t[m.end(1):]):
            continue  # „Herr Thorsten van Ellen Bündnis 90 …": Anwesenheitsliste, keine Wortmeldung
        rest.append(t[pos:s])
        naechster = starts[i + 1][0] if i + 1 < len(starts) else len(t)
        ende = min([e for e in enden if s < e < naechster] or [naechster])
        kopf = [k for k in koepfe if k[0] < s]
        meldungen.append({"name": nachname(m.group(1)), "rat": bool(_RAT.match(m.group(0))),
                          "sammel": bool(kopf and kopf[-1][1]), "text": t[s:ende]})
        pos = ende
    rest.append(t[pos:])
    return meldungen, " ".join(rest)


def _falt(s: str) -> str:
    """Kleinschreibung, Umlaute aufgelöst („Kindergärten" ~ „Kindergarten")."""
    s = (s or "").lower().translate(str.maketrans({"ä": "a", "ö": "o", "ü": "u", "ß": "ss"}))
    return re.sub(r"[^a-z0-9]", "", s)


def bewerten(fall: dict, beitraege: list[dict], roh_antwort_in_rede: int = 0) -> dict:
    meldungen, rest = zerlegen(fall["text"])
    erwartet = Counter(m["name"] for m in meldungen if m["name"] and not m["sammel"])
    sammel = sammel_nummern(fall["text"])
    rat = {m["name"] for m in meldungen if m["rat"]}
    text_gefaltet = falte(fall["text"])
    meld_falt = [_falt(m["text"]) for m in meldungen]
    rest_falt = _falt(rest)

    def markant(stamm: str) -> set[int] | None:
        """Wortmeldungen, in denen der Stamm steht — None, wenn nicht markant."""
        if stamm in rest_falt:
            return None
        wo = {i for i, mf in enumerate(meld_falt) if stamm in mf}
        return wo if 0 < len(wo) <= 2 else None

    def einmalig(stamm: str) -> set[int] | None:
        """Strenger fürs Fremd-Maß: genau eine Wortmeldung, langer Stamm."""
        wo = markant(stamm) if len(stamm) >= 9 else None
        return wo if wo is not None and len(wo) == 1 else None

    gezaehlt: Counter = Counter()
    erfunden: list[str] = []
    je_person: dict[str, list[str]] = defaultdict(list)
    fremd_beitraege = bewertbar = 0
    fremd_beispiele: list[str] = []
    for b in beitraege:
        n = nachname(b.get("speaker"))
        inhalt = " ".join(x for x in (b.get("text"), b.get("answer")) if x)
        if n:
            je_person[n].append(inhalt)
            if n not in text_gefaltet:
                erfunden.append(str(b.get("speaker")))
        im_sammel = top_nummer(re.sub(r"^zu\s+", "", str(b.get("top") or ""))) in sammel \
            or bool(_SAMMEL.search(str(b.get("top") or "")))
        if n and b.get("kind") in ("speech", "inquiry") and not im_sammel:
            gezaehlt[n] += 1
        eigene = {i for i, m in enumerate(meldungen) if m["name"] == n}
        if not n or not eigene:
            continue
        bewertbar += 1
        fremde = []
        for w in dict.fromkeys(_SUBSTANTIV.findall(b.get("text") or "")):
            wo = einmalig(_stamm(_falt(w)))
            if wo is not None and not (wo & eigene):
                fremde.append(w)
        if fremde:
            fremd_beitraege += 1
            if len(fremd_beispiele) < 6:
                fremd_beispiele.append(f"{b.get('speaker')}: {', '.join(fremde[:3])}")

    # Detailtreue: Zahlen und markante Stämme jeder längeren Wortmeldung.
    zahlen_da = zahlen_alle = begriffe_da = begriffe_alle = 0
    for i, m in enumerate(meldungen):
        if len(m["text"]) < 250 or not m["name"]:
            continue
        eigen = _falt(" ".join(je_person.get(m["name"], [])))
        for z in dict.fromkeys(_ZAHL.findall(m["text"])):
            if len(z) < 2:
                continue
            zahlen_alle += 1
            zahlen_da += _falt(z) in eigen
        for w in dict.fromkeys(_WORT.findall(m["text"].lower())):
            s = _stamm(_falt(w))
            if len(s) < 9 or markant(s) != {i}:
                continue
            begriffe_alle += 1
            begriffe_da += s in eigen

    tp = fp = fn = 0
    tp_ohne = fn_ohne = 0
    for n, p in erwartet.items():
        e = gezaehlt.get(n, 0)
        tp += min(e, p)
        fn += max(0, p - e)
        fp += max(0, e - p)
        if n not in rat:
            tp_ohne += min(e, p)
            fn_ohne += max(0, p - e)
    fp += sum(e for n, e in gezaehlt.items() if n not in erwartet)
    return {"id": fall["id"], "tp": tp, "fp": fp, "fn": fn,
            "tp_ohne": tp_ohne, "fn_ohne": fn_ohne,
            "verpasst": sorted(n for n in erwartet if not gezaehlt.get(n)),
            "erfunden": erfunden, "antwort_in_rede": roh_antwort_in_rede,
            "fremd": fremd_beitraege, "bewertbar": bewertbar, "fremd_beispiele": fremd_beispiele,
            "zahlen": [zahlen_da, zahlen_alle], "begriffe": [begriffe_da, begriffe_alle],
            "beitraege": len(beitraege)}


def zusammenfassen(zeilen: list[dict]) -> dict:
    ok = [z for z in zeilen if "fehler" not in z]

    def s(k: str) -> int:
        return sum(z.get(k, 0) for z in zeilen)

    def quote(a: int, b: int) -> float | None:
        return round(a / b, 4) if b else None

    tp, fp, fn = s("tp"), s("fp"), s("fn")
    return {
        "n_cases": len(zeilen),
        "f1": round(2 * tp / (2 * tp + fp + fn), 4) if tp else 0.0,
        "precision": quote(tp, tp + fp),
        "recall": quote(tp, tp + fn),
        "recall_ohne_mandat": quote(s("tp_ohne"), s("tp_ohne") + s("fn_ohne")),
        "antwort_in_rede": s("antwort_in_rede"),
        "fremd_zugeschrieben": quote(s("fremd"), s("bewertbar")),
        "zahlen_erhalten": quote(sum(z["zahlen"][0] for z in ok), sum(z["zahlen"][1] for z in ok)),
        "begriffe_erhalten": quote(sum(z["begriffe"][0] for z in ok), sum(z["begriffe"][1] for z in ok)),
        "erfunden": sum(len(z.get("erfunden", [])) for z in ok),
        "beitraege": s("beitraege"),
        "fehlgeschlagen": len(zeilen) - len(ok),
        "faelle": zeilen,
    }


def ein_lauf(faelle: list[dict], modell: str | None = None) -> dict:
    from council import wortbeitraege as wb
    original = wb._ein_fenster
    roh = {"n": 0}

    def zaehlend(text: str, model: str) -> list[dict]:
        daten = original(text, model)
        roh["n"] += sum(1 for r in daten if isinstance(r, dict)
                        and str(r.get("kind") or "speech").lower() not in wb.MIT_ANTWORT
                        and str(r.get("answer") or "").strip())
        return daten

    zeilen = []
    wb._ein_fenster = zaehlend
    try:
        for fall in faelle:
            roh["n"] = 0
            try:
                beitraege = wb.extract_wortbeitraege(fall["text"], modell or wb.MODEL)
            except Exception as e:  # noqa: BLE001 — ein Fall, nicht der Lauf
                meldungen, _ = zerlegen(fall["text"])
                zeilen.append({"id": fall["id"], "tp": 0, "fp": 0,
                               "fn": sum(1 for m in meldungen if m["name"]),
                               "fehler": f"{type(e).__name__}: {str(e)[:200]}"})
                continue
            zeilen.append(bewerten(fall, beitraege, roh["n"]))
    finally:
        wb._ein_fenster = original
    return zusammenfassen(zeilen)


def lade() -> list[dict]:
    if not FAELLE.exists():
        raise SystemExit(f"{FAELLE} fehlt: python eval/run_speeches_protokolle.py --bauen")
    return json.loads(FAELLE.read_text(encoding="utf-8"))


def bauen(db: Path) -> None:
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    faelle = []
    for ksinr in AUSWAHL:
        row = conn.execute(
            "SELECT p.raw_text, s.committee, s.session_date FROM council_protocols p "
            "JOIN council_sessions s USING (ksinr) WHERE p.ksinr = ?", (ksinr,)).fetchone()
        if not row or not row[0]:
            raise SystemExit(f"ksinr {ksinr}: kein Protokolltext in {db}")
        # Anwesenheitslisten tragen Dienstadressen der Verwaltung. Das Repo ist
        # öffentlich (CLAUDE.md, lint_adressen.py) — für die Messung zählt
        # keine davon.
        text = _ADRESSE.sub("[E-Mail]", row[0])
        faelle.append({"id": f"{ksinr}", "ksinr": ksinr, "gremium": row[1], "datum": row[2],
                       "text": text})
    FAELLE.write_text(json.dumps(faelle, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(faelle)} Fälle, {sum(len(f['text']) for f in faelle):,} Zeichen → {FAELLE}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--modell")
    ap.add_argument("--bauen", action="store_true")
    ap.add_argument("--db", default=str(WURZEL / "data" / "council.sqlite"))
    a = ap.parse_args()
    if a.bauen:
        bauen(Path(a.db))
        return 0
    from dotenv import load_dotenv
    load_dotenv(WURZEL / ".env")
    erg = ein_lauf(lade(), a.modell)
    for z in erg["faelle"]:
        print(f"  {z['id']:6} tp {z['tp']:3} fp {z['fp']:3} fn {z['fn']:3} "
              f"ohne Mandat {z.get('tp_ohne', 0)}/{z.get('tp_ohne', 0) + z.get('fn_ohne', 0)} "
              f"answer {z.get('antwort_in_rede', 0)} fremd {z.get('fremd', 0)}/{z.get('bewertbar', 0)}"
              f"{' ' + z['fehler'] if z.get('fehler') else ''}")
    print({k: v for k, v in erg.items() if k != "faelle"})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
