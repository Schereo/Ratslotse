"""Was alle Dialekte teilen: Verweise auflösen, Rohobjekte zu einem Batch machen.

``normalize_common`` ist **rein** — sie liest nur die Rohablage, nie das Netz.
Deshalb lässt sich die Stufe beliebig oft wiederholen, und die Tests füttern
sie mit eingecheckten Rohobjekten statt mit einem Server.
"""
from __future__ import annotations

import re
from dataclasses import replace
from typing import Any

from council.cities.model import (
    AgendaItem, Batch, Consultation, File, FileRole, Meeting, Organization, Paper,
    file_role, org_kind, outcome, paper_kind,
)
from council.cities.oparl import as_list
from council.cities.store import CitiesStore

#: ALLRIS setzt ``created``/``modified`` bei jedem Objekt auf diesen Wert.
#: Als Datum ist er wertlos — wer ihn für echt hält, sortiert den ganzen
#: Bestand auf denselben Tag.
ALLRIS_LEERDATUM = "2000-01-01"


def obj_id(o: Any) -> str | None:
    """Die ``id``-URL eines Objekts — egal ob eingebettet oder als Verweis."""
    if isinstance(o, str):
        return o
    if isinstance(o, dict):
        wert = o.get("id")
        return wert if isinstance(wert, str) else None
    return None


def ref(o: dict, key: str) -> str | None:
    """Erster Verweis unter ``key``."""
    werte = as_list(o.get(key))
    for w in werte:
        kennung = obj_id(w)
        if kennung:
            return kennung
    return None


def refs(o: dict, key: str) -> list[str]:
    return [k for k in (obj_id(w) for w in as_list(o.get(key))) if k]


def parse_date(wert: Any) -> str | None:
    """ISO-Datum ohne Zeit — oder ``None``, wenn es keins gibt.

    Das ALLRIS-Leerdatum zählt als „unbekannt": Es steht bei ALLEN Objekten
    in ``created``/``modified`` und sagt nichts über den Vorgang.
    """
    if not isinstance(wert, str) or len(wert) < 10:
        return None
    datum = wert[:10]
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", datum):
        return None
    return None if datum == ALLRIS_LEERDATUM else datum


def parse_datetime(wert: Any) -> str | None:
    if not isinstance(wert, str) or len(wert) < 10:
        return None
    if wert[:10] == ALLRIS_LEERDATUM:
        return None
    return wert


def normalize_title(text: str | None) -> str:
    """Titel für den Abgleich vereinheitlichen — Kleinschrift, nur Buchstaben.

    Gebraucht, wo ein Dialekt Papier und Tagesordnungspunkt nicht verbindet
    (ALLRIS): Dann ist der Titel die einzige Brücke.
    """
    grob = re.sub(r"[^a-zäöüß0-9 ]", " ", (text or "").lower())
    return re.sub(r"\s+", " ", grob).strip()[:120]


def files_from(o: dict, body_id: str, *, paper_id: str | None = None,
               agenda_item_id: str | None = None, meeting_id: str | None = None,
               url_fix=None) -> list[File]:
    """Alle Dateien eines Objekts, mit Rolle.

    ``url_fix`` erlaubt einem Dialekt, kaputte Adressen zu ersetzen — Magdeburg
    nennt Datei-URLs, die durchweg 404 antworten.
    """
    out: list[File] = []
    for key in ("mainFile", "auxiliaryFile", "resolutionFile", "invitation",
                "resultsProtocol", "verbatimProtocol"):
        for eintrag in as_list(o.get(key)):
            if isinstance(eintrag, str):
                kennung, daten = eintrag, {}
            elif isinstance(eintrag, dict):
                kennung, daten = obj_id(eintrag), eintrag
            else:
                continue
            if not kennung:
                continue
            url = daten.get("accessUrl") or daten.get("downloadUrl")
            if url_fix:
                url = url_fix(daten, url)
            out.append(File(
                id=kennung, body_id=body_id, role=file_role(daten.get("name"), key),
                paper_id=paper_id, agenda_item_id=agenda_item_id, meeting_id=meeting_id,
                name=daten.get("name") or daten.get("fileName"),
                mime=daten.get("mimeType"), size=daten.get("size"), access_url=url))
    return out


def promote_main(dateien: list[File]) -> list[File]:
    """Ohne erkennbares Hauptdokument gilt die erste Anlage als eines.

    Somacos hängt alles unter ``auxiliaryFile``; welche Datei die Vorlage ist,
    verrät nur ihr Name. Heißt keine davon danach — es gibt Vorlagen, deren
    Anlagen schlicht „Anlage 1" heißen —, bliebe das Papier ohne Text und
    damit ohne Einordnung. Dann ist die erste Anlage die beste Vermutung.
    """
    if not dateien or any(f.role == FileRole.MAIN for f in dateien):
        return dateien
    zuerst = dateien[0]
    if zuerst.role != FileRole.AUXILIARY:
        return dateien
    return [replace(zuerst, role=FileRole.MAIN)] + dateien[1:]


def organizations_from(raw: CitiesStore, body_id: str) -> list[Organization]:
    out = []
    for o in raw.raw_objects(body_id, "organization"):
        kennung = obj_id(o)
        if not kennung:
            continue
        name = o.get("name") or o.get("shortName") or ""
        typ = o.get("organizationType") or o.get("classification")
        out.append(Organization(kennung, body_id, name, typ, org_kind(name, typ)))
    return out


def meetings_from(raw: CitiesStore, body_id: str, url_fix=None
                  ) -> tuple[list[Meeting], list[AgendaItem], list[File]]:
    """Sitzungen samt eingebetteten Tagesordnungspunkten und deren Dateien."""
    meetings: list[Meeting] = []
    items: list[AgendaItem] = []
    files: list[File] = []
    for m in raw.raw_objects(body_id, "meeting"):
        kennung = obj_id(m)
        if not kennung:
            continue
        meetings.append(Meeting(
            id=kennung, body_id=body_id, organization_id=ref(m, "organization"),
            name=m.get("name") or "", start=parse_datetime(m.get("start")),
            end=parse_datetime(m.get("end")), state_raw=m.get("meetingState"),
            cancelled=bool(m.get("cancelled"))))
        files += files_from(m, body_id, meeting_id=kennung, url_fix=url_fix)
        for pos, eintrag in enumerate(as_list(m.get("agendaItem"))):
            if not isinstance(eintrag, dict):
                continue          # nur ein Verweis; der Dialekt muss ihn holen
            ai_id = obj_id(eintrag)
            if not ai_id:
                continue
            roh = eintrag.get("result")
            items.append(AgendaItem(
                id=ai_id, meeting_id=kennung, name=eintrag.get("name") or "",
                number=str(eintrag.get("number")) if eintrag.get("number") is not None else None,
                position=eintrag.get("order") if isinstance(eintrag.get("order"), int) else pos,
                public=bool(eintrag.get("public", True)),
                result_raw=roh, outcome=outcome(roh),
                resolution_text=eintrag.get("resolutionText")))
            files += files_from(eintrag, body_id, agenda_item_id=ai_id, url_fix=url_fix)
    return meetings, items, files


def papers_from(raw: CitiesStore, body_id: str, url_fix=None
                ) -> tuple[list[Paper], list[File], list[Consultation]]:
    """Vorlagen samt Dateien und Beratungsfolge.

    ``originatorOrganization`` wird übernommen, wenn der Dialekt sie liefert —
    ALLRIS und Somacos tun das nicht, dort steht die Fraktion nur im Titel und
    im Dokument. Ein Annotator holt sie später heraus; die Spalte bleibt so
    lange leer, statt geraten zu werden.
    """
    papers: list[Paper] = []
    files: list[File] = []
    consultations: list[Consultation] = []
    for p in raw.raw_objects(body_id, "paper"):
        kennung = obj_id(p)
        if not kennung:
            continue
        typ = p.get("paperType")
        papers.append(Paper(
            id=kennung, body_id=body_id, name=p.get("name") or "",
            reference=p.get("reference"), date=parse_date(p.get("date")),
            paper_type_raw=typ, kind=paper_kind(typ),
            originator_org_id=ref(p, "originatorOrganization"),
            under_direction_of_id=ref(p, "underDirectionOf"),
            web=p.get("web")))
        files += promote_main(files_from(p, body_id, paper_id=kennung, url_fix=url_fix))
        for eintrag in as_list(p.get("consultation")):
            if isinstance(eintrag, str):
                consultations.append(Consultation(id=eintrag, paper_id=kennung))
                continue
            if not isinstance(eintrag, dict):
                continue
            c_id = obj_id(eintrag)
            if not c_id:
                continue
            consultations.append(Consultation(
                id=c_id, paper_id=kennung,
                meeting_id=ref(eintrag, "meeting"),
                agenda_item_id=ref(eintrag, "agendaItem"),
                organization_id=ref(eintrag, "organization"),
                role_raw=eintrag.get("role"),
                authoritative=eintrag.get("authoritative")))
    return papers, files, consultations


def normalize_common(body_id: str, raw: CitiesStore, url_fix=None) -> Batch:
    """Rohablage → Batch. Der Teil, der bei allen Dialekten gleich ist."""
    meetings, items, m_files = meetings_from(raw, body_id, url_fix)
    papers, p_files, consultations = papers_from(raw, body_id, url_fix)
    return Batch(
        organizations=organizations_from(raw, body_id),
        meetings=meetings, agenda_items=items,
        papers=papers, files=m_files + p_files, consultations=consultations)


def link_by_title(batch: Batch) -> int:
    """Papiere und Tagesordnungspunkte über den Titel verbinden — nur als Notnagel.

    ALLRIS liefert die Beratungsfolge eines Papiers oft ohne ``agendaItem``:
    Die Verbindung existiert im System, steht aber nicht in der Antwort. Ohne
    sie hätte kein Papier je ein Ergebnis. Der Abgleich läuft über den
    normalisierten Titel und ist als solcher erkennbar — die Kennung der so
    entstandenen Beratung trägt ``#title-match#``.

    Gibt zurück, wie viele Verbindungen so entstanden sind (Kennzahl für den
    Lauf: steigt sie stark, hat der Dialekt sich geändert).
    """
    nach_titel: dict[tuple[str, str], str] = {}
    for a in batch.agenda_items:
        schluessel = (a.meeting_id, normalize_title(a.name))
        nach_titel.setdefault(schluessel, a.id)
    titel_zu_items: dict[str, list[AgendaItem]] = {}
    for a in batch.agenda_items:
        titel_zu_items.setdefault(normalize_title(a.name), []).append(a)

    schon_verbunden = {c.paper_id for c in batch.consultations if c.agenda_item_id}
    ergaenzt = 0
    for p in batch.papers:
        if p.id in schon_verbunden:
            continue
        kandidaten = titel_zu_items.get(normalize_title(p.name), [])
        # Nur eindeutige Treffer: Zwei gleichnamige Punkte in verschiedenen
        # Sitzungen sind meist dieselbe Sache in zwei Stationen — welche
        # gemeint ist, weiß der Titel nicht.
        mit_ergebnis = [a for a in kandidaten if a.outcome != "none"]
        wahl = mit_ergebnis or kandidaten
        if len(wahl) != 1:
            continue
        ziel = wahl[0]
        batch.consultations.append(Consultation(
            id=f"{p.id}#title-match#{ziel.id}", paper_id=p.id,
            meeting_id=ziel.meeting_id, agenda_item_id=ziel.id,
            role_raw="Titelabgleich", authoritative=None))
        ergaenzt += 1
    return ergaenzt
