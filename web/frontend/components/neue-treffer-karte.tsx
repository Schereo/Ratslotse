"use client";

import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight } from "lucide-react";
import { api } from "@/lib/api";
import { vertrag, type ApiAntwort } from "@/lib/vertrag";
import type { DecisionOutcome } from "@/lib/types";
import { Button, Card, formatDate } from "@/components/ui";
import { Mascot } from "@/components/mascot";
import { OutcomeBadge, OutcomeDot } from "@/components/decision-ui";
import { shortCommittee } from "@/lib/committees";
import { decisionHref } from "@/lib/routes";
import { cn } from "@/lib/utils";

type Treffer = ApiAntwort<"/topics/latest-hits">["hits"][number];

// Aus dem API-Vertrag statt von Hand — `found` unterscheidet die Fälle.
//
// Einzige Abweichung: `outcome` steht im Vertrag als `string`, nicht als Union.
// Die Spalte wird vom LLM befüllt; eine Verengung im Backend hieße, dass ein
// unerwarteter Wert die Antwort mit 500 abbricht statt nur ein Etikett
// unbeschriftet zu lassen. Die Oberfläche darf enger sehen als der Vertrag.
type DieseWocheRoh = ApiAntwort<"/council/diese-woche">;
type DieseWoche =
  | Extract<DieseWocheRoh, { found: false }>
  | (Omit<Extract<DieseWocheRoh, { found: true }>, "outcome"> & { outcome: DecisionOutcome | null });

/**
 * „Neu zu deinen Themen" auf dem Heute-Briefing — der Rückblick auf das,
 * was der Rat zu den eigenen Themen entschieden hat.
 *
 * Bis 09/2026 stand hier je Treffer eine Themen-Pille, der rohe RIS-Titel und
 * „Gremium · vor 3 Wochen" — zweimal dieselbe Pille untereinander, kein
 * Ergebnis, kein Satz dazu, und die Karte sagte trotz ihres Namens nicht,
 * was daran neu war (Tims Befund 06.09.2026: „ziemlich hässlich"). Jetzt hat
 * jede Zeile dieselbe Anatomie wie die Themen-Karte auf „Meine Themen":
 * Punkt für ungelesen, Titel, der Satz aus der Zusammenfassung (WAS wurde
 * entschieden), Mono-Zeile mit Datum · Gremium · Thema — und rechts das
 * Ergebnis als Badge (kurze, gedeckelte Liste, DESIGNSPRACHE § 5). Der
 * Kicker rechts im Kopf nennt ehrlich, was hinter der Auswahl steht.
 */
export function NeueTrefferKarte({ topicCount, topicsLaden }: {
  /** Zahl der eigenen Themen — steuert die Leerzustände. */
  topicCount: number;
  /** Solange die Themen noch laden, bleibt der „Erstes Thema"-Zustand aus. */
  topicsLaden: boolean;
}) {
  const qc = useQueryClient();
  const hitsQuery = useQuery({
    queryKey: ["topic-latest-hits"],
    // Drei statt zwei: Mit Ergebnis und Satz trägt jede Zeile jetzt genug,
    // dass drei die Karte füllen, ohne sie zu strecken — und der dritte
    // Treffer ist bei mehreren Themen oft der aus dem zweiten Thema.
    queryFn: () => vertrag.get("/topics/latest-hits?limit=3"),
  });
  const hits = hitsQuery.data?.hits ?? [];

  // RL-U15 (13a-A): Ersatz für den Treffer-Leerzustand — nur laden, wenn er
  // gebraucht würde (Themen vorhanden, aber keine Treffer).
  const wocheQuery = useQuery({
    queryKey: ["diese-woche"],
    queryFn: () => api.get<DieseWoche>("/council/diese-woche"),
    enabled: !hitsQuery.isLoading && hits.length === 0 && topicCount > 0,
    staleTime: 60 * 60 * 1000,
  });
  const woche = wocheQuery.data?.found ? wocheQuery.data : null;

  /* Wer einen Treffer öffnet, hat genau den gelesen — dieselbe Regel wie auf
     der Themen-Karte (RL-903). Fire-and-forget: Ein Fehler darf den
     Seitenwechsel nicht aufhalten; beim nächsten Laden steht der Punkt dann
     eben noch. */
  const gelesen = (h: Treffer) => {
    if (!h.is_new) return;
    api.post(`/topics/${h.topic_id}/seen`, { decision_id: h.id }).then(() => {
      qc.invalidateQueries({ queryKey: ["topic-latest-hits"] });
      qc.invalidateQueries({ queryKey: ["topics"] });
      qc.invalidateQueries({ queryKey: ["topics-unread"] });
    }).catch(() => {});
  };

  const neu = hitsQuery.data?.unread_total ?? 0;
  const themen = hitsQuery.data?.topic_count ?? 0;
  const gesamt = hitsQuery.data?.total ?? 0;
  // Ehrliche Mengen (DESIGNSPRACHE § 6): Was hinter den drei Zeilen steht.
  const kicker = gesamt > 0 ? `${themen} ${themen === 1 ? "Thema" : "Themen"} · ${gesamt} Treffer` : "";

  return (
    <Card className="flex flex-col p-5">
      {/* `flex-wrap` + `ml-auto` am Kicker: Auf dem Telefon (318 px Innenraum)
          passen Titel, Abzeichen und Kicker nicht in eine Zeile — der Titel
          brach dann in drei Zeilen um, während der Kicker rechts stehen
          blieb. Jetzt bleibt der Titel ganz, der Kicker rückt darunter. */}
      <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
        <div className="flex items-center gap-2">
          <h2 className="whitespace-nowrap font-display text-base font-bold text-foreground">Neu zu deinen Themen</h2>
          {/* Dasselbe Abzeichen wie auf der Themen-Karte — dort räumt es sich
              per Klick weg, hier sagt es nur, wie viel ungelesen ist; gelesen
              wird über die Zeilen. */}
          {neu > 0 && (
            <span className="inline-flex shrink-0 items-center gap-1.5 rounded-full bg-signal/[0.12] px-2 py-0.5 text-[11px] font-semibold text-signal">
              <span className="h-1.5 w-1.5 rounded-full bg-signal" aria-hidden />
              {neu} {neu === 1 ? "neuer" : "neue"}
            </span>
          )}
        </div>
        {kicker && (
          <span className="ml-auto shrink-0 font-mono text-[10px] uppercase tracking-[0.1em] text-muted-foreground">
            {kicker}
          </span>
        )}
      </div>

      <ul className="mt-2 flex-1">
        {hits.map((h, i) => (
          <li key={h.id} className={cn(i > 0 && "border-t border-border/60")}>
            <Link
              href={decisionHref(h.id)}
              onClick={() => gelesen(h)}
              className="-mx-2 block rounded-lg px-2 py-2.5 transition-colors hover:bg-accent/60"
            >
              {/* Das Badge steht NEBEN dem Titel, nicht neben der ganzen Zeile:
                  Als Spalte über die volle Höhe nahm es Satz und Mono-Zeile
                  110 px Breite weg — auf dem Telefon brach der Satz in vier
                  Zeilen und das Thema wurde zu „KIT…". */}
              <span className="flex items-start justify-between gap-3">
                <span className="flex min-w-0 items-start gap-1.5">
                  {h.is_new && <span className="mt-[6px] h-1.5 w-1.5 shrink-0 rounded-full bg-signal" aria-label="neu" />}
                  <span className={cn(
                    "line-clamp-2 text-[13.5px] leading-snug text-foreground",
                    h.is_new ? "font-semibold" : "font-medium",
                  )}>
                    {h.title}
                  </span>
                </span>
                <OutcomeBadge outcome={h.outcome} />
              </span>
              {/* WAS entschieden wurde, in einem Satz — der RIS-Titel sagt
                  das nicht („… - Bericht"). Dieselbe Zeile wie das `sub`
                  der Beschluss-Karten in Suche und Themenfeld. */}
              {h.summary && (
                <span className="mt-1 line-clamp-2 block text-[12.5px] leading-relaxed text-muted-foreground">
                  {h.summary}
                </span>
              )}
              <span className="mt-1.5 block truncate font-mono text-[10px] uppercase tracking-[0.08em] text-muted-foreground">
                {formatDate(h.session_date)} · {shortCommittee(h.committee)} ·{" "}
                <span className="font-semibold text-primary">{h.topic_name}</span>
              </span>
            </Link>
          </li>
        ))}

        {/* Skelett nur, solange nichts dasteht, was stehen bleiben könnte
            (DESIGNSPRACHE § 7) — zwei Zeilen in der Höhe echter Treffer,
            damit die Karte beim Eintreffen nicht springt. */}
        {hitsQuery.isLoading && topicCount > 0 && [0, 1].map((i) => (
          <li key={i} className={cn("py-2.5", i > 0 && "border-t border-border/60")} aria-hidden>
            <div className="h-3.5 w-4/5 animate-pulse rounded bg-muted" />
            <div className="mt-2 h-3 w-full animate-pulse rounded bg-muted/70" />
            <div className="mt-2 h-2.5 w-2/5 animate-pulse rounded bg-muted/70" />
          </li>
        ))}

        {!hitsQuery.isLoading && hits.length === 0 && topicCount > 0 && (
          woche ? (
            /* RL-U15 (13a-A): der interessanteste Beschluss der Woche statt
               des leeren Texts — „Warum spannend" ist wörtlich der
               interest_reason der Bewertungs-Pipeline. */
            <li>
              <Link href={decisionHref(woche.decision_id)} className="-mx-2 block rounded-lg px-2 py-2.5 transition-colors hover:bg-accent/60">
                <span className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.08em] text-muted-foreground">
                  <OutcomeDot outcome={woche.outcome} /> {shortCommittee(woche.committee)}
                </span>
                <p className="mt-1 line-clamp-2 text-[13.5px] font-medium leading-snug text-foreground">{woche.title}</p>
                {woche.interest_reason && (
                  <p className="mt-1 text-[12.5px] leading-relaxed text-muted-foreground">
                    <span className="font-semibold text-signal">Warum spannend:</span> {woche.interest_reason}
                  </p>
                )}
                <span className="mt-1.5 inline-flex items-center gap-1 text-[13px] font-medium text-primary">
                  Zum Beschluss <ArrowRight className="h-3.5 w-3.5" />
                </span>
              </Link>
            </li>
          ) : (
            <li className="py-2 text-sm leading-relaxed text-muted-foreground">
              Noch keine Treffer — sobald der Rat zu deinen Themen entscheidet, steht es hier.
            </li>
          )
        )}

        {!topicsLaden && topicCount === 0 && (
          /* Leerzustand 4a: gestrichelte Lotti-Karte „Erstes Thema anlegen". */
          <li className="mt-1 flex flex-col items-center gap-2 rounded-xl border-2 border-dashed border-border px-4 py-5 text-center">
            <Mascot pose="point" decorative className="h-12 w-12" />
            <p className="text-sm text-muted-foreground">
              Lege dein erstes Thema an und werde benachrichtigt, sobald der Rat dazu entscheidet.
            </p>
            <Button size="sm" asChild>
              <Link href="/topics">Erstes Thema anlegen</Link>
            </Button>
          </li>
        )}
      </ul>

      {topicCount > 0 && (
        <div className="mt-2 border-t border-border/60 pt-3">
          <Link href="/topics" className="inline-flex items-center gap-1 text-[13px] font-medium text-primary hover:underline">
            Meine Themen <ArrowRight className="h-3.5 w-3.5" />
          </Link>
        </div>
      )}
    </Card>
  );
}
