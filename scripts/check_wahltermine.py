#!/usr/bin/env python3
"""Merkt, wenn beim Votemanager eine Wahl auftaucht, die wir nicht kennen.

Zwei Lücken, die am 14.09.2026 beide von Hand gestopft wurden — und genau das
ist der Grund für diesen Lauf:

1. **Die Stichwahl.** Am 13.09. hat niemand die absolute Mehrheit erreicht; am
   27.09. läuft die Stichwahl. Ihre Wahl-Id vergibt die Stadt erst kurz vorher,
   und ohne sie zeigt die Seite einen Countdown statt Zahlen.
   ``mayor.resolve_ids`` sucht sie am Titel — aber ob die Suche greift, sieht
   man erst am Wahlabend. Dieser Lauf sieht früher hin.
2. **Die nächste Wahl überhaupt.** Ob eine Landtags-, Bundestags- oder
   Kommunalwahl im Kalender der Stadt steht, erfährt man sonst aus der
   Zeitung. Der Votemanager führt alle Termine unter
   ``<ags>/api/termine.json`` — die Liste, aus der auch die Erhebung vom
   14.09. stammt (2006 und 2021 stand die Stichwahl dort unter der URL der
   Hauptwahl, nicht unter einer eigenen).

**Was er NICHT tut: irgendetwas anlegen.** Eine Wahl ist eine Datei in
``kommunalwahl/wahlen/`` mit Register, Referenzordner und Sitzzahl — das ist
Handarbeit mit Blick in die amtliche Bekanntmachung, kein Automatismus. Dieser
Lauf schreibt eine Mail und hört auf. Was er findet, ist ein Hinweis, kein
Auftrag.

**Und er meldet nichts doppelt.** Gemeldete Termine stehen in
``data/wahltermine-gesehen.json``; ein Termin, über den schon einmal eine Mail
ging, taucht nicht jede Nacht wieder auf. Die Datei ist Bequemlichkeit, keine
Zusage: Ist sie weg, gibt es die Meldung noch einmal — lästig, nicht schlimm.

Cron (als Nutzer tim auf dem App-Server):
  15 6 * * * /home/<user>/app/.venv/bin/python /home/<user>/app/scripts/check_wahltermine.py
"""
from __future__ import annotations

import json
import logging
import os
import sys
from datetime import date, datetime
from pathlib import Path

import requests

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL))
sys.path.insert(0, str(WURZEL / "web" / "backend"))

from app.election import elections  # noqa: E402

_log = logging.getLogger("ratslotse.wahltermine")

#: Der Terminkalender der Stadt. Die AGS steht in der Basis-URL jeder Wahl
#: (``…/20260913/03403000``) — abgeleitet statt zweitgeschrieben, damit eine
#: zweite Stadt nichts Neues braucht.
TERMINE_PFAD = "/api/termine.json"
TIMEOUT = (5, 15)
UA = "Ratslotse-Wahlabend/1.0 (+https://ratslotse.de/wahlabend)"
GESEHEN = WURZEL / "data" / "wahltermine-gesehen.json"

#: So weit zurück interessiert uns ein Termin. Der Kalender reicht bis 2006;
#: „neu" ist nur, was noch kommt oder gerade war.
RUECKBLICK_TAGE = 30


def termine_url() -> str:
    """``https://votemanager.kdo.de/03403000/api/termine.json`` — aus der
    Basis-URL der aktiven Wahl abgeleitet."""
    if url := os.environ.get("WAHLTERMINE_URL"):
        return url
    basis = elections.active().source.base.rstrip("/")
    # …/<wahltag>/<ags>  ->  …/<ags>
    teile = basis.rsplit("/", 2)
    return f"{teile[0]}/{teile[-1]}{TERMINE_PFAD}" if len(teile) == 3 else basis + TERMINE_PFAD


def _datum(text: str) -> date | None:
    """„13.09.2026" → ``date``; alles andere ``None``."""
    try:
        return datetime.strptime(text.strip(), "%d.%m.%Y").date()
    except (ValueError, AttributeError):
        return None


def hole(url: str) -> list[dict]:
    with requests.Session() as s:
        s.headers.update({"User-Agent": UA})
        antwort = s.get(url, timeout=TIMEOUT)
        antwort.raise_for_status()
        nutzlast = antwort.json()
    termine = nutzlast.get("termine") if isinstance(nutzlast, dict) else None
    return [t for t in termine or [] if isinstance(t, dict)]


def unbekannt(termine: list[dict], heute: date | None = None) -> list[dict]:
    """Termine, zu denen wir keine Wahl in der Registry haben.

    Verglichen wird über das **Datum**, nicht über den Titel: „Kommunalwahlen"
    im Kalender der Stadt sind bei uns zwei Einträge (Ratswahl und OB-Wahl),
    und „Stichwahl des/der Oberbürgermeisters/in" heißt bei uns
    „OB-Stichwahl Oldenburg". Das Datum ist die eine Angabe, die beide Seiten
    gleich schreiben.
    """
    heute = heute or date.today()
    bekannt = {w.date for w in elections.all().values()}
    offen = []
    for t in termine:
        d = _datum(t.get("date", ""))
        if d is None or (heute - d).days > RUECKBLICK_TAGE:
            continue
        if d.isoformat() not in bekannt:
            offen.append({"date": d.isoformat(), "name": (t.get("name") or "").strip(),
                          "url": (t.get("url") or "").strip()})
    return offen


def fehlende_ids(heute: date | None = None) -> list[dict]:
    """Wahlen, deren Id wir suchen — und ob sie inzwischen da ist.

    Das ist der Stichwahl-Fall: Der Eintrag in ``kommunalwahl/wahlen/`` trägt
    ``discover`` statt einer Id, weil es sie beim Anlegen noch nicht gab.
    Sobald die Stadt sie vergibt, soll das jemand erfahren — und wenn der
    Wahltag näher rückt und sie immer noch fehlt, erst recht.
    """
    from app.election import mayor

    heute = heute or date.today()
    treffer = []
    for wahl in elections.all().values():
        quelle = wahl.source
        if quelle.presentation_id is not None or not quelle.discover:
            continue
        tage = (date.fromisoformat(wahl.date) - heute).days
        if tage < -RUECKBLICK_TAGE:
            continue
        gefunden = None
        try:
            with requests.Session() as s:
                s.headers.update({"User-Agent": UA})
                antwort = s.get(mayor.base_url(wahl) + mayor.TERMIN_PATH, timeout=TIMEOUT)
                antwort.raise_for_status()
                gefunden = mayor._eintrag(antwort.json(), quelle)
        except (requests.RequestException, ValueError) as exc:
            _log.info("Wahltermine: termin.json für %s nicht lesbar (%s)", wahl.slug, exc)
        treffer.append({"slug": wahl.slug, "short_title": wahl.short_title, "date": wahl.date,
                        "tage": tage, "wahl_id": gefunden[0] if gefunden else None})
    return treffer


def _gesehen() -> set[str]:
    try:
        return set(json.loads(GESEHEN.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return set()


def _merken(schluessel: set[str]) -> None:
    try:
        GESEHEN.parent.mkdir(parents=True, exist_ok=True)
        GESEHEN.write_text(json.dumps(sorted(schluessel), ensure_ascii=False), encoding="utf-8")
    except OSError as exc:  # eine Merkdatei darf den Lauf nicht umbringen
        _log.warning("Wahltermine: %s nicht schreibbar (%s) — die nächste Meldung kommt doppelt.",
                     GESEHEN, exc)


def main() -> dict:
    from kern.alerts import notify_admin

    url = termine_url()
    try:
        termine = hole(url)
    except (requests.RequestException, ValueError) as exc:
        # Kein Alarm: Der Kalender der Stadt ist kein Dienst, den wir betreiben.
        # Bleibt er länger weg, meldet sich der Herzschlag über die Job-Ampel.
        _log.warning("Wahltermine: %s nicht erreichbar (%s)", url, exc)
        return {"termine": 0, "unbekannt": 0, "gemeldet": 0, "fehler": type(exc).__name__}

    neu = unbekannt(termine)
    ids = fehlende_ids()
    vorher = _gesehen()
    meldungen: list[str] = []
    jetzt_gesehen = set(vorher)

    frisch = [t for t in neu if f"termin:{t['date']}" not in vorher]
    if frisch:
        zeilen = [f"• <b>{t['name'] or 'ohne Titel'}</b> am {t['date']}" for t in frisch]
        meldungen.append(
            "Im Kalender der Stadt stehen Wahlen, die wir nicht kennen:\n" + "\n".join(zeilen)
            + "\n\nWenn eine davon auf Ratslotse laufen soll, braucht sie einen Eintrag in "
              "<code>kommunalwahl/wahlen/</code> (Register, Referenzordner, Sitzzahl) — "
              "siehe docs/plan-wahlen-generalisieren.md.")
        jetzt_gesehen |= {f"termin:{t['date']}" for t in frisch}

    for i in ids:
        schluessel = f"id:{i['slug']}:{i['wahl_id']}"
        if i["wahl_id"] is not None and schluessel not in vorher:
            meldungen.append(
                f"<b>{i['short_title']}</b> ({i['date']}) hat jetzt eine Wahl-Id beim "
                f"Votemanager: <code>{i['wahl_id']}</code>. Die Seite findet sie von selbst — "
                "diese Meldung ist die Bestätigung, dass die Suche am Titel greift.")
            jetzt_gesehen.add(schluessel)
        elif i["wahl_id"] is None and 0 <= i["tage"] <= 2:
            # Kurz vor dem Wahltag ohne Id: DAS ist der Fall, der wehtut.
            meldungen.append(
                f"<b>{i['short_title']}</b> ist in {i['tage']} Tag(en) — und beim Votemanager "
                "steht noch keine Wahl-Id dafür. Bleibt das so, zeigt die Seite am Wahlabend "
                f"einen Countdown statt Zahlen. Notfalls <code>presentation_id</code> in "
                f"<code>kommunalwahl/wahlen/{i['slug']}.json</code> nachtragen.")

    if meldungen:
        notify_admin("\n\n".join(meldungen), betreff="Ratslotse – Wahltermine",
                     fusszeile=f"Kalender der Stadt: {url}")
    _merken(jetzt_gesehen)

    return {
        "termine": len(termine),
        "unbekannt": len(neu),
        "wahlen_ohne_id": sum(1 for i in ids if i["wahl_id"] is None),
        "gemeldet": len(meldungen),
    }


if __name__ == "__main__":
    from kern.alerts import run_guarded

    run_guarded("check_wahltermine", main)
