"use client";

/**
 * Der Mehrheitsrechner (`/werkzeuge/mehrheiten`): Mit welchen Fraktionen und
 * Gruppen reicht es — im Rat und in jedem Ausschuss?
 *
 * Wunsch aus dem Rat, für alle Ratsmitglieder gebaut (Tim, 22.11.2026). Die
 * Auswahl ist neutral: Jede Fraktion lässt sich gleich auf „dabei“ oder
 * „ohne“ setzen, die Kombinationen stehen ohne Wertung da.
 *
 * Gerechnet wird im Backend (`web/backend/app/majorities.py`) — Schwelle,
 * Auswahl, Kombinationen und die Übersicht über alle Gremien kommen fertig.
 * Hier steht nur die Darstellung. Die Auswahl lebt in der Adresse
 * (`lib/werkzeuge.ts`), damit sie sich teilen und neu laden lässt.
 *
 * **Bedienung und Wirkung bleiben beieinander.** Am breiten Schirm steht der
 * Sitzbogen links und bleibt beim Scrollen stehen, die Schalter liegen
 * daneben; schmal wandert ein Stimmen-Meter mit der Liste mit. Wer unten
 * „ohne“ setzt, sieht sofort, was es bewirkt.
 */
import { useId, useMemo, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { ArrowLeft, Check, ExternalLink, RotateCcw, X } from "lucide-react";

import { api } from "@/lib/api";
import type { ApiAntwort } from "@/lib/vertrag";
import { halbkreis } from "@/lib/wahlabend";
import { KOPFLEISTE_HOEHE } from "@/lib/tableiste";
import { cn, formatDate } from "@/lib/utils";
import {
  auswahlAus, auswahlQuery, aufzaehlung, reihenFuer, sitzReihenfolge, uebernehmen, umschalten,
  wahlVon, type Auswahl, type Wahl,
} from "@/lib/werkzeuge";
import { Card, DetailSkeleton, EmptyState, ErrorState, PageHeader, Select } from "@/components/ui";
import { Punkt } from "@/components/wahlabend/bausteine";
import { ShareButton } from "@/components/share-button";

type Rechner = ApiAntwort<"/tools/majorities">;
type Block = Rechner["blocks"][number];
type Kombination = Rechner["coalitions"][number];
type Zeile = Rechner["overview"][number];

/** So viele Kombinationen stehen sofort da; der Rest auf Knopfdruck. */
const ERSTE = 12;

const stimmen = (n: number) => `${n.toLocaleString("de-DE")} ${n === 1 ? "Stimme" : "Stimmen"}`;
const fehlen = (n: number) => (n === 1 ? "1 fehlt" : `${n} fehlen`);

function useRechner(a: Auswahl) {
  const q = new URLSearchParams();
  if (a.gremium) q.set("body", a.gremium);
  if (a.dabei.length) q.set("include", a.dabei.join(","));
  if (a.ohne.length) q.set("exclude", a.ohne.join(","));
  const query = q.toString();
  return useQuery({
    queryKey: ["mehrheiten", query],
    queryFn: () => api.get<Rechner>(`/tools/majorities${query ? `?${query}` : ""}`),
    // Beim Umschalten bleibt der alte Stand stehen, bis der neue da ist —
    // sonst blinkte der ganze Bogen bei jedem Klick weg.
    placeholderData: keepPreviousData,
    staleTime: 5 * 60 * 1000,
  });
}

export function Mehrheitsrechner() {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const auswahl = useMemo(() => auswahlAus(new URLSearchParams(params.toString())), [params]);
  const { data, isPending, isError, refetch, isFetching } = useRechner(auswahl);
  // Vorschau einer Kombination unter dem Zeiger oder Fokus — nur Darstellung.
  const [vorschau, setVorschau] = useState<readonly string[] | null>(null);

  const setzen = (a: Auswahl) => {
    setVorschau(null);
    const q = auswahlQuery(a);
    router.replace(q ? `${pathname}?${q}` : pathname, { scroll: false });
  };

  if (isPending) return <DetailSkeleton />;
  if (isError || !data) {
    return <ErrorState onRetry={() => void refetch()} busy={isFetching} />;
  }

  const query = auswahlQuery(auswahl);
  const kopf = (
    <div>
      <Link
        href="/werkzeuge"
        className="mb-2 inline-flex items-center gap-1 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4" aria-hidden />
        Werkzeuge
      </Link>
      <PageHeader
        title="Mehrheitsrechner"
        description="Welche Fraktionen und Gruppen zusammen eine Mehrheit haben — im Rat und in jedem Ausschuss."
      />
    </div>
  );
  const body = data.body;
  if (!body) {
    return (
      <div className="space-y-6">
        {kopf}
        <EmptyState
          title="Die Besetzung der Gremien ist noch nicht geladen"
          hint="Sie kommt aus dem Ratsinformationssystem und wird einmal in der Woche abgerufen."
        />
      </div>
    );
  }

  const namen = new Map(data.blocks.map((b) => [b.key, b.short]));
  const sel = data.selection;
  const vorn = vorschau ?? sel.include;
  const gewaehlt = auswahl.dabei.length + auswahl.ohne.length > 0;
  const gremium = (key: string) => setzen({ ...auswahl, gremium: key === data.bodies[0]?.key ? null : key });

  return (
    <div className="space-y-6">
      {kopf}

      <div className="flex flex-wrap items-end gap-x-4 gap-y-2">
        <label className="w-full min-w-0 sm:w-auto sm:max-w-md sm:flex-1">
          <span className="mb-1 block font-mono text-[11px] font-medium uppercase tracking-[0.08em] text-muted-foreground">
            Gremium
          </span>
          <Select value={body.key} onChange={(e) => gremium(e.target.value)}>
            {data.bodies.map((b) => (
              <option key={b.key} value={b.key}>
                {b.short} · {stimmen(b.votes)}
              </option>
            ))}
          </Select>
        </label>
        <div className="flex h-10 items-center gap-4">
          {gewaehlt && (
            <button
              type="button"
              onClick={() => setzen({ ...auswahl, dabei: [], ohne: [] })}
              className="inline-flex items-center gap-1 text-sm text-muted-foreground transition-colors hover:text-primary"
            >
              <RotateCcw className="h-3.5 w-3.5" aria-hidden />
              Zurücksetzen
            </button>
          )}
          <ShareButton
            still
            label="Auswahl teilen"
            path={query ? `${pathname}?${query}` : pathname}
            title="Mehrheitsrechner"
            hinweis="Der Link öffnet den Rechner mit dieser Auswahl — für Konten mit der Rolle Ratsmitglied."
          />
        </div>
      </div>

      <div className="@container">
        <div className="grid gap-6 @4xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          {/* Links der Bogen: am breiten Schirm bleibt er beim Scrollen stehen. */}
          <div className="min-w-0 @4xl:sticky @4xl:top-6 @4xl:self-start">
            <Card className="p-4 sm:p-5">
              <Sitzbogen
                blocks={data.blocks}
                votes={body.votes}
                majority={body.majority}
                vorn={vorn}
                hinten={sel.exclude}
                titel={body.name}
              />
              <Stand sel={sel} namen={namen} votes={body.votes} majority={body.majority} />
              {data.partners.length > 0 && (
                <Vorschlaege
                  partners={data.partners}
                  blocks={data.blocks}
                  onVorschau={(key) => setVorschau(key ? [...sel.include, key] : null)}
                  onDazu={(key) => setzen(umschalten(auswahl, key, "dabei"))}
                />
              )}
              {(body.notes.length > 0 || data.advisory.length > 0) && (
                <div className="mt-3 space-y-1.5 border-t border-border/70 pt-3">
                  {body.notes.map((n) => (
                    <p key={n} className="text-hinweis text-muted-foreground">{n}</p>
                  ))}
                  {data.advisory.length > 0 && (
                    <p className="text-hinweis text-muted-foreground">
                      Beratend, ohne Stimme:{" "}
                      {data.advisory.map((m, i) => (
                        <span key={`${m.name}-${i}`}>
                          {i > 0 && ", "}
                          <span className="whitespace-nowrap">
                            {m.short && <Punkt color={m.color} dark={m.color_dark} className="mr-1 align-middle" />}
                            {m.short ?? m.role}
                          </span>{" "}
                          ({m.name})
                        </span>
                      ))}
                    </p>
                  )}
                </div>
              )}
            </Card>
          </div>

          <div className="flex min-w-0 flex-col gap-6">
            <Card className="p-4 sm:p-5">
              {/* Schmal wandert das Meter mit der Liste mit: Der Bogen steht
                  dann oberhalb, außer Sicht. */}
              <div
                className="sticky top-[var(--kopf)] -mx-4 -mt-1 bg-card/95 px-4 pb-2 pt-1 backdrop-blur-sm desk:top-0 sm:-mx-5 sm:px-5 @4xl:static @4xl:bg-transparent @4xl:backdrop-blur-none"
                style={{ "--kopf": KOPFLEISTE_HOEHE } as React.CSSProperties}
              >
                <h2 className="font-display text-[15px] font-bold text-foreground">Fraktionen und Gruppen</h2>
                <div className="mt-1.5 flex items-center gap-3">
                  <Meter seats={sel.seats} votes={body.votes} majority={body.majority} className="flex-1" />
                  <span className="shrink-0 text-[12.5px] tabular-nums text-muted-foreground">
                    {sel.include.length
                      ? <><strong className="font-semibold text-foreground">{sel.seats}</strong> von {body.votes} · {sel.has_majority ? "Mehrheit" : fehlen(sel.missing)}</>
                      : <>Mehrheit ab {body.majority}</>}
                  </span>
                </div>
              </div>
              <ul className="mt-1 divide-y divide-border/70">
                {data.blocks.map((b) => (
                  <BlockZeile
                    key={b.key}
                    b={b}
                    rat={body.kind === "council"}
                    wahl={wahlVon(auswahl, b.key)}
                    reicht={data.partners.some((x) => x.key === b.key && x.completes)}
                    onWahl={(w) => setzen(umschalten(auswahl, b.key, w))}
                  />
                ))}
              </ul>
            </Card>

            <Card className="p-4 sm:p-5">
              <Kombinationen
                key={`${body.key}|${query}`}
                data={data}
                namen={namen}
                onVorschau={setVorschau}
                onWaehlen={(k) => setzen(uebernehmen(auswahl, k.blocks))}
              />
            </Card>
          </div>
        </div>
      </div>

      {/* Volle Breite, zweispaltig: Sechzehn Zeilen neben dem Bogen ließen
          links ein Loch, so lang wie die Liste. */}
      <Card className="@container p-4 sm:p-5">
        <Gremien
          zeilen={data.overview}
          aktuell={body.key}
          dabei={aufzaehlung(sel.include.map((k) => namen.get(k) ?? k))}
          mehrere={sel.include.length > 1}
          onGremium={gremium}
        />
      </Card>

      <p className="text-meta text-muted-foreground">
        Besetzung laut Ratsinformationssystem der Stadt Oldenburg
        {data.as_of && <>, Stand {formatDate(data.as_of)}</>} ·{" "}
        <a
          href={body.source_url}
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-1 text-primary underline-offset-2 hover:underline"
        >
          {body.short} im Ratsinfo
          <ExternalLink className="h-3 w-3" aria-hidden />
        </a>
      </p>
    </div>
  );
}

/** Stimmen-Meter: Anteil der Auswahl an allen Stimmen, der Strich markiert
 *  die Mehrheit. Primärfarbe statt Parteifarben — es zeigt eine Summe, keine
 *  Partei (DESIGNSPRACHE § 2: Parteifarben nur als Punkte). */
function Meter({ seats, votes, majority, className }: { seats: number; votes: number; majority: number; className?: string }) {
  const anteil = votes ? Math.min(1, seats / votes) : 0;
  const strich = votes ? majority / votes : 0.5;
  return (
    <span aria-hidden className={cn("relative block h-1.5 rounded-full bg-muted", className)}>
      <span
        className="absolute inset-y-0 left-0 rounded-full bg-primary transition-[width] duration-fluss"
        style={{ width: `${anteil * 100}%` }}
      />
      <span className="absolute -inset-y-1 w-0.5 rounded-full bg-signal" style={{ left: `calc(${strich * 100}% - 1px)` }} />
    </span>
  );
}

/** Ein Sitz je Punkt, die Mittellinie markiert die Hälfte. Was dabei ist,
 *  sitzt links und in Farbe; was ausgeschlossen ist, rechts und hohl. Der
 *  Zeiger auf einem Sitz nennt, wer dort sitzt. */
function Sitzbogen({
  blocks, votes, majority, vorn, hinten, titel,
}: {
  blocks: readonly Block[];
  votes: number;
  majority: number;
  vorn: readonly string[];
  hinten: readonly string[];
  titel: string;
}) {
  const id = useId();
  const reihen = reihenFuer(votes);
  const innen = reihen === 1 ? 1 : reihen === 2 ? 0.62 : 0.48;
  // Gedeckelt: Bei elf Sitzen in einem Bogen würde jeder Punkt so groß, dass
  // er über den Rand der Grafik ragt.
  const plaetze = halbkreis(votes, reihen, innen).map((q) => ({ ...q, r: Math.min(q.r, 0.072) }));
  // Die Mittellinie reicht bis knapp unter den innersten Bogen — darunter
  // steht die Zahl.
  const linieBis = 1 - innen + 0.1;
  const belegung: { b: Block; wer: string }[] = [];
  for (const b of sitzReihenfolge(blocks, vorn, hinten)) {
    const namen = b.members.length ? b.members : b.functions.flatMap((f) => Array<string>(f.seats).fill(f.label));
    for (let i = 0; i < b.seats; i++) belegung.push({ b, wer: namen[i] ?? b.label });
  }
  const aktiv = vorn.length > 0;
  const dabei = blocks.filter((b) => vorn.includes(b.key)).reduce((s, b) => s + b.seats, 0);
  const reicht = dabei >= majority;

  return (
    <figure>
      <figcaption className="flex items-baseline justify-between gap-3">
        <span className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
          {titel} · {votes} Stimmen
        </span>
        <span className="shrink-0 font-mono text-[10px] text-muted-foreground">Mehrheit ab {majority}</span>
      </figcaption>
      <svg viewBox="-0.08 -0.1 2.16 1.22" className="mx-auto mt-2 block w-full max-w-[520px]" role="img" aria-labelledby={`${id}-t`}>
        <title id={`${id}-t`}>
          {titel}: {blocks.map((b) => `${b.short} ${b.seats}`).join(", ")}. Mehrheit ab {majority} von {votes} Stimmen.
        </title>
        <line x1="1" y1="-0.08" x2="1" y2={linieBis} className="stroke-signal" strokeWidth="0.008" strokeDasharray="0.03 0.02" />
        {plaetze.map((q, i) => {
          const sitz = belegung[i];
          if (!sitz) return null;
          const { b, wer } = sitz;
          const aus = hinten.includes(b.key);
          const zurueck = aktiv && !vorn.includes(b.key);
          return (
            <circle
              key={i}
              cx={q.x}
              cy={q.y}
              r={aus ? q.r * 0.82 : q.r}
              strokeWidth={aus ? q.r * 0.36 : 0}
              className={cn(
                "transition-[opacity] duration-fluss",
                aus
                  ? "fill-none stroke-[var(--dot)] opacity-45 dark:stroke-[var(--dot-dark)]"
                  : "fill-[var(--dot)] dark:fill-[var(--dot-dark)]",
                !aus && zurueck && "opacity-20",
              )}
              style={{ "--dot": b.color, "--dot-dark": b.color_dark } as React.CSSProperties}
            >
              <title>{wer === b.label || b.kind === "external" ? wer : `${wer} · ${b.short}`}</title>
            </circle>
          );
        })}
        <text x="1" y="0.9" textAnchor="middle" className="fill-foreground font-display tabular-nums" fontSize="0.24" fontWeight={700}>
          {aktiv ? dabei : votes}
        </text>
        <text x="1" y="1.03" textAnchor="middle" className={cn("tabular-nums", aktiv && reicht ? "fill-primary" : "fill-muted-foreground")} fontSize="0.07">
          {aktiv ? `von ${votes} · ${reicht ? "Mehrheit" : fehlen(majority - dabei)}` : "Stimmen"}
        </text>
      </svg>
    </figure>
  );
}

/** Die Ablesezeile unter dem Bogen — nie leer, und sie sagt, was die Auswahl hergibt. */
function Stand({
  sel, namen, votes, majority,
}: {
  sel: Rechner["selection"];
  namen: Map<string, string>;
  votes: number;
  majority: number;
}) {
  const dabei = aufzaehlung(sel.include.map((k) => namen.get(k) ?? k));
  const ohne = aufzaehlung(sel.exclude.map((k) => namen.get(k) ?? k));
  let satz: React.ReactNode;
  if (!sel.possible) {
    satz = <>Ohne {ohne} kommen höchstens {sel.max_seats} von {votes} Stimmen zusammen — für eine Mehrheit braucht es {majority}.</>;
  } else if (!sel.include.length) {
    satz = <>Mehrheit ab {majority} von {votes} Stimmen. Setze Fraktionen auf „dabei“ — oder übernimm eine der möglichen Mehrheiten.</>;
  } else if (sel.has_majority) {
    const ueber = sel.seats - majority;
    satz = (
      <>
        <strong className="font-semibold">{dabei}</strong> {sel.include.length > 1 ? "kommen" : "kommt"} auf{" "}
        {sel.seats} von {votes} Stimmen — {ueber === 0 ? "genau die Mehrheit" : `${ueber} mehr als nötig`}.
      </>
    );
  } else {
    satz = (
      <>
        <strong className="font-semibold">{dabei}</strong>: {sel.seats} von {votes} Stimmen — es{" "}
        {sel.missing === 1 ? "fehlt eine" : `fehlen ${sel.missing}`} bis zur Mehrheit.
      </>
    );
  }
  return (
    <p className="mt-2 text-center text-[14px] leading-relaxed text-foreground" aria-live="polite">
      {satz}
    </p>
  );
}

/**
 * Wer für die Mehrheit in Frage kommt (Tims Wunsch 22.11.2026): sobald etwas
 * auf „dabei“ steht und noch Stimmen fehlen. Zwei Gruppen — wer die Lücke
 * allein schließt, und wer es nur zusammen mit anderen tut. Welche das sind,
 * rechnet der Server (`partners`); ein Klick setzt den Block auf „dabei“.
 */
function Vorschlaege({
  partners, blocks, onVorschau, onDazu,
}: {
  partners: Rechner["partners"];
  blocks: readonly Block[];
  onVorschau: (key: string | null) => void;
  onDazu: (key: string) => void;
}) {
  const block = new Map(blocks.map((b) => [b.key, b]));
  const allein = partners.filter((x) => x.completes);
  const zusammen = partners.filter((x) => !x.completes);
  const reihe = (titel: string, liste: typeof partners) => liste.length > 0 && (
    <div className="flex flex-wrap items-center gap-x-1.5 gap-y-1.5">
      <span className="mr-0.5 text-[12.5px] text-muted-foreground">{titel}</span>
      {liste.map((x) => {
        const b = block.get(x.key);
        if (!b) return null;
        return (
          <button
            key={x.key}
            type="button"
            onMouseEnter={() => onVorschau(x.key)}
            onFocus={() => onVorschau(x.key)}
            onMouseLeave={() => onVorschau(null)}
            onBlur={() => onVorschau(null)}
            onClick={() => onDazu(x.key)}
            title={`${b.label} dazunehmen — zusammen ${x.total} Stimmen`}
            className={cn(
              "inline-flex h-8 items-center gap-1.5 rounded-full border bg-card px-2.5 text-[12.5px] font-medium text-foreground transition-colors duration-tipp hover:border-primary/40 hover:bg-primary/5",
              x.completes ? "border-border" : "border-dashed border-input",
            )}
          >
            <Punkt color={b.color} dark={b.color_dark} />
            {b.short}
            <span className="tabular-nums text-muted-foreground">+{x.seats}</span>
          </button>
        );
      })}
    </div>
  );
  return (
    <div className="mt-3 space-y-2 border-t border-border/70 pt-3" aria-label="Wer für die Mehrheit in Frage kommt">
      {reihe(allein.length === 1 ? "Für die Mehrheit reicht:" : "Für die Mehrheit reicht jeweils:", allein)}
      {reihe(allein.length ? "Nur zusammen mit anderen:" : "In Frage kommen, nur zu mehreren:", zusammen)}
    </div>
  );
}

function art(b: Block): string {
  switch (b.kind) {
    case "group":
      return b.parties.length ? `Gruppe aus ${aufzaehlung(b.parties)}` : "Gruppe";
    case "single":
      return b.label !== b.short ? `Einzelmitglied · ${b.label}` : "Einzelmitglied";
    case "mayor":
      return b.members[0]?.replace(/^Oberbürgermeister(in)?\s+/, "Oberbürgermeister · ") ?? "Oberbürgermeister";
    case "external":
      return b.functions.map((f) => (f.seats > 1 ? `${f.seats} ${f.label}` : f.label)).join(", ");
    default:
      return b.label !== b.short ? `Fraktion ${b.label}` : "Fraktion";
  }
}

function BlockZeile({
  b, rat, wahl, reicht, onWahl,
}: {
  b: Block;
  rat: boolean;
  wahl: Wahl | null;
  /** Mit diesem Block hätte die Auswahl die Mehrheit. */
  reicht: boolean;
  onWahl: (w: Wahl) => void;
}) {
  return (
    <li className="flex items-center gap-3 py-2.5">
      <Punkt color={b.color} dark={b.color_dark} className="h-2.5 w-2.5" />
      <div className="min-w-0 flex-1">
        <p className={cn("text-[14px] font-semibold leading-snug text-foreground", wahl === "ohne" && "text-muted-foreground line-through decoration-1")}>
          {b.kind === "external" ? b.label : b.short}{" "}
          <span className="font-normal tabular-nums text-muted-foreground no-underline">· {stimmen(b.seats)}</span>
        </p>
        <p className="text-xs leading-snug text-muted-foreground">
          {art(b)}
          {reicht && <span className="font-medium text-primary"> · damit reicht es</span>}
        </p>
        {/* Im Ausschuss sind die Namen die Auskunft; im Rat wären es dreizehn. */}
        {!rat && b.kind !== "mayor" && b.members.length > 0 && (
          <p className="mt-0.5 text-xs leading-snug text-muted-foreground">{b.members.join(", ")}</p>
        )}
      </div>
      {b.selectable ? (
        <div className="flex shrink-0 gap-1" role="group" aria-label={`${b.short}: dabei oder ohne`}>
          <WahlKnopf an={wahl === "dabei"} onClick={() => onWahl("dabei")} icon={Check} label="dabei" ton="dabei" />
          <WahlKnopf an={wahl === "ohne"} onClick={() => onWahl("ohne")} icon={X} label="ohne" ton="ohne" />
        </div>
      ) : (
        <span className="shrink-0 text-xs text-muted-foreground">zählt mit</span>
      )}
    </li>
  );
}

function WahlKnopf({
  an, onClick, icon: Icon, label, ton,
}: {
  an: boolean;
  onClick: () => void;
  icon: typeof Check;
  label: string;
  ton: "dabei" | "ohne";
}) {
  return (
    <button
      type="button"
      aria-pressed={an}
      onClick={onClick}
      className={cn(
        "inline-flex h-9 items-center gap-1 rounded-full border px-3 text-[12.5px] font-medium transition-colors duration-tipp",
        !an && "border-border bg-card text-muted-foreground hover:bg-accent hover:text-foreground",
        an && ton === "dabei" && "border-primary bg-primary text-primary-foreground",
        an && ton === "ohne" && "border-foreground bg-foreground text-background",
      )}
    >
      <Icon className="h-3.5 w-3.5" aria-hidden />
      {label}
    </button>
  );
}

/** „Zu zweit“, „Zu dritt“ … — die Gliederung der Kombinationen. */
const ZU = ["Allein", "Zu zweit", "Zu dritt", "Zu viert", "Zu fünft", "Zu sechst", "Zu siebt", "Zu acht"];

function Kombinationen({
  data, namen, onVorschau, onWaehlen,
}: {
  data: Rechner;
  namen: Map<string, string>;
  onVorschau: (k: readonly string[] | null) => void;
  onWaehlen: (k: Kombination) => void;
}) {
  const [alle, setAlle] = useState(false);
  const sel = data.selection;
  const liste = alle ? data.coalitions : data.coalitions.slice(0, ERSTE);
  const bloecke = new Map(data.blocks.map((b) => [b.key, b]));
  const dabei = aufzaehlung(sel.include.map((k) => namen.get(k) ?? k));
  const gruppen: { n: number; k: Kombination[] }[] = [];
  for (const k of liste) {
    const g = gruppen.at(-1);
    if (g && g.n === k.blocks.length) g.k.push(k);
    else gruppen.push({ n: k.blocks.length, k: [k] });
  }

  let einleitung: string;
  if (!sel.possible) einleitung = "Mit dieser Auswahl kommt keine Kombination auf eine Mehrheit.";
  else if (sel.has_majority) einleitung = `${dabei} ${sel.include.length > 1 ? "haben" : "hat"} schon eine Mehrheit.`;
  else if (sel.include.length) einleitung = `Mit wem ${dabei} auf eine Mehrheit ${sel.include.length > 1 ? "kommen" : "kommt"} — ohne Partner, die entbehrlich wären. Ein Klick übernimmt die Kombination.`;
  else einleitung = "Jede Kombination, aus der niemand wegfallen kann, ohne die Mehrheit zu verlieren. Ein Klick übernimmt sie.";

  return (
    <section aria-labelledby="kombinationen-titel">
      <h2 id="kombinationen-titel" className="font-display text-[15px] font-bold text-foreground">
        Mögliche Mehrheiten{" "}
        <span className="font-sans text-[13px] font-medium tabular-nums text-muted-foreground">{data.coalitions.length}</span>
      </h2>
      <p className="mt-0.5 text-[13px] text-muted-foreground">{einleitung}</p>
      <div className="-mx-2 mt-2" onMouseLeave={() => onVorschau(null)}>
        {gruppen.map((g) => (
          <div key={g.n} className="mt-2 first:mt-0">
            <p className="px-2 pb-0.5 pt-1 font-mono text-[10.5px] font-medium uppercase tracking-[0.08em] text-muted-foreground">
              {ZU[g.n - 1] ?? `${g.n} zusammen`}
            </p>
            <ul>
              {g.k.map((k) => (
                <li key={k.blocks.join("+")}>
                  <button
                    type="button"
                    onMouseEnter={() => onVorschau(k.blocks)}
                    onFocus={() => onVorschau(k.blocks)}
                    onBlur={() => onVorschau(null)}
                    onClick={() => onWaehlen(k)}
                    className="flex w-full items-center gap-3 rounded-lg px-2 py-2 text-left transition-colors duration-tipp hover:bg-accent focus-visible:bg-accent"
                  >
                    <span className="flex min-w-0 flex-1 flex-wrap items-center gap-x-1.5 gap-y-1 text-[14px]">
                      {k.blocks.map((key, i) => {
                        const b = bloecke.get(key);
                        const neu = k.added.includes(key);
                        return (
                          <span key={key} className="inline-flex items-center gap-1.5">
                            {i > 0 && <span className="text-muted-foreground" aria-hidden>+</span>}
                            {b && <Punkt color={b.color} dark={b.color_dark} />}
                            <span className={cn(neu || !sel.include.length ? "font-semibold text-foreground" : "text-muted-foreground")}>
                              {namen.get(key) ?? key}
                            </span>
                          </span>
                        );
                      })}
                    </span>
                    <span className="shrink-0 text-right tabular-nums">
                      <span className="text-[14px] font-semibold text-foreground">{k.seats}</span>
                      <span className="ml-1.5 inline-block w-12 text-xs text-muted-foreground">
                        {k.surplus === 0 ? "genau" : `+${k.surplus}`}
                      </span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
      {data.coalitions.length > ERSTE && (
        <button
          type="button"
          onClick={() => setAlle(!alle)}
          className="mt-2 text-sm font-medium text-primary underline-offset-2 hover:underline"
        >
          {alle ? "Weniger zeigen" : `Alle ${data.coalitions.length} zeigen`}
        </button>
      )}
    </section>
  );
}

/** Dieselbe Auswahl in jedem Gremium — die Frage „wo reicht es?“ auf einen
 *  Blick. Eine Zeile wechselt ins Gremium, die Auswahl bleibt. */
function Gremien({
  zeilen, aktuell, dabei, mehrere, onGremium,
}: {
  zeilen: readonly Zeile[];
  aktuell: string;
  dabei: string;
  mehrere: boolean;
  onGremium: (key: string) => void;
}) {
  const gewaehlt = dabei.length > 0;
  return (
    <section aria-labelledby="gremien-titel">
      <h2 id="gremien-titel" className="font-display text-[15px] font-bold text-foreground">In jedem Gremium</h2>
      <p className="mt-0.5 text-[13px] text-muted-foreground">
        {gewaehlt
          ? `Wo ${dabei} eine Mehrheit ${mehrere ? "haben" : "hat"} — ein Klick wechselt ins Gremium.`
          : "Setze Fraktionen auf „dabei“: Dann steht hier, in welchen Gremien es für sie reicht."}
      </p>
      <ul className="-mx-2 mt-2 @3xl:columns-2 @3xl:gap-x-8">
        {zeilen.map((z) => (
          <li key={z.key} className="break-inside-avoid">
            <button
              type="button"
              onClick={() => onGremium(z.key)}
              aria-current={z.key === aktuell ? "true" : undefined}
              className={cn(
                "flex w-full items-center gap-3 rounded-lg px-2 py-2 text-left transition-colors duration-tipp hover:bg-accent focus-visible:bg-accent",
                z.key === aktuell && "bg-primary/[0.06]",
              )}
            >
              <span className={cn("min-w-0 flex-1 text-[13.5px] leading-snug", z.key === aktuell ? "font-semibold text-foreground" : "text-foreground")}>
                {z.short}
              </span>
              <Meter seats={z.seats} votes={z.votes} majority={z.majority} className="hidden w-20 shrink-0 sm:block" />
              <span className="w-12 shrink-0 text-right text-[12.5px] tabular-nums text-muted-foreground">
                {gewaehlt ? `${z.seats}/${z.votes}` : z.votes}
              </span>
              <Lage z={z} gewaehlt={gewaehlt} />
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}

/** Punkt + Wort (DESIGNSPRACHE, Ergebnis in Listen): reicht, fehlt, geht nicht. */
function Lage({ z, gewaehlt }: { z: Zeile; gewaehlt: boolean }) {
  let punkt = "bg-muted-foreground/50";
  let wort = `ab ${z.majority}`;
  if (!z.possible) wort = "nicht möglich";
  else if (gewaehlt && z.has_majority) { punkt = "bg-[#22c55e]"; wort = "Mehrheit"; }
  else if (gewaehlt) { punkt = "bg-[#f59e0b]"; wort = fehlen(z.missing); }
  return (
    <span className="inline-flex w-[6.5rem] shrink-0 items-center gap-1.5 text-xs font-medium text-foreground">
      {(gewaehlt || !z.possible) && <span className={cn("h-[7px] w-[7px] shrink-0 rounded-full", punkt)} aria-hidden />}
      <span className={cn(!gewaehlt && z.possible && "font-normal text-muted-foreground")}>{wort}</span>
    </span>
  );
}
