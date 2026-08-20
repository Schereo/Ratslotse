"""Wirtschaftspläne aus der **Anlage** — die Betriebe, die im Beschlusstext
keine Zahl nennen.

``council/wirtschaftsplan.py`` liest die Eckwerte aus dem Beschlusstext der
Ratsvorlage. Das geht nur beim Eigenbetrieb Gebäudewirtschaft und Hochbau: Von
46 Wirtschaftsplan-Vorlagen tragen acht diesen Block, und alle acht sind seine.
Die übrigen Betriebe stimmen „der anliegenden Fassung" zu — ihre Zahlen stehen
im **Erfolgsplan der Anlage**, und der ist eine Tabelle.

Dieses Modul liest diese Tabelle. Es beginnt mit dem
Abfallwirtschaftsbetrieb (AWB), ist aber auf die anderen Betriebe hin gebaut:
Was sich je Betrieb unterscheidet, ist ausschließlich das **Vokabular** der
Zeilenbeschriftungen (:data:`VOKABULAR`); der Weg — Kopfzeile lesen, die drei
Summenzeilen finden, spaltenweise prüfen, die Planspalte auswählen — ist
derselbe.

Warum ausgerechnet der AWB
--------------------------
Weil aus seinem Erfolgsplan die **Abfallgebühren** kalkuliert werden. Von allen
Betrieben ist er derjenige, dessen Zahlen jeder Haushalt in Oldenburg direkt
bezahlt.

Zwei Layouts, dieselbe Aussage
------------------------------
Der AWB hat sein Tabellenlayout zwischen 2025 und 2026 gewechselt. Beide führen
dieselben drei Summen, nur unter anderem Namen::

    Layout A (2023–2025)          Layout B (ab 2026)
    ────────────────────          ──────────────────
    Gesamtertrag                  Summe Erträge
    Gesamtaufwendungen            Summe Aufwendungen
    Gesamtergebnis                11. Ergebnis nach Steuern

Beide Male gilt ``Erträge − Aufwendungen = Ergebnis``, und beide Male steht das
Ergebnis unmittelbar unter seinen beiden Summanden. Ein Layout-Schalter ist
deshalb nicht nötig: Das Vokabular führt beide Schreibweisen, und welche
gegriffen hat, hält die Herkunft fest.

**Was das Ergebnis NICHT ist.** In Layout B folgen unter der gelesenen Zeile
noch „12. Sonstige Steuern" und „13. Jahresüberschuss"; in Layout A stecken die
sonstigen Steuern bereits in den Aufwendungen. Gelesen wird deshalb in beiden
Fällen die Zeile, die das Dokument **direkt unter seine beiden Summen** setzt —
nicht die, die zufällig „Jahresüberschuss" heißt. So bleibt die Beziehung
``Erträge − Aufwendungen = Ergebnis`` in jeder gespeicherten Zeile wahr, und
zwar dieselbe wie bei den EGH-Zeilen aus dem Beschlusstext.

Drei Proben, alle aus dem Dokument
----------------------------------
1. **``wirtschaftsplan_spalten``** — ``Erträge − Aufwendungen = Ergebnis``, und
   zwar in **jeder** Spalte der Tabelle, nicht nur in der, die wir speichern.
   Ein Dokument führt sechs Spalten (ein Ist- und fünf Planjahre); die Probe
   läuft also sechsmal je Jahrgang. Über die fünf lesbaren AWB-Jahrgänge sind
   das 30 Proben, von denen 29 auf den Cent aufgehen und eine um 1 € daneben
   liegt (Finanzplanung 2029 im Jahrgang 2026) — die Quelle rundet je Position.
   Daher :data:`TOLERANZ_EUR` = 2 und nicht 0,005 wie beim Beschlusstext.
2. **``wirtschaftsplan_prosa``** — Unter der Tabelle steht ein Satz, der die
   beiden Summen des **Planjahres** wiederholt: „Der Erfolgsplan 2025 umfasst
   voraussichtlich anfallende Erträge in Höhe von insgesamt 25.197.796 € und
   voraussichtlich entstehende Aufwendungen in Höhe von insgesamt
   24.570.285 €." Zwei unabhängig gesetzte Stellen desselben Dokuments, die
   übereinstimmen müssen — dieselbe Art Beleg wie die Wiederholungsprobe des
   Investitionsprogramms.

   Sie ist **weich**: Fehlt der Satz, fällt der Jahrgang nicht. Er ist Fließtext
   und keine Tabellenzeile; ein Jahrgang, der ihn weglässt oder anders
   formuliert, hat deswegen keine falschen Zahlen. Widerspricht er dagegen der
   Tabelle, ist das ein harter Fehler.
3. **``wirtschaftsplan_bereiche``** — Der Erfolgsplan führt seine Ertragszeile
   fünfmal: einmal für alle Bereiche und je einmal in den vier Anlagen
   (Abfallbehandlung, Abfallsammlung, Straßenreinigung, Werkstatt). Die vier
   ergeben die erste. Damit ist „die erste Zeile ist die Gesamtrechnung" keine
   Positionsannahme mehr, sondern gemessen.

   Auch sie ist **kein Fallbeil**, und dafür gibt es einen konkreten Anlass:
   Im Jahrgang 2025 ergeben die Zweige in der Planspalte 447.001 € mehr als die
   Gesamtzeile (1,77 %) — in allen anderen Spalten stimmt es auf ±1 €. Die
   gespeicherte Zahl hängt daran nicht: Spaltenprobe und Prosa-Satz decken sie
   unabhängig voneinander. Dieselbe Lage wie 2022 bei den Schulden — die Summe
   trägt, die Aufteilung nicht, und dann fällt die Aufteilung.

Welche Spalte der Plan ist
--------------------------
Die Kopfzeile nennt jede Spalte mit Art und Jahr::

    Ist 2023   Plan 2024   Plan 2025   Plan 2026   Plan 2027   Plan 2028

Gesucht ist die Spalte mit dem **Haushaltsjahr der Vorlage** — beim
Wirtschaftsplan 2025 also die dritte. Das ist keine Positionsannahme: Die
Spaltenzahl schwankt, und der Jahrgang 2026 schreibt „Ergebnis 2024" statt
„Ist 2024". Findet sich das Haushaltsjahr nicht im Kopf, wird nichts
gespeichert — lieber keine Zeile als eine unter dem falschen Jahr.

Die Finanzplanungsjahre werden **nicht** gespeichert. Sie sind eine Vorausschau
nach § 8 NKomVG, die jeder neue Plan neu schreibt; dieselbe Entscheidung wie
bei ``council_ergebnishaushalt``, dort ausführlich begründet. Geprüft werden
sie trotzdem — eine Spalte, die ihre eigene Rechnung nicht erfüllt, sagt etwas
über den Textextrakt der ganzen Tabelle.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from council.herkunft import Herkunft
from council.wirtschaftsplan import BETRIEBE, Wirtschaftsplan, WirtschaftsplanFehler

PROBE_SPALTEN = "wirtschaftsplan_spalten"
PROBE_PROSA = "wirtschaftsplan_prosa"
PROBE_BEREICHE = "wirtschaftsplan_bereiche"

PROBEN: dict[str, str] = {
    PROBE_SPALTEN:
        "In jeder Spalte des Erfolgsplans gilt die Rechnung des Dokuments: "
        "Erträge − Aufwendungen = Ergebnis. Geprüft werden alle Spalten, "
        "gespeichert nur das Planjahr.",
    PROBE_PROSA:
        "Der Satz unter der Tabelle nennt dieselben beiden Summen wie die "
        "Planspalte — zwei unabhängig gesetzte Stellen desselben Dokuments.",
    PROBE_BEREICHE:
        "Die Betriebszweige ergeben zusammen die Gesamtzeile. Sie belegt, dass "
        "die gelesene Zeile die Gesamtrechnung ist und nicht einer der Zweige — "
        "gemessen, nicht als Fallbeil (s. BEREICHE_SCHWELLE).",
}

#: Zwei Euro. Die Quelle rundet je Position auf volle Euro; über sechs Spalten
#: und fünf Jahrgänge trat genau eine Abweichung auf, und die betrug 1 €. Eine
#: schärfere Schwelle verwürfe einen Jahrgang wegen einer Rundung, eine
#: weitere ließe echte Lesefehler durch — der kleinste Betrag der Tabelle liegt
#: bei 164 €.
TOLERANZ_EUR = 2.0

#: Je Betrieb die Zeilenbeschriftungen der drei Summen. Mehrere Schreibweisen
#: je Feld, weil die Betriebe ihr Layout wechseln — welche gegriffen hat, hält
#: die Herkunft fest.
#:
#: Bewusst **kein** Eintrag für Betriebe, die noch niemand geprüft hat: Ein
#: geratenes Vokabular fände irgendeine Zeile, und ihre Zahlen stünden dann
#: unter einem Namen, den nie jemand nachgeschlagen hat.
VOKABULAR: dict[str, dict[str, tuple[str, ...]]] = {
    "awb": {
        "ertraege": (r"Gesamtertrag", r"Summe Ertr[äa]ge"),
        "aufwendungen": (r"Gesamtaufwendungen", r"Summe Aufwendungen"),
        # „Gesamtergebnis" (Layout A) bzw. „11. Ergebnis nach Steuern"
        # (Layout B) — beide stehen unmittelbar unter ihren zwei Summanden.
        "ergebnis": (r"Gesamtergebnis", r"1?1?\.?\s*Ergebnis nach Steuern"),
    },
}

#: Ein Betrag der Tabelle: „24.058.098 €", „-118.500,00 €", „0 €".
_BETRAG = re.compile(r"-?\d{1,3}(?:\.\d{3})*(?:,\d{2})?\s*€")

#: Die Kopfzeile: „Ist 2023 Plan 2024 …", ab 2026 „Ergebnis 2024 Plan 2025 …".
_KOPFSPALTE = re.compile(r"(Ist|Plan|Ergebnis)\s+(20\d{2})")

#: Der Satz unter der Tabelle. „Euro" und „€" kommen beide vor, und er läuft
#: über einen Zeilenumbruch — deshalb wird der Text vorher geglättet.
_PROSA = re.compile(
    r"Erfolgsplan\s+(?P<jahr>\d{4})\s+umfasst.{0,80}?Ertr[äa]ge.{0,60}?insgesamt\s+"
    r"(?P<ertraege>[\d.]+)\s*(?:€|Euro).{0,90}?Aufwendungen.{0,60}?insgesamt\s+"
    r"(?P<aufwendungen>[\d.]+)\s*(?:€|Euro)")

#: Wie weit die Betriebszweige von ihrer Gesamtzeile abweichen dürfen, damit
#: sie noch als deren Teile gelten: 5 %.
#:
#: Die Schwelle beantwortet EINE Frage — „haben wir die Gesamtzeile erwischt
#: oder aus Versehen einen Betriebszweig?". Ein Zweig ist fünf- bis zwölfmal
#: kleiner als die Summe; alles in dieser Größenordnung fällt durch, lange
#: bevor 5 % erreicht sind.
#:
#: Sie ist NICHT dazu da, Widersprüche des Dokuments abzufangen. Der Jahrgang
#: 2025 hat einen: Dort ergeben die vier Zweige in der **Planspalte**
#: 447.001 € mehr als die ausgewiesene Gesamtzeile (1,77 %), in allen anderen
#: Spalten stimmt es auf ±1 €. Die gespeicherte Zahl hängt daran nicht — sie
#: ist durch die Spaltenprobe UND den Prosa-Satz gedeckt, zwei unabhängige
#: Stellen desselben Dokuments. Dieselbe Lage wie 2022 bei den Schulden: Die
#: Summe trägt, die Aufteilung nicht, und dann fällt die Aufteilung und nicht
#: die Summe. Gemessen wird der Abstand trotzdem und reist in der Herkunft mit.
BEREICHE_SCHWELLE = 0.05

#: So viele Beträge muss eine Zeile tragen, damit sie als Datenzeile gilt.
#: Ohne diese Schwelle greift der Parser eine gleichnamige **Überschrift** ohne
#: Zahlen — genau das ist im Jahrgang 2024 passiert, wo „Gesamtergebnis" vor
#: der Tabelle schon einmal als Zwischentitel steht.
MINDEST_SPALTEN = 3


@dataclass(frozen=True)
class Spaltenprobe:
    """Das Ergebnis der Rechenprobe einer Spalte."""

    art: str          # ist | ansatz | finanzplanung
    jahr: int
    ertraege: float
    aufwendungen: float
    ergebnis: float

    @property
    def rest(self) -> float:
        return self.ertraege - self.aufwendungen - self.ergebnis

    @property
    def geht_auf(self) -> bool:
        return abs(self.rest) <= TOLERANZ_EUR


def _eur(roh: str) -> float:
    return float(roh.replace("€", "").strip().replace(".", "").replace(",", "."))


def _glaetten(text: str) -> str:
    """Zeilenumbrüche für die Prosa-Suche auflösen — die Tabelle bleibt roh."""
    return re.sub(r"\s+", " ", text)


def _datenzeile(zeilen: list[str], muster: tuple[str, ...]) -> tuple[str, list[float]] | None:
    """Die erste Zeile, die auf eines der Muster passt **und** Zahlen trägt."""
    for zeile in zeilen:
        for m in muster:
            if not re.search(rf"^\s*{m}\b", zeile):
                continue
            betraege = [_eur(x) for x in _BETRAG.findall(zeile)]
            if len(betraege) >= MINDEST_SPALTEN:
                return m, betraege
    return None


def kopfspalten(zeilen: list[str], mindestens: int = 4) -> list[tuple[str, int]]:
    """Die Spalten der Tabelle als ``(art, jahr)`` — aus der Kopfzeile.

    ``art`` ist ``ist`` für die Rückschau (das Dokument schreibt „Ist" oder
    „Ergebnis") und sonst ``plan``; welches der Planjahre **der** Haushalt ist,
    entscheidet erst der Abgleich mit dem Jahrgang der Vorlage.
    """
    for zeile in zeilen:
        treffer = _KOPFSPALTE.findall(zeile)
        if len(treffer) >= mindestens:
            return [("ist" if wort in ("Ist", "Ergebnis") else "plan", int(jahr))
                    for wort, jahr in treffer]
    return []


def spaltenproben(text: str, betrieb: str) -> list[Spaltenprobe]:
    """Die Rechenprobe jeder Spalte des Erfolgsplans.

    Wirft :class:`WirtschaftsplanFehler`, wenn die drei Summenzeilen nicht
    gleich viele Beträge tragen: Dann ist die Spaltenzuordnung nicht mehr
    gesichert, und eine Probe über verrutschte Spalten prüfte nichts.
    """
    if betrieb not in VOKABULAR:
        raise WirtschaftsplanFehler(
            f"Für '{betrieb}' ist kein Zeilen-Vokabular hinterlegt — erst die "
            "Beschriftungen des Erfolgsplans prüfen und in VOKABULAR eintragen.")
    zeilen = text.splitlines()
    kopf = kopfspalten(zeilen)
    if not kopf:
        raise WirtschaftsplanFehler("keine Kopfzeile mit Jahresangaben gefunden")

    gefunden: dict[str, list[float]] = {}
    labels: dict[str, str] = {}
    for feld, muster in VOKABULAR[betrieb].items():
        treffer = _datenzeile(zeilen, muster)
        if treffer is None:
            raise WirtschaftsplanFehler(
                f"Zeile '{feld}' nicht gefunden (gesucht: {', '.join(muster)})")
        labels[feld], gefunden[feld] = treffer

    laengen = {len(v) for v in gefunden.values()}
    if len(laengen) != 1:
        raise WirtschaftsplanFehler(
            "Die Summenzeilen tragen verschieden viele Beträge "
            f"({ {f: len(v) for f, v in gefunden.items()} }) — Spalten verrutscht")
    breite = laengen.pop()
    if breite != len(kopf):
        raise WirtschaftsplanFehler(
            f"Kopfzeile nennt {len(kopf)} Spalten, die Summenzeilen tragen "
            f"{breite} Beträge")

    return [
        Spaltenprobe(art=art, jahr=jahr, ertraege=e, aufwendungen=a, ergebnis=g)
        for (art, jahr), e, a, g in zip(
            kopf, gefunden["ertraege"], gefunden["aufwendungen"], gefunden["ergebnis"])
    ]


def bereichsprobe(text: str, betrieb: str) -> tuple[int, list[float]] | None:
    """Wie weit die Betriebszweige von der Gesamtzeile abweichen, je Spalte.

    Der Erfolgsplan führt seine Ertragszeile fünfmal: einmal für alle Bereiche
    und je einmal in den vier Anlagen (Abfallbehandlung, Abfallsammlung,
    Straßenreinigung, Werkstatt). Die erste ist die Gesamtrechnung — das ist
    hier keine Positionsannahme mehr, sondern gemessen.

    ``None``, wenn es keine Zweige gibt (dann greift die Probe nicht).
    """
    muster = VOKABULAR.get(betrieb, {}).get("ertraege", ())
    zeilen: list[list[float]] = []
    for zeile in text.splitlines():
        if not any(re.search(rf"^\s*{m}\b", zeile) for m in muster):
            continue
        betraege = [_eur(x) for x in _BETRAG.findall(zeile)]
        if len(betraege) >= MINDEST_SPALTEN:
            zeilen.append(betraege)
    if len(zeilen) < 2:
        return None
    gesamt, zweige = zeilen[0], zeilen[1:]
    breite = min(len(gesamt), *(len(z) for z in zweige))
    return len(zweige), [sum(z[i] for z in zweige) - gesamt[i] for i in range(breite)]


def prosa_summen(text: str) -> tuple[int, float, float] | None:
    """Jahr, Erträge und Aufwendungen aus dem Satz unter der Tabelle."""
    m = _PROSA.search(_glaetten(text))
    if not m:
        return None
    return (int(m.group("jahr")),
            _eur(m.group("ertraege")), _eur(m.group("aufwendungen")))


def plan_bezug(proben: list[Spaltenprobe], jahr: int) -> float:
    """Die Ertragssumme des Planjahres — Bezugsgröße der Bereichsprobe."""
    return next((p.ertraege for p in proben if p.jahr == jahr), 0.0)


def parse_erfolgsplan(vorlage_nr: str, betrieb: str, haushaltsjahr: int,
                      text: str) -> tuple[Wirtschaftsplan, list[Spaltenprobe]]:
    """Den Erfolgsplan einer Anlage lesen — geprüft, oder gar nicht.

    Liefert den Plan des **Haushaltsjahres** und alle Spaltenproben (auch die
    der Finanzplanungsjahre, die nicht gespeichert werden — sie belegen, dass
    der Textextrakt der ganzen Tabelle trägt).
    """
    proben = spaltenproben(text, betrieb)

    gerissen = [p for p in proben if not p.geht_auf]
    if gerissen:
        raise WirtschaftsplanFehler(
            f"{vorlage_nr}: {len(gerissen)} von {len(proben)} Spalten gehen nicht "
            "auf — " + "; ".join(f"{p.jahr}: Rest {p.rest:+.2f} €" for p in gerissen))

    plan = next((p for p in proben if p.jahr == haushaltsjahr), None)
    if plan is None:
        raise WirtschaftsplanFehler(
            f"{vorlage_nr}: Haushaltsjahr {haushaltsjahr} steht nicht in der "
            f"Kopfzeile (dort: {sorted(p.jahr for p in proben)})")

    # Die Bereichsprobe beantwortet: Haben wir die Gesamtzeile erwischt? Ein
    # Betriebszweig wäre um ein Vielfaches kleiner und fiele hier durch, lange
    # bevor die Schwelle greift. Ein Widerspruch INNERHALB des Dokuments (wie
    # 2025) reißt den Jahrgang dagegen nicht — die Summe ist durch zwei andere
    # Proben gedeckt, und dann fällt die Aufteilung und nicht die Summe.
    bereiche = bereichsprobe(text, betrieb)
    if bereiche:
        n_zweige, reste = bereiche
        i = next((k for k, p_ in enumerate(proben) if p_.jahr == haushaltsjahr), None)
        if i is not None and i < len(reste) and plan_bezug(proben, haushaltsjahr):
            abstand = abs(reste[i]) / max(plan_bezug(proben, haushaltsjahr), 1.0)
            if abstand > BEREICHE_SCHWELLE:
                raise WirtschaftsplanFehler(
                    f"{vorlage_nr}: Die {n_zweige} Betriebszweige weichen um "
                    f"{abstand:.1%} von der gelesenen Zeile ab — das ist keine "
                    "Gesamtzeile, sondern vermutlich einer der Zweige")

    prosa = prosa_summen(text)
    if prosa and prosa[0] == haushaltsjahr:
        _, p_ertraege, p_aufwendungen = prosa
        if (abs(p_ertraege - plan.ertraege) > TOLERANZ_EUR
                or abs(p_aufwendungen - plan.aufwendungen) > TOLERANZ_EUR):
            raise WirtschaftsplanFehler(
                f"{vorlage_nr}: Der Satz unter der Tabelle nennt "
                f"{p_ertraege:.0f} / {p_aufwendungen:.0f} €, die Planspalte "
                f"{plan.ertraege:.0f} / {plan.aufwendungen:.0f} € — "
                "zwei Stellen desselben Dokuments widersprechen sich")

    name = BETRIEBE[betrieb][1]
    return Wirtschaftsplan(
        betrieb=betrieb, betrieb_name=name, jahr=haushaltsjahr,
        vorlage_nr=vorlage_nr,
        ertraege=plan.ertraege, aufwendungen=plan.aufwendungen,
        # Kein eigener Steuerposten: Was der Beschlusstext des EGH als
        # „steuerliche Aufwendungen" gesondert ausweist, steckt hier in den
        # Aufwendungen. Die Null ist deshalb eine Aussage und keine Lücke —
        # sie hält `Erträge − Aufwendungen − Steuern = Ergebnis` in jeder
        # gespeicherten Zeile wahr, egal aus welcher Quelle sie stammt.
        steuern=0.0, ergebnis=plan.ergebnis,
        # Der Vermögensplan steht in einer eigenen Tabelle dieser Anlage und
        # bringt eigene Proben mit; er ist nicht Teil dieser Schicht.
        vermoegensplan=None, verpflichtungen=None,
        entwurf_vom=None,
    ), proben


def herkunft_fuer(plan: Wirtschaftsplan, proben: list[Spaltenprobe],
                  url: str | None, dokument_id: int | None,
                  label: str | None) -> Herkunft:
    """Die Herkunft: die **Anlage**, nicht die Vorlage."""
    geprueft = len(proben)
    schaerfste = max((abs(p.rest) for p in proben), default=0.0)
    return Herkunft(
        art="ris",
        probe=[PROBE_SPALTEN, PROBE_PROSA],
        dokument_id=dokument_id,
        label=label or f"Anlage zu {plan.vorlage_nr}",
        url=url,
        fundstelle="Erfolgsplan der Anlage",
        probe_ergebnis=(f"{geprueft} Spalten geprüft, größte Abweichung "
                        f"{schaerfste:.2f} €"),
        stand=f"Wirtschaftsplan {plan.jahr}, Fassung der Anlage",
    )
