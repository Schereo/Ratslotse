# App-Store-Review-Audit der nativen Ratslotse-App

Stand: 29. August 2026. Geprüft gegen die App Review Guidelines vom 8. Juni 2026, Apples Human Interface Guidelines und den aktuellen nativen Code.

## Ergebnis

Die App erfüllt die wesentlichen technischen und inhaltlichen Voraussetzungen: eigenständige native Funktionalität, Sign in with Apple, In-App-Kontolöschung, HTTPS-only, Datenschutzmanifest, Erklärungen für Kalender und Push, funktionierende Support-/Datenschutzseiten sowie einen klar abgegrenzten Admin-Bereich. Vor dem Upload bleiben zwei betriebliche Pflichtpunkte: ein echter Review-Account mit befüllten Daten und die Apple-Token-Widerrufs-Konfiguration in Production.

## Pflichtprüfung

| Bereich | Status | Befund / Maßnahme |
|---|---|---|
| 2.1 Vollständigkeit | Vor Upload | Release-Archive auf echtem Gerät und mit Production-Backend testen; App-Review-Konto samt Zugang und Hinweisen in App Store Connect hinterlegen. |
| 2.3 Metadaten | Vor Upload | Screenshots müssen die tatsächlich eingereichte native Version zeigen. Analyse, KI-Hinweis und In-App-Kontolöschung nicht als kommende Funktionen darstellen. |
| 4.2 Mindestfunktionalität | Erfüllt | Keine WebView-Hülle: Fragen, Beschlüsse, Sitzungen, Karte, Analyse, Themen, Quiz, Konto und Admin sind nativ. Externe Links öffnen nur amtliche Quellen und Rechtstexte. |
| 4.8 Anmeldung | Erfüllt | Bei E-Mail/Passwort als Primärlogin ist Sign in with Apple zusätzlich nativ vorhanden. |
| 5.1.1 Datenschutz | Erfüllt | Datenschutzlink ist in Login/Konto/Mehr erreichbar; `PrivacyInfo.xcprivacy` deklariert E-Mail, Name, User-ID, Nutzerinhalte und Push-Gerätekennung ohne Tracking. |
| 5.1.1(v) Kontolöschung | Code erfüllt / Production konfigurieren | Löschung ist in der App möglich und verlangt frische Re-Authentifizierung. Für Apple-Konten übermittelt die App jetzt zusätzlich den frischen Authorization Code; das Backend tauscht ihn und widerruft das Apple-Token. Production benötigt `APPLE_TEAM_ID`, `APPLE_KEY_ID` und `APPLE_PRIVATE_KEY`. |
| KI-Transparenz | Erfüllt | Vor der ersten Frage erscheint einmalig der Hinweis zu OpenRouter, passenden Ratsauszügen, möglicher Drittlandverarbeitung, Fehlern und personenbezogenen Daten; die Datenschutzerklärung ist direkt verlinkt. Die Speicherentscheidung wird ausdrücklich von der externen Verarbeitung getrennt. |
| Berechtigungen | Erfüllt | Kalenderzugriff wird erst bei „In Kalender“ angefragt und ist mit `NSCalendarsFullAccessUsageDescription` erklärt. Push wird erst nach dem eigenen Primer angefragt. Keine Standortberechtigung: die Karte zeigt Ratsdaten, nicht den Nutzerstandort. |
| Netzwerk | Erfüllt | Keine globale ATS-Ausnahme; API und Rechtstexte laufen über HTTPS. Datenschutz, Impressum, Hilfe und AASA antworteten beim Audit mit HTTP 200. |
| Admin-Schutz | Erfüllt | Native Admin-UI erscheint nur bei `role=admin`; jeder schreibende Endpunkt bleibt zusätzlich serverseitig durch die Admin-Abhängigkeit geschützt. |
| Barrierefreiheit | Nachweis vor Upload | Dynamic Type, VoiceOver, „Bewegung reduzieren“, Kontrast, Querformat und große Textgrößen auf einem echten Gerät durchgehen. Die Diagramme besitzen Beschriftung und eine alternative Wertetabelle. |
| iPad | Nachweis vor Upload | Split-Navigation und Zweispalten-Chat sind nativ. Vor Upload je ein vollständiger Smoke-Test auf iPad in Hoch-/Querformat und mit Stage Manager. |
| Kryptografie | Erfüllt | `ITSAppUsesNonExemptEncryption=false`; die App nutzt ausschließlich Betriebssystem-/HTTPS-Standardverschlüsselung. |

## App-Review-Notizen für App Store Connect

- Testkonto mit aktiven Beispielthemen, mindestens einem Gespräch, einer Sitzung und Analysewerten angeben.
- Kurz erklären: „Frag den Rat“ erzeugt KI-Text, jede Tatsachenbehauptung ist mit amtlichen Quellen verlinkt; maßgeblich bleibt das Original.
- Falls der Admin-Bereich geprüft werden soll, einen separaten Admin-Testaccount liefern. Keine Production-Zugangsdaten in Repository oder Review-Notizen einchecken.
- Push, Kalender, Sign in with Apple, Gesprächsspeicherung und Kontolöschung als prüfbare Schritte beschreiben.
- Production-Konfiguration vor Einreichung verifizieren: Apple-Revoke-Secrets, APNs-Production-Entitlement, `apple-app-site-association`, Datenschutz-/Support-URL und Backend-Migrationsstand.

## Bewusst nicht enthalten

- Haushalt bleibt wie beschlossen außerhalb dieses Releases.
- Das Kommunalwahl-Dev-Feature wird nicht beworben oder in die App übernommen.
- Es gibt kein Tracking, keine Werbung und keine In-App-Käufe.
