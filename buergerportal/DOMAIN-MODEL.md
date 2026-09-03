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
aktives, bestätigtes Konto darf private Inhalte anlegen oder verändern. Jede
private Lese- und Änderungsoperation verlangt die ID der meldenden Person.
Unbekannte und fremde Meldungs-IDs werden dabei nicht unterschieden und geben
keinen Inhalt preis.

Ein neuer Datensatz beginnt als `draft`. Beschreibung, kontrollierte Kategorie,
geografischer Bezug, privater genauer Ort und Beobachtungsdatum können nur in
diesem Zustand geändert werden. Stadtweite Entwürfe speichern keinen genauen
Ort; alle anderen Bezüge brauchen Ortsbezeichnung und Koordinaten innerhalb
einer konservativen Hülle Oldenburgs. Jede Inhaltsänderung erhöht die Revision.

`submit_owned_draft` ist ein atomarer, einmaliger Übergang zu `submitted`: Der
bestätigte Text und Absendezeitpunkt werden gesetzt und dieselbe Transaktion
hängt genau eine erste Beobachtung an. Danach bleibt der Entwurf unveränderlich.
Weitere Beobachtungen erhöhen die Inhaltsrevision und werden angehängt, nie
überschrieben; sie gehören weiterhin derselben Person und sind keine zusätzliche
unabhängige Meldung. Datenbank-Constraints und Trigger sichern Eigentümer-ID,
kontrollierte Kategorien und Geografie, Zeitwerte, Revisionsbindung und die
Unveränderlichkeit gespeicherter Beobachtungen zusätzlich zum Store ab.

Die privaten Migrationen werden einzeln atomar in
`civic_report_schema_migrations` protokolliert und sind wiederholbar. Sie legen
nur private Tabellen, Indizes und Trigger an und verändern weder
`civic_problems` noch `civic_problem_feature_examples`. Die explizite
Kontolöschgrenze `erase_reporter_data` entfernt alle privaten Meldungen und ihre
Beobachtungen einer Eigentümer-ID per Fremdschlüssel-Kaskade. Zusätzlich kennt
die zentrale Kontolöschung `civic_reports`, damit auch der bestehende
DSGVO-Löschweg keine privaten Daten zurücklässt. Beide Wege schreiben nicht in
öffentliche Projektionen.

## Veröffentlichung bleibt geschlossen

Eine reale Meldung darf erst in eine öffentliche Projektion einfließen, wenn
beides zur aktuellen Inhaltsrevision unveränderlich belegt ist:

1. eine eigenständige KI-Vorprüfung mit Urteil `suitable`;
2. eine abschließende menschliche Freigabe durch einen Ratslotse-Admin.

Fehlt ein Nachweis, ist er veraltet oder ist die Prüfung fehlgeschlagen, wird
nichts veröffentlicht. `ProblemStore` bleibt eine reine öffentliche Lesegrenze.
Iteration 4 persistiert zwar private Entwürfe und Beobachtungen, führt aber weder
HTTP-Zugriff noch KI-Prüfung, Moderation, Problemzuordnung oder
Veröffentlichungslogik ein. Anwendungscode kann weiterhin keine reale
öffentliche Projektion anlegen oder veröffentlichen.

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
