---
title: 0009 — Zentraler, hierarchischer Ortskatalog
description: Suche, Karten, Quiz und KI verwenden dieselben Ortsbereiche, Quartiere und besonderen Gebiete.
sidebar:
  order: 9
---

**Status:** Akzeptiert

## Kontext

Oldenburg besitzt unterhalb der Gesamtstadt **keine offiziell festgelegten
Stadtteile**. Die Stadt führt stattdessen neun statistische Bezirke sowie
Siedlungsbereiche, Unterbezirke und Blockgruppen. Diese Ebenen sind laut
[Stadtteil- und Quartierskonzept der Stadt Oldenburg](https://www.oldenburg.de/fileadmin/oldenburg/Benutzer/Dateien/50_Amt_fuer_Teilhabe_und_Soziales/Quartier/Oldenburg_Stadtteil_Quartierskonzept_Entwurf_b.pdf)
in der Stadtgesellschaft nur teilweise gebräuchlich.
Das aktuelle [Statistische Jahrbuch](https://www.oldenburg.de/startseite/rathaus/politik-verwaltung/stadtverwaltung/statistik/statistisches-jahrbuch.html)
führt diese amtliche Feingliederung fort.

Ratslotse verwendete bereits 31 flächendeckende OSM-Gebiete. Namen und
Wahlbereichs-Zuordnungen standen jedoch zusätzlich als getrennte Konstanten in
Python und TypeScript. Suche, Themenkarte, Quiz und KI-Ortsextraktion konnten
dadurch fachlich und technisch auseinanderlaufen. Außerdem klang „amtliche
Stadtteile“ genauer, als die Datengrundlage tatsächlich ist.

## Entscheidung

Ratslotse bildet zwei Ebenen ab und verknüpft sie über stabile IDs.

- Der versionierte Basiskatalog `council/oldenburg_places.json` enthält die 31
  flächendeckenden Ortsbereiche und die recherchierten Startdaten.
  Die redaktionell gepflegte Tabelle `council_place_reviews` erweitert den
  Katalog um geprüfte Kandidaten. Rohbeobachtungen und versionierte Dateien
  bleiben dabei im laufenden Betrieb erhalten. Beide Schichten bilden gemeinsam den Laufzeitkatalog.
- Die 31 flächendeckenden **Ortsbereiche** bleiben die primäre Produktebene.
  Zusätzlich darf der Katalog kuratierte, nicht flächendeckende Ortsobjekte wie
  Quartiere, Wohn- und Sanierungsgebiete, Parks, Schutz- oder
  Entwicklungsgebiete enthalten. Sie verweisen über `parent_ids` auf einen
  oder mehrere Ortsbereiche, sofern die Zuordnung fachlich sicher ist.
- Roh erkannte Straßen, Gebäude und Gebietsbezeichnungen in Beschlüssen sind
  zunächst **Beobachtungen**. Häufigkeit allein macht sie nicht zum Katalogort.
  In den Katalog aufgenommen werden nur wiederkehrende, politisch nützliche und
  anhand belastbarer Quellen eindeutig benennbare Orte.
- Der Admin-Bereich zeigt Kandidaten mit Beschlusszahl, Koordinaten und
  Stichproben der Fundstellen. Bei der Prüfung lässt sich ein Kandidat
  als eigener Ort oder als Alias eines vorhandenen Orts freigeben oder
  verwerfen. Die Entscheidung kann rückgängig gemacht werden. Neue Importe
  verwenden freigegebene Namen und Aliase sofort.
- Grenzen bleiben ein separates, über den stabilen Namen verknüpftes
  GeoJSON-Asset. Sie stammen aus OpenStreetMap (`admin_level=10`, ODbL) und
  sind keine amtlichen Stadtteilgrenzen.
- Backend, Beschlusssuche, Themenkarte, Quiz und KI-Ortsextraktion lesen
  denselben Katalog. Das Frontend bekommt ihn über `/api/council/places`;
  einzelne Orte besitzen ein Profil unter `/api/council/place/{id}`.
- Die Stadtkarte ergänzt Themen um konkrete Beschlussorte innerhalb Oldenburgs.
  Straßen, Plätze, Gebäude und Gewässer werden ab drei verschiedenen
  Beschlüssen automatisch gezeigt. Unscharfe Gebietsbegriffe erscheinen erst
  nach redaktioneller Freigabe; verworfene Kandidaten nie. Bei gleichem Namen
  ersetzt der präzisere Beschlussort den alten Themenpunkt. Ein Klick öffnet
  das Ortsprofil oder eine exakt auf diesen Rohort gefilterte Beschlussliste.
- Neue Beschluss-Orte speichern neben dem Rohbeleg eine exakte `place_id` und,
  soweit bekannt, die übergeordnete `ortsbereich_id`. Ein einmaliger Backfill
  ergänzt diese IDs in bestehenden Ortslinks. Aliase bleiben Eingabeformen;
  gespeichert und angezeigt wird der kanonische Name.
- Nutzeroberflächen unterscheiden den jeweiligen Typ („Ortsbereich“,
  „Quartier“, „Park“ …). Freier Text darf weiterhin natürlich von einem
  Stadtteil sprechen.
- Historische Datenbankfelder und API-Schlüssel wie `stadtteil` bleiben
  vorerst aus Kompatibilitätsgründen bestehen. Sie verweisen stets auf
  einen kanonischen Ortsbereich von Ratslotse. Neue Logik verwendet die stabilen IDs.
- Amtliche statistische Bezirke und Unterbezirke sind eine **separate
  Taxonomie**. Sie dürfen später über eigene IDs verknüpft, aber nicht still mit
  den Ratslotse-Ortsbereichen gleichgesetzt werden.

## Konsequenzen

- **Plus:** Alle Funktionen verwenden dieselbe Definition für Bornhorst,
  Fliegerhorst und die übrigen Gebiete. Schreibvarianten verweisen auf
  dieselbe stabile ID.
- **Plus:** Die Oberfläche macht die tatsächliche Genauigkeit transparent und
  behauptet keine nicht vorhandene amtliche Stadtteilgliederung.
- **Plus:** Eine spätere feinere Ebene (Quartier, statistischer Unterbezirk,
  Projektgebiet) kann mit eigener Art und Hierarchie ergänzt werden, ohne IDs
  oder gespeicherte Nutzerstände umzudeuten.
- **Plus:** Die Beschlusssuche kann auf einen Ort oder dessen übergeordneten
  Ortsbereich filtern. Die KI-Frage begrenzt ihr Retrieval bei expliziten
  Ortsfragen auf genau diese belegten Beschlüsse. Das Quiz verwendet dieselben
  Namen und Stammdaten.
- **Plus:** Zu jedem kuratierten Ort sind Definition und Quelle prüfbar; aus
  Beschlüssen extrahierte Fundstellen bleiben als separate Belege sichtbar.
- **Minus:** Die 31 OSM-Grenzen bleiben eine redaktionelle Produktentscheidung.
  Änderungen brauchen Quellenprüfung, Review und gegebenenfalls eine Migration
  bestehender Ortszuordnungen.
- **Minus:** Manche kleinräumigen Orte lassen sich erst nach einer
  Prüfung in den Katalog aufnehmen. Mehrdeutige Kandidaten bleiben
  Rohbeobachtungen, bis Geometrie, Einordnung und Quelle geklärt sind.
