"use client";

// Quellen-System des Haushalts-Bereichs.
//
// Vorher trug jede Karte eine freitextliche Quellenzeile — gut gemeint, aber
// nicht nachprüfbar: Man sah nicht, WELCHE Zahl aus WELCHER Tabelle stammt,
// und ein Klick führte bestenfalls auf ein 200-seitiges PDF. Jetzt gilt die
// Fußnoten-Grammatik des Ratsgesprächs auch für Zahlen: Jede Angabe trägt
// einen kleinen Beleg-Chip, und am Seitenende steht das Verzeichnis mit
// Dokument, Fundstelle, Stand, Lizenz und Direktlink.
//
// Die Nummerierung läuft SEITENWEISE (1, 2, 3 …), nicht global über das
// Verzeichnis: Sonst trägt eine Seite mit zwei Quellen die Nummern 2 und 4,
// und die Fußnote verweist ins Leere. Welche Quellen eine Seite nutzt, sagt
// sie dem Provider — dieselbe Liste, die unten das Verzeichnis rendert.
//
// ZWEI DINGE, DIE DAS VERZEICHNIS NICHT AUS `QUELLEN` NIMMT
//
// 1. **Das Dokument.** Die Konstante beschreibt eine Quelle über alle
//    Jahrgänge hinweg und trug deshalb eine Adresse, die für alle stimmt —
//    bei sechs Quellen war das `https://buergerinfo.oldenburg.de`, die
//    Startseite. Welches PDF zum gezeigten Jahr gehört, kommt aus
//    `lib/haushalt-dokumente.ts`; die statische Adresse ist der Rückfall.
// 2. **Den Linktext.** Er hängt an der Adresse, nicht an der Quellenart: Wo
//    der Rückfall greift, heißt es „Im Ratsinformationssystem suchen" statt
//    „Dokument öffnen" — ein Link, der etwas anderes verspricht, als er hält,
//    ist schlimmer als keiner.
//
// DER APPARAT AM SEITENFUSS
//
// Quellenverzeichnis und Datenstand standen in derselben Kartenform wie der
// Inhalt darüber — weiße Fläche, Rahmen, Schatten. Wer die Seite herunterlas,
// nahm sie als „noch ein Abschnitt", dabei sind sie Apparat: Belege und
// Reichweite, nicht Aussage (Tim, 16.08.). `Apparat` ist deshalb bewusst die
// Gegenform zur Karte — kein Hintergrund, kein Rahmen, nur eine gestrichelte
// Trennlinie, wie sie im Bereich für „nicht von uns" ohnehin gilt.
//
// Zugeklappt als Voreinstellung, aber mit drei Bedingungen:
//  * Natives `<details>`/`<summary>` — Tastatur und Screenreader können das,
//    ein selbstgebauter Aufklapper kann es meistens nicht.
//  * Die Zusammenfassung sagt, was drinsteckt („5 Quellen"), nicht nur
//    „Quellen".
//  * Die Beleg-Chips im Text springen weiterhin hierher und klappen den
//    Eintrag dabei auf (`zeigeImVerzeichnis`) — sonst zeigten sie ins Nichts.

import {
  createContext, useContext, useEffect, useMemo, useRef, useState,
  type CSSProperties, type ReactNode,
} from "react";
import { ChevronRight, ExternalLink } from "lucide-react";
import {
  QuellenSchluessel, QUELLEN, Quelle, standText, type Jahrgaenge,
} from "@/lib/haushalt-quellen";
import {
  belegziel, belegzieleAlle, nummerierung, nummerFuer, zielart, zielText,
  vorgangVerb, type Belegziel, type DokumenteAntwort,
  type HaushaltDokument, type HaushaltDokumente, type JeDokument,
  type NummerEintrag,
} from "@/lib/haushalt-dokumente";
import type { Herkunft } from "@/lib/herkunft";
import { datumLang, gremiumKurz } from "@/lib/haushalt-streit";
import { GlossaryText } from "@/components/glossary-text";
import { useFetch } from "@/lib/use-fetch";
import { cn } from "@/lib/utils";

type Kontext = {
  schluessel: QuellenSchluessel[];
  dokumente: HaushaltDokumente | undefined;
  /** Die Jahrgänge je Quelle aus dem Bestand — daraus wird der Datenstand
   *  gerechnet, statt ihn von Hand zu pflegen (s. `standText`). */
  jahrgaenge: Jahrgaenge | undefined;
  /** Der Jahrgang, den die Seite gerade zeigt — `null`, wo sie keinen hat. */
  jahr: number | null;
  /** Die Nummern dieser Seite — je Papier oder je Quellenart, s.
   *  `nummerierung`. Chips und Verzeichnis lesen daraus dieselbe Ziffer. */
  eintraege: NummerEintrag[];
};

const SeitenQuellen = createContext<Kontext>({
  schluessel: [], dokumente: undefined, jahrgaenge: undefined, jahr: null,
  eintraege: [],
});

/** Die id des Verzeichnisses am Seitenfuß. Es gibt genau eines je Seite —
 *  die Beleg-Chips brauchen ein Ziel, das sie ohne Umweg aufklappen können. */
const VERZEICHNIS_ID = "quellenverzeichnis";

const eintragId = (k: QuellenSchluessel) => `quelle-${k}`;

/** Den Eintrag einer Quelle im Verzeichnis zeigen: aufklappen, hinscrollen.
 *
 *  Das Aufklappen ist der Teil, der nicht fehlen darf. Ein `<details>` öffnet
 *  sich zwar in neueren Browsern beim Sprung auf ein Fragment darin, aber
 *  nicht in allen — und ein Beleg, der auf eine zugeklappte Lade zeigt, ist
 *  genau das Nichts, das er nicht sein soll. */
function zeigeImVerzeichnis(k: QuellenSchluessel) {
  const lade = document.getElementById(VERZEICHNIS_ID);
  if (lade instanceof HTMLDetailsElement) lade.open = true;
  const eintrag = document.getElementById(eintragId(k));
  eintrag?.scrollIntoView({ behavior: "smooth", block: "center" });
}

/** Klammert die Seite: legt fest, welche Quellen sie nutzt, in welcher
 *  Reihenfolge sie nummeriert werden — und welchen Jahrgang sie zeigt.
 *
 *  `jahr` ist der Grund, warum es diesen Provider gibt und nicht nur eine
 *  Liste: Derselbe Beleg „Jahresabschluss" führt auf acht verschiedene PDFs,
 *  je nachdem, welches Jahr die Seite gerade anzeigt. Seiten ohne Jahrgang
 *  lassen ihn weg; dann nimmt der Beleg das jüngste Dokument und schreibt den
 *  Jahrgang an. */
export function Quellenkontext({ schluessel, jeDokument = LEER, jahr = null, children }: {
  schluessel: QuellenSchluessel[];
  /** Quellenarten, deren Papiere je eine eigene Nummer bekommen sollen.
   *
   *  Je Quellenart die ADRESSEN der Papiere, auf denen einzelne Aussagen der
   *  Seite ruhen — jede Betriebskarte auf dem Plan ihres Betriebs. Ohne diese
   *  Angabe bekäme die ganze Art eine Nummer, und „1 Quelle" stünde über fünf
   *  Dokumenten (s. `nummerierung`).
   *
   *  Der Wert muss über Renderdurchläufe stabil sein (`useMemo`), sonst läuft
   *  die Nummerierung bei jedem Tastendruck neu. */
  jeDokument?: JeDokument;
  jahr?: number | null;
  children: ReactNode;
}) {
  // Ein Aufruf je Seite, wenige Dutzend Zeilen. Bewusst hier und nicht in
  // jeder Seite: Sonst müsste jede von ihnen dieselbe Verkabelung tragen,
  // und die eine, die es vergisst, zeigt wieder auf die Startseite.
  const { data } = useFetch<DokumenteAntwort>("/council/haushalt/dokumente");
  const eintraege = useMemo(
    () => nummerierung(schluessel, jeDokument, data?.dokumente, jahr),
    [schluessel, jeDokument, data?.dokumente, jahr]);
  return (
    <SeitenQuellen.Provider value={{
      schluessel, dokumente: data?.dokumente, jahrgaenge: data?.jahrgaenge, jahr,
      eintraege,
    }}>
      {children}
    </SeitenQuellen.Provider>
  );
}

/** Ein geteiltes leeres Objekt statt `{}` im Vorgabewert: Ein frisches bei
 *  jedem Rendern wäre eine neue Abhängigkeit für `useMemo`, und die
 *  Nummerierung liefe bei jedem Tastendruck neu. */
const LEER: JeDokument = {};

/** Beleg-Chip direkt an der Zahl. Klick öffnet die Fundstelle. */
export function Beleg({ q, h, className }: {
  q: QuellenSchluessel;
  /** Die Herkunft der Zeile, auf der diese Zahl steht — dann trägt der Chip
   *  die Nummer IHRES Papiers und nicht die der Quellenart.
   *
   *  Wirkt nur, wo die Seite die Art über `jeDokument` einzeln nummerieren
   *  lässt; sonst gibt es nur eine Nummer, und die ist auch die richtige. */
  h?: Herkunft | null;
  className?: string;
}) {
  const { offen, setOffen, knopf, faehnchen, lage } = useFaehnchen();
  const { schluessel, dokumente, jahrgaenge, jahr, eintraege } =
    useContext(SeitenQuellen);
  const quelle = QUELLEN[q];
  const idx = schluessel.indexOf(q);
  // Quelle nicht angemeldet: lieber keinen Chip als eine falsche Nummer.
  //
  // ABER NICHT LAUTLOS. Genau das ist am 21.08.2026 aufgefallen: Drei Chips
  // auf zwei Seiten (`/gebaut` zweimal, `/schulden` einmal) zeigten auf
  // „jahresabschluss", das dort nie angemeldet war — sie rendeten nichts, und
  // die Sätze endeten mit einer Fußnote, die es nicht gab. Ein statischer
  // Abgleich findet das nicht zuverlässig, weil Chips auch in Komponenten
  // stehen, die eine Seite erst zur Laufzeit einbindet.
  if (idx < 0) {
    if (process.env.NODE_ENV !== "production") {
      // eslint-disable-next-line no-console
      console.warn(
        `[Beleg] „${q}" steht nicht im Quellenkontext dieser Seite — der Chip `
        + "rendert nichts. Entweder in die QUELLEN der Seite aufnehmen oder "
        + "den Chip entfernen.");
    }
    return null;
  }
  // Die Nummer kommt aus der Zuteilung der Seite, nicht mehr aus der
  // Position in `schluessel`: Wo eine Art mehrere Papiere hat und die Seite
  // sie einzeln nummerieren lässt, trägt jede Zahl die Ziffer IHRES Papiers.
  const eintrag = nummerFuer(eintraege, q, h?.url);
  if (!eintrag) return null;
  const nr = eintrag.nr;
  // Steht die Nummer für genau ein Papier, zeigt das Fähnchen dessen
  // Fundstelle — sonst die der Art (das jüngste Papier des Jahrgangs).
  const ziel = eintrag.dokument
    ? { dokument: eintrag.dokument, jahrgang: eintrag.dokument.jahr,
        abweichend: jahr == null || eintrag.dokument.jahr !== jahr,
        weitere: 0 }
    : belegziel(dokumente, q, jahr);
  return (
    <span className="relative inline-block">
      <button
        ref={knopf}
        type="button"
        onClick={() => setOffen((o) => !o)}
        aria-label={`Beleg ${nr}: ${quelle.titel}`}
        aria-expanded={offen}
        className={cn(
          "ml-0.5 inline-flex h-4 w-4 items-center justify-center rounded bg-primary/10 align-super text-[9px] font-bold text-primary transition-colors hover:bg-primary/20",
          offen && "bg-primary text-primary-foreground",
          className,
        )}
      >
        {nr}
      </button>
      {offen && (
        <span
          ref={faehnchen}
          // `fixed` und nicht `absolute`: Ein absolut gesetztes Fähnchen hängt
          // an seinem Chip, und ein Chip am rechten Textrand schiebt es aus
          // dem Bild — auf dem Handy zuverlässig (Tim, 21.08.2026). Fixiert
          // lässt es sich am Fenster ausrichten statt am Absatz.
          style={lage}
          className="fixed z-30 block max-h-[70vh] overflow-y-auto overscroll-contain rounded-xl border border-border bg-card p-3 text-left shadow-[0_12px_32px_-10px_rgba(2,32,71,0.28)]"
        >
          <QuelleInhalt
            quelle={quelle} nr={nr}
            ziel={ziel}
            jahrgaenge={jahrgaenge?.[q]}
            imVerzeichnis={() => { setOffen(false); zeigeImVerzeichnis(q); }}
          />
        </span>
      )}
    </span>
  );
}

/** Wo das Fähnchen steht — am Fenster ausgerichtet, nicht am Absatz.
 *
 *  Drei Dinge, die ein `absolute`-Fähnchen nicht kann und die auf einem
 *  Handybildschirm alle drei vorkommen:
 *
 *  * **Nicht seitlich hinausragen.** Die Breite ist auf die Fensterbreite
 *    minus zweimal `RAND` gedeckelt, und die linke Kante wird in das Fenster
 *    hineingeschoben, statt vom Chip aus zentriert zu bleiben.
 *  * **Nicht oben abgeschnitten werden.** Ist über dem Chip kein Platz, klappt
 *    es darunter.
 *  * **Beim Scrollen mitgehen.** Sonst stünde es nach zwei Fingerwischen
 *    irgendwo im Nichts.
 */
const RAND = 12;
const BREITE = 300;

// Exportiert, weil der Gesetz-Chip (`components/haushalt/gesetz.tsx`) dasselbe
// Fähnchen öffnet. Zwei Implementierungen hießen: Die Falle, die Tim am
// 21.08.2026 auf dem Handy gefunden hat, wäre in der zweiten wieder drin.
//
// SEIT 26.08.2026 GEHÖRT DEM HOOK AUCH DER OFFEN-ZUSTAND. Vorher hielt ihn
// jeder Chip selbst, und beide hatten denselben Mangel: Das Fähnchen ging nur
// wieder zu, wenn man denselben Chip ein zweites Mal traf (Tim). Ein Klick
// daneben — das, was jeder zuerst versucht — tat nichts. Zustand und
// Schließen-Logik liegen deshalb zusammen an einer Stelle; wer den nächsten
// Chip baut, bekommt beides, ohne daran zu denken.
export function useFaehnchen() {
  const [offen, setOffen] = useState(false);
  const knopf = useRef<HTMLButtonElement>(null);
  // Das Fähnchen selbst — damit ein Klick DARIN es nicht zuklappt. Sonst
  // ließe sich der Text darin nicht markieren, und auf dem Handy schlösse
  // schon das Antippen des Links das Fähnchen, bevor der Link zieht.
  const faehnchen = useRef<HTMLSpanElement>(null);
  const [lage, setLage] = useState<CSSProperties>({ visibility: "hidden" });

  useEffect(() => {
    if (!offen) return;
    const daneben = (e: PointerEvent) => {
      const ziel = e.target as Node | null;
      if (!ziel) return;
      if (knopf.current?.contains(ziel) || faehnchen.current?.contains(ziel)) return;
      setOffen(false);
    };
    const taste = (e: KeyboardEvent) => {
      // Escape gehört dazu, nicht als Zugabe: Wer mit der Tastatur unterwegs
      // ist, hat kein „daneben", auf das er klicken könnte.
      if (e.key === "Escape") { setOffen(false); knopf.current?.focus(); }
    };
    // `pointerdown` statt `click`: Auf dem Handy liegen zwischen Berührung und
    // Klick bis zu 300 ms, in denen das Fähnchen noch offen über dem steht,
    // was jemand treffen wollte. In der Capture-Phase, damit ein Element, das
    // den Klick selbst abfängt, das Schließen nicht verschluckt.
    document.addEventListener("pointerdown", daneben, true);
    document.addEventListener("keydown", taste);
    return () => {
      document.removeEventListener("pointerdown", daneben, true);
      document.removeEventListener("keydown", taste);
    };
  }, [offen]);

  useEffect(() => {
    if (!offen) return;
    const messen = () => {
      const k = knopf.current?.getBoundingClientRect();
      if (!k) return;
      const breite = Math.min(BREITE, window.innerWidth - 2 * RAND);
      const mitte = k.left + k.width / 2 - breite / 2;
      const links = Math.min(Math.max(mitte, RAND),
                             window.innerWidth - breite - RAND);
      // Über dem Chip, wenn dort Platz ist — sonst darunter. Gemessen wird
      // gegen die halbe Fensterhöhe und nicht gegen die tatsächliche Höhe des
      // Fähnchens: Die steht erst nach dem Zeichnen fest, und ein zweiter
      // Durchlauf ließe es sichtbar springen.
      const obenPlatz = k.top > window.innerHeight * 0.45;
      setLage(obenPlatz
        ? { left: links, bottom: window.innerHeight - k.top + 6, width: breite }
        : { left: links, top: k.bottom + 6, width: breite });
    };
    messen();
    window.addEventListener("scroll", messen, true);
    window.addEventListener("resize", messen);
    return () => {
      window.removeEventListener("scroll", messen, true);
      window.removeEventListener("resize", messen);
    };
  }, [offen]);

  return { offen, setOffen, knopf, faehnchen, lage };
}

/** Wo im Dokument die Zahl steht — nur wo die Datenbank es weiß.
 *
 *  Nicht zu verwechseln mit `Quelle.fundstelle`: Das ist der redaktionelle
 *  Absatz über alle Jahrgänge. Dies hier ist der Abschnitt **dieses**
 *  Dokuments, aus `council_herkunft.fundstelle` — die Angabe, mit der man die
 *  Zahl in 300 Seiten tatsächlich wiederfindet. */
function Fundstelle({ ziel }: { ziel: Belegziel }) {
  const { fundstelle, seite } = ziel.dokument;
  if (!fundstelle && seite == null) return null;
  return (
    <span className="mt-1.5 block text-[11px] leading-relaxed text-foreground/80">
      Im Dokument: {fundstelle}
      {seite != null && <>{fundstelle ? ", " : ""}Seite {seite}</>}
    </span>
  );
}

/** Der Ratsvorgang hinter dem Dokument — wo die Datenbank ihn kennt.
 *
 *  Die Ergänzung zu `Fundstelle`: Die sagt, WO im Papier die Zahl steht, dies
 *  hier, WANN der Rat darüber entschieden hat. Damit hängt eine Haushaltszahl
 *  nicht mehr nur an einem PDF, sondern an einem Vorgang, den man
 *  weiterverfolgen kann.
 *
 *  Keine Farbe am Ergebnis — auch nicht rot an „abgelehnt". Der Beleg-Apparat
 *  berichtet, er bewertet nicht (DESIGNSPRACHE § 7); ein grünes
 *  „beschlossen" machte aus einer Herkunftsangabe eine Meinung. */
function Vorgang({ ziel }: { ziel: Belegziel }) {
  const b = ziel.dokument.beschluss;
  if (!b || !b.datum) return null;
  const gremium = b.gremium ? gremiumKurz(b.gremium) : "Der Rat";
  return (
    <span className="mt-1 block text-[11px] leading-relaxed text-foreground/80">
      {gremium} hat das am {datumLang(b.datum)} {vorgangVerb(b.outcome)}
      {b.vorlage_nr && (
        <span className="text-muted-foreground"> · Vorlage {b.vorlage_nr}</span>
      )}
    </span>
  );
}

/** Der Link ans Dokument — oder, wo keines vorliegt, die ehrliche Auskunft.
 *
 *  Beides derselbe Baustein, weil sich beides nur in einem unterscheidet: der
 *  Adresse. Der Text kommt aus ihr (`zielText`), der Jahrgang steht daneben,
 *  sobald das Dokument nicht das des gezeigten Jahres ist. */
function Zeile({ ziel, quelle, klein }: {
  ziel: Belegziel | null; quelle: Quelle; klein?: boolean;
}) {
  const url = ziel?.dokument.url ?? quelle.url;
  if (!url) return null;
  const gross = klein ? "text-[11px]" : "text-[11.5px]";
  return (
    <span className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-0.5">
      <a href={url} target="_blank" rel="noopener noreferrer"
        className={cn("inline-flex items-center gap-1.5 font-semibold text-primary", gross)}>
        {zielText(url)}
        <ExternalLink className="h-3 w-3" />
      </a>
      {/* „Jahrgang 2024" steht NUR da, wo der Link nicht auf das Jahr der
          Seite zeigt. Sonst läse man an jeder Zahl eine Jahreszahl, die schon
          drei Zeilen weiter oben steht. */}
      {ziel?.abweichend && ziel.jahrgang != null && (
        <span className="font-mono text-[9.5px] uppercase tracking-wide text-muted-foreground">
          Jahrgang {ziel.jahrgang}
        </span>
      )}
    </span>
  );
}

function QuelleInhalt({ quelle, nr, ziel, jahrgaenge, imVerzeichnis }: {
  quelle: Quelle; nr: number; ziel: Belegziel | null;
  jahrgaenge: number[] | undefined; imVerzeichnis: () => void;
}) {
  return (
    <>
      <span className="block text-[11.5px] font-bold leading-snug">
        {nr}. {quelle.titel}
      </span>
      {/* DER LANGE ABSATZ STEHT HIER NICHT MEHR (Tim, 21.08.2026: „der Text,
          der dann erscheint, ist wirklich riesig"). `quelle.fundstelle` ist
          ein redaktioneller Absatz über alle Jahrgänge — bei den
          Wirtschaftsplänen sechs Zeilen, die auf einem Handybildschirm den
          halben Platz einnehmen und dabei nicht das beantworten, wofür man
          den Chip angetippt hat: „Wo steht diese Zahl?"

          Diese Frage beantworten `Fundstelle` und der Link. Der Absatz steht
          vollständig im Verzeichnis, und der Knopf unten führt hin. */}
      {ziel && <Fundstelle ziel={ziel} />}
      {ziel && <Vorgang ziel={ziel} />}
      <span className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-0.5 font-mono text-[9.5px] uppercase tracking-wide text-muted-foreground">
        <span>Stand {standText(quelle, jahrgaenge)}</span>
      </span>
      <Zeile ziel={ziel} quelle={quelle} klein />
      {/* Der Rückweg ins Verzeichnis. Dort steht, was hier keinen Platz hat:
          der Absatz zur Quelle, ihr Herausgeber, die Lizenz — und bei
          mehreren Papieren alle neun Teilhaushalts-Anlagen. */}
      <button type="button" onClick={imVerzeichnis}
        className="mt-2 inline-flex items-center gap-1 text-[10.5px] font-medium text-muted-foreground underline decoration-dotted underline-offset-2">
        {ziel && ziel.weitere > 0
          ? `Alle ${ziel.weitere + 1} Dokumente im Verzeichnis`
          : "Mehr zu dieser Quelle"}
      </button>
    </>
  );
}

/** Das Dokument hinter EINER Zeile — mit Namen, nicht als Kategorie.
 *
 *  Der Unterschied zu :func:`Beleg`: Der hochgestellte Chip dort steht für eine
 *  Quellen*art* über alle Jahrgänge („Wirtschaftspläne der Eigenbetriebe") und
 *  führt ins Verzeichnis. Dies hier steht für EIN Papier — den Plan dieses
 *  Betriebs in diesem Jahr, mit der Stelle, an der die Zahl darin steht.
 *
 *  DER BEFUND, DER DAS ERZWUNGEN HAT (Tim, 21.08.2026): Auf `/haushalt/betriebe`
 *  standen 33 Wirtschaftspläne aus sieben Betrieben unter einer einzigen
 *  Quellenangabe, und deren Link führte auf die Startseite des
 *  Ratsinformationssystems — „zu keinem Dokument, zu keiner Suche, zu gar
 *  nichts". Die Vorlagennummer stand sogar auf jeder Karte, aber als toter
 *  Text. Die Daten lagen die ganze Zeit bereit: Jede Zeile trägt ihre
 *  `herkunft_id`, und daran hängen Adresse, Fundstelle und Ratsvorgang.
 *
 *  DER LINK TRÄGT DEN NAMEN DES DOKUMENTS, nicht „Dokument öffnen". Bei einer
 *  Quellenart über acht Jahrgänge ist „Dokument öffnen" die richtige Auskunft —
 *  hier wäre sie die schwächere, denn die Frage, die diese Zeile beantwortet,
 *  ist ja gerade: welches.
 *
 *  Wo die Adresse keine Datei ist, sondern die Vorlagenseite im RIS, steht das
 *  dabei. Ein Link, der mehr verspricht, als er hält, war der Anlass für diesen
 *  ganzen Baustein; ihn hier neu einzuführen wäre absurd. */
export function Dokumentbeleg({ h, vorlageNr, className }: {
  h: Herkunft | null | undefined;
  /** Das Aktenzeichen der Zeile. Bewusst als eigener Wert und nicht aus
   *  `h.beschluss`: Den Vorgang kennt die Datenbank nur, wo die Vorlage im
   *  Bestand steht — die Nummer steht dagegen in jeder Datenzeile. */
  vorlageNr?: string | null;
  className?: string;
}) {
  if (!h) return null;
  // Die Seitenzahl als Sprungmarke: `#page=` verstehen die PDF-Anzeigen der
  // Browser. Wo wir keine haben, bleibt es beim Dokument — eine geratene
  // Seitenzahl wäre schlimmer als keine.
  const ziel = h.url && h.seite != null ? `${h.url}#page=${h.seite}` : h.url;
  const name = h.label ?? "Dokument im Ratsinformationssystem";
  const art = h.url ? zielart(h.url) : null;
  return (
    <span className={cn(
      "mt-1.5 flex flex-wrap items-baseline gap-x-2 gap-y-0.5 text-[11px] leading-relaxed text-muted-foreground",
      className,
    )}>
      {ziel ? (
        <a href={ziel} target="_blank" rel="noopener noreferrer"
          className="inline-flex items-baseline gap-1 font-semibold text-primary">
          {name}
          <ExternalLink className="h-3 w-3 flex-none self-center" />
        </a>
      ) : (
        // Kein Link, aber der Name bleibt: „Wir wissen, aus welchem Papier das
        // stammt, nur nicht, wo es liegt" ist eine Auskunft. Nichts anzeigen
        // hieße auf dieser Seite „dazu gibt es keine Quelle".
        <span className="font-semibold text-foreground/80">{name}</span>
      )}
      {art === "vorlage" && <span>· Vorlagenseite, nicht die Datei</span>}
      {h.fundstelle && <span>· {h.fundstelle}</span>}
      {h.seite != null && <span>· Seite {h.seite}</span>}
      {/* Das Aktenzeichen nur, wo es nicht schon im Namen steht: Manche
          Herkünfte heißen selbst „Vorlage 25/0819", und dann stünde
          „Vorlage 25/0819 · VORLAGE 25/0819" da. */}
      {vorlageNr && !name.includes(vorlageNr) && (
        <span className="font-mono text-[9.5px] uppercase tracking-wide">
          Vorlage {vorlageNr}
        </span>
      )}
    </span>
  );
}

/** Der Apparat am Seitenfuß: zugeklappt, flach, gestrichelt abgesetzt.
 *
 *  Bewusst KEINE Karte. Der Inhalt der Seite steht in Karten; was hier steht,
 *  belegt ihn. Zwei verschiedene Sachen sollen nicht gleich aussehen. */
export function Apparat({ id, kicker, zusatz, children }: {
  id?: string; kicker: string; zusatz: string; children: ReactNode;
}) {
  return (
    <details id={id} className="group border-t border-dashed border-border pt-3">
      {/* `list-none` allein reicht Safari nicht — es zeichnet sein Dreieck
          über `::-webkit-details-marker`, und dann stünden zwei Pfeile da. */}
      <summary className="flex cursor-pointer list-none items-center gap-2 text-muted-foreground marker:hidden hover:text-foreground/80 [&::-webkit-details-marker]:hidden">
        <ChevronRight
          aria-hidden
          className="h-3.5 w-3.5 flex-none transition-transform group-open:rotate-90"
        />
        <span className="font-mono text-[10px] font-medium uppercase tracking-[0.11em]">
          {kicker}
        </span>
        {/* Rechts die ehrliche Zähl-/Zeitraum-Angabe (Designsprache §5): Wer
            zuklappt, muss trotzdem wissen, was in der Lade liegt. */}
        <span className="ml-auto text-right text-[11px] leading-snug">{zusatz}</span>
      </summary>
      {children}
    </details>
  );
}

/** Mehrere Papiere unter einer Quelle — jedes mit Namen und Fundstelle.
 *
 *  Die Langfassung für den Fall, dass ein Jahrgang aus mehr als einem Dokument
 *  besteht: neun Teilhaushalts-Anlagen, sieben Wirtschaftspläne. Der Name kommt
 *  aus `council_herkunft.label` und ist das, wonach jemand sucht — „Vorlage
 *  25/0722" allein wäre ein Aktenzeichen ohne Gegenstand. */
function Dokumentliste({ dokumente, eintraege }: {
  /** Papiere ohne eigene Nummer — sie gehören alle zur Nummer der Art. */
  dokumente?: HaushaltDokument[];
  /** Papiere MIT eigener Nummer. Dann steht die Ziffer vor jedem Titel, und
   *  ein Beleg-Chip im Text kann genau auf sie zeigen. */
  eintraege?: NummerEintrag[];
}) {
  const zeilen = eintraege
    ? eintraege.map((e) => ({ nr: e.nr, d: e.dokument! }))
    : (dokumente ?? []).map((d) => ({ nr: null as number | null, d }));
  return (
    <ul className="mt-1.5 flex flex-col gap-1">
      {zeilen.map(({ nr, d }) => (
        <li key={d.url} className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
          {nr != null && (
            <span className="inline-flex h-4 w-4 flex-none items-center justify-center self-center rounded bg-primary/10 text-[9px] font-bold text-primary">
              {nr}
            </span>
          )}
          <a href={d.seite != null ? `${d.url}#page=${d.seite}` : d.url}
            target="_blank" rel="noopener noreferrer"
            className="inline-flex items-baseline gap-1 text-[11.5px] font-semibold text-primary">
            {d.label || zielText(d.url)}
            <ExternalLink className="h-3 w-3 flex-none self-center" />
          </a>
          {d.fundstelle && (
            <span className="text-[11px] text-muted-foreground">· {d.fundstelle}</span>
          )}
          {d.beschluss?.vorlage_nr
            && !(d.label ?? "").includes(d.beschluss.vorlage_nr) && (
            <span className="font-mono text-[9.5px] uppercase tracking-wide text-muted-foreground">
              Vorlage {d.beschluss.vorlage_nr}
            </span>
          )}
        </li>
      ))}
    </ul>
  );
}

/** Quellenverzeichnis am Seitenende — die Langfassung aller benutzten Belege.
 *
 *  GEZÄHLT WERDEN PAPIERE, NICHT KATEGORIEN (Tim, 21.08.2026). Über fünf
 *  Wirtschaftsplänen aus fünf Betrieben stand „1 Quelle" — richtig gerechnet
 *  nach der alten Regel (eine Nummer je Eintrag der Registratur) und trotzdem
 *  die falsche Auskunft: Wer die Zeile liest, soll sehen, worauf die Seite
 *  ruht, und das sind fünf Dokumente.
 *
 *  Die BESCHREIBUNG der Quellenart steht dabei weiter genau einmal. Sie ist
 *  redaktioneller Text über alle Jahrgänge („Bei den Gesellschaften ist die
 *  einzige nachprüfbare Zahl das beschlossene Jahresergebnis …") und wäre
 *  fünfmal untereinander kein Beleg mehr, sondern eine Wand. */
export function Quellenverzeichnis({ schluessel }: { schluessel: QuellenSchluessel[] }) {
  const { dokumente, jahrgaenge, jahr, eintraege } = useContext(SeitenQuellen);
  if (!schluessel.length) return null;
  // Die Nummern in Gruppen je Quellenart — sie liegen zusammenhängend, weil
  // `nummerierung` die Schlüssel der Reihe nach abarbeitet.
  const gruppen: { k: QuellenSchluessel; nummern: NummerEintrag[] }[] = [];
  for (const e of eintraege) {
    const letzte = gruppen[gruppen.length - 1];
    if (letzte && letzte.k === e.q) letzte.nummern.push(e);
    else gruppen.push({ k: e.q, nummern: [e] });
  }
  const gesamt = eintraege.length;
  return (
    <Apparat
      id={VERZEICHNIS_ID}
      kicker="Quellen"
      zusatz={`${gesamt} ${gesamt === 1 ? "Quelle" : "Quellen"} · woher diese Zahlen kommen`}
    >
      <div className="mt-3 flex flex-col gap-2.5">
        {gruppen.map(({ k, nummern }) => {
          const q = QUELLEN[k];
          const einzeln = nummern.length > 1 || nummern[0].dokument != null;
          const ziel = belegziel(dokumente, k, jahr);
          const alle = nummern[0].dokumente;
          return (
            <div key={k} id={eintragId(k)} className="flex scroll-mt-24 gap-2.5">
              {/* Bei einer Nummer trägt sie die Kategorie; bei mehreren steht
                  vorn keine Ziffer, sondern die Spanne — die Ziffern selbst
                  stehen an den Papieren darunter, wo sie hingehören. */}
              <span className={cn(
                "mt-0.5 inline-flex h-4 flex-none items-center justify-center rounded bg-primary/10 text-[9px] font-bold text-primary",
                nummern.length > 1 ? "w-8" : "w-4",
              )}>
                {nummern.length > 1
                  ? `${nummern[0].nr}\u2013${nummern[nummern.length - 1].nr}`
                  : nummern[0].nr}
              </span>
              <div className="min-w-0">
                <p className="text-[12.5px] font-semibold leading-snug">{q.titel}</p>
                {/* Im Verzeichnis stehen die schwersten Wörter des ganzen
                    Bereichs — „Gesamtermächtigung", „Ergebnisrechnung",
                    „Ertragsart". Sie hier zu erklären kostet nichts und
                    erspart das Nachschlagen woanders. Im kleinen Beleg-Popover
                    bewusst NICHT: 280 px tragen keinen zweiten Tooltip. */}
                <p className="mt-0.5 text-[11.5px] leading-relaxed text-muted-foreground">
                  <GlossaryText text={q.fundstelle} />
                </p>
                <p className="mt-1 flex flex-wrap items-center gap-x-2 font-mono text-[9.5px] uppercase tracking-wide text-muted-foreground">
                  <span>{q.herausgeber}</span><span>·</span>
                  <span>Stand {standText(q, jahrgaenge?.[k])}</span>
                  {q.lizenz && (<><span>·</span><span>{q.lizenz}</span></>)}
                </p>
                {/* EIN Papier ohne eigene Nummer: Fundstelle und Vorgang
                    stehen darüber, der Link darunter heißt „Dokument öffnen".
                    Das war die ganze Bauform dieses Eintrags — und sie stimmt
                    nur, solange es eines ist.

                    MEHRERE: Dann gehörte die Fundstelle oben zu genau einem
                    von ihnen und stand doch über allen („Erfolgsplan der
                    Anlage" über fünf Plänen, von denen vier keine Anlage
                    haben). Jedes Papier bekommt deshalb seine eigene Zeile. */}
                {nummern.length > 1 ? (
                  <Dokumentliste eintraege={nummern} />
                ) : alle.length > 1 ? (
                  <Dokumentliste dokumente={alle} />
                ) : (
                  <>
                    {ziel && <Fundstelle ziel={ziel} />}
                    {ziel && <Vorgang ziel={ziel} />}
                    <Zeile ziel={ziel} quelle={q} />
                  </>
                )}
              </div>
            </div>
          );
        })}
      </div>
      <p className="mt-3 border-t border-dashed border-border pt-2.5 text-[11px] leading-relaxed text-muted-foreground">
        Wir hosten diese Unterlagen nicht, sondern verlinken das Original. Rechenwege, die wir
        selbst gebildet haben (Anteile, Differenzen, Reichweiten), stehen an Ort und Stelle als
        solche gekennzeichnet — sie sind keine amtlichen Kennzahlen.
      </p>
    </Apparat>
  );
}
