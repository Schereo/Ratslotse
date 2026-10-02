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
import { Fragment, type CSSProperties, type ReactNode } from "react";
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
  /** „mehrheitlich“ / „einstimmig“ — oder `null`, wenn das Protokoll es nicht sagt. */
  vote_label: string | null;
  /** ["18 Gegenstimmen", "2 Enthaltungen"] — leer, wenn nichts gezählt ist. */
  vote_counts: string[];
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

/** Eine Kachel: kleines Etikett oben, die Angabe darunter. */
function Kachel({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="min-w-0 rounded-[10px] bg-muted/60 px-3 py-2.5">
      <p className="font-mono text-[10px] uppercase tracking-[0.08em] text-muted-foreground">{label}</p>
      {children}
    </div>
  );
}

function Meta({ children }: { children: ReactNode }) {
  return <p className="flex flex-wrap items-center gap-x-2 gap-y-0.5 font-mono text-meta text-muted-foreground">{children}</p>;
}

const TITEL = "break-words text-quelle font-medium leading-snug";

/** „Zuletzt“ / „Als Nächstes“ — Punkt und Etikett wie im Verlauf (RG-03):
 *  gefüllt mit Halo für einen Beschluss, gestrichelt für einen Termin ohne
 *  Ergebnis und — grau — für eine Pressemitteilung (nicht von uns). */
function Station({ s, label, idToNum, onJump, hinweis }: {
  s: KeyFactsStation; label: string; idToNum: Map<number, number>;
  onJump: (id: number) => void; hinweis?: string;
}) {
  return (
    <li className="flex gap-3">
      <span aria-hidden className={cn("mt-[5px] h-2.5 w-2.5 shrink-0 rounded-full border-2",
        s.kind === "announced" ? "border-dashed border-primary/70 bg-card"
          : s.kind === "press" ? "border-dashed border-muted-foreground/70 bg-card"
          : "border-primary bg-primary shadow-[0_0_0_3px_hsl(var(--primary)/0.15)]")} />
      <div className="min-w-0 flex-1">
        <p className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
          <span className="font-mono text-[9px] font-bold uppercase tracking-[0.14em] text-primary">{label}</span>
          <span className="font-mono text-meta text-muted-foreground">
            {datum(s.date)}{s.kind === "press" ? " · Pressemitteilung der Stadt" : s.committee ? ` · ${s.committee}` : ""}
          </span>
          {s.kind === "decision" && <Badge outcome={s.outcome} />}
        </p>
        {s.kind === "decision" && s.decision_id != null ? (
          <p className={TITEL}>
            <Link href={decisionHref(s.decision_id)} className="hover:text-primary hover:underline">{s.title}</Link>
            <Chip id={s.decision_id} idToNum={idToNum} onJump={onJump} />
          </p>
        ) : s.kind === "press" && s.url ? (
          <p className={TITEL}>
            <a href={s.url} target="_blank" rel="noopener noreferrer" className="hover:text-primary hover:underline">
              {s.title}
              <ExternalLink className="ml-1 inline h-3 w-3 -translate-y-px text-muted-foreground" aria-hidden />
            </a>
          </p>
        ) : (
          <p className={TITEL}>{s.title}</p>
        )}
        {hinweis && <p className="mt-0.5 text-meta text-muted-foreground">{hinweis}</p>}
      </div>
    </li>
  );
}

export function KeyFactsCard({ facts, idToNum, onJump }: {
  facts: KeyFacts; idToNum: Map<number, number>; onJump: (id: number) => void;
}) {
  const d = facts.decision;
  const zahlen = d.vote_counts ?? [];
  const stimmen = d.vote_label || zahlen.length > 0;
  const kacheln = (stimmen ? 1 : 0) + facts.amounts.length;
  return (
    <section aria-label="Eckdaten" style={{ "--zl-i": 0 } as CSSProperties}
      className="zeitleiste-auf rounded-xl border border-border bg-card p-3.5">
      <p className="mb-1.5 font-mono text-[10px] uppercase tracking-[0.12em] text-muted-foreground">Eckdaten</p>

      {/* Der Beschluss ist der Kopf — kein Etikett nötig, das Badge sagt, was er ist. */}
      <Meta>
        <span>{datum(d.date)}{d.committee ? ` · ${d.committee}` : ""}</span>
        <Badge outcome={d.outcome} />
      </Meta>
      <p className={TITEL}>
        <Link href={decisionHref(d.decision_id)} className="hover:text-primary hover:underline">{d.title}</Link>
        <Chip id={d.decision_id} idToNum={idToNum} onJump={onJump} />
      </p>

      {kacheln > 0 && (
        // Auf dem Handy untereinander: Nebeneinander blieben je Kachel gut
        // 110 px, und „18 Gegenstimmen“ brach mitten in der Angabe um.
        <div className="mt-3 grid gap-2 ab-lesezeile:grid-cols-[repeat(auto-fit,minmax(9rem,1fr))]">
          {stimmen && (
            <Kachel label="Abstimmung">
              {d.vote_label && (
                <p className="mt-0.5 text-[17px] font-semibold leading-tight first-letter:uppercase">{d.vote_label}</p>
              )}
              {zahlen.length > 0 && (
                <p className={cn("text-meta", d.vote_label ? "text-muted-foreground" : "mt-0.5 font-semibold")}>
                  {/* Umbruch nur zwischen den Angaben, der Trenner bleibt am
                      Zeilenende — sonst begann die zweite Zeile mit „· 2 …“. */}
                  {zahlen.map((z, i) => (
                    <Fragment key={z}>
                      <span className="whitespace-nowrap">{z}{i < zahlen.length - 1 && " ·"}</span>
                      {i < zahlen.length - 1 && " "}
                    </Fragment>
                  ))}
                </p>
              )}
            </Kachel>
          )}
          {facts.amounts.map((a) => (
            <Kachel key={a.decision_id} label="Betrag">
              <p className="mt-0.5 font-display text-[22px] font-bold leading-tight tracking-tight tabular-nums">
                {euro(a.amount_eur)}
              </p>
              <p className="break-words text-meta text-muted-foreground">
                {a.decision_id === d.decision_id ? "größter Betrag im Beschlusstext" : a.title}
                <Chip id={a.decision_id} idToNum={idToNum} onJump={onJump} />
              </p>
            </Kachel>
          ))}
        </div>
      )}

      {(facts.latest || facts.next) && (
        <ul className="mt-3 space-y-2.5 border-t border-border pt-3">
          {facts.latest && (
            <Station s={facts.latest} label="Zuletzt" idToNum={idToNum} onJump={onJump}
              hinweis={facts.latest.kind === "announced"
                ? "stand auf der Tagesordnung, ein Ergebnis ist noch nicht protokolliert" : undefined} />
          )}
          {facts.next && (
            <Station s={facts.next} label="Als Nächstes" idToNum={idToNum} onJump={onJump}
              hinweis="steht auf der Tagesordnung" />
          )}
        </ul>
      )}
    </section>
  );
}
