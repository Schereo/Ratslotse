# Ratslotse für iOS

Die App in diesem Verzeichnis ist die native SwiftUI-Ausgabe von Ratslotse. Sie
läuft auf iPhone und iPad ab iOS 17 und spricht ohne WebView direkt mit der
FastAPI unter `https://ratslotse.de`.

## Architektur

- `RatslotseAPI`: `URLSession`-Client, Codable-Modelle, Bearer-Token im
  Keychain, Capacitor-Tokenmigration, SSE und Universal-Link-Router.
- `RatslotseDesign`: Farben, Typografie und wiederverwendbare SwiftUI-
  Komponenten aus der Web-Designsprache.
- `RatslotseFeatures`: Lotti-Onboarding, Auth, Heute, Ratsgespräch, Deep
  Research, Ratssuche, öffentliche Detailseiten, Themen, Quiz und Konto.
- `RatslotseApp`: App-Lebenszyklus, APNs, Universal Links und Root-View.

Der Release-Build verwendet weiterhin die bestehende Bundle-ID
`de.ratslotse.app`. Debug verwendet `de.ratslotse.dev`, damit Entwicklungs-
und Release-Build getrennt installiert werden können. Die Entitlements
enthalten Push, Sign in with Apple und
`applinks:ratslotse.de`; Build 18 beginnt die native 2.0-Linie.

## Projekt erzeugen und testen

Das Xcode-Projekt wird mit [XcodeGen](https://github.com/yonaskolb/XcodeGen)
aus `project.yml` erzeugt. Die generierte Projektdatei ist eingecheckt, damit
die App auch ohne XcodeGen sofort in Xcode geöffnet werden kann.

```bash
brew install xcodegen                 # einmalig
xcodegen generate --spec ios/project.yml
swift test --package-path ios/Packages/RatslotseAPI
xcodebuild -project ios/Ratslotse.xcodeproj -scheme Ratslotse \
  -configuration Debug \
  -destination 'platform=iOS Simulator,name=Ratslotse iPhone 17' \
  CODE_SIGNING_ALLOWED=NO build
```

Ein anderer installierter Simulator lässt sich mit
`xcrun simctl list devices available` ermitteln. Der CI-Workflow
`.github/workflows/ios.yml` erzeugt das Projekt neu, führt die Paket- und
App-Tests aus und baut zusätzlich gegen ein generisches iOS-Simulatorziel.

## Authentifizierung und Migration

Native Requests tragen immer `X-Client: app`; angemeldete Requests zusätzlich
`Authorization: Bearer …`. Das Token liegt mit
`kSecAttrAccessibleAfterFirstUnlock` im Keychain. Beim ersten Start wird ein
vorhandenes Capacitor-Token aus `CapacitorStorage.access_token` übernommen und
anschließend aus `UserDefaults` entfernt. `/api/auth/me` erneuert das Token bei
jedem erfolgreichen Bootstrap.

Passwort-Reset und Passwortwechsel liefern dem nativen Client ebenfalls ein
neues Token. Der öffentliche Endpoint `/api/app-config` kann über
`APP_MIN_BUILD` alte Store-Builds sperren und mit `APP_UPDATE_NOTICE` einen
Hinweis anzeigen.

## Erststart mit Lotti

Der native Erststart übernimmt den Einrichtungsablauf der bisherigen App:
dunkler Lotti-Auftakt vor der Anmeldung, danach drei jederzeit überspringbare
Schritte für Gremien-Abos, automatisch beschriebene Themen und Push. Der
erreichte Schritt liegt in `UserDefaults` und zusätzlich unter
`/api/onboarding/setup` am Konto. Dadurch wird eine unterbrochene Einrichtung
nach App-Neustart, Gerätewechsel oder Neuinstallation fortgesetzt; ein bereits
abgeschlossener WebView-Erststart wird über den Kontostand nicht wiederholt.
Unter „Konto“ lässt sich der Ablauf bewusst erneut öffnen.

## Streaming und produktiver Proxy

Das Ratsgespräch nutzt einen nativen POST-SSE-Client. Er verarbeitet
Keepalives, mehrzeilige Daten sowie `replace`, `abbruch` und `error`. Deep
Research reconnectet mit dem letzten Event-Index und fällt bei HTTP 410 auf
den Snapshot-Endpoint zurück.

Vor einem TestFlight-Cutover muss der produktive Reverse Proxy geprüft werden:
Requests an `/api/council/ask` mit `X-Client: app` sollen direkt an FastAPI
gehen und nicht über den Next-Route-Handler. Die Caddy-/Ingress-Konfiguration
liegt nicht in diesem Repository; diese Prüfung ist daher ein Deployment-Gate.

## Release

Vor jedem Upload `CURRENT_PROJECT_VERSION` in `project.yml` erhöhen und das
Projekt neu erzeugen. Archiv und Export funktionieren ohne einen Frontend-
Build:

```bash
xcodegen generate --spec ios/project.yml
xcodebuild -project ios/Ratslotse.xcodeproj -scheme Ratslotse \
  -configuration Release -destination 'generic/platform=iOS' \
  -archivePath /tmp/ratslotse/Ratslotse.xcarchive \
  -allowProvisioningUpdates \
  -authenticationKeyPath "$HOME/.appstoreconnect/private_keys/AuthKey_<KEY_ID>.p8" \
  -authenticationKeyID <KEY_ID> -authenticationKeyIssuerID <ISSUER_ID> archive

xcodebuild -exportArchive \
  -archivePath /tmp/ratslotse/Ratslotse.xcarchive \
  -exportPath /tmp/ratslotse/ipa \
  -exportOptionsPlist ExportOptions.plist \
  -allowProvisioningUpdates \
  -authenticationKeyPath "$HOME/.appstoreconnect/private_keys/AuthKey_<KEY_ID>.p8" \
  -authenticationKeyID <KEY_ID> -authenticationKeyIssuerID <ISSUER_ID>
```

`ExportOptions.plist` bleibt lokal und verwendet die Team-ID `YM87689GUY`,
`method = app-store-connect`, `signingStyle = automatic` und
`manageAppVersionAndBuildNumber = false`. Das IPA anschließend zuerst mit
`xcrun altool --validate-app` prüfen und danach mit `--upload-app` hochladen.

## Plattformstand

Die frühere Capacitor/WebView-Ausgabe für iOS wurde nach dem Paritätsabgleich
entfernt. Unter iOS wird ausschließlich dieses SwiftUI-Projekt gebaut. Das
unveröffentlichte Android-Gerüst bleibt separat unter `web/frontend/android`.
Landingpage, Changelog, Doku und geteilte `/g`-Snapshots bleiben bewusst im
Web.
