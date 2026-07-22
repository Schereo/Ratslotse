"use client";

import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Search, Play, MapPin, Sparkles, History, Check, X, ChevronDown, ChevronUp } from "lucide-react";
import { QuizAreas, QuizAreaEntry, QuizQuestion, QuizStats, QuizDaily } from "@/lib/types";
import { PageHeader, Card, Button, Input, Spinner, EmptyState, toast } from "@/components/ui";
import { Mascot } from "@/components/mascot";
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

/** Menschliche Kurzbeschreibung der Auswahl fürs „Weiterspielen"-Kärtchen.
 *  Kennt auch „wahlbereich:"-Einträge aus alten gespeicherten Ständen. */
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

/** Abschnitts-Label im Setup (12a): Mono-Optik wie die Kicker der Karten. */
function SetupLabel({ children, hint }: { children: React.ReactNode; hint?: string }) {
  return (
    <p className="mt-5 text-[11px] font-bold uppercase tracking-wider text-muted-foreground">
      {children}
      {hint && <span className="ml-1.5 font-medium normal-case tracking-normal text-muted-foreground/80">{hint}</span>}
    </p>
  );
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

/** Setup in EINEM Schritt (RL-U13, Design 12a): Wahlbereich-Kacheln als
 *  Schnellwahl, die die Stadtteil-Chips setzen; Themen nach Ort gruppiert;
 *  Kategorien optional; Live-Zusammenfassung mit Startknopf. */
function QuizSetup({ catalog, starting, onStart, onCancel }: {
  catalog: QuizAreas;
  starting: boolean;
  onStart: (areas: string[], cats: string[]) => void;
  onCancel: () => void;
}) {
  const [wbSel, setWbSel] = useState<Set<string>>(new Set());
  const [stSel, setStSel] = useState<Set<string>>(new Set());
  const [thSel, setThSel] = useState<Set<string>>(new Set());
  const [cats, setCats] = useState<Set<string>>(new Set());
  const [searchOpen, setSearchOpen] = useState(false);
  const [q, setQ] = useState("");
  const [showOutside, setShowOutside] = useState(false);

  const stByName = useMemo(
    () => new Map(catalog.stadtteile.map((s) => [s.key, s] as [string, QuizAreaEntry])),
    [catalog],
  );

  // Schnellwahl: Kachel an = Stadtteile des Bereichs dazu; Kachel aus = nur die
  // Stadtteile entfernen, die kein anderer noch aktiver Bereich hält.
  const toggleWb = (w: QuizAreaEntry) => {
    const key = w.key;
    const members = (w.stadtteile ?? []).filter((n) => stByName.has(n));
    if (wbSel.has(key)) {
      const nextWb = new Set(wbSel); nextWb.delete(key);
      const held = new Set(
        catalog.wahlbereiche.filter((o) => nextWb.has(o.key)).flatMap((o) => o.stadtteile ?? []));
      const nextSt = new Set(stSel);
      for (const n of members) if (!held.has(n)) nextSt.delete(n);
      setWbSel(nextWb); setStSel(nextSt);
    } else {
      setWbSel(new Set(wbSel).add(key));
      const nextSt = new Set(stSel);
      for (const n of members) nextSt.add(n);
      setStSel(nextSt);
    }
  };

  const toggleIn = (set: Set<string>, key: string, upd: (s: Set<string>) => void) => {
    const next = new Set(set);
    next.has(key) ? next.delete(key) : next.add(key);
    upd(next);
  };

  // Stadtteil-Chips: gewählte zuerst (gefüllt, ✕), dann die stärksten übrigen;
  // der Rest steckt hinter dem Such-Chip.
  const selectedSt = catalog.stadtteile.filter((s) => stSel.has(s.key));
  const unselectedSt = catalog.stadtteile
    .filter((s) => !stSel.has(s.key))
    .sort((a, b) => b.questions - a.questions);
  const needle = q.trim().toLowerCase();
  const visibleUnselected = searchOpen && needle
    ? unselectedSt.filter((s) => s.key.toLowerCase().includes(needle))
    : unselectedSt.slice(0, searchOpen ? unselectedSt.length : 8);
  const hiddenCount = unselectedSt.length - (searchOpen ? 0 : Math.min(8, unselectedSt.length));

  // Themen nach Ortsbezug gruppieren (RL-U13): in der Auswahl / stadtweit /
  // außerhalb. Gewählte Themen bleiben immer sichtbar — fällt ihr Ort aus der
  // Auswahl, wandern sie mit Orts-Hinweis in die obere Zeile.
  const themen = catalog.themen;
  const inSelection = themen.filter((t) => t.stadtteil && stSel.has(t.stadtteil));
  const cityWide = themen.filter((t) => !t.stadtteil);
  const outside = themen.filter((t) => t.stadtteil && !stSel.has(t.stadtteil));
  const outsideUnselected = outside.filter((t) => !thSel.has(`thema:${t.key}`));
  const selectedOutside = outside.filter((t) => thSel.has(`thema:${t.key}`));

  const themeChip = (t: QuizAreaEntry, ortHint = false) => {
    const key = `thema:${t.key}`;
    const active = thSel.has(key);
    return (
      <button key={key} type="button" onClick={() => toggleIn(thSel, key, setThSel)}
        className={cn("inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium transition-colors",
          active ? "border-primary bg-primary/10 text-primary" : "border-border text-muted-foreground hover:text-foreground")}>
        {t.stadtteil && <MapPin className="h-3 w-3 shrink-0" />}
        {t.label ?? t.key} · {t.questions}
        {ortHint && t.stadtteil && <span className="text-[10px] opacity-70">({t.stadtteil})</span>}
        <Points n={t.points} />
      </button>
    );
  };

  const totalQuestions =
    selectedSt.reduce((sum, s) => sum + s.questions, 0) +
    themen.filter((t) => thSel.has(`thema:${t.key}`)).reduce((sum, t) => sum + t.questions, 0);
  const areaCount = stSel.size + thSel.size;
  const catStr = cats.size ? [...cats].map((c) => CATEGORY_LABEL[c] ?? c).join(", ") : null;
  const summary = areaCount
    ? `in ${stSel.size ? `${stSel.size} Stadtteil${stSel.size === 1 ? "" : "en"}` : ""}${stSel.size && thSel.size ? " + " : ""}${thSel.size ? `${thSel.size} Thema${thSel.size === 1 ? "" : "en"}` : ""}${catStr ? ` · ${catStr}` : ""}`
    : "Noch kein Gebiet gewählt — Schnellwahl oder Stadtteile antippen.";

  const start = () => onStart(
    [...stSel].map((s) => `stadtteil:${s}`).concat([...thSel]),
    [...cats],
  );

  return (
    <div className="pb-32 md:pb-0">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h1 className="font-display text-xl font-bold text-foreground">Neues Quiz</h1>
          <p className="mt-0.5 text-sm text-muted-foreground">
            Wähle, worüber Lotti dich fragen soll — alles optional außer mindestens einem Gebiet.
          </p>
        </div>
        <Button variant="ghost" size="sm" onClick={onCancel}>Abbrechen</Button>
      </div>

      {catalog.wahlbereiche.length > 0 && (
        <>
          <SetupLabel hint="— wählt seine Stadtteile vor">Schnellwahl · Wahlbereich</SetupLabel>
          <div className="mt-2 grid grid-cols-3 gap-2 sm:grid-cols-6">
            {catalog.wahlbereiche.map((w) => {
              const active = wbSel.has(w.key);
              return (
                <button key={w.key} type="button" onClick={() => toggleWb(w)}
                  aria-pressed={active} title={w.label}
                  className={cn("card-interactive relative rounded-xl border p-2.5 text-center transition-colors",
                    active ? "border-2 border-primary bg-primary/5" : "border-border bg-card")}>
                  {active && (
                    <span className="absolute -right-1.5 -top-1.5 flex h-[18px] w-[18px] items-center justify-center rounded-full bg-primary text-primary-foreground">
                      <Check className="h-2.5 w-2.5" strokeWidth={3.5} />
                    </span>
                  )}
                  <span className={cn("block font-display text-[15px] font-bold", active && "text-primary")}>WB {w.key}</span>
                  <span className={cn("block text-[10.5px]", active ? "text-primary/80" : "text-muted-foreground")}>
                    {w.questions} Fragen{w.points ? ` · ${w.points} P` : ""}
                  </span>
                </button>
              );
            })}
          </div>
        </>
      )}

      <SetupLabel hint={stSel.size ? `${stSel.size} ausgewählt${wbSel.size ? " — aus der Schnellwahl, frei anpassbar" : ""}` : undefined}>
        Stadtteile
      </SetupLabel>
      <div className="mt-2 flex flex-wrap items-center gap-1.5">
        {selectedSt.map((s) => (
          <button key={s.key} type="button" onClick={() => toggleIn(stSel, s.key, setStSel)}
            aria-label={`${s.key} abwählen`}
            className="inline-flex items-center gap-1.5 rounded-full border border-primary bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground transition-opacity hover:opacity-90">
            {s.key} <X className="h-3 w-3" />
          </button>
        ))}
        {visibleUnselected.map((s) => (
          <Chip key={s.key} active={false} onClick={() => toggleIn(stSel, s.key, setStSel)}>
            {s.key} · {s.questions}<Points n={s.points} />
          </Chip>
        ))}
        {searchOpen ? (
          <div className="relative">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
            <Input autoFocus className="h-8 w-44 rounded-full pl-8 text-xs" placeholder="Stadtteil suchen…"
              value={q} onChange={(e) => setQ(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Escape") { setSearchOpen(false); setQ(""); } }} />
          </div>
        ) : hiddenCount > 0 && (
          <button type="button" onClick={() => setSearchOpen(true)}
            className="inline-flex items-center gap-1.5 rounded-full border border-dashed border-border px-3 py-1.5 text-xs text-muted-foreground transition-colors hover:text-foreground">
            <Search className="h-3 w-3" /> Stadtteil suchen — {hiddenCount} weitere
          </button>
        )}
      </div>

      {themen.length > 0 && (
        <>
          {(inSelection.length > 0 || selectedOutside.length > 0) && (
            <>
              <SetupLabel hint="— liegen in den gewählten Stadtteilen">Themen in deiner Auswahl</SetupLabel>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {inSelection.map((t) => themeChip(t))}
                {selectedOutside.map((t) => themeChip(t, true))}
              </div>
            </>
          )}
          {cityWide.length > 0 && (
            <>
              <SetupLabel>Stadtweite Themen</SetupLabel>
              <div className="mt-2 flex flex-wrap gap-1.5">{cityWide.map((t) => themeChip(t))}</div>
            </>
          )}
          {outsideUnselected.length > 0 && (
            <div className="mt-3">
              <button type="button" onClick={() => setShowOutside((v) => !v)}
                className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline">
                {outsideUnselected.length} {outsideUnselected.length === 1 ? "Thema" : "Themen"} außerhalb deiner Auswahl {showOutside ? "ausblenden" : "anzeigen"}
                {showOutside ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
              </button>
              {showOutside && (
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {outsideUnselected.map((t) => themeChip(t, true))}
                </div>
              )}
            </div>
          )}
        </>
      )}

      {catalog.categories.length > 0 && (
        <>
          <SetupLabel hint="(optional — sonst kommt alles dran)">Kategorien</SetupLabel>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {catalog.categories.map((c) => (
              <Chip key={c} active={cats.has(c)} onClick={() => toggleIn(cats, c, setCats)}>{CATEGORY_LABEL[c] ?? c}</Chip>
            ))}
          </div>
        </>
      )}

      {/* Live-Zusammenfassung + Start — mobil als schwebende Leiste. */}
      <div className="fixed inset-x-4 bottom-[calc(env(safe-area-inset-bottom)+4.75rem)] z-30 rounded-xl border border-border bg-background/95 p-3 shadow-lg backdrop-blur md:sticky md:inset-x-auto md:bottom-4 md:mt-6 md:border-t md:bg-background/90 md:shadow-none">
        <div className="flex items-center gap-3">
          <Mascot decorative pose="point" className="hidden h-11 w-11 shrink-0 sm:block" />
          <p className="min-w-0 flex-1 text-sm text-muted-foreground">
            {areaCount ? (
              <><strong className="font-semibold text-foreground">{totalQuestions} Fragen</strong> {summary}</>
            ) : summary}
          </p>
          <Button onClick={start} disabled={!areaCount || starting} className="shrink-0">
            {starting ? "Lädt…" : <><Play className="!size-4" /> Quiz starten</>}
          </Button>
        </div>
      </div>
    </div>
  );
}

function QuizInner() {
  // reloadKey bumpt nach jeder Runde die Datenpfade → Punkte/Fortschritt aktuell.
  const [reloadKey, setReloadKey] = useState(0);
  const params = useSearchParams();
  const { data, loading } = useFetch<QuizAreas>(`/quiz/areas?v=${reloadKey}`);
  const { data: stats } = useFetch<QuizStats>(`/quiz/stats?v=${reloadKey}`);
  const { data: daily } = useFetch<QuizDaily>(`/quiz/daily?v=${reloadKey}`);

  const [starting, setStarting] = useState(false);
  const [round, setRound] = useState<QuizQuestion[] | null>(null);
  const [kind, setKind] = useState<RoundKind>("normal");
  const [mapTargets, setMapTargets] = useState<string[] | null>(null);
  const [view, setView] = useState<"home" | "setup">("home");
  const [last, setLast] = useState<LastSettings | null>(null);
  const [autoStarted, setAutoStarted] = useState(false);

  useEffect(() => { setLast(loadLast()); }, [reloadKey]);

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
  const startDaily = () => { if (daily && !daily.done && daily.questions.length) { setKind("daily"); setRound(daily.questions); } };

  // ---- Setup: alles auf einer Seite (RL-U13) --------------------------------
  if (view === "setup") {
    return (
      <QuizSetup catalog={catalog} starting={starting}
        onStart={(areas, cats) => void startRound(areas, cats)}
        onCancel={() => setView("home")} />
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
            sub="Wahlbereich als Schnellwahl, Stadtteile, Themen und Kategorien — alles auf einer Seite."
            action={<Button variant={last ? "secondary" : "primary"} onClick={() => setView("setup")}>
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
