"use client";

import { useEffect, useRef, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell, Check, Landmark, Loader2, Mail, MapPin, Plus, Sparkles, X } from "lucide-react";
import { api } from "@/lib/api";
import { isNativeApp } from "@/lib/platform";
import { cn, pfad } from "@/lib/utils";
import { Button, Input } from "@/components/ui";
import { Mascot, type MascotPose } from "@/components/mascot";
import { committeeExplains, committeeRank, shortCommittee } from "@/lib/committees";
import { useAuth } from "@/lib/auth";
import { TopicSheet, type Described } from "@/components/topic-sheet";

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
 *
 *  **Seit 09/2026 läuft der Assistent auch im Browser.** Vorher stand hier ein
 *  `if (!isNativeApp()) return` — der ganze Ablauf existierte, war im Web aber
 *  unsichtbar, und wer sich dort registrierte, landete unvermittelt auf einem
 *  leeren „Heute". Drei Dinge unterscheiden die beiden Plattformen:
 *
 *  1. **Wer ihn zu sehen bekommt, entscheidet der Server** (`/onboarding/setup`,
 *     Feld `pending`). Der localStorage taugte dafür nur in der App: Im Browser
 *     wechselt man das Gerät, und ein zweiter Rechner finge sonst von vorn an.
 *     Die Regel steht damit an einer Stelle für beide Frontends.
 *  2. **Der Auftakt begrüßt in der App VOR dem Login** — dort gibt es keine
 *     Startseite, die das täte. Im Browser ist das die Landingpage; der
 *     Assistent beginnt deshalb erst nach der Anmeldung.
 *  3. **Schritt 3 fragt etwas anderes.** Im Browser gibt es keine Push-Erlaubnis
 *     (das Backend kennt nur APNs/FCM), also geht es dort um die E-Mail-
 *     Zustellung — siehe `PushStep`/`MailStep`.
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

/** Die Spalte, in der der Assistent steht. Am Telefon füllt sie den Schirm, am
 *  Desktop steht sie zentriert — 980 px, dieselbe Breite wie die iPad-Fassung
 *  der App. Fortschrittsleiste, Inhalt und Fußzeile MÜSSEN dieselbe Klasse
 *  benutzen, sonst steht die Leiste neben ihrem eigenen Schritt. */
const SPALTE = "mx-auto w-full max-w-[980px]";
/** Am Desktop zweispaltig wie auf dem iPad: links Lotti mit der Frage, rechts
 *  die Antwortfläche. Darunter (`lg` = 1024 px) bleibt es einspaltig. */
const ZWEISPALTIG = "lg:grid lg:grid-cols-[320px_minmax(0,1fr)] lg:gap-12";

/** Im Browser darf der Assistent nur INNERHALB der App auftauchen.
 *
 *  Er hängt global in `app/providers.tsx` (in der App muss er das: dort liegt
 *  er über dem Login). Im Web liegt darunter aber auch die Landingpage, das
 *  Changelog, Impressum und Datenschutz — und ein deckender Vollbild-Assistent
 *  über dem Impressum wäre schlicht falsch, gerade weil solche Seiten aus
 *  Rechtsgründen erreichbar bleiben müssen.
 *
 *  Bewusst eine Positivliste der Bereiche aus `app/(app)/`: Eine Negativliste
 *  müsste bei jeder neuen öffentlichen Seite nachgezogen werden, und wer das
 *  vergisst, merkt es nicht — der Fehler zeigt sich nur angemeldeten
 *  Erstnutzer*innen auf genau dieser Seite. */
const APP_BEREICHE = [
  "/dashboard", "/council", "/fragen", "/topics", "/abos",
  "/bookmarks", "/quiz", "/account", "/admin", "/haushalt",
];

function imAppBereich(pathname: string | null): boolean {
  const p = pfad(pathname);
  return APP_BEREICHE.some((b) => p === b || p.startsWith(`${b}/`));
}

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
 *  Erstnutzer*in mit „Willkommen zurück". */
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

/** Server-Stand des Assistenten. `pending` beantwortet „ist er dran?" — die
 *  Regel steht im Backend (`Store.get_setup`), damit Web und App dieselbe
 *  Antwort bekommen und das Frontend nicht erst Themen und Abos zählen muss. */
type SetupStand = { step: number; started_at: string | null; done_at: string | null; pending: boolean };

export function OnboardingFlow() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const [step, setStep] = useState<Step | null>(null);
  const rootRef = useRef<HTMLDivElement>(null);
  const native = isNativeApp();
  // In DIESER Sitzung abgeschlossen. Ohne den Riegel schöbe die noch im Cache
  // liegende Server-Antwort (`pending: true`) den Assistenten sofort wieder
  // hoch, sobald der Effekt erneut läuft — der Abschluss ist ja fire-and-forget.
  const fertig = useRef(false);

  const setup = useQuery({
    queryKey: ["onboarding-setup"],
    queryFn: () => api.get<SetupStand>("/onboarding/setup"),
    enabled: isUsable(user),
    staleTime: 60_000,
    retry: false,
  });

  const setupData = setup.data;
  useEffect(() => {
    // Erst wenn feststeht, ob jemand angemeldet ist — sonst hielte der Flow
    // einen angemeldeten Rückkehrer für abgemeldet und träte kurz beiseite.
    if (loading || fertig.current) return;

    // --- Ohne (nutzbares) Konto ---
    // In der App begrüßt der Auftakt VOR dem Login; im Browser tut das die
    // Landingpage, dort gibt es hier also nichts zu zeigen.
    if (!isUsable(user)) {
      if (!native) { setStep(null); return; }
      try {
        if (localStorage.getItem(DONE_KEY) || localStorage.getItem(LEGACY_INTRO_KEY)) {
          setStep(null);
          return;
        }
        const raw = Number(localStorage.getItem(STEP_KEY) ?? 0);
        const saved = (Number.isFinite(raw) && raw >= 0 && raw <= 3 ? raw : 0) as Step;
        // Die Schritte 1–3 brauchen ein Konto (Abos und Themen hängen daran):
        // Ohne eins tritt der Flow beiseite und gibt den Login frei; sobald
        // angemeldet, macht er genau dort weiter.
        setStep(saved > 0 ? null : saved);
      } catch {
        setStep(0);
      }
      return;
    }

    // Im Browser nur innerhalb der App — nicht über Landingpage oder Impressum.
    if (!native && !imAppBereich(pathname)) { setStep(null); return; }

    // --- Angemeldet: der Server entscheidet ---
    // In der App zählt zusätzlich der lokale „schon erledigt"-Riegel. Er kann
    // nur NEIN sagen, nie ja — für Stände aus der Zeit vor der Server-Persistenz.
    if (native) {
      try {
        if (localStorage.getItem(DONE_KEY) || localStorage.getItem(LEGACY_INTRO_KEY)) {
          setStep(null);
          return;
        }
      } catch { /* unlesbarer Speicher — dann entscheidet allein der Server */ }
    }
    if (!setupData) return;              // Antwort steht noch aus: nichts zeigen
    if (!setupData.pending) { setStep(null); return; }
    setStep(Math.max(0, Math.min(3, setupData.step)) as Step);
  }, [user, loading, native, setupData, pathname]);

  const go = (next: Step | "done") => {
    if (next === "done") {
      fertig.current = true;
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
  //
  // Ausnahme „Thema anpassen": Das Blatt hängt bewusst direkt an <body> (sonst
  // fängt ein transformierter Vorfahre sein `position: fixed` ein) und liegt
  // damit außerhalb von rootRef. Ohne diese Ausnahme entzöge der Wächter seinen
  // Feldern sofort wieder den Fokus — man könnte dort nichts mehr tippen.
  useEffect(() => {
    if (step === null) return;
    const blurOutside = (el: Element | null) => {
      if (el instanceof HTMLElement && !rootRef.current?.contains(el)
          && !el.closest("[data-topic-sheet]")) el.blur();
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
    /* Ebene „flaeche": Der Auftakt ERSETZT die App-Hülle (deckend, inset-0),
       das Blatt „Thema anpassen" liegt eine Stufe darüber. Die Leiter steht in
       app/globals.css. */
    <div ref={rootRef} className="fixed inset-0 z-[var(--level-flaeche)] flex flex-col bg-background pb-[calc(1.25rem+env(safe-area-inset-bottom))] pt-[calc(0.75rem+env(safe-area-inset-top))]">
      {step > 0 && (
        /* Am Desktop läuft die Fortschrittsleiste nicht über die volle Breite:
           Sie gehört über den Inhalt, und der ist auf Lesebreite begrenzt.
           Dieselbe `mx-auto max-w-*`-Fassung wie in StepShell — beide MÜSSEN
           gleich sein, sonst steht die Leiste neben ihrem eigenen Schritt. */
        <div className={cn(SPALTE, "px-[18px] lg:px-8")}>
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

      {step === 0 && <Welcome onNext={() => go(1)} />}
      {step === 1 && <CommitteeStep onNext={() => go(2)} />}
      {step === 2 && <TopicStep onNext={() => go(3)} />}
      {/* Schritt 3 fragt auf beiden Plattformen dasselbe („Soll Lotti sich
          melden?") — aber der Browser kann keine Push-Erlaubnis geben, dort
          geht es um die E-Mail. */}
      {step === 3 && (native
        ? <PushStep onDone={() => go("done")} />
        : <MailStep onDone={() => go("done")} />)}
    </div>
  );
}

/* -------------------------------------------------------------- Auftakt --- */

/** Der Auftakt ist der erste Eindruck der App — deshalb bewusst ein eigener
 *  Raum statt einer weiteren hellen Liste: nachtblauer Verlauf mit Wellen und
 *  ein paar Sternen, Lotti winkt aus zwei auslaufenden Ringen heraus, dann
 *  staffeln sich die drei Versprechen ein. Er bleibt dunkel, egal welches Theme
 *  eingestellt ist — er ist ein Moment, keine Seite. */
function Welcome({ onNext }: { onNext: () => void }) {
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

      {/* Der Gruß bleibt auch am großen Schirm eine Spalte. Ohne die Grenze
          liefen die drei Versprechen über die volle Fensterbreite auseinander —
          und aus dem Moment würde eine Tabelle. */}
      <div className="relative flex w-full max-w-[26rem] flex-col items-center">
      <div className="wl-lotti relative flex items-center justify-center">
        <span aria-hidden className="wl-ring absolute h-[150px] w-[150px] rounded-full border-2 border-[hsl(19_92%_55%)]" />
        <span aria-hidden className="wl-ring wl-ring-2 absolute h-[150px] w-[150px] rounded-full border-2 border-[hsl(202_90%_60%)]" />
        <Mascot pose="wave" decorative className="h-32 w-32" />
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
    </div>
  );
}

/* ------------------------------------------------- Schritt 1: Ausschüsse --- */

function CommitteeStep({ onNext }: { onNext: () => void }) {
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
      pose="point"
      footer={
        <Button className="w-full lg:w-auto lg:min-w-44" onClick={onNext}>
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

type TopicRow = {
  id: number; name: string; description: string;
  decision_count?: number; decision_count_capped?: boolean; matched?: boolean;
};

function TopicStep({ onNext }: { onNext: () => void }) {
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [warn, setWarn] = useState<string | null>(null);
  // Kein Fehler, sondern eine Auskunft: Das Thema IST angelegt, der Rat hat nur
  // noch nichts dazu entschieden. Darum eigene, ruhige Farbe statt Warngelb.
  const [note, setNote] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const [editing, setEditing] = useState<TopicRow | null>(null);
  // Wie viele Beschlüsse auf die Beschreibung passen. NICHT decision_count aus
  // /topics — das zählt, was der Wächter bereits zugeordnet hat, und ist bei
  // einem frisch angelegten Thema immer 0 („0 Beschlüsse passen dazu" beim
  // Fliegerhorst mit 158 Beschlüssen). Hier zählt, was die Beschreibung trifft.
  //
  // Die Zahl trägt ihre Herkunft mit: Der Vorschlags-Chip kennt nur, wie oft
  // die Entitäts-Erkennung den Namen im letzten Jahr gesehen hat — eine andere
  // Größe als die Treffer auf die Beschreibung. Beide „12 Beschlüsse" zu nennen
  // war genau Tims Befund vom 16.08. („die zahlen passen nicht zusammen").
  const [matchCount, setMatchCount] = useState<Record<string, { n: number; source: "year" | "treffer" }>>({});
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
   *  nicht generisch gefüllt.
   *
   *  Drei Ausgänge, weil zwei zu grob sind:
   *  - **belegt**     — anlegen, Trefferzahl zeigen.
   *  - **plausibel**  — anlegen, aber ehrlich sagen, dass der Rat dazu noch
   *    nichts entschieden hat. „Grundschule Krusenbusch" gibt es wirklich; sie
   *    kam nur noch nicht vor. Genau dafür ist ein Thema ja da.
   *  - **ungeeignet** — NICHT anlegen. Vorher wurde auch das gespeichert und die
   *    Warnung erschien danach; so landeten ganze Anweisungssätze als Thema. */
  const add = async (topicName: string, presetDescription?: string, presetMatches?: number) => {
    const clean = topicName.trim();
    if (clean.length < 2 || busy) return;
    setBusy(true);
    setWarn(null);
    setNote(null);
    try {
      let description = presetDescription ?? "";
      if (typeof presetMatches === "number") setMatchCount((m) => ({ ...m, [clean]: { n: presetMatches, source: "year" } }));
      if (!description) {
        const d = await api.post<Described>("/topics/describe", { name: clean });
        if (d.verdict === "ungeeignet") {
          setWarn(d.reason || "Das sieht nicht nach einem Thema des Oldenburger Stadtrats aus.");
          return;
        }
        description = d.description;
        setMatchCount((m) => ({ ...m, [clean]: { n: d.matches, source: "treffer" } }));
        if (d.verdict === "plausibel") {
          setNote(`Über „${clean}" hat der Rat bisher nichts entschieden — Lotti meldet sich, sobald es so weit ist.`);
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
      pose="search"
      footer={<Button className="w-full lg:w-auto lg:min-w-44" onClick={onNext}>Weiter</Button>}
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

      <StadtteilWahl
        vorhanden={mine.map((t) => t.name)}
        busy={busy}
        onWaehlen={(name, beschreibung) => void add(name, beschreibung)}
      />
      {warn && (
        <p role="status" className="mt-2 rounded-lg border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs text-amber-800 dark:text-amber-300">
          {warn}
        </p>
      )}
      {note && (
        <p role="status" className="mt-2 rounded-lg border border-border bg-muted/50 px-3 py-2 text-xs text-muted-foreground">
          {note}
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

/** „Dein Stadtteil" — der eine Schritt, den die App schon hatte und das Web nicht.
 *
 *  Er ist ein Thema wie jedes andere, nur eins, das fast alle wollen und das
 *  kaum jemand von sich aus tippt: Ein Stadtteil hat einen amtlichen Namen, den
 *  man raten müsste, und er taucht in Beschlüssen unter vielen Schreibweisen
 *  auf. Als Auswahlliste kostet er einen Klick statt eines Versuchs.
 *
 *  Die Liste kommt aus `/council/districts` — also nur Ortsbereiche, zu denen
 *  es überhaupt Beschlüsse gibt. Ein leerer Stadtteil in der Auswahl wäre ein
 *  Versprechen, das der Datenbestand nicht hält.
 */
function StadtteilWahl({ vorhanden, busy, onWaehlen }: {
  vorhanden: string[];
  busy: boolean;
  onWaehlen: (name: string, beschreibung: string) => void;
}) {
  const districts = useQuery({
    queryKey: ["council-districts"],
    queryFn: () => api.get<{ districts: { place_id: string; name: string; description?: string | null }[] }>(
      "/council/districts").then((d) => d.districts),
    staleTime: 10 * 60_000,
  });

  const liste = (districts.data ?? []).slice()
    .sort((a, b) => a.name.localeCompare(b.name, "de"));
  if (!liste.length) return null;

  // Schon als Thema angelegt? Dann ist er gewählt — dieselbe Prüfung wie in
  // der App: Der Stadtteil IST das Thema, es gibt keinen zweiten Zustand.
  const gewaehlt = liste.find((d) =>
    vorhanden.some((n) => n.toLowerCase() === d.name.toLowerCase()));

  return (
    <div className="mt-3 rounded-2xl border border-border bg-muted/30 p-3.5">
      <div className="flex items-start gap-3">
        <span className="mt-0.5 inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-[10px] bg-primary/10">
          <MapPin className="h-4 w-4 text-primary" />
        </span>
        <div className="min-w-0">
          <p className="flex items-center gap-1.5 text-[13.5px] font-semibold text-foreground">
            Dein Stadtteil
            <span className="font-mono text-[9px] uppercase tracking-[0.1em] text-muted-foreground">optional</span>
          </p>
          <p className="mt-0.5 text-xs leading-relaxed text-muted-foreground">
            Lotti beobachtet dort neue Beschlüsse und Planungen für dich.
          </p>
        </div>
      </div>

      <label className="sr-only" htmlFor="onb-stadtteil">Stadtteil auswählen</label>
      <select
        id="onb-stadtteil"
        className="mt-3 h-11 w-full rounded-[11px] border border-border bg-card px-3 text-sm font-medium text-foreground disabled:opacity-60"
        value={gewaehlt?.place_id ?? ""}
        disabled={busy}
        onChange={(e) => {
          const d = liste.find((x) => x.place_id === e.target.value);
          if (!d) return;
          // Dieselbe Beschreibung wie in der App — sie ist es, an der der
          // Wächter später misst, also darf sie nicht generisch sein.
          const detail = (d.description ?? "").trim();
          onWaehlen(d.name, detail
            ? `${detail} Neue Beschlüsse, Planungen und Maßnahmen mit Bezug zu ${d.name}.`
            : `Neue Beschlüsse, Planungen und Maßnahmen des Oldenburger Stadtrats mit Bezug zu ${d.name}.`);
        }}
      >
        <option value="">Stadtteil auswählen …</option>
        {liste.map((d) => (
          <option key={d.place_id} value={d.place_id}>{d.name}</option>
        ))}
      </select>
      {gewaehlt && (
        <p className="mt-2 flex items-center gap-1.5 text-xs text-primary">
          <Check className="h-3.5 w-3.5 shrink-0" />
          {gewaehlt.name} steht unter „Deine Themen" und löst passende Hinweise aus.
        </p>
      )}
    </div>
  );
}

/** Ein angelegtes Thema: Name, Herkunft der Beschreibung, wie viele Beschlüsse
 *  darauf passen — und der Weg, es anzupassen. Die Trefferzahl ist der Beleg
 *  dafür, dass die Beschreibung etwas taugt; ohne sie bliebe sie eine Behauptung. */
function TopicCard({ topic, matches, onEdit, onRemove }: {
  topic: TopicRow;
  /** Zahl samt Herkunft — undefined, solange nichts ermittelt ist. Dann bleibt
   *  die Zeile leer statt „0" zu behaupten. `treffer` sind Beschlüsse, die auf
   *  die Beschreibung passen (dieselbe Definition wie Themen-Karte und Liste);
   *  `year` ist die viel gröbere Zahl aus dem Vorschlags-Chip — wie oft der
   *  Name im letzten Jahr überhaupt vorkam. Beide „Beschlüsse" zu nennen hat
   *  genau die Verwirrung erzeugt, die Tim am 16.08. gemeldet hat. */
  matches?: { n: number; source: "year" | "treffer" };
  onEdit: () => void;
  onRemove: () => void;
}) {
  // Seit dem Sofort-Abgleich (28.08.2026) trägt das angelegte Thema selbst die
  // verbindliche Zahl — dieselbe, die gleich auf der Themen-Karte steht. Die
  // hat Vorrang vor der lokalen Vorschau: Die stammt aus `/topics/describe` auf
  // den bloßen Namen, das Thema wurde aber mit „Name. Beschreibung" abgeglichen.
  // Zwei Wege, dieselbe Definition, minimal andere Zahl — genau die Sorte
  // Abweichung, die hier schon einmal Verwirrung gestiftet hat.
  const zahl = topic.matched && typeof topic.decision_count === "number"
    ? { n: topic.decision_count, source: "treffer" as const, gedeckelt: !!topic.decision_count_capped }
    : matches && { ...matches, gedeckelt: false };
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
        {zahl && zahl.n > 0 && (
          <>
            <span className="rounded bg-primary/10 px-1.5 font-semibold tabular-nums text-primary">
              {zahl.n}{zahl.gedeckelt ? "+" : ""}{" "}
              {zahl.n === 1 && !zahl.gedeckelt ? "Beschluss" : "Beschlüsse"}
            </span>
            <span>
              {zahl.source === "year"
                ? "im letzten Jahr"
                : zahl.n === 1 && !zahl.gedeckelt ? "passt dazu" : "passen dazu"}
            </span>
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

/* --------------------------------------------- Schritt 3 (Web): E-Mail --- */

/** Im Browser gibt es keine Push-Erlaubnis — das Backend kennt nur APNs und
 *  FCM (`kern/push.py`), Web-Push (VAPID) existiert nicht. Der Schritt stellt
 *  deshalb dieselbe Frage über den Kanal, der im Browser wirklich zustellt.
 *
 *  Und er wirbt dafür, statt nur zu fragen. Das ist kein Verkaufston, sondern
 *  die Sache: Ohne Mitteilung erfährt man nicht, dass das eigene Thema auf
 *  einer Tagesordnung steht — und dann ist Ratslotse eine Seite, die man von
 *  sich aus aufrufen müsste, um zu erfahren, dass es etwas zu erfahren gäbe.
 *  Genau dafür sind Themen und Abos in den Schritten davor angelegt worden.
 *
 *  Geworben wird mit dem, was zutrifft, nicht mit Dringlichkeit: was konkret
 *  käme, und wie wenig es ist. Die Mengen stehen als Zahl da (aus
 *  `kern/notify.py`: höchstens zwei am Tag, zwischen 21 und 7 Uhr nichts) —
 *  „nur wenige E-Mails" wäre genau die Sorte Beteuerung, der niemand glaubt.
 */
function MailStep({ onDone }: { onDone: () => void }) {
  const { user, refresh } = useAuth();
  const [busy, setBusy] = useState(false);
  const [fehler, setFehler] = useState<string | null>(null);
  // Bei der Registrierung wird „email" gesetzt — der Normalfall ist also, dass
  // der Kanal bereits an ist. Dann ist dies eine Bestätigung, kein Schalter:
  // Ein Knopf, der etwas einschaltet, das längst an ist, macht ratlos.
  const an = user?.delivery_channel === "email" || user?.delivery_channel === "both";

  const einschalten = async () => {
    if (an) { onDone(); return; }
    setBusy(true);
    setFehler(null);
    try {
      // Wer vorher Push hatte (etwa aus der App), behält es und bekommt E-Mail
      // dazu — sonst nähme dieser Schritt einen Kanal weg, statt einen zu geben.
      await api.put("/account/delivery",
        { delivery_channel: user?.delivery_channel === "push" ? "both" : "email" });
      await refresh();
      onDone();
    } catch {
      setFehler("Das ließ sich gerade nicht speichern. Du kannst es in den Kontoeinstellungen nachholen.");
      setBusy(false);
    }
  };

  return (
    <StepShell
      title="Soll Lotti sich melden?"
      lead="Ohne Mitteilung merkst du nicht, wenn dein Thema auf einer Tagesordnung landet — und genau darum geht es hier."
      pose="wave"
      footer={
        <div className="flex w-full flex-col gap-2 lg:w-auto lg:items-end">
          <Button className="w-full lg:w-auto lg:min-w-56" onClick={einschalten} disabled={busy}>
            {busy ? <Loader2 className="h-4 w-4 animate-spin" />
                  : an ? "Ja, so ist es richtig" : "E-Mail-Mitteilungen einschalten"}
          </Button>
          {/* Ein Nein muss möglich bleiben — aber es steht als stiller Text da,
              nicht als gleichwertiger zweiter Knopf. */}
          <button type="button" onClick={onDone}
            className="py-1 text-sm text-muted-foreground transition-colors hover:text-foreground">
            {an ? "Später entscheiden" : "Ohne Mitteilungen weiter"}
          </button>
        </div>
      }
    >
      {/* Was konkret käme — als das, was es ist: eine Mail. */}
      <div className="overflow-hidden rounded-xl border border-border bg-card">
        <div className="flex items-center gap-2 border-b border-border bg-muted/40 px-3.5 py-2">
          <Mail className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
          <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-muted-foreground">
            So sieht das aus
          </span>
        </div>
        <div className="flex items-start gap-3 p-3.5">
          <Mascot pose="point" decorative className="h-10 w-10 shrink-0" />
          <div className="min-w-0">
            <p className="font-mono text-[10px] uppercase tracking-[0.1em] text-muted-foreground">
              Neu zu deinen Themen
            </p>
            <p className="mt-1 text-sm font-medium text-foreground">
              Cäcilienbrücke: Rat fordert schnelleren Neubau
            </p>
            <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
              Verkehrsausschuss · morgen 17:00 — mit dem Beschlusstext und der Vorlage.
            </p>
          </div>
        </div>
      </div>

      {/* Drei Gründe, alle konkret. Kein „verpasse nichts". */}
      <ul className="mt-3 flex flex-col gap-2">
        {[
          ["Dein Thema kommt auf den Tisch",
           "Auch in Gremien, die du gar nicht abonniert hast — sonst erführst du es nie."],
          ["Der Rat hat entschieden",
           "Ergebnisse stehen erst im Protokoll, oft Wochen nach der Sitzung. Von allein sieht man das nicht."],
          ["Eine Tagesordnung erscheint",
           "Meist wenige Tage vor der Sitzung — früh genug, um noch etwas zu sagen."],
        ].map(([titel, text]) => (
          <li key={titel} className="flex items-start gap-2.5">
            <Check className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
            <span className="min-w-0 text-[13px] leading-relaxed text-foreground">
              <strong className="font-semibold">{titel}</strong>
              <span className="block text-muted-foreground">{text}</span>
            </span>
          </li>
        ))}
      </ul>

      {/* Die Gegenfrage, die jede:r stellt — mit Zahlen beantwortet. */}
      <p className="mt-3 rounded-lg border border-border bg-muted/30 px-3 py-2.5 text-xs leading-relaxed text-muted-foreground">
        <strong className="font-semibold text-foreground">Höchstens zwei Mitteilungen am Tag</strong>, zwischen
        21 und 7 Uhr gar keine — mehr wird gebündelt. Welche Anlässe du bekommst, stellst du
        jederzeit im Konto ein; abbestellen geht mit einem Klick in jeder Mail.
      </p>

      {an && (
        <p className="mt-2.5 flex items-center gap-1.5 text-xs text-primary">
          <Check className="h-3.5 w-3.5 shrink-0" />
          E-Mail-Mitteilungen sind für {user?.email} bereits eingeschaltet.
        </p>
      )}
      {fehler && (
        <p role="status" className="mt-2.5 rounded-lg border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs text-amber-800 dark:text-amber-300">
          {fehler}
        </p>
      )}
    </StepShell>
  );
}

/* ------------------------------------------------------- Schritt 3: Push --- */

function PushStep({ onDone }: { onDone: () => void }) {
  const { user, refresh } = useAuth();
  const [busy, setBusy] = useState(false);
  const allow = async () => {
    setBusy(true);
    try {
      const { enablePush } = await import("@/lib/push");
      // Die iOS-Erlaubnis registriert nur das Gerät. Ohne das Umstellen des
      // Zustellwegs bliebe das Konto auf „nur E-Mail" — man hätte zugestimmt
      // und trotzdem nie eine Mitteilung bekommen. (Genau so beobachtet:
      // „Heute" bat danach weiter um Erlaubnis, und zwar zu Recht.)
      if (await enablePush()) {
        // Wer vorher ganz abgeschaltet hatte, bekommt nur Push zurück — nicht
        // zusätzlich wieder E-Mails, die er ausdrücklich abbestellt hatte.
        const vorher = user?.delivery_channel;
        const channel = vorher === "push" || vorher === "off" ? "push" : "both";
        await api.put("/account/delivery", { delivery_channel: channel });
        await refresh();
      }
    } catch { /* Ablehnen ist eine gültige Antwort — nicht drängeln */ }
    setBusy(false);
    onDone();
  };
  return (
    <StepShell
      title="Soll Lotti sich melden?"
      lead="Nur wenn der Rat zu deinen Themen entscheidet oder eine Tagesordnung erscheint. Kein Spam — versprochen."
      pose="wave"
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
        <Mascot pose="point" decorative className="h-10 w-10 shrink-0" />
        <div className="min-w-0">
          <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Neu zu deinen Themen</p>
          <p className="mt-0.5 text-sm text-foreground">Cäcilienbrücke: Rat fordert schnelleren Neubau</p>
        </div>
      </div>
    </StepShell>
  );
}

/* ------------------------------------------------------------- Gerüst ---- */

function StepShell({ title, lead, pose, children, footer }: {
  title: string;
  lead: string;
  pose: MascotPose;
  children: React.ReactNode;
  footer: React.ReactNode;
}) {
  return (
    <>
      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className={cn(SPALTE, "px-[18px] pt-5 lg:px-8 lg:pt-10")}>
          <div className={ZWEISPALTIG}>
            {/* Lotti steht neben der Frage, nicht darüber: Sie fragt, man
                antwortet — das trägt den Ton des ganzen Flows. Am Desktop
                rutscht sie über den Titel und wird größer (Platz ist da), und
                die Frage bleibt beim Scrollen stehen: Auf einem langen Schritt
                wie den Gremien verliert man sonst aus dem Blick, was gefragt war. */}
            <div className="lg:sticky lg:top-10 lg:self-start">
              <div className="flex items-center gap-3 lg:block">
                <Mascot pose={pose} decorative className="h-11 w-11 shrink-0 lg:mb-5 lg:h-28 lg:w-28" />
                {/* `hyphens-none`: In der 320-px-Spalte trennte der Browser die
                    Frage mitten im Wort („Worüber willst du Be-scheid wissen?").
                    Silbentrennung taugt für Fließtext, nicht für eine Überschrift
                    aus vier Wörtern — die soll am Wort umbrechen. */}
                <h1 className="font-display text-xl font-extrabold leading-tight tracking-tight text-foreground [hyphens:none] lg:text-[28px]">{title}</h1>
              </div>
              <p className="mt-2.5 text-[13.5px] leading-relaxed text-muted-foreground lg:text-[14.5px]">{lead}</p>
            </div>
            {/* Reichlich Luft unten: Die Fußzeile liegt fest, der Inhalt
                scrollt darunter durch — mit knappem Abstand endete die letzte
                Zeile am Telefon mittendrin und sah kaputt aus statt scrollbar. */}
            <div className="mt-4 pb-8 lg:mt-0 lg:pb-4">{children}</div>
          </div>
        </div>
      </div>
      <div className={cn(SPALTE, "px-[18px] pt-3 lg:px-8")}>
        <div className={ZWEISPALTIG}>
          <div className="hidden lg:block" />
          {/* Am Desktop steht die Aktion rechts unter ihrer eigenen Spalte —
              ein Knopf über 680 px wäre keine Schaltfläche mehr, sondern ein Balken. */}
          <div className="lg:flex lg:justify-end">{footer}</div>
        </div>
      </div>
    </>
  );
}
