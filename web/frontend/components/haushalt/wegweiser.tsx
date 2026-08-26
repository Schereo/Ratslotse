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
//   1–6   Die Zahlen      Woher das Geld kommt, wohin es geht, was fest ist,
//                         was einzelne Aufgaben kosten, wer sie tut — und was
//                         gebaut werden soll.
//   7–10  Die Gegenprobe  Ein Haushalt ist ein Plan; was daraus wurde, steht
//                         im Jahresabschluss und in den Rechnungsergebnissen,
//                         geprüft wird er auch, und am Ende fasst die Stadt
//                         sich in dreizehn Kennzahlen selbst zusammen.
//   11–15 Der Rahmen      Der Kernhaushalt ist rund zwei Drittel der Stadt,
//                         Oldenburg steht nicht allein da, und was aus allen
//                         Jahren zusammen offen blieb, sind die Schulden.
//   16–18 Mitreden        Wann entschieden wird, worüber gestritten wurde,
//                         und was sich drehen ließe.
//
// AUS DER 16er-LISTE WERDEN VIER ETAPPEN-KARTEN (17.08., vierte Runde,
// Boards H3-08/H4-00). Die nummerierte Liste trug bis Schritt 10 — bei
// sechzehn wurde sie zur Pflichtlektüre: 16 Zeilen mit je zwei Textzeilen
// sind auf jedem Gerät eine Wand. Jetzt ist die STUFE die Karte („Etappe"),
// und die Schritte darin sind einzeilig — die Etappe ist die Einheit, die
// man an einem Abend schafft. Drei Dinge gehören zu dieser Form:
//
//  * **„Weiter, wo du warst."** Besuchte Seiten werden lokal gemerkt
//    (lib/haushalt-fortschritt.ts, kein Konto nötig); der Knopf oben springt
//    zum ersten noch nicht aufgerufenen Schritt, und erledigte Etappen
//    tragen ihr Häkchen. „Erledigt" heißt ehrlich nur „aufgerufen" — mehr
//    messen wir nicht.
//  * **Mobil ein Akkordeon** (H4-00): Nur die Etappe mit dem nächsten
//    Schritt ist offen, die anderen drei sind eine Kopfzeile mit Bilanz
//    („4 von 4"). Der „Weiter"-Knopf steht am Kopf der Karte — bewusst NICHT
//    als fixierter Knopf über der Tab-Leiste, wie das Board vorschlägt: Dort
//    schwebt schon der „Nach oben"-Pfeil (components/back-to-top.tsx), und
//    zwei konkurrierende Schwebe-Elemente über der Tab-Bar verdecken sich
//    gegenseitig.
//  * **Die Kurzbeschreibungen der Schritte** stehen nicht mehr als zweite
//    Zeile in der Liste (sie waren die halbe Wand), sondern als `title` am
//    Link — die Seite selbst erklärt sich in ihrer ersten Zeile ohnehin.
//
// Die REIHENFOLGE der Schritte ist unverändert — sie ist der Vertrag dieser
// Datei. Die Begründungen je Position (warum die Schulden hinter dem
// Vergleich stehen, der Stellenplan zwischen Produkten und Investitionen,
// das Labor am Ende) stehen als Kommentare an den Zielen selbst.
// `tests/test_haushalt_schritte.py` hält die selbstgeschriebenen
// Kicker-Nummern der Seiten gegen die hier gerechnete Reihenfolge — wer
// unten etwas einfügt, verschiebt alles danach und zieht die Kicker nach.
//
// **Zwei der zwanzig Unterseiten haben bewusst keinen Schritt.**
// `/haushalt/bereich` und `/haushalt/steuer` sind Steckbriefe: Sie brauchen
// einen Query-Parameter und öffnen ohne ihn den Vorgabefall. Als eigener
// Schritt stünde ein beliebiger Bereich neben achtzehn Fragen. Sie werden am
// Fuß benannt, damit die Zählung „achtzehn Schritte, zwanzig Unterseiten"
// nicht wie eine Lücke aussieht. (Die Übersicht `/haushalt` selbst ist kein
// Ziel dieses Wegweisers — von dort kommt man ja. Sie zählt nur beim
// Umgebungs-Gate mit, das alle einundzwanzig Seiten deckt: `lib/haushalt-frei.ts`.)
//
// Zwei Spalten ab 768 px **Container-Innenbreite**, nicht Fensterbreite
// (Designsprache §4): Am Desktop liegt der Block neben der Seitenleiste, auf
// dem iPad nicht — dieselbe Fensterbreite meint zwei verschiedene
// Platzangebote. Und zwar TEXTSPALTEN (`columns`), kein Raster: Die Etappen
// sind 6, 4, 5 und 3 Schritte lang — in einem Raster würde jede Zeile so
// hoch wie ihre höhere Karte, unter der kurzen bliebe Leere stehen.

import { useState } from "react";
import Link from "next/link";
import {
  BarChart3, Check, ChevronDown, ChevronRight, ClipboardCheck, Coins,
  FlaskConical, Hammer, LineChart, ListTree, MessagesSquare, Network, Play,
  Scale, Stamp, Users, type LucideIcon,
} from "lucide-react";
import { useFortschritt } from "@/lib/haushalt-fortschritt";
import { useBreite } from "@/lib/use-breite";
import { cn } from "@/lib/utils";

type Ziel = {
  href: string;
  titel: string;
  text: string;
  /** Das Zeichen des Schritts (Tim, 24.08.: „ein paar helfende Icons").
   *  Es steht HIER, an der einzigen Quelle der Schritte, und taucht an drei
   *  Stellen wieder auf: klein in den Zeilen dieses Wegweisers, als Kachel im
   *  Kopf der Seite (`schritt-zeichen.tsx`) und in der Weiter-Navigation am
   *  Fuß. Dieselbe Form an allen dreien — man erkennt eine Seite wieder,
   *  statt zwölf Titel zu vergleichen. */
  zeichen: LucideIcon;
};

const STUFEN: { kicker: string; frage: string; ziele: Ziel[] }[] = [
  {
    kicker: "Die Zahlen",
    frage: "Woher das Geld kommt, wohin es geht — und wie wenig davon frei ist.",
    ziele: [
      {
        href: "/haushalt/einnahmen",
        titel: "Woher kommt das Geld?",
        text: "Alle Einnahmequellen — und bei welchen der Rat etwas zu entscheiden hat.",
        zeichen: Coins,
      },
      {
        // „Was kostet eigentlich …?" bleibt hinter „Muss oder kann?": Es ist
        // die griffigste Seite, beantwortet aber eine Frage, die erst Sinn
        // ergibt, wenn man weiß, dass der größte Teil des Geldes gar nicht
        // zur Disposition steht.
        href: "/haushalt/pflicht",
        titel: "Muss oder kann?",
        text: "Wie viel gesetzlich vorgeschrieben ist — und wie die Stadt selbst das sieht.",
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
        text: "Archiv, Feuerwehr, Schwimmbad: einzelne Aufgaben mit Kosten und Auftrag.",
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
        text: "Der Stellenplan: wie viele Stellen die Stadt vorhält — und wie viele leer stehen.",
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
        titel: "Was gebaut wird — und was daraus wurde",
        text: "Neubauten, Fahrzeuge, Grundstücke — der Haushalt, in dem die Seiten davor nicht vorkommen; dazu, was am Jahresende davon abgeflossen ist.",
        zeichen: Hammer,
      },
    ],
  },
  {
    kicker: "Die Gegenprobe",
    frage: "Ein Haushalt ist ein Plan. Was daraus wurde, steht woanders — und wird geprüft.",
    ziele: [
      {
        href: "/haushalt/plan-ist",
        titel: "Geplant und geworden",
        text: "Was am Jahresende wirklich zusammenkam — aus den Jahresabschlüssen.",
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
        text: "Was das Rechnungsprüfungsamt beanstandet — und worauf die Stadt ihren Abschluss selbst eindampft.",
        zeichen: Stamp,
      },
    ],
  },
  {
    kicker: "Der Rahmen",
    frage: "Der Haushalt ist nicht die ganze Stadt, Oldenburg steht nicht allein da — "
      + "und was aus allen Jahren zusammen offen blieb, steht in keinem davon.",
    ziele: [
      {
        // EIN Ziel statt vierer (21.08.2026). Summe, Gesellschaften, ihre
        // Wirtschaftspläne und die Gebühren, die daraus folgen, sind eine
        // Kette: Wer bei den Gebühren anfängt, liest eine Zahl ohne Herkunft;
        // wer bei der Summe aufhört, weiß nicht, wer dahintersteckt.
        href: "/haushalt/konzern",
        titel: "Und ist das die ganze Stadt?",
        text: "Klinikum, Busse, Bäder, Gebäude: was neben dem Haushalt noch läuft.",
        zeichen: Network,
      },
      {
        // Spät, nicht vorn: „Steht Oldenburg besser da?" stellt sich erst,
        // wenn man die eigenen Zahlen kennt — und die Seite besteht zur
        // Hälfte aus der Begründung, warum der Ausgaben-Vergleich nicht trägt.
        href: "/haushalt/vergleich",
        titel: "Steht Oldenburg besser da?",
        text: "Steuerkraft und Hebesätze der kreisfreien Städte — und warum Ausgaben sich nicht vergleichen lassen.",
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
        text: "Der Schuldenstand seit 1995, insgesamt und je Einwohner*in — und was er zählt.",
        zeichen: LineChart,
      },
    ],
  },
  {
    kicker: "Mitreden",
    frage: "Wann entschieden wird, worüber gestritten wurde — und was sich drehen ließe.",
    ziele: [
      {
        // EIN Ziel statt zweier (21.08.2026). „Wann wird das entschieden?"
        // und „Der Streit ums Geld" waren zwei Schritte für eine Frage — und
        // einer davon war im ganzen Frontend über nichts als diese Liste
        // erreichbar. Sie stehen jetzt als Abschnitte auf einer Seite; die
        // Anker führen weiterhin gezielt hin.
        href: "/haushalt/mitreden",
        titel: "Mitreden",
        text: "Wann entschieden wird — und worüber die Fraktionen gestritten haben.",
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
        text: "Selbst an den Stellschrauben drehen und sehen, was das ausmacht.",
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

type Zustand = "gelesen" | "naechster" | "offen";

/** ✓ / ▶ / ○ — die Lesestand-Marker der Etappen-Form (H3-08). Hafenblau,
 *  nie Signal: Ein ungelesener Schritt ist keine Abweichung. */
function Marker({ zustand }: { zustand: Zustand }) {
  return (
    <span aria-hidden="true" className="flex w-4 flex-none items-center justify-center">
      {zustand === "gelesen" ? (
        <Check size={13} strokeWidth={2.5} className="text-primary" />
      ) : zustand === "naechster" ? (
        <Play size={10} className="fill-primary text-primary" />
      ) : (
        <span className="h-[7px] w-[7px] rounded-full border-[1.5px] border-muted-foreground/70" />
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
        "group -mx-1.5 flex min-h-[36px] items-center gap-2 rounded-lg px-1.5 py-1 transition-colors hover:bg-primary/[0.05]",
        zustand === "naechster" && "bg-primary/[0.06]",
      )}
    >
      <Marker zustand={zustand} />
      <span className="flex-none font-mono text-[10.5px] font-medium tabular-nums text-muted-foreground">
        {/* „1 Woher kommt das Geld?" liest eine Sprachausgabe als nackte
            Ziffer vor — das Wort steht deshalb da, nur nicht im Bild. */}
        <span className="sr-only">Schritt </span>{z.nr}
      </span>
      {/* Das Zeichen des Schritts — dieselbe Form wie in der Kachel im Kopf
          der Seite. Ruhig grau, nicht Hafenblau: In der Zeile markieren schon
          ✓/▶ den Stand, ein zweites blaues Element je Zeile wäre Rauschen. */}
      <z.zeichen aria-hidden size={14} strokeWidth={2}
        className="flex-none text-muted-foreground/80 transition-colors group-hover:text-primary" />
      <span className={cn(
        "min-w-0 flex-1 text-[13px] leading-snug",
        zustand === "naechster" ? "font-bold" : "font-semibold",
        zustand === "gelesen" && "text-foreground/75",
      )}>
        {z.titel}
        {zustand === "gelesen" && <span className="sr-only"> (schon aufgerufen)</span>}
        {zustand === "naechster" && <span className="sr-only"> (nächster Schritt)</span>}
      </span>
      <ChevronRight aria-hidden size={14} strokeWidth={2}
        className="flex-none text-muted-foreground transition-transform group-hover:translate-x-0.5 group-hover:text-primary" />
    </Link>
  );
}

export function Wegweiser() {
  const besucht = useFortschritt();
  // Gemessen statt Fenster-Breakpoint (Designsprache §4): Das Akkordeon
  // hängt am Platz der KARTE, nicht am Gerät.
  const { box, breite } = useBreite(1024, 280);
  const schmal = breite < 744;
  const [offene, setOffene] = useState<number | null>(null);

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
  // Mobil ist genau eine Etappe offen: die zuletzt angetippte, sonst die mit
  // dem nächsten Schritt, sonst die erste.
  const offenIndex = offene ?? aktiverIndex ?? 0;

  const zustandVon = (z: Ziel & { nr: number }): Zustand =>
    besucht.has(z.href) ? "gelesen" : naechster?.href === z.href ? "naechster" : "offen";

  const statusChip = (e: (typeof etappen)[number]) =>
    e.fertig ? (
      <span className="inline-flex items-center gap-1 font-mono text-[9.5px] font-medium uppercase tracking-[0.09em] text-primary">
        <Check aria-hidden size={11} strokeWidth={2.5} /> erledigt
      </span>
    ) : e.index === aktiverIndex && gelesenGesamt > 0 ? (
      <span className="font-mono text-[9.5px] font-medium uppercase tracking-[0.09em] text-primary">
        Du bist hier
      </span>
    ) : null;

  const kopfzeile = (e: (typeof etappen)[number]) => (
    <div className="flex items-baseline justify-between gap-3">
      <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-foreground/70">
        Etappe {e.index + 1} · {e.kicker}
      </p>
      <span className="flex flex-none items-baseline gap-2.5">
        {statusChip(e)}
        <span className="font-mono text-[10px] font-medium tabular-nums text-muted-foreground">
          {e.von === e.bis ? `Schritt ${e.von}` : `Schritt ${e.von}–${e.bis}`}
        </span>
      </span>
    </div>
  );

  return (
    <div ref={box} className="rounded-2xl border border-border bg-card p-4 shadow-sm sm:p-5">
      {/* Als <h2>, obwohl es wie ein Kicker aussieht: Der Block trägt darunter
          vier <h3>, und die Seite eine <h1> auf der Anzeigetafel. Ohne diese
          Stufe spränge die Gliederung von 1 auf 3. */}
      <h2 className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
        Der Weg durch den Haushalt
      </h2>
      <p className="mt-1 max-w-[76ch] text-[12.5px] leading-relaxed text-muted-foreground">
        {GESAMT} Schritte in vier Etappen, und sie bauen aufeinander auf: erst die Zahlen
        selbst, dann die Gegenprobe, dann der Blick über den Haushalt hinaus, zuletzt die
        Frage, was sich ändern ließe. Eine Etappe ist ein Abend — einzeln funktioniert aber
        jede Seite für sich.
      </p>

      {/* „Weiter, wo du warst": erst ab dem ersten gemerkten Besuch — vorher
          wäre der Knopf nur ein zweiter Weg zu Schritt 1. Der Lesestand
          liegt im Browser (kein Konto), deshalb steht das ehrlich dabei. */}
      {naechster && gelesenGesamt > 0 && (
        <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1.5">
          <Link
            href={naechster.href}
            className="inline-flex min-h-[40px] items-center gap-2 rounded-xl bg-primary px-3.5 py-1.5 text-[12.5px] font-semibold text-primary-foreground transition-opacity hover:opacity-90"
          >
            <Play aria-hidden size={11} className="fill-current" />
            Weiter bei Schritt {naechster.nr} · {naechster.titel}
          </Link>
          <span className="text-[11px] text-muted-foreground">
            {gelesenGesamt} von {GESAMT} aufgerufen — gemerkt nur in diesem Browser.
          </span>
        </div>
      )}
      {!naechster && (
        <p className="mt-3 inline-flex items-center gap-1.5 text-[12.5px] font-semibold text-primary">
          <Check aria-hidden size={14} strokeWidth={2.5} />
          Alle {GESAMT} Schritte aufgerufen — der Weg ist durch.
        </p>
      )}

      {schmal ? (
        /* Akkordeon (H4-00 mobil): nur eine Etappe offen, die anderen sind
           eine Kopfzeile mit Bilanz. Die Bilanz ersetzt nichts — jede Etappe
           lässt sich öffnen, ohne die offene zu verlieren geht es nicht,
           und genau das ist der Punkt: eine Wand weniger. */
        <div className="mt-3.5 flex flex-col">
          {etappen.map((e) => {
            const offen = e.index === offenIndex;
            const panelId = `wegweiser-etappe-${e.index + 1}`;
            return (
              <section key={e.kicker} className="border-t border-dashed border-border pt-3 [&:not(:first-of-type)]:mt-3">
                <button
                  type="button"
                  aria-expanded={offen}
                  aria-controls={panelId}
                  onClick={() => setOffene(offen ? -1 : e.index)}
                  className="-mx-1.5 flex w-[calc(100%+12px)] items-center gap-2.5 rounded-lg px-1.5 py-1 text-left transition-colors hover:bg-primary/[0.05]"
                >
                  <span className="min-w-0 flex-1">
                    <span className="block font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-foreground/70">
                      Etappe {e.index + 1} · {e.kicker}
                    </span>
                    <span className="mt-0.5 flex items-baseline gap-2.5">
                      {statusChip(e) ?? (
                        <span className="font-mono text-[9.5px] uppercase tracking-[0.09em] text-muted-foreground">
                          {e.gelesen} von {e.ziele.length}
                        </span>
                      )}
                      <span className="font-mono text-[9.5px] tabular-nums uppercase tracking-[0.09em] text-muted-foreground">
                        Schritt {e.von}–{e.bis}
                      </span>
                    </span>
                  </span>
                  <ChevronDown aria-hidden size={15} strokeWidth={2}
                    className={cn("flex-none text-muted-foreground transition-transform", offen && "rotate-180")} />
                </button>
                <div id={panelId} hidden={!offen} className="mt-1.5">
                  <p className="max-w-[74ch] text-[12px] leading-relaxed text-muted-foreground">
                    {e.frage}
                  </p>
                  <div className="mt-1 flex flex-col">
                    {e.ziele.map((z) => <Station key={z.href} z={z} zustand={zustandVon(z)} />)}
                  </div>
                </div>
              </section>
            );
          })}
        </div>
      ) : (
        /* Breite Fassung: vier Etappen-Karten in zwei TEXTSPALTEN — die
           Etappen sind verschieden lang (6/3/4/3 Schritte), ein Raster ließe
           unter den kurzen Leere stehen (Designsprache §4). Die Schwelle
           hängt an der GEMESSENEN Kartenbreite, nicht am Fenster. */
        <div className={cn("mt-3.5 gap-x-4", breite >= 768 && "columns-2")}>
          {etappen.map((e) => (
            <section
              key={e.kicker}
              className={cn(
                "mb-3 break-inside-avoid rounded-xl border border-border p-3",
                e.index === aktiverIndex && gelesenGesamt > 0 && "border-primary/35 bg-primary/[0.03]",
              )}
            >
              {kopfzeile(e)}
              <p className="mt-1 max-w-[74ch] text-[12px] leading-relaxed text-muted-foreground">
                {e.frage}
              </p>
              <div className="mt-1.5 flex flex-col">
                {e.ziele.map((z) => <Station key={z.href} z={z} zustand={zustandVon(z)} />)}
              </div>
            </section>
          ))}
        </div>
      )}

      {/* Ohne diesen Satz sähen die Schritte nach einer Lücke aus: Der
          Bereich hat zwanzig Unterseiten. Die beiden übrigen sind Steckbriefe
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
