"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell, ExternalLink, X } from "lucide-react";
import { api } from "@/lib/api";
import { Card, formatDate, toast } from "@/components/ui";
import { shortCommittee } from "@/lib/committees";

type Station = {
  date: string | null;
  committee: string;
  result: string | null;
};

type Follow = {
  id: number;
  kvonr: number;
  template_number: string;
  title: string;
  created_at: string;
  notified_at: string | null;
  url: string;
  n_stationen: number;
  naechste: Station | null;
  letzte: Station | null;
};

/** Eine Station als eine Zeile: „Verkehrsausschuss · 13.08.2026 · angenommen". */
function stationLine(s: Station): string {
  return [shortCommittee(s.committee), s.date ? formatDate(s.date) : null, s.result]
    .filter(Boolean)
    .join(" · ");
}

/**
 * „Verfolgte Vorgänge" auf Meine Themen (Design 28a/W1).
 *
 * Zeigt je Vorgang den letzten und den nächsten Halt — die zwei Angaben, für
 * die man das Abo überhaupt abgeschlossen hat. Ohne Follows rendert der
 * Abschnitt nichts: Ein leerer Kasten mit Erklärtext stünde hier dauerhaft im
 * Weg, angelegt wird ein Follow ohnehin auf der Beschluss-Seite.
 */
export function FollowedVorgaenge() {
  const qc = useQueryClient();
  const { data } = useQuery({
    queryKey: ["vorlage-follows"],
    queryFn: () => api.get<{ follows: Follow[] }>("/council/follows").then((d) => d.follows),
  });

  const unfollow = useMutation({
    mutationFn: (kvonr: number) => api.del(`/council/template/${kvonr}/follow`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["vorlage-follows"] });
      toast.success("Vorgang wird nicht mehr verfolgt.");
    },
    onError: () => toast.error("Hat nicht geklappt."),
  });

  const follows = data ?? [];
  if (follows.length === 0) return null;

  return (
    <>
      <h2 className="mt-10 flex items-center gap-2 text-lg font-bold text-foreground">
        <Bell className="h-4 w-4 text-primary" /> Verfolgte Vorgänge
      </h2>
      <p className="mt-1 text-sm text-muted-foreground">
        Eine Meldung, sobald eine dieser Vorlagen in einem Gremium weiterberaten wird.
      </p>
      <Card className="mt-3 divide-y divide-border p-0">
        {follows.map((f) => (
          <div key={f.id} className="flex items-start justify-between gap-3 p-4">
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium text-foreground">{f.title || f.template_number}</p>
              <p className="mt-0.5 text-xs text-muted-foreground">
                {f.template_number && <span className="font-mono">{f.template_number}</span>}
                {f.template_number && " · "}
                {f.n_stationen} {f.n_stationen === 1 ? "Station" : "Stationen"}
              </p>
              <dl className="mt-2 space-y-0.5 text-xs">
                {f.letzte && (
                  <div className="flex gap-1.5">
                    <dt className="shrink-0 text-muted-foreground">Zuletzt:</dt>
                    <dd className="min-w-0 text-foreground">{stationLine(f.letzte)}</dd>
                  </div>
                )}
                <div className="flex gap-1.5">
                  <dt className="shrink-0 text-muted-foreground">Als Nächstes:</dt>
                  <dd className="min-w-0 text-foreground">
                    {f.naechste ? stationLine(f.naechste) : "kein Termin veröffentlicht"}
                  </dd>
                </div>
              </dl>
              <a
                href={f.url}
                target="_blank"
                rel="noreferrer"
                className="mt-2 inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
              >
                Vorlage im Ratsinfo <ExternalLink className="h-3 w-3" />
              </a>
            </div>
            <button
              type="button"
              onClick={() => unfollow.mutate(f.kvonr)}
              disabled={unfollow.isPending}
              aria-label={`„${f.title || f.template_number}" nicht mehr verfolgen`}
              className="shrink-0 rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        ))}
      </Card>
    </>
  );
}
