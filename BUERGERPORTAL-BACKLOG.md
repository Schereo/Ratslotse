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

1. **Öffentliche Problemübersicht (#1034): umgesetzt.** Rein lesende
   API-Projektion, Karte, Themenfilter, alle ehrlichen Geometrieformen, sichere
   Feature-Beispiele, Navigation, Sitemap und öffentlicher Vertrag.
2. **Rangliste (#1042): umgesetzt auf diesem Task-Branch.** Nur ungelöste Projektionen, exakte
   lebenszeitliche Zahl unabhängiger Meldungen, deterministische Rangfolge,
   vergleichbare Balkenschienen, zugängliche Vorschauen und ehrlicher Kartenfokus.
3. Öffentliche Detailseite und plattformgerechte Verlinkung — offen.
4. Private Meldungs-Domäne und sichere Persistenz — offen.
5. Eigentümergebundene Entwurfs- und Einreichungs-API — offen.
6. Geführter Meldechat und prominenter Einstieg — offen.
7. Lokale Sicherheits-/Eignungsprüfung vor externen KI-Aufrufen — offen.
8. Moderation, Clustering, privates Dashboard und Beta-Betrieb — in weitere,
   einzeln abgenommene Schnitte zu zerlegen.

## Noch nicht Teil des Bürgerportal-Stands

Keine Detailseite, privaten Meldetabellen oder Meldungsendpunkte, KI-Aufrufe,
Moderationsoberfläche, automatische Veröffentlichung, Uploads oder öffentlichen
Kommentare. Die nächste Iteration startet erst nach ausdrücklicher Abnahme der
deployten Übersicht.
