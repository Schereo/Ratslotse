"""Argumente und Fraktionen zu einem Vorgang — die Reiter der Punkt-Seite.

Plan: ``docs/plan-punkt-argumente.md`` (Schritt 6 der Sitzungsseite).

Zwei Teile, mit Absicht verschieden gebaut:

* **Fraktionen** entstehen OHNE Modell. Die Wortbeiträge in
  ``council_speeches`` sind schon Paraphrasen aus dem Protokoll („Ratsherr
  Niederstein spricht sich gegen eine Vertagung aus …"); sie werden nur nach
  Fraktion geordnet. Was das Protokoll keiner Fraktion zuordnet, steht unter
  „Fraktion im Protokoll nicht genannt".
* **Argumente** ordnet ein Modell zu Streitpunkten mit Dafür und Dagegen. Es
  bekommt nummerierte Quellen und muss für jede Aussage die Kennung nennen.
  **Wer etwas gesagt hat, entscheidet nicht das Modell**, sondern die Quelle:
  Person, Fraktion, Gremium, Datum und Seite werden nach dem Parsen aus dem
  Wortbeitrag übernommen. Eine Aussage ohne gültige Kennung fällt weg; ein
  Streitpunkt ohne beide Seiten auch.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from typing import Any

from kern import llm, prompts

from .impact import vorlagen_kern

#: Wie die Kartentexte: GPT-6 Luna im Flex-Tarif, kein Feature mit
#: Nutzereingabe (``llm.OHNE_NUTZEREINGABE``).
MODEL = os.environ.get("COUNCIL_ARGUMENTS_MODEL", "openai/gpt-6-luna")

#: Höchstens so viele Wortbeiträge gehen ins Modell (die jüngsten zuerst
#: abgeschnitten, ältere fallen weg) — eine Ratsdebatte über den Fliegerhorst
#: hat Hunderte.
MAX_BEITRAEGE = 60
#: Zeichen aus der Vorlage (ab „Sachverhalt"/„Begründung"), in Stücken.
VORLAGE_ZEICHEN = 6_000
VORLAGE_STUECK = 1_500
#: Eine Paraphrase hat höchstens zwei Sätze; was länger ist, hat das Modell
#: nicht paraphrasiert, sondern abgeschrieben.
MAX_TEXT = 320

#: Unter dieser Menge erscheint der Reiter nicht (Plan § 6): zwei Seiten mit je
#: zwei Aussagen bzw. zwei Fraktionen mit je einer Wortmeldung.
MIN_JE_SEITE = 2
MIN_FRAKTIONEN = 2


def subject_key(template_number: str | None, title_core: str | None) -> str | None:
    """Der Vorgang hinter einem Punkt: die Vorlage, sonst der datierte Titel."""
    tn = (template_number or "").strip()
    if tn:
        return f"tn:{tn}"
    titel = (title_core or "").strip()
    return f"titel:{titel}" if titel else None


def sources_hash(speech_ids: list[int], template_number: str | None) -> str:
    roh = json.dumps([sorted(speech_ids), template_number or ""])
    return hashlib.sha256(roh.encode()).hexdigest()[:16]


def factions(speeches: list[dict]) -> list[dict]:
    """Wortmeldungen nach Fraktion — ohne Modell, älteste zuerst je Fraktion.
    Fraktionen mit den meisten Wortmeldungen oben; „nicht genannt" zuletzt."""
    gruppen: dict[str, list[dict]] = {}
    for s in speeches:
        gruppen.setdefault((s.get("party") or "").strip(), []).append(s)
    out = [{"party": p or None, "statements": [_aussage(s) for s in sorted(ss, key=lambda x: x["date"])]}
           for p, ss in gruppen.items()]
    out.sort(key=lambda g: (g["party"] is None, -len(g["statements"]), g["party"] or ""))
    return out


def _aussage(s: dict, text: str | None = None) -> dict:
    return {
        "text": text if text is not None else s["text"],
        "speaker": s.get("speaker"),
        "party": (s.get("party") or "").strip() or None,
        "body": s.get("committee"),
        "date": s.get("date"),
        "source": {"kind": s["kind"], "id": s["id"], "page": s.get("page")},
    }


def vorlage_stuecke(raw_text: str | None) -> list[str]:
    kern = vorlagen_kern(raw_text)[:VORLAGE_ZEICHEN]
    return [kern[i:i + VORLAGE_STUECK] for i in range(0, len(kern), VORLAGE_STUECK) if kern[i:i + VORLAGE_STUECK].strip()]


def build_input(title: str, speeches: list[dict], template: dict | None, outcome_note: str | None) -> tuple[str, dict[str, dict]]:
    """Der Nutzer-Text für das Modell und das Verzeichnis der Quellen.

    Kennungen: ``W<id>`` für Wortbeiträge (die Datenbank-Kennung, damit eine
    Aussage auch nach Wochen noch auf ihren Beitrag zeigt), ``V<n>`` für
    Abschnitte der Vorlage."""
    quellen: dict[str, dict] = {}
    zeilen = [f"VORGANG: {title}"]
    if outcome_note:
        zeilen.append(f"ERGEBNIS ZULETZT: {outcome_note}")
    zeilen.append("")
    for s in speeches[-MAX_BEITRAEGE:]:
        k = f"W{s['id']}"
        quellen[k] = {**s, "kind": "speech"}
        wer = s.get("speaker") or "unbekannt"
        partei = f" ({s['party']})" if s.get("party") else ""
        zeilen.append(f"[{k}] {s.get('date')} · {s.get('committee')} · {wer}{partei}: {' '.join((s.get('text') or '').split())}")
    if template:
        for i, stueck in enumerate(vorlage_stuecke(template.get("raw_text")), start=1):
            k = f"V{i}"
            quellen[k] = {"id": template["kvonr"], "kind": "template", "speaker": "Verwaltung", "party": None,
                          "committee": f"Vorlage {template.get('template_number') or ''}".strip(),
                          "date": template.get("date"), "page": None, "text": stueck}
            zeilen.append(f"[{k}] Vorlage der Verwaltung: {' '.join(stueck.split())}")
    return "\n".join(zeilen), quellen


def parse(roh: str, quellen: dict[str, dict]) -> dict[str, Any] | None:
    """Antwort des Modells → gespeicherte Form. Verwirft jede Aussage ohne
    gültige Kennung und jeden Streitpunkt ohne beide Seiten; Urheber kommen
    aus der Quelle. ``None``, wenn die Antwort kein JSON ist."""
    roh = (roh or "").strip()
    if roh.startswith("```"):
        roh = roh.strip("`")
        roh = roh[roh.find("{"):]
    try:
        d = json.loads(roh)
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(d, dict):
        return None

    def aussagen(liste: Any) -> list[dict]:
        out = []
        gesehen = set()
        for a in liste if isinstance(liste, list) else []:
            if not isinstance(a, dict):
                continue
            k = str(a.get("source") or "").strip().strip("[]")
            text = " ".join(str(a.get("text") or "").split())
            if k not in quellen or not text or len(text) > MAX_TEXT or (k, text) in gesehen:
                continue
            gesehen.add((k, text))
            out.append(_aussage(quellen[k], text))
        return out

    issues = []
    for i in d.get("issues") if isinstance(d.get("issues"), list) else []:
        if not isinstance(i, dict):
            continue
        frage = " ".join(str(i.get("question") or "").split())
        pro, contra = aussagen(i.get("pro")), aussagen(i.get("contra"))
        if frage and pro and contra:
            issues.append({"question": frage[:200], "pro": pro, "contra": contra})
    weitere = d.get("further") if isinstance(d.get("further"), dict) else {}
    return {"issues": issues[:3], "further": {"pro": aussagen(weitere.get("pro")), "contra": aussagen(weitere.get("contra"))}}


def counts(payload: dict) -> tuple[int, int]:
    """(dafür, dagegen) über Streitpunkte und weitere Argumente."""
    pro = sum(len(i["pro"]) for i in payload.get("issues", [])) + len(payload.get("further", {}).get("pro", []))
    contra = sum(len(i["contra"]) for i in payload.get("issues", [])) + len(payload.get("further", {}).get("contra", []))
    return pro, contra


def zeigen(payload: dict | None) -> bool:
    """Reicht es für den Reiter „Argumente"?"""
    if not payload:
        return False
    pro, contra = counts(payload)
    return pro >= MIN_JE_SEITE and contra >= MIN_JE_SEITE


def fraktionen_zeigen(gruppen: list[dict]) -> bool:
    return sum(1 for g in gruppen if g["party"]) >= MIN_FRAKTIONEN


def generate(title: str, speeches: list[dict], template: dict | None, outcome_note: str | None) -> dict | None:
    """Ein Modellaufruf je Vorgang. ``None`` ohne Stoff oder bei kaputter Antwort."""
    if len(speeches) < 2:
        return None
    nutzer, quellen = build_input(title, speeches, template, outcome_note)
    resp = llm.chat_complete(
        model=MODEL, response_format={"type": "json_object"},
        messages=[{"role": "system", "content": prompts.get("item_arguments_system")},
                  {"role": "user", "content": nutzer}],
        max_tokens=3_000, _feature="item_arguments", _geduld=True, _ersatz=llm.ersatz_fuer(MODEL),
        _tarif="flex")
    return parse(resp.choices[0].message.content or "", quellen)


def re_nummer(item_number: str | None) -> str:
    return re.sub(r"^\D+", "", item_number or "").strip()
