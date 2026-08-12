"use client";

/**
 * Ratsgespräch — der KI-Frage-Tab als Gespräch (Design „Ratsgespräch", RG-01…08
 * plus Feedback-Runde 2 „Beruhigt & gebündelt"):
 *
 * - Composer klebt IMMER unten (auch im Empty State); der Verlauf wächst darüber.
 * - Weiterfragen-Chips liegen im Composer (nur für den jüngsten Turn) und
 *   bleiben damit beim Hochscrollen sichtbar.
 * - Teilen/Drucken sind stille Icons in der Meta-Zeile, keine gerahmten Buttons.
 * - Zitierte Quellen sind einzeilige Pills (Titel + Jahr); Gremium & Datum
 *   stehen im Ausklapper und im Beschluss-Detail.
 * - Desktop: Chat-Spalte + 320-px-Belege-Spalte rechts (Quellen, Presse,
 *   Aktionen des jüngsten Turns); ältere Turns zeigen inline die Kompaktzeile
 *   „Quellen (N) · Presse (M)", aufklappbar.
 */

import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { Sparkles, Send, Loader2, ChevronDown, ChevronRight, ChevronUp, ArrowRight, Plus,
  Square, CircleSlash, ExternalLink, ArrowDown, FlaskConical, History, Pencil, RotateCcw,
  MessageSquarePlus, Share2, ThumbsDown, ThumbsUp, Trash2, Volume2, X,
  BookOpen, SearchX } from "lucide-react";
import dynamic from "next/dynamic";
import { Mascot } from "@/components/mascot";
import type { QaOrtPin } from "@/components/qa-orte-karte";

// 5a/I-10: Leaflet kennt kein SSR — die Mini-Karte kommt nur im Browser.
const QaOrteKarte = dynamic(() => import("@/components/qa-orte-karte"), { ssr: false });
import { QaSource } from "@/lib/types";
import { apiUrl, authHeaders } from "@/lib/api";
import { entwurfAbholen, entwurfMelden } from "@/lib/draft";
import { Button, Input, toast } from "@/components/ui";
import { decisionHref } from "@/lib/routes";
import { PrintButton } from "@/components/print-button";
import { cn } from "@/lib/utils";
import { isNativeApp } from "@/lib/platform";
import { reportBadgeEvent } from "@/components/badges";
import {
  berichtAbschnitte, RechercheFehlerKarte, RechercheFortschritt, RechercheGestoppt,
  RechercheHinweisKarte, RechercheLimitKarte, RechercheToggle, Sprungmarken, WieEsWeitergeht,
  type DeepFacette, type DeepPhase, type Planung,
} from "@/components/deep-recherche";
// Antworttext und Belege-Bausteine teilen sich Gespräch und Teilen-Seite
// (app/g) — sonst driften die beiden Ansichten auseinander.
import {
  AnlagenBlock, AntwortText, DebattenBlock, ParteienListe, PresseBlock,
  type AnlagenHinweis, type DebattenHinweis, type ParteiMeinung, type PresseHinweis,
} from "@/components/qa-bausteine";
import {
  anlagenBuchstaben, ANL_RE, CITE_RE, citationIds, fmtDatumKurz,
} from "@/lib/qa-belege";

/** Bewährte Beispielfragen für den Empty State — kuratiert, nicht beliebig.
 *
 *  Jede Frage lief am 10.08.2026 durch das echte Retrieval des /ask-Endpoints
 *  gegen den Prod-Bestand und musste liefern: mindestens vier Volltreffer
 *  (Relevanz ≥ 0,7), zweistellig viele brauchbare Treffer und Material bis
 *  mindestens 2025. Themen, die im Ratsinformationssystem kaum vorkommen
 *  (Küstenautobahn A20, Straßenbahn, Ärztemangel, E-Ladesäulen), stehen
 *  bewusst NICHT hier — ein Beispiel, das beim ersten Klick eine dünne
 *  Antwort erzeugt, kostet mehr Vertrauen, als Abwechslung einbringt.
 *  Wer die Liste erweitert, misst vorher nach.
 */
const EXAMPLES = [
  "Wie ist der Stand bei der Cäcilienbrücke?",
  "Was wurde zum Radverkehr beschlossen?",
  "Was kostet der Neubau des Stadions?",
  "Gab es Beschlüsse zu Kita-Plätzen?",
  "Was ist beim Fliegerhorst geplant?",
  "Was wurde zur Weser-Ems-Halle beschlossen?",
  "Was wurde zum Thema Parken und Parkgebühren entschieden?",
  "Welche Beschlüsse gibt es zum Klimaschutz?",
  "Welche Beschlüsse gibt es zu Spielplätzen?",
  "Was ist zum Pferdemarkt beschlossen worden?",
  "Welche Sportstätten werden gefördert?",
  "Wie unterstützt die Stadt Kultur und Museen?",
  "Welche neuen Baugebiete hat der Rat beschlossen?",
  "Was wurde zur Gebührenerhöhung bei Müll und Abwasser beschlossen?",
  "Was wurde zur Digitalisierung der Verwaltung beschlossen?",
  "Welche Beschlüsse gibt es zum Thema Jugend und Jugendzentren?",
  "Was tut die Stadt für bezahlbaren Wohnraum?",
  "Was wurde zu Windenergie und Photovoltaik beschlossen?",
  "Welche Schulen werden saniert oder neu gebaut?",
  "Welche Beschlüsse gibt es zu Tempo 30?",
  "Was wurde zum Thema Obdachlosigkeit beschlossen?",
  "Wie viele Bäume werden gefällt und nachgepflanzt?",
];

/** Wörter, die in fast jeder Beispielfrage stehen und deshalb nichts über ihr
 *  Thema aussagen — sie dürfen die Dubletten-Prüfung nicht auslösen. */
const BEISPIEL_STOPP = new Set([
  "beschl", "entsch", "welche", "wurden", "themas", "oldenb", "stadts",
]);

/** Themen-Stämme einer Frage: Wortanfänge (6 Zeichen) der langen Wörter.
 *  Auf Stämmen statt ganzen Wörtern, weil deutsche Komposita sonst
 *  aneinander vorbeilaufen („Stadions" vs. „Stadionneubau"). */
function themenStaemme(frage: string): string[] {
  const woerter = frage.toLowerCase().match(/[a-zäöüß]{6,}/g) ?? [];
  return woerter.map((w) => w.slice(0, 6)).filter((s) => !BEISPIEL_STOPP.has(s));
}

/** Vorschläge aus dem bewährten Pool ziehen — bei jedem Besuch andere, aber
 *  keine, die ein frischer Vorschlag schon abdeckt: sonst steht das Stadion
 *  zweimal untereinander. Wird bewusst erst nach dem Mount aufgerufen; der
 *  statische Export darf nicht gegen ein zufälliges Ergebnis hydrieren. */
function waehleBeispiele(frisch: string[], anzahl: number): string[] {
  if (anzahl <= 0) return [];
  const belegt = new Set(frisch.flatMap(themenStaemme));
  const pool = [...EXAMPLES];
  for (let i = pool.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [pool[i], pool[j]] = [pool[j], pool[i]];
  }
  const frei = pool.filter((f) => !themenStaemme(f).some((s) => belegt.has(s)));
  // Lieber eine thematische Dublette als eine leere Liste.
  return [...frei, ...pool.filter((f) => !frei.includes(f))].slice(0, anzahl);
}

type Step = "expand" | "search" | "answer";
const STEP_LABELS: Record<Step, string> = {
  expand: "Frage wird in Suchbegriffe übersetzt",
  search: "Beschlüsse werden durchsucht und sortiert",
  answer: "Antwort wird formuliert",
};

// Playful rotating status words (Claude-Code-style) shown while the model works.
const PLAYFUL = [
  "Aktenschränke durchwühlen", "Protokolle querlesen", "Paragraphen sortieren",
  "Ratsmehrheiten zählen", "Anträge stapeln", "Beschlüsse abklopfen",
  "Tagesordnungen wälzen", "Fußnoten entstauben", "Vorlagen sichten", "Sitzungssäle durchsuchen",
];

const MODE_LABEL: Record<string, string> = {
  semantisch: "semantische Suche",
  keyword: "Stichwortsuche",
  recherche: "gründliche Recherche",
};

const OUTCOME_BADGE: Record<string, string> = {
  angenommen: "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400",
  abgelehnt: "bg-signal/10 text-signal",
  vertagt: "bg-amber-500/10 text-amber-700 dark:text-amber-400",
  zur_kenntnis: "bg-muted text-muted-foreground",
};
const OUTCOME_LABEL: Record<string, string> = {
  angenommen: "Angenommen", abgelehnt: "Abgelehnt", vertagt: "Vertagt",
  zur_kenntnis: "Zur Kenntnis", kein_beschluss: "Kein Beschluss",
};

/** Gesprächs-Zeile der „Meine Gespräche"-Liste (5a/I-04). */
type GespraechEintrag = { id: number; titel: string; updated: string; n_turns: number };

type Turn = {
  /** Eindeutiger React-Key (monotone Nummer) — nie der Array-Index. */
  key: number;
  frage: string;
  antwort: string;
  qtype: string | null;
  mode: string | null;
  sources: QaSource[];
  presse: PresseHinweis[];
  debatten: DebattenHinweis[];
  cited: number[];
  followups: string[];
  fehler?: "netz" | "limit" | null;
  abgebrochen?: boolean;
  /** 5a/I-06: die vom Backend kondensierte Frage — der Kontext-Chip zeigt,
   *  worauf sich Anschlussfragen beziehen. */
  kontext?: string | null;
  /** RG-10 „Gründliche Recherche": dieser Turn ist ein Recherche-Bericht.
   *  Der Job läuft SERVER-seitig — Tab-Wechsel und App-Navigation sind ihm
   *  egal; deepStatus spiegelt nur den zuletzt bekannten Stand. */
  recherche?: boolean;
  deepJobId?: string;
  deepStatus?: "laeuft" | "gestoppt" | "fehler" | "fertig";
  deepPhase?: DeepPhase;
  deepDokumente?: number | null;
  deepFacetten?: DeepFacette[];
  deepFacettenFertig?: number;
  deepTeilberichtMoeglich?: boolean;
  gelesen?: number;
  zeitraum?: string;
  planungen?: Planung[];
  anlagen?: AnlagenHinweis[];
  /** Wie tragfähig die gefundenen Beschlüsse sind (deterministisch aus den
   *  Relevanz-Werten) — „duenn" blendet einen Ehrlichkeits-Hinweis ein. */
  beleglage?: "solide" | "duenn";
  /** Hintergrund zu den in der Frage genannten Objekten („Was ist die GSG?"). */
  steckbriefe?: { name: string; slug: string; beschreibung: string }[];
};

/** Antwort vorlesen (5a/I-12, nur die TTS-Hälfte): SpeechSynthesis mit
 *  deutscher Stimme, Zitat-Marker und Fettdruck werden nicht mitgelesen.
 *  Bewusst KEIN Diktat-Mikro — Web-Speech-Erkennung fehlt im iOS-WebView,
 *  ein totes Mikro wäre schlimmer als keins (dieselbe Logik wie beim
 *  Druck-Knopf in der App). Knopf erscheint nur, wenn der Browser TTS kann. */
function VorlesenKnopf({ text }: { text: string }) {
  const [kann, setKann] = useState(false);
  const [liest, setLiest] = useState(false);
  useEffect(() => {
    if (typeof window === "undefined" || !("speechSynthesis" in window)) return;
    setKann(true);
    // Chrome liefert getVoices() beim ersten Aufruf oft LEER und füllt die
    // Liste asynchron — ohne diesen Anstoß sprach der miese Browser-Default
    // statt einer guten deutschen Stimme (Tims Befund).
    window.speechSynthesis.getVoices();
    return () => { try { window.speechSynthesis?.cancel(); } catch { /* egal */ } };
  }, []);
  if (!kann || !text) return null;
  const besteStimme = (): SpeechSynthesisVoice | null => {
    const de = window.speechSynthesis.getVoices()
      .filter((v) => v.lang.toLowerCase().startsWith("de"));
    if (de.length === 0) return null;
    // Netzwerk-/Premiumstimmen („Google Deutsch", macOS „Enhanced/Premium",
    // Siri) klingen deutlich natürlicher als die kompakten Lokal-Defaults.
    const guete = (v: SpeechSynthesisVoice) =>
      (/premium|enhanced|siri|natural/i.test(v.name) ? 4 : 0) +
      (!v.localService ? 2 : 0) +
      (v.lang === "de-DE" ? 1 : 0);
    return [...de].sort((a, b) => guete(b) - guete(a))[0];
  };
  const toggle = () => {
    const synth = window.speechSynthesis;
    if (liest) { synth.cancel(); setLiest(false); return; }
    const klartext = text.replace(CITE_RE, "").replace(ANL_RE, "")
      .replace(/\*\*([^*]+)\*\*/g, "$1");
    const u = new SpeechSynthesisUtterance(klartext);
    u.lang = "de-DE";
    const stimme = besteStimme();
    if (stimme) u.voice = stimme;
    u.onend = () => setLiest(false);
    u.onerror = () => setLiest(false);
    synth.cancel();
    synth.speak(u);
    setLiest(true);
  };
  return (
    <button type="button" onClick={toggle}
      aria-label={liest ? "Vorlesen stoppen" : "Antwort vorlesen"}
      title={liest ? "Vorlesen stoppen" : "Vorlesen"}
      className={cn("rounded-md p-1 transition-colors",
        liest ? "text-primary" : "text-muted-foreground hover:bg-muted hover:text-foreground")}>
      {liest ? <Square className="h-3.5 w-3.5 fill-current" aria-hidden />
        : <Volume2 className="h-3.5 w-3.5" aria-hidden />}
    </button>
  );
}

/** Beleg-Peek (5a/I-01): Ein Zitat-Chip öffnet erst die Kurzinfo der Quelle —
 *  Titel, Gremium, Kernaussage — statt sofort wegzuspringen. Von dort geht es
 *  in den Beschluss oder zur Quellenliste. Escape/Backdrop schließen. */
function BelegPeek({ quelle, nummer, onClose, onListe }: {
  quelle: QaSource; nummer: number | undefined; onClose: () => void; onListe: () => void;
}) {
  const router = useRouter();
  const karteRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", esc);
    // Fokus in den Dialog holen — sonst tabbte die Tastatur hinter dem
    // Backdrop weiter und Screenreader erreichten die Aktionen nie (F10).
    karteRef.current?.focus();
    return () => window.removeEventListener("keydown", esc);
  }, [onClose]);
  // Portal an <body>: Im Chat sitzt ein transform-Vorfahre (Einblende-
  // Animationen), der position:fixed einfängt — die Karte klebte dadurch in
  // der App HINTER der Bottom-Nav (iOS-Test 09.08.). Am Body gilt der
  // Viewport wieder; z-[70] schlägt die Nav (z-40), das Bottom-Padding hebt
  // die Karte mobil über sie.
  return createPortal(
    <div className="fixed inset-0 z-[70] flex items-end justify-center p-3 pb-[calc(env(safe-area-inset-bottom)+6.5rem)] sm:items-center sm:pb-3 print:hidden"
      role="dialog" aria-modal="true" aria-label={`Quelle ${nummer ?? ""}`}>
      <button type="button" aria-label="Schließen" onClick={onClose}
        className="absolute inset-0 bg-foreground/25 backdrop-blur-[2px]" />
      <div ref={karteRef} tabIndex={-1}
        className="relative w-full max-w-md animate-fade-up rounded-2xl border border-border bg-card p-4 shadow-xl outline-none">
        <div className="flex items-start gap-2.5">
          <span aria-hidden className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-primary text-[10px] font-bold text-primary-foreground">
            {nummer}
          </span>
          <div className="min-w-0 flex-1">
            <p className="text-sm font-semibold leading-snug text-foreground">{quelle.title}</p>
            <p className="mt-0.5 text-[11px] text-muted-foreground">
              {quelle.committee} · {fmtDatum(quelle.session_date)}
              {quelle.outcome && OUTCOME_LABEL[quelle.outcome] ? ` · ${OUTCOME_LABEL[quelle.outcome]}` : ""}
            </p>
          </div>
          <button type="button" onClick={onClose} aria-label="Schließen"
            className="shrink-0 rounded-md p-1 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground">
            <X className="h-4 w-4" aria-hidden />
          </button>
        </div>
        {quelle.summary && (
          <p className="mt-2.5 text-[13px] leading-relaxed text-muted-foreground">{quelle.summary}</p>
        )}
        <div className="mt-3 flex items-center gap-2">
          <button type="button" onClick={() => router.push(decisionHref(quelle.id))}
            className="inline-flex items-center gap-1.5 rounded-full bg-primary px-3.5 py-1.5 text-xs font-semibold text-primary-foreground transition-colors hover:bg-primary/90">
            Beschluss öffnen <ArrowRight className="h-3 w-3" aria-hidden />
          </button>
          <button type="button" onClick={() => { onClose(); onListe(); }}
            className="rounded-full border border-border px-3 py-1.5 text-xs font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground">
            In Quellenliste zeigen
          </button>
        </div>
      </div>
    </div>,
    document.body,
  );
}

/** Daumen hoch/runter zur KI-Antwort (5a/I-03) — der einzige Qualitätsmesser
 *  außerhalb der Eval-Gold-Fälle. 👎 fragt optional nach dem Grund; gesendet
 *  wird fire-and-forget, der Dank kommt sofort. */
function FeedbackDaumen({ turn }: { turn: Turn }) {
  const [abgegeben, setAbgegeben] = useState<"up" | "down" | null>(null);
  const [frageGrund, setFrageGrund] = useState(false);
  const [grund, setGrund] = useState("");
  const post = (bewertung: "up" | "down", grundText?: string) =>
    void fetch(apiUrl("/council/qa-feedback"), {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify({
        frage: turn.frage.slice(0, 300),
        antwort_auszug: turn.antwort.slice(0, 500) || null,
        bewertung,
        grund: grundText?.trim() || null,
      }),
    }).catch(() => {});
  const senden = (bewertung: "up" | "down") => {
    // Nochmal auf denselben Daumen: nichts zu melden, nichts zu senden — das
    // spart eine Zeile in der Tabelle und einen Schlag aufs Rate-Limit.
    if (bewertung === abgegeben) return;
    const korrektur = abgegeben !== null;
    setAbgegeben(bewertung);
    setFrageGrund(bewertung === "down");
    // Beim Umschwenken auf „hilfreich" ist der alte Grund hinfällig.
    if (bewertung === "up") setGrund("");
    // Der Daumen zählt sofort — auch wenn der Grund nie kommt.
    post(bewertung);
    if (bewertung === "up") toast.success(korrektur ? "Danke — Bewertung geändert." : "Danke für die Rückmeldung!");
  };
  const grundNachreichen = () => {
    setFrageGrund(false);
    // Nur mit echtem Text nachsenden — die Grund-Zeile ersetzt beim Auswerten
    // den nackten Daumen (gleiche Frage, jüngerer Zeitstempel).
    if (grund.trim()) post("down", grund);
    toast.success("Danke für die Rückmeldung!");
  };
  return (
    <span className="flex items-center gap-0.5">
      {/* Beide Daumen bleiben anklickbar: Wer sich vertippt oder es sich
          anders überlegt, muss die Bewertung ändern können (Tims Befund).
          Der nicht gewählte Daumen tritt nur zurück, statt zu erstarren. */}
      <button type="button" aria-label="Antwort war hilfreich" title="Hilfreich"
        aria-pressed={abgegeben === "up"}
        onClick={() => senden("up")}
        className={cn("rounded-md p-1 transition-colors",
          abgegeben === "up" ? "text-primary" : "text-muted-foreground hover:bg-muted hover:text-foreground",
          abgegeben === "down" && "opacity-40 hover:opacity-100")}>
        <ThumbsUp className="h-3.5 w-3.5" aria-hidden />
      </button>
      <button type="button" aria-label="Antwort war nicht hilfreich" title="Nicht hilfreich"
        aria-pressed={abgegeben === "down"}
        onClick={() => senden("down")}
        className={cn("rounded-md p-1 transition-colors",
          abgegeben === "down" ? "text-signal" : "text-muted-foreground hover:bg-muted hover:text-foreground",
          abgegeben === "up" && "opacity-40 hover:opacity-100")}>
        <ThumbsDown className="h-3.5 w-3.5" aria-hidden />
      </button>
      {frageGrund && (
        <form className="ml-1 flex min-w-0 items-center gap-1"
          onSubmit={(e) => { e.preventDefault(); grundNachreichen(); }}>
          {/* 16px auf Touch: Unter 16px zoomt iOS-Safari beim Fokus in das
              Feld hinein (Tims Befund beim Daumen runter). */}
          <input value={grund} onChange={(e) => setGrund(e.target.value)} autoFocus
            placeholder="Was war falsch? (optional)" maxLength={500}
            className="h-7 w-44 min-w-0 rounded-md border border-border bg-card px-2 text-[16px] outline-none placeholder:text-muted-foreground/60 focus:border-primary sm:h-6 sm:w-40 sm:text-[11px]" />
          <button type="submit" className="text-[11px] font-medium text-primary hover:underline">Senden</button>
        </form>
      )}
    </span>
  );
}

/** Chip-Zeile mit verstecktem Scrollbalken (Design 4a): rechts ein Fade als
 *  Scroll-Hinweis plus ein Weiter-Pfeil — horizontales Scrollen per Maus ist
 *  schlecht unterstützt (Tims Feedback), der Pfeil schafft den Zugang. Beides
 *  erscheint nur, solange rechts wirklich noch Chips liegen. */
function ChipZeile({ children }: { children: ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  const [mehr, setMehr] = useState(false);
  const pruefen = () => {
    const el = ref.current;
    setMehr(!!el && el.scrollWidth - el.clientWidth - el.scrollLeft > 8);
  };
  useEffect(() => {
    pruefen();
    const el = ref.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(pruefen);
    ro.observe(el);
    return () => ro.disconnect();
  }, [children]);
  return (
    <div className="relative mb-2">
      {mehr && (
        <>
          <div className="pointer-events-none absolute inset-y-0 right-0 z-10 w-12 bg-gradient-to-l from-background to-transparent" />
          <button type="button" aria-label="Weitere Vorschläge zeigen"
            onClick={() => ref.current?.scrollBy({ left: 260, behavior: "smooth" })}
            className="absolute right-0 top-1/2 z-20 flex h-6 w-6 -translate-y-1/2 items-center justify-center rounded-full border border-border bg-card shadow-sm transition-colors hover:bg-muted">
            <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" aria-hidden />
          </button>
        </>
      )}
      <div ref={ref} onScroll={pruefen}
        className="scrollbar-none flex gap-1.5 overflow-x-auto pb-0.5 pr-8 [-webkit-overflow-scrolling:touch]">
        {children}
      </div>
    </div>
  );
}

/** Gremium mit Artikel für die frische Beispielfrage (5a/I-07). */
function derAusschuss(committee: string): string {
  if (committee === "Rat") return "der Rat";
  if (/ausschuss|beirat/i.test(committee)) return `der ${committee}`;
  return `„${committee}"`;
}

/** TOP-Titel auf den Gegenstand eindampfen, damit „Was wurde zu „…" entschieden?"
 *  eine lesbare Frage ergibt. RIS-Titel schleppen Zusätze mit: Semikolon-Ketten
 *  („…; außerplanmäßige Bewilligung von Mehrausgaben"), Antragsteller-Klammern,
 *  „ - Beschluss", und vorneweg gern die Firmierung des Vorhabenträgers. Ohne
 *  das entsteht der Stummel „Stadion Oldenburg GmbH & Co. KG: Stadionneubau
 *  Maastrichter " — mitten im Wort abgeschnitten. Leerer String = unbrauchbar. */
function kurzerGegenstand(roh: string): string {
  // „(Oldb)" ist der amtliche Namenszusatz und steht mitten im Titel — als
  // Klammer-Trenner behandelt würde er „Satzung der Stadt Oldenburg" übrig
  // lassen und die eigentliche Sache abschneiden.
  let t = roh.replace(/\s*\((?:Oldb|Oldenburg)\.?\)/gi, "").split(/;|\s[-–—(]/)[0].trim();
  // Anführungszeichen raus: der Vorschlag setzt den Gegenstand selbst in „…".
  t = t.replace(/["'‚“”„‘’«»]/g, "")
    .replace(/\s+([:,])/g, "$1").replace(/\s{2,}/g, " ").trim();
  // „Stadion Oldenburg GmbH & Co. KG: Stadionneubau …" — der Firmen-Präfix vor
  // dem Doppelpunkt sagt nichts über die Sache, der Teil dahinter alles.
  const teile = t.match(/^(.{3,70}?):\s+(.{8,})$/);
  if (teile && /\b(GmbH|AG|KG|mbH|e\.\s?V\.|Stiftung|Verband|Betrieb)\b/.test(teile[1])) t = teile[2];
  if (t.length > 58) {
    const schnitt = t.slice(0, 58);
    const luecke = schnitt.lastIndexOf(" ");
    // Nur an einer Wortgrenze kürzen — sonst lieber gar keinen Vorschlag.
    if (luecke < 20) return "";
    t = `${schnitt.slice(0, luecke).replace(/[,;:.\-–—]+$/, "")} …`;
  }
  return t.length >= 8 ? t : "";
}

/** 5a/I-02: „stützt sich auf N Beschlüsse von X bis Y" — Zeitraum-Ehrlichkeit
 *  in der Meta-Zeile; leer, wenn nichts zitiert wurde. */
function stuetztAuf(zitierte: QaSource[]): string {
  if (zitierte.length === 0) return "";
  const jahre = zitierte.map((s) => jahr(s.session_date)).filter(Boolean).sort();
  const n = zitierte.length;
  if (jahre.length === 0) return `stützt sich auf ${n} ${n === 1 ? "Beschluss" : "Beschlüsse"}`;
  const von = jahre[0], bis = jahre[jahre.length - 1];
  const zeitraum = von === bis ? `aus ${von}` : `von ${von} bis ${bis}`;
  return `stützt sich auf ${n} ${n === 1 ? "Beschluss" : "Beschlüsse"} ${zeitraum}`;
}

const fmtDatum = (d?: string | null) =>
  d ? new Date(d).toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric" }) : "";
/** Naives UTC-ISO aus dem Backend (ohne „Z") als UTC deuten — sonst rutscht
 *  ein 00:30-Uhr-Gespräch aufs Vortagsdatum (Befund F14). */
const fmtUtcKurz = (d: string) =>
  fmtDatumKurz(/Z$|[+-]\d\d:?\d\d$/.test(d) ? d : `${d}Z`);
/** Datum + Uhrzeit (lokal) für die Gespräche-Liste — „10.08.26, 20:59".
 *  Server-Zeitstempel sind UTC ohne Suffix, daher das Z-Anfügen. */
const fmtUtcMitZeit = (d: string) => {
  const iso = /Z$|[+-]\d\d:?\d\d$/.test(d) ? d : `${d}Z`;
  return new Date(iso).toLocaleString("de-DE", {
    day: "2-digit", month: "2-digit", year: "2-digit",
    hour: "2-digit", minute: "2-digit",
  });
};
const jahr = (d?: string | null) => (d ? d.slice(0, 4) : "");

/** Relativer Tag fürs Gespräche-Sheet (9a②): „heute · 3 Fragen", „gestern",
 *  sonst „05.08.". Gleiche UTC-Deutung wie fmtUtcMitZeit. */
const relativTag = (d: string) => {
  const iso = /Z$|[+-]\d\d:?\d\d$/.test(d) ? d : `${d}Z`;
  const dann = new Date(iso);
  const tag = (x: Date) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime();
  const diff = Math.round((tag(new Date()) - tag(dann)) / 86_400_000);
  if (diff <= 0) return "heute";
  if (diff === 1) return "gestern";
  return dann.toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit" });
};

const fmtEur = (n: number) =>
  n >= 1_000_000 ? `${(n / 1_000_000).toLocaleString("de-DE", { maximumFractionDigits: 1 })} Mio. €`
    : `${Math.round(n).toLocaleString("de-DE")} €`;

/** Fußnoten-Nummern eines Turns: [id]-Zitate in Reihenfolge des Auftauchens. */
function useIdToNum(turn: Turn) {
  return useMemo(() => {
    const valid = new Set(turn.sources.map((s) => s.id));
    const map = new Map<number, number>();
    for (const g of turn.antwort.matchAll(CITE_RE)) {
      for (const id of citationIds(g[0])) {
        if (valid.has(id) && !map.has(id)) map.set(id, map.size + 1);
      }
    }
    return map;
  }, [turn.antwort, turn.sources]);
}

function zitierteVon(turn: Turn, idToNum: Map<number, number>): QaSource[] {
  const byId = new Map(turn.sources.map((s) => [s.id, s]));
  return [...idToNum.keys()].map((id) => byId.get(id)).filter(Boolean) as QaSource[];
}

/** Anlagen-Fußnoten eines Turns: nr → Buchstabe, in Reihenfolge des
 *  Auftauchens im Text. Nur Marker, zu denen es wirklich eine Anlage gibt —
 *  ein halluziniertes „[A9]" bekommt keinen Buchstaben und wird beim Rendern
 *  ersatzlos geschluckt (wie die ungültigen [id] serverseitig). */
function useAnlagenBuchstaben(turn: Turn) {
  return useMemo(() => anlagenBuchstaben(turn.antwort, turn.anlagen),
    [turn.antwort, turn.anlagen]);
}

/** Sprung zur Quelle: mobil zum Inline-Block, ab lg in die Belege-Spalte. */
function jumpZuQuelle(turnIdx: number, id: number, spalte: boolean) {
  const ziel = spalte && window.matchMedia("(min-width: 1024px)").matches
    ? document.getElementById(`qa-col-${id}`) ?? document.getElementById(`qa-source-${turnIdx}-${id}`)
    : document.getElementById(`qa-source-${turnIdx}-${id}`) ?? document.getElementById(`qa-col-${id}`);
  ziel?.scrollIntoView({ behavior: "smooth", block: "center" });
}

/** Dasselbe für die Anlagen-Karten (eigene Anker, sonst kollidieren Inline-
 *  Block und Belege-Spalte über dieselbe id). */
function jumpZuAnlage(turnIdx: number, nr: number, spalte: boolean) {
  const inline = () => document.getElementById(`qa-anlage-${turnIdx}-${nr}`);
  const col = () => document.getElementById(`qa-anlage-col-${nr}`);
  const ziel = spalte && window.matchMedia("(min-width: 1024px)").matches
    ? col() ?? inline() : inline() ?? col();
  ziel?.scrollIntoView({ behavior: "smooth", block: "center" });
}

export function QaTab({ modeToggle }: { modeToggle?: ReactNode }) {
  const [q, setQ] = useState("");
  const sp = useSearchParams();
  const router = useRouter();
  useEffect(() => {
    // ?q= gehört dem QaTab nur im KI-Modus (im Such-Modus ist es die
    // Stichwortsuche) — und wird nach Übernahme aus der URL entfernt, sonst
    // füllte jeder spätere URL-Wechsel den längst geleerten Composer erneut
    // und Reloads/geteilte Links feuerten die Frage als Suche (Befund F5).
    const urlQ = sp.get("q");
    if (!urlQ || sp.get("mode") !== "fragen") return;
    setQ((prev) => prev || urlQ);
    const params = new URLSearchParams(sp.toString());
    params.delete("q");
    router.replace(`/council?${params.toString()}`, { scroll: false });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sp]);
  useEffect(() => {
    // ?share=<token> (Task 31c): Eingeloggte kommen von einer geteilten
    // Antwort — der Snapshot wird als erster Turn übernommen, Anschluss-
    // fragen tragen dann automatisch dessen Kontext. Nur ins leere Gespräch
    // (nicht mitten in ein laufendes platzen); der Param wird wie ?q= nach
    // Übernahme entfernt.
    const token = sp.get("share");
    if (!token || sp.get("mode") !== "fragen") return;
    const params = new URLSearchParams(sp.toString());
    params.delete("share");
    router.replace(`/council?${params.toString()}`, { scroll: false });
    setTurns((ts) => {
      if (ts.length > 0) return ts;
      fetch(apiUrl(`/council/qa-share/${encodeURIComponent(token)}`))
        .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
        .then((s: {
          frage: string; antwort: string; quellen: QaSource[];
          presse?: PresseHinweis[]; debatten?: DebattenHinweis[]; anlagen?: AnlagenHinweis[];
        }) => {
          setTurns((alt) => alt.length > 0 ? alt : [{
            key: naechsterKey(),
            frage: s.frage, antwort: s.antwort, qtype: null, mode: null,
            // Der Snapshot trägt die Bausteine mit — sonst sähe die Person,
            // die dem Link folgt, weniger als auf der geteilten Seite.
            sources: s.quellen ?? [], presse: s.presse ?? [], debatten: s.debatten ?? [],
            anlagen: s.anlagen ?? [],
            cited: (s.quellen ?? []).map((q) => q.id), followups: [],
            kontext: s.frage,
          }]);
        })
        .catch(() => toast.error("Die geteilte Antwort konnte nicht geladen werden."));
      return ts;
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sp]);
  // Design 29a (P8): Entwurf überlebt den Sitzungs-Rauswurf.
  useEffect(() => entwurfMelden("ki-frage", () => q), [q]);
  useEffect(() => {
    const gerettet = entwurfAbholen("ki-frage");
    if (gerettet) setQ((prev) => prev || gerettet);
  }, []);

  const [turns, setTurns] = useState<Turn[]>([]);
  const [loading, setLoading] = useState(false);
  const [step, setStep] = useState<Step | null>(null);
  const [word, setWord] = useState(PLAYFUL[0]);
  const [showAnchor, setShowAnchor] = useState(false);
  const [flashId, setFlashId] = useState<number | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const endRef = useRef<HTMLDivElement>(null);
  // Eindeutige Turn-Keys über Gesprächswechsel hinweg: Mit dem Array-Index
  // als key erbte ein geladenes Gespräch den lokalen State (Daumen, Peek,
  // TTS) der Turns des vorherigen (Befund F2).
  const turnSeq = useRef(0);
  const naechsterKey = () => ++turnSeq.current;

  const patchLast = (patch: Partial<Turn> | ((t: Turn) => Partial<Turn>)) =>
    setTurns((ts) => {
      if (ts.length === 0) return ts;
      const last = ts[ts.length - 1];
      const p = typeof patch === "function" ? patch(last) : patch;
      return [...ts.slice(0, -1), { ...last, ...p }];
    });
  // RG-10: Recherche-Events patchen ihren Turn über den KEY — während der
  // Server recherchiert, darf im selben Gespräch eine schnelle Frage laufen
  // (patchLast träfe dann den falschen Turn).
  const patchTurn = (key: number, patch: Partial<Turn> | ((t: Turn) => Partial<Turn>)) =>
    setTurns((ts) => ts.map((t) => t.key === key
      ? { ...t, ...(typeof patch === "function" ? patch(t) : patch) } : t));

  useEffect(() => {
    if (!loading) return;
    let i = 0;
    const id = setInterval(() => { i = (i + 1) % PLAYFUL.length; setWord(PLAYFUL[i]); }, 1400);
    return () => clearInterval(id);
  }, [loading]);

  useEffect(() => () => abortRef.current?.abort(), []);

  // „Nach unten"-Anker ab ~1,5 Bildschirmen Abstand zum Gesprächsende (RG-07).
  useEffect(() => {
    const check = () => {
      const el = endRef.current;
      if (!el) return setShowAnchor(false);
      const abstand = el.getBoundingClientRect().top - window.innerHeight;
      setShowAnchor(abstand > window.innerHeight * 0.5);
    };
    window.addEventListener("scroll", check, { passive: true });
    check();
    return () => window.removeEventListener("scroll", check);
  }, [turns.length]);

  const flash = (id: number) => {
    setFlashId(id);
    window.setTimeout(() => setFlashId((f) => (f === id ? null : f)), 1600);
  };

  const ask = async (question: string) => {
    const text = question.trim();
    if (text.length < 4) return;
    try { localStorage.setItem("ratslotse:qa-benutzt", "1"); } catch {}
    reportBadgeEvent("frage"); // RL-U12: Erste Frage
    const unterbrochen = loading;
    abortRef.current?.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    // Gesprächskontext (Paket A): die letzten Runden, Antworten gekürzt.
    const verlauf = turns
      .filter((t) => t.antwort && !t.fehler)
      .slice(-4)
      .map((t) => ({ frage: t.frage.slice(0, 300), antwort: t.antwort.slice(0, 600) }));
    setQ("");
    setLoading(true);
    setStep("expand");
    // Wer mitten im Stream weiterfragt („Dazu fragen"-Icons sind bewusst
    // klickbar), lässt den alten Turn ehrlich als abgebrochen zurück statt
    // als kommentarlosen Texttorso (Befund F4).
    setTurns((ts) => [...ts.map((t, i) => ({
      ...t, followups: [],
      abgebrochen: t.abgebrochen || (unterbrochen && i === ts.length - 1 && !t.fehler) || undefined,
    })), {
      key: naechsterKey(),
      frage: text, antwort: "", qtype: null, mode: null,
      sources: [], presse: [], debatten: [], cited: [], followups: [],
    }]);
    requestAnimationFrame(() => endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" }));

    try {
      const res = await fetch(apiUrl("/council/ask"), {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({ question: text, verlauf, gespraech_id: gespraechId }),
        signal: ctrl.signal,
      });
      if (!res.ok || !res.body) {
        if (res.status === 429) {
          // Wie im Netz-Fehlerpfad: Die Frage gehört zurück ins Eingabefeld,
          // damit nach der Verschnaufpause ein Neuversuch möglich ist (F8).
          patchLast({ fehler: "limit" });
          setQ(text);
          return;
        }
        let msg = "Frage fehlgeschlagen.";
        try { const b = await res.json(); if (b?.detail) msg = typeof b.detail === "string" ? b.detail : msg; } catch { /* ignore */ }
        throw new Error(msg);
      }
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buf = "";
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const chunks = buf.split("\n\n");
        buf = chunks.pop() ?? "";
        for (const chunk of chunks) {
          const line = chunk.replace(/^data: ?/, "").trim();
          if (!line) continue;
          let msg: { type: string; [k: string]: unknown };
          try { msg = JSON.parse(line); } catch { continue; }
          if (msg.type === "step") setStep(msg.step as Step);
          else if (msg.type === "sources") patchLast({
            sources: msg.sources as QaSource[],
            mode: (msg.mode as string) ?? null,
            qtype: (msg.qtype as string) ?? null,
            presse: (msg.presse as PresseHinweis[]) ?? [],
            debatten: (msg.debatten as DebattenHinweis[]) ?? [],
            kontext: (msg.frage as string) ?? null,
            planungen: (msg.planungen as Planung[]) ?? [],
            beleglage: (msg.beleglage as "solide" | "duenn") ?? undefined,
            steckbriefe: (msg.steckbriefe as Turn["steckbriefe"]) ?? [],
          });
          else if (msg.type === "token") patchLast((t) => ({ antwort: t.antwort + (msg.text as string) }));
          // Riss der LLM-Stream mitten in der Antwort, generiert das Backend
          // einmal komplett neu und ersetzt den Torso (Befund 10.08.).
          else if (msg.type === "replace") patchLast({ antwort: (msg.text as string) ?? "" });
          else if (msg.type === "abbruch") patchLast({ abgebrochen: true });
          else if (msg.type === "suggestions") patchLast({ followups: (msg.questions as string[]) ?? [] });
          else if (msg.type === "done") {
            patchLast({ cited: (msg.cited as number[]) ?? [] });
            // null heißt: Server konnte/durfte nicht (mehr) in dieses Gespräch
            // speichern (z. B. auf anderem Gerät gelöscht) — die tote id nicht
            // weiter mitschicken, die nächste Frage eröffnet frisch (F3).
            if (msg.gespraech_id != null) setGespraechId(msg.gespraech_id as number);
            else if ("gespraech_id" in msg) setGespraechId(null);
          }
          else if (msg.type === "error") throw new Error((msg.message as string) ?? "Frage fehlgeschlagen.");
        }
      }
    } catch (e) {
      if ((e as Error)?.name === "AbortError") return;
      // Fehler-Turn: Die Frage ist nicht verloren — zurück ins Eingabefeld.
      patchLast({ fehler: "netz" });
      setQ(text);
      toast.error(e instanceof Error ? e.message : "Frage fehlgeschlagen.");
    } finally {
      if (abortRef.current === ctrl) {
        setLoading(false);
        setStep(null);
        abortRef.current = null;
      }
    }
  };

  /** Stopp: abgebrochener Text bleibt mit Vermerk stehen (RG-07). */
  const stopAsking = () => {
    const ctrl = abortRef.current;
    if (!ctrl) return;
    abortRef.current = null;
    ctrl.abort();
    setLoading(false);
    setStep(null);
    patchLast({ abgebrochen: true });
  };

  // ---- „Gründliche Recherche" (RG-10) ------------------------------------
  // Der Job läuft SERVER-seitig; hier lebt nur die Anzeige-Verbindung. Ein
  // Verbindungsriss (Tab-Wechsel, App im Hintergrund) ist folgenlos: der
  // Loop verbindet sich neu und holt verpasste Events per ?ab=-Replay nach.
  const [rechercheModus, setRechercheModus] = useState(false);
  const [deepFrei, setDeepFrei] = useState<number | null>(null);
  const [deepLimit, setDeepLimit] = useState(false);
  const [deepHinweis, setDeepHinweis] = useState(false);
  const deepStreams = useRef(new Map<string, AbortController>());
  const deepAb = useRef(new Map<string, number>());
  useEffect(() => {
    const streams = deepStreams.current;
    return () => streams.forEach((c) => c.abort());
  }, []);

  const toggleRecherche = () => {
    setRechercheModus((an) => {
      if (!an) {
        // Erwartung ehrlich (8a①): einmal täglich die ausführliche Karte,
        // danach reicht die Kurzform neben der Pill.
        const heute = new Date().toISOString().slice(0, 10);
        let gesehen: string | null = null;
        try {
          gesehen = localStorage.getItem("ratslotse:recherche-hinweis");
          localStorage.setItem("ratslotse:recherche-hinweis", heute);
        } catch { /* egal */ }
        setDeepHinweis(gesehen !== heute);
      } else {
        setDeepHinweis(false);
      }
      return !an;
    });
  };

  /** Fertigen/gescheiterten Job aus der DB in einen Turn übersetzen —
   *  deckungsgleich mit dem Live-Pfad, damit App-Neustarts nichts verlieren. */
  const deepSnapshotTurn = (job: {
    id: string; frage: string; status: string; bericht?: string | null;
    quellen?: { sources?: QaSource[]; presse?: PresseHinweis[]; debatten?: DebattenHinweis[];
      planungen?: Planung[]; anlagen?: AnlagenHinweis[]; cited?: number[];
      gelesen?: number; zeitraum?: string;
      facetten?: string[]; facetten_fertig?: number } | null;
  }): Turn => ({
    key: naechsterKey(),
    frage: job.frage, antwort: job.bericht ?? "", qtype: "deep", mode: "recherche",
    sources: job.quellen?.sources ?? [], presse: job.quellen?.presse ?? [],
    debatten: job.quellen?.debatten ?? [], anlagen: job.quellen?.anlagen ?? [],
    cited: job.quellen?.cited ?? [],
    followups: [], kontext: job.frage,
    recherche: true, deepJobId: job.id,
    deepStatus: job.status === "fehler" ? "fehler"
      : job.status === "gestoppt" ? "gestoppt" : "fertig",
    deepFacetten: (job.quellen?.facetten ?? []).map((name) => ({ name })),
    deepFacettenFertig: job.quellen?.facetten_fertig ?? 0,
    deepTeilberichtMoeglich: false,
    gelesen: job.quellen?.gelesen, zeitraum: job.quellen?.zeitraum,
    planungen: job.quellen?.planungen ?? [],
  });

  const deepGesehenMelden = (jobId: string) => {
    // Nur melden, wenn der Tab gerade SICHTBAR ist: wird der Bericht fertig,
    // während die App im Hintergrund liegt, bliebe er sonst als „gesehen"
    // markiert und der nächste Besuch fände ein leeres Gespräch vor.
    if (typeof document !== "undefined" && document.visibilityState !== "visible") return;
    void fetch(apiUrl(`/council/deep-research/${jobId}/gesehen`), {
      method: "POST", credentials: "include", headers: authHeaders(),
    }).catch(() => {});
  };

  /** Endzustand aus der DB holen (Job nicht mehr im Speicher, Neustart …). */
  const ladeDeepSnapshot = async (jobId: string, turnKey: number) => {
    try {
      const r = await fetch(apiUrl(`/council/deep-research/${jobId}`), {
        credentials: "include", headers: authHeaders() });
      if (!r.ok) throw new Error();
      const job = await r.json();
      const t = deepSnapshotTurn(job);
      patchTurn(turnKey, { ...t, key: turnKey });
      if (t.deepStatus === "fertig") deepGesehenMelden(jobId);
    } catch {
      patchTurn(turnKey, { deepStatus: "fehler" });
    }
  };

  /** SSE-Anschluss mit Wiederverbinden: Events zählen, bei Riss ab dem
   *  letzten Stand weiter — Token-Replays hängen so nie doppelt an. */
  const verbindeDeep = (jobId: string, turnKey: number, abStart?: number) => {
    deepStreams.current.get(jobId)?.abort();
    const ctrl = new AbortController();
    deepStreams.current.set(jobId, ctrl);
    if (abStart !== undefined) deepAb.current.set(jobId, abStart);
    if ((deepAb.current.get(jobId) ?? 0) === 0) {
      // Frischer Aufbau ab Event 0: eventuell schon gezeigten Text
      // verwerfen, der Replay liefert gleich alles erneut.
      patchTurn(turnKey, { antwort: "" });
    }

    const verarbeite = (msg: { type: string; [k: string]: unknown }): boolean => {
      if (msg.type === "phase") {
        patchTurn(turnKey, { deepPhase: msg.phase as DeepPhase,
          deepDokumente: (msg.dokumente as number) ?? null });
      } else if (msg.type === "facetten") {
        patchTurn(turnKey, {
          deepFacetten: ((msg.facetten as string[]) ?? []).map((name) => ({ name })),
          deepFacettenFertig: 0, deepPhase: "suchen",
        });
      } else if (msg.type === "facette") {
        patchTurn(turnKey, (t) => ({
          deepFacetten: (t.deepFacetten ?? []).map((f, i) =>
            i === ((msg.fertig as number) ?? 1) - 1
              ? { ...f, treffer: (msg.treffer as number) ?? 0, neu: (msg.neu as number) ?? 0 } : f),
          deepFacettenFertig: (msg.fertig as number) ?? 0,
        }));
      } else if (msg.type === "sources") {
        patchTurn(turnKey, {
          sources: (msg.sources as QaSource[]) ?? [],
          mode: (msg.mode as string) ?? null, qtype: (msg.qtype as string) ?? null,
          presse: (msg.presse as PresseHinweis[]) ?? [],
          debatten: (msg.debatten as DebattenHinweis[]) ?? [],
          planungen: (msg.planungen as Planung[]) ?? [],
          anlagen: (msg.anlagen as AnlagenHinweis[]) ?? [],
          gelesen: (msg.gelesen as number) ?? undefined,
          zeitraum: (msg.zeitraum as string) ?? undefined,
          kontext: (msg.frage as string) ?? null,
        });
      } else if (msg.type === "token") {
        patchTurn(turnKey, (t) => ({ antwort: t.antwort + (msg.text as string) }));
      } else if (msg.type === "replace") {
        // Server hat den Berichts-Stream neu angesetzt (Provider-Riss) —
        // der bisherige Torso wird ersetzt, es kommt ein frischer Aufbau.
        patchTurn(turnKey, { antwort: (msg.text as string) ?? "" });
      } else if (msg.type === "done") {
        patchTurn(turnKey, { deepStatus: "fertig", cited: (msg.cited as number[]) ?? [],
          gelesen: (msg.gelesen as number) ?? undefined,
          zeitraum: (msg.zeitraum as string) ?? undefined });
        if (msg.gespraech_id != null) setGespraechId(msg.gespraech_id as number);
        deepGesehenMelden(jobId);
        return true;
      } else if (msg.type === "gestoppt") {
        patchTurn(turnKey, { deepStatus: "gestoppt",
          deepFacettenFertig: (msg.facetten_fertig as number) ?? 0,
          deepTeilberichtMoeglich: Boolean(msg.teilbericht_moeglich) });
        return true;
      } else if (msg.type === "fehler") {
        patchTurn(turnKey, { deepStatus: "fehler" });
        deepGesehenMelden(jobId);
        return true;
      }
      return false;
    };

    const lauf = async () => {
      let beendet = false;
      while (!beendet && !ctrl.signal.aborted) {
        try {
          const ab = deepAb.current.get(jobId) ?? 0;
          const res = await fetch(apiUrl(`/council/deep-research/${jobId}/events?ab=${ab}`), {
            credentials: "include", headers: authHeaders(), signal: ctrl.signal });
          if (res.status === 410) {
            // Job lebt nicht mehr im Speicher → Endzustand aus der DB.
            await ladeDeepSnapshot(jobId, turnKey);
            return;
          }
          if (!res.ok || !res.body) throw new Error(String(res.status));
          const reader = res.body.getReader();
          const decoder = new TextDecoder();
          let buf = "";
          for (;;) {
            const { done, value } = await reader.read();
            if (done) break;
            buf += decoder.decode(value, { stream: true });
            const chunks = buf.split("\n\n");
            buf = chunks.pop() ?? "";
            for (const chunk of chunks) {
              if (chunk.startsWith(":")) continue; // Keepalive
              const line = chunk.replace(/^data: ?/, "").trim();
              if (!line) continue;
              let msg: { type: string; [k: string]: unknown };
              try { msg = JSON.parse(line); } catch { continue; }
              deepAb.current.set(jobId, (deepAb.current.get(jobId) ?? 0) + 1);
              if (verarbeite(msg)) beendet = true;
            }
          }
        } catch (e) {
          if ((e as Error)?.name === "AbortError") return;
        }
        // Riss ohne Terminal-Event: kurz durchatmen, dann ab letztem Stand
        // neu verbinden — der Server recherchiert währenddessen weiter.
        if (!beendet && !ctrl.signal.aborted) await new Promise((r) => setTimeout(r, 2000));
      }
    };
    void lauf();
  };

  const askDeep = async (question: string) => {
    const text = question.trim();
    if (text.length < 4) return;
    try { localStorage.setItem("ratslotse:qa-benutzt", "1"); } catch { /* egal */ }
    setQ("");
    setRechercheModus(false); // gilt je Frage, rastet nicht ein (8d)
    setDeepHinweis(false);
    setDeepLimit(false);
    const key = naechsterKey();
    setTurns((ts) => [...ts.map((t) => ({ ...t, followups: [] })), {
      key, frage: text, antwort: "", qtype: "deep", mode: "recherche",
      sources: [], presse: [], debatten: [], cited: [], followups: [],
      recherche: true, deepStatus: "laeuft" as const, deepPhase: "zerlegen" as const,
      deepFacetten: [], deepFacettenFertig: 0,
    }]);
    requestAnimationFrame(() => endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" }));
    try {
      const res = await fetch(apiUrl("/council/deep-research"), {
        method: "POST", credentials: "include",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({ frage: text, gespraech_id: gespraechId }),
      });
      if (res.status === 429) {
        setTurns((ts) => ts.filter((t) => t.key !== key));
        setDeepFrei(0);
        setDeepLimit(true);
        setQ(text);
        return;
      }
      if (!res.ok) {
        let msg = "Recherche konnte nicht gestartet werden.";
        try { const b = await res.json(); if (typeof b?.detail === "string") msg = b.detail; } catch { /* egal */ }
        throw new Error(msg);
      }
      const b = await res.json();
      setDeepFrei(typeof b.frei === "number" ? b.frei : null);
      patchTurn(key, { deepJobId: b.job_id });
      verbindeDeep(b.job_id, key, 0);
    } catch (e) {
      setTurns((ts) => ts.filter((t) => t.key !== key));
      setQ(text);
      toast.error(e instanceof Error ? e.message : "Recherche konnte nicht gestartet werden.");
    }
  };

  const deepStop = async (t: Turn) => {
    if (!t.deepJobId) return;
    try {
      const r = await fetch(apiUrl(`/council/deep-research/${t.deepJobId}/stop`), {
        method: "POST", credentials: "include", headers: authHeaders() });
      if (!r.ok) throw new Error();
      const b = await r.json();
      patchTurn(t.key, { deepStatus: "gestoppt",
        deepFacettenFertig: b.facetten_fertig ?? 0,
        deepTeilberichtMoeglich: Boolean(b.teilbericht_moeglich) });
    } catch {
      toast.error("Abbrechen hat nicht geklappt — die Recherche läuft weiter.");
    }
  };

  const deepTeilbericht = async (t: Turn) => {
    if (!t.deepJobId) return;
    patchTurn(t.key, { deepStatus: "laeuft", deepPhase: "schreiben" });
    try {
      const r = await fetch(apiUrl(`/council/deep-research/${t.deepJobId}/teilbericht`), {
        method: "POST", credentials: "include", headers: authHeaders() });
      if (!r.ok) throw new Error();
      // Weiter am bestehenden Event-Zähler — der Teilbericht hängt seine
      // Events an dieselbe Liste an.
      verbindeDeep(t.deepJobId, t.key);
    } catch {
      patchTurn(t.key, { deepStatus: "gestoppt" });
      toast.error("Teilbericht konnte nicht gestartet werden.");
    }
  };

  const deepVerwerfen = (t: Turn) => {
    if (t.deepJobId) {
      deepStreams.current.get(t.deepJobId)?.abort();
      deepGesehenMelden(t.deepJobId);
    }
    setTurns((ts) => ts.filter((x) => x.key !== t.key));
  };

  // Nach Navigation oder App-Neustart: läuft noch eine Recherche (oder wartet
  // ein ungesehener Bericht), holt der leere Tab sie zurück ins Gespräch —
  // „der Bericht erscheint hier im Gespräch" gilt damit wirklich (8d).
  useEffect(() => {
    fetch(apiUrl("/council/deep-research/aktuell"), { credentials: "include", headers: authHeaders() })
      .then((r) => (r.ok ? r.json() : null))
      .then((b) => {
        if (!b) return;
        if (typeof b.frei === "number") setDeepFrei(b.frei);
        const job = b.job as { id: string; frage: string; status: string; gesehen: number } | null;
        if (!job) return;
        if (job.status === "laeuft") {
          setTurns((ts) => {
            if (ts.length > 0) return ts;
            const key = naechsterKey();
            verbindeDeep(job.id, key, 0);
            return [{
              key, frage: job.frage, antwort: "", qtype: "deep", mode: "recherche",
              sources: [], presse: [], debatten: [], cited: [], followups: [],
              recherche: true, deepJobId: job.id, deepStatus: "laeuft",
              deepPhase: "zerlegen", deepFacetten: [], deepFacettenFertig: 0,
            }];
          });
        } else if (!job.gesehen && (job.status === "fertig" || job.status === "teilbericht" || job.status === "fehler")) {
          setTurns((ts) => {
            if (ts.length > 0) return ts;
            fetch(apiUrl(`/council/deep-research/${job.id}`), { credentials: "include", headers: authHeaders() })
              .then((r) => (r.ok ? r.json() : Promise.reject(new Error())))
              .then((voll) => {
                setTurns((alt) => (alt.length > 0 ? alt : [deepSnapshotTurn(voll)]));
                deepGesehenMelden(job.id);
              })
              .catch(() => {});
            return ts;
          });
        }
      })
      .catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /** Eine NEUE Frage stellen — in dem Modus, der gerade eingeschaltet ist.
   *
   *  Vorschläge, Weiterfragen-Chips und „Dazu fragen" gingen bisher immer den
   *  schnellen Weg, auch wenn „Gründlich recherchieren" aktiv war: Man tippt
   *  den Kolben an, klickt einen Vorschlag — und bekommt wortlos die schnelle
   *  Antwort (Tims Befund). Nur das Absenden im Composer las den Schalter.
   *
   *  Ausdrücklich NICHT hierüber laufen die Verfeinerungen der schon
   *  vorliegenden Antwort („Einfacher erklären", „Ausführlicher"), der erneute
   *  Versuch nach einem Fehler und „stattdessen schnell fragen" — die meinen
   *  jeweils genau einen Weg. */
  const frageStellen = (text: string) => void (rechercheModus ? askDeep(text) : ask(text));

  const neuesGespraech = () => {
    abortRef.current?.abort();
    abortRef.current = null;
    setLoading(false);
    setStep(null);
    setTurns([]);
    setQ("");
    setGespraechId(null);
    inputRef.current?.focus();
  };

  const letzter = turns.length > 0 ? turns[turns.length - 1] : null;
  const letzterFehler = letzter?.fehler;
  // RG-10: solange die Recherche des jüngsten Turns läuft, bleiben die
  // Register-Chips und die Belege-Spalte im Warte-Zustand.
  const deepAktiv = Boolean(letzter?.recherche && letzter.deepStatus === "laeuft");
  const showIntro = turns.length === 0;

  // „Meine Gespräche" (5a/I-04 + 6a): Einwilligung (null = nie gefragt),
  // laufendes Gespräch und die gespeicherte Liste.
  const [einstellung, setEinstellung] = useState<number | null | undefined>(undefined);
  const [gespraechId, setGespraechId] = useState<number | null>(null);
  const [gespraeche, setGespraeche] = useState<GespraechEintrag[]>([]);
  const [zeigeListe, setZeigeListe] = useState(false);
  const ladeGespraeche = () =>
    fetch(apiUrl("/council/gespraeche"), { credentials: "include", headers: authHeaders() })
      .then((r) => (r.ok ? r.json() : null))
      .then((b) => {
        if (!b) return;
        setEinstellung(b.einstellung);
        setGespraeche(b.gespraeche ?? []);
      })
      .catch(() => {});
  useEffect(() => { void ladeGespraeche(); }, []);
  const einwilligen = async (an: boolean) => {
    setEinstellung(an ? 1 : 0);
    try {
      const r = await fetch(apiUrl("/council/gespraeche/einstellung"), {
        method: "POST", credentials: "include",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({ an }),
      });
      if (!r.ok) throw new Error();
    } catch {
      // Nicht so tun, als wäre die Wahl angekommen — der Server prüft beim
      // Speichern autoritativ, die Sitzung liefe sonst still ungespeichert
      // trotz sichtbarem „Ja" (Befund F12).
      setEinstellung(null);
      toast.error("Deine Wahl konnte nicht gespeichert werden — bitte nochmal.");
    }
  };
  const gespraechLaden = async (id: number) => {
    // Ein laufender Stream würde seine Tokens sonst an das GELADENE Gespräch
    // hängen und dessen id beim done überschreiben (Befund F1).
    abortRef.current?.abort();
    abortRef.current = null;
    setLoading(false);
    setStep(null);
    try {
      const r = await fetch(apiUrl(`/council/gespraeche/${id}`), { credentials: "include", headers: authHeaders() });
      if (!r.ok) throw new Error();
      const g = await r.json();
      // Presse/Debatten/Anlagen/Planungen stecken seit dem 10.08. mit im
      // Snapshot — ohne sie verlor ein geladenes Gespräch den Stadt-Block
      // und (übers Debatten-Gate) den Parteien-Baustein (Tims Befund).
      // Ältere Turns ohne diese Felder bleiben schlicht ohne.
      type DbTurn = { frage: string; antwort: string; quellen: {
        sources?: QaSource[]; cited?: number[]; presse?: PresseHinweis[];
        debatten?: DebattenHinweis[]; anlagen?: AnlagenHinweis[];
        planungen?: Planung[]; recherche?: boolean;
        gelesen?: number; zeitraum?: string } | null };
      setTurns((g.turns as DbTurn[]).map((t) => ({
        key: naechsterKey(),
        frage: t.frage, antwort: t.antwort, qtype: null, mode: null,
        sources: t.quellen?.sources ?? [],
        presse: t.quellen?.presse ?? [],
        debatten: t.quellen?.debatten ?? [],
        anlagen: t.quellen?.anlagen ?? [],
        planungen: t.quellen?.planungen ?? [],
        cited: t.quellen?.cited ?? [],
        followups: [], kontext: t.frage,
        ...(t.quellen?.recherche ? {
          recherche: true, deepStatus: "fertig" as const,
          gelesen: t.quellen?.gelesen, zeitraum: t.quellen?.zeitraum,
        } : {}),
      })));
      setGespraechId(id);
      setZeigeListe(false);
      setSheetOffen(false);
      requestAnimationFrame(() => endRef.current?.scrollIntoView({ block: "end" }));
    } catch {
      toast.error("Gespräch konnte nicht geladen werden.");
    }
  };
  const gespraechLoeschen = async (id: number) => {
    setGespraeche((gs) => gs.filter((g) => g.id !== id));
    if (gespraechId === id) setGespraechId(null);
    try {
      await fetch(apiUrl(`/council/gespraeche/${id}`), { method: "DELETE", credentials: "include", headers: authHeaders() });
    } catch { /* Liste wird beim nächsten Öffnen neu geladen */ }
  };
  const gespraechUmbenennen = async (id: number, titel: string) => {
    const sauber = titel.replace(/\s+/g, " ").trim().slice(0, 120);
    if (!sauber) return;
    setGespraeche((gs) => gs.map((g) => (g.id === id ? { ...g, titel: sauber } : g)));
    try {
      const r = await fetch(apiUrl(`/council/gespraeche/${id}`), {
        method: "PATCH", credentials: "include",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({ titel: sauber }),
      });
      if (!r.ok) throw new Error();
    } catch {
      toast.error("Umbenennen hat nicht geklappt.");
      void ladeGespraeche();
    }
  };
  // 9a①/②: das mobile Gespräche-Sheet (Desktop behält das Dropdown aus 5a).
  const [sheetOffen, setSheetOffen] = useState(false);

  // Fixed-Composer (Tims TestFlight-Feedback 11.08.): Der Spacer im Fluss
  // trägt die live gemessene Composer-Höhe — sie ändert sich mit Chips,
  // Kontext-Zeile und Karten, eine feste Zahl liefe sofort auseinander.
  const composerRef = useRef<HTMLDivElement>(null);
  const [composerHoehe, setComposerHoehe] = useState(110);
  useEffect(() => {
    const el = composerRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setComposerHoehe(el.offsetHeight));
    ro.observe(el);
    setComposerHoehe(el.offsetHeight);
    return () => ro.disconnect();
  }, []);

  // Brücke zum History-Knopf im Seitenkopf (Tims TestFlight-Feedback 11.08.):
  // Status hoch (gibt es Gespräche zu zeigen?), Taps herunter. Fenster-Events
  // statt State-Hochzug, weil PageHeader und Gespräch in getrennten Ästen
  // leben und der Knopf nur auf dem Fragen-Screen existiert.
  useEffect(() => {
    window.dispatchEvent(new CustomEvent("rl:gespraeche-status", {
      detail: { sichtbar: einstellung === 1 && (turns.length > 0 || gespraeche.length > 0) },
    }));
  }, [einstellung, turns.length, gespraeche.length]);
  useEffect(() => {
    const auf = () => { setSheetOffen(true); void ladeGespraeche(); };
    window.addEventListener("rl:gespraeche-oeffnen", auf);
    return () => window.removeEventListener("rl:gespraeche-oeffnen", auf);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 5a/I-07: frische Beispiel-Anlässe aus den jüngsten Sitzungen — die
  // Klassiker bleiben, aber ein bis zwei Vorschläge zeigen, dass hier
  // aktuelles Material liegt. Fehlt der Endpoint, bleiben die Klassiker.
  const [frische, setFrische] = useState<string[]>([]);
  useEffect(() => {
    if (!showIntro) return;
    fetch(apiUrl("/council/qa-beispiele"), { credentials: "include", headers: authHeaders() })
      .then((r) => (r.ok ? r.json() : null))
      .then((b) => {
        const rows = (b?.sitzungen ?? []) as { committee: string; session_date: string; top_titel?: string | null }[];
        if (rows.length === 0) return;
        // Zwei frische Anlässe, aber nicht zweimal dieselbe Datums-Formel:
        // erst die jüngste Sitzung, dann KONKRET ihr wichtigster Beschluss
        // (Tims Wunsch nach dynamischeren Vorschlägen).
        const vorschlaege = [
          `Was hat ${derAusschuss(rows[0].committee)} am ${fmtDatum(rows[0].session_date)} beschlossen?`,
        ];
        const kurz = kurzerGegenstand(rows[0].top_titel ?? "");
        if (kurz) vorschlaege.push(`Was wurde zu „${kurz}" entschieden?`);
        setFrische(vorschlaege.slice(0, 2));
      })
      .catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showIntro]);
  // Die restlichen Plätze füllt der bewährte Pool — bei jedem Besuch mit
  // anderen Fragen (Tims Wunsch), aber nur solchen, die messbar tragen.
  // Erstes Rendern zeigt die Klassiker; gewürfelt wird erst nach dem Mount,
  // sonst weicht das Markup des statischen Exports von der Hydration ab.
  const [gewuerfelt, setGewuerfelt] = useState<string[]>(() => EXAMPLES.slice(0, 4));
  useEffect(() => {
    if (!showIntro) return;
    setGewuerfelt(waehleBeispiele(frische, 4 - frische.length));
  }, [showIntro, frische]);
  const beispiele = [...frische, ...gewuerfelt].slice(0, 4);
  // Weiterfragen leben im Composer (Design 2②) — nur vom jüngsten Turn.
  const composerFollowups = !loading && letzter && !letzter.fehler ? letzter.followups.slice(0, 3) : [];

  return (
    <div className="mx-auto mt-3 lg:grid lg:max-w-[1220px] lg:grid-cols-[minmax(0,1fr)_320px] lg:items-start lg:gap-6">
      {/* Chat-Spalte. Die mobile min-height-Krücke (Design 2①: „Composer
          klebt auch im Empty State unten") ist seit dem FIXED-Composer
          obsolet — und machte die Seite höher als den Viewport, sodass das
          letzte Beispiel hinter dem Composer verschwand (Tims UI-Befund
          12.08.). Ohne sie ist der Empty State kompakt und komplett lesbar.
          Ab lg wird sie zur GESPRÄCHS-BÜHNE (Design 4a): ein getöntes Panel,
          in der Höhe an den Viewport gebunden — der Verlauf scrollt IM Panel,
          der Composer klebt an der Panel-Unterkante statt „irgendwo am
          Seitenende" zu hängen (Tims Whitespace-Befund). */}
      <div className={cn("flex flex-col",
        "lg:relative lg:h-[calc(100dvh-135px)] lg:min-h-0 lg:overflow-hidden lg:rounded-2xl lg:border lg:border-border lg:bg-primary/[0.04] dark:lg:bg-primary/[0.07]",
      )}>
        {/* Desktop (5a): „Gespräche"/„Neues Gespräch" im Bühnen-Kopf. Mobil
            ersetzt die EINE Gesprächs-Zeile (9a①) die zwei Streu-Icons. */}
        {(modeToggle || turns.length > 0 || gespraeche.length > 0) && (
          <div className="mb-1 hidden items-center justify-between gap-2 md:flex lg:mb-0 lg:px-4 lg:pb-2 lg:pt-3">
            {modeToggle ? <div>{modeToggle}</div> : <span />}
            <div className="relative flex shrink-0 items-center gap-1.5 print:hidden">
              {/* 5a/I-04: gespeicherte Gespräche — Liste lädt beim Öffnen frisch. */}
              {einstellung === 1 && (gespraeche.length > 0 || gespraechId != null) && (
                <button
                  type="button"
                  onClick={() => { setZeigeListe((v) => !v); if (!zeigeListe) void ladeGespraeche(); }}
                  aria-expanded={zeigeListe}
                  className="inline-flex items-center gap-1.5 rounded-[10px] border border-border bg-card px-2.5 py-1.5 text-xs font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                >
                  <History className="h-3.5 w-3.5" aria-hidden />
                  <span className="hidden sm:inline">Gespräche</span>
                </button>
              )}
              {turns.length > 0 && (
                <button
                  type="button"
                  onClick={neuesGespraech}
                  className="inline-flex items-center gap-1.5 rounded-[10px] border border-border bg-card px-2.5 py-1.5 text-xs font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                >
                  <MessageSquarePlus className="h-3.5 w-3.5" aria-hidden />
                  <span className="hidden sm:inline">Neues Gespräch</span>
                </button>
              )}
              {zeigeListe && (
                <div className="absolute right-0 top-full z-30 mt-1.5 flex max-h-[min(60vh,26rem)] w-72 flex-col rounded-xl border border-border bg-card p-1.5 shadow-lg">
                  <p className="shrink-0 px-2 pb-1 pt-1.5 font-mono text-[10px] uppercase tracking-[0.12em] text-muted-foreground">
                    Meine Gespräche · in deinem Konto
                  </p>
                  {/* Bei vielen Gesprächen wuchs die Liste über den
                      Bildschirmrand, ohne scrollbar zu sein (Tims Befund) —
                      jetzt scrollt sie im gedeckelten Panel. */}
                  <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain">
                  {gespraeche.map((g) => (
                    <div key={g.id} className="group flex items-center gap-1 rounded-lg px-2 py-1.5 transition-colors hover:bg-muted">
                      <button type="button" onClick={() => void gespraechLaden(g.id)}
                        className="min-w-0 flex-1 text-left">
                        <span className="block truncate text-[12.5px] font-medium text-foreground">{g.titel}</span>
                        <span className="block text-[10.5px] text-muted-foreground">
                          {fmtUtcMitZeit(g.updated)} · {g.n_turns} {g.n_turns === 1 ? "Frage" : "Fragen"}
                        </span>
                      </button>
                      <button type="button" onClick={() => void gespraechLoeschen(g.id)}
                        aria-label={`Gespräch „${g.titel}" löschen`} title="Löschen"
                        className="shrink-0 rounded-md p-1 text-muted-foreground opacity-60 transition-opacity hover:text-signal sm:opacity-0 sm:group-hover:opacity-100">
                        <Trash2 className="h-3.5 w-3.5" aria-hidden />
                      </button>
                    </div>
                  ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* 9a① → oben rechts (Tims TestFlight-Feedback 11.08.): Die mobile
            Gesprächs-Zeile stand als breiter Pill mitten im Screen und
            kostete Platz. Der Griff sitzt jetzt als History-Knopf im
            Seitenkopf (view.tsx) — verbunden über zwei Fenster-Events, weil
            Kopf und Gesprächs-State in getrennten Ästen leben: Wir melden
            hoch, OB es etwas zu zeigen gibt, der Kopf meldet Taps herunter. */}
        {sheetOffen && (
          <GespraecheSheet
            gespraeche={gespraeche}
            aktivId={gespraechId}
            onNeu={() => { setSheetOffen(false); neuesGespraech(); }}
            onLaden={(id) => void gespraechLaden(id)}
            onLoeschen={(id) => void gespraechLoeschen(id)}
            onUmbenennen={(id, titel) => void gespraechUmbenennen(id, titel)}
            onClose={() => setSheetOffen(false)}
          />
        )}

        {/* Ab lg scrollt der Verlauf IM Panel (Design 4a) — mobil weiter am
            Window, der Wrapper ist dort nur ein durchreichender flex-Teil. */}
        <div className="flex flex-1 flex-col lg:min-h-0 lg:overflow-y-auto lg:px-4">
        {/* Empty State — bodenständig: Beispiele direkt über dem Composer. */}
        {showIntro && (
          <div className="flex flex-1 flex-col items-center justify-end pb-5 text-center">
            {/* 6a①: Erstnutzungs-Frage — einmalig, solange nie beantwortet. */}
            {einstellung === null && (
              <div className="mb-5 w-full max-w-md rounded-2xl border border-primary/25 bg-primary/[0.04] p-4 text-left">
                <div className="flex items-start gap-3">
                  <Mascot pose="wave" className="h-10 w-10 shrink-0" />
                  <div className="min-w-0">
                    <p className="text-sm font-semibold text-foreground">Soll ich mir deine Gespräche merken?</p>
                    <p className="mt-1 text-[12.5px] leading-relaxed text-muted-foreground">
                      Wenn du magst, speichere ich deine Verläufe in deinem Konto — du findest
                      sie dann auf allen Geräten oben unter „Gespräche". Wenn nicht, lebt ein
                      Gespräch nur, bis du es schließt.
                    </p>
                    <div className="mt-2.5 flex gap-2">
                      <button type="button" onClick={() => void einwilligen(true)}
                        className="rounded-full bg-primary px-3.5 py-1.5 text-xs font-semibold text-primary-foreground transition-colors hover:bg-primary/90">
                        Ja, merken
                      </button>
                      <button type="button" onClick={() => void einwilligen(false)}
                        className="rounded-full border border-border px-3.5 py-1.5 text-xs font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground">
                        Nein, nicht merken
                      </button>
                    </div>
                    <p className="mt-2 text-[10.5px] text-muted-foreground/70">
                      Deine Wahl gilt für dein Konto und lässt sich jederzeit in den Einstellungen ändern.
                    </p>
                  </div>
                </div>
              </div>
            )}
            {/* Tims UI-Befund 12.08.: Der Empty State soll ohne Scrollen ganz
                lesbar sein — kürzerer Untertitel (die Fußnoten sieht man an
                der ersten Antwort selbst), weniger Luft vor „Zum Beispiel",
                und mobil nur drei Beispiele (das vierte ab lg). */}
            <Mascot pose="wave" bob className="h-20 w-20" />
            <h2 className="mt-3 text-xl font-bold tracking-tight">Frag den Rat</h2>
            <p className="mt-1 max-w-md text-sm text-muted-foreground">
              Die Antwort entsteht aus den echten Ratsbeschlüssen.
            </p>
            <p className="mt-3 font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground/70">
              Zum Beispiel
            </p>
            <div className="mt-1.5 flex w-full max-w-md flex-col gap-1.5">
              {beispiele.map((ex, i) => (
                <button key={ex} type="button" onClick={() => frageStellen(ex)}
                  className={cn(
                    "items-center gap-2.5 rounded-[11px] border border-border bg-card px-3 py-2.5 text-left text-[13.5px] transition-[background-color,transform] duration-150 ease-out-strong hover:bg-muted active:scale-[0.99]",
                    i >= 3 ? "hidden lg:flex" : "flex")}>
                  <Sparkles className="h-3.5 w-3.5 shrink-0 text-primary" aria-hidden />
                  <span className="min-w-0 flex-1">{ex}</span>
                  {i < frische.length && (
                    <span className="shrink-0 rounded-full bg-signal/10 px-1.5 py-0.5 text-[10px] font-medium text-signal">Neu</span>
                  )}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Gesprächsverlauf. */}
        {!showIntro && (
          <div className="flex flex-1 flex-col gap-6 sm:gap-7">
            {turns.map((t, ti) => (
              <TurnView
                key={t.key}
                turn={t}
                turnIdx={ti}
                istLetzter={ti === turns.length - 1}
                loading={loading && ti === turns.length - 1}
                step={loading && ti === turns.length - 1 ? step : null}
                word={word}
                flashId={flashId}
                onJump={(id) => { jumpZuQuelle(ti, id, ti === turns.length - 1); flash(id); }}
                onRetry={() => { setTurns((ts) => ts.slice(0, -1)); void ask(t.frage); }}
                onEigeneFrage={() => inputRef.current?.focus()}
                onDazuFragen={(titel) => frageStellen(`Erzähl mir mehr zu „${titel}".`)}
                onFrageStellen={(text) => frageStellen(text)}
                onDeepStop={() => void deepStop(t)}
                onDeepTeilbericht={() => void deepTeilbericht(t)}
                onDeepVerwerfen={() => deepVerwerfen(t)}
                onDeepFortsetzen={() => { deepVerwerfen(t); void askDeep(t.frage); }}
                onDeepSchnell={() => { deepVerwerfen(t); void ask(t.frage); }}
                onGruendlich={() => void askDeep(t.kontext || t.frage)}
              />
            ))}
          </div>
        )}
        <div ref={endRef} />
        </div>

        {/* „Nach unten"-Anker (RG-07); in der Bühne am Panel verankert. */}
        {showAnchor && (
          <button
            type="button"
            aria-label="Zum Gesprächsende springen"
            onClick={() => endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" })}
            className="fixed bottom-40 right-4 z-20 flex h-9 w-9 items-center justify-center rounded-full border border-border bg-card shadow-md transition-transform hover:scale-105 print:hidden sm:right-8 lg:absolute lg:bottom-32 lg:right-5"
          >
            <ArrowDown className="h-4 w-4 text-muted-foreground" aria-hidden />
          </button>
        )}

        {/* Composer: mobil sticky am Viewport-Boden, in der Bühne (lg) fest an
            der Panel-Unterkante — Weiterfragen-Chips direkt darüber (2①②/4a). */}
        {/* IMMER an der Tab-Bar (Tims TestFlight-Feedback 11.08., dritter
            Anlauf): sticky kann ein Element nur nach OBEN pinnen — ist die
            Seite kürzer als der Viewport (Empty State), bleibt es an seiner
            Fluss-Position und über der Tab-Bar klafft die Lücke aus
            Container-Padding und Flex-Rest. Deshalb der klassische
            Chat-Aufbau: mobil FIXED direkt auf der Tab-Bar-Oberkante
            (4rem + Safe-Area = Höhe der Leiste), und der Spacer darunter
            hält im Fluss genau die gemessene Composer-Höhe frei, damit das
            Gesprächsende nie darunter verschwindet. Ab lg wie gehabt statisch
            in der Bühne. */}
        <div aria-hidden style={{ height: composerHoehe }} className="md:hidden" />
        <div ref={composerRef}
          className="fixed inset-x-0 bottom-[calc(env(safe-area-inset-bottom)+4rem)] z-10 bg-gradient-to-t from-background via-background to-transparent px-4 pb-1.5 pt-4 print:hidden md:static md:inset-x-auto md:bottom-auto md:bg-none md:px-0 md:pb-0 md:pt-2 lg:px-4 lg:pb-4">
          {/* 9a-Regel: Ohne aktives Speichern gibt es keine Gesprächs-Zeile —
              „Neues Gespräch" ist dann ein schlichter Text-Link überm Composer. */}
          {turns.length > 0 && einstellung !== 1 && (
            <div className="mb-1.5 flex justify-end md:hidden">
              <button type="button" onClick={neuesGespraech}
                className="inline-flex items-center gap-1 text-[12px] font-medium text-muted-foreground transition-colors active:text-foreground">
                <MessageSquarePlus className="h-3.5 w-3.5" aria-hidden /> Neues Gespräch
              </button>
            </div>
          )}
          {/* 5a/I-06: Der Kontext-Chip macht sichtbar, worauf sich Anschluss-
              fragen beziehen — ✕ beginnt ein frisches Gespräch. */}
          {letzter?.kontext && !letzter.fehler && (
            <div className="mb-1.5 flex">
              <span className="inline-flex min-w-0 items-center gap-1.5 rounded-full bg-muted px-2.5 py-1 text-[11px] text-muted-foreground">
                <span className="shrink-0 font-medium">Kontext:</span>
                <span className="min-w-0 truncate">{letzter.kontext}</span>
                <button type="button" onClick={neuesGespraech} aria-label="Kontext zurücksetzen — neues Gespräch"
                  title="Kontext zurücksetzen" className="shrink-0 rounded-full p-0.5 transition-colors hover:bg-background hover:text-foreground">
                  <X className="h-3 w-3" aria-hidden />
                </button>
              </span>
            </div>
          )}
          {!deepAktiv && (composerFollowups.length > 0 || (!loading && letzter && !letzter.fehler && letzter.antwort)) && (
            <ChipZeile>
              {composerFollowups.map((s) => (
                <button key={s} type="button" onClick={() => frageStellen(s)}
                  className="inline-flex shrink-0 items-center gap-1.5 rounded-full border border-primary/30 bg-primary/[0.05] px-3 py-1.5 text-[12.5px] text-foreground transition-[background-color,transform] duration-150 ease-out-strong hover:bg-primary/[0.1] active:scale-[0.98]">
                  <span className="max-w-[260px] truncate">{s}</span>
                  <ArrowRight className="h-3 w-3 shrink-0 text-primary" aria-hidden />
                </button>
              ))}
              {/* 5a/I-09: feste Register — dieselbe Antwort, andere Flughöhe. */}
              {!loading && letzter && !letzter.fehler && letzter.antwort && (
                <>
                  <button type="button" onClick={() => void ask("Erkläre das bitte einfacher, ohne Fachbegriffe.")}
                    className="inline-flex shrink-0 items-center gap-1.5 rounded-full border border-border bg-card px-3 py-1.5 text-[12.5px] text-muted-foreground transition-colors hover:bg-muted hover:text-foreground">
                    Einfacher erklären
                  </button>
                  <button type="button" onClick={() => void ask("Bitte ausführlicher — was gehört noch zum Bild?")}
                    className="inline-flex shrink-0 items-center gap-1.5 rounded-full border border-border bg-card px-3 py-1.5 text-[12.5px] text-muted-foreground transition-colors hover:bg-muted hover:text-foreground">
                    Ausführlicher
                  </button>
                </>
              )}
            </ChipZeile>
          )}
          {/* RG-10: Kontingent-Karte (8c⑤) und Tages-Erstinfo (8a①). */}
          {deepLimit && (
            <RechercheLimitKarte onSchnelleFrage={() => { setDeepLimit(false); void ask(q); }} />
          )}
          {rechercheModus && deepHinweis && !deepLimit && <RechercheHinweisKarte frei={deepFrei} />}
          {letzterFehler === "limit" ? (
            <div className="rounded-2xl border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-sm">
              <p className="font-medium text-foreground">Kurze Verschnaufpause</p>
              <p className="mt-0.5 text-[12.5px] text-muted-foreground">
                Mehr als 10 Fragen in 10 Minuten — in ein paar Minuten geht es weiter.
                Deine bisherigen Antworten bleiben stehen, die Frage steht wieder im Eingabefeld.
              </p>
              {/* Ausweg statt Sackgasse (Befund F8): Der Neuversuch ersetzt den
                  Limit-Turn; schlägt er erneut an, erscheint das Banner wieder. */}
              <button type="button"
                onClick={() => { const t = letzter; setTurns((ts) => ts.slice(0, -1)); void ask(q || t?.frage || ""); }}
                className="mt-2 inline-flex items-center gap-1.5 rounded-full border border-amber-500/50 px-3 py-1.5 text-xs font-medium text-foreground transition-colors hover:bg-amber-500/15">
                <RotateCcw className="h-3.5 w-3.5" aria-hidden /> Nochmal versuchen
              </button>
            </div>
          ) : (
            <form onSubmit={(e) => { e.preventDefault(); void (rechercheModus ? askDeep(q) : ask(q)); }} className="flex flex-col gap-1.5">
              {/* RG-10-Pill ÜBER dem Eingabefeld (Tims TestFlight-Feedback
                  11.08., zweite Runde): unter dem Feld stand sie im Weg, als
                  Kolben-Knopf in der Zeile nahm sie der Textbox Breite. */}
              <div className="flex items-center gap-2">
                <RechercheToggle aktiv={rechercheModus} frei={deepFrei} onToggle={toggleRecherche} />
                {rechercheModus && !deepHinweis && (
                  <span className="text-[10.5px] text-muted-foreground/70">
                    1–2 Min{deepFrei !== null ? ` · noch ${deepFrei} heute` : ""}
                  </span>
                )}
              </div>
              <div className="flex gap-2">
                <div className="relative flex-1">
                  <Sparkles className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                  <Input ref={inputRef} data-search enterKeyHint="send"
                    className="h-12 rounded-2xl pl-9"
                    placeholder={rechercheModus ? "Gründlich recherchieren …"
                      : turns.length > 0 ? "Anschlussfrage stellen …" : "Frag den Rat …"}
                    value={q} onChange={(e) => setQ(e.target.value)} />
                </div>
                {loading ? (
                  <Button type="button" variant="secondary" className="h-12 rounded-2xl" onClick={stopAsking} aria-label="Antwort abbrechen">
                    <Square className="fill-current" /> Stopp
                  </Button>
                ) : (
                  <Button type="submit" className="h-12 w-12 rounded-2xl p-0" disabled={q.trim().length < 4} aria-label="Fragen">
                    <Send />
                  </Button>
                )}
              </div>
            </form>
          )}
          {/* Der KI-Datenschutz-Hinweis wohnt jetzt in den Einstellungen
              (Gespräche-Karte) — Tims TestFlight-Feedback 11.08. */}
        </div>
      </div>

      {/* Belege-Spalte (Desktop, Design 2⑤/4a): eigene Karte neben der Bühne,
          gleiche Höhe, eigener Scroll — nie ein leeres Loch: Vor der ersten
          Frage erklärt sie sich, während der Suche zeigt sie ein Skelett
          (Tims Feedback), danach Quellen, Presse und Aktionen. */}
      <aside className="hidden print:hidden lg:flex lg:h-[calc(100dvh-135px)] lg:flex-col lg:overflow-hidden lg:rounded-2xl lg:border lg:border-border lg:bg-card">
        <div className="flex-1 overflow-y-auto p-4">
          {letzter && letzter.antwort && !letzter.fehler ? (
            <BelegeSpalte turn={letzter} flashId={flashId}
              onDazuFragen={(titel) => frageStellen(`Erzähl mir mehr zu „${titel}".`)}
              onFlash={flash} />
          ) : loading || deepAktiv ? (
            <div aria-hidden className="space-y-3 pt-1">
              <div className="h-3 w-24 animate-pulse rounded bg-muted" />
              {[0, 1, 2, 3, 4].map((i) => (
                <div key={i} className="h-8 animate-pulse rounded-full bg-muted"
                  style={{ animationDelay: `${i * 120}ms` }} />
              ))}
              <div className="h-3 w-32 animate-pulse rounded bg-muted" />
            </div>
          ) : (
            <div className="flex h-full flex-col items-center justify-center gap-2 text-center">
              <Sparkles className="h-5 w-5 text-muted-foreground/50" aria-hidden />
              <p className="max-w-[220px] text-xs leading-relaxed text-muted-foreground">
                Quellen und Belege erscheinen hier, sobald du eine Frage stellst —
                mit Fußnote zu jedem zitierten Beschluss.
              </p>
            </div>
          )}
        </div>
      </aside>
    </div>
  );
}

/* ------------------------------------------------------------------------- */

function TurnView({ turn, turnIdx, istLetzter, loading, step, word, flashId, onJump, onRetry, onEigeneFrage, onDazuFragen, onFrageStellen, onDeepStop, onDeepTeilbericht, onDeepVerwerfen, onDeepFortsetzen, onDeepSchnell, onGruendlich }: {
  turn: Turn; turnIdx: number; istLetzter: boolean; loading: boolean;
  step: Step | null; word: string; flashId: number | null;
  onJump: (id: number) => void; onRetry: () => void; onEigeneFrage: () => void;
  onDazuFragen?: (titel: string) => void;
  onFrageStellen?: (text: string) => void;
  onDeepStop?: () => void; onDeepTeilbericht?: () => void; onDeepVerwerfen?: () => void;
  onDeepFortsetzen?: () => void; onDeepSchnell?: () => void;
  /** Dieselbe Frage gründlich nachrecherchieren — der Ausweg bei dünner Beleglage. */
  onGruendlich?: () => void;
}) {
  const [showAll, setShowAll] = useState(false);
  // Ältere Turns beruhigen (Design 2⑤): Belege hinter der Kompaktzeile.
  const [aufgeklappt, setAufgeklappt] = useState(false);
  // 5a/I-01: welcher Zitat-Chip gerade sein Peek zeigt.
  const [peekId, setPeekId] = useState<number | null>(null);
  const idToNum = useIdToNum(turn);
  const anlBuchstaben = useAnlagenBuchstaben(turn);
  // 5a/I-10: Pins der zitierten Quellen — gleiche Koordinate nur einmal.
  const ortsPins = useMemo<QaOrtPin[]>(() => {
    const gesehen = new Set<string>();
    const pins: QaOrtPin[] = [];
    for (const [id, nummer] of idToNum) {
      const s = turn.sources.find((x) => x.id === id);
      if (!s || s.lat == null || s.lon == null) continue;
      const key = `${s.lat.toFixed(4)},${s.lon.toFixed(4)}`;
      if (gesehen.has(key)) continue;
      gesehen.add(key);
      pins.push({ id, nummer, name: s.ort_name ?? s.title ?? "", lat: s.lat, lon: s.lon });
    }
    return pins;
  }, [turn.sources, idToNum]);
  const zitierte = useMemo(() => zitierteVon(turn, idToNum), [turn, idToNum]);

  const hatAntwort = turn.antwort.length > 0;
  // RG-10: Recherche-Turns haben einen eigenen Lebenszyklus neben `loading`
  // (das nur den /ask-Stream spiegelt) — der Job läuft server-seitig weiter.
  const deepLaeuft = Boolean(turn.recherche && turn.deepStatus === "laeuft");
  const deepFertig = Boolean(turn.recherche && turn.deepStatus === "fertig");
  const deepGescheitert = Boolean(turn.recherche && turn.deepStatus === "fehler");
  // Auch der Fehler-Torso zählt als „nicht abgeschlossen": Meta-Zeile und
  // Bausteine würden ihn sonst wie einen fertigen Bericht aussehen lassen.
  const beschaeftigt = loading || deepLaeuft || deepGescheitert;
  const abschnitte = useMemo(
    () => (turn.recherche ? berichtAbschnitte(turn.antwort) : []),
    [turn.recherche, turn.antwort]);
  const nichtsGefunden = !beschaeftigt && hatAntwort && turn.sources.length === 0 && !turn.fehler;
  // Mobil zeigt der jüngste Turn seine Belege inline (die Desktop-Spalte
  // übernimmt ab lg); ältere Turns nur nach Klick auf die Kompaktzeile.
  const belegeInline = istLetzter ? "lg:hidden" : aufgeklappt ? "" : "hidden";

  return (
    <div className="flex flex-col gap-3">
      {/* Nutzer-Turn: rechtsbündig, stille Bubble (RG-01). */}
      <div className="flex flex-col items-end gap-1">
        <div className="max-w-[78%] rounded-[18px] rounded-br-[6px] border border-primary/[0.18] bg-primary/[0.07] px-3.5 py-2.5 text-[14.5px] leading-[1.55] sm:max-w-[60%]">
          {turn.frage}
        </div>
        {/* RG-10: Modus-Zeile unter der Bubble — nach Abschluss mit Umfang. */}
        {turn.recherche && (
          <span className="inline-flex items-center gap-1.5 text-[10.5px] text-muted-foreground/80">
            <FlaskConical className="h-3 w-3" aria-hidden />
            Gründliche Recherche{deepFertig && turn.gelesen ? ` · ${turn.gelesen} Dokumente gelesen` : ""}
          </span>
        )}
      </div>

      {/* RG-10 (8a②): Fortschritts-Karte, solange der Job läuft. */}
      {deepLaeuft && !hatAntwort && (
        <RechercheFortschritt
          phase={turn.deepPhase ?? "zerlegen"}
          facetten={turn.deepFacetten ?? []}
          facettenFertig={turn.deepFacettenFertig ?? 0}
          dokumente={turn.deepDokumente ?? null}
          onStop={() => onDeepStop?.()}
        />
      )}
      {/* RG-10 (8c⑥/⑦): Abbruch mit Teilbericht-Angebot bzw. Fehler. */}
      {turn.recherche && turn.deepStatus === "gestoppt" && !hatAntwort && (
        <RechercheGestoppt
          fertig={turn.deepFacettenFertig ?? 0}
          gesamt={turn.deepFacetten?.length ?? 0}
          teilberichtMoeglich={Boolean(turn.deepTeilberichtMoeglich)}
          onTeilbericht={() => onDeepTeilbericht?.()}
          onVerwerfen={() => onDeepVerwerfen?.()}
        />
      )}
      {/* Auch MIT Text-Torso zeigen: ein gerissener Berichts-Stream darf
          nicht wie ein fertiger Bericht aussehen (Tims Ur-Befund bei /ask). */}
      {turn.recherche && turn.deepStatus === "fehler" && (
        <RechercheFehlerKarte
          onFortsetzen={() => onDeepFortsetzen?.()}
          onSchnelleFrage={() => onDeepSchnell?.()}
        />
      )}

      {/* Fehler-Turn (RG ⑧). */}
      {turn.fehler === "netz" && (
        <div className="flex items-start gap-3 rounded-xl border border-signal/30 bg-signal/5 p-4">
          <Mascot pose="confused" decorative className="h-12 w-12 shrink-0" />
          <div className="min-w-0">
            <p className="text-sm font-medium text-foreground">Das hat nicht geklappt.</p>
            <p className="mt-0.5 text-[12.5px] text-muted-foreground">
              Die Verbindung ist abgebrochen. Deine Frage ist nicht verloren —
              sie steht wieder im Eingabefeld.
            </p>
            <div className="mt-2.5 flex flex-wrap gap-2">
              <button type="button" onClick={onRetry}
                className="inline-flex items-center gap-1.5 rounded-full border border-primary/30 bg-primary/5 px-3 py-1.5 text-xs font-medium text-primary transition-colors hover:bg-primary/10">
                <RotateCcw className="h-3 w-3" aria-hidden /> Nochmal versuchen
              </button>
              <button type="button" onClick={onEigeneFrage}
                className="rounded-full border border-border px-3 py-1.5 text-xs font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground">
                Frage ändern
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Laufender Schritt, solange noch kein Text streamt (RG ②). */}
      {loading && !hatAntwort && !turn.fehler && (
        <div role="status" className="flex items-center gap-3 rounded-xl border-2 border-dashed border-border px-4 py-3 text-sm text-muted-foreground">
          <Mascot pose="search" bob className="h-12 w-12 shrink-0" />
          <div className="min-w-0">
            <span className="flex items-center gap-2 font-medium text-foreground">
              <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" />
              {step ? STEP_LABELS[step] : "Wird vorbereitet"}…
            </span>
            <span className="hidden text-xs text-muted-foreground/70 sm:inline">{word} …</span>
          </div>
        </div>
      )}

      {hatAntwort && (
        <div aria-busy={beschaeftigt} className="flex flex-col gap-3.5">
          {/* RG-10 (8b): Sprungmarken — Pflicht ab 4 Abschnitten. */}
          {turn.recherche && abschnitte.length >= 4 && (
            <Sprungmarken abschnitte={abschnitte} ankerPrefix={`qa-abschnitt-${turnIdx}`} />
          )}
          {/* Steckbrief ÜBER der Antwort: erst wissen, worum es geht. */}
          {(turn.steckbriefe?.length ?? 0) > 0 && (
            <SteckbriefBaustein steckbriefe={turn.steckbriefe ?? []} />
          )}
          {/* div statt p: die Antwort darf Listen (ul) enthalten. */}
          <div className="whitespace-pre-wrap text-[14.5px] leading-[1.7] text-foreground sm:leading-[1.75]">
            {/* 5a/I-01: Der Chip öffnet erst das Peek — nicht sofort wegspringen. */}
            <AntwortText text={turn.antwort} idToNum={idToNum} onJump={(id) => setPeekId(id)}
              anlBuchstaben={anlBuchstaben}
              onAnlage={(nr) => jumpZuAnlage(turnIdx, nr, istLetzter)}
              ankerPrefix={turn.recherche ? `qa-abschnitt-${turnIdx}` : undefined}
              berichtKoepfe={turn.recherche} />
            {((loading && step === "answer") || deepLaeuft) && <span className="ml-0.5 inline-block h-4 w-1.5 animate-pulse bg-primary align-text-bottom" />}
          </div>

          {peekId != null && (() => {
            const q = turn.sources.find((s) => s.id === peekId);
            const id = peekId;
            return q ? (
              <BelegPeek quelle={q} nummer={idToNum.get(id)}
                onClose={() => setPeekId(null)}
                onListe={() => {
                  // Bei älteren Turns liegt die Quellenliste hinter der
                  // Kompaktzeile — erst aufklappen, dann springen (Befund F9).
                  if (!istLetzter && !aufgeklappt) {
                    setAufgeklappt(true);
                    requestAnimationFrame(() => onJump(id));
                  } else {
                    onJump(id);
                  }
                }} />
            ) : null;
          })()}

          {turn.abgebrochen && (
            <p role="status" className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <CircleSlash className="h-3.5 w-3.5 shrink-0" aria-hidden />
              Abgebrochen — die Antwort blieb unvollständig. Du kannst direkt weiterfragen.
            </p>
          )}

          {/* Dünne Beleglage: ehrlicher Hinweis + der Ausweg, der hier hilft. */}
          {!beschaeftigt && turn.beleglage === "duenn" && !turn.recherche
            && !turn.fehler && !turn.abgebrochen && (
            <DuenneBeleglage onGruendlich={onGruendlich}
              mitSteckbrief={(turn.steckbriefe?.length ?? 0) > 0} />
          )}

          {/* RG-09: „Das sagen die Parteien" — direkt unter dem Antworttext,
              vor Zeitstrahl/Geld/Karte. Lädt nach der Antwort nach; bei dünner
              Lage verschwindet er ganz (kein Leerzustand). Gate ≥1 statt ≥2:
              Sachstands-Fragen ließen oft nur einen Debatten-Beleg durch,
              obwohl der Baustein mit seiner eigenen Fraktions-Suche liefert
              (Tims Befund 10.08.) — ob es reicht, entscheidet der Endpoint. */}
          {/* Bei Personen-Fragen zielt alles auf EINE Person — die Meinung
              aller Parteien daneben wäre Rauschen (Tims Befund 10.08.). */}
          {!beschaeftigt && turn.antwort && !turn.fehler && !turn.abgebrochen
            && turn.qtype !== "person" && (turn.debatten?.length ?? 0) >= 1 && (
            <ParteienBaustein frage={turn.kontext || turn.frage} onFrageStellen={onFrageStellen} />
          )}

          {!beschaeftigt && <Baustein turn={turn} idToNum={idToNum} onJump={(id) => setPeekId(id)} />}

          {/* RG-10 (8b): „Wie es weitergeht" — künftige Beratungsstationen
              aus dem Sitzungskalender, deterministisch, nie vom Modell. Seit
              Paket 1 auch unter der SCHNELLEN Antwort: Sachstands-Fragen sind
              der häufigste Fragetyp, und bisher blickte die Antwort nur zurück. */}
          {!beschaeftigt && (turn.planungen?.length ?? 0) > 0 && (
            <WieEsWeitergeht planungen={turn.planungen ?? []} />
          )}

          {/* 5a/I-10: Mini-Karte der zitierten Orte — deterministisch aus den
              geocodierten Entitäten der Quellen; Pin-Klick öffnet das Peek. */}
          {!beschaeftigt && ortsPins.length > 0 && (
            <div className="overflow-hidden rounded-xl border border-border print:hidden">
              <QaOrteKarte pins={ortsPins} onPin={(id) => setPeekId(id)} />
              <div className="flex items-center justify-between gap-2 border-t border-border bg-muted/30 px-3 py-1.5">
                <p className="text-[11px] text-muted-foreground">
                  {ortsPins.length === 1 ? "1 Ort" : `${ortsPins.length} Orte`} aus den zitierten Beschlüssen
                </p>
                <Link href="/council?tab=themen" className="shrink-0 text-[11px] font-medium text-primary hover:underline">
                  Zur Stadtkarte →
                </Link>
              </div>
            </div>
          )}

          {/* Kompaktzeile älterer Turns (Design 2⑤). */}
          {/* turn.debatten defensiv (?.) — Fast-Refresh/alte States kennen das Feld nicht. */}
          {!istLetzter && !aufgeklappt && (turn.sources.length > 0 || turn.presse.length > 0 || (turn.debatten?.length ?? 0) > 0) && (
            <button type="button" onClick={() => setAufgeklappt(true)}
              className="flex w-fit items-center gap-1.5 rounded-full border border-border px-3 py-1 font-mono text-[10px] uppercase tracking-[0.1em] text-muted-foreground transition-colors hover:bg-muted hover:text-foreground">
              <ChevronDown className="h-3 w-3" aria-hidden />
              Quellen ({turn.sources.length}){turn.presse.length > 0 ? ` · Presse (${turn.presse.length})` : ""}{(turn.debatten?.length ?? 0) > 0 ? ` · Debatten (${turn.debatten.length})` : ""}
            </button>
          )}

          <div className={cn("flex flex-col gap-3.5", belegeInline)}>
            {turn.sources.length > 0 && (
              <QuellenBlock turn={turn} turnIdx={turnIdx} idToNum={idToNum} zitierte={zitierte}
                showAll={showAll} setShowAll={setShowAll} flashId={flashId} ankerPrefix={`qa-source-${turnIdx}`}
                onDazuFragen={onDazuFragen} />
            )}
            {(turn.debatten?.length ?? 0) > 0 && <DebattenBlock debatten={turn.debatten} />}
            {(turn.anlagen?.length ?? 0) > 0 && (
              <AnlagenBlock anlagen={turn.anlagen ?? []} buchstaben={anlBuchstaben}
                ankerPrefix={`qa-anlage-${turnIdx}`} />
            )}
            {turn.presse.length > 0 && <PresseBlock presse={turn.presse} />}
          </div>

          {nichtsGefunden && (
            <div className="flex flex-wrap gap-2">
              <Link href={`/topics?neu=${encodeURIComponent(turn.frage)}`}
                className="rounded-full border border-primary/30 bg-primary/5 px-3 py-1.5 text-xs font-medium text-primary transition-colors hover:bg-primary/10">
                Als Thema anlegen — wir melden uns bei Neuem
              </Link>
              <button type="button" onClick={onEigeneFrage}
                className="rounded-full border border-border px-3 py-1.5 text-xs font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground">
                Frage umformulieren
              </button>
            </div>
          )}

          {/* Meta-Zeile: stille Icons + Disclaimer (Design 2③) — bei JEDEM
              Turn direkt unter der Antwort, auch dem jüngsten auf Desktop:
              die Bewertung nur unten rechts in der Belege-Spalte wurde nicht
              als zugehörig erkannt (Tims Befund 10.08.). */}
          {!beschaeftigt && (
            <div className="flex items-center gap-1 border-t border-border/60 pt-1.5 print:hidden">
              {/* Task 31: teilt einen Snapshot GENAU dieser Antwort — der alte
                  ?q=-Link ließ Empfänger eine andere Antwort würfeln. */}
              {turn.antwort && !turn.fehler && !turn.abgebrochen && (
                <TeilenKnopf turn={turn} zitierte={zitierte} />
              )}
              <PrintButton iconOnly />
              {turn.antwort && !turn.fehler && <VorlesenKnopf text={turn.antwort} />}
              {turn.antwort && !turn.fehler && <FeedbackDaumen turn={turn} />}
              <span role="status" className="min-w-0 flex-1 text-right text-[10.5px] leading-snug text-muted-foreground/70">
                {/* 5a/I-02 bzw. RG-10: ehrlich sagen, worauf die Antwort fußt. */}
                {turn.recherche && turn.gelesen
                  ? <>Bericht aus {turn.gelesen} gelesenen Dokumenten{turn.zeitraum ? ` (${turn.zeitraum})` : ""}{zitierte.length > 0 ? `, ${zitierte.length} zitiert` : ""} — kann unvollständig sein. Quellen prüfen.</>
                  : <>Automatische Antwort{zitierte.length > 0 ? `, ${stuetztAuf(zitierte)}` : " aus den gefundenen Beschlüssen"} — kann unvollständig sein. Quellen prüfen.</>}
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/* ---------------- Gespräche-Sheet (Design 9a②, mobil) ---------------- */

/** Eine Sheet-Zeile mit Wisch-nach-links-Aktionen (Umbenennen · Löschen).
 *  Der Wisch folgt dem Finger nur horizontal — vertikale Bewegung bleibt
 *  Scroll. Umbenennen verwandelt die Zeile in ein Eingabefeld. */
function SheetZeile({ g, aktiv, offen, aufklappen, onLaden, onLoeschen, onUmbenennen }: {
  g: GespraechEintrag; aktiv: boolean; offen: boolean;
  aufklappen: (id: number | null) => void;
  onLaden: () => void; onLoeschen: () => void; onUmbenennen: (titel: string) => void;
}) {
  const AKTIONEN_BREITE = 148;
  const start = useRef<{ x: number; y: number } | null>(null);
  const [dx, setDx] = useState(0);            // Finger-Delta während des Wischens
  const [zieht, setZieht] = useState(false);
  const [umbenennen, setUmbenennen] = useState(false);
  const [entwurf, setEntwurf] = useState(g.titel);
  const basis = offen ? -AKTIONEN_BREITE : 0;
  const verschiebung = zieht ? Math.max(-AKTIONEN_BREITE, Math.min(0, basis + dx)) : basis;

  const speichern = () => {
    setUmbenennen(false);
    aufklappen(null);
    if (entwurf.trim() && entwurf.trim() !== g.titel) onUmbenennen(entwurf);
  };

  if (umbenennen) {
    return (
      <form className="flex items-center gap-2 border-b border-border/60 px-2.5 py-2"
        onSubmit={(e) => { e.preventDefault(); speichern(); }}>
        <Input autoFocus value={entwurf} onChange={(e) => setEntwurf(e.target.value)}
          onBlur={speichern} maxLength={120} aria-label="Neuer Gesprächstitel"
          className="h-9 flex-1 text-[13.5px]" />
        <button type="submit" className="shrink-0 rounded-full bg-primary px-3 py-1.5 text-xs font-semibold text-primary-foreground">
          Sichern
        </button>
      </form>
    );
  }

  return (
    <div className="relative overflow-hidden border-b border-border/60 last:border-b-0">
      {/* Aktionsleiste hinter der Zeile — sichtbar nach dem Wisch. */}
      <div className="absolute inset-y-0 right-0 flex" aria-hidden={!offen}>
        <button type="button" tabIndex={offen ? 0 : -1}
          onClick={() => { setEntwurf(g.titel); setUmbenennen(true); }}
          className="flex w-[80px] flex-col items-center justify-center gap-0.5 bg-muted text-[10px] font-medium text-foreground">
          <Pencil className="h-4 w-4" aria-hidden /> Umbenennen
        </button>
        <button type="button" tabIndex={offen ? 0 : -1} onClick={onLoeschen}
          className="flex w-[68px] flex-col items-center justify-center gap-0.5 bg-signal text-[10px] font-medium text-signal-foreground">
          <Trash2 className="h-4 w-4" aria-hidden /> Löschen
        </button>
      </div>
      <div
        className={cn("relative flex items-center gap-2.5 bg-card px-2.5 py-3",
          aktiv && "bg-primary/[0.07]", !zieht && "transition-transform duration-200")}
        style={{ transform: `translateX(${verschiebung}px)` }}
        onTouchStart={(e) => {
          start.current = { x: e.touches[0].clientX, y: e.touches[0].clientY };
          setDx(0);
        }}
        onTouchMove={(e) => {
          if (!start.current) return;
          const ddx = e.touches[0].clientX - start.current.x;
          const ddy = e.touches[0].clientY - start.current.y;
          if (!zieht && Math.abs(ddx) > 8 && Math.abs(ddx) > Math.abs(ddy)) setZieht(true);
          if (zieht || Math.abs(ddx) > Math.abs(ddy)) setDx(ddx);
        }}
        onTouchEnd={() => {
          if (zieht) aufklappen(basis + dx < -AKTIONEN_BREITE / 2 ? g.id : null);
          setZieht(false);
          setDx(0);
          start.current = null;
        }}
      >
        <button type="button" className="flex min-w-0 flex-1 items-center gap-2.5 text-left"
          onClick={() => { if (offen) aufklappen(null); else onLaden(); }}>
          <span className="min-w-0 flex-1">
            <span className={cn("block truncate text-[13.5px] text-foreground", aktiv && "font-semibold")}>{g.titel}</span>
            <span className="mt-px block text-[11px] text-muted-foreground">
              {relativTag(g.updated)} · {g.n_turns} {g.n_turns === 1 ? "Frage" : "Fragen"}
            </span>
          </span>
          {aktiv ? (
            <span className="shrink-0 rounded-full bg-primary/[0.12] px-2 py-0.5 text-[10.5px] font-semibold text-primary">aktiv</span>
          ) : (
            <ChevronRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground/50" aria-hidden />
          )}
        </button>
      </div>
    </div>
  );
}

/** Bottom Sheet „Gespräche" (9a②): Neues Gespräch als erste Aktion, darunter
 *  die Liste — das mobile Gegenstück zum Desktop-Dropdown aus 5a/I-04. */
function GespraecheSheet({ gespraeche, aktivId, onNeu, onLaden, onLoeschen, onUmbenennen, onClose }: {
  gespraeche: GespraechEintrag[]; aktivId: number | null;
  onNeu: () => void; onLaden: (id: number) => void; onLoeschen: (id: number) => void;
  onUmbenennen: (id: number, titel: string) => void; onClose: () => void;
}) {
  const [offenId, setOffenId] = useState<number | null>(null);
  const startY = useRef<number | null>(null);
  useEffect(() => {
    const alt = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = alt; };
  }, []);
  return createPortal(
    <div className="fixed inset-0 z-50 md:hidden" role="dialog" aria-modal="true" aria-label="Gespräche">
      <button type="button" aria-label="Schließen" onClick={onClose}
        className="absolute inset-0 bg-[hsl(212_50%_12%/0.4)]" />
      <div
        className="absolute inset-x-0 bottom-0 flex max-h-[80dvh] flex-col rounded-t-[20px] bg-card px-4 pb-[max(env(safe-area-inset-bottom),16px)] pt-2 shadow-[0_-18px_50px_-12px_rgba(2,32,71,0.45)]"
        onTouchStart={(e) => { startY.current = e.touches[0]?.clientY ?? null; }}
        onTouchMove={(e) => {
          const y = e.touches[0]?.clientY;
          if (startY.current != null && y != null && y - startY.current > 60) onClose();
        }}
      >
        <span aria-hidden className="mx-auto block h-1 w-[38px] shrink-0 rounded-full bg-border" />
        <div className="flex shrink-0 items-baseline justify-between gap-2 px-0.5 pb-2.5 pt-3">
          <span className="font-display text-[17px] font-bold tracking-tight text-foreground">Gespräche</span>
          <span className="font-mono text-[9px] font-medium uppercase tracking-[0.1em] text-muted-foreground">In deinem Konto</span>
        </div>
        <button type="button" onClick={onNeu}
          className="flex h-11 shrink-0 items-center justify-center gap-2 rounded-xl bg-primary text-sm font-semibold text-primary-foreground transition-colors active:bg-primary/90">
          <Plus className="h-4 w-4" aria-hidden /> Neues Gespräch
        </button>
        <div className="mt-2 min-h-0 flex-1 overflow-y-auto overscroll-contain">
          {gespraeche.map((g) => (
            <SheetZeile key={g.id} g={g} aktiv={g.id === aktivId} offen={offenId === g.id}
              aufklappen={setOffenId}
              onLaden={() => onLaden(g.id)}
              onLoeschen={() => { setOffenId(null); onLoeschen(g.id); }}
              onUmbenennen={(titel) => onUmbenennen(g.id, titel)} />
          ))}
        </div>
        <p className="shrink-0 pt-2 text-[10.5px] leading-relaxed text-muted-foreground/70">
          Zeile nach links wischen: Umbenennen · Löschen. Ob Gespräche gespeichert
          werden, änderst du in den Einstellungen.
        </p>
      </div>
    </div>,
    document.body,
  );
}

/* ------------------- Belege-Spalte (Desktop, Design 2⑤) ------------------- */

function BelegeSpalte({ turn, flashId, onFlash, onDazuFragen }: {
  turn: Turn; flashId: number | null; onFlash: (id: number) => void;
  onDazuFragen?: (titel: string) => void;
}) {
  const [showAll, setShowAll] = useState(false);
  const idToNum = useIdToNum(turn);
  const anlBuchstaben = useAnlagenBuchstaben(turn);
  const zitierte = useMemo(() => zitierteVon(turn, idToNum), [turn, idToNum]);
  if (turn.sources.length === 0 && turn.presse.length === 0 && (turn.debatten?.length ?? 0) === 0) return null;
  // Scroll und Höhe übernimmt seit Design 4a die Karten-Hülle im QaTab.
  return (
    <div className="flex flex-col gap-3.5">
      {turn.sources.length > 0 && (
        <QuellenBlock turn={turn} turnIdx={-1} idToNum={idToNum} zitierte={zitierte}
          showAll={showAll} setShowAll={setShowAll} flashId={flashId} ankerPrefix="qa-col"
          onDazuFragen={onDazuFragen} />
      )}
      {(turn.debatten?.length ?? 0) > 0 && <DebattenBlock debatten={turn.debatten} />}
      {(turn.anlagen?.length ?? 0) > 0 && (
        <AnlagenBlock anlagen={turn.anlagen ?? []} buchstaben={anlBuchstaben}
          ankerPrefix="qa-anlage-col" />
      )}
      {turn.presse.length > 0 && <PresseBlock presse={turn.presse} />}
      {/* Keine eigene Aktionszeile mehr: Seit die Meta-Zeile (Teilen, Vorlesen,
          Bewertung) bei JEDEM Turn direkt unter der Antwort steht, wäre sie
          hier nur ein Duplikat mit eigenem Daumen-State (Befund 10.08.). */}
    </div>
  );
}

/* --------------------------- Quellen (RG-02, v2) --------------------------- */

function QuellenBlock({ turn, turnIdx, idToNum, zitierte, showAll, setShowAll, flashId, ankerPrefix, onDazuFragen }: {
  turn: Turn; turnIdx: number; idToNum: Map<number, number>; zitierte: QaSource[];
  showAll: boolean; setShowAll: (fn: (v: boolean) => boolean) => void; flashId: number | null;
  ankerPrefix: string; onDazuFragen?: (titel: string) => void;
}) {
  const router = useRouter();
  // Der Ausklapper zeigt NUR die noch nicht gelisteten Treffer. Vorher lief
  // `turn.sources` komplett durch: die zitierten standen zweimal da — oben als
  // Pills in Fußnoten-Reihenfolge, unten nochmal in Relevanz-Reihenfolge, also
  // mit „durcheinandergewürfelten" Nummern (Tims Befund 10.08.).
  const weitere = useMemo(
    () => turn.sources.filter((s) => !idToNum.has(s.id)),
    [turn.sources, idToNum]);
  return (
    <div>
      <p className="font-mono text-[10px] uppercase tracking-[0.12em] text-muted-foreground">
        Quellen
        <span className="ml-1.5 normal-case tracking-normal text-muted-foreground/70">
          {zitierte.length > 0 ? `${zitierte.length} zitiert · ` : ""}{turn.sources.length} gefunden
          {turn.mode ? ` · ${MODE_LABEL[turn.mode] ?? turn.mode}` : ""}
        </span>
      </p>
      {/* Zitierte als EINZEILIGE Pills: Titel + Jahr (Design 2④) — Gremium &
          Datum stehen im Ausklapper und im Beschluss-Detail. */}
      {zitierte.length > 0 && (
        <div className="mt-1.5 flex flex-wrap gap-1.5">
          {zitierte.map((s) => (
            <button key={s.id} type="button" id={`${ankerPrefix}-${s.id}`}
              onClick={() => router.push(decisionHref(s.id))}
              title={`${s.title ?? ""} — ${s.committee} · ${fmtDatum(s.session_date)}`}
              className={cn(
                "inline-flex max-w-full items-center gap-1.5 rounded-full border border-border bg-card py-1 pl-1 pr-2.5 text-left transition-[background-color,box-shadow] hover:bg-muted",
                flashId === s.id && "ring-2 ring-primary",
              )}>
              <span aria-hidden className="flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-primary text-[9px] font-bold text-primary-foreground">
                {idToNum.get(s.id)}
              </span>
              <span className="max-w-[210px] truncate text-[12px] font-medium leading-none sm:max-w-[240px]">{s.title}</span>
              {turn.qtype === "partei" && s.factions && s.factions.length > 0 && (
                <span className="rounded-[4px] bg-signal/10 px-1 py-px text-[9px] font-bold leading-none text-signal">
                  {s.factions[0]}
                </span>
              )}
              <span className="shrink-0 font-mono text-[9.5px] leading-none text-muted-foreground">{jahr(s.session_date)}</span>
            </button>
          ))}
        </div>
      )}
      {/* Partei-Ehrlichkeit (RG-05). */}
      {turn.qtype === "partei" && (
        <p className="mt-2 text-[11px] leading-snug text-muted-foreground/80">
          Abstimmungsergebnisse einzelner Fraktionen erfasst das Ratsinformationssystem nicht —
          deshalb zeigt Ratslotse hier bewusst keine Stimm-Grafik.
        </p>
      )}
      {/* Ausklapper: die übrigen Treffer in Relevanz-Reihenfolge, mit Gremium ·
          Datum + Score. */}
      {weitere.length > 0 && (
        <button type="button" onClick={() => setShowAll((v) => !v)} aria-expanded={showAll}
          className="mt-2 flex items-center gap-1.5 rounded-full border border-border px-3 py-1 text-xs font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground">
          {showAll ? (<><ChevronUp className="h-3.5 w-3.5" /> Weniger</>)
            : zitierte.length > 0
              ? (<><ChevronDown className="h-3.5 w-3.5" /> {weitere.length} weitere</>)
              : (<><ChevronDown className="h-3.5 w-3.5" /> Alle {weitere.length}</>)}
        </button>
      )}
      {showAll && weitere.length > 0 && (
        <div className="mt-2 space-y-1">
          {zitierte.length > 0 && (
            <p className="px-2 pb-0.5 text-[11px] text-muted-foreground/70">
              Gefunden und gelesen, in der Antwort aber nicht zitiert:
            </p>
          )}
          {weitere.map((s) => (
            <div key={s.id} id={`${ankerPrefix}-alle-${s.id}`}
              className={cn(
                "group flex w-full items-baseline gap-2 rounded-lg px-2 py-1.5 transition-colors hover:bg-muted",
                flashId === s.id && "ring-2 ring-primary",
              )}>
              <button type="button" onClick={() => router.push(decisionHref(s.id))}
                className="flex min-w-0 flex-1 items-baseline gap-2 text-left">
                <span aria-hidden className="mt-[7px] h-1 w-1 shrink-0 self-start rounded-full bg-border" />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-[12.5px]">{s.title}</span>
                  <span className="block font-mono text-[9.5px] uppercase tracking-wide text-muted-foreground">
                    {s.committee} · {fmtDatum(s.session_date)}
                  </span>
                </span>
              </button>
              {typeof s.score === "number" && (
                <span className="shrink-0 font-mono text-[9.5px] text-muted-foreground/70">Score {Math.round(s.score * 100)}</span>
              )}
              {/* 5a/I-08: das Gespräch direkt an einer Quelle weiterführen. */}
              {onDazuFragen && (
                <button type="button" onClick={() => onDazuFragen(s.title ?? "")}
                  title="Dazu fragen" aria-label={`Zu „${s.title}" weiterfragen`}
                  className="shrink-0 self-center rounded-md p-1 text-muted-foreground opacity-60 transition-opacity hover:bg-background hover:text-primary focus:opacity-100 sm:opacity-0 sm:group-hover:opacity-100">
                  <Sparkles className="h-3.5 w-3.5" aria-hidden />
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/** Teilen mit Substanz (Task 31): erstellt beim Klick einen Server-Snapshot
 *  von Frage + EXAKTER Antwort + zitierten Quellen und teilt dessen URL —
 *  der alte ?q=-Link ließ Empfänger die Frage neu ausführen und eine ANDERE
 *  Antwort sehen (Tims Befund). Das Token wird je Turn nur einmal erzeugt.
 *
 *  Der Snapshot nimmt seit dem Bausteine-Nachtrag auch Debatten, Presse,
 *  Anlagen und die verdichteten Fraktions-Positionen mit: Wer den Link
 *  öffnete, sah vorher deutlich weniger als die Person, die ihn teilte. */
function TeilenKnopf({ turn, zitierte }: { turn: Turn; zitierte: QaSource[] }) {
  const tokenRef = useRef<string | null>(null);
  const [laedt, setLaedt] = useState(false);
  const teilen = async () => {
    if (laedt) return;
    let token = tokenRef.current;
    if (!token) {
      setLaedt(true);
      try {
        // Parteien liegen nicht am Turn, sondern im Cache des Bausteins —
        // derselbe Schlüssel wie beim Laden (kondensierte Frage).
        const parteien = turn.qtype !== "person"
          ? (parteiMeinungenCache.get(turn.kontext || turn.frage) ?? []) : [];
        const r = await fetch(apiUrl("/council/qa-share"), {
          method: "POST", credentials: "include",
          headers: { "Content-Type": "application/json", ...authHeaders() },
          body: JSON.stringify({
            frage: turn.frage.slice(0, 300),
            antwort: turn.antwort.slice(0, 8000),
            quellen: zitierte.slice(0, 40).map((q) => ({
              id: q.id, title: (q.title ?? "").slice(0, 300),
              session_date: q.session_date ?? null,
              committee: q.committee ?? null, outcome: q.outcome ?? null,
            })),
            debatten: (turn.debatten ?? []).slice(0, 20).map((d) => ({
              sprecher: d.sprecher, partei: d.partei, art: d.art,
              top: (d.top ?? "")?.slice(0, 300) || null,
              auszug: (d.auszug ?? "").slice(0, 2000),
              committee: d.committee, datum: d.datum,
            })),
            presse: (turn.presse ?? []).slice(0, 10).map((p) => ({
              titel: p.titel.slice(0, 300), url: p.url.slice(0, 500), datum: p.datum,
            })),
            // nr muss mit: Ohne sie fänden die „[A1]"-Belege im geteilten
            // Text ihre Anlage nicht und würden ersatzlos geschluckt.
            anlagen: (turn.anlagen ?? []).slice(0, 10).map((a, i) => ({
              nr: a.nr ?? i + 1,
              label: a.label, url: a.url, vorlage_nr: a.vorlage_nr,
              vorlage_titel: a.vorlage_titel, auszug: (a.auszug ?? "").slice(0, 600),
            })),
            // Ohne beitraege_liste: die Aufklapp-Beiträge blähen den Snapshot,
            // die geteilte Seite zeigt Position und Kernaussage.
            parteien: parteien.slice(0, 12).map((p) => ({
              partei: p.partei, haltung: p.haltung ?? null,
              position: (p.position ?? "").slice(0, 800), einig: p.einig,
              hinweis: p.hinweis, kernaussage: p.kernaussage, beitraege: p.beitraege,
            })),
          }),
        });
        if (!r.ok) throw new Error(String(r.status));
        token = (await r.json()).token as string;
        tokenRef.current = token;
      } catch {
        toast.error("Teilen gerade nicht möglich — bitte nochmal versuchen.");
        return;
      } finally {
        setLaedt(false);
      }
    }
    const base = isNativeApp() ? "https://ratslotse.de" : window.location.origin;
    const url = `${base}/g?t=${token}`;
    if (navigator.share) {
      try {
        await navigator.share({ title: `Ratslotse: ${turn.frage}`, url });
        return;
      } catch (e) {
        if ((e as Error).name === "AbortError") return;
      }
    }
    try {
      await navigator.clipboard.writeText(url);
      toast.success("Link zur Antwort kopiert.");
    } catch {
      toast.error("Link konnte nicht kopiert werden.");
    }
  };
  return (
    <button type="button" onClick={() => void teilen()} aria-label="Antwort teilen"
      title="Antwort teilen (Link zeigt genau diese Antwort)"
      className="inline-flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground">
      {laedt ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Share2 className="h-3.5 w-3.5" />}
    </button>
  );
}

/* ------------------ Baustein „Das sagen die Parteien" (RG-09) ------------------ */

/** Doppel-Fetches (Remount durch Kompaktzeile, Strict-Mode) kosten echte
 *  LLM-Calls — das Ergebnis je kondensierter Frage einmal festhalten. Der
 *  Cache ist außerdem die Quelle für den Teilen-Snapshot: Was hier steht,
 *  wandert beim Teilen mit in den Link (Tims Befund 10.08.). */
export const parteiMeinungenCache = new Map<string, ParteiMeinung[]>();

/** Lädt die verdichteten Fraktions-Positionen nach und übergibt sie an
 *  `ParteienListe` — die Darstellung teilt sich diese Seite mit app/g. */
/** „Worum geht es?" — Steckbrief zu den in der Frage genannten Objekten.
 *
 *  Die Beschreibungen liegen seit dem Themen-Ausbau in der Datenbank, wurden
 *  von der Frage-Antwort aber nie gezeigt. Echte Nutzerfragen wie „Was ist die
 *  GSG, was macht sie?" beantworten Beschlüsse schlecht — sie dokumentieren
 *  Entscheidungen, nicht Hintergrund. Der Baustein steht deshalb ÜBER der
 *  Antwort: erst wissen, worum es geht, dann was beschlossen wurde. */
function SteckbriefBaustein({ steckbriefe }: {
  steckbriefe: NonNullable<Turn["steckbriefe"]>;
}) {
  const [offen, setOffen] = useState<string | null>(null);
  if (steckbriefe.length === 0) return null;
  return (
    <div className="flex flex-col gap-1.5">
      {steckbriefe.slice(0, 2).map((s) => {
        const lang = s.beschreibung.length > 180;
        const auf = offen === s.slug;
        return (
          <div key={s.slug} className="rounded-xl border border-border bg-muted/30 px-3.5 py-2.5">
            <p className="flex items-center gap-1.5 font-mono text-[9px] font-medium uppercase tracking-[0.1em] text-muted-foreground">
              <BookOpen className="h-3 w-3" aria-hidden /> Worum geht es?
            </p>
            <p className="mt-1.5 text-[13px] leading-relaxed text-foreground">
              <strong className="font-semibold">{s.name}:</strong>{" "}
              {auf || !lang ? s.beschreibung : `${s.beschreibung.slice(0, 180).trimEnd()} …`}
            </p>
            <div className="mt-1 flex items-center gap-3">
              {lang && (
                <button type="button" onClick={() => setOffen(auf ? null : s.slug)}
                  className="text-[11.5px] font-medium text-primary hover:underline">
                  {auf ? "Weniger" : "Mehr"}
                </button>
              )}
              <Link href={`/council/entity?slug=${encodeURIComponent(s.slug)}`}
                className="text-[11.5px] font-medium text-primary hover:underline">
                Alle Beschlüsse dazu
              </Link>
            </div>
          </div>
        );
      })}
    </div>
  );
}

/** Ehrlichkeits-Hinweis bei dünner Beleglage.
 *
 *  Das einzige begründete 👎 („Falschinfo", Giftmüll am Fliegerhorst) traf eine
 *  Frage mit genau dieser Signatur: wenige, schwache Treffer — und trotzdem eine
 *  Antwort im selbstbewussten Ton. Der Hinweis sagt es offen und bietet den
 *  Ausweg an, der hier wirklich hilft (die Recherche liest auch Anlagen und
 *  Protokolle). */
function DuenneBeleglage({ onGruendlich, mitSteckbrief }: {
  onGruendlich?: () => void; mitSteckbrief?: boolean;
}) {
  return (
    <div className="rounded-xl border border-border bg-card px-3.5 py-3">
      <p className="flex items-start gap-2 text-[12.5px] leading-relaxed text-muted-foreground">
        <SearchX className="mt-0.5 h-3.5 w-3.5 shrink-0 text-signal" aria-hidden />
        <span>
          {mitSteckbrief
            /* Mit Steckbrief ist die EINORDNUNG belegt, nur die Beschlusslage
               dünn — dann wäre ein pauschales „mit Vorsicht" schlicht falsch. */
            ? "Der Rat hat zu dieser Frage wenig entschieden — die Einordnung oben stammt aus den Ratsunterlagen, die Beschlusslage darunter ist dünn."
            : "Zu dieser Frage geben die Ratsunterlagen wenig her — die Antwort steht auf wenigen, nur schwach passenden Beschlüssen. Nimm sie mit Vorsicht."}
        </span>
      </p>
      {onGruendlich && (
        <button type="button" onClick={onGruendlich}
          className="mt-2 inline-flex items-center gap-1.5 rounded-[10px] border border-border bg-card px-3 py-1.5 text-xs font-medium transition-colors hover:bg-muted">
          <FlaskConical className="h-3 w-3" aria-hidden /> Gründlich recherchieren
        </button>
      )}
    </div>
  );
}

function ParteienBaustein({ frage, onFrageStellen }: {
  frage: string; onFrageStellen?: (text: string) => void;
}) {
  const [parteien, setParteien] = useState<ParteiMeinung[] | null>(
    () => parteiMeinungenCache.get(frage) ?? null);
  const [ohneBeitraege, setOhneBeitraege] = useState<string[]>([]);
  useEffect(() => {
    if (parteiMeinungenCache.has(frage)) { setParteien(parteiMeinungenCache.get(frage)!); return; }
    let aktiv = true;
    fetch(apiUrl("/council/partei-meinungen"), {
      method: "POST", credentials: "include",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify({ frage }),
    })
      .then((r) => { if (!r.ok) throw new Error(String(r.status)); return r.json(); })
      .then((b) => {
        // RG-09: Reihenfolge nach Redeanteil, nicht alphabetisch.
        const sortiert = ((b.parteien as ParteiMeinung[]) ?? [])
          .slice().sort((a, z) => z.beitraege - a.beitraege);
        parteiMeinungenCache.set(frage, sortiert);
        if (aktiv) {
          setParteien(sortiert);
          setOhneBeitraege((b.ohne_beitraege as string[]) ?? []);
        }
      })
      // Fehler NICHT cachen: ein transienter 4xx/5xx soll den Baustein nur
      // für diesen Moment verstecken, nicht bis zum nächsten Voll-Reload.
      .catch(() => { if (aktiv) setParteien([]); });
    return () => { aktiv = false; };
  }, [frage]);

  if (parteien !== null && parteien.length < 2) return null; // dünne Lage: gar nicht
  return <ParteienListe parteien={parteien} ohneBeitraege={ohneBeitraege} onFrageStellen={onFrageStellen} />;
}

/* ---------------------- Fragetyp-Bausteine (RG-03/04) --------------------- */

function Baustein({ turn, idToNum, onJump }: {
  turn: Turn; idToNum: Map<number, number>; onJump: (id: number) => void;
}) {
  const zitierteQuellen = useMemo(() => zitierteVon(turn, idToNum), [turn, idToNum]);

  // Ein Zeitstrahl braucht ZEIT: Mindestens zwei verschiedene Sitzungstermine —
  // fünf Beschlüsse derselben Ratssitzung („Was wurde am 01.06. beschlossen?")
  // sind eine Aufzählung, kein Verlauf (Tims Befund 09.08.).
  const termine = new Set(zitierteQuellen.map((s) => s.session_date).filter(Boolean));
  if (turn.qtype === "verlauf" && zitierteQuellen.length >= 2 && termine.size >= 2) {
    const stationen = [...zitierteQuellen].sort((a, b) => (a.session_date ?? "").localeCompare(b.session_date ?? ""));
    return (
      <div className="rounded-xl border border-border bg-card p-3.5">
        <div className="flex flex-col">
          {stationen.map((s, i) => {
            const letzte = i === stationen.length - 1;
            return (
              <div key={s.id} className="relative flex gap-3 pb-3.5 last:pb-0">
                <div className="flex w-4 shrink-0 flex-col items-center">
                  <span className={cn(
                    "mt-1 h-2.5 w-2.5 shrink-0 rounded-full border-2",
                    letzte ? "border-primary bg-primary shadow-[0_0_0_3px_hsl(var(--primary)/0.15)]" : "border-primary/45 bg-card",
                  )} />
                  {!letzte && <span className="mt-1 w-0.5 flex-1 rounded-full bg-border" />}
                </div>
                <div className={cn("min-w-0 flex-1", letzte && "rounded-[10px] bg-primary/[0.06] p-2")}>
                  {letzte && (
                    <p className="font-mono text-[9px] font-bold uppercase tracking-[0.14em] text-primary">Aktueller Stand</p>
                  )}
                  <p className="flex flex-wrap items-center gap-x-2 gap-y-0.5">
                    <span className="font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
                      {fmtDatum(s.session_date)} · {s.committee}
                    </span>
                    {s.outcome && (
                      <span className={cn("rounded px-1.5 py-px text-[9.5px] font-semibold", OUTCOME_BADGE[s.outcome] ?? "bg-muted text-muted-foreground")}>
                        {OUTCOME_LABEL[s.outcome] ?? s.outcome}
                      </span>
                    )}
                  </p>
                  <p className="mt-0.5 text-[12.5px] font-semibold leading-snug">
                    {s.title}
                    <button type="button" onClick={() => onJump(s.id)} aria-label={`Quelle ${idToNum.get(s.id)} anzeigen`}
                      className="ml-1 inline-flex h-4 min-w-4 -translate-y-[2px] items-center justify-center rounded bg-primary/10 px-1 align-baseline text-[10px] font-semibold leading-none text-primary hover:bg-primary/20">
                      {idToNum.get(s.id)}
                    </button>
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    );
  }

  if (turn.qtype === "geld") {
    const mitBetrag = zitierteQuellen.filter((s) => (s.amount_eur ?? 0) > 0);
    if (mitBetrag.length === 0) return null;
    const max = Math.max(...mitBetrag.map((s) => s.amount_eur ?? 0));
    const gross = mitBetrag[0];
    // Kostenentwicklung (10.08.26): Beträge mit Datum, chronologisch — als
    // ehrliche ZEITREIHE ohne Steigerungs-Behauptung. Ein „von X auf Y"-Delta
    // gibt es NUR innerhalb derselben Vorlagen-Familie (Revisions-Suffix
    // gestrippt) — Beträge verschiedener Vorlagen können verschiedene Dinge
    // messen (Planungskosten vs. Gesamtkosten), da wäre ein Pfeil gelogen.
    const basis = (nr: string | null | undefined) => (nr ?? "").replace(/-\d+$/, "");
    const zeitreihe = mitBetrag
      .filter((s) => s.session_date)
      .sort((a, b) => a.session_date.localeCompare(b.session_date));
    const termineGeld = new Set(zeitreihe.map((s) => s.session_date));
    const familien = new Map<string, typeof zeitreihe>();
    for (const s of zeitreihe) {
      const b = basis(s.vorlage_nr);
      if (!b) continue;
      familien.set(b, [...(familien.get(b) ?? []), s]);
    }
    const delta = [...familien.values()]
      .filter((f) => f.length >= 2 && f[0].amount_eur !== f[f.length - 1].amount_eur)
      .sort((a, b) => (b[b.length - 1].amount_eur ?? 0) - (a[a.length - 1].amount_eur ?? 0))[0];
    return (
      <div className="rounded-xl border border-border bg-card p-3.5">
        <p className="font-mono text-[10px] uppercase tracking-[0.12em] text-muted-foreground">Aus den zitierten Beschlüssen</p>
        <p className="mt-1 flex items-baseline gap-1.5">
          <span className="text-[26px] font-bold tabular-nums tracking-tight sm:text-[28px]">{fmtEur(gross.amount_eur ?? 0)}</span>
          <FussnotenChip id={gross.id} idToNum={idToNum} onJump={onJump} />
        </p>
        <p className="max-w-full truncate text-[11.5px] text-muted-foreground">{gross.title}</p>
        {delta && (
          <p className="mt-2 flex flex-wrap items-center gap-x-1.5 gap-y-0.5 rounded-lg bg-primary/[0.06] px-2.5 py-1.5 text-[12px]">
            <span className="font-medium">Entwicklung derselben Vorlage:</span>
            <span className="tabular-nums">{fmtEur(delta[0].amount_eur ?? 0)}</span>
            <span className="text-muted-foreground">({fmtDatumKurz(delta[0].session_date)})</span>
            <span aria-hidden>→</span>
            <span className="font-semibold tabular-nums">{fmtEur(delta[delta.length - 1].amount_eur ?? 0)}</span>
            <span className="text-muted-foreground">({fmtDatumKurz(delta[delta.length - 1].session_date)})</span>
            <FussnotenChip id={delta[0].id} idToNum={idToNum} onJump={onJump} />
            <FussnotenChip id={delta[delta.length - 1].id} idToNum={idToNum} onJump={onJump} />
          </p>
        )}
        {zeitreihe.length >= 2 && termineGeld.size >= 2 ? (
          <div className="mt-2.5 flex flex-col gap-1.5">
            <p className="font-mono text-[9px] uppercase tracking-[0.12em] text-muted-foreground/70">Beträge im Zeitverlauf</p>
            {zeitreihe.slice(-5).map((s) => (
              <div key={s.id} className="flex items-center gap-2">
                <span className="w-[64px] shrink-0 font-mono text-[10px] text-muted-foreground">{fmtDatumKurz(s.session_date)}</span>
                <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-primary/[0.12]">
                  <span className="block h-full rounded-full bg-primary" style={{ width: `${Math.max(6, Math.round(((s.amount_eur ?? 0) / max) * 100))}%` }} />
                </span>
                <span className="shrink-0 text-[12px] font-semibold tabular-nums">{fmtEur(s.amount_eur ?? 0)}</span>
                <FussnotenChip id={s.id} idToNum={idToNum} onJump={onJump} />
              </div>
            ))}
          </div>
        ) : mitBetrag.length > 1 && (
          <div className="mt-2.5 flex flex-col gap-1.5">
            {mitBetrag.slice(1, 4).map((s) => (
              <div key={s.id} className="flex items-center gap-2">
                <span className="w-[110px] shrink-0 truncate text-[11px] text-muted-foreground sm:w-[130px]">{s.title}</span>
                <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-primary/[0.12]">
                  <span className="block h-full rounded-full bg-primary" style={{ width: `${Math.max(6, Math.round(((s.amount_eur ?? 0) / max) * 100))}%` }} />
                </span>
                <span className="shrink-0 text-[12px] font-semibold tabular-nums">{fmtEur(s.amount_eur ?? 0)}</span>
                <FussnotenChip id={s.id} idToNum={idToNum} onJump={onJump} />
              </div>
            ))}
          </div>
        )}
      </div>
    );
  }

  if (turn.qtype === "partei") {
    const zaehler = new Map<string, number>();
    for (const s of turn.sources) for (const f of s.factions ?? []) zaehler.set(f, (zaehler.get(f) ?? 0) + 1);
    const dominant = [...zaehler.entries()].sort((a, b) => b[1] - a[1])[0];
    if (!dominant) return null;
    const zitiertMit = zitierteQuellen.filter((s) => (s.factions ?? []).includes(dominant[0])).length;
    return (
      <div className="flex items-center gap-2 rounded-[10px] border border-border bg-card px-3 py-2 text-[12.5px]">
        <span aria-hidden className="h-2 w-2 shrink-0 rounded-full bg-signal" />
        <span className="min-w-0 flex-1">
          Anträge der {dominant[0]}-Fraktion zu diesem Thema: <strong>{dominant[1]}</strong>
          {zitiertMit > 0 ? <span className="text-muted-foreground"> · {zitiertMit} zitiert</span> : null}
        </span>
      </div>
    );
  }

  return null;
}

function FussnotenChip({ id, idToNum, onJump }: {
  id: number; idToNum: Map<number, number>; onJump: (id: number) => void;
}) {
  if (!idToNum.has(id)) return null;
  return (
    <button type="button" onClick={() => onJump(id)} aria-label={`Quelle ${idToNum.get(id)} anzeigen`}
      className="inline-flex h-4 min-w-4 items-center justify-center rounded bg-primary/10 px-1 text-[10px] font-semibold leading-none text-primary hover:bg-primary/20">
      {idToNum.get(id)}
    </button>
  );
}
