---
kategorie: hinzugefuegt
---

**Ratslotse zählt jetzt selbst, welche Seiten aufgerufen werden — anonym.** Die
Nutzung ohne Anmeldung war bis dahin vollständig unbeobachtet: kein
Zugriffslog, keine Analytik. Wer die Startseite ansah oder einem geteilten
Beschluss-Link folgte, hinterließ keine Spur, und „wir hatten viele Besucher"
war ein Gefühl statt einer Zahl.

Gezählt werden vier Dinge: Tag, Seite, Client und ob jemand angemeldet war.
Kein Cookie, keine Kennung, keine IP, kein Referrer, kein User-Agent, keine
Verweildauer — und vor allem **keine Query**, denn die trägt hier alles
Persönliche (`?id=` sagt, welchen Beschluss jemand liest, `?q=` wäre die
Suchanfrage). Der Server nimmt zudem nur Seiten an, die er kennt; alles andere
fällt in eine Sammelzeile, damit ein fremder Browser die Tabelle weder
aufblähen noch beschriften kann. Kein Dritt-Dienst ist beteiligt: Die Meldung
geht an dieselbe Domäne, aus der die Seite kommt.

Eine einzige Ausnahme von „Query kommt nie mit": der Reiter auf der
Ratsinfo-Seite. Suche, Sitzungen, Themen und Analyse sind nicht vier Seiten,
sondern eine mit vier Reitern — ohne diesen einen Parameter (mit genau vier
erlaubten Werten) fielen die vier meistbenutzten Bereiche in eine Zeile
zusammen.

Im Admin-Panel steht das unter *Statistik*: Aufrufe je Tag, Besuche, Anteil
ohne Anmeldung, die meistgesehenen Seiten und die Aufteilung nach App und Web.
