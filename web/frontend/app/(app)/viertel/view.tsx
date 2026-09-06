"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, CalendarDays, Check, Flag, Hammer, LocateFixed, MapPinned, Megaphone, Search, X } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { ApiAntwort } from "@/lib/vertrag";
import type { Topic } from "@/lib/types";
import { decisionHref, sitzungHref, viertelHref } from "@/lib/routes";
import { shortCommittee } from "@/lib/committees";
import { cn, formatDate } from "@/lib/utils";
import { Badge, Button, Card, DetailSkeleton, EmptyState, Input, PageHeader, Sheet, SheetContent, SheetTitle, Spinner, toast } from "@/components/ui";
import { ViertelKarte, STAND_FARBE } from "@/components/viertel-karte";
import { ShareButton } from "@/components/share-button";
import { StadtteilKarte } from "@/components/stadtteil-karte";
import { loadOrtsbereiche, ortsbereichFor } from "@/lib/districts";
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
  const sp = useSearchParams();
  const id = sp.get("id");
  const v = Number(sp.get("v"));
  return id ? <VorhabenTafel placeId={id} vorgewaehlt={Number.isFinite(v) && v > 0 ? v : null} /> : <ViertelAuswahl />;
}

/* -------------------------------------------------------------- Auswahl --- */

/** Die Auswahl ohne gewähltes Viertel — und warum sie mehr ist als eine Karte.
 *
 *  Bis 06.09.2026 stand hier eine blasse Stadtkarte über einem Alphabet aus
 *  31 Kacheln: nichts, was den Blick zog, nichts, was einen zum Handeln
 *  brachte („langweilig … ich habe keinen Anreiz hier irgendwas zu machen",
 *  Tim). Die Seite beantwortet jetzt drei Fragen in dieser Reihenfolge:
 *
 *  1. **Was ist da überhaupt?** — die Anzeigetafel: EINE Zahl für die ganze
 *     Stadt, daneben, wie viel davon im Bau, beschlossen, in Planung ist.
 *     Ehrliche Menge mit Zeitraum, wie es die Designsprache verlangt.
 *  2. **Und bei mir?** — die eine Handlung, um die es geht: Straße oder
 *     Stadtteil tippen, oder den Standort nehmen. Beides endet auf der Tafel
 *     des eigenen Viertels. Wer angemeldet ist und seinen Stadtteil schon
 *     gewählt hat, sieht ihn als Knopf, bevor er tippen muss.
 *  3. **Wo ist am meisten los?** — die Karte tönt nach Zahl (Wärmekarte),
 *     daneben die Vorhaben, die stadtweit gerade herausstechen, darunter die
 *     Rangliste statt des Alphabets. Für den Namen, den man kennt, ist die
 *     Suche da; die Liste bleibt für Tastatur und Screenreader.
 */
type Uebersicht = ApiAntwort<"/districts/projects">;
type Treffer = ApiAntwort<"/districts/lookup">["matches"][number];

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
  const gewichte = useMemo(() => new Map((orte ?? []).map((o) => [o.name, o.count])), [orte]);
  // Rangliste: die meisten zuerst, bei Gleichstand alphabetisch, die leeren am Ende.
  const rang = useMemo(() => [...(orte ?? [])].sort((a, b) => b.count - a.count || a.name.localeCompare(b.name, "de")), [orte]);

  if (q.isLoading) return <DetailSkeleton />;
  if (!orte || !q.data) return <EmptyState title="Die Übersicht lässt sich gerade nicht laden." mascot="confused" />;
  const data = q.data;
  const belegt = orte.filter((o) => o.count > 0).length;
  const maxCount = rang[0]?.count ?? 0;

  return (
    // `@container`: Die Spalten-Varianten (`@3xl:`) messen die Breite DIESES
    // Elements; das (app)-Layout deklariert keinen Container. Ohne die Klasse
    // blieb die Seite auf jedem Schirm einspaltig — so stand sie bis 06.09.
    <div className="@container mx-auto max-w-5xl">
      <PageHeader
        title="Mein Viertel"
        description="Was sich in deinem Ortsbereich in den nächsten Jahren ändert — Vorhaben aus den Beschlüssen des Stadtrats, gebündelt und gegengeprüft."
      />

      <section
        className={cn("hh-tafel mt-5 grid gap-6 rounded-2xl border border-border bg-background p-5 text-foreground @3xl:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)] @3xl:gap-8 @3xl:p-7", STAFFEL)}
        style={staffelStil(0)}
        aria-labelledby="viertel-stadt-titel"
      >
        <div className="min-w-0">
          <p className="font-mono text-[10px] font-medium uppercase tracking-[0.1em] text-muted-foreground">
            Ganz Oldenburg · Beschlüsse der letzten zwei Jahre
          </p>
          <p id="viertel-stadt-titel" className="mt-2 font-display text-[40px] font-bold leading-none tracking-tight tabular-nums sm:text-[52px]">
            {data.total}
            <span className="ml-2 text-[18px] font-semibold tracking-normal text-muted-foreground sm:text-[20px]">Vorhaben</span>
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
                <dd className="mt-1.5 font-display text-[21px] font-bold leading-none tracking-tight tabular-nums sm:text-[27px]">
                  {data.stages[st] ?? 0}
                </dd>
              </div>
            ))}
          </dl>
        </div>

        <div className="min-w-0 @3xl:border-l @3xl:border-border @3xl:pl-8">
          <h2 className="font-display text-lg font-bold leading-snug sm:text-xl">Und vor deiner Haustür?</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Straße oder Stadtteil eingeben — oder den Standort nehmen. Nichts davon wird gespeichert.
          </p>
          {meine.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-2">
              {meine.map((o) => (
                <Button key={o.place_id} asChild>
                  <Link href={viertelHref(o.place_id)}>
                    <MapPinned className="h-4 w-4" /> {o.name}
                    <span className="ml-1 rounded-full bg-primary-foreground/20 px-1.5 text-xs tabular-nums">{byName.get(o.name)?.count ?? 0}</span>
                    <ArrowRight className="h-4 w-4" />
                  </Link>
                </Button>
              ))}
            </div>
          )}
          <OrtSuche className="mt-3" onWaehlen={(placeId) => router.push(viertelHref(placeId))} />
          <StandortKnopf className="mt-2" onGefunden={(name) => {
            const o = byName.get(name);
            if (o) router.push(viertelHref(o.place_id));
            else toast.error("Dieser Ort liegt außerhalb der 31 Ortsbereiche.");
          }} />
        </div>
      </section>

      <div className={cn("mt-6 grid gap-6 @3xl:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)]", STAFFEL)} style={staffelStil(1)}>
        <Card className="p-3">
          <p className="px-1 pt-1 font-mono text-[10px] font-medium uppercase tracking-[0.1em] text-muted-foreground">
            Wo am meisten los ist
          </p>
          <StadtteilKarte
            gewaehlt={new Set(meine.map((o) => o.name))}
            auswaehlbar={mitVorhaben}
            gewichte={gewichte}
            titel={(name) => `${name} · ${byName.get(name)?.count ?? 0} Vorhaben`}
            onWaehlen={(name) => { const o = byName.get(name); if (o) router.push(viertelHref(o.place_id)); }}
          />
          <p className="flex items-center gap-2 px-1 pb-1 text-[11px] text-muted-foreground">
            <span className="inline-flex h-2 w-16 rounded-sm" aria-hidden
              style={{ background: "linear-gradient(90deg, hsl(var(--primary) / 0.12), hsl(var(--primary) / 0.62))" }} />
            wenige → viele Vorhaben · antippen öffnet das Viertel
          </p>
        </Card>

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
                <Link href={viertelHref(h.place_id, h.id)} className="group flex items-center gap-3 px-4 py-3 transition-colors hover:bg-accent">
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
      </div>

      <section aria-labelledby="viertel-rang-titel" className={cn("mt-8", STAFFEL)} style={staffelStil(2)}>
        <div className="flex items-baseline justify-between gap-2">
          <h2 id="viertel-rang-titel" className="font-display text-base font-bold text-foreground">Alle {orte.length} Ortsbereiche</h2>
          <span className="font-mono text-[10px] font-medium uppercase tracking-[0.1em] text-muted-foreground">nach Zahl der Vorhaben</span>
        </div>
        <ol className="mt-2 grid grid-cols-1 gap-2 @xl:grid-cols-2 @3xl:grid-cols-3">
          {rang.map((o, i) => (
            <li key={o.place_id} className={STAFFEL} style={staffelStil(i)}>
              <Link
                href={viertelHref(o.place_id)}
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
    </div>
  );
}

/** „Ich wohne in der …": Eingabe mit Vorschlägen — Stadtteil, Straße oder
 *  Platz, jeweils mit dem Ortsbereich dahinter. Die Vorschläge kommen vom
 *  Server (nur Orte, die je ein Beschluss genannt hat); Enter nimmt den
 *  markierten, Pfeile wandern, Escape schließt. Kein Konto, kein Sprachmodell. */
function OrtSuche({ onWaehlen, className }: { onWaehlen: (placeId: string) => void; className?: string }) {
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
function StandortKnopf({ onGefunden, className }: { onGefunden: (name: string) => void; className?: string }) {
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

/* ---------------------------------------------------------------- Tafel --- */

/** Reihenfolge der Stufenleiste: was gerade passiert, zuerst. */
const STUFEN = ["building", "decided", "planning", "idea", "done", "rejected"] as const;

function VorhabenTafel({ placeId, vorgewaehlt }: { placeId: string; vorgewaehlt: number | null }) {
  const { user } = useAuth();
  const q = useQuery({
    queryKey: ["viertel", placeId],
    queryFn: () => api.get<Tafel>(`/districts/${encodeURIComponent(placeId)}/projects`),
  });
  const [gemeldet, setGemeldet] = useState<Set<string>>(new Set());
  const [stufe, setStufe] = useState<string | null>(null);
  // Ein Highlight der Auswahl-Seite zeigt auf genau ein Vorhaben (`?v=`):
  // Das steht dann gleich offen, statt dass man es in der Liste suchen muss.
  const [aktiv, setAktiv] = useState<number | null>(vorgewaehlt);
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
    <div className="@container mx-auto max-w-5xl">
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
