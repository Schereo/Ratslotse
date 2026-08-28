# Ratslotse auf mobilen Geräten

Die primäre iOS-App ist seit Version 2.0 eine echte SwiftUI-App. Quellcode,
Build-, Test- und Release-Anleitung stehen in
[`../../ios/README.md`](../../ios/README.md). Sie unterstützt iPhone und iPad,
Sign in with Apple, APNs, Universal Links, Keychain, MapKit und EventKit und
spricht direkt mit der FastAPI.

## Übergangsstand

Die bisherige Capacitor-8-Ausgabe bleibt bis zum abgeschlossenen
TestFlight-Vergleich unter `web/frontend/ios/` baubar. Sie ist ein statischer
Next-Export in einer WebView, nutzt `X-Client: app` und speichert das
Bearer-Token in Capacitor Preferences. Die neue SwiftUI-App übernimmt dieses
Token beim ersten Start in den Keychain.

```bash
cd web/frontend
npm install
npm run build:mobile
npm run cap:sync
npm run cap:ios       # Legacy-iOS in Xcode öffnen
npm run cap:android   # unveröffentlichtes Android-Gerüst öffnen
```

Der Legacy-Build wird nicht mehr als Ausgangspunkt für neue iOS-Funktionen
verwendet. Er bleibt als Rollback-Möglichkeit erhalten, bis der native Build
unter derselben App-Store-ID `6786553049` freigegeben ist.

## Gemeinsame produktive Voraussetzungen

- Bundle-ID: `de.ratslotse.app`
- Apple-Team: `YM87689GUY`
- Associated Domain: `applinks:ratslotse.de`
- Capabilities: Push Notifications, Sign in with Apple, Associated Domains
- Backend-APNs-Topic: `de.ratslotse.app`
- Universal-Link-Pfade: `/verify-email`, `/reset-password`, `/dashboard`,
  `/fragen`, `/fragen/*`, `/g`, `/topics` und `/council*`

Die Server-Zugangsdaten bleiben außerhalb des Deploy-Verzeichnisses:

```dotenv
APNS_KEY_P8=/home/<user>/secrets/AuthKey_XXXX.p8
APNS_KEY_ID=XXXXXXXXXX
APNS_TEAM_ID=YYYYYYYYYY
APNS_TOPIC=de.ratslotse.app
```

`APNS_USE_SANDBOX=1` ist optional. Der Sender probiert bei einem
`BadDeviceToken` automatisch das andere Gateway, sodass Debug- und
TestFlight-Geräte parallel funktionieren.

## App-Store-Checkliste

Die vorbereiteten Texte und Feldwerte stehen in [`STORE.md`](STORE.md). Vor
der Einreichung insbesondere prüfen:

1. Build-Nummer ist größer als der letzte Upload (native Linie beginnt mit
   Marketing-Version 2.0.0, Build 18).
2. EU-DSA-Trader-Status und Privacy Nutrition Labels sind vollständig.
3. Demo-Konto und Review-Hinweise sind aktuell.
4. Neue Screenshots für iPhone und iPad sind hochgeladen.
5. Altersfreigabe, Support-URL und Datenschutz-URL sind bestätigt.
6. `/api/council/ask` wird für native Requests direkt zu FastAPI geroutet.

Nach der Freigabe werden Capacitor, die JS-Brücken und das Android-Gerüst in
einem separaten Aufräum-PR entfernt. Web-only bleiben Admin, Landingpage,
Changelog, Dokumentation und `/g`-Share-Snapshots.
