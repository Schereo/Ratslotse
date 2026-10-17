---
kategorie: hinzugefuegt
---

**Eigener Agent: Ratsdaten über MCP.** Konten mit der neuen Rolle „MCP-Zugang“ stellen sich in den Einstellungen persönliche Schlüssel aus, bis zu fünf, und schließen damit Claude, ChatGPT, Cursor oder einen anderen MCP-fähigen Agenten an `/api/mcp` an. Der Agent sucht dann selbst in Beschlüssen, liest Vorlagen samt ihren Anlagen, Beratungsfolgen, Sitzungen, Tagesordnungen und den Protokollabschnitt zu jedem Punkt, und er zählt Beschlüsse. Eine noch nicht geladene Anlage holt Ratslotse beim ersten Abruf nach. Jede Antwort kommt als JSON und bringt die Adressen auf Ratslotse und im Ratsinformationssystem mit. Er kann nur lesen, der Haushalt ist nicht dabei, und auf unserer Seite läuft kein Sprachmodell. Vorerst nur auf dev, hinter dem Schalter `mcp-server`.
