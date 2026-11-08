"use client";

// Woher eine Kandidatur kommt — die Zeile unter dem Namen auf /wahlabend/ob
// und /wahlabend/stichwahl.
//
// Eigene Datei, weil `/wahlabend/ob` sie bis 11/2026 aus `stichwahl.tsx`
// importierte und damit die ganze Stichwahl-Seite (Karte, Verlauf, Momente,
// Simulator) in seinen ersten Aufruf zog: 25 KB gzip für eine Zeile Text.

import { useState } from "react";
import { ChevronDown } from "lucide-react";
import { Aufklapp } from "@/components/aufklapp";
import { cn } from "@/lib/utils";
import type { StichwahlKandidat } from "@/lib/stichwahl";

/** Was der Parteiname über dem Namen NICHT sagt: ob die Person Mitglied ist,
 *  und wer sie sonst noch unterstützt.
 *
 *  Beides steht nicht in der amtlichen Bekanntmachung — das Backend liefert
 *  es nur mit eigener Quelle, und die steht hier als Beleg daneben. Ohne
 *  Angaben bleibt die Zeile weg; sie ist kein Platzhalter. */
export function Herkunft({ k }: { k: StichwahlKandidat }) {
  // Eingeklappt, was nur Erklärung ist (Tim 23.09.2026: „sehr viel Text
  // dafür, dass es eigentlich nur ein Disclaimer ist"): Die Zeile mit den
  // Parteien bleibt stehen, die Begründung zum Stimmzettel und die Belege
  // kommen auf Tipp.
  const [offen, setOffen] = useState(false);
  // Drei Stufen, die der Stimmzettel nicht unterscheidet: aufgestellt (eine
  // eigene Versammlung, wie bei Grünen UND CDU für Rohr), unterstützt (ein
  // Beschluss ohne Aufstellung, wie Volt) — und darüber die Frage, warum
  // dann nur eine Partei auf dem Zettel steht (`ballot_note`).
  const aufgestellt = k.co_nominated_by.length
    ? `aufgestellt von ${[k.party, ...k.co_nominated_by].filter(Boolean).join(" und ")}`
    : null;
  const teile = [
    k.independent ? "parteilos" : null,
    aufgestellt,
    k.supported_by.length ? `unterstützt von ${k.supported_by.join(", ")}` : null,
  ].filter(Boolean);
  if (!teile.length) return null;
  // Mehrere Belege bekommen ihren Absender als Beschriftung: Seit Volt
  // (15.09.2026) neben der CDU steht, deckt EIN Link nicht mehr beide
  // Aussagen — und zwei gleich beschriftete „Beleg"-Links wären ein Rätsel.
  const mehrere = k.note_sources.length > 1;
  const mehr = Boolean(k.ballot_note) || k.note_sources.length > 0;
  return (
    <div className="mt-1.5 text-[12.5px] leading-relaxed text-muted-foreground">
      <p>{teile.join(" · ")}</p>
      {mehr ? (
        <>
          <button
            type="button"
            onClick={() => setOffen((o) => !o)}
            aria-expanded={offen}
            className="mt-0.5 inline-flex items-center gap-1 rounded-md text-[12px] font-medium text-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            {k.ballot_note ? `Warum nur ${k.party || "eine Partei"} auf dem Stimmzettel?` : "Belege"}
            <ChevronDown className={cn("h-3.5 w-3.5 transition-transform duration-fluss", offen && "rotate-180")} aria-hidden />
          </button>
          <Aufklapp offen={offen}>
            <p className="pt-1 text-[12px] leading-relaxed">
              {k.ballot_note}
              {k.note_sources.map((quelle, i) => (
                <span key={quelle}>
                  {i === 0 ? (k.ballot_note ? " " : "") : " · "}
                  <a
                    href={quelle}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="font-medium text-primary underline-offset-2 hover:underline"
                  >
                    {mehrere ? `${absender(quelle)} ↗` : "Beleg ↗"}
                  </a>
                </span>
              ))}
            </p>
          </Aufklapp>
        </>
      ) : null}
    </div>
  );
}

/** „gruene-oldenburg.de" aus einer Beleg-Adresse — ohne „www.", damit die
 *  Zeile schmal bleibt. Eine kaputte Adresse gibt es selbst zurück, statt zu
 *  werfen: Ein Beleg-Link ist nie eine Seite wert. */
function absender(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}
