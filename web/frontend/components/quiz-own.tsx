"use client";

import { useMemo, useState } from "react";
import { Play, Plus, Pencil, Trash2, ChevronLeft, Sparkles } from "lucide-react";
import { UserQuizQuestion } from "@/lib/types";
import { Card, Button, Input, toast } from "@/components/ui";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { CATEGORY_LABEL } from "@/components/quiz-play";
import { WAHLBEREICH } from "@/lib/stadtteile";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

// Alle Stadtteilnamen (nicht nur die mit Katalog-Fragen) — für den Ort-Dropdown.
const ALL_STADTTEILE = Object.keys(WAHLBEREICH).sort((a, b) => a.localeCompare(b, "de"));

/** Eigene Quizfragen (RL-U14, Design 12a): Verwaltungsliste + Editor-Dialog.
 *  Privat je Konto; Üben läuft über die normale Spiel-Ansicht, gibt aber
 *  bewusst keine Punkte und zählt nicht für Abzeichen. */

const CATEGORIES = ["geschichte", "orte", "menschen", "ratspolitik", "schaetzen"];

const nf = new Intl.NumberFormat("de-DE");

function practiceLabel(q: UserQuizQuestion): string {
  if (!q.practiced) return "noch nie geübt";
  const quote = Math.round((q.correct_count / q.practiced) * 100);
  return `${q.practiced}× geübt, ${quote} %`;
}

const YEAR_SPAN = 50;  // ± Jahre um eine Jahreszahl (muss zu quiz.py passen)

/** Jahreszahl: Einheit Jahr/Jahre UND >= 100 (kleine Werte = Dauer). */
function isYear(unit: string, value: number): boolean {
  return ["jahr", "jahre"].includes(unit.trim().toLowerCase()) && Math.abs(value) >= 100;
}

/** Slider-Grenzen aus der Antwort ableiten (Spiegel von `_auto_range` im
 *  Backend): 0 bis ~2× der Zahl, auf zwei signifikante Stellen gerundet — bei
 *  Jahreszahlen stattdessen ein enges Fenster (±50 Jahre) um die Zahl. */
function autoRange(value: number, unit: string): [number, number] {
  if (isYear(unit, value)) {
    const v = Math.round(value);
    return [Math.max(0, v - YEAR_SPAN), v + YEAR_SPAN];
  }
  const raw = Math.max(Math.abs(value) * 2, 1);
  const step = Math.pow(10, Math.max(0, Math.floor(Math.log10(raw)) - 1));
  const hi = Math.round(raw / step) * step;
  return [0, Math.max(hi, Math.abs(value) + step)];
}

type Draft = {
  question: string;
  options: string[];
  correct_index: number;
  stadtteil: string;   // "" = stadtweit
  category: string;
  explanation: string;
  // Schätzfrage (category === "schaetzen"): Zahl statt Optionen.
  answerValue: string;
  unit: string;
  rangeManual: boolean;
  rangeMin: string;
  rangeMax: string;
};

const EMPTY_DRAFT: Draft = {
  question: "", options: ["", ""], correct_index: 0, stadtteil: "", category: "geschichte",
  explanation: "", answerValue: "", unit: "", rangeManual: false, rangeMin: "", rangeMax: "",
};

function draftOf(q: UserQuizQuestion): Draft {
  const estimate = q.qtype === "estimate";
  return { question: q.question, options: q.options.length ? [...q.options] : ["", ""],
           correct_index: q.correct_index, stadtteil: q.stadtteil ?? "", category: q.category,
           explanation: q.explanation ?? "",
           answerValue: estimate && q.answer_value != null ? String(q.answer_value) : "",
           unit: q.unit ?? "", rangeManual: false,
           rangeMin: q.range_min != null ? String(q.range_min) : "",
           rangeMax: q.range_max != null ? String(q.range_max) : "" };
}

/** Editor-Dialog nach 12a: Frage, 2–4 Antworten mit Korrekt-Radio, Ort und
 *  Kategorie, optionale Erklärung. */
function QuestionEditor({ open, initial, editId, onClose, onSaved }: {
  open: boolean;
  initial: Draft;
  editId: number | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [draft, setDraft] = useState<Draft>(initial);
  const [saving, setSaving] = useState(false);
  // Beim (Neu-)Öffnen den Stand des aufrufenden Eintrags übernehmen.
  const [seenInitial, setSeenInitial] = useState(initial);
  if (initial !== seenInitial) { setSeenInitial(initial); setDraft(initial); }

  const setOption = (i: number, v: string) => {
    const options = [...draft.options];
    options[i] = v;
    setDraft({ ...draft, options });
  };
  const removeOption = (i: number) => {
    const options = draft.options.filter((_, j) => j !== i);
    setDraft({ ...draft, options,
      correct_index: draft.correct_index === i ? 0 : draft.correct_index - (draft.correct_index > i ? 1 : 0) });
  };

  const isEstimate = draft.category === "schaetzen";
  const av = Number(draft.answerValue.replace(",", "."));
  const hasAv = draft.answerValue.trim() !== "" && Number.isFinite(av);
  const yearRange = hasAv && isYear(draft.unit, av);
  const [autoLo, autoHi] = hasAv ? autoRange(av, draft.unit) : [0, 0];
  const lo = draft.rangeManual ? Number(draft.rangeMin.replace(",", ".")) : autoLo;
  const hi = draft.rangeManual ? Number(draft.rangeMax.replace(",", ".")) : autoHi;

  const filled = draft.options.map((o) => o.trim());
  const valid = draft.question.trim().length >= 5 && (
    isEstimate
      ? hasAv && Number.isFinite(lo) && Number.isFinite(hi) && hi > lo && lo <= av && av <= hi
      : filled.filter(Boolean).length >= 2 && Boolean(filled[draft.correct_index])
  );

  async function save() {
    setSaving(true);
    try {
      const common = {
        question: draft.question.trim(),
        stadtteil: draft.stadtteil || null,
        category: draft.category,
        explanation: draft.explanation.trim() || null,
      };
      const body = isEstimate
        ? { ...common, options: [], correct_index: 0, answer_value: av,
            unit: draft.unit.trim() || null, range_min: lo, range_max: hi }
        // correct_index auf die gefilterte Liste abbilden (Leere davor fallen weg).
        : { ...common, options: filled.filter(Boolean),
            correct_index: filled.slice(0, draft.correct_index).filter(Boolean).length };
      if (editId != null) await api.put(`/quiz/own/${editId}`, body);
      else await api.post("/quiz/own", body);
      toast.success(editId != null ? "Frage aktualisiert." : "Frage gespeichert.");
      onSaved();
      onClose();
    } catch {
      toast.error("Speichern fehlgeschlagen.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent className="max-w-lg">
        <DialogTitle className="font-display text-lg font-bold">
          {editId != null ? "Frage bearbeiten" : "Neue Frage"}
        </DialogTitle>

        <label className="block text-sm font-medium text-foreground">
          Frage
          <Input className="mt-1.5" value={draft.question} maxLength={300}
            placeholder="Wie hieß der Oldenburger Hafenkran, der …?"
            onChange={(e) => setDraft({ ...draft, question: e.target.value })} />
        </label>

        {/* Kategorie zuerst — sie entscheidet, ob Optionen oder eine Zahl gefragt sind. */}
        <label className="block text-sm font-medium text-foreground">
          Kategorie
          <select value={draft.category} onChange={(e) => setDraft({ ...draft, category: e.target.value })}
            className="mt-1.5 h-10 w-full rounded-lg border border-input bg-card px-3 text-sm text-foreground">
            {CATEGORIES.map((c) => <option key={c} value={c}>{CATEGORY_LABEL[c] ?? c}</option>)}
          </select>
        </label>
        {isEstimate && (
          <p className="-mt-1 text-xs leading-relaxed text-muted-foreground">
            Bei Schätzfragen tippt man keine Optionen, sondern rät eine Zahl — je näher, desto mehr Punkte.
          </p>
        )}

        {isEstimate ? (
          <div className="rounded-xl border border-border bg-muted/30 p-4">
            <div className="grid grid-cols-[1.4fr_1fr] gap-3">
              <label className="block text-sm font-medium text-foreground">
                Richtige Zahl
                <Input type="number" inputMode="decimal" className="mt-1.5 tabular-nums" value={draft.answerValue}
                  placeholder="172000" onChange={(e) => setDraft({ ...draft, answerValue: e.target.value })} />
              </label>
              <label className="block text-sm font-medium text-foreground">
                Einheit <span className="font-normal text-muted-foreground">(opt.)</span>
                <Input className="mt-1.5" value={draft.unit} maxLength={40} placeholder="Einwohner"
                  onChange={(e) => setDraft({ ...draft, unit: e.target.value })} />
              </label>
            </div>
            <div className="mt-3">
              <div className="flex items-baseline justify-between gap-2">
                <span className="text-sm font-medium text-foreground">Slider-Bereich beim Raten</span>
                {!draft.rangeManual && (
                  <span className="inline-flex items-center gap-1 text-[11px] font-medium text-primary">
                    <Sparkles className="h-3 w-3" /> automatisch aus der Zahl
                  </span>
                )}
              </div>
              <div className="mt-1.5 grid grid-cols-[1fr_auto_1fr] items-center gap-2">
                {draft.rangeManual ? (
                  <>
                    <Input type="number" inputMode="decimal" className="tabular-nums" value={draft.rangeMin}
                      aria-label="Untergrenze" onChange={(e) => setDraft({ ...draft, rangeMin: e.target.value })} />
                    <span className="text-xs text-muted-foreground">bis</span>
                    <Input type="number" inputMode="decimal" className="tabular-nums" value={draft.rangeMax}
                      aria-label="Obergrenze" onChange={(e) => setDraft({ ...draft, rangeMax: e.target.value })} />
                  </>
                ) : (
                  <>
                    <div className="rounded-lg border border-border bg-card px-3 py-2 text-sm tabular-nums text-muted-foreground">{nf.format(lo)}</div>
                    <span className="text-xs text-muted-foreground">bis</span>
                    <div className="rounded-lg border border-border bg-card px-3 py-2 text-sm tabular-nums text-muted-foreground">{hasAv ? nf.format(hi) : "—"}</div>
                  </>
                )}
              </div>
              {/* Vorschau-Slider: Daumen mittig, rein illustrativ. */}
              <div className="relative mt-2.5 h-1.5 rounded-full bg-muted">
                <div className="absolute inset-y-0 left-0 w-1/2 rounded-full bg-primary/25" />
                <span className="absolute left-1/2 top-1/2 h-4 w-4 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-primary bg-background shadow-sm" />
              </div>
              <p className="mt-1.5 text-[11px] leading-relaxed text-muted-foreground">
                {draft.rangeManual ? (
                  <>Eigene Grenzen. <button type="button" onClick={() => setDraft({ ...draft, rangeManual: false })} className="font-medium text-primary hover:underline">Automatisch berechnen</button></>
                ) : (
                  <>{yearRange
                    ? "Fenster um die Jahreszahl (±50 Jahre) — die richtige Zahl liegt mittig. "
                    : "Wird aus der Zahl erzeugt (0 bis ~2×, glatt gerundet) — die richtige Zahl liegt so nie am Rand. "}
                  <button type="button" onClick={() => setDraft({ ...draft, rangeManual: true, rangeMin: String(lo), rangeMax: hasAv ? String(hi) : "" })} className="font-medium text-primary hover:underline">Bereich manuell anpassen</button></>
                )}
              </p>
            </div>
          </div>
        ) : (
          <div>
            <p className="text-sm font-medium text-foreground">
              Antworten <span className="font-normal text-muted-foreground">— richtige markieren</span>
            </p>
            <div className="mt-1.5 flex flex-col gap-2">
              {draft.options.map((opt, i) => (
                <div key={i} className="flex items-center gap-2.5">
                  <input type="radio" name="korrekt" checked={draft.correct_index === i}
                    onChange={() => setDraft({ ...draft, correct_index: i })}
                    aria-label={`Antwort ${i + 1} ist richtig`} className="h-4 w-4 shrink-0 accent-primary" />
                  <Input value={opt} maxLength={200} placeholder={`Antwort ${i + 1}`}
                    className={cn("flex-1", draft.correct_index === i && "border-primary bg-primary/5")}
                    onChange={(e) => setOption(i, e.target.value)} />
                  {draft.options.length > 2 && (
                    <button type="button" onClick={() => removeOption(i)} aria-label="Antwort entfernen"
                      className="rounded-md p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground">
                      <Trash2 className="h-4 w-4" />
                    </button>
                  )}
                </div>
              ))}
              {draft.options.length < 4 && (
                <button type="button" onClick={() => setDraft({ ...draft, options: [...draft.options, ""] })}
                  className="rounded-lg border border-dashed border-border px-3 py-2 text-left text-sm text-muted-foreground hover:text-foreground">
                  + Antwort (optional, 2–4)
                </button>
              )}
            </div>
          </div>
        )}

        <label className="block text-sm font-medium text-foreground">
          Ort <span className="font-normal text-muted-foreground">(optional)</span>
          <select value={draft.stadtteil} onChange={(e) => setDraft({ ...draft, stadtteil: e.target.value })}
            className="mt-1.5 h-10 w-full rounded-lg border border-input bg-card px-3 text-sm text-foreground">
            <option value="">Stadtweit</option>
            {ALL_STADTTEILE.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </label>

        <label className="block text-sm font-medium text-foreground">
          Erklärung <span className="font-normal text-muted-foreground">(optional — erscheint nach der Antwort)</span>
          <Input className="mt-1.5" value={draft.explanation} maxLength={500}
            placeholder="Warum ist die richtige Antwort richtig?"
            onChange={(e) => setDraft({ ...draft, explanation: e.target.value })} />
        </label>

        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>Abbrechen</Button>
          <Button onClick={save} disabled={!valid || saving}>
            {saving ? "Speichert…" : "Frage speichern"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

/** Verwaltung „Meine Fragen" (12a): Liste mit Übungs-Stand, Bearbeiten/Löschen,
 *  „+ Neue Frage" und Üben-Start. */
export function OwnQuestionsView({ questions, autoNew, starting, onPractice, onBack, reload }: {
  questions: UserQuizQuestion[];
  autoNew?: boolean;
  starting: boolean;
  onPractice: () => void;
  onBack: () => void;
  reload: () => void;
}) {
  const [editorOpen, setEditorOpen] = useState(Boolean(autoNew));
  const [editId, setEditId] = useState<number | null>(null);
  const initialDraft = useMemo(
    () => {
      const q = editId != null ? questions.find((x) => x.id === editId) : null;
      return q ? draftOf(q) : { ...EMPTY_DRAFT, options: ["", ""] };
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [editId, editorOpen],
  );

  async function remove(q: UserQuizQuestion) {
    if (!window.confirm(`Frage „${q.question.slice(0, 60)}…" wirklich löschen?`)) return;
    try {
      await api.del(`/quiz/own/${q.id}`);
      toast.success("Frage gelöscht.");
      reload();
    } catch {
      toast.error("Löschen fehlgeschlagen.");
    }
  }

  return (
    <div>
      <div className="flex flex-wrap items-center gap-3">
        <button type="button" onClick={onBack} aria-label="Zurück zum Quiz"
          className="flex h-9 w-9 items-center justify-center rounded-lg border border-border text-muted-foreground hover:text-foreground">
          <ChevronLeft className="h-4 w-4" />
        </button>
        <div className="min-w-0">
          <h1 className="font-display text-xl font-bold text-foreground">
            Meine Fragen <span className="text-sm font-medium text-muted-foreground">({questions.length})</span>
          </h1>
          <p className="text-sm text-muted-foreground">Nur für dich — eine Übungsrunde mischt 10 deiner Fragen.</p>
        </div>
        <div className="ml-auto flex shrink-0 gap-2">
          <Button variant="secondary" size="sm" onClick={() => { setEditId(null); setEditorOpen(true); }}>
            <Plus className="!size-4" /> Neue Frage
          </Button>
          {questions.length > 0 && (
            <Button variant="signal" size="sm" onClick={onPractice} disabled={starting}>
              <Play className="!size-4" /> Üben
            </Button>
          )}
        </div>
      </div>

      {questions.length === 0 ? (
        <Card className="mt-4 p-6 text-center text-sm text-muted-foreground">
          Noch keine eigenen Fragen — leg mit „Neue Frage" die erste an.
        </Card>
      ) : (
        <Card className="mt-4 overflow-hidden p-0">
          {questions.map((q, i) => (
            <div key={q.id}
              className={cn("flex items-center gap-2.5 px-4 py-3", i > 0 && "border-t border-border")}>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium leading-snug text-foreground">{q.question}</p>
                <p className="mt-0.5 text-xs text-muted-foreground">
                  {q.stadtteil ?? "Stadtweit"} · {CATEGORY_LABEL[q.category] ?? q.category} · {practiceLabel(q)}
                </p>
              </div>
              <button type="button" aria-label="Bearbeiten"
                onClick={() => { setEditId(q.id); setEditorOpen(true); }}
                className="rounded-lg p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground">
                <Pencil className="h-4 w-4" />
              </button>
              <button type="button" aria-label="Löschen" onClick={() => remove(q)}
                className="rounded-lg p-1.5 text-muted-foreground hover:bg-muted hover:text-red-600">
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          ))}
        </Card>
      )}

      <p className="mt-3 text-xs text-muted-foreground">
        Üben nutzt die normale Quiz-Ansicht — eigene Fragen geben keine Punkte und fließen
        nicht in Abzeichen ein (sonst könnte man sich Punkte selbst schreiben).
      </p>

      <QuestionEditor open={editorOpen} initial={initialDraft} editId={editId}
        onClose={() => { setEditorOpen(false); setEditId(null); }}
        onSaved={reload} />
    </div>
  );
}
