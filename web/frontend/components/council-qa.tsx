"use client";

import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { Sparkles, Send, Loader2 } from "lucide-react";
import { Mascot } from "@/components/mascot";
import { QaSource } from "@/lib/types";
import { apiUrl, authHeaders } from "@/lib/api";
import { Button, Card, Input, toast } from "@/components/ui";
import { DecisionLinkCard } from "@/components/decision-ui";
import { cn } from "@/lib/utils";

const EXAMPLES = [
  "Was wurde zum Radverkehr beschlossen?",
  "Welche Entscheidungen gab es zum Klimaschutz?",
  "Was ist mit dem Wohnungsbau passiert?",
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

export function QaTab({ modeToggle }: { modeToggle?: ReactNode }) {
  const [q, setQ] = useState("");
  // Suchtext aus der URL übernehmen (Leerzustand der Suche reicht ihn als
  // ?q= weiter) — einmalig nach dem Mount, kein Hydration-Mismatch.
  const sp = useSearchParams();
  useEffect(() => {
    const urlQ = sp.get("q");
    if (urlQ) setQ((prev) => prev || urlQ);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const [loading, setLoading] = useState(false);
  const [step, setStep] = useState<Step | null>(null);
  const [answer, setAnswer] = useState("");
  const [sources, setSources] = useState<QaSource[]>([]);
  const [mode, setMode] = useState<string | null>(null);
  const [cited, setCited] = useState<number[]>([]);
  const [word, setWord] = useState(PLAYFUL[0]);
  // Kurzes Aufblitzen der Quelle, zu der eine Fußnote gerade gesprungen ist.
  const [flashId, setFlashId] = useState<number | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  // [id]-Zitate im Antworttext → Fußnoten-Nummern in Reihenfolge des ersten
  // Auftauchens. Nur IDs, die wirklich in den Quellen vorkommen.
  const idToNum = useMemo(() => {
    const valid = new Set(sources.map((s) => s.id));
    const map = new Map<number, number>();
    for (const g of answer.matchAll(/\[([\d,\s]+)\]/g)) {
      for (const n of g[1].match(/\d+/g) ?? []) {
        const id = Number(n);
        if (valid.has(id) && !map.has(id)) map.set(id, map.size + 1);
      }
    }
    return map;
  }, [answer, sources]);

  const jumpToSource = (id: number) => {
    document.getElementById(`qa-source-${id}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
    setFlashId(id);
    window.setTimeout(() => setFlashId((f) => (f === id ? null : f)), 1600);
  };

  // Rotate the playful word while loading.
  useEffect(() => {
    if (!loading) return;
    let i = 0;
    const id = setInterval(() => { i = (i + 1) % PLAYFUL.length; setWord(PLAYFUL[i]); }, 1400);
    return () => clearInterval(id);
  }, [loading]);

  useEffect(() => () => abortRef.current?.abort(), []);

  const ask = async (question: string) => {
    const text = question.trim();
    if (text.length < 4) return;
    // Erste Frage gestellt → der Glitzer-Lockruf auf dem KI-Frage-Umschalter
    // hat seinen Job getan (Segmented sparkle, siehe council/page.tsx).
    try { localStorage.setItem("ratslotse:qa-benutzt", "1"); } catch {}
    abortRef.current?.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    setQ(text);
    setLoading(true);
    setStep("expand");
    setAnswer("");
    setSources([]);
    setMode(null);
    setCited([]);

    try {
      // Absolute URL + bearer in the app (no Next proxy route there); same-origin
      // /api on web, where the route handler streams the SSE unbuffered.
      const res = await fetch(apiUrl("/council/ask"), {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({ question: text }),
        signal: ctrl.signal,
      });
      if (!res.ok || !res.body) {
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
          else if (msg.type === "sources") { setSources(msg.sources as QaSource[]); setMode((msg.mode as string) ?? null); }
          else if (msg.type === "token") setAnswer((a) => a + (msg.text as string));
          else if (msg.type === "done") setCited((msg.cited as number[]) ?? []);
          else if (msg.type === "error") throw new Error((msg.message as string) ?? "Frage fehlgeschlagen.");
        }
      }
    } catch (e) {
      if ((e as Error)?.name === "AbortError") return;
      toast.error(e instanceof Error ? e.message : "Frage fehlgeschlagen.");
    } finally {
      if (abortRef.current === ctrl) {
        setLoading(false);
        setStep(null);
        abortRef.current = null;
      }
    }
  };

  const showIntro = !loading && !answer && sources.length === 0;
  const citedSet = new Set(cited);

  return (
    <div className="mt-3 space-y-4">
      {/* Gleiche weiße Karte wie im Such-Modus (Umschalter oben drin) — beim
          Wechsel Suchen ↔ KI-Frage springt das Layout nicht mehr. */}
      <Card className="p-4">
        {modeToggle && <div className="mb-3">{modeToggle}</div>}
        <form onSubmit={(e) => { e.preventDefault(); ask(q); }} className="flex gap-2">
          <div className="relative flex-1">
            <Sparkles className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input data-search className="pl-9" placeholder="Frag den Stadtrat — z. B. „Was wurde zum Radverkehr beschlossen?“"
              value={q} onChange={(e) => setQ(e.target.value)} />
          </div>
          <Button type="submit" disabled={loading || q.trim().length < 4}>
            <Send /> Fragen
          </Button>
        </form>
        <p className="mt-2 text-xs text-muted-foreground/70">
          Bitte keine personenbezogenen oder sensiblen Daten eingeben — Anfragen werden zur Beantwortung an einen externen KI-Dienst übermittelt.
        </p>

        {showIntro && (
          <div className="mt-3 flex flex-wrap gap-2">
            {EXAMPLES.map((ex) => (
              <button key={ex} type="button" onClick={() => ask(ex)}
                className="rounded-full border border-border px-3 py-1.5 text-xs text-muted-foreground transition-colors hover:bg-muted hover:text-foreground">
                {ex}
              </button>
            ))}
          </div>
        )}
      </Card>

      {/* Live progress: Lotti sucht — real step + a rotating playful word. */}
      {loading && !answer && (
        <div role="status" className="flex items-center gap-3 rounded-xl border-2 border-dashed border-border px-4 py-3 text-sm text-muted-foreground">
          <Mascot pose="search" bob className="h-14 w-14 shrink-0" />
          <div>
            <span className="flex items-center gap-2 font-medium text-foreground">
              <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" />
              {step ? STEP_LABELS[step] : "Wird vorbereitet"}…
            </span>
            <span className="hidden text-xs text-muted-foreground/70 sm:inline">{word}</span>
          </div>
        </div>
      )}

      {/* Answer streams in as soon as the first token arrives — Lotti überbringt sie. */}
      {answer && (
        <div className="flex items-start gap-3">
          <Mascot pose={loading ? "search" : "point"} className="mt-1 hidden h-14 w-14 shrink-0 sm:block" />
          {/* aria-busy: Screenreader warten, bis der Stream fertig ist; die
              Fertig-Meldung unten (role=status) sagt dann aktiv Bescheid.
              Bubble-Radien nach 6a: 18 px, oben links 6 px (Sprechblase). */}
          <Card aria-busy={loading} className="flex-1 rounded-[18px] rounded-tl-[6px] p-4">
            <p className="whitespace-pre-wrap text-sm leading-relaxed text-foreground">
              <AnswerWithCitations text={answer} idToNum={idToNum} onJump={jumpToSource} />
              {loading && step === "answer" && <span className="ml-0.5 inline-block h-4 w-1.5 animate-pulse bg-primary align-text-bottom" />}
            </p>
          </Card>
        </div>
      )}

      {/* Sources appear the moment retrieval + rerank finish — before the answer. */}
      {sources.length > 0 && (
        <div>
          <p className="mb-2 text-xs font-medium text-muted-foreground">
            Gefundene Beschlüsse ({sources.length})
            {cited.length > 0 ? ` · ${cited.length} zitiert` : ""}
            {mode ? ` · ${MODE_LABEL[mode] ?? mode}` : ""}
          </p>
          <div className="space-y-2">
            {sources.map((s, i) => (
              <div
                key={s.id}
                id={`qa-source-${s.id}`}
                className={cn(
                  "animate-fade-up relative rounded-lg transition-shadow",
                  citedSet.has(s.id) && "ring-1 ring-primary/40",
                  flashId === s.id && "ring-2 ring-primary",
                )}
                /* RL-1104: Quellen staffeln sich nacheinander ein (max. 8 gestuft). */
                style={{ animationDelay: `${Math.min(i, 8) * 55}ms` }}
              >
                {/* Fußnoten-Nummer der Quelle — korrespondiert mit den Chips im Antworttext. */}
                {idToNum.has(s.id) && (
                  <span
                    aria-hidden
                    className="absolute -left-2 -top-2 z-10 flex h-5 w-5 items-center justify-center rounded-full bg-primary text-[10px] font-bold text-primary-foreground shadow-sm"
                  >
                    {idToNum.get(s.id)}
                  </span>
                )}
                <DecisionLinkCard id={s.id} title={s.title} committee={s.committee}
                  session_date={s.session_date} field={s.policy_field} sub={s.summary} score={s.score} />
              </div>
            ))}
          </div>
        </div>
      )}

      {answer && !loading && sources.length === 0 && (
        <div className="flex items-start gap-3 rounded-xl border border-border bg-muted/30 p-4">
          <Mascot pose="confused" decorative className="h-12 w-12 shrink-0" />
          <div className="min-w-0">
            <p className="text-sm text-foreground">
              Dazu habe ich keine passenden Beschlüsse gefunden — vielleicht hat der Rat dazu (noch) nichts entschieden.
            </p>
            <div className="mt-2.5 flex flex-wrap gap-2">
              <Link
                href={`/topics?neu=${encodeURIComponent(q.trim())}`}
                className="rounded-full border border-primary/30 bg-primary/5 px-3 py-1.5 text-xs font-medium text-primary transition-colors hover:bg-primary/10"
              >
                Als Thema anlegen — wir melden uns, sobald es Neues gibt
              </Link>
              <button
                type="button"
                onClick={() => document.querySelector<HTMLInputElement>("input[data-search]")?.focus()}
                className="rounded-full border border-border px-3 py-1.5 text-xs font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              >
                Frage umformulieren
              </button>
            </div>
          </div>
        </div>
      )}

      {answer && !loading && (
        <>
          <p role="status" className="sr-only">Antwort vollständig.</p>
          <p className="text-xs text-muted-foreground/70">
            Antwort von einer KI aus den gefundenen Beschlüssen erzeugt — kann unvollständig sein. Immer die Quellen prüfen.
          </p>
        </>
      )}
    </div>
  );
}

/**
 * Antworttext mit klickbaren Fußnoten: Das LLM zitiert Beschlüsse als "[id]" —
 * roh wären das kryptische Zahlen wie [4711]. Hier werden sie zu nummerierten
 * Chips (1, 2, …), die zur zitierten Quelle scrollen. IDs, die nicht in den
 * Quellen vorkommen, werden gar nicht erst angezeigt (Absicherung zusätzlich
 * zum Backend-Zitat-Resolver).
 */
function AnswerWithCitations({
  text,
  idToNum,
  onJump,
}: {
  text: string;
  idToNum: Map<number, number>;
  onJump: (id: number) => void;
}) {
  const parts = text.split(/(\[[\d,\s]+\])/g);
  return (
    <>
      {parts.map((part, i) => {
        const m = /^\[([\d,\s]+)\]$/.exec(part);
        if (!m) return <span key={i}>{part}</span>;
        const ids = (m[1].match(/\d+/g) ?? []).map(Number).filter((id) => idToNum.has(id));
        if (ids.length === 0) return null;
        return (
          <span key={i} className="whitespace-nowrap">
            {ids.map((id) => (
              <button
                key={id}
                type="button"
                onClick={() => onJump(id)}
                title="Zur zitierten Quelle springen"
                aria-label={`Quelle ${idToNum.get(id)} anzeigen`}
                className="mx-0.5 inline-flex h-4 min-w-4 -translate-y-[3px] items-center justify-center rounded bg-primary/10 px-1 align-baseline text-[10px] font-semibold leading-none text-primary transition-colors hover:bg-primary/20"
              >
                {idToNum.get(id)}
              </button>
            ))}
          </span>
        );
      })}
    </>
  );
}
