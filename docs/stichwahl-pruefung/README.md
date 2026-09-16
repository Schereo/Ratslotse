# Übergabe: neutrale Prüfung der Stichwahlanalyse

Stand: 16. September 2026. Ablage der bisherigen Ergebnisse auf
`codex/stichwahl-analyse-verstaendlich` für die weitere Durchsicht.

Dieser Ordner enthält die fachliche Prüfung, verständliche Textfassungen und
die eigenständige lokale Vorschau. Er ändert weder die ursprüngliche
Next.js-Seite noch Karte, Wahlbezirksansichten, API oder Potenzialmodell.
Die Dokumente enthalten keine neuen Empfehlungen zur Auswahl von
Wahlkampfgebieten oder zur Ansprache bestimmter Wählergruppen.

## Einstieg

| Datei | Inhalt |
|---|---|
| [stichwahl-prueffassung.md](stichwahl-prueffassung.md) | Ausgearbeitete Faktenkorrekturen, Erläuterungen und Quellen; fachlicher Einstieg. |
| [vorschau/lesefassung.md](vorschau/lesefassung.md) | Kurze Kernaussagen der zuletzt gezeigten Vorschau. |
| [stichwahl-review.md](stichwahl-review.md) | Erstes ausführliches Review mit Fundstellen in den geprüften PR-Ständen. |
| [stichwahl-faktencheck.py](stichwahl-faktencheck.py) | Unabhängige Nachrechnung aus den Quelldateien; importiert kein Potenzialmodell. |
| [stichwahl-faktencheck.json](stichwahl-faktencheck.json) | Vollständiges Ergebnis der Nachrechnung samt Quellen-Prüfsummen. |
| [stichwahl-nachrechnung.json](stichwahl-nachrechnung.json) | Frühere kompakte Nachrechnung; die vollständige Fassung steht in `stichwahl-faktencheck.json`. |
| [vorschau/index.html](vorschau/index.html) | Fertige statische Vorschau mit ausklappbaren Rechenwegen und umschaltbarer Prozent-Bezugsgröße. |

Die Aussagen „nicht integriert“ in den Prüfberichten beziehen sich auf die
Produktanwendung. Die Angaben zur damaligen Verifikation im ersten Review
sind historisch: Die später erstellte Vorschau wurde zusätzlich im Browser
geprüft. Die beiden Markdown-Fassungen ergänzen sich: kurze Erläuterungen
stehen auf der Seite, die ausführlichen Abschnitte in geschlossenen
`details`-Elementen. Die acht wesentlichen Korrekturen sind separat aufklappbar.

## Wesentliche Ergebnisse

- **49.522 Nichtwählende stadtweit**, nach Einbeziehung der Briefwahl. Die
  bisherige Zahl 76.873 enthält 27.351 Briefwählende. Eine entsprechende
  Zahl je Urnenbezirk ist ohne passende Zuordnung der Briefwahl nicht bestimmt.
- **34.335 CDU-Ratswahlstimmen 2026**; 37.430 gehört zu 2021.
  Ratswahlstimmen sind weder „Zweitstimmen“ noch eine genaue Personenzahl.
- **30.731 Stimmen für alle sieben ausgeschiedenen Kandidaturen**;
  29.222 umfasst nur die fünf einzeln ausgewiesenen Kandidaturen.
- **34,8 Prozent und 51,1 Prozent** beschreiben dieselben Briefwahlstimmen
  für Rohr mit unterschiedlichen Bezugsgrößen: alle gültigen Stimmen bzw.
  nur die Stimmen für beide Finalisten.
- Historische Gesamtverhältnisse sind keine individuellen Rückkehr- oder
  Wechselquoten. Veränderungen gültiger Stimmen und der Wählendenzahl sind
  wegen ungültiger Stimmzettel getrennt zu betrachten.
- Szenarien sind Rechenergebnisse unter Annahmen. Die Daten messen keine
  Wirkung je Haustürkontakt; diese Grenze belegt keine allgemeine
  Wirkungslosigkeit persönlicher Gespräche.

Die Belege und Einschränkungen stehen in der ausführlichen Prüffassung.
Die Zahlen für 2026 sind ein eingefrorener vorläufiger Stand, kein Live-Ergebnis.
Korrelationskoeffizienten aus dem ursprünglichen Plan wurden nicht neu geschätzt.

## Vorschau aus diesem Checkout öffnen

Vom Repository-Root aus, mit Python 3.12, ohne Build oder Backend:

```bash
python3.12 -m http.server 3038 --bind 127.0.0.1 --directory docs/stichwahl-pruefung
```

Danach [http://127.0.0.1:3038/vorschau/](http://127.0.0.1:3038/vorschau/) öffnen.
Falls der Port belegt ist, einen anderen wählen. Das übergeordnete
Prüfverzeichnis wird ausgeliefert, damit die Download-Links auf die Berichte
und Nachrechnung funktionieren. Serverzustand, PIDs und Logs sind nicht Teil
der Übergabe. Die bisher gezeigte Instanz auf Port 3028 läuft unabhängig von
dieser Kopie im Arbeitsverzeichnis der ursprünglichen Sitzung.

## Nachrechnung wiederholen

Vom Repository-Root aus:

```bash
python3.12 docs/stichwahl-pruefung/stichwahl-faktencheck.py . > /tmp/stichwahl-nachgerechnet.json
diff -u docs/stichwahl-pruefung/stichwahl-faktencheck.json /tmp/stichwahl-nachgerechnet.json
```

Die Nachrechnung braucht nur die Python-Standardbibliothek und die
Quelldateien im Checkout. Die beiden CSVs unter `quellen-2014/` sind
unveränderte Kopien aus Commit
`a78689b63d225a893c0ab26ae643b3bdea73ab5b` (geprüfter Stand von PR #1385).
Ihre ursprünglichen Pfade und SHA-256-Prüfsummen bleiben im JSON erhalten;
das Skript prüft zusätzlich die mitgelieferten Kopien gegen diese Summen.
Der fremde Git-Commit muss deshalb nicht lokal vorhanden sein.

Geprüft werden unter anderem Stadt-/Bezirkssummen, Stimmenmengen,
Auszählungsstände und die unterschiedlichen Ratswahl-Exportschemata von
2021 und 2026. Bei abweichenden Quelldaten ist ein Unterschied zur
eingefrorenen Nachrechnung möglich und muss inhaltlich geprüft werden.

## Vorschau nach Textänderungen neu erzeugen

`vorschau/build.py` benötigt `markdown-it-py` (im verwendeten Projekt-venv
bereits installiert). Die fertige HTML-Datei ist eingecheckt, daher ist diese
Abhängigkeit nur zum erneuten Erzeugen erforderlich.

```bash
.venv/bin/python docs/stichwahl-pruefung/vorschau/build.py
```

Der Generator liest `vorschau/lesefassung.md`, `stichwahl-prueffassung.md`
und `stichwahl-faktencheck.json`. Er erzeugt `index.html` und `data.js` und
kopiert das vorhandene Ratslotse-Logo. Zusätzliche Überschriften, Quellenlinks
und Einleitungstexte stehen im Generator; `style.css` und `app.js` enthalten
Darstellung und Interaktionen. Nach dem Erzeugen den Browser neu laden.

Die lokale Prüfung der letzten Fassung umfasste die unabhängige Nachrechnung,
JavaScript-Syntax, erreichbare Assets und Downloads sowie das Aufklappen und
Umschalten der Prozent-Bezugsgröße im Browser. Es liegt keine Implementierung
oder Prüfung einer Integration in die Produktanwendung vor.
