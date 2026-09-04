# Bürgerportal

Das Bürgerportal bündelt private Beobachtungen aus Oldenburg zu moderierten
öffentlichen Problemen, ohne einen amtlichen Bearbeitungsstand vorzutäuschen.

## Sprache

### Meldeentwurf

Private, noch nicht abgesendete Vorstufe einer Meldung. Kein Problem und nicht
öffentlich. Nicht: Ticket, öffentliche Meldung.

### Meldung

Privater, bewusst abgesendeter Beitrag eines verifizierten Ratslotse-Kontos mit
der eigenen Beobachtung. Nicht: Ticket, Fall, öffentliche Meldung.

### Beobachtung

Erstmeldung oder spätere Aktualisierung derselben Person zu derselben Meldung.
Aktualisierungen erhöhen nicht die Zahl unabhängiger Meldungen. Nicht: Kommentar.

### Problem

Von Ratslotse moderierter öffentlicher Cluster aus mindestens einer
freigegebenen unabhängigen Meldung. Kein amtlicher Vorgang und keine Meldung.

### Öffentliche Projektion

Bewusst datenarme Sicht auf ein Problem. Sie enthält nur moderierten Titel,
neutrale Zusammenfassung, freigegebene Kategorie und Geografie sowie belegbaren
Status. Rohtexte, Identitäten, genaue private Orte, KI-Begründungen und
Moderationsnotizen gehören nie hinein. Nicht: anonymisierte Meldung.

### Lokale Weitergabeprüfung

Private, deterministische Sperre vor einer möglichen externen Verarbeitung der
aktuellen Meldungsrevision. „Kandidatin“ bedeutet nur, dass kein lokaler
Sperrgrund erkannt wurde. Nicht: Sicherheitsurteil, KI-Vorprüfung, Freigabe.

### Owner report history

The private **“Meine Meldungen”** read view of one eligible account's drafts and
submitted reports. Its overview is a bounded summary projection, not a public
problem feed or a processing queue. The product states remain only `Entwurf`
and `Privat eingegangen`.

### KI-Vorprüfung

Privates, unveränderliches Eignungsurteil zur aktuellen Inhaltsrevision einer
Meldung. Es darf allein nichts veröffentlichen. Nicht: automatische Freigabe.

### Moderationsentscheidung

Private, unveränderliche menschliche Entscheidung eines Ratslotse-Admins. Kein
amtlicher Bescheid.

### Statusereignis

Belegbare Änderung im Lebenslauf eines Problems. Ohne überprüfbare städtische
Quelle ist es kein Bearbeitungsstand der Stadt.

### Meldende Person

Person hinter dem verifizierten Konto. Öffentlich steht ausschließlich
„1 unabhängige Meldung“ oder „N unabhängige Meldungen“, nie „Reporter*in“.

### Moderator*in

Ratslotse-Admin. Nicht: Sachbearbeiter*in oder Stadtverwaltung.

## Persistierte Beziehung seit Iteration 4

Ein Konto kann mehrere private Meldeentwürfe besitzen. Bewusstes Absenden macht
einen Entwurf genau einmal zur Meldung und übernimmt den bestätigten Text als
erste unveränderliche Beobachtung. Weitere Beobachtungen werden angehängt; sie
bleiben Beiträge derselben meldenden Person. Weder Meldung noch Beobachtung ist
bereits ein öffentliches Problem.

## Private HTTP-Grenze seit Iteration 5

Ein aktives, bestätigtes Nicht-Admin-Konto kann seinen eigenen Entwurf über die
private Meldungs-API anlegen, lesen, revisionsgebunden ändern und bewusst
absenden. Die Eigentümer-ID stammt immer aus der Sitzung. Ein konto-spezifischer
Idempotenzschlüssel bezeichnet die ursprüngliche Erstellung; er ist weder eine
öffentliche Kennung noch Teil der Antwort. Fremde und unbekannte Meldungen sind
über dieselbe `404`-Antwort ununterscheidbar.

## Geführte Erfassung seit Iteration 6

Der **Meldechat** ist ein deterministischer Eingabe-Adapter für einen
Meldeentwurf, kein KI-Assistent und kein eigener Domänenakteur. Er sammelt
räumlichen Bezug, privaten genauen Ort, Beobachtungsdatum, kontrollierte
Kategorie und eigene Beschreibung schrittweise ein. Erst der vollständige
Inhalt wird serverseitig als Meldeentwurf angelegt. Vor dem Absenden kann die
meldende Person alle Angaben korrigieren und bestätigt ausdrücklich den eigenen
Beobachtungstext.

Eine kurzlebige, kontogebundene Browsersitzung hält unvollständige Eingaben und
die Referenz auf einen bereits angelegten Entwurf für die Wiederaufnahme. Sie
ist weder ein zweiter persistierter Meldeentwurf noch eine öffentliche Kennung.
Der Serverstand bleibt maßgeblich: Wiederaufnahme liest ihn über die private
HTTP-Grenze, Änderungen verwenden seine erwartete Inhaltsrevision, und ein
Konflikt überschreibt keine Eingabe still.

## Owner read view since Iteration 8

`PrivateReportStore.list_owned_reports` and `GET /api/meldungen` expose only a
newest-first, account-bound summary page. A summary carries a text preview of at
most 160 characters, controlled category and scope, observation date, honest
private state, revision, submission time, and last update. It deliberately omits
account identifiers, precise private locations, coordinates, idempotency data,
screening evidence, and forwarding state.

Selecting a row expands its detail directly inside that report's summary card
and reads the existing owner-bound detail endpoint. The detail is never detached
below later reports in the overview. Continuing a draft records that existing
report ID in the short-lived account-bound browser session and reloads the
authoritative server revision in the reporting flow. It never creates a
replacement draft. Submitted reports remain read-only.

## External AI pre-screening since Iteration 9

A successful private submission schedules a background pre-screening only after
its current revision has immutable `external_review_candidate` evidence under
the active local ruleset. The worker opens a fresh `PrivateReportStore`
connection and gives the evaluator only current observation texts plus the
controlled category and scope. Account/report identity, separately stored
location labels, coordinates, dates, idempotency data, local evidence, and
public-problem data never cross the evaluator boundary.

`civic_report_ai_screening_claims` provides a durable revision/version lease so
one provider attempt is active at a time. Immediately before dispatch, the
worker atomically marks the attempt started, revalidates the report revision,
owner, and local evidence, and reads a fresh minimized payload. A per-account
submission rate limit adds a cost ceiling without ever failing the private
response. A valid controlled result becomes one immutable
`civic_report_ai_screenings` row linked to the qualifying local evidence.
Provider failures and malformed output release the unfinished claim without
changing the private submission; expired claims can be recovered and completed
evidence is reused. A later observation makes old evidence ineligible without
deleting it.

The browser discloses automatic processing before submission and warns people
not to put personal or sensitive facts in free text. Owner HTTP responses and
states still expose no screening or forwarding information. The AI verdict is
private evidence for later human moderation, never a truth, urgency, safety,
assignment, rejection, or publication decision.
