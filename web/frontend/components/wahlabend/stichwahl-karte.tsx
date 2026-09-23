"use client";

// Die Karte der Stichwahl (docs/plan-stichwahl-spannung.md S5): die 91
// Urnenbezirke, je Bezirk in der Farbe dessen, der dort vorn liegt — Prange
// rot, Rohr orange — und kräftiger, je deutlicher der Vorsprung. Tims
// Entscheidung vom 15.09.2026; die Designsprache kennt sonst keine
// Parteifarben-Flächen, für zwei Namen auf einem Stimmzettel ist das die
// Ausnahme (DESIGNSPRACHE „Parteifarben").
//
// Zwei Zustände in einer Karte: Ein GEZÄHLTER Bezirk trägt seine Stichwahl-
// Farbe und einen festen Rand; ein OFFENER zeigt den ersten Wahlgang, halb
// so kräftig und gestrichelt. So sieht man die Auszählung laufen — und
// vorher, wo die beiden ihre Hochburgen hatten.
//
// Die 42 Briefwahlbezirke haben keine Fläche; sie stehen als Zeile darunter.
// Kein neuer Endpunkt: `/api/wahlabend/stichwahl/bezirke` (S1) trägt je
// Bezirk beide Wahlgänge.

import { useEffect, useMemo, useRef, useState } from "react";
import { ChevronLeft } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { KICKER, Punkt } from "@/components/wahlabend/bausteine";
import { Gebietskarte } from "@/components/wahlabend/gebietskarte";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { prozent, zahl } from "@/lib/wahlabend";
import { ladeWahlbezirke, roemisch, type Wahlbezirkflaeche } from "@/lib/wahlgebiete";
import {
  abrufTakt,
  bezirkAnteil,
  bezirkFuehrung,
  flaechenAlpha,
  stichwahlBezirkePfad,
  type Stichwahl,
  type StichwahlBezirk,
  type StichwahlBezirke,
  type StichwahlKandidat,
} from "@/lib/stichwahl";
import { bezugsperson } from "@/components/wahlabend/stichwahl-verlauf";

/** Die Kartenfarbe je Kandidatur: Prange in der Listenfarbe der SPD, Rohr in
 *  Orange — nicht Grün, weil er parteilos antritt und Grün neben Rot auf
 *  einer Fläche die Ampel wäre. Als hell/dunkel-Paar ohne Alpha; die
 *  Deckkraft kommt aus dem Vorsprung. */
function kartenfarbe(k: StichwahlKandidat, kandidaten: readonly StichwahlKandidat[]): { hell: string; dunkel: string } {
  const erster = bezugsperson(kandidaten);
  if (k.slug === erster?.slug) return { hell: k.color || "#e3000f", dunkel: k.color_dark || "#ff6b6b" };
  return { hell: "#e8590c", dunkel: "#ff8a3d" };
}

function mitAlpha(hex: string, a: number): string {
  const n = Math.round(Math.min(1, Math.max(0, a)) * 255).toString(16).padStart(2, "0");
  return `${hex}${n}`;
}

type Fokus = "city" | number;

function Chip({ an, onClick, children, title }: { an: boolean; onClick: () => void; children: React.ReactNode; title?: string }) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={title}
      aria-pressed={an}
      className={cn(
        "inline-flex min-h-9 items-center gap-1 rounded-full border px-3.5 text-[13px] font-medium transition-colors",
        an ? "border-foreground bg-foreground text-background" : "border-border bg-card text-foreground hover:bg-primary/5",
      )}
    >
      {children}
    </button>
  );
}

/** Ein Bezirk: erster Wahlgang und Stichwahl nebeneinander. */
function Bezirkstafel({ zeile, kandidaten, schliessen }: {
  zeile: StichwahlBezirk;
  kandidaten: readonly StichwahlKandidat[];
  schliessen: () => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => { ref.current?.scrollIntoView({ behavior: "smooth", block: "nearest" }); }, [zeile.number]);
  return (
    <div ref={ref} className="rounded-xl border border-border bg-muted/30 p-3.5" data-testid="bezirkstafel">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className={KICKER}>Wahlbezirk {zeile.number} · Wahlbereich {roemisch(zeile.area)}</p>
          <p className="font-display text-[15px] font-bold leading-snug tracking-tight">{zeile.name}</p>
        </div>
        <button
          type="button"
          onClick={schliessen}
          className="flex-none rounded-md px-2 py-1 text-[12px] font-medium text-muted-foreground hover:bg-primary/5 hover:text-foreground"
        >
          schließen
        </button>
      </div>
      <table className="mt-3 w-full text-[13px]">
        <thead>
          <tr className={KICKER}>
            <th className="pb-1 text-left font-medium">&nbsp;</th>
            <th className="pb-1 text-right font-medium">1. Wahlgang</th>
            <th className="pb-1 text-right font-medium">Stichwahl</th>
          </tr>
        </thead>
        <tbody>
          {kandidaten.map((k) => (
            <tr key={k.slug}>
              <td className="flex items-center gap-2 py-1 font-medium">
                <Punkt color={k.color || "#6b7a8c"} dark={k.color_dark || "#a3b1c2"} />
                <span className="truncate">{k.name}</span>
              </td>
              <td className="py-1 text-right tabular-nums text-muted-foreground">
                {prozent(bezirkAnteil(zeile, k.slug, "first_round"))}
                <span className="ml-1 text-[11px]">({zahl(zeile.first_round[k.slug] ?? null)})</span>
              </td>
              <td className="py-1 text-right font-semibold tabular-nums">
                {zeile.counted ? (
                  <>
                    {prozent(bezirkAnteil(zeile, k.slug, "votes"))}
                    <span className="ml-1 text-[11px] font-normal text-muted-foreground">({zahl(zeile.votes[k.slug] ?? null)})</span>
                  </>
                ) : "–"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="mt-2.5 text-[11.5px] text-muted-foreground">
        {zeile.counted
          ? <>{zahl(zeile.valid_votes)} gültige Stimmen{zeile.eligible ? <> · {zahl(zeile.eligible)} Wahlberechtigte</> : null}</>
          : <>Noch nicht ausgezählt{zeile.eligible ? <> · {zahl(zeile.eligible)} Wahlberechtigte</> : null}</>}
      </p>
    </div>
  );
}

export function StichwahlKarte({ daten, probe, counted, auswahl, className }: {
  daten: Stichwahl;
  probe: string | null;
  counted: string | null;
  /** Ein Bezirk, den der Ticker gezeigt haben will — `n` zählt hoch, damit
   *  derselbe Bezirk zweimal hintereinander gewählt werden kann. */
  auswahl?: { nr: number; n: number } | null;
  className?: string;
}) {
  const wer = bezugsperson(daten.candidates);
  const [fokus, setFokus] = useState<Fokus>("city");
  const [flaechen, setFlaechen] = useState<Wahlbezirkflaeche[]>([]);
  const [gewaehlt, setGewaehlt] = useState<number | null>(null);
  useEffect(() => { void ladeWahlbezirke().then(setFlaechen); }, []);

  const pfad = stichwahlBezirkePfad(probe, counted);
  const abfrage = useQuery({
    queryKey: ["stichwahl-bezirke", pfad],
    queryFn: () => api.get<StichwahlBezirke>(pfad),
    // Im Takt der Tafel (`abrufTakt`) — mit einer Minute hinkte die Karte am
    // Abend bis zu 45 s hinter den Zahlen darüber her.
    refetchInterval: abrufTakt(daten),
    refetchIntervalInBackground: true,
    staleTime: 10_000,
  });
  // Meldet die Tafel einen neuen Stand, zieht die Karte sofort nach, statt
  // auf ihren eigenen Takt zu warten.
  const { refetch } = abfrage;
  const gemeldet = daten.reports_received;
  const ersterStand = useRef(gemeldet);
  useEffect(() => {
    if (gemeldet !== ersterStand.current) void refetch();
  }, [gemeldet, refetch]);
  const bezirke = useMemo(() => new Map((abfrage.data?.districts ?? []).map((d) => [d.number, d])), [abfrage.data]);

  // Frisch gezählte Bezirke blitzen zweimal auf — nur was seit dem letzten
  // Abruf DIESER Karte dazukam, nie beim ersten Laden (DESIGNSPRACHE §7).
  const kasten = useRef<HTMLElement>(null);
  const gezaehltVorher = useRef<Set<number> | null>(null);
  useEffect(() => {
    if (!abfrage.data) return;
    const jetzt = new Set(abfrage.data.districts.filter((d) => d.counted).map((d) => d.number));
    const vorher = gezaehltVorher.current;
    gezaehltVorher.current = jetzt;
    if (!vorher || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    for (const nr of jetzt) {
      if (vorher.has(nr)) continue;
      kasten.current?.querySelector<SVGPathElement>(`path[data-nr="${nr}"]`)?.animate(
        [{ opacity: 1 }, { opacity: 0.2 }, { opacity: 1 }, { opacity: 0.2 }, { opacity: 1 }],
        { duration: 1800, easing: "ease-in-out" },
      );
    }
  }, [abfrage.data]);

  // Der Ticker wählt einen Bezirk: ganze Stadt zeigen, ihn markieren, hinscrollen.
  useEffect(() => {
    if (!auswahl) return;
    setFokus("city");
    setGewaehlt(auswahl.nr);
    kasten.current?.scrollIntoView({
      behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth",
      block: "start",
    });
  }, [auswahl]);

  // Je Bezirk: wer vorn liegt (Stichwahl, wo gezählt; sonst erster Wahlgang)
  // und wie deutlich. Die Deckkraft misst sich am deutlichsten Vorsprung der
  // GEZEIGTEN Flächen — im Ausschnitt eines Wahlbereichs sollen SEINE
  // Unterschiede sichtbar sein.
  const slugs = useMemo(() => daten.candidates.map((k) => k.slug), [daten.candidates]);
  const fuehrung = useMemo(() => {
    const m = new Map<number, { slug: string; share: number; live: boolean }>();
    for (const d of bezirke.values()) {
      if (d.postal) continue;
      const f = bezirkFuehrung(d, slugs);
      if (f) m.set(d.number, f);
    }
    return m;
  }, [bezirke, slugs]);
  const imFokus = useMemo(
    () => (typeof fokus === "number" ? flaechen.filter((f) => f.properties.wb === fokus) : flaechen),
    [flaechen, fokus],
  );
  const bereiche = useMemo(() => [...new Set(flaechen.map((f) => f.properties.wb))].sort((a, b) => a - b), [flaechen]);
  const maxShare = useMemo(() => {
    let max = 50;
    for (const f of imFokus) {
      const x = fuehrung.get(f.properties.nr);
      if (x && x.share > max) max = x.share;
    }
    return max;
  }, [imFokus, fuehrung]);
  const farben = useMemo(
    () => new Map(daten.candidates.map((k) => [k.slug, kartenfarbe(k, daten.candidates)])),
    [daten.candidates],
  );
  const flaechenfarbe = (nr: number): string | null => {
    const f = fuehrung.get(nr);
    const c = f ? farben.get(f.slug) : undefined;
    if (!f || !c) return null;
    const a = flaechenAlpha(f.share, maxShare, f.live);
    return `light-dark(${mitAlpha(c.hell, a)}, ${mitAlpha(c.dunkel, a)})`;
  };
  const vornZaehler = useMemo(() => {
    const z = new Map<string, number>();
    for (const f of imFokus) {
      const x = fuehrung.get(f.properties.nr);
      if (x?.live) z.set(x.slug, (z.get(x.slug) ?? 0) + 1);
    }
    return z;
  }, [imFokus, fuehrung]);
  const gezaehlt = [...bezirke.values()].filter((d) => !d.postal && d.counted).length;
  const urne = [...bezirke.values()].filter((d) => !d.postal).length;
  const brief = [...bezirke.values()].filter((d) => d.postal);
  const briefGezaehlt = brief.filter((d) => d.counted);
  const briefAnteil = useMemo(() => {
    if (!wer || briefGezaehlt.length === 0) return null;
    let mein = 0;
    let alle = 0;
    for (const d of briefGezaehlt) {
      for (const [slug, v] of Object.entries(d.votes)) {
        alle += v ?? 0;
        if (slug === wer.slug) mein += v ?? 0;
      }
    }
    return alle > 0 ? Math.round((1000 * mein) / alle) / 10 : null;
  }, [briefGezaehlt, wer]);
  const gewaehlterBezirk = gewaehlt !== null ? bezirke.get(gewaehlt) : undefined;

  function geheZu(f: Fokus) {
    setFokus(f);
    setGewaehlt(null);
  }
  if (!wer) return null;

  return (
    <section ref={kasten} className={cn("mt-5 scroll-mt-20 rounded-2xl border border-border bg-card p-4 shadow-[0_1px_2px_rgba(0,0,0,0.04)] @container sm:p-5", className)} data-testid="stichwahl-karte">
      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
        <div className="min-w-0">
          <p className={KICKER}>Wahlbezirke</p>
          <h2 className="mt-0.5 font-display text-[16px] font-bold tracking-tight">
            {typeof fokus === "number" ? `Wahlbereich ${roemisch(fokus)}` : "Wo die beiden stark sind"}
          </h2>
          <p className="mt-1 text-[13px] text-muted-foreground">
            {gezaehlt === 0
              ? "Noch der erste Wahlgang, blass: wer wo vorn lag. Gezählte Bezirke bekommen ihre Stichwahl-Farbe und einen festen Rand."
              : `${gezaehlt} von ${urne} Urnenbezirken gezählt — ${daten.candidates
                  .map((k) => `${vornZaehler.get(k.slug) ?? 0}× ${k.name.split(" ").pop()}`)
                  .join(", ")} vorn; blass und gestrichelt ist noch der erste Wahlgang.`}{" "}
            Je kräftiger, desto deutlicher der Vorsprung. Ein Bezirk antippen zeigt beide Wahlgänge.
          </p>
        </div>
        {typeof fokus === "number" ? (
          <button
            type="button"
            onClick={() => geheZu("city")}
            className="inline-flex min-h-9 flex-none items-center gap-1 rounded-full border border-border bg-card px-3.5 text-[13px] font-medium text-foreground hover:bg-primary/5"
          >
            <ChevronLeft aria-hidden className="h-4 w-4" />
            Ganze Stadt
          </button>
        ) : null}
      </div>

      <div className="mt-3 flex flex-wrap gap-1.5">
        <Chip an={fokus === "city"} onClick={() => geheZu("city")}>Ganze Stadt</Chip>
        {bereiche.map((nr) => (
          <Chip key={nr} an={fokus === nr} onClick={() => geheZu(nr)} title={`Wahlbereich ${roemisch(nr)}`}>
            {roemisch(nr)}
          </Chip>
        ))}
      </div>

      <ul className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-[12px] text-muted-foreground" aria-label="Legende" data-testid="karten-legende">
        {daten.candidates.map((k) => {
          const c = farben.get(k.slug);
          return (
            <li key={k.slug} className="flex items-center gap-1.5">
              <span aria-hidden className="inline-block h-3 w-5 rounded-sm" style={{ background: c ? `light-dark(${mitAlpha(c.hell, 0.85)}, ${mitAlpha(c.dunkel, 0.85)})` : undefined }} />
              {k.name} vorn
            </li>
          );
        })}
        <li className="flex items-center gap-1.5">
          <span aria-hidden className="inline-block h-3 w-5 rounded-sm border border-dashed border-border bg-muted" />
          noch offen (1. Wahlgang)
        </li>
      </ul>
      <div className={cn("mt-2 grid items-start gap-4", gewaehlterBezirk && "@3xl:grid-cols-[minmax(0,1fr)_22rem]")}>
        <Gebietskarte
          flaechen={imFokus}
          farbe={flaechenfarbe}
          gewaehlt={gewaehlt}
          onWaehlen={(nr) => setGewaehlt((alt) => (alt === nr ? null : nr))}
          beschriftung={typeof fokus === "number" ? (e) => String(e.nr) : undefined}
          schrift={12}
          hoehe={560}
          blass={(nr) => !(bezirke.get(nr)?.counted ?? false)}
          rand={(nr) => bezirke.get(nr)?.counted ?? false}
          titel={(e) => {
            const d = bezirke.get(e.nr);
            const kopf = `${e.nr} ${d?.name ?? e.name} · Wahlbereich ${roemisch(e.wb)}`;
            if (!d) return kopf;
            const vorher = prozent(bezirkAnteil(d, wer.slug, "first_round"));
            if (!d.counted) return `${kopf} — noch offen · 1. Wahlgang ${wer.name} ${vorher}`;
            return `${kopf} — ${wer.name} ${prozent(bezirkAnteil(d, wer.slug, "votes"))} (1. Wahlgang ${vorher})`;
          }}
          hinweis={abfrage.isPending ? "Wahlbezirke werden geladen …" : "Grenzen: Stadt Oldenburg, openGEOdata"}
        />
        {gewaehlterBezirk ? (
          <Bezirkstafel zeile={gewaehlterBezirk} kandidaten={daten.candidates} schliessen={() => setGewaehlt(null)} />
        ) : null}
      </div>

      {abfrage.data ? (
        <p className="mt-3 text-[12px] text-muted-foreground">
          Briefwahl: {briefGezaehlt.length} von {brief.length} Briefwahlbezirken gezählt
          {briefAnteil !== null ? <> · {wer.name} dort {prozent(briefAnteil)}</> : null} — Briefwahlbezirke haben keine Fläche.
        </p>
      ) : null}
    </section>
  );
}
