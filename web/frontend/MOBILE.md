# Ratslotse mobile apps (Capacitor)

The iOS/Android apps are the **same Next.js frontend**, statically exported and
wrapped in a Capacitor 8 native shell. They talk to the existing FastAPI backend
at an absolute origin with a **bearer token** (see `lib/platform.ts`,
`lib/token.ts`), so no cookies/proxy are involved. Native **push** is a delivery
channel alongside email/Telegram.

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
  (`nwz/push.py`) and prunes device tokens the gateways report as gone.
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
npx @capacitor/assets generate --iconBackgroundColor '#2563eb' --iconBackgroundColorDark '#0b1220'
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

```bash
cd web/frontend/ios/App
xcodebuild -project App.xcodeproj -scheme App -configuration Debug \
  -sdk iphonesimulator -derivedDataPath build build
xcrun simctl boot "Ratslotse iPhone 17"   # once: simctl create "Ratslotse iPhone 17" \
                                          #   com.apple.CoreSimulator.SimDeviceType.iPhone-17 \
                                          #   com.apple.CoreSimulator.SimRuntime.iOS-26-5
xcrun simctl install booted build/Build/Products/Debug-iphonesimulator/App.app
xcrun simctl launch booted de.ratslotse.app
```

## Push credentials (backend `.env`)

```
# iOS — Apple push (token-based .p8, no Firebase)
APNS_KEY_P8=/path/AuthKey_XXXX.p8     # or the PEM contents inline
APNS_KEY_ID=XXXXXXXXXX
APNS_TEAM_ID=YYYYYYYYYY
APNS_TOPIC=de.ratslotse.app
# APNS_USE_SANDBOX=1                   # for dev/TestFlight debug builds
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
