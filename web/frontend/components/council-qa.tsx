"use client";

import { useState } from "react";
import { Sparkles, Send } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { QaAnswer } from "@/lib/types";
import { Card, Input, Spinner, toast } from "@/components/ui";
import { DecisionLinkCard } from "@/components/decision-ui";

const EXAMPLES = [
  "Was wurde zum Radverkehr beschlossen?",
  "Welche Entscheidungen gab es zum Klimaschutz?",
  "Was ist mit dem Wohnungsbau passiert?",
  "Gab es Beschlüsse zu Kita-Plätzen?",
];

export function QaTab() {
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(false);
  const [res, setRes] = useState<QaAnswer | null>(null);

  const ask = async (question: string) => {
    const text = question.trim();
    if (text.length < 4) return;
    setQ(text);
    setLoading(true);
    setRes(null);
    try {
      setRes(await api.post<QaAnswer>("/council/ask", { question: text }));
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Frage fehlgeschlagen.");
    } finally {
      setLoading(false);
    }
  };

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

      {!res && !loading && (
        <div className="flex flex-wrap gap-2">
          {EXAMPLES.map((ex) => (
            <button key={ex} type="button" onClick={() => ask(ex)}
              className="rounded-full border border-border px-3 py-1.5 text-xs text-muted-foreground transition-colors hover:bg-muted hover:text-foreground">
              {ex}
            </button>
          ))}
        </div>
      )}

      {loading && <div className="py-8"><Spinner /></div>}

      {res && (
        <div className="space-y-3">
          <Card className="p-4">
            <p className="whitespace-pre-wrap text-sm leading-relaxed text-foreground">{res.answer}</p>
          </Card>
          {res.sources.length > 0 && (
            <div>
              <p className="mb-2 text-xs font-medium text-muted-foreground">
                Gefundene Beschlüsse ({res.sources.length}){res.mode ? ` · ${res.mode === "semantisch" ? "semantische Suche" : "Stichwortsuche"}` : ""}
              </p>
              <div className="space-y-2">
                {res.sources.map((s) => (
                  <DecisionLinkCard key={s.id} id={s.id} title={s.title} committee={s.committee}
                    session_date={s.session_date} field={s.policy_field} sub={s.summary} score={s.score} />
                ))}
              </div>
            </div>
          )}
          <p className="text-xs text-muted-foreground/70">
            Antwort von einer KI aus den gefundenen Beschlüssen erzeugt — kann unvollständig sein. Immer die Quellen prüfen.
          </p>
        </div>
      )}
    </div>
  );
}
