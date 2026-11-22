"use client";

/* „Mein Mitschrieb" beim Mitlesen (Schalter `mitschrieb`, Plan
   `docs/plan-sitzungsseite-kurs.md` 3.17 und `docs/plan-notizen-verschluesselt.md`
   § 1, Bild `docs/entwurf-sitzungsseite/bilder/mitlesen-desktop-zustand-mitschrieb.png`).

   Je Punkt: was passiert ist (eigene Einschätzung) und ein Text. Verschlüsselt
   wie die Notizen, Art `transcript`. Das eigene Ergebnis färbt die Boje nur
   im EIGENEN Kurs — nie die öffentliche Seite, und das amtliche Ergebnis aus
   dem Protokoll geht immer vor. */

import { OUTCOME_DOT_CLS } from "@/components/decision-ui";
import { Konflikt } from "@/components/notiz/meine-notiz";
import { Fuss, Karte, NotizSchloss, SperrenKnopf, type Offen } from "@/components/notiz/notiz-schloss";
import { statusText, useVerschluesselt } from "@/components/notiz/use-verschluesselt";
import type { TranscriptDoc } from "@/lib/notizen";
import { cn } from "@/lib/utils";

const FUSS = "Nur für dich und nicht das amtliche Ergebnis: Das steht hier, sobald das Protokoll vorliegt. "
  + "Dein Mitschrieb wird auf deinem Gerät verschlüsselt, bevor er gespeichert wird.";
const leer: TranscriptDoc = { text: "", outcome: null };
const istLeer = (d: TranscriptDoc) => !d.text.trim() && !d.outcome;
const WAHL: { key: NonNullable<TranscriptDoc["outcome"]>; label: string }[] = [
  { key: "accepted", label: "Angenommen" },
  { key: "rejected", label: "Abgelehnt" },
  { key: "postponed", label: "Vertagt" },
  { key: "noted", label: "Zur Kenntnis" },
];

export function Mitschrieb({ ksinr, itemNumber, label, onOutcome }: {
  ksinr: number; itemNumber: string; label: string;
  onOutcome?: (itemNumber: string, outcome: TranscriptDoc["outcome"]) => void;
}) {
  const titel = `Mein Mitschrieb zu ${label}`;
  return (
    <NotizSchloss titel={titel} id="mein-mitschrieb" fuss={FUSS}
      angebot="Halte fest, was bei diesem Punkt passiert ist. Nur du kannst es lesen.">
      {(o) => <Editor key={itemNumber} o={o} ksinr={ksinr} itemNumber={itemNumber} titel={titel} onOutcome={onOutcome} />}
    </NotizSchloss>
  );
}

function Editor({ o, ksinr, itemNumber, titel, onOutcome }: {
  o: Offen; ksinr: number; itemNumber: string; titel: string;
  onOutcome?: (itemNumber: string, outcome: TranscriptDoc["outcome"]) => void;
}) {
  const v = useVerschluesselt<TranscriptDoc>(o.dk, o.keyVersion, "agenda_item", `${ksinr}|${itemNumber}`, "transcript", leer, istLeer);
  const setze = (neu: TranscriptDoc) => {
    v.setDoc(neu);
    if (neu.outcome !== v.doc.outcome) onOutcome?.(itemNumber, neu.outcome);
  };
  return (
    <Karte titel={titel} id="mein-mitschrieb" rechts={<SperrenKnopf owner={o.owner} />}>
      <fieldset disabled={v.stand === "lädt"}>
        <legend className="text-sm text-muted-foreground">Was ist passiert?</legend>
        <div className="mt-2 flex flex-wrap gap-2">
          {WAHL.map((w) => {
            const an = v.doc.outcome === w.key;
            return (
              <button key={w.key} type="button" aria-pressed={an}
                onClick={() => setze({ ...v.doc, outcome: an ? null : w.key })}
                className={cn("inline-flex min-h-11 items-center gap-2 rounded-xl border px-3 text-sm font-medium transition-colors",
                  an ? "border-primary bg-primary/[0.08] text-foreground ring-2 ring-primary/25" : "border-border bg-card text-foreground hover:bg-accent")}>
                <span className={cn("h-2.5 w-2.5 rounded-full", OUTCOME_DOT_CLS[w.key])} aria-hidden /> {w.label}
              </button>
            );
          })}
        </div>
      </fieldset>
      <label htmlFor="mitschrieb-text" className="sr-only">Mein Mitschrieb</label>
      <textarea id="mitschrieb-text" value={v.doc.text} disabled={v.stand === "lädt"} rows={4} maxLength={8000}
        onChange={(e) => setze({ ...v.doc, text: e.target.value })} onBlur={() => { void v.jetztSpeichern(); }}
        placeholder="Was wurde gesagt, was ist offen?"
        className="mt-3 w-full resize-y rounded-xl border border-input bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" />
      {v.stand === "konflikt" && (
        <Konflikt text={v.konflikt?.doc?.text ?? ""} was="Mitschrieb"
          onUebernehmen={() => { v.uebernehmen(); onOutcome?.(itemNumber, v.konflikt?.doc?.outcome ?? null); }}
          onBehalten={v.behalten} />
      )}
      <p className="mt-1 min-h-5 text-meta text-muted-foreground" aria-live="polite">{statusText(v.stand, v.version, v.um)}</p>
      <Fuss text={FUSS} />
    </Karte>
  );
}
