"use client";

import { useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { EyeOff, Flag, RotateCcw, ThumbsUp } from "lucide-react";
import { api } from "@/lib/api";
import { karteHref } from "@/lib/routes";
import type { ApiAntwort } from "@/lib/vertrag";
import { Badge, Button, Card, ErrorState, Spinner, formatDateTime, toast } from "@/components/ui";
import { cn } from "@/lib/utils";

type Meldungen = ApiAntwort<"/admin/district-reports">;
type Gruppe = Meldungen["groups"][number];
type Status = "open" | "decided" | "all";

/** „Gehört nicht hierher" aus Mein Viertel: je Vorhaben die Meldungen samt
 *  Grund, und die Entscheidung. Erst „Ausblenden" nimmt ein Vorhaben von der
 *  Tafel — eine Meldung allein tut das seit 10/2026 nicht mehr. Jede
 *  Entscheidung ist umkehrbar. Wer gemeldet hat, steht bewusst nicht da. */
export function ViertelMeldungenTab() {
  const qc = useQueryClient();
  const [status, setStatus] = useState<Status>("open");
  const query = useQuery({
    queryKey: ["admin", "district-reports", status],
    queryFn: () => api.get<Meldungen>(`/admin/district-reports?status=${status}`),
  });
  const entscheiden = useMutation({
    mutationFn: ({ key, verdict }: { key: string; verdict: "hidden" | "kept" | null }) =>
      api.put(`/admin/district-reports/${encodeURIComponent(key)}`, { verdict }),
    onSuccess: (_d, { verdict }) => {
      toast.success(verdict === "hidden" ? "Ausgeblendet." : verdict === "kept" ? "Bleibt stehen." : "Wieder offen.");
      qc.invalidateQueries({ queryKey: ["admin", "district-reports"] });
      qc.invalidateQueries({ queryKey: ["viertel"] });
      qc.invalidateQueries({ queryKey: ["viertel-uebersicht"] });
    },
    onError: () => toast.error("Die Entscheidung ließ sich nicht speichern."),
  });

  if (query.isPending) return <Spinner />;
  if (query.isError) return <ErrorState title="Die Meldungen konnten nicht geladen werden"
    onRetry={() => void query.refetch()} busy={query.isFetching} />;
  const gruppen = query.data.groups;
  const reiter: [Status, string][] = [["open", `Offen (${query.data.open_count})`], ["decided", "Entschieden"], ["all", "Alle"]];

  return (
    <div className="space-y-4 [overflow-wrap:anywhere]">
      <p className="text-sm text-muted-foreground">
        Vorhaben aus „Mein Viertel", die jemand als falsch verortet gemeldet hat. Sie bleiben auf der Tafel, bis
        hier entschieden ist; die erste Meldung je Vorhaben kommt zusätzlich als Mail.
      </p>
      <div className="flex flex-wrap gap-1.5">
        {reiter.map(([value, label]) => (
          <button key={value} type="button" onClick={() => setStatus(value)}
            className={cn("min-h-9 rounded-full border px-3 py-1.5 text-xs font-medium",
              status === value ? "border-primary bg-primary/10 text-primary" : "border-border text-muted-foreground")}>
            {label}
          </button>
        ))}
      </div>
      {gruppen.length === 0 ? (
        <Card className="p-8 text-center text-sm text-muted-foreground">
          {status === "open" ? "Keine offenen Meldungen." : "Hier steht nichts."}
        </Card>
      ) : gruppen.map((g) => (
        <MeldungKarte key={g.project_key} g={g} busy={entscheiden.isPending}
          onEntscheiden={(verdict) => entscheiden.mutate({ key: g.project_key, verdict })} />
      ))}
    </div>
  );
}

function MeldungKarte({ g, busy, onEntscheiden }: {
  g: Gruppe; busy: boolean; onEntscheiden: (verdict: "hidden" | "kept" | null) => void;
}) {
  return (
    <Card className="p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">{g.place_name}</p>
          <p className="mt-0.5 font-semibold">
            {g.project ? (
              <Link href={karteHref(g.place_id, g.project.id)} className="hover:underline">{g.name}</Link>
            ) : g.name}
          </p>
          {g.project?.what && <p className="mt-1 text-sm text-muted-foreground">{g.project.what}</p>}
          {!g.project && <p className="mt-1 text-xs text-muted-foreground">Nicht mehr auf der Tafel — ein späterer Lauf kennt dieses Vorhaben nicht mehr.</p>}
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          <Badge color="slate"><Flag className="mr-1 inline h-3 w-3" />{g.count} {g.count === 1 ? "Meldung" : "Meldungen"}</Badge>
          {g.verdict === "hidden" && <Badge color="red">Ausgeblendet</Badge>}
          {g.verdict === "kept" && <Badge color="green">Passt</Badge>}
        </div>
      </div>
      <ul className="mt-3 space-y-1.5 border-t border-border pt-3 text-sm">
        {g.reports.map((m, i) => (
          <li key={i} className="flex flex-wrap gap-x-3 gap-y-0.5">
            <span className="text-xs tabular-nums text-muted-foreground">{formatDateTime(m.created_at)}</span>
            <span className={m.reason ? "text-foreground" : "italic text-muted-foreground"}>{m.reason ?? "ohne Grund"}</span>
          </li>
        ))}
      </ul>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        {g.verdict === null ? (
          <>
            <Button size="sm" variant="secondary" disabled={busy} onClick={() => onEntscheiden("kept")}>
              <ThumbsUp className="h-4 w-4" /> Passt doch
            </Button>
            {g.project && (
              <Button size="sm" disabled={busy} onClick={() => onEntscheiden("hidden")}>
                <EyeOff className="h-4 w-4" /> Ausblenden
              </Button>
            )}
          </>
        ) : (
          <>
            <span className="text-xs text-muted-foreground">Entschieden {g.decided_at ? formatDateTime(g.decided_at) : ""}</span>
            <Button size="sm" variant="secondary" disabled={busy} onClick={() => onEntscheiden(null)}>
              <RotateCcw className="h-4 w-4" /> Zurücknehmen
            </Button>
          </>
        )}
      </div>
    </Card>
  );
}
