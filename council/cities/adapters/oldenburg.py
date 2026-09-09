"""Oldenburg als Stadt Nummer null — aus ``council.sqlite``, ohne Netz.

**Warum Oldenburg im selben Speicher liegt.** Nur so sind „was fehlt uns?"
und „was haben wir, was andere nicht haben?" dieselbe Rechnung mit
vertauschten Rollen, und nur so kann ein Nachbar eines Oldenburger
Beschlusses ein Osnabrücker Antrag sein und umgekehrt.

**Warum der Adapter über die Rohablage geht**, obwohl die Daten schon in
einer Datenbank liegen: Damit die Regel „Schicht 1 entsteht ausschließlich
aus Schicht 0" ohne Ausnahme gilt. Die Rohobjekte sind hier synthetisch (aus
Tabellenzeilen gebaut statt von einem Server geholt), aber sie sind da, und
``normalize`` läuft darüber wie über eine echte Ernte.

**Was NICHT übernommen wird:** ``policy_field``, ``summary``,
``simple_summary``, ``interest``, ``importance``, ``impact``. Das sind
Annotationen im Sinne des Speichers, keine Eigenschaften der Objekte — sie
gehören in Schicht 3 und kommen, wenn überhaupt, als eigener Annotator.
Ebenso wenig Personen: Mandatsträger stehen in ``council_persons``, hier
nicht.
"""
from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
from collections.abc import Iterator
from pathlib import Path

from council.cities.model import Batch
from council.cities.oparl import OParlClient
from council.cities.registry import BodySpec
from council.cities.store import CitiesStore

logger = logging.getLogger("council.cities.oldenburg")

BODY_ID = "oldenburg"
BASE = "https://buergerinfo.oldenburg.de"

#: Der Text der Vorlagen und Anträge liegt schon geparst in der
#: Rats-Datenbank — er wandert unter diesem Extraktor mit, statt dass
#: jemand dieselben PDFs ein zweites Mal holt.
EXTRACTOR = "council"
TEXT_VERSION = "1"


def council_db_path() -> Path:
    """Pfad der Rats-Datenbank — aus der Umgebung, mit derselben Vorgabe wie
    die Backend-Konfiguration."""
    root = Path(__file__).resolve().parents[3]
    return Path(os.environ.get("COUNCIL_DB", root / "data" / "council.sqlite"))


# --------------------------------------------------------------- Kennungen
# Sprechend und stabil: Wer eine Kennung sieht, weiß, worauf sie zeigt, und
# ein erneuter Lauf erzeugt dieselbe.

def org_id(kgrnr: int | str) -> str:
    return f"{BODY_ID}:org:{kgrnr}"


def faction_id(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")
    return f"{BODY_ID}:faction:{slug}"


def meeting_id(ksinr: int | str) -> str:
    return f"{BODY_ID}:meeting:{ksinr}"


def agenda_id(ksinr: int | str, item_number: str | None) -> str:
    return f"{BODY_ID}:agenda:{ksinr}:{item_number or '-'}"


def paper_id(kvonr: int | str) -> str:
    return f"{BODY_ID}:paper:{kvonr}"


def motion_id(document_id: int | str) -> str:
    return f"{BODY_ID}:paper:att:{document_id}"


def file_id(document_id: int | str) -> str:
    return f"{BODY_ID}:file:{document_id}"


#: Oldenburgs Ergebnisse stehen schon kanonisch in ``council_decisions.outcome``
#: — bis auf einen Wert, den der Städte-Speicher anders nennt.
_OUTCOME_MAP = {
    "accepted": "accepted", "rejected": "rejected", "postponed": "postponed",
    "noted": "noted", "no_decision": "none", "": "none", None: "none",
}


class OldenburgAdapter:
    """Liest die Rats-Datenbank und schreibt Rohobjekte in OParl-Form."""

    dialect = "oldenburg"

    # ---------------------------------------------------------------- Suche

    def discover(self, client: OParlClient, spec: BodySpec) -> dict:
        """Kein Abruf — das Body-Objekt ist bekannt."""
        return {
            "body": {"id": f"{BASE}/", "name": spec.name, "type": "Body"},
            "license": None,
            "name": spec.name,
        }

    # ------------------------------------------------------------- Abrufen

    def _conn(self) -> sqlite3.Connection:
        pfad = council_db_path()
        conn = sqlite3.connect(f"file:{pfad}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        return conn

    def iter_organizations(self, client: OParlClient, body: dict) -> Iterator[dict]:
        """Gremien aus ``committees``, Fraktionen aus den Antragstellern."""
        conn = self._conn()
        try:
            for zeile in conn.execute("SELECT kgrnr, name FROM committees ORDER BY kgrnr"):
                obj = {"id": org_id(zeile["kgrnr"]), "type": "Organization",
                       "name": zeile["name"], "organizationType": "Gremium"}
                client.raw.put_raw_object(BODY_ID, "organization", obj["id"], obj)
                yield obj
            fraktionen: set[str] = set()
            for zeile in conn.execute(
                    "SELECT applicants FROM council_attachments "
                    "WHERE is_motion=1 AND applicants IS NOT NULL AND applicants != '[]'"):
                try:
                    fraktionen.update(json.loads(zeile["applicants"]) or [])
                except (TypeError, ValueError):
                    continue
            for name in sorted(fraktionen):
                obj = {"id": faction_id(name), "type": "Organization",
                       "name": f"{name}-Fraktion", "organizationType": "Fraktion"}
                client.raw.put_raw_object(BODY_ID, "organization", obj["id"], obj)
                yield obj
        finally:
            conn.close()

    def iter_meetings(self, client: OParlClient, body: dict, since: str) -> Iterator[dict]:
        """Sitzungen samt Tagesordnungspunkten und deren Beschlüssen.

        Der Beschlusstext steht in ``council_decisions.official_text``; er ist
        das, was in OParl ``resolutionText`` heißt.
        """
        conn = self._conn()
        try:
            gremien = {z["name"]: z["kgrnr"] for z in conn.execute("SELECT kgrnr, name FROM committees")}
            punkte: dict[int, list[dict]] = {}
            for zeile in conn.execute(
                    "SELECT d.ksinr, d.item_number, d.title, d.outcome, d.raw_result, "
                    "       d.official_text, d.position "
                    "FROM council_decisions d JOIN council_sessions s ON s.ksinr = d.ksinr "
                    "WHERE d.kind = 'decision' AND s.session_date >= ? "
                    "ORDER BY d.ksinr, d.position", (since,)):
                punkte.setdefault(zeile["ksinr"], []).append({
                    "id": agenda_id(zeile["ksinr"], zeile["item_number"]),
                    "type": "AgendaItem",
                    "number": zeile["item_number"],
                    "name": zeile["title"] or "",
                    "order": zeile["position"],
                    "public": True,
                    "result": zeile["raw_result"] or zeile["outcome"],
                    "resolutionText": zeile["official_text"],
                    # Der kanonische Wert steht in Oldenburg schon fest —
                    # er wandert mit, damit die Regel in `model.outcome`
                    # nicht auf einem Freitext raten muss.
                    "ratslotseOutcome": _OUTCOME_MAP.get(zeile["outcome"], "none"),
                })

            for zeile in conn.execute(
                    "SELECT ksinr, committee, session_date, session_time, location "
                    "FROM council_sessions WHERE session_date >= ? ORDER BY session_date", (since,)):
                start = zeile["session_date"]
                if zeile["session_time"]:
                    start = f"{start}T{zeile['session_time']}:00"
                kgrnr = gremien.get(zeile["committee"])
                obj = {
                    "id": meeting_id(zeile["ksinr"]), "type": "Meeting",
                    "name": zeile["committee"] or "", "start": start,
                    "organization": [org_id(kgrnr)] if kgrnr else [],
                    "meetingState": "durchgeführt",
                    "agendaItem": punkte.get(zeile["ksinr"], []),
                }
                client.raw.put_raw_object(BODY_ID, "meeting", obj["id"], obj)
                yield obj
        finally:
            conn.close()

    def iter_papers(self, client: OParlClient, body: dict, since: str) -> Iterator[dict]:
        """Vorlagen aus ``council_templates`` — und Anträge aus den Anlagen.

        In Oldenburg gibt es **keine** Vorlagenart „Antrag": Fraktionsanträge
        hängen als Anlage an einer Verwaltungsvorlage. Sie sind der
        interessanteste Teil des Bestands und bekommen deshalb ein eigenes
        Papier.
        """
        conn = self._conn()
        try:
            # Beratungsfolge je Vorlage, damit das Papier seine Stationen kennt.
            beratungen: dict[int, list[dict]] = {}
            for zeile in conn.execute(
                    "SELECT kvonr, ksinr, committee, top, result FROM council_deliberations"):
                beratungen.setdefault(zeile["kvonr"], []).append(zeile)
            gremien = {z["name"]: z["kgrnr"] for z in conn.execute("SELECT kgrnr, name FROM committees")}

            # Datum einer Vorlage: die früheste Sitzung, in der sie beraten wurde.
            datum = {z["kvonr"]: z["d"] for z in conn.execute(
                "SELECT kvonr, MIN(date) AS d FROM council_deliberations GROUP BY kvonr")}

            for zeile in conn.execute(
                    "SELECT kvonr, template_number, title, kind, document_id, document_url, "
                    "       raw_text, n_pages, office FROM council_templates ORDER BY kvonr"):
                d = datum.get(zeile["kvonr"])
                if d and d < since:
                    continue
                obj = {
                    "id": paper_id(zeile["kvonr"]), "type": "Paper",
                    "name": zeile["title"] or "", "reference": zeile["template_number"],
                    "date": d, "paperType": zeile["kind"],
                    "web": f"{BASE}/vo0050.php?__kvonr={zeile['kvonr']}",
                    "consultation": [{
                        "id": f"{BODY_ID}:cons:{zeile['kvonr']}:{b['ksinr']}:{b['top']}",
                        "type": "Consultation",
                        "meeting": meeting_id(b["ksinr"]) if b["ksinr"] else None,
                        "agendaItem": agenda_id(b["ksinr"], b["top"]) if b["ksinr"] else None,
                        "organization": [org_id(gremien[b["committee"]])]
                                        if b["committee"] in gremien else [],
                        "role": b["result"],
                    } for b in beratungen.get(zeile["kvonr"], [])],
                }
                if zeile["document_id"]:
                    obj["mainFile"] = {
                        "id": file_id(zeile["document_id"]), "type": "File",
                        "name": "Vorlage", "mimeType": "application/pdf",
                        "accessUrl": zeile["document_url"],
                        # Der Text ist schon geparst — er wandert mit, statt
                        # dass jemand dasselbe PDF ein zweites Mal holt.
                        "text": zeile["raw_text"] or "",
                    }
                client.raw.put_raw_object(BODY_ID, "paper", obj["id"], obj)
                yield obj

            # Anträge, die als Anlage hängen.
            for zeile in conn.execute(
                    "SELECT a.document_id, a.kvonr, a.label, a.url, a.applicants, a.raw_text, "
                    "       t.template_number "
                    "FROM council_attachments a "
                    "LEFT JOIN council_templates t ON t.kvonr = a.kvonr "
                    "WHERE a.is_motion = 1 ORDER BY a.document_id"):
                d = datum.get(zeile["kvonr"])
                if d and d < since:
                    continue
                try:
                    antragsteller = json.loads(zeile["applicants"] or "[]")
                except (TypeError, ValueError):
                    antragsteller = []
                obj = {
                    "id": motion_id(zeile["document_id"]), "type": "Paper",
                    "name": zeile["label"] or "", "reference": zeile["template_number"],
                    "date": d, "paperType": "Antrag (Anlage)",
                    "web": f"{BASE}/vo0050.php?__kvonr={zeile['kvonr']}",
                    "originatorOrganization": [faction_id(a) for a in antragsteller],
                    "mainFile": {
                        "id": file_id(zeile["document_id"]), "type": "File",
                        "name": "Antrag", "mimeType": "application/pdf",
                        "accessUrl": zeile["url"], "text": zeile["raw_text"] or "",
                    },
                }
                client.raw.put_raw_object(BODY_ID, "paper", obj["id"], obj)
                yield obj
        finally:
            conn.close()

    # --------------------------------------------------------- Normalisieren

    def normalize(self, body_id: str, raw: CitiesStore) -> Batch:
        from council.cities.adapters._common import normalize_common
        from council.cities.model import Outcome

        batch = normalize_common(body_id, raw)
        # Oldenburgs Ergebnisse sind schon kanonisch — den Freitext neu zu
        # raten wäre ein Rückschritt gegenüber dem, was `protocols.py` mit
        # einem Sprachmodell herausgeholt hat.
        vorgegeben: dict[str, str] = {}
        for m in raw.raw_objects(body_id, "meeting"):
            for punkt in m.get("agendaItem") or []:
                if isinstance(punkt, dict) and punkt.get("ratslotseOutcome"):
                    vorgegeben[punkt["id"]] = punkt["ratslotseOutcome"]
        if vorgegeben:
            from dataclasses import replace
            batch.agenda_items = [
                replace(a, outcome=Outcome(vorgegeben[a.id])) if a.id in vorgegeben else a
                for a in batch.agenda_items]
        return batch

    def file_url(self, file_json: dict, url: str | None) -> str | None:
        return url

    # ------------------------------------------------------------- Texte

    def inline_texts(self, raw: CitiesStore, body_id: str) -> list[tuple[str, str]]:
        """``(file_id, text)`` — der Text steht schon in der Rats-Datenbank."""
        out: list[tuple[str, str]] = []
        for p in raw.raw_objects(body_id, "paper"):
            datei = p.get("mainFile")
            if isinstance(datei, dict) and datei.get("text") and datei.get("id"):
                out.append((datei["id"], datei["text"]))
        return out
