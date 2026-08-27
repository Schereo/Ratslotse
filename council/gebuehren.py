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

WAS HIER NICHT STEHT: die Gebührensätze selbst. Anlage 4 führt sie als
Zeitreihe über zwölf Jahre und zwölf Gebührenarten, mit einer eigenen
Prozentprobe je Zeile — eine eigene Schicht, die auf diese hier aufbaut.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from council.herkunft import Herkunft

PROBE_KASKADE = "gebuehren_kaskade"
PROBE_DIVISION = "gebuehren_division"

PROBEN: dict[str, str] = {
    PROBE_KASKADE:
        "Die Kalkulationskosten minus alle Abzüge ergeben die Kosten, die "
        "durch Gebühren zu decken sind — nachgerechnet mit den Abzügen, die "
        "das Dokument selbst benennt.",
    PROBE_DIVISION:
        "Die zu deckenden Kosten, geteilt durch die Bezugsmenge, ergeben die "
        "gedruckte Gebühr. Menge und Gebühr stehen an anderer Stelle als die "
        "Kaskade — zwei unabhängige Angaben desselben Dokuments.",
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
    jahr: int
    bereich: str
    bereich_name: str
    #: Was der Bereich im Haushaltsjahr insgesamt kostet.
    kostenkalkulation: float
    #: Alles, was davon abgezogen wird — negativ. Erstattungen Dritter,
    #: Erlöse, Rückstellungen und die Über-/Unterdeckung aus Vorjahren.
    abzuege: float
    #: Was die Gebührenzahler tragen.
    zu_deckende_kosten: float
    #: Wonach die Gebühr bemessen wird (Tonnen, Liter, Meter Quadratwurzel).
    #: ``None`` bei der Abfallsammlung: Sie erhebt eine Grundgebühr UND eine
    #: Gebühr je Liter, es gibt dort also keine einzelne Division. Die
    #: Kaskade ist trotzdem geprüft.
    bezugsmenge: float | None
    bezugseinheit: str | None
    gebuehr: float | None
    #: Der gerundete Vorschlag an den Rat — das, was am Ende erhoben wird.
    #: ``None``, wo das Dokument ihn nicht gesondert ausweist.
    gebuehrenvorschlag: float | None
    vorlage_nr: str | None


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


def _menge_aus_der_probe(teil: str, zu_decken: float, gebuehr: float) -> float:
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
    for m in _MENGE.finditer(teil):
        try:
            wert = float(m.group(1).replace(".", ""))
        except ValueError:
            continue
        if wert > 0:
            kandidaten.append((wert, m.start()))
    # Und die im Textextrakt zerrissenen Formen.
    for m in re.finditer(r"(?<![\d,.])(\d{1,3})\s+([\d.]{3,})(?!\s*€)", teil):
        try:
            kandidaten.append((float((m.group(1) + m.group(2)).replace(".", "")),
                               m.start()))
        except ValueError:
            continue

    treffer = [(w, pos) for w, pos in kandidaten
               if w and abs(zu_decken / w - gebuehr) <= TOLERANZ_GEBUEHR]
    if not treffer:
        raise GebuehrenFehler(
            f"Keine Bezugsmenge im Text ergibt die gedruckte Gebühr "
            f"({gebuehr:.3f} aus {zu_decken:.2f} €) — die Division lässt sich "
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
    g = _GEBUEHR_MIT_EINHEIT.search(teil)
    davor = [(pos, w) for w, pos in treffer if g and pos < g.start()]
    if not davor:
        raise GebuehrenFehler(
            f"Mehrere Bezugsmengen ergäben die Gebühr {gebuehr:.3f}: "
            f"{sorted(werte)}, und keine steht vor der Gebührenzeile — "
            "nicht entscheidbar.")
    return max(davor)[1]


def _kaskade_aus_der_reihenfolge(teil: str) -> tuple[float, float, float] | None:
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
    for m in _BETRAG_RE.finditer(teil):
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
    for wert, _ in betraege[1:]:
        if wert < 0:
            laufend += wert
        elif abs(kalkulation + laufend - wert) <= TOLERANZ_EUR:
            gefunden = (kalkulation, laufend, wert)
    return gefunden


def parse_anlage(teil: str, vorlage_nr: str | None = None) -> Gebuehrenbedarf:
    """Eine Anlage lesen — geprüft, oder gar nicht."""
    bereich = _bereich_aus_kopf(teil)
    if bereich is None:
        raise GebuehrenFehler("Kein bekannter Bereich im Anlagenkopf")
    jahr = _JAHR.search(teil)
    if jahr is None:
        raise GebuehrenFehler("Kein Jahrgang („Gebührenbedarfsberechnung JJJJ“)")

    k = _KALKULATION.search(teil)
    d = _ZU_DECKEN.search(teil)
    if k and d:
        kalkulation, zu_decken = _eur(k.group(1)), _eur(d.group(1))
        kaskade = teil[k.end():d.start()]
        abzuege = sum(_eur(x) for x in _BETRAG_RE.findall(kaskade)
                      if x.strip().startswith("-"))
        rest = kalkulation + abzuege - zu_decken
        ueberdeckung = _UEBER_UNTERDECKUNG.search(kaskade)
        if ueberdeckung is not None:
            wert = _eur(ueberdeckung.group(1))
            if wert > 0 and abs(rest - wert) <= TOLERANZ_EUR:
                abzuege -= wert
    else:
        # Beschriftungen und Beträge stehen in getrennten Blöcken (2024).
        ueber_reihenfolge = _kaskade_aus_der_reihenfolge(teil)
        if ueber_reihenfolge is None:
            raise GebuehrenFehler(
                "Kaskade unvollständig: "
                + ("Kostenkalkulation fehlt. " if not k else "")
                + ("Zeile „zu decken sind“ fehlt. " if not d else "")
                + "Auch über die Reihenfolge der Beträge geht keine Kaskade auf.")
        kalkulation, abzuege, zu_decken = ueber_reihenfolge
    rest = kalkulation + abzuege - zu_decken
    if abs(rest) > TOLERANZ_EUR:
        raise GebuehrenFehler(
            f"{bereich[1]} {jahr.group(1)}: Kalkulation {kalkulation:,.2f} € "
            f"und Abzüge {abzuege:,.2f} € ergeben {kalkulation + abzuege:,.2f} €, "
            f"die Zeile nennt {zu_decken:,.2f} € — Rest {rest:+,.2f} €.")

    # NICHT JEDER BEREICH HAT EINE EINZELNE GEBÜHR. Die Abfallsammlung
    # erhebt eine Grundgebühr UND eine Gebühr je Liter Behältervolumen; eine
    # Division „zu deckende Kosten ÷ Menge" gibt es dort nicht, und eine
    # erfundene wäre schlimmer als keine. Der Jahrgang wird trotzdem
    # gespeichert — seine Kaskade ist geprüft, nur die zweite Probe fehlt.
    g = _GEBUEHR_MIT_EINHEIT.search(teil)
    gebuehr = menge = None
    einheit = None
    if g is not None:
        einheit = _einheit_aus(g.group(1))
        if einheit is None:
            raise GebuehrenFehler(
                f"{bereich[1]} {jahr.group(1)}: Unbekannte Bezugseinheit "
                f"„{' '.join(g.group(1).split())}“ — eine erfundene Einheit "
                "wäre eine Behauptung über das Dokument.")
        gebuehr = float(g.group(2).replace(".", "").replace(",", "."))
        try:
            menge = _menge_aus_der_probe(teil, zu_decken, gebuehr)
        except GebuehrenFehler:
            # Wahrscheinlich der gerundete VORSCHLAG erwischt statt der
            # errechneten Gebühr — das passiert, wo der Textextrakt
            # Beschriftungen und Beträge trennt. Die errechnete hat drei
            # Nachkommastellen; welche der Kandidaten es ist, entscheidet
            # wieder die Division und nicht die Reihenfolge.
            gebuehr = menge = None
            for kandidat in _GEBUEHR_DREISTELLIG.findall(teil):
                wert = float(kandidat.replace(".", "").replace(",", "."))
                try:
                    menge = _menge_aus_der_probe(teil, zu_decken, wert)
                except GebuehrenFehler:
                    continue
                gebuehr = wert
                break
            if gebuehr is None:
                raise
    v = _VORSCHLAG.search(teil)

    return Gebuehrenbedarf(
        jahr=int(jahr.group(1)), bereich=bereich[0], bereich_name=bereich[1],
        kostenkalkulation=kalkulation, abzuege=abzuege,
        zu_deckende_kosten=zu_decken, bezugsmenge=menge, bezugseinheit=einheit,
        gebuehr=gebuehr,
        gebuehrenvorschlag=(float(v.group(1).replace(".", "").replace(",", "."))
                            if v else None),
        vorlage_nr=vorlage_nr,
    )


def lies(text: str, vorlage_nr: str | None = None
         ) -> tuple[list[Gebuehrenbedarf], list[str]]:
    """Alle Anlagen eines Dokuments lesen.

    Liefert ``(gelesen, risse)``. Ein gerissener Bereich nimmt die anderen
    nicht mit: Sie stehen in eigenen Anlagen und prüfen sich einzeln.
    """
    gelesen, risse = [], []
    for teil in teile_anlagen(text):
        try:
            gelesen.append(parse_anlage(teil, vorlage_nr))
        except GebuehrenFehler as fehler:
            risse.append(str(fehler))
    return gelesen, risse


def herkunft_fuer(bedarf: Gebuehrenbedarf, *, url: str | None,
                  dokument_id: int | None, label: str | None) -> Herkunft:
    """Die Herkunft: die Anlage, und was an ihr nachgerechnet wurde."""
    rest = bedarf.kostenkalkulation + bedarf.abzuege - bedarf.zu_deckende_kosten
    proben = [PROBE_KASKADE]
    division = ""
    if bedarf.gebuehr is not None and bedarf.bezugsmenge:
        proben.append(PROBE_DIVISION)
        division = (f"; {bedarf.zu_deckende_kosten:,.0f} € ÷ "
                    f"{bedarf.bezugsmenge:,.0f} {bedarf.bezugseinheit} = "
                    f"{bedarf.gebuehr:.3f} €")
    return Herkunft(
        art="ris",
        probe=proben,
        dokument_id=dokument_id,
        label=label or f"Gebührenbedarfsberechnung {bedarf.jahr}",
        url=url,
        fundstelle=f"Gebührenbedarfsberechnung {bedarf.jahr}, {bedarf.bereich_name}",
        probe_ergebnis=f"Kaskade geht auf (Rest {rest:+.2f} €){division}",
        stand=f"Gebührenbedarfsberechnung {bedarf.jahr}",
    )
