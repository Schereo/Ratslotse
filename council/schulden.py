"""Die Schuldenzeitreihe der Stadt Oldenburg — Tabelle 1108 des Statistischen
Jahrbuchs, 1995 bis heute.

„Wie viel Schulden hat Oldenburg?" ist eine der häufigsten Fragen an den
Haushalt, und der Bereich konnte sie bis 08/2026 nicht beantworten. Diese
Schicht beantwortet sie — mit einer Seite, die alles mitbringt, was dafür
nötig ist: dreißig Jahre am Stück, aufgeteilt nach Schuldenart, mit Summe und
Pro-Kopf-Betrag.

Welche Abgrenzung — und warum das die wichtigste Zeile dieses Moduls ist
--------------------------------------------------------------------------
Bei Kommunalschulden gibt es zwei Zahlen, die sich um mehr als das Doppelte
unterscheiden, und beide heißen „die Schulden der Stadt". Wer sie verwechselt,
liegt nicht ein bisschen daneben, sondern um einen Faktor. Tabelle 1108 zählt:

    Kernhaushalt **einschließlich der Eigenbetriebe** — also die Stadt
    Oldenburg als Rechtsträger. Ohne die rechtlich selbstständigen
    Beteiligungen (AöR, GmbH), auch wenn sie der Stadt gehören.

Das steht nicht als Satz in der Tabelle; es steht in ihren Spalten und
Fußnoten, und zwar dreifach:

1. **Die vierte Spalte heißt „Schulden der Eigenbetriebe einschließlich
   Kliniken und innere Darlehen".** Eigenbetriebe sind also drin — sie haben
   keine eigene Rechtspersönlichkeit, ihre Schulden sind rechtlich die der
   Stadt.
2. **Fußnote 1: „Ab 1999 ohne Kliniken, die jetzt als Klinikum Oldenburg AöR
   geführt werden."** In dem Moment, in dem die Kliniken eine eigene
   Rechtsform bekommen, fallen sie aus der Reihe. Das Kriterium ist damit
   benannt: Rechtsträgerschaft, nicht Eigentum.
3. **Fußnote 3 sagt es ausdrücklich** — zur Weser-Ems-Halle: „Die Schulden des
   Eigenbetriebs verbleiben rechtlich bei der Stadt. Wirtschaftlich werden die
   Darlehen der WEH GmbH & Co. KG zugerechnet." Die Tabelle folgt der
   rechtlichen Zurechnung, nicht der wirtschaftlichen.

Die Probe aufs Exempel liefert der Jahrgang 2010 (Fußnote 4): Mit der Gründung
des Eigenbetriebs Gebäudewirtschaft und Hochbau wandern 108,9 Mio. € aus dem
städtischen Kreditportfolio in den Eigenbetrieb. In der Tabelle fällt die
Kreditmarkt-Spalte von 130,8 auf 30,5 Mio. und die Eigenbetriebs-Spalte
steigt von 18,6 auf 123,5 Mio. — **die Summe bleibt fast unverändert**
(149,5 → 154,0 Mio.). Eine Umbuchung innerhalb desselben Rechtsträgers, kein
Schuldenabbau. Wer nur die erste Spalte zeigte, verkündete für 2010 einen
Rückgang um drei Viertel, den es nie gab.

Deshalb trägt jede Zahl dieser Schicht ihre Abgrenzung mit
(:data:`ABGRENZUNG`), und deshalb speichern wir die Spalten einzeln und nicht
nur die Summe: Der Sprung von 2010 ist keine Fußnote, er ist die Geschichte.

Die zwei Proben
---------------
:func:`summenprobe` ist die interne: Die vier Schuldenarten müssen die Summe
ergeben, die die Tabelle daneben ausweist. Sie greift in 30 von 31 Jahrgängen.

:func:`prokopfprobe` ist die unabhängige und damit die stärkere: Die
ausgewiesene Gesamtschuld, geteilt durch die Einwohnerzahl aus **Datensatz
1102** des Open-Data-Portals, muss den Pro-Kopf-Betrag ergeben, den dieselbe
Zeile nennt. Beide Seiten stammen aus verschiedenen Veröffentlichungen der
Stadt; dass sie sich treffen, kann kein Übertragungsfehler auf unserer Seite
erzeugen. Die Stichtage passen exakt zueinander — 1108 vermerkt im Kopf
„Bevölkerungsstand: 31. Dezember des Vorjahres", 1102 beschriftet seine Spalte
„Einwohner am 31.12. des Vorjahres".

**2022 ist der Fall, für den beide gebaut sind.** Dort ergeben die
Schuldenarten 282.535 T€, ausgewiesen sind 281.457 T€ — 1,078 Mio. €
Unterschied, im Dokument selbst. Die Summenprobe reißt, und ohne eine zweite
Probe wäre der Jahrgang verloren. Die Pro-Kopf-Probe entscheidet ihn:
281.457.000 € / 170.389 Einwohner*innen = 1.651,85 €, und genau 1.652 € nennt
die Tabelle. Die **Summe** ist also belegt, die **Aufteilung** ist es nicht.
Also kommt die Summe herein und die Aufteilung nicht — nicht der ganze
Jahrgang fliegt raus, und geschätzt wird nichts. Welche Spalte danebenliegt,
sagt das Dokument nicht, und wir raten es nicht.

Was der Extrakt anrichtet
-------------------------
Die Fußnotenziffern kleben im Textextrakt an den Beträgen: ``26.5981`` ist
26.598 mit Fußnote 1, nicht 265.981. Ein Parser, der die Punkte einfach
entfernt, liest dort das Zehnfache und meldet nichts. Auflösbar ist das, weil
deutsche Tausendergruppen **genau drei** Ziffern haben — was hinter der letzten
vollständigen Gruppe steht, ist keine Zahl mehr (:func:`_zelle`). Dasselbe gilt
für das ``r`` der revidierten Werte (``251.160r``), das wir als Angabe
behalten: Der Jahrgang 2024 ist im Nachhinein korrigiert worden, und das darf
auf der Seite stehen.

Vier Jahrgänge tragen solche Marken (1999, 2001, 2008, 2010) — und die
Summenprobe schließt in allen vieren. Sie ist damit nicht nur eine Prüfung der
Quelle, sondern auch die des Entzerrers: Hätte er eine Ziffer falsch
abgeschnitten, ginge die Rechnung nicht auf.

Ausdrücklich **nicht** eingelesen
----------------------------------
Der absolute Schuldenstand aus dem **Vorbericht des Haushaltsplans**. Dort
stehen die Werte in einem Diagramm, und im Textextrakt sind die
Achsenbeschriftungen von den Datenwerten nicht zu unterscheiden — es gibt
keine Summenzeile, keine zweite Spalte, nichts, woran sich prüfen ließe, ob
eine gelesene Zahl ein Datenpunkt oder eine Gitterlinie ist. Keine Probe
möglich, also nicht eingelesen. Tabelle 1108 deckt dieselbe Frage ab und
bringt ihre Proben mit.
"""
from __future__ import annotations

import re

#: Woher die Reihe kommt. Die Datei trägt den Jahrgang im Namen („-2025-"), die
#: Stadt legt jedes Jahr eine neue an — der Link wandert also mit. Deshalb liest
#: ``scripts/ingest_schulden.py`` die Übersichtsseite und nimmt den Link, der
#: dort auf 1108 zeigt; diese Konstante ist der Stand vom 16.08.2026 und die
#: Rückfallebene, wenn die Seite sich ändert.
JAHRBUCH_URL = ("https://www.oldenburg.de/startseite/rathaus/politik-verwaltung/"
                "stadtverwaltung/statistik/statistisches-jahrbuch.html")
TABELLE_URL = ("https://www.oldenburg.de/fileadmin/oldenburg/Benutzer/Dateien/"
               "40_Stadtplanungsamt/402_Geo_und_Daten/Statistik/1108-2025-AZ.pdf")

#: Wie die Übersichtsseite den Link zu dieser Tabelle schreibt.
LINK_MUSTER = re.compile(r'href="([^"]*/1108[^"]*\.pdf)"', re.IGNORECASE)

#: Was diese Zahlen zählen — in einem Satz, der neben der Zahl stehen kann.
#: Nicht optional: Ohne ihn ist „337 Mio. €" eine von zwei Zahlen, die beide so
#: heißen (s. Modulkopf).
ABGRENZUNG = ("Stadt Oldenburg als Rechtsträger: Kernhaushalt und Eigenbetriebe. "
              "Ohne die rechtlich selbstständigen Beteiligungen wie das Klinikum "
              "(AöR) oder die städtischen Gesellschaften.")

#: Posten 17 der Ergebnisrechnung: „Zinsen und ähnliche Aufwendungen".
#:
#: Was der Schuldenstand im Jahr KOSTET, steht nicht in Tabelle 1108, sondern
#: im Jahresabschluss — und dort als Ist, geprüft gegen die Probe des
#: Dokuments. Die Nummer hier, damit Frontend und Endpunkt nicht zwei
#: verschiedene Posten für dieselbe Aussage nehmen (``finanzberichte.
#: ERGEBNIS_POSTEN`` führt sie im Wortlaut).
#:
#: Ausdrücklich NUR die Zinsen: Die Tilgung steht im Finanzhaushalt. Sie
#: mindert den Schuldenstand, ist aber kein Aufwand — beides in einer Zahl
#: zusammenzuziehen wäre die häufigste Verwechslung im ganzen Thema, und die
#: Summe stünde in keinem Dokument.
POSTEN_ZINSAUFWAND = 17

#: Die Spalten der Tabelle, in ihrer Reihenfolge — Feldname und Überschrift.
#: Die ersten vier sind die Schuldenarten, die fünfte ihre Summe, die sechste
#: der Pro-Kopf-Betrag.
SPALTEN: tuple[tuple[str, str], ...] = (
    ("credit_market", "Schulden aus Kreditmarktmitteln"),
    ("special_funds", "Schulden aus öffentlichen Sondermitteln"),
    ("public_authorities", "Schulden bei Gebietskörperschaften"),
    ("municipal_enterprises", "Schulden der Eigenbetriebe einschließlich Kliniken "
                      "und innere Darlehen"),
    ("total", "Schulden insgesamt"),
    ("per_capita", "Schulden je Einwohner*in"),
)

#: Die vier Schuldenarten, die sich zur Summe addieren müssen.
ARTEN: tuple[str, ...] = tuple(f for f, _ in SPALTEN[:4])

#: Erkennt das Dokument. Titel und Nummer stehen in der zweiten Zeile.
_TITEL = re.compile(r"1108\s+Stand der Verschuldung der Stadt Oldenburg\s+"
                    r"((?:19|20)\d\d)\s+bis\s+((?:19|20)\d\d)")

#: Eine Datenzeile beginnt mit der Jahreszahl in der ersten Spalte.
_ZEILE = re.compile(r"^((?:19|20)\d\d)\s+(\S.*)$")

#: Ein Tabellenfeld: deutsche Tausendergruppen, dahinter höchstens eine
#: Fußnotenziffer oder das ``r`` für „revidiert". Die Gruppen sind der Trick —
#: ``\.\d{3}`` lässt eine fünfte Ziffer gar nicht erst zur Zahl gehören.
_ZELLE = re.compile(r"^(\d{1,3}(?:\.\d{3})*)([1-9]|r)?$")

#: Die Schuldenspalten stehen in Tausend Euro, der Pro-Kopf-Betrag in Euro.
TAUSEND = 1000


def _zelle(field: str) -> tuple[float | None, str]:
    """Ein Tabellenfeld → (Zahl, Marke). ``(None, "")``, wenn es keine ist.

    Ohne Tausenderpunkt gilt das Feld ungeteilt: ``891`` sind 891 und nicht
    89 mit Fußnote 1. Die Tabelle setzt bei jedem vierstelligen Wert einen
    Punkt, eine Fußnote an einem punktlosen Feld gäbe es also nur, wenn sich
    das Format änderte — und dann soll die Zahl lieber unverändert durch die
    Summenprobe fallen, als still um eine Stelle zu schrumpfen."""
    field = field.strip()
    if "." not in field:
        return (float(field), "") if field.isdigit() else (None, "")
    m = _ZELLE.match(field)
    if not m:
        return (None, "")
    return float(m.group(1).replace(".", "")), m.group(2) or ""


def erkenne(text: str) -> tuple[int, int] | None:
    """Ist das Tabelle 1108 — und welche Spanne deckt sie ab?

    Die Spanne kommt aus dem Titel und nicht aus den gelesenen Zeilen: Sie ist
    damit eine Angabe des Dokuments, gegen die sich prüfen lässt, ob der Parser
    alle Jahrgänge erwischt hat (:func:`lies` tut genau das)."""
    m = _TITEL.search(re.sub(r"[ \t]+", " ", text or ""))
    return (int(m.group(1)), int(m.group(2))) if m else None


def parse(text: str) -> list[dict]:
    """Die Datenzeilen der Tabelle → je Jahrgang ein dict in **Euro**.

    Die Quelle rechnet in Tausend Euro; gespeichert wird wie überall im Bereich
    in Euro. Die dabei behauptete Genauigkeit ist die der Quelle — auf Tausend
    gerundet, und das bleibt sie auch nach der Multiplikation.

    Zeilen, deren Felderzahl nicht stimmt, fallen weg statt zurechtgebogen zu
    werden; welche das waren, sagt :func:`lies`."""
    zeilen: list[dict] = []
    for roh in (text or "").splitlines():
        m = _ZEILE.match(roh.strip())
        if not m:
            continue
        felder = [_zelle(f) for f in m.group(2).split()]
        if len(felder) != len(SPALTEN) or any(w is None for w, _ in felder):
            zeilen.append({"year": int(m.group(1)), "unlesbar": roh.strip()})
            continue
        row: dict = {"year": int(m.group(1)), "unlesbar": None}
        for (field, _), (value, mark) in zip(SPALTEN, felder):
            # Der Pro-Kopf-Betrag steht schon in Euro, die Schuldenarten nicht.
            row[field] = value if field == "per_capita" else value * TAUSEND
            if mark == "r":
                row["revised"] = True
        row.setdefault("revised", False)
        zeilen.append(row)
    return zeilen


def summenprobe(row: dict) -> tuple[bool, float]:
    """Ergeben die vier Schuldenarten die ausgewiesene Summe?

    Rückgabe ``(bestanden, Abweichung in Euro)``. Ohne Toleranz: Die Quelle
    rundet jede Spalte auf volle Tausend und ist in 30 von 31 Jahrgängen auf
    den Euro stimmig — eine Toleranz würde hier nur den einen Jahrgang
    durchwinken, für den sie gedacht wäre."""
    summe = sum(row.get(a) or 0.0 for a in ARTEN)
    deviation = summe - (row.get("total") or 0.0)
    return deviation == 0.0, deviation


def prokopfprobe(row: dict, population: int | None) -> tuple[bool | None, float | None]:
    """Gesamtschuld ÷ Einwohnerzahl = der ausgewiesene Pro-Kopf-Betrag?

    Die unabhängige Probe: Der Divisor kommt aus Datensatz 1102 des
    Open-Data-Portals (``council_einwohner``), also aus einer anderen
    Veröffentlichung als die Tabelle. Die Stichtage decken sich (beide
    „31.12. des Vorjahres", s. Modulkopf).

    ``(None, None)``, wenn für den Jahrgang keine Einwohnerzahl vorliegt — das
    ist vor 2010 der Normalfall und kein Mangel dieser Zeile. Toleranz ist eine
    ganze Einheit: Die Quelle rundet den Pro-Kopf-Betrag auf volle Euro, und
    schon deshalb ist der letzte Euro nicht zu halten."""
    ausgewiesen = row.get("per_capita")
    if not population or ausgewiesen is None or row.get("total") is None:
        return None, None
    gerechnet = row["total"] / population
    return abs(gerechnet - ausgewiesen) <= 1.0, gerechnet


def lies(text: str, population: dict[int, int] | None = None) -> dict:
    """Die Tabelle einlesen und jeden Jahrgang durch beide Proben schicken.

    Rückgabe:

    ``zeilen``
        Die übernommenen Jahrgänge. Wo die Summenprobe reißt, stehen die vier
        Schuldenarten auf ``None`` — die Summe bleibt, die Aufteilung geht
        (s. Modulkopf, Fall 2022).
    ``verworfen``
        Jahrgänge, die **gar keine** Probe bestanden haben, mit Grund. Sie
        stehen nirgends in der Datenbank.
    ``probes``
        Was gerechnet wurde, in Zahlen — Grundlage des Beleg-Texts.
    """
    population = population or {}
    spanne = erkenne(text)
    roh = parse(text)

    zeilen: list[dict] = []
    verworfen: list[dict] = []
    summe_ok = summe_gerissen = kopf_ok = kopf_gerissen = 0
    ohne_einwohner = 0
    for row in roh:
        if row.get("unlesbar"):
            verworfen.append({"year": row["year"],
                              "reason": f"Zeile nicht in {len(SPALTEN)} Felder "
                                       f"zerlegbar: {row['unlesbar']!r}"})
            continue
        s_ok, deviation = summenprobe(row)
        k_ok, gerechnet = prokopfprobe(row, population.get(row["year"]))
        summe_ok += bool(s_ok)
        summe_gerissen += not s_ok
        if k_ok is None:
            ohne_einwohner += 1
        else:
            kopf_ok += bool(k_ok)
            kopf_gerissen += not k_ok

        bestanden = [n for n, ok in (("schulden_summenzeile", s_ok),
                                     ("schulden_prokopf", k_ok)) if ok]
        if not bestanden:
            reason = (f"Summenprobe um {deviation:+,.0f} € gerissen"
                     if not s_ok else "Summenprobe gerissen")
            if k_ok is False:
                reason += (f"; Pro-Kopf-Probe ebenfalls "
                          f"({gerechnet:,.2f} € gerechnet gegen "
                          f"{row['per_capita']:,.0f} € ausgewiesen)")
            else:
                reason += "; keine Einwohnerzahl für die Gegenprobe"
            verworfen.append({"year": row["year"], "reason": reason})
            continue

        uebernommen = dict(row)
        uebernommen.pop("unlesbar", None)
        if not s_ok:
            # Die Summe trägt die Pro-Kopf-Probe, die Aufteilung trägt nichts.
            for art in ARTEN:
                uebernommen[art] = None
            uebernommen["breakdown_rejected"] = round(deviation)
        else:
            uebernommen["breakdown_rejected"] = None
        uebernommen["probes"] = bestanden
        zeilen.append(uebernommen)

    years = sorted(z["year"] for z in zeilen)
    luecken = ([j for j in range(spanne[0], spanne[1] + 1) if j not in years]
               if spanne else [])
    return {
        "zeilen": zeilen,
        "verworfen": verworfen,
        "spanne": spanne,
        # Der Titel nennt seine Spanne selbst — was daraus fehlt, ist ein
        # Befund und keine Geschmacksfrage.
        "fehlende_jahrgaenge": luecken,
        "probes": {
            "summe_bestanden": summe_ok, "summe_gerissen": summe_gerissen,
            "prokopf_bestanden": kopf_ok, "prokopf_gerissen": kopf_gerissen,
            "prokopf_ohne_einwohnerzahl": ohne_einwohner,
        },
    }


def probennachweis(result: dict) -> str:
    """Der Messwert für die Herkunft — „was ist wirklich gelaufen?".

    Steht später im Beleg auf der Seite; deshalb Zahlen und keine Adjektive."""
    p = result["probes"]
    teile = [f"Summenprobe {p['summe_bestanden']} von "
             f"{p['summe_bestanden'] + p['summe_gerissen']} Jahrgängen"]
    geprueft = p["prokopf_bestanden"] + p["prokopf_gerissen"]
    if geprueft:
        teile.append(f"Pro-Kopf-Gegenprobe gegen die Einwohnerzahlen "
                     f"{p['prokopf_bestanden']} von {geprueft}")
    return "; ".join(teile)
