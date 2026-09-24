"""Die Schulden der acht kreisfreien Städte Niedersachsens — Kernhaushalt
UND eigene Einrichtungen, aus der Regionaldatenbank (Plan
Haushalt-Datenquellen, PR 7).

QUELLE: die Regionaldatenbank der Statistischen Ämter
(regionalstatistik.de, GENESIS-Webservice, Konto nötig; Zugangsdaten in
``REGIONALSTATISTIK_USER`` / ``REGIONALSTATISTIK_PASSWORD``), Statistik 71327:

* ``71327-Z-02`` — je Kreis/kreisfreie Stadt die Schulden des Kernhaushalts
  (``SDKHGV1``) und die der öffentlichen Fonds, Einrichtungen und Unternehmen,
  an denen der Kernhaushalt unmittelbar zu 100 % beteiligt ist
  (``SDOFEU1``), 2019–2025, Stichtag 31.12.
* ``71327-Z-07`` — die Einwohnerzahl am 30.06. desselben Jahres.

Beide Tabellen sind zu groß für den Dialogabruf; der Webservice baut sie als
Auftrag im Hintergrund (``job=true``) und liefert sie danach als Ergebnis.

WARUM GERADE DAS (gemessen 24.09.2026): Die Seite /haushalt/vergleich
erklärt, dass ein Vergleich von Kernhaushalten zuerst misst, wie viel eine
Stadt ausgelagert hat. Diese Tabelle zeigt beides nebeneinander — Oldenburg
hat 2025 41 Mio. € im Kernhaushalt und 419 Mio. € in den eigenen
Einrichtungen. Was sie nicht zeigt: Beteiligungen unter 100 % (die Stadtwerke
Osnabrück sind voll städtisch, EWE ist es für Oldenburg nicht).

WAS NICHT GEHT, und bewusst nicht gebaut ist:

* Die Kassenstatistik je Quartal (71517) endet in der Regionaldatenbank 2014.
* Das Personal (74111, Vollzeitäquivalente zum 30.06.) passt nicht zum
  Stellenplan der Stadt (2024: 2.825 gegen 1.990 besetzte Stellen) — eine
  andere Abgrenzung, die sich nicht prüfen lässt.

DIE PROBE: Oldenburgs Kernhaushalt gegen die eigene Schuldenreihe
(``council_debt.credit_market``, in T€ gerundet) — höchstens 1.000 € Abstand.
Ein Jahr ohne bestandene Probe fällt für alle Städte heraus. Die Schulden der
Einrichtungen haben keine eigene Gegenreihe; sie stehen, wie die Statistik
sie führt, und die Seite sagt das.
"""
from __future__ import annotations

import csv
import io
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass, field

SERIES = "regionalstatistik"
PROBE = "regional_debt_core_budget"
BASIS = "https://www.regionalstatistik.de/genesisws/rest/2020/"
TABELLE_SCHULDEN = "71327-Z-02"
TABELLE_EINWOHNER = "71327-Z-07"

#: Die acht kreisfreien Städte Niedersachsens — Kreisschlüssel wie in der
#: Tabelle (mit „F" davor) → Gemeindeschlüssel, wie ihn die übrigen Reihen
#: in ``council_city_comparison`` tragen.
STAEDTE = {
    "F03101": ("03101000", "Braunschweig"),
    "F03102": ("03102000", "Salzgitter"),
    "F03103": ("03103000", "Wolfsburg"),
    "F03401": ("03401000", "Delmenhorst"),
    "F03402": ("03402000", "Emden"),
    "F03403": ("03403000", "Oldenburg"),
    "F03404": ("03404000", "Osnabrück"),
    "F03405": ("03405000", "Wilhelmshaven"),
}
OLDENBURG = "03403000"
MERKMALE = {"SDKHGV1": "debt_core", "SDOFEU1": "debt_entities"}


class RegionalFehler(RuntimeError):
    """Der Webservice liefert nicht, was er soll."""


class Webservice:
    """Der GENESIS-Webservice mit Zugang im Kopf und Mindestabstand."""

    def __init__(self, user: str, password: str, pause: float = 1.2) -> None:
        self._kopf = {"username": user, "password": password,
                      "Content-Type": "application/x-www-form-urlencoded"}
        self.pause, self._zuletzt = pause, 0.0

    def rufe(self, pfad: str, **params: str) -> bytes:
        warten = self.pause - (time.monotonic() - self._zuletzt)
        if warten > 0:
            time.sleep(warten)
        params.setdefault("language", "de")
        anfrage = urllib.request.Request(BASIS + pfad, data=urllib.parse.urlencode(params).encode(),
                                         headers=self._kopf)
        try:
            with urllib.request.urlopen(anfrage, timeout=180) as antwort:
                return antwort.read()
        except urllib.error.HTTPError as fehler:
            # Der Dienst antwortet auf „noch nicht fertig" mit 404 und einer
            # JSON-Meldung im Körper — die ist die Auskunft, nicht der Status.
            return fehler.read() or b"{}"
        finally:
            self._zuletzt = time.monotonic()

    def tabelle(self, name: str, *, startjahr: int, warten: int = 600) -> str:
        """Eine große Tabelle als flache CSV: Auftrag anlegen, Ergebnis holen."""
        antwort = self.rufe("data/tablefile", name=name, area="all", format="ffcsv",
                            compress="false", startyear=str(startjahr), job="true").decode("utf-8", "replace")
        if "_" not in antwort or "Bearbeitungsauftrag" not in antwort:
            raise RegionalFehler(f"{name}: kein Auftrag angelegt ({antwort[:160]})")
        ergebnis = antwort.split("folgendem Namen abgerufen werden:")[1].split('"')[0].strip()
        ende = time.monotonic() + warten
        while time.monotonic() < ende:
            daten = self.rufe("data/resultfile", name=ergebnis, area="all", format="ffcsv", compress="false")
            if daten[:2] == b"PK":
                with zipfile.ZipFile(io.BytesIO(daten)) as zf:
                    return zf.read(zf.namelist()[0]).decode("utf-8-sig")
            if daten[:10].lstrip(b"\xef\xbb\xbf").startswith(b"statistics"):
                return daten.decode("utf-8-sig")
            time.sleep(15)
        raise RegionalFehler(f"{name}: Ergebnis {ergebnis} nach {warten} s nicht fertig")


@dataclass
class Lesung:
    #: (Gemeindeschlüssel, Jahr, Kennzahl) → Wert; Kennzahlen: debt_core,
    #: debt_entities (Euro), population (Personen).
    werte: dict[tuple[str, int, str], float] = field(default_factory=dict)
    bestanden: set[int] = field(default_factory=set)
    hinweise: list[str] = field(default_factory=list)


def _stadt(code: str) -> tuple[str, str] | None:
    """„F03403" (Kreisschlüssel, Z-02) oder „F03403000000000" (Regionalschlüssel,
    Z-07) → die Stadt; ein längerer Schlüssel nur, wenn er die Stadt selbst meint."""
    stadt = STAEDTE.get(code[:6])
    return stadt if stadt and set(code[6:]) <= {"0"} else None


def lies(schulden_csv: str, einwohner_csv: str) -> Lesung:
    """Die beiden flachen CSV-Dateien → Werte der acht Städte."""
    aus = Lesung()
    for z in csv.DictReader(io.StringIO(schulden_csv), delimiter=";"):
        stadt = _stadt(z.get("1_variable_attribute_code", ""))
        merkmal = MERKMALE.get(z.get("value_variable_code", ""))
        if stadt and merkmal and z["value"] not in ("", "-", "."):
            aus.werte[(stadt[0], int(z["time"][:4]), merkmal)] = float(z["value"])
    for z in csv.DictReader(io.StringIO(einwohner_csv), delimiter=";"):
        stadt = _stadt(z.get("1_variable_attribute_code", ""))
        if stadt and z.get("value_variable_code") == "FINBEV" and z["value"] not in ("", "-", "."):
            aus.werte[(stadt[0], int(z["time"][:4]), "population")] = float(z["value"])
    if not aus.werte:
        raise RegionalFehler("keine der acht Städte in den Tabellen — Schlüssel geändert?")
    return aus


def pruefe(lesung: Lesung, eigene_kern: dict[int, float]) -> Lesung:
    """Oldenburgs Kernhaushalt gegen die eigene Reihe; ein Jahr ohne bestandene
    Probe fällt für alle Städte heraus."""
    jahre = sorted({j for (_, j, _) in lesung.werte})
    for j in jahre:
        stat = lesung.werte.get((OLDENBURG, j, "debt_core"))
        eigen = eigene_kern.get(j)
        if stat is None or eigen is None:
            lesung.hinweise.append(f"{j}: {'keine eigene Reihe' if eigen is None else 'kein Wert'} zum Prüfen")
        elif abs(stat - eigen) <= 1000:
            lesung.bestanden.add(j)
        else:
            lesung.hinweise.append(f"{j}: Statistik {stat:,.0f} €, eigene Reihe {eigen:,.0f} €")
    return lesung
