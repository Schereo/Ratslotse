"use client";

import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Search, Play, MapPin, Landmark, Sparkles, History, ChevronLeft, ChevronRight } from "lucide-react";
import { QuizAreas, QuizQuestion, QuizStats, QuizDaily } from "@/lib/types";
import { PageHeader, Card, Button, Input, Spinner, EmptyState, toast } from "@/components/ui";
import { useFetch } from "@/lib/use-fetch";
import { api, qs } from "@/lib/api";
import { cn } from "@/lib/utils";
import { QuizPlay, CATEGORY_LABEL } from "@/components/quiz-play";
import { QuizStatsStrip, QuizDailyCard } from "@/components/quiz-progress";
import { QuizMapPlay, QuizMapCard } from "@/components/quiz-map-play";

type RoundKind = "normal" | "review" | "daily";

// Zuletzt gespielte Einstellungen (localStorage) → „Weiterspielen".
const LS_KEY = "quiz:lastSettings";
type LastSettings = { areas: string[]; cats: string[] };
function loadLast(): LastSettings | null {
  try {
    const o = JSON.parse(localStorage.getItem(LS_KEY) || "null");
    return o && Array.isArray(o.areas) && o.areas.length ? { areas: o.areas, cats: o.cats ?? [] } : null;
  } catch { return null; }
}
function saveLast(s: LastSettings) {
  try { localStorage.setItem(LS_KEY, JSON.stringify(s)); } catch { /* privater Modus o. ä. */ }
}

/** Menschliche Kurzbeschreibung der Auswahl fürs „Weiterspielen"-Kärtchen. */
function describeSelection(s: LastSettings, catalog: QuizAreas): string {
  const wb = new Map(catalog.wahlbereiche.map((w) => [`wahlbereich:${w.key}`, w.label ?? `Wahlbereich ${w.key}`] as [string, string]));
  const th = new Map(catalog.themen.map((t) => [`thema:${t.key}`, t.label ?? t.key] as [string, string]));
  const areas = s.areas.map((a) =>
    a.startsWith("wahlbereich:") ? (wb.get(a) ?? a)
      : a.startsWith("thema:") ? (th.get(a) ?? a.slice(6))
        : a.startsWith("stadtteil:") ? a.slice(10) : a);
  const catStr = s.cats.length ? s.cats.map((c) => CATEGORY_LABEL[c] ?? c).join(", ") : "Alle Kategorien";
  return `${areas.join(" · ")} · ${catStr}`;
}

const WIZARD_STEPS = ["Wahlbereich", "Themen", "Stadtteile", "Kategorien"] as const;

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

/** Startkachel (Weiterspielen / Neues Spiel). */
function ActionCard({ icon, title, sub, action, accent }: {
  icon: React.ReactNode; title: string; sub: string; action: React.ReactNode; accent?: boolean;
}) {
  return (
    <Card className={cn("flex flex-wrap items-center justify-between gap-3 p-4", accent && "border-primary/30 bg-primary/5")}>
      <div className="flex min-w-0 items-center gap-3">
        <div className={cn("flex h-10 w-10 shrink-0 items-center justify-center rounded-full",
          accent ? "bg-primary/15 text-primary" : "bg-muted text-muted-foreground")}>
          {icon}
        </div>
        <div className="min-w-0">
          <p className="font-semibold text-foreground">{title}</p>
          <p className="truncate text-sm text-muted-foreground">{sub}</p>
        </div>
      </div>
      <div className="shrink-0">{action}</div>
    </Card>
  );
}

function QuizInner() {
  // reloadKey bumpt nach jeder Runde die Datenpfade → Punkte/Fortschritt aktuell.
  const [reloadKey, setReloadKey] = useState(0);
  const params = useSearchParams();
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
  const [view, setView] = useState<"home" | "wizard">("home");
  const [step, setStep] = useState(0);
  const [last, setLast] = useState<LastSettings | null>(null);
  const [autoStarted, setAutoStarted] = useState(false);

  useEffect(() => { setLast(loadLast()); }, [reloadKey]);

  const themeLabels = useMemo(
    () => Object.fromEntries((data?.themen ?? []).map((t) => [t.key, t.label ?? t.key])),
    [data],
  );

  const toggle = (set: Set<string>, key: string, upd: (s: Set<string>) => void) => {
    const next = new Set(set);
    next.has(key) ? next.delete(key) : next.add(key);
    upd(next);
  };

  const startRound = useCallback(async (areaList: string[], catList: string[], roundKind: RoundKind = "normal") => {
    if (!areaList.length) return;
    setStarting(true);
    try {
      const res = await api.get<{ questions: QuizQuestion[] }>(
        "/quiz/round" + qs({ areas: areaList.join(","), categories: catList.join(","), n: 10 }));
      if (!res.questions.length) {
        toast.info("Für diese Auswahl gibt es (noch) keine offenen Fragen. Andere Gebiete probieren?");
        return;
      }
      if (roundKind === "normal") {
        const s = { areas: areaList, cats: catList };
        saveLast(s); setLast(s);
      }
      setKind(roundKind);
      setRound(res.questions);
    } catch {
      toast.error("Runde konnte nicht geladen werden.");
    } finally {
      setStarting(false);
    }
  }, []);

  const startReview = useCallback(async () => {
    setStarting(true);
    try {
      const res = await api.get<{ questions: QuizQuestion[] }>("/quiz/review?n=10");
      if (!res.questions.length) { toast.info("Keine offenen Fehler — stark!"); return; }
      setKind("review");
      setRound(res.questions);
    } catch {
      toast.error("Runde konnte nicht geladen werden.");
    } finally {
      setStarting(false);
    }
  }, []);

  const startMap = useCallback(async () => {
    setStarting(true);
    try {
      const res = await api.get<{ questions: { target: string }[] }>("/quiz/map-round?n=5");
      if (!res.questions.length) return;
      setMapTargets(res.questions.map((qq) => qq.target));
    } catch {
      toast.error("Karten-Quiz konnte nicht geladen werden.");
    } finally {
      setStarting(false);
    }
  }, []);

  // Auto-Start über Query (?review=1 / ?play=<area>) — von der Statistik-Seite.
  useEffect(() => {
    if (autoStarted || loading || !data) return;
    if (params.get("review")) { setAutoStarted(true); void startReview(); }
    else {
      const play = params.get("play");
      if (play) { setAutoStarted(true); void startRound([play], []); }
    }
  }, [autoStarted, loading, data, params, startReview, startRound]);

  if (loading) return <div className="py-10"><Spinner /></div>;

  if (mapTargets) {
    return <QuizMapPlay targets={mapTargets}
      onExit={() => { setMapTargets(null); setReloadKey((k) => k + 1); }} />;
  }

  if (round) {
    const title = kind === "daily" ? "Tägliche Challenge" : kind === "review" ? "Meine Fehler" : undefined;
    const onComplete = kind === "daily"
      ? (r: { correct: number; total: number; points: number }) => { void api.post("/quiz/daily/complete", r).catch(() => {}); }
      : undefined;
    return (
      <QuizPlay questions={round} title={title} onComplete={onComplete}
        onExit={() => { setRound(null); setView("home"); setReloadKey((k) => k + 1); }} />
    );
  }

  const catalog = data ?? { wahlbereiche: [], stadtteile: [], themen: [], categories: [] };
  const empty = !catalog.wahlbereiche.length && !catalog.stadtteile.length && !catalog.themen.length;
  const start = () => startRound([...sel], [...cats]);
  const startDaily = () => { if (daily && !daily.done && daily.questions.length) { setKind("daily"); setRound(daily.questions); } };

  const filteredStadtteile = (() => {
    const needle = q.trim().toLowerCase();
    return (catalog.stadtteile ?? []).filter((s) => !needle || s.key.toLowerCase().includes(needle));
  })();

  // ---- Wizard: Gebiete & Kategorien Schritt für Schritt ---------------------
  if (view === "wizard") {
    const openWizardStep = (i: number) => (
      i === 0 ? (
        catalog.wahlbereiche.length ? (
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {catalog.wahlbereiche.map((w) => {
              const key = `wahlbereich:${w.key}`;
              const active = sel.has(key);
              return (
                <button key={key} type="button" onClick={() => toggle(sel, key, setSel)}
                  className={cn("card-interactive rounded-xl border p-3 text-left", active ? "border-primary bg-primary/5" : "border-border")}>
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
        ) : <p className="text-sm text-muted-foreground">Keine Wahlbereiche verfügbar — einfach weiter.</p>
      ) : i === 1 ? (
        catalog.themen.length ? (
          <div className="flex flex-wrap gap-1.5">
            {catalog.themen.map((t) => {
              const key = `thema:${t.key}`;
              return <Chip key={key} active={sel.has(key)} onClick={() => toggle(sel, key, setSel)}>{t.label} · {t.questions}<Points n={t.points} /></Chip>;
            })}
          </div>
        ) : <p className="text-sm text-muted-foreground">Keine großen Themen verfügbar — einfach weiter.</p>
      ) : i === 2 ? (
        <>
          <div className="relative mb-3 max-w-sm">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input className="pl-9" placeholder="Stadtteil suchen…" value={q} onChange={(e) => setQ(e.target.value)} />
          </div>
          <div className="flex flex-wrap gap-1.5">
            {filteredStadtteile.map((s) => {
              const key = `stadtteil:${s.key}`;
              return <Chip key={key} active={sel.has(key)} onClick={() => toggle(sel, key, setSel)}>{s.key} · {s.questions}<Points n={s.points} /></Chip>;
            })}
          </div>
        </>
      ) : (
        <div className="flex flex-wrap gap-1.5">
          {catalog.categories.map((c) => (
            <Chip key={c} active={cats.has(c)} onClick={() => toggle(cats, c, setCats)}>{CATEGORY_LABEL[c] ?? c}</Chip>
          ))}
        </div>
      )
    );

    return (
      <div className="pb-28 md:pb-0">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Schritt {step + 1} von {WIZARD_STEPS.length}</p>
            <h1 className="mt-0.5 text-xl font-bold text-foreground">
              {WIZARD_STEPS[step]}{step < 3 ? " wählen" : ""} <span className="text-sm font-normal text-muted-foreground">(optional)</span>
            </h1>
          </div>
          <Button variant="ghost" size="sm" onClick={() => setView("home")}>Abbrechen</Button>
        </div>
        <div className="mt-3 flex gap-1.5">
          {WIZARD_STEPS.map((s, i) => <div key={s} className={cn("h-1 flex-1 rounded-full transition-colors", i <= step ? "bg-primary" : "bg-muted")} />)}
        </div>

        <p className="mt-4 text-sm text-muted-foreground">
          {step === 3 ? "Optional auf bestimmte Kategorien einschränken — sonst kommt alles dran." : "Mehrfachauswahl möglich. Leer lassen und weiter ist ok — du brauchst am Ende mindestens ein Gebiet."}
        </p>
        <div className="mt-3 min-h-[14rem]">{openWizardStep(step)}</div>

        <div className="fixed inset-x-4 bottom-[calc(env(safe-area-inset-bottom)+4.75rem)] z-30 rounded-xl border border-border bg-background/95 p-3 shadow-lg backdrop-blur md:sticky md:inset-x-auto md:bottom-4 md:mt-4 md:bg-background/90 md:shadow-none">
          <div className="flex items-center justify-between gap-3">
            <Button variant="secondary" onClick={() => (step === 0 ? setView("home") : setStep(step - 1))}>
              <ChevronLeft className="!size-4" /> {step === 0 ? "Abbrechen" : WIZARD_STEPS[step - 1]}
            </Button>
            <span className="hidden text-xs text-muted-foreground sm:block">
              {sel.size ? `${sel.size} Gebiet${sel.size === 1 ? "" : "e"}` : "Noch kein Gebiet"}
            </span>
            {step < WIZARD_STEPS.length - 1 ? (
              <Button onClick={() => setStep(step + 1)}>{WIZARD_STEPS[step + 1]} <ChevronRight className="!size-4" /></Button>
            ) : (
              <Button onClick={start} disabled={!sel.size || starting}>
                {starting ? "Lädt…" : <><Play className="!size-4" /> Quiz starten</>}
              </Button>
            )}
          </div>
        </div>
      </div>
    );
  }

  // ---- Startseite -----------------------------------------------------------
  return (
    <div>
      <PageHeader title="Oldenburg-Quiz" description="Teste dein Wissen über deine Stadt — nach Wahlbereich, Stadtteil oder großem Thema." />

      {empty ? (
        <EmptyState mascot="sleep" title="Das Quiz wird gerade vorbereitet"
          hint="Die Fragen werden aus Wikipedia, der Stadt-Website und den Ratsdaten erzeugt. Schau bald wieder vorbei." />
      ) : (
        <div className="mt-2 space-y-4">
          {stats && stats.total.answered > 0 && (
            <QuizStatsStrip stats={stats} onReview={startReview} />
          )}

          {last && (
            <ActionCard accent icon={<History className="h-5 w-5" />} title="Weiterspielen"
              sub={describeSelection(last, catalog)}
              action={<Button onClick={() => startRound(last.areas, last.cats)} disabled={starting}><Play className="!size-4" /> Weiterspielen</Button>} />
          )}

          <ActionCard icon={<Sparkles className="h-5 w-5" />} title="Neues Spiel"
            sub="Wahlbereich, Themen, Stadtteile und Kategorien Schritt für Schritt wählen."
            action={<Button variant={last ? "secondary" : "primary"} onClick={() => { setSel(new Set()); setCats(new Set()); setQ(""); setStep(0); setView("wizard"); }}>
              <Play className="!size-4" /> Neues Spiel
            </Button>} />

          {daily && <QuizDailyCard done={daily.done} count={daily.questions.length} onStart={startDaily} />}
          <QuizMapCard onStart={startMap} />
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
