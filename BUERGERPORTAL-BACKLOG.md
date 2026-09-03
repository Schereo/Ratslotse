# Bürgerportal: bestätigte Reihenfolge

Quelle für die aktuelle Migration ist Parent-Issue #1033. Jeder Punkt wird als
eigener vertikaler Schnitt von aktuellem `feature` umgesetzt, auf
`feature.ratslotse.de` geprüft und ausdrücklich abgenommen. Vor dieser Abnahme
beginnt kein späterer Punkt.

## Verbindliche Leitplanken

- Öffentliche Problemprojektion und private Meldungen bleiben getrennte Domänen.
- Rohtexte, Identitäten, Moderationsnotizen und genaue private Orte bleiben privat.
- Reale Veröffentlichung braucht aktuelle geeignete KI-Vorprüfung und
  unveränderliche menschliche Freigabe; Fehler bleiben geschlossen.
- Häufigkeitsfarben bedeuten nie Dringlichkeit.
- Stadtweite oder ungültige Geometrien erhalten keinen erfundenen Kartenpunkt.
- Ratslotse ist kein amtliches System der Stadt Oldenburg.

## Iterationen

1. **Öffentliche Problemübersicht (#1034): umgesetzt auf diesem Task-Branch.**
   Rein lesende API-Projektion, Karte, Themenfilter, vollständiges Status-Board,
   alle ehrlichen Geometrieformen, sichere Feature-Beispiele, Navigation,
   Sitemap und aktueller Vertrag.
2. Öffentliche Detailseite und plattformgerechte Verlinkung — offen.
3. Private Meldungs-Domäne und sichere Persistenz — offen.
4. Eigentümergebundene Entwurfs- und Einreichungs-API — offen.
5. Geführter Meldechat und prominenter Einstieg — offen.
6. Lokale Sicherheits-/Eignungsprüfung vor externen KI-Aufrufen — offen.
7. Moderation, Clustering, privates Dashboard und Beta-Betrieb — in weitere,
   einzeln abgenommene Schnitte zu zerlegen.

## Nicht Teil von #1034

Keine Detailseite, privaten Meldetabellen oder Meldungsendpunkte, KI-Aufrufe,
Moderationsoberfläche, automatische Veröffentlichung, Uploads oder öffentlichen
Kommentare. Die nächste Iteration startet erst nach ausdrücklicher Abnahme der
deployten Übersicht.
