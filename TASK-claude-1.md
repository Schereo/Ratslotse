## Task 1: Fix committee list to include ALL Oldenburg committees

**Problem:** Der Bot zeigt nur ~10 Ausschüsse an, aber es gibt mehr. Die Quelle ist `buergerinfo.oldenburg.de` (Bürgerinformationssystem). Der Scraper findet nur Ausschüsse die aktuell Sitzungen haben — Ausschüsse ohne Termine tauchen nicht auf.

**Vollständige Liste der Oldenburger Fachausschüsse (von oldenburg.de):**
1. Ausschuss für Allgemeine Angelegenheiten
2. Ausschuss für Finanzen und Beteiligungen
3. Ausschuss für Integration und Migration
4. Ausschuss für Stadtgrün, Umwelt und Klima
5. Ausschuss für Stadtplanung und Bauen
6. Ausschuss für Wirtschaftsförderung, Digitalisierung und internationale Zusammenarbeit

Plus Pflichtausschüsse (Schulausschuss, Jugendhilfeausschuss etc.) und ggf. weitere Gremien.

**Mögliche Lösungen:**
1. Das Bürgerinformationssystem hat vermutlich eine Seite die alle Gremien auflistet — z.B. `https://buergerinfo.oldenburg.de/gremien/` oder ähnlich. Finde die URL und scrape sie.
2. Falls keine API-Seite existiert: Erstelle eine statische Liste in einer Konfigurationsdatei als Fallback.

**Was zu tun:**
- Untersuche `buergerinfo.oldenburg.de` auf eine Gremien-Übersichtsseite
- Ergänze den `CouncilScraper` um eine Methode `fetch_all_committees()` die alle Ausschuss-Namen lädt
- Speichere die Namen in `council_sessions` Tabelle (oder einer neuen Tabelle) damit `/committees` sie anzeigt
- Falls Scraping nicht möglich: Lege `data/committees.json` mit der vollständigen Liste an

**Nicht ändern:** Bestehende Session-Scraping-Logik, Bot-Kommandos, Buttons. Nur die Datenquelle für Committees erweitern.

Branch: `feat/all-committees`