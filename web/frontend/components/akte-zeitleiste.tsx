"use client";

// <AkteZeitleiste> — der Verlauf eines Vorgangs unter der Antwort (Plan „Akte“,
// Schalter `akten-zeitleiste`).
//
// GEBAUT WIRD SIE IM BACKEND (council/akte_suche.py, zeitleiste_anzeige):
// Stationen, Gruppen, Abstände und Pausen kommen fertig formuliert an — hier
// wird nur dargestellt. Die App bekommt dasselbe Feld und baut nichts nach.
//
// Grammatik wie der Zeitstrahl RG-03 (DESIGNSPRACHE §5): Schiene, 10-px-Punkte,
// die jüngste protokollierte Station gefüllt mit Halo und „Aktueller Stand“.
// Gestrichelt heißt „nicht von uns / noch nicht“: angekündigte Termine (noch
// kein Ergebnis), Pressemitteilungen (extern) und eine Pause ab einem halben
// Jahr ohne neue Station — die ist selbst eine Aussage über den Vorgang.

import { useState, type CSSProperties } from "react";
import Link from "next/link";
import { ChevronDown, ChevronUp, ExternalLink } from "lucide-react";
import { OUTCOME_META } from "@/components/decision-ui";
import { decisionHref } from "@/lib/routes";
import type { DecisionOutcome } from "@/lib/types";
import { cn } from "@/lib/utils";

export type ZeitleistenMitglied = {
  date: string;
  committee: string | null;
  decision_id: number | null;
  title: string;
};

export type ZeitleistenStation = {
  date: string;
  date_end: string | null;
  kind: "decision" | "group" | "press" | "announced";
  outcome: DecisionOutcome | null;
  title: string;
  committee: string | null;
  detail: string | null;
  decision_id: number | null;
  url: string | null;
  members: ZeitleistenMitglied[];
  gap_days: number | null;
  gap_label: string | null;
  pause: boolean;
};

export type AkteZeitleisteDaten = {
  span: string;
  count: number;
  stations: ZeitleistenStation[];
};

/** So viele Stationen stehen offen; die früheren hinter einem Knopf. */
const SICHTBAR = 8;

/** Die Leiste geht chronologisch auf (`.zeitleiste-auf` in app/globals.css):
 *  jede Zeile — Station oder Abstand — eine Stufe später, ab der 16. gemeinsam. */
function stufe(zeile: number): CSSProperties {
  return { "--zl-i": Math.max(0, Math.min(zeile, 15)) } as CSSProperties;
}

/** „26.06.2023“ aus dem ISO-Datum — ohne `new Date`, das rutscht je nach
 *  Zeitzone auf den Vortag. */
function datum(iso: string): string {
  const [j, m, t] = iso.split("-");
  return t && m && j ? `${t}.${m}.${j}` : iso;
}

function Abstand({ station, zeile }: { station: ZeitleistenStation; zeile: number }) {
  if (!station.gap_label) return null;
  return (
    <li aria-hidden className="zeitleiste-auf flex gap-3" style={stufe(zeile)}>
      <div className="flex w-4 shrink-0 justify-center">
        <span style={stufe(zeile)} className={cn("zeitleiste-schiene h-7 w-0", station.pause
          ? "border-l-2 border-dashed border-muted-foreground/50"
          : "border-l-2 border-primary/25")} />
      </div>
      <p className={cn("self-center text-[12px] leading-none text-muted-foreground",
        station.pause && "italic")}>
        {station.pause ? `${station.gap_label} ohne neue Station` : station.gap_label}
      </p>
    </li>
  );
}

function Punkt({ station, stand }: { station: ZeitleistenStation; stand: boolean }) {
  return (
    <span className={cn(
      "mt-1 h-2.5 w-2.5 shrink-0 rounded-full border-2",
      stand ? "border-primary bg-primary shadow-[0_0_0_3px_hsl(var(--primary)/0.15)]"
        : station.kind === "announced" ? "border-dashed border-primary/70 bg-card"
        : station.kind === "press" ? "border-dashed border-muted-foreground/70 bg-card"
        : station.kind === "group" ? "border-muted-foreground/40 bg-muted"
        : "border-primary/45 bg-card",
    )} />
  );
}

function Titel({ station, idToNum, onJump }: {
  station: ZeitleistenStation; idToNum: Map<number, number>; onJump: (id: number) => void;
}) {
  const [offen, setOffen] = useState(false);
  const titelCls = "break-words text-quelle font-medium leading-snug";
  if (station.kind === "decision" && station.decision_id != null) {
    const n = idToNum.get(station.decision_id);
    return (
      <p className={titelCls}>
        <Link href={decisionHref(station.decision_id)} className="hover:text-primary hover:underline">
          {station.title}
        </Link>
        {n != null && (
          <button type="button" onClick={() => onJump(station.decision_id as number)}
            aria-label={`Quelle ${n} anzeigen`}
            className="ml-1.5 inline-flex h-4 min-w-4 -translate-y-[2px] items-center justify-center rounded bg-primary/10 px-1 align-baseline text-[10px] font-bold leading-none text-primary hover:bg-primary/20">
            {n}
          </button>
        )}
      </p>
    );
  }
  if (station.kind === "press" && station.url) {
    return (
      <p className={titelCls}>
        <a href={station.url} target="_blank" rel="noopener noreferrer"
          className="hover:text-primary hover:underline">
          {station.title}
          <ExternalLink className="ml-1 inline h-3 w-3 -translate-y-px text-muted-foreground" aria-hidden />
        </a>
      </p>
    );
  }
  if (station.kind === "group") {
    return (
      <div>
        <button type="button" onClick={() => setOffen((o) => !o)} aria-expanded={offen}
          className={cn(titelCls, "inline-flex items-center gap-1 text-left hover:text-primary")}>
          {station.title}
          {offen ? <ChevronUp className="h-3.5 w-3.5" aria-hidden /> : <ChevronDown className="h-3.5 w-3.5" aria-hidden />}
        </button>
        {offen && (
          <ul className="mt-1 space-y-0.5">
            {station.members.map((m) => (
              <li key={`${m.date}-${m.decision_id}`} className="text-meta">
                {m.decision_id != null ? (
                  <Link href={decisionHref(m.decision_id)} className="hover:text-primary hover:underline">
                    <span className="font-mono text-muted-foreground">{datum(m.date)}</span>{" "}
                    {m.committee}
                  </Link>
                ) : (
                  <span><span className="font-mono text-muted-foreground">{datum(m.date)}</span> {m.committee}</span>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
    );
  }
  return <p className={titelCls}>{station.title}</p>;
}

export function AkteZeitleiste({ daten, idToNum, onJump }: {
  daten: AkteZeitleisteDaten; idToNum: Map<number, number>; onJump: (id: number) => void;
}) {
  const [alle, setAlle] = useState(false);
  const stationen = daten.stations;
  if (stationen.length < 2) return null;
  const verborgen = alle ? 0 : Math.max(0, stationen.length - SICHTBAR);
  // „Aktueller Stand“ ist die jüngste Station mit Ergebnis oder Meldung —
  // ein angekündigter Termin ist noch keiner.
  let stand = -1;
  stationen.forEach((s, i) => { if (s.kind !== "announced") stand = i; });

  return (
    <section aria-label="Verlauf des Vorgangs" className="rounded-xl border border-border bg-card p-3.5">
      <div className="mb-2 flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5">
        <p className="font-mono text-[10px] uppercase tracking-[0.12em] text-muted-foreground">Verlauf</p>
        <p className="font-mono text-meta text-muted-foreground">
          {daten.span} · {daten.count} Stationen
        </p>
      </div>
      {verborgen > 0 && (
        <button type="button" onClick={() => setAlle(true)}
          className="mb-1 ml-7 inline-flex items-center gap-1 text-meta text-primary hover:underline">
          <ChevronUp className="h-3.5 w-3.5" aria-hidden />
          {verborgen === 1 ? "1 frühere Station zeigen" : `${verborgen} frühere Stationen zeigen`}
        </button>
      )}
      <ol className="flex flex-col">
        {stationen.slice(verborgen).flatMap((s, j) => {
          const i = verborgen + j;
          const istStand = i === stand;
          const bis = s.date_end && s.date_end !== s.date ? ` – ${datum(s.date_end)}` : "";
          const zeilen = [];
          if (i > 0) zeilen.push(<Abstand key={`a${i}`} station={s} zeile={2 * j - 1} />);
          zeilen.push(
            <li key={`s${i}`} className="zeitleiste-auf flex gap-3" style={stufe(2 * j)}>
              <div className="flex w-4 shrink-0 flex-col items-center">
                <Punkt station={s} stand={istStand} />
                {i < stationen.length - 1 && (
                  <span style={stufe(2 * j)} className="zeitleiste-schiene mt-1 w-0.5 flex-1 bg-primary/25" />
                )}
              </div>
              <div className={cn("min-w-0 flex-1", istStand && "rounded-[10px] bg-primary/[0.06] p-2")}>
                {istStand && (
                  <p className="font-mono text-[9px] font-bold uppercase tracking-[0.14em] text-primary">Aktueller Stand</p>
                )}
                {s.kind === "announced" && (
                  <p className="font-mono text-[9px] font-bold uppercase tracking-[0.14em] text-primary">Angekündigt</p>
                )}
                <p className="flex flex-wrap items-center gap-x-2 gap-y-0.5">
                  <span className="font-mono text-meta text-muted-foreground">
                    {datum(s.date)}{bis}{s.kind !== "group" && s.committee ? ` · ${s.committee}` : ""}
                  </span>
                  {s.kind === "decision" && s.outcome && OUTCOME_META[s.outcome] && (
                    <span className={cn("rounded-full px-2 py-px text-[10.5px] font-semibold", OUTCOME_META[s.outcome].cls)}>
                      {OUTCOME_META[s.outcome].label}
                    </span>
                  )}
                </p>
                <Titel station={s} idToNum={idToNum} onJump={onJump} />
                {s.detail && <p className="mt-0.5 text-meta text-muted-foreground">{s.detail}</p>}
              </div>
            </li>,
          );
          return zeilen;
        })}
      </ol>
    </section>
  );
}
