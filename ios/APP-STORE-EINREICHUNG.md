# App-Store-Einreichung: Anleitung für die offenen Punkte

Stand: 10. September 2026. Ergänzt die Checkliste in
[`APP-STORE-REVIEW-AUDIT.md`](APP-STORE-REVIEW-AUDIT.md) um das, was nur der
Account Holder in App Store Connect oder jemand mit dem Gerät in der Hand
erledigen kann. Reihenfolge wie dort: Abschnitte 1 bis 5 vor dem Release,
Abschnitt 6 erst mit dem Release-Build.

Voraussetzungen: Anmeldung bei [appstoreconnect.apple.com](https://appstoreconnect.apple.com)
als Account Holder; TestFlight-Build 22 (oder neuer) auf iPhone **und**
iPad installiert; ein eigenes Prod-Konto mit Adminrolle (nicht das
Review-Konto).

## 1. Privacy Labels (App-Datenschutz)

Apple verlangt, dass die Angaben im Store zu dem passen, was die App an
den Server schickt. Die Quelle der Wahrheit ist
[`Resources/PrivacyInfo.xcprivacy`](Resources/PrivacyInfo.xcprivacy). Dort
stehen genau sechs Datentypen, alle „mit der Identität verknüpft", alle
„nicht für Tracking"; fünf mit dem Zweck „App-Funktionalität", die
Produktinteraktion zusätzlich mit „Analysen" (das Backend zählt je Konto
und Tag, welche Funktionen benutzt werden: `user_activity` in
`kern/store.py`).

1. App Store Connect → **Apps → Ratslotse → App-Datenschutz** (linke
   Spalte, unter „Allgemein").
2. Falls noch nie ausgefüllt: **Erste Schritte**. Frage „Erfassen Sie oder
   Ihre Drittanbieter-Partner Daten in dieser App?" → **Ja, wir erfassen
   Daten in dieser App**.
3. Datentypen anhaken, sonst nichts:

   | Kategorie | Datentyp | Grund |
   |---|---|---|
   | Kontaktinformationen | **Name** | Anzeigename im Konto |
   | Kontaktinformationen | **E-Mail-Adresse** | Anmeldung, Benachrichtigungen |
   | Kennungen | **Benutzer-ID** | Kontonummer im Backend |
   | Kennungen | **Geräte-ID** | Push-Token für APNs |
   | Nutzerinhalte | **Andere Nutzerinhalte** | Fragen, Themen, geteilte Antworten |
   | Nutzungsdaten | **Produktinteraktion** | Zähler je Konto und Tag: Sitzung, KI-Frage, Recherche, Suche, Analyse, Karte |

4. **Weiter**. Für jeden der sechs Typen erscheinen drei Fragen:
   - Verwendungszweck: **App-Funktionalität**; bei Produktinteraktion
     zusätzlich **Analysen**.
   - „Sind die Daten mit der Identität des Nutzers verknüpft?" → **Ja**.
   - „Werden die Daten für Tracking verwendet?" → **Nein**.
5. Am Ende **Veröffentlichen**. Die Angaben gelten für alle künftigen
   Versionen, bis sie geändert werden.

Nicht anhaken, auch wenn es plausibel klingt: Standort (die Karte zeigt
Ratsdaten, nie den Nutzerstandort; „Mein Viertel" ist eine Kontoangabe),
Suchverlauf (gezählt wird, dass gesucht wurde, nicht wonach), Diagnose
(kein eigenes Crash-Reporting; der Fehlersammler speichert kein Konto und
keine Gerätekennung, siehe `kern/fehler.py`), Kundendienst (das
Feedback-Formular fällt unter Apples Ausnahme für optionale Formulare),
Kaufhistorie.

## 2. Händlerstatus nach dem Digital Services Act

Ohne diese Angabe nimmt Apple seit Februar 2025 keine Einreichung für die
EU an; sie steht deshalb vor allem anderen.

1. App Store Connect → **Geschäft** (oben in der Leiste; nur der Account
   Holder sieht den Punkt) → **Digital Services Act** beziehungsweise der
   Hinweisbanner „Händlerstatus angeben" auf der Startseite.
2. Frage „Sind Sie ein Händler?" → **Nein, ich bin kein Händler** (Ratslotse
   ist kostenlos, ohne Käufe, Werbung oder Spenden, kein Gewerbe).
3. Bestätigen. Der Status erscheint danach im Store-Eintrag als „Nicht
   gewerblicher Anbieter"; Apple blendet in der EU einen entsprechenden
   Hinweis in der App-Seite ein.

Sollte Ratslotse einmal Einnahmen haben, muss der Status auf „Händler"
wechseln; dann verlangt Apple Adresse, Telefonnummer und E-Mail-Adresse
zur Veröffentlichung im Store.

## 3. Gerätetests

Alles mit dem TestFlight-Build, angemeldet mit dem eigenen Konto. Bei
jedem Test gilt: kein Absturz, keine leere Ansicht, jeder Weg zurück
funktioniert. Auffälliges als Screenshot in TestFlight melden (App
schütteln oder Screenshot machen → „Feedback teilen"), das landet in der
API, die ich lesen kann.

### 3a. VoiceOver (iPhone reicht)

1. Einstellungen → **Bedienungshilfen → Kurzbefehl** → VoiceOver anhaken.
   Danach schaltet dreimaliges Drücken der Seitentaste VoiceOver an und
   aus. Ohne den Kurzbefehl ist das Abschalten mühsam.
2. VoiceOver an, Ratslotse öffnen. Bedienung: einmal tippen wählt aus und
   liest vor, doppeltes Tippen aktiviert, Wischen nach rechts geht zum
   nächsten Element.
3. Diese Wege durchgehen und darauf achten, dass jedes Element einen
   sprechenden Namen hat (nicht nur „Taste" oder „Bild"):
   - **Start:** Begrüßung, Frage-Feld („Frag den Rat"), Live-Karte,
     Neu-bei-Ratslotse-Karte, Tab-Leiste (fünf Tabs mit Namen).
   - **Fragen:** ins Feld, eine Frage diktieren oder tippen, absenden. Die
     Antwort muss vorgelesen werden, Fußnoten müssen als Links erkennbar
     sein, der Daumen-hoch/-runter mit Namen.
   - **Sitzungen:** eine Sitzung öffnen, Tagesordnung durchwischen, „In
     Kalender" muss als Taste mit Namen kommen.
   - **Beschluss:** Titel, Ergebnis-Badge („Angenommen"), Abstimmung,
     Quellen-Link.
   - **Mehr → Konto:** alle Schalter mit Namen und Zustand („an"/„aus").
4. Kurzbefehl dreimal drücken, VoiceOver aus.

### 3b. Bewegung reduzieren

1. Einstellungen → **Bedienungshilfen → Bewegung → Bewegung reduzieren**
   an.
2. Ratslotse neu starten. Prüfen: Lotti blinzelt und atmet nicht mehr,
   Blätter erscheinen mit Überblendung statt Schieben, die
   Neu-bei-Ratslotse-Karte blättert ohne Animation, die Karte (Mein
   Viertel) zoomt ohne Flug.
3. Einmal durch alle fünf Tabs, einmal eine Frage stellen. Danach die
   Einstellung wieder aus.

### 3c. Stage Manager und Split View (iPad)

1. Kontrollzentrum (von oben rechts wischen) → **Stage Manager** an.
2. Ratslotse öffnen, am unteren Fensterrand ziehen und das Fenster
   schmal machen (etwa ein Drittel der Breite). Erwartung: Die
   Seitenleiste klappt zusammen, die Tab-Leiste übernimmt, nichts
   überlappt.
3. Fenster wieder breit ziehen: Seitenleiste kommt zurück.
4. Split View ohne Stage Manager: Ratslotse öffnen, oben die drei Punkte
   → **Split View** → Safari daneben. Ratslotse auf beide Breiten testen,
   dabei einmal eine Frage stellen und einen Beschluss öffnen.
5. Gerät im Querformat drehen, dann wieder hoch: Kein Sprung im Layout,
   das Frage-Feld bleibt erreichbar.

### 3d. Schwaches Netz

Am einfachsten mit dem **Network Link Conditioner**, der auf dem iPhone
erscheint, sobald das Gerät einmal an Xcode hing:

1. Einstellungen → **Entwickler** (ganz unten) → **Network Link
   Conditioner** → Profil **3G** oder **Very Bad Network** wählen,
   Schalter an.
2. Ratslotse starten und eine Frage stellen. Erwartung: Der Sende-Knopf
   zeigt Aktivität, die Antwort trudelt ein, der Verlauf bleibt bedienbar.
   Kein Abbruch ohne Meldung.
3. Beschlussliste scrollen, Sitzung öffnen, Karte laden: Ladezustände
   sichtbar, keine leere Fläche ohne Hinweis.
4. Conditioner aus, dann **Flugmodus** an und dieselben drei Wege: Die
   App muss jeweils „Das hat nicht geklappt" mit „Noch einmal versuchen"
   zeigen; Start zeigt „Zuletzt angesehen" aus dem lokalen Vorrat.
   Flugmodus aus, „Noch einmal versuchen" tippen: lädt.

Fehlt der Punkt „Entwickler" in den Einstellungen: iPhone per Kabel an
den Mac, Xcode öffnen, Window → Devices and Simulators, Gerät auswählen;
danach ist das Menü da.

### 3e. Apple-Login, Push, Kalender, Kontolöschung

Das braucht ein **Wegwerfkonto**, weil die Kontolöschung am Ende steht.
Bitte nicht mit dem eigenen Konto und nicht mit dem Review-Konto.

1. Ratslotse abmelden (Mehr → Konto → Abmelden), auf der Anmeldeseite
   **Mit Apple anmelden**. Beim Apple-Dialog „E-Mail verbergen" wählen;
   so entsteht ein frisches Konto mit Relay-Adresse. Erwartung: Direkt
   eingeloggt, Einrichtungs-Assistent startet.
2. Im Assistenten den Push-Schritt durchlaufen: Erst erscheint der
   eigene Erklärbildschirm („Soll Lotti sich melden?"), erst nach
   „Mitteilungen erlauben" der iOS-Dialog. **Erlauben**.
3. Push-Empfang prüfen: Ein Ausschuss abonnieren (Mehr → Ausschuss-Abos).
   Einen Test-Push gibt es weder im Admin-Panel noch als Skript; der
   direkte Weg ist eine Meldung in der Warteschlange, ausgeliefert über
   denselben Pfad wie jede echte (Konto-ID im Admin-Panel unter
   *Web-Nutzer\*innen* ablesen):

   ```bash
   cd ~/app && .venv/bin/python -c "
   from kern.store import Store; from kern import notify
   s = Store(); notify.einreihen(s, KONTO_ID, 'digest', 'Probe', '<p>Probe</p>', 'https://ratslotse.de/sitzungen', push_text='Probe von Ratslotse', wichtig=True); notify.zustellen(s)"
   ```

   Nachtruhe und Tagesgrenze gelten auch hier: tagsüber ausführen. Der
   Push muss auf dem Sperrbildschirm ankommen und beim Antippen die
   Sitzungen öffnen.
4. Kalender: Sitzungen → eine Sitzung → **In Kalender**. Erst jetzt darf
   der iOS-Dialog für den Kalenderzugriff erscheinen; **Vollzugriff
   erlauben**, dann erscheint das Bearbeiten-Blatt von iOS mit Titel, Ort
   und Uhrzeit; **Hinzufügen**. In der Kalender-App nachsehen.
5. Kontolöschung: Mehr → Konto → **Konto löschen**. Bei einem
   Apple-Konto erscheint der Apple-Dialog noch einmal (frischer
   Authorization Code), danach die Bestätigung. Erwartung: App steht auf
   der Anmeldeseite; unter iOS-Einstellungen → Apple-ID → **Mit Apple
   anmelden** ist Ratslotse **nicht mehr** aufgeführt. Ist es noch dort,
   hat der Token-Widerruf auf dem Server nicht funktioniert; dann im
   Admin-Panel unter *Fehler* nachsehen.

## 4. Moderationsprobe: Teilen, Melden, Entfernen, Sperren

Auch hier ein Wegwerfkonto (das aus 3e, **vor** der Löschung) oder das
eigene Testkonto, nie das Review-Konto: Es wird am Ende gesperrt.

1. **Teilen (App):** Fragen → eine Frage stellen → unter der Antwort
   **Weitergeben** → „Antwort als Link teilen" → Link kopieren. Der Link
   hat die Form `ratslotse.de/g?t=…`.
2. **Melden (ohne Konto):** Den Link in Safari im privaten Modus öffnen
   (nicht angemeldet). Unten **Inhalt melden** → Grund wählen
   (unangemessen, irreführend, Privatsphäre, anderer Grund) → absenden.
   Erwartung: „Gemeldet – danke". Ein zweites Melden vom selben Gerät
   innerhalb weniger Minuten wird gebremst; das ist gewollt.
3. **Ansehen (Admin, Web):** ratslotse.de/admin → Reiter **Feedback**.
   Der Eintrag trägt das rote Etikett **Geteilter Inhalt** und nennt
   Grund, Share-Token und die interne Inhaber-ID. Die Mail dazu ist
   parallel an `FEEDBACK_EMAIL` gegangen.
4. **Entfernen (Web):** Im selben Eintrag **Link entfernen**. Danach den
   Link in Safari neu laden: 404 „Nicht gefunden".
5. **Sperren (Web):** Reiter **Web-Nutzer\*innen** → das Konto über die
   Inhaber-ID oder E-Mail suchen → **Sperren**. In der App des gesperrten
   Kontos: Beim nächsten Aufruf Abmeldung mit Hinweis, Anmeldung
   schlägt fehl.
6. **Dasselbe in der App:** Auf dem iPhone mit dem Admin-Konto Mehr →
   **Admin**. Dort unter den Nutzer\*innen **Sperren/Freischalten** und
   bei einer zweiten Meldung das Entfernen des Links. Beide Wege müssen
   funktionieren, weil Apple die App prüft, nicht die Website.
7. Eintrag im Feedback **Abhaken**, Konto wieder **Freischalten** (oder
   löschen, wenn es das Wegwerfkonto war).

## 5. Moderationspostfach

Meldungen erreichen zwei Orte: das Admin-Panel (Reiter Feedback, mit
Zähler „offen") und das Postfach hinter `FEEDBACK_EMAIL`, derzeit
`ratslotse@timsigl.de`. Apple erwartet, dass Meldungen zeitnah
bearbeitet werden; eine feste Frist nennt die Richtlinie nicht, in der
Praxis gelten 24 Stunden als sicher.

Festzulegen, am besten in einer Zeile in dieser Datei:

- **Wer** liest das Postfach und wie oft (Vorschlag: täglich, als
  Erinnerung im Kalender).
- **Was** passiert bei einer Meldung: erst Link entfernen (ist
  umkehrbar nicht, aber der Inhalt bleibt im Konto), dann prüfen, dann
  bei Missbrauch sperren.
- **Wo** das festgehalten wird: Abhaken im Feedback-Reiter reicht als
  Protokoll.

Technisch nützlich: Im Postfach eine Regel anlegen, die Mails mit
Betreff „Geteilter Inhalt" oder dem Absender `noreply@ratslotse.de` in
einen eigenen Ordner mit Benachrichtigung legt, damit sie zwischen den
Cron-Alarmen nicht untergehen.

Zuständigkeit (bitte ausfüllen): _______________________

## 6. Einreichung (erst mit dem Release-Build aus `main`)

Voraussetzung: Release-PR `dev` → `main` ist gemergt, der Store-Build
ist aus `main` archiviert und hochgeladen (Weg wie in `ios/README.md`),
in App Store Connect steht er unter TestFlight auf „Bereit zum Testen".

1. **Version anlegen:** Apps → Ratslotse → linke Spalte neben „iOS-App"
   auf **+** → Versionsnummer wie `MARKETING_VERSION` (z. B. 2.4.0). Die
   alte 1.10.0 kann stehen bleiben; Apple nimmt nur eine Version in
   Vorbereitung, also gegebenenfalls die 1.10.0 auf die neue Nummer
   umbenennen statt neu anlegen.
2. **Build anhängen:** Abschnitt „Build" → **+** → den neuen Build
   wählen. Die Export-Compliance-Frage entfällt, weil
   `ITSAppUsesNonExemptEncryption=false` im Info.plist steht.
3. **Neu in dieser Version:** den Abschnitt aus `CHANGELOG.md` in
   Prosa kürzen, drei bis sechs Zeilen, keine PR-Nummern.
4. **Screenshots:** Pflicht sind iPhone 6,7 Zoll (1290 × 2796) und iPad
   13 Zoll (2064 × 2752); Apple skaliert die kleineren Geräte daraus.
   Aufnehmen aus genau diesem Build mit dem Review-Konto oder dem
   eigenen, nie mit erfundenen Beschlüssen. Reihenfolge: Frage mit
   Antwort, Beschluss, Sitzungen, Stadtkarte, Themen. Mindestens drei,
   höchstens zehn je Gerät. Die alten sechs vom August vorher löschen.
5. **Prüfen, was schon steht:** Beschreibung, Schlüsselwörter, Support-
   und Marketing-URL, Kategorie (Bildung), Altersfreigabe (4+ mit UGC),
   App-Review-Informationen (Kontakt, Demo-Konto, Notizen). Das ist
   alles eingetragen; nur lesen, ob es noch stimmt.
6. **Freigabe-Art:** Abschnitt „Versionsfreigabe" → **Diese Version
   manuell freigeben**. Dann kann nach der Genehmigung der Server-Stand
   in Ruhe geprüft werden, bevor die App im Store erscheint.
7. Oben rechts **Zur Prüfung hinzufügen** → **Zur Prüfung einreichen**.
   Status wechselt auf „Wartet auf Prüfung". Übliche Dauer: 24 bis 48
   Stunden, bei der ersten Einreichung gern länger.
8. Kommt eine **Rückfrage oder Ablehnung**, steht sie im Bereich
   „App-Review" mit Verweis auf die Richtlinie. Antworten geht im
   selben Dialog; bei einer Ablehnung wegen Metadaten reicht Ändern und
   erneut Einreichen, bei einer wegen Code ein neuer Build.

## 7. Nach der Genehmigung

1. Status „Zur Verkaufsfreigabe bereit" → **Diese Version freigeben**.
   Die App ist danach innerhalb weniger Stunden im Store.
2. Auf dem Server `APP_MIN_BUILD` in der `.env` auf die eingereichte
   Build-Nummer setzen und `nwz-web-api` neu starten. Ältere
   TestFlight-Builds zeigen dann den Aktualisierungs-Schirm.
3. In App Store Connect → Ratslotse → **App-Store-Version** die Option
   „Automatische Updates" prüfen; App-Store-Kund*innen bekommen Updates
   ohnehin automatisch.
4. Die Neuigkeiten-Karte im Admin-Panel unter *Neuigkeiten* ein paar Tage
   nach dem Erscheinen verschicken (Ausliefern und Ankündigen sind zwei
   Entscheidungen).
5. TestFlight-Feedback und die ersten Rezensionen im Auge behalten;
   Rezensionen lassen sich in App Store Connect unter **Bewertungen und
   Rezensionen** beantworten.
