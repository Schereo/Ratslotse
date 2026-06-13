## Task 3: Exclude "Einwohnerfragestunde" from committee summaries

**Problem:** Der TOP "Einwohnerfragestunde" (public question time) kommt bei JEDER Sitzung vor und ist immer nur Routine. Die GPT-Summary soll ihn nicht erwähnen.

**Wo:** `council/committee_summary.py` — `summarize_agenda()` Funktion

**Was zu tun:**
- Füge im System-Prompt einen expliziten Hinweis ein: "Ignoriere Tagesordnungspunkte die 'Einwohnerfragestunde', 'Bürgerfragestunde' oder ähnliche Bürgerbeteiligungs-Formate betreffen — diese sind Routine und nicht zusammenfassungsrelevant."
- Ergänze auch eine clientseitige Filterung: Vor dem Prompt-Bau filtere Agenda-Items deren Titel "Einwohnerfragestunde", "Bürgerfragestunde", "Fragestunde" enthalten raus
- Dadurch werden sie nie an GPT gesendet — spart Tokens UND stellt sicher dass sie nie in der Summary auftauchen

**Test:** Ein Agenda-Item mit `title="Einwohnerfragestunde"` wird vor dem Prompt gefiltert.

**Nicht ändern:** Andere Filter-Logik, Bot-Kommandos, Buttons. Nur `committee_summary.py`.

Branch: `feat/filter-einwohnerfragestunde`