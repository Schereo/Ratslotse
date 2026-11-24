"""Die Quartalsberichte der städtischen Beteiligungen — Plan, Hochrechnung, später das Ist.

Das Handbuch Beteiligungen (Richtlinie zum Beteiligungsmanagement, Seite 32)
verpflichtet die Geschäftsführungen, zum 30.06., 30.09. und 31.12. über den
Stand des Wirtschaftsplans zu berichten, in der Regel binnen drei Wochen nach
dem Stichtag. Die Verwaltung bündelt das zu einer Sammelvorlage „Bericht zum
n. Quartal JJJJ der städtischen Beteiligungsunternehmen und Eigenbetriebe“ im
Ausschuss für Finanzen und Beteiligungen. Der Inhalt steht allein in der
Anlage; das Protokoll hält nur fest, dass der Bericht zur Kenntnis genommen
wird.

Was dieses Modul liest
----------------------
Die **Übersichtstabelle** je Teil (Teil A: Gesellschaften, Teil B:
Eigenbetriebe): je Unternehmen das Ergebnis des Vorjahres, den Plan des
laufenden Jahres, die Hochrechnung (HR) dieses Jahres und die gedruckte
Abweichung. Dazu aus dem Abschnitt des Unternehmens die Zeilen „Hochrechnung“
und „Plan“ im Seitentext, die Art des Plans (ursprünglich oder geändert) und
den Satz, mit dem der Bericht selbst sagt, ob der Wirtschaftsplan eingehalten
wird.

Gelesen wird aus dem **gespeicherten Anlagentext**, ohne PDF-Download. Die
Tabelle steht dort je nach Textauszug zeilenweise oder Zelle für Zelle; der
Leser zerlegt deshalb den Text in Wörter und sucht die Kopfzeile samt Zeilen
(Kürzel plus drei oder vier Zahlen), statt sich auf Zeilenumbrüche zu
verlassen.

Was bewusst NICHT gelesen wird
------------------------------
* **Kein Ist.** Die Spalte „Vorjahr Ist“ steht im Bericht, ist aber nicht das
  Ist des Vorjahres: Sie ist teils vorläufig (BBGO 2025: −10.241.408 € im Bericht
  gegen −10.447.445 € im festgestellten Abschluss), teils falsch übertragen (VWG
  „2021 Ist“ trägt den Wert von 2020) und hat teils eine andere Basis (KOL 2024).
  Sie wird als ``prior_reported`` festgehalten und nie als Ist gezeigt. Ist
  kommt aus dem Abschluss.
* **Kein kumuliertes Ist zum Stichtag, keine Vermögens- und Investitions-
  planung.** Das Handbuch verlangt sie, im öffentlichen Bericht steht sie
  nicht.
* **Keine Ad-hoc-Berichte** (Corona 2020): anderes Format.

Drei Fallen, an denen die Schicht hängt
---------------------------------------
**Einheit und Vorzeichen gelten je Bericht.** 19/0148 rechnet in TEUR, gerundet,
und druckt die Abweichung als Plan − HR; alle späteren in Euro mit
HR − Plan. Beides wird nicht der Kopfzeile geglaubt, sondern gerechnet: Die
Vorzeichenregel ist die, unter der die Abweichungen der Zeilen aufgehen.

**„Plan“ heißt zweierlei.** Die Spalte trägt „(geänderter) Plan“, und je
Unternehmen ist es mal der ursprüngliche, mal der angepasste. Welcher, sagt der
Abschnitt des Unternehmens („Plan 2025“ gegen „Geänderter Plan 2025“). Die
Art gehört deshalb an jeden Wert (``plan_kind``).

**Tabelle und Seitentext widersprechen sich um Kleinigkeiten.** KOL Q4 2025:
Tabelle −25.429.193 €, Seitentext −25.429.270 €, die gedruckte Abweichung
passt zum Seitentext (77 € Differenz). Solche Zeilen werden behalten und als
Konflikt markiert; beide Werte bleiben sichtbar. Reißt die Rechnung dagegen
grob (ein verlorenes Minuszeichen, eine Hochrechnung, die im Text anders
lautet als in der Tabelle), wird die Zeile **nicht gespeichert** und in der
Meldung des Laufs genannt.

Basis: Die VWG meldet keinen Jahresüberschuss, sondern den
„Gesamtzuschussbedarf“ (Jahresfehlbetrag vor Ausgleichszahlung, plus
Verzinsung des EWE-Anteils) — ``basis = subsidy_need``.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from council.herkunft import Herkunft

#: Die Namen der Proben (Erklärsätze in ``herkunft.PROBEN``).
PROBE_DEVIATION = "holding_quarterly_deviation"
PROBE_PERIOD = "holding_quarterly_period"
PROBE_PLAN_TEXT = "holding_quarterly_plan_text"

#: Kürzel im Bericht → Schlüssel wie in ``council_companies.company`` bzw.
#: ``council_business_plans.enterprise``.
KUERZEL: dict[str, str] = {
    "BBGO": "bbgo", "KOL": "klinikum", "OTM": "otm", "VWG": "vwg", "WEH": "weh",
    "TGO": "tgo", "VHS": "vhs", "SOG": "stadion",
    "AWB": "awb", "BBO": "bbo", "EGH": "egh", "Hafen": "hafen",
}
EIGENBETRIEBE = frozenset({"awb", "bbo", "egh", "hafen"})

#: Wie der Bericht die Unternehmen nennt — für Fließtext (KI-Frage), wo ein
#: Kürzel nichts sagt.
NAMEN: dict[str, str] = {
    "klinikum": "Klinikum Oldenburg AöR (KOL)",
    "bbgo": "Bäderbetriebsgesellschaft Oldenburg mbH (BBGO)",
    "otm": "Oldenburg Tourismus und Marketing GmbH (OTM)",
    "vwg": "Verkehr und Wasser GmbH (VWG)",
    "weh": "Weser-Ems-Halle GmbH & Co. KG (WEH)",
    "tgo": "TGO Technologie- und Gründerzentrum Oldenburg GmbH (TGO)",
    "vhs": "Volkshochschule Oldenburg gGmbH (VHS)",
    "stadion": "Stadion Oldenburg GmbH & Co. KG (SOG)",
    "awb": "Abfallwirtschaftsbetrieb Stadt Oldenburg (AWB)",
    "bbo": "Bäderbetrieb der Stadt Oldenburg (BBO)",
    "egh": "Eigenbetrieb Gebäudewirtschaft und Hochbau (EGH)",
    "hafen": "Hafen Oldenburg",
}

#: Woran eine Frage ein Unternehmen meint — Muster auf dem GEFALTETEN Wortlaut
#: (klein, ae/oe/ue/ss). Bewusst ohne das nackte „Stadion“: Das ist in
#: Oldenburg ein Thema, keine Gesellschaft.
FIRMEN: dict[str, re.Pattern[str]] = {
    "klinikum": re.compile(r"klinikum|\bkol\b"),
    "bbgo": re.compile(r"baederbetriebsgesellschaft|\bbbgo\b|baedergesellschaft"),
    "otm": re.compile(r"tourismus|\botm\b"),
    "vwg": re.compile(r"verkehr und wasser|\bvwg\b"),
    "weh": re.compile(r"weser ems halle(?! oldenburg beteiligung)|\bweh\b"),
    "tgo": re.compile(r"\btgo\b|gruenderzentrum"),
    "vhs": re.compile(r"volkshochschule|\bvhs\b"),
    "stadion": re.compile(r"\bsog\b|stadion (?:oldenburg )?gmbh|stadiongesellschaft"),
    "awb": re.compile(r"\bawb\b|abfallwirtschaft"),
    "bbo": re.compile(r"\bbbo\b|\bbaederbetrieb\b"),
    "egh": re.compile(r"\begh\b|gebaeudewirtschaft"),
    "hafen": re.compile(r"\bhafen\b"),
}


def firmen_in(gefaltet: str) -> list[str]:
    """Die Unternehmen, die ein gefalteter Wortlaut nennt, in Registerreihenfolge."""
    return [k for k, m in FIRMEN.items() if m.search(gefaltet)]

#: Der Titel der Sammelvorlage (SQL-LIKE) — Ad-hoc-Berichte heißen anders.
TITEL_MUSTER = "Bericht zum%Quartal%Beteiligungsunternehmen%"

_STRICHE = str.maketrans({c: "-" for c in "‐‑‒–—−"})
_ZAHL = r"-?\s?\d+(?:\.\d{3})*"
_ZELLE = rf"({_ZAHL})(?:\s*€)?"
_KUERZEL_RE = "|".join(sorted(KUERZEL, key=len, reverse=True))
_KOPF = re.compile(
    r"(\d{4}) Ist (\d{4}) (?:\((?:geänderter|angepasster)\) )?Plan(?: bzw\. \d\. Nachtrags-? ?haushalt)? (\d{4}) HR "
    r"Abweichung\s*(?:Plan/ ?HR)?\s*((?:\[?(?:TEUR|EUR|Euro|€|T€)\]?\s*){4})")
#: Kürzel plus drei oder vier Zahlen. Drei, wenn die erste Spalte leer ist (SOG
#: im Bericht zum 31.12.2024 hat kein Vorjahr); die Deutung entscheidet die Probe.
_ZEILE = re.compile(
    rf"\s*({_KUERZEL_RE})\s+{_ZELLE}\s+{_ZELLE}\s+{_ZELLE}(?:\s+{_ZELLE}(?=\s|$))?(?=\s|$)")
_ABSCHNITT = re.compile(r"\(([A-Za-z]{3,5})\) Bericht zum (\d{2})\.(\d{2})\.(\d{2,4})")
_ETIKETT = re.compile(
    r"\s*-\s*(?:(?:der|dem)\s+)?(?:\(?([Gg]eänder\w*|[Aa]ngepasst\w*)\)?\s+)?"
    r"(Hochrechnung|HR|Plan)\s+(?:\d{2}\.\d{2}\.)?(\d{2,4})\s*:")
_WERT = re.compile(rf"\s*({_ZAHL})\s*(?:Euro|€)")
_WERT_FOLGE = re.compile(rf"({_ZAHL})\s*(?:Euro|€)")
_VORAB = re.compile(rf"\s*((?:{_ZAHL}\s*(?:Euro|€)\s*)+)(?=(?:Das|Der|Die)\b)")
_SATZ = re.compile(
    r"Der\s+(?:\S+\s+){0,3}?Wirtscha\S{0,3}plan\b[^.]{0,80}?eingehalten[^.]{0,80}\.")
_TITEL = re.compile(r"Bericht zum (\d)\. Quartal(?: (\d{4}))?")
_STICHTAG_MMDD = {1: "03-31", 2: "06-30", 3: "09-30", 4: "12-31"}

#: Wie weit gedruckte Abweichung und Rechnung auseinanderliegen dürfen, ohne
#: dass die Zeile als Widerspruch gilt: zwei Euro Rundung (in einem TEUR-Bericht
#: eine Tausenderstelle). Darüber, aber unter der Nähe-Grenze, steht die Zeile
#: mit Konfliktmarke; darüber wird sie nicht gespeichert.
_RUNDUNG_EUR = 2
_NAH_EUR = 2000
_NAH_ANTEIL = 0.0005


class QuartalFehler(Exception):
    """Der Bericht ließ sich nicht sauber lesen — Grund im Text."""


@dataclass
class Zeile:
    company: str
    plan: int                      # Euro (Tabelle)
    forecast: int                  # Euro
    deviation_printed: int         # Euro, wie gedruckt (Vorzeichen: ``Bericht.sign_rule``)
    prior_reported: int | None     # Euro — Prüfwert, nie als Ist zeigen
    plan_kind: str | None = None   # original | adjusted | None (nicht bestimmbar)
    plan_text: int | None = None   # Planwert laut Seitentext, der zur Tabelle gehört
    plan_other: int | None = None  # der zweite Planwert des Seitentexts (VWG)
    plan_other_kind: str | None = None
    conflict: bool = False         # Tabelle, Seitentext und Abweichung widersprechen sich leicht
    deviation_gap: int = 0         # gedruckte Abweichung minus gerechnete, in Euro
    statement: str | None = None   # der Satz des Berichts zur Einhaltung des Plans
    basis: str = "result"          # result | subsidy_need
    probes: tuple[str, ...] = (PROBE_DEVIATION, PROBE_PERIOD)


@dataclass
class Bericht:
    template_number: str
    quarter: int
    fiscal_year: int
    as_of: str                     # ISO-Stichtag
    unit: str                      # EUR | TEUR — wie gedruckt
    rounded_to: int                # 1 | 1000 — die Werte stehen in Euro
    sign_rule: str                 # forecast_minus_plan | plan_minus_forecast
    zeilen: list[Zeile] = field(default_factory=list)
    abgewiesen: list[str] = field(default_factory=list)
    document_id: int | None = None

    @property
    def probes(self) -> tuple[str, ...]:
        """Die Proben, die JEDE gespeicherte Zeile bestanden hat."""
        if not self.zeilen:
            return (PROBE_DEVIATION, PROBE_PERIOD)
        gemeinsam = set(self.zeilen[0].probes)
        for z in self.zeilen[1:]:
            gemeinsam &= set(z.probes)
        return tuple(p for p in (PROBE_DEVIATION, PROBE_PERIOD, PROBE_PLAN_TEXT) if p in gemeinsam)


def ist_quartalsbericht(titel: str | None) -> bool:
    """Gehört dieser Vorlagentitel zu einer Sammelvorlage der Quartalsberichte?"""
    return bool(titel and re.search(
        r"Bericht zum \d\. Quartal.*Beteiligungsunternehmen", titel))


def _normal(text: str) -> str:
    text = text.translate(_STRICHE)
    text = re.sub(r"Wirtscha[^\w\s]s?plan", "Wirtschaftsplan", text)
    return re.sub(r"\s+", " ", text)


def _zahl(s: str) -> int:
    return int(s.replace(" ", "").replace(".", ""))


def _jahr(j: str) -> int:
    n = int(j)
    return n + 2000 if n < 100 else n


def _nah(a: int, b: int, tol: int) -> bool:
    """Gleich bis auf Rundung — ``tol`` ist die Druckeinheit des Berichts."""
    return abs(a - b) <= max(tol, int(0.0002 * max(abs(a), abs(b))))


def _euro(n: int) -> str:
    return f"{n:,}".replace(",", ".") + " €"


def _lesarten(zahlen: list[int]) -> list[tuple[int | None, int, int, int]]:
    """Wie die Zahlen einer Zeile gelesen werden können: (Vorjahr, Plan, HR, Abw.).

    Vier Zahlen sind die Regel. Eine leere erste Spalte (neue Gesellschaft ohne
    Vorjahr) ergibt drei — und eine Seitenzahl, die hinter der letzten Zeile
    einer Seite steht, kann als vierte danebenstehen. Welche Lesart gilt,
    entscheidet die Rechnung, nicht die Reihenfolge."""
    if len(zahlen) == 4:
        return [(zahlen[0], zahlen[1], zahlen[2], zahlen[3]),
                (None, zahlen[0], zahlen[1], zahlen[2])]
    return [(None, zahlen[0], zahlen[1], zahlen[2])]


def _regel_bestimmen(zeilen: list[tuple[str, list]], tol: int) -> str:
    """Welche Vorzeichenregel die gedruckte Abweichung hat — gerechnet.

    Gewinnt die Regel, unter der mehr Zeilen aufgehen; Zeilen, die unter beiden
    aufgehen (Abweichung 0), zählen nicht. Gleichstand ist ein Fehler, keine
    Entscheidung."""
    treffer = {"forecast_minus_plan": 0, "plan_minus_forecast": 0}
    for _, lesarten in zeilen:
        for _vj, plan, hr, dev in lesarten:
            a = abs(dev - (hr - plan)) <= tol
            b = abs(dev - (plan - hr)) <= tol
            if a != b:
                treffer["forecast_minus_plan" if a else "plan_minus_forecast"] += 1
                break
    a, b = treffer["forecast_minus_plan"], treffer["plan_minus_forecast"]
    if a == b:
        raise QuartalFehler(
            "Vorzeichenregel der Abweichung nicht bestimmbar "
            f"(HR − Plan: {a} Zeilen, Plan − HR: {b})")
    return "forecast_minus_plan" if a > b else "plan_minus_forecast"


def _abschnitte(text: str) -> dict[str, tuple[str, str]]:
    """Kürzel → (Stichtag, Abschnittstext) je Unternehmen."""
    treffer = list(_ABSCHNITT.finditer(text))
    out: dict[str, tuple[str, str]] = {}
    for i, m in enumerate(treffer):
        ende = treffer[i + 1].start() if i + 1 < len(treffer) else len(text)
        stichtag = f"{_jahr(m.group(4)):04d}-{m.group(3)}-{m.group(2)}"
        kuerzel = m.group(1).upper() if m.group(1).upper() in KUERZEL else m.group(1)
        out.setdefault(kuerzel, (stichtag, text[m.end():ende]))
    return out


def _seitenwerte(abschnitt: str, jahr: int) -> tuple[int | None, list[tuple[str, int]]]:
    """Hochrechnung und Pläne (Art, Wert) aus der Aufzählung eines Abschnitts.

    „Das Jahresergebnis beträgt laut“ steht mal als Zeile je Wert (Etikett,
    Betrag, Etikett, Betrag), mal erst alle Etiketten und dann alle Beträge —
    je nachdem, wie der Textauszug die Spalten ordnet. Beides ist dieselbe
    Aufzählung: Jeder Betrag gehört zum ältesten Etikett ohne Betrag."""
    erstes = _ETIKETT.search(abschnitt)
    if not erstes:
        return None, []
    # Mancher Textauszug setzt den ersten Betrag VOR die Überschrift („KOL …
    # -25.935.513 Euro Das Jahresergebnis beträgt laut - Hochrechnung 2023: …“).
    # Er gehört dann zum ersten Etikett.
    lead = _VORAB.match(abschnitt)
    vorab = [_zahl(z) for z in _WERT_FOLGE.findall(lead.group(1))] if lead else []
    pos, offen, paare = erstes.start(), [], []
    while True:
        e = _ETIKETT.match(abschnitt, pos)
        if e:
            if vorab:
                paare.append((e, vorab.pop(0)))
            else:
                offen.append(e)
            pos = e.end()
            continue
        w = _WERT.match(abschnitt, pos)
        if w and offen:
            paare.append((offen.pop(0), _zahl(w.group(1))))
            pos = w.end()
            continue
        break
    hr = None
    plaene: list[tuple[str, int]] = []
    for e, wert in paare:
        if _jahr(e.group(3)) != jahr:
            continue
        if e.group(2) == "Plan":
            plaene.append(("adjusted" if e.group(1) else "original", wert))
        elif hr is None:
            hr = wert
    return hr, plaene


def lies_bericht(text: str, titel: str, template_number: str,
                 document_id: int | None = None) -> Bericht:
    """Die Übersichtstabellen eines Quartalsberichts, geprüft.

    Wirft :class:`QuartalFehler`, wenn der Bericht als Ganzes nicht trägt
    (keine Tabelle, Jahre ungleich, Stichtag widersprüchlich, keine
    Vorzeichenregel). Einzelne Zeilen, die ihre Probe reißen, landen in
    ``Bericht.abgewiesen`` und werden nicht gespeichert."""
    t = _normal(text)
    kopf = list(_KOPF.finditer(t))
    if not kopf:
        raise QuartalFehler("keine Übersichtstabelle (Kopfzeile „Ist/Plan/HR/Abweichung“) gefunden")

    einheit = None
    roh: list[tuple[str, list[int]]] = []
    jahre: set[int] = set()
    for k in kopf:
        vj, j_plan, j_hr = int(k.group(1)), int(k.group(2)), int(k.group(3))
        if not (j_plan == j_hr == vj + 1):
            raise QuartalFehler(f"Jahre der Kopfzeile passen nicht zusammen: {vj}/{j_plan}/{j_hr}")
        jahre.add(j_plan)
        e = "TEUR" if re.search(r"TEUR|T€", k.group(4)) else "EUR"
        if einheit not in (None, e):
            raise QuartalFehler("beide Tabellen nennen verschiedene Einheiten")
        einheit = e
        pos = k.end()
        while (z := _ZEILE.match(t, pos)):
            roh.append((z.group(1), [_zahl(g) for g in z.groups()[1:] if g is not None]))
            pos = z.end()
    if len(jahre) != 1:
        raise QuartalFehler(f"mehrere Berichtsjahre in den Tabellen: {sorted(jahre)}")
    jahr = jahre.pop()
    if not roh:
        raise QuartalFehler("Kopfzeile ohne Zeilen")
    assert einheit is not None
    faktor = 1000 if einheit == "TEUR" else 1
    tol = faktor if faktor > 1 else _RUNDUNG_EUR
    zeilen_roh = [(k, [(None if v is None else v * faktor, p * faktor, h * faktor, d * faktor)
                       for v, p, h, d in _lesarten(zahlen)]) for k, zahlen in roh]

    # Stichtag: der Titel nennt das Quartal; der Text nennt den Tag.
    tm = _TITEL.search(titel or "")
    if not tm:
        raise QuartalFehler(f"Titel ohne „n. Quartal“: {titel!r}")
    quartal = int(tm.group(1))
    if tm.group(2) and int(tm.group(2)) != jahr:
        raise QuartalFehler(f"Titel nennt {tm.group(2)}, die Tabelle {jahr}")
    as_of = f"{jahr}-{_STICHTAG_MMDD[quartal]}"
    abschnitte = _abschnitte(t)
    tage = {s for s, _ in abschnitte.values()}
    if tage and tage != {as_of}:
        raise QuartalFehler(f"Stichtag laut Titel {as_of}, laut Text {sorted(tage)}")

    regel = _regel_bestimmen(zeilen_roh, tol)
    bericht = Bericht(template_number=template_number, quarter=quartal,
                      fiscal_year=jahr, as_of=as_of, unit=einheit,
                      rounded_to=faktor, sign_rule=regel, document_id=document_id)

    def gerechnet(plan: int, hr: int) -> int:
        return (hr - plan) if regel == "forecast_minus_plan" else (plan - hr)

    def nah(plan: int, hr: int) -> int:
        return min(_NAH_EUR, int(_NAH_ANTEIL * max(abs(plan), abs(hr))))

    gesehen: set[str] = set()
    for kuerzel, lesarten in zeilen_roh:
        if kuerzel in gesehen:
            bericht.abgewiesen.append(f"{kuerzel}: steht zweimal in den Tabellen")
            continue
        gesehen.add(kuerzel)
        # Die Lesart, unter der die Abweichung aufgeht; sonst die erste (für die Meldung).
        wahl = next((x for x in lesarten if abs(x[3] - gerechnet(x[1], x[2])) <= tol), None)
        if wahl is None and faktor == 1:
            wahl = next((x for x in lesarten
                         if abs(x[3] - gerechnet(x[1], x[2])) <= nah(x[1], x[2])), None)
        vj, plan, hr, dev = wahl or lesarten[0]
        zeile = Zeile(company=KUERZEL[kuerzel], plan=plan, forecast=hr,
                      deviation_printed=dev, prior_reported=vj)
        abschnitt = abschnitte.get(kuerzel)
        text_hr, plaene = _seitenwerte(abschnitt[1], jahr) if abschnitt else (None, [])
        if abschnitt:
            if "Gesamtzuschussbedarf" in abschnitt[1]:
                zeile.basis = "subsidy_need"
            satz = _SATZ.search(abschnitt[1])
            if satz:
                zeile.statement = satz.group(0).strip()
        # Hochrechnung im Seitentext muss die der Tabelle sein.
        if text_hr is not None and not _nah(text_hr, hr, tol):
            bericht.abgewiesen.append(
                f"{kuerzel}: Hochrechnung laut Tabelle {_euro(hr)}, laut Seitentext {_euro(text_hr)}")
            continue
        # Art des Plans — und der Seitentext-Plan, der zur Tabelle passt.
        passend = [(art, w) for art, w in plaene if _nah(w, plan, tol)]
        if passend:
            art, wert = min(passend, key=lambda p: abs(p[1] - plan))
            zeile.plan_kind, zeile.plan_text = art, wert
            andere = [(a, w) for a, w in plaene if (a, w) != (art, wert)]
            if andere:
                zeile.plan_other_kind, zeile.plan_other = andere[0]
        elif plaene:
            zeile.plan_other_kind, zeile.plan_other = plaene[0]
        # Probe: die gedruckte Abweichung ist HR − Plan (bzw. umgekehrt).
        luecke = dev - gerechnet(plan, hr)
        if abs(luecke) <= tol:
            if zeile.plan_text is not None and zeile.plan_text != plan:
                zeile.conflict = True
            elif zeile.plan_text == plan:
                zeile.probes = (PROBE_DEVIATION, PROBE_PERIOD, PROBE_PLAN_TEXT)
        else:
            # Rechnet die Abweichung mit dem Plan des Seitentexts? Dann steht
            # der Widerspruch zwischen Tabelle und Text, die Zeile bleibt.
            alt = [(a, w) for a, w in plaene
                   if abs(dev - gerechnet(w, hr)) <= tol
                   and abs(w - plan) <= max(1000, int(_NAH_ANTEIL * abs(plan)))]
            if alt:
                zeile.conflict = True
                zeile.plan_kind, zeile.plan_text = alt[0]
                zeile.plan_other, zeile.plan_other_kind = None, None
            elif faktor == 1 and abs(luecke) <= nah(plan, hr):
                # Rundungsfehler im Bericht selbst: Die Zeile bleibt, der Abstand steht dabei.
                zeile.conflict = True
                zeile.deviation_gap = luecke
            else:
                bericht.abgewiesen.append(
                    f"{kuerzel}: gedruckte Abweichung {_euro(dev)} passt nicht zu Hochrechnung "
                    f"{_euro(hr)} und Plan {_euro(plan)} ({regel})")
                continue
        bericht.zeilen.append(zeile)
    if not bericht.zeilen:
        raise QuartalFehler("keine Zeile besteht die Abweichungsprobe")
    return bericht


def einheit_aus_kopf(label: str | None, kopf: str | None) -> tuple[int, str] | None:
    """``(Jahr, Stichtag)`` aus dem Label bzw. dem Textkopf einer Anlage —
    wofür die Registry die Einheiten einer Anlage braucht, ohne sie zu lesen.

    ``None``, wo nichts Eindeutiges steht (19/0148 nennt kein Jahr im Titel);
    die Anlage zählt dann nur nicht als Kandidat einer bestimmten Einheit."""
    quelle = _normal(f"{kopf or ''} {label or ''}")
    m = _TITEL.search(quelle)
    if m and m.group(2):
        return int(m.group(2)), f"{m.group(2)}-{_STICHTAG_MMDD[int(m.group(1))]}"
    m = re.search(r"\b(?:Q(\d)[- ]?(20\d{2})|(\d{2})\.(\d{2})\.(20\d{2}))\b", quelle)
    if m and m.group(1):
        return int(m.group(2)), f"{m.group(2)}-{_STICHTAG_MMDD[int(m.group(1))]}"
    if m and m.group(3):
        stichtag = f"{m.group(5)}-{m.group(4)}-{m.group(3)}"
        if stichtag[5:] in _STICHTAG_MMDD.values():
            return int(m.group(5)), stichtag
    return None


def abgleich(bericht: Bericht, conn) -> list[tuple[bool, str]]:
    """Messzahlen gegen die Nachbarschichten — Bestätigung, kein Fallbeil.

    * **Plan gegen den Wirtschaftsplan** (``council_business_plans``): nur, wo
      die Art des Plans (``plan_kind = adjusted``) dazu passt — der Bestand hält
      je Betrieb und Jahr EINEN Plan, und eine Anpassung ersetzt den Stand.
    * **„Vorjahr Ist“ gegen den Abschluss** (``council_company_accounts``,
      ``council_enterprise_accounts``): Sie weichen systematisch ab (vorläufige
      Werte, falsch übertragene Jahre, andere Basis). Nur gemeldet, nie
      übernommen; für die VWG gilt eine andere Basis (Zuschussbedarf).

    Liefert je Befund ``(stimmt, Text)``, geeignet für das Protokoll des Laufs."""
    out: list[tuple[bool, str]] = []
    jahr = bericht.fiscal_year
    for z in bericht.zeilen:
        try:
            plan = conn.execute(
                "SELECT result FROM council_business_plans WHERE enterprise = ? AND year = ?",
                (z.company, jahr)).fetchone()
            if plan is not None and z.plan_kind in ("adjusted", None):
                if abs(plan[0] - z.plan) <= max(bericht.rounded_to, 1):
                    out.append((True, f"{z.company}: Plan {_euro(z.plan)} = Wirtschaftsplan {jahr}"))
                else:
                    out.append((False, f"{z.company}: Plan {_euro(z.plan)} ≠ Wirtschaftsplan {jahr} "
                                f"{_euro(int(plan[0]))} (Art laut Bericht: {z.plan_kind or 'offen'})"))
            if z.prior_reported is None or z.basis == "subsidy_need":
                continue
            rundung = max(bericht.rounded_to, 1)
            ist = conn.execute(
                "SELECT value FROM council_company_accounts WHERE company = ? AND year = ? "
                "AND indicator = 'jahresergebnis'", (z.company, jahr - 1)).fetchone()
            if ist is None:
                ist = conn.execute(
                    "SELECT value, unit FROM council_enterprise_accounts WHERE enterprise = ? "
                    "AND year = ? AND metric = 'result'", (z.company, jahr - 1)).fetchone()
                if ist is not None and ist[1] == "TEUR":
                    rundung = 1000     # der Abschluss rundet auf Tausend
            if ist is not None:
                abstand = z.prior_reported - ist[0]
                if abs(abstand) <= rundung:
                    out.append((True, f"{z.company}: Vorjahr {_euro(z.prior_reported)} = Abschluss {jahr - 1}"))
                else:
                    out.append((False, f"{z.company}: Vorjahr im Bericht {_euro(z.prior_reported)}, "
                                f"Abschluss {jahr - 1} {_euro(int(ist[0]))} "
                                f"(Abstand {_euro(int(abstand))}) — nicht übernommen"))
        except Exception:  # noqa: BLE001 — Nachbartabellen können fehlen
            return out
    return out


def herkunft_fuer(bericht: Bericht, *, document_id: int | None, label: str | None,
                  url: str | None) -> Herkunft:
    """Die Herkunft eines Berichts: Anlage der Sammelvorlage, Probe je Bericht."""
    return Herkunft(
        kind="ris", probe=bericht.probes, document_id=document_id, as_of=bericht.as_of,
        label=label or f"Vorlage {bericht.template_number}", url=url,
        citation=f"Bericht zum {bericht.quarter}. Quartal {bericht.fiscal_year}, "
                 f"Vorlage {bericht.template_number}")


# --------------------------------------------------------------------------
# Für die Seite: Plan, Hochrechnungen, Ist — drei getrennte Stationen
# --------------------------------------------------------------------------

def _note(s: dict) -> str | None:
    """Der Widerspruch einer Station, als Satz über die QUELLE.

    Beide Werte stehen dabei: Welcher stimmt, weiß nur die Geschäftsführung."""
    if s.get("conflict") and s.get("plan_text") not in (None, s["plan"]):
        return (f"Der Seitentext des Berichts nennt den Plan mit {_euro(int(s['plan_text']))}, "
                f"die Tabelle mit {_euro(int(s['plan']))}.")
    if s.get("conflict") and s.get("deviation_gap"):
        return (f"Die gedruckte Abweichung weicht um {_euro(abs(int(s['deviation_gap'])))} "
                "von Hochrechnung minus Plan ab.")
    return None


def laufendes_jahr(store) -> list[dict]:
    """Je Unternehmen das jüngste Jahr mit Quartalsbericht — für die Seite.

    Drei Stationen, nie verrechnet und nie bewertet: der **Plan** (mit seiner
    Art), jede **Hochrechnung** mit ihrem Stichtag nebeneinander und das
    **Ist** — das nur aus dem Abschluss kommt, nie aus dem Bericht. Wo ein
    Abschluss das Jahr schon nennt, steht es als dritte Station daneben; wo
    nicht, fehlt es, und das ist die Auskunft.

    Die VWG meldet den Gesamtzuschussbedarf, der Abschluss ein anderes
    Ergebnis: Dort steht kein Ist, sondern ein Satz dazu."""
    je_firma: dict[str, list[dict]] = {}
    for z in store.holding_forecasts():
        je_firma.setdefault(z["company"], []).append(z)
    aus: list[dict] = []
    for firma in KUERZEL.values():
        reihen = je_firma.get(firma)
        if not reihen:
            continue
        jahr = max(r["fiscal_year"] for r in reihen)
        stationen = [r for r in reihen if r["fiscal_year"] == jahr]
        basis = stationen[-1]["basis"]
        ist = None if basis == "subsidy_need" else store.holding_actual(firma, jahr)
        aus.append({
            "company": firma,
            "year": jahr,
            "basis": basis,
            "stations": [{
                "as_of": r["as_of"], "quarter": r["quarter"],
                "plan": r["plan"], "plan_kind": r["plan_kind"],
                "forecast": r["forecast"],
                "plan_other": r["plan_other"], "plan_other_kind": r["plan_other_kind"],
                "rounded": r["rounded_to"] > 1,
                "conflict_note": _note(r),
                "statement": r["statement"],
                "template_number": r["template_number"],
                "herkunft_id": r["herkunft_id"],
            } for r in stationen],
            "actual": ({"value": ist["value"], "source": ist["source"],
                        "herkunft_id": ist["herkunft_id"]} if ist else None),
            "actual_note": ("Für die VWG nennt der Bericht den Gesamtzuschussbedarf, "
                            "der Jahresabschluss ein anderes Ergebnis."
                            if basis == "subsidy_need" else None),
        })
    return aus
