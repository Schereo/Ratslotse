---
title: App & Konten
description: Die native iOS-/Android-App (Capacitor), die Anmeldung (klassisch und mit Apple) und was alles am Nutzerkonto hängt.
---

Dieselbe Next.js-Oberfläche läuft im Browser und — statisch exportiert und in
eine **Capacitor**-Hülle gepackt — als native App. Beide sprechen dasselbe
FastAPI-Backend an; unterschiedlich ist nur, wie die Sitzung transportiert wird
(Cookie im Web, Bearer-Token in der App) und welche Bedienmuster greifen.

## Native App (Capacitor)

Die nativen Projekte liegen im Repo (`web/frontend/ios/` **und**
`web/frontend/android/`, beide eingecheckt). Bau-Anleitung, Xcode-Capabilities
und die Einreichungs-Checkliste stehen in `web/frontend/MOBILE.md`.

### Vom Next-Build zur App

```bash
cd web/frontend
npm run build:mobile   # = node scripts/build-mobile.mjs
npm run cap:sync       # kopiert ./out in ios/ und android/
npm run cap:ios        # bzw. cap:android — öffnet Xcode / Android Studio
```

`scripts/build-mobile.mjs` erledigt dabei drei Dinge, die ein nacktes
`next build` nicht kann:

1. **Statischer Export** statt Server: `MOBILE=1 next build` schaltet in
   `next.config.mjs` auf `output: "export"` (+ `trailingSlash`, unoptimierte
   Bilder) und schreibt nach `./out` — das ist `webDir` in
   `capacitor.config.ts`.
2. Der **web-only Route-Handler** unter `app/api/` (SSE-Proxy) wird für den
   Build beiseitegeschoben und danach zurückgelegt — Route Handler lassen sich
   nicht statisch exportieren.
3. Eine **Content-Security-Policy** wird als `<meta http-equiv>` in jede
   exportierte `.html` injiziert, weil der Export keine Header setzen kann.

Es gibt **keine `server.url`** in der Capacitor-Konfiguration: Die App lädt ihre
Assets lokal aus der WebView und ruft das Backend an einem **absoluten Origin**
auf — `NEXT_PUBLIC_API_BASE`, sonst `https://ratslotse.de`
(`lib/platform.ts`). Damit das ohne `.env`-Änderung funktioniert, hängt das
Backend die festen App-WebView-Origins immer an die CORS-Liste an
(`capacitor://localhost`, `https://localhost` — `app_cors_origins` in
`web/backend/app/config.py`).

| Datei | Rolle |
|---|---|
| `web/frontend/capacitor.config.ts` | `appId` `de.ratslotse.app`, `appName` „Ratslotse", `webDir: "out"`, `androidScheme: "https"`, Push-Präsentationsoptionen |
| `web/frontend/scripts/build-mobile.mjs` | Export-Build + CSP-Injektion |
| `web/frontend/lib/platform.ts` | `isNativeApp()`, `nativePlatform()`, `apiBase()` |
| `web/frontend/MOBILE.md` | Setup, Xcode-Capabilities, Push-Credentials, Deep-Links, App-Store-Checkliste |

### Was die App vom Web unterscheidet

| Verhalten | Umsetzung | Ort |
|---|---|---|
| Safe-Area / Notch | `viewportFit: "cover"` liefert echte `env(safe-area-inset-*)`-Werte; Topbar, Tab-Leiste, Hauptbereich, Offline-Pille und Intro rechnen damit | `app/layout.tsx`, `components/nav.tsx`, `app/(app)/layout.tsx` |
| Zurückwischen vom Bildschirmrand | `MainViewController` setzt `webView.allowsBackForwardNavigationGestures = true`; da der Next-Router über die History-API navigiert, entspricht das exakt der Zurück-Navigation (als `customClass` in `Main.storyboard` eingehängt) | `ios/App/App/AppDelegate.swift` |
| Zoom-Sperre | nur nativ: das Viewport-Meta wird auf `maximum-scale=1, user-scalable=no` umgeschrieben (der System-Zoom der Bedienungshilfen bleibt); im Web bleibt Pinch-Zoom unangetastet | `app/providers.tsx` |
| Tab-Leiste unten statt Sidebar | `MobileBottomNav` (`md:hidden`) mit 4 Zielen + angehobener „Fragen"-Taste vs. `DesktopSidebar` (`hidden md:flex`) — greift auf allen schmalen Viewports, in der App also immer | `components/nav.tsx` |
| Pull-to-Refresh | nur App: Touch-Handler am Seitenanfang, Schwelle 70 px, danach `invalidateQueries()` (kein harter Reload) | `components/pull-to-refresh.tsx` |
| Startseite überspringen | `/` ersetzt sich in der App sofort durch `/dashboard` | `components/native-redirect.tsx` |
| Universal / App Links | `appUrlOpen` → In-App-Route (E-Mail-Bestätigung, Passwort-Reset, Push-Tap) | `lib/app-links.ts` |
| Anmeldung | Bearer-Token aus `@capacitor/preferences` statt httpOnly-Cookie | `lib/token.ts`, `lib/api.ts` |

### Offline

Zwei getrennte Bausteine:

- **Offline-Pille** (`components/offline-pill.tsx`): hört auf `navigator.onLine`
  und die `online`/`offline`-Events und blendet unten „Offline — du siehst
  gespeicherte Inhalte" ein. Bewusst **auch im Web** aktiv.
- **Persistenter Query-Cache** (`app/providers.tsx`): **nur in der App** wird der
  React-Query-Client in einen `PersistQueryClientProvider` gehängt.

```
Storage   window.localStorage, Schlüssel „ratslotse.query-cache"
maxAge    24 h  (gcTime der Queries ist auf denselben Wert gehoben,
                 sonst räumt der Garbage Collector vor dem Persist auf)
buster    "v2"  (verwirft ältere, inkompatible Caches)
staleTime 30 s, retry 1  (Query-Defaults, web wie app)
```

Gecacht werden damit genau die **API-Antworten der besuchten Seiten**, die über
React Query laufen — keine PDFs, keine Kartenkacheln. Beim Start im Funkloch
zeigt die App den letzten Stand statt Skeletons oder Fehlern.

### Icons und Erststart

- **App-Icons** in drei Erscheinungsbildern (iOS): `AppIcon-1024.png`,
  `AppIcon-1024-dark.png`, `AppIcon-1024-tinted.png` in
  `ios/App/App/Assets.xcassets/AppIcon.appiconset/` (dazu `Splash.imageset`).
  Erzeugt mit `@capacitor/assets` aus `web/frontend/assets/logo.png`
  (Hintergrund `#0764a6` hell, `#09111b` dunkel).
- **First-Run-Intro** (`components/app-intro.tsx`): drei Karten mit dem
  Maskottchen beim allerersten App-Start, „Überspringen" jederzeit möglich.
  Nur nativ, danach nie wieder (`localStorage`-Schlüssel
  `ratslotse.intro.done`).

## Anmeldung

Passwörter werden mit **scrypt** gehasht, Sitzungs-Token sind
**HS256-JWTs**, signiert mit `WEB_JWT_SECRET` — beides stdlib-pur in
`web/backend/app/security.py` (kein passlib/bcrypt/cryptography).

**Web:** Login/Registrierung setzen ein `access_token`-Cookie — `httponly`,
`samesite=lax`, `secure` gesteuert über `COOKIE_SECURE` (Default `True`),
Laufzeit `ACCESS_TOKEN_EXPIRE_MINUTES` (Default 1 Tag). Page-JS sieht das Token
nie.

**App:** Der Client schickt den Header `X-Client: app`. Erkennt das Backend ihn,
liefert es zusätzlich ein **langlebiges Token im Antwort-Body**
(`app_access_token_expire_minutes`, Default 90 Tage), das die App in
`@capacitor/preferences` ablegt und als `Authorization: Bearer …` mitschickt.
`deps.get_current_user` akzeptiert beides — Bearer zuerst, sonst Cookie.

**Widerruf** läuft über `web_users.token_version`: Der Wert steckt als `ver` im
Token; passt er nicht mehr zur Zeile, ist die Sitzung ungültig. Erhöht wird er
bei Passwort-Änderung und Passwort-Reset. `POST /api/auth/logout` löscht nur das
Cookie — die App entfernt ihr Token zusätzlich lokal und meldet vorher ihren
Push-Token ab (`lib/auth.tsx`, `lib/push.ts`).

| Endpunkt | Zweck | Limit |
|---|---|---|
| `POST /api/auth/register` | Konto anlegen (E-Mail, Passwort ≥ 8 Zeichen, optional `display_name`) | 5 / 5 min |
| `POST /api/auth/login` | Anmelden | 10 / min |
| `POST /api/auth/logout` | Session-Cookie löschen | — |
| `GET /api/auth/me` | aktuelles Konto (`UserOut`) | — |
| `POST /api/auth/forgot-password` | Reset-Link (1 h gültig); antwortet **immer** 200, verrät also nicht, ob ein Konto existiert | 5 / 15 min |
| `POST /api/auth/reset-password` | neues Passwort setzen, danach alle Sitzungen ungültig | — |
| `POST /api/auth/verify-email` | Adresse bestätigen (Link 24 h gültig) → Konto wird aktiv | — |
| `POST /api/auth/resend-verification` | Bestätigungslink erneut senden | 5 / 15 min |
| `POST /api/auth/apple` | Sign in with Apple | 10 / min |

Die Registrierung braucht **keine Admin-Freigabe**: Wer die E-Mail bestätigt,
ist aktiv; die Admins bekommen nur eine FYI-Mail. Ohne konfigurierten
E-Mail-Versand (`RESEND_API_KEY` fehlt) wird die Verifikation übersprungen —
sonst ließe sich das Konto nie bestätigen. Solange ein Konto nicht aktiv ist,
zeigt die Oberfläche einen Hinweis statt der Inhalte und pollt `/auth/me`
(`app/(app)/layout.tsx`); serverseitig blockt `require_active`.

### Sign in with Apple

`web/backend/app/routers/auth_apple.py`. Die App holt über das Apple-SDK
(`@capacitor-community/apple-sign-in`) ein **Identity-Token**, im Browser tut
das „Sign in with Apple JS" als Popup-Flow (`lib/apple.ts`). Beide Wege schicken
dasselbe Token an `POST /api/auth/apple` — Secrets oder Schlüssel braucht keine
Seite.

Geprüft wird das RS256-Token gegen **Apples JWKS**
(`https://appleid.apple.com/auth/keys`, 24 h gecacht, bei unbekannter `kid`
einmal Zwangs-Refresh): Signatur, `exp`, `iss` und `aud`.

| Variable | Bedeutung |
|---|---|
| `APPLE_BUNDLE_ID` | erlaubte `aud` der nativen App (Default `de.ratslotse.app`) |
| `APPLE_SERVICE_ID` | erlaubte `aud` des Web-Flows (Services ID, z. B. `de.ratslotse.web`); **leer = Web-Flow aus**, weil dann keine passende `aud` akzeptiert wird |

Danach entscheidet die Kontozuordnung:

- `apple_sub` bereits bekannt → Anmeldung in dieses Konto.
- sonst: gleiche, **von Apple bestätigte** E-Mail vorhanden → **verknüpfen**
  (`apple_sub` setzen, offene Verifikation gilt als erledigt, `pending` wird
  `active`). Private-Relay-Adressen sind dabei normale Adressen.
- sonst: **neues Konto**, sofort `active` und `email_verified`, mit
  Zufalls-Passwort-Hash und `password_set = 0` — ein eigenes Passwort lässt sich
  über „Passwort vergessen" nachrüsten.

Nur die E-Mail **aus dem signierten Token** zählt; eine Client-Angabe wäre
fälschbar. Liefert Apple **keine** E-Mail und ist die `sub` unbekannt, kann kein
Konto zugeordnet werden — die API antwortet mit 400 und dem Hinweis, Ratslotse
in den Apple-ID-Einstellungen unter „Mit Apple anmelden" zu entfernen und es
erneut zu versuchen (Apple sendet die Adresse nur bei der Erstautorisierung).

### Rollen und Status

| Spalte | Werte | Bedeutung |
|---|---|---|
| `web_users.role` | `user`, `admin` | `admin` sieht den Admin-Bereich (`require_admin`) und ist immer aktiv |
| `web_users.status` | `pending`, `active` | `pending` = E-Mail noch nicht bestätigt **oder** von einem Admin deaktiviert |
| `web_users.email_verified` | 0/1 | gesetzt durch Verifikationslink oder Apple-Login |
| `web_users.password_set` | 0/1 | 0 = Apple-Konto ohne selbst gesetztes Passwort |

**Admin wird**, wessen Registrierungs-Adresse `WEB_ADMIN_EMAIL` entspricht —
außerdem der allererste Account einer leeren Datenbank
(`store.count_web_users() == 0`). Beides gilt für die klassische Registrierung
und für neu per Apple angelegte Konten.

## Was am Konto hängt

Alle Konto-Daten liegen in `nwz.sqlite` (siehe
[Architektur](/docs/architektur/)); Eigentum ist durchgängig über
`owner_id = web_users.id` modelliert.

### Zustellkanal

`web_users.delivery_channel` ∈ `email` | `push` | `both` (neue Konten starten
auf `email`).

| Endpunkt | Zweck |
|---|---|
| `PUT /api/account/delivery` | Kanal setzen; `email`/`both` scheitern, wenn keine echte Adresse hinterlegt ist |
| `POST /api/account/test-notification` | Test über alle aktiven Kanäle, exakt über den Cron-Versandpfad `nwz.delivery.deliver_message`; gibt die tatsächlich bedienten Kanäle zurück |

- **E-Mail** über **Resend** (`nwz/email.py`). Ohne `RESEND_API_KEY` wird der
  Versand still übersprungen.
- **Push** über **APNs** (iOS, token-basiert mit `.p8` — kein Firebase) und
  **FCM v1** (Android) in `nwz/push.py`. Geräte-Token, die die Gateways als
  ungültig melden, werden ausgesortiert.
- In der App führt der **Push-Primer** (`components/push-primer.tsx`) vor den
  System-Dialog: Er erscheint erst, wenn es mindestens ein Thema oder ein
  Ausschuss-Abo gibt, und schlummert nach „Später" 7 Tage.

Geräte-Token registriert die App selbst:

| Endpunkt | Zweck |
|---|---|
| `POST /api/push/register` | Token + Plattform (`ios`/`android`) speichern; idempotent, die App registriert bei jedem Start neu |
| `POST /api/push/unregister` | Token entfernen (Logout, Push abschalten) — nur eigene Token |

```
push_tokens
  token PK, owner_id, platform, created_at, last_seen
```

### Themen und Ausschuss-Abos

`web/backend/app/routers/topics.py`. Themen sind die Watchlist des Kontos;
Ausschuss-Abos liegen daneben in `committee_subscriptions`.

| Endpunkt | Zweck |
|---|---|
| `GET /api/topics` | Themen inkl. Trefferzahl, jüngstem Treffer und `unread_count` |
| `POST /api/topics` · `PUT /api/topics/{id}` · `DELETE /api/topics/{id}` | anlegen, ändern, löschen |
| `GET /api/topics/suggestions` | anklickbare Vorschläge aus echten Entitäten mit jüngster Ratsaktivität (Ähnlichkeits-Dedupe gegen vorhandene Themen) |
| `GET /api/topics/{id}/decisions` | gematchte Beschlüsse mit Score |
| `GET /api/topics/latest-hits` | jüngste Treffer über **alle** Themen (Heute-Briefing) |
| `GET /api/topics/unread-count` | Summe ungesehener Treffer |
| `POST /api/topics/{id}/seen` | alle aktuellen Treffer eines Themas als gesehen markieren |
| `GET/POST/DELETE /api/subscriptions` | Ausschuss-Abos lesen, anlegen, entfernen |

Der **„Neu"-Zähler** speist sich aus `topic_hits_seen` (`owner_id`, `topic_id`,
`decision_id`, `seen_at`): Alles, was nicht darin steht, gilt als ungesehen. Die
Navigation pollt `unread-count` im Minutentakt und zeigt die Zahl an „Meine
Themen" bzw. einen orangen Punkt am Themen-Tab; das Öffnen der Beschlussliste
eines Themas ruft `/seen` (`components/nav.tsx`).

Wie Themen gegen Tagesordnungen und Beschlüsse gematcht werden, steht in
[KI-Pipeline](/docs/ki-pipeline/) und
[Ratsdokumente & Beschlüsse](/docs/beschluesse/).

### Abzeichen

`web/backend/app/routers/badges.py` — **acht** Lotsen-Abzeichen, kein Ranking,
keine Serien, die reißen können: `erste-frage`, `themen-lotse`, `quiz-serie`
(5 Tage), `kartograf` (3 Orte), `analyst`, `sitzungsgast`, `fruehwarner`,
`kompass`.

Der Stand wird bei jedem `GET /api/badges` **neu berechnet**, teils aus
vorhandenen Daten (Themen vorhanden, Quiz-Serie, Push-Gerät registriert,
Onboarding-Schritt „analyse"), teils aus Ereignis-Flags, die das Frontend
gemeldet hat. Persistiert wird in der JSON-Spalte `web_users.badges`:

```
{"earned": [ids], "map_places": [slugs], "flags": ["frage","sitzung","tour"]}
```

- `POST /api/badges/event` meldet ein Ereignis (`frage`, `sitzung`, `tour` oder
  `map_place` mit `key`) — idempotent, Unbekanntes wird still verworfen. Das
  Frontend ruft das fire-and-forget über `reportBadgeEvent()`
  (`components/badges.tsx`).
- `newly_earned` enthält die Abzeichen, die **in genau diesem GET** neu dazukamen;
  sie werden dabei in `earned` geschrieben und tauchen danach nie wieder auf.
  Das ist der Auslöser für Toast und Konfetti (`BadgeCelebrator`) — genau einmal.
- Einmal verdient bleibt verdient: Wer ein Thema löscht oder die Quiz-Serie
  reißt, behält das Abzeichen.

### Onboarding

`web/backend/app/routers/onboarding.py`, Spalte `web_users.onboarding` (JSON:
`{"steps": [...], "celebrated": bool}`). Bewusst **serverseitig am Konto statt
im localStorage**, damit der Kurs „Erste Schritte mit Lotti" auf jedem Gerät
denselben Stand hat und nach Abschluss überall verschwindet.

- `GET /api/onboarding` liefert den Stand, `POST /api/onboarding` merged
  erledigte Schritte dazu und/oder setzt `celebrated`.
- Erlaubt sind nur die bekannten Schritte `frag`, `beschluesse`, `analyse`,
  `karten`, `thema` — alles andere wird verworfen, damit die Spalte nicht
  zuwuchert. Schritte gelten schon beim **Besuch** der jeweiligen Seite als
  erledigt (`components/onboarding.tsx`).

### Anzeigename und Konto löschen

`web_users.display_name` (max. 60 Zeichen, optional) wird bei der Registrierung
abgefragt und ist über `POST /api/account/display-name` änderbar — auch für
Apple-Konten und Altbestand, die bei der Anmeldung keinen angeben konnten. Er
dient der persönlichen Ansprache, u. a. in der Begrüßung der
Benachrichtigungs-Mails.

`DELETE /api/account` löscht das Konto endgültig (Recht auf Löschung nach
DSGVO). Verlangt wird eine **frische Bestätigung** — eine offene Sitzung
allein darf ein Konto nicht zerstören können:

- Konten mit Passwort bestätigen mit dem aktuellen Passwort,
- Apple-only-Konten (`password_set = 0`) mit einem frischen Apple-Identity-Token,
  dessen `sub` zum Konto passt (Re-Auth in der App).

`Store.delete_web_user` entfernt dabei die Zeilen aus `topics`,
`article_topic_matches`, `topic_classified_editions`,
`committee_subscriptions`, `password_reset_tokens`,
`email_verification_tokens` und `web_users`; anschließend geht eine
Bestätigungs-Mail raus (Best-Effort). Die Löschmöglichkeit **in der App** ist
zugleich eine App-Store-Anforderung für Apps mit Registrierung.

## Datenschutz-relevante Punkte

Personenbezogen gespeichert werden ausschließlich Daten, die aus der Nutzung
selbst entstehen:

| Daten | Wo |
|---|---|
| E-Mail-Adresse, Passwort-Hash (scrypt), Anzeigename | `web_users` |
| Apple-Kennung (`apple_sub`) und die von Apple bestätigte Adresse — bei „E-Mail verbergen" eine Weiterleitungsadresse | `web_users` |
| Themen und Ausschuss-Abos (frei formulierte Interessen) | `topics`, `committee_subscriptions` |
| gesehene Treffer, Onboarding-Fortschritt, Abzeichen-Stand | `topic_hits_seen`, `web_users.onboarding`, `web_users.badges` |
| Quiz-Antworten (Punkte je Gebiet) | `quiz_answers` |
| Push-Geräte-Token | `push_tokens` |
| Aktivität für die Admin-Statistik: eine Zeile je Konto/Tag/Feature mit Zähler | `user_activity` |

Verarbeiter sind **Resend** (E-Mail-Versand), **Apple/APNs** bzw.
**Google/FCM** (Push-Zustellung) und **Apple** beim „Sign in with Apple" — jeweils
nur, wenn der entsprechende Kanal aktiv ist. Auf dem Gerät liegen Design-Wahl,
in der App das Anmelde-Token und der oben beschriebene Inhalts-Zwischenspeicher.

**Nicht** übernommen werden die **Kontaktdaten der Mandatsträger:innen** aus dem
Ratsinformationssystem (Adresse, Telefon, Beruf auf den Personenseiten) — das
ist eine bewusste Entscheidung der Stammdaten-Auswertung, siehe
[Ratsdokumente & Beschlüsse](/docs/beschluesse/).

Die vollständige, verbindliche Fassung steht auf der Datenschutzseite der App:
[ratslotse.de/datenschutz](https://ratslotse.de/datenschutz) (Quelle:
`web/frontend/app/datenschutz/page.tsx`).
