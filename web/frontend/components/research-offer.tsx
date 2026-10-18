"use client";

// <ResearchOffer> — unter der Antwort zu einem langen Vorgang die Gründliche
// Recherche anbieten (Plan „Akte“, Idee vom 03.10.2026).
//
// WARUM: Am Gold-Set nennt die Recherche bei denselben Vorgangsfragen deutlich
// mehr Pflichtfakten als die kurze Antwort (63,7 % gegen rund 51–56 %); sie
// schreibt aus, was die kurze Antwort im Kontext hat und weglässt. Der Abstand
// ist am größten, wo viel Stoff liegt.
//
// WANN, entscheidet das Backend (council/akte_suche.py, research_offer): ab
// sechs Stationen im Verlauf, nicht bei einer engen Zahlfrage. Hier wird nur
// dargestellt. Ob jemand annimmt, zählt die Nutzungsstatistik
// (research_offer_shown / research_offer_taken).

import { FlaskConical } from "lucide-react";

export type ResearchOfferData = { stations: number; span: string };

export function ResearchOffer({ offer, frei, onStart }: {
  offer: ResearchOfferData; frei?: number | null; onStart: () => void;
}) {
  return (
    <section aria-label="Gründliche Recherche anbieten"
      className="rounded-xl border border-border bg-card px-3.5 py-3">
      <p className="flex items-start gap-2 text-hinweis text-muted-foreground">
        <FlaskConical className="mt-1 h-4 w-4 shrink-0 text-primary" aria-hidden />
        <span>
          <span className="font-semibold text-foreground">Ein langer Vorgang:</span>{" "}
          {offer.stations} Stationen{offer.span ? ` über ${offer.span}` : ""}. Die Gründliche
          Recherche liest ihn ausführlich — alle Beratungen, Debatten und Mitteilungen — und
          schreibt einen Bericht mit Abschnitten.
        </span>
      </p>
      <div className="mt-2.5 flex flex-wrap items-center gap-x-3 gap-y-1.5 pl-6">
        <button type="button" onClick={onStart}
          className="inline-flex items-center gap-1.5 rounded-full border border-primary/30 bg-primary/5 px-3 py-1.5 text-[13px] font-medium text-primary transition-colors hover:bg-primary/10">
          {/* Nicht „Gründlich recherchieren": So heißt der Umschalter im Eingabefeld,
              der erst die NÄCHSTE Frage betrifft. Dieser Knopf legt sofort los. */}
          <FlaskConical className="h-3.5 w-3.5" aria-hidden /> Diese Frage gründlich recherchieren
        </button>
        <span className="text-meta text-muted-foreground">
          ~30 Sek{frei != null ? ` · noch ${frei} heute` : ""}
        </span>
      </div>
    </section>
  );
}
