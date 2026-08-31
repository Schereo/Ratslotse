"""Der Haushalt neben dem Haushalt: die Wirtschaftspläne der Eigenbetriebe.

Der Kernhaushalt ist nicht alles, was der Rat beschließt. Daneben stehen die
**Wirtschaftspläne** der Eigenbetriebe und Gesellschaften — eigene Erfolgs- und
Vermögenspläne, in derselben Ratssitzung entschieden, aus dem Haushalts-Bereich
bisher unsichtbar. Der größte davon ist der Eigenbetrieb Gebäudewirtschaft und
Hochbau (EGH): 2026 rund 82,8 Mio. € Erträge und Aufwendungen, dazu ein
Vermögensplan über 51,1 Mio. €. Er baut und saniert die städtischen Gebäude —
also auch die Schulen, die im Investitionsprogramm des Kernhaushalts
ausdrücklich fehlen.

Was `/haushalt/konzern` und `/haushalt/beteiligungen` von diesen Betrieben
zeigen, ist ihr **Ist**, aus dem Gesamtabschluss und dem Beteiligungsbericht,
und beides hinkt rund zwei Jahre hinterher. Was sie für das laufende Jahr
vorhaben, stand nirgends.

Die Quelle ist ungewöhnlich
---------------------------
Nicht eine Anlage, sondern die **Vorlage selbst**. Der Beschlussvorschlag einer
EGH-Wirtschaftsplan-Vorlage trägt die Eckwerte im Klartext::

    im Erfolgsplan

    mit Erträgen von 82.815.150 Euro
    mit Aufwendungen von 82.824.771 Euro
    mit steuerlichen Aufwendungen von                6.000 Euro
    und einem Jahresergebnis von              -    15.621 Euro

    und im Vermögensplan

    mit Einzahlungen und Auszahlungen von je 51.134.100 Euro
    und Verpflichtungsermächtigungen von 104.980.000 Euro

Das ist der Beschlusstext, über den abgestimmt wird — keine Zusammenfassung
und keine Anlage, die später ausgetauscht werden könnte. `council_vorlagen`
führt ihn längst als Volltext; es brauchte nur niemand.

Die Rechenprobe steht im Text
-----------------------------
``Erträge − Aufwendungen − steuerliche Aufwendungen = Jahresergebnis``

Vier Zahlen, von denen die vierte aus den ersten dreien folgt. Über **alle acht
Jahrgänge** (2019–2026) geht sie auf den **Cent** auf — nicht auf den Euro, auf
den Cent. Wer eine Zahl falsch liest, fällt auf.

Dazu eine zweite, unabhängige: Das Haushaltsjahr steht zweimal da, im Fließtext
(„für das Haushaltsjahr 2026") und im Titel der Vorlage. Ein Parser, der die
Zahlen dem falschen Jahr zuschlägt, ist damit erkennbar — der häufigere Fehler
als eine falsch gelesene Ziffer, weil eine Vorlage aus dem Oktober 2025 das
Jahr 2026 beschließt.

Nur der EGH, und das ist ein Befund
-----------------------------------
Von 46 Wirtschaftsplan-Vorlagen im Bestand (2018–2026) tragen **acht** diesen
Block — alle acht vom EGH. Die übrigen 38 nennen im Beschlusstext gar keine
Zahl: Abfallwirtschaftsbetrieb und Bäderbetrieb stimmen „der anliegenden
Fassung" zu, die Zahlen stehen dort in einer Anlage. Bäderbetriebsgesellschaft
und Stadion nennen genau eine Zahl (den Jahresfehlbetrag) im Fließtext, ohne
Gegenrechnung.

Diese Schicht liest deshalb **nur, was sich prüfen lässt**. Für die anderen
Betriebe eine Zahl aus einem Prosasatz zu ziehen, hieße eine Angabe ohne
Gegenprobe in eine Tabelle zu schreiben, die daneben lauter geprüfte führt —
die Herkunft sagte „ungeprüft", und auf der Seite sähe sie aus wie der Rest.
Was fehlt, fehlt sichtbar (:func:`ohne_eckwerte`).

Zwei Formate, ein Muster
------------------------
Die Jahrgänge 2019 und 2020 schreiben „EUR" statt „Euro", führen **keine**
steuerlichen Aufwendungen und setzen ein ``+`` vor ein positives Ergebnis. Das
Muster deckt beides ab; die fehlende Steuerzeile zählt als 0, was sie
rechnerisch auch ist (die Probe geht in beiden Jahrgängen auf).

Was diese Zahlen sind — und was nicht
-------------------------------------
Es ist der **Verwaltungsentwurf**, nicht der Beschluss: Der Text sagt das
selbst („in der Fassung des Verwaltungsentwurfes vom 01.10.2025 — unter
Einbeziehung der sich aus den Beschlüssen … ergebenden Änderungen"). Das Datum
wird mitgelesen und gehört an jede Anzeige, dieselbe Vorsicht wie beim
Gesamtergebnishaushalt (``council/income_budget.py``).

Und sie sind **nicht** mit dem Kernhaushalt verrechenbar. Der EGH vermietet der
Stadt ihre eigenen Gebäude; seine Erträge sind zu einem großen Teil Aufwand des
Kernhaushalts. Wer beide addiert, zählt dasselbe Geld zweimal. Der
Gesamtabschluss rechnet genau diese Verflechtung heraus — das ist seine
Aufgabe, und deshalb ersetzt diese Schicht ihn nicht, sondern steht daneben.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from council.herkunft import Herkunft

#: Name der Rechenprobe, die im Dokument selbst steht.
PROBE_ERFOLGSPLAN = "wirtschaftsplan_erfolgsplan"
#: Die zweite: Fließtext-Jahr gegen Titel-Jahr.
PROBE_JAHR = "wirtschaftsplan_jahr"

PROBEN: dict[str, str] = {
    PROBE_ERFOLGSPLAN:
        "Der Beschlusstext rechnet sich selbst vor: Erträge − Aufwendungen − "
        "steuerliche Aufwendungen = Jahresergebnis. Über alle Jahrgänge auf den "
        "Cent.",
    PROBE_JAHR:
        "Das Haushaltsjahr steht im Fließtext und im Titel der Vorlage — beide "
        "müssen dasselbe sagen. Eine Vorlage aus dem Oktober beschließt das "
        "FOLGENDE Jahr; ohne diese Probe landeten die Zahlen leicht im Jahr der "
        "Vorlage.",
}

#: Was diese Zahlen sind und was nicht — reist mit den Daten statt im Frontend
#: zu stehen (dieselbe Regel wie `buergschaften.ABGRENZUNG`). Ohne diesen Satz
#: liest sich „82,8 Mio. €" als Teil des Stadthaushalts, und das ist es nicht.
ABGRENZUNG = (
    "Eigener Wirtschaftsplan des Betriebs, nicht Teil des Kernhaushalts und mit "
    "ihm nicht addierbar: Der Eigenbetrieb vermietet der Stadt ihre eigenen "
    "Gebäude, seine Erträge sind zu großen Teilen Aufwand des Kernhaushalts. "
    "Herausgerechnet wird diese Verflechtung erst im Gesamtabschluss."
)

#: Cent-genau. Die Quelle führt volle Euro; die kleinste mögliche Abweichung
#: wäre damit 1 €, und eine Toleranz von 1 € ließe genau den einen Fehler
#: durch, den die Probe sehen könnte — dieselbe Überlegung wie bei
#: `investitionen.TOLERANZ_EUR`.
TOLERANZ_EUR = 0.005

#: Ein Betrag im Beschlusstext: „82.815.150", „-  5.401.285", „+ 349.700",
#: auch mit Cent. Vorzeichen und Zahl können durch Leerraum getrennt sein —
#: das PDF setzt sie in verschiedene Tabellenzellen.
_BETRAG = r"([+-]?\s*\d{1,3}(?:\.\d{3})*(?:,\d{2})?)"

#: Die Zeilen des Beschlusstextes. `steuer` fehlt in den Jahrgängen 2019/2020
#: und zählt dann als 0.
_ZEILEN = {
    "revenues":   r"mit Ertr[äa]gen von\s*" + _BETRAG,
    "expenses": r"mit Aufwendungen von\s*" + _BETRAG,
    "taxes":    r"mit steuerlichen Aufwendungen von\s*" + _BETRAG,
    "result":   r"und einem Jahresergebnis von\s*" + _BETRAG,
    "capital_plan": r"Einzahlungen und Auszahlungen von je\s*" + _BETRAG,
    "commitments": r"Verpflichtungserm[äa]chtigungen von\s*" + _BETRAG,
}

#: „für das Haushaltsjahr 2026" — die Jahresangabe im Beschlusstext.
_JAHR_TEXT = re.compile(r"f[üu]r das Haushaltsjahr\s+(\d{4})")
#: Eine vierstellige Jahreszahl im Titel („… der Stadt Oldenburg 2026 - Beschluss").
_JAHR_TITEL = re.compile(r"\b(20\d{2})\b")
#: „in der Fassung des Verwaltungsentwurfes vom 01.10.2025" — und, im Jahrgang
#: 2024, „des **I.** Verwaltungsentwurfes vom 04.10.2023". Die Ordnungszahl
#: zählt die Fassung: Bringt die Verwaltung nachträglich eine zweite ein, steht
#: dort „II.". Sie wird zugelassen, aber nicht ausgewertet — welche Fassung
#: gilt, sagt ohnehin erst der Ratsbeschluss, und das Datum unterscheidet sie
#: eindeutig.
_ENTWURF = re.compile(
    r"Fassung des\s+(?:[IVX]+\.\s*)?Verwaltungsentwurfe?s? vom\s+(\d{2}\.\d{2}\.\d{4})")

#: Welcher Betrieb — erkannt am Vorlagentitel. Bewusst eine benannte Liste und
#: kein „alles, was Wirtschaftsplan heißt": Ein unbekannter Betrieb soll als
#: unbekannt auffallen und nicht unter einem geratenen Namen in der Tabelle
#: landen.
BETRIEBE: dict[str, tuple[str, str]] = {
    "egh": (r"Eigenbetrieb(?:es)?\s+Geb[äa]udewirtschaft",
            "Eigenbetrieb Gebäudewirtschaft und Hochbau"),
    "awb": (r"Abfallwirtschaftsbetrieb", "Abfallwirtschaftsbetrieb Stadt Oldenburg"),
    "bbo": (r"B[äa]derbetrieb der Stadt|Eigenbetrieb(?:es|s)?\s+B[äa]der",
            "Bäderbetrieb der Stadt Oldenburg"),
    "bbgo": (r"B[äa]derbetriebsgesellschaft", "Bäderbetriebsgesellschaft Oldenburg mbH"),
    "hafen": (r"Eigenbetrieb\s+Hafen", "Eigenbetrieb Hafen der Stadt Oldenburg"),
    # ZWEI Gesellschaften, nicht eine. Die Planungsgesellschaft hat das Stadion
    # geplant, die Betriebsgesellschaft betreibt es — sie legen eigene
    # Wirtschaftspläne vor, und 2024 gibt es von beiden einen (−152.000 € bzw.
    # −190.000 €). Ein gemeinsames Muster „Stadion" schrieb den einen Betrag
    # unter den Namen der anderen. Die Planungsgesellschaft steht ZUERST: Ihr
    # Name enthält den der anderen nicht, umgekehrt schon nicht — aber die
    # Reihenfolge entscheidet, und geraten wird hier nichts.
    "stadion_planung": (r"Stadionplanungsgesellschaft",
                        "Stadionplanungsgesellschaft mbH"),
    "stadion": (r"Stadion Oldenburg", "Stadion Oldenburg GmbH & Co. KG"),
}


class WirtschaftsplanFehler(ValueError):
    """Der Beschlusstext trägt Eckwerte, aber sie gehen nicht auf."""


@dataclass(frozen=True)
class Wirtschaftsplan:
    """Die Eckwerte eines Wirtschaftsplans, wie der Rat sie beschließt."""

    enterprise: str          # Kürzel aus BETRIEBE
    enterprise_name: str
    year: int             # Haushaltsjahr, nicht das Jahr der Vorlage
    template_number: str
    revenues: float
    expenses: float
    taxes: float
    result: float
    #: Einzahlungen = Auszahlungen; das Dokument nennt nur eine Zahl.
    capital_plan: float | None
    commitments: float | None
    #: Datum des Verwaltungsentwurfs — der Stand, den diese Zahlen tragen.
    draft_date: str | None
    #: Die Investitionen IM Vermögensplan — ein Posten, nicht die Summe.
    #:
    #: Zwei Betriebe, zwei Sprechweisen: Der EGH nennt im Beschlusstext die
    #: Gesamtsumme („Einzahlungen und Auszahlungen von je 51,6 Mio. €"), der
    #: Bäderbetrieb nur den Posten („Der Vermögensplan weist Investitionen in
    #: Höhe von 10.752.000 Euro aus"). Beide Angaben in dieselbe Spalte zu
    #: legen hieße, eine Teilmenge als Summe auszugeben.
    #:
    #: Vorgabe ``None``, damit die drei Lesewege (Beschlusstext, Erfolgsplan
    #: der Anlage, Kernzahl) nur setzen, was ihre Quelle wirklich nennt.
    investitionen: float | None = None

    @property
    def probe_result(self) -> str:
        """Der Messwert der Probe, für die Herkunft."""
        rest = self.revenues - self.expenses - self.taxes - self.result
        return f"Erfolgsplan geht auf, Restbetrag {rest:.2f} €"


def _eur(roh: str) -> float:
    """„-  5.401.285" → -5401285.0. Deutsche Schreibweise, Vorzeichen darf
    durch Leerraum abgesetzt sein."""
    s = roh.replace(" ", "").replace(" ", "")
    vz = -1.0 if s.startswith("-") else 1.0
    s = s.lstrip("+-").replace(".", "").replace(",", ".")
    return vz * float(s)


def _glaetten(text: str) -> str:
    """Trennstriche am Zeilenende auflösen und Zeilen verbinden.

    **Nur innerhalb von Wörtern** (``Olden-\\nburg``): Ein Bindestrich, dem
    Leerraum vorausgeht, ist im Beschlusstext ein **Minuszeichen** vor einem
    Betrag. Ein pauschales ``-\\s*\\n`` würde es verschlucken und aus einem
    Fehlbetrag einen Überschuss machen — der teuerste denkbare Lesefehler
    dieser Schicht."""
    text = re.sub(r"(?<=[A-Za-zÄÖÜäöüß])-\s*\n\s*(?=[a-zäöüß])", "", text)
    return re.sub(r"\s+", " ", text)


def betrieb_aus_titel(title: str) -> tuple[str, str] | None:
    """Kürzel und Klarname des Betriebs — oder ``None``, wenn unbekannt."""
    for key, (muster, name) in BETRIEBE.items():
        if re.search(muster, title, re.I):
            return key, name
    return None


def parse_wirtschaftsplan(template_number: str, title: str, text: str) -> Wirtschaftsplan | None:
    """Die Eckwerte aus dem Beschlusstext einer Wirtschaftsplan-Vorlage.

    ``None``, wenn der Beschlusstext keine Eckwerte trägt — der Normalfall
    außerhalb des EGH und **kein** Fehler (s. Modul-Docstring). Wirft
    :class:`WirtschaftsplanFehler`, wenn Eckwerte dastehen, aber die Probe
    reißt: Dann ist etwas falsch gelesen, und Schweigen wäre die schlechteste
    Antwort.
    """
    flach = _glaetten(text)

    werte: dict[str, float] = {}
    for field, muster in _ZEILEN.items():
        m = re.search(muster, flach)
        if m:
            werte[field] = _eur(m.group(1))

    # Ohne diese drei ist es kein Eckwert-Block. `taxes` darf fehlen (bis
    # 2020 gab es die Zeile nicht), `capital_plan` und `commitments`
    # ebenfalls — sie stehen in einem eigenen Absatz, den ein künftiges Layout
    # anders setzen könnte, ohne die Erfolgsplan-Zeilen zu berühren.
    if not {"revenues", "expenses", "result"} <= werte.keys():
        return None

    taxes = werte.get("taxes", 0.0)
    rest = werte["revenues"] - werte["expenses"] - taxes - werte["result"]
    if abs(rest) > TOLERANZ_EUR:
        raise WirtschaftsplanFehler(
            f"{template_number}: Erfolgsplan geht nicht auf — "
            f"{werte['revenues']:.2f} − {werte['expenses']:.2f} − {taxes:.2f} "
            f"≠ {werte['result']:.2f} (Restbetrag {rest:.2f} €)")

    m_jahr = _JAHR_TEXT.search(flach)
    if not m_jahr:
        raise WirtschaftsplanFehler(
            f"{template_number}: Eckwerte ohne Haushaltsjahr im Text — ohne Jahr "
            "gehören die Zahlen nirgendwohin")
    year = int(m_jahr.group(1))

    # Zweite Probe: Steht dasselbe Jahr im Titel? Der Titel führt oft auch die
    # Vorlagen-Jahreszahl („25/0722"), deshalb wird auf ENTHALTENSEIN geprüft
    # und nicht auf Gleichheit mit dem ersten Fund.
    titel_jahre = {int(j) for j in _JAHR_TITEL.findall(title)}
    if titel_jahre and year not in titel_jahre:
        raise WirtschaftsplanFehler(
            f"{template_number}: Haushaltsjahr {year} steht so nicht im Titel "
            f"(dort: {sorted(titel_jahre)}) — eines von beiden ist falsch gelesen")

    erkannt = betrieb_aus_titel(title)
    if not erkannt:
        raise WirtschaftsplanFehler(
            f"{template_number}: Eckwerte gefunden, aber der Betrieb ist unbekannt — "
            f"Titel: {title!r}. Erst in BETRIEBE eintragen.")
    key, name = erkannt

    m_entwurf = _ENTWURF.search(flach)
    return Wirtschaftsplan(
        enterprise=key, enterprise_name=name, year=year, template_number=template_number,
        revenues=werte["revenues"], expenses=werte["expenses"],
        taxes=taxes, result=werte["result"],
        capital_plan=werte.get("capital_plan"),
        commitments=werte.get("commitments"),
        draft_date=m_entwurf.group(1) if m_entwurf else None,
    )


def ohne_eckwerte(template_number: str, title: str) -> dict:
    """Eine Vorlage, die keine Eckwerte im Beschlusstext trägt — mit dem Grund.

    Damit die Lücke **gezählt** dasteht statt zu verschwinden: „38 von 46
    Wirtschaftsplänen nennen im Beschlusstext keine Zahl" ist eine Auskunft,
    ein stilles Überspringen wäre keine."""
    erkannt = betrieb_aus_titel(title)
    return {
        "template_number": template_number,
        "enterprise": erkannt[0] if erkannt else None,
        "enterprise_name": erkannt[1] if erkannt else None,
        "title": title,
        "reason": "Der Beschlusstext stimmt der anliegenden Fassung zu, ohne die "
                 "Eckwerte zu nennen — die Zahlen stehen in der Anlage.",
    }


def dokument_name(plan: Wirtschaftsplan) -> str:
    """Wie das Dokument im Quellenverzeichnis heißen soll.

    Bis zum 21.08.2026 stand hier ``f"Vorlage {plan.template_number}"``, und das
    Verzeichnis von ``/haushalt/betriebe`` listete für den Jahrgang 2026 fünf
    Links namens „Vorlage 25/0722", „Vorlage 25/0818/1", „Vorlage 25/0819" …
    — fünf verschiedene Dokumente, aber keines sagte, WESSEN Plan es ist. Tim
    am selben Tag: „eigentlich sollte es hier auch unterschiedliche Quellen
    geben für die unterschiedlichen Wirtschaftspläne der unterschiedlichen
    Eigenbetriebe."

    Das Aktenzeichen geht dabei nicht verloren: Es steht in der Vorgangszeile
    unter jedem Beleg („Der Rat hat das am … beschlossen · Vorlage 25/0722").
    Was dort fehlte, war der Name — und der ist es, wonach man sucht.

    ACHTUNG, das ändert den Herkunfts-Fingerabdruck (``Herkunft.key``
    schließt ``label`` ein): Der nächste Einlesevorgang legt neue Zeilen in
    ``council_herkunft`` an und hängt die Daten dort ein. Die alten bleiben
    unreferenziert liegen — sichtbar wird davon nichts."""
    return f"{plan.enterprise_name}: Wirtschaftsplan {plan.year}"


def herkunft_fuer(plan: Wirtschaftsplan, url: str | None,
                  document_id: int | None = None) -> Herkunft:
    """Die Herkunft einer Zeile: die Vorlage selbst, nicht eine Anlage."""
    return Herkunft(
        art="ris",
        probe=[PROBE_ERFOLGSPLAN, PROBE_JAHR],
        document_id=document_id,
        label=dokument_name(plan),
        url=url,
        citation="Beschlussvorschlag der Vorlage",
        probe_result=plan.probe_result,
        as_of=(f"Verwaltungsentwurf vom {plan.draft_date}"
               if plan.draft_date else "Fassung der Einbringung"),
    )
