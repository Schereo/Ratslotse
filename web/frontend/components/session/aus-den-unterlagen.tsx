"use client";

/* „Aus den Unterlagen" auf der Punkt-Seite (docs/plan-vorlagen-aufbereiten.md,
   § 6.1, Stufe 0): was die Vorlage schon trägt — Beschlussvorschlag, Anträge,
   Kosten, Klima. Alles amtlicher Wortlaut aus der Ernte, deshalb
   als Zitat mit Zitatkante und ohne KI-Stern. Ab Stufe 2 (Dossier) treten die
   erzeugten Abschnitte mit Belegen dazu; die Karte bleibt dieselbe.

   Schalter `aus-den-unterlagen`. */

import { useState } from "react";
import { ExternalLink } from "lucide-react";
import { normalizeParty, partyBrand } from "@/components/decision-ui";
import type { ApiAntwort } from "@/lib/vertrag";
import { cn } from "@/lib/utils";
import { Aenderungsantraege, type Antrag } from "@/components/session/aenderungsantraege";
import { DossierAbschnitt, dossierStand, type Dossier } from "@/components/session/dossier";
import { KiStern } from "@/components/ki-stern";

type Felder = NonNullable<ApiAntwort<"/council/session/{ksinr}/item">["template_fields"]>;

const KICKER = "font-mono text-meta uppercase tracking-[0.06em] text-muted-foreground";
const ZITAT = "border-l-2 border-border pl-3 text-lese text-foreground/90";

/** Wer die Vorlage geschrieben hat, steht als Absender am Kopf: Eine Vorlage
 *  kommt immer aus einem Amt (Anträge der Fraktionen sind keine Vorlagen und
 *  tragen ihre Partei selbst). Als eigener Abschnitt unten wiederholte die
 *  Zeile auf jeder Seite dasselbe Etikett (Tim, 13.11.2026). */
function Absender({ f }: { f: Felder | null }) {
  if (!f?.office) return null;
  return <p className="mt-1 text-sm text-muted-foreground">Von: {f.office}</p>;
}

function Abschnitt({ titel, children, className }: { titel: string; children: React.ReactNode; className?: string }) {
  return (
    <div className={cn("border-t border-border pt-4 first:border-t-0 first:pt-0", className)}>
      <h3 className={KICKER}>{titel}</h3>
      <div className="mt-2">{children}</div>
    </div>
  );
}

/** Langer Wortlaut: die ersten Zeilen, der Rest auf Wunsch. */
function Wortlaut({ text }: { text: string }) {
  const [offen, setOffen] = useState(false);
  const lang = text.length > 420;
  return (
    <>
      <blockquote className={cn(ZITAT, lang && !offen && "line-clamp-5")}>„{text.trim()}“</blockquote>
      {lang && (
        <button type="button" onClick={() => setOffen((o) => !o)} aria-expanded={offen}
          className="mt-1 inline-flex min-h-11 items-center text-sm font-medium text-primary hover:underline">
          {offen ? "Weniger zeigen" : "Ganzen Wortlaut zeigen"}
        </button>
      )}
    </>
  );
}

export function AusDenUnterlagen({ f, antraege, dossier }: { f: Felder | null; antraege?: Antrag[]; dossier?: Dossier | null }) {
  if (dossier && dossier.sections.length) return <MitDossier d={dossier} f={f} antraege={antraege} />;
  if (!f && !antraege?.length) return null;
  f = f ?? { template_number: null, document_url: null, office: null, proposed_decision: null, cost: null, climate: null, motions: [] };
  const hatInhalt = f.proposed_decision || f.motions.length || f.cost || f.climate || antraege?.length;
  if (!hatInhalt) return null;
  const vorlage = f.template_number ? `Vorlage ${f.template_number}` : null;
  return (
    <section aria-labelledby="aus-den-unterlagen" className="mt-6 rounded-2xl border border-border bg-card p-5 shadow-sm">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h2 id="aus-den-unterlagen" className="font-display text-base font-semibold text-foreground">Aus den Unterlagen</h2>
        {vorlage && f.document_url && (
          <a href={f.document_url} target="_blank" rel="noreferrer"
            className="inline-flex min-h-11 items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground">
            {vorlage} <ExternalLink className="h-3.5 w-3.5" aria-hidden />
          </a>
        )}
      </div>
      <Absender f={f} />

      <div className="mt-4 flex flex-col gap-4">
        {f.proposed_decision && (
          <Abschnitt titel="Was beschlossen werden soll">
            <Wortlaut text={f.proposed_decision} />
          </Abschnitt>
        )}

        {antraege && antraege.length > 0 && <Aenderungsantraege antraege={antraege} />}

        {!antraege?.length && f.motions.length > 0 && (
          <Abschnitt titel={f.motions.length === 1 ? "Antrag dazu" : `${f.motions.length} Anträge dazu`}>
            <ul className="flex flex-col gap-2">
              {f.motions.map((m) => {
                const partei = m.applicants[0] ? normalizeParty(m.applicants[0]) : null;
                const brand = partei ? partyBrand(partei) : null;
                return (
                  <li key={m.url ?? m.label}>
                    <a href={m.url ?? undefined} target="_blank" rel="noreferrer"
                      className="group flex min-h-11 items-start gap-2.5 rounded-xl border border-dashed border-border px-3 py-2.5 hover:bg-muted/50">
                      <span aria-hidden className="mt-1.5 h-2 w-2 flex-none rounded-full"
                        style={{ backgroundColor: brand?.bg ?? "hsl(var(--muted-foreground))" }} />
                      <span className="min-w-0 flex-1">
                        {m.applicants.length > 0 && (
                          <span className="block text-sm font-semibold text-foreground">{m.applicants.join(", ")}</span>
                        )}
                        <span className="block text-sm text-foreground">{m.label}</span>
                      </span>
                      <ExternalLink className="mt-1 h-3.5 w-3.5 flex-none text-muted-foreground group-hover:text-foreground" aria-hidden />
                    </a>
                  </li>
                );
              })}
            </ul>
          </Abschnitt>
        )}

        {f.cost && (
          <Abschnitt titel="Was es kostet">
            {f.cost.status === "none" ? (
              <p className="text-lese text-foreground">Laut Vorlage keine Kosten.</p>
            ) : (
              <Wortlaut text={f.cost.text} />
            )}
          </Abschnitt>
        )}

        {f.climate && (
          <Abschnitt titel="Klima-Check">
            {f.climate.relevant != null && (
              <p className="mb-1.5 text-sm font-medium text-foreground">
                {f.climate.relevant ? "Klimarelevant" : "Laut Vorlage nicht klimarelevant"}
              </p>
            )}
            <Wortlaut text={f.climate.text} />
          </Abschnitt>
        )}

      </div>
    </section>
  );
}

/** Mit Dossier: die belegten Abschnitte; der amtliche Wortlaut des
 *  Beschlussvorschlags klappt unter seinem Abschnitt auf, die Anträge stehen
 *  direkt darunter (Plan § 6.1). Der KI-Stern sitzt einmal an der Überschrift. */
function MitDossier({ d, f, antraege }: { d: Dossier; f: Felder | null; antraege?: Antrag[] }) {
  const [vorschlag, ...rest] = d.sections[0]?.key === "proposal" ? d.sections : [null, ...d.sections];
  return (
    <section aria-labelledby="aus-den-unterlagen" className="mt-6 rounded-2xl border border-border bg-card p-5 shadow-sm">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h2 id="aus-den-unterlagen" className="flex items-center gap-1 font-display text-base font-semibold text-foreground">
          Aus den Unterlagen
          <KiStern text="Automatisch aus der Vorlage und ihren Anlagen erstellt. Jede Angabe trägt ihren Beleg; verbindlich sind die Unterlagen im Ratsinfo." />
        </h2>
        <p className={KICKER}>{dossierStand(d)}</p>
      </div>
      <Absender f={f} />
      {d.added_after.length > 0 && (
        <p className="mt-2 text-sm text-muted-foreground">
          Danach dazugekommen: {d.added_after.join(", ")} — <a href="#unterlagen" className="text-primary underline">in den Unterlagen</a>
        </p>
      )}
      <div className="mt-4 flex flex-col gap-4">
        {vorschlag && (
          <div>
            <DossierAbschnitt s={vorschlag} />
            {f?.proposed_decision && (
              <details className="group mt-2">
                <summary className="flex min-h-11 cursor-pointer list-none items-center text-sm font-medium text-primary">
                  › Amtlicher Wortlaut
                </summary>
                <Wortlaut text={f.proposed_decision} />
              </details>
            )}
          </div>
        )}
        {antraege && antraege.length > 0 && <Aenderungsantraege antraege={antraege} />}
        {rest.map((s) => s && <DossierAbschnitt key={s.key} s={s} />)}
      </div>
    </section>
  );
}

/** Mitlesen (Plan § 6.2): Beim laufenden Punkt stehen die Änderungsanträge
 *  zuoberst — über sie wird gerade abgestimmt —, darunter, was beschlossen
 *  werden soll: aus dem Dossier mit Belegen, sonst der amtliche Wortlaut. */
export function JetztZurAbstimmung({ f, antraege, dossier }: { f: Felder | null; antraege?: Antrag[]; dossier?: Dossier | null }) {
  const vorschlag = dossier?.sections.find((s) => s.key === "proposal" && s.statements.length > 0) ?? null;
  const wortlaut = !vorschlag ? f?.proposed_decision ?? null : null;
  if (!antraege?.length && !vorschlag && !wortlaut) return null;
  return (
    <div className="flex flex-col gap-4">
      {antraege && antraege.length > 0 && <Aenderungsantraege antraege={antraege} />}
      {vorschlag && <DossierAbschnitt s={vorschlag} />}
      {wortlaut && (
        <Abschnitt titel="Was beschlossen werden soll">
          <Wortlaut text={wortlaut} />
        </Abschnitt>
      )}
    </div>
  );
}
