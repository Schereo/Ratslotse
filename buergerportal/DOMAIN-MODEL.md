# Domänenmodell und Zugriffsgrenzen des Bürgerportals

## Verbindliche Grenze

Private Meldungen sind Evidenz. Öffentliche Probleme sind moderierte,
datensparsame Projektionen. Auch wenn beide Domänen später dieselbe
`ratslotse.sqlite` verwenden, besitzen sie getrennte Tabellen und Interfaces.
Eine öffentliche Antwort wird niemals aus Rohmeldungen serialisiert.

| Privat | Öffentlich nach Freigabe |
|---|---|
| Konto-ID und Meldungstext | moderierter Titel und neutrale Zusammenfassung |
| einzelne Beobachtungen | kontrollierte Kategorie und freigegebene Geografie |
| genauer Eingabeort | vergröberter oder ausdrücklich freigegebener Ortsbezug |
| KI-Urteil und Begründung | lebenszeitliche Zahl freigegebener unabhängiger Meldungen plus Häufigkeitsband |
| Moderationsnotiz | belegbarer Status |

Seit Iteration 2 enthält die Übersichtsprojektion die moderierte öffentliche
Zusammenfassung und die exakte lebenszeitliche Zahl freigegebener unabhängiger
meldender Personen. Aktualisierungen derselben Person erhöhen sie nicht. Daneben
bleibt das daraus abgeleitete Band `once`, `several`, `many` oder `very_many`
für die gemeinsame Hafenblau-Skala von Karte und Rangliste. Zahl und Band
bedeuten gemeinschaftliche Bestätigung und Aufmerksamkeit, nie Wahrheit,
Dringlichkeit, Schadenshöhe oder die Zahl betroffener Personen. Identitäten,
Rohtexte, Einzelmeldungen und Moderationsdaten bleiben privat.

## Privates Schreibmodell — Iteration 4

`PrivateReportStore` besitzt die Tabellen `civic_reports` und
`civic_report_observations`; `ProblemStore` besitzt sie ausdrücklich nicht. Eine
Meldung verweist per Fremdschlüssel auf ein bestehendes Ratslotse-Konto; nur ein
aktives, bestätigtes Nicht-Admin-Konto darf private Inhalte anlegen oder verändern. Jede
private Lese- und Änderungsoperation verlangt die ID der meldenden Person.
Unbekannte und fremde Meldungs-IDs werden dabei nicht unterschieden und geben
keinen Inhalt preis.

Ein neuer Datensatz beginnt als `draft`. Beschreibung, kontrollierte Kategorie,
geografischer Bezug, privater genauer Ort und Beobachtungsdatum können nur in
diesem Zustand geändert werden. Stadtweite Entwürfe speichern keinen genauen
Ort; alle anderen Bezüge brauchen Ortsbezeichnung und Koordinaten innerhalb
einer konservativen Hülle Oldenburgs. Ein Beobachtungsdatum darf nicht nach dem
aktuellen Kalendertag in Oldenburg (`Europe/Berlin`) liegen. Jede Inhaltsänderung
erhöht die Revision.

`submit_owned_draft` ist ein atomarer, einmaliger Übergang zu `submitted`: Der
bestätigte Text und Absendezeitpunkt werden gesetzt und dieselbe Transaktion
hängt genau eine erste Beobachtung an. Danach bleibt der Entwurf unveränderlich.
Weitere Beobachtungen erhöhen die Inhaltsrevision und werden angehängt, nie
überschrieben; sie gehören weiterhin derselben Person und sind keine zusätzliche
unabhängige Meldung. Datenbank-Constraints und Trigger sichern Eigentümer-ID,
kontrollierte Kategorien und Geografie, Zeitwerte, Revisionsbindung und die
Unveränderlichkeit gespeicherter Beobachtungen zusätzlich zum Store ab.

Die privaten Migrationen werden einzeln atomar in
`civic_report_schema_migrations` protokolliert und sind wiederholbar. Eine
Folgemigration ergänzt ältere private Schemata um Inhaltsrevisionen und erneuert
deren Invariantentrigger; eine weitere ergänzt Erstellungs-Idempotenz samt
eindeutigem Konto-Schlüssel und privatem Anfragefingerabdruck. Eine additive
Folgemigration erneuert auch bei bereits angewendeter Idempotenzmigration die
Eigentümertrigger für Nicht-Admin-Konten. Bestehende Meldungsdaten werden dabei
nicht ersetzt. Die Migrationen verändern weder
`civic_problems` noch `civic_problem_feature_examples`. Die explizite
Kontolöschgrenze `erase_reporter_data` entfernt alle privaten Meldungen und ihre
Beobachtungen einer Eigentümer-ID per Fremdschlüssel-Kaskade. Zusätzlich kennt
die zentrale Kontolöschung `civic_reports`, damit auch der bestehende
DSGVO-Löschweg keine privaten Daten zurücklässt. Beide Wege schreiben nicht in
öffentliche Projektionen.

## Private HTTP-Grenze — Iteration 5

`POST /api/meldungen/entwuerfe`, `GET /api/meldungen/{report_id}`,
`PUT /api/meldungen/{report_id}/entwurf` und
`POST /api/meldungen/{report_id}/absenden` bilden nur den bestehenden privaten
Lebenslauf ab. Die Reporter-ID kommt ausschließlich aus der authentifizierten
Sitzung. Zugelassen sind aktive, bestätigte Nicht-Admin-Konten; alle privaten
Antworten besitzen eine eigene Form ohne Konto-ID, Idempotenzschlüssel oder
Erstellungsfingerabdruck.

Der Erstellungsschlüssel ist je Konto eindeutig. Ein Fingerabdruck der
normalisierten ursprünglichen Anfrage lässt identische, auch konkurrierende
Retries denselben Entwurf laden und weist denselben Schlüssel mit anderem
Inhalt als Konflikt zurück. Änderungen und Absenden vergleichen die erwartete
Inhaltsrevision atomar. Ein identischer Absende-Retry mit derselben erwarteten
Vor-Revision liefert dieselbe bereits abgesendete Meldung; jede abweichende oder
veraltete Wiederholung scheitert mit `409`. Fremde und unbekannte IDs liefern
für Lesen, Ändern und Absenden dieselbe `404`-Antwort.

Die HTTP-Grenze bietet noch keinen Nachtrag späterer Beobachtungen. Sie schreibt
weder in `civic_problems` noch in Feature-Beispiele und ruft keine KI,
Moderation, Clusterung oder Veröffentlichung auf.

## Geführter Frontend-Adapter — Iteration 6

`/probleme/melden` bleibt hinter der bestehenden Anmeldungs- und Kontosperre.
Der Adapter stellt deterministische Fragen und bildet die Antworten erst nach
vollständiger Eingabe auf den privaten API-Inhalt ab. Für `citywide` sendet er
bewusst leere Ortsbezeichnung und `null`-Koordinaten; alle anderen Bezüge
verlangen eine private Ortsbezeichnung und eine innerhalb der Oldenburg-Hülle
markierte Position. Er liest keine öffentlichen Problemprojektionen und ruft
keinen KI- oder Assistenzendpunkt auf.

Vor der ersten Serverpersistenz besitzt die Oberfläche einen stabilen
Idempotenzschlüssel. Nach einem mehrdeutigen Netzfehler bewahrt sie zusätzlich
die unveränderte erste Anlegenutzlast: So kann sie zunächst die ID desselben
Entwurfs wiedererlangen und eine inzwischen lokale Korrektur anschließend als
revisionsgebundene Änderung speichern, statt den Schlüssel mit anderem Inhalt
zu wiederholen. Ein kurzlebiger `sessionStorage`-Datensatz ist an die Konto-ID
aus der authentifizierten Sitzung gebunden, verwirft fremde, ungültige oder
abgelaufene Inhalte und wird nach erfolgreichem Absenden entfernt. Enthält er
eine Melde-ID, lädt die Oberfläche den maßgeblichen
Serverentwurf über `GET` neu. Änderungen auf der Prüfseite werden mit der
zuletzt gelesenen Inhaltsrevision per `PUT` gespeichert, bevor exakt der
geprüfte Text per `POST …/absenden` bestätigt wird. Bei `409` bleibt die lokale
Korrektur sichtbar; ein neuerer Serverstand wird erst auf ausdrücklichen Wunsch
geladen.

Der Adapter ist keine zweite Schreibdomäne. Er erzeugt weder eine öffentliche
Projektion noch Problemzuordnungen, Moderationsdaten, KI-Urteile oder spätere
Beobachtungen.

## Lokale Weitergabeprüfung — Iteration 7

Nach dem privaten Absenden prüft `PrivateReportStore` alle bis zur aktuellen
Inhaltsrevision bestätigten Beobachtungstexte mit einem versionierten lokalen
Regelsatz. Eindeutige Notfallformulierungen, direkte E-Mail- oder
Telefonangaben sowie nicht unterstützte Steuerzeichen halten die Revision bei
`manual_review_only`. Andernfalls bedeutet `external_review_candidate` nur,
dass diese begrenzten Regeln keinen Sperrgrund gefunden haben — nie, dass der
Inhalt sicher, geeignet, wahr oder nicht dringend ist.

`civic_report_local_screenings` speichert ausschließlich Meldungs-ID,
Inhaltsrevision, Regelsatzversion, kontrolliertes Ergebnis und Grundcodes sowie
den Erstellungszeitpunkt. Konto-ID, Roh- und bestätigter Text, genauer Ort und
Koordinaten werden nicht dupliziert. Ein zusammengesetzter Fremdschlüssel bindet
die Evidenz an eine vorhandene Beobachtungsrevision; Trigger erlauben nur die
aktuelle eingereichte Revision eines weiterhin zugelassenen Kontos und
verhindern Änderung oder direkte Löschung. Konto- und Meldungslöschung kaskadieren
weiterhin vollständig.

Gleiche und konkurrierende Prüfversuche liefern dieselbe unveränderliche
Evidenz. Eine spätere Beobachtung macht sie als aktuelle Weitergabebedingung
unbrauchbar. Schlägt die lokale Prüfung oder ihre Persistenz fehl, bleibt die
private Einreichung erhalten, aber es existiert keine weitergabefähige
Kandidatin. Es gibt weder externen Aufruf noch HTTP-Ausgabe des Ergebnisses.

## Owner-bound read model — Iteration 8

`PrivateReportStore.list_owned_reports(reporter_id, limit, offset)` returns an
explicit `PrivateReportPage`, ordered by `updated_at DESC, id DESC`. The Store
accepts only active, verified non-admin owners and bounds each page to 1–50
rows. Each `PrivateReportSummary` uses at most 160 characters of the current
draft or submitted description and includes only category, scope, observation
date, honest private state, revision, submission time, and update time. The
query does not select account identity, precise location, coordinates,
idempotency or request fingerprints, local screening evidence, or forwarding
state.

`GET /api/meldungen?limit=…&offset=…` takes the owner exclusively from the
authenticated session and serializes the same narrow model. Exact private facts
are fetched only after selection through the existing indistinguishable-404
detail boundary. `/meine-meldungen` exposes loading, empty, retryable error, and
bounded older-page states. Before a human decision its states are `Entwurf` and `Privat eingegangen`.
Iteration 10 adds only the exact final human outcome and a reporter-facing
rejection explanation; it still does not infer City processing.

Draft continuation stores the selected existing report ID in the short-lived,
account-bound browser session. Navigation proceeds only after that handoff is
stored successfully. The reporting adapter then reads the authoritative server
report and revision before any update, so continuation cannot fall through to a
new draft creation. Submitted reports are read-only in this slice. Client query keys include the
account ID, private report queries are removed whenever authentication changes,
and those queries are excluded from the native app's persisted offline cache.

## Revision-bound external AI pre-screening — Iteration 9

The external screening module can claim only a submitted report whose current
revision has `external_review_candidate` evidence under the active local
ruleset and whose owner remains an active, verified non-admin account. The
evaluator input is a deliberately narrow value containing only ordered current
observation texts, controlled category, and controlled scope. It has no
account/report identity, stored location label, coordinates, observation dates,
idempotency/fingerprint data, local-screening result, forwarding state, or
public-problem data.

`civic_report_ai_screening_claims` owns the durable lease for one report
revision and assessment version. Immediately before provider dispatch, a
single transaction marks the attempt started, revalidates the current revision,
owner eligibility, and local evidence, and reads the minimized input. An active
lease blocks duplicate provider work; a failed worker releases its unfinished
claim and an expired lease can be reclaimed. A completed assessment is reused.
The account-scoped submission limiter provides an additional cost ceiling while
quota exhaustion leaves the private response unchanged. The adapter calls only
`kern.llm.chat_complete`, uses a non-overridable no-training/Zero Data Retention
provider policy and `_feature="civic_report_screening"`, treats report text as
untrusted data, and accepts only strict JSON with one allowed verdict/reason
combination. Its named system prompt lives in `kern/prompts.py`.

`civic_report_ai_screenings` stores the report/revision identity, qualifying
local-screening row, assessment/prompt version, controlled verdict and reason,
model identifier, and creation time. It stores no owner, report text, location,
date, raw prompt/response, provider error, or reasoning. Foreign keys and
triggers keep evidence revision-bound, controlled, append-only, and immutable.
A newer observation makes previous evidence stale while preserving its audit
record; report/account deletion cascades through claims and assessments.

Submission schedules this work as a FastAPI background task and returns the
unchanged private owner model. The worker always opens its own store connection.
Provider, parsing, persistence, and scheduling failures are logged generically
and cannot change or fail the private submission. No assessment is exposed to
owners or public projections, and no verdict performs moderation, assignment,
rejection, clustering, or publication.

## Human moderation — Iteration 10

`moderator` is a dedicated account role with no general admin or owner-report
capability. Active admins and active, verified moderators may use
`PrivateReportStore.list_reports_for_moderation`,
`get_report_for_moderation`, and `decide_report` through the separate
`/api/moderation/meldungen` boundary. Queue and detail values deliberately omit
reporter/account identity, exact location labels, coordinates, idempotency data,
provider/model metadata, claims, and public-problem fields. Only current
submitted revisions with current local evidence and an eligible owner are
reviewable, oldest first. Unknown and no-longer-reviewable IDs share one `404`.

`civic_report_moderation_decisions` stores one `approved` or `rejected` decision
per exact report revision, its authorized reviewer ID for internal audit, the
decision time, and—only for rejection—a trimmed explanation of at most 1000
characters. Database triggers revalidate report, owner, local evidence, and
reviewer authorization. Decision rows are append-only and immutable; exact
retries return the same row, while conflicting and concurrent attempts cannot
replace it. Rejection prevents any later observation. Deleting the reporter cascades all report evidence. Deleting a reviewer account
preserves the immutable decision and its historical integer reviewer ID without
a cascading account foreign key; the deleted account row and identity are no
longer available, and direct actor changes remain blocked.

`civic_report_rejection_draft_claims` provides a durable version/revision lease.
At dispatch, the Store revalidates the pending report and reviewer. For a local
`manual_review_only` result, `RejectionDraftInput` contains no observation text
or AI advice—only controlled local reason codes, category, and scope. Otherwise
it may contain the already minimized observation texts and controlled AI advice.
It never contains identities, report IDs, locations, coordinates, dates,
idempotency data, or claims. The strict `kern.llm.chat_complete` adapter uses a
named prompt, privacy routing, bounded JSON, and the distinct
`civic_report_rejection_drafting` cost label. Cached suggestions are immutable revision-bound drafting evidence, not
decisions. The active claim carries a reviewer ID only while work is pending;
the database removes that ID atomically when it stores a suggestion. Failure
always leaves manual wording available.

Owner list/detail models expose only `moderation_outcome` and the final rejection
explanation. They omit reviewer and screening evidence. A human may override any
AI verdict: approval means only eligibility for a later assignment/projection
slice, while rejection is final and read-only.

## Menschlich bestätigte Problemzuordnung — Iteration 11

Eine Projektionskandidatin ist ausschließlich eine eingereichte Meldung, deren
exakt aktuelle Revision menschlich freigegeben ist, weiterhin einem aktiven,
bestätigten Meldekonto gehört und noch keine aktuelle Problemzuordnung besitzt.
Die separate Grenze `/api/moderation/projektionen` verwendet dieselbe Berechtigung
wie die Moderation, ordnet Kandidatinnen oldest-first und behandelt unbekannte,
veraltete, abgelehnte, gelöschte und bereits zugeordnete IDs gleich undurchsichtig.
Ihre Detailprojektion enthält nur Beobachtungstexte und -daten sowie kontrollierte
Kategorie und räumlichen Bezug; Identität, privater genauer Ort, Koordinaten,
KI-/Moderations-/Claim-Evidenz und Providerdaten bleiben ausgeschlossen.

`ProjectionStore` ist die einzige Schreibgrenze zwischen den Domänen. Eine
Projektionsbestätigung bindet genau eine aktuelle freigegebene Meldungsrevision
an genau ein echtes `civic_problems`-Ziel. Sie verlangt die erwartete Revision
und eine eigene menschliche Bestätigung nach der Moderationsfreigabe. Das private
`civic_report_problem_assignments` bewahrt Meldungsrevision, Problem, historische
Prüf-ID und Zeitpunkt append-only auf. Die zugehörige Baseline erhält die bereits
öffentliche unabhängige Meldezahl und Beobachtungsspanne eines bestehenden
Problems. Datenbank-Views und Trigger prüfen aktuelle Freigabe, Melde- und
Prüfberechtigung, Zielzustand und Revision; exakte Retries liefern denselben
Nachweis, während abweichende oder konkurrierende Zuordnungen den ersten Gewinner
nicht ersetzen. Die dedizierte, atomare und wiederholbare
`civic_projection_schema_migrations` wird beim Start der freigeschalteten
Bürgerportal-Umgebung vorbereitet; neuere unbekannte Versionen brechen
geschlossen ab und bestehende öffentliche Zeilen bleiben unverändert.

Bestehende Ziele kommen nur aus den realen, bereits sichtbaren
`civic_problems`; Feature-Beispiele sind keine Ziele. Alternativ darf nur eine
stadtweite Kandidatin atomar eine neue stadtweite Projektion erzeugen. Deren
öffentlicher deutscher Titel und neutrale Zusammenfassung werden vom Menschen
eigenständig formuliert und bestätigt. Kategorie kommt aus der Meldung; Ort,
Koordinaten und Geometrie bleiben leer, Tags starten leer und der Status startet
als `new`. Beobachtungsdaten und Zahl werden aus gültiger Evidenz abgeleitet,
nie vom Client geliefert. Scheitert ein Teil, fehlen sowohl Projektion als auch
Zuordnung.

Die Zahl addiert zur unveränderten Baseline nur unterschiedliche weiterhin
berechtigte Meldekonten; mehrere Meldungen derselben Person zählen für dasselbe
Problem einmal. Neue Inhaltsrevisionen sowie Rollen-, Status- oder
Bestätigungsänderungen lassen alte Zuordnungen unverändert, entfernen ihre
Wirkung aber sofort aus Zahl und öffentlicher Sichtbarkeit. Die Löschung der
meldenden Person kaskadiert durch Meldung und Zuordnung. Ohne verbleibende
Evidenz ist eine neu erzeugte Projektion nicht mehr öffentlich. Die Löschung
eines Prüferkontos entfernt dessen Identität, erhält aber die historische
Ganzzahl in der unveränderlichen Zuordnung.

`ProblemStore` bleibt die einzige öffentliche Lesegrenze und serialisiert keine
Zuordnungs-, Melde-, Identitäts-, Moderations- oder KI-Daten. Owner-Listen und
-Details ergänzen nur bereits öffentlichen Problemtitel und ID. KI formuliert
keinen öffentlichen Text, wählt kein Ziel und löst keine Zuordnung aus. Es gibt
weiterhin keine automatische Clusterung, neue kartierte Projektion,
Benachrichtigung, Weitergabe an die Stadt, städtische Zuständigkeit oder
Statusänderung.

## Geografie

Erlaubte Bezüge sind Punkt, Einrichtung, Route, Gebiet und Stadtgebiet.
Öffentlich gelten:

- Punkt und Einrichtung: gültige Breite/Länge;
- Route: GeoJSON `LineString` mit mindestens zwei Positionen;
- Gebiet: GeoJSON `Polygon` oder `MultiPolygon` mit geschlossenen Ringen;
- Koordinaten: `[Längengrad, Breitengrad]`;
- Stadtgebiet: keine erfundene Geometrie.

Ungültige oder nicht ehrlich kartierbare Projektionen bleiben in der
Rangliste und werden auf der Karte ausgelassen. Die Vorschau
benennt diese Grenze, statt einen stadtweiten oder ersatzweisen Punkt zu erfinden.

## Öffentliche Übersichtsprojektion

`civic_problems` speichert ausschließlich die öffentliche Projektion. Der Store
liest explizite Spalten und filtert zwingend auf `published_at IS NOT NULL`,
mindestens eine unabhängige Meldung und einen ungelösten Status. Er sortiert
nach `independent_reports DESC`, bei Gleichstand nach Titel und ID. Damit ist
die Rangfolge deterministisch und enthält weder Zeitfenster noch versteckten
Score. Additive Migrationen stehen in
`civic_problem_schema_migrations`, laufen wiederholbar und erhalten eine ältere
Legacy-Projektion mit `unique_reporters`.

Die öffentliche Detailansicht ist keine zweite oder reichere Projektion. Sie
liest genau einen Eintrag durch dieselbe Filter- und Serialisierungsgrenze wie
die Übersicht. Dadurch kann ein Detail-Link weder unveröffentlichte oder gelöste
Einträge noch zusätzliche Spalten, Rohmeldungen oder Moderationsdaten sichtbar
machen. Eine öffentliche Zeitleiste entsteht erst, wenn eigenständige,
quellenbelegte Projektionsereignisse modelliert sind; Statuswerte und Zeitstempel
werden dafür nicht umgedeutet.

Die Tabelle `civic_problem_feature_examples` gehört allein zur isolierten
Feature-Vorschau. Sie ist von `civic_problems` getrennt, damit Beispiele auch
bestehende Veröffentlichungssperren für echte Projektionen nicht umgehen. Der
Seeder schreibt über `FeatureExampleStore` und akzeptiert ausschließlich den
exakten Pfad `app-feature/data/ratslotse.sqlite` sowie den nur im Feature-Deploy
gesetzten Schalter. Dev und Produktion brechen vor dem Öffnen einer Datenbank ab;
die Oberfläche wird zusätzlich nur mit `NEXT_PUBLIC_BUERGERPORTAL=1` gebaut.
