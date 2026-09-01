---
kategorie: behoben
---

**Der nächste Einlesevorgang der integrierten Schulden wäre abgebrochen.** Die
Spalte für die übrigen Schulden heißt in einer gewachsenen Datenbank längst
`other`, im Tabellen-Entwurf stand aber weiter der alte deutsche Name — der
Einlesevorgang nannte ihn und wäre auf dev und Prod im Datenbankfehler
gestorben. Auf einer frischen Datenbank funktionierte er, weshalb kein Test
etwas merkte. Ein neuer Prüflauf hält das frische Schema ab jetzt gegen jede
Umbenennung.
