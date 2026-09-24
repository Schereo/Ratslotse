"use client";

/**
 * „Der neue Rat": wer nach der Ratswahl ab dem 1. November im Rat sitzt.
 *
 * Nach Listen gruppiert, in der Reihenfolge des Stimmzettels — dieselbe wie
 * auf der Wahlabend-Seite. Wer schon ein Profil aus den Protokollen hat,
 * verlinkt dorthin; für alle anderen baut die Personen-Seite ein Profil aus
 * dem Wahlergebnis (`components/neuer-rat.tsx`).
 */
import { useMemo, useState } from "react";
import { notFound } from "next/navigation";
import Link from "next/link";

import { Punkt } from "@/components/wahlabend/bausteine";
import {
  MANDAT, StandHinweis, langesDatum, letztePeriode, steckbrief, useGewaehlt,
  type Gewaehlt, type GewaehlterRat,
} from "@/components/neuer-rat";
import { Card, DetailSkeleton, PageHeader, Segmented } from "@/components/ui";
import { personHref } from "@/lib/routes";
import { ratsjahre } from "@/lib/ratsjahre";

type Filter = "all" | Gewaehlt["council_status"];

const zahl = (n: number) => n.toLocaleString("de-DE");

function PersonKarte({ g, letzte }: { g: Gewaehlt; letzte: number }) {
  const info = steckbrief(g);
  const jahre = ratsjahre(g.council_terms, letzte);
  return (
    <Link href={personHref(g.slug)} className="block">
      <Card className="card-interactive h-full p-3.5">
        <div className="flex items-start justify-between gap-2">
          <p className="min-w-0 text-[15px] font-semibold leading-snug text-foreground">{g.name}</p>
          {g.council_status === "new" && (
            <span className="shrink-0 rounded-full border border-primary/25 bg-primary/10 px-2 py-px text-[10.5px] font-semibold text-primary">
              neu
            </span>
          )}
          {g.council_status === "former" && (
            <span className="shrink-0 rounded-full border border-border bg-muted px-2 py-px text-[10.5px] font-semibold text-muted-foreground">
              zurück
            </span>
          )}
        </div>
        {info && <p className="mt-0.5 text-xs text-muted-foreground">{info}</p>}
        <p className="mt-2 text-xs text-muted-foreground">
          Wahlbereich {g.area_roman} · {g.area_name}
        </p>
        <p className="text-xs text-muted-foreground">
          {g.votes != null ? `${zahl(g.votes)} Stimmen` : null}
          {g.votes != null && MANDAT[g.mandate] ? " · " : null}
          {MANDAT[g.mandate]}
        </p>
        {jahre && <p className="mt-1.5 text-xs text-muted-foreground">Im Rat {jahre}</p>}
        {/* Die Karte steht weiter unter der Liste, über die gewählt wurde —
            das ist das Wahlergebnis. Die Abweichung steht daneben; die Quelle
            dazu auf der Personen-Seite (ein Link im Link ginge hier nicht). */}
        {g.affiliation && (
          <p className="mt-1.5 text-xs font-medium text-foreground">
            Tritt {g.affiliation.label} an
          </p>
        )}
      </Card>
    </Link>
  );
}

export default function View() {
  const { an, data, laedt } = useGewaehlt<GewaehlterRat>();
  const [filter, setFilter] = useState<Filter>("all");

  const gruppen = useMemo(() => {
    const out: { list: string; short: string; color: string; dark: string; members: Gewaehlt[]; sitze: number }[] = [];
    for (const m of data?.members ?? []) {
      let g = out.find((x) => x.list === m.list);
      if (!g) {
        g = { list: m.list, short: m.list_short, color: m.color, dark: m.color_dark, members: [], sitze: 0 };
        out.push(g);
      }
      g.sitze += 1;
      if (filter === "all" || filter === m.council_status) g.members.push(m);
    }
    return out;
  }, [data, filter]);

  if (laedt) return <DetailSkeleton />;
  if (!an || !data) notFound();

  const zahl_ = (st: Gewaehlt["council_status"]) => data.members.filter((m) => m.council_status === st).length;
  const neu = zahl_("new"), wieder = zahl_("current"), zurueck = zahl_("former");
  const letzte = letztePeriode(data.term_start);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Der neue Rat"
        description={`Gewählt am ${langesDatum(data.date)} · im Amt ab ${langesDatum(data.term_start)}`}
      />

      <div className="max-w-3xl space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <StandHinweis status={data.status} />
        </div>
        <p className="text-lese text-foreground">
          {data.seats} Sitze, dazu kraft Amtes die Oberbürgermeisterin oder der Oberbürgermeister.{" "}
          <strong className="font-semibold">{neu}</strong> der Gewählten saßen noch nie im Rat,{" "}
          <strong className="font-semibold">{wieder}</strong> sind wieder dabei
          {zurueck > 0 && <>, <strong className="font-semibold">{zurueck}</strong> kehren nach einer Pause zurück</>}.
        </p>
        {data.status === "vorlaeufig" && (
          <p className="text-hinweis text-muted-foreground">
            Das ist das vorläufige Ergebnis vom Wahlabend. Endgültig wird es, wenn der Wahlausschuss
            das amtliche Endergebnis feststellt. Danach kann sich noch ändern, wer einen Sitz
            übernimmt: Wer die Wahl ablehnt, wird durch eine Ersatzperson derselben Liste ersetzt.
          </p>
        )}
      </div>

      {data.vacancies.length > 0 && (
        <Card className="max-w-3xl p-4">
          <h2 className="font-display text-[15px] font-bold text-foreground">Wechsel nach der Wahl</h2>
          <ul className="mt-2 space-y-1.5 text-[13.5px] text-foreground">
            {data.vacancies.map((v) => (
              <li key={v.name}>
                <strong className="font-semibold">{v.name}</strong> ({v.list_short}) — {v.reason}
                {v.successor ? <>; nachgerückt ist {v.successor}</> : <>; die Nachfolge steht noch nicht fest</>}
                {v.source && (
                  <>
                    {" "}(<a href={v.source} target="_blank" rel="noreferrer" className="text-primary underline-offset-2 hover:underline">Quelle</a>)
                  </>
                )}.
              </li>
            ))}
          </ul>
        </Card>
      )}

      {/* Vier Segmente sind auf 390 px einen Hauch zu breit — seitwärts
          rollen wie die Analyse-Reiter, statt die Seite zu schieben. */}
      <Segmented<Filter>
        className="overflow-x-auto sm:w-fit"
        value={filter}
        onChange={setFilter}
        options={[
          { value: "all", label: `Alle ${data.members.length}` },
          { value: "new", label: `Neu ${neu}` },
          { value: "current", label: `Wieder dabei ${wieder}` },
          ...(zurueck > 0 ? [{ value: "former" as const, label: `Zurück ${zurueck}` }] : []),
        ]}
      />

      <div className="space-y-7">
        {gruppen.filter((g) => g.members.length > 0).map((g) => (
          <section key={g.list}>
            <div className="flex items-baseline gap-2.5">
              <Punkt color={g.color} dark={g.dark} className="translate-y-[-1px]" />
              <h2 className="font-display text-base font-bold text-foreground">{g.short}</h2>
              <span className="font-mono text-[11px] uppercase tracking-[0.08em] text-muted-foreground">
                {g.sitze} {g.sitze === 1 ? "Sitz" : "Sitze"}
              </span>
            </div>
            <div className="mt-2.5 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {g.members.map((m) => <PersonKarte key={m.slug} g={m} letzte={letzte} />)}
            </div>
          </section>
        ))}
      </div>

      <p className="max-w-3xl border-t border-border pt-4 text-hinweis text-muted-foreground">
        Quelle: das Wahlergebnis der Stadt Oldenburg (Open Data des Votemanagers), die Sitze nach
        §§ 36/37 NKWG nachgerechnet wie am Wahlabend. Beruf und Jahrgang aus der{" "}
        <a className="text-primary underline-offset-2 hover:underline" target="_blank" rel="noreferrer"
          href="https://www.oldenburg.de/fileadmin/oldenburg/Benutzer/Dateien/22_Rechtsamt/Bekanntmachungen/20260724-Zulassung_Wahlvorschlaege.pdf">
          Bekanntmachung der zugelassenen Wahlvorschläge
        </a>. Wer schon im Rat saß, steht in den Ratsprotokollen (ab 2018) oder mit seinen Mandaten im
        Ratsinformationssystem der Stadt, das sie für heutige Ratsmitglieder bis 1991 zurück führt. Wer vor 2018
        im Rat saß und dort nicht mehr geführt wird, erscheint hier als neu.
      </p>
    </div>
  );
}
