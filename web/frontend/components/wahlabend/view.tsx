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
import { api } from "@/lib/api";
import { useAppConfig, useFeature } from "@/lib/features";
import { cn } from "@/lib/utils";
import {
  LISTE_SPEICHER,
  abfragePfad,
  delta,
  fortschritt,
  kandidatenStatus,
  nachStimmen,
  prozent,
  sitzband,
  standText,
  uhrzeit,
  zahl,
  type StatusTon,
  type Wahlabend,
  type WahlabendBereich,
  type WahlabendPartei,
} from "@/lib/wahlabend";

const KICKER = "font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground";

const TON: Record<StatusTon, string> = {
  seated: "bg-emerald-50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300",
  shaky: "bg-amber-50 text-amber-800 dark:bg-amber-900/30 dark:text-amber-200",
  projected: "bg-primary/8 text-primary",
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

function Tafel({ daten, aktualisiert }: { daten: Wahlabend; aktualisiert: number }) {
  const p = daten.progress;
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
          </p>
        </div>
        <dl className="grid grid-cols-3 gap-x-6 gap-y-1 text-right">
          <div>
            <dt className={KICKER}>Wahlbeteiligung</dt>
            <dd className="font-display text-[24px] font-bold tabular-nums">{prozent(daten.totals.turnout_pct)}</dd>
          </div>
          <div>
            <dt className={KICKER}>Gültige Stimmen</dt>
            <dd className="font-display text-[24px] font-bold tabular-nums">{zahl(daten.totals.valid_votes)}</dd>
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
          <li key={p.slug}>
            <button
              type="button"
              onClick={() => waehle(p.slug)}
              aria-pressed={liste === p.slug}
              className={cn(
                "grid w-full grid-cols-[minmax(0,7.5rem)_1fr_auto] items-center gap-x-3 rounded-lg px-2 py-1.5 text-left transition-colors duration-tipp hover:bg-primary/5 sm:grid-cols-[minmax(0,9rem)_1fr_auto_auto]",
                liste === p.slug && "bg-primary/5",
              )}
            >
              <span className="flex min-w-0 items-center gap-2">
                <Punkt color={p.color} dark={p.color_dark} />
                <span className="truncate text-[13px] font-semibold">{p.short}</span>
              </span>
              <span className="flex items-center gap-2">
                <span className="h-2 flex-1 overflow-hidden rounded-full bg-foreground/10">
                  <span
                    className={cn("block h-full rounded-full transition-[width] duration-weg", liste === p.slug ? "bg-primary" : "bg-foreground/40")}
                    style={{ width: `${zaehlt ? (100 * (p.share_pct ?? 0)) / max : 0}%` }}
                  />
                </span>
                <span className="w-[4.2rem] text-right text-[13px] tabular-nums">{prozent(p.share_pct)}</span>
              </span>
              <span className="hidden w-12 text-right font-mono text-[10.5px] text-signal sm:inline tabular-nums">
                {delta(p.share_pct, p.share_2021_pct) ?? ""}
              </span>
              <span className="text-right text-[12.5px] tabular-nums text-muted-foreground">
                {zaehlt ? (
                  <>
                    <strong className="font-semibold text-foreground">{p.seats ?? "–"}</strong>
                    {daten.phase === "counting" ? <> → {p.projected_seats ?? "–"}</> : null}
                  </>
                ) : (
                  "–"
                )}
                <span className="hidden sm:inline"> · 2021: {p.seats_2021 ?? 0}</span>
              </span>
            </button>
          </li>
        ))}
      </ol>
      <p className="mt-2 text-[11.5px] text-muted-foreground">
        Antippen wählt die Liste für die Wahlbereiche unten. Der Abstand in Punkten vergleicht mit dem Ergebnis von 2021.
      </p>
    </section>
  );
}

function Sitzband({ daten }: { daten: Wahlabend }) {
  if (daten.phase === "before") return null;
  const baender: { title: string; teile: ReturnType<typeof sitzband> }[] = [
    { title: "Stand", teile: sitzband(daten.parties, "seats") },
  ];
  if (daten.phase === "counting") baender.push({ title: "Hochrechnung", teile: sitzband(daten.parties, "projected_seats") });
  return (
    <section className="mt-6 grid gap-3 @3xl:grid-cols-2">
      {baender.map((b) => (
        <div key={b.title} className="rounded-2xl border border-border bg-card p-4 shadow-[0_1px_2px_rgba(0,0,0,0.04)]">
          <p className={KICKER}>
            {daten.election.seats} Sitze · {b.title}
          </p>
          <div className="mt-2 flex flex-wrap gap-x-4 gap-y-2">
            {b.teile.map((t) => (
              <span key={t.slug} className="flex items-center gap-1.5">
                <span className="flex flex-wrap gap-[3px]">
                  {Array.from({ length: t.n }, (_, i) => (
                    <Punkt key={i} color={t.color} dark={t.color_dark} />
                  ))}
                </span>
                <span className="text-[11.5px] text-muted-foreground">
                  {t.short} <strong className="font-semibold text-foreground">{t.n}</strong>
                </span>
              </span>
            ))}
          </div>
        </div>
      ))}
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

function BereichKarte({ bereich, slug, daten }: { bereich: WahlabendBereich; slug: string; daten: Wahlabend }) {
  const eintrag = bereich.parties.find((p) => p.slug === slug);
  const zaehlt = daten.phase !== "before" && bereich.districts_counted > 0;
  return (
    <article className="flex flex-col rounded-2xl border border-border bg-card p-4 shadow-[0_1px_2px_rgba(0,0,0,0.04)]">
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
              <dd className="font-display text-[22px] font-bold leading-none tabular-nums">{zaehlt ? prozent(eintrag.share_pct) : "–"}</dd>
            </div>
            <div>
              <dt className={KICKER}>Stimmen</dt>
              <dd className="font-display text-[22px] font-bold leading-none tabular-nums">{zaehlt ? zahl(eintrag.votes) : "–"}</dd>
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
            {eintrag.candidates.map((k) => {
              const s = kandidatenStatus(k, daten.phase, daten.person_votes_available, bereich.districts_counted > 0);
              return (
                <li key={k.position} className="flex items-start gap-2.5 py-2">
                  <span className="w-5 flex-none pt-0.5 font-mono text-[10.5px] text-muted-foreground tabular-nums">{k.position}</span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-[13px] font-medium">{k.name}</span>
                    <span className="block truncate text-[11.5px] text-muted-foreground">
                      {[k.occupation, k.born ? `*${k.born}` : null].filter(Boolean).join(" · ")}
                    </span>
                    <span className={cn("mt-1 inline-block rounded-full px-2 py-0.5 text-[10.5px] font-semibold", TON[s.ton])}>{s.text}</span>
                  </span>
                  <span className="flex-none text-right">
                    <span className="block text-[13px] font-semibold tabular-nums">{zahl(k.votes)}</span>
                    {daten.phase === "counting" && k.projected_votes !== null ? (
                      <span className="block text-[10.5px] text-muted-foreground tabular-nums">→ {zahl(k.projected_votes)}</span>
                    ) : null}
                  </span>
                </li>
              );
            })}
          </ol>
          {zaehlt ? (
            <p className="mt-2 text-[11px] text-muted-foreground">
              Liste {zahl(eintrag.list_votes)} · Personen {zahl(eintrag.candidate_votes)}
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
        <Tafel daten={daten} aktualisiert={abfrage.dataUpdatedAt} />
        {daten.phase === "before" && daten.dataset === "live" ? (
          <p className="mt-4 text-[13.5px] leading-relaxed text-muted-foreground">
            Die Wahllokale schließen um 18 Uhr. Die ersten Wahlbezirke melden erfahrungsgemäß gegen 20 Uhr; 2021 lag das
            vorläufige Ergebnis der Ratswahl am Montagmorgen vor. Die Seite aktualisiert sich von selbst.
          </p>
        ) : null}
        <ListenTafel daten={daten} liste={liste} waehle={waehle} />
        <Sitzband daten={daten} />
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
