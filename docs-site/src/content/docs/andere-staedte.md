---
title: Andere Städte
description: Der Städte-Speicher — Ratsdokumente anderer Kommunen, in fünf Schichten gehalten, mit belegten Urteilen gegen Oldenburg verglichen.
---

Was ein Rat beschließt, hat oft schon ein anderer beschlossen. Der
Städte-Speicher (`council/cities`, Datei `data/cities.sqlite`) hält
Ratsdokumente anderer Kommunen und vergleicht sie mit Oldenburg. Daraus
entstehen zwei Dinge in der Oberfläche:

- **„In anderen Städten“** auf der Beschluss-Seite und in „Frag den Rat“
  (Schalter `andere-staedte`): was andere Städte zu derselben Sache
  beantragt, beraten oder beschlossen haben.
- **„Ideen aus anderen Städten“** unter `/council/ideen` (Schalter
  `ideen-anderswo`): je Themenfeld, was andere Räte haben und Oldenburg
  fehlt, mit Urteil, Belegen und dem Weg zum Original.

Die Endpunkte unter `/api/council/cities/` sind öffentlich wie die
Beschluss-Seiten: Es stehen nur Ratsdokumente anderer Städte darin und ein
Urteil darüber, ob Oldenburg dasselbe hat.

## Fünf Schichten

```
0  raw_objects, raw_files    was die Schnittstelle lieferte, unverändert, nur anhängend
1  bodies … consultations    die acht OParl-Objekte, vereinheitlicht
2  texts                     Volltext, versioniert nach Extraktor
3  annotations               was ein Modell oder eine Regel dazu sagt
4  chunks … neighbors, FTS   Indizes, je Modell getrennt
```

**Jede Schicht ist aus der darunter vollständig neu berechenbar.** Wer 2 bis 4
löscht, verliert Rechenzeit und ein paar Dollar, keine Daten. Deshalb braucht
eine bessere Auswertung später keinen erneuten Abruf bei den Städten.

**Schicht 0 wird nur angehängt.** Ein Papier ändert sich: Das Ergebnis wird
Wochen nach der Sitzung nachgetragen, ein Titel berichtigt, eine Anlage
ergänzt. Wer die Zeile überschreibt, verliert die Frage „Wann kam das
Ergebnis?“, bevor sie jemand stellt. Ein unveränderter Abruf erzeugt keine
neue Zeile (`UNIQUE(oparl_id, content_hash)`); der Wochenlauf kostet also
nichts, solange sich nichts tut.

Die Stufen folgen den Schichten (`council/cities/pipeline.py`):
`fetch → normalize → extract → annotate → index`. Jede liest die Tabellen der
vorigen und schreibt ihre eigenen. Ein neuer Prompt heißt damit: nur
`annotate` für diesen Annotator. Ein neues Embedding-Modell: nur `index`.

## Ein Adapter je Ratsinformationssystem

Wenige Hersteller bedienen die meisten deutschen Kommunen, und Städte
desselben Herstellers antworten mit denselben Eigenheiten. Deshalb gibt es
einen Adapter je **System**, nicht je Stadt (`council/cities/adapters/`). Jede
Reparatur kommt allen Städten dieses Systems zugute, auch denen, die noch
niemand angeschlossen hat.

Stand 11/2026 sind angeschlossen: Osnabrück, Braunschweig und Potsdam
(ALLRIS 4 über OParl), Wolfsburg (ALLRIS 4 ohne Schnittstelle), Münster und
Magdeburg (SessionNet) und Oldenburg selbst, dessen Adapter die eigene
`council.sqlite` liest. Welche Städte im Speicher liegen, steht als Code in
`council/cities/registry.py`, damit ein Eintrag im Pull Request sichtbar ist.

**Höflich abrufen.** Die Systeme gehören Städten. `council/cities/oparl.py`
stellt höchstens eine Anfrage je Sekunde und Host, mit Kennung und
Rückadresse im User-Agent. Ein Lauf, der nachts eine Stunde braucht, ist
billiger als ein gesperrter Zugang. `CITIES_RATE_SECONDS` kann den Abstand nur
vergrößern. Parallel läuft nur die Ernte über Städte hinweg: je Stadt ein
Prozess und eine eigene Rohdatei (`data/cities-raw/<slug>.sqlite`), denn die
Hauptdatenbank hat genau einen Schreiber.

## Annotatoren: eine Frage an die Dokumente ist ein Eintrag

Was über ein Dokument gesagt wird, steht in `council/cities/annotators.py`
als Register. Eine neue Frage an den Bestand ist ein Eintrag dort plus ein
Prompt in `kern/prompts.py`, ohne Schemaänderung. Zwei Fassungen desselben
Annotators liegen nebeneinander in `annotations` und lassen sich
gegeneinander messen.

Der Probelauf hat gezeigt, wo der Hebel liegt: Dasselbe Modell traf mit der
ersten Prompt-Fassung 73 % der Übertragbarkeits-Entscheidungen, mit der
zweiten rund 87 %. Ein elfmal teureres Modell lag bei 71 %. Deshalb trägt
jeder Annotator seine Fassung im Schlüssel und wird gegen ein Golden Set
gemessen (`eval/run_cities_transfer.py`).

### Das Urteil: Hat Oldenburg das schon?

Der Annotator `fit` (`council/cities/fit.py`) beantwortet je fremder Vorlage
zwei Fragen: Hat Oldenburg das schon, und lohnt es sich? Jede Vorlage bekommt
dafür ihre eigenen Belege aus dem Oldenburger Bestand und geht allein ins
Modell.

**Ohne Beleg keine Frage, ohne Beleg-Kennung kein Urteil.** Findet die
Belegsuche (`council/cities/evidence.py`) nichts aus Oldenburg, wird das
Modell gar nicht erst gefragt; die Antwort wäre eine Behauptung ins Leere.
Nennt es eine Kennung, die ihm nicht vorlag, fliegt der ganze Eintrag raus.
Beides wird gezählt, damit ein Rückgang auffällt.

Welche Vorlagen überhaupt teilnehmen, regelt `council/cities/auswahl.py` an
einer Stelle für alle Stufen: ein Zeitfenster je Stadt und die Vorlagenarten,
die eine Idee sein können.

### Dieselbe Idee in mehreren Städten

„Osnabrück hat X beschlossen, Oldenburg nicht“ ist eine Beobachtung. „Vier
von sechs Städten haben X, Oldenburg nicht“ ist ein Argument, und es filtert
Lokalkolorit von selbst weg. `council/cities/clusters.py` bildet solche
Gruppen (in der Oberfläche „Bewegungen“).

Der Freitext der Einordnung reicht dafür nicht: Von 1.461 verschiedenen
Instrument-Texten waren am 08.09.2026 fünf wortgleich in zwei Städten.
Eingebettet wird deshalb, und zwar nur das, was die Einordnung als die Idee
bezeichnet hat: Instrument plus Zusammenfassung. Der Vektor des ganzen
Papiers trüge Ortsnamen, Datum, Antragsteller und Verwaltungsprosa, für die
Frage „Ist das dieselbe Idee?“ alles Rauschen.

## Der Wächter für stumme Fehler

Am 08.09.2026 lagen vier Fehler gleichzeitig im Bestand, und keiner hatte
sich gemeldet: kein Absturz, kein roter Test, keine verdächtige Kennzahl. Die
Daten waren nur falsch. Bei einer Stadt hatten 0 von 700 Vorlagen ein
Ergebnis, obwohl fast 6.000 Tagesordnungspunkte eines trugen.

`council/cities/pruefung.py` prüft deshalb nach jeder Ernte, ob der Bestand
einer Stadt plausibel ist: der Anteil der Vorlagen mit Ergebnis, das
Verhältnis von Sitzungen zu Vorlagen, doppelte Kennungen und
Tagesordnungspunkte. Die Bänder sind gemessen, nicht gesetzt: Jede Regel
nennt den Bereich, in dem die Städte des Bestands liegen, und ist so weit
gefasst, dass eine gesunde weitere hineinpasst. Ein Befund heißt nicht
„kaputt“, sondern „sieh nach, bevor du diese Stadt benutzt“.

Der Adapter je System sorgt dafür, dass eine Reparatur allen Städten
desselben Herstellers zugutekommt. Den nächsten, noch unbekannten Fehler
bemerkt er nicht. Dafür ist diese Prüfung da, und sie muss mitwachsen: Ein
fünfter Fehler (ein Fünftel der Tagesordnungspunkte lag doppelt) schlug bei
keiner der ersten vier Regeln an.

## Betrieb

`scripts/check_cities.py` war der teuerste Cron und läuft seit 3.0.0 schlank:
werktags nur Oldenburg (ohne Netz und Modell; daraus entsteht „Anderswo“
unter neuen Beschlüssen), sonntags alles, Urteile nur über Neues, mit **einer**
Kostengrenze für den ganzen Lauf (`CITIES_MAX_USD`). Lange Läufe treten einem
wartenden Deploy zur Seite und behalten, was sie geschrieben haben.

Der Bestand entsteht nicht aus dem Cron, sondern aus einem einmaligen Lauf je
Stadt. Der Weg, die Kosten und das Runbook stehen unter
[Betrieb](/docs/betrieb/#städte-speicher-der-einmalige-backfill).

## Schnittstellen

| Route | Zweck |
|---|---|
| `GET /api/council/cities/ideas/fields` | je Themenfeld, wie viele Ideen dort liegen |
| `GET /api/council/cities/ideas` | was andere Städte haben und Oldenburg fehlt; ein Themenfeld ist Pflicht |
| `GET /api/council/cities/movements` | Ideen, die mehrere Räte hatten, je Idee eine Zeile |
| `GET /api/council/cities/movements/detail` | eine Bewegung mit allen Vorlagen |
| `GET /api/council/cities/search` | „Was haben andere Städte zu …?“ als Volltextsuche |
| `GET /api/admin/cities` | was im Speicher liegt, je Stadt |

Die Suche nutzt keinen Vektor über die Anfrage: Das bräuchte fastembed im
Web-Dienst, und dort ist es bewusst nicht
(siehe [ADR 0003](/docs/adr/0003-fastembed-statt-torch/)).
