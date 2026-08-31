// Der Daten-Vertrag des Grafik-Baukastens (GB-00).
//
// Alle Komponenten essen dieselben Formen: `{year, value}` für Reihen,
// `{label, value}` für Listen. Lücken sind DATEN, kein Sonderfall:
// `{year: 2019, fehlt: "Arten ergeben die Summe nicht"}`. Jede Komponente
// MUSS sie beschriftet rendern (über `<LueckenFeld>`), keine darf
// interpolieren — die Union macht das zum Typsystem: Wer `value` einer Lücke
// lesen will, kommt am `fehlt`-Zweig nicht vorbei.

/** Ein vorhandener Punkt einer Zeitreihe.
 *
 *  `bruchDavor` trennt die Linie **vor** diesem Punkt: Der Wert ist da, aber
 *  er ist mit dem davor nicht vergleichbar, weil die Quelle inzwischen etwas
 *  anderes misst. Eine Lücke wäre dafür falsch (der Wert fehlt ja nicht),
 *  eine durchgezogene Linie auch — sie behauptete eine Entwicklung, wo eine
 *  Definition wechselte. Der erste Fall im Bestand: Bei der
 *  Personalintensität fielen 2022 die Versorgungsempfänger aus dem Zähler.
 *
 *  Der Text ist der Grund. Er gehört an die Daten und nicht in die Seite —
 *  dieselbe Regel wie bei `fehlt`. */
export type JahrWert = { year: number; value: number; bruchDavor?: string };

/** Eine Lücke: das Jahr gibt es, den Wert nicht — und der Grund reist mit.
 *  `datum` ist der Stichtag der Feststellung, wo er bekannt ist. */
export type JahrLuecke = { year: number; fehlt: string; datum?: string };

/** Eine Reihe besteht aus Punkten UND Lücken — in einer Liste, damit die
 *  x-Achse vollständig bleibt und keine Komponente Lücken „vergessen" kann. */
export type JahrPunkt = JahrWert | JahrLuecke;

/** Ein Eintrag einer Liste/Rangliste. */
export type LabelWert = { label: string; value: number };

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
