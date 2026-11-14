"use client";

/* „Aus der Vorlage“ auf der Beschluss-Seite (Plan Vorlagen § 6.3): zwei
   Karten in den Stufen von „Aus den Unterlagen“ (`unterlagen-typo.ts`).

   1. „Vorschlag und Beschluss“ — nur, wo der Rat vom Vorschlag der Verwaltung
      abgewichen ist. Ein Umschalter zeigt die Änderungen (Wortdiff), den
      Vorschlag oder den Beschluss für sich.
   2. „So stand es in der Vorlage“ — das belegte Dossier als aufklappbare
      Gliederung.

   Vorher standen beide als Fließtext unter zwei 14-px-Zeilen: Der Inhalt war
   größer gesetzt als seine Überschriften (Tim, 14.11.2026: „sehr viel nicht
   übersichtlich formatierter Text … besser sortieren, hierarchisch“). */

import { useState } from "react";
import { FileText, Gavel, GitCompareArrows, type LucideIcon } from "lucide-react";
import { KiStern } from "@/components/ki-stern";
import { Segmented } from "@/components/ui/segmented";
import { Wortdiff } from "@/components/session/aenderungsantraege";
import { DossierGliederung, dossierStand, type Dossier } from "@/components/session/dossier";
import { INHALT, KARTENTITEL, META } from "@/components/session/unterlagen-typo";
import { cn } from "@/lib/utils";

type Sicht = "changes" | "proposal" | "decision";

// Dieselben Zeichen wie anderswo auf der Seite: der Vergleichspfeil steht
// schon an „Vom Vorschlag abgewichen“, das Dokument für die Vorlage, der
// Hammer für Beschlüsse (Befehlspalette, Verwaltungsausschuss).
const SICHTEN: { value: Sicht; label: string; icon: LucideIcon }[] = [
  { value: "changes", label: "Änderungen", icon: GitCompareArrows },
  { value: "proposal", label: "Vorschlag", icon: FileText },
  { value: "decision", label: "Beschluss", icon: Gavel },
];

const KARTE = "rounded-2xl border border-border bg-card p-4 shadow-sm sm:p-5";

function VorschlagUndBeschluss({ diff, vorschlag, beschluss, vorlageArt }: {
  diff: string[][]; vorschlag: string | null; beschluss: string | null; vorlageArt: string;
}) {
  const [sicht, setSicht] = useState<Sicht>("changes");
  // Ohne einen der beiden Texte gibt es nichts umzuschalten — dann nur der Vergleich.
  const mitUmschalter = Boolean(vorschlag && beschluss);
  return (
    <section aria-labelledby="vorschlag-und-beschluss" className={KARTE}>
      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
        <h3 id="vorschlag-und-beschluss" className={KARTENTITEL}>Vorschlag und Beschluss</h3>
        {mitUmschalter && (
          // Am Handy über die ganze Breite und mit schmalen Rändern: Bei 320 px
          // bleiben in der Karte 256 px, die drei Wörter brauchen sonst 310.
          // Die Zeichen erst ab 480 px — mit ihnen bräuchte der Umschalter
          // 331 px, bei 390 px Fensterbreite hat die Karte innen 326.
          <Segmented className="w-full print:hidden sm:w-auto [&_button]:px-1 sm:[&_button]:px-3 [&_svg]:hidden ab-lesezeile:[&_svg]:block"
            value={sicht} onChange={setSicht} options={SICHTEN} />
        )}
      </div>
      {sicht === "changes" || !mitUmschalter ? (
        <>
          <p className={cn(META, "mt-1")}>
            <del className="decoration-signal/70">Durchgestrichen</del> stand im Vorschlag der Verwaltung,{" "}
            <ins className="rounded-sm bg-signal/10 px-0.5 font-medium text-foreground no-underline">hervorgehoben</ins> steht nur im Beschluss.
          </p>
          <div className="mt-3"><Wortdiff diff={diff} /></div>
        </>
      ) : sicht === "proposal" ? (
        <>
          <p className={cn(META, "mt-1")}>Der Beschlussvorschlag der Verwaltung, wie er in der {vorlageArt} stand.</p>
          <p className={cn(INHALT, "mt-3 whitespace-pre-line")}>{vorschlag}</p>
        </>
      ) : (
        <>
          <p className={cn(META, "mt-1")}>Der Beschluss, wie ihn das Sitzungsprotokoll festhält.</p>
          <p className={cn(INHALT, "mt-3 whitespace-pre-line")}>{beschluss}</p>
        </>
      )}
    </section>
  );
}

export function AusDerVorlage({ diff, vorschlag, beschluss, vorlageArt, dossier }: {
  /** Wortdiff Vorschlag ↔ Beschluss; die Karte erscheint nur mit einer echten Änderung. */
  diff?: string[][] | null;
  vorschlag?: string | null;
  beschluss?: string | null;
  /** „Beschlussvorlage“, „Vorlage“ … — das Wort für das Dokument. */
  vorlageArt: string;
  dossier?: Dossier | null;
}) {
  const geaendert = diff?.some(([op]) => op !== "=") ? diff : null;
  if (!geaendert && !dossier) return null;
  return (
    <div className="flex flex-col gap-3">
      {geaendert && (
        <VorschlagUndBeschluss diff={geaendert} vorschlag={vorschlag ?? null} beschluss={beschluss ?? null} vorlageArt={vorlageArt} />
      )}
      {dossier && (
        <section aria-labelledby="so-stand-es" className={KARTE}>
          <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
            <h3 id="so-stand-es" className={cn(KARTENTITEL, "flex items-center gap-1")}>
              So stand es in der Vorlage
              <KiStern text="Automatisch aus der Vorlage und ihren Anlagen erstellt, Stand vor der Sitzung. Beschlossen wurde, was oben steht." />
            </h3>
            <p className={META}>{dossierStand(dossier)}</p>
          </div>
          <div className="mt-3"><DossierGliederung d={dossier} /></div>
        </section>
      )}
    </div>
  );
}
