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

**Nur eine Ratssitzung wird verfolgt.** Am 28.09.2026 fiel die Übertragung
aus; O1 sendete sechs Stunden Ersatzprogramm (Kinder-Uni, ein
Philosophie-Gespräch, Lesungen, ein Vortrag zur Stadtgestaltung). Der
Tracker machte daraus die „Einwohnerfragestunde" (Publikumsfragen der
Kinder-Uni) und ab 20:07 Uhr TOP 10.1 „Innenentwicklung" (der Vortrag) —
ohne dass im ganzen Abend ein einziger Punkt aufgerufen worden wäre. Deshalb:

- Das Modell beurteilt je Fenster, ob überhaupt eine Ratssitzung läuft
  (``broadcast``).
- Ein TOP-Wechsel braucht einen **Aufruf**: ein wörtliches Zitat aus dem
  Fenster, das den Punkt beim Namen nennt (Nummer oder ein Wort aus dem
  Titel). Ein Thema, das zum Titel passt, reicht nicht.
- Gezeigt wird erst ab dem ersten solchen Aufruf (``on_air``). Läuft
  ``OFF_AIR_SECONDS`` lang etwas anderes, wird der Stand zurückgezogen;
  kommt die Sitzung zurück, erscheint er nach ``RESUME_SECONDS`` wieder.
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

#: Gemini 2.5 Flash läuft bei OpenRouter am 20.10.2026 aus. Prüfstand
#: `live-verfolgung` (30 Fenster, je zwei Läufe, 23.09.2026): 2.5 Flash 100 %,
#: 3.5 Flash Lite 100 %, 3 Flash Preview 100 %, 3.1 Flash Lite 98,3 % — alle im
#: Rauschen. Hier zählt der Verzug: 3.5 Flash Lite antwortet in 1,1 s (p50)
#: statt 1,8 s, zum selben Preis je Aufruf (0,16 ct). 3.1 Flash Lite wäre ein
#: Viertel billiger, braucht aber 2,2 s. Stand: docs/modell-pruefstand.md.
TRACKER_MODEL = os.environ.get("COUNCIL_LIVE_TRACKER_MODEL", "google/gemini-3.5-flash-lite")
#: Wie viel vom Vorgänger-Fenster mit ins Transkript geht — ein Aufruf, der
#: kurz vor der Stück-Grenze fiel, steht sonst in keinem Fenster ganz.
OVERLAP_SECONDS = 30
#: Ab dieser Ähnlichkeit des Nachnamens gilt ein gehörter Name als
#: Ratsmitglied (difflib-Ratio; Bark→Baak 0,75, Pichotta→Piechotta 0,94).
MATCH_THRESHOLD = 0.72
PHASES = ("aufruf", "aussprache", "abstimmung", "pause", "unklar", "ende")
#: Urteil des Modells je Fenster: Läuft eine Ratssitzung?
BROADCASTS = ("rat", "anderes", "unklar")
#: So lange muss ununterbrochen etwas anderes laufen, bis ein gezeigter Stand
#: zurückgezogen wird. Kürzer nicht: Eine Einzelmeinung des Modells über
#: eine Rede, die weit ausholt, soll die Karte nicht flackern lassen.
OFF_AIR_SECONDS = 5 * 60
#: Nach einem Rückzug: so lange Ratssitzung am Stück, bis der letzte Stand
#: wieder erscheint (ohne neuen Aufruf — die Übertragung setzt mitten im
#: Punkt wieder ein).
RESUME_SECONDS = 90
#: Wie genau ein Zitat im Fenster stehen muss (Anteil des längsten
#: gemeinsamen Stücks an der Länge des Zitats, ohne Satzzeichen).
QUOTE_MIN_RATIO = 0.8

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
 "evidence": "<wörtliches Zitat ≤ 120 Zeichen, das TOP oder Sprecher belegt>",
 "broadcast": "rat|anderes|unklar"}

Regeln:
- ZUERST "broadcast": Läuft im Fenster überhaupt eine Ratssitzung?
  "rat": Sitzungsleitung ruft Punkte auf, erteilt das Wort, lässt abstimmen;
  Ratsmitglieder oder Verwaltung reden im Plenum zu Punkten der Tagesordnung.
  "anderes": Der Sender zeigt etwas anderes — Vortrag, Podium, Lesung,
  Interview, Kinder- oder Kulturprogramm, Musik, Nachrichten, Werbung, eine
  Störungsansage. Fällt die Übertragung aus, sendet der Sender eigenes
  Programm, auch über Oldenburger Stadtplanung und mit bekannten Namen. Ein
  Thema, das zur Tagesordnung passt, macht daraus KEINE Ratssitzung;
  Publikumsfragen bei einer Veranstaltung sind keine Einwohnerfragestunde.
  "unklar": zu wenig Text, Stille, Pause.
- Bei "anderes": "transitions" leer, "top" null, "speaker" null.
- "transitions" listet JEDEN Wechsel im Fenster in zeitlicher Reihenfolge: ein
  neuer TOP wird aufgerufen (kind top), eine Abstimmung findet statt (kind
  vote), jemand bekommt das Wort (kind speaker). Die Zeit ist die Marke des
  Absatzes, in dem es passiert. Mehrere TOPs in einer Minute (Formalien,
  Veränderungssperren) sind normal — jeden einzeln nennen.
- "top" ist der Stand am ENDE des Fensters.
- Die Sitzungsleitung ruft Punkte auf („Wir kommen zu Tagesordnungspunkt 9.3",
  „Punkt 10.2, Antrag der Fraktion …") und erteilt das Wort („Frau Müller für
  die Fraktion Bündnis 90/Die Grünen"). Nur daraus schließen; nicht raten.
  Das "evidence" eines top- oder vote-Wechsels ist der Aufruf selbst, wörtlich
  aus dem Transkript, mit der Nummer oder dem Titel des Punkts.
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
            "phase": "unklar", "speaker": None, "party": None, "evidence": "",
            "broadcast": "unklar"}


def _plain(text: str) -> str:
    """Kleinbuchstaben, nur Buchstaben und Ziffern — „Punkt 9.3," == „punkt 93"."""
    return re.sub(r"[^0-9a-zäöüß]", "", (text or "").lower())


def quoted(evidence: str | None, window_text: str) -> bool:
    """Steht das Zitat (fast) wörtlich im Fenster? Das Modell soll zitieren,
    nicht zusammenfassen — ein Beleg, der nicht dasteht, belegt nichts."""
    # Ohne die Zeitmarken aus format_window — ein Aufruf über zwei Segmente
    # („mit 7.1 [25:53] weiter") stünde sonst nicht mehr am Stück da.
    needle = _plain(evidence or "")
    hay = _plain(re.sub(r"\[\d+:\d{2}\]", " ", window_text or ""))
    if len(needle) < 4:
        return False
    if needle in hay:
        return True
    m = difflib.SequenceMatcher(None, hay, needle, autojunk=False).find_longest_match(
        0, len(hay), 0, len(needle))
    return m.size >= QUOTE_MIN_RATIO * len(needle)


#: Wörter aus TOP-Titeln, die keinen Punkt kennzeichnen.
_TITLE_STOP = {"beschluss", "antrag", "anfrage", "fraktion", "gruppe", "stadt",
               "oldenburg", "oldenburger", "vorlage", "bericht", "änderung",
               "satzung", "mitteilung", "mitteilungen", "information"}


#: So ruft die Sitzungsleitung auf: „Tagesordnungspunkt …", „wir kommen
#: zur …", „dann sind wir bei …", „weiter mit …", „ich rufe … auf".
_CALL_RE = re.compile(
    r"tagesordnungspunkt|\bpunkt|\btop\b|\bkommen\b|weiter mit|\brufe|aufruf"
    r"|sind wir (?:bei|beim|jetzt bei)|\bnächste[nr]?\b|\bdann (?:die|der|das|zu[mr]?)\b")


def names_item(evidence: str | None, number: str | None, title: str | None) -> bool:
    """Nennt ein Zitat den Punkt beim Namen — seine Nummer oder ein
    kennzeichnendes Wort seines Titels („Einwohnerfragestunde")?

    Die Erkennung schreibt 9.3 als „9.3", „9,3" oder „93"; verglichen wird
    deshalb ohne Trenner, aber an Zahlgrenzen („93" steckt nicht in „1993")."""
    ev = (evidence or "").lower()
    if not ev or not number:
        return False
    digits = re.sub(r"\D", "", number)
    if digits:
        for m in re.finditer(r"\d+(?:\s*[.,]\s*\d+)*", ev):
            if re.sub(r"\D", "", m.group(0)) == digits:
                return True
    # Ein Titelwort allein ist ein Thema, kein Aufruf („Kennedystraße" in
    # der Einwohnerfragestunde, „Bahnhof" mitten in einer Rede) — es zählt
    # nur zusammen mit den Worten, mit denen die Sitzungsleitung aufruft.
    if not _CALL_RE.search(ev):
        return False
    ev_words = set(re.findall(r"[a-zäöüß]{6,}", ev))
    for word in re.findall(r"[a-zäöüß]{6,}", (title or "").lower()):
        if word in _TITLE_STOP:
            continue
        # Erste sechs Buchstaben: „Eröffnung" ~ „eröffne", „Innenentwicklungs…"
        if any(w[:6] == word[:6] for w in ev_words):
            return True
    return False


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
        #: Wird der Stand gerade gezeigt? Erst ab dem ersten Aufruf (s. Modulkopf).
        self.on_air = False
        #: War überhaupt schon eine Ratssitzung zu sehen?
        self.seen_council = False
        self.off_air_seconds = 0.0
        self.council_seconds = 0.0
        #: Fenster, die das Modell als etwas anderes als eine Ratssitzung sah.
        self.off_air_windows = 0
        store.clear_live_state(ksinr)
        if not self.people:
            log.warning("Sitzung %s: kein Sprecher-Verzeichnis — Fraktionen bleiben leer", ksinr)

    # ------------------------------------------------------------- Haken

    def on_chunk(self, idx: int, segments: list[tuple[float, str]], closing: bool) -> None:
        """Haken für den Stück-Weg: Stück ``idx`` deckt feste Sekunden ab."""
        self.on_window(idx * self.chunk_seconds, (idx + 1) * self.chunk_seconds, segments, closing)

    def on_window(self, t_from: float, t_to: float, segments: list[tuple[float, str]],
                  closing: bool) -> None:
        """Haken für den Streaming-Weg (``stream_stt.Windower``): ein Fenster
        beliebiger Länge — auch ein kurzes, wenn gerade ein Punkt aufgerufen
        oder das Wort erteilt wurde."""
        self.segments.extend(segments)
        window = [s for s in self.segments if t_from - OVERLAP_SECONDS <= s[0] < t_to]
        if not window:
            if closing:
                self.finish(int(t_to))
            return
        text = format_window(window)
        res = track_window(self._agenda_text, self._roster_text, self.state,
                           text, int(t_from), int(t_to), self.model)
        self.apply(res, int(t_from), int(t_to), closing, window_text=text)

    def apply(self, res: dict, t_from: int, t_to: int, closing: bool = False,
              window_text: str = "") -> dict | None:
        """Modellantwort in Stand + Ereignisse übersetzen und speichern.

        Gibt die geschriebene Zeile zurück — oder None, wenn gerade nichts
        gezeigt wird (noch kein Aufruf gesehen, oder der Sender zeigt etwas
        anderes)."""
        said = res.get("broadcast")
        broadcast = said if isinstance(said, str) and said in BROADCASTS else "unklar"
        self._count_air(broadcast, t_to - t_from)
        if broadcast == "anderes":
            self.off_air_windows += 1
            events: list[dict] = []
        else:
            events = self._events(res, t_from, window_text)

        # Ein neuer TOP nur mit Aufruf: ein belegtes Ereignis, oder das
        # Zitat der Antwort nennt den Punkt selbst.
        candidate = norm_top(res.get("top"))
        top = self.state.get("top")
        called = {e["item_number"] for e in events if e["kind"] in ("top", "vote")}
        if broadcast != "anderes" and candidate and candidate != top and candidate in self.titles:
            if candidate in called or self._is_call(res.get("evidence"), candidate, window_text):
                top = candidate
        elif candidate is None and called:
            top = [e["item_number"] for e in events if e["item_number"] in called][-1]

        # Welche TOPs sind im Fenster durchgelaufen? Mehr als einer → Block.
        tops_seen: list[str] = []
        for e in events:
            n = e.get("item_number")
            if n and n not in tops_seen:
                tops_seen.append(n)
        block_start = tops_seen[0] if len(tops_seen) >= 2 and tops_seen[-1] == top else None

        top_changed = top != self.state.get("top")
        if top_changed:
            first = next((e for e in events if e.get("item_number") == top), None)
            at = first["at_seconds"] if first else t_from
            self.since = self.started_at + timedelta(seconds=at)

        phase = res.get("phase") if res.get("phase") in PHASES else "unklar"
        person = match_speaker(res.get("speaker"), self.people) if broadcast != "anderes" else None
        if person:
            speaker, party = person["name"], party_of(person)
        elif (phase == "aussprache" and top == self.state.get("top")
              and self.state.get("speaker") and broadcast != "anderes"):
            # Kein neuer Name im Fenster, aber die Aussprache zum selben
            # Punkt läuft weiter: Dann redet noch, wer zuletzt das Wort
            # bekam. Bei 15-s-Fenstern fehlt die Ankündigung sonst in jedem
            # zweiten Fenster (gemessen 06.09.: 57 % → 91 % mit Sprecher).
            speaker, party = self.state["speaker"], self.state.get("party")
        else:
            speaker = None
            party = (res.get("party") if res.get("party") == "Verwaltung"
                     and broadcast != "anderes" else None)
        self.state = {"top": top, "speaker": speaker, "party": party}

        self._update_air(top_changed and top is not None)
        if not self.on_air:
            if closing:
                self.finish(t_to)
            return None

        finished = bool(closing)
        if finished:
            phase = "ende"
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

    # ------------------------------------------------------ Sendet der Rat?

    def _is_call(self, evidence: str | None, number: str, window_text: str) -> bool:
        return (quoted(evidence, window_text)
                and names_item(evidence, number, self.titles.get(number)))

    def _count_air(self, broadcast: str, seconds: float) -> None:
        seconds = max(float(seconds), 0.0)
        if broadcast == "anderes":
            self.off_air_seconds += seconds
            self.council_seconds = 0.0
        elif broadcast == "rat":
            self.council_seconds += seconds
            self.off_air_seconds = 0.0

    def _update_air(self, called: bool) -> None:
        """Zeigen, zurückziehen, wieder zeigen — s. Modulkopf."""
        if self.on_air:
            if self.off_air_seconds >= OFF_AIR_SECONDS:
                self.on_air = False
                self.state = {**self.state, "speaker": None, "party": None}
                self.store.withdraw_live_state(self.ksinr)
                log.warning("Sitzung %s: seit %d min keine Ratssitzung im Stream — "
                            "Live-Stand zurückgezogen", self.ksinr, self.off_air_seconds // 60)
            return
        if called and self.off_air_seconds == 0:
            self.on_air = self.seen_council = True
        elif (self.seen_council and self.state.get("top")
              and self.council_seconds >= RESUME_SECONDS):
            self.on_air = True
            log.info("Sitzung %s: Ratssitzung wieder im Stream — Live-Stand zurück", self.ksinr)

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

    def _events(self, res: dict, t_from: int, window_text: str = "") -> list[dict]:
        """Die Wechsel der Antwort — nur belegte: Ein TOP- oder
        Abstimmungswechsel braucht den Aufruf im Fenster, ein
        Sprecherwechsel einen Namen aus dem Verzeichnis."""
        out: list[dict] = []
        for tr in res.get("transitions") or []:
            if not isinstance(tr, dict):
                continue
            kind = tr.get("kind") if tr.get("kind") in ("top", "vote", "speaker") else "top"
            at = _seconds(tr.get("at"))
            person = match_speaker(tr.get("speaker"), self.people)
            number = norm_top(tr.get("top"))
            if kind == "speaker":
                if not person:
                    continue
            elif (number is None or number not in self.titles
                  or not self._is_call(tr.get("evidence"), number, window_text)):
                continue
            out.append({
                "at_seconds": at if at is not None else t_from,
                "kind": kind,
                "item_number": number,
                "speaker": person["name"] if person else None,
                "party": party_of(person) if person else None,
                "evidence": (tr.get("evidence") or "")[:120] or None,
            })
        out.sort(key=lambda e: e["at_seconds"])
        return out
