# Beschlussradar-Backlog

Arbeitsstand und nächste Schritte für das dev-gatete Beschlussradar. Dieses Dokument ist die Arbeitsliste für Agenten und Menschen, bis die Punkte in GitHub-Issues überführt sind.

## Zielbild

Das Beschlussradar zeigt Vorlagen/Beschlüsse als ruhiges Kanban: Was ist geplant, was ist in Beratung, was ist offiziell entschieden? Es bleibt quellentreu und behauptet keinen Umsetzungsstand, solange dafür keine belastbaren Belege modelliert sind.

## Aktueller Stand

Draft-PR: https://github.com/Schereo/Ratslotse/pull/810

V1 ist implementiert als dev-gatete Vorschau:

- Backend-Endpunkt `GET /api/council/beschlussradar`
- Store-Abfrage auf Vorlage-Ebene
- Kanban-Spalten `Geplant`, `In Beratung`, `Entschieden`
- Zeitraum: letzte 90 Tage plus zukünftige Beratungen
- Frontend-Seite `/beschlussradar`
- Navigation in Desktop-Sidebar, mobilem Mehr-Sheet und Command-Palette
- Tests und Build lokal grün; GitHub-CI für PR #810 grün vor der Navigationsergänzung

## Arbeitsregeln

- Neue Feature-Arbeit basiert auf `upstream/dev` und läuft über Branches `agent/<kurzer-slug>`.
- PRs gehen gegen `Schereo/Ratslotse:dev`.
- Das Feature bleibt bis zur Produktfreigabe hinter `NEXT_PUBLIC_RATSLOTSE_ENV === "dev"`.
- Offizielle Beratungs-/Beschlussstände und reale Umsetzung werden getrennt modelliert.
- Keine Karte darf Umsetzung, Wirkung oder Vollständigkeit behaupten, wenn nur Ratsinfo-Daten vorliegen.

## Backlog

### Jetzt: PR #810 prüfen und abrunden

- [ ] Menschliche UI-Prüfung: Sind Spalten, Karten und Begriffe verständlich?
- [ ] Prüfen, ob Navigation an der gewünschten Stelle sitzt.
- [ ] Kleine Text-/Layout-Politur nur bei konkretem Review-Feedback.
- [ ] Wenn freigegeben: Draft-PR #810 auf Ready for Review setzen.

Akzeptanz: Die Vorschau ist erreichbar, erklärt ihren Datenstand klar und bleibt bewusst ohne Umsetzungsversprechen.

### Nächster PR: Board-Nutzbarkeit

- [ ] Filter nach Ausschuss/Gremium.
- [ ] Filter nach Zeitraum.
- [ ] Textsuche über Titel/Vorlagennummer.
- [ ] Sortierung je Spalte: neueste Aktivität, nächste Beratung, letzte Entscheidung.
- [ ] URL-Parameter für Filterzustand, damit Ansichten teilbar sind.

Akzeptanz: Nutzer können eine konkrete Vorlage schneller wiederfinden, ohne die Quellentreue des Boards zu verlieren.

### Danach: Kartentiefe und Verlauf

- [ ] Karten zeigen klarer: nächste Beratung, letzte Beratung, finales Ergebnis.
- [ ] Detail-Drawer oder Detailseite für eine Vorlage.
- [ ] Beratungsfolge als Timeline mit Gremium, Datum, TOP und Ergebnis.
- [ ] Offizielle Links/Quellen deutlicher bündeln.
- [ ] Datenlücken explizit markieren: keine Quelle, keine finale Entscheidung, fehlendes Datum.

Akzeptanz: Eine Karte beantwortet „wo steht diese Vorlage gerade?“ und die Detailansicht zeigt, worauf diese Antwort beruht.

### Später: Integration ins Produkt

- [ ] Merken/Folgen direkt aus dem Beschlussradar.
- [ ] Benachrichtigung bei neuer Beratung oder nachgetragener Entscheidung.
- [ ] Verknüpfung mit Stadtkarte/Themen.
- [ ] Dashboard-Widget für neue, bewegte oder entschiedene Vorlagen.
- [ ] Leichte Einführung/Leerzustand für Nutzer, die den Begriff Beschlussradar nicht kennen.

Akzeptanz: Das Radar wird nicht nur eine Übersicht, sondern ein Einstieg in bestehende Ratslotse-Flows.

### Separater Strang: Umsetzungstracking

Nicht in PR #810 und nicht mit offiziellen Ratsinfo-Ständen vermischen.

Offene Modellierungsfragen:

- Was ist eine umgesetzte Maßnahme: Beschluss, Teilmaßnahme, Haushaltsposition, Bauprojekt, Verwaltungshandeln?
- Welche Quellen zählen als Beleg: Pressemitteilung, Ratsvorlage, Haushaltsdaten, Baustellenmeldung, externe Quelle?
- Welche Zustände sind ehrlich genug: ungeklärt, geplant, begonnen, umgesetzt, aufgegeben, widersprüchlich?
- Wie werden mehrere Teilmaßnahmen mit unterschiedlichem Stand abgebildet?

Mögliche erste Umsetzung:

- [ ] Domain-Modell für `Umsetzungshinweis`/`Maßnahme` entwerfen.
- [ ] Belegpflicht definieren: jede Umsetzungsaussage braucht Quelle und Datum.
- [ ] Kleine manuell kuratierte Testmenge anlegen.
- [ ] UI nur als separaten Bereich „Umsetzungshinweise“, nicht als vierte Kanban-Spalte.

Akzeptanz: Nutzer sehen klar den Unterschied zwischen „politisch entschieden“ und „in der Stadt wirklich passiert“.

## Wiederaufnahme-Checkliste für Agenten

1. Diesen Backlog lesen.
2. Aktuelle PRs gegen `Schereo/Ratslotse:dev` prüfen.
3. `upstream/dev` holen und neuen `agent/*`-Branch verwenden.
4. Vor UI-Arbeit `web/frontend/DESIGNSPRACHE.md` lesen.
5. Vor PR-Erstellung Tests passend zum Änderungstyp ausführen und eine separate Pi-Review machen.
