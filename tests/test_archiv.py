"""Aus dem Statistik-Archiv lesen (``council/archiv.py``).

Das Schreiben prüft ``tests/test_archive_statistik.py`` — hier geht es um die
andere Richtung, die es seit 08/2026 gibt: Parser holen sich aus dem Archiv,
was live nicht mehr steht.

Der Fall, für den es gebaut ist: **Tabelle 1103 führt nur drei Jahrgänge.**
Jede neue Ausgabe schiebt den ältesten heraus, und die Stadt hält keine alten
Ausgaben online (``1103-2024-AZ.pdf`` antwortet mit 404, nachgemessen am
17.08.2026). Weil der Dateiname den Jahrgang trägt, ist jede Ausgabe ein
eigener Ordner — wer alle liest, hat mehr als drei Jahre.
"""
from __future__ import annotations

from datetime import date

from council import archiv


def _ablegen(wurzel, name: str, inhalt: bytes, tag: str) -> None:
    archiv.version_ablegen(wurzel, "jahrbuch", name, inhalt,
                           date.fromisoformat(tag))


def test_fassungen_kommen_in_zeitlicher_reihenfolge(tmp_path):
    """Sortiert wird über den Dateinamen — er beginnt mit dem ISO-Datum.

    Kein ``mtime``: Der überlebt weder ein ``rsync``-Deployment noch eine
    Wiederherstellung aus dem Backup, und dann stünde die falsche Fassung am
    Ende."""
    _ablegen(tmp_path, "1103-2025-AZ.pdf", b"zweite", "2026-08-17")
    _ablegen(tmp_path, "1103-2025-AZ.pdf", b"erste", "2025-09-01")
    _ablegen(tmp_path, "1103-2025-AZ.pdf", b"dritte", "2026-11-02")
    fassungen = archiv.fassungen(tmp_path, "jahrbuch", "1103-2025-AZ.pdf")
    assert [p.read_bytes() for p in fassungen] == [b"erste", b"zweite", b"dritte"]
    assert archiv.neueste(tmp_path, "jahrbuch", "1103-2025-AZ.pdf").read_bytes() \
        == b"dritte"


def test_je_ausgabe_ihre_neueste_fassung(tmp_path):
    """Der eigentliche Lesepfad: **eine Datei je Jahrgang**, nicht eine einzige.

    Drei Ausgaben, von denen zwei nachgebessert wurden — heraus kommen drei
    Dateien, und zwar die jeweils letzte."""
    for name, fassungen in (
            ("1103-2024-AZ.pdf", [("2024-09-02", b"24-alt"), ("2024-11-05", b"24-neu")]),
            ("1103-2025-AZ.pdf", [("2025-08-30", b"25")]),
            ("1103-2026-AZ.pdf", [("2026-08-17", b"26-alt"), ("2026-08-19", b"26-neu")])):
        for tag, inhalt in fassungen:
            _ablegen(tmp_path, name, inhalt, tag)
    gefunden = archiv.neueste_je_datei(tmp_path, "jahrbuch", "1103-*.pdf")
    assert [p.read_bytes() for p in gefunden] == [b"24-neu", b"25", b"26-neu"]
    # Älteste Ausgabe zuerst: Wer die Reihen in dieser Reihenfolge
    # zusammenlegt, lässt die jüngere gewinnen — und die trägt die revidierten
    # Werte.
    assert [p.parent.name for p in gefunden] == [
        "1103-2024-AZ.pdf", "1103-2025-AZ.pdf", "1103-2026-AZ.pdf"]


def test_das_muster_trennt_die_tabellen_voneinander(tmp_path):
    """Im selben Ordner liegen alle Jahrbuch-Tabellen nebeneinander.

    ``1103-*.pdf`` darf weder 1102 noch das Blatt 1104-1105 mitnehmen — beide
    beginnen mit derselben Ziffernfolge oder enthalten sie."""
    for name in ("1102-2025-AZ.pdf", "1103-2025-AZ.pdf", "1104-1105-2025-AZ.pdf",
                 "1108-2025-AZ.pdf"):
        _ablegen(tmp_path, name, name.encode(), "2026-08-17")
    assert [p.parent.name for p in
            archiv.neueste_je_datei(tmp_path, "jahrbuch", "1103-*.pdf")] \
        == ["1103-2025-AZ.pdf"]
    assert [p.parent.name for p in
            archiv.neueste_je_datei(tmp_path, "jahrbuch", "1104-1105-*.pdf")] \
        == ["1104-1105-2025-AZ.pdf"]


def test_ein_leeres_archiv_ist_kein_fehler(tmp_path):
    """Auf einer frisch geklonten Maschine und in der CI gibt es kein Archiv.

    Die Aufrufer fallen dann auf den Live-Download zurück und sagen das — ein
    Absturz wäre die falsche Antwort auf einen Normalfall."""
    assert archiv.neueste_je_datei(tmp_path, "jahrbuch", "1103-*.pdf") == []
    assert archiv.fassungen(tmp_path, "jahrbuch", "gibtsnicht.pdf") == []
    assert archiv.neueste(tmp_path, "jahrbuch", "gibtsnicht.pdf") is None
    assert archiv.herkunft_der_fassung(tmp_path, tmp_path / "x.pdf") == {}


def test_die_herkunft_einer_fassung_nennt_die_original_adresse(tmp_path):
    """Ein Beleg zeigt auf die Adresse der Stadt, nicht auf unseren Dateipfad."""
    url = ("https://www.oldenburg.de/fileadmin/oldenburg/Benutzer/Dateien/"
           "40_Stadtplanungsamt/402_Geo_und_Daten/Statistik/1103-2025-AZ.pdf")
    pfad, neu = archiv.version_ablegen(
        tmp_path, "jahrbuch", "1103-2025-AZ.pdf", b"inhalt",
        date(2026, 8, 17))
    assert neu is True
    archiv.manifest_schreiben(tmp_path, {url: {
        "bereich": "jahrbuch", "datei": "1103-2025-AZ.pdf",
        "pfad": str(pfad.relative_to(tmp_path)),
        "zuerst_gesehen": "2026-08-17", "zuletzt_gesehen": "2026-08-18"}})
    gefunden = archiv.herkunft_der_fassung(tmp_path, pfad)
    assert gefunden["url"] == url
    assert gefunden["zuerst_gesehen"] == "2026-08-17"


def test_ohne_manifest_bleibt_wenigstens_das_datum(tmp_path):
    """Ein Archiv ohne sein Inhaltsverzeichnis ist kein Haufen Hashes: Der
    Tag, an dem wir eine Fassung zuerst gesehen haben, steht im Dateinamen."""
    pfad, _ = archiv.version_ablegen(tmp_path, "jahrbuch", "1103-2025-AZ.pdf",
                                     b"inhalt", date(2026, 8, 17))
    assert archiv.herkunft_der_fassung(tmp_path, pfad) == {
        "zuerst_gesehen": "2026-08-17"}


def test_derselbe_inhalt_wird_nicht_zweimal_abgelegt(tmp_path):
    """Die Idempotenz-Zusage hängt am Inhalt, nicht am Datum — auch beim
    Lesen sichtbar: Ein zweiter Lauf am nächsten Tag verlängert die Liste der
    Fassungen nicht."""
    _ablegen(tmp_path, "1103-2025-AZ.pdf", b"gleich", "2026-08-17")
    _, neu = archiv.version_ablegen(tmp_path, "jahrbuch", "1103-2025-AZ.pdf",
                                    b"gleich", date(2026, 8, 18))
    assert neu is False
    assert len(archiv.fassungen(tmp_path, "jahrbuch", "1103-2025-AZ.pdf")) == 1
