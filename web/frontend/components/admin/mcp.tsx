"use client";

import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { ApiAntwort } from "@/lib/vertrag";
import { AreaSparkline } from "@/components/admin-charts";
import { ChartSkeleton, ErrorState } from "@/components/ui";

import { AbschnittKopf } from "./primitives";

/**
 * Der Reiter „Agenten (MCP)" — wie benutzen eigene Agenten den MCP-Server?
 *
 * **Die Frage dahinter** (Tim, 18.10.2026): „gucken, wie Agents den nutzen".
 * Drei Antworten darauf: welche Werkzeuge sie aufrufen und in welcher
 * Reihenfolge (die Anleitung des Servers schlägt drei Wege vor — gehen sie
 * die?), wonach sie suchen, und wo die Suche sie ohne Treffer stehen lässt.
 *
 * **Mit Konto und Suchtext**, so entschieden und vorher angesagt: auf der
 * Freigabe-Seite und in der Einstellungskarte. Der Suchtext ist gekürzt,
 * Kontaktdaten sind maskiert, nach 90 Tagen ist er weg.
 */
type AdminMcp = ApiAntwort<"/admin/stats/mcp">;

function tageReihe(perDay: AdminMcp["per_day"], days: number) {
  const werte = new Map(perDay.map((d) => [d.day, d.n]));
  const tage: string[] = [];
  const heute = new Date();
  for (let i = days - 1; i >= 0; i--) {
    const t = new Date(Date.UTC(heute.getUTCFullYear(), heute.getUTCMonth(), heute.getUTCDate() - i));
    tage.push(t.toISOString().slice(0, 10));
  }
  return { tage, werte: tage.map((t) => werte.get(t) ?? 0) };
}

function ms(wert: number | null) {
  if (wert == null) return "–";
  return wert < 1000 ? `${wert} ms` : `${(wert / 1000).toLocaleString("de-DE", { maximumFractionDigits: 1 })} s`;
}

function anteil(teil: number, ganz: number) {
  return ganz > 0 ? `${Math.round((teil * 100) / ganz)} %` : undefined;
}

export function McpTab() {
  const { data, isPending, isError, refetch, isFetching } = useQuery({
    queryKey: ["admin", "mcp"],
    queryFn: () => api.get<AdminMcp>("/admin/stats/mcp?days=30"),
  });
  if (isPending) return <ChartSkeleton />;
  if (isError || !data) {
    return <ErrorState title="Die MCP-Zahlen konnten nicht geladen werden"
      onRetry={() => void refetch()} busy={isFetching} />;
  }
  const reihe = tageReihe(data.per_day, data.days);

  return (
    <div className="space-y-8">
      <section className="space-y-3">
        <AbschnittKopf titel="Wird der MCP-Server benutzt?">
          Die letzten {data.days} Tage, jeder Werkzeugaufruf gezählt. Eine Sitzung ist eine Folge
          von Aufrufen derselben Verbindung ohne Pause über 30 Minuten.
        </AbschnittKopf>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Zahl label="Aufrufe" n={data.calls} note={`Median ${ms(data.p50_ms)}`} />
          <Zahl label="Konten" n={data.accounts} />
          <Zahl label="Sitzungen" n={data.sessions}
            note={data.calls_per_session != null ? `Median ${data.calls_per_session} Aufrufe` : undefined} />
          <Zahl label="Fehler" n={data.errors} note={anteil(data.errors, data.calls)} />
        </div>
        {data.calls > 0 && (
          <div className="rounded-xl border border-border bg-card p-3">
            <AreaSparkline values={reihe.werte} days={reihe.tage} axisTicks={6} height={90} />
          </div>
        )}
      </section>

      <section className="space-y-3">
        <AbschnittKopf titel="Welche Werkzeuge, in welcher Reihenfolge">
          „Ohne Treffer" heißt: Die Antwort war eine leere Liste. Die Abfolgen zählen Schritte
          innerhalb einer Sitzung — die Anleitung schlägt drei Wege vor, hier steht, welche
          die Agenten wirklich gehen.
        </AbschnittKopf>
        {data.tools.length === 0
          ? <p className="text-hinweis text-muted-foreground">Noch kein Aufruf.</p>
          : (
            <div className="overflow-x-auto rounded-xl border border-border bg-card">
              <table className="w-full min-w-[480px] text-[13px]">
                <thead>
                  <tr className="border-b border-border text-left font-mono text-[10px] uppercase tracking-[0.1em] text-muted-foreground">
                    <th className="px-3 py-2 font-medium">Werkzeug</th>
                    <th className="px-3 py-2 text-right font-medium">Aufrufe</th>
                    <th className="px-3 py-2 text-right font-medium">ohne Treffer</th>
                    <th className="px-3 py-2 text-right font-medium">Fehler</th>
                    <th className="px-3 py-2 text-right font-medium">Median</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {data.tools.map((t) => (
                    <tr key={t.key}>
                      <td className="px-3 py-2 font-mono text-[12px] text-foreground">{t.key}</td>
                      <td className="px-3 py-2 text-right tabular-nums">{t.n.toLocaleString("de-DE")}</td>
                      <td className="px-3 py-2 text-right tabular-nums text-muted-foreground">{t.empty || "–"}</td>
                      <td className="px-3 py-2 text-right tabular-nums text-muted-foreground">{t.errors || "–"}</td>
                      <td className="px-3 py-2 text-right tabular-nums text-muted-foreground">{ms(t.p50_ms)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        <div className="grid gap-4 sm:grid-cols-3">
          <Liste titel="Einstieg einer Sitzung" zeilen={data.entries} />
          <Liste titel="Schritte" zeilen={data.transitions} />
          <Liste titel="Gesetzte Argumente" zeilen={data.arguments} />
        </div>
      </section>

      <section className="space-y-3">
        <AbschnittKopf titel="Wonach Agenten suchen"
          rechts={data.searches > 0 ? `${anteil(data.empty_searches, data.searches)} der Suchen ohne Treffer` : undefined}>
          Der Suchtext von <code>search_decisions</code>, gekürzt und ohne Kontaktdaten; nach 90
          Tagen gelöscht. Die rechte Liste ist die Arbeitsliste: Dort fehlt ein Wort im Index
          oder ein Synonym.
        </AbschnittKopf>
        <div className="grid gap-4 sm:grid-cols-2">
          <Suchen titel="Häufigste Suchen" zeilen={data.queries} />
          <Suchen titel="Ohne Treffer" zeilen={data.empty_queries} leer="Jede Suche hat etwas gefunden." />
        </div>
      </section>

      <section className="space-y-3">
        <AbschnittKopf titel="Wer und womit">
          Agent ist der Name des Schlüssels bzw. der, den sich ein OAuth-Client selbst gibt.
        </AbschnittKopf>
        <div className="grid gap-4 sm:grid-cols-[1fr_2fr]">
          <Liste titel="Agenten" zeilen={data.clients} />
          <div className="rounded-xl border border-border bg-card p-3">
            <p className="font-mono text-[10px] uppercase tracking-[0.11em] text-muted-foreground">Konten</p>
            {data.accounts_list.length === 0
              ? <p className="mt-2 text-hinweis text-muted-foreground">Noch nichts.</p>
              : (
                <ul className="mt-2 divide-y divide-border">
                  {data.accounts_list.map((k) => (
                    <li key={k.owner_id} className="flex items-baseline gap-3 py-1.5">
                      <span className="min-w-0 flex-1 truncate text-[13px] text-foreground">
                        {k.display_name || k.email || `Konto ${k.owner_id}`}
                        <span className="ml-2 text-meta text-muted-foreground">{k.clients.join(", ")}</span>
                      </span>
                      <span className="shrink-0 font-mono text-meta tabular-nums text-muted-foreground">
                        {k.n.toLocaleString("de-DE")} · {new Date(k.last).toLocaleDateString("de-DE", { day: "numeric", month: "short" })}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
          </div>
        </div>
      </section>
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
    <div className="min-w-0 rounded-xl border border-border bg-card p-3">
      <p className="font-mono text-[10px] uppercase tracking-[0.11em] text-muted-foreground">{titel}</p>
      {zeilen.length === 0
        ? <p className="mt-2 text-hinweis text-muted-foreground">Noch nichts.</p>
        : (
          <ul className="mt-2 space-y-1.5">
            {zeilen.map((z) => (
              <li key={z.key}>
                <div className="flex items-baseline justify-between gap-2">
                  <span className="min-w-0 truncate font-mono text-[11.5px] text-foreground" title={z.key}>{z.key}</span>
                  <span className="shrink-0 font-mono text-[11.5px] tabular-nums text-muted-foreground">{z.n}</span>
                </div>
                <div className="mt-0.5 h-[5px] overflow-hidden rounded-full bg-muted">
                  <span className="block h-full rounded-full bg-primary"
                    style={{ width: `${Math.max(4, (z.n / max) * 100)}%` }} />
                </div>
              </li>
            ))}
          </ul>
        )}
    </div>
  );
}

function Suchen({ titel, zeilen, leer = "Noch keine Suche." }: {
  titel: string; zeilen: AdminMcp["queries"]; leer?: string;
}) {
  return (
    <div className="min-w-0 rounded-xl border border-border bg-card p-3">
      <p className="font-mono text-[10px] uppercase tracking-[0.11em] text-muted-foreground">{titel}</p>
      {zeilen.length === 0
        ? <p className="mt-2 text-hinweis text-muted-foreground">{leer}</p>
        : (
          <ul className="mt-2 divide-y divide-border">
            {zeilen.map((q) => (
              <li key={q.query} className="flex items-baseline gap-3 py-1.5">
                <span className="min-w-0 flex-1 break-words text-[13px] text-foreground">{q.query}</span>
                <span className="shrink-0 font-mono text-meta tabular-nums text-muted-foreground">{q.n}×</span>
              </li>
            ))}
          </ul>
        )}
    </div>
  );
}
