"use client";

// Das Wähler*innen-Potenzial für die Stichwahl (docs/plan-stichwahl-potenzial.md,
// P2): die Seite hinter dem Link, den man raten müsste. Kein Knopf führt
// hierher, kein Suchindex kennt sie, und ohne den Token aus der `.env`
// antwortet der Server wie für eine Adresse, die es nicht gibt.
//
// Vier Ansichten auf EINE Rechnung (`potential.py`): die Tafel mit dem, was
// Rohr braucht, samt Reglern für die Annahmen; die Karte mit der Einstufung je
// Bezirk; die Einsatzliste nach Stadtbezirken mit Haken; und der Blick auf
// 2021. Gerechnet wird im Backend — jede Reglerstellung ist eine Anfrage,
// die Seite hält die letzte Antwort, bis die neue da ist.
//
// Alles hier ist Rechnung, nichts Prognose. Die Regler sind Tims Einschätzung
// in Zahlen; die Seite sagt das an jeder Stelle, an der jemand eine Zahl
// für eine Messung halten könnte.

import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { KICKER } from "@/components/wahlabend/bausteine";
import { Kopf } from "@/components/wahlabend/kopf";
import { Mascot } from "@/components/mascot";
import { api } from "@/lib/api";
import { VORGABE, potenzialPfad, saldoSatz, type Potenzial, type Regler } from "@/lib/potenzial";
import { useTween } from "@/lib/use-tween";
import { cn } from "@/lib/utils";
import { prozent, zahl } from "@/lib/wahlabend";
import { Briefwahl, Lehren2014, Lehren2021, Vorbehalte } from "./bloecke";
import { Einsatzliste } from "./einsatzliste";
import { PotenzialKarte } from "./karte";
import { ReglerTafel } from "./regler";

function Hinweisbild() {
  return (
    <div data-testid="potenzial-fehlt" className="mx-auto mt-16 flex max-w-md flex-col items-center text-center">
      <Mascot pose="confused" className="h-28 w-28" decorative />
      <h1 className="mt-4 font-display text-[22px] font-bold tracking-tight">Hier gibt es nichts</h1>
      <p className="mt-2 text-[14px] leading-relaxed text-muted-foreground">
        Diese Adresse führt zu keiner Seite. Vielleicht ist der Link nicht vollständig.
      </p>
    </div>
  );
}

/** Die eine Zahl groß, ihr Name klein darunter — die Bauform der Anzeigetafel. */
function Kennzahl({ wert, name, hinweis, className }: { wert: string; name: string; hinweis?: string; className?: string }) {
  return (
    <div className={cn("min-w-0", className)} title={hinweis}>
      <div className="font-display text-[26px] font-bold tabular-nums leading-none tracking-tight sm:text-[30px]">{wert}</div>
      <div className={cn(KICKER, "mt-1.5")}>{name}</div>
    </div>
  );
}

/** Was Rohr braucht: der Rückstand, die Reserven, und darunter das Duell
 *  nach den Reglern. Der Balken läuft an, wenn eine Annahme sich ändert —
 *  so sieht man, was ein Regler bewegt, statt nur eine neue Zahl zu lesen. */
function Tafel({ p, rechnet }: { p: Potenzial; rechnet: boolean }) {
  const summe = p.projected_rohr + p.projected_prange;
  const anteil = useTween(summe > 0 ? (100 * p.projected_rohr) / summe : 50, 450) ?? 50;
  const saldo = useTween(p.balance, 450) ?? p.balance;
  const vorn = p.balance >= 0;
  return (
    <section data-testid="potenzial-tafel" className="hh-tafel mt-6 rounded-2xl border px-5 py-5 sm:px-7 sm:py-6">
      <div className="grid grid-cols-2 gap-x-6 gap-y-5 sm:grid-cols-4">
        <Kennzahl wert={zahl(p.lead)} name="Rückstand im ersten Wahlgang" hinweis={`Prange ${zahl(p.prange)} · Rohr ${zahl(p.rohr)}`} />
        <Kennzahl wert={zahl(p.pool)} name="Stimmen der Ausgeschiedenen" hinweis="Stimmen für alle sieben ausgeschiedenen Kandidaturen, einschließlich der unter „Sonstige“ zusammengefassten" />
        <Kennzahl wert={`≈ ${zahl(p.cdu_voters_est)}`} name="Geschätzte CDU-Wählende" hinweis={`${zahl(p.cdu_council)} CDU-Stimmen bei der Ratswahl, geteilt durch durchschnittlich ${p.votes_per_voter.toFixed(2).replace(".", ",")} Stimmen je Wählendem. Die CDU hatte keine eigene OB-Kandidatur.`} />
        <Kennzahl wert={zahl(p.non_voters)} name="Nichtwählende" hinweis={`${zahl(p.eligible)} Wahlberechtigte minus ${zahl(p.voters)} Wählende (Urne und Brief); je Bezirk geschätzt`} />
      </div>

      <div className="mt-7">
        <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
          <h2 className="font-display text-[20px] font-bold tracking-tight sm:text-[22px]">
            {saldoSatz(Math.round(saldo))}
          </h2>
          <span className={cn(KICKER, "transition-opacity", rechnet ? "opacity-100" : "opacity-0")} aria-live="polite">
            rechnet …
          </span>
        </div>
        <p className="mt-1 text-[13px] text-muted-foreground">
          Nach deinen Annahmen verändert sich der Stimmenabstand für Rohr gegenüber dem ersten Wahlgang um {zahl(p.net_total)} Stimmen.
          Um Prange zu überholen, müsste er den Rückstand um {zahl(p.lead + 1)} Stimmen verringern.
        </p>

        <div className="relative mt-4 h-7 overflow-hidden rounded-full bg-muted" role="img"
          aria-label={`Rohr ${zahl(p.projected_rohr)} gegen Prange ${zahl(p.projected_prange)}`}>
          <div className="absolute inset-y-0 left-0 transition-none" style={{ width: `${anteil}%`, background: "hsl(var(--signal) / 0.85)" }} />
          <div className="absolute inset-y-0 right-0 bg-foreground/30" style={{ width: `${100 - anteil}%` }} />
          <div aria-hidden className="absolute inset-y-0 left-1/2 w-[2px] -translate-x-1/2 bg-background" />
        </div>
        <div className="mt-2 flex flex-wrap justify-between gap-x-3 font-mono text-[12px] tabular-nums">
          <span className={cn("whitespace-nowrap", vorn ? "font-semibold" : "text-muted-foreground")}>Rohr {zahl(p.projected_rohr)} · {prozent(anteil)}</span>
          <span className={cn("whitespace-nowrap", !vorn ? "font-semibold" : "text-muted-foreground")}>{prozent(100 - anteil)} · Prange {zahl(p.projected_prange)}</span>
        </div>
      </div>
    </section>
  );
}

/** Drei Sätze vorweg — die Befunde, die man auch ohne Regler mitnehmen soll. */
function Befunde({ p }: { p: Potenzial }) {
  const oben = p.bundles[0];
  const unten = [...p.bundles].sort((a, b) => (a.yield_per_1000 ?? 0) - (b.yield_per_1000 ?? 0))[0];
  const faktor = oben && unten && unten.yield_per_1000 ? (oben.yield_per_1000 ?? 0) / unten.yield_per_1000 : null;
  const saetze = [
    {
      title: "Rohrs Anteil war bei der Briefwahl höher.",
      text: `Unter den Stimmen für Rohr und Prange lag sein Anteil per Brief bei ${prozent(p.rohr_pct_postal)}, an der Urne bei ${prozent(p.rohr_pct_urn)}. Auch Fuhrhop erreichte 2021 per Brief einen höheren Anteil. Bei Gesprächen kann die Briefwahl zur Sprache kommen.`,
    },
    {
      title: "Nicht alle Kandidaturen waren in denselben Vierteln stark.",
      text: "Butzin und Küßner erhielten Stimmen in Bümmerstede, Kreyenbrück und Krusenbusch, weniger in Eversten. Die eigenen Hochburgen im Blick zu behalten und in anderen Vierteln Gespräche zu führen, schließt sich nicht aus.",
    },
    {
      title: faktor ? `Der berechnete Wert liegt in ${oben.district_name} ${faktor.toFixed(1).replace(".", ",")}-mal so hoch wie in ${unten.district_name}.` : "Der berechnete Wert unterscheidet sich zwischen den Stadtbezirken deutlich.",
      text: "Verglichen wird die Veränderung des Stimmenabstands je 1.000 Wahlberechtigte. Sie beruht auf den Einstellungen der Regler und misst nicht die Wirkung einzelner Gespräche. Die Einsatzliste ist nach diesem Wert sortiert.",
    },
  ];
  return (
    <section className="mt-8 grid gap-3 sm:grid-cols-3">
      {saetze.map((s, i) => (
        <div key={i} className="rounded-2xl border border-border bg-card p-4">
          <div className={KICKER}>Befund {i + 1}</div>
          <h3 className="mt-1.5 font-display text-[16px] font-bold leading-snug tracking-tight">{s.title}</h3>
          <p className="mt-2 text-[13px] leading-relaxed text-muted-foreground">{s.text}</p>
        </div>
      ))}
    </section>
  );
}

export function PotenzialView() {
  const params = useSearchParams();
  const token = params.get("k") ?? "";

  // Die Regler: `regler` folgt der Hand, `wirksam` dem Server — mit 180 ms
  // Abstand, damit ein Zug über die Skala eine Anfrage ist, nicht dreißig.
  const [regler, setRegler] = useState<Regler>(VORGABE);
  const [wirksam, setWirksam] = useState<Regler>(VORGABE);
  useEffect(() => {
    const t = setTimeout(() => setWirksam(regler), 180);
    return () => clearTimeout(t);
  }, [regler]);

  const { data, isError, isFetching } = useQuery({
    queryKey: ["stichwahl-potenzial", token, wirksam],
    queryFn: () => api.get<Potenzial>(potenzialPfad(token, wirksam)),
    enabled: token.length > 0,
    retry: false,
    staleTime: 10 * 60_000,
    placeholderData: keepPreviousData,
  });

  const urne = useMemo(() => (data?.districts ?? []).filter((z) => !z.postal), [data]);

  if (!token || isError) {
    return (
      <>
        <Kopf label="Stichwahl" />
        <main className="mx-auto w-full max-w-3xl px-4 pb-16 sm:px-6"><Hinweisbild /></main>
      </>
    );
  }
  if (!data) {
    return (
      <>
        <Kopf label="Stichwahl" />
        <main className="mx-auto w-full max-w-5xl px-4 pb-16 sm:px-6">
          <div className="mt-10 h-40 animate-pulse rounded-2xl bg-muted" />
        </main>
      </>
    );
  }

  return (
    <>
      <Kopf label="Stichwahl · Potenzial" />
      <main className="mx-auto w-full max-w-5xl px-4 pb-20 sm:px-6">
        <header className="mt-8 print:hidden">
          <div className="flex flex-wrap items-center gap-2">
            <span className={KICKER}>Wahlkampf-Werkzeug</span>
            <span className="rounded-full border border-dashed border-border px-2 py-0.5 font-mono text-[10px] uppercase tracking-[0.11em] text-muted-foreground">
              nur mit Link
            </span>
          </div>
          <h1 className="mt-2 font-display text-[28px] font-bold leading-tight tracking-tight sm:text-[34px]">
            Stichwahl-Potenzial in Oldenburg
          </h1>
          <p className="mt-2 max-w-2xl text-[14.5px] leading-relaxed text-muted-foreground">
            Diese Auswertung zur Stichwahl am 27. September nutzt die Ergebnisse aus 133 Wahlbezirken, die Ratswahl
            und die beiden früheren Stichwahlen. Wie viele Stimmen die ausgeschiedenen Kandidaturen erhielten, ist
            bekannt. Wie sich Stimmen in der Stichwahl verteilen könnten, zeigen die Annahmen in den Reglern.
          </p>
        </header>

        <Tafel p={data} rechnet={isFetching} />
        <div className="print:hidden">
          <Befunde p={data} />
          <ReglerTafel regler={regler} onChange={setRegler} annahmen={data.assumptions} cduWaehlende={data.cdu_voters_est} wiederkommen2014={data.lessons_2014.return_rate_pct} />
          <PotenzialKarte bezirke={urne} zaehler={data.strategy_counts} />
        </div>
        <Einsatzliste buendel={data.bundles} bezirke={urne} />
        <div className="print:hidden">
          <Briefwahl p={data} />
          <Lehren2021 p={data} />
          <Lehren2014 p={data} />
          <Vorbehalte p={data} />
        </div>
      </main>
    </>
  );
}
