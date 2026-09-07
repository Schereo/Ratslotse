"""Wahlabend: Sitzzuteilung, Votemanager-Anbindung und Hochrechnung zur Ratswahl.

Der Bereich hat keine Datenbank und keinen Cron. Er liest die Open-Data-CSVs
des Votemanagers der Stadt (60-s-Cache), rechnet die Sitze nach NKWG nach und
liefert ein fertiges Bild für ``GET /api/wahlabend``.
"""
