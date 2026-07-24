"use client";

import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Loader2, Sparkles } from "lucide-react";
import { api } from "@/lib/api";
import { isNativeApp } from "@/lib/platform";
import { cn } from "@/lib/utils";
import { Button, Input } from "@/components/ui";
import { Mascot } from "@/components/mascot";
import { useMascotTheme } from "@/components/seasonal-mascot";
import { committeeExplains, shortCommittee } from "@/lib/committees";
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
/** Der alte First-Run-Schlüssel: Wer die Intro-Karten schon gesehen hat, ist
 *  kein Erstnutzer mehr und wird nicht nachträglich durchs Onboarding geschickt. */
const LEGACY_INTRO_KEY = "ratslotse.intro.done";

type Step = 0 | 1 | 2 | 3;

export function OnboardingFlow() {
  const { user } = useAuth();
  const theme = useMascotTheme();
  const [step, setStep] = useState<Step | null>(null);

  useEffect(() => {
    // Nur in der App und nur beim ersten Mal. Ohne Konto ergibt der Flow
    // nichts — Abos und Themen hängen am Login.
    if (!isNativeApp() || !user) return;
    try {
      if (localStorage.getItem(DONE_KEY) || localStorage.getItem(LEGACY_INTRO_KEY)) return;
      const saved = Number(localStorage.getItem(STEP_KEY) ?? 0);
      setStep((Number.isFinite(saved) && saved >= 0 && saved <= 3 ? saved : 0) as Step);
    } catch {
      setStep(0);
    }
  }, [user]);

  const go = (next: Step | "done") => {
    if (next === "done") {
      try {
        localStorage.setItem(DONE_KEY, "1");
        localStorage.setItem(LEGACY_INTRO_KEY, "1"); // die alte Intro nicht nachschieben
        localStorage.removeItem(STEP_KEY);
      } catch { /* Speicher voll/gesperrt — dann eben nochmal beim nächsten Start */ }
      setStep(null);
      return;
    }
    try { localStorage.setItem(STEP_KEY, String(next)); } catch { /* egal */ }
    setStep(next);
  };

  if (step === null) return null;

  return (
    <div className="fixed inset-0 z-[100] flex flex-col bg-background pb-[calc(1.25rem+env(safe-area-inset-bottom))] pt-[calc(0.75rem+env(safe-area-inset-top))]">
      {step > 0 && (
        <div className="px-5">
          <div className="flex items-center justify-between gap-3">
            <div className="h-1 flex-1 overflow-hidden rounded-full bg-muted" role="progressbar"
              aria-valuenow={step} aria-valuemin={1} aria-valuemax={3}
              aria-label={`Schritt ${step} von 3`}>
              <div className="h-full rounded-full bg-primary transition-[width] duration-300"
                style={{ width: `${(step / 3) * 100}%` }} />
            </div>
            <button type="button" onClick={() => go(step === 3 ? "done" : ((step + 1) as Step))}
              className="shrink-0 py-1 text-sm text-muted-foreground transition-colors hover:text-foreground">
              Überspringen
            </button>
          </div>
        </div>
      )}

      {step === 0 && <Welcome theme={theme} onNext={() => go(1)} />}
      {step === 1 && <CommitteeStep onNext={() => go(2)} />}
      {step === 2 && <TopicStep onNext={() => go(3)} />}
      {step === 3 && <PushStep theme={theme} onDone={() => go("done")} />}
    </div>
  );
}

/* -------------------------------------------------------------- Auftakt --- */

function Welcome({ theme, onNext }: { theme: ReturnType<typeof useMascotTheme>; onNext: () => void }) {
  const points = [
    ["Frag den Rat", "Antworten mit Quellen"],
    ["Bleib informiert", "Mitteilung bei neuen Beschlüssen"],
    ["Aus der amtlichen Quelle", "Rat Oldenburg"],
  ];
  return (
    // Tippen überspringt sofort — die Animation ist ein Gruß, kein Tor.
    <button type="button" onClick={onNext}
      className="flex flex-1 flex-col items-center justify-center gap-6 px-7 text-center">
      <Mascot pose="wave" theme={theme} decorative className="animate-fade-up h-28 w-28" />
      <div className="animate-fade-up" style={{ animationDelay: "120ms" }}>
        <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-signal">Moin &amp; willkommen</p>
        <h1 className="mt-1.5 font-display text-3xl font-extrabold leading-tight text-foreground">
          Willkommen bei<br />Ratslotse
        </h1>
      </div>
      <ul className="flex w-full max-w-xs flex-col gap-2.5 text-left">
        {points.map(([t, sub], i) => (
          <li key={t} className="animate-fade-up flex items-start gap-2.5"
            style={{ animationDelay: `${240 + i * 90}ms` }}>
            <Check className="mt-0.5 h-4 w-4 shrink-0 text-signal" />
            <span className="text-sm text-foreground">
              <strong className="font-semibold">{t}</strong>
              <span className="text-muted-foreground"> — {sub}</span>
            </span>
          </li>
        ))}
      </ul>
      <span className="animate-fade-up mt-2 w-full max-w-xs" style={{ animationDelay: "540ms" }}>
        <Button className="w-full" onClick={onNext}>Los geht&rsquo;s</Button>
      </span>
    </button>
  );
}

/* ------------------------------------------------- Schritt 1: Ausschüsse --- */

function CommitteeStep({ onNext }: { onNext: () => void }) {
  const qc = useQueryClient();
  const [showAll, setShowAll] = useState(false);
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
  // Die erklärten Gremien zuerst — sie sind die, die Leute wirklich suchen.
  const all = (committees.data ?? []).slice().sort((a, b) =>
    (committeeExplains(b) ? 1 : 0) - (committeeExplains(a) ? 1 : 0));
  const shown = showAll ? all : all.slice(0, 6);

  return (
    <StepShell
      title="Welche Gremien interessieren dich?"
      lead="Du bekommst eine Mitteilung, sobald eine Tagesordnung erscheint. Jederzeit änderbar."
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
      {!showAll && all.length > shown.length && (
        <button type="button" onClick={() => setShowAll(true)}
          className="mt-3 w-full rounded-xl border border-dashed border-border py-2 text-xs font-medium text-primary">
          Alle {all.length} Ausschüsse anzeigen
        </button>
      )}
    </StepShell>
  );
}

/* ----------------------------------------------------- Schritt 2: Themen --- */

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

function TopicStep({ onNext }: { onNext: () => void }) {
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [warn, setWarn] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const topics = useQuery({
    queryKey: ["topics"],
    queryFn: () => api.get<{ id: number; name: string; description: string }[]>("/topics"),
  });
  const suggestions = useQuery({
    queryKey: ["topic-suggestions"],
    queryFn: () => api.get<{ suggestions: { name: string; description: string }[] }>("/topics/suggestions")
      .then((d) => d.suggestions),
  });

  /** RL-U17: Der Nutzer tippt nur den Namen — die Beschreibung entsteht aus den
   *  Beschlüssen. Sie ist es, an der der Wächter später misst, deshalb wird sie
   *  nicht generisch gefüllt. Ohne Rats-Bezug gibt es einen Hinweis, aber kein
   *  Verbot: angelegt wird trotzdem, wenn man will. */
  const add = async (topicName: string, presetDescription?: string) => {
    const clean = topicName.trim();
    if (clean.length < 2 || busy) return;
    setBusy(true);
    setWarn(null);
    try {
      let description = presetDescription ?? "";
      if (!description) {
        const d = await api.post<Described>("/topics/describe", { name: clean });
        description = d.description;
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

  const mine = topics.data ?? [];
  return (
    <StepShell
      title="Worüber willst du Bescheid wissen?"
      lead="Lege Themen an — Lotti meldet sich, sobald der Rat dazu entscheidet."
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
          <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Gerade aktuell im Rat</p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {suggestions.data!.slice(0, 7).map((s) => (
              <button key={s.name} type="button" disabled={busy}
                onClick={() => void add(s.name, s.description)}
                className="rounded-full border border-border px-3 py-1.5 text-xs text-foreground transition-colors hover:bg-muted disabled:opacity-50">
                {s.name}
              </button>
            ))}
          </div>
        </div>
      )}

      {mine.length > 0 && (
        <div className="mt-5">
          <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
            Deine Themen ({mine.length})
          </p>
          <div className="mt-2 flex flex-col gap-2">
            {mine.map((t) => (
              <div key={t.id} className="rounded-xl border border-border bg-card p-3">
                <p className="text-sm font-semibold text-foreground">{t.name}</p>
                <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{t.description}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </StepShell>
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

function StepShell({ title, lead, children, footer }: {
  title: string;
  lead: string;
  children: React.ReactNode;
  footer: React.ReactNode;
}) {
  return (
    <>
      <div className="min-h-0 flex-1 overflow-y-auto px-5 pt-5">
        <h1 className="font-display text-2xl font-bold leading-tight text-foreground">{title}</h1>
        <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">{lead}</p>
        <div className="mt-4">{children}</div>
      </div>
      <div className="px-5 pt-3">{footer}</div>
    </>
  );
}
