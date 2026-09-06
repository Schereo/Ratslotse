"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, CalendarDays, Check, Flag, Hammer, MapPinned, Megaphone, X } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { ApiAntwort } from "@/lib/vertrag";
import type { Topic } from "@/lib/types";
import { decisionHref, sitzungHref, viertelHref } from "@/lib/routes";
import { shortCommittee } from "@/lib/committees";
import { cn, formatDate } from "@/lib/utils";
import { Badge, Button, Card, DetailSkeleton, EmptyState, PageHeader, Sheet, SheetContent, SheetTitle, toast } from "@/components/ui";
import { ViertelKarte, STAND_FARBE } from "@/components/viertel-karte";
import { ShareButton } from "@/components/share-button";
import { StadtteilKarte } from "@/components/stadtteil-karte";
import { Mascot } from "@/components/mascot";
import { formatEuro, OUTCOME_META } from "@/components/decision-ui";
import type { DecisionOutcome } from "@/lib/types";
import { STAFFEL, staffelStil } from "@/components/staffel";

/** „Mein Viertel": Was sich in einem Ortsbereich in den nächsten Jahren ändert.
 *
 *  Die Tafel zeigt VORHABEN, nicht Beschlüsse: Ausschuss und Rat,
 *  Aufstellungs- und Satzungsbeschluss, Bericht und Antrag zum selben
 *  Gegenstand sind eine Karte mit Stand (Idee → Planung → beschlossen → im
 *  Bau → fertig). Gerechnet wird das im Backend (`council/viertel.py`) —
 *  hier wird nur gelesen, plus die eine Handlung „Gehört nicht hierher".
 *
 *  **Die Karte ist die Bühne** (Tims Entscheidung 06.09.2026): Oben das
 *  Viertel mit einem Pin je Vorhaben, darunter die Stufenleiste als Filter
 *  und eine knappe Liste. Ein Pin oder eine Zeile öffnet das Detail — am
 *  Schreibtisch in der Seitenspalte, auf dem Telefon als Bottom-Sheet. Kein
 *  Seitwärts-Blättern: Karte und Wischen in einer Fläche wären zwei Gesten,
 *  die sich in die Quere kommen.
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

/** Reihenfolge der Stufenleiste: was gerade passiert, zuerst. */
const STUFEN = ["building", "decided", "planning", "idea", "done", "rejected"] as const;

function VorhabenTafel({ placeId }: { placeId: string }) {
  const { user } = useAuth();
  const q = useQuery({
    queryKey: ["viertel", placeId],
    queryFn: () => api.get<Tafel>(`/districts/${encodeURIComponent(placeId)}/projects`),
  });
  const [gemeldet, setGemeldet] = useState<Set<string>>(new Set());
  const [stufe, setStufe] = useState<string | null>(null);
  const [aktiv, setAktiv] = useState<number | null>(null);
  // Schreibtisch: Detail in der Seitenspalte. Telefon: Bottom-Sheet. Die
  // Grenze ist die Container-Breite des Rasters (@3xl), gemessen über
  // matchMedia auf dem Fenster — reicht, weil die Seite ohne Seitenleiste
  // dieselbe Breite hat wie der Container.
  const [breit, setBreit] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia("(min-width: 900px)");
    const h = () => setBreit(mq.matches);
    h(); mq.addEventListener("change", h);
    return () => mq.removeEventListener("change", h);
  }, []);

  if (q.isLoading) return <DetailSkeleton />;
  const data = q.data;
  if (!data) return <EmptyState title="Diesen Ortsbereich gibt es nicht." mascot="search" action={<Button asChild variant="secondary"><Link href={viertelHref()}>Zur Auswahl</Link></Button>} />;

  const place = data.place as { id: string; name: string; description?: string | null };
  const vorhaben = [...data.projects].sort((a, b) => (STAND[a.stage]?.rang ?? 9) - (STAND[b.stage]?.rang ?? 9) || (b.last_date ?? "").localeCompare(a.last_date ?? ""));
  const zaehler = new Map<string, number>();
  for (const v of vorhaben) zaehler.set(v.stage, (zaehler.get(v.stage) ?? 0) + 1);
  const sichtbar = stufe ? vorhaben.filter((v) => v.stage === stufe) : vorhaben;
  const gedimmt = new Set(vorhaben.filter((v) => stufe && v.stage !== stufe).map((v) => v.id));
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

  const detail = ausgewaehlt && (
    <VorhabenDetail
      v={ausgewaehlt}
      angemeldet={!!user}
      gemeldet={gemeldet.has(ausgewaehlt.project_key) || ausgewaehlt.reported}
      onMelden={() => melden(ausgewaehlt)}
      onSchliessen={() => setAktiv(null)}
    />
  );

  return (
    <div className="mx-auto max-w-5xl">
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
              : `${vorhaben.length} Vorhaben aus den Beschlüssen der letzten zwei Jahre` +
                (data.updated_at ? ` · Stand ${formatDate(data.updated_at.slice(0, 10))}` : "")}
          </p>
        </div>
      </header>

      <div className={cn("mt-5 grid gap-5", breit && ausgewaehlt && "grid-cols-[minmax(0,1fr)_360px]")}>
        <div className="min-w-0">
          {vorhaben.length > 0 && (
            <ViertelKarte
              ortsbereich={place.name}
              vorhaben={vorhaben}
              aktiv={aktiv}
              gedimmt={gedimmt}
              onSelect={setAktiv}
              className={cn(STAFFEL, "h-[280px] sm:h-[340px]")}
            />
          )}

          {vorhaben.length > 0 && (
            <div className={cn("mt-3 flex gap-1.5 overflow-x-auto pb-1 [scrollbar-width:none]", STAFFEL)} style={staffelStil(1)} role="group" aria-label="Nach Stand filtern">
              {STUFEN.filter((s) => zaehler.get(s)).map((s) => {
                const an = stufe === s;
                return (
                  <button
                    key={s}
                    type="button"
                    aria-pressed={an}
                    onClick={() => { setStufe(an ? null : s); setAktiv(null); }}
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
          )}

          {/* Demnächst im Rat: der Haken für „Mitreden" — da wird entschieden, und
              in der Einwohnerfragestunde darf man fragen. */}
          {data.upcoming.length > 0 && (
            <Card className={cn("mt-4 border-signal/30 bg-signal/5 p-4", STAFFEL)} style={staffelStil(2)}>
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
            <Card className={cn("mt-4 p-4", STAFFEL)} style={staffelStil(2)}>
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
            <div className="mt-6 flex flex-col items-center gap-3 rounded-xl border-2 border-dashed border-border px-4 py-8 text-center">
              <Mascot pose="search" decorative className="h-16 w-16" />
              <p className="max-w-md text-sm text-muted-foreground">
                Für {place.name} hat der Rat in den letzten zwei Jahren nichts beschlossen, was sich als Vorhaben zeigen ließe. Nebenan ist mehr los:
              </p>
              <Nachbarn nachbarn={data.neighbours} />
            </div>
          ) : (
            <ol className={cn("mt-4 divide-y divide-border rounded-2xl border border-border bg-card", STAFFEL)} style={staffelStil(3)}>
              {sichtbar.map((v) => (
                <VorhabenZeile key={v.id} v={v} aktiv={v.id === aktiv} onClick={() => setAktiv(v.id === aktiv ? null : v.id)} />
              ))}
              {sichtbar.length === 0 && (
                <li className="px-4 py-6 text-center text-sm text-muted-foreground">Kein Vorhaben in dieser Stufe.</li>
              )}
            </ol>
          )}

          {data.investments.length > 0 && (
            <Card className="mt-5 p-4">
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
            <div className="mt-6 border-t border-border pt-4">
              <p className="mb-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">Nebenan</p>
              <Nachbarn nachbarn={data.neighbours} />
            </div>
          )}

          <p className="mt-6 text-xs leading-relaxed text-muted-foreground">
            Die Vorhaben stammen aus den öffentlichen Beschlüssen des Oldenburger Stadtrats der letzten zwei Jahre. Ein Sprachmodell prüft je Beschluss, ob er wirklich dieses Viertel betrifft, und fasst zusammengehörige Beschlüsse zu einem Vorhaben zusammen. Termine stehen nur, wenn ein Beschluss sie nennt. Ratslotse ist kein Angebot der Stadt.
          </p>
        </div>

        {breit && ausgewaehlt && (
          <aside className="sticky top-4 self-start">
            <Card className="p-5">{detail}</Card>
          </aside>
        )}
      </div>

      {!breit && (
        <Sheet open={!!ausgewaehlt} onOpenChange={(o) => { if (!o) setAktiv(null); }}>
          <SheetContent side="bottom" className="px-5 pt-4">
            <SheetTitle className="sr-only">{ausgewaehlt?.name ?? "Vorhaben"}</SheetTitle>
            <div className="mx-auto mb-3 h-1 w-9 rounded-full bg-border" aria-hidden />
            {detail}
          </SheetContent>
        </Sheet>
      )}
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

/** Eine Zeile der Liste unter der Karte — knapp: Farbpunkt, Name, Termin. */
function VorhabenZeile({ v, aktiv, onClick }: { v: Vorhaben; aktiv: boolean; onClick: () => void }) {
  const stand = STAND[v.stage] ?? STAND.planning;
  return (
    <li>
      <button
        type="button"
        onClick={onClick}
        aria-pressed={aktiv}
        className={cn(
          "flex w-full items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-accent",
          aktiv && "bg-primary/5",
        )}
      >
        <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: STAND_FARBE[v.stage] }} aria-hidden />
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

/** Der Weg eines Vorhabens: Idee → Planung → beschlossen → im Bau → fertig,
 *  die erreichte Stufe gefüllt. Abgelehnt ist keine Stufe, sondern ein Ende. */
const WEG = ["idea", "planning", "decided", "building", "done"] as const;

function VorhabenDetail({ v, angemeldet, gemeldet, onMelden, onSchliessen }: {
  v: Vorhaben; angemeldet: boolean; gemeldet: boolean; onMelden: () => void; onSchliessen: () => void;
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
        <button type="button" onClick={onSchliessen} className="hidden rounded-md p-1 text-muted-foreground hover:text-foreground @3xl:block" aria-label="Detail schließen">
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

      {v.locations.length > 0 && (
        <p className="mt-3 text-xs text-muted-foreground">
          <MapPinned className="mr-1 inline h-3.5 w-3.5 align-[-2px]" />
          {v.locations.map((l) => l.name).join(" · ")}
        </p>
      )}

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
