# Bürgerportal: Produktentscheidungen und Backlog

> Status: bestätigte Planungsgrundlage für die iterative Umsetzung im Ratslotse-Repository.
> Bei widersprüchlichen Annahmen ist dieses Dokument für das Bürgerportal die Quelle der Wahrheit.

## Ziel

Ratslotse erhält einen unabhängigen, kartenorientierten Problemtracker für kommunal beeinflussbare Themen in Oldenburg. Bürger*innen melden Beobachtungen privat. Ratslotse bündelt ähnliche Meldungen zu moderierten öffentlichen Problemen und macht dadurch Häufungen und zeitliche Entwicklungen sichtbar.

Das Portal ist kein Angebot der Stadt Oldenburg und zeigt ohne belegte Quelle keinen amtlichen Bearbeitungsstand an.

## Arbeitsbegriffe

- **Meldung:** privater Beitrag eines verifizierten Ratslotse-Kontos mit der eigenen Beobachtung.
- **Problem:** öffentlicher, moderierter Cluster aus einer oder mehreren Meldungen.
- **Beobachtung:** Erstmeldung oder spätere Aktualisierung derselben Person zum selben Problem.
- **Bürgeranliegen:** spätere Funktion; ein Vorschlag, den eine Fraktion oder ein Ratsmitglied übernehmen und zu einem formellen Antrag weiterentwickeln kann. Das Bürgeranliegen selbst ist kein Ratsantrag.

Die öffentliche Produktbezeichnung und die endgültigen UI-Begriffe sind noch festzulegen.

## Bestätigte Leitplanken

### Geltungsbereich

- Erfasst werden Themen, die die Stadt bereitstellt oder beeinflussen kann: unter anderem öffentlicher Raum, Mobilität, Schulen, Kindergärten, Krippen, Wohnen, Umwelt, Barrierefreiheit und Verwaltung.
- Personenbezogene Beschwerden, Vorwürfe gegen konkrete Personen, private Streitigkeiten, Notfälle und Straftaten gehören nicht in den Tracker.
- Notfälle und ungeeignete Anliegen werden an passende Anlaufstellen verwiesen.
- Der MVP startet stadtweit als Beta mit einer kontrollierten Oberkategorie-Struktur und `Sonstiges kommunales Thema`.

### Öffentlichkeit und Datenschutz

- Die Problemkarte und öffentliche Problemseiten sind ohne Anmeldung sichtbar.
- Nur angemeldete, per E-Mail verifizierte Ratslotse-Nutzer*innen können den Meldeassistenten verwenden oder Meldungen abgeben.
- Rohtexte, Identitäten, Moderationsnotizen und einzelne Meldungen bleiben privat.
- Öffentlich erscheinen nur moderierte Zusammenfassungen und aggregierte Metadaten.
- Externe KI erhält keine ungefilterten Rohmeldungen. Lokale Validierung und Entfernung personenbezogener Daten erfolgen zuerst; an einen freigegebenen No-Training-Anbieter gehen nur notwendige Inhalte.
- Nutzer*innen bestätigen den finalen deutschen Meldetext vor dem Absenden.

### Veröffentlichung und Moderation

- Eine Meldung wird zuerst automatisch auf Eignung und mögliche personenbezogene Inhalte geprüft.
- Das erste öffentliche Problem entsteht erst nach manueller Freigabe durch Ratslotse-Administrator*innen.
- KI darf Kategorie und Cluster vorschlagen. Menschen entscheiden über Veröffentlichung, Zusammenführung und sensible Änderungen.
- Reporter*innen erhalten Begründungscodes und eine kurze Moderationsnotiz und können einmal eine erneute Prüfung verlangen.
- Die private Moderationshistorie bleibt nachvollziehbar.
- Im MVP gibt es keine öffentlichen Kommentare.

### Karte und öffentliche Darstellung

- Die Karte ist der primäre Zugang; eine Listenansicht ergänzt sie.
- Ein Problem kann einen Punkt, eine Einrichtung, eine Route, ein Gebiet/Stadtteil oder das gesamte Stadtgebiet betreffen.
- Eine öffentliche Problemseite zeigt höchstens:
  - moderierten Titel und neutrale Zusammenfassung,
  - geografischen Bezug,
  - Kategorie und freigegebene Tags,
  - Anzahl eindeutiger Reporter*innen,
  - aktuelle und historische Beobachtungszahlen,
  - erste und letzte Beobachtung,
  - Vertrauen beziehungsweise Bestätigungsgrad,
  - belegbaren Status und öffentliche Zeitleiste.
- Rohtexte oder anonymisierte Zitate aus Meldungen werden nicht veröffentlicht.

### Datenqualität und Status

- Ein Konto hat pro Problem genau einen privaten Beitrag und kann diesen aktualisieren, aber keine neue Meldung zum selben Problem erzeugen.
- Wiederholte Aktualisierungen erhöhen nicht die Zahl eindeutiger Reporter*innen.
- `Reporter*innen`, `aktuelle Beobachtungen` und `Beobachtungen insgesamt` bleiben getrennte Kennzahlen.
- Eine Meldung kann zurückgezogen werden. Sie verlässt aktive Zählungen und KI-Eingaben; höchstens ein minimaler, nicht personenbezogener Audit-Eintrag bleibt bestehen, soweit erforderlich.
- Meldungen altern abhängig von der Kategorie. Probleme können veralten, erneut bestätigt, archiviert oder durch neue Beobachtungen wieder geöffnet werden.
- Statuswerte beschreiben nur belegbare Tatsachen, zum Beispiel `neu`, `mehrfach gemeldet`, `geprüft`, `weiterhin vorhanden` oder `offenbar behoben`.
- `In Bearbeitung durch die Stadt` darf nur mit einer überprüfbaren städtischen Quelle erscheinen.
- Externe Reaktionen erhalten Quellen und eindeutige Rollenlabels: `Stadtverwaltung`, `Ratsmitglied`, `Fraktion` oder `Ratslotse-Prüfung`. Eine politische Rückmeldung ist kein amtlicher Status.
- Eine einfache Zustimmung ist kein Bericht. Falls später eine Unterstützungsfunktion entsteht, bleibt deren Zahl getrennt von unabhängigen Meldungen.

### Meldeassistent

- Die Interaktion mit dem Assistenten darf in unterschiedlichen Sprachen stattfinden; der bestätigte Meldetext ist Deutsch.
- Der Ablauf ist hybrid:
  1. geografischen Bezug angeben,
  2. mögliche bestehende Probleme anzeigen,
  3. Problem in eigenen Worten beschreiben,
  4. Kategorie bestätigen,
  5. fehlende, kategorienabhängige Fakten durch wenige adaptive Fragen ergänzen,
  6. neutralen deutschen Entwurf und Cluster-Vorschlag prüfen,
  7. bewusst absenden.
- Jede Kategorie definiert prüfbare Mindestangaben. Typischer Kern: geografischer Bezug, Beobachtungsdatum oder Zeitraum, faktische Beschreibung und bestätigte Kategorie.
- KI verbessert Formulierungen und fragt fehlende Angaben ab, erfindet aber keine Tatsachen und ist nie alleinige Annahmeinstanz.
- Ähnliche Probleme werden sowohl früh nach der Ortswahl als auch semantisch nach Fertigstellung der Meldung vorgeschlagen.

### Benachrichtigungen

- Das private Dashboard zeigt die vollständige Zeitleiste der eigenen Meldung und des zugeordneten Problems.
- E-Mail oder Push werden nur für wesentliche Ereignisse verwendet: Moderationsergebnis, Rückfrage oder Bitte um erneute Bestätigung, Behebung/Wiederöffnung und Entscheidung über einen Einspruch.
- Kanäle verwenden das bestehende Ratslotse-Benachrichtigungssystem und bleiben konfigurierbar.

## MVP-Backlog

Die Reihenfolge beschreibt Produktpriorität. Jeder Block soll als testbarer vertikaler Schnitt geliefert werden.

### P0 — Begriff, Route und Datenmodell festlegen

- [ ] Produktname und sichtbare Begriffe festlegen; amtlich klingende Ticket-Versprechen vermeiden.
- [ ] URL-Routen und Navigation innerhalb der bestehenden Web-App festlegen.
- [ ] Domänenmodell für Meldung, Problem, Zuordnung, Aktualisierung, Moderationsentscheidung, Statusereignis und geografischen Bezug dokumentieren.
- [ ] Migrationen in der bestehenden Datenhaltung entwerfen; private Meldedaten und öffentliche Projektionen klar trennen.
- [ ] Autorisierungsmatrix für Öffentlichkeit, Reporter*in und Administrator*in definieren.

**Fertig, wenn:** Das Modell alle in diesem Dokument bestätigten Regeln ausdrücken kann, Daten anderer Nutzer*innen nicht über öffentliche oder fremde Konto-Endpunkte erreichbar sind und Migrationstests vorliegen.

### P1 — Öffentliche Problemkarte als dünner vertikaler Schnitt

Erster Review-Schnitt: `/probleme` zeigt in Vercel-Preview-Deployments deutlich
markierte, frei erfundene Beispieldaten; Produktion liest ausschließlich die
öffentliche FastAPI-Projektion. Die Beispieldaten werden entfernt, sobald das
Preview-Backend freigegebene Testprobleme bereitstellt.

- [x] Öffentliche API für freigegebene Probleme mit Karte, Filtern und Listenansicht bereitstellen.
- [ ] Punkt, Einrichtung, Route, Gebiet/Stadtteil und stadtweite Probleme darstellbar machen.
- [ ] Problem-Detailseite mit erlaubten Aggregaten und öffentlicher Zeitleiste bauen.
- [x] Kennzeichnung als unabhängiges Ratslotse-Angebot und Erklärung der Statusaussage sichtbar platzieren.
- [x] Leere, Lade-, Fehler- und mobile Zustände sowie Tastaturbedienung und Screenreader-Texte abdecken.

**Fertig, wenn:** Ein manuell angelegtes und freigegebenes Problem auf Karte und Liste auffindbar ist, seine Detailseite ausschließlich öffentliche Felder ausliefert und die Darstellung mobil sowie per Tastatur nutzbar ist.

### P2 — Privater geführter Meldeablauf

- [ ] Zugang auf verifizierte Konten begrenzen.
- [ ] Orts-/Bereichswahl und frühe Suche nach bestehenden Problemen umsetzen.
- [ ] Kontrollierte Oberkategorien plus `Sonstiges kommunales Thema` bereitstellen.
- [ ] Kategorienabhängige Mindestangaben und deterministische Validierung definieren.
- [ ] Adaptiven Assistenten für knappe, ausreichende Angaben und einen neutralen deutschen Entwurf umsetzen.
- [ ] Finalen Bestätigungsschritt mit verständlichem Datenschutzhinweis einbauen.
- [ ] Keine Foto-Uploads oder Anhänge anbieten.

**Fertig, wenn:** Eine verifizierte Person eine verwertbare Meldung mit wenigen Schritten als privaten Entwurf erstellen, prüfen und genau einmal absenden kann; fehlende Fakten werden erfragt und nicht erfunden.

### P3 — Datenschutz- und Eignungsprüfung

- [ ] Lokale Erkennung/Redaktion personenbezogener oder sensibler Inhalte vor jedem externen KI-Aufruf implementieren.
- [ ] Ungeeignete Fälle strukturiert erkennen und passende Hinweise für Notfälle, Straftaten, persönliche Vorwürfe und private Streitigkeiten zeigen.
- [ ] Datenminimierte KI-Payloads, Fehlerverhalten und Auditierbarkeit dokumentieren und testen.
- [ ] Aufbewahrungs-, Konto-Lösch- und Rückzugsregeln rechtlich und technisch festlegen.
- [ ] Rate Limits und Missbrauchsschutz für Assistent und Einreichung ergänzen.

**Fertig, wenn:** Tests belegen, dass typische personenbezogene Inhalte den externen Anbieter nicht erreichen, ungeeignete Anliegen sicher umgeleitet werden und ein Ausfall der KI weder Daten veröffentlicht noch Meldungen verliert.

### P4 — Moderationswarteschlange und Veröffentlichung

- [ ] Admin-Warteschlange mit Rohmeldung, bereinigtem Entwurf, KI-Hinweisen und Cluster-Vorschlägen bauen.
- [ ] Freigeben, ablehnen, Rückfragen, Kategorie/Geografie korrigieren und mit einem Problem zusammenführen ermöglichen.
- [ ] Begründungscodes, kurze Notiz und eine erneute Prüfung abbilden.
- [ ] Jede relevante Entscheidung privat auditieren.
- [ ] Erwartete Prüfzeit und einen sichtbaren Annahmestopp bei nicht betreubarer Warteschlange unterstützen.

**Fertig, wenn:** Keine neue Meldung ohne Admin-Entscheidung öffentlich wird, jede Entscheidung nachvollziehbar ist und Reporter*innen Ergebnis sowie zulässige nächste Schritte sehen.

### P5 — Clustering, Kennzahlen und Alterung

- [ ] Geografische und semantische Cluster-Vorschläge implementieren; finale Zusammenführung bleibt manuell.
- [ ] Eindeutige Reporter*innen, aktuelle Beobachtungen und Beobachtungen insgesamt separat berechnen.
- [ ] Aktualisierung desselben Beitrags ohne Erhöhung der Reporter*innenzahl erlauben.
- [ ] Kategorieabhängige Alterungsregeln, erneute Bestätigung, Archivierung und Wiederöffnung umsetzen.
- [ ] Rückzug aus aktiven Kennzahlen und Clustering-Eingaben umsetzen.
- [ ] Moderierte öffentliche Zusammenfassungen bei neuen Meldungen sicher aktualisieren.

**Fertig, wenn:** Tests Mehrfachmeldungen, Aktualisierungen, Rückzüge, Alterung, falsche Cluster-Vorschläge und Wiederöffnung abdecken und öffentliche Zählungen reproduzierbar bleiben.

### P6 — Privates Dashboard und Benachrichtigungen

- [ ] Eigene Meldungen mit Moderations- und Problemstatus anzeigen.
- [ ] Private Zeitleiste für Freigabe, Ablehnung, Zusammenführung, Rückfragen, Einspruch, Alterung, Behebung und Wiederöffnung bauen.
- [ ] Beitrag aktualisieren und zurückziehen ermöglichen.
- [ ] Einen strukturierten Einspruch pro Moderationsentscheidung ermöglichen.
- [ ] Bedeutende Ereignisse über bestehende konfigurierbare E-Mail-/Push-Kanäle versenden.

**Fertig, wenn:** Eine Person den vollständigen Stand ihrer Meldung versteht, erlaubte Aktionen selbst ausführen kann und keine Informationen über fremde Meldungen erhält.

### P7 — Beta-Betrieb absichern

- [ ] Moderationsvolumen, Bearbeitungsdauer, Ablehnungsgründe, Cluster-Korrekturen und Rückzüge datensparsam messen.
- [ ] Barrierefreiheit, mobile Nutzung und verständliche Sprache prüfen.
- [ ] Backup, Wiederherstellung und Löschung der neuen Daten testen.
- [ ] Betreiber-, Datenschutz-, Nutzungs- und Community-Daten-Hinweise veröffentlichen.
- [ ] Feedbackkanal ohne öffentliche Kommentare bereitstellen.

**Fertig, wenn:** Der Betrieb die Warteschlange zuverlässig betreuen, Datenschutzanfragen erfüllen, Daten wiederherstellen und anhand definierter Beta-Kennzahlen über die nächste Iteration entscheiden kann.

## Ausdrücklich nicht im MVP

- Foto- oder Datei-Uploads.
- Öffentliche Kommentare und Diskussionen.
- Automatische Veröffentlichung ohne Admin-Freigabe.
- Amtliche Bearbeitungsstände ohne überprüfbare Quelle.
- Zertifizierte Vor-Ort-Verifikation.
- Offener Datenexport oder öffentliche Schreib-API.
- Eigene Zugänge für Ratsmitglieder oder Fraktionen.
- Versand von Bürgeranliegen per E-Mail.
- Bürgeranliegen-Assistent und Überführung in politische Anträge.

## Spätere Phasen

### Zertifizierte Verifikation und Fotos

- Verifizierer*innen werden manuell ausgewählt; eine automatische Reputation reicht nicht.
- Einsätze finden nur an öffentlichen Orten statt, ohne Konfrontation, Personenbezug oder Notfalleinsatz.
- Ein Auftrag kann nach einer kategorienabhängigen Meldeschwelle entstehen.
- Erst dann können geschulte Personen nicht sensible Fotos aufnehmen.
- Vor Veröffentlichung: Metadaten entfernen, sensible Inhalte prüfen, Gesichter/Kennzeichen unkenntlich machen und Freigabe dokumentieren.

### Offene aggregierte Daten

- Versionierte, nur lesbare API und Downloads für öffentliche Problemcluster.
- ODbL 1.0 für die veröffentlichte aggregierte Datenbank; Software bleibt AGPL-lizenziert.
- Private Meldungen, Kennungen, genaue Einreichungszeiten und Moderationsnotizen bleiben ausgeschlossen.
- Provenienz, Rate Limits und ausdrückliche Zustimmung zu Beitragsbedingungen vor Veröffentlichung klären.

### Bürgeranliegen und politische Übergabe

- Eigenständiges Bürgeranliegen oder Ableitung aus einem oder mehreren öffentlichen Problemen.
- Originalvorschlag und verwendete Problemstatistik bleiben nachvollziehbar.
- Zunächst Versand per E-Mail; später getrennte, verifizierte Zugänge für Ratsmitglieder und Fraktionen.
- Status unterscheidet `von Ratslotse versandt`, `Rückmeldung erhalten`, `von Fraktion aufgegriffen` und einen verlinkten formellen Ratsantrag.
- Bürgeranliegen, Fraktionsentwurf und formeller Antrag bleiben getrennte Objekte.
- Antworten von Ratsmitglied, Fraktion und Verwaltung werden eindeutig gekennzeichnet.

## Offene Entscheidungen vor der jeweiligen Umsetzung

Diese Punkte sind bewusst nicht geraten und blockieren nur den betroffenen Backlog-Block:

- Produktname, UI-Begriffe und Routen.
- Erste Oberkategorien, Mindestangaben und Alterungsintervalle je Kategorie.
- Geodaten-Repräsentation für Route und Fläche sowie Umgang mit sensiblen Orten.
- Konkrete lokale PII-Prüfung, freigegebener KI-Anbieter, Löschfristen und rechtliche Prüfung.
- Moderations-SLA, Ablehnungsgründe und Beta-Kapazitätsgrenze.
- Schwellen und Auswahlverfahren für spätere Vor-Ort-Verifikation.
- Umfang der ODbL-Beitragsbedingungen und des späteren Open-Data-Schemas.
- Empfängerwahl, Neutralitätsregeln und Einwilligungen für den späteren E-Mail-Versand von Bürgeranliegen.

## Änderungsregel

Neue Erkenntnisse ändern die relevante Entscheidung an einer Stelle in diesem Dokument. Abgelöste Regeln werden ersetzt statt als widersprüchliche Ergänzung stehen gelassen. Umsetzungs-PRs markieren erledigte Punkte und ergänzen nur Entscheidungen, die tatsächlich bestätigt oder durch Tests belegt wurden.
