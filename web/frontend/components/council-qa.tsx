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
  Square, CircleSlash, ExternalLink, ArrowDown, History, RotateCcw, MessageSquarePlus,
  Share2, ThumbsDown, ThumbsUp, Trash2, Volume2, X } from "lucide-react";
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

// Zitat-Klammern im Antworttext. Spiegelt council/qa.py (_CITE_RE /
// citation_ids) — beide Seiten MÜSSEN dieselbe Regel anwenden, sonst laufen
// Fußnoten-Nummerierung und die vom Server gemeldeten `cited` auseinander.
const CITE_SOURCE = String.raw`\[\d[^\]\n]{0,160}\]`;
const CITE_RE = new RegExp(CITE_SOURCE, "g");
const CITE_SPLIT_RE = new RegExp(`(${CITE_SOURCE})`, "g");
const CITE_EXACT_RE = new RegExp(`^${CITE_SOURCE}$`);

function citationIds(bracket: string): number[] {
  const inner = bracket.slice(1, -1);
  if (/^[\d,\s]+$/.test(inner)) return (inner.match(/\d+/g) ?? []).map(Number);
  const m = /^\s*(\d+)/.exec(inner);
  return m ? [Number(m[1])] : [];
}

const EXAMPLES = [
  "Wie ist der Stand bei der Cäcilienbrücke?",
  "Was wurde zum Radverkehr beschlossen?",
  "Was kostet der Neubau des Stadions?",
  "Gab es Beschlüsse zu Kita-Plätzen?",
];

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

type PresseHinweis = { titel: string; url: string; datum: string | null };

/** Task 16: Wortbeitrag aus einem Sitzungsprotokoll (Rede, Anfrage,
 *  Einwohnerfrage oder Verwaltungs-Zusage) im Belege-Bereich. */
type DebattenHinweis = {
  sprecher: string | null; partei: string | null; art: string;
  top: string | null; auszug: string; committee: string | null; datum: string | null;
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
    const klartext = text.replace(CITE_RE, "").replace(/\*\*([^*]+)\*\*/g, "$1");
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
    setAbgegeben(bewertung);
    setFrageGrund(bewertung === "down");
    // Der Daumen zählt sofort — auch wenn der Grund nie kommt.
    post(bewertung);
    if (bewertung === "up") toast.success("Danke für die Rückmeldung!");
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
      <button type="button" aria-label="Antwort war hilfreich" title="Hilfreich"
        disabled={abgegeben !== null}
        onClick={() => senden("up")}
        className={cn("rounded-md p-1 transition-colors",
          abgegeben === "up" ? "text-primary" : "text-muted-foreground hover:bg-muted hover:text-foreground",
          abgegeben === "down" && "opacity-40")}>
        <ThumbsUp className="h-3.5 w-3.5" aria-hidden />
      </button>
      <button type="button" aria-label="Antwort war nicht hilfreich" title="Nicht hilfreich"
        disabled={abgegeben !== null}
        onClick={() => senden("down")}
        className={cn("rounded-md p-1 transition-colors",
          abgegeben === "down" ? "text-signal" : "text-muted-foreground hover:bg-muted hover:text-foreground",
          abgegeben === "up" && "opacity-40")}>
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
const fmtDatumKurz = (d?: string | null) =>
  d ? new Date(d).toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit", year: "2-digit" }) : "";
/** Naives UTC-ISO aus dem Backend (ohne „Z") als UTC deuten — sonst rutscht
 *  ein 00:30-Uhr-Gespräch aufs Vortagsdatum (Befund F14). */
const fmtUtcKurz = (d: string) =>
  fmtDatumKurz(/Z$|[+-]\d\d:?\d\d$/.test(d) ? d : `${d}Z`);
const jahr = (d?: string | null) => (d ? d.slice(0, 4) : "");

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

/** Sprung zur Quelle: mobil zum Inline-Block, ab lg in die Belege-Spalte. */
function jumpZuQuelle(turnIdx: number, id: number, spalte: boolean) {
  const ziel = spalte && window.matchMedia("(min-width: 1024px)").matches
    ? document.getElementById(`qa-col-${id}`) ?? document.getElementById(`qa-source-${turnIdx}-${id}`)
    : document.getElementById(`qa-source-${turnIdx}-${id}`) ?? document.getElementById(`qa-col-${id}`);
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
        .then((s: { frage: string; antwort: string; quellen: QaSource[] }) => {
          setTurns((alt) => alt.length > 0 ? alt : [{
            key: naechsterKey(),
            frage: s.frage, antwort: s.antwort, qtype: null, mode: null,
            sources: s.quellen ?? [], presse: [], debatten: [],
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
  const showIntro = turns.length === 0;
  const [nativeApp, setNativeApp] = useState(false);
  useEffect(() => { setNativeApp(isNativeApp()); }, []);

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
      type DbTurn = { frage: string; antwort: string; quellen: { sources?: QaSource[]; cited?: number[] } | null };
      setTurns((g.turns as DbTurn[]).map((t) => ({
        key: naechsterKey(),
        frage: t.frage, antwort: t.antwort, qtype: null, mode: null,
        sources: t.quellen?.sources ?? [], presse: [], debatten: [], cited: t.quellen?.cited ?? [],
        followups: [], kontext: null,
      })));
      setGespraechId(id);
      setZeigeListe(false);
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
        const top = rows[0].top_titel;
        if (top) {
          const kurz = top.split(/ [-–(]/)[0].trim().slice(0, 60);
          if (kurz.length >= 8) vorschlaege.push(`Was wurde zu „${kurz}" entschieden?`);
        }
        setFrische(vorschlaege.slice(0, 2));
      })
      .catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showIntro]);
  const beispiele = [...frische, ...EXAMPLES].slice(0, 4);
  // Weiterfragen leben im Composer (Design 2②) — nur vom jüngsten Turn.
  const composerFollowups = !loading && letzter && !letzter.fehler ? letzter.followups.slice(0, 3) : [];

  return (
    <div className="mx-auto mt-3 lg:grid lg:max-w-[1220px] lg:grid-cols-[minmax(0,1fr)_320px] lg:items-start lg:gap-6">
      {/* Chat-Spalte. Mobil: min-height, damit der Composer auch im Empty
          State unten klebt (Design 2①) — in der nativen App steht mehr Chrome
          im Weg (iOS-Test 09.08.), erst nach dem Mount entscheiden.
          Ab lg wird sie zur GESPRÄCHS-BÜHNE (Design 4a): ein getöntes Panel,
          in der Höhe an den Viewport gebunden — der Verlauf scrollt IM Panel,
          der Composer klebt an der Panel-Unterkante statt „irgendwo am
          Seitenende" zu hängen (Tims Whitespace-Befund). */}
      <div className={cn("flex flex-col",
        nativeApp ? "min-h-[calc(100dvh-380px)]" : "min-h-[calc(100dvh-230px)]",
        "lg:relative lg:h-[calc(100dvh-135px)] lg:min-h-0 lg:overflow-hidden lg:rounded-2xl lg:border lg:border-border lg:bg-primary/[0.04] dark:lg:bg-primary/[0.07]",
      )}>
        {(modeToggle || turns.length > 0 || gespraeche.length > 0) && (
          <div className="mb-1 flex items-center justify-between gap-2 lg:mb-0 lg:px-4 lg:pb-2 lg:pt-3">
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
                <div className="absolute right-0 top-full z-30 mt-1.5 w-72 rounded-xl border border-border bg-card p-1.5 shadow-lg">
                  <p className="px-2 pb-1 pt-1.5 font-mono text-[10px] uppercase tracking-[0.12em] text-muted-foreground">
                    Meine Gespräche · in deinem Konto
                  </p>
                  {gespraeche.map((g) => (
                    <div key={g.id} className="group flex items-center gap-1 rounded-lg px-2 py-1.5 transition-colors hover:bg-muted">
                      <button type="button" onClick={() => void gespraechLaden(g.id)}
                        className="min-w-0 flex-1 text-left">
                        <span className="block truncate text-[12.5px] font-medium text-foreground">{g.titel}</span>
                        <span className="block text-[10.5px] text-muted-foreground">
                          {fmtUtcKurz(g.updated)} · {g.n_turns} {g.n_turns === 1 ? "Frage" : "Fragen"}
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
              )}
            </div>
          </div>
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
            <Mascot pose="wave" bob className="h-20 w-20" />
            <h2 className="mt-3 text-xl font-bold tracking-tight">Frag den Rat</h2>
            <p className="mt-1.5 max-w-md text-sm text-muted-foreground">
              Die Antwort entsteht aus den echten Ratsbeschlüssen — mit Fußnote zu jeder Quelle.
            </p>
            <p className="mt-5 font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground/70">
              Zum Beispiel
            </p>
            <div className="mt-2 flex w-full max-w-md flex-col gap-1.5">
              {beispiele.map((ex, i) => (
                <button key={ex} type="button" onClick={() => void ask(ex)}
                  className="flex items-center gap-2.5 rounded-[11px] border border-border bg-card px-3 py-2.5 text-left text-[13.5px] transition-[background-color,transform] duration-150 ease-out-strong hover:bg-muted active:scale-[0.99]">
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
                onDazuFragen={(titel) => void ask(`Erzähl mir mehr zu „${titel}".`)}
                onFrageStellen={(text) => void ask(text)}
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
        <div className="sticky bottom-0 z-10 -mx-1 mt-4 bg-gradient-to-t from-background via-background to-transparent px-1 pb-[max(env(safe-area-inset-bottom),8px)] pt-4 print:hidden lg:static lg:mx-0 lg:bg-none lg:px-4 lg:pb-4 lg:pt-2">
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
          {(composerFollowups.length > 0 || (!loading && letzter && !letzter.fehler && letzter.antwort)) && (
            <ChipZeile>
              {composerFollowups.map((s) => (
                <button key={s} type="button" onClick={() => void ask(s)}
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
            <form onSubmit={(e) => { e.preventDefault(); void ask(q); }} className="flex gap-2">
              <div className="relative flex-1">
                <Sparkles className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input ref={inputRef} data-search enterKeyHint="send"
                  className="h-12 rounded-2xl pl-9"
                  placeholder={turns.length > 0 ? "Anschlussfrage stellen …" : "Frag den Rat …"}
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
            </form>
          )}
          {/* Feedback-Runde 3: Der Disclaimer ist toter Dauer-Text — er steht
              nur noch im Empty State; wer schon im Gespräch ist, kennt ihn. */}
          {showIntro && (
            <p className="mt-1.5 text-center text-[10px] text-muted-foreground/60">
              Keine personenbezogenen Daten eingeben — Fragen gehen an einen externen KI-Dienst.
            </p>
          )}
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
              onDazuFragen={(titel) => void ask(`Erzähl mir mehr zu „${titel}".`)}
              onFlash={flash} />
          ) : loading ? (
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

function TurnView({ turn, turnIdx, istLetzter, loading, step, word, flashId, onJump, onRetry, onEigeneFrage, onDazuFragen, onFrageStellen }: {
  turn: Turn; turnIdx: number; istLetzter: boolean; loading: boolean;
  step: Step | null; word: string; flashId: number | null;
  onJump: (id: number) => void; onRetry: () => void; onEigeneFrage: () => void;
  onDazuFragen?: (titel: string) => void;
  onFrageStellen?: (text: string) => void;
}) {
  const [showAll, setShowAll] = useState(false);
  // Ältere Turns beruhigen (Design 2⑤): Belege hinter der Kompaktzeile.
  const [aufgeklappt, setAufgeklappt] = useState(false);
  // 5a/I-01: welcher Zitat-Chip gerade sein Peek zeigt.
  const [peekId, setPeekId] = useState<number | null>(null);
  const idToNum = useIdToNum(turn);
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
  const nichtsGefunden = !loading && hatAntwort && turn.sources.length === 0 && !turn.fehler;
  // Mobil zeigt der jüngste Turn seine Belege inline (die Desktop-Spalte
  // übernimmt ab lg); ältere Turns nur nach Klick auf die Kompaktzeile.
  const belegeInline = istLetzter ? "lg:hidden" : aufgeklappt ? "" : "hidden";

  return (
    <div className="flex flex-col gap-3">
      {/* Nutzer-Turn: rechtsbündig, stille Bubble (RG-01). */}
      <div className="flex justify-end">
        <div className="max-w-[78%] rounded-[18px] rounded-br-[6px] border border-primary/[0.18] bg-primary/[0.07] px-3.5 py-2.5 text-[14.5px] leading-[1.55] sm:max-w-[60%]">
          {turn.frage}
        </div>
      </div>

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
        <div aria-busy={loading} className="flex flex-col gap-3.5">
          {/* div statt p: die Antwort darf Listen (ul) enthalten. */}
          <div className="whitespace-pre-wrap text-[14.5px] leading-[1.7] text-foreground sm:leading-[1.75]">
            {/* 5a/I-01: Der Chip öffnet erst das Peek — nicht sofort wegspringen. */}
            <AnswerWithCitations text={turn.antwort} idToNum={idToNum} onJump={(id) => setPeekId(id)} />
            {loading && step === "answer" && <span className="ml-0.5 inline-block h-4 w-1.5 animate-pulse bg-primary align-text-bottom" />}
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

          {/* RG-09: „Das sagen die Parteien" — direkt unter dem Antworttext,
              vor Zeitstrahl/Geld/Karte. Lädt nach der Antwort nach; bei dünner
              Lage verschwindet er ganz (kein Leerzustand). Gate ≥1 statt ≥2:
              Sachstands-Fragen ließen oft nur einen Debatten-Beleg durch,
              obwohl der Baustein mit seiner eigenen Fraktions-Suche liefert
              (Tims Befund 10.08.) — ob es reicht, entscheidet der Endpoint. */}
          {!loading && turn.antwort && !turn.fehler && !turn.abgebrochen
            && (turn.debatten?.length ?? 0) >= 1 && (
            <ParteienBaustein frage={turn.kontext || turn.frage} onFrageStellen={onFrageStellen} />
          )}

          {!loading && <Baustein turn={turn} idToNum={idToNum} onJump={(id) => setPeekId(id)} />}

          {/* 5a/I-10: Mini-Karte der zitierten Orte — deterministisch aus den
              geocodierten Entitäten der Quellen; Pin-Klick öffnet das Peek. */}
          {!loading && ortsPins.length > 0 && (
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
          {!loading && (
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
                {/* 5a/I-02: ehrlich sagen, worauf die Antwort fußt. */}
                Automatische Antwort{zitierte.length > 0 ? `, ${stuetztAuf(zitierte)}` : " aus den gefundenen Beschlüssen"} — kann unvollständig sein. Quellen prüfen.
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/* ------------------- Belege-Spalte (Desktop, Design 2⑤) ------------------- */

function BelegeSpalte({ turn, flashId, onFlash, onDazuFragen }: {
  turn: Turn; flashId: number | null; onFlash: (id: number) => void;
  onDazuFragen?: (titel: string) => void;
}) {
  const [showAll, setShowAll] = useState(false);
  const idToNum = useIdToNum(turn);
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
  const nichtZitiert = turn.sources.length - zitierte.length;
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
      {/* Ausklapper: alle Treffer in Relevanz-Reihenfolge, mit Gremium · Datum + Score. */}
      {(nichtZitiert > 0 || showAll) && (
        <button type="button" onClick={() => setShowAll((v) => !v)} aria-expanded={showAll}
          className="mt-2 flex items-center gap-1.5 rounded-full border border-border px-3 py-1 text-xs font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground">
          {showAll ? (<><ChevronUp className="h-3.5 w-3.5" /> Weniger</>)
            : (<><ChevronDown className="h-3.5 w-3.5" /> Alle {turn.sources.length}</>)}
        </button>
      )}
      {showAll && (
        <div className="mt-2 space-y-1">
          {turn.sources.map((s) => (
            <div key={s.id} id={`${ankerPrefix}-alle-${s.id}`}
              className={cn(
                "group flex w-full items-baseline gap-2 rounded-lg px-2 py-1.5 transition-colors hover:bg-muted",
                flashId === s.id && "ring-2 ring-primary",
              )}>
              <button type="button" onClick={() => router.push(decisionHref(s.id))}
                className="flex min-w-0 flex-1 items-baseline gap-2 text-left">
                {idToNum.has(s.id) ? (
                  <span aria-hidden className="flex h-4 w-4 shrink-0 translate-y-0.5 items-center justify-center rounded-full bg-primary text-[9px] font-bold text-primary-foreground">
                    {idToNum.get(s.id)}
                  </span>
                ) : <span className="w-4 shrink-0" />}
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
          {nichtZitiert > 0 && (
            <p className="px-2 pt-1 text-[11px] text-muted-foreground/70">
              {nichtZitiert === 1 ? "Ein weiterer Treffer" : `${nichtZitiert} weitere Treffer`} — gefunden,
              aber in der Antwort nicht zitiert.
            </p>
          )}
        </div>
      )}
    </div>
  );
}

function PresseBlock({ presse }: { presse: PresseHinweis[] }) {
  return (
    <div className="rounded-xl border border-dashed border-border p-3">
      <p className="font-mono text-[10px] uppercase tracking-[0.12em] text-muted-foreground">
        Aktuelles von der Stadt <span className="text-muted-foreground/60">· extern</span>
      </p>
      <ul className="mt-1.5 space-y-1">
        {presse.map((p) => (
          <li key={p.url}>
            <a href={p.url} target="_blank" rel="noopener noreferrer"
              className="group flex items-baseline gap-2 rounded-lg px-1.5 py-1 text-sm transition-colors hover:bg-muted">
              <span className="min-w-0 flex-1 truncate text-[12.5px] group-hover:underline">{p.titel}</span>
              <span className="shrink-0 font-mono text-[10px] text-muted-foreground">{fmtDatumKurz(p.datum)}</span>
              <ExternalLink className="h-3 w-3 shrink-0 text-muted-foreground" aria-hidden />
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Task 16: Wortbeiträge aus den Sitzungsprotokollen — was im Rat GESAGT
 *  wurde (Reden, Anfragen mit Verwaltungsantwort, Einwohnerfragen, Zusagen),
 *  im Unterschied zu dem, was beschlossen wurde. */
function DebattenBlock({ debatten }: { debatten: DebattenHinweis[] }) {
  const artLabel: Record<string, string> = {
    rede: "Rede", anfrage: "Anfrage", einwohnerfrage: "Einwohnerfrage", zusage: "Zusage",
  };
  return (
    <div className="rounded-xl border border-dashed border-border p-3">
      <p className="font-mono text-[10px] uppercase tracking-[0.12em] text-muted-foreground">
        Aus den Ratsdebatten <span className="text-muted-foreground/60">· Protokolle</span>
      </p>
      <ul className="mt-1.5 space-y-2">
        {debatten.map((d, i) => (
          <li key={i} className="text-[12.5px] leading-snug">
            <p className="flex items-baseline gap-2">
              <span className="min-w-0 flex-1 truncate font-medium">
                {d.sprecher ?? "Ohne Namen"}{d.partei ? ` (${d.partei})` : ""}
                <span className="ml-1.5 font-normal text-muted-foreground">· {artLabel[d.art] ?? d.art}</span>
              </span>
              {d.datum && <span className="shrink-0 font-mono text-[10px] text-muted-foreground">{fmtDatumKurz(d.datum)}</span>}
            </p>
            <p className="mt-0.5 text-muted-foreground">{d.auszug}{d.auszug.length >= 220 ? "…" : ""}</p>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Teilen mit Substanz (Task 31): erstellt beim Klick einen Server-Snapshot
 *  von Frage + EXAKTER Antwort + zitierten Quellen und teilt dessen URL —
 *  der alte ?q=-Link ließ Empfänger die Frage neu ausführen und eine ANDERE
 *  Antwort sehen (Tims Befund). Das Token wird je Turn nur einmal erzeugt. */
function TeilenKnopf({ turn, zitierte }: { turn: Turn; zitierte: QaSource[] }) {
  const tokenRef = useRef<string | null>(null);
  const [laedt, setLaedt] = useState(false);
  const teilen = async () => {
    if (laedt) return;
    let token = tokenRef.current;
    if (!token) {
      setLaedt(true);
      try {
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

type ParteiMeinung = {
  partei: string; haltung?: "dafür" | "dagegen" | "offen" | "gewandelt";
  position: string; einig: boolean; hinweis: string | null;
  kernaussage: { text: string; sprecher: string | null; datum: string | null } | null;
  beitraege: number;
};

/** Haltungs-Badge: Wort statt Grafik (RG-05-Verbot von Stimm-Balken gilt
 *  weiter); „offen" bekommt kein Badge — Grau neben Grau wäre nur Rauschen. */
const HALTUNG_BADGE: Record<string, { label: string; cls: string }> = {
  "dafür": { label: "dafür", cls: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300" },
  "dagegen": { label: "dagegen", cls: "bg-rose-100 text-rose-800 dark:bg-rose-900/40 dark:text-rose-300" },
  "gewandelt": { label: "Haltung gewandelt", cls: "bg-sky-100 text-sky-800 dark:bg-sky-900/40 dark:text-sky-300" },
};

/** RG-09-Parteifarben (bewusst NICHT partyBrand aus decision-ui — das Artboard
 *  definiert eigene Dot-Farben). Gruppen (FDP/Volt, Für Oldenburg, IBO/LiVe)
 *  behalten ihr kombiniertes Label und bekommen den neutralen Dot. */
function parteiDot(label: string): { bg: string; ring: boolean } {
  const l = label.toLowerCase();
  if (l.includes("grün")) return { bg: "#3d8f29", ring: false };
  if (l.includes("linke")) return { bg: "#e6007e", ring: false };
  if (l.includes("spd")) return { bg: "#e3000f", ring: false };
  if (l.includes("cdu")) return { bg: "#1a1a1a", ring: false };
  if (l.includes("bsw")) return { bg: "#7d254f", ring: false };
  if (l.includes("afd")) return { bg: "#009ee0", ring: false };
  if (l === "fdp") return { bg: "#ffe000", ring: true }; // exakt — „FDP/Volt" ist eine Gruppe
  return { bg: "hsl(209 18% 65%)", ring: false };
}

/** Doppel-Fetches (Remount durch Kompaktzeile, Strict-Mode) kosten echte
 *  LLM-Calls — das Ergebnis je kondensierter Frage einmal festhalten. */
const parteiMeinungenCache = new Map<string, ParteiMeinung[]>();

function ParteienBaustein({ frage, onFrageStellen }: {
  frage: string; onFrageStellen?: (text: string) => void;
}) {
  const [parteien, setParteien] = useState<ParteiMeinung[] | null>(
    () => parteiMeinungenCache.get(frage) ?? null);
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
        if (aktiv) setParteien(sortiert);
      })
      // Fehler NICHT cachen: ein transienter 4xx/5xx soll den Baustein nur
      // für diesen Moment verstecken, nicht bis zum nächsten Voll-Reload.
      .catch(() => { if (aktiv) setParteien([]); });
    return () => { aktiv = false; };
  }, [frage]);

  if (parteien !== null && parteien.length < 2) return null; // dünne Lage: gar nicht

  const daten = [...new Set((parteien ?? []).map((p) => p.kernaussage?.datum).filter(Boolean))];
  return (
    <div className="rounded-xl border border-border bg-card p-3.5 shadow-sm print:break-inside-avoid">
      <div className="flex items-baseline justify-between gap-2">
        <p className="font-mono text-[10px] uppercase tracking-[0.12em] text-muted-foreground">
          Aus den Ratsdebatten
        </p>
        <p className="text-[10.5px] text-muted-foreground/70">
          {parteien === null ? "Positionen werden verdichtet …"
            : `${parteien.length} Fraktionen${daten.length === 1 ? ` · Sitzung ${daten[0]}` : ""}`}
        </p>
      </div>
      {parteien === null ? (
        <div aria-hidden className="mt-3 flex animate-pulse flex-col gap-3.5">
          {[34, 28, 40].map((w, i) => (
            <div key={i} className="flex gap-2.5">
              <span className="mt-1 h-2 w-2 shrink-0 rounded-full bg-muted" />
              <span className="flex flex-1 flex-col gap-1.5">
                <span className="h-2.5 rounded bg-muted" style={{ width: `${w}%` }} />
                <span className="h-2 w-[92%] rounded bg-muted/70" />
                {i !== 1 && <span className="h-2 w-[60%] rounded bg-muted/70" />}
              </span>
            </div>
          ))}
        </div>
      ) : (
        <>
          <div className="mt-2 flex flex-col divide-y divide-border/60">
            {parteien.map((p) => {
              const dot = parteiDot(p.partei);
              return (
                <div key={p.partei}
                  className="group relative -mx-1.5 flex gap-2.5 rounded-lg px-1.5 py-2.5 transition-colors lg:hover:bg-primary/5">
                  <span aria-hidden className="mt-[5px] h-2 w-2 shrink-0 rounded-full"
                    style={{ background: dot.bg, boxShadow: dot.ring ? "inset 0 0 0 1px rgba(0,0,0,0.15)" : undefined }} />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <p className="text-[12.5px] font-bold">{p.partei}</p>
                      {p.haltung && HALTUNG_BADGE[p.haltung] && (
                        <span className={cn("rounded-full px-2 py-px text-[10px] font-semibold",
                          HALTUNG_BADGE[p.haltung].cls)}>
                          {HALTUNG_BADGE[p.haltung].label}
                        </span>
                      )}
                      {/* Ehrlichkeit zur Datenbasis: aus wie vielen Wortbeiträgen
                          die Position verdichtet ist (Tims Befund 10.08.). */}
                      {p.beitraege > 0 && (
                        <span className="font-mono text-[10px] text-muted-foreground/70">
                          {p.beitraege === 1 ? "1 Beitrag" : `${p.beitraege} Beiträge`}
                        </span>
                      )}
                      {!p.einig && (
                        <span className="rounded-full bg-amber-100 px-2 py-px text-[10px] font-semibold text-amber-800 dark:bg-amber-900/40 dark:text-amber-300">
                          uneinheitlich
                        </span>
                      )}
                      {onFrageStellen && (
                        <button type="button"
                          onClick={() => onFrageStellen(`Was sagt ${p.partei} dazu im Detail?`)}
                          className="ml-auto inline-flex shrink-0 items-center gap-1 rounded-full px-1.5 py-0.5 text-[10.5px] text-muted-foreground transition-opacity hover:text-foreground lg:opacity-0 lg:group-hover:opacity-100 lg:focus:opacity-100"
                          title={`Was sagt ${p.partei} dazu im Detail?`}>
                          <MessageSquarePlus className="h-3 w-3" aria-hidden /> Dazu fragen
                        </button>
                      )}
                    </div>
                    <p className="mt-0.5 text-[12.5px] leading-relaxed text-foreground/90">
                      {p.position}{!p.einig && p.hinweis ? ` — ${p.hinweis}` : ""}
                    </p>
                    {p.kernaussage && (
                      <p className="mt-1 text-[12px] italic leading-snug text-muted-foreground">
                        {p.kernaussage.text}
                        <span className="font-mono text-[10px] not-italic text-muted-foreground/80">
                          {" "}— {p.kernaussage.sprecher ?? "ohne Namen"}{p.kernaussage.datum ? `, ${p.kernaussage.datum}` : ""}
                        </span>
                      </p>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
          <p className="mt-1.5 border-t border-dashed border-border pt-2 text-[10px] leading-normal text-muted-foreground/70">
            Verdichtet aus den Wortbeiträgen der Sitzungsprotokolle — Paraphrasen, keine wörtlichen Zitate.
          </p>
        </>
      )}
    </div>
  );
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
    return (
      <div className="rounded-xl border border-border bg-card p-3.5">
        <p className="font-mono text-[10px] uppercase tracking-[0.12em] text-muted-foreground">Aus den zitierten Beschlüssen</p>
        <p className="mt-1 flex items-baseline gap-1.5">
          <span className="text-[26px] font-bold tabular-nums tracking-tight sm:text-[28px]">{fmtEur(gross.amount_eur ?? 0)}</span>
          <FussnotenChip id={gross.id} idToNum={idToNum} onJump={onJump} />
        </p>
        <p className="max-w-full truncate text-[11.5px] text-muted-foreground">{gross.title}</p>
        {mitBetrag.length > 1 && (
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

/**
 * Antworttext mit klickbaren Fußnoten und SPARSAMEM Markdown: "[id]" →
 * nummerierte Chips; "**fett**" → <strong>; "- "-Zeilen → echte Liste;
 * Leerzeilen → Absätze. Streaming-fest: ein offenes "**" bleibt Text.
 */
function AnswerWithCitations({ text, idToNum, onJump }: {
  text: string; idToNum: Map<number, number>; onJump: (id: number) => void;
}) {
  const inline = (chunk: string, keyBase: string) => {
    const parts = chunk.split(CITE_SPLIT_RE);
    return parts.map((part, i) => {
      if (CITE_EXACT_RE.test(part)) {
        const ids = citationIds(part).filter((id) => idToNum.has(id));
        if (ids.length === 0) return null;
        return (
          <span key={`${keyBase}-${i}`} className="whitespace-nowrap">
            {ids.map((id) => (
              <button key={id} type="button" onClick={() => onJump(id)}
                title="Zur zitierten Quelle springen" aria-label={`Quelle ${idToNum.get(id)} anzeigen`}
                className="mx-0.5 inline-flex h-4 min-w-4 -translate-y-[3px] items-center justify-center rounded bg-primary/10 px-1 align-baseline text-[10px] font-semibold leading-none text-primary transition-colors hover:bg-primary/20">
                {idToNum.get(id)}
              </button>
            ))}
          </span>
        );
      }
      const seg = part.split(/(\*\*[^*]+\*\*)/g);
      return seg.map((s, j) =>
        /^\*\*[^*]+\*\*$/.test(s)
          ? <strong key={`${keyBase}-${i}-${j}`} className="font-semibold">{s.slice(2, -2)}</strong>
          : <span key={`${keyBase}-${i}-${j}`}>{s}</span>);
    });
  };

  const bloecke = text.split(/\n{2,}/);
  return (
    <>
      {bloecke.map((block, bi) => {
        // Drei Zeilenarten: „## "-Zwischenüberschrift (Task 32, lange
        // Antworten zu großen Themen), „- "-Listenzeile, Fließtext.
        const gruppen: { art: "kopf" | "liste" | "text"; zeilen: string[] }[] = [];
        for (const z of block.split("\n")) {
          const art = z.trim().startsWith("## ") ? "kopf" as const
            : z.trim().startsWith("- ") ? "liste" as const : "text" as const;
          const g = gruppen[gruppen.length - 1];
          if (g && g.art === art && art !== "kopf") g.zeilen.push(z);
          else gruppen.push({ art, zeilen: [z] });
        }
        return (
          <span key={bi} className="block [&:not(:first-child)]:mt-2.5">
            {gruppen.map((g, gi) =>
              g.art === "kopf" ? (
                <span key={gi} className="mt-3 block text-[13.5px] font-bold tracking-tight first:mt-0">
                  {inline(g.zeilen[0].trim().replace(/^##\s+/, ""), `${bi}-${gi}`)}
                </span>
              ) : g.art === "liste" ? (
                <ul key={gi} className="my-1.5 space-y-1 pl-1">
                  {g.zeilen.filter((z) => z.trim()).map((z, zi) => (
                    <li key={zi} className="flex gap-2">
                      <span aria-hidden className="mt-[9px] h-1 w-1 shrink-0 rounded-full bg-primary/60" />
                      <span className="min-w-0 whitespace-normal">{inline(z.trim().replace(/^-\s+/, ""), `${bi}-${gi}-${zi}`)}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <span key={gi}>{inline(g.zeilen.join("\n"), `${bi}-${gi}`)}</span>
              ))}
          </span>
        );
      })}
    </>
  );
}
