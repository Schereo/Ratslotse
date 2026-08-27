---
title: 0009 — Zentraler Ortskatalog statt vermeintlich amtlicher Stadtteile
description: Suche, Karten, Quiz und KI verwenden dieselben 31 dokumentierten Ratslotse-Ortsbereiche.
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

Ratslotse führt die neutrale Produktebene **Ortsbereich** ein:

- Der versionierte Katalog `council/oldenburg_places.json` ist die einzige
  Quelle für die 31 Gebiete, stabile IDs, Anzeigenamen, Schreibvarianten und
  Wahlbereichs-Zuordnungen.
- Grenzen bleiben ein separates, über den stabilen Namen verknüpftes
  GeoJSON-Asset. Sie stammen aus OpenStreetMap (`admin_level=10`, ODbL) und
  sind keine amtlichen Stadtteilgrenzen.
- Backend, Beschlusssuche, Themenkarte, Quiz und KI-Ortsextraktion lesen
  denselben Katalog. Das Frontend bekommt ihn über `/api/council/places`.
- Nutzeroberflächen nennen die kontrollierte Ebene „Ortsbereiche“. Freier Text
  darf weiterhin natürlich von einem Stadtteil oder Quartier sprechen.
- Historische DB-Felder und API-Schlüssel wie `stadtteil` bleiben vorerst als
  kompatible technische Namen bestehen; fachlich referenzieren sie immer einen
  kanonischen Ratslotse-Ortsbereich.
- Amtliche statistische Bezirke und Unterbezirke sind eine **separate
  Taxonomie**. Sie dürfen später über eigene IDs verknüpft, aber nicht still mit
  den Ratslotse-Ortsbereichen gleichgesetzt werden.

## Konsequenzen

- **Plus:** Bornhorst, Fliegerhorst und alle anderen Gebiete bedeuten in jeder
  Funktion dasselbe; Schreibvarianten landen auf derselben stabilen ID.
- **Plus:** Die Oberfläche macht die tatsächliche Genauigkeit transparent und
  behauptet keine nicht vorhandene amtliche Stadtteilgliederung.
- **Plus:** Eine spätere feinere Ebene (Quartier, statistischer Unterbezirk,
  Projektgebiet) kann mit eigener Art und Hierarchie ergänzt werden, ohne IDs
  oder gespeicherte Nutzerstände umzudeuten.
- **Minus:** Die 31 OSM-Grenzen bleiben eine redaktionelle Produktentscheidung.
  Änderungen brauchen Quellenprüfung, Review und gegebenenfalls eine Migration
  bestehender Ortszuordnungen.
