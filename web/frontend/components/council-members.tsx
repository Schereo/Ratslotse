"use client";

import { useState } from "react";
import Link from "next/link";
import { Search, Users } from "lucide-react";
import { Member } from "@/lib/types";
import { Card, Input, Select, Spinner, EmptyState } from "@/components/ui";
import { PartyBadge } from "@/components/decision-ui";
import { personHref } from "@/lib/routes";
import { useFetch } from "@/lib/use-fetch";

function MemberChip({ m }: { m: Member }) {
  return (
    <Link href={personHref(m.slug)} className="block">
      <Card className="card-interactive flex items-center gap-3 p-3">
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-foreground">{m.name}</p>
          <p className="mt-0.5 text-xs text-muted-foreground">
            {m.n} {m.n === 1 ? "Sitzung" : "Sitzungen"} · {m.committees} {m.committees === 1 ? "Gremium" : "Gremien"}
          </p>
        </div>
        {m.party && <PartyBadge party={m.party} />}
      </Card>
    </Link>
  );
}

export function PersonenView() {
  const { data, loading } = useFetch<{ members: Member[] }>("/council/members");
  const [q, setQ] = useState("");
  const [party, setParty] = useState("");

  if (loading) return <div className="py-10"><Spinner /></div>;
  const all = data?.members ?? [];
  if (all.length === 0) {
    return <EmptyState icon={Users} title="Keine Ratsmitglieder" hint="Es wurden noch keine Anwesenheiten aus den Protokollen erfasst." />;
  }
  const parties = Array.from(new Set(all.map((m) => m.party).filter((p): p is string => !!p))).sort();
  const needle = q.trim().toLowerCase();
  const filtered = all.filter((m) => (!needle || m.name.toLowerCase().includes(needle)) && (!party || m.party === party));

  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-border bg-muted/40 p-3 text-xs leading-relaxed text-muted-foreground">
        Aus den Anwesenheitslisten der Protokolle: wer im Rat und in den Ausschüssen sitzt, in welcher Fraktion und
        wie präsent. Protokolle nennen selten namentliche Einzelstimmen — daher zählt hier die <span className="font-medium text-foreground">Präsenz</span>, nicht das Stimmverhalten. Erfasst sind Sitzungen <span className="font-medium text-foreground">ab 2018</span>.
      </div>
      <div className="flex flex-col gap-2 sm:flex-row">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input className="pl-9" placeholder="Name suchen…" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        <Select value={party} onChange={(e) => setParty(e.target.value)} className="sm:w-56">
          <option value="">Alle Fraktionen</option>
          {parties.map((p) => <option key={p} value={p}>{p}</option>)}
        </Select>
      </div>
      <p className="text-xs text-muted-foreground">{filtered.length} Personen — nach Präsenz sortiert, klicken für das Profil.</p>
      <div className="grid gap-2 sm:grid-cols-2">
        {filtered.map((m) => <MemberChip key={m.slug} m={m} />)}
      </div>
    </div>
  );
}
