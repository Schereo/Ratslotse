# Phase 0: Was andere Räte beschließen — der Probelauf

Stand: 07.09.2026. Fünf Städte, zwölf Monate, 2.967 Vorlagen geerntet, 2.946
davon per Sprachmodell eingeordnet, gegen 8.199 Oldenburger Beschlüsse und
5.067 Vorlagen gerechnet. Alle Zahlen hier sind gemessen. Gesamtkosten des
Probelaufs: **3,49 $**.

Der Plan dazu steht in
[`plan-best-practice-kommunen.md`](plan-best-practice-kommunen.md); dieses
Dokument ist sein Prüfstand.

## 1. Das Ergebnis in vier Sätzen

**Der Datenweg trägt.** Osnabrück, Braunschweig, Münster, Potsdam und
Magdeburg liefern über OParl zusammen rund 3.000 Anträge, Anfragen und
Beschlussvorlagen je Jahr, praktisch alle mit Volltext (99,5 %), dazu 22.494
Tagesordnungspunkte, von denen 12.948 ein Ergebnis tragen.

**Die Einordnung funktioniert, aber nur mit dem richtigen Prompt.** Die
Entscheidung, auf die es ankommt — taugt eine fremde Vorlage als Idee für
Oldenburg oder nicht —, trifft das beste Modell in rund 87 % der Fälle richtig
(fünf Läufe, 84 bis 91 %). Mit demselben Modell und einem schwächeren Prompt
waren es 73 %. Ein einzelner Lauf zeigte 98 %; das war Glück, s. § 2.

**Der gezielte Modus schlägt das freie Brainstorming deutlich.** „Was haben
andere zu diesem Thema gemacht?" liefert präzise Treffer. „Was fehlt uns?"
liefert brauchbare Kandidaten erst, nachdem drei Filter hintereinander
geschaltet sind — und bleibt der wackligere Teil.

**Was jetzt fehlt, ist dein Urteil.** 29 Lücken-Kandidaten, 10 Themenfragen
und 11 Nachbarschaften liegen zur Bewertung bereit.

## 2. Der Modellvergleich

Maßstab sind 45 Vorlagen, die ich von Hand eingeordnet habe: Themenfeld,
Übertragbarkeit, Zuständigkeit. Die Stichprobe ist geschichtet über Städte und
Vorlagenarten. Jedes Modell bekam denselben Prompt und dieselben 45 Texte.

Die entscheidende Spalte ist **taugt/taugt nicht**: Ob ein Modell eine fremde
Vorlage als übertragbar einstuft oder nicht, ist die eine Entscheidung, die das
Produkt später trifft. Die feinere Fünf-Stufen-Einteilung und das Themenfeld
sind Beiwerk.

| Modell | geliefert | taugt/taugt nicht | Übertragbarkeit | Themenfeld | Zuständigkeit | $/1000 | Sek. für 45 |
|---|---:|---:|---:|---:|---:|---:|---:|
| **deepseek/deepseek-v4-flash** | 100 % | **98 %** ¹ | 87 % | 84 % | 56 % | **0,43** | 143 |
| qwen/qwen3.8-flash | 100 % | 96 % | 89 % | 82 % | 67 % | 1,07 | 235 |
| tencent/hy4-preview | 100 % | 93 % | 67 % | 87 % | 69 % | 20,74 | 1036 |
| minimax/minimax-m3 | 98 % | 89 % | 80 % | 82 % | 77 % | 0,63 | 42 |
| z-ai/glm-5.3-flash | 100 % | 87 % | 80 % | 87 % | 69 % | 0,40 | 115 |
| openai/gpt-5.6-luna | 100 % | 87 % | 80 % | 80 % | **80 %** | 0,42 | **26** |
| mistralai/mistral-small-2603 | 100 % | 80 % | 69 % | 73 % | 64 % | 0,23 | 10 |
| z-ai/glm-4.7-flash | 87 % | 79 % | 67 % | 79 % | 67 % | 2,05 | 861 |
| tencent/hy3 | 100 % | 78 % | 69 % | 89 % | 67 % | 0,54 | 96 |
| google/gemini-2.5-flash | 100 % | 78 % | 69 % | 80 % | 67 % | 0,67 | 9 |
| meta-llama/llama-4-scout | 100 % | 73 % | 64 % | 71 % | 64 % | 0,12 | 52 |
| xiaomi/mimo-v2.5 | 100 % | 73 % | 58 % | 89 % | 67 % | 0,31 | 598 |
| deepseek/deepseek-v4-pro | 100 % | 71 % | 60 % | 89 % | 71 % | 2,67 | 170 |
| nvidia/nemotron-3-super-120b | 100 % | 67 % | 58 % | 89 % | 64 % | 0,58 | 305 |
| deepseek/deepseek-v4-flash-0731 | **84 %** | 66 % | 55 % | 84 % | 74 % | 1,26 | 2296 |
| google/gemini-2.5-flash-lite | 100 % | 58 % | 47 % | 76 % | 60 % | 0,12 | 6 |

¹ Ein Lauf. Fünf Wiederholungen ergaben 84 bis 91 % — s. den Nachtrag unten.
**Jede Zahl in dieser Tabelle ist ein einzelner Lauf** und trägt dieselbe
Unsicherheit von rund ±7 Punkten.

Die Auswahl folgt der OpenRouter-Wochenrangliste (Stand 06.09.2026: Hy4
preview, GPT-5.6 Luna, GLM 5.3 Flash, DeepSeek V4 Flash 0731, MiniMax M3, Hy3,
Nemotron 3, GLM 5.3, MiMo-V2.5), ergänzt um die Modelle, die das Projekt schon
benutzt, und um zwei europäische und ein Meta-Modell.

### Was daraus folgt

**`deepseek/deepseek-v4-flash` ist die Empfehlung.** Beste Trefferquote,
zweitgünstigster Preis, vollständige Lieferung. Für den ganzen Bestand von
2.906 Vorlagen kostete der Lauf **0,91 $** und dauerte 50 Minuten.

**Das teuerste Modell ist nicht das beste.** `hy4-preview`, das derzeit
meistgenutzte Modell auf OpenRouter, kostet das **48-fache** und liegt bei der
entscheidenden Frage fünf Punkte zurück. Es denkt lange (17 Minuten für 45
Vorlagen) und teuer.

**`deepseek-v4-flash-0731`, das du genannt hattest, ist die schlechteste Wahl
der DeepSeek-Familie.** Es lieferte nur 84 % der Ergebnisse, brauchte 38
Minuten und kostet dreimal so viel wie die rollende Fassung `deepseek-v4-flash`
bei schlechterer Trefferquote. Der Grund für die Ausfälle: Es ist ein
Reasoning-Modell, dessen Denk-Tokens gegen `max_tokens` zählen; ist das Budget
aufgebraucht, kommt eine **leere Antwort mit Status 200** zurück. In
[`kern/llm.py`](../kern/llm.py) steht dafür der Token-Boden `MODEL_PARAMS` —
und genau dieser Modellname fehlt dort. **Wer ihn einträgt, repariert damit
auch jede andere Verwendung.**

**Zuständigkeit ist die schwächste Größe.** Kein Modell kommt über 80 %,
der Sieger liegt bei 56 %. Das Feld hat als einziges keinen geschärften Prompt
bekommen; es ist Baustelle, nicht Befund. Für Phase 1 heißt das: entweder
nachschärfen oder das Feld weglassen.

**Für Nutzerfragen bliebe alles beim Alten.** Deine Einordnung ist richtig,
dass hier nur öffentliche Ratsdokumente anderer Städte durchs Modell gehen und
die ZDR-Pflicht deshalb nicht dieselbe Rolle spielt. Zwei Anmerkungen dazu: Die
Beschränkung kostete messbar — `gpt-5.6-luna` lieferte mit ihr nur **53 %** der
Ergebnisse, ohne sie **100 %** bei doppelter Geschwindigkeit. Und die Umsetzung
gehört nicht in den globalen Schalter `NWZ_OPENROUTER_ROUTING`, sondern in den
Aufruf: `chat_complete` reicht ein mitgegebenes `extra_body["provider"]` mit
Vorrang durch, die Einordnung der Fremdvorlagen kann ihre Lockerung also selbst
mitbringen, ohne dass die KI-Frage sie erbt.

### Der Prompt schlägt das Modell

| | taugt/taugt nicht | Übertragbarkeit |
|---|---:|---:|
| `deepseek-v4-flash`, Prompt-Fassung 1 | 73 % | 60 % |
| `deepseek-v4-flash`, Prompt-Fassung 2 | **98 %** | **87 %** |
| `deepseek-v4-pro` (elfmal teurer), Fassung 1 | 71 % | 60 % |

> **Nachtrag 07.09.2026, nach fünf Wiederholungen:** Die 98 % waren ein
> einzelner Lauf. Dieselbe Fassung, dasselbe Modell, fünfmal gemessen — mit
> und ohne Provider-Beschränkung, mit Batchgröße 4 und 6 — ergibt **84 bis
> 91 %**, im Mittel rund 87 %. Bei 45 Fällen ist ein Punkt knapp ein halber
> Fall; die Spanne ist Rauschen, kein Einstellungseffekt. **Jede einzelne Zahl
> in diesem Abschnitt ist ein Lauf und trägt dieselbe Unsicherheit** — die
> Rangfolge der Modelle bleibt davon unberührt, der Abstand zwischen
> Prompt-Fassung 1 und 2 (73 gegen 87) ebenso, aber „98 %" sollte niemand
> zitieren. Die Suite `eval/run_cities_transfer.py` sagt das jetzt selbst und
> zählt erst unter 80 % als Regression.

Alle zwölf Fehler der ersten Fassung gingen in dieselbe Richtung: Das Modell
hielt **laufende Pflichtgeschäfte** für übertragbare Ideen — Haushaltsvollzug,
jährliche Gebührenkalkulation, Jahresabschluss, Zuschuss an einen bestimmten
Verein, Feststellung eines Wahlergebnisses. Kein einziger Fehler ging in die
andere Richtung. Die zweite Fassung zählt diese Fälle namentlich auf und
schärft „ortsgebunden" um Vereine, Quartiere und einzelne Gebäude. Das genügte.

Die Lehre für Phase 1: **Ein Golden Set mit 45 handeingeordneten Vorlagen
kostet einen halben Tag und ist der Hebel.** Er gehört in `eval/`, wie die
Tragweite-Prüfung.

## 3. Der Bestand

| Stadt | Vorlagen | mit Volltext | ⌀ Zeichen | Zeitraum | TOPs | davon mit Ergebnis |
|---|---:|---:|---:|---|---:|---:|
| Osnabrück | 555 | 555 | 8.877 | 09/25–09/26 | 2.194 | 1.018 (46 %) |
| Braunschweig | 636 | 635 | 7.027 | 09/25–09/26 | 4.507 | 2.510 (56 %) |
| Münster | 376 | 376 | 6.861 | 09/25–08/26 | 2.793 | 1.272 (46 %) |
| Potsdam | 700 | 694 | 3.274 | 09/25–09/26 | 3.247 | 1.608 (50 %) |
| Magdeburg | 700 | 691 | 3.578 | 09/25–09/26 | 9.753 | 6.540 (67 %) |
| **Summe** | **2.967** | **2.951** | | | **22.494** | **12.948 (58 %)** |

Nach Art: 1.124 Anträge, 1.041 Beschlussvorlagen, 802 Anfragen. Bei Potsdam und
Magdeburg griff eine Obergrenze von 700 je Stadt, die Anträge und Anfragen
bevorzugt — von dort fehlen also die Verwaltungsvorlagen. Ortsteil-Ebene ist
überall ausgeschlossen: In Braunschweig sind 128 der 267 Gremien Stadtbezirksräte,
deren Kleinanträge Oldenburg nicht kennt.

**Korrektur zum Plan:** Dort stand, Magdeburg liefere so gut wie keine
Ergebnisse. Das war ein Messfehler — über die Sitzungen geholt trägt Magdeburg
mit 67 % die **beste** Ergebnisquote aller fünf Städte. Der erste Messweg
(`body.agendaItem`) liefert dort nur einen unbrauchbaren Ausschnitt.

### Was beim Ernten hakte, und woran es lag

Vier Fallen, alle gemessen, alle für Phase 1 relevant:

**Somacos Session verliert den Zeitfilter im `next`-Link.** Seite 1 und 2 einer
gefilterten Papierliste tragen `created_since` im Folge-Link, ab Seite 3 fehlt
er. Wer `next` folgt, blättert ab da unbemerkt den **Gesamtbestand seit 1997**
ab und hält das Ergebnis für gefiltert. Münster lieferte so 6.000 Papiere, von
denen nur 376 ins Fenster fielen. Richtig ist, `page=N` samt Filter bei jeder
Anfrage selbst zu setzen.

**Magdeburgs OParl nennt Datei-URLs, die es nicht gibt.** Sowohl `accessUrl`
als auch `downloadUrl` antworten mit **404** — bei jedem geprüften Dokument.
Die Dateien sind da, nur unter einem anderen Pfad: `getfile.asp?id=<Datei-ID>&type=do`
liefert dasselbe PDF. Ohne diese Umschreibung wären 700 Magdeburger Vorlagen
textlos geblieben.

**ALLRIS 4 sortiert alt nach neu und ignoriert `limit`.** Die neuesten Papiere
stehen auf der **letzten** Seite (Osnabrück: Seite 1.955 von 1.955), die
Seitengröße ist fest 10, und `created_since` liefert null Treffer, weil
`created` und `modified` bei allen Papieren auf `2000-01-01` stehen. Der
einzige Weg ist rückwärts blättern, bis die Daten aus dem Fenster fallen. Alte
Osnabrücker Papiere tragen zudem **gar kein Datum** — wer undatierte Zeilen als
„noch im Fenster" zählt, blättert bis zum Anfang.

**Fünf Threads auf einer SQLite-Datei sind einer zu viel.** Der Osnabrück-Faden
starb zweimal still an `database is locked`, während die anderen vier
weiterliefen — ohne Log-Zeile, weil das Schreiben des Fehlers selbst am
gesperrten Log scheiterte. In Phase 1 heißt das: ein Schreiber je Datenbank,
oder je Stadt eine eigene Datei und am Ende zusammenführen.

## 4. Die beiden Modi im Vergleich

Deine offene Frage war, ob das Ganze gezielt („was haben andere zu Thema X
gemacht?") oder als freies Brainstorming („was fehlt uns?") funktionieren soll.
Phase 0 hat beides gebaut. Der Befund ist eindeutig genug, um ihn hier
hinzuschreiben.

### Modus A — gezielt, vom Thema oder vom Beschluss aus

Funktioniert auf Anhieb. Zu einem Oldenburger Beschluss stehen die
Entsprechungen der Nachbarstädte präzise daneben:

| Oldenburger Beschluss | nächster fremder Treffer | Nähe |
|---|---|---:|
| Kommunale Wärmeplanung: Oldenburger Wärmeplan | Braunschweig: Kommunale Wärmeplanung — Endbericht | 0,84 |
| Anpassung der Schulbezirke der Grundschulen | Braunschweig: 13. Satzung zur Änderung der Schulbezirkssatzung | 0,81 |
| Bebauungsplan N-777 G (Fliegerhorst) | Münster: Bebauungsplan Nr. 648 — Satzungsbeschluss | 0,84 |

Eine Schwäche ist gemessen und muss in Phase 1 behoben werden: **Die Trefferliste
hängt an der Formulierung der Frage.** Dreimal dieselbe Sache gefragt:

| Frage | erster Treffer |
|---|---|
| „Hitzeaktionsplan" | Braunschweig: Konzept zur Hitzeaktionsplanung (0,84) ✓ |
| „Hitzeschutz und Hitzeaktionsplan" | Braunschweig: Konzept zur Hitzeaktionsplanung (0,81) ✓ |
| „Hitzeschutz und Hitzeaktionsplan **für die Stadt**" | Osnabrück: Kommunale **Wärm**eplanung (0,86) ✗ |

Drei Wörter mehr, und die Liste kippt: „Wärme" und „Hitze" liegen im
Einbettungsraum eng beieinander, inhaltlich sind sie fast Gegenteile. Reine
Embeddings reichen also nicht; es braucht dieselbe Strecke wie die KI-Frage,
mit Volltextsuche und Cross-Encoder-Nachsortierung. Deine Regel, jede
Such-Verbesserung an den Stadion-Fragen zu prüfen, gilt hier genauso.

### Modus B — frei, „was fehlt uns?"

Trägt erst nach drei Filtern hintereinander, und der Weg dahin war lehrreich.

*Erstens* taugt der Ähnlichkeitswert **nicht** als Schwelle: Der Median der
Ähnlichkeit einer fremden Vorlage zum nächsten Oldenburger Beschluss liegt bei
**0,70**, weil deutscher Verwaltungstext sich überall gleicht. Eine feste Grenze
trennt hier nichts.

*Zweitens* klebte die erste Cluster-Bildung bei 0,80 Ähnlichkeit
Zusammenhangloses aneinander — „Gewässerzustandsbericht" mit
„Trinkwasservertrag kündigen". Erst die Schwelle 0,86 **plus** die Bedingung,
dass alle Mitglieder im selben Themenfeld liegen, ergab brauchbare Gruppen: aus
122 wurden 54 Cluster, dafür stimmige.

*Drittens* entscheidet nicht die Rechnung, sondern ein Sprachmodell mit
Belegen: Zu jedem Cluster gehen die drei nächsten Oldenburger Beschlüsse, die
zwei nächsten Vorlagen und die Volltextsuche als Belege in einen Prompt, der
streng fragt: Hat Oldenburg **genau das** schon? Ergebnis über 54 Cluster:
**29 fehlt, 13 teilweise, 11 vorhanden** — für 0,014 $.

Dass die Gegenprobe wirkt, zeigen ihre Treffer: Sie erkennt den Oldenburger
Wärmeplan, die Digitalisierungsstrategie von 2023 und die Bewohnerparkzone
Haarenesch als „vorhanden" und begründet es mit dem richtigen Beschluss. Und
sie trifft die feinen Fälle: Zur Zweckentfremdungssatzung sagt sie „bisher nur
politische Anträge, keine Verabschiedung" — was genau dem Stand entspricht.

### Empfehlung

**Beides bauen, aber in dieser Reihenfolge.** Modus A ist die verlässliche
Grundfunktion und gehört in Phase 1 — als Block auf der Beschluss-Seite und als
Freitext-Frage. Modus B ist der Teil mit dem größeren Reiz und dem größeren
Risiko; er gehört in Phase 2 und braucht die drei Filter oben, sonst produziert
er Unsinn mit Selbstbewusstsein.

## 5. Was zu bewerten ist

Bereit liegen:

- **29 Lücken-Kandidaten** (Modus B), je mit Instrument, den Städten, bis zu
  drei Beispielvorlagen und der Begründung, warum Oldenburg dazu nichts hat.
- **10 Themenfragen** (Modus A) mit je drei Treffern.
- **11 Nachbarschaften** (Modus A) von einem Oldenburger Beschluss aus.

Die Schwelle aus dem Plan: mindestens 40 % der Lücken und 60 % der
Nachbarschaften brauchbar. Die ersten zwölf Lücken zur Ansicht:

| | Instrument | Städte |
|---|---|---|
| L01 | Zweckentfremdungssatzung erlassen | Braunschweig, Osnabrück, Potsdam |
| L02 | Zuständigkeitsregelung für § 36a BauGB | Braunschweig, Osnabrück, Potsdam |
| L03 | Mieterkauf zur Wohnungsbaufinanzierung prüfen | Magdeburg, Osnabrück, Potsdam |
| L04 | Teilnahme am Bundesförderprogramm Schwimmbadsanierung | Braunschweig, Münster, Osnabrück |
| L05 | Digitalisierungsrat berufen | Münster, Potsdam |
| L06 | Verkehrsberuhigung vor Kitas prüfen | Magdeburg, Osnabrück |
| L07 | Klimaneutralitätsziele als Absichtserklärungen führen | Braunschweig, Magdeburg |
| L08 | Vereinszuschüsse für vereinseigene Sportanlagen | Osnabrück, Potsdam |
| L09 | Mindestbeförderungsentgelt für Mietwagen | Magdeburg, Münster |
| L10 | Barrierefreiheits-Ausbauprogramm für Schulen | Braunschweig, Münster |
| L11 | Gewässerzustandsbericht erstellen | Magdeburg, Osnabrück |
| L12 | Schrankenanlage gegen illegale Müllentsorgung | Magdeburg, Osnabrück |

## 6. Kosten

| Posten | gemessen |
|---|---|
| Einordnung des ganzen Bestands (2.906 Vorlagen) | 0,91 $ |
| Modellvergleich, 19 Läufe über 45 Vorlagen | 2,55 $ |
| Lücken-Gegenprobe, 54 Cluster | 0,01 $ |
| Embeddings (Oldenburg 13.266 Texte, fremde 2.946) | 0 $ (lokal) |
| **Phase 0 gesamt** | **3,49 $** |

Hochgerechnet auf den Dauerbetrieb mit fünf Städten: rund **1,30 $ im Jahr**
für die Einordnung, wenn nur neue Vorlagen laufen. Der Rückblick über weitere
Jahrgänge kostet 0,31 $ je 1.000 Vorlagen.

## 7. Was Phase 1 mitnehmen muss

1. **Modell:** `deepseek/deepseek-v4-flash`, Prompt-Fassung 2, Batches zu
   sechs, `max_tokens` großzügig. Das Golden Set nach `eval/`.
2. **Zuständigkeits-Feld** nachschärfen oder streichen.
3. **Vier Ernte-Fallen** aus Abschnitt 3 in den Client einbauen — sie sind
   allesamt still, keine wirft einen Fehler.
4. **Retrieval für Modus A** über die vorhandene Strecke der KI-Frage, nicht
   über rohe Embeddings.
5. **Modus B** nur mit Themenfeld-Bindung, Schwelle 0,86 und LLM-Gegenprobe.
6. **Ein Schreiber je SQLite-Datei.**

Skripte, Golden Set und der geerntete Bestand liegen unter
**`~/.cache/ratslotse/phase0/`** (47 MB, außerhalb des Repos): `harvest.py`,
`classify.py`, `match.py`, `gaps.py`, `compare2.py`, `gold.json` und
`peers.sqlite` mit allen 2.967 Vorlagen samt Volltext und Einordnung. Der Code
ist Wegwerf-Code; die Daten sparen einer Phase 1 eine Stunde Ernte.
