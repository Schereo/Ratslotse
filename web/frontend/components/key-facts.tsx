"use client";

// <KeyFactsCard> — die Eckdaten unter der Antwort (Plan „Akte“, Schalter
// `akten-zeitleiste`): der jüngste zitierte Beschluss mit seiner Abstimmung,
// der Betrag, den er nennt, was danach kam und was als Nächstes ansteht.
//
// WARUM ES SIE GIBT: In der Gold-Runde vom 02.10.2026 hatten 30 % der
// verfehlten Pflichtfakten ihren Beleg im Kontext — fast immer Stimmen,
// Beträge und Daten. Das Modell lässt sie weg, egal wie man fragt. Hier
// stehen sie trotzdem, direkt aus den Daten.
//
// GEBAUT WIRD SIE IM BACKEND (council/akte_suche.py, key_facts): welcher
// Beschluss, welcher Betrag, welche Station — hier wird nur dargestellt.

import Link from "next/link";
import type { CSSProperties, ReactNode } from "react";
import { ExternalLink } from "lucide-react";
import { OUTCOME_META } from "@/components/decision-ui";
import { decisionHref } from "@/lib/routes";
import type { DecisionOutcome } from "@/lib/types";
import { cn } from "@/lib/utils";

export type KeyFactsDecision = {
  decision_id: number;
  date: string;
  committee: string | null;
  outcome: DecisionOutcome;
  votes: string | null;
  title: string;
};

export type KeyFactsAmount = { amount_eur: number; decision_id: number; title: string };

export type KeyFactsStation = {
  kind: "decision" | "press" | "announced";
  date: string;
  title: string;
  committee: string | null;
  outcome: DecisionOutcome | null;
  decision_id: number | null;
  url: string | null;
};

export type KeyFacts = {
  decision: KeyFactsDecision;
  amounts: KeyFactsAmount[];
  latest: KeyFactsStation | null;
  next: KeyFactsStation | null;
};

/** „01.06.2026“ aus dem ISO-Datum — ohne `new Date`, das rutscht je nach
 *  Zeitzone auf den Vortag. */
function datum(iso: string): string {
  const [j, m, t] = iso.split("-");
  return t && m && j ? `${t}.${m}.${j}` : iso;
}

function euro(n: number): string {
  return n >= 1_000_000
    ? `${(n / 1_000_000).toLocaleString("de-DE", { maximumFractionDigits: 1 })} Mio. €`
    : `${Math.round(n).toLocaleString("de-DE")} €`;
}

function Chip({ id, idToNum, onJump }: {
  id: number; idToNum: Map<number, number>; onJump: (id: number) => void;
}) {
  const n = idToNum.get(id);
  if (n == null) return null;
  return (
    <button type="button" onClick={() => onJump(id)} aria-label={`Quelle ${n} anzeigen`}
      className="ml-1.5 inline-flex h-4 min-w-4 -translate-y-[2px] items-center justify-center rounded bg-primary/10 px-1 align-baseline text-[10px] font-bold leading-none text-primary hover:bg-primary/20">
      {n}
    </button>
  );
}

function Badge({ outcome }: { outcome: DecisionOutcome | null }) {
  const m = outcome ? OUTCOME_META[outcome] : undefined;
  if (!m) return null;
  return <span className={cn("rounded-full px-2 py-px text-[10.5px] font-semibold", m.cls)}>{m.label}</span>;
}

/** Eine Zeile: links das Etikett, rechts die Angabe — auf dem Handy untereinander. */
function Zeile({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid gap-x-4 gap-y-1 py-2.5 first:pt-0 last:pb-0 sm:grid-cols-[7.5rem_minmax(0,1fr)]">
      <dt className="pt-px font-mono text-[10px] uppercase tracking-[0.08em] text-muted-foreground">{label}</dt>
      <dd className="min-w-0">{children}</dd>
    </div>
  );
}

function Meta({ children }: { children: ReactNode }) {
  return <p className="flex flex-wrap items-center gap-x-2 gap-y-0.5 font-mono text-meta text-muted-foreground">{children}</p>;
}

function Station({ s, idToNum, onJump, hinweis }: {
  s: KeyFactsStation; idToNum: Map<number, number>; onJump: (id: number) => void; hinweis?: string;
}) {
  const titelCls = "break-words text-quelle font-medium leading-snug";
  return (
    <>
      <Meta>
        <span>{datum(s.date)}{s.kind === "press" ? " · Pressemitteilung der Stadt" : s.committee ? ` · ${s.committee}` : ""}</span>
        {s.kind === "decision" && <Badge outcome={s.outcome} />}
      </Meta>
      {s.kind === "decision" && s.decision_id != null ? (
        <p className={titelCls}>
          <Link href={decisionHref(s.decision_id)} className="hover:text-primary hover:underline">{s.title}</Link>
          <Chip id={s.decision_id} idToNum={idToNum} onJump={onJump} />
        </p>
      ) : s.kind === "press" && s.url ? (
        <p className={titelCls}>
          <a href={s.url} target="_blank" rel="noopener noreferrer" className="hover:text-primary hover:underline">
            {s.title}
            <ExternalLink className="ml-1 inline h-3 w-3 -translate-y-px text-muted-foreground" aria-hidden />
          </a>
        </p>
      ) : (
        <p className={titelCls}>{s.title}</p>
      )}
      {hinweis && <p className="mt-0.5 text-meta text-muted-foreground">{hinweis}</p>}
    </>
  );
}

export function KeyFactsCard({ facts, idToNum, onJump }: {
  facts: KeyFacts; idToNum: Map<number, number>; onJump: (id: number) => void;
}) {
  const d = facts.decision;
  return (
    <section aria-label="Eckdaten" style={{ "--zl-i": 0 } as CSSProperties}
      className="zeitleiste-auf rounded-xl border border-border bg-card p-3.5">
      <p className="mb-2 font-mono text-[10px] uppercase tracking-[0.12em] text-muted-foreground">Eckdaten</p>
      <dl className="divide-y divide-border">
        <Zeile label="Beschluss">
          <Meta>
            <span>{datum(d.date)}{d.committee ? ` · ${d.committee}` : ""}</span>
            <Badge outcome={d.outcome} />
          </Meta>
          <p className="break-words text-quelle font-medium leading-snug">
            <Link href={decisionHref(d.decision_id)} className="hover:text-primary hover:underline">{d.title}</Link>
            <Chip id={d.decision_id} idToNum={idToNum} onJump={onJump} />
          </p>
        </Zeile>

        {d.votes && (
          <Zeile label="Abstimmung">
            <p className="text-quelle font-semibold leading-snug first-letter:uppercase">{d.votes}</p>
          </Zeile>
        )}

        {facts.amounts.length > 0 && (
          <Zeile label="Betrag">
            <div className="grid gap-x-6 gap-y-2 sm:grid-cols-2">
              {facts.amounts.map((a) => (
                <div key={a.decision_id} className="min-w-0">
                  <p className="font-display text-[24px] font-bold leading-tight tracking-tight tabular-nums">
                    {euro(a.amount_eur)}
                  </p>
                  <p className="break-words text-meta text-muted-foreground">
                    {a.decision_id === d.decision_id ? "im Beschluss oben" : a.title}
                    <Chip id={a.decision_id} idToNum={idToNum} onJump={onJump} />
                  </p>
                </div>
              ))}
            </div>
            <p className="mt-1.5 text-meta text-muted-foreground">
              {facts.amounts.length === 1
                ? "Der größte Betrag, den der Beschlusstext nennt."
                : "Je der größte Betrag, den der Beschlusstext nennt."}
            </p>
          </Zeile>
        )}

        {facts.latest && (
          <Zeile label="Zuletzt">
            <Station s={facts.latest} idToNum={idToNum} onJump={onJump}
              hinweis={facts.latest.kind === "announced"
                ? "stand auf der Tagesordnung, ein Ergebnis ist noch nicht protokolliert" : undefined} />
          </Zeile>
        )}

        {facts.next && (
          <Zeile label="Als Nächstes">
            <Station s={facts.next} idToNum={idToNum} onJump={onJump} hinweis="steht auf der Tagesordnung" />
          </Zeile>
        )}
      </dl>
    </section>
  );
}
