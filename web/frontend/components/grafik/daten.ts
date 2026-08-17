// Der Daten-Vertrag des Grafik-Baukastens (GB-00).
//
// Alle Komponenten essen dieselben Formen: `{jahr, wert}` für Reihen,
// `{label, wert}` für Listen. Lücken sind DATEN, kein Sonderfall:
// `{jahr: 2019, fehlt: "Arten ergeben die Summe nicht"}`. Jede Komponente
// MUSS sie beschriftet rendern (über `<LueckenFeld>`), keine darf
// interpolieren — die Union macht das zum Typsystem: Wer `wert` einer Lücke
// lesen will, kommt am `fehlt`-Zweig nicht vorbei.

/** Ein vorhandener Punkt einer Zeitreihe. */
export type JahrWert = { jahr: number; wert: number };

/** Eine Lücke: das Jahr gibt es, den Wert nicht — und der Grund reist mit.
 *  `datum` ist der Stichtag der Feststellung, wo er bekannt ist. */
export type JahrLuecke = { jahr: number; fehlt: string; datum?: string };

/** Eine Reihe besteht aus Punkten UND Lücken — in einer Liste, damit die
 *  x-Achse vollständig bleibt und keine Komponente Lücken „vergessen" kann. */
export type JahrPunkt = JahrWert | JahrLuecke;

/** Ein Eintrag einer Liste/Rangliste. */
export type LabelWert = { label: string; wert: number };

/** Type Guard für den Lücken-Zweig — das Gegenstück ist `vorhanden`. */
export function istLuecke(p: JahrPunkt): p is JahrLuecke {
  return "fehlt" in p;
}

/** Type Guard für den Werte-Zweig. Zusammen mit `istLuecke` der einzige
 *  vorgesehene Weg, eine Reihe auseinanderzunehmen — z. B. als
 *  `defined`-Prädikat für `d3-shape`, damit Linien an Lücken abreißen. */
export function vorhanden(p: JahrPunkt): p is JahrWert {
  return !("fehlt" in p);
}
