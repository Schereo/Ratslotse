"use client";

/**
 * „Anderswo beschlossen" — was andere Städte zu derselben Sache gemacht haben.
 *
 * Die Karten führen aus dem Haus heraus (ins Ratsinformationssystem der
 * jeweiligen Stadt), deshalb kein `DecisionLinkCard`: Der Chevron dort
 * verspricht eine Detailseite bei uns. Externe Ziele öffnen in einem neuen Tab
 * und sagen das über das Symbol.
 *
 * **Kein Ranking, keine Prozentzahl.** Die Nähe ist ein Rechenwert, keine
 * Aussage über Qualität — sie sortiert und bleibt sonst unsichtbar
 * (Ausnahme: der Titel für den, der sie wissen will).
 */
import { ArrowUpRight, Building2 } from "lucide-react";

import { Card } from "@/components/ui/card";
import { api } from "@/lib/api";
import { useFeature } from "@/lib/features";
import type { ApiAntwort } from "@/lib/vertrag";
import { useQuery } from "@tanstack/react-query";

type Antwort = ApiAntwort<"/council/decision/{decision_id}/elsewhere">;
type Eintrag = Antwort["items"][number];

/** Kanonische Ergebnisse aus `council/cities/model.py`. */
const ERGEBNIS: Record<string, string> = {
  accepted: "beschlossen",
  amended: "geändert beschlossen",
  rejected: "abgelehnt",
  postponed: "vertagt",
  noted: "zur Kenntnis",
  referred: "verwiesen",
  withdrawn: "zurückgezogen",
};

/** Vorlagenarten — kurz, weil sie neben Stadt und Datum stehen. */
const ART: Record<string, string> = {
  motion: "Antrag",
  amendment: "Änderungsantrag",
  inquiry: "Anfrage",
  answer: "Antwort",
  proposal: "Beschlussvorlage",
  report: "Bericht",
  notice: "Mitteilung",
  petition: "Eingabe",
};

function datum(iso: string | null): string {
  if (!iso) return "";
  const [j, m, t] = iso.slice(0, 10).split("-");
  return `${t}.${m}.${j}`;
}

function Eintragskarte({ item }: { item: Eintrag }) {
  const ergebnis = ERGEBNIS[item.outcome];
  // Nicht jede Stadt veröffentlicht eine Ansichtsseite zur Vorlage — Münster
  // liefert über OParl nur die API-Adresse. Ohne Ziel gibt es dann auch keinen
  // Anker, keine Zeigerhand und keinen Pfeil: Ein Link, der nichts öffnet,
  // ist schlimmer als gar keiner (Designsprache, „Zeigerhand nur mit Ziel").
  const inhalt = (
      <Card className={`group flex items-start gap-3 p-3${item.web ? " card-interactive" : ""}`}>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <span className="inline-flex items-center gap-1 text-xs font-semibold text-foreground">
              <Building2 className="h-3 w-3 text-muted-foreground" aria-hidden />
              {item.body_name}
            </span>
            <span className="text-xs text-muted-foreground">
              {[ART[item.kind] ?? item.paper_type_raw, datum(item.date)].filter(Boolean).join(" · ")}
            </span>
            {ergebnis && (
              // Anzeigetafel-Tönung, nie eine dunkle Karte im Hellmodus.
              <span className="rounded bg-muted px-1.5 text-xs font-medium text-muted-foreground">
                {ergebnis}
              </span>
            )}
            {item.originator && (
              <span className="text-xs text-muted-foreground/80">{item.originator}</span>
            )}
          </div>
          <p className="mt-1 text-sm font-medium text-foreground" title={`Nähe ${Math.round(item.score * 100)} %`}>
            {item.name}
          </p>
          {item.summary && (
            <p className="mt-0.5 line-clamp-2 text-xs leading-relaxed text-muted-foreground">
              {item.summary}
            </p>
          )}
        </div>
        {item.web && (
          <ArrowUpRight
            className="mt-0.5 h-4 w-4 shrink-0 self-center text-muted-foreground/40 group-hover:text-primary"
            aria-hidden
          />
        )}
      </Card>
  );
  if (!item.web) return inhalt;
  return (
    <a href={item.web} target="_blank" rel="noopener noreferrer" className="block">
      {inhalt}
    </a>
  );
}

export function Elsewhere({ decisionId }: { decisionId: number }) {
  const an = useFeature("andere-staedte");
  const { data } = useQuery({
    queryKey: ["elsewhere", decisionId],
    queryFn: () => api.get<Antwort>(`/council/decision/${decisionId}/elsewhere`),
    // Der Bestand ändert sich wöchentlich; ihn bei jedem Seitenwechsel neu zu
    // holen brächte niemandem etwas.
    staleTime: 60 * 60 * 1000,
    enabled: an,
  });

  // Ohne Treffer bleibt der Block ganz weg — eine Überschrift mit „keine
  // Ergebnisse" wäre eine Zeile, die nie jemand lesen will.
  if (!an || !data?.items.length) return null;

  return (
    <div className="mt-6">
      <h2 className="text-sm font-semibold text-muted-foreground">Anderswo beschlossen</h2>
      <p className="text-xs text-muted-foreground/70">
        Was {data.bodies.join(", ")} zu einer ähnlichen Sache beantragt oder beschlossen
        {" "}haben — aus den Ratsinformationssystemen dieser Städte.
      </p>
      <div className="mt-3 space-y-2">
        {data.items.map((item) => (
          <Eintragskarte key={item.paper_id} item={item} />
        ))}
      </div>
    </div>
  );
}
