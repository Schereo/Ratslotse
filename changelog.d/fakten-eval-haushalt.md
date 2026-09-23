---
kategorie: hinzugefuegt
---

**Eine Fakten-Eval prüft Lotti und Frag den Rat an 142 Haushaltsfragen — und trennt dabei Fehler im Kontext von Fehlern des Modells.** Jede Frage läuft über den echten Weg (eigenes Backend, angemeldet wie im Browser), der Prompt wird mitgeschnitten, und für jeden Goldwert aus der Datenbank steht fest, ob er dem Modell überhaupt vorlag — und unter welchem Jahr. Die Liste der Kontextfehler, gruppiert nach dem Baustein, der den Wert hätte liefern müssen, steht in `docs/fakten-eval.md`; der Modell-Prüfstand kennt die Suiten `fakten-haushalt` und `fakten-rat`.
