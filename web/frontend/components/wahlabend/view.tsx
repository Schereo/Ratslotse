"use client";

// /wahlabend — der Wahlabend zur Ratswahl am 13.09.2026.
//
// Alles Gerechnete kommt vom Backend (`GET /api/wahlabend`): Sitze nach NKWG,
// Hochrechnung, Abstände. Diese Datei zeigt es nur — in der Reihenfolge, in
// der man am Wahlabend fragt: Wie weit ist die Auszählung? Wie stehen die
// Listen? Und dann für EINE Liste: Wer ist in welchem Wahlbereich drin, wer
// knapp dran? Die Seite fragt einmal je Minute nach, so lange cacht auch der
// Votemanager der Stadt.

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { BrandMark } from "@/components/brand";
import { Mascot } from "@/components/mascot";
import { WebThemeSwitch } from "@/components/web-theme-switch";
import { Halbkreis } from "@/components/wahlabend/halbkreis";
import { Mehrheiten } from "@/components/wahlabend/mehrheiten";
import { Verlauf } from "@/components/wahlabend/verlauf";
import { useFrisch, useTween } from "@/lib/use-tween";
import { api, apiUrl } from "@/lib/api";
import { useAppConfig, useFeature } from "@/lib/features";
import { cn } from "@/lib/utils";
import {
  LISTE_SPEICHER,
  abfragePfad,
  bildPfad,
  delta,
  fortschritt,
  kandidatenStatus,
  nachStimmen,
  prozent,
  sitzgrenze,
  standText,
  uhrzeit,
  zahl,
  type StatusTon,
  type Wahlabend,
  type WahlabendBereich,
  type WahlabendKandidat,
  type WahlabendPartei,
} from "@/lib/wahlabend";

const KICKER = "font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground";

const TON: Record<StatusTon, string> = {
  seated: "bg-emerald-50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300",
  shaky: "bg-amber-50 text-amber-800 dark:bg-amber-900/30 dark:text-amber-200",
  projected: "bg-primary/10 text-primary",
  close: "bg-amber-50 text-amber-800 dark:bg-amber-900/30 dark:text-amber-200",
  open: "bg-muted text-muted-foreground",
  out: "bg-muted text-muted-foreground",
  unknown: "border border-dashed border-border text-muted-foreground",
};

/* ── Kopf & Fuß ─────────────────────────────────────────────────────────── */

function Kopf() {
  return (
    <header className="sticky top-0 z-40 border-b border-border bg-card/95 backdrop-blur">
      <div className="mx-auto flex w-full max-w-7xl items-center justify-between gap-3 px-4 pb-3 pt-[calc(env(safe-area-inset-top)+0.75rem)] sm:px-6 lg:px-10">
        <div className="flex min-w-0 items-center gap-2.5">
          <Link href="/" className="flex flex-none items-center gap-2.5 rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
            <BrandMark className="h-[30px] w-[30px]" />
            <span className="font-display text-[17px] font-bold tracking-tight text-foreground">Ratslotse</span>
          </Link>
          <span className="truncate border-l border-border pl-2.5 text-[13px] text-muted-foreground">Wahlabend 2026</span>
        </div>
        <div className="flex flex-none items-center gap-3 sm:gap-4">
          <WebThemeSwitch />
          <Link href="/" className="hidden text-[13px] font-medium text-primary sm:inline">
            ← Zurück zu Ratslotse
          </Link>
        </div>
      </div>
    </header>
  );
}

function Fuss({ daten }: { daten: Wahlabend | undefined }) {
  return (
    <footer className="mt-10 border-t border-border pt-4 text-[12.5px] leading-relaxed text-muted-foreground">
      <p className="max-w-[76ch]">
        <strong className="font-semibold text-foreground">Quelle:</strong> Open-Data-Dateien des Votemanagers der Stadt
        Oldenburg, alle 60 Sekunden abgerufen. Datenlizenz Deutschland – Namensnennung – 2.0.
        {daten ? (
          <>
            {" "}
            <a href={daten.election.presentation_url} className="font-medium text-primary" target="_blank" rel="noopener noreferrer">
              Zur amtlichen Ergebnispräsentation
            </a>
          </>
        ) : null}
      </p>
      <p className="mt-2 max-w-[76ch]">
        <strong className="font-semibold text-foreground">Unsere Rechnung:</strong> Die Sitze folgen dem Verfahren des
        Niedersächsischen Kommunalwahlgesetzes (§§ 36, 37 — dreimal Hare/Niemeyer: Listen, Wahlbereiche, dann Listen-
        gegen Personensitze). Gegen das amtliche Ergebnis von 2021 geprüft, alle 50 Mandate. Die Hochrechnung setzt für
        jeden offenen Wahlbezirk sein Ergebnis von 2021 an, skaliert mit dem Trend der schon ausgezählten Bezirke im
        selben Wahlbereich. Kein amtliches Ergebnis — das stellt der Wahlausschuss fest.
      </p>
    </footer>
  );
}

/* ── Zustände ohne Zahlen ───────────────────────────────────────────────── */

function Hinweisbild({ pose, titel, text }: { pose: "sleep" | "wave" | "confused"; titel: string; text: string }) {
  return (
    <div className="mx-auto mt-16 flex max-w-md flex-col items-center text-center">
      <Mascot pose={pose} className="h-28 w-28" decorative />
      <h1 className="mt-4 font-display text-[22px] font-bold tracking-tight">{titel}</h1>
      <p className="mt-2 text-[14px] leading-relaxed text-muted-foreground">{text}</p>
    </div>
  );
}

/* ── Anzeigetafel ───────────────────────────────────────────────────────── */

function Tafel({ daten, aktualisiert, probe, counted }: { daten: Wahlabend; aktualisiert: number; probe: string | null; counted: string | null }) {
  const p = daten.progress;
  const beteiligung = useTween(daten.totals.turnout_pct);
  const gueltig = useTween(daten.totals.valid_votes);
  const bild = apiUrl(bildPfad(daten.phase === "counting" ? "projected_seats" : "seats", probe, counted));
  const anteil = fortschritt(p.districts_counted, p.districts_total);
  const stand = standText(daten.source.last_modified ? new Date(daten.source.last_modified).toISOString() : daten.source.fetched_at);
  const phase =
    daten.phase === "before"
      ? "Noch nichts ausgezählt"
      : daten.phase === "complete"
        ? "Alle Wahlbezirke ausgezählt"
        : `${zahl(p.districts_counted)} von ${zahl(p.districts_total)} Wahlbezirken ausgezählt`;
  return (
    <section className="hh-tafel mt-5 rounded-2xl p-5 sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-x-8 gap-y-5">
        <div className="min-w-0 flex-1">
          <p className={KICKER}>
            Ratswahl Oldenburg · 13. September 2026 · {daten.dataset === "probe" ? "Generalprobe" : "Live"}
          </p>
          <h1 className="mt-1 font-display text-[28px] font-bold leading-none tracking-tight sm:text-[32px]">Wahlabend</h1>
          <p className="mt-3 text-[14px] text-foreground">
            <strong className="font-semibold">{phase}</strong>
            {stand ? <span className="text-muted-foreground"> · Stand {stand}</span> : null}
          </p>
          <div className="mt-2 h-1.5 w-full max-w-md overflow-hidden rounded-full bg-foreground/10">
            <div className="h-full rounded-full bg-primary transition-[width] duration-weg" style={{ width: `${anteil}%` }} />
          </div>
          <p className="mt-2 text-[11.5px] text-muted-foreground">
            {daten.source.ok
              ? `Zuletzt abgefragt ${uhrzeit(new Date(aktualisiert).toISOString()) ?? "–"} Uhr · nächste Abfrage in einer Minute`
              : `Der Votemanager antwortet gerade nicht (${daten.source.error ?? "Fehler"}) — gezeigt wird der letzte Stand.`}
            {daten.phase !== "before" ? (
              <>
                {" · "}
                <a href={bild} target="_blank" rel="noopener noreferrer" className="font-medium text-primary">
                  Bild zum Teilen ↗
                </a>
              </>
            ) : null}
          </p>
        </div>
        <dl className="grid grid-cols-3 gap-x-6 gap-y-1 text-right">
          <div>
            <dt className={KICKER}>Wahlbeteiligung</dt>
            <dd className="font-display text-[24px] font-bold tabular-nums">{prozent(beteiligung)}</dd>
          </div>
          <div>
            <dt className={KICKER}>Gültige Stimmen</dt>
            <dd className="font-display text-[24px] font-bold tabular-nums">{zahl(gueltig === null ? null : Math.round(gueltig))}</dd>
          </div>
          <div>
            <dt className={KICKER}>Sitze</dt>
            <dd className="font-display text-[24px] font-bold tabular-nums">{daten.election.seats}</dd>
          </div>
        </dl>
      </div>
      {daten.notes.length ? (
        <ul className="mt-4 space-y-1 border-t border-border pt-3 text-[12.5px] text-foreground">
          {daten.notes.map((n) => (
            <li key={n}>{n}</li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}

/* ── Listen stadtweit ───────────────────────────────────────────────────── */

function Punkt({ color, dark, className }: { color: string; dark: string; className?: string }) {
  return (
    <span
      aria-hidden
      className={cn("inline-block h-2 w-2 flex-none rounded-full bg-[var(--dot)] ring-1 ring-inset ring-black/10 dark:bg-[var(--dot-dark)]", className)}
      style={{ "--dot": color, "--dot-dark": dark } as React.CSSProperties}
    />
  );
}

function ListenZeile({
  p,
  max,
  zaehlt,
  phase,
  aktiv,
  waehle,
}: {
  p: WahlabendPartei;
  max: number;
  zaehlt: boolean;
  phase: string;
  aktiv: boolean;
  waehle: (slug: string) => void;
}) {
  const anteil = useTween(p.share_pct);
  return (
    <li>
      <button
        type="button"
        onClick={() => waehle(p.slug)}
        aria-pressed={aktiv}
        className={cn(
          "grid w-full grid-cols-[minmax(0,7.5rem)_1fr_auto] items-center gap-x-3 rounded-lg px-2 py-1.5 text-left transition-colors duration-tipp hover:bg-primary/5 sm:grid-cols-[minmax(0,9rem)_1fr_auto_auto]",
          aktiv && "bg-primary/5",
        )}
      >
        <span className="flex min-w-0 items-center gap-2">
          <Punkt color={p.color} dark={p.color_dark} />
          <span className="truncate text-[13px] font-semibold">{p.short}</span>
        </span>
        <span className="flex items-center gap-2">
          <span className="h-2 flex-1 overflow-hidden rounded-full bg-foreground/10">
            <span
              className={cn("block h-full rounded-full transition-[width] duration-weg", aktiv ? "bg-primary" : "bg-foreground/40")}
              style={{ width: `${zaehlt ? (100 * (anteil ?? 0)) / max : 0}%` }}
            />
          </span>
          <span className="w-[4.2rem] text-right text-[13px] tabular-nums">{prozent(anteil)}</span>
        </span>
        <span className="hidden w-12 text-right font-mono text-[10.5px] text-signal sm:inline tabular-nums">
          {delta(p.share_pct, p.share_2021_pct) ?? ""}
        </span>
        <span className="text-right text-[12.5px] tabular-nums text-muted-foreground">
          {zaehlt ? (
            <>
              <strong className="font-semibold text-foreground">{p.seats ?? "–"}</strong>
              {phase === "counting" ? <> → {p.projected_seats ?? "–"}</> : null}
            </>
          ) : (
            "–"
          )}
          <span className="hidden sm:inline"> · 2021: {p.seats_2021 ?? 0}</span>
        </span>
      </button>
    </li>
  );
}

function ListenTafel({ daten, liste, waehle }: { daten: Wahlabend; liste: string | null; waehle: (slug: string) => void }) {
  const sortiert = nachStimmen(daten.parties);
  const max = Math.max(1, ...daten.parties.map((p) => p.share_pct ?? 0));
  const zaehlt = daten.phase !== "before";
  return (
    <section className="mt-6">
      <div className="flex items-baseline justify-between gap-3">
        <h2 className="font-display text-[16px] font-bold tracking-tight">Alle Listen stadtweit</h2>
        <span className={cn(KICKER, "hidden sm:inline")}>Anteil · Sitze Stand → Hochrechnung · 2021</span>
      </div>
      <ol className="mt-3 rounded-2xl border border-border bg-card p-2 shadow-[0_1px_2px_rgba(0,0,0,0.04)]">
        {sortiert.map((p) => (
          <ListenZeile key={p.slug} p={p} max={max} zaehlt={zaehlt} phase={daten.phase} aktiv={liste === p.slug} waehle={waehle} />
        ))}
      </ol>
      <p className="mt-2 text-[11.5px] text-muted-foreground">
        Antippen wählt die Liste für die Wahlbereiche unten. Der Abstand in Punkten vergleicht mit dem Ergebnis von 2021.
      </p>
    </section>
  );
}

function Sitzbild({ daten }: { daten: Wahlabend }) {
  if (daten.phase === "before") return null;
  const zwei = daten.phase === "counting";
  return (
    <section className={cn("mt-6 grid gap-4", zwei && "@3xl:grid-cols-2")}>
      <Halbkreis parteien={daten.parties} gesamt={daten.election.seats} feld="seats" titel="Stand" />
      {zwei ? <Halbkreis parteien={daten.parties} gesamt={daten.election.seats} feld="projected_seats" titel="Hochrechnung" /> : null}
    </section>
  );
}

/** Gewinne und Verluste gegenüber 2021 in Prozentpunkten — Deltas tragen
 *  Signal-Orange (Designsprache), Flächen bleiben neutral. */
function GewinneVerluste({ daten }: { daten: Wahlabend }) {
  if (daten.phase === "before") return null;
  const zeilen = daten.parties
    .filter((p) => p.share_pct !== null && p.share_2021_pct !== null)
    .map((p) => ({ p, d: (p.share_pct ?? 0) - (p.share_2021_pct ?? 0) }))
    .sort((a, b) => b.d - a.d);
  if (!zeilen.length) return null;
  const max = Math.max(0.5, ...zeilen.map((z) => Math.abs(z.d)));
  return (
    <section className="rounded-2xl border border-border bg-card p-4 shadow-[0_1px_2px_rgba(0,0,0,0.04)]">
      <div className="flex items-baseline justify-between gap-3">
        <h2 className="font-display text-[16px] font-bold tracking-tight">Gewinne und Verluste</h2>
        <span className={KICKER}>Punkte gegenüber 2021</span>
      </div>
      <ol className="mt-3 space-y-1.5">
        {zeilen.map(({ p, d }) => (
          <li key={p.slug} className="grid grid-cols-[minmax(0,5.5rem)_1fr_3.2rem] items-center gap-2 text-[12.5px]">
            <span className="flex min-w-0 items-center gap-1.5">
              <Punkt color={p.color} dark={p.color_dark} />
              <span className="truncate font-medium">{p.short}</span>
            </span>
            <span className="relative h-2.5">
              <span className="absolute inset-y-0 left-1/2 w-px bg-border" />
              <span
                className="gb-balken-auf absolute inset-y-0 rounded-sm bg-signal/80"
                style={
                  d >= 0
                    ? { left: "50%", width: `${(50 * d) / max}%` }
                    : { right: "50%", width: `${(50 * -d) / max}%` }
                }
              />
            </span>
            <span className="text-right font-mono text-[11px] tabular-nums text-signal">{delta(p.share_pct, p.share_2021_pct)}</span>
          </li>
        ))}
      </ol>
      <p className="mt-2 text-[11px] text-muted-foreground">Listen ohne Antritt 2021 fehlen hier; sie stehen oben mit „–".</p>
    </section>
  );
}

function MehrheitenBlock({ daten }: { daten: Wahlabend }) {
  const [feld, setFeld] = useState<"seats" | "projected_seats">("projected_seats");
  if (daten.phase === "before") return null;
  const zaehlt = daten.phase === "counting";
  const aktiv = zaehlt ? feld : "seats";
  return (
    <section className="mt-6 grid items-start gap-4 @3xl:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)] @container">
      <div>
        {zaehlt ? (
          <div className="mb-2 inline-flex rounded-full border border-border bg-card p-0.5 text-[12px]">
            {(["projected_seats", "seats"] as const).map((f) => (
              <button
                key={f}
                type="button"
                aria-pressed={aktiv === f}
                onClick={() => setFeld(f)}
                className={cn("rounded-full px-3 py-1 transition-colors duration-tipp", aktiv === f ? "bg-primary text-primary-foreground" : "text-muted-foreground")}
              >
                {f === "seats" ? "Stand" : "Hochrechnung"}
              </button>
            ))}
          </div>
        ) : null}
        <Mehrheiten parteien={daten.parties} gesamt={daten.election.seats} feld={aktiv} hochrechnung={aktiv === "projected_seats"} />
      </div>
      <GewinneVerluste daten={daten} />
    </section>
  );
}

/* ── Liste wählen ───────────────────────────────────────────────────────── */

function ListenWahl({ parteien, liste, waehle }: { parteien: readonly WahlabendPartei[]; liste: string | null; waehle: (slug: string) => void }) {
  return (
    <section className="mt-8">
      <h2 className="font-display text-[16px] font-bold tracking-tight">Eine Liste, sechs Wahlbereiche</h2>
      <p className="mt-1 text-[13px] text-muted-foreground">
        Wähle eine Liste — dann siehst du je Wahlbereich ihre Kandidat*innen, die Personenstimmen und wer nach dem
        Zuteilungsverfahren gerade drin wäre.
      </p>
      <div className="mt-3 flex flex-wrap gap-1.5">
        {parteien.map((p) => (
          <button
            key={p.slug}
            type="button"
            onClick={() => waehle(p.slug)}
            aria-pressed={liste === p.slug}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-[12.5px] font-medium transition-colors duration-tipp",
              liste === p.slug ? "border-primary/30 bg-primary/5 text-primary" : "border-border bg-card text-foreground hover:bg-primary/5",
            )}
          >
            <Punkt color={p.color} dark={p.color_dark} />
            {p.short}
          </button>
        ))}
      </div>
    </section>
  );
}

/* ── Wahlbereiche ───────────────────────────────────────────────────────── */

/** Eine Kandidatur im Rennen: Name, Status, Stimmen — und der Balken, der
 *  sie zur stärksten Person der Liste ins Verhältnis setzt. Die Marke ist
 *  die Sitzgrenze (schwächster Personensitz), wo es eine gibt. */
function KandidatZeile({
  k,
  max,
  grenze,
  rang,
  status,
  hochrechnung,
}: {
  k: WahlabendKandidat;
  max: number;
  grenze: number | null;
  rang: number;
  status: { ton: StatusTon; text: string };
  hochrechnung: boolean;
}) {
  const stimmen = useTween(k.votes);
  const breite = stimmen === null || max <= 0 ? 0 : Math.max(1.5, (100 * stimmen) / max);
  const drin = k.elected !== null;
  return (
    <li className="flex items-start gap-2.5 py-2">
      <span className="w-5 flex-none pt-0.5 font-mono text-[10.5px] text-muted-foreground tabular-nums">{k.position}</span>
      <span className="min-w-0 flex-1">
        <span className={cn("block truncate text-[13px]", drin ? "font-semibold" : "font-medium")}>{k.name}</span>
        <span className="block truncate text-[11.5px] text-muted-foreground">
          {[k.occupation, k.born ? `*${k.born}` : null].filter(Boolean).join(" · ")}
        </span>
        {k.votes !== null ? (
          <span aria-hidden className="relative mt-1.5 block h-1.5 w-full overflow-hidden rounded-full bg-foreground/10">
            <span
              className={cn("gb-balken-auf block h-full rounded-full transition-[width] duration-weg", drin ? "bg-primary" : "bg-foreground/35")}
              style={{ width: `${breite}%`, animationDelay: `${rang * 40}ms` }}
            />
            {grenze !== null && max > 0 ? (
              <span className="absolute inset-y-0 w-0.5 -translate-x-1/2 bg-signal" style={{ left: `${Math.min(100, (100 * grenze) / max)}%` }} />
            ) : null}
          </span>
        ) : null}
        <span className={cn("mt-1 inline-block rounded-full px-2 py-0.5 text-[10.5px] font-semibold", TON[status.ton])}>{status.text}</span>
      </span>
      <span className="flex-none text-right">
        <span className="block text-[13px] font-semibold tabular-nums">{zahl(stimmen === null ? null : Math.round(stimmen))}</span>
        {hochrechnung && k.projected_votes !== null ? (
          <span className="block text-[10.5px] text-muted-foreground tabular-nums">→ {zahl(k.projected_votes)}</span>
        ) : null}
      </span>
    </li>
  );
}

function BereichKarte({ bereich, slug, daten }: { bereich: WahlabendBereich; slug: string; daten: Wahlabend }) {
  const eintrag = bereich.parties.find((p) => p.slug === slug);
  const zaehlt = daten.phase !== "before" && bereich.districts_counted > 0;
  const frisch = useFrisch(bereich.districts_counted);
  const anteil = useTween(eintrag?.share_pct);
  const stimmen = useTween(eintrag?.votes);
  const max = Math.max(0, ...(eintrag?.candidates ?? []).map((k) => k.votes ?? 0));
  const grenze = eintrag ? sitzgrenze(eintrag.candidates) : null;
  return (
    <article
      className={cn(
        "flex flex-col rounded-2xl border border-border bg-card p-4 shadow-[0_1px_2px_rgba(0,0,0,0.04)] transition-shadow duration-buehne",
        frisch && "shadow-lifted ring-2 ring-primary/40",
      )}
    >
      <div className="flex items-baseline justify-between gap-3">
        <div>
          <p className={KICKER}>Wahlbereich {bereich.roman}</p>
          <h3 className="font-display text-[15px] font-bold tracking-tight">{bereich.name}</h3>
        </div>
        <span className="font-mono text-[10.5px] text-muted-foreground tabular-nums">
          {bereich.districts_counted}/{bereich.districts_total} Bezirke
        </span>
      </div>
      {eintrag ? (
        <>
          <dl className="mt-3 flex items-end gap-5">
            <div>
              <dt className={KICKER}>Anteil</dt>
              <dd className="font-display text-[22px] font-bold leading-none tabular-nums">{zaehlt ? prozent(anteil) : "–"}</dd>
            </div>
            <div>
              <dt className={KICKER}>Stimmen</dt>
              <dd className="font-display text-[22px] font-bold leading-none tabular-nums">{zaehlt ? zahl(stimmen === null ? null : Math.round(stimmen)) : "–"}</dd>
            </div>
            <div>
              <dt className={KICKER}>Sitze{daten.phase === "counting" ? " · Hochr." : ""}</dt>
              <dd className="font-display text-[22px] font-bold leading-none tabular-nums">
                {daten.phase === "before" ? "–" : (eintrag.seats ?? "–")}
                {daten.phase === "counting" ? <span className="text-muted-foreground"> → {eintrag.projected_seats ?? "–"}</span> : null}
              </dd>
            </div>
          </dl>
          <ol className="mt-4 divide-y divide-border/70 border-t border-border/70">
            {eintrag.candidates.map((k, i) => (
              <KandidatZeile
                key={k.position}
                k={k}
                max={max}
                grenze={grenze}
                rang={i}
                status={kandidatenStatus(k, daten.phase, daten.person_votes_available, bereich.districts_counted > 0)}
                hochrechnung={daten.phase === "counting"}
              />
            ))}
          </ol>
          {zaehlt ? (
            <p className="mt-2 text-[11px] text-muted-foreground">
              Liste {zahl(eintrag.list_votes)} · Personen {zahl(eintrag.candidate_votes)}
              {grenze !== null ? <> · Marke: Sitzgrenze bei {zahl(grenze)}</> : null}
            </p>
          ) : null}
        </>
      ) : (
        <p className="mt-3 text-[13px] text-muted-foreground">Diese Liste tritt im Wahlbereich {bereich.roman} nicht an.</p>
      )}
    </article>
  );
}

function Bereiche({ daten, liste }: { daten: Wahlabend; liste: string | null }) {
  if (!liste) return null;
  const partei = daten.parties.find((p) => p.slug === liste);
  if (!partei) return null;
  return (
    <section className="mt-5 @container">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h2 className="flex items-center gap-2 font-display text-[16px] font-bold tracking-tight">
          <Punkt color={partei.color} dark={partei.color_dark} />
          {partei.name}
        </h2>
        {daten.phase !== "before" ? (
          <p className="text-[12.5px] text-muted-foreground">
            stadtweit {prozent(partei.share_pct)} · {partei.seats ?? "–"} {partei.seats === 1 ? "Sitz" : "Sitze"}
            {partei.votes_to_next_seat !== null ? <> · {zahl(partei.votes_to_next_seat)} Stimmen bis zum nächsten Sitz</> : null}
            {partei.votes_to_lose_seat !== null ? <> · {zahl(partei.votes_to_lose_seat)} Stimmen Puffer auf dem letzten Sitz</> : null}
          </p>
        ) : null}
      </div>
      <div className="mt-3 grid gap-4 @3xl:grid-cols-2 @6xl:grid-cols-3">
        {daten.areas.map((b) => (
          <BereichKarte key={b.number} bereich={b} slug={liste} daten={daten} />
        ))}
      </div>
    </section>
  );
}

/* ── Alle Sitze ─────────────────────────────────────────────────────────── */

function Mandate({ daten }: { daten: Wahlabend }) {
  if (daten.phase === "before" || !daten.mandates.length) return null;
  const roman = new Map(daten.areas.map((a) => [a.number, a.roman]));
  const gruppen = daten.parties
    .map((p) => ({ p, sitze: daten.mandates.filter((m) => m.slug === p.slug) }))
    .filter((g) => g.sitze.length);
  return (
    <details className="mt-8 rounded-2xl border border-border bg-card p-4 shadow-[0_1px_2px_rgba(0,0,0,0.04)]">
      <summary className="cursor-pointer font-display text-[15px] font-bold tracking-tight">
        Alle {daten.mandates.length} Sitze nach aktuellem Stand
      </summary>
      <div className="mt-3 grid gap-4 @3xl:grid-cols-2">
        {gruppen.map(({ p, sitze }) => (
          <div key={p.slug}>
            <p className="flex items-center gap-2 text-[13px] font-semibold">
              <Punkt color={p.color} dark={p.color_dark} />
              {p.short} <span className="font-normal text-muted-foreground">· {sitze.length}</span>
            </p>
            <ul className="mt-1 space-y-0.5 text-[12.5px]">
              {sitze.map((m, i) => (
                <li key={i} className="flex justify-between gap-3">
                  <span className="truncate">{m.name ?? "Name folgt mit den Personenstimmen"}</span>
                  <span className="flex-none text-muted-foreground">
                    {roman.get(m.area)} · {m.kind === "direct" ? "direkt" : m.kind === "list" ? "Liste" : m.kind === "transfer" ? "Übergang" : "–"}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </details>
  );
}

/* ── Die Seite ──────────────────────────────────────────────────────────── */

export function WahlabendView() {
  const params = useSearchParams();
  const router = useRouter();
  const probe = params.get("probe");
  const counted = params.get("counted");
  const schalterAn = useFeature("wahlabend");
  const config = useAppConfig();

  const abfrage = useQuery({
    queryKey: ["wahlabend", probe, counted],
    queryFn: () => api.get<Wahlabend>(abfragePfad(probe, counted)),
    enabled: schalterAn,
    refetchInterval: 60_000,
    refetchOnWindowFocus: true,
    staleTime: 30_000,
  });

  const [liste, setListe] = useState<string | null>(null);
  useEffect(() => {
    const ausUrl = params.get("liste");
    if (ausUrl) {
      setListe(ausUrl);
      return;
    }
    try {
      setListe(window.localStorage.getItem(LISTE_SPEICHER));
    } catch {
      /* privates Fenster o. ä. — dann eben ohne Vorauswahl */
    }
  }, [params]);

  const waehle = useMemo(
    () => (slug: string) => {
      setListe(slug);
      try {
        window.localStorage.setItem(LISTE_SPEICHER, slug);
      } catch {
        /* s. o. */
      }
      const q = new URLSearchParams(params.toString());
      q.set("liste", slug);
      router.replace(`?${q.toString()}`, { scroll: false });
    },
    [params, router],
  );

  const daten = abfrage.data;
  let inhalt: React.ReactNode;
  if (config.isLoading) {
    inhalt = null;
  } else if (!schalterAn) {
    inhalt = (
      <Hinweisbild
        pose="sleep"
        titel="Der Wahlabend ist noch nicht freigeschaltet"
        text="Am 13. September 2026 ab 18 Uhr zeigt diese Seite den Auszählungsstand der Ratswahl Oldenburg — live, nachgerechnet, je Wahlbereich."
      />
    );
  } else if (abfrage.isError) {
    inhalt = (
      <Hinweisbild
        pose="confused"
        titel="Gerade keine Zahlen"
        text="Der Abruf ist fehlgeschlagen. Die Seite versucht es in einer Minute von selbst noch einmal."
      />
    );
  } else if (!daten) {
    inhalt = <p className="mt-10 text-center text-[13px] text-muted-foreground">Zahlen werden geladen …</p>;
  } else {
    inhalt = (
      <>
        {daten.dataset === "probe" ? (
          <p className="mt-5 rounded-xl border border-amber-200 bg-amber-50 px-4 py-2.5 text-[13px] text-amber-900 dark:border-amber-800 dark:bg-amber-900/30 dark:text-amber-100">
            <strong className="font-semibold">Generalprobe.</strong> Die Zahlen sind die der Ratswahl 2021, die Listen und Namen die
            von 2026. Nichts davon ist ein Ergebnis vom 13. September.
          </p>
        ) : null}
        <Tafel daten={daten} aktualisiert={abfrage.dataUpdatedAt} probe={probe} counted={counted} />
        {daten.phase === "before" && daten.dataset === "live" ? (
          <p className="mt-4 text-[13.5px] leading-relaxed text-muted-foreground">
            Die Wahllokale schließen um 18 Uhr. Die ersten Wahlbezirke melden erfahrungsgemäß gegen 20 Uhr; 2021 lag das
            vorläufige Ergebnis der Ratswahl am Montagmorgen vor. Die Seite aktualisiert sich von selbst.
          </p>
        ) : null}
        <ListenTafel daten={daten} liste={liste} waehle={waehle} />
        <Sitzbild daten={daten} />
        <MehrheitenBlock daten={daten} />
        <Verlauf daten={daten} liste={liste} />
        <ListenWahl parteien={daten.parties} liste={liste} waehle={waehle} />
        <Bereiche daten={daten} liste={liste} />
        <Mandate daten={daten} />
      </>
    );
  }

  return (
    <>
      <Kopf />
      <main className="mx-auto w-full max-w-7xl px-4 pb-16 sm:px-6 lg:px-10 @container">
        {inhalt}
        <Fuss daten={daten} />
      </main>
    </>
  );
}
