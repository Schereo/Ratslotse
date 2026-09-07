"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { MapPinned } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { viertelHref } from "@/lib/routes";
import { cn, formatDate } from "@/lib/utils";
import { Button, Card, DetailSkeleton, EmptyState, PageHeader, Sheet, SheetContent, SheetTitle, toast } from "@/components/ui";
import { ViertelKarte } from "@/components/viertel-karte";
import { ShareButton } from "@/components/share-button";
import { StadtteilKarte } from "@/components/stadtteil-karte";
import { Mascot } from "@/components/mascot";
import { STAFFEL, staffelStil } from "@/components/staffel";
import {
  BeteiligungKarte, DemnaechstKarte, Highlights, InvestitionenKarte, MeineKnoepfe, Nachbarn, OrtSuche, PresseBlock,
  QUELLEN_HINWEIS, Rangliste, SperrungenKarte, StandChips, StandortKnopf, Stadtzahl, VorhabenDetail, VorhabenListe,
  useMeineOrtsbereiche, useTafel, useTafelZustand, useUebersicht,
} from "@/components/viertel/bausteine";

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
 *  Schreibtisch in der Seitenspalte, auf dem Telefon als Bottom-Sheet.
 *
 *  Seit 07.09.2026 sind die Bausteine (Kopf, Karten, Liste, Detail, Suche)
 *  in `components/viertel/bausteine.tsx` — die vereinte Stadtkarte
 *  (`/karte`, STADTKARTE-PLAN.md) setzt dieselben in ihrer Tafel-Spalte
 *  zusammen. Diese Seite ist die alte Reihenfolge, unverändert.
 *
 *  Öffentlich lesbar (`OEFFENTLICHE_PFADE`), bis der Umzug (Schritt 5 des
 *  Plans) sie hinter die Anmeldung nimmt. Ohne `?id=` steht die Auswahl.
 */
export default function ViertelView() {
  const sp = useSearchParams();
  const id = sp.get("id");
  const v = Number(sp.get("v"));
  return id ? <VorhabenTafel placeId={id} vorgewaehlt={Number.isFinite(v) && v > 0 ? v : null} /> : <ViertelAuswahl />;
}

/* -------------------------------------------------------------- Auswahl --- */

/** Die Auswahl ohne gewähltes Viertel: Anzeigetafel (was ist da), die eine
 *  Handlung (und bei mir?), Wärmekarte und Highlights (wo ist am meisten
 *  los), Rangliste statt Alphabet. */
function ViertelAuswahl() {
  const router = useRouter();
  const q = useUebersicht();
  const orte = q.data?.districts;
  const meine = useMeineOrtsbereiche(orte);
  const byName = useMemo(() => new Map((orte ?? []).map((o) => [o.name, o])), [orte]);
  const mitVorhaben = useMemo(() => new Set((orte ?? []).filter((o) => o.count > 0).map((o) => o.name)), [orte]);
  const gewichte = useMemo(() => new Map((orte ?? []).map((o) => [o.name, o.count])), [orte]);

  if (q.isLoading) return <DetailSkeleton />;
  if (!orte || !q.data) return <EmptyState title="Die Übersicht lässt sich gerade nicht laden." mascot="confused" />;
  const data = q.data;

  return (
    // `@container`: Die Spalten-Varianten (`@3xl:`) messen die Breite DIESES
    // Elements; das (app)-Layout deklariert keinen Container.
    <div className="@container mx-auto max-w-5xl">
      <PageHeader
        title="Mein Viertel"
        description="Was sich in deinem Ortsbereich in den nächsten Jahren ändert — Vorhaben aus den Beschlüssen des Stadtrats, gebündelt und gegengeprüft."
      />

      {/* `relative z-30`: Die Staffel-Animation macht jede Fläche zum eigenen
          Stapelkontext, und die Karten-Kachel kommt im Baum NACH der Tafel —
          ohne die Anhebung malte sie sich über die Suchvorschläge. */}
      <section
        className={cn("hh-tafel relative z-30 mt-5 grid gap-6 rounded-2xl border border-border bg-background p-5 text-foreground @3xl:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)] @3xl:gap-8 @3xl:p-7", STAFFEL)}
        style={staffelStil(0)}
        aria-labelledby="viertel-stadt-titel"
      >
        <Stadtzahl data={data} orte={orte} />
        <div className="min-w-0 @3xl:border-l @3xl:border-border @3xl:pl-8">
          <h2 className="font-display text-lg font-bold leading-snug sm:text-xl">Und vor deiner Haustür?</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Straße oder Stadtteil eingeben — oder den Standort nehmen. Nichts davon wird gespeichert.
          </p>
          <MeineKnoepfe meine={meine} byName={byName} ortHref={viertelHref} />
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
        <Highlights data={data} ortHref={viertelHref} />
      </div>

      <div className={cn("mt-8", STAFFEL)} style={staffelStil(2)}>
        <Rangliste orte={orte} ortHref={viertelHref} />
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------- Tafel --- */

function VorhabenTafel({ placeId, vorgewaehlt }: { placeId: string; vorgewaehlt: number | null }) {
  const { user } = useAuth();
  const q = useTafel(placeId);
  const z = useTafelZustand(q.data, vorgewaehlt);
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
  const { vorhaben, ausgewaehlt } = z;

  const detail = ausgewaehlt && (
    <VorhabenDetail
      v={ausgewaehlt}
      angemeldet={!!user}
      gemeldet={z.gemeldet.has(ausgewaehlt.project_key) || ausgewaehlt.reported}
      onMelden={() => z.melden(ausgewaehlt)}
      onSchliessen={() => z.setAktiv(null)}
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
              ? (data.updated_at ? "Noch kein Vorhaben aus den Beschlüssen der letzten zwei Jahre." : "Die Tafel ist noch nicht gerechnet.")
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
              sperrungen={data.closures}
              aktiv={z.aktiv}
              gedimmt={z.gedimmt}
              schwebt={z.schwebt}
              onSelect={z.setAktiv}
              onHover={z.setSchwebt}
              className={cn(STAFFEL, "h-[280px] sm:h-[340px]")}
            />
          )}

          {vorhaben.length > 0 && (
            <StandChips zaehler={z.zaehler} stufe={z.stufe} onStufe={(s) => { z.setStufe(s); z.setAktiv(null); }} className={cn("mt-3", STAFFEL)} />
          )}

          <DemnaechstKarte items={data.upcoming} className={cn("mt-4", STAFFEL)} style={staffelStil(2)} />
          <BeteiligungKarte items={data.participations} className={cn("mt-4", STAFFEL)} style={staffelStil(2)} />
          <SperrungenKarte items={data.closures} className={cn("mt-4", STAFFEL)} style={staffelStil(2)} />

          {vorhaben.length === 0 ? (
            <div className="mt-6 flex flex-col items-center gap-3 rounded-xl border-2 border-dashed border-border px-4 py-8 text-center">
              <Mascot pose="search" decorative className="h-16 w-16" />
              <p className="max-w-md text-sm text-muted-foreground">
                {data.updated_at
                  ? `Für ${place.name} hat der Rat in den letzten zwei Jahren nichts beschlossen, was sich als Vorhaben zeigen ließe. Nebenan ist mehr los:`
                  /* Ohne Zeitstempel hat das Register dieses Viertel noch nie
                     gerechnet — das ist ein Zustand des Laufs, kein Befund
                     über den Rat, und darf nicht so klingen. */
                  : `Die Tafel für ${place.name} ist noch nicht gerechnet — der nächste Lauf füllt sie. Nebenan:`}
              </p>
              <Nachbarn nachbarn={data.neighbours} ortHref={viertelHref} />
            </div>
          ) : (
            <VorhabenListe sichtbar={z.sichtbar} aktiv={z.aktiv} schwebt={z.schwebt} onAktiv={z.setAktiv} onSchwebt={z.setSchwebt} className={cn("mt-4", STAFFEL)} style={staffelStil(3)} />
          )}

          <InvestitionenKarte items={data.investments} className="mt-5" />
          <PresseBlock items={data.press} className={cn("mt-5", STAFFEL)} style={staffelStil(3)} />

          {vorhaben.length > 0 && data.neighbours.length > 0 && (
            <div className="mt-6 border-t border-border pt-4">
              <p className="mb-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">Nebenan</p>
              <Nachbarn nachbarn={data.neighbours} ortHref={viertelHref} />
            </div>
          )}

          <p className="mt-6 text-xs leading-relaxed text-muted-foreground">{QUELLEN_HINWEIS}</p>
        </div>

        {breit && ausgewaehlt && (
          <aside className="sticky top-4 self-start">
            <Card className="p-5">{detail}</Card>
          </aside>
        )}
      </div>

      {!breit && (
        <Sheet open={!!ausgewaehlt} onOpenChange={(o) => { if (!o) z.setAktiv(null); }}>
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
