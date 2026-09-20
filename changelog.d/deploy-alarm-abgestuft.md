---
kategorie: behoben
---

**Ein abgebrochener Deploy weckt nur noch, wenn die Seite betroffen ist.** Bisher schickte jeder Abbruch dieselbe Alarm-Mail — auch die Abbrüche, die vor dem Umschalten passieren und die laufende Seite gar nicht anfassen. Am 20.09.2026 waren das fünf von sechs an einem Tag, alle mit dem Satz „die Seite ist unten", während sie lief; die eine Mail, die zählte, ging darin unter. Jetzt misst der Alarm vorher, ob Wartungsbarriere und Dienste überhaupt betroffen sind, und bleibt sonst still.

Damit dabei nichts unbemerkt liegen bleibt, holt ein neuer Wächter halbstündlich nach, was liegen geblieben ist: Ist ein Stand nicht auf ratslotse.de angekommen und blockiert kein langer Hintergrundlauf mehr, startet die Veröffentlichung von selbst — und meldet sich, wenn das über Stunden nicht klappt. Kurze Hintergrundläufe wartet die Veröffentlichung jetzt außerdem ab, statt an ihnen zu scheitern.
