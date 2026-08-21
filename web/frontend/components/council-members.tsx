"use client";

import { useState } from "react";
import Link from "next/link";
import { Search } from "lucide-react";
import { Member } from "@/lib/types";
import { Card, Input, Select, TableSkeleton, EmptyState } from "@/components/ui";
import { PartyBadge } from "@/components/decision-ui";
import { AnalysisIntro } from "@/components/analysis-intro";
import { personHref } from "@/lib/routes";
import { useFetch } from "@/lib/use-fetch";

function MemberChip({ m }: { m: Member }) {
  return (
    <Link href={personHref(m.slug)} className="block">
      <Card className="card-interactive flex items-center gap-3 p-3">
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-foreground">{m.name}</p>
          <p className="mt-0.5 truncate text-xs text-muted-foreground">
            {m.n} {m.n === 1 ? "Sitzung" : "Sitzungen"} · {m.committees} {m.committees === 1 ? "Gremium" : "Gremien"}
            {/* Bei beratenden Mitgliedern steht im Fraktions-Feld die
                entsendende Organisation — die sagt hier mehr als die Zahl. */}
            {m.organisation ? ` · ${m.organisation}` : ""}
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

  if (loading) return <div className="py-4"><TableSkeleton rows={8} cols={4} /></div>;
  const all = data?.members ?? [];
  if (all.length === 0) {
    return <EmptyState mascot="sleep" title="Keine Ratsmitglieder" hint="Es wurden noch keine Anwesenheiten aus den Protokollen erfasst." />;
  }
  // Der Filter führt Fraktionen, keine Zusammenschlüsse: „Mitglied der Gruppe
  // FDP/Volt" ist niemand — man gehört der FDP an oder Volt (Tims Befund
  // 21.08.2026). Wo die Auflösung nichts fand, zählt das Gruppen-Label für
  // beide Parteien; die Karte nennt daneben weiter das ehrliche Label.
  const parties = Array.from(new Set(all.flatMap((m) => m.filter_parteien ?? []))).sort();
  const needle = q.trim().toLowerCase();
  const filtered = all.filter((m) => (!needle || m.name.toLowerCase().includes(needle))
    && (!party || (m.filter_parteien ?? []).includes(party)));
  const rat = filtered.filter((m) => m.art !== "beratend");
  const beratend = filtered.filter((m) => m.art === "beratend");

  return (
    <div className="space-y-4">
      <AnalysisIntro summary={<>Wer im Rat sitzt, wer die Ausschüsse <strong className="font-semibold text-foreground">berät</strong> — und wie präsent.</>}>
        Aus den Anwesenheitslisten der Protokolle: wer im Rat und in den Ausschüssen sitzt, in welcher Fraktion und wie
        präsent. Protokolle nennen namentliche Einzelstimmen nur selten — daher zählt hier die{" "}
        <strong className="font-semibold text-foreground">Präsenz</strong>, nicht das Stimmverhalten. Erfasst sind
        Sitzungen <strong className="font-semibold text-foreground">ab 2018</strong>.
      </AnalysisIntro>
      <div className="flex flex-col gap-2 sm:flex-row">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input data-search className="pl-9" placeholder="Name suchen…" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        <Select value={party} onChange={(e) => setParty(e.target.value)} className="sm:w-56">
          <option value="">Alle Fraktionen</option>
          {parties.map((p) => <option key={p} value={p}>{p}</option>)}
        </Select>
      </div>
      <p className="text-xs text-muted-foreground">
        {rat.length} {rat.length === 1 ? "Ratsmitglied" : "Ratsmitglieder"}
        {beratend.length > 0 && ` · ${beratend.length} beratende ${beratend.length === 1 ? "Person" : "Personen"}`}
        {" "}— nach Präsenz sortiert, klicken für das Profil.
      </p>
      {/* Zwei Abschnitte statt einer Liste: Ein beratendes Ausschuss-Mitglied
          (Verband, Beirat, Fachperson) gehört dem Rat NICHT an — es zwischen
          die Ratsmitglieder zu mischen, behauptet ein Mandat, das es nicht
          gibt (Tims Skiba-Befund 21.08.2026). */}
      {rat.length > 0 && (
        <div className="grid gap-2 sm:grid-cols-2">
          {rat.map((m) => <MemberChip key={m.slug} m={m} />)}
        </div>
      )}
      {beratend.length > 0 && (
        <>
          <div className="flex items-baseline gap-2 pt-2">
            <h3 className="font-display text-base font-bold text-foreground">Beratende Mitglieder</h3>
            <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-muted-foreground">
              {beratend.length} Personen
            </span>
          </div>
          <p className="-mt-2 text-xs leading-relaxed text-muted-foreground">
            Verbände, Beiräte und Fachleute, die in Ausschüssen mitberaten — sie sitzen dort mit
            Rederecht, gehören dem Rat aber nicht an und stimmen nicht mit ab. Erkannt daran, dass
            sie in keiner Ratssitzung als Mitglied geführt sind.
          </p>
          <div className="grid gap-2 sm:grid-cols-2">
            {beratend.map((m) => <MemberChip key={m.slug} m={m} />)}
          </div>
        </>
      )}
    </div>
  );
}
