# Plan: E-Mail-Adresse ändern

Anlass: Feature-Vorschlag aus dem Feedback-Postfach (09.09.2026): „E-Mail-Adresse
ändern". Heute gibt es dafür keinen Weg — wer die Adresse wechseln will, muss
das Konto löschen und neu anlegen (Themen, Merkliste, Abzeichen weg).

Dieser Plan ist so geschrieben, dass ein Agent ihn ohne weiteres Nachfragen
umsetzen kann. Er nennt je Schritt die Dateien, die Entscheidungen samt Grund
und die Randfälle mit dem Ort, an dem sie abgefangen werden. Ein Branch, ein
PR mit `--base dev`, Squash-Merge, Changelog-Fragment (s. Wurzel-`CLAUDE.md`).

## 1. Was heute da ist (gemessen am 09.09.2026)

| Baustein | Wo | Für den Plan wichtig |
|---|---|---|
| Konto | `web_users` in `kern/store.py` (~Z. 168) | `email TEXT NOT NULL UNIQUE`, immer `lower().strip()` gespeichert; `email_verified`, `status ∈ {pending, active}`, `apple_sub`, `password_set`, `token_version` |
| Bestätigungs-Tokens | `email_verification_tokens` (~Z. 239), `create_email_verification` / `consume_email_verification` (~Z. 2625) | sha256-Hash, einmalig, Ablauf; **ein Token je Konto** — ein neuer löscht den alten |
| Bestätigen | `POST /api/auth/verify-email` in `web/backend/app/routers/auth.py` (~Z. 396) | öffentlich (`OEFFENTLICH` in `tests/test_endpunkt_schutz.py`), gibt App-Clients ein Bearer-Token zurück |
| Erneut senden | `POST /api/auth/resend-verification` (~Z. 429) | `get_current_user`, no-op für bestätigte Konten, `verify_email_limiter` |
| Sitzung | `web/backend/app/security.py::create_access_token` | JWT trägt nur `sub` + `ver`, **keine Adresse** → ein Adresswechsel braucht keine neue Anmeldung |
| Re-Auth-Muster | `DELETE /api/account` in `routers/account.py` (~Z. 184) | Passwort **oder** frisches Apple-Identity-Token (Apple-only-Konten, `password_set = 0`) |
| Web-Seite | `web/frontend/app/verify-email/page.tsx` | ruft `verify-email`, dann `refresh()`, springt nach `/dashboard` |
| Web-Konto | `web/frontend/app/(app)/account/page.tsx` | zwei Spalten; rechts `DisplayNameCard`, `AppearanceCard`, Passwort-Karte, Löschen |
| Unbestätigt-Banner Web | `web/frontend/app/(app)/layout.tsx` (ruft `resend-verification`) | hier fehlt ein Ausweg bei Tippfehler |
| iOS-Routing | `ios/Packages/RatslotseAPI/Sources/RatslotseAPI/AppRoute.swift` | `/verify-email?token=` → `.verifyEmail`; **jeder unbekannte Pfad → `.web(url)`, also Safari** |
| iOS-Konto | `ios/Packages/RatslotseFeatures/Sources/RatslotseFeatures/TopicsAndAccountViews.swift` | `ChangePasswordView` (~Z. 925), `DeleteAccountView` mit Apple-Re-Auth (~Z. 959–1050) |
| iOS-Modell | `ios/Packages/RatslotseAPI/Sources/RatslotseAPI/Models.swift::User` (~Z. 353) | handgeschrieben; `email` ist Pflichtfeld, unbekannte Schlüssel werden ignoriert |
| Empfänger von Mails | `kern/store.py` ~Z. 4090, 4252, 4426; `kern/delivery.py` | alle **joinen live** auf `web_users.email` — nichts speichert eine Kopie der Adresse (einzige Ausnahme: `feedback.email`, bewusst ein Schnappschuss) |

## 2. Entscheidungen

1. **Doppelte Bestätigung: Passwort jetzt, Link an die neue Adresse.** Eine
   offene Sitzung allein (Laptop im Café, gestohlenes Cookie) darf die Adresse
   nicht wechseln können — sonst übernimmt, wer die Sitzung hat, per
   „Passwort vergessen" gleich das ganze Konto. Deshalb dasselbe Re-Auth-Muster
   wie beim Löschen: Passwort, bei Apple-only-Konten ein frisches
   Apple-Identity-Token. Die neue Adresse gilt erst, wenn dort der Link
   geklickt wurde; bis dahin ändert sich **nichts** — Anmeldung, Mails,
   Passwort-Reset laufen weiter über die alte.

2. **Der bestehende Bestätigungsweg wird wiederverwendet, nicht kopiert.**
   Die Tabelle `email_verification_tokens` bekommt eine Spalte `new_email`
   (NULL = Erstbestätigung wie bisher). `POST /api/auth/verify-email`, die
   Seite `/verify-email` und die iOS-Route `/verify-email` bleiben der eine
   Ort, an dem Adressen bestätigt werden. Zwei Gründe:
   - Die **ausgelieferte App** kennt `/verify-email` und ruft den Endpunkt;
     jeder neue Pfad (`/email-bestaetigen`) würde von `AppRoute.swift` als
     unbekannt nach Safari geschickt. So kann selbst die alte App-Fassung
     einen Wechsel abschließen, ohne Store-Update.
   - Die Eigenschaft „ein Token je Konto" erledigt nebenbei einen Randfall:
     Wer nach einem Tippfehler bei der Registrierung die Adresse ändert,
     macht damit den alten Link auf die Tippfehler-Adresse ungültig.

3. **Auch unbestätigte Konten dürfen wechseln.** Der häufigste echte Fall ist
   der Tippfehler bei der Registrierung — genau das Konto, das `require_active`
   aussperrt. Der Endpunkt nimmt deshalb `get_current_user` und prüft selbst:
   erlaubt, wenn `status == active` **oder** `email_verified == 0`; verboten
   (403, gleicher Text wie `require_active`), wenn bestätigt, aber vom Admin
   deaktiviert. Beim Bestätigen wird ein vorher unbestätigtes Konto aktiv —
   über den Pfad, der das heute schon tut.

4. **Ohne Mail-Versand gilt die Änderung sofort** — dieselbe Regel wie bei der
   Registrierung (`verified = not can_send_email` in `register`). Dev und
   Feature haben keinen `RESEND_API_KEY`; wäre der Wechsel dort unmöglich,
   ließe sich das Feature nirgends außer auf Prod ausprobieren, und die
   Browsertests (ohne Mail) hätten keinen Pfad. Die Antwort sagt, was
   passiert ist: `email` schon neu und `pending_email` leer, oder `email` alt
   und `pending_email` gesetzt.

5. **Sitzungen bleiben gültig.** `token_version` wird **nicht** erhöht. Der
   Wechsel wurde mit Passwort bestätigt; wer den Link auf einem anderen Gerät
   klickt (Anfrage im Browser, Klick in der Mail-App), würde sonst beide
   Geräte abmelden. Die alte Adresse wird zweimal informiert (s. 7), das ist
   der Schutz, nicht der Rauswurf.

6. **Zwei Endpunkte, kein dritter.** `POST /api/account/change-email`
   (anstoßen, mit Re-Auth) und `DELETE /api/account/change-email` (abbrechen,
   nur Sitzung). „Erneut senden" ist `POST /api/auth/resend-verification`, das
   einen schwebenden Wechsel erkennt und an die **neue** Adresse schickt. So
   verhalten sich Banner (unbestätigtes Konto) und Konto-Karte gleich, ohne
   dass ein zweiter Resend-Endpunkt entsteht.

7. **Drei Mails.** (a) An die neue Adresse: der Link. (b) An die alte, sofort
   beim Anstoßen: „Jemand will deine Adresse auf … ändern — wenn du das nicht
   warst, ändere jetzt dein Passwort" (solange die alte Adresse noch die
   Reset-Mails bekommt, ist das der wirksame Moment). (c) An die alte, nach
   dem Bestätigen: „Deine Adresse ist jetzt …; Passwort-Reset geht ab jetzt
   nur noch über die neue — antworte auf diese Mail, wenn das nicht du warst."
   Alle drei best-effort im `BackgroundTasks`, alle über
   `kern.digest_email.render_html_email` mit `knopf` (Muster:
   `_send_verification_email`, `_send_goodbye_email`). Held: `passwort`
   („Lotti grübelt", Konto-Sicherheit) für (b)/(c), `willkommen` für (a).

8. **`pending_email` kommt ins `UserOut`** — optional, Vorgabe `None`, nur
   von `/api/auth/me` und den beiden Konto-Endpunkten gefüllt (kein Extra-
   Query in `get_current_user`). Die ausgelieferte App ignoriert den
   unbekannten Schlüssel; die neue liest ihn als `String?`.

9. **Gültigkeit 24 h**, wie die Erstbestätigung (`_VERIFY_TTL_HOURS`). Der
   Link vollendet nur, was jemand mit Passwort begonnen hat — die 1 h des
   Reset-Links wäre unnötig streng für jemanden, der das neue Postfach
   nicht sofort zur Hand hat.

10. **Rate-Limit pro Konto**: `change_email_limiter = RateLimiter(max_calls=5,
    window_seconds=900)` in `web/backend/app/ratelimit.py`, geprüft mit
    `subject=user["id"]` (angemeldet, verschickt Mails → kostet Resend-
    Kontingent). Das Abbrechen braucht keins.

11. **Kein Feature-Schalter, kein Umgebungs-Gate.** Klein, abgeschlossen,
    nichts Halbfertiges; darf mit dem nächsten Release nach `main`.

## 3. Ablauf

```
Konto-Seite (Web/App)            Backend                              Postfächer
──────────────────────           ───────────────────────────────      ────────────────────
neue Adresse + Passwort  ──►  POST /api/account/change-email
                              ├ Re-Auth (Passwort | Apple)
                              ├ normalisieren, ≠ alt, nicht vergeben,
                              │ nicht @local, Status erlaubt
                              ├ ohne RESEND_API_KEY: sofort umschreiben ──► UserOut(email=neu)
                              ├ Token (new_email=neu, 24 h) — ersetzt
                              │ jeden älteren Token dieses Kontos
                              ├ Mail (a) an neu: Link /verify-email?token=…&change=1
                              └ Mail (b) an alt: „wenn du das nicht warst …"
                         ◄──  UserOut(email=alt, pending_email=neu)

Klick auf den Link       ──►  POST /api/auth/verify-email {token}
(Web-Seite oder App)          ├ Token verbrauchen → (user_id, new_email)
                              ├ new_email noch frei? sonst 409
                              ├ UPDATE email=neu, email_verified=1
                              ├ war vorher unbestätigt → status active,
                              │ Admin-Info, Admin-Erst-Einrichtung (wie heute)
                              └ Mail (c) an alt: „Adresse geändert"
                         ◄──  UserOut(email=neu, App: access_token)
```

## 4. Umsetzung — Backend

### 4.1 `kern/store.py`

- **Schema UND Migration** (Regel aus `council/CLAUDE.md` gilt hier genauso):
  `new_email TEXT` an `email_verification_tokens` — im `CREATE TABLE`
  ergänzen **und** im `ALTER TABLE`-Block von `_migrate` nach dem Muster der
  `web_users`-Spalten (`PRAGMA table_info`, unbedingt an der eigenen Spalte
  prüfen — `tests/test_web_users_spalten.py` erklärt, warum eine Spalte nie
  an einer fremden Bedingung hängen darf).
- `create_email_verification(user_id, token_hash, expires_at, new_email: str | None = None)`
  — schreibt die Spalte; das `DELETE` aller alten Tokens des Kontos bleibt.
- `consume_email_verification(token_hash, now) -> dict | None` — gibt
  `{"user_id": …, "new_email": …}` zurück statt nur der ID. Aufrufer
  anpassen (`verify_email` und die Tests, `grep consume_email_verification`).
- `pending_email_change(user_id, now) -> str | None` — `new_email` des
  unverbrauchten, nicht abgelaufenen Tokens, sonst `None`.
- `cancel_email_change(user_id)` — `DELETE … WHERE user_id = ? AND new_email IS NOT NULL`.
- `update_email(user_id, new_email)` — `UPDATE web_users SET email = ?,
  email_verified = 1 WHERE id = ?`; `sqlite3.IntegrityError` **nicht**
  schlucken, der Router macht daraus 409.
- `USER_OWNED_TABLES` bleibt: `email_verification_tokens` steht schon drin,
  ein gelöschtes Konto nimmt seinen schwebenden Wechsel mit
  (`tests/test_account_deletion.py` hält das).

### 4.2 `web/backend/app/schemas.py`

```python
class ChangeEmailRequest(BaseModel):
    """Adresswechsel verlangt eine frische Bestätigung — wie DeleteAccountRequest."""
    new_email: EmailStr
    current_password: str = Field(default="", max_length=128)
    apple_identity_token: str = Field(default="", max_length=4096)
```

`UserOut` bekommt `pending_email: str | None = None` (mit Kommentar, warum
optional: nur `/me` und die Konto-Endpunkte füllen es; die ausgelieferte App
kennt es nicht).

### 4.3 `web/backend/app/routers/account.py`

- Die Re-Auth-Verzweigung aus `delete_account` (Apple-Token mit `sub`-Abgleich,
  sonst Passwort, Fehlertext je nach `password_set`) in eine Hilfsfunktion
  ziehen, z. B. `_reauth(user, current_password, apple_identity_token)`, und
  von beiden Endpunkten benutzen. Der Apple-Zweig in `delete_account` widerruft
  zusätzlich den Authorization-Code — das bleibt dort, nicht in der
  Hilfsfunktion.
- `POST /change-email` (`response_model=UserOut`, Abhängigkeit
  **`get_current_user`**, nicht `require_active` — Grund in Entscheidung 3):
  1. `change_email_limiter.check(request, subject=user["id"])`
  2. Status: erlaubt bei `active` oder `email_verified == 0` oder
     `ist_admin(user)`; sonst 403 „Dein Konto ist derzeit deaktiviert."
  3. `_reauth(...)`
  4. `new = str(body.new_email).lower().strip()`; `new == user["email"]` → 400
     „Das ist bereits deine Adresse."; `new.endswith("@local")` → 400;
     `store.get_web_user_by_email(new)` → 409 „E-Mail ist bereits registriert."
     (derselbe Text wie `register`; das Konto ist angemeldet und gebremst, ein
     Aufzählungs-Orakel entsteht damit nicht neu)
  5. `settings.resend_api_key` leer → `store.update_email(...)`, fertig
     (IntegrityError → 409). Sonst Token wie in `resend_verification`
     (`secrets.token_urlsafe(32)`, sha256, `_VERIFY_TTL_HOURS`) mit
     `new_email=new`; `background.add_task(_send_email_change_link, new, raw, display_name)`
     und, falls die alte Adresse nicht auf `@local` endet,
     `background.add_task(_send_email_change_notice, old, new, display_name)`.
  6. Antwort `_to_out(frisch_geladen, _app_access_token(...), pending_email=…)`.
- `DELETE /change-email` (`response_model=UserOut`, `get_current_user`):
  `cancel_email_change`, Antwort ohne `pending_email`.
- Die drei Mail-Funktionen leben in `auth.py` neben `_send_verification_email`
  (der Link-Bauer ist derselbe; `account.py` importiert aus `auth.py`, so wie
  es heute `_to_out` importiert). Link: `…/verify-email?token=…&change=1` —
  `change=1` ist **nur Kosmetik für die Web-Seite** (Erfolgstext, Ziel
  `/account`); die Wahrheit steht im Token. `AppRoute.swift` liest nur `token`.
- `_to_out` bekommt einen Parameter `pending_email: str | None = None`;
  `me()` in `auth.py` füllt ihn mit `store.pending_email_change(...)`.

### 4.4 `web/backend/app/routers/auth.py::verify_email`

```python
row = store.consume_email_verification(token_hash, now)
if row is None: 400 wie heute
user = store.get_web_user_by_id(row["user_id"])
war_unbestaetigt = not user.get("email_verified")        # VOR dem Umschreiben merken
alt = user["email"]
if row["new_email"]:
    if store.get_web_user_by_email(row["new_email"]): 409 „inzwischen vergeben — bitte neu anstoßen"
    try: store.update_email(user_id, row["new_email"])
    except sqlite3.IntegrityError: 409 (Wettlauf zwischen Prüfung und UPDATE)
    background.add_task(_send_email_changed_notice, alt, row["new_email"], display_name)  # außer alt endet auf @local
else:
    store.set_email_verified(user_id, True)
user = neu laden
if war_unbestaetigt and user["status"] == "pending":
    aktivieren + _notify_admins_registration  (wie heute)
_promote_configured_admin(...)                              (wie heute, s. Randfall „WEB_ADMIN_EMAIL")
```

**Der `war_unbestaetigt`-Merker ist kein Stil, sondern ein Loch, das sonst
aufginge:** `status == pending` heißt auch „vom Admin deaktiviert". Ohne den
Merker könnte ein deaktiviertes Konto mit schwebendem Wechsel sich per Link
selbst reaktivieren.

### 4.5 `web/backend/app/routers/auth.py::resend_verification`

Vor dem heutigen `if user.get("email_verified"): return ok` zuerst
`pending = store.pending_email_change(...)`; ist einer da, neuen Token mit
`new_email=pending` und Mail (a) an die neue Adresse, Rückgabe ok. Sonst wie
bisher. Damit funktioniert „Erneut senden" für aktive Konten aus der
Konto-Karte **und** für unbestätigte aus dem Banner, und ein Resend killt
den schwebenden Wechsel nicht mehr (heute würde er einen Token ohne
`new_email` anlegen und den Wechsel damit löschen).

### 4.6 Vertrag

```bash
python scripts/openapi_schnitt.py
cd web/frontend && npm run api:typen
python scripts/ios_vertrag.py
```

Beide Endpunkte tragen `get_current_user` → `tests/test_endpunkt_schutz.py`
zählt sie als geschützt; `OEFFENTLICH` bleibt unverändert.

## 5. Umsetzung — Web

Vorher `web/frontend/DESIGNSPRACHE.md` lesen. Alle Aufrufe über `lib/api.ts`.

- `lib/types.ts::User`: `pending_email?: string | null` ergänzen (der Typ ist
  ein Handtyp, „Restschuld" laut `web/frontend/CLAUDE.md` — hier nur das
  Feld nachziehen, nicht den Typ umbauen). Für die Antwort des neuen
  Endpunkts `ApiAntwort<"/account/change-email">` aus `lib/vertrag.ts`.
- `app/(app)/account/page.tsx`: neue Karte **„E-Mail-Adresse"** in der
  rechten Spalte zwischen `DisplayNameCard` und `AppearanceCard` (Reihenfolge
  der Spalte: was dich betrifft — Name, Adresse, Aussehen, Anmeldung). Inhalt:
  - aktuelle Adresse als Text,
  - bei `user.pending_email`: Hinweis „Bestätigungslink an *neu* unterwegs —
    der Link ist 24 Stunden gültig." mit zwei Textknöpfen *Erneut senden*
    (`api.post("/auth/resend-verification")`) und *Abbrechen*
    (`api.del("/account/change-email")`), danach `refresh()`;
  - Formular: `Input type="email" autoComplete="email"` + `PasswordInput`
    (`autoComplete="current-password"`), wenn `has_password`; sonst wie in der
    Lösch-Mutation `appleIdentityToken()` bei `nativeApple`, und im Browser
    der bestehende Hinweistext, zuerst ein Passwort zu setzen;
  - Erfolg: `u.email === neu` → toast „E-Mail-Adresse geändert." (Fall ohne
    Mail-Versand), sonst toast „Bestätigungslink an *neu* unterwegs."; dann
    `refresh()`, Felder leeren. Fehler: `err.message` aus `ApiError`.
  - `PageHeader description={user?.email}` und die Adresse in `nav.tsx`
    aktualisieren sich über `refresh()` von selbst.
- `app/verify-email/page.tsx`: `change` aus den Suchparametern lesen. Bei
  Erfolg mit `change`: toast „Deine neue E-Mail-Adresse ist bestätigt." und
  `router.replace("/account")` statt `/dashboard`; das Prefetch des
  Assistenten entfällt in dem Fall. Fehlertext bei 409 kommt vom Backend.
- `app/(app)/layout.tsx` (Unbestätigt-Banner): steht `user.pending_email`,
  lautet der Text „Bestätigungslink an *neu* unterwegs" statt der alten
  Adresse; daneben ein Link „Falsche Adresse? Ändern" auf `/account`. Die
  Konto-Seite muss für ein unbestätigtes Konto erreichbar sein — prüfen, ob
  das `(app)`-Layout sie heute schon zeigt (das Banner liegt dort, die
  Seite selbst ruft nur `require_active`-Endpunkte für Zustellung/Name, die
  dann 403 liefern und ihre Karten leer lassen — das ist in Ordnung, die
  E-Mail-Karte funktioniert).
- **Vor dem Merge ein Bild der Karte (Ruhezustand + schwebend) per
  `SendUserFile` an Tim und sein Gegenlesen abwarten** — stehende Regel für
  jeden UI-PR.

## 6. Umsetzung — iOS

- `Models.swift::User`: `public let pendingEmail: String?` + CodingKey
  `pending_email`. Optional → die Fixtures unter
  `Packages/RatslotseAPI/Tests/RatslotseAPITests/Fixtures/` brauchen keinen
  Nachzug; `python scripts/ios_vertrag.py` muss grün bleiben.
- `AppModel.swift`: `changeEmail(newEmail:password:appleIdentityToken:) async throws`
  (POST, `accept(user:)`), `cancelEmailChange() async throws` (DELETE,
  `accept(user:)`); `resendVerification()` gibt es schon.
- `TopicsAndAccountViews.swift`: im Panel „Profil" unter dem Anzeigenamen
  eine `RatsSettingsRow("E-Mail-Adresse", detail: user.email)` mit Chevron →
  Sheet `ChangeEmailView` nach dem Vorbild von `ChangePasswordView` (Feld
  neue Adresse, `.textContentType(.emailAddress)`, `.keyboardType(.emailAddress)`,
  `.textInputAutocapitalization(.never)`; Passwortfeld, wenn `hasPassword`;
  sonst der Apple-Knopf aus `DeleteAccountView`, der `appleToken` liefert —
  der Authorization-Code wird hier **nicht** gebraucht). Bei
  `user.pendingEmail`: die Zeile zeigt „Bestätigung an … unterwegs", das
  Sheet bietet *Erneut senden* und *Abbrechen*.
- Deep-Link: `/verify-email` ist geroutet; `verifyEmail(token:)` meldet
  „Deine E-Mail-Adresse ist bestätigt." — passt für beide Fälle. Wird der
  Link geöffnet, während die App abgemeldet ist, landet sie über das
  zurückgegebene `access_token` angemeldet — wie heute bei der
  Erstbestätigung.
- Unbestätigt-Bildschirm in `AuthViews.swift` (dort wird
  `resendVerification()` gerufen): Zeile „Falsche Adresse? Ändern" → dasselbe
  Sheet. Und: steht `pendingEmail`, nennt der Text die neue Adresse.
- Neue Dateien nur innerhalb `Packages/` → kein `xcodegen generate` nötig.
  Die iOS-CI läuft nur bei Änderungen unter `ios/`; der Simulator-Lauf ist
  Handarbeit (Rezept in `ios/CLAUDE.md`).

## 7. Tests

Neue Datei `tests/test_email_aendern.py`, Fixtures und Muster aus
`tests/test_backend_api.py` (`client`, `_register`, das
`fake_settings`/`fake_send`-Paar aus
`test_configured_admin_gets_role_only_after_email_confirmation` — es liefert
den Token aus dem Mailtext per Regex). Adressen nur auf `example.org`
(`scripts/lint_adressen.py` läuft im Commit-Hook).

Ohne `RESEND_API_KEY` (Vorgabe der Suite) läuft der Sofort-Pfad; der
Token-Pfad braucht das `fake_settings`-Patch.

| Test | Erwartung |
|---|---|
| Sofort-Pfad ohne Mail-Versand | 200, `email` neu, `pending_email` null; Login mit neu klappt, mit alt 401 |
| Token-Pfad | 200, `email` alt, `pending_email` neu; **zwei** Mails (neu: Link, alt: Hinweis); `/me` zeigt `pending_email`; nach `verify-email` `email` neu, dritte Mail an alt |
| Falsches Passwort | 400, nichts geändert, keine Mail |
| Apple-only-Konto | mit gültigem Identity-Token (Fixture `apple_jwks`) 200; mit fremder `sub` 400; Passwort-Weg gibt den Apple-Hinweistext |
| Gleiche Adresse | 400 |
| Vergebene Adresse | 409 |
| Vergeben **zwischen** Anstoßen und Klick | Anstoßen 200; zweites Konto registriert die Adresse; Klick → 409; `pending_email` danach null (Token verbraucht) |
| `@local` als Ziel | 400 |
| Unbestätigtes Konto (Tippfehler) | Anstoßen 200; alter Registrierungs-Link danach 400 (ersetzt); Klick auf neuen Link → `email` neu, `status` active, Admin-Info-Mail |
| Deaktiviertes Konto (verified, status pending per Admin) | Anstoßen 403; ein vorher erzeugter Token darf das Konto beim Klick **nicht** aktivieren |
| Abbrechen | DELETE → `pending_email` null; der alte Link → 400 |
| Erneut senden bei schwebendem Wechsel | `resend-verification` schickt an die **neue** Adresse; der frühere Link ist tot, der neue gilt |
| Zweites Anstoßen mit anderer Adresse | ersetzt den ersten; erster Link tot |
| Rate-Limit | 6. Aufruf in 15 min → 429 (Suite setzt `DISABLE_RATE_LIMIT` — für diesen Test per `monkeypatch` aufheben) |
| Sitzung | nach Wechsel bleibt das Cookie gültig (`/me` 200 ohne neue Anmeldung); App-Client bekommt `access_token` |
| Konto löschen mit schwebendem Wechsel | Token-Zeile weg (deckt `test_account_deletion` schon ab, hier nur ein Durchlauf) |
| Vertrag | `test_api_vertrag.py`, `test_ios_vertrag.py`, `test_endpunkt_schutz.py` bleiben grün |

Browsertest in `web/frontend/tests/e2e/09-konto.spec.ts`: eigenes Konto
anlegen (`anlegen: true` in `konten.ts`, **nicht** die geteilten Identitäten —
die anderen Specs melden sich mit deren Adresse an), Adresse ändern, Kopfzeile
zeigt die neue, Abmelden, Anmelden mit neu klappt, mit alt nicht. Der
Test-Backend hat keinen Resend-Key → Sofort-Pfad.

## 8. Randfälle — vollständige Liste

| # | Fall | Verhalten | Wo |
|---|---|---|---|
| 1 | Sitzung ohne Passwort (fremdes Gerät) | kein Wechsel möglich | Re-Auth in 4.3 |
| 2 | Apple-only-Konto (`password_set = 0`) | Apple-Re-Auth, `sub` muss zum Konto passen; im Browser ohne Apple: Hinweis, erst Passwort zu setzen | 4.3, 5, 6 |
| 3 | Apple-Konto mit Relay-Adresse (`@privaterelay.appleid.com`) wechselt auf echte Adresse | erlaubt; spätere Apple-Anmeldung trifft über `apple_sub`, die Relay-Adresse im Token wird danach nicht mehr verglichen | `auth_apple.py` unverändert |
| 4 | Tippfehler bei der Registrierung, Konto unbestätigt | Wechsel erlaubt; alter Link tot; Klick aktiviert | Entscheidung 3, 4.4 |
| 5 | Vom Admin deaktiviertes Konto | 403 beim Anstoßen; ein Alt-Token aktiviert nichts | `war_unbestaetigt` in 4.4 |
| 6 | Neue = alte Adresse (auch nur Groß/Klein oder Leerzeichen anders) | 400 nach Normalisierung | 4.3 |
| 7 | Neue Adresse gehört einem anderen Konto | 409 | 4.3 |
| 8 | Adresse wird zwischen Anstoßen und Klick registriert | Klick 409, Token verbraucht, neu anstoßen | 4.4 |
| 9 | Zwei Konten stoßen denselben Wechsel an | wer zuerst klickt, gewinnt; der zweite bekommt 409 | 4.4 |
| 10 | Zweimal auf den Link klicken | zweiter Klick 400 „ungültig oder abgelaufen" | `consume` wie heute |
| 11 | Link nach 24 h | 400; „Erneut senden" oder neu anstoßen | TTL |
| 12 | Link in der App geöffnet, App abgemeldet | Endpunkt gibt `access_token`, App ist danach angemeldet | wie Erstbestätigung |
| 13 | Link geöffnet, während ein **anderes** Konto angemeldet ist | Web: Wechsel wird trotzdem durchgeführt (Token ist kontogebunden), die Seite zeigt danach das angemeldete Konto — Erfolgstext bleibt korrekt. App: `accept(user:)` wechselt auf das Konto des Tokens, wie heute bei Erstbestätigung. Kein Schaden, im PR benennen | 5, 6 |
| 14 | Link in Safari statt App | Web-Seite erledigt es; die App zeigt beim nächsten `/me` die neue Adresse | — |
| 15 | Alte Adresse ist `tg-…@local` (Alt-Bestand) | keine Hinweis-Mails an alt; Wechsel ist genau der Weg, so ein Konto zu einer echten Adresse zu bringen; danach ist `delivery_channel = email` wieder wählbar (`set_delivery` prüft `@local`) | 4.3 |
| 16 | Neue Adresse `@local` | 400 | 4.3 |
| 17 | Kein `RESEND_API_KEY` (dev, feature, lokal, Tests) | sofort umschreiben, keine Mails; Antwort zeigt es | Entscheidung 4 |
| 18 | Resend-Fehler (HTTP-Fehler) | Hintergrund-Task loggt, Anfrage bleibt 200; Nutzer*in nimmt „Erneut senden" | wie `_send_verification_email` |
| 19 | Passwort ändern, während ein Wechsel schwebt | `token_version` steigt, der Wechsel-Token bleibt gültig (unabhängig) | — |
| 20 | Konto löschen, während ein Wechsel schwebt | Token weg (`USER_OWNED_TABLES`) | `test_account_deletion` |
| 21 | Admin ändert Rolle/Status, während ein Wechsel schwebt | Rollen hängen an `user_id`, bleiben | — |
| 22 | Benachrichtigungen (Digest, Erinnerung, Kalender, Push) | joinen live auf `web_users.email` → nächste Zustellung an die neue Adresse; Push-Tokens unberührt | Messung in Abschnitt 1 |
| 23 | Schwebende Warteschlange (`notify`) | speichert keine Adresse, wird beim Versand aufgelöst | `kern/notify.py` |
| 24 | `feedback.email` | bewusst Schnappschuss „Adresse zum Zeitpunkt des Absendens", bleibt alt | Kommentar in `store.py` |
| 25 | Adresse in `record_activity` / Fehlersammler | keine gespeichert (Fehlersammler maskiert Adressen) | `kern/fehler.py` |
| 26 | Admin-Konto wechselt **weg** von `WEB_ADMIN_EMAIL` | Rollen bleiben (an `user_id`); Start-Warnung in `main.py` findet kein Konto zur konfigurierten Adresse und schweigt; **`scripts/rauchprobe.py` findet das Konto nicht mehr** → in der `.env` `RAUCHPROBE_KONTO` auf die neue Adresse setzen, sonst entfällt der angemeldete Teil der Probe mit Meldung „kein Konto" | Ops-Hinweis im PR und in `docs-site` |
| 27 | Jemand wechselt **auf** `WEB_ADMIN_EMAIL` | `_promote_configured_admin` greift nur, solange es **keinen** Admin gibt — dieselbe Garantie wie bei der Registrierung (Postfach nachgewiesen). Unverändert lassen, im Test festhalten | 4.4 |
| 28 | Registrierung mit einer Adresse, für die ein Wechsel schwebt | erlaubt (sie steht noch nicht in `web_users`); der Wechsel scheitert später mit 409 | Fall 8 |
| 29 | Apple-Anmeldung mit einer Apple-ID, deren (Apple-bestätigte) Adresse jetzt die neue Adresse dieses Kontos ist | `auth_apple.py` verknüpft per Adresse — bestehendes Verhalten, nicht Teil dieses PR | — |
| 30 | Groß/Klein, Leerzeichen, Unicode | `EmailStr` + `lower().strip()` wie `register`; SQLite-UNIQUE ist byte-genau, deshalb die Normalisierung **vor** jeder Prüfung | 4.3 |
| 31 | Sehr schnelles Wiederholen | 5 / 15 min pro Konto → 429 mit `Retry-After` | 4.3 |
| 32 | `change=1` in der URL manipuliert | ändert nur Erfolgstext und Sprungziel der Web-Seite; die Wahrheit steht im Token | 5 |
| 33 | Alte App-Fassung im Store | zeigt keine Karte, aber: Link aus der Mail funktioniert (`/verify-email`), `/me` liefert die neue Adresse, `pending_email` wird ignoriert | Entscheidung 2, 8 |

## 9. Sicherheit — Kurzfassung für den PR-Text

- Re-Auth mit Passwort/Apple; die Sitzung allein reicht nicht.
- Nur der sha256-Hash des Tokens liegt in der Datenbank; einmalig; 24 h.
- Ein Token je Konto; ein neuer Antrag oder ein Resend ersetzt den alten.
- Die alte Adresse wird beim Anstoßen **und** nach dem Wechsel informiert.
- Pro Konto gebremst (Resend-Kontingent, Mail-Spam an Dritte).
- Ein deaktiviertes Konto kann sich über den Link nicht reaktivieren.
- Keine neue Aufzählungsmöglichkeit: 409 gibt es nur angemeldet und gebremst,
  denselben Text liefert `register` heute schon unangemeldet.
- Sitzungen werden bewusst nicht beendet (Entscheidung 5).

## 10. Doku, Changelog, Abschluss

- `docs-site/src/content/docs/app-und-konten.md`: die Endpunkt-Tabelle um
  `POST/DELETE /api/account/change-email` (Limit 5 / 15 min) ergänzen; bei
  `POST /api/auth/verify-email` den Zusatz „bestätigt auch einen
  Adresswechsel"; Absatz zum Ablauf; Ops-Hinweis `RAUCHPROBE_KONTO` (Fall 26)
  in `betrieb.md`.
- `changelog.d/email-adresse-aendern.md`, `kategorie: hinzugefuegt`, ohne
  Überschrift: **E-Mail-Adresse ändern.** Unter *Mein Konto* lässt sich die
  Adresse wechseln: Passwort bestätigen, Link an die neue Adresse klicken,
  fertig — Themen, Merkliste und Abzeichen bleiben. Auch nach einem
  Tippfehler bei der Registrierung.
- Vor dem Push: `python scripts/pruefe.py`; Browsertests
  `cd web/frontend && npx playwright test` (freie Ports, s. Wurzel-`CLAUDE.md`).
- Bild an Tim (Web-Karte, iOS-Sheet), Gegenlesen abwarten, dann
  `python scripts/merge_wenn_gruen.py`.

## 11. Bewusst nicht in diesem PR

- **Admin ändert die Adresse eines fremden Kontos.** Anderer Vertrauensweg
  (keine Re-Auth der Person möglich), eigener Endpunkt im Admin-Panel — bei
  Bedarf ein Folge-PR.
- **`pending_email` im Admin-Panel** anzeigen — nett, nicht nötig.
- **Sitzungen beim Wechsel beenden** — s. Entscheidung 5.
- **Apple-Verknüpfung per Adresse** (Fall 29) — bestehendes Verhalten.
- **Antwort an den Einsender** des Vorschlags — macht Tim, nicht der PR.
