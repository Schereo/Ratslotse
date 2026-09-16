# Stichwahl: fachliche Prüfung und neutrale Neufassung

Stand: 16. September 2026. Geprüft wurden [PR #1382](https://github.com/Schereo/Ratslotse/pull/1382), [#1383](https://github.com/Schereo/Ratslotse/pull/1383), [#1384](https://github.com/Schereo/Ratslotse/pull/1384) und [#1385](https://github.com/Schereo/Ratslotse/pull/1385): Plan, Berechnungen, Oberflächentexte, historische Vergleiche und die zugehörigen Zahlentests.

**Die Analyse braucht sachliche Korrekturen vor einer sprachlichen Politur.** Besonders schwer wiegen die falsch bezeichneten Nichtwählenden und die Vermischung von Ratswahldaten aus 2021 mit der OB-Wahl 2026. Mehrere weitere Aussagen beschreiben individuelles Wahlverhalten oder die Wirkung von Wahlkampf, obwohl lediglich zusammengefasste Wahlergebnisse vorliegen.

Diese Überarbeitung enthält eine unabhängige, neutrale Erklärung der Wahldaten. Sie enthält keine Empfehlungen zur gezielten Ansprache bestimmter Wählergruppen oder zur Verteilung von Wahlkampfeinsätzen. Die operativen PRs wurden nicht verändert.

## Neufassung für eine allgemein verständliche Wahlanalyse

### Die Ausgangslage: ein Ergebnis, noch keine Vorhersage

Im gespeicherten Ergebnis des ersten Wahlgangs erhielt Ulf Prange 28.075 Stimmen und Jascha Rohr 25.850 Stimmen. Der Abstand betrug 2.225 Stimmen. Bezogen auf alle 84.656 gültigen Stimmen entfielen 33,16 Prozent auf Prange und 30,54 Prozent auf Rohr. Die Stadt bestätigt diese Prozentwerte in ihrer [Information zur OB-Wahl 2026](https://www.oldenburg.de/startseite/rathaus/politik-verwaltung/wahlen/rats-oberbuergermeisterwahl-kommunalwahl/oberbuergermeisterwahl-2026/ob-wahl-entscheidung-faellt-am-27-september.html).

An die sieben übrigen Kandidaturen gingen zusammen 30.731 Stimmen. Davon berücksichtigt das bisherige Modell nur 29.222 Stimmen für fünf Kandidaturen. Weitere 1.509 Stimmen stehen in der Bezirksdatei unter „Sonstige“. Die kleinere Zahl ist daher eine Auswahl des Modells und nicht die Gesamtzahl der Stimmen für ausgeschiedene Kandidaturen.

Diese Ergebnisse zeigen, wie im ersten Wahlgang abgestimmt wurde. Sie zeigen nicht, welche Menschen an der Stichwahl teilnehmen oder wie sie sich dort entscheiden werden. Auch eine Unterstützungserklärung einer Kandidatur ist kein Nachweis dafür, dass deren bisherige Wählerschaft geschlossen folgt.

### Wahlbeteiligung: Briefwählende haben bereits gewählt

Der verwendete Datenstand enthält 135.513 Wahlberechtigte und 85.991 Wählende. Davon wählten 58.640 an der Urne und 27.351 per Brief. Damit beteiligten sich 63,46 Prozent; 49.522 Wahlberechtigte nahmen nicht teil.

Die bisher angezeigte Zahl von 76.873 entsteht, wenn nur die Urnenwählenden von den Wahlberechtigten abgezogen werden. Darin stecken auch die 27.351 Briefwählenden. Sie als Nichtwählende zu bezeichnen, ist falsch.

Für die ganze Stadt lässt sich die Nichtteilnahme aus der Gesamtsumme bestimmen. Für einzelne Urnenbezirke reicht dieselbe Subtraktion nicht aus, solange die Briefwählenden diesen Bezirken nicht verlässlich zugeordnet werden können. Fehlende Zuordnung bedeutet fehlendes Wissen und nicht null Personen.

### Zwei Prozentangaben können gleichzeitig stimmen

Bei den Briefwahlstimmen entfielen auf Rohr 9.447 und auf Prange 9.052 Stimmen. Betrachtet man ausschließlich die Stimmen für diese beiden Kandidaten, beträgt Rohrs Anteil 51,1 Prozent. Bezieht man dagegen alle 27.122 gültigen Briefwahlstimmen ein, beträgt sein Anteil 34,8 Prozent.

An der Urne lauten die entsprechenden Werte 46,3 Prozent unter den Stimmen für die beiden späteren Stichwahlkandidaten und 28,5 Prozent unter allen gültigen Stimmen.

| Bezugsgröße im ersten Wahlgang | Rohr, Urne | Rohr, Brief |
|---|---:|---:|
| Anteil an sämtlichen gültigen Stimmen der jeweiligen Wahlart | 28,5 % | 34,8 % |
| Anteil ausschließlich an den Stimmen für Rohr und Prange | 46,3 % | 51,1 % |

Der Unterschied beschreibt die Zusammensetzung der abgegebenen Stimmen. Er beweist nicht, dass die Wahlart die politische Entscheidung verursacht. Die Zweieranteile sind auch keine Prognose für die Stichwahl: Stimmen für andere Kandidaturen sind aus ihrem Nenner herausgerechnet.

### Ratswahlstimmen sind keine zusätzliche Gruppe von Menschen

Die gespeicherten Ratswahldaten von 2026 weisen 34.335 Stimmen für die CDU aus. Es handelt sich um die Summe der Listen- und Personenstimmen. Die bisher genannte Zahl von 37.430 gehört zur Ratswahl 2021.

Bei der niedersächsischen Ratswahl kann jede Person bis zu drei Stimmen vergeben und sie auch verteilen. Bei der OB-Wahl hat jede Person eine Stimme. Deshalb lassen sich Ratswahlstimmen weder als „Zweitstimmen“ bezeichnen noch eins zu eins in Personen oder zusätzliche OB-Stimmen übersetzen. Auch eine pauschale Division durch drei würde keine exakte Personenzahl ergeben. Erläutert ist das beim [Niedersächsischen Landeswahlleiter](https://landeswahlleiter.niedersachsen.de/wahlen/kommunalwahlen/grundzuege_kommunalwahlsystem/grundzuge-des-niedersachsischen-kommunalwahlsystems-252504.html).

### Der historische Vergleich: weniger oder mehr Stimmen, aber keine beobachteten Wanderungen

2014 sank die Zahl der Wählenden zwischen Haupt- und Stichwahl von 50.801 auf 44.149. Das waren 6.652 Personen beziehungsweise 13,1 Prozent weniger. Die Stichwahl erreichte damit 86,9 Prozent der Wählendenzahl des ersten Wahlgangs. Die Wahlbeteiligung sank von 38,93 auf 33,82 Prozent der jeweils Wahlberechtigten, also um 5,11 Prozentpunkte. Quellen: [Hauptwahl 2014](https://votemanager.kdo.de/20140928/03403000/html5/Buergermeisterwahl_NDS_51_Gemeinde_Stadt_Oldenburg_Oldenburg.html) und [Stichwahl 2014](https://votemanager.kdo.de/20140928/03403000/html5/Buergermeisterstichwahl_NDS_52_Gemeinde_Stadt_Oldenburg_Oldenburg.html).

„86,9 Prozent kamen wieder“ wäre eine andere Aussage: Sie würde bedeuten, dass dieselben Menschen in beiden Wahlgängen identifiziert wurden. Das leisten die Ergebnisse nicht. Einige können nur am ersten, andere nur am zweiten Wahlgang teilgenommen haben.

2021 verlief die Entwicklung umgekehrt: Die Wählendenzahl stieg von 72.765 auf 81.472, also um 8.707 beziehungsweise rund 12,0 Prozent. Die Beteiligung stieg von 53,83 auf 60,30 Prozent, also um 6,47 Prozentpunkte. Quellen: die amtlichen Bekanntmachungen zur [Hauptwahl](https://www.oldenburg.de/fileadmin/oldenburg/Benutzer/Dateien/22_Rechtsamt/Bekanntmachungen/20210917-11_KW_Bekanntmachung_Ergebnis_OB.pdf) und zur [Stichwahl](https://www.oldenburg.de/fileadmin/oldenburg/Benutzer/Dateien/22_Rechtsamt/Bekanntmachungen/20211001-2021-09-30_Bekanntmachung_Stichwahl_OB.pdf).

Die Stichwahl 2021 fand am Tag der Bundestagswahl statt. Das ist ein wesentlicher Unterschied zwischen den Vergleichsjahren. Wie groß der Einfluss dieses gemeinsamen Termins war, lässt sich aus den beiden Gesamtergebnissen allein nicht bestimmen. Den Bundestagswahltermin bestätigt die [Bundeswahlleiterin](https://www.bundeswahlleiterin.de/mitteilungen/bundestagswahlen/2021/20201214-wahltermin.html).

### Wachstum erklären: eine Verdopplung ist kein Herkunftsnachweis

Ein Faktor von 2,2 bedeutet: Die Stimmenzahl im zweiten Wahlgang beträgt das 2,2-Fache der ursprünglichen Zahl, also 120 Prozent mehr. Er sagt weder, woher die zusätzlichen Stimmen stammen, noch welche Maßnahme sie ausgelöst hat.

Ein einfaches Beispiel verdeutlicht den Unterschied zwischen relativem und absolutem Wachstum: Ein Anstieg von 100 auf 220 Stimmen entspricht dem Faktor 2,2 und einem Plus von 120 Stimmen. Ein Anstieg von 1.000 auf 1.550 entspricht nur dem Faktor 1,55, aber einem Plus von 550 Stimmen. Der größere Faktor muss deshalb nicht den größeren absoluten Zuwachs bezeichnen.

### Was eine Szenariorechnung aussagt

Ein Szenario zeigt das rechnerische Ergebnis gewählter Annahmen. Es misst nicht, wie wahrscheinlich diese Annahmen sind. Ein exakt ausgerechneter Wert kann daher eine erhebliche inhaltliche Unsicherheit enthalten. Die Genauigkeit der Rechnung ist von der Verlässlichkeit ihrer Voraussetzungen zu unterscheiden.

Wahlergebnisse, Rechenannahmen und daraus abgeleitete Aussagen sollten jeweils erkennbar sein. Für jede Kennzahl braucht es mindestens eine Einheit, eine Bezugsgröße, das Wahljahr und eine Erklärung, welche Schlussfolgerung sie zulässt. Wo die Daten keine Antwort geben, ist „nicht bestimmbar“ verständlicher und richtiger als eine scheinbar genaue Zahl.

## Fachliche Befunde mit Fundstellen

Die folgenden Quellverweise sind auf den geprüften Stand von PR #1385 festgelegt (`a78689b63d225a893c0ab26ae643b3bdea73ab5b`). Die dort unverändert enthaltenen Bestandteile aus #1383 und #1384 wurden mitgeprüft. Der Plan wurde unter `8ba2d8160c97b97d77d1ef74747dbc20f9206441` gelesen.

### 1. Nichtwählende: falsche Bedeutung einer rechnerisch korrekten Differenz

**Befund:** Die Subtraktion berücksichtigt je Urnenbezirk nur dort gezählte Wählende, während Briefwahl separat gezählt wird. Dadurch werden auf Stadtebene 27.351 tatsächlich Wählende fälschlich als Nichtwählende ausgewiesen.

**Nachrechnung:** 135.513 − 58.640 = 76.873; nach Einbeziehung der Briefwahl: 135.513 − 85.991 = 49.522.

Fundstelle: [potential.py, Berechnung von `nicht`](https://github.com/Schereo/Ratslotse/blob/a78689b63d225a893c0ab26ae643b3bdea73ab5b/web/backend/app/election/potential.py#L137). Datengrundlage: [eingefrorene OB-Bezirksdaten](https://github.com/Schereo/Ratslotse/blob/a78689b63d225a893c0ab26ae643b3bdea73ab5b/kommunalwahl/referenz-2026/praesentation-ob-wahlbezirke.json).

### 2. Ratswahldaten: falsches Jahr und falsche Einheit

**Befund:** `_cdu_je_bezirk()` greift auf den Referenzstand der Generalprobe zu. Für die aktive Ratswahl 2026 ist das die Vorwahl 2021. Die 37.430 lassen sich dort exakt wiederfinden. Die 2026er Stadtdatei und die Summe ihrer 133 Bezirkszeilen ergeben dagegen übereinstimmend 34.335. Unabhängig davon sind beide Werte Stimmenzahlen und keine identifizierte Personengruppe.

Fundstellen: [Datenbezug in potential.py](https://github.com/Schereo/Ratslotse/blob/a78689b63d225a893c0ab26ae643b3bdea73ab5b/web/backend/app/election/potential.py#L90), [Auswahl des Referenzjahres](https://github.com/Schereo/Ratslotse/blob/a78689b63d225a893c0ab26ae643b3bdea73ab5b/web/backend/app/election/reference.py#L78), [Stadtergebnis 2021](https://github.com/Schereo/Ratslotse/blob/a78689b63d225a893c0ab26ae643b3bdea73ab5b/kommunalwahl/referenz-2021/ratswahl-2021-stadt.csv) und [Stadtergebnis 2026](https://github.com/Schereo/Ratslotse/blob/a78689b63d225a893c0ab26ae643b3bdea73ab5b/kommunalwahl/referenz-2026/ratswahl-2026-stadt.csv).

### 3. „Verschiebt nur“ beschreibt die Rechnung nicht

**Befund:** Der zusätzliche CDU-Term wird in der Implementierung bei einer der beiden Kandidaturen addiert, ohne beim Gegenüber abgezogen zu werden. Bei ungleichen Einstellungen verändert sich damit auch die Gesamtstimmenzahl. Das widerspricht der Beschreibung einer bloßen Verschiebung. Zusammen mit der unklaren Personenzuordnung können die ausgegebenen Kandidatenzahlen nicht als konsistentes Modell individueller Stimmenwanderung gelten.

Fundstelle: [Berechnung der beiden Ergebniszahlen](https://github.com/Schereo/Ratslotse/blob/a78689b63d225a893c0ab26ae643b3bdea73ab5b/web/backend/app/election/potential.py#L134). Dies ist eine Feststellung zur Aussagekraft; hier wird kein Ersatzmodell für den Wahlkampfeinsatz entwickelt.

### 4. Historische Summen werden als individuelles Verhalten beschrieben

**Befund:** Die Formulierungen zum Wiederkommen und zur Herkunft zusätzlicher Stimmen behaupten mehr, als die Daten zeigen. Auch 2014 wird keine individuelle Wiederwahlteilnahme beobachtet. Ein Zuwachs bei einer Kandidatur lässt sich nicht eindeutig den zuvor ausgeschiedenen Kandidaturen zuordnen. Nichtteilnahme, neue Teilnahme, Wechsel zwischen den Finalisten und ungültige Stimmen bleiben auseinanderzuhalten.

Fundstellen: [Berechnung der Verhältniszahl](https://github.com/Schereo/Ratslotse/blob/a78689b63d225a893c0ab26ae643b3bdea73ab5b/web/backend/app/election/potential.py#L283) und [historische Erläuterungen](https://github.com/Schereo/Ratslotse/blob/a78689b63d225a893c0ab26ae643b3bdea73ab5b/web/frontend/components/wahlabend/potenzial/bloecke.tsx).

### 5. Historische Fünftel sind nicht direkt vergleichbar

**Befund:** 2021 werden Urnen- und Briefwahlbezirke gemeinsam eingeteilt, 2014 ausschließlich Urnenbezirke. Außerdem richtet sich die Sortierung 2021 nach Fuhrhop und 2014 nach Krogmann. Die Gruppen umfassen ungefähr gleich viele Bezirke, nicht gleich viele Wahlberechtigte oder Wählende. Die Faktoren vergleichen daher unterschiedliche Gruppierungen und sind keine direkte Wiederholung desselben Versuchs.

Hohe Wachstumsfaktoren bei niedriger Ausgangszahl belegen zudem keine Sättigung in anderen Bezirken. Ein kausaler Schluss zur Wirksamkeit von Ansprache folgt daraus nicht.

Fundstellen: [Gruppenbildung 2021](https://github.com/Schereo/Ratslotse/blob/a78689b63d225a893c0ab26ae643b3bdea73ab5b/web/backend/app/election/potential.py#L218) und [Gruppenbildung 2014](https://github.com/Schereo/Ratslotse/blob/a78689b63d225a893c0ab26ae643b3bdea73ab5b/web/backend/app/election/potential.py#L267).

### 6. „Ertrag je Tür“ ist keine gemessene Wirkung

**Befund:** Die zugrunde liegende Größe ist ein Szenariosaldo, geteilt durch die Zahl der Wahlberechtigten und mit 1.000 multipliziert. Sie enthält weder die Zahl besuchter Haushalte noch die Zahl geführter Gespräche oder einen gemessenen Effekt. Aussagen zur Wirksamkeit einer einzelnen Tür, zu einem doppelten Nutzen oder zur Bearbeitbarkeit eines Stadtbezirks an einem Nachmittag sind dadurch nicht belegt.

Fundstellen: [Interpretation in den Befunden](https://github.com/Schereo/Ratslotse/blob/a78689b63d225a893c0ab26ae643b3bdea73ab5b/web/frontend/components/wahlabend/potenzial/view.tsx#L103) und [Bezeichnungen der Einstufungen](https://github.com/Schereo/Ratslotse/blob/a78689b63d225a893c0ab26ae643b3bdea73ab5b/web/frontend/lib/potenzial.ts#L78).

### 7. Korrelationen werden überinterpretiert

**Befund:** Ein Korrelationskoeffizient nahe null bedeutet nicht, dass Stimmen überall gleich verteilt sind. Ein negativer Koeffizient ist weder eine Prozentangabe noch ein Nachweis individueller Wechselbereitschaft. Bei Anteilen ist zusätzlich zu beachten, dass sie sich auf eine gemeinsame Gesamtsumme beziehen: Ein höherer Anteil lässt für die anderen zusammen weniger übrig.

Die im Plan angegebenen Koeffizienten wurden hier nicht neu geschätzt. Geprüft wurde die daraus gezogene Aussage; diese geht über die Bedeutung der Kennzahl hinaus.

Fundstelle: [Plan, Abschnitt 1.3](https://github.com/Schereo/Ratslotse/blob/8ba2d8160c97b97d77d1ef74747dbc20f9206441/docs/plan-stichwahl-potenzial.md).

### 8. Angezeigte Restanteile und Beteiligung haben verschiedene Bezugsgrößen

**Befund:** Die Oberfläche bezeichnet die Differenz zwischen 100 Prozent und den beiden Übergangsanteilen als Nichtteilnahme. Die Berechnung multipliziert die Übergänge jedoch zusätzlich mit einem Beteiligungsfaktor. Sobald dieser von 100 Prozent abweicht, erklärt der angezeigte Rest nicht mehr vollständig, welcher Anteil rechnerisch keiner der beiden Kandidaturen zugeordnet wird. Auch die historische Verhältniszahl aus 2014 ist keine gemessene Teilnahmequote einzelner politischer Gruppen.

Fundstellen: [Restanzeige](https://github.com/Schereo/Ratslotse/blob/a78689b63d225a893c0ab26ae643b3bdea73ab5b/web/frontend/components/wahlabend/potenzial/regler.tsx#L77) und [zusätzliche Multiplikation](https://github.com/Schereo/Ratslotse/blob/a78689b63d225a893c0ab26ae643b3bdea73ab5b/web/backend/app/election/potential.py#L132).

### 9. Grüne Tests bestätigen noch keine richtige Interpretation

**Befund:** Die Tests schreiben unter anderem 76.873 Nichtwählende und 37.430 CDU-Stimmen fest. Sie können die derzeitige Ausgabe reproduzieren, belegen aber weder deren richtige Bezeichnung noch die Übereinstimmung des Wahljahres. Ebenso validiert ein Test einer Gebietseinstufung nicht die behauptete Wirkung von Wahlkampf.

Fundstelle: [Tests zur Ausgangslage](https://github.com/Schereo/Ratslotse/blob/a78689b63d225a893c0ab26ae643b3bdea73ab5b/tests/test_stichwahl_potenzial.py#L28).

## Verständlichkeit einer neutralen Darstellung

- **Die Erklärung direkt an die Zahl setzen.** Beispielsweise: „86,9 % der Wählendenzahl des ersten Wahlgangs“, gefolgt von den beiden absoluten Zahlen. Eine Erklärung nur per Hover ist auf Mobilgeräten schwer zugänglich.
- **Beobachtung und Annahme sichtbar kennzeichnen.** Historische Ergebnisse erhalten Wahljahr und Quellenstand; Modellwerte die Bezeichnung „Szenario“. Ein gemeinsamer Hinweis am Seitenende reicht für missverständliche Hauptaussagen nicht aus.
- **Absolute und relative Veränderung zusammen zeigen.** Neben einem Wachstumsfaktor stehen Ausgangszahl, Endzahl und Differenz. So wird der Einfluss kleiner Ausgangswerte sichtbar.
- **Prozent und Prozentpunkte ausschreiben.** Die historische Beteiligung zeigt anschaulich, warum ein Rückgang der Wählendenzahl um 13,1 Prozent und ein Rückgang der Beteiligung um 5,11 Prozentpunkte unterschiedliche Aussagen sind.
- **Neutrale Begriffe verwenden.** „Historischer Vergleich“ statt „Gegenprobe“, „Bezirke mit niedrigem Ausgangsanteil“ statt „Diaspora“, „Stimmen für ausgeschiedene Kandidaturen“ statt „Umworbene“. Eine statistische Kategorie sollte keine nicht gemessene Absicht von Menschen unterstellen.
- **Datenlücken benennen.** Die nicht einzeln ausgewiesenen 1.509 Stimmen und die fehlende kleinräumige Zuordnung der Briefwahl gehören in die Erläuterung der Datenbasis.

## Umfang der Verifikation

Die Stadtwerte 2026 und die historischen Beteiligungswerte wurden mit einem unabhängigen Python-Skript direkt aus den JSON- beziehungsweise CSV-Dateien summiert, ohne die Potenzialberechnung aufzurufen. Für 2026 wurden 133 Bezirkszeilen, darunter 42 Briefwahlbezirke, berücksichtigt. Die CDU-Summe 2026 wurde sowohl in der Stadtdatei als auch über alle Bezirke geprüft. Die historischen Gesamtwerte wurden mit den amtlichen Veröffentlichungen abgeglichen.

Die Wahlbekanntmachung vom 30. September 2021 bestätigt die im Repository gespeicherten 43.493 beziehungsweise 36.949 Kandidatenstimmen. Eine ebenfalls auffindbare städtische Pressemitteilung nennt leicht abweichende Zahlen; für den Abgleich wurde die förmliche Bekanntmachung herangezogen.

Nicht durchgeführt wurden Browser-, Sicherheits- oder Performanceprüfungen. Es wurden keine Produktdateien, Tests, PRs oder Deployments verändert. Diese Datei ist die ausgearbeitete fachliche und sprachliche Überarbeitung für eine neutrale Darstellung, keine Freigabe des vorhandenen Wahlkampfwerkzeugs.
