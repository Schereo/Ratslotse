"""Die Schichten des Python-Codes — als Test statt als Bitte im Review.

`CLAUDE.md` beschreibt die Aufteilung in Prosa: `kern/` ist geteilte
Infrastruktur, `council/` der Scraper samt Store, `web/backend/app/` die API,
`scripts/` die Cron-Jobs. Was daraus folgt, steht dort **nicht**: dass die
Pfeile nur in eine Richtung zeigen dürfen.

**Warum das zählt.** Ein Import von `kern` nach `council` wäre ein Ring: Beide
Pakete ließen sich dann nicht mehr getrennt laden, ein Zyklus beim Import
könnte je nach Einstiegspunkt zuschlagen (der Web-Dienst importiert anders
als ein Cron), und ein Fehler daraus erscheint als `ImportError` beim Start —
auf Prod, nicht in der CI, weil die Testsuite alles auf einmal lädt.

Gemessen am 04.09.2026 hält der Bestand die Ordnung bereits vollständig. Das
ist der beste Zeitpunkt, sie festzuschreiben: Es gibt nichts aufzuräumen,
nur etwas zu halten.

    kern      ← council ← app ← scripts
                       ↖ eval
"""
from __future__ import annotations

import ast
import collections
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parents[1]

#: Die Pakete und wo sie liegen. `app` heißt im Dateisystem anders als im
#: Import — deshalb die Zuordnung hier statt einer Ableitung aus dem Pfad.
PAKETE = {
    "kern": "kern",
    "council": "council",
    "app": "web/backend/app",
    "scripts": "scripts",
    "eval": "eval",
}

#: Wen ein Paket importieren DARF. Alles andere ist ein Fehler — auch das,
#: was heute technisch ginge. Die Liste ist die Architektur, nicht ihr Abbild.
ERLAUBT: dict[str, set[str]] = {
    # Die Grundlage. Sie kennt niemanden über sich; sonst wäre sie keine.
    "kern": set(),
    # Der Scraper steht auf `kern` und weiß nichts von einer API.
    "council": {"kern"},
    # Die API liest die Stores. Sie ruft keine Cron-Skripte auf.
    "app": {"kern", "council"},
    # Cron-Jobs stehen ganz oben und dürfen alles darunter benutzen.
    "scripts": {"kern", "council", "app"},
    # Der Eval-Aufbau ist ein Blatt wie `scripts`, kommt aber ohne die API aus.
    "eval": {"kern", "council"},
}

UEBERSPRINGEN = ("node_modules", ".venv", "__pycache__", ".next", ".claude", "/tests/")


def _paket(rel: str) -> str | None:
    for name, pfad in PAKETE.items():
        if rel == pfad or rel.startswith(pfad + "/"):
            return name
    return None


def _kanten() -> dict[tuple[str, str], list[str]]:
    """(von, nach) → die Dateien, in denen der Import steht."""
    aus: dict[tuple[str, str], list[str]] = collections.defaultdict(list)
    for p in WURZEL.rglob("*.py"):
        rel = p.relative_to(WURZEL).as_posix()
        if any(t in "/" + rel for t in UEBERSPRINGEN):
            continue
        von = _paket(rel)
        if von is None:
            continue
        try:
            baum = ast.parse(p.read_text(encoding="utf-8"))
        except SyntaxError:                      # nicht Sache dieses Tests
            continue
        for n in ast.walk(baum):
            if isinstance(n, ast.ImportFrom) and n.module and n.level == 0:
                ziele = [n.module]
            elif isinstance(n, ast.Import):
                ziele = [a.name for a in n.names]
            else:
                continue
            for z in ziele:
                nach = z.split(".")[0]
                if nach in PAKETE and nach != von:
                    aus[(von, nach)].append(rel)
    return aus


@pytest.mark.parametrize("paket", sorted(ERLAUBT))
def test_ein_paket_importiert_nur_nach_unten(paket: str):
    verstoss = {
        nach: sorted(set(dateien))[:5]
        for (von, nach), dateien in _kanten().items()
        if von == paket and nach not in ERLAUBT[paket]
    }
    assert not verstoss, (
        f"`{paket}` importiert aus {sorted(verstoss)}, darf aber nur "
        f"{sorted(ERLAUBT[paket]) or '— nichts —'}.\n"
        f"Betroffen: {verstoss}\n"
        "Ein Pfeil nach oben ist ein Ring: Der Fehler daraus erscheint als "
        "ImportError beim Start eines Dienstes, nicht hier — weil die "
        "Testsuite alles auf einmal lädt. Gehört der geteilte Teil nach "
        "`kern/`? Oder ist der Aufrufer in der falschen Schicht?")


def test_die_erlaubnisliste_ist_nicht_zu_grosszuegig():
    """Die zweite Richtung: Steht in `ERLAUBT` eine Kante, die es gar nicht
    gibt? Dann ist sie entweder Absicht für später — oder ein Rest, der die
    Regel unnötig aufweicht."""
    vorhanden = {(v, n) for (v, n) in _kanten()}
    ungenutzt = sorted(
        (v, n) for v, ns in ERLAUBT.items() for n in ns if (v, n) not in vorhanden)
    # `app → kern`/`council` usw. sind alle in Gebrauch; was hier auftaucht,
    # ist eine Erlaubnis auf Vorrat.
    assert ungenutzt == [], (
        f"Diese Erlaubnisse werden von niemandem gebraucht: {ungenutzt}. "
        "Eine Regel, die mehr zulässt als nötig, hält beim nächsten Mal "
        "weniger. Aus ERLAUBT streichen.")
