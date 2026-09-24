"""Das Ergebnis eines Beschlusses für die Zusammenfassungen: Hinweis und Probe.

**Warum überhaupt.** ``official_text`` ist bei einem abgelehnten oder
vertagten Punkt nicht das, was gilt, sondern der Beschlussvorschlag, der zur
Abstimmung stand. Die beiden Zusammenfassungen (``summary`` aus
:mod:`council.topics`, ``simple_summary`` aus :mod:`council.simple_summary`)
bekamen bis 09/2026 nur diesen Text — und schrieben ihn als gefassten
Beschluss nach. Gemessen am 23.09.2026: Von 21 abgelehnten Beschlüssen mit
Kurzfassung beschrieben 15 den Vorschlag als angenommen, etwa 5988
(„einstimmig abgelehnt") als „Der Satz für die Grundsteuer B steigt von 445
auf 490 Prozent". Frag den Rat und Lotti reichten das weiter.

Zwei Teile, beide an EINER Stelle, damit Prompt und Probe dieselben Fälle
kennen:

- :func:`note` — der Absatz, den beide Prompts über den Beschlusstext
  stellen: Ergebnis, Original-Abstimmungssatz und was daraus für die
  Zusammenfassung folgt.
- :func:`states_outcome` — ob ein fertiger Text das Ergebnis überhaupt nennt.
  Die Erzeugung verwirft, was diese Probe nicht besteht; der Nachlauf
  (``scripts/fix_outcome_summaries.py``) sucht damit die betroffenen Zeilen.

Angenommen (``accepted``) und zur Kenntnis genommen (``noted``) brauchen
beides nicht: Dort beschreibt ``official_text`` tatsächlich, was gilt.
"""
from __future__ import annotations

import re

#: Die Ergebnisse, bei denen der Beschlusstext NICHT gilt.
NOT_ADOPTED = ("rejected", "postponed", "no_decision")

#: Wie das Ergebnis im Prompt heißt.
LABEL = {
    "rejected": "ABGELEHNT",
    "postponed": "VERTAGT, VERWIESEN ODER ZURÜCKGESTELLT — noch nicht entschieden",
    "no_decision": "KEIN BESCHLUSS GEFASST",
}

_RULE = {
    "rejected": (
        "Der Beschlusstext unten ist nur der VORSCHLAG, der zur Abstimmung stand. "
        "Er wurde abgelehnt und gilt NICHT. Schreib ausdrücklich, dass der Vorschlag "
        "abgelehnt wurde, und beschreibe ihn als Vorschlag („sollte“, „war vorgeschlagen“) "
        "— nie so, als sei er beschlossen oder werde umgesetzt. Erfinde keine Folgen "
        "der Ablehnung („bleibt unverändert“, „wird nicht umgesetzt“): Ein Ausschuss "
        "empfiehlt oft nur, endgültig entscheiden Verwaltungsausschuss oder Rat."
    ),
    "postponed": (
        "Der Beschlusstext unten ist nur der VORSCHLAG. Über ihn wurde noch nicht "
        "entschieden: Er wurde vertagt, in ein anderes Gremium verwiesen oder "
        "zurückgestellt. Schreib genau das, und beschreibe den Inhalt als Vorschlag "
        "— nie so, als sei er beschlossen."
    ),
    "no_decision": (
        "Zu diesem Punkt wurde KEIN Beschluss gefasst. Schreib das ausdrücklich; "
        "beschreibe höchstens, worüber gesprochen wurde — nie so, als sei etwas "
        "beschlossen."
    ),
}

# Woran man erkennt, dass ein Text das Ergebnis nennt. Bewusst großzügig: Die
# Probe soll den Fall fangen, dass das Ergebnis GAR NICHT vorkommt („Der Satz
# steigt von 445 auf 490 Prozent"), nicht Formulierungen benoten.
_MARKERS = {
    "rejected": (
        r"abgelehnt", r"\blehnt\w*\b.*\bab\b", r"ablehn", r"abzulehn", r"nicht angenommen",
        r"keine mehrheit", r"scheitert", r"gescheitert", r"nicht (wieder)?gewählt",
        r"nicht beschlossen", r"nicht zugestimmt", r"stimmte?n? dagegen",
        r"dagegen gestimmt", r"nicht durch",
    ),
    "postponed": (
        r"vertagt", r"verschoben", r"verschiebt", r"verwiesen", r"verweist",
        r"zurückgestellt", r"weiter\w*(geben|leiten|leitet)", r"abgegeben",
        r"(an|in) (einen |zwei |die )?(anderen?|weiteren?) (fach-?)?(ausschü|ausschu|gremi)",
        r"abgesetzt", r"zurückgezogen", r"noch nicht", r"später", r"nächsten sitzung",
        r"erneut beraten", r"wieder beraten", r"weiter beraten", r"aufgeschoben",
        r"kein\w* (beschluss|entscheidung)",
    ),
    "no_decision": (
        r"kein\w* (formal\w* )?(beschluss|entscheidung|abstimmung)",
        r"nicht (entschieden|abgestimmt|beschlossen)", r"nichts (entschieden|beschlossen)",
        r"als behandelt", r"beratung\b.*\bbeendet", r"stimm\w* nicht",
        r"zurückgezogen", r"zur kenntnis", r"noch offen",
        r"vertagt", r"verschoben", r"besprochen", r"gesprochen", r"beraten",
        r"diskutiert", r"informiert", r"berichtet",
    ),
}
_MARKER_RE = {k: re.compile("|".join(v), re.IGNORECASE) for k, v in _MARKERS.items()}


#: Voranstellung für einen Text, der das Ergebnis NICHT nennt — etwa den
#: Beschlussvorschlag selbst, wenn die Kurzfassung fehlt oder die Probe nicht
#: besteht.
PROPOSAL_PREFIX = {
    "rejected": "Abgelehnter Vorschlag: ",
    "postponed": "Vertagter Vorschlag (noch nicht entschieden): ",
    "no_decision": "Ohne Beschluss geblieben — Vorschlag: ",
}


def as_proposal(outcome: str | None, text: str) -> str:
    """``text`` mit Ergebnis-Vorsatz, wenn er das Ergebnis selbst nicht nennt."""
    if states_outcome(outcome, text) or outcome not in PROPOSAL_PREFIX:
        return text
    return PROPOSAL_PREFIX[outcome] + text


def note(outcome: str | None, raw_result: str | None) -> str:
    """Der Ergebnis-Absatz für den Prompt — leer bei angenommen/zur Kenntnis."""
    if outcome not in NOT_ADOPTED:
        return ""
    raw = " ".join((raw_result or "").split())[:400]
    lines = [f"ERGEBNIS: {LABEL[outcome]}"]
    if raw:
        lines.append(f"Abstimmung laut Protokoll: {raw}")
    lines.append(_RULE[outcome])
    return "\n".join(lines)


def states_outcome(outcome: str | None, text: str | None) -> bool:
    """Nennt ``text`` das Ergebnis? Bei angenommen/zur Kenntnis immer ``True``.

    Ein leerer Text nennt nichts Falsches und besteht deshalb ebenfalls —
    ob er gespeichert wird, entscheidet der Aufrufer.
    """
    if outcome not in NOT_ADOPTED or not (text or "").strip():
        return True
    return bool(_MARKER_RE[outcome].search(text or ""))
