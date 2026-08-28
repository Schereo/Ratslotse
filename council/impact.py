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

# gpt-5.6-luna nach dem Vergleich vom 28.08.26 (55 echte Tagesordnungspunkte,
# gegen deepseek-v4-pro, gpt-5.1 und gpt-5-mini): behält als einziges Modell
# durchgängig Beträge, Hektar und Ortsnamen, trifft Rechtsinstrumente genauer
# (Veränderungssperre ≠ „Bauverbot") — und kostet ein Viertel.
MODEL = os.environ.get("COUNCIL_IMPACT_MODEL", "openai/gpt-5.6-luna")

#: Für die Bewertung reicht kurzes Nachdenken: Mit dem Standard-Aufwand
#: verbrannte Luna das Doppelte an Denk-Tokens für identische Ergebnisse.
#: Aufrufer-Angabe schlägt diesen Default (siehe kern.llm MODEL_PARAMS).
REASONING_KURZ = {"reasoning": {"effort": "low"}}
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


def _nachgefasst(rest_von, ausgefallen: list[dict], tiefe: int,
                feature: str) -> list[tuple[int, int, str]]:
    """Zweiter Anlauf für ausgefallene oder ausgelassene Punkte.

    Zwei Fehlerarten, die vorher STILL Punkte kosteten (Luna-Test 28.08.26:
    zweimal 55 Punkte angefragt, 20 bzw. 40 zurück — kein Log, nichts):

    ① Der ganze Aufruf scheitert (Provider-Fehler jenseits der Retries in
      ``kern.llm``). Vorher: ganze Tranche weg. Jetzt: halbieren und je
      Hälfte neu — ein vergifteter Einzelpunkt kostet so höchstens sich
      selbst, ein transienter Fehler meist gar nichts.
    ② Der Aufruf gelingt, aber das Modell lässt Einträge aus. Vorher fiel
      das niemandem auf. Jetzt werden die fehlenden IDs einzeln nachgefragt.

    ``tiefe`` begrenzt die Rekursion; ab 2 wird aufgegeben UND GESAGT.
    """
    if not ausgefallen:
        return []
    if tiefe >= 2:
        print(f"  ⚠️ {feature}: {len(ausgefallen)} Punkte auch im Nachfassen "
              f"ohne Bewertung — nächster Lauf versucht es erneut")
        return []
    if len(ausgefallen) == 1:
        return rest_von(ausgefallen, _tiefe=tiefe + 1)
    mitte = len(ausgefallen) // 2
    return (rest_von(ausgefallen[:mitte], _tiefe=tiefe + 1)
            + rest_von(ausgefallen[mitte:], _tiefe=tiefe + 1))


def rate_agenda_batch(items: list[dict], _tiefe: int = 0) -> list[tuple[int, int, str]]:
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
            extra_body=dict(REASONING_KURZ),
            _feature="impact_rating_agenda",
        )
        data = json.loads(resp.choices[0].message.content or "{}")
    except Exception as exc:  # noqa: BLE001
        print(f"  ⚠️ Tragweite-Batch ({len(items)} Punkte) fehlgeschlagen: "
              f"{exc!r} — fasse in Hälften nach")
        return _nachgefasst(rate_agenda_batch, items, _tiefe, "Tragweite (Tagesordnung)")
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
    fehlend = valid_ids - {iid for iid, _s, _w in out}
    if fehlend:
        out += _nachgefasst(rate_agenda_batch,
                            [it for it in items if it["id"] in fehlend],
                            _tiefe, "Tragweite (Tagesordnung)")
    return out


def rate_batch(decisions: list[dict], _tiefe: int = 0) -> list[tuple[int, int, str]]:
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
            extra_body=dict(REASONING_KURZ),
            _feature="impact_rating",
        )
        data = json.loads(resp.choices[0].message.content or "{}")
    except Exception as exc:  # noqa: BLE001
        print(f"  ⚠️ Tragweite-Batch ({len(decisions)} Beschlüsse) fehlgeschlagen: "
              f"{exc!r} — fasse in Hälften nach")
        return _nachgefasst(rate_batch, decisions, _tiefe, "Tragweite (Beschlüsse)")
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
    fehlend = valid_ids - {did for did, _s, _g in out}
    if fehlend:
        out += _nachgefasst(rate_batch,
                            [d for d in decisions if d["id"] in fehlend],
                            _tiefe, "Tragweite (Beschlüsse)")
    return out
