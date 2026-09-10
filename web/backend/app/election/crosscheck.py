"""Bedeuten die Spalten das, was wir annehmen? Zwei Gegenproben.

Die ganze Auswertung hängt an EINER stillen Annahme: dass Spalte ``D7`` der
CSV die Liste mit Index 7 im Register ist. Steht die Reihenfolge der
Wahlvorschläge am Wahlabend anders in der Datei als in der amtlichen
Bekanntmachung, rechnet der Dienst weiter — nur eben Volts Stimmen auf die
PIRATEN. Kein Fehler, keine Ausnahme, keine leere Seite: nur falsche Zahlen.
Genau die Fehlerklasse, die niemand bemerkt.

Also zwei Proben, beide nur **Hinweise** (``Snapshot.warnings``) — sie halten
nichts an und ändern ``Snapshot.ok`` nicht:

1. **Gegen den Votemanager selbst** (Netz, optional). Sobald ausgezählt wird,
   trägt die Stadt-Ebene ein JSON mit der Ergebnistabelle; deren Zeilen stehen
   in Spaltenreihenfolge und nennen die Wahlvorschläge im Klartext
   („SPD - Summe Partei- und Kandidaten-Stimmen"). Daraus lässt sich die
   Reihenfolge ablesen und gegen das Register halten. Vor der Auszählung fehlt
   die Tabelle ganz — dann gibt es nichts zu prüfen.
2. **Gegen die Kopfzeile** (ohne Netz). Je Liste steht in der CSV genau eine
   Kandidatenspalte je Listenplatz; die Höchstzahl muss zur Höchstzahl der
   Bewerber*innen im Register passen, und ein Einzelwahlvorschlag hat gar
   keine. Das prüft dieselbe Zuordnung von der anderen Seite und braucht
   keinen zweiten Abruf.

Passt eine Zuordnung nicht, ist der Notausgang ``WAHLABEND_COLUMNS``
(s. ``register.py``): Spaltenreihenfolge in die ``.env``, Dienst neu starten,
fertig — kein Deploy, kein Merge, keine Nacht.

Die Schlüsselwörter unten sind bewusst **groß-/kleinschreibungsempfindlich**:
„Die PARTEI" trägt PARTEI in Versalien, „Freie Demokratische Partei" nicht —
ohne den Unterschied träfe das Schlüsselwort die FDP mit.
"""
from __future__ import annotations

import logging
import re
from collections.abc import Sequence
from typing import Any

import requests

from .register import Register
from .register import load as load_register

#: Die Ergebnistabelle der Stadt-Ebene. Vor der Auszählung ohne ``Komponente``.
TABLE_PATH = "/daten/api/wahl_913/ergebnis_ebene_-6361_id_10358_0.json"
#: Kürzer als beim CSV-Abruf: Diese Datei ist eine Zugabe, keine Grundlage.
TIMEOUT = (5, 10)

#: Was hinter dem letzten „ - " einer Zeile stehen kann. Der Wortlaut 2026 darf
#: leicht abweichen, deshalb wird auf Wortbestandteile geprüft, nicht auf
#: Gleichheit.
TOTAL = "total"
LIST = "list"
CANDIDATES = "candidates"

#: Slug -> Wörter, an denen die Liste in der Votemanager-Schreibweise zu
#: erkennen ist. Ein Wort genügt. Groß/klein zählt (s. Modul-Docstring).
KEYWORDS: dict[str, tuple[str, ...]] = {
    "gruene": ("GRÜNE", "GRUENE", "Grüne", "Bündnis 90"),
    "spd": ("SPD",),
    "cdu": ("CDU",),
    "linke": ("LINKE", "Linke"),
    "fdp": ("FDP",),
    "afd": ("AfD",),
    "volt": ("Volt",),
    "piraten": ("PIRATEN", "Piraten"),
    "bsw": ("BSW", "Wagenknecht"),
    "dava": ("DAVA",),
    "stille": ("Stille",),
    "partei": ("PARTEI",),
    "pgm": ("PGM",),
    "buergerbuendnis": ("BB-OL", "Bürger Bündnis", "Bürgerbündnis"),
    "echt-oldenburg": ("Echt Oldenburg",),
    "fuer-oldenburg": ("WFO", "Für Oldenburg"),
}

_log = logging.getLogger("ratslotse.web.wahlabend")


# ------------------------------------------------------------------ Kopfzeile

def check_header(header: Sequence[str], reg: Register | None = None) -> list[str]:
    """Die Kandidatenspalten der CSV gegen die Listenlängen des Registers.

    Ohne Netz und ohne Ergebnisse: Der Kopf steht ab dem ersten Abruf. Findet
    sich gar keine ``D<n>_2_<k>``-Spalte (altes Schema von 2021), wird nicht
    geprüft — eine Probe, die ihre Grundlage nicht kennt, warnt sonst blind.
    """
    reg = reg or load_register()
    widest: dict[int, int] = {}
    for h in header:
        m = re.fullmatch(r"D(\d+)_2_(\d+)", h.strip())
        if m:
            n, k = int(m.group(1)), int(m.group(2))
            widest[n] = max(widest.get(n, 0), k)
    if not widest:
        return []
    out: list[str] = []
    for p in sorted(reg.parties, key=lambda p: p.index):
        found = widest.get(p.index, 0)
        if p.kind == "einzelbewerber":
            if found:
                out.append(f"Spalte D{p.index} hat {found} Kandidatenspalte(n), im Register steht dort der "
                           f"Einzelwahlvorschlag ‚{p.short}‘ — Zuordnung prüfen!")
            continue
        expected = max((len(c) for c in p.areas.values()), default=0)
        if found != expected:
            out.append(f"Spalte D{p.index} hat {found} Kandidatenspalte(n), das Register erwartet {expected} "
                       f"für ‚{p.short}‘ — Zuordnung prüfen!")
    return out


# ------------------------------------------------------------------ Tabelle

def _table_rows(payload: Any) -> list[Any]:
    """``Komponente.tabelle.zeilen`` — ``Komponente`` darf auch eine Liste sein."""
    if not isinstance(payload, dict):
        return []
    component = payload.get("Komponente")
    candidates = component if isinstance(component, list) else [component]
    for c in candidates:
        if not isinstance(c, dict):
            continue
        table = c.get("tabelle")
        if isinstance(table, dict) and isinstance(table.get("zeilen"), list):
            return table["zeilen"]
    return []


def label_of(row: Any) -> str | None:
    if not isinstance(row, dict):
        return None
    label = row.get("label")
    if isinstance(label, str):
        return label.strip() or None
    if isinstance(label, dict):
        for key in ("labelKurz", "labelLang", "label"):
            value = label.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def suffix_kind(suffix: str) -> str | None:
    low = suffix.lower()
    if "summe" in low and "partei" in low and "kandidaten" in low:
        return TOTAL
    if "summe" in low and "kandidaten" in low:
        return CANDIDATES
    if "partei" in low and "stimmen" in low:
        return LIST
    return None


def columns(payload: Any) -> list[str]:
    """Die Wahlvorschläge in Spaltenreihenfolge, aus der Ergebnistabelle.

    Je Liste stehen dort drei Zeilen (Gesamt, Partei, Kandidaten); gezählt wird
    die Gesamt-Zeile. Ein Einzelwahlvorschlag hat nur eine Zeile und ist an dem
    Wort zu erkennen. Alles andere (Wahlberechtigte, Wähler*innen, ungültige
    Stimmen) fällt heraus.
    """
    out: list[str] = []
    for row in _table_rows(payload):
        label = label_of(row)
        if not label:
            continue
        # Von HINTEN trennen: „Bürger Bündnis Oldenburg (BB - OL) - Summe …"
        # trägt den Bindestrich schon im Namen.
        name, sep, suffix = label.rpartition(" - ")
        if sep:
            kind = suffix_kind(suffix)
            if kind == TOTAL:
                out.append(name.strip())
                continue
            if kind in (LIST, CANDIDATES):
                continue
        if "einzelwahlvorschlag" in label.lower():
            out.append(label)
    return out


def slugs_for(name: str) -> set[str]:
    return {slug for slug, words in KEYWORDS.items() if any(w in name for w in words)}


def check_columns(names: Sequence[str], reg: Register | None = None) -> list[str]:
    """Die Reihenfolge des Votemanagers gegen die des Registers.

    Leere Eingabe heißt „nichts erkannt" (Tabelle fehlt, oder der Wortlaut hat
    sich 2026 geändert) — dann wird geschwiegen statt geraten.
    """
    if not names:
        return []
    reg = reg or load_register()
    parties = sorted(reg.parties, key=lambda p: p.index)
    out: list[str] = []
    if len(names) != len(parties):
        out.append(f"Der Votemanager listet {len(names)} Wahlvorschläge, das Register {len(parties)} "
                   f"— Zuordnung prüfen!")
    for party, name in zip(parties, names):
        if party.slug in slugs_for(name):
            continue
        out.append(f"Spalte D{party.index} heißt beim Votemanager ‚{name}‘, im Register ‚{party.short}‘ "
                   f"— Zuordnung prüfen!")
    return out


# ------------------------------------------------------------------ Abruf

def fetch_table(session: requests.Session, base: str) -> Any | None:
    """Die Ergebnistabelle der Stadt-Ebene — ``None``, wenn sie nicht da ist.

    Bewusst ohne Weiterreichen des Fehlers: Diese Datei ist die vierte,
    optionale. Ihr Ausfall darf den Wahlabend nicht rot färben.
    """
    try:
        resp = session.get(base + TABLE_PATH, timeout=TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except (requests.RequestException, ValueError) as exc:
        _log.info("Wahlabend: Spaltenprobe ohne Antwort (%s: %s)", type(exc).__name__, exc)
        return None


def run(session: requests.Session, base: str, header: Sequence[str] | None, *, counted: bool,
        payload: Any | None = None) -> list[str]:
    """Beide Proben. Gibt Hinweise zurück und wirft nie.

    ``payload`` ist die Ergebnistabelle der Stadt, falls der Ersatzpfad
    (``presentation``) sie in dieser Runde schon geholt hat — dann wird sie
    nicht ein zweites Mal abgerufen."""
    reg = load_register()
    out: list[str] = []
    if header:
        out += check_header(header, reg)
    if payload is None and counted:
        payload = fetch_table(session, base)
    if payload is not None:
        out += check_columns(columns(payload), reg)
    return out
