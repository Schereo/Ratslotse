# Bürgerportal: bestätigte Reihenfolge

Quelle für die aktuelle Migration ist Parent-Issue #1033. Jeder Punkt wird als
eigener vertikaler Schnitt von aktuellem `feature` umgesetzt, auf
`feature.ratslotse.de` geprüft und ausdrücklich abgenommen. Vor dieser Abnahme
beginnt kein späterer Punkt.

## Verbindliche Leitplanken

- Öffentliche Problemprojektion und private Meldungen bleiben getrennte Domänen.
- Rohtexte, Identitäten, Moderationsnotizen und genaue private Orte bleiben privat.
- Reale Veröffentlichung braucht aktuelle geeignete KI-Vorprüfung und
  unveränderliche menschliche Freigabe; Fehler bleiben geschlossen.
- Häufigkeitsfarben bedeuten nie Dringlichkeit.
- Stadtweite oder ungültige Geometrien erhalten keinen erfundenen Kartenpunkt.
- Ratslotse ist kein amtliches System der Stadt Oldenburg.

## Iterationen

1. **Öffentliche Problemübersicht (#1034): umgesetzt.** Rein lesende
   API-Projektion, Karte, Themenfilter, alle ehrlichen Geometrieformen, sichere
   Feature-Beispiele, Navigation, Sitemap und öffentlicher Vertrag.
2. **Rangliste (#1042): auf `feature` umgesetzt und abgenommen.** Nur ungelöste
   Projektionen, exakte lebenszeitliche Zahl unabhängiger Meldungen,
   deterministische Rangfolge, vergleichbare Balkenschienen, zugängliche
   Vorschauen und ehrlicher Kartenfokus.
3. **Öffentliche Detailseite (#1058): auf `feature` umgesetzt und abgenommen.**
   Sichere Einzelprojektion, kanonische Web-Route, Query-Adapter im statischen
   Export, Teilen, Lotti-Hilfe und ehrliche Detailkarte.
4. **Private Meldungs-Domäne und sichere Persistenz (#1071): auf `feature`
   umgesetzt und abgenommen.** Eigentümergebundene Entwürfe, einmaliges
   atomisches Absenden, append-only Beobachtungen, versionierte Migrationen und
   Kontolöschgrenze.
5. **Eigentümergebundene Entwurfs- und Einreichungs-API (#1075): auf `feature`
   umgesetzt und abgenommen.** Nur aktive, bestätigte Nicht-Admin-Konten;
   konto-sichere Idempotenz beim Anlegen, erwartete Inhaltsrevisionen beim Ändern
   und retry-sicheres einmaliges Absenden.
6. **Geführter Meldechat und prominenter Einstieg (#1086): auf `feature`
   umgesetzt und abgenommen.** Deterministische Fragen, privater genauer
   Kartenort, sitzungsgebundene Wiederaufnahme, korrigierbare Prüfung und
   revisionssicheres Absenden über die bestehende API — ohne KI oder
   öffentlichen Problemabgleich.
7. **Lokale Weitergabeprüfung vor externer KI (#1102): umgesetzt auf diesem
   Task-Branch.** Revisionsgebundene, unveränderliche Sperre mit kontrollierten
   Gründen; private Einreichungen bleiben erhalten, externe Verarbeitung und
   öffentliche Projektionen bleiben geschlossen.
8. Moderation, Clustering, privates Dashboard und Beta-Betrieb — in weitere,
   einzeln abgenommene Schnitte zu zerlegen.

## Noch nicht Teil des Bürgerportal-Stands

Weiterhin nicht enthalten sind eine API für spätere Beobachtungen, externe
KI-Aufrufe, Moderationsoberfläche, Clusterung, automatische Veröffentlichung,
Uploads, private Meldungsübersicht oder öffentliche Kommentare. Iteration 7 ist erst
nach ausdrücklicher Abnahme der deployten lokalen Weitergabeprüfung
abgeschlossen.
