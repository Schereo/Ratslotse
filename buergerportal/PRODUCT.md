# Produktvertrag „Probleme in Oldenburg“

## Identität und Sprache

Der Bereich heißt **Probleme in Oldenburg**, in knapper Navigation
**Probleme**. **Problemkarte** bezeichnet nur die Kartenansicht. Das Angebot ist
ein unabhängiges Ratslotse-Bürgerprojekt und kein amtliches Meldesystem der
Stadt Oldenburg.

Amtlich klingende Wörter wie Ticket, Fallnummer, Mängelmelder oder unbelegter
Bearbeitungsstand werden nicht verwendet. Karten- und Ranglistenfarben folgen derselben beschrifteten Hafenblau-Skala
für die Meldehäufigkeit: 1, 2–4, 5–9 oder 10 und mehr.

## Öffentliche Übersicht — Iteration 2

`/probleme` ist ohne Anmeldung lesbar und auf der Feature-Umgebung freigeschaltet.
Die Karte ist die Standardansicht. Direkt erreichbare Themenchips filtern die
Karte. Veröffentlichte Projektionen brauchen keinen zusätzlichen Freigabe- oder
Mehrfachmeldungs-Status in der Oberfläche: Karte, Auswahl und Rangliste zeigen
vorerst weder Statusfilter noch Status-Badges. Die exakte Meldezahl trägt die
Mengeninformation bereits selbst.

Der Tab „Rangliste“ ersetzt das frühere Status-Board; der kompatible Direktlink
bleibt `/probleme?view=meistgemeldet`. Die Rangliste enthält nur ungelöste
Projektionen und ordnet sie nach der lebenszeitlichen Gesamtzahl freigegebener
unabhängiger meldender Personen, absteigend. Gleichstände werden nach Titel und
dann ID aufgelöst. Jede Zeile nennt die exakte Zahl; sie zeigt Aufmerksamkeit,
nicht Wahrheit, Dringlichkeit, Schadenshöhe oder Betroffenenzahl. Alle Ränge
stehen auf Desktop und Mobil als gleich breite Zeilen untereinander. Ihre Balken
wachsen auf einer gemeinsamen Null-bis-Maximum-Schiene von links nach rechts;
die ersten drei unterscheiden sich kompakt durch Tönung, Schrift und Rangzahl,
nicht durch eine andere Kartenbreite. Die Quellenzeile bleibt direkt unter der
Rangliste sichtbar, die Projekt-/Amtlichkeitseinordnung im Pflicht-Fuß. Lotti ist
der eine kontextuelle Hilfezugang für Karte und Rangliste. Geschlossen ruht sie auf der
Karte beziehungsweise weist in der Rangliste auf den Inhalt, geöffnet erklärt
sie mit der zustandsgebundenen `erklaert`-Regung Skala, Zählgrenzen und fiktive
Beispiele. Sie ist ein echter Tastatur- und Touch-Button und feiert kein
ungelöstes Problem.

Die per Tastatur bedienbare Vorschau enthält ausschließlich die freigegebene
Zusammenfassung und Metadaten der öffentlichen Projektion. Punkte,
Einrichtungen, Routen, Polygone und MultiPolygone lassen sich nur mit gültiger
Geometrie auf der Karte fokussieren. Stadtweite und fehlerhafte Projektionen
bleiben in der Rangliste; die Vorschau erklärt, warum kein Kartenpunkt erfunden
wird. Bewegungen markieren den Eintritt in die Rangliste, Hover/Fokus, Aufklappen,
Lotti-Hilfe und Kartenfokus. Sie sind zustandsgebunden, laufen nicht zufällig
und entfallen bei `prefers-reduced-motion`.

`GET /api/probleme` liefert die moderierte Zusammenfassung, die exakte Zahl und
das Häufigkeitsband, aber niemals Identitäten, Rohtexte, einzelne Meldungen oder
private Moderationsdaten. Die Feature-Daten sind im Titel und in der Oberfläche
als frei erfundene Beispiele gekennzeichnet. Sie werden idempotent ausschließlich
in der separaten Feature-Datenbank erzeugt.

## Öffentliche Detailseite — Iteration 3

Die kanonische Web-Route `/probleme/[id]` zeigt dieselbe datensparsame
öffentliche Projektion wie die Übersicht: Titel, moderierte Zusammenfassung,
Kategorie, freigegebenen Ortsbezug, ehrliche Geometrie, exakte unabhängige
Meldezahl und Häufigkeitsband. `GET /api/probleme/{problem_id}` verwendet
identische Sichtbarkeits- und Projektionsregeln wie die Liste. Unveröffentlichte,
gelöste, meldungslose oder unbekannte IDs liefern keinen Datensatz.

Karte und Rangliste trennen „Auf der Karte zeigen“ von „Details ansehen“.
Ehrlich kartierbare Details fokussieren ihre Geometrie; stadtweite und ungültige
Geografien erklären knapp, warum keine Karte erscheint. Status-Badges und eine
aus Daten oder Statuswerten erfundene Zeitleiste bleiben aus. Lotti ist der eine
kontextuelle Hilfezugang für Zählgrenzen, Geografie und fiktive Beispiele. Die
Seite lässt sich über ihre kanonische Web-URL teilen und bleibt ohne Konto
lesbar.

Der statische Android-Export kann beliebige IDs nicht vorab erzeugen. Dort
öffnet `/probleme?problem=[id]` dieselbe Darstellung innerhalb der Übersicht;
eingehende Web-Links werden auf diesen Query-Pfad übersetzt. Auch negative IDs
der ausschließlich auf `feature` vorhandenen Beispiele sind gültig. Die native
iOS-App besitzt noch keine Bürgerportal-Ansicht und öffnet diese öffentlichen
Links deshalb im Web.

## Private Meldungs-Domäne — Iteration 4

Die noch nicht über HTTP erreichbare Persistenz trennt private Meldeentwürfe und
Beobachtungen vollständig von öffentlichen Problemprojektionen. Jeder private
Zugriff ist an die ID der meldenden Person gebunden; Änderungen verlangen ein
bestehendes, aktives und bestätigtes Nicht-Admin-Konto. Ein Entwurf kann geändert
und genau einmal bewusst abgesendet werden; dabei entsteht atomar seine erste
unveränderliche Beobachtung. Spätere Beobachtungen werden
angehängt und zählen nicht als weitere Person.

Private Rohtexte, bestätigte Texte, genaue Orte, Beobachtungsdaten und
Kontozuordnung werden nicht über `ProblemStore` lesbar. Die Kontolöschgrenze des
privaten Stores und die bestehende zentrale Kontolöschung entfernen diese Daten,
ohne öffentliche Projektionen zu ändern. Es gibt in dieser Iteration keinen
Endpunkt, keine Oberfläche, keinen Seeder für private Daten und keine KI-,
Moderations-, Cluster- oder Veröffentlichungslogik.

## Private Entwurfs- und Einreichungs-API — Iteration 5

Unter `/api/meldungen` kann ein aktives, bestätigtes Nicht-Admin-Konto einen
eigenen Entwurf idempotent anlegen, wieder lesen, mit erwarteter Inhaltsrevision
ersetzen und genau einmal bewusst absenden. Die Eigentümer-ID stammt nur aus der
authentifizierten Sitzung. Fremde und unbekannte IDs liefern dieselbe
`404`-Antwort.

Die privaten Antworten enthalten Beschreibung, kontrollierte Kategorie,
privaten Ortsbezug, Lebenslauf und Revision, aber keine Konto-ID,
Idempotenzschlüssel oder internen Anfragefingerabdruck. Derselbe
Erstellungsschlüssel gilt nur innerhalb eines Kontos. Identische
Erstellungs-Retries liefern denselben Entwurf; abweichende
Schlüsselwiederverwendung und veraltete Revisionen liefern `409`. Ein exakt
identischer Absende-Retry ist idempotent, ein abweichender Retry bleibt
geschlossen.

Die API verändert keine öffentliche Problemprojektion. Sie ergänzt keine
späteren Beobachtungen, keine privaten Feature-Beispiele und keine KI-,
Moderations-, Cluster- oder Veröffentlichungslogik.

## Geführter privater Meldechat — Iteration 6

Von der öffentlichen Übersicht führt die hervorgehobene Aktion „Problem melden“
nach `/probleme/melden`. Ohne Konto bewahrt die bestehende Anmeldung dieses Ziel
für den Rücksprung. Die Melderoute selbst bleibt aktiven, bestätigten
Nicht-Admin-Konten vorbehalten; Admin-Konten erhalten statt einer
Meldeoberfläche eine Erklärung der Rollentrennung.

Der Meldechat ist kein KI-Chat. Er fragt nacheinander räumlichen Bezug, privaten
genauen Ort, Datum der eigenen Beobachtung, Kategorie und Beschreibung ab. Der
Ort besteht aus eigener Bezeichnung und einer Markierung auf der Oldenburg-Karte;
bei „Ganz Oldenburg“ entfallen beide bewusst. Der Kalendertag am
Beobachtungsort Oldenburg ist dabei maßgeblich; ein zukünftiges Datum oder
unvollständige Angaben gelangen nicht an die API. Vor und zurück verändert
bereits gegebene Antworten nicht.

Nach vollständiger Eingabe legt die Oberfläche mit einem stabilen,
kontogebunden verwendeten Idempotenzschlüssel einen privaten Entwurf an. Nach
einem mehrdeutigen Netzfehler wiederholt sie dafür unverändert die erste
Anlegenutzlast; spätere lokale Korrekturen folgen erst revisionsgebunden, sobald
die Entwurfs-ID wieder vorliegt. Ein kurzlebiger, kontogebundener Sitzungsstand
ermöglicht die Wiederaufnahme; für einen schon angelegten Entwurf wird der
maßgebliche Serverstand erneut gelesen.
Auf der Prüfseite bleiben alle Angaben korrigierbar. Änderungen werden mit der
erwarteten Revision gespeichert und erst danach wird exakt der ausdrücklich
bestätigte Text abgesendet. Bei einem Revisionskonflikt bleibt die lokale
Korrektur erhalten, bis die Person den neueren Serverstand bewusst lädt.

Nach erfolgreichem Absenden ist der lokale Sitzungsstand entfernt. Die
Bestätigung sagt nur, dass die Meldung privat eingegangen und nicht automatisch
öffentlich ist. Der Meldeweg nennt dauerhaft die Projektunabhängigkeit und weist
knapp darauf hin, dass er kein Notrufkanal ist; bei akuter Gefahr gilt 112. Er
führt keinen öffentlichen Problemabgleich, keine Sicherheitsklassifikation,
keinen KI-Aufruf, keine Moderation, Clusterung oder Veröffentlichung aus.

## Lokale Weitergabeprüfung — Iteration 7

Eine bewusst abgesendete Meldung erhält serverseitig eine private,
revisionsgebundene lokale Weitergabeprüfung. Der begrenzte Regelsatz hält
Meldungen mit eindeutigen Notfallformulierungen, direkten Kontaktangaben oder
nicht unterstützten Textformaten für ausschließlich manuelle Behandlung zurück.
Die Meldung selbst bleibt in jedem Fall privat eingegangen.

Ohne lokalen Sperrgrund heißt das Ergebnis nur „Kandidatin für eine mögliche
spätere externe Vorprüfung“. Es behauptet weder Sicherheit noch Eignung,
Wahrheit, Dringlichkeit oder Veröffentlichung. Eine neuere Beobachtung und jeder
Prüf- oder Speicherfehler sperren die Weitergabe wieder. Die Prüfung sendet
keinen Inhalt an externe Dienste, erscheint in keiner HTTP-Antwort und verändert
keine öffentliche Projektion.

## Owner-bound “Meine Meldungen” — Iteration 8

`/meine-meldungen` is available only to active, verified non-admin accounts and
is linked from their personal navigation. It lists the account's own activity
newest first. Each row shows a bounded description preview, observation date,
category, scope, last update, and exactly one honest state: `Entwurf` or
`Privat eingegangen`. Older rows load through bounded `limit`/`offset`
pagination. Loading, empty, failure, and retry states are explicit.

The overview contains no account ID, precise private location, coordinates,
idempotency or request fingerprint, screening outcome, forwarding state, or
public metadata. Selecting a row fetches its complete owner-bound detail. Draft
details can continue in `/probleme/melden`; the existing server report ID and
current revision remain authoritative, and no second draft is created.
Submitted details are read-only.

This view does not claim that Ratslotse or the City of Oldenburg is processing a
report. It performs no AI call, moderation, clustering, assignment, or
publication and does not change the public problem projection.

## Routen

| Route | Sichtbarkeit | Stand |
|---|---|---|
| `/probleme` | öffentlich | Iteration 2 |
| `/probleme/[id]` | öffentlich | Iteration 3 |
| `/probleme?problem=[id]` | öffentlich | Iteration 3, statischer App-Adapter |
| `/probleme/melden` | verifiziertes Nicht-Admin-Konto | Iteration 6 |
| `/meine-meldungen` | verifiziertes Nicht-Admin-Konto | Iteration 8 |
| `/admin/meldungen` | Admin | reserviert |

Iteration 8 adds only the owner-bound private read view and draft continuation.
Later-observation APIs, a public timeline, external AI, moderation tooling,
clustering, assignment, and automatic publication remain reserved for later
slices.
