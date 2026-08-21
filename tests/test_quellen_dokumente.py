"""Kein Beleg darf auf der Startseite enden.

DER BEFUND, DER DIESE DATEI ERZWUNGEN HAT (Tim, 21.08.2026). Auf
`/haushalt/betriebe` standen 33 Wirtschaftspläne aus sieben Eigenbetrieben,
und darunter genau eine Quellenangabe, deren Link auf
``https://buergerinfo.oldenburg.de`` führte:

    „Das führt mich zum Ratsinformationssystem, aber zu keinem Dokument, zu
    keiner Suche, zu gar nichts."

Der Apparat konnte es längst besser. ``CouncilStore._DOKUMENT_QUELLEN``
schlägt je Quelle und Jahrgang das konkrete PDF nach, und dreizehn Quellen
nutzten das auch. Die drei Schichten vom 20.08.2026 — Wirtschaftspläne,
Haushaltssatzung, Gebührenbedarfsberechnung — waren dort schlicht nicht
eingetragen. Sichtbar wurde das nirgends: Die Seite baute, der Chip erschien,
der Link führte ins Nichts. Genau die Art Fehler, gegen die eine Prüfung hilft
und ein Blick nicht.

Die Regel ist deshalb bewusst eng an dem formuliert, was schiefging: **Eine
Quelle, die ein Dokument meint, muss zu einem Dokument führen.** Die
Startseite des Ratsinformationssystems ist kein Dokument.

Nicht geprüft wird, ob jede Tabelle mit ``herkunft_id`` als Quelle
registriert ist — 45 tragen die Spalte, und die Mehrzahl davon meint zu Recht
kein eigenes Papier (verworfene Zeilen, Untertabellen, Rechenwege). Eine
Prüfung mit siebzehn Ausnahmen prüft nichts mehr, sie verwaltet nur noch ihre
Ausnahmen.
"""
from __future__ import annotations

import re
from pathlib import Path

from council.store import CouncilStore

ROOT = Path(__file__).resolve().parents[1]
QUELLEN_TS = ROOT / "web" / "frontend" / "lib" / "haushalt-quellen.ts"

#: Adressen, die nichts belegen: die Startseite des Ratsinformationssystems,
#: mit und ohne Schrägstrich.
STARTSEITEN = {
    "https://buergerinfo.oldenburg.de",
    "https://buergerinfo.oldenburg.de/",
}

#: Quellen, die diese Adresse zu Recht tragen — mit dem Grund im Klartext.
#:
#: ``ratsbeschluss`` ist keine Papierquelle, sondern das System selbst: der
#: Weg einer Vorlage durch Sitzungen und Gremien. Es GIBT dort kein einzelnes
#: Dokument, auf das eine Gesamtadresse zeigen könnte — die einzelnen
#: Stationen verlinken die Seiten je Zeile auf ihren Eintrag. Wer hier eine
#: Ausnahme ergänzt, schreibt den Grund dazu; „geht gerade nicht" ist keiner.
OHNE_DOKUMENT = {
    "ratsbeschluss": "Das Ratsinformationssystem als System, nicht als Papier — "
                     "die einzelnen Stationen verlinken die Seiten je Zeile.",
}


def _statische_adressen() -> dict[str, str]:
    """Je Quellenschlüssel die fest eingetragene Adresse aus dem Frontend.

    Ein Regex und kein Node-Lauf: Gebraucht wird ein Feld je Eintrag, und die
    Prüfung soll auch dort laufen, wo die CI nur Python einrichtet."""
    text = QUELLEN_TS.read_text(encoding="utf-8")
    # Die Einträge stehen auf zwei Ebenen Einrückung im QUELLEN-Objekt; ein
    # Eintrag endet an der schließenden Klammer in derselben Einrückung.
    aus: dict[str, str] = {}
    for block in re.finditer(r"^  (\w+): \{(.*?)^  \},", text, re.S | re.M):
        adresse = re.search(r'\burl:\s*"([^"]+)"', block.group(2))
        if adresse:
            aus[block.group(1)] = adresse.group(1)
    return aus


def test_quellenverzeichnis_gelesen():
    """Die Voraussetzung der Prüfung selbst — sonst prüft sie ein leeres dict.

    Ein Regex über fremde Syntax kann still nichts finden, und dann wäre diese
    Datei ein grüner Haken ohne Inhalt (dieselbe Falle wie eine Zusicherung,
    die auf einer leeren Liste trivial zutrifft)."""
    adressen = _statische_adressen()
    assert len(adressen) >= 25, (
        f"Nur {len(adressen)} Quellen gelesen — das Muster passt nicht mehr "
        f"auf {QUELLEN_TS.name}.")


def test_keine_quelle_endet_auf_der_startseite():
    """Jede Papierquelle führt zu einem Papier."""
    adressen = _statische_adressen()
    mit_dokumenten = set(CouncilStore._DOKUMENT_QUELLEN)  # noqa: SLF001

    blind = sorted(
        key for key, url in adressen.items()
        if url in STARTSEITEN
        and key not in mit_dokumenten
        and key not in OHNE_DOKUMENT
    )
    assert not blind, (
        "Diese Quellen zeigen auf die Startseite des Ratsinformationssystems "
        f"und haben keine Dokumente je Jahrgang: {', '.join(blind)}.\n"
        "Entweder in CouncilStore._DOKUMENT_QUELLEN eintragen (Tabelle, "
        "Jahresspalte, Filter, Alt-URL) — dann liefert /haushalt/dokumente das "
        "PDF je Jahrgang —, oder in OHNE_DOKUMENT mit einem Grund."
    )


def test_ausnahmen_gelten_noch():
    """Eine Ausnahme, die keine mehr ist, gehört weg.

    Ohne diese Prüfung sammelt ``OHNE_DOKUMENT`` Einträge, die längst
    Dokumente haben — und die nächste Schicht schlüpft unter dem Vorwand
    durch, dass „das schon immer so stand"."""
    adressen = _statische_adressen()
    mit_dokumenten = set(CouncilStore._DOKUMENT_QUELLEN)  # noqa: SLF001
    for key in OHNE_DOKUMENT:
        assert key in adressen, f"{key} steht gar nicht mehr in den Quellen."
        assert key not in mit_dokumenten, (
            f"{key} hat inzwischen Dokumente je Jahrgang — die Ausnahme in "
            "OHNE_DOKUMENT ist überflüssig geworden.")


def test_dokument_quellen_kennen_ihre_tabellen():
    """Jeder Eintrag zeigt auf eine Tabelle und Spalte, die es gibt.

    ``haushalt_dokumente`` fängt ``OperationalError`` ab und überspringt den
    Schlüssel — richtig zur Laufzeit (eine frische Datenbank hat noch nicht
    jede Tabelle), aber es macht einen Tippfehler unsichtbar: Die Quelle fiele
    still auf die Startseite zurück, also genau dorthin, wo sie herkommt."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        store = CouncilStore(Path(tmp) / "council.sqlite")
        try:
            for key, (tabelle, jahrspalte, _, alt) in \
                    CouncilStore._DOKUMENT_QUELLEN.items():  # noqa: SLF001
                spalten = {r[1] for r in
                           store._conn.execute(f"PRAGMA table_info({tabelle})")}  # noqa: SLF001
                assert spalten, f"{key}: Tabelle {tabelle} gibt es nicht."
                assert jahrspalte in spalten, (
                    f"{key}: {tabelle} hat keine Spalte {jahrspalte}.")
                assert "herkunft_id" in spalten, (
                    f"{key}: {tabelle} trägt keine herkunft_id — ohne sie gibt "
                    "es weder Adresse noch Fundstelle.")
                if alt:
                    assert alt in spalten, (
                        f"{key}: {tabelle} hat keine Alt-URL-Spalte {alt}.")
        finally:
            store.close()
