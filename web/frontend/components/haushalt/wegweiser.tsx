// Wegweiser zu den Vertiefungsseiten des Haushalts-Bereichs.
//
// Die drei Karten standen als reine Textkacheln zwischen zwei großen
// Diagramm-Panels und gingen dort unter (Tim, 16.08.). Sie sind aber der
// einzige Weg in die Tiefe — deshalb tragen sie ein Piktogramm im
// Primär-Tint, den Titel in der Display-Schrift und einen Pfeil, der beim
// Überfahren mitgeht. Farbe bleibt Hafenblau: Signal-Orange ist im Haushalt
// dem Minus vorbehalten.
//
// AUS SECHS KACHELN WURDE EIN WEG (16.08., zweite Runde). Sechs gleich große
// Karten nebeneinander sind ein Archiv, keine Führung: Wer zum ersten Mal
// hier ist, sieht sechs gleichwertige Angebote und keinen Anfang. Sie tragen
// deshalb Schritt-Nummern und stehen in der Reihenfolge, in der die Fragen
// aufeinander aufbauen. Die Nummern sind eine Empfehlung, keine Sperre.
//
// AUS SIEBEN SCHRITTEN WERDEN VIER STUFEN (16.08., dritte Runde). Der
// Bereich hat inzwischen zwölf Unterseiten, und drei davon fand niemand:
// `/haushalt/jahr` und `/haushalt/vergleich` waren im ganzen Frontend von
// keinem einzigen `href` erreichbar, `/haushalt/bereiche` nur rückwärts —
// über die Detailseite eines einzelnen Bereichs, also von innen nach außen.
//
// Die naheliegende Reparatur wäre gewesen, drei Kacheln anzuhängen. Zehn
// durchnummerierte Karten sind aber genau das Problem, das die zweite Runde
// gelöst hat, nur größer: Eine Nummer sagt „danach kommt elf", sie sagt nicht,
// WOFÜR man weiterliest. Deshalb liegen die Schritte jetzt in vier benannten
// Stufen, und jede Stufe sagt in einem Satz, welche Frage sie beantwortet.
// Die Nummern laufen durch — es bleibt ein Weg, er hat nur sichtbare
// Abschnitte:
//
//   1–5   Die Zahlen      Woher das Geld kommt, wohin es geht, was fest ist,
//                         was einzelne Aufgaben kosten — und was gebaut wird.
//   6–7   Die Gegenprobe  Ein Haushalt ist ein Plan; was daraus wurde, steht
//                         im Jahresabschluss, und geprüft wird er auch.
//   8–9   Der Rahmen      Der Kernhaushalt ist rund zwei Drittel der Stadt,
//                         und Oldenburg steht nicht allein da.
//   10–11 Mitreden        Wann entschieden wird, und was sich drehen ließe.
//
// „Was wird gebaut?" kam 08/2026 als Schritt 5 dazu — mit der ersten Schicht,
// die den FINANZhaushalt liest. Es steht am Ende der Zahlen-Stufe und nicht
// vorn, weil es die einzige Seite ist, die einen anderen Haushalt zeigt als
// die vier davor: Erst wenn klar ist, was im Ergebnishaushalt steht, ist die
// Aussage „und hier steht das alles NICHT drin" überhaupt eine.
//
// Drei Entscheidungen dahinter, die man sonst rückgängig macht:
//
//  * **„Was kostet eigentlich …?" bleibt hinter „Muss oder kann?".** Es ist
//    die griffigste Seite, beantwortet aber eine Frage, die erst Sinn ergibt,
//    wenn man weiß, dass der größte Teil des Geldes gar nicht zur Disposition
//    steht. Das stand schon in der zweiten Runde hier und gilt weiter.
//  * **Der Städtevergleich steht spät (Schritt 9), nicht vorn.** „Steht
//    Oldenburg besser da als Osnabrück?" ist eine Frage, die sich erst stellt,
//    wenn man die eigenen Zahlen kennt — und die Seite selbst besteht zur
//    Hälfte aus der Begründung, warum der Vergleich bei den Ausgaben nicht
//    trägt. Vorn gelesen wäre sie eine Absage an eine Frage, die noch niemand
//    gestellt hat.
//  * **Das Labor rutscht von Platz 4 ans Ende.** An Stellschrauben zu drehen
//    ist der letzte Schritt, nicht der zweite: Vorher fehlt der Bezug, an dem
//    sich ablesen ließe, ob eine Bewegung viel ist.
//
// **`/haushalt/konzern` steht auf Schritt 8.** Die Seite schreibt ihre Nummer
// selbst in den Kicker (`konzern/page.tsx`, „Stadtfinanzen Oldenburg ·
// Schritt 8"). Wer die Reihenfolge oben ändert, ändert dort mit, sonst
// widersprechen sich zwei Seiten still — genau das ist beim Einfügen von
// „Was wird gebaut?" (08/2026) passiert und dort nachgezogen worden: Die
// Seite trug bis dahin Schritt 7.
//
// **Zwei der dreizehn Seiten haben bewusst keinen Schritt.** `/haushalt/bereich`
// und `/haushalt/steuer` sind Steckbriefe: Sie brauchen einen Query-Parameter
// und öffnen ohne ihn den Vorgabefall. Als eigener Schritt stünde ein
// beliebiger Bereich neben elf Fragen. Sie werden am Fuß benannt, damit die
// Zählung „elf Schritte, dreizehn Seiten" nicht wie eine Lücke aussieht.
//
// FORM: eine Karte, nicht zehn. Zehn Karten sind auf 375 px eine Liste ohne
// Ende — die Stufen wären zwischen ihnen untergegangen, und genau sie sind
// die Orientierung. Die Schritte sind deshalb Zeilen in einer Karte,
// abschnittsweise durch eine gestrichelte Linie getrennt: Der sichtbare
// Rhythmus ist vier, nicht zehn. Gemessen bei 375 px: 1.426 px für zehn Ziele
// gegen 1.322 px für die sieben Kacheln vorher — 8 % mehr Höhe für 43 % mehr
// Inhalt, also rund ein Viertel weniger Platz je Eintrag.
//
// Zwei Spalten ab 768 px **Container-Innenbreite**, nicht Fensterbreite
// (Designsprache §4): Am Desktop liegt der Block neben der Seitenleiste, auf
// dem iPad nicht — dieselbe Fensterbreite meint zwei verschiedene
// Platzangebote. Die Polsterung der Karte zählt dabei nicht mit; ein iPad
// hochkant (834 px Fenster → 746 px innen) bleibt deshalb einspaltig. Das ist
// Absicht: 746 px auf zwei Spalten wären zwei schmale statt einer lesbaren.

import Link from "next/link";
import {
  ArrowLeftRight, BookOpenText, Building2, CalendarDays, ChevronRight, Coins,
  GitCompareArrows, HardHat, Receipt, Scale, SearchCheck, SlidersHorizontal,
} from "lucide-react";
import { cn } from "@/lib/utils";

type Ziel = {
  href: string;
  Icon: typeof Coins;
  titel: string;
  text: string;
};

const STUFEN: { kicker: string; frage: string; ziele: Ziel[] }[] = [
  {
    kicker: "Die Zahlen",
    frage: "Woher das Geld kommt, wohin es geht — und wie wenig davon frei ist.",
    ziele: [
      {
        href: "/haushalt/einnahmen",
        Icon: Coins,
        titel: "Woher kommt das Geld?",
        text: "Alle Einnahmequellen — und bei welchen der Rat etwas zu entscheiden hat.",
      },
      {
        href: "/haushalt/bereiche",
        Icon: BookOpenText,
        titel: "Was steckt hinter den Namen?",
        text: "„Soziales“, „Finanzmanagement“: die Teilhaushalte im Klartext, mit Betrag.",
      },
      {
        href: "/haushalt/pflicht",
        Icon: Scale,
        titel: "Muss oder kann?",
        text: "Wie viel gesetzlich vorgeschrieben ist — und wie die Stadt selbst das sieht.",
      },
      {
        href: "/haushalt/produkte",
        Icon: Receipt,
        titel: "Was kostet eigentlich …?",
        text: "Archiv, Feuerwehr, Schwimmbad: einzelne Aufgaben mit Kosten und Auftrag.",
      },
      {
        href: "/haushalt/investitionen",
        Icon: HardHat,
        titel: "Was wird gebaut?",
        text: "Neubauten, Fahrzeuge, Grundstücke — der Haushalt, in dem die vier Seiten davor nicht vorkommen.",
      },
    ],
  },
  {
    kicker: "Die Gegenprobe",
    frage: "Ein Haushalt ist ein Plan. Was daraus wurde, steht woanders — und wird geprüft.",
    ziele: [
      {
        href: "/haushalt/plan-ist",
        Icon: GitCompareArrows,
        titel: "Geplant und geworden",
        text: "Was am Jahresende wirklich zusammenkam — aus den Jahresabschlüssen.",
      },
      {
        href: "/haushalt/pruefung",
        Icon: SearchCheck,
        titel: "Die Prüfung",
        text: "Was das Rechnungsprüfungsamt an den Abschlüssen beanstandet — im Wortlaut.",
      },
    ],
  },
  {
    kicker: "Der Rahmen",
    frage: "Der Haushalt ist nicht die ganze Stadt, und Oldenburg steht nicht allein da.",
    ziele: [
      {
        href: "/haushalt/konzern",
        Icon: Building2,
        titel: "Und ist das die ganze Stadt?",
        text: "Klinikum, Busse, Bäder, Gebäude: was neben dem Haushalt noch läuft.",
      },
      {
        href: "/haushalt/vergleich",
        Icon: ArrowLeftRight,
        titel: "Steht Oldenburg besser da?",
        text: "Steuerkraft und Hebesätze der kreisfreien Städte — und warum Ausgaben sich nicht vergleichen lassen.",
      },
    ],
  },
  {
    kicker: "Mitreden",
    frage: "Wann entschieden wird — und was sich rechnerisch drehen ließe.",
    ziele: [
      {
        href: "/haushalt/jahr",
        Icon: CalendarDays,
        titel: "Wann wird das entschieden?",
        text: "Der Weg durch den Rat, Station für Station, aus acht Haushaltsjahren.",
      },
      {
        href: "/haushalt/labor",
        Icon: SlidersHorizontal,
        titel: "Haushalts-Labor",
        text: "Selbst an den Stellschrauben drehen und sehen, was das ausmacht.",
      },
    ],
  },
];

/** Die Schritt-Nummern laufen über alle Stufen durch — einmal beim Laden
 *  gerechnet, damit keine Stelle sie von Hand mitzählt. */
const STUFEN_NUMMERIERT = (() => {
  let n = 0;
  return STUFEN.map((stufe) => {
    const ziele = stufe.ziele.map((z) => ({ ...z, nr: ++n }));
    return { ...stufe, ziele, von: ziele[0].nr, bis: ziele[ziele.length - 1].nr };
  });
})();

const GESAMT = STUFEN_NUMMERIERT[STUFEN_NUMMERIERT.length - 1].bis;

export function Wegweiser() {
  return (
    <div className="@container/weg rounded-2xl border border-border bg-card p-4 shadow-sm sm:p-5">
      {/* Als <h2>, obwohl es wie ein Kicker aussieht: Der Block trägt darunter
          vier <h3>, und die Seite eine <h1> auf der Anzeigetafel. Ohne diese
          Stufe spränge die Gliederung von 1 auf 3. */}
      <h2 className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
        Der Weg durch den Haushalt
      </h2>
      <p className="mt-1 max-w-[76ch] text-[12.5px] leading-relaxed text-muted-foreground">
        Der Bereich hat {GESAMT} Vertiefungsseiten, und sie bauen aufeinander auf: erst die
        Zahlen selbst, dann die Gegenprobe, dann der Blick über den Haushalt hinaus, zuletzt die
        Frage, was sich ändern ließe. Wer zum ersten Mal hier ist, fängt oben an — einzeln
        funktioniert aber jede Seite für sich.
      </p>

      {STUFEN_NUMMERIERT.map((stufe) => (
        <section key={stufe.kicker} className="mt-3.5 border-t border-dashed border-border pt-3">
          {/* Kicker links, Schritt-Spanne rechts — die ehrliche Mengenangabe
              an derselben Stelle wie überall sonst (Designsprache §5). */}
          <div className="flex items-baseline justify-between gap-3">
            <h3 className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-foreground/70">
              {stufe.kicker}
            </h3>
            <span className="flex-none font-mono text-[10px] font-medium tabular-nums text-muted-foreground">
              {stufe.von === stufe.bis
                ? `Schritt ${stufe.von}`
                : `Schritt ${stufe.von}–${stufe.bis}`}
            </span>
          </div>
          <p className="mt-0.5 max-w-[74ch] text-[12px] leading-relaxed text-muted-foreground">
            {stufe.frage}
          </p>

          {/* Zwei Spalten am Container (Schwelle 768 px), nicht am Fenster.
              Ein `grid` füllt Zeilen, die Nummern laufen also links-rechts
              weiter — genau die Leserichtung, die sie behaupten. */}
          <div className="mt-1.5 @3xl/weg:grid @3xl/weg:grid-cols-2 @3xl/weg:gap-x-5">
            {stufe.ziele.map((z) => (
              <Link key={z.href} href={z.href}
                className="group -mx-2 flex items-start gap-3 rounded-xl px-2 py-1.5 transition-colors hover:bg-primary/[0.05]">
                <span aria-hidden className={cn(
                  "mt-0.5 flex h-8 w-8 flex-none items-center justify-center rounded-xl",
                  "bg-primary/10 text-primary transition-colors group-hover:bg-primary/[0.16]",
                )}>
                  <z.Icon size={17} strokeWidth={2} />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="flex items-baseline gap-1.5">
                    {/* „1 Woher kommt das Geld?" liest eine Sprachausgabe als
                        nackte Ziffer vor. Das Wort steht deshalb da — nur
                        nicht im Bild, wo die Spalte es schon sagt. */}
                    <span className="flex-none font-mono text-[10.5px] font-medium tabular-nums text-muted-foreground">
                      <span className="sr-only">Schritt </span>{z.nr}
                    </span>
                    <span className="font-display text-[14px] font-bold leading-snug tracking-tight">
                      {z.titel}
                    </span>
                  </span>
                  <span className="mt-0.5 block text-[12px] leading-relaxed text-muted-foreground">
                    {z.text}
                  </span>
                </span>
                <ChevronRight aria-hidden size={15} strokeWidth={2}
                  className="mt-1.5 flex-none text-muted-foreground transition-transform group-hover:translate-x-0.5 group-hover:text-primary" />
              </Link>
            ))}
          </div>
        </section>
      ))}

      {/* Ohne diesen Satz sähe „elf Schritte" nach einer Lücke aus: Der
          Bereich hat dreizehn Unterseiten. Die beiden übrigen sind Steckbriefe
          und brauchen einen Bereich bzw. eine Einnahmeart, über die man sie
          aufruft — als Schritt stünde dort ein beliebiger Einzelfall. */}
      <p className="mt-3.5 border-t border-dashed border-border pt-2.5 text-[11px] leading-relaxed text-muted-foreground">
        Dazu kommen zwei Steckbriefe, die keinen eigenen Schritt haben, weil man sie immer aus
        einer der Seiten oben öffnet: der eines einzelnen Bereichs (aus Schritt 2 oder aus der
        Bereichstabelle auf dieser Seite) und der einer einzelnen Einnahmeart (aus Schritt 1).
      </p>
    </div>
  );
}
