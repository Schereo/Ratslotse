"use client";

// „Lotti erklärt's einfach" für den Haushalts-Bereich.
//
// Der Haushalt ist der sperrigste Stoff, den Ratslotse zeigt: Doppik-Vokabular,
// Millionen ohne Bezugsgröße, Zuständigkeiten quer über drei Ebenen. Lotti
// steht hier in ihrer angestammten Rolle (Beobachterin, die einordnet — nie
// Autorin einer Antwort) und übersetzt genau eine Sache pro Karte in
// Alltagssprache. Regeln aus der Designsprache: max. drei Sätze, keine
// Fachwörter ohne Erklärung, keine Bewertung („zu viel“, „zu wenig“).
//
// Zwei Formen, mehr braucht es nicht:
// - `LottiErklaert`: die Karte an einer schweren Stelle im Fluss.
// - `LottiVergleich`: eine große Zahl in eine Alltagsgröße übersetzt
//   (pro Kopf, pro Tag) — der Rechenweg steht dabei, weil er unsere
//   Rechnung ist und keine amtliche Kennzahl.

import { Mascot } from "@/components/mascot";
import { GlossaryText } from "@/components/glossary-text";
import { cn } from "@/lib/utils";

export function LottiErklaert({
  titel, text, pose = "point", className,
}: {
  titel: string;
  text: string;
  pose?: "point" | "search" | "wave" | "confused";
  className?: string;
}) {
  return (
    // DER DECKEL SITZT AN DER KARTE, NICHT AM TEXT (Tim, 21.08.2026: „hier ist
    // der ganze rechte Bereich frei, das sieht absolut scheiße aus").
    //
    // Vorher war es umgekehrt: volle Kartenbreite, Text auf 76ch gedeckelt.
    // Der Deckel war richtig — ohne ihn lief der Erklärtext auf 1.440 px über
    // 220 Zeichen je Zeile, während die Einstiegstexte derselben Seiten bei
    // rund 95 enden. Nur stand er an der falschen Stelle: In einer 1.496 px breiten
    // Karte blieben rechts 873 px leer, und eine halb gefüllte Kiste sieht
    // nicht nach Absicht aus, sondern nach Fehler.
    //
    // Jetzt endet die KARTE dort, wo der Text endet. Der Leerraum liegt damit
    // außerhalb — er ist Seitenrand statt Loch. Und das ist auch inhaltlich
    // richtig: Das hier ist ein `aside`, keine Hauptaussage; dass er schmaler
    // steht als die Karten des Flusses, sagt genau das.
    //
    // `70ch` AN DER KARTE, und das sind NICHT 70 Zeichen Text — hier stecken
    // ZWEI Umrechnungen drin (beide in DESIGNSPRACHE.md § 4 erklärt):
    //   1. `ch` misst die Schrift des Elements, an dem es steht — hier die
    //      16 px der Karte, während der Erklärtext 13 px hat. Dazu gehen links
    //      48 px Bild + 14 px Abstand + 2 × 14 px Polsterung ab, zusammen 92 px.
    //      70ch = 706,6 px Karte − 92 px = 614,6 px Textspalte = 74,9ch bei 13 px.
    //   2. Ein `ch` ist die Ziffernbreite, nicht ein Prosa-Zeichen. In Inter
    //      ist es 1,26 Zeichen breit: 74,9ch = **95 Zeichen je Zeile**.
    // Der Wert stand bis 24.08.2026 auf `74ch` und lief damit auf 101 Zeichen —
    // der einzige Ausreißer über 100 im Bereich, der auf einen Rechenfehler
    // zurückging und nicht auf eine Entscheidung. Der Kommentar behauptete
    // „~80 Zeichen", das waren in Wahrheit 80 **ch**. Nachgemessen im Browser
    // (Range.getClientRects über 120 Absätze echten Seitentexts).
    <aside className={cn(
      "flex max-w-[70ch] gap-3.5 rounded-2xl border border-primary/20 bg-primary/[0.04] p-3.5",
      className,
    )}>
      <Mascot pose={pose} decorative className="h-11 w-11 flex-none sm:h-12 sm:w-12" />
      <div className="min-w-0">
        <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-primary">
          {titel}
        </p>
        <p className="mt-1.5 text-[13px] leading-relaxed text-foreground/90">
          <GlossaryText text={text} />
        </p>
      </div>
    </aside>
  );
}

/** Große Zahl → Alltagsgröße. `pro_kopf` rechnet mit der Einwohnerzahl, die
 *  als Quelle mitgegeben wird; ohne sie erscheint der Baustein nicht. */
export function LottiVergleich({
  betragMio, population, was, className,
}: {
  betragMio: number;
  population: number;
  /** Wofür das Geld ist — steht im Satz („für Kitas und Jugendhilfe"). */
  was: string;
  className?: string;
}) {
  if (!population) return null;
  const proKopf = Math.round((betragMio * 1_000_000) / population);
  const proKopfMonat = Math.round(proKopf / 12);
  return (
    // Dieselbe Bauform wie `LottiErklaert` — Deckel an der Karte, s. dort.
    // Auch dieselben 70ch: Der Wert muss mit der Schwester zusammenpassen,
    // beide Kästen stehen auf denselben Seiten untereinander.
    <aside className={cn(
      "flex max-w-[70ch] gap-3.5 rounded-2xl border border-primary/20 bg-primary/[0.04] p-3.5",
      className,
    )}>
      <Mascot pose="point" decorative className="h-11 w-11 flex-none sm:h-12 sm:w-12" />
      <div className="min-w-0">
        <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-primary">
          Was heißt das pro Kopf?
        </p>
        <p className="mt-1.5 text-[13px] leading-relaxed text-foreground/90">
          {betragMio.toLocaleString("de-DE", { maximumFractionDigits: 1 })}&#8239;Mio.&nbsp;€ {was} sind{" "}
          <strong>{proKopf.toLocaleString("de-DE")}&nbsp;€ pro Einwohner*in im Jahr</strong>
          {proKopfMonat >= 1 && <> — rund {proKopfMonat.toLocaleString("de-DE")}&nbsp;€ im Monat</>}.
        </p>
        <p className="mt-1 text-[11px] leading-relaxed text-muted-foreground">
          Unsere Rechnung: Betrag geteilt durch {population.toLocaleString("de-DE")} Einwohner*innen.
          Keine amtliche Kennzahl — die Stadt weist sie so nicht aus.
        </p>
      </div>
    </aside>
  );
}
