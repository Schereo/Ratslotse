# Plan: Notizen und Mitschrieb in der App

Stand 10.11.2026. Reihenfolge 4 aus
[`plan-notizen-verschluesselt.md`](plan-notizen-verschluesselt.md) („App, eigener
Plan“). Web und Server stehen (Schalter `notizen` und `mitschrieb`); dieser Plan
sagt, wie die App **dieselben** Daten liest und schreibt. Gebaut wird nach
Tims Abnahme.

## 1. Was die App können soll

- **Meine Notiz** an Beschluss und Tagesordnungspunkt — dieselbe Notiz wie im
  Web, auf jedem Gerät lesbar.
- **Einrichten, Entsperren, Wiederherstellen** wie im Web; zusätzlich der
  Schlüssel in der Keychain, auf Wunsch hinter Face ID.
- **Mitschrieb** erst, wenn die App ein Mitlesen hat (heute nicht) — bis dahin
  zeigt sie einen Mitschrieb aus dem Web am Punkt nur an.

## 2. Krypto — dieselben Bytes wie im Web

Das Web rechnet mit WebCrypto (`web/frontend/lib/notiz-krypto.ts`). CryptoKit
allein reicht nicht; was fehlt, kommt aus CommonCrypto (beides im System, kein
fremdes Paket):

| Schritt | Web | App |
|---|---|---|
| Passphrase → `KEK_p` | PBKDF2-SHA-256, 600.000 Runden, 16 Byte Salz | `CCKeyDerivationPBKDF` (CommonCrypto) |
| Code → `KEK_r` | HKDF-SHA-256, Info `ratslotse-notizen-wiederherstellung` | `HKDF<SHA256>.deriveKey` (CryptoKit) |
| DK verpacken | AES-KW (RFC 3394) | `CCSymmetricKeyWrap` / `CCSymmetricKeyUnwrap` |
| Notiz | AES-256-GCM, 12-Byte-IV, Zusatzdaten `art|schlüssel|kind` | `AES.GCM.seal(…, authenticating:)` |
| Code | Crockford-Base32, 8 × 4 Zeichen, 160 Bit | dieselbe Tabelle, eigene kleine Funktion |

**Die Testvektoren sind der Vertrag.** In `notiz-krypto.test.ts` stehen DK,
Salz, Code, IV und die erwarteten Verpackungen und Geheimtexte; dieselben
Zahlen kommen in `RatslotseAPITests` und laufen ohne Simulator (`swift test`
im Paket). Ohne diesen Test wäre „Web und App lesen dieselben Daten“ eine
Behauptung. Dazu RFC 3394 § 4.6 und RFC 7914 § 11 wie im Web.

## 3. Wo was liegt

- **`RatslotseAPI`**: `NotesCrypto.swift` (die Tabelle oben), Modelle
  `NoteKeysState`, `NoteEntry`, `NoteList` von Hand (danach
  `python scripts/ios_vertrag.py`), Aufrufe im `APIClient`. Keine
  Simulator-Abhängigkeit — deshalb testbar.
- **Keychain**: der entsperrte DK als `kSecClassKey`/generisches Passwort mit
  `kSecAttrAccessibleWhenUnlockedThisDeviceOnly`, mit Face ID über
  `SecAccessControl(.biometryCurrentSet)`. Nie in iCloud, nie im Backup.
  Abmelden und Konto-Löschen räumen ihn (wie `LocalAccountData`).
- **`RatslotseFeatures`**: `NoteCard` (SwiftUI) mit denselben vier Zuständen
  wie im Web; auf `DecisionDetail` und — sobald es sie gibt — der Punkt-Ansicht.
  Sichtbar nur mit `features.contains("notizen")` aus `/api/app-config`.
- **XcodeGen**: nur für neue Dateien unter `RatslotseApp/`; die Pakete
  brauchen es nicht (`ios/CLAUDE.md`).

## 4. Was man dazu sagen muss

Dieselben Sätze wie im Web (`plan-notizen-verschluesselt.md` § 4) — mit einer
Ausnahme: Der Hinweis „im Browser kommt der Code vom selben Server“ entfällt in
der App, denn ihr Code kommt aus dem Store. Das ist der Grund, warum die App
für Notizen das stärkere Versprechen ist.

## 5. Prüfen

1. `swift test` in `RatslotseAPI`: RFC-Vektoren, die Web-Vektoren, falsche
   Passphrase, falscher Code, Passphrasen-Wechsel.
2. Gegenprobe über Kreuz: im Web eine Notiz schreiben, in der App lesen — und
   umgekehrt — auf dev, mit demselben Konto.
3. `python scripts/ios_vertrag.py` für die neuen Modelle.
4. Simulator: Einrichten, Sperren, Face ID abbrechen (dann Passphrase), App
   neu starten (gesperrt oder Face ID, je nach Wahl).

## 6. Reihenfolge

1. `NotesCrypto` mit Tests (ohne Oberfläche).
2. Modelle, Client, Keychain.
3. `NoteCard` an `DecisionDetail`, Schalter `notizen`.
4. Anzeige des Mitschriebs am Punkt; Schreiben erst mit einem Mitlesen in der App.

## 7. Offene Fragen an Tim

1. Face ID als Vorgabe an, oder erst auf Wunsch?
2. Soll die App einen Mitschrieb anzeigen, bevor sie selbst mitlesen kann?
3. Gehört ein App-Mitlesen in den nächsten Release-Plan?
