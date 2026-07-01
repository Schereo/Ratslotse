# Ratslotse mobile apps (Capacitor)

The iOS/Android apps are the **same Next.js frontend**, statically exported and
wrapped in a Capacitor native shell. They talk to the existing FastAPI backend at
an absolute origin with a **bearer token** (see `lib/platform.ts`, `lib/token.ts`),
so no cookies/proxy are involved. Native **push** is a delivery channel alongside
email/Telegram.

## What's already wired in the repo

- **Auth:** app sends `X-Client: app`; backend returns a long-lived JWT which the
  app stores in secure storage (`@capacitor/preferences`) and sends as a bearer.
- **API base:** `""` (same-origin) on web, `https://ratslotse.de` in the app.
- **Static export:** `MOBILE=1 next build` → `./out` (via `npm run build:mobile`,
  which also removes the web-only SSE route handler and injects the app CSP).
- **Routing:** council detail views use query-param routes so the export needs no
  dynamic-route enumeration.
- **Push:** `lib/push.ts` (permission + token registration + tap-to-navigate);
  `POST /api/push/register`; backend sends via APNs/FCM (`nwz/push.py`).
- **Capacitor:** `capacitor.config.ts`, deps + scripts in `package.json`.

## One-time setup (on the Mac)

```bash
cd web/frontend
npm install
npm run build:mobile          # produces ./out
npx cap add ios
npx cap add android
npx @capacitor/assets generate --iconBackgroundColor '#2563eb' --iconBackgroundColorDark '#0b1220'
npm run cap:sync
```

Icons/splash are generated from `public/icon-512.png`.

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

Xcode: enable the **Push Notifications** capability. Android: drop
`google-services.json` into `android/app/`.

## Backend CORS

Add the app origins so cross-origin fetches (incl. the Q&A SSE stream) are allowed:

```
CORS_ORIGINS=https://ratslotse.de,capacitor://localhost,https://localhost
```

## Deep links

`public/.well-known/apple-app-site-association` and `assetlinks.json` are templates
— fill in your Apple Team ID and the Android signing-cert SHA-256, and make sure
Caddy serves the AASA file as `application/json`. Then verify/reset-email links and
push taps open the app (handled in `lib/push.ts` + the app's `appUrlOpen`).

## Run / release

```bash
npm run build:mobile && npm run cap:sync
npm run cap:ios       # opens Xcode  → run on simulator / Archive → App Store
npm run cap:android   # opens Android Studio → run on emulator / build AAB → Play
```
