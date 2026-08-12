# Ratslotse mobile apps (Capacitor)

The iOS/Android apps are the **same Next.js frontend**, statically exported and
wrapped in a Capacitor 8 native shell. They talk to the existing FastAPI backend
at an absolute origin with a **bearer token** (see `lib/platform.ts`,
`lib/token.ts`), so no cookies/proxy are involved. Native **push** is a delivery
channel alongside email.

## What's already wired in the repo

- **Auth:** app sends `X-Client: app`; backend returns a long-lived JWT which the
  app stores on-device (`@capacitor/preferences`) and sends as a bearer. Logout
  unregisters the device's push token first.
- **API base:** `""` (same-origin) on web, `https://ratslotse.de` in the app
  (override with `NEXT_PUBLIC_API_BASE` at build time — also feeds the app CSP).
- **CORS:** the backend always allows the app WebView origins
  (`capacitor://localhost`, `https://localhost`) — no `.env` change needed.
- **Static export:** `MOBILE=1 next build` → `./out` (via `npm run build:mobile`,
  which also removes the web-only SSE route handler and injects the app CSP).
- **Routing:** council detail views use query-param routes so the export needs no
  dynamic-route enumeration; in the app, `/` redirects straight to the dashboard.
- **Push:** `lib/push.ts` (permission + token registration + tap-to-navigate);
  `POST /api/push/register` / `/unregister`; backend sends via APNs/FCM
  (`kern/push.py`) and prunes device tokens the gateways report as gone.
- **Capacitor:** `capacitor.config.ts`, deps + scripts in `package.json`.

## One-time setup (on the Mac)

**Already done and committed** (`ios/`, `android/`, icons/splash, entitlements) —
kept for reference in case the native projects ever need regenerating:

Requires **Node ≥ 22** (Capacitor 8 CLI) and a current Xcode / Android Studio.

```bash
cd web/frontend
npm install
npm run build:mobile          # produces ./out
npx cap add ios               # scaffolds with SPM (CapApp-SPM), not CocoaPods
npx cap add android
npx @capacitor/assets generate --iconBackgroundColor '#0764a6' --iconBackgroundColorDark '#09111b'
npm run cap:sync
```

Icons/splash are generated from `assets/logo.png` (1024×1024, committed —
regenerate from the design source or `sips -z 1024 1024 public/icon-512.png
--out assets/logo.png`). The generator also touches `public/manifest.json` and
a stray `icons/` dir (PWA mode) — revert those, the site has its own icons.

### Xcode capabilities

Already wired in the committed project (`App/App.entitlements`, referenced via
`CODE_SIGN_ENTITLEMENTS` in both configs): **Push Notifications**
(`aps-environment`, auto-switched to `production` at distribution) and
**Associated Domains** (`applinks:ratslotse.de` — Universal Links for email
verify/reset links and push taps).

Android: drop `google-services.json` into `android/app/` (FCM).

### Fresh Mac / fresh Xcode (App Store install) — pitfalls

1. Activate Xcode and install its system resources, otherwise CoreSimulator
   registers no runtimes (`simctl list runtimes` empty, `actool` fails with
   `supportedRuntimes=[]`, and Xcode's GUI platform download dead-loops on a
   `Duplicate of <UUID>` error):
   ```bash
   sudo xcode-select -s /Applications/Xcode.app/Contents/Developer
   sudo xcodebuild -runFirstLaunch
   xcodebuild -downloadPlatform iOS      # simulator runtime, ~8.5 GB
   ```
2. Don't `simctl runtime delete` a *duplicate* runtime entry — both entries
   share one MobileAsset image, deleting the dupe purges the good one too.

### Build & run from the CLI (no Xcode GUI needed)

Build with a `-destination` (NOT bare `-sdk iphonesimulator` — that defaults to
an x86_64 slice, which runs under Rosetta in the simulator and **silently
disables remote push**; APNs in the simulator needs a native arm64 app):

```bash
cd web/frontend/ios/App
xcodebuild -project App.xcodeproj -scheme App -configuration Debug \
  -destination 'platform=iOS Simulator,name=Ratslotse iPhone 17' \
  -derivedDataPath build build
xcrun simctl boot "Ratslotse iPhone 17"   # once: simctl create "Ratslotse iPhone 17" \
                                          #   com.apple.CoreSimulator.SimDeviceType.iPhone-17 \
                                          #   com.apple.CoreSimulator.SimRuntime.iOS-26-5
xcrun simctl install booted build/Build/Products/Debug-iphonesimulator/App.app
xcrun simctl launch booted de.ratslotse.app
```

Simulator push (Apple-silicon Macs) works end-to-end: the team id is set in the
project (`DEVELOPMENT_TEAM`), `AppDelegate.swift` forwards the APNs token to the
Capacitor plugin (a required manual step per the plugin README), and the device
registers a *sandbox* token — delivered via the sender's gateway fallback.

### Release: TestFlight-Upload und Installation aufs eigene Gerät (CLI)

Beides ohne Xcode-GUI. Vorbedingung ist ein **App-Store-Connect-API-Key** unter
`~/.appstoreconnect/private_keys/AuthKey_<KEY_ID>.p8`; `xcodebuild` benutzt ihn
für Signier-Assets, `altool` für den Upload. Die **Issuer-ID** gehört zum Key
(App Store Connect → Benutzer & Zugriff → Integrationen) — sie steht auch in der
`Packaging.log` eines früheren Exports, falls sie verloren ging.

**Vorher die Build-Nummer erhöhen.** App Store Connect weist einen Upload ab,
dessen `CURRENT_PROJECT_VERSION` schon existiert; `MARKETING_VERSION` folgt dem
Changelog-Versionsschnitt.

```bash
cd web/frontend
# Dev-Server VORHER stoppen — er teilt sich .next mit dem Build, und ein
# paralleler Lauf hinterlässt ein kaputtes .next ("TypeError: e[o] is not a
# function"), das nur ein `rm -rf .next` wieder heilt.
npm run build:mobile && npm run cap:sync

cd ios/App
# ACHTUNG zsh: Die Flags NICHT in eine Variable packen und unquotiert einsetzen
# ($AUTH). zsh trennt unquotierte Expansionen — anders als bash — nicht in Wörter
# auf, xcodebuild bekommt dann alles als ein einziges Argument und bricht ab:
#   xcodebuild: error: invalid option '-allowProvisioningUpdates   -authent…'
# Entweder ein Array (AUTH=(-allowProvisioningUpdates …) und "${AUTH[@]}") oder,
# wie hier, die Flags ausschreiben.
AUTHKEY="$HOME/.appstoreconnect/private_keys/AuthKey_<KEY_ID>.p8"

xcodebuild -project App.xcodeproj -scheme App -configuration Release \
  -destination 'generic/platform=iOS' \
  -archivePath /tmp/rl-archive/App.xcarchive \
  -allowProvisioningUpdates \
  -authenticationKeyPath "$AUTHKEY" \
  -authenticationKeyID <KEY_ID> -authenticationKeyIssuerID <ISSUER_ID> \
  archive

xcodebuild -exportArchive -archivePath /tmp/rl-archive/App.xcarchive \
  -exportPath /tmp/rl-archive/ipa \
  -exportOptionsPlist ExportOptions.plist \
  -allowProvisioningUpdates \
  -authenticationKeyPath "$AUTHKEY" \
  -authenticationKeyID <KEY_ID> -authenticationKeyIssuerID <ISSUER_ID>
```

`ExportOptions.plist` liegt bewusst **nicht** im Repo (`.gitignore`) und wird
einmal lokal angelegt — `manageAppVersionAndBuildNumber` muss `false` bleiben,
sonst zählt Xcode die Build-Nummer eigenmächtig hoch und Projekt und App Store
Connect laufen auseinander:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>method</key><string>app-store-connect</string>
	<key>destination</key><string>export</string>
	<key>signingStyle</key><string>automatic</string>
	<key>teamID</key><string>YM87689GUY</string>
	<key>manageAppVersionAndBuildNumber</key><false/>
	<key>uploadSymbols</key><true/>
</dict>
</plist>
```

```bash
# Erst prüfen, dann hochladen — die Prüfung findet dieselben Fehler in 30 s
# statt nach dem Upload.
xcrun altool --validate-app -f /tmp/rl-archive/ipa/App.ipa -t ios \
  --apiKey <KEY_ID> --apiIssuer <ISSUER_ID>
xcrun altool --upload-app   -f /tmp/rl-archive/ipa/App.ipa -t ios \
  --apiKey <KEY_ID> --apiIssuer <ISSUER_ID>
```

Verarbeitung dauert ein paar Minuten. `altool` kann den Stand NICHT abfragen
(kein `--list-builds`); die ASC-API beantwortet
`GET /v1/builds?filter[app]=<APP_ID>&limit=5&sort=-uploadedDate` mit
`processingState` (`PROCESSING` → `VALID`). Dafür braucht es ein ES256-JWT aus
demselben `.p8` — `cryptography` genügt, PyJWT ist nicht nötig. Achtung: Das
Projekt-venv hat `cryptography` **nicht** (nichts in `requirements*.txt` zieht
es), also entweder ein Wegwerf-venv anlegen oder gezielt nachinstallieren —
nicht wundern, wenn der Import im `.venv` scheitert.

Ein frisch hochgeladener Build taucht in der Liste erst nach einigen Minuten
überhaupt auf; „nicht sichtbar" heißt also nicht „abgelehnt".

**Aufs eigene iPhone** braucht es keinen TestFlight-Umweg: Das **Archiv** trägt
noch die Entwickler-Signatur (erst der Export ersetzt sie durch die
Distributions-Signatur), also lässt sich sein App-Bundle direkt installieren.
Das Gerät darf dabei per WLAN gepaart sein — `xcrun xctrace list devices` führt
es dann irrelevanterweise unter „Offline", `devicectl` sieht es trotzdem:

```bash
xcrun devicectl list devices                      # Identifier ablesen
xcrun devicectl device install app --device <ID> \
  /tmp/rl-archive/App.xcarchive/Products/Applications/App.app
xcrun devicectl device info apps --device <ID> | grep ratslotse   # Version prüfen
```

Push funktioniert in beiden Varianten: Das Archiv registriert einen
*Sandbox*-Token, der TestFlight-Build einen *Produktions*-Token — der Sender
probiert beide Gateways.

## Push credentials (backend `.env`)

```
# iOS — Apple push (token-based .p8, no Firebase)
# Key OUTSIDE ~/app (e.g. /home/<user>/secrets/) — the deploy rsync --delete would
# remove anything under ~/app that isn't in the repo/excludes.
APNS_KEY_P8=/home/<user>/secrets/AuthKey_XXXX.p8   # or the PEM contents inline
APNS_KEY_ID=XXXXXXXXXX
APNS_TEAM_ID=YYYYYYYYYY
APNS_TOPIC=de.ratslotse.app
# APNS_USE_SANDBOX=1   # optional: try the sandbox gateway first. Not required —
#                      # on BadDeviceToken the sender retries the other gateway,
#                      # so Xcode debug builds (sandbox tokens) and TestFlight/
#                      # App Store builds (production tokens) coexist automatically.
# Android — FCM v1
FCM_PROJECT_ID=ratslotse-xxxxx
FCM_CREDENTIALS=/path/service-account.json
```

## Deep links

Fill in the placeholders and deploy (the files live in `public/.well-known/`):

- `apple-app-site-association.json` — your Apple **Team ID**. Apple fetches the
  extensionless URL; a Next rewrite serves the `.json` file there with the
  required `application/json` content type — no webserver config needed. Verify:
  `curl -sI https://ratslotse.de/.well-known/apple-app-site-association`.
- `assetlinks.json` — the Android signing-cert **SHA-256 fingerprint**
  (`cd android && ./gradlew signingReport`, or from the Play Console under
  App-Integrität when Play App Signing is on).

## Run / release

```bash
npm run build:mobile && npm run cap:sync
npm run cap:ios       # opens Xcode  → run on simulator / Archive → App Store
npm run cap:android   # opens Android Studio → run on emulator / build AAB → Play
```

Notes for review/submission:

- Account deletion is available in-app (Einstellungen → Konto löschen) — an App
  Store requirement for apps with registration.
- Android push routes through FCM (Google as processor) — worth a line on the
  Datenschutz page; iOS via APNs stays with Apple.

## App-Store-Einreichung (Checkliste)

Im Repo bereits erledigt:

- `PrivacyInfo.xcprivacy` (Pflicht seit 2024): E-Mail, Nutzerinhalte (Themen),
  Push-Geräte-Token — je „App-Funktionalität", verknüpft, kein Tracking; dazu
  UserDefaults **CA92.1** (Capacitor Preferences speichert das Bearer-Token).
  Die Capacitor-Core-Pakete bringen eigene Manifeste mit; `@capacitor/preferences`
  nicht — daher die Deklaration hier.
- `ITSAppUsesNonExemptEncryption = false` (nur Standard-HTTPS) — keine
  Export-Compliance-Rückfrage bei jedem Upload.
- Build mit **Xcode 26** (seit 28.04.2026 Pflicht für Neueinreichungen/Updates).

In App Store Connect vor der ersten Einreichung (manuell):

1. **EU-DSA-Trader-Status** deklarieren (Pflicht; ohne Deklaration keine
   Einreichung). Nicht-kommerzielles Privatprojekt → „Non-Trader" plausibel.
2. **Privacy Nutrition Labels** — muss zum Manifest passen: E-Mail,
   Nutzerinhalte, Geräte-ID (Push-Token); „Daten werden nicht zum Tracking
   verwendet".
3. **Demo-Konto** in den App-Review-Informationen hinterlegen (App ist
   login-pflichtig — Guideline 2.1; häufigster Rejection-Grund).
4. **Screenshots**: nur iPhone — die App ist iPhone-only
   (`TARGETED_DEVICE_FAMILY = 1`; auf dem iPad läuft sie im
   Kompatibilitätsmodus, ohne iPad-Screenshot-Pflicht).
5. Altersfreigabe-Fragebogen (läuft auf 4+ hinaus), Support-URL
   (https://ratslotse.de), Datenschutz-URL (https://ratslotse.de/datenschutz).
6. In den Review-Notes die nativen Mehrwerte nennen (Push-Themen-Alerts,
   Universal Links) — beugt einer 4.2-„Webseiten-Wrapper"-Rückfrage vor.
7. **Abgrenzung zur Stadt** (Guideline 5.2): Die App trägt einen amtlich
   klingenden Namen und zeigt fast ausschließlich Dokumente der Stadt — ohne
   Klarstellung liest Apple das als Angebot einer Behörde, die die App gar nicht
   eingereicht hat (5.2.1: Dienste einer Einrichtung darf nur diese Einrichtung
   selbst anbieten; sonst braucht es eine deutliche Distanzierung). Der Satz steht
   in der App (Anmeldung, Registrierung, Konto-Fuß, Impressum) **und** muss als
   **erste Zeile der Store-Beschreibung** stehen — wörtlich:

   > Ratslotse ist ein privates Bürgerprojekt und kein Angebot der Stadt
   > Oldenburg — es besteht keine Verbindung zur Stadtverwaltung oder zum
   > Stadtrat.

   Danach erst der Werbetext. Der Untertitel („Subtitle", max. 30 Zeichen) darf
   nichts Amtliches behaupten; passend ist **„Stadtrat Oldenburg verstehen"**
   (28 Zeichen). Bei der Frage nach dem Government-Entity-Status in App Store
   Connect: **nein** — Einreicher ist eine Privatperson.
