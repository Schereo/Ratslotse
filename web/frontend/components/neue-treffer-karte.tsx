"use client";

import { useState } from "react";
import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, Check, CheckCheck, Tag } from "lucide-react";
import { api } from "@/lib/api";
import { vertrag, type ApiAntwort } from "@/lib/vertrag";
import { Button, formatDate } from "@/components/ui";
import { HeuteWidget } from "@/components/heute-widget";
import { OUTCOME_META } from "@/components/decision-ui";
import { shortCommittee } from "@/lib/committees";
import { decisionHref } from "@/lib/routes";

/** Eigenes Widget mit eigener Abfrage: Auch ohne andere Heute-Daten nutzbar.
 * Ausblenden braucht später nur das Entfernen dieses Bausteins aus dem Raster. */
export function NeueTrefferKarte() {
  const qc = useQueryClient();
  const [marking, setMarking] = useState<number | null>(null);
  const [markError, setMarkError] = useState<string | null>(null);
  const hitsQuery = useQuery({
    queryKey: ["topic-latest-hits", "unread"],
    queryFn: () => vertrag.get("/topics/latest-hits?limit=3&unread_only=true"),
  });
  const data = hitsQuery.data;
  const hits = data?.hits ?? [];

  async function gelesen(id: number, focus = false) {
    setMarking(id);
    setMarkError(null);
    try {
      // Ein Beschluss kann zu mehreren Themen passen. Alle eigenen Treffer
      // dieses Beschlusses werden zusammen markiert, fremde bleiben unberührt.
      await api.post(`/topics/decisions/${id}/seen`, {});
      await qc.cancelQueries({ queryKey: ["topic-latest-hits"] });
      // Bestätigte Marken bleiben auch bei einem anschließenden Funkloch
      // erhalten. Erst das Nachladen füllt den frei gewordenen Platz auf.
      qc.setQueryData<ApiAntwort<"/topics/latest-hits">>(["topic-latest-hits", "unread"], previous => {
        if (!previous?.hits.some(h => h.id === id)) return previous;
        return { ...previous, hits: previous.hits.filter(h => h.id !== id), unread_decisions: Math.max(0, previous.unread_decisions - 1) };
      });
      await Promise.all([
        qc.invalidateQueries({ queryKey: ["topic-latest-hits"] }),
        qc.invalidateQueries({ queryKey: ["topics"] }),
        qc.invalidateQueries({ queryKey: ["topics-unread"] }),
      ]);
      if (focus) document.getElementById("themen-neuigkeiten-title")?.focus();
    } catch {
      setMarkError("Der Gelesen-Status konnte nicht gespeichert werden. Versuche es erneut.");
    } finally {
      setMarking(null);
    }
  }

  return (
    <HeuteWidget id="themen-neuigkeiten" title="Neu zu deinen Themen" icon={<Tag className="h-5 w-5" />}
      footer={data && data.topic_count > 0 ? (
        <Link href="/topics" className="inline-flex min-h-11 items-center gap-2 text-sm font-medium text-primary hover:underline">
          Meine Themen <ArrowRight className="h-4 w-4" aria-hidden />
        </Link>
      ) : undefined}
    >
      {hitsQuery.isPending && (
        <div role="status" className="space-y-3">
          <span className="sr-only">Deine Neuigkeiten werden geladen.</span>
          {[0, 1].map(i => <div key={i} aria-hidden className="h-24 animate-pulse rounded-lg bg-muted motion-reduce:animate-none" />)}
        </div>
      )}
      {hitsQuery.isError && (
        <div role="alert" className="mb-3 text-hinweis text-muted-foreground">
          <p>{data ? "Deine Neuigkeiten konnten nicht aktualisiert werden." : "Deine Neuigkeiten konnten nicht geladen werden."}</p>
          <Button variant="ghost" className="mt-1 min-h-11" onClick={() => hitsQuery.refetch()} disabled={hitsQuery.isFetching}>
            Erneut versuchen
          </Button>
        </div>
      )}
      {data && (
        <>
          {hits.length > 0 ? (
            <>
              <p className="text-hinweis text-muted-foreground" role="status">
                <span className="font-semibold text-foreground">{hits.length < data.unread_decisions ? `${hits.length} von ${data.unread_decisions}` : data.unread_decisions} ungelesen</span>
                {" · "}{data.topic_count} {data.topic_count === 1 ? "Thema" : "Themen"}
              </p>
              <ul className="mt-1 divide-y divide-border/60">
                {hits.map(h => (
                  <li key={h.id} className="py-3 first:pt-2 last:pb-0">
                    <Link href={decisionHref(h.id)} onClick={() => { void gelesen(h.id); }}
                      className="-mx-1 block rounded-lg px-1 py-1 transition-colors hover:bg-accent/60 focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary"
                    >
                      <p className="text-meta text-primary [overflow-wrap:anywhere]">Zu deinem Thema <span className="font-semibold">{h.topic_name}</span></p>
                      <h3 className="mt-1 line-clamp-2 text-quelle font-semibold text-foreground [overflow-wrap:anywhere]">{h.title}</h3>
                      {h.summary && <p className="mt-1 line-clamp-2 text-hinweis text-muted-foreground">{h.summary}</p>}
                    </Link>
                    <div className="mt-1 flex flex-wrap items-center justify-between gap-x-2">
                      <p className="min-w-0 text-meta text-muted-foreground [overflow-wrap:anywhere]">
                        {h.outcome && OUTCOME_META[h.outcome] ? `${OUTCOME_META[h.outcome].label} · ` : ""}
                        {formatDate(h.session_date)} · {shortCommittee(h.committee)}
                      </p>
                      <Button variant="ghost" size="sm" className="-mr-2 ml-auto h-auto min-h-11 gap-1.5 whitespace-normal py-2 text-right text-meta text-muted-foreground [&>svg]:shrink-0"
                        aria-label={`Als gelesen markieren: ${h.title}`} disabled={marking !== null} onClick={() => { void gelesen(h.id, true); }}>
                        <Check className="h-4 w-4" aria-hidden /> {marking === h.id ? "Wird gespeichert…" : "Als gelesen markieren"}
                      </Button>
                    </div>
                  </li>
                ))}
              </ul>
            </>
          ) : data.topic_count === 0 ? (
            <div className="space-y-2">
              <p className="text-quelle font-semibold">Was interessiert dich in Oldenburg?</p>
              <p className="text-hinweis text-muted-foreground">Lege ein Thema an. Passende Beschlüsse findest du dann hier.</p>
              <Button asChild className="h-auto min-h-11 whitespace-normal py-2"><Link href="/topics">Erstes Thema anlegen</Link></Button>
            </div>
          ) : (
            <div className="flex items-start gap-3" role="status">
              <CheckCheck className="mt-1 h-5 w-5 shrink-0 text-primary" aria-hidden />
              <div>
                <p className="text-quelle font-semibold">{data.unread_decisions > 0 ? "Weitere Treffer in deinen Themen" : data.total > 0 ? "Alles gelesen" : "Noch keine passenden Beschlüsse"}</p>
                <p className="mt-1 text-hinweis text-muted-foreground">{data.unread_decisions > 0
                  ? "Öffne deine Themen, um die übrigen ungelesenen Treffer zu sehen."
                  : data.total > 0
                  ? "Sobald neue Treffer zu deinen Themen dazukommen, stehen sie hier."
                  : "Hier erscheinen neue Treffer zu deinen Themen, sobald welche vorliegen."}</p>
              </div>
            </div>
          )}
          {markError && <p role="alert" className="mt-3 text-hinweis text-destructive">{markError}</p>}
        </>
      )}
    </HeuteWidget>
  );
}
