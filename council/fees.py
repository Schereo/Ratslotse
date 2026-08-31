"""Die Gebührenbedarfsberechnung — warum die Müllabfuhr kostet, was sie kostet.

Von allen Zahlen des Haushalts landet keine so direkt im Portemonnaie wie die
Abfall- und Straßenreinigungsgebühr. Wie sie zustande kommt, steht jedes Jahr
in einer Anlage zur Ratsvorlage — und diese Anlage ist das am besten
prüfbare Dokument im ganzen Bestand.

DREI BEREICHE JE JAHRGANG, alle nach demselben Muster:

* **Anlage 1 — Abfallbehandlungsanlagen**, Gebühr je Tonne (Mg)
* **Anlage 2 — Abfallsammlung**, Bezugsgröße ist das Behältervolumen in Litern
* **Anlage 3 — Straßenreinigung**, Gebühr je Meter Quadratwurzel

ZWEI PROBEN, BEIDE AUS DEM DOKUMENT SELBST:

1. **Die Kaskade.** Die Kalkulationskosten minus alle Abzüge ergeben die
   Kosten, die durch Gebühren zu decken sind. Über elf geprüfte Blöcke geht
   das neunmal cent-genau auf und zweimal um genau 1 € daneben — dieselbe
   Rundungs-Signatur wie beim Erfolgsplan des Abfallwirtschaftsbetriebs,
   für die ``TOLERANZ_EUR`` da ist.
2. **Die Division.** Zu deckende Kosten geteilt durch die Bezugsmenge ergibt
   die gedruckte Gebühr. Sie ist unabhängig von der ersten, weil Menge und
   Gebühr an anderer Stelle stehen als die Kaskade.

DIE ZWEITE PROBE MACHT DIE ARBEIT DER ERSTEN MIT. Im Textextrakt zerreißen
Zahlen an Leerzeichen — „-295. 000 €" im Jahrgang 2026, „7 71.000" in der
Straßenreinigung desselben Jahres. Das erste repariert :func:`_glaetten`; beim
zweiten ist nicht sicher zu entscheiden, wo die Zahl anfängt. Deshalb wird die
Bezugsmenge nicht geraten, sondern **an der Division erkannt**: Von allen
Kandidaten im Text gilt die, die zusammen mit den zu deckenden Kosten die
gedruckte Gebühr ergibt. Zwei unabhängig gesetzte Stellen müssen sich einig
sein, sonst gibt es keine Zeile.

ANLAGE 4 IST DIE TARIFSCHICHT. Sie führt zwölf fest benannte Gebührenarten:
unter anderem Grundgebühr, allgemeine Litergebühr, Biogrundmenge sowie die
Karten und Anlieferungsmengen. Bis 2025 steht das jeweilige Vorschlagsjahr in
einer kompakten Zeile; 2026 wechselt die Tabelle in zwölf Zeilen und rechnet
für jede die Veränderung zum Vorjahr vor. Beide Layouts werden gelesen. Eine
frei kombinierbare Matrix aus Behältergröße und Abfuhrrhythmus steht dort
hingegen nicht — der Parser erfindet sie deshalb auch nicht.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from council.herkunft import Herkunft

PROBE_KASKADE = "gebuehren_kaskade"
PROBE_DIVISION = "gebuehren_division"
PROBE_SATZANZAHL = "gebuehrensaetze_anzahl"
PROBE_ECKWERTE = "gebuehrensaetze_eckwerte"
PROBE_VORJAHRESVERGLEICH = "gebuehrensaetze_vorjahresvergleich"

PROBEN: dict[str, str] = {
    PROBE_KASKADE:
        "Die Kalkulationskosten minus alle Abzüge ergeben die Kosten, die "
        "durch Gebühren zu decken sind — nachgerechnet mit den Abzügen, die "
        "das Dokument selbst benennt.",
    PROBE_DIVISION:
        "Die zu deckenden Kosten, geteilt durch die Bezugsmenge, ergeben die "
        "gedruckte Gebühr. Menge und Gebühr stehen an anderer Stelle als die "
        "Kaskade — zwei unabhängige Angaben desselben Dokuments.",
    PROBE_SATZANZAHL:
        "Anlage 4 enthält jede der zwölf benannten Tarifarten genau einmal.",
    PROBE_ECKWERTE:
        "Die beiden Eckwerte der Tarifübersicht stimmen mit den getrennten "
        "Berechnungen in Anlagen 1 und 3 überein.",
    PROBE_VORJAHRESVERGLEICH:
        "Neuer Satz und Vorjahressatz ergeben die in Anlage 4 gedruckte "
        "prozentuale Veränderung.",
}

#: Wie beim Erfolgsplan des AWB. Gemessen an elf Kaskaden: neun gehen auf den
#: Cent auf, zwei um genau 1 € daneben — das Dokument rundet seine Abzüge.
TOLERANZ_EUR = 2.0

#: Die Gebühr steht mit drei Nachkommastellen („151,214 €"), der Vorschlag
#: darunter mit zwei („151,21 €"). Geprüft wird gegen die dreistellige, und
#: ein halber Cent Abstand ist die Rundung der letzten Stelle.
TOLERANZ_GEBUEHR = 0.0011


class GebuehrenFehler(RuntimeError):
    """Eine Berechnung, die ihrer eigenen Rechnung widerspricht."""


BEREICHE: dict[str, tuple[str, str]] = {
    # Kürzel → (Muster im Anlagenkopf, Name für die Anzeige)
    "abfallbehandlung": (r"Abfallbehandlungsanlagen", "Abfallbehandlungsanlagen"),
    "abfallsammlung": (r"Abfallsammlung", "Abfallsammlung"),
    "strassenreinigung": (r"Stra[ßs]enreinigung", "Straßenreinigung"),
}

#: Die Einheit, in der die Bezugsmenge gemessen wird — sie steht im Dokument
#: und wird nicht aus dem Bereich abgeleitet: Das wäre eine Behauptung über
#: ein Dokument, das man nicht gelesen hat.
#: Reihenfolge zählt: „Meter Quadratwurzel" muss vor „Meter" stehen, sonst
#: gewinnt die kürzere Form.
EINHEITEN = (
    (r"Meter\s+Quadratwurzel", "Meter Quadratwurzel"),
    (r"Mg", "Mg"),
    (r"Liter", "Liter"),
    (r"m²", "m²"),
)


def _einheit_aus(roh: str) -> str | None:
    """Aus dem eingefangenen Text die EINHEIT herausschälen.

    Die Erfassung greift zwangsläufig zu weit: Im Jahrgang 2024 stehen
    Beschriftungen und Beträge getrennt, und zwischen „je Mg" und der Zahl
    liegt das Wort „Gebührenvorschlag". Ein freier Text als Einheit stünde
    dann so in der Datenbank.
    """
    for muster, name in EINHEITEN:
        if re.search(r"\b" + muster + r"\b", roh, re.IGNORECASE):
            return name
    return None


# --------------------------------------------------------------------------
# Text vorbereiten
# --------------------------------------------------------------------------

#: Leerzeichen zwischen Tausenderpunkt und Dreiergruppe: „-295. 000 €".
#: Hier IST entscheidbar, dass die Zahl weitergeht — vor dem Punkt steht eine
#: Ziffer, dahinter genau drei. Beim umgekehrten Fall („7 71.000") ist es das
#: nicht, und deshalb wird dort nicht repariert, sondern geprüft (s. Modulkopf).
_ZERRISSEN = re.compile(r"(?<=\d\.)\s+(?=\d{3}(?!\d))")

_BETRAG = r"(-\s?[\d.]+(?:,\d+)?|[\d.]+(?:,\d+)?)\s*€"
_BETRAG_RE = re.compile(_BETRAG)


def _eur(roh: str) -> float:
    return float(roh.replace(" ", "").replace(".", "").replace(",", "."))


def _glaetten(text: str) -> str:
    return _ZERRISSEN.sub("", " ".join((text or "").split()))


# --------------------------------------------------------------------------
# Die Felder
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Gebuehrenbedarf:
    year: int
    area: str
    area_name: str
    #: Was der Bereich im Haushaltsjahr insgesamt kostet.
    cost_calculation: float
    #: Alles, was davon abgezogen wird — negativ. Erstattungen Dritter,
    #: Erlöse, Rückstellungen und die Über-/Unterdeckung aus Vorjahren.
    deductions: float
    #: Was die Gebührenzahler tragen.
    costs_to_cover: float
    #: Wonach die Gebühr bemessen wird (Tonnen, Liter, Meter Quadratwurzel).
    #: ``None`` bei der Abfallsammlung: Sie erhebt eine Grundgebühr UND eine
    #: Gebühr je Liter, es gibt dort also keine einzelne Division. Die
    #: Kaskade ist trotzdem geprüft.
    reference_quantity: float | None
    reference_unit: str | None
    fee: float | None
    #: Der gerundete Vorschlag an den Rat — das, was am Ende erhoben wird.
    #: ``None``, wo das Dokument ihn nicht gesondert ausweist.
    fee_proposed: float | None
    template_number: str | None


@dataclass(frozen=True)
class Gebuehrensatz:
    """Ein ausdrücklich benannter Tarif aus Anlage 4.

    ``amount`` ist ein Vorschlag der Verwaltung, nicht automatisch der vom
    Rat beschlossene Satz. Diese Unterscheidung reist bis zur Herkunft mit.
    """

    year: int
    key: str
    area: str
    label: str
    amount: float
    unit: str
    prior_year: float | None
    change_pct: float | None
    template_number: str | None


@dataclass(frozen=True)
class _Satzart:
    key: str
    area: str
    code: str
    label: str
    unit: str
    modernes_muster: str


# Reihenfolge = Spaltenreihenfolge der Tabellen 2023–2025. Dieselben zwölf
# Bezeichnungen stehen 2026 als Zeilen. Die Einheiten sind keine Ableitung,
# sondern stammen aus deren Kopf bzw. Bezeichnung.
SATZARTEN: tuple[_Satzart, ...] = (
    _Satzart("abfallbehandlung_mg", "abfallbehandlung", "AB", "Gebühr je Mg",
             "Mg", r"Geb[üu]hr je Mg"),
    _Satzart("grundgebuehr", "abfallsammlung", "AS", "Grundgebühr",
             "Grundgebühr", r"Grundgeb[üu]hr"),
    _Satzart("litergebuehr", "abfallsammlung", "AS", "Allgemeine Litergebühr",
             "Liter Behältervolumen", r"Allg\.\s*Litergeb[üu]hr"),
    _Satzart("biogrundmenge_60l", "abfallsammlung", "AS", "Biogrundmenge 60 L",
             "60 L Biogrundmenge", r"Biogrundmenge\s+60\s*L"),
    _Satzart("sperrmuellkarte", "abfallsammlung", "AS", "Sperrmüllkarte",
             "Karte", r"Sperrm[üu]llkarte"),
    _Satzart("gruengutkarte", "abfallsammlung", "AS", "Grüngutkarte",
             "Karte", r"Gr[üu]ngutkarte"),
    _Satzart("sperrmuell_1m3", "abfallsammlung", "AS",
             "Sperrmüllanlieferung 1 m³", "Anlieferung 1 m³",
             r"Sperrm[üu]llanlieferung\s+1\s*m\s*³"),
    _Satzart("sperrmuell_2m3", "abfallsammlung", "AS",
             "Sperrmüllanlieferung 2 m³", "Anlieferung 2 m³",
             r"Sperrm[üu]llanlieferung\s+2\s*m\s*³"),
    _Satzart("gruengut_05m3", "abfallsammlung", "AS",
             "Grüngutanlieferung bis 0,5 m³", "Anlieferung bis 0,5 m³",
             r"Gr[üu]ngutanlieferung\s+bis\s+0,5\s*m\s*³"),
    _Satzart("gruengut_1m3", "abfallsammlung", "AS",
             "Grüngutanlieferung bis 1 m³", "Anlieferung bis 1 m³",
             r"Gr[üu]ngutanlieferung\s+bis\s+1\s*m\s*³"),
    _Satzart("gruengut_2m3", "abfallsammlung", "AS",
             "Grüngutanlieferung bis 2 m³", "Anlieferung bis 2 m³",
             r"Gr[üu]ngutanlieferung\s+bis\s+2\s*m\s*³"),
    _Satzart("strassenreinigung_qw", "strassenreinigung", "SR",
             "Gebühr je Meter Quadratwurzel bei wöchentlicher Reinigung",
             "Meter Quadratwurzel", r"Geb[üu]hr je Meter Quadratwurzel"),
)


# --------------------------------------------------------------------------
# Lesen
# --------------------------------------------------------------------------

#: Der Jahrgang steht in der Überschrift des Abschnitts — in zwei
#: Schreibweisen. Ab 2023 heißt sie „Gebührenbedarfs**be**rechnung", der
#: Jahrgang 2020 schreibt „Gebührenbedarfsrechnung 2020"; beide Wörter stehen
#: sogar in derselben Datei nebeneinander (die Überschrift so, die
#: Erläuterungen darunter anders). Das ``be`` ist deshalb optional — die
#: Alternative wäre gewesen, einen ganzen Jahrgang liegen zu lassen, weil ein
#: Sachbearbeiter 2019 zwei Silben kürzer getippt hat.
_JAHR = re.compile(r"Geb[üu]hrenbedarfs(?:be)?rechnung\s+(\d{4})")
_KALKULATION = re.compile(r"Kostenkalkulation f[üu]r \d{4}\s*" + _BETRAG)
_ZU_DECKEN = re.compile(r"decken sind\s*" + _BETRAG)
#: Die Gebührenzeile MIT ihrer Einheit — beides in einem Griff.
#:
#: Die Einheit irgendwo im Anlagentext zu suchen ging schief: Im Abschnitt
#: Straßenreinigung steht „je Mg" in einem Querverweis, und die erste
#: Fundstelle gewann. Sie steht aber verlässlich neben der Gebühr selbst.
_GEBUEHR_MIT_EINHEIT = re.compile(
    r"(?:Ergebnis/)?Geb[üu]hr\s*(?:rd\.)?\s*je\s+([A-Za-zÄÖÜäöüß² ]{1,24}?)\s*"
    r"([\d.]+,\d{2,3})\s*€", re.I)
_VORSCHLAG = re.compile(r"Geb[üu]hrenvorschlag[^0-9]{0,30}?([\d.]+,\d{2})\s*€", re.I)
# Im Jahrgang 2020 ist die Überdeckung positiv gedruckt, obwohl sie in der
# Kaskade abgezogen wird. Der Erläuterungstext bestätigt ausdrücklich, dass
# 280.500 € aus der Überdeckung 2017 eingesetzt werden. Wir drehen das
# Vorzeichen trotzdem nicht allein aufgrund des Wortes: Nur wenn genau dieser
# Betrag den Rest der dokumentierten Kaskade schließt, darf er als Abzug
# gelten. So bleibt ein OCR- oder Layoutfehler ein harter Riss.
_UEBER_UNTERDECKUNG = re.compile(
    r"[ÜUu]ber-/Unterdeckung\s+aus\s+Vorjahren\s*" + _BETRAG, re.I)

#: Die ERRECHNETE Gebühr trägt drei Nachkommastellen („134,709 €"), der
#: gerundete Vorschlag darunter zwei („134,70 €"). Wo der Textextrakt
#: Beschriftungen und Beträge trennt (2024), ist das der einzige Unterschied,
#: an dem sich die beiden noch auseinanderhalten lassen — und die Division
#: entscheidet danach, ob es die richtige war.
_GEBUEHR_DREISTELLIG = re.compile(r"([\d.]+,\d{3})\s*€")

#: Alles, was eine Bezugsmenge sein könnte: eine Zahl OHNE €-Zeichen. Welche
#: es ist, entscheidet die Division und nicht dieses Muster.
_MENGE = re.compile(r"(?<![\d,.])([\d.]{3,})(?!\s*€)(?![\d,.])")

# Tarifbeträge in der alten Anlage-4-Tabelle. Dort fehlen Eurozeichen in den
# Datenzeilen und glatte Beträge stehen als „50,--" bzw. „3,-". Jahreszahlen
# treffen das Muster absichtlich nicht.
_SATZ_BETRAG = re.compile(
    r"(?<![\d,.])(\d{1,3}(?:\.\d{3})*(?:,\d{1,2}|,--|,-))(?![\d,.])")
_SATZ_BETRAG_EURO = r"([\d.]+,\d{2})\s*€"


def _bereich_aus_kopf(text: str) -> tuple[str, str] | None:
    for key, (muster, name) in BEREICHE.items():
        if re.search(r"-\s*" + muster + r"\s*-", text):
            return key, name
    return None


def teile_anlagen(text: str) -> list[str]:
    """Den Volltext in seine Anlagen zerlegen.

    Getrennt wird am Kopf „Anlage N - Bereich -", nicht an Seitenzahlen: Eine
    Anlage geht über mehrere Seiten, und die Erläuterungen dahinter gehören
    noch zu ihr.
    """
    flach = _glaetten(text)
    teile = re.split(r"(?=Anlage [1-4]\s+-\s*[A-ZÄÖÜ])", flach)
    return [t for t in teile if _bereich_aus_kopf(t)]


def _menge_aus_der_probe(part: str, zu_decken: float, fee: float) -> float:
    """Die Bezugsmenge daran erkennen, dass sie die gedruckte Gebühr ergibt.

    NICHT geraten und nicht die erste passende Zahl genommen: Im Textextrakt
    zerreißen Zahlen an Leerzeichen („7 71.000" für 771.000), und welche
    Ziffernfolge gemeint ist, steht nirgends. Was aber dasteht, ist die
    Gebühr — und die kennt nur eine Menge.
    """
    # Kandidat MIT Fundstelle: Die Lage entscheidet später den Gleichstand,
    # und eine zusammengesetzte Zahl („7 71.000") ließe sich hinterher nicht
    # mehr im Text wiederfinden.
    kandidaten: list[tuple[float, int]] = []
    for m in _MENGE.finditer(part):
        try:
            value = float(m.group(1).replace(".", ""))
        except ValueError:
            continue
        if value > 0:
            kandidaten.append((value, m.start()))
    # Und die im Textextrakt zerrissenen Formen.
    for m in re.finditer(r"(?<![\d,.])(\d{1,3})\s+([\d.]{3,})(?!\s*€)", part):
        try:
            kandidaten.append((float((m.group(1) + m.group(2)).replace(".", "")),
                               m.start()))
        except ValueError:
            continue

    treffer = [(w, pos) for w, pos in kandidaten
               if w and abs(zu_decken / w - fee) <= TOLERANZ_GEBUEHR]
    if not treffer:
        raise GebuehrenFehler(
            f"Keine Bezugsmenge im Text ergibt die gedruckte Gebühr "
            f"({fee:.3f} aus {zu_decken:.2f} €) — die Division lässt sich "
            "nicht nachrechnen, also wird nichts gespeichert.")
    werte = {w for w, _ in treffer}
    if len(werte) == 1:
        return treffer[0][0]

    # MEHRERE WERTE, UND DAS IST KEIN PARSERFEHLER: Die Gebühr steht mit drei
    # Nachkommastellen da, und 3.114.327 ÷ 770.900 wie ÷ 771.000 ergeben beide
    # 4,039. Zwei Zahlen, die auf die gedruckte Genauigkeit dasselbe sagen,
    # lassen sich an der Division nicht unterscheiden.
    #
    # Entschieden wird deshalb an der LAGE: Die Bezugsmenge steht im
    # „Gebührenermittlung"-Block unmittelbar über der Gebühr. Das ist eine
    # Aussage über den Aufbau des Dokuments, keine über die Zahl.
    g = _GEBUEHR_MIT_EINHEIT.search(part)
    davor = [(pos, w) for w, pos in treffer if g and pos < g.start()]
    if not davor:
        raise GebuehrenFehler(
            f"Mehrere Bezugsmengen ergäben die Gebühr {fee:.3f}: "
            f"{sorted(werte)}, und keine steht vor der Gebührenzeile — "
            "nicht entscheidbar.")
    return max(davor)[1]


def _kaskade_aus_der_reihenfolge(part: str) -> tuple[float, float, float] | None:
    """Kalkulation, Abzüge und Deckungsbetrag aus der REIHENFOLGE der Beträge.

    Der Notweg für Jahrgänge, in denen der Textextrakt Beschriftungen und
    Beträge in getrennte Blöcke legt — im Jahrgang 2024 stehen erst alle
    Zahlen der Anlage 1 und danach erst ihre Zeilennamen. Ein Muster, das die
    Zahl neben ihrer Beschriftung sucht, findet dort nichts.

    Geraten wird trotzdem nicht: Die Zuordnung gilt nur, wenn sie die Kaskade
    des Dokuments erfüllt. Genommen wird der LETZTE positive Betrag, der
    aufgeht — die früheren sind Zwischensummen („Gebührenwirksame Kosten"),
    und die Deckungszeile steht hinter allen Abzügen.
    """
    # Leere Treffer überspringen: Das Betrags-Muster lässt eine leere
    # Ziffernfolge zu, wenn im Extrakt nur ein „€" ohne Zahl steht.
    betraege: list[tuple[float, int]] = []
    for m in _BETRAG_RE.finditer(part):
        roh = m.group(1).strip()
        if not roh.strip("-. "):
            continue
        try:
            betraege.append((_eur(roh), m.start()))
        except ValueError:
            continue
    if len(betraege) < 3 or betraege[0][0] <= 0:
        return None
    kalkulation = betraege[0][0]
    gefunden = None
    laufend = 0.0
    for value, _ in betraege[1:]:
        if value < 0:
            laufend += value
        elif abs(kalkulation + laufend - value) <= TOLERANZ_EUR:
            gefunden = (kalkulation, laufend, value)
    return gefunden


def parse_anlage(part: str, template_number: str | None = None) -> Gebuehrenbedarf:
    """Eine Anlage lesen — geprüft, oder gar nicht."""
    area = _bereich_aus_kopf(part)
    if area is None:
        raise GebuehrenFehler("Kein bekannter Bereich im Anlagenkopf")
    year = _JAHR.search(part)
    if year is None:
        raise GebuehrenFehler("Kein Jahrgang („Gebührenbedarfsberechnung JJJJ“)")

    k = _KALKULATION.search(part)
    d = _ZU_DECKEN.search(part)
    if k and d:
        kalkulation, zu_decken = _eur(k.group(1)), _eur(d.group(1))
        kaskade = part[k.end():d.start()]
        deductions = sum(_eur(x) for x in _BETRAG_RE.findall(kaskade)
                      if x.strip().startswith("-"))
        rest = kalkulation + deductions - zu_decken
        ueberdeckung = _UEBER_UNTERDECKUNG.search(kaskade)
        if ueberdeckung is not None:
            value = _eur(ueberdeckung.group(1))
            if value > 0 and abs(rest - value) <= TOLERANZ_EUR:
                deductions -= value
    else:
        # Beschriftungen und Beträge stehen in getrennten Blöcken (2024).
        ueber_reihenfolge = _kaskade_aus_der_reihenfolge(part)
        if ueber_reihenfolge is None:
            raise GebuehrenFehler(
                "Kaskade unvollständig: "
                + ("Kostenkalkulation fehlt. " if not k else "")
                + ("Zeile „zu decken sind“ fehlt. " if not d else "")
                + "Auch über die Reihenfolge der Beträge geht keine Kaskade auf.")
        kalkulation, deductions, zu_decken = ueber_reihenfolge
    rest = kalkulation + deductions - zu_decken
    if abs(rest) > TOLERANZ_EUR:
        raise GebuehrenFehler(
            f"{area[1]} {year.group(1)}: Kalkulation {kalkulation:,.2f} € "
            f"und Abzüge {deductions:,.2f} € ergeben {kalkulation + deductions:,.2f} €, "
            f"die Zeile nennt {zu_decken:,.2f} € — Rest {rest:+,.2f} €.")

    # NICHT JEDER BEREICH HAT EINE EINZELNE GEBÜHR. Die Abfallsammlung
    # erhebt eine Grundgebühr UND eine Gebühr je Liter Behältervolumen; eine
    # Division „zu deckende Kosten ÷ Menge" gibt es dort nicht, und eine
    # erfundene wäre schlimmer als keine. Der Jahrgang wird trotzdem
    # gespeichert — seine Kaskade ist geprüft, nur die zweite Probe fehlt.
    g = _GEBUEHR_MIT_EINHEIT.search(part)
    fee = menge = None
    unit = None
    if g is not None:
        unit = _einheit_aus(g.group(1))
        if unit is None:
            raise GebuehrenFehler(
                f"{area[1]} {year.group(1)}: Unbekannte Bezugseinheit "
                f"„{' '.join(g.group(1).split())}“ — eine erfundene Einheit "
                "wäre eine Behauptung über das Dokument.")
        fee = float(g.group(2).replace(".", "").replace(",", "."))
        try:
            menge = _menge_aus_der_probe(part, zu_decken, fee)
        except GebuehrenFehler:
            # Wahrscheinlich der gerundete VORSCHLAG erwischt statt der
            # errechneten Gebühr — das passiert, wo der Textextrakt
            # Beschriftungen und Beträge trennt. Die errechnete hat drei
            # Nachkommastellen; welche der Kandidaten es ist, entscheidet
            # wieder die Division und nicht die Reihenfolge.
            fee = menge = None
            for kandidat in _GEBUEHR_DREISTELLIG.findall(part):
                value = float(kandidat.replace(".", "").replace(",", "."))
                try:
                    menge = _menge_aus_der_probe(part, zu_decken, value)
                except GebuehrenFehler:
                    continue
                fee = value
                break
            if fee is None:
                raise
    v = _VORSCHLAG.search(part)

    return Gebuehrenbedarf(
        year=int(year.group(1)), area=area[0], area_name=area[1],
        cost_calculation=kalkulation, deductions=deductions,
        costs_to_cover=zu_decken, reference_quantity=menge, reference_unit=unit,
        fee=fee,
        fee_proposed=(float(v.group(1).replace(".", "").replace(",", "."))
                            if v else None),
        template_number=template_number,
    )


def lies(text: str, template_number: str | None = None
         ) -> tuple[list[Gebuehrenbedarf], list[str]]:
    """Alle Anlagen eines Dokuments lesen.

    Liefert ``(gelesen, risse)``. Ein gerissener Bereich nimmt die anderen
    nicht mit: Sie stehen in eigenen Anlagen und prüfen sich einzeln.
    """
    gelesen, risse = [], []
    for part in teile_anlagen(text):
        try:
            gelesen.append(parse_anlage(part, template_number))
        except GebuehrenFehler as fehler:
            risse.append(str(fehler))
    return gelesen, risse


# --------------------------------------------------------------------------
# Anlage 4 — die zwölf konkreten Tarife
# --------------------------------------------------------------------------

def _satz_eur(roh: str) -> float:
    roh = roh.replace(",--", ",00").replace(",-", ",00")
    return float(roh.replace(".", "").replace(",", "."))


def _anlage_4(text: str) -> str | None:
    flach = _glaetten(text)
    treffer = list(re.finditer(r"\bAnlage\s+4\b", flach, re.I))
    return flach[treffer[-1].end():] if treffer else None


def _saetze_altes_layout(part: str, template_number: str | None) -> list[Gebuehrensatz] | None:
    """Die eine Vorschlagszeile der Tabellen 2023–2025 lesen."""
    m = re.search(r"\bVorschl(?:ag|[äa]ge)(?:\s+f[üu]r)?\s+(\d{4})\s+", part, re.I)
    if not m:
        return None
    year = int(m.group(1))
    werte = [_satz_eur(x) for x in _SATZ_BETRAG.findall(part[m.end():])]
    if len(werte) != len(SATZARTEN):
        raise GebuehrenFehler(
            f"Anlage 4 für {year}: {len(werte)} statt {len(SATZARTEN)} "
            "Tarifbeträge in der Vorschlagszeile — nichts gespeichert.")
    return [Gebuehrensatz(
        year=year, key=art.key, area=art.area,
        label=art.label, amount=value, unit=art.unit,
        prior_year=None, change_pct=None, template_number=template_number)
        for art, value in zip(SATZARTEN, werte, strict=True)]


def _saetze_neues_layout(part: str, template_number: str | None) -> list[Gebuehrensatz] | None:
    """Das Zeilenlayout ab 2026 samt Prozentprobe lesen."""
    if not re.search(r"Ver[äa]nderung\s+in\s+%", part, re.I):
        return None
    kopf = re.search(r"\bVorschlag\s+(\d{4})(?:\s+\d{4})+", part, re.I)
    if not kopf:
        raise GebuehrenFehler("Anlage 4: Vorschlagsjahr im Tabellenkopf fehlt")
    year = int(kopf.group(1))
    aus: list[Gebuehrensatz] = []
    for art in SATZARTEN:
        m = re.search(
            rf"\b{art.code}\s+{art.modernes_muster}\s+"
            rf"(-?[\d.]+,\d{{2}})%\s+{_SATZ_BETRAG_EURO}\s+"
            rf"{_SATZ_BETRAG_EURO}", part, re.I)
        if not m:
            raise GebuehrenFehler(
                f"Anlage 4 für {year}: Tarifzeile „{art.label}“ fehlt")
        change = _satz_eur(m.group(1))
        amount, prior_year = _satz_eur(m.group(2)), _satz_eur(m.group(3))
        errechnet = round((amount / prior_year - 1) * 100, 2) if prior_year else 0.0
        if abs(errechnet - change) > 0.011:
            raise GebuehrenFehler(
                f"Anlage 4 für {year}, {art.label}: {amount:.2f} € gegen "
                f"{prior_year:.2f} € ergeben {errechnet:.2f} %, gedruckt sind "
                f"{change:.2f} %.")
        aus.append(Gebuehrensatz(
            year=year, key=art.key, area=art.area,
            label=art.label, amount=amount, unit=art.unit,
            prior_year=prior_year, change_pct=change,
            template_number=template_number))
    return aus


def lies_gebuehrensaetze(text: str, template_number: str | None = None) -> list[Gebuehrensatz]:
    """Die Vorschläge aus Anlage 4 lesen und gegen Anlagen 1 und 3 halten.

    Ein bloßes „Anlage 4" ohne Tabelleninhalt (der OCR-Stand von 2020) ist
    keine kaputte Zahl und liefert deshalb eine leere Liste. Sobald aber ein
    bekanntes Tabellenlayout beginnt, gilt: alle zwölf Zeilen oder keine.
    """
    part = _anlage_4(text)
    if not part or not part.strip():
        return []
    saetze = (_saetze_neues_layout(part, template_number)
              or _saetze_altes_layout(part, template_number))
    if saetze is None:
        raise GebuehrenFehler("Anlage 4: unbekanntes Tabellenlayout")

    year = saetze[0].year
    bedarfe, risse = lies(text, template_number)
    eckwerte = {
        b.area: b.fee_proposed for b in bedarfe
        if b.year == year and b.area in ("abfallbehandlung", "strassenreinigung")
    }
    tarifwerte = {s.area: s.amount for s in saetze
                  if s.key in ("abfallbehandlung_mg", "strassenreinigung_qw")}
    if set(eckwerte) != {"abfallbehandlung", "strassenreinigung"}:
        details = f"; gerissene Anlagen: {' | '.join(risse)}" if risse else ""
        raise GebuehrenFehler(
            f"Anlage 4 für {year}: Eckwerte aus Anlagen 1 und 3 fehlen{details}")
    for area, amount in tarifwerte.items():
        if eckwerte[area] is None or abs(amount - eckwerte[area]) > 0.011:
            raise GebuehrenFehler(
                f"Anlage 4 für {year}: {area} nennt {amount:.2f} €, "
                f"die eigene Bedarfsberechnung {eckwerte[area]} €.")
    return saetze


def herkunft_fuer_satz(satz: Gebuehrensatz, *, url: str | None,
                       document_id: int | None, label: str | None) -> Herkunft:
    probes = [PROBE_SATZANZAHL, PROBE_ECKWERTE]
    result = ("12 von 12 Tarifarten gelesen; Gebühren je Mg und je Meter "
                "Quadratwurzel stimmen mit Anlagen 1 und 3 überein")
    if satz.change_pct is not None:
        probes.append(PROBE_VORJAHRESVERGLEICH)
        result += (f"; {satz.amount:.2f} € gegen {satz.prior_year:.2f} € = "
                     f"{satz.change_pct:.2f} %")
    return Herkunft(
        art="ris", probe=probes, document_id=document_id, label=label,
        url=url, citation=f"Anlage 4, {satz.label}, Vorschlag {satz.year}",
        probe_result=result, as_of=f"Gebührenvorschlag {satz.year}")


def herkunft_fuer(bedarf: Gebuehrenbedarf, *, url: str | None,
                  document_id: int | None, label: str | None) -> Herkunft:
    """Die Herkunft: die Anlage, und was an ihr nachgerechnet wurde."""
    rest = bedarf.cost_calculation + bedarf.deductions - bedarf.costs_to_cover
    probes = [PROBE_KASKADE]
    division = ""
    if bedarf.fee is not None and bedarf.reference_quantity:
        probes.append(PROBE_DIVISION)
        division = (f"; {bedarf.costs_to_cover:,.0f} € ÷ "
                    f"{bedarf.reference_quantity:,.0f} {bedarf.reference_unit} = "
                    f"{bedarf.fee:.3f} €")
    return Herkunft(
        art="ris",
        probe=probes,
        document_id=document_id,
        label=label or f"Gebührenbedarfsberechnung {bedarf.year}",
        url=url,
        citation=f"Gebührenbedarfsberechnung {bedarf.year}, {bedarf.area_name}",
        probe_result=f"Kaskade geht auf (Rest {rest:+.2f} €){division}",
        as_of=f"Gebührenbedarfsberechnung {bedarf.year}",
    )
