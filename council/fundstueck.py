"""Fundstück des Tages (RL-U11, Design 10a): der tägliche Öffnungsgrund.

Kuratiert je Kalendertag EINEN erzählenswerten Beschluss aus dem Archiv:
Jahrestage („Heute vor N Jahren") haben Vorrang, sofern sie mithalten;
sonst der beste noch nicht kürzlich gezeigte Fund. Bewertet wird aus ZWEI
Werten — Erzählbarkeit (``council/interest.py``) UND Tragweite
(``council/impact.py``). Interesse allein wählte Kuriositäten statt
Beschlüssen, über die man redet.
Ein LLM schreibt die 1-Satz-Story; ohne brauchbare Story gibt es für den Tag
schlicht keine Karte (das Frontend lässt sie dann ersatzlos weg).
Karten werden Tage im Voraus generiert (``scripts/generate_fundstuecke.py``)
und liegen prüfbar in ``council_fundstuecke``.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import date

from kern import llm, prompts

from .store import CouncilStore

MODEL = os.environ.get("COUNCIL_FUNDSTUECK_MODEL", "deepseek/deepseek-v4-pro")
#: Ein Jahrestag ist ein Aufhänger, kein Freifahrtschein. Bis 20.08.26 gewann
#: JEDER Jahrestag ab Interesse 45 gegen jeden Archivfund — auch gegen einen
#: mit Bestwerten. Jetzt muss er einen ordentlichen Fundwert mitbringen, und
#: ein deutlich besserer Archivfund sticht ihn (siehe ARCHIV_STICHT_UM).
MIN_FUNDWERT_JAHRESTAG = 60
MIN_FUNDWERT_ARCHIV = 65

#: Um wie viel besser ein Archivfund sein muss, um den Datumshaken zu
#: schlagen. „Heute vor 5 Jahren" ist hübsch, aber kein Selbstzweck.
ARCHIV_STICHT_UM = 12

REUSE_BLOCK_DAYS = 180

#: Wie lange ein THEMA gesperrt bleibt. Kürzer als die ID-Sperre: Derselbe
#: Beschluss darf ein halbes Jahr nicht wieder, dasselbe Thema aber schon
#: nach anderthalb Monaten.
THEMA_BLOCK_DAYS = 45

#: Wörter, die fast jeder Ratsbeschluss trägt — sie taugen nicht, um ein
#: Thema zu erkennen, und würden alles sperren.
_ALLERWELT = {
    "oldenburg", "stadt", "staedtische", "städtische", "staedtischen", "städtischen",
    "beschluss", "beschlusses", "antrag", "antrags", "bericht", "berichts",
    "fraktion", "fraktionen", "vorlage", "satzung", "aenderung", "änderung",
    "aenderungen", "änderungen", "verwaltung", "sitzung", "gruppe", "ausschuss",
    "gemeinsamer", "gemeinsame", "weiteren", "weitere", "sachstand",
}
MAX_BESCHLUSS_CHARS = 4000


def _kernworte(title: str) -> set[str]:
    """Die eigentümlichen Wörter eines Titels — daran hängt das Thema.

    Sechs Zeichen aufwärts, ohne die Allerweltswörter: „Stadionneubau",
    „Maastrichter", „Ausfallbürgschaft" bleiben; „Beschluss", „Stadt",
    „Oldenburg" fliegen raus.
    """
    worte = re.findall(r"[A-Za-zÄÖÜäöüß]{6,}", (title or "").lower())
    return {w for w in worte if w not in _ALLERWELT}


def _thema_frei(title: str, confidential: list[set[str]]) -> bool:
    """Kein eigentümliches Wort mit einem der letzten Funde gemeinsam."""
    meine = _kernworte(title)
    return not any(meine & andere for andere in confidential)


def pick_candidate(store: CouncilStore, day: date) -> tuple[dict, int] | None:
    """Wählt den Beschluss für ``day`` → (decision, years_ago); years_ago 0 =
    kein Jahrestag. Deterministisch je Tag (Hash-Seed statt Zufall — Läufe
    sind wiederholbar, Resume-sicher und redaktionell nachvollziehbar).

    Der Jahrestag hat Vorrang, aber keinen Vorrang um jeden Preis: Ist der
    beste Archivfund deutlich stärker, gewinnt er. Vorher schlug jeder
    Jahrestag ab Interesse 45 alles andere — dadurch stand an manchen Tagen
    eine Straßenbenennung, während ein 79-Millionen-Beschluss wartete.
    """
    used = store.recent_fundstueck_decision_ids(REUSE_BLOCK_DAYS)
    confidential = [_kernworte(t) for t in
                store.recent_fundstueck_titles(THEMA_BLOCK_DAYS)]

    # 1) Archiv-Feld zuerst holen: Es ist der Maßstab, an dem sich der
    #    Jahrestag messen lassen muss.
    # Großzügig holen: Erst NACH der Abfrage greifen Themen-Sperre und
    # Fundwert-Schwelle. Bei 25 war das Feld nach zwei Wochen leer, und der
    # Generator ließ Tage ohne Karte (gemessen 20.08.26).
    top = [c for c in store.fundstueck_candidates(exclude_ids=used, limit=120)
           if (c.get("fundwert") or 0) >= MIN_FUNDWERT_ARCHIV
           and _thema_frei(c.get("title") or "", confidential)]

    # 2) Jahrestag: gleicher Kalendertag, früheres Jahr, ordentlicher Wert.
    mmdd = day.strftime("%m-%d")
    for c in store.fundstueck_candidates(mmdd=mmdd, exclude_ids=used, limit=5):
        if (c.get("fundwert") or 0) < MIN_FUNDWERT_JAHRESTAG:
            continue
        if not _thema_frei(c.get("title") or "", confidential):
            continue
        years = day.year - int(str(c["session_date"])[:4])
        if years < 1:
            continue
        bester = top[0]["fundwert"] if top else 0
        if bester - (c.get("fundwert") or 0) > ARCHIV_STICHT_UM:
            break                       # der Archivfund ist deutlich besser
        return c, years

    # 3) Archiv-Fund: unter den Top-Kandidaten deterministisch je Tag streuen,
    #    damit nicht wochenlang derselbe Spitzenreiter wartet, falls ein Lauf
    #    Tage überspringt. Nur die besten fünf — bei zehn landete zu oft der
    #    schwächste im Feld auf der Karte.
    if not top:
        return None
    seed = int(hashlib.sha256(day.isoformat().encode()).hexdigest(), 16)
    return top[seed % min(len(top), 5)], 0


def write_story(decision: dict) -> str | None:
    """Der eine Satz der Karte. None = Antwort unbrauchbar (Tag bleibt leer)."""
    system = prompts.get("daily_find_story_system")
    user = prompts.render(
        "daily_find_story_user",
        session_date=str(decision.get("session_date") or ""),
        committee=decision.get("committee") or "",
        outcome=decision.get("outcome") or "unbekannt",
        title=(decision.get("title") or "").strip(),
        interest_reason=decision.get("interest_reason") or "",
        official_text=(decision.get("official_text") or decision.get("summary") or "")[:MAX_BESCHLUSS_CHARS],
    )
    try:
        resp = llm.chat_complete(
            model=MODEL,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=300,
            temperature=0.4,
            _feature="daily_find_story",
        )
        data = json.loads(resp.choices[0].message.content or "{}")
    except Exception:  # noqa: BLE001 — nächster Lauf füllt den Tag erneut
        return None
    story = (data.get("story") or "").strip()
    if not story or len(story) > 260:
        return None
    return story


def kicker_for(years_ago: int) -> str:
    if years_ago == 1:
        return "Heute vor einem Jahr"
    if years_ago > 1:
        return f"Heute vor {years_ago} Jahren"
    return "Aus dem Archiv"


def generate_for_day(store: CouncilStore, day: date) -> bool:
    """Erzeugt (falls möglich) das Fundstück für einen Tag. True = gespeichert."""
    picked = pick_candidate(store, day)
    if not picked:
        return False
    decision, years = picked
    # interest_reason für den Story-Prompt nachladen (Kandidaten-Query ist schlank).
    full = store.get_decision(decision["id"]) or decision
    full.setdefault("committee", decision.get("committee"))
    full.setdefault("session_date", decision.get("session_date"))
    story = write_story(full)
    if not story:
        return False
    store.save_fundstueck(day.isoformat(), decision["id"], kicker_for(years), story)
    return True
