"""Ratsaufträge ohne gefundene Folge (Plan „Pläne der Stadt“ § 3.5, Art 2).

Ein angenommener Beschluss beauftragt die Verwaltung, dem Rat etwas vorzulegen —
und danach findet sich im Ratsinformationssystem keine Station mehr. Ein
falscher Treffer behauptet, die Stadt sei säumig, wo der Bericht in Wahrheit
existiert; deshalb gilt § 3.5: lieber zu wenig als zu viel, „nicht gefunden“
statt „gibt es nicht“, und angezeigt wird nur, was das Messziel erreicht.

Hier steht, was ohne Modell geht: Aufträge erkennen und spätere
Tagesordnungspunkte als Kandidaten für die Folge zusammensuchen. Welcher Art
ein Auftrag ist und ob ein Kandidat die Folge ist, entscheidet
``council/plan_judge.py``.
"""
from __future__ import annotations

import re
from datetime import date, timedelta

#: „Die Verwaltung wird beauftragt / gebeten / aufgefordert …“
MANDATE = re.compile(r"Verwaltung wird (?:\w+ ){0,3}?(?:beauftragt|gebeten|aufgefordert)", re.I)
#: So lange hat ein Auftrag Zeit, bevor sein Schweigen auffällt.
MIN_AGE_DAYS = 183
#: So viele Zeichen des Auftrags gehen ans Modell und auf die Seite.
QUOTE_CHARS = 330


def stem(number: str) -> str:
    return "/".join(str(number).split("/")[:2])


def mandates(decisions: list[dict]) -> list[dict]:
    """Je Vorlagenstamm ein Auftrag: der jüngste angenommene Beschluss, dessen Text die
    Verwaltung beauftragt. ``since`` ist die LETZTE Beratung der Vorlage — vorher läuft sie noch."""
    by_stem: dict[str, list[dict]] = {}
    for d in decisions:
        by_stem.setdefault(stem(d["template_number"]), []).append(d)
    out = []
    for key, group in by_stem.items():
        # Erst Leerraum glätten: Im Beschlusstext bricht die Zeile auch mitten in „wird / beauftragt“.
        accepted = [(d, text) for d in group if d["outcome"] == "accepted"
                    and (text := " ".join((d["official_text"] or "").split())) and MANDATE.search(text)]
        if not accepted:
            continue
        final, text = max(accepted, key=lambda pair: pair[0]["session_date"])
        start = MANDATE.search(text).start()  # type: ignore[union-attr]  # oben geprüft
        out.append({"stem": key, "decision_id": final["id"], "title": final["title"],
                    "committee": final["committee"], "since": max(d["session_date"] for d in group),
                    "quote": text[start:start + QUOTE_CHARS]})
    return sorted(out, key=lambda m: (m["since"], m["stem"]))


def old_enough(mandate: dict, today: str) -> bool:
    return date.fromisoformat(mandate["since"]) <= date.fromisoformat(today) - timedelta(days=MIN_AGE_DAYS)


#: Wörter, die in fast jedem Titel stehen und nichts über die Sache sagen.
_GENERIC = frozenset("""beschluss bericht antrag anfrage fraktion fraktionen gruppe stadt oldenburg oldenburger
verwaltung umsetzung konzept weiteres vorgehen sachstand änderung satzung bündnis grünen linke ratsfraktion
stellungnahme einrichtung erstellung prüfung entwicklung ausschuss fortschreibung planung maßnahmen maßnahme
projekt förderung richtlinie bereich rahmen ergebnisse workshop leitantrag änderungsantrag punkt""".split())


def _needle(word: str) -> str:
    """Ein Suchwort so gekürzt, dass Beugung und Kompositum es nicht verstecken: „Pferdemarktes“
    findet „Pferdemarkt“, „Schulentwicklungsplan“ findet „Schulentwicklung“."""
    word = word.lower().strip()
    return word[:min(max(6, len(word) - 2), 12)]


def title_words(title: str) -> list[str]:
    """Die eigenen Wörter eines Titels, ohne Klammerzusätze („(Fraktion … vom …)“) und Allerweltswörter."""
    plain = re.sub(r"\(.*?\)|\s-\s(?:Beschluss|Bericht).*$", " ", title or "")
    return [w for w in re.findall(r"[A-Za-zÄÖÜäöüß][A-Za-zÄÖÜäöüß\-]{5,}", plain) if w.lower() not in _GENERIC]


def follow_up_candidates(mandate: dict, subject: list[str], agenda: list[dict], limit: int = 12) -> list[dict]:
    """Spätere Tagesordnungspunkte (``title``, ``date``, ``committee``, ``template_number``), deren
    Titel eines der Suchwörter trägt — die Suchwörter des Modells und die eigenen Wörter des
    Auftragstitels. Die mit den meisten Treffern zuerst, dann die frühesten; die eigene Vorlage
    des Auftrags zählt nicht. Lieber ein Kandidat zu viel: Ob er die Folge ist, entscheidet das Modell."""
    needles = sorted({_needle(w) for w in [*subject, *title_words(mandate["title"])] if len(w.strip()) >= 4})
    scored = []
    for item in agenda:
        if item["date"] <= mandate["since"] or (item["template_number"] and stem(item["template_number"]) == mandate["stem"]):
            continue
        title = (item["title"] or "").lower()
        hits = sum(1 for n in needles if n in title)
        if hits:
            scored.append((-hits, item["date"], item))
    scored.sort(key=lambda s: (s[0], s[1]))
    seen, out = set(), []
    for _, _, item in scored:
        key = (item["template_number"] and stem(item["template_number"])) or item["title"]
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
        if len(out) == limit:
            break
    return out
