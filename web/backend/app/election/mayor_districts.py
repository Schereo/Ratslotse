"""Die Wahlbezirke einer OB-Wahl aus der Ergebnisdarstellung — ein Abruf, 133 Zeilen.

Die Stichwahl hat keine Open-Data-CSV. Sie hat aber, wie jede Wahl im
Votemanager, eine Ebene „Wahlbezirke" in der Ergebnisdarstellung, und deren
Übersicht (``uebersicht_<ebene>_0.json``) trägt **alle** Bezirke auf einmal:
je Zeile das Wahllokal, ob es schon gemeldet hat, Wahlberechtigte,
Wähler*innen, gültige Stimmen und je Kandidatur die Stimmen. Gemessen am
ersten Wahlgang 2026 (``wahl_2552``, 222 KB) und an der Stichwahl 2021
(``wahl_224``, alte API) — dieselbe Form seit fünf Jahren.

Wozu: Erst je Bezirk lässt sich ein Zwischenstand deuten. Der Prange-Anteil
streute im ersten Wahlgang zwischen den Bezirken um acht Punkte, die
Briefwahl lag fünf Punkte anders als die Urne. „Wer führt gerade" ist ohne
den Blick auf die offenen Bezirke keine Aussage — dafür rechnet
``runoff_model`` (PR S2), und das hier ist sein Eingang.

**Eine Falle, gemessen:** ``felder`` einer Zeile ist um ZWEI kürzer als der
``header`` der Tabelle — „Wahlbezirk" und „Stand" stehen als ``label`` und
``statusString`` in der Zeile selbst. Spalte ``i`` des Kopfes ist also
``felder[i − 2]``. Wer ``i − 1`` nimmt, liest die Wahlberechtigten als
Wahlbeteiligung und bekommt lauter ``None``.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

from . import presentation, votemanager

_log = logging.getLogger("ratslotse.web.wahlabend")

#: Um so viele Spalten ist ``felder`` kürzer als ``header`` (s. Modul-Docstring).
FELD_VERSATZ = 2


@dataclass(frozen=True)
class MayorDistrict:
    """Ein Wahlbezirk mit seinem Stand. ``votes`` trägt nur die bekannten
    Kandidaturen (Slug → Stimmen); ``None`` heißt „noch nicht gemeldet"."""

    number: int
    name: str
    #: Wahlbereich 1…6 — Hunderter bzw. Zehner ab 900 (``votemanager.area_of_district``).
    area: int
    #: Briefwahlbezirk (ab 900)? Zählt zum Wahlbereich, hat aber keinen Ort.
    postal: bool
    counted: bool
    eligible: int | None
    voters: int | None
    valid_votes: int | None
    votes: dict[str, int | None]


def level_id(wahl_payload: Any) -> str | None:
    """Die Ebenen-Id der Wahlbezirke aus ``wahl.json`` (``menu_links``,
    ``type: uebersicht``, Titel „Wahlbezirke")."""
    links = wahl_payload.get("menu_links", []) if isinstance(wahl_payload, dict) else []
    for link in links:
        if not isinstance(link, dict) or link.get("type") != "uebersicht":
            continue
        titel = str(link.get("title") or "").casefold()
        if "bezirk" in titel and isinstance(link.get("id"), str):
            return link["id"]
    return None


def _nachname(label_kurz: str) -> str:
    """„Rohr, GRÜNE" → „Rohr"; „Wahlberechtigte" → „Wahlberechtigte"."""
    return label_kurz.split(",", 1)[0].strip()


def _slug_columns(header: list[Any], known_slugs: dict[str, str]) -> dict[int, str]:
    """Spaltenindex → Slug für jede Kandidaten-Spalte des Kopfes. Der Kopf
    nennt Nachname und Liste („Rohr, GRÜNE"); der Nachname ist der Schlüssel
    (``mayor.slug_of``), wie überall in der OB-Auswertung."""
    from .mayor import slug_of

    out: dict[int, str] = {}
    for i, h in enumerate(header):
        kurz = h.get("labelKurz") if isinstance(h, dict) else None
        if not isinstance(kurz, str) or "," not in kurz:
            continue
        slug = slug_of(_nachname(kurz))
        if slug in known_slugs:
            out[i] = slug
    return out


def _spalte(header: list[Any], *praefixe: str) -> int | None:
    for i, h in enumerate(header):
        kurz = str(h.get("labelKurz") or "") if isinstance(h, dict) else ""
        if any(kurz.casefold().startswith(p) for p in praefixe):
            return i
    return None


def parse_overview(payload: Any, known_slugs: dict[str, str]) -> tuple[MayorDistrict, ...]:
    """Die Übersichts-Datei einer Wahlbezirks-Ebene → Bezirke.

    ``known_slugs`` (Slug → Name) sagt, welche Kandidaturen zählen; im ersten
    Wahlgang stehen neun Spalten, für die Stichwahl-Probe braucht es zwei.
    Zeilen ohne führende Nummer (die Stadtzeile) werden übersprungen. Fehlt
    die Tabelle (vor der Auszählung ist die Datei leer), kommt ``()``.
    """
    tabelle = payload.get("tabelle") if isinstance(payload, dict) else None
    if not isinstance(tabelle, dict):
        return ()
    header = tabelle.get("header") or []
    zeilen = tabelle.get("zeilen") or []
    if not isinstance(header, list) or not isinstance(zeilen, list):
        return ()
    slugs = _slug_columns(header, known_slugs)
    i_berechtigt = _spalte(header, "wahlberechtigte")
    i_waehler = _spalte(header, "wahlbeteiligung", "wähler")
    i_gueltig = _spalte(header, "gültig")

    def feld(felder: list[Any], i: int | None) -> int | None:
        if i is None:
            return None
        j = i - FELD_VERSATZ
        if j < 0 or j >= len(felder) or not isinstance(felder[j], dict):
            return None
        return presentation.parse_number(felder[j].get("absolut"))

    out: list[MayorDistrict] = []
    for z in zeilen:
        if not isinstance(z, dict):
            continue
        label = str(z.get("label") or "")
        nummer = votemanager.district_number(label, None)
        if nummer is None:
            continue  # die Stadtzeile — oder etwas, das kein Bezirk ist
        felder = z.get("felder") or []
        if not isinstance(felder, list):
            felder = []
        status = str(z.get("statusString") or "").casefold()
        # „eingegangen" ist der Wortlaut 2021 und 2026; zur Sicherheit zählt
        # auch ein voller Prozentbalken.
        counted = status.startswith("eingegangen") or z.get("statusProzent") == 100
        stimmen: dict[str, int | None] = {slug: feld(felder, i) for i, slug in slugs.items()}
        if not counted:
            stimmen = {slug: None for slug in stimmen}
        area = votemanager.area_of_district(nummer)
        if area is None:
            _log.info("Wahlabend/OB: Bezirk %s ohne Wahlbereich — übersprungen", label)
            continue
        out.append(MayorDistrict(
            number=nummer, name=re.sub(r"^\d{3}\s*", "", label).strip() or label,
            area=area, postal=nummer >= 900, counted=counted,
            eligible=feld(felder, i_berechtigt), voters=feld(felder, i_waehler),
            valid_votes=feld(felder, i_gueltig) if counted else None,
            votes=stimmen,
        ))
    out.sort(key=lambda d: d.number)
    return tuple(out)


def overview_path(api_path: str, ebene: str) -> str:
    return f"{api_path}/uebersicht_{ebene}_0.json"
