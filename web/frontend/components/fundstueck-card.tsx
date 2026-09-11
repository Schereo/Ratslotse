"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Lightbulb } from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui";
import { OutcomeDot, voteLabel } from "@/components/decision-ui";
import { ShareButton } from "@/components/share-button";
import { decisionHref } from "@/lib/routes";
import { HeuteWidget, type WidgetSize } from "@/components/heute-widget";
import { cn } from "@/lib/utils";
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
export function FundstueckCard({ size }: { size?: WidgetSize }) {
  const { data } = useQuery({
    queryKey: ["fundstueck"],
    queryFn: () => api.get<Fundstueck>("/council/daily-find"),
    staleTime: 60 * 60 * 1000, // wechselt einmal täglich
  });
  if (!data?.found) return null;

  return (
    <HeuteWidget id="fundstueck" title="Fundstück des Tages" icon={Lightbulb} size={size}
      footer={<div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <Button size="sm" asChild>
          <Link href={decisionHref(data.decision_id)}>Zum Beschluss <ArrowRight className="!size-3.5" /></Link>
        </Button>
        <ShareButton path={decisionHref(data.decision_id)} title={`${data.kicker}: ${data.story}`} />
        <span className="ml-auto text-meta text-muted-foreground">Morgen wartet ein neues Fundstück</span>
      </div>}>
      {detail => <>
        <p className="text-meta text-muted-foreground">{data.kicker}</p>
        <p className={cn("mt-2 max-w-3xl text-quelle font-semibold text-foreground", detail === "compact" && "line-clamp-3")}>{data.story}</p>
        <div className="mt-3 flex flex-wrap items-center gap-x-2.5 gap-y-1 text-meta text-muted-foreground">
          <OutcomeDot outcome={data.outcome} />
          <span>
            {detail !== "compact" && `${data.committee} · `}{fmtDate(data.session_date)}
            {detail === "expanded" && data.vote && ` · ${voteLabel(data.vote)}`}
          </span>
        </div>
      </>}
    </HeuteWidget>
  );
}
