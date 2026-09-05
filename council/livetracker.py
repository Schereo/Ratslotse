"""Live-Verfolgung der Ratssitzung: Welcher TOP läuft gerade, wer spricht?

Läuft im Mitschnitt-Job (``scripts/record_council_livestream.py``) je
fertigem Audio-Stück: Das Transkript des Stücks (plus 30 s Überlappung) geht zusammen
mit der Tagesordnung, dem Sprecher-Verzeichnis und dem letzten Stand an ein
schnelles Modell, das antwortet, welcher Punkt am Ende des Fensters läuft,
in welcher Phase, und wer das Wort hat. Das Ergebnis steht in
``council_live_state`` — eine Zeile je Sitzung — und die Live-Karte in
Web und App liest sie.

Gemessen am 05.09.2026 gegen die Aufzeichnung der Ratssitzung vom 31.08.
(3 h 49 min, Gemini 2.5 Flash für beides), mit 30-s- und 120-s-Stücken:

- Kosten je Sitzung: 30-s-Stücke 0,58 $ Transkription + 0,47 $ Verfolgung
  (459 Aufrufe); 120-s-Stücke 0,47 $ + 0,14 $.
- Jeder TOP mit Aussprache wurde richtig verfolgt, auch die Umnummerierung
  eines Dringlichkeitsantrags; zwischen zwei Abstimmungen stimmte die
  Anzeige bei beiden Stücklängen in denselben Minuten (52 % bzw. 50 % —
  der Rest sind Strecken, in denen die Abstimmungs-Zeitmarken als
  Wahrheit taugen, nicht die Anzeige: Punkte ohne Abstimmung, Blöcke).
- Der neue Punkt ist mit 30-s-Stücken im Median 40 s nach seinem Aufruf
  sichtbar (20–55 s), mit 120-s-Stücken bis zu 125 s.
- Die Grenze ist die Zeitauflösung, nicht die Erkennung: Formalien, die im
  Block in einer Minute durchlaufen (vier Veränderungssperren in 50 s),
  erscheinen nicht einzeln. Dafür gibt es ``block_start`` — die Karte sagt
  dann „TOP 9.4–9.8".
- Sprecher: Ohne Verzeichnis riet das Modell die Fraktion in rund 30 % der
  Fälle falsch. Mit der Anwesenheitsliste der vorigen Ratssitzung
  (``CouncilStore.council_roster_before``) und unscharfem Nachnamen-
  Abgleich (die Erkennung verschreibt: Bark → Baak, Pichotta → Piechotta) stand in
  355 von 456 Stücken Name und Fraktion (31 verschiedene Sprecher). Die
  Sitzungsleitung kündigt fast
  jede Rednerin an („Herr Ellberg, dann Herr Paul") — daraus, nicht aus
  der Stimme.

Der Verzug gegenüber dem Saal ist Stücklänge plus Transkription (~2 s je
30-s-Stück) plus Verfolgung (~1,5 s), dazu die Latenz des HLS-Streams
selbst — zusammen unter einer Minute. ``as_of`` trägt den
Audio-Stand, den eine Zeile abbildet; die Clients rechnen daraus „vor
N Min." mit ihrer eigenen Uhr und sagen ehrlich dazu, woher es kommt.
"""
from __future__ import annotations

import difflib
import json
import logging
import os
import re
from datetime import datetime, timedelta

from council.videos import strip_prefix
from kern import llm

log = logging.getLogger(__name__)

TRACKER_MODEL = os.environ.get("COUNCIL_LIVE_TRACKER_MODEL", "google/gemini-2.5-flash")
#: Wie viel vom Vorgänger-Fenster mit ins Transkript geht — ein Aufruf, der
#: kurz vor der Stück-Grenze fiel, steht sonst in keinem Fenster ganz.
OVERLAP_SECONDS = 30
#: Ab dieser Ähnlichkeit des Nachnamens gilt ein gehörter Name als
#: Ratsmitglied (difflib-Ratio; Bark→Baak 0,75, Pichotta→Piechotta 0,94).
MATCH_THRESHOLD = 0.72
PHASES = ("aufruf", "aussprache", "abstimmung", "pause", "unklar", "ende")

TRACKER_SYSTEM = """Du verfolgst live eine Sitzung des Oldenburger Stadtrats anhand eines
Transkripts. Du bekommst die Tagesordnung, das Verzeichnis der Ratsmitglieder,
den zuletzt bekannten Stand und das jüngste Transkript-Fenster. Antworte NUR
mit JSON:
{"transitions": [{"at": "<mm:ss aus dem Transkript>",
                  "kind": "top|vote|speaker",
                  "top": "<Nummer aus der Tagesordnung oder null>",
                  "speaker": "<Name oder null>", "party": "<Fraktion oder null>",
                  "evidence": "<wörtliches Zitat ≤ 80 Zeichen>"}],
 "top": "<Nummer aus der Tagesordnung oder null>",
 "top_confidence": 0.0-1.0,
 "phase": "aufruf|aussprache|abstimmung|pause|unklar",
 "speaker": "<Name, wie im Transkript genannt, oder null>",
 "party": "<Fraktion/Gruppe oder Verwaltung oder null>",
 "evidence": "<wörtliches Zitat ≤ 120 Zeichen, das TOP oder Sprecher belegt>"}

Regeln:
- "transitions" listet JEDEN Wechsel im Fenster in zeitlicher Reihenfolge: ein
  neuer TOP wird aufgerufen (kind top), eine Abstimmung findet statt (kind
  vote), jemand bekommt das Wort (kind speaker). Die Zeit ist die Marke des
  Absatzes, in dem es passiert. Mehrere TOPs in einer Minute (Formalien,
  Veränderungssperren) sind normal — jeden einzeln nennen.
- "top" ist der Stand am ENDE des Fensters.
- Die Sitzungsleitung ruft Punkte auf („Wir kommen zu Tagesordnungspunkt 9.3",
  „Punkt 10.2, Antrag der Fraktion …") und erteilt das Wort („Frau Müller für
  die Fraktion Bündnis 90/Die Grünen"). Nur daraus schließen; nicht raten.
- Die Spracherkennung frisst Punkte in Nummern: „93" kann 9.3 sein — gegen
  Titel der Tagesordnung prüfen.
- Bleibt der TOP unerwähnt, gilt der letzte bekannte weiter (top_confidence
  dann ≤ 0.6). Ohne Anhaltspunkt für den Sprecher: speaker null.
- Sprecher NUR aus dem Verzeichnis, in dessen Schreibweise; die Fraktion aus
  dem Verzeichnis. Wer dort nicht steht (Einwohner*in, Gast): speaker null.
- Verwaltung sind Oberbürgermeister und Dezernent*innen."""


def norm_top(value) -> str | None:
    """„Ö 9.3" / „9.3" / „TOP 9.3" → „9.3"; „DZT 1" bleibt (s. videos.strip_prefix)."""
    if value is None:
        return None
    s = re.sub(r"^\s*TOP\s+", "", str(value).strip(), flags=re.I)
    s = strip_prefix(s).strip()
    return s or None


def match_speaker(spoken: str | None, people: list[dict]) -> dict | None:
    """Gehörter Name → Zeile des Verzeichnisses (oder None).

    Verglichen wird der Nachname; Anreden und Titel fliegen vorher raus. Ein
    exakter Treffer schlägt jeden unscharfen."""
    if not spoken:
        return None
    s = re.sub(r"^(?:(?:herr|herrn|frau|dr\.?|prof\.?)\s+)+", "", spoken.strip(), flags=re.I)
    s = s.strip().lower()
    if not s:
        return None
    gesagt_nachname = s.split()[-1]
    best, score = None, 0.0
    for person in people:
        name = person.get("name") or ""
        if not name:
            continue
        last = name.split()[-1].lower()
        if s == name.lower() or gesagt_nachname == last:
            r = 1.0
        else:
            r = difflib.SequenceMatcher(None, gesagt_nachname, last).ratio()
        if r > score:
            best, score = person, r
    return best if score >= MATCH_THRESHOLD else None


def party_of(person: dict) -> str | None:
    party = (person.get("party") or "").strip()
    if party:
        return party
    return "Verwaltung" if person.get("role") == "administration" else None


def agenda_text(items: list[dict]) -> str:
    return "\n".join(f"{it['item_number']}\t{it['title']}" for it in items)


def roster_text(people: list[dict]) -> str:
    return "\n".join(f"{p['name']}\t{party_of(p) or ''}" for p in people)


def _empty(previous: dict) -> dict:
    return {"transitions": [], "top": previous.get("top"), "top_confidence": 0,
            "phase": "unklar", "speaker": None, "party": None, "evidence": ""}


def parse_response(raw: str, previous: dict) -> dict:
    """Modellantwort → dict; bei Bruch (abgeschnitten, Prosa) der alte Stand."""
    raw = re.sub(r"^```(?:json)?|```$", "", (raw or "").strip(), flags=re.M).strip()
    inner = re.search(r"\{.*\}", raw, re.S)
    for candidate in (raw, inner.group(0) if inner else ""):
        try:
            data = json.loads(candidate)
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(data, dict):
            data.setdefault("transitions", [])
            if not isinstance(data["transitions"], list):
                data["transitions"] = []
            return data
    return _empty(previous)


def track_window(agenda: str, roster: str, state: dict, window_text: str,
                 t_from: int, t_to: int, model: str = TRACKER_MODEL) -> dict:
    """Ein Tracker-Aufruf für ein Fenster (Sekunden seit Aufnahmestart)."""
    user = (f"TAGESORDNUNG (Nummer<TAB>Titel):\n{agenda}\n\n"
            f"RATSMITGLIEDER (Name<TAB>Fraktion):\n{roster or '(kein Verzeichnis)'}\n\n"
            f"LETZTER STAND: {json.dumps(state, ensure_ascii=False)}\n\n"
            f"TRANSKRIPT {t_from // 60}:{t_from % 60:02d}–{t_to // 60}:{t_to % 60:02d} "
            f"seit Aufnahmestart:\n{window_text}")
    resp = llm.chat_complete(
        model=model, _feature="live_top_tracker", _allow_empty_response=True,
        messages=[{"role": "system", "content": TRACKER_SYSTEM},
                  {"role": "user", "content": user}],
        temperature=0, response_format={"type": "json_object"}, max_tokens=2500,
    )
    if not getattr(resp, "choices", None):
        return _empty(state)
    return parse_response(resp.choices[0].message.content or "", state)


def _seconds(mark) -> int | None:
    m = re.match(r"\s*(\d+):(\d{2})", str(mark or ""))
    return int(m.group(1)) * 60 + int(m.group(2)) if m else None


def format_window(segments: list[tuple[float, str]]) -> str:
    return "\n".join(f"[{int(t) // 60}:{int(t) % 60:02d}] {body}" for t, body in segments)


class LiveTracker:
    """Hält den Stand einer laufenden Sitzung und schreibt ihn je Stück.

    ``on_chunk`` passt auf ``livestream.record_and_transcribe(on_chunk=…)``.
    Ein Fehler im Modellaufruf lässt den alten Stand stehen und den Mitschnitt
    weiterlaufen — der Live-Stand ist Zugabe, nicht Auftrag."""

    def __init__(self, store, ksinr: int, chunk_seconds: int,
                 started_at: datetime | None = None, model: str = TRACKER_MODEL):
        self.store = store
        self.ksinr = ksinr
        self.chunk_seconds = chunk_seconds
        self.model = model
        self.started_at = started_at or datetime.now().astimezone()
        self.agenda = [it for it in store.agenda_items(ksinr) if it.get("is_public")]
        self.titles = {norm_top(it["item_number"]): it["title"] for it in self.agenda}
        self.people = store.council_roster_before(ksinr)
        self._agenda_text = agenda_text(self.agenda)
        self._roster_text = roster_text(self.people)
        self.state: dict = {"top": None, "speaker": None, "party": None}
        self.since: datetime = self.started_at
        self.segments: list[tuple[float, str]] = []
        self.updates = 0
        store.clear_live_state(ksinr)
        if not self.people:
            log.warning("Sitzung %s: kein Sprecher-Verzeichnis — Fraktionen bleiben leer", ksinr)

    # ------------------------------------------------------------- Haken

    def on_chunk(self, idx: int, segments: list[tuple[float, str]], closing: bool) -> None:
        self.segments.extend(segments)
        t_from = idx * self.chunk_seconds
        t_to = (idx + 1) * self.chunk_seconds
        window = [s for s in self.segments if t_from - OVERLAP_SECONDS <= s[0] < t_to]
        if not window:
            if closing:
                self.finish(t_to)
            return
        res = track_window(self._agenda_text, self._roster_text, self.state,
                           format_window(window), t_from, t_to, self.model)
        self.apply(res, t_from, t_to, closing)

    def apply(self, res: dict, t_from: int, t_to: int, closing: bool = False) -> dict:
        """Modellantwort in Stand + Ereignisse übersetzen und speichern."""
        events = self._events(res, t_from)
        top = norm_top(res.get("top")) or self.state.get("top")
        # Welche TOPs sind im Fenster durchgelaufen? Mehr als einer → Block.
        tops_seen: list[str] = []
        for e in events:
            n = e.get("item_number")
            if n and n not in tops_seen:
                tops_seen.append(n)
        block_start = tops_seen[0] if len(tops_seen) >= 2 and tops_seen[-1] == top else None

        if top != self.state.get("top"):
            first = next((e for e in events if e.get("item_number") == top), None)
            at = first["at_seconds"] if first else t_from
            self.since = self.started_at + timedelta(seconds=at)

        person = match_speaker(res.get("speaker"), self.people)
        if person:
            speaker, party = person["name"], party_of(person)
        else:
            speaker = None
            party = res.get("party") if res.get("party") == "Verwaltung" else None
        phase = res.get("phase") if res.get("phase") in PHASES else "unklar"
        finished = bool(closing)
        if finished:
            phase = "ende"
        self.state = {"top": top, "speaker": speaker, "party": party}
        row = {
            "item_number": top, "item_title": self.titles.get(top),
            "block_start": block_start, "phase": phase,
            "speaker": speaker, "party": party,
            "evidence": (res.get("evidence") or "")[:200] or None,
            "since": self.since.isoformat(timespec="seconds"),
            "as_of": (self.started_at + timedelta(seconds=t_to)).isoformat(timespec="seconds"),
            "finished": finished,
        }
        self.store.save_live_state(self.ksinr, row, self.model)
        self.store.add_live_events(self.ksinr, events)
        self.updates += 1
        log.info("Live %s: TOP %s (%s) %s%s", self.ksinr, top, phase,
                 speaker or "–", f" ({party})" if party else "")
        return row

    def finish(self, t_to: int | None = None) -> None:
        """Nach der Schlussformel (oder dem Aufnahme-Ende): Stand als
        beendet markieren, damit die Karte nicht „gerade" sagt."""
        current = self.store.get_live_state(self.ksinr)
        if current and current.get("finished"):
            return
        as_of = self.started_at + timedelta(seconds=t_to) if t_to is not None else datetime.now().astimezone()
        row = {**(current or {}), "phase": "ende", "finished": True,
               "as_of": as_of.isoformat(timespec="seconds"),
               "since": (current or {}).get("since") or self.since.isoformat(timespec="seconds")}
        self.store.save_live_state(self.ksinr, row, self.model)

    # ---------------------------------------------------------- Ereignisse

    def _events(self, res: dict, t_from: int) -> list[dict]:
        out: list[dict] = []
        for tr in res.get("transitions") or []:
            if not isinstance(tr, dict):
                continue
            kind = tr.get("kind") if tr.get("kind") in ("top", "vote", "speaker") else "top"
            at = _seconds(tr.get("at"))
            person = match_speaker(tr.get("speaker"), self.people)
            out.append({
                "at_seconds": at if at is not None else t_from,
                "kind": kind,
                "item_number": norm_top(tr.get("top")),
                "speaker": person["name"] if person else None,
                "party": party_of(person) if person else None,
                "evidence": (tr.get("evidence") or "")[:120] or None,
            })
        out.sort(key=lambda e: e["at_seconds"])
        return out
