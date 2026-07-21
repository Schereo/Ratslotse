"""Sitzungspausen des Oldenburger Rats erkennen und erklären.

Der Rat tagt laut Stadt „in der Regel einmal im Monat" und: „In den
Schulferien finden keine Sitzungen statt."
(oldenburg.de → Politik → Rat & Fraktionen → Ratssitzungen)

Unsere eigene Sitzungshistorie seit 2018 bestätigt das Muster: Jede Lücke
über drei Wochen deckt sich mit niedersächsischen Schulferien (plus Corona
im Frühjahr 2020). Im Wahljahr 2021 ging es exakt am letzten Ferientag
weiter (Sommerferien bis 01.09. → erste Sitzung 01.09.); nach dem Ende der
Wahlperiode (31.10.) konstituierte sich der neue Rat am 22.11.2021.

Die Ferientermine legt das Nds. Kultusministerium Jahre im Voraus fest
(aktuell bis Schuljahr 2029/30). Die Tabelle unten enthält die verifizierten
Fenster; läuft sie aus, verschwindet nur die konkrete Bis-Angabe — die
generische Erklärung („keine kommenden Termine veröffentlicht") bleibt.
Winterferien (2 Tage) fehlen bewusst: zu kurz für eine spürbare Pause.

Kommunalwahl 2026: Wahltag 13.09.2026 (Stichwahlen 27.09.), die laufende
Wahlperiode endet am 31.10.2026, die neue beginnt am 01.11.2026 (NKomVG).
"""
from __future__ import annotations

from datetime import date, timedelta

# (von, bis, Anzeige-Name) — jeweils erster und letzter Ferientag,
# Niedersachsen, wie vom Kultusministerium festgelegt.
FERIEN: list[tuple[date, date, str]] = [
    (date(2026, 7, 2), date(2026, 8, 12), "Sommerpause"),
    (date(2026, 10, 12), date(2026, 10, 24), "Herbstpause"),
    (date(2026, 12, 23), date(2027, 1, 9), "Weihnachtspause"),
    (date(2027, 3, 22), date(2027, 4, 3), "Osterpause"),
    (date(2027, 5, 7), date(2027, 5, 18), "Pfingstpause"),
    (date(2027, 7, 8), date(2027, 8, 18), "Sommerpause"),
]

# Übergangsfenster der Kommunalwahl 2026: vom Ende der Sommerferien bis zur
# erwarteten Konstituierung des neuen Rats (2021: 22. November).
WAHL_2026 = {
    "start": date(2026, 8, 13),
    "ende": date(2026, 11, 30),
    "wahltag": date(2026, 9, 13),
    "periodenende": date(2026, 10, 31),
}


def _fmt(d: date) -> str:
    return f"{d.day}.{d.month}.{d.year}"


def sitzungspause(today: date, next_session_date: date | None) -> dict:
    """Pausen-Status für die Übersicht.

    ``next_session_date`` ist die nächste im Ratsinfo veröffentlichte Sitzung
    (oder None). Gibt ein dict mit ``active``, ``label``, ``until`` (ISO oder
    None), ``next_session_date`` (ISO oder None) und ``note`` (fertiger
    Erklärtext) zurück. ``active=False`` → kein Banner.
    """
    ferien = next(((von, bis, name) for von, bis, name in FERIEN
                   if von <= today <= bis), None)
    wahl = WAHL_2026["start"] <= today <= WAHL_2026["ende"]

    # Künftige Sitzungen bekannt und keine Ferien → Betrieb läuft normal.
    if next_session_date and not ferien:
        return {"active": False, "label": None, "until": None,
                "next_session_date": next_session_date.isoformat(), "note": ""}

    if ferien:
        von, bis, name = ferien
        if next_session_date:
            note = (f"Der Rat pausiert in den Schulferien — so hält es die Stadt "
                    f"grundsätzlich. Weiter geht es am {_fmt(next_session_date)}.")
        else:
            note = (f"Der Rat und seine Ausschüsse pausieren in den Schulferien — "
                    f"so hält es die Stadt grundsätzlich. Die Ferien enden am "
                    f"{_fmt(bis)}; neue Sitzungstermine erscheinen erfahrungsgemäß "
                    f"kurz danach im Ratsinformationssystem.")
        if name == "Sommerpause" and today.year == 2026:
            note += (f" Besonderheit 2026: Am {_fmt(WAHL_2026['wahltag'])} ist "
                     f"Kommunalwahl — danach endet die Wahlperiode des aktuellen "
                     f"Rats am {_fmt(WAHL_2026['periodenende'])}, und der neu "
                     f"gewählte Rat startet im November.")
        return {"active": True, "label": name, "until": bis.isoformat(),
                "next_session_date": next_session_date.isoformat() if next_session_date else None,
                "note": note}

    if wahl and not next_session_date:
        note = (f"Am {_fmt(WAHL_2026['wahltag'])} ist Kommunalwahl. Die Wahlperiode "
                f"des aktuellen Rats endet am {_fmt(WAHL_2026['periodenende'])}; der "
                f"neu gewählte Rat konstituiert sich im November (beim letzten Mal "
                f"am 22.11.2021). Bis dahin tagen die Gremien seltener — neue "
                f"Termine erscheinen hier, sobald die Stadt sie veröffentlicht.")
        return {"active": True, "label": "Kommunalwahl & Ratswechsel",
                "until": WAHL_2026["ende"].isoformat(),
                "next_session_date": None, "note": note}

    if not next_session_date:
        # Kein bekanntes Fenster, aber auch keine Termine — ehrlich bleiben,
        # nichts behaupten (könnte auch schlicht noch nicht veröffentlicht sein).
        return {"active": True, "label": "Keine Termine veröffentlicht",
                "until": None, "next_session_date": None,
                "note": ("Im Ratsinformationssystem sind derzeit keine kommenden "
                         "Sitzungen veröffentlicht. Neue Termine erscheinen hier "
                         "automatisch, sobald die Stadt sie einstellt.")}

    return {"active": False, "label": None, "until": None,
            "next_session_date": next_session_date.isoformat(), "note": ""}


def naechste_ferien(today: date) -> tuple[date, date, str] | None:
    """Das nächste (oder laufende) Ferienfenster — für Tests/Debug."""
    upcoming = [(von, bis, name) for von, bis, name in FERIEN if bis >= today]
    return min(upcoming, default=None)


def resume_hint(today: date) -> date | None:
    """Frühester Tag, ab dem nach der aktuellen Pause wieder Sitzungen zu
    erwarten sind (Ferienende + 1 Tag); None außerhalb von Ferien."""
    for von, bis, _ in FERIEN:
        if von <= today <= bis:
            return bis + timedelta(days=1)
    return None
