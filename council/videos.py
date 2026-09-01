"""Vorläufige Abstimmungsergebnisse aus der O1-Videoaufzeichnung lesen.

oldenburg eins überträgt jede Ratssitzung und lädt die Aufzeichnung tags
darauf auf YouTube (Titel ``Ratssitzung Oldenburg | TT.MM.JJJJ``). Die
deutschen Auto-Untertitel reichen, um die Abstimmungsergebnisse zu lesen —
das amtliche Protokoll braucht 1–2 Monate. Dieses Modul schließt die Lücke
mit ausdrücklich vorläufigen Ergebnissen (Tabelle ``council_video_results``).

Gemessen am 31.08.2026 gegen 120 protokollierte Hauptabstimmungen aus sechs
Sitzungen: 111 als gesichert ausgegeben, davon 111 richtig — null falsche
Ergebnisse. Der Preis der Fehlerfreiheit sind drei Sicherungen:

1. Der Prompt darf schweigen („lieber auslassen als raten") und muss jedes
   Ergebnis mit einem wörtlichen Zitat belegen.
2. Jeder Beleg wird mechanisch im Transkript wiedergefunden — was nicht
   dasteht, ist erfunden und fliegt raus (fing 7 umformulierte Zitate).
3. Zwei Durchläufe mit um einen halben Abschnitt versetzten Schnittkanten;
   nur wo beide dasselbe Ergebnis nennen, gilt es als gesichert.

Beim Zusatz einstimmig/mehrheitlich gilt: nur behaupten, was der Wortlaut
trägt. Gegenstimmen werden per Handzeichen gezählt und fast nie ausgesprochen
— „keine Gegenstimme gehört" heißt also nicht null. Dieselbe Formulierung
(„eine Enthaltung, mehrheitlich angenommen") stand im Prüfbestand einmal für
Protokoll-„einstimmig" und einmal für 18 ungezählte Gegenstimmen. Deshalb
bleibt ``vote`` offen (NULL), wo weder eine gezählte Gegenstimme noch das
Wort „einstimmig" im Beleg steht.

Hinweis Betrieb: Der Untertitel-Abgriff verstößt gegen die YouTube-ToS
(Vertragsrisiko: Rate-Limit/IP-Sperre, kein Rechtsverstoß — die Ergebnisse
selbst sind Fakten). Tims Entscheidung 31.08.2026: erstmal so, später ggf.
bei O1 direkt um die Aufzeichnung bzw. einen Feed bitten — das nähme YouTube
ganz aus der Kette und hülfe auch bei Videos ohne Untertitel (1 von 7 im
Prüfbestand hatte keine).
"""
from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from pathlib import Path

from kern import llm

log = logging.getLogger(__name__)

CHANNEL_URL = "https://www.youtube.com/channel/UCnBlQZSUnJh3JJtyWd81l0Q/videos"
MODEL = os.environ.get("COUNCIL_VIDEO_MODEL", "openai/gpt-5.6-luna")
CHUNK_CHARS = 40_000
OVERLAP_CHARS = 4_000
#: Titel-Datum minus Sitzungsdatum: 0 (29.06.) bis +1 Tag (Video „24.02."
#: war die Sitzung vom 23.02.) — mit Luft nach oben.
TITLE_DATE_TOLERANCE_DAYS = 2

_TITLE_RE = re.compile(r"Ratssitzung Oldenburg\s*\|\s*(\d{2})\.(\d{2})\.(\d{4})")

SYSTEM_PROMPT = """Du liest das automatisch erzeugte Transkript einer Ratssitzung der
Stadt Oldenburg und ziehst daraus die Abstimmungsergebnisse.

TEXTQUALITAET: Das Transkript stammt aus einer Spracherkennung. Sie
verschluckt den Punkt in Tagesordnungspunkt-Nummern ("141" meint 14.1,
"147 8 und 9" meint 14.7, 14.8 und 14.9) und verschreibt Eigennamen.
Ordne Nummern IMMER gegen die mitgelieferte Tagesordnung zu und nutze den
mitgesprochenen Titel als Kontrolle.

ABLAUF: Die Sitzungsleitung ruft den Punkt auf ("Dann machen wir mit 7.1
weiter, Umgestaltung des Bahnhofsvorplatzes"), danach die Aussprache, dann
"Wenn Sie dem Beschlussvorschlag folgen, bitte ich um das Handzeichen.
Gegenstimmen. Enthaltung." und zuletzt das Ergebnis.

FALLE 1 - mehrere Abstimmungen je Punkt: Oft wird zuerst ueber
Geschaeftsordnungsantraege (Vertagung) und Aenderungsantraege der Fraktionen
abgestimmt, erst danach ueber die Sache selbst. Die Sachabstimmung ist
art="haupt", alle vorherigen sind art="vorab". Im Zweifel ist die LETZTE
Abstimmung zu einem Punkt die Hauptabstimmung.

FALLE 2 - Frage statt Ergebnis: "Gibt es Gegenstimmen? Enthaltung?" ohne
Zahl ist die FRAGE der Leitung. Uebernimm Zahlen nur, wenn sie wirklich
genannt werden ("bei vier Enthaltungen", "20 dagegen").

LIEBER SCHWEIGEN ALS RATEN. Nimm einen Punkt nur auf, wenn in DIESEM
Abschnitt eine Abstimmung wirklich stattfindet und du das Ergebnis hoerst.
Ein aufgerufener, aber nicht abgestimmter Punkt kommt nicht vor.

Das Feld "beleg" muss ein WOERTLICHES, ununterbrochenes Zitat aus dem
Transkript sein (mindestens 40 Zeichen), das die Ergebnisworte enthaelt.
Formuliere nichts um.

Antworte AUSSCHLIESSLICH mit einem JSON-Objekt:
{"ergebnisse": [{"nr": "7.1", "art": "haupt", "outcome": "angenommen",
  "vote": "einstimmig", "gegenstimmen": null, "enthaltungen": 1,
  "beleg": "woertliches Zitat"}]}

outcome: angenommen, abgelehnt, vertagt, zur_kenntnis oder abgesetzt.
vote: "einstimmig", "mehrheitlich" oder null.
gegenstimmen/enthaltungen: Zahl oder null (null = nicht ausgesprochen)."""


# ---------------------------------------------------------------- yt-dlp

def _yt_dlp_bin() -> str | None:
    """Bewusst NICHT in requirements.txt (wie fastembed): Web-Service und
    Deploy bleiben unberührt, nur der Cron braucht das Werkzeug. Auf dem
    Server: ``.venv/bin/pip install yt-dlp``."""
    root = Path(__file__).resolve().parent.parent
    cand = root / ".venv" / "bin" / "yt-dlp"
    if cand.exists():
        return str(cand)
    return shutil.which("yt-dlp")


def _run_yt_dlp(args: list[str], timeout: int = 300) -> str | None:
    exe = _yt_dlp_bin()
    if not exe:
        log.warning("yt-dlp nicht installiert — Video-Ergebnisse übersprungen "
                    "(.venv/bin/pip install yt-dlp)")
        return None
    try:
        p = subprocess.run([exe, *args], capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        log.warning("yt-dlp Timeout nach %ss: %s", timeout, args[:3])
        return None
    if p.returncode != 0:
        log.warning("yt-dlp fehlgeschlagen (%s): %s", p.returncode, p.stderr[-400:])
        return None
    return p.stdout


def find_video(session_date: str) -> dict | None:
    """Das O1-Video zu einer Ratssitzung — oder None, wenn (noch) keins da ist.

    Das Titel-Datum kann dem Sitzungsdatum um einen Tag nachlaufen, deshalb
    ein kleines Fenster statt Gleichheit."""
    out = _run_yt_dlp(["--flat-playlist", "--print", "%(id)s\t%(title)s",
                       "--playlist-end", "60", CHANNEL_URL])
    if not out:
        return None
    want = date.fromisoformat(session_date[:10])
    for line in out.splitlines():
        vid, _, title = line.partition("\t")
        m = _TITLE_RE.search(title)
        if not m:
            continue
        d, mo, y = (int(x) for x in m.groups())
        try:
            title_date = date(y, mo, d)
        except ValueError:
            continue
        if timedelta(0) <= title_date - want <= timedelta(days=TITLE_DATE_TOLERANCE_DAYS):
            return {"video_id": vid.strip(), "title": title.strip()}
    return None


def fetch_transcript(video_id: str, workdir: Path) -> list[tuple[float, str]] | None:
    """Deutsche Auto-Untertitel als [(Sekunden, Text)] — None, wenn YouTube
    (noch) keine erzeugt hat. Frisch hochgeladene Videos brauchen Stunden;
    der nächste Cron-Lauf holt sie dann."""
    workdir.mkdir(parents=True, exist_ok=True)
    target = workdir / f"{video_id}.de-orig.json3"
    if not target.exists():
        ok = _run_yt_dlp(["--skip-download", "--write-auto-subs",
                          "--sub-langs", "de-orig", "--sub-format", "json3",
                          "-o", str(workdir / video_id),
                          f"https://www.youtube.com/watch?v={video_id}"])
        if ok is None or not target.exists():
            return None
    data = json.loads(target.read_text())
    segments: list[tuple[float, str]] = []
    for e in data.get("events", []):
        if not e.get("segs"):
            continue
        text = "".join(s.get("utf8", "") for s in e["segs"]).replace("\n", " ").strip()
        if text:
            segments.append((e["tStartMs"] / 1000, text))
    return segments or None


# ------------------------------------------------------- Text-Werkzeuge

def strip_prefix(item_number: str) -> str:
    """'Ö 10.3' → '10.3'. council_agenda_items führt das Ö/N-Präfix,
    council_decisions nicht — und 'Ö' ist kein ASCII-O, eine Zeichenklasse
    ließe es durch. Alles vor der ersten Ziffer fällt weg."""
    return re.sub(r"^[^\d]+", "", str(item_number or "").strip())


def _fold(s: str) -> str:
    """Für den Beleg-Abgleich: Umlaute, Groß-/Kleinschreibung und alles
    außer Buchstaben/Ziffern raus — die Spracherkennung setzt Satzzeichen
    frei, das Modell zitiert sie mal mit, mal ohne."""
    s = (s or "").lower()
    s = (s.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")
           .replace("ß", "ss"))
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "", s)


def _flatten(segments: list[tuple[float, str]]) -> tuple[str, list[tuple[int, float]]]:
    """Fließtext plus Zeitanker — die Anker zählen in GEFALTETEN Positionen
    (``_fold``), weil auch die Beleg-Suche dort läuft. So braucht der
    Timestamp keine Rückrechnung ins Original: ``_fold`` der Konkatenation
    ist die Konkatenation der ``_fold``-Stücke (Leerzeichen fallen weg)."""
    anchors: list[tuple[int, float]] = []
    parts: list[str] = []
    fpos = 0
    for seconds, text in segments:
        anchors.append((fpos, seconds))
        parts.append(text)
        fpos += len(_fold(text))
    return " ".join(parts), anchors


def _seconds_at(anchors: list[tuple[int, float]], pos: int) -> float:
    lo, hi, best = 0, len(anchors) - 1, 0.0
    while lo <= hi:
        mid = (lo + hi) // 2
        if anchors[mid][0] <= pos:
            best = anchors[mid][1]
            lo = mid + 1
        else:
            hi = mid - 1
    return best


def _quote_positions(folded: str, quote: str) -> list[int]:
    """Alle Fundstellen des Belegs im gefalteten Transkript.

    Erst das VOLLE Zitat: Die Abstimmungs-Formeln beginnen wortgleich
    („Gibt es Gegenstimmen? Enthaltung einstimmig angenommen…"), der
    60-Zeichen-Kopf allein hatte im Prüfbestand bis zu vier Fundstellen —
    das komplette Zitat trägt den Übergang zum nächsten TOP mit und ist
    (fast) immer eindeutig. Der Kopf bleibt Rückfall für Zitate, die
    hinten von der ASR-Schreibung abweichen."""
    def _all(key: str) -> list[int]:
        out, i = [], folded.find(key)
        while i >= 0:
            out.append(i)
            i = folded.find(key, i + 1)
        return out

    full = _fold(quote)
    if len(full) < 30:
        return []
    return _all(full) or _all(full[:60])


def _anchor_position(folded: str, item_number: str,
                     quote_a: str, quote_b: str) -> int:
    """Die Fundstelle des Ergebnisses im Transkript — vorsichtig gewählt.

    Die Abstimmungs-Formeln der Sitzungsleitung sind oft WORTGLEICH („Wenn
    Sie dem Beschlussvorschlag folgen …einstimmig angenommen"), ein Beleg
    kann also mehrfach im Transkript stehen; die erste Fundstelle blind zu
    nehmen setzte den Timestamp von TOP 14.4 auf Minute 25 statt 1:50
    (gemessen 31.08.). Zwei Anker dagegen:

    1. Die Belege BEIDER Pässe zeigen auf dieselbe Stelle, sind aber oft
       verschieden formuliert (andere Chunk-Grenzen) — das Positionspaar
       mit dem kleinsten Abstand ist die echte Stelle.
    2. Bleibt es mehrdeutig (beide Pässe zitieren wortgleich), gewinnt die
       Fundstelle, in deren Umgebung die TOP-Nummer fällt.
    """
    pos_a = _quote_positions(folded, quote_a)
    pos_b = _quote_positions(folded, quote_b)
    if not pos_a and not pos_b:
        return -1
    if pos_a and pos_b:
        best_gap, candidates = None, []
        for x in pos_a:
            for y in pos_b:
                gap = abs(x - y)
                if best_gap is None or gap < best_gap:
                    best_gap, candidates = gap, [x]
                elif gap == best_gap and x not in candidates:
                    candidates.append(x)
    else:
        candidates = pos_a or pos_b
    if len(candidates) > 1:
        needle = _fold(item_number)
        with_nr = [c for c in candidates
                   if needle and needle in folded[max(0, c - 800):c + 800]]
        if with_nr:
            candidates = with_nr
    return candidates[0]


def resolve_vote(result: dict) -> str | None:
    """Nur behaupten, was der Wortlaut trägt (s. Modul-Docstring):
    gezählte Gegenstimme → mehrheitlich; das Wort „einstimmig" im Beleg →
    einstimmig; alles andere — insbesondere ein bloßes „mehrheitlich" der
    Leitung — bleibt offen."""
    if result.get("gegenstimmen"):
        return "mehrheitlich"
    if re.search(r"einstimmig|einm[uü]tig", (result.get("beleg") or ""), re.I):
        return "einstimmig"
    return None


# ------------------------------------------------------------ LLM-Lesen

def _chunks(text: str, start: int) -> list[str]:
    out, i = [], start
    if start:
        out.append(text[:start])
    while i < len(text):
        out.append(text[i:i + CHUNK_CHARS])
        if i + CHUNK_CHARS >= len(text):
            break
        i += CHUNK_CHARS - OVERLAP_CHARS
    return out


def _ask(agenda_text: str, chunk: str, tag: str, attempt: int = 0) -> list[dict]:
    content = (f"TAGESORDNUNG DIESER SITZUNG (Nummer<TAB>Titel):\n{agenda_text}\n\n"
               f"TRANSKRIPT-ABSCHNITT:\n{chunk}")
    resp = llm.chat_complete(
        model=MODEL, _feature="video_ergebnisse",
        messages=[{"role": "system", "content": SYSTEM_PROMPT},
                  {"role": "user", "content": content}],
        temperature=0, response_format={"type": "json_object"}, max_tokens=32_000,
    )
    # gpt-5.6-luna liefert vereinzelt eine Antwort ganz OHNE choices (kein
    # Fehler, kein Inhalt) — chat_complete wirft dabei nicht, also selbst
    # noch einmal versuchen, sonst fällt der Abschnitt still aus.
    if not getattr(resp, "choices", None):
        if attempt < 2:
            return _ask(agenda_text, chunk, tag, attempt + 1)
        log.warning("Video-Lesen %s: dreimal leere Antwort", tag)
        return []
    raw = (resp.choices[0].message.content or "").strip()
    raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.M).strip()
    try:
        return json.loads(raw).get("ergebnisse", [])
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", raw, re.S)
        if m:
            try:
                return json.loads(m.group(0)).get("ergebnisse", [])
            except json.JSONDecodeError:
                pass
        log.warning("Video-Lesen %s: JSON unlesbar (%d Zeichen)", tag, len(raw))
        return []


def _one_pass(agenda_text: str, text: str, start: int, tag: str) -> list[dict]:
    chunks = _chunks(text, start)
    found: list[dict] = []
    with ThreadPoolExecutor(max_workers=3) as ex:
        futures = {ex.submit(_ask, agenda_text, c, f"{tag}/{i}"): i
                   for i, c in enumerate(chunks)}
        for f in as_completed(futures):
            i = futures[f]
            try:
                for r in f.result():
                    r["_chunk"] = i
                    found.append(r)
            except Exception:  # noqa: BLE001 — ein Abschnitt darf ausfallen
                log.exception("Video-Lesen %s/%s fehlgeschlagen", tag, i)
    return found


def _consolidate(found: list[dict], folded_text: str,
                 valid_numbers: set[str]) -> dict[str, dict]:
    """Beleg-Prüfung + je TOP die Hauptabstimmung behalten."""
    by_item: dict[str, dict] = {}
    for r in sorted(found, key=lambda x: x.get("_chunk", 0)):
        nr = strip_prefix(str(r.get("nr", "")))
        quote = _fold(r.get("beleg") or "")
        # Sicherung 2: das Zitat muss wörtlich im Transkript stehen.
        if not nr or nr not in valid_numbers or len(quote) < 30 \
                or quote[:60] not in folded_text:
            continue
        prev = by_item.get(nr)
        if prev and prev.get("art") == "haupt" and r.get("art") != "haupt":
            continue
        by_item[nr] = r
    return by_item


def extract_results(segments: list[tuple[float, str]],
                    agenda_items: list[dict]) -> list[dict]:
    """Der volle strenge Durchlauf → Zeilen für ``save_video_results``.

    ``agenda_items`` sind die Zeilen aus ``store.agenda_items(ksinr)``;
    zurück kommen nur konsens-gesicherte Ergebnisse mit wiedergefundenem
    Beleg, samt Video-Timestamp der Fundstelle."""
    text, anchors = _flatten(segments)
    folded = _fold(text)
    valid = {strip_prefix(it["item_number"]) for it in agenda_items}
    valid.discard("")
    agenda_text = "\n".join(
        f'{strip_prefix(it["item_number"])}\t'
        # Der angehängte „Beschluss: …"-Vermerk steht nicht im gesprochenen Wort.
        f'{re.split(r"\s+Beschluss:", it["title"])[0][:130]}'
        for it in agenda_items if strip_prefix(it["item_number"]))

    # Sicherung 3: zwei Durchläufe, Schnittkanten um einen halben Abschnitt
    # versetzt — ein Votum, das im ersten auf der Kante stirbt, liegt im
    # zweiten mitten im Abschnitt.
    pass_a = _consolidate(_one_pass(agenda_text, text, 0, "A"), folded, valid)
    pass_b = _consolidate(_one_pass(agenda_text, text, CHUNK_CHARS // 2, "B"),
                          folded, valid)

    results: list[dict] = []
    for nr in sorted(set(pass_a) & set(pass_b)):
        a, b = pass_a[nr], pass_b[nr]
        if a.get("outcome") != b.get("outcome"):
            continue  # uneinig → „Protokoll abwarten"
        # Der ausführlichere Befund gewinnt (Zahlen sind selten — wer eine
        # hat, hat genauer hingehört).
        r = a if (a.get("gegenstimmen") is not None
                  or a.get("enthaltungen") is not None) else b
        outcome = r.get("outcome")
        if outcome not in ("angenommen", "abgelehnt", "vertagt",
                           "zur_kenntnis", "abgesetzt"):
            continue
        quote = (r.get("beleg") or "").strip()
        pos = _anchor_position(folded, nr, a.get("beleg") or "", b.get("beleg") or "")
        seconds = _seconds_at(anchors, pos) if pos >= 0 else None
        results.append({
            "item_number": nr,
            "outcome": outcome,
            "vote": resolve_vote(r),
            "gegenstimmen": r.get("gegenstimmen"),
            "enthaltungen": r.get("enthaltungen"),
            "quote": quote,
            "video_seconds": int(seconds) if seconds is not None else None,
        })
    return results
