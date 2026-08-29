# App-Store-Review-Audit der nativen Ratslotse-App

Stand: 29. August 2026. Geprüft gegen die App Review Guidelines vom 8. Juni 2026, Apples Human Interface Guidelines und den aktuellen nativen Code.

## Ergebnis

Der Code erfüllt nach dem Audit die anwendbaren Regeln. Zwei zuvor verdeckte
Risiken wurden behoben: Öffentliche geteilte KI-Antworten besitzen jetzt einen
Meldeweg ohne Konto samt Admin-Löschung und Kontosperre; außerdem kennzeichnet
die native Anmeldung Ratslotse sichtbar als privates Bürgerprojekt und nicht als
Angebot der Stadt Oldenburg.

**Noch nicht freigabefähig ist der Store-Eintrag selbst.** Vor der Einreichung
müssen App-Store-Connect-Angaben, Production-Secrets und Nachweise auf echter
Hardware abgeschlossen werden. Diese Punkte lassen sich nicht aus dem
Repository heraus bestätigen.

## Pflichtprüfung

| Bereich | Status | Befund / Maßnahme |
|---|---|---|
| 2.1 Vollständigkeit | Vor Upload | Release-Archive auf echtem Gerät und mit Production-Backend testen; App-Review-Konto samt Zugang und Hinweisen in App Store Connect hinterlegen. |
| 2.3 Metadaten | Vor Upload | Screenshots müssen die tatsächlich eingereichte native Version und aktuelle Daten zeigen. Analyse, KI-Hinweis, öffentliche Shares und In-App-Kontolöschung korrekt beschreiben. Keine Preis-, Behörden- oder Funktionsbehauptung darf über die App hinausgehen. |
| 2.4 Hardware | Nachweis vor Upload | iPhone und iPad in allen unterstützten Orientierungen, Dynamic Type, Split View/Stage Manager, Offline-/schwaches-Netz-Verhalten und Speicherwarnung auf Release-Build testen. |
| 2.5 Software | Code erfüllt / Archiv prüfen | Nur öffentliche Apple-APIs; kein nachladbarer Code, keine globale ATS-Ausnahme und keine unnötigen Hintergrundmodi. Im signierten App-Store-Archiv `aps-environment=production`, Associated Domains und Sign in with Apple prüfen. |
| 3 Geschäft | Nicht anwendbar | Kostenlos, keine Käufe, Abos, Werbung, Spenden oder bezahlten digitalen Inhalte; daher kein StoreKit/IAP- oder Zahlungsfluss. |
| 4.1 / 5.2 Identität und Rechte | Code erfüllt / Unterlagen offen | Eigenständige Marke und UI. Native Login-/Welcome-Seiten nennen sichtbar: privates Bürgerprojekt, kein Angebot der Stadt. Store-Beschreibung beginnt ebenso. Rechte an Lotti, Logo, Schriften und sonstigen Assets vor Upload dokumentieren; Drittinhalte in App Store Connect ehrlich deklarieren. |
| 4.2 Mindestfunktionalität | Erfüllt | Keine WebView-Hülle: Fragen, Beschlüsse, Sitzungen, Karte, Analyse, Themen, Quiz, Konto und Admin sind nativ. Externe Links öffnen nur amtliche Quellen und Rechtstexte. |
| 4.8 Anmeldung | Erfüllt | Bei E-Mail/Passwort als Primärlogin ist Sign in with Apple zusätzlich nativ vorhanden. |
| 5.1.1 Datenschutz | Erfüllt | Datenschutzlink ist in Login/Konto/Mehr erreichbar; `PrivacyInfo.xcprivacy` deklariert E-Mail, Name, User-ID, Nutzerinhalte und Push-Gerätekennung ohne Tracking. |
| 5.1.1(v) Kontolöschung | Code erfüllt / Production konfigurieren | Löschung ist in der App möglich und verlangt frische Re-Authentifizierung. Für Apple-Konten übermittelt die App jetzt zusätzlich den frischen Authorization Code; das Backend tauscht ihn und widerruft das Apple-Token. Production benötigt `APPLE_TEAM_ID`, `APPLE_KEY_ID` und `APPLE_PRIVATE_KEY`. |
| 5.1.2 / KI-Transparenz | Erfüllt | Vor der ersten Frage erscheint einmalig der Hinweis zu OpenRouter, passenden Ratsauszügen, möglicher Drittlandverarbeitung, Fehlern und personenbezogenen Daten; die Datenschutzerklärung ist direkt verlinkt. Beide Auswahlknöpfe erlauben ausdrücklich die beschriebene Übermittlung und entscheiden getrennt davon nur über die Kontospeicherung. Bis zur Auswahl bleibt das Absenden in Web und iOS gesperrt. |
| 1.2 Nutzergenerierte Inhalte | Erfüllt / Betriebspflicht | Geteilte Antworten sind nicht gelistet und nicht durchsuchbar, aber ehrlich als UGC einzustufen. Ein enges Vorabfilter blockiert eindeutige Missbrauchsphrasen und eingebettete Web-/Script-Ziele. Empfänger*innen können ohne Konto nach Grund melden. Meldungen landen im Admin-Bereich; Admins können den öffentlichen Link löschen und über die interne Inhaber-ID missbrauchende Konten sperren. Kontaktweg ist veröffentlicht. Meldungen müssen im Betrieb zeitnah bearbeitet werden. |
| 1.1 Sicherheit / KI-Inhalte | Erfüllt | „Frag den Rat“ ist auf importierte Ratsdaten begrenzt, nennt Quellen und weist auf mögliche Fehler hin. Keine medizinische, finanzielle oder behördlich verbindliche Beratung; amtliche Originale bleiben maßgeblich. |
| Berechtigungen | Erfüllt | Kalenderzugriff wird erst bei „In Kalender“ angefragt und ist mit `NSCalendarsFullAccessUsageDescription` erklärt. Push wird erst nach dem eigenen Primer angefragt. Keine Standortberechtigung: die Karte zeigt Ratsdaten, nicht den Nutzerstandort. |
| Netzwerk | Erfüllt | Keine globale ATS-Ausnahme; API und Rechtstexte laufen über HTTPS. Datenschutz, Impressum, Hilfe und AASA antworteten beim Audit mit HTTP 200. |
| Admin-Schutz | Erfüllt | Native Admin-UI erscheint nur bei `role=admin`; jeder schreibende Endpunkt bleibt zusätzlich serverseitig durch die Admin-Abhängigkeit geschützt. |
| Barrierefreiheit | Nachweis vor Upload | Dynamic Type, VoiceOver, „Bewegung reduzieren“, Kontrast, Querformat und große Textgrößen auf einem echten Gerät durchgehen. Die Diagramme besitzen Beschriftung und eine alternative Wertetabelle. |
| iPad | Nachweis vor Upload | Split-Navigation und Zweispalten-Chat sind nativ. Vor Upload je ein vollständiger Smoke-Test auf iPad in Hoch-/Querformat und mit Stage Manager. |
| Kryptografie | Erfüllt | `ITSAppUsesNonExemptEncryption=false`; die App nutzt ausschließlich Betriebssystem-/HTTPS-Standardverschlüsselung. |
| 5.3–5.6 regulierte Dienste / Verhalten | Nicht anwendbar | Kein Glücksspiel, keine Finanz-, Krypto-, Gesundheits-, VPN- oder Dating-Funktion; keine Werbung, Manipulation von Reviews oder erzwungene Bewertungen. |

## Prüfung aller Guideline-Hauptbereiche

- **1 Sicherheit:** politische/amtliche Inhalte, KI-Hinweis, Quellen, Meldung
  und Moderation geprüft. Keine gefährlichen Handlungsanleitungen oder
  gesundheitsbezogenen Rechner.
- **2 Performance:** kein Platzhalter-/Demo-Code im Produktpfad gefunden.
  Release-Backend, Review-Konto, Absturzfreiheit und Metadaten bleiben reale
  Einreichungsprüfungen.
- **3 Business:** vollständig nicht anwendbar, solange Ratslotse kostenlos und
  ohne Kauf-, Abo-, Spenden- oder Werbefunktion bleibt.
- **4 Design:** native App statt Website-Wrapper, Systemnavigation,
  Sign in with Apple, Universal Links und iPad-Anpassung vorhanden.
- **5 Legal:** Datenschutzerklärung, Impressum, Account-Löschung,
  Auftragsverarbeiter, amtliche Quellen, Personen in öffentlicher Funktion und
  Unabhängigkeit sind offengelegt. Asset-Rechte und Store-Erklärungen brauchen
  einen externen Nachweis.

## App-Review-Notizen für App Store Connect

- Testkonto mit aktiven Beispielthemen, mindestens einem Gespräch, einer Sitzung und Analysewerten angeben.
- Kurz erklären: „Frag den Rat“ erzeugt KI-Text, jede Tatsachenbehauptung ist mit amtlichen Quellen verlinkt; maßgeblich bleibt das Original.
- Falls der Admin-Bereich geprüft werden soll, einen separaten Admin-Testaccount liefern. Keine Production-Zugangsdaten in Repository oder Review-Notizen einchecken.
- Push, Kalender, Sign in with Apple, Gesprächsspeicherung und Kontolöschung als prüfbare Schritte beschreiben.
- Production-Konfiguration vor Einreichung verifizieren: Apple-Revoke-Secrets, APNs-Production-Entitlement, `apple-app-site-association`, Datenschutz-/Support-URL und Backend-Migrationsstand.
- App-Privacy-Formular exakt wie `PrivacyInfo.xcprivacy` ausfüllen: E-Mail,
  Name, Nutzer-ID, Nutzerinhalte einschließlich Fragen/Shares und Push-Token;
  alles verknüpft, App-Funktionalität, kein Tracking.
- Altersfreigabe ehrlich mit **User Generated Content = ja** beantworten. Ein
  nicht gelisteter Share-Link bleibt öffentlicher Inhalt; „kein Feed“ macht ihn
  nicht zu privatem Inhalt.
- EU-DSA-Trader-Status abschließen und die operative Zuständigkeit für
  Share-Meldungen vor Release festlegen.

## Bewusst nicht enthalten

- Haushalt bleibt wie beschlossen außerhalb dieses Releases.
- Das Kommunalwahl-Dev-Feature wird nicht beworben oder in die App übernommen.
- Es gibt kein Tracking, keine Werbung und keine In-App-Käufe.

## Harte Freigabe-Checkliste

- [ ] App-Store-Connect Privacy Labels gespeichert und gegengelesen.
- [ ] Neuer Altersfreigabe-Fragebogen mit UGC = ja gespeichert; resultierende
      Altersfreigabe akzeptiert und Store-Texte angepasst.
- [ ] EU-DSA-Trader-Status abgeschlossen.
- [ ] Production: `APPLE_TEAM_ID`, `APPLE_KEY_ID`, `APPLE_PRIVATE_KEY`, APNs
      und Mailzustellung getestet.
- [ ] Signiertes Release-Archiv: Production Push, Associated Domains, Sign in
      with Apple, Privacy Manifest und Export-Compliance geprüft.
- [ ] Review-Konto mit realen, nicht vertraulichen Beispieldaten funktioniert.
- [ ] Jeder aktuelle iPhone-/iPad-Store-Screenshot stammt aus genau diesem
      Build und zeigt keine Testkonten oder erfundene Beschlüsse.
- [ ] Echter-Gerät-Matrix: iPhone/iPad, Hoch/Querformat, VoiceOver, großes
      Dynamic Type, Reduce Motion, Dark Mode, schwaches Netz und Offline.
- [ ] Support, Datenschutz, Impressum, AASA und amtliche Deep Links aus dem
      Production-Build erreichbar.
- [ ] Lotti/Logo/Schriften/3D-Assets und verwendete Drittinhalte rechtlich
      dokumentiert.
- [ ] Moderationspostfach wird überwacht; Testmeldung kann in Web und iOS
      entfernt werden, zugehöriges Konto kann gesperrt werden.
