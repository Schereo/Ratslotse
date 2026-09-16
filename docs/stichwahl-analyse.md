# Stichwahlanalyse

Die Seite am bestehenden privaten Pfad `/stichwahl/potenzial?k=…` erklärt
stadtweite Ergebnisse. Seit der Überarbeitung vom 16.09.2026 ersetzt sie
das Potenzialmodell aus #1383/#1384. Keine Gebietsempfehlungen, individuellen
Transferannahmen oder Einsatzlisten. Der Zugang mit `WAHLKAMPF_TOKEN` und
`noindex` bleibt bestehen. Keine zusätzlichen Navigations- oder Sitemaplinks.

## Daten und Bezugsgrößen

- OB-Wahl 2026: `kommunalwahl/referenz-2026/praesentation-ob-wahlbezirke.json`.
  Nichtteilnahme = stadtweite Wahlberechtigte minus alle Wählenden,
  einschließlich Briefwahl. Die bisherigen 76.873 enthielten 27.351
  Briefwählende; richtig sind in diesem Stand 49.522 Nichtwählende.
- Ratswahl: ausdrücklich `referenz-2026`, unabhängig von der aktiven Wahl
  oder Generalprobe. CDU: 34.335 Listen- und Personenstimmen zusammen.
  37.430 war der Stand von 2021. Stimmen sind keine Zahl verschiedener Personen.
- Die unter „Sonstige“ zusammengefassten 1.509 Stimmen bleiben sichtbar.
  Alle sieben ausgeschiedenen Kandidaturen zusammen haben 30.731 Stimmen.
- Prozentwerte tragen ihren Nenner. Der Umschalter zwischen allen gültigen
  Stimmen und den Stimmen für beide Finalisten ändert keine Stimmenzahl.
- Historie: Stadtgesamtwerte inklusive Briefwahl. Keine unterschiedlichen
  Bezirksfünftel, keine Rückkehrquoten identifizierter Personen. Der Vergleich
  zeigt absolute Veränderungen, Prozentänderungen und Prozentpunkte getrennt.
- Null Nenner ist unbekannt; fehlende Pflichtdaten oder widersprüchliche
  Stadtsummen brechen die Auswertung ab, statt eine Null zu erfinden.

## Historische Quellen

Die CSVs von 2014 wurden unverändert aus PR #1385 übernommen. Die dortigen
Änderungen der Tokenableitung und des alten Szenariomodells sind nicht Teil
dieser Überarbeitung.

- [Hauptwahl 2014](https://votemanager.kdo.de/20140928/03403000/html5/Buergermeisterwahl_NDS_51_Gemeinde_Stadt_Oldenburg_Oldenburg.html)
- [Stichwahl 2014](https://votemanager.kdo.de/20140928/03403000/html5/Buergermeisterstichwahl_NDS_52_Gemeinde_Stadt_Oldenburg_Oldenburg.html)
- [Amtliche Bekanntmachung Hauptwahl 2021](https://www.oldenburg.de/fileadmin/oldenburg/Benutzer/Dateien/22_Rechtsamt/Bekanntmachungen/20210917-11_KW_Bekanntmachung_Ergebnis_OB.pdf)
- [Amtliche Bekanntmachung Stichwahl 2021](https://www.oldenburg.de/fileadmin/oldenburg/Benutzer/Dateien/22_Rechtsamt/Bekanntmachungen/20211001-2021-09-30_Bekanntmachung_Stichwahl_OB.pdf)

## Aussagekraft für die Wirkung von Gesprächen

Die fehlende Absicherung örtlicher Wirkungsaussagen ist kein Nachweis,
dass Haustürgespräche generell wirkungslos wären. Experimente fanden etwa
Auswirkungen auf die [Wahlbeteiligung bei US-Kommunalwahlen](https://doi.org/10.1111/1468-2508.t01-1-00126)
und auf [Stimmenanteile bei der französischen Präsidentschaftswahl 2012](https://www.aeaweb.org/articles?id=10.1257/aer.20160524).
Diese Studien untersuchen tatsächliche Kontakte mit Vergleichsgruppen.
Die hier ausgewerteten Ergebnisdateien enthalten diese Informationen nicht;
eine örtliche Rangfolge der Kontaktwirkung folgt daraus nicht.

## Vertrag und Prüfung

`runoff_analysis.compute()` erzeugt `RunoffAnalysis` in `antworten.py`.
Der private Endpunkt behält seinen Pfad, ersetzt jedoch vor Veröffentlichung
den bisherigen Dev-Vertrag. Keine Verwendung durch die ausgelieferte iOS-App.
Das Konsolenskript behält seinen Namen und exportiert dieselbe neutrale Analyse:

```bash
python scripts/stichwahl_potenzial.py --json web/frontend/tests/e2e/fixtures/stichwahl-analyse.json
```

`tests/test_stichwahl_analyse.py` hält Quelljahr, Beteiligung einschließlich
Briefwahl, vollständige Stimmenmengen, Nenner und historischen Abgleich fest.
Der HTTP-Test vergleicht die tatsächlich serialisierte Antwort mit der
Berechnung. Der Fixture-Wächter verlangt vollständige Gleichheit. Browser-
tests prüfen Zugang, Nennerwechsel, Quellen, Fehlerzustände und schmale Layouts.
