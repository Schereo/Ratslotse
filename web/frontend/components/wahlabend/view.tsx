"use client";

// /wahlabend — der Wahlabend zur Ratswahl am 13.09.2026.
//
// Alles Gerechnete kommt vom Backend (`GET /api/wahlabend`): Sitze nach NKWG,
// Hochrechnung, Abstände. Diese Datei zeigt es nur — in der Reihenfolge, in
// der man am Wahlabend fragt: Wie weit ist die Auszählung? Wie stehen die
// Listen? Und dann für EINE Liste: Wer ist in welchem Wahlbereich drin, wer
// knapp dran? Die Seite fragt einmal je Minute nach, so lange cacht auch der
// Votemanager der Stadt.

import { ChevronDown } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Mascot } from "@/components/mascot";
import { KICKER, Punkt, TON } from "@/components/wahlabend/bausteine";
import { Halbkreis } from "@/components/wahlabend/halbkreis";
import { Kandidaten, type KandidatenFilter } from "@/components/wahlabend/kandidaten";
import { Wahlgebiete } from "@/components/wahlabend/wahlgebiete";
import { Rangfolge, bereichAnker, springeZuBereich } from "@/components/wahlabend/rangfolge";
import { Kopf } from "@/components/wahlabend/kopf";
import { ReiterLeiste, ReiterTafel, type Reiter } from "@/components/ui/reiter";
import { Mehrheiten } from "@/components/wahlabend/mehrheiten";
import { Verlauf } from "@/components/wahlabend/verlauf";
import { useFrisch, useTween } from "@/lib/use-tween";
import { useWahlabendZeit } from "@/components/wahlabend-hinweis";
import { api, apiUrl } from "@/lib/api";
import { useAppConfig, useFeature } from "@/lib/features";
import { cn } from "@/lib/utils";
import {
  datumLang,
  LISTE_SPEICHER,
  abfragePfad,
  bildPfad,
  kartePfad,
  type KartenFormat,
  delta,
  fortschritt,
  kandidatenStatus,
  nachStimmen,
  prozent,
  sitzgrenze,
  standText,
  uhrzeit,
  vorneDrei,
  zahl,
  type KandidatenSortierung,
  type StatusTon,
  type Wahlabend,
  type WahlabendBereich,
  type WahlabendKandidat,
  type WahlabendPartei,
} from "@/lib/wahlabend";

/* ── Kopf & Fuß ─────────────────────────────────────────────────────────── */

function Fuss({ daten }: { daten: Wahlabend | undefined }) {
  return (
    <footer className="mt-10 border-t border-border pt-4 text-[12.5px] leading-relaxed text-muted-foreground">
      <p className="max-w-[76ch]">
        <strong className="font-semibold text-foreground">Quelle:</strong> Open-Data-Dateien des Votemanagers der Stadt
        Oldenburg, alle 60 Sekunden abgerufen. Datenlizenz Deutschland – Namensnennung – 2.0.
        {daten ? (
          <>
            {" "}
            <a href={daten.election.presentation_url} className="font-medium text-primary" target="_blank" rel="noopener noreferrer">
              Zur amtlichen Ergebnispräsentation
            </a>
          </>
        ) : null}
      </p>
      <p className="mt-2">
        <Link href="/wahlen" className="font-medium text-primary">
          Alle Wahlen in Oldenburg →
        </Link>
      </p>
      <p className="mt-2 max-w-[76ch]">
        <strong className="font-semibold text-foreground">Unsere Rechnung:</strong> Die Sitze folgen dem Verfahren des
        Niedersächsischen Kommunalwahlgesetzes (§§ 36, 37 — dreimal Hare/Niemeyer: Listen, Wahlbereiche, dann Listen-
        gegen Personensitze). Gegen das amtliche Ergebnis von 2021 geprüft, alle 50 Mandate. Die Hochrechnung setzt für
        jeden offenen Wahlbezirk sein Ergebnis von {daten?.election.previous_label ?? "der Vorwahl"} an, skaliert mit dem Trend der schon ausgezählten Bezirke im
        selben Wahlbereich. Kein amtliches Ergebnis — das stellt der Wahlausschuss fest.
      </p>
    </footer>
  );
}

/* ── Karten zum Teilen ──────────────────────────────────────────────────── */

/** Die Auswahl „Beitrag · Story“ (und quer, wo Platz ist) für eine Karte. */
function KartenLinks({
  liste,
  bereich,
  platz,
  probe,
  counted,
  stadtweit = false,
  name,
  vorwahl,
}: {
  liste: string;
  bereich: number | null;
  platz: number | null;
  probe: string | null;
  counted: string | null;
  /** Die Listenkarte: dazu das Querformat und der Schalter für den Vergleich
   *  zur Vorwahl. */
  stadtweit?: boolean;
  name: string;
  /** Wie die Vorwahl heißt („2021") — leer, wenn es keine gibt. */
  vorwahl: string;
}) {
  const [vergleich, setVergleich] = useState(true);
  const formate: { format: KartenFormat; label: string }[] = [
    { format: "beitrag", label: "Beitrag" },
    { format: "story", label: "Story" },
    ...(stadtweit ? [{ format: "quer" as const, label: "quer" }] : []),
  ];
  return (
    <span className="inline-flex flex-wrap items-center gap-x-1.5">
      <span>Bild zum Teilen:</span>
      {formate.map((f, i) => (
        <span key={f.format}>
          {i > 0 ? <span className="mr-1.5 text-muted-foreground">·</span> : null}
          <a
            href={apiUrl(kartePfad(liste, bereich, platz, f.format, probe, counted, vergleich))}
            target="_blank"
            rel="noopener noreferrer"
            className="font-medium text-primary"
            aria-label={`${name}: Bild zum Teilen als ${f.label} ↗`}
          >
            {f.label} ↗
          </a>
        </span>
      ))}
      {stadtweit && vorwahl ? (
        <label className="ml-2 inline-flex cursor-pointer items-center gap-1.5 text-muted-foreground">
          <input
            type="checkbox"
            checked={vergleich}
            onChange={(e) => setVergleich(e.target.checked)}
            className="h-3.5 w-3.5 accent-primary"
          />
          mit Vergleich zu {vorwahl}
        </label>
      ) : null}
    </span>
  );
}

/** Die Stichwahl ist die Frage, die nach der Ratswahl offen blieb — auf DIESER
 *  Seite steht sie nicht, also gehört hier ein Weg dorthin. Ohne Datum im
 *  Code: Es kommt aus der Antwort der Stichwahl-Seite. */
function StichwahlHinweis() {
  return (
    <section className="mt-4 flex flex-wrap items-center gap-x-3 gap-y-1.5 rounded-xl border border-border bg-muted/40 px-4 py-2.5 text-[13px]">
      <span className={cn(KICKER, "text-foreground")}>Am 27. September</span>
      <span>
        Beim Oberbürgermeisteramt hat niemand die absolute Mehrheit erreicht — es gibt eine{" "}
        <Link href="/wahlabend/stichwahl" className="font-medium text-primary">
          Stichwahl
        </Link>
        .
      </span>
    </section>
  );
}

/** Der Hinweis, dass es die Karten neu gibt — mit festem Platz unter der
 *  Anzeigetafel, nicht wegklickbar, nicht aufdringlich: Wer die Seite am
 *  Wahlabend schon kannte, soll sehen, was dazugekommen ist. */
function NeuKarten({ liste }: { liste: string | null }) {
  return (
    <section className="mt-4 flex flex-wrap items-center gap-x-3 gap-y-1.5 rounded-xl border border-primary/16 bg-primary/5 px-4 py-2.5 text-[13px]">
      <span className="rounded-md bg-primary px-1.5 py-0.5 font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-primary-foreground">
        Neu
      </span>
      <span>
        <strong className="font-semibold">Ein Bild zum Teilen für jede Liste, jeden Wahlbereich und jede Person</strong> — als
        Beitrag (4:5) oder Story (9:16), mit Lotti und einem Danke an die Wählenden.{" "}
        {liste ? (
          <span className="text-muted-foreground">Die Links stehen unten neben der Liste, an jedem Wahlbereich und an jeder Person.</span>
        ) : (
          <span className="text-muted-foreground">Wähle unten eine Liste, dann stehen die Links neben der Liste, an jedem Wahlbereich und an jeder Person.</span>
        )}
      </span>
    </section>
  );
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

/* ── Anzeigetafel ───────────────────────────────────────────────────────── */

function Tafel({
  daten,
  aktualisiert,
  probe,
  counted,
  abfrageFehler,
}: {
  daten: Wahlabend;
  aktualisiert: number;
  probe: string | null;
  counted: string | null;
  abfrageFehler: boolean;
}) {
  const p = daten.progress;
  const zeit = useWahlabendZeit(daten.election.polls_close);
  const beteiligung = useTween(daten.totals.turnout_pct);
  const gueltig = useTween(daten.totals.valid_votes);
  const bild = apiUrl(bildPfad(daten.phase === "counting" ? "projected_seats" : "seats", probe, counted));
  const anteil = fortschritt(p.districts_counted, p.districts_total);
  const stand = standText(daten.source.last_modified ? new Date(daten.source.last_modified).toISOString() : daten.source.fetched_at);
  const phase =
    daten.phase === "before"
      ? "Noch nichts ausgezählt"
      : daten.phase === "complete"
        ? "Alle Wahlbezirke ausgezählt"
        : `${zahl(p.districts_counted)} von ${zahl(p.districts_total)} Wahlbezirken ausgezählt`;
  return (
    <section className="hh-tafel mt-5 rounded-2xl p-5 sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-x-8 gap-y-5">
        <div className="min-w-0 flex-1">
          <p className={KICKER}>
            {daten.election.short_title} · {datumLang(daten.election.date)} ·{" "}
            <span suppressHydrationWarning>
              {daten.dataset === "probe" ? "Generalprobe" : daten.dataset === "archive" ? "Rückblick" : zeit.kicker}
            </span>
          </p>
          <h1 className="mt-1 font-display text-[28px] font-bold leading-none tracking-tight sm:text-[32px]">Wahlabend</h1>
          <p className="mt-3 text-[14px] text-foreground">
            <strong className="font-semibold">{phase}</strong>
            {/* Bei einem Rückblick wäre „Stand 15:55 Uhr" die Uhrzeit, zu der
                die Datei gelesen wurde — nicht die des Wahlabends. */}
            {stand && daten.dataset !== "archive" ? <span className="text-muted-foreground"> · Stand {stand}</span> : null}
          </p>
          <div className="mt-2 h-1.5 w-full max-w-md overflow-hidden rounded-full bg-foreground/10">
            <div className="h-full rounded-full bg-primary transition-[width] duration-weg" style={{ width: `${anteil}%` }} />
          </div>
          <p className="mt-2 text-[11.5px] text-muted-foreground">
            {daten.dataset === "archive"
              ? "Eingefrorener Stand vom Ende des Wahlabends — er ändert sich nicht mehr."
              : abfrageFehler
              ? `Die letzte Abfrage ist fehlgeschlagen — gezeigt wird der Stand von ${uhrzeit(new Date(aktualisiert).toISOString()) ?? "–"} Uhr, nächster Versuch in einer Minute.`
              : daten.source.ok
                ? daten.phase === "complete"
                  ? "Alle Wahlbezirke sind ausgezählt — die Zahlen ändern sich nicht mehr."
                  : zeit.phase !== "vorher"
                    ? `Zuletzt abgefragt ${uhrzeit(new Date(aktualisiert).toISOString()) ?? "–"} Uhr · nächste Abfrage in einer Minute`
                    : `${zeit.wann} fragt die Seite jede Minute nach.`
                : `Der Votemanager antwortet gerade nicht (${daten.source.error ?? "Fehler"}) — gezeigt wird der letzte Stand.`}
            {daten.phase !== "before" && daten.dataset !== "archive" ? (
              <>
                {" · "}
                <a href={bild} target="_blank" rel="noopener noreferrer" className="font-medium text-primary">
                  Bild zum Teilen ↗
                </a>
              </>
            ) : null}
          </p>
        </div>
        <dl className="grid grid-cols-3 gap-x-6 gap-y-1 text-right">
          <div>
            <dt className={KICKER}>Wahlbeteiligung</dt>
            <dd className="font-display text-[24px] font-bold tabular-nums">{prozent(beteiligung)}</dd>
          </div>
          <div>
            <dt className={KICKER}>Gültige Stimmen</dt>
            <dd className="font-display text-[24px] font-bold tabular-nums">{zahl(gueltig === null ? null : Math.round(gueltig))}</dd>
          </div>
          <div>
            <dt className={KICKER}>Sitze</dt>
            <dd className="font-display text-[24px] font-bold tabular-nums">{daten.election.seats}</dd>
          </div>
        </dl>
      </div>
      {daten.notes.length ? (
        <ul className="mt-4 space-y-1 border-t border-border pt-3 text-[12.5px] text-foreground">
          {daten.notes.map((n) => (
            <li key={n}>{n}</li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}

/** Der Hinweis mit festem Platz (Designsprache: nicht wegklickbar, nicht
 *  aufdringlich): Was zählt, ist die amtliche Präsentation der Stadt — und
 *  unsere Rechnung kann Fehler haben. */
function Vorbehalt({ daten }: { daten: Wahlabend }) {
  return (
    <p className="mt-3 rounded-xl border border-dashed border-border px-4 py-2.5 text-[12.5px] leading-relaxed text-muted-foreground">
      <strong className="font-semibold text-foreground">Maßgeblich ist die amtliche Ergebnispräsentation der Stadt.</strong> Die
      Zahlen hier stammen aus deren Open-Data-Dateien; Sitze, Abstände und Hochrechnung rechnen wir selbst nach dem
      Kommunalwahlgesetz. Diese Rechnung kann Fehler haben — dann sind auch unsere Zahlen falsch. Im Zweifel gilt, was die
      Stadt zeigt:{" "}
      <a href={daten.election.presentation_url} target="_blank" rel="noopener noreferrer" className="font-medium text-primary">
        zur amtlichen Ergebnispräsentation ↗
      </a>
    </p>
  );
}

/* ── Listen stadtweit ───────────────────────────────────────────────────── */

function ListenZeile({
  p,
  max,
  zaehlt,
  phase,
  aktiv,
  waehle,
  vorwahl,
}: {
  p: WahlabendPartei;
  max: number;
  zaehlt: boolean;
  phase: string;
  aktiv: boolean;
  waehle: (slug: string) => void;
  vorwahl: string;
}) {
  const anteil = useTween(p.share_pct);
  return (
    <li>
      <button
        type="button"
        onClick={() => waehle(p.slug)}
        aria-pressed={aktiv}
        className={cn(
          "grid w-full grid-cols-[minmax(0,7.5rem)_1fr_auto] items-center gap-x-3 rounded-lg px-2 py-1.5 text-left transition-colors duration-tipp hover:bg-primary/5 sm:grid-cols-[minmax(0,9rem)_1fr_auto_auto]",
          aktiv && "bg-primary/5",
        )}
      >
        <span className="flex min-w-0 items-center gap-2">
          <Punkt color={p.color} dark={p.color_dark} />
          <span className="truncate text-[13px] font-semibold">{p.short}</span>
        </span>
        <span className="flex items-center gap-2">
          <span className="h-2 flex-1 overflow-hidden rounded-full bg-foreground/10">
            <span
              className={cn("block h-full rounded-full transition-[width] duration-weg", aktiv ? "bg-primary" : "bg-foreground/40")}
              style={{ width: `${zaehlt ? (100 * (anteil ?? 0)) / max : 0}%` }}
            />
          </span>
          <span className="w-[4.2rem] text-right text-[13px] tabular-nums">{prozent(anteil)}</span>
        </span>
        <span className="hidden w-12 text-right font-mono text-[10.5px] text-signal sm:inline tabular-nums">
          {delta(p.share_pct, p.share_previous_pct) ?? ""}
        </span>
        <span className="text-right text-[12.5px] tabular-nums text-muted-foreground">
          {zaehlt ? (
            <>
              <strong className="font-semibold text-foreground">{p.seats ?? "–"}</strong>
              {phase === "counting" ? <> → {p.projected_seats ?? "–"}</> : null}
            </>
          ) : (
            "–"
          )}
          {vorwahl ? <span className="hidden sm:inline"> · {vorwahl}: {p.seats_previous ?? 0}</span> : null}
        </span>
      </button>
    </li>
  );
}

function ListenTafel({ daten, liste, waehle }: { daten: Wahlabend; liste: string | null; waehle: (slug: string) => void }) {
  const vorwahl = daten.election.previous_label;
  const sortiert = nachStimmen(daten.parties);
  const max = Math.max(1, ...daten.parties.map((p) => p.share_pct ?? 0));
  const zaehlt = daten.phase !== "before";
  return (
    <section className="mt-6">
      <div className="flex items-baseline justify-between gap-3">
        <h2 className="font-display text-[16px] font-bold tracking-tight">Alle Listen stadtweit</h2>
        <span className={cn(KICKER, "hidden sm:inline")}>Anteil · Sitze Stand → Hochrechnung{vorwahl ? ` · ${vorwahl}` : ""}</span>
      </div>
      <ol className="mt-3 rounded-2xl border border-border bg-card p-2 shadow-[0_1px_2px_rgba(0,0,0,0.04)]">
        {sortiert.map((p) => (
          <ListenZeile key={p.slug} p={p} max={max} zaehlt={zaehlt} phase={daten.phase} aktiv={liste === p.slug} waehle={waehle} vorwahl={vorwahl} />
        ))}
      </ol>
      <p className="mt-2 text-[11.5px] text-muted-foreground">
        Antippen wählt die Liste für die Wahlbereiche unten.
        {vorwahl ? ` Der Abstand in Punkten vergleicht mit dem Ergebnis von ${vorwahl}.` : ""}
      </p>
    </section>
  );
}

function Sitzbild({ daten }: { daten: Wahlabend }) {
  if (daten.phase === "before") return null;
  const zwei = daten.phase === "counting";
  return (
    <section className={cn("mt-6 grid gap-4", zwei && "@3xl:grid-cols-2")}>
      <Halbkreis parteien={daten.parties} gesamt={daten.election.seats} feld="seats" titel="Stand" />
      {zwei ? <Halbkreis parteien={daten.parties} gesamt={daten.election.seats} feld="projected_seats" titel="Hochrechnung" /> : null}
    </section>
  );
}

/** Gewinne und Verluste gegenüber der Vorwahl in Prozentpunkten — Deltas
 *  tragen Signal-Orange (Designsprache), Flächen bleiben neutral.
 *
 *  Wie die Vorwahl heißt, steht in der Antwort (`election.previous_label`);
 *  bis 09/2026 stand „2021" hier als Literal. */
function GewinneVerluste({ daten }: { daten: Wahlabend }) {
  const vorwahl = daten.election.previous_label;
  if (daten.phase === "before" || !vorwahl) return null;
  const zeilen = daten.parties
    .filter((p) => p.share_pct !== null && p.share_previous_pct !== null)
    .map((p) => ({ p, d: (p.share_pct ?? 0) - (p.share_previous_pct ?? 0) }))
    .sort((a, b) => b.d - a.d);
  if (!zeilen.length) return null;
  const max = Math.max(0.5, ...zeilen.map((z) => Math.abs(z.d)));
  return (
    <section className="rounded-2xl border border-border bg-card p-4 shadow-[0_1px_2px_rgba(0,0,0,0.04)]">
      <div className="flex items-baseline justify-between gap-3">
        <h2 className="font-display text-[16px] font-bold tracking-tight">Gewinne und Verluste</h2>
        <span className={KICKER}>Punkte gegenüber {vorwahl}</span>
      </div>
      <ol className="mt-3 space-y-1.5">
        {zeilen.map(({ p, d }) => (
          <li key={p.slug} className="grid grid-cols-[minmax(0,5.5rem)_1fr_3.2rem] items-center gap-2 text-[12.5px]">
            <span className="flex min-w-0 items-center gap-1.5">
              <Punkt color={p.color} dark={p.color_dark} />
              <span className="truncate font-medium">{p.short}</span>
            </span>
            <span className="relative h-2.5">
              <span className="absolute inset-y-0 left-1/2 w-px bg-border" />
              <span
                className="gb-balken-auf absolute inset-y-0 rounded-sm bg-signal/80"
                style={
                  d >= 0
                    ? { left: "50%", width: `${(50 * d) / max}%` }
                    : { right: "50%", width: `${(50 * -d) / max}%` }
                }
              />
            </span>
            <span className="text-right font-mono text-[11px] tabular-nums text-signal">{delta(p.share_pct, p.share_previous_pct)}</span>
          </li>
        ))}
      </ol>
      <p className="mt-2 text-[11px] text-muted-foreground">Listen ohne Antritt {vorwahl} fehlen hier; sie stehen oben mit „–".</p>
    </section>
  );
}

function MehrheitenBlock({ daten }: { daten: Wahlabend }) {
  const [feld, setFeld] = useState<"seats" | "projected_seats">("projected_seats");
  if (daten.phase === "before") return null;
  const zaehlt = daten.phase === "counting";
  const aktiv = zaehlt ? feld : "seats";
  return (
    <section className="mt-6 grid items-start gap-4 @3xl:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)] @container">
      <div>
        {zaehlt ? (
          <div className="mb-2 inline-flex rounded-full border border-border bg-card p-0.5 text-[12px]">
            {(["projected_seats", "seats"] as const).map((f) => (
              <button
                key={f}
                type="button"
                aria-pressed={aktiv === f}
                onClick={() => setFeld(f)}
                className={cn("rounded-full px-3 py-1 transition-colors duration-tipp", aktiv === f ? "bg-primary text-primary-foreground" : "text-muted-foreground")}
              >
                {f === "seats" ? "Stand" : "Hochrechnung"}
              </button>
            ))}
          </div>
        ) : null}
        <Mehrheiten parteien={daten.parties} gesamt={daten.election.seats} feld={aktiv} hochrechnung={aktiv === "projected_seats"} />
      </div>
      <GewinneVerluste daten={daten} />
    </section>
  );
}

/* ── Liste wählen ───────────────────────────────────────────────────────── */

function ListenWahl({ parteien, liste, waehle }: { parteien: readonly WahlabendPartei[]; liste: string | null; waehle: (slug: string) => void }) {
  return (
    <section className="mt-8">
      <h2 className="font-display text-[16px] font-bold tracking-tight">Eine Liste, sechs Wahlbereiche</h2>
      <p className="mt-1 text-[13px] text-muted-foreground">
        Wähle eine Liste — dann siehst du je Wahlbereich ihre Kandidat*innen, die Personenstimmen und wer nach dem
        Zuteilungsverfahren gerade drin wäre.
      </p>
      <div className="mt-3 flex flex-wrap gap-1.5">
        {parteien.map((p) => (
          <button
            key={p.slug}
            type="button"
            onClick={() => waehle(p.slug)}
            aria-pressed={liste === p.slug}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-[12.5px] font-medium transition-colors duration-tipp",
              liste === p.slug ? "border-primary/30 bg-primary/5 text-primary" : "border-border bg-card text-foreground hover:bg-primary/5",
            )}
          >
            <Punkt color={p.color} dark={p.color_dark} />
            {p.short}
          </button>
        ))}
      </div>
    </section>
  );
}

/* ── Wahlbereiche ───────────────────────────────────────────────────────── */

/** Eine Kandidatur im Rennen: Name, Status, Stimmen — und der Balken, der
 *  sie zur stärksten Person der Liste ins Verhältnis setzt. Die Marke ist
 *  die Sitzgrenze (schwächster Personensitz), wo es eine gibt. */
function KandidatZeile({
  k,
  max,
  grenze,
  rang,
  status,
  hochrechnung,
  bild,
}: {
  k: WahlabendKandidat;
  max: number;
  grenze: number | null;
  rang: number;
  status: { ton: StatusTon; text: string };
  hochrechnung: boolean;
  bild: { liste: string; bereich: number; probe: string | null; counted: string | null; vorwahl: string } | null;
}) {
  const stimmen = useTween(k.votes);
  const breite = stimmen === null || max <= 0 ? 0 : Math.max(1.5, (100 * stimmen) / max);
  const drin = k.elected !== null;
  return (
    <li className="flex items-start gap-2.5 py-2">
      <span className="w-5 flex-none pt-0.5 font-mono text-[10.5px] text-muted-foreground tabular-nums">{k.position}</span>
      <span className="min-w-0 flex-1">
        <span className={cn("block truncate text-[13px]", drin ? "font-semibold" : "font-medium")}>{k.name}</span>
        <span className="block truncate text-[11.5px] text-muted-foreground">
          {[k.occupation, k.born ? `*${k.born}` : null].filter(Boolean).join(" · ")}
        </span>
        {k.votes !== null ? (
          <span aria-hidden className="relative mt-1.5 block h-1.5 w-full overflow-hidden rounded-full bg-foreground/10">
            <span
              className={cn("gb-balken-auf block h-full rounded-full transition-[width] duration-weg", drin ? "bg-primary" : "bg-foreground/35")}
              style={{ width: `${breite}%`, animationDelay: `${rang * 40}ms` }}
            />
            {grenze !== null && max > 0 ? (
              <span className="absolute inset-y-0 w-0.5 -translate-x-1/2 bg-signal" style={{ left: `${Math.min(100, (100 * grenze) / max)}%` }} />
            ) : null}
          </span>
        ) : null}
        <span className={cn("mt-1 inline-block rounded-full px-2 py-0.5 text-[10.5px] font-semibold", TON[status.ton])}>{status.text}</span>
        {bild ? (
          <span className="mt-1 block text-[10.5px] text-muted-foreground">
            <KartenLinks liste={bild.liste} bereich={bild.bereich} platz={k.position} probe={bild.probe} counted={bild.counted} name={k.name} vorwahl={bild.vorwahl} />
          </span>
        ) : null}
      </span>
      <span className="flex-none text-right">
        <span className="block text-[13px] font-semibold tabular-nums">{zahl(stimmen === null ? null : Math.round(stimmen))}</span>
        {hochrechnung && k.projected_votes !== null ? (
          <span className="block text-[10.5px] text-muted-foreground tabular-nums" title="Hochrechnung: Personenstimmen am Ende der Auszählung">Hochr. → {zahl(k.projected_votes)}</span>
        ) : null}
      </span>
    </li>
  );
}

function BereichKarte({
  bereich,
  slug,
  daten,
  probe,
  counted,
  rang,
  zugriff,
}: {
  bereich: WahlabendBereich;
  slug: string;
  daten: Wahlabend;
  probe: string | null;
  counted: string | null;
  /** Platz dieses Wahlbereichs in der Rangfolge der gewählten Liste. */
  rang: number | null;
  /** „letzter Sitz" bzw. „nächster Sitz" — oder nichts. */
  zugriff: string | null;
}) {
  const eintrag = bereich.parties.find((p) => p.slug === slug);
  const zaehlt = daten.phase !== "before" && bereich.districts_counted > 0;
  const frisch = useFrisch(bereich.districts_counted);
  const anteil = useTween(eintrag?.share_pct);
  const stimmen = useTween(eintrag?.votes);
  const max = Math.max(0, ...(eintrag?.candidates ?? []).map((k) => k.votes ?? 0));
  const grenze = eintrag ? sitzgrenze(eintrag.candidates) : null;
  // Balken und Sitzgrenze rechnen weiter über ALLE Kandidaturen — sonst
  // änderte das Aufklappen den Maßstab.
  const { vorne, rest } = vorneDrei(eintrag?.candidates ?? [], daten.phase);
  const teilbar = zaehlt && !!eintrag;
  return (
    <article
      id={bereichAnker(bereich.number)}
      // Der Anker ist kein Schmuck: Die Rangfolge darüber springt hierher,
      // und `scroll-mt` hält den klebenden Seitenkopf aus dem Weg.
      className={cn(
        "flex scroll-mt-24 flex-col rounded-2xl border border-border bg-card p-4 shadow-[0_1px_2px_rgba(0,0,0,0.04)] transition-shadow duration-buehne",
        frisch && "shadow-lifted ring-2 ring-primary/40",
      )}
    >
      <div className="flex items-baseline justify-between gap-3">
        <div>
          <p className={KICKER}>
            Wahlbereich {bereich.roman}
            {rang ? <span className="text-primary"> · Platz {rang}</span> : null}
          </p>
          <h3 className="font-display text-[15px] font-bold tracking-tight">{bereich.name}</h3>
        </div>
        <span className="font-mono text-[10.5px] text-muted-foreground tabular-nums">
          {bereich.districts_counted}/{bereich.districts_total} Bezirke
        </span>
      </div>
      {eintrag ? (
        <>
          {/* Die Stimmen zuerst und groß, der Anteil klein daneben (Tims
              Befund 14.09.2026): Die Sitze folgen den Stimmen, der Anteil
              beantwortet eine andere Frage. */}
          <dl className="mt-3 flex items-end gap-5">
            <div>
              <dt className={KICKER}>Stimmen</dt>
              <dd className="font-display text-[22px] font-bold leading-none tabular-nums">{zaehlt ? zahl(stimmen === null ? null : Math.round(stimmen)) : "–"}</dd>
              <dd className="mt-1 text-[11.5px] text-muted-foreground tabular-nums">{zaehlt ? prozent(anteil) : ""}</dd>
            </div>
            <div>
              <dt className={KICKER}>Sitze{daten.phase === "counting" ? " · Hochr." : ""}</dt>
              <dd className="font-display text-[22px] font-bold leading-none tabular-nums">
                {daten.phase === "before" ? "–" : (eintrag.seats ?? "–")}
                {daten.phase === "counting" ? <span className="text-muted-foreground"> → {eintrag.projected_seats ?? "–"}</span> : null}
              </dd>
              {zugriff ? <dd className="mt-1 whitespace-nowrap font-mono text-[10px] font-medium uppercase tracking-[0.08em] text-signal">{zugriff}</dd> : null}
            </div>
          </dl>
          {/* Höchstens drei Kandidaturen je Karte (Tims Befund 14.09.2026):
              SPD und Linke stellen in einem Wahlbereich bis zu zwölf, und
              sechs Karten untereinander waren auf dem Telefon rund siebzig
              Zeilen. Welche drei, entscheidet `vorneDrei` — Gewählte immer
              dabei, gezeigt in Listenplatz-Reihenfolge. */}
          <ol className="mt-4 divide-y divide-border/70 border-t border-border/70">
            {vorne.map((k, i) => (
              <KandidatZeile key={k.position} k={k} max={max} grenze={grenze} rang={i}
                status={kandidatenStatus(k, daten.phase, daten.person_votes_available, bereich.districts_counted > 0)}
                hochrechnung={daten.phase === "counting"}
                bild={teilbar && k.votes !== null ? { liste: slug, bereich: bereich.number, probe, counted, vorwahl: daten.election.previous_label } : null}
              />
            ))}
          </ol>
          {rest.length ? (
            <details className="group border-b border-border/70">
              <summary className="cursor-pointer list-none py-2 text-[12.5px] font-medium text-primary marker:hidden">
                <ChevronDown aria-hidden className="mr-1 inline h-3.5 w-3.5 align-[-2px] transition-transform group-open:rotate-180" />
                {rest.length} weitere {rest.length === 1 ? "Kandidatur" : "Kandidaturen"}
                <span className="sr-only"> anzeigen</span>
              </summary>
              <ol className="divide-y divide-border/70 border-t border-border/70">
                {rest.map((k, i) => (
                  <KandidatZeile key={k.position} k={k} max={max} grenze={grenze} rang={i}
                    status={kandidatenStatus(k, daten.phase, daten.person_votes_available, bereich.districts_counted > 0)}
                    hochrechnung={daten.phase === "counting"}
                    bild={teilbar && k.votes !== null ? { liste: slug, bereich: bereich.number, probe, counted, vorwahl: daten.election.previous_label } : null}
                  />
                ))}
              </ol>
            </details>
          ) : null}
          {zaehlt ? (
            <p className="mt-2 text-[11px] text-muted-foreground">
              Liste {zahl(eintrag.list_votes)} · Personen {zahl(eintrag.candidate_votes)}
              {grenze !== null ? <> · Marke: Sitzgrenze bei {zahl(grenze)}</> : null}
            </p>
          ) : null}
          {teilbar ? (
            <p className="mt-1.5 text-[11px] text-muted-foreground">
              <KartenLinks liste={slug} bereich={bereich.number} platz={null} probe={probe} counted={counted} name={`Wahlbereich ${bereich.roman}`} vorwahl={daten.election.previous_label} />
            </p>
          ) : null}
        </>
      ) : (
        <p className="mt-3 text-[13px] text-muted-foreground">Diese Liste tritt im Wahlbereich {bereich.roman} nicht an.</p>
      )}
    </article>
  );
}

function Bereiche({ daten, liste, probe, counted, rueckblick }: { daten: Wahlabend; liste: string | null; probe: string | null; counted: string | null; rueckblick: string | null }) {
  if (!liste) return null;
  const partei = daten.parties.find((p) => p.slug === liste);
  if (!partei) return null;
  const karte = daten.phase !== "before";
  const rangZeilen = new Map(partei.areas.map((z) => [z.area, z]));
  const sortiert = [...daten.areas].sort(
    (a, b) => (rangZeilen.get(a.number)?.rank ?? 99) - (rangZeilen.get(b.number)?.rank ?? 99),
  );
  return (
    <section className="mt-5 @container">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h2 className="flex items-center gap-2 font-display text-[16px] font-bold tracking-tight">
          <Punkt color={partei.color} dark={partei.color_dark} />
          {partei.name}
        </h2>
        {daten.phase !== "before" ? (
          <p className="text-[12.5px] text-muted-foreground">
            stadtweit {prozent(partei.share_pct)} · {partei.seats ?? "–"} {partei.seats === 1 ? "Sitz" : "Sitze"}
            {partei.votes_to_next_seat !== null ? <> · {zahl(partei.votes_to_next_seat)} Stimmen bis zum nächsten Sitz</> : null}
            {partei.votes_to_lose_seat !== null ? <> · {zahl(partei.votes_to_lose_seat)} Stimmen Puffer auf dem letzten Sitz</> : null}
          </p>
        ) : null}
      </div>
      {karte ? (
        <p className="mt-1 text-[12.5px] text-muted-foreground">
          <KartenLinks liste={liste} bereich={null} platz={null} probe={probe} counted={counted} stadtweit name={partei.short} vorwahl={daten.election.previous_label} />
        </p>
      ) : null}
      {/* Erst die Karte in voller Breite, dann die Rangfolge: „wo ist das?"
          braucht Fläche, „wo ist die Liste stark?" braucht Zeilen. Als
          Zweispalter (bis 14.09.2026) war die Karte ein Drittel so groß, und
          die Wahlbezirke darin waren nicht zu treffen. */}
      <Wahlgebiete
        className="mt-4"
        daten={daten}
        partei={partei}
        probe={probe}
        counted={counted}
        rueckblick={rueckblick}
      />
      <Rangfolge className="mt-4" partei={partei} daten={daten} />
      {/* Die Karten folgen derselben Rangfolge — eine Liste, die in IV am
          stärksten ist, soll IV zuerst zeigen. Wahlbereiche, in denen sie
          nicht antritt, hängt der Server nicht an `areas` an; sie stehen
          hinten und behalten ihre Erklärung. */}
      <div className="mt-3 grid gap-4 @3xl:grid-cols-2 @6xl:grid-cols-3">
        {sortiert.map((b) => {
          const z = rangZeilen.get(b.number);
          return (
            <BereichKarte
              key={b.number}
              bereich={b}
              slug={liste}
              daten={daten}
              probe={probe}
              counted={counted}
              rang={z?.rank ?? null}
              zugriff={z?.took_last_seat ? "letzter Sitz" : z?.next_seat ? "nächster Sitz" : null}
            />
          );
        })}
      </div>
    </section>
  );
}

/* ── Alle Sitze ─────────────────────────────────────────────────────────── */

function Mandate({ daten }: { daten: Wahlabend }) {
  if (daten.phase === "before" || !daten.mandates.length) return null;
  const roman = new Map(daten.areas.map((a) => [a.number, a.roman]));
  const gruppen = daten.parties
    .map((p) => ({ p, sitze: daten.mandates.filter((m) => m.slug === p.slug) }))
    .filter((g) => g.sitze.length);
  return (
    <details className="mt-8 rounded-2xl border border-border bg-card p-4 shadow-[0_1px_2px_rgba(0,0,0,0.04)]">
      <summary className="cursor-pointer font-display text-[15px] font-bold tracking-tight">
        Alle {daten.mandates.length} Sitze nach aktuellem Stand
      </summary>
      <div className="mt-3 grid gap-4 @3xl:grid-cols-2">
        {gruppen.map(({ p, sitze }) => (
          <div key={p.slug}>
            <p className="flex items-center gap-2 text-[13px] font-semibold">
              <Punkt color={p.color} dark={p.color_dark} />
              {p.short} <span className="font-normal text-muted-foreground">· {sitze.length}</span>
            </p>
            <ul className="mt-1 space-y-0.5 text-[12.5px]">
              {sitze.map((m, i) => (
                <li key={i} className="flex justify-between gap-3">
                  <span className="truncate">{m.name ?? "Name folgt mit den Personenstimmen"}</span>
                  <span className="flex-none text-muted-foreground">
                    {roman.get(m.area)} · {m.kind === "direct" ? "direkt" : m.kind === "list" ? "Liste" : m.kind === "transfer" ? "Übergang" : "–"}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </details>
  );
}

/* ── Die Seite ──────────────────────────────────────────────────────────── */

/** Die drei Ansichten unter der Tafel. Warum Reiter: Als eine Rolle war die
 *  Seite am Wahlabend sehr lang — Sitzbild, Mehrheiten, Verlauf, dann sechs
 *  Wahlbereichs-Karten, dann alle Sitze; die Kandidaten-Rangliste hätte sie
 *  noch einmal um 383 Zeilen verlängert. Die Tafel (Auszählungsstand,
 *  Listen) steht ÜBER den Reitern: Sie ist die Antwort auf die erste Frage
 *  und gehört zu jeder Ansicht. Die Ansicht steht in der URL (`?ansicht=`),
 *  damit ein Link auf die Rangliste ein Link auf die Rangliste ist. */
type Ansicht = "ergebnis" | "bereiche" | "kandidaten";
const ANSICHTEN: Reiter<Ansicht>[] = [
  { id: "ergebnis", label: "Ergebnis" },
  { id: "bereiche", label: "Wahlbereiche" },
  { id: "kandidaten", label: "Kandidat*innen" },
];
function ansichtAus(wert: string | null, liste: string | null): Ansicht {
  if (wert === "bereiche" || wert === "kandidaten" || wert === "ergebnis") return wert;
  // Ein geteilter Link mit `?liste=` (Sharepic, Neu-Karten) zeigt auf die
  // Wahlbereiche dieser Liste — dort soll er auch landen.
  return liste ? "bereiche" : "ergebnis";
}
const SORTIERUNGEN: readonly KandidatenSortierung[] = ["votes", "party", "area", "name"];

export function WahlabendView() {
  const params = useSearchParams();
  const router = useRouter();
  const probe = params.get("probe");
  const counted = params.get("counted");
  // `?wahl=` zeigt eine gelaufene Wahl aus dem Repo — dieselbe Seite, nur mit
  // eingefrorenen Zahlen und ohne Minutentakt.
  const rueckblick = params.get("wahl");
  const schalterAn = useFeature("wahlabend");
  const config = useAppConfig();
  // Ohne Argument: der Termin aus `/api/app-config`. Hier ist die Antwort des
  // Wahlabends noch nicht da — und genau dieser Wert entscheidet, ob sie
  // überhaupt jede Minute geholt wird.
  const zeit = useWahlabendZeit();
  // Bis Sonntag 18 Uhr gibt es nichts nachzufragen — der Minutentakt beginnt
  // mit dem Wahlabend (Tims Wunsch: eine Woche Polling wäre Overkill).
  //
  // **Er endet aber nicht mit dem Wahltag.** Seit `wahlabendZeit` eine dritte
  // Phase kennt („danach"), wäre `phase === "laeuft"` als Bedingung eine
  // Falle: 2021 lag das vorläufige Ergebnis der Ratswahl erst am
  // Montagmorgen vor — die Seite hätte um Mitternacht aufgehört zu fragen und
  // einen Zwischenstand eingefroren. Gefragt wird deshalb, bis wirklich
  // ausgezählt ist.
  const gestartet = zeit.phase !== "vorher";
  const holen = gestartet && !rueckblick;

  const abfrage = useQuery({
    queryKey: ["wahlabend", probe, counted, rueckblick],
    queryFn: () => api.get<Wahlabend>(abfragePfad(probe, counted, rueckblick)),
    enabled: schalterAn,
    // Ein Rückblick ändert sich nicht mehr — kein Minutentakt, kein
    // Nachfragen beim Zurückschalten ins Fenster.
    refetchInterval: (abfrage) =>
      holen && abfrage.state.data?.phase !== "complete" ? 60_000 : false,
    refetchOnWindowFocus: holen,
    staleTime: rueckblick ? Infinity : gestartet ? 30_000 : 15 * 60_000,
  });

  const [liste, setListe] = useState<string | null>(null);
  useEffect(() => {
    const ausUrl = params.get("liste");
    if (ausUrl) {
      setListe(ausUrl);
      return;
    }
    try {
      setListe(window.localStorage.getItem(LISTE_SPEICHER));
    } catch {
      /* privates Fenster o. ä. — dann eben ohne Vorauswahl */
    }
  }, [params]);

  // Die Ansicht und die Filter der Rangliste leben in der URL — `replace`
  // ohne Scrollsprung, wie schon `?liste=`.
  const setzeQuery = useCallback(
    (aenderungen: Record<string, string | null>) => {
      const q = new URLSearchParams(params.toString());
      for (const [k, v] of Object.entries(aenderungen)) {
        if (v === null) q.delete(k);
        else q.set(k, v);
      }
      const s = q.toString();
      router.replace(s ? `?${s}` : "?", { scroll: false });
    },
    [params, router],
  );
  const ansicht = ansichtAus(params.get("ansicht"), params.get("liste"));
  const sortParam = params.get("sort");
  const bereichParam = params.get("bereich");
  const kandidatenFilter: KandidatenFilter = {
    sortierung: SORTIERUNGEN.find((s) => s === sortParam) ?? "votes",
    liste: params.get("kliste"),
    bereich: bereichParam && /^\d+$/.test(bereichParam) ? Number(bereichParam) : null,
  };
  const setKandidatenFilter = useCallback(
    (f: KandidatenFilter) =>
      setzeQuery({
        sort: f.sortierung === "votes" ? null : f.sortierung,
        kliste: f.liste,
        bereich: f.bereich === null ? null : String(f.bereich),
      }),
    [setzeQuery],
  );

  const waehle = useMemo(
    () => (slug: string) => {
      setListe(slug);
      try {
        window.localStorage.setItem(LISTE_SPEICHER, slug);
      } catch {
        /* s. o. */
      }
      // Eine Liste wählen heißt: ihre Wahlbereiche sehen wollen.
      setzeQuery({ liste: slug, ansicht: "bereiche" });
    },
    [setzeQuery],
  );

  const daten = abfrage.data;
  let inhalt: React.ReactNode;
  if (config.isLoading) {
    inhalt = null;
  } else if (config.isError && !daten) {
    inhalt = (
      <Hinweisbild
        pose="confused"
        titel="Gerade keine Verbindung"
        text="Ratslotse antwortet nicht. Die Seite versucht es gleich von selbst noch einmal — oder lade sie neu."
      />
    );
  } else if (!schalterAn && !daten) {
    inhalt = (
      <Hinweisbild
        pose="sleep"
        titel="Der Wahlabend ist noch nicht freigeschaltet"
        text={`${zeit.wann} zeigt diese Seite den Auszählungsstand — live, nachgerechnet, je Wahlbereich.`}
      />
    );
  } else if (abfrage.isError && !daten) {
    inhalt = (
      <Hinweisbild
        pose="confused"
        titel="Gerade keine Zahlen"
        text="Der Abruf ist fehlgeschlagen. Die Seite versucht es in einer Minute von selbst noch einmal."
      />
    );
  } else if (!daten) {
    inhalt = <p className="mt-10 text-center text-[13px] text-muted-foreground">Zahlen werden geladen …</p>;
  } else {
    inhalt = (
      <>
        {daten.dataset === "probe" ? (
          <p className="mt-5 rounded-xl border border-amber-200 bg-amber-50 px-4 py-2.5 text-[13px] text-amber-900 dark:border-amber-800 dark:bg-amber-900/30 dark:text-amber-100">
            <strong className="font-semibold">Generalprobe.</strong> Die Zahlen sind die der Ratswahl{" "}
            {daten.election.previous_label || "der Vorwahl"}, die Listen und Namen die von heute. Nichts davon ist
            ein Ergebnis dieser Wahl.
          </p>
        ) : null}
        <Tafel daten={daten} aktualisiert={abfrage.dataUpdatedAt} probe={probe} counted={counted} abfrageFehler={abfrage.isError} />
        {daten.dataset === "archive" ? null : <StichwahlHinweis />}
        {daten.phase !== "before" && daten.dataset !== "archive" ? <NeuKarten liste={liste} /> : null}
        <Vorbehalt daten={daten} />
        {daten.phase === "before" && daten.dataset === "live" ? (
          <p className="mt-4 text-[13.5px] leading-relaxed text-muted-foreground">
            Gewählt wird am {datumLang(daten.election.date)}, die Wahllokale schließen um 18 Uhr. Die ersten Wahlbezirke melden
            erfahrungsgemäß gegen 20 Uhr; 2021 lag das vorläufige Ergebnis der Ratswahl am Montagmorgen vor. Die Seite
            aktualisiert sich dann von selbst — bis dahin zeigt sie die Listen und Kandidat*innen ohne Zahlen.
          </p>
        ) : null}
        <ListenTafel daten={daten} liste={liste} waehle={waehle} />
        <ReiterLeiste
          reiter={ANSICHTEN}
          aktiv={ansicht}
          // IMMER ausdrücklich in die Adresse — auch „ergebnis". Bis 14.09.2026
          // wurde der Reiter dann weggelassen, und `ansichtAus` machte aus
          // einer Adresse mit `?liste=` wieder „bereiche": Sobald jemand eine
          // Liste angetippt hatte, war der Ergebnis-Reiter nicht mehr
          // erreichbar (Tims Befund: „der lädt gar nicht").
          onChange={(id) => setzeQuery({ ansicht: id })}
          label="Ansichten des Wahlabends"
          className="mt-8"
        />
        <ReiterTafel id="ergebnis" aktiv={ansicht}>
          <Sitzbild daten={daten} />
          <MehrheitenBlock daten={daten} />
          <Verlauf daten={daten} liste={liste} />
          <Mandate daten={daten} />
        </ReiterTafel>
        <ReiterTafel id="bereiche" aktiv={ansicht}>
          <ListenWahl parteien={daten.parties} liste={liste} waehle={waehle} />
          <Bereiche daten={daten} liste={liste} probe={probe} counted={counted} rueckblick={rueckblick} />
        </ReiterTafel>
        <ReiterTafel id="kandidaten" aktiv={ansicht}>
          <Kandidaten
            daten={daten}
            probe={probe}
            counted={counted}
            rueckblick={rueckblick}
            filter={kandidatenFilter}
            setFilter={setKandidatenFilter}
            live={holen}
          />
        </ReiterTafel>
      </>
    );
  }

  return (
    <>
      <Kopf label="Wahlabend 2026" />
      <main className="mx-auto w-full max-w-7xl px-4 pb-16 sm:px-6 lg:px-10 @container">
        {inhalt}
        <Fuss daten={daten} />
      </main>
    </>
  );
}
