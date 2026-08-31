"""Der Wächter gegen Oberflächen, die einen umbenannten Wert lesen.

Hintergrund: Der Umbau auf englische Bezeichner benennt gespeicherte Werte um
und trägt dafür ein Migrationspaar in ``council/store.py`` ein. Zieht das
Web-Frontend oder die App nicht nach, wird der Vergleich dort nie mehr wahr —
lautlos. Am 01.09.2026 standen so acht Stellen tot: die Entwurfs- und
Summenzeilen der Änderungslisten, die Reihenfolge der Verwaltungslisten, die
Einheit „Personen" der Kennzahlen, die Abweichungs-Fahne und die drei
Anwesenheitsrollen der Beschlussseite, der Ratsbeschluss-Kanal der
Nachbewilligungen und das Quiz-Gebiet „Thema" im Web wie in der App.

Keiner der 2.296 Tests hat davon etwas gemerkt, und das ist kein Versäumnis
einzelner Tests: Das Backend schreibt den neuen Wert, seine Fixtures kennen
nur den neuen Wert, die Frontend-Tests laufen gegen erfundene Daten, und für
TypeScript ist beides ``string``. Die Lücke liegt genau zwischen den Suiten —
deshalb prüft sie ein Skript über den Quelltext.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.pruefe_alte_werte import (  # noqa: E402
    ERLAUBT,
    ERLAUBT_STELLE,
    ERLAUBT_ZEILE,
    dateien,
    main,
    migrationspaare,
)


def test_keine_oberflaeche_liest_einen_umbenannten_wert():
    """Der eigentliche Wächter. Schlägt er an, nennt die Ausgabe Datei, Zeile
    und den neuen Namen — entweder eintragen oder mit Begründung erlauben."""
    assert main() == 0


def test_die_migrationspaare_werden_wirklich_gelesen():
    """Ohne Paare prüfte der Wächter nichts und wäre trotzdem grün.

    Die Paare stehen teils direkt im ``_werte_umschreiben``-Aufruf, teils in
    einer Listen-Konstante daneben (``ORTSARTEN``) — beide Formen müssen
    ankommen."""
    paare = migrationspaare()
    assert len(paare) > 80
    assert ("angenommen", "accepted") in paare       # direkt im Aufruf
    assert ("strasse", "street") in paare            # aus der Listen-Konstante
    assert all(alt != neu for alt, neu in paare)     # selbstgleich hilft nie


def test_er_schaut_in_beide_oberflaechen():
    """Der Befund vom 01.09. lag zur Hälfte im Web und zur Hälfte in der App."""
    pfade = {str(p) for p in dateien()}
    assert any("web/frontend/lib" in p for p in pfade)
    assert any("ios/Packages" in p for p in pfade)
    assert not any("node_modules" in p for p in pfade)


def test_jede_erlaubnis_traegt_eine_begruendung():
    """Die Erlaubtlisten sind die Dokumentation dessen, was bewusst deutsch
    bleibt. Ein Eintrag ohne Grund wäre nur ein stummgeschalteter Fund."""
    for wert, grund in ERLAUBT.items():
        assert len(grund) > 15, wert
    for stelle, grund in ERLAUBT_STELLE.items():
        assert len(grund) > 15, stelle
    # Ein Zeilen-Filter ohne Eintrag in ERLAUBT wirkt nie — das wäre ein
    # stiller Tippfehler.
    assert set(ERLAUBT_ZEILE) <= set(ERLAUBT)
