"""Die Aufbewahrung der Sicherungen — sieben Tage fein, vier Wochen grob.

**Der Fehler, gegen den das steht.** Bis 09/2026 behielt `backup_db.py` je
Datenbank die letzten sieben Kopien. Ein Schaden, der erst nach acht Tagen
auffiel, war damit endgültig — und weil gelöscht wurde, was alphabetisch vorn
stand, warfen zwei Handkopien vom August (`council_pre_location_…`) zwei der
sieben Tagesstände hinaus, ohne dass es jemand sah: Auf Prod lagen am
03.09.2026 nur fünf Tagesstände von `council`, aber sieben von `nwz`.

Die Tests prüfen deshalb nicht die Formel, sondern das Ergebnis über simulierte
Monatsläufe: Wie weit reicht der Bestand nach 60 Tagen zurück, was passiert bei
Cron-Ausfällen, und fassen Handkopien wirklich niemanden an.
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.backup_db import TAEGLICH, WOECHENTLICH, rotation, sicherungsdatum  # noqa: E402

STAMM = "council"


def _lauf(ordner: Path, tage: list[date], stamm: str = STAMM) -> list[date]:
    """Spielt die Sicherungen Tag für Tag durch und gibt den Endbestand zurück.

    Wichtig ist das *Tag für Tag*: Die Rotation läuft nach jeder einzelnen
    Sicherung, nicht einmal am Ende über den ganzen Vorrat. Nur so zeigt sich,
    ob ein Stand, den ein früherer Lauf behalten hat, später doch noch
    weggeräumt wird.
    """
    for tag in tage:
        (ordner / f"{stamm}_{tag.isoformat()}.sqlite").write_bytes(b"x")
        _, veraltet = rotation(ordner.glob(f"{stamm}_*.sqlite"), stamm)
        for pfad in veraltet:
            pfad.unlink()
    return sorted(d for p in ordner.glob(f"{stamm}_*.sqlite")
                  if (d := sicherungsdatum(p, stamm)))


def test_der_bestand_reicht_einen_monat_zurueck():
    """Nach zwei Monaten täglicher Läufe: 11 Stände, ältester ≥ 28 Tage alt.

    Der Test läuft über JEDEN Starttag einer Woche — die Abdeckung hängt davon
    ab, wie das Sieben-Tage-Fenster in den Kalender fällt, und genau dieser
    Wochentags-Effekt war der Grund für die vierte Wochenmarke.
    """
    import tempfile

    for versatz in range(7):
        with tempfile.TemporaryDirectory() as tmp:
            ordner = Path(tmp)
            start = date(2026, 1, 5) + timedelta(days=versatz)   # 05.01. = Montag
            tage = [start + timedelta(days=i) for i in range(60)]
            bestand = _lauf(ordner, tage)

            assert len(bestand) == TAEGLICH + WOECHENTLICH, (versatz, bestand)
            spanne = (bestand[-1] - bestand[0]).days
            assert spanne >= 28, f"Start {start}: nur {spanne} Tage Abdeckung"
            assert spanne <= 35, f"Start {start}: {spanne} Tage — mehr als geplant"

            # Die sieben jüngsten liegen lückenlos hintereinander.
            assert bestand[-TAEGLICH:] == [tage[-1] - timedelta(days=i)
                                           for i in reversed(range(TAEGLICH))]
            # Und kein Loch größer als eine Woche im groben Teil.
            luecken = [(b - a).days for a, b in zip(bestand, bestand[1:])]
            assert max(luecken) <= 8, (versatz, luecken)


def test_handkopien_werden_nie_angefasst_und_verdraengen_nichts(tmp_path):
    """Der Prod-Fund vom 03.09.2026 — zwei Handkopien, zwei fehlende Tagesstände."""
    hand = [
        tmp_path / "council_pre_location_backfill_2026-08-26.sqlite",
        tmp_path / "council_vor_release_v2.0.0.sqlite",
    ]
    for pfad in hand:
        pfad.write_bytes(b"hand")

    tage = [date(2026, 8, 1) + timedelta(days=i) for i in range(30)]
    bestand = _lauf(tmp_path, tage)

    assert all(pfad.exists() for pfad in hand), "Handkopie weggeräumt"
    assert len(bestand) == TAEGLICH + WOECHENTLICH, "Handkopie hat einen Platz gekostet"
    assert sicherungsdatum(hand[0], STAMM) is None
    assert sicherungsdatum(hand[1], STAMM) is None


def test_ein_cron_ausfall_verkuerzt_den_bestand_nicht(tmp_path):
    """Fällt der Job eine Woche aus, bleiben die sieben jüngsten Stände stehen —
    sie decken dann eben mehr Kalendertage ab. Der Bestand darf durch einen
    Ausfall nicht ZUSÄTZLICH schrumpfen."""
    tage = [date(2026, 2, 1) + timedelta(days=i) for i in range(43)]    # bis 15.03.
    tage += [date(2026, 3, 23) + timedelta(days=i) for i in range(3)]   # 7 Tage Lücke
    bestand = _lauf(tmp_path, tage)

    assert len(bestand) == TAEGLICH + WOECHENTLICH
    assert bestand[-3:] == tage[-3:]
    # Die Lücke steckt IM Tagesfenster, die Abdeckung wird dadurch größer,
    # nicht kleiner — verloren geht nichts.
    assert (bestand[-1] - bestand[0]).days >= 28


def test_wiederholter_lauf_loescht_nichts_mehr(tmp_path):
    """Zweimal dieselbe Rotation über denselben Ordner: beim zweiten Mal bleibt
    die Löschliste leer. Sonst wanderte der Bestand mit jedem Aufruf weiter."""
    for tag in (date(2026, 5, 1) + timedelta(days=i) for i in range(45)):
        (tmp_path / f"{STAMM}_{tag.isoformat()}.sqlite").write_bytes(b"x")

    _, veraltet = rotation(tmp_path.glob(f"{STAMM}_*.sqlite"), STAMM)
    for pfad in veraltet:
        pfad.unlink()
    assert veraltet

    _, nochmal = rotation(tmp_path.glob(f"{STAMM}_*.sqlite"), STAMM)
    assert nochmal == []


def test_wenig_daten_werden_gar_nicht_geloescht(tmp_path):
    """Frische Installation: weniger Stände als das Tagesfenster — nichts fliegt."""
    for tag in (date(2026, 6, 1) + timedelta(days=i) for i in range(3)):
        (tmp_path / f"{STAMM}_{tag.isoformat()}.sqlite").write_bytes(b"x")

    behalten, veraltet = rotation(tmp_path.glob(f"{STAMM}_*.sqlite"), STAMM)
    assert len(behalten) == 3 and veraltet == []


def test_fremde_namen_gehoeren_nicht_zu_diesem_stamm(tmp_path):
    """`council_…` und `nwz_…` dürfen sich nicht gegenseitig zählen, und ein
    Datum, das keines ist, macht die Datei zur Handkopie statt zum Fehler."""
    assert sicherungsdatum(tmp_path / "nwz_2026-09-03.sqlite", STAMM) is None
    assert sicherungsdatum(tmp_path / "council_2026-09-03.sqlite", STAMM) == date(2026, 9, 3)
    assert sicherungsdatum(tmp_path / "council_2026-13-45.sqlite", STAMM) is None
    assert sicherungsdatum(tmp_path / "council_2026-09-03.sqlite.bak", STAMM) is None
