"use client";

// Die Kandidaten-Rangliste — alle 383 Kandidaturen der Ratswahl als EINE
// Liste, nach Personenstimmen. Tims Frage am Abend nach der Wahl: „wie
// manche von der AfD so viele Direkt-Kandidatinnen-Stimmen bekommen
// konnten" — die Wahlbereichs-Karten kannten die Zahl, aber nur sechs
// Karten tief je Liste. Hier steht sie in einer Zeile, und daneben die
// zwei Anteile, die das „wie" beantworten (election/candidates.py).
//
// Sortiert und gefiltert wird auf dem SERVER: `sort`, `party`, `area` gehen
// als Query mit, die Seite rendert, was zurückkommt. Der Rang bleibt
// stadtweit, auch wenn nur eine Liste gezeigt wird.
//
// Bauform: ab `breit` eine echte <table> (ein Spaltenraster, Linien vor den
// Zahlenspalten, tabular-nums — die Zahlentabellen-Regel aus dem Haushalt),
// darunter Zeilenblöcke, die ihre Beschriftung selbst tragen. Der Balken je
// Zeile setzt die Stimmen ins Verhältnis zur stärksten Person der Wahl.

import { useQuery } from "@tanstack/react-query";
import { ChevronRight } from "lucide-react";
import { Fragment, useMemo, useState } from "react";
import { KICKER, Punkt, TON } from "@/components/wahlabend/bausteine";
import { BeobachtenHinweis, BeobachtetKarte, Stern, useBeobachtet } from "@/components/wahlabend/beobachtet";
import { KandidatBezirke } from "@/components/wahlabend/kandidat-bezirke";
import { Segmented } from "@/components/ui/segmented";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import {
  kandidatenPfad,
  kandidatenStatus,
  prozent,
  zahl,
  type Kandidatenliste,
  type KandidatenListe,
  type KandidatenSortierung,
  type KandidatenZeile,
  type Wahlabend,
} from "@/lib/wahlabend";

const SORTIERUNGEN: { value: KandidatenSortierung; label: string }[] = [
  { value: "votes", label: "Stimmen" },
  { value: "party", label: "Liste" },
  { value: "area", label: "Wahlbereich" },
  { value: "name", label: "Name" },
];

export type KandidatenFilter = {
  sortierung: KandidatenSortierung;
  liste: string | null;
  bereich: number | null;
  /** Ein WAHLBEZIRK — das Wahllokal, in dem ausgezählt wurde. Jede
   *  Kandidatur hat Stimmen in jedem Bezirk ihres Wahlbereichs, also 15 bis
   *  24 Zahlen; eine Spalte könnte davon keine zeigen. Deshalb hier ein
   *  Filter (gesetzt zeigt die Liste, wer in DIESEM Wahllokal vorn lag) — und
   *  je Zeile die Tafel mit allen Bezirken (`KandidatBezirke`). */
  bezirk: number | null;
};

function Chip({ an, onClick, children, title }: { an: boolean; onClick: () => void; children: React.ReactNode; title?: string }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={an}
      title={title}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-[12.5px] font-medium transition-colors duration-tipp",
        an ? "border-primary/30 bg-primary/5 text-primary" : "border-border bg-card text-foreground hover:bg-primary/5",
      )}
    >
      {children}
    </button>
  );
}

/** Wie personenbezogen die Wähler*innen jeder Liste stimmen — der Kontext
 *  zu jeder Zeile darunter. Sortiert nach Anteil, damit die Spanne (2026:
 *  SPD 50 % bis PGM 26 %) auf einen Blick dasteht. */
function Personenanteile({ listen, liste, waehle }: { listen: KandidatenListe[]; liste: string | null; waehle: (slug: string | null) => void }) {
  const mit = listen.filter((l) => l.personal_pct !== null).sort((a, b) => (b.personal_pct ?? 0) - (a.personal_pct ?? 0));
  if (!mit.length) return null;
  const max = Math.max(...mit.map((l) => l.personal_pct ?? 0));
  return (
    <section className="mt-5 rounded-2xl border border-border bg-card p-4 shadow-[0_1px_2px_rgba(0,0,0,0.04)]">
      <p className={KICKER}>Personen oder Liste?</p>
      <h3 className="mt-0.5 font-display text-[15px] font-bold tracking-tight">Wie viel jede Liste über ihre Namen holt</h3>
      <p className="mt-1 text-[12.5px] leading-relaxed text-muted-foreground">
        Jede Person hat drei Stimmen und gibt sie einer Liste oder einzelnen Kandidat*innen. Der Balken zeigt, welcher Anteil
        der Stimmen einer Liste stadtweit an Personen ging. Eine Liste antippen filtert die Rangliste.
      </p>
      <ul className="mt-3 grid gap-x-6 gap-y-1.5 @2xl:grid-cols-2 @5xl:grid-cols-3">
        {mit.map((l) => {
          const an = liste === l.slug;
          return (
            <li key={l.slug}>
              <button
                type="button"
                onClick={() => waehle(an ? null : l.slug)}
                aria-pressed={an}
                className={cn("flex w-full items-center gap-2.5 rounded-md px-1 py-0.5 text-left transition-colors hover:bg-primary/5", an && "bg-primary/5")}
              >
                <Punkt color={l.color} dark={l.color_dark} />
                <span className={cn("w-24 flex-none truncate text-[12.5px]", an ? "font-semibold text-primary" : "font-medium")}>{l.short}</span>
                <span aria-hidden className="relative h-1.5 min-w-0 flex-1 overflow-hidden rounded-full bg-foreground/10">
                  <span
                    className={cn("gb-balken-auf block h-full rounded-full", an ? "bg-primary" : "bg-foreground/35")}
                    style={{ width: `${max > 0 ? (100 * (l.personal_pct ?? 0)) / max : 0}%` }}
                  />
                </span>
                <span className="w-12 flex-none text-right text-[12.5px] font-semibold tabular-nums">{prozent(l.personal_pct, 0)}</span>
              </button>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

function Balken({ votes, max, drin }: { votes: number | null; max: number; drin: boolean }) {
  if (votes === null || max <= 0) return null;
  return (
    <span aria-hidden className="relative block h-1.5 w-full overflow-hidden rounded-full bg-foreground/10">
      <span className={cn("block h-full rounded-full", drin ? "bg-primary" : "bg-foreground/35")} style={{ width: `${Math.max(1.5, (100 * votes) / max)}%` }} />
    </span>
  );
}

/** Der Name ist der Griff. Er verspricht, was aufgeht: alle Wahlbezirke
 *  dieser einen Kandidatur — die Zahlen, die in der Liste nicht in eine
 *  Spalte passen.
 *
 *  Tims Befund 15.09.: Ein 10-px-Dreieck sagt niemandem, dass hier etwas
 *  aufgeht. Deshalb ein Pfeil in einem Kreis, der mit der ZEILE reagiert
 *  (`group/zeile` liegt auf `tr` bzw. `li`): Wer über die Zeile fährt, sieht
 *  den Kreis in Primärfarbe und die Zeile getönt — die ganze Zeile ist der
 *  Griff, nicht nur der Name. Offen: Pfeil nach unten, Kreis gefüllt. */
function Aufklapper({ auf, onClick, name, children }: { auf: boolean; onClick: () => void; name: string; children: React.ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-expanded={auf}
      title={auf ? "Wahlbezirke zuklappen" : `Alle Wahlbezirke von ${name} zeigen`}
      className="-mx-1 block w-full min-w-0 rounded-md px-1 py-0.5 text-left focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
    >
      <span className="flex min-w-0 items-start gap-2">
        <span
          aria-hidden
          className={cn(
            "mt-px flex h-[22px] w-[22px] flex-none items-center justify-center rounded-full border transition-[transform,color,border-color,background-color] duration-tipp",
            auf
              ? "rotate-90 border-primary bg-primary text-primary-foreground"
              : "border-border bg-card text-muted-foreground group-hover/zeile:border-primary group-hover/zeile:text-primary",
          )}
        >
          <ChevronRight className="h-4 w-4" strokeWidth={2.25} />
        </span>
        <span className="min-w-0 flex-1">{children}</span>
      </span>
    </button>
  );
}

/** Die ganze Zeile klappt auf — nicht nur der Name. Ein Klick, der auf einem
 *  eigenen Knopf landet (Stern, Aufklapper selbst), bleibt bei dem. */
function zeilenKlick(umschalten: () => void) {
  return (e: React.MouseEvent<HTMLElement>) => {
    if ((e.target as HTMLElement).closest("button, a")) return;
    umschalten();
  };
}

function Statuspille({ z, daten }: { z: KandidatenZeile; daten: Kandidatenliste }) {
  const s = kandidatenStatus(z, daten.phase, daten.person_votes_available);
  return <span className={cn("inline-block whitespace-nowrap rounded-full px-2 py-0.5 text-[10.5px] font-semibold", TON[s.ton])}>{s.text}</span>;
}

/** „In welchem Wahllokal?" — die Ebene unter dem Wahlbereich.
 *
 *  Die Liste der Bezirke kommt mit der Antwort mit (`districts`), nicht aus
 *  einer zweiten Abfrage. Ohne gewählten Wahlbereich stehen alle 133 da, nach
 *  Wahlbereich gruppiert; mit Wahlbereich nur dessen eigene.
 */
function Bezirkswahl({ daten, liste, filter, setFilter }: {
  daten: Wahlabend;
  liste: Kandidatenliste | undefined;
  filter: KandidatenFilter;
  setFilter: (f: KandidatenFilter) => void;
}) {
  const alle = liste?.districts ?? [];
  if (!alle.length) return null;
  const gewaehlt = filter.bezirk;
  // Nach dem gewählten Wahlbereich einschränken — sonst nach allen gruppieren.
  const sichtbar = filter.bereich === null ? alle : alle.filter((b) => b.area === filter.bereich);
  const nachBereich = daten.areas
    .map((a) => ({ a, bezirke: sichtbar.filter((b) => b.area === a.number) }))
    .filter((g) => g.bezirke.length);
  return (
    <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1.5">
      <label htmlFor="kandidaten-bezirk" className={KICKER}>Wahlbezirk</label>
      <select
        id="kandidaten-bezirk"
        value={gewaehlt === null ? "" : String(gewaehlt)}
        onChange={(e) => {
          const wert = e.target.value ? Number(e.target.value) : null;
          const b = wert === null ? null : alle.find((x) => x.number === wert) ?? null;
          setFilter({ ...filter, bezirk: wert, bereich: b ? b.area : filter.bereich });
        }}
        className="min-h-9 max-w-full rounded-full border border-border bg-card px-3 text-[13px] font-medium text-foreground hover:bg-primary/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <option value="">Alle Wahlbezirke</option>
        {nachBereich.map(({ a, bezirke }) => (
          <optgroup key={a.number} label={`Wahlbereich ${a.roman} · ${a.name}`}>
            {bezirke.map((b) => (
              <option key={b.number} value={b.number}>
                {b.name}
                {b.postal ? " (Briefwahl)" : ""}
              </option>
            ))}
          </optgroup>
        ))}
      </select>
      {gewaehlt !== null ? (
        <button
          type="button"
          onClick={() => setFilter({ ...filter, bezirk: null })}
          className="text-[12.5px] font-medium text-primary underline-offset-2 hover:underline"
        >
          zurücksetzen
        </button>
      ) : null}
    </div>
  );
}

/** Der Tabellenkopf klebt unter dem Seitenkopf (kopf.tsx: 30-px-Marke +
 *  pt-3/pb-3 + Linie, im Browser gemessen 61 px plus Sicherheitszone). */
const KLEBE_AB = "top-[calc(env(safe-area-inset-top)+61px)]";

const SPALTE_ZAHL = "border-l border-border/70 px-3 py-2 text-right tabular-nums";

export function Kandidaten({
  daten,
  probe,
  counted,
  rueckblick,
  filter,
  setFilter,
  live,
}: {
  daten: Wahlabend;
  probe: string | null;
  counted: string | null;
  rueckblick: string | null;
  filter: KandidatenFilter;
  setFilter: (f: KandidatenFilter) => void;
  live: boolean;
}) {
  const beobachtet = useBeobachtet(rueckblick, probe, counted);
  const pfad = kandidatenPfad(probe, counted, rueckblick, filter.sortierung, filter.liste, filter.bereich, filter.bezirk);
  const abfrage = useQuery({
    queryKey: ["wahlabend-kandidaten", pfad],
    queryFn: () => api.get<Kandidatenliste>(pfad),
    // Im Minutentakt wie die Tafel, solange ausgezählt wird; ein Rückblick
    // ändert sich nicht mehr.
    refetchInterval: (q) => (live && q.state.data?.phase !== "complete" ? 60_000 : false),
    staleTime: rueckblick ? Infinity : 30_000,
    placeholderData: (alt) => alt,
  });
  const liste = abfrage.data;
  const max = useMemo(() => {
    // Bezugsgröße ist die stärkste Person der WAHL, nicht der Auswahl — sonst
    // sähe die schwächste Liste gefiltert aus wie die stärkste.
    //
    // **Im Wahlbezirk gilt der Bezirk.** Dort geht es um 20 bis 300 Stimmen;
    // gegen die 4.019 der Stadt gemessen wäre jeder Balken ein Strich.
    if (liste?.district) return Math.max(0, ...liste.rows.map((z) => z.votes ?? 0));
    const alle = daten.areas.flatMap((a) => a.parties.flatMap((p) => p.candidates.map((k) => k.votes ?? 0)));
    return Math.max(0, ...alle);
  }, [daten, liste]);
  // Aufgeklappt ist höchstens eine Zeile: Die Tafel ist selbst eine Liste,
  // zwei davon übereinander liest niemand mehr als eine Tabelle.
  const [offen, setOffen] = useState<string | null>(null);
  const listeInfo = filter.liste ? daten.parties.find((p) => p.slug === filter.liste) : null;
  const vorher = daten.phase === "before";

  return (
    <section className="mt-5 @container">
      <h2 className="font-display text-[16px] font-bold tracking-tight">Alle Kandidat*innen nach Personenstimmen</h2>
      <p className="mt-1 text-[13px] text-muted-foreground">
        {vorher
          ? "Die Personenstimmen kommen mit der Auszählung — bis dahin stehen hier die Namen in Stimmzettel-Reihenfolge."
          : liste?.district
            // Im Wahlbezirk zählen dessen Zahlen — ein stadtweiter Rang
            // neben Bezirks-Stimmen wäre eine Zahl aus einer anderen Rechnung.
            ? `Stimmen, Anteil und Rang gelten für dieses Wahllokal. Gezeigt werden die Kandidaturen des Wahlbereichs, zu dem es gehört — nur sie standen dort auf dem Stimmzettel.`
            : "Der Rang ist stadtweit und bleibt es auch gefiltert. Der Anteil sagt, wie viel von allen Stimmen der eigenen Liste im Wahlbereich auf diese Person entfielen."}
      </p>

      {beobachtet.angemeldet ? (
        <BeobachtetKarte
          className="mt-4"
          eintraege={beobachtet.eintraege}
          daten={daten}
          entfernen={(e) => e.row && beobachtet.umschalten(e.row)}
        />
      ) : (
        <BeobachtenHinweis className="mt-2" />
      )}

      {!vorher ? <Personenanteile listen={liste?.parties ?? []} liste={filter.liste} waehle={(slug) => setFilter({ ...filter, liste: slug })} /> : null}

      {/* Sortierung und Filter gehören zusammen — direkt über das, was sie ordnen. */}
      <div className="mt-6 flex flex-wrap items-center gap-x-3 gap-y-2">
        <span className={KICKER}>Sortieren</span>
        <Segmented
          value={filter.sortierung}
          onChange={(v) => setFilter({ ...filter, sortierung: v })}
          options={SORTIERUNGEN}
          className="w-full sm:w-auto"
        />
      </div>
      <div className="mt-3 flex flex-wrap gap-1.5">
        <Chip an={filter.liste === null} onClick={() => setFilter({ ...filter, liste: null })}>Alle Listen</Chip>
        {daten.parties.map((p) => (
          <Chip key={p.slug} an={filter.liste === p.slug} onClick={() => setFilter({ ...filter, liste: filter.liste === p.slug ? null : p.slug })} title={p.name}>
            <Punkt color={p.color} dark={p.color_dark} />
            {p.short}
          </Chip>
        ))}
      </div>
      <div className="mt-2 flex flex-wrap gap-1.5">
        <Chip an={filter.bereich === null && filter.bezirk === null} onClick={() => setFilter({ ...filter, bereich: null, bezirk: null })}>Alle Wahlbereiche</Chip>
        {daten.areas.map((a) => (
          <Chip
            key={a.number}
            an={filter.bereich === a.number && filter.bezirk === null}
            // Ein Wahlbereich hebt den Bezirk auf: Der Bezirk IST einer
            // seiner Teile, beides zugleich wäre ein Widerspruch.
            onClick={() => setFilter({ ...filter, bereich: filter.bereich === a.number && filter.bezirk === null ? null : a.number, bezirk: null })}
            title={a.name}
          >
            {a.roman}
            <span className="hidden text-muted-foreground sm:inline">· {a.name}</span>
          </Chip>
        ))}
      </div>

      {/* Der Wahlbezirk als Auswahlfeld, nicht als Chip-Reihe: 133 Chips
          wären keine Filterleiste mehr. Ein `select` bringt auf dem Handy
          die native Rolltrommel mit und ordnet die Bezirke nach
          Wahlbereich. */}
      <Bezirkswahl daten={daten} liste={liste} filter={filter} setFilter={setFilter} />

      {abfrage.isError && !liste ? (
        <p className="mt-6 text-[13px] text-muted-foreground">Die Rangliste ließ sich gerade nicht laden — die Seite versucht es von selbst noch einmal.</p>
      ) : !liste ? (
        <p className="mt-6 text-center text-[13px] text-muted-foreground">Rangliste wird geladen …</p>
      ) : (
        <>
          <p className="mt-4 text-[12.5px] text-muted-foreground" aria-live="polite">
            {liste.shown === liste.total ? `${zahl(liste.total)} Kandidaturen` : `${zahl(liste.shown)} von ${zahl(liste.total)} Kandidaturen`}
            {listeInfo ? <> · {listeInfo.name}</> : null}
            {filter.bereich !== null ? <> · Wahlbereich {daten.areas.find((a) => a.number === filter.bereich)?.roman}</> : null}
            {liste.district !== null ? <> · <strong className="font-semibold text-foreground">{liste.district_name}</strong></> : null}
            {abfrage.isFetching && abfrage.isPlaceholderData ? <> · wird aktualisiert …</> : null}
          </p>

          {/* Ab `breit`: die Tabelle. */}
          <div className={cn("mt-2 hidden breit:block", abfrage.isPlaceholderData && "opacity-60 transition-opacity")}>
            <table className="w-full border-separate border-spacing-0 text-[13px]">
              <thead>
                <tr className={cn("sticky z-10 bg-background", KLEBE_AB)}>
                  <th scope="col" className="w-12 border-b border-border px-2 py-2 text-right font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">Rang</th>
                  <th scope="col" className="border-b border-border px-3 py-2 text-left font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">Kandidatur</th>
                  <th scope="col" className="w-28 border-b border-border px-3 py-2 text-left font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">Liste</th>
                  <th scope="col" className="w-44 border-b border-border px-3 py-2 text-left font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground" title={liste.district === null
                    ? "Wahlbereich der Kandidatur — darunter ihr stärkster Wahlbezirk"
                    : "Stimmen im ganzen Wahlbereich — und welcher Anteil davon aus diesem Wahllokal kam"}>{liste.district === null ? "Wahlbereich · stärkster Bezirk" : "Im ganzen Wahlbereich"}</th>
                  <th scope="col" className="w-48 border-b border-border border-l border-l-border/70 px-3 py-2 text-right font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">Personenstimmen</th>
                  <th scope="col" className="w-24 border-b border-border border-l border-l-border/70 px-3 py-2 text-right font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground" title={liste.district === null
                    ? "Anteil an allen Stimmen der eigenen Liste im Wahlbereich"
                    : "Anteil an allen Stimmen der eigenen Liste in diesem Wahlbezirk"}>Anteil</th>
                  <th scope="col" className="w-48 border-b border-border px-3 py-2 text-left font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">Stand</th>
                </tr>
              </thead>
              <tbody>
                {liste.rows.map((z) => {
                  const drin = z.elected !== null;
                  const id = `${z.party}-${z.area}-${z.position}`;
                  const auf = offen === id;
                  return (
                    <Fragment key={id}>
                    <tr
                      className={cn("group/zeile cursor-pointer transition-colors duration-tipp hover:bg-primary/5", auf && "bg-primary/[0.04]")}
                      onClick={zeilenKlick(() => setOffen(auf ? null : id))}
                    >
                      <td className="border-b border-border/60 px-2 py-2 text-right font-mono text-[11px] text-muted-foreground tabular-nums">{z.rank ?? "–"}</td>
                      <td className={cn("border-b px-3 py-2", auf ? "border-transparent" : "border-border/60")}>
                        <Aufklapper auf={auf} onClick={() => setOffen(auf ? null : id)} name={z.name}>
                          <span className={cn("block truncate", drin ? "font-semibold" : "font-medium")}>{z.name}</span>
                          <span className="block truncate text-[11.5px] text-muted-foreground">
                            {[z.occupation, z.born ? `*${z.born}` : null].filter(Boolean).join(" · ")}
                          </span>
                        </Aufklapper>
                      </td>
                      <td className="border-b border-border/60 px-3 py-2">
                        <span className="flex items-center gap-1.5"><Punkt color={z.color} dark={z.color_dark} />{z.party_short}</span>
                        <span className="block text-[11px] text-muted-foreground">Platz {z.position}</span>
                      </td>
                      {/* Stadtweit hat eine Kandidatur 15 bis 24 Wahlbezirke
                          — hier steht ihr Wahlbereich und darunter die
                          Hochburg, die eine davon, die etwas aussagt. Im
                          Bezirks-Filter ist es genau einer, und dann steht
                          er selbst da. */}
                      <td className="border-b border-border/60 px-3 py-2">
                        {liste.district === null ? (
                          <>
                            <span className="block">{z.area_roman}</span>
                            <span className="block truncate text-[11px] text-muted-foreground">{z.area_name}</span>
                            {z.top_district !== null ? (
                              <span className="mt-0.5 block truncate text-[11px] text-muted-foreground" title={`Stärkster Wahlbezirk: ${z.top_district_name} mit ${zahl(z.top_district_votes)} Personenstimmen`}>
                                ↗ {z.top_district_name} · {zahl(z.top_district_votes)}
                              </span>
                            ) : null}
                          </>
                        ) : (
                          // Der Bezirk steht schon in der Überschrift — 61-mal
                          // derselbe Name wäre keine Spalte, sondern ein Muster.
                          // Hier steht, was je Zeile verschieden ist: die große
                          // Zahl, neben der die Bezirkszahl erst etwas sagt.
                          <>
                            <span className="block tabular-nums">{zahl(z.area_votes)}</span>
                            <span className="block text-[11px] text-muted-foreground tabular-nums">
                              {z.area_votes && z.votes !== null
                                ? `${prozent((100 * z.votes) / z.area_votes)} davon hier`
                                : `Wahlbereich ${z.area_roman}`}
                            </span>
                          </>
                        )}
                      </td>
                      <td className={cn("border-b border-border/60", SPALTE_ZAHL)}>
                        <span className={cn("block", drin && "font-semibold")}>{zahl(z.votes)}</span>
                        <Balken votes={z.votes} max={max} drin={drin} />
                      </td>
                      <td className={cn("border-b border-border/60", SPALTE_ZAHL, "text-muted-foreground")}>{z.party_share_pct === null ? "–" : prozent(z.party_share_pct)}</td>
                      <td className="border-b border-border/60 px-3 py-2">
                        <span className="flex items-center gap-2">
                          <Statuspille z={z} daten={liste} />
                          {beobachtet.angemeldet ? (
                            <Stern gemerkt={beobachtet.istGemerkt(z)} onClick={() => beobachtet.umschalten(z)} name={z.name} />
                          ) : null}
                        </span>
                      </td>
                    </tr>
                    {auf ? (
                      <tr>
                        <td colSpan={7} className="border-b border-border/60 px-3 pb-3">
                          <KandidatBezirke
                            party={z.party} area={z.area} position={z.position}
                            probe={probe} counted={counted} rueckblick={rueckblick} offen
                          />
                        </td>
                      </tr>
                    ) : null}
                    </Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Darunter: Zeilenblöcke mit eigener Beschriftung. */}
          <ol className={cn("mt-2 divide-y divide-border/70 border-t border-border/70 breit:hidden", abfrage.isPlaceholderData && "opacity-60 transition-opacity")}>
            {liste.rows.map((z) => {
              const drin = z.elected !== null;
              const id = `${z.party}-${z.area}-${z.position}`;
              const auf = offen === id;
              return (
                <li
                  key={id}
                  className={cn("group/zeile -mx-2 cursor-pointer rounded-lg px-2 py-2.5 transition-colors duration-tipp hover:bg-primary/5", auf && "bg-primary/[0.04]")}
                  onClick={zeilenKlick(() => setOffen(auf ? null : id))}
                >
                  <span className="flex items-start gap-2.5">
                  <span className="w-7 flex-none pt-0.5 text-right font-mono text-[10.5px] text-muted-foreground tabular-nums">{z.rank ?? "–"}</span>
                  <span className="min-w-0 flex-1">
                    <Aufklapper auf={auf} onClick={() => setOffen(auf ? null : id)} name={z.name}>
                      <span className={cn("block truncate text-[13px]", drin ? "font-semibold" : "font-medium")}>{z.name}</span>
                    </Aufklapper>
                    <span className="mt-0.5 flex flex-wrap items-center gap-x-1.5 text-[11.5px] text-muted-foreground">
                      <Punkt color={z.color} dark={z.color_dark} />
                      {z.party_short} · Platz {z.position} · {liste.district === null ? `WB ${z.area_roman}` : `Bezirk ${liste.district}`}
                    </span>
                    {liste.district === null && z.top_district !== null ? (
                      <span className="block truncate text-[11px] text-muted-foreground">↗ {z.top_district_name} · {zahl(z.top_district_votes)}</span>
                    ) : null}
                    <span className="mt-1.5 block"><Balken votes={z.votes} max={max} drin={drin} /></span>
                    <span className="mt-1 flex items-center gap-2"><Statuspille z={z} daten={liste} /></span>
                  </span>
                  <span className="flex-none text-right">
                    <span className={cn("block text-[13px] tabular-nums", drin && "font-semibold")}>{zahl(z.votes)}</span>
                    <span className="block text-[10.5px] text-muted-foreground tabular-nums">{z.party_share_pct === null ? "" : `${prozent(z.party_share_pct)} der Liste${liste.district === null ? "" : " hier"}`}</span>
                  </span>
                  {beobachtet.angemeldet ? (
                    <Stern gemerkt={beobachtet.istGemerkt(z)} onClick={() => beobachtet.umschalten(z)} name={z.name} className="mt-0.5 flex-none" />
                  ) : null}
                  </span>
                  {auf ? (
                    <span className="mt-2 block">
                      <KandidatBezirke
                        party={z.party} area={z.area} position={z.position}
                        probe={probe} counted={counted} rueckblick={rueckblick} offen
                      />
                    </span>
                  ) : null}
                </li>
              );
            })}
          </ol>
        </>
      )}
    </section>
  );
}
