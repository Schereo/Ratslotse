"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, CalendarDays, ChevronDown, Flag, Hammer, MapPinned, Megaphone } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { ApiAntwort } from "@/lib/vertrag";
import type { Topic } from "@/lib/types";
import { decisionHref, sitzungHref, viertelHref } from "@/lib/routes";
import { shortCommittee } from "@/lib/committees";
import { cn, formatDate } from "@/lib/utils";
import { Badge, Button, Card, DetailSkeleton, EmptyState, PageHeader, toast } from "@/components/ui";
import { ShareButton } from "@/components/share-button";
import { StadtteilKarte } from "@/components/stadtteil-karte";
import { Mascot } from "@/components/mascot";
import { formatEuro } from "@/components/decision-ui";
import { STAFFEL, staffelStil } from "@/components/staffel";

/** „Mein Viertel": Was sich in einem Ortsbereich in den nächsten Jahren ändert.
 *
 *  Die Tafel zeigt VORHABEN, nicht Beschlüsse: Ausschuss und Rat,
 *  Aufstellungs- und Satzungsbeschluss, Bericht und Antrag zum selben
 *  Gegenstand sind eine Karte mit Stand (Idee → Planung → beschlossen → im
 *  Bau → fertig). Gerechnet wird das im Backend (`council/viertel.py`) —
 *  hier wird nur gelesen, plus die eine Handlung „Gehört nicht hierher".
 *
 *  Öffentlich lesbar (`OEFFENTLICHE_PFADE`): Der Link zur Tafel ist der, den
 *  man der Nachbarin schickt. Ohne `?id=` steht die Auswahl — Karte und Liste
 *  der 31 Ortsbereiche mit der Zahl ihrer Vorhaben.
 */
type Tafel = ApiAntwort<"/districts/{place_id}/projects">;
type Uebersicht = ApiAntwort<"/districts/projects">;
type Vorhaben = Tafel["projects"][number];

/** Reihenfolge und Beschriftung der Stände — was gerade passiert, zuerst. */
const STAND: Record<string, { label: string; color: "amber" | "green" | "blue" | "slate" | "red"; rang: number }> = {
  building: { label: "Im Bau", color: "amber", rang: 0 },
  decided: { label: "Beschlossen", color: "green", rang: 1 },
  planning: { label: "In Planung", color: "blue", rang: 2 },
  idea: { label: "Idee", color: "slate", rang: 3 },
  done: { label: "Fertig", color: "slate", rang: 4 },
  rejected: { label: "Abgelehnt", color: "red", rang: 5 },
};
const KATEGORIE: Record<string, string> = {
  housing: "Wohnen & Bauen", traffic: "Verkehr", school_childcare: "Schule & Kita",
  green: "Grün & Umwelt", culture_sport_social: "Kultur, Sport & Soziales", other: "Sonstiges",
};

export default function ViertelView() {
  const id = useSearchParams().get("id");
  return id ? <VorhabenTafel placeId={id} /> : <ViertelAuswahl />;
}

/* -------------------------------------------------------------- Auswahl --- */

function useMeineOrtsbereiche(orte: { name: string; place_id: string }[] | undefined) {
  const { user } = useAuth();
  const topics = useQuery({ queryKey: ["topics"], queryFn: () => api.get<Topic[]>("/topics"), enabled: !!user });
  return useMemo(() => {
    if (!topics.data || !orte) return [] as { name: string; place_id: string }[];
    // Ein gewählter Stadtteil IST ein Thema (Einrichtungs-Assistent, Schritt 2) —
    // abgeleitet statt gemerkt, wie dort.
    return orte.filter((o) => topics.data.some((t) => t.name.toLowerCase() === o.name.toLowerCase()));
  }, [topics.data, orte]);
}

function ViertelAuswahl() {
  const router = useRouter();
  const q = useQuery({ queryKey: ["viertel-uebersicht"], queryFn: () => api.get<Uebersicht>("/districts/projects") });
  const orte = q.data?.districts;
  const meine = useMeineOrtsbereiche(orte);
  const byName = useMemo(() => new Map((orte ?? []).map((o) => [o.name, o])), [orte]);
  const mitVorhaben = useMemo(() => new Set((orte ?? []).filter((o) => o.count > 0).map((o) => o.name)), [orte]);

  if (q.isLoading) return <DetailSkeleton />;
  if (!orte) return <EmptyState title="Die Übersicht lässt sich gerade nicht laden." mascot="confused" />;

  return (
    <div className="mx-auto max-w-4xl">
      <PageHeader
        title="Mein Viertel"
        description="Was sich in deinem Ortsbereich in den nächsten Jahren ändert — Vorhaben aus den Beschlüssen des Stadtrats, gebündelt und gegengeprüft."
      />
      {meine.length > 0 && (
        <div className={cn("mt-4 flex flex-wrap gap-2", STAFFEL)} style={staffelStil(0)}>
          {meine.map((o) => (
            <Button key={o.place_id} asChild>
              <Link href={viertelHref(o.place_id)}>
                <MapPinned className="h-4 w-4" /> {o.name}
                <span className="ml-1 rounded-full bg-primary-foreground/20 px-1.5 text-xs">{byName.get(o.name)?.count ?? 0}</span>
              </Link>
            </Button>
          ))}
        </div>
      )}
      <div className={cn("mt-6 grid gap-6 @3xl:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)]", STAFFEL)} style={staffelStil(1)}>
        <Card className="p-3">
          <StadtteilKarte
            gewaehlt={new Set(meine.map((o) => o.name))}
            auswaehlbar={mitVorhaben}
            onWaehlen={(name) => { const o = byName.get(name); if (o) router.push(viertelHref(o.place_id)); }}
          />
        </Card>
        <ul className="grid grid-cols-2 gap-2 self-start sm:grid-cols-3 @3xl:grid-cols-2">
          {orte.map((o, i) => (
            <li key={o.place_id} className={STAFFEL} style={staffelStil(i)}>
              <Link
                href={viertelHref(o.place_id)}
                className={cn(
                  "flex items-baseline justify-between gap-2 rounded-lg border border-border px-3 py-2 text-sm transition-colors hover:bg-accent",
                  o.count === 0 && "text-muted-foreground",
                )}
              >
                <span className="truncate font-medium">{o.name}</span>
                <span className="shrink-0 tabular-nums text-xs text-muted-foreground">{o.count}</span>
              </Link>
            </li>
          ))}
        </ul>
      </div>
      <p className="mt-4 text-xs text-muted-foreground">
        Die Zahl nennt die Vorhaben der letzten zwei Jahre. Ortsbereiche ohne Zahl haben in dieser Zeit keinen Beschluss mit belegtem Ortsbezug.
      </p>
    </div>
  );
}

/* ---------------------------------------------------------------- Tafel --- */

function VorhabenTafel({ placeId }: { placeId: string }) {
  const { user } = useAuth();
  const q = useQuery({
    queryKey: ["viertel", placeId],
    queryFn: () => api.get<Tafel>(`/districts/${encodeURIComponent(placeId)}/projects`),
  });
  const [gemeldet, setGemeldet] = useState<Set<string>>(new Set());

  if (q.isLoading) return <DetailSkeleton />;
  const data = q.data;
  if (!data) return <EmptyState title="Diesen Ortsbereich gibt es nicht." mascot="search" action={<Button asChild variant="secondary"><Link href={viertelHref()}>Zur Auswahl</Link></Button>} />;

  const place = data.place as { id: string; name: string; description?: string | null };
  const vorhaben = [...data.projects].sort((a, b) => (STAND[a.stage]?.rang ?? 9) - (STAND[b.stage]?.rang ?? 9) || (b.last_date ?? "").localeCompare(a.last_date ?? ""));
  const laufend = vorhaben.filter((v) => v.stage !== "done" && v.stage !== "rejected");
  const vorbei = vorhaben.filter((v) => v.stage === "done" || v.stage === "rejected");

  async function melden(v: Vorhaben) {
    try {
      const r = await api.post<{ ok: boolean; hidden: boolean }>(`/districts/projects/${v.id}/report`, { reason: null });
      setGemeldet((s) => new Set(s).add(v.project_key));
      toast.success(r.hidden ? "Danke — das Vorhaben ist jetzt ausgeblendet." : "Danke, wir prüfen das.");
    } catch {
      /* die API hat schon einen Toast gezeigt */
    }
  }

  return (
    <div className="mx-auto max-w-3xl">
      <div className="print-hidden flex items-center justify-between gap-3">
        <Link href={viertelHref()} className="text-sm text-muted-foreground hover:text-foreground">← Alle Ortsbereiche</Link>
        <ShareButton path={viertelHref(place.id)} title={`Mein Viertel: ${place.name} — Ratslotse`} />
      </div>

      <header className="mt-4 flex items-start gap-3">
        <span className="rounded-xl bg-primary/10 p-2.5 text-primary"><MapPinned className="h-6 w-6" /></span>
        <div className="min-w-0">
          <p className="text-xs font-medium uppercase tracking-wider text-primary">Mein Viertel</p>
          <h1 className="mt-0.5 font-display text-2xl font-bold text-foreground">{place.name}</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {vorhaben.length === 0
              ? "Noch kein Vorhaben aus den Beschlüssen der letzten zwei Jahre."
              : `${vorhaben.length} ${vorhaben.length === 1 ? "Vorhaben" : "Vorhaben"} aus den Beschlüssen der letzten zwei Jahre` +
                (data.updated_at ? ` · Stand ${formatDate(data.updated_at.slice(0, 10))}` : "")}
          </p>
        </div>
      </header>

      {/* Demnächst im Rat: der Haken für „Mitreden" — da wird entschieden, und
          in der Einwohnerfragestunde darf man fragen. */}
      {data.upcoming.length > 0 && (
        <Card className={cn("mt-6 border-signal/30 bg-signal/5 p-4", STAFFEL)} style={staffelStil(0)}>
          <h2 className="flex items-center gap-2 font-display text-base font-bold text-foreground">
            <CalendarDays className="h-4 w-4 text-signal" /> Demnächst im Rat
          </h2>
          <ul className="mt-2 space-y-2">
            {data.upcoming.map((u) => (
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
      )}

      {data.participations.length > 0 && (
        <Card className={cn("mt-4 p-4", STAFFEL)} style={staffelStil(1)}>
          <h2 className="flex items-center gap-2 font-display text-base font-bold text-foreground">
            <Megaphone className="h-4 w-4 text-primary" /> Mitreden — Beteiligung läuft
          </h2>
          <ul className="mt-2 space-y-2 text-sm">
            {data.participations.map((b, i) => (
              <li key={i}>
                <a href={b.url ?? "#"} target="_blank" rel="noreferrer" className="font-medium text-primary hover:underline">{b.title}</a>
                <span className="text-muted-foreground"> — {b.step}{b.valid_until ? `, bis ${formatDate(b.valid_until)}` : ""}</span>
              </li>
            ))}
          </ul>
        </Card>
      )}

      {vorhaben.length === 0 ? (
        <div className="mt-8 flex flex-col items-center gap-3 rounded-xl border-2 border-dashed border-border px-4 py-8 text-center">
          <Mascot pose="search" decorative className="h-16 w-16" />
          <p className="max-w-md text-sm text-muted-foreground">
            Für {place.name} hat der Rat in den letzten zwei Jahren nichts beschlossen, was sich als Vorhaben zeigen ließe. Nebenan ist mehr los:
          </p>
          <Nachbarn nachbarn={data.neighbours} />
        </div>
      ) : (
        <ol className="mt-6 space-y-3">
          {laufend.map((v, i) => (
            <VorhabenKarte key={v.id} v={v} i={i} angemeldet={!!user} gemeldet={gemeldet.has(v.project_key) || v.reported} onMelden={() => melden(v)} />
          ))}
          {vorbei.length > 0 && (
            <li className="pt-3">
              <p className="px-1 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground/70">Erledigt oder abgelehnt</p>
            </li>
          )}
          {vorbei.map((v, i) => (
            <VorhabenKarte key={v.id} v={v} i={laufend.length + i} angemeldet={!!user} gemeldet={gemeldet.has(v.project_key) || v.reported} onMelden={() => melden(v)} />
          ))}
        </ol>
      )}

      {data.investments.length > 0 && (
        <Card className="mt-6 p-4">
          <h2 className="flex items-center gap-2 font-display text-base font-bold text-foreground">
            <Hammer className="h-4 w-4 text-primary" /> Im Investitionsprogramm {data.investments[0].programme_year}
          </h2>
          <p className="mt-1 text-xs text-muted-foreground">Straßen und Plätze dieses Viertels, für die die Stadt Geld eingeplant hat — Summe über die Programmjahre.</p>
          <ul className="mt-2 divide-y divide-border text-sm">
            {data.investments.map((i) => (
              <li key={i.code ?? i.label} className="flex items-baseline justify-between gap-3 py-1.5">
                <span className="text-foreground">{i.label}</span>
                <span className="shrink-0 tabular-nums text-muted-foreground">{formatEuro(i.total_eur)}</span>
              </li>
            ))}
          </ul>
        </Card>
      )}

      {vorhaben.length > 0 && data.neighbours.length > 0 && (
        <div className="mt-8 border-t border-border pt-4">
          <p className="mb-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">Nebenan</p>
          <Nachbarn nachbarn={data.neighbours} />
        </div>
      )}

      <p className="mt-8 text-xs leading-relaxed text-muted-foreground">
        Die Vorhaben stammen aus den öffentlichen Beschlüssen des Oldenburger Stadtrats der letzten zwei Jahre. Ein Sprachmodell prüft je Beschluss, ob er wirklich dieses Viertel betrifft, und fasst zusammengehörige Beschlüsse zu einem Vorhaben zusammen. Termine stehen nur, wenn ein Beschluss sie nennt. Ratslotse ist kein Angebot der Stadt.
      </p>
    </div>
  );
}

function Nachbarn({ nachbarn }: { nachbarn: Tafel["neighbours"] }) {
  return (
    <div className="flex flex-wrap justify-center gap-2">
      {nachbarn.map((n) => (
        <Button key={n.place_id} asChild variant="secondary" size="sm">
          <Link href={viertelHref(n.place_id)}>{n.name} <span className="ml-1 tabular-nums text-muted-foreground">{n.count}</span></Link>
        </Button>
      ))}
    </div>
  );
}

function VorhabenKarte({ v, i, angemeldet, gemeldet, onMelden }: {
  v: Vorhaben; i: number; angemeldet: boolean; gemeldet: boolean; onMelden: () => void;
}) {
  const [offen, setOffen] = useState(false);
  const stand = STAND[v.stage] ?? STAND.planning;
  return (
    <li className={STAFFEL} style={staffelStil(i)}>
      <Card className={cn("p-4", (v.stage === "done" || v.stage === "rejected") && "opacity-80")}>
        <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          <Badge color={stand.color}>{stand.label}</Badge>
          {v.when && <span className="font-semibold text-signal">{v.when}</span>}
          <span className="ml-auto">{KATEGORIE[v.category] ?? KATEGORIE.other}</span>
        </div>
        <h3 className="mt-2 font-display text-lg font-bold leading-snug text-foreground">{v.name}</h3>
        <p className="mt-1 text-sm leading-relaxed text-foreground/90">{v.what}</p>
        <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs">
          <button
            type="button"
            onClick={() => setOffen((o) => !o)}
            aria-expanded={offen}
            className="inline-flex items-center gap-1 font-medium text-primary hover:underline"
          >
            {v.decisions.length} {v.decisions.length === 1 ? "Beschluss" : "Beschlüsse"}
            <ChevronDown className={cn("h-3.5 w-3.5 transition-transform", offen && "rotate-180")} />
          </button>
          {angemeldet && (
            gemeldet ? (
              <span className="inline-flex items-center gap-1 text-muted-foreground"><Flag className="h-3 w-3" /> Gemeldet</span>
            ) : (
              <button type="button" onClick={onMelden} className="inline-flex items-center gap-1 text-muted-foreground hover:text-foreground">
                <Flag className="h-3 w-3" /> Gehört nicht hierher
              </button>
            )
          )}
        </div>
        {offen && (
          <ul className="mt-2 divide-y divide-border border-t border-border">
            {v.decisions.map((d) => (
              <li key={d.id}>
                <Link href={decisionHref(d.id)} className="group flex items-start justify-between gap-3 py-2 text-sm">
                  <span className="min-w-0">
                    <span className="block text-foreground group-hover:underline">{d.title}</span>
                    <span className="block text-xs text-muted-foreground">{formatDate(d.date)} · {shortCommittee(d.committee ?? "")}{d.outcome ? ` · ${d.outcome}` : ""}</span>
                  </span>
                  <ArrowRight className="mt-1 h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </li>
  );
}
