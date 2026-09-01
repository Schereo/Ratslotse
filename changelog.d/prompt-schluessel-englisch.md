---
kategorie: geaendert
---

**Auch die Namen der Prompt-Vorlagen heißen jetzt englisch.** Jede Vorlage in
`kern/prompts.py` trägt einen Namen, unter dem der Code sie abruft — bisher
gemischt deutsch (`qa_antwort`, `top_wichtigkeit_system`), jetzt durchgängig
englisch wie der übrige Code (`qa_answer`, `agenda_item_importance_system`).
Der Text der Prompts ist unangetastet geblieben, Zeichen für Zeichen: Er ist
das, was das Sprachmodell liest, und er bleibt deutsch. Für Leser*innen von
ratslotse.de ändert sich nichts.

Neu ist ein Wächter, der beides in beide Richtungen abgleicht — kein Abruf
ohne Vorlage, keine Vorlage ohne Abruf. Ein Vorlagen-Name ist nur eine
Zeichenkette: Wer ihn an einer Stelle ändert und an der anderen vergisst,
merkt das sonst erst mitten in einem nächtlichen Lauf.
