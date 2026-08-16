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


def _tabellenkopf(kopf: str, jahr: int) -> dict | None:
    """Aus dem Tabellenkopf lesen, welche Spalten es gibt und in welcher
    Reihenfolge — die Grundlage für alles Weitere.

    Liefert ``{positionen, varianten, hat_vorjahr}``. ``varianten`` sind die
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
    finde("vorjahr", r"Ergebnis des Vorjahres", rf"Ergebnis {jahr - 1}")
    finde("ansatz", r"Ansätze des Haushaltsjahres", r"Ansätze des Haushaltsplanes",
          rf"Ansätze? {jahr}", r"Ansätze des", r"\bAnsatz\b")
    finde("nachtrag", r"Veränderung durch\s*Nachtrag", r"\bNachtrag\b")
    finde("gesamtermaechtigung", r"Gesamtermächtigung")
    finde("ergebnis", r"Ergebnis des Haushaltsjahres", rf"Ergebnis {jahr}")
    finde("abweichung", r"mehr \(\+\)", r"Differenz", r"Abweichung", r"Vergleich")

    if "ergebnis" not in positionen or "abweichung" not in positionen:
        return None

    varianten: list[str] = []
    # Die Gesamtermächtigung ist der spezifischste Bezug: Wo der Kopf sie
    # führt (2018), ist sie die Spalte direkt vor dem Ergebnis.
    if "gesamtermaechtigung" in positionen:
        varianten.append("gesamtermaechtigung")
    if "ansatz" in positionen and "nachtrag" in positionen:
        varianten.append("ansatz_nachtrag")
    if "ansatz" in positionen:
        varianten.append("ansatz")
    if not varianten:
        return None
    return {"positionen": positionen, "varianten": tuple(varianten),
            "hat_vorjahr": "vorjahr" in positionen}


def _plan_zuerst(kopf: dict, art: str) -> bool:
    """Steht die Plan-Spalte im Kopf vor der Ergebnis-Spalte? 2017 nicht —
    dort lautet die Reihenfolge Vorjahr, Ergebnis, Ansatz, Differenz."""
    spalte = "gesamtermaechtigung" if art == "gesamtermaechtigung" else "ansatz"
    return kopf["positionen"][spalte] < kopf["positionen"]["ergebnis"]


def parse_ergebnisrechnung(text: str, jahr: int) -> list[dict]:
    """Ergebnisrechnung der Kernverwaltung aus dem Jahresabschluss-Volltext.

    Liefert je Posten ``{nr, bezeichnung, vorjahr, ansatz, ergebnis,
    abweichung}`` in Euro. ``ansatz`` ist der Planwert des Jahres,
    ``ergebnis`` das tatsächliche Ergebnis — genau das Paar, aus dem
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

    return _posten_aus_block(block, jahr)


def _posten_aus_block(block: str, jahr: int) -> list[dict]:
    """Die Posten einer Ergebnisrechnungs-Tabelle lesen — gemeinsam genutzt
    von der Gesamtrechnung und den Teil-Ergebnisrechnungen je Teilhaushalt,
    die dieselbe Tabellenform haben.

    Jeder Abschnitt trägt seinen eigenen Kopf; er steht vor der ersten
    Zwischenüberschrift („Ordentliche Erträge")."""
    schnitt = re.search(r"[Oo]rdentliche Erträge", block)
    kopf = _tabellenkopf(block[:schnitt.start()] if schnitt else block[:900], jahr)
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
    for nr, bezeichnung in ERGEBNIS_POSTEN.items():
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
        out.append({"nr": nr, "bezeichnung": bezeichnung, "jahr": jahr,
                    "ist_summe": 1 if nr in SUMMEN_POSTEN else 0, **werte})
    return out


#: Kopf einer Teil-Ergebnisrechnung: „A. Teil-Ergebnisrechnung THH01 Name".
#: Die Schreibweise schwankt zwischen den Jahrgängen, und im Jahresabschluss
#: 2022 fällt bei THH09 sogar ein Zeilenumbruch mitten hinein („A. Teil\n
#: -Ergebnisrechnung THH09"). Ohne den Umbruch im Muster fand der Parser dort
#: nur die Fortsetzungsseite ab Posten 21, zählte den Teilhaushalt nicht mit
#: und verwarf die ganze Ebene über die Summenprobe (4,1 % Abweichung).
#: Deshalb rund um den Bindestrich beliebiger Leerraum.
_THH_ABSCHNITT = re.compile(r"Teil\s*-?\s*Ergebnisrechnung\s+THH\s?(\d\d)\s*([^\n]{0,60})")


def parse_teilergebnisrechnungen(text: str, jahr: int) -> list[dict]:
    """Teil-Ergebnisrechnungen je Teilhaushalt aus dem Jahresabschluss.

    Liefert dieselben Posten wie ``parse_ergebnisrechnung``, zusätzlich mit
    ``thh_nr`` und ``thh_name`` — die Grundlage für „geplant gegen
    tatsächlich" je Bereich (Design H-16).

    Je Teilhaushalt stehen im Dokument mehrere Abschnitte (Ergebnis-, dann
    Finanzrechnung, dazu Fortsetzungsseiten). Genommen wird der erste, der
    beide Summenzeilen (12 und 20) liefert — so landet nie die Finanzrechnung
    in der Ergebnis-Tabelle."""
    treffer: dict[int, dict] = {}
    stellen = list(_THH_ABSCHNITT.finditer(text))
    for i, m in enumerate(stellen):
        thh_nr = int(m.group(1))
        if thh_nr in treffer:
            continue
        # Bis zum nächsten Abschnitt lesen, damit keine Werte des folgenden
        # Teilhaushalts hineinrutschen.
        ende = stellen[i + 1].start() if i + 1 < len(stellen) else m.end() + 9000
        posten = _posten_aus_block(text[m.end():ende], jahr)
        nummern = {p["nr"] for p in posten}
        if not {12, 20} <= nummern:
            continue  # kein vollständiger Ergebnis-Abschnitt
        name = re.sub(r"^\s*(THH\s?\d\d)?\s*", "", m.group(2)).strip(" -–—:")
        treffer[thh_nr] = {"thh_nr": thh_nr, "thh_name": name, "posten": posten}
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
        for feld in ("plan", "ergebnis"):
            ganz = next((p.get(feld) for p in gesamt if p["nr"] == nr), None)
            if not ganz:
                return False, 1.0
            teil = sum(next((p.get(feld) for p in x["posten"] if p["nr"] == nr), 0) or 0
                       for x in teilhaushalte)
            schlimmste = max(schlimmste, abs(teil - ganz) / abs(ganz))
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
    for feld in ("plan", "ergebnis"):
        werte = [nach_nr[n].get(feld) for n in (12, 20, 21)]
        if any(w is None for w in werte):
            return False, f"{feld}: Wert fehlt"
        rest = (werte[0] - werte[1]) - werte[2]
        if abs(rest) > toleranz:
            return False, f"{feld}: 12 − 20 − 21 = {rest:+.2f} €"
    return True, ""


def vorjahreskette(je_jahr: dict[int, list[dict]],
                   toleranz: float = _TOLERANZ) -> list[tuple[int, int, str]]:
    """Vierte Absicherung, über Dokumentgrenzen hinweg: Das Ist eines Jahres
    taucht im Folgejahrgang als Vorjahresspalte wieder auf.

    Geprüft werden die Summenzeilen 12 und 20 jedes benachbarten Paares.
    Zurück kommt die Liste der **gerissenen** Glieder als
    ``(jahr, folgejahr, begruendung)`` — leer heißt: alles schließt.

    Weil ein gerissenes Glied nicht verrät, welche der beiden Seiten falsch
    gelesen wurde, verliert der Aufrufer beide. Das ist die konservative
    Lesart und entspricht dem Grundsatz dieses Moduls: lieber eine Lücke als
    eine Zahl, die niemand nachrechnen kann."""
    kaputt: list[tuple[int, int, str]] = []
    for jahr in sorted(je_jahr):
        folge = jahr + 1
        if folge not in je_jahr:
            continue
        vorher = {p["nr"]: p for p in je_jahr[jahr]}
        nachher = {p["nr"]: p for p in je_jahr[folge]}
        for nr in (12, 20):
            ist = vorher.get(nr, {}).get("ergebnis")
            genannt = nachher.get(nr, {}).get("vorjahr")
            if ist is None or genannt is None:
                kaputt.append((jahr, folge, f"Posten {nr}: Wert fehlt"))
            elif abs(ist - genannt) > toleranz:
                kaputt.append((jahr, folge,
                               f"Posten {nr}: Ist {ist:,.2f} ≠ Vorjahresspalte "
                               f"{genannt:,.2f}"))
    return kaputt


def _fenster(zahlen: list[float], kopf: dict, art: str) -> tuple | None:
    """Das Fenster in der Zahlenfolge suchen, das die Rechenprobe der
    jeweiligen Bezugsgröße erfüllt.

    Zurück kommt ``(plan, ergebnis, abweichung, start_index, repariert)``.

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
    mindest = 1 if kopf["hat_vorjahr"] else 0
    plan_zuerst = _plan_zuerst(kopf, art)
    breite = 4 if art == "ansatz_nachtrag" else 3
    if art == "ansatz_nachtrag" and not plan_zuerst:
        return None  # Nachtragsspalte gibt es nur in der Ansatz-zuerst-Form
    exakt = repariert = None
    for i in range(mindest, len(zahlen) - breite + 1):
        if art == "ansatz_nachtrag":
            ansatz, nachtrag, ergebnis, abweichung = zahlen[i:i + 4]
            if nachtrag == 0:
                continue  # leere Nachtragsspalte → das ist der einfache Fall
            plan = ansatz + nachtrag
        else:
            a, b, abweichung = zahlen[i:i + 3]
            plan, ergebnis = (a, b) if plan_zuerst else (b, a)
        if abs((ergebnis - plan) - abweichung) <= _TOLERANZ:
            exakt = (plan, ergebnis, abweichung, i, False)
        elif (abs((ergebnis - plan) + abweichung) <= _TOLERANZ_VORZEICHEN
                and abweichung and ergebnis and plan):
            # Im Dokument fehlt das Minuszeichen (gesehen 2020, Summenzeile 20
            # des Schlussberichts). Nur reparieren, wenn der Betrag auf den
            # Cent passt — und nur bei einem echten Tripel: Ohne die
            # Null-Bedingung erfüllt jedes „X | 0,00 | X" diese Probe, was im
            # Jahresabschluss 2018 einen ganzen Teilhaushalt mit einem Ist von
            # 0,00 € eingetragen hätte (THH11, richtig sind 105,0 Mio. €).
            repariert = (plan, ergebnis, ergebnis - plan, i, True)
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
        plan, ergebnis, abweichung, start, repariert = gefunden
        vorjahr = zahlen[0] if kopf["hat_vorjahr"] else None
        if art == "ansatz_nachtrag":
            ansatz = zahlen[start]          # Nachtrag steht direkt dahinter
        elif art == "gesamtermaechtigung" and kopf["hat_vorjahr"] and start >= 2:
            # Der Kopf führt als zweite Spalte den Ansatz; die Zwischenspalten
            # (Nachtrag, sonstige Ermächtigungen, Übertragungen) dürfen leer
            # sein, die beiden ersten sind es nie.
            ansatz = zahlen[1]
        else:
            ansatz = plan
        return {"vorjahr": vorjahr, "ansatz": ansatz, "plan": plan,
                "plan_art": art, "ergebnis": ergebnis, "abweichung": abweichung,
                "vorzeichen_repariert": repariert}
    return None


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


def parse_abweichungsgruende(text: str, jahr: int) -> list[dict]:
    """Abschnitt 6.3.1 des Jahresabschlusses: **warum** ein Posten vom Plan
    abweicht, je Posten und in den Worten der Verwaltung.

    Liefert je Posten ``{nr, bezeichnung, delta_mio, prozent, text}``.
    ``delta_mio`` und ``prozent`` sind die Werte, die die Überschrift selbst
    nennt — sie sind die Eintrittskarte: Erst der Abgleich mit der geparsten
    Tabellenzeile (``pruefe_abweichungsgruende``) entscheidet, ob die
    Erläuterung übernommen wird.

    Der Abschnitt existiert zweimal je Dokument — einmal für die Ergebnis-,
    einmal für die Finanzrechnung. Gesucht ist die Ergebnisrechnung; erkannt
    wird sie am entzifferten Überschrifts-Rest, nicht an der Reihenfolge."""
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
            "jahr": jahr, "nr": nr,
            "bezeichnung": " ".join(m.group(2).split()),
            "delta_mio": _eur_lose(m.group(4)) * vorzeichen,
            "prozent": _eur_lose(m.group(6)) * vz_prozent,
            "text": _fliesstext(gewaehlt[m.end():ende]),
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
        if not p or p.get("abweichung") is None:
            abgelehnt.append(f"Posten {g['nr']}: keine passende Tabellenzeile")
            continue
        ist_mio = p["abweichung"] / 1e6
        if abs(ist_mio - g["delta_mio"]) > toleranz_mio:
            abgelehnt.append(
                f"Posten {g['nr']}: Text {g['delta_mio']:+.1f} Mio. ≠ Tabelle {ist_mio:+.2f} Mio.")
            continue
        plan = p.get("plan")
        if plan:
            ist_prozent = p["abweichung"] / plan * 100
            if abs(ist_prozent - g["prozent"]) > toleranz_prozent:
                abgelehnt.append(
                    f"Posten {g['nr']}: Text {g['prozent']:+.2f} % ≠ Tabelle {ist_prozent:+.2f} %")
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

    Liefert ``{jahr, lesbar, buchstabenanteil}`` oder ``None``. Gesucht wird
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
    return {"jahr": int(treffer.group(1)), "lesbar": anteil >= _TEXT_MINDESTANTEIL,
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


def parse_teilergebnishaushalt(text: str) -> list[dict]:
    """Produkte eines Teilhaushalts-Plans → je Produkt ein dict mit
    ``{thh_nr, thh_name, produkt_nr, produkt_name, amt, jahr, ertraege,
    aufwendungen, ergebnis}`` für das **Haushaltsjahr** des Dokuments — das
    ist der ERSTE Ansatz im Tabellenkopf; die weiteren Spalten sind die
    mittelfristige Finanzplanung und keine beschlossenen Ansätze.

    Nur die Summenzeilen (12/20/21) werden gelesen: Die Einzelposten sind im
    PDF-Text oft verschmolzen („355.188334.704“). Die Zahl der Wertespalten
    kommt aus dem Tabellenkopf („Ergebnis 2018 · Ansatz 2019 … Ansatz 2023“) —
    blind die letzte Zahl zu nehmen ginge schief, weil hinter der
    Ergebniszeile die Seitenzahl klebt („−451.635\n601“).

    Übernommen wird ein Produkt nur, wenn ``Erträge − Aufwendungen =
    ordentliches Ergebnis`` aufgeht."""
    gefunden: dict[str, dict] = {}
    for m in _PRODUKT_KOPF.finditer(text):
        thh_nr, thh_name, produkt_name, produkt_nr, amt = m.groups()
        if produkt_nr in gefunden:
            continue  # Fortsetzungsseite desselben Produkts
        # Nur bis zum nächsten Produkt-Kopf lesen: Fehlt einem Produkt die
        # Summenzeile, würden sonst die Werte des FOLGENDEN Produkts gelesen —
        # zwei Produkte trügen dieselben Zahlen (aufgefallen bei „Soziale
        # Beratung" und „Grundsicherung für Arbeitsuchende", beide 54,0 Mio.).
        naechster = _PRODUKT_KOPF.search(text, m.end())
        block = text[m.end():naechster.start() if naechster else m.end() + 4000]

        # Spalten aus dem Kopf: „Ergebnis JJJJ“ + n × „Ansatz JJJJ“.
        # Das HAUSHALTSJAHR ist der ERSTE Ansatz — die weiteren Spalten sind
        # die mittelfristige Finanzplanung (bis +4 Jahre). Die letzte Spalte
        # zu nehmen hieße, Finanzplanungswerte als Haushaltsansatz auszugeben.
        kopf = re.findall(r"(Ergebnis|Ansatz)\s+(20\d\d)", block[:600])
        jahre = [int(j) for _, j in kopf]
        if len(jahre) < 2:
            continue
        spalten = len(jahre)
        ansatz_idx = next((i for i, (art, _) in enumerate(kopf) if art == "Ansatz"), None)
        if ansatz_idx is None:
            continue

        werte = {}
        for schluessel, muster in (
            ("ertraege", r"12\.\s*=?\s*Summe ordentliche\s*Erträge([^\n]*(?:\n[^\n]*)?)"),
            ("aufwendungen", r"20\.\s*=?\s*Summe ordentliche\s*Aufwendungen([^\n]*(?:\n[^\n]*)?)"),
            ("ergebnis", r"21\.\s*ordentliches Ergebnis([^\n]*(?:\n[^\n]*)?)"),
        ):
            mm = re.search(muster, block)
            if not mm:
                continue
            zahlen = _thh_zahlen(mm.group(1))
            # Genau so viele Werte wie Spalten — alles danach ist Seitenzahl.
            if len(zahlen) < spalten:
                continue
            werte[schluessel] = zahlen[ansatz_idx]
        if len(werte) < 3:
            continue
        # Prüfsumme des Dokuments: Erträge − Aufwendungen = Ergebnis.
        if abs((werte["ertraege"] - werte["aufwendungen"]) - werte["ergebnis"]) > 1.0:
            continue
        gefunden[produkt_nr] = {
            "thh_nr": int(thh_nr), "thh_name": thh_name.strip(),
            "produkt_nr": produkt_nr, "produkt_name": produkt_name.strip(),
            "amt": amt.strip(), "jahr": jahre[ansatz_idx], **werte,
        }
    return list(gefunden.values())
