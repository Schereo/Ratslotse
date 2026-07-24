"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Bell, Check, Landmark, Loader2, Plus, Sparkles, X } from "lucide-react";
import { api } from "@/lib/api";
import { isNativeApp } from "@/lib/platform";
import { cn } from "@/lib/utils";
import { Button, Input } from "@/components/ui";
import { Mascot, type MascotPose } from "@/components/mascot";
import { useMascotTheme } from "@/components/seasonal-mascot";
import { committeeExplains, committeeRank, shortCommittee } from "@/lib/committees";
import { useAuth } from "@/lib/auth";

/** Design 26a — geführtes Onboarding: einrichten statt nur vorstellen.
 *
 *  Die drei Intro-Karten (RL-1103) erzählten, was die App kann, und ließen
 *  einen dann auf einem leeren „Heute" stehen. Hier richtet man stattdessen
 *  direkt ein, wovon die App lebt: Ausschüsse, Themen, Mitteilungen.
 *
 *  Zwei Grundsätze, die den Ablauf bestimmen:
 *  - **Jeder Schritt ist überspringbar.** Niemand wird zu einer Eingabe
 *    gezwungen; die „Erste Schritte"-Leiste auf „Heute" bleibt das Auffangnetz.
 *  - **Abbruch merkt sich den Schritt.** Wer die App mittendrin schließt, macht
 *    beim nächsten Start dort weiter, statt von vorn zu beginnen.
 */

const DONE_KEY = "ratslotse.onboarding.done";
const STEP_KEY = "ratslotse.onboarding.step";
/** Muss zum Schlüssel in push-primer.tsx passen: Schritt 3 IST der Primer
 *  (26a zieht ihn nach vorn). Ohne das Setzen fragt die Karte auf „Heute"
 *  unmittelbar danach ein zweites Mal — im Simulator genau so beobachtet. */
const PUSH_SNOOZE_KEY = "ratslotse.push-primer.snoozed-until";
const PUSH_SNOOZE_DAYS = 7;
/** Der alte First-Run-Schlüssel: Wer die Intro-Karten schon gesehen hat, ist
 *  kein Erstnutzer mehr und wird nicht nachträglich durchs Onboarding geschickt. */
const LEGACY_INTRO_KEY = "ratslotse.intro.done";

type Step = 0 | 1 | 2 | 3;

/** Läuft der Flow gerade? Der Abzeichen-Toast fragt das ab und schweigt so
 *  lange: Beim Anmelden registriert die App den Push-Token, was sofort das
 *  „Frühwarner"-Abzeichen auslöst — die Meldung knallte damit über den
 *  Willkommens-Gruß, bevor man überhaupt etwas getan hatte. Modul-State statt
 *  Context, damit der Celebrator nicht am Flow hängen muss. */
let flowVisible = false;
export function isOnboardingVisible(): boolean {
  return flowVisible;
}
/** Wird beim Abschluss/Abbruch gefeuert, damit aufgeschobene Abzeichen-Meldungen
 *  nachgeholt werden können. */
export const ONBOARDING_DONE_EVENT = "ratslotse:onboarding-done";
/** Der Auftakt tritt beiseite und gibt den Login frei. Die Login-Seite liegt
 *  darunter längst gemountet — ohne dieses Signal begrüßte sie eine:n
 *  Erstnutzer:in mit „Willkommen zurück". */
export const ONBOARDING_NEEDS_LOGIN_EVENT = "ratslotse:onboarding-needs-login";

/** Den erreichten Schritt auch am Konto festhalten (fire-and-forget).
 *  Der lokale Speicher merkt sich den Stand fürs Gerät; erst der Server-Stand
 *  überlebt eine Neuinstallation — und nur er erlaubt es, nach zwei Tagen an
 *  eine liegengebliebene Einrichtung zu erinnern (scripts/remind_setup.py). */
function reportSetupStep(step: number, done = false) {
  api.post("/onboarding/setup", { step, done }).catch(() => {});
}

/** Ein Konto allein reicht nicht — frisch registriert ist es „pending" und
 *  unbestätigt, und die Schritte 1–3 (Abos, Themen) laufen dann in 403. Erst
 *  wenn es freigeschaltet ist, geht es weiter; bis dahin liegt die
 *  Bestätigungs-Aufforderung frei. Admins sind wie im App-Layout ausgenommen. */
function isUsable(user: { status?: string; email_verified?: boolean; role?: string } | null): boolean {
  if (!user) return false;
  if (user.role === "admin") return true;
  return user.status === "active" && !!user.email_verified;
}

export function OnboardingFlow() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const theme = useMascotTheme();
  const [step, setStep] = useState<Step | null>(null);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Nur in der App und nur beim ersten Mal.
    if (!isNativeApp()) return;
    // Erst wenn feststeht, ob jemand angemeldet ist — sonst hielte der Flow
    // einen angemeldeten Rückkehrer für abgemeldet und träte kurz beiseite.
    if (loading) return;
    try {
      if (localStorage.getItem(DONE_KEY) || localStorage.getItem(LEGACY_INTRO_KEY)) {
        setStep(null);
        return;
      }
      const raw = Number(localStorage.getItem(STEP_KEY) ?? 0);
      const saved = (Number.isFinite(raw) && raw >= 0 && raw <= 3 ? raw : 0) as Step;
      // Der Auftakt begrüßt VOR dem Login — erst danach fragt die App nach einem
      // Konto. Die Schritte 1–3 brauchen dagegen eins (Abos und Themen hängen
      // daran): Ohne Konto tritt der Flow beiseite und gibt den Login frei;
      // sobald angemeldet, macht er genau dort weiter.
      if (!isUsable(user) && saved > 0) {
        setStep(null);
        return;
      }
      setStep(saved);
    } catch {
      setStep(0);
    }
  }, [user, loading]);

  const go = (next: Step | "done") => {
    if (next === "done") {
      try {
        localStorage.setItem(DONE_KEY, "1");
        localStorage.setItem(LEGACY_INTRO_KEY, "1"); // die alte Intro nicht nachschieben
        localStorage.removeItem(STEP_KEY);
        // Push wurde in Schritt 3 gefragt — die Karte auf „Heute" schweigt jetzt
        // dieselbe Frist wie nach einem „Später" dort.
        localStorage.setItem(PUSH_SNOOZE_KEY,
          String(Date.now() + PUSH_SNOOZE_DAYS * 24 * 60 * 60 * 1000));
      } catch { /* Speicher voll/gesperrt — dann eben nochmal beim nächsten Start */ }
      setStep(null);
      if (isUsable(user)) reportSetupStep(3, true);
      window.dispatchEvent(new Event(ONBOARDING_DONE_EVENT));
      return;
    }
    try { localStorage.setItem(STEP_KEY, String(next)); } catch { /* egal */ }
    // Nach dem Auftakt ohne Konto: beiseitetreten, damit der Login sichtbar
    // wird. Der Schritt ist gemerkt — nach dem Anmelden geht es dort weiter.
    const asideForLogin = !isUsable(user) && next > 0;
    setStep(asideForLogin ? null : next);
    if (asideForLogin) {
      // Registrieren statt Anmelden: Wer den Auftakt gerade zum ersten Mal
      // sieht, hat in aller Regel noch kein Konto. Der Weg zurück steht auf
      // dem Registrieren-Screen („Schon registriert? Anmelden").
      if (!user) router.replace("/register");
      window.dispatchEvent(new Event(ONBOARDING_NEEDS_LOGIN_EVENT));
    }
  };

  // Den Stand melden, sobald ein Konto da ist — auch nachträglich: Wer den
  // Auftakt vor dem Login sieht, meldet Schritt 1 erst nach dem Anmelden.
  useEffect(() => {
    if (isUsable(user) && step !== null && step > 0) reportSetupStep(step);
  }, [user, step]);

  // Der Flow liegt ÜBER der Login-/Registrieren-Seite — und deren autoFocus-Feld
  // zieht den Fokus an sich, worauf iOS sofort die Tastatur aufklappt: Auf dem
  // Gerät stand sie über dem Willkommens-Gruß, noch bevor man etwas getan hatte.
  // Solange der Flow oben liegt, bekommt darum nur er den Fokus.
  useEffect(() => {
    if (step === null) return;
    const blurOutside = (el: Element | null) => {
      if (el instanceof HTMLElement && !rootRef.current?.contains(el)) el.blur();
    };
    blurOutside(document.activeElement);
    const onFocusIn = (e: FocusEvent) => blurOutside(e.target as Element | null);
    document.addEventListener("focusin", onFocusIn, true);
    return () => document.removeEventListener("focusin", onFocusIn, true);
  }, [step]);

  // Solange der Flow oben liegt, halten Abzeichen-Toasts still (s. flowVisible).
  useEffect(() => {
    flowVisible = step !== null;
    return () => { flowVisible = false; };
  }, [step]);

  if (step === null) return null;

  return (
    <div ref={rootRef} className="fixed inset-0 z-[100] flex flex-col bg-background pb-[calc(1.25rem+env(safe-area-inset-bottom))] pt-[calc(0.75rem+env(safe-area-inset-top))]">
      {step > 0 && (
        <div className="px-[18px]">
          <div className="flex items-center gap-3">
            {/* Drei Segmente statt eines Laufbalkens: Man sieht, wie viele
                Schritte es überhaupt sind — und dass es nur drei sind. */}
            <div className="flex flex-1 gap-1.5" role="progressbar"
              aria-valuenow={step} aria-valuemin={1} aria-valuemax={3}
              aria-label={`Schritt ${step} von 3`}>
              {[1, 2, 3].map((n) => (
                <span key={n} className={cn("h-1 flex-1 rounded-full transition-colors duration-300",
                  n <= step ? "bg-primary" : "bg-muted")} />
              ))}
            </div>
            <button type="button" onClick={() => go(step === 3 ? "done" : ((step + 1) as Step))}
              className="shrink-0 py-1 text-[13px] text-muted-foreground transition-colors hover:text-foreground">
              Überspringen
            </button>
          </div>
        </div>
      )}

      {step === 0 && <Welcome theme={theme} onNext={() => go(1)} />}
      {step === 1 && <CommitteeStep theme={theme} onNext={() => go(2)} />}
      {step === 2 && <TopicStep theme={theme} onNext={() => go(3)} />}
      {step === 3 && <PushStep theme={theme} onDone={() => go("done")} />}
    </div>
  );
}

/* -------------------------------------------------------------- Auftakt --- */

/** Der Auftakt ist der erste Eindruck der App — deshalb bewusst ein eigener
 *  Raum statt einer weiteren hellen Liste: nachtblauer Verlauf mit Wellen und
 *  ein paar Sternen, Lotti winkt aus zwei auslaufenden Ringen heraus, dann
 *  staffeln sich die drei Versprechen ein. Er bleibt dunkel, egal welches Theme
 *  eingestellt ist — er ist ein Moment, keine Seite. */
function Welcome({ theme, onNext }: { theme: ReturnType<typeof useMascotTheme>; onNext: () => void }) {
  const points: { icon: typeof Sparkles; tint: string; title: string; sub: string }[] = [
    { icon: Sparkles, tint: "bg-[hsla(19,92%,55%,0.2)] text-[hsl(19_92%_62%)]",
      title: "Frag den Rat", sub: "Antworten mit Quellen" },
    { icon: Bell, tint: "bg-[hsla(202,90%,60%,0.2)] text-[hsl(202_90%_68%)]",
      title: "Bleib informiert", sub: "Mitteilung bei neuen Beschlüssen" },
    { icon: Landmark, tint: "bg-white/10 text-white/80",
      title: "Aus der amtlichen Quelle", sub: "Rat Oldenburg" },
  ];
  const rows = ["wl-r1", "wl-r2", "wl-r3"];
  return (
    // Tippen überspringt sofort — die Animation ist ein Gruß, kein Tor. Bewusst
    // ein div mit onClick statt eines <button>: Der „Los geht's"-Knopf steckt
    // darin, und verschachtelte Buttons sind ungültiges HTML — React bricht
    // daran die Hydration ab (die Seite blieb leer).
    <div role="presentation" onClick={onNext}
      className="relative -mx-[18px] -mb-[calc(1.25rem+env(safe-area-inset-bottom))] -mt-[calc(0.75rem+env(safe-area-inset-top))] flex flex-1 flex-col items-center justify-center overflow-hidden px-8 text-center"
      style={{ background: "linear-gradient(170deg, hsl(213 62% 8%), hsl(210 55% 16%) 72%, hsl(205 58% 24%))" }}>
      <span aria-hidden className="bg-waves-light pointer-events-none absolute inset-0 opacity-90" />
      {/* Ein paar Sterne — sie machen aus dem Verlauf einen Nachthimmel. */}
      <span aria-hidden className="absolute left-[13%] top-[14%] h-[3px] w-[3px] rounded-full bg-[#BFE3F7] opacity-60" />
      <span aria-hidden className="absolute right-[16%] top-[20%] h-[2px] w-[2px] rounded-full bg-[#BFE3F7] opacity-50" />
      <span aria-hidden className="absolute left-[23%] top-[25%] h-[2px] w-[2px] rounded-full bg-[#BFE3F7] opacity-50" />

      <div className="wl-lotti relative flex items-center justify-center">
        <span aria-hidden className="wl-ring absolute h-[150px] w-[150px] rounded-full border-2 border-[hsl(19_92%_55%)]" />
        <span aria-hidden className="wl-ring wl-ring-2 absolute h-[150px] w-[150px] rounded-full border-2 border-[hsl(202_90%_60%)]" />
        <Mascot pose="wave" theme={theme} bob decorative className="h-32 w-32" />
      </div>

      <p className="wl-title mt-6 font-mono text-[11px] uppercase tracking-[0.18em] text-[hsl(19_92%_58%)]">
        Moin &amp; willkommen
      </p>
      <h1 className="wl-title mt-2 font-display text-[30px] font-extrabold leading-[1.08] tracking-tight text-white">
        Willkommen bei<br />Ratslotse
      </h1>

      <div className="mt-6 flex w-full flex-col gap-2.5">
        {points.map((p, i) => (
          <div key={p.title}
            className={cn(rows[i], "flex items-center gap-3 rounded-[13px] border border-white/[0.14] bg-white/[0.08] px-3.5 py-3 text-left")}>
            <span className={cn("inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-[9px]", p.tint)}>
              <p.icon className="h-4 w-4" />
            </span>
            <span className="text-[13.5px] text-white/[0.92]">
              <strong className="font-semibold text-white">{p.title}</strong> — {p.sub}
            </span>
          </div>
        ))}
      </div>

      <button type="button" onClick={onNext}
        className="wl-cta mt-7 flex h-12 w-full items-center justify-center rounded-[13px] bg-primary text-[15px] font-semibold text-primary-foreground shadow-[0_8px_22px_-10px_hsla(205,92%,34%,0.5)] transition-transform active:scale-[0.98]">
        Los geht&rsquo;s
      </button>
    </div>
  );
}

/* ------------------------------------------------- Schritt 1: Ausschüsse --- */

function CommitteeStep({ theme, onNext }: { theme: ReturnType<typeof useMascotTheme>; onNext: () => void }) {
  const qc = useQueryClient();
  const committees = useQuery({
    queryKey: ["committees"],
    queryFn: () => api.get<{ committees: string[] }>("/council/committees").then((d) => d.committees),
  });
  const subs = useQuery({
    queryKey: ["subscriptions"],
    queryFn: () => api.get<{ subscriptions: string[] }>("/subscriptions").then((d) => d.subscriptions),
  });
  const toggle = useMutation({
    mutationFn: ({ committee, on }: { committee: string; on: boolean }) =>
      on ? api.post("/subscriptions", { committee_name: committee })
         : api.del("/subscriptions", { committee_name: committee }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["subscriptions"] }),
  });

  const active = subs.data ?? [];
  // Alle Gremien direkt sichtbar, nach Alltagsbezug sortiert: Wer den Rat oder
  // Stadtplanung sucht, findet sie oben; Betriebsausschüsse stehen unten, aber
  // eben da — ein „Alle anzeigen"-Knopf hätte sie hinter einem Klick versteckt.
  const shown = (committees.data ?? []).slice()
    .sort((a, b) => committeeRank(a) - committeeRank(b) || shortCommittee(a).localeCompare(shortCommittee(b), "de"));

  return (
    <StepShell
      title="Welche Gremien interessieren dich?"
      lead="Du bekommst eine Mitteilung, sobald eine Tagesordnung erscheint. Jederzeit änderbar."
      pose="point" theme={theme}
      footer={
        <Button className="w-full" onClick={onNext}>
          {active.length > 0 ? `${active.length} abonniert · Weiter` : "Weiter"}
        </Button>
      }
    >
      {committees.isLoading && <p className="text-sm text-muted-foreground">Gremien werden geladen …</p>}
      <div className="flex flex-col gap-2">
        {shown.map((c) => {
          const on = active.includes(c);
          const explain = committeeExplains(c);
          return (
            <button key={c} type="button" aria-pressed={on}
              onClick={() => toggle.mutate({ committee: c, on: !on })}
              className={cn(
                "flex items-start gap-3 rounded-xl border p-3 text-left transition-colors",
                on ? "border-primary bg-primary/5" : "border-border bg-card hover:bg-muted/50",
              )}>
              <span className={cn(
                "mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-md border",
                on ? "border-primary bg-primary text-primary-foreground" : "border-border",
              )}>
                {on && <Check className="h-3.5 w-3.5" />}
              </span>
              <span className="min-w-0">
                <span className="block text-sm font-semibold text-foreground">{shortCommittee(c)}</span>
                {/* Ohne den Satz ist das eine Liste von Amtsbezeichnungen. */}
                {explain && <span className="mt-0.5 block text-xs leading-relaxed text-muted-foreground">{explain}</span>}
              </span>
            </button>
          );
        })}
      </div>
    </StepShell>
  );
}

/* ----------------------------------------------------- Schritt 2: Themen --- */

type TopicRow = { id: number; name: string; description: string; decision_count?: number };

type Described = {
  description: string;
  matches: number;
  examples: string[];
  is_council_topic: boolean;
  reason: string;
  vague: boolean;
  hint: string;
  suggestion: string;
};

function TopicStep({ theme, onNext }: { theme: ReturnType<typeof useMascotTheme>; onNext: () => void }) {
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [warn, setWarn] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const [editing, setEditing] = useState<TopicRow | null>(null);
  // Wie viele Beschlüsse auf die Beschreibung passen. NICHT decision_count aus
  // /topics — das zählt, was der Wächter bereits zugeordnet hat, und ist bei
  // einem frisch angelegten Thema immer 0 („0 Beschlüsse passen dazu" beim
  // Fliegerhorst mit 158 Beschlüssen). Hier zählt, was die Beschreibung trifft.
  const [matchCount, setMatchCount] = useState<Record<string, number>>({});
  const topics = useQuery({
    queryKey: ["topics"],
    queryFn: () => api.get<TopicRow[]>("/topics"),
  });
  const suggestions = useQuery({
    queryKey: ["topic-suggestions"],
    queryFn: () => api.get<{ suggestions: { name: string; description: string; n: number }[] }>("/topics/suggestions")
      .then((d) => d.suggestions),
  });

  /** RL-U17: Der Nutzer tippt nur den Namen — die Beschreibung entsteht aus den
   *  Beschlüssen. Sie ist es, an der der Wächter später misst, deshalb wird sie
   *  nicht generisch gefüllt. Ohne Rats-Bezug gibt es einen Hinweis, aber kein
   *  Verbot: angelegt wird trotzdem, wenn man will. */
  const add = async (topicName: string, presetDescription?: string, presetMatches?: number) => {
    const clean = topicName.trim();
    if (clean.length < 2 || busy) return;
    setBusy(true);
    setWarn(null);
    try {
      let description = presetDescription ?? "";
      if (typeof presetMatches === "number") setMatchCount((m) => ({ ...m, [clean]: presetMatches }));
      if (!description) {
        const d = await api.post<Described>("/topics/describe", { name: clean });
        description = d.description;
        setMatchCount((m) => ({ ...m, [clean]: d.matches }));
        if (!d.is_council_topic) {
          setWarn(d.reason || "Dazu gibt es bisher keine Beschlüsse des Oldenburger Stadtrats.");
          description = description || `Beschlüsse des Oldenburger Stadtrats rund um ${clean}.`;
        }
      }
      await api.post("/topics", { name: clean, description });
      setName("");
      qc.invalidateQueries({ queryKey: ["topics"] });
      qc.invalidateQueries({ queryKey: ["topic-suggestions"] });
    } catch {
      setWarn("Das Thema konnte gerade nicht angelegt werden. Versuch es gleich nochmal.");
    } finally {
      setBusy(false);
    }
  };

  const remove = async (id: number) => {
    try {
      await api.del(`/topics/${id}`);
      qc.invalidateQueries({ queryKey: ["topics"] });
      qc.invalidateQueries({ queryKey: ["topic-suggestions"] });
    } catch { /* bleibt stehen — beim nächsten Laden wieder korrekt */ }
  };

  const mine = topics.data ?? [];
  return (
    <StepShell
      title="Worüber willst du Bescheid wissen?"
      lead="Lege Themen an — Lotti meldet sich, sobald der Rat dazu entscheidet."
      pose="search" theme={theme}
      footer={<Button className="w-full" onClick={onNext}>Weiter</Button>}
    >
      <form onSubmit={(e) => { e.preventDefault(); void add(name); }} className="flex gap-2">
        <Input ref={inputRef} value={name} onChange={(e) => setName(e.target.value)}
          placeholder="Eigenes Thema, z. B. „Cäcilienbrücke“" enterKeyHint="done" aria-label="Thema" />
        <Button type="submit" disabled={busy || name.trim().length < 2} aria-label="Thema anlegen">
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
        </Button>
      </form>
      <p className="mt-1.5 text-xs text-muted-foreground">
        Beschreibung nicht nötig — Lotti formuliert sie automatisch aus passenden Beschlüssen.
      </p>
      {warn && (
        <p role="status" className="mt-2 rounded-lg border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs text-amber-800 dark:text-amber-300">
          {warn}
        </p>
      )}

      {(suggestions.data?.length ?? 0) > 0 && (
        <div className="mt-4">
          <p className="text-[11px] font-bold uppercase tracking-[0.06em] text-muted-foreground">Gerade aktuell im Rat</p>
          <div className="mt-2.5 flex flex-wrap gap-2">
            {suggestions.data!.slice(0, 7).map((s) => {
              const have = mine.some((t) => t.name === s.name);
              return (
                <button key={s.name} type="button" disabled={busy || have}
                  onClick={() => void add(s.name, s.description, s.n)}
                  className={cn(
                    "inline-flex items-center gap-1.5 rounded-full border px-3.5 py-[7px] text-[13px] transition-colors",
                    have ? "border-primary/30 bg-primary/5 text-primary"
                         : "border-border bg-card text-foreground hover:bg-muted disabled:opacity-50",
                  )}>
                  {have ? <Check className="h-3 w-3" /> : <Plus className="h-3 w-3 text-muted-foreground" />}
                  {s.name}
                </button>
              );
            })}
          </div>
        </div>
      )}

      {mine.length > 0 && (
        <div className="mt-4 rounded-2xl border border-border bg-card p-3.5">
          <p className="text-[11px] font-bold uppercase tracking-[0.06em] text-muted-foreground">
            Deine Themen ({mine.length})
          </p>
          <div className="mt-2.5 flex flex-col gap-2">
            {mine.map((t) => (
              <TopicCard key={t.id} topic={t} matches={matchCount[t.name]}
                onEdit={() => setEditing(t)} onRemove={() => void remove(t.id)} />
            ))}
          </div>
        </div>
      )}

      {editing && (
        <TopicSheet topic={editing} onClose={() => setEditing(null)}
          onSaved={() => { setEditing(null); qc.invalidateQueries({ queryKey: ["topics"] }); }} />
      )}
    </StepShell>
  );
}

/** Ein angelegtes Thema: Name, Herkunft der Beschreibung, wie viele Beschlüsse
 *  darauf passen — und der Weg, es anzupassen. Die Trefferzahl ist der Beleg
 *  dafür, dass die Beschreibung etwas taugt; ohne sie bliebe sie eine Behauptung. */
function TopicCard({ topic, matches, onEdit, onRemove }: {
  topic: TopicRow;
  /** Treffer der Beschreibung — undefined, solange nicht ermittelt. Dann bleibt
   *  die Zeile leer statt „0" zu behaupten. */
  matches?: number;
  onEdit: () => void;
  onRemove: () => void;
}) {
  return (
    <div className="rounded-xl border border-border bg-muted/30 px-3 py-2.5">
      <div className="flex items-center gap-2">
        <span className="min-w-0 flex-1 truncate text-sm font-semibold text-foreground">{topic.name}</span>
        <button type="button" onClick={onRemove} aria-label={`${topic.name} entfernen`}
          className="shrink-0 p-0.5 text-muted-foreground transition-colors hover:text-foreground">
          <X className="h-3.5 w-3.5" />
        </button>
      </div>
      <p className="mt-1.5 flex items-center gap-1.5 text-[10px] font-semibold tracking-[0.04em] text-signal">
        <Sparkles className="h-[11px] w-[11px]" />
        AUTOMATISCH BESCHRIEBEN
      </p>
      <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{topic.description}</p>
      <div className="mt-1.5 flex items-center gap-1.5 text-[11px] text-muted-foreground">
        {typeof matches === "number" && matches > 0 && (
          <>
            <span className="rounded bg-primary/10 px-1.5 font-semibold tabular-nums text-primary">
              {matches} {matches === 1 ? "Beschluss" : "Beschlüsse"}
            </span>
            <span>{matches === 1 ? "passt dazu" : "passen dazu"}</span>
          </>
        )}
        <button type="button" onClick={onEdit}
          className="ml-auto text-[11px] font-medium text-primary transition-colors hover:underline">
          anpassen
        </button>
      </div>
    </div>
  );
}

/** „anpassen": Name + Beschreibung bearbeiten. Zwei Dinge machen es mehr als ein
 *  Formular — beide zielen darauf, dass man die Folgen der eigenen Änderung
 *  sieht, bevor man speichert:
 *  „Passt gerade auf" zählt live, worauf der Text zutrifft, und die
 *  Vagheits-Prüfung warnt bei zu breiten Formulierungen. Sie blockiert nicht:
 *  „Trotzdem speichern" bleibt immer möglich. */
function TopicSheet({ topic, onClose, onSaved }: {
  topic: TopicRow;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [description, setDescription] = useState(topic.description ?? "");
  const [check, setCheck] = useState<Described | null>(null);
  const [checking, setChecking] = useState(false);
  const [saving, setSaving] = useState(false);
  const debounce = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Bei jeder Änderung neu prüfen — aber erst, wenn das Tippen kurz ruht.
  useEffect(() => {
    if (debounce.current) clearTimeout(debounce.current);
    debounce.current = setTimeout(() => {
      setChecking(true);
      api.post<Described>("/topics/describe", { name: topic.name, description })
        .then(setCheck)
        .catch(() => setCheck(null))
        .finally(() => setChecking(false));
    }, 900);
    return () => { if (debounce.current) clearTimeout(debounce.current); };
  }, [topic.name, description]);

  const regenerate = async () => {
    setChecking(true);
    try {
      const d = await api.post<Described>("/topics/describe", { name: topic.name });
      if (d.description) setDescription(d.description);
      setCheck(d);
    } catch { /* Fehlschlag ändert nichts — der alte Text bleibt stehen */ }
    setChecking(false);
  };

  const save = async () => {
    setSaving(true);
    try {
      await api.put(`/topics/${topic.id}`, { name: topic.name, description: description.trim() });
      onSaved();
    } catch {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[110] flex flex-col justify-end">
      <button type="button" aria-label="Schließen" onClick={onClose}
        className="absolute inset-0 bg-[rgba(9,17,27,0.42)]" />
      <div className="relative max-h-[88%] overflow-y-auto rounded-t-[22px] bg-card px-[18px] pb-[calc(1.125rem+env(safe-area-inset-bottom))] pt-2.5 shadow-[0_-12px_40px_-14px_rgba(2,32,71,0.4)]">
        <span aria-hidden className="mx-auto mb-3.5 block h-1 w-9 rounded-full bg-border" />
        <div className="flex items-center gap-2.5">
          <h3 className="flex-1 font-display text-lg font-bold text-foreground">Thema anpassen</h3>
          <button type="button" onClick={onClose} aria-label="Schließen"
            className="flex h-8 w-8 items-center justify-center rounded-[10px] bg-muted text-muted-foreground">
            <X className="h-4 w-4" />
          </button>
        </div>

        <p className="mb-1.5 mt-4 text-xs font-semibold text-muted-foreground">Name</p>
        <div className="flex h-[46px] items-center rounded-xl border border-border bg-card px-3.5 text-[15px] font-medium text-foreground">
          {topic.name}
        </div>

        <div className="mb-1.5 mt-4 flex items-center justify-between">
          <p className="text-xs font-semibold text-muted-foreground">Beschreibung</p>
          <button type="button" onClick={regenerate} disabled={checking}
            className="inline-flex items-center gap-1.5 text-xs font-medium text-signal disabled:opacity-50">
            <Sparkles className="h-3 w-3" /> Neu generieren
          </button>
        </div>
        <textarea value={description} onChange={(e) => setDescription(e.target.value)}
          rows={3} aria-label="Beschreibung"
          className="w-full rounded-xl border-[1.5px] border-primary bg-card px-3.5 py-3 text-[13px] leading-relaxed text-foreground outline-none" />

        <div className="mt-3.5 rounded-xl bg-muted/60 px-3.5 py-3">
          <p className="flex items-center justify-between text-[11px] font-semibold uppercase tracking-[0.05em] text-muted-foreground">
            Passt gerade auf
            {checking && (
              <span className="inline-flex items-center gap-1 normal-case tracking-normal">
                <Loader2 className="h-3 w-3 animate-spin" /> prüft…
              </span>
            )}
          </p>
          <p className="mt-1 text-[12.5px] leading-relaxed text-muted-foreground">
            {check ? (
              <>
                <strong className="font-semibold text-foreground">
                  {check.matches} {check.matches === 1 ? "Beschluss" : "Beschlüsse"}
                </strong>
                {check.examples.length > 0 && <> — u. a. „{check.examples.slice(0, 2).join("“, „")}“.</>}
              </>
            ) : "—"}
          </p>
        </div>

        {check?.vague && (
          <div className="mt-3 rounded-xl border border-amber-500/35 bg-amber-500/[0.06] px-3.5 py-3">
            <div className="flex items-start gap-2">
              <AlertTriangle className="mt-px h-[15px] w-[15px] shrink-0 text-amber-700 dark:text-amber-500" />
              <div className="min-w-0">
                <p className="text-[12.5px] leading-relaxed text-amber-900 dark:text-amber-200">
                  {check.hint || "Das ist recht weit gefasst — enger fassen?"}
                </p>
                {check.suggestion && (
                  <button type="button" onClick={() => setDescription(check.suggestion)}
                    className="mt-1.5 inline-flex items-start gap-1.5 rounded-[9px] border border-amber-500/40 bg-card px-2.5 py-1.5 text-left text-xs text-amber-900 dark:text-amber-200">
                    <Check className="mt-0.5 h-[11px] w-[11px] shrink-0" />
                    <span>Vorschlag übernehmen: „{check.suggestion}“</span>
                  </button>
                )}
              </div>
            </div>
          </div>
        )}

        <div className="mt-3.5 flex gap-2.5">
          <button type="button" onClick={onClose}
            className="h-[46px] flex-1 rounded-xl border border-border bg-card text-sm font-medium text-foreground">
            Abbrechen
          </button>
          <Button className="h-[46px] flex-1" onClick={save} disabled={saving || !description.trim()}>
            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : check?.vague ? "Trotzdem speichern" : "Speichern"}
          </Button>
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------- Schritt 3: Push --- */

function PushStep({ theme, onDone }: { theme: ReturnType<typeof useMascotTheme>; onDone: () => void }) {
  const [busy, setBusy] = useState(false);
  const allow = async () => {
    setBusy(true);
    try {
      const { enablePush } = await import("@/lib/push");
      await enablePush();
    } catch { /* Ablehnen ist eine gültige Antwort — nicht drängeln */ }
    setBusy(false);
    onDone();
  };
  return (
    <StepShell
      title="Soll Lotti sich melden?"
      lead="Nur wenn der Rat zu deinen Themen entscheidet oder eine Tagesordnung erscheint. Kein Spam — versprochen."
      pose="wave" theme={theme}
      footer={
        <div className="flex flex-col gap-2">
          <Button className="w-full" onClick={allow} disabled={busy}>
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : "Mitteilungen erlauben"}
          </Button>
          <button type="button" onClick={onDone} className="py-2 text-sm text-muted-foreground">
            Vielleicht später
          </button>
        </div>
      }
    >
      <div className="flex items-start gap-3 rounded-xl border border-border bg-card p-3">
        <Mascot pose="point" theme={theme} decorative className="h-10 w-10 shrink-0" />
        <div className="min-w-0">
          <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Neu zu deinen Themen</p>
          <p className="mt-0.5 text-sm text-foreground">Veloroute 4 beschlossen — 1,1 Mio. €</p>
        </div>
      </div>
    </StepShell>
  );
}

/* ------------------------------------------------------------- Gerüst ---- */

function StepShell({ title, lead, pose, theme, children, footer }: {
  title: string;
  lead: string;
  pose: MascotPose;
  theme: ReturnType<typeof useMascotTheme>;
  children: React.ReactNode;
  footer: React.ReactNode;
}) {
  return (
    <>
      <div className="min-h-0 flex-1 overflow-y-auto px-[18px] pt-5">
        {/* Lotti steht neben der Frage, nicht darüber: Sie fragt, man antwortet
            — das trägt den Ton des ganzen Flows. */}
        <div className="flex items-center gap-3">
          <Mascot pose={pose} theme={theme} decorative className="h-11 w-11 shrink-0" />
          <h1 className="font-display text-xl font-extrabold leading-tight tracking-tight text-foreground">{title}</h1>
        </div>
        <p className="mt-2.5 text-[13.5px] leading-relaxed text-muted-foreground">{lead}</p>
        <div className="mt-4 pb-2">{children}</div>
      </div>
      <div className="px-[18px] pt-3">{footer}</div>
    </>
  );
}
