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
bounded older-page states. Its only states are `Entwurf` and
`Privat eingegangen`; it does not infer moderation or City processing.

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

## Veröffentlichung bleibt geschlossen

Eine reale Meldung darf erst in eine öffentliche Projektion einfließen, wenn
beides zur aktuellen Inhaltsrevision unveränderlich belegt ist:

1. eine eigenständige KI-Vorprüfung mit Urteil `suitable`;
2. eine abschließende menschliche Freigabe durch einen Ratslotse-Admin.

Fehlt ein Nachweis, ist er veraltet oder ist die Prüfung fehlgeschlagen, wird
nichts veröffentlicht. `ProblemStore` bleibt eine reine öffentliche Lesegrenze.
Iterations 4–9 persist and expose owner-bound private reports and add only the
revision-bound private external pre-screening. They add no human moderation
decision, problem assignment, or publication path. Application code still
cannot create or publish a real public projection from a private report.

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
