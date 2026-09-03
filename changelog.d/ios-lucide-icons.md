---
kategorie: geaendert
---

**Die App zeichnet jetzt durchgehend mit derselben Bildsprache wie die
Website.** Bisher mischten sich Apples SF Symbols unter die Lucide-Icons der
Web-App — an 240 Stellen, in 123 verschiedenen Zeichen. Sie sahen daneben
fremd aus, weil sie eine andere Strichstärke und andere Rundungen haben. Alle
sind ersetzt; die Vektoren stammen aus demselben Lucide-Satz, den auch die
Website benutzt, und liegen als Assets in der App, damit sie ohne Netz und
ohne Laufzeit-Abhängigkeit rendern. Eine Ausnahme bleibt bewusst stehen: das
Apple-Zeichen bei „Mit Apple verknüpft" — Apples Richtlinien verlangen dort
ihre eigene Marke. Ein Test in der CI hält den Zustand, damit sich kein
SF Symbol zurückschleicht.
