# Qualitäts-Vergleich: vorher vs. nachher

Blind-Judge: `google/gemini-2.5-flash`, Seiten je Frage per Frage-Hash vertauscht.

| Frage | Aktualität | Quellentreue | Vollständigkeit | Klarheit | Gesamt |
|---|---|---|---|---|---|
| stadion-stand | nachher | gleich | nachher | nachher | **nachher** |
| stadion-kosten | vorher | gleich | vorher | vorher | **vorher** |
| stadion-parteien | gleich | gleich | gleich | vorher | **vorher** |
| stadion-verlauf | nachher | gleich | gleich | gleich | **nachher** |
| caeci-was | gleich | gleich | nachher | nachher | **nachher** |
| caeci-slang | vorher | gleich | vorher | vorher | **vorher** |
| floetenteich | nachher | gleich | nachher | gleich | **nachher** |
| fliegerhorst | nachher | nachher | nachher | gleich | **nachher** |
| entlastungsstrasse-stand | vorher | vorher | vorher | vorher | **vorher** |
| bplan831 | nachher | nachher | nachher | nachher | **nachher** |
| radverkehr-zuletzt | vorher | vorher | vorher | vorher | **vorher** |
| schulen-sanierung | gleich | gleich | gleich | gleich | **gleich** |

## Bilanz je Kriterium
- **aktualitaet**: nachher 5 · vorher 4 · gleich 3
- **quellentreue**: nachher 2 · vorher 2 · gleich 8
- **vollstaendigkeit**: nachher 5 · vorher 4 · gleich 3
- **klarheit**: nachher 3 · vorher 5 · gleich 4
- **gesamt**: nachher 6 · vorher 5 · gleich 1

## Jüngste Quelle im Kandidatenset (deterministisch)
| Frage | vorher | nachher | frischer |
|---|---|---|---|
| stadion-stand | 2025-12-03 | 2026-02-25 | **nachher** |
| stadion-kosten | 2026-06-01 | 2026-06-01 | **gleich** |
| stadion-parteien | 2026-06-01 | 2026-06-01 | **gleich** |
| stadion-verlauf | 2025-12-03 | 2025-12-03 | **gleich** |
| caeci-was | 2025-08-25 | 2025-08-25 | **gleich** |
| caeci-slang | 2025-08-25 | 2025-08-25 | **gleich** |
| floetenteich | 2025-11-04 | 2025-09-11 | **vorher** |
| fliegerhorst | 2026-02-23 | 2026-02-23 | **gleich** |
| entlastungsstrasse-stand | 2026-03-19 | 2026-05-21 | **nachher** |
| bplan831 | 2026-04-13 | 2026-04-13 | **gleich** |
| radverkehr-zuletzt | 2025-02-24 | 2026-04-20 | **nachher** |
| schulen-sanierung | 2026-03-16 | 2026-03-16 | **gleich** |

## Begründungen (A/B = verblindete Seiten, Zuordnung je Frage)
- **stadion-stand** (stadion+recency, gesamt nachher; A=nachher, B=vorher): Antwort A präsentiert den neuesten Sachstandsbericht vom 25. Februar 2026 als aktuellsten Stand, während Antwort B nur bis zum 3. Dezember 2025 reicht. Zudem ist die chronologische Darstellung in A prägnanter und fokussierter auf die wesentlichen Entwicklungen.
- **stadion-kosten** (stadion+geld, gesamt vorher; A=vorher, B=nachher): Antwort A ist aktueller, da sie den Fehlbetrag der Stadionplanungsgesellschaft mbH für 2024 erwähnt, der in Antwort B fehlt. Antwort A bietet auch eine detailliertere Aufschlüsselung der Fehlbeträge und eine bessere Strukturierung der Informationen.
- **stadion-parteien** (stadion+partei, gesamt vorher; A=vorher, B=nachher): Antwort A ist klarer strukturiert und präsentiert die Informationen thematisch geordnet, was die Lesbarkeit und das Verständnis verbessert. Antwort B mischt die Informationen stärker, was die Übersichtlichkeit beeinträchtigt.
- **stadion-verlauf** (stadion+verlauf, gesamt nachher; A=nachher, B=vorher): Antwort A ist aktueller, da sie den Jahresabschluss 2023 der Stadionplanungsgesellschaft mbH mit dem Datum 26. August 2024 korrekt dem Rat zuordnet, während Antwort B diesen dem Ausschuss für Finanzen und Beteiligungen am 7. August 2024 zuschreibt und die Ratssitzung nur als Bestätigung nennt. Zudem listet Antwort A die Sachstandsberichte für 2024 und 2025 in chronologisch korrekter Reihenfolge auf, während Antwort B hier eine Vermischung der Daten aufweist.
- **caeci-was** (entitaet, gesamt nachher; A=nachher, B=vorher): Antwort A ist vollständiger, da sie auch andere Brückenprojekte im Umfeld erwähnt, die im Kontext der Cäcilienbrücke relevant sein könnten. Beide Antworten nutzen die gleichen Quellen und stellen den Sachstand ähnlich dar.
- **caeci-slang** (entitaet+glossar, gesamt vorher; A=vorher, B=nachher): Antwort A ist aktueller, da sie den Sachstandsbericht vom April 2024 als zuletzt zur Kenntnis genommen darstellt, während B dies nicht explizit hervorhebt. Zudem ist A vollständiger, da es die Abgrenzung zu anderen Brückenprojekten thematisiert, was für die Klarheit der Antwort relevant ist.
- **floetenteich** (entitaet, gesamt nachher; A=vorher, B=nachher): Antwort B ist aktueller, da sie einen Sachstandsbericht zum Genehmigungsverfahren Tiefengeothermie vom September 2025 erwähnt, während Antwort A nur bis Oktober 2024 reicht. Zudem ist die Struktur von B etwas prägnanter und fokussierter auf die Hauptthemen.
- **fliegerhorst** (entitaet, gesamt nachher; A=nachher, B=vorher): Antwort A ist aktueller, da sie die Entscheidung zur Dreifeldhalle im Februar 2026 korrekt datiert und die Diskussion um die Fliegerhorst-Straße mit einem 'Faktenupdate' im September 2023 erwähnt. Antwort B hingegen datiert die Dreifeldhalle ebenfalls auf 2026, aber erwähnt auch ältere, vertagte Diskussionen, ohne den neuesten Stand klar hervorzuheben.
- **entlastungsstrasse-stand** (recency, gesamt vorher; A=vorher, B=nachher): Antwort A ist aktueller, da sie einen Beschluss vom März 2026 als den letzten Stand nennt, während Antwort B einen Beschluss vom April 2026 nennt, aber den letzten Stand als März 2026 angibt. Antwort A bietet zudem eine detailliertere chronologische Darstellung und mehr spezifische Informationen aus den Protokollen, was sie vollständiger und klarer macht.
- **bplan831** (recency+supersedes, gesamt nachher; A=nachher, B=vorher): Antwort A ist aktueller, da sie den Beschluss des Bebauungsplans 831 als Satzung am 13. April 2026 korrekt als finalen Schritt darstellt, während Antwort B einen Zwischenschritt des Ausschusses als Satzungsbeschluss nennt und den Ratsbeschluss als Bestätigung. Antwort A ist auch quellentreuer, da sie die Zitate der Politiker präziser und mit korrekter Datumsangabe wiedergibt.
- **radverkehr-zuletzt** (recency, gesamt vorher; A=vorher, B=nachher): Antwort A ist aktueller, da sie Beschlüsse aus dem Jahr 2025 erwähnt, die in Antwort B fehlen oder anders datiert sind. Antwort A präsentiert die Informationen auch in einer klareren und besser strukturierten Weise, die die neuesten Entwicklungen hervorhebt.
- **schulen-sanierung** (breit, gesamt gleich; A=vorher, B=nachher): Beide Antworten sind in Bezug auf Aktualität, Quellentreue, Vollständigkeit und Klarheit sehr ähnlich. Es gibt keine signifikanten Unterschiede, die eine Antwort deutlich besser als die andere erscheinen lassen würden.
