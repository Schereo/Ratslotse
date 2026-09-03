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

## Veröffentlichung bleibt geschlossen

Eine reale Meldung darf erst in eine öffentliche Projektion einfließen, wenn
beides zur aktuellen Inhaltsrevision unveränderlich belegt ist:

1. eine eigenständige KI-Vorprüfung mit Urteil `suitable`;
2. eine abschließende menschliche Freigabe durch einen Ratslotse-Admin.

Fehlt ein Nachweis, ist er veraltet oder ist die Prüfung fehlgeschlagen, wird
nichts veröffentlicht. Iteration 1 führt bewusst keine reale Schreib- oder
Veröffentlichungs-API ein. `ProblemStore` ist eine reine Lesegrenze. Die
persistente Freigabelogik und privaten Tabellen folgen erst in einem eigenen,
getesteten Schnitt; bis dahin kann Anwendungscode keine reale Projektion
anlegen oder veröffentlichen.

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
