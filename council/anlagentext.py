"""Wann der Text einer Anlage als gelesen gilt — und wie man eine nachlädt.

Zwei Wege laden Anlagen-PDFs: der Backfill (``scripts/backfill_anlagen_texte
.py``, Tausende am Stück) und der MCP-Server (``council/mcp_tools.py``, eine
auf Zuruf eines Agenten). Beide müssen dasselbe Urteil fällen — sonst gilt
dieselbe Anlage je nach Weg als „gelesen“ oder als Scan. Die Schwellen
standen bis 10/2026 im Skript und sind deshalb hierher gezogen; das Skript
importiert sie.
"""
from __future__ import annotations

from council.kontaktdaten import entfernen

MIN_TEXT = 200          # darunter gilt das PDF als Scan/Bild ('empty')

#: Mindestanteil echter Buchstaben. Darunter ist die Zeichenzuordnung der PDF
#: kaputt, und was herauskommt, ist kein Text.
#:
#: DER FALL, DER DIESE SCHWELLE ERZWUNGEN HAT: Der Schlussbericht des
#: Rechnungsprüfungsamts zum Jahresabschluss 2024 (Dokument 295296) liefert
#: 460.084 Zeichen — und **keinen einzigen Buchstaben**. Seine Schrift bringt
#: keine ToUnicode-Tabelle mit, deshalb extrahiert pypdf die Glyph-Nummern
#: („/1 /2 /3 …") und Kästchen. Ohne diese Prüfung stünden 460 KB Rauschen in
#: der Datenbank, im Volltextindex und damit in den Treffern der KI-Frage —
#: und der Bericht sähe aus, als sei er gelesen worden.
#:
#: 0,05 IST GEMESSEN, NICHT GEGRIFFEN: Über die 558 Anlagen mit Volltext liegt
#: der Median bei 0,69, das erste Perzentil bei 0,32. Unterhalb von 0,12 liegen
#: genau zwei Dokumente — die beiden kaputten. Die Schwelle hat also nach oben
#: den doppelten Abstand zum nächsten echten Dokument.
MIN_BUCHSTABEN = 0.05

#: Obergrenze je Anlage. Kappt Extrem-PDFs, damit ein einzelnes Gutachten die
#: Datenbank nicht aufbläht.
#:
#: WARUM 800.000 UND NICHT MEHR 400.000. Bei 400.000 endeten die
#: Jahresabschlüsse mitten im Dokument — und zwar ausgerechnet vor Abschnitt 8
#: („Anlagen zum Anhang" mit Anlagen-, Forderungs-, Schulden- und
#: Rückstellungsübersicht). Für 2022 ließ sich das nachweisen: Die Abschnitte
#: 8.3 und 8.4 stehen bei 70 % des Textes, der Schnitt lag bei 56 %.
#:
#: Der Preis ist klein, weil die Grenze fast niemanden trifft: Von 6.366
#: Anlagen mit Volltext standen **23** exakt an ihr, davon acht die
#: Jahresabschlüsse (gemessen 18.08.2026). Die längste ist der Abschluss 2022
#: mit 709.076 Zeichen; 800.000 nimmt sie vollständig auf und lässt Luft für
#: einen dickeren Jahrgang, ohne dass jemand die Zahl wieder anfassen muss.
#: In einer 263-MB-Datenbank kostet das rund 7 MB.
MAX_TEXT = 800_000


def buchstabenanteil(text: str) -> float:
    """Wie viel des Textes wirklich aus Buchstaben besteht (0 bis 1)."""
    return sum(ch.isalpha() for ch in text) / len(text) if text else 0.0


def beurteilen(text: str | None) -> str:
    """Der Text, wie er gespeichert wird — oder ``""``, wenn das PDF als
    Scan bzw. kaputte Zeichenzuordnung gilt (Status ``empty``).

    Kontonummern und Anschriften fallen schon hier heraus (``entfernen``):
    Was beim Speichern gestrichen ist, kann kein späterer Weg ausgeben."""
    t = entfernen((text or "").strip())[:MAX_TEXT]
    if t and buchstabenanteil(t) < MIN_BUCHSTABEN:
        return ""
    return t if len(t) >= MIN_TEXT else ""
