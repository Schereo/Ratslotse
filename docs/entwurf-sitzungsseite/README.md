# Entwurf: Sitzungsseite „Kurs der Sitzung“

Material zum Plan [`docs/plan-sitzungsseite-kurs.md`](../plan-sitzungsseite-kurs.md).
Der Plan sagt, was gebaut wird und in welcher Reihenfolge. Dieser Ordner zeigt,
wie es aussehen soll.

**Das hier ist kein Code für das Repo.** Nichts aus `quellen/` wird
eingebunden, importiert oder ausgeliefert. Es ist die Vorlage, an der sich die
Umsetzung messen lässt.

## Inhalt

| Ordner | Was | Wozu |
|---|---|---|
| `bilder/` | 23 Bilder aller Ansichten, Desktop (1.360 px) und Handy (390 px) | zuerst ansehen; für den Vergleich mit dem Ergebnis |
| `quellen/` | die Artboards der Design-Canvas als `.dc.html`, dazu `canvas.json` | genaue Maße, Texte und die lauffähige Rechnung des Kurses |

## Bilder

| Datei | Zeigt |
|---|---|
| `vor-der-sitzung-desktop-1…3.png` | Sitzungsseite vor der Sitzung, von oben nach unten |
| `vor-der-sitzung-handy-1…2.png` | dasselbe bei 390 px; je Bild drei Abschnitte der Seite nebeneinander |
| `nach-der-sitzung-desktop-1…4.png` | Sitzungsseite nach der Sitzung, mit Protokoll |
| `nach-der-sitzung-handy-1…2.png` | dasselbe bei 390 px (vier und drei Abschnitte) |
| `mitlesen-desktop-1…2.png` | Mitlesen, aktiver Punkt Ö 11.1 |
| `mitlesen-handy.png` | Mitlesen bei 390 px, aktiver Punkt Ö 8 |
| `mitlesen-desktop-zustand-anfang.png` | erster Schritt (Formalien), ohne „Zurück“ |
| `mitlesen-desktop-zustand-mitschrieb.png` | Ö 9 mit eigenem Mitschrieb „Angenommen“ und Notiz; die Boje ist grün |
| `mitlesen-desktop-zustand-ende.png` | letzter Schritt (nichtöffentlich), ohne „Weiter“ |
| `mitlesen-handy-zustand-mitschrieb.png` | wie oben bei 390 px; der Kurs ist kompakt |
| `punkt-desktop-1…2.png` | Punkt-Seite „Soziales D-Ticket“, Reiter Argumente, Gespräch rechts |
| `punkt-handy-1…2.png` | dasselbe bei 390 px |
| `kurs-varianten.png` | der Kurs mit wenigen und vielen Punkten und in drei Handy-Breiten |

Die Bilder sind auf 192 Farben verkleinert, damit der Ordner klein bleibt.
Feine Verläufe und Schatten sind deshalb gröber als im Original.

## Quellen lesen

- Gewöhnliches HTML mit Inline-Styles. `{{ name }}` wird von der Klasse
  `Component` am Dateiende gefüllt (`renderVals()`), `<sc-if>` blendet ein,
  `<sc-for>` wiederholt, `<dc-import name="Kurs">` bindet `Kurs.dc.html` ein.
- Die Dateien laufen nur in der Canvas; `support.js` und die Bilder unter
  `/_blob/…` gibt es hier nicht. Im Browser öffnen bringt nichts.
- Farben sind Literale des Hellmodus. Welches Token dahintersteht, sagt
  Anhang B des Plans.
- `Mobil.dc.html` und `MitlesenMobil.dc.html` binden nur die Desktop-Datei bei
  390 px Breite ein. Es gibt keine eigene Handy-Fassung; alles bricht aus
  einer Quelle um.
- Kopfzeile, Fußzeile und der Block „Willst du früher davon erfahren?“
  gehören zur `PublicShell` des Bestands und werden nicht nachgebaut.

## Was im Entwurf gesetzt ist

Sitzungen, Punkte, Vorlagen, Ergebnisse und Beschluss-Nummern stammen aus dem
Ratsbestand. Von Hand gesetzt sind die Lotti-Sätze, „wichtig“ samt Grund, die
Piktogramme, die Etappen, die „Zusagen der Verwaltung“, die Abschnitte „Was
beantragt wird“, „Was die Verwaltung sagt“, „Was es kostet“, alle Argumente
und Fraktions-Paraphrasen, die Antworten im Gespräch und der Presse-Link. Der
Plan sagt in Abschnitt 4.7, wofür es schon eine Quelle gibt.

## Wenn alles gebaut ist

Der Ordner wandert mit dem Plan nach `docs/archiv/`.
