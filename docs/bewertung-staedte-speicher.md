# Städte-Speicher: Bewertung nach der Umsetzung

Stand 08.09.2026, nach den sieben PRs aus
[`plan-cities-umsetzung.md`](plan-cities-umsetzung.md). Jede Zahl hier ist
gegen den lokalen Bestand (`data/cities.sqlite`, 166 MB) und die
Rats-Datenbank gemessen; die Skripte dazu stehen am Ende.

## Kurzfassung

Der Speicher steht, der Bestand ist vollständig eingeordnet, und der Block
„Anderswo beschlossen" liefert dort, wo er erscheint, in der Hälfte der Fälle
etwas Brauchbares. Drei Dinge halten ihn zurück, und keins davon ist ein
Datenproblem:

1. **Er erscheint fast nie.** Die Brücke vom Beschluss zur Vorlage läuft über
   `kvonr`, und die trägt nur 274 von 9.059 Beschlüssen. Über die
   Vorlagennummer fänden 6.479 ihre Vorlage. Der Block erschiene damit auf
   486 statt 50 Beschluss-Seiten — ein Fehler, keine Entscheidung.
2. **Er verwechselt Gattung mit Thema.** Ein Oldenburger Bebauungsplan findet
   Osnabrücker Bebauungspläne bei 0,84, ein Haushaltsvollzug die Münsteraner
   Haushaltssatzung bei 0,86. Das Modell misst, wie ein Dokument geschrieben
   ist, nicht, wovon es handelt. Die Einordnung sieht das selbst: Diese
   Treffer tragen `local` oder `one_off`. Ein Filter auf übertragbare Treffer
   halbiert die Abdeckung und nimmt alles Rauschen der Stichprobe heraus.
3. **Die Gegenrichtung ist noch nicht belastbar.** „Was haben andere, was
   Oldenburg nicht hat?" braucht Oldenburgs ganze Geschichte, nicht zwölf
   Monate davon. Von 4.864 Oldenburger Vorlagen mit Beschluss liegen 512 im
   Speicher.

Mehr Daten braucht es — aber gezielt in die Tiefe (Oldenburg vollständig, die
anderen Städte drei Jahre), nicht in die Breite. Und erst nach 1 und 2.

## Was gebaut ist

| PR | Inhalt |
|---|---|
| #1185 | Store, Schema, kanonische Regeln |
| #1186 | OParl-Client, Adapter für ALLRIS 4 und Somacos Session |
| #1187 | Oldenburg als Stadt Nummer null, Wochen-Cron |
| #1188 | Einordnung durch das Modell samt Prüfstand (Golden Set, 45 Vorlagen) |
| #1189 | Chunks, Embeddings, Volltextindex, Nachbarschaften |
| #1191 | Fix: ein kaputter Batch kippt nicht mehr den ganzen Lauf |
| #1190 | „Anderswo beschlossen" im Web |
| #1192 | dasselbe in der App |

## Der Bestand

| Stadt | Papiere | Zeitraum | Anträge/Anfragen | mit Volltext |
|---|---:|---|---:|---:|
| Oldenburg | 710 | 09/2025 – 09/2026 | 62 | 706 |
| Magdeburg | 700 | 09/2025 – 09/2026 | 475 | 691 |
| Potsdam | 700 | 09/2025 – 09/2026 | 583 | 694 |
| Braunschweig | 636 | 09/2025 – 09/2026 | 271 | 635 |
| Osnabrück | 592 | 09/2025 – 09/2026 | 206 | 555 |
| Münster | 376 | 09/2025 – 08/2026 | 49 | 376 |

3.714 Papiere, alle 3.714 eingeordnet (Kosten der Einordnung: rund 1 $), 98 %
mit Volltext. Die Einordnung nach Übertragbarkeit:

| Einstufung | Papiere |
|---|---:|
| `local` — ortsgebunden | 1.293 |
| `adaptable` — anpassbar | 1.233 |
| `one_off` — Formalvorgang | 833 |
| `direct` — direkt übertragbar | 280 |
| `jurisdiction` — andere Zuständigkeit | 75 |

Ein Drittel des Bestands ist damit von vornherein keine Idee, die irgendwohin
wandern könnte. Das ist keine Schwäche des Bestands, sondern die Natur von
Ratsarbeit: Bebauungspläne, Wahlen, Haushaltsvollzug, Zuschüsse an einzelne
Vereine.

**Oldenburg fällt aus der Reihe.** 62 Anträge und Anfragen gegen 583 in
Potsdam. Das liegt nicht an Oldenburgs Rat, sondern am Adapter: Er liest die
Rats-Datenbank, und die kennt Anträge nur als Anlagen von Tagesordnungspunkten
(Kennung `oldenburg:paper:att:…`), nicht als eigene Vorlagen. Für den Block ist
das egal (er geht von der Oldenburger Vorlage aus). Für die Gegenrichtung ist
es ein Loch: Was Oldenburger Fraktionen beantragt haben, ist im Speicher
unterrepräsentiert.

## Wie gut der Block funktioniert

### Abdeckung

Von 710 Oldenburger Papieren im Speicher haben einen fremden Nachbarn:

| Nähe mindestens | Papiere | Anteil |
|---|---:|---:|
| 0,55 (der Index schreibt ab hier) | 699 | 98 % |
| **0,70 (der Block zeigt ab hier)** | **491** | **69 %** |
| 0,75 | 298 | 42 % |
| 0,80 | 147 | 21 % |
| 0,85 | 49 | 7 % |

Zwei Drittel der Oldenburger Vorlagen bekämen also einen Block. Tatsächlich
erscheint er auf **50 Beschluss-Seiten**, und das ist Befund 1: Die Brücke
läuft über `council_decisions.kvonr`, und die ist an 274 von 9.059 Beschlüssen
gefüllt. `template_number` dagegen steht an 6.553, und `council_templates`
übersetzt sie in `kvonr` — `CouncilStore.get_vorlage_by_nr` tut genau das
schon. Über diese Brücke:

| | Beschlüsse mit Vorlage | Vorlagen | Block erscheint auf |
|---|---:|---:|---:|
| über `kvonr` | 274 | 257 | 50 Seiten |
| über `template_number` | 6.479 | 4.864 | 486 Seiten |

Der Rest der 4.864 Vorlagen liegt außerhalb des 12-Monats-Fensters — dazu
unten.

### Qualität: eine Stichprobe von zwölf

Zwölf Oldenburger Vorlagen mit Beschluss-Seite, zufällig über die Themenfelder
verteilt, je die zwei besten Treffer, von Hand gelesen. Bewertet wurde
„handelt es von derselben Sache", nicht „wäre das für Oldenburg sinnvoll" —
das zweite kann nur jemand mit Ratswissen.

| | Oldenburg | bester Treffer | Nähe | Urteil |
|---|---|---|---:|---|
| 1 | Satzung Mittagsverpflegung | BS: Förderrichtlinie Mittagsverpflegung | 0,83 | **gut** |
| 2 | Bebauungsplan N-777 | OS: Bebauungsplan Nr. 674 | 0,84 | Gattung |
| 3 | Parkgebühren-Verordnung | BS: Parkgebührenordnung | 0,83 | **gut** |
| 4 | Ferienpass-Bericht | BS: Entgelte Ferienfreizeiten | 0,71 | schwach |
| 5 | Abfallwirtschaftssatzung | OS: Abfallwirtschaftssatzung | 0,77 | **gut** |
| 6 | Haushaltsvollzug | MS: Haushaltssatzung 2026/27 | 0,86 | Gattung |
| 7 | Statusbericht Digitalisierung | BS: Digitalisierungsstrategie | 0,71 | **gut** |
| 8 | Förderrichtlinien Jugendarbeit | MS: Förderrichtlinien Jugendarbeit | 0,82 | **gut** |
| 9 | Überplanmäßige Bewilligung | BS: Haushaltsvollzug | 0,73 | Gattung |
| 10 | Sanierungsgebiet Innenstadt | MS: Brunnen / BS: Städtebauförderung | 0,75 | gemischt |
| 11 | Bebauungsplan 851 | OS: Bebauungsplan Nr. 674 | 0,81 | Gattung |
| 12 | Konzept öffentliche Toiletten | BS: Anfrage Toiletten / OS: Nette Toilette | 0,78 | **gut** |

Sechs gut, zwei schwach, vier Gattungs-Rauschen. Und das Rauschen hat eine
Signatur: Die Nähe ist dort **hoch** (0,81 bis 0,86), weil das Modell die
Textsorte erkennt — ein Satzungsbeschluss liest sich in jeder Stadt gleich.
Eine Schwelle kann das nicht trennen; sie stünde über den guten Treffern.

Was es trennt, ist die Einordnung. Alle vier Rauschfälle tragen auf beiden
Seiten `local` oder `one_off`; alle sechs guten haben mindestens einen
Treffer mit `direct` oder `adaptable`:

| Regel | Vorlagen im Fenster mit Block |
|---|---:|
| heute (Nähe ≥ 0,70, `one_off` raus) | 361 |
| nur Treffer mit `direct` oder `adaptable` | 190 |
| zusätzlich: Oldenburger Vorlage selbst nicht `local`/`one_off` | 86 |

Die zweite Regel nimmt in der Stichprobe alle vier Rauschfälle heraus und
behält alle sechs guten. Die dritte wäre zu viel: Fall 1 (Oldenburgs Satzung
ist ein `one_off`, Braunschweigs Förderrichtlinie eine Idee) und Fall 3
(Parkgebühren, `local` gegen `direct`) gingen verloren — gerade die beiden
zeigen, wozu der Block da ist. **Empfehlung: die fremde Seite filtern, die
eigene nicht.** Preis: die Abdeckung halbiert sich.

### Wer liefert

Angezeigte Treffer (Nähe ≥ 0,70) von Oldenburg aus, nach Stadt:

| Stadt | Treffer |
|---|---:|
| Osnabrück | 780 |
| Braunschweig | 591 |
| Münster | 486 |
| Potsdam | 372 |
| Magdeburg | 187 |

Die beiden Städte mit demselben Kommunalverfassungsrecht liefern die Hälfte.
Das spricht dafür, bei einer Erweiterung zuerst in Niedersachsen zu suchen.

Und die Nähe ist meist Grenzbereich: 1.290 der 2.416 Kanten liegen zwischen
0,70 und 0,75, nur 80 über 0,85. Das Modell (`paraphrase-multilingual-MiniLM`,
384 Dimensionen) ist das kleinste, das für Oldenburgs eigene „Ähnliche
Beschlüsse" schon reicht. Ein stärkeres Embedding-Modell ist der eine Hebel,
der hier noch nicht gezogen ist — der Speicher hält mehrere Modelle
nebeneinander, genau dafür.

## Die Gegenrichtung

„Was haben andere, was Oldenburg nicht hat?" — gemessen als: übertragbare
fremde Papiere (`direct`, `adaptable`) ohne Oldenburger Nachbarn ab 0,70.

| Themenfeld | ohne Gegenstück | von |
|---|---:|---:|
| Verkehr | 138 | 187 |
| Soziales & Gesundheit | 128 | 178 |
| Verwaltung & Digitales | 125 | 151 |
| Klima & Umwelt | 104 | 169 |
| Kultur & Sport | 80 | 114 |
| Bauen & Wohnen | 80 | 138 |
| Sicherheit & Ordnung | 74 | 88 |
| Finanzen | 68 | 84 |

922 von 1.290. Die Zahl ist **nicht belastbar**, und zwar aus einem Grund:
Oldenburg liegt mit zwölf Monaten im Speicher. Ob Oldenburg ein
Hitzeaktionsplan fehlt, entscheidet nicht das letzte Jahr, sondern ob der Rat
ihn 2022 beschlossen hat. Die Rats-Datenbank kennt 4.864 Vorlagen mit
Beschluss seit 2018; im Speicher sind 512. Bevor Oldenburg nicht vollständig
drin ist, sagt jede Lücken-Liste vor allem, was der Speicher nicht weiß.

Der Weg dafür ist in Phase 0 gemessen und steht im
[Bericht](phase0-andere-staedte.md): Nähe taugt nicht als Schwelle,
Instrument-Cluster brauchen 0,86 plus gleiches Themenfeld, dann eine
Gegenprobe durch das Modell mit Belegen. Das ist kein Block auf einer Seite,
sondern eine eigene Auswertung.

## Braucht es mehr Daten?

Ja — in die Tiefe, nicht in die Breite, und erst nach den beiden Fixes oben.

**1. Oldenburg vollständig.** Die Rats-Datenbank hat alles seit 2018; der
Adapter liest sie nur ab `since`. Für die Gegenrichtung ist das die
Voraussetzung, für den Block ändert es nichts (er geht vom Beschluss aus, und
der ist da). Kosten: etwa 4.400 Vorlagen mehr einzuordnen, rund 1,20 $, kein
Netz.

**2. Die anderen Städte drei Jahre statt eins.** Osnabrück hält 19.500
Papiere vor, Braunschweig 49.000 — das Fenster ist die Grenze, nicht die
Quelle. Drei Jahre über fünf Städte sind grob 9.000 Papiere mehr, Einordnung
rund 3 $. Der Engpass ist die Ernte: ein Aufruf je Sekunde je Stadt, also
Stunden je Stadt, einmalig. Dafür bekommt jeder Oldenburger Beschluss
dreimal so viele Kandidaten, und die Gegenrichtung sieht, was andere vor
zwei Jahren beschlossen haben.

**3. Mehr Städte — später, und dann Niedersachsen.** Die Hälfte der Treffer
kommt aus Osnabrück und Braunschweig. Welche weiteren niedersächsischen
Städte OParl anbieten, ist noch nicht gemessen; die Registry trägt die fünf
aus Phase 0. Eine sechste Stadt bringt weniger als ein drittes Jahr der
vorhandenen.

**Was mehr Daten nicht lösen:** das Gattungs-Rauschen (das löst die
Einordnung), die fehlende Brücke (ein Fehler), und die Frage, ob eine fremde
Idee für Oldenburg taugt (das kann nur ein Mensch mit Ratswissen; der
[Bewertungsbogen](https://claude.ai/code/artifact/9d483ac0-f5fe-48da-8508-0a7ff0dd3547)
aus Phase 0 wartet darauf).

**Was nicht fehlt:** Text. 98 % der Papiere tragen Volltext, und der
Objektvektor entsteht aus Titel plus Zusammenfassung plus Instrument — mehr
Text je Papier änderte daran nichts.

## Was als nächstes geschehen sollte

In dieser Reihenfolge; die ersten beiden sind klein, das dritte ein
Cron-Parameter, ab dem vierten wird es ein eigenes Vorhaben.

1. **Brücke über die Vorlagennummer.** Ein Fehler im Endpunkt, zehnmal so
   viele Seiten mit Block. Kein Produktentscheid.
2. **Fremde Treffer auf `direct`/`adaptable` filtern.** Nimmt das
   Gattungs-Rauschen heraus, halbiert die Abdeckung. Ein Produktentscheid,
   mit den Zahlen oben.
3. **Oldenburg vollständig, andere Städte drei Jahre.** `since` im Cron,
   einmal laufen lassen, rund 4 $.
4. **Die Gegenrichtung als eigene Auswertung** — nach 3, nicht davor. Mit
   der Phase-0-Strecke (Cluster, Themenfeld, Gegenprobe) und Belegen, als
   Seite oder als Bericht. Das ist die Idee aus dem ursprünglichen Auftrag;
   der Block ist ihr kleiner Bruder.
5. **Ein Ratsmitglied an den Bewertungsbogen.** 29 Lücken, 10 Fragen, 11
   Nachbarschaften warten auf ein Urteil. Ohne das bleibt „brauchbar" ein
   Wort von mir.
6. **Freie Suche über den Speicher.** Der Volltextindex ist gebaut und hat
   kein Fenster nach vorn. „Was haben andere zu Hitzeschutz?" ist eine
   Suchzeile, keine Nachbarschaft — und die Formulierungsempfindlichkeit aus
   Phase 0 gilt, s. `stadion-validierung`.
7. **Ein zweites Embedding-Modell im Vergleich.** Der Speicher trägt mehrere
   nebeneinander; das heutige ist das kleinste. Erst messen, dann wechseln.
8. **Schalter `andere-staedte` auf Prod**, sobald 1 und 2 drin sind.

## Messskripte

Alle Zahlen dieser Seite entstehen aus `data/cities.sqlite` und
`data/council.sqlite` mit `sqlite3` und der `neighbors`-Tabelle für das
Modell `paraphrase-multilingual-MiniLM-L12-v2`. Abdeckung: `MAX(score)` je
`a_id LIKE 'oldenburg:%'` gegen die Schwellen. Brücke: `council_decisions`
über `template_number` auf `council_templates.kvonr`, Schnitt mit den
Oldenburger Papieren im Speicher. Gegenrichtung: fremde Papiere mit
`transfer IN ('direct','adaptable')` ohne Kante `b_id LIKE 'oldenburg:%'`
ab 0,70. Stichprobe: `random.seed(8)` über die Vorlagen mit Beschluss, je
Themenfeld höchstens eine, bis zwölf.
