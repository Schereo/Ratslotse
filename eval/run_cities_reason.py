#!/usr/bin/env python3
"""Gibt ``reason`` wieder, was in der Niederschrift steht — oder erfindet es etwas?

**Warum die Frage zählt.** Das „Warum" ist das Wertvollste, was der
Städtevergleich zu bieten hat: Dass Magdeburg die Verpackungssteuer-Prüfung
eingestellt hat, weiß die Karte schon; *warum* der Rat das tat, ist das, was
eine Oldenburger Fraktion in ihrer eigenen Sitzung braucht. Genau deshalb ist
ein erfundenes „Warum" hier der teuerste aller Fehler — es sieht aus wie die
wertvollste Information und ist eine Lüge über einen echten Ratsbeschluss.

```bash
python eval/run_cities_reason.py            # ~0,05 $
python eval/run_cities_reason.py --runs 3   # Streuung messen
```

**Drei Schranken, und die erste steht bei null.**

1. ``grounded=true``, wo im Abschnitt gar keine Begründung steht: **0**.
   Dieselbe Klasse wie erfundene Beleg-Kennungen bei ``fit`` — eine harte
   Zusage, keine Quote. Der umgekehrte Fall (``false``, obwohl eine
   Begründung dasteht) ist ärgerlich, aber harmlos: Dann zeigt die Karte
   nichts, statt etwas Falsches zu zeigen.
2. ``vote`` zu **90 %** richtig. Das Abstimmungsergebnis steht fast immer
   wörtlich da („einstimmig", „12 dafür, 8 dagegen"); wer es verfehlt, hat
   den Abschnitt falsch geschnitten und nicht falsch gelesen — der Fehler
   gehört dann in ``council/cities/protocol.py``, nicht in den Prompt.
3. Keine Personennamen in der Ausgabe: **0** Treffer. Der Prompt verlangt
   Fraktionen und Rollen. Die Protokolle sind öffentlich, unsere Wiedergabe
   auf einer Vergleichskarte muss es nicht sein.

``why`` selbst wird **nicht automatisch bewertet** — ob ein Satz die
Begründung trifft, ist eine Handdurchsicht. Der Lauf schreibt die Sätze
deshalb mit ``--zeigen`` aus; die Schranke dafür (80 % „trifft zu") steht in
``gut_wenn`` des Annotators und wird von Hand geprüft.

**Die Fälle sind echte Abschnitte** aus ``eval/cases_cities_reason.json``,
und die Erwartungen stammen von mir, nicht von Tim: Ob im Text eine
Begründung steht und was als Abstimmungsergebnis dasteht, ist eine
Tatsachenfrage, keine Wertung.
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(WURZEL / ".env")

from council.cities.annotate import parse_json  # noqa: E402
from council.cities.annotators import get as get_annotator  # noqa: E402
from kern import llm, prompts  # noqa: E402

FAELLE = WURZEL / "eval" / "cases_cities_reason.json"

#: Erfundene Begründungen: keine. Siehe Modulkopf.
SCHWELLE_ERFUNDEN = 0
#: Das Abstimmungsergebnis steht wörtlich da.
SCHWELLE_VOTE = 0.90
#: Personennamen in der Ausgabe: keine.
SCHWELLE_NAMEN = 0

#: „Herr Meyer", „Frau Dr. Schulz-Braun" — grob, aber für einen Wächter reicht
#: es: Der Prompt verbietet die Anrede samt Namen vollständig.
_NAME_RE = re.compile(r"\b(Herr|Frau)\s+(Dr\.\s+)?[A-ZÄÖÜ][a-zäöüß]{2,}")


def lade() -> list[dict]:
    if not FAELLE.exists():
        raise SystemExit(
            f"{FAELLE} fehlt. Die Fälle entstehen aus echten Abschnitten:\n"
            f"  python eval/build_cities_reason_cases.py")
    return json.loads(FAELLE.read_text(encoding="utf-8"))


def _gleich(a: str | None, b: str | None) -> bool:
    """„einstimmig" und „Einstimmig angenommen." sind dasselbe Ergebnis."""
    def norm(x: str | None) -> str:
        return re.sub(r"[^a-zäöüß0-9]+", " ", (x or "").lower()).strip()
    x, y = norm(a), norm(b)
    if not x or not y:
        return x == y
    return x in y or y in x


def ein_lauf(faelle: list[dict], ann) -> dict:
    system = prompts.get(ann.prompt_system)
    erfunden: list[dict] = []
    namen: list[dict] = []
    vote_treffer = vote_gesamt = 0
    gefunden = verpasst = 0
    kosten = 0.0
    saetze: list[dict] = []

    for f in faelle:
        try:
            antwort = llm.chat_complete(
                model=ann.model, response_format={"type": "json_object"},
                messages=[{"role": "system", "content": system},
                          {"role": "user", "content": prompts.render(
                              ann.prompt_user, stadt=f["body"], gremium=f["organization"],
                              datum=f["date"], punkt=f["item"],
                              abschnitt=f["section"][:ann.input_chars])}],
                max_tokens=ann.max_tokens, temperature=ann.temperature,
                extra_body={"provider": {}} if ann.routing_free else {},
                _feature=ann.feature)
            nutzlast = ann.payload.model_validate(
                parse_json(antwort.choices[0].message.content or ""))
            verbrauch = getattr(antwort, "usage", None)
            kosten += float(getattr(verbrauch, "cost", 0) or 0) if verbrauch else 0.0
        except Exception as e:  # noqa: BLE001
            erfunden.append({"item": f["item"], "warum": f"FEHLER {type(e).__name__}"})
            continue

        # 1. Die harte Zusage: keine Begründung behaupten, wo keine steht.
        if nutzlast.grounded and not f["has_reason"]:
            erfunden.append({"item": f["item"], "why": nutzlast.why,
                             "warum": "im Abschnitt steht keine Begründung"})
        elif nutzlast.grounded and not nutzlast.why.strip():
            erfunden.append({"item": f["item"], "why": "",
                             "warum": "grounded=true, aber `why` leer"})
        if f["has_reason"]:
            gefunden += bool(nutzlast.grounded)
            verpasst += not nutzlast.grounded

        # 2. Das Abstimmungsergebnis.
        if f.get("vote") is not None:
            vote_gesamt += 1
            vote_treffer += _gleich(nutzlast.vote, f["vote"])

        # 3. Keine Personennamen.
        text = " ".join([nutzlast.discussed, nutzlast.decided, nutzlast.why])
        if _NAME_RE.search(text):
            namen.append({"item": f["item"],
                          "stelle": _NAME_RE.search(text).group(0)})

        saetze.append({"item": f["item"], "grounded": nutzlast.grounded,
                       "vote": nutzlast.vote, "why": nutzlast.why,
                       "decided": nutzlast.decided})

    return {"erfunden": erfunden, "namen": namen, "saetze": saetze,
            "vote_quote": vote_treffer / max(vote_gesamt, 1), "vote_gesamt": vote_gesamt,
            "gefunden": gefunden, "verpasst": verpasst, "cost_usd": kosten}


def main() -> int:
    p = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    p.add_argument("--runs", type=int, default=1)
    p.add_argument("--zeigen", type=int, default=6,
                   help="so viele `why`-Sätze für die Handdurchsicht ausschreiben")
    a = p.parse_args()

    faelle = lade()
    ann = get_annotator("reason")
    mit_grund = sum(1 for f in faelle if f["has_reason"])
    print(f"{len(faelle)} Abschnitte ({mit_grund} mit Begründung im Text), "
          f"Modell {ann.model}, {a.runs} Lauf/Läufe\n")

    laeufe = [ein_lauf(faelle, ann) for _ in range(a.runs)]
    letzter = laeufe[-1]
    votes = [x["vote_quote"] for x in laeufe]
    erfunden = statistics.fmean(len(x["erfunden"]) for x in laeufe)
    namen = statistics.fmean(len(x["namen"]) for x in laeufe)

    print(f"  Erfundene Begründungen  {erfunden:.1f}   Schwelle {SCHWELLE_ERFUNDEN}")
    print(f"  Abstimmungsergebnis     {statistics.fmean(votes):.0%} von "
          f"{letzter['vote_gesamt']}   Schwelle {SCHWELLE_VOTE:.0%}")
    print(f"  Personennamen           {namen:.1f}   Schwelle {SCHWELLE_NAMEN}")
    print(f"  Begründung gefunden     {letzter['gefunden']} von {mit_grund} "
          f"({letzter['verpasst']} übersehen — harmlos, die Karte zeigt dann nichts)")
    print(f"  Kosten                  ${sum(x['cost_usd'] for x in laeufe):.4f}")

    if letzter["erfunden"]:
        print("\n  ERFUNDEN:")
        for d in letzter["erfunden"][:8]:
            print(f"    {d['item'][:50]}  ({d['warum']})")
            if d.get("why"):
                print(f"        „{d['why'][:80]}“")
    if letzter["namen"]:
        print("\n  Personennamen in der Ausgabe:")
        for d in letzter["namen"][:8]:
            print(f"    {d['item'][:50]}  → {d['stelle']}")
    if a.zeigen:
        print("\n  Für die Handdurchsicht — trifft der Satz die Begründung?")
        for s in [x for x in letzter["saetze"] if x["grounded"]][:a.zeigen]:
            print(f"    {s['item'][:60]}")
            print(f"      beschlossen: {s['decided'][:70]}")
            print(f"      weil:        {s['why'][:90]}")

    schlecht = (erfunden > SCHWELLE_ERFUNDEN
                or statistics.fmean(votes) < SCHWELLE_VOTE
                or namen > SCHWELLE_NAMEN)
    print("\n" + ("NICHT bestanden." if schlecht else "Bestanden."))
    return 1 if schlecht else 0


if __name__ == "__main__":
    raise SystemExit(main())
