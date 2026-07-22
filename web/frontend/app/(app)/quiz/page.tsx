"use client";

import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { Search, Play, MapPin, Sparkles, Check, X, ChevronDown, ChevronUp, PencilLine, Zap, Flame, RotateCcw } from "lucide-react";
import { QuizAreas, QuizAreaEntry, QuizQuestion, QuizStats, QuizDaily, UserQuizQuestion } from "@/lib/types";
import { Button, Input, Spinner, EmptyState, toast } from "@/components/ui";
import { Mascot } from "@/components/mascot";
import { useFetch } from "@/lib/use-fetch";
import { api, qs } from "@/lib/api";
import { cn } from "@/lib/utils";
import { QuizPlay, CATEGORY_LABEL } from "@/components/quiz-play";
import { QuizMapPlay } from "@/components/quiz-map-play";
import { OwnQuestionsView } from "@/components/quiz-own";

type RoundKind = "normal" | "review" | "daily" | "own";

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

/** Auswahl eines gespeicherten Spiels in Gebiets-Chips + Kategorie-Label
 *  zerlegen (Hero-Karte „Weiterspielen"). Kennt auch „wahlbereich:"-Einträge
 *  aus alten gespeicherten Ständen. */
function selectionParts(s: LastSettings, catalog: QuizAreas): { areas: string[]; cat: string } {
  const wb = new Map(catalog.wahlbereiche.map((w) => [`wahlbereich:${w.key}`, w.label ?? `Wahlbereich ${w.key}`] as [string, string]));
  const th = new Map(catalog.themen.map((t) => [`thema:${t.key}`, t.label ?? t.key] as [string, string]));
  const areas = s.areas.map((a) =>
    a.startsWith("wahlbereich:") ? (wb.get(a) ?? a)
      : a.startsWith("thema:") ? (th.get(a) ?? a.slice(6))
        : a.startsWith("stadtteil:") ? a.slice(10) : a);
  return { areas, cat: s.cats.length ? s.cats.map((c) => CATEGORY_LABEL[c] ?? c).join(", ") : "Alle Kategorien" };
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

/** Hero-Karte (Design 14a): Primär-Tint, Lotti und der EINZIGE gefüllte Button.
 *  „Weiterspielen" zeigt die gemerkte Auswahl als Chips; ohne gemerkte Runde
 *  ist „Neues Spiel" die Hero-Karte (dann `sub` statt Chips). Auf dem Handy
 *  stapelt der Button volle Breite unter Lotti + Chips. */
function HeroCard({ title, parts, sub, buttonLabel, onStart, starting }: {
  title: string;
  parts?: { areas: string[]; cat: string };
  sub?: string;
  buttonLabel: string;
  onStart: () => void;
  starting: boolean;
}) {
  const shown = parts ? parts.areas.slice(0, 3) : [];
  const rest = parts ? parts.areas.length - shown.length : 0;
  return (
    <div className="rounded-2xl border border-primary/25 bg-gradient-to-br from-primary/[0.07] to-transparent p-4 shadow-sm sm:p-5">
      <div className="flex items-center gap-4">
        <Mascot decorative pose="point" bob className="h-14 w-14 shrink-0 sm:h-16 sm:w-16" />
        <div className="min-w-0 flex-1">
          <p className="font-display text-lg font-bold text-foreground">{title}</p>
          {parts ? (
            <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
              {shown.map((a) => (
                <span key={a} className="inline-flex rounded-full bg-primary/10 px-2.5 py-0.5 text-[11.5px] font-medium text-foreground">{a}</span>
              ))}
              {rest > 0 && (
                <span className="inline-flex rounded-full bg-primary/10 px-2.5 py-0.5 text-[11.5px] font-medium text-foreground">+ {rest} weitere</span>
              )}
              <span className="inline-flex rounded-full border border-border px-2.5 py-0.5 text-[11.5px] text-muted-foreground">{parts.cat}</span>
            </div>
          ) : (
            <p className="mt-1 text-sm text-muted-foreground">{sub}</p>
          )}
        </div>
        <Button className="hidden shrink-0 sm:inline-flex" onClick={onStart} disabled={starting}>
          <Play className="!size-4" /> {buttonLabel}
        </Button>
      </div>
      <Button className="mt-3 w-full sm:hidden" onClick={onStart} disabled={starting}>
        <Play className="!size-4" /> {buttonLabel}
      </Button>
    </div>
  );
}

type ModeTileData = {
  key: string;
  icon: React.ReactNode;
  iconClass: string;
  title: React.ReactNode;
  sub: string;
  badge?: React.ReactNode;
  onClick: () => void;
};

/** Modus-Kachel (Design 14a): ganze Fläche klickbar, Icon-Farbe unterscheidet
 *  den Modus, Sub-Text max. ein Satz. */
function ModeTile({ icon, iconClass, title, sub, badge, onClick }: Omit<ModeTileData, "key">) {
  return (
    <button type="button" onClick={onClick}
      className="card-interactive relative flex flex-col items-start gap-2.5 rounded-2xl border border-border bg-card p-4 text-left shadow-sm">
      {badge}
      <span className={cn("flex h-10 w-10 items-center justify-center rounded-xl", iconClass)}>{icon}</span>
      <span>
        <span className="block font-display text-[15px] font-bold text-foreground">{title}</span>
        <span className="mt-0.5 block text-xs leading-relaxed text-muted-foreground">{sub}</span>
      </span>
    </button>
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
  const { data: own } = useFetch<{ questions: UserQuizQuestion[] }>(`/quiz/own?v=${reloadKey}`);

  const [starting, setStarting] = useState(false);
  const [round, setRound] = useState<QuizQuestion[] | null>(null);
  const [kind, setKind] = useState<RoundKind>("normal");
  const [mapTargets, setMapTargets] = useState<string[] | null>(null);
  const [view, setView] = useState<"home" | "setup" | "own">("home");
  const [ownAutoNew, setOwnAutoNew] = useState(false);
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

  const startOwnPractice = useCallback(async () => {
    setStarting(true);
    try {
      const res = await api.get<{ questions: QuizQuestion[] }>("/quiz/own/round?n=10");
      if (!res.questions.length) { toast.info("Noch keine eigenen Fragen zum Üben."); return; }
      setKind("own");
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
    const title = kind === "daily" ? "Tägliche Challenge"
      : kind === "review" ? "Meine Fehler"
        : kind === "own" ? "Meine Fragen üben" : undefined;
    const onComplete = kind === "daily"
      ? (r: { correct: number; total: number; points: number }) => { void api.post("/quiz/daily/complete", r).catch(() => {}); }
      : undefined;
    return (
      <QuizPlay questions={round} title={title} onComplete={onComplete}
        practice={kind === "own"} answerPath={kind === "own" ? "/quiz/own/answer" : "/quiz/answer"}
        onExit={() => { setRound(null); setView(kind === "own" ? "own" : "home"); setReloadKey((k) => k + 1); }} />
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

  // ---- Eigene Fragen: verwalten + üben (RL-U14) -----------------------------
  if (view === "own") {
    return (
      <OwnQuestionsView questions={own?.questions ?? []} autoNew={ownAutoNew}
        starting={starting} onPractice={() => void startOwnPractice()}
        onBack={() => { setOwnAutoNew(false); setView("home"); }}
        reload={() => setReloadKey((k) => k + 1)} />
    );
  }

  // ---- Startseite (Design 14a): Stats im Kopf, Hero + vier Modi-Kacheln ------
  const answered = stats?.total.answered ?? 0;
  const totalQuote = stats && stats.total.answered
    ? Math.round((stats.total.correct / stats.total.answered) * 100) : 0;
  const ownCount = own?.questions.length ?? 0;
  const dailyOpen = Boolean(daily && !daily.done && daily.questions.length);

  // Modi-Kacheln. „Neues Spiel" ist nur dann eine Kachel, wenn „Weiterspielen"
  // bereits die Hero-Karte belegt — sonst wird es selbst zur Hero-Karte.
  const tiles: ModeTileData[] = [];
  if (last) {
    tiles.push({
      key: "neu", icon: <Sparkles className="h-[18px] w-[18px]" />, iconClass: "bg-primary/10 text-primary",
      title: "Neues Spiel", sub: "Gebiete & Themen frei wählen", onClick: () => setView("setup"),
    });
  }
  if (daily && (dailyOpen || daily.done)) {
    tiles.push({
      key: "daily", icon: <Zap className="h-[18px] w-[18px]" />,
      iconClass: "bg-amber-500/15 text-amber-700 dark:text-amber-500",
      title: "Tägliche Challenge", sub: "5 Fragen — jeden Tag neu",
      badge: dailyOpen ? (
        <span className="absolute right-3 top-3 rounded-full bg-signal px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-signal-foreground">Heute offen</span>
      ) : (
        <span className="absolute right-3 top-3 inline-flex items-center gap-1 rounded-full bg-emerald-500/15 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-emerald-700 dark:text-emerald-400">
          <Check className="h-2.5 w-2.5" strokeWidth={3} /> Erledigt
        </span>
      ),
      onClick: dailyOpen ? startDaily : () => toast.info("Heute schon erledigt — morgen gibt's neue Fragen."),
    });
  }
  tiles.push({
    key: "map", icon: <MapPin className="h-[18px] w-[18px]" />,
    iconClass: "bg-emerald-500/[0.12] text-emerald-700 dark:text-emerald-400",
    title: "Karten-Quiz", sub: "Stadtteile auf der Karte finden", onClick: () => void startMap(),
  });
  tiles.push({
    key: "own", icon: <PencilLine className="h-[18px] w-[18px]" />, iconClass: "bg-muted text-muted-foreground",
    title: <>Eigene Fragen{ownCount > 0 && <span className="font-medium text-muted-foreground"> · {ownCount}</span>}</>,
    sub: "Anlegen & üben — ohne Punkte",
    onClick: () => { setOwnAutoNew(ownCount === 0); setView("own"); },
  });
  const lgCols = tiles.length >= 4 ? "lg:grid-cols-4" : tiles.length === 3 ? "lg:grid-cols-3" : "lg:grid-cols-2";

  return (
    <div>
      {/* Kopf: Titel + Kernzahlen inline, rechts „Fehler üben" + Statistik-Link. */}
      <div className="flex flex-wrap items-end justify-between gap-x-4 gap-y-2">
        <div className="min-w-0">
          <h1 className="font-display text-2xl font-bold tracking-tight text-foreground sm:text-[30px] sm:leading-9">Oldenburg-Quiz</h1>
          {answered > 0 && stats ? (
            <div className="mt-1.5 flex flex-wrap items-center gap-x-3.5 gap-y-1 text-sm text-muted-foreground">
              <span><strong className="font-bold tabular-nums text-foreground">{stats.total.points}</strong> {stats.total.points === 1 ? "Punkt" : "Punkte"}</span>
              <span className="text-border" aria-hidden>·</span>
              <span><strong className="font-bold tabular-nums text-foreground">{totalQuote}&nbsp;%</strong> Trefferquote</span>
              {stats.streak > 0 && (
                <>
                  <span className="text-border" aria-hidden>·</span>
                  <span className="inline-flex items-center gap-1">
                    <Flame className="h-3.5 w-3.5 text-signal" />
                    <strong className="font-bold tabular-nums text-foreground">{stats.streak}</strong> Tage-Serie
                  </span>
                </>
              )}
            </div>
          ) : (
            <p className="mt-1 text-sm text-muted-foreground">Teste dein Wissen über deine Stadt — nach Wahlbereich, Stadtteil oder großem Thema.</p>
          )}
        </div>
        {answered > 0 && stats && (
          <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
            {stats.wrong > 0 && (
              <Button variant="secondary" size="sm" onClick={startReview} disabled={starting}>
                <RotateCcw className="!size-4" /> {stats.wrong} Fehler üben
              </Button>
            )}
            <Link href="/quiz/stats" className="whitespace-nowrap text-sm font-medium text-primary hover:underline">Alle Statistiken →</Link>
          </div>
        )}
      </div>

      {empty ? (
        <EmptyState mascot="sleep" title="Das Quiz wird gerade vorbereitet"
          hint="Die Fragen werden aus Wikipedia, der Stadt-Website und den Ratsdaten erzeugt. Schau bald wieder vorbei." />
      ) : (
        <div className="mt-5 space-y-3">
          {last ? (
            <HeroCard title="Weiterspielen" parts={selectionParts(last, catalog)} buttonLabel="Weiterspielen"
              starting={starting} onStart={() => startRound(last.areas, last.cats)} />
          ) : (
            <HeroCard title="Neues Spiel" sub="Gebiete, Themen und Kategorien frei wählen — alles auf einer Seite."
              buttonLabel="Neues Spiel" starting={starting} onStart={() => setView("setup")} />
          )}

          <div className={cn("grid grid-cols-2 gap-3", lgCols)}>
            {tiles.map(({ key, ...rest }) => <ModeTile key={key} {...rest} />)}
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
