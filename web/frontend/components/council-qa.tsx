"use client";

/**
 * Ratsgespräch — der KI-Frage-Tab als Gespräch (Design „Ratsgespräch", RG-01…08).
 *
 * Nutzerfragen rechts als stille Bubble, Antworten als ruhige Textblöcke in
 * voller Breite — keine Blasen-Optik für Inhalte, die aus Beschlüssen kommen.
 * Stack je Antwort-Turn (fix): Text → Fragetyp-Baustein → Quellen → Presse →
 * Fußzeile. Zitierte Quellen als kompakte Chips (Fußnoten [n] springen dorthin),
 * der Rest hinter „Alle N Quellen". Anschlussfragen laufen mit Gesprächskontext
 * (Paket A: /ask bekommt die letzten Runden als `verlauf`).
 */

import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { Sparkles, Send, Loader2, ChevronDown, ChevronUp, ArrowRight, Lightbulb, Plus,
  Square, CircleSlash, ExternalLink, ArrowDown, RotateCcw, MessageSquarePlus } from "lucide-react";
import { Mascot } from "@/components/mascot";
import { QaSource } from "@/lib/types";
import { apiUrl, authHeaders } from "@/lib/api";
import { entwurfAbholen, entwurfMelden } from "@/lib/draft";
import { Button, Input, toast } from "@/components/ui";
import { decisionHref } from "@/lib/routes";
import { ShareButton } from "@/components/share-button";
import { PrintButton } from "@/components/print-button";
import { cn } from "@/lib/utils";
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
};

const fmtDatum = (d?: string | null) =>
  d ? new Date(d).toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric" }) : "";

const fmtEur = (n: number) =>
  n >= 1_000_000 ? `${(n / 1_000_000).toLocaleString("de-DE", { maximumFractionDigits: 1 })} Mio. €`
    : `${Math.round(n).toLocaleString("de-DE")} €`;

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
          });
          else if (msg.type === "token") patchLast((t) => ({ antwort: t.antwort + (msg.text as string) }));
          else if (msg.type === "suggestions") patchLast({ followups: (msg.questions as string[]) ?? [] });
          else if (msg.type === "done") patchLast({ cited: (msg.cited as number[]) ?? [] });
          else if (msg.type === "error") throw new Error((msg.message as string) ?? "Frage fehlgeschlagen.");
        }
      }
    } catch (e) {
      if ((e as Error)?.name === "AbortError") return;
      // Fehler-Turn (RG ⑧): Die Frage ist nicht verloren — zurück ins Eingabefeld.
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

  const letzterFehler = turns.length > 0 ? turns[turns.length - 1].fehler : null;
  const showIntro = turns.length === 0;

  return (
    <div className="mx-auto mt-3 flex max-w-3xl flex-col">
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

      {/* Empty State — erste Nutzung (RG ①). */}
      {showIntro && (
        <div className="mt-4 flex flex-col items-center text-center">
          <Mascot pose="wave" bob className="h-20 w-20" />
          <h2 className="mt-3 text-xl font-bold tracking-tight">Frag den Stadtrat</h2>
          <p className="mt-1.5 max-w-md text-sm text-muted-foreground">
            Stell deine Frage in normalen Worten. Die Antwort entsteht aus den echten
            Ratsbeschlüssen — mit Fußnote zu jeder Quelle.
          </p>
          <p className="mt-5 font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground/70">
            Zum Beispiel
          </p>
          <div className="mt-2 flex w-full max-w-md flex-col gap-1.5">
            {EXAMPLES.map((ex) => (
              <button key={ex} type="button" onClick={() => void ask(ex)}
                className="flex items-center gap-2.5 rounded-[11px] border border-border bg-card px-3 py-2.5 text-left text-[13.5px] transition-[background-color,transform] duration-150 ease-out-strong hover:bg-muted active:scale-[0.99]">
                <Sparkles className="h-3.5 w-3.5 shrink-0 text-primary" aria-hidden />
                <span className="min-w-0 flex-1">{ex}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Gesprächsverlauf. */}
      <div className="flex flex-col gap-6 sm:gap-7">
        {turns.map((t, ti) => (
          <TurnView
            key={ti}
            turn={t}
            turnIdx={ti}
            istLetzter={ti === turns.length - 1}
            loading={loading && ti === turns.length - 1}
            step={loading && ti === turns.length - 1 ? step : null}
            word={word}
            onFollowup={(f) => void ask(f)}
            onRetry={() => { setTurns((ts) => ts.slice(0, -1)); void ask(t.frage); }}
            onEigeneFrage={() => inputRef.current?.focus()}
          />
        ))}
      </div>
      <div ref={endRef} />

      {/* „Nach unten"-Anker (RG-07). */}
      {showAnchor && (
        <button
          type="button"
          aria-label="Zum Gesprächsende springen"
          onClick={() => endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" })}
          className="fixed bottom-36 right-4 z-20 flex h-9 w-9 items-center justify-center rounded-full border border-border bg-card shadow-md transition-transform hover:scale-105 print:hidden sm:right-8"
        >
          <ArrowDown className="h-4 w-4 text-muted-foreground" aria-hidden />
        </button>
      )}

      {/* Eingabe-Dock: sticky, Verlaufs-Gradient darüber, Safe-Area (RG-07). */}
      <div className="sticky bottom-0 z-10 -mx-1 mt-4 bg-gradient-to-t from-background via-background to-transparent px-1 pb-[max(env(safe-area-inset-bottom),8px)] pt-5 print:hidden">
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
        <p className="mt-1.5 text-center text-[10px] text-muted-foreground/70">
          Keine personenbezogenen Daten eingeben — Fragen gehen an einen externen KI-Dienst.
        </p>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------------- */

function TurnView({ turn, turnIdx, istLetzter, loading, step, word, onFollowup, onRetry, onEigeneFrage }: {
  turn: Turn; turnIdx: number; istLetzter: boolean; loading: boolean;
  step: Step | null; word: string;
  onFollowup: (f: string) => void; onRetry: () => void; onEigeneFrage: () => void;
}) {
  const [showAll, setShowAll] = useState(false);
  const [flashId, setFlashId] = useState<number | null>(null);
  const [pendingJump, setPendingJump] = useState<number | null>(null);

  // [id]-Zitate → Fußnoten-Nummern in Reihenfolge des ersten Auftauchens.
  const idToNum = useMemo(() => {
    const valid = new Set(turn.sources.map((s) => s.id));
    const map = new Map<number, number>();
    for (const g of turn.antwort.matchAll(CITE_RE)) {
      for (const id of citationIds(g[0])) {
        if (valid.has(id) && !map.has(id)) map.set(id, map.size + 1);
      }
    }
    return map;
  }, [turn.antwort, turn.sources]);

  // Zitierte Chips in Fußnoten-Reihenfolge (RG-02); Rest im Ausklapper.
  const zitierte = useMemo(() => {
    const byId = new Map(turn.sources.map((s) => [s.id, s]));
    return [...idToNum.keys()].map((id) => byId.get(id)).filter(Boolean) as QaSource[];
  }, [turn.sources, idToNum]);

  const jump = (id: number) => {
    const anker = `qa-source-${turnIdx}-${id}`;
    if (!zitierte.some((s) => s.id === id) && !showAll) {
      setShowAll(true);
      setPendingJump(id);
    } else {
      document.getElementById(anker)?.scrollIntoView({ behavior: "smooth", block: "center" });
    }
    setFlashId(id);
    window.setTimeout(() => setFlashId((f) => (f === id ? null : f)), 1600);
  };
  useEffect(() => {
    if (pendingJump == null) return;
    document.getElementById(`qa-source-${turnIdx}-${pendingJump}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
    setPendingJump(null);
  }, [pendingJump, turnIdx]);

  const hatAntwort = turn.antwort.length > 0;
  const nichtsGefunden = !loading && hatAntwort && turn.sources.length === 0 && !turn.fehler;

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

      {/* Antwort-Stack: Text → Baustein → Quellen → Presse → Fußzeile (RG-01). */}
      {(hatAntwort || (!loading && !turn.fehler)) && hatAntwort && (
        <div aria-busy={loading} className="flex flex-col gap-3.5">
          {/* div statt p: die Antwort darf jetzt Listen (ul) enthalten. */}
          <div className="whitespace-pre-wrap text-[14.5px] leading-[1.7] text-foreground sm:leading-[1.75]">
            <AnswerWithCitations text={turn.antwort} idToNum={idToNum} onJump={jump} />
            {loading && step === "answer" && <span className="ml-0.5 inline-block h-4 w-1.5 animate-pulse bg-primary align-text-bottom" />}
          </div>

          {turn.abgebrochen && (
            <p role="status" className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <CircleSlash className="h-3.5 w-3.5 shrink-0" aria-hidden />
              Abgebrochen — die Antwort blieb unvollständig. Du kannst direkt weiterfragen.
            </p>
          )}

          {!loading && <Baustein turn={turn} idToNum={idToNum} onJump={jump} />}

          {turn.sources.length > 0 && (
            <QuellenBlock turn={turn} turnIdx={turnIdx} idToNum={idToNum} zitierte={zitierte}
              showAll={showAll} setShowAll={setShowAll} flashId={flashId} />
          )}

          {turn.presse.length > 0 && (
            <div className="rounded-xl border border-dashed border-border p-3">
              <p className="font-mono text-[10px] uppercase tracking-[0.12em] text-muted-foreground">
                Aktuelles von der Stadt
                <span className="ml-1.5 normal-case tracking-normal text-muted-foreground/70">· oldenburg.de — extern, keine Beschlüsse</span>
              </p>
              <ul className="mt-1.5 space-y-1">
                {turn.presse.map((p) => (
                  <li key={p.url}>
                    <a href={p.url} target="_blank" rel="noopener noreferrer"
                      className="group flex items-baseline gap-2 rounded-lg px-1.5 py-1 text-sm transition-colors hover:bg-muted">
                      <span className="min-w-0 flex-1 truncate text-[12.5px] group-hover:underline">{p.titel}</span>
                      <span className="shrink-0 text-[10.5px] text-muted-foreground">{fmtDatum(p.datum)}</span>
                      <ExternalLink className="h-3 w-3 shrink-0 text-muted-foreground" aria-hidden />
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          )}

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

          {/* Fußzeile je Turn: Teilen/Drucken + Disclaimer (RG-01). */}
          {!loading && (
            <div className="flex flex-wrap items-center gap-x-2 gap-y-1 border-t border-border/60 pt-2 print:hidden">
              <ShareButton
                path={`/council?tab=decisions&mode=fragen&q=${encodeURIComponent(turn.frage)}`}
                title={`Ratslotse: ${turn.frage}`}
              />
              <PrintButton />
              <span role="status" className="min-w-0 flex-1 text-right text-[10.5px] leading-snug text-muted-foreground/70">
                KI-Antwort aus den gefundenen Beschlüssen — kann unvollständig sein. Quellen prüfen.
              </span>
            </div>
          )}

          {/* Weiterfragen nur am jüngsten Turn (RG-07). */}
          {istLetzter && !loading && turn.followups.length > 0 && (
            <div>
              <p className="flex items-center gap-1.5">
                <span className="flex h-[20px] w-[20px] items-center justify-center rounded-[6px] bg-signal/[0.12] text-signal">
                  <Lightbulb className="h-3 w-3" aria-hidden />
                </span>
                <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-muted-foreground">Weiterfragen</span>
              </p>
              <div className="mt-2 flex flex-col gap-1.5">
                {turn.followups.slice(0, 3).map((s) => (
                  <button key={s} type="button" onClick={() => onFollowup(s)}
                    className="flex w-full items-center gap-2.5 rounded-[11px] border border-primary/30 bg-primary/[0.04] px-3 py-2.5 text-left transition-[color,background-color,transform] duration-150 ease-out-strong hover:bg-primary/[0.08] active:scale-[0.99]">
                    <span className="min-w-0 flex-1 text-[13px] text-foreground sm:text-[13.5px]">{s}</span>
                    <ArrowRight className="h-3.5 w-3.5 shrink-0 text-primary" aria-hidden />
                  </button>
                ))}
              </div>
              <div className="mt-2 flex items-center justify-between gap-2">
                <button type="button" onClick={onEigeneFrage}
                  className="inline-flex shrink-0 items-center gap-1.5 text-xs font-medium text-primary">
                  <Plus className="h-3 w-3 shrink-0" aria-hidden /> Eigene Frage
                </button>
                <span className="truncate text-[10.5px] text-muted-foreground/70">Anschlussfragen kennen den Gesprächsverlauf.</span>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/* --------------------------- Quellen (RG-02) ------------------------------ */

function QuellenBlock({ turn, turnIdx, idToNum, zitierte, showAll, setShowAll, flashId }: {
  turn: Turn; turnIdx: number; idToNum: Map<number, number>; zitierte: QaSource[];
  showAll: boolean; setShowAll: (fn: (v: boolean) => boolean) => void; flashId: number | null;
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
      {/* Zitierte als kompakte Chips in Fußnoten-Reihenfolge. */}
      {zitierte.length > 0 && (
        <div className="mt-1.5 flex flex-wrap gap-1.5">
          {zitierte.map((s) => (
            <button key={s.id} type="button" id={`qa-source-${turnIdx}-${s.id}`}
              onClick={() => router.push(decisionHref(s.id))}
              className={cn(
                "flex max-w-full items-center gap-2 rounded-[10px] border border-border bg-card px-2.5 py-[7px] text-left transition-[background-color,box-shadow] hover:bg-muted",
                flashId === s.id && "ring-2 ring-primary",
              )}>
              <span aria-hidden className="flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-primary text-[9px] font-bold text-primary-foreground">
                {idToNum.get(s.id)}
              </span>
              <span className="min-w-0">
                <span className="block max-w-[180px] truncate text-[12.5px] font-medium leading-tight sm:max-w-[260px]">{s.title}</span>
                <span className="block font-mono text-[9.5px] uppercase tracking-wide text-muted-foreground">
                  {turn.qtype === "partei" && s.factions && s.factions.length > 0 && (
                    <span className="mr-1 rounded-[4px] bg-signal/10 px-1 py-px text-[9px] font-bold normal-case tracking-normal text-signal">
                      {s.factions.join(" · ")}
                    </span>
                  )}
                  {s.committee} · {fmtDatum(s.session_date)}
                </span>
              </span>
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
      {/* Ausklapper: alle Treffer in Relevanz-Reihenfolge, Score hier (RG-02). */}
      {(nichtZitiert > 0 || showAll) && (
        <button type="button" onClick={() => setShowAll((v) => !v)} aria-expanded={showAll}
          className="mt-2 flex items-center gap-1.5 rounded-full border border-border px-3 py-1.5 text-xs font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground">
          {showAll ? (<><ChevronUp className="h-3.5 w-3.5" /> Weniger anzeigen</>)
            : (<><ChevronDown className="h-3.5 w-3.5" /> Alle {turn.sources.length} Quellen</>)}
        </button>
      )}
      {showAll && (
        <div className="mt-2 space-y-1">
          {turn.sources.map((s) => (
            <button key={s.id} type="button" id={`qa-source-${turnIdx}-${s.id}`}
              onClick={() => router.push(decisionHref(s.id))}
              className={cn(
                "flex w-full items-baseline gap-2 rounded-lg px-2 py-1.5 text-left transition-colors hover:bg-muted",
                flashId === s.id && "ring-2 ring-primary",
              )}>
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
              {typeof s.score === "number" && (
                <span className="shrink-0 font-mono text-[9.5px] text-muted-foreground/70">Score {Math.round(s.score * 100)}</span>
              )}
            </button>
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

/* ---------------------- Fragetyp-Bausteine (RG-03/04) --------------------- */

function Baustein({ turn, idToNum, onJump }: {
  turn: Turn; idToNum: Map<number, number>; onJump: (id: number) => void;
}) {
  const zitierteQuellen = useMemo(() => {
    const byId = new Map(turn.sources.map((s) => [s.id, s]));
    return [...idToNum.keys()].map((id) => byId.get(id)).filter(Boolean) as QaSource[];
  }, [turn.sources, idToNum]);

  if (turn.qtype === "verlauf" && zitierteQuellen.length >= 2) {
    const stationen = [...zitierteQuellen].sort((a, b) => (a.session_date ?? "").localeCompare(b.session_date ?? ""));
    return (
      <div className="rounded-xl border border-border bg-card p-3.5">
        <div className="flex flex-col">
          {stationen.map((s, i) => {
            const letzte = i === stationen.length - 1;
            return (
              <div key={s.id} className="relative flex gap-3 pb-3.5 last:pb-0">
                {/* Rail: Punkt + Linie. */}
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
    // Kopfzeile (RG-05): dominante Fraktion unter den zitierten Antragstellern.
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
 * Leerzeilen → Absätze. Bewusst kein voller Markdown-Renderer — das Prompt
 * erlaubt genau diese drei Formen, alles andere bleibt Text. Streaming-fest:
 * ein noch offenes "**" am Ende wird als Text gezeigt, nicht verschluckt.
 */
function AnswerWithCitations({ text, idToNum, onJump }: {
  text: string; idToNum: Map<number, number>; onJump: (id: number) => void;
}) {
  // Inline-Ebene: Zitat-Chips + **fett** in einem Textstück.
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
      // **fett** — nur geschlossene Paare; ein offenes ** (Streaming) bleibt Text.
      const seg = part.split(/(\*\*[^*]+\*\*)/g);
      return seg.map((s, j) =>
        /^\*\*[^*]+\*\*$/.test(s)
          ? <strong key={`${keyBase}-${i}-${j}`} className="font-semibold">{s.slice(2, -2)}</strong>
          : <span key={`${keyBase}-${i}-${j}`}>{s}</span>);
    });
  };

  // Block-Ebene: Absätze (Leerzeile); INNERHALB eines Blocks werden
  // aufeinanderfolgende "- "-Zeilen zur echten Liste gruppiert — auch nach
  // einer Kopfzeile („Weitere Maßnahmen umfassen: - … - …").
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
