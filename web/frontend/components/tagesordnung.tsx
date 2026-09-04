"use client";

/** Die Tagesordnung — einmal gebaut, an zwei Orten gezeigt.
 *
 *  Sie steht in der aufgeklappten Sitzungskarte der Liste
 *  (`app/(app)/council/view.tsx`) UND auf der eigenständigen, ohne Konto
 *  lesbaren Sitzungs-Seite (`app/(app)/council/sitzung`), die hinter jedem
 *  geteilten Link steht. Beide Male dieselben Zeilen, dieselben Ergebnis-
 *  Punkte, derselbe Sprung zum verlinkten Punkt — deshalb wohnt das hier und
 *  nicht zweimal nebeneinander.
 *
 *  Was hier NICHT hingehört: alles, was ein Konto voraussetzt. Der
 *  Merken-Knopf blendet sich ohne Anmeldung selbst aus (s. BookmarkButton),
 *  die „dein Thema"-Marke kommt als Prop von der Liste — die öffentliche Seite
 *  reicht sie schlicht nicht durch.
 */

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { CalendarPlus, ChevronRight, Flame, Paperclip, Users } from "lucide-react";
import {
  AgendaAenderung, AgendaRowItem, AgendaItem, CouncilDecision, CouncilSession, DecisionOutcome, SessionDetail,
  VideoResult,
} from "@/lib/types";
import { Badge, toast } from "@/components/ui";
import { offerIcs } from "@/lib/ics";
import { shortCommittee } from "@/lib/committees";
import { OutcomeDot, normalizeParty, PartyAttendanceBadge } from "@/components/decision-ui";
import { VideoResultChip } from "@/components/video-result";
import { BookmarkButton } from "@/components/bookmark-button";
import { ShareButton } from "@/components/share-button";
import { decisionHref, sitzungHref } from "@/lib/routes";
import { cn } from "@/lib/utils";

export const sessionUrl = (ksinr: number) => `https://buergerinfo.oldenburg.de/si0057.php?__ksinr=${ksinr}`;

/* TOP-Nummern zusammenführen. Die Tagesordnung führt sie mit Sichtbarkeits-
   Präfix („Ö 6.1", „N 12"), das Protokoll ohne („6.1") — ein direkter Vergleich
   trifft deshalb NIE. Der Ergebnis-Punkt an der TOP-Zeile war damit von Anfang
   an tot, und der Beschluss-Link aus 28a/S1 hätte dasselbe Schicksal geteilt.
   Nichtöffentliche Punkte bleiben außen vor: „N 5" und „Ö 5" fielen sonst auf
   denselben Schlüssel, und der öffentliche Beschluss landete an der falschen
   Zeile. */
export const topKey = (n: string | null | undefined) => (n ?? "").replace(/^\p{L}+\s+/u, "").trim();
export const agendaNumber = (n: string | null | undefined) => n?.match(/\d+(?:\.\d+)*/)?.[0] ?? "";
/* Schlüssel für Video-Ergebnisse: wie `topKey`, aber es fallen NUR die
   amtlichen Ö/N-Marker weg. Dringlichkeitsanträge zählen eigenständig —
   „DZT 1" ist nicht „Ö 1". `topKey` verkürzte beide auf „1" und hängte das
   Ergebnis des Antrags an „Feststellung der Beschlussfähigkeit" (02.09.2026);
   spiegelt `videos.strip_prefix` im Backend. */
export const videoKey = (n: string | null | undefined) => (n ?? "").replace(/^[ÖN]\s+/iu, "").trim();

/** Gliederungs-TOPs wie „Anträge der Fraktionen“ haben kein eigenes Ergebnis.
 *  Öffentlicher und nichtöffentlicher Teil werden getrennt betrachtet. */
export const hasAgendaChildren = (item: AgendaRowItem, items: AgendaItem[]) => {
  const parent = agendaNumber(item.item_number);
  if (!parent) return false;
  return items.some((candidate) =>
    Boolean(candidate.is_public) === Boolean(item.is_public)
    && agendaNumber(candidate.item_number).startsWith(`${parent}.`),
  );
};

/* DOM-Kennung einer Tagesordnungszeile — Ziel des `?top=…`-Sprungs aus einer
   Benachrichtigung. Bewusst die VOLLE Nummer, nicht `topKey`: Der wirft das
   Präfix weg, und „Ö 6" (öffentlich) und „N 6" (nichtöffentlich) fielen dann
   auf dieselbe Zeile. Nicht-alphanumerisches wird ersetzt, damit Leerzeichen
   und Umlaute keine ungültige id ergeben. */
export const topDomId = (ksinr: number, itemNumber: string) =>
  `top-${ksinr}-${(itemNumber || "").trim().replace(/[^\p{L}\p{N}]+/gu, "_")}`;

export function itemMatches(it: AgendaRowItem, query: string): boolean {
  const q = query.trim().toLowerCase();
  if (!q) return false;
  return it.title.toLowerCase().includes(q) || (it.template_number?.toLowerCase().includes(q) ?? false);
}

/* Design 28a/R1: JEDES Wort der Eingabe, an JEDER Fundstelle markieren.
   Vorher wurde nur das erste, wörtliche Vorkommen der GANZEN Eingabe getroffen —
   bei „radwege innenstadt" also nie eines, weil die beiden Wörter nirgends
   zusammenhängend stehen. Die Karte war der Treffer, sah aber aus wie keiner,
   und genau daran entstand der Eindruck, die Suche funktioniere nicht.
   Ein-Zeichen-Wörter bleiben außen vor: Die markierten sonst halbe Sätze. */
function highlightRegex(query: string): RegExp | null {
  const words = query
    .trim()
    .split(/\s+/)
    .filter((w) => w.length >= 2)
    .map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"))
    .sort((a, b) => b.length - a.length); // längere zuerst → keine Teiltreffer
  if (words.length === 0) return null;
  return new RegExp(`(${words.join("|")})`, "gi");
}

export function Highlight({ text, query }: { text: string; query: string }) {
  const re = query.trim() && text ? highlightRegex(query) : null;
  if (!re || !text) return <>{text}</>;
  const parts = text.split(re);
  if (parts.length === 1) return <>{text}</>;
  return (
    <>
      {parts.map((part, i) =>
        // split() mit Capture-Group liefert die Treffer an ungeraden Positionen.
        i % 2 === 1 ? (
          <mark key={i} className="rounded bg-amber-200 px-0.5 text-foreground dark:bg-amber-700/60">
            {part}
          </mark>
        ) : (
          part
        ),
      )}
    </>
  );
}
/* Design 28a/S1: Ein TOP, zu dem es einen Beschluss gibt, führt auf dessen Seite.
   Vorher zeigte die Zeile das Ergebnis an (grüner/roter Punkt) und war trotzdem
   toter Text — man musste zurück in die Suche, um den Beschluss zu finden, der
   direkt dahinter liegt. TOPs ohne Beschluss (Berichte, künftige Sitzungen)
   bleiben bewusst ruhiger Text, damit der Zeiger nichts verspricht, was fehlt. */
/** Der eine Satz unter dem Titel — der bessere zuerst.
 *
 *  `social_text` entsteht aus der ganzen Vorlage samt Anlagen, `summary`
 *  allein aus dem Titel („Du kennst nur den Titel des Punktes" steht wörtlich
 *  in deren Prompt) und kann deshalb nicht mehr als die Überschrift
 *  umformulieren. Beide kommen vom Server; die Reihenfolge steht auch dort
 *  (`store.agenda_items`) — hier nur noch die Auswahl fürs Auge. */
export function kurzfassung(it: AgendaRowItem): string | null {
  return it.social_text || it.summary || null;
}

export function AgendaRow({ it, query, outcome, decisionId, myTopic, domId, flash, ksinr, bookmarkable = true, shareable = true, videoResult }: {
  it: AgendaRowItem; query: string; outcome?: DecisionOutcome | null;
  decisionId?: number; myTopic?: string;
  ksinr?: number;
  bookmarkable?: boolean;
  /** Teilen-Knopf an der Zeile: verschickt die Sitzung MIT diesem Punkt —
   *  wer den Link öffnet, landet bei genau dieser Zeile (s. sitzungHref). Aus
   *  der Trefferliste der Suche heraus abgeschaltet: Dort steht die Zeile
   *  ohne ihre Sitzung, und die Aktionen gehören an den Treffer, nicht an
   *  eine Sitzung, die man gerade gar nicht ansieht. */
  shareable?: boolean;
  /** Vorläufiges Ergebnis aus der Videoaufzeichnung — nur solange der TOP
   *  keinen Protokoll-Beschluss hat (das Protokoll gewinnt immer). */
  videoResult?: VideoResult;
  /* Ziel des `?top=…`-Sprungs aus einer Benachrichtigung (s. topDomId). */
  domId?: string;
  /** Kurz nach dem Sprung hervorgehoben — sonst sieht die Zielzeile aus wie
   *  jede andere und man sucht, was gemeint war. */
  flash?: boolean;
}) {
  const hit = itemMatches(it, query);
  const body = (
    <>
      {/* w-10 statt w-7: „Ö 6.2" brach sonst auf zwei Zeilen um und zog die
          ganze Zeile auseinander. */}
      <span className="w-10 shrink-0 whitespace-nowrap text-xs font-medium text-muted-foreground">{it.item_number}</span>
      <div className="min-w-0 flex-1">
        {/* In der Trefferliste der Suche steht der Antrag ohne den Block über
            der Tagesordnung — die Marke muss deshalb an der Zeile selbst
            hängen, sonst liest er sich wie ein gewöhnlicher Punkt. */}
        {it.dringlich && (
          <span className="mb-0.5 flex items-center gap-1 font-mono text-[9.5px] font-semibold uppercase tracking-[0.11em] text-signal">
            <Flame className="h-3 w-3" aria-hidden /> Dringlichkeitsantrag
          </span>
        )}
        <p className="text-sm text-foreground"><Highlight text={it.title} query={query} /></p>
        {/* Ein Satz, worum es geht (Tims Wunsch 12.08.) — der Hinweis
            „Kurzfassung" sagt, dass hier eine Maschine zusammengefasst hat. */}
        {kurzfassung(it) && (
          <p className="mt-0.5 text-[12.5px] leading-relaxed text-muted-foreground">
            <span className="mr-1 font-mono text-[9.5px] uppercase tracking-[0.1em] text-muted-foreground/70">
              Kurzfassung
            </span>
            {kurzfassung(it)}
          </p>
        )}
        {it.template_number && <p className="text-xs text-muted-foreground">Vorlage <Highlight text={it.template_number} query={query} /></p>}
        {/* Tims Befund 12.08.: Die TOP-Anhänge (RIS-PDFs) fehlten in der App
            komplett — gerade Fraktions-Anträge ohne Vorlage hängen NUR hier. */}
        {(it.anlagen?.length ?? 0) > 0 && (
          <p className="mt-0.5 flex flex-wrap gap-x-3 gap-y-0.5">
            {it.anlagen!.map((a) => (
              <a key={a.url} href={a.url} target="_blank" rel="noreferrer"
                onClick={(e) => e.stopPropagation()}
                className="inline-flex max-w-full items-center gap-1 text-xs text-primary hover:underline">
                <Paperclip className="h-3 w-3 shrink-0" aria-hidden />
                <span className="truncate">{a.label}</span>
              </a>
            ))}
          </p>
        )}
        {myTopic && (
          /* RL-902: TOP passt zu einem eigenen Thema. */
          <span className="mt-1 inline-flex rounded-full bg-signal/10 px-2 py-0.5 text-[11px] font-semibold text-signal">
            dein Thema · {myTopic}
          </span>
        )}
      </div>
      {outcome ? <OutcomeDot outcome={outcome} />
        : videoResult ? <VideoResultChip r={videoResult} />
        : !it.is_public ? <Badge color="amber">nichtöffentlich</Badge> : null}
      {decisionId != null && <ChevronRight className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground/50" aria-hidden />}
    </>
  );
  const tone = hit ? "bg-amber-50 dark:bg-amber-950/40" : myTopic ? "bg-signal/5" : "";
  const layout = cn(
    "flex flex-wrap items-start gap-x-3 gap-y-1 rounded-md px-2 py-2",
    // Der Ring verschwindet nach 1,6 s von selbst; die Farbe blendet weich
    // aus, damit die Markierung nicht springt.
    "transition-[box-shadow,background-color] duration-500",
    flash && "bg-primary/[0.07] ring-2 ring-primary",
  );

  const bookmark = bookmarkable && it.is_public && ksinr != null
    ? <BookmarkButton target={{ kind: "agenda_item", ksinr, item_number: it.item_number }} compact className="mt-0.5 shrink-0" />
    : null;

  /* Nichtöffentliche Punkte tragen keinen Teilen-Knopf: Von ihnen steht nur
     die Überschrift da, die geteilte Seite zeigt dem Empfänger also nichts,
     was den Weg lohnt. */
  const teilen = shareable && it.is_public && ksinr != null
    ? (
      <ShareButton
        kompakt
        className="mt-0.5 shrink-0 text-muted-foreground"
        label={`Tagesordnungspunkt ${it.item_number} teilen`}
        path={sitzungHref(ksinr, [it.item_number])}
        title={`${it.item_number} ${it.title}`}
      />
    )
    : null;

  const aktionen = bookmark || teilen
    ? <span className="flex shrink-0 items-start">{teilen}{bookmark}</span>
    : null;

  if (decisionId != null) {
    return (
      <li id={domId} className={cn(layout, tone)}>
        <Link
          href={decisionHref(decisionId)}
          className="flex min-w-0 flex-1 flex-wrap items-start gap-x-3 gap-y-1 transition-colors active:scale-[0.995]"
        >
          {body}
        </Link>
        {aktionen}
      </li>
    );
  }
  return <li id={domId} className={cn(layout, tone)}>{body}{aktionen}</li>;
}

/** „Zuletzt geändert" (Tims Wunsch 18.08.): Ziel der Änderungs-Push — die
 *  Push nennt nur den Satz, hier stehen die Einzelheiten. Farbgrammatik wie
 *  in der Mail: Neues grün, Geändertes gelb, Entferntes rot. */
const AENDERUNG_FARBE: Record<string, string> = {
  new: "border-emerald-500",
  changed: "border-amber-500", moved: "border-amber-500",
  template: "border-amber-500", attachments: "border-amber-500",
  removed: "border-rose-400",
};

function fmtAenderungsDatum(iso: string): string {
  return iso.length >= 10 ? `${iso.slice(8, 10)}.${iso.slice(5, 7)}.${iso.slice(0, 4)}` : iso;
}

export function AenderungenSection({ aenderungen }: { aenderungen: AgendaAenderung[] }) {
  return (
    <div className="mb-3 rounded-lg bg-muted/50 p-3">
      {aenderungen.map((a, i) => (
        <div key={i} className={cn(i > 0 && "mt-3 border-t border-border pt-3")}>
          <p className="font-mono text-[10px] uppercase tracking-[0.11em] text-muted-foreground">
            {i === 0 ? "Zuletzt geändert" : "Davor"} · {fmtAenderungsDatum(a.changed_at)}
          </p>
          <ul className="mt-1.5 space-y-1.5">
            {a.zeilen.map((z, j) => (
              <li key={j} className={cn("border-l-2 pl-2 text-sm leading-snug",
                AENDERUNG_FARBE[z.art] ?? "border-border")}>
                <span className={cn("font-medium", z.art === "removed" && "line-through decoration-muted-foreground/50")}>
                  {z.label}
                </span>
                <span className={cn("text-muted-foreground", z.art === "removed" && "line-through decoration-muted-foreground/50")}>
                  {" — "}{z.title}
                </span>
                {z.nichtoeffentlich && (
                  <span className="ml-1 text-[11px] text-muted-foreground/70">(nichtöffentlich)</span>
                )}
                {z.detail && (
                  <span className="block text-[12px] text-muted-foreground/80">{z.detail}</span>
                )}
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}

/** „Dringlichkeitsantrag: festgestellte PAK-Belastung" → „Festgestellte
 *  PAK-Belastung". Die Marke steht schon im Kicker darüber; bleibt nichts
 *  übrig, steht der ganze Titel da. */
function ohneMarke(title: string): string {
  const rest = title.replace(/^\s*Dringlichkeitsantrag\s*[:–-]\s*/i, "").trim();
  if (!rest) return title;
  return rest[0].toUpperCase() + rest.slice(1);
}

/**
 * Dringlichkeitsanträge — der Teil der Sitzung, der nirgends steht.
 *
 * Ein Dringlichkeitsantrag wird kurzfristig auf die Tagesordnung gehoben und
 * hat im Ratsinformationssystem deshalb **keinen eigenen Punkt**: Er hängt
 * als Dokument an „Ö 2 Genehmigung der Tagesordnung", weil dort über seine
 * Aufnahme abgestimmt wird. `council/dringlichkeit.py` macht daraus eine
 * eigene Zeile mit der Kennung `DZT n`.
 *
 * Sie steht hier über der Tagesordnung statt in ihr, und das ist keine
 * Bequemlichkeit: Der Punkt ist abgeleitet, nicht amtlich — er hat keine
 * Ö-Nummer und in der gedruckten Tagesordnung keine Zeile. Zwischen den
 * amtlichen Punkten stünde er wie einer von ihnen; hier sieht man ihm an,
 * dass er dazugekommen ist.
 *
 * Am Bestand gemessen (40 Ratssitzungen, Juli 2022 – August 2026): zwölfmal,
 * also in 30 % der Sitzungen — Resolution Iran, Anwohnerparken, Lachgas,
 * Fliegerhorst, Platanen am Stadtmuseum. Keine Randthemen.
 */
export function DringlichkeitsBlock({ items, ksinr, videoByItem }: {
  items: AgendaItem[]; ksinr?: number;
  /** Vorläufige Ergebnisse je Schlüssel (s. videoKey) — der Antrag wird
   *  später in der Sitzung auch inhaltlich abgestimmt, und dieses Ergebnis
   *  gehört an SEINE Karte, nicht an einen gleichnamigen Ö-Punkt. */
  videoByItem?: Record<string, VideoResult>;
}) {
  if (items.length === 0) return null;
  return (
    <div className="mb-3 space-y-2">
      {items.map((it) => (
        <div key={it.item_number}
          className="rounded-lg border border-signal/25 bg-signal/[0.05] px-3 py-2.5">
          <div className="flex items-start gap-3">
            <div className="min-w-0 flex-1">
              <span className="flex items-center gap-1.5 font-mono text-[9.5px] font-semibold uppercase tracking-[0.11em] text-signal">
                <Flame className="h-3 w-3" aria-hidden /> Dringlichkeitsantrag
              </span>
              <p className="mt-1 text-sm font-semibold leading-snug text-foreground">
                {ohneMarke(it.title)}
              </p>
              {kurzfassung(it) && (
                <p className="mt-1 text-[12.5px] leading-relaxed text-muted-foreground">
                  {kurzfassung(it)}
                </p>
              )}
              {/* Warum der Punkt anders ist als die anderen — ohne diesen Satz
                  sieht die Hervorhebung nach Laune aus. */}
              <p className="mt-1.5 text-[11.5px] leading-relaxed text-muted-foreground/85">
                Kurzfristig eingebracht: Er steht in keiner Tagesordnung. Zu Beginn
                der Sitzung wird erst darüber abgestimmt, ob er überhaupt behandelt wird.
              </p>
              {videoByItem?.[videoKey(it.item_number)] && (
                <VideoResultChip r={videoByItem[videoKey(it.item_number)]} layout="block" />
              )}
              {(it.anlagen?.length ?? 0) > 0 && (
                <p className="mt-1.5 flex flex-wrap gap-x-3 gap-y-0.5">
                  {it.anlagen!.map((a) => (
                    <a key={a.url} href={a.url} target="_blank" rel="noreferrer"
                      className="inline-flex max-w-full items-center gap-1 text-xs text-primary hover:underline">
                      <Paperclip className="h-3 w-3 shrink-0" aria-hidden />
                      <span className="truncate">Antrag im Ratsinfo</span>
                    </a>
                  ))}
                </p>
              )}
            </div>
            {ksinr != null && (
              <BookmarkButton target={{ kind: "agenda_item", ksinr, item_number: it.item_number }}
                compact className="mt-0.5 shrink-0" />
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

export function AttendanceSection({ detail }: { detail: SessionDetail }) {
  const att = detail.attendance ?? [];
  if (att.length === 0) return null;
  const byParty: Record<string, number> = {};
  for (const a of att) {
    if (a.role === "administration" || a.role === "minutes" || a.role === "guest") continue;
    const p = normalizeParty(a.party || "—");
    byParty[p] = (byParty[p] ?? 0) + 1;
  }
  return (
    <div className="mt-4 border-t border-border pt-3">
      <p className="flex items-center gap-1.5 text-sm font-medium text-muted-foreground">
        <Users className="h-4 w-4" /> Anwesenheit ({att.length})
      </p>
      <div className="mt-2 flex flex-wrap gap-1.5">
        {Object.entries(byParty).sort((a, b) => b[1] - a[1]).map(([p, n]) => (
          <PartyAttendanceBadge key={p} party={p} n={n} />
        ))}
      </div>
    </div>
  );
}
/** Ergebnis-Punkt und Beschluss-Link je TOP, aus den Protokoll-Beschlüssen der
 *  Sitzung — und die vorläufigen Video-Ergebnisse für die TOPs, die noch
 *  keinen haben (das Protokoll gewinnt immer). Eine Schleife, drei Karten:
 *  Beide Ansichten der Tagesordnung brauchen exakt diese drei. */
export function ergebnisseJeTop(detail: SessionDetail | undefined) {
  const outcomeByItem: Record<string, DecisionOutcome | null> = {};
  const decisionByItem: Record<string, number> = {};
  for (const dec of detail?.decisions ?? []) {
    if (dec.kind === "decision" && dec.item_number) {
      const key = topKey(dec.item_number);
      outcomeByItem[key] = dec.outcome;
      decisionByItem[key] ??= dec.id;
    }
  }
  const videoByItem: Record<string, VideoResult> = {};
  for (const v of detail?.video_results ?? []) {
    const key = videoKey(v.item_number);
    if (!(key in outcomeByItem)) videoByItem[key] ??= v;
  }
  return { outcomeByItem, decisionByItem, videoByItem };
}

/** `?top=…` — der Tagesordnungspunkt aus einem geteilten Link oder einer
 *  Benachrichtigung: hinrollen und kurz hervorheben. Gibt die DOM-Id der
 *  hervorgehobenen Zeile zurück (oder null).
 *
 *  `bereit` heißt: Die Tagesordnung ist geladen. Das allein reicht aber nicht,
 *  und in den Zeilen unten stecken drei Fallen, die hier alle schon dazu
 *  geführt haben, dass die Seite oben stehen blieb:
 *
 *  1. Nachgefasst wird mit `setTimeout`, nicht mit requestAnimationFrame.
 *     Genau im gemeldeten Fall — Antippen einer Benachrichtigung — wacht die
 *     App gerade erst auf; ein Fenster, das noch nicht zeichnet, ruft keine
 *     Animationsbilder ab, und die Suche liefe nie an.
 *  2. Das sanfte Scrollen wird **einmal** angestoßen und dann in Ruhe
 *     gelassen. Es läuft über mehrere hundert Millisekunden; wer es in jedem
 *     Durchgang neu anstößt, setzt es immer wieder an den Anfang zurück — die
 *     Seite bewegt sich dann keinen Pixel.
 *  3. Auf das sanfte Scrollen ist kein Verlass. In einem Fenster, das gerade
 *     nicht zeichnet, fällt die Animation ersatzlos aus: Der Aufruf kehrt
 *     zurück, als sei alles gut, und die Seite steht weiter oben. Deshalb wird
 *     kurz darauf nachgesehen — hat sich nichts bewegt, springt es hart.
 */
export function useTopSprung(
  ksinr: number | null, tops: string[], bereit: boolean,
  /** Markierung stehen lassen, statt sie nach 2,5 s ausblenden zu lassen.
   *  Auf der geteilten Sitzungs-Seite ist der Punkt der GRUND, warum die Seite
   *  offen ist — wer sie einen Moment später ansieht (Handy aus der Tasche,
   *  Nachricht erst zu Ende gelesen), soll nicht raten müssen, welche Zeile
   *  gemeint war. In der Sitzungsliste bleibt es beim kurzen Aufblitzen: Dort
   *  hat man die Liste danach noch vor sich und arbeitet weiter mit ihr. */
  dauerhaft = false,
): string | null {
  const [flashTop, setFlashTop] = useState<string | null>(null);
  const done = useRef(false);
  const ziel = ksinr != null && ksinr > 0 && tops.length > 0 ? topDomId(ksinr, tops[0]) : null;

  useEffect(() => {
    if (!ziel || !bereit || done.current) return;
    const sanft = !window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    let versuche = 0;
    let handle = 0 as unknown as ReturnType<typeof setTimeout>;
    let nachschau = 0 as unknown as ReturnType<typeof setTimeout>;
    let entwarnung = 0 as unknown as ReturnType<typeof setTimeout>;
    const suchen = () => {
      const el = document.getElementById(ziel);
      // Die Zeile muss da sein UND die Seite überhaupt scrollbar: Ein Aufruf,
      // während das Dokument noch so hoch ist wie das Fenster, verpufft.
      if (el && document.documentElement.scrollHeight > window.innerHeight + 4) {
        done.current = true;
        // Den Zielpunkt kurz markieren: Nach dem Sprung stand die Zeile zwar
        // in der Mitte, sah aber aus wie jede andere — man musste raten,
        // welche gemeint war (Tims Befund 15.08.). Länger als der Ring um die
        // Sitzungskarte (1,6 s): Der springt ins Auge, während man noch
        // scrollt — die Zeile findet man erst, wenn die Bewegung steht.
        setFlashTop(ziel);
        if (!dauerhaft) entwarnung = setTimeout(() => setFlashTop(null), 2500);
        const vorher = window.scrollY;
        // `center` statt `start`: Die Zeile steht mitten im Bild, mit dem
        // Zusammenhang darüber und darunter — nicht am oberen Rand geklebt.
        el.scrollIntoView({ behavior: sanft ? "smooth" : "auto", block: "center" });
        if (sanft) {
          nachschau = setTimeout(() => {
            const r = el.getBoundingClientRect();
            const imBild = r.top >= 0 && r.bottom <= window.innerHeight;
            // Nur eingreifen, wenn wirklich nichts passiert ist: Eine noch
            // laufende Animation hat sich längst ein Stück bewegt.
            if (!imBild && Math.abs(window.scrollY - vorher) < 4) {
              el.scrollIntoView({ behavior: "auto", block: "center" });
            }
          }, 500);
        }
        return;
      }
      if (++versuche < 40) handle = setTimeout(suchen, 100);
    };
    handle = setTimeout(suchen, 60);
    return () => { clearTimeout(handle); clearTimeout(nachschau); clearTimeout(entwarnung); };
  }, [ziel, bereit, dauerhaft]);

  return flashTop;
}

/** Die TOP-Nummern aus `?top=` — „Ö 6,Ö 7" wird zur Liste. */
export function useTopsAusLink(roh: string | null): string[] {
  return useMemo(() => (roh || "").split(",").map((t) => t.trim()).filter(Boolean), [roh]);
}

/** Design 28a/W2: Sitzung in den eigenen Kalender. Das Ratsinformationssystem
 *  bietet keinen Export — wer den Termin nicht verpassen will, tippt ihn bisher
 *  ab. Die Tagesordnung wandert mit ins Beschreibungsfeld, samt Ratsinfo-Link,
 *  damit der Eintrag auch in vier Wochen noch etwas sagt. */
export function CalendarButton({ session, agenda }: { session: CouncilSession; agenda?: string[] }) {
  // Umlaute umschreiben statt wegwerfen — sonst hieße die Datei
  // „ratslotse-stadtgr-n-klima-….ics".
  const slug = shortCommittee(session.committee)
    .toLowerCase()
    .replace(/ä/g, "ae").replace(/ö/g, "oe").replace(/ü/g, "ue").replace(/ß/g, "ss")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
  return (
    <button
      type="button"
      onClick={(e) => {
        e.stopPropagation();
        offerIcs(
          {
            uid: session.ksinr ? `sitzung-${session.ksinr}` : `termin-${session.session_date}-${slug}`,
            committee: session.committee,
            session_date: session.session_date,
            session_time: session.session_time,
            location: session.location,
            url: session.ksinr ? sessionUrl(session.ksinr) : null,
            // Nur die ersten TOPs: Eine 60-Punkte-Tagesordnung sprengt jede
            // Kalender-Vorschau, der Link führt ohnehin zur vollen Liste.
            agenda: agenda?.slice(0, 12),
          },
          `ratslotse-${slug}-${session.session_date.slice(0, 10)}.ics`,
        ).catch(() => toast.error("Kalendereintrag konnte nicht erzeugt werden."));
      }}
      className="inline-flex items-center gap-1 text-sm text-muted-foreground transition-colors hover:text-primary"
    >
      <CalendarPlus className="h-3.5 w-3.5" /> Kalender
    </button>
  );
}


/** RL-U10: kleiner LIVE-Chip an der laufenden Sitzung — von der Startzeit bis
 *  zur nächsten Sitzung desselben Tages (s. `lib/live`). An Ratstagen trug ihn
 *  vorher der Ausschuss noch, während längst der Rat tagte. */
export function LiveChip() {
  return (
    <span className="inline-flex shrink-0 items-center gap-1 rounded-full bg-red-500/10 px-2 py-0.5 text-[11px] font-bold text-red-600 dark:text-red-400">
      <span className="h-1.5 w-1.5 rounded-full bg-red-500" aria-hidden /> LIVE
    </span>
  );
}


/** Monats/Tages-Kachel 50 px (RL-801, Design 6a-Sitzungen). */
export function DateTile({ iso }: { iso: string }) {
  const d = new Date(iso + "T12:00:00");
  return (
    <span
      // Das Jahr steht am Trenner über der Gruppe, nicht in jeder Kachel —
      // hier bleibt es als Titel erreichbar, ohne die Kachel dreizeilig zu machen.
      title={d.toLocaleDateString("de-DE", { weekday: "long", day: "numeric", month: "long", year: "numeric" })}
      className="w-[50px] shrink-0 rounded-lg border border-border bg-muted/40 py-1 text-center"
    >
      <span className="block font-mono text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
        {d.toLocaleDateString("de-DE", { month: "short" }).replace(".", "")}
      </span>
      <span className="block font-display text-lg font-bold leading-tight text-foreground">{d.getDate()}</span>
    </span>
  );
}
