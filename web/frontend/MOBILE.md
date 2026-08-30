# Ratslotse auf mobilen Geräten

Die primäre iOS-App ist seit Version 2.0 eine echte SwiftUI-App. Quellcode,
Build-, Test- und Release-Anleitung stehen in
[`../../ios/README.md`](../../ios/README.md). Sie unterstützt iPhone und iPad,
Sign in with Apple, APNs, Universal Links, Keychain, MapKit und EventKit und
spricht direkt mit der FastAPI.

Der Lotti-Erststart ist ebenfalls nativ umgesetzt: Begrüßung vor der
Anmeldung, anschließend Gremien, Themen und Push. Der Fortschritt wird lokal
und über `/api/onboarding/setup` am Konto fortgesetzt.

## Plattformstand

Für iOS existiert ausschließlich die native SwiftUI-App unter `../../ios/`.
Das frühere Capacitor/Xcode-Projekt wurde nach dem Paritätsabgleich entfernt.
Das unveröffentlichte Android-Gerüst bleibt vorerst als statischer Next-Export
in einer WebView erhalten.

```bash
cd web/frontend
npm install
npm run build:mobile
npm run cap:sync
npm run cap:android   # unveröffentlichtes Android-Gerüst öffnen
```

Neue iOS-Funktionen und iOS-Releases werden nur noch aus `ios/` gebaut.

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

Wenn das unveröffentlichte Android-Gerüst später ebenfalls entfällt, können
der verbleibende Capacitor-Sonderbuild und die JS-Brücken separat entfernt
werden. Web-only bleiben Landingpage, Changelog, Dokumentation und
`/g`-Share-Snapshots.
