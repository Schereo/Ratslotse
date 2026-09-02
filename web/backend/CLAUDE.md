# Regeln für `web/backend/`

FastAPI. Diese Schicht bedient **zwei** Clients, das Web-Frontend und die
native iOS-App. Was hier still die Form ändert, macht dort eine leere Seite.
Allgemeines: [`../../CLAUDE.md`](../../CLAUDE.md).

## Vorher: echte Daten holen

Ein Endpunkt gegen eine leere Datenbank sagt wenig. Ob eine Abfrage bei 8.000
Beschlüssen noch schnell ist, ob ein Feld wirklich nie `null` wird, ob die
Antwort in eine Seite passt — das zeigt erst der Bestand:

```bash
python scripts/lokale_daten.py hol && python scripts/lokale_daten.py setz
python scripts/saat_konten.py
```

Nützlich auch beim Beschreiben einer Antwortform: Die Nullbarkeit eines Feldes
lässt sich am Bestand **messen** statt raten — genau so sind die Formen in
`antworten.py` entstanden, die zuletzt dazugekommen sind. Näheres in der
Wurzel-[`CLAUDE.md`](../../CLAUDE.md).

## Ein neuer Endpunkt ist erst fertig, wenn der Vertrag stimmt

1. Router unter `app/routers/`, und in `app/main.py` per `include_router`
   registrieren. **Ein zweites Router-Objekt in derselben Datei existiert
   nicht, solange es kein eigenes `include_router` hat.**
2. **Rückgabe-Annotation ist Pflicht**, und zwar eine Form aus
   `app/antworten.py` — niemals `-> dict`. Sonst steht im Vertrag nur
   „irgendein Objekt", und kein Client kann daraus generieren. Ein Test hält
   das fest; die Ausnahmeliste ist seit 09/2026 leer, ein neuer Eintrag ist
   eine bewusste Entscheidung.
3. **Neu schneiden und mitcommitten:**
   ```bash
   python scripts/openapi_schnitt.py
   cd web/frontend && npm run api:typen
   ```
   Oder einfach `python scripts/pruefe.py --schnell`, das meldet beides.

## Zwei Fallen in den Antwortformen

- **Ein fehlender Pflichtschlüssel ist ein 500er**, kein leeres Feld. Alles
  Optionale gehört als `NotRequired[...]`, alles Nullbare als `| None`. Ein
  als `int` deklariertes Feld hat jede Woche ohne Tagesordnung zerlegt.
- **Nicht deklarierte Felder werden still ENTFERNT**, nicht gemeldet. Ein
  vergessenes Feld ließ beide Frontends „0 Tagesordnungspunkte" anzeigen — und
  weil die Testfixturen beider Seiten das Feld selbst setzten, blieb alles
  grün. Deshalb steht für breite `SELECT *`-Nutzlasten bewusst
  `dict[str, Any]` statt einer Aufzählung, die beim nächsten `ALTER TABLE`
  Daten verliert.

Nullbare Felder müssen im Vertrag als `type: [T, "null"]` landen, nicht als
`anyOf` mit null: Der Swift-Generator lässt solche Felder sonst **still weg**.

Antworten ohne JSON brauchen **beides**: `response_class=…` und
`responses=…` am Dekorator, plus den Eintrag in der Ausnahmeliste des
Vertragstests.

## Schutz vergisst sich lautlos

`Depends(require_active)` für „eingeloggt", `require_admin` für Admin,
`optional_user` für öffentliche Seiten mit persönlichem Zusatz. Ein neuer
Endpunkt, bei dem die Dependency fehlt, ist offen — und fällt durch **kein**
generisches Netz: Es gibt nur endpunkt-eigene Tests, ein versehentlich offener
neuer Endpunkt bleibt grün. Beim Anlegen also ausdrücklich entscheiden, ob er
öffentlich sein soll, und die Entscheidung in den Pull Request schreiben.

Gesperrte oder unbestätigte Konten bekommen **403, nicht 401** — die iOS-App
unterscheidet daran, ob sie zur Anmeldung schickt oder das Konto erklärt.

## Streams und Proxys

Der Strom der KI-Frage darf durch **keine** `BaseHTTPMiddleware` laufen, die
puffert ihn. Deshalb ist die Sitzungsverlängerung rohes ASGI. Streamende
Antworten tragen `Cache-Control: no-cache` **und** `X-Accel-Buffering: no`.

## Echte IP und Rate-Limit

`X-Forwarded-For` **nie selbst auslesen** — die echte Adresse setzt die
Proxy-Middleware, und ein selbstgelesener Header ist ein Rate-Limit-Bypass.
Teure, angemeldete Endpunkte zählen pro Konto statt pro IP, weil
Mobilfunkanbieter viele Geräte hinter einer Adresse bündeln.

## Datenbank

Router gehen über `Depends(get_store)` / `Depends(get_council_store)`. Roh-SQL
im Router gibt es an vier begründeten Stellen; neue gehören nicht dazu.
