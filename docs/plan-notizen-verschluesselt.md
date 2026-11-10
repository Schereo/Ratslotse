# Plan: Notizen und Mitschrieb, auf dem Gerät verschlüsselt

Stand 10.11.2026. Schritt 7 aus [`plan-sitzungsseite-kurs.md`](plan-sitzungsseite-kurs.md):
eigener Plan vor dem Bau. Gebaut wird erst nach Tims Abnahme — und nach seiner
Antwort auf die offene Frage 8.3 (Mitschrieb).

## 1. Was es geben soll

- **Meine Notiz** auf der Punkt-Seite und am Beschluss: ein freier Text, den
  nur die Person selbst lesen kann (Entwurf `punkt-desktop-2.png`, rechts unten:
  „Wird auf deinem Gerät verschlüsselt, bevor sie gespeichert wird. Ratslotse
  sieht nur den verschlüsselten Text.“).
- **Mein Mitschrieb** beim Mitlesen: je Punkt „Was ist passiert?“ (Angenommen,
  Abgelehnt, Vertagt, Zur Kenntnis) und ein Text (Entwurf
  `mitlesen-desktop-zustand-mitschrieb.png`). Ausdrücklich „nur für dich und
  nicht das amtliche Ergebnis“ — die eigene Einschätzung färbt die Boje im
  eigenen Kurs, nie die öffentliche Seite.

Beides nur mit Konto, beides synchron zwischen Geräten.

## 2. Was feststeht (aus dem Hauptplan)

- Notizen werden **auf dem Gerät** verschlüsselt; der Server speichert nur den
  verschlüsselten Text.
- Der Schlüssel entsteht auf dem Gerät und wird mit einer **eigenen
  Notiz-Passphrase** und einem **Wiederherstellungscode** verpackt. Das
  Anmeldepasswort taugt nicht: Es geht an den Server, und Konten mit „Mit Apple
  anmelden“ haben keins.

## 3. Aufbau

### Schlüssel

| Was | Wie | Wo |
|---|---|---|
| Datenschlüssel `DK` | AES-256-GCM, zufällig erzeugt beim Einrichten | nur auf dem Gerät, nie im Klartext beim Server |
| Passphrasen-Schlüssel `KEK_p` | PBKDF2-SHA-256, 600.000 Runden, 16 Byte Salz (WebCrypto kennt kein Argon2; die App nimmt dieselbe Ableitung, damit beide dieselben Daten lesen) | wird nie gespeichert |
| Wiederherstellungsschlüssel `KEK_r` | 128 Bit Zufall, gezeigt als Code in 8 Gruppen zu 4 Zeichen (Crockford-Base32), einmal beim Einrichten | nur bei der Person (ausdrucken, aufschreiben) |
| Beim Server | `wrap(DK, KEK_p)`, `wrap(DK, KEK_r)`, Salz, Runden, Version | Tabelle `note_keys` |

Entsperren heißt: Passphrase → `KEK_p` → `DK` auspacken. Im Web bleibt `DK`
als **nicht exportierbarer** `CryptoKey` für die Sitzung im Speicher (auf
Wunsch in IndexedDB, „auf diesem Gerät merken“); in der App in der Keychain
(`kSecAttrAccessibleWhenUnlockedThisDeviceOnly`), optional hinter Face ID.

### Daten

Tabelle `user_notes` in `ratslotse.sqlite` (Konten-Datenbank, nicht die
Ratsdaten):

```
id, owner_id, target_kind ('agenda_item' | 'decision'), target_key,
kind ('note' | 'transcript'), iv, ciphertext, key_version, version,
created_at, updated_at
UNIQUE(owner_id, target_kind, target_key, kind)
```

`target_key` ist `ksinr|Nummer` bzw. die Beschluss-Kennung. Der Klartext ist
ein JSON-Dokument (`{ "text": … }`, beim Mitschrieb zusätzlich
`"outcome": …`) — der Server kennt nicht einmal die Felder. Beide Tabellen
kommen in `USER_OWNED_TABLES` (`kern/store.py`), sonst bliebe nach der
Konto-Löschung ein verschlüsselter Rest stehen.

### Endpunkte (alle `require_active`)

- `GET/PUT /notes/keys` — die verpackten Schlüssel; PUT nur beim Einrichten
  und beim Wechsel der Passphrase (dann wird nur `wrap(DK, KEK_p)` ersetzt,
  die Notizen bleiben, wie sie sind).
- `GET /notes?target_kind=&target_key=` — eine oder alle Notizen einer Seite.
- `PUT /notes/{target_kind}/{target_key}/{kind}` mit `version` — wer eine
  ältere Version schickt, bekommt 409 und den neuen Stand (zwei Geräte, eine
  Notiz: der Client fragt, statt still zu überschreiben).
- `DELETE …` und `GET /notes/export` (verschlüsselt; entschlüsselt wird im
  Browser, die Datei entsteht dort).

Grenzen: höchstens 16 KB je verschlüsseltem Text, 2.000 Notizen je Konto,
Rate-Limit je Konto wie bei den Merklisten.

## 4. Was man dazu sagen muss — auf der Seite, nicht im Kleingedruckten

1. **Wer Passphrase und Wiederherstellungscode verliert, verliert die
   Notizen.** Ratslotse kann sie nicht zurückholen. Das steht beim Einrichten,
   vor dem ersten Speichern, und der Code muss einmal abgetippt werden.
2. **Der Server kann nicht in ihnen suchen.** Suche geht nur auf dem Gerät,
   über die entschlüsselten Notizen.
3. **„Frag den Rat“ kennt sie nicht.** Keine Notiz geht an ein Sprachmodell.
4. **Im Web ist das Versprechen schwächer als in der App.** Den Code, der
   verschlüsselt, liefert im Browser derselbe Server, der die Daten speichert;
   ein manipulierter Server könnte ihn austauschen. Die App bringt ihren Code
   aus dem Store mit. Der Hinweis im Web sagt das in einem Satz.
5. **Was der Server trotzdem sieht:** zu welchem Punkt es eine Notiz gibt,
   wann sie geändert wurde und wie lang sie ungefähr ist. Das steht in der
   Datenschutzerklärung.

## 5. Mitschrieb vor Schritt 7? (Frage 8.3)

Zwei Wege, Tim entscheidet:

- **A — warten:** Der Mitschrieb kommt mit den verschlüsselten Notizen. Bis
  dahin gibt es beim Mitlesen keinen.
- **B — vorher nur im Browser:** Mitschrieb im `localStorage`, unverschlüsselt,
  ohne Konto, ohne Synchronisation, mit dem Hinweis „bleibt nur in diesem
  Browser“. Beim Einrichten der Notizen bietet die Seite an, ihn zu
  übernehmen. Schnell gebaut, aber ein zweiter Speicherort, der später
  aufgeräumt werden muss.

Empfehlung: **A**. Ein Mitschrieb, der beim Gerätewechsel weg ist, enttäuscht
genau die Leute, die ihn am meisten nutzen würden (Ratsmitglieder, Presse).

## 6. Prüfen

- **vitest** (Node 24 hat WebCrypto): Einpacken/Auspacken mit festen
  Testvektoren, falsche Passphrase scheitert sauber, Wiederherstellung über
  den Code, Passphrasen-Wechsel lässt alte Notizen lesbar.
- **pytest:** Der Server speichert und liefert nur Blobs; Größen- und
  Versionsprüfung; Konto-Löschung räumt beide Tabellen ab; ein Wächter, der in
  `ratslotse.sqlite` nach Klartext-Mustern in `ciphertext` sucht (es darf
  keine geben).
- **Browsertest:** Einrichten, Notiz schreiben, neu laden (gesperrt), mit
  Passphrase entsperren, Notiz lesen; ein zweiter Kontext mit falscher
  Passphrase sieht nichts.
- **App:** dieselben Testvektoren in Swift (CryptoKit), damit Web und App
  dieselben Daten lesen — ohne das ist die Synchronisation eine Behauptung.

## 7. Reihenfolge

1. Krypto-Modul mit Testvektoren (Web), Endpunkte, Tabellen, Löschung.
2. „Meine Notiz“ auf Punkt- und Beschluss-Seite (Schalter `notizen`).
3. Mitschrieb beim Mitlesen (nach 8.3).
4. App (eigener Plan, `ios/CLAUDE.md`).

## 8. Offene Fragen an Tim

1. Frage 8.3: Mitschrieb nach Weg A oder B?
2. Notizen auch an Sitzungen und Themen, oder erst nur an Punkten und
   Beschlüssen?
3. „Auf diesem Gerät merken“ im Web anbieten (bequem, aber der Schlüssel liegt
   dann im Browser), oder jedes Mal die Passphrase?
