"use client";

import { useEffect, useRef, useState } from "react";
import { Sparkles, Send, Loader2 } from "lucide-react";
import { Mascot } from "@/components/mascot";
import { QaSource } from "@/lib/types";
import { apiUrl, authHeaders } from "@/lib/api";
import { Card, Input, toast } from "@/components/ui";
import { DecisionLinkCard } from "@/components/decision-ui";

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

export function QaTab() {
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(false);
  const [step, setStep] = useState<Step | null>(null);
  const [answer, setAnswer] = useState("");
  const [sources, setSources] = useState<QaSource[]>([]);
  const [mode, setMode] = useState<string | null>(null);
  const [cited, setCited] = useState<number[]>([]);
  const [word, setWord] = useState(PLAYFUL[0]);
  const abortRef = useRef<AbortController | null>(null);

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
    <div className="mt-4 space-y-4">
      <form onSubmit={(e) => { e.preventDefault(); ask(q); }} className="flex gap-2">
        <div className="relative flex-1">
          <Sparkles className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input className="pl-9" placeholder="Frag den Stadtrat — z. B. „Was wurde zum Radverkehr beschlossen?“"
            value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        <button type="submit" disabled={loading || q.trim().length < 4}
          className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-4 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-50">
          <Send className="h-4 w-4" /> Fragen
        </button>
      </form>
      <p className="-mt-2 text-xs text-muted-foreground/70">
        Bitte keine personenbezogenen oder sensiblen Daten eingeben — Anfragen werden zur Beantwortung an einen externen KI-Dienst übermittelt.
      </p>

      {showIntro && (
        <div className="flex flex-wrap gap-2">
          {EXAMPLES.map((ex) => (
            <button key={ex} type="button" onClick={() => ask(ex)}
              className="rounded-full border border-border px-3 py-1.5 text-xs text-muted-foreground transition-colors hover:bg-muted hover:text-foreground">
              {ex}
            </button>
          ))}
        </div>
      )}

      {/* Live progress: Lotti sucht — real step + a rotating playful word. */}
      {loading && !answer && (
        <div className="flex items-center gap-3 text-sm text-muted-foreground">
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
          <Mascot pose={loading ? "search" : "point"} className="mt-1 hidden h-12 w-12 shrink-0 sm:block" />
          <Card className="flex-1 rounded-2xl rounded-tl-sm p-4">
            <p className="whitespace-pre-wrap text-sm leading-relaxed text-foreground">
              {answer}
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
            {sources.map((s) => (
              <div key={s.id} className={citedSet.has(s.id) ? "rounded-lg ring-1 ring-primary/40" : ""}>
                <DecisionLinkCard id={s.id} title={s.title} committee={s.committee}
                  session_date={s.session_date} field={s.policy_field} sub={s.summary} score={s.score} />
              </div>
            ))}
          </div>
        </div>
      )}

      {answer && !loading && (
        <p className="text-xs text-muted-foreground/70">
          Antwort von einer KI aus den gefundenen Beschlüssen erzeugt — kann unvollständig sein. Immer die Quellen prüfen.
        </p>
      )}
    </div>
  );
}
