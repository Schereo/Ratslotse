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
  createContext, useContext, useState, type ReactNode,
} from "react";
import { ChevronRight, ExternalLink } from "lucide-react";
import {
  QuellenSchluessel, QUELLEN, Quelle, standText, type Jahrgaenge,
} from "@/lib/haushalt-quellen";
import {
  belegziel, belegzieleAlle, zielart, zielText, vorgangVerb,
  type Belegziel, type DokumenteAntwort, type HaushaltDokument,
  type HaushaltDokumente,
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
};

const SeitenQuellen = createContext<Kontext>({
  schluessel: [], dokumente: undefined, jahrgaenge: undefined, jahr: null,
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
export function Quellenkontext({ schluessel, jahr = null, children }: {
  schluessel: QuellenSchluessel[];
  jahr?: number | null;
  children: ReactNode;
}) {
  // Ein Aufruf je Seite, wenige Dutzend Zeilen. Bewusst hier und nicht in
  // jeder Seite: Sonst müsste jede von ihnen dieselbe Verkabelung tragen,
  // und die eine, die es vergisst, zeigt wieder auf die Startseite.
  const { data } = useFetch<DokumenteAntwort>("/council/haushalt/dokumente");
  return (
    <SeitenQuellen.Provider value={{
      schluessel, dokumente: data?.dokumente, jahrgaenge: data?.jahrgaenge, jahr,
    }}>
      {children}
    </SeitenQuellen.Provider>
  );
}

/** Beleg-Chip direkt an der Zahl. Klick öffnet die Fundstelle. */
export function Beleg({ q, className }: { q: QuellenSchluessel; className?: string }) {
  const [offen, setOffen] = useState(false);
  const { schluessel, dokumente, jahrgaenge, jahr } = useContext(SeitenQuellen);
  const quelle = QUELLEN[q];
  const idx = schluessel.indexOf(q);
  // Quelle nicht angemeldet: lieber keinen Chip als eine falsche Nummer.
  if (idx < 0) return null;
  const nr = idx + 1;
  return (
    <span className="relative inline-block">
      <button
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
        <span className="absolute bottom-full left-1/2 z-20 mb-1.5 block w-[280px] -translate-x-1/2 rounded-xl border border-border bg-card p-3 text-left shadow-[0_12px_32px_-10px_rgba(2,32,71,0.28)]">
          <QuelleInhalt
            quelle={quelle} nr={nr}
            ziel={belegziel(dokumente, q, jahr)}
            jahrgaenge={jahrgaenge?.[q]}
            imVerzeichnis={() => { setOffen(false); zeigeImVerzeichnis(q); }}
          />
        </span>
      )}
    </span>
  );
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
      <span className="mt-1 block text-[11px] leading-relaxed text-muted-foreground">
        {quelle.fundstelle}
      </span>
      {ziel && <Fundstelle ziel={ziel} />}
      {ziel && <Vorgang ziel={ziel} />}
      <span className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-0.5 font-mono text-[9.5px] uppercase tracking-wide text-muted-foreground">
        <span>{quelle.herausgeber}</span>
        <span>·</span>
        <span>Stand {standText(quelle, jahrgaenge)}</span>
        {quelle.lizenz && (<><span>·</span><span>{quelle.lizenz}</span></>)}
      </span>
      <Zeile ziel={ziel} quelle={quelle} klein />
      {/* Der Rückweg ins Verzeichnis. Im Popover ist kein Platz für neun
          Teilhaushalts-Anlagen — dort stehen sie vollständig. */}
      <button type="button" onClick={imVerzeichnis}
        className="mt-2 inline-flex items-center gap-1 text-[10.5px] font-medium text-muted-foreground underline decoration-dotted underline-offset-2">
        {ziel && ziel.weitere > 0
          ? `Alle ${ziel.weitere + 1} Dokumente im Verzeichnis`
          : "Im Quellenverzeichnis zeigen"}
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
function Dokumentliste({ dokumente }: { dokumente: HaushaltDokument[] }) {
  return (
    <ul className="mt-1.5 flex flex-col gap-1">
      {dokumente.map((d) => (
        <li key={d.url} className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
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

/** Quellenverzeichnis am Seitenende — die Langfassung aller benutzten Belege. */
export function Quellenverzeichnis({ schluessel }: { schluessel: QuellenSchluessel[] }) {
  const { dokumente, jahrgaenge, jahr } = useContext(SeitenQuellen);
  const genutzt = schluessel;
  if (!genutzt.length) return null;
  return (
    <Apparat
      id={VERZEICHNIS_ID}
      kicker="Quellen"
      zusatz={`${genutzt.length} ${genutzt.length === 1 ? "Quelle" : "Quellen"} · woher diese Zahlen kommen`}
    >
      <ol className="mt-3 space-y-2.5">
        {genutzt.map((k, i) => {
          const q = QUELLEN[k];
          const nr = i + 1;
          const ziel = belegziel(dokumente, k, jahr);
          // ALLE Dokumente des Jahrgangs — bei der Produktebene neun, bei den
          // Wirtschaftsplänen sieben (einer je Betrieb). Im Verzeichnis ist
          // Platz für alle; nur eines zu zeigen hieße, acht Belege zu
          // verschweigen.
          const alle = belegzieleAlle(dokumente, k, jahr);
          return (
            <li key={k} id={eintragId(k)} className="flex scroll-mt-24 gap-2.5">
              <span className="mt-0.5 inline-flex h-4 w-4 flex-none items-center justify-center rounded bg-primary/10 text-[9px] font-bold text-primary">
                {nr}
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
                {/* EIN Dokument: Fundstelle und Vorgang stehen darüber, der
                    Link darunter heißt „Dokument öffnen". Das war die ganze
                    Bauform dieses Eintrags — und sie stimmt nur, solange es
                    eines ist.

                    MEHRERE: Dann gehörte die Fundstelle oben zu genau einem
                    von ihnen und stand doch über allen („Im Dokument:
                    Erfolgsplan der Anlage" über fünf Wirtschaftsplänen, von
                    denen vier gar keine Anlage haben). Deshalb bekommt dort
                    jedes Papier seine eigene Zeile mit seiner eigenen
                    Fundstelle — das ist die Antwort auf „welche Dokumente
                    sind hier benutzt worden?". */}
                {alle.length > 1 ? (
                  <Dokumentliste dokumente={alle} />
                ) : (
                  <>
                    {ziel && <Fundstelle ziel={ziel} />}
                    {ziel && <Vorgang ziel={ziel} />}
                    <Zeile ziel={ziel} quelle={q} />
                  </>
                )}
              </div>
            </li>
          );
        })}
      </ol>
      <p className="mt-3 border-t border-dashed border-border pt-2.5 text-[11px] leading-relaxed text-muted-foreground">
        Wir hosten diese Unterlagen nicht, sondern verlinken das Original. Rechenwege, die wir
        selbst gebildet haben (Anteile, Differenzen, Reichweiten), stehen an Ort und Stelle als
        solche gekennzeichnet — sie sind keine amtlichen Kennzahlen.
      </p>
    </Apparat>
  );
}
