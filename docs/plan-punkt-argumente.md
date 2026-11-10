# Plan: Argumente und Fraktionen auf der Punkt-Seite

Stand 10.11.2026. Schritt 6 aus [`plan-sitzungsseite-kurs.md`](plan-sitzungsseite-kurs.md).
Der Plan dort sagt: eigenes Vorhaben, vor dem ersten Code dieser kurze Plan —
mit Rohstoff, Ablage, Prompt und vor allem der **Messung**. Gebaut wird erst,
wenn Tim ihn abgenommen hat und die Messung ihr Ziel erreicht.

## 1. Was die Punkt-Seite zeigen soll

Zwei Reiter neben „Vorgeschichte“ und „Unterlagen“ (Bild:
`entwurf-sitzungsseite/bilder/punkt-desktop-1…2.png`):

- **Argumente:** „Worüber gestritten wird“ mit Zählung („7 dafür · 9 dagegen
  oder mit Bedenken“), darunter Streitpunkte als Karten — je eine Frage, zwei
  Spalten „Dafür“ und „Dagegen“, je Aussage Urheber und Fundstelle, am Fuß
  „Dazu fragen“. Danach „Weitere Argumente“.
- **Fraktionen:** je Fraktion ihre Wortmeldungen als Paraphrasen mit Person,
  Gremium und Datum. Abstimmungen nur als Satz aus dem Protokoll.

Feste Hinweise: „Ratslotse ergänzt keine eigenen Argumente.“ · „Argumente sind
Aussagen der Beteiligten, keine geprüften Tatsachen.“ · „Paraphrasen, keine
wörtlichen Zitate. Eine einzelne Wortmeldung ist nicht immer die Linie der
ganzen Fraktion.“

## 2. Rohstoff — gemessen am dev-Abzug (08.11.2026)

| Quelle | Bestand | Für |
|---|---|---|
| `council_speeches` (`kind = 'speech'`) | 35.953 Wortbeiträge in 6.884 Tagesordnungspunkten, 2018–09/2026; je Beitrag Person, Partei, paraphrasierter Text, Seite im Protokoll | Argumente aus der Debatte, Fraktionen |
| `council_templates.raw_text` | 5.219 von 5.277 Vorlagen mit Volltext (> 500 Zeichen) | „Was die Verwaltung sagt“, Argumente der Verwaltung |
| Anlagen-Volltexte (`council_attachments.raw_text`) | im Abzug geleert, auf dev/Prod vorhanden | Anträge der Fraktionen (Begründung) |
| `council_speeches` (`kind = 'pledge'`) | 1.447 Zusagen der Verwaltung | **nicht** für diesen Schritt — aber die Quelle, die Plan 3.16 vermisst hat |

**Wie viele Punkte überhaupt Stoff haben** (983 Punkte mit Vorlage, 11/2025 bis
11/2026, Wortbeiträge über alle Stationen derselben Vorlage):

| Wortbeiträge | Punkte | Anteil |
|---|---:|---:|
| keine | 557 | 57 % |
| 1–3 | 140 | 14 % |
| 4 und mehr | 286 | 29 % |
| … davon aus mindestens zwei Fraktionen | 222 | 23 % |

Heißt: Für gut drei Viertel der Punkte gibt es **keinen** Streit, den man
zeigen könnte — der Reiter fehlt dort (Mindestmenge, s. u.). Und vor der
ersten Beratung gibt es nur die Vorlage und den Antrag; „Worüber gestritten
wird“ ist dann leer, „Was beantragt wird“ und „Was die Verwaltung sagt“ nicht.

## 3. Ablage

Neue Tabelle `agenda_item_arguments` in `council.sqlite` (Schema **und**
Migration, `council/CLAUDE.md`), geschlüsselt nach Vorlage (`template_number`)
bzw. bei Anträgen ohne Vorlage nach dem datierten Titel — dieselbe Zuordnung
wie beim gelben Punkt und der Vorgeschichte. So gilt eine Auswertung für alle
Stationen einer Vorlage und wird nur neu gerechnet, wenn eine Station mit neuen
Wortbeiträgen dazukommt (`sources_hash` über die Kennungen der Quellen).

Je Zeile ein JSON-Dokument:

```
{ "issues": [ { "question": "...", "pro": [Aussage], "contra": [Aussage] } ],
  "further": { "pro": [Aussage], "contra": [Aussage] },
  "factions": [ { "party": "SPD", "statements": [Aussage] } ] }
Aussage = { "text": Paraphrase, "speaker": str|null, "party": str|null,
            "body": Gremium oder Dokument, "date": "YYYY-MM-DD",
            "source": { "kind": "speech"|"template"|"attachment", "id": int, "page": int|null } }
```

**Ohne `source` keine Aussage** — der Parser verwirft sie, bevor sie
gespeichert wird. `party` nur, wenn das Protokoll sie nennt; sonst
„Fraktion im Protokoll nicht genannt“.

## 4. Prompt

Neuer Schlüssel `punkt_argumente` in `kern/prompts.py`, ein Aufruf je Vorlage,
Modell wie die Kurzfassungen (`COUNCIL_TOPIC_MODEL`, ohne Nutzereingabe —
`llm.OHNE_NUTZEREINGABE`). Eingabe: die nummerierten Wortbeiträge aller
Stationen (Person, Partei, Gremium, Datum, Text, Kennung), der Abschnitt
„Begründung“ der Vorlage und — wo vorhanden — die Begründung des Antrags,
beide als Fremdtext markiert (`kern/foreign_text.py`).

Regeln im Prompt (und im Parser geprüft):

- Jede Aussage zitiert die Kennung ihrer Quelle; Kennungen, die nicht in der
  Eingabe stehen, verwirft der Parser.
- Keine eigenen Argumente, keine Gewichtung, keine Empfehlung, keine Wertung.
- Paraphrase in Du-freier, neutraler Sprache, höchstens zwei Sätze.
- Ein Streitpunkt nur, wenn es zu ihm Aussagen auf **beiden** Seiten gibt.
- Kein Stimmverhalten; Abstimmungen kommen nicht aus dem Modell, sondern aus
  `council_decisions` (Satz aus dem Protokoll).
- Bei einem **abgelehnten** oder vertagten Beschluss bekommt das Modell das
  Ergebnis mit (`outcome_note`, `council/CLAUDE.md`), und die Textart kommt in
  `tests/test_texte_kennen_ergebnis.py`.

## 5. Messung — vor jedem Ausrollen

**Stichprobe:** 20 Punkte aus dem Bestand mit mindestens vier Wortbeiträgen
aus mindestens zwei Fraktionen, gemischt nach Gremium (Rat, Verkehr,
Stadtplanung, Soziales, Finanzen) und Ergebnis (angenommen, abgelehnt,
vertagt). Darunter fest: Soziales D-Ticket (Vorlage 26/0719 und Vorgänger),
Weißenmoorstraße, Grundsteuer C — die Fälle aus dem Entwurf.

**Von Hand gelesen, je Aussage drei Fragen:**

1. Steht sie in der genannten Quelle? (belegt / nicht belegt)
2. Gehört sie der genannten Person bzw. Fraktion? (richtig / falsch / Fraktion fehlt zu Recht)
3. Stimmt die Paraphrase inhaltlich? (treu / verzerrt)

Dazu je Punkt: Fehlt ein Argument, das in den Quellen deutlich steht?
Steht ein Streitpunkt da, den es nicht gibt?

**Tor:** 100 % belegt (eine erfundene Aussage reicht, um nicht auszurollen),
mindestens 95 % richtig zugeordnet, mindestens 90 % treu, höchstens ein
erfundener Streitpunkt über alle 20. Gemessen wird mit
`eval/run_punkt_argumente.py` (Ausgabe als Tabelle zum Abhaken, die Urteile
von Hand in `eval/punkt_argumente_gold.json`), der Lauf protokolliert seine
Kosten.

**Kosten:** Schätzung je Vorlage ~6.000 Eingabe-Token; 20 Punkte liegen unter
0,50 $. Der Bestandslauf über die 286 Punkte mit Stoff aus einem Jahr wird
vorher gemessen (Tims Regel: ab 1 $ fragen).

## 6. Darstellung — was feststeht

- **Mindestmenge:** zwei Seiten mit je zwei Aussagen — darunter erscheint der
  Reiter „Argumente“ nicht. „Fraktionen“ erscheint ab zwei Fraktionen mit je
  einer Wortmeldung.
- Paraphrasen kursiv, ohne Anführungszeichen (DESIGNSPRACHE § 1).
- Jede Aussage mit „— Person (Fraktion) · Gremium · Datum“ und einem Link auf
  die Fundstelle (Protokoll-Seite, Vorlage).
- „Dazu fragen“ an einem Streitpunkt setzt den Bezug-Chip im Ratsgespräch
  (wie die Box „Frag den Rat“, Schritt 4) und schickt den Streitpunkt als
  `element_title`/`element_text` mit.
- Hinter einem eigenen Schalter `punkt-argumente`.

## 7. Offene Fragen an Tim

1. Tor wie oben (100 / 95 / 90 %) — oder strenger bei der Zuordnung?
2. Sollen „Was beantragt wird“ und „Was die Verwaltung sagt“ (aus Antrag und
   Vorlage, ohne Debatte) im selben Lauf entstehen? Sie hätten Stoff für fast
   jeden Punkt, auch vor der ersten Beratung.
3. Die 1.447 „Zusagen der Verwaltung“ (`kind = 'pledge'`) lösen Plan 3.16 auf
   — eigener kleiner Schritt danach?
