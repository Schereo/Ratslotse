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
- **Willkommens-Auftakt und Einrichtung** (`components/onboarding-flow.tsx`):
  begrüßt beim allerersten Start vor dem Login und führt danach durch Gremien,
  Themen und Mitteilungen. „Überspringen" ist jederzeit möglich, der erreichte
  Schritt wird gemerkt. (Die früher hier beschriebene `components/app-intro.tsx`
  existiert nicht mehr.)
  Nur nativ, danach nie wieder (`localStorage`-Schlüssel
  `ratslotse.intro.done`).

## Anmeldung

Passwörter werden mit **scrypt** gehasht, Sitzungs-Token sind
**HS256-JWTs**, signiert mit `WEB_JWT_SECRET` — beides stdlib-pur in
`web/backend/app/security.py` (kein passlib/bcrypt/cryptography).

**Web:** Login/Registrierung setzen ein `access_token`-Cookie — `httponly`,
`samesite=lax`, `secure` gesteuert über `COOKIE_SECURE` (Default `True`),
Laufzeit `ACCESS_TOKEN_EXPIRE_MINUTES` (Default 90 Tage). Page-JS sieht das
Token nie.

**App:** Der Client schickt den Header `X-Client: app`. Erkennt das Backend ihn,
liefert es zusätzlich ein **langlebiges Token im Antwort-Body**
(`app_access_token_expire_minutes`, Default 90 Tage), das die App in
`@capacitor/preferences` ablegt und als `Authorization: Bearer …` mitschickt.
`deps.get_current_user` akzeptiert beides — Bearer zuerst, sonst Cookie.

**Angemeldet bleiben:** Beide Sitzungen verlängern sich still bei Nutzung, sonst
stünde man nach Ablauf der Laufzeit trotz täglicher Nutzung wieder vor dem
Login.

- *Web:* Die Middleware `SitzungsVerlaengerung` (`web/backend/app/session.py`,
  rohes ASGI, damit der SSE-Strom der KI-Frage unberührt bleibt) hängt ein
  frisches Cookie an die Antwort, sobald weniger als
  `SESSION_RENEW_WITHIN_MINUTES` (Default 45 Tage, `0` schaltet ab) Restlaufzeit
  übrig sind. Weil das erneuerte Cookie wieder voll läuft, fällt die nächste
  Erneuerung erst eine halbe Laufzeit später an — kein `Set-Cookie` an jeder
  Antwort. Sie greift auf **allen** Routen, auch den öffentlichen; wer nur
  Beschluss-Seiten liest, behält seine Sitzung trotzdem. Ausgenommen sind
  Antworten, die selbst schon ein Cookie setzen (Login, Logout,
  Passwortwechsel — sonst überschriebe die Verlängerung das Abmelden), sowie
  `401`-Antworten.
- *App:* Cookies helfen dort nicht. Stattdessen liefert `GET /api/auth/me` an
  `X-Client: app` ein frisch datiertes Token, das `lib/auth.tsx` in den
  Preferences ablegt — die App fragt den Endpunkt bei jedem Start.

Der Widerruf bleibt davon unberührt: Das erneuerte Token trägt dieselbe
`token_version` wie das alte.

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

### Was ohne Konto sichtbar ist

Vier Endpunkte antworten **ohne Anmeldung**. Nicht aus Versehen, sondern weil
Teilen die Kernhandlung der App ist: Wer einen Beschluss weiterreichte,
schickte die Empfänger*innen vorher ins Registrierungsformular — bevor sie
überhaupt gesehen hatten, worum es geht.

| Endpunkt | Seite |
|---|---|
| `GET /api/council/decision/{id}` | Beschluss |
| `GET /api/council/entity/{slug}` | Thema |
| `GET /api/council/person/{slug}` | Person |
| `GET /api/council/session/{ksinr}` | Sitzung (die Beschluss-Seite zieht Gremium + Datum daraus) |
| `GET /api/council/preview/{art}/{key}` | nur Titel + Kurzfassung für die Link-Vorschau |

Genau die Seiten mit Teilen-Knopf und Link-Vorschau. Alles davon bereitet das
amtliche Ratsinformationssystem auf und ist dort ohnehin für alle einsehbar —
es entsteht keine neue Öffentlichkeit, nur eine lesbare.

:::caution[Die Grenze steht im Backend, nicht im Frontend]
`optional_user` (`web/backend/app/deps.py`) liefert `None` statt eines 401 und
legt **dieselbe Schwelle an wie `require_active`**: Ein unbestätigtes oder
gesperrtes Konto gilt hier als Gast und sieht die öffentliche Fassung. Ohne
das wäre der Weg ein stiller Seiteneingang an der Sperre vorbei.

Persönliches hängt an dieser Prüfung: `follow` (verfolge ich diesen Vorgang?)
kommt nur in die Antwort, wenn wirklich jemand angemeldet ist. Stöbern, Suche,
Analyse, eigene Themen und Benachrichtigungen bleiben zu —
`test_stoebern_und_persoenliches_bleiben_hinter_der_anmeldung` hält diese
Liste fest, damit die Grenze beim nächsten Aufräumen sichtbar ist.

Die Pfadliste im Frontend (`web/frontend/lib/public-routes.ts`) entscheidet nur,
wo statt der Weiterleitung zur Anmeldung die Gast-Hülle erscheint. Sie macht für
sich genommen nichts sichtbar.
:::

Gäste sehen `components/public-shell.tsx` statt der App-Navigation — deren
Ziele verlangen ausnahmslos ein Konto. Die Einladung zum Registrieren steht am
**Ende** der Seite: Erst wer gelesen hat, weiß, wofür sich ein Konto lohnt.
`?weiter=<pfad>` bringt nach Anmeldung, Registrierung oder Apple-Login zurück
zum Ausgangspunkt (nur seiteneigene Pfade, siehe `sicheresZiel`).

Der „Zurück"-Knopf fehlt Gästen bewusst: Bei einem frisch aus einem Messenger
geöffneten Tab führt `router.back()` aus der Seite heraus, und der Rückfall auf
die Sitzungs-Übersicht landet an der Anmeldewand. `history.length > 1`
unterscheidet die Fälle nicht — es zählt auch fremde Einträge.

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

**Die Registrierung vergibt keine Rollen**: Jedes über `/api/auth/register`
angelegte Konto ist `user` — auch die Adresse aus `WEB_ADMIN_EMAIL` und auch das
erste Konto einer leeren Datenbank. Andernfalls bekäme Adminrechte, wer die
konfigurierte Adresse als Erstes ins Formular tippt, ohne Zugriff auf dieses
Postfach nachzuweisen.

**Admin wird** die Adresse aus `WEB_ADMIN_EMAIL`, sobald sie ihre E-Mail
**bestätigt** hat (`/api/auth/verify-email`, nach verbrauchtem Einmal-Token) —
und nur, solange es im Deployment noch gar keinen Admin gibt. Damit holt sich ein
bewusst degradiertes oder gesperrtes Konto die Rechte nicht über einen neuen
Bestätigungslink zurück. Ohne `RESEND_API_KEY` gibt es keinen Link: dann vergibt
`scripts/grant_admin.py <adresse>` die Rechte an ein **bestehendes** Konto (das
Backend weist bei Registrierung und bei jedem Start im Log darauf hin).

**Beim Apple-Login** gilt eine eigene Regel: Wird dabei ein Konto *neu* angelegt
und entspricht die Adresse `WEB_ADMIN_EMAIL`, ist es sofort Admin — ohne
Bestätigungslink und ohne die „noch kein Admin vorhanden"-Bedingung. Das ist
vertretbar, weil Apple die Adresse im signierten Token bereits nachweist; der
Nachweis, den die klassische Registrierung erst über den Link erbringt, liegt
hier schon vor. Der „erstes Konto einer leeren Datenbank"-Notnagel entfällt aber
auch hier.

## Was am Konto hängt

Alle Konto-Daten liegen in `nwz.sqlite` (siehe
[Architektur](/docs/architektur/)); Eigentum ist durchgängig über
`owner_id = web_users.id` modelliert.

### Zustellkanal

`web_users.delivery_channel` ∈ `email` | `push` | `both` | `off` (neue Konten
starten auf `email`).

`off` heißt: gar keine Benachrichtigungen. Kein eigenes Feld, weil es dieselbe
Frage beantwortet wie die anderen drei — wohin? — nur mit „nirgendwohin". Die
Prüfung sitzt in `kern.notify.gewuenscht()`, also **vor** der Warteschlange:
Bei `off` wird nichts eingereiht, sonst zählten unzustellbare Meldungen gegen
die Tagesgrenze und kämen beim Wiedereinschalten als Nachlieferung an.
Zusätzlich verwirft `PUT /api/account/delivery` beim Umschalten auf `off`, was
noch offen in der Warteschlange liegt, und `setups_to_remind()` überspringt
diese Konten — auch die freundlich gemeinte Einrichtungs-Erinnerung schweigt.

| Endpunkt | Zweck |
|---|---|
| `PUT /api/account/delivery` | Kanal setzen; `email`/`both` scheitern, wenn keine echte Adresse hinterlegt ist; `off` räumt zusätzlich die Warteschlange |
| `POST /api/account/test-notification` | Test über alle aktiven Kanäle, exakt über den Cron-Versandpfad `kern.delivery.deliver_message`; gibt die tatsächlich bedienten Kanäle zurück |

- **E-Mail** über **Resend** (`kern/email.py`). Ohne `RESEND_API_KEY` wird der
  Versand still übersprungen.
- **Push** über **APNs** (iOS, token-basiert mit `.p8` — kein Firebase) und
  **FCM v1** (Android) in `kern/push.py`. Geräte-Token, die die Gateways als
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

### Benachrichtigungen: sechs Anlässe, vier Grenzen

Der Zustellkanal sagt **wo**, die Anlässe sagen **wofür**. Beides steht in
„Mein Konto"; die Anlass-Schalter liegen als JSON in `web_users.notify_prefs`
(leer = Vorgaben aus `kern/notify.py`).

| Anlass | wann | Vorgabe | Auslöser |
|---|---|---|---|
| `n1_tagesordnung` | Tagesordnung eines abonnierten Gremiums erscheint | an | `scripts/check_committees.py` (7 Uhr) |
| `n2_thema` | ein eigenes Thema steht auf einer Tagesordnung | an | `council/watcher.py` über `check_council.py` (8/14 Uhr) |
| `n3_ergebnis` | zu einem gemeldeten TOP liegt das Ergebnis vor | an | `council/ergebnisse.py` am Protokoll-Import (`check_protocols.py`, 9 Uhr) |
| `n4_vorgang` | eine verfolgte Vorlage bewegt sich | an | `scripts/check_vorlage_follows.py` |
| `n5_vorabend` | morgen tagt ein Gremium, das dich betrifft | **aus** | `scripts/abendmeldungen.py` (18 Uhr) |
| `n6_woche` | Wochenüberblick | **aus** | dasselbe Skript, nur sonntags |

:::caution[N3 kommt spät — und das ist keine Panne]
Beschlüsse entstehen ausschließlich aus dem **Protokoll-PDF**, und das
erscheint Wochen nach der Sitzung. Gemessen am 26.07.2026: Von 15
Juni-Sitzungen hatte **eine** ein Protokoll; der Verkehrsausschuss vom 08.06.
nach 48 Tagen noch keines, während 20.04. längst vorlag. Der Rat ist schneller
(rund 3,5 Wochen) als die Ausschüsse.

Schnellere Quellen gibt es nicht: Die Sitzungsseite enthält „angenommen",
„abgelehnt", „einstimmig" **kein einziges Mal**, und `council_beratungen.ergebnis`
trägt nur die Beratungs*art* (`Kenntnisnahme` · `Entscheidung` · `Vorberatung`).
Die Meldung nennt deshalb immer das **Sitzungsdatum**, statt Frische zu
behaupten.
:::

#### Die Warteschlange

Kein Anlass sendet selbst. Alle reihen über `kern.notify.einreihen()` in
`notification_queue` ein; zugestellt wird zentral in `notify.zustellen()`, das
die Cron-Jobs am Ende ihres Laufs aufrufen. Ein eigener Cron dafür ist nicht
nötig — `check_committees` läuft um 7 Uhr und leert damit, was über Nacht liegen
blieb.

| Grenze | Regel |
|---|---|
| **Zwei am Tag** | pro Person, nicht pro Anlass. Was darüber hinausgeht, nimmt die letzte freie Zustellung als **ein Bündel** mit; ein Bündel zählt als eine Zustellung. Nichts geht verloren — der Rest kommt morgen. |
| **… außer termingebunden** | `kern.notify.TERMINGEBUNDEN` (derzeit nur `n5_vorabend`) hat einen **eigenen** Vorrat von zwei am Tag. Eine Vorabend-Erinnerung, die einen Tag später kommt, ist nicht verspätet, sondern wertlos — und weil der 18-Uhr-Lauf der letzte des Tages ist, verlor sie den Wettlauf um den gemeinsamen Topf regelmäßig (Prod, 16.08.2026: ab 18 Uhr fertig, zugestellt am Sitzungstag selbst). Innerhalb ihres Topfes gelten dieselben Regeln, also auch das Bündeln ab der dritten. Weil `notifications_sent_on()` je Topf nach `kind` zählt, bündelt `_zustellen_fuer()` nie über die Topfgrenze hinweg — ein gemischtes Bündel wäre in beiden Töpfen eine Zustellung. |
| **Nachtruhe 21–7 Uhr** | Ortszeit (`zoneinfo`, Europe/Berlin). Was abends anfällt, bekommt `deliver_after` auf 7 Uhr. |
| **Nie ohne Ereignis** | Es gibt keine Funktion, die ohne Ratsvorgang einreiht. Abzeichen und Quiz-Serien bleiben in der App. |
| **Immer ein Ziel** | `url` ist Pflichtfeld; `einreihen()` wirft ohne. Antippen öffnet den Beschluss oder die Tagesordnung, nie die Startseite. |

```
notification_queue
  id PK, owner_id, kind, title, body_html, url,
  created_at, deliver_after, sent_at, bundled
```

Zwei Regeln verhindern Dubletten: `check_committees` überspringt ein Konto, das
für dieselbe Sitzung schon einen Themen-Treffer hat (**Themen-Treffer gewinnt**),
und eine Änderungsmeldung geht nur noch **≤ 48 h vor der Sitzung** raus.

| Endpunkt | Zweck |
|---|---|
| `GET /api/account/notifications` | Anlässe mit Beschriftung, Vorgabe und Zustand + die geltenden Grenzen |
| `PUT /api/account/notifications` | Schalter setzen; unbekannte Schlüssel werden verworfen |

Die Oberfläche pflegt **keine** eigene Anlass-Liste — sie rendert, was der
Endpunkt liefert. Sonst fiele ein neu dazugekommener Anlass erst auf, wenn sich
jemand über eine unabschaltbare Meldung ärgert.

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
  Das ist der Auslöser für die Feier-Karte (`BadgeCelebrator`) — genau einmal.
- Einmal verdient bleibt verdient: Wer ein Thema löscht oder die Quiz-Serie
  reißt, behält das Abzeichen.

Die Feier selbst ist reines Frontend: eine Karte, die unten über den laufenden
Screen fährt (bewusst **kein** Vollbild — sie blockiert nichts und geht nach 6 s
von selbst), mit Konfetti *innerhalb* der Karte und einem Weg zur Sammlung.
Mehrere gleichzeitig verdiente Abzeichen laufen nacheinander statt gestapelt.
Welche gerade neu sind, merkt sich der Browser unter `ratslotse:badges-neu` und
zeigt sie in der Konto-Karte als **„NEU"** — bis die Sammlung einmal offen war.
Das ist bewusst gerätelokal: Es markiert „hier noch nicht angesehen", nicht
einen Kontostand.

### Onboarding

`web/backend/app/routers/onboarding.py`, Spalte `web_users.onboarding` (JSON:
`{"steps": [...], "celebrated": bool}`). Bewusst **serverseitig am Konto statt
im localStorage**, damit der Kurs „Erste Schritte mit Lotti" auf jedem Gerät
denselben Stand hat und nach Abschluss überall verschwindet.

- `GET /api/onboarding` liefert den Stand, `POST /api/onboarding` merged
  erledigte Schritte dazu und/oder setzt `celebrated`.
- Erlaubt sind nur die bekannten Schritte `frag`, `beschluesse`, `analyse`,
  `karten` — alles andere wird verworfen, damit die Spalte nicht
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

`Store.delete_web_user` räumt jede Tabelle aus `USER_OWNED_TABLES`
(`kern/store.py`) ab und löscht zuletzt die Zeile in `web_users` — derzeit
**18 Tabellen**. Diese Seite zählt sie bewusst *nicht* mehr einzeln auf: Die
frühere Aufzählung nannte sechs und war damit lange falsch. Maßgeblich ist die
Konstante, und dass sie vollständig bleibt, prüft
`test_delete_web_user_covers_every_user_table` gegen das Schema — wer eine neue
nutzerbezogene Tabelle anlegt, muss sie dort eintragen, sonst schlägt der Test
fehl. Anschließend geht eine Bestätigungs-Mail raus (Best-Effort). Die Löschmöglichkeit **in der App** ist
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

**Nicht** übernommen werden die **Kontaktdaten der Mandatsträger*innen** aus dem
Ratsinformationssystem (Adresse, Telefon, Beruf auf den Personenseiten) — das
ist eine bewusste Entscheidung der Stammdaten-Auswertung, siehe
[Ratsdokumente & Beschlüsse](/docs/beschluesse/).

Die vollständige, verbindliche Fassung steht auf der Datenschutzseite der App:
[ratslotse.de/datenschutz](https://ratslotse.de/datenschutz) (Quelle:
`web/frontend/app/datenschutz/page.tsx`).
