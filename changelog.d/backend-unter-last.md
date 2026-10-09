---
kategorie: geaendert
---

**Ratslotse bleibt schnell, wenn viele gleichzeitig kommen.** Der Server prüfte bei jeder einzelnen Anfrage sein Datenbank-Schema neu; das kostete mehr Zeit als die meisten Antworten selbst, und bei zwanzig gleichzeitigen Anfragen dauerte es drei Sekunden statt einer halben. Jetzt geschieht das einmal beim Start. Angemeldete Seiten warten außerdem nicht mehr bis zu fünf Sekunden, wenn im Hintergrund gerade jemand in die Datenbank schreibt, und ein Fehler hält nicht mehr den ganzen Dienst an. Die Auswertung „Analyse“ lädt in Millisekunden statt in einer Sekunde, Personenseiten spürbar schneller. Zwei Seiten unter *Analyse → Ziele* (Klima, Wohnungsbau) brachen mit einem Fehler ab und öffnen wieder.
