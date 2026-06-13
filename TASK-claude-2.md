## Task 2: Replace /subscriptions with the /committees menu

**Problem:** `/subscriptions` zeigt nur eine Textliste der Abos. Der Benutzer will stattdessen das `/committees` Menü (mit Inline-Buttons zum Abonnieren/Kündigen) auch unter `/subscriptions` sehen.

**Was zu tun:**
- Ändere den `/subscriptions` Handler so, dass er genau das gleiche wie `/committees` anzeigt — die vollständige Ausschussliste mit ✅/➕ Buttons
- `/subscriptions` alleine wird nicht mehr gebraucht — der Befehl wird quasi zum Alias für `/committees`

**Technisch:**
- Der `/subscriptions` Befehl soll die gleiche Funktion aufrufen wie `/committees` (den Button-Code verwenden)
- Extrahiere die Committee-List-Logik in eine gemeinsame Hilfsfunktion falls nötig
- `handle_callback_query` bleibt unverändert — die Buttons sind identisch
- `/help` aktualisieren: `/subscriptions` zeigt "Ausschussliste mit Buttons" an

**Nicht ändern:** `handle_callback_query`, `_committee_buttons`, Telegram-Funktionen, Tests

Branch: `feat/subscriptions-committees-menu`