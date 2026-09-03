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
| KI-Urteil und Begründung | grobes Häufigkeitsband |
| Moderationsnotiz | belegbarer Status |

Die Listenprojektion in Iteration 1 enthält absichtlich weder Zusammenfassung
noch exakte Zahl unabhängiger Meldungen. Sie liefert nur das daraus abgeleitete
Band `once`, `several`, `many` oder `very_many`. Es bedeutet Häufigkeit, nie
Dringlichkeit.

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

Ungültige oder nicht ehrlich kartierbare Projektionen bleiben im vollständigen
Status-Board und werden auf der Karte ausgelassen.

## Iteration-1-Schema

`civic_problems` speichert ausschließlich die öffentliche Projektion. Der Store
liest explizite Spalten und filtert zwingend auf `published_at IS NOT NULL` und
mindestens eine unabhängige Meldung. Additive Migrationen stehen in
`civic_problem_schema_migrations`, laufen wiederholbar und erhalten eine ältere
Legacy-Projektion mit `unique_reporters`.

Die Spalten `example_key` und `is_fictional` gehören allein zur isolierten
Feature-Vorschau. Der Seeder akzeptiert ausschließlich den exakten Pfad
`app-feature/data/ratslotse.sqlite` und zusätzlich einen nur im Feature-Deploy
gesetzten Schalter. Dev und Produktion brechen vor dem Öffnen einer Datenbank ab.
