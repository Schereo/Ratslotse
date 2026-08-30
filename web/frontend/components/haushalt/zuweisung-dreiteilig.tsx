"use client";

// Die drei Teile der Landeszuweisung — der Block, der eine zu kleine Zahl
// gerade rückt.
//
// Was er korrigiert: Die Kurve darüber und die Kachel „Schlüsselzuweisungen
// vom Land" zeigen den Open-Data-Datensatz 1106 der Stadt. Der enthält
// **zwei** der drei Komponenten des kommunalen Finanzausgleichs — nachgemessen
// auf den Euro: Ausgleichsjahr 2025 = 51.653 + 17.557 = 69.210 T€,
// Ausgleichsjahr 2026 = 62.654 + 19.624 = 82.278 T€. Die dritte, „Zuweisungen
// für Aufgaben des übertragenen Wirkungskreises", steht nur beim Land und ist
// mit 12–13 % des Ausgleichs kein Rundungsposten. Der Anteil im Text wird
// gerechnet, nicht geschrieben — er ist je Jahr ein anderer.
//
// Warum die alte Zahl trotzdem stehen bleibt: Sie ist nicht falsch, sie ist
// enger. „Schlüsselzuweisungen" heißen genau die beiden ersten Teile; der
// dritte ist rechtlich etwas anderes und zweckgebunden. Der Block ersetzt
// deshalb nichts, er stellt daneben — und sagt, dass die Summe größer ist.
//
// Keine Bewertungsfarbe: Ob eine höhere Zuweisung gut ist, sagt diese Seite
// nicht. Sie sagt, wie hoch sie ist.

import { FinanzausgleichJahr, deMio } from "@/lib/haushalt";
import { Beleg } from "@/components/haushalt/quelle";
import { GlossaryText } from "@/components/glossary-text";

/** Die drei Komponenten in der Reihenfolge, in der das Blatt sie führt. */
const TEILE: {
  feld: keyof FinanzausgleichJahr;
  titel: string;
  erklaerung: string;
  imDatensatz: boolean;
}[] = [
  {
    feld: "zuweisungen_gemeindeaufgaben",
    titel: "Für Gemeindeaufgaben",
    erklaerung: "Der große Teil des Ausgleichs: Geld für das, was jede Gemeinde tut.",
    imDatensatz: true,
  },
  {
    feld: "zuweisungen_kreisaufgaben",
    titel: "Für Kreisaufgaben",
    erklaerung:
      "Oldenburg ist kreisfrei und erledigt zusätzlich die Aufgaben eines Landkreises — "
      + "Sozialhilfe, Jugendhilfe, Kfz-Zulassung.",
    imDatensatz: true,
  },
  {
    feld: "zuweisungen_uebertragener_wirkungskreis",
    titel: "Für übertragene staatliche Aufgaben",
    erklaerung:
      "Geld dafür, dass die Stadt Aufgaben des Landes miterledigt: Standesamt, "
      + "Melde- und Ausländerwesen, Bauaufsicht. Es ist an diese Aufgaben gebunden.",
    imDatensatz: false,
  },
];

export function ZuweisungDreiteilig({ reihe }: { reihe?: FinanzausgleichJahr[] }) {
  const jahre = (reihe ?? []).filter((j) => j.nettobetrag != null);
  if (!jahre.length) return null;
  const j = jahre[jahre.length - 1];

  // Was der Open-Data-Datensatz führt — nicht aus ihm gelesen, sondern aus
  // denselben Zeilen gerechnet, damit die beiden Zahlen im Block garantiert
  // zueinander passen. Der Abgleich mit dem Datensatz selbst ist die Probe im
  // Ingest (council/steuerkraft.py), nicht die Aufgabe der Oberfläche.
  const zweiTeile = (j.zuweisungen_gemeindeaufgaben ?? 0) + (j.zuweisungen_kreisaufgaben ?? 0);
  const dritter = j.zuweisungen_uebertragener_wirkungskreis ?? 0;
  const umlage = j.finanzausgleichsumlage ?? 0;
  const anteil = j.nettobetrag ? Math.round((dritter / j.nettobetrag) * 100) : 0;

  return (
    <section className="rounded-2xl border border-border bg-card p-4 shadow-sm">
      <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
        Ausgleichsjahr {j.year}
      </p>
      <h3 className="mt-1 font-display text-[16px] font-bold leading-tight tracking-tight">
        Die Zuweisung hat drei Teile — die Kurve oben zeigt zwei
      </h3>
      <div className="mt-1.5 max-w-[74ch] text-[12.5px] leading-relaxed text-foreground/85">
        <GlossaryText
          text={"Der Datensatz der Stadt führt unter „Schlüsselzuweisungen“ die ersten beiden "
            + `Teile. Der dritte steht nur beim Land — und ist mit ${anteil} % der Summe kein `
            + "Rundungsposten."}
        />
      </div>

      <dl className="mt-3 divide-y divide-dashed divide-border border-y border-dashed border-border">
        {TEILE.map((t) => {
          const wert = j[t.feld];
          return (
            <div key={t.feld} className="grid grid-cols-[1fr_auto] items-baseline gap-x-4 py-2.5">
              <dt className="min-w-0">
                <span className="text-[13px] font-semibold leading-snug">{t.titel}</span>
                {!t.imDatensatz && (
                  <span className="ml-1.5 whitespace-nowrap rounded-full border border-dashed border-border px-1.5 py-0.5 align-middle font-mono text-[9px] uppercase tracking-[0.08em] text-muted-foreground">
                    fehlte bisher
                  </span>
                )}
                <span className="mt-0.5 block max-w-[70ch] text-[11.5px] leading-relaxed text-muted-foreground">
                  {t.erklaerung}
                </span>
              </dt>
              <dd className="whitespace-nowrap font-display text-[15px] font-bold tabular-nums">
                {typeof wert === "number" ? deMio(wert / 1000) : "—"}
                <span className="ml-1 font-sans text-[10px] font-normal text-muted-foreground">
                  Mio.&nbsp;€
                </span>
              </dd>
            </div>
          );
        })}
        {umlage > 0 && (
          <div className="grid grid-cols-[1fr_auto] items-baseline gap-x-4 py-2.5">
            <dt className="text-[13px] font-semibold">abzüglich Finanzausgleichsumlage</dt>
            <dd className="whitespace-nowrap font-display text-[15px] font-bold tabular-nums">
              −{deMio(umlage / 1000)}
              <span className="ml-1 font-sans text-[10px] font-normal text-muted-foreground">
                Mio.&nbsp;€
              </span>
            </dd>
          </div>
        )}
        <div className="grid grid-cols-[1fr_auto] items-baseline gap-x-4 py-2.5">
          <dt className="text-[13px] font-bold">Zusammen bekommt die Stadt</dt>
          <dd className="whitespace-nowrap font-display text-[19px] font-bold tabular-nums">
            {deMio((j.nettobetrag ?? 0) / 1000)}
            <span className="ml-1 font-sans text-[10px] font-normal text-muted-foreground">
              Mio.&nbsp;€
            </span>
          </dd>
        </div>
      </dl>

      <p className="mt-2.5 max-w-[74ch] text-[11.5px] leading-relaxed text-muted-foreground">
        Die Kurve und die Kachel „Schlüsselzuweisungen vom Land“ nennen{" "}
        {deMio(zweiTeile / 1000)}&nbsp;Mio.&nbsp;€ — das ist derselbe Ausgleich, nur ohne den
        dritten Teil. Beide Zahlen stimmen; sie zählen Verschiedenes. Wer wissen will, was vom
        Land insgesamt kommt, nimmt die untere.
      </p>
      <p className="mt-2 border-t border-dashed border-border pt-2.5 text-[11px] text-muted-foreground">
        Quelle: Landesamt für Statistik Niedersachsen, Blatt „9a“
        <Beleg q="lsn_finanzausgleich" />
        {" "}· Probe: Die drei Teile minus Umlage ergeben den ausgewiesenen Nettobetrag, für
        alle acht kreisfreien Städte.
      </p>
    </section>
  );
}
