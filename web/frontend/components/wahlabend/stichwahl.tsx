"use client";

// /wahlabend/stichwahl — die Stichwahl um das Oberbürgermeisteramt.
//
// Warum eine eigene Seite und kein Reiter auf /wahlabend: Es ist eine andere
// Wahl, zwei Wochen später, mit einer anderen Frage. Auf /wahlabend steht
// weiter die Ratswahl — die bleibt auch am 27. September das, was Leute dort
// suchen.
//
// Alles Gerechnete kommt vom Backend (`GET /api/wahlabend/stichwahl`): Zahlen,
// Auszählungsstand, der Vergleich mit dem ersten Wahlgang. Hier steht nur, was
// die Anzeige daraus macht.

import { useEffect, useLayoutEffect, useRef, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { ChevronDown, Info } from "lucide-react";
import { Aufklapp } from "@/components/aufklapp";
import { Mascot } from "@/components/mascot";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { Kopf } from "@/components/wahlabend/kopf";
import { TippspielEinladung, useWahlzeile } from "@/components/tipp/einladung";
import { AuszaehlungsSimulator } from "@/components/wahlabend/simulator";
import { StichwahlKarte } from "@/components/wahlabend/stichwahl-karte";
import { Mitfiebern, StichwahlMomente } from "@/components/wahlabend/stichwahl-momente";
import { BezirksTicker, BildTeilen, Countdown } from "@/components/wahlabend/stichwahl-bausteine";
import { StichwahlVerlauf } from "@/components/wahlabend/stichwahl-verlauf";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useFeature } from "@/lib/features";
import { useFrisch, useTween } from "@/lib/use-tween";
import { cn } from "@/lib/utils";
import { prozent, uhrzeit, zahl } from "@/lib/wahlabend";
import {
  abfragePfad,
  TAKT_LIVE_MS,
  abrufTakt,
  abstandStimmen,
  aufholText,
  bezirkeText,
  chanceText,
  datumLang,
  fensterTitel,
  fuehrend,
  ladeFavorit,
  letzteMeldung,
  letzterWechsel,
  nachStimmen,
  nachname,
  verschiebung,
  vorsprung,
  zeitlage,
  type Stichwahl,
  type StichwahlHochrechnung,
  type StichwahlKandidat,
} from "@/lib/stichwahl";

const KICKER = "font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground";

/** So lange zählen Stimmen und Prozente zum neuen Stand hoch. Länger als die
 *  300 ms, die `useTween` sonst nimmt: Hier SOLL man zusehen, wie eine Zahl
 *  wächst — das ist der Moment des Abends (Tim 23.09.2026: „wirklich so
 *  hochzählen"). Die Balken laufen im selben Takt mit. */
const ZAEHLEN_MS = 1200;

/** Die Farbe der Liste — oder ein neutraler Ton, wenn die Kandidatur zu
 *  keiner gehört. Zwei Farbwerte, weil der Hellmodus einen dunkleren braucht. */
function farbe(k: StichwahlKandidat): { hell: string; dunkel: string } {
  return { hell: k.color || "#6b7a8c", dunkel: k.color_dark || "#a3b1c2" };
}

/* ── Anzeigetafel ───────────────────────────────────────────────────────── */

function Tafel({ daten, aktualisiert, probe, counted }: {
  daten: Stichwahl;
  aktualisiert: number;
  probe: string | null;
  counted: string | null;
}) {
  const zeit = zeitlage(daten.election.polls_close);
  const beteiligung = useTween(daten.turnout_pct, ZAEHLEN_MS);
  const gueltig = useTween(daten.valid_votes, ZAEHLEN_MS);
  const takt = abrufTakt(daten);
  const anteil = daten.reports_expected > 0 ? Math.round((daten.reports_received / daten.reports_expected) * 100) : 0;
  const phase =
    daten.phase === "before"
      ? "Noch nichts ausgezählt"
      : daten.phase === "complete"
        ? "Alle Wahlbezirke ausgezählt"
        : `${zahl(daten.reports_received)} von ${zahl(daten.reports_expected)} Wahlbezirken ausgezählt`;
  return (
    <section className="hh-tafel mt-5 rounded-2xl p-5 sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-x-8 gap-y-5">
        {/* `basis` statt nur `flex-1`: Auf 400 px schiebt sich die
            Kennzahlen-Spalte sonst NEBEN die Überschrift und drückt sie auf
            ein Wort je Zeile zusammen. Mit einer Mindestbreite bricht die
            Zeile stattdessen um — gemessen an einem iPhone-Ausschnitt. */}
        <div className="min-w-0 flex-1 basis-[18rem]">
          <p className={KICKER}>
            Oldenburg · {datumLang(daten.election.date)} ·{" "}
            <span suppressHydrationWarning>{daten.dataset === "probe" ? "Generalprobe" : zeit.kicker}</span>
          </p>
          <h1 className="mt-1 font-display text-[28px] font-bold leading-none tracking-tight sm:text-[32px]">Stichwahl</h1>
          <p className="mt-3 text-[14px] text-foreground">
            <strong className="font-semibold">{phase}</strong>
            {daten.fetched_at ? <span className="text-muted-foreground"> · Stand {uhrzeit(daten.fetched_at) ?? "–"} Uhr</span> : null}
          </p>
          <div className="mt-2 h-1.5 w-full max-w-md overflow-hidden rounded-full bg-foreground/10">
            <div
              className="h-full w-full origin-left rounded-full bg-primary transition-transform ease-out-strong"
              style={{ transform: `scaleX(${anteil / 100})`, transitionDuration: `${ZAEHLEN_MS}ms` }}
            />
          </div>
          <p className="mt-2 flex flex-col items-start gap-1 text-[11.5px] text-muted-foreground">
            {/* Live ab 18 Uhr — und in der Probe, die den Abend nachstellt. */}
            {(takt === TAKT_LIVE_MS || daten.dataset === "probe") && daten.ok && daten.phase !== "complete" ? (
              <AbfrageTakt seit={aktualisiert} ms={takt} />
            ) : null}
            {daten.dataset === "probe"
              ? "Geprobt wird mit den Zahlen des ersten Wahlgangs — live fragt die Seite alle 15 Sekunden nach."
              : daten.ok
                ? zeit.phase === "laeuft"
                  ? daten.phase === "complete"
                    ? "Alle Bezirke sind da — die Seite fragt nur noch jede Minute nach."
                    : "Die Seite fragt alle 15 Sekunden nach."
                  : `Ab ${zeit.tage === 0 ? "heute" : "Sonntag"} 18 Uhr fragt die Seite alle 15 Sekunden nach.`
                : (daten.error ?? "Der Votemanager antwortet gerade nicht.")}
          </p>
          <BildTeilen daten={daten} probe={probe} counted={counted} />
        </div>
        <dl className="grid grid-cols-2 gap-x-6 gap-y-1 text-left sm:text-right">
          <div>
            <dt className={KICKER}>Wahlbeteiligung</dt>
            <dd className="font-display text-[24px] font-bold tabular-nums">{prozent(beteiligung)}</dd>
          </div>
          <div>
            <dt className={KICKER}>Gültige Stimmen</dt>
            <dd className="font-display text-[24px] font-bold tabular-nums">{zahl(gueltig === null ? null : Math.round(gueltig))}</dd>
          </div>
        </dl>
      </div>
    </section>
  );
}

/** Live-Punkt und ein Balken, der sich bis zur nächsten Abfrage füllt: Auch
 *  zwischen zwei Meldungen sieht man, dass die Seite arbeitet — und wann sie
 *  wieder nachsieht. Ein neuer Abruf setzt ihn zurück. */
function AbfrageTakt({ seit, ms }: { seit: number; ms: number }) {
  const balken = useRef<HTMLSpanElement>(null);
  useEffect(() => {
    const el = balken.current;
    if (!el || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const a = el.animate([{ transform: "scaleX(0)" }, { transform: "scaleX(1)" }], {
      duration: ms,
      easing: "linear",
      fill: "forwards",
    });
    a.currentTime = Math.min(ms, Math.max(0, Date.now() - seit));
    return () => a.cancel();
  }, [seit, ms]);
  return (
    <span className="inline-flex items-center gap-2" aria-hidden data-testid="abfrage-takt">
      <span className="live-punkt inline-block h-2 w-2 rounded-full bg-signal" />
      <span className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-foreground">Live</span>
      <span className="font-mono text-[10px] uppercase tracking-[0.11em]">· nächste Abfrage</span>
      <span className="relative inline-block h-1 w-14 overflow-hidden rounded-full bg-foreground/10">
        <span ref={balken} className="absolute inset-0 origin-left rounded-full bg-foreground/35" style={{ transform: "scaleX(0)" }} />
      </span>
    </span>
  );
}

/* ── Die beiden ─────────────────────────────────────────────────────────── */

/** Was der Parteiname über dem Namen NICHT sagt: ob die Person Mitglied ist,
 *  und wer sie sonst noch unterstützt.
 *
 *  Beides steht nicht in der amtlichen Bekanntmachung — das Backend liefert
 *  es nur mit eigener Quelle, und die steht hier als Beleg daneben. Ohne
 *  Angaben bleibt die Zeile weg; sie ist kein Platzhalter. */
function Herkunft({ k }: { k: StichwahlKandidat }) {
  // Eingeklappt, was nur Erklärung ist (Tim 23.09.2026: „sehr viel Text
  // dafür, dass es eigentlich nur ein Disclaimer ist"): Die Zeile mit den
  // Parteien bleibt stehen, die Begründung zum Stimmzettel und die Belege
  // kommen auf Tipp.
  const [offen, setOffen] = useState(false);
  // Drei Stufen, die der Stimmzettel nicht unterscheidet: aufgestellt (eine
  // eigene Versammlung, wie bei Grünen UND CDU für Rohr), unterstützt (ein
  // Beschluss ohne Aufstellung, wie Volt) — und darüber die Frage, warum
  // dann nur eine Partei auf dem Zettel steht (`ballot_note`).
  const aufgestellt = k.co_nominated_by.length
    ? `aufgestellt von ${[k.party, ...k.co_nominated_by].filter(Boolean).join(" und ")}`
    : null;
  const teile = [
    k.independent ? "parteilos" : null,
    aufgestellt,
    k.supported_by.length ? `unterstützt von ${k.supported_by.join(", ")}` : null,
  ].filter(Boolean);
  if (!teile.length) return null;
  // Mehrere Belege bekommen ihren Absender als Beschriftung: Seit Volt
  // (15.09.2026) neben der CDU steht, deckt EIN Link nicht mehr beide
  // Aussagen — und zwei gleich beschriftete „Beleg"-Links wären ein Rätsel.
  const mehrere = k.note_sources.length > 1;
  const mehr = Boolean(k.ballot_note) || k.note_sources.length > 0;
  return (
    <div className="mt-1.5 text-[12.5px] leading-relaxed text-muted-foreground">
      <p>{teile.join(" · ")}</p>
      {mehr ? (
        <>
          <button
            type="button"
            onClick={() => setOffen((o) => !o)}
            aria-expanded={offen}
            className="mt-0.5 inline-flex items-center gap-1 rounded-md text-[12px] font-medium text-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            {k.ballot_note ? `Warum nur ${k.party || "eine Partei"} auf dem Stimmzettel?` : "Belege"}
            <ChevronDown className={cn("h-3.5 w-3.5 transition-transform duration-fluss", offen && "rotate-180")} aria-hidden />
          </button>
          <Aufklapp offen={offen}>
            <p className="pt-1 text-[12px] leading-relaxed">
              {k.ballot_note}
              {k.note_sources.map((quelle, i) => (
                <span key={quelle}>
                  {i === 0 ? (k.ballot_note ? " " : "") : " · "}
                  <a
                    href={quelle}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="font-medium text-primary underline-offset-2 hover:underline"
                  >
                    {mehrere ? `${absender(quelle)} ↗` : "Beleg ↗"}
                  </a>
                </span>
              ))}
            </p>
          </Aufklapp>
        </>
      ) : null}
    </div>
  );
}

/** „gruene-oldenburg.de" aus einer Beleg-Adresse — ohne „www.", damit die
 *  Zeile schmal bleibt. Eine kaputte Adresse gibt es selbst zurück, statt zu
 *  werfen: Ein Beleg-Link ist nie eine Seite wert. */
function absender(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

function Person({
  k,
  fuehrt,
  fertig,
  probe,
  hochrechnung,
  frisch,
  entschieden,
}: {
  k: StichwahlKandidat;
  fuehrt: boolean;
  fertig: boolean;
  probe: boolean;
  hochrechnung: number | null;
  /** Gerade neu gemeldet — die Karte leuchtet 1,6 s auf (§7 Bewegung). */
  frisch: boolean;
  /** Rechnerisch entschieden: Der Kicker sagt „Gewählt" statt „Vorn". */
  entschieden: boolean;
}) {
  const c = farbe(k);
  const anteil = useTween(k.share_pct, ZAEHLEN_MS);
  const stimmen = useTween(k.votes, ZAEHLEN_MS);
  const erwartet = useTween(hochrechnung, ZAEHLEN_MS);
  const diff = verschiebung(k);
  return (
    <article
      className={cn(
        "relative h-full overflow-hidden rounded-2xl border bg-card p-5 transition-[box-shadow,border-color] duration-fluss sm:p-6",
        fuehrt ? "border-foreground/25 shadow-sm" : "border-border",
        frisch && "shadow-lifted ring-2 ring-primary/40",
      )}
      data-testid="person"
      data-slug={k.slug}
    >
      <span
        aria-hidden
        className="absolute inset-x-0 top-0 h-1.5"
        style={{ background: `light-dark(${c.hell}, ${c.dunkel})` }}
      />
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          {/* „vorgeschlagen von", nicht bloß der Parteiname: Auf dem
              Stimmzettel steht je Kandidatur genau eine Liste, und wer sie
              aufgestellt hat, muss weder ihr Mitglied sein noch ihre einzige
              Unterstützung haben (Tims Hinweis 14.09.2026 zu Jascha Rohr). */}
          <p className={KICKER}>
            {k.party ? `vorgeschlagen von ${k.party}` : "Einzelwahlvorschlag"}
          </p>
          <h2 className="mt-1 truncate font-display text-[22px] font-bold tracking-tight sm:text-[26px]">{k.name}</h2>
          <Herkunft k={k} />
        </div>
        {fuehrt ? (
          <span className="flex-none rounded-md bg-foreground px-2 py-1 font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-background">
            {entschieden || (fertig && !probe) ? "Gewählt" : "Vorn"}
          </span>
        ) : null}
      </div>

      <p className="mt-4 font-display text-[44px] font-bold leading-none tabular-nums sm:text-[56px]">{prozent(anteil)}</p>
      {erwartet !== null ? (
        <p className="mt-1.5 text-[12.5px] tabular-nums text-muted-foreground" data-testid="hochrechnung-anteil">
          Hochrechnung <span className="font-semibold text-foreground">{prozent(erwartet)}</span>
        </p>
      ) : null}
      <div className="mt-3 h-2.5 w-full overflow-hidden rounded-full bg-foreground/10">
        {/* Über `transform` statt `width` (DESIGNSPRACHE §7), im Takt der
            hochzählenden Zahl; der Glanz läuft in den Pausen darüber. */}
        <div
          className="balken-glanz h-full w-full origin-left rounded-full transition-transform ease-out-strong"
          style={{
            transform: `scaleX(${Math.max(0, Math.min(100, k.share_pct ?? 0)) / 100})`,
            transitionDuration: `${ZAEHLEN_MS}ms`,
            background: `light-dark(${c.hell}, ${c.dunkel})`,
          }}
        />
      </div>
      <dl className="mt-4 flex flex-wrap gap-x-8 gap-y-2 text-[13px]">
        <div>
          <dt className={KICKER}>Stimmen</dt>
          <dd className="mt-0.5 font-semibold tabular-nums">{zahl(stimmen === null ? null : Math.round(stimmen))}</dd>
        </div>
        <div>
          <dt className={KICKER}>1. Wahlgang</dt>
          <dd className="mt-0.5 tabular-nums text-muted-foreground">
            {prozent(k.first_round_pct)}
            {diff !== null ? (
              <span className="ml-1.5 font-mono text-[11px] text-signal">
                {diff > 0 ? "+" : diff < 0 ? "−" : "±"}
                {Math.abs(diff).toFixed(1).replace(".", ",")}
              </span>
            ) : null}
          </dd>
        </div>
      </dl>
    </article>
  );
}

function Abstand({ daten }: { daten: Stichwahl }) {
  const punkte = vorsprung(daten.candidates);
  const stimmen = abstandStimmen(daten.candidates);
  if (punkte === null || stimmen === null || daten.phase === "before") return null;
  const vorn = fuehrend(daten.candidates);
  const name = daten.candidates.find((k) => k.slug === vorn)?.name;
  return (
    <p className="mt-4 text-[13.5px] leading-relaxed text-muted-foreground">
      {name ? (
        <>
          <strong className="font-semibold text-foreground">{name}</strong> liegt {zahl(stimmen)} Stimmen vorn — das sind{" "}
          {punkte.toFixed(1).replace(".", ",")} Prozentpunkte.
        </>
      ) : (
        <>Beide liegen gleichauf. Bei Stimmengleichheit entscheidet das Los (§ 45c Abs. 2 NKWG).</>
      )}
    </p>
  );
}

/* ── Die beiden nebeneinander — mit Platztausch ──────────────────────────── */

/** Die Karten stehen in der Reihenfolge des Stimmzettels im DOM und werden
 *  über `order` sortiert; wechselt die Führung, GLEITEN sie auf ihren neuen
 *  Platz (FLIP: alte Lage messen, neue Lage messen, Differenz als Transform
 *  setzen, dann in 300 ms auf null). Ein Sprung würde den Moment verschenken,
 *  um den es geht. `prefers-reduced-motion` legt den Übergang still. */
function Duell({
  daten,
  vorn,
  fertig,
  frisch,
  entschieden,
}: {
  daten: Stichwahl;
  vorn: string | null;
  fertig: boolean;
  frisch: boolean;
  entschieden: boolean;
}) {
  const rang = nachStimmen(daten.candidates).map((k) => k.slug);
  const raster = useRef<HTMLElement>(null);
  const lagen = useRef<Map<string, DOMRect>>(new Map());
  const schluessel = rang.join(">");
  useLayoutEffect(() => {
    const el = raster.current;
    if (!el) return;
    const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const karten = Array.from(el.querySelectorAll<HTMLElement>("[data-slug]"));
    const neu = new Map(karten.map((k) => [k.dataset.slug ?? "", k.getBoundingClientRect()]));
    for (const k of karten) {
      const slug = k.dataset.slug ?? "";
      const alt = lagen.current.get(slug);
      const jetzt = neu.get(slug);
      if (!alt || !jetzt || still) continue;
      const dx = alt.left - jetzt.left;
      const dy = alt.top - jetzt.top;
      if (Math.abs(dx) < 1 && Math.abs(dy) < 1) continue;
      k.style.transition = "none";
      k.style.transform = `translate(${dx}px, ${dy}px)`;
      void k.offsetWidth; // Reflow, damit der Start auch gesetzt ist
      k.style.transition = "transform 300ms var(--ease-in-out-strong)";
      k.style.transform = "";
      k.addEventListener("transitionend", () => { k.style.transition = ""; }, { once: true });
    }
    lagen.current = neu;
  }, [schluessel]);
  return (
    <section ref={raster} className="mt-5 grid gap-4 sm:grid-cols-2" data-testid="duell" aria-label="Die beiden Kandidaturen">
      {daten.candidates.map((k) => (
        <div key={k.slug} style={{ order: Math.max(0, rang.indexOf(k.slug)) }}>
          <Person
            k={k}
            fuehrt={k.slug === vorn}
            fertig={fertig}
            probe={daten.dataset === "probe"}
            hochrechnung={daten.projection && !fertig ? (daten.projection.shares[k.slug] ?? null) : null}
            frisch={frisch}
            entschieden={entschieden && k.slug === vorn}
          />
        </div>
      ))}
    </section>
  );
}

/* ── Die Meldung: was gerade dazukam ────────────────────────────────────── */

/** „18:42 · 12 weitere Bezirke ausgezählt — Prange +312, Rohr +298". Aus der
 *  Historie, nicht aus dem Browser-Zustand: Ein frisch geladener Tab sieht
 *  dieselbe Zeile. Der Schlüssel wechselt mit dem Stand, die Zeile gleitet
 *  deshalb bei jeder Meldung neu ein. */
function Meldung({ daten }: { daten: Stichwahl }) {
  const m = letzteMeldung(daten);
  if (!m || daten.phase === "before") return null;
  const wechsel = letzterWechsel(daten);
  const neuVorn = wechsel && wechsel.reports_received === daten.reports_received
    ? daten.candidates.find((k) => k.slug === wechsel.leader)
    : null;
  const teile = nachStimmen(daten.candidates).map((k) => `${nachname(k)} ${m.zuwachs[k.slug] >= 0 ? "+" : "−"}${zahl(Math.abs(m.zuwachs[k.slug] ?? 0))}`);
  return (
    <div
      key={daten.reports_received}
      className="mt-4 animate-in fade-in-0 slide-in-from-top-2 duration-fluss ease-out-strong"
      data-testid="meldung"
      role="status"
    >
      <p className="rounded-xl border border-border bg-card px-4 py-2.5 text-[13.5px] leading-relaxed">
        <span className="font-mono text-[11px] text-muted-foreground">{uhrzeit(m.at) ?? "–"}</span>
        <span className="mx-2 text-muted-foreground">·</span>
        <strong className="font-semibold">
          {m.bezirke === 1 ? "1 weiterer Bezirk" : `${zahl(m.bezirke)} weitere Bezirke`}
        </strong>{" "}
        ausgezählt — {teile.join(", ")}
        {neuVorn ? (
          <>
            <span className="mx-2 text-muted-foreground">·</span>
            <span className="font-semibold text-signal" data-testid="fuehrungswechsel-zeile">
              Führungswechsel — {neuVorn.name} liegt jetzt vorn
            </span>
          </>
        ) : null}
      </p>
    </div>
  );
}

/* ── Bühnen: vor 18 Uhr, und wenn es entschieden ist ────────────────────── */

function BuehneVorher({ daten, vorbei }: { daten: Stichwahl; vorbei: () => void }) {
  const zeit = zeitlage(daten.election.polls_close);
  return (
    <section className="mt-5 flex flex-col items-center gap-5 rounded-2xl border border-border bg-card p-6 text-center sm:flex-row sm:text-left" data-testid="buehne-vorher">
      <Mascot pose="wave" className="h-28 w-28 flex-none" decorative />
      <div className="min-w-0">
        <p className={KICKER} suppressHydrationWarning>{zeit.kicker}</p>
        <h2 className="mt-1 font-display text-[20px] font-bold tracking-tight">Was ab 18 Uhr passiert</h2>
        <Countdown pollsClose={daten.election.polls_close} vorbei={vorbei} />
        <p className="mt-2 max-w-[60ch] text-[13.5px] leading-relaxed text-muted-foreground">
          Am 13. September hat niemand die absolute Mehrheit erreicht; am {datumLang(daten.election.date)} entscheidet die
          Stichwahl zwischen den beiden Bestplatzierten. Ab 18 Uhr melden die 133 Wahlbezirke nach und nach — die Seite
          fragt alle 15 Sekunden nach, und jede neue Meldung leuchtet einmal kurz auf. Ab dem ersten Bezirk rechnet sie hoch, ab dem 15. nennt sie eine Chance, und sobald der
          Vorsprung größer ist als alles, was noch offen ist, steht hier, wer gewählt ist.
        </p>
      </div>
    </section>
  );
}

function BuehneEntschieden({ daten, p }: { daten: Stichwahl; p: StichwahlHochrechnung }) {
  const wer = daten.candidates.find((k) => k.slug === p.actual_leader);
  const fertig = p.open_ballot + p.open_postal === 0;
  return (
    <section
      className="mt-5 flex flex-col items-center gap-5 rounded-2xl border border-foreground/25 bg-card p-6 text-center shadow-sm animate-in fade-in-0 zoom-in-95 duration-fluss ease-out-strong sm:flex-row sm:text-left"
      data-testid="entschieden"
      aria-live="polite"
    >
      <Mascot pose="celebrate" className="h-28 w-28 flex-none" decorative />
      <div className="min-w-0">
        <p className={KICKER}>{daten.dataset === "probe" ? "Generalprobe · " : ""}{fertig ? "Endergebnis" : "Rechnerisch entschieden"}</p>
        <h2 className="mt-1 font-display text-[24px] font-bold tracking-tight sm:text-[28px]">
          {wer?.name ?? p.actual_leader} ist gewählt
        </h2>
        <p className="mt-2 max-w-[60ch] text-[14px] leading-relaxed text-muted-foreground">
          Der Vorsprung von <strong className="font-semibold text-signal">{zahl(p.actual_lead_votes)} Stimmen</strong>{" "}
          {fertig
            ? "steht — alle Bezirke sind gezählt."
            : `ist größer als alle Stimmen, die noch offen sind (höchstens ${zahl(p.open_votes_max)}).`}{" "}
          Kein amtliches Ergebnis; das stellt der Wahlausschuss fest.
        </p>
      </div>
    </section>
  );
}

/* ── Hochrechnung ───────────────────────────────────────────────────────── */

/** Die Karte „Hochrechnung": zwei große Zahlen, die Bezirkszahl daneben, die
 *  Chance des Führenden — und ⓘ mit dem, was das Modell annimmt. Nie ohne
 *  das Wort „Modell", nie ohne die Bezirkszahl (docs/plan-stichwahl-spannung.md S2). */
function Hochrechnung({ daten, p }: { daten: Stichwahl; p: StichwahlHochrechnung }) {
  const reihe = nachStimmen(daten.candidates).slice().sort((a, b) => (p.shares[b.slug] ?? 0) - (p.shares[a.slug] ?? 0));
  const fuehrt = daten.candidates.find((k) => k.slug === p.leader);
  const vorn = daten.candidates.find((k) => k.slug === p.actual_leader);
  const chance = chanceText(p, fuehrt?.name);
  const aufholen = aufholText(p, daten.candidates);
  const fertig = p.open_ballot + p.open_postal === 0;
  return (
    <section
      className={cn(
        "mt-5 rounded-2xl border bg-card p-5 sm:p-6",
        p.decided ? "border-foreground/25 shadow-sm" : "border-border",
      )}
      data-testid="hochrechnung"
      aria-label="Hochrechnung"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1">
        <h2 className={KICKER}>{fertig ? "Endstand" : "Hochrechnung"}</h2>
        <p className="text-[11.5px] tabular-nums text-muted-foreground">{bezirkeText(p)}</p>
      </div>
      <dl className="mt-3 grid grid-cols-2 gap-x-6">
        {reihe.map((k) => {
          const c = farbe(k);
          return (
            <div key={k.slug} className="min-w-0">
              <dt className="flex items-center gap-1.5 truncate text-[12.5px] text-muted-foreground">
                <span aria-hidden className="inline-block h-2 w-2 flex-none rounded-full" style={{ background: `light-dark(${c.hell}, ${c.dunkel})` }} />
                <span className="truncate">{k.name}</span>
              </dt>
              <dd className="mt-0.5 font-display text-[32px] font-bold leading-none tabular-nums sm:text-[40px]">
                <Zahl wert={p.shares[k.slug] ?? null} />
              </dd>
            </div>
          );
        })}
      </dl>

      {p.decided ? (
        <p className="mt-4 text-[13.5px] leading-relaxed text-muted-foreground">
          {fertig
            ? `Alle Bezirke sind gezählt; ${vorn?.name ?? p.actual_leader} liegt ${zahl(p.actual_lead_votes)} Stimmen vorn.`
            : `Rechnerisch entschieden: ${zahl(p.actual_lead_votes)} Stimmen Vorsprung, höchstens ${zahl(p.open_votes_max)} noch offen.`}
        </p>
      ) : null}
      {p.decided ? null : chance ? (
        <div className="mt-4 flex flex-wrap items-center gap-x-3 gap-y-1">
          <p className={cn("text-[14px]", p.chance_pct === null ? "text-muted-foreground" : "font-semibold")} data-testid="chance">
            {chance}
          </p>
          <p className="text-[12px] text-muted-foreground">Modell aus dem ersten Wahlgang je Bezirk</p>
        </div>
      ) : null}
      {/* Die Aufholrechnung (Tim 23.09.2026): die spannendste Zahl des
          Abends, solange es nicht entschieden ist — und reine Arithmetik
          auf der Hochrechnung, keine zweite Vorhersage. */}
      {aufholen ? (
        <p className="mt-2 text-[13.5px] leading-relaxed text-foreground" data-testid="aufholrechnung">
          {aufholen}
        </p>
      ) : null}

      <Sheet>
        <SheetTrigger asChild>
          <button
            type="button"
            className="mt-3 inline-flex items-center gap-1 rounded-md text-[12px] font-medium text-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <Info className="h-3.5 w-3.5" aria-hidden />
            Was das Modell annimmt
          </button>
        </SheetTrigger>
        <SheetContent side="bottom" className="px-5 pt-5 sm:px-8">
          <h3 className="font-display text-[18px] font-bold tracking-tight">Was das Modell annimmt</h3>
          <ul className="mt-3 max-w-[70ch] space-y-2 text-[13.5px] leading-relaxed text-muted-foreground">
            {p.caveats.map((c) => (
              <li key={c}>· {c}</li>
            ))}
            <li>
              · Die Chance ist Φ(Vorsprung ÷ Streuung) über die offenen Bezirke — eine Modellrechnung, keine Umfrage. Unter 15
              gezählten Bezirken zeigen wir sie nicht, über 99 % nie; „rechnerisch entschieden" ist dagegen kein Modell, sondern
              Arithmetik gegen die Wahlberechtigten der offenen Bezirke.
            </li>
            <li>· Geprüft an der Stichwahl 2021 (Krogmann gegen Fuhrhop): Nach 30 gezählten Bezirken nannte das Modell in jeder Auszählungsreihenfolge den Sieger.</li>
          </ul>
        </SheetContent>
      </Sheet>
    </section>
  );
}

/** Eine Prozentzahl, die sich beim Wechsel bewegt. */
function Zahl({ wert }: { wert: number | null }) {
  const v = useTween(wert, ZAEHLEN_MS);
  return <>{prozent(v)}</>;
}

/* ── Zustände ohne Zahlen ───────────────────────────────────────────────── */

function Hinweisbild({ pose, titel, text }: { pose: "sleep" | "wave" | "confused"; titel: string; text: string }) {
  return (
    <div className="mx-auto mt-16 flex max-w-md flex-col items-center text-center">
      <Mascot pose={pose} className="h-28 w-28" decorative />
      <h1 className="mt-4 font-display text-[22px] font-bold tracking-tight">{titel}</h1>
      <p className="mt-2 text-[14px] leading-relaxed text-muted-foreground">{text}</p>
    </div>
  );
}

/** Nach 18 Uhr: eine Zeile statt der Einladungskarte — wer getippt hat,
 *  findet die Rangliste, wer nicht, wird nicht mehr gefragt. */
function TippspielFussnote({ slug }: { slug: string }) {
  const zeile = useWahlzeile(slug);
  if (!zeile?.tipp_path) return null;
  return (
    <p className="mt-2">
      <Link href={zeile.tipp_path} className="font-medium text-primary">
        Tippspiel: Wer lag richtig? →
      </Link>
    </p>
  );
}

/** Ein leiser Hinweis auf Ratslotse für alle ohne Konto (Tims Wunsch
 *  23.09.2026): Am Stichwahl-Abend kommen viele zum ersten Mal hierher, und
 *  was nach der Wahl kommt, entscheidet der Rat. Eine Karte zwischen Karte
 *  und Einstellungen — kein Banner, nichts, das über den Zahlen steht, und
 *  nichts für Angemeldete. Erst nach `loading`: Sonst blitzte sie bei jedem
 *  Neuladen auch bei denen auf, die längst ein Konto haben. */
function RatslotseEinladung() {
  const { user, loading } = useAuth();
  if (loading || user) return null;
  return (
    <section
      className="mt-8 flex flex-col items-start gap-4 rounded-2xl border border-primary/20 bg-primary/[0.05] p-5 sm:flex-row sm:items-center"
      data-testid="ratslotse-einladung"
      aria-labelledby="ratslotse-einladung-titel"
    >
      <Mascot pose="point" className="hidden h-20 w-20 flex-none sm:block" decorative />
      <div className="min-w-0 flex-1">
        <p className={KICKER}>Nach der Wahl</p>
        <h2 id="ratslotse-einladung-titel" className="mt-1 font-display text-[17px] font-bold tracking-tight">
          Wer auch gewinnt: Entschieden wird im Rat.
        </h2>
        <p className="mt-1.5 max-w-[62ch] text-[13.5px] leading-relaxed text-muted-foreground">
          Du möchtest mehr über den Rat und seine Arbeit in Oldenburg erfahren? Ratslotse erklärt Sitzungen und
          Beschlüsse verständlich und meldet sich, wenn es um deine Themen oder dein Viertel geht. Kostenlos.
        </p>
      </div>
      <Link
        href="/register"
        className="inline-flex w-full flex-none items-center justify-center rounded-xl bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground transition-colors duration-fluss hover:bg-primary/90 sm:w-auto"
      >
        Kostenlos registrieren
      </Link>
    </section>
  );
}

/* ── Seite ──────────────────────────────────────────────────────────────── */

export function StichwahlView() {
  const params = useSearchParams();
  const probe = params.get("probe");
  const counted = params.get("counted");
  const frei = useFeature("wahlabend");

  const { data, isLoading, isError, dataUpdatedAt, refetch } = useQuery({
    queryKey: ["stichwahl", probe, counted],
    queryFn: () => api.get<Stichwahl>(abfragePfad(probe, counted)),
    enabled: frei,
    // Ab 18 Uhr alle 15 s, sonst jede Minute (`abrufTakt`). Auch im
    // Hintergrund-Tab: Der Fenstertitel trägt den Stand, und genau dafür
    // hat man den Tab im Hintergrund (Standard wäre: dort anhalten).
    refetchInterval: (q) => abrufTakt(q.state.data),
    refetchIntervalInBackground: true,
    // Der Simulator der Generalprobe wechselt den Schlüssel; ohne das stünde
    // bei jedem Schritt kurz das Skelett da — und die Momente sähen nie
    // einen Vorgängerstand.
    placeholderData: keepPreviousData,
    retry: 1,
  });
  // Wem man die Daumen drückt — erst nach dem Laden gelesen: Der Speicher
  // gehört dem Browser, der Server-Durchlauf kennt ihn nicht.
  const [favorit, setFavorit] = useState<string | null>(null);
  // Was der Ticker auf der Karte gezeigt haben will.
  const [kartenAuswahl, setKartenAuswahl] = useState<{ nr: number; n: number } | null>(null);
  const wahlSlug = data?.election.slug;
  const slugs = data?.candidates.map((k) => k.slug).join(",");
  useEffect(() => {
    if (wahlSlug && slugs) setFavorit(ladeFavorit(wahlSlug, slugs.split(",")));
  }, [wahlSlug, slugs]);
  // Vor den frühen Ausstiegen — Hooks laufen in jeder Runde in derselben Reihenfolge.
  const frisch = useFrisch(data?.reports_received);
  useEffect(() => {
    if (data) document.title = fensterTitel(data);
  }, [data]);

  if (!frei || isError) {
    return (
      <>
        <Kopf label="Stichwahl" />
        <main className="mx-auto w-full max-w-3xl px-4 pb-16 sm:px-6">
          <Hinweisbild
            pose="sleep"
            titel="Die Stichwahl ist noch nicht offen"
            text="Diese Seite zeigt ab dem 27. September ab 18 Uhr den Auszählungsstand. Bis dahin gibt es hier nichts zu sehen."
          />
        </main>
      </>
    );
  }
  if (isLoading || !data) {
    return (
      <>
        <Kopf label="Stichwahl" />
        <main className="mx-auto w-full max-w-3xl px-4 pb-16 sm:px-6">
          <div className="mt-10 h-40 animate-pulse rounded-2xl bg-muted" />
        </main>
      </>
    );
  }

  const vorn = fuehrend(data.candidates);
  const fertig = data.phase === "complete";
  const zu = zeitlage(data.election.polls_close).phase === "laeuft";
  const entschieden = Boolean(data.projection?.decided);

  return (
    <>
      <Kopf label="Stichwahl" />
      <main className="mx-auto w-full max-w-3xl px-4 pb-16 sm:px-6">
        {data.dataset === "probe" ? (
          <p className="mt-4 rounded-xl border border-amber-300/50 bg-amber-50 px-4 py-2.5 text-[13px] text-amber-900 dark:border-amber-700/40 dark:bg-amber-900/25 dark:text-amber-100">
            <strong className="font-semibold">Generalprobe.</strong> Die Zahlen sind die des ersten Wahlgangs vom
            13. September, umgerechnet auf die beiden verbliebenen Namen. Nichts davon ist ein Ergebnis vom 27. September.
          </p>
        ) : null}

        <Tafel daten={data} aktualisiert={dataUpdatedAt} probe={probe} counted={counted} />
        <Meldung daten={data} />
        <BezirksTicker daten={data} zeigen={(nr) => setKartenAuswahl((a) => ({ nr, n: (a?.n ?? 0) + 1 }))} />
        {/* Der Weg ins Tippspiel dieser Wahl — nur, solange getippt werden
            kann. Ab 18 Uhr gehört die Fläche dem Stand (Tim 23.09.2026: „ab
            18 Uhr weg"); die Rangliste steht dann leise im Fuß. Ob es ein
            Spiel gibt, sagt das Backend. */}
        {!zu ? <TippspielEinladung slug={data.election.slug} phase={data.phase} /> : null}
        {entschieden && data.projection ? <BuehneEntschieden daten={data} p={data.projection} /> : null}
        {data.phase === "before" ? <BuehneVorher daten={data} vorbei={() => void refetch()} /> : null}

        <Duell daten={data} vorn={vorn} fertig={fertig} frisch={frisch} entschieden={entschieden} />
        <Abstand daten={data} />

        {/* Einmal für beide, statt an einer Karte: Die Angabe über dem Namen
            ist der Wahlvorschlag. Wer das nicht weiß, liest sie als
            Parteibuch. */}
        <p className="mt-4 text-[12.5px] leading-relaxed text-muted-foreground">
          Über jedem Namen steht, wer die Kandidatur <strong className="font-semibold text-foreground">vorgeschlagen</strong> hat.
          Auf dem Stimmzettel ist je Kandidatur genau eine Liste zugelassen — wer dort steht, muss weder deren Mitglied
          sein noch ihre einzige Unterstützung haben.
        </p>


        {data.projection ? <Hochrechnung daten={data} p={data.projection} /> : null}
        {data.phase !== "before" ? <StichwahlVerlauf daten={data} /> : null}
        <StichwahlKarte daten={data} probe={probe} counted={counted} auswahl={kartenAuswahl} />

        <RatslotseEinladung />
        <Mitfiebern daten={data} favorit={favorit} setFavorit={setFavorit} />

        {data.notes.length > 0 ? (
          <ul className="mt-5 space-y-1.5 text-[12.5px] text-muted-foreground">
            {data.notes.map((n: string) => (
              <li key={n}>· {n}</li>
            ))}
          </ul>
        ) : null}

        <footer className="mt-10 border-t border-border pt-4 text-[12.5px] leading-relaxed text-muted-foreground">
          <p className="max-w-[76ch]">
            <strong className="font-semibold text-foreground">Quelle:</strong> Ergebnisdarstellung des Votemanagers der
            Stadt Oldenburg, am Abend alle 15 Sekunden abgerufen. Die Stichwahl hat — anders als die Ratswahl — keine
            Open-Data-Datei. Kein amtliches Ergebnis; das stellt der Wahlausschuss fest.{" "}
            <a href={data.election.presentation_url} className="font-medium text-primary" target="_blank" rel="noopener noreferrer">
              Zur amtlichen Ergebnispräsentation
            </a>
          </p>
          {zu ? <TippspielFussnote slug={data.election.slug} /> : null}
          <p className="mt-2">
            <Link href="/wahlabend" className="font-medium text-primary">
              ← Zum Wahlabend der Ratswahl
            </Link>
          </p>
        </footer>
      </main>
      <StichwahlMomente daten={data} favorit={favorit} />
      {/* Nur auf dev sichtbar — die Bedienung für die Generalprobe. */}
      <AuszaehlungsSimulator />
    </>
  );
}
