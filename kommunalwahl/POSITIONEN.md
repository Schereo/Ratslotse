# Auftrag: Positionsbestimmung zu 44 Thesen

Du bestimmst für **einen** Wahlvorschlag zur Ratswahl Oldenburg 2026, wie er zu 44 Thesen
steht. Grundlage ist **ausschließlich** sein Programm-Volltext. Welcher, steht in deinem
individuellen Prompt.

**BASE** = Wurzel dieses Ordners (`kommunalwahl/` im Ratslotse-Repo).
Setze sie einmal in der Shell: `export BASE="$(pwd)"`

## Sparsam und belegt arbeiten

Lies den Volltext **nicht am Stück** ein. Nutze das Suchwerkzeug:

```
python3 "$BASE/suche.py" <slug> "<regex>" [--kontext 3] [--max 8]
```

Es zeigt Fundstellen mit Seitenzahl und Kontext. Beispiel:

```
python3 "$BASE/suche.py" spd "Fliegerhorst|Entlastungsstra" --kontext 3
```

Arbeite die Thesen thematisch gebündelt ab, mehrere Suchbegriffe pro Aufruf mit `|`.
Nur wenn die Suche nichts Brauchbares liefert und du den Verdacht hast, das Thema sei
anders benannt, lies gezielt einen Abschnitt mit Read (mit `offset`/`limit`).
Ziel: unter ~30 Tool-Aufrufen.

## Bewertungsmaßstab

Für jede These genau einen Wert:

| Wert | Bedeutung |
|---|---|
| `1` | **Zustimmung** — das Programm fordert das oder Gleichbedeutendes. |
| `0` | **Teils/teils** — grundsätzlich dafür, aber mit erheblichen Einschränkungen; oder das Programm nennt Pro und Contra ohne klare Festlegung; oder es fordert etwas deutlich Schwächeres als die These. |
| `-1` | **Ablehnung** — das Programm lehnt das ab oder fordert klar das Gegenteil. |
| `null` | **Keine Aussage** — das Programm äußert sich dazu nicht. |

**Die wichtigste Regel:** `null` ist kein Makel und keine Lücke, die du füllen sollst.
Wenn ein Programm zu einer These schweigt, ist `null` die einzige richtige Antwort.
Leite Positionen **nicht** aus der allgemeinen politischen Ausrichtung der Partei ab,
nicht aus Bundes- oder Landesprogrammen und nicht aus deinem Vorwissen über die Partei.
Nur was im vorliegenden Oldenburger Text steht, zählt. Lieber viele `null` als geraten.

Ebenso: Werte eine schwache, allgemeine Absichtserklärung nicht als volle Zustimmung.
„Wir wollen bezahlbaren Wohnraum" ist **keine** Zustimmung zur These, eine zusätzliche
städtische Wohnungsbaugesellschaft zu gründen — das wäre `null`.

## Ausgabe

Schreibe `$BASE/positionen/<slug>.json` **per Python-Heredoc** (nicht mit dem Write-Tool —
deutsche Anführungszeichen zerlegen sonst das JSON):

```
python3 - <<'PYEOF'
import json
d = {
  "slug": "<slug>",
  "positionen": {
    "W1": {"pos": 1, "beleg": "Kurzzitat oder knappe Paraphrase der Fundstelle", "seite": 12},
    "W2": {"pos": None, "beleg": None, "seite": None},
    # ... alle 44 IDs
  }
}
json.dump(d, open("positionen/<slug>.json","w",encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("ok", len(d["positionen"]))
PYEOF
```

- **Alle 44 Thesen-IDs müssen vorkommen**, auch die mit `null`.
- `beleg`: bei `1`, `0` oder `-1` **Pflicht** — maximal ein Satz, der die Einstufung trägt.
  Bei `null` ebenfalls `null`.
- `seite`: PDF-Seitenzahl aus der Suchausgabe; bei Webquellen `null`.
- Die Thesen stehen in `$BASE/thesen.json` (Feld `these`, dazu `hinweis` mit lokalem Kontext).

## Abschlussnachricht (max. 8 Zeilen)

Verteilung der Werte (wie viele 1 / 0 / -1 / null), die 3 markantesten Positionen,
aufgetretene Zweifelsfälle. Die JSON-Datei ist das Ergebnis.
