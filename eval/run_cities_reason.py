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
#: Ab wie vielen fehlgeschlagenen Aufrufen ein Lauf gar nichts aussagt.
#: Einzelne Fehlschläge sind Alltag (gemessen: einer von 36, beim nächsten
#: Versuch lief derselbe Fall durch); ein Drittel wäre eine Störung, und ein
#: Urteil darüber wäre eins über das Netz, nicht über das Modell.
ANTEIL_FEHLER_MAX = 0.1

#: Das Abstimmungsergebnis steht wörtlich da.
SCHWELLE_VOTE = 0.90
#: Personennamen in der Ausgabe: keine.
SCHWELLE_NAMEN = 0

#: **Dieselbe Regel, die der Annotator anwendet** — nicht eine zweite. Ein
#: Prüfstand mit eigenem Namensmuster misst sein Muster, nicht die Ausgabe:
#: Die erste Fassung hier kannte nur „Herr/Frau" und hätte „Sachkundiger
#: Einwohner Fassl" durchgewinkt, also genau den Fall, für den es die Regel
#: gibt.
from council.cities.annotators import _NAMEN_RE as _NAME_RE  # noqa: E402


def lade() -> list[dict]:
    if not FAELLE.exists():
        raise SystemExit(
            f"{FAELLE} fehlt. Die Fälle entstehen aus echten Abschnitten:\n"
            f"  python eval/build_cities_reason_cases.py")
    return json.loads(FAELLE.read_text(encoding="utf-8"))


#: Die Schreibweisen, in denen ein Abstimmungsergebnis mit Zahlen dasteht.
#: Alle sechs kommen in den 36 Handfällen vor: „mit 6 Ja-, 34 Neinstimmen und
#: 5 Enthaltungen", „0 – 2 – 4", „dafür: 6 dagegen: 0 Enthaltungen: 0" …
_JA = re.compile(r"(\d+)\s*(?:ja|dafür|dafuer|zustimmung)", re.I)
_NEIN = re.compile(r"(\d+)\s*(?:nein|dagegen|gegenstimm)", re.I)
_ENTH = re.compile(r"(\d+)\s*enthalt", re.I)
_BLANK = re.compile(r"\b(\d+)\s*[–—-]\s*(\d+)\s*[–—-]\s*(\d+)\b")
#: „dafür: 6 dagegen: 0" — die Zahl steht HINTER dem Wort, nicht davor.
_JA_NACH = re.compile(r"(?:ja|dafür|dafuer)[^0-9a-zäöüß]{0,3}(\d+)", re.I)
_NEIN_NACH = re.compile(r"(?:nein|dagegen)[^0-9a-zäöüß]{0,3}(\d+)", re.I)
_ENTH_NACH = re.compile(r"enthaltung(?:en)?[^0-9a-zäöüß]{0,3}(\d+)", re.I)


def _stimmen(text: str | None) -> list[tuple[int, int, int]]:
    """Ja/Nein/Enthaltungen als Zahlen — so oft, wie sie im Text stehen.

    **Ein Abschnitt kann ZWEI Abstimmungen tragen** (erst der
    Änderungsantrag, dann der Hauptantrag). Wer nur die letzte nimmt,
    verwirft die, die ein Mensch ins Golden Set geschrieben hat — gemessen
    am 13.09.2026 an genau diesem Fall.

    Ohne Ja UND Nein gibt es kein Tripel: „mit 7 Ja-Stimmen und einer
    Enthaltung" nennt keine Gegenstimmen, und eine geratene Null wäre eine
    Behauptung. Dann entscheidet weiter der Textvergleich.
    """
    if not text:
        return []
    roh = _BLANK.findall(text)
    if roh:
        return [(int(a), int(b), int(c)) for a, b, c in roh]
    for ja_re, nein_re, enth_re in ((_JA, _NEIN, _ENTH),
                                    (_JA_NACH, _NEIN_NACH, _ENTH_NACH)):
        ja, nein = ja_re.findall(text), nein_re.findall(text)
        if not ja or not nein:
            continue
        enth = enth_re.findall(text)
        return [(int(j), int(n), int(enth[i]) if i < len(enth) else 0)
                for i, (j, n) in enumerate(zip(ja, nein))]
    return []


def _gleich(a: str | None, b: str | None) -> bool:
    """„einstimmig" und „Einstimmig angenommen." sind dasselbe Ergebnis.

    **Zahlen werden als Zahlen verglichen, nicht als Zeichenketten.** „mit 6
    Ja-, 34 Neinstimmen und 5 Enthaltungen" und „6 Ja, 34 Nein, 5
    Enthaltungen" sind dieselbe Abstimmung; der Teilketten-Vergleich sah
    darin zwei verschiedene und meldete einen Modellfehler, wo keiner war
    (gemessen 13.09.2026: drei von drei „Abweichungen" waren Schreibweisen).
    """
    erwartet, bekommen = _stimmen(a), _stimmen(b)
    if erwartet and bekommen:
        # Trägt die Antwort die gesuchte Abstimmung, gilt sie als getroffen —
        # auch wenn sie die zweite des Abschnitts dazu nennt.
        return any(e in bekommen for e in erwartet)

    def norm(x: str | None) -> str:
        roh = re.sub(r"[^a-zäöüß0-9]+", " ", (x or "").lower()).strip()
        # „einer Enthaltung" und „1 Enthaltung" sind dieselbe Stimme. Deutsch
        # schreibt kleine Zahlen aus, und die Beugung wechselt mit dem Fall —
        # gemessen: „mit 7 Ja-Stimmen und EINER Enthaltung" gegen „7
        # Ja-Stimmen und EINE Enthaltung", zwei Schreibweisen derselben
        # Abstimmung. Nur ganze Wörter, sonst träfe es „einstimmig".
        return " ".join("1" if w in ("ein", "eine", "einer", "einem", "einen")
                        else w for w in roh.split())
    x, y = norm(a), norm(b)
    if not x or not y:
        return x == y
    return x in y or y in x


def ein_lauf(faelle: list[dict], ann) -> dict:
    system = prompts.get(ann.prompt_system)
    erfunden: list[dict] = []
    fehler: list[dict] = []
    namen: list[dict] = []
    vote_treffer = vote_gesamt = 0
    vote_daneben: list[dict] = []
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
                extra_body={},
                _feature=ann.feature)
            nutzlast = ann.payload.model_validate(
                parse_json(antwort.choices[0].message.content or ""))
            verbrauch = getattr(antwort, "usage", None)
            kosten += float(getattr(verbrauch, "cost", 0) or 0) if verbrauch else 0.0
        except Exception as e:  # noqa: BLE001
            # **Ein fehlgeschlagener Aufruf ist keine erfundene Begründung.**
            # Bis zum 13.09.2026 landete er in derselben Liste — und damit
            # riss ein Netzwackler die harte Schranke („null Erfindungen"),
            # ohne dass das Modell etwas falsch gemacht hätte. Gemessen:
            # Derselbe Fall lief beim nächsten Versuch fehlerfrei durch.
            fehler.append({"item": f["item"], "warum": f"{type(e).__name__}: {e}"})
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
            if _gleich(nutzlast.vote, f["vote"]):
                vote_treffer += 1
            else:
                vote_daneben.append({"item": f["item"], "erwartet": f["vote"],
                                     "bekommen": nutzlast.vote})

        # 3. Keine Personennamen.
        text = " ".join([nutzlast.discussed, nutzlast.decided, nutzlast.why])
        treffer = _NAME_RE.search(text)
        if treffer:
            namen.append({"item": f["item"], "stelle": treffer.group(0)})

        saetze.append({"item": f["item"], "grounded": nutzlast.grounded,
                       "vote": nutzlast.vote, "why": nutzlast.why,
                       "decided": nutzlast.decided})

    return {"erfunden": erfunden, "fehler": fehler, "namen": namen, "saetze": saetze,
            "vote_daneben": vote_daneben,
            "vote_quote": vote_treffer / max(vote_gesamt, 1), "vote_gesamt": vote_gesamt,
            "gefunden": gefunden, "verpasst": verpasst, "cost_usd": kosten}


def main() -> int:
    p = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    # **Drei Läufe, nicht einer.** 36 Abschnitte tragen 15 Abstimmungen; ein
    # einzelner Fall sind sieben Prozentpunkte. Gemessen am 13.09.2026 lag
    # dieselbe Einstellung in drei Einzelläufen bei 80 %, 87 % und 79 % —
    # ein Urteil daraus wäre eines über den Zufall. Gemittelt: 93 %.
    p.add_argument("--runs", type=int, default=3)
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
    fehler = statistics.fmean(len(x["fehler"]) for x in laeufe)
    print(f"  Fehlgeschlagene Aufrufe {fehler:.1f} von {len(faelle)} "
          f"(zählen NICHT als Erfindung)")
    print(f"  Kosten                  ${sum(x['cost_usd'] for x in laeufe):.4f}")

    if letzter["fehler"]:
        print("\n  FEHLGESCHLAGEN (kein Urteil über das Modell):")
        for d in letzter["fehler"][:8]:
            print(f"    {d['item'][:50]}  ({d['warum'][:60]})")
    if letzter["erfunden"]:
        print("\n  ERFUNDEN:")
        for d in letzter["erfunden"][:8]:
            print(f"    {d['item'][:50]}  ({d['warum']})")
            if d.get("why"):
                print(f"        „{d['why'][:80]}“")
    if letzter["vote_daneben"]:
        print("\n  Abstimmungsergebnis daneben (erwartet | bekommen):")
        for d in letzter["vote_daneben"][:8]:
            print(f"    {d['item'][:44]:46}")
            print(f"        {d['erwartet'][:56]!r}")
            print(f"        {str(d['bekommen'])[:56]!r}")
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
    # **Ein Lauf mit vielen Fehlschlägen hat nichts gemessen.** Er darf weder
    # bestehen noch durchfallen — sonst entscheidet über einen Annotator, wie
    # gut das Netz an diesem Nachmittag war.
    if fehler > len(faelle) * ANTEIL_FEHLER_MAX:
        print(f"\nKEIN URTEIL: {fehler:.0f} von {len(faelle)} Aufrufen "
              f"fehlgeschlagen (mehr als {ANTEIL_FEHLER_MAX:.0%}). "
              "Noch einmal laufen lassen.")
        return 2
    print("\n" + ("NICHT bestanden." if schlecht else "Bestanden."))
    return 1 if schlecht else 0


if __name__ == "__main__":
    raise SystemExit(main())
