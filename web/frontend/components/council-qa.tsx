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
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { Sparkles, Send, Loader2, ChevronDown, ChevronRight, ChevronUp, ArrowRight, Plus,
  Square, CircleSlash, ExternalLink, ArrowDown, RotateCcw, MessageSquarePlus, ThumbsDown, ThumbsUp, X } from "lucide-react";
import { Mascot } from "@/components/mascot";
import { QaSource } from "@/lib/types";
import { apiUrl, authHeaders } from "@/lib/api";
import { entwurfAbholen, entwurfMelden } from "@/lib/draft";
import { Button, Input, toast } from "@/components/ui";
import { decisionHref } from "@/lib/routes";
import { ShareButton } from "@/components/share-button";
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

type Turn = {
  frage: string;
  antwort: string;
  qtype: string | null;
  mode: string | null;
  sources: QaSource[];
  presse: PresseHinweis[];
  cited: number[];
  followups: string[];
  fehler?: "netz" | "limit" | null;
  abgebrochen?: boolean;
  /** 5a/I-06: die vom Backend kondensierte Frage — der Kontext-Chip zeigt,
   *  worauf sich Anschlussfragen beziehen. */
  kontext?: string | null;
};

/** Beleg-Peek (5a/I-01): Ein Zitat-Chip öffnet erst die Kurzinfo der Quelle —
 *  Titel, Gremium, Kernaussage — statt sofort wegzuspringen. Von dort geht es
 *  in den Beschluss oder zur Quellenliste. Escape/Backdrop schließen. */
function BelegPeek({ quelle, nummer, onClose, onListe }: {
  quelle: QaSource; nummer: number | undefined; onClose: () => void; onListe: () => void;
}) {
  const router = useRouter();
  useEffect(() => {
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, [onClose]);
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center p-3 sm:items-center print:hidden"
      role="dialog" aria-modal="true" aria-label={`Quelle ${nummer ?? ""}`}>
      <button type="button" aria-label="Schließen" onClick={onClose}
        className="absolute inset-0 bg-foreground/25 backdrop-blur-[2px]" />
      <div className="relative w-full max-w-md animate-fade-up rounded-2xl border border-border bg-card p-4 shadow-xl">
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
    </div>
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
          <input value={grund} onChange={(e) => setGrund(e.target.value)} autoFocus
            placeholder="Was war falsch? (optional)" maxLength={500}
            className="h-6 w-40 min-w-0 rounded-md border border-border bg-card px-2 text-[11px] outline-none placeholder:text-muted-foreground/60 focus:border-primary" />
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
  useEffect(() => {
    const urlQ = sp.get("q");
    if (urlQ) setQ((prev) => prev || urlQ);
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
    setTurns((ts) => [...ts.map((t) => ({ ...t, followups: [] })), {
      frage: text, antwort: "", qtype: null, mode: null,
      sources: [], presse: [], cited: [], followups: [],
    }]);
    requestAnimationFrame(() => endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" }));

    try {
      const res = await fetch(apiUrl("/council/ask"), {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({ question: text, verlauf }),
        signal: ctrl.signal,
      });
      if (!res.ok || !res.body) {
        if (res.status === 429) {
          patchLast({ fehler: "limit" });
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
            kontext: (msg.frage as string) ?? null,
          });
          else if (msg.type === "token") patchLast((t) => ({ antwort: t.antwort + (msg.text as string) }));
          else if (msg.type === "suggestions") patchLast({ followups: (msg.questions as string[]) ?? [] });
          else if (msg.type === "done") patchLast({ cited: (msg.cited as number[]) ?? [] });
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
    inputRef.current?.focus();
  };

  const letzter = turns.length > 0 ? turns[turns.length - 1] : null;
  const letzterFehler = letzter?.fehler;
  const showIntro = turns.length === 0;
  const [nativeApp, setNativeApp] = useState(false);
  useEffect(() => { setNativeApp(isNativeApp()); }, []);

  // 5a/I-07: frische Beispiel-Anlässe aus den jüngsten Sitzungen — die
  // Klassiker bleiben, aber ein bis zwei Vorschläge zeigen, dass hier
  // aktuelles Material liegt. Fehlt der Endpoint, bleiben die Klassiker.
  const [frische, setFrische] = useState<string[]>([]);
  useEffect(() => {
    if (!showIntro) return;
    fetch(apiUrl("/council/qa-beispiele"), { credentials: "include", headers: authHeaders() })
      .then((r) => (r.ok ? r.json() : null))
      .then((b) => {
        const rows = (b?.sitzungen ?? []) as { committee: string; session_date: string }[];
        setFrische(rows.slice(0, 2).map((s) =>
          `Was hat ${derAusschuss(s.committee)} am ${fmtDatum(s.session_date)} beschlossen?`));
      })
      .catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showIntro]);
  const beispiele = [...frische, ...EXAMPLES].slice(0, 4);
  // Weiterfragen leben im Composer (Design 2②) — nur vom jüngsten Turn.
  const composerFollowups = !loading && letzter && !letzter.fehler ? letzter.followups.slice(0, 3) : [];

  return (
    <div className="mx-auto mt-3 lg:grid lg:max-w-[1220px] lg:grid-cols-[minmax(0,1fr)_320px] lg:items-start lg:gap-7">
      {/* Chat-Spalte: min-height, damit der Composer auch im Empty State unten
          klebt (Design 2①) — der Verlauf wächst darüber. In der nativen App
          steht mehr Chrome im Weg (Topbar, Tab-Umschalter, Bottom-Nav): mit dem
          Web-Wert rutschte der Composer unter die Falte (iOS-Test 09.08.).
          Erst nach dem Mount entscheiden — der Server rendert immer „Web". */}
      <div className={cn("flex flex-col", nativeApp ? "min-h-[calc(100dvh-380px)]" : "min-h-[calc(100dvh-230px)]")}>
        {(modeToggle || turns.length > 0) && (
          <div className="mb-1 flex items-center justify-between gap-2">
            {modeToggle ? <div>{modeToggle}</div> : <span />}
            {turns.length > 0 && (
              <button
                type="button"
                onClick={neuesGespraech}
                className="inline-flex shrink-0 items-center gap-1.5 rounded-[10px] border border-border bg-card px-2.5 py-1.5 text-xs font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground print:hidden"
              >
                <MessageSquarePlus className="h-3.5 w-3.5" aria-hidden />
                <span className="hidden sm:inline">Neues Gespräch</span>
              </button>
            )}
          </div>
        )}

        {/* Empty State — bodenständig: Beispiele direkt über dem Composer. */}
        {showIntro && (
          <div className="flex flex-1 flex-col items-center justify-end pb-5 text-center">
            <Mascot pose="wave" bob className="h-20 w-20" />
            <h2 className="mt-3 text-xl font-bold tracking-tight">Frag den Stadtrat</h2>
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
                key={ti}
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
              />
            ))}
          </div>
        )}
        <div ref={endRef} />

        {/* „Nach unten"-Anker (RG-07). */}
        {showAnchor && (
          <button
            type="button"
            aria-label="Zum Gesprächsende springen"
            onClick={() => endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" })}
            className="fixed bottom-40 right-4 z-20 flex h-9 w-9 items-center justify-center rounded-full border border-border bg-card shadow-md transition-transform hover:scale-105 print:hidden sm:right-8"
          >
            <ArrowDown className="h-4 w-4 text-muted-foreground" aria-hidden />
          </button>
        )}

        {/* Composer: fix unten, Weiterfragen-Chips direkt darüber (Design 2①②). */}
        <div className="sticky bottom-0 z-10 -mx-1 mt-4 bg-gradient-to-t from-background via-background to-transparent px-1 pb-[max(env(safe-area-inset-bottom),8px)] pt-4 print:hidden">
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
                Deine bisherigen Antworten bleiben stehen.
              </p>
            </div>
          ) : (
            <form onSubmit={(e) => { e.preventDefault(); void ask(q); }} className="flex gap-2">
              <div className="relative flex-1">
                <Sparkles className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input ref={inputRef} data-search enterKeyHint="send"
                  className="h-12 rounded-2xl pl-9"
                  placeholder={turns.length > 0 ? "Anschlussfrage stellen …" : "Frag den Stadtrat …"}
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

      {/* Belege-Spalte (Desktop, Design 2⑤): Quellen, Presse und Aktionen des
          jüngsten Turns — die Antwortspalte bleibt purer Text. */}
      <aside className="hidden lg:sticky lg:top-4 lg:block lg:pt-9 print:hidden">
        {letzter && letzter.antwort && !letzter.fehler && (
          <BelegeSpalte turn={letzter} flashId={flashId}
            onFlash={flash} loading={loading} />
        )}
      </aside>
    </div>
  );
}

/* ------------------------------------------------------------------------- */

function TurnView({ turn, turnIdx, istLetzter, loading, step, word, flashId, onJump, onRetry, onEigeneFrage, onDazuFragen }: {
  turn: Turn; turnIdx: number; istLetzter: boolean; loading: boolean;
  step: Step | null; word: string; flashId: number | null;
  onJump: (id: number) => void; onRetry: () => void; onEigeneFrage: () => void;
  onDazuFragen?: (titel: string) => void;
}) {
  const [showAll, setShowAll] = useState(false);
  // Ältere Turns beruhigen (Design 2⑤): Belege hinter der Kompaktzeile.
  const [aufgeklappt, setAufgeklappt] = useState(false);
  // 5a/I-01: welcher Zitat-Chip gerade sein Peek zeigt.
  const [peekId, setPeekId] = useState<number | null>(null);
  const idToNum = useIdToNum(turn);
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
              Die Verbindung zum KI-Dienst ist abgebrochen. Deine Frage ist nicht verloren —
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
            return q ? (
              <BelegPeek quelle={q} nummer={idToNum.get(peekId)}
                onClose={() => setPeekId(null)} onListe={() => onJump(peekId)} />
            ) : null;
          })()}

          {turn.abgebrochen && (
            <p role="status" className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <CircleSlash className="h-3.5 w-3.5 shrink-0" aria-hidden />
              Abgebrochen — die Antwort blieb unvollständig. Du kannst direkt weiterfragen.
            </p>
          )}

          {!loading && <Baustein turn={turn} idToNum={idToNum} onJump={(id) => setPeekId(id)} />}

          {/* Kompaktzeile älterer Turns (Design 2⑤). */}
          {!istLetzter && !aufgeklappt && (turn.sources.length > 0 || turn.presse.length > 0) && (
            <button type="button" onClick={() => setAufgeklappt(true)}
              className="flex w-fit items-center gap-1.5 rounded-full border border-border px-3 py-1 font-mono text-[10px] uppercase tracking-[0.1em] text-muted-foreground transition-colors hover:bg-muted hover:text-foreground">
              <ChevronDown className="h-3 w-3" aria-hidden />
              Quellen ({turn.sources.length}){turn.presse.length > 0 ? ` · Presse (${turn.presse.length})` : ""}
            </button>
          )}

          <div className={cn("flex flex-col gap-3.5", belegeInline)}>
            {turn.sources.length > 0 && (
              <QuellenBlock turn={turn} turnIdx={turnIdx} idToNum={idToNum} zitierte={zitierte}
                showAll={showAll} setShowAll={setShowAll} flashId={flashId} ankerPrefix={`qa-source-${turnIdx}`}
                onDazuFragen={onDazuFragen} />
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

          {/* Meta-Zeile: stille Icons + Disclaimer (Design 2③); auf Desktop
              übernimmt beim jüngsten Turn die Belege-Spalte die Aktionen. */}
          {!loading && (
            <div className={cn("flex items-center gap-1 border-t border-border/60 pt-1.5 print:hidden", istLetzter && "lg:hidden")}>
              <ShareButton iconOnly
                path={`/council?tab=decisions&mode=fragen&q=${encodeURIComponent(turn.frage)}`}
                title={`Ratslotse: ${turn.frage}`}
              />
              <PrintButton iconOnly />
              {turn.antwort && !turn.fehler && <FeedbackDaumen turn={turn} />}
              <span role="status" className="min-w-0 flex-1 text-right text-[10.5px] leading-snug text-muted-foreground/70">
                {/* 5a/I-02: ehrlich sagen, worauf die Antwort fußt. */}
                KI-Antwort{zitierte.length > 0 ? `, ${stuetztAuf(zitierte)}` : " aus den gefundenen Beschlüssen"} — kann unvollständig sein. Quellen prüfen.
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/* ------------------- Belege-Spalte (Desktop, Design 2⑤) ------------------- */

function BelegeSpalte({ turn, flashId, onFlash, loading, onDazuFragen }: {
  turn: Turn; flashId: number | null; onFlash: (id: number) => void; loading: boolean;
  onDazuFragen?: (titel: string) => void;
}) {
  const [showAll, setShowAll] = useState(false);
  const idToNum = useIdToNum(turn);
  const zitierte = useMemo(() => zitierteVon(turn, idToNum), [turn, idToNum]);
  if (turn.sources.length === 0 && turn.presse.length === 0) return null;
  return (
    <div className="flex max-h-[calc(100dvh-40px)] flex-col gap-3.5 overflow-y-auto pb-4 pr-0.5">
      {turn.sources.length > 0 && (
        <QuellenBlock turn={turn} turnIdx={-1} idToNum={idToNum} zitierte={zitierte}
          showAll={showAll} setShowAll={setShowAll} flashId={flashId} ankerPrefix="qa-col"
          onDazuFragen={onDazuFragen} />
      )}
      {turn.presse.length > 0 && <PresseBlock presse={turn.presse} />}
      {!loading && (
        <div className="flex items-center gap-1 border-t border-border/60 pt-1.5">
          <ShareButton iconOnly
            path={`/council?tab=decisions&mode=fragen&q=${encodeURIComponent(turn.frage)}`}
            title={`Ratslotse: ${turn.frage}`}
          />
          <PrintButton iconOnly />
          {turn.antwort && !turn.fehler && <FeedbackDaumen turn={turn} />}
          <span className="min-w-0 flex-1 text-right text-[10.5px] leading-snug text-muted-foreground/70">
            KI-Antwort{zitierte.length > 0 ? `, ${stuetztAuf(zitierte)}` : ""} — kann unvollständig sein. Quellen prüfen.
          </span>
        </div>
      )}
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

/* ---------------------- Fragetyp-Bausteine (RG-03/04) --------------------- */

function Baustein({ turn, idToNum, onJump }: {
  turn: Turn; idToNum: Map<number, number>; onJump: (id: number) => void;
}) {
  const zitierteQuellen = useMemo(() => zitierteVon(turn, idToNum), [turn, idToNum]);

  if (turn.qtype === "verlauf" && zitierteQuellen.length >= 2) {
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
        const gruppen: { liste: boolean; zeilen: string[] }[] = [];
        for (const z of block.split("\n")) {
          const liste = z.trim().startsWith("- ");
          const g = gruppen[gruppen.length - 1];
          if (g && g.liste === liste) g.zeilen.push(z);
          else gruppen.push({ liste, zeilen: [z] });
        }
        return (
          <span key={bi} className="block [&:not(:first-child)]:mt-2.5">
            {gruppen.map((g, gi) =>
              g.liste ? (
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
