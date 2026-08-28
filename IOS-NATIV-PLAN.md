# Ratslotse nativ — Umbauplan Capacitor → SwiftUI

> **Status:** Implementiert als native 2.0-Grundlage am 28.08.2026. Phase 0,
> Kern-MVP und die zentralen Rats-Browser-/Paritätsbausteine sind im neuen
> Top-Level-Verzeichnis `ios/` umgesetzt. Die Empfehlungen aus Abschnitt 9
> wurden als Arbeitsannahmen übernommen: iOS 17, iPhone + iPad, MapKit,
> GitHub-Actions-Build und TestFlight-Cutover vor dem späteren
> Capacitor-Aufräumen. Details und Buildbefehle: `ios/README.md`.

Ziel: Aus der heutigen Capacitor-Shell (statischer Next-Export in einer WebView)
eine **wirklich native iOS-App** in Swift/SwiftUI machen, die direkt gegen die
bestehende FastAPI-REST-API spricht.

## 1. Ausgangslage

Heute ist die iOS-App eine **Capacitor-8-Shell um einen statischen Next-Export**
(`web/frontend/capacitor.config.ts`: `webDir: "out"`, keine Remote-URL). Die
Web-Assets liegen im Bundle, die App spricht mit `https://ratslotse.de` per
Bearer-Token. Drei Befunde bestimmen den Plan:

### 1.1 Der native Bestand ist winzig

Der gesamte iOS-spezifische Code ist **eine Swift-Datei**
(`web/frontend/ios/App/App/AppDelegate.swift`: APNs-Token-Weiterleitung an das
Push-Plugin, Edge-Swipe-Zurück via `MainViewController`) plus fünf
JS-Brückendateien mit zusammen ~317 Zeilen: `web/frontend/lib/platform.ts`,
`lib/push.ts`, `lib/apple.ts`, `lib/token.ts`, `lib/app-links.ts`. Nur diese
fünf Dateien (plus `capacitor.config.ts`) importieren `@capacitor/*`.

Der Umbau erbt keine Legacy — er erbt **Verankerungen**: Bundle-ID,
Entitlements, Privacy-Manifest, Icons und die Release-Doku in
`web/frontend/MOBILE.md`.

### 1.2 Das Backend ist bereits „app-ready"

- **Auth:** Header `X-Client: app` → `/api/auth/login`, `/register`,
  `/verify-email`, `/apple` und `/me` liefern `access_token` im Response-Body,
  Laufzeit **90 Tage** (`APP_ACCESS_TOKEN_EXPIRE_MINUTES`). Refresh-Mechanismus:
  `GET /api/auth/me` gibt bei jedem Aufruf ein frisches Token — App ruft ihn beim
  Start und ersetzt das gespeicherte.
- **Sign in with Apple:** `POST /api/auth/apple` (Body
  `{identity_token, given_name?, family_name?}`) validiert gegen Apples JWKS und
  akzeptiert `aud = de.ratslotse.app` (`APPLE_BUNDLE_ID`-Default) — serverseitig
  ist nichts Neues nötig.
- **Push:** `POST /api/push/register` (`{token, platform: "ios"}`) ist
  idempotent, gedacht für Re-Registrierung bei jedem App-Start. APNs läuft
  direkt bei Apple (kein Firebase, DSGVO-bewusst; `kern/push.py`),
  Prod/Sandbox-Fallback automatisch. Der Tap-Deep-Link steckt im Custom-Key
  `url` des Payloads (`kern/delivery.py`).
- **CORS wird irrelevant:** Ein URLSession-Client sendet keinen `Origin` —
  die ganze Capacitor-Origin-Mechanik (`app_cors_origins` in
  `web/backend/app/config.py`) samt Next-SSE-Proxy
  (`web/frontend/app/api/council/ask/route.ts`) entfällt für die native App.

### 1.3 Keine Store-Bestandsnutzer; der Aufwand liegt komplett im UI

Die App war **nie im öffentlichen App Store**, nur TestFlight (v1.13.2,
Build 17; Store-Version 1.0 hängt in „Prepare for Submission"). Keine
Migrationspflichten — nur die TestFlight-Tester sollen per Token-Übernahme
angemeldet bleiben (→ 3.1).

Der Aufwand steckt im Web-Inventar (~25 Screens), vier Brocken:

1. **Ratsgespräch**: `components/council-qa.tsx` (3226 Z.) +
   `qa-bausteine.tsx` (1026 Z.) + `deep-recherche.tsx` (359 Z.) — zwei
   SSE-Ströme, Zitat-Parsing, Verläufe, TTS, Teilen.
2. **Rats-Browser**: `app/(app)/council/view.tsx` (1725 Z.) — vier Tabs
   (Beschlüsse/Sitzungen/Themen/Auswertungen).
3. **Fünf Leaflet-Karten** (`council-map`, `entity-map`, `qa-orte-karte`,
   `quiz-map`, `quiz-locator-map`) + CARTO-Kacheln (`lib/basemap.ts`).
4. **Admin-Panel** (`app/(app)/admin/page.tsx`, 1342 Z.) — bleibt Web.

### 1.4 Was den Umbau unverändert überleben muss (extern verankert)

- **Bundle-ID `de.ratslotse.app`**: APNs-Topic in der Server-`.env`
  (`APNS_TOPIC`), `appID` in der AASA, ASC-App-Datensatz **6786553049**,
  Team `YM87689GUY`.
- **Die AASA-Pfadliste**
  (`web/frontend/public/.well-known/apple-app-site-association.json`):
  `/verify-email`, `/reset-password`, `/dashboard`, `/fragen`, `/fragen/*`,
  `/g`, `/topics`, `/council*`. Backend-Mails verlinken `/verify-email` und
  `/reset-password`; geteilte Links nutzen die **Query-Param-Formen**
  (`?id=`, `?tab=`, `?ksinr=&top=`, `?q=`, `?t=`, `?token=` …, vollständige
  Liste in `web/frontend/lib/routes.ts`). Die native App muss diese URLs
  weiterhin entgegennehmen und intern routen.

### 1.5 Bekannte Doku-Abweichungen (beim Umbau korrigieren)

- `MOBILE.md` behauptet iPhone-only — tatsächlich `TARGETED_DEVICE_FAMILY = 1,2`
  (iPhone **und** iPad, bewusst).
- `MOBILE.md` nennt bei den Capabilities nur Push + Associated Domains —
  das Entitlement **Sign in with Apple** fehlt in der Aufzählung.
- `STORE.md`-Buildstand ist veraltet (nennt Build 9, Projekt steht auf 17).

## 2. Zielbild & Technologie-Entscheidung

**Empfehlung: SwiftUI + Swift, ohne Umwege.**

| Option | Einordnung | Urteil |
|---|---|---|
| SwiftUI + Swift | Echte native App; voller Zugriff auf Widgets, Live Activities, App Intents, MapKit, EventKit, AVSpeechSynthesizer. Werkzeuge (Xcode 26.6, SPM, CLI-Release-Kette) auf Tims Mac eingerichtet. | **Empfehlung** |
| React Native / Expo | Nutzt React-Wissen, bleibt aber JS-Bundle mit Bridge — dem Anspruch „wirklich nativ" nur halb gerecht. | verworfen |
| Flutter | Eigene Rendering-Engine, kein natives UI-Verhalten, zusätzlicher Dart-Stack. | verworfen |
| Capacitor punktuell nativieren | Löst weder Review-Risiko 4.2 (Wrapper) noch WebView-Haptik. | verworfen |

Eckdaten:

- **Deployment-Target iOS 17** (heute 15.0): `@Observable`, `NavigationStack`,
  MapKit für SwiftUI, TipKit, Swift Charts. Ohne Store-Bestand kostet die
  Anhebung niemanden etwas. (iOS 18 diskutabel → Entscheidung 1.)
- **iPhone + iPad** wie heute; Layouts von Anfang an mit
  `horizontalSizeClass` denken (iPad-Lektionen: `DESIGNSPRACHE.md` §4).
- **Externe Dependencies ≈ 0**: URLSession statt Alamofire, eigener SSE-Parser
  (~100 Zeilen), `AttributedString(markdown:)` + eigener Fußnoten-Renderer.
  Jede Dependency ist ein Update-Risiko im Ein-Personen-Projekt.
- **Die Web-App bleibt das Vollsortiment** — die native App ist die kuratierte
  Alltagsoberfläche (→ 5.6 „Bleibt Web").

## 3. Architektur der App

Neues Top-Level-Verzeichnis `ios/` im Repo; das Capacitor-Projekt bleibt bis
zum Cutover unangetastet unter `web/frontend/ios/`.

```
ios/
  Ratslotse.xcodeproj          # App-Target, Entitlements, Assets, Widgets-Extension (Phase 4)
  Packages/
    RatslotseAPI/              # APIClient, Codable-Modelle, SSEClient, Keychain, URL-Router
    RatslotseDesign/           # Farb-/Typo-Tokens aus DESIGNSPRACHE.md, Bausteine
    RatslotseFeatures/         # je Feature ein Modul: Fragen, Rat, Themen, Quiz, Konto …
```

### 3.1 Netz & Auth (RatslotseAPI)

- **APIClient** als `actor` über URLSession async/await. Basis
  `https://ratslotse.de`, immer `X-Client: app` + `Authorization: Bearer`.
  Fehler-Decoder muss beide `detail`-Formen verkraften (String bei
  HTTPException, Array bei 422); 429 liefert `Retry-After` → Countdown-UI.
  Sonderfall: `DELETE /api/subscriptions` erwartet einen **Body**.
- **Token im Keychain** (`kSecAttrAccessibleAfterFirstUnlock`, damit ein
  Push-Tap vor dem ersten Entsperren nicht crasht). **Migration:** Capacitor
  Preferences legt den Token in UserDefaults unter
  `CapacitorStorage.access_token` ab — beim Erststart auslesen, in den
  Keychain übernehmen, aus UserDefaults löschen. TestFlight-Tester bleiben
  so angemeldet.
- **Kontozustände als eigene Screens:** `require_active` antwortet mit **403**
  (nicht 401) für unbestätigte/gesperrte Konten — die App ist dann
  „angemeldet, aber gesperrt" und zeigt Verify-/Pending-Zustände mit
  `/me`-Polling (Vorbild: `app/(app)/layout.tsx`).
- **Modelle handgeschrieben:** Die API hat kaum `response_model`-Typisierung —
  OpenAPI-Codegen ergäbe fast nur `[String: Any]`. Also Codable-Structs je
  genutztem Endpoint, abgesichert durch Vertragstests im Backend (→ B3).
  (Die OpenAPI-Spec gibt es nur lokal: `/openapi.json` ist in Prod
  abgeschaltet, lokal mit `COOKIE_SECURE=false` erreichbar.)

### 3.2 SSE-Engine — das technische Herzstück

- Generischer `SSEClient` über `URLSession.bytes(for:)` — **zwingend, weil
  `/council/ask` ein POST ist** (EventSource kann kein POST). Zeilenpuffer,
  `data:`-JSON-Frames, Keepalive-Kommentare (`: ping`) verwerfen.
- **Ratsgespräch** (`POST /api/council/ask`): Event-Folge
  `step → sources → token* → suggestions → done`, plus Sonderfälle
  `replace` (kompletter Textersatz, One-Shot-Fallback — muss implementiert
  sein), `abbruch` und `error`. Das `sources`-Event trägt die halbe Seite
  (Quellen, Presse, Debatten, Anlagen, Planungen, Sitzungen, Steckbriefe,
  Beleglage) und kommt nach ~2 s — das UI baut sich vor der Antwort auf.
- **Gründliche Recherche**
  (`GET /api/council/deep-research/{job}/events?ab=N`): Replay-fähig —
  Verbindungsabriss folgenlos, Job läuft serverseitig weiter, App verbindet
  mit höherem `ab` neu; `410 Gone` → Snapshot-Endpoint
  (`GET /deep-research/{job}`). Beim App-Start `/deep-research/aktuell`
  prüfen und laufende Jobs wieder anheften. Backgrounding beendet die
  Verbindung, `scenePhase .active` resumt.

### 3.3 Design-System (RatslotseDesign)

- `web/frontend/DESIGNSPRACHE.md` wird 1:1 zu Swift-Tokens: Farbtabellen
  hell/dunkel als Asset-Catalog-Farben, Radius-/Abstands-Konstanten,
  Semantik-Tints. Fonts **Inter, Bricolage Grotesque, IBM Plex Mono** sind
  SIL-OFL-lizenziert und werden gebündelt — die App behält ihre
  Typo-Identität statt auf SF Pro zu wechseln.
- Bausteine als SwiftUI-Views (Spez in `DESIGNSPRACHE.md` §5): Karte,
  Pill/Chip, Mono-Kicker, Ergebnis-Badge, Zeitstrahl, Quellen-Zeile,
  Fußnoten-Chip, Composer, Turn-Fußzeile.
- Dark Mode via Asset Catalog; „Automatisch" (heute App-only-Theme-Option)
  wird Standardverhalten.

### 3.4 URL-Router — eine Tabelle für drei Eingänge

Universal Links, Push-Taps (`data.url`) und interne Navigation laufen über
**ein** Mapping, destilliert aus `web/frontend/lib/routes.ts`. Es muss die
historischen Query-Param-Formen verstehen (`/council/decision?id=`,
`/council?tab=sessions&ksinr=…&top=…`, `/fragen?q=`, `/verify-email?token=` …) —
AASA, Mails und alle je geteilten Links verwenden sie. Intern navigiert die
App typisierte Ziele; die Query-Form ist nur die Eingangstür.

### 3.5 Rendering-Entscheidungen je Feature

| Web-Technik heute | Nativ | Anmerkung |
|---|---|---|
| Antwort-Markdown + Zitat-Chips (Regex `CITE_RE`/`ANL_RE` in `council-qa.tsx`) | AttributedString + eigener Chip-Layout | Regexe portieren; Paraphrasen kursiv ohne Anführungszeichen (Designsprache §1) |
| 5 × Leaflet + CARTO-Kacheln | MapKit (Cluster, Polygon-Overlays) | GeoJSON `public/geo/stadtteile-oldenburg.json` wiederverwenden; CARTO-Key entfällt → Entscheidung 3 |
| Diagramme: CSS-Balken + Inline-SVG (keine Chart-Lib!) | Swift Charts / eigene Views | bewusst schlank halten |
| `window.speechSynthesis` (Vorlesen) | AVSpeechSynthesizer | nativ besser steuerbar (Rate, Unterbrechung, Audio-Session) |
| `lib/ics.ts` (Kalender-Datei) | EventKit | echter „In Kalender"-Dialog statt Datei-Umweg |
| Pull-to-Refresh, Sheets, Scroll-Memory | SwiftUI-Bordmittel | `refreshable`, `sheet` — hier schrumpft Code |
| 3D-Lotti (three.js, nur Landing) | entfällt | SVG-Lotti (`mascot.tsx`) reicht; Landing bleibt Web |

## 4. Backend-Vorarbeiten (5 kleine PRs, alle vorab machbar)

| Nr | Paket | Warum |
|---|---|---|
| **B1** | **Token-Rückgabe bei Passwortwechsel:** `POST /api/account/change-password` und `/api/auth/reset-password` erhöhen die `token_version`, geben aber nur das Cookie neu aus — kein `access_token` im Body (`_to_out` ohne `_app_access_token`). | Ein Bearer-Client fliegt nach jedem Passwortwechsel mit 401 raus — **trifft schon die heutige Capacitor-App**. Sofort sinnvoll. |
| **B2** | **App-Config / Force-Update:** neuer öffentlicher Endpoint `GET /api/app-config` → `{min_build, hinweis}`; App prüft beim Start, zeigt ggf. Update-Screen. | Die API hat kein `/v1` und keinen Versionsvertrag; Store-Builds leben Monate. Lebensversicherung für spätere Breaking Changes. |
| **B3** | **Vertragstests:** pytest-Schema-Snapshots (Feldnamen + Typen) für jeden von der App genutzten Endpoint, als CI-Gate. Alternativ/zusätzlich schrittweise `response_model`. | Die meisten Council-Endpoints liefern untypisierte dicts — stille Feldumbenennung fiele sonst erst im Store-Build auf. |
| **B4** | **SSE-Routing prüfen:** sicherstellen, dass `ratslotse.de/api/council/ask` für native Clients direkt Caddy → FastAPI läuft, nicht durch den Next-Route-Handler (`app/api/council/ask/route.ts` hat Vorrang vor dem Rewrite). | Der Next-Proxy existiert nur für Web-CORS; für native Clients wäre er ein unnötiger Node-Hop in der Streaming-Latenz. |
| **B5** | **Rate-Limit-Key:** mindestens `/council/ask` auf Konto-ID statt Client-IP (`app/ratelimit.py` nutzt `request.client.host`). | Hinter Mobilfunk-CGNAT teilen sich fremde Nutzer einen Bucket (10 Logins/min, 10 Fragen/10 min). |

Optional (passt zu Phase 4): Badge-Zahl + `apns-collapse-id` im Push-Payload,
Push-Kategorien für Aktions-Buttons. Der Payload-Deep-Link (`url`) bleibt.

## 5. Phasenplan (~34 Arbeitspakete in PR-Größe)

### Phase 0 — Fundament (~6 Pakete)

- Xcode-Projekt in `ios/` anlegen; **Entitlements (Push, Sign in with Apple,
  `applinks:ratslotse.de`), `PrivacyInfo.xcprivacy`, Icons/Splash aus dem
  Capacitor-Projekt übernehmen**; Bundle-ID `de.ratslotse.app`, Team, Signing
  wie gehabt.
- RatslotseDesign: Farb-/Typo-Tokens, Fonts bündeln, 5–6 Kern-Bausteine.
- APIClient + Keychain + Token-Migration aus `CapacitorStorage.access_token`;
  `/auth/me`-Bootstrap mit den drei Kontozuständen.
- SSEClient mit Unit-Tests gegen aufgezeichnete Event-Streams (Fixtures vom
  echten Backend ziehen).
- URL-Router + Routen-Tabelle; Unit-Tests für alle AASA-Pfade und Query-Formen.
- Build-Skript/CI-Smoke: `xcodebuild build` je PR (→ Entscheidung 7).

**Ergebnis:** App baut, loggt ein, empfängt SSE-Fixtures.

### Phase 1 — Kern-MVP (~10 Pakete) → TestFlight-fähig

- **Auth-Screens:** Login, Registrierung, Sign in with Apple (natives
  `ASAuthorizationController` — kein Plugin mehr), Passwort vergessen/
  zurücksetzen, E-Mail bestätigen — inkl. Deep-Link-Einstiege
  (`/verify-email?token=` loggt per `X-Client: app` direkt ein).
- **App-Hülle:** Tab-Leiste (Heute · Fragen · Rat · Themen · Konto),
  Verify-/Pending-Vollbildzustände, Offline-Pille (`NWPathMonitor`).
- **Dashboard „Heute":** `/heute`, `/diese-woche`, `/wochenvorschau`,
  `/fundstueck`, letzte Beschlüsse, Push-Primer.
- **Ratsgespräch v1** — bewusst in 3–4 Pakete geschnitten:
  (a) Composer + Streaming + Antwort-Rendering mit Fußnoten-Chips,
  (b) Quellen/Belege-Sheet aus dem `sources`-Event,
  (c) Verläufe (`/gespraeche` CRUD) + Weiterfragen-Chips + Beispielfragen,
  (d) Fehler-/Limit-/Abbruch-Zustände nach Interaktions-Grammatik.
  *Bewusst noch ohne:* Partei-Meinungen, Drucken, TTS, Orts-Minikarte.
- **Push komplett:** Permission-Flow, Registrierung bei jedem Start,
  Tap-Routing, Logout-Unregister; Ende-zu-Ende-Test über
  `POST /api/account/test-notification`.
- **Konto-Basics:** Anzeigename, Zustellkanäle (`email/push/both/off`),
  Benachrichtigungs-Anlässe (Labels kommen vom Server — nicht hardcoden),
  Abmelden, Konto löschen (mit Apple-Re-Auth).

### Phase 2 — Rats-Browser (~10 Pakete)

- Beschluss-Suche mit Filtern (Gremium, Partei, Themenfeld, Stadtteil,
  Zeitraum).
- Beschluss-Detail: Abstimmung, Fraktionen, Anlagen (PDF via
  `QLPreviewController`), Zeitstrahl/Beratungsfolge, Teilen, Merken, Folgen.
  **Öffentlich lesbar** — funktioniert vor dem Login (Universal-Link-Einstieg;
  öffentliche Pfade siehe `lib/public-routes.ts` + `optional_user` im Backend).
- Sitzungen + Tagesordnungen (`?ksinr=`/`?top=`-Routing), Kalender-Export per
  EventKit, Live-Sitzungs-Banner (`lib/live.ts`-Logik portieren).
- Personen-Seiten (öffentlich), Themen-/Entitätsseiten (öffentlich, Karte in
  Phase 3), Orts-Seiten.
- Merkliste; „Meine Themen": Abos anlegen/bearbeiten/löschen inkl.
  LLM-Beschreibung (`/topics/describe`), Ungelesen-Zähler, verfolgte Vorlagen.
- Onboarding-Flow (Themen wählen → Abos → Push).

### Phase 3 — Parität (~8 Pakete) → Capacitor kann weg

- Karten: Stadtkarte mit Clustering + Stadtteil-Polygonen, Themen-Karte,
  Orts-Minikarte unter KI-Antworten, Vollbild.
- Quiz: alle vier Modi (normal/Wiederholung/Tagesfrage/eigene), Karten-Fragen
  (Polygon-Tap), Streak, Abzeichen, Statistik mit Swift Charts.
- Gründliche Recherche: Job-Start, Facetten-Fortschritt, Resume nach
  App-Wechsel, Stop/Teilbericht, Wiederaufnahme beim Start.
- Ratsgespräch-Vervollständigung: Partei-Meinungen, TTS, Teilen-Snapshot
  (Share-Sheet mit `https://ratslotse.de/g?t=…` — `/g` bleibt Web),
  Feedback-Daumen.
- Tour/Feature-Hinweise mit TipKit, Hilfe/FAQ + Kontaktformular, Rechtstexte.

### Phase 4 — Native Dividende (offen, inkrementell nach Cutover)

| Feature | Was es tut | Trägt darauf |
|---|---|---|
| Widgets | „Heute im Rat", Wochenvorschau, Fundstück auf Home-/Lockscreen | `/heute`, `/wochenvorschau`, `/fundstueck` — fertig |
| Live Activity | Laufende Ratssitzung in der Dynamic Island: aktueller TOP, Stream-Link | `lib/live.ts`-Zeitfenster + Tagesordnungsdaten |
| App Intents / Siri | „Frag den Rat …" als Shortcut | `/council/ask` |
| Spotlight | Gemerkte Beschlüsse/Themen in der iOS-Suche | Merkliste/Abos lokal indexieren |
| Push-Ausbau | Badge-Zahlen, Aktions-Buttons | Backend-Paket (collapse-id, Kategorien) |
| Handoff | Jede App-Ansicht hat ihre Web-URL; Teilen bleibt `https://` | URL-Router rückwärts |

### 5.6 Bleibt bewusst Web (Positivliste, keine Restmenge)

- **Admin-Panel** (acht Tabs) — bei Bedarf Link im Konto-Tab für Admins.
- **Landing `/`, Changelog, `/g`-Share-Snapshots** (OG-Metadaten brauchen
  Server-Rendering), Doku.
- **3D-Lotti** — Landing-Schmuck, kein App-Feature.

## 6. Übergang & Release

- **Parallelbetrieb:** Capacitor bleibt voll baubar — Hotfixes an der heutigen
  App jederzeit möglich. Für Side-by-side-Tests bekommt die Debug-Konfiguration
  des neuen Projekts temporär eine zweite Bundle-ID (z. B. `de.ratslotse.dev`);
  Release behält `de.ratslotse.app`.
- **TestFlight-Cutover** (nach Phase 1 oder 2 → Entscheidung 4): Der native
  Build ersetzt den Capacitor-Build unter derselben ASC-App — Build-Nummern
  zählen weiter (> 17), `MARKETING_VERSION` springt auf **2.0.0**. TestFlight
  verteilt automatisch an die interne Gruppe; die Token-Migration hält alle
  angemeldet. „Rollback" = neuer Capacitor-Build mit höherer Nummer.
- **Release-Prozess bleibt der CLI-Weg** aus `MOBILE.md`
  (`xcodebuild archive` / `-exportArchive` + `altool` + ASC-API-Polling) —
  nur ohne `npm run build:mobile`/`cap sync` davor. Versionspflege in ein
  kleines Skript (agvtool/xcconfig) statt Hand-Edits im pbxproj. `MOBILE.md`
  neu schreiben; Simulator-/devicectl-/Signing-Abschnitte bleiben fast
  wörtlich gültig.
- **Store-Launch:** ASC-App 6786553049 ist mit Metadaten, Screenshots,
  Altersfreigabe fertig befüllt (Feldwerte: `web/frontend/STORE.md`). Der
  Umbau ist der natürliche Moment, mit 2.0.0 einzureichen — neue Screenshots
  nötig, Privacy-Labels bleiben inhaltlich gleich. Das in `MOBILE.md`
  notierte **Review-Risiko 4.2 („Wrapper-App") verschwindet**.
- **Aufräumen nach Cutover** (eigener PR-Block): `scripts/build-mobile.mjs`
  samt CSP-Injektion, die fünf `lib/`-Brücken, Capacitor-Dependencies +
  patch-package (`patches/`), Next-SSE-Proxy-CORS, `app_cors_origins` im
  Backend, `web/frontend/ios/` und ggf. `android/`. Das Web-Frontend wird
  messbar einfacher (kein `MOBILE=1`-Sonderbuild mehr).
- **Android** ist reines Gerüst (nie released, `google-services.json` fehlt,
  App-Links-Platzhalter in `assetlinks.json`). Empfehlung: mit dem Cutover
  einfrieren/streichen; falls Android je kommt, ist Kotlin/Compose gegen
  dieselbe API der konsequente Weg (→ Entscheidung 2).

## 7. Risiken & Gegenmittel

| Risiko | Schwere | Gegenmittel |
|---|---|---|
| **Doppelpflege Web + iOS** — jedes Nutzerfeature künftig zweimal | strukturell | API-first als Regel (Feature = erst Backend + Web, App zieht nach); bewusste Untermenge (5.6 ist Positivliste); App-Hinweise über `app-config` statt App-Update |
| **Ratsgespräch-Parität unterschätzt** — `sources`-Event trägt 7 Baustein-Typen, dazu Zitat-Parsing, Verläufe, Limits, Abbruch | hoch | Baustein-Liste aus `qa-bausteine.tsx` als Checkliste; MVP-Schnitt in Phase 1 bewusst schmal; SSE-Fixtures vom echten Backend |
| **Kein API-Versionsvertrag** — Web-PR benennt still ein Feld um, Store-Build bricht Monate später | mittel | B2 (min_build) + B3 (Vertragstests als CI-Gate); ohne beide kein Store-Release |
| **SSE über Mobilfunk**: Abrisse, Captive Portals, Backgrounding | mittel | Deep Research resumt per Design (`?ab=`); `/ask` resumt nicht → Abbruch-Zustand nach Interaktions-Grammatik: „Frage steht wieder im Eingabefeld", nie Datenverlust |
| **MapKit ändert Karten-Optik**; Datenschutz-Kapitel nennt CARTO | klein | Apple statt CARTO ist DSGVO-seitig eher Fortschritt; Datenschutzerklärung anpassen. Optik-Konsistenz: CARTO-Kacheln als MapKit-Overlay möglich (→ Entscheidung 3) |
| **Review-Flächen**: TTS, nutzergenerierte Quiz-Fragen, KI-Inhalte | klein | Alles heute schon deklariert (`STORE.md`, Demo-Konto); 4.2 entfällt, netto sinkt das Risiko |
| **Bus-Faktor** für Swift neben Python + TypeScript | mittel | Dependencies ≈ 0, Standard-Patterns (@Observable, async/await), gleiche PR-Disziplin; Architektur-Doku von Anfang an in `docs-site/` |

## 8. Aufwandsschätzung

| Block | Pakete | Meilenstein |
|---|---|---|
| Backend-Vorarbeiten B1–B5 | 5 kleine | parallel zu Phase 0; B1 sofort sinnvoll |
| Phase 0 — Fundament | ~6 | App baut, loggt ein, empfängt SSE-Fixtures |
| Phase 1 — Kern-MVP | ~10 | **TestFlight-Cutover möglich** |
| Phase 2 — Rats-Browser | ~10 | Alltags-Parität |
| Phase 3 — Parität | ~8 | **Capacitor + Brücken löschen, Store-Einreichung 2.0.0** |
| Phase 4 — Native Dividende | offen | inkrementell, nichts blockiert |

Kalenderzeit beim eingespielten Takt dieses Repos (mehrere PR-große Pakete pro
Arbeitstag): **Phase 1 nach ~1,5–2 Wochen, Phase 3 nach ~5–8 Wochen** — die
Spanne hängt fast vollständig an der Ratsgespräch-Parität. Jedes Paket ist ein
PR mit eigenem, prüfbarem Ergebnis; der Plan bleibt gültig, wenn der Takt ein
anderer ist.

## 9. Offene Entscheidungen

**Vor Phase 0 mit Tim klären.** Die Empfehlungen sind Vorschläge, keine
Beschlüsse.

1. **Mindest-iOS 17 oder 18?** — *Empfehlung: 17* (maximale Abdeckung bei
   vollem SwiftUI-Komfort; 18-only-Features für Ratslotse verzichtbar).
2. **Android: einfrieren, streichen oder Capacitor weiterpflegen?** —
   *Empfehlung: streichen* (Verzeichnis + Brücken raus, Entscheid
   dokumentieren); „Kotlin später, gleiche API" bleibt davon unberührt.
3. **Karten: MapKit pur oder CARTO-Kacheln als Overlay?** — *Empfehlung:
   MapKit pur* (ein Key und ein Wasserzeichen-Thema weniger).
4. **Cutover-Schwelle: TestFlight-Umstieg nach Phase 1 oder erst Phase 2?** —
   *Empfehlung: nach Phase 1* (frühes Feedback der Tester-Gruppe; fehlende
   Flächen öffnen übergangsweise die Web-App per Link).
5. **Store-Einreichung an 2.0.0 koppeln?** — *Empfehlung: ja, nach Phase 3.*
6. **iPad von Anfang an mit?** — *Empfehlung: ja, als Layout-Disziplin
   (Size-Classes ab Phase 0), nicht als eigene Screens.*
7. **CI: xcodebuild auf GitHub-Actions-macOS-Runnern oder Tims Mac?** —
   *Empfehlung: Build-Smoke in Actions, Release weiter lokal* (Signing +
   Upload bleiben auf dem eingerichteten Mac).

---

*Erhoben aus: `web/frontend` (Routen, Capacitor-Brücken, `build-mobile.mjs`),
`web/backend/app` (Router, Auth, Push, SSE, Rate-Limits),
`web/frontend/ios/App` (pbxproj, Entitlements, Info.plist), `MOBILE.md`,
`STORE.md`, `DESIGNSPRACHE.md`.*
