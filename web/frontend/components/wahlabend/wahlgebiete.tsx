"use client";

// Die Karte neben der Rangfolge: sechs Wahlbereiche — und eine Ebene tiefer
// die 91 Wahlbezirke, die es an der Urne gibt.
//
// Tims zwei Wünsche vom 14.09.2026: „die openstreetmap der Wahlbereiche mit
// klickbaren shades näher ranbringen (Wo is eigentlich nochmal Wahlbereich
// 5)" und „ggf die Wahlbezirke ebenfalls aus opendata als Geodaten
// mitverwenden für visuelle Filterung".
//
// **Was die Ebenen trennt.** Die Wahlbereiche sind die Einheit der
// Sitzverteilung (§ 37 Abs. 3) — sie stehen auch in der Rangfolge daneben.
// Die Wahlbezirke sind die Einheit der Auszählung: ein Wahllokal, ein paar
// hundert bis zweitausend Stimmen. Sie beantworten eine andere Frage („wie
// hat mein Wahllokal gewählt?") und kommen deshalb erst auf Zuruf — mit
// ihnen kommen auch 42 KB Geometrie und eine zweite Abfrage.
//
// **Die Briefwahl hat keine Fläche.** 42 der 133 Bezirke sind Briefwahl und
// tragen gut ein Drittel der Stimmen; sie gehören zu einem Wahlbereich, aber
// zu keinem Ort. Die Karte lässt sie weg und sagt das — sie zu verschweigen
// hieße, ein Drittel der Wählenden verschwinden zu lassen.

import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { KICKER, Punkt } from "@/components/wahlabend/bausteine";
import { Gebietskarte } from "@/components/wahlabend/gebietskarte";
import { Segmented } from "@/components/ui/segmented";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import {
  ladeWahlbereiche,
  ladeWahlbezirke,
  roemisch,
  type Wahlbereichflaeche,
  type Wahlbezirkflaeche,
} from "@/lib/wahlgebiete";
import {
  bezirkePfad,
  prozent,
  zahl,
  type Wahlabend,
  type WahlabendPartei,
  type Wahlbezirke,
} from "@/lib/wahlabend";

type Ebene = "bereiche" | "bezirke";

const EBENEN: { value: Ebene; label: string }[] = [
  { value: "bereiche", label: "Wahlbereiche" },
  { value: "bezirke", label: "Wahlbezirke" },
];

/** Das Ergebnis EINES Wahlbezirks, aufgeklappt unter der Karte. */
function Bezirkstafel({ zeile, daten, schliessen }: {
  zeile: Wahlbezirke["districts"][number];
  daten: Wahlabend;
  schliessen: () => void;
}) {
  const stamm = new Map(daten.parties.map((p) => [p.slug, p]));
  const listen = [...zeile.parties]
    .filter((p) => p.votes)
    .sort((a, b) => (b.votes ?? 0) - (a.votes ?? 0))
    .slice(0, 6);
  return (
    <div className="mt-3 rounded-xl border border-border bg-muted/30 p-3">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className={KICKER}>
            Wahlbezirk {zeile.number} · Wahlbereich {roemisch(zeile.area)}
          </p>
          <p className="truncate font-display text-[14px] font-bold tracking-tight">{zeile.name}</p>
        </div>
        <button
          type="button"
          onClick={schliessen}
          className="flex-none rounded-md px-2 py-1 text-[11.5px] font-medium text-muted-foreground hover:bg-primary/5 hover:text-foreground"
        >
          schließen
        </button>
      </div>
      {!zeile.counted ? (
        <p className="mt-2 text-[12.5px] text-muted-foreground">Hier ist noch nicht ausgezählt.</p>
      ) : (
        <>
          <ol className="mt-2 space-y-1">
            {listen.map((p) => {
              const info = stamm.get(p.slug);
              return (
                <li key={p.slug} className="flex items-center gap-2 text-[12.5px]">
                  <Punkt color={info?.color ?? "#6b7a8c"} dark={info?.color_dark ?? "#a3b1c2"} />
                  <span className="min-w-0 flex-1 truncate">{info?.short ?? p.slug}</span>
                  <span className="flex-none tabular-nums text-muted-foreground">{zahl(p.votes)}</span>
                  <span className="w-14 flex-none text-right font-semibold tabular-nums">{prozent(p.share_pct)}</span>
                </li>
              );
            })}
          </ol>
          <p className="mt-2 text-[11px] text-muted-foreground">
            {zahl(zeile.totals.valid_votes)} gültige Stimmen
            {zeile.totals.turnout_pct !== null ? <> · Wahlbeteiligung {prozent(zeile.totals.turnout_pct)}</> : null}
          </p>
        </>
      )}
    </div>
  );
}

export function Wahlgebiete({ daten, partei, probe, counted, rueckblick, onBereich, className }: {
  daten: Wahlabend;
  /** Die gewählte Liste — sie färbt die Karte. */
  partei: WahlabendPartei;
  probe: string | null;
  counted: string | null;
  rueckblick: string | null;
  /** Klick auf einen Wahlbereich: zur Karte dieses Wahlbereichs springen. */
  onBereich: (nr: number) => void;
  className?: string;
}) {
  const [ebene, setEbene] = useState<Ebene>("bereiche");
  const [bereiche, setBereiche] = useState<Wahlbereichflaeche[]>([]);
  const [bezirke, setBezirke] = useState<Wahlbezirkflaeche[]>([]);
  const [gewaehlt, setGewaehlt] = useState<number | null>(null);

  useEffect(() => { void ladeWahlbereiche().then(setBereiche); }, []);
  // Erst auf Zuruf: 42 KB Geometrie und eine zweite Abfrage brauchen nur die,
  // die auch hinsehen.
  useEffect(() => { if (ebene === "bezirke") void ladeWahlbezirke().then(setBezirke); }, [ebene]);

  const pfad = bezirkePfad(probe, counted, rueckblick);
  const abfrage = useQuery({
    queryKey: ["wahlbezirke", pfad],
    queryFn: () => api.get<Wahlbezirke>(pfad),
    enabled: ebene === "bezirke",
    staleTime: rueckblick ? Infinity : 60_000,
  });

  const zaehlt = daten.phase !== "before";
  // Wahlbereiche: der Anteil dieser Liste. Wahlbezirke: derselbe Anteil je
  // Bezirk — dieselbe Frage, feiner aufgelöst.
  const werteBereiche = useMemo(
    () => new Map(partei.areas.filter((z) => z.share_pct !== null).map((z) => [z.area, z.share_pct as number])),
    [partei],
  );
  const werteBezirke = useMemo(() => {
    const m = new Map<number, number>();
    for (const z of abfrage.data?.districts ?? []) {
      if (z.postal || !z.counted) continue;
      const p = z.parties.find((x) => x.slug === partei.slug);
      if (p?.share_pct !== null && p?.share_pct !== undefined) m.set(z.number, p.share_pct);
    }
    return m;
  }, [abfrage.data, partei.slug]);

  const bezirkeNachNr = useMemo(
    () => new Map((abfrage.data?.districts ?? []).map((z) => [z.number, z])),
    [abfrage.data],
  );
  const gewaehlterBezirk = gewaehlt !== null ? bezirkeNachNr.get(gewaehlt) : undefined;
  const brief = (abfrage.data?.districts ?? []).filter((z) => z.postal).length;

  return (
    <section className={cn("rounded-2xl border border-border bg-card p-4 shadow-[0_1px_2px_rgba(0,0,0,0.04)]", className)}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className={KICKER}>Wo das ist</p>
          <h3 className="mt-0.5 font-display text-[15px] font-bold tracking-tight">
            {ebene === "bereiche" ? "Die sechs Wahlbereiche" : "Die Wahlbezirke"}
          </h3>
        </div>
        <Segmented value={ebene} onChange={(v) => { setEbene(v); setGewaehlt(null); }} options={EBENEN} />
      </div>

      {ebene === "bereiche" ? (
        <Gebietskarte
          className="mt-2"
          flaechen={bereiche}
          werte={zaehlt ? werteBereiche : undefined}
          onWaehlen={onBereich}
          beschriftung={(e) => roemisch(e.nr)}
          titel={(e) => {
            const z = partei.areas.find((a) => a.area === e.nr);
            const b = daten.areas.find((a) => a.number === e.nr);
            if (!z || !b) return `Wahlbereich ${roemisch(e.nr)}`;
            return `Wahlbereich ${z.roman} · ${b.name}`
              + (z.votes !== null ? ` — ${partei.short} ${prozent(z.share_pct)}, ${zahl(z.votes)} Stimmen` : "");
          }}
          hinweis={zaehlt
            ? `Je kräftiger, desto stärker ${partei.short} dort · Grenzen: Stadt Oldenburg`
            : "Grenzen: Stadt Oldenburg, openGEOdata"}
        />
      ) : (
        <>
          <Gebietskarte
            className="mt-2"
            flaechen={bezirke}
            werte={zaehlt ? werteBezirke : undefined}
            gewaehlt={gewaehlt}
            onWaehlen={(nr) => setGewaehlt((alt) => (alt === nr ? null : nr))}
            titel={(e) => {
              const z = bezirkeNachNr.get(e.nr);
              const p = z?.parties.find((x) => x.slug === partei.slug);
              const kopf = `${e.nr} ${z?.name ?? e.name} · Wahlbereich ${roemisch(e.wb)}`;
              if (!z?.counted) return `${kopf} — noch nicht ausgezählt`;
              return `${kopf} — ${partei.short} ${prozent(p?.share_pct)}, ${zahl(p?.votes)} von ${zahl(z.totals.valid_votes)}`;
            }}
            hinweis={abfrage.isPending
              ? "Wahlbezirke werden geladen …"
              : `Antippen zeigt das Ergebnis · ${brief} Briefwahlbezirke haben keine Fläche`}
          />
          {gewaehlterBezirk ? (
            <Bezirkstafel zeile={gewaehlterBezirk} daten={daten} schliessen={() => setGewaehlt(null)} />
          ) : null}
          {/* Die Briefwahl steht als Zeile da, wo die Karte sie nicht zeigen
              kann — mit derselben Zahl, die auch die Flächen tragen. */}
          {abfrage.data && zaehlt ? (
            <p className="mt-2 text-[11.5px] text-muted-foreground">
              Briefwahl: {partei.short}{" "}
              {prozent(anteilBriefwahl(abfrage.data, partei.slug))} über alle {brief} Briefwahlbezirke.
            </p>
          ) : null}
        </>
      )}
    </section>
  );
}

/** Der Anteil einer Liste über alle Briefwahlbezirke — eine Zahl, weil die
 *  einzelnen Briefwahlbezirke niemandem etwas sagen. */
function anteilBriefwahl(daten: Wahlbezirke, slug: string): number | null {
  let stimmen = 0;
  let gueltig = 0;
  for (const z of daten.districts) {
    if (!z.postal || !z.counted) continue;
    gueltig += z.totals.valid_votes ?? 0;
    stimmen += z.parties.find((p) => p.slug === slug)?.votes ?? 0;
  }
  return gueltig ? Math.round((1000 * stimmen) / gueltig) / 10 : null;
}
