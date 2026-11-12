"""Antragserkennung an Anlagen (docs/plan-vorlagen-aufbereiten.md, PR 2)."""
import pytest

from council import vorlagen


@pytest.mark.parametrize("label", [
    "Änderungsantrag CDU Geschäftsordnung Rat 2.11.26", "Aenderungsantrag CDU Baumschutzsatzung",
    "Anderungsantrag VA Leitantrag", "Ergänzungsantrag SPD-Fraktion", "Zusatzantrag Grüne",
    "Dringlichkeitsantrag CDU Hauptsatzung", "Berichtsantrag FDP", "Fraktionsantrag BSW",
    "Beschlussantrag Baum- und Stadtgrünstrategie", "Verweisungsantrag Stadion an AFB",
    "Gegenantrag Linke", "Antrag CDU-Fraktion", "Anfrage der SPD",
])
def test_antraege_werden_erkannt(label):
    assert vorlagen.ist_antrag(label)


@pytest.mark.parametrize("label", [
    "Zuschussantrag Verein für Kinder", "Förderantrag 2026", "Genehmigungsantrag",
    "Anlage1antrag Bauvorhaben", "Lageplan", "Vorlage",
])
def test_antraege_dritter_bleiben_draussen(label):
    assert not vorlagen.ist_antrag(label)


def test_kopf_verraet_den_antrag():
    # Ö 13.2 am Rat 02.11.2026: Das Label sagt nichts, die erste Seite alles.
    label = "2026-10-31 Reduzierung Anzahl beratende Mitglieder"
    kopf = "Fraktion Bündnis 90/Die Grünen\nÄnderungsantrag zu TOP 13.2\n…"
    assert not vorlagen.ist_antrag(label)
    assert vorlagen.ist_antrag(label, kopf)
    assert vorlagen.ist_antrag(label, "Wir beantragen zur Vorlage 26/0796 folgende Änderung: …")
    # Nur der Kopf zählt, nicht ein Satz auf Seite 9.
    assert not vorlagen.ist_antrag(label, "x" * 2000 + " Änderungsantrag")
