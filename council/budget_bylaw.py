"""Die Haushaltssatzung — der Rahmen, den die Zahlen des Haushalts bekommen.

Drei Größen des Haushalts-Bereichs standen bisher nirgends, obwohl sie in einem
dreiseitigen Dokument je Jahrgang stehen:

* **§ 2 — Kredite für Investitionen.** Wie viel die Stadt sich für Investitionen
  leihen darf. In allen acht gelesenen Jahrgängen: gar nichts.
* **§ 4 — Liquiditätskredite.** Der Höchstbetrag für den Dispo der Stadt.
  60 Mio. € (2019/2020) → 95 Mio. (2021) → 60 Mio. (2023) → 100 Mio. (ab 2024).
* **§ 1.2 — der Finanzhaushalt im Ganzen.** Der Bereich las bisher nur die
  Investitionen daraus; die laufende Verwaltungstätigkeit und die
  Finanzierungstätigkeit fehlten.

DIE SATZUNG PRÜFT SICH SELBST. Unter § 1 steht „Nachrichtlich: Gesamtbetrag der
Einzahlungen des Finanzhaushaltes …", und dieser Betrag ist die Summe der drei
Einzahlungszeilen darüber. Dasselbe für die Auszahlungen. Über alle acht
Jahrgänge geht diese Probe **cent-genau** auf — sie ist der Grund, dass diese
Schicht ohne Zweitquelle auskommt.

WAS HIER STEHT, IST NICHT BESCHLOSSEN. Alle neun Dokumente im Bestand tragen
auf dem Deckblatt „Verwaltungsentwurf", und ihr Satzungstext nennt als
Sitzungsdatum „xx.xx.20xx" — eine Vorlage, kein Beschluss. Die beschlossene
Fassung wird im Amtsblatt veröffentlicht, nicht im Ratsinformationssystem.
Deshalb trägt **jede** Zeile ``version='draft'``, und jede Anzeige muss das
mitführen: Was der Rat daraus macht, steht auf `/haushalt/streit`.

Der Jahrgang **2026** ist die eine Ausnahme mit einem echten Datum
(15.12.2025) — aber auch sein Deckblatt sagt „Verwaltungsentwurf". Das Datum
ist die geplante Sitzung, nicht ihr Ergebnis. Wer es als Beleg nähme, machte
aus einem Vorschlag einen Beschluss.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from council.herkunft import Herkunft

PROBE_FINANZHAUSHALT = "satzung_finanzhaushalt"
PROBE_HEBESATZ = "satzung_hebesatz"

PROBEN: dict[str, str] = {
    PROBE_FINANZHAUSHALT:
        "Die Satzung nennt unter § 1 die drei Einzahlungs- und die drei "
        "Auszahlungszeilen des Finanzhaushalts einzeln und darunter noch "
        "einmal ihre Summe („Nachrichtlich“). Beide Summen sind nachgerechnet.",
    PROBE_HEBESATZ:
        "Der Hebesatz aus § 5 steht auch in Tabelle 1105 des Statistischen "
        "Jahrbuchs — zwei Dokumente aus zwei Häusern.",
}

#: Cent-genau. Die Satzung führt volle Euro ohne Nachkommastellen, und ihre
#: eigene Summenzeile ging in allen acht Jahrgängen exakt auf. Eine Toleranz
#: wäre hier keine Vorsicht, sondern ein blinder Fleck.
TOLERANZ_EUR = 0.005


class SatzungFehler(RuntimeError):
    """Eine Satzung, deren eigene Summenzeile nicht aufgeht."""


#: Beträge stehen mal mit „Euro", mal mit „EUR" — die älteren Jahrgänge (2019,
#: 2020) schreiben durchgängig „EUR". Dieselbe Falle wie beim Eigenbetrieb
#: Hafen, und sie ist lautlos: Ein Muster, das nur „Euro" kennt, findet in
#: diesen Jahrgängen einfach nichts.
_BETRAG = r"([\d.]+)\s*(?:Euro|EUR|€)"


def _eur(roh: str) -> float:
    return float(roh.replace(".", "").replace(" ", ""))


def _glatt(text: str) -> str:
    """Zeilenumbrüche weg — die Satzung bricht mitten in Aufzählungspunkten um."""
    return " ".join((text or "").split())


# --------------------------------------------------------------------------
# Die Felder
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Haushaltssatzung:
    year: int
    #: 0 = die Satzung selbst, 1.. = Nachtrag. Nachträge liest dieses Modul
    #: (noch) nicht; das Feld hält den Platz und den Primärschlüssel frei.
    supplement: int
    #: Immer ``entwurf``, solange nur das Ratsinformationssystem die Quelle ist
    #: (s. Modul-Kopf). Der Wert ist bewusst kein Boolean: Käme je eine
    #: beschlossene Fassung dazu, stünde sie daneben und nicht an ihrer Stelle.
    version: str

    ordinary_revenues: float
    ordinary_expenses: float
    extraordinary_revenues: float
    extraordinary_expenses: float

    in_operating: float
    out_operating: float
    in_capital: float
    out_capital: float
    in_financing: float
    out_financing: float
    #: Die „Nachrichtlich"-Zeilen — nachgerechnet, nicht übernommen.
    in_total: float
    out_total: float

    #: § 2. ``0.0`` heißt „nicht veranschlagt" und ist eine Aussage;
    #: ``None`` hieße „der Paragraph fehlt", und das kam bisher nicht vor.
    investment_loans: float | None
    #: § 3.
    commitment_authorizations: float | None
    #: § 4 — der Dispo der Stadt.
    liquidity_loans: float | None

    #: § 5. Ab 2026 nennt die Satzung nur noch die Gewerbesteuer und verweist
    #: für die Grundsteuer auf eine eigene Satzung — die beiden Felder sind
    #: dann leer, und das ist die Auskunft, keine Lücke im Einlesen.
    property_tax_a_rate: int | None
    property_tax_b_rate: int | None
    trade_tax_rate: int | None

    #: Das im Text genannte Sitzungsdatum, ``None`` bei „xx.xx.20xx".
    session_date: str | None
    template_number: str | None


# --------------------------------------------------------------------------
# Lesen
# --------------------------------------------------------------------------

_JAHR = re.compile(r"f[üu]r das Haushaltsjahr (\d{4})")
_SITZUNG = re.compile(r"in der Sitzung am\s*(\d{2}\.\d{2}\.\d{4})")
_ENTWURF = re.compile(r"Verwaltungsentwurf|Haushaltsentwurf|xx\.xx", re.I)

_ERGEBNIS = {
    "ordinary_revenues": r"1\.1 der ordentlichen Ertr[äa]ge auf\s*",
    "ordinary_expenses": r"1\.2 der ordentlichen Aufwendungen auf\s*",
    "extraordinary_revenues": r"1\.3 der au[ßs]erordentlichen Ertr[äa]ge auf\s*",
    "extraordinary_expenses": r"1\.4 der au[ßs]erordentlichen Aufwendungen auf\s*",
}
_FINANZ = {
    "in_operating": r"2\.1 der Einzahlungen aus laufender Verwaltungst[äa]tigkeit\s*",
    "out_operating": r"2\.2 der Auszahlungen aus laufender Verwaltungst[äa]tigkeit\s*",
    "in_capital": r"2\.3 der Einzahlungen f[üu]r Investitionst[äa]tigkeit\s*",
    "out_capital": r"2\.4 der Auszahlungen f[üu]r Investitionst[äa]tigkeit\s*",
    "in_financing": r"2\.5 der Einzahlungen f[üu]r Finanzierungst[äa]tigkeit\s*",
    "out_financing": r"2\.6 der Auszahlungen f[üu]r Finanzierungst[äa]tigkeit\s*",
}
_NACHRICHTLICH_EIN = re.compile(
    r"Gesamtbetrag der Einzahlungen des Finanzhaushaltes\s*" + _BETRAG)
_NACHRICHTLICH_AUS = re.compile(
    r"Gesamtbetrag der Auszahlungen des Finanzhaushaltes\s*" + _BETRAG)

_KREDITE_KEINE = re.compile(
    r"Kredite f[üu]r Investitionen[^§]{0,120}?(?:werden )?nicht veranschlagt", re.I)
_KREDITE_BETRAG = re.compile(
    r"Kredite f[üu]r Investitionen[^§]{0,160}?auf\s*" + _BETRAG, re.I)
_VE = re.compile(
    r"Gesamtbetrag der Verpflichtungserm[äa]chtigungen wird auf\s*" + _BETRAG, re.I)
_LIQUI = re.compile(
    r"Liquidit[äa]tskredite[^§]{0,220}?festgesetzt", re.I)
_LIQUI_BETRAG = re.compile(
    r"Liquidit[äa]tskredite[^§]{0,200}?auf\s*" + _BETRAG, re.I)

_HEBESATZ = r"(\d{2,4})\s*v\.?\s*H\.?"
_GRUNDSTEUER_A = re.compile(r"Grundsteuer A\)?\s*" + _HEBESATZ, re.I)
_GRUNDSTEUER_B = re.compile(r"Grundsteuer B\)?\s*" + _HEBESATZ, re.I)
_GEWERBESTEUER = re.compile(r"Gewerbesteuer(?:\s+wird[^.]{0,80}?auf)?\s*" + _HEBESATZ, re.I)


def _pflichtbetrag(text: str, muster: str, field: str) -> float:
    treffer = re.search(muster + _BETRAG, text)
    if treffer is None:
        raise SatzungFehler(
            f"Zeile '{field}' steht nicht in der Satzung (gesucht: {muster!r}) — "
            "vermutlich ein anderes Layout, und dann ist keine Zuordnung sicher.")
    return _eur(treffer.group(1))


def _zahl(muster: re.Pattern, text: str) -> int | None:
    treffer = muster.search(text)
    return int(treffer.group(1)) if treffer else None


def parse_satzung(text: str, template_number: str | None = None) -> Haushaltssatzung:
    """Eine Haushaltssatzung lesen — geprüft an ihrer eigenen Summenzeile.

    Wirft :class:`SatzungFehler`, wenn die Summe nicht aufgeht. Eine Satzung,
    deren sechs Finanzhaushalts-Zeilen nicht ihre eigene Gesamtsumme ergeben,
    ist entweder falsch gelesen oder ein Nachtrag mit anderer Tabelle — in
    beiden Fällen hat sie im Bestand nichts verloren.
    """
    t = _glatt(text)

    year = _JAHR.search(t)
    if year is None:
        raise SatzungFehler("Kein Haushaltsjahr im Text („für das Haushaltsjahr JJJJ“)")
    if "Nachtragshaushaltssatzung" in t:
        raise SatzungFehler(
            "Nachtragshaushaltssatzung — sie führt eine ganz andere Tabelle "
            "(bisher / erhöht um / vermindert um / Gesamtbetrag) und wird von "
            "diesem Modul bewusst nicht gelesen.")

    werte = {field: _pflichtbetrag(t, muster, field)
             for field, muster in {**_ERGEBNIS, **_FINANZ}.items()}

    ne, na = _NACHRICHTLICH_EIN.search(t), _NACHRICHTLICH_AUS.search(t)
    if ne is None or na is None:
        raise SatzungFehler(
            "Die „Nachrichtlich“-Zeilen fehlen — ohne sie prüft diese Schicht "
            "nichts nach, und eine ungeprüfte Zahl wird nicht gespeichert.")
    in_total, out_total = _eur(ne.group(1)), _eur(na.group(1))

    total_in = werte["in_operating"] + werte["in_capital"] + werte["in_financing"]
    total_out = werte["out_operating"] + werte["out_capital"] + werte["out_financing"]
    for name, gerechnet, gedruckt in (("Einzahlungen", total_in, in_total),
                                      ("Auszahlungen", total_out, out_total)):
        if abs(gerechnet - gedruckt) > TOLERANZ_EUR:
            raise SatzungFehler(
                f"{name} des Finanzhaushalts: Die drei Zeilen ergeben "
                f"{gerechnet:,.2f} €, die Satzung schreibt {gedruckt:,.2f} € — "
                "zwei Stellen desselben Dokuments widersprechen sich.")

    kredite: float | None = None
    if _KREDITE_KEINE.search(t):
        kredite = 0.0
    elif (m := _KREDITE_BETRAG.search(t)):
        kredite = _eur(m.group(1))

    liqui: float | None = None
    if _LIQUI.search(t) and (m := _LIQUI_BETRAG.search(t)):
        liqui = _eur(m.group(1))

    commitment_authorizations = _VE.search(t)

    return Haushaltssatzung(
        year=int(year.group(1)), supplement=0,
        # Der Bestand kennt nur Entwürfe (s. Modul-Kopf). Sollte je ein
        # Dokument ohne jeden Entwurfs-Vermerk auftauchen, heißt es hier
        # `unbekannt` und NICHT `beschlossen` — behauptet wird nichts.
        version="draft" if _ENTWURF.search(text) else "unknown",
        **werte,
        in_total=in_total, out_total=out_total,
        investment_loans=kredite,
        commitment_authorizations=_eur(commitment_authorizations.group(1)) if commitment_authorizations else None,
        liquidity_loans=liqui,
        property_tax_a_rate=_zahl(_GRUNDSTEUER_A, t),
        property_tax_b_rate=_zahl(_GRUNDSTEUER_B, t),
        trade_tax_rate=_zahl(_GEWERBESTEUER, t),
        session_date=(m.group(1) if (m := _SITZUNG.search(t)) else None),
        template_number=template_number,
    )


def herkunft_fuer(satzung: Haushaltssatzung, *, url: str | None,
                  document_id: int | None, label: str | None,
                  hebesatz_geprueft: str | None = None) -> Herkunft:
    """Die Herkunft: die Anlage, und was an ihr nachgerechnet wurde."""
    probes = [PROBE_FINANZHAUSHALT]
    result = (f"Einzahlungen {satzung.in_total:,.0f} € und Auszahlungen "
                f"{satzung.out_total:,.0f} € aus je drei Zeilen nachgerechnet")
    if hebesatz_geprueft:
        probes.append(PROBE_HEBESATZ)
        result += f"; {hebesatz_geprueft}"
    return Herkunft(
        kind="ris",
        probe=probes,
        document_id=document_id,
        label=label or f"Haushaltssatzung {satzung.year}",
        url=url,
        citation=f"Haushaltssatzung {satzung.year}, §§ 1–5",
        probe_result=result,
        # Die Fassung gehört in den STAND und nicht in eine Fußnote: Wer diese
        # Zahlen liest, liest einen Vorschlag der Verwaltung.
        as_of=(f"Haushaltssatzung {satzung.year}, "
               + ("Verwaltungsentwurf" if satzung.version == "draft"
                  else "Fassung unbekannt")),
    )
