# Plan: Vorlagen aufbereiten, damit die Unterlagen nur noch zum Gegenlesen dienen

Stand 12.11.2026. Grundlage sind drei Entwürfe und zwei Gutachten dazu. Alle Zahlen
mit ✔ habe ich am 12.11. selbst am lokalen Abzug (`data/council.sqlite`), im Code
oder über den MCP-Server nachgemessen. Gebaut wird erst, wenn Tim den Plan abnimmt.
Ein Modell-Feld geht erst raus, wenn es sein Tor im Gold-Set erreicht hat
(Abschnitt 7).

**Ziel (Tim, 12.11.):** Die Informationen aus Vorlagen, Anlagen und
Änderungsanträgen werden so aufbereitet, dass man die Unterlagen nur noch
**zum Gegenlesen** öffnen muss.

## 0. Kurzfassung

1. **Zuerst ohne Modell.** Zwei Ernte-Fehler verderben heute die Eingabe aller
   Modelle. Der Beschlussvorschlag läuft in 781 Vorlagen in den „Anlass“ hinein,
   und in weiteren rund 200 bricht er zu früh ab. Änderungsanträge werden oft
   nicht als Anträge erkannt. Beide Fixes gehen gegen `main`. Danach zeigen
   Punkt-Seite und App, was die Vorlage schon trägt: Beschlussvorschlag, Kosten,
   Klima, Amt und Antragsteller.
2. **Feste Abschnitte statt einer Linkliste.** Die Punkt-Seite bekommt den Block
   **„Aus den Unterlagen“**. Seine Abschnitte folgen den Fragen der Leserin: was
   beschlossen werden soll, was die Änderungsanträge wollen, was sich ändert, was
   es kostet, wen es betrifft, was die Verwaltung sagt, was danach passiert. Der
   Reiter „Unterlagen“ wird zur **Gegenlese-Liste**.
3. **Jede Angabe trägt einen Beleg aus Zitat, Dokument und Seite.** Eine Prüfung
   ohne Modell verwirft alles, was nicht wörtlich dasteht. Die Fußnote [n] trägt
   dieselbe Nummer wie die Unterlage in der Gegenlese-Liste. Ihr Link springt auf
   die Seite im PDF. **Gegengelesen wird damit die einzelne Aussage, nicht das
   ganze Dokument.**
4. **Ein Modellaufruf je Vorlage für alle Abschnitte.** Gegenüber getrennten
   Aufrufen sind das rund 70 % weniger Kosten. Änderungsanträge bekommen je
   Antrag einen eigenen kleinen Aufruf, sobald sie eintreffen.
5. **Cron für kommende Sitzungen, Abruf nur als Rückfall.** Nur auf Abruf wäre
   **nicht billiger**, denn Web-Aufrufe laufen ohne Flex. Der Text fehlte dann
   außerdem in Mails, App, MCP, bei Lotti und für alle ohne Konto.
6. **Kosten rund 2,6 $ im Jahr** mit Rückfall und Puffer, einmalig rund 1,3 $.
   Teuer würde nur ein Richter-Modell. Gemessen wird deshalb ohne Richter-Modell.

---

## 1. Ziel und Befund

### 1.1 Was „nur noch gegenlesen“ heißt

- **Lesen auf der Seite, Gegenlesen am Beleg.** Jede Aussage ist ein kurzer,
  neutraler Satz mit wörtlichem Zitat aus einem bestimmten Dokument auf einer
  bestimmten Seite. Klickt man auf [n], öffnet sich ein Popover:
  - oben das Zitat in Anführungszeichen mit Zitatkante,
  - darunter „Vorlage 26/0796 · S. 2“,
  - darunter gestrichelt „im PDF öffnen“ (`getfile.php?id=…&type=do#page=2`).
- **Vor der Sitzung so viel wie danach.** Kosten, Klima, Amt und Begründung stehen
  mit der Vorlage fest, also Wochen vor dem Protokoll.
- **Änderungsanträge verstehen, ohne sie zu öffnen** (Tims Beispiel). Gezeigt
  wird, wer was an welcher Stelle will, alt gegen neu, und nach dem Protokoll das
  Ergebnis.
- **Nichts wird geglättet.** Nennen Vorlage und Anlage verschiedene Werte, stehen
  beide da, je mit Beleg. Beispiel B-Plan 26/0592: 8,6 ha gegen „etwa 8,5 Hektar“.
- **Ehrlich, wenn etwas fehlt.** Eine Abwesenheit wird nur behauptet, wenn sie
  belegt ist („laut Vorlage keine Kosten“) oder wenn alle Lesestoff-Dokumente
  ganz gelesen wurden. Ein Scan ohne Textebene steht als Eigenschaft des Dokuments
  da, nicht als Lücke im Text.

### 1.2 Befund (Stand 12.11.2026)

**Volumen ✔.** In den letzten 365 Tagen gab es:

- 1.929 öffentliche Punkte,
- **672 verschiedene Vorlagen**, im Mittel 5.073 Zeichen (≈ 1.400 Token), die
  längste mit 26.472 Zeichen,
- **850 Anlagen mit 20.841 Seiten**.

Eine Vorlage steht im Mittel 1,39-mal auf einer Tagesordnung. 2025/26 waren es
655 Berichts- und 430 Beschlussvorlagen ✔. 1.020 von 1.089 tragen „Anlass:“, 366
den Abschnitt „Abwägung und Bewertung“ ✔.

**Was die Seiten heute zeigen**

- **Punkt-Seite:** „Das Wichtigste in Kürze“ (Kartentext oder Titel-Kurzfassung),
  „Warum wichtig“ und Links. Von 129 öffentlichen Punkten mit Vorlage seit dem
  15.09. haben 88 einen Kartentext ✔. Punkte ohne Vorlage (Fraktions- und
  Dringlichkeitsanträge) haben keinen.
- **Beschlussvorschlag:** Er wird geerntet (`council_templates.proposed_decision`),
  aber auf keiner Seite und in der App nicht gezeigt.
- **Kosten, Klima, Amt, Sachverhalt:** nur auf der Beschluss-Seite, also erst
  nach dem Protokoll.
- **App:** `AgendaItemModels.swift` kennt nur `summary`, also die
  Titel-Kurzfassung ✔. `social_text` und `important_reason` liest sie nicht.
- **Änderungsanträge:** Vor der Sitzung erscheint nur das rohe Label. Danach gibt
  es nur den Titel der Teilabstimmung, ohne Link aufs PDF. Bei allen 871
  Teilabstimmungen ist `official_text` leer ✔. 2026 sind es 84 an 32 Punkten ✔.
- **Beschluss-Seite:** Die Liste „Anlagen zum Beschluss“ ist leer. `decision/view.tsx:936`
  liest `data.anlagen`, der Router liefert `attachments` (`council.py:3129`) ✔.
- **Unterlagen am Punkt:** Die Vorlage steht doppelt da, einmal als vo0050-Link,
  einmal als Punkt-Anlage „Vorlage“ ✔.

**Fehler in der Ernte, die vor jeder KI-Aufwertung liegen**

1. **Der Beschlussvorschlag ist oft falsch geschnitten ✔.** `_VORSCHLAG_RE` endet
   an `ernte._ENDE`, und dort fehlen Überschriften wie „Anlass“. Zugleich stehen
   dort `[a-c]\)\s` und `Seite:\s*\d` als Blockende.

   | Fehlerart | Bestand | Beispiel |
   |---|---:|---|
   | läuft in „Anlass:“ hinein | **781 von 2.368** (Jahrgänge 2025/26: 368 von 443) | 26/0796 |
   | endet vor „b)“ einer eigenen Aufzählung, die nicht „b) Klima“ ist | 122 | **26/0674 Jahresabschluss**: Nur Ziffer a) bleibt, der Fehlbetrag von −24.822.337,17 € fehlt |
   | endet am Seitenkopf mitten im Vorschlag | ≈ 76 | 26/0737, 26/0795, 26/0631 |
   | länger als 1.500 Zeichen, wird gekappt (`_saeubern(max_len=1500)`) | 210 | – |

   Das Feld geht in Tragweite, Kartentext, Vorschlagsfragen und MCP ein.
2. **Änderungsanträge werden nicht als Anträge erkannt ✔.**
   - `vorlagen._ANTRAG_LABEL_RE = \b(antr[aä]g|anfrage)` verfehlt Komposita.
   - Alle 38 Anlagen an Vorlagen mit „Änderungsantrag“ im Label stehen auf
     `is_motion = 0`.
   - **Die vordere Wortgrenze einfach zu streichen ist falsch.** Das trifft 107
     weitere Labels, davon rund 40 Anträge Dritter:
     - 22 Zuschussanträge,
     - 3 Förderanträge,
     - 2 Genehmigungsanträge,
     - rund 12 zusammengeschriebene Labels wie „Anlage1antrag…“.

     Sie bekämen `is_motion = 1` und stünden in `store.anlagen_fuer` an erster
     Stelle.
   - Der Grünen-Antrag zu Ö 13.2 (315835) heißt „2026-10-31 Reduzierung Anzahl
     beratende Mitglieder“. Erst der Kopf des PDFs sagt „Änderungsantrag … TOP
     13.2“. **Den Typ eines Dokuments muss man aus Label UND Textkopf bestimmen.**
3. **Punkt-Anlagen haben fast nie Text ✔** (lokal 11 von 1.250). Auf Prod haben
   sie nur Text, wenn der MCP-Server ihn auf Zuruf geladen hat.
4. **Zwei Anlagen-Welten ✔.** `council_attachments` (an der Vorlage, mit
   `document_id`) steht neben `council_agenda_attachments` (am Punkt, **ohne**
   `document_id`, nur `url`).
   - Alle 1.250 Punkt-URLs tragen `getfile.php?id=…`.
   - 498 der 504 Punkt-Anlagen „Vorlage“ sind das Haupt-PDF der Vorlage.
   - 514 Punkt-Anlagen hängen auch an der Vorlage, 238 nur am Punkt.
5. **`council_agenda_attachments` wird bei jedem Abgleich gelöscht und neu
   geschrieben ✔** (`store_sitzungen.py:254–270`). Nur `raw_text` überlebt, je URL.
   Jede neue Spalte dort wäre am nächsten Morgen leer.
6. **`no_pdf` wird nie nachgeholt ✔, lässt sich aber schließen.** Die sechs
   Punkt-Anlagen „Vorlage“ ohne passende Vorlage sind genau die `no_pdf`-Fälle:
   26/0557, 26/0558, 26/0559, 26/0566 und 26/0792. Der Text liegt also am Punkt.
7. **Ausgetauschte Vorlagen werden nicht bemerkt ✔.**
   - `backfill_vorlagen.process_missing` überspringt eingelesene `kvonr`.
   - Der Anlagen-Rescan lässt bekannte `document_id`s nur als Link stehen
     (`skip_document_ids`).
8. **Anlagentexte kommen spät ✔.** Was kein Antrag ist, bekommt seinen Text nur
   sonntags (`weekly_enrich`, `backfill_anlagen_texte.py --limit 300`). Lokal
   stehen 1.175 Anlagen auf `listed` und 603 auf `empty`.
9. **Seiten.**
   - **Vorlagen ✔:** 5.239 von 5.253 tragen im Text den Druckkopf „Seite: n/m“.
     Bei 5.237 ist er vollständig und passt zu `n_pages`. „Ausdruck vom:“ tragen
     nur 4.991. Seitengenaue Belege für Vorlagen gehen also **ohne Download**.
   - **Anlagen ✔:** `anlagentext.pdf_seiten` liefert Seiten, gespeichert wird aber
     `"\n".join(…)`. Danach verschieben `entfernen` (`_TRENNSTRICH`, Platzhalter)
     und `strip` die Stellen.
   - Die [V]-Belege der Argumente zeigen auf die vo0050-Metaseite ✔.
10. **Fünf Modellaufrufe lesen dieselbe Vorlage getrennt:**
    - Tragweite: 900 Zeichen
    - Kartentext: 40.000 + 40.000 Zeichen
    - Argumente: 6.000 Zeichen
    - Vorschlagsfragen: 6.000 Zeichen
    - Orte: 4.500 Zeichen

    `cached_tokens` wird nirgends erfasst ✔.
11. **Textqualität ✔.** In 315835 stehen Telefonnummer und Fraktions-Mail in
    gesperrter Schrift („T e l e f o n 0 4 4 1 – 2 3 5 …“). `kontaktdaten.entfernen`
    übersieht das, und der MCP-Server gibt es so aus.
12. **Der Vektorindex nimmt nur einen Anfang ✔:** höchstens 4 Stücke je Vorlage
    und 8 je Anlage (`embeddings.MAX_CHUNKS`, `ANLAGE_MAX_CHUNKS`).
13. **Der KI-Stern ist da ✔** (`components/ki-stern.tsx`, #1877). Die UI-Schritte
    hängen von nichts mehr ab.

**Folgerung:** Vor jedem Modell steht eine deterministische Schicht aus Fixes,
Dokumentensatz, Seiten, Typen und Vor-Ernte. Sie kostet nichts, hilft sofort und
liefert dem Prüfer die Anker, gegen die er jedes Zitat hält.

---

## 2. Informationsfelder je Dokumentart

### 2.1 Leitfragen und Abschnitte

Die Abschnitte folgen der Reihenfolge, in der man vor der Sitzung fragt
(B = Bürgerin, R = Ratsmitglied). Die Extraktion leitet sich rückwärts daraus ab:
Gelesen wird, was eine dieser Fragen beantwortet.

| # | Leitfrage | wer | Abschnitt | heute |
|---|---|---|---|---|
| 1 | Worum geht es? | B R | **Leitsatz** (Kartentext wie heute) | 88 von 129 Punkten |
| 2 | Was genau soll beschlossen werden? | B R | **Was beschlossen werden soll** | nirgends |
| 3 | Was wollen die Änderungsanträge, von wem? | R B | **Was die Änderungsanträge wollen** | nur das Label |
| 4 | Was ändert sich gegenüber heute? | B | **Was sich ändert** (alt gegen neu) | nirgends |
| 5 | Was kostet es, wer zahlt, ab wann? | B R | **Was es kostet** | erst nach dem Protokoll |
| 6 | Wen betrifft es, wo? | B | **Wen und wo es betrifft** | nirgends |
| 7 | Warum? Was sagt die Verwaltung? | R | **Was die Verwaltung sagt** | Rohauszug nach dem Protokoll |
| 8 | Wie verbindlich, was danach, was offen? | R | **Was danach passiert** | nirgends |
| 9 | Wo steht das, wo prüfe ich nach? | R | **Gegenlese-Liste** und [n] an jeder Aussage | rohe Linkliste |

**Regeln für alle Abschnitte**

- Ein Abschnitt erscheint nur mit mindestens einer belegten Aussage.
- Obergrenzen:
  - „Was beschlossen werden soll“: höchstens 5 Punkte
  - „Was sich ändert“: höchstens 8 Zeilen, der Rest als „und N weitere“ mit Beleg
    auf die Synopse
  - „Was es kostet“: höchstens 4 Posten
  - „Was die Verwaltung sagt“: höchstens 3 Gründe
  - „Was danach passiert“: höchstens 4 Punkte
- Kurze, neutrale Sätze im Vorschlags-Modus („soll“, „schlägt vor“). Keine
  Wertung, kein vorweggenommenes Ergebnis, keine Selbstauskunft.
- Überschriften hängen von der Form ab (2.3) und kommen aus dem Backend. Bei
  einem B-Plan heißt „Was sich ändert“ zum Beispiel „Was gebaut werden darf“, bei
  einem Bericht „Was berichtet wird“.
- **Widersprüche:** Beide Werte stehen da, je mit Beleg. Die Vorlage geht der
  Anlage vor, die neuere Fassung der älteren. Das bestimmt nur die Reihenfolge,
  gelöscht wird nichts.

### 2.2 Kernfelder für jede Vorlage

Herkunft:

- **D** = ohne Modell (Struktur, Regex)
- **M** = Modell, Zitat vom Prüfer gehalten
- **D+M** = die Vor-Ernte liefert Kandidaten mit Seite, das Modell ordnet ein, und
  der Wert muss unter den Kandidaten stehen

| Feld | Inhalt | Herkunft |
|---|---|---|
| `form` | F1–F8 (2.3) | D |
| `proposal.official` | amtlicher Beschlussvorschlag in Ziffern | D (nach dem Fix) |
| `proposal.plain` | dasselbe in 1–3 einfachen Sätzen | M |
| `proposal.not_included` | was ausdrücklich **nicht** beschlossen wird | M |
| `costs` | Status und Posten `{amount_eur, recurrence: once/yearly/total/unknown, years, purpose, borne_by: city/third_party/grant/investor/unknown}`; Deckung `{amount_eur, source}` | D+M |
| `dates` | `{date, role: in_force/deadline/start/participation/next_deliberation/report_due/other}` | D+M |
| `affected`, `places` | Gruppen (**nie Privatpersonen**), Straßen, Flurstücke, Stadtteile | M, D+M |
| `figures` | Kennzahlen ohne Geld (Fläche, Wohnungen, Fallzahlen) | D+M |
| `administration` | Haltung (`recommends`, `neutral_report`, `no_alternative`, `mixed`, `none`) mit Satz; Alternativen; Bedingungen und Risiken | M |
| `trigger` | Anlass als Art (`law`, `council_mandate`, `motion`, `applicant`, `administration`, `court`) mit Satz | D+M |
| `legal_basis` | „§ 71 Abs. 7 NKomVG“ mit Rolle | D+M |
| `history` | Vorlagennummern im Text, Fassungen /1, /2 | D |
| `climate`, `office`, `other_impacts` | Abschnitte b), Amt, c) | D (c) ist neu) |
| `conflicts` | gleiche Größe, verschiedene Werte | D (Abgleich der Belege) |

**Feldstatus**, denn ein Feld ist nie einfach leer:

| Status | Bedeutung | Anzeige |
|---|---|---|
| `found` | belegte Aussagen | Aussagen mit [n] |
| `stated_none` | das Dokument sagt ausdrücklich „keine“ | „Laut Vorlage keine Kosten [1]“ |
| `absent` | alle Lesestoff-Dokumente ganz gelesen, nichts dazu | nur bei Kosten: „In den Unterlagen nicht beziffert“; sonst entfällt der Abschnitt |
| `unread` | ein Dokument, das die Angabe tragen könnte, ist Scan, zu lang oder fehlt | entfällt; das Dokument trägt in der Gegenlese-Liste „Scan ohne Textebene“ |
| `unsupported` | das Modell fand etwas, das sich nicht belegen ließ | gilt **nicht** als `absent`; wo die Vor-Ernte den Abschnitt kennt (Beschlussvorschlag, Kosten, Klima), steht dessen amtlicher Wortlaut mit Seite da, sonst entfällt der Abschnitt |

So behauptet die Seite nie eine Lücke, die nicht belegt ist. Und ein verworfener
Satz wird nie zu „steht nicht drin“.

### 2.3 Formen und Zusatzfelder

Die 14 Typen der Stichprobe (T1–T14) bilden acht **Formen**. Die Form wird ohne
Modell bestimmt, aus:

- Vorlagenart,
- Titelendung („– Beschluss“, „– Bericht“, „Satzungsbeschluss“, „Beschlussantrag
  mit Bericht“),
- Typen der Anlagen.

Das Modell bekommt nur das Schema seiner Form. Eine abweichende Einschätzung
meldet es in `form_suggestion`. Das wird protokolliert und ändert nichts. Fälle,
die keiner Form zugeordnet werden können, bekommen nur den Kern.

| Form | Typen | Zusatzfelder | Lesestoff |
|---|---|---|---|
| F1 Formalie | T1 Widmung, Benennung, Zuwendung; T12 Besetzung | Ort bzw. Gremium, Sitze, ab wann | Vorlage |
| F2 Sachentscheidung | T6 Bau/Investition; T14 Grundlagenbeschluss | Gesamt- und Folgekosten, Bürgschaften, Bedingungen, Zeitplan, `binding` (was verbindlich wird, was nicht) | Vorlage, Kernkapitel der Studie |
| F3 Regelwerk | T3 Satzung, Geschäftsordnung, Gebühren | `rule_changes[] {ref „§ 3 Abs. 2“, before, after}`, Altfassung beigefügt ja/nein, Inkrafttreten | Synopse, Änderungssatzung, Regelwerk mit §-Ankern |
| F4 Geld | T4 über- oder außerplanmäßig; T5 Jahresabschluss | Betrag, Ursache, Deckung je Quelle, Ermessen; Ergebnis (ordentlich/außerordentlich); Prüfvermerke B/WB | Vorlage, Schlussbericht RPA (nur Randcodes) |
| F5 Bauleitplanung | T2 | was gebaut werden darf (Nutzung, Höhe, Wohnungen, Fläche), wo, Verfahrensschritt, Beteiligung (Zahl der Stellungnahmen, Themen, Ergebnis) | Vorlage, Begründung Kap. 5/7/8, Abwägung (nur Zahl und Themen) |
| F6 Antrag | T7 Fraktionsantrag mit Stellungnahme; T9 Dringlichkeitsantrag | je Antragspunkt Forderung und Haltung der Verwaltung (`rejects`, `already_done`, `not_lawful`, `partly`, `agrees`, `no_view`); Dringlichkeitsgrund | Antrag, Stellungnahme („Zu Punkt n“-Paare aus der Vor-Ernte) |
| F7 Bericht/Anfrage | T10, T11 | Auftrag (Datum, Vorlage), Kernbefunde; Frage → Antwort mit Status (`answered`, `no_data`, `oral`, `unknown`); nächste Schritte | Vorlage |
| F8 Einzelfall | T13 Einsprüche, Widersprüche | je Fall Rüge und Bewertung, **ohne Namen** | Vorlage (die Einsprüche selbst sind Scans) |

Der Änderungsantrag (T8) ist keine Form, sondern eine eigene Dokumentart mit
eigenem Auszug (Abschnitt 5).

### 2.4 Unterlagen: Lesestoff oder Belegmaterial

Den Typ bestimmt `council/document_types.py::classify(label, head, n_pages, is_image)`
ohne Modell, aus Label **und** den ersten 1.500 Zeichen.

| Typ | Behandlung |
|---|---|
| `amendment`, `motion`, `urgent_motion`, `inquiry` | **Lesestoff** ganz; Änderungsanträge mit eigenem Aufruf |
| `statement` (Stellungnahme), `report` | Lesestoff |
| `synopsis`, `bylaw_text`, `rules_text` | Lesestoff, gezielt über §-Anker; `rule_changes` aus der flachen Synopse erst mit dem Spaltenleser (PR 17) |
| `land_use_reasoning` | Lesestoff, Kapitel 5, 7 und 8 |
| `objection_table`, `audit_report` | nur Zahlen, Themen, Randcodes |
| `expert_report`, `plan_drawing`, `visualisation`, `list`, `other` | **Belegmaterial**: ein Inhaltssatz aus Titelseite und Inhaltsverzeichnis |
| Scan ohne Text | OCR (`attachment_ocr`) nur für Lesestoff, auf Tims Ja |

Je Unterlage gibt es einen **Inhaltssatz** (`gist`). Er ist eine Aussage **mit
Beleg** auf Seite 1–2 und beschreibt das Dokument: „Schalltechnisches Gutachten
zum B-Plan 837, 48 Seiten“. Eine Wertung enthält er nicht.

---

## 3. Datenmodell und Belege

### 3.1 Tabellen (`council.sqlite`, Schema **und** Migration)

| Was | Wo | Inhalt |
|---|---|---|
| Kennung der Punkt-Anlage | Spalte `document_id` an `council_agenda_attachments` | `save_session` füllt sie beim Einfügen aus der URL. Die Migration füllt den Bestand per `substr`. Weil die Tabelle bei jedem Abgleich neu geschrieben wird, kommt die Kennung jedes Mal neu aus der URL. Das ist der einzige Wert, der dort richtig liegt. |
| Dokument-Steckbrief | **neue Tabelle `council_documents`** | `document_id` PK, `doc_type`, `applicants` (JSON), `n_pages`, `is_scan`, `page_offsets` (JSON), `text_hash`, `classified_at`. Gilt für Vorlagen-PDFs, Vorlagen-Anlagen und Punkt-Anlagen, denn alle drei hängen an `document_id`. Ein Dokument an zwei Punkten (315588 an DZT 1 und Ö 2) steht einmal da. |
| Dossier | **neue Tabelle `template_dossiers`** | PK (`subject_key`, `sources_hash`); `prompt_version`, `model`, `form`, `status` (`ok`/`running`/`failed`), `started_at`, `payload`, `dropped` (JSON, nur zur Messung), `cost_usd`, `created_at` |
| Antrags-Auszug | **neue Tabelle `motion_extracts`** | `document_id` PK, `base_subject_key`, `base_hash`, `text_hash`, `status`, `payload`, `prompt_version`, `model`, `cost_usd`, `created_at` |
| Kosten-Cache | Spalte `cached_tokens` an `llm_usage` (`ratslotse.sqlite`, Schema und Migration in `kern/`) | aus `usage.prompt_tokens_details.cached_tokens` |

- **Store-Mixin** `council/store_unterlagen.py` (`class UnterlagenMixin(StoreBasis)`),
  nicht `store.py` (`tests/test_store_groesse.py`). Es gibt keine Bindung an ein
  Konto, also keinen Eintrag in `COUNCIL_USER_OWNED_TABLES`.
- **Schlüssel wie bei den Argumenten:**
  - `tn:26/0796` je Vorlage, für alle Stationen gleich (spart den Faktor 1,39),
  - `doc:<document_id>` des Antrags bei Punkten ohne Vorlage. Das ist stabil
    gegen Umnummerierung, `top:4709|Ö 9` wäre es nicht.
- **`sources_hash`** wird gebildet über:
  - Text-Prüfsumme der Vorlage,
  - Prüfsummen der Lesestoff-Anlagen, **die keine Anträge sind**,
  - Form und `prompt_version`.

  **Nicht** darin stehen Änderungsanträge (eigener Auszug), Belegmaterial
  (Inhaltssatz im Sammelaufruf) und abgeleitete Texte (die Lehre aus
  `page_questions`). Ein Antrag am Sitzungstag schreibt also nicht das ganze
  Dossier neu, und was schon in einer Mail stand, bleibt im Wortlaut.
- **Geschichte statt Überschreiben:** Jede neue Quellenlage gibt eine neue Zeile.
  - Eine **vergangene** Station zeigt das jüngste `ok`-Dossier, das bis zum
    Sitzungstag entstand. Auf der Beschluss-Seite des Ausschusses steht also kein
    Text aus Dokumenten, die erst zum Rat kamen.
  - Kommende Stationen zeigen das jüngste.
  - Nach einem Wechsel der `prompt_version` bleibt die alte Zeile sichtbar, bis
    die geplante Tranche sie ersetzt. Es gibt keine aktive Fassung, die den Bestand
    unsichtbar macht.
- Die **Zuordnung Antrag ↔ Teilabstimmung** wird beim Lesen berechnet, nicht
  gespeichert. So veraltet sie nicht, wenn das Protokoll später kommt.

### 3.2 Payload

```
Aussage = { "text": str (≤ 220 Zeichen), "quote": str (wörtlich, 30–420),
            "source": "V1" | "A1" … , "page": int }
          # beim Speichern wird source zu {document_id, kind, label, list_no}
{ "form": "F3",
  "proposal":  {"status": …, "plain": [Aussage], "not_included": [Aussage]},
  "costs":     {"status": "found|stated_none|absent|unread|unsupported",
                "unquantified": bool,
                "items": [{"amount_eur": num|null, "recurrence": "...", "years": [int],
                           "borne_by": "...", **Aussage}],
                "coverage": [{"amount_eur": num|null, "source_name": str, **Aussage}]},
  "changes":   {"status": …, "items": [{"subject": str, "before": Aussage|null, "after": Aussage}],
                "more_n": int},
  "affected":  {...}, "places": {...}, "figures": {...},
  "administration": {"status": …, "stance": "...", "points": [Aussage],
                     "alternatives": Aussage|null, "conditions": [Aussage]},
  "next":      {"status": …, "dates": [{"date": "YYYY-MM-DD", "role": "...", **Aussage}],
                "binding": Aussage|null, "open": [Aussage]},
  "extra":     { formabhängig, 2.3 },
  "documents": [{"source": "A3", "gist": Aussage}],
  "conflicts": [{"field": str, "values": [Aussage, Aussage]}],
  "form_suggestion": "F2" | null }
```

Die Vorlage heißt `V1`, nicht `V`, sonst verwirft die übernommene Prüfung jede
Vorlage als „unbekannte Quelle“.

### 3.3 Seiten

- **Vorlagen:** Die Seiten werden aus dem Druckkopf **„Seite: n/m“** gerechnet,
  nicht aus „Ausdruck vom:“ (das fehlt in rund 250 Vorlagen). Ohne Download
  werden 5.237 von 5.253 Vorlagen abgedeckt. Die Offsets kommen nach
  `council_documents.page_offsets` (Schlüssel: `document_id` des Haupt-PDFs).
- **Anlagen:** Seiten-Anker statt Rechnen. Beim Laden wird je Seite aus
  `pdf_seiten` der Anfang (die ersten 60 verdichteten Zeichen) im **gespeicherten**
  Text gesucht, monoton von vorn. So bleiben die Offsets richtig, egal was
  `entfernen`, `_TRENNSTRICH` und `strip` verschoben haben. `text_hash` hält fest,
  zu welchem Text sie gehören; passt er nicht mehr, gelten die Offsets als
  ungültig.
- **Bestand:** Neu geladen wird nur, was gelesen wird: Lesestoff der letzten 12
  Monate und alles an kommenden Sitzungen. Das sind rund 400 Dokumente, bei 1 s
  Abstand unter 10 Minuten. Weicht beim Neuladen die Prüfsumme ab, wird der Text
  neu gelesen, statt nur Seiten anzuhängen.

### 3.4 Belegprüfung (`council/evidence.py`, ohne Modell)

Das Modul nimmt `tight`, `locate` und `check_statement` aus `plan_judge`.
`plan_judge` importiert sie danach von dort, es gibt also eine Regel statt zwei.
Eine Aussage bleibt nur, wenn alles gilt:

1. **Quelle bekannt** (`V1`, `A1…An`).
2. **Zitat wörtlich**, mindestens 30 Zeichen, verdichtet und ohne Druckkopf.
   Steht es auf einer anderen Seite als angegeben, wird die Seite berichtigt.
3. **Zahlen belegt.** Die Prüfung übernimmt **`kritiker._zahlen` und
   `_varianten`**, nicht `plan_judge.numbers`. Dessen `_NUMBER = \d+(?:[.,]\d+)*`
   prüft nur Ziffern.
   - Zahlwörter (zwei bis zwölf), „9,5 Mio.“ gegen „9.500.000“ und Tausenderpunkte
     sind damit abgedeckt.
   - Jahreszahlen, Paragrafen und Ordnungszahlen bleiben frei.
   - Genau das sind Tims Beispiele: Die Grünen schreiben „von fünf auf vier“,
     Volt „zwei Tage“ → „eine Woche“.
4. **Beträge und Daten** stehen zusätzlich unter den Kandidaten der Vor-Ernte
   (selbes Dokument).
5. **Eigener Wortwahl-Regelsatz statt `kritiker.pruefe`.** Dessen Listen sind für
   einen Kartensatz gebaut. Sie verwerfen „Risiken“, „dringend“ und „erheblich“
   (`_WERTUNG_RE`) sowie „beschlossen“ und „abgelehnt“ (`_ERGEBNIS_RE`). Gerade
   die Risiken, der Dringlichkeitsgrund und die Vorgeschichte („Der Rat hat am …
   beschlossen“) liefen sonst leer. Die Regel lautet deshalb:
   - Ein Wertungs- oder Ergebniswort ist erlaubt, **wenn es im Zitat steht**.
   - Sonst wird die Aussage verworfen.
   - Aktenzeichen in Klammern bleiben verboten.
   - Höchstens 220 Zeichen.
6. **Namen.** Ein erzeugter Satz nennt nur Ratsmitglieder, Verwaltungsspitze
   (`store_personen`) und Organisationen. In den Formen F5 (Abwägung) und F8 nennt
   er keine Person.
7. **Ausgabefilter.**
   - In erzeugten Sätzen: keine URL, kein `@`, keine Telefonnummer, auch nicht in
     gesperrter Schrift. Vorher werden Folgen aus Einzelzeichen mit Leerzeichen
     zusammengezogen.
   - Für Zitate gelten `kontaktdaten.maskieren` und dasselbe Zusammenziehen.
   - `vorschlagsfragen._VERDAECHTIG` läuft **nicht** über Zitate. Es verwirft
     eckige Klammern und „Anweisung“, die in Satzungen echt vorkommen.

Verworfene Aussagen landen mit Grund in `dropped` (für die Messung) und setzen das
Feld auf `unsupported`.

**Wächter `tests/test_dossier_belege.py`** (nach dem Muster von
`test_quellen_dokumente.py`): Kein Beleg verlässt die API ohne `document_id`, und
keiner zeigt auf die Ratsinfo-Startseite oder auf vo0050. Die Argumente stellen
ihre [V]-Belege danach auf PDF und Seite um.

---

## 4. Pipeline: Cron, Abruf und Bündelung

```
Stufe 0  ohne Modell, kostenlos
  Fixes → Dokumentensatz je Punkt (Vorlage + Vorlagen-Anlagen + Punkt-Anlagen ALLER
  Stationen, über document_id entdoppelt) → Typ und Form → Lesestoff nachladen (1/s)
  → Seiten → Vor-Ernte mit Seiten
Stufe 1  ein Aufruf je Vorlage                  → template_dossier → evidence → template_dossiers
Stufe 2  ein kleiner Aufruf je Antrag           → motion_extract   → evidence → motion_extracts
Stufe 3  nach dem Protokoll, ohne Modell        → Antrag ↔ Teilabstimmung; Vorschlag ↔ Beschluss (Diff)
         nur bei deviation slight/strong: ein Satz mit outcome_note (decision_deviation)
Stufe 4  abgeleitete Texte, nach A/B            → Kartentext, Vorschlagsfragen, Tragweite lesen das Dossier
```

### 4.1 Stufe 0: Vor-Ernte (`council/dossier_harvest.py`)

- **Abschnitte mit Seite:** Kopf, Beratungsfolge, Beschlussvorschlag in Ziffern,
  Anlass, Bericht oder Begründung, a) Finanzen, b) Klima, c) Weitere, Abwägung,
  Anlagenliste. Floskeln werden zu `stated_none`.
- **Kandidaten mit Kontext und Seite:** Beträge, Daten, §§, Vorlagennummern,
  Flurstücke, Flächen.
- **Paare:** „Zu Punkt n“ mit Antragspunkt n; nummerierte Fragen mit Antworten;
  Randcodes B/WB im Schlussbericht.
- **§-Anker-Index** für Regelwerke, damit Änderungsanträge ihren Altwortlaut
  finden.
- **Antragsteller** über `parties_in_text`. Das Modell darf sie bestätigen, aber
  keine neuen hinzufügen.

### 4.2 Stufe 1: der Dossier-Aufruf

**Eingabe:**

- **Vorspann:** Regeln und Schema der Form.
- **Vorgaben aus Stufe 0 als feste Fakten:** Form, Antragsteller, Amt,
  Beratungsfolge, amtlicher Beschlussvorschlag, Kandidaten.
- **Dokumentblock mit Seitenmarken** („— [V1] Seite 2 —“):
  - die Vorlage ganz,
  - die Lesestoff-Anlagen nach Typ (Stellungnahme, Synopse und Satzung,
    Begründung), höchstens 12.000 Zeichen je Anlage und rund 30.000 Token
    zusammen,
  - von Belegmaterial nur die Kopfzeile.
- **Reihenfolge für den Prompt-Cache:** Vorspann, dann der deterministisch
  sortierte Dokumentblock, die Aufgabe zuletzt.
- Die Dokumente sind als Fremdtext markiert (`kern/foreign_text.py`).

**Ausgabe:** JSON nach 3.2 über `response_format=json_object` mit eigener
Prüfung, wie überall im Repo. Ein strenges JSON-Schema wäre der erste Einsatz und
ist mit Flex und den Ersatzmodellen ungemessen.

**Leitplanken:**

- `llm.chat_complete(_feature="template_dossier", _tarif="flex", _geduld=True, _ersatz=…)`.
  Prompt `template_dossier_system` in `kern/prompts.py`. Feature in
  `OHNE_NUTZEREINGABE` und `FEATURE_LABELS`. Modell `COUNCIL_DOSSIER_MODEL`
  (Vorgabe GPT-6 Luna).
- **`max_tokens` bremst nicht.** Für Luna hebt `MODEL_PARAMS` jeden Wert auf
  16.000 an (`GPT56_MIN_MAX_TOKENS`) ✔. Die Bremse ist deshalb Geld:
  - `stopp.ausgeben(...)` je Aufruf,
  - `DOSSIER_MAX_USD` je Lauf (Vorgabe 0,50 $),
  - ein Tagesdeckel in Dollar beim Abruf.

  `finish_reason='length'` gilt als Fehler, nicht als halbes JSON. Liegt die
  geschätzte Ausgabe über 4.000 Token (Jahresabschluss, B-Plan), teilt sich der
  Aufruf in Kern und Form mit gleichem Präfix.
- **Ersatzkette ohne DeepSeek, als dokumentierte Ausnahme.** `kern/CLAUDE.md`
  verlangt `_ersatz=llm.ersatz_fuer(MODEL)`, und das endet bei DeepSeek ✔. Dessen
  Mindestbudget von 24.000 Token hat am 09.11. 0,78 $ ohne Ergebnis gekostet.
  - Neuer Parameter `llm.ersatz_fuer(MODEL, lange_ausgabe=True)`: Er lässt Modelle
    mit einem Token-Boden über 20.000 weg.
  - Dazu ein Satz in `kern/CLAUDE.md`. Sonst stellt ein späteres Review die
    Ausnahme zurück.
  - `gpt-5.6-luna` läuft einmal über das Gold-Set, damit ein Rückfall nicht
    ungeprüft schreibt.
- **Schichtung:** `council/template_dossier.py` und `council/motions.py`
  importieren nur aus `kern`.

### 4.3 Takt

| Weg | wann | was |
|---|---|---|
| **Dossier-Lauf** (neuer Job `vorlagen_dossiers`, `scripts/vorlagen_dossiers.py`, `run_guarded`, Takt in `kern/jobs.py`) | täglich **10:00** (nach `check_protocols` 9:00, das Vorlagentexte holt und Anlagen neu prüft) und **15:00** (nach `check_council` 14:00) | Sitzungen der nächsten 21 Tage: Lesestoff nachladen (höchstens 30 PDFs je Lauf, 1 s Abstand), Vorlagen-Austausch prüfen, fehlende oder veraltete Dossiers erzeugen, danach der Inhaltssatz für Belegmaterial im 8er-Stapel |
| **Änderungsanträge, ereignisgesteuert** | nach `save_session` in `check_committees` (7:00) und `check_council` (8:00, 14:00) | neue Punkt-Anlage vom Typ Antrag → Text laden (er überlebt in `council_agenda_attachments.raw_text`) → `motion_extract` |
| **Nachzügler-Lauf** (neuer Job, `scripts/antraege_nachzuegler.py`) | 11, 13, 16 und 18 Uhr, nur wenn heute oder morgen eine Sitzung ist, sonst Leerlauf | Tagesordnungsseite dieser Sitzungen neu lesen (1 Abruf je Sitzung und Lauf) plus neue PDFs. Volt kam am 01.11., die CDU am Sitzungstag 02.11. |
| **Rückfall auf Abruf** | Punkt- oder Beschluss-Seite geöffnet, angemeldet, kein Dossier vorhanden oder Vorlage ausgetauscht | `BackgroundTasks`. **Sperre in der Datenbank** (`status='running'`, `started_at`, 5 min gültig) statt `threading.Lock`, das nur in einem uvicorn-Worker gilt. Normaltarif **ohne** `_geduld` (Web-Pfad), eigenes Feature `template_dossier_abruf`, Tagesdeckel 0,20 $ aus `llm_usage`. Die Seite zeigt solange die Felder aus Stufe 0. Ein Wechsel der Prompt-Version löst **keinen** Abruf aus. |
| **Bestand** | `scripts/vorlagen_dossiers.py --schreiben --seit … --max-usd …` | 12 Monate nach dem Tor; älteres nur auf Abruf oder auf Tims Ja |

- **Ausgetauschte Vorlagen** fallen ohne zusätzlichen Abruf auf: Die Punkt-Anlage
  „Vorlage“ trägt die `document_id` des aktuellen PDFs, und `check_council`
  liest sie zweimal täglich. Weicht sie von `council_templates.document_id` ab,
  wird der Text neu geholt. Damit schließen sich auch die `no_pdf`-Fälle.
- **dev:** Dort laufen keine Crons. Der Abruf füllt die Seiten, sobald jemand sie
  öffnet. Für Vorführungen gibt es das Skript.

### 4.4 Tims Frage: mehrere KI-Ausgaben in einem Aufruf?

**Ja.** Ein Aufruf je Vorlage schreibt alle Abschnitte, die Formfelder und die
Inhaltssätze der gelesenen Unterlagen. Eingabe, Zeitpunkt und Lebensdauer sind
dieselben, und das Modell sieht beim Schreiben, was es schon belegt hat. Das
Schema hält die Felder trotzdem einzeln messbar.

| Variante (900 Aufrufe im Jahr, Flex) | Aufrufe je Vorlage | Token hinein / heraus | je Vorlage | Jahr |
|---|---:|---|---:|---:|
| getrennt: 7 Ausgaben, je ein Aufruf mit derselben Eingabe | 7 | 52.500 / 6.000 | 0,41 ct | **3,7 $** |
| **gebündelt: ein Dossier-Aufruf** | 1 | 7.500 / 3.200 | 0,12 ct | **1,1 $** |
| alles in einem, Anträge eingeschlossen (jeder Antrag schreibt das Dossier neu) | 1 + ⌀ 0,3 | wie oben | 0,16 ct | 1,4 $, und der Wortlaut flattert |

**Getrennt bleibt:**

| Ausgabe | Grund |
|---|---|
| Änderungsanträge | andere Lebensphase: Sie kommen Tage später, je Antrag ein Aufruf mit 0,05 ct statt eines neuen Dossiers mit 0,12 ct |
| „Wichtig“ | Rangfolge über viele Punkte (`impact.rate_agenda_batch`, 20 je Aufruf); je Vorlage ginge die Eichung verloren. Liest künftig Dossier-Zeilen statt 900 Zeichen Rohtext. |
| Kritiker | Der Prüfer darf nicht der Schreiber sein. Gleiches Präfix ergibt Cache-Treffer. |
| Texte nach dem Ergebnis | brauchen `outcome_note` (`council/CLAUDE.md`) |
| Lotti, Frag den Rat | Nutzereingabe, ZDR-Pflicht, kein Flex |
| Kartentext, Vorschlagsfragen | vorerst eigene Aufrufe (der Kartentext hat Gold-Set und Kritiker). In Stufe 4 lesen sie das Dossier (rund 1.500 Token) statt bis zu 80.000 Zeichen, nach A/B gegen den Prüfstand. |

**Kurz:** Bündeln spart gegenüber getrennten Aufrufen rund 70 %, in Geld rund
2,6 $ im Jahr. Der größere Gewinn ist eine gemeinsame, belegte Faktenbasis:
Kartentext, Vorschlagsfragen, Lotti und Frag den Rat können sich nicht mehr
widersprechen. Ob Prompt-Caching die getrennten Wege nennenswert verbilligt,
zeigt `cached_tokens` ab PR 9. Bis dahin ist es eine Annahme.

### 4.5 Tims Frage: on-demand beim Anklicken oder Cron?

**Cron für kommende Sitzungen, Abruf nur als Rückfall und für den alten Bestand.**

| Variante | Aufrufe im Jahr | Tarif | Jahr | Folge |
|---|---:|---|---:|---|
| **Cron, 21 Tage voraus** | ≈ 900 | Flex (0,12 ct) | 1,1 $ | auch Ungelesenes wird erzeugt |
| nur on-demand | ≈ 400 (Annahme: 45 % der Punkte werden angemeldet geöffnet) | normal (0,24 ct), denn ein Web-Pfad wartet nicht auf Flex | 1,0 $ | fehlt in Mails, Push, App, MCP, bei Lotti und für alle ohne Konto; der erste Besucher wartet 10–35 s |
| **Cron + Rückfall (Empfehlung)** | ≈ 900 + ≤ 300 | Flex + normal | 1,1 + ≤ 0,7 $ | – |
| Bestand seit 2018 per Lauf | 5.253 einmalig | Flex | 6,3 $ einmalig | nur auf Tims Ja |
| Bestand vor 12 Monaten nur auf Abruf | nach Besuch | normal | Cent-Beträge im Monat | erster Besucher wartet einmal |

On-demand spart für kommende Sitzungen kein Geld, weil es den Flex-Rabatt
verliert. Sinnvoll ist es für den **alten Bestand**, wo wenige Seiten Besuch
bekommen.

---

## 5. Änderungsanträge

**Erkennen (ohne Modell)**

1. **Label mit Präfixliste statt ohne Wortgrenze:**
   `\b(?:(?:ä|ae|a)nderungs|ergänzungs|zusatz|dringlichkeits|berichts|fraktions|beschluss|verweisungs|gegen)?antr[aä]g|\banfrage`.
   Gegenprobe im PR: kein Zuschuss-, Förder- oder Genehmigungsantrag und kein
   „Anlage1antrag…“ wird erfasst.
2. **Textkopf:** „Änderungsantrag“, „Ergänzungsantrag“, „Zusatzantrag“,
   „Dringlichkeitsantrag“ oder „beantragen … folgende Änderung“ in den ersten
   1.500 Zeichen. Erst damit fällt Ö 13.2 auf.
3. **Titel des Punkts:** `store_sitzungen._ist_aenderungsantrag` und
   `dringlichkeit.ist_dringlichkeitsantrag`.
4. **Bestand:** `scripts/antraege_nachziehen.py`, standardmäßig nur Bericht,
   schreibend mit `--schreiben`. Der Rescan stuft wegen `skip_document_ids` nichts
   neu ein.

**Basis auflösen**

| Muster | Beispiel | Basis | alt gegen neu |
|---|---|---|---|
| Streichung | CDU, Ö 9 (315836): die neue Regel in § 18 Abs. 4 „wird ersatzlos gestrichen“ | im Antrag zitiert, abgeglichen mit Regelwerk 315818 | alt = zitierter Satz, neu = gestrichen |
| Neufassung eines Absatzes | Volt, Ö 9 (315834): § 24 Abs. 2 GO | §-Anker in 315818 | **Wortdiff ohne Modell:** nur Satz 1 ändert sich, Ladungsfrist „zwei Tage“ → „eine Woche“ |
| Ersetzung des Beschlussvorschlags | Grüne, Ö 13.2 (315835): „von fünf auf vier reduziert“, fünfter Platz für das Jugendparlament | `proposed_decision` von 26/0796 (nach dem Fix) | alt und neu nebeneinander, je mit Beleg, dazu ein Bedeutungssatz; ein Wortdiff wäre hier sinnlos, weil die Formulierung neu ist |
| Gegenantrag | CDU zu 26/0631: Satzung außer Vollzug, Neufassung bis 31.12.2026 | keine Altfassung | nur „was der Antrag will“ |

- **Bezug auf eine andere Fassung:** Nennt der Antrag eine andere Nummer als die
  des Punkts, ist sie die Basis. Beispiel: FDP 313563 an 26/0714 bezieht sich auf
  26/0351/1. Steht der zitierte Basistext nicht im aktuellen Vorschlag, zeigt die
  Seite „bezieht sich auf die frühere Fassung 26/0351/1“ statt eines falschen
  Diffs.
- **Teils übernommen:** Ist ein Punkt schon im aktuellen Verwaltungsvorschlag
  enthalten, steht „teils übernommen“ mit beiden Belegen da.
- **Altfassung fehlt** (Dringlichkeitsantrag Hauptsatzung 315588): „Geltende
  Fassung nicht beigefügt“. Das ist eine Feststellung über die Unterlagen.

**Aufruf `motion_extract`**

- Flex mit Geduld, im Rückfall ohne.
- Eingabe: der Antrag ganz, der aufgelöste Ausschnitt der Basis und der
  Beschlussvorschlag, zusammen rund 4.000 Token.
- Ausgabe:
  - `target` („§ 24 Abs. 2 GO“, „Beschlussvorschlag Ziffer 2“),
  - `pattern` (streicht / ersetzt / ergänzt / fasst neu / Gegenantrag),
  - `before` und `after` als Aussagen mit Zitat (bei §-Ankern füllt der Code
    `before`),
  - `meaning`: ein neutraler Satz,
  - `reason`: die Begründung als Paraphrase, kursiv ohne Anführungszeichen
    (RG-09).
- Zahlwörter laufen durch die Prüfung aus 3.4: „vier“ muss im Zitat stehen.
- „eine Woche“ bleibt ungeprüft, weil „eine“ meist Artikel ist. Der Wortdiff
  zeigt die Wörter aber wörtlich.

**Nach dem Protokoll (ohne Modell)**

- Die Zuordnung zur Teilabstimmung läuft über `parent_item`, die antragstellende
  Fraktion in Titel bzw. `factions`, die Nähe des Titels zu `target`/`meaning` und
  das Datum.
- Zugeordnet wird nur, wenn es eindeutig ist. Lieber keine Zuordnung als eine
  falsche.
- Das Ergebnis-Badge kommt aus dem Protokoll, der Inhalt aus dem Antrag. Der
  Kommentar „kein erfundener alt/neu-Diff“ in der `SubvoteTimeline` bleibt
  richtig, denn alt und neu sind belegte Zitate.

---

## 6. Oberfläche je Seite

Alles erscheint hinter zwei Schaltern in `kern/features.py`, je mit `fertig_wenn`:

- `aenderungsantraege` (kommt früher),
- `aus-den-unterlagen`.

Die neuen Felder sind `NotRequired` in `antworten.py`, danach wird der Vertrag
neu geschnitten. Jeder UI-PR braucht vor dem Merge ein Bild und Tims OK.

**KI-Stern:**

- Er sitzt **einmal an der Überschrift** des Blocks und des Antrags-Abschnitts,
  nicht an jeder Zeile, sonst entstünde bei 15 Aussagen eine Funken-Wüste.
- Die Hover-Karte liefert das Backend: „Automatisch aus der Vorlage und 2 Anlagen
  erstellt. Verbindlich sind die Unterlagen im Ratsinfo.“ Kein KI-Vokabular, keine
  Selbstauskunft.
- **Amtlicher Wortlaut trägt keinen Stern.** Der aufklappbare Beschlussvorschlag
  und der Wortlaut „a) Finanzen“ stehen mit Anführungszeichen und Zitatkante da,
  sichtbar abgesetzt vom erzeugten Text.

**Beispiel** (Rat 02.11.2026, Ö 13.2, Vorlage 26/0796 mit dem Grünen-Antrag
315835; beide am 12.11. gelesen):

```
AUS DEN UNTERLAGEN ✱                         Stand 22.10. · Vorlage + 1 Antrag
WAS BESCHLOSSEN WERDEN SOLL
  Sieben Fachausschüsse bekommen je fünf beratende Mitglieder. [1]
  › Amtlicher Wortlaut
WAS DER ÄNDERUNGSANTRAG WILL ✱
  ● Grüne · ersetzt den Beschlussvorschlag
    vorher  „… Ausschuss für Gesundheit und Soziales 5 …“ [1]
    nachher „… wird von fünf auf vier reduziert. Der fünfte Platz wird für …
             des Jugendparlaments vorgesehen.“ [2]
    Vier statt fünf beratende Mitglieder; der fünfte Platz geht an das
    Jugendparlament. [2]
WAS ES KOSTET
  je Mitglied und Sitzung 35 € Sitzungsgeld, 6 € elektronische Ratsarbeit,
  5 € Fahrtkosten [1] · einen Gesamtbetrag nennt die Vorlage nicht
WAS DIE VERWALTUNG SAGT
  Zulässig sind höchstens sechs, weil mindestens zwei Drittel der Mitglieder
  Abgeordnete sein sollen (§ 71 Abs. 7 NKomVG). [1]
WAS DANACH PASSIERT
  Nach der Konstituierung des Jugendparlaments soll der Rat über ein
  sechstes Mitglied entscheiden. [1]
```

[1] zeigt im Popover das Zitat und „Vorlage 26/0796 · S. 2“. In der
Gegenlese-Liste ist es Unterlage 1, [2] ist der Antrag mit 2 Seiten.

### 6.1 Web: Punkt-Seite (`punkt/view.tsx`, `components/session/item-sections.tsx`)

1. **„Das Wichtigste in Kürze“ bleibt** als Leitsatz mit „Warum wichtig“.
2. **Neue Karte „Aus den Unterlagen“** direkt darunter. Der Name ist nötig, weil
   „Auf einen Blick“ rechts schon vergeben ist (`AufEinenBlick`).
   - **Kicker rechts:** Stand der Unterlagen („Stand 22.10. · Vorlage + 2
     Anlagen“). Ist seit dem Dossier ein Dokument dazugekommen: „1 Unterlage kam
     danach dazu“ mit Sprung in die Liste.
   - **Abschnitte** aus 2.1 mit Mono-Kicker, je Aussage eine Fußnote [n]
     (16×16).
   - **Was es kostet:** Geld-Baustein RG-04, € hinter jedem Betrag, Status nach
     2.2.
   - **Was sich ändert:** alt gegen neu, alt in `meta` durchgestrichen, Delta in
     Signal-Orange.
   - **Formabschnitte:** „Antragspunkte und Haltung der Verwaltung“, „Fragen und
     Antworten“ mit Status, „Was verbindlich wird“, „Beanstandungen der Prüfer“.
3. **„Was die Änderungsanträge wollen“** (`id="antraege"`) steht **im Block direkt
   unter „Was beschlossen werden soll“**, nicht hinter einem Reiter. Je Antrag:
   - Fraktions-Dot und Label (RG-09),
   - Art-Chip,
   - Ziel als Kicker („ÄNDERT § 24 ABS. 2 GO“),
   - alt gegen neu,
   - Bedeutung,
   - Begründung kursiv,
   - [n] aufs Antrags-PDF,
   - nach dem Protokoll das Ergebnis-Badge.
4. **Reiter „Unterlagen“ wird zur Gegenlese-Liste.** Je Eintrag:
   - die Nummer [n] (dieselbe wie in den Fußnoten),
   - Typ-Chip und Antragsteller-Dot,
   - bereinigtes Label ohne Datumspräfix,
   - Seitenzahl,
   - der Inhaltssatz mit eigenem Beleg,
   - „Fundstelle für 4 Angaben“,
   - Merkmale: „Scan ohne Textebene“, „kam nach der Zusammenfassung dazu“, „kam
     nach dieser Sitzung dazu“,
   - gestrichelter Link mit Extern-Icon.

   Reihenfolge: Vorlage, Anträge, Synopse und Satzung, Rest. Belegmaterial steht
   eingeklappt als Gruppe. Die doppelte Vorlage entfällt.
5. **Rechte Spalte:**
   - `AufEinenBlick` bekommt Federführung, Klima-Check und Vorlagenart dazu.
   - „Frag den Rat“ bekommt das Dossier als festen Kontext. Erst damit stimmt die
     Zeile „An Bord · N Unterlagen“.
6. **Ohne Dossier** (alt, läuft gerade, Tor noch nicht erreicht) zeigt die Karte
   die Felder aus Stufe 0: amtlichen Beschlussvorschlag, Kosten im Wortlaut mit
   Status, Amt, Klima und die Anträge mit Antragsteller. Einen Platzhaltertext
   gibt es nicht.

### 6.2 Web: Sitzungsseite und Mitlesen (`session-page.tsx`)

- **`ItemCard`:**
  - „Unterlagen N“ zählt ohne die doppelte Vorlage.
  - Gibt es Anträge, steht dort der Chip „**2 Änderungsanträge · CDU, Volt**“
    mit Sprung zu `#antraege`.
  - Nur wenn ein Betrag beziffert und belegt ist, steht dort „89.000 € jährlich“.
  - Die Beschriftungen setzt das Backend (`CourseItem.amendments_label`,
    `cost_label`).
- **Mitlesen:** Beim laufenden Punkt stehen die Änderungsanträge aufgeklappt
  zuoberst, denn über sie wird gerade abgestimmt. Darunter steht „Was beschlossen
  werden soll“. Das kommt über dieselben Bausteine aus `item-sections.tsx`.

### 6.3 Web: Beschluss-Seite (`decision/view.tsx`)

- **„Aus der Vorlage“:** das auf den Sitzungstag eingefrorene Dossier (3.1) unter
  dem amtlichen Beschlusstext, ausdrücklich im Vorschlags-Modus. Das Ergebnis
  zeigt die Seite selbst. Die Textart kommt in
  `tests/test_texte_kennen_ergebnis.py`.
- **„Vorgeschlagen ↔ beschlossen“:** Nur bei `deviation` slight oder strong.
  Beschlussvorschlag und `official_text` stehen nebeneinander, Wortdiff ohne
  Modell, darüber ein Satz aus `decision_deviation` mit `outcome_note`. Beispiel
  26/0396 (CDU-Antrag angenommen). Nach dem Fix aus PR 1 wird `refresh_abweichung`
  neu gerechnet.
- **`SubvoteTimeline` „Was beantragt wurde“:** Inhalt aus `motion_extracts` mit
  PDF-Link.
- **„Warum es dazu kam“:** gegliedert mit [n], der Rohauszug aufklappbar.
- **„Was kostet das?“:** Posten mit Belegen, der amtliche Wortlaut bleibt Zitat.
- **„Dokumente & Anlagen“:** Zuerst wird die tote Liste repariert (PR 3). Danach
  zeigt sie dieselbe Gegenlese-Liste.

### 6.4 iOS (`AgendaItemDetailView.swift`, `CouncilViews.swift`)

- **Zuerst ohne neuen Server-Code (PR 5):** `social_text` und `important_reason`
  ins Modell. Die Punkt-Ansicht zeigt den Kartentext statt der Titel-Kurzfassung,
  dazu Beschlussvorschlag, Kosten, Klima und Amt.
- **Danach (PR 15):**
  - Karten wie im Web, Anträge direkt unter dem Beschlussvorschlag.
  - Unterlagen mit Nummer, Typ und Inhaltssatz.
  - [n] öffnet ein Sheet mit dem Zitat. „Im Dokument“ öffnet **PDFKit** auf der
    Seite (`PDFView.go(to:)`), denn QuickLook (heute in `CouncilViews.swift`)
    springt nicht auf eine Seite.
- **Gegenstücke auf dem Beschluss:** `DecisionTemplateStory` und
  `DecisionSubvotesCard`.
- **Modelle:** alles mit `decodeIfPresent`, Enums mit Rückfall `unknown`. Vor dem
  Release läuft `python3 scripts/ios_vertrag.py --ausgeliefert`.

### 6.5 Lotti, Frag den Rat, MCP, Mails

- **Lotti:** neues `page_context.punkt_lines`, nur mit den angezeigten Feldern
  („nur, was die Seite zeigt“).
- **Frag den Rat:** Für den Gegenstand „Punkt“ und „Beschluss“ geht das Dossier
  als fester Kontext mit. Die Vorschlagsfragen schöpfen in Stufe 4 aus dem
  Dossier.
- **MCP:** `get_template` und `get_agenda` liefern Dossier und Antrags-Auszüge
  samt Belegen.
- **Mails, Heute-Woche, Kalender:** höchstens „2 Änderungsanträge“ und der
  Kostenwert. Der Text bleibt der Kartentext.

### 6.6 Vertrag

| Antwortform | neu |
|---|---|
| `SessionItemDetail` | `dossier`, `amendments`, `template_fields` (Stufe 0) |
| `SessionItemDocument` | `document_id`, `list_no`, `doc_type`, `applicants`, `pages`, `gist`, `cited_n`, `is_scan`, `after_summary` |
| `DecisionTemplate` | `proposed_decision`, `dossier` |
| `DecisionDetail.sub_votes[]` | `amendment` |
| `CourseItem` | `amendments_label`, `amendment_parties`, `cost_label` |

---

## 7. Messung

**Grundsatz:** Kein Modell richtet im Betrieb. Ein Opus-Lauf kostet rund 1,1 $,
mehr als ein Produktionsjahr. Was sich buchstäblich prüfen lässt, prüft ein
Programm. Ob eine Aussage gestützt und treu ist, wird gelesen.

**Wer liest:** wie bei den Punkt-Argumenten (190 Aussagen) der Coding-Agent in
der Sitzung, und Tim prüft 5 Fälle stichprobenartig gegen. Ein Agent als Leser
ist faktisch ein Richter-Modell. Er läuft aber nur je Torlauf, nicht über
OpenRouter und nicht im Betrieb, und Tims Stichprobe eicht ihn.

**Aufwand:** Der erste Torlauf braucht rund 580 Urteile:

- 20 Dossiers × ~18 Aussagen,
- 120 Leitfragen,
- 72 Antrags-Urteile,
- 30 Zuordnungen.

Urteile werden nach Prüfsumme aus Satz und Zitat gespeichert. Folgeläufe
beurteilen nur geänderte Aussagen.

**Testdaten:**

- Der Abzug hat keine Anlagentexte, und `hol --von prod` entfernt sie auch ✔.
- Der MCP-Server liefert maskierten, verdichteten Text ohne Seitengrenzen ✔.
- Deshalb lädt `eval/run_dossier.py --hol` die rund 100 PDFs der Gold-Fälle
  einmal direkt aus dem Ratsinfo: 1 s Abstand, über `anlagentext.pdf_seiten`, mit
  Seiten, nach `~/.cache/ratslotse/dossier/`.
- **Nichts davon kommt ins öffentliche Repo**, denn gesperrte Kontaktdaten wie in
  315835 übersieht auch `lint_adressen`. Die Gold-Datei enthält nur Pflichtfakten
  (Zahl, Begriff, Dokument, Seite).

### 7.1 Ernte (PR 1 und 2, ohne Modell)

| Prüfung | Tor |
|---|---|
| Vorschläge mit „Anlass:“ | 781 → unter 10 |
| Vorschlag endet vor eigener Aufzählung | 26/0674 mit allen Ziffern; Liste der 122 Fälle durchgesehen |
| Vorschlag endet am Seitenkopf | 26/0737, 26/0795, 26/0631 vollständig; die ≈ 76 Fälle auf null |
| 20 Vorschläge von Hand | Ende richtig, nichts abgeschnitten |
| Antragserkennung | alle 38 Änderungsanträge an Vorlagen und die Punkt-Labels erkannt, Ö 13.2 über den Kopf; **0** Zuschuss-, Förder- und Genehmigungsanträge |
| `no_pdf` | 26/0557–0566 und 26/0792 mit Text |

### 7.2 Dossier (`eval/dossier_gold.json`, festgelegt **vor** dem ersten Prompt)

**20 Fälle.**

- **16 aus der Typologie:**
  - 26/0654 Widmung
  - 26/0806 Besetzung
  - 26/0820 Einsprüche, Scans
  - 26/0592 B-Plan, Widerspruch 8,6/8,5 ha
  - 26/0674 Jahresabschluss
  - 26/0656 überplanmäßig 9,5 Mio. €
  - 25/0667 Haushalt
  - 26/0666 Grundsteuer C
  - 26/0613 + 26/0631 Baumschutz, „Zu Punkt n“
  - 26/0743 Entschädigungssatzung, Synopse
  - 26/0792 GO, `no_pdf`
  - 26/0714 Studie mit 2 Anträgen
  - 26/0396 Stadion
  - 26/0699 Bericht
  - 26/0780 Anfrage
  - DZT 1 in 4708 Dringlichkeitsantrag
- **dazu:** 26/0796 und 26/0795, zwei zufällige Ausschuss-Punkte.

Je Fall stehen dort 3–6 Pflichtfakten mit Abschnitt, Dokument und Seite, der
richtige Status leerer Felder und die Leitfragen. Beispiele:

- 26/0796: fünf Mitglieder in sieben Ausschüssen; 35 €, 6 € und 5 € je Sitzung;
  höchstens sechs nach § 71 Abs. 7; sechster Platz Jugendparlament (S. 3).
- 26/0654: § 6 NStrG, ab 01.10.2026, 94 m.
- 26/0674: Jahresfehlbetrag −24.822.337,17 €.
- 26/0743: 89.000 €/Jahr, ab 01.11.2026, 335 → 400 €. Der letzte Wert braucht
  den Spaltenleser und wird bis dahin getrennt als erwarteter Fehlschlag gezählt.

| Kennzahl | Art | Tor |
|---|---|---|
| belegt (Zitat wörtlich, Seite berichtigt) | automatisch, dazu 50 Zitate von Hand auf Fehlzuordnung | 100 % |
| gestützt (das Zitat trägt den Satz) | Hand | ≥ 97 % |
| treu (keine Verzerrung, kein hinzugefügtes Motiv) | Hand | ≥ 95 % |
| Beträge und Daten: Wert / Rolle (jährlich oder einmalig, Inkrafttreten oder Frist) | automatisch / Hand | 100 % / ≥ 95 % |
| Pflichtfakten im richtigen Abschnitt | automatisch | ≥ 85 % |
| Status richtig (`stated_none`, `absent`, `unread`, `unsupported`) | gegen Gold | ≥ 95 % |
| **Leitfragen ohne PDF beantwortbar** (je Fall sechs: Was soll beschlossen werden? Was kostet es? Wen betrifft es? Ab wann? Was sagt die Verwaltung? Was wollen die Anträge?) | Hand: ja / teils / nein / **falsch**; eine falsch behauptete Lücke zählt als **falsch** | ≥ 80 % ja, **0 falsch** |
| Widerspruch zum Kartentext | Hand | 0 |
| verbotene Inhalte (Ergebnis vorweg, Privatnamen, Kontaktdaten, Wertung ohne Zitat) | automatisch | 0 |
| Wegfallquote je Form | automatisch | < 20 %; über 25 % fällt die Form auf den Kern zurück, bis Prompt oder Vor-Ernte nachgebessert sind |
| Widerspruch 26/0592 | Hand | beide Werte gezeigt |
| Ersatzmodell `gpt-5.6-luna` | ein voller Lauf | dieselben Tore |

### 7.3 Änderungsanträge und Zuordnung

**12 Anträge:**

- Volt 315834
- CDU 315836
- Grüne 315835
- CDU 315795
- Grüne 313562
- FDP 313563
- CDU 313627
- Dringlichkeitsantrag 315588
- vier weitere, zufällig aus 2025/26: mindestens einer in der Schreibung
  „Aenderungsantrag“, einer an der Vorlage statt am Punkt, ein angenommener und
  ein abgelehnter

**Tore:**

- Antragsteller und Ziel: 12/12
- Muster: ≥ 11/12
- alt gegen neu: ≥ 11/12, und **0** falsche alt/neu-Paare. „Altfassung nicht
  beigefügt“ zählt als richtig, wenn sie wirklich fehlt.
- Bedeutungssatz treu: ≥ 11/12
- Der Fassungsbezug der FDP (26/0351/1) wird erkannt.

**Zuordnung zur Teilabstimmung:** 30 Fälle, Präzision 100 %, Trefferquote ≥ 80 %.

### 7.4 Stufe 4 (A/B)

- **Kartentext aus dem Dossier gegen heute:** auf dem Prüfstand `social-text`
  nicht schlechter als 92,5 % ± 5.
- **Tragweite aus Dossier-Zeilen:** ρ am Tragweite-Gold darf nicht fallen.
- **Vorschlagsfragen:** 13 vorhandene Fälle, von Hand: Ist die Frage aus dem
  Dossier beantwortbar?
- **Frag den Rat:** 5 Fragen mit Bezug auf einen Punkt kommen ins KI-Frage-Gold.

Jeder Lauf protokolliert seine Kosten. Die Urteile stehen in der Gold-Datei, das
Ergebnis im PR.

---

## 8. Kosten je Jahr

GPT-6 Luna: 0,10 / 0,50 $ je Million Token, im Flex-Tarif die Hälfte. Rund 3,6
Zeichen je Token. Die Ausgabe enthält das Denken.

| Posten | Menge/Jahr | Token hinein / heraus | je Aufruf | Jahr |
|---|---:|---|---:|---:|
| Dossier (Cron, Flex): 600 Gegenstände × 1,5 Neuerzeugungen (neue Lesestoff-Anlage, ausgetauschte Vorlage) | 900 | 7.500 / 3.200 | 0,12 ct | 1,06 $ |
| Aufteilung Kern/Form bei langen Ausgaben (≈ 10 %) | 90 | Präfix aus dem Cache | – | 0,10 $ |
| Antrags-Auszug (Flex): ~150 Anträge × 1,3 | 195 | 4.000 / 1.200 | 0,05 ct | 0,10 $ |
| Inhaltssatz für Belegmaterial (8er-Stapel, Flex) | ~500 Dokumente | 1.000 / 120 je Dokument | 0,008 ct | 0,04 $ |
| Abweichungssatz nach dem Protokoll (Flex) | ~60 | 2.000 / 600 | 0,025 ct | 0,02 $ |
| Rückfall auf Abruf (normal, gedeckelt) | ≤ 300 | 7.500 / 3.200 | 0,24 ct | ≤ 0,72 $ |
| Puffer: Ersatzkette, abgewiesener Flex, Denk-Ausreißer (+40 % auf die Cron-Posten) | | | | 0,53 $ |
| **Laufend** | | | | **≈ 2,6 $** |
| optional: OCR für Lesestoff-Scans (Satzungstext von Veränderungssperren, Einsprüche) | ~200 Seiten | | 0,24 ct/Seite | 0,48 $ |
| optional: Bildleser für Tabellenseiten, wo `find_tables` scheitert | ~130 Seiten | | 0,24 ct/Seite | 0,31 $ |
| **mit Optionen** | | | | **≈ 3,4 $** |
| nicht eingerechnet: Kartentext, Fragen und Tragweite lesen das Dossier statt Rohtext | | | | −0,2 bis −0,5 $ |

**Einmalig:**

- Bestand 12 Monate: rund 600 × 0,12 ct ≈ 0,72 $, dazu Anträge 2025/26 ≈ 0,03 $.
- Gold-Läufe: ≈ 0,06 $ je Lauf (32 Fälle), rund 10 Läufe, also 0,60 $.
- Seiten-Nachlauf: 0 $ Modell, unter 10 min Ratsinfo-Zeit.
- **Bestand seit 2018** (5.253 Vorlagen): ≈ 6,3 $ Flex, **nur auf Tims Ja**.
  Sonst auf Abruf.

**Einordnung:** Das Monatsbudget liegt bei 40 $, Prod ohne Städtevergleich kostet
rund 3,5 $ im Monat. Der Plan erhöht das um rund 0,2 $ im Monat. Teuer würden nur
GPT-6 Sol statt Luna (≈ 17 $ im Jahr, ohne Flex) oder ein Richter-Modell im
Betrieb. Beides ist nicht vorgesehen.

---

## 9. Schritte als PRs

UI-PRs gehen erst nach Bild und OK von Tim durch. Alle anderen werden nach grüner
CI selbst gemergt (`scripts/merge_wenn_gruen.py --pr N`). Jeder nutzerrelevante
PR legt ein Changelog-Fragment an, Funktionen hinter Schaltern mit `schalter:`.
Dieser Plan kommt vorab als eigener PR nach `dev`.

| # | PR | Basis | Inhalt | Ergebnis / Abnahme |
|---|---|---|---|---|
| 1 | **Beschlussvorschlag richtig ernten** | main | `_ENDE` um Anlass, Bericht, Einordnung, Ausgangslage, Abwägung; Druckkopf vor der Ernte entfernen; a)/b)/c) nur als Finanzen/Klima/Weitere; Länge für den Vorschlag auf 8.000; Nachlauf `ernte_backfill` und `refresh_abweichung` mit Bericht | Tore 7.1; Tragweite, Kartentext und Vorschlagsfragen bekommen sofort die richtige Eingabe (neue Fragen-Hashes, Cent-Beträge) |
| 2 | **Anträge erkennen, `no_pdf` schließen** | main | Präfixliste und Kopfprüfung; `scripts/antraege_nachziehen.py`; `no_pdf` aus der Punkt-Anlage „Vorlage“; Austausch-Erkennung über `document_id` | Tore 7.1; Liste der Falsch-Positiven im PR |
| 3 | **UI-Fixes** | main | Beschluss-Seite `attachments` statt `anlagen`; doppelte Vorlage und Zähler | Bild + OK; behoben seit 02.09. |
| 4 | **Punkt-Seite zeigt die Vorlage** | dev | amtlicher Beschlussvorschlag, Kosten mit Status, Klima, Amt, Anträge mit Antragsteller; `SessionItemDetail.template_fields`, `DecisionTemplate.proposed_decision`; Vertrag | Bild + OK |
| 5 | **iOS: Kartentext und Vorlage am Punkt** | dev | `social_text`, `important_reason`, Felder aus 4 | Bild + OK, `ios_vertrag` |
| 6 | **Dokumente und Seiten** | dev | `document_id` an Punkt-Anlagen; `council_documents`; `document_types.classify`; Vorlagen-Seiten aus „Seite: n/m“; Anlagen-Offsets per Anker; `item_documents` über alle Stationen; Text der Antrags-Anlagen am Punkt beim Einlesen; Test „Sitzung zweimal einlesen“ | Seitenabdeckung Vorlagen ≥ 99 %; Typ-Abweichungen gegen alle 7.856 Labels als Liste; Ö 13.2 = Änderungsantrag |
| 7 | **Gegenlese-Liste ohne Modell** | dev | Reiter „Unterlagen“: Nummer, Typ, Antragsteller, Seiten, Merkmale, Belegmaterial eingeklappt | Bild + OK |
| 8 | **Belegprüfung** | dev | `council/evidence.py` (3.4), Ausgabefilter mit gesperrter Schrift, `cached_tokens`, `ersatz_fuer(lange_ausgabe=True)` samt Zeile in `kern/CLAUDE.md`, `tests/test_dossier_belege.py` | Tests; `plan_judge` unverändert grün |
| 9 | **Änderungsanträge lesen** | dev | `council/motions.py`, §-Anker, Wortdiff, `motion_extracts`, Auslöser in `check_committees`/`check_council`, Nachzügler-Job, Rückfall; Gold 12 + Zuordnung 30 | Tore 7.3; Nachlauf 2025/26 ≈ 0,03 $ |
| 10 | **Änderungsanträge zeigen** | dev | Abschnitt auf der Punkt-Seite, Mitlesen, Chip auf der Sitzungsseite, `SubvoteTimeline`; Schalter `aenderungsantraege` | Bild + OK |
| 11 | **Gold-Set Dossier** | dev | `eval/dossier_gold.json`, Fixture-Lader, `eval/run_dossier.py`, **vor** dem Prompt | Tim prüft 5 Fälle |
| 12 | **Dossier erzeugen** | dev | Vor-Ernte, Prompt, `template_dossiers`, Job `vorlagen_dossiers` (10 und 15 Uhr), Rückfall mit Sperre in der Datenbank, Stapel für Belegmaterial, `scripts/vorlagen_dossiers.py` | Tore 7.2; Ersatzmodell-Lauf; Bestand 12 Monate ≈ 0,7 $ |
| 13 | **„Aus den Unterlagen“** | dev | Karte, Beleg-Popover, Inhaltssätze und Stand in der Liste, Kostenchip, Mitlesen, Lotti `punkt_lines`, Kontext für Frag den Rat; Schalter `aus-den-unterlagen` | Bild + OK |
| 14 | **Beschluss-Seite** | dev | „Aus der Vorlage“ (eingefroren), Vorgeschlagen ↔ beschlossen mit `decision_deviation`, gegliedertes „Warum“, Kosten mit Belegen | Bild + OK |
| 15 | **iOS: Dossier und Anträge** | dev | Karten, Belege-Sheet, PDFKit mit Seitensprung, Beschluss-Gegenstücke | Bild + OK, `ios_vertrag`, neuer Build |
| 16 | **Folgeverbraucher** | dev | MCP; A/B: Kartentext, Vorschlagsfragen und Tragweite aus dem Dossier | Tore 7.4 |
| 17 | **Spezialleser nach Bedarf** | dev | Synopse spaltengenau (PyMuPDF-Wörter mit x-Koordinate bzw. `find_tables`), Abwägungstabelle, RPA-Randcodes, OCR für Lesestoff | je eigenes Gold, zum Beispiel 26/0743: 335 → 400 € |

**Abhängigkeiten:**

- 1 und 2 vor allem anderen,
- 6 vor 7, 9 und 12,
- 8 vor 9 und 12,
- 9 vor 10,
- 11 vor 12,
- 12 vor 13 bis 16.

**Prod:**

- 1 bis 3 sofort.
- Der Rest mit dem nächsten Release. Die Schalter gehen dort erst an, wenn die
  Tore stehen.

---

## 10. Weitere KI-Ideen für die Sitzungsvorbereitung

Fast alle sind Abfragen über die gespeicherten, belegten Felder, keine neuen
Lesedurchgänge. Geordnet nach Nutzen je Aufwand:

| Prio | Idee | Nutzen | Kosten/Jahr | braucht |
|---|---|---|---:|---|
| 1 | **Meldung bei neuem Änderungsantrag** zu einer gefolgten Vorlage (`vorlage_follows`) oder einem abonnierten Ausschuss, mit Ziel und Bedeutung; neuer Anlass über `notify.einreihen` (Aus-Schalter, Nachtruhe, Tagesgrenze) | Anträge kommen am Vortag oder Sitzungstag. Heute erfährt man erst in der Sitzung davon. | 0 $ | PR 9 |
| 2 | **Prüfhinweise** als Feststellung über die Unterlagen, je mit Beleg: verschiedene Zahlen in Vorlage und Anlage, Altfassung nicht beigefügt, Antrag auf eine frühere Fassung, „gedeckt“ ohne Betrag, gesetzte Frist verfehlt | Zeigt genau die Stellen, an denen man wirklich gegenlesen sollte | 0 $ | PR 12 |
| 3 | **Was ist neu seit der letzten Beratung:** Fassungen (/1 → /2) und Stationen (neue Anlagen, neue Anträge, geänderter Vorschlag), Diff ohne Modell plus ein Satz | Wer im Ausschuss saß, liest im Rat nur noch den Unterschied | < 0,10 $ | PR 12 |
| 4 | **Lücken als Vorschlagsfragen:** Pflichtfelder der Form mit Status `absent` („Folgekosten ab 2028 nicht beziffert“, „keine Alternative genannt“) | Das sind die Fragen, die man in der Sitzung stellt | ≤ 0,05 $ | PR 12, 16 |
| 5 | **Vorher statt nachher benachrichtigen:** Orte und Betroffene aus dem Dossier treffen „Mein Viertel“ und Themen-Abos schon bei der Vorlage, nicht erst beim Beschluss | „Am Dienstag entscheidet der Verkehrsausschuss über …“ kommt, solange man noch etwas tun kann | ≈ 0,1 $ | PR 12 |
| 6 | **Sitzungsmappe am Vortag:** Seite je Sitzung mit Kostensumme, allen Anträgen alt gegen neu, Fristen und Prüfhinweisen; Mail optional | Vorbereitung ohne jede Punkt-Seite einzeln | ≈ 0,1 $ | PR 9, 12 |
| 7 | **Zusagen der Verwaltung nachhalten:** 1.447 Wortbeiträge vom Typ `pledge` gegen spätere Vorlagen; „im ASB zugesagt … · diese Vorlage antwortet darauf“ | Belegte Rückfragen | ≈ 0,2 $ | PR 12 |
| 8 | **Suche über ganze Dokumente:** Dossier-Aussagen mit Seite als zusätzliche Stücke in FTS und Vektorindex (heute höchstens 4 bzw. 8 Stücke je Dokument) | KI-Frage, Lotti und MCP finden und zitieren seitengenau | 0 $ (fastembed) | PR 12 |
| 9 | **Große Anlagen seitengenau:** Studien, Gutachten, Jahresabschlüsse ab 20 Seiten an Rats-Punkten bekommen 5–8 Kernaussagen mit Seite (`plan_judge.key_points`); RPA B/WB mit Textziffer | Ein Materialband mit 361 Seiten wird verlinkbar | 0,2–0,4 $ | PR 17 |
| 10 | **Beschluss-Texte lesen die Vorlage:** `simple_summary`, Interessantheit und Klassifikation bekommen Dossier-Felder statt 300–900 Zeichen | Bessere Beschluss-Seiten, auch rückwirkend | +0,2 $ | PR 16 |
| 11 | **Haushaltsbezug der Kosten:** Produktnummern auf die Haushaltsschichten abbilden, nur mit Recht `budget` | Ob ein Betrag groß ist, wird einschätzbar | 0 $ | Haushalt auf Prod |

---

## 11. Risiken

- **Echtes Zitat, verdrehter Satz.** Die Belegprüfung fängt erfundene Zitate und
  Zahlen, aber keine verdrehte Aussage über ein echtes Zitat. Dagegen helfen die
  Handprüfung „gestützt/treu“, kurze Sätze, je Satz ein Zitat und die
  Vor-Ernte-Kandidaten für Beträge und Daten.
- **Zu viel verworfen, Abschnitte leer.** Das misst die Wegfallquote je Form.
  Folge ist eine Schärfung von Prompt oder Vor-Ernte, nie eine gelockerte
  Prüfung.
- **Falsch behauptete Lücken.** Eine Abwesenheit steht nur mit Beleg oder nach
  vollständigem Lesen da. Im Tor zählt sie als „falsch“.
- **Tabellen ohne Spalten.** Synopse, Änderungslisten und Abwägung sind im
  Textlayer verschachtelt. Alt gegen neu kommt bis PR 17 nur aus §-Ankern und
  Anträgen, nie aus der flachen Synopse.
- **Fassungen.** Fehlt im Antrag die Vorlagennummer, steht „Basis unklar“ statt
  eines Diffs.
- **Späte Anträge.** Auch der Nachzügler-Lauf verpasst, was während der Sitzung
  eingeht. Mitlesen und der Abruf fangen es auf. Tischvorlagen sind nie im
  Ratsinfo.
- **Seitensprünge stimmen nicht.** Offsets per Anker im gespeicherten Text, dazu
  `text_hash`. Ein Test liest eine Anlage mit Trennstrichen und Anschrift.
- **Neue Spalten gehen verloren.** Alles Neue hängt an `document_id` in eigenen
  Tabellen. Der Test „Sitzung zweimal einlesen“ hält das fest.
- **Datenschutz.** Einsprüche und Abwägungen nennen Privatpersonen, gesperrte
  Schrift umgeht `entfernen`. Dagegen helfen Namensregel, Ausgabefilter mit
  Zusammenziehen und Fixtures außerhalb des Repos.
- **Fremde Anweisungen in Dokumenten.** Dagegen helfen Fremdtext-Markierung,
  JSON-Ausgabe und Filter über alle erzeugten Sätze.
- **Neutralität.** „Was die Verwaltung sagt“ ist die Haltung der Verwaltung und so
  beschriftet. Das Modell gewichtet nicht und empfiehlt nichts.
- **Wortlaut flattert.** Anträge und Belegmaterial gehen nicht in den Hash ein.
  Neue Prompt-Fassungen werden nur geplant und in Tranchen neu gerechnet.
- **Ergebnisregel.** Das Dossier spricht vom Vorschlag. Auf der Beschluss-Seite
  steht es eingefroren unter „Aus der Vorlage“ neben dem Ergebnis.
- **Übervertrauen.** Dagegen helfen [n] an jeder Aussage, der Link auf die genaue
  Seite und der KI-Stern.
- **Zu viel auf der Seite.** Leere Abschnitte entfallen, es gelten Obergrenzen,
  Belegmaterial steht eingeklappt, die Abnahme läuft per Bild.
- **Kosten laufen davon.** Dollar-Deckel je Lauf und Tag, `stopp.ausgeben`, keine
  Ersatzmodelle mit 24k-Boden, `LLM_TAGESKOSTEN_ALARM_USD` greift ohnehin.
- **Last auf dem Ratsinfo.** Höchstens 1 Abruf je Sekunde, rund 500 PDFs im Jahr
  zusätzlich, Nachzügler-Läufe nur an Sitzungstagen. Ein Austausch fällt ohne
  zusätzlichen Abruf auf.
- **App im Store.** Alle Felder sind optional, Enums haben `unknown`.
  `ios_vertrag --ausgeliefert` läuft vor dem Release.

---

## 12. Offene Fragen an Tim

1. **Tore** wie in Abschnitt 7: 97 % gestützt, 95 % treu, 85 % Pflichtfakten,
   Leitfragen ≥ 80 % beantwortbar bei **0 falschen**?
   *Empfehlung:* so annehmen. Strenger wird es nur bei „falsch“, und das steht
   schon auf null.
2. **Name des Blocks:** „Aus den Unterlagen“, „Das steht drin“ oder „Steckbrief“?
   *Empfehlung:* „Aus den Unterlagen“. „Auf einen Blick“ ist rechts vergeben.
3. **Stufe 4:** Sollen Kartentext, Vorschlagsfragen und Tragweite nach bestandener
   A/B-Messung aus dem Dossier entstehen?
   *Empfehlung:* ja. Das gibt eine Quelle der Wahrheit, keine Widersprüche und
   etwas geringere Kosten.
4. **Nachzügler-Lauf** an Sitzungstagen um 11, 13, 16 und 18 Uhr, mit einem Abruf
   je Sitzung und Lauf?
   *Empfehlung:* ja. Die Last ist gering, und Anträge vom Sitzungstag sind Tims
   Kernfall.
5. **Bestand:** 12 Monate per Lauf (≈ 0,7 $), älteres nur auf Abruf, oder alles
   seit 2018 (≈ 6,3 $)?
   *Empfehlung:* 12 Monate per Lauf, älteres auf Abruf. Den Rest erst, wenn der
   Abruf zeigt, dass alte Seiten gelesen werden.
6. **Beschluss-Seite:** das eingefrorene Dossier als „Aus der Vorlage“ zeigen,
   oder nur „Vorgeschlagen ↔ beschlossen“ und die Anträge?
   *Empfehlung:* zeigen. Gerade bei alten Beschlüssen fehlt heute jede
   Aufbereitung der Vorlage.
7. **Prüfhinweise** (Widersprüche, nicht beigefügte Altfassung, frühere Fassung)
   sichtbar machen?
   *Empfehlung:* ja, als Feststellung über die Unterlagen oben in der
   Gegenlese-Liste, nicht im Hauptblock. Dort wirken sie nicht wie eine Wertung.
8. **OCR für Lesestoff-Scans** (Satzungstext von Veränderungssperren, Einsprüche;
   ≈ 0,5 $ im Jahr)?
   *Empfehlung:* ja, aber erst, wenn das Gold zeigt, wie oft Felder auf `unread`
   stehen.
9. **Ohne Konto:** Das Dossier ist für alle sichtbar, weil der Cron es erzeugt.
   Der Abruf bleibt wie bei den Vorschlagsfragen angemeldeten Konten vorbehalten.
   *Empfehlung:* so lassen. Das schützt vor Crawlern auf dem Normaltarif.
10. **Ersatzkette ohne DeepSeek** für lange Extraktionen als dokumentierte
    Ausnahme in `kern/CLAUDE.md`?
    *Empfehlung:* ja. Der 24k-Boden hat am 09.11. 0,78 $ ohne Ergebnis gekostet.
11. **Handprüfung:** Der Agent liest alle Urteile, Tim prüft 5 Fälle
    stichprobenartig. Reicht das?
    *Empfehlung:* ja, wie bei den Punkt-Argumenten. Bei einer Abweichung zwischen
    Agent und Tim wird der ganze Fall neu gelesen.
12. **Fix der leeren Anlagenliste** auf der Beschluss-Seite (auf Prod seit 02.09.):
    gegen `main` oder mit dem Release?
    *Empfehlung:* gegen `main` (PR 3). Es ist eine Zeile, und die Liste fehlt
    seit zehn Wochen.
13. **Sitzungsmappe** (Idee 6) per Mail, und für Ratsmitglieder ab Werk an?
    *Empfehlung:* zuerst nur als Seite. Die Mail erst, wenn die Meldung bei neuen
    Anträgen (Idee 1) läuft, und dann für die Rolle Ratsmitglied ab Werk an.
