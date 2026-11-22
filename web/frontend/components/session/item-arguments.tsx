"use client";

/* Reiter „Argumente“ und „Fraktionen“ der Punkt-Seite (Schalter
   `punkt-argumente`, Plan `docs/plan-punkt-argumente.md`, Bild
   `docs/entwurf-sitzungsseite/bilder/punkt-desktop-1…2.png`).

   Paraphrasen kursiv, ohne Anführungszeichen (DESIGNSPRACHE § 1). Jede
   Aussage trägt ihren Urheber und eine Fundstelle; beides kommt aus der
   Quelle, nicht vom Modell. */

import { useState } from "react";
import Link from "next/link";
import { ExternalLink, MessageSquareQuote } from "lucide-react";
import { KiStern } from "@/components/ki-stern";
import { partyBrand } from "@/components/decision-ui";
import { chipMerken } from "@/lib/chip-frage";
import {
  askHref, attribution, basisLine, countLine, sourceLabel,
  type ItemArguments, type Statement,
} from "@/lib/punkt-argumente";
import { cn } from "@/lib/utils";

const KICKER = "font-mono text-meta uppercase tracking-[0.06em] text-muted-foreground";
const CHIP = "inline-flex rounded-full px-2 py-0.5 text-xs font-medium";
const DAFUER = "bg-green-50 text-green-700 dark:bg-green-950/40 dark:text-green-300";
const DAGEGEN = "bg-red-50 text-red-700 dark:bg-red-950/40 dark:text-red-300";

function Aussage({ a, party = true }: { a: Statement; party?: boolean }) {
  return (
    <li className="[overflow-wrap:anywhere]">
      <p className="text-quelle italic text-foreground">{a.text}</p>
      <p className="mt-1 text-hinweis text-muted-foreground">
        — {attribution(a, { party })}
        {a.source.url && (
          <>
            {" · "}
            <a href={a.source.url} target="_blank" rel="noreferrer"
              className="inline-flex items-center gap-1 text-primary hover:underline">
              {sourceLabel(a)} <ExternalLink className="h-3 w-3" aria-hidden />
            </a>
          </>
        )}
      </p>
    </li>
  );
}

function Seite({ titel, cls, xs }: { titel: string; cls: string; xs: Statement[] }) {
  return (
    <div className="min-w-0">
      <span className={cn(CHIP, cls)}>{titel}</span>
      {xs.length > 0
        ? <ul className="mt-2 space-y-4">{xs.map((a, i) => <Aussage key={`${a.source.id}-${i}`} a={a} />)}</ul>
        : <p className="mt-2 text-hinweis text-muted-foreground">Dazu gibt es auf dieser Seite keine Aussage.</p>}
    </div>
  );
}

export function Argumente({ args, ksinr, itemNumber }: { args: ItemArguments; ksinr: number; itemNumber: string }) {
  const n = args.issues.length;
  const basis = basisLine(args);
  const weitere = args.further.pro.length + args.further.contra.length;
  return (
    <section aria-labelledby="argumente-titel">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h2 id="argumente-titel" className="font-display text-base font-semibold text-foreground">
          Worüber gestritten wird
          {basis && <KiStern className="ml-1" text={`Von einem Sprachmodell zusammengestellt ${basis}.`} />}
        </h2>
        <p className={KICKER}>{countLine(args)}</p>
      </div>

      {args.issues.map((iss, i) => (
        <article key={iss.question} className="mt-4 rounded-2xl border border-border bg-card p-5 shadow-sm">
          <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
            <h3 className="min-w-0 font-display text-base font-semibold text-foreground [overflow-wrap:anywhere]">{iss.question}</h3>
            {n > 1 && <p className={KICKER}>Streitpunkt {i + 1} von {n}</p>}
          </div>
          <div className="mt-3 grid grid-cols-[minmax(0,1fr)] gap-5 sm:grid-cols-2">
            <Seite titel="Dafür" cls={DAFUER} xs={iss.pro} />
            <Seite titel="Dagegen" cls={DAGEGEN} xs={iss.contra} />
          </div>
          <div className="mt-4 border-t border-border pt-2">
            <Link href={askHref(ksinr, itemNumber, iss)} prefetch={false} onClick={() => chipMerken(iss.question)}
              className="inline-flex min-h-11 items-center gap-1.5 text-sm font-medium text-primary hover:underline">
              <MessageSquareQuote className="h-4 w-4" aria-hidden /> Dazu fragen
            </Link>
          </div>
        </article>
      ))}

      {weitere > 0 && (
        <>
          <div className="mt-6 flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
            <h3 className="font-display text-base font-semibold text-foreground">{n ? "Weitere Argumente" : "Argumente"}</h3>
            <p className={KICKER}>{args.further.pro.length} dafür · {args.further.contra.length} dagegen oder mit Bedenken</p>
          </div>
          <div className="mt-3 grid grid-cols-[minmax(0,1fr)] items-start gap-4 sm:grid-cols-2">
            {args.further.pro.length > 0 && (
              <div className="rounded-2xl border border-border bg-card p-5 shadow-sm">
                <Seite titel="Dafür" cls={DAFUER} xs={args.further.pro} />
              </div>
            )}
            {args.further.contra.length > 0 && (
              <div className="rounded-2xl border border-border bg-card p-5 shadow-sm">
                <Seite titel="Dagegen oder mit Bedenken" cls={DAGEGEN} xs={args.further.contra} />
              </div>
            )}
          </div>
        </>
      )}

      <p className="mt-5 text-hinweis text-muted-foreground">
        Argumente sind Aussagen der Beteiligten, keine geprüften Tatsachen. Wortmeldungen stehen sinngemäß, wie
        das Protokoll sie wiedergibt; das Datum steht jeweils dabei.
        {args.stale && " Seit der Zusammenstellung sind Wortbeiträge dazugekommen; sie fließen beim nächsten Lauf ein."}
      </p>
    </section>
  );
}

/** Je Fraktion die ersten Wortmeldungen; der Rest auf Wunsch. Sieben
 *  Beiträge einer Fraktion hintereinander schieben die übrigen aus dem Blick. */
const ERSTE = 3;

function FraktionKarte({ f }: { f: ItemArguments["factions"][number] }) {
  const [alle, setAlle] = useState(false);
  const brand = partyBrand(f.party);
  const zeigen = alle ? f.statements : f.statements.slice(0, ERSTE);
  const rest = f.statements.length - zeigen.length;
  return (
    <article className="rounded-2xl border border-border bg-card p-5 shadow-sm">
      <h3 className="flex flex-wrap items-center gap-x-2 gap-y-0.5 font-display text-base font-semibold text-foreground">
        {/* Ring: Der CDU-Punkt ist schwarz und verschwände sonst im Dunkeln. */}
        <span className="h-2.5 w-2.5 flex-none rounded-full ring-1 ring-foreground/25"
          style={{ backgroundColor: brand?.bg ?? "transparent" }} aria-hidden />
        {f.party}
        <span className="font-mono text-meta font-normal text-muted-foreground">
          {f.statements.length} {f.statements.length === 1 ? "Wortmeldung" : "Wortmeldungen"}
        </span>
      </h3>
      <ul className="mt-3 space-y-4">
        {zeigen.map((a, i) => <Aussage key={`${a.source.id}-${i}`} a={a} party={false} />)}
      </ul>
      {rest > 0 && (
        <button type="button" onClick={() => setAlle(true)}
          className="mt-2 inline-flex min-h-11 items-center text-sm font-medium text-primary hover:underline">
          {rest === 1 ? "Eine weitere Wortmeldung" : `${rest} weitere Wortmeldungen`}
        </button>
      )}
    </article>
  );
}

export function Fraktionen({ args }: { args: ItemArguments }) {
  return (
    <section aria-labelledby="fraktionen-titel">
      <h2 id="fraktionen-titel" className="font-display text-base font-semibold text-foreground">Was die Fraktionen gesagt haben</h2>
      <div className="mt-3 space-y-4">
        {args.factions.map((f) => <FraktionKarte key={f.party} f={f} />)}
      </div>
      <p className="mt-5 text-hinweis text-muted-foreground">
        Wortmeldungen stehen sinngemäß, wie das Protokoll sie wiedergibt. Eine einzelne Wortmeldung ist nicht immer
        die Linie der ganzen Fraktion. Hier stehen nur Wortmeldungen, denen das Protokoll eine Fraktion zuordnet.
      </p>
    </section>
  );
}
