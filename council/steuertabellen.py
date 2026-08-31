"""Die beiden Steuertabellen des Statistischen Jahrbuchs — 1103 und 1105.

Zwei Tabellen, ein Ziel: der Steuer-Steckbrief (``/haushalt/steuer?art=…``).
Sie stehen zusammen in einem Modul, weil sie sich gegenseitig prüfen und beide
an derselben dritten Tabelle hängen — **1104**, der Ist-Reihe, die wir seit
Monaten als ``council_steuern`` führen.

Tabelle 1103 — was geplant war, neben dem, was kam
---------------------------------------------------
Sie stellt je Steuerart den **Haushaltsplan** neben das **Rechnungsergebnis**,
für drei Jahrgänge. Das ist die einzige Stelle, an der wir die Plan-Seite je
Steuerart überhaupt bekommen: Weder ``council_ergebnishaushalt`` noch
``council_ergebnisrechnung`` schlüsseln Steuern auf — beide führen nur
„Steuern und ähnliche Abgaben" als eine Summe.

Der Befund, den sie sichtbar macht (Ausgabe 2025):

======  =========  =========  ========
Jahr    Plan       Ist        Abstand
======  =========  =========  ========
2023    124,2 Mio  176,8 Mio  +42,3 %
2024    133,4 Mio  202,9 Mio  +52,1 %
2025    155,5 Mio  222,1 Mio  +42,8 %
======  =========  =========  ========

Drei Jahre über 40 % ist ein Muster und keine Schwankung. **Es ist trotzdem
keine Note.** Die Gewerbesteuer hängt an den Gewinnen einiger weniger großer
Zahler und schwankt zwischen 60 und 222 Mio. €; wer sie vorsichtig ansetzt,
plant nicht schlecht, sondern vermeidet ein Haushaltsloch, das er nicht mehr
schließen kann. Die Zahlen stehen deshalb nebeneinander, ohne Bewertung —
weder im Code noch in der Farbe (s. ``components/grafik/hantel.tsx``).

**Die Grenze, die dazugehört:** Jede Ausgabe führt nur **drei** Jahrgänge.
Erscheint die Ausgabe 2026, fällt 2023 heraus, und die Stadt führt kein
Archiv. Deshalb liest dieses Modul nicht nur die Live-Datei, sondern **jede
Ausgabe, die** ``scripts/archive_statistik.py`` **je gesichert hat** (s.
``council/archiv.neueste_je_datei``). Die Reihe wächst damit ab jetzt um einen
Jahrgang pro Jahr, statt bei dreien zu bleiben.

Tabelle 1105 — die Hebesätze seit 1980
---------------------------------------
Neun Zeilen für 45 Jahre, denn die Tabelle führt **nur die Änderungsjahre**
(ihre Fußnote sagt das selbst). Ein Hebesatz gilt bis zur nächsten Änderung —
das ist eine **Treppe, keine Kurve**, und zwischen zwei Stufen wird nichts
interpoliert.

**Der Pflicht-Kontext, ohne den die Zahl irreführt.** 2025 stieg der
Grundsteuer-B-Hebesatz von 445 auf 539 (+21 %). „Grundsteuer +21 %" allein
wäre falsch verstanden: Das **Aufkommen sank** im selben Jahr von 34,17 auf
32,59 Mio. € (−4,6 %), weil die Grundsteuerreform zum 01.01.2025 gleichzeitig
alle Messbeträge umstellte. Ein höherer Hebesatz auf eine kleinere
Bemessungsgrundlage ist nicht mehr Geld. Hebesatz und Aufkommen gehören
deshalb zusammen ins Bild; die Seite stellt sie nebeneinander, und dieses
Modul liefert beide Seiten aus derselben Quelle.

Die Jahresbeschriftung — die Falle, die 1106 gestellt hat
----------------------------------------------------------
Datensatz 1106 beschriftete seine Zeilen um ein Jahr zu früh; wir rücken sie
seither zurecht (``council/haushalt._STEUERKRAFT_VERSATZ``). Für **beide**
Tabellen hier ist die Beschriftung deshalb geprüft worden, bevor eine Zahl
gespeichert wird:

* **1103** — jedes Rechnungsergebnis steht ein zweites Mal in Tabelle 1104,
  die ihre Jahre einzeln beschriftet (eine Zeile je Jahr, 1998–2025). Beide
  werden getrennt gelesen; für 2023, 2024 und 2025 nennen sie in **allen
  sechs** Steuerarten denselben Betrag. Wäre die Spalte um ein Jahr
  verrutscht, risse dieser Abgleich in jeder einzelnen Zeile.
  :func:`istabgleich` ist zugleich das Aufnahmekriterium: **Ein Jahrgang ohne
  diese Zweitquelle kommt nicht herein.**

* **1105** — die Tabelle nennt nur Änderungsjahre und hat keine Zweitquelle
  mit denselben Zahlen. Geprüft wird deshalb der **Zeitpunkt der Wirkung**
  (:func:`sprungjahrprobe`): Wo der Grundsteuer-Hebesatz stieg, muss das
  Aufkommen im **genannten** Jahr stärker steigen als im Jahr danach.
  Gemessen an der Ist-Reihe 1104 (Stand 18.08.2026):

  ====  ==============  =================  ================
  Jahr  Hebesatz B      Aufkommen im Jahr  im Jahr danach
  ====  ==============  =================  ================
  2002  360 → 410       +14,55 %           +1,71 %
  2011  410 → 430       +9,31 %            −0,64 %
  2015  430 → 445       +8,48 %            +0,19 %
  ====  ==============  =================  ================

  Und die Gegenprobe: Unterstellt man die Änderung ein Jahr **später**, reißt
  die Rechnung in allen drei Fällen (+1,71 gegen +1,73 · −0,64 gegen +0,56 ·
  +0,19 gegen +0,81). Die Beschriftung ist damit nicht nur plausibel, sondern
  die Verschiebung ausgeschlossen.

  Drei der acht Änderungen sind so prüfbar; die fünf von 1984 bis 1997 liegen
  vor dem Beginn der Aufkommensreihe (1998), und 2025 ist es aus zwei Gründen
  nicht — es fehlt das Folgejahr, und die Reform hat die Bemessungsgrundlage
  mitverändert (:data:`BEMESSUNG_NEU`). Was nicht prüfbar ist, wird gesagt und
  nicht behauptet.

Warum „Hundesteuer" gegen „sonstige Steuern" geprüft werden darf
-----------------------------------------------------------------
1103 führt die Zeile „Hundesteuer", 1104 an derselben Stelle „sonstige
Steuern". Das ist kein Bruch: Die Fußnote von 1104 sagt, was darin steckt —
„per Saldo die Hunde- und die Jagdsteuer. Seit dem Jahr 2005 wird in Oldenburg
keine Jagdsteuer mehr erhoben." Seit 2005 ist „sonstige Steuern" also genau die
Hundesteuer, und die Beträge stimmen (813 · 819 · 819 T€). Erzwungen wird die
Gleichheit trotzdem nicht durch ein Jahr im Code, sondern durch den Abgleich
selbst: Wo die Beträge auseinanderliefen, käme der Jahrgang nicht herein.
"""
from __future__ import annotations

import re
import unicodedata

from council import schulden

# --- Woher die Tabellen kommen ----------------------------------------------

#: Die Übersichtsseite des Statistischen Jahrbuchs. Bewusst aus
#: ``council/schulden.py`` importiert statt abgeschrieben — zwei Kopien
#: derselben Adresse laufen auseinander.
JAHRBUCH_URL = schulden.JAHRBUCH_URL

#: Stand 18.08.2026 und **Rückfallebene**, wenn die Übersichtsseite ihren Link
#: nicht mehr führt. Der Dateiname trägt den Jahrgang, die Adresse wandert also
#: jedes Jahr; gesucht wird deshalb primär über :data:`LINK_1103` /
#: :data:`LINK_1105` auf der Übersichtsseite.
TABELLE_1103_URL = ("https://www.oldenburg.de/fileadmin/oldenburg/Benutzer/Dateien/"
                    "40_Stadtplanungsamt/402_Geo_und_Daten/Statistik/1103-2025-AZ.pdf")
#: 1105 hat keine eigene Datei — sie steht auf demselben Blatt wie 1104.
TABELLE_1105_URL = ("https://www.oldenburg.de/fileadmin/oldenburg/Benutzer/Dateien/"
                    "40_Stadtplanungsamt/402_Geo_und_Daten/Statistik/1104-1105-2025-AZ.pdf")

LINK_1103 = re.compile(r'href="([^"]*/1103[^"]*\.pdf)"', re.IGNORECASE)
LINK_1105 = re.compile(r'href="([^"]*/1104-1105[^"]*\.pdf)"', re.IGNORECASE)

#: Wie die Ausgaben im Archiv heißen (``council/archiv.neueste_je_datei``).
#: Ein Muster, kein Name: Jede Ausgabe ist ein eigener Ordner, weil ihr
#: Dateiname den Jahrgang trägt — und genau deshalb bleiben die alten stehen.
ARCHIV_1103 = "1103-*.pdf"
ARCHIV_1105 = "1104-1105-*.pdf"

#: Was diese Zahlen umfassen — in einem Satz, der neben ihnen stehen kann.
ABGRENZUNG_1103 = (
    "Kernhaushalt der Stadt Oldenburg. Plan ist der Ansatz der beschlossenen "
    "Haushaltssatzung, Ist das Rechnungsergebnis desselben Jahres; die "
    "Gewerbesteuer steht nach Abzug der Umlage an Bund und Land.")
ABGRENZUNG_1105 = (
    "Die vom Rat mit der Haushaltssatzung beschlossenen Hebesätze in Prozent. "
    "Ein Satz gilt bis zur nächsten Änderung — die Tabelle führt nur die Jahre, "
    "in denen sich etwas geändert hat.")


# --- Steuerarten ------------------------------------------------------------

def _norm(text: str) -> str:
    """Label → Vergleichsform: klein, ohne Trenn- und Sonderzeichen, ohne
    Umlaute. Aus „Vergnügungs-\\nsteuer" wird ``vergnuegungssteuer`` — dieselbe
    Zeichenkette, egal wie der Zeilenumbruch im PDF gerade fiel."""
    text = text.lower()
    for alt, neu in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        text = text.replace(alt, neu)
    text = unicodedata.normalize("NFKD", text)
    return re.sub(r"[^a-z0-9]+", "", text)


#: Sammelzeile der Tabelle — Prüfgröße, keine Steuerart.
SUMME = "\x00insgesamt"
#: Die Finanzzuweisungen. Sie stehen in derselben Tabelle und in derselben
#: Summe, sind aber **keine Steuer** — und vor allem haben sie in
#: ``council_steuern`` keine Entsprechung, gegen die sich ihre
#: Jahresbeschriftung prüfen ließe. Sie tragen deshalb die Summenprobe mit und
#: werden nicht gespeichert. (Der Abgleich der Zuweisungen gehört zu
#: ``council/tax_capacity.py``, wo die Abgrenzung des Landes danebensteht;
#: „Finanzzuweisungen" hier ist NICHT dasselbe wie „Schlüsselzuweisungen"
#: dort.)
ZUWEISUNGEN = "\x00finanzzuweisungen"

#: Zeilenname in 1103 → ``council_steuern.art`` (Spaltenname in 1104).
#:
#: Die Reihenfolge entscheidet: Geprüft wird auf **enthaltene** Bruchstücke,
#: und „gewerbesteuer" enthält „steuer". Spezifisches steht deshalb vorn.
_ZEILEN: tuple[tuple[str, str], ...] = (
    ("grundsteuer",      "Grundsteuer A+B"),
    ("gewerbesteuer",    "Gewerbesteuer (-umlage)"),
    ("einkommen",        "Einkommensteueranteil"),
    ("umsatzsteuer",     "Gemeindeanteil an der Umsatzsteuer"),
    ("vergnuegung",      "Vergnügungssteuer"),
    # Siehe Modulkopf: 1103 nennt die Zeile beim Namen, 1104 führt sie im
    # Sammelposten. Seit 2005 ist beides dasselbe, und der Abgleich beweist es
    # Jahrgang für Jahrgang.
    ("hundesteuer",      "sonstige Steuern"),
    ("finanzzuweisung",  ZUWEISUNGEN),
    ("total",        SUMME),
)

#: Die drei Realsteuer-Hebesätze aus 1105, in der Spaltenreihenfolge der
#: Tabelle. Sie wird nicht geraten, sondern am Tabellenkopf geprüft
#: (:func:`spaltenprobe`).
HEBESATZ_ARTEN: tuple[str, ...] = ("Grundsteuer A", "Grundsteuer B", "Gewerbesteuer")

#: Jahre, in denen sich **die Bemessungsgrundlage** änderte und nicht nur der
#: Hebesatz. Die Sprungjahr-Probe kann dort nicht greifen: Sie misst den
#: Hebesatz am Aufkommen, und wenn sich gleichzeitig der Messbetrag ändert,
#: misst sie zwei Dinge auf einmal.
#:
#: 2025: Grundsteuerreform. Die Finanzämter setzten zum 01.01.2025 für jedes
#: Grundstück neue Messbeträge fest; die Stadt hat ihren Hebesatz deshalb
#: angepasst. Das Aufkommen sank trotz des höheren Satzes um 4,6 %.
BEMESSUNG_NEU: dict[int, str] = {
    2025: "Grundsteuerreform — zum 01.01.2025 wurden alle Messbeträge neu "
          "festgesetzt. Hebesatz und Aufkommen bewegen sich in diesem Jahr "
          "nicht miteinander: Der Satz stieg, das Aufkommen sank.",
}


def steuerart(label: str) -> str | None:
    """Zeilenname aus 1103 → Steuerart, oder ``None`` bei einer unbekannten
    Zeile. Unbekannt heißt nicht „egal": Eine nicht zugeordnete Zeile fehlt in
    der Summenprobe, und die reißt dann — laut und an der richtigen Stelle."""
    norm = _norm(label)
    for bruchstueck, art in _ZEILEN:
        if bruchstueck in norm:
            return art
    return None


# --- Tabelle 1103: Plan neben Ist -------------------------------------------

#: Ein Betrag in Tausend Euro („33.770") gefolgt von seinem Anteil („8,66").
#: Die Tabelle stellt beide immer paarweise — je Jahr einmal für den Plan und
#: einmal für das Ergebnis.
_PAAR = r"\d{1,3}(?:\.\d{3})*\s+\d{1,3}(?:\.\d{3})*,\d{2}"
_DATENZEILE = re.compile(rf"^(?P<label>.*?)\s*(?P<zahlen>(?:{_PAAR}\s*)+)$")
_ZAHL = re.compile(r"\d{1,3}(?:\.\d{3})*(?:,\d{2})?")

#: Die Spaltenmarke, die jede Jahrbuch-Tabelle über ihre erste Datenzeile
#: setzt. Sie trennt Kopf von Körper — und das ist hier keine Bequemlichkeit,
#: sondern nötig: Der Titel von 1103 enthält die Wörter „Steuern" und
#: „Finanzzuweisungen", und im Textextrakt steht er teils **zwischen** den
#: Zeilen. Ohne diese Marke geriete er in einen Zeilennamen.
_SPALTENMARKE = re.compile(r"^\s*S\s*1(\s+S\s*\d+)+\s*$")
_ENDE = re.compile(r"^\s*(Quelle\s*:|\d\s+[A-ZÄÖÜ])")


def _teur(field: str) -> int:
    """„124.234" → 124234. Tausenderpunkte raus, sonst nichts."""
    return int(field.replace(".", ""))


def _prozent(field: str) -> float:
    """„8,66" → 8.66."""
    return float(field.replace(".", "").replace(",", "."))


def erkenne_1103(text: str) -> tuple[int, int] | None:
    """Die Jahresspanne aus dem Titel: „… Umlagen 2023 bis 2025" → ``(2023, 2025)``.

    Der Titel bricht im Textextrakt über zwei Zeilen um, deshalb wird über den
    ganzen Text gesucht und nicht Zeile für Zeile. ``\\d{4}`` bleibt bei vier
    Stellen stehen und stolpert damit nicht über eine angeklebte Fußnotenziffer
    („2010 bis 20251" — dieselbe Falle wie in den Tabellen 1102 und 1107)."""
    treffer = re.search(r"1103\b.{0,200}?(\d{4})\s+bis\s+(\d{4})", text, re.S)
    if not treffer:
        return None
    von, bis = int(treffer.group(1)), int(treffer.group(2))
    return (von, bis) if 1990 <= von <= bis <= 2100 else None


def parse_1103(text: str) -> dict:
    """Tabelle 1103 → ``{"years": [...], "zeilen": {art: {year: {plan, ist}}},
    "unbekannt": [...], "provisional": [...]}``.

    Beträge in **Tausend Euro**, wie gedruckt — umgerechnet wird erst beim
    Speichern. Die Anteilsspalten kommen als ``anteile`` mit, weil sie die
    Anteilsprobe tragen.
    """
    spanne = erkenne_1103(text)
    zeilen: dict[str, dict[int, dict]] = {}
    unbekannt: list[str] = []
    if not spanne:
        return {"years": [], "zeilen": zeilen, "unbekannt": unbekannt,
                "provisional": [], "spanne": None}
    years = list(range(spanne[0], spanne[1] + 1))

    # Welche Jahrgänge die Tabelle selbst als vorläufig ausweist. Die Spalte
    # heißt dann „vorläufiges Rechnungsergebnis" statt „Rechnungsergebnis" —
    # gezählt wird, nicht geraten, und markiert werden die JÜNGSTEN Jahre:
    # Ein abgerechnetes Jahr wird nicht nachträglich vorläufig.
    anzahl_vorlaeufig = len(re.findall(r"vorl(?:ä|ae)ufig", text, re.I))
    provisional = years[len(years) - anzahl_vorlaeufig:] if anzahl_vorlaeufig else []

    im_koerper = False
    puffer: list[str] = []
    for roh in text.splitlines():
        zeile = roh.rstrip()
        if not im_koerper:
            im_koerper = bool(_SPALTENMARKE.match(zeile))
            continue
        if _ENDE.match(zeile):
            break
        if not zeile.strip():
            continue
        treffer = _DATENZEILE.match(zeile.strip())
        if not treffer:
            puffer.append(zeile.strip())
            continue
        felder = _ZAHL.findall(treffer.group("zahlen"))
        # Je Jahr zwei Paare (Plan, Ist), je Paar Betrag und Anteil. Alles
        # andere ist keine Zeile dieser Tabelle — eine Kopfzeile, die zufällig
        # Zahlen trägt, oder eine Ausgabe mit anderem Spaltensatz.
        if len(felder) != len(years) * 4:
            puffer.append(zeile.strip())
            continue
        label = " ".join([*puffer, treffer.group("label")]).strip()
        puffer = []
        art = steuerart(label)
        if art is None:
            unbekannt.append(re.sub(r"\s+", " ", label))
            continue
        je_jahr: dict[int, dict] = {}
        for i, year in enumerate(years):
            block = felder[i * 4:(i + 1) * 4]
            je_jahr[year] = {
                "plan": _teur(block[0]), "plan_anteil": _prozent(block[1]),
                "ist": _teur(block[2]), "ist_anteil": _prozent(block[3]),
            }
        zeilen[art] = je_jahr
    return {"years": years, "zeilen": zeilen, "unbekannt": unbekannt,
            "provisional": provisional, "spanne": spanne}


def summenprobe(gelesen: dict) -> dict[int, dict[str, float]]:
    """Die Teilbeträge müssen die Zeile „insgesamt" ergeben — je Spalte.

    Sechs Rechnungen je Ausgabe: für jedes der drei Jahre einmal im Plan und
    einmal im Ergebnis. Zurück kommt je Jahr die Abweichung in Tausend Euro;
    ``0`` heißt, dass es auf den Tausender aufgeht.
    """
    aus: dict[int, dict[str, float]] = {}
    zeilen = gelesen["zeilen"]
    if SUMME not in zeilen:
        return aus
    teile = [a for a in zeilen if a != SUMME]
    for year in gelesen["years"]:
        aus[year] = {}
        for spalte in ("plan", "ist"):
            summe = sum(zeilen[a][year][spalte] for a in teile
                        if year in zeilen[a])
            aus[year][spalte] = summe - zeilen[SUMME][year][spalte]
    return aus


def anteilsprobe(gelesen: dict) -> list[dict]:
    """Neben jedem Betrag druckt die Tabelle seinen Anteil an der Gesamtsumme.

    Betrag ÷ Summe muss genau diesen Prozentsatz ergeben. Die Probe hält Betrag
    und Anteil zusammen — und damit auch **die Spalte**: Wären die Zahlen einer
    Zeile um ein Feld verrutscht, stünde ein Betrag neben dem falschen Anteil,
    und die Rechnung ginge nicht mehr auf.

    Zurück kommt nur, was **reißt** (Toleranz eine Rundungsstelle).
    """
    fehler: list[dict] = []
    zeilen = gelesen["zeilen"]
    if SUMME not in zeilen:
        return fehler
    for art, je_jahr in zeilen.items():
        if art == SUMME:
            continue
        for year, werte in je_jahr.items():
            gesamt = zeilen[SUMME][year]
            for spalte in ("plan", "ist"):
                if not gesamt[spalte]:
                    continue
                gerechnet = round(werte[spalte] / gesamt[spalte] * 100, 2)
                gedruckt = werte[f"{spalte}_anteil"]
                if abs(gerechnet - gedruckt) > 0.011:
                    fehler.append({"art": art, "year": year, "spalte": spalte,
                                   "gerechnet": gerechnet, "gedruckt": gedruckt})
    return fehler


def istabgleich(gelesen: dict, ist_reihe: dict[int, dict[str, float]]) -> dict:
    """Das Rechnungsergebnis gegen Tabelle 1104 — **das Aufnahmekriterium**.

    ``ist_reihe`` ist ``{year: {art: amount_in_euro}}`` aus ``council_steuern``.
    Verglichen wird in Tausend Euro, weil 1103 so druckt.

    Ein Jahrgang wird nur übernommen, wenn **jede** seiner Steuerarten dort
    wiederzufinden ist und übereinstimmt. Das ist keine Strenge um der Strenge
    willen: Es ist die einzige Prüfung, die die **Jahresbeschriftung** dieser
    Tabelle absichert — 1104 beschriftet seine Zeilen einzeln, 1103 seine
    Spalten in einer Kopfzeile. Ein Jahrgang ohne Zweitquelle käme ungeprüft
    herein, und genau so ist der Versatz im Datensatz 1106 jahrelang unbemerkt
    geblieben.

    Zurück: ``{"bestanden": [years], "verworfen": [{year, grund}]}``.
    """
    zeilen = gelesen["zeilen"]
    arten = [a for a in zeilen if a not in (SUMME, ZUWEISUNGEN)]
    bestanden: list[int] = []
    verworfen: list[dict] = []
    for year in gelesen["years"]:
        fehlend = [a for a in arten if ist_reihe.get(year, {}).get(a) is None]
        if fehlend:
            verworfen.append({
                "year": year,
                "grund": f"Tabelle 1104 führt für {year} keinen Wert zu "
                         f"{', '.join(sorted(fehlend))} — ohne Zweitquelle ist "
                         f"die Jahresbeschriftung ungeprüft"})
            continue
        abweichend = []
        for art in arten:
            hier = zeilen[art][year]["ist"]
            dort = round(ist_reihe[year][art] / 1000)
            if hier != dort:
                abweichend.append(f"{art}: 1103 {hier} vs. 1104 {dort} T€")
        if abweichend:
            verworfen.append({"year": year,
                              "grund": "; ".join(abweichend)})
            continue
        bestanden.append(year)
    return {"bestanden": bestanden, "verworfen": verworfen}


def lies_1103(text: str, ist_reihe: dict[int, dict[str, float]]) -> dict:
    """Eine Ausgabe der Tabelle 1103 lesen und prüfen.

    Zurück: ``{"zeilen": [...], "years": [...], "verworfen": [...],
    "probes": [...], "spanne": (von, bis), "unbekannt": [...]}``.
    ``zeilen`` sind speicherfertige Datensätze mit Beträgen **in Euro**.
    """
    gelesen = parse_1103(text)
    probes: list[str] = []
    if not gelesen["years"] or not gelesen["zeilen"]:
        return {"zeilen": [], "years": [], "verworfen": [], "probes": probes,
                "spanne": gelesen["spanne"], "unbekannt": gelesen["unbekannt"],
                "abbruch": "In der Datei ist keine Tabelle 1103 zu finden."}

    # 1. Die Tabelle muss zu ihrem eigenen Titel passen: so viele Jahresblöcke,
    #    wie der Titel Jahre nennt. Das prüft `parse_1103` schon beim Lesen
    #    (Zeilen mit anderer Feldzahl kommen gar nicht durch) — hier fällt nur
    #    auf, wenn dadurch NICHTS übrig blieb.
    abweichungen = summenprobe(gelesen)
    if not abweichungen or any(v for year in abweichungen.values()
                               for v in year.values()):
        schlimmste = max((abs(v) for year in abweichungen.values()
                          for v in year.values()), default=None)
        return {"zeilen": [], "years": [], "verworfen": [], "probes": probes,
                "spanne": gelesen["spanne"], "unbekannt": gelesen["unbekannt"],
                "abbruch": (
                    "Die Summenprobe reißt: Die Steuerarten ergeben nicht die "
                    f"Zeile „total“ (größte Abweichung {schlimmste} T€). "
                    "Entweder fehlt eine Zeile, oder die Tabelle ist anders "
                    "gebaut als bisher."
                    + (f" Nicht zugeordnet: {gelesen['unbekannt']}."
                       if gelesen["unbekannt"] else ""))}
    probes.append("steuerplan_summenzeile")

    if anteilsprobe(gelesen):
        return {"zeilen": [], "years": [], "verworfen": [], "probes": probes,
                "spanne": gelesen["spanne"], "unbekannt": gelesen["unbekannt"],
                "abbruch": "Die Anteilsprobe reißt: Ein Betrag steht neben "
                           "einem Prozentsatz, der nicht zu ihm gehört."}
    probes.append("steuerplan_anteilsprobe")

    abgleich = istabgleich(gelesen, ist_reihe)
    if abgleich["bestanden"]:
        probes.append("steuerplan_istabgleich")

    zeilen: list[dict] = []
    for art, je_jahr in gelesen["zeilen"].items():
        if art in (SUMME, ZUWEISUNGEN):
            continue
        for year in abgleich["bestanden"]:
            werte = je_jahr[year]
            zeilen.append({
                "year": year, "art": art,
                "plan": werte["plan"] * 1000.0,
                "ist": werte["ist"] * 1000.0,
                "provisional": year in gelesen["provisional"],
            })
    zeilen.sort(key=lambda z: (z["year"], z["art"]))
    return {"zeilen": zeilen, "years": abgleich["bestanden"],
            "verworfen": abgleich["verworfen"], "probes": probes,
            "spanne": gelesen["spanne"], "unbekannt": gelesen["unbekannt"],
            "abbruch": None}


# --- Tabelle 1105: die Hebesätze --------------------------------------------

_HEBESATZ_ZEILE = re.compile(r"^(\d{4})\s+(\d{2,4})\s+(\d{2,4})\s+(\d{2,4})$")


def erkenne_1105(text: str) -> int | None:
    """Das Startjahr aus dem Titel: „Realsteuer-Hebesätze in Prozent seit 1980".

    Im Extrakt klebt die Fußnotenziffer an der Jahreszahl („seit 19801") —
    ``\\d{4}`` liest trotzdem 1980, weil es nach vier Stellen aufhört."""
    treffer = re.search(r"1105\b.{0,120}?seit\s+(\d{4})", text, re.S)
    if not treffer:
        return None
    year = int(treffer.group(1))
    return year if 1900 <= year <= 2100 else None


def _bereich_1105(text: str) -> list[str]:
    """Die Zeilen der Tabelle 1105 — ab ihrem Titel, bis zur Quellenangabe.

    Nötig, weil 1105 auf demselben Blatt steht wie 1104: Ohne diese Grenze
    liefe der Zeilenleser über die Steuereinnahmen von 2004 bis 2025 mit."""
    zeilen = text.splitlines()
    start = next((i for i, z in enumerate(zeilen)
                  if re.match(r"^\s*1105\b", z)), None)
    if start is None:
        return []
    aus: list[str] = []
    for zeile in zeilen[start + 1:]:
        if re.match(r"^\s*Quelle\s*:", zeile):
            break
        aus.append(zeile)
    return aus


def spaltenprobe(text: str) -> bool:
    """Steht die Gewerbesteuer wirklich rechts von den beiden Grundsteuern?

    Die Spaltenreihenfolge wird nicht angenommen, sondern am Tabellenkopf
    gelesen: „Grundsteuer" und darunter „A B", dahinter „Gewerbe-steuer".
    Dreht die Stadt die Spalten einmal um, kommt nichts herein statt der
    Gewerbesteuer unter dem Namen der Grundsteuer.
    """
    kopf: list[str] = []
    for zeile in _bereich_1105(text):
        if _SPALTENMARKE.match(zeile):
            break
        kopf.append(zeile)
    zusammen = _norm(" ".join(kopf))
    if "grundsteuer" not in zusammen or "gewerbe" not in zusammen:
        return False
    if zusammen.index("grundsteuer") > zusammen.index("gewerbe"):
        return False
    # Die beiden Grundsteuer-Spalten heißen im Kopf nur „A“ und „B“, und sie
    # stehen eine Zeile tiefer als „Grundsteuer“ — sonst stünde nirgends,
    # welche der beiden links liegt. Geprüft wird der ZEILENANFANG, nicht die
    # ganze Zeile: Dahinter läuft die zweite Hälfte des umgebrochenen
    # Nachbartitels weiter („A B steuer“ — das „steuer“ gehört zu
    # „Gewerbe-“). Eine `fullmatch`-Prüfung fiel genau darüber.
    return any(re.match(r"\s*A\s+B\b", z) for z in kopf)


def parse_1105(text: str) -> list[dict]:
    """Tabelle 1105 → ``[{year, "Grundsteuer A": …, "Grundsteuer B": …,
    "Gewerbesteuer": …}]``, aufsteigend nach Jahr.

    Eine Zeile ist ein Jahr und **genau drei** ganze Zahlen. Die Beträge aus
    1104 auf demselben Blatt tragen Tausenderpunkte und acht Spalten — sie
    passen deshalb nicht auf das Muster, selbst wenn die Bereichsgrenze
    einmal nicht greifen sollte.
    """
    aus: list[dict] = []
    for zeile in _bereich_1105(text):
        treffer = _HEBESATZ_ZEILE.match(zeile.strip())
        if not treffer:
            continue
        year = int(treffer.group(1))
        if not 1900 <= year <= 2100:
            continue
        eintrag = {"year": year}
        for i, art in enumerate(HEBESATZ_ARTEN, start=2):
            eintrag[art] = int(treffer.group(i))
        aus.append(eintrag)
    aus.sort(key=lambda z: z["year"])
    return aus


def treppenprobe(zeilen: list[dict]) -> list[int]:
    """Jede Zeile muss sich von der vorhergehenden unterscheiden.

    Die Tabelle sagt in ihrer Fußnote, was sie führt: „Ausgewiesen sind die
    Jahre, in denen sich die Hebesätze geändert haben." Zwei gleiche Zeilen
    hintereinander wären also entweder ein Fehler der Tabelle oder einer im
    Lesen — in jedem Fall nichts, was gespeichert gehört.

    Zurück: die Jahre, die nichts ändern (leer = bestanden).
    """
    doppelt: list[int] = []
    for vor, jetzt in zip(zeilen, zeilen[1:]):
        if all(jetzt[a] == vor[a] for a in HEBESATZ_ARTEN):
            doppelt.append(jetzt["year"])
    return doppelt


def sprungjahrprobe(zeilen: list[dict],
                    grundsteuer_ist: dict[int, float]) -> dict:
    """Wirkt die Änderung im **genannten** Jahr — oder erst im Jahr danach?

    Die Probe gegen den Jahresversatz (s. Modulkopf). Für jedes Änderungsjahr
    ``J``, in dem der Grundsteuer-B-Hebesatz stieg, muss gelten:

        Aufkommen(J) / Aufkommen(J−1)  >  Aufkommen(J+1) / Aufkommen(J)

    Auf Deutsch: Das Aufkommen zieht in dem Jahr an, das die Tabelle nennt, und
    nicht im nächsten. Verglichen werden nur **Verhältnisse**, keine Beträge —
    die Probe braucht deshalb keine Annahme darüber, wie viel ein
    Hebesatzpunkt bringt.

    Nicht prüfbar sind Jahre ohne Aufkommensreihe (vor 1998) oder ohne
    Folgejahr, und die in :data:`BEMESSUNG_NEU`. Das wird zurückgegeben, nicht
    stillschweigend übergangen.

    Zurück: ``{"bestanden": [...], "gerissen": [...], "nicht_pruefbar": [...]}``
    """
    bestanden, gerissen, offen = [], [], []
    for vor, jetzt in zip(zeilen, zeilen[1:]):
        year = jetzt["year"]
        if jetzt["Grundsteuer B"] <= vor["Grundsteuer B"]:
            offen.append({"year": year,
                          "grund": "Grundsteuer B unverändert oder gesenkt — "
                                   "die Probe misst einen Anstieg"})
            continue
        if year in BEMESSUNG_NEU:
            offen.append({"year": year, "grund": BEMESSUNG_NEU[year]})
            continue
        fehlt = [j for j in (year - 1, year, year + 1) if not grundsteuer_ist.get(j)]
        if fehlt:
            offen.append({"year": year,
                          "grund": "die Aufkommensreihe führt "
                                   f"{', '.join(str(j) for j in fehlt)} nicht"})
            continue
        im_jahr = grundsteuer_ist[year] / grundsteuer_ist[year - 1] - 1
        danach = grundsteuer_ist[year + 1] / grundsteuer_ist[year] - 1
        eintrag = {"year": year, "im_jahr": im_jahr, "danach": danach,
                   "hebesatz_vorher": vor["Grundsteuer B"],
                   "hebesatz_nachher": jetzt["Grundsteuer B"]}
        (bestanden if im_jahr > danach else gerissen).append(eintrag)
    return {"bestanden": bestanden, "gerissen": gerissen, "nicht_pruefbar": offen}


def lies_1105(text: str, grundsteuer_ist: dict[int, float]) -> dict:
    """Eine Ausgabe der Tabelle 1105 lesen und prüfen.

    Zurück: ``{"zeilen": [...], "probes": [...], "sprungjahre": {...},
    "abbruch": str|None}``. ``zeilen`` sind speicherfertige Datensätze
    ``{year, art, rate, prior_rate}``.
    """
    start = erkenne_1105(text)
    roh = parse_1105(text)
    probes: list[str] = []
    if not roh:
        return {"zeilen": [], "probes": probes, "sprungjahre": {"bestanden": [], "gerissen": [], "nicht_pruefbar": []},
                "abbruch": "In der Datei ist keine Tabelle 1105 zu finden."}
    if not spaltenprobe(text):
        return {"zeilen": [], "probes": probes, "sprungjahre": {"bestanden": [], "gerissen": [], "nicht_pruefbar": []},
                "abbruch": "Der Tabellenkopf nennt die Spalten nicht in der "
                           "erwarteten Reihenfolge (Grundsteuer A, Grundsteuer "
                           "B, Gewerbesteuer) — es wird nichts übernommen."}
    if start is not None and roh[0]["year"] != start:
        return {"zeilen": [], "probes": probes, "sprungjahre": {"bestanden": [], "gerissen": [], "nicht_pruefbar": []},
                "abbruch": f"Der Titel nennt „seit {start}“, die erste Zeile "
                           f"ist aber {roh[0]['year']}."}
    probes.append("hebesatz_spaltenkopf")

    doppelt = treppenprobe(roh)
    if doppelt:
        return {"zeilen": [], "probes": probes, "sprungjahre": {"bestanden": [], "gerissen": [], "nicht_pruefbar": []},
                "abbruch": "Die Tabelle führt nach eigener Fußnote nur "
                           "Änderungsjahre, aber diese ändern nichts: "
                           f"{doppelt}."}
    probes.append("hebesatz_treppe")

    sprung = sprungjahrprobe(roh, grundsteuer_ist)
    if sprung["gerissen"]:
        years = ", ".join(str(e["year"]) for e in sprung["gerissen"])
        return {"zeilen": [], "probes": probes, "sprungjahre": sprung,
                "abbruch": (
                    f"Die Sprungjahr-Probe reißt für {years}: Das Aufkommen "
                    "zieht dort nicht im genannten Jahr an, sondern später. "
                    "Das ist genau das Muster eines Jahresversatzes (vgl. "
                    "Datensatz 1106) — es wird nichts übernommen.")}
    if sprung["bestanden"]:
        probes.append("hebesatz_sprungjahr")

    zeilen: list[dict] = []
    for i, eintrag in enumerate(roh):
        vorher = roh[i - 1] if i else None
        for art in HEBESATZ_ARTEN:
            zeilen.append({
                "year": eintrag["year"], "art": art,
                "rate": eintrag[art],
                "prior_rate": vorher[art] if vorher else None,
            })
    return {"zeilen": zeilen, "probes": probes, "sprungjahre": sprung,
            "abbruch": None}


# --- Für die Ausgabe --------------------------------------------------------

#: Kurznamen der Proben — für den Herkunftsnachweis, der neben der Zahl steht.
PROBEN_KURZ: dict[str, str] = {
    "steuerplan_summenzeile": "Summenzeile",
    "steuerplan_anteilsprobe": "Anteilsspalten",
    "steuerplan_istabgleich": "Abgleich mit Tabelle 1104",
    "hebesatz_spaltenkopf": "Spaltenkopf",
    "hebesatz_treppe": "nur Änderungsjahre",
    "hebesatz_sprungjahr": "Sprungjahr gegen das Aufkommen",
}


def zusammenlegen(ausgaben: list[tuple[str, list[dict]]],
                  schluessel) -> list[dict]:
    """Die Jahrgänge mehrerer Ausgaben zu **einer** Reihe machen.

    ``ausgaben`` kommt in der Reihenfolge älteste Ausgabe zuerst; bei gleichem
    Schlüssel gewinnt deshalb die **jüngere** Ausgabe. Das ist die richtige
    Richtung: Sie trägt die revidierten Werte — aus einem vorläufigen
    Rechnungsergebnis wird ein abgerechnetes, und das soll das vorläufige
    ersetzen und nicht umgekehrt.

    Genau dafür wird das Archiv gelesen: Jede Ausgabe von 1103 führt nur drei
    Jahrgänge, aber jede führt **andere** drei.
    """
    nach_schluessel: dict[tuple, dict] = {}
    for herkunft, zeilen in ausgaben:
        for zeile in zeilen:
            nach_schluessel[schluessel(zeile)] = {**zeile, "ausgabe": herkunft}
    return [nach_schluessel[k] for k in sorted(nach_schluessel)]
