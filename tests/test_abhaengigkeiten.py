"""Jede Abhängigkeit braucht eine feste Fassung in ``constraints.txt``.

**Der Fehler, gegen den das steht.** Die Requirements-Dateien nennen nur
Untergrenzen. Bis 02.09.2026 gab es nichts darüber hinaus — jeder Lauf
installierte die jeweils neueste Fassung, und die drei Umgebungen liefen
auseinander, ohne dass es irgendwo aufgefallen wäre: fastapi 0.137 auf Prod,
0.139 auf dev, in der CI wieder etwas Drittes. Die CI prüfte also gegen etwas,
das die Seite nicht trägt.

Eine neue Abhängigkeit ohne Zeile in ``constraints.txt`` reißt dieses Loch
sofort wieder auf, und zwar unsichtbar: Es fehlt ja nichts, es ist nur wieder
alles offen.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parents[1]
REQUIREMENTS = (
    WURZEL / "requirements.txt",
    WURZEL / "requirements-dev.txt",
    WURZEL / "web" / "backend" / "requirements.txt",
)
CONSTRAINTS = WURZEL / "constraints.txt"

#: Bewusst ohne feste Fassung — mit Grund.
OHNE_PIN = {
    # Kein Laufzeit-Paket. Die Begründung für die offene Grenze steht in
    # `ruff.toml`: Eine neue Fassung kann eine F-Regel schärfen, der Fund wäre
    # dann echt, nur zur Unzeit — festgenagelt würde er nie gefunden.
    "ruff",
}


def _normal(name: str) -> str:
    """PEP 503: Groß/klein, ``-``, ``_`` und ``.`` sind dasselbe Paket."""
    return re.sub(r"[-_.]+", "-", name).lower()


def _angefordert() -> set[str]:
    namen: set[str] = set()
    for datei in REQUIREMENTS:
        for zeile in datei.read_text().splitlines():
            zeile = zeile.split("#")[0].strip()
            if not zeile or zeile.startswith("-"):
                continue
            # `httpx[http2]>=0.27` → `httpx`
            namen.add(_normal(re.split(r"[\[<>=!~;]", zeile)[0].strip()))
    return namen


def _festgelegt() -> dict[str, str]:
    fest: dict[str, str] = {}
    for zeile in CONSTRAINTS.read_text().splitlines():
        zeile = zeile.split("#")[0].strip()
        if "==" in zeile:
            name, fassung = zeile.split("==", 1)
            fest[_normal(name.strip())] = fassung.strip()
    return fest


@pytest.mark.parametrize("paket", sorted(_angefordert() - OHNE_PIN))
def test_jede_abhaengigkeit_hat_eine_feste_fassung(paket):
    assert paket in _festgelegt(), (
        f"„{paket}" + "“ steht in einer Requirements-Datei, aber nicht in "
        "constraints.txt. Dann installiert jede Umgebung wieder etwas anderes.\n"
        "Feste Fassung eintragen (die, mit der es hier läuft) — oder, wenn das "
        "bewusst offen bleiben soll, mit Begründung in OHNE_PIN aufnehmen."
    )


def test_constraints_nagelt_mit_doppeltem_gleich_fest():
    """Eine Zeile mit ``>=`` in einer Constraints-Datei bindet nichts."""
    lose = []
    for zeile in CONSTRAINTS.read_text().splitlines():
        ohne_kommentar = zeile.split("#")[0].strip()
        if ohne_kommentar and "==" not in ohne_kommentar:
            lose.append(ohne_kommentar)
    assert not lose, f"keine feste Fassung: {lose}"


def test_ohne_pin_traegt_keine_leichen():
    veraltet = OHNE_PIN - _angefordert()
    assert not veraltet, (
        f"{sorted(veraltet)} steht in keiner Requirements-Datei mehr — "
        "die Ausnahme deckt nichts ab und gehört gestrichen."
    )
