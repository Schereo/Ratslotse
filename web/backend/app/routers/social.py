"""Schnittstelle für den Social-Media-Bot (ratslotse-social, eigenes Repo).

Der Bot läuft auf einer anderen Maschine und baut aus diesen Daten die
Instagram-Karten: Lese-Endpunkte für Wochenvorschau, Tages-Sitzungen,
Fundstück und neue Beschlüsse, dazu ein Schreib-Endpunkt für die fertigen
Karten — weil Instagram Bilder **nur** von einer öffentlichen URL abholt
(``image_url`` ist laut Meta-Doku für Bilder Pflicht, der Direkt-Upload gilt
nur für Videos). Der Bot fragt hier alles ab, rendert lokal, und liefert die
JPEGs wieder hier ab, damit ratslotse.de sie ausliefert.

**Kein Konto, sondern ein fester Token.** Der Bot ist keine Person; ihm ein
Nutzerkonto zu geben hieße, ein Konto mit gültigem Passwort dauerhaft auf
einer zweiten Maschine zu lagern. Ohne ``SOCIAL_API_TOKEN`` sind beide
Endpunkte aus — eine Standard-Installation exponiert also nichts.

Der Schreib-Endpunkt ist die einzige Stelle im Projekt, an der von außen
Dateien entstehen, die öffentlich ausgeliefert werden. Entsprechend eng:
Dateinamen vergibt der Server, JPEG wird an den Magic Bytes geprüft (nicht
an der Endung), Größe und Anzahl sind gedeckelt, und das Zielverzeichnis
wird gegen den erlaubten Wurzelpfad aufgelöst.
"""
from __future__ import annotations

import logging
import re
import secrets
from datetime import date, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, status

from ..config import get_settings
from ..deps import get_council_store

from council.store import CouncilStore

router = APIRouter(prefix="/api/social", tags=["social"])

_log = logging.getLogger(__name__)

#: Ein Karussell trägt höchstens 10 Bilder — mehr braucht niemand hochladen.
MAX_BILDER = 10
#: 8 MiB je Bild. Unsere Karten wiegen rund 200 KiB; der Deckel ist die
#: Reißleine, keine Zielgröße.
MAX_BYTES = 8 * 1024 * 1024
#: JPEG beginnt mit FF D8 FF. Die Dateiendung sagt nichts — sie kommt vom
#: Aufrufer.
JPEG_MAGIC = b"\xff\xd8\xff"

_TAG_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def bot_token(request: Request) -> str:
    """Prüft den Bot-Token. 404 statt 401, wenn die Schnittstelle aus ist —
    ein abgeschalteter Endpunkt soll sich nicht als vorhanden verraten."""
    settings = get_settings()
    erwartet = (settings.social_api_token or "").strip()
    if not erwartet:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Nicht gefunden.")
    geliefert = (request.headers.get("X-Social-Token") or "").strip()
    # compare_digest: konstante Laufzeit, damit der Token nicht Zeichen für
    # Zeichen erraten werden kann.
    if not geliefert or not secrets.compare_digest(geliefert, erwartet):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Ungültiger Token.")
    return geliefert


@router.get("/wochenvorschau", dependencies=[Depends(bot_token)])
def wochenvorschau(
    tage: int = 14,
    store: CouncilStore = Depends(get_council_store),
) -> dict:
    """Die Wochenvorschau, wie sie auf der Startseite steht — aber neutral.

    ``meine=None`` ist Absicht: Die Fassung im Dashboard hebt Punkte hervor,
    die zu den Themen des angemeldeten Kontos passen. Ein Instagram-Beitrag
    hat kein Konto und zeigt die Sicht für die ganze Stadt.

    ``kommende`` trägt zusätzlich die terminierten Sitzungen ohne
    veröffentlichte Tagesordnung (``ksinr`` ist dann NULL). Das kommt aus
    ``upcoming_sessions`` statt aus eigenem SQL: Dort steht die kanonische
    Definition, welche Sitzung als „kommend" gilt, samt Entdopplung gegen
    gleichnamige Termine — für eine Vorschau ist gerade die Ratssitzung
    interessant, deren Tagesordnung noch aussteht.
    """
    tage = max(1, min(int(tage), 31))
    daten = store.wochenvorschau(tage=tage, max_punkte=40)
    bis = (date.today() + timedelta(days=tage)).isoformat()
    daten["kommende"] = [s for s in store.upcoming_sessions(limit=100)
                         if s["session_date"] <= bis]
    return daten


@router.get("/sitzungen/{tag}", dependencies=[Depends(bot_token)])
def sitzungen(tag: str, store: CouncilStore = Depends(get_council_store)) -> list[dict]:
    """Alle Sitzungen eines Kalendertags — Grundlage der Sitzungstag-Story."""
    if not _TAG_RE.match(tag):
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "Tag muss ein ISO-Datum sein (JJJJ-MM-TT).")
    return store.sessions_on(tag)


@router.get("/fundstueck/{tag}", dependencies=[Depends(bot_token)])
def fundstueck(tag: str, store: CouncilStore = Depends(get_council_store)) -> dict | None:
    """Das vorgenerierte Fundstück des Tages, falls vorhanden."""
    if not _TAG_RE.match(tag):
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "Tag muss ein ISO-Datum sein (JJJJ-MM-TT).")
    return store.get_fundstueck(tag)


@router.get("/neue-beschluesse", dependencies=[Depends(bot_token)])
def neue_beschluesse(
    seit_id: int,
    mindest_wichtig: int = 55,
    limit: int = 3,
    store: CouncilStore = Depends(get_council_store),
) -> list[dict]:
    """Neue, wichtige Beschlüsse seit einer ID — Kandidaten für
    „So wurde entschieden". Dieselbe Abfrage, die vorher direkt gegen die
    Datenbank lief (``ratslotse_social.quellen.neue_beschluesse``), nur
    jetzt hinter dem Token statt hinter einem lokalen DB-Pfad."""
    zeilen = [dict(r) for r in store._conn.execute(
        """SELECT d.id, d.title, d.beschluss, d.outcome, d.vote,
                  d.simple_summary, d.importance, d.item_number,
                  cs.committee, cs.session_date
           FROM council_decisions d
           JOIN council_sessions cs ON cs.ksinr = d.ksinr
           WHERE d.id > ? AND d.kind = 'decision'
             AND d.outcome IN ('angenommen', 'abgelehnt')
             AND COALESCE(d.importance, 0) >= ?
           ORDER BY d.id""",
        (seit_id, mindest_wichtig))]
    for z in zeilen:
        z["votes"] = []
    ids = [z["id"] for z in zeilen]
    if ids:
        votes = store.decision_votes_for(ids)
        for z in zeilen:
            z["votes"] = votes.get(z["id"], [])
    return zeilen[:limit] if limit else zeilen


@router.get("/hoechste-beschluss-id", dependencies=[Depends(bot_token)])
def hoechste_beschluss_id(store: CouncilStore = Depends(get_council_store)) -> dict:
    """Aktueller Zählerstand — der Startpunkt fürs erste Merken beim Bot,
    damit sein Ereignis-Cron nicht den gesamten Bestand als „neu" meldet."""
    wert = store._conn.execute("SELECT MAX(id) FROM council_decisions").fetchone()[0]
    return {"hoechste_id": int(wert or 0)}


def _zielverzeichnis(tag: str) -> Path:
    settings = get_settings()
    wurzel = Path(settings.social_media_dir).resolve()
    ziel = (wurzel / tag).resolve()
    # Gürtel und Hosenträger: ``tag`` ist schon gegen ein Datumsmuster
    # geprüft, aber der Pfad wird trotzdem gegen die Wurzel aufgelöst.
    if wurzel not in ziel.parents and ziel != wurzel:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unzulässiger Pfad.")
    return ziel


@router.post("/medien/{tag}", dependencies=[Depends(bot_token)])
async def medien_ablegen(tag: str, dateien: list[UploadFile]) -> dict:
    """Gerenderte Karten entgegennehmen und öffentlich ablegen.

    Gibt die URLs zurück, unter denen Instagram sie abholen kann. Ein
    zweiter Aufruf für denselben Tag ersetzt den Satz vollständig — der Bot
    rendert neu, wenn sich die Tagesordnung noch geändert hat.
    """
    if not _TAG_RE.match(tag):
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "Tag muss ein ISO-Datum sein (JJJJ-MM-TT).")
    if not dateien:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Keine Datei empfangen.")
    if len(dateien) > MAX_BILDER:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            f"Höchstens {MAX_BILDER} Bilder je Beitrag.")

    inhalte: list[bytes] = []
    for datei in dateien:
        roh = await datei.read(MAX_BYTES + 1)
        if len(roh) > MAX_BYTES:
            raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                                f"Bild größer als {MAX_BYTES // 1024 // 1024} MiB.")
        if not roh.startswith(JPEG_MAGIC):
            raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                                "Nur JPEG — Instagram nimmt nichts anderes.")
        inhalte.append(roh)

    ziel = _zielverzeichnis(tag)
    ziel.mkdir(parents=True, exist_ok=True)
    # Alte Fassung desselben Tages wegräumen, damit kein Bild aus einem
    # früheren Lauf im Karussell landet.
    for alt in ziel.glob("*.jpg"):
        alt.unlink()

    settings = get_settings()
    urls = []
    for i, roh in enumerate(inhalte, start=1):
        # Den Namen vergibt der Server. Der Aufrufer bestimmt nur den Inhalt.
        name = f"{tag}-{i:02d}.jpg"
        (ziel / name).write_bytes(roh)
        urls.append(f"{settings.social_media_base_url.rstrip('/')}/{tag}/{name}")

    _log.info("Social-Medien abgelegt: %s (%d Bilder)", tag, len(urls))
    return {"tag": tag, "anzahl": len(urls), "urls": urls}
