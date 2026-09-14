"""Ein Wochenlauf darf nicht den ganzen Bestand neu ziehen.

Gemessen an Hannover am 13.09.2026 mit einem Wochen-Fenster
(`--since 2026-09-06`): **4.083 Vorlagen geholt, davon 4.083 schon bekannt
und 0 neu.** Nach 35 Minuten war der Lauf bei einem Sechstel; ein
Wochen-Cron hätte jeden Sonntag 25.729 Seiten von der Stadt gezogen, um
nichts zu erfahren.

Das ist dieselbe Last, die zwei Tage zuvor Hildesheims ALLRIS umgeworfen
haben könnte — und es betraf alle drei HTML-Dialekte gleichzeitig.
"""
from __future__ import annotations

import inspect

import pytest

from council.cities.adapters import get_adapter
from council.cities.adapters._common import muss_geholt_werden

DIALEKTE = ("hannover_sim", "allris_classic", "allris4_html")


@pytest.mark.parametrize("dialekt", DIALEKTE)
def test_jeder_html_dialekt_fragt_vor_dem_abruf(dialekt):
    """Der Wächter: ohne die Frage holt der Dialekt wieder alles.

    Alle drei laufen über die Sitzungen der ROHABLAGE — nicht über die
    dieses Laufs. Ohne `muss_geholt_werden` ruft jeder von ihnen zu jedem
    Drucksachen-Verweis `get_text`, egal ob die Seite längst abgelegt ist.
    """
    quelle = inspect.getsource(get_adapter(dialekt).iter_papers)
    assert "muss_geholt_werden" in quelle, (
        f"{dialekt}.iter_papers holt wieder jede Vorlage bei jedem Lauf — "
        "bei Hannover 25.729 Abrufe je Woche, für null neue Erkenntnis.")
    assert "raw_ids(" in quelle and "raw_ids_since(" in quelle, (
        f"{dialekt} muss die beiden Mengen EINMAL je Lauf holen, nicht je "
        "Vorlage.")


def test_unbekanntes_wird_immer_geholt():
    """Sonst käme eine abgebrochene Ernte nie zu Ende.

    Hildesheim stand am 13.09.2026 bei 1.078 Vorlagen zu 1.089 Sitzungen —
    ein Rest, den nur ein neuer Lauf holen kann.
    """
    assert muss_geholt_werden(None, "sitzung/1", "vorlage/neu", set(), set())


def test_bekanntes_an_einer_unveraenderten_sitzung_bleibt_liegen():
    """Ändert sich die Sitzungsseite nicht, ändert sich ihre Vorlagenliste nicht."""
    assert not muss_geholt_werden(None, "sitzung/1", "vorlage/alt",
                                  {"vorlage/alt"}, set())


def test_bekanntes_an_einer_frischen_sitzung_wird_neu_geholt():
    """Dort hängt das Neue: eine nachgetragene Station, ein Ergebnis."""
    assert muss_geholt_werden(None, "sitzung/1", "vorlage/alt",
                              {"vorlage/alt"}, {"sitzung/1"})
