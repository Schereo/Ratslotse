"""Die dritte Komponente des Finanzausgleichs — und warum sie gefehlt hat.

Was in `council_steuerkraft` steht, ist **nicht** alles
--------------------------------------------------------
Der Open-Data-Datensatz 1106 der Stadt führt eine Spalte
„Schluesselzuweisungen, Anordnungssoll". Nachgemessen (17.08.2026) enthält sie
**exakt** die Summe aus zwei der drei Komponenten des kommunalen
Finanzausgleichs:

===============  ==========  ==========  ============  =========
Ausgleichsjahr   Gemeinde-   Kreis-      = Datensatz    Netto
                 aufgaben    aufgaben    1106           (LSN)
===============  ==========  ==========  ============  =========
2025             51.653      17.557      69.210 ✓       79.785
2026             62.654      19.624      82.278 ✓       93.438
===============  ==========  ==========  ============  =========

Die Differenz ist die dritte Komponente: **Zuweisungen für Aufgaben des
übertragenen Wirkungskreises** (10.575 T€ für 2025, 11.160 T€ für 2026) — das
Geld, das die Stadt dafür bekommt, dass sie staatliche Aufgaben erledigt
(Standesamt, Einwohnermeldewesen, Ausländerbehörde, Bauaufsicht). Sie steht in
keiner städtischen Veröffentlichung, die wir einlesen; sie steht beim Land.

Deshalb ist die Zahl auf unseren Seiten bisher **zu niedrig**: um 10.575 T€
für 2025 und 11.160 T€ für 2026 — auf den gezeigten Betrag bezogen 15,3 %
bzw. 13,6 %, gemessen am vollständigen Ausgleich 13,3 % bzw. 11,9 %. Welche
Bezugsgröße man nimmt, ändert nichts am Befund: Das ist kein Rundungsfehler,
das ist eine fehlende Zeile.

Die Quelle
----------
Landesamt für Statistik Niedersachsen, „Kommunaler Finanzausgleich …,
Ergebnis- und Vergleichstabellen KSV" (XLSX), Blatt ``9a`` — die acht
kreisfreien Städte, Schlüssel-Nr. ``403`` ist Oldenburg. Dieselbe Datei, aus
der ``council/staedtevergleich.py`` schon die Steuerkraftmesszahlen liest
(Blatt ``ST_KR_MESS_VGL``); dieses Modul ergänzt nur das zweite Blatt.

Die Download-Nummern des LSN wechseln jährlich (``/download/227086``) und sind
nicht vorhersagbar — sie stehen auf der Übersichtsseite und werden dort
gelesen, nie hier verdrahtet.

Zwei Proben, und die zweite ist die interessante
------------------------------------------------
1. **Im Dokument** (:func:`probe_komponenten`): Gemeindeaufgaben +
   Kreisaufgaben + übertragener Wirkungskreis − Finanzausgleichsumlage ergibt
   den Nettobetrag, den dieselbe Zeile ausweist. Für alle acht Städte und
   beide Jahre, die eine Datei führt.
2. **Gegen die Bücher der Stadt** (:func:`probe_gegen_jahrbuch`): Die Summe
   der drei Komponenten muss die Zeile „Finanzzuweisungen" in Tabelle 1103 des
   Statistischen Jahrbuchs treffen. Gemessen für das Haushaltsjahr 2025:
   **79.785 T€** (LSN) gegen **79.787 T€** (Jahrbuch, vorläufiges
   Rechnungsergebnis) — 2 T€ Abstand auf 79,8 Mio. €, also 0,0025 %.

   Warum überhaupt eine Toleranz und nicht null: Die beiden Zahlen sind nicht
   dieselbe Messung. Das LSN nennt den **Festsetzungsbetrag** des
   Ausgleichsjahres, die Stadt ihr **Rechnungsergebnis** — was in ihrer Kasse
   angekommen ist. Zwischen beiden liegen unterjährige Korrekturen und
   Rundungen auf volle Tausend. :data:`JAHRBUCH_TOLERANZ` ist deshalb 0,5 %
   und nicht 0: enger wäre eine Behauptung über Buchungspraxis, weiter würde
   ein echter Zuordnungsfehler durchrutschen (die kleinste Komponente ist mit
   11 Mio. € rund 13 % der Summe — sie zu vergessen fiele bei 0,5 % sofort auf).

Die Falle, die dieser Parser umgeht
------------------------------------
**Spaltenpositionen sind keine Zusage.** Zwischen den Ausgaben ändert sich der
Aufbau: Die Ausgabe 2023 schreibt die Schlüsselnummer sechsstellig
(``403000``), die Ausgabe 2026 dreistellig (``403``); die Kopfzeile 2023 nennt
„Euro je Einwohner/Einwohnerin", die 2026 „Euro je Einwohnerin/Einwohner" —
dieselbe Spalte, andere Reihenfolge. Gelesen wird deshalb ausschließlich über
den **ausgeschriebenen Tabellenkopf**, den das LSN als Vorlesehilfe für
Screenreader mitliefert und dessen Zeilennummer die Datei in ihren ersten
Zeilen selbst nennt. Die Mechanik dafür steht in ``council/staedtevergleich.py``
und wird hier benutzt, nicht kopiert.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from . import staedtevergleich as sv

#: Die drei Komponenten und die Umlage, wie der Tabellenkopf sie nennt →
#: unser Kennzahl-Name. Gematcht wird gegen den ausgeschriebenen Kopftext,
#: nicht gegen die Spaltennummer (s. Modulkopf).
KOMPONENTEN: dict[str, str] = {
    r"Schlüsselzuweisungen\s+für\s+Gemeindeaufgaben": "zuweisungen_gemeindeaufgaben",
    r"Schlüsselzuweisungen\s+für\s+Kreisaufgaben": "zuweisungen_kreisaufgaben",
    r"Zuweisungen\s+für\s+Aufgaben\s+des\s+übertragenen\s+Wirkungskreises":
        "zuweisungen_uebertragener_wirkungskreis",
    r"Finanzausgleichsumlage": "finanzausgleichsumlage",
}

#: Wie viel die Summe der drei Komponenten vom Jahrbuch-Wert abweichen darf.
#: Die Begründung steht im Modulkopf — kurz: Festsetzung gegen
#: Rechnungsergebnis, gemessener Abstand 0,0025 %.
JAHRBUCH_TOLERANZ = 0.005

#: Die Komponente, um die es geht. Als Konstante, weil sie an drei Stellen
#: auftaucht (Parser, Probe, Frontend-Text) und ein Tippfehler dort still
#: bliebe.
UEBERTRAGEN = "zuweisungen_uebertragener_wirkungskreis"

#: Was die Komponente ist, in einem Satz, der neben der Zahl stehen kann.
#: Nicht optional: „Zuweisungen für Aufgaben des übertragenen Wirkungskreises"
#: sagt niemandem etwas, der nicht Kommunalrecht studiert hat.
UEBERTRAGEN_ERKLAERT = (
    "Geld des Landes dafür, dass die Stadt staatliche Aufgaben miterledigt — "
    "Standesamt, Melde- und Ausländerwesen, Bauaufsicht. Es ist an diese "
    "Aufgaben gebunden und steht der Stadt nicht frei zur Verfügung.")


@dataclass
class KfaZuweisungen:
    """Ein Ausgleichsjahr aus Blatt ``9a`` — die acht kreisfreien Städte."""

    jahr: int
    stand: str | None
    #: Schlüssel (sechsstellig) → {stadt, zuweisungen_*, nettobetrag,
    #: nettobetrag_je_ew}. Alle Beträge in **Tausend Euro**, wie im Blatt.
    staedte: dict[str, dict] = field(default_factory=dict)


def _jahresspalten(spalten: dict[int, str]) -> dict[int, dict[str, int]]:
    """Kopfzeile → ``{jahr: {kennzahl: spaltenindex}}``.

    Eine Datei führt **zwei** Ausgleichsjahre nebeneinander; welche Spalte zu
    welchem Jahr gehört, sagt der Kopftext („… im Jahr 2026 …"). Genau das ist
    der Grund, aus dem hier nicht gezählt, sondern gelesen wird.
    """
    aus: dict[int, dict[str, int]] = {}
    for i, text in sorted(spalten.items()):
        jahr_treffer = re.search(r"im\s+Jahr\s+(\d{4})", text)
        if not jahr_treffer:
            continue
        jahr = int(jahr_treffer.group(1))
        # Der Nettobetrag ZUERST, und das ist kein Stilfrage: Sein Kopftext
        # lautet „… abzüglich der Finanzausgleichsumlage im Jahr 2025)" und
        # enthält damit den Namen einer Komponente. Andersherum geprüft würden
        # die beiden Netto-Spalten als Umlage durchgehen, und der Parser
        # meldete stumm eine Datei ohne Nettobetrag.
        if re.search(r"Nettobetrag.*Summe", text, re.IGNORECASE | re.DOTALL):
            # Zweimal je Jahr: in Tausend Euro und je Einwohner*in.
            # Unterschieden über die Betragsangabe und NICHT über die
            # Reihenfolge — die Ausgabe 2023 schreibt „Einwohner/Einwohnerin",
            # die 2026 „Einwohnerin/Einwohner".
            if re.search(r"Beträge\s+in\s+1[\s.]?000\s+Euro", text, re.IGNORECASE):
                aus.setdefault(jahr, {}).setdefault("nettobetrag", i)
            elif re.search(r"je\s+Einwohner", text, re.IGNORECASE):
                aus.setdefault(jahr, {}).setdefault("nettobetrag_je_ew", i)
            continue
        for muster, name in KOMPONENTEN.items():
            if re.search(muster, text, re.IGNORECASE):
                aus.setdefault(jahr, {}).setdefault(name, i)
                break
    return aus


def lies_zuweisungen(pfad: str) -> list[KfaZuweisungen]:
    """Blatt ``9a`` einer KFA-Datei einlesen → beide Ausgleichsjahre.

    Die Reihenfolge ist aufsteigend nach Jahr; das jüngere ist das, um das es
    der Ausgabe geht, das ältere die mitgelieferte Vergleichsspalte.
    """
    zeilen = sv.blatt_lesen(pfad, "9a")
    if not zeilen:
        raise ValueError(f"{pfad}: Blatt 9a ist leer")
    kopf_idx = sv._kopfzeile(zeilen)
    spalten = sv._spalten(zeilen[kopf_idx])

    c_key = sv._finde(spalten, r"Schlüsselnummer")
    c_name = sv._finde(spalten, r"Bezeichnung")
    jahre = _jahresspalten(spalten)
    vollstaendig = {j: s for j, s in jahre.items()
                    if set(KOMPONENTEN.values()) <= set(s) and "nettobetrag" in s}
    if c_key is None or c_name is None or len(vollstaendig) < 1:
        raise ValueError(
            f"{pfad}: Blatt 9a trägt nicht die erwarteten Spalten "
            f"(gefunden: {sorted(spalten.values())[:4]}…). Lieber abbrechen als "
            f"über Spaltenpositionen raten.")

    stand = None
    for zeile in zeilen[:6]:
        for zelle in zeile:
            if (m := re.search(r"Stand:\s*([\d.]+)", str(zelle or ""))):
                stand = m.group(1)

    aus: list[KfaZuweisungen] = []
    for jahr in sorted(vollstaendig):
        jahrgang = KfaZuweisungen(jahr=jahr, stand=stand)
        for zeile in zeilen[kopf_idx + 1:]:
            if not zeile or c_key >= len(zeile):
                continue
            key = sv.schluessel_normalisieren(zeile[c_key])
            if not key or key not in sv.KREISFREIE_STAEDTE:
                # Blatt 9a führt nur die acht kreisfreien Städte; alles andere
                # sind Zwischenüberschriften und Summenzeilen.
                continue
            werte = {name: sv._zahl(zeile[i]) if i < len(zeile) else None
                     for name, i in vollstaendig[jahr].items()}
            if werte.get("nettobetrag") is None:
                continue
            werte["stadt"] = " ".join(str(zeile[c_name] or "").split())
            jahrgang.staedte[key] = werte
        if jahrgang.staedte:
            aus.append(jahrgang)
    return aus


def probe_komponenten(jahrgang: KfaZuweisungen) -> dict:
    """Die Probe im Dokument: Die drei Komponenten minus Umlage ergeben Netto.

    Rundung: Das Blatt führt volle Tausend Euro, deshalb ist ein Abstand von
    1 T€ je Zeile zulässig — mehr wäre keine Rundung mehr, sondern eine
    vergessene oder doppelt gezählte Spalte.
    """
    abweichungen = []
    for key, w in sorted(jahrgang.staedte.items()):
        teile = [w.get("zuweisungen_gemeindeaufgaben"),
                 w.get("zuweisungen_kreisaufgaben"), w.get(UEBERTRAGEN)]
        if any(t is None for t in teile) or w.get("nettobetrag") is None:
            abweichungen.append({"schluessel": key, "stadt": w.get("stadt"),
                                 "grund": "Komponente fehlt"})
            continue
        summe = sum(teile) - (w.get("finanzausgleichsumlage") or 0)
        if abs(summe - w["nettobetrag"]) > 1:
            abweichungen.append({"schluessel": key, "stadt": w.get("stadt"),
                                 "grund": f"{summe:.0f} statt {w['nettobetrag']:.0f} T€"})
    n = len(jahrgang.staedte)
    return {"geprueft": n, "abweichungen": abweichungen, "ok": not abweichungen,
            "ergebnis": (f"{n - len(abweichungen)} von {n} Städten: "
                         f"Gemeinde- plus Kreis- plus übertragene Aufgaben minus "
                         f"Umlage ergibt den ausgewiesenen Nettobetrag "
                         f"(Ausgleichsjahr {jahrgang.jahr})")}


def probe_gegen_jahrbuch(jahrgang: KfaZuweisungen, jahrbuch_teur: float,
                         schluessel: str = sv.OLDENBURG) -> dict:
    """Die zweite Probe: Trifft der Nettobetrag die Bücher der Stadt?

    ``jahrbuch_teur`` ist die Zeile „Finanzzuweisungen" aus Tabelle 1103 des
    Statistischen Jahrbuchs, in Tausend Euro. Zwei Veröffentlichungen, zwei
    Behörden, dieselbe Zahl — das ist die stärkere der beiden Proben, weil sie
    nicht innerhalb eines Dokuments rechnet.
    """
    wert = (jahrgang.staedte.get(schluessel) or {}).get("nettobetrag")
    if wert is None:
        return {"ok": False, "ergebnis": f"kein Nettobetrag für {schluessel}"}
    abstand = abs(wert - jahrbuch_teur)
    anteil = abstand / max(jahrbuch_teur, 1)
    return {
        "ok": anteil <= JAHRBUCH_TOLERANZ,
        "lsn_teur": wert, "jahrbuch_teur": jahrbuch_teur,
        "abweichung_prozent": round(anteil * 100, 4),
        "ergebnis": (f"Ausgleichsjahr {jahrgang.jahr}: {wert:,.0f} T€ (Land) "
                     f"gegen {jahrbuch_teur:,.0f} T€ (Jahrbuch 1103) — "
                     f"{anteil * 100:.4f} % Abstand".replace(",", ".")),
    }


def zeilen_finanzausgleich(jahrgang: KfaZuweisungen) -> list[dict]:
    """Ein Jahrgang → Zeilen für ``council_staedtevergleich``.

    Bewusst dieselbe Tabelle wie die Steuerkraftmesszahlen und **nicht** eine
    neue Spalte in ``council_steuerkraft``: Dort stünde in einer Zeile eine
    Zahl aus dem Open-Data-Portal neben einer vom Land, und eine Zeile trägt
    genau **eine** Herkunft (s. ``council/herkunft.py``). Getrennt lässt sich
    von jeder Zahl sagen, wer sie veröffentlicht hat.

    Die Pro-Kopf-Spalte kommt **nicht** mit — derselbe Grund wie bei den
    Steuerkraftmesszahlen, hier sogar gemessen: Für das Ausgleichsjahr 2025
    nennt die Ausgabe 2025 „452,46 € je Ew.", die Ausgabe 2026 „452,27 €".
    Derselbe Nettobetrag, revidierte Einwohnerzahl. Der Absolutwert ist
    stabil, der Quotient nicht — wer pro Kopf braucht, teilt selbst durch die
    Einwohnerzahl, die dieselbe Datei in ``reihe='steuerkraft'`` mitliefert.
    """
    aus: list[dict] = []
    for key, w in sorted(jahrgang.staedte.items()):
        for name, wert in sorted(w.items()):
            if name in ("stadt", "nettobetrag_je_ew") or wert is None:
                continue
            aus.append({"jahr": jahrgang.jahr, "schluessel": key,
                        "stadt": sv.KREISFREIE_STAEDTE.get(key, w.get("stadt", "")),
                        "kennzahl": name, "wert": float(wert), "einheit": "teur"})
    return aus
