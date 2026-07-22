"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight } from "lucide-react";
import { api } from "@/lib/api";
import { Button, Card } from "@/components/ui";
import { OutcomeDot } from "@/components/decision-ui";
import { ShareButton } from "@/components/share-button";
import { decisionHref } from "@/lib/routes";
import type { DecisionOutcome } from "@/lib/types";

type Fundstueck =
  | { found: false }
  | {
      found: true;
      kicker: string;
      story: string;
      decision_id: number;
      title: string;
      outcome: DecisionOutcome;
      vote: string | null;
      committee: string;
      session_date: string;
    };

const fmtDate = (iso: string) => new Date(iso + "T12:00:00").toLocaleDateString("de-DE");

/**
 * RL-U11 (Design 10a/11a): „Fundstück des Tages" — der tägliche Öffnungsgrund
 * auf der Übersicht, nach dem Karten-Grid. Kuratiert von der Interest-Pipeline
 * (Jahrestage zuerst); ohne freigegebenes Fundstück entfällt die Karte
 * ersatzlos. Ein Fund pro Tag, morgen wartet der nächste.
 */
export function FundstueckCard() {
  const { data } = useQuery({
    queryKey: ["fundstueck"],
    queryFn: () => api.get<Fundstueck>("/council/fundstueck"),
    staleTime: 60 * 60 * 1000, // wechselt einmal täglich
  });
  if (!data?.found) return null;

  return (
    <Card className="mt-6 border-primary/20 bg-gradient-to-br from-primary/[0.05] to-transparent p-5">
      <p className="font-mono text-[11px] font-medium uppercase tracking-[0.14em] text-primary">
        Fundstück · {data.kicker}
      </p>
      <p className="mt-2 max-w-3xl text-balance font-display text-lg font-bold leading-snug text-foreground">
        {data.story}
      </p>
      <div className="mt-2.5 flex flex-wrap items-center gap-x-2.5 gap-y-1 text-xs text-muted-foreground">
        <OutcomeDot outcome={data.outcome} />
        <span>
          {data.committee} · {fmtDate(data.session_date)}
          {data.vote && ` · ${data.vote}`}
        </span>
      </div>
      <div className="mt-3.5 flex flex-wrap items-center gap-x-2.5 gap-y-2">
        <Button size="sm" asChild>
          <Link href={decisionHref(data.decision_id)}>
            Zum Beschluss <ArrowRight className="!size-3.5" />
          </Link>
        </Button>
        <ShareButton path={decisionHref(data.decision_id)} title={`${data.kicker}: ${data.story}`} />
        <span className="ml-auto text-[11px] text-muted-foreground">
          Morgen wartet ein neues Fundstück
        </span>
      </div>
    </Card>
  );
}
