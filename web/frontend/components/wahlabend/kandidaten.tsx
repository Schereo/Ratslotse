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
import { useMemo } from "react";
import { KICKER, Punkt, TON } from "@/components/wahlabend/bausteine";
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

function Statuspille({ z, daten }: { z: KandidatenZeile; daten: Kandidatenliste }) {
  const s = kandidatenStatus(z, daten.phase, daten.person_votes_available);
  return <span className={cn("inline-block whitespace-nowrap rounded-full px-2 py-0.5 text-[10.5px] font-semibold", TON[s.ton])}>{s.text}</span>;
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
  const pfad = kandidatenPfad(probe, counted, rueckblick, filter.sortierung, filter.liste, filter.bereich);
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
    const alle = daten.areas.flatMap((a) => a.parties.flatMap((p) => p.candidates.map((k) => k.votes ?? 0)));
    return Math.max(0, ...alle);
  }, [daten]);
  const listeInfo = filter.liste ? daten.parties.find((p) => p.slug === filter.liste) : null;
  const vorher = daten.phase === "before";

  return (
    <section className="mt-5 @container">
      <h2 className="font-display text-[16px] font-bold tracking-tight">Alle Kandidat*innen nach Personenstimmen</h2>
      <p className="mt-1 text-[13px] text-muted-foreground">
        {vorher
          ? "Die Personenstimmen kommen mit der Auszählung — bis dahin stehen hier die Namen in Stimmzettel-Reihenfolge."
          : "Der Rang ist stadtweit und bleibt es auch gefiltert. Der Anteil sagt, wie viel von allen Stimmen der eigenen Liste im Wahlbereich auf diese Person entfielen."}
      </p>

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
        <Chip an={filter.bereich === null} onClick={() => setFilter({ ...filter, bereich: null })}>Alle Wahlbereiche</Chip>
        {daten.areas.map((a) => (
          <Chip key={a.number} an={filter.bereich === a.number} onClick={() => setFilter({ ...filter, bereich: filter.bereich === a.number ? null : a.number })} title={a.name}>
            {a.roman}
            <span className="hidden text-muted-foreground sm:inline">· {a.name}</span>
          </Chip>
        ))}
      </div>

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
                  <th scope="col" className="w-36 border-b border-border px-3 py-2 text-left font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">Wahlbereich</th>
                  <th scope="col" className="w-48 border-b border-border border-l border-l-border/70 px-3 py-2 text-right font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">Personenstimmen</th>
                  <th scope="col" className="w-24 border-b border-border border-l border-l-border/70 px-3 py-2 text-right font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground" title="Anteil an allen Stimmen der eigenen Liste im Wahlbereich">Anteil</th>
                  <th scope="col" className="w-48 border-b border-border px-3 py-2 text-left font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">Stand</th>
                </tr>
              </thead>
              <tbody>
                {liste.rows.map((z) => {
                  const drin = z.elected !== null;
                  return (
                    <tr key={`${z.party}-${z.area}-${z.position}`} className="group">
                      <td className="border-b border-border/60 px-2 py-2 text-right font-mono text-[11px] text-muted-foreground tabular-nums">{z.rank ?? "–"}</td>
                      <td className="border-b border-border/60 px-3 py-2">
                        <span className={cn("block truncate", drin ? "font-semibold" : "font-medium")}>{z.name}</span>
                        <span className="block truncate text-[11.5px] text-muted-foreground">
                          {[z.occupation, z.born ? `*${z.born}` : null].filter(Boolean).join(" · ")}
                        </span>
                      </td>
                      <td className="border-b border-border/60 px-3 py-2">
                        <span className="flex items-center gap-1.5"><Punkt color={z.color} dark={z.color_dark} />{z.party_short}</span>
                        <span className="block text-[11px] text-muted-foreground">Platz {z.position}</span>
                      </td>
                      <td className="border-b border-border/60 px-3 py-2">
                        <span className="block">{z.area_roman}</span>
                        <span className="block truncate text-[11px] text-muted-foreground">{z.area_name}</span>
                      </td>
                      <td className={cn("border-b border-border/60", SPALTE_ZAHL)}>
                        <span className={cn("block", drin && "font-semibold")}>{zahl(z.votes)}</span>
                        <Balken votes={z.votes} max={max} drin={drin} />
                      </td>
                      <td className={cn("border-b border-border/60", SPALTE_ZAHL, "text-muted-foreground")}>{z.party_share_pct === null ? "–" : prozent(z.party_share_pct)}</td>
                      <td className="border-b border-border/60 px-3 py-2"><Statuspille z={z} daten={liste} /></td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Darunter: Zeilenblöcke mit eigener Beschriftung. */}
          <ol className={cn("mt-2 divide-y divide-border/70 border-t border-border/70 breit:hidden", abfrage.isPlaceholderData && "opacity-60 transition-opacity")}>
            {liste.rows.map((z) => {
              const drin = z.elected !== null;
              return (
                <li key={`${z.party}-${z.area}-${z.position}`} className="flex items-start gap-2.5 py-2.5">
                  <span className="w-7 flex-none pt-0.5 text-right font-mono text-[10.5px] text-muted-foreground tabular-nums">{z.rank ?? "–"}</span>
                  <span className="min-w-0 flex-1">
                    <span className={cn("block truncate text-[13px]", drin ? "font-semibold" : "font-medium")}>{z.name}</span>
                    <span className="mt-0.5 flex flex-wrap items-center gap-x-1.5 text-[11.5px] text-muted-foreground">
                      <Punkt color={z.color} dark={z.color_dark} />
                      {z.party_short} · Platz {z.position} · WB {z.area_roman}
                    </span>
                    <span className="mt-1.5 block"><Balken votes={z.votes} max={max} drin={drin} /></span>
                    <span className="mt-1 block"><Statuspille z={z} daten={liste} /></span>
                  </span>
                  <span className="flex-none text-right">
                    <span className={cn("block text-[13px] tabular-nums", drin && "font-semibold")}>{zahl(z.votes)}</span>
                    <span className="block text-[10.5px] text-muted-foreground tabular-nums">{z.party_share_pct === null ? "" : `${prozent(z.party_share_pct)} der Liste`}</span>
                  </span>
                </li>
              );
            })}
          </ol>
        </>
      )}
    </section>
  );
}
