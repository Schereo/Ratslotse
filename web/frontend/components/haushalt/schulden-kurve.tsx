"use client";

// Schuldenzeitreihe — dreißig Jahre in einem Bild.
//
// KEINE BEWERTUNGSFARBEN, wie im ganzen Bereich (components/grafik/hantel.tsx).
// Bei Schulden ist die Versuchung am größten: Rot für „viel", Grün für den
// Rückgang. Beides wäre gelogen. Ein Schuldenrückgang kann bedeuten, dass die
// Stadt eine Aufgabe abgegeben hat (2001: die Stadtentwässerung ging an einen
// Verband, mit ihr 139,5 Mio. € Darlehen), und ein Anstieg, dass sie Schulen
// saniert. Die Kurve trägt deshalb einen der neutralen Rampentöne des
// Bereichs und keine Ampel.
//
// MARKER AUS DEN DATEN, nicht aus dem Gedächtnis — dieselbe Lehre wie in
// `ist-kurve.tsx`: Der größte Rückgang und der größte Anstieg werden gerechnet
// und mit Jahreszahl und Betrag beschriftet, ohne historische Deutung. Was
// hinter einem Sprung steckt, steht als Fußnote der Quelle im Text der Seite,
// wo es belegt ist — nicht als Behauptung im Bild.
//
// ZWEI ANSICHTEN, weil sie über dreißig Jahre in verschiedene Richtungen
// zeigen: Die Einwohnerzahl ist in derselben Zeit stark gewachsen. Nur die
// absolute Reihe zu zeigen läse das Wachstum der Stadt als Schuldenaufbau;
// nur die Pro-Kopf-Reihe zu zeigen verschwiege den absoluten Anstieg.
//
// DIE ZINSLINIE (H4-13) ist die dünne, gestrichelte zweite Reihe IN der
// Kurve: was der Bestand im Jahr kostet, auf DERSELBEN Skala — dass sie fast
// auf der Nulllinie klebt, ist die Aussage, kein Darstellungsfehler. Sie
// trägt eine eigene Stufe der Rampe und KEIN Signal-Orange: Zins ist keine
// Abweichung. Nur in der absoluten Ansicht — einen Pro-Kopf-Zins weist die
// Quelle nicht aus, und wir dividieren nicht selbst.
//
// ANNOTATIONEN (H4-13) stehen im Bild, nicht in der Fußnote: „2010: 108,9
// Mio. umgebucht" gehört an den Knick, den es erklärt. Der Wortlaut kommt
// von der Seite (dort steht er mit Beleg); schmal bleibt im Bild nur die
// „2010 ⓘ"-Marke, der Satz steht dann sichtbar unter dem Diagramm.
//
// TODO(Grafik-Baukasten): Auf die gemeinsame <Zeitreihe> (GB-01,
// components/grafik/zeitreihe.tsx) umziehen, sobald sie gemergt ist — sie
// bringt `zweitreihe` und `annotationen` als Vertrag mit. Stand dieses
// Branches existiert sie noch nicht; die Kurve bleibt deshalb seiten-lokal.

import { useId, useState } from "react";
import { useBreite } from "@/lib/use-breite";
import { deMio } from "@/lib/haushalt";
import { Ansicht, Punkt, deEuro } from "@/lib/haushalt-schulden";
import {
  AbleseBeschreibung, AbleseFlaeche, AbleseStelle, Ableseleiste, useAblesen,
} from "@/components/grafik/ablesen";

const H = 210, Y0 = 172, YTOP = 22;

// Beschriftungen im Bild bekommen einen Kontur-Halo in Kartenfarbe, sonst
// schneiden Kurve und Fläche mitten durch die Ziffern.
const halo = { paintOrder: "stroke", strokeWidth: 3, strokeLinejoin: "round" } as const;

//: Die Farbe der Reihe. `--hh-aus-0` ist der neutrale Schieferton des
//: Bereichs — gewählt, weil Schulden weder Einnahme noch Ausgabe sind und
//: die Rampe in beiden Themes gegen die Karte geprüft ist.
const TON = "var(--hh-aus-0)";
//: Die Zinslinie in einer klar unterscheidbaren Rampenstufe: `--hh-ein-1`
//: ist in beiden Themes ein deutliches Blau — `--hh-aus-1` läge zu nah an
//: der Hauptkurve (hell: 26 % gegen 36 % Helligkeit im selben Grauton).
//: KEIN Signal-Orange: Zins ist keine Abweichung (H4-13).
const ZINS_TON = "var(--hh-ein-1)";

function zahl(wert: number, ansicht: Ansicht): string {
  return ansicht === "insgesamt" ? deMio(wert) : deEuro(wert);
}

export type KurvenAnnotation = {
  jahr: number;
  /** Steht im Bild: „108,9 Mio. umgebucht". Schmal nur „{jahr} ⓘ". */
  kurz: string;
  /** Der ganze Satz — schmal unter dem Diagramm, immer in der Vorlesehilfe. */
  text: string;
};

export function SchuldenKurve({ punkte, ansicht, zweitreihe, zweitreiheLabel, annotationen = [] }: {
  punkte: Punkt[];
  ansicht: Ansicht;
  /** Die dünne zweite Reihe IN der Kurve (H4-13) — gleiche Einheit wie die
   *  Hauptreihe, sonst wäre die gemeinsame Skala eine Lüge. */
  zweitreihe?: Punkt[];
  /** Beschriftung der zweiten Reihe, z. B. „Zinslast p. a.". */
  zweitreiheLabel?: string;
  annotationen?: KurvenAnnotation[];
}) {
  const [tabelle, setTabelle] = useState(false);
  // viewBox-Breite = Containerbreite, sonst staucht das SVG die Schrift mit
  // (Messfalle und Epsilon: `lib/use-breite.ts`).
  const { box, breite } = useBreite();
  const ablesen = useAblesen(punkte.length, Math.max(punkte.length - 1, 0));
  const beschreibungId = useId();
  const schmal = breite < 520;
  const fs = schmal
    ? { achse: 13, jahr: 13, marke: 12.5, wert: 14 }
    : { achse: 11, jahr: 11, marke: 11, wert: 13 };
  if (punkte.length < 2) return null;

  const einheit = ansicht === "insgesamt" ? "Mio. €" : "€ je Einwohner*in";
  // Die zweite Reihe rechnet in der Skala mit — sie liegt zwar immer weit
  // darunter, aber eine Skala, die eine gezeichnete Reihe abschneiden KÖNNTE,
  // ist keine.
  const werte = [...punkte.map((p) => p.wert), ...(zweitreihe ?? []).map((p) => p.wert)];
  // Nullbasis: Eine Bestandsgröße gehört auf eine Skala, die bei null
  // beginnt — sonst macht ein abgeschnittener Sockel aus 5 % Bewegung ein
  // Gebirge. (Nur reine Abstandsdiagramme dürfen abschneiden, s. zeitreihe.tsx.)
  const stufe = ansicht === "insgesamt" ? 50 : 500;
  const hi = Math.max(Math.ceil(Math.max(...werte) / stufe) * stufe, stufe);
  const gitter = [0.25, 0.5, 0.75, 1].map((f) => Math.round(hi * f));
  const achsenText = gitter.map((v) => v.toLocaleString("de-DE"));

  // Der linke Rand richtet sich nach der BREITESTEN Achsenzahl, statt fest zu
  // sein: In der Pro-Kopf-Ansicht steht dort „2.500" (fünf Zeichen), in der
  // Mio.-Ansicht „350" (drei) — ein fester Wert ragte im schmalen Container
  // links aus der Zeichenfläche heraus (gemessen 16.08.2026: −1,1 px bei
  // 280 px Breite). Mono-Ziffern laufen rund 0,62 em breit; 9 px Zugabe sind
  // der Abstand zur Achse plus Reserve.
  const W = breite;
  const X0 = Math.ceil(Math.max(...achsenText.map((t) => t.length)) * fs.achse * 0.62) + 9;
  const X1 = W - 20;

  // Die Jahre spannen die X-Achse, nicht ihr Index: Fehlt ein Jahrgang, soll
  // die Lücke im Bild auch eine Lücke sein.
  const von = punkte[0].jahr, bis = punkte[punkte.length - 1].jahr;
  const x = (jahr: number) => X0 + ((jahr - von) / Math.max(bis - von, 1)) * (X1 - X0);
  const y = (v: number) => Y0 - (v / hi) * (Y0 - YTOP);

  // Segmente: an jeder Lücke neu ansetzen (Konvention des Bereichs — nie
  // durchziehen, was wir nicht wissen).
  const segmente: Punkt[][] = [];
  let akt: Punkt[] = [];
  for (let jahr = von; jahr <= bis; jahr++) {
    const p = punkte.find((q) => q.jahr === jahr);
    if (p) akt.push(p);
    else if (akt.length) { segmente.push(akt); akt = []; }
  }
  if (akt.length) segmente.push(akt);

  const pfad = (seg: Punkt[]) =>
    seg.map((p, i) => `${i ? "L" : "M"}${x(p.jahr)} ${y(p.wert)}`).join(" ");
  const flaeche = (seg: Punkt[]) =>
    `${pfad(seg)} L${x(seg[seg.length - 1].jahr)} ${Y0} L${x(seg[0].jahr)} ${Y0} Z`;

  // Die zweite Reihe (Zins): gleiche Lücken-Konvention, eigene Segmente —
  // und nur innerhalb der x-Achse der Hauptreihe.
  const zweit = (zweitreihe ?? [])
    .filter((p) => p.jahr >= von && p.jahr <= bis)
    .sort((a, b) => a.jahr - b.jahr);
  const zweitSegmente: Punkt[][] = [];
  {
    let akt2: Punkt[] = [];
    for (let jahr = von; jahr <= bis; jahr++) {
      const p = zweit.find((q) => q.jahr === jahr);
      if (p) akt2.push(p);
      else if (akt2.length) { zweitSegmente.push(akt2); akt2 = []; }
    }
    if (akt2.length) zweitSegmente.push(akt2);
  }
  const zinsBei = (jahr: number) => zweit.find((q) => q.jahr === jahr) ?? null;

  const erster = punkte[0], letzter = punkte[punkte.length - 1];

  // --- Beschriftungen entzerren -------------------------------------------
  // SVG-Text weicht nicht von selbst aus. Der Endwert steht fest an der
  // letzten Stelle — und genau dort liegt regelmäßig auch einer der beiden
  // Sprung-Marker (in der Pro-Kopf-Ansicht ist der größte Anstieg das letzte
  // Jahr: „2025: +235" lag exakt auf der „1.908"). Deshalb dieselbe Bauart
  // wie in `ist-kurve.tsx`: Kästen grob schätzen, Belegtes sammeln, die
  // beweglichen Marken zeilenweise ausweichen lassen.
  type Kasten = { x1: number; x2: number; y1: number; y2: number };
  // Grobe Breitenschätzung (~0,55 der Schriftgröße je Zeichen, mit Reserve) —
  // genau messen ginge nur mit einem zweiten Render-Durchgang.
  const textBreite = (t: string, size: number) => t.length * size * 0.55;
  const stoert = (a: Kasten, b: Kasten) =>
    a.x1 < b.x2 + 4 && b.x1 < a.x2 + 4 && a.y1 < b.y2 + 2 && b.y1 < a.y2 + 2;

  const endText = zahl(letzter.wert, ansicht);
  const endY = y(letzter.wert) - 10;
  const endBreite = textBreite(endText, fs.wert + 1);
  const belegt: Kasten[] = [{
    x1: x(letzter.jahr) - 6 - endBreite, x2: x(letzter.jahr) - 6,
    y1: endY - fs.wert - 1, y2: endY + 3,
  }];

  // Beschriftung der Zinslinie — über ihrem letzten Punkt, in ihrer Farbe.
  const zinsLetzter = zweit.length ? zweit[zweit.length - 1] : null;
  const zinsBeschriftung = zinsLetzter
    ? (() => {
        const text = schmal
          ? "Zins"
          : `${zweitreiheLabel ?? "Zweitreihe"} (${zweit[0].jahr}–${zinsLetzter.jahr})`;
        const w = textBreite(text, fs.marke);
        const tx = Math.min(Math.max(x(zinsLetzter.jahr), X0 + w), X1);
        const ty = y(zinsLetzter.wert) - 8;
        belegt.push({ x1: tx - w, x2: tx, y1: ty - fs.marke, y2: ty + 3 });
        return { text, tx, ty };
      })()
    : null;

  // Größter Rückgang und größter Anstieg — gerechnet, neutral beschriftet.
  const spruenge = punkte
    .map((p, i) => (i === 0 ? null : { jahr: p.jahr, delta: p.wert - punkte[i - 1].wert }))
    .filter((d): d is { jahr: number; delta: number } => d != null);
  const runter = [...spruenge].sort((a, b) => a.delta - b.delta)[0];
  const rauf = [...spruenge].sort((a, b) => b.delta - a.delta)[0];
  const marken = [runter, rauf]
    .filter((m): m is { jahr: number; delta: number } => !!m)
    .map((m) => {
      const text = `${m.jahr}: ${m.delta > 0 ? "+" : "−"}${zahl(Math.abs(m.delta), ansicht)}`;
      const w = textBreite(text, fs.marke);
      return {
        ...m, text, w,
        // In die Zeichenfläche klemmen: links stehen die Achsenzahlen.
        mitte: Math.min(Math.max(x(m.jahr), X0 + w / 2), X1 - w / 2),
        py: y(punkte.find((p) => p.jahr === m.jahr)!.wert),
      };
    })
    .sort((a, b) => a.mitte - b.mitte)
    .map((m) => {
      const kasten = (ty: number): Kasten =>
        ({ x1: m.mitte - m.w / 2, x2: m.mitte + m.w / 2, y1: ty - fs.marke, y2: ty + 3 });
      // Erst über dem Punkt, zeilenweise höher; wenn oben nichts frei ist,
      // darunter.
      const zeile = fs.marke + 4;
      const kandidaten: number[] = [];
      for (let n = 0; n < 6 && m.py - 10 - n * zeile - fs.marke > YTOP; n++) {
        kandidaten.push(m.py - 10 - n * zeile);
      }
      kandidaten.push(Math.min(m.py + 9 + fs.marke, Y0 - 4));
      const ty = kandidaten.find((k) => !belegt.some((b) => stoert(kasten(k), b)))
        ?? kandidaten[kandidaten.length - 1];
      belegt.push(kasten(ty));
      return { ...m, ty };
    });

  // Annotationen (H4-13): neutral beschriftet, gleiche Ausweich-Mechanik wie
  // die Sprung-Marken — sie kommen zuletzt und weichen allem aus. Schmal
  // steht im Bild nur „{jahr} ⓘ", der Satz folgt unter dem Diagramm.
  const annoMarken = annotationen
    .filter((a) => punkte.some((p) => p.jahr === a.jahr))
    .map((a) => {
      const text = schmal ? `${a.jahr} ⓘ` : `${a.jahr}: ${a.kurz}`;
      const w = textBreite(text, fs.marke);
      const mitte = Math.min(Math.max(x(a.jahr), X0 + w / 2), X1 - w / 2);
      const py = y(punkte.find((p) => p.jahr === a.jahr)!.wert);
      const kasten = (ty: number): Kasten =>
        ({ x1: mitte - w / 2, x2: mitte + w / 2, y1: ty - fs.marke, y2: ty + 3 });
      const zeile = fs.marke + 4;
      const kandidaten: number[] = [];
      for (let n = 0; n < 6 && py - 10 - n * zeile - fs.marke > YTOP; n++) {
        kandidaten.push(py - 10 - n * zeile);
      }
      kandidaten.push(Math.min(py + 9 + fs.marke, Y0 - 4));
      const ty = kandidaten.find((k) => !belegt.some((b) => stoert(kasten(k), b)))
        ?? kandidaten[kandidaten.length - 1];
      belegt.push(kasten(ty));
      return { ...a, text, w, mitte, py, ty };
    });

  // Jahres-Beschriftung ausdünnen, damit nichts überlappt.
  const schritt = Math.max(Math.ceil((bis - von) / (schmal ? 4 : 6)), 1);
  const jahresmarken: number[] = [];
  for (let j = von; j <= bis; j += schritt) jahresmarken.push(j);
  if (jahresmarken[jahresmarken.length - 1] !== bis) {
    // Das letzte Jahr steht immer — notfalls fliegt die vorletzte Marke, wenn
    // sie ihm zu nah käme.
    if (bis - jahresmarken[jahresmarken.length - 1] < schritt * 0.6) jahresmarken.pop();
    jahresmarken.push(bis);
  }

  const ableseStellen: AbleseStelle[] = punkte.map((p, i) => {
    const vor = i > 0 ? p.wert - punkte[i - 1].wert : null;
    const zins = zinsBei(p.jahr);
    const anno = annotationen.find((a) => a.jahr === p.jahr) ?? null;
    return {
      titel: String(p.jahr),
      werte: [
        { label: einheit, wert: zahl(p.wert, ansicht), farbe: TON },
        ...(vor == null ? [] : [{
          label: "ggü. Vorjahr",
          wert: `${vor > 0 ? "+" : vor < 0 ? "−" : ""}${zahl(Math.abs(vor), ansicht)}`,
          // `signal` markiert die Bewegung, nicht ihre Güte — bei Schulden
          // wäre „Anstieg = schlecht" genau die Wertung, die hier nicht
          // hingehört. Deshalb bekommt jede Bewegung dieselbe Marke.
          signal: false,
        }]),
        // Die Wertzeile zeigt Summe und Zins gemeinsam (H4-13).
        ...(zins == null ? [] : [{
          label: "Zins", wert: zahl(zins.wert, ansicht), farbe: ZINS_TON,
        }]),
      ],
      vorlesen: `${p.jahr}: ${zahl(p.wert, ansicht)} ${
        ansicht === "insgesamt" ? "Millionen Euro" : "Euro je Einwohnerin"}`
        + (vor == null ? "."
          : `, ${zahl(Math.abs(vor), ansicht)} ${vor < 0 ? "weniger" : "mehr"} als im Vorjahr.`)
        + (zins == null ? "" : ` Zinslast: ${zahl(zins.wert, ansicht)} Millionen Euro.`)
        + (anno == null ? "" : ` ${anno.text}`),
    };
  });

  return (
    <div ref={box}>
      <div className="mb-2 flex flex-col gap-0.5 sm:flex-row sm:items-baseline sm:justify-between sm:gap-3">
        <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
          {ansicht === "insgesamt" ? "Schulden insgesamt" : "Schulden je Einwohner*in"}
        </p>
        <span className="font-mono text-[10px] uppercase text-muted-foreground">
          {von}–{bis} · {punkte.length} Werte · {einheit}
        </span>
      </div>

      <AbleseBeschreibung id={beschreibungId}>
        {`Verlauf ${von} bis ${bis}: ${punkte.map((p) => `${p.jahr} ${zahl(p.wert, ansicht)}`).join(", ")} ${
          ansicht === "insgesamt" ? "Millionen Euro" : "Euro je Einwohnerin"}`}
        {zweit.length > 0 && ` Dünne zweite Reihe: ${zweitreiheLabel ?? "Zweitreihe"}, ${
          zweit[0].jahr} bis ${zweit[zweit.length - 1].jahr}.`}
        {annotationen.map((a) => ` ${a.text}`).join("")}
      </AbleseBeschreibung>
      {/* `role="group"` statt `role="img"`: Ein `img` fasst seinen Inhalt zu
          einem Objekt zusammen — die Jahres-Ziele darin wären für die
          Vorlesehilfe unsichtbar. */}
      <svg viewBox={`0 0 ${W} ${H}`} className="block w-full" role="group"
        aria-describedby={beschreibungId}
        aria-label={`Schuldenstand ${von} bis ${bis}`}>
        {gitter.map((v, i) => (
          <g key={v}>
            <line x1={X0} y1={y(v)} x2={X1} y2={y(v)} className="stroke-border/60" />
            <text x={X0 - 6} y={y(v) + 4} textAnchor="end" fontSize={fs.achse}
              className="fill-muted-foreground font-mono">
              {achsenText[i]}
            </text>
          </g>
        ))}
        <line x1={X0} y1={Y0} x2={X1} y2={Y0} className="stroke-border" />

        {segmente.map((seg, i) => (
          <g key={i}>
            {seg.length > 1 && <path d={flaeche(seg)} style={{ fill: TON }} opacity={0.08} />}
            <path d={pfad(seg)} fill="none" strokeWidth={2.2} strokeLinejoin="round"
              strokeLinecap="round" style={{ stroke: TON }} />
          </g>
        ))}

        {/* Die Zinslinie: dünn, gestrichelt, eigene Rampenstufe — IN der
            Kurve, auf derselben Skala (H4-13). */}
        {zweitSegmente.map((seg, i) => (
          <path key={`zins-${i}`} d={pfad(seg)} fill="none" strokeWidth={1.4}
            strokeDasharray="4 3" strokeLinejoin="round" strokeLinecap="round"
            style={{ stroke: ZINS_TON }} />
        ))}
        {zinsLetzter && zinsBeschriftung && (
          <g>
            <circle cx={x(zinsLetzter.jahr)} cy={y(zinsLetzter.wert)} r={3}
              style={{ fill: ZINS_TON }} />
            <text x={zinsBeschriftung.tx} y={zinsBeschriftung.ty} textAnchor="end"
              fontSize={fs.marke} className="stroke-card" {...halo}
              style={{ fill: ZINS_TON }}>
              {zinsBeschriftung.text}
            </text>
          </g>
        )}

        {/* Erst alle Linien und Punkte, dann alle Beschriftungen: Sonst zieht
            der Führungsstrich der einen Marke durch den Text der anderen. */}
        {marken.map((m) => (
          <g key={m.jahr}>
            {/* Steht die Beschriftung versetzt, führt ein feiner Strich
                zurück zum Punkt. */}
            {(Math.abs(m.mitte - x(m.jahr)) > 2 || m.ty < m.py - 13 || m.ty > m.py) && (
              <line x1={x(m.jahr)} y1={m.py + (m.ty > m.py ? 6 : -6)}
                x2={Math.min(Math.max(x(m.jahr), m.mitte - m.w / 2), m.mitte + m.w / 2)}
                y2={m.ty > m.py ? m.ty - fs.marke - 2 : m.ty + 4}
                strokeWidth={1} className="stroke-signal" opacity={0.45} />
            )}
            <circle cx={x(m.jahr)} cy={m.py} r={4}
              className="fill-card stroke-signal" strokeWidth={2} />
          </g>
        ))}
        {marken.map((m) => (
          <text key={m.jahr} x={m.mitte} y={m.ty} textAnchor="middle" fontSize={fs.marke}
            className="fill-signal stroke-card" {...halo}>{m.text}</text>
        ))}

        {/* Annotationen: neutral (kein Orange — sie erklären, sie warnen
            nicht), gleiche Führungsstrich-Mechanik wie die Marken. */}
        {annoMarken.map((a) => (
          <g key={`anno-${a.jahr}`}>
            {(Math.abs(a.mitte - x(a.jahr)) > 2 || a.ty < a.py - 13 || a.ty > a.py) && (
              <line x1={x(a.jahr)} y1={a.py + (a.ty > a.py ? 6 : -6)}
                x2={Math.min(Math.max(x(a.jahr), a.mitte - a.w / 2), a.mitte + a.w / 2)}
                y2={a.ty > a.py ? a.ty - fs.marke - 2 : a.ty + 4}
                strokeWidth={1} className="stroke-foreground/45" />
            )}
            <circle cx={x(a.jahr)} cy={a.py} r={4}
              className="fill-card stroke-foreground/60" strokeWidth={1.6} />
            <text x={a.mitte} y={a.ty} textAnchor="middle" fontSize={fs.marke}
              className="fill-foreground/75 stroke-card" {...halo}>{a.text}</text>
          </g>
        ))}

        <circle cx={x(erster.jahr)} cy={y(erster.wert)} r={4} className="fill-card"
          strokeWidth={2} style={{ stroke: TON }} />
        <circle cx={x(letzter.jahr)} cy={y(letzter.wert)} r={5} style={{ fill: TON }} />
        <text x={x(letzter.jahr) - 6} y={endY} textAnchor="end"
          fontSize={fs.wert + 1} fontWeight={700} className="stroke-card" {...halo}
          style={{ fill: TON }}>{endText}</text>

        {jahresmarken.map((j) => (
          <text key={j} x={x(j)} y={193} textAnchor="middle" fontSize={fs.jahr}
            className={j === bis ? "fill-foreground font-mono" : "fill-muted-foreground font-mono"}>
            {j}
          </text>
        ))}

        {/* Zuletzt: die Ablese-Fläche liegt über allem, sonst fangen Kurve und
            Punkte den Zeiger ab. */}
        <AbleseFlaeche
          stellen={ableseStellen} steuerung={ablesen} gruppe="Jahre der Reihe"
          x={(i) => x(punkte[i].jahr)} xVon={X0} xBis={X1}
          yVon={YTOP} hoehe={Y0 - YTOP} fangHoehe={197 - YTOP}
          marken={(i) => {
            const z = zinsBei(punkte[i].jahr);
            return [
              { y: y(punkte[i].wert), farbe: TON },
              ...(z ? [{ y: y(z.wert), farbe: ZINS_TON }] : []),
            ];
          }}
        />
      </svg>

      {/* Schmal trägt das Bild nur „{jahr} ⓘ" — der Satz dazu steht hier,
          sichtbar und nicht hinter einem Auslöser (H4-A: Hinweise dieser
          Sorte werden nie eingeklappt). */}
      {schmal && annoMarken.length > 0 && (
        <div className="mt-2 flex flex-col gap-1">
          {annoMarken.map((a) => (
            <p key={a.jahr} className="text-[11.5px] leading-relaxed text-muted-foreground">
              <span className="font-mono font-semibold text-foreground/75">{a.jahr} ⓘ</span>{" "}
              {a.text}
            </p>
          ))}
        </div>
      )}

      <Ableseleiste className="mt-2" stelle={ableseStellen[ablesen.aktiv]} steuerung={ablesen}
        hinweis="Jahr überfahren, antippen oder mit den Pfeiltasten wechseln." />

      <button type="button" onClick={() => setTabelle((t) => !t)}
        aria-expanded={tabelle} className="mt-2 text-[12px] font-semibold text-primary">
        {tabelle ? "Tabelle ausblenden" : `Alle ${punkte.length} Werte als Tabelle`}
      </button>
      {tabelle && (
        <div className="mt-2 grid grid-cols-[repeat(auto-fill,minmax(104px,1fr))] gap-x-3 gap-y-1 text-[11.5px] tabular-nums">
          {punkte.map((p) => (
            <span key={p.jahr} className="flex justify-between border-t border-border/60 py-1">
              <span className="font-mono text-muted-foreground">{p.jahr}</span>
              <span>{zahl(p.wert, ansicht)}</span>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
