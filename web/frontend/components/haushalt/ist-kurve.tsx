"use client";

// Ist-Kurve einer Steuerart (Design H-10) — 28 Jahre in einem Bild.
//
// GEGENCHECK-BEFUND (16.08.2026): Der Entwurf markierte „Finanzkrise 2009"
// und „Corona 2020" als Einbrüche. In Oldenburg ist die Gewerbesteuer 2009
// aber GESTIEGEN (58,9 → 61,9 Mio.), und 2020 fiel sie nur um 3,8 Mio. Die
// wirklichen Einbrüche liegen 2000–2003. Deshalb werden die Marker hier aus
// den Daten berechnet und neutral beschriftet — eine Jahreszahl mit
// Rückgang, keine historische Deutung, die die Reihe nicht hergibt.

import { useEffect, useRef, useState } from "react";
import { deMio } from "@/lib/haushalt";

type Punkt = { jahr: number; betrag: number };

const H = 210, Y0 = 172, YTOP = 22;

// Beschriftungen im Diagramm bekommen einen Kontur-Halo in Kartenfarbe: Sonst
// schneiden Kurve, Fläche und die gestrichelten Fall-Linien mitten durch die
// Ziffern (die 2000er-Linie lief genau durch das „42,7").
const halo = { paintOrder: "stroke", strokeWidth: 3, strokeLinejoin: "round" } as const;

export function IstKurve({ reihe, einheit = "Mio. Euro" }: {
  reihe: Punkt[];
  einheit?: string;
}) {
  const [tabelle, setTabelle] = useState(false);
  // viewBox-Breite = Containerbreite, sonst staucht das SVG die Schrift mit
  // (siehe Zeitreihe): Eine SVG-Einheit soll ein echtes Pixel sein.
  const box = useRef<HTMLDivElement>(null);
  const [breite, setBreite] = useState(640);
  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const pruefe = () => setBreite(Math.max(el.clientWidth, 280));
    pruefe();
    const ro = new ResizeObserver(pruefe);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  const schmal = breite < 520;
  const fs = schmal
    ? { achse: 13, jahr: 13, marke: 12.5, wert: 14 }
    : { achse: 11, jahr: 11, marke: 11, wert: 13 };
  const W = breite, X0 = schmal ? 38 : 42, X1 = W - 20;
  if (reihe.length < 2) return null;

  const werte = reihe.map((p) => p.betrag / 1e6);
  const hi = Math.ceil(Math.max(...werte) / 50) * 50;
  const x = (i: number) => X0 + (i / (reihe.length - 1)) * (X1 - X0);
  const y = (v: number) => Y0 - (v / hi) * (Y0 - YTOP);

  const linie = reihe.map((p, i) => `${i ? "L" : "M"}${x(i)} ${y(p.betrag / 1e6)}`).join(" ");
  const flaeche = `${linie} L${x(reihe.length - 1)} ${Y0} L${X0} ${Y0} Z`;

  // Die zwei größten Rückgänge gegenüber dem Vorjahr — aus den Daten, nicht
  // aus dem Geschichtsbuch.
  const rueckgaenge = reihe
    .map((p, i) => (i === 0 ? null : { i, jahr: p.jahr, delta: (p.betrag - reihe[i - 1].betrag) / 1e6 }))
    .filter((d): d is { i: number; jahr: number; delta: number } => !!d && d.delta < 0)
    .sort((a, b) => a.delta - b.delta)
    .slice(0, 2);

  const gitter = [0.25, 0.5, 0.75, 1].map((f) => Math.round(hi * f));
  const erste = reihe[0], letzte = reihe[reihe.length - 1];
  const faktor = erste.betrag > 0 ? letzte.betrag / erste.betrag : 0;
  // Jahres-Beschriftung ausdünnen, damit nichts überlappt.
  const schritt = Math.ceil(reihe.length / (schmal ? 4 : 6));

  // --- Marker-Beschriftungen entzerren ------------------------------------
  // SVG-Text weicht nicht von selbst aus: Liegen die zwei größten Rückgänge
  // dicht beieinander und weit links (bei den Steuern 2000 und 2003, Werte 3
  // und 6 von 28), schoben sich „2000: -8,5" und „2003: -7,8" ineinander und
  // zugleich über die Achsenzahl links daneben (Befund 16.08.2026, mobil).
  // Deshalb hier: Kästen grob schätzen, in die Zeichenfläche klemmen und bei
  // Kollision zeilenweise ausweichen — nach oben, notfalls unter den Punkt.
  type Kasten = { x1: number; x2: number; y1: number; y2: number };
  // Grobe Breitenschätzung (gemessen: ~0,50 der Schriftgröße je Zeichen, hier
  // mit Reserve) — genau messen ginge nur mit zweitem Render-Durchgang.
  const textBreite = (t: string, size: number) => t.length * size * 0.55;
  const stoert = (a: Kasten, b: Kasten) =>
    a.x1 < b.x2 + 4 && b.x1 < a.x2 + 4 && a.y1 < b.y2 + 2 && b.y1 < a.y2 + 2;

  const ersterText = deMio(erste.betrag / 1e6), letzterText = deMio(letzte.betrag / 1e6);
  const ersterY = y(erste.betrag / 1e6) + 17, letzterY = y(letzte.betrag / 1e6) - 10;
  const letzteBreite = textBreite(letzterText, fs.wert + 1);
  // Die beiden Wert-Labels stehen fest — die Marker weichen ihnen aus.
  const belegt: Kasten[] = [
    { x1: x(0), x2: x(0) + textBreite(ersterText, fs.wert), y1: ersterY - fs.wert, y2: ersterY + 3 },
    { x1: x(reihe.length - 1) - 6 - letzteBreite, x2: x(reihe.length - 1) - 6,
      y1: letzterY - fs.wert - 1, y2: letzterY + 3 },
  ];
  const marken = rueckgaenge
    .map((r) => {
      const text = `${r.jahr}: ${deMio(r.delta)}`;
      const w = textBreite(text, fs.marke);
      return {
        ...r, text, w,
        // In die Zeichenfläche klemmen: links stehen die Achsenzahlen.
        mitte: Math.min(Math.max(x(r.i), X0 + w / 2), X1 - w / 2),
        py: y(reihe[r.i].betrag / 1e6),
      };
    })
    .sort((a, b) => a.mitte - b.mitte)
    .map((m) => {
      const kasten = (ty: number): Kasten =>
        ({ x1: m.mitte - m.w / 2, x2: m.mitte + m.w / 2, y1: ty - fs.marke, y2: ty + 3 });
      // Erst über dem Punkt, zeilenweise höher; wenn oben nichts frei ist
      // (Einbruch im letzten Jahr, direkt am großen Endwert), darunter.
      const zeile = fs.marke + 4;
      const kandidaten: number[] = [];
      for (let n = 0; n < 6 && m.py - 9 - n * zeile - fs.marke > YTOP; n++) kandidaten.push(m.py - 9 - n * zeile);
      kandidaten.push(Math.min(m.py + 9 + fs.marke, Y0 - 4));
      const ty = kandidaten.find((k) => !belegt.some((b) => stoert(kasten(k), b))) ?? kandidaten.at(-1)!;
      belegt.push(kasten(ty));
      return { ...m, ty };
    });

  return (
    <div ref={box}>
      <div className="mb-1.5 flex flex-col gap-0.5 sm:flex-row sm:items-baseline sm:justify-between sm:gap-3">
        <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
          Tatsächlich eingenommen
        </p>
        <span className="font-mono text-[10px] uppercase text-muted-foreground">
          {erste.jahr}–{letzte.jahr} · {reihe.length} Werte · {einheit}
        </span>
      </div>
      <p className="mb-3 max-w-[72ch] text-sm leading-relaxed text-foreground/90">
        In {letzte.jahr - erste.jahr} Jahren ist der Betrag von {deMio(erste.betrag / 1e6)} auf{" "}
        <strong>{deMio(letzte.betrag / 1e6)}&#8239;Mio.&nbsp;€</strong> gestiegen
        {faktor >= 1.5 && <> — das {faktor.toLocaleString("de-DE", { maximumFractionDigits: 1 })}-Fache</>}.
        {rueckgaenge.length > 0 && (
          <> Dazwischen ging es auch zurück: am stärksten {rueckgaenge[0].jahr} um{" "}
          {deMio(-rueckgaenge[0].delta)}&#8239;Mio.</>
        )}
      </p>

      <svg viewBox={`0 0 ${W} ${H}`} className="block w-full" role="img"
        aria-label={`Verlauf ${erste.jahr} bis ${letzte.jahr}: ${reihe.map((p) => `${p.jahr} ${deMio(p.betrag / 1e6)}`).join(", ")} Millionen Euro`}>
        {gitter.map((v) => (
          <g key={v}>
            <line x1={X0} y1={y(v)} x2={X1} y2={y(v)} className="stroke-border/60" />
            <text x={X0 - 6} y={y(v) + 4} textAnchor="end" fontSize={fs.achse} className="fill-muted-foreground font-mono">{v}</text>
          </g>
        ))}
        <line x1={X0} y1={Y0} x2={X1} y2={Y0} className="stroke-border" />

        <path d={flaeche} style={{ fill: "var(--hh-ein-0)" }} opacity={0.08} />
        <path d={linie} fill="none" strokeWidth={2.2} strokeLinejoin="round" strokeLinecap="round"
          style={{ stroke: "var(--hh-ein-0)" }} />

        {/* Erst alle Linien und Punkte, dann alle Beschriftungen: Sonst zieht der
            Führungsstrich der oberen Marke durch den Text der unteren. */}
        {marken.map((m) => (
          <g key={m.jahr}>
            <line x1={x(m.i)} y1={m.py} x2={x(m.i)} y2={Y0}
              strokeWidth={1} strokeDasharray="3 3" className="stroke-muted-foreground" />
            {/* Steht die Beschriftung versetzt, führt ein feiner Strich zurück zum Punkt. */}
            {(Math.abs(m.mitte - x(m.i)) > 2 || m.ty < m.py - 12 || m.ty > m.py) && (
              <line x1={x(m.i)} y1={m.py + (m.ty > m.py ? 6 : -6)}
                x2={Math.min(Math.max(x(m.i), m.mitte - m.w / 2), m.mitte + m.w / 2)}
                y2={m.ty > m.py ? m.ty - fs.marke - 2 : m.ty + 4}
                strokeWidth={1} className="stroke-signal" opacity={0.45} />
            )}
            <circle cx={x(m.i)} cy={m.py} r={4} className="fill-card stroke-signal" strokeWidth={2} />
          </g>
        ))}
        {marken.map((m) => (
          <text key={m.jahr} x={m.mitte} y={m.ty} textAnchor="middle" fontSize={fs.marke}
            className="fill-signal stroke-card" {...halo}>{m.text}</text>
        ))}

        <circle cx={x(0)} cy={y(erste.betrag / 1e6)} r={4} className="fill-card" strokeWidth={2}
          style={{ stroke: "var(--hh-ein-0)" }} />
        <text x={x(0)} y={ersterY} fontSize={fs.wert} fontWeight={600} className="stroke-card" {...halo}
          style={{ fill: "var(--hh-ein-0)" }}>{ersterText}</text>
        <circle cx={x(reihe.length - 1)} cy={y(letzte.betrag / 1e6)} r={5} style={{ fill: "var(--hh-ein-0)" }} />
        <text x={x(reihe.length - 1) - 6} y={letzterY} textAnchor="end" fontSize={fs.wert + 1}
          fontWeight={700} className="stroke-card" {...halo}
          style={{ fill: "var(--hh-ein-0)" }}>{letzterText}</text>

        {reihe.map((p, i) => (
          (i % schritt === 0 || i === reihe.length - 1) && (
            <text key={p.jahr} x={x(i)} y={193} textAnchor="middle" fontSize={fs.jahr}
              className={i === reihe.length - 1 ? "fill-foreground font-mono" : "fill-muted-foreground font-mono"}>
              {p.jahr}
            </text>
          )
        ))}
      </svg>

      <button type="button" onClick={() => setTabelle((t) => !t)}
        className="mt-1.5 text-[12px] font-semibold text-primary">
        {tabelle ? "Zahlen ausblenden" : `Zahlen anzeigen (${reihe.length} Werte)`}
      </button>
      {tabelle && (
        <div className="mt-2 grid grid-cols-[repeat(auto-fill,minmax(96px,1fr))] gap-x-3 gap-y-1 text-[11.5px] tabular-nums">
          {reihe.map((p) => (
            <span key={p.jahr} className="flex justify-between border-t border-border/60 py-1">
              <span className="font-mono text-muted-foreground">{p.jahr}</span>
              <span>{deMio(p.betrag / 1e6)}</span>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
