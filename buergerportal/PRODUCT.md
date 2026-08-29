# Produktbegriffe und Routen des Bürgerportals

Dieses Dokument hält den bestätigten öffentlichen Sprach- und Routenvertrag fest. Die Domänenbegriffe stehen in [`CONTEXT.md`](CONTEXT.md).

## Sichtbare Bezeichnung

Der Bereich heißt **Probleme in Oldenburg**. In knappen Navigationselementen steht **Probleme**; **Problemkarte** bezeichnet nur die Kartenansicht innerhalb des Bereichs.

Die sichtbare Bereichsbezeichnung ist in der Frontend-Konfiguration zentralisiert und darf später ohne Änderung der Domänenbegriffe, Datenbank oder URLs umbenannt werden.

Verwendete Begriffe:

- **Problem** für einen moderierten öffentlichen Cluster,
- **Meldung** für den privaten Beitrag einer Person,
- **Beobachtung** für die Erstmeldung oder eine spätere Aktualisierung,
- **Ratslotse-Prüfung** für eine klar als unabhängig gekennzeichnete Einordnung.

Nicht verwendet werden amtlich klingende Begriffe wie **Mängelmelder**, **Ticket**, **Fallnummer** oder ein unbelegter **Bearbeitungsstand**.

## Stabiler Routenvertrag

| Route | Sichtbarkeit | Zweck | Status |
|---|---|---|---|
| `/probleme` | öffentlich | Karte und Status-Board | umgesetzt |
| `/probleme/[id]` | öffentlich | freigegebene Details und öffentliche Zeitleiste | umgesetzt |
| `/probleme/melden` | verifiziertes Konto | geführter Meldeablauf | für P2 reserviert |
| `/meine-meldungen` | verifiziertes Konto | eigene Meldungen und private Zeitleiste | für P6 reserviert |
| `/admin/meldungen` | Admin | Moderationswarteschlange | für P4 reserviert |

Geteilte Links auf `/probleme/[id]` bleiben ohne Anmeldung lesbar. Die Hauptnavigation führt unter **Probleme** zur Übersicht; Detailseiten bieten einen Rückweg zur Problemkarte. Spätere Umbenennungen der sichtbaren Bezeichnung ändern diese URLs nicht.
