# Prüfungen des Datenbestands

Die Skripte, mit denen der Bestand am 07.08.2026 vollständig nachgeprüft wurde.
Ergebnis und Bewertung: [`../pruefbericht.md`](../pruefbericht.md).

Alle lösen ihre Pfade relativ zum eigenen Ort auf und laufen ohne Abhängigkeiten
(reine Standardbibliothek). Aufruf von überall:

```bash
python3 kommunalwahl/pruefungen/pruef_struktur.py
```

## Prüfer (sollten grün bleiben)

| Skript | Prüft |
|---|---|
| `pruef_struktur.py` | Vollständigkeit der 16 Positionsdateien, Gültigkeit jedes `pos`, Kopplung `pos ↔ beleg ↔ seite`, Gleichlauf mit `data.json` — und rechnet **alle** abgeleiteten Zahlen nach: 120 Paare × 13 Werte, `thesen_stat`, `abdeckung`, Kandidatensummen |
| `pruef_zitate.py` | Jedes wörtliche Zitat in einem Beleg gegen den Programm-Volltext, tolerant gegenüber Auslassungen (`…`, `[...]`) und Flexions-Einschüben (`[r]`) |
| `pruef_seiten.py` | Wo ein Zitatstück lokalisierbar ist: stimmt die angegebene Seite? Meldet außerdem Positionen ohne Seitenzahl trotz PDF-Quelle |

**Zwei bekannte, geprüfte Fehlalarme** — beide sind in Ordnung, nicht „reparieren":

- `pruef_struktur.py` warnt beim Bürgerentscheid, dass `ja + nein` (37 242) kleiner ist als die
  Beteiligung (37 295). Die Differenz sind **53 ungültige Stimmen**; die Prozentwerte sind
  korrekt auf die gültigen Stimmen gerechnet.
- `pruef_seiten.py` meldet `linke/D1` mit S. 11 statt S. 9. Der Beleg verbindet zwei
  Fundstellen; die angegebene Seite gehört zur Hauptaussage. Ebenso meldet `pruef_zitate.py`
  `bsw/M2` als teilweise belegt — dort trennt die PDF-Extraktion „Tempo 30 Zonen" ohne
  Bindestriche.

## Werkzeuge zur Nachprüfung von Hand

| Skript | Zweck |
|---|---|
| `finde.py <slug> <regex> [breite]` | Fundstellen im entsilbten Fließtext, mit Seitenzahl und ungekürztem Kontext — genauer als `suche.py`, weil Zeilenumbrüche und Silbentrennung aufgelöst werden |
| `zeige.py <themenkey\|thesen-id…\|alle>` | Eine These mit den Positionen **aller** Vergleichslisten nebeneinander. Das Werkzeug für die inhaltliche Durchsicht: So fallen Listen auf, die dasselbe sagen und verschieden eingestuft sind |

## Analysen (kein Grün/Rot, sondern Kennzahlen)

| Skript | Zeigt |
|---|---|
| `pruef_methode.py` | Wie viel Ähnlichkeit aus beidseitigem „teils/teils" stammt, wie stark die Werte an einzelnen Thesen hängen (Jackknife), und auf wie wenigen Thesen die Themen-Teilwerte stehen |
| `pruef_konsistenz.py` | Tragfähigkeit jeder These, Belege mit Einschränkungssprache trotz klarer Note, Paare mit gleichem Stichwort und entgegengesetzter Note, Auskunftsdichte je Liste |
| `pruef_besonderes.py [grenze]` | Ob die „Fällt auf"- und Kernpunkt-Aussagen im Programmtext verankert sind |
