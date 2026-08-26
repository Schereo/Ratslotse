"use client";

// Die 9×9-Ähnlichkeitsmatrix mit Paar-Detail (Design 3c).
//
// Breit: Matrix im eigenen Quer-Scroll-Container — der Body scrollt nie
// seitwärts (Bauplan §8). Zelle antippen → Detail direkt darunter.
// Schmal: sortierbare Paar-Liste („Nach Wert / Nach Liste").
//
// Das Paar-Detail zeigt KEINE 12 Themen-Ampeln: 46 % dieser Zellen hätten
// höchstens einen gemeinsamen Vergleichspunkt (Prüfbericht §4.3). Stattdessen
// die Thesen selbst — Übereinstimmung, Dissens mit Belegen, und die dritte
// Gruppe „beide unbestimmt", die den Prozentwert mit hochtreibt (§7.6).

import { useMemo, useState } from "react";
import { X } from "lucide-react";
import type { NaeheDaten } from "@/lib/kommunalwahl-types";
import { BswPill, FarbPunkt, Glyph, skalaStil } from "./ui";

function paarVon(d: NaeheDaten, a: string, b: string) {
  return d.paare[`${a}|${b}`] ?? d.paare[`${b}|${a}`] ?? null;
}

function PaarDetail({ d, kombi, onClose }: { d: NaeheDaten; kombi: [string, string]; onClose: () => void }) {
  const [aSlug, bSlug] = kombi;
  const a = d.listen.find((l) => l.slug === aSlug)!;
  const b = d.listen.find((l) => l.slug === bSlug)!;
  const p = paarVon(d, aSlug, bSlug);
  if (!p) return null;

  return (
    <div className="mt-5 overflow-hidden rounded-[18px] border border-border bg-card shadow-lifted">
      <div className="flex flex-wrap items-center gap-3 border-b border-border px-5 py-4 sm:px-6">
        <span className="inline-flex items-center gap-2">
          <FarbPunkt farbe={a.farbe} farbeDunkel={a.farbeDunkel} size={11} />
          <span className="text-[15px] font-bold sm:text-base">{a.kurz}</span>
          {a.landesprogramm && <BswPill kompakt />}
        </span>
        <span className="text-[13px] text-muted-foreground">×</span>
        <span className="inline-flex items-center gap-2">
          <FarbPunkt farbe={b.farbe} farbeDunkel={b.farbeDunkel} size={11} />
          <span className="text-[15px] font-bold sm:text-base">{b.kurz}</span>
          {b.landesprogramm && <BswPill kompakt />}
        </span>
        <span className="ml-2 font-display text-2xl font-bold tabular-nums">
          {p.wert === null ? "—" : `${p.wert} %`}
        </span>
        <span className="text-xs text-muted-foreground">
          bei n&thinsp;=&thinsp;{p.n} gemeinsamen Thesen
          {p.n < d.minN && " — unter der Belastbarkeits-Schranke"}
        </span>
        <button
          type="button"
          onClick={onClose}
          aria-label="Paar-Detail schließen"
          className="ml-auto inline-flex h-7 w-7 flex-none items-center justify-center rounded-full border border-border text-muted-foreground hover:text-foreground"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      </div>
      <div className="grid gap-6 p-5 sm:p-6 md:grid-cols-2">
        <div>
          <p className="mb-2 text-[11px] font-bold uppercase tracking-wider text-emerald-800 dark:text-emerald-300">
            Gleiche Position — {p.einig.length} Thesen
          </p>
          {p.einig.length === 0 ? (
            <p className="text-[12.5px] leading-relaxed text-muted-foreground">Keine These mit identischer klarer Position.</p>
          ) : (
            <div className="flex flex-col gap-2">
              {p.einig.map((id) => (
                <p key={id} className="text-[12.5px] leading-snug text-muted-foreground">
                  <strong className="font-semibold text-foreground">{id}</strong> · {d.thesen[id].these}
                </p>
              ))}
            </div>
          )}
          {p.teils.length > 0 && (
            <p className="mt-4 text-[12.5px] leading-relaxed text-muted-foreground">
              <strong className="font-semibold text-foreground">Dazu {p.teils.length} Thesen, zu denen sich beide nur unbestimmt äußern</strong>{" "}
              ({p.teils.join(", ")}) — sie zählen in der Formel als volle Übereinstimmung und heben den Wert.
            </p>
          )}
        </div>
        <div>
          <p className="mb-2 text-[11px] font-bold uppercase tracking-wider text-amber-800 dark:text-amber-300">
            Wo sie auseinandergehen
          </p>
          {p.dissens.length === 0 ? (
            <p className="text-[12.5px] leading-relaxed text-muted-foreground">
              Kein voller Dissens bei diesem Paar — die Unterschiede sind Teils-Abstufungen (eine Liste
              „dafür", die andere „teils / mit Bedingungen").
            </p>
          ) : (
            <div className="flex flex-col gap-3.5">
              {p.dissens.map((id) => {
                const ba = d.belege[`${aSlug}:${id}`];
                const bb = d.belege[`${bSlug}:${id}`];
                return (
                  <div key={id}>
                    <p className="text-[12.5px] font-semibold leading-snug">
                      {id} · {d.thesen[id].these}
                    </p>
                    {[ba, bb].filter(Boolean).map((bel) => (
                      <p key={bel!.slug} className="mt-1 flex items-start gap-2 text-xs leading-relaxed text-muted-foreground">
                        <Glyph pos={bel!.pos} size={14} className="mt-0.5" />
                        <span>
                          <strong className="font-semibold text-foreground">{bel!.kurz}</strong>{" "}
                          {bel!.href ? (
                            <a href={bel!.href} target="_blank" rel="noopener noreferrer" className="text-primary">
                              ({bel!.seitenLabel} ↗)
                            </a>
                          ) : (
                            <>({bel!.seitenLabel})</>
                          )}{" "}
                          »{bel!.beleg}«
                        </span>
                      </p>
                    ))}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export function NaeheAnsicht({ daten }: { daten: NaeheDaten }) {
  const [kombi, setKombi] = useState<[string, string] | null>(null);
  const [sortierung, setSortierung] = useState<"wert" | "liste">("wert");
  const [alleMobil, setAlleMobil] = useState(false);

  const paarListe = useMemo(() => {
    const out: { a: (typeof daten.listen)[0]; b: (typeof daten.listen)[0]; wert: number | null; n: number }[] = [];
    for (let i = 0; i < daten.listen.length; i++)
      for (let j = i + 1; j < daten.listen.length; j++) {
        const p = paarVon(daten, daten.listen[i].slug, daten.listen[j].slug);
        if (p) out.push({ a: daten.listen[i], b: daten.listen[j], wert: p.wert, n: p.n });
      }
    if (sortierung === "wert") out.sort((x, y) => (y.wert ?? -1) - (x.wert ?? -1));
    return out;
  }, [daten, sortierung]);

  return (
    <>
      {/* Breit: die Matrix */}
      <div className="mt-7 hidden overflow-hidden rounded-2xl border border-border bg-card md:block">
        <div className="overflow-x-auto p-5">
          <div
            className="grid items-center"
            style={{ gridTemplateColumns: `110px repeat(${daten.listen.length}, 72px)` }}
          >
            <span />
            {daten.listen.map((l) => (
              <span key={l.slug} className="flex flex-col items-center gap-[3px] pb-2">
                <FarbPunkt farbe={l.farbe} farbeDunkel={l.farbeDunkel} />
                <span className="text-[10px] font-semibold text-muted-foreground">{l.kurz}</span>
              </span>
            ))}
            {daten.listen.map((zeile) => (
              <ZeileFragment
                key={zeile.slug}
                daten={daten}
                zeile={zeile}
                onWahl={(a, b) => setKombi([a, b])}
              />
            ))}
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-border bg-background/60 px-5 py-3 text-[11.5px] text-muted-foreground">
          <span className="inline-flex items-center gap-1.5">
            <span className="h-3.5 w-5 rounded border border-emerald-700/30 bg-emerald-700/15" /> ≥ 70 % nah
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="h-3.5 w-5 rounded border border-amber-600/30 bg-amber-600/15" /> 40–69 %
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="h-3.5 w-5 rounded border border-red-700/30 bg-red-700/10" /> &lt; 40 % fern
          </span>
          <span>Zahl = Prozent · n im Paar-Detail · Zelle antippen → Detail</span>
          <span className="ml-auto">Eigener Quer-Scroll — die Seite scrollt nie seitwärts</span>
        </div>
      </div>

      {/* Schmal: sortierbare Liste */}
      <div className="mt-6 md:hidden">
        <div className="flex gap-1.5">
          {(
            [
              ["wert", "Nach Wert"],
              ["liste", "Nach Liste"],
            ] as const
          ).map(([k, label]) => (
            <button
              key={k}
              type="button"
              onClick={() => setSortierung(k)}
              className={
                sortierung === k
                  ? "rounded-full bg-primary px-3 py-1.5 text-xs font-semibold text-primary-foreground"
                  : "rounded-full border border-border bg-card px-3 py-1.5 text-xs font-medium text-muted-foreground"
              }
            >
              {label}
            </button>
          ))}
        </div>
        <p className="mb-1.5 mt-3 text-[11.5px] text-muted-foreground">
          Auf schmalen Screens wird die Matrix zur sortierbaren Liste.
        </p>
        <div className="flex flex-col gap-1.5">
          {(alleMobil ? paarListe : paarListe.slice(0, 10)).map((p) => (
            <button
              key={`${p.a.slug}|${p.b.slug}`}
              type="button"
              onClick={() => setKombi([p.a.slug, p.b.slug])}
              className="flex items-center gap-2 rounded-xl border border-border bg-card px-3 py-2.5 text-left"
            >
              <FarbPunkt farbe={p.a.farbe} farbeDunkel={p.a.farbeDunkel} size={8} />
              <span className="text-[12.5px] font-semibold">{p.a.kurz}</span>
              <span className="text-[11px] text-muted-foreground">×</span>
              <FarbPunkt farbe={p.b.farbe} farbeDunkel={p.b.farbeDunkel} size={8} />
              <span className="text-[12.5px] font-semibold">{p.b.kurz}</span>
              <span className="ml-auto text-[13px] font-bold tabular-nums">
                {p.wert === null ? "—" : `${p.wert} %`}
              </span>
              <span className="text-[10px] text-muted-foreground">n={p.n}</span>
            </button>
          ))}
        </div>
        {!alleMobil && paarListe.length > 10 && (
          <button
            type="button"
            onClick={() => setAlleMobil(true)}
            className="mt-2 text-xs font-semibold text-primary"
          >
            Alle {paarListe.length} Paare ⌄
          </button>
        )}
      </div>

      {kombi && <PaarDetail d={daten} kombi={kombi} onClose={() => setKombi(null)} />}
    </>
  );
}

function ZeileFragment({
  daten,
  zeile,
  onWahl,
}: {
  daten: NaeheDaten;
  zeile: NaeheDaten["listen"][0];
  onWahl: (a: string, b: string) => void;
}) {
  return (
    <>
      <div className="flex items-center gap-1.5 py-0.5 pr-2">
        <FarbPunkt farbe={zeile.farbe} farbeDunkel={zeile.farbeDunkel} size={9} />
        <span className="text-xs font-semibold">{zeile.kurz}</span>
      </div>
      {daten.listen.map((spalte) => {
        if (spalte.slug === zeile.slug) return <span key={spalte.slug} />;
        const p = paarVon(daten, zeile.slug, spalte.slug);
        const stil = skalaStil(p?.wert ?? null);
        return (
          <span key={spalte.slug} className="flex justify-center p-[3px]">
            <button
              type="button"
              onClick={() => onWahl(zeile.slug, spalte.slug)}
              aria-label={`${zeile.kurz} und ${spalte.kurz}: ${p?.wert ?? "—"} Prozent bei n = ${p?.n ?? 0} — Detail öffnen`}
              className={`inline-flex h-[34px] w-16 items-center justify-center rounded-lg text-[12.5px] font-bold tabular-nums outline-none transition-transform hover:scale-105 focus-visible:ring-2 focus-visible:ring-ring ${stil.className}`}
            >
              {p?.wert === null || !p ? "—" : p.wert}
            </button>
          </span>
        );
      })}
    </>
  );
}
