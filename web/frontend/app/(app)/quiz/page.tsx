"use client";

import { Suspense, useMemo, useState } from "react";
import { Search, Play, MapPin, Landmark, Sparkles } from "lucide-react";
import { QuizAreas, QuizQuestion, QuizStats, QuizDaily } from "@/lib/types";
import { PageHeader, Card, Button, Input, Spinner, EmptyState, toast } from "@/components/ui";
import { useFetch } from "@/lib/use-fetch";
import { api, qs } from "@/lib/api";
import { cn } from "@/lib/utils";
import { QuizPlay, CATEGORY_LABEL } from "@/components/quiz-play";
import { QuizProgress, QuizDailyCard } from "@/components/quiz-progress";
import { QuizMapPlay, QuizMapCard } from "@/components/quiz-map-play";

type RoundKind = "normal" | "review" | "daily";

function Chip({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button type="button" onClick={onClick}
      className={cn("inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium transition-colors",
        active ? "border-primary bg-primary/10 text-primary" : "border-border text-muted-foreground hover:text-foreground")}>
      {children}
    </button>
  );
}

function Points({ n }: { n: number }) {
  if (!n) return null;
  return <span className="ml-1 rounded bg-primary/10 px-1 text-[10px] font-semibold tabular-nums text-primary">{n} P</span>;
}

function QuizInner() {
  // reloadKey bumpt nach jeder gespielten Runde die Datenpfade → Punkte &
  // Fortschritt aktualisieren sich beim Zurückkehren zur Auswahl.
  const [reloadKey, setReloadKey] = useState(0);
  const { data, loading } = useFetch<QuizAreas>(`/quiz/areas?v=${reloadKey}`);
  const { data: stats } = useFetch<QuizStats>(`/quiz/stats?v=${reloadKey}`);
  const { data: daily } = useFetch<QuizDaily>(`/quiz/daily?v=${reloadKey}`);
  const [sel, setSel] = useState<Set<string>>(new Set());
  const [cats, setCats] = useState<Set<string>>(new Set());
  const [q, setQ] = useState("");
  const [starting, setStarting] = useState(false);
  const [round, setRound] = useState<QuizQuestion[] | null>(null);
  const [kind, setKind] = useState<RoundKind>("normal");
  const [mapTargets, setMapTargets] = useState<string[] | null>(null);

  const themeLabels = useMemo(
    () => Object.fromEntries((data?.themen ?? []).map((t) => [t.key, t.label ?? t.key])),
    [data],
  );

  const toggle = (set: Set<string>, key: string, upd: (s: Set<string>) => void) => {
    const next = new Set(set);
    next.has(key) ? next.delete(key) : next.add(key);
    upd(next);
  };

  const filteredStadtteile = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return (data?.stadtteile ?? []).filter((s) => !needle || s.key.toLowerCase().includes(needle));
  }, [data, q]);

  if (loading) return <div className="py-10"><Spinner /></div>;
  const catalog = data ?? { wahlbereiche: [], stadtteile: [], themen: [], categories: [] };
  const empty = !catalog.wahlbereiche.length && !catalog.stadtteile.length && !catalog.themen.length;

  if (mapTargets) {
    return <QuizMapPlay targets={mapTargets}
      onExit={() => { setMapTargets(null); setReloadKey((k) => k + 1); }} />;
  }

  if (round) {
    // Nach der Runde: zurück zur Auswahl UND Fortschritt/Punkte neu laden.
    const title = kind === "daily" ? "Tägliche Challenge" : kind === "review" ? "Meine Fehler" : undefined;
    const onComplete = kind === "daily"
      ? (r: { correct: number; total: number; points: number }) => {
          void api.post("/quiz/daily/complete", r).catch(() => {});
        }
      : undefined;
    return (
      <QuizPlay questions={round} title={title} onComplete={onComplete}
        onExit={() => { setRound(null); setReloadKey((k) => k + 1); }} />
    );
  }

  async function startRound(areaList: string[], catList: string[], roundKind: RoundKind = "normal") {
    if (!areaList.length) return;
    setStarting(true);
    try {
      const res = await api.get<{ questions: QuizQuestion[] }>(
        "/quiz/round" + qs({ areas: areaList.join(","), categories: catList.join(","), n: 10 }));
      if (!res.questions.length) {
        toast.info("Für diese Auswahl gibt es (noch) keine offenen Fragen. Andere Gebiete probieren?");
        return;
      }
      setKind(roundKind);
      setRound(res.questions);
    } catch {
      toast.error("Runde konnte nicht geladen werden.");
    } finally {
      setStarting(false);
    }
  }
  const start = () => startRound([...sel], [...cats]);

  async function startReview() {
    setStarting(true);
    try {
      const res = await api.get<{ questions: QuizQuestion[] }>("/quiz/review?n=10");
      if (!res.questions.length) {
        toast.info("Keine offenen Fehler — stark!");
        return;
      }
      setKind("review");
      setRound(res.questions);
    } catch {
      toast.error("Runde konnte nicht geladen werden.");
    } finally {
      setStarting(false);
    }
  }

  function startDaily() {
    if (!daily || daily.done || !daily.questions.length) return;
    setKind("daily");
    setRound(daily.questions);
  }

  async function startMap() {
    setStarting(true);
    try {
      const res = await api.get<{ questions: { target: string }[] }>("/quiz/map-round?n=5");
      if (!res.questions.length) return;
      setMapTargets(res.questions.map((q) => q.target));
    } catch {
      toast.error("Karten-Quiz konnte nicht geladen werden.");
    } finally {
      setStarting(false);
    }
  }

  return (
    <div>
      <PageHeader title="Oldenburg-Quiz" description="Teste dein Wissen über deine Stadt — nach Wahlbereich, Stadtteil oder großem Thema." />

      {empty ? (
        <EmptyState mascot="sleep" title="Das Quiz wird gerade vorbereitet"
          hint="Die Fragen werden aus Wikipedia, der Stadt-Website und den Ratsdaten erzeugt. Schau bald wieder vorbei." />
      ) : (
        <div className="mt-2 space-y-6 pb-28 md:pb-0">
          {daily && (
            <QuizDailyCard done={daily.done} count={daily.questions.length} onStart={startDaily} />
          )}
          <QuizMapCard onStart={startMap} />

          {stats && stats.total.answered > 0 && (
            <QuizProgress stats={stats} themeLabels={themeLabels}
              onPractice={(area) => startRound([area], [])} onReview={startReview} />
          )}

          {catalog.wahlbereiche.length > 0 && (
            <section>
              <h2 className="mb-2 flex items-center gap-1.5 text-sm font-semibold text-muted-foreground">
                <Landmark className="h-4 w-4" /> Wahlbereiche
              </h2>
              <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                {catalog.wahlbereiche.map((w) => {
                  const key = `wahlbereich:${w.key}`;
                  const active = sel.has(key);
                  return (
                    <button key={key} type="button" onClick={() => toggle(sel, key, setSel)}
                      className={cn("card-interactive rounded-xl border p-3 text-left",
                        active ? "border-primary bg-primary/5" : "border-border")}>
                      <div className="flex items-center justify-between">
                        <span className="font-medium text-foreground">{w.label}</span>
                        {active && <Sparkles className="h-4 w-4 text-primary" />}
                      </div>
                      <p className="mt-0.5 truncate text-xs text-muted-foreground">{w.stadtteile?.join(", ")}</p>
                      <p className="mt-1 text-xs text-muted-foreground">{w.questions} Fragen<Points n={w.points} /></p>
                    </button>
                  );
                })}
              </div>
            </section>
          )}

          {catalog.themen.length > 0 && (
            <section>
              <h2 className="mb-2 flex items-center gap-1.5 text-sm font-semibold text-muted-foreground">
                <Sparkles className="h-4 w-4" /> Große Themen
              </h2>
              <div className="flex flex-wrap gap-1.5">
                {catalog.themen.map((t) => {
                  const key = `thema:${t.key}`;
                  return (
                    <Chip key={key} active={sel.has(key)} onClick={() => toggle(sel, key, setSel)}>
                      {t.label} · {t.questions}<Points n={t.points} />
                    </Chip>
                  );
                })}
              </div>
            </section>
          )}

          {catalog.stadtteile.length > 0 && (
            <section>
              <h2 className="mb-2 flex items-center gap-1.5 text-sm font-semibold text-muted-foreground">
                <MapPin className="h-4 w-4" /> Stadtteile
              </h2>
              <div className="relative mb-2 max-w-sm">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input className="pl-9" placeholder="Stadtteil suchen…" value={q} onChange={(e) => setQ(e.target.value)} />
              </div>
              <div className="flex flex-wrap gap-1.5">
                {filteredStadtteile.map((s) => {
                  const key = `stadtteil:${s.key}`;
                  return (
                    <Chip key={key} active={sel.has(key)} onClick={() => toggle(sel, key, setSel)}>
                      {s.key} · {s.questions}<Points n={s.points} />
                    </Chip>
                  );
                })}
              </div>
            </section>
          )}

          <section>
            <h2 className="mb-2 text-sm font-semibold text-muted-foreground">Kategorien (optional)</h2>
            <div className="flex flex-wrap gap-1.5">
              {catalog.categories.map((c) => (
                <Chip key={c} active={cats.has(c)} onClick={() => toggle(cats, c, setCats)}>
                  {CATEGORY_LABEL[c] ?? c}
                </Chip>
              ))}
            </div>
          </section>
        </div>
      )}

      {/* Start-Leiste: mobil fixiert oberhalb der Tab-Bar (bottom-Offset =
          Nav-Höhe + Safe-Area), damit sie immer erreichbar ist und nicht mit
          der Navigation kollidiert; auf Desktop klebt sie am unteren Rand des
          Scroll-Bereichs. Der pb-28 am Inhalt oben hält Platz frei. */}
      {!empty && (
        <div className="fixed inset-x-4 bottom-[calc(env(safe-area-inset-bottom)+4.75rem)] z-30 rounded-xl border border-border bg-background/95 p-3 shadow-lg backdrop-blur md:sticky md:inset-x-auto md:bottom-4 md:mt-4 md:bg-background/90 md:shadow-none">
          <div className="flex items-center justify-between gap-3">
            <span className="text-sm text-muted-foreground">
              {sel.size ? `${sel.size} Gebiet${sel.size === 1 ? "" : "e"} gewählt` : "Wähle mindestens ein Gebiet"}
            </span>
            <Button onClick={start} disabled={!sel.size || starting}>
              {starting ? "Lädt…" : <><Play className="!size-4" /> Quiz starten</>}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

export default function QuizPage() {
  return (
    <Suspense fallback={<div className="py-10"><Spinner /></div>}>
      <QuizInner />
    </Suspense>
  );
}
