"""Fördervorhaben und Ratsvorlagen verbinden.

Zwei Fragen, die die Listen der Geber (``council/foerdermittel.py``) allein
nicht beantworten:

1. **Was hat der Rat zu einem bewilligten Vorhaben gesehen?** Eine Vorlage
   gehört zu einem Vorhaben, wenn sie es ERKENNBAR meint — nicht, wenn sie
   nur dasselbe Stichwort trägt. Zwei Regeln, beide an der ganzen Ratsdatenbank
   gemessen (24.09.2026, 101 Vorhaben gegen 5.141 Vorlagen):

   - **Betrag und Name:** Der bewilligte Betrag steht auf den Euro genau im
     Text (ab 5.000 €), UND ein seltenes Wort aus dem Titel des Vorhabens steht
     daneben („Eislaufbahn", „Signalprogrammauswahl"). Selten heißt: in
     höchstens zwölf Vorlagen überhaupt. Ohne diese Schranke hing
     „Technologien" an der Smart-City-Bewerbung und „Haarenstraße" an einer
     Anfrage zur Beleuchtung — beide mit einem zufällig gleichen Betrag.
   - **Titel im Titel:** Der Kern des Vorlagentitels (ohne „- Bericht" und
     Klammern, mindestens zwei Wörter) steht vollständig im Titel des
     Vorhabens: „Wärmewende Nordwest - Bericht" → „Verbundvorhaben Wärmewende
     Nordwest: …".

   Beide nur im Zeitfenster ein Jahr vor Beginn bis zwei nach Ende. Ohne das
   hing eine Vorlage von 2023 zu Aufpflasterungen in der Peterstraße an einem
   Klimaschutz-Vorhaben, das 2026 beginnt.

2. **Wofür hat die Stadt Geld beantragt?** Die Vorlagen, mit denen der Rat
   einen Förderantrag beschließt („Förderantrag Skatehalle", „Teilnahme am
   Bundesprogramm …"). Die meisten gehören zu Programmen, die in KEINER der
   beiden Listen stehen (Sanierung kommunaler Sportstätten, Städtebau) — ein
   Antrag ist deshalb nie als Bewilligung zu lesen. Die eigenen
   Förderprogramme der Stadt („Förderprogramm Photovoltaik") sind die andere
   Richtung und bleiben draußen.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

#: Ein Wort, das in mehr Vorlagen steht, trägt keine Zuordnung.
SELTEN = 12
#: Unter diesem Betrag ist die Zahl zu häufig, um etwas zu belegen.
MINDESTBETRAG = 5000

_WORT = re.compile(r"[A-Za-zÄÖÜäöüß][\wÄÖÜäöüß-]{2,}")
_FUELL = {"der", "die", "das", "und", "für", "von", "den", "dem", "des", "zur", "zum",
          "mit", "auf", "bericht", "beschluss", "stadt", "oldenburg", "oldb",
          "sachstand", "antrag", "berichtsvorlage"}


@dataclass(frozen=True)
class Verweis:
    source: str
    source_id: str
    template_number: str
    basis: str  # amount | title


def _woerter(text: str) -> set[str]:
    return {w.lower() for w in _WORT.findall(text or "")}


def _jahr(template_number: str) -> int | None:
    m = re.match(r"(\d\d)/", template_number or "")
    return 2000 + int(m.group(1)) if m else None


def _betrag_muster(betrag: float) -> re.Pattern:
    """„90.000" trifft „90.000 €" und „90.000,00", nicht „190.000"."""
    euro, cent = divmod(round(betrag * 100), 100)
    ganz = f"{euro:,}".replace(",", r"\.")
    rest = rf",{cent:02d}(?!\d)" if cent else r"(?:,00)?(?![\d]|[.,]\d)"
    return re.compile(rf"(?<![\d.,]){ganz}{rest}")


def _kern(titel: str) -> set[str]:
    titel = re.sub(r"\([^)]*\)", "", titel or "")
    titel = re.split(r"\s[-–]\s*(?:Bericht|Beschluss|Sachstand)", titel)[0]
    return _woerter(titel) - _FUELL


def verknuepfe(vorhaben: list[dict], vorlagen: list[dict]) -> list[Verweis]:
    """``vorhaben``: Zeilen aus ``council_grants_received``; ``vorlagen``:
    ``template_number``, ``title``, ``raw_text``."""
    texte = [(v, _woerter(v.get("raw_text") or "") | _woerter(v["title"])) for v in vorlagen]
    df = Counter(w for _, ws in texte for w in ws)
    aus: list[Verweis] = []
    for z in vorhaben:
        beginn = int((z.get("start") or "1900")[:4])
        ende = int((z.get("end") or z.get("start") or "2100")[:4])
        titelwoerter = _woerter(z["title"])
        selten = {w for w in titelwoerter if 0 < df[w] <= SELTEN}
        muster = (_betrag_muster(z["amount_granted"])
                  if (z.get("amount_granted") or 0) >= MINDESTBETRAG else None)
        for v, ws in texte:
            jahr = _jahr(v["template_number"])
            if jahr is None or not beginn - 1 <= jahr <= ende + 2:
                continue
            basis = None
            kern = _kern(v["title"])
            if len(kern) >= 2 and kern <= titelwoerter:
                basis = "title"
            elif muster and selten & ws and muster.search(v.get("raw_text") or ""):
                basis = "amount"
            if basis:
                aus.append(Verweis(z["source"], z["source_id"], v["template_number"], basis))
    return aus


#: Vorlagen, mit denen die Stadt Geld beantragt oder sich bewirbt.
ANTRAG = re.compile(
    r"Förderantr|Zuwendungsantr|Zuwendungsbescheid|Bundes(?:förder)?programm|"
    r"Landesförderprogramm|Projektaufruf|Förderaufruf|Bewerbung (?:als|um|für)")
#: … und was trotz eines der Wörter keine ist: die eigenen Programme der
#: Stadt, ihre Richtlinien, und die Übernahme nicht gedeckter Kosten.
_KEIN_ANTRAG = re.compile(r"^(?:Änderung der )?(?:Förderrichtlinie|Förderprogramm)|Richtlinie|"
                          r"^Sanierungsgebiet|Übernahme des nicht")


def ist_antrag(titel: str) -> bool:
    return bool(ANTRAG.search(titel or "")) and not _KEIN_ANTRAG.search(titel or "")
