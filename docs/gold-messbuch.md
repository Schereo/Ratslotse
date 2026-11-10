# Messbuch: Gold-Läufe „Frag den Rat“

Hier stehen alle Gold-Läufe, die eine Änderung an der **Pipeline** von „Frag
den Rat“ bewertet haben, also Suche, Kontext, Notizen oder Regeln. Modelle
vergleicht der [Modell-Prüfstand](modell-pruefstand.md); der wird aus
`eval/results/pruefstand/` erzeugt und kennt keine Gold-Läufe. Dieses Messbuch
wird von Hand geführt: **Wer einen Gold-Lauf macht, trägt ihn hier ein**, auch
wenn er nichts gebracht hat. Gerade dann.

Der Anlass: Die Belegnotizen hatten im Oktober „+5 Pp“ gebracht und waren für
Prod vorgesehen. Im November brachten sie auf Prod nichts und kosteten 8 s je
Antwort. Warum, ließ sich nur aus Commits und Notizen zusammensuchen (s. u.).

## Wie man misst

```bash
gh workflow run ops-gold.yml -f umgebung=prod -f weg=ask -f label=<name>          # Prod
gh workflow run ops-gold.yml -f umgebung=dev  -f weg=ask -f label=<name> --ref dev  # dev
```

- **27 Fälle** aus `eval/cases_deep_gold.json`, Richter Claude Opus 5.5, ≈ 1,1 $
  je Lauf (Richter) plus die Antworten selbst (≈ 0,1 $). `-f ohne_richter=true`
  misst nur den Kontext-Recall und kostet nur die Antworten.
- **Streuung:** derselbe Code ergab 51 % und 45 % (17.10.2026), einzelne Fälle
  schwanken um bis zu ±30 Pp. Eine Änderung unter ~5 Pp ist aus einem Lauf je
  Seite nicht zu lesen; dafür braucht es zwei.
- **Kontext-Recall** (Belege im Prompt / Belege insgesamt) braucht keinen
  Richter und streut nicht. Er sagt, ob die *Suche* besser wurde.
- **Fehlerarten** der verfehlten Fakten: *weggelassen* (Material im Prompt,
  Antwort lässt es weg), *nicht gefunden*, *teilweise*, *abgeschnitten*
  (gefunden, aber hinter dem Prompt-Schnitt), *ohne Material*.
- **Bestanden** ist seit #1733 (18.10.2026) bei Punktfragen milder, die
  Bestanden-Zahlen davor und danach sind nicht vergleichbar.
- **dev und Prod** haben verschiedene Daten und verschiedene Maschinen. Die
  Abdeckung lässt sich grob vergleichen, die Dauer gar nicht (dev braucht
  ≈ 48 s je Antwort, Prod ≈ 28 s). Vorher/nachher immer auf derselben Umgebung.
- **Ergebnisse** liegen auf dem jeweiligen Server unter
  `~/app/data/eval_gold/ask-<label>.json`. Nicht während eines Laufs nach dev
  mergen: Der Deploy startet die Dienste mitten im Lauf neu.

**Zeit bis zum ersten Wort** misst der Gold-Lauf nicht (er speichert nur die
Gesamtdauer), und `qa_timings` steht nicht im Journal. Am 09.11.2026 lief dafür
eine eigene Probe direkt auf dem Server: die 27 Fragen ohne Richter, je Frage
die Zeit bis zum ersten Token beim Client und die `timings` aus dem
`done`-Ereignis.

## Läufe

Abdeckung = Mittel über 27 Fälle. Recall = Belege im Prompt / Belege gesamt.
„wegg.“ = verfehlte Fakten, deren Material im Prompt stand. Dauer = Median der
Gesamtdauer je Antwort.

| Datum | Umgebung | Label | Stand | Abdeckung | best. | Recall | wegg. | Dauer |
|---|---|---|---|---:|---:|---:|---:|---:|
| 17.10. | dev | `okt-basis-c` / `-d` | Grundlinie, alle Schalter aus | 57 % / 56 % | 11 / 12 | 127/198 | 53 / 50 | 32 s / 30 s |
| 17.10. | dev | `okt-diaet-a` / `-b` | + Kontext-Diät (#1725) | 55 % / 54 % | 11 / 9 | 127/198 | 55 / 56 | 34 s / 32 s |
| 18.10. | dev | `okt-notizen-a` / `-b2` | + Belegnotizen **und** 24 statt 6 Beiträge Aussprache (#1726) | 59 % / 60 % | 13 / 14 | 126/198 | 45 / 41 | 32 s / 33 s |
| 18.10. | dev | `okt-kontrolle-a` / `-b` | + Diät ohne Fraktionsfragen, mildere Punktfragen-Regel (#1733) | 60 % / 61 % | 19 / 18 | 126/198 | 42 / 40 | 36 s / 33 s |
| 18.10. | dev | `okt-suche-a` / `-b` | + Suche-Ausbau, Vorgang als Zeitleiste (#1736) | 62 % / 62 % | 19 / 19 | 135/198 | 47 / 45 | 33 s / 32 s |
| 09.11. | Prod | `nov09-prod-a` | v3.0.0: Suche-Ausbau, Diät, Akte; **ohne** Belegnotizen, ohne Nachrecherche | 62 % | 18 | 153/198 | 52 | 27 s |
| 09.11. | Prod | `nov09-prod-belegnotizen` | wie oben **mit** Belegnotizen | 61 % | 18 | 153/198 | 49 | 35 s |
| 09.11. | dev | `nov09-dev-vor` | alle Schalter, Stand vor #1801 | 57 % | 15 | 135/198 | 47 | 49 s |
| 09.11. | dev | `nov09-dev-nach` | + #1801 (Personenreden, Komposita, „seitdem“ mit Datum, Gold-Pflege) | 63 % | 19 | 137/200 | 46 | 48 s |

Zu `nov09-dev-vor`/`-nach`: #1801 hat drei Gold-Fälle umgestellt (afaa,
Wärmewende-Beirat X4, Parkgebühren X3). Ohne diese drei: 56,9 % → 61,4 %,
bestanden 13 → 16 von 24. Den größten Sprung machte `behrens-baumschutz`
(18 % → 65 %): Die Personensuche nahm bis dahin die 120 *neuesten* Beiträge
eines Redners, und die reichten bei Paul Behrens nicht bis 2024 zurück.

### Teilläufe (`-f nur=…`)

Einzelne Fälle, um einen gezielten Fix zu prüfen. Nicht mit den vollen Läufen
oben vergleichen: Die Auswahl sind gerade die schwachen Fälle.

| Datum | Umgebung | Label | Stand | Fall | Abdeckung |
|---|---|---|---|---|---:|
| 09.11. | dev | `nov09-dev-nach-1803` | + jüngste Aussprache nach der Akte (#1803) | trinkwasserspender-draussen | 8 % |
| | | | | bahnuebergang-am-stadtrand-verlauf | 40 % |
| | | | | heidbrook-zusagen | 39 % |
| | | | | behrens-baumschutz | 71 % |
| | | | | parkgebuehren-mehreinnahmen | 62 % |
| | | | | klinikum-buergschaften-stand | 62 % |
| 09.11. | dev | `nov09-dev-nach-1811` | + Zusagen auch bei Termin- und Faktenfragen (#1811) | trinkwasserspender-draussen | 33 % |
| | | | | bahnuebergang-am-stadtrand-verlauf | 40 % |
| | | | | heidbrook-zusagen | 33 % |

#1803 griff bei den drei oberen Fällen nicht: Der Forschungsplan schaltete bei
Termin- und Faktenfragen die Aussprache ganz ab, und damit auch den neuen
Block. #1811 holt in diesem Fall die Zusagen der Verwaltung trotzdem; beim
Trinkwasserspender steht der fehlende Beleg seitdem im Kontext. Bahnübergang
und Heidbrook fehlt weiter Material in der Suche, nicht in den Zusagen.

## Zeit bis zum ersten Wort (Prod, 09.11.2026)

| | Erstes Wort (Median) | Gesamt (Median) | Analyse | Suche (davon Rerank) | Notizen |
|---|---:|---:|---:|---:|---:|
| ohne Belegnotizen | 26,9 s | 29,1 s | 3,3 s | 6,6 s (4,8 s) | – |
| mit Belegnotizen | 30,6 s | 34,1 s | 0,0 s* | 6,4 s | 6,8 s |

\* Im Lauf mit Notizen lag die Analyse noch im Zwischenspeicher, weil dieselben
Fragen kurz vorher gestellt worden waren. Um sie bereinigt kosten die Notizen
je Frage **≈ 8 s** bis zum ersten Wort: die 6,8 s des Notiz-Schritts plus einen
längeren Prompt für das Antwortmodell. Ohne Notizen liegen zwischen dem Ende
der Suche und dem ersten Wort rund 17 s: der Kontext wird gebaut, und das
Antwortmodell (GPT-6 Luna) denkt nach, bevor es schreibt. Dort liegt der
größte Hebel für die Wartezeit, nicht in der Suche.

## Was daraus folgt

### Belegnotizen: Warum der Oktober-Gewinn nicht wiederkam

Am 18.10. ging die Abdeckung von 55/54 % (Diät) auf 59/60 % (Notizen), und
„weggelassen“ fiel von 55/56 auf 45/41. Am 09.11. auf Prod, Notizen an gegen
aus: 62 % → 61 %, „weggelassen“ 52 → 49, dafür 8 s mehr Wartezeit. Drei Gründe,
in dieser Reihenfolge:

1. **Der Oktober-Schritt hat zwei Dinge gemessen.** #1726 brachte die Notizen
   *und* hob die Aussprache zu den acht besten Beschlüssen von 6 auf 24
   Beiträge (`ANKER_AUSSPRACHE_MAX`). Die zweite Hälfte hängt am Schalter
   `kontext-diaet` und ist auf Prod längst an. Der November-Vergleich misst die
   Notizen zum ersten Mal **allein**, und allein bringen sie nichts Messbares.
2. **Anderes Modell.** Im Oktober schrieb Gemini 3.1 Flash Lite die Notizen
   (`EXPAND_MODEL`). Seit #1783 (08.11.2026, Nutzereingaben nur noch über
   EU-Anbieter) ist es GPT-5.6 Luna über Azure EU, mit voller Denkstufe; die
   niedrige Stufe aus #1795 gilt nur für Analyse, Suchbegriffe und Zerlegung.
   Im Oktober kosteten die Notizen auf dev kaum Zeit (Dauer 32/33 s gegen
   34/32 s), jetzt 8 s.
3. **Die Suche ist besser geworden.** Der Kontext-Recall stieg von 126/198
   (Oktober) auf 153/198 (Prod, November). Die Notizen decken nur 14
   Beschlüsse und 12 Wortbeiträge ab; je mehr gutes Material im Prompt steht,
   desto weniger fällt eine Vorauswahl ins Gewicht.

**Entscheidung 09.11.2026:** Belegnotizen auf Prod aus. Bevor sie wieder an
gehen: mit niedriger Denkstufe oder einem schnellen EU-Modell messen, zwei
Läufe je Seite, und die Zeit bis zum ersten Wort mit.

### Lehre für künftige Schalter

Ein Schalter, der zwei Dinge auf einmal ändert, lässt sich nicht bewerten.
Jede Änderung bekommt ihre eigene Messung, auch wenn sie im selben PR landet.
Und wechselt das Modell unter einem Schritt, gilt seine alte Messung nicht mehr.
