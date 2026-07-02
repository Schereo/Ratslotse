# Security Policy

## Eine Schwachstelle melden

Bitte melde Sicherheitslücken **nicht** über öffentliche Issues.

Nutze stattdessen die **[private Security-Advisory-Funktion von GitHub](https://github.com/Schereo/Ratslotse/security/advisories/new)**
(„Report a vulnerability"). So bleibt die Meldung vertraulich, bis ein Fix
verfügbar ist.

Bitte gib nach Möglichkeit an:

- betroffene Komponente (Backend, Frontend, Bot, Deploy) und Version/Commit,
- eine kurze Beschreibung und Reproduktionsschritte,
- die mögliche Auswirkung.

Wir bemühen uns um eine zeitnahe Rückmeldung und halten dich über den Fortschritt
auf dem Laufenden. Verantwortungsvolle Offenlegung wird geschätzt.

## Scope

Ratslotse verarbeitet öffentliche Ratsinformationen sowie Konto-/Abo-Daten
registrierter Nutzer:innen. Besonders relevant sind Auth/Session-Handling,
Rate-Limiting und alles, was Nutzerdaten berührt.
