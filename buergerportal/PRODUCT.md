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

Nicht verwendet werden **Reporter*in** oder amtlich klingende Begriffe wie **Mängelmelder**, **Ticket**, **Fallnummer** und ein unbelegter **Bearbeitungsstand**. Öffentlich steht nur die knappe Zahl **unabhängige Meldungen**.

## Darstellungsprinzip

Karte, Farbe, Symbole und kurze Zahlenhinweise tragen die Oberfläche. Text bleibt so knapp wie möglich. Exakte Meldezahlen erscheinen erst am ausgewählten Problem als zum Beispiel **6 unabhängige Meldungen**; Beobachtungs-Unterzahlen werden nicht zusätzlich gezeigt.

## Kartenzeichen

Die Karte unterscheidet räumliche Bezüge ohne Erklärungstext: Punkte sind Kreise, Einrichtungen abgerundete Gebäudemarker, Routen kräftige Linien und Gebiete transparente Flächen. Stadtweite oder nicht verortbare Probleme erscheinen nur im Status-Board, nicht als künstliches Zeichen auf der Karte. Direkt erreichbare Themenchips filtern die Karte. Die öffentliche Problemseite wiederholt den räumlichen Bezug als Karte, wenn das Problem ehrlich verortbar ist. Grau, Blau, Orange und Rot zeigen ausschließlich die grobe Meldehäufigkeit – nie Dringlichkeit.

## Freigabefolge

Eine abgesendete Meldung bleibt privat. Zuerst hält eine eigenständige KI-Vorprüfung ihr Urteil privat fest. Danach entscheidet ein Mensch abschließend. Nur Meldungen mit geeignetem KI-Urteil **und** menschlicher Freigabe dürfen in die öffentliche Ratslotse-Projektion einfließen. Ein Ausfall oder fehlendes Urteil veröffentlicht nichts. Diese Projektion ist keine offizielle Datenbank der Stadt Oldenburg.

## Stabiler Routenvertrag

| Route | Sichtbarkeit | Zweck | Status |
|---|---|---|---|
| `/probleme` | öffentlich | Karte und Status-Board | umgesetzt |
| `/probleme/[id]` | öffentlich | freigegebene Details und öffentliche Zeitleiste | umgesetzt |
| `/probleme/melden` | verifiziertes Konto | geführter Meldeablauf | für P2 reserviert |
| `/meine-meldungen` | verifiziertes Konto | eigene Meldungen und private Zeitleiste | für P6 reserviert |
| `/admin/meldungen` | Admin | Moderationswarteschlange | für P4 reserviert |

Geteilte Links auf `/probleme/[id]` bleiben ohne Anmeldung lesbar. Die statisch exportierte Mobil-App bildet diesen Web-Pfad intern auf die bestehende Query-Ansicht `/probleme?problem=[id]` ab. Die Hauptnavigation führt unter **Probleme** zur Übersicht; Detailseiten bieten einen Rückweg zur Problemkarte. Spätere Umbenennungen der sichtbaren Bezeichnung ändern die öffentlichen URLs nicht.
