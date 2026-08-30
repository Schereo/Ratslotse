"""Tragweite-Score (RL-U16): Wie folgenreich ist ein Beschluss?

Das Gegenstück zum Interessantheits-Score (``council/interest.py``): Der
belohnt Kuriosität (schräge Straßennamen landen oben) und taugt darum nicht
als Priorität. Hier bewertet ein LLM die TRAGWEITE nach fester Rubrik
(Betroffene · Geld · Bindungswirkung · Präzedenz, je 0–25) mit
Anker-Beispielen zur Kalibrierung — die Lehre aus dem Interest-Lauf. Der
Batch bekommt Struktur-Signale (kind, outcome, Betrag, Gremium, Textlänge)
mit, nicht nur Titel. Das Ergebnis mischt 50/50 in den Wichtig-Wert
(``CouncilStore.backfill_importance``); die Heuristik bleibt der Boden.
Vor dem Prod-Rollout: ``scripts/eval_impact.py`` gegen das Golden-Set.
"""
from __future__ import annotations

import json
import os
import re

from kern import llm, prompts

MODEL = os.environ.get("COUNCIL_IMPACT_MODEL", "deepseek/deepseek-v4-pro")
BATCH_SIZE = 20
MAX_EXCERPT_CHARS = 900

#: Wo der Inhalt einer Vorlage anfängt. Davor stehen rund 300 Zeichen
#: Briefkopf (Ausdruckdatum, Seitenzahl, Amt, Vorlagen-Nr., wiederholter
#: Titel, Beratungsfolge) — die fraßen die Hälfte des Auszugs und schoben
#: genau den Satz heraus, auf den es ankommt: Bei der Unfallstatistik
#: 26/0602 endete er bei „bedauerlic", direkt vor „nicht möglich", und das
#: Modell hielt eine abgesagte Berichterstattung für einen Bericht mit Zahlen
#: (Tims Befund 19.08.26).
_VORLAGE_KOPF_RE = re.compile(r"\b(Anlass|Sachverhalt|Begr[üu]ndung|Bericht)\s*:",
                              re.IGNORECASE)

#: Straßenrechtliche Formalakte: Widmung, (Teil-)Einziehung, Umstufung einer
#: Straße machen einen längst bestehenden Zustand amtlich — für niemanden
#: ändert sich etwas. Das LLM hielt „Widmung der Straße ‚Im Technologiepark‘"
#: trotzdem für wichtig (Tims Befund 18.08., Wochen-Karte) — deshalb ein
#: DETERMINISTISCHER Deckel statt Prompt-Hoffnung. \b verhindert, dass
#: „Umwidmung" (von Mitteln) mitgefangen wird.
_FORMALAKT_RE = re.compile(r"\b(teil)?(widmung|einziehung|umstufung)\b", re.IGNORECASE)
_STRASSE_RE = re.compile(
    r"(straße|strasse|weg\b|wege\b|weges\b|platz|verkehrsfläche|gehweg|radweg|fußweg)",
    re.IGNORECASE)
FORMALAKT_MAX = 15


def formalakt_deckel(title: str | None) -> int | None:
    """Score-Obergrenze für straßenrechtliche Formalakte — sonst None."""
    t = title or ""
    if _FORMALAKT_RE.search(t) and _STRASSE_RE.search(t):
        return FORMALAKT_MAX
    return None


#: Untergrenze für Dringlichkeitsanträge (Tims Entscheidung 30.08.26).
#:
#: Die Rubrik misst TRAGWEITE — Betroffene, Geld, Bindungswirkung,
#: Präzedenz. Dass ein Antrag kurzfristig auf die Tagesordnung gehoben wird,
#: kommt darin nicht vor, ist aber selbst eine Nachricht: Eine Fraktion hält
#: eine Sache für so dringend, dass sie die Tagesordnung dafür aufmacht.
#:
#: Der Wert ist gemessen, nicht geraten. Am Bestand (158 bewertete Punkte):
#: 65 erreicht das oberste Zehntel. Der SECHSTE Punkt einer Sitzung — der
#: letzte, der auf eine Karte kommt — wiegt im Median 25; nur im Rat, der
#: dichtesten Tagesordnung, liegt er bei 60. 65 reicht damit in jedem
#: Fachausschuss sicher und im Rat knapp.
#:
#: Ein BODEN, keine Addition: Er hebt eine zu niedrige Bewertung an, senkt
#: aber nie eine hohe. Und er ersetzt die Begründung des Modells nicht — sie
#: bleibt richtig, sie wog nur die Kurzfristigkeit nicht mit.
DRINGLICHKEIT_MIN = 65

#: Woran ein Dringlichkeitsantrag zu erkennen ist: an der Kennung, die
#: council/dringlichkeit.py vergibt. Am Titel zu prüfen wäre unschärfer —
#: „Dringlichkeit" kann auch im Titel einer gewöhnlichen Vorlage stehen.
_DZT_RE = re.compile(r"^\s*DZT\b")


def dringlichkeits_boden(item_number: str | None) -> int | None:
    """Score-Untergrenze für Dringlichkeitsanträge — sonst None."""
    return DRINGLICHKEIT_MIN if _DZT_RE.match(item_number or "") else None


def _batch_text(decisions: list[dict]) -> str:
    lines: list[str] = []
    for d in decisions:
        text = (d.get("beschluss") or d.get("summary") or "").strip().replace("\n", " ")
        amount = d.get("amount_eur")
        signals = (
            f"Art {d.get('kind') or 'decision'} · Ergebnis {d.get('outcome') or '?'} · "
            f"Gremium {d.get('committee') or '?'} · "
            f"Betrag {f'{amount:,.0f} €'.replace(',', '.') if amount else 'keiner genannt'} · "
            f"Beschlusstext {len(d.get('beschluss') or '')} Zeichen"
        )
        lines.append(
            f"id {d['id']}: {(d.get('title') or '').strip()}\n"
            f"  Signale: {signals}\n"
            f"  Auszug: {text[:MAX_EXCERPT_CHARS]}"
        )
    return "\n\n".join(lines)


def vorlagen_kern(roh: str | None) -> str:
    """Vorlagentext ab der ersten inhaltlichen Überschrift, in einer Zeile.

    Der Briefkopf sagt nichts, was das Modell nicht ohnehin als Signal
    bekommt (Amt, Vorlagen-Nr., Beratungsfolge, Titel) — er kostet nur Platz
    im Auszug. Findet sich keine Überschrift, bleibt der Text wie er ist:
    lieber ein Briefkopf zu viel als ein leerer Auszug.
    """
    text = " ".join((roh or "").split())
    if not text:
        return ""
    m = _VORLAGE_KOPF_RE.search(text)
    return text[m.start():] if m else text


def _agenda_batch_text(items: list[dict]) -> str:
    """Ein Tagesordnungspunkt hat noch keinen Beschlusstext — dafür Signale,
    die das Modell selbst nicht kennen kann: wie oft dieselbe Formulierung
    schon dran war (Routine!), was beschlossen werden soll, was die Vorlage zu
    den Kosten sagt, durch wie viele Gremien sie geht."""
    lines: list[str] = []
    for it in items:
        wieder = int(it.get("wiederkehr") or 0)
        routine = ("erstmalig" if wieder <= 1 else
                   f"stand schon {wieder}× so auf einer Tagesordnung")
        signals = [
            f"Behandlung {it.get('behandlung') or 'unbekannt'}",
            f"Gremium {it.get('committee') or '?'}",
            f"Wiederkehr: {routine}",
        ]
        # Beschluss- oder Berichtsvorlage — die amtliche Einstufung der
        # Verwaltung, ob überhaupt etwas entschieden werden soll. Fehlte dem
        # Modell komplett, obwohl sie in der Vorlage steht.
        if it.get("art"):
            signals.append(f"Vorlagenart {it['art']}")
        if it.get("antragsteller"):
            signals.append(f"Antrag von {it['antragsteller']}")
        if it.get("stationen"):
            signals.append(f"{it['stationen']} Stationen in der Beratungsfolge")
        if it.get("amt"):
            signals.append(f"Federführung {it['amt']}")
        teile = [f"id {it['id']}: {(it.get('title') or '').strip()}",
                 "  Signale: " + " · ".join(signals)]
        if it.get("beschlussvorschlag"):
            teile.append("  Soll beschlossen werden: "
                         + " ".join(str(it["beschlussvorschlag"]).split())[:500])
        if it.get("finanz_check"):
            teile.append("  Kosten laut Vorlage: "
                         + " ".join(str(it["finanz_check"]).split())[:280])
        # Der Sachverhalt aus der Vorlage schlägt die Kurzfassung — nicht
        # umgekehrt. Die Kurzfassung entsteht allein aus dem TITEL („Du kennst
        # nur den Titel des Punktes" steht wörtlich in ihrem Prompt), das
        # Modell bewertete also eine Umformulierung der Überschrift, obwohl
        # der echte Text danebenlag.
        text = vorlagen_kern(it.get("sachverhalt")) or (it.get("summary") or "").strip()
        if text:
            teile.append(f"  Auszug: {text[:MAX_EXCERPT_CHARS]}")
        lines.append("\n".join(teile))
    return "\n\n".join(lines)


def rate_agenda_batch(items: list[dict]) -> list[tuple[int, int, str]]:
    """Bewertet Tagesordnungspunkte VOR der Sitzung → (id, score, warum).

    Eigener Prompt statt des Beschluss-Prompts (``top_wichtigkeit_*``): Vor der
    Sitzung gibt es keinen Beschlusstext, dafür Beschlussvorschlag, Kostenteil
    und — entscheidend — die Wiederkehr. „Annahme von Zuwendungen" stand 101×
    auf einer Tagesordnung; ohne dieses Signal hält jedes Modell den Punkt für
    eine Geldentscheidung (Tims Befund 15.08.). Der Grund kommt in einfacher
    Sprache zurück und steht so auf der Karte.
    """
    if not items:
        return []
    valid_ids = {it["id"] for it in items}
    _deckel_je_id = {it["id"]: formalakt_deckel(it.get("title")) for it in items}
    system = prompts.get("top_wichtigkeit_system")
    user = prompts.render("top_wichtigkeit_user", batch=_agenda_batch_text(items))
    try:
        resp = llm.chat_complete(
            model=MODEL,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=2600,
            temperature=0.1,
            _feature="impact_rating_agenda",
        )
        data = json.loads(resp.choices[0].message.content or "{}")
    except Exception:  # noqa: BLE001 — nächster Lauf versucht es erneut
        return []
    out: list[tuple[int, int, str]] = []
    for r in data.get("ratings") or []:
        try:
            iid = int(r.get("id"))
            score = int(r.get("score"))
        except (TypeError, ValueError):
            continue
        if iid in valid_ids and 0 <= score <= 100:
            warum = str(r.get("warum") or r.get("grund") or "").strip()
            deckel = _deckel_je_id.get(iid)
            if deckel is not None and score > deckel:
                score = deckel
                warum = ("Formsache: Die Straße wird nur amtlich gewidmet oder "
                         "eingezogen — für den Alltag ändert sich nichts.")
            out.append((iid, score, warum[:300]))
    return out


def rate_batch(decisions: list[dict]) -> list[tuple[int, int, str]]:
    """Bewertet einen Batch → Liste (decision_id, impact 0–100, grund).
    Halluzinierte IDs und Out-of-range-Scores werden verworfen."""
    if not decisions:
        return []
    valid_ids = {d["id"] for d in decisions}
    deckel_je_id = {d["id"]: formalakt_deckel(d.get("title")) for d in decisions}
    system = prompts.get("impact_bewertung_system")
    user = prompts.render("impact_bewertung_user", batch=_batch_text(decisions))
    try:
        resp = llm.chat_complete(
            model=MODEL,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=2200,
            temperature=0.1,
            _feature="impact_rating",
        )
        data = json.loads(resp.choices[0].message.content or "{}")
    except Exception:  # noqa: BLE001 — nächster Lauf versucht es erneut
        return []
    out: list[tuple[int, int, str]] = []
    for r in data.get("ratings") or []:
        try:
            did = int(r.get("id"))
            score = int(r.get("score"))
        except (TypeError, ValueError):
            continue
        if did in valid_ids and 0 <= score <= 100:
            grund = str(r.get("grund") or "").strip()
            deckel = deckel_je_id.get(did)
            if deckel is not None and score > deckel:
                score = deckel
                grund = ("Formsache: Die Straße wird nur amtlich gewidmet oder "
                         "eingezogen — für den Alltag ändert sich nichts.")
            out.append((did, score, grund[:300]))
    return out
