"""Bis wann gilt eine Sitzung als „läuft gerade"?

Zwei Regeln, in dieser Reihenfolge:

1. **Die nächste Sitzung desselben Tages beendet die vorige.** An Ratstagen
   tagen drei Gremien nacheinander im selben Haus — 16:00 Ausschuss für
   Allgemeine Angelegenheiten, 16:30 Verwaltungsausschuss, 18:00 Rat. Es sind
   weitgehend dieselben Leute, die beiden Ausschüsse sitzen sogar im selben
   Raum; sie warten aufeinander und tagen nicht parallel (Tims Befund
   31.08.2026). Wer anfängt, beendet damit die vorige Runde.

2. **Sonst ein Deckel ab Beginn.** Wann eine Sitzung endet, veröffentlicht das
   Ratsinformationssystem nirgends — der Deckel ist eine Schätzung, und die
   fällt je nach Gremium anders aus: Ausschüsse sind nach rund drei Stunden
   durch, der Rat zieht sich länger (Tims Maß 31.08.2026).

Die Rechnung gehört in den Server, nicht in die Clients: Es gibt drei
Anzeigen dafür (Web-Übersicht, Startseiten-Leiste, Sitzungsliste) plus die
iOS-App, und ein Maß, das an vier Stellen liegt, driftet auseinander, sobald
es jemand nachzieht. Die Clients bekommen mit ``live_until`` einen fertigen
Zeitpunkt und vergleichen nur noch mit ihrer Uhr — die kennt der Server nicht.
"""
from __future__ import annotations

#: Deckel ab Sitzungsbeginn in Stunden, wenn an dem Tag keine weitere folgt.
CAP_HOURS = 3
CAP_HOURS_COUNCIL = 4

#: „Der Rat" selbst. Exakter Abgleich (klein/getrimmt): „Ortsrat", „Beirat"
#: und „Integrationsbeirat" enthalten ebenfalls „rat", und der
#: Verwaltungsausschuss ist zwar Hauptausschuss des Rates, tagt aber kurz —
#: er bekommt denselben Deckel wie die Fachausschüsse.
_COUNCIL_NAMES = frozenset({"rat", "stadtrat", "rat der stadt", "rat der stadt oldenburg"})


def is_council(committee: str | None) -> bool:
    """Ist das die Ratssitzung (nicht Ausschuss, Ortsrat oder Beirat)?"""
    return (committee or "").strip().lower() in _COUNCIL_NAMES


def cap_hours(committee: str | None) -> int:
    """Wie lange läuft eine Sitzung dieses Gremiums höchstens?"""
    return CAP_HOURS_COUNCIL if is_council(committee) else CAP_HOURS


def window_end(committee: str | None, start: str | None,
               successor: str | None = None) -> str | None:
    """Ende des Live-Fensters als ``"HH:MM"`` — ``None`` ohne lesbare Startzeit.

    ``successor`` ist die Startzeit der nächsten Sitzung desselben Tages
    (siehe ``CouncilStore.live_windows``); sie schlägt den Deckel immer.

    Über Mitternacht wird nicht gerechnet: Der Deckel endet spätestens um
    23:59. Sonst stünde bei einer Sitzung um 22:00 als Ende „02:00" — ein
    Zeitpunkt VOR dem Beginn, mit dem kein Client etwas anfangen kann.
    """
    if successor:
        return successor
    minuten = _minutes(start)
    if minuten is None:
        return None
    ende = min(minuten + cap_hours(committee) * 60, 23 * 60 + 59)
    return f"{ende // 60:02d}:{ende % 60:02d}"


def _minutes(hhmm: str | None) -> int | None:
    """``"16:30"`` → 990. ``None`` für alles, was keine Uhrzeit ist."""
    teile = (hhmm or "").split(":")
    try:
        stunde = int(teile[0])
        minute = int(teile[1]) if len(teile) > 1 else 0
    except (ValueError, IndexError):
        return None
    if not (0 <= stunde <= 23 and 0 <= minute <= 59):
        return None
    return stunde * 60 + minute
