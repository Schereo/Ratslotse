"use client";

import Link from "next/link";
import { Check } from "lucide-react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { CommitteeDetail } from "@/lib/types";
import { CardListSkeleton, ErrorState, PageHeader, formatDate, toast } from "@/components/ui";
import { wochentagKurz } from "@/lib/utils";
import { committeeExplains, committeeRank, shortCommittee } from "@/lib/committees";

/** Der Termin in zwei Längen — oder gar nicht.
 *
 *  Ohne Termin gibt es keine Zeile: Einen zu erfinden wäre schlimmer als
 *  keinen zu zeigen. Und ohne Uhrzeit bleibt es beim Datum; das Ratsinfo
 *  führt sie nicht immer.
 *
 *  Zwei Längen, weil die Zeile neben dem Knopf steht: Auf 390 px schnitt
 *  „MO 14.09.2026 · 17:00" genau die Uhrzeit ab — also die Angabe, für die
 *  die Zeile da ist. Kurz fällt das Jahr weg, das bei einem Termin in den
 *  nächsten Wochen ohnehin nichts beiträgt.
 */
function terminText(d: CommitteeDetail): { kurz: string; lang: string } | null {
  if (!d.next_date) return null;
  const tag = wochentagKurz(d.next_date);
  const voll = formatDate(d.next_date);                 // 14.09.2026
  const ohneJahr = voll.split(".").slice(0, 2).join(".") + ".";
  const zeit = d.next_time ? ` · ${d.next_time.slice(0, 5)}` : "";
  const praefix = tag ? `${tag} ` : "";
  return { kurz: `${praefix}${ohneJahr}${zeit}`, lang: `${praefix}${voll}${zeit}` };
}

function Zeile({ d, abonniert, onToggle, busy }: {
  d: CommitteeDetail; abonniert: boolean; onToggle: () => void; busy: boolean;
}) {
  const termin = terminText(d);
  const erklaerung = committeeExplains(d.name);
  return (
    <div className="flex items-start gap-3 px-4 py-3">
      <div className="min-w-0 flex-1">
        {/* Der amtliche Name bleibt im title erreichbar — angezeigt wird der
            Kurzname, wie im Einrichtungs-Assistenten (Design 28a/R3). */}
        <p className="text-sm font-medium leading-snug text-foreground" title={d.name}>
          {shortCommittee(d.name)}
        </p>
        {/* Der Erklärsatz kam mit Design 28a/R3 dazu, weil ein Gremienname
            allein nicht sagt, worüber dort entschieden wird — und genau das
            ist die Frage vor einem Abo. Ein unbekanntes Gremium bekommt
            keinen erfundenen Satz, dann bleibt es beim Namen. */}
        {erklaerung && (
          <p className="mt-0.5 text-[12.5px] leading-relaxed text-muted-foreground">{erklaerung}</p>
        )}
        {/* Mobil ohne das Wort „Nächste Sitzung": Es kostete so viel Zeile,
            dass die Uhrzeit dahinter abgeschnitten wurde — also genau die
            Angabe, für die die Zeile da ist. Neben einem Datum in der Zukunft
            sagt der Zusatz ohnehin wenig; auf dem Desktop ist Platz für ihn. */}
        {termin && (
          <p className="mt-1 truncate font-mono text-[10px] uppercase tracking-[0.08em] text-muted-foreground">
            <span className="hidden sm:inline">Nächste Sitzung · {termin.lang}</span>
            <span className="sm:hidden">{termin.kurz}</span>
          </p>
        )}
      </div>
      {d.decisions_year > 0 && (
        <span className="hidden shrink-0 whitespace-nowrap text-[11px] text-muted-foreground @xl:inline">
          {d.decisions_year} {d.decisions_year === 1 ? "Beschluss" : "Beschlüsse"} {new Date().getFullYear()}
        </span>
      )}
      <button
        type="button" onClick={onToggle} disabled={busy}
        aria-label={`${d.name} ${abonniert ? "abbestellen" : "abonnieren"}`}
        className={
          abonniert
            ? "inline-flex h-8 shrink-0 items-center gap-1.5 whitespace-nowrap rounded-xl border border-border bg-card px-3 text-[13px] font-medium text-foreground transition-colors hover:bg-muted disabled:opacity-50"
            : "inline-flex h-8 shrink-0 items-center whitespace-nowrap rounded-xl bg-primary px-3 text-[13px] font-medium text-primary-foreground shadow-[0_1px_2px_hsl(var(--primary)/0.25)] transition-opacity hover:opacity-90 disabled:opacity-50"
        }
      >
        {abonniert && <Check className="h-3.5 w-3.5" />}
        {abonniert ? "Abonniert" : "Abonnieren"}
      </button>
    </div>
  );
}

export function AbosView() {
  const qc = useQueryClient();

  const gremienQuery = useQuery({
    queryKey: ["committees"],
    queryFn: () => api.get<{ committees: string[]; details?: CommitteeDetail[] }>("/council/committees"),
  });

  const subsQuery = useQuery({
    queryKey: ["subscriptions"],
    queryFn: () => api.get<{ subscriptions: string[] }>("/subscriptions").then((d) => d.subscriptions),
  });

  const subMutation = useMutation({
    mutationFn: ({ committee, subscribed }: { committee: string; subscribed: boolean }) =>
      subscribed
        ? api.del("/subscriptions", { committee_name: committee })
        : api.post("/subscriptions", { committee_name: committee }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["subscriptions"] }),
    onError: () => toast.error("Abo konnte nicht geändert werden."),
  });

  const HEADER_DESC =
    "Benachrichtigungen, sobald ein Gremium eine Tagesordnung veröffentlicht — "
    + "und noch einmal, wenn sie sich danach ändert.";

  if (gremienQuery.isPending) {
    return (
      <div>
        <PageHeader title="Ausschuss-Abos" description={HEADER_DESC} />
        <div className="mt-6"><CardListSkeleton rows={4} /></div>
      </div>
    );
  }
  if (gremienQuery.isError) {
    return (
      <div>
        <PageHeader title="Ausschuss-Abos" description={HEADER_DESC} />
        <div className="mt-6">
          <ErrorState title="Die Gremien kamen nicht durch"
            onRetry={() => void gremienQuery.refetch()} busy={gremienQuery.isFetching} />
        </div>
      </div>
    );
  }

  const namen = Array.isArray(gremienQuery.data?.committees) ? gremienQuery.data.committees : [];
  const details = Array.isArray(gremienQuery.data?.details) ? gremienQuery.data!.details! : [];
  const abos = Array.isArray(subsQuery.data) ? subsQuery.data : [];

  /* Aus den Namen die Liste bauen, nicht aus `details`: Ein älteres Backend
     (native App auf altem Stand gegen neues Web, oder umgekehrt) liefert die
     Zusatzangaben noch nicht — dann fehlen Termin und Zahl, die Seite steht
     aber vollständig. */
  const perName = new Map(details.map((d) => [d.name, d]));
  const alle: CommitteeDetail[] = namen.map((n) =>
    perName.get(n) ?? { name: n, next_date: null, next_time: null, decisions_year: 0 });

  // Alltagsbezug zuerst, wie im Einrichtungs-Assistenten (Design 28a/R3).
  const sortiert = alle.slice().sort((a, b) =>
    committeeRank(a.name) - committeeRank(b.name)
    || shortCommittee(a.name).localeCompare(shortCommittee(b.name), "de"));

  const meine = sortiert.filter((d) => abos.includes(d.name));
  const rest = sortiert.filter((d) => !abos.includes(d.name));

  const toggle = (name: string, subscribed: boolean) =>
    subMutation.mutate({ committee: name, subscribed });

  return (
    <div className="@container">
      <PageHeader title="Ausschuss-Abos" description={HEADER_DESC} />

      <p className="mt-7 font-mono text-[10px] font-medium uppercase tracking-[0.1em] text-muted-foreground">
        Abonniert ({meine.length})
      </p>
      <div className="mt-2 divide-y divide-border/60 overflow-hidden rounded-xl border border-border bg-card shadow-[0_1px_2px_rgba(0,0,0,0.04)]">
        {meine.length === 0 ? (
          <p className="px-4 py-3.5 text-[13.5px] text-muted-foreground">
            Noch keine Abos — wähle unten ein Gremium aus.
          </p>
        ) : (
          meine.map((d) => (
            <Zeile key={d.name} d={d} abonniert onToggle={() => toggle(d.name, true)} busy={subMutation.isPending} />
          ))
        )}
      </div>

      {rest.length > 0 && (
        <>
          <p className="mt-7 font-mono text-[10px] font-medium uppercase tracking-[0.1em] text-muted-foreground">
            Weitere Gremien ({rest.length})
          </p>
          <div className="mt-2 divide-y divide-border/60 overflow-hidden rounded-xl border border-border bg-card shadow-[0_1px_2px_rgba(0,0,0,0.04)]">
            {rest.map((d) => (
              <Zeile key={d.name} d={d} abonniert={false} onToggle={() => toggle(d.name, false)} busy={subMutation.isPending} />
            ))}
          </div>
        </>
      )}

      <div className="mt-6 flex flex-wrap items-center justify-between gap-4 rounded-2xl bg-muted/60 px-4 py-3.5">
        <p className="text-[13.5px] text-muted-foreground">
          Nur ein bestimmtes Anliegen verfolgen? Lege dafür ein Thema an — wir durchsuchen jede neue Sitzung danach.
        </p>
        <Link href="/topics" className="whitespace-nowrap text-[13px] font-medium text-primary hover:underline">
          Zu Meinen Themen →
        </Link>
      </div>
    </div>
  );
}
