"""Wächter für die Feature-Schalter (`kern/features.py`).

**Wogegen das steht.** Ein Schalter ist ein Name, der an zwei Stellen stimmen
muss: in der Registry und an der Verwendung im Frontend. Passen sie nicht
zusammen, passiert etwas Unangenehmes — und zwar LAUTLOS:

* Ein Tippfehler an der Verwendung (``useFeature("haushalt-labr")``) ist
  dauerhaft aus. Das sieht aus wie „noch nicht angeschaltet", und niemand
  sucht an der richtigen Stelle.
* Ein Schalter in der Registry, den niemand mehr liest, bleibt für immer
  stehen. „Vielleicht braucht ihn noch jemand" ist der Satz, an dem
  Schalter-Systeme sterben.

**Beide Richtungen**, wie jeder Wächter hier.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from kern.features import FEATURES, Feature, aktive, an

WURZEL = Path(__file__).resolve().parents[1]
FRONTEND = WURZEL / "web" / "frontend"

#: Wo die Schalter im Frontend gelesen werden. `lib/features.ts` selbst ist
#: die Fassung — dort steht kein Name, sondern der Parameter.
EIGENE_SACHE = {"lib/features.ts", "lib/features.test.ts"}


def _verwendete_namen() -> dict[str, set[str]]:
    """``{name: {datei, …}}`` — alle ``useFeature("…")``/``featureAktiv(…, "…")``."""
    muster = re.compile(r'(?:useFeature|featureAktiv)\([^)"\']*["\']([a-z0-9-]+)["\']')
    aus: dict[str, set[str]] = {}
    for pfad in sorted(list(FRONTEND.rglob("*.ts")) + list(FRONTEND.rglob("*.tsx"))):
        if "node_modules" in pfad.parts or ".next" in str(pfad):
            continue
        rel = pfad.relative_to(FRONTEND).as_posix()
        if rel in EIGENE_SACHE:
            continue
        for treffer in muster.findall(pfad.read_text(encoding="utf-8")):
            aus.setdefault(treffer, set()).add(rel)
    return aus


#: Eine gesetzte Registry für die Logik-Tests. Die echte ist (noch) leer —
#: prüfte man die Logik gegen sie, prüfte man nichts.
PROBE = {
    "alpha": Feature(key="alpha", description="Der erste Schalter zum Prüfen.",
                     fertig_wenn="Wenn die Probe nicht mehr gebraucht wird."),
    "beta-zwei": Feature(key="beta-zwei", description="Der zweite Schalter zum Prüfen.",
                         fertig_wenn="Wenn die Probe nicht mehr gebraucht wird."),
}


@pytest.fixture
def probe(monkeypatch):
    monkeypatch.setattr("kern.features.FEATURES", PROBE)
    return PROBE


def test_jeder_schluessel_passt_zu_seinem_eintrag():
    for key, f in FEATURES.items():
        assert f.key == key, f"{key!r} trägt intern den Schlüssel {f.key!r}"


def test_namen_sind_kleingeschrieben_und_mit_bindestrich():
    """Ein Name reist durch `.env`, JSON und TypeScript. Alles außer
    Kleinbuchstaben, Ziffern und Bindestrich lädt zu Verwechslungen ein."""
    for key in FEATURES:
        assert re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", key), (
            f"{key!r} — erlaubt sind Kleinbuchstaben, Ziffern und Bindestriche.")


def test_jeder_schalter_sagt_wann_er_weg_kann():
    """Ohne diese Angabe bleibt jeder Schalter für immer stehen."""
    for key, f in FEATURES.items():
        assert len(f.description) > 20, f"{key}: keine brauchbare Beschreibung"
        assert len(f.fertig_wenn) > 20, (
            f"{key}: `fertig_wenn` fehlt. Ein Schalter ist eine Schuld — es "
            "muss dastehen, woran man erkennt, dass er weg kann.")


def test_ein_unbekannter_name_wird_verworfen_statt_durchgereicht(probe):
    """Sonst schaltete ein Tippfehler in der `.env` etwas frei, das es nicht
    gibt — und der Unterschied zu \u201eist eben aus\u201c wäre unsichtbar."""
    assert aktive("gibtesnicht") == []
    assert aktive("gibtesnicht,alpha") == ["alpha"]


def test_leerraum_und_leere_eintraege_stoeren_nicht(probe):
    assert aktive("") == []
    assert aktive(" , , ") == []
    assert aktive("  alpha  ") == ["alpha"]


def test_die_reihenfolge_folgt_der_registry_nicht_der_env(probe):
    """Damit die Antwort von `/api/app-config` stabil ist und als
    Cache-Schlüssel taugt."""
    assert aktive("beta-zwei,alpha") == ["alpha", "beta-zwei"]


def test_an_und_aktive_sagen_dasselbe(probe):
    assert an("alpha", "alpha") is True
    assert an("alpha", "beta-zwei") is False
    assert an("alpha", "") is False


def test_die_registry_darf_leer_sein_und_liefert_dann_nichts():
    """Der Auslieferungszustand: Mechanik da, kein Schalter an."""
    assert aktive("irgendwas") == []


@pytest.mark.parametrize("name", sorted(_verwendete_namen()) or ["(keiner)"])
def test_jeder_im_frontend_benutzte_schalter_steht_in_der_registry(name: str):
    if name == "(keiner)":
        pytest.skip("Das Frontend benutzt noch keinen Schalter.")
    verwendung = _verwendete_namen()[name]
    assert name in FEATURES, (
        f"`{name}` wird in {sorted(verwendung)} gelesen, steht aber nicht in "
        "`kern/features.py`. Ein Name, den die Registry nicht kennt, wird von "
        "`aktive()` verworfen — der Schalter ist damit DAUERHAFT AUS, und das "
        "sieht aus wie \u201enoch nicht angeschaltet\u201c.")


def test_kein_schalter_ohne_nutzung():
    """Die zweite Richtung: Ein Schalter, den niemand mehr liest, ist erledigt.

    Er steht dann noch in der `.env` und in dieser Registry, schaltet aber
    nichts — und beim nächsten Lesen fragt sich jemand, was er tut.
    """
    verwendet = set(_verwendete_namen())
    unbenutzt = sorted(set(FEATURES) - verwendet)
    assert not unbenutzt, (
        f"Diese Schalter liest niemand mehr: {unbenutzt}. Wenn das Feature "
        "steht, gehört der Schalter raus — aus `kern/features.py`, aus der "
        "`.env` und aus der Oberfläche. Wenn es noch nicht steht, fehlt die "
        "Verwendung.")
