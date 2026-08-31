"use client";

// <Zeitstrahl> — der liegende Verfahrens-Strahl (GB-11).
//
// Ein Kreis hat kein Heute — der Strahl schon (H3-06). Er zeigt, WANN die
// Stationen eines Verfahrens liegen, mit einem „Sie sind hier"-Pin auf dem
// aktuellen Datum. Die Geometrie rechnet `scaleTime` (d3-scale), die
// Monats-Ticks kommen aus `scale.ticks()` — das sind die d3-time-Intervalle
// (GB-15: Beifang von scaleTime, offiziell nutzbar). Gerendert wird eigenes
// SVG + HTML; beschriftet wird über `Intl`, nie über d3-time-format.
//
// `gemessen` IST PFLICHT — je Station. Der Strahl behauptet nichts, was
// nicht aus den Jahrgängen gezählt ist: Wer eine Station ohne Zählangabe
// will, kommt am Typsystem nicht vorbei. Stationen, deren Lage nur aus
// früheren Jahrgängen gemessen ist (kein Termin!), tragen `ungefaehr` und
// werden mit „≈" beschriftet.
//
// BREAKPOINT-VERHALTEN (H4-A, eingebaut, kein Prop): ab 744 px liegend —
// Notizen über dem Strahl auf versetzten Ebenen, Monatsachse darunter.
// Unter 744 px kippt der Strahl senkrecht: Linie links, Stationen
// untereinander in Leserichtung, der Pin sortiert sich als eigener Eintrag
// ein, die Monatsachse entfällt — die Zeitangaben stehen an den Stationen
// (H4-14). Nichts entfällt: Beide Richtungen zeigen dieselben Stationen mit
// denselben Zählangaben.
//
// KEINE BEWERTUNGSFARBEN. Punkte und Zeiträume sind Hafenblau-Grammatik wie
// im Rest der App (RG-03: offener Punkt = öffentlich, noch kein Beschluss;
// gefüllt = beraten/beschlossen); der Termin aus dem Ratskalender ist
// gestrichelt („noch nicht") — Signal-Orange kommt hier nirgends vor, denn
// nichts an einem Kalender ist eine Abweichung.

import { Fragment, useMemo, type ReactNode } from "react";
import Link from "next/link";
import { scaleTime } from "d3-scale";
import { useBreite } from "@/lib/use-breite";
import { cn } from "@/lib/utils";

export type ZeitstrahlStation = {
  /** Kurzname der Station („Einbringung"). */
  label: string;
  /** Lage auf dem Strahl (ISO-Datum). Ohne `bis` ein Punkt, sonst Zeitraum. */
  von: string;
  bis?: string;
  /** PFLICHT: die ehrliche Zählangabe — „in 7 von 8 Jahrgängen im Oktober".
   *  Ohne sie kompiliert die Station nicht (GB-11). */
  gemessen: string;
  /** Offener Punkt: öffentlich, aber noch kein Beschluss (RG-03-Grammatik). */
  offen?: boolean;
  /** Lage aus früheren Jahrgängen gemessen, kein Termin — wird „≈"
   *  beschriftet und nie als Zusage gelesen. */
  ungefaehr?: boolean;
  /** Wohin die Station einlädt („Einladung statt Erklärseite", H3-06). */
  href?: string;
};

export type ZeitstrahlTermin = {
  label: string;
  /** ISO-Datum. */
  datum: string;
  /** Herkunft ist Teil des Vertrags: Der Strahl zeigt nur Termine, die
   *  wirklich im Ratskalender stehen — nichts Erratenes. */
  quelle: "kalender";
};

// ---- Beschriftung: Intl statt d3-time-format (GB-15) ---------------------

const MONAT = new Intl.DateTimeFormat("de-DE", { month: "short" });
const TAG_MONAT = new Intl.DateTimeFormat("de-DE", { day: "numeric", month: "short" });

function datumAus(iso: string): Date {
  const [j, m, t] = iso.split("-").map(Number);
  return new Date(j, (m || 1) - 1, t || 1);
}

/** „Okt. 25" — Monat + zweistelliges Jahr, für Achse und Zeiträume. */
function monatJahr(d: Date): string {
  return `${MONAT.format(d)} ${String(d.getFullYear()).slice(2)}`;
}

/** Die Zeitangabe einer Station: Punkt exakt („9. Feb. 26"), Zeitraum auf
 *  Monatsebene („Okt.–Dez. 25"), Gemessenes mit „≈". */
function zeitText(s: ZeitstrahlStation): string {
  const von = datumAus(s.von);
  if (s.ungefaehr) return `≈ ${monatJahr(von)}`;
  if (!s.bis) return `${TAG_MONAT.format(von)} ${String(von.getFullYear()).slice(2)}`;
  const bis = datumAus(s.bis);
  if (von.getFullYear() === bis.getFullYear() && von.getMonth() === bis.getMonth()) {
    return monatJahr(von);
  }
  if (von.getFullYear() === bis.getFullYear()) {
    return `${MONAT.format(von)}–${monatJahr(bis)}`;
  }
  return `${monatJahr(von)}–${monatJahr(bis)}`;
}

// ---- Geometrie des liegenden Strahls -------------------------------------

const PAD = 10;
const NOTE_W = 160;
/** Bis zu drei Versatz-Ebenen für die Notizen: Um den Jahreswechsel drängen
 *  sich Ausschüsse, Jahresbeginn und Ratsbeschluss auf wenige Wochen — zwei
 *  Ebenen reichten dort nicht (gemessen am Jahrgang 2026). */
const EBENE_H = 86;
const NOTE_H = 78;
const BAND = 16;

export function Zeitstrahl({ stationen, heute, termin, beleg, className }: {
  stationen: ZeitstrahlStation[];
  heute: Date;
  termin?: ZeitstrahlTermin;
  /** Beleg-Chip der Seite — Pflicht-Slot jeder Grafik (GB-00). */
  beleg?: ReactNode;
  className?: string;
}) {
  const { box, breite } = useBreite(640, 320);

  const sortiert = useMemo(
    () => [...stationen].sort((a, b) => a.von.localeCompare(b.von)),
    [stationen],
  );

  const { skala, ticks } = useMemo(() => {
    const daten = sortiert.flatMap((s) => [datumAus(s.von), datumAus(s.bis ?? s.von)]);
    daten.push(heute);
    if (termin) daten.push(datumAus(termin.datum));
    const min = new Date(Math.min(...daten.map((d) => +d)));
    const max = new Date(Math.max(...daten.map((d) => +d)));
    // Auf Monatsgrenzen erweitern, damit weder der erste noch der letzte
    // Punkt auf der Kante klebt.
    const von = new Date(min.getFullYear(), min.getMonth(), 1);
    const bis = new Date(max.getFullYear(), max.getMonth() + 1, 1);
    const s = scaleTime([von, bis], [PAD, Math.max(breite - PAD, PAD + 1)]);
    // d3-time-Ticks: saubere Monats-/Quartalsgrenzen, mobil weniger.
    return { skala: s, ticks: s.ticks(breite < 900 ? 5 : 8) };
  }, [sortiert, heute, termin, breite]);

  if (!sortiert.length) return null;

  // Notiz-Platzierung. Anker ist die Mitte des Zeitraums; platziert wird in
  // Anker-Reihenfolge auf bis zu drei Ebenen. Eine Notiz darf dabei BEGRENZT
  // nach rechts rutschen (Punkte ein Stück, Zeiträume bis kurz vor ihr
  // Ende) — der Verbinder läuft dann schräg zum Anker, keine Station wird
  // verschoben. Ohne das Rutschen liefen um den Jahreswechsel (Ausschüsse,
  // Jahresbeginn, Ratsbeschluss binnen weniger Wochen) auch drei Ebenen
  // voll, und die letzte Notiz läge auf ihrer Nachbarin.
  const noten = (() => {
    const platziert = sortiert.map((s) => {
      const x0 = skala(datumAus(s.von));
      const x1 = skala(datumAus(s.bis ?? s.von));
      const anker = (x0 + x1) / 2;
      const gewuenscht = Math.min(Math.max(anker - NOTE_W / 2, 0), Math.max(breite - NOTE_W, 0));
      return { s, x0, x1, anker, gewuenscht, links: gewuenscht, level: 0 };
    });
    const frei = [-Infinity, -Infinity, -Infinity];
    const rechts = Math.max(breite - NOTE_W, 0);
    for (const n of [...platziert].sort((a, b) => a.gewuenscht - b.gewuenscht)) {
      const kandidaten = frei.map((f) => Math.min(Math.max(n.gewuenscht, f), rechts));
      const grenze = n.s.bis
        ? Math.max(n.x1 - 48, n.gewuenscht)
        : n.gewuenscht + 40;
      let level = kandidaten.findIndex((k, e) => k >= frei[e] && k <= grenze);
      if (level === -1) {
        // Notlösung: die Ebene mit dem kleinsten Versatz.
        level = kandidaten.reduce((best, k, e) => (k < kandidaten[best] ? e : best), 0);
      }
      n.level = level;
      n.links = kandidaten[level];
      frei[level] = n.links + NOTE_W + 8;
    }
    return platziert;
  })();

  // Höhe aus den wirklich belegten Ebenen — meist zwei, am Jahreswechsel
  // drei. Der Strahl rückt entsprechend nach unten.
  const ebenen = Math.max(...noten.map((n) => n.level)) + 1;
  const RAIL_TOP = ebenen * EBENE_H + 6;
  const RAIL_MITTE = RAIL_TOP + BAND / 2;
  const H = RAIL_TOP + BAND + (termin ? 64 : 48);

  const heuteX = skala(heute);
  const terminX = termin ? skala(datumAus(termin.datum)) : null;
  const heuteText = `Sie sind hier · ${TAG_MONAT.format(heute)}`;

  return (
    <div className={cn(className)}>
      {/* ---- ab 744 px: liegend ---- */}
      <div ref={box} className="relative hidden [@media(min-width:744px)]:block" style={{ height: H }}>
        <svg
          viewBox={`0 0 ${breite} ${H}`}
          className="absolute inset-0 h-full w-full"
          aria-hidden="true"
          focusable="false"
        >
          {/* Verbinder Notiz → Strahl. Vor dem Band gezeichnet, damit sie
              darunter enden statt darüber zu liegen. Ist eine Notiz zur
              Seite gerutscht, läuft ihr Verbinder schräg zum Anker. */}
          {noten.map(({ s, anker, links, level }) => {
            const vonX = Math.min(Math.max(anker, links + 12), links + NOTE_W - 12);
            return (
              <line
                key={`v-${s.label}`}
                x1={vonX} y1={level * EBENE_H + NOTE_H - 6} x2={anker} y2={RAIL_TOP}
                strokeWidth={1}
                strokeDasharray={s.ungefaehr ? "3 3" : undefined}
                className="stroke-border"
              />
            );
          })}

          {/* Der Strahl selbst. */}
          <rect x={PAD} y={RAIL_TOP} width={Math.max(breite - 2 * PAD, 1)} height={BAND}
            rx={BAND / 2} className="fill-muted" />

          {/* Zeiträume als Segmente, Punkte als Kreise — RG-03-Grammatik.
              Erst alle Segmente, dann alle Punkte: Ein Beschluss-Punkt im
              Haushaltsjahr-Band bliebe sonst unter der Fläche. */}
          {noten.filter(({ s }) => s.bis).map(({ s, x0, x1 }) => (
            <rect
              key={`z-${s.label}`}
              x={x0} y={RAIL_TOP} width={Math.max(x1 - x0, 2)} height={BAND}
              rx={BAND / 2}
              strokeDasharray={s.ungefaehr ? "3 3" : undefined}
              className={s.ungefaehr
                ? "fill-primary/10 stroke-primary/45"
                : "fill-primary/25"}
            />
          ))}
          {noten.filter(({ s }) => !s.bis).map(({ s, x0 }) => (
            <circle
              key={`z-${s.label}`}
              cx={x0} cy={RAIL_MITTE} r={5}
              strokeWidth={2}
              strokeDasharray={s.ungefaehr ? "2.5 2.5" : undefined}
              className={s.offen || s.ungefaehr
                ? "fill-card stroke-primary"
                : "fill-primary stroke-primary"}
            />
          ))}

          {/* Monatsachse aus den d3-time-Ticks. Marken, die dem Heute-Pin zu
              nahe kommen, weichen — sein Label braucht die Zeile. */}
          {ticks.map((t) => {
            const x = skala(t);
            // Randmarken fallen weg: halb abgeschnittene Monatsnamen an den
            // Kanten wären keine Auskunft. Nah am Heute-Pin weicht die Achse
            // ebenfalls — sein Label braucht die Zeile.
            if (x < 28 || x > breite - 28 || Math.abs(x - heuteX) < 34) return null;
            return (
              <Fragment key={+t}>
                <line x1={x} y1={RAIL_TOP + BAND} x2={x} y2={RAIL_TOP + BAND + 5}
                  strokeWidth={1} className="stroke-border" />
                <text x={x} y={RAIL_TOP + BAND + 18} textAnchor="middle" fontSize={9.5}
                  className="fill-muted-foreground font-mono uppercase tracking-[0.07em]">
                  {monatJahr(t)}
                </text>
              </Fragment>
            );
          })}

          {/* SIE SIND HIER: Pin mit Halo — die Marke, die den Strahl vom
              Kreis unterscheidet. */}
          <line x1={heuteX} y1={RAIL_TOP - 8} x2={heuteX} y2={RAIL_TOP + BAND + 24}
            strokeWidth={1.5} className="stroke-primary" />
          <circle cx={heuteX} cy={RAIL_MITTE} r={10} className="fill-primary/20" />
          <circle cx={heuteX} cy={RAIL_MITTE} r={5.5} className="fill-primary" />
          <text
            x={Math.min(Math.max(heuteX, 70), breite - 70)}
            y={RAIL_TOP + BAND + 40}
            textAnchor="middle" fontSize={9.5} fontWeight={600}
            className="fill-primary font-mono uppercase tracking-[0.09em]"
          >
            {heuteText}
          </text>

          {/* Termin aus dem Ratskalender: gestrichelter Ring („noch nicht"),
              Label unter der Heute-Zeile. */}
          {termin && terminX != null && (
            <>
              <circle cx={terminX} cy={RAIL_MITTE} r={5} strokeWidth={1.5}
                strokeDasharray="2.5 2.5" className="fill-card stroke-foreground/55" />
              <text
                x={Math.min(Math.max(terminX, 110), breite - 110)}
                y={RAIL_TOP + BAND + 56}
                textAnchor="middle" fontSize={9}
                className="fill-muted-foreground font-mono uppercase tracking-[0.08em]"
              >
                {termin.label} · {TAG_MONAT.format(datumAus(termin.datum))} · Ratskalender
              </text>
            </>
          )}
        </svg>

        {/* Die Notizen als echter Text über dem Strahl — Links bleiben Links,
            die Vorlesehilfe liest sie in Zeitreihenfolge. */}
        {noten.map(({ s, links, level }) => (
          <div
            key={s.label}
            className="absolute"
            style={{ left: links, top: level * EBENE_H, width: NOTE_W }}
          >
            <StationsText s={s} kompakt />
          </div>
        ))}
      </div>

      {/* ---- unter 744 px: senkrecht ---- */}
      <ol className="relative flex flex-col [@media(min-width:744px)]:hidden">
        {/* Die Linie links — die Stationen sitzen mit ihren Markern darauf. */}
        <span aria-hidden className="absolute bottom-2 left-[7px] top-2 w-px bg-border" />
        {senkrechteEintraege(sortiert, heute, termin).map((e) => (
          <li key={e.key} className="relative flex gap-3 py-2.5 pl-0">
            <span className="relative z-[1] mt-[3px] flex h-4 w-4 flex-none items-center justify-center">
              {e.art === "heute" ? (
                <>
                  <span className="absolute h-4 w-4 rounded-full bg-primary/20" />
                  <span className="h-[11px] w-[11px] rounded-full bg-primary" />
                </>
              ) : e.art === "termin" ? (
                <span className="h-[11px] w-[11px] rounded-full border-[1.5px] border-dashed border-foreground/55 bg-card" />
              ) : (
                <span
                  className={cn(
                    "h-[11px] w-[11px] rounded-full",
                    e.station?.bis
                      ? "rounded-[4px] bg-primary/30"
                      : e.station?.offen || e.station?.ungefaehr
                        ? "border-2 border-primary bg-card"
                        : "bg-primary",
                  )}
                  style={e.station?.ungefaehr ? { borderStyle: "dashed" } : undefined}
                />
              )}
            </span>
            <div className="min-w-0 flex-1">
              {e.art === "heute" ? (
                <p className="font-mono text-[10.5px] font-semibold uppercase tracking-[0.09em] text-primary">
                  {heuteText}
                </p>
              ) : e.art === "termin" && termin ? (
                <>
                  <p className="text-[13px] font-semibold leading-snug">{termin.label}</p>
                  <p className="mt-0.5 font-mono text-[10px] uppercase tracking-[0.07em] text-muted-foreground">
                    {TAG_MONAT.format(datumAus(termin.datum))}{" "}
                    {datumAus(termin.datum).getFullYear()} · aus dem Ratskalender
                  </p>
                </>
              ) : e.station ? (
                <StationsText s={e.station} />
              ) : null}
            </div>
          </li>
        ))}
      </ol>

      {/* Quellenzeile mit Beleg-Chip — unter beiden Richtungen dieselbe. */}
      {beleg && (
        <p className="mt-1 text-right font-mono text-[10px] uppercase tracking-[0.07em] text-muted-foreground">
          {beleg}
        </p>
      )}
    </div>
  );
}

/** Label (ggf. als Einladungs-Link), Zeitangabe, Zählangabe — dieselben drei
 *  Zeilen in beiden Richtungen, damit kein Gerät weniger erfährt. */
function StationsText({ s, kompakt = false }: { s: ZeitstrahlStation; kompakt?: boolean }) {
  const label = s.href ? (
    <Link href={s.href} className="underline-offset-2 hover:underline focus-visible:underline">
      {s.label}
    </Link>
  ) : (
    s.label
  );
  return (
    <>
      <p className={cn("font-semibold leading-snug", kompakt ? "text-[12.5px]" : "text-[13px]")}>
        {label}
      </p>
      <p className="mt-0.5 font-mono text-[10px] uppercase tracking-[0.07em] tabular-nums text-muted-foreground">
        {zeitText(s)}
      </p>
      <p className={cn(
        "mt-0.5 leading-snug text-muted-foreground",
        kompakt ? "text-[10.5px]" : "text-[11.5px]",
      )}>
        {s.gemessen}
      </p>
    </>
  );
}

type SenkrechtEintrag = {
  key: string;
  art: "station" | "heute" | "termin";
  datum: string;
  station?: ZeitstrahlStation;
};

/** Senkrechte Reihenfolge: Stationen, Heute-Pin und Termin nach Datum
 *  einsortiert — Leserichtung = Zeitachse, nichts entfällt (H4-A). */
function senkrechteEintraege(
  stationen: ZeitstrahlStation[],
  heute: Date,
  termin?: ZeitstrahlTermin,
): SenkrechtEintrag[] {
  const iso = (d: Date) =>
    `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  const liste: SenkrechtEintrag[] = stationen.map((s) => ({
    key: `s-${s.label}`, art: "station", datum: s.von, station: s,
  }));
  liste.push({ key: "heute", art: "heute", datum: iso(heute) });
  if (termin) liste.push({ key: "termin", art: "termin", datum: termin.datum });
  return liste.sort((a, b) => a.datum.localeCompare(b.datum));
}
