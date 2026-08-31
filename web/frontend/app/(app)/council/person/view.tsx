"use client";


import { Suspense, useEffect, useState } from "react";
import { useSearchParams, notFound } from "next/navigation";
import { ArrowLeft, Gavel, Info, ExternalLink, ChevronDown, Users } from "lucide-react";
import { MemberDetail, PersonProfil, VerwaltungDetail } from "@/lib/types";
import { Card, DetailSkeleton, formatDate } from "@/components/ui";
import { PartyBadge, partyBrand, AffiliationBadge } from "@/components/decision-ui";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { apiUrl, authHeaders } from "@/lib/api";
import { useFetch } from "@/lib/use-fetch";
import { cn } from "@/lib/utils";
import { shortCommittee } from "@/lib/committees";
import { useZurueck } from "@/lib/zurueck";

const sessionUrl = (ksinr: number) => `https://buergerinfo.oldenburg.de/si0057.php?__ksinr=${ksinr}`;

type Membership = NonNullable<MemberDetail["ris"]>["memberships"][number];

const yearOf = (d: string | null | undefined): number | null => {
  const y = d ? parseInt(d.slice(0, 4), 10) : NaN;
  return Number.isFinite(y) ? y : null;
};
const isChair = (role: string | null) => !!role && /vorsitz/i.test(role);
const isDeputy = (role: string | null) => !!role && /(stellv|stv\.)/i.test(role);
const initials = (name: string) =>
  name.trim().split(/\s+/).filter(Boolean).map((w) => w[0]).slice(0, 2).join("").toUpperCase() || "?";

function Section({ title, aside, children }: { title: string; aside?: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="mt-6">
      <div className="flex items-baseline justify-between gap-3">
        <h2 className="font-display text-[15px] font-bold text-foreground">{title}</h2>
        {aside && <span className="text-xs text-muted-foreground">{aside}</span>}
      </div>
      <div className="mt-2.5">{children}</div>
    </div>
  );
}

/** Aktuelle Ämter als Gantt (Design 17a): Balkenlänge = Amtsdauer, orange =
 *  Vorsitz, „–heute"-Balken laufen bis zum rechten Rand. */
function OfficesGantt({ current }: { current: Membership[] }) {
  const thisYear = new Date().getFullYear();
  const starts = current.map((m) => yearOf(m.von)).filter((y): y is number => y != null);
  const minYear = starts.length ? Math.min(...starts) : thisYear - 4;
  const span = Math.max(1, thisYear - minYear);
  const midYear = minYear + Math.round(span / 2);
  const rows = [...current].sort((a, b) => {
    const ca = isChair(a.role) ? 0 : 1, cb = isChair(b.role) ? 0 : 1;
    return ca !== cb ? ca - cb : (yearOf(a.von) ?? minYear) - (yearOf(b.von) ?? minYear);
  });
  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <div className="flex flex-col gap-2.5">
        {rows.map((m, i) => {
          const chair = isChair(m.role);
          const vy = yearOf(m.von) ?? minYear;
          const leftPct = Math.min(90, Math.max(0, ((vy - minYear) / span) * 100));
          const showLabel = 100 - leftPct >= 26 && m.von;
          return (
            // Schmal (< sm) stapelt sich die Zeile: Name über dem Balken, Jahr
            // rechts daneben. Zweispaltig fraß die Namensspalte auf dem Handy
            // die halbe Breite — Ämter wurden abgeschnitten („Wirtschaft & Dig…")
            // und junge Ämter schrumpften zum Punkt. Ab sm bleibt der Gantt.
            <div key={`${m.committee}-${i}`}
              className="flex flex-wrap items-center gap-x-1.5 gap-y-1 sm:grid sm:grid-cols-[14rem_1fr] sm:gap-3">
              <span className="flex w-full min-w-0 items-center gap-1.5 sm:w-auto">
                {chair
                  ? <Gavel className="h-3.5 w-3.5 shrink-0 text-signal" />
                  : <span className="w-3.5 shrink-0" aria-hidden />}
                <span className={cnEllipsis(chair)} title={m.committee}>
                  {shortCommittee(m.committee)}
                  {/* nowrap nur schmal, wo der Name umbrechen darf: sonst landet
                      der Trenner allein am Zeilenende und „Stellv." rutscht in
                      die nächste. Ab sm wird ohnehin gekürzt statt umgebrochen. */}
                  {isDeputy(m.role) && <span className="ml-1 text-[11px] font-normal text-muted-foreground max-sm:whitespace-nowrap">· Stellv.</span>}
                </span>
                {/* Das Jahr steht schmal IMMER in der Namenszeile — im Balken
                    wäre es bei kurzer Amtszeit unlesbar oder ganz weg. */}
                {m.von && (
                  <span className={`ml-auto shrink-0 text-[11px] font-semibold tabular-nums sm:hidden ${chair ? "text-signal" : "text-primary"}`}>
                    seit {vy}
                  </span>
                )}
              </span>
              {/* Schmal mit Spur hinterlegt, damit die gemeinsame Skala sichtbar
                  bleibt und man Startjahre vergleichen kann. */}
              <span className="relative block h-2 w-full rounded-full bg-muted sm:h-4 sm:w-auto sm:rounded-none sm:bg-transparent">
                <span className={`absolute inset-y-0 rounded-full sm:inset-y-[2px] ${chair ? "bg-signal" : "bg-primary"}`}
                  style={{ left: `${leftPct}%`, right: 0 }} />
                {showLabel && (
                  <span className="absolute top-1/2 hidden -translate-y-1/2 text-[10.5px] font-semibold text-white sm:inline"
                    style={{ left: `calc(${leftPct}% + 8px)` }}>
                    seit {vy}
                  </span>
                )}
              </span>
            </div>
          );
        })}
      </div>
      {/* Jahresachse — nur ab sm: schmal ist unter jedem Balken schon eine
          Spur, die Spanne steht kompakt in der Legende. */}
      <div className="relative mt-3 hidden h-4 border-t border-border sm:ml-[14rem] sm:block">
        <span className="absolute left-0 top-1 text-[10px] text-muted-foreground">{minYear}</span>
        {span > 6 && <span className="absolute left-1/2 top-1 -translate-x-1/2 text-[10px] text-muted-foreground">{midYear}</span>}
        <span className="absolute right-0 top-1 text-[10px] text-muted-foreground">heute</span>
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11.5px] text-muted-foreground">
        <span className="inline-flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-signal" /> Vorsitz<span className="hidden sm:inline"> / stellv. Vorsitz</span></span>
        <span className="inline-flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-primary" /> Mitglied</span>
        <span className="ml-auto tabular-nums sm:hidden">{minYear} → heute</span>
      </div>
    </div>
  );
}

/** Schmal darf der Gremienname umbrechen — er hat dort die volle Zeile für sich
 *  und wird nicht mehr von einer Balkenspalte beschnitten. Erst ab sm, wo er in
 *  einer festen 14rem-Spalte sitzt, wird wieder gekürzt. */
function cnEllipsis(chair: boolean) {
  return `min-w-0 text-[13px] sm:truncate ${chair ? "font-semibold text-foreground" : "text-foreground"}`;
}

function PersonInner() {
  const slug = useSearchParams().get("slug");
  const { data, loading } = useFetch<PersonProfil>(slug ? `/council/person/${slug}` : null);

  // Eine Person kann in den Anwesenheitslisten unter zwei Namensformen stehen;
  // das Backend liefert für beide dasselbe Profil und nennt in `slug` die
  // aktuelle Adresse. Die Zeile korrigiert nur die Adressleiste — der alte Link
  // funktioniert weiter, aber wer von hier aus teilt, teilt die aktuelle
  // Adresse. Ohne Router-Navigation, damit die Seite nicht neu lädt.
  const kanon = data?.slug ?? null;
  useEffect(() => {
    if (kanon && slug && kanon !== slug) {
      window.history.replaceState(null, "", `/council/person?slug=${encodeURIComponent(kanon)}`);
    }
  }, [kanon, slug]);

  if (loading) return <DetailSkeleton />;
  if (!data) notFound();
  if (data.typ === "verwaltung") return <VerwaltungProfil data={data} />;
  return <RatsmitgliedProfil data={data} />;
}

function RatsmitgliedProfil({ data }: { data: MemberDetail }) {
  const { zeigen: zeigeZurueck, zurueck } = useZurueck();
  const [pastOpen, setPastOpen] = useState(false);

  const brand = data.party ? partyBrand(data.party) : null;
  // Aktuelle Zugehörigkeit: vom Server aufgelöst, damit der Kopf dasselbe
  // sagt wie das Verzeichnis („FDP/Volt" → FDP, wo es belegt ist). Ältere
  // Antworten ohne das Feld fallen auf die letzte Phase zurück.
  const currentAffiliation = data.current_affiliation
    ?? (data.faction_timeline.length ? data.faction_timeline[data.faction_timeline.length - 1] : null);
  const memberships = data.ris?.memberships ?? [];
  const current = memberships.filter((m) => !m.bis);
  const past = memberships.filter((m) => m.bis);
  const nChairs = data.committees.filter((c) => c.chair).length;
  const maxPresence = Math.max(1, ...data.committees.map((c) => c.n));

  const pastFrom = past.map((m) => yearOf(m.von)).filter((y): y is number => y != null);
  const pastTo = past.map((m) => yearOf(m.bis)).filter((y): y is number => y != null);
  const pastSpan = pastFrom.length && pastTo.length ? `${Math.min(...pastFrom)}–${Math.max(...pastTo)}` : null;

  return (
    <Card className="mx-auto max-w-3xl p-5 sm:p-6">
      {zeigeZurueck && (
        <button onClick={() => zurueck("/council")} className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft className="h-4 w-4" /> Zurück
        </button>
      )}

      {/* Kopf: Avatar + Name + Kennzahlen */}
      <div className="mt-3.5 flex items-center gap-4">
        <span className={cn("flex h-14 w-14 shrink-0 items-center justify-center rounded-full font-display text-xl font-bold shadow-sm", !brand && "bg-muted text-muted-foreground")}
          style={brand ? { backgroundColor: brand.bg, color: brand.fg } : undefined}>
          {initials(data.name)}
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1">
            <h1 className="font-display text-2xl font-bold tracking-tight text-foreground">{data.name}</h1>
            {/* Beratende Ausschuss-Mitglieder haben keine Fraktion, sondern eine
                entsendende Organisation — „parteilos" wäre hier die falsche
                Kategorie, nicht bloß eine unschöne Vokabel (Tims Befund
                21.08.2026). */}
            {data.art === "beratend"
              ? (
                <span className="inline-flex items-center gap-1.5 rounded-full border border-border bg-muted/60 px-2.5 py-0.5 text-xs font-medium text-muted-foreground">
                  <Users className="h-3 w-3" aria-hidden />
                  Beratendes Mitglied{data.organisation ? ` · ${data.organisation}` : ""}
                </span>
              )
              : currentAffiliation
              ? <AffiliationBadge label={currentAffiliation.label} kind={currentAffiliation.kind} parties={currentAffiliation.parties} />
              : data.party && <PartyBadge party={data.party} />}
          </div>
          <div className="mt-1 flex flex-wrap items-center gap-x-3.5 gap-y-1 text-[13px] text-muted-foreground">
            <span><strong className="font-bold tabular-nums text-foreground">{data.n_sessions}</strong> Sitzungen besucht</span>
            {data.active_from && (
              <>
                <span className="text-border" aria-hidden>·</span>
                <span>aktiv seit <strong className="font-semibold text-foreground">{yearOf(data.active_from)}</strong></span>
              </>
            )}
            {nChairs > 0 && (
              <>
                <span className="text-border" aria-hidden>·</span>
                <span className="inline-flex items-center gap-1 font-semibold text-signal">
                  <Gavel className="h-3 w-3" /> {nChairs} {nChairs === 1 ? "Vorsitz" : "Vorsitze"}
                </span>
              </>
            )}
          </div>
        </div>
        <Popover>
          <PopoverTrigger asChild>
            <button type="button" className="hidden shrink-0 items-center gap-1.5 rounded-lg border border-input bg-card px-3 py-1.5 text-xs font-medium text-foreground transition-colors hover:bg-accent sm:inline-flex">
              <Info className="h-3.5 w-3.5" /> Wie erfasst?
            </button>
          </PopoverTrigger>
          <PopoverContent className="w-72 max-w-[calc(100vw-2rem)] text-xs leading-relaxed text-muted-foreground">
            Aus den Anwesenheitslisten der Protokolle (erfasst ab 2018), ergänzt um die offiziellen Gremien-Zeiträume
            aus dem Ratsinformationssystem (zurück bis 2001). Präsenz zeigt Aktivität, nicht das Stimmverhalten —
            Protokolle nennen namentliche Einzelstimmen nur selten.
          </PopoverContent>
        </Popover>
      </div>

      {/* Aktuelle Ämter als Gantt */}
      {current.length > 0 && (
        <Section title="Aktuelle Ämter" aside={<>{current.length} laufend · Balken = Amtszeit</>}>
          <OfficesGantt current={current} />
        </Section>
      )}

      {/* Frühere Ämter eingeklappt */}
      {past.length > 0 && (
        <div className="mt-3 overflow-hidden rounded-xl border border-border bg-card">
          <button type="button" onClick={() => setPastOpen((v) => !v)}
            className="flex w-full items-center justify-between gap-2 px-4 py-3 text-left">
            <span className="text-[13.5px] font-semibold text-foreground">
              Frühere Ämter <span className="font-normal text-muted-foreground">· {past.length} beendet{pastSpan ? ` (${pastSpan})` : ""}</span>
            </span>
            <ChevronDown className={`h-4 w-4 shrink-0 text-muted-foreground transition-transform ${pastOpen ? "rotate-180" : ""}`} />
          </button>
          {pastOpen && (
            <div className="border-t border-border px-4 py-3">
              <div className="space-y-1.5">
                {past.map((m, i) => (
                  <div key={`${m.committee}-${i}`} className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5">
                    <span className="min-w-0 text-[13px] text-foreground" title={m.committee}>
                      {shortCommittee(m.committee)}
                      {isChair(m.role) && <span className="ml-1.5 text-[11px] font-medium text-signal">{isDeputy(m.role) ? "stellv. Vorsitz" : "Vorsitz"}</span>}
                    </span>
                    <span className="shrink-0 text-xs tabular-nums text-muted-foreground">
                      {m.von ? yearOf(m.von) : "?"} – {m.bis ? yearOf(m.bis) : "heute"}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Fraktions- & Gruppen-Verlauf */}
      {data.faction_timeline.length > 0 && (
        <Section title="Zugehörigkeit im Zeitverlauf" aside="Fraktion · Gruppe · parteilos">
          <div className="flex flex-wrap items-center gap-2">
            {data.faction_timeline.map((f, i) => (
              <div key={`${f.label}-${f.first}`} className="flex items-center gap-2">
                {i > 0 && <span className="text-muted-foreground/50">→</span>}
                <span className="inline-flex items-center gap-2 rounded-lg border border-border px-2.5 py-1.5">
                  <AffiliationBadge label={f.label} kind={f.kind} parties={f.parties} />
                  <span className="text-[11.5px] tabular-nums text-muted-foreground">
                    {formatDate(f.first)} – {formatDate(f.last)}
                  </span>
                </span>
              </div>
            ))}
          </div>
        </Section>
      )}

      {/* Präsenz je Gremium als Balken */}
      {data.committees.length > 0 && (
        <Section title="Präsenz je Gremium" aside="besuchte Sitzungen">
          <div className="space-y-2">
            {data.committees.map((c) => (
              // Gleiche Stapelung wie beim Ämter-Gantt: schmal ist für eine
              // Namensspalte kein Platz („Betrieb Gebäudewirtschaft" bräuchte
              // 164 px, bekam 70). Name samt Zahl oben, Balken darunter.
              <div key={c.committee}
                className="flex flex-wrap items-center gap-x-1.5 gap-y-1 sm:grid sm:grid-cols-[14rem_1fr_3rem] sm:gap-3">
                <span className="flex w-full min-w-0 items-center gap-1.5 sm:w-auto">
                  <span className="min-w-0 text-[13px] text-foreground sm:truncate" title={c.committee}>{shortCommittee(c.committee)}</span>
                  {c.chair && (
                    <span className="inline-flex shrink-0 items-center gap-1 rounded-md bg-signal/10 px-1.5 py-0.5 text-[10px] font-semibold text-signal">
                      <Gavel className="h-2.5 w-2.5" /> Vorsitz
                    </span>
                  )}
                  <span className="ml-auto shrink-0 text-xs font-semibold tabular-nums text-muted-foreground sm:hidden">{c.n}</span>
                </span>
                <span className="block h-2 w-full overflow-hidden rounded-full bg-muted sm:w-auto">
                  <span className="block h-full rounded-full bg-primary" style={{ width: `${(c.n / maxPresence) * 100}%` }} />
                </span>
                <span className="hidden text-right text-xs tabular-nums text-muted-foreground sm:block">{c.n}</span>
              </div>
            ))}
          </div>
        </Section>
      )}

      {/* Wortbeiträge (Personen-Paket 10.08.26): die jüngsten Beiträge in
          voller Länge — dasselbe Beleg-Versprechen wie im Ratsgespräch.
          Vielredner kommen auf über tausend Beiträge, deshalb seitenweise und
          nach Gremium filterbar (Tims Wunsch 10.08.). */}
      {(data.wortbeitraege?.length ?? 0) > 0 && (
        <Wortbeitraege slug={data.slug} erste={data.wortbeitraege ?? []}
          gesamt={data.wortbeitraege_gesamt ?? (data.wortbeitraege?.length ?? 0)}
          committees={data.wortbeitraege_gremien ?? []} />
      )}

      {/* Zuletzt anwesend */}
      {data.recent.length > 0 && (
        <Section title="Zuletzt anwesend">
          <div className="flex flex-col">
            {data.recent.map((r, i) => (
              <a key={`${r.ksinr}-${r.session_date}`} href={sessionUrl(r.ksinr)} target="_blank" rel="noreferrer"
                className={`group flex items-center justify-between gap-3 py-2.5 text-[13.5px] ${i > 0 ? "border-t border-border" : ""}`}>
                <span className="min-w-0 truncate text-foreground" title={r.committee}>{shortCommittee(r.committee)}</span>
                <span className="flex shrink-0 items-center gap-1.5 text-xs text-muted-foreground">
                  {formatDate(r.session_date)}
                  <ExternalLink className="h-3 w-3 text-muted-foreground/40 group-hover:text-primary" />
                </span>
              </a>
            ))}
          </div>
        </Section>
      )}
    </Card>
  );
}

/** Schmaler Steckbrief für Verwaltungsleute mit erkanntem Amt (Tims Wunsch
 *  19.08., im Anschluss an den Figura-Badge-Fund): kein Mandat, deshalb keine
 *  Fraktions-Zeitleiste, kein Vorsitz-Zähler, keine Gremien-Präsenz — nur
 *  Amt, Erwähnungszeitraum und Wortbeiträge/Zusagen. Dieselbe Hafenblau-Farbe
 *  wie das „Stadt"-Badge im KI-Antworttext (qa-bausteine.tsx), damit beide
 *  erkennbar zusammengehören. */
function VerwaltungProfil({ data }: { data: VerwaltungDetail }) {
  const { zeigen: zeigeZurueck, zurueck } = useZurueck();
  const zeitraum = data.aktiv
    ? (data.von ? `In Sitzungsprotokollen erwähnt seit ${data.von}` : null)
    : (data.von && data.bis ? `In Sitzungsprotokollen erwähnt ${data.von}–${data.bis}` : null);

  return (
    <Card className="mx-auto max-w-3xl p-5 sm:p-6">
      {zeigeZurueck && (
        <button onClick={() => zurueck("/council")} className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft className="h-4 w-4" /> Zurück
        </button>
      )}

      <div className="mt-3.5 flex items-center gap-4">
        <span className="flex h-14 w-14 shrink-0 items-center justify-center rounded-full font-display text-xl font-bold text-white shadow-sm"
          style={{ backgroundColor: "#0764a6" }}>
          {initials(data.name)}
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1">
            <h1 className="font-display text-2xl font-bold tracking-tight text-foreground">{data.name}</h1>
            <span className="inline-flex items-center gap-1.5 rounded-full border border-border bg-card px-1.5 py-px text-[10px] font-medium text-muted-foreground">
              <span aria-hidden className="h-[7px] w-[7px] shrink-0 rounded-full" style={{ backgroundColor: "#0764a6" }} />
              Stadt
            </span>
          </div>
          <p className="mt-1 text-[13px] text-muted-foreground">
            {data.role}{zeitraum && <> · {zeitraum}</>}
          </p>
        </div>
        <Popover>
          <PopoverTrigger asChild>
            <button type="button" className="hidden shrink-0 items-center gap-1.5 rounded-lg border border-input bg-card px-3 py-1.5 text-xs font-medium text-foreground transition-colors hover:bg-accent sm:inline-flex">
              <Info className="h-3.5 w-3.5" /> Wie erfasst?
            </button>
          </PopoverTrigger>
          <PopoverContent className="w-72 max-w-[calc(100vw-2rem)] text-xs leading-relaxed text-muted-foreground">
            Amt und Zeitraum stammen aus den Anwesenheitslisten der Protokolle — das
            Ratsinformationssystem führt die Stadtverwaltung nicht als Mandatsträger:innen,
            deshalb gibt es hier keine amtliche Amtszeit, nur den Zeitraum der
            Protokoll-Erwähnungen.
          </PopoverContent>
        </Popover>
      </div>

      {(data.wortbeitraege?.length ?? 0) > 0 && (
        <Wortbeitraege slug={data.slug} erste={data.wortbeitraege ?? []}
          gesamt={data.wortbeitraege_gesamt ?? (data.wortbeitraege?.length ?? 0)}
          committees={data.wortbeitraege_gremien ?? []} />
      )}
    </Card>
  );
}

const WB_ART: Record<string, string> = {
  rede: "Rede", anfrage: "Anfrage", einwohnerfrage: "Einwohnerfrage", zusage: "Zusage",
};

function WortbeitragZeile({ w, erste }: {
  w: NonNullable<MemberDetail["wortbeitraege"]>[number]; erste: boolean;
}) {
  const [offen, setOffen] = useState(false);
  const lang = w.text.length > 300;
  return (
    <div className={cn("py-2.5 text-[13px] leading-relaxed", !erste && "border-t border-border")}>
      <p className="flex items-baseline justify-between gap-3 text-xs text-muted-foreground">
        <span className="min-w-0 truncate">
          {WB_ART[w.art] ?? w.art}{w.top ? ` · ${w.top}` : ""} · {shortCommittee(w.committee ?? "")}
        </span>
        <span className="shrink-0">{formatDate(w.session_date)}</span>
      </p>
      <p className={cn("mt-1 whitespace-pre-wrap text-foreground", !offen && lang && "line-clamp-3")}>
        {w.text}
      </p>
      {lang && (
        <button type="button" onClick={() => setOffen((v) => !v)} aria-expanded={offen}
          className="mt-0.5 text-[11.5px] font-medium text-primary hover:underline">
          {offen ? "Weniger anzeigen" : "Ganzen Beitrag anzeigen"}
        </button>
      )}
    </div>
  );
}

type WB = NonNullable<MemberDetail["wortbeitraege"]>[number];

/** „Aus den Protokollen": alle Beiträge, seitenweise nachladbar und nach
 *  Gremium filterbar.
 *
 *  Die erste Seite kommt aus dem Profil mit (die Seite soll sofort etwas
 *  zeigen); erst „Mehr anzeigen" oder ein Gremien-Wechsel fragt nach. Der
 *  Filter zeigt die Anzahl je Gremium — bei vierzehn Ausschüssen ist das der
 *  Unterschied zwischen Suchen und Finden. */
function Wortbeitraege({ slug, erste, gesamt, committees }: {
  slug: string; erste: WB[]; gesamt: number;
  committees: { committee: string; n: number }[];
}) {
  const [items, setItems] = useState<WB[]>(erste);
  const [committee, setGremium] = useState<string>("");
  const [total, setTotal] = useState(gesamt);
  const [laedt, setLaedt] = useState(false);
  const [fehler, setFehler] = useState(false);

  const laden = async (naechstesGremium: string, ab: number) => {
    setLaedt(true);
    setFehler(false);
    try {
      const p = new URLSearchParams({ offset: String(ab), limit: "20" });
      if (naechstesGremium) p.set("committee", naechstesGremium);
      const r = await fetch(apiUrl(`/council/person/${encodeURIComponent(slug)}/wortbeitraege?${p}`),
        { credentials: "include", headers: authHeaders() });
      if (!r.ok) throw new Error();
      const b = await r.json();
      setItems((alt) => (ab === 0 ? b.items : [...alt, ...b.items]));
      setTotal(b.total ?? 0);
    } catch {
      // Ehrlich bleiben: kein stilles Nichts, sondern ein Hinweis mit
      // Wiederholen — die Liste davor bleibt stehen.
      setFehler(true);
    } finally {
      setLaedt(false);
    }
  };

  const filtern = (naechstes: string) => {
    setGremium(naechstes);
    void laden(naechstes, 0);
  };

  return (
    <Section title="Aus den Protokollen"
      aside={`${items.length} von ${total} · Paraphrasen`}>
      {committees.length > 1 && (
        <div className="mb-2.5">
          <label className="sr-only" htmlFor="wb-committee">Nach Gremium filtern</label>
          <select id="wb-committee" value={committee}
            onChange={(e) => filtern(e.target.value)}
            className="h-8 w-full max-w-[22rem] rounded-[10px] border border-border bg-card px-2 text-[13px] outline-none focus:border-primary">
            <option value="">Alle Gremien ({gesamt})</option>
            {committees.map((g) => (
              <option key={g.committee} value={g.committee}>
                {shortCommittee(g.committee)} ({g.n})
              </option>
            ))}
          </select>
        </div>
      )}
      <div className="flex flex-col">
        {items.map((w, i) => (
          <WortbeitragZeile key={`${w.session_date}-${w.top}-${i}`} w={w} erste={i === 0} />
        ))}
      </div>
      {items.length === 0 && !laedt && (
        <p className="py-3 text-[13px] text-muted-foreground">
          In diesem Gremium ist kein Wortbeitrag protokolliert.
        </p>
      )}
      {items.length < total && (
        <button type="button" disabled={laedt}
          onClick={() => void laden(committee, items.length)}
          className="mt-2 w-full rounded-[11px] border border-border bg-card py-2 text-[13px] font-medium transition-colors hover:bg-muted disabled:opacity-60">
          {laedt ? "Wird geladen …" : `Mehr anzeigen (noch ${total - items.length})`}
        </button>
      )}
      {fehler && (
        <p className="mt-2 text-[12px] text-signal">
          Konnte nicht geladen werden.{" "}
          <button type="button" onClick={() => void laden(committee, items.length)}
            className="font-medium underline">Nochmal versuchen</button>
        </p>
      )}
      {/* Ehrlichkeit zur Quelle (Tims Punkt 10.08.): Niederschriften sind
          Verlaufsprotokolle — die Protokollführung fasst zusammen, nicht
          jede Wortmeldung wird erfasst. Ohne den Hinweis läse sich eine
          kurze Liste wie „mehr hat die Person nie gesagt". */}
      <p className="mt-2 text-[11px] leading-relaxed text-muted-foreground/60">
        Die Protokolle fassen Wortbeiträge sinngemäß zusammen — nicht jede
        Wortmeldung wird erfasst. Diese Liste ist deshalb ein Ausschnitt,
        kein vollständiges Redeprotokoll.
      </p>
    </Section>
  );
}

export default function PersonPage() {
  return (
    <Suspense fallback={<DetailSkeleton />}>
      <PersonInner />
    </Suspense>
  );
}
