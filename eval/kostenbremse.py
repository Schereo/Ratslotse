"""Kostenbremse der Messläufe: teure Modelle erst als Stichprobe.

**Tims Regel vom 23.09.2026:** Teure Modelle nur in KLEINEN Benchmarks. Anlass
war die Messung der ausführlichen Recherche (docs/plan-modellwechsel.md): Ein
voller Lauf mit GPT-6 Sol (2/10 $ je Mio. Tokens, 20-mal Luna) kostete 3,10 $,
ein abgebrochener zweiter noch einmal 2,44 $ — für einen Unterschied von zwei
Fällen, den schon eine Stichprobe gezeigt hätte.

Zwei Riegel, beide VOR dem ersten Aufruf:

1. **Schätzung gegen eine Grenze.** Listenpreis aus ``kern/usage.PRICES`` ×
   Promptlänge der gewählten Fälle × Zahl der Aufrufe. Liegt sie über
   ``--max-kosten`` (Vorgabe 1 $), bricht der Lauf mit der Schätzung ab —
   außer mit ``--teuer-ok``. Ein Modell ohne Preis lässt sich nicht schätzen
   und läuft ebenfalls nur mit ``--teuer-ok``.
2. **Stichprobe für teure Modelle.** Kostet die Ausgabe mehr als
   ``TEUER_AUSGABE_USD`` je Mio. Tokens, misst der Lauf ohne weitere Angabe
   eine geschichtete Stichprobe (``--stichprobe N``, Vorgabe 15, feste
   Saat); den vollen Lauf gibt es nur mit ``--voll``.

Die Schätzung ist bewusst eher zu hoch: Die Promptlänge kommt aus früheren
Läufen desselben Falls (dort gemessen, ``kontext_zeichen``), die Antwortlänge
ist eine großzügige Annahme je Kanal, einschließlich der Denk-Tokens.
"""
from __future__ import annotations

import math
import random
from collections import defaultdict
from collections.abc import Callable, Iterable

#: Ab diesem Ausgabepreis (USD je Mio. Tokens) gilt ein Modell als teuer.
#: GPT-6 Luna 0,50, 3.1 Flash Lite 1,50, 3.5 Flash 9,00, GPT-6 Sol 10,00.
TEUER_AUSGABE_USD = 5.0
#: Vorgabe für ``--max-kosten``: Was ein Lauf ohne ausdrückliches Ja kosten darf.
MAX_KOSTEN_USD = 1.0
#: Vorgabe für ``--stichprobe``.
STICHPROBE_N = 15
#: Feste Saat: Zwei Läufe (oder zwei Modelle) sehen dieselbe Stichprobe.
STICHPROBE_SAAT = 20260923
#: Zeichen je Token in deutschen Prompts — grob, und eher zu wenig Zeichen
#: (also eher zu viele Tokens).
ZEICHEN_JE_TOKEN = 3.5


def preis(modell: str) -> tuple[float, float] | None:
    """Listenpreis (Eingabe, Ausgabe) in USD je Mio. Tokens — oder ``None``."""
    from kern import usage
    return usage.PRICES.get((modell or "").split(":")[0])


def teuer(modell: str) -> bool:
    p = preis(modell)
    return p is not None and p[1] > TEUER_AUSGABE_USD


def schaetzen(modell: str, prompt_tokens: Iterable[float], antwort_tokens: float,
              aufrufe_je_fall: float = 1.0) -> float | None:
    """Erwartete Kosten in USD: je Fall Prompt + Antwort, mal Aufrufe je Fall."""
    p = preis(modell)
    if p is None:
        return None
    ein, aus = p
    return sum((pt * ein + antwort_tokens * aus) * aufrufe_je_fall
               for pt in prompt_tokens) / 1e6


def bremse(schaetzung: float | None, *, max_kosten: float, teuer_ok: bool,
           modell: str, was: str = "Der Lauf") -> str | None:
    """``None`` = darf laufen; sonst der Grund samt Ausweg."""
    if teuer_ok:
        return None
    if schaetzung is None:
        return (f"{was} lässt sich nicht schätzen: Für {modell} steht kein Preis in "
                "kern/usage.PRICES. Eintragen (Listenpreis von OpenRouter) — oder "
                "ausdrücklich --teuer-ok.")
    if schaetzung > max_kosten:
        return (f"{was} kostet geschätzt {schaetzung:.2f} $ (Grenze {max_kosten:.2f} $, "
                f"--max-kosten). Erst eine Stichprobe (--stichprobe N); der volle Lauf "
                "nur, wenn sie einen echten Gewinn zeigt — dann mit --teuer-ok.")
    return None


def schicht_fakten(fall: dict) -> str:
    """Die Schicht eines Fakten-Falls: „nicht in den Daten“ für sich, sonst
    der Bereich vor dem Schrägstrich (haushalt, verlauf, verwechslung …)."""
    if not fall.get("antwort_in_daten", True):
        return "nicht-in-daten"
    return str(fall.get("kategorie") or "?").split("/")[0]


def stichprobe(faelle: list[dict], n: int = STICHPROBE_N, *, saat: int = STICHPROBE_SAAT,
               schicht: Callable[[dict], str] = schicht_fakten) -> list[dict]:
    """Eine geschichtete Stichprobe von ``n`` Fällen, in der Reihenfolge der Eingabe.

    Je Schicht so viele, wie ihrem Anteil entspricht (größter Rest), aber
    mindestens einer, solange ``n`` für alle Schichten reicht — sonst fiele
    „nicht in den Daten“ mit sechs von 55 Fällen leicht ganz heraus. Welche
    Fälle einer Schicht es werden, entscheidet eine feste Saat.
    """
    if n >= len(faelle):
        return list(faelle)
    gruppen: dict[str, list[dict]] = defaultdict(list)
    for f in faelle:
        gruppen[schicht(f)].append(f)
    namen = sorted(gruppen)
    anteile = {g: len(gruppen[g]) * n / len(faelle) for g in namen}
    zahl = {g: math.floor(anteile[g]) for g in namen}
    if n >= len(namen):
        for g in namen:
            zahl[g] = max(zahl[g], 1)
    # Größter Rest, bis n erreicht ist; zu viel (durch die Mindestzahl) wird
    # bei den größten Schichten wieder abgezogen.
    for g in sorted(namen, key=lambda g: (-(anteile[g] - math.floor(anteile[g])), g)):
        if sum(zahl.values()) >= n:
            break
        if zahl[g] < len(gruppen[g]):
            zahl[g] += 1
    while sum(zahl.values()) > n:
        g = max(namen, key=lambda g: (zahl[g], g))
        zahl[g] -= 1
    rng = random.Random(saat)
    gewaehlt: set[str] = set()
    for g in namen:
        ids = sorted(f["id"] for f in gruppen[g])
        gewaehlt.update(rng.sample(ids, min(zahl[g], len(ids))))
    return [f for f in faelle if f["id"] in gewaehlt]


def auswahl_fuer(modell: str, faelle: list[dict], *, stichprobe_n: int | None,
                 voll: bool) -> tuple[list[dict], str | None]:
    """Die Fälle, die ein Lauf wirklich misst, und ein Hinweis dazu.

    Ausdrücklich ``--stichprobe N`` gilt immer; ein teures Modell ohne
    ``--voll`` bekommt die Vorgabe-Stichprobe.
    """
    if stichprobe_n:
        teil = stichprobe(faelle, stichprobe_n)
        return teil, f"Stichprobe: {len(teil)} von {len(faelle)} Fällen (--stichprobe)"
    if teuer(modell) and not voll:
        teil = stichprobe(faelle, STICHPROBE_N)
        if len(teil) < len(faelle):
            return teil, (f"{modell} ist teuer (Ausgabe über {TEUER_AUSGABE_USD:.0f} $ je Mio. "
                          f"Tokens): Stichprobe {len(teil)} von {len(faelle)} Fällen. "
                          "Den vollen Lauf nur mit --voll, und nur, wenn die Stichprobe einen "
                          "echten Gewinn zeigt.")
    return faelle, None
