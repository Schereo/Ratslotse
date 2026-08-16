"use client";

// „Bis wann reichen die Zahlen?" — der Datenstand des Haushalts-Bereichs.
//
// Kein Betreiber-Werkzeug, sondern die Antwort auf eine echte Leserfrage:
// Auf /haushalt steht der Plan für 2026, auf /haushalt/plan-ist die
// Abrechnung für 2024, auf /haushalt/pruefung Feststellungen bis 2023 — und
// jede dieser Seiten müsste sonst für sich erklären, warum. Die Ursache liegt
// meist bei der Stadt (seit dem Städtevergleich nicht mehr immer: dessen
// Reihen gibt das Land heraus): Der Plan kommt im Oktober für das
// kommende Jahr, die Abrechnung im September für das vorletzte. Zwischen
// September und Oktober liegt für einen Jahrgang deshalb immer nur die eine
// Hälfte vor. Das steht hier einmal, in Sätzen statt in einer Matrix.
//
// ZWEI TAKTE WAREN EINMAL ALLE. Mit dem Konzern-Bereich (#514) kam eine
// dritte Schicht dazu, und sie hat einen eigenen Rhythmus: Der konsolidierte
// Gesamtabschluss entsteht erst, wenn alle einbezogenen Betriebe geprüft
// sind, und liegt damit rund zwei Jahre hinter dem Haushaltsjahr
// (`finanzquellen.QUELLEN`, Februar / Jahrgang + 2). Der Einleitungssatz
// nennt Plan und Abrechnung deshalb weiter als die zwei bekannten Fälle,
// behauptet aber nicht mehr, es seien alle — welcher Takt für welche Schicht
// gilt, steht ohnehin an jeder Zeile. Wer eine vierte Schicht ergänzt, muss
// hier nichts nachziehen; die Liste kommt aus dem Endpunkt.
//
// Bewusst eine eigene Datei: Der Block hängt an einem eigenen Endpunkt, und
// eine Änderung an den Texten der Übersichtsseite soll ihn nicht anfassen.

import { Check, Clock } from "lucide-react";
import { Apparat } from "@/components/haushalt/quelle";
import { useFetch } from "@/lib/use-fetch";
import { cn } from "@/lib/utils";

export type Datenschicht = {
  key: string;
  label: string;
  was: string;
  jahrgaenge: number[];
  luecken: number[];
  neuester: number | null;
  offen: number[];
  ueberfaellig: number[];
  naechster_jahrgang: number;
  naechster_ab: string;
  erwarteter_monat: number;
  monat: string;
  herkunft: string;
  /** Die veröffentlichende Stelle im Klartext („Portal der Stadt"). */
  quelle: string;
  automatisch: boolean;
  /** Wie eine Einheit heißt („Teilhaushalte"), wo ein Jahrgang aus mehreren
   *  Dokumenten besteht — sonst null. */
  einheit: string | null;
  /** Je Jahrgang die Zahl der Einheiten, und wie viele der bestbelegte hat. */
  einheiten: Record<string, number>;
  einheiten_voll: number | null;
  /** Jahrgänge, die weniger Einheiten tragen als der bestbelegte. */
  teilweise: number[];
};

export type Antwort = { heute: string; schichten: Datenschicht[] };

/** „2017–2024" bzw. „2024" — und nichts, wo nichts ist. */
function spanne(jahre: number[]): string | null {
  if (jahre.length === 0) return null;
  const von = jahre[0], bis = jahre[jahre.length - 1];
  return von === bis ? String(von) : `${von}–${bis}`;
}

/** Wie eine Lücke *innerhalb* eines Jahrgangs heißt.
 *
 *  Nicht generisch formuliert: „Von 2023 haben wir 6 der 9 Einheiten" wäre
 *  Buchhaltersprache. Ein fehlender Teilhaushalt lässt sich zählen, eine
 *  fehlende Auswertungsebene nicht — die sagt man besser als Sache. */
const LUECKENTEXT: Record<string, (jahr: number, hat: number, voll: number) => string> = {
  Teilhaushalte: (jahr, hat, voll) =>
    `Für ${jahr} haben wir ${hat} von ${voll} Teilhaushalten.`,
  Ebenen: (jahr) =>
    `Für ${jahr} fehlt noch die Aufteilung auf die einzelnen Bereiche.`,
};

/** „a", „a und b", „a, b und c" — für Namen, die aus den Daten kommen und
 *  deren Zahl niemand vorher kennt. `join(" und ")` reichte, solange es eine
 *  einzige Schicht von Hand gab; bei dreien käme „a und b und c" heraus. */
function aufzaehlung(teile: string[]): string {
  if (teile.length <= 1) return teile[0] ?? "";
  return `${teile.slice(0, -1).join(", ")} und ${teile[teile.length - 1]}`;
}

/** Die Schichten, die der Cron nicht nachzieht — gruppiert nach der Stelle,
 *  die sie herausgibt.
 *
 *  Die Gruppierung ist der ganze Punkt: Die Fußzeile nannte pauschal das
 *  „Portal der Stadt", und das stimmte genau so lange, wie der Haushaltsplan
 *  die einzige Schicht von Hand war. Der Städtevergleich kommt vom Landesamt
 *  für Statistik — mit dem alten Satz hätte die Seite eine Landesbehörde zur
 *  Stadtverwaltung erklärt. Die Namen der Stellen kommen deshalb aus den
 *  Daten, genau wie die der Schichten. */
function vonHandNachStelle(schichten: Datenschicht[]): { quelle: string; labels: string[] }[] {
  const gruppen: { quelle: string; labels: string[] }[] = [];
  for (const s of schichten) {
    if (s.automatisch) continue;
    const treffer = gruppen.find((g) => g.quelle === s.quelle);
    if (treffer) treffer.labels.push(s.label);
    else gruppen.push({ quelle: s.quelle, labels: [s.label] });
  }
  return gruppen;
}

/** Was als Nächstes ansteht, als Satz.
 *
 *  Zwei Fälle, und der Unterschied ist der ganze Punkt: Ein Jahrgang, dessen
 *  Monat noch bevorsteht, ist keine Lücke — er ist einfach noch nicht
 *  erschienen. Erst danach lohnt der Hinweis, dass er auf sich warten lässt.
 *  „Fehlt" steht deshalb nirgends: Was die Stadt noch nicht veröffentlicht
 *  hat, fehlt uns nicht. */
export function ausblick(s: Datenschicht, heute: string): { text: string; wartet: boolean } {
  const jahr = s.naechster_jahrgang;
  const ab = new Date(s.naechster_ab);
  const monatJahr = `${s.monat} ${ab.getFullYear()}`;
  if (s.ueberfaellig.includes(jahr)) {
    return {
      text: `Der Jahrgang ${jahr} wäre seit ${monatJahr} zu erwarten und liegt noch nicht vor.`,
      wartet: true,
    };
  }
  if (new Date(heute) < ab) {
    return { text: `Der Jahrgang ${jahr} wird üblicherweise im ${monatJahr} vorgelegt.`, wartet: false };
  }
  return { text: `Der Jahrgang ${jahr} wird gerade erwartet (üblich: ${monatJahr}).`, wartet: false };
}

/** Was der Block verspricht — und was er ausdrücklich nicht verspricht.
 *
 *  Eigene Komponente, weil sie die einzige Stelle des Blocks ist, die einen
 *  Satz aus Daten *baut* statt ihn hinzuschreiben: Namen der Schichten, Namen
 *  der Stellen, Zahl der Gruppen — alles kommt aus dem Endpunkt. So lässt sie
 *  sich mit einem Stand füttern und lesen, ohne den ganzen Block samt
 *  Endpunkt aufzubauen. */
export function Fussnote({ schichten }: { schichten: Datenschicht[] }) {
  const vonHand = vonHandNachStelle(schichten);
  return (
    /* Der Satz stand pauschal über der ganzen Liste — und deren erste,
       prominenteste Zeile ist der Haushaltsplan, der gerade NICHT
       automatisch nachkommt. Was von Hand läuft, wird deshalb aus den
       Daten benannt statt mitversprochen. Das ist die eine Auskunft, die
       den Stand wirklich begrenzt: welche Schicht von selbst nachkommt und
       welche auf eine Hand wartet.

       ZWEI SÄTZE STANDEN BIS 16.08. ZU VIEL, beide über uns statt über die
       Zahlen: der Takt, in dem der Cron nachsieht („geprüft wird alle zwei
       Wochen"), und die Rechenprobe als Türsteher („Zahlen, die eine
       Rechenprobe des Dokuments nicht bestehen, bleiben draußen"). Beides
       läuft unverändert weiter und steht in der Technik-Doku. Für die Frage
       dieses Blocks — „bis wann reichen die Zahlen?" — ist es keine Antwort:
       Wo ein Jahrgang tatsächlich fehlt, sagt das die Zeile darüber
       (`luecken`, „Für 2019 liegen uns keine auswertbaren Zahlen vor"), und
       zwar am richtigen Ort und ohne Prüfzeugnis. DESIGNSPRACHE.md § 7. */
    <p className="mt-3.5 border-t border-dashed border-border pt-2.5 text-[11px] leading-relaxed text-muted-foreground">
      Was im Ratsinformationssystem veröffentlicht wird, tragen wir automatisch nach.
      {/* Aufzählung ohne Artikel und ohne Verb-Kongruenz: Die Namen kommen
          aus den Daten, „Nur den Haushaltsplan holen wir …" ließe sich für
          eine beliebige Liste nicht grammatisch bilden. Die Stelle steht in
          Klammern dahinter — ein Satzbau, der auch bei vier Stellen hält. */}
      {vonHand.length > 0 && <> Nicht dabei: {vonHand.map((g, i) => (
        <span key={g.quelle}>
          {i > 0 && "; "}{aufzaehlung(g.labels)} ({g.quelle})
        </span>
      ))} — die Zahlen dafür holen wir von Hand.</>}
    </p>
  );
}

export function Datenstand() {
  const { data } = useFetch<Antwort>("/council/haushalt/datenstand");
  // Still bleiben, solange nichts da ist: Ein Skelett für einen Nachtrag am
  // Seitenende wäre mehr Unruhe als Information.
  if (!data || data.schichten.length === 0) return null;
  // Die Spanne über ALLE Schichten — das, was in der zugeklappten Lade steht.
  // Ein „bis 2026" wäre gelogen: Der Plan reicht so weit, die Abrechnung
  // zwei Jahre kürzer. Beide Enden zu nennen ist die einzige Angabe, die für
  // die ganze Liste stimmt.
  const alleJahre = data.schichten.flatMap((s) => s.jahrgaenge);
  const gesamtspanne = spanne(
    [...new Set(alleJahre)].sort((a, b) => a - b));

  return (
    <Apparat
      kicker="Stand der Daten"
      zusatz={gesamtspanne
        ? `${gesamtspanne} · bis wann die Zahlen reichen`
        : "bis wann die Zahlen reichen"}
    >
      <p className="mt-3 max-w-[74ch] text-[12.5px] leading-relaxed text-muted-foreground">
        Die Stadt legt ihre Zahlen zu verschiedenen Zeiten vor: den Plan im Herbst für das
        kommende Jahr, die Abrechnung ein knappes Jahr nach dessen Ende — und was die
        Betriebe der Stadt einschließt, noch einmal später. Deshalb reicht nicht jede Seite
        gleich weit; welcher Takt wo gilt, steht an jeder Zeile.
      </p>

      <ul className="mt-3 flex flex-col gap-2.5">
        {data.schichten.map((s) => {
          const bereich = spanne(s.jahrgaenge);
          const { text, wartet } = ausblick(s, data.heute);
          // Nur der jüngste unvollständige Jahrgang wird benannt: Die älteren
          // sind eine Geschichte für sich und würden die Zeile zumauern.
          const offen = s.teilweise[s.teilweise.length - 1];
          const satz = s.einheit ? LUECKENTEXT[s.einheit] : undefined;
          const luecke = offen != null && satz && s.einheiten_voll
            ? satz(offen, s.einheiten[String(offen)], s.einheiten_voll)
            : null;
          return (
            <li key={s.key} className="flex flex-col gap-1">
              {/* Titel und Jahresspanne auf einer Zeile, in jeder Breite: Die
                  Spanne ist die Antwort, die hier jemand sucht. Unter dem Satz
                  stehend (nur `sm:` rechtsbündig) landete sie auf 375 px als
                  Letztes und links — also genau dort, wo niemand hinsieht. */}
              <div className="flex items-baseline justify-between gap-3">
                <span className="min-w-0 text-[13px] font-bold leading-snug">{s.label}</span>
                <span className="flex-none font-mono text-[11.5px] font-medium tabular-nums text-foreground/80">
                  {bereich ?? "—"}
                </span>
              </div>
              <span className="text-[12px] leading-relaxed text-muted-foreground">{s.was}</span>
              <span className={cn(
                "flex items-start gap-1.5 text-[11.5px] leading-relaxed",
                wartet ? "text-foreground/80" : "text-muted-foreground",
              )}>
                {wartet
                  ? <Clock size={12} strokeWidth={2} className="mt-[3px] flex-none" />
                  : <Check size={12} strokeWidth={2} className="mt-[3px] flex-none" />}
                <span>
                  {text}
                  {s.luecken.length > 0 && (
                    <> Für {s.luecken.join(", ")} liegen uns keine auswertbaren Zahlen vor.</>
                  )}
                  {/* Ein Jahrgang aus neun Dokumenten kann zu einem Drittel
                      gelesen sein und stünde trotzdem in derselben
                      Jahresspanne wie ein vollständiger. Das gehört
                      danebengeschrieben, nicht verschwiegen. */}
                  {luecke && <> {luecke}</>}
                </span>
              </span>
            </li>
          );
        })}
      </ul>

      <Fussnote schichten={data.schichten} />
    </Apparat>
  );
}
