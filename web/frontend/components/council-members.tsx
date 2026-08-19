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
import { PersonEintrag } from "@/components/qa-bausteine";

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

/** Verwaltungsleute mit erkanntem Amt (Tims Wunsch 19.08.): dieselbe
 *  Hafenblau-Farbe wie ihr Badge im KI-Antworttext, statt einer Partei —
 *  Verwaltung ist parteilos, ein Partei-Badge wäre hier falsch. */
function VerwaltungChip({ p }: { p: PersonEintrag }) {
  return (
    <Link href={personHref(p.slug)} className="block">
      <Card className="card-interactive flex items-center gap-3 p-3">
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-foreground">{p.name}</p>
          <p className="mt-0.5 truncate text-xs text-muted-foreground">{p.rolle}</p>
        </div>
        <span className="inline-flex shrink-0 items-center gap-1.5 rounded-full border border-border bg-card px-1.5 py-px text-[10px] font-medium text-muted-foreground">
          <span aria-hidden className="h-[7px] w-[7px] shrink-0 rounded-full" style={{ backgroundColor: "#0764a6" }} />
          Stadt
        </span>
      </Card>
    </Link>
  );
}

export function PersonenView() {
  const { data, loading } = useFetch<{ members: Member[] }>("/council/members");
  // Öffentlich, sechs Stunden gecacht (dieselbe Quelle wie die Badges im
  // KI-Antworttext) — kein eigener Verwaltungs-Endpunkt nötig.
  const { data: lexikon } = useFetch<{ personen: PersonEintrag[] }>("/council/personen-lexikon");
  const [q, setQ] = useState("");
  const [party, setParty] = useState("");

  if (loading) return <div className="py-4"><TableSkeleton rows={8} cols={4} /></div>;
  const all = data?.members ?? [];
  if (all.length === 0) {
    return <EmptyState mascot="sleep" title="Keine Ratsmitglieder" hint="Es wurden noch keine Anwesenheiten aus den Protokollen erfasst." />;
  }
  const parties = Array.from(new Set(all.map((m) => m.party).filter((p): p is string => !!p))).sort();
  const needle = q.trim().toLowerCase();
  // Gesucht wird über alle belegten Schreibweisen, angezeigt wird die aktuelle:
  // Wer eine Person aus einem älteren Protokoll unter der damaligen Namensform
  // sucht, soll sie finden — die Karte bleibt trotzdem so beschriftet, wie die
  // jüngste Anwesenheitsliste sie nennt.
  const passt = (m: Member) =>
    m.name.toLowerCase().includes(needle) ||
    (m.formen ?? []).some((f) => f.toLowerCase().includes(needle));
  const filtered = all.filter((m) => (!needle || passt(m)) && (!party || m.party === party));
  // Nur Verwaltungsleute mit ERKANNTEM Amt haben einen Steckbrief
  // (verwaltung_detail() im Backend) — ohne Amt gäbe es nur einen toten Link.
  // Der Parteifilter blendet den Block aus: Verwaltung ist parteilos, unter
  // einer gewählten Fraktion wäre er nur verwirrend.
  const verwaltung = party ? [] : (lexikon?.personen ?? [])
    .filter((p) => p.art === "stadt" && p.rolle && (!needle || (p.name ?? "").toLowerCase().includes(needle)));

  return (
    <div className="space-y-4">
      <AnalysisIntro summary={<>Wer im Rat und in den Ausschüssen sitzt — und wie <strong className="font-semibold text-foreground">präsent</strong>.</>}>
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
      <p className="text-xs text-muted-foreground">{filtered.length} Personen — nach Präsenz sortiert, klicken für das Profil.</p>
      <div className="grid gap-2 sm:grid-cols-2">
        {filtered.map((m) => <MemberChip key={m.slug} m={m} />)}
      </div>
      {verwaltung.length > 0 && (
        <>
          <h2 className="mt-2 font-display text-[15px] font-bold text-foreground">Stadtverwaltung</h2>
          <p className="text-xs text-muted-foreground">
            Amt laut Anwesenheitslisten der Protokolle — keine amtlichen Stammdaten, s. Profil.
          </p>
          <div className="grid gap-2 sm:grid-cols-2">
            {verwaltung.map((p) => <VerwaltungChip key={p.slug} p={p} />)}
          </div>
        </>
      )}
    </div>
  );
}
