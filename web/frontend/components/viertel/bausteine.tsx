"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, CalendarDays, Check, ExternalLink, Flag, Hammer, LocateFixed, MapPinned, Megaphone, Newspaper, Search, TrafficCone, X } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { ApiAntwort } from "@/lib/vertrag";
import type { DecisionOutcome, Topic } from "@/lib/types";
import { decisionHref, sitzungHref } from "@/lib/routes";
import { shortCommittee } from "@/lib/committees";
import { cn, formatDate } from "@/lib/utils";
import { Badge, Button, Card, Input, Spinner, toast } from "@/components/ui";
import { STAND_FARBE } from "@/components/viertel-zeichner";
import { loadOrtsbereiche, ortsbereichFor } from "@/lib/districts";
import { formatEuro, OUTCOME_META } from "@/components/decision-ui";
import { STAFFEL, staffelStil } from "@/components/staffel";

/** Die Bausteine von „Mein Viertel" — Tafel-Kopf, Karten, Liste, Detail,
 *  Suche, Standort — als eigene Komponenten.
 *
 *  **Warum eine eigene Datei.** Bis 07.09.2026 stand alles in
 *  `app/(app)/viertel/view.tsx` (849 Zeilen), und die Seite war die einzige,
 *  die es brauchte. Mit der vereinten Stadtkarte (`STADTKARTE-PLAN.md`,
 *  Richtung A) füllen dieselben Bausteine die Tafel-Spalte neben der großen
 *  Karte — in schmalerer Fassung, mit anderen Links (`ortHref`), aber ohne
 *  zweite Wahrheit. `/viertel` setzt sie in der alten Reihenfolge zusammen und
 *  verhält sich unverändert; `/karte` setzt sie neu zusammen.
 *
 *  Die Links gehen über `ortHref(placeId, vorhaben?)`: `/viertel` gibt
 *  `viertelHref` hinein, `/karte` gibt `karteHref` hinein. So zeigt „Nebenan"
 *  auf derselben Karte auf dieselbe Karte und nicht auf die alte Seite.
 */
export type Tafel = ApiAntwort<"/districts/{place_id}/projects">;
export type Vorhaben = Tafel["projects"][number];
export type Uebersicht = ApiAntwort<"/districts/projects">;
export type Treffer = ApiAntwort<"/districts/lookup">["matches"][number];
export type OrtHref = (placeId: string, vorhaben?: number | null) => string;

/** Reihenfolge und Beschriftung der Stände — was gerade passiert, zuerst. */
export const STAND: Record<string, { label: string; color: "amber" | "green" | "blue" | "slate" | "red"; rang: number }> = {
  building: { label: "Im Bau", color: "amber", rang: 0 },
  decided: { label: "Beschlossen", color: "green", rang: 1 },
  planning: { label: "In Planung", color: "blue", rang: 2 },
  idea: { label: "Idee", color: "slate", rang: 3 },
  done: { label: "Fertig", color: "slate", rang: 4 },
  rejected: { label: "Abgelehnt", color: "red", rang: 5 },
};
export const KATEGORIE: Record<string, string> = {
  housing: "Wohnen & Bauen", traffic: "Verkehr", school_childcare: "Schule & Kita",
  green: "Grün & Umwelt", culture_sport_social: "Kultur, Sport & Soziales", other: "Sonstiges",
};
/** Reihenfolge der Stufenleiste: was gerade passiert, zuerst. */
export const STUFEN = ["building", "decided", "planning", "idea", "done", "rejected"] as const;
/** Der Weg eines Vorhabens: Idee → Planung → beschlossen → im Bau → fertig,
 *  die erreichte Stufe gefüllt. Abgelehnt ist keine Stufe, sondern ein Ende. */
export const WEG = ["idea", "planning", "decided", "building", "done"] as const;

/* ------------------------------------------------------------- Daten --- */

export function useUebersicht(enabled = true) {
  return useQuery({ queryKey: ["viertel-uebersicht"], queryFn: () => api.get<Uebersicht>("/districts/projects"), enabled });
}

export function useTafel(placeId: string | null) {
  return useQuery({
    queryKey: ["viertel", placeId],
    queryFn: () => api.get<Tafel>(`/districts/${encodeURIComponent(placeId ?? "")}/projects`),
    enabled: !!placeId,
  });
}

export function useMeineOrtsbereiche(orte: { name: string; place_id: string }[] | undefined) {
  const { user } = useAuth();
  const topics = useQuery({ queryKey: ["topics"], queryFn: () => api.get<Topic[]>("/topics"), enabled: !!user });
  return useMemo(() => {
    if (!topics.data || !orte) return [] as { name: string; place_id: string }[];
    // Ein gewählter Stadtteil IST ein Thema (Einrichtungs-Assistent, Schritt 2) —
    // abgeleitet statt gemerkt, wie dort.
    return orte.filter((o) => topics.data.some((t) => t.name.toLowerCase() === o.name.toLowerCase()));
  }, [topics.data, orte]);
}

/** Die Vorhaben einer Tafel in Anzeige-Reihenfolge: was gerade passiert, zuerst; dann das jüngste. */
export function sortiert(projects: Vorhaben[]): Vorhaben[] {
  return [...projects].sort((a, b) => (STAND[a.stage]?.rang ?? 9) - (STAND[b.stage]?.rang ?? 9) || (b.last_date ?? "").localeCompare(a.last_date ?? ""));
}

/* ------------------------------------------------------- Stadt-Stufe --- */

/** Die Stadtzahl mit den drei Ständen — der Blickfang der Anzeigetafel.
 *  `kompakt` für die Tafel-Spalte der Karte (kleinere Type). */
export function Stadtzahl({ data, orte, kompakt }: { data: Uebersicht; orte: Uebersicht["districts"]; kompakt?: boolean }) {
  const belegt = orte.filter((o) => o.count > 0).length;
  return (
    <div className="min-w-0">
      <p className="font-mono text-[10px] font-medium uppercase tracking-[0.1em] text-muted-foreground">
        Ganz Oldenburg · Beschlüsse der letzten zwei Jahre
      </p>
      <p id="viertel-stadt-titel" className={cn("mt-2 font-display font-bold leading-none tracking-tight tabular-nums", kompakt ? "text-[34px]" : "text-[40px] sm:text-[52px]")}>
        {data.total}
        <span className={cn("ml-2 font-semibold tracking-normal text-muted-foreground", kompakt ? "text-[16px]" : "text-[18px] sm:text-[20px]")}>Vorhaben</span>
      </p>
      <p className="mt-2 text-sm text-muted-foreground">
        in {belegt} von {orte.length} Ortsbereichen{data.updated_at ? ` · Stand ${formatDate(data.updated_at.slice(0, 10))}` : ""}
      </p>
      <dl className="mt-4 flex flex-wrap gap-x-6 gap-y-3">
        {(["building", "decided", "planning"] as const).map((st) => (
          <div key={st} className="min-w-0">
            <dt className="flex items-center gap-1.5 text-[11.5px] leading-none text-muted-foreground">
              <span className="h-2 w-2 rounded-full" style={{ background: STAND_FARBE[st] }} aria-hidden />
              {STAND[st].label}
            </dt>
            <dd className={cn("mt-1.5 font-display font-bold leading-none tracking-tight tabular-nums", kompakt ? "text-[19px]" : "text-[21px] sm:text-[27px]")}>
              {data.stages[st] ?? 0}
            </dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

/** Die Knöpfe der eigenen Stadtteile (ein gewählter Stadtteil ist ein Thema). */
export function MeineKnoepfe({ meine, byName, ortHref }: {
  meine: { name: string; place_id: string }[]; byName: Map<string, { count: number }>; ortHref: OrtHref;
}) {
  if (!meine.length) return null;
  return (
    <div className="mt-3 flex flex-wrap gap-2">
      {meine.map((o) => (
        <Button key={o.place_id} asChild>
          <Link href={ortHref(o.place_id)}>
            <MapPinned className="h-4 w-4" /> {o.name}
            <span className="ml-1 rounded-full bg-primary-foreground/20 px-1.5 text-xs tabular-nums">{byName.get(o.name)?.count ?? 0}</span>
            <ArrowRight className="h-4 w-4" />
          </Link>
        </Button>
      ))}
    </div>
  );
}

/** „Gerade in der Stadt": die Vorhaben, die stadtweit herausstechen. */
export function Highlights({ data, ortHref, kompakt }: { data: Uebersicht; ortHref: OrtHref; kompakt?: boolean }) {
  return (
    <section aria-labelledby="viertel-highlights-titel" className="min-w-0">
      <div className="flex items-baseline justify-between gap-2">
        <h2 id="viertel-highlights-titel" className="font-display text-base font-bold text-foreground">Gerade in der Stadt</h2>
        <span className="font-mono text-[10px] font-medium uppercase tracking-[0.1em] text-muted-foreground">
          {data.highlights.length} von {data.total}
        </span>
      </div>
      <ol className="mt-2 divide-y divide-border rounded-2xl border border-border bg-card">
        {data.highlights.map((h, i) => (
          <li key={h.id} className={STAFFEL} style={staffelStil(i + 1)}>
            <Link href={ortHref(h.place_id, h.id)} className={cn("group flex items-center gap-3 transition-colors hover:bg-accent", kompakt ? "px-3 py-2.5" : "px-4 py-3")}>
              <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: STAND_FARBE[h.stage] ?? STAND_FARBE.planning }} aria-hidden />
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm font-semibold text-foreground">{h.name}</span>
                <span className="block truncate text-xs text-muted-foreground">
                  <span className="font-medium text-foreground/80">{h.place_name}</span>
                  {" · "}{STAND[h.stage]?.label ?? h.stage}{h.when ? ` · ${h.when}` : ""}
                </span>
              </span>
              <ArrowRight className="h-4 w-4 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5 group-hover:text-primary" />
            </Link>
          </li>
        ))}
        {data.highlights.length === 0 && (
          <li className="px-4 py-6 text-center text-sm text-muted-foreground">Noch kein Vorhaben im Register.</li>
        )}
      </ol>
    </section>
  );
}

/** Alle Ortsbereiche nach Zahl der Vorhaben, mit Balken. `spalten` steuert das Raster. */
export function Rangliste({ orte, ortHref, spalten = "grid-cols-1 @xl:grid-cols-2 @3xl:grid-cols-3", onHover }: {
  orte: Uebersicht["districts"]; ortHref: OrtHref; spalten?: string; onHover?: (name: string | null) => void;
}) {
  const rang = useMemo(() => [...orte].sort((a, b) => b.count - a.count || a.name.localeCompare(b.name, "de")), [orte]);
  const maxCount = rang[0]?.count ?? 0;
  return (
    <section aria-labelledby="viertel-rang-titel">
      <div className="flex items-baseline justify-between gap-2">
        <h2 id="viertel-rang-titel" className="font-display text-base font-bold text-foreground">Alle {orte.length} Ortsbereiche</h2>
        <span className="font-mono text-[10px] font-medium uppercase tracking-[0.1em] text-muted-foreground">nach Zahl der Vorhaben</span>
      </div>
      <ol className={cn("mt-2 grid gap-2", spalten)}>
        {rang.map((o, i) => (
          <li key={o.place_id} className={STAFFEL} style={staffelStil(i)}>
            <Link
              href={ortHref(o.place_id)}
              onMouseEnter={() => onHover?.(o.name)}
              onMouseLeave={() => onHover?.(null)}
              className={cn(
                "relative flex items-baseline justify-between gap-2 overflow-hidden rounded-lg border border-border px-3 py-2 text-sm transition-colors hover:bg-accent",
                o.count === 0 && "text-muted-foreground",
              )}
            >
              {/* Der Balken hinter der Zeile: Länge = Anteil am Spitzenwert. */}
              {o.count > 0 && maxCount > 0 && (
                <span aria-hidden className="absolute inset-y-0 left-0 bg-primary/[0.07]" style={{ width: `${Math.max(6, (100 * o.count) / maxCount)}%` }} />
              )}
              <span className="relative truncate font-medium">
                <span className="mr-1.5 inline-block w-5 text-right font-mono text-[10px] text-muted-foreground">{i + 1}</span>
                {o.name}
              </span>
              <span className="relative shrink-0 tabular-nums text-xs text-muted-foreground">
                {o.stages.building ? <span className="mr-1.5 inline-block h-1.5 w-1.5 rounded-full align-middle" style={{ background: STAND_FARBE.building }} title="im Bau" /> : null}
                {o.count}
              </span>
            </Link>
          </li>
        ))}
      </ol>
      <p className="mt-3 text-xs text-muted-foreground">
        Die Zahl nennt die Vorhaben der letzten zwei Jahre; der orange Punkt heißt: dort wird schon gebaut. Ortsbereiche ohne Zahl haben in dieser Zeit keinen Beschluss mit belegtem Ortsbezug.
      </p>
    </section>
  );
}

/** „Ich wohne in der …": Eingabe mit Vorschlägen — Stadtteil, Straße oder
 *  Platz, jeweils mit dem Ortsbereich dahinter. Die Vorschläge kommen vom
 *  Server (nur Orte, die je ein Beschluss genannt hat); Enter nimmt den
 *  markierten, Pfeile wandern, Escape schließt. Kein Sprachmodell. */
export function OrtSuche({ onWaehlen, className }: { onWaehlen: (placeId: string) => void; className?: string }) {
  const [wert, setWert] = useState("");
  const [frage, setFrage] = useState("");
  const [offen, setOffen] = useState(false);
  const [markiert, setMarkiert] = useState(0);
  const listeId = "ort-suche-liste";
  useEffect(() => {
    const t = setTimeout(() => setFrage(wert.trim()), 180);
    return () => clearTimeout(t);
  }, [wert]);
  const q = useQuery({
    queryKey: ["viertel-lookup", frage],
    queryFn: () => api.get<ApiAntwort<"/districts/lookup">>(`/districts/lookup?q=${encodeURIComponent(frage)}`),
    enabled: frage.length >= 2,
    staleTime: 5 * 60_000,
  });
  const treffer: Treffer[] = frage.length >= 2 ? (q.data?.matches ?? []) : [];
  useEffect(() => { setMarkiert(0); }, [treffer.length, frage]);

  function nehmen(t: Treffer) {
    setOffen(false);
    setWert(t.name);
    onWaehlen(t.place_id);
  }

  return (
    <div className={cn("relative", className)}>
      <div className="relative">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
        <Input
          value={wert}
          onChange={(e) => { setWert(e.target.value); setOffen(true); }}
          onFocus={() => setOffen(true)}
          onBlur={() => setTimeout(() => setOffen(false), 120)}
          onKeyDown={(e) => {
            if (!treffer.length) return;
            if (e.key === "ArrowDown") { e.preventDefault(); setMarkiert((m) => (m + 1) % treffer.length); }
            else if (e.key === "ArrowUp") { e.preventDefault(); setMarkiert((m) => (m - 1 + treffer.length) % treffer.length); }
            else if (e.key === "Enter") { e.preventDefault(); nehmen(treffer[markiert] ?? treffer[0]); }
            else if (e.key === "Escape") setOffen(false);
          }}
          placeholder="Straße oder Stadtteil, z. B. Nadorster Straße"
          aria-label="Straße oder Stadtteil"
          role="combobox"
          aria-expanded={offen && treffer.length > 0}
          aria-controls={listeId}
          aria-autocomplete="list"
          autoComplete="off"
          className="h-11 rounded-xl pl-9 pr-9"
        />
        {q.isFetching && <Spinner className="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2" />}
      </div>
      {offen && frage.length >= 2 && (
        <ul id={listeId} role="listbox" className="absolute left-0 right-0 z-20 mt-1 max-h-72 overflow-auto rounded-xl border border-border bg-card p-1 shadow-lg">
          {treffer.map((t, i) => (
            <li key={`${t.kind}-${t.name}-${t.place_id}`} role="option" aria-selected={i === markiert}>
              <button
                type="button"
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => nehmen(t)}
                onMouseEnter={() => setMarkiert(i)}
                className={cn("flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm", i === markiert ? "bg-accent text-foreground" : "text-foreground")}
              >
                <MapPinned className="h-3.5 w-3.5 shrink-0 text-primary" aria-hidden />
                <span className="min-w-0 flex-1 truncate">
                  {t.name}
                  {t.kind !== "district" && <span className="text-muted-foreground"> · liegt in {t.place_name}</span>}
                </span>
                <span className="shrink-0 tabular-nums text-xs text-muted-foreground">{t.count} Vorhaben</span>
              </button>
            </li>
          ))}
          {!treffer.length && !q.isFetching && (
            <li className="px-3 py-2 text-sm text-muted-foreground">
              Nichts gefunden — nur Straßen, die ein Beschluss nennt, sind dabei. Zeig auf der Karte oder nimm den Standort.
            </li>
          )}
        </ul>
      )}
    </div>
  );
}

/** „Meinen Standort nehmen": Der Browser fragt einmal nach, die Zuordnung zum
 *  Ortsbereich läuft im Browser gegen die Umrisse (`ortsbereichFor`) — die
 *  Koordinate verlässt das Gerät nicht. */
export function StandortKnopf({ onGefunden, className }: { onGefunden: (name: string) => void; className?: string }) {
  const [sucht, setSucht] = useState(false);
  const kann = typeof navigator !== "undefined" && "geolocation" in navigator;
  if (!kann) return null;
  function orten() {
    setSucht(true);
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        try {
          const features = await loadOrtsbereiche();
          const name = ortsbereichFor(pos.coords.latitude, pos.coords.longitude, features);
          if (name) onGefunden(name);
          else toast.error("Dein Standort liegt außerhalb Oldenburgs.");
        } finally {
          setSucht(false);
        }
      },
      () => { setSucht(false); toast.error("Der Standort ist gerade nicht verfügbar."); },
      { timeout: 10_000, maximumAge: 5 * 60_000 },
    );
  }
  return (
    <Button variant="secondary" size="sm" className={className} onClick={orten} disabled={sucht}>
      {sucht ? <Spinner className="h-4 w-4" /> : <LocateFixed className="h-4 w-4" />}
      Meinen Standort nehmen
    </Button>
  );
}

/* ----------------------------------------------------- Viertel-Stufe --- */

/** Die Stufenleiste als Filter: nur Stände, die es gibt, mit Zähler. */
export function StandChips({ zaehler, stufe, onStufe, className }: {
  zaehler: Map<string, number>; stufe: string | null; onStufe: (s: string | null) => void; className?: string;
}) {
  return (
    <div className={cn("flex gap-1.5 overflow-x-auto pb-1 [scrollbar-width:none]", className)} role="group" aria-label="Nach Stand filtern">
      {STUFEN.filter((s) => zaehler.get(s)).map((s) => {
        const an = stufe === s;
        return (
          <button
            key={s}
            type="button"
            aria-pressed={an}
            onClick={() => onStufe(an ? null : s)}
            className={cn(
              "inline-flex shrink-0 items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-semibold transition-colors",
              an ? "border-current text-foreground" : "border-border text-muted-foreground hover:text-foreground",
            )}
          >
            <span className="h-2 w-2 rounded-full" style={{ background: STAND_FARBE[s] }} aria-hidden />
            {STAND[s].label}
            <span className="tabular-nums opacity-70">{zaehler.get(s)}</span>
          </button>
        );
      })}
    </div>
  );
}

/** Demnächst im Rat: der Haken für „Mitreden" — da wird entschieden, und in
 *  der Einwohnerfragestunde darf man fragen. */
export function DemnaechstKarte({ items, className, style }: { items: Tafel["upcoming"]; className?: string; style?: React.CSSProperties }) {
  if (!items.length) return null;
  return (
    <Card className={cn("border-signal/30 bg-signal/5 p-4", className)} style={style}>
      <h2 className="flex items-center gap-2 font-display text-base font-bold text-foreground">
        <CalendarDays className="h-4 w-4 text-signal" /> Demnächst im Rat
      </h2>
      <ul className="mt-2 space-y-2">
        {items.map((u) => (
          <li key={u.id}>
            <Link href={sitzungHref(u.ksinr, u.item_number ? [u.item_number] : undefined)} className="block rounded-lg px-2 py-1.5 transition-colors hover:bg-accent">
              <p className="text-xs text-muted-foreground">
                {formatDate(u.session_date)}{u.session_time ? `, ${u.session_time} Uhr` : ""} · {shortCommittee(u.committee ?? "")}
              </p>
              <p className="mt-0.5 text-sm font-medium text-foreground">{u.title}</p>
            </Link>
          </li>
        ))}
      </ul>
    </Card>
  );
}

export function BeteiligungKarte({ items, className, style }: { items: Tafel["participations"]; className?: string; style?: React.CSSProperties }) {
  if (!items.length) return null;
  return (
    <Card className={cn("p-4", className)} style={style}>
      <h2 className="flex items-center gap-2 font-display text-base font-bold text-foreground">
        <Megaphone className="h-4 w-4 text-primary" /> Mitreden — Beteiligung läuft
      </h2>
      <ul className="mt-2 space-y-2 text-sm">
        {items.map((b, i) => (
          <li key={i}>
            <a href={b.url ?? "#"} target="_blank" rel="noreferrer" className="font-medium text-primary hover:underline">{b.title}</a>
            <span className="text-muted-foreground"> — {b.step}{b.valid_until ? `, bis ${formatDate(b.valid_until)}` : ""}</span>
            {b.geometry ? <span className="ml-1 text-xs text-muted-foreground">· Fläche auf der Karte</span> : null}
          </li>
        ))}
      </ul>
    </Card>
  );
}

/** Sperrungen der Stadt (Geoportal): Kontext zum Viertel, kein Vorhaben —
 *  deshalb eine eigene Karte in Warnfarbe und auf der Karte gestrichelt. */
export function SperrungenKarte({ items, className, style }: { items: Tafel["closures"]; className?: string; style?: React.CSSProperties }) {
  if (!items.length) return null;
  return (
    <Card className={cn("border-amber-700/25 bg-amber-50/60 p-4 dark:bg-amber-950/20", className)} style={style}>
      <h2 className="flex items-center gap-2 font-display text-base font-bold text-foreground">
        <TrafficCone className="h-4 w-4 text-amber-700" /> Gesperrt und im Bau
      </h2>
      <ul className="mt-2 divide-y divide-amber-700/15 text-sm">
        {items.map((c) => (
          <li key={c.id} className="py-2">
            <p className="font-medium text-foreground">
              {c.street}
              {c.kind_label && <span className="ml-2 rounded-full bg-amber-700/10 px-2 py-0.5 text-[11px] font-semibold text-amber-800 dark:text-amber-300">{c.kind_label}</span>}
            </p>
            <p className="text-xs text-muted-foreground">
              {c.reason}{c.valid_until ? ` · bis ${formatDate(c.valid_until)}` : c.valid_from ? ` · seit ${formatDate(c.valid_from)}` : ""}
            </p>
          </li>
        ))}
      </ul>
      <p className="mt-2 text-[11px] text-muted-foreground">Stand der Verkehrsbehörde, Stadt Oldenburg (Geoportal). Kleine Tagesbaustellen stehen dort nicht.</p>
    </Card>
  );
}

export function InvestitionenKarte({ items, className }: { items: Tafel["investments"]; className?: string }) {
  if (!items.length) return null;
  return (
    <Card className={cn("p-4", className)}>
      <h2 className="flex items-center gap-2 font-display text-base font-bold text-foreground">
        <Hammer className="h-4 w-4 text-primary" /> Im Investitionsprogramm {items[0].programme_year}
      </h2>
      <p className="mt-1 text-xs text-muted-foreground">Straßen und Plätze dieses Viertels, für die die Stadt Geld eingeplant hat — Summe über die Programmjahre.</p>
      <ul className="mt-2 divide-y divide-border text-sm">
        {items.map((i) => (
          <li key={i.code ?? i.label} className="flex items-baseline justify-between gap-3 py-1.5">
            <span className="text-foreground">{i.label}</span>
            <span className="shrink-0 tabular-nums text-muted-foreground">{formatEuro(i.total_eur)}</span>
          </li>
        ))}
      </ul>
    </Card>
  );
}

/** Aktuelles von der Stadt (Designsprache: Presse-Block — extern, nie wie
 *  Beschlüsse gestylt): die Pressemitteilungen, die diesen Ortsbereich
 *  nennen, regelbasiert verortet (council/presse_orte.py). */
export function PresseBlock({ items, className, style }: { items: Tafel["press"]; className?: string; style?: React.CSSProperties }) {
  if (!items.length) return null;
  return (
    <section className={className} style={style} aria-labelledby="viertel-presse-titel">
      <div className="flex items-baseline justify-between gap-2">
        <h2 id="viertel-presse-titel" className="flex items-center gap-2 font-display text-base font-bold text-foreground">
          <Newspaper className="h-4 w-4 text-primary" /> Aktuelles von der Stadt
        </h2>
        <span className="font-mono text-[10px] font-medium uppercase tracking-[0.1em] text-muted-foreground">Pressemitteilungen · letzte 4 Monate</span>
      </div>
      <ul className="mt-2 divide-y divide-dashed divide-border rounded-2xl border border-dashed border-border bg-card">
        {items.map((p) => (
          <li key={p.id}>
            <a href={p.url} target="_blank" rel="noreferrer" className="group flex items-start gap-3 px-4 py-3 transition-colors hover:bg-accent">
              <span className="min-w-0 flex-1">
                <span className="block text-sm font-medium text-foreground group-hover:underline">{p.title}</span>
                <span className="block text-xs text-muted-foreground">
                  {p.date ? formatDate(p.date) : ""}{p.evidence ? ` · ${p.evidence}` : ""} · oldenburg.de
                </span>
              </span>
              <ExternalLink className="mt-1 h-3.5 w-3.5 shrink-0 text-muted-foreground" />
            </a>
          </li>
        ))}
      </ul>
    </section>
  );
}

export function Nachbarn({ nachbarn, ortHref }: { nachbarn: Tafel["neighbours"]; ortHref: OrtHref }) {
  return (
    <div className="flex flex-wrap justify-center gap-2">
      {nachbarn.map((n) => (
        <Button key={n.place_id} asChild variant="secondary" size="sm">
          <Link href={ortHref(n.place_id)}>{n.name} <span className="ml-1 tabular-nums text-muted-foreground">{n.count}</span></Link>
        </Button>
      ))}
    </div>
  );
}

export const QUELLEN_HINWEIS = "Die Vorhaben stammen aus den öffentlichen Beschlüssen des Oldenburger Stadtrats der letzten zwei Jahre. Ein Sprachmodell prüft je Beschluss, ob er wirklich dieses Viertel betrifft, und fasst zusammengehörige Beschlüsse zu einem Vorhaben zusammen. Termine stehen nur, wenn ein Beschluss sie nennt. Ratslotse ist kein Angebot der Stadt.";

/** Eine Zeile der Liste unter der Karte — knapp: Farbpunkt, Name, Termin. */
export function VorhabenZeile({ v, aktiv, schwebt, onClick, onHover }: {
  v: Vorhaben; aktiv: boolean; schwebt?: boolean; onClick: () => void; onHover?: (an: boolean) => void;
}) {
  const stand = STAND[v.stage] ?? STAND.planning;
  return (
    <li>
      <button
        type="button"
        onClick={onClick}
        onMouseEnter={() => onHover?.(true)}
        onMouseLeave={() => onHover?.(false)}
        onFocus={() => onHover?.(true)}
        onBlur={() => onHover?.(false)}
        aria-pressed={aktiv}
        className={cn(
          "flex w-full items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-accent",
          aktiv && "bg-primary/5",
          schwebt && !aktiv && "bg-accent",
        )}
      >
        <span className={cn("h-2.5 w-2.5 shrink-0 rounded-full transition-transform", (schwebt || aktiv) && "scale-125")} style={{ background: STAND_FARBE[v.stage] }} aria-hidden />
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm font-semibold text-foreground">{v.name}</span>
          <span className="block truncate text-xs text-muted-foreground">
            {stand.label}{v.when ? ` · ${v.when}` : ""} · {KATEGORIE[v.category] ?? KATEGORIE.other}
          </span>
        </span>
        <ArrowRight className={cn("h-4 w-4 shrink-0 text-muted-foreground transition-transform", aktiv && "translate-x-0.5 text-primary")} />
      </button>
    </li>
  );
}

/** Die Liste der Vorhaben — mit Filter-Leerzustand. */
export function VorhabenListe({ sichtbar, aktiv, schwebt, onAktiv, onSchwebt, className, style }: {
  sichtbar: Vorhaben[]; aktiv: number | null; schwebt: number | null;
  onAktiv: (id: number | null) => void; onSchwebt: (id: number | null) => void; className?: string; style?: React.CSSProperties;
}) {
  return (
    <ol className={cn("divide-y divide-border rounded-2xl border border-border bg-card", className)} style={style}>
      {sichtbar.map((v) => (
        <VorhabenZeile key={v.id} v={v} aktiv={v.id === aktiv} schwebt={v.id === schwebt}
          onClick={() => onAktiv(v.id === aktiv ? null : v.id)}
          onHover={(an) => onSchwebt(an ? v.id : null)} />
      ))}
      {sichtbar.length === 0 && (
        <li className="px-4 py-6 text-center text-sm text-muted-foreground">Kein Vorhaben in dieser Stufe.</li>
      )}
    </ol>
  );
}

export function VorhabenDetail({ v, angemeldet, gemeldet, onMelden, onSchliessen, schliessenSichtbar }: {
  v: Vorhaben; angemeldet: boolean; gemeldet: boolean; onMelden: () => void; onSchliessen: () => void;
  /** Der Schließen-Knopf: auf `/viertel` nur in der Seitenspalte (`@3xl`),
   *  auf der Karte immer — dort ist das Detail nie ein Sheet mit Griff. */
  schliessenSichtbar?: "immer" | "breit";
}) {
  const stand = STAND[v.stage] ?? STAND.planning;
  const erreicht = WEG.indexOf(v.stage as (typeof WEG)[number]);
  return (
    <div>
      <div className="flex items-start justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          <Badge color={stand.color}>{stand.label}</Badge>
          {v.when && <span className="font-semibold text-signal">{v.when}</span>}
          <span>{KATEGORIE[v.category] ?? KATEGORIE.other}</span>
        </div>
        <button type="button" onClick={onSchliessen} className={cn("rounded-md p-1 text-muted-foreground hover:text-foreground", schliessenSichtbar === "immer" ? "block" : "hidden @3xl:block")} aria-label="Detail schließen">
          <X className="h-4 w-4" />
        </button>
      </div>
      <h3 className="mt-2 font-display text-xl font-bold leading-snug text-foreground">{v.name}</h3>
      <p className="mt-2 text-sm leading-relaxed text-foreground/90">{v.what}</p>

      {v.stage !== "rejected" && (
        <ol className="mt-4 flex items-center gap-1" aria-label="Stand des Vorhabens">
          {WEG.map((s, i) => {
            const voll = i <= erreicht;
            return (
              <li key={s} className="flex flex-1 items-center gap-1">
                <span
                  className={cn("flex h-5 w-5 shrink-0 items-center justify-center rounded-full border text-[10px]", voll ? "border-transparent text-white" : "border-border text-muted-foreground")}
                  style={voll ? { background: STAND_FARBE[s] } : undefined}
                  title={STAND[s].label}
                >
                  {voll ? <Check className="h-3 w-3" /> : null}
                </span>
                {i < WEG.length - 1 && <span className={cn("h-0.5 flex-1 rounded", i < erreicht ? "bg-primary/60" : "bg-border")} />}
              </li>
            );
          })}
        </ol>
      )}

      {v.locations.length > 0 && (() => {
        // Gegenstand, Abschnittsgrenzen und Bezugsstraßen getrennt:
        // „Tweelbäker Tredde · Abschnitt: Am Schmeel, Brahmweg" bzw.
        // „Quartier am Krusenbusch · Umfeld: Am Schmeel, Brahmweg" — weder
        // Grenzen noch Umfeld sind betroffen.
        const gegenstand = v.locations.filter((l) => l.role === "subject").map((l) => l.name);
        const grenzen = v.locations.filter((l) => l.role === "boundary").map((l) => l.name);
        const umfeld = v.locations.filter((l) => l.role === "context").map((l) => l.name);
        return (
          <p className="mt-3 text-xs text-muted-foreground">
            <MapPinned className="mr-1 inline h-3.5 w-3.5 align-[-2px]" />
            {gegenstand.length > 0 ? gegenstand.join(" · ") : "Fläche"}
            {grenzen.length > 0 && <span className="opacity-80"> · {gegenstand.length > 0 ? "Abschnitt" : "zwischen"}: {grenzen.join(", ")}</span>}
            {umfeld.length > 0 && <span className="opacity-80"> · Umfeld: {umfeld.join(", ")}</span>}
          </p>
        );
      })()}

      {/* Der Bebauungsplan hinter der Fläche: Nummer, Name, die drei Stationen
          des Verfahrens — aus den offenen Geodaten der Stadt, nicht aus dem
          Modell. Die Fläche auf der Karte ist sein Geltungsbereich. */}
      {v.locations.filter((l) => l.plan).map((l) => (
        <div key={l.slug} className="mt-3 rounded-lg border border-dashed border-border bg-muted/40 px-3 py-2 text-xs">
          <p className="font-semibold text-foreground">Bebauungsplan {l.plan!.nr} <span className="font-normal text-muted-foreground">· {l.plan!.name}</span></p>
          <p className="mt-1 text-muted-foreground">
            {[
              l.plan!.status === "in_procedure" && "In Aufstellung",
              l.plan!.resolution_date && `Aufstellung ${formatDate(l.plan!.resolution_date)}`,
              l.plan!.adoption_date && `Satzung ${formatDate(l.plan!.adoption_date)}`,
              l.plan!.effective_date && `rechtskräftig seit ${formatDate(l.plan!.effective_date)}`,
            ].filter(Boolean).join(" · ")}
          </p>
          <p className="mt-1 text-[11px] text-muted-foreground">
            Fläche: Geltungsbereich laut <a href={l.plan!.source_url} target="_blank" rel="noreferrer" className="underline hover:text-foreground">{l.plan!.source}</a>
          </p>
        </div>
      ))}

      <p className="mt-4 text-xs font-medium uppercase tracking-wider text-muted-foreground">
        {v.decisions.length} {v.decisions.length === 1 ? "Beschluss" : "Beschlüsse"}
      </p>
      <ul className="mt-1 divide-y divide-border">
        {v.decisions.map((d) => (
          <li key={d.id}>
            <Link href={decisionHref(d.id)} className="group flex items-start justify-between gap-3 py-2 text-sm">
              <span className="min-w-0">
                <span className="block text-foreground group-hover:underline">{d.title}</span>
                <span className="block text-xs text-muted-foreground">{formatDate(d.date)} · {shortCommittee(d.committee ?? "")}{d.outcome ? ` · ${OUTCOME_META[d.outcome as DecisionOutcome]?.label ?? d.outcome}` : ""}</span>
              </span>
              <ArrowRight className="mt-1 h-3.5 w-3.5 shrink-0 text-muted-foreground" />
            </Link>
          </li>
        ))}
      </ul>

      {angemeldet && (
        <div className="mt-4 border-t border-border pt-3 text-xs">
          {gemeldet ? (
            <span className="inline-flex items-center gap-1 text-muted-foreground"><Flag className="h-3 w-3" /> Gemeldet — danke.</span>
          ) : (
            <button type="button" onClick={onMelden} className="inline-flex items-center gap-1 text-muted-foreground hover:text-foreground">
              <Flag className="h-3 w-3" /> Gehört nicht hierher
            </button>
          )}
        </div>
      )}
    </div>
  );
}

/** Der Tafel-Zustand, den `/viertel` und `/karte` teilen: Stufe, aktives
 *  Vorhaben, Hover, gemeldet — und die Handlung „Gehört nicht hierher". */
export function useTafelZustand(data: Tafel | undefined, vorgewaehlt: number | null) {
  const [gemeldet, setGemeldet] = useState<Set<string>>(new Set());
  const [stufe, setStufe] = useState<string | null>(null);
  const [aktiv, setAktiv] = useState<number | null>(vorgewaehlt);
  const [schwebt, setSchwebt] = useState<number | null>(null);
  const vorhaben = useMemo(() => sortiert(data?.projects ?? []), [data]);
  const zaehler = useMemo(() => {
    const m = new Map<string, number>();
    for (const v of vorhaben) m.set(v.stage, (m.get(v.stage) ?? 0) + 1);
    return m;
  }, [vorhaben]);
  const sichtbar = stufe ? vorhaben.filter((v) => v.stage === stufe) : vorhaben;
  const gedimmt = useMemo(() => new Set(vorhaben.filter((v) => stufe && v.stage !== stufe).map((v) => v.id)), [vorhaben, stufe]);
  const ausgewaehlt = vorhaben.find((v) => v.id === aktiv) ?? null;

  async function melden(v: Vorhaben) {
    try {
      const r = await api.post<{ ok: boolean; hidden: boolean }>(`/districts/projects/${v.id}/report`, { reason: null });
      setGemeldet((s) => new Set(s).add(v.project_key));
      toast.success(r.hidden ? "Danke — das Vorhaben ist jetzt ausgeblendet." : "Danke, wir prüfen das.");
    } catch {
      /* die API hat schon einen Toast gezeigt */
    }
  }

  return { vorhaben, zaehler, sichtbar, gedimmt, ausgewaehlt, stufe, setStufe, aktiv, setAktiv, schwebt, setSchwebt, gemeldet, melden };
}
