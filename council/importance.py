"""Wichtigkeit eines Ratsbeschlusses (0–100).

Ein bewusst **einfacher, transparenter** Score (kein ML) aus vier Signalen —
damit wichtige Beschlüsse im Quiz, in Beschluss-Listen und auf den Themen-Seiten
nach vorn rücken (das „Wichtigkeits"-Konzept aus dem Nutzer-Feedback):

1. **Geld** — großer €-Betrag = gewichtiger (log-skaliert).
2. **Umstrittenheit** — Gegenstimmen/Enthaltungen = politisch bedeutsam
   (Routine läuft einstimmig durch).
3. **Verbindlichkeit & Ebene** — Satzung/Bebauungsplan im **Rat** wiegt schwerer
   als eine Kenntnisnahme im Fachausschuss.
4. **Beratungsaufwand** — je mehr Stationen die Beratungsfolge durchlief, desto
   bedeutsamer/komplexer.

Jedes Signal ist **optional**: Fehlt der Rohwert (kein €-Betrag bekannt, keine
Abstimmung, Beratungsfolge noch nicht gescrapt), zählt das Signal NICHT als 0,
sondern fällt aus der Gewichtung — die verbleibenden Signale werden neu
normiert. So wird ein Beschluss nicht dafür bestraft, dass ein Datum fehlt.

Die einzelnen Beiträge sind über :func:`importance_breakdown` abrufbar, damit die
UI erklären kann, *warum* ein Beschluss als wichtig gilt.
"""
from __future__ import annotations

import math

# Gewichte der vier Signale (Summe = 1.0; werden bei fehlenden Signalen neu
# normiert).
_W_MONEY = 0.34
_W_CONTENTION = 0.24
_W_BINDING = 0.22
_W_EFFORT = 0.20

# 50 Mio € → Vollausschlag des Geld-Signals (log-skaliert: 5.000 € ≈ 0.32,
# 500.000 € ≈ 0.63, 5 Mio € ≈ 0.85). Große Hochbau-/Infrastruktur-Beschlüsse
# liegen im zweistelligen Millionenbereich.
_MONEY_CAP = 50_000_000.0

# Schlagworte, die auf einen verbindlichen/gewichtigen Beschluss deuten
# (rechtssetzend oder haushaltswirksam) …
_BINDING_WORDS = (
    "satzung", "bebauungsplan", "flächennutzungsplan", "haushalt",
    "doppelhaushalt", "gebühren", "verordnung", "änderungssatzung",
)
# … und solche, die typische Routine/Formalia markieren.
_ROUTINE_WORDS = (
    "kenntnisnahme", "kenntnis genommen", "niederschrift", "mitteilung",
    "anfrage", "einwohnerfrage", "einwohnerfragestunde", "resolution",
)

# Gremien-Namen des **Rates**/beschließenden Hauptausschusses — im Gegensatz zu
# Fachausschüssen/Beiräten. **Exakter** Abgleich (klein/getrimmt): in den Daten
# steht schlicht „Rat"; ein Teilstring-Abgleich verböte sich, weil „Beirat",
# „Ortsrat" oder „Integrationsbeirat" ebenfalls „rat" enthalten.
_COUNCIL_NAMES = frozenset({"rat", "rat der stadt oldenburg", "verwaltungsausschuss"})


def _is_council_level(committee: str | None) -> bool:
    """True, wenn der Beschluss im **Rat** (oder Verwaltungsausschuss als dessen
    beschließendem Hauptausschuss) gefasst wurde — nicht in einem Fachausschuss
    oder Beirat."""
    return (committee or "").strip().lower() in _COUNCIL_NAMES


def _money_signal(amount_eur: float | None) -> float | None:
    if not amount_eur or amount_eur <= 0:
        return None  # kein Betrag bekannt → Signal fehlt (nicht 0!)
    return min(1.0, math.log10(amount_eur + 1.0) / math.log10(_MONEY_CAP))


def _contention_signal(gegenstimmen: int | None, enthaltungen: int | None,
                       vote: str | None, outcome: str | None) -> float | None:
    # Nur aussagekräftig, wenn tatsächlich abgestimmt wurde.
    if outcome in (None, "kein_beschluss", "zur_kenntnis"):
        return None
    g = gegenstimmen or 0
    e = enthaltungen or 0
    if g > 0 or e > 0:
        # Jede Gegenstimme hebt an, Enthaltungen halb; grob gedeckelt (die
        # Ratsgröße kennen wir nicht zuverlässig, daher heuristisch).
        return min(1.0, 0.45 + 0.55 * min(1.0, (g + 0.5 * e) / 10.0))
    # Keine Zahlen extrahiert → auf das (zuverlässigere) `vote`-Feld stützen.
    v = (vote or "").strip().lower()
    if v == "mehrheitlich":
        return 0.6   # es gab Gegenstimmen, nur nicht als Zahl erfasst
    if v == "einstimmig":
        return 0.12  # klar einstimmig → wenig umstritten
    return None      # gar keine Abstimmungsinfo → Signal fehlt (nicht 0)


def _binding_signal(title: str | None, committee: str | None,
                    kind: str | None) -> float:
    """Immer vorhanden (Titel-basiert), damit jeder Beschluss mindestens ein
    Signal hat."""
    t = (title or "").lower()
    if any(w in t for w in _BINDING_WORDS):
        score = 0.9
    elif any(w in t for w in _ROUTINE_WORDS):
        score = 0.1
    else:
        score = 0.35  # normaler Sachbeschluss
    if _is_council_level(committee):
        score = min(1.0, score + 0.25)   # im Rat gefasst → gewichtiger
    if kind == "subvote":
        score *= 0.7                     # Teil-Abstimmung eines größeren Punkts
    return score


def _effort_signal(n_beratungen: int | None) -> float | None:
    if not n_beratungen or n_beratungen <= 1:
        return None  # keine/triviale Beratungsfolge → Signal fehlt
    return min(1.0, (n_beratungen - 1) / 5.0)  # 6+ Stationen → Vollausschlag


def importance_breakdown(decision: dict, n_beratungen: int | None = None) -> dict:
    """Einzelbeiträge (0–1 je vorhandenem Signal) + Gesamtscore (0–100).
    Fehlende Signale sind ``None`` und fallen aus der Gewichtung."""
    parts = {
        "geld": (_W_MONEY, _money_signal(decision.get("amount_eur"))),
        "umstritten": (_W_CONTENTION, _contention_signal(
            decision.get("gegenstimmen"), decision.get("enthaltungen"),
            decision.get("vote"), decision.get("outcome"))),
        "verbindlich": (_W_BINDING, _binding_signal(
            decision.get("title"), decision.get("committee"), decision.get("kind"))),
        "aufwand": (_W_EFFORT, _effort_signal(n_beratungen)),
    }
    present = [(w, s) for w, s in parts.values() if s is not None]
    total_w = sum(w for w, _ in present) or 1.0
    score = sum(w * s for w, s in present) / total_w
    return {
        "score": round(100 * score),
        "signals": {k: (round(s, 3) if s is not None else None) for k, (_, s) in parts.items()},
    }


def importance_score(decision: dict, n_beratungen: int | None = None) -> int:
    """Wichtigkeit eines Beschlusses als ganze Zahl 0–100."""
    return importance_breakdown(decision, n_beratungen)["score"]
