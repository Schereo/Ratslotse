"""Die dreizehn Kennzahlen — und was passiert, wenn man sie nachschlägt.

Am Ende jedes Rechenschaftsberichts steht eine Anlage, die den ganzen
Jahresabschluss auf dreizehn Zahlen eindampft: Eigenkapitalquote,
Anlagenintensität, Steuerquote, Verschuldung je Kopf. Das ist die Zusammen-
fassung, die die Stadt selbst für die Ratsmitglieder schreibt — mit den
**gedruckten Rechenwegen** darunter („Ermittlung: Sachvermögen * 100 /
Bilanzsumme").

Zwei Dinge machen diese Anlage wertvoller als eine weitere Tabelle:

**Die Rechenwege stehen dabei.** Wir müssen keine Kennzahl erfinden und keine
Formel raten — wir zeigen die der Stadt, im Wortlaut, mit Beleg. Wo wir
nachrechnen können, rechnen wir nach (:func:`gegen_bilanz`); für 2016–2024
stimmen Anlagenintensität, Infrastrukturquote und Eigenkapitalquote II auf
die letzte gedruckte Nachkommastelle mit unserem Bilanz-Parser überein.

**Jeder Bericht zeigt fünf Jahre, nicht eins.** Der Bericht 2019 druckt
2015–2019, der Bericht 2024 druckt 2020–2024. Sechs Berichte decken so
2015–2024 ab, und die mittleren Jahrgänge stehen bis zu fünfmal da — in
fünf Berichten, aus fünf Jahren Rückschau.

WARUM ``bericht_jahr`` IM SCHLÜSSEL STEHT
------------------------------------------
Weil dieselbe Kennzahl desselben Jahres in zwei Berichten **verschiedene
Werte** hat. Nicht selten und nicht klein:

* Verschuldung je Einwohner (inkl. Rückstellungen) für 2021 — der Bericht
  2021 druckt 2.340,30 €, der Bericht 2024 druckt 2.224,11 €.
* Netto-Neuinvestitionen je Einwohner 2021 — 120,45 € gegen 151,81 €.
* Personalintensität 2020 — 26,03 % gegen 25,09 %.

Das sind keine Fehler, sondern Nachträge: Der Abschluss eines Jahres wird
später korrigiert, und der nächste Bericht druckt den korrigierten Wert.
Ohne ``bericht_jahr`` im Schlüssel überschriebe der neuere Bericht den
älteren still — und die Revision, die eine eigene Nachricht ist, wäre weg.
:func:`ueberlappungsprobe` sucht sie deshalb gezielt.

WAS DIE PROBE VON EINER REVISION UNTERSCHEIDET
-----------------------------------------------
Die Berichte drucken **unterschiedlich genau**: 2019 steht „48%", ab 2021
„53,15%". Ein stumpfer Vergleich meldete deshalb reihenweise Abweichungen,
die nur Rundung sind. Die Probe leitet ihre Toleranz darum aus der
**gröberen der beiden gedruckten Genauigkeiten** ab — bei „48%" gegen
„48,32%" ist alles unter einem halben Prozentpunkt kein Widerspruch,
sondern dieselbe Zahl in zwei Auflösungen.

ZWEI BERICHTE HABEN DIESE ANLAGE NICHT
---------------------------------------
2017 und 2018 zeigen dieselben Kennzahlen **nur als Diagramm** — die Werte
stehen als Balkenbeschriftung im Text, zwischen den Achsenbeschriftungen, und
der „Ermittlung:"-Satz steht dort *vor* seinem Diagramm statt darunter. Das
wäre zu raten, und es wäre umsonst: Die Jahrgänge 2015–2018 stehen als
Tabelle im Bericht 2019. Deshalb liest dieses Modul nur die Tabelle.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

#: Die Kopfzeile der Tabelle — und zugleich die Liste der Jahresspalten.
#: Mindestens drei Jahre, damit eine beliebige Jahreszahlen-Folge im Fließtext
#: nicht als Tabellenkopf durchgeht.
KOPF = re.compile(r"Haushaltsjahr\s+(20\d\d(?:\s+20\d\d){2,})")

#: Seitenmarken des Rechenschaftsberichts („RB 121"). Sie stehen mitten im
#: Text, und ihre Nummer sieht aus wie ein Tabellenwert — erst raus, dann
#: zählen.
SEITENMARKE = re.compile(r"\bRB\s+\d{1,3}\b")

#: Ein Zahlenwert der Tabelle: „48%", „53,15%", „170.693", „-21,32",
#: „2.251,33". Bewusst als Vollmatch benutzt, damit „(31.12." und „HH-Jahr)"
#: keine Werte werden.
WERT = re.compile(r"(-?\d{1,3}(?:\.\d{3})*(?:,\d+)?)(%?)")

#: Wo die Tabelle endet und der Rechenweg-Teil beginnt.
ENDE = re.compile(r"Ermittlung")

#: „Einwohnerzahl Stand 31.12.2022: 173.987 (Prognose)" — die Fußnote unter
#: der Tabelle. Ihre Zahl sieht aus wie ein Tabellenwert, gehört aber zu keiner
#: Zeile. Zwei Eigenheiten des PDF-Auszugs stecken in diesem Muster: Zwischen
#: jedem Buchstaben steht ein erlaubter Umbruch (2022 bricht „Ei\nnwohnerzahl"
#: mitten entzwei), und geschnitten wird **bis zum Ende** des Tabellenbereichs,
#: weil 2024 der Zeilenumbruch vor der Zahl steht („31.12.2024\n*): 176.068").
#: Nach dieser Fußnote kommt in keinem Bericht noch eine Tabellenzeile.
SCHLUSSZEILE = re.compile(r"\s*".join("Einwohnerzahl") + r"\s+Stand.*", re.S)


@dataclass(frozen=True)
class Kennzahl:
    """Eine der dreizehn — mit dem Muster, das ihre Schreibweisen einfängt.

    Das Muster muss **zwei** Beschriftungen treffen: die der Tabellenzeile
    („Verschuldung in EUR pro Einwohner (ohne Rückstellungen)") und die
    Überschrift über dem Rechenweg („Verschuldung pro Einwohner (ohne
    Rückstellungen)"). Sie sind nie gleich, und über die Jahrgänge ändern
    sie sich zusätzlich: aus „Personalintensität" wurde
    „Personalintensitätsquote", und der Bericht 2019 schreibt zweimal
    „Eigenkaptalquote" ohne i.
    """

    key: str
    label: str
    einheit: str          # "prozent" | "eur" | "anzahl"
    muster: str

    def passt(self, beschriftung: str) -> bool:
        return re.match(self.muster, _flach(beschriftung)) is not None


#: Reihenfolge wie im Dokument. „Neuverschuldung" enthält „verschuldung" —
#: deshalb sind alle Muster am Anfang verankert, sonst finge die eine die
#: andere ein.
KENNZAHLEN: tuple[Kennzahl, ...] = (
    Kennzahl("eigenkapitalquote_1", "Eigenkapitalquote I (ohne Sonderposten)",
             "prozent", r"eigenkap.?talquote i(?!i)"),
    Kennzahl("eigenkapitalquote_2", "Eigenkapitalquote II (mit Sonderposten)",
             "prozent", r"eigenkap.?talquote ii"),
    Kennzahl("einwohner", "Einwohnende am 31.12.",
             "anzahl", r"anzahl der einwohnenden"),
    Kennzahl("verschuldung_je_einwohner",
             "Verschuldung je Einwohner*in (ohne Rückstellungen)",
             "eur", r"verschuldung .*ohne r[üu]ckstellungen"),
    Kennzahl("verschuldung_mit_rueckstellungen_je_einwohner",
             "Verschuldung je Einwohner*in (mit Rückstellungen)",
             "eur", r"verschuldung .*inkl"),
    Kennzahl("neuverschuldung_je_einwohner",
             "Neuverschuldung je Einwohner*in (nur Geldschulden)",
             "eur", r"neuverschuldung"),
    Kennzahl("vermoegen_je_einwohner", "Vermögen je Einwohner*in",
             "eur", r"verm[öo]gen "),
    Kennzahl("netto_neuinvestitionen_je_einwohner",
             "Netto-Neuinvestitionen je Einwohner*in",
             "eur", r"netto-neuinvestitionen"),
    Kennzahl("anlagenintensitaet", "Anlagenintensität",
             "prozent", r"anlagenintensit[äa]t"),
    Kennzahl("reinvestitionsquote", "Reinvestitionsquote auf Sachvermögen",
             "prozent", r"reinvestitionsquote"),
    Kennzahl("infrastrukturquote", "Infrastrukturquote",
             "prozent", r"infrastrukturquote"),
    Kennzahl("personalintensitaet", "Personalintensität",
             "prozent", r"(aktive )?personalintensit[äa]t"),
    Kennzahl("steuerquote", "Steuerquote",
             "prozent", r"steuerquote"),
)

#: Was sich aus unserer Bilanz nachrechnen lässt: Kennzahl → (Zähler-Rolle,
#: Nenner ist immer die Bilanzsumme). Nur diese drei — bei den Kennzahlen je
#: Einwohner rechnet die Stadt mit einer *anderen* Schuldenabgrenzung als
#: ``council_schulden``, und ein Abgleich meldete dort verlässlich eine
#: Differenz, die keine ist.
BILANZ_QUOTE = {
    "eigenkapitalquote_2": "nettoposition",
    "anlagenintensitaet": "sachvermoegen",
    "infrastrukturquote": "infrastrukturvermoegen",
}

#: Die Aktiv-Posten, die zusammen die Bilanzsumme ergeben.
AKTIVA = ("immaterielles_vermoegen", "sachvermoegen", "finanzvermoegen",
          "liquide_mittel", "aktive_rap")

#: Schreibweisen, die denselben Rechenweg meinen. Bewusst kurz und
#: aufzählend: Wer hier großzügig normalisiert, verschmilzt zwei verschiedene
#: Definitionen zu einer Reihe — genau der Fehler, den die Fassungen
#: verhindern sollen. „inkl." gegen „inklusive" ist derselbe Satz; aus
#: „Gesamtschulden" gegen „Schulden" wird hier **nicht** derselbe.
SCHREIBWEISEN = ((r"\binkl\.", "inklusive"), (r"\s+", " "), (r"[*]", " * "))

PROBE_UEBERLAPPUNG = "kennzahlen_ueberlappung"
PROBE_BILANZ = "kennzahlen_gegen_bilanz"
PROBE_VERMOEGEN = "kennzahlen_vermoegensprobe"


def _flach(text: str) -> str:
    """Kleinschreiben, Umbrüche und Mehrfach-Leerzeichen weg."""
    return re.sub(r"\s+", " ", text).strip().lower()


def _zahl(roh: str) -> tuple[float, int]:
    """„2.251,33" → (2251.33, 2). Die zweite Zahl ist die gedruckte Genauigkeit."""
    ohne = roh.replace(".", "")
    stellen = len(ohne.split(",")[1]) if "," in ohne else 0
    return float(ohne.replace(",", ".")), stellen


def jahresspalten(text: str) -> list[int]:
    """Die Jahre der Kopfzeile — gelesen, nicht angenommen.

    Alle sechs Berichte mit Tabelle zeigen fünf Spalten. Das steht trotzdem
    nirgends im Code: Käme ein Jahrgang mit sechs, verteilte ein fester Wert
    die Zahlen um eine Spalte versetzt, und jede Reihe wäre um ein Jahr
    verschoben — der Fehler, der bei einer Jahresreihe niemandem auffällt.
    """
    m = KOPF.search(text)
    return [int(j) for j in m.group(1).split()] if m else []


def parse_kennzahlen(text: str, bericht_jahr: int) -> tuple[list[dict], list[str]]:
    """Die Tabelle. Liefert die Werte und die **nicht** zugeordneten Zeilen.

    Die zweite Liste ist Absicht: Eine Beschriftung, die zu keiner der
    dreizehn passt, ist entweder eine neue Kennzahl oder ein Parser-Fehler.
    Beides gehört gemeldet, nicht verschluckt.
    """
    jahre = jahresspalten(text)
    if len(jahre) < 3:
        return [], []

    m = KOPF.search(text)
    rest = text[m.end():]
    schluss = ENDE.search(rest)
    tabelle = rest[:schluss.start()] if schluss else rest
    tabelle = SCHLUSSZEILE.sub(" ", SEITENMARKE.sub(" ", tabelle))

    zeilen: list[dict] = []
    unbekannt: list[str] = []
    beschriftung: list[str] = []
    werte: list[tuple[float, int, bool]] = []

    def abschliessen() -> None:
        if not werte:
            return
        text_ = " ".join(beschriftung)
        treffer = next((k for k in KENNZAHLEN if k.passt(text_)), None)
        if treffer is None:
            unbekannt.append(_flach(text_) or "(ohne Beschriftung)")
        else:
            for year, (wert, stellen, prozent) in zip(jahre, werte):
                # Das Prozentzeichen ist ein zweites, unabhängiges Signal für
                # die Einheit — steht es an einer Euro-Kennzahl, stimmt die
                # Spaltenzuordnung nicht.
                if prozent != (treffer.einheit == "prozent"):
                    unbekannt.append(f"{treffer.key}: Einheit passt nicht zum Wert {wert}")
                    break
                zeilen.append({"bericht_jahr": bericht_jahr, "kennzahl": treffer.key,
                               "label": treffer.label, "year": year, "wert": wert,
                               "einheit": treffer.einheit, "stellen": stellen})
        beschriftung.clear()
        werte.clear()

    for wort in tabelle.split():
        treffer = WERT.fullmatch(wort)
        if treffer:
            werte.append((*_zahl(treffer.group(1)), bool(treffer.group(2))))
            if len(werte) == len(jahre):
                abschliessen()
        else:
            if werte:                       # neue Zeile beginnt, alte war kurz
                unbekannt.append(_flach(" ".join(beschriftung)))
                beschriftung.clear()
                werte.clear()
            beschriftung.append(wort)
    if werte:
        unbekannt.append(_flach(" ".join(beschriftung)) + " (Zeile blieb unvollständig)")
    return zeilen, unbekannt


def parse_formeln(text: str, bericht_jahr: int) -> list[dict]:
    """Die gedruckten Rechenwege, jeder mit der Überschrift darüber.

    Auch die Formel gehört zum Bericht und nicht zur Kennzahl: Für die
    Verschuldung je Einwohner steht 2019 „Gesamtschulden / Einwohnerzahl",
    2024 „Schulden / Einwohnerzahl". Die Kennzahl heißt gleich, gerechnet
    wird anders.
    """
    m = KOPF.search(text)
    if not m:
        return []
    block = SEITENMARKE.sub(" ", text[m.end():])
    zeilen = block.split("\n")

    formeln: list[dict] = []
    for i, zeile in enumerate(zeilen):
        stelle = zeile.find("Ermittlung")
        if stelle < 0:
            continue
        formel = zeile[stelle:].split(":", 1)[-1].strip()
        # WO EINE FORMEL AUFHÖRT. Sie bricht auf zwei Arten um: mit Trennstrich
        # („Gesamtaufwen-\ndungen") und ohne („… / ordentliche
        # \nGesamtaufwendungen"). Eine Regel, die nur den Trennstrich kennt,
        # schneidet die zweite Art mitten im Satz ab — und ein abgeschnittener
        # Rechenweg ist ein falsches Zitat, kein fehlendes.
        #
        # Fortgesetzt wird deshalb, solange die nächste Zeile weder leer ist
        # noch eine der dreizehn Überschriften trägt. Beides kennen wir
        # genau; alles andere gehört noch zur Formel. Die Obergrenze von drei
        # Zeilen ist eine Reißleine, keine Messung — die längste Formel im
        # Bestand braucht eine.
        j = i
        while j + 1 < len(zeilen) and j - i < 3:
            weiter = zeilen[j + 1].strip()
            if not weiter or "Ermittlung" in weiter:
                break
            if any(k.passt(weiter) for k in KENNZAHLEN):
                break
            j += 1
            formel = (formel[:-1] if formel.endswith("-") else formel + " ") + weiter
        ueberschrift = next((z.strip() for z in reversed(zeilen[:i]) if z.strip()), "")
        treffer = next((k for k in KENNZAHLEN if k.passt(ueberschrift)), None)
        if treffer:
            formeln.append({"bericht_jahr": bericht_jahr, "kennzahl": treffer.key,
                            "ueberschrift": re.sub(r"\s+", " ", ueberschrift).strip(),
                            "formel": re.sub(r"\s+", " ", formel).strip()})
    return formeln


def _formel_flach(formel: str) -> str:
    text = _flach(formel)
    for muster, ersatz in SCHREIBWEISEN:
        text = re.sub(muster, ersatz, text)
    return text.strip()


def fassungen(formeln: list[dict]) -> dict[tuple[str, int], int]:
    """(Kennzahl, Bericht) → laufende Nummer des gedruckten Rechenwegs.

    Drei der dreizehn Kennzahlen haben zwischen 2019 und 2024 ihre Definition
    gewechselt, nicht nur ihren Wert:

    * Personalintensität — „Aufwand für Personal (inklusive Versorgung)"
      wurde „Aufwendungen für aktives Personal". Die Versorgungsempfänger
      fielen heraus; für 2020 sinkt die Quote dadurch von 26,03 % auf 25,09 %.
    * Vermögen je Einwohner*in — „Gesamtvermögen (inklusive liquide Mittel)"
      wurde „Aktiva (ohne aktive Rechnungsabgrenzung)".
    * Verschuldung je Einwohner*in — „Gesamtschulden" wurde „Schulden".

    Über so einen Wechsel darf keine Linie laufen. Die Nummer hier ist das,
    was die Reihe unterbricht — und was auf der Seite als Satz erscheint,
    nicht als Knick, den niemand erklärt.
    """
    nummern: dict[tuple[str, int], int] = {}
    bekannt: dict[str, dict[str, int]] = {}
    for f in sorted(formeln, key=lambda f: (f["kennzahl"], f["bericht_jahr"])):
        je_kennzahl = bekannt.setdefault(f["kennzahl"], {})
        text = _formel_flach(f["formel"])
        nummern[(f["kennzahl"], f["bericht_jahr"])] = je_kennzahl.setdefault(
            text, len(je_kennzahl) + 1)
    return nummern


def stempeln(zeilen: list[dict], formeln: list[dict]) -> list[dict]:
    """Jedem Wert seine Fassung anheften. Ohne gedruckten Rechenweg: ``None``.

    ``None`` heißt „nicht vergleichbar", nicht „wie vorher" — der Bericht 2021
    druckt für die Einwohnerzahl keinen Rechenweg, und ein übernommener wäre
    geraten.
    """
    nummern = fassungen(formeln)
    for z in zeilen:
        z["fassung"] = nummern.get((z["kennzahl"], z["bericht_jahr"]))
    return zeilen


def toleranz(stellen_a: int, stellen_b: int) -> float:
    """Ein halber Schritt der **gröberen** der beiden Genauigkeiten.

    „48%" gegen „48,32%": Der erste Wert kann alles zwischen 47,5 und 48,5
    bedeuten — 0,32 ist innerhalb, also dieselbe Zahl. Ohne diese Regel
    meldete die Überlappungsprobe für den Bericht 2019 jede zweite Zeile.
    """
    return 0.5 * 10 ** -min(stellen_a, stellen_b)


def ueberlappungsprobe(zeilen: list[dict]) -> tuple[int, list[dict]]:
    """Wo zwei Berichte dieselbe Zelle drucken, muss dieselbe Zahl stehen.

    Von 240 Überlappungspaaren im Bestand stimmen 233 exakt überein. Die
    sieben, die es nicht tun, sind der Ertrag dieser Schicht — jede ist eine
    Korrektur, die die Stadt vorgenommen und nirgends angesagt hat:

    * Steuerquote 2021 — 45,90 % (Bericht 2021), dann 49,05 % (2022), dann
      45,92 % (2023). Hoch und wieder zurück: Der Bericht 2022 hat diese Zeile
      verrechnet, der Bericht 2023 hat sie ohne Anmerkung geradegezogen.
    * Verschuldung je Einwohner*in (mit Rückstellungen) 2021 — 2.340,30 €
      wurde 2.224,11 €, also 116 € je Kopf weniger.
    * Netto-Neuinvestitionen je Einwohner*in 2021 — 120,45 € wurde 151,81 €.

    Jeder Fund trägt seine ``art``:

    ``revision``
        Gleicher gedruckter Rechenweg, anderer Wert — die Stadt hat den
        Abschluss des Jahres nachträglich korrigiert.
    ``definition``
        Anderer gedruckter Rechenweg, anderer Wert — nicht dasselbe gemessen.
        Darüber darf keine Linie laufen.
    ``umbenennung``
        Anderer gedruckter Rechenweg, **gleicher** Wert. Der Text wurde
        umformuliert, gemeint war dasselbe: „Gesamtvermögen (inklusive
        liquide Mittel)" und „Aktiva (ohne aktive Rechnungsabgrenzung)"
        liefern über acht Jahrgänge denselben Betrag.

    Die Einteilung wird **gemessen, nicht angenommen**: Ein geänderter
    Rechenweg schaltet den Vergleich nicht ab, er benennt nur, was
    herauskommt. Sonst bliebe unbemerkt, dass zwei der drei Wechsel gar
    keine sind.
    """
    nach_zelle: dict[tuple[str, int], list[dict]] = {}
    for z in zeilen:
        nach_zelle.setdefault((z["kennzahl"], z["year"]), []).append(z)

    bestaetigt = 0
    funde: list[dict] = []
    for (kennzahl, year), gruppe in sorted(nach_zelle.items()):
        gruppe = sorted(gruppe, key=lambda z: z["bericht_jahr"])
        for aelter, juenger in zip(gruppe, gruppe[1:]):
            diff = juenger["wert"] - aelter["wert"]
            gleich = abs(diff) <= toleranz(aelter["stellen"], juenger["stellen"])
            umgestellt = (aelter.get("fassung") and juenger.get("fassung")
                          and aelter["fassung"] != juenger["fassung"])
            if gleich and not umgestellt:
                bestaetigt += 1
                continue
            funde.append({
                "art": "umbenennung" if gleich else
                       ("definition" if umgestellt else "revision"),
                "kennzahl": kennzahl, "year": year,
                "alt": aelter["wert"], "alt_bericht": aelter["bericht_jahr"],
                "neu": juenger["wert"], "neu_bericht": juenger["bericht_jahr"],
                "difference": round(diff, 4)})
    return bestaetigt, funde


def gegen_bilanz(zeilen: list[dict], bilanz: list[dict]) -> tuple[int, list[dict]]:
    """Drei Quoten selbst nachrechnen — aus unserer Bilanz, nicht aus dem Text.

    Das ist der Abgleich über die Quellengrenze: Zähler und Nenner kommen aus
    :mod:`council.bilanz`, das Ergebnis steht gedruckt im Rechenschaftsbericht.
    Stimmen beide, hat der Bilanz-Parser die Posten richtig zugeordnet **und**
    die Kennzahlentabelle ist richtig ausgelesen.
    """
    summe: dict[int, float] = {}
    posten: dict[tuple[int, str], float] = {}
    for b in bilanz:
        if b.get("rolle") in AKTIVA:
            summe[b["year"]] = summe.get(b["year"], 0.0) + b["wert"]
        if b.get("rolle"):
            posten[(b["year"], b["rolle"])] = b["wert"]

    geprueft = 0
    risse: list[dict] = []
    for z in zeilen:
        rolle = BILANZ_QUOTE.get(z["kennzahl"])
        zaehler = posten.get((z["year"], rolle)) if rolle else None
        if zaehler is None or not summe.get(z["year"]):
            continue
        eigen = zaehler * 100 / summe[z["year"]]
        if abs(eigen - z["wert"]) <= toleranz(z["stellen"], z["stellen"]):
            geprueft += 1
        else:
            risse.append({"kennzahl": z["kennzahl"], "year": z["year"],
                          "bericht_jahr": z["bericht_jahr"],
                          "gedruckt": z["wert"], "gerechnet": round(eigen, 4)})
    return geprueft, risse


def vermoegensprobe(zeilen: list[dict], bilanz: list[dict]) -> tuple[int, list[dict]]:
    """Zwei Zeilen derselben Tabelle mal genommen — und die Bilanz kommt heraus.

    Die Tabelle druckt „Vermögen in EUR pro Einwohner" und „Anzahl der
    Einwohnenden" als getrennte Zeilen. Ihr Produkt muss die Aktiva ohne
    aktive Rechnungsabgrenzung ergeben — so steht es im Rechenweg des
    Berichts, und so steht es in :mod:`council.bilanz`.

    Das ist die schärfste Probe dieser Schicht, weil vier voneinander
    unabhängige Größen zusammenkommen: zwei Zeilen der Kennzahlentabelle und
    zwei Posten unseres Bilanz-Parsers. Über 2017–2024 geht sie in **jedem**
    Jahrgang auf; die Abweichung bleibt unter einem Tausendstel Prozent.

    Die Toleranz ist nicht gegriffen, sondern gerechnet: Ein je-Kopf-Wert mit
    zwei Nachkommastellen kann um einen halben Cent danebenliegen, und das
    mal 176.000 Einwohnenden sind rund 880 €. Alles darüber wäre echt.
    """
    aktiva: dict[int, float] = {}
    rap: dict[int, float] = {}
    for b in bilanz:
        if b.get("rolle") in AKTIVA:
            aktiva[b["year"]] = aktiva.get(b["year"], 0.0) + b["wert"]
        if b.get("rolle") == "aktive_rap":
            rap[b["year"]] = b["wert"]

    # Nur Zeilen DESSELBEN Berichts multiplizieren — zwei Berichte gemischt
    # wäre eine andere Rechnung, und ihr Ergebnis sagte nichts über beide.
    je_bericht: dict[tuple[int, int], dict[str, dict]] = {}
    for z in zeilen:
        je_bericht.setdefault((z["bericht_jahr"], z["year"]), {})[z["kennzahl"]] = z

    geprueft = 0
    risse: list[dict] = []
    for (bericht_jahr, year), zellen in sorted(je_bericht.items()):
        kopf = zellen.get("vermoegen_je_einwohner")
        leute = zellen.get("einwohner")
        if not (kopf and leute) or year not in aktiva:
            continue
        soll = aktiva[year] - rap.get(year, 0.0)
        ist = kopf["wert"] * leute["wert"]
        if abs(ist - soll) <= 0.5 * 10 ** -kopf["stellen"] * leute["wert"]:
            geprueft += 1
        else:
            risse.append({"bericht_jahr": bericht_jahr, "year": year,
                          "gerechnet": round(ist, 2), "bilanz": round(soll, 2),
                          "difference": round(ist - soll, 2)})
    return geprueft, risse


def neueste(zeilen: list[dict]) -> list[dict]:
    """Je Kennzahl und Jahr der Wert aus dem **jüngsten** Bericht.

    Die Reihe, die man zeigt. Die älteren Stände bleiben in der Datenbank —
    sie sind die Belegkette für jede Revision.
    """
    beste: dict[tuple[str, int], dict] = {}
    for z in zeilen:
        schluessel = (z["kennzahl"], z["year"])
        if schluessel not in beste or z["bericht_jahr"] > beste[schluessel]["bericht_jahr"]:
            beste[schluessel] = z
    return sorted(beste.values(), key=lambda z: (z["kennzahl"], z["year"]))
