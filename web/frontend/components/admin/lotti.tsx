"use client";

import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { ApiAntwort } from "@/lib/vertrag";
import { ChartSkeleton, ErrorState } from "@/components/ui";
import { cn } from "@/lib/utils";

import { AbschnittKopf } from "./primitives";

/**
 * Der Reiter „Lotti" — wird die Assistentin angenommen, und wofür?
 *
 * **Die Frage dahinter** (Tim, 21.09.2026): „ob das Feature angenommen wird
 * und welche Fragen gestellt werden". Dafür braucht es einen Trichter statt
 * Einzelzahlen: Eine große Zahl an Aufrufen sagt nichts, wenn sie von drei
 * Konten kommt.
 *
 * **Was die Fragen NICHT sind: vollständig.** Sie stammen aus gespeicherten
 * Gesprächen, also von den Konten mit Einwilligung. Der Reiter sagt das an
 * der Liste, statt einen Ausschnitt als Ganzes auszugeben — dieselbe
 * Ehrlichkeit wie bei „Antworten ohne Quelle · gespeicherte Gespräche".
 */
type AdminLotti = ApiAntwort<"/admin/stats/assistant">;

export function LottiTab() {
  const { data, isPending, isError, refetch, isFetching } = useQuery({
    queryKey: ["admin", "lotti"],
    queryFn: () => api.get<AdminLotti>("/admin/stats/assistant?days=30"),
  });
  if (isPending) return <ChartSkeleton />;
  if (isError || !data) {
    return <ErrorState title="Die Lotti-Zahlen konnten nicht geladen werden"
      onRetry={() => void refetch()} busy={isFetching} />;
  }

  const t = data.funnel;
  const c = data.calls;
  const modellanteil = c.with_model + c.without_model > 0
    ? c.without_model / (c.with_model + c.without_model) : null;

  return (
    <div className="space-y-8">
      <section className="space-y-3">
        <AbschnittKopf titel="Wird Lotti benutzt?">
          Die letzten {data.days} Tage, je Konto gezählt. „Gefragt“ heißt: mindestens
          eine Erklärung geholt — auch eine, die ohne Sprachmodell auskam.
        </AbschnittKopf>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Stufe label="Aktive Konten" n={t.active} von={null} />
          <Stufe label="Fenster geöffnet" n={t.opened} von={t.active} />
          <Stufe label="Gefragt" n={t.asked} von={t.opened} />
          <Stufe label="Speichern mit" n={t.saving} von={t.asked} />
        </div>
      </section>

      <section className="space-y-3">
        <AbschnittKopf titel="Was die Antworten gekostet haben">
          Der Anteil ohne Sprachmodell ist die wichtigere Zahl: Glossar,
          Beschluss-Kurzfassung und Seitenbeschreibung antworten aus geprüftem
          Text und kosten nichts.
        </AbschnittKopf>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Zahl label="Ohne Modell" n={c.without_model}
            note={modellanteil != null ? `${Math.round(modellanteil * 100)} % aller Antworten` : undefined} />
          <Zahl label="Mit Modell" n={c.with_model} />
          <Zahl label="An „Frag den Rat“" n={c.handed_over} />
          <Zahl label="Fenster geöffnet" n={c.opened} />
        </div>
      </section>

      <section className="space-y-3">
        <AbschnittKopf titel="Wo gefragt wird">
          Aus den gespeicherten Gesprächen — also von den Konten mit
          Einwilligung. Ein Ausschnitt, kein Gesamtbild.
        </AbschnittKopf>
        <div className="grid gap-4 sm:grid-cols-2">
          <Liste titel="Seiten" zeilen={data.pages} />
          <Liste titel="Bausteine" zeilen={data.elements} />
        </div>
      </section>

      <section className="space-y-3">
        <AbschnittKopf titel="Welche Fragen gestellt werden">
          Ebenfalls nur aus gespeicherten Gesprächen. Gleiche Fragen sind
          zusammengefasst; die Liste zeigt die fünfzig häufigsten.
        </AbschnittKopf>
        {data.questions.length === 0
          ? <p className="text-hinweis text-muted-foreground">Noch keine gespeicherten Fragen.</p>
          : (
            <ul className="divide-y divide-border rounded-xl border border-border bg-card">
              {data.questions.map((f) => (
                <li key={f.question} className="flex items-baseline gap-3 px-3 py-2">
                  <span className="min-w-0 flex-1 text-[13.5px] text-foreground">{f.question}</span>
                  <span className="shrink-0 font-mono text-meta tabular-nums text-muted-foreground">
                    {f.n}×
                  </span>
                </li>
              ))}
            </ul>
          )}
      </section>

      <section className="space-y-3">
        <AbschnittKopf titel="Was die Leute dazu sagen">
          Daumen an Lottis Antworten — nur aus ihrem Fenster (<code>source =
          lotti</code>), die des Ratsgesprächs stehen nicht darin. Der Grund
          steht nur da, wo jemand einen getippt hat.
        </AbschnittKopf>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {/* Die Quote am Daumen-hoch: Zwei nackte Zahlen beantworten
              „taugt das?" nicht — 12 zu 3 und 12 zu 40 sehen nebeneinander
              gleich aus. Ohne eine einzige Stimme steht sie nicht da: Ein
              „0 %" aus null Rückmeldungen wäre eine Behauptung. */}
          <Zahl label="Daumen hoch" n={data.feedback.up}
            note={data.feedback.up + data.feedback.down > 0
              ? `${Math.round(data.feedback.up * 100 / (data.feedback.up + data.feedback.down))} % der Daumen`
              : undefined} />
          <Zahl label="Daumen runter" n={data.feedback.down} />
          <Zahl label="Anstupser gezeigt" n={data.nudge.shown} />
          <Zahl label="davon angenommen" n={data.nudge.accepted} />
        </div>
        {data.feedback.reasons.length > 0 && (
          <ul className="space-y-1.5">
            {data.feedback.reasons.map((r, i) => (
              <li key={i} className="rounded-lg border border-border bg-card px-3 py-2 text-[13px] text-foreground/90">
                {r}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

/** Eine Stufe des Trichters — mit dem Anteil an der Stufe davor. */
function Stufe({ label, n, von }: { label: string; n: number; von: number | null }) {
  const anteil = von && von > 0 ? n / von : null;
  return (
    <div className="rounded-xl bg-muted/40 p-3">
      <p className="text-meta text-muted-foreground">{label}</p>
      <p className="mt-1 font-display text-[22px] font-bold leading-none tabular-nums text-foreground">
        {n.toLocaleString("de-DE")}
      </p>
      {anteil != null && (
        <p className="mt-1 font-mono text-[10.5px] tabular-nums text-muted-foreground">
          {Math.round(anteil * 100)} % der Stufe davor
        </p>
      )}
    </div>
  );
}

function Zahl({ label, n, note }: { label: string; n: number; note?: string }) {
  return (
    <div className="rounded-xl bg-muted/40 p-3">
      <p className="text-meta text-muted-foreground">{label}</p>
      <p className="mt-1 font-display text-[22px] font-bold leading-none tabular-nums text-foreground">
        {n.toLocaleString("de-DE")}
      </p>
      {note && <p className="mt-1 font-mono text-[10.5px] text-muted-foreground">{note}</p>}
    </div>
  );
}

function Liste({ titel, zeilen }: { titel: string; zeilen: { key: string; n: number }[] }) {
  const max = Math.max(1, ...zeilen.map((z) => z.n));
  return (
    <div className="rounded-xl border border-border bg-card p-3">
      <p className="font-mono text-[10px] uppercase tracking-[0.11em] text-muted-foreground">{titel}</p>
      {zeilen.length === 0
        ? <p className="mt-2 text-hinweis text-muted-foreground">Noch nichts.</p>
        : (
          <ul className="mt-2 space-y-1.5">
            {zeilen.map((z) => (
              <li key={z.key}>
                <div className="flex items-baseline justify-between gap-2">
                  <span className="min-w-0 truncate font-mono text-[11.5px] text-foreground">{z.key}</span>
                  <span className="shrink-0 font-mono text-[11.5px] tabular-nums text-muted-foreground">{z.n}</span>
                </div>
                <div className="mt-0.5 h-[5px] overflow-hidden rounded-full bg-muted">
                  <span className={cn("block h-full rounded-full bg-primary")}
                    style={{ width: `${Math.max(4, (z.n / max) * 100)}%` }} />
                </div>
              </li>
            ))}
          </ul>
        )}
    </div>
  );
}
