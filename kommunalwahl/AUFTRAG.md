# Auftrag: Wahlprogramm-Auswertung Stadtratswahl Oldenburg 2026

Du wertest **einen** Wahlvorschlag zur Ratswahl der **Stadt Oldenburg (Oldb), Niedersachsen**
am **13. September 2026** aus. Welchen, steht in deinem individuellen Prompt.
Ziel des Gesamtprojekts: eine neutrale Vergleichsseite (Wahl-O-Mat-Charakter) über alle 16
zugelassenen Wahlvorschläge.

**BASE** = Wurzel dieses Ordners (`kommunalwahl/` im Ratslotse-Repo).
Setze sie einmal in der Shell: `export BASE="$(pwd)"`

## Sparsam arbeiten (wichtig)

Ein früherer Durchlauf ist am Token-Limit gescheitert. Deshalb:

- **Niemals HTML- oder PDF-Rohinhalte in den Kontext lesen.** Immer erst per Skript in Text
  wandeln, dann nur die `.txt` mit Read öffnen.
- **WebFetch nur als letzte Rettung** (JS-Seite, 403). Erste Wahl ist `curl` + Konverter.
- Höchstens ca. **4 Suchanfragen**. Findest du nach gründlicher Suche nichts, ist
  `"gefunden": false` ein korrektes Ergebnis — kein Grund weiterzusuchen.
- Keine Kandidatenlisten, Impressen, Spendenseiten o. Ä. laden. Nur Programminhalte.
- Ziel: unter ~25 Tool-Aufrufen bleiben.

## Schritt 1 — Programm finden

Gesucht: das offizielle **kommunale Wahlprogramm zur Stadtratswahl Oldenburg 2026**.

Verwechslungsgefahr, unbedingt prüfen:
- **Stadt Oldenburg (Oldb), Niedersachsen** — NICHT Landkreis Oldenburg / Oldenburg-Land,
  NICHT Oldenburg in Holstein.
- **Kommunalwahl 2026** — NICHT Bundestagswahl 2025, nicht Landtagswahl, nicht 2021.
- Bundes-, Landes- oder Grundsatzprogramme sind **kein Ersatz** für ein Kommunalprogramm.

Fallstufen:
1. Vollständiges Programm (PDF oder Webseite) → ideal.
2. Kein Langprogramm, aber offizielle kommunale Kernforderungen/Thesen 2026 (auch
   Kandidatenporträt mit inhaltlichen Aussagen) → nimm das, setze `programm.hinweis`.
3. Nichts Kommunales für 2026 → `"gefunden": false`, `hinweis` dokumentiert die Suche.
   **Nichts erfinden, nicht auf Bundesprogramme ausweichen.**

**Keine Browser-Tools** (`mcp__Claude_Browser__*`, `mcp__claude-in-chrome__*`).

## Schritt 2 — Volltext sichern

PDF:
```
curl -sL --max-time 120 -A "Mozilla/5.0" -o "$BASE/programme/<slug>.pdf" '<URL>'
file "$BASE/programme/<slug>.pdf"          # muss "PDF document" sagen
python3 "$BASE/extract.py" "$BASE/programme/<slug>.pdf" "$BASE/programme/<slug>.txt"
```

Webseite (mehrere Seiten nacheinander anhängen):
```
curl -sL --max-time 60 -A "Mozilla/5.0" -o /tmp/s1.html '<URL>'
python3 "$BASE/html2text.py" /tmp/s1.html "$BASE/programme/<slug>.txt"
python3 "$BASE/html2text.py" /tmp/s2.html "$BASE/programme/<slug>.txt" --append
```

Dann `<slug>.txt` mit Read lesen (lange Dateien abschnittsweise) und an Titel/Einleitung
verifizieren, dass es wirklich das Kommunalprogramm 2026 der Stadt Oldenburg ist.

## Schritt 3 — Auswertung schreiben

Ziel: `$BASE/digests/<slug>.json`.

**Schreibe die Datei mit einem Python-Heredoc, nicht mit dem Write-Tool** — deutsche
Anführungszeichen und Umlaute haben zuvor kaputtes JSON erzeugt:

```
python3 - <<'PYEOF'
import json
d = { ... }   # Python-Dict, hier ganz normal deutsche Anführungszeichen erlaubt
json.dump(d, open("digests/<slug>.json","w",encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("ok")
PYEOF
```

Schema (alle Felder Pflicht):

```json
{
  "slug": "<slug>",
  "partei": {"kurz": "...", "name": "<amtliche Bezeichnung>", "typ": "partei|waehlergruppe|einzelbewerber", "kandidaten": 0},
  "programm": {"gefunden": true, "titel": "...", "url": "...", "format": "pdf|web",
               "seiten": null, "stand": null, "hinweis": null},
  "charakter": "<2-3 Saetze: Gesamtcharakter, Tonalitaet, Schwerpunkte>",
  "kernpunkte": ["<5-7 markanteste, konkreteste Forderungen>"],
  "themen": {
    "wohnen": {"positionen": ["..."], "seiten": [], "praegnanz": 0},
    "mobilitaet": {...}, "klima": {...}, "wirtschaft": {...}, "bildung": {...},
    "soziales": {...}, "kultur": {...}, "sicherheit": {...}, "digitales": {...},
    "finanzen": {...}, "beteiligung": {...}, "integration": {...}
  },
  "besonderes": ["<ungewoehnliche oder besonders ortsspezifische Forderungen>"]
}
```

### Themen-Zuordnung (alle 12 Schlüssel müssen existieren, auch leer)

| Schlüssel | umfasst |
|---|---|
| `wohnen` | Wohnen, Mieten, Wohnungsbau, Stadtentwicklung/Quartiere, Bauland, Wohnungslosigkeit |
| `mobilitaet` | Rad-/Fußverkehr, ÖPNV/Bus, Auto/Parken, Straßen, Bahnanbindung, Verkehrssicherheit |
| `klima` | Klimaschutz/-anpassung, Energie/Wärme, Stadtgrün/Bäume/Natur, Wasser, Abfall, Tierschutz |
| `wirtschaft` | Wirtschaftsförderung, Gewerbeflächen, Innenstadt/Einzelhandel, Tourismus, Fachkräfte, Hochschulstandort |
| `bildung` | Kitas/Betreuung, Schulen (Bau, Sanierung, Ganztag, Digitalisierung), Jugendbildung, VHS |
| `soziales` | Armut, Familien, Senioren, Inklusion, Gesundheit/Klinikum, Pflege, Sucht-/Drogenhilfe |
| `kultur` | Kultureinrichtungen, Theater, Museen, Soziokultur, Sport, Bäder, Vereine, Nachtleben, Erinnerungskultur |
| `sicherheit` | Ordnung, Sauberkeit, Ordnungsdienst/Polizei, Prävention, Videoüberwachung, Feuerwehr/Katastrophenschutz |
| `digitales` | Verwaltungsdigitalisierung, Bürgerservice, Smart City, Open Data, Personal der Stadtverwaltung, Bürokratieabbau |
| `finanzen` | Haushalt, Schulden, Steuern/Hebesätze/Gebühren, städtische Beteiligungen, Investitionsprioritäten |
| `beteiligung` | Bürgerbeteiligung, Transparenz, Jugendbeteiligung, Stadtteilarbeit, Ehrenamt, Demokratieförderung |
| `integration` | Migration, Geflüchtete, Integration, Vielfalt/Antidiskriminierung, Gleichstellung, Queer |

### Regeln

- **`positionen`**: pro konkreter Forderung ein kurzer Satz in eigener Formulierung (keine
  langen Zitate). So konkret wie das Programm selbst — Zahlen, Straßen, Projektnamen,
  Stadtteile ausdrücklich nennen. Lieber 8 präzise Sätze als 20 vage.
- **`seiten`**: PDF-Seitenzahlen aus den `[Seite N]`-Markern; bei Webquellen leere Liste.
- **`praegnanz`**: 0 = kommt nicht vor, 1 = Randnotiz, 2 = eigener Abschnitt, 3 = Schwerpunkt.
- **Strikt sachlich-neutral**, für alle Listen derselbe Maßstab — auch bei polarisierenden
  Inhalten: exakt wiedergeben, weder abschwächen noch verschärfen, nicht kommentieren.

## Abschlussnachricht (kurz halten, max. 10 Zeilen)

gefunden ja/nein · Titel · URL · Format/Seiten · 2 Sätze Inhalt · Probleme.
Die JSON-Datei ist das eigentliche Ergebnis.
