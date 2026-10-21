---
title: "Feature: MCP-Server"
description: Ratsdaten für den eigenen Agenten — persönliche Schlüssel, die Werkzeuge, ihre Grenzen und wie man Claude, ChatGPT oder Cursor anschließt.
---

Über das [Model Context Protocol](https://modelcontextprotocol.io) lässt sich
ein eigener Agent an die Ratsdaten anschließen, zum Beispiel Claude Desktop,
Claude Code, ChatGPT oder Cursor. Der Agent ruft dann selbst die Werkzeuge
von Ratslotse auf: Er sucht Beschlüsse, liest Vorlagen und Tagesordnungen und
verfolgt eine Vorlage durch die Gremien.

## Zugang

Der Zugang hängt am Recht `mcp`, das die Rolle **„MCP-Zugang“** trägt. Admins
vergeben sie im Admin-Panel unter *Web-Nutzer\*innen*; sie kommt zusätzlich
zu jeder anderen Rolle. Admins haben das Recht ohnehin.

Wer die Rolle hat, findet in den Einstellungen die Karte **„Eigener Agent
(MCP)“** und stellt sich dort Schlüssel aus: bis zu fünf je Konto, einen je
Agent, damit man jeden einzeln zurückziehen kann. Der Schlüssel beginnt mit
`rlmcp_` und erscheint **genau einmal**. Gespeichert wird nur sein SHA-256;
die Liste zeigt die ersten Zeichen, das Datum der letzten Nutzung und die
Zahl der Aufrufe.

Wird einem Konto die Rolle entzogen, bleibt der Schlüssel stehen, wirkt aber
nicht mehr (Antwort 403). Gibt man sie zurück, gilt er wieder. Wird das Konto
gelöscht, gehen die Schlüssel mit (`USER_OWNED_TABLES`).

Solange der Schalter `mcp-server` aus ist, antworten der Server und die
Schlüssel-Endpunkte mit 404.

## Anschließen

Adresse: `https://ratslotse.de/api/mcp` (auf dev entsprechend
`dev.ratslotse.de`). Transport ist *Streamable HTTP*, die Anmeldung läuft
über die Kopfzeile `Authorization: Bearer rlmcp_…`.

```bash
claude mcp add --transport http ratslotse https://ratslotse.de/api/mcp \
  --header "Authorization: Bearer rlmcp_…"
```

Andere Clients fragen nach denselben zwei Angaben, also Adresse und
Kopfzeile. Clients, die keine feste Kopfzeile können, melden sich per OAuth
an (s. u.). Das Sitzungs-Cookie öffnet den Server **nicht**: Sonst könnte jede
fremde Seite im Namen einer angemeldeten Person Anfragen stellen.

## Anmelden per OAuth (ChatGPT, Claude im Browser)

ChatGPT schickt einem eigenen MCP-Server keinen festen Schlüssel. Es
kennt nur OAuth 2.1 mit PKCE: Laut OpenAI kann ChatGPT „can not present
custom API keys“. Ratslotse ist deshalb selbst Autorisierungsserver
(`web/backend/app/routers/mcp_oauth.py`). In ChatGPT trägt man im
Entwicklermodus nur die Adresse ein, unter chatgpt.com/plugins und auf dem
iPad in Safari. Danach geht es so weiter:

1. Der Agent ruft `/api/mcp` ohne Token. Die 401-Antwort nennt in
   `WWW-Authenticate` die Schutz-Metadaten
   `/.well-known/oauth-protected-resource` (RFC 9728). Von dort kommt er zu
   `/.well-known/oauth-authorization-server` (RFC 8414). Beide liegen im
   Backend; Next leitet sie durch, weil der Proxy nur `/api` weiterreicht.
2. Er meldet sich als Client an, auf einem von zwei Wegen. Entweder per
   *Dynamic Client Registration* (`POST /api/oauth/register`), oder er nennt
   als `client_id` eine https-Adresse, unter der sein Steckbrief liegt
   (*Client ID Metadata Document*; ChatGPT bevorzugt das).
3. Der Browser öffnet `/oauth/freigeben`. Wer nicht angemeldet ist, meldet
   sich erst an und landet danach wieder dort. Die Seite zeigt, was der
   Agent darf und was nicht, und vor allem, **wohin es danach zurückgeht**.
   Den Namen gibt sich ein Agent selbst, die Adresse nicht. Freigeben kann
   nur ein Konto mit dem Recht `mcp`.
4. Der Agent tauscht den Code gegen ein Zugangs-Token (`rloat_…`, gültig eine
   Stunde) und ein Erneuerungs-Token (`rlort_…`). Das Erneuerungs-Token
   verfällt nach 30 Tagen ohne Nutzung und wird bei jedem Gebrauch ersetzt.

Die Grenzen:

- **Rücksprungadressen exakt**, so wie registriert. Erlaubt sind https,
  `http://localhost` bzw. `127.0.0.1` und das eigene Schema einer App
  (`cursor://…`). Die letzten beiden zeigt die Seite mit einer Warnung, weil
  dort ein beliebiges Programm auf dem Gerät mithören kann. Stimmt die
  Adresse nicht, leitet die Seite **nicht** weiter, sondern zeigt nur den
  Fehler.
- **PKCE mit S256 ist Pflicht.** Andere Verfahren nimmt der Server nicht an.
- **Audience:** Ein Token gilt nur für `/api/mcp` dieser Instanz. Ein
  `resource`-Parameter für etwas anderes wird abgewiesen.
- **Einmal heißt einmal.** Wird ein Code zum zweiten Mal eingelöst oder ein
  abgelöstes Erneuerungs-Token wieder benutzt, fällt die ganze Freigabe.
- **Bremsen:** Registrierung 10 je Stunde und Adresse, insgesamt 200 je
  Stunde. Token-Endpunkt 60 je Minute, und nach 20 Fehlversuchen in zehn
  Minuten ist für diese Adresse Pause. Freigaben 30 je Stunde und Konto.
- **Steckbrief-Abruf ohne Umweg ins eigene Netz:** nur https, nur öffentliche
  Adressen, keine Weiterleitung, drei Sekunden, zehn Kilobyte, einen Tag
  zwischengespeichert.
- **Trennen:** Die Einstellungen listen die verbundenen Agenten (höchstens
  zehn); jeder lässt sich einzeln trennen. „Überall abmelden“ und ein neues
  Passwort beenden alle Freigaben, ebenso ein entzogenes Recht. Wird das
  Konto gelöscht, gehen sie mit (`USER_OWNED_TABLES`).

Gespeichert werden nur die SHA-256 von Code und Tokens. Die Tokens sind
opak, keine JWT, damit ein Widerruf sofort wirkt. Per DCR angelegte
Clients, die nach einem Tag niemand freigegeben hat, räumt der Server
wieder ab.

## Auswertung

Jeder Werkzeugaufruf landet als Zeile in `mcp_calls` (`ratslotse.sqlite`). Das
Admin-Panel zeigt die Auswertung unter *Nutzung → Agenten (MCP)*: Aufrufe je
Tag, Werkzeuge mit Fehlern und leeren Antworten, den Einstieg einer Sitzung,
die Schritte darin („search_decisions → get_decision“), welche Argumente
gesetzt werden, wonach gesucht wird, was ohne Treffer bleibt, und welche
Konten mit welchen Agenten fragen. Eine Sitzung ist eine Folge von Aufrufen
derselben Verbindung ohne Pause über 30 Minuten.

Gespeichert werden **mit Konto** (Tims Entscheidung 18.10.2026) Zeitpunkt,
Werkzeug, der Name des Agenten, Dauer, Ergebnis (`ok`, `tool_error`,
`internal`), die Trefferzahl und die **Namen** der gesetzten Argumente. Ihre
Werte werden nicht gespeichert, mit einer Ausnahme: den Suchtext (`query`).
Der wird auf 200 Zeichen gekürzt, Kontaktdaten werden maskiert, auch eine
nackte Telefonnummer, die `kontaktdaten.maskieren` allein nicht erkennt.
Nach 90 Tagen ist der Suchtext leer, nach einem Jahr ist die Zeile weg, und
mit dem Konto geht alles (`USER_OWNED_TABLES`). Die Freigabe-Seite, die
Einstellungskarte und die Datenschutzerklärung sagen das, bevor jemand
verbindet.

Geschrieben wird gesammelt, nie während der Antwort: höchstens alle
15 Sekunden bzw. alle 50 Aufrufe, ohne auf eine Schreibsperre zu warten.
Gelingt es nicht, bleibt der Stapel liegen und geht mit dem nächsten.

## Werkzeuge

| Werkzeug | Was es liefert |
|---|---|
| `search_decisions` | Volltextsuche (deutsch, BM25) über Beschlüsse, filterbar nach Gremium, Ergebnis, Themenfeld, Zeitraum; blättert mit `offset` |
| `get_decision` | Ein Beschluss vollständig: Text, Abstimmung, Antragsteller, Kurzfassung, einfache Sprache, Änderungsanträge, Links |
| `get_template` | Eine Vorlage mit Beschlussvorschlag, Finanz- und Klimaauswirkungen, Volltext in Stücken zu 12.000 Zeichen und der Liste ihrer Anlagen |
| `get_attachment` | Der Text einer Anlage; eine noch nicht geladene holt Ratslotse beim ersten Abruf aus dem Ratsinformationssystem |
| `get_protocol_section` | Der Protokollabschnitt zu einem Tagesordnungspunkt: Debatte, Wortbeiträge, Abstimmung |
| `get_template_history` | Die Beratungsfolge einer Vorlage durch alle Gremien |
| `list_committees` | Alle Gremien mit nächster Sitzung |
| `list_sessions` | Sitzungen eines Gremiums, vergangen und geplant |
| `get_agenda` | Die Tagesordnung einer Sitzung samt Ergebnissen, Vorlagennummer und den Anlagen, die nur am Punkt hängen |
| `count_decisions` | Beschlüsse eines Jahres nach Ergebnis, Themenfeld, Gremium |

Mit dem Recht `budget` kommen sechs Haushaltswerkzeuge dazu — dieselben
Abfragen wie Lottis Haushaltswerkzeuge (`council/lotti_werkzeuge.py`,
`*_daten`), hier mit einem Beleg je Wert (`source` verweist in `sources`):

| Werkzeug | Was es liefert |
|---|---|
| `budget_search` | Suche in den Haushaltsdaten, derselbe Block wie in der KI-Frage (jede Zahl unter ihrem Jahr, Plan und Ist getrennt) |
| `budget_series` | Eine Kennzahl über Jahre: Schulden, Steuern, Investitionen, Personal, Ergebnis, Einwohner, Stellen, Hebesätze |
| `budget_product` | Geplante Aufwendungen und Erträge einer Aufgabe (Produkt) über Planjahre |
| `enterprise_plans` | Wirtschaftspläne der Betriebe (Erträge, Aufwendungen, geplantes Ergebnis) |
| `fee_calculations` | Gebührenkalkulationen: zu deckende Kosten, Gebührensatz |
| `cash_position` | Kassenstand je Monatsende |

`rechnen` und `seite_lesen` aus Lottis Satz fehlen bewusst: Rechnen kann der
Agent selbst, und die Haushaltsseiten sind Oberfläche, keine Daten.

Alle Werkzeuge antworten mit **JSON**, auch die vier, deren Abfragen Lotti
teilt (`council/lotti_werkzeuge.py`, die `…_daten`-Funktionen): Lotti formt
daraus ihren Fließtext, der MCP-Server gibt die Daten selbst aus. Bis 10/2026
kamen diese vier als Lottis Text — mit TOP-Titeln, die bei 160 Zeichen mitten
im Wort endeten. Titel kommen jetzt ungekürzt.

Der Vorlagen-Volltext (`get_template`) ist von den Spuren des PDF-Textlayers
befreit: keine Seitenköpfe („Ausdruck vom … Seite 1/2“), Zeilen eines Absatzes
als Fließtext, Silbentrennung geheilt, die gesperrt gesetzte Unterschrift
lesbar („D r .  S v e n  U h r h a n“ → „Dr. Sven Uhrhan“). Anders als der
Auszug auf der Beschluss-Seite bleibt dabei **alles** stehen, auch Kopf und
angehängte Anlagen.

## Grenzen

- **Nur lesend.** Nichts Kontogebundenes (Themen, Lesezeichen, Gespräche).
  **Den Haushalt nur mit dem Recht `budget`** (seit 21.10.2026, Ratsmitglieder
  und Fachpublikum): Die sechs Haushaltswerkzeuge tragen `recht="budget"`, und
  ein Konto ohne das Recht sieht sie weder in `tools/list` noch in der
  Anleitung; ein Aufruf antwortet wie für ein unbekanntes Werkzeug.
  `tests/test_mcp.py` prüft am Quelltext, dass kein Werkzeug eine
  kontogebundene Tabelle anfasst und keines ohne Recht eine Haushaltstabelle.
- **Kein Sprachmodell auf unserer Seite.** Das Denken macht der Agent mit
  seinem eigenen Modell; bei uns laufen SQLite und die Volltextsuche. Die
  KI-Frage und die ausführliche Recherche fehlen deshalb mit Absicht, sonst
  bezahlten wir fremde Schleifen.
- **Fremdtext wird entschärft.** Texte aus dem Ratsarchiv laufen durch
  denselben Anweisungsfilter wie bei Lotti (`kern/foreign_text.py`).
- **Bremse je Konto:** 120 Aufrufe in der Minute, 3.000 am Tag.

## Protokoll

Die Hülle in `web/backend/app/routers/mcp.py` ist selbst geschrieben, nicht
aus dem `mcp`-Paket. Für einen zustandslosen Server, der nur Werkzeuge
anbietet, braucht es vier Methoden (`initialize`, `ping`, `tools/list`,
`tools/call`) und die Regel „Benachrichtigung → 202“. Das Paket brächte
dafür ein Dutzend Abhängigkeiten, einen eigenen ASGI-Unterbau und einen
Sitzungsspeicher auf den Server. Antworten kommen immer als
`application/json`, ein `GET` bekommt 405, denn einen vom Server gesendeten
Strom gibt es nicht. Verhandelt werden die Fassungen `2025-11-25`,
`2025-06-18` und `2025-03-26`.

## Protokolle und Anlagen

Was ein Beschluss **bedeutet**, steht in der Vorlage; **warum** er so ausfiel,
steht nur im Protokoll. `get_protocol_section` schneidet den Abschnitt eines
Punkts aus dem öffentlichen Protokoll — mit demselben Schnitt, mit dem die
Haushaltsdebatte ihre Reden findet (`council/haushaltsdebatte.py::top_abschnitt`,
an den Ankern „zu 7.2“). Gemessen über 400 zufällige Beschlüsse mit Protokoll:
**388 finden ihren Abschnitt** (97 %), Median rund 1.000 Zeichen. Gemeinsam
beratene Punkte (Stadion: 6.1 bis 6.3) tragen die ganze Debatte und können
30.000 Zeichen lang werden; sie kommen in Stücken. Nichtöffentliche Punkte
(„N 11“) weist das Werkzeug ab.

**Anlagen auf Zuruf.** Von den Anlagen einer Vorlage sind die meisten schon
gelesen (`text: "available"`); was der Backfill noch nicht geholt hat
(`"on_demand"`), lädt `get_attachment` beim ersten Abruf und legt den Text in
den Bestand — der zweite Abruf und die KI-Frage haben ihn dann ohne Download.
Ob ein PDF als gelesen gilt oder als Scan, entscheidet dieselbe Regel wie im
Backfill (`council/anlagentext.py`); ein Scan wird als `empty` festgehalten
und nicht bei jedem Abruf neu geladen. Gedeckelt ist das **über alle Agenten
zusammen**: mindestens eine Sekunde zwischen zwei Downloads, höchstens 120 je
Stunde. Das Ratsinformationssystem ist die Quelle des ganzen Bestands, eine
Sperre dort träfe den Ingest.

**Anlagen am Tagesordnungspunkt.** Dringlichkeits- und Änderungsanträge,
Konzepte zu Fraktionsanträgen und Einwohnerfragen hängen im
Ratsinformationssystem oft direkt am Punkt, **ohne Vorlage** — gemessen 266
solcher Unterlagen im Bestand. `get_agenda` listet sie je Punkt, aber nur die,
die es nicht schon über `get_template` gibt (das System wiederholt am Punkt
die Vorlage und ihre Anlagen). Beide Arten spricht `get_attachment` über
**dieselbe Kennung** an: die Dokumentnummer aus `getfile.php?id=…`. Ein
nachgeladener Text überlebt das tägliche Neu-Einlesen der Sitzung
(`save_session` übernimmt ihn über die URL).

**Was nicht hinausgeht:** Telefonnummern und E-Mail-Adressen werden in
Anlagen- und Protokolltext maskiert, wie beim Suchindex
(`council/kontaktdaten.py::maskieren`). Kontonummern und Anschriften stehen
ohnehin nicht im Bestand, sie fallen schon beim Speichern heraus.

