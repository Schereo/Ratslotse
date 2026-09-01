---
kategorie: behoben
---

**In der App klebten Absätze und Zwischenüberschriften der KI-Antwort aneinander.**
„… vertagt ⑦.Kosten und FinanzierungPlanungskosten: …" — ohne Leerzeichen, und
die Überschrift stand unformatiert mitten im Fließtext. Ursache war der
Markdown-Parser von iOS: Er erkennt Absätze, Überschriften und Listen zwar,
wirft ihre Grenzen im Ergebnis aber ersatzlos weg. Die App schneidet die Blöcke
jetzt selbst — Überschriften stehen als Überschriften, Aufzählungen als
Aufzählungen, Absätze mit Luft dazwischen. Ebenfalls behoben: Unter „Aktuelles
von der Stadt" stand nur eine Überschrift samt Link nach draußen; die Meldung
selbst lag längst in der Datenbank und wurde auf dem Weg zur Anzeige verworfen —
jetzt steht sie da, im Web wie in der App. Und die Datumszeilen der Belege
zeigten stellenweise das rohe „2026-08-27" statt „27. Aug. 2026".
