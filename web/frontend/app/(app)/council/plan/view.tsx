"use client";

// Die Detailseite eines Plans (Schalter `plaene`, docs/plan-ziele-plaene.md § 3.2).
//
// Kopf, Laufzeit, Maßnahmen (wo es eine geprüfte Liste gibt), Berichte und
// Beschlüsse zum Plan. Kein leerer Platzhalter für das, was fehlt.
// Alles Rechnen steht in council/plan_pages.py; hier wird gezeichnet.

import { Suspense, useState, type CSSProperties } from "react";
import Link from "next/link";
import { notFound, useSearchParams } from "next/navigation";
import { ArrowLeft, ChevronDown, ChevronUp, ExternalLink } from "lucide-react";
import { DetailSkeleton } from "@/components/ui";
import { OutcomeDot } from "@/components/decision-ui";
import { Kicker, StatusAbzeichen } from "@/components/council-plaene";
import { AbrufFehler } from "@/components/abruf-fehler";
import { ShareButton } from "@/components/share-button";
import { useFetch } from "@/lib/use-fetch";
import { istNichtGefunden } from "@/lib/api";
import { useAppConfig, featureAktiv } from "@/lib/features";
import { decisionHref, planHref, plaeneHref } from "@/lib/routes";
import { useZurueck } from "@/lib/zurueck";
import { cn } from "@/lib/utils";
import {
  datum, gremien, stationsArt,
  type PlanBeschlussGruppe, type PlanDetail, type PlanStation,
} from "@/lib/plaene";

/** So viele Stationen stehen offen; die früheren hinter einem Knopf. */
const SICHTBAR = 8;

function Abschnitt({ kicker, rechts, children, className }: {
  kicker: string; rechts?: React.ReactNode; children: React.ReactNode; className?: string;
}) {
  return (
    <section className={cn("rounded-xl border border-border bg-card p-4 sm:p-5", className)}>
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5">
        <Kicker className="text-[11px] font-medium tracking-[0.1em]">{kicker}</Kicker>
        {rechts && <p className="font-mono text-meta text-muted-foreground">{rechts}</p>}
      </div>
      {children}
    </section>
  );
}

function Vorlage({ nummer, url, decisionId }: { nummer: string | null; url: string | null; decisionId: number | null }) {
  if (!nummer) return null;
  return (
    <span className="inline-flex flex-wrap items-center gap-x-2">
      {decisionId != null ? (
        <Link href={decisionHref(decisionId)} className="font-mono text-meta text-primary hover:underline">{nummer}</Link>
      ) : <span className="font-mono text-meta">{nummer}</span>}
      {url && (
        <a href={url} target="_blank" rel="noopener noreferrer"
          className="inline-flex items-center gap-0.5 text-meta text-muted-foreground hover:text-primary">
          Ratsinfo <ExternalLink className="h-3 w-3" aria-hidden />
        </a>
      )}
    </span>
  );
}

function Kopf({ d }: { d: PlanDetail }) {
  const a = d.adoption;
  return (
    <header className="mt-3">
      <Kicker>{d.kicker}</Kicker>
      <h1 className="mt-1.5 hyphens-auto break-words font-display text-2xl font-bold leading-tight text-foreground sm:text-[30px] sm:leading-[38px]">
        {d.title}
      </h1>
      <p className="mt-1 text-meta text-muted-foreground">
        {[d.office, d.kind_label, d.owner].filter(Boolean).join(" · ")}
      </p>
      <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-2">
        {a ? (
          <span className={cn("rounded-full px-2.5 py-0.5 text-[11px] font-semibold",
            a.mode === "noted" ? "bg-muted text-muted-foreground"
              : "bg-green-50 text-green-700 dark:bg-green-950/40 dark:text-green-300")}>
            {a.mode === "noted" ? "Zur Kenntnis genommen" : "Beschlossen"}
          </span>
        ) : (
          <span className="rounded-full bg-primary/10 px-2.5 py-0.5 text-[11px] font-semibold text-primary">Noch nicht beschlossen</span>
        )}
        {a && (
          <span className="text-meta text-muted-foreground">
            {a.committee} · {datum(a.date)}{a.label ? ` · ${a.label}` : ""}
            {!a.template_number && " · vor 2018, nicht im Ratsinformationssystem"}
          </span>
        )}
        {a && <Vorlage nummer={a.template_number} url={a.url} decisionId={a.decision_id} />}
        <StatusAbzeichen karte={d} />
      </div>
    </header>
  );
}

function Zeile({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid gap-0.5 py-2 sm:grid-cols-[11rem_minmax(0,1fr)] sm:gap-3">
      <dt className="text-meta text-muted-foreground">{label}</dt>
      <dd className="min-w-0 text-[14px] leading-relaxed text-foreground">{children}</dd>
    </div>
  );
}

function Laufzeit({ d }: { d: PlanDetail }) {
  return (
    <Abschnitt kicker="Laufzeit">
      <dl className="divide-y divide-border/70">
        <Zeile label="Beginn">{d.start_label ?? (d.adoption ? datum(d.adoption.date) : "noch offen")}</Zeile>
        <Zeile label="Ende">
          {d.end_label ? `bis ${d.end_label}` : "ohne Enddatum"}
          {d.horizon_note && <span className="block text-hinweis text-muted-foreground">{d.horizon_note}</span>}
        </Zeile>
        {d.review_label && <Zeile label="Nächste Überprüfung">{d.review_label}</Zeile>}
        {d.commissioned && (
          <Zeile label="Arbeit begonnen">
            <span className="block break-words">{d.commissioned.title ?? d.commissioned.template_number}</span>
            <span className="text-meta text-muted-foreground">{d.commissioned.date ? `${datum(d.commissioned.date)} · ` : ""}</span>
            <Vorlage nummer={d.commissioned.template_number} url={d.commissioned.url} decisionId={null} />
          </Zeile>
        )}
        {d.decisions.length > 0 && (
          <Zeile label="Weitere Beschlüsse">
            <ul className="space-y-1.5">
              {d.decisions.map((b) => (
                <li key={`${b.date}-${b.template_number}`}>
                  <span className="block">{b.label ?? "Beschluss zum Plan"}</span>
                  <span className="text-meta text-muted-foreground">
                    {b.committee} · {datum(b.date)}{b.mode === "noted" ? " · zur Kenntnis genommen" : ""} ·{" "}
                  </span>
                  <Vorlage nummer={b.template_number} url={b.url} decisionId={b.decision_id} />
                </li>
              ))}
            </ul>
          </Zeile>
        )}
        {d.concluded && (
          <Zeile label="Ausgewertet in">
            <span className="block break-words">{d.concluded.title ?? d.concluded.template_number}</span>
            <Vorlage nummer={d.concluded.template_number} url={d.concluded.url} decisionId={null} />
          </Zeile>
        )}
        {d.predecessor && (
          <Zeile label="Vorgänger">
            <Link href={planHref(d.predecessor.key)} className="text-primary hover:underline">{d.predecessor.title}</Link>
          </Zeile>
        )}
        {d.successor && (
          <Zeile label="Nachfolger">
            <Link href={planHref(d.successor.key)} className="text-primary hover:underline">{d.successor.title}</Link>
            {!d.successor.adopted && <span className="text-meta text-muted-foreground"> · noch nicht beschlossen</span>}
          </Zeile>
        )}
      </dl>
      {d.note && <p className="mt-3 border-t border-border/70 pt-3 text-hinweis text-muted-foreground">{d.note}</p>}
    </Abschnitt>
  );
}

/** Ab so vielen Maßnahmen stehen die Handlungsfelder zugeklappt da. */
const OFFEN_BIS = 20;

function Massnahmen({ m }: { m: NonNullable<PlanDetail["measures"]> }) {
  const [offen, setOffen] = useState<Set<number>>(
    () => new Set(m.count <= OFFEN_BIS ? m.groups.map((_, i) => i) : []));
  const alleOffen = offen.size === m.groups.length;
  const umschalten = (i: number) => setOffen((alt) => {
    const neu = new Set(alt);
    if (neu.has(i)) neu.delete(i); else neu.add(i);
    return neu;
  });
  const stand = m.source.as_of_label ? `Stand ${m.source.as_of_label}` : undefined;
  return (
    <Abschnitt kicker="Maßnahmen" rechts={[`${m.count}`, stand].filter(Boolean).join(" · ")}>
      {m.count_note && <p className="mb-3 text-hinweis text-muted-foreground">{m.count_note}</p>}
      {m.groups.length > 1 && (
        <button type="button" onClick={() => setOffen(new Set(alleOffen ? [] : m.groups.map((_, i) => i)))}
          className="mb-2 text-meta text-primary hover:underline">
          {alleOffen ? "Alle zuklappen" : "Alle aufklappen"}
        </button>
      )}
      <div className="divide-y divide-border/70 border-y border-border/70">
        {m.groups.map((g, i) => {
          const auf = offen.has(i);
          let letztesPaket: string | null = null;
          return (
            <div key={g.field ?? i}>
              <button type="button" onClick={() => umschalten(i)} aria-expanded={auf}
                className="flex min-h-11 w-full items-center gap-2 py-2 text-left">
                <span className="min-w-0 flex-1 break-words text-[14px] font-semibold text-foreground">
                  {g.field ?? "Maßnahmen"}
                </span>
                <span className="font-mono text-meta text-muted-foreground">{g.measures.length}</span>
                {auf ? <ChevronUp className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
                  : <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />}
              </button>
              {auf && (
                // Ein Raster je Feld: Die Kennungsspalte ist so breit wie die
                // längste Kennung („K1“ wie „Klimapakt_07“), der Titel nimmt den Rest.
                <ul className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-3 pb-3">
                  {g.measures.map((x) => {
                    const neuesPaket = x.package && x.package !== letztesPaket ? x.package : null;
                    letztesPaket = x.package ?? letztesPaket;
                    return (
                      <li key={x.code} className="col-span-2 grid grid-cols-subgrid">
                        {neuesPaket && (
                          <p className="col-span-2 mt-2 font-mono text-[10.5px] uppercase tracking-[0.08em] text-muted-foreground">{neuesPaket}</p>
                        )}
                        <span className="py-1 font-mono text-meta text-muted-foreground">{x.code}</span>
                        <span className="break-words py-1 text-[14px] leading-snug text-foreground">{x.title}</span>
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>
          );
        })}
      </div>
      <p className="mt-3 text-meta text-muted-foreground">
        Quelle:{" "}
        <a href={m.source.url} target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
          {m.source.label}
          <ExternalLink className="ml-1 inline h-3 w-3 -translate-y-px" aria-hidden />
        </a>
        {m.source.template_number && <span className="font-mono"> · {m.source.template_number}</span>}
      </p>
    </Abschnitt>
  );
}

function stufe(zeile: number): CSSProperties {
  return { "--zl-i": Math.max(0, Math.min(zeile, 15)) } as CSSProperties;
}

function Station({ s, stand, letzte, zeile }: { s: PlanStation; stand: boolean; letzte: boolean; zeile: number }) {
  const bis = s.date_end ? ` – ${datum(s.date_end)}` : "";
  const leise = s.kind === "preparation";
  return (
    <li className="zeitleiste-auf flex gap-3" style={stufe(zeile)}>
      <div className="flex w-4 shrink-0 flex-col items-center">
        <span className={cn("mt-1 h-2.5 w-2.5 shrink-0 rounded-full border-2",
          stand ? "border-primary bg-primary shadow-[0_0_0_3px_hsl(var(--primary)/0.15)]"
            : leise ? "border-muted-foreground/40 bg-muted"
            : s.oral ? "border-primary/45 bg-muted"
            : "border-primary/45 bg-card")} />
        {!letzte && <span style={stufe(zeile)} className="zeitleiste-schiene mt-1 w-0 flex-1 border-l-2 border-primary/25" />}
      </div>
      <div className={cn("min-w-0 flex-1 pb-4", stand && "rounded-lg bg-primary/[0.06] px-3 py-2.5")}>
        {stand && <p className="mb-0.5 font-mono text-[10px] font-medium uppercase tracking-[0.12em] text-primary">Aktueller Stand</p>}
        <p className="font-mono text-[10.5px] uppercase tracking-[0.08em] text-muted-foreground">
          {stationsArt(s)} · {datum(s.date)}{bis}
        </p>
        <p className="mt-0.5 break-words text-quelle font-medium leading-snug text-foreground">
          {s.decision_id != null ? (
            <Link href={decisionHref(s.decision_id)} className="hover:text-primary hover:underline">{s.title}</Link>
          ) : s.title}
        </p>
        <p className="mt-0.5 text-meta text-muted-foreground">
          {gremien(s.committees)}
          {s.template_number && <span className="font-mono"> · {s.template_number}</span>}
        </p>
      </div>
    </li>
  );
}

function Berichte({ d }: { d: PlanDetail }) {
  const [alle, setAlle] = useState(false);
  const stationen = d.timeline.stations;
  const verborgen = alle ? 0 : Math.max(0, stationen.length - SICHTBAR);
  const rechts = stationen.length === 0 ? undefined : d.report_count > 0
    ? `${d.report_count} ${d.report_count === 1 ? "Bericht" : "Berichte"} · ${d.timeline.span}` : d.timeline.span;
  return (
    <Abschnitt kicker="Berichte im Rat" rechts={rechts}>
      {d.report_note && <p className="mb-3 text-hinweis text-muted-foreground">{d.report_note}</p>}
      {stationen.length === 0 ? null : (
        <>
          {verborgen > 0 && (
            <button type="button" onClick={() => setAlle(true)}
              className="mb-2 ml-7 inline-flex items-center gap-1 text-meta text-primary hover:underline">
              <ChevronUp className="h-3.5 w-3.5" aria-hidden />
              {verborgen === 1 ? "1 frühere Station zeigen" : `${verborgen} frühere Stationen zeigen`}
            </button>
          )}
          <ol className="flex flex-col">
            {stationen.slice(verborgen).map((s, j) => {
              const i = verborgen + j;
              return <Station key={`${s.date}-${s.template_number ?? s.title}-${i}`} s={s}
                stand={i === stationen.length - 1} letzte={i === stationen.length - 1} zeile={j} />;
            })}
          </ol>
        </>
      )}
    </Abschnitt>
  );
}

function Eintraege({ gruppe }: { gruppe: PlanBeschlussGruppe }) {
  return (
    <ul className="divide-y divide-border/70">
      {gruppe.entries.map((e) => (
        <li key={`${e.template_number ?? e.title}-${e.date}`} className="py-2.5">
          <p className="break-words text-[14px] font-medium leading-snug text-foreground">
            {e.decision_id != null ? (
              <Link href={decisionHref(e.decision_id)} className="hover:text-primary hover:underline">{e.title}</Link>
            ) : e.title}
          </p>
          <p className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-meta text-muted-foreground">
            {e.outcome && <OutcomeDot outcome={e.outcome} />}
            <span>{[e.committee, datum(e.date)].filter(Boolean).join(" · ")}</span>
            {e.template_number && <span className="font-mono">{e.template_number}</span>}
            {e.deliberations > 1 && <span>{e.deliberations} Beratungen</span>}
          </p>
        </li>
      ))}
    </ul>
  );
}

function Beschluesse({ d }: { d: PlanDetail }) {
  const [weitere, setWeitere] = useState(false);
  const haupt = d.decision_groups.filter((g) => g.key !== "mentions");
  const erwaehnt = d.decision_groups.find((g) => g.key === "mentions");
  if (haupt.length === 0 && !erwaehnt) return null;
  return (
    <Abschnitt kicker="Beschlüsse zum Plan">
      <div className="space-y-4">
        {haupt.map((g) => (
          <div key={g.key}>
            <p className="text-[13px] font-semibold text-foreground">
              {g.label} <span className="font-normal text-muted-foreground">· {g.entries.length}</span>
            </p>
            <Eintraege gruppe={g} />
          </div>
        ))}
        {erwaehnt && (
          <div>
            <button type="button" onClick={() => setWeitere((w) => !w)} aria-expanded={weitere}
              className="inline-flex items-center gap-1 text-[13px] font-medium text-primary hover:underline">
              {weitere ? <ChevronUp className="h-3.5 w-3.5" aria-hidden /> : <ChevronDown className="h-3.5 w-3.5" aria-hidden />}
              Weitere: {erwaehnt.entries.length} {erwaehnt.entries.length === 1 ? "Beschluss erwähnt" : "Beschlüsse erwähnen"} den Plan
            </button>
            {weitere && (
              <div className="mt-2">
                <p className="text-hinweis text-muted-foreground">
                  Ihre Vorlage nennt die Nummer des Plans. Eine Erwähnung ist keine Umsetzung.
                </p>
                <Eintraege gruppe={erwaehnt} />
              </div>
            )}
          </div>
        )}
      </div>
    </Abschnitt>
  );
}

function PlanInner() {
  const key = useSearchParams().get("key");
  const { zeigen: zeigeZurueck, zurueck } = useZurueck();
  const config = useAppConfig();
  const an = featureAktiv(config.data, "plaene");
  const { data, loading, error, refetch } = useFetch<PlanDetail>(
    key && an ? `/council/plan/${encodeURIComponent(key)}` : null, { quiet: true });

  // Erst die Konfiguration, dann der Plan. `!data && !error` gilt als Laden:
  // Im Durchlauf, in dem der Schalter angeht, hat `useFetch` den neuen Pfad
  // noch nicht gesehen und meldet kein Laden — ein `notFound()` dort trifft
  // jede Seite beim ersten Aufruf.
  if (config.isPending || (an && (loading || (!data && !error)))) return <DetailSkeleton />;
  if (!an) notFound();
  if (!data) {
    if (error && !istNichtGefunden(error)) return <AbrufFehler error={error} onRetry={refetch} was="Dieser Plan" />;
    notFound();
  }
  return (
    <div className="mx-auto max-w-3xl weit:max-w-[1480px]">
      <div className="print-hidden flex items-center justify-between gap-3">
        {zeigeZurueck ? (
          <button onClick={() => zurueck(plaeneHref)} className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
            <ArrowLeft className="h-4 w-4" /> Pläne der Stadt
          </button>
        ) : <span />}
        <ShareButton path={planHref(data.key)} title={`${data.title} — Ratslotse`} />
      </div>
      <Kopf d={data} />
      {/* Ab `weit` zwei Spalten wie auf der Themen-Seite: links, was den Plan
          beschreibt und was über ihn berichtet wurde; rechts die Beschlüsse. */}
      <div className="mt-5 space-y-4 weit:grid weit:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] weit:items-start weit:gap-6 weit:space-y-0">
        <div className="min-w-0 space-y-4">
          <Laufzeit d={data} />
          {data.measures && <Massnahmen m={data.measures} />}
          <Berichte d={data} />
        </div>
        <div className="min-w-0 space-y-4">
          <Beschluesse d={data} />
          <p className="text-hinweis text-muted-foreground">
            Gefunden über die Titel und Vorlagen der Tagesordnungspunkte im Ratsinformationssystem.
            Nichtöffentliche Sitzungen, Mitteilungen ohne Vorlage und Berichte außerhalb des
            Ratsinformationssystems sieht Ratslotse nicht.
          </p>
        </div>
      </div>
    </div>
  );
}

export default function PlanPage() {
  return (
    <Suspense fallback={<DetailSkeleton />}>
      <PlanInner />
    </Suspense>
  );
}
