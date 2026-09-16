# Stichwahl Oldenburg: geprüfte Zahlen und verständliche Erläuterungen

Stand: 16. September 2026. Unabhängige fachliche und sprachliche Prüfung.

Diese Fassung enthält überprüfte Stadtgesamtwerte und neutrale Textbausteine. Sie ist kein neuer Seitenentwurf. Die bestehende Website, Karte, Berechnung und PRs wurden für diese Prüfung nicht verändert. Die Ersatztexte sind hier ausgearbeitet, aber nicht in der Anwendung eingesetzt.

Geprüft sind der Stand nach [PR #1384](https://github.com/Schereo/Ratslotse/pull/1384), Commit `39b6a938f6b13ea9259fa22781b6c6f0625db2e1`, sowie die historische Ergänzung in [PR #1385](https://github.com/Schereo/Ratslotse/pull/1385), Commit `a78689b63d225a893c0ab26ae643b3bdea73ab5b`. Die Angaben beziehen sich auf eingefrorene Quelldaten. Für 2026 ist das ein vorläufiger Ergebnisstand.

## 1. Die wesentlichen Korrekturen

| Bisherige Aussage oder Zahl | Prüfergebnis | Sachlich richtige Einordnung |
|---|---|---|
| 76.873 Nichtwählende | Falsch bezeichnet: Darin stecken 27.351 Briefwählende. | Stadtweit nahmen 49.522 Wahlberechtigte nicht teil. Für einzelne Urnenbezirke fehlt die passende Zuordnung der Briefwahl. |
| 37.430 CDU-„Zweitstimmen“ der Ratswahl am selben Tag | Falsches Jahr und falsche Bezeichnung. | 34.335 Listen- und Personenstimmen bei der Ratswahl 2026. Die 37.430 gehören zu 2021. |
| 29.222 Stimmen der Ausgeschiedenen | Nur die fünf einzeln berücksichtigten Kandidaturen. | Alle sieben ausgeschiedenen Kandidaturen erhielten zusammen 30.731 Stimmen. 1.509 davon stehen in der Bezirksdatei unter „Sonstige“. |
| 51,1 % „Rohr per Brief“ | Rechnerisch richtig, wenn nur die beiden Finalisten den Nenner bilden. | Unter allen gültigen Briefwahlstimmen sind es 34,8 %. Der Nenner muss unmittelbar sichtbar sein. |
| 2014: 86,9 % „kamen wieder“ | Individuelles Verhalten wird nicht beobachtet. | Die Wählendenzahl der Stichwahl betrug 86,9 % der Wählendenzahl des ersten Wahlgangs. |
| Der Zuwachs einer Kandidatur stammt von zuvor ausgeschiedenen Kandidaturen | Aus den Summen nicht eindeutig ableitbar. | Sichtbar ist ein Nettozuwachs. Seine Zusammensetzung aus Wechseln, neuer Teilnahme, Nichtteilnahme und ungültigen Stimmen ist unbekannt. |
| Größerer Wachstumsfaktor bedeutet größeres absolutes Plus | Falsch. | Ein kleiner Ausgangswert kann einen großen Faktor erzeugen. Absolute und relative Veränderungen gehören nebeneinander. |
| 2014 als „Gegenprobe“, die andere Einflüsse ausschließt | Der Vergleich isoliert keinen einzelnen Einfluss. | Ein zusätzliches Vergleichsjahr mit anderer Ausgangslage; keine kontrollierte Wiederholung von 2021. |

Die Fundstellen und die weitergehende Prüfung der bisherigen Modellbeschreibungen stehen im [ersten Review](stichwahl-review.md). Die folgenden Abschnitte enthalten die ausgearbeiteten neutralen Formulierungen.

## 2. Textbaustein: Teilnahme und Nichtteilnahme

**Wie viele Menschen im ersten Wahlgang gewählt haben**

Bei der OB-Wahl waren im verwendeten Datenstand 135.513 Menschen wahlberechtigt. 85.991 nahmen teil: 58.640 an der Urne und 27.351 per Brief. Die Wahlbeteiligung betrug damit 63,46 Prozent. Stadtweit nahmen 49.522 Wahlberechtigte nicht teil.

Die Rechnung lautet: **135.513 − 85.991 = 49.522**. Wer nur die 58.640 Urnenwählenden abzieht, erhält 76.873. Diese größere Zahl enthält jedoch auch die Briefwählenden und ist deshalb keine Zahl der Nichtwählenden.

Die Briefwahl wird in eigenen Zählbezirken erfasst. Ohne eine verlässliche Zuordnung zu den Wohngebieten lässt sich die Nichtteilnahme einzelner Urnenbezirke aus diesen Daten nicht bestimmen. Fehlende Zuordnung bedeutet fehlendes Wissen.

Von den 85.991 abgegebenen Stimmzetteln waren 84.656 gültig und 1.335 ungültig. Auch Menschen, deren Stimmzettel ungültig ist, zählen zur Wahlbeteiligung.

Datengrundlage: die 133 Bezirkszeilen in `kommunalwahl/referenz-2026/praesentation-ob-wahlbezirke.json`, darunter 91 Urnen- und 42 Briefwahlbezirke. Die Stadt nennt ebenfalls [63,46 Prozent Wahlbeteiligung](https://www.oldenburg.de/startseite/rathaus/politik-verwaltung/wahlen/rats-oberbuergermeisterwahl-kommunalwahl/oberbuergermeisterwahl-2026/ob-wahl-entscheidung-faellt-am-27-september.html).

## 3. Textbaustein: Ergebnis und vollständige Stimmenmengen

**Das Ergebnis beschreibt den ersten Wahlgang**

Ulf Prange erhielt 28.075 Stimmen, Jascha Rohr 25.850. Der Abstand betrug 2.225 Stimmen. Bezogen auf alle 84.656 gültigen Stimmen waren das 33,16 beziehungsweise 30,54 Prozent.

An die sieben übrigen Kandidaturen gingen zusammen 30.731 Stimmen. Fünf davon sind in der verwendeten Bezirksdatei einzeln ausgewiesen und kommen auf 29.222 Stimmen. Weitere 1.509 Stimmen für Michael Stille und Yakup Castur sind dort als „Sonstige“ zusammengefasst. Die kleinere Summe beschreibt daher eine Auswahl und nicht alle ausgeschiedenen Kandidaturen.

Aus diesen Ergebnissen geht nicht hervor, welche Personen erneut teilnehmen und wie sie in der Stichwahl entscheiden. Eine Unterstützungserklärung einer Kandidatur ist ebenfalls keine Messung des späteren Wahlverhaltens ihrer bisherigen Wählenden.

Quellen: eingefrorene Bezirksdatei und [Ergebnisdarstellung der Stadt](https://www.oldenburg.de/startseite/rathaus/politik-verwaltung/wahlen/rats-oberbuergermeisterwahl-kommunalwahl/oberbuergermeisterwahl-2026/ob-wahl-entscheidung-faellt-am-27-september.html).

## 4. Textbaustein: Prozentwerte mit verständlichem Nenner

**Welche Stimmen ergeben zusammen 100 Prozent?**

| Wahlart | Stimmen für Rohr | Stimmen für Prange | Alle gültigen Stimmen | Rohr unter allen gültigen Stimmen | Rohr nur unter den Stimmen für beide Finalisten |
|---|---:|---:|---:|---:|---:|
| Urne | 16.403 | 19.023 | 57.534 | 28,5 % | 46,3 % |
| Brief | 9.447 | 9.052 | 27.122 | 34,8 % | 51,1 % |

Beide Prozentangaben können gleichzeitig richtig sein. Bei der Briefwahl ergibt **9.447 ÷ 27.122 × 100** einen Anteil von 34,8 Prozent an allen gültigen Stimmen. Betrachtet man nur die Stimmen für Rohr und Prange, lautet die Rechnung **9.447 ÷ (9.447 + 9.052) × 100**; das sind 51,1 Prozent.

Die zweite Rechnung lässt die übrigen Kandidaturen aus dem Nenner weg. Sie ist keine Prognose für die Stichwahl. Unterschiede zwischen Brief- und Urnenwahl zeigen auch nicht, dass die Wahlart die politische Entscheidung verursacht: Die Zusammensetzung der jeweils Wählenden kann unterschiedlich sein.

Die gleiche Erklärung gehört an historische Zweieranteile. Ein Anteil im ersten Wahlgang, der andere Kandidaturen ausblendet, ist ausdrücklich als Anteil **unter den Stimmen für die beiden späteren Finalisten** zu kennzeichnen. Er ist nicht der reguläre Anteil an allen gültigen Stimmen.

## 5. Textbaustein: Ratswahl, Wahljahr und Einheit

**Ratswahlstimmen sind keine Personenzahl**

Die CDU erhielt bei der Ratswahl 2026 insgesamt 34.335 Stimmen: 17.866 Listenstimmen und 16.469 Personenstimmen. Die zuvor angezeigten 37.430 Stimmen gehören zur Ratswahl 2021.

Bei der Ratswahl kann jede Person bis zu drei Stimmen vergeben und diese auf Listen oder Personen verteilen. Bei der OB-Wahl hat jede Person eine Stimme. Die Ratswahlstimmen sind deshalb keine „Zweitstimmen“ im Sinne der Bundestagswahl. Aus ihrer Summe lässt sich auch durch pauschales Teilen durch drei keine genaue Zahl verschiedener Wählender bestimmen.

Die Ergebnisse der gleichzeitig stattfindenden Wahlen identifizieren keine disjunkten Personengruppen: Eine Person kann sowohl eine Stimme bei der OB-Wahl als auch Stimmen bei der Ratswahl abgegeben haben. Die beiden Summen dürfen deshalb nicht als getrennte Gruppen von Menschen addiert werden.

Quellen: Ratswahl-Stadtdatei und unabhängige Summe aller Ratswahl-Bezirkszeilen des jeweiligen Jahres; zum Wahlverfahren der [Niedersächsische Landeswahlleiter](https://landeswahlleiter.niedersachsen.de/wahlen/kommunalwahlen/grundzuege_kommunalwahlsystem/grundzuge-des-niedersachsischen-kommunalwahlsystems-252504.html).

## 6. Historischer Vergleich: drei verschiedene Größen

Die Vergleiche beziehen sich jeweils auf die ganze Stadt einschließlich Briefwahl. Wahlberechtigtenzahlen können sich zwischen Wahlgängen ändern. Für die Beteiligungsquote wird deshalb die Wahlberechtigtenzahl des jeweiligen Wahlgangs verwendet.

| Kennzahl | 2014: erster Wahlgang → Stichwahl | Veränderung | 2021: erster Wahlgang → Stichwahl | Veränderung |
|---|---:|---:|---:|---:|
| Wahlberechtigte | 130.492 → 130.543 | +51 | 135.173 → 135.112 | −61 |
| Wählende | 50.801 → 44.149 | −6.652 | 72.765 → 81.472 | +8.707 |
| Gültige Stimmen | 50.407 → 43.353 | −7.054 | 72.248 → 80.442 | +8.194 |
| Ungültige Stimmzettel | 394 → 796 | +402 | 517 → 1.030 | +513 |
| Wahlbeteiligung | 38,93 % → 33,82 % | −5,11 Prozentpunkte | 53,83 % → 60,30 % | +6,47 Prozentpunkte |

### Textbaustein für 2014

**2014 sank die Wählendenzahl um 13,1 Prozent**

An der Stichwahl nahmen 44.149 Menschen teil, nach 50.801 im ersten Wahlgang. Das waren 6.652 beziehungsweise 13,1 Prozent weniger. Die Stichwahl erreichte damit 86,9 Prozent der ursprünglichen Wählendenzahl. Dieser Wert bezeichnet ein Verhältnis zweier Gesamtzahlen. Er bedeutet nicht, dass 86,9 Prozent derselben Menschen wiederkamen.

Die Zahl der gültigen Stimmen sank um 7.054 und damit stärker als die Zahl der Wählenden. Der Unterschied erklärt sich durch 402 zusätzliche ungültige Stimmzettel: **6.652 + 402 = 7.054**. Die Abnahme gültiger Stimmen vollständig als Nichtteilnahme zu beschreiben, wäre daher falsch.

Jürgen Krogmann erhielt 6.523 Stimmen mehr als im ersten Wahlgang, Christoph Baak 745 mehr. Das sind Nettoveränderungen ihrer Ergebnisse. Welche Personen hinter diesen Veränderungen stehen, lässt sich aus den Summen nicht erkennen.

Quellen: [Hauptwahl 2014](https://votemanager.kdo.de/20140928/03403000/html5/Buergermeisterwahl_NDS_51_Gemeinde_Stadt_Oldenburg_Oldenburg.html) und [Stichwahl 2014](https://votemanager.kdo.de/20140928/03403000/html5/Buergermeisterstichwahl_NDS_52_Gemeinde_Stadt_Oldenburg_Oldenburg.html). Die zugehörigen CSVs stammen aus dem oben genannten Commit von PR #1385.

### Textbaustein für 2021

**2021 stiegen Wählendenzahl und gültige Stimmen unterschiedlich stark**

Die Wählendenzahl stieg von 72.765 auf 81.472, also um 8.707 beziehungsweise rund 12,0 Prozent. Die Zahl der gültigen Stimmen nahm um 8.194 zu. Gleichzeitig gab es 513 zusätzliche ungültige Stimmzettel. Beide Veränderungen zusammen ergeben den Anstieg der Wählendenzahl: **8.194 + 513 = 8.707**.

Krogmann gewann gegenüber seinem ersten Ergebnis 13.929 Stimmen hinzu, Fuhrhop 15.337. Zusammen sind das 29.266 Stimmen mehr für die beiden Finalisten. Diese Zunahme ist größer als die 21.072 Stimmen für ausgeschiedene Kandidaturen im ersten Wahlgang. Schon deshalb lässt sie sich nicht vollständig als Wechsel ausschließlich aus dieser ursprünglichen Gruppe beschreiben.

Die Stichwahl fand am 26. September 2021 und damit am Tag der Bundestagswahl statt. Aus den Gesamtergebnissen allein lässt sich nicht bestimmen, welcher Teil der höheren Beteiligung durch den gemeinsamen Termin verursacht wurde.

Quellen: amtliche Bekanntmachungen zur [Hauptwahl 2021](https://www.oldenburg.de/fileadmin/oldenburg/Benutzer/Dateien/22_Rechtsamt/Bekanntmachungen/20210917-11_KW_Bekanntmachung_Ergebnis_OB.pdf) und [Stichwahl 2021](https://www.oldenburg.de/fileadmin/oldenburg/Benutzer/Dateien/22_Rechtsamt/Bekanntmachungen/20211001-2021-09-30_Bekanntmachung_Stichwahl_OB.pdf), zum gemeinsamen Termin die [Bundeswahlleiterin](https://www.bundeswahlleiterin.de/mitteilungen/bundestagswahlen/2021/20201214-wahltermin.html). Für 2021 sind die förmlichen Bekanntmachungen maßgeblich; eine städtische Pressemitteilung enthält leicht abweichende Kandidatenzahlen.

### Wachstum: absolute und relative Veränderung zusammen lesen

| Jahr und Kandidat | Erster Wahlgang | Stichwahl | Absolutes Plus | Relatives Plus | Faktor |
|---|---:|---:|---:|---:|---:|
| 2014 · Krogmann | 23.482 | 30.005 | 6.523 | 27,8 % | 1,28 |
| 2014 · Baak | 12.603 | 13.348 | 745 | 5,9 % | 1,06 |
| 2021 · Krogmann | 29.564 | 43.493 | 13.929 | 47,1 % | 1,47 |
| 2021 · Fuhrhop | 21.612 | 36.949 | 15.337 | 71,0 % | 1,71 |

Ein Faktor von 2,2 bedeutet: Die spätere Stimmenzahl beträgt das 2,2-Fache der früheren, also 120 Prozent mehr. Bei 100 Ausgangsstimmen sind das 120 zusätzliche Stimmen. Ein Anstieg von 1.000 auf 1.550 Stimmen hat dagegen nur den Faktor 1,55, aber ein Plus von 550 Stimmen. Ein größerer Faktor muss deshalb kein größeres absolutes Plus bedeuten.

Die bisherigen Bezirksfünftel von 2014 und 2021 sind zudem unterschiedlich gebildet: 2014 nur Urnenbezirke, 2021 Urnen- und Briefwahlbezirke; außerdem erfolgt die Sortierung nach unterschiedlichen Kandidaten. Die Gruppen enthalten ungefähr gleich viele Bezirke, nicht gleich viele Menschen. Eine direkte Interpretation als derselbe wiederholte Vergleich ist damit nicht gedeckt.

## 7. Neutrale Erläuterungen zur Aussagekraft

**Beobachtung, Annahme und Rechenergebnis**

Ein beobachtetes Wahlergebnis beschreibt abgegebene Stimmen. Ein Szenario berechnet dagegen, was unter gewählten Annahmen folgen würde. Eine exakt berechnete Zahl sagt nicht, wie wahrscheinlich ihre Voraussetzungen sind. Auch viele Nachkommastellen ersetzen keinen empirischen Nachweis.

**Prozent und Prozentpunkte**

Ein Anstieg von 40 auf 50 Prozent beträgt 10 Prozentpunkte. Bezogen auf den Ausgangswert von 40 Prozent entspricht das einem relativen Anstieg um 25 Prozent. Die beiden Angaben beantworten unterschiedliche Fragen.

**Was „nicht belegt“ hier bedeutet**

Die verwendeten Ergebnisdateien enthalten keine Messung von besuchten Türen, geführten Gesprächen oder dadurch veränderten Wahlentscheidungen. Daraus lässt sich keine Wirkung je Kontakt bestimmen. Diese Grenze der Daten ist kein Nachweis dafür, dass persönliche Gespräche generell wirkungslos wären.

Experimentelle Untersuchungen fanden etwa Auswirkungen persönlicher Kontakte auf die [Wahlbeteiligung in US-Kommunalwahlen](https://doi.org/10.1111/1468-2508.t01-1-00126) und auf [Stimmenanteile bei der französischen Präsidentschaftswahl 2012](https://www.aeaweb.org/articles?id=10.1257/aer.20160524). Eine andere Untersuchung schätzte den durchschnittlichen Überzeugungseffekt von Kampagnenkontakten in den untersuchten US-Hauptwahlen auf null ([Kalla und Broockman](https://www.cambridge.org/core/journals/american-political-science-review/article/abs/minimal-persuasive-effects-of-campaign-contact-in-general-elections-evidence-from-49-field-experiments/753665A313C4AB433DBF7110299B7433)). Die Studien untersuchen unterschiedliche Kontexte und Zielgrößen. Keine dieser Aussagen ist eine gemessene Rangfolge der Kontaktwirkung in Oldenburger Wohngebieten.

**Zusammenhang zwischen Gebieten ist kein individuelles Verhalten**

Ein Korrelationswert nahe null belegt keine gleichmäßige räumliche Verteilung. Ein negativer Korrelationswert ist keine Wechselquote. Aus zusammengefassten Gebietsergebnissen lässt sich nicht direkt ablesen, welche einzelne Person ihre Entscheidung ändert. Die im Plan genannten Korrelationskoeffizienten wurden hier nicht neu geschätzt.

## 8. Neutraler Hinweis zum Briefwahlverfahren

**Briefwahlunterlagen für die Stichwahl**

Wer bereits bei der Hauptwahl auch Briefwahlunterlagen für die Stichwahl angefordert hat, erhält diese nach Auskunft der Stadt automatisch. Wer für die Stichwahl noch keine Unterlagen angefordert hat, findet die aktuellen Möglichkeiten beim Wahlbüro. Die Stadt nennt den 21. September 2026 als Beginn der persönlichen Beantragung und direkten Stimmabgabe vor Ort.

Quelle und aktueller Stand: [Stadt Oldenburg, Informationen zur Stichwahl](https://www.oldenburg.de/startseite/rathaus/politik-verwaltung/wahlen/rats-oberbuergermeisterwahl-kommunalwahl/oberbuergermeisterwahl-2026/ob-wahl-entscheidung-faellt-am-27-september.html), geprüft am 16. September 2026. Fristen der bereits abgeschlossenen Hauptwahl werden nicht auf die Stichwahl übertragen. Eine Beantragung allein ist noch keine abgegebene Stimme.

## 9. Nachrechnung und Reichweite der Prüfung

Die unabhängige Nachrechnung liegt als [Python-Datei](stichwahl-faktencheck.py) und [JSON-Ergebnis](stichwahl-faktencheck.json) bei. Das Skript importiert weder das bestehende Potenzialmodell noch dessen Parser. Es liest die JSON- und CSV-Quelldaten unmittelbar und gibt ausschließlich stadtweite Ergebnisse aus.

Es prüft:

- vollständige Auszählungsstände und eindeutige Bezirkszeilen;
- Summen aller Kandidatenstimmen gegen gültige Stimmen;
- Bezirks- gegen vorhandene Stadtgesamtwerte;
- Ratswahl-Listen- und Personenstimmen sowie die unterschiedlichen CSV-Schemata von 2021 und 2026;
- die Gleichung „Veränderung der Wählenden = Veränderung gültiger Stimmen + Veränderung ungültiger Stimmzettel“;
- Quellenidentität durch SHA-256-Prüfsummen, für 2014 zusätzlich den geprüften Git-Commit.

Aufruf aus einem Checkout dieses Branches (die unveränderten 2014er CSVs aus dem genannten Commit liegen unter `quellen-2014/` bei und werden anhand ihrer SHA-256-Prüfsummen geprüft):

```bash
python3.12 stichwahl-faktencheck.py /pfad/zum/kommunalwahl-scraper > nachrechnung.json
```

Die Prüfung bestätigt Rechenwerte und begrenzt deren Interpretation. Sie ersetzt keine Untersuchung individueller Wahlentscheidungen. Website-Code, Karten, API-Vertrag und bestehende Wahlkampffunktionen wurden nicht bearbeitet; daher gab es für diese Prüffassung keinen neuen PR, Merge oder Deploy.
