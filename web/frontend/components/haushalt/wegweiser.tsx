"use client";

// Wegweiser zu den Vertiefungsseiten des Haushalts-Bereichs.
//
// Die drei Karten standen als reine Textkacheln zwischen zwei großen
// Diagramm-Panels und gingen dort unter (Tim, 16.08.). Sie sind aber der
// einzige Weg in die Tiefe — deshalb Titel in der Display-Schrift und ein
// klarer Anfang. Farbe bleibt Hafenblau: Signal-Orange ist im Haushalt
// dem Minus vorbehalten.
//
// AUS SECHS KACHELN WURDE EIN WEG (16.08., zweite Runde). Sechs gleich große
// Karten nebeneinander sind ein Archiv, keine Führung: Wer zum ersten Mal
// hier ist, sieht sechs gleichwertige Angebote und keinen Anfang. Sie tragen
// deshalb Schritt-Nummern und stehen in der Reihenfolge, in der die Fragen
// aufeinander aufbauen. Die Nummern sind eine Empfehlung, keine Sperre.
//
// AUS SIEBEN SCHRITTEN WERDEN VIER STUFEN (16.08., dritte Runde). Der
// Bereich hatte damals zwölf Unterseiten, und drei davon fand niemand:
// `/haushalt/jahr` und `/haushalt/vergleich` waren im ganzen Frontend von
// keinem einzigen `href` erreichbar, `/haushalt/bereiche` nur rückwärts —
// über die Detailseite eines einzelnen Bereichs, also von innen nach außen.
//
// Die naheliegende Reparatur wäre gewesen, drei Kacheln anzuhängen. Zehn
// durchnummerierte Karten sind aber genau das Problem, das die zweite Runde
// gelöst hat, nur größer: Eine Nummer sagt „danach kommt elf", sie sagt nicht,
// WOFÜR man weiterliest. Deshalb liegen die Schritte in vier benannten
// Stufen, und jede Stufe sagt in einem Satz, welche Frage sie beantwortet.
//
//   1–5   Die Zahlen      Woher das Geld kommt, wohin es geht, was fest ist,
//                         was einzelne Aufgaben kosten, wer sie tut — und was
//                         gebaut werden soll.
//   6–7   Die Gegenprobe  Ein Haushalt ist ein Plan; was daraus wurde, steht
//                         im Jahresabschluss und in den Rechnungsergebnissen,
//                         geprüft wird er auch, und am Ende fasst die Stadt
//                         sich in dreizehn Kennzahlen selbst zusammen.
//   8–10  Der Rahmen      Der Kernhaushalt ist rund zwei Drittel der Stadt,
//                         Oldenburg steht nicht allein da, und was aus allen
//                         Jahren zusammen offen blieb, sind die Schulden.
//   11–12 Mitreden        Wann entschieden wird, worüber gestritten wurde,
//                         und welche Stellschrauben es gibt.
//
// AUS DEM KLEINEN VERZEICHNIS WIRD EINE WEG-BÜHNE (27.08.). Obwohl dieser
// Block der einzige vollständige Eingang in die zwölf Schritt-Seiten ist,
// sah er zwischen den großen Haushaltsgrafiken wie eine weitere Nebenkarte
// aus: 10-px-Kicker, vier Kästen im Kasten, beim ersten Besuch kein klarer
// Start. Jetzt trägt er eine echte Überschrift, einen immer sichtbaren
// Start-/Weiter-Knopf und den wiederverwendbaren SVG-Schlangenpfad aus der
// Haushaltsdebatte (`components/grafik/schlangenpfad.tsx`). Daran hängen die
// vier Etappen als große Stationen; alle zwölf Ziele bleiben gleichzeitig
// sichtbar und frei anwählbar.
//
// Der Pfad verbindet die INNEREN Kartenkanten, nicht die fernen Seitenränder:
// So bleibt der Schwung als Motiv erhalten, ohne die riesigen leeren Bögen der
// Debattenansicht nachzuahmen. Unter Containerbreite stehen alle Karten links;
// derselbe gemessene Pfad wird dadurch von selbst zur fast geraden mobilen
// Leselinie. Nichts verschwindet in einem Akkordeon.
//
// Besuchte Seiten werden weiter lokal gemerkt (lib/haushalt-fortschritt.ts,
// kein Konto nötig). „Aufgerufen" heißt bewusst nicht „gelesen": Mehr misst
// die Anwendung nicht, und genau diesen Wortlaut trägt auch die große Bilanz.
//
// Die REIHENFOLGE der Schritte ist unverändert — sie ist der Vertrag dieser
// Datei. Die Begründungen je Position (warum die Schulden hinter dem
// Vergleich stehen, der Stellenplan zwischen Produkten und Investitionen,
// das Labor am Ende) stehen als Kommentare an den Zielen selbst.
// `tests/test_haushalt_schritte.py` hält die selbstgeschriebenen
// Kicker-Nummern der Seiten gegen die hier gerechnete Reihenfolge — wer
// unten etwas einfügt, verschiebt alles danach und zieht die Kicker nach.
//
// **Zwei Detailansichten haben bewusst keinen Schritt.**
// `/haushalt/bereich` und `/haushalt/steuer` sind Steckbriefe: Sie brauchen
// einen Query-Parameter und öffnen ohne ihn den Vorgabefall. Als eigener
// Schritt stünde ein beliebiger Bereich neben zwölf Fragen. Sie werden am
// Fuß benannt, damit die Zählung nicht wie eine Lücke aussieht. (Die
// Übersicht `/haushalt` selbst ist kein
// Ziel dieses Wegweisers — von dort kommt man ja. Sie zählt nur beim
// Umgebungs-Gate mit, das alle einundzwanzig Seiten deckt: `lib/haushalt-frei.ts`.)
//
// Alle Breitenwechsel hängen an der Container-Innenbreite (`@container/weg`),
// nicht am Fenster: Auf dem Desktop liegt die Seite neben der Seitenleiste,
// auf dem iPad nicht. Dieselbe Fensterbreite meint dort zwei verschiedene
// Platzangebote (Designsprache §4).

import Link from "next/link";
import {
  ArrowRight, BarChart3, Check, ChevronRight, ClipboardCheck, Coins,
  FlaskConical, Hammer, LineChart, ListTree, MessagesSquare, Network,
  Scale, Stamp, Users, type LucideIcon,
} from "lucide-react";
import { Schlangenpfad } from "@/components/grafik/schlangenpfad";
import { useFortschritt } from "@/lib/haushalt-fortschritt";
import { cn } from "@/lib/utils";

type Ziel = {
  href: string;
  titel: string;
  text: string;
  /** Das Zeichen des Schritts (Tim, 24.08.: „ein paar helfende Icons").
   *  Es steht HIER, an der einzigen Quelle der Schritte, und taucht an drei
   *  kleinen Stellen auf: in den Zeilen dieses Wegweisers, in der
   *  Weiter-Navigation am Fuß und im Fähnchen des Schritt-Pfads. Die
   *  Zeichen-Kachel im Seitenkopf gab es vom 24. bis 26.08. — sie
   *  wiederholte nur das Zeichen groß („hässlich", Tim) und wich dem
   *  Schritt-Pfad (`schritt-pfad.tsx`, H5-09), der dort den Lesestand zeigt
   *  und seit dem Umbau am selben Tag auch in die Schritte hineinführt. */
  zeichen: LucideIcon;
};

const STUFEN: { kicker: string; frage: string; ziele: Ziel[] }[] = [
  {
    kicker: "Die Zahlen",
    frage: "Woher das Geld kommt, wofür es eingeplant ist und welcher Teil politisch gestaltbar bleibt.",
    ziele: [
      {
        href: "/haushalt/einnahmen",
        titel: "Woher kommt das Geld?",
        text: "Die Einnahmequellen der Stadt und der Einfluss des Rates auf ihre Höhe.",
        zeichen: Coins,
      },
      {
        // „Was kostet eigentlich …?" bleibt hinter „Muss oder kann?": Es ist
        // die griffigste Seite, beantwortet aber eine Frage, die erst Sinn
        // ergibt, wenn man weiß, dass der größte Teil des Geldes gar nicht
        // zur Disposition steht.
        href: "/haushalt/pflicht",
        titel: "Muss oder kann?",
        text: "Welche Ausgaben gesetzlich gebunden sind und wo politische Entscheidungen möglich bleiben.",
        zeichen: Scale,
      },
      {
        // Seit 21.08.2026 mit „Was steckt hinter den Namen?" zusammen: Beide
        // gehen denselben Baum hinunter — erst die zehn Teilhaushalte im
        // Klartext, dann die Aufgaben darin. Wer den zweiten Schritt ohne den
        // ersten liest, sucht Aufgaben in Bereichen, deren Namen ihm nichts
        // sagen.
        href: "/haushalt/produkte",
        titel: "Was kostet eigentlich …?",
        text: "Was einzelne Aufgaben wie Archiv, Feuerwehr oder Schwimmbad kosten und welcher Auftrag dahintersteht.",
        zeichen: ListTree,
      },
      {
        // Zwischen „Was kostet …?" und „Was wird gebaut?": „Wer macht die
        // Arbeit?" stellt sich erst, wenn man weiß, was die Arbeit kostet —
        // und der Stellenplan gehört zum laufenden Betrieb, während die
        // Investitionen den Haushalt wechseln. Vor die Gegenprobe, weil er
        // sie lesbar macht: Unbesetzte Stellen erklären, warum
        // Personalausgaben unter dem Plan bleiben können.
        href: "/haushalt/personal",
        titel: "Wer macht die Arbeit?",
        text: "Wie viele Stellen die Stadt plant, wie viele besetzt sind und wo Personal fehlt.",
        zeichen: Users,
      },
      {
        // Am Ende der Zahlen-Stufe, weil es die einzige Seite ist, die einen
        // ANDEREN Haushalt zeigt: Erst wenn klar ist, was im Ergebnishaushalt
        // steht, ist „und hier steht das alles NICHT drin" eine Aussage.
        // Seit 21.08.2026 mit dem Ist zusammen: „Was wurde davon wirklich
        // gebaut?" stand als eigener Schritt in der NÄCHSTEN Etappe. Plan und
        // Ist derselben Sache — wer wissen will, was aus einem Vorhaben wurde,
        // sollte dafür nicht die Etappe wechseln müssen.
        href: "/haushalt/investitionen",
        titel: "Was gebaut wird und was daraus wurde",
        text: "Welche Neubauten, Fahrzeuge und Grundstücke geplant sind und wie viel davon tatsächlich umgesetzt wurde.",
        zeichen: Hammer,
      },
    ],
  },
  {
    kicker: "Die Gegenprobe",
    frage: "Der Haushalt ist ein Plan. Der Jahresabschluss zeigt, was tatsächlich daraus geworden ist.",
    ziele: [
      {
        href: "/haushalt/plan-ist",
        titel: "Geplant und geworden",
        text: "Wie sich Plan und tatsächliches Ergebnis in den Jahresabschlüssen unterscheiden.",
        zeichen: ClipboardCheck,
      },
      {
        // EIN Ziel statt zweier (21.08.2026). „Die Prüfung" und „Die dreizehn
        // Zahlen" beantworten dieselbe Frage aus zwei Richtungen: von außen
        // geprüft, von innen zusammengefasst. Die Reihenfolge bleibt die alte
        // — erst die Feststellungen, dann die Selbstauskunft —, weil eine
        // Liste von Quoten ohne die Zahlen, die sie zusammenfassen, nichts
        // sagt. Sie ist jetzt nur die Reihenfolge der Abschnitte.
        href: "/haushalt/pruefung",
        titel: "Geprüft und zusammengefasst",
        text: "Was das Rechnungsprüfungsamt beanstandet und mit welchen Kennzahlen die Stadt ihren Abschluss zusammenfasst.",
        zeichen: Stamp,
      },
    ],
  },
  {
    kicker: "Der Rahmen",
    frage: "Zum Gesamtbild gehören auch städtische Unternehmen, der Vergleich mit anderen Städten und die Schulden über mehrere Jahre.",
    ziele: [
      {
        // EIN Ziel statt vierer (21.08.2026). Summe, Gesellschaften, ihre
        // Wirtschaftspläne und die Gebühren, die daraus folgen, sind eine
        // Kette: Wer bei den Gebühren anfängt, liest eine Zahl ohne Herkunft;
        // wer bei der Summe aufhört, weiß nicht, wer dahintersteckt.
        href: "/haushalt/konzern",
        titel: "Und ist das die ganze Stadt?",
        text: "Welche städtischen Unternehmen und Beteiligungen neben dem Kernhaushalt stehen.",
        zeichen: Network,
      },
      {
        // Spät, nicht vorn: „Steht Oldenburg besser da?" stellt sich erst,
        // wenn man die eigenen Zahlen kennt — und die Seite besteht zur
        // Hälfte aus der Begründung, warum der Ausgaben-Vergleich nicht trägt.
        href: "/haushalt/vergleich",
        titel: "Steht Oldenburg besser da?",
        text: "Wie Oldenburg bei Steuerkraft und Hebesätzen dasteht und warum Ausgabenvergleiche Grenzen haben.",
        zeichen: BarChart3,
      },
      {
        // Am Ende des Rahmens: Die Schulden sind die einzige Bestandsgröße
        // im ganzen Weg — was aus allen Jahren zusammen offen blieb. Hinter
        // dem Konzern gelesen weiß man gerade, dass „die Stadt" zwei
        // Abgrenzungen hat, und genau davon hängt ab, welche Schuldenzahl
        // gilt. (Und: Hier eingefügt statt weiter vorn verschiebt es keine
        // Kicker-Nummern der Seiten davor.)
        href: "/haushalt/schulden",
        titel: "Wie viel Schulden hat Oldenburg?",
        text: "Wie sich der Schuldenstand seit 1995 entwickelt hat und welche Verbindlichkeiten darin enthalten sind.",
        zeichen: LineChart,
      },
    ],
  },
  {
    kicker: "Mitreden",
    frage: "Wann der Rat entscheidet, worüber politisch gestritten wird und welche Stellschrauben es gibt.",
    ziele: [
      {
        // EIN Ziel statt zweier (21.08.2026). „Wann wird das entschieden?"
        // und „Der Streit ums Geld" waren zwei Schritte für eine Frage — und
        // einer davon war im ganzen Frontend über nichts als diese Liste
        // erreichbar. Sie stehen jetzt als Abschnitte auf einer Seite; die
        // Anker führen weiterhin gezielt hin.
        href: "/haushalt/mitreden",
        titel: "Mitreden",
        text: "Wann der Haushalt beschlossen wird und welche Positionen die Fraktionen vertreten.",
        zeichen: MessagesSquare,
      },
      {
        // Das Labor stand vom 21. bis 24.08.2026 als dritter Abschnitt auf
        // /haushalt/mitreden (#698) und ist wieder ein eigener Schritt: Es
        // soll deutlich mehr Stellschrauben bekommen, und ein wachsendes
        // Werkzeug braucht eine eigene Adresse statt eines Abschnitts am Fuß
        // einer langen Seite. Am Ende des Wegs, wie schon vor #698: An
        // Stellschrauben zu drehen ist der letzte Schritt, nicht der zweite —
        // vorher fehlt der Bezug, an dem sich ablesen ließe, ob eine Bewegung
        // viel ist.
        href: "/haushalt/labor",
        titel: "Haushalts-Labor",
        text: "Ausprobieren, wie sich veränderte Einnahmen und Ausgaben auf das Ergebnis auswirken.",
        zeichen: FlaskConical,
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

/** Die Schritte als flache, nummerierte Liste — für die Weiter-Navigation am
 *  Fuß der Detailseiten (`schritt-weiter.tsx`).
 *
 *  Bewusst HIER exportiert statt in eine lib verschoben: `STUFEN` ist die
 *  einzige Quelle der Reihenfolge, und `tests/test_haushalt_schritte.py`
 *  liest genau diese Datei, um die selbstgeschriebenen Kicker dagegen zu
 *  halten. Eine zweite Liste woanders wäre der Anfang genau der Drift, die
 *  der Wächter verhindern soll. */
export const SCHRITTE: { href: string; titel: string; nr: number; zeichen: LucideIcon }[] =
  STUFEN_NUMMERIERT.flatMap((stufe) =>
    stufe.ziele.map((z) => ({ href: z.href, titel: z.titel, nr: z.nr, zeichen: z.zeichen })));

/** Die Etappen als Gruppen über den Schritten — für den Schritt-Pfad im Kopf
 *  der Seiten (`schritt-pfad.tsx`): Er zeigt die zwölf Punkte in genau diesen
 *  vier Gruppen, damit die Lücken im Pfad dieselben sind wie die Karten des
 *  Wegweisers. Gleiche Regel wie bei `SCHRITTE`: hier exportiert, nicht
 *  abgeschrieben. */
export const ETAPPEN: { kicker: string; von: number; bis: number }[] =
  STUFEN_NUMMERIERT.map((stufe) => ({ kicker: stufe.kicker, von: stufe.von, bis: stufe.bis }));

type Zustand = "gelesen" | "naechster" | "offen";

/** Die Nummer ist zugleich der Lesestand: offen als Kontur, als Nächstes mit
 *  kräftigem Ring und nach dem Aufruf als Häkchen. Kein zweiter Status-Punkt
 *  neben der Nummer, damit die Wegkarte nicht zum Dashboard wird. */
function SchrittMarke({ zustand, nr }: { zustand: Zustand; nr: number }) {
  return (
    <span aria-hidden="true" className={cn(
      "flex h-8 w-8 flex-none items-center justify-center rounded-full border font-mono text-[10px] font-semibold tabular-nums transition-[color,background-color,border-color,box-shadow,transform] duration-200",
      zustand === "gelesen" && "border-primary bg-primary text-primary-foreground",
      zustand === "naechster" && "border-primary bg-card text-primary shadow-[0_0_0_4px_hsl(var(--primary)/0.12)]",
      zustand === "offen" && "border-border bg-card text-muted-foreground",
    )}>
      {zustand === "gelesen" ? (
        <Check size={14} strokeWidth={2.5} />
      ) : (
        nr
      )}
    </span>
  );
}

function Station({ z, zustand }: {
  z: Ziel & { nr: number };
  zustand: Zustand;
}) {
  return (
    <Link
      href={z.href}
      title={z.text}
      className={cn(
        "group flex min-h-[52px] items-center gap-2.5 rounded-xl border border-transparent px-2 py-1.5 transition-[background-color,border-color,transform] duration-200 hover:border-primary/20 hover:bg-primary/[0.045] active:scale-[0.99] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        zustand === "naechster" && "border-primary/25 bg-primary/[0.07]",
      )}
    >
      <SchrittMarke zustand={zustand} nr={z.nr} />
      <z.zeichen aria-hidden size={14} strokeWidth={2}
        className="flex-none text-muted-foreground transition-colors group-hover:text-primary" />
      <span className="min-w-0 flex-1">
        <span className="block font-mono text-[9px] font-medium uppercase tracking-[0.09em] text-muted-foreground">
          Schritt {z.nr}
          {zustand === "gelesen" && <span className="sr-only">, schon aufgerufen</span>}
          {zustand === "naechster" && <span className="sr-only">, als Nächstes</span>}
        </span>
        <span className={cn(
          "mt-0.5 block text-[13px] font-semibold leading-snug text-foreground",
          zustand === "naechster" && "font-bold",
          zustand === "gelesen" && "text-foreground/75",
        )}>
          {z.titel}
        </span>
      </span>
      <ChevronRight aria-hidden size={14} strokeWidth={2}
        className="flex-none text-muted-foreground transition-transform group-hover:translate-x-0.5 group-hover:text-primary" />
    </Link>
  );
}

export function Wegweiser() {
  const besucht = useFortschritt();

  const etappen = STUFEN_NUMMERIERT.map((stufe, i) => {
    const gelesen = stufe.ziele.filter((z) => besucht.has(z.href)).length;
    return { ...stufe, index: i, gelesen, fertig: gelesen === stufe.ziele.length };
  });
  const alleZiele = etappen.flatMap((e) => e.ziele);
  const naechster = alleZiele.find((z) => !besucht.has(z.href)) ?? null;
  const gelesenGesamt = alleZiele.length - alleZiele.filter((z) => !besucht.has(z.href)).length;
  const aktiverIndex = naechster
    ? etappen.findIndex((e) => e.ziele.some((z) => z.href === naechster.href))
    : null;

  const zustandVon = (z: Ziel & { nr: number }): Zustand =>
    besucht.has(z.href) ? "gelesen" : naechster?.href === z.href ? "naechster" : "offen";

  const ctaZiel = naechster ?? alleZiele[0];
  const ctaText = !naechster
    ? "Weg noch einmal ansehen"
    : gelesenGesamt > 0
      ? `Weiter bei Schritt ${naechster.nr}`
      : "Weg beginnen";

  return (
    <section className="@container/weg relative isolate overflow-hidden rounded-2xl border border-primary/20 bg-primary/[0.045] shadow-sm">
      {/* Große, ruhige Kreislinien geben der Bühne Tiefe, ohne eine zweite
          Akzentfarbe oder eine bedeutungslose Illustration einzuführen. */}
      <span aria-hidden="true"
        className="pointer-events-none absolute -right-24 -top-28 h-72 w-72 rounded-full border-[44px] border-primary/[0.035]" />
      <span aria-hidden="true"
        className="pointer-events-none absolute -bottom-32 -left-24 h-64 w-64 rounded-full border-[32px] border-primary/[0.025]" />

      <div className="relative px-4 py-5 sm:px-6 sm:py-7 @4xl/weg:px-9 @4xl/weg:py-8">
        <div className="grid gap-6 @3xl/weg:grid-cols-[minmax(0,1fr)_280px] @3xl/weg:items-end @4xl/weg:gap-10">
          <div className="min-w-0">
            <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-primary">
              Der Weg durch den Haushalt
            </p>
            <h2 className="mt-2 max-w-[18ch] font-display text-[31px] font-bold leading-[1.04] tracking-tight text-foreground sm:text-[38px] @5xl/weg:text-[44px]">
              Den Haushalt verstehen. <span className="text-primary">In {GESAMT} Schritten.</span>
            </h2>
            <p className="mt-3 max-w-[62ch] text-[14px] leading-relaxed text-foreground/80 sm:text-[14.5px]">
              Vier Etappen zeigen, wie Oldenburg plant, prüft und entscheidet. Folge dem Weg
              oder öffne direkt die Frage, die dich interessiert.
            </p>
          </div>

          <div className="border-t border-primary/15 pt-4 @3xl/weg:border-l @3xl/weg:border-t-0 @3xl/weg:pl-6 @3xl/weg:pt-0">
            <p className="flex items-end gap-1.5 font-display text-foreground">
              <span className="text-[38px] font-bold leading-none tabular-nums">{gelesenGesamt}</span>
              <span className="pb-0.5 text-[17px] font-semibold text-muted-foreground">von {GESAMT}</span>
            </p>
            <p className="mt-1 text-[11px] leading-relaxed text-muted-foreground">
              aufgerufen, nur in diesem Browser gemerkt
            </p>
            <Link
              href={ctaZiel.href}
              className="group mt-3 inline-flex min-h-[42px] items-center gap-2 whitespace-nowrap rounded-xl bg-primary px-4 py-2 text-[12.5px] font-semibold text-primary-foreground transition-[opacity,transform] hover:opacity-90 active:scale-[0.98] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
            >
              {ctaText}
              <ArrowRight aria-hidden size={15} strokeWidth={2}
                className="transition-transform group-hover:translate-x-0.5" />
            </Link>
          </div>
        </div>

        {/* Derselbe gemessene SVG-Pfad wie in der Haushaltsdebatte, aber mit
            einer eigenen Dramaturgie: vier kompakte Etappen statt langer
            Redekarten. Auf Mobil wird aus der Schlange von allein eine fast
            gerade Leselinie, weil alle vier Anker links stehen. */}
        <Schlangenpfad
          zeichnungsart="sichtkontakt"
          grundKlasse="text-primary/15"
          stiftKlasse="text-primary/65"
          className="mt-7 @4xl/weg:mt-9"
        >
          <ol className="relative flex list-none flex-col gap-4 @2xl/weg:gap-5">
            {etappen.map((e) => {
              const rechts = e.index % 2 === 1;
              const aktiv = e.index === aktiverIndex;
              const status = e.fertig
                ? "Etappe aufgerufen"
                : aktiv
                  ? gelesenGesamt > 0 ? "Als Nächstes" : "Hier anfangen"
                  : `${e.gelesen} von ${e.ziele.length} aufgerufen`;
              return (
                <li
                  key={e.kicker}
                  data-auftritt
                  className="group relative transition-opacity duration-700 ease-out motion-safe:data-[reveal=aus]:opacity-0"
                >
                  <span
                    data-punkt
                    aria-hidden="true"
                    className={cn(
                      "absolute left-[11px] top-[34px] z-10 flex h-[13px] w-[13px] -translate-x-1/2 items-center justify-center rounded-full border-2 bg-card transition-[background-color,border-color,box-shadow]",
                      rechts ? "@2xl/weg:left-[28%]" : "@2xl/weg:left-[72%]",
                      e.fertig && "border-primary bg-primary",
                      aktiv && "border-primary shadow-[0_0_0_5px_hsl(var(--primary)/0.14)]",
                      !e.fertig && !aktiv && "border-primary/35",
                    )}
                  >
                    {e.fertig && <Check size={8} strokeWidth={3} className="text-primary-foreground" />}
                  </span>

                  <section className={cn(
                    "relative ml-7 rounded-2xl border bg-card p-4 shadow-lifted transition-[transform,border-color] duration-700 ease-out @2xl/weg:ml-0 @2xl/weg:w-[72%] @4xl/weg:p-5",
                    rechts && "@2xl/weg:ml-auto",
                    aktiv ? "border-primary/45" : "border-border",
                    rechts
                      ? "motion-safe:group-data-[reveal=aus]:translate-x-5"
                      : "motion-safe:group-data-[reveal=aus]:-translate-x-5",
                  )}>
                    <div className="flex items-start gap-3.5">
                      <span aria-hidden="true"
                        className="flex-none font-display text-[34px] font-bold leading-none tabular-nums text-primary/25">
                        {String(e.index + 1).padStart(2, "0")}
                      </span>
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
                          <h3 className="font-display text-[19px] font-bold leading-tight tracking-tight text-foreground sm:text-[21px]">
                            {e.kicker}
                          </h3>
                          <span className={cn(
                            "font-mono text-[9px] font-medium uppercase tracking-[0.09em]",
                            aktiv || e.fertig ? "text-primary" : "text-muted-foreground",
                          )}>
                            {status}
                          </span>
                        </div>
                        <p className="mt-1.5 text-[12.5px] leading-relaxed text-muted-foreground">
                          {e.frage}
                        </p>
                      </div>
                    </div>

                    <div className={cn(
                      "mt-3 grid gap-1",
                      e.ziele.length > 2 && "@3xl/weg:grid-cols-2",
                    )}>
                      {e.ziele.map((z) => (
                        <Station key={z.href} z={z} zustand={zustandVon(z)} />
                      ))}
                    </div>
                  </section>
                </li>
              );
            })}
          </ol>
        </Schlangenpfad>

        <p className="mt-6 border-t border-primary/15 pt-3 text-[11px] leading-relaxed text-muted-foreground">
          Die Steckbriefe für einen Haushaltsbereich und eine Einnahmeart öffnen sich direkt
          aus den passenden Schritten. Sie sind deshalb keine eigenen Stationen des Wegs.
        </p>
      </div>
    </section>
  );
}
