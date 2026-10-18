"use client";

/**
 * „Neu bei Ratslotse" — was eine neue Ausgabe gebracht hat, auf der Übersicht.
 *
 * Ratslotse liefert laufend aus; wer alle paar Wochen vorbeikommt, merkt von
 * einem neuen Feature sonst nichts. Die Karte steht im Hinweis-Slot der
 * Heute-Seite und **nicht** als Dialog vor der Seite: Wer die App öffnet, will
 * zum Rat, nicht zu uns (Tims Entscheidung 07.09.2026).
 *
 * **Video-Kacheln statt einer Bühne zum Durchklicken** (seit 3.0.0, Tims
 * Befund 07.10.2026: „Die Karte fühlt sich langweilig an; ich weiß nicht, ob
 * ich Bock habe, da unten durchzuklicken — mehr Bilder, mehr Anreiz"). Jede
 * Neuerung ist eine große Kachel mit Titelbild, Farbe, Titel und Länge des
 * Clips; ein Tipp öffnet den **Story-Spieler**
 * (`components/neuigkeiten-spieler.tsx`). Die Kachel verspricht, was der
 * Spieler hält — vorher stand ein Satz, und das Bild musste man erst
 * erblättern. Kleinere Neuerungen stehen als Zeile „Außerdem: …" darunter
 * (`aside` in `kern/releases.py`). Ohne Medien fällt die Karte auf die
 * Listenform zurück (die Registry verlangt: alle oder keines).
 *
 * **Kein Selbstlauf auf der Karte.** Die Kacheln zeigen Standbilder; was sich
 * bewegt, bewegt sich erst im Spieler, und den öffnet ein Mensch.
 *
 * **Wer sie sieht, entscheidet der Server** (`GET /news`). Dieselbe Regel wie
 * beim Einrichtungs-Assistenten: Web und native App bekommen dieselbe Antwort,
 * statt die Bedingung je Client nachzubauen.
 *
 * **Wann die Karte endgültig geht.** Die Hochwassermarke am Konto
 * (`news_seen_version`, `POST /news/seen`) bleibt die eine Entscheidung, die
 * für alle Geräte gilt. Sie wird an zwei Stellen gesetzt:
 *
 * 1. **wenn alle Kacheln angesehen sind** — dann hat die Karte ihren Zweck
 *    erfüllt. Sie bleibt für diesen Besuch stehen (alle drei abgehakt, „3 von
 *    3 angesehen"), statt unter dem schließenden Spieler wegzuspringen, und ist
 *    beim nächsten Laden weg. Vorher brauchte es dafür ein „Alles klar", das
 *    nach dem Durchklicken niemand mehr vermisst hätte.
 * 2. **wenn sie jemand ausblendet** (×) — ein Nein ist eine Antwort. Das ×
 *    ist klein und steht in der Ecke: In der ersten Fassung stand „Alles klar"
 *    gleichberechtigt neben der Bühne, und drei von vier Neuerungen sah nie
 *    jemand (Tims Befund 07.09.2026).
 *
 * Gemeldet wird die Version, die diese Karte GEZEIGT hat — käme zwischen
 * Laden und Klick ein Deploy, würde „die neueste" ein Release miterledigen,
 * das niemand sah. Welche Kacheln schon angesehen sind, merkt sich dagegen nur
 * dieses Gerät (`lib/neuigkeiten.ts`).
 */

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, Check, ChevronLeft, ChevronRight, Play, X } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { vertrag } from "@/lib/vertrag";
import { Card } from "@/components/ui";
import { Mascot } from "@/components/mascot";
import { NeuigkeitenSpieler } from "@/components/neuigkeiten-spieler";
import {
  aufteilen, dauerGesprochen, formatDauer, gesehenLesen, gesehenMerken,
  highlightSchluessel, kachelFarbe, mitKacheln, zaehleGesehen,
  type Highlight, type NewsState, type Release,
} from "@/lib/neuigkeiten";
import { cn } from "@/lib/utils";

const NEWS_QUERY_KEY = ["news"] as const;

const KICKER =
  "font-mono text-[11px] font-semibold uppercase tracking-[0.08em] text-primary";

/** „2.3.0" → „2.3" — die Patch-Null sagt niemandem etwas. */
export function kurzVersion(version: string): string {
  return version.replace(/\.0$/, "");
}

/** Der Kicker über der Karte: eine Ausgabe nennt ihre Nummer, mehrere sagen,
 *  dass hier Liegengebliebenes steht. */
export function kickerText(versionen: string[]): string {
  if (versionen.length <= 1) {
    return `Neu bei Ratslotse · ${kurzVersion(versionen[0] ?? "")}`;
  }
  return `Neu seit deinem letzten Besuch · ${versionen.map(kurzVersion).join(" und ")}`;
}

/** Der Abdunkler über dem Titelbild: die Textfarbe des hellen Themes,
 *  hsl(212 55% 11%), halb deckend — darauf die Farbe der Kachel. Ab gut der
 *  Hälfte der Höhe deckt die Farbe zu 95 %, ab drei Vierteln ganz; dort steht
 *  die Schrift, und ihr Kontrast hängt nicht am Bild darunter (gemessen mit
 *  einem Browserfenster als Bild: Bei 70 % lief Text aus dem Clip durch den
 *  Titel). */
function verlauf(farbe: string): string {
  return `linear-gradient(180deg, hsl(212 55% 11% / 0) 20%, hsl(212 55% 11% / 0.5) 40%, ${farbe}f2 58%, ${farbe} 74%)`;
}

/** Eine Video-Kachel: Titelbild, Farbe, Titel, eine Zeile, Länge, Abspielen.
 *
 *  Die ganze Kachel ist EIN Knopf — er öffnet den Spieler. Der Name sagt,
 *  was passiert und wie lange es dauert, statt die Bausteine einzeln
 *  vorzulesen. */
function Kachel({
  h, nummer, gesehen, onOeffnen,
}: { h: Highlight; nummer: number; gesehen: boolean; onOeffnen: (von: HTMLElement) => void }) {
  const farbe = kachelFarbe(h.color);
  const dauer = formatDauer(h.media?.duration);
  const gesprochen = dauerGesprochen(h.media?.duration);
  return (
    <button
      type="button"
      onClick={(e) => onOeffnen(e.currentTarget)}
      aria-label={`Video ansehen: ${h.title}${gesprochen ? `, ${gesprochen}` : ""}${gesehen ? " (schon angesehen)" : ""}`}
      className={cn(
        "group relative block aspect-[4/5] w-full overflow-hidden rounded-[18px] bg-[hsl(212_55%_11%)] text-left",
        "shadow-[0_18px_36px_-24px_rgba(2,32,64,0.6)] outline-none",
        "focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-card",
        "@3xl:aspect-[20/19]",
        // Unter der Maus hebt sich die Kachel und der Knopf wächst — nur
        // `transform`, nur mit Bewegung (DESIGNSPRACHE §7), nur mit Zeiger.
        "transition-[transform,box-shadow] duration-fluss ease-out-strong",
        "maus:hover:shadow-[0_24px_44px_-24px_rgba(2,32,64,0.7)] motion-safe:maus:hover:-translate-y-0.5",
      )}
    >
      {h.media?.cover && (
        // Statische Datei aus der Registry; `next/image` bringt im Export nichts.
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={h.media.cover}
          alt=""
          loading="lazy"
          className="absolute inset-0 h-full w-full object-cover object-top"
        />
      )}
      <span aria-hidden className="absolute inset-0" style={{ background: verlauf(farbe) }} />

      {/* Oben links die Nummer — oder der Haken, wenn sie schon dran war. */}
      <span
        aria-hidden
        className="absolute left-3.5 top-3.5 grid h-8 w-8 place-items-center rounded-full bg-white/95 font-display text-[17px] font-extrabold tabular-nums"
        style={{ color: farbe }}
      >
        {gesehen ? <Check className="h-4 w-4" strokeWidth={3} /> : nummer}
      </span>
      {dauer && (
        <span
          aria-hidden
          className="absolute right-3.5 top-3.5 inline-flex items-center gap-1 rounded-full bg-[hsl(212_55%_11%/0.62)] px-2.5 py-1 text-[13px] font-semibold tabular-nums text-white"
        >
          <Play className="h-3 w-3 fill-current" /> {dauer}
        </span>
      )}

      <span
        aria-hidden
        className="absolute left-1/2 top-[40%] grid h-16 w-16 -translate-x-1/2 -translate-y-1/2 place-items-center rounded-full bg-white/[0.94] shadow-[0_10px_30px_-10px_rgba(0,0,0,0.5)] transition-transform duration-fluss ease-out-strong motion-safe:maus:group-hover:scale-[1.06]"
      >
        <Play className="ml-1 h-7 w-7" style={{ color: farbe, fill: farbe }} />
      </span>

      <span className="absolute inset-x-0 bottom-0 block p-4 @3xl:p-5">
        <span className="block font-display text-[22px] font-extrabold leading-[1.1] text-white">
          {h.title}
        </span>
        {h.tagline && (
          <span className="mt-1.5 block text-[14px] leading-snug text-white/90">{h.tagline}</span>
        )}
      </span>
    </button>
  );
}

/** Der Fortschritt im Kopf: je Kachel ein Balken, gefüllt = angesehen.
 *  Signal-Orange als Marker (DESIGNSPRACHE §2), keine Fläche. */
function Fortschritt({ gesamt, gesehen }: { gesamt: number; gesehen: number }) {
  return (
    <div className="shrink-0 text-right" aria-live="polite">
      <div aria-hidden className="flex justify-end gap-1.5">
        {Array.from({ length: gesamt }, (_, i) => (
          <span key={i} className={cn("h-1.5 w-9 rounded-full", i < gesehen ? "bg-signal" : "bg-border")} />
        ))}
      </div>
      <p className="mt-1.5 text-meta text-muted-foreground tabular-nums">
        {gesehen} von {gesamt} angesehen
      </p>
    </div>
  );
}

/** Die Kacheln: am Schreibtisch nebeneinander, schmal ein Karussell.
 *
 *  Schmal laufen die Kacheln bis an den Kartenrand und rasten ein; die
 *  nächste schaut angeschnitten herein — das sagt ohne Worte, dass es
 *  weitergeht. Darunter die Punkte; mit Maus zusätzlich die Blätter-Pfeile
 *  daneben, am Anschlag gedimmt statt versteckt (DESIGNSPRACHE §6). */
function Kacheln({
  kacheln, gesehen, onOeffnen,
}: { kacheln: Highlight[]; gesehen: ReadonlySet<string>; onOeffnen: (i: number, von: HTMLElement) => void }) {
  const leiste = useRef<HTMLUListElement>(null);
  const [aktiv, setAktiv] = useState(0);

  const messen = useCallback(() => {
    const el = leiste.current;
    if (!el) return;
    const erste = el.firstElementChild as HTMLElement | null;
    if (!erste) return;
    const schritt = erste.getBoundingClientRect().width + 12;
    setAktiv(Math.max(0, Math.min(kacheln.length - 1, Math.round(el.scrollLeft / schritt))));
  }, [kacheln.length]);

  const blaettern = (richtung: 1 | -1) => {
    const el = leiste.current;
    const ziel = el?.children[Math.max(0, Math.min(kacheln.length - 1, aktiv + richtung))] as HTMLElement | undefined;
    if (!el || !ziel) return;
    const ruhig = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    el.scrollTo({ left: ziel.offsetLeft - el.offsetLeft - parseFloat(getComputedStyle(el).paddingLeft || "0"), behavior: ruhig ? "auto" : "smooth" });
  };

  const spalten = ["", "@3xl:grid-cols-1", "@3xl:grid-cols-2", "@3xl:grid-cols-3", "@3xl:grid-cols-4"][kacheln.length] ?? "@3xl:grid-cols-4";

  return (
    <div className="mt-5">
      <ul
        ref={leiste}
        onScroll={messen}
        aria-label="Neuerungen dieser Ausgabe"
        className={cn(
          // Schmal: Karussell bis an den Kartenrand.
          "scrollbar-none -mx-4 flex snap-x snap-mandatory scroll-px-4 gap-3 overflow-x-auto px-4 pb-3 pt-1 sm:-mx-6 sm:scroll-px-6 sm:px-6",
          // Breit: ein Raster, alle Kacheln auf einen Blick.
          "@3xl:mx-0 @3xl:grid @3xl:gap-4 @3xl:overflow-visible @3xl:px-0 @3xl:pb-1",
          spalten,
        )}
      >
        {kacheln.map((h, i) => (
          <li key={highlightSchluessel(h)} className="w-[78%] max-w-[300px] shrink-0 snap-start @3xl:w-auto @3xl:max-w-none">
            <Kachel h={h} nummer={i + 1} gesehen={gesehen.has(highlightSchluessel(h))} onOeffnen={(von) => onOeffnen(i, von)} />
          </li>
        ))}
      </ul>

      {kacheln.length > 1 && (
        <div className="mt-1 flex items-center justify-center gap-3 @3xl:hidden">
          <button
            type="button"
            onClick={() => blaettern(-1)}
            aria-label="Vorige Kachel"
            className={cn("hidden h-6 w-6 place-items-center rounded-full border border-border bg-card shadow-sm maus:grid", aktiv === 0 && "opacity-40")}
          >
            <ChevronLeft className="h-3.5 w-3.5" />
          </button>
          <div aria-hidden className="flex items-center gap-1.5">
            {kacheln.map((h, i) => (
              <span
                key={highlightSchluessel(h)}
                className={cn("h-2 rounded-full transition-[width,background-color] duration-fluss ease-out-strong",
                  i === aktiv ? "w-5 bg-signal" : "w-2 bg-border")}
              />
            ))}
          </div>
          <button
            type="button"
            onClick={() => blaettern(1)}
            aria-label="Nächste Kachel"
            className={cn("hidden h-6 w-6 place-items-center rounded-full border border-border bg-card shadow-sm maus:grid", aktiv === kacheln.length - 1 && "opacity-40")}
          >
            <ChevronRight className="h-3.5 w-3.5" />
          </button>
        </div>
      )}
    </div>
  );
}

/** „Außerdem: …" — eine Neuerung ohne eigene Kachel. Ein Tipp öffnet ihren
 *  Clip im Spieler, allein und ohne Fortschritt. */
function Nebenbei({ h, onOeffnen }: { h: Highlight; onOeffnen: (von: HTMLElement) => void }) {
  const bild = h.media?.cover ?? h.media?.poster ?? null;
  return (
    <button
      type="button"
      onClick={(e) => onOeffnen(e.currentTarget)}
      className="group mt-3 flex w-full items-center gap-3 rounded-xl bg-primary/[0.06] p-3 text-left outline-none transition-colors duration-tipp maus:hover:bg-primary/[0.1] focus-visible:ring-2 focus-visible:ring-ring"
    >
      {bild && (
        // eslint-disable-next-line @next/next/no-img-element -- s. o.
        <img src={bild} alt="" loading="lazy"
          className="hidden h-[54px] w-24 shrink-0 rounded-lg border border-border object-cover object-top @md:block" />
      )}
      <span className="min-w-0 flex-1">
        <span className="block text-[15px] leading-snug text-foreground">
          <span className="font-semibold">Außerdem:</span> {h.title}
        </span>
        {/* Schmal bleibt es eine Zeile wie im Entwurf — die Unterzeile
            steht im Spieler ohnehin unter dem Clip. */}
        {h.tagline && <span className="mt-0.5 hidden text-hinweis text-muted-foreground @md:block">{h.tagline}</span>}
      </span>
      <span className="inline-flex shrink-0 items-center gap-1 text-sm font-semibold text-primary">
        <span className="hidden @md:inline">Ansehen</span>
        <ArrowRight aria-hidden className="h-4 w-4 transition-transform duration-fluss ease-out-strong motion-safe:maus:group-hover:translate-x-0.5" />
      </span>
    </button>
  );
}

/** Ohne Medien: dieselben Sätze als Liste — lesbar, nur eben still. */
function Liste({ highlights }: { highlights: Highlight[] }) {
  return (
    <ul className="mt-2.5 grid gap-x-8 gap-y-2.5 @2xl:grid-cols-2">
      {highlights.map((h) => (
        <li key={highlightSchluessel(h)} className="min-w-0">
          <Link href={h.url} className="group block rounded-lg outline-none focus-visible:ring-2 focus-visible:ring-ring">
            <span className="text-sm font-semibold text-foreground [@media(hover:hover)]:group-hover:text-primary">
              {h.title}
              <ArrowRight aria-hidden className="ml-1 inline h-3.5 w-3.5 align-[-2px] text-primary transition-transform duration-fluss ease-out-strong [@media(hover:hover)]:group-hover:translate-x-0.5" />
            </span>
            <span className="mt-0.5 block text-sm leading-relaxed text-muted-foreground">{h.text}</span>
          </Link>
        </li>
      ))}
    </ul>
  );
}

type Spieler = {
  folge: Highlight[];
  start: number;
  nebenbei: boolean;
  /** Der Knopf, der ihn geöffnet hat — dorthin kehrt der Fokus zurück. */
  von: HTMLElement | null;
} | null;

export function ReleaseNewsCard() {
  const { user } = useAuth();
  const qc = useQueryClient();

  const { data } = useQuery({
    queryKey: NEWS_QUERY_KEY,
    queryFn: () => vertrag.get("/news"),
    enabled: !!user,
    // Eine Ausgabe erscheint ein paar Mal im Jahr — einmal je Sitzung reicht.
    staleTime: 60 * 60 * 1000,
  });

  /** × — die Karte ist weg, auf jedem Gerät. */
  const ausblenden = useMutation({
    mutationFn: (version: string) => api.post("/news/seen", { version }),
    // Optimistisch leeren: Die Karte soll beim Klick verschwinden, nicht nach
    // der Antwort. Ein Fehlschlag bringt sie beim nächsten Laden zurück —
    // besser, als eine weggewischte Karte stehen zu lassen.
    onMutate: () => {
      qc.setQueryData<NewsState>(NEWS_QUERY_KEY, (cur) =>
        cur ? { ...cur, releases: [], older_count: 0 } : cur);
    },
    onSettled: () => { void qc.invalidateQueries({ queryKey: NEWS_QUERY_KEY }); },
  });

  /** Alle angesehen — die Marke setzen, die Karte aber für diesen Besuch
   *  stehen lassen (kein Leeren, kein Neuladen: Der Spieler hängt an ihr). */
  const abschliessen = useMutation({
    mutationFn: (version: string) => api.post("/news/seen", { version }),
  });

  const releases = data?.releases ?? [];
  const neuestes = releases[0];
  const version = neuestes?.version;

  // Was auf diesem Gerät schon angesehen ist — erst nach dem Einhängen
  // gelesen: Der Server kennt den Speicher nicht, ein Haken, der beim
  // Hydrieren springt, wäre ein Fehler in der Konsole.
  const [gesehen, setGesehen] = useState<ReadonlySet<string>>(() => new Set());
  useEffect(() => { if (version) setGesehen(gesehenLesen(version)); }, [version]);
  const [spieler, setSpieler] = useState<Spieler>(null);

  const merken = useCallback((h: Highlight) => {
    if (!version || h.aside) return; // Nebenbei zählt nicht zum Fortschritt.
    setGesehen(new Set(gesehenMerken(version, highlightSchluessel(h))));
  }, [version]);

  const { kacheln, nebenbei } = aufteilen(neuestes?.highlights ?? []);
  const mitBildern = mitKacheln(neuestes);
  const anzahl = zaehleGesehen(kacheln, gesehen);
  const alle = mitBildern && kacheln.length > 0 && anzahl >= kacheln.length;

  // Alle angesehen → die Marke am Konto setzen, einmal je Version und Besuch.
  // Die Karte bleibt dabei stehen; s. Kopfkommentar, Punkt 1.
  const gemeldet = useRef<string | null>(null);
  const abschluss = abschliessen.mutate;
  useEffect(() => {
    if (alle && version && gemeldet.current !== version) {
      gemeldet.current = version;
      abschluss(version);
    }
  }, [alle, version, abschluss]);

  if (!neuestes) return null;

  const aeltere = releases.slice(1);
  const weitere = data?.older_count ?? 0;

  return (
    // `@container`: Die Karte steht im Hinweis-Slot über die volle Breite —
    // Kacheln nebeneinander erst, wenn die KARTE breit genug ist, nicht das
    // Fenster (neben der Seitenleiste ist dieselbe Fensterbreite schmaler).
    <Card className="@container relative rounded-2xl p-4 sm:p-6">
      <div className="flex items-start gap-3 pr-9 sm:gap-4 @3xl:items-center">
        {/* `hat-idee`: Lotti bringt etwas mit, sie warnt nicht. */}
        <Mascot decorative regung="hat-idee" className="h-14 w-14 flex-none sm:h-[72px] sm:w-[72px]" />
        <div className="min-w-0 flex-1">
          <p className={KICKER}>{kickerText(releases.map((r) => r.version))}</p>
          <h2 className="mt-0.5 font-display text-[26px] font-extrabold leading-[1.1] tracking-tight text-foreground sm:text-[30px]">
            {neuestes.title}
          </h2>
          {neuestes.teaser && (
            <p className="mt-1 text-hinweis text-muted-foreground sm:text-[15px]">{neuestes.teaser}</p>
          )}
        </div>
        {/* Am Schreibtisch oben rechts; schmal sagen es die Haken auf den
            Kacheln (der Entwurf hat dort keinen Platz dafür). */}
        {mitBildern && kacheln.length > 1 && (
          <div className="hidden @3xl:block">
            <Fortschritt gesamt={kacheln.length} gesehen={anzahl} />
          </div>
        )}
      </div>

      {/* Klein und in der Ecke — s. Kopfkommentar, Punkt 2. */}
      <button
        type="button"
        onClick={() => ausblenden.mutate(neuestes.version)}
        disabled={ausblenden.isPending}
        aria-label="Neuigkeiten ausblenden"
        title="Ausblenden"
        className="absolute right-2 top-2 grid h-10 w-10 place-items-center rounded-full text-muted-foreground transition-colors duration-tipp maus:hover:bg-muted maus:hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring sm:right-3 sm:top-3"
      >
        <X className="h-[18px] w-[18px]" />
      </button>

      {mitBildern ? (
        <>
          <Kacheln
            kacheln={kacheln}
            gesehen={gesehen}
            onOeffnen={(i, von) => setSpieler({ folge: kacheln, start: i, nebenbei: false, von })}
          />
          {nebenbei.map((h) => (
            <Nebenbei key={highlightSchluessel(h)} h={h}
              onOeffnen={(von) => setSpieler({ folge: [h], start: 0, nebenbei: true, von })} />
          ))}
          <NeuigkeitenSpieler
            offen={spieler !== null}
            folge={spieler?.folge ?? []}
            start={spieler?.start ?? 0}
            nebenbei={spieler?.nebenbei ?? false}
            onGesehen={merken}
            onSchliessen={() => setSpieler(null)}
            rueckkehr={spieler?.von}
          />
        </>
      ) : <Liste highlights={neuestes.highlights} />}

      {aeltere.length > 0 && (
        <div className="mt-4 border-t border-border pt-3">
          <p className="font-mono text-[10px] font-medium uppercase tracking-[0.08em] text-muted-foreground">
            Außerdem seit deinem letzten Besuch
          </p>
          <ul className="mt-1.5 flex flex-col gap-1">
            {aeltere.map((r) => (
              <li key={r.version} className="text-[13px] leading-snug text-muted-foreground">
                <span className="font-semibold text-foreground">{kurzVersion(r.version)}</span>
                {" — "}
                {r.highlights.map((h) => h.title).join(" · ")}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-2">
        {/* „dieser Version" stimmt nur, wenn es wirklich eine ist — bei
            mehreren stünde dort ein falsches Versprechen. */}
        <Link href="/changelog" className="text-[13px] text-muted-foreground underline hover:text-foreground">
          {weitere > 0
            ? `Alle Änderungen — auch ${weitere} ältere Version${weitere === 1 ? "" : "en"}`
            : releases.length > 1
              ? "Alle Änderungen im Einzelnen"
              : "Alle Änderungen dieser Version"}
        </Link>
      </div>
    </Card>
  );
}
