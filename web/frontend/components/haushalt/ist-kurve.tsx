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

        {rueckgaenge.map((r) => (
          <g key={r.jahr}>
            <line x1={x(r.i)} y1={y(reihe[r.i].betrag / 1e6)} x2={x(r.i)} y2={Y0}
              strokeWidth={1} strokeDasharray="3 3" className="stroke-muted-foreground" />
            <circle cx={x(r.i)} cy={y(reihe[r.i].betrag / 1e6)} r={4} className="fill-card stroke-signal" strokeWidth={2} />
            <text x={x(r.i)} y={y(reihe[r.i].betrag / 1e6) - 9} textAnchor="middle" fontSize={fs.marke}
              className="fill-signal">{r.jahr}: {deMio(r.delta)}</text>
          </g>
        ))}

        <circle cx={x(0)} cy={y(erste.betrag / 1e6)} r={4} className="fill-card" strokeWidth={2}
          style={{ stroke: "var(--hh-ein-0)" }} />
        <text x={x(0)} y={y(erste.betrag / 1e6) + 17} fontSize={fs.wert} fontWeight={600}
          style={{ fill: "var(--hh-ein-0)" }}>{deMio(erste.betrag / 1e6)}</text>
        <circle cx={x(reihe.length - 1)} cy={y(letzte.betrag / 1e6)} r={5} style={{ fill: "var(--hh-ein-0)" }} />
        <text x={x(reihe.length - 1) - 6} y={y(letzte.betrag / 1e6) - 10} textAnchor="end" fontSize={fs.wert + 1}
          fontWeight={700} style={{ fill: "var(--hh-ein-0)" }}>{deMio(letzte.betrag / 1e6)}</text>

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
