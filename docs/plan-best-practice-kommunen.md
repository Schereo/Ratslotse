# Was andere Räte beschließen — Plan für einen Städtevergleich der Vorhaben

Stand: 07.09.2026. Alle Zahlen in diesem Dokument sind an diesem Tag gemessen,
gegen die Ratsinformationssysteme der genannten Städte und gegen den lokalen
Abzug der Oldenburger Ratsdaten. Nichts davon ist geschätzt, wo es messbar war;
wo geschätzt wurde, steht es dabei.

> **Nachtrag 07.09.2026:** Phase 0 ist gelaufen — fünf Städte, 2.967 Vorlagen,
> Ergebnis und Korrekturen in
> [`phase0-andere-staedte.md`](phase0-andere-staedte.md). Wo dieses Dokument und
> der Bericht sich widersprechen, gilt der Bericht: Er misst, dieser Plan schätzte.

## 1. Die Frage und die Antwort in Kürze

Die Idee: Für künftige Anträge in Oldenburg nachsehen, was andere Kommunen zu
derselben Sache beschlossen haben — welche Ideen sie hatten, wie sie sie
umgesetzt haben, und wo Oldenburg etwas noch gar nicht angefasst hat.

**Die Idee trägt.** Drei Befunde, die das stützen:

1. **Die Daten sind da und maschinenlesbar.** Osnabrück und Braunschweig — die
   beiden nächsten Zwillinge Oldenburgs — liefern ihre Vorlagen über die
   OParl-Schnittstelle, Osnabrück ausdrücklich unter CC BY 4.0. Beide
   Endpunkte waren in keinem Verzeichnis zu finden; sie antworten trotzdem.
   Dazu kommen 13 weitere Städte mit brauchbarem OParl (Münster, Köln,
   Potsdam, Leipzig, Magdeburg, Dresden, Freiburg, Aachen, Bonn, …).
2. **Die Werkzeuge existieren schon im Repo.** PDF-Text (`council/vorlagen.py`),
   Themenfeld-Klassifikation (`council/topics.py`), Embeddings und Nachbarn
   (`council/embeddings.py`, `council/related.py`), Antragsteller-Erkennung
   (`council/parties.py`): Für die Nachbarstädte ist das derselbe Weg mit
   anderer Eingangstür.
3. **Die Stichprobe liefert.** Zehn Anträge aus Osnabrück, Münster und
   Braunschweig von Hand gegen die Oldenburger Datenbank gehalten: vier davon
   sind dort in keinem Beschluss zu finden (Einsamkeitsprävention,
   Hitzeaktionsplan, KI-Strategie, Mindestentgelt für Mietwagen), zwei sind
   längst erledigt (Trinkwasserbrunnen, Schulstraßen), einer läuft gerade
   parallel (Zweckentfremdungssatzung — Braunschweig und die Oldenburger SPD
   im selben Halbjahr). Genau diese drei Sorten Antwort soll das Feature
   geben.

**Drei Einschränkungen**, die den Plan formen:

- **Eine Lücke ist kein Versäumnis.** Dass Oldenburg zu etwas keinen
  Ratsbeschluss hat, kann heißen: die Verwaltung macht es ohne Beschluss, ein
  Eigenbetrieb macht es, es ist nicht Sache der Stadt, oder es ist schlicht
  unnötig. Das Feature darf deshalb nie „Oldenburg hat das nicht" behaupten,
  sondern nur „in Oldenburg findet sich dazu nichts Näheres als …" — mit dem
  nächsten Berührungspunkt daneben. Dieselbe Vorsicht, die
  `council/staedtevergleich.py` für Kennzahlen begründet, gilt für Vorhaben.
- **Die Ergebnisse (angenommen/abgelehnt) sind draußen lückenhaft.** Osnabrück
  trägt an gut der Hälfte der Tagesordnungspunkte ein Ergebnis, Münster an
  einem Fünftel, Magdeburg praktisch nie. Was überall da ist: der Antragstext
  und die Beschlussvorlage. Das Feature ist deshalb zuerst eine
  **Ideen-Quelle**, erst in zweiter Linie eine Erfolgsstatistik.
- **Es gibt schon einen Aggregator**, Ratsblick.de, ehrenamtlich, mit knapp
  einer Million Anträgen aus 7.731 Gemeinden, freier API und wöchentlichen
  Gesamtabzügen. Er nimmt uns das Einsammeln nicht ab (dazu unten), aber er
  beantwortet in einer Stunde, was sonst eine Woche Ingest kostet: *Gibt es
  in dieser Menge überhaupt genug Übertragbares?*

## 2. Was es schon gibt — und was davon fehlt

| Angebot | Was es ist | Was uns fehlt |
|---|---|---|
| **Ratsblick.de** | Ehrenamtliche Ein-Personen-Initiative (HagenIT, NL), Ableger des niederländischen „RaadKijker". OParl aus 184 Kommunen plus eigene OCR-Pipeline für den Rest, täglich. JSON-API (Schlüssel kostenlos auf Anfrage, 60 Anfragen/min, 5.000/Tag), CSV-Gesamtabzüge wöchentlich ohne Anmeldung („Nutzung frei mit Quellenangabe"). Deckt **Oldenburg selbst** (2.528 Anträge mit Ergebnis), Hannover (63.416), Osnabrück (3.101, ohne Ergebnis), Braunschweig (2.934), Kiel (1.957), Salzgitter (875), Hildesheim (745), Lüneburg (764), Emden (430), Delmenhorst (227). Göttingen: keine Daten. | Keine Oldenburg-Perspektive: kein Abgleich mit *unseren* Beschlüssen, keine Übertragbarkeit, keine Lücken. Kein Volltext in der API-Beschreibung erkennbar. Abhängigkeit von einer Person. Keine Lizenz im Rechtssinn. |
| **Poliscope.de** | Kommerziell, „90 % aller Kommunen", eigene Crawler, REST-API, KI-Auswertung. Nur nach Vertriebskontakt. | Preis unbekannt, kein offener Zugang, nichts Oldenburg-spezifisches. |
| **Politik bei uns / OParl-Mirror** | Die OKF-Spiegel aus der OParl-Frühzeit. | Beide tot: „wird nicht mehr aktiv betreut", `mirror.oparl.org` löst nicht mehr auf. |
| **KGSt Best-Practice-Datenbank** | 270 Beispiele, Mitglieder-Login. | Verwaltungs-, nicht Ratsperspektive; keine Beschlusstexte. |
| **Parteinahe Sammlungen** (Klimaunion-Vorlagen, Kommunaldatenbank der Linken, KommunalWiki der Böll-Stiftung) | Von Hand kuratierte Antragsvorlagen einer Partei. | Einseitig, klein, nicht auf Oldenburg bezogen. |

**Unser Beitrag ist die Relation zu Oldenburg**, nicht das Sammeln. Niemand
beantwortet heute: „Zu diesem Oldenburger Beschluss — was haben Osnabrück und
Braunschweig gemacht?" und „Welche Vorhaben haben zwei Nachbarstädte, zu denen
in Oldenburg nichts vorliegt?" Das ist auch der Grund, warum Ratslotse hier
etwas Eigenes hat: Wir sind die Einzigen mit 9.059 klassifizierten Oldenburger
Beschlüssen seit 2018 samt Vorlagen-Volltext, gegen die man vergleichen kann.

## 3. Datenlage: Wer liefert was (gemessen 07.09.2026)

### 3.1 Die Vergleichsstädte und ihre Schnittstellen

Ring 1 — **niedersächsische Zwillinge** (gleiches Kommunalverfassungsrecht,
NKomVG, gleiches Landesrecht in Schule, Bau, Finanzausgleich):

| Stadt | RIS | OParl | Lizenz | Papiere gesamt | Befund |
|---|---|---|---|---|---|
| **Osnabrück** | ALLRIS 4 | ✓ 1.1 — `www.osnabrueck.sitzung-online.de/oparl/system` | **CC BY 4.0** | 19.543 | Die letzten 393 Papiere (Feb–Sep 2026): 145 Beschlussvorlagen, 129 Mitteilungen, **72 Anträge**, 47 Anfragen. Jedes Papier hat ein „Sammeldokument öffentlich" (PDF, Textebene vorhanden, Fraktion im Kopf). Ergebnis an 376 von 707 TOPs (53 %), Beschluss-PDF an 100 %. |
| **Braunschweig** | ALLRIS 4 | ✓ 1.1 — `www.ratsinfo.braunschweig.sitzung-online.de/oparl/system` | keine Angabe | 49.483 (seit 1997) | Die letzten 393 Papiere (Jun–Sep 2026): **85 Anträge**, 83 Anfragen, 45 Beschlussvorlagen. Viele Anträge kommen aus den 19 Stadtbezirksräten („Sitzbank im Fichtengrund") — das ist Ortsratsebene, die Oldenburg nicht hat. Ergebnis an 25 von 82 TOPs, Beschluss-PDF an 57. |
| Wolfsburg | ALLRIS 4 | System antwortet, `bodies` wirft 500 | — | — | Kaputt; ggf. der Stadt melden. |
| Hannover | ALLRIS net (`ris.hannit.de`) | ✗ | — | — | Kein OParl. Ratsblick hat 63.416 Anträge mit Ergebnis — mit Abstand der größte Bestand. Landeshauptstadt, aber die **Region** trägt ÖPNV, Jobcenter, Abfall: viele Themen liegen dort außerhalb des Rats. |
| Göttingen | ALLRIS | Host antwortet uns nicht (TCP) | — | — | Auch Ratsblick: keine Daten. |
| Salzgitter, Celle | ALLRIS 4 | ✗ (Modul nicht freigeschaltet) | — | — | Ratsblick: 875 / 0. |
| Hildesheim, Lüneburg, Delmenhorst, Emden, Wilhelmshaven | ALLRIS / unklar | ✗ | — | — | Ratsblick: 745 / 764 / 227 / 430 / –. Nur über Ratsblick oder eigenen HTML-Scraper. |

Ring 2 — **strukturelle Zwillinge** anderswo (kreisfreie Universitätsstadt,
150–300 Tsd., ähnliche Themenlage):

| Stadt | RIS | OParl | Lizenz | Papiere gesamt | Befund |
|---|---|---|---|---|---|
| **Münster** | Session (Somacos) | ✓ 1.1 — `oparl.stadt-muenster.de/system` | keine | ≥ 4.000 in 12 Monaten | Antragstypen sauber getrennt („Antrag an den Rat" 307, an die Bezirksvertretungen ~600). **Kein `mainFile`** — die Dateien hängen unter `auxiliaryFile`. Ergebnis nur an 22 % der TOPs; Ergebnisprotokoll-PDF an 52 von 69 Sitzungen. Fahrradstadt, oft Oldenburgs Referenz. |
| **Potsdam** | ALLRIS 4 | ✓ 1.1 | eigener Hinweis | 28.132 | 37 von 100 neuesten Papieren sind Anträge. Ergebnisse: 0 von 10 geprüften. |
| **Magdeburg** | Session | ✓ 1.1 | **DL-DE-Zero 2.0** | ≥ 4.000/Jahr | Antragsfreudigster Rat der Probe: 524 Anträge, 486 Änderungsanträge, 817 Anfragen in 12 Monaten. Ergebnisse: über die Sitzungen geholt **67 %** der Tagesordnungspunkte — die beste Quote der fünf Städte (die Angabe „fast keine" stammte aus einem zu kleinen Ausschnitt über `body.agendaItem`). Die Datei-URLs der Schnittstelle antworten allerdings durchweg mit 404, s. Phase-0-Bericht. |
| **Freiburg** | more! rubin | ✓ **1.0** | keine | 13.959 | Einziger Endpunkt mit **Volltext im Dateiobjekt** (`text`, ~6.000 Zeichen) und `resolutionText`. Aber: Zeitfilter werden ignoriert, kein Antragstyp (nur Beschluss-/Informationsvorlage). |
| Aachen, Bonn | ALLRIS | ✓ 1.1 | Aachen „CC", Bonn eigene Bedingungen | 21.650 / 24.469 | Aachen kennt keinen Antragstyp (nur Entscheidungsvorlage/Kenntnisnahme), Ergebnis an 78 %. Bonn: Filter liefern 0. |
| Kiel, Lübeck, Regensburg, Würzburg, Trier | ALLRIS 4 | ✗ | — | — | Ratsblick: Kiel 1.957, Lübeck 1.274. |
| Bielefeld, Heidelberg, Mainz, Ulm, Erfurt | SessionNet | ✗ | — | — | Wie Oldenburg: kein OParl (Ulm steht in der Registry, antwortet 404). |

Ring 3 — **Ideen-Reservoir** (groß, gut erschlossen, aber strukturell weit
weg): Köln (Session, Ergebnis an 72 % der TOPs, Antragsteller im Titel),
Leipzig (ALLRIS 4, CC BY 4.0, 49.116 Papiere), Dresden (DL-DE-Zero, langsam),
Wuppertal, Düsseldorf, München (München Transparent, 1.0). Bremen scheidet
aus: Stadtstaat mit Bürgerschaft, anderes Recht, eigenes System (Parlis).

Was **nicht** vergleichbar ist, folgt aus der Tabelle: Braunschweigs
Stadtbezirksräte und Münsters Bezirksvertretungen erzeugen hunderte
Kleinstanträge auf Ortsratsebene, die in Oldenburg im Fachausschuss oder gar
nicht landen. Hannovers Regionsaufgaben, Bremens Landesaufgaben und Osnabrücks
Eigenbetrieb für Abfall und Straßen (Betriebsausschuss statt Rat) verschieben
Themen zwischen Gremien. Der Vergleich muss deshalb **auf Gremienebene
filtern** (Rat und Fachausschüsse, nicht Ortsräte) und **je Thema wissen, wer
zuständig ist** (§ 5 unten).

### 3.2 Eigenheiten je Hersteller — die Fallen für den Ingest

Vier Hersteller, vier Dialekte. Gemessen, nicht gelesen:

| Hersteller | Städte | Was man wissen muss |
|---|---|---|
| **ALLRIS 4** (CC e-gov) | Osnabrück, Braunschweig, Potsdam, Leipzig, Bonn, Langenhagen | Endpunkt immer `<host>/oparl/system`. **Seitengröße fest 10**, `limit` wird ignoriert (Osnabrück: 1.955 Seiten). Liste läuft **alt → neu**; die neuesten stehen auf `links.last`. `created_since` liefert 0, `modified_since` ist unbrauchbar, weil `created`/`modified` bei allen Papieren auf `2000-01-01` stehen. Inkrementell heißt hier: von `last` rückwärts blättern, bis eine bekannte ID kommt. Jedes Papier trägt ein Sammel-PDF; der Antragsteller steht nur im Titel und im PDF-Kopf, nicht in `originatorOrganization`. `consultation` am Papier verweist nicht auf den TOP — die Verbindung Papier → Ergebnis geht nur über `agendaItem.consultation`. |
| **Session** (Somacos) | Münster, Köln, Magdeburg, Dresden, Wuppertal, Düsseldorf | Seitengröße 100, `modified_since` funktioniert, Datumsangaben echt. Kein `mainFile`, Dateien unter `auxiliaryFile`. Ergebnis am TOP je nach Stadt (Köln gut, Münster mäßig, Magdeburg leer). Dresden antwortet langsam (Timeout 40 s). |
| **more! rubin** | Freiburg, Darmstadt | Noch OParl 1.0: Zeitfilter werden ignoriert, aber Volltext liegt schon im Dateiobjekt. `body.agendaItem` gibt es nicht — TOPs nur über die Sitzung. |
| **SD.NET RIM** (Sternberg) | Krefeld, Bochum, Wallenhorst, Paderborn (ohne OParl) | `limit` → HTTP 400; 25 je Seite; Papiere tragen kaum Felder (Krefeld: nur `created/modified/id/deleted`). Für uns unbrauchbar, bis nachgeladen wird. |
| **SessionNet** (Somacos, Bürgerinfo) | Oldenburg, Bielefeld, Heidelberg, Mainz, Ulm, Erfurt | Kein OParl. Der Hersteller hat das Modul seit 2017 im Angebot (Session-Städte oben nutzen es), die SessionNet-Instanzen haben es nicht freigeschaltet. |

Merksatz für den Client: **eine Abstraktion, vier Adapter**. Was der Client
liefern muss, ist klein — Papiere mit Titel, Nummer, Datum, Typ, Datei-URL,
Gremium; TOPs mit Ergebnis und Beschluss-PDF; Sitzungen mit Datum und Gremium.
Alles andere ist Dialekt.

### 3.3 Die Oldenburger Seite

| | |
|---|---|
| Beschlüsse seit 2018 | 9.059 (~1.050 je Jahr), alle mit Themenfeld |
| Vorlagen mit Volltext | 5.090 |
| Anträge (als Anlagen) | 861, davon 544 mit erkanntem Antragsteller (CDU 150, Grüne 116, SPD 102, Grüne+SPD 63, Linke 29, FDP 16, WFO/LKR 15) |
| Themenfelder | 12 (`council/topics.py`); Schwerpunkte Finanzen 1.882, Bauen/Wohnen 1.257, Verkehr 1.229, Klima/Umwelt 1.223 |
| Ergebnisse 2024–26 | angenommen 1.150, Kenntnis 1.012, abgelehnt 141, vertagt 138 |

Zum Maßstab: Osnabrück produziert im selben Rhythmus rund 120 Anträge im Jahr,
Braunschweig (inkl. Stadtbezirksräte) rund 350, Münster (inkl.
Bezirksvertretungen) rund 1.000, Magdeburg rund 1.000 samt Änderungsanträgen.
Oldenburgs 861 Anträge in achteinhalb Jahren sind eher wenig — was die These
stützt, dass es hier etwas zu holen gibt.

## 4. Welche Städte sich zum Vergleich anbieten

Drei Kriterien, in dieser Reihenfolge:

1. **Gleicher Rechtsrahmen** schlägt alles. Ein Antrag aus Braunschweig zur
   Zweckentfremdungssatzung „nach § 1 NZwEWG" ist wörtlich übertragbar; der
   Münsteraner Antrag zu „Anregungen und Beschwerden nach § 24 GO NRW" braucht
   erst die Übersetzung ins NKomVG. Deshalb Ring 1 zuerst, und dort Osnabrück
   und Braunschweig, weil nur sie OParl haben.
2. **Ähnliche Aufgabenlast.** Kreisfrei, Universitätsstadt, Klinikum und
   Stadtwerke im Konzern, Eigenbetriebe: Osnabrück ist der Zwilling, Münster
   und Freiburg die größeren Geschwister mit denselben Debatten (Radverkehr,
   Wohnen, Klima). Potsdam und Magdeburg sind ähnlich groß, aber
   Landeshauptstädte in Ost-Ländern mit anderem Förder- und Schulrecht.
3. **Datenqualität.** Ergebnis am TOP (Osnabrück, Köln, Aachen), Volltext
   ohne PDF (Freiburg), saubere Antragstypen (Münster, Magdeburg, Potsdam).

Empfehlung für den Start: **Osnabrück, Braunschweig, Münster** — zwei
Rechtsrahmen-Zwillinge und ein Themen-Zwilling, alle drei mit OParl. Zweite
Welle: Potsdam, Magdeburg, Leipzig, Freiburg. Hannover, Kiel, Salzgitter nur
über Ratsblick oder gar nicht; ein eigener ALLRIS-HTML-Scraper lohnt erst,
wenn die ersten drei den Nutzen belegt haben.

## 5. Übertragbar oder nicht — die Einordnung

Jede fremde Vorlage bekommt **zwei** Einordnungen, beide per LLM aus dem
Volltext, beide als Schlüssel aus einer geschlossenen Liste (wie
`POLICY_FIELDS`), damit sie zählbar und filterbar sind.

### 5.1 Themenfeld

Dieselben zwölf Felder wie in Oldenburg (`council/topics.py`), mit demselben
Prompt. Das ist keine Bequemlichkeit, sondern Voraussetzung: Nur so lassen
sich „Verkehr in Osnabrück" und „Verkehr in Oldenburg" nebeneinanderstellen.
Die Vorlagentypen der Städte (Antrag, Anfrage, Änderungsantrag,
Beschlussvorlage, Mitteilung) werden auf **vier** Typen normalisiert:
`motion`, `inquiry`, `proposal`, `notice` — Anfragen sind für Ideen so
wertvoll wie Anträge (sie zeigen, was eine Fraktion umtreibt), Mitteilungen
meist nicht.

### 5.2 Übertragbarkeit

| Stufe | Kennzeichen | Beispiele aus der Probe |
|---|---|---|
| **ortsgebunden** | Konkretes Grundstück, Straße, Platz, Gebäude, Person; der Antrag ist ohne den Ort sinnlos | „Benennung Wiesenfestplatz Porz-Langel" (Köln), „Grünpflege Gehweg Rautheimer Straße" (Braunschweig), „Erinnerungszeichen für eine verstorbene Person im Bürgerpark" (Osnabrück) |
| **einmalig / reaktiv** | Resolution, Ehrung, Reaktion auf ein Ereignis | „Keine Panzer aus der Friedensstadt" (Osnabrück), Verschiebung einer Preisverleihung |
| **zuständigkeits- oder rechtsrahmengebunden** | Setzt Landesrecht, Stadtstaat, Bezirksvertretung oder Regionsaufgabe voraus | „Verfahren nach § 24 GO NRW" (Münster), alles aus Bezirksvertretungen und Stadtbezirksräten, Hannovers Regionsthemen |
| **übertragbar mit Anpassung** | Ein Instrument — Förderrichtlinie, Satzung, Programm, Prüfauftrag, Konzept, Beteiligungsformat, Organisationsmaßnahme — das anderswo genauso ginge | „Gemeinsam gegen Einsamkeit" (OS), „Jedes Dach zählt — Solar auf städtischen Immobilien" (MS), „Mehrweg fördern" (OS), „Sport im Verein für alle Kinder" (OS), „Kinderbibliothek in Leerstandsimmobilie" (OS; das Instrument ist: Leerstand kulturell nutzen), „Mindestbeförderungsentgelt für Mietwagen" (MS; Taxitarif ist kommunal), „Eine KI-Strategie für Münster" |
| **direkt übertragbar** | Gleiches Landesgesetz, gleiche Rechtsgrundlage, oder ein Beitritt/eine Berichtspflicht | „Erlass einer Zweckentfremdungssatzung nach § 1 NZwEWG" (BS), Beitritte zu Städtebündnissen, Berichtsaufträge |

Die ersten drei Stufen fliegen aus der Ideen-Liste, bleiben aber in der Datenbank
— ein ortsgebundener Antrag kann trotzdem der nächste Nachbar eines
Oldenburger Beschlusses sein („Osnabrück hat für seinen Bürgerpark dasselbe
entschieden").

Wichtig: Der Ort im Titel ist kein Ausschlusskriterium. „Sicherer Schulweg in
Hellern — Querungshilfe an der Kleinen Schulstraße" ist ortsgebunden, aber der
Prompt soll das **Instrument dahinter** benennen (Querungshilfe an
Schulwegen) — als eigenes Feld `instrument`, ein bis fünf Wörter. Erst darüber
werden Cluster möglich.

### 5.3 Zuständigkeit

Ein drittes, kleines Feld: **Wer macht das in Oldenburg?** Rat, Verwaltung
ohne Beschluss, Eigenbetrieb (Gebäudewirtschaft, Abfallwirtschaft, Bäder), Beteiligung (Stadtwerke,
Klinikum, VWG), Landkreis (entfällt, kreisfrei), Land. Die Liste steht als
Code, weil sie Oldenburg-spezifisch ist. Ein Osnabrücker Antrag an den
Betriebsausschuss Abfall ist in Oldenburg ein Thema für den Betriebsausschuss des Abfallwirtschaftsbetriebs;
ein Hannoveraner ÖPNV-Antrag richtet sich an die Region und hat in Oldenburg
die VWG als Adressat. Ohne dieses Feld hält die Lücken-Analyse
Zuständigkeitsunterschiede für Untätigkeit.

## 6. Lücken finden — das Verfahren

**Definition.** Eine Lücke ist ein *Instrument* (§ 5.2), das

- in mindestens **zwei** Vergleichsstädten vorkommt (eine Stadt ist ein
  Einfall, zwei sind ein Muster),
- dort mindestens einmal **beschlossen** wurde, wo Ergebnisse vorliegen (sonst
  gilt: „beantragt"),
- als übertragbar eingestuft ist,
- und in Oldenburg **keinen nahen Treffer** hat: kein Beschluss und keine
  Vorlage mit Kosinus-Ähnlichkeit über der Schwelle, und ein LLM-Nachcheck
  bestätigt „nichts Vergleichbares".

**Warum der LLM-Nachcheck nötig ist**, zeigt die Stichprobe: „Solar auf
städtischen Dächern" fand per Wortsuche keinen Oldenburger Beschluss, aber 57
Vorlagentexte erwähnen Photovoltaik auf städtischen Gebäuden — Oldenburg
*macht* das, nur nie unter diesem Titel. Embeddings finden solche Fälle,
Wortsuche nicht; und das Modell muss dann sagen, ob es dasselbe Instrument ist.

**Ausgabe.** Kein Ranking, keine Note. Eine Liste je Themenfeld:
„*Instrument* — in Osnabrück (Antrag Grüne 2026, beschlossen) und Münster
(Vorlage 2025). Nächster Berührungspunkt in Oldenburg: *Titel*, Ähnlichkeit
0,61." Wer das liest, entscheidet selbst, ob es eine Lücke ist. Das ist die
Form, in der Ratslotse auch sonst arbeitet: Beleg neben Aussage.

**Die zweite Richtung** ist einfacher und kommt zuerst: Zu einem Oldenburger
Beschluss die nächsten fremden Papiere — „So machen es andere Städte". Dafür
braucht es keine Cluster, nur die Nachbarschaft über dieselben Embeddings, die
`council_similar` heute innerhalb Oldenburgs berechnet.

## 7. Architektur

Nach den Regeln des Repos: Logik im Backend, Web und iOS featuregleich, Code
auf Englisch, Schalter aus `kern/features.py`, Cron über `run_guarded` mit
Takt in `kern/jobs.py`, Antwortformen im Vertrag.

### 7.1 Daten

**Eigene Datei `data/peers.sqlite`**, nicht `council.sqlite`. Drei Gründe:
Die Ratsdatenbank ist der Abzug, den jeder Worktree kopiert (220 MB, und
Nachbarstädte würden sie in einem Jahr verdoppeln); die Tabellen haben andere
Lebenszyklen (ein Vollneuaufbau der Nachbarn darf Oldenburg nicht berühren);
und die Trennung macht den Abzug für die lokale Arbeit optional. Anbindung
wie die beiden bestehenden Datenbanken über die Backend-Konfiguration.

```
peer_bodies         id, name, state, ris_vendor, oparl_url, license, population,
                    fetched_at, notes
peer_organizations  id, body_id, name, kind (council|committee|district|faction)
peer_meetings       id, body_id, organization_id, name, start, state, protocol_url
peer_papers         id, body_id, reference, name, date, paper_type_raw,
                    paper_type (motion|inquiry|proposal|notice), originator
                    (Fraktion aus Titel/PDF), file_url, text, n_pages,
                    policy_field, policy_tags, instrument, transferability
                    (local|one_off|jurisdiction|adaptable|direct),
                    competence (council|administration|utility|holding|state),
                    summary, fetched_at, status
peer_agenda_items   id, meeting_id, paper_id, number, name, result_raw,
                    outcome (accepted|rejected|postponed|noted|no_decision),
                    resolution_url
peer_embeddings     paper_id, vector (384, wie council_embeddings)
peer_matches        decision_id (Oldenburg) ↔ paper_id, score, kind
                    (nearest|same_instrument), checked_at
peer_gaps           instrument, policy_field, bodies (JSON), best_oldenburg
                    (decision_id, score), llm_verdict, computed_at
```

`peer_papers.text` trägt den Volltext ab „Sachverhalt/Begründung" wie
`council_templates.raw_text`, gedeckelt auf 20.000 Zeichen; PDFs werden nicht
gespeichert. Personen (`originatorPerson`) werden **nicht** übernommen — für
die Frage „welche Fraktion" reicht die Organisation, und Ratsmitglieder anderer
Städte gehören nicht in unsere Datenbank.

### 7.2 Module

| Datei | Aufgabe |
|---|---|
| `council/peers/oparl.py` | Generischer OParl-Client mit den vier Dialekten aus § 3.2: System → Body → Papers/Meetings/AgendaItems, Blättern vorwärts und rückwärts, Drosselung 1 Anfrage/s, User-Agent mit Kontaktadresse |
| `council/peers/bodies.py` | Die Registry der Vergleichsstädte als Code (wie `city_topics.py`): Name, Endpunkt, Dialekt, Startdatum, welche Gremien zählen (Rat und Fachausschüsse, keine Orts-/Bezirksräte) |
| `council/peers/sync.py` | Inkrementeller Abgleich; PDF-Text über dieselbe pypdf-Strecke wie `vorlagen.py`; Antragsteller über `parties.parties_in_text` mit einer je Stadt erweiterten Liste |
| `council/peers/classify.py` | Themenfeld (Prompt aus `topics.py` wiederverwendet), Typ, Instrument, Übertragbarkeit, Zuständigkeit — ein Aufruf je Papier, Batches wie bei `topics.py` |
| `council/peers/match.py` | Embeddings (fastembed, dasselbe Modell wie `council_embeddings`, nur im Skript), Nachbarn in beide Richtungen, Instrument-Cluster, Lücken-Kandidaten mit LLM-Nachcheck |
| `council/peers/store.py` | Schema und Migration nach den Regeln aus `council/CLAUDE.md` |
| `scripts/check_peers.py` | Wöchentlich, `run_guarded`, Kennzahlen (Papiere neu, klassifiziert, Lücken) ins Admin-Panel |
| `web/backend/app/routers/peers.py` | `GET /api/peers/bodies`, `GET /api/council/decision/{id}/peers` (Nachbarn), `GET /api/peers/ideas?field=…` (Ideen-Liste), `GET /api/peers/gaps?field=…` |
| Frontend | Block „So machen es andere Städte" auf der Beschluss-Seite (`app/(app)/council/decision/`), Seite `/council/peers` mit Themenfeld-Filter, Karten wie Beschluss-Karten mit Stadt-Marke statt Gremium; iOS-Nachzug im selben PR-Paar |

Neue Prompts stehen in `kern/prompts.py`, wie alle. Der Schalter heißt
`andere-staedte` mit `fertig_wenn`: „Die Lücken-Liste hat vier Wochen auf dev
gelegen und Tim hat mindestens die Hälfte der Kandidaten als brauchbar
markiert."

### 7.3 Kosten und Last

| Posten | Schätzung | Grundlage |
|---|---|---|
| LLM-Klassifikation | unter 1 Cent je Papier; drei Städte ≈ 5.500 Papiere/Jahr ≈ **10 €/Jahr**; Rückfüllung 2023–2026 einmalig ≈ 30 € | „Einfach erklärt" kostete 2,80 $ für 2.069 Stücke bei ~400 Token rein / 700 raus (deepseek-v4-pro); hier ~1.500 rein / 300 raus |
| Embeddings | 0 € (fastembed lokal, ~1,5 KB je Papier) | wie `embed_decisions.py` |
| Speicher | ~6 KB Text + 1,5 KB Vektor je Papier → drei Städte ≈ 40 MB/Jahr; Erstlauf ab 2023 ≈ 150 MB | Osnabrücker PDFs: 60–450 KB, Text ~6.000 Zeichen |
| Netz, Erstlauf | Osnabrück: 1.955 Listenseiten + ~4.000 PDFs ab 2023 ≈ 1 GB, bei 1 Anfrage/s rund zwei Stunden nachts | gemessen |
| Netz, wöchentlich | ~30 Listenseiten + ~50 PDFs je Stadt | |
| Server | Ein nächtlicher Cron auf der Dev-VM; nichts davon im Request-Pfad | |

Mit sieben Städten (zweite Welle) verdreifacht sich alles; es bleibt unter
50 €/Jahr und unter 500 MB.

### 7.4 Recht und Anstand

- **Amtliche Werke.** Beschlussvorlagen, Beschlüsse und Protokolle sind
  amtliche Werke (§ 5 UrhG), frei nutzbar. Fraktionsanträge sind es streng
  genommen nicht; sie werden öffentlich beraten und liegen im RIS, wir zeigen
  Titel, Auszug und Link zur Quelle — dieselbe Praxis wie heute für
  Oldenburger Anträge. Wo eine Lizenz steht (Osnabrück, Leipzig CC BY 4.0;
  Magdeburg, Dresden DL-DE-Zero; Bonn eigene Bedingungen), nennen wir sie am
  Stadt-Eintrag.
- **Keine Personen.** Siehe § 7.1. Auch keine Kontaktdaten, die manche
  Organisation-Objekte mitliefern.
- **Drosselung und Kennung.** Eine Anfrage je Sekunde, `User-Agent` mit
  Projekt-URL, nachts. ALLRIS-Instanzen zeigen auf der HTML-Seite eine
  „Zugriff prüfen"-Hürde; die OParl-Pfade sind davon nicht betroffen — das
  soll so bleiben.
- **Quellenangabe** bei allem, was aus Ratsblick kommt (ihre einzige
  Bedingung).

## 8. Phasen

### Phase 0 — Stichprobe, ohne Produktcode (2–3 Tage)

Die Frage: *Findet das Verfahren Dinge, die ein Ratsmitglied brauchbar findet?*

1. Aus Osnabrück, Braunschweig und Münster die Anträge und Beschlussvorlagen
   der letzten 24 Monate holen (Rat und Fachausschüsse, ~2.500 Papiere), Text
   ziehen, klassifizieren (§ 5), einbetten.
2. Gegen Oldenburg 2024–2026 rechnen: Nachbarn je Oldenburger Beschluss;
   Instrument-Cluster mit ≥ 2 Städten ohne nahen Oldenburger Treffer.
3. Ausgabe: eine Markdown-Liste mit 30 Lücken-Kandidaten und 30
   Nachbarschaften, je mit Belegen.
4. **Tim bewertet** jeden Kandidaten: brauchbar / kenne ich schon / falsch.
   Schwelle für Phase 1: mindestens 40 % brauchbar bei den Lücken, 60 % bei
   den Nachbarschaften.

Ratsblick kommt hier als Gegenprobe hinzu, nicht als Quelle: Der
Gemeinden-Abzug (383 KB) sagt, welche Städte sie mit welcher Tiefe haben, der
Anträge-Abzug (39 MB) erlaubt, die Instrument-Cluster über 20 statt 3 Städte
zu zählen — nur zum Zählen, die Texte kommen aus den RIS.

### Phase 1 — Ingest und Nachbarschaft (5–7 Tage)

`peers.sqlite`, OParl-Client mit den drei Dialekten (ALLRIS 4, Session, und
zur Probe more! rubin für Freiburg), wöchentlicher Cron, Admin-Kennzahlen,
Embeddings. Endpunkt `…/decision/{id}/peers`. Block auf der Beschluss-Seite
und in der App, hinter dem Schalter, auf dev.

### Phase 2 — Ideen und Lücken (6–8 Tage)

Klassifikation um Instrument, Übertragbarkeit und Zuständigkeit ergänzt;
Cluster; Lücken-Liste je Themenfeld mit LLM-Nachcheck; Seite `/council/peers`
mit Filter Themenfeld × Stadt × Typ × Übertragbarkeit; KI-Frage bekommt einen
Kontextblock „In anderen Städten" (wie heute „Aktuelles von der Stadt"), damit
„Hat eine andere Stadt schon einen Hitzeaktionsplan?" beantwortbar wird.

### Phase 3 — Ausbau (laufend)

Zweite Welle Städte; Benachrichtigung für die Rolle `mandate` („Neu in
Osnabrück zu deinen Themen", über `notify.einreihen`); Ergebnis-Nachlauf, wo
Städte Ergebnisse nachtragen; ggf. ein ALLRIS-HTML-Scraper für Hannover und
Kiel, falls die ersten Städte den Bedarf zeigen.

## 9. Risiken

| Risiko | Wirkung | Gegenmittel |
|---|---|---|
| Endpunkte ändern sich (Braunschweig ist 2026 auf einen neuen Host gezogen; Wolfsburg ist kaputt) | Cron rot, Bestand friert ein | Jeder Body trägt `fetched_at`; die Herzschlag-Prüfung aus `check_herzschlag.py` gilt auch hier; Registry als Code mit Datum des letzten erfolgreichen Laufs |
| Ergebnisse fehlen (Magdeburg, Potsdam, Münster) | „beantragt" statt „beschlossen" | Feld `outcome` darf leer sein und wird so gezeigt; Ergebnisprotokoll-PDF als späterer Nachlauf |
| Falsche Lücken durch Zuständigkeit oder Wortwahl | Vertrauensverlust bei genau der Zielgruppe | § 5.3, § 6: nächster Berührungspunkt immer daneben; Phase-0-Schwelle vor jedem Produktcode |
| LLM-Einordnung schwankt | Cluster zerfallen | Geschlossene Schlüssellisten, Golden-Set mit 100 handbewerteten Papieren im `eval/`-Harness wie bei Tragweite |
| Abhängigkeit von Ratsblick | Fällt aus, ist die Abdeckungs-Sicht weg | Nur in Phase 0 und als Gegenprobe; das Produkt liest die RIS direkt |
| Dev-Abzug wächst | Lokale Arbeit wird träge | Eigene Datei, im Abzug optional |

## 10. Offene Entscheidungen

1. **Startmenge:** Osnabrück, Braunschweig, Münster — oder gleich Potsdam und
   Magdeburg dazu, weil sie die meisten Anträge haben?
2. **Sichtbarkeit:** Öffentlich für alle (Ratslotse ist eine Bürger-App, und
   Ideen aus anderen Städten sind auch für Bürgerinnen interessant), oder
   zunächst nur für die Rolle `mandate`? Vorschlag: öffentlich lesbar hinter
   dem Schalter, Benachrichtigungen nur für Mandate.
3. **Ratsblick-Schlüssel:** Der API-Schlüssel ist kostenlos, aber eine
   Anmeldung — das solltest du selbst machen, wenn wir ihn wollen. Für Phase 0
   reichen die CSV-Abzüge ohne Anmeldung.
4. **Name:** „So machen es andere Städte" / „Anderswo" / „Nachbarn" — die
   Formulierung prägt, ob es wie ein Ranking klingt. Vorschlag: „Anderswo
   beschlossen".
5. **Eigene Anträge als Ausgangspunkt:** Soll die Suche auch aus einem
   *Entwurf* heraus funktionieren („ich schreibe gerade einen Antrag zu X —
   was gibt es dazu anderswo?"), also als Freitext-Eingabe statt nur vom
   Beschluss aus? Technisch dasselbe wie die Themen-Intelligenz
   (`topic_intel.py`); es wäre die Funktion, die Ratsmitglieder vermutlich am
   meisten nutzen.

## Anhang A — Gemessene Endpunkte

| Stadt | Endpunkt | Hersteller | Version |
|---|---|---|---|
| Osnabrück | `https://www.osnabrueck.sitzung-online.de/oparl/system` | CC e-gov ALLRIS 4 | 1.1 |
| Braunschweig | `https://www.ratsinfo.braunschweig.sitzung-online.de/oparl/system` | CC e-gov ALLRIS 4 | 1.1 |
| Potsdam | `https://www.potsdam.sitzung-online.de/oparl/system` | CC e-gov ALLRIS 4 | 1.1 |
| Leipzig | `https://www.leipzig.sitzung-online.de/oparl/system` | CC e-gov ALLRIS 4 | 1.1 |
| Bonn | `https://www.bonn.sitzung-online.de/oparl/system` | CC e-gov ALLRIS 4 | 1.1 |
| Langenhagen | `https://www.langenhagen.sitzung-online.de/oparl/system` | CC e-gov ALLRIS 4 | 1.1 |
| Aachen | `https://ratsinfo.aachen.de/public/oparl/system` | CC e-gov ALLRIS | 1.1 |
| Wolfsburg | `https://ratsinfob.stadt.wolfsburg.de/oparl/system` (Body-Liste: HTTP 500) | CC e-gov ALLRIS 4 | 1.1 |
| Münster | `https://oparl.stadt-muenster.de/system` | Somacos Session 1.6.0 | 1.1 |
| Köln | `https://buergerinfo.stadt-koeln.de/oparl/system` | Somacos Session 1.6.1 | 1.1 |
| Magdeburg | `https://ratsinfo.magdeburg.de/oparl/system` | Somacos Session 1.5.3 | 1.1 |
| Dresden | `https://oparl.dresden.de/system` | Somacos Session 1.5.4 | 1.1 |
| Wuppertal | `https://oparl.wuppertal.de/oparl/system` | Somacos Session 1.6.1 | 1.1 |
| Düsseldorf | `https://ris-oparl.itk-rheinland.de/Oparl/system` | Somacos Session 1.6.0 | 1.1 |
| Freiburg | `https://ris.freiburg.de/oparl/system` | more! rubin | 1.0 |
| Darmstadt | `https://darmstadt.gremien.info/oparl/system` | more! rubin | 1.0 |
| Krefeld | `https://ris.krefeld.de/webservice/oparl/v1.0/system` | Sternberg SD.NET | 1.0 |
| Bochum | `https://bochum.ratsinfomanagement.net/webservice/oparl/v1.0/system` | Sternberg SD.NET | 1.0 |
| Wallenhorst | `https://wallenhorst.ratsinfomanagement.net/webservice/oparl/v1.0/system` | Sternberg SD.NET | 1.0 |
| München | `https://www.muenchen-transparent.de/oparl/v1.0` | München Transparent | 1.0 |

Ohne OParl (geprüft): Oldenburg, Hannover, Salzgitter, Celle, Kiel, Lübeck,
Regensburg, Würzburg, Trier, Goslar, Bielefeld, Heidelberg, Mainz, Ulm,
Erfurt, Kassel, Paderborn, Delmenhorst, Bremerhaven, Bremen. Nicht erreichbar:
Göttingen (`ratsinfo.goettingen.de`), Kiel (`ratsinfo.kiel.de`) — beide
brechen die TCP-Verbindung ab.

Die Registry unter `dev.oparl.org/api/endpoints` (127 Einträge) kennt weder
Osnabrück noch Potsdam noch Leipzig unter den heutigen Hosts; Braunschweig
steht dort mit dem alten. Wer eine Stadt sucht: ALLRIS-4-Instanzen laufen fast
immer unter `<stadt>.sitzung-online.de`, und der Endpunkt ist `/oparl/system`.

## Anhang B — Probe-Rezept

```bash
# Antwortet ein Host mit OParl?
curl -s -A "Ratslotse (+https://ratslotse.de)" https://www.osnabrueck.sitzung-online.de/oparl/system | python3 -m json.tool | head -20

# Neueste Papiere einer ALLRIS-4-Instanz: erst die Seitenzahl holen …
curl -s https://www.osnabrueck.sitzung-online.de/oparl/bodies/1000001/papers | python3 -c "import json,sys; print(json.load(sys.stdin)['links']['last'])"
# … dann von hinten blättern (?page=1955&size=10, size wird ignoriert)
```

Die Messskripte dieser Erhebung liegen nicht im Repo; sie waren Wegwerf-Code.
Was bleibt, steht in den Tabellen oben.
