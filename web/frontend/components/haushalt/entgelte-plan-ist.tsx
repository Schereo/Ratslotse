"use client";

// „Geplant und geworden" für einen Posten der Ergebnisrechnung
// (Steuer-Steckbrief, Einnahmearten ohne Steuerreihe).
//
// Die Schwester von `steuer-plan-ist.tsx`, aber aus einer anderen Quelle — und
// genau darin liegt der Grund, warum sie eine eigene Datei ist und nicht ein
// Schalter in jener: Tabelle 1103 stellt Plan und Ist nebeneinander und
// erläutert nichts dazu. Der Jahresabschluss tut mehr, und das muss die Anzeige
// tragen.
//
// DIE BEZUGSGRÖSSE WECHSELT ÜBER DIE JAHRGÄNGE. Wogegen ein Abschluss seine
// Abweichung rechnet, ist nicht in allen Jahren dasselbe: 2018 gegen die
// Gesamtermächtigung, 2020 gegen den Ansatz samt Nachtrag, sonst gegen den
// nackten Ansatz. Das steht als `plan_kind` an jeder Zeile, und es gehört an
// jede Hantel: Ohne diese Angabe vergliche die Reihe stillschweigend
// Verschiedenes. Deshalb ist `plan_kind` hier die Einordnung — nicht `null`,
// wie bei Tabelle 1103, die über sich selbst nichts sagt.
//
// KEINE BEWERTUNG (Regel des ganzen Bereichs). Weniger Gebühren als geplant
// ist kein Versagen — 2021 blieben die öffentlich-rechtlichen Entgelte fast
// 3 Mio. € hinter dem Ansatz, weil Einrichtungen geschlossen waren. Wer
// weniger nutzt, zahlt weniger. Die Hantel zeigt den Abstand, kein Urteil.

import { Hantel, type HantelZeile } from "@/components/grafik/hantel";
import { PLAN_ART_LABEL, type ErgebnisPosten } from "@/lib/haushalt";

export function EntgeltePlanIst({ zeilen, beleg }: {
  /** Die Gesamt-Zeilen (thh_nr = null) EINES Postens, ein Eintrag je Jahr. */
  zeilen: ErgebnisPosten[];
  /** Beleg-Chip-Slot (GB-00) — die Seite wählt die Quelle. */
  beleg?: React.ReactNode;
}) {
  // Beide Werte müssen da sein: Eine Hantel mit einem Ende ist keine Hantel,
  // sondern ein Punkt, der so tut, als wäre er ein Vergleich.
  const sortiert = zeilen
    .filter((z) => z.plan != null && z.plan > 0 && z.result != null)
    .sort((a, b) => a.year - b.year);
  if (sortiert.length < 2) return null;

  const hantelZeilen: HantelZeile[] = sortiert.map((z) => ({
    label: String(z.year),
    plan: (z.plan as number) / 1e6,
    ist: (z.result as number) / 1e6,
    // Die Bezugsgröße dieses Jahrgangs, im Klartext des Dokuments. Wo sie
    // fehlt, wird sie nicht durch „Ansatz" ersetzt — dann steht sie eben nicht
    // da, statt geraten zu werden.
    einordnung: z.plan_kind
      ? `Verglichen wird gegen: ${PLAN_ART_LABEL[z.plan_kind]}.`
      : null,
  }));

  return (
    <div className="rounded-2xl border border-border bg-card p-4 shadow-sm">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
          Geplant und geworden
        </p>
        <span className="font-mono text-[10px] uppercase text-muted-foreground">
          {sortiert[0].year}–{sortiert[sortiert.length - 1].year}
          {" · "}{sortiert.length} Jahre
        </span>
      </div>
      <p className="mt-1.5 max-w-[70ch] text-[12.5px] leading-relaxed text-foreground/80">
        Was im beschlossenen Haushalt stand — und was am Ende des Jahres
        tatsächlich in der Kasse war.
      </p>

      <div className="mt-3">
        <Hantel
          zeilen={hantelZeilen}
          unit="Mio. €"
          /* Chronologie schlägt Rangfolge: Dass 2024 auf 2023 folgt, muss die
             Reihenfolge tragen — wie weit es danebenlag, zeigt die Länge. */
          sortierung="alpha"
          wovon="diese Einnahme"
          keineWertung={
            <>Die Farbe bewertet nicht: Weniger als geplant heißt hier, dass
              Leistungen weniger genutzt wurden — mehr heißt umgekehrt, dass
              der Ansatz zu vorsichtig war. Keines von beidem ist für sich
              genommen gut oder schlecht.</>
          }
          beleg={beleg}
        />
      </div>
    </div>
  );
}
