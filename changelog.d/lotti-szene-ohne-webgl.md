---
kategorie: behoben
---

**Startseite ohne WebGL zeigte die Fehlerseite.** Die 3D-Lotti-Szene baut auf dem Desktop einen WebGL-Renderer, und wenn der Browser keinen Kontext hergibt (Hardware-Beschleunigung aus, ein Browser ohne WebGL), warf das eine Ausnahme mitten im Aufbau — statt der Startseite stand „Etwas ist schiefgelaufen". Jetzt wird vorher geprüft, ob WebGL überhaupt geht, und die Szene meldet einen Fehlschlag, statt zu werfen; in beiden Fällen bleibt die gezeichnete Lotti-Familie stehen, wie auf dem Handy.
