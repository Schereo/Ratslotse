"use client";

// Die Karte der Stichwahl (docs/plan-stichwahl-spannung.md S5): die 91
// Urnenbezirke, getönt nach dem Anteil dessen, der im ersten Wahlgang vorn
// lag — hell, wo die andere Kandidatur stärker war, kräftig, wo er es war.
//
// Zwei Zustände in einer Karte: Ein GEZÄHLTER Bezirk trägt seine Stichwahl-
// Tönung und einen festen Rand; ein OFFENER bleibt beim ersten Wahlgang,
// halb durchsichtig und gestrichelt. So sieht man die Auszählung laufen —
// und vorher, wo die beiden ihre Hochburgen hatten.
//
// Eine Primärtönung, keine zwei Parteifarben (Designsprache: Parteifarben nur
// als Punkte). Die Frage „wo lag wer vorn" beantwortet die Legende: über
// 50 % ist die Fläche kräftig, darunter hell.
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
import { bezirkAnteil, stichwahlBezirkePfad, type Stichwahl, type StichwahlBezirk, type StichwahlBezirke, type StichwahlKandidat } from "@/lib/stichwahl";
import { bezugsperson } from "@/components/wahlabend/stichwahl-verlauf";

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

export function StichwahlKarte({ daten, probe, counted, className }: {
  daten: Stichwahl;
  probe: string | null;
  counted: string | null;
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
    refetchInterval: 60_000,
    staleTime: 30_000,
  });
  const bezirke = useMemo(() => new Map((abfrage.data?.districts ?? []).map((d) => [d.number, d])), [abfrage.data]);

  // Die Tönung: Stichwahl, wo gezählt; sonst der erste Wahlgang. Die Spanne
  // rechnet die Karte über die gezeigten Flächen — im Ausschnitt eines
  // Wahlbereichs sollen SEINE Unterschiede sichtbar sein.
  const werte = useMemo(() => {
    const m = new Map<number, number>();
    if (!wer) return m;
    for (const d of bezirke.values()) {
      if (d.postal) continue;
      const v = d.counted ? bezirkAnteil(d, wer.slug, "votes") : bezirkAnteil(d, wer.slug, "first_round");
      if (v !== null) m.set(d.number, v);
    }
    return m;
  }, [bezirke, wer]);
  const imFokus = useMemo(
    () => (typeof fokus === "number" ? flaechen.filter((f) => f.properties.wb === fokus) : flaechen),
    [flaechen, fokus],
  );
  const bereiche = useMemo(() => [...new Set(flaechen.map((f) => f.properties.wb))].sort((a, b) => a - b), [flaechen]);
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
    <section className={cn("mt-5 rounded-2xl border border-border bg-card p-4 shadow-[0_1px_2px_rgba(0,0,0,0.04)] @container sm:p-5", className)} data-testid="stichwahl-karte">
      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
        <div className="min-w-0">
          <p className={KICKER}>Wahlbezirke</p>
          <h2 className="mt-0.5 font-display text-[16px] font-bold tracking-tight">
            {typeof fokus === "number" ? `Wahlbereich ${roemisch(fokus)}` : "Wo die beiden stark sind"}
          </h2>
          <p className="mt-1 text-[13px] text-muted-foreground">
            {gezaehlt === 0
              ? `Getönt nach dem ersten Wahlgang: je kräftiger, desto stärker ${wer.name} dort. Gezählte Bezirke bekommen ihre Stichwahl-Tönung und einen festen Rand.`
              : `${gezaehlt} von ${urne} Urnenbezirken gezählt — die tragen ihre Stichwahl-Tönung und einen festen Rand; blass und gestrichelt ist noch der erste Wahlgang.`}{" "}
            Ein Bezirk antippen zeigt beide Wahlgänge.
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

      <div className={cn("mt-3 grid items-start gap-4", gewaehlterBezirk && "@3xl:grid-cols-[minmax(0,1fr)_22rem]")}>
        <Gebietskarte
          flaechen={imFokus}
          werte={werte}
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
          hinweis={abfrage.isPending
            ? "Wahlbezirke werden geladen …"
            : `Tönung: Anteil ${wer.name} · kräftig = vorn · blass = noch offen · Grenzen: Stadt Oldenburg, openGEOdata`}
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
