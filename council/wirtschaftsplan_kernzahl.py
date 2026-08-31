"""Die Kernzahl — was der Rat beschließt, bestätigt durch die Anlage.

Der dritte und letzte Weg zu den Wirtschaftsplänen, und der einzige, der über
**zwei Dokumente** geht.

Die beiden anderen brauchen eine Tabelle, die sich selbst vorrechnet:
``wirtschaftsplan.py`` liest die Eckwerte aus dem Beschlusstext (nur der
Eigenbetrieb Gebäudewirtschaft schreibt sie dorthin),
``wirtschaftsplan_tabelle.py`` den Erfolgsplan der Anlage (der
Abfallwirtschaftsbetrieb). Für Bäderbetriebsgesellschaft, Stadion und
Bäderbetrieb trägt beides nicht — und der Grund ist lehrreich.

Warum die Tabellen dieser drei nicht gelesen werden
---------------------------------------------------
Sie führen **dieselben Zeilennamen** wie der Abfallwirtschaftsbetrieb:
``Gesamtleistung``, ``Gesamtkosten``, ``Gesamtergebnis``. Ein Parser, der dem
Namen glaubt, liefert Zahlen, die plausibel aussehen — und falsch sind. Die
Probe ``Gesamtleistung − Gesamtkosten = Gesamtergebnis`` geht auf:

===============  ==================================
Stadion          5 von 5 Spalten
Bäderbetrieb     **0** von 11 und 0 von 6 Spalten
Bäderbetriebsg.  **1** von 24 und 2 von 15 Spalten
===============  ==================================

Bei den beiden Bäder-Gesellschaften stehen zwischen ``Gesamtkosten`` und
``Gesamtergebnis`` noch Abschreibungen, Zinsen und neutrale Posten:
``Gesamtkosten`` ist dort schlicht **nicht** der Gesamtaufwand. Gleiches
Vokabular, andere Bedeutung — genau der Fall, für den es Rechenproben gibt.

Was stattdessen trägt
---------------------
Der **Beschlusstext der Vorlage** nennt die eine Zahl, über die abgestimmt
wird::

    …wird in der anliegenden Fassung mit einem für die Gesellschaft
    ausgewiesenen Jahresfehlbetrag von -10.128.335 Euro beschlossen.

    …wird in der anliegenden Fassung mit einem maximalen Fehlbetrag in Höhe
    von 651.500 Euro beschlossen.

Und die **Anlage** enthält dieselbe Zahl in ihrer Tabelle. Zwei getrennte
Dokumente, unabhängig gesetzt, die übereinstimmen müssen — die stärkste Form
von Beleg, die dieser Bereich kennt, und die einzige hier, die nicht davon
abhängt, eine Tabellenzeile richtig zu deuten.

Gemessen über den Bestand: Bäderbetriebsgesellschaft **9 von 9**, Stadion
**2 von 2**.

Nur das Ergebnis, und das ist der Punkt
---------------------------------------
Diese Route liefert **kein** Erträge/Aufwendungen-Paar. Das ist keine
Nachlässigkeit, sondern die ehrliche Grenze: Die einzige Zahl dieser Dokumente,
die zweifach belegt ist, ist das Jahresergebnis. ``council_wirtschaftsplaene``
lässt ``ertraege`` und ``aufwendungen`` deshalb seit 20.08.2026 offen — ein
``NULL`` sagt „diese Quelle nennt es nicht", eine 0 wäre eine Behauptung.

Die Vorzeichen-Falle
--------------------
„Fehlbetrag in Höhe von 651.500 Euro" ist **minus** 651.500 €. Das Wort trägt
das Vorzeichen, nicht die Ziffernfolge — und mal steht es zusätzlich davor
(„Jahresfehlbetrag von -10.128.335 Euro"), mal nicht. Wer beides gleich liest,
macht aus dem größten Verlust der Stadtgesellschaften einen Gewinn.

Deshalb: Das **Wort** entscheidet die Richtung, die Ziffernfolge nur den
Betrag. Ein „Fehlbetrag" kann nie positiv gespeichert werden, ein
„Überschuss" nie negativ; beides wird geprüft und wirft, statt still
umzudrehen.
"""
from __future__ import annotations

import re

from council.herkunft import Herkunft
from council.wirtschaftsplan import (BETRIEBE, Wirtschaftsplan,
                                    WirtschaftsplanFehler, dokument_name)

PROBE_KERNZAHL = "wirtschaftsplan_kernzahl"
PROBE_INVESTITIONEN = "wirtschaftsplan_investitionen"

PROBEN: dict[str, str] = {
    PROBE_KERNZAHL:
        "Die Zahl, über die der Rat abstimmt, steht im Beschlusstext der "
        "Vorlage — und dieselbe Zahl steht in der beigefügten Anlage. Zwei "
        "getrennte Dokumente, unabhängig gesetzt.",
    PROBE_INVESTITIONEN:
        "Der Beschlusstext nennt die Investitionen des Vermögensplans und "
        "gleich daneben, woraus sie finanziert werden — Kreditaufnahme und "
        "eigene Mittel ergeben zusammen die Summe.",
}

#: Der Satz im Beschlusstext. Fünf Schreibweisen kommen vor:
#: „Jahresfehlbetrag von X", „Jahresfehlbetrag in Höhe von X", „maximalen
#: Fehlbetrag in Höhe von X", „ein Verlust von X EUR ermittelt worden" und
#: „Der ermittelte Verlust in Höhe von X". Das erste Wort trägt die Richtung.
#:
#: „Verlust"/„Gewinn" kamen am 20.08.2026 dazu — sie sind die Sprache des
#: **Eigenbetriebs Hafen**, des einzigen Betriebs, der weder „Fehlbetrag" noch
#: „Überschuss" schreibt. Ohne sie blieben seine beiden einzigen Jahrgänge
#: (2019 und 2020) draußen, ohne dass jemand einen Fehler gesehen hätte: Die
#: Vorlage wäre einfach nie erkannt worden.
_KERNZAHL = re.compile(
    r"(?P<wort>Jahresfehlbetrag|Jahres[üu]berschuss|Fehlbetrag|[Üu]berschuss"
    r"|Verlust|Gewinn)"
    r"[^.]{0,80}?(?:in H[öo]he von|von)\s+"
    r"(?P<betrag>-?\s*\d{1,3}(?:\.\d{3})*(?:,\d{2})?)\s*(?:€|Euro|EUR)", re.I)

#: Wörter, die einen Verlust bezeichnen — sie erzwingen ein negatives
#: Vorzeichen, egal wie die Ziffernfolge geschrieben ist.
_VERLUST = ("fehlbetrag", "verlust")


def _eur(roh: str) -> float:
    s = roh.replace(" ", "")
    vz = -1.0 if s.startswith("-") else 1.0
    return vz * float(s.lstrip("+-").replace(".", "").replace(",", "."))


def kernzahl_aus_beschluss(text: str) -> tuple[str, float] | None:
    """Das beschlossene Jahresergebnis aus dem Beschlusstext.

    Liefert ``(wort, betrag)`` mit dem Betrag **vorzeichenrichtig**: Ein
    „Fehlbetrag" ist negativ, auch wenn die Ziffern ohne Minus dastehen.
    """
    m = _KERNZAHL.search(re.sub(r"\s+", " ", text))
    if not m:
        return None
    wort = m.group("wort")
    betrag = _eur(m.group("betrag"))
    if any(v in wort.lower() for v in _VERLUST):
        # `-abs(0.0)` wäre `-0.0` und stünde als „-0,00 €" auf der Seite.
        betrag = -abs(betrag) if betrag else 0.0
    elif betrag < 0:
        raise WirtschaftsplanFehler(
            f"„{wort}“ mit negativem Betrag ({betrag:.2f} €) — das Wort und die "
            "Zahl sagen Verschiedenes")
    return wort, betrag


def _ziffern(betrag: float) -> str:
    """Die Ziffernfolge, wie sie im Dokument steht: ``10.128.335``."""
    ganz = f"{abs(betrag):,.0f}".replace(",", ".")
    return ganz


def in_anlage_belegt(betrag: float, anlagen_texte: list[str]) -> bool:
    """Steht dieselbe Zahl in einer der Anlagen?

    Verglichen wird die **Ziffernfolge** und nicht der Betrag: Die Anlage setzt
    ihre Vorzeichen anders (mal führendes Minus, mal nachgestellt, mal in einer
    eigenen Spalte), und darüber zu streiten hieße, den Beleg an einer
    Formatfrage scheitern zu lassen. Die Richtung entscheidet ohnehin das Wort
    im Beschlusstext.

    Leerzeichen werden vorher entfernt: Im Textextrakt kleben Zahlen teils
    aneinander (``9.996.40910.570.144``), teils stehen Trennzeichen dazwischen.
    """
    ziffern = _ziffern(betrag)
    return any(ziffern in (t or "").replace(" ", "") for t in anlagen_texte)


def parse_kernzahl(template_number: str, titel: str, vorlage_text: str,
                   year: int, anlagen_texte: list[str],
                   ) -> tuple[Wirtschaftsplan, str, str] | None:
    """Das beschlossene Jahresergebnis — belegt durch die Anlage.

    ``None``, wenn der Beschlusstext keine Zahl nennt. Wirft, wenn er eine
    nennt, die in keiner Anlage steht: Dann widersprechen sich zwei Dokumente,
    oder eines von beiden ist falsch gelesen.

    **Die Null ist der Sonderfall.** Ein ausgeglichener Plan („Jahresfehlbetrag
    in Höhe von 0,00 Euro") lässt sich in der Anlage nicht suchen — die Ziffer
    0 steht dort hundertfach. Er wird trotzdem übernommen: Der Beschlusstext
    ist die maßgebliche Stelle, und „ausgeglichen" ist eine Aussage, die man
    nicht schärfer belegen kann als durch den Beschluss selbst. Die Herkunft
    schreibt an, dass die Gegenprobe hier nicht greift.
    """
    erkannt = kernzahl_aus_beschluss(vorlage_text)
    if erkannt is None:
        return None
    wort, betrag = erkannt

    lesbar = [x for x in anlagen_texte if x and x.strip()]
    if betrag != 0 and lesbar and not in_anlage_belegt(betrag, lesbar):
        raise WirtschaftsplanFehler(
            f"{template_number}: Der Beschlusstext nennt {betrag:,.2f} € "
            f"(„{wort}“), aber die Zahl steht in keiner Anlage — zwei "
            "Dokumente desselben Vorgangs widersprechen sich")
    # KEIN lesbarer Anlagentext ist etwas anderes als ein Widerspruch: Dann
    # konnte die Gegenprobe gar nicht laufen. Der Wert kommt trotzdem herein
    # — der Beschlusstext ist die maßgebliche Stelle —, aber die Herkunft sagt,
    # dass er unbestätigt blieb. Das kam beim Stadion dreimal vor, wo die
    # Anlagen älterer Jahrgänge noch keinen Volltext tragen.
    # Zwei verschiedene Gründe, warum die Gegenprobe nicht lief — und sie
    # gehören auseinandergehalten, weil der eine sich später auflöst und der
    # andere nie:
    #   "ausgeglichen" — der Betrag ist 0, und die Ziffer 0 steht in jeder
    #     Anlage hundertfach. Daran ändert auch ein OCR-Lauf nichts.
    #   "ohne_anlage"  — es gibt schlicht keinen Anlagentext (Scan oder noch
    #     nicht nachgeladen). Das kann sich ändern.
    if betrag == 0:
        beleglage = "ausgeglichen"
    elif not lesbar:
        beleglage = "ohne_anlage"
    else:
        beleglage = "belegt"

    key = _betrieb_key(titel)
    if key is None:
        raise WirtschaftsplanFehler(
            f"{template_number}: Betrieb unbekannt — Titel: {titel!r}")

    plan = Wirtschaftsplan(
        betrieb=key, betrieb_name=BETRIEBE[key][1], year=year,
        template_number=template_number,
        # Diese Quelle nennt nur das Ergebnis. NULL heißt „sagt sie nicht" —
        # eine 0 wäre eine Behauptung über Erträge, die nirgends steht.
        ertraege=None, aufwendungen=None, steuern=None,
        ergebnis=betrag,
        vermoegensplan=None, verpflichtungen=None, entwurf_vom=None,
        # Der zweite Satz über Geld in derselben Vorlage — mit eigener
        # Probe, sonst `None` (s. `investitionen_aus_beschluss`).
        investitionen=investitionen_aus_beschluss(vorlage_text),
    )
    return plan, wort, beleglage


#: Die Investitionen im Vermögensplan — der zweite Satz, den diese Vorlagen
#: über Geld sagen.
#:
#: WARUM ES IHN BRAUCHT (Tim, 21.08.2026): „Ich habe in den Wirtschaftsplan
#: vom Bäderbetrieb reingeguckt und da stehen ja ganz, ganz viele Zahlen drin.
#: Wie kann es sein, dass hier das Jahresergebnis immer Null ist?" Die Null ist
#: richtig — alle sieben Jahrgänge schreiben wörtlich „schließt mit einem
#: geplanten Jahresfehlbetrag in Höhe von 0,00 EUR ab", der Betrieb verpachtet
#: seit 2005 nur noch sein Vermögen an die Betriebsgesellschaft. Nur stand auf
#: der Karte dann eine Null und sonst nichts, während derselbe Beschlusstext
#: 10.752.000 € Investitionen nennt.
#:
#: „Ursprüngliche[r] Vermögensplan" ist AUSGESCHLOSSEN und das ist der Kern
#: dieses Musters: Zwei Jahrgänge (2024, 2025) sind Anpassungs-Vorlagen, die
#: den alten Stand zitieren, bevor sie ihn ändern. Wer ihn liest, speichert
#: eine überholte Zahl als aktuelle.
_INVESTITIONEN = re.compile(
    r"(?<!ursprünglicher )(?<!ursprüngliche )(?<!urspruenglicher )"
    r"Verm[öo]gensplan(?:\s+\d{4})?\s+weist\s+Investitionen\s+in\s+H[öo]he\s+von\s+"
    r"(?P<betrag>\d{1,3}(?:\.\d{3})*(?:,\d{2})?)\s*(?:€|Euro|EUR)", re.I)

#: Die Finanzierungsteile in Klammern, direkt hinter dem Satz: „durch eine
#: Kreditaufnahme am Kreditmarkt (10.702.000 Euro) und aus der Verwendung von
#: Abschreibungen […] und der Liquidität (50.000 Euro)".
_FINANZTEIL = re.compile(
    r"\(\s*(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)\s*(?:€|Euro|EUR)\s*\)", re.I)

#: Wie weit hinter dem Satz nach den Klammern gesucht wird. Der
#: Finanzierungssatz folgt unmittelbar; weiter hinten stünden Klammerbeträge
#: aus ganz anderen Absätzen.
_FINANZ_FENSTER = 420

#: Ein Euro. Die Teile sind auf volle Euro gerundet gedruckt.
TOLERANZ_INVEST_EUR = 1.0

def investitionen_aus_beschluss(text: str) -> float | None:
    """Die Investitionen des Vermögensplans — nur, wenn sie sich selbst prüfen.

    DIE PROBE STEHT IM SATZ DANEBEN. Der Beschlusstext nennt die Summe und
    unmittelbar darauf, woraus sie finanziert wird; die Teile müssen sie
    ergeben. Für 2026 des Bäderbetriebs: 10.702.000 € Kredit + 50.000 €
    Liquidität = 10.752.000 €.

    Fehlt der Finanzierungssatz oder geht er nicht auf, wird **nichts**
    zurückgegeben. Eine Zahl ohne Gegenrechnung wäre in diesem Bereich der
    schlechtere Tausch — dieselbe Regel wie überall sonst hier.
    """
    flach = re.sub(r"\s+", " ", text or "")
    m = _INVESTITIONEN.search(flach)
    if m is None:
        return None
    gesamt = _eur(m.group("betrag"))
    teile = [_eur(x) for x in
             _FINANZTEIL.findall(flach[m.end():m.end() + _FINANZ_FENSTER])]
    if not teile or abs(sum(teile) - gesamt) > TOLERANZ_INVEST_EUR:
        return None
    return gesamt


def _betrieb_key(titel: str) -> str | None:
    from council.wirtschaftsplan import betrieb_aus_titel

    erkannt = betrieb_aus_titel(titel)
    return erkannt[0] if erkannt else None


#: Wie der Beleg-Chip die drei Lagen anschreibt.
BELEGLAGE = {
    "belegt": "dieselbe Zahl steht in der Anlage",
    "ausgeglichen": "ausgeglichener Plan — die Null lässt sich in der Anlage "
                    "nicht gegenprüfen",
    "ohne_anlage": "die Anlage trägt (noch) keinen lesbaren Text",
}


def herkunft_fuer(plan: Wirtschaftsplan, wort: str, beleglage: str,
                  url: str | None, kvonr: int | None) -> Herkunft:
    """Die Herkunft: die **Vorlage**, mit der Anlage als Gegenprobe."""
    return Herkunft(
        art="ris",
        # Die zweite Probe steht nur dran, wo sie auch gelaufen ist: Sie hängt
        # an einem Satz, den nicht jede Vorlage schreibt.
        probe=([PROBE_KERNZAHL, PROBE_INVESTITIONEN]
               if plan.investitionen is not None else [PROBE_KERNZAHL]),
        # Der Name statt des Aktenzeichens — s. `wirtschaftsplan.dokument_name`.
        label=dokument_name(plan),
        url=url or (f"https://buergerinfo.oldenburg.de/vo0050.php?__kvonr={kvonr}"
                    if kvonr else None),
        fundstelle="Beschlussvorschlag der Vorlage",
        probe_ergebnis=f"„{wort}“ — {BELEGLAGE[beleglage]}",
        stand=f"Wirtschaftsplan {plan.year}, Fassung des Ratsbeschlusses",
    )
