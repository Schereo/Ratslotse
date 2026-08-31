"""Wie viele Betriebe die Gewerbesteuer aufbringen — die Statistik 73511.

Der Steuer-Steckbrief zeigt seit 08/2026 den Block „Wer zahlt das eigentlich"
(``components/haushalt/wer-zahlt.tsx``). Er erklärt, dass **Namen** unter das
Steuergeheimnis fallen (§ 30 AO), und lässt die naheliegende Anschlussfrage
offen: *wie viele* Betriebe sind es überhaupt? Diese Zahl ist im Gegensatz zum
einzelnen Betrag amtlich veröffentlicht — hier kommt sie her.

Die Quelle
----------
**Gewerbesteuerstatistik** (EVAS 735 11) des Landesamts für Statistik
Niedersachsen, Statistischer Bericht L IV 13. Sie wertet die von den
Finanzämtern festgesetzten Steuermessbescheide aus, dazu die
Zerlegungsbescheide — also die **Veranlagung**, nicht die Kasse. Erhoben ab
1995 dreijährlich, ab Erhebungsjahr 2010 jährlich.

Gelesen werden zwei Blätter derselben Datei:

* **6.1** — kreisfreie Städte und Landkreise, mit der Aufteilung in *reine
  Festsetzungen* (Betrieb nur hier) und *Zerlegungen* (Betriebsstätte eines
  mehrörtigen Unternehmens, § 28 GewStG).
* **6.2** — alle Gemeinden, dafür mit dem **Hebesatz** als Kontrollspalte.

Beide nennen für eine kreisfreie Stadt dieselben drei Zahlen. Das ist keine
Redundanz, sondern die zweite Probe (:func:`probe_blaetter`) — und der
Hebesatz aus 6.2 ist die dritte, denn er steht auch in Tabelle 1105 des
Statistischen Jahrbuchs, die wir längst führen (:func:`probe_hebesatz`).

Was hier NICHT herauskommt — und warum das dokumentiert gehört
--------------------------------------------------------------
Der Wunsch war eine Konzentrationsaussage: „x % der Betriebe tragen y % des
Messbetrags". Die Größenklassen des Gewerbeertrags, aus denen sie fiele,
veröffentlicht die Statistik **nur für das Land und den Bund** (Blätter 1.1,
1.2, 3, 5 und 7 des Berichts; beim Bund die Tabellen 73511-03 ff.). Die
einzige Städte-Tabelle des Bundes führt die „50 Städte mit den höchsten
Steuermessbeträgen" — Platz 50 liegt 2021 bei 35,7 Mio. €, Oldenburg mit
30,0 Mio. € fällt knapp heraus. Je Gemeinde bleiben die drei Merkmale, die
diese Schicht speichert.

Der einzige Weg zu Oldenburger Größenklassen führt über die Einzeldaten des
Forschungsdatenzentrums (Gastwissenschaftsarbeitsplatz oder kontrollierte
Datenfernverarbeitung, wissenschaftliche Vorhaben, mit Antrag). Kein Weg für
dieses Projekt.

**Die Konzentration lässt sich trotzdem belegen, nur anders.** Blatt 6.1
trennt reine Festsetzung und Zerlegung, und der Unterschied ist groß: 2021
trugen in Oldenburg 879 zerlegte Betriebsstätten — 10,4 % aller erfassten
Fälle — 53,0 % des Steuermessbetrags; je zahlendem Fall das 3,5-Fache einer
rein örtlichen Firma. Das ist genau der Weg über die Arbeitslöhne, den der
Block bisher nur beschreiben konnte.

Die Abgrenzung, die neben jeder Zahl stehen muss
------------------------------------------------
**Steuermessbetrag ist nicht Aufkommen**, und der Hebesatz schließt die Lücke
nicht. Gemessen für Oldenburg (Hebesatz durchgehend 439 %), Messbetrag × 4,39
gegen das kassenmäßige Ist-Aufkommen brutto des Realsteuervergleichs:

====  ==============  ==============  ===========
Jahr  Messbetrag×439  Ist brutto      Abstand
====  ==============  ==============  ===========
2019  136.458 T€      132.607 T€      +2,9 %
2020  144.391 T€      113.469 T€      +27,3 %
2021  131.767 T€      150.968 T€      −12,7 %
====  ==============  ==============  ===========

Der Abstand wechselt das Vorzeichen, weil drei verschiedene Dinge gemessen
werden: die **Veranlagung** des Erhebungsjahres (hier), die **Kasse** eines
Kalenderjahres mit Vorauszahlungen, Abschlusszahlungen und Berichtigungen
(Realsteuervergleich) und das **doppische Rechnungsergebnis nach Abzug der
Umlage** (``council_steuern``, Tabelle 1104). Auch die beiden letzten weichen
voneinander ab, 2021 um 16,4 %.

Deshalb: Diese Zahlen kommen in **keine** Kurve mit der Ist-Reihe, und aus
einem Messbetrag wird hier kein „das wären dann xxx Mio. €" gerechnet. Was
die Schicht liefert, ist ein **Nenner** — wie viele Fälle, wie viele davon
zahlen, und wie sich der Messbetrag auf beide Arten verteilt.

Der Verzug gehört dazu
----------------------
Eine Veranlagung ist erst nach den Betriebsprüfungen endgültig; der Bericht
erscheint deshalb rund fünf Jahre später (Berichtsjahr 2019 → August 2024,
2020 → September 2025, 2021 → März 2026). Neben einer Aufkommenskurve bis
2025 steht hier also ein Nenner von 2021. Das ist kein Grund, ihn wegzulassen
— aber einer, es dazuzusagen: :data:`ABGRENZUNG_KURZ` und :data:`ABGRENZUNG`
tun das, und beide reisen mit den Zahlen statt im Frontend zu stehen.

Warum kein eigener XLSX-Leser
-----------------------------
Die Datei ist gebaut wie die des Realsteuervergleichs — dieselbe Behörde,
dasselbe Format, derselbe ausgeschriebene Vorlese-Tabellenkopf, der sagt, in
welcher Zeile er steht. ``council/staedtevergleich.py`` liest das bereits ohne
Fremdpaket; diese Schicht benutzt dieselben Werkzeuge, so wie
``council/steuerkraft.py`` es auch tut. Ein zweiter Leser wäre eine zweite
Stelle, an der derselbe Fehler passieren kann.

Drei Fallen, die dieser Parser bewusst umgeht
---------------------------------------------
1. **Der Städtename wandert.** 2017–2020 heißt die Zeile „Oldenburg
   (Oldenburg), Stadt", 2021 „Oldenburg (Oldb), Stadt". Verbunden wird über
   die Schlüsselnummer — die steht in 6.1 dreistellig („403"), in 6.2
   sechsstellig („403000"); :func:`staedtevergleich.schluessel_normalisieren`
   bringt beides auf dieselbe Form.
2. **Die Spaltenköpfe wandern auch.** 2017–2019 heißt eine Spalte „Betrag der
   Festsetzungen und Zerlegungen … mit positivem Steuermessbetrag in €",
   2020/2021 „Festsetzungen und Zerlegungen …; darunter mit positivem
   Steuermessbetrag in Euro" — ohne „Betrag der", mit Semikola und „Euro"
   statt „€". Auch die Schlüsselspalte wechselt ihren Namen („Regionale
   Gliederung nach AGS" → „Amtlicher Gemeindeschlüssel"). Deshalb wird nicht
   auf ganze Kopftexte verglichen, sondern jede Spalte über **Block und
   Rolle** eingeordnet (:func:`spaltenzuordnung`) — und wenn am Ende nicht
   genau die erwarteten Spalten dastehen, bricht der Lauf ab, statt eine
   falsche zu nehmen.
3. **„g" ist kein Nullwert.** Wo ein einzelner Zahler die Gemeinde dominiert,
   sperrt das LSN den Betrag und druckt „g" (2021: Salzgitter und Wolfsburg).
   Die **Anzahlen stehen trotzdem da**. Ein Parser, der „g" zu 0 macht,
   behauptet, dort werde keine Gewerbesteuer gezahlt. Hier wird der Betrag zu
   ``None`` und die Zeile trägt ``gesperrt``; Oldenburg ist in keinem der fünf
   geprüften Jahrgänge (2017–2021) gesperrt.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from . import staedtevergleich as sv

#: Die beiden Blätter, aus denen gelesen wird. Über alle fünf xlsx-Jahrgänge
#: (2017–2021) heißen sie gleich — anders als beim Realsteuervergleich, dessen
#: Blattnamen zwischen „Tab. 2.1", „GFRV_VÖ_2_1" und „2_1" gewandert sind.
BLATT_KREISE = "6.1"
BLATT_GEMEINDEN = "6.2"

#: Die acht kreisfreien Städte — dieselbe Menge wie beim Städtevergleich und
#: aus demselben Grund importiert statt abgeschrieben.
#:
#: Warum alle acht und nicht nur Oldenburg: Es ist derselbe Schleifendurchlauf,
#: dieselbe Datei und dieselbe Probe. Und die sieben anderen tragen den Fall
#: mit, den Oldenburg nicht hat — die Geheimhaltung (Salzgitter, Wolfsburg).
#: Wer nur Oldenburg speicherte, hätte im Bestand keinen einzigen gesperrten
#: Betrag und merkte nie, ob der Umgang damit stimmt.
STAEDTE = sv.KREISFREIE_STAEDTE
OLDENBURG = sv.OLDENBURG

#: Was diese Zahlen umfassen — in **zwei** Fassungen, und beide reisen mit den
#: Daten über die API statt im Frontend zu stehen (eine Legende, die es in zwei
#: Sprachen gibt, driftet — dieselbe Regel wie bei
#: ``steuertabellen.ABGRENZUNG_1103``).
#:
#: WARUM ZWEI. Die vollständige Fassung ist sechs Zeilen lang und stand bis zum
#: 26.08.2026 ungekürzt unter den drei Zahlen — mehr Kleingedrucktes als
#: Aussage (Tim). Sie bleibt vollständig erhalten, steht auf der Seite aber
#: hinter einem „Was diese Zahlen genau umfassen"; davor steht der eine Satz,
#: ohne den die Zahlen irreführen. Die Aufteilung liegt HIER und nicht im
#: Frontend: Was sichtbar bleiben muss, ist eine Aussage über die Daten und
#: keine über das Layout.
#:
#: :data:`ABGRENZUNG_KURZ` steht immer, :data:`ABGRENZUNG` setzt fort — die
#: beiden wiederholen einander nicht.
ABGRENZUNG_KURZ = (
    "Gezählt wird die Veranlagung des Erhebungsjahres — nicht das Geld, das in "
    "diesem Jahr in der Kasse ankam.")

ABGRENZUNG = (
    "Erfasst sind Betriebe und Betriebsstätten nach dem Sitz, also die Fälle, "
    "für die in Oldenburg Gewerbesteuer erhoben wird — samt der Betriebsstätten "
    "auswärtiger Unternehmen. Der Steuermessbetrag entsteht aus dem "
    "Gewerbeertrag (× 3,5 %); Vorauszahlungen, Abschluss- und "
    "Berichtigungszahlungen verschieben sich dagegen um Jahre. Messbetrag mal "
    "Hebesatz ergibt deshalb nicht das Aufkommen der Kurve oben — in den Jahren "
    "2019 bis 2021 lagen beide zwischen 13 % darunter und 27 % darüber. Die "
    "Statistik erscheint rund fünf Jahre nach dem Erhebungsjahr.")


# --- Der Tabellenkopf: welche Spalte was ist -------------------------------

#: Die drei Blöcke des Blattes 6.1, an ihrer kürzesten eindeutigen Wendung
#: erkannt. Die Reihenfolge entscheidet nicht — die Wendungen überschneiden
#: sich nicht: „Festsetzungen und Zerlegungen von Betrieben und
#: Betriebsstätten" enthält weder „reine Festsetzungen" noch „Zerlegungen von
#: Betriebsstätten" (dort steht „von Betrieben und Betriebsstätten").
BLOECKE: tuple[tuple[str, str], ...] = (
    ("gesamt", r"Festsetzungen und Zerlegungen"),
    ("festsetzung", r"reine[nr]?\s+Festsetzungen"),
    ("zerlegung", r"Zerlegungen von Betriebsstätten"),
)

#: Die neun Wertespalten von Blatt 6.1 — Block × Rolle.
ERWARTET_KREISE: tuple[str, ...] = tuple(
    f"{block}_{role}" for block, _ in BLOECKE
    for role in ("count", "positiv", "amount"))

#: Blatt 6.2 führt nur den Gesamtblock, dafür den Hebesatz.
ERWARTET_GEMEINDEN: tuple[str, ...] = ("gesamt_count", "gesamt_positiv",
                                       "gesamt_amount")


def spaltenzuordnung(spalten: dict[int, str]) -> dict[str, int]:
    """Ausgeschriebener Tabellenkopf → ``{"gesamt_count": 2, …}``.

    Eingeordnet wird über **Block und Rolle**, nicht über den ganzen Kopftext:
    Die Formulierungen haben sich zwischen den Jahrgängen zweimal geändert
    (s. Modulkopf), die Bedeutung nicht. Eine Spalte ist eine *Anzahl*, wenn
    ihr Kopf mit „Anzahl" beginnt, sonst ein *Betrag*; das „darunter mit
    positivem Steuermessbetrag" unterscheidet innerhalb des Blocks die
    zahlenden Fälle von allen.

    **Die Einheit taugt nicht als Merkmal** — das war der erste Versuch. Blatt
    6.1 schreibt „… in €" (2017–2019) bzw. „… in Euro" (2020/2021) hinter den
    Betrag, Blatt 6.2 im Jahrgang 2017 gar nichts. Wer auf die Einheit prüft,
    findet dieselbe Spalte im einen Blatt und im anderen nicht. Geprüft wird
    stattdessen auf „Steuermessbetrag" — das steht in jeder Wertespalte beider
    Blätter — und dagegen, dass es sich um einen Prozentwert handelt (die
    nachrichtliche Hebesatzspalte gehört zu keinem Block, aber eine künftige
    Anteilsspalte könnte es).

    Spalten, die zu keinem Block gehören (Schlüssel, Name, „Zeilenende"),
    fallen still heraus — geprüft wird nicht hier, sondern beim Aufrufer
    gegen :data:`ERWARTET_KREISE` bzw. :data:`ERWARTET_GEMEINDEN`.
    """
    aus: dict[str, int] = {}
    for idx, text in sorted(spalten.items()):
        block = next((name for name, muster in BLOECKE
                      if re.search(muster, text, re.IGNORECASE)), None)
        if block is None:
            continue
        if re.match(r"\s*Anzahl\b", text, re.IGNORECASE):
            role = "positiv" if "positiv" in text.lower() else "count"
        elif "steuermessbetrag" in text.lower() and not re.search(
                r"Prozent|%", text, re.IGNORECASE):
            role = "amount"
        else:
            continue
        # Die erste passende Spalte gewinnt. 2017 wiederholt Blatt 6.1 die
        # Schlüsselspalte am Zeilenende; dieselbe Vorsicht gilt für jede
        # Wiederholungsspalte, die das LSN als Lesehilfe einzieht.
        aus.setdefault(f"{block}_{role}", idx)
    return aus


def _zelle(zeile: list[object], idx: int | None) -> object:
    """Zellwert oder ``None`` — ohne IndexError, denn XLSX-Zeilen enden früh."""
    if idx is None or idx >= len(zeile):
        return None
    return zeile[idx]


def _wert(roh: object) -> tuple[float | None, bool]:
    """Zellwert einer Wertespalte → ``(wert, gesperrt)``.

    Drei Fälle, und der mittlere ist der Grund für diese Funktion:

    * eine Zahl → der Wert;
    * ein Text (das LSN druckt „g") → ``(None, True)``: die Angabe
      unterliegt der Geheimhaltung;
    * leer → ``(None, False)``: da steht nichts, und das ist etwas anderes
      als eine gesperrte Zahl.

    Angewendet auf **alle** Wertespalten, nicht nur auf die Beträge. Der
    Jahrgang 2020 ist der Grund: Dort sind für Salzgitter und Wolfsburg alle
    neun Spalten gesperrt, nicht nur die drei Beträge (2021 dagegen nur die
    Beträge). Eine Erkennung, die nur auf Beträge schaut, hielte die erste
    Zeile für „leer" statt für „gesperrt" — und damit einen Beschluss des
    Landesamts für einen Lesefehler.
    """
    wert = sv._zahl(roh)
    if wert is not None:
        return wert, False
    text = "" if roh is None else str(roh).strip()
    return None, bool(text)


# --- Ein Jahrgang -----------------------------------------------------------

@dataclass
class Gewerbesteuerjahrgang:
    """Ein Erhebungsjahr der Gewerbesteuerstatistik, beide Blätter.

    ``year`` ist das **Erhebungsjahr** der Veranlagung, das die Datei selbst
    im Titel nennt — nicht das Jahr, in dem der Bericht erschien. Zwischen
    beiden liegen rund fünf Jahre, und genau deshalb steht das Erscheinen
    getrennt daneben (:attr:`stand`).
    """

    year: int
    #: „Erschienen im März 2026", aus dem Impressum.
    erschienen: str | None = None
    #: „Korrigierte Fassung vom 11.02.2026", wo es eine gibt (Jahrgang 2020).
    korrektur: str | None = None
    #: Schlüssel → die neun Werte aus Blatt 6.1 plus ``stadt``/``gesperrt``.
    staedte: dict[str, dict] = field(default_factory=dict)
    #: Schlüssel → ``{stadt, gesamt_*, hebesatz, gesperrt}`` aus Blatt 6.2.
    gemeinden: dict[str, dict] = field(default_factory=dict)

    @property
    def stand(self) -> str | None:
        """Was über die gelesene Fassung zu sagen ist, in einem Feld.

        Beides gehört an die Zahl: wann der Bericht erschien (der Verzug ist
        die wichtigste Eigenschaft dieser Statistik) und ob wir eine korrigierte
        Fassung gelesen haben."""
        teile = [t for t in (self.erschienen, self.korrektur) if t]
        return ", ".join(teile) or None


def _kopf(pfad: str) -> tuple[int, str | None, str | None]:
    """Erhebungsjahr, Erscheinen und Korrekturvermerk vom Titel-/Impressumsblatt.

    Das Jahr steht auf dem Titelblatt gleich zweimal — als Berichtsnummer
    („L IV 13 − j / 2021") und im Titel („Gewerbesteuerstatistik 2021").
    Gelesen wird der Titel; die Berichtsnummer ist der Rückfall, denn sie
    trägt ein Sonderzeichen (U+2212, kein Bindestrich), an dem eine
    naheliegende Suche vorbeiläuft.
    """
    year = jahr_nummer = None
    korrektur = None
    for zeile in sv.blatt_lesen(pfad, "Titel"):
        for zelle in zeile:
            text = " ".join(str(zelle or "").split())
            if (m := re.search(r"Gewerbesteuerstatistik\s+(\d{4})", text)):
                year = int(m.group(1))
            if (m := re.search(r"L\s*IV\s*13\s*.\s*j\s*/\s*(\d{4})", text)):
                jahr_nummer = int(m.group(1))
            if (m := re.search(r"(Korrigierte Fassung vom [\d.]+)", text)):
                korrektur = m.group(1)
    year = year or jahr_nummer
    if year is None:
        raise ValueError(f"{pfad}: Auf dem Titelblatt steht kein Erhebungsjahr")

    erschienen = None
    for zeile in sv.blatt_lesen(pfad, "Impressum"):
        for zelle in zeile:
            text = " ".join(str(zelle or "").split())
            if (m := re.search(r"(Erschienen im \w+ \d{4})", text)):
                erschienen = m.group(1)
    return year, erschienen, korrektur


def _blatt(pfad: str, blatt: str, erwartet: tuple[str, ...],
           mit_hebesatz: bool) -> dict[str, dict]:
    """Ein Blatt einlesen und auf die acht kreisfreien Städte einengen."""
    zeilen = sv.blatt_lesen(pfad, blatt)
    if not zeilen:
        raise ValueError(f"{pfad}: Blatt {blatt} ist leer")
    kopf_idx = sv._kopfzeile(zeilen)
    spalten = sv._spalten(zeilen[kopf_idx])
    zuordnung = spaltenzuordnung(spalten)

    fehlend = [name for name in erwartet if name not in zuordnung]
    if fehlend:
        raise ValueError(
            f"{pfad}: Blatt {blatt} trägt nicht die erwarteten Spalten — es "
            f"fehlen {', '.join(fehlend)}. Gefunden wurden "
            f"{sorted(zuordnung)}. Lieber abbrechen als raten, welche Spalte "
            f"gemeint sein könnte.")

    c_key = sv._finde(spalten, r"(Amtlicher Gemeindeschlüssel|Regionale "
                              r"Gliederung nach AGS|Schlüsselnummer)")
    c_name = sv._finde(spalten, r"^(Kreisfreie|Gemeinde)")
    c_hebesatz = sv._finde(spalten, r"Hebesatz") if mit_hebesatz else None
    if c_key is None:
        raise ValueError(f"{pfad}: Blatt {blatt} ohne Schlüsselspalte")
    if mit_hebesatz and c_hebesatz is None:
        raise ValueError(f"{pfad}: Blatt {blatt} ohne Hebesatzspalte")

    aus: dict[str, dict] = {}
    for zeile in zeilen[kopf_idx + 1:]:
        if not zeile:
            continue
        key = sv.schluessel_normalisieren(_zelle(zeile, c_key))
        if key not in STAEDTE:
            continue
        eintrag: dict = {
            "stadt": " ".join(str(_zelle(zeile, c_name) or "").split()),
            "gesperrt": False,
        }
        for name in erwartet:
            wert, gesperrt = _wert(_zelle(zeile, zuordnung[name]))
            eintrag[name] = wert
            eintrag["gesperrt"] = eintrag["gesperrt"] or gesperrt
        if mit_hebesatz:
            eintrag["hebesatz"] = sv._zahl(_zelle(zeile, c_hebesatz))
        aus[key] = eintrag
    return aus


def lies_bericht(pfad: str) -> Gewerbesteuerjahrgang:
    """Einen Statistischen Bericht L IV 13 einlesen (Blätter 6.1 und 6.2)."""
    year, erschienen, korrektur = _kopf(pfad)
    return Gewerbesteuerjahrgang(
        year=year, erschienen=erschienen, korrektur=korrektur,
        staedte=_blatt(pfad, BLATT_KREISE, ERWARTET_KREISE, mit_hebesatz=False),
        gemeinden=_blatt(pfad, BLATT_GEMEINDEN, ERWARTET_GEMEINDEN,
                         mit_hebesatz=True))


# --- Die Proben -------------------------------------------------------------

#: Die drei Größen, die sich aus ihren beiden Teilen zusammensetzen.
_TEILSUMMEN = (("gesamt_count", "festsetzung_count", "zerlegung_count"),
               ("gesamt_positiv", "festsetzung_positiv", "zerlegung_positiv"),
               ("gesamt_amount", "festsetzung_amount", "zerlegung_amount"))


def probe_summen(eintrag: dict) -> dict:
    """Reine Festsetzungen + Zerlegungen = insgesamt — dreimal je Stadt.

    Die Rechnung steht nicht daneben, sie ist der Aufbau der Tabelle: Jeder
    Fall ist entweder eine reine Festsetzung oder eine Zerlegung, und beide
    Spaltengruppen summieren sich auf die dritte. Geht das nicht auf, wurde
    eine Spalte falsch zugeordnet — der einzige Fehler, den diese Datei
    überhaupt zulässt, seit die Kopftexte zweimal umformuliert wurden.

    Ganzzahlen ohne Toleranz: Das LSN rundet hier nichts, die Beträge stehen
    auf den Euro genau da. Wo ein Betrag der Geheimhaltung unterliegt, fällt
    **diese eine** Teilprobe weg (die Anzahlen daneben stehen trotzdem und
    werden geprüft) — sie ist dann nicht bestanden, sondern nicht anwendbar.
    """
    teilproben, fehler = [], []
    for summe, a, b in _TEILSUMMEN:
        werte = [eintrag.get(summe), eintrag.get(a), eintrag.get(b)]
        if any(w is None for w in werte):
            teilproben.append({"groesse": summe, "ok": None,
                               "grund": "gesperrt oder nicht ausgewiesen"})
            continue
        deviation = abs(werte[0] - (werte[1] + werte[2]))
        ok = deviation < 0.5
        teilproben.append({"groesse": summe, "ok": ok, "deviation": deviation})
        if not ok:
            fehler.append(f"{summe}: {werte[0]:.0f} gegen "
                          f"{werte[1]:.0f}+{werte[2]:.0f}")
    gelaufen = [t for t in teilproben if t["ok"] is not None]
    return {"ok": bool(gelaufen) and not fehler,
            "teilproben": teilproben,
            "result": (f"{len(gelaufen)} von 3 Summen nachgerechnet"
                         + (f", ABWEICHUNG: {'; '.join(fehler)}" if fehler else ""))}


def probe_blaetter(budget_year: Gewerbesteuerjahrgang) -> dict:
    """Blatt 6.2 wiederholt für jede kreisfreie Stadt, was Blatt 6.1 sagt.

    Zwei getrennt gelesene Tabellen desselben Berichts, verschieden gebaut
    (die eine mit der Aufteilung nach Festsetzung und Zerlegung, die andere
    mit dem Hebesatz) und trotzdem in den drei gemeinsamen Größen identisch.
    Das prüft nicht die Statistik, sondern **uns**: Hätten wir in einem der
    beiden Blätter die falsche Spalte erwischt, risse dieser Vergleich.
    """
    geprueft, abweichungen = 0, []
    for key, kreis in sorted(budget_year.staedte.items()):
        gemeinde = budget_year.gemeinden.get(key)
        if not gemeinde:
            abweichungen.append({"schluessel": key, "stadt": kreis["stadt"],
                                 "grund": "fehlt in Blatt 6.2"})
            continue
        for name in ERWARTET_GEMEINDEN:
            a, b = kreis.get(name), gemeinde.get(name)
            if a is None and b is None:
                continue
            geprueft += 1
            if a is None or b is None or abs(a - b) >= 0.5:
                abweichungen.append({"schluessel": key, "stadt": kreis["stadt"],
                                     "grund": f"{name}: {a} gegen {b}"})
    return {"ok": geprueft > 0 and not abweichungen,
            "geprueft": geprueft, "abweichungen": abweichungen,
            "result": (f"{geprueft} Werte in beiden Blättern verglichen, "
                         f"{len(abweichungen)} Abweichungen")}


def hebesatz_im_jahr(zeilen: list[dict], year: int,
                     art: str = "Gewerbesteuer") -> float | None:
    """Den Hebesatz eines Jahres aus der Treppe von Tabelle 1105 lesen.

    ``council_hebesaetze`` führt **nur die Änderungsjahre** — ein Satz gilt,
    bis der Rat ihn ändert. Für ein beliebiges Jahr ist der gesuchte Wert
    deshalb der der letzten Änderung davor, nicht der einer Zeile mit diesem
    Jahr: Für 2021 gibt es keine Zeile, es gilt der Satz von 2015 (439 %).
    Wer auf Gleichheit sucht, findet nichts und hielte die Probe für nicht
    durchführbar.
    """
    passend = [z for z in zeilen
               if z.get("art") == art and int(z.get("year", 0)) <= year
               and z.get("hebesatz") is not None]
    if not passend:
        return None
    return float(max(passend, key=lambda z: int(z["year"]))["hebesatz"])


def probe_hebesatz(budget_year: Gewerbesteuerjahrgang, schluessel: str,
                   hebesatz_1105: float | None) -> dict:
    """Der nachrichtliche Hebesatz aus 6.2 gegen Tabelle 1105 des Jahrbuchs.

    Die stärkste Probe dieser Schicht, weil sie das Haus verlässt: Das
    Landesamt schreibt den Hebesatz, den es der Veranlagung zugrunde legt,
    nachrichtlich in seine Gemeindetabelle; die Stadt veröffentlicht denselben
    Satz in ihrem Statistischen Jahrbuch, wo wir ihn seit 08/2026 führen
    (``council_hebesaetze``). Zwei Häuser, zwei Veröffentlichungen, dieselbe
    Zahl — und wenn nicht, ist entweder das Jahr falsch zugeordnet oder die
    Zeile die einer anderen Stadt.

    Ohne Vergleichswert (leerer Bestand, Jahr vor Beginn der Reihe) gilt die
    Probe als nicht gelaufen — nicht als bestanden.
    """
    eintrag = budget_year.gemeinden.get(schluessel) or {}
    satz = eintrag.get("hebesatz")
    if satz is None or hebesatz_1105 is None:
        return {"ok": None,
                "result": ("kein Vergleichswert" if satz is not None
                             else "Blatt 6.2 nennt keinen Hebesatz")}
    ok = abs(satz - hebesatz_1105) < 0.5
    return {"ok": ok,
            "result": (f"Hebesatz {satz:.0f} % (Landesamt) gegen "
                         f"{hebesatz_1105:.0f} % (Jahrbuch 1105) für "
                         f"{budget_year.year}")}


# --- Was in die Datenbank geht ---------------------------------------------

def zeilen(budget_year: Gewerbesteuerjahrgang) -> tuple[list[dict], list[dict]]:
    """Speicherzeilen eines Jahrgangs — und was daran scheiterte.

    Gibt ``(zeilen, verworfen)`` zurück. Eine Stadt, deren Summenprobe nicht
    aufgeht, kommt **gar nicht** herein: lieber eine sichtbare Lücke als eine
    Zahl, die falsch sein könnte. Dieselbe Regel wie beim Städtevergleich.

    Der Hebesatz kommt aus Blatt 6.2 und wird mitgespeichert, obwohl er auch
    in ``council_hebesaetze`` steht. Nicht aus Bequemlichkeit: Er ist die
    Angabe des **Landesamts** zu diesem Erhebungsjahr und damit Teil der
    gelesenen Zeile. Wer später prüfen will, ob beide Häuser dasselbe sagen,
    braucht beide Zahlen — nicht eine und einen Verweis.
    """
    aus: list[dict] = []
    verworfen: list[dict] = []
    for key, eintrag in sorted(budget_year.staedte.items()):
        # Zuerst der Fall, der KEIN Fehler ist: eine Stadt, für die das
        # Landesamt gar nichts ausweist. 2020 trifft das Salzgitter und
        # Wolfsburg — dort steht in allen neun Spalten „g". Das als
        # „Probe gerissen" zu protokollieren wäre falsch: Nichts widerspricht
        # sich, es steht nur nichts da. Der Unterschied gehört ins Protokoll,
        # sonst sucht beim nächsten Lauf jemand einen Parserfehler, den es
        # nicht gibt.
        if eintrag.get("gesamt_count") is None and eintrag.get("gesperrt"):
            verworfen.append({"schluessel": key, "stadt": eintrag["stadt"],
                              "grund": "Geheimhaltung",
                              "result": "das Landesamt weist für diese Stadt "
                                          "keine Zahlen aus (§ 16 BStatG)"})
            continue
        probe = probe_summen(eintrag)
        if not probe["ok"]:
            verworfen.append({"schluessel": key, "stadt": eintrag["stadt"],
                              "grund": "Summenprobe",
                              "result": probe["result"]})
            continue
        gemeinde = budget_year.gemeinden.get(key) or {}
        aus.append({
            "year": budget_year.year,
            "schluessel": key,
            # Der Name aus unserer Liste, nicht der aus der Datei: Die Datei
            # schreibt ihn je Jahrgang anders („Oldenburg (Oldb)" gegen
            # „Oldenburg (Oldenburg)"), und eine Reihe, die ihren eigenen
            # Namen wechselt, sieht in jeder Anzeige nach zwei Städten aus.
            "stadt": STAEDTE[key],
            "faelle": eintrag["gesamt_count"],
            "cases_positive": eintrag["gesamt_positiv"],
            "tax_base_eur": eintrag["gesamt_amount"],
            "festsetzungen": eintrag["festsetzung_count"],
            "assessments_positive": eintrag["festsetzung_positiv"],
            "assessment_tax_base_eur": eintrag["festsetzung_amount"],
            "apportionments": eintrag["zerlegung_count"],
            "apportionments_positive": eintrag["zerlegung_positiv"],
            "apportioned_assessment_eur": eintrag["zerlegung_amount"],
            "hebesatz": gemeinde.get("hebesatz"),
            "gesperrt": bool(eintrag.get("gesperrt")),
        })
    return aus, verworfen
