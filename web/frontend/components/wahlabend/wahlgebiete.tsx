"use client";

// Die Karte des Wahlabends: sechs Wahlbereiche — und eine Ebene tiefer die
// 91 Wahlbezirke, die es an der Urne gibt.
//
// Tims zwei Wünsche vom 14.09.2026: „die openstreetmap der Wahlbereiche mit
// klickbaren shades näher ranbringen (Wo is eigentlich nochmal Wahlbereich
// 5)" und „ggf die Wahlbezirke ebenfalls aus opendata als Geodaten
// mitverwenden für visuelle Filterung". Und sein Befund am selben Abend zur
// ersten Fassung: „die Karte ist wirklich sehr klein … besonders wenn man
// auf Wahlbezirke geht, kann man die gar nicht richtig sehen." Deshalb:
//
// **Die Karte hat die ganze Breite**, die Rangfolge steht darunter. Und die
// Wahlbezirke kommen nicht als 91 Splitter auf einmal, sondern **je
// Wahlbereich**: Ein Wahlbereich antippen zoomt in seine 15 bis 24 Bezirke —
// die Projektion passt den Ausschnitt in dieselbe Box, jeder Bezirk wird so
// fünf- bis sechsmal so groß, und auf dem Touchscreen trifft der Daumen.
// „Ganze Stadt" bleibt als Überblick wählbar.
//
// **Was die Ebenen trennt.** Die Wahlbereiche sind die Einheit der
// Sitzverteilung (§ 37 Abs. 3), die Wahlbezirke die der Auszählung: ein
// Wahllokal, ein paar hundert bis zweitausend Stimmen. Die Bezirks-Geometrie
// (42 KB) und die zweite Abfrage kommen erst, wenn jemand hineingeht.
//
// **Die Briefwahl hat keine Fläche.** 42 der 133 Bezirke sind Briefwahl und
// tragen gut ein Drittel der Stimmen; sie gehören zu einem Wahlbereich, aber
// zu keinem Ort. Die Karte lässt sie weg und sagt das.

import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import { Segmented } from "@/components/ui/segmented";
import { KICKER, Punkt } from "@/components/wahlabend/bausteine";
import { Gebietskarte } from "@/components/wahlabend/gebietskarte";
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

/** Welcher Ausschnitt gezeigt wird: die sechs Wahlbereiche, alle Wahlbezirke
 *  der Stadt, oder die Wahlbezirke EINES Wahlbereichs (1–6). */
type Fokus = "bereiche" | "city" | number;  // `city` englisch wie die Werte des Vertrags

/** Der Umschalter über der Karte — Tims Wunsch 15.09.: „bei Wahlbereiche
 *  oben bei der Map fehlt ein Toggle zwischen Wahlbereiche und Wahlbezirke".
 *  Vorher kam man in die Bezirke nur, indem man einen Wahlbereich antippte,
 *  und zurück nur über einen Knopf, der erst dort stand. */
const EBENEN = [
  { value: "bereiche", label: "Wahlbereiche" },
  { value: "bezirke", label: "Wahlbezirke" },
] as const;

function Chip({ an, onClick, children, title }: { an: boolean; onClick: () => void; children: React.ReactNode; title?: string }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={an}
      title={title}
      // Mindestens 36 px hoch: Auf dem Touchscreen ist das der Unterschied
      // zwischen Treffen und Danebentippen.
      className={cn(
        "inline-flex min-h-9 items-center gap-1.5 rounded-full border px-3.5 text-[13px] font-medium transition-colors duration-tipp",
        an ? "border-primary/30 bg-primary/5 text-primary" : "border-border bg-card text-foreground hover:bg-primary/5",
      )}
    >
      {children}
    </button>
  );
}

/** Das Ergebnis EINES Wahlbezirks — neben der Karte, auf dem Handy darunter. */
function Bezirkstafel({ zeile, daten, schliessen }: {
  zeile: Wahlbezirke["districts"][number];
  daten: Wahlabend;
  schliessen: () => void;
}) {
  const stamm = new Map(daten.parties.map((p) => [p.slug, p]));
  const listen = [...zeile.parties]
    .filter((p) => p.votes)
    .sort((a, b) => (b.votes ?? 0) - (a.votes ?? 0))
    .slice(0, 8);
  const max = listen[0]?.share_pct ?? 0;
  // Auf dem Handy steht die Tafel unter der Karte, außerhalb des Bildes —
  // wer antippt, soll sehen, dass etwas passiert ist. `nearest` rührt am
  // Schreibtisch nichts an, dort steht sie ohnehin daneben.
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => { ref.current?.scrollIntoView({ behavior: "smooth", block: "nearest" }); }, [zeile.number]);
  return (
    <div ref={ref} className="rounded-xl border border-border bg-muted/30 p-3.5">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className={KICKER}>Wahlbezirk · Wahlbereich {roemisch(zeile.area)}</p>
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
      {!zeile.counted ? (
        <p className="mt-2 text-[13px] text-muted-foreground">Hier ist noch nicht ausgezählt.</p>
      ) : (
        <>
          <ol className="mt-3 space-y-1.5">
            {listen.map((p) => {
              const info = stamm.get(p.slug);
              return (
                <li key={p.slug} className="flex items-center gap-2 text-[13px]">
                  <Punkt color={info?.color ?? "#6b7a8c"} dark={info?.color_dark ?? "#a3b1c2"} />
                  <span className="w-[5.5rem] flex-none truncate font-medium">{info?.short ?? p.slug}</span>
                  <span aria-hidden className="relative h-1.5 min-w-0 flex-1 overflow-hidden rounded-full bg-foreground/10">
                    <span className="block h-full rounded-full bg-primary/70" style={{ width: `${max > 0 ? (100 * (p.share_pct ?? 0)) / max : 0}%` }} />
                  </span>
                  <span className="w-14 flex-none text-right font-semibold tabular-nums">{prozent(p.share_pct)}</span>
                </li>
              );
            })}
          </ol>
          <p className="mt-2.5 text-[11.5px] text-muted-foreground">
            {zahl(zeile.totals.valid_votes)} gültige Stimmen
            {zeile.totals.turnout_pct !== null ? <> · Wahlbeteiligung {prozent(zeile.totals.turnout_pct)}</> : null}
          </p>
        </>
      )}
    </div>
  );
}

export function Wahlgebiete({ daten, partei, probe, counted, rueckblick, className }: {
  daten: Wahlabend;
  /** Die gewählte Liste — sie färbt die Karte. */
  partei: WahlabendPartei;
  probe: string | null;
  counted: string | null;
  rueckblick: string | null;
  className?: string;
}) {
  const [fokus, setFokus] = useState<Fokus>("bereiche");
  const [bereiche, setBereiche] = useState<Wahlbereichflaeche[]>([]);
  const [bezirke, setBezirke] = useState<Wahlbezirkflaeche[]>([]);
  const [gewaehlt, setGewaehlt] = useState<number | null>(null);
  const inBezirken = fokus !== "bereiche";

  useEffect(() => { void ladeWahlbereiche().then(setBereiche); }, []);
  // Erst auf Zuruf: 42 KB Geometrie und eine zweite Abfrage brauchen nur die,
  // die auch hineingehen.
  useEffect(() => { if (inBezirken) void ladeWahlbezirke().then(setBezirke); }, [inBezirken]);

  const pfad = bezirkePfad(probe, counted, rueckblick);
  const abfrage = useQuery({
    queryKey: ["wahlbezirke", pfad],
    queryFn: () => api.get<Wahlbezirke>(pfad),
    enabled: inBezirken,
    staleTime: rueckblick ? Infinity : 60_000,
  });

  const zaehlt = daten.phase !== "before";
  const werteBereiche = useMemo(
    () => new Map(partei.areas.filter((z) => z.share_pct !== null).map((z) => [z.area, z.share_pct as number])),
    [partei],
  );
  // Der Anteil dieser Liste je Bezirk — dieselbe Frage wie bei den
  // Wahlbereichen, feiner aufgelöst. Die Spanne der Tönung rechnet die Karte
  // über die GEZEIGTEN Flächen: Im Ausschnitt eines Wahlbereichs sollen die
  // Unterschiede zwischen seinen Bezirken sichtbar sein, nicht die zur
  // ganzen Stadt.
  const werteBezirke = useMemo(() => {
    const m = new Map<number, number>();
    for (const z of abfrage.data?.districts ?? []) {
      if (z.postal || !z.counted) continue;
      const p = z.parties.find((x) => x.slug === partei.slug);
      if (p?.share_pct !== null && p?.share_pct !== undefined) m.set(z.number, p.share_pct);
    }
    return m;
  }, [abfrage.data, partei.slug]);

  const bezirkeImFokus = useMemo(
    () => (typeof fokus === "number" ? bezirke.filter((f) => f.properties.wb === fokus) : bezirke),
    [bezirke, fokus],
  );
  const bezirkeNachNr = useMemo(
    () => new Map((abfrage.data?.districts ?? []).map((z) => [z.number, z])),
    [abfrage.data],
  );
  const gewaehlterBezirk = gewaehlt !== null ? bezirkeNachNr.get(gewaehlt) : undefined;
  const brief = (abfrage.data?.districts ?? []).filter((z) => z.postal).length;
  const fokusBereich = typeof fokus === "number" ? daten.areas.find((a) => a.number === fokus) : null;

  function geheZu(f: Fokus) {
    setFokus(f);
    setGewaehlt(null);
  }

  return (
    <section className={cn("rounded-2xl border border-border bg-card p-4 shadow-[0_1px_2px_rgba(0,0,0,0.04)] sm:p-5", className)}>
      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
        <div className="min-w-0">
          <p className={KICKER}>{inBezirken ? "Wahlbezirke" : "Wo das ist"}</p>
          <h3 className="mt-0.5 font-display text-[16px] font-bold tracking-tight">
            {!inBezirken
              ? "Die sechs Wahlbereiche"
              : fokusBereich
                ? `Wahlbereich ${fokusBereich.roman} · ${fokusBereich.name}`
                : "Alle Wahlbezirke der Stadt"}
          </h3>
          <p className="mt-1 text-[13px] text-muted-foreground">
            {!inBezirken
              ? "Ein Wahlbereich antippen öffnet seine Wahlbezirke — die Wahllokale, in denen ausgezählt wurde."
              : zaehlt
                ? `Je kräftiger, desto stärker ${partei.short} dort. Ein Wahlbezirk antippen zeigt sein Ergebnis.`
                : "Sobald ausgezählt wird, färbt sich die Karte nach der Stärke der gewählten Liste."}
          </p>
        </div>
        <Segmented
          value={inBezirken ? "bezirke" : "bereiche"}
          onChange={(v) => geheZu(v === "bezirke" ? "city" : "bereiche")}
          options={[...EBENEN]}
          className="flex-none"
        />
      </div>

      {inBezirken ? (
        // Die Wahlbereiche als Chips: Von einem zum nächsten springen, ohne
        // erst zurück zur Übersicht. „Ganze Stadt" ist der Überblick mit
        // allen 91 — dort sind die Flächen klein, das ist der Preis.
        <div className="mt-3 flex flex-wrap gap-1.5">
          <Chip an={fokus === "city"} onClick={() => geheZu("city")}>Ganze Stadt</Chip>
          {daten.areas.map((a) => (
            <Chip key={a.number} an={fokus === a.number} onClick={() => geheZu(a.number)} title={a.name}>
              {a.roman}
              <span className="hidden text-muted-foreground sm:inline">· {a.name}</span>
            </Chip>
          ))}
        </div>
      ) : null}

      {/* Karte und Tafel: nebeneinander, sobald die Karte breit genug bleibt;
          darunter gestapelt. Die Karte bekommt immer den größeren Teil. */}
      <div className={cn("mt-3 grid items-start gap-4", inBezirken && gewaehlterBezirk && "@3xl:grid-cols-[minmax(0,1fr)_20rem]")}>
        {!inBezirken ? (
          <Gebietskarte
            flaechen={bereiche}
            werte={zaehlt ? werteBereiche : undefined}
            onWaehlen={(nr) => geheZu(nr)}
            beschriftung={(e) => roemisch(e.nr)}
            schrift={18}
            hoehe={560}
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
          <Gebietskarte
            flaechen={bezirkeImFokus}
            werte={zaehlt ? werteBezirke : undefined}
            gewaehlt={gewaehlt}
            onWaehlen={(nr) => setGewaehlt((alt) => (alt === nr ? null : nr))}
            // Im Ausschnitt eines Wahlbereichs ist Platz für die Nummer —
            // auf der ganzen Stadt wäre sie ein Knäuel.
            beschriftung={typeof fokus === "number" ? (e) => String(e.nr) : undefined}
            schrift={12}
            hoehe={560}
            titel={(e) => {
              const z = bezirkeNachNr.get(e.nr);
              const p = z?.parties.find((x) => x.slug === partei.slug);
              // Der Name aus der Ergebnisdatei trägt die Nummer schon („101 Amt
              // für …"); nur die Geometrie kennt sie ohne.
              const kopf = `${z?.name ?? `${e.nr} ${e.name}`} · Wahlbereich ${roemisch(e.wb)}`;
              if (!z?.counted) return `${kopf} — noch nicht ausgezählt`;
              return `${kopf} — ${partei.short} ${prozent(p?.share_pct)}, ${zahl(p?.votes)} von ${zahl(z.totals.valid_votes)}`;
            }}
            hinweis={abfrage.isPending
              ? "Wahlbezirke werden geladen …"
              : `${bezirkeImFokus.length} Wahlbezirke${typeof fokus === "number" ? "" : ` · ${brief} Briefwahlbezirke haben keine Fläche`}`}
          />
        )}
        {inBezirken && gewaehlterBezirk ? (
          <Bezirkstafel zeile={gewaehlterBezirk} daten={daten} schliessen={() => setGewaehlt(null)} />
        ) : null}
      </div>

      {/* Die Briefwahl steht als Zeile da, wo die Karte sie nicht zeigen
          kann — mit derselben Zahl, die auch die Flächen tragen. */}
      {inBezirken && abfrage.data && zaehlt ? (
        <p className="mt-3 text-[12px] text-muted-foreground">
          Briefwahl: {partei.short}{" "}
          {prozent(anteilBriefwahl(abfrage.data, partei.slug, typeof fokus === "number" ? fokus : null))}
          {typeof fokus === "number" ? ` in den Briefwahlbezirken von Wahlbereich ${roemisch(fokus)}` : ` über alle ${brief} Briefwahlbezirke`}.
        </p>
      ) : null}
    </section>
  );
}

/** Der Anteil einer Liste über die Briefwahlbezirke — eine Zahl, weil die
 *  einzelnen Briefwahlbezirke niemandem etwas sagen. Mit `bereich` nur die
 *  eines Wahlbereichs. */
function anteilBriefwahl(daten: Wahlbezirke, slug: string, bereich: number | null): number | null {
  let stimmen = 0;
  let gueltig = 0;
  for (const z of daten.districts) {
    if (!z.postal || !z.counted) continue;
    if (bereich !== null && z.area !== bereich) continue;
    gueltig += z.totals.valid_votes ?? 0;
    stimmen += z.parties.find((p) => p.slug === slug)?.votes ?? 0;
  }
  return gueltig ? Math.round((1000 * stimmen) / gueltig) / 10 : null;
}
