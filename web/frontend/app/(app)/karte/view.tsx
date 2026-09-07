"use client";

import { useEffect, useMemo, useState } from "react";
import { notFound, useRouter, useSearchParams } from "next/navigation";
import { ArrowLeft, ChevronRight } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { featureAktiv, useAppConfig } from "@/lib/features";
import { karteHref } from "@/lib/routes";
import { cn, formatDate } from "@/lib/utils";
import { Button, DetailSkeleton, EmptyState, Sheet, SheetContent, SheetTitle, toast } from "@/components/ui";
import { StadtKarte, type KartenStufe } from "@/components/stadt-karte";
import { EbenenChips } from "@/components/ebenen-chips";
import { ebeneUmschalten, ebenenMerken, ebenenStart, ebenenZuUrl, type EbenenId } from "@/lib/karten-ebenen";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { api } from "@/lib/api";
import { themaHref } from "@/lib/routes";
import type { Entity, EntityMapPoint } from "@/lib/types";
import { loadOrtsbereiche, ortsbereichFor, type OrtsbereichFeature } from "@/lib/districts";
import { KIND_COLOR, istBeschlussort, punktHref } from "@/components/council-map";
import { ENTITY_KIND } from "@/components/council-entities";
import { StadtteilKarte } from "@/components/stadtteil-karte";
import { ShareButton } from "@/components/share-button";
import { Mascot } from "@/components/mascot";
import { STAFFEL, staffelStil } from "@/components/staffel";
import {
  BeteiligungKarte, DemnaechstKarte, Highlights, InvestitionenKarte, MeineKnoepfe, Nachbarn, OrtSuche, PresseBlock,
  QUELLEN_HINWEIS, Rangliste, SperrungenKarte, StandChips, StandortKnopf, Stadtzahl, VorhabenDetail, VorhabenListe,
  useMeineOrtsbereiche, useTafel, useTafelZustand, useUebersicht,
} from "@/components/viertel/bausteine";

/** Die vereinte Stadtkarte — Richtung A aus `STADTKARTE-PLAN.md`: die Karte
 *  füllt die Seite, rechts läuft eine Tafel-Spalte mit, die mit dem Zoom
 *  ihren Inhalt wechselt.
 *
 *  Drei Stufen, eine Adresse:
 *  - `/karte`            Stadt: Wärmekarte der 31 Ortsbereiche, Stadtzahl,
 *                        Suche, Standort, Highlights, Rangliste.
 *  - `/karte?ort=…`      Viertel: Umriss, Pins, Planflächen, Sperrungen — und
 *                        die Tafel des Viertels (dieselben Bausteine wie
 *                        `/viertel`).
 *  - `/karte?ort=…&v=…`  Vorhaben: das Detail in der Spalte, der Pin mit
 *                        Schild und Ring.
 *
 *  Der Ortsbereich steht als `push` in der Geschichte (zurück = Stadt), das
 *  Vorhaben als `replace` (zurück springt nicht durch jeden Pin).
 *
 *  Hinter dem Schalter `stadtkarte` (Tims Entscheidung 07.09.2026: die Karte
 *  liegt hinter der Anmeldung; öffentlich bleibt nur die Landingpage — das
 *  regelt das App-Layout, `/karte` steht nicht in `OEFFENTLICHE_PFADE`).
 *
 *  Schritt 1 des Plans: noch keine Ebenen-Chips (Schritt 2), keine
 *  Themen-Orte (3), keine Navigation hierher (5).
 */
export default function KarteView() {
  const cfg = useAppConfig();
  // `undefined` heißt „noch nicht geladen" und wäre AUS — ein notFound() in
  // diesem Moment träfe jeden beim ersten Aufruf. Deshalb erst nach Antwort.
  if (cfg.isSuccess && !featureAktiv(cfg.data, "stadtkarte")) notFound();
  if (!cfg.isSuccess) return <DetailSkeleton />;
  return <Buehne />;
}

function Buehne() {
  const router = useRouter();
  const sp = useSearchParams();
  const ort = sp.get("ort");
  const v = Number(sp.get("v"));
  const vorgewaehlt = Number.isFinite(v) && v > 0 ? v : null;
  const { user } = useAuth();

  const uebersicht = useUebersicht();
  const orte = uebersicht.data?.districts;
  const meine = useMeineOrtsbereiche(orte);
  const byName = useMemo(() => new Map((orte ?? []).map((o) => [o.name, o])), [orte]);
  const byId = useMemo(() => new Map((orte ?? []).map((o) => [o.place_id, o])), [orte]);
  const gewichte = useMemo(() => new Map((orte ?? []).map((o) => [o.name, o.count])), [orte]);
  const ortName = ort ? byId.get(ort)?.name ?? null : null;

  const tafel = useTafel(ort);
  const z = useTafelZustand(tafel.data, vorgewaehlt);
  const [schwebtOrt, setSchwebtOrt] = useState<string | null>(null);

  // Die Ebenen: Adresse vor Speicher vor Vorgabe (lib/karten-ebenen.ts).
  // Ein Wechsel schreibt beides — die Adresse, damit ein geteilter Link zeigt,
  // was man sah, und den Speicher, damit es beim nächsten Mal so bleibt.
  const ebenenParam = sp.get("ebenen");
  const [ebenen, setEbenen] = useState<Set<EbenenId>>(() => ebenenStart(ebenenParam));
  function ebeneWechseln(id: EbenenId) {
    const neu = ebeneUmschalten(ebenen, id);
    setEbenen(neu);
    ebenenMerken(neu);
  }

  // Ein neues Vorhaben in der Adresse (Highlight, geteilter Link) → auswählen.
  useEffect(() => {
    z.setAktiv(vorgewaehlt);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [vorgewaehlt, ort]);
  // Auswahl und Ebenen → Adresse (replace: zurück soll nicht durch jeden Pin
  // und jeden Chip springen). Die Vorgabe der Ebenen bleibt aus der Adresse
  // heraus — sie soll sauber sein, solange nichts Besonderes gilt.
  useEffect(() => {
    const basis = karteHref(ort, ort ? z.aktiv : null);
    const e = ebenenZuUrl(ebenen);
    const ziel = e == null ? basis : `${basis}${basis.includes("?") ? "&" : "?"}ebenen=${e}`;
    if (window.location.pathname + window.location.search !== ziel) router.replace(ziel, { scroll: false });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [z.aktiv, ebenen]);

  // Die Ebene „Themen-Orte" (Schritt 3): die Punkte der alten Themen-Karte,
  // geladen erst, wenn die Ebene an ist (der Endpunkt verlangt ein Konto —
  // die Karte auch, also passt das). Auf der Viertel-Stufe nur die Punkte
  // im Ortsbereich, zugeordnet im Browser über die Umrisse.
  const themenAn = ebenen.has("themen-orte");
  const themenQ = useQuery({
    queryKey: ["entities-map"],
    queryFn: () => api.get<{ entities: EntityMapPoint[] }>("/council/entities-map"),
    enabled: themenAn,
    staleTime: 10 * 60_000,
  });
  const entitiesQ = useQuery({
    queryKey: ["entities-liste"],
    queryFn: () => api.get<{ entities: Entity[] }>("/council/entities"),
    enabled: themenAn && !ort,
    staleTime: 10 * 60_000,
  });
  const [art, setArt] = useState<ThemenArt>("");
  const [umrisse, setUmrisse] = useState<OrtsbereichFeature[]>([]);
  useEffect(() => {
    if (!themenAn || umrisse.length) return;
    void loadOrtsbereiche().then(setUmrisse).catch(() => {});
  }, [themenAn, umrisse.length]);
  const themenOrte = useMemo(() => {
    if (!themenAn) return [];
    const alle = themenQ.data?.entities ?? [];
    const nachArt = alle.filter((p) => !art || (art === "location" ? istBeschlussort(p) : p.kind === art && !istBeschlussort(p)));
    if (!ortName) return nachArt;
    if (!umrisse.length) return [];
    return nachArt.filter((p) => ortsbereichFor(p.lat, p.lon, umrisse) === ortName);
  }, [themenAn, themenQ.data, art, ortName, umrisse]);
  const artZaehler = useMemo(() => {
    const alle = themenQ.data?.entities ?? [];
    const imBereich = ortName && umrisse.length ? alle.filter((p) => ortsbereichFor(p.lat, p.lon, umrisse) === ortName) : alle;
    const z: Record<string, number> = {};
    for (const p of imBereich) {
      const k = istBeschlussort(p) ? "location" : p.kind;
      z[k] = (z[k] ?? 0) + 1;
    }
    return z;
  }, [themenQ.data, ortName, umrisse]);

  // Schreibtisch: Tafel-Spalte neben der Karte. Telefon: Karte oben, Tafel
  // darunter, Detail als Sheet — die Grenze wie auf /viertel.
  const [breit, setBreit] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia("(min-width: 900px)");
    const h = () => setBreit(mq.matches);
    h(); mq.addEventListener("change", h);
    return () => mq.removeEventListener("change", h);
  }, []);

  function zumOrt(placeId: string) { router.push(karteHref(placeId)); }
  function zurStadt() { router.push(karteHref()); }

  if (uebersicht.isLoading) return <DetailSkeleton />;
  if (!orte || !uebersicht.data) return <EmptyState title="Die Karte lässt sich gerade nicht laden." mascot="confused" />;
  const daten = uebersicht.data;
  const stufe: KartenStufe = ortName ? { art: "district", name: ortName } : { art: "city" };
  const place = tafel.data?.place as { id: string; name: string } | undefined;

  const detail = z.ausgewaehlt && (
    <VorhabenDetail
      v={z.ausgewaehlt}
      angemeldet={!!user}
      gemeldet={z.gemeldet.has(z.ausgewaehlt.project_key) || z.ausgewaehlt.reported}
      onMelden={() => z.ausgewaehlt && z.melden(z.ausgewaehlt)}
      onSchliessen={() => z.setAktiv(null)}
      schliessenSichtbar="immer"
    />
  );

  return (
    // Die Bühne bricht aus dem Seitenpolster aus: negative Ränder gegen
    // `px-4/6/8` und `--rl-luft` des App-Layouts, damit die Karte bis an die
    // Kanten läuft. `@container` für die Spalten-Varianten der Bausteine.
    <div className="@container -mx-4 -my-[var(--rl-luft)] flex flex-col sm:-mx-6 lg:-mx-8 desk:h-[calc(100dvh)] desk:flex-row desk:overflow-hidden">
      <div className="relative h-[45dvh] min-h-[280px] desk:h-auto desk:min-h-0 desk:flex-1">
        <StadtKarte
          stufe={stufe}
          ebenen={ebenen}
          orte={gewichte}
          gewaehlt={new Set(meine.map((o) => o.name))}
          schwebtOrt={schwebtOrt}
          onOrt={(name) => { const o = byName.get(name); if (o) zumOrt(o.place_id); }}
          vorhaben={z.vorhaben}
          sperrungen={tafel.data?.closures}
          themenOrte={themenOrte}
          onThemenOrt={(p) => router.push(punktHref(p))}
          aktiv={z.aktiv}
          gedimmt={z.gedimmt}
          schwebt={z.schwebt}
          onSelect={z.setAktiv}
          onHover={z.setSchwebt}
          className="h-full w-full"
        />
        {/* Ebenen-Chips oben links AUF der Karte — zugleich die Legende. Die
            Zähler sagen, was gerade auf dieser Stufe liegt. */}
        <EbenenChips
          ebenen={ebenen}
          stufe={stufe.art}
          zaehler={stufe.art === "city"
            ? { vorhaben: daten.total, ...(themenAn ? { "themen-orte": themenOrte.length } : {}) }
            : {
              vorhaben: z.vorhaben.length,
              plaene: z.vorhaben.reduce((n, v) => n + v.locations.filter((l) => l.kind === "bplan").length, 0),
              sperrungen: tafel.data?.closures.length ?? 0,
              ...(themenAn ? { "themen-orte": themenOrte.length } : {}),
            }}
          onToggle={ebeneWechseln}
          unterzeile={themenAn && <ThemenArtChips art={art} zaehler={artZaehler} onArt={setArt} />}
          className="absolute left-3 top-3 z-[500] max-w-[calc(100%-4.5rem)]"
        />
        {/* Brotkrumen: wo bin ich, und wie komme ich eine Stufe hoch. */}
        <nav aria-label="Stufe" className="absolute bottom-4 left-4 z-[500] flex items-center gap-2 rounded-xl border border-border bg-card/95 px-3 py-2 text-[12.5px] font-medium shadow-lg backdrop-blur">
          {ortName ? (
            <>
              <button type="button" onClick={zurStadt} className="text-muted-foreground hover:text-foreground">Oldenburg</button>
              <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" aria-hidden />
              <span className="font-bold">{ortName}</span>
              <button type="button" onClick={zurStadt} className="ml-1 font-semibold text-primary hover:underline">Stadt zeigen</button>
            </>
          ) : (
            <span className="font-bold">Oldenburg · 31 Ortsbereiche</span>
          )}
        </nav>
        {/* Mini-Stadtkarte unten rechts: wo das Viertel in der Stadt liegt —
            und ein Tipp auf einen Nachbarn wechselt dorthin. */}
        {ortName && (
          <div className="absolute bottom-4 right-4 z-[500] hidden w-[180px] rounded-xl border border-border bg-card/95 p-1.5 shadow-lg backdrop-blur desk:block">
            <StadtteilKarte
              gewaehlt={new Set([ortName])}
              auswaehlbar={new Set(orte.map((o) => o.name))}
              gewichte={gewichte}
              titel={(name) => `${name} · ${byName.get(name)?.count ?? 0} Vorhaben`}
              onWaehlen={(name) => { const o = byName.get(name); if (o) zumOrt(o.place_id); }}
            />
          </div>
        )}
      </div>

      <aside className="min-w-0 border-t border-border bg-card desk:w-[420px] desk:shrink-0 desk:overflow-y-auto desk:border-l desk:border-t-0" aria-label={ortName ? `Tafel ${ortName}` : "Tafel Oldenburg"}>
        {stufe.art === "city" ? (
          <StadtTafel daten={daten} orte={orte} meine={meine} byName={byName} onOrt={zumOrt} onHoverOrt={setSchwebtOrt}
            themen={themenAn ? entitiesQ.data?.entities : undefined} />
        ) : tafel.isLoading ? (
          <div className="p-5"><DetailSkeleton /></div>
        ) : !tafel.data || !place ? (
          <div className="p-5">
            <EmptyState title="Diesen Ortsbereich gibt es nicht." mascot="search" action={<Button variant="secondary" onClick={zurStadt}>Zur Stadt</Button>} />
          </div>
        ) : breit && z.ausgewaehlt ? (
          <div className="p-5">
            <button type="button" onClick={() => z.setAktiv(null)} className="mb-3 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
              <ArrowLeft className="h-4 w-4" /> {place.name}
            </button>
            {detail}
          </div>
        ) : (
          <ViertelTafel data={tafel.data} place={place} z={z} />
        )}
      </aside>

      {!breit && (
        <Sheet open={!!z.ausgewaehlt} onOpenChange={(o) => { if (!o) z.setAktiv(null); }}>
          <SheetContent side="bottom" className="px-5 pt-4">
            <SheetTitle className="sr-only">{z.ausgewaehlt?.name ?? "Vorhaben"}</SheetTitle>
            <div className="mx-auto mb-3 h-1 w-9 rounded-full bg-border" aria-hidden />
            {detail}
          </SheetContent>
        </Sheet>
      )}
    </div>
  );
}

/** Die Tafel-Spalte auf der Stadt-Stufe: Stadtzahl, die eine Handlung,
 *  Highlights, Rangliste — die heutige Auswahl, nur in einer Spalte. */
/** Die Arten der Themen-Orte als Unter-Chips: Ort, Organisation, Projekt —
 *  und die konkreten Beschlussorte (Straßen, Plätze, Gebäude aus der
 *  Orts-Pipeline) in ihrer eigenen Farbe. */
type ThemenArt = "" | "place" | "organisation" | "project" | "location";
const THEMEN_ARTEN: { id: ThemenArt; label: string; farbe: string }[] = [
  ...(Object.keys(ENTITY_KIND) as ("place" | "organisation" | "project")[]).map((k) => ({ id: k, label: ENTITY_KIND[k].plural, farbe: KIND_COLOR[k] })),
  { id: "location", label: "Beschlussorte", farbe: KIND_COLOR.beschlussort },
];

function ThemenArtChips({ art, zaehler, onArt }: { art: ThemenArt; zaehler: Record<string, number>; onArt: (a: ThemenArt) => void }) {
  return (
    <div className="flex flex-wrap gap-1" role="group" aria-label="Art der Themen-Orte">
      {THEMEN_ARTEN.map((a) => {
        const an = art === a.id;
        return (
          <button key={a.id} type="button" aria-pressed={an} onClick={() => onArt(an ? "" : a.id)}
            className={cn("inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium shadow-sm backdrop-blur transition-colors",
              an ? "border-current bg-card/95 text-foreground" : "border-border/70 bg-card/70 text-muted-foreground hover:text-foreground")}>
            <span aria-hidden className="h-2 w-2 rounded-full" style={{ background: a.farbe }} />
            {a.label}
            {zaehler[a.id] != null && <span className="font-mono text-[10px] tabular-nums opacity-70">{zaehler[a.id]}</span>}
          </button>
        );
      })}
    </div>
  );
}

/** „Gerade aktiv" — die Themen mit den meisten Beschlüssen in zwölf Monaten,
 *  aus dem Themen-Tab in die Stadt-Tafel gewandert (Schritt 3). */
function ThemenAktiv({ themen }: { themen: Entity[] }) {
  const top = [...themen]
    .filter((e) => (e.n_recent ?? 0) > 0)
    .sort((a, b) => (b.n_recent ?? 0) - (a.n_recent ?? 0) || (b.last_date ?? "").localeCompare(a.last_date ?? "") || b.n - a.n)
    .slice(0, 6);
  if (!top.length) return null;
  return (
    <section aria-labelledby="karte-themen-titel">
      <div className="flex items-baseline justify-between gap-2">
        <h2 id="karte-themen-titel" className="font-display text-base font-bold text-foreground">Themen, die gerade laufen</h2>
        <span className="font-mono text-[10px] font-medium uppercase tracking-[0.1em] text-muted-foreground">12 Monate · alle Jahre auf der Karte</span>
      </div>
      <ol className="mt-2 divide-y divide-border rounded-2xl border border-border bg-card">
        {top.map((e) => {
          const k = ENTITY_KIND[e.kind] ?? ENTITY_KIND.project;
          return (
            <li key={e.slug}>
              <Link href={themaHref(e.slug)} className="group flex items-center gap-3 px-3 py-2.5 transition-colors hover:bg-accent">
                <k.Icon className="h-4 w-4 shrink-0" style={{ color: KIND_COLOR[e.kind] ?? KIND_COLOR.projekt }} aria-hidden />
                <span className="min-w-0 flex-1 truncate text-sm font-medium text-foreground">{e.name}</span>
                <span className="shrink-0 font-mono text-[11px] tabular-nums text-muted-foreground" title="Beschlüsse in zwölf Monaten">{e.n_recent}</span>
                <ChevronRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5" aria-hidden />
              </Link>
            </li>
          );
        })}
      </ol>
    </section>
  );
}

function StadtTafel({ daten, orte, meine, byName, onOrt, onHoverOrt, themen }: {
  daten: ReturnType<typeof useUebersicht>["data"] & object;
  orte: NonNullable<ReturnType<typeof useUebersicht>["data"]>["districts"];
  meine: { name: string; place_id: string }[];
  byName: Map<string, { place_id: string; count: number }>;
  onOrt: (placeId: string) => void;
  onHoverOrt: (name: string | null) => void;
  /** Die Themen-Liste, wenn die Ebene an ist — sonst bleibt der Block weg. */
  themen?: Entity[];
}) {
  return (
    <div className="flex flex-col gap-5 p-5">
      <section className={cn("hh-tafel relative z-30 rounded-2xl border border-border bg-background p-4 text-foreground", STAFFEL)} style={staffelStil(0)} aria-labelledby="viertel-stadt-titel">
        <Stadtzahl data={daten} orte={orte} kompakt />
        <div className="mt-4 border-t border-border pt-4">
          <h2 className="font-display text-base font-bold leading-snug">Und vor deiner Haustür?</h2>
          <MeineKnoepfe meine={meine} byName={byName} ortHref={(id) => karteHref(id)} />
          <OrtSuche className="mt-3" onWaehlen={onOrt} />
          <StandortKnopf className="mt-2" onGefunden={(name) => {
            const o = byName.get(name);
            if (o) onOrt(o.place_id);
            else toast.error("Dieser Ort liegt außerhalb der 31 Ortsbereiche.");
          }} />
        </div>
      </section>
      <div className={STAFFEL} style={staffelStil(1)}>
        <Highlights data={daten} ortHref={karteHref} kompakt />
      </div>
      {themen && <div className={STAFFEL} style={staffelStil(2)}><ThemenAktiv themen={themen} /></div>}
      <div className={STAFFEL} style={staffelStil(2)}>
        <Rangliste orte={orte} ortHref={karteHref} spalten="grid-cols-1" onHover={onHoverOrt} />
      </div>
    </div>
  );
}

/** Die Tafel-Spalte auf der Viertel-Stufe — die Karten und die Liste von
 *  `/viertel`, in der Reihenfolge, die dort gilt. */
function ViertelTafel({ data, place, z }: {
  data: NonNullable<ReturnType<typeof useTafel>["data"]>;
  place: { id: string; name: string };
  z: ReturnType<typeof useTafelZustand>;
}) {
  return (
    <div className="flex flex-col gap-4 p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-medium uppercase tracking-wider text-primary">Mein Viertel</p>
          <h1 className="mt-0.5 font-display text-2xl font-bold text-foreground">{place.name}</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {z.vorhaben.length === 0
              ? (data.updated_at ? "Noch kein Vorhaben aus den Beschlüssen der letzten zwei Jahre." : "Die Tafel ist noch nicht gerechnet.")
              : `${z.vorhaben.length} Vorhaben aus den Beschlüssen der letzten zwei Jahre` +
                (data.updated_at ? ` · Stand ${formatDate(data.updated_at.slice(0, 10))}` : "")}
          </p>
        </div>
        <ShareButton path={karteHref(place.id)} title={`Mein Viertel: ${place.name} — Ratslotse`} />
      </div>

      {z.vorhaben.length > 0 && <StandChips zaehler={z.zaehler} stufe={z.stufe} onStufe={(s) => { z.setStufe(s); z.setAktiv(null); }} />}

      <DemnaechstKarte items={data.upcoming} className={STAFFEL} style={staffelStil(1)} />
      <SperrungenKarte items={data.closures} className={STAFFEL} style={staffelStil(1)} />
      <BeteiligungKarte items={data.participations} className={STAFFEL} style={staffelStil(2)} />

      {z.vorhaben.length === 0 ? (
        <div className="flex flex-col items-center gap-3 rounded-xl border-2 border-dashed border-border px-4 py-8 text-center">
          <Mascot pose="search" decorative className="h-16 w-16" />
          <p className="max-w-md text-sm text-muted-foreground">
            {data.updated_at
              ? `Für ${place.name} hat der Rat in den letzten zwei Jahren nichts beschlossen, was sich als Vorhaben zeigen ließe. Nebenan ist mehr los:`
              : `Die Tafel für ${place.name} ist noch nicht gerechnet — der nächste Lauf füllt sie. Nebenan:`}
          </p>
          <Nachbarn nachbarn={data.neighbours} ortHref={karteHref} />
        </div>
      ) : (
        <VorhabenListe sichtbar={z.sichtbar} aktiv={z.aktiv} schwebt={z.schwebt} onAktiv={z.setAktiv} onSchwebt={z.setSchwebt} className={STAFFEL} style={staffelStil(2)} />
      )}

      <InvestitionenKarte items={data.investments} />
      <PresseBlock items={data.press} className={STAFFEL} style={staffelStil(3)} />

      {z.vorhaben.length > 0 && data.neighbours.length > 0 && (
        <div className="border-t border-border pt-4">
          <p className="mb-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">Nebenan</p>
          <Nachbarn nachbarn={data.neighbours} ortHref={karteHref} />
        </div>
      )}
      <p className="text-xs leading-relaxed text-muted-foreground">{QUELLEN_HINWEIS}</p>
    </div>
  );
}
