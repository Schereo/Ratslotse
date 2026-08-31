"""Jahresabschlüsse und Teilhaushalte aus dem Ratsinformationssystem lesen.

Beide Dokumenttypen liegen längst als Anlagen zu Ratsvorlagen in
``council_anlagen`` — mit Volltext, den der Protokoll-Scraper ohnehin zieht.
Kein neuer Download, keine neue Quelle:

- **Jahresabschluss** (300+ Seiten, jährlich): enthält die Ergebnisrechnung
  der Kernverwaltung mit **Ansatz UND Ergebnis nebeneinander** — die Grundlage
  für „geplant gegen tatsächlich", und zugleich die Aufschlüsselung der
  Erträge nach Arten (Steuern, Zuwendungen, Entgelte, Kostenerstattungen).
- **Teilhaushalts-Pläne** (THH01–13, je bis 234 Seiten): enthalten die
  **Produktebene** — was einzelne Aufgaben kosten („Archivierung",
  „Kindertagesbetreuung"), mit Produktnummer und zuständigem Amt.

Beide Parser sind bewusst misstrauisch: Aus PDF-Text extrahierte Tabellen
verschmelzen gerne Zahlen („355.188334.704" statt zweier Werte). Deshalb
werden nur Zeilen übernommen, die eine im Dokument selbst dokumentierte
Rechenbeziehung erfüllen:

- Jahresabschluss: Abweichung = Ergebnis − Plan (Fußnote der Tabelle)
- Teilhaushalt: Erträge − Aufwendungen = ordentliches Ergebnis

Was diese Probe nicht besteht, fällt raus. Lieber eine Lücke als eine Zahl,
die niemand nachrechnen kann.

**„Plan" heißt nicht in jedem Jahrgang dasselbe.** Die Ergebnisrechnung
vergleicht das Ist mit dem Wert, den das Dokument selbst als Bezug führt —
und der wechselt: 2018 ist es die Gesamtermächtigung, 2020 der Ansatz
einschließlich Nachtragshaushalt, sonst der nackte Ansatz. Bei 2020 sind das
27 Mio. € Unterschied, also der Unterschied zwischen „21,5 Mio. weniger
ausgegeben als geplant" und „5,7 Mio. mehr". Deshalb speichert der Parser
beides — ``ansatz`` (der ursprüngliche Haushaltsansatz) und ``plan`` (die
Bezugsgröße der Abweichung) — und dazu in ``plan_art``, welche der beiden
gemeint ist. Eine Kurve, die 2018 die Gesamtermächtigung und 2021 den nackten
Ansatz gegen das Ist stellt, ohne das zu sagen, wäre still falsch.

Welche Spalte wo steht, kommt aus dem **Tabellenkopf**, nicht aus einer
Reihenfolgeannahme: 2017 steht das Ergebnis vor dem Ansatz, 2018 hat elf
Spalten mit sechs möglichen Leerfeldern, 2019–2024 tragen eine (meist leere)
Nachtragsspalte. Erlaubt ist als Bezugsgröße nur, was der Kopf auch nennt.
"""
from __future__ import annotations

import re

# --- Jahresabschluss: Ergebnisrechnung der Kernverwaltung --------------------

#: Die Posten der Ergebnisrechnung, wie sie in der Tabelle nummeriert sind.
#: Nur diese Nummern werden gelesen; Zwischenüberschriften fallen weg.
ERGEBNIS_POSTEN = {
    1: "Steuern und ähnliche Abgaben",
    2: "Zuwendungen und allgemeine Umlagen",
    3: "Auflösungserträge aus Sonderposten",
    4: "sonstige Transfererträge",
    5: "öffentlich-rechtliche Entgelte",
    6: "privatrechtliche Entgelte",
    7: "Kostenerstattungen und Kostenumlagen",
    8: "Zinsen und ähnliche Finanzerträge",
    9: "aktivierungsfähige Eigenleistungen",
    10: "Bestandsveränderungen",
    11: "sonstige ordentliche Erträge",
    12: "Summe ordentliche Erträge",
    13: "Personalaufwendungen",
    14: "Versorgungsaufwendungen",
    15: "Aufwendungen für Sach- und Dienstleistungen",
    16: "Abschreibungen",
    17: "Zinsen und ähnliche Aufwendungen",
    18: "Transferaufwendungen",
    19: "sonstige ordentliche Aufwendungen",
    20: "Summe ordentliche Aufwendungen",
    21: "ordentliches Ergebnis",
    22: "außerordentliche Erträge",
    23: "außerordentliche Aufwendungen",
    24: "außerordentliches Ergebnis",
}

#: Posten 12/20/21/24 sind Summen bzw. Salden, keine eigenständigen Arten.
SUMMEN_POSTEN = {12, 20, 21, 24}

_BETRAG = re.compile(r"-?\d{1,3}(?:\.\d{3})*,\d{2}")

#: Rundungstoleranz der Rechenproben in Euro.
_TOLERANZ = 1.0
#: Für die Vorzeichen-Reparatur reicht Rundung nicht: Dort muss der Betrag
#: auf den Cent stimmen, sonst ist es kein fehlendes Minus, sondern ein
#: falsch gelesener Wert.
_TOLERANZ_VORZEICHEN = 0.01

#: Bezugsgrößen der Abweichung, menschenlesbar — für die Oberfläche.
#: Ohne diese Angabe ist eine Mehrjahres-Kurve nicht ehrlich lesbar.
PLAN_ARTEN = {
    "ansatz": "Haushaltsansatz",
    "ansatz_nachtrag": "Ansatz einschließlich Nachtragshaushalt",
    "gesamtermaechtigung": "Gesamtermächtigung (Ansatz, Nachtrag, Übertragungen)",
}


def _eur(s: str) -> float:
    return float(s.replace(".", "").replace(",", "."))


def _kopf_normalisieren(kopf: str) -> str:
    """Tabellenkopf für die Spaltensuche glätten.

    Im PDF-Text sind die Kopfzellen umbrochen und getrennt („Ansätze des
    Haushalts-\\njahres 2018", „Gesamt-\\nermäch-\\ntigungen"). Erst ohne
    Trennstriche und mit einfachem Leerraum sind die Spaltennamen als
    zusammenhängende Wörter suchbar."""
    return " ".join(re.sub(r"-\s*\n\s*", "", kopf).split())


def _tabellenkopf(kopf: str, year: int) -> dict | None:
    """Aus dem Tabellenkopf lesen, welche Spalten es gibt und in welcher
    Reihenfolge — die Grundlage für alles Weitere.

    Liefert ``{positionen, varianten, has_prior_year}``. ``varianten`` sind die
    als Bezugsgröße der Abweichung zugelassenen Spalten, von der
    spezifischsten zur allgemeinsten; genannt wird nur, was im Kopf steht.
    ``None``, wenn der Kopf nicht genug hergibt — dann wird nichts geraten."""
    k = _kopf_normalisieren(kopf)
    positionen: dict[str, int] = {}

    def finde(name: str, *muster: str) -> None:
        for mu in muster:
            m = re.search(mu, k)
            if m:
                positionen[name] = m.start()
                return

    # Achtung: „Ermächtigungen des Haushaltsjahres" darf nicht als Ergebnis
    # durchgehen — deshalb steht „Ergebnis" in den Mustern immer mit dabei.
    finde("prior_year", r"Ergebnis des Vorjahres", rf"Ergebnis {year - 1}")
    finde("ansatz", r"Ansätze des Haushaltsjahres", r"Ansätze des Haushaltsplanes",
          rf"Ansätze? {year}", r"Ansätze des", r"\bAnsatz\b")
    finde("supplement", r"Veränderung durch\s*Nachtrag", r"\bNachtrag\b")
    finde("gesamtermaechtigung", r"Gesamtermächtigung")
    finde("result", r"Ergebnis des Haushaltsjahres", rf"Ergebnis {year}")
    # Der Zwischenraum vor der Klammer ist nicht verlässlich: Die
    # Finanzrechnung 2017 schreibt „mehr(+), weniger(-)" ohne Leerzeichen, und
    # ohne das ``\s*`` fand der Kopf dort gar keine Abweichungsspalte — der
    # ganze Jahrgang fiel durch. Die Stelle ist nur ein Vorhandenseins-Test
    # (die Reihenfolge kommt aus Ansatz und Ergebnis), Aufweiten also gefahrlos.
    finde("deviation", r"mehr\s*\(\+\)", r"Differenz", r"Abweichung", r"Vergleich")

    if "result" not in positionen or "deviation" not in positionen:
        return None

    varianten: list[str] = []
    # Die Gesamtermächtigung ist der spezifischste Bezug: Wo der Kopf sie
    # führt (2018), ist sie die Spalte direkt vor dem Ergebnis.
    if "gesamtermaechtigung" in positionen:
        varianten.append("gesamtermaechtigung")
    if "ansatz" in positionen and "supplement" in positionen:
        varianten.append("ansatz_nachtrag")
    if "ansatz" in positionen:
        varianten.append("ansatz")
    if not varianten:
        return None
    return {"positionen": positionen, "varianten": tuple(varianten),
            "has_prior_year": "prior_year" in positionen}


def _plan_zuerst(kopf: dict, art: str) -> bool:
    """Steht die Plan-Spalte im Kopf vor der Ergebnis-Spalte? 2017 nicht —
    dort lautet die Reihenfolge Vorjahr, Ergebnis, Ansatz, Differenz."""
    spalte = "gesamtermaechtigung" if art == "gesamtermaechtigung" else "ansatz"
    return kopf["positionen"][spalte] < kopf["positionen"]["result"]


def parse_ergebnisrechnung(text: str, year: int) -> list[dict]:
    """Ergebnisrechnung der Kernverwaltung aus dem Jahresabschluss-Volltext.

    Liefert je Posten ``{nr, label, prior_year, ansatz, result,
    deviation}`` in Euro. ``ansatz`` ist der Planwert des Jahres,
    ``result`` das tatsächliche Ergebnis — genau das Paar, aus dem
    „geplant gegen tatsächlich" wird.

    Die Tabelle hat sieben Spalten, von denen zwei (Nachtrag, Ermächtigung)
    meist leer bleiben. Welche Zahl zu welcher Spalte gehört, lässt sich aus
    der Reihenfolge allein nicht sicher sagen — deshalb prüft der Parser die
    in der Tabellen-Fußnote dokumentierte Beziehung
    ``Abweichung = Ergebnis − Ansatz`` und übernimmt nur, was passt.
    """
    # Auf den Abschnitt der Kernverwaltung beschränken: Danach folgt die
    # Gesamtergebnisrechnung (inkl. Stiftungen), die andere Werte trägt.
    # „3.1 Ergebnisrechnung [der] Kernverwaltung" — ältere Jahrgänge schreiben
    # das „der" mit. Der erste Treffer ist das Inhaltsverzeichnis, deshalb die
    # Fundstelle mit den meisten Beträgen dahinter nehmen.
    stellen = [m.start() for m in re.finditer(
        r"Ergebnisrechnung\s+(?:der\s+)?Kernverwaltung", text)]
    if not stellen:
        return []
    start = max(stellen, key=lambda i: len(_BETRAG.findall(text[i:i + 6000])))
    # Bis zur Gesamtergebnisrechnung lesen, aber mindestens so weit, dass die
    # Aufwendungen (Posten 13–24 auf der Folgeseite) noch drin sind.
    ende = text.find("Gesamtergebnisrechnung", start + 6000)
    block = text[start:ende if ende > 0 else start + 12000]

    return _posten_aus_block(block, year)


def _posten_aus_block(block: str, year: int) -> list[dict]:
    """Die Posten einer Ergebnisrechnungs-Tabelle lesen — gemeinsam genutzt
    von der Gesamtrechnung und den Teil-Ergebnisrechnungen je Teilhaushalt,
    die dieselbe Tabellenform haben.

    Jeder Abschnitt trägt seinen eigenen Kopf; er steht vor der ersten
    Zwischenüberschrift („Ordentliche Erträge")."""
    schnitt = re.search(r"[Oo]rdentliche Erträge", block)
    kopf = _tabellenkopf(block[:schnitt.start()] if schnitt else block[:900], year)
    if kopf is None:
        return []

    # Zeilenumbrüche in Bezeichnungen zusammenziehen: Der Postenname kann über
    # zwei Zeilen laufen („07. Kostenerstattungen und\nKostenumlagen 119.0…").
    flach = re.sub(r"\s*\n\s*", " ", block)

    # An den Posten-Nummern aufteilen: „01. …“, „02. …“ — robuster als ein
    # Lookahead, weil zwischen zwei Posten beliebig viel Seitenkopf stehen darf.
    # 2017 schreibt die Summenzeilen als „12.= Summe …“ ohne Leerzeichen.
    teile = re.split(r"(?<![\d,.])(\d\d)\.(?:\s*=)?\s", flach)
    inhalt: dict[int, str] = {}
    for i in range(1, len(teile) - 1, 2):
        nr = int(teile[i])
        # Erster Treffer gewinnt: Wiederholungen sind Seitenköpfe.
        inhalt.setdefault(nr, teile[i + 1])

    out: list[dict] = []
    for nr, label in ERGEBNIS_POSTEN.items():
        roh = inhalt.get(nr)
        if not roh:
            continue
        # Nur bis zum Ende der Zahlenkolonne dieser Zeile lesen. 2018 hat elf
        # Spalten, deshalb etwas mehr Luft als die früher genügenden 200.
        # Hinter Posten 24 steht die Zeile „Jahresergebnis" ohne Nummer; ohne
        # diesen Schnitt gehörten ihre Zahlen noch zu Posten 24.
        zeile = re.split(r"Jahresergebnis", roh[:240])[0]
        zahlen = [_eur(z) for z in _BETRAG.findall(zeile)]
        werte = _spalten_zuordnen(zahlen, kopf)
        if werte is None:
            continue
        out.append({"nr": nr, "label": label, "year": year,
                    "is_total": 1 if nr in SUMMEN_POSTEN else 0, **werte})
    return out


#: Kopf einer Teil-Ergebnisrechnung: „A. Teil-Ergebnisrechnung THH01 Name".
#: Die Schreibweise schwankt zwischen den Jahrgängen, und im Jahresabschluss
#: 2022 fällt bei THH09 sogar ein Zeilenumbruch mitten hinein („A. Teil\n
#: -Ergebnisrechnung THH09"). Ohne den Umbruch im Muster fand der Parser dort
#: nur die Fortsetzungsseite ab Posten 21, zählte den Teilhaushalt nicht mit
#: und verwarf die ganze Ebene über die Summenprobe (4,1 % Abweichung).
#: Deshalb rund um den Bindestrich beliebiger Leerraum.
_THH_ABSCHNITT = re.compile(r"Teil\s*-?\s*Ergebnisrechnung\s+THH\s?(\d\d)\s*([^\n]{0,60})")


def parse_teilergebnisrechnungen(text: str, year: int) -> list[dict]:
    """Teil-Ergebnisrechnungen je Teilhaushalt aus dem Jahresabschluss.

    Liefert dieselben Posten wie ``parse_ergebnisrechnung``, zusätzlich mit
    ``sub_budget_no`` und ``sub_budget_name`` — die Grundlage für „geplant gegen
    tatsächlich" je Bereich (Design H-16).

    Je Teilhaushalt stehen im Dokument mehrere Abschnitte (Ergebnis-, dann
    Finanzrechnung, dazu Fortsetzungsseiten). Genommen wird der erste, der
    beide Summenzeilen (12 und 20) liefert — so landet nie die Finanzrechnung
    in der Ergebnis-Tabelle."""
    treffer: dict[int, dict] = {}
    stellen = list(_THH_ABSCHNITT.finditer(text))
    for i, m in enumerate(stellen):
        sub_budget_no = int(m.group(1))
        if sub_budget_no in treffer:
            continue
        # Bis zum nächsten Abschnitt lesen, damit keine Werte des folgenden
        # Teilhaushalts hineinrutschen.
        ende = stellen[i + 1].start() if i + 1 < len(stellen) else m.end() + 9000
        posten = _posten_aus_block(text[m.end():ende], year)
        nummern = {p["nr"] for p in posten}
        if not {12, 20} <= nummern:
            continue  # kein vollständiger Ergebnis-Abschnitt
        name = re.sub(r"^\s*(THH\s?\d\d)?\s*", "", m.group(2)).strip(" -–—:")
        treffer[sub_budget_no] = {"sub_budget_no": sub_budget_no, "sub_budget_name": name, "posten": posten}
    return list(treffer.values())


def summenprobe(teilhaushalte: list[dict], gesamt: list[dict],
                toleranz: float = 0.01) -> tuple[bool, float]:
    """Zweite Absicherung: Die Summe der Teilhaushalte muss der
    Gesamt-Ergebnisrechnung entsprechen — für den **Plan und das Ist**.

    Nötig, weil die zeilenweise Prüfung (``Abweichung = Ergebnis − Plan``)
    einen Fall nicht fängt: Wird für einen Teilhaushalt versehentlich eine
    andere, in sich stimmige Tabelle gelesen, sind die Zahlen konsistent —
    aber falsch. Im Jahresabschluss 2022 wurde THH09 so mit 0,1 statt
    26,8 Mio. € gelesen; erst die Summe über alle Teilhaushalte machte es
    sichtbar (26,7 Mio. Differenz).

    Nur den Plan zu prüfen genügte nicht: Ein Fehlgriff, der zufällig
    denselben Ansatz trägt, käme durch. Geprüft werden deshalb beide
    Summenzeilen (Erträge 12, Aufwendungen 20) in beiden Größen.

    Gibt ``(besteht, groesste_abweichung)`` zurück."""
    schlimmste = 0.0
    for nr in (12, 20):
        for field in ("plan", "result"):
            ganz = next((p.get(field) for p in gesamt if p["nr"] == nr), None)
            if not ganz:
                return False, 1.0
            part = sum(next((p.get(field) for p in x["posten"] if p["nr"] == nr), 0) or 0
                       for x in teilhaushalte)
            schlimmste = max(schlimmste, abs(part - ganz) / abs(ganz))
    return schlimmste <= toleranz, schlimmste


def strukturprobe(posten: list[dict], toleranz: float = _TOLERANZ) -> tuple[bool, str]:
    """Dritte Absicherung, innerhalb einer Tabelle: ``12 − 20 = 21``.

    Die Summe der ordentlichen Erträge minus die der ordentlichen
    Aufwendungen ist das ordentliche Ergebnis — in Plan und Ist. Die Probe
    hängt an keiner anderen Quelle und fällt sofort auf, wenn eine der drei
    Zeilen aus einer falschen Tabelle stammt.

    (``22 − 23 = 24`` ist als Probe unbrauchbar: Direkt darunter steht die
    Zeile „Jahresergebnis" ohne Nummer und rutscht in die Zahlenkolonne.)"""
    nach_nr = {p["nr"]: p for p in posten}
    if not {12, 20, 21} <= set(nach_nr):
        return False, "Posten 12, 20 oder 21 fehlt"
    for field in ("plan", "result"):
        werte = [nach_nr[n].get(field) for n in (12, 20, 21)]
        if any(w is None for w in werte):
            return False, f"{field}: Wert fehlt"
        rest = (werte[0] - werte[1]) - werte[2]
        if abs(rest) > toleranz:
            return False, f"{field}: 12 − 20 − 21 = {rest:+.2f} €"
    return True, ""


def vorjahreskette(je_jahr: dict[int, list[dict]],
                   toleranz: float = _TOLERANZ) -> list[tuple[int, int, str]]:
    """Vierte Absicherung, über Dokumentgrenzen hinweg: Das Ist eines Jahres
    taucht im Folgejahrgang als Vorjahresspalte wieder auf.

    Geprüft werden die Summenzeilen 12 und 20 jedes benachbarten Paares.
    Zurück kommt die Liste der **gerissenen** Glieder als
    ``(year, folgejahr, begruendung)`` — leer heißt: alles schließt.

    Weil ein gerissenes Glied nicht verrät, welche der beiden Seiten falsch
    gelesen wurde, verliert der Aufrufer beide. Das ist die konservative
    Lesart und entspricht dem Grundsatz dieses Moduls: lieber eine Lücke als
    eine Zahl, die niemand nachrechnen kann."""
    kaputt: list[tuple[int, int, str]] = []
    for year in sorted(je_jahr):
        folge = year + 1
        if folge not in je_jahr:
            continue
        vorher = {p["nr"]: p for p in je_jahr[year]}
        nachher = {p["nr"]: p for p in je_jahr[folge]}
        for nr in (12, 20):
            ist = vorher.get(nr, {}).get("result")
            genannt = nachher.get(nr, {}).get("prior_year")
            if ist is None or genannt is None:
                kaputt.append((year, folge, f"Posten {nr}: Wert fehlt"))
            elif abs(ist - genannt) > toleranz:
                kaputt.append((year, folge,
                               f"Posten {nr}: Ist {ist:,.2f} ≠ Vorjahresspalte "
                               f"{genannt:,.2f}"))
    return kaputt


def _fenster(zahlen: list[float], kopf: dict, art: str) -> tuple | None:
    """Das Fenster in der Zahlenfolge suchen, das die Rechenprobe der
    jeweiligen Bezugsgröße erfüllt.

    Zurück kommt ``(plan, result, deviation, start_index, repariert)``.

    Genommen wird das **letzte** passende Fenster, also von rechts gelesen.
    Das ist die Anordnung, die der Kopf vorgibt: Ganz rechts steht die
    Abweichung, davor das Ergebnis, davor die Bezugsgröße. In der breiten
    2018er-Tabelle stehen zwischen Ansatz und Gesamtermächtigung bis zu vier
    Ermächtigungsspalten, von denen einzelne leer bleiben — von links
    gelesen träfe man dort die falsche Spaltenfolge.

    Zwei Schutzregeln halten das eng:

    * Fängt der Kopf mit einer Vorjahresspalte an, darf das Fenster nicht bei
      Index 0 beginnen — die erste Zahl der Zeile ist dann immer das Vorjahr.
    * Ein exakter Treffer schlägt immer eine Vorzeichen-Reparatur."""
    mindest = 1 if kopf["has_prior_year"] else 0
    plan_zuerst = _plan_zuerst(kopf, art)
    breite = 4 if art == "ansatz_nachtrag" else 3
    if art == "ansatz_nachtrag" and not plan_zuerst:
        return None  # Nachtragsspalte gibt es nur in der Ansatz-zuerst-Form
    exakt = repariert = None
    for i in range(mindest, len(zahlen) - breite + 1):
        if art == "ansatz_nachtrag":
            ansatz, supplement, result, deviation = zahlen[i:i + 4]
            if supplement == 0:
                continue  # leere Nachtragsspalte → das ist der einfache Fall
            plan = ansatz + supplement
        else:
            a, b, deviation = zahlen[i:i + 3]
            plan, result = (a, b) if plan_zuerst else (b, a)
        if abs((result - plan) - deviation) <= _TOLERANZ:
            exakt = (plan, result, deviation, i, False)
        elif (abs((result - plan) + deviation) <= _TOLERANZ_VORZEICHEN
                and deviation and result and plan):
            # Im Dokument fehlt das Minuszeichen (gesehen 2020, Summenzeile 20
            # des Schlussberichts). Nur reparieren, wenn der Betrag auf den
            # Cent passt — und nur bei einem echten Tripel: Ohne die
            # Null-Bedingung erfüllt jedes „X | 0,00 | X" diese Probe, was im
            # Jahresabschluss 2018 einen ganzen Teilhaushalt mit einem Ist von
            # 0,00 € eingetragen hätte (THH11, richtig sind 105,0 Mio. €).
            repariert = (plan, result, result - plan, i, True)
    return exakt or repariert


def _spalten_zuordnen(zahlen: list[float], kopf: dict) -> dict | None:
    """Zahlenfolge einer Tabellenzeile den Spalten zuordnen — kopfgesteuert
    und validiert.

    Übernommen wird nur, was ``Abweichung ≈ Ergebnis − Plan`` erfüllt, wobei
    als Plan nur zugelassen ist, was der Tabellenkopf auch als Spalte nennt
    (Ansatz, Ansatz + Nachtrag oder Gesamtermächtigung). Geliefert werden
    beide Größen: ``ansatz`` der ursprüngliche Haushaltsansatz, ``plan`` die
    Bezugsgröße der Abweichung, ``plan_art`` welche davon."""
    if len(zahlen) < 4:
        return None
    for art in kopf["varianten"]:
        gefunden = _fenster(zahlen, kopf, art)
        if not gefunden:
            continue
        plan, result, deviation, start, repariert = gefunden
        prior_year = zahlen[0] if kopf["has_prior_year"] else None
        if art == "ansatz_nachtrag":
            ansatz = zahlen[start]          # Nachtrag steht direkt dahinter
        elif art == "gesamtermaechtigung" and kopf["has_prior_year"] and start >= 2:
            # Der Kopf führt als zweite Spalte den Ansatz; die Zwischenspalten
            # (Nachtrag, sonstige Ermächtigungen, Übertragungen) dürfen leer
            # sein, die beiden ersten sind es nie.
            ansatz = zahlen[1]
        else:
            ansatz = plan
        return {"prior_year": prior_year, "ansatz": ansatz, "plan": plan,
                "plan_art": art, "result": result, "deviation": deviation,
                "vorzeichen_repariert": repariert,
                # Wo das gefundene Fenster in der Zahlenfolge anfängt. Die
                # Ergebnisrechnung braucht das nicht; die Finanzrechnung liest
                # daran die Spalte ab, die HINTER der Abweichung steht (die
                # Ermächtigungen aus Vorjahren, s. `parse_finanzrechnung`).
                "_fenster_start": start}
    return None


# --- Jahresabschluss: Finanzrechnung der Kernverwaltung ---------------------
#
# Derselbe Bericht, dreißig Seiten weiter, und die andere Hälfte der Wahrheit.
# Die Ergebnisrechnung oben bucht: Sie zeigt für 2024 einen Jahresüberschuss
# von 6,1 Mio. €. Die Finanzrechnung zahlt: Im selben Dokument steht, dass die
# Stadt am Jahresende 22,4 Mio. € weniger Geld hatte als am Anfang. Beides
# stimmt — Abschreibungen kosten Buchwert, aber kein Bargeld, und eine
# Investition kostet Bargeld, aber im Buchungsjahr kaum Aufwand.
#
# Die Tabelle hat dieselbe Grammatik wie die Ergebnisrechnung (Vorjahr,
# Ansatz, Ergebnis, Abweichung, geprüft über die Fußnote „Spalte 6 = Spalte 5
# − Summe (Spalte 3 + Spalte 4)"), deshalb liest sie derselbe Spaltenapparat:
# `_tabellenkopf`, `_fenster`, `_spalten_zuordnen`. Vier Dinge sind anders,
# und jedes davon ist beim Bauen aufgelaufen:
#
# 1. **Die Postennummern verschieben sich.** 2017–2020 führt die Tabelle 42
#    Zeilen, 2021–2024 nur 41: Die Zeile „Einzahlungen aus der Veräußerung
#    geringwertiger Vermögensgegenstände" fällt weg, und alles ab Posten 08
#    rutscht um eins. Ein fester Nummern-Katalog wie ``ERGEBNIS_POSTEN``
#    ginge hier also für die Hälfte der Jahrgänge daneben. Deshalb kommt die
#    Bezeichnung aus dem **Dokument** und die Bedeutung aus :data:`ROLLEN` —
#    das Dokument benennt seine Zeilen selbst.
# 2. **Die Zeilen verweisen aufeinander** („18. Saldo aus laufender
#    Verwaltungstätigkeit (Zeile 10 abzüglich Zeile 17)"). Ein Zeilensplit an
#    zweistelligen Zahlen schneidet mitten in diesen Verweis und lässt die
#    Zahlenkolonne dahinter liegen: Posten 18, 33, 36, 37 und 40 kamen so in
#    keinem einzigen Jahrgang an. :data:`_VERWEIS` wirft sie vorher weg.
# 3. **Der Seitenfuß „JA 29" sieht aus wie ein Posten.** Er steht am Ende der
#    ersten Tabellenseite — also VOR dem echten Posten 29 auf der zweiten.
#    Wer ihn stehen lässt, verliert „29. Sonstige Investitionstätigkeit" und
#    damit die Summenprobe der Investitions-Auszahlungen.
# 4. **Es gibt eine Spalte mehr:** die Ermächtigungen aus Haushaltsvorjahren.
#    Sie ist die Antwort auf „warum wird das Geplante nicht gebaut?" — 2024
#    stehen dort 58,8 Mio. € übertragene Baugenehmigungen neben 96,4 Mio. €
#    tatsächlichen Auszahlungen. Sie trägt ihre eigene Summenprobe.
#
# Was diese Datei NICHT tut: aus Jahresüberschuss und Kassenveränderung eine
# Differenz bilden. Diese Zahl steht in keiner Quelle und hieße nichts.

#: Die Zeilen, auf die es ankommt — erkannt an dem Namen, den das Dokument
#: ihnen selbst gibt. Stabil über beide Nummerierungen hinweg.
#:
#: Zwei Muster sind aufgeweitet, und beide Male sagt die Rechenprobe, dass es
#: dieselbe Zeile ist: Die Summenzeile der Investitions-Einzahlungen heißt mal
#: „aus", mal „für" Investitionstätigkeit, und 2017 heißt die Finanzmittel-
#: veränderung „Finanzmittelbestand" — rechnet aber wie überall sonst
#: Finanzmittelsaldo + Saldo der Finanzierungstätigkeit.
ROLLEN: tuple[tuple[str, str], ...] = (
    ("total_in_operating", r"Summe der Einzahlungen aus laufender Verwaltungst"),
    ("total_out_operating", r"Summe der Auszahlungen aus laufender Verwaltungst"),
    ("balance_operating", r"^Saldo aus laufender Verwaltungst"),
    ("total_in_capital", r"Summe der Einzahlungen (?:aus|f[üu]r) Investitionst"),
    ("total_out_capital", r"Summe der Auszahlungen (?:aus|f[üu]r) Investitionst"),
    ("balance_capital", r"^Saldo aus Investitionst"),
    ("cash_surplus", r"^Finanzmittel-\s*[ÜU]berschuss"),    ("balance_financing", r"^Saldo aus Finanzierungst"),
    ("cash_change", r"^Finanzmittel(?:ver[äa]nderung|bestand)\b"),    ("balance_non_budgetary", r"^Saldo aus haushaltsunwirksamen"),
    ("opening_balance", r"Anfangsbestand an Zahlungsmitteln"),    ("closing_balance", r"Endbestand an Zahlungsmitteln"),)

#: Die sieben Zeilen, ohne die ein Jahrgang wertlos ist. Fehlt eine davon oder
#: reißt eine ihrer Proben, kommt der ganze Jahrgang nicht herein.
PFLICHT_ROLLEN = ("total_in_operating", "total_out_operating", "balance_operating",
                  "total_in_capital", "total_out_capital",
                  "balance_capital", "cash_surplus")

#: Alle übrigen Rollen sind Kür: Das Dokument bezeichnet sie in seiner Fußnote
#: selbst als optional („Die Zeilen 37 bis 41 können optional ergänzt werden").
#: Sie fehlen zu lassen ist kein Fehler; falsch zeigen wäre einer. Welche Probe
#: welche von ihnen trägt, steht in :data:`_KUER_KETTEN`.

#: Die Bestandszeilen führen im Dokument **keine** Ansatzspalte — ein
#: Kassenbestand wird nicht veranschlagt. Was der Spaltenapparat dort als
#: „Plan" findet, ist der Vorjahreswert oder eine Wiederholung; 2018 kam so
#: für den Anfangsbestand ein Ansatz von 61,7 Mio. € heraus, den niemand je
#: beschlossen hat. Für diese Rollen wird deshalb nur das Ist gespeichert.
OHNE_ANSATZ_ROLLEN = ("balance_non_budgetary", "opening_balance", "closing_balance")

#: Seitenfuß mitten in der Tabelle. Anders als in `_SEITENFUSS` wird hier auf
#: derselben Zeile ersetzt und der Zeilenumbruch behalten: Die Postennummern
#: werden am Zeilenanfang gesucht, ein geschluckter Umbruch nähme dem ersten
#: Posten der Folgeseite seinen Anker.
_FR_SEITENFUSS = re.compile(r"[ \t]*\bJA\s*\d{1,3}\b[ \t]*")

#: Ein Querverweis der Tabelle auf ihre eigenen Zeilen — „(Zeile 10 abzüglich
#: Zeile 17)", „(Summe a. Zeilen 37,40,41)". Er steht mitten in der
#: Bezeichnung und enthält zweistellige Zahlen, die wie Postennummern
#: aussehen. Was er sagt, prüft ohnehin :func:`finanzprobe` nach.
_VERWEIS = re.compile(r"\([^()]*Zeilen?[^()]*\)")

#: Beginn einer Tabellenzeile: die Postennummer am **Zeilenanfang**. Der Punkt
#: dahinter ist optional — 2021–2024 schreibt die Stadt „35 Saldo aus
#: Finanzierungstätigkeit" ohne ihn. Ohne den Zeilenanker wäre das zu
#: großzügig: Die Kopfzeile nummeriert ihre Spalten („1 2 3 … 11"), und „10"
#: und „11" von dort hatten die echten Posten 10 und 11 von 2018 verdrängt.
_FR_POSTEN = re.compile(r"^[ \t]*(\d\d)\.?(?:\s*=)?[ \t]", re.M)

#: Rundungstoleranz der Kaskade in Euro. Dieselbe wie in `strukturprobe`: Die
#: Tabelle rechnet auf den Cent, ein Euro Luft deckt die Cent-Rundung.
_FR_TOLERANZ = 1.0


def _rolle(label: str) -> str | None:
    for name, muster in ROLLEN:
        if re.search(muster, label):
            return name
    return None


def _leerer_ansatz(zahlen: list[float], has_prior_year: bool) -> dict | None:
    """Die Zeile ohne Haushaltsansatz — erkannt an der Wiederholung.

    Das Dokument rechnet ``Abweichung = Ergebnis − Ansatz``. Wo kein Ansatz
    steht, sind Ergebnis und Abweichung deshalb **derselbe Betrag**. Gesucht
    wird genau dieses Paar, und zwar unter zwei Bedingungen, die beide nötig
    sind:

    * **Es steht ganz vorn.** Höchstens die Vorjahresspalte darf davor liegen —
      denn „kein Ansatz" heißt: Zwischen Vorjahr und Ergebnis ist die Zeile
      leer. Ohne diese Bedingung schlug die Regel im Jahrgang 2018 bei Posten
      30 zu, wo Gesamtermächtigung und Ergebnis zufällig beide 19.000.000,00 €
      betragen — der Ansatz von 19 Mio. € wäre verloren gegangen.
    * **Dahinter stehen nur noch Nullen.** Die breite 2018er-Tabelle wiederholt
      ihre Beträge über mehrere Ermächtigungsspalten („13.281.900,24
      13.281.900,24 13.281.900,24 14.488.825,34 …"); ohne diese Bedingung
      hielte sich dort jede zweite Zeile für ansatzlos.

    Die Prüfung läuft **vor** dem normalen Spaltenapparat, weil der sonst ein
    Fenster findet, das rechnerisch aufgeht und trotzdem falsch ist: Bei
    Posten 08 des Jahrgangs 2018 („1.850,00 | 180,00 | 180,00 | 0,00") las er
    einen Ansatz von 180,00 € — genug, um die Summenprobe der Einzahlungen um
    genau diesen Betrag zu reißen."""
    # Mit Vorjahresspalte zuerst hinter ihr suchen, dann davor: Auch das
    # Vorjahr darf leer sein („12. Versorgungsauszahlungen 6,00 6,00" im
    # Jahrgang 2019 — zwei Zahlen für eine Zeile mit sechs Spalten).
    for i in ((1, 0) if has_prior_year else (0,)):
        if len(zahlen) > i + 1 and zahlen[i] and zahlen[i] == zahlen[i + 1] \
                and not any(zahlen[i + 2:]):
            return {"prior_year": zahlen[0] if i else None,
                    "ansatz": None, "plan": None, "plan_art": None,
                    "result": zahlen[i], "deviation": zahlen[i + 1],
                    "vorzeichen_repariert": False, "_fenster_start": i}
    return None


#: Die Spalte mit den übertragenen Ermächtigungen. Im PDF-Text bricht das
#: Wort selbst um („Ermächtigun\ngen aus Haushalts-\nvorjahren"), deshalb der
#: Leerraum mitten drin.
_ERMAECHTIGUNG_KOPF = re.compile(
    r"Erm[äa]chtigun\s*g(?:en)?\s+aus\s+Haushaltsvorjahren")


def _fuehrt_ermaechtigung(kopfblock: str, kopf: dict) -> bool:
    """Steht die Ermächtigungsspalte **hinter** dem Ergebnis?

    Nur dann ist sie die Zahl, die dem gefundenen Rechenfenster folgt. Der
    Jahrgang 2018 führt sie als sechste von elf Spalten, also **vor** dem
    Ergebnis; dort steht hinter der Abweichung stattdessen „Zu Spalte 5: Davon
    bisher nicht bewilligte über-/außerplanmäßige Auszahlungen", und die ist
    in jeder Zeile 0,00. Ohne diese Prüfung hätten alle Zeilen des Jahrgangs
    2018 übertragene Ermächtigungen von 0,00 € getragen — eine Zahl, die im
    Dokument so nicht steht (dort sind es 34,9 Mio. €).

    2017 führt die Spalte gar nicht."""
    m = _ERMAECHTIGUNG_KOPF.search(_kopf_normalisieren(kopfblock))
    return bool(m) and m.start() > kopf["positionen"]["result"]


def _ohne_vorjahr(zahlen: list[float], kopf: dict) -> dict | None:
    """Die Zeile mit leerer **Vorjahres**-Spalte: drei Zahlen statt vier.

    `_spalten_zuordnen` verlangt vier Werte und lässt das Fenster nie bei
    Index 0 beginnen — beides ist richtig, solange die erste Zahl der Zeile
    das Vorjahr ist. Steht dort nichts, bleiben genau die drei Werte übrig,
    die die Rechenprobe braucht. Übernommen wird auch hier nur, was sie
    erfüllt; gefunden wurde der Fall bei Posten 30 des Jahrgangs 2017
    („122.853,13 | 100.000,00 | 22.853,13") und ohne ihn riss die
    Summenprobe der Investitions-Auszahlungen um denselben Betrag."""
    if len(zahlen) != 3:
        return None
    ohne = {**kopf, "has_prior_year": False}
    for art in ohne["varianten"]:
        gefunden = _fenster(zahlen, ohne, art)
        if not gefunden:
            continue
        plan, result, deviation, start, repariert = gefunden
        return {"prior_year": None, "ansatz": plan, "plan": plan, "plan_art": art,
                "result": result, "deviation": deviation,
                "vorzeichen_repariert": repariert, "_fenster_start": start}
    return None


def parse_finanzrechnung(text: str, year: int) -> list[dict]:
    """Abschnitt 4.1 des Jahresabschlusses: was die Stadt wirklich ein- und
    ausgezahlt hat.

    Liefert je Zeile ``{nr, role, label, prior_year, ansatz, plan,
    plan_art, result, deviation, authorization, is_total}``. ``nr`` ist
    die Nummer, die das Dokument vergibt (und die sich zwischen den
    Jahrgängen verschiebt), ``role`` der stabile Name aus :data:`ROLLEN` —
    Leser*innen und Frontend hängen an der Rolle, nie an der Nummer.

    ``authorization`` ist die letzte Spalte: Geld, das aus Vorjahren
    übertragen wurde und in diesem Jahr noch ausgegeben werden durfte. Sie
    steht direkt hinter der Abweichung, deshalb wird sie über das Fenster
    abgegriffen, das die Rechenprobe gefunden hat — nicht über eine
    Positionsannahme.

    Geprüft wird nichts hier: :func:`finanzprobe` entscheidet, ob der
    Jahrgang übernommen wird."""
    stellen = [m.start() for m in re.finditer(
        r"Finanzrechnung\s+(?:der\s+)?Kernverwaltung", text)]
    if not stellen:
        return []
    # Erster Treffer ist das Inhaltsverzeichnis; genommen wird die Fundstelle
    # mit den meisten Beträgen dahinter — dieselbe Regel wie oben.
    start = max(stellen, key=lambda i: len(_BETRAG.findall(text[i:i + 6000])))
    # Dahinter folgt die Gesamtfinanzrechnung (mit Stiftungen), die eigene
    # Werte trägt. Der Mindestabstand hält die Überschrift der eigenen
    # Tabelle aus der Suche heraus.
    ende = text.find("Gesamtfinanzrechnung", start + 3000)
    block = text[start:ende if ende > 0 else start + 12000]

    schnitt = re.search(r"Einzahlungen aus\s+laufender", block)
    kopfblock = block[:schnitt.start()] if schnitt else block[:900]
    kopf = _tabellenkopf(kopfblock, year)
    if kopf is None:
        return []
    hat_ermaechtigung = _fuehrt_ermaechtigung(kopfblock, kopf)

    teile = _FR_POSTEN.split(_VERWEIS.sub(" ", _FR_SEITENFUSS.sub("\n", block)))
    inhalt: dict[int, str] = {}
    for i in range(1, len(teile) - 1, 2):
        # Erster Treffer gewinnt: Wiederholungen sind Fortsetzungsseiten.
        inhalt.setdefault(int(teile[i]), " ".join(teile[i + 1].split()))

    out: list[dict] = []
    for nr in sorted(inhalt):
        if not 1 <= nr <= 45:
            continue
        roh = inhalt[nr][:260]
        zahlen = [_eur(z) for z in _BETRAG.findall(roh)]
        label = " ".join(_BETRAG.split(roh)[0].split()).strip(" .")
        role = _rolle(label)
        werte = (_leerer_ansatz(zahlen, kopf["has_prior_year"])
                 or _spalten_zuordnen(zahlen, kopf)
                 or _ohne_vorjahr(zahlen, kopf))
        if werte is None:
            continue
        werte.pop("vorzeichen_repariert", None)
        # Die Ermächtigung steht eine Spalte hinter der Abweichung. Es gibt
        # sie nur, wenn die Zeile dort auch wirklich noch eine Zahl trägt.
        stelle = werte.pop("_fenster_start") + (
            4 if werte.get("plan_art") == "ansatz_nachtrag" else 3)
        authorization = (zahlen[stelle] if hat_ermaechtigung
                         and stelle < len(zahlen) else None)
        if role in OHNE_ANSATZ_ROLLEN:
            # Kein Ansatz im Dokument, also auch keiner bei uns (s. o.).
            werte.update(ansatz=None, plan=None, plan_art=None, deviation=None)
            authorization = None
        out.append({"nr": nr, "role": role, "label": label,
                    "year": year, "authorization": authorization,
                    "is_total": 1 if role else 0, **werte})
    return out


def _bereiche(nach_rolle: dict[str, dict]) -> list[tuple[str, int, int, str]] | str:
    """Welche Zeilen sich zu welcher Summenzeile addieren — abgeleitet aus der
    Nummerierung des Dokuments, nicht aus einem Katalog.

    Die Summenzeilen kennen wir über ihre Rolle; dazwischen liegt jeweils
    genau der Block, den sie summieren. Dass die Salden unmittelbar hinter
    ihrer Summenzeile stehen, ist dabei selbst eine Probe: Sitzt eine Rolle
    an einer Nummer, die nicht zur Reihenfolge passt, wurde die falsche Zeile
    erkannt und der Jahrgang fliegt raus.

    Gibt die Blöcke zurück oder eine Begründung als Text."""
    nr = {r: p["nr"] for r, p in nach_rolle.items()}
    fehlend = [r for r in PFLICHT_ROLLEN if r not in nr]
    if fehlend:
        return "Zeilen nicht gefunden: " + ", ".join(fehlend)
    if not (nr["balance_operating"] == nr["total_out_operating"] + 1
            and nr["balance_capital"] == nr["total_out_capital"] + 1
            and nr["cash_surplus"] == nr["balance_capital"] + 1):
        return ("Reihenfolge passt nicht zur Nummerierung: "
                + ", ".join(f"{r}={nr[r]}" for r in PFLICHT_ROLLEN))
    return [
        ("Einzahlungen aus laufender Verwaltungstätigkeit",
         1, nr["total_in_operating"] - 1, "total_in_operating"),
        ("Auszahlungen aus laufender Verwaltungstätigkeit",
         nr["total_in_operating"] + 1, nr["total_out_operating"] - 1,
         "total_out_operating"),
        ("Einzahlungen für Investitionstätigkeit",
         nr["balance_operating"] + 1, nr["total_in_capital"] - 1,
         "total_in_capital"),
        ("Auszahlungen für Investitionstätigkeit",
         nr["total_in_capital"] + 1, nr["total_out_capital"] - 1,
         "total_out_capital"),
    ]


#: Die drei Salden der Kaskade: ``ziel = a (±) b``.
_SALDEN = (("total_in_operating", "total_out_operating", "balance_operating", -1),
           ("total_in_capital", "total_out_capital", "balance_capital", -1),
           ("balance_operating", "balance_capital", "cash_surplus", +1))

#: Die Kür-Ketten: ``(glieder, ziel, was die Kette belegt)``.
#:
#: Das dritte Feld ist der Grund, warum die Ketten überhaupt getrennt sind.
#: Eine Kette belegt nur die Zeilen, die es ohne sie nicht gäbe — die
#: Bestandskette belegt die drei Bestandszeilen, die Tilgungskette den Saldo
#: der Finanzierungstätigkeit und die Finanzmittelveränderung. Fehlen die
#: optionalen Bestandszeilen (das Dokument erlaubt es ausdrücklich), soll die
#: Finanzmittelveränderung deshalb bleiben: Sie hängt an der anderen Kette,
#: und die geht auf.
#:
#: Die Reihenfolge ist nicht beliebig: Die Bestandskette rechnet mit der
#: Finanzmittelveränderung. Fällt die erste Kette, ist die zweite nicht mehr
#: belegt, auch wenn sie für sich aufginge.
_KUER_KETTEN = (
    (("cash_surplus", "balance_financing"), "cash_change",
     ("balance_financing", "cash_change")),
    (("opening_balance", "cash_change", "balance_non_budgetary"),
     "closing_balance",
     ("opening_balance", "balance_non_budgetary", "closing_balance")),
)


def finanzprobe(posten: list[dict], toleranz: float = _FR_TOLERANZ
                ) -> tuple[list[dict], list[str], list[str]]:
    """Die Rechenkaskade der Finanzrechnung — die Eintrittskarte jedes
    Jahrgangs.

    Das Dokument rechnet sich neunmal selbst vor, und jede Stufe hängt an der
    vorigen::

        Summe Einzahlungen  = Σ der Einzahlungsarten
        Summe Auszahlungen  = Σ der Auszahlungsarten
        Saldo Verwaltung    = Einzahlungen − Auszahlungen
        (dasselbe für die Investitionstätigkeit)
        Finanzmittelsaldo   = Saldo Verwaltung + Saldo Investition
        Finanzmittelveränd. = Finanzmittelsaldo + Saldo Finanzierung   (Kür)
        Endbestand = Anfangsbestand + Veränderung + haushaltsunwirksam (Kür)

    Geprüft wird in **beiden** Größen, im Ist und im Ansatz: Eine Zeile aus
    einer falschen, in sich stimmigen Tabelle fiele sonst nicht auf.

    Eine **fehlende** Einzelzeile zählt dabei als Null. Das ist keine Lücke im
    Beweis, sondern der Beweis selbst: Fehlt eine Zeile, weil das Dokument
    sie leer lässt (Versorgungsauszahlungen 2024, Finanzvermögensanlagen), so
    geht die Summe auf — fehlt sie, weil wir sie falsch gelesen haben, geht
    sie nicht auf, und der Jahrgang fliegt raus.

    Die Ermächtigungen aus Vorjahren tragen dieselbe Probe noch einmal: Die
    übertragenen Beträge der Einzelzeilen ergeben die der Summenzeile. Wo das
    nicht aufgeht, wird die ganze Spalte verworfen — nicht der Jahrgang.

    Gibt ``(uebernommen, fehler, hinweise)`` zurück. Ist ``fehler`` nicht
    leer, gehört der Jahrgang nicht in den Bestand."""
    nach_rolle = {p["role"]: p for p in posten if p.get("role")}
    nach_nr = {p["nr"]: p for p in posten}
    bereiche = _bereiche(nach_rolle)
    if isinstance(bereiche, str):
        return [], [bereiche], []

    fehler: list[str] = []
    hinweise: list[str] = []

    def summe(von: int, bis: int, field: str) -> float:
        return sum(nach_nr[n].get(field) or 0 for n in range(von, bis + 1) if n in nach_nr)

    for field, wie in (("result", "Ist"), ("plan", "Ansatz")):
        for name, von, bis, role in bereiche:
            soll, ist = nach_rolle[role].get(field), summe(von, bis, field)
            if soll is None:
                fehler.append(f"{wie}: {name} — Summenzeile ohne Wert")
            elif abs(ist - soll) > toleranz:
                fehler.append(f"{wie}: {name} — Einzelzeilen {ist:,.2f} € ≠ "
                              f"Summenzeile {soll:,.2f} € (Δ {ist - soll:+,.2f} €)")
        for a, b, ziel, vorzeichen in _SALDEN:
            werte = [nach_rolle[r].get(field) for r in (a, b, ziel)]
            if any(v is None for v in werte):
                fehler.append(f"{wie}: {ziel} nicht nachrechenbar — Wert fehlt")
            elif abs((werte[0] + vorzeichen * werte[1]) - werte[2]) > toleranz:
                fehler.append(
                    f"{wie}: {a} {vorzeichen:+d}·{b} = "
                    f"{werte[0] + vorzeichen * werte[1]:,.2f} € ≠ {ziel} "
                    f"{werte[2]:,.2f} €")

    # Die Ermächtigungen: eigene Probe, eigenes Schicksal.
    traegt_ermaechtigung = True
    for name, von, bis, role in bereiche:
        soll = nach_rolle[role].get("authorization")
        ist = summe(von, bis, "authorization")
        if soll is None and not ist:
            continue  # der Jahrgang führt diese Spalte hier nicht
        if soll is None or abs(ist - (soll or 0)) > toleranz:
            hinweise.append(f"Ermächtigungen verworfen: {name} — Einzelzeilen "
                            f"{ist:,.2f} € ≠ Summenzeile "
                            f"{'—' if soll is None else format(soll, ',.2f') + ' €'}")
            traegt_ermaechtigung = False
    if not traegt_ermaechtigung:
        for p in posten:
            p["authorization"] = None

    # Die Kür: je Kette einzeln. Was nicht vollständig ist oder nicht aufgeht,
    # verliert die Zeilen, die diese Kette belegt — der Jahrgang bleibt.
    gestrichen: set[str] = set()
    for glieder, ziel, lizenziert in _KUER_KETTEN:
        alle = glieder + (ziel,)
        werte = [nach_rolle[r].get("result") if r in nach_rolle else None
                 for r in alle]
        if gestrichen & set(glieder):
            hinweise.append(f"{ziel} nicht gespeichert — die Kette davor trägt nicht")
        elif any(v is None for v in werte):
            fehlt = [r for r, v in zip(alle, werte) if v is None]
            hinweise.append(f"{ziel} nicht gespeichert — {', '.join(fehlt)} fehlt")
        elif abs(sum(werte[:-1]) - werte[-1]) > toleranz:
            hinweise.append(f"{ziel} verworfen: {' + '.join(glieder)} = "
                            f"{sum(werte[:-1]):,.2f} € ≠ {werte[-1]:,.2f} €")
        else:
            continue
        gestrichen |= set(lizenziert)

    uebernommen = [p for p in posten if p.get("role") not in gestrichen]
    return (uebernommen if not fehler else []), fehler, hinweise


def kassenkette(je_jahr: dict[int, list[dict]],
                toleranz: float = _FR_TOLERANZ) -> list[tuple[int, int, str]]:
    """Die Probe über Dokumentgrenzen hinweg: Was am 31.12. in der Kasse lag,
    steht im Jahresabschluss des Folgejahres noch einmal als Anfangsbestand.

    Das Gegenstück zu :func:`vorjahreskette` für die Ergebnisrechnung, und aus
    demselben Grund wertvoll: Beide Zahlen stammen aus **verschiedenen**
    Dokumenten, die Jahre auseinanderliegen. Ein Lesefehler in einem der
    beiden fällt hier auf, ohne dass wir eine eigene Rechnung anstellen.

    Zurück kommt die Liste der **gerissenen** Glieder als
    ``(year, folgejahr, begruendung)``. Geprüft wird nur, wo beide Jahrgänge
    ihre Bestandszeilen führen — sie sind laut Dokument optional, und ein
    fehlendes Glied ist keine gerissene Kette."""
    kaputt: list[tuple[int, int, str]] = []
    for year in sorted(je_jahr):
        if year + 1 not in je_jahr:
            continue
        ende = next((p.get("result") for p in je_jahr[year]
                     if p.get("role") == "closing_balance"), None)
        anfang = next((p.get("result") for p in je_jahr[year + 1]
                       if p.get("role") == "opening_balance"), None)
        if ende is None or anfang is None:
            continue
        if abs(ende - anfang) > toleranz:
            kaputt.append((year, year + 1,
                           f"Endbestand {ende:,.2f} € ≠ Anfangsbestand des "
                           f"Folgejahres {anfang:,.2f} €"))
    return kaputt


# --- Jahresabschluss: das „Warum" zu den Abweichungen -----------------------

#: Überschrift des Erläuterungsteils. Im PDF-Text ist sie umbrochen und
#: getrennt („in der Ergebni s-\nrechnung"), deshalb wird für die Auswahl
#: normalisiert statt wörtlich gesucht.
_ERLAEUTERUNG_KOPF = re.compile(r"Erläuterung der erheblichen Plan\s?/?\s?-?\s?Ist")

#: Ein erläuterter Posten: „01. Steuern und ähnliche Abgaben (+75,1 Millionen
#: Euro, +24,82 %)". Die Schreibweise wechselt über die Jahrgänge zwischen
#: „Mio. EUR" und „Millionen Euro", mit und ohne Punkt hinter der Nummer,
#: mit und ohne Leerzeichen hinter dem Vorzeichen.
_ERLAEUTERUNG_POSTEN = re.compile(
    r"(?<![\d,.])(\d\d)\.?\s+([^\n(]{3,70}?)\s*\(\s*([+-])\s*([\d.,]+)\s*"
    r"(?:Mio\.?|Millionen)\s*(?:EUR|Euro)\s*,\s*([+-])\s*([\d.,]+)\s*%\s*\)")

#: Seitenfuß „JA 161", der mitten im Fließtext landet — mal mit einem, mal
#: mit zwei Leerzeichen. Die Wortgrenze hinter der Zahl schützt vor
#: Jahreszahlen („JA 2020" bliebe stehen).
_SEITENFUSS = re.compile(r"\s*\bJA\s*\d{1,3}\b\s*")

#: Die nächste nummerierte Abschnittsüberschrift — sie beendet den letzten
#: Posten.
#:
#: Warum es die braucht: Der Erläuterungsteil endet nicht mit einer eigenen
#: Marke. Für jeden Posten außer dem letzten liefert der nächste Posten das
#: Ende; der letzte lief bis zum Blockende — und das ist erst die
#: Finanzrechnungs-Fassung derselben Überschrift, die im Dokument **hinter**
#: Abschnitt 6.4 steht. Der letzte Posten schluckte damit ganze Folge-
#: abschnitte: gemessen über alle acht Jahrgänge 5.371–7.176 Zeichen, während
#: der längste aller übrigen 1.378 hat.
#:
#: Die Bedingungen sind einzeln nötig: Ziffernfolge (der Bericht nummeriert
#: seine Abschnitte), führender Leerraum (sonst greift sie in „1.049.000"),
#: Großbuchstabe mit kleiner Fortsetzung dahinter (sonst greift sie in
#: Verweisen wie „unter Ziffer 2.2.1.1 des Rechenschaftsberichts" — dort geht
#: es klein weiter).
_NAECHSTER_ABSCHNITT = re.compile(r"\s\d{1,2}(?:\.\d{1,2}){1,3}\s+[A-ZÄÖÜ][a-zäöüß]")


def _bis_abschnittsende(text: str) -> str:
    """Schneidet an der nächsten Abschnittsüberschrift ab.

    Wird auf **jeden** Posten angewandt, nicht nur auf den letzten: Für die
    übrigen ist es folgenlos (ihr Ende liegt vorher), und die Regel muss nicht
    wissen, welcher Posten der letzte ist.

    **Probe am Bestand (17.08.2026, alle 45 Zeilen):** greift bei 8 von 8
    letzten Posten, bei 0 von 37 übrigen. Ein Muster, das auch die kurzen
    Erläuterungen anschnitte, wäre zu gierig und dürfte nicht bleiben."""
    m = _NAECHSTER_ABSCHNITT.search(text)
    return text[:m.start()].rstrip() if m else text


def _fliesstext(roh: str) -> str:
    """Erläuterungstext lesbar machen, ohne ihn zu verändern.

    Aus dem PDF kommt der Text mit Trennstrichen am Zeilenende
    („ent-\\nstanden") und mit eingestreuten Seitenfüßen. Beides wird
    entfernt — der Wortlaut selbst bleibt unangetastet.

    Ein Trennstrich wird nur dann geschluckt, wenn es hinter dem Umbruch
    klein weitergeht: „Personal-\\nrückstellungen" ist eine Silbentrennung,
    „Fliegerhorst-\\nGelände" dagegen ein echter Bindestrich."""
    ohne_trennung = re.sub(r"-\s*\n\s*(?=[a-zäöüß])", "", roh)
    ohne_trennung = re.sub(r"-\s*\n\s*(?=[A-ZÄÖÜ])", "-", ohne_trennung)
    return " ".join(_SEITENFUSS.sub(" ", ohne_trennung).split())


def parse_abweichungsgruende(text: str, year: int) -> list[dict]:
    """Abschnitt 6.3.1 des Jahresabschlusses: **warum** ein Posten vom Plan
    abweicht, je Posten und in den Worten der Verwaltung.

    Liefert je Posten ``{nr, label, delta_meur, percent, text}``.
    ``delta_meur`` und ``percent`` sind die Werte, die die Überschrift selbst
    nennt — sie sind die Eintrittskarte: Erst der Abgleich mit der geparsten
    Tabellenzeile (``pruefe_abweichungsgruende``) entscheidet, ob die
    Erläuterung übernommen wird.

    Der Abschnitt existiert zweimal je Dokument — einmal für die Ergebnis-,
    einmal für die Finanzrechnung. Gesucht ist die Ergebnisrechnung; erkannt
    wird sie am entzifferten Überschrifts-Rest, nicht an der Reihenfolge.

    Jeder Text endet an der nächsten Abschnittsüberschrift
    (``_bis_abschnittsende``). Ohne diesen Schnitt lief der **letzte** Posten
    bis zum Blockende weiter und nahm Abschnitt 6.4 mitsamt Folgeabschnitten
    mit — der Erläuterungsteil hat keine eigene Schlussmarke."""
    stellen = [m.start() for m in _ERLAEUTERUNG_KOPF.finditer(text)]
    gewaehlt = None
    for i, s in enumerate(stellen):
        # „in der Ergebnis-rechnung der Kernverwaltung" — nach dem Entfalten.
        titel = _kopf_normalisieren(text[s:s + 130]).replace(" ", "")
        if "Ergebnisrechnung" not in titel:
            continue
        ende = stellen[i + 1] if i + 1 < len(stellen) else len(text)
        block = text[s:min(ende, s + 16000)]
        # Das Inhaltsverzeichnis trägt dieselbe Überschrift, aber keine Posten.
        if len(_ERLAEUTERUNG_POSTEN.findall(block)) >= 2:
            gewaehlt = block
    if gewaehlt is None:
        return []

    treffer = list(_ERLAEUTERUNG_POSTEN.finditer(gewaehlt))
    out: list[dict] = []
    for i, m in enumerate(treffer):
        ende = treffer[i + 1].start() if i + 1 < len(treffer) else len(gewaehlt)
        nr = int(m.group(1))
        if nr not in ERGEBNIS_POSTEN:
            continue
        vorzeichen = -1 if m.group(3) == "-" else 1
        vz_prozent = -1 if m.group(5) == "-" else 1
        out.append({
            "year": year, "nr": nr,
            "label": " ".join(m.group(2).split()),
            "delta_meur": _eur_lose(m.group(4)) * vorzeichen,
            "percent": _eur_lose(m.group(6)) * vz_prozent,
            "text": _bis_abschnittsende(_fliesstext(gewaehlt[m.end():ende])),
        })
    return out


def _eur_lose(s: str) -> float:
    """Zahl aus dem Fließtext („6,3", „107,2", „1.618"). Anders als in den
    Tabellen fehlen hier die Nachkommastellen mal ganz."""
    return float(s.replace(".", "").replace(",", "."))


def pruefe_abweichungsgruende(gruende: list[dict], posten: list[dict],
                              toleranz_mio: float = 0.12,
                              toleranz_prozent: float = 0.6) -> tuple[list[dict], list[str]]:
    """Die Eintrittskarte für jede Erläuterung.

    Die Überschrift nennt die Abweichung **doppelt** — als Betrag und als
    Prozentsatz. Beides muss zu der Zeile passen, die der Tabellen-Parser für
    denselben Posten gelesen hat. Damit prüft sich das Dokument an einer
    zweiten Stelle selbst; was nicht zusammenpasst, wird verworfen statt
    angezeigt.

    Der Prozentsatz bezieht sich dabei auf den **Plan** (die Bezugsgröße der
    Abweichung), nicht auf den nackten Ansatz — in den Jahrgängen mit
    Nachtrag oder Gesamtermächtigung ist das der Unterschied, an dem die
    Probe hängt.

    Gibt ``(angenommen, begruendungen_der_ablehnung)`` zurück."""
    nach_nr = {p["nr"]: p for p in posten}
    angenommen: list[dict] = []
    abgelehnt: list[str] = []
    for g in gruende:
        p = nach_nr.get(g["nr"])
        if not p or p.get("deviation") is None:
            abgelehnt.append(f"Posten {g['nr']}: keine passende Tabellenzeile")
            continue
        ist_mio = p["deviation"] / 1e6
        if abs(ist_mio - g["delta_meur"]) > toleranz_mio:
            abgelehnt.append(
                f"Posten {g['nr']}: Text {g['delta_meur']:+.1f} Mio. ≠ Tabelle {ist_mio:+.2f} Mio.")
            continue
        plan = p.get("plan")
        if plan:
            ist_prozent = p["deviation"] / plan * 100
            if abs(ist_prozent - g["percent"]) > toleranz_prozent:
                abgelehnt.append(
                    f"Posten {g['nr']}: Text {g['percent']:+.2f} % ≠ Tabelle {ist_prozent:+.2f} %")
                continue
        angenommen.append(g)
    return angenommen, abgelehnt


# --- Schlussberichte des Rechnungsprüfungsamts ------------------------------

#: Der Satz, mit dem jeder Schlussbericht zur Kernverwaltung anfängt. Die
#: Labels taugen zur Auswahl nicht: „Schlussbericht JA 2017" ist der
#: Prüfbericht zum Eigenbetrieb Gebäudewirtschaft, und ein gutes Dutzend
#: weiterer Treffer betrifft Klävemann-Stiftung, VOSS, AWB oder EGH. Nur
#: diese Formel nennt die Stadt selbst als geprüfte Stelle.
_PRUEFBERICHT = re.compile(
    r"Schlussbericht des Rechnungspr[üu]fungsamtes\s+über die Pr[üu]fung\s+"
    r"des Jahresabschlusses\s+(20\d\d)\s+der Stadt Oldenburg")

#: Unterhalb dieses Buchstabenanteils ist der Volltext kein Text mehr.
#: Der Schlussbericht 2024 trägt keine ToUnicode-Zuordnung; sein Extrakt
#: besteht aus Glyphen-Indizes („/12 /8 /6 □ …") und kommt auf 0,00 —
#: die brauchbaren Jahrgänge liegen alle zwischen 0,71 und 0,76.
_TEXT_MINDESTANTEIL = 0.40


def pruefbericht_aus_anlage(label: str | None, raw_text: str | None) -> dict | None:
    """Erkennt den Schlussbericht des Rechnungsprüfungsamts zur
    **Kernverwaltung** und sagt, ob sein Volltext brauchbar ist.

    Liefert ``{year, readable, buchstabenanteil}`` oder ``None``. Gesucht wird
    zuerst im Text, ersatzweise im Label — beim Jahrgang 2024 ist der Text
    unbrauchbar, das Dokument aber vorhanden und verlinkbar.

    Achtung: Der Volltext ist umbrochen, die Formel steht also nicht als
    zusammenhängende Zeichenkette in der Datenbank. Ein ``LIKE`` darauf
    findet nichts — deshalb wird vor dem Vergleich normalisiert."""
    text = raw_text or ""
    kopf = _kopf_normalisieren(text[:400])
    treffer = _PRUEFBERICHT.search(kopf) or _PRUEFBERICHT.search(
        " ".join((label or "").split()))
    if not treffer:
        return None
    buchstaben = sum(ch.isalpha() for ch in text)
    anteil = buchstaben / max(len(text), 1)
    return {"year": int(treffer.group(1)), "readable": anteil >= _TEXT_MINDESTANTEIL,
            "buchstabenanteil": round(anteil, 4)}


# --- Teilhaushalte: Produktebene --------------------------------------------

_PRODUKT_KOPF = re.compile(
    r"Teilergebnishaushalt\s+THH(\d+):\s*([^\n]+?)\s*\n\s*"
    r"Produkt:\s*(.+?)\s*\((P[\d.]+)\)\s*\n\s*([^\n]+)")
#: Zahlen in den THH-Tabellen stehen teils ohne Nachkommastellen („484.239").
_THH_BETRAG = re.compile(r"-?\d{1,3}(?:\.\d{3})*(?:,\d{2})?")


def _thh_zahlen(zeile: str) -> list[float]:
    out = []
    for s in _THH_BETRAG.findall(zeile):
        if s in {"-", ""}:
            continue
        out.append(float(s.replace(".", "").replace(",", ".")))
    return out


# Beschriftung und Zahlenkolonne stehen im PDF-Extrakt nicht zwingend auf
# derselben Zeile — und seit dem **Haushaltsplan 2025** regelmäßig nicht mehr.
# Die Stadt hat der Zeile „21. ordentliches Ergebnis" zwei Beschriftungszeilen
# nachgestellt::
#
#     20. = Summe ordentliche
#     Aufwendungen
#     7.723.524,43 8.153.186 9.520.575 9.708.260 9.656.398 9.798.826
#     21. ordentliches Ergebnis
#     Jahresüberschuss(+)
#     /Jahresfehlbetrag (-)
#     -7.247.704,53 -7.706.646 -8.860.025 -9.016.606 -9.197.608 -9.340.036
#
# Wer nur „Rest der Zeile plus höchstens eine weitere" liest, findet dort
# nichts mehr — und verliert mit Posten 21 das ganze Produkt, weil die
# Rechenprobe ohne ihn nicht aufgeht. Genau das ist ab dem Plan 2025 passiert:
# 0 von 78 bzw. 0 von 89 Produkten, während 2018–2023 unverändert durchliefen.
#
# Ein Seitenumbruch kann die beiden Zeilen sogar zerreißen (Plan 2026, THH01:
# „Jahresüberschuss(+)" steht vor der Zahlenzeile, „/Jahresfehlbetrag (-)"
# hinter dem Seitenkopf dahinter). Eine feste Zeilenzahl trifft das nicht;
# gesucht wird deshalb vorwärts bis zur Zahlenzeile.
#
# DIE GEFAHR DABEI ist nicht theoretisch: Läuft die Suche zu weit, holt sie
# die Zahlen der NÄCHSTEN Zeile. Über den Bestand gemessen steht zwischen
# Beschriftung und Zahlen 155-mal „Jahresüberschuss(+)", aber 85-mal auch
# „Ordentliche Aufwendungen" und 21-mal „14. Versorgungsaufwendungen" — dort
# ist die eigene Zelle nämlich leer. Ohne harte Grenze klebte der Personal-
# aufwand als „Summe ordentliche Erträge" am Produkt. Deshalb endet die Suche
# an der ersten Zeile, die eine neue Tabellenzeile beginnt.

#: Beginn einer neuen Tabellenzeile: nummerierter Posten („13.", „21."),
#: Kontonummer („34859902 …"), Zwischenüberschrift oder ein wiederholter
#: Seitenkopf. Hier ist Schluss — was dahinter steht, gehört einem anderen
#: Posten.
#:
#: Das ``(?!\d)`` hinter der Postennummer ist nicht kosmetisch: Ohne es gilt
#: „38.949.730,76" als Beginn von Posten 38 — die Zahlenzeile hielte sich
#: selbst für die nächste Zeile, und Posten 20 bliebe in jedem Dokument leer.
_THH_NEUE_ZEILE = re.compile(
    r"^[ \t]*(?:\d\d\.(?!\d)|\d{6,}|Ordentliche\s+(?:Erträge|Aufwendungen)\b"
    r"|Nachrichtlich\b|Teilergebnishaushalt\b|Teilfinanzhaushalt\b)")

#: Eine Zahlenzeile trägt nur Zahlen. Das schließt die Kopfzeilen aus, die
#: ein Seitenumbruch einstreut („Ansatz 2025", „- Euro -"): Sie enthalten
#: zwar Ziffern, aber eben auch Text.
_THH_NUR_ZAHLEN = re.compile(r"[ \t]*(?:-?\d{1,3}(?:\.\d{3})*(?:,\d{2})?[ \t]*)+")

#: Sicherheitsnetz gegen eine davonlaufende Suche. Gemessen am Bestand liegen
#: zwischen Beschriftung und Zahlen höchstens zwei Zeilen; acht lassen einem
#: eingestreuten Seitenkopf Luft, ohne in die übernächste Tabelle zu geraten.
_THH_MAX_ZEILEN = 8


def _thh_wertezeile(block: str, muster: str, spalten: int) -> list[float] | None:
    """Die Zahlenkolonne zu einer Postenbeschriftung holen.

    Gesucht wird ab dem Ende der Beschriftung vorwärts nach der ersten Zeile,
    die aus **nur** Zahlen besteht und mindestens so viele trägt, wie der
    Tabellenkopf Spalten nennt. Übersprungen wird dabei alles, was selbst
    keine Tabellenzeile ist: die Fortsetzung der Beschriftung
    („Jahresüberschuss(+)"), eine Seitenzahl, ein wiederholter Seitenkopf.

    ``None``, sobald eine neue Tabellenzeile anfängt — dann ist die eigene
    Zelle leer, und die Zahlen dahinter gehören jemand anderem. Das ist der
    häufige Fall (Produkte ohne Erträge), und er bleibt bewusst eine Lücke:
    Wo im Dokument nichts steht, lässt sich auch nichts nachrechnen."""
    m = re.search(muster, block)
    if not m:
        return None
    for zeile in block[m.end():].split("\n")[:_THH_MAX_ZEILEN]:
        if _THH_NEUE_ZEILE.match(zeile):
            return None
        if not zeile.strip():
            continue
        if not _THH_NUR_ZAHLEN.fullmatch(zeile.rstrip()):
            continue
        zahlen = _thh_zahlen(zeile)
        if len(zahlen) >= spalten:
            return zahlen
    return None


# --- Teilhaushalte: Produkt-Steckbrief ---------------------------------------
#
# Zu jedem Produkt führen die Pläne einen Steckbrief: was die Aufgabe umfasst,
# auf welchem Gesetz sie beruht, wie viel Spielraum die Stadt bei ihr hat.
# Genau das beantwortet die häufigste Bürgerfrage zum Haushalt („was kostet
# eigentlich das Stadtarchiv?") — und belegt die Pflicht/Kür-Einordnung, statt
# sie zu schätzen.
#
# ZWEI FALLEN, beide beim Bauen aufgelaufen:
#
# 1. **Die Label stehen im extrahierten Text NACH ihrem Inhalt.** Im PDF sitzt
#    „Kurzbeschreibung:" als Spaltenüberschrift links neben dem Absatz; die
#    Textextraktion schiebt sie dahinter. Die Reihenfolge im Text ist also:
#    Absatz, dann `Kurzbeschreibung:`, dann der Rechtsgrundlagen-Absatz, dann
#    `Auftragsgrundlage:`. Wer vorwärts liest, bekommt jedes Feld um genau
#    eines verschoben — die Kurzbeschreibung wäre dann das Gesetz.
#    Kurze Werte passen im PDF neben ihr Label und stehen deshalb DAHINTER
#    („Grad der Beeinflussbarkeit: mittel"). Beide Fälle stehen unten
#    ausdrücklich als `rueckwaerts` markiert, statt sie zu erraten.
#
# 2. **Jede Leistung trägt einen eigenen Steckbrief.** Ein Produkt zerfällt in
#    Leistungen („Leistung: Interne Gleichstellungsarbeit (P10.111000.001)"),
#    und die haben dieselben Felder. Ungefiltert bekäme das Produkt den Text
#    einer beliebigen Unterposition. Deshalb wird der Produktblock vor der
#    ersten Leistungs-Überschrift abgeschnitten (in 661 von 664 Blöcken des
#    Bestands steht der Produkt-Steckbrief davor; in den übrigen bleiben die
#    Felder leer — lieber eine Lücke als ein fremder Text).

#: Felder, die wir übernehmen: (Spalte, Label-Regex, Inhalt steht davor?).
_STECKBRIEF_FELDER: tuple[tuple[str, str, bool], ...] = (
    ("short_description", r"Kurzbeschreibung", True),
    ("legal_basis", r"Auftragsgrundlage", True),
    ("controllability_raw", r"Grad der Beeinflussbarkeit", False),
    ("scope", r"Wirkungskreis", False),
    ("target_group", r"Zielgruppe\(n\)", True),
)

#: Weitere Label des Steckbriefs. Wir lesen sie nicht, aber sie begrenzen die
#: rückwärts gelesenen Felder — ohne sie liefe die Zielgruppe bis in die
#: Kennzahlen-Tabelle.
_WEITERE_LABEL = (
    r"Ziel\(e\)", r"Kennzahl\(en\)", r"Maßnahme\(n\)", r"Erläuterung\(en\)",
    r"Grunddaten", r"Haushaltsvermerk\(e\)", r"Zuweisungen und Zuschüsse an Dritte",
    r"Leistungen", r"Das Produkt enthält [^\n:]{0,40}Leistungen", r"Projekte",
    r"Investitionen", r"Städtische Einrichtungen", r"Verantwortlich", r"Hinweis",
)

#: Alle Label als eine Alternative — Zeilenanfang, damit „… im eigenen
#: Wirkungskreis:" mitten im Fließtext keine Grenze zieht.
_LABEL = re.compile(
    r"^[ \t]*(" + "|".join([r for _, r, _ in _STECKBRIEF_FELDER] + list(_WEITERE_LABEL))
    + r"):", re.M)

#: Zeilen, die kein Fließtext sind: Tabellenkopf der Grunddaten/Kennzahlen,
#: Tabellenzeile (endet auf mehreren Zahlen), nacktes Einheiten-Kürzel,
#: Seitenzahl.
_KEIN_FLIESSTEXT = re.compile(
    r"^\s*(?:\d{1,4}"                                  # Seitenzahl
    r"|(?:PRS|ST|EUR|VZÄ|%|Anzahl)"                    # nacktes Einheiten-Kürzel
    r"|.*\bEinheit\b.*(?:Ist|Plan)\s+20\d\d.*"         # Tabellenkopf
    r"|.*?(?:\s-?[\d.,]+){2,}"                         # Tabellenzeile
    r")\s*$")

#: Erste Zeile eines wiederholten Seitenkopfs. Der Kopf ist mehrzeilig
#: (Teilergebnishaushalt · Produkt · [Leistung ·] Amt) und muss als Einheit
#: fallen: Die Amtszeile allein sieht aus wie Fließtext und stand sonst vorn
#: in der Zielgruppe („Amt für Umweltschutz und Bauordnung Verwaltung und
#: Politik sowie alle …").
_KOPFZEILE = re.compile(r"^\s*Teilergebnishaushalt\b")


def _ohne_seitenkopf(zeilen: list[str]) -> list[str]:
    """Wiederholte Seitenköpfe aus einem Steckbrief-Abschnitt entfernen."""
    out: list[str] = []
    i = 0
    while i < len(zeilen):
        if not _KOPFZEILE.match(zeilen[i]):
            out.append(zeilen[i])
            i += 1
            continue
        i += 1  # „Teilergebnishaushalt THH…"
        for muster in (r"^\s*Produkt:", r"^\s*Leistung:"):
            if i < len(zeilen) and re.match(muster, zeilen[i]):
                i += 1
        if i < len(zeilen) and zeilen[i].strip():
            i += 1  # die Amtszeile
    return out

#: Überschrift einer Leistung — die Grenze des Produkt-Steckbriefs.
_LEISTUNG_KOPF = re.compile(r"^[ \t]*Leistung:[^\n]*\(P[\d.]+\.\d+\)[ \t]*$", re.M)

#: Die Stadt schreibt denselben Spielraum mal „niedrig", mal „gering" — und
#: mal groß. Wir vereinheitlichen für Filter und Vergleich, behalten den
#: Rohwert aber in `controllability_raw`: Was im Plan steht, bleibt
#: nachlesbar, auch wenn wir es anders einsortieren.
_BEEINFLUSSBARKEIT = {
    "niedrig": "niedrig", "gering": "niedrig",
    "mittel": "mittel", "hoch": "hoch",
}


def normalisiere_beeinflussbarkeit(roh: str | None) -> str | None:
    """„gering"/„Niedrig"/„niedrig" → ``"niedrig"``; Unbekanntes → ``None``.

    Bewusst streng: Mischformen („niedrig - mittel") bekommen keine der drei
    Stufen zugewiesen, weil jede Wahl eine Behauptung wäre. Sie bleiben über
    den Rohwert sichtbar."""
    if not roh:
        return None
    return _BEEINFLUSSBARKEIT.get(roh.strip().strip(".").lower())


def _saeubern(roh: str) -> str | None:
    """Absatz aus dem PDF-Text zu einem lesbaren Satz zusammenziehen.

    Der Text ist an der Satzbreite umbrochen, nicht am Satzende — Zeilenumbrüche
    sind hier also Layout, keine Bedeutung und werden zu Leerzeichen.

    Vom Ende her gelesen: Der gesuchte Absatz steht unmittelbar VOR seinem
    Label; was davor liegt, kann eine Tabelle sein. Zwischen „Wirkungskreis:"
    und „Zielgruppe(n):" steht bei einigen Produkten die ganze Grunddaten-
    Tabelle („Einheit · Ist 2021 · Plan 2022 …", Zeilen wie „PRS 3,46 3,44 …"),
    weil deren Label ausnahmsweise VOR seinem Inhalt steht. Ungefiltert stand
    diese Zahlenwüste als „Zielgruppe" auf der Seite. Deshalb wird nur der
    zusammenhängende Fließtext-Block am Ende übernommen."""
    absatz: list[str] = []
    for zeile in reversed(_ohne_seitenkopf(roh.split("\n"))):
        if not zeile.strip():
            continue
        if _KEIN_FLIESSTEXT.match(zeile):
            break
        absatz.append(zeile)
    text = re.sub(r"\s+", " ", " ".join(reversed(absatz))).strip(" -–—·\t")
    # Zu kurz ist kein Inhalt (etwa ein übrig gebliebener Doppelpunkt), zu lang
    # heißt: Ein Label fehlte und wir haben doch eine Tabelle mitgelesen.
    if not (3 <= len(text) <= 2000):
        return None
    return text


def _steckbrief(block: str) -> dict[str, str | None]:
    """Steckbrief-Felder eines Produktblocks lesen.

    ``block`` reicht vom Produktkopf bis zum Kopf des NÄCHSTEN Produkts. Alles
    ab der ersten Leistungs-Überschrift wird verworfen (Falle 2 oben)."""
    leistung = _LEISTUNG_KOPF.search(block)
    stamm = block[:leistung.start()] if leistung else block

    marken = list(_LABEL.finditer(stamm))
    out: dict[str, str | None] = {name: None for name, _, _ in _STECKBRIEF_FELDER}
    for i, m in enumerate(marken):
        name, rueckwaerts = next(
            ((n, r) for n, muster, r in _STECKBRIEF_FELDER
             if re.fullmatch(muster, m.group(1))), (None, None))
        if name is None or out[name] is not None:
            continue  # unbekanntes Label oder Wiederholung (erster Treffer gilt)
        if rueckwaerts:
            # Inhalt steht VOR dem Label: vom Ende der vorigen Marke bis hierher.
            # Ohne vorige Marke ab Blockanfang — dann steht der Seitenkopf davor,
            # den `_saeubern` entfernt.
            #
            # Und zwar ab dem ZEILENENDE der vorigen Marke, nicht ab dem Label:
            # Trägt die vorige Marke ihren Wert auf derselben Zeile
            # („Verantwortlich: Leitung des Gleichstellungsbüros"), rutscht er
            # sonst vorn in dieses Feld — jede Kurzbeschreibung begänne mit dem
            # Namen der Amtsleitung, jede Zielgruppe mit dem Wirkungskreis.
            beginn = 0
            if i:
                zeilenende = stamm.find("\n", marken[i - 1].end())
                beginn = zeilenende + 1 if zeilenende >= 0 else marken[i - 1].end()
            out[name] = _saeubern(stamm[beginn:m.start()])
        else:
            # Inhalt steht hinter dem Doppelpunkt, auf DERSELBEN Zeile: Ein
            # Umbruch bedeutet hier, dass der Wert fehlt — die nächste Zeile
            # gehört schon zum nächsten Feld.
            zeile = stamm[m.end():].split("\n", 1)[0]
            out[name] = _saeubern(zeile)
    return out


def parse_teilergebnishaushalt(text: str) -> list[dict]:
    """Produkte eines Teilhaushalts-Plans → je Produkt ein dict mit
    ``{sub_budget_no, sub_budget_name, product_no, product_name, office, year, revenues,
    expenses, result}`` für das **Haushaltsjahr** des Dokuments — das
    ist der ERSTE Ansatz im Tabellenkopf; die weiteren Spalten sind die
    mittelfristige Finanzplanung und keine beschlossenen Ansätze.

    Dazu der Steckbrief des Produkts (``short_description``,
    ``legal_basis``, ``controllability`` + ``controllability_raw``,
    ``scope``, ``target_group``), soweit der Plan ihn führt — fehlende
    Felder bleiben ``None``, nichts wird vom Nachbarprodukt übernommen.
    Zu den beiden Fallen dabei siehe den Abschnitt „Produkt-Steckbrief" oben.

    Nur die Summenzeilen (12/20/21) werden gelesen: Die Einzelposten sind im
    PDF-Text oft verschmolzen („355.188334.704“). Die Zahl der Wertespalten
    kommt aus dem Tabellenkopf („Ergebnis 2018 · Ansatz 2019 … Ansatz 2023“) —
    blind die letzte Zahl zu nehmen ginge schief, weil hinter der
    Ergebniszeile die Seitenzahl klebt („−451.635\n601“).

    Beschriftung und Zahlen stehen dabei nicht zwingend auf derselben Zeile;
    seit dem Haushaltsplan 2025 trägt Posten 21 zwei Beschriftungszeilen
    dazwischen. ``_thh_wertezeile`` sucht deshalb vorwärts — aber nur bis zur
    nächsten Tabellenzeile, damit nie die Zahlen des Nachbarpostens an einem
    Produkt kleben.

    Übernommen wird ein Produkt nur, wenn ``Erträge − Aufwendungen =
    ordentliches Ergebnis`` aufgeht."""
    koepfe = list(_PRODUKT_KOPF.finditer(text))
    gefunden: dict[str, dict] = {}
    for i, m in enumerate(koepfe):
        sub_budget_no, sub_budget_name, product_name, product_no, office = m.groups()
        if product_no in gefunden:
            continue  # Fortsetzungsseite desselben Produkts
        # Nur bis zum nächsten Produkt-Kopf lesen: Fehlt einem Produkt die
        # Summenzeile, würden sonst die Werte des FOLGENDEN Produkts gelesen —
        # zwei Produkte trügen dieselben Zahlen (aufgefallen bei „Soziale
        # Beratung" und „Grundsicherung für Arbeitsuchende", beide 54,0 Mio.).
        naechster = koepfe[i + 1] if i + 1 < len(koepfe) else None
        block = text[m.end():naechster.start() if naechster else m.end() + 4000]

        # Der Steckbrief steht ein paar Seiten weiter, hinter den Fortsetzungs-
        # köpfen DESSELBEN Produkts — sein Block reicht deshalb bis zum ersten
        # Kopf eines ANDEREN Produkts. Dieselbe Grenzziehung wie oben, nur eine
        # Ebene weiter: Wer hier am nächstbesten Kopf abschneidet, findet den
        # Steckbrief nie; wer gar nicht abschneidet, holt den des Nachbarn.
        fremd = next((k for k in koepfe[i + 1:] if k.group(4) != product_no), None)
        steckbrief = _steckbrief(text[m.end():fremd.start() if fremd else len(text)])

        # Spalten aus dem Kopf: „Ergebnis JJJJ“ + n × „Ansatz JJJJ“.
        # Das HAUSHALTSJAHR ist der ERSTE Ansatz — die weiteren Spalten sind
        # die mittelfristige Finanzplanung (bis +4 Jahre). Die letzte Spalte
        # zu nehmen hieße, Finanzplanungswerte als Haushaltsansatz auszugeben.
        kopf = re.findall(r"(Ergebnis|Ansatz)\s+(20\d\d)", block[:600])
        years = [int(j) for _, j in kopf]
        if len(years) < 2:
            continue
        spalten = len(years)
        ansatz_idx = next((i for i, (art, _) in enumerate(kopf) if art == "Ansatz"), None)
        if ansatz_idx is None:
            continue

        werte = {}
        for schluessel, muster in (
            ("revenues", r"12\.\s*=?\s*Summe ordentliche\s*Erträge"),
            ("expenses", r"20\.\s*=?\s*Summe ordentliche\s*Aufwendungen"),
            ("result", r"21\.\s*ordentliches Ergebnis"),
        ):
            # Mindestens so viele Werte wie Spalten — alles danach ist
            # Seitenzahl. Zur Suche siehe `_thh_wertezeile`.
            zahlen = _thh_wertezeile(block, muster, spalten)
            if zahlen is None:
                continue
            werte[schluessel] = zahlen[ansatz_idx]
        if len(werte) < 3:
            continue
        # Prüfsumme des Dokuments: Erträge − Aufwendungen = Ergebnis.
        if abs((werte["revenues"] - werte["expenses"]) - werte["result"]) > 1.0:
            continue
        gefunden[product_no] = {
            "sub_budget_no": int(sub_budget_no), "sub_budget_name": sub_budget_name.strip(),
            "product_no": product_no, "product_name": product_name.strip(),
            "office": office.strip(), "year": years[ansatz_idx], **werte,
            **steckbrief,
            "controllability": normalisiere_beeinflussbarkeit(
                steckbrief["controllability_raw"]),
        }
    return list(gefunden.values())
