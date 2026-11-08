"use client";

import { createContext, useContext, useEffect, useMemo, useRef, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Bell, Check, ChevronDown, Landmark, Loader2, Mail, MapPin, Plus, SlidersHorizontal, Sparkles, X } from "lucide-react";
import { api } from "@/lib/api";
import { SETUP_QUERY_KEY, gemeldeterSetupSchritt, holeSetupStand } from "@/lib/onboarding-setup";
import { cn } from "@/lib/utils";
import { Button, Input, toast } from "@/components/ui";
import { Mascot, type MascotPose } from "@/components/mascot";
import { committeeExplains, committeeIcon, committeeImage, committeeRank, shortCommittee } from "@/lib/committees";
import { useAuth } from "@/lib/auth";
import { TopicSheet, type Described } from "@/components/topic-sheet";
import { merkeEinladung } from "@/lib/tour-einladung";
import { StadtteilKarteGrund } from "@/components/stadtteil-karte-grund";
import { useVollbildMelden } from "@/lib/vollbild";
import { useScrollRestUnten } from "@/lib/use-scroll-rand";
import { meldeChips, stadtthemaBild, stadtthemaChip } from "@/lib/onboarding-chips";
import {
  ONBOARDING_DONE_EVENT, ONBOARDING_FINISHED_EVENT, ONBOARDING_NEEDS_LOGIN_EVENT,
  imAppBereich, isFlowDeciding, isUsable, setFlowDeciding, setFlowVisible,
} from "@/lib/onboarding-state";

// Zustand, Bereichs-Liste und Ereignisse stehen seit 11/2026 in
// lib/onboarding-state.ts: Abzeichen, Tour-Einladung und Anmeldung brauchen
// sie, bevor dieser Assistent geladen ist (er kommt per next/dynamic, s.
// components/onboarding-gate.tsx). Hier weitergereicht für alte Importe.
export {
  ONBOARDING_DONE_EVENT, ONBOARDING_FINISHED_EVENT, ONBOARDING_NEEDS_LOGIN_EVENT,
  einrichtungLiefHier, isOnboardingVisible,
} from "@/lib/onboarding-state";

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
 *  Drei Dinge, die im Browser anders laufen als in der nativen iOS-App:
 *
 *  1. **Wer ihn zu sehen bekommt, entscheidet der Server** (`/onboarding/setup`,
 *     Feld `pending`). Im Browser wechselt man das Gerät, und ein zweiter
 *     Rechner finge mit dem localStorage allein von vorn an. Die Regel steht
 *     damit an einer Stelle für beide Frontends.
 *  2. **Der Auftakt begrüßt erst nach der Anmeldung** — davor tut das die
 *     Landingpage.
 *  3. **Der letzte Schritt fragt nach der E-Mail.** Im Browser gibt es keine
 *     Push-Erlaubnis (das Backend kennt nur APNs/FCM) — siehe `MailStep`.
 */

const DONE_KEY = "ratslotse.onboarding.done";
const STEP_KEY = "ratslotse.onboarding.step";

type Step = 0 | 1 | 2 | 3 | 4 | 5;
/** Schritt 5 ist kein Schritt im Pfad, sondern ein Auffangnetz: Er erscheint
 *  ausschließlich, wenn nach dem letzten Schritt WEDER ein Thema NOCH ein
 *  Gremium hinterlegt ist. Am 08.09.2026 traf das auf fünf von neun neuen
 *  Konten zu — und für die gibt es danach keinen einzigen Anlass mehr, sich
 *  je wieder bei ihnen zu melden. Deshalb zählt er nicht in `SCHRITTE` und
 *  steht nicht im Schritt-Pfad; er ist überspringbar wie alles andere. */
const HAKEN_SCHRITT = 5;

/** Der laufende Schritt, für das Gerüst. Als Kontext statt als Prop, weil ihn
 *  nur `StepShell` braucht — vier Schritt-Komponenten, die ihn bloß
 *  durchreichen, wären genau die Sorte Verdrahtung, die beim fünften Schritt
 *  jemand vergisst. */
const SchrittKontext = createContext<Step>(1);

/** Die Spalte, in der der Assistent steht. Am Telefon füllt sie den Schirm; am
 *  Desktop ist sie die Breite des Blatts (s. u.), auf dem der Schritt liegt.
 *  Kopfzeile, Inhalt und Fußleiste MÜSSEN dieselbe Klasse benutzen, sonst
 *  steht die Leiste neben ihrem eigenen Schritt. 1040 statt 980, damit die
 *  Antwortspalte rechts 650 px behält — genug für zwei Gremien nebeneinander. */
const SPALTE = "mx-auto w-full max-w-[1040px]";
/** Vier Schritte: Gremien, Themen, Stadtteil, Mitteilungen. Die App kennt den
 *  Stadtteil-Schritt (noch) nicht und läuft mit drei — deshalb steht die Zahl
 *  hier und nicht als `3` an fünf Stellen im Markup.
 *
 *  **Themen VOR Stadtteil** (seit 30.09.2026). Davor stand der Stadtteil an
 *  zweiter Stelle, und neue Konten nahmen fast nur Stadtteile: sieben von acht
 *  Konten seit dem 20.09., 44 von 62 Themen. Eine Karte mit einem Klick je
 *  Fläche schlägt jede Liste von Begriffen — kommt sie zuerst, ist der Mensch
 *  mit dem Thema-Sammeln fertig, bevor die Themen an der Reihe sind. */
const SCHRITTE = 4;
/** Am Desktop zweispaltig: links Lotti, die Frage und der Schritt-Pfad, rechts
 *  die Antwortfläche. Darunter (`lg` = 1024 px) bleibt es einspaltig. 280 statt
 *  320 für die Frage-Spalte: Vier Wörter Überschrift brauchen keine 320 px,
 *  und jeder Pixel davon fehlt rechts, wo die Arbeit passiert. */
const ZWEISPALTIG = "lg:grid lg:grid-cols-[280px_minmax(0,1fr)] lg:gap-10";

/** Den erreichten Schritt auch am Konto festhalten (fire-and-forget).
 *  Der lokale Speicher merkt sich den Stand fürs Gerät; erst der Server-Stand
 *  überlebt eine Neuinstallation — und nur er erlaubt es, nach zwei Tagen an
 *  eine liegengebliebene Einrichtung zu erinnern (scripts/remind_setup.py). */
function reportSetupStep(step: number, done = false) {
  api.post("/onboarding/setup", { step: gemeldeterSetupSchritt(step), done }).catch(() => {});
}

/** Server-Stand des Assistenten. `pending` beantwortet „ist er dran?" — die
 *  Regel steht im Backend (`Store.get_setup`), damit Web und App dieselbe
 *  Antwort bekommen und das Frontend nicht erst Themen und Abos zählen muss. */
// Typ, Schlüssel und Abruf stehen in lib/onboarding-setup.ts — sie werden auch
// dort gebraucht, wo dieser Assistent noch gar nicht geladen sein soll.

export function OnboardingFlow() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const [step, setStep] = useState<Step | null>(null);
  // Genau einmal je Durchlauf: Ohne die Merke riefe `go("done")` aus dem
  // Rückruf die Prüfung erneut auf — eine Schleife.
  const hakenGeprueft = useRef(false);
  // Solange die Prüfung läuft, zählt ein zweites „Fertig" nicht. Sonst ging
  // der zweite Klick (die Abfrage braucht einen Moment) an der Prüfung vorbei
  // direkt zu „done" — und wenn sie danach „kein Haken" meldete, stand der
  // Haken-Schritt ÜBER der Tour-Einladung (Browsertest, 06.10.2026).
  const hakenLaeuft = useRef(false);
  const rootRef = useRef<HTMLDivElement>(null);
  // In DIESER Sitzung abgeschlossen. Ohne den Riegel schöbe die noch im Cache
  // liegende Server-Antwort (`pending: true`) den Assistenten sofort wieder
  // hoch, sobald der Effekt erneut läuft — der Abschluss ist ja fire-and-forget.
  const fertig = useRef(false);

  const setup = useQuery({
    queryKey: SETUP_QUERY_KEY,
    queryFn: holeSetupStand,
    enabled: isUsable(user),
    staleTime: 60_000,
    retry: false,
  });

  const setupData = setup.data;
  useEffect(() => {
    // Erst wenn feststeht, ob jemand angemeldet ist — sonst hielte der Flow
    // einen angemeldeten Rückkehrer für abgemeldet und träte kurz beiseite.
    if (loading || fertig.current) return;

    // Ohne (nutzbares) Konto gibt es nichts einzurichten: Begrüßt wird auf
    // der Landingpage.
    if (!isUsable(user)) { setStep(null); return; }

    // Nur innerhalb der App — nicht über Landingpage oder Impressum.
    if (!imAppBereich(pathname)) { setStep(null); return; }

    // --- Angemeldet: der Server entscheidet ---
    if (!setupData) return;              // Antwort steht noch aus: nichts zeigen
    if (!setupData.pending) { setStep(null); return; }
    // Bis 4, nicht bis 3: Der letzte Schritt (Mitteilungen) IST ein Schritt,
    // an dem man aufhören kann. Die 3 hier hätte auch nach dem Server-Fix
    // dafür gesorgt, dass ein Wiedereinstieg beim Themen-Schritt landet — man
    // hätte ihn ein zweites Mal gemacht.
    setStep(Math.max(0, Math.min(4, setupData.step)) as Step);
  }, [user, loading, setupData, pathname]);

  /** Hat das Konto irgendetwas, woran sich eine Meldung hängen ließe? */
  const hatHaken = async (): Promise<boolean> => {
    try {
      const [themen, abos] = await Promise.all([
        api.get<TopicRow[]>("/topics"),
        api.get<{ subscriptions: string[] }>("/subscriptions"),
      ]);
      return themen.length > 0 || (abos.subscriptions?.length ?? 0) > 0;
    } catch {
      // Im Zweifel NICHT nachfragen: Ein Netzfehler darf keinen zusätzlichen
      // Schirm erzeugen, den niemand erwartet hat.
      return true;
    }
  };

  const go = (next: Step | "done") => {
    if (next === "done" && hakenLaeuft.current) return;
    if (next === "done" && !hakenGeprueft.current) {
      hakenGeprueft.current = true;
      hakenLaeuft.current = true;
      void hatHaken().then((ja) => {
        hakenLaeuft.current = false;
        if (ja) { go("done"); return; }
        try { localStorage.setItem(STEP_KEY, String(HAKEN_SCHRITT)); } catch { /* egal */ }
        setStep(HAKEN_SCHRITT as Step);
      });
      return;
    }
    if (next === "done") {
      fertig.current = true;
      try {
        localStorage.setItem(DONE_KEY, "1");
        localStorage.removeItem(STEP_KEY);
      } catch { /* Speicher voll/gesperrt — dann eben nochmal beim nächsten Start */ }
      // Lottis Einladung ist ab jetzt dran. Die Marke setzt der Assistent
      // selbst, nicht erst der Empfänger des Ereignisses unten: Der hängt in
      // der App-Hülle und ist in mehreren Momenten nicht gemountet (s.
      // lib/tour-einladung.ts). Ohne die Marke war die Gelegenheit einmalig
      // vorbei — genau so ist sie auf Prod verpufft.
      merkeEinladung("offen");
      setStep(null);
      if (isUsable(user)) reportSetupStep(3, true);
      // Reihenfolge ist Absicht: Erst nimmt die Einladung ihren Platz ein
      // (und meldet sich als offen), dann erst dürfen die Abzeichen prüfen,
      // ob sie sich zeigen dürfen — sie tun es dann nicht.
      window.dispatchEvent(new Event(ONBOARDING_FINISHED_EVENT));
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

  // Solange der Flow oben liegt, halten Abzeichen-Toasts still, und was er
  // verdient, wird hinterher nicht gefeiert (lib/onboarding-state.ts).
  useEffect(() => {
    setFlowVisible(step !== null);
    return () => { setFlowVisible(false); };
  }, [step]);

  // …und der Lotti-Knopf tritt ganz weg. Gemeldet wird erst, wenn der Flow
  // WIRKLICH steht — nicht schon, während er auf `/onboarding/setup` wartet
  // (`isFlowDeciding`): Bleibt diese Antwort aus, hinge der Knopf sonst
  // dauerhaft an einer Entscheidung, die nie fällt. Ein Wimpernschlag Knopf
  // vor dem Assistenten ist der bessere Ausfall als gar kein Knopf mehr.
  useVollbildMelden("onboarding", step !== null);

  // Und solange er noch überlegt, ebenfalls. Steht das Ergebnis fest und lautet
  // es „nicht zeigen", muss das Signal kommen, das die geparkten Abzeichen
  // freigibt — sonst warteten sie bis zum nächsten neuen Abzeichen.
  useEffect(() => {
    const wartet = !loading && isUsable(user) && !setupData && step === null
      && imAppBereich(pathname);
    const vorher = isFlowDeciding();
    setFlowDeciding(wartet);
    if (vorher && !wartet && step === null) {
      window.dispatchEvent(new Event(ONBOARDING_DONE_EVENT));
    }
    return () => { setFlowDeciding(false); };
  }, [loading, user, setupData, step, pathname]);

  if (step === null) return null;

  return (
    <SchrittKontext.Provider value={step}>
    {/* Ebene „flaeche": Der Auftakt ERSETZT die App-Hülle (deckend, inset-0),
        das Blatt „Thema anpassen" liegt eine Stufe darüber. Die Leiter steht in
        app/globals.css.

        Am Desktop liegt der Schritt als BLATT in der Fenstermitte — Radius 18,
        Rahmen, eigene Fußleiste —, nicht als Inhalt, der im Viewport schwebt
        (die „Bühne" aus DESIGNSPRACHE §4). Vorher war das Gerüst auf allen
        Breiten dasselbe: Inhalt oben, Knopf an der Unterkante des Fensters —
        und bei einem kurzen Schritt wie der Zustellung blieb dazwischen ein
        leeres Drittel des Bildschirms (Tims Befund, 01.09.2026). Ein Blatt ist
        so hoch wie sein Inhalt und steht mittig; ist der Inhalt länger als das
        Fenster, scrollt er im Blatt, die Fußleiste bleibt. Der Auftakt bekommt
        kein Blatt — er ist ein Moment, keine Seite. */}
    <div ref={rootRef} className={cn(
      "fixed inset-0 z-[var(--level-flaeche)] flex flex-col bg-background",
      "pb-[calc(1.25rem+env(safe-area-inset-bottom))] pt-[calc(0.75rem+env(safe-area-inset-top))]",
      step > 0 && "lg:flex-row lg:items-center lg:justify-center lg:p-6 xl:p-10",
    )}>
      {step === 0 ? <Welcome onNext={() => go(1)} /> : (
        <section aria-label={step === HAKEN_SCHRITT
            ? "Einrichtung, letzter Hinweis"
            : `Einrichtung, Schritt ${step} von ${SCHRITTE}`}
          className={cn(
            "flex min-h-0 flex-1 flex-col",
            "lg:max-h-full lg:w-full lg:max-w-[1040px] lg:flex-none lg:overflow-hidden",
            "lg:rounded-[18px] lg:border lg:border-border lg:bg-card lg:shadow-[0_1px_2px_rgba(0,0,0,0.04)]",
          )}>
          {/* Kopfzeile: am Telefon die Fortschrittssegmente, am Desktop nur ein
              stiller Mono-Kicker — dort trägt der Schritt-Pfad in der linken
              Spalte den Fortschritt, und zwei Anzeigen für dieselbe Sache
              übereinander wären eine zu viel. */}
          {/* Auf dem Auffangnetz KEINE Kopfzeile: Es ist kein Schritt im Pfad,
              und „Schritt 5 von 4" wäre schlicht falsch. Sein „Später" steht
              in der Fußleiste, ein zweites „Überspringen" daneben wären zwei
              Wege für dieselbe Handlung. */}
          <div className={cn(SPALTE, "px-[18px] lg:px-8 lg:pt-5",
                             step === HAKEN_SCHRITT && "hidden")}>
            <div className="flex items-center gap-3">
              {/* Zurück (10/2026): Bis dahin gab es nur „Überspringen" und
                  „Weiter" — wer sich im Themen-Schritt verklickt hatte, kam
                  nicht mehr zu den Ausschüssen. Die Schritte laden ihren Stand
                  vom Konto, eine Wahl geht beim Zurückgehen also nicht verloren. */}
              {step > 1 && step <= SCHRITTE && (
                <button type="button" onClick={() => go((step - 1) as Step)}
                  className="inline-flex shrink-0 items-center gap-1 py-1 text-[13px] text-muted-foreground transition-colors hover:text-foreground">
                  <ArrowLeft className="h-3.5 w-3.5" aria-hidden /> Zurück
                </button>
              )}
              {/* Segmente statt eines Laufbalkens: Man sieht, wie viele
                  Schritte es überhaupt sind. */}
              <div className="flex flex-1 gap-1.5 lg:hidden" role="progressbar"
                aria-valuenow={step} aria-valuemin={1} aria-valuemax={SCHRITTE}
                aria-label={`Schritt ${step} von ${SCHRITTE}`}>
                {[1, 2, 3, 4].slice(0, SCHRITTE).map((n) => (
                  <span key={n} className={cn("h-1 flex-1 rounded-full transition-colors duration-300",
                    n <= step ? "bg-primary" : "bg-muted")} />
                ))}
              </div>
              <Kicker className="hidden flex-1 lg:flex">Schritt {step} von {SCHRITTE}</Kicker>
              <button type="button" onClick={() => go(step >= SCHRITTE ? "done" : ((step + 1) as Step))}
                className="shrink-0 py-1 text-[13px] text-muted-foreground transition-colors hover:text-foreground">
                Überspringen
              </button>
            </div>
          </div>

          {step === 1 && <CommitteeStep onNext={() => go(2)} />}
          {/* Die Themen kommen zuerst (s. `SCHRITTE`), der Stadtteil danach als
              eigener Schritt: Er ist die Angabe, die fast alle machen wollen —
              und dort stehen dann auch die Vorschläge „aus deinen Stadtteilen".
              Als Beiwerk im Themen-Schritt (bis 09/2026) ging der Stadtteil
              unter; vor den Themen (bis 30.09.2026) verdrängte er sie. */}
          {step === 2 && <TopicStep onNext={() => go(3)} />}
          {step === 3 && <StadtteilStep onNext={() => go(4)} />}
          {/* Schritt 4 fragt, ob Lotti sich melden soll — im Browser per
              E-Mail, eine Push-Erlaubnis gibt es dort nicht. */}
          {step === 4 && <MailStep onDone={() => go("done")} />}
          {step === HAKEN_SCHRITT && <HakenStep onDone={() => go("done")} />}
        </section>
      )}
    </div>
    </SchrittKontext.Provider>
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
      title: "Bleib informiert", sub: "Bescheid bei neuen Beschlüssen" },
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
      lead="Du bekommst eine Mitteilung, sobald eine Tagesordnung erscheint. Diese Auswahl kannst du später ändern."
      pose="point"
      mehr="Weitere Gremien"
      footer={
        <Button className="w-full lg:w-auto lg:min-w-44" onClick={onNext}>
          {active.length > 0 ? `${active.length} abonniert · Weiter` : "Weiter"}
        </Button>
      }
    >
      {committees.isLoading && <p className="text-sm text-muted-foreground">Gremien werden geladen …</p>}
      {/* Zwei Spalten, sobald die Antwortfläche 576 px hergibt (Container-
          Query, nicht Fensterbreite — DESIGNSPRACHE §4). Zwölf Gremien
          untereinander waren zwölf Kacheln à 125 px: Man scrollte durch eine
          Liste, für die der Platz daneben leer stand. Nebeneinander passen alle
          auf einen Schirm, und die Wahl wird ein Überblick statt einer Reise. */}
      <div className="@container">
        <div className="grid gap-2 @xl:grid-cols-2">
          {shown.map((c) => {
            const on = active.includes(c);
            const explain = committeeExplains(c);
            return (
              <button key={c} type="button" aria-pressed={on}
                onClick={() => toggle.mutate({ committee: c, on: !on })}
                className={cn(
                  "relative flex items-center gap-3 rounded-xl border p-3 pr-9 text-left transition-colors",
                  // Auf dem Blatt (Desktop) eine Stufe leiser als das Blatt
                  // selbst — Container im Container; am Telefon, wo kein Blatt
                  // ist, bleibt die Kachel weiß auf der Seite.
                  on ? "border-primary bg-primary/5"
                     : "border-border bg-card hover:bg-muted/60 lg:bg-background lg:hover:bg-muted/50",
                )}>
                <GremiumZeichen committee={c} aktiv={on} />
                <span className="min-w-0">
                  <span className="block text-[13.5px] font-semibold leading-snug text-foreground">{shortCommittee(c)}</span>
                  {/* Ohne den Satz ist das eine Liste von Amtsbezeichnungen. */}
                  {explain && <span className="mt-0.5 block text-[12px] leading-snug text-muted-foreground">{explain}</span>}
                </span>
                {/* Das Häkchen sitzt an der Kante, nicht in der Zeile: Das
                    Zeichen links trägt schon den Zustand (gefüllt = gewählt),
                    das Häkchen bestätigt ihn nur — für alle, denen eine
                    Farbfläche allein zu wenig sagt. */}
                {on && (
                  <span className="absolute right-3 top-3 flex h-4 w-4 items-center justify-center rounded-full bg-primary text-primary-foreground">
                    <Check className="h-2.5 w-2.5" strokeWidth={3} />
                  </span>
                )}
              </button>
            );
          })}
        </div>
      </div>
    </StepShell>
  );
}

/** Lotti mit einem Requisit aus dem Sachbereich des Gremiums (`public/gremien/`);
 *  gewählt = Ring in der Primärfarbe. Gremien ohne Bild und unbekannte behalten
 *  das Zeichen auf getönter Scheibe (Primär-Tint /8, DESIGNSPRACHE §2; gewählt =
 *  gefüllt). Eine eigene Komponente, damit keine Kachel davon weiß. */
function GremiumZeichen({ committee, aktiv }: { committee: string; aktiv: boolean }) {
  const Icon = committeeIcon(committee);
  const bild = committeeImage(committee);
  if (bild) {
    // 80 px und leicht herangezoomt: Bei 56 px war Lotti samt Requisit kaum zu
    // erkennen, und im Bild selbst füllt das Motiv nur rund zwei Drittel
    // (Tims Befund 08.11.2026). Der Zoom schneidet nur Hintergrund ab — die
    // Motive halten zum Rand gut ein Sechstel Abstand.
    return (
      <span aria-hidden className={cn(
        "block h-20 w-20 shrink-0 overflow-hidden rounded-xl bg-muted transition-shadow",
        aktiv && "ring-2 ring-primary ring-offset-2 ring-offset-background",
      )}>
        {/* Feste 256-px-Dateien aus dem Repo; `next/image` optimiert hier nichts (s. next.config.mjs). */}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={bild} alt="" width={80} height={80} loading="lazy" decoding="async"
          className="h-full w-full scale-[1.1] object-cover" />
      </span>
    );
  }
  return (
    <span aria-hidden className={cn(
      "flex h-9 w-9 shrink-0 items-center justify-center rounded-[11px] transition-colors",
      aktiv ? "bg-primary text-primary-foreground" : "bg-primary/[0.08] text-primary",
    )}>
      <Icon className="h-[18px] w-[18px]" strokeWidth={2} />
    </span>
  );
}

/* -------------------------------------------------- Schritt 3: Stadtteil --- */

type Ortsbereich = {
  place_id: string; name: string; kind?: string;
  description?: string | null; count?: number;
};

/** Die Stadtteile, zu denen es überhaupt Beschlüsse gibt. Zwei Schritte
 *  brauchen sie (Auswahl und Vorschläge), deshalb ein gemeinsamer Query-Key.
 *
 *  **Nur `kind === "local_area"`.** `/council/districts` liefert für den
 *  Beschlussfilter auch die kuratierten Teilorte mit — „Alte Fleiwa",
 *  „Technologiepark Oldenburg", „Eversten Holz". Im Beschlussfilter ist das
 *  richtig, hier nicht: Auf dem Prod-Bestand standen dadurch 40 Pillen unter
 *  einer Karte mit 31 Flächen, und „Alte Fleiwa" als Stadtteil anzubieten ist
 *  schlicht falsch. Die 31 flächendeckenden Ortsbereiche sind die Auswahl. */
function useOrtsbereiche() {
  return useQuery({
    queryKey: ["council-districts"],
    queryFn: () => api.get<{ districts: Ortsbereich[] }>("/council/districts")
      .then((d) => d.districts
        .filter((o) => o.kind === "local_area")
        .sort((a, b) => a.name.localeCompare(b.name, "de"))),
    staleTime: 10 * 60_000,
  });
}

/** Welche Stadtteile hat dieses Konto gewählt?
 *
 *  Abgeleitet statt gemerkt: Ein gewählter Stadtteil IST ein Thema (nur so löst
 *  er Hinweise aus), und die Themen stehen ohnehin auf dem Server. Damit
 *  überlebt die Auswahl einen Neuladen mitten im Ablauf — ein Zustand in React
 *  täte das nicht, und der Assistent nimmt seinen Stand sonst überall vom
 *  Server. */
function gewaehlteOrtsbereiche(topics: { name: string }[], orte: Ortsbereich[]): Ortsbereich[] {
  return orte.filter((o) => topics.some((t) => t.name.toLowerCase() === o.name.toLowerCase()));
}

/** Die Beschreibung, an der der Wächter später misst. Dieselbe Formulierung
 *  wie in der App — sie darf nicht generisch sein, sonst trifft das Thema
 *  entweder alles oder nichts. */
function ortsBeschreibung(ort: Ortsbereich): string {
  const detail = (ort.description ?? "").trim();
  return detail
    ? `${detail} Neue Beschlüsse, Planungen und Maßnahmen mit Bezug zu ${ort.name}.`
    : `Neue Beschlüsse, Planungen und Maßnahmen des Oldenburger Stadtrats mit Bezug zu ${ort.name}.`;
}

/** Mehr als so viele Stadtteile nimmt der Assistent nicht an. Eine Karte mit
 *  einem Klick je Fläche ist die leichteste Wahl im ganzen Ablauf: Am
 *  30.09.2026 standen bei einem Konto acht Stadtteile und sonst nichts. Drei
 *  reichen für den Start, mehr lassen sich später unter „Themen" ergänzen —
 *  dort ist die Grenze keine. */
const MAX_STADTTEILE = 3;

/** Die Vorschläge „aus deinen Stadtteilen" — je gewähltem Stadtteil ein Aufruf,
 *  einer nach dem anderen.
 *
 *  EIN Aufruf JE STADTTEIL statt einem für alle: Der Endpunkt beurteilt jeden
 *  noch nie gesehenen Vorschlag einmal per Modell; bei zwei, drei Stadtteilen
 *  wartete man vorher auf den letzten, bevor der erste erschien (Tims Befund,
 *  03.09.2026). Getrennt gefragt steht jede Gruppe da, sobald sie fertig ist.
 *
 *  NACHEINANDER, nicht gleichzeitig: Jeder Aufruf bekommt mit `exclude` zu
 *  hören, was oben schon steht — ohne das stünde dieselbe Baustelle zweimal.
 *  ZWEI je Stadtteil, ohne Nachbarschaft: Vier Stadtteile mit je sechs Chips
 *  plus „direkt nebenan" waren eine Wand aus Straßennamen. */
function useStadtteilVorschlaege(stadtteile: Ortsbereich[], bereit: boolean) {
  const qc = useQueryClient();
  const ortsIds = stadtteile.map((o) => o.place_id);
  const schluessel = (id: string, gesehen: string[]) =>
    ["topic-suggestions", "district", id, JE_STADTTEIL, gesehen.join("|")] as const;
  const namenVon = (g: VorschlagsGruppe | null | undefined) =>
    g ? g.suggestions.map((v) => v.name) : [];
  // Die Kette WÄHREND des Renderns aufbauen: Was schon da ist, steht im Cache
  // — und `useQueries` hängt an genau diesen Schlüsseln, der nächste Render
  // verlängert die Kette also von selbst.
  let gesehen: string[] = [];
  let wartetNoch = false;                 // ab der ersten offenen Gruppe
  const ketten = ortsIds.map((id) => {
    const key = schluessel(id, gesehen);
    const daten = qc.getQueryData<VorschlagsGruppe | null>(key);
    const eintrag = { id, key, exclude: gesehen, enabled: bereit && !wartetNoch };
    if (daten === undefined) wartetNoch = true;
    else gesehen = [...gesehen, ...namenVon(daten)];
    return eintrag;
  });
  const gruppenQueries = useQueries({
    queries: ketten.map((k) => ({
      // Die Stadtteile UND das schon Gezeigte gehören in den Schlüssel: Wer
      // zurückgeht und umwählt, bekäme sonst die Vorschläge der alten Auswahl
      // aus dem Cache.
      queryKey: k.key,
      queryFn: () => api.get<VorschlagsAntwort>(
        `/topics/suggestions?district=${encodeURIComponent(k.id)}&citywide=0&city=0&limit=${JE_STADTTEIL}&nearby=0`
        + k.exclude.map((n) => `&exclude=${encodeURIComponent(n)}`).join(""))
        .then((d) => d.districts[0] ?? null),
      // Erst fragen, wenn die Auswahl feststeht.
      enabled: k.enabled,
    })),
  });
  const gruppen = stadtteile.map((ort, i) => ({ ort, query: gruppenQueries[i] }));
  return {
    nochUnterwegs: gruppen.filter((g) => g.query?.isPending).map((g) => g.ort.name),
    // Alle Vorschläge in EINER Reihe, jeder mit seinem Ort.
    chips: gruppen.flatMap(({ ort, query }): Vorschlag[] =>
      (query?.data?.suggestions ?? []).map((v) => ({ ...v, place: ort.name }))),
    stille: gruppen.filter((g) => g.query?.data && g.query.data.suggestions.length === 0)
      .map((g) => g.ort.name),
    weitestesFenster: Math.max(0, ...gruppen.map((g) => g.query?.data?.months ?? 0)),
    anzahl: gruppen.length,
  };
}

/** Schritt 3 — die Stadtteile, die jemanden interessieren.
 *
 *  **Die Frage lautet bewusst nicht „wo wohnst du?".** Das wäre eine Frage nach
 *  der Wohnadresse, und die braucht Ratslotse nicht: Es geht um Interesse, nicht
 *  um Meldedaten. Wer im Dobbenviertel wohnt und die Baustelle in Osternburg
 *  verfolgt, soll beides angeben können — deshalb ist die Auswahl mehrfach.
 */
function StadtteilStep({ onNext }: { onNext: () => void }) {
  const qc = useQueryClient();
  const [fehler, setFehler] = useState<string | null>(null);
  // Was gerade unterwegs ist, je Stadtteil — und WOHIN (an oder aus). Die
  // Anzeige folgt sofort dieser Absicht, nicht erst der Server-Antwort.
  const [unterwegs, setUnterwegs] = useState<Map<string, boolean>>(() => new Map());

  const orte = useOrtsbereiche();
  const topics = useQuery({ queryKey: ["topics"], queryFn: () => api.get<TopicRow[]>("/topics") });
  const [anlegend, setAnlegend] = useState<string | null>(null);
  const gemeldet = useRef({ schritt: false, vorschlaege: false });
  // Dass der Schritt angeboten wurde, zählt einmal je Besuch — nicht je Fläche.
  useEffect(() => {
    if (gemeldet.current.schritt) return;
    gemeldet.current.schritt = true;
    meldeChips(["district"]);
  }, []);

  const liste = orte.data ?? [];
  const meine = topics.data ?? [];
  const bestaetigt = gewaehlteOrtsbereiche(meine, liste);
  // Serverstand plus Absicht: Ein Klick zählt ab sofort, nicht erst, wenn der
  // Server geantwortet hat und die Themen neu geladen sind.
  const namen = useMemo(() => {
    const n = new Set(bestaetigt.map((o) => o.name));
    for (const [name, an] of unterwegs) { if (an) n.add(name); else n.delete(name); }
    return n;
  }, [bestaetigt, unterwegs]);
  const gewaehlt = useMemo(() => liste.filter((o) => namen.has(o.name)), [liste, namen]);
  const auswaehlbar = useMemo(() => new Set(liste.map((o) => o.name)), [liste]);
  const bereit = !topics.isPending && !orte.isPending;
  // An der AUSWAHL, nicht am Serverstand: Bis 11/2026 fragten die Vorschläge
  // erst, wenn das Anlegen des Stadtteils zurück war — und das gleicht den
  // Stadtteil sofort gegen den Bestand ab (`_erstabgleich`, Cross-Encoder).
  // Man sah also erst den Stadtteil laden und danach die Vorschläge (Tims
  // Befund 08.11.2026). Jetzt laufen beide nebeneinander.
  const vorschlaege = useStadtteilVorschlaege(gewaehlt, bereit);
  useEffect(() => {
    if (vorschlaege.chips.length === 0 || gemeldet.current.vorschlaege) return;
    gemeldet.current.vorschlaege = true;
    meldeChips(["district_suggestion"]);
  }, [vorschlaege.chips.length]);

  /** An/aus je Stadtteil — optimistisch und je Stadtteil für sich.
   *
   *  Ein Stadtteil IST ein Thema, und ein neues Thema gleicht der Server sofort
   *  gegen den Bestand ab (`_erstabgleich`): warm eine halbe Sekunde, nach
   *  einem Neustart des Dienstes bis zu zwanzig, weil erst die Modelle laden.
   *  Vorher wartete die Pille genau so lange, bis sie umsprang, und ein
   *  globaler Riegel sperrte jeden weiteren Klick — wer drei Stadtteile
   *  wählen wollte, wartete dreimal (Tims Befund, 02.09.2026). Jetzt springt
   *  die Anzeige sofort um, jeder Stadtteil hat seinen eigenen Wartezustand,
   *  und die Klicks laufen nebeneinander. Erst wenn der Server NEIN sagt,
   *  fällt die Anzeige zurück — mit einem Satz dazu. */
  const umschalten = (name: string) => {
    if (unterwegs.has(name)) return;
    const ort = liste.find((o) => o.name === name);
    if (!ort) return;
    const an = !namen.has(name);
    if (an && namen.size >= MAX_STADTTEILE) {
      setFehler(`Für den Anfang reichen drei Stadtteile — so bleibt die Übersicht ruhig. Nimm einen heraus, um ${name} zu wählen; weitere kannst du später unter „Themen" ergänzen.`);
      return;
    }
    if (an) meldeChips([], ["district"]);
    setUnterwegs((m) => new Map(m).set(name, an));
    setFehler(null);
    void (async () => {
      try {
        const vorhanden = meine.find((t) => t.name.toLowerCase() === name.toLowerCase());
        if (!an && vorhanden) await api.del(`/topics/${vorhanden.id}`);
        else if (an && !vorhanden) await api.post("/topics", { name: ort.name, description: ortsBeschreibung(ort) });
        // Erst den Serverstand holen, DANN die Absicht fallen lassen — sonst
        // flackert die Pille kurz zurück, bevor die neue Liste da ist.
        // Die Vorschläge NICHT neu holen: Ein Stadtteil-Thema verändert sie
        // nicht (Ortsnamen zählen beim Aussortieren bewusst nicht mit, s.
        // `topic_suggestions`), und das Neuholen ließ jede Gruppe nach dem
        // Speichern ein zweites Mal laden.
        await qc.invalidateQueries({ queryKey: ["topics"] });
      } catch {
        setFehler(`${name} ließ sich gerade nicht ${an ? "anlegen" : "entfernen"}. Versuch es gleich noch einmal.`);
      } finally {
        setUnterwegs((m) => { const n = new Map(m); n.delete(name); return n; });
      }
    })();
  };

  /** Eine Karte aus „Aus deinen Stadtteilen" anlegen. Die Beschreibung kommt
   *  vom Server mit; ein Modellaufruf wie beim eigenen Thema braucht es nicht. */
  const waehleVorschlag = async (v: Vorschlag) => {
    if (anlegend) return;
    setAnlegend(v.name);
    setFehler(null);
    meldeChips([], ["district_suggestion"]);
    try {
      await api.post("/topics", { name: v.name, description: v.description });
      await qc.invalidateQueries({ queryKey: ["topics"] });
    } catch {
      setFehler("Das Thema konnte gerade nicht angelegt werden. Versuch es gleich nochmal.");
    } finally {
      setAnlegend(null);
    }
  };

  return (
    <StepShell
      title="Welche Stadtteile interessieren dich?"
      // Die Grenze von drei steht hier bewusst NICHT: „Bis zu drei" und
      // „2 von 3" lasen sich wie eine Aufgabe, drei zu wählen (Tims Befund
      // 08.11.2026). Sie meldet sich erst, wenn jemand an sie stößt.
      lead="Zum Beispiel der, in dem du wohnst — aber genauso einer, in dem gerade etwas passiert. Lotti meldet neue Beschlüsse und Planungen von dort. Alles jederzeit änderbar."
      pose="point"
      footer={
        <Button className="w-full lg:w-auto lg:min-w-44" onClick={onNext} disabled={unterwegs.size > 0 || !!anlegend}>
          {unterwegs.size > 0 ? <><Loader2 className="h-4 w-4 animate-spin" /> Speichert …</>
            : gewaehlt.length === 0 ? "Überspringen"
              : gewaehlt.length === 1 ? `${gewaehlt[0].name} · Weiter`
                : `${gewaehlt.length} Stadtteile · Weiter`}
        </Button>
      }
    >
      {/* Die Karte am Desktop, wo Platz ist. Die Liste steht auf JEDER Breite
          da — sie ist nicht bloß der Ersatz fürs kleine Fenster, sondern auch
          der Weg für Tastatur und Screenreader. */}
      <StadtteilKarteGrund className="hidden h-[400px] lg:block" gewaehlt={namen}
        auswaehlbar={auswaehlbar} onWaehlen={umschalten} />

      <div className={cn("flex flex-wrap gap-1.5", liste.length && "lg:mt-4")}>
        {liste.map((o) => {
          const an = namen.has(o.name);
          return (
            // Nur DIESE Pille ist gesperrt, solange sie unterwegs ist — die
            // anderen bleiben klickbar. Sie zeigt sofort den Zielzustand samt
            // Häkchen und atmet, bis der Server ihn bestätigt. Bis 11/2026
            // stand hier ein 12-px-Spinner statt des Häkchens — „so klein,
            // dass er nicht wirklich schön aussieht" (Tim, 08.11.2026).
            <button key={o.place_id} type="button" aria-pressed={an} aria-busy={unterwegs.has(o.name) || undefined}
              disabled={unterwegs.has(o.name)}
              onClick={() => umschalten(o.name)}
              className={cn(
                "inline-flex items-center gap-1.5 rounded-full border px-3 py-[6px] text-[12.5px] transition-colors",
                an ? "border-primary bg-primary font-semibold text-primary-foreground"
                   : "border-border bg-card text-foreground hover:bg-muted",
                unterwegs.has(o.name) && "animate-pulse",
              )}>
              {an && <Check className="h-3 w-3" />}
              {o.name}
            </button>
          );
        })}
      </div>

      {fehler && (
        <p role="status" className="mt-3 rounded-lg border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs text-amber-800 dark:text-amber-300">
          {fehler}
        </p>
      )}
      {gewaehlt.length > 0 ? (
        <p className="mt-3 flex items-start gap-1.5 text-xs text-primary">
          <Check className="mt-px h-3.5 w-3.5 shrink-0" />
          <span>
            {gewaehlt.map((o) => o.name).join(", ")} {gewaehlt.length === 1 ? "steht" : "stehen"} ab
            jetzt unter „Deine Themen". Darunter siehst du, was dort gerade läuft.
          </span>
        </p>
      ) : (
        <p className="mt-3 text-xs text-muted-foreground">
          Ohne Angabe geht es auch — die Themen aus dem Schritt davor bleiben stadtweit.
        </p>
      )}

      {/* „Aus deinen Stadtteilen": ein bis zwei Vorschläge je gewähltem
          Stadtteil, jeder mit dem Grund, warum er dort hängt. Stand bis
          30.09.2026 im Themen-Schritt; er folgt dem Stadtteil dorthin, wo
          der gewählt wird. Jede Karte erscheint, sobald IHR Aufruf zurück ist. */}
      {vorschlaege.anzahl > 0 && (
        <div className="mt-5">
          <Kicker>
            <MapPin className="h-3 w-3" />
            Aus deinen Stadtteilen
            {/* Zeitraum dazuschreiben, sobald es mehr als ein Jahr war. In
                ruhigen Stadtteilen reicht ein Jahr nicht; das stumm zu weiten
                hieße, Aktualität zu behaupten. */}
            {vorschlaege.weitestesFenster > 12 && (
              <span className="font-sans text-[11px] font-medium normal-case tracking-normal text-muted-foreground">
                · bis zu {Math.round(vorschlaege.weitestesFenster / 12)} Jahre zurück
              </span>
            )}
          </Kicker>
          {vorschlaege.chips.length > 0
            ? <OrtsVorschlaege vorschlaege={vorschlaege.chips} vorhanden={meine}
                busy={!!anlegend} onWaehlen={(v) => void waehleVorschlag(v)} />
            : vorschlaege.nochUnterwegs.length > 0
              ? <KartenPlatzhalter anzahl={JE_STADTTEIL * vorschlaege.anzahl} /> : null}
          {/* Leere Stadtteile ausdrücklich benennen statt sie wegzulassen —
              sonst sähe es aus, als hätte der Schritt etwas verschluckt. */}
          {vorschlaege.stille.length > 0 && (
            <p className="mt-2 text-xs text-muted-foreground">
              Im Rat {vorschlaege.stille.length === 1 ? "war" : "waren"} {vorschlaege.stille.join(" und ")} zuletzt kaum
              ein Thema. {vorschlaege.stille.length === 1 ? "Der Stadtteil bleibt" : "Die Stadtteile bleiben"} trotzdem
              beobachtet — Lotti meldet sich, sobald etwas kommt.
            </p>
          )}
          {vorschlaege.nochUnterwegs.length > 0 && (
            // Ohne Spinner: Die Platzhalter-Karten darüber zeigen schon, dass
            // gleich etwas kommt; der Satz sagt nur noch, was.
            <p role="status" className="mt-3 text-xs text-muted-foreground">
              Lotti liest noch, was in {vorschlaege.nochUnterwegs.join(" und ")} läuft — du kannst
              schon auswählen.
            </p>
          )}
        </div>
      )}
    </StepShell>
  );
}

/* ----------------------------------------------------- Schritt 2: Themen --- */

type TopicRow = {
  id: number; name: string; description: string;
  /** Schlüssel des kuratierten Stadtthemas (Bild unter `public/themen/`). */
  image_key?: string | null;
  decision_count?: number; decision_count_capped?: boolean; matched?: boolean;
  /** Treffer der letzten zwölf Monate — die Zahl, die dieser Schritt zeigt.
   *  Die Gesamtzahl (`decision_count`) steht auf der Themen-Karte. */
  hits_12m?: number;
};

function TopicStep({ onNext }: { onNext: () => void }) {
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  // Der Name, der gerade angelegt wird: Er steht sofort als Zeile unter
  // „Deine Themen", während der Server die Beschreibung schreibt und den
  // Bestand abgleicht — das dauert je nach Modell zwei bis fünf Sekunden,
  // und vorher sah man in der Zeit gar nichts (Tims Befund, 02.09.2026).
  const [anlegend, setAnlegend] = useState<string | null>(null);
  const [warn, setWarn] = useState<string | null>(null);
  // Kein Fehler, sondern eine Auskunft: Das Thema IST angelegt, der Rat hat nur
  // noch nichts dazu entschieden. Darum eigene, ruhige Farbe statt Warngelb.
  const [note, setNote] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const [editing, setEditing] = useState<TopicRow | null>(null);
  const topics = useQuery({
    queryKey: ["topics"],
    queryFn: () => api.get<TopicRow[]>("/topics"),
  });
  const orte = useOrtsbereiche();
  // Stadtteile, die schon gewählt sind (Zurück aus dem nächsten Schritt), stehen
  // als Themen in der Liste — die Wahl selbst passiert erst im Schritt danach.
  const stadtteile = gewaehlteOrtsbereiche(topics.data ?? [], orte.data ?? []);
  const bereit = !topics.isPending;
  // Die Stadtthemen sind der Kern des Schritts (seit 03.09.2026): Radverkehr
  // oder Kitas holen ab, wo eine Straße aus der Entitäts-Erkennung niemandem
  // etwas sagt (Tims Befund: „schreckt eher ab"). Sie kosten kein Modell, nur
  // eine Zählung, und stehen deshalb sofort da.
  const stadtQuery = useQuery({
    queryKey: ["topic-suggestions", "city"],
    queryFn: () => api.get<VorschlagsAntwort>("/topics/suggestions?citywide=0&city=1")
      .then((d) => d.city),
    enabled: bereit,
  });
  // Was angeboten wurde, zählt einmal je Besuch des Schritts.
  const angebotGemeldet = useRef(false);
  useEffect(() => {
    if (angebotGemeldet.current || !stadtQuery.data || stadtQuery.data.length === 0) return;
    angebotGemeldet.current = true;
    meldeChips(stadtQuery.data.filter((v) => v.key).map((v) => stadtthemaChip(v.key!)));
  }, [stadtQuery.data]);
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
  const add = async (topicName: string) => {
    const clean = topicName.trim();
    if (clean.length < 2 || busy) return;
    setBusy(true);
    setAnlegend(clean);
    setWarn(null);
    setNote(null);
    try {
      const d = await api.post<Described>("/topics/describe", { name: clean });
      if (d.verdict === "ungeeignet") {
        setWarn(d.reason || "Das sieht nicht nach einem Thema des Oldenburger Stadtrats aus.");
        return;
      }
      // `d.matches` ist die Gesamtzahl seit 2018 — sie steht hier bewusst
      // NICHT in der Zeile. Bis die frische Themenliste da ist (eine
      // Sekunde später, mit `hits_12m`), bleibt die Zeile lieber ohne Zahl
      // als mit einer aus einem anderen Zeitraum.
      if (d.verdict === "plausibel") {
        setNote(`Über „${clean}" hat der Rat bisher nichts entschieden — Lotti meldet sich, sobald es so weit ist.`);
      }
      await api.post("/topics", { name: clean, description: d.description });
      setName("");
      // Erst die Liste holen, dann die Vorschau-Zeile wegnehmen — sonst
      // verschwindet das Thema für einen Moment, bevor es wiederkommt.
      await qc.invalidateQueries({ queryKey: ["topics"] });
      // Die Vorschläge nicht neu holen: Die Kacheln stehen fest, ihr Häkchen
      // kommt aus der Themenliste.
    } catch {
      setWarn("Das Thema konnte gerade nicht angelegt werden. Versuch es gleich nochmal.");
    } finally {
      setBusy(false);
      setAnlegend(null);
    }
  };

  const mine = topics.data ?? [];

  // Die Stadtthemen-Kacheln sind Umschalter, jede für sich: was gerade
  // unterwegs ist und WOHIN (an oder aus) — dieselbe Grammatik wie die
  // Stadtteil-Pillen. Bis 11/2026 teilten sie `busy` mit dem Formular: Ein
  // Klick sperrte alle Kacheln, bis der Server fertig war, und das dauerte,
  // solange jedes Thema auf den Cross-Encoder wartete (Tims Befund
  // 08.11.2026). Ein Stadtthema braucht seitdem kein Modell mehr
  // (`council.city_topics.treffer`), und mehrere dürfen gleichzeitig
  // unterwegs sein.
  const [stadtLaeufe, setStadtLaeufe] = useState<ReadonlyMap<string, boolean>>(() => new Map());
  const umschaltenStadtthema = async (v: Vorschlag) => {
    const clean = v.name.trim();
    if (stadtLaeufe.has(clean)) return;
    const vorhanden = mine.find((t) => t.name === clean);
    const an = !vorhanden;
    if (an && v.key) meldeChips([], [stadtthemaChip(v.key)]);
    setStadtLaeufe((m) => new Map(m).set(clean, an));
    setWarn(null);
    try {
      // Die Beschreibung der Kachel unverändert mitschicken: Daran erkennt
      // der Server das Stadtthema und nimmt dessen Liste statt des Modells.
      if (vorhanden) await api.del(`/topics/${vorhanden.id}`);
      else await api.post("/topics", { name: clean, description: v.description });
      // Erst den Serverstand holen, DANN die Absicht fallen lassen — sonst
      // flackert die Kachel kurz zurück, bevor die neue Liste da ist.
      await qc.invalidateQueries({ queryKey: ["topics"] });
    } catch {
      setWarn(`„${clean}“ ließ sich gerade nicht ${an ? "anlegen" : "entfernen"}. Versuch es gleich nochmal.`);
    } finally {
      setStadtLaeufe((m) => {
        const rest = new Map(m);
        rest.delete(clean);
        return rest;
      });
    }
  };

  // Ein Stadtthema steht NUR an seiner Kachel: Häkchen heißt gewählt,
  // darunter „anpassen". Bis 11/2026 stand es oben in „Deine Themen" ein
  // zweites Mal, und die Liste wiederholte, was die Kacheln schon zeigten
  // (Tim, 08.11.2026). Oben bleibt, was keine Kachel hat: selbst getippte
  // Themen, Stadtteile aus dem Schritt danach — und ein Stadtthema, das unter
  // die Schwelle gefallen ist und deshalb keine Kachel mehr bekommt; sonst
  // wäre es nirgends zu sehen. Solange die Kacheln laden, hält das Bild
  // (`image_key`) sie auseinander, damit oben nichts kurz auf- und abtaucht.
  const kachelNamen = useMemo(() => new Set((stadtQuery.data ?? []).map((v) => v.name)), [stadtQuery.data]);
  const eigene = mine.filter((t) => (stadtQuery.isPending ? !t.image_key : !kachelNamen.has(t.name)));
  const unterwegs = anlegend && !mine.some((t) => t.name === anlegend) ? [anlegend] : [];

  const remove = async (id: number) => {
    try {
      await api.del(`/topics/${id}`);
      qc.invalidateQueries({ queryKey: ["topics"] });
    } catch { /* bleibt stehen — beim nächsten Laden wieder korrekt */ }
  };

  return (
    <StepShell
      title="Worüber willst du Bescheid wissen?"
      lead="Lege Themen an — Lotti meldet sich, sobald der Rat dazu entscheidet."
      pose="search"
      mehr="Weitere Themen"
      footer={
        // Erst weiter, wenn alles angelegt ist — sonst fehlte ein gerade
        // geklicktes Thema im nächsten Schritt, und der Fehler, falls einer
        // kommt, stünde auf einer Seite, die man schon verlassen hat.
        <Button className="w-full lg:w-auto lg:min-w-44" onClick={onNext}
          disabled={busy || stadtLaeufe.size > 0}>Weiter</Button>
      }
    >
      <form onSubmit={(e) => { e.preventDefault(); meldeChips([], ["own"]); void add(name); }} className="flex gap-2">
        <Input ref={inputRef} value={name} onChange={(e) => setName(e.target.value)}
          placeholder="Eigenes Thema, z. B. „Cäcilienbrücke“" enterKeyHint="done" aria-label="Thema" />
        <Button type="submit" disabled={busy || name.trim().length < 2} aria-label="Thema anlegen">
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
        </Button>
      </form>
      <p className="mt-1.5 text-xs text-muted-foreground">
        Du brauchst keine Beschreibung zu schreiben — Lotti formuliert sie aus passenden Beschlüssen.
      </p>

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

      {/* Die eigenen Themen ZUERST — direkt unter dem Feld, in das man sie
          tippt. Vorher standen sie unter allen Vorschlagsgruppen und damit
          unter dem sichtbaren Bereich: Man legte ein Thema an und sah es
          nicht (Tims Befund, 02.09.2026). Kompakt als Zeilen, nicht als
          Karten; die Beschreibung steht als Tooltip und im Blatt „anpassen". */}
      {(eigene.length > 0 || unterwegs.length > 0) && (
        <div className="mt-4 rounded-2xl border border-border bg-card p-3 lg:bg-background">
          <Kicker>Deine Themen ({eigene.length + unterwegs.length})</Kicker>
          <ul className="mt-2 flex flex-col divide-y divide-border">
            {/* Was gerade angelegt wird, steht schon da — mit einem Balken
                dort, wo gleich die Zahl steht, statt eines kleinen Kreisels. */}
            {unterwegs.map((n) => (
              <li key={`unterwegs-${n}`} aria-busy="true"
                className="flex items-center gap-2 py-1.5 text-[13px] text-muted-foreground">
                <span className="h-7 w-7 shrink-0 animate-pulse rounded-md bg-primary/10" aria-hidden />
                <span className="min-w-0 flex-1 truncate font-semibold text-foreground">{n}</span>
                <span className="h-2.5 w-24 shrink-0 animate-pulse rounded-full bg-primary/15" aria-hidden />
                <span className="sr-only">wird angelegt</span>
              </li>
            ))}
            {eigene.map((t) => (
              <TopicZeile key={t.id} topic={t}
                istStadtteil={stadtteile.some((o) => o.name.toLowerCase() === t.name.toLowerCase())}
                onEdit={() => setEditing(t)} onRemove={() => void remove(t.id)} />
            ))}
          </ul>
        </div>
      )}

      {/* Stadtthemen zuerst: Interessen, mit denen Menschen kommen — nicht
          Vorgänge, die der Rat zuletzt benannt hat. Jeder Chip trägt die Zahl
          der Beschlüsse aus zwölf Monaten; was darunter zu dünn ist, kommt
          gar nicht erst aus dem Server (Zusage: nichts anbieten, wozu Lotti
          nicht liefert). Die Liste ist stabil; ein Klick wählt, ein zweiter
          nimmt das Thema wieder heraus. */}
      <div className="mt-4">
        <Kicker className="text-primary">
          <Sparkles className="h-3 w-3" />
          Gerade in Oldenburg
          <span className="font-sans text-[11px] font-medium normal-case tracking-normal text-muted-foreground">
            · Beschlüsse der letzten 12 Monate
          </span>
          {stadtQuery.isPending && <Loader2 className="h-3 w-3 animate-spin text-primary" />}
        </Kicker>
        {stadtQuery.isPending
          ? <KachelPlatzhalter />
          : <StadtthemenKacheln vorschlaege={stadtQuery.data ?? []} vorhanden={mine} laufend={stadtLaeufe}
              onUmschalten={(v) => void umschaltenStadtthema(v)} onAnpassen={setEditing} />}
      </div>

      {editing && (
        <TopicSheet topic={editing} onClose={() => setEditing(null)}
          onSaved={() => { setEditing(null); qc.invalidateQueries({ queryKey: ["topics"] }); }} />
      )}
    </StepShell>
  );
}

type VorschlagsGruppe = {
  place_id: string; name: string; months: number;
  suggestions: Vorschlag[];
  /** Aus den nächsten Ortsbereichen — jeder trägt seinen Herkunftsort. */
  nearby: (Vorschlag & { place: string })[];
};

type VorschlagsAntwort = { city: Vorschlag[]; suggestions: Vorschlag[]; districts: VorschlagsGruppe[] };

/** Vorschläge je gewähltem Stadtteil. Zwei, nicht sechs: Die Stadtteile sind
 *  ein Sammelbecken unter den Stadtthemen, nicht die Hauptsache. */
const JE_STADTTEIL = 2;

type Vorschlag = {
  name: string; description: string; n: number; context?: string | null;
  /** Nur bei den kuratierten Stadtthemen: ihr Schlüssel (`cycling`, `pools`) —
   *  daran hängen Bild und Zähler. */
  key?: string;
  /** Nur bei „nebenan": aus welchem Ortsbereich der Vorschlag stammt. */
  place?: string;
  /** Warum der Vorschlag an diesem Stadtteil hängt — der Titel des
   *  Beschlusses, der beide verbindet. Nur bei Stadtteil-Vorschlägen. */
  place_reason?: string | null;
};

/** Kacheln in Wartestellung: gleiche Höhe wie die echten, damit nichts springt,
 *  wenn die Liste eintrifft. */
function KachelPlatzhalter() {
  return (
    <div className="mt-2.5 grid grid-cols-2 gap-2 lg:grid-cols-3" aria-busy="true">
      {Array.from({ length: 9 }, (_, i) => (
        <span key={i}
          className="h-[68px] animate-pulse rounded-xl border border-dashed border-border bg-muted/40" />
      ))}
    </div>
  );
}

/** „Bebauungsplan 865", „Bebauungsplan S-745 B" — Namen, die ohne Einordnung
 *  niemandem etwas sagen. Dieselbe Regel wie `_ist_plannummer` im Backend. */
function istPlannummer(name: string): boolean {
  return /\b(?:vorhabenbezogener\s+)?(?:bebauungs|flächennutzungs)plan\s+[\dSNOWM]/i.test(name);
}

/** Die Stadtthemen als Kacheln mit Bild — flach gezeichnet, dünne Kontur, Markenfarben, und
 *  manchmal spielt ein Gast aus Lottis Welt mit (`public/themen/`, erzeugt von `scripts/themen_grafiken.py`).
 *
 *  Kacheln statt Pillen, seit Neue Konten fast nur Stadtteile wählten
 *  (30.09.2026): „Bus und Bahn" als Text neben einem Stadtteil ist abstrakt, ein
 *  kleiner Bus ist es nicht. Die Reihenfolge kommt fertig vom Server (gemischt,
 *  nicht nach Zahl); die Zahl der Beschlüsse steht darunter als Beleg dafür,
 *  dass Lotti bei dem Thema wirklich etwas zu melden hat.
 *
 *  Waagerecht gebaut (Bild links, Text rechts): 20 senkrechte Kacheln wären
 *  fünf Reihen Bildschirm, so sind es sieben Zeilen, die man überfliegt. */
function StadtthemenKacheln({ vorschlaege, vorhanden, laufend, onUmschalten, onAnpassen }: {
  vorschlaege: Vorschlag[];
  vorhanden: TopicRow[];
  /** Kacheln, die gerade an- oder ausgeschaltet werden, mit ihrem Ziel.
   *  Jede sperrt nur sich selbst. */
  laufend: ReadonlyMap<string, boolean>;
  onUmschalten: (v: Vorschlag) => void;
  onAnpassen: (t: TopicRow) => void;
}) {
  return (
    <ul className="mt-2.5 grid grid-cols-2 gap-2 lg:grid-cols-3">
      {vorschlaege.map((v) => {
        const thema = vorhanden.find((t) => t.name === v.name);
        const ziel = laufend.get(v.name.trim());
        const laeuft = ziel !== undefined;
        // Die Anzeige folgt sofort der Absicht, nicht erst dem Server.
        const an = ziel ?? !!thema;
        // Wer die Beschreibung angepasst hat, sieht die Zahl SEINER Fassung —
        // sonst stünde an der Kachel die des Stadtthemas und im Blatt eine andere.
        const zahl = thema && thema.description !== v.description && thema.matched
          && typeof thema.hits_12m === "number" ? thema.hits_12m : v.n;
        return (
          <li key={v.key ?? v.name}
            className={cn(
              "flex flex-col overflow-hidden rounded-xl border transition-colors",
              an ? "border-primary/40 bg-primary/5"
                 : "border-border bg-card hover:border-primary/40 hover:bg-muted",
            )}>
            <button type="button" disabled={laeuft} onClick={() => onUmschalten(v)}
              aria-pressed={an} aria-busy={laeuft || undefined} title={v.context || undefined}
              className="group flex flex-1 items-center gap-2 p-2 text-left sm:gap-2.5">
              <span className="relative shrink-0">
                {v.key ? (
                  // Feste 256-px-Dateien aus dem Repo; `next/image` optimiert hier nichts (s. next.config.mjs).
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={stadtthemaBild(v.key)} alt="" width={52} height={52} loading="lazy" decoding="async"
                    className="h-11 w-11 rounded-lg bg-muted object-cover sm:h-[52px] sm:w-[52px]" />
                ) : (
                  <span aria-hidden className="block h-11 w-11 rounded-lg bg-muted sm:h-[52px] sm:w-[52px]" />
                )}
                {/* Auf dem Handy sitzt das Häkchen auf dem Bild: Neben dem
                    Text nahm es der Spalte so viel Breite, dass „Schwimmbäder"
                    hineinlief und bei 320 px jeder Name zerbrach. */}
                {an && (
                  <span aria-hidden className="absolute -right-1 -top-1 rounded-full bg-primary p-0.5 text-primary-foreground ring-2 ring-card sm:hidden">
                    <Check className="h-3 w-3" />
                  </span>
                )}
              </span>
              <span className="min-w-0 flex-1">
                <span className={cn("block hyphens-auto break-words text-[13px] font-semibold leading-tight",
                                    an ? "text-primary" : "text-foreground")}>
                  {v.name}
                </span>
                {laeuft ? (
                  // Ein Balken, wo gleich wieder die Zahl steht — die Kachel
                  // springt nicht, und ein Kreisel in 11 px wäre kaum zu sehen.
                  <span className="mt-1.5 block h-2 w-16 animate-pulse rounded-full bg-primary/20" aria-hidden />
                ) : (
                  <span className="mt-0.5 block text-[11px] text-muted-foreground">
                    {zahl} {zahl === 1 ? "Beschluss" : "Beschlüsse"}
                  </span>
                )}
              </span>
              {an
                ? <Check className="hidden h-4 w-4 shrink-0 text-primary sm:block" aria-hidden />
                : <Plus className="hidden h-4 w-4 shrink-0 text-muted-foreground group-hover:text-primary sm:block" aria-hidden />}
            </button>
            {/* Anpassen hängt an der Kachel selbst. Er erscheint mit dem Klick
                (nicht erst mit der Antwort), damit die Kachel nur einmal ihre
                Höhe ändert, und wird bedienbar, sobald das Thema angelegt ist. */}
            {an && (
              <button type="button" disabled={!thema || laeuft} onClick={() => thema && onAnpassen(thema)}
                aria-label={`${v.name} anpassen`}
                className="flex items-center gap-1 border-t border-primary/15 px-2 py-1 text-left text-[11px] font-medium text-primary transition-colors hover:bg-primary/10 disabled:opacity-50">
                <SlidersHorizontal className="h-3 w-3 shrink-0" aria-hidden />
                anpassen
              </button>
            )}
          </li>
        );
      })}
    </ul>
  );
}

/** Die Vorschläge aus den gewählten Stadtteilen — als kleine Karten, nicht als
 *  Pillen. Grund ist die zweite Zeile: Sie sagt, WARUM der Vorschlag an diesem
 *  Stadtteil hängt, und in eine Pille (Radius 9999, eine Zeile) passt das
 *  nicht. „Kommunale Wärmeplanung" unter Kreyenbrück las sich sonst wie ein
 *  Fehler — mit „Maßnahme Machbarkeitsstudien" darunter ist es sofort klar
 *  (Tim, 03.09.2026: „es bräuchte manchmal nur eine ganz kurze Erklärung").
 *
 *  Der Ortsname bleibt auf der ERSTEN Zeile beim Namen. Ihn stattdessen in die
 *  Begründung zu ziehen („Machbarkeitsstudien in Kreyenbrück") bräuchte den
 *  richtigen Artikel — „in Innenstadt" statt „in der Innenstadt" — und der
 *  hängt am Stadtteil, nicht an einer Regel. */
function OrtsVorschlaege({ vorschlaege, vorhanden, busy, onWaehlen }: {
  vorschlaege: Vorschlag[];
  vorhanden: { name: string }[];
  busy: boolean;
  onWaehlen: (v: Vorschlag) => void;
}) {
  return (
    <div className="mt-2.5 grid grid-cols-1 gap-2 sm:grid-cols-2">
      {vorschlaege.map((v) => {
        const have = vorhanden.some((t) => t.name === v.name);
        // Die Einordnung einer Plannummer ist selbst die Begründung — der
        // Server schickt dann keine zweite dazu.
        const zweite = v.place_reason || (istPlannummer(v.name) ? v.context : null);
        return (
          <button key={`${v.place}-${v.name}`} type="button" disabled={busy || have}
            onClick={() => onWaehlen(v)}
            className={cn(
              "flex flex-col items-start gap-0.5 rounded-xl border px-3 py-2 text-left transition-colors",
              have ? "border-primary/30 bg-primary/5"
                   : "border-border bg-card hover:bg-muted disabled:opacity-50",
            )}>
            <span className="flex w-full items-center gap-1.5">
              {have ? <Check className="h-3 w-3 shrink-0 text-primary" />
                    : <Plus className="h-3 w-3 shrink-0 text-muted-foreground" />}
              <span className={cn("truncate text-[13px] font-medium",
                                  have ? "text-primary" : "text-foreground")}>
                {v.name}
              </span>
              {v.place && (
                <span className="ml-auto shrink-0 text-[11px] text-muted-foreground">{v.place}</span>
              )}
            </span>
            {zweite && (
              <span className="w-full truncate pl-[18px] text-[11px] leading-snug text-muted-foreground">
                {zweite}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}

/** Wartestellung für die Karten — gleiche Höhe wie die echten, damit nichts
 *  springt, wenn sie eintreffen. */
function KartenPlatzhalter({ anzahl }: { anzahl: number }) {
  return (
    <div className="mt-2.5 grid grid-cols-1 gap-2 sm:grid-cols-2" aria-busy="true">
      {Array.from({ length: anzahl }, (_, i) => (
        <span key={i}
          className="h-[52px] animate-pulse rounded-xl border border-dashed border-border bg-muted/40" />
      ))}
    </div>
  );
}

/** Ein angelegtes Thema als EINE Zeile: Name, Herkunft, Trefferzahl,
 *  anpassen, entfernen. Die Beschreibung steht im Tooltip und im Blatt
 *  „anpassen" — als Absatz auf der Karte trug sie 60 % der Höhe, und die
 *  Liste rutschte unter den sichtbaren Bereich. Die Trefferzahl bleibt: Sie
 *  ist der Beleg dafür, dass die Beschreibung etwas taugt. */
function TopicZeile({ topic, istStadtteil, onEdit, onRemove }: {
  topic: TopicRow;
  /** Dieses Thema ist einer der im Stadtteil-Schritt gewählten Stadtteile. Es steht mit in der
   *  Liste — es IST ein Thema, nur so löst es Hinweise aus —, sagt das aber
   *  auch: Sonst wirkte die Trennung der beiden Schritte hinterher hinfällig,
   *  weil der Stadtteil unbeschriftet zwischen den anderen Themen auftauchte. */
  istStadtteil?: boolean;
  onEdit: () => void;
  onRemove: () => void;
}) {
  // Nur das Zwölf-Monats-Fenster, in beiden Richtungen. Die Gesamtzahl seit
  // 2018 (`decision_count`) steht bewusst nicht hier: Sie ist die Aussage der
  // Themen-Karte („was liegt vor"), während dieser Schritt neben Chips steht,
  // die „Beschlüsse der letzten 12 Monate" zählen. Beides nebeneinander waren
  // zwei Zahlen für dasselbe Thema (Tim, 03.09.2026).
  const zahl = topic.matched ? topic.hits_12m : undefined;
  return (
    <li className="flex items-center gap-2 py-1.5 text-[13px]" title={topic.description}>
      {topic.image_key ? (
        // Feste 256-px-Dateien aus dem Repo; `next/image` optimiert hier nichts (s. next.config.mjs).
        // eslint-disable-next-line @next/next/no-img-element
        <img src={stadtthemaBild(topic.image_key)} alt="" width={28} height={28} loading="lazy"
          className="h-7 w-7 shrink-0 rounded-md bg-muted object-cover" />
      ) : (
        <span className={cn("shrink-0", istStadtteil ? "text-primary" : "text-signal")} aria-hidden>
          {istStadtteil ? <MapPin className="h-3.5 w-3.5" /> : <Sparkles className="h-3.5 w-3.5" />}
        </span>
      )}
      <span className="min-w-0 flex-1 truncate font-semibold text-foreground">{topic.name}</span>
      {typeof zahl === "number" && zahl > 0 && (
        <span className="hidden shrink-0 text-[11px] text-muted-foreground sm:inline">
          <span className="rounded bg-primary/10 px-1.5 font-semibold tabular-nums text-primary">
            {zahl}
          </span>{" "}
          {zahl === 1 ? "Beschluss" : "Beschlüsse"} in 12 Monaten
        </span>
      )}
      <button type="button" onClick={onEdit}
        className="shrink-0 text-[11px] font-medium text-primary transition-colors hover:underline">
        anpassen
      </button>
      <button type="button" onClick={onRemove} aria-label={`${topic.name} entfernen`}
        className="shrink-0 p-0.5 text-muted-foreground transition-colors hover:text-foreground">
        <X className="h-3.5 w-3.5" />
      </button>
    </li>
  );
}

/* ---------------------------------------------------- Schritt 4: E-Mail --- */

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
      lead="Ohne Benachrichtigung merkst du nicht, wenn dein Thema auf einer Tagesordnung landet — und genau darum geht es hier."
      pose="wave"
      // Am Desktop nebeneinander in der Fußleiste, der Knopf rechts außen; am
      // Telefon untereinander, der Knopf oben. `flex-row-reverse`, damit der
      // Knopf in beiden Fällen als Erstes im DOM steht — die Tab-Reihenfolge
      // folgt der Wichtigkeit, nicht der Bildschirmposition.
      footer={
        <div className="flex w-full flex-col gap-2 lg:w-auto lg:flex-row-reverse lg:items-center lg:gap-5">
          {/* Der Knopf sagt, WOZU man ja sagt. „Ja, so ist es richtig"
              bestätigte nur, dass irgendein Schalter steht (Tim, 01.09.2026). */}
          <Button className="w-full lg:w-auto lg:min-w-56" onClick={einschalten} disabled={busy}>
            {busy ? <Loader2 className="h-4 w-4 animate-spin" />
                  : an ? "Ja, ich möchte Benachrichtigungen erhalten"
                       : "E-Mail-Benachrichtigungen einschalten"}
          </Button>
          {/* Ein Nein muss möglich bleiben — aber es steht als stiller Text da,
              nicht als gleichwertiger zweiter Knopf. */}
          <button type="button" onClick={onDone}
            className="py-1 text-sm text-muted-foreground transition-colors hover:text-foreground">
            {an ? "Später entscheiden" : "Ohne Benachrichtigungen weiter"}
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
        <strong className="font-semibold text-foreground">Höchstens zwei Benachrichtigungen am Tag</strong>, zwischen
        21 und 7 Uhr gar keine — mehr wird gebündelt. Welche Anlässe du bekommst, stellst du
        jederzeit im Konto ein; abbestellen geht mit einem Klick in jeder Mail.
      </p>

      {an && (
        <p className="mt-2.5 flex items-center gap-1.5 text-xs text-primary">
          <Check className="h-3.5 w-3.5 shrink-0" />
          E-Mail-Benachrichtigungen sind für {user?.email} bereits eingeschaltet.
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

/* ------------------------------------------------------------- Gerüst ---- */

/** Mono-Kicker über einem Block (DESIGNSPRACHE §3/§5): IBM Plex Mono, Versalien,
 *  0,1 em Laufweite. Vorher standen die Gruppen-Überschriften des Themen-
 *  Schritts in fetten Inter-Versalien — die gibt es sonst nirgends in der App. */
function Kicker({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <p className={cn(
      "flex flex-wrap items-center gap-x-1.5 font-mono text-[10.5px] uppercase tracking-[0.1em] text-muted-foreground",
      className,
    )}>
      {children}
    </p>
  );
}

const SCHRITT_NAMEN = ["Gremien", "Themen", "Stadtteile"] as const;

/** Der Schritt-Pfad in der Frage-Spalte (nur `lg`). Vorher stand dort unter der
 *  Frage nichts — 400 px Luft auf jedem Schritt. Jetzt trägt die Spalte, wo man
 *  ist und was noch kommt, in der Form aus DESIGNSPRACHE §5 (Schritt-Pfad):
 *  erledigt = gefüllter Punkt, aktuell = Ring mit Halo, offen = Rand-Punkt.
 *  Am Telefon übernehmen die Segmente in der Kopfzeile; zweimal dasselbe
 *  bräuchte niemand. */
/** Das Auffangnetz: erscheint NUR, wenn nach dem letzten Schritt weder ein
 *  Thema noch ein Gremium hinterlegt ist.
 *
 *  Warum es das braucht. Am 08.09.2026 hatten fünf von neun echten neuen
 *  Konten am Ende nichts hinterlegt — und damit gibt es keinen einzigen
 *  Anlass, sich je wieder bei ihnen zu melden: keine Tagesordnung, keine
 *  Ergebnis-Mail, nichts. Ob sie wiederkommen, entscheidet sich allein daran,
 *  ob sie von selbst daran denken. Das ist die größte Einzelverlustquelle im
 *  ganzen Trichter, und sie lässt sich mit einem Tipp schließen.
 *
 *  Warum trotzdem überspringbar. Der Assistent zwingt an keiner Stelle zu
 *  einer Eingabe (Modul-Kopf), und ein Schirm, an dem man nicht vorbeikommt,
 *  wäre der erste. „Später" steht deshalb da — nur eben als Textlink und
 *  nicht als gleichrangiger Knopf.
 *
 *  Die Vorschläge sind dieselben kuratierten Stadtthemen wie in Schritt 3:
 *  Sie kosten kein Modell, stehen sofort da und sind daran kalibriert, in den
 *  nächsten Wochen wirklich etwas zu melden.
 */
function HakenStep({ onDone }: { onDone: () => void }) {
  const qc = useQueryClient();
  const [busy, setBusy] = useState<string | null>(null);
  const [gewaehlt, setGewaehlt] = useState<string[]>([]);
  const stadt = useQuery({
    queryKey: ["topic-suggestions", "city"],
    queryFn: () => api.get<VorschlagsAntwort>("/topics/suggestions?citywide=0&city=1").then((d) => d.city),
  });
  // Drei, nicht alle: Dies ist der letzte Schirm vor dem Schluss, und eine
  // Wand aus Kacheln ist hier das Gegenteil von „ein Handgriff". Aber drei
  // KARTEN mit Einordnung und Zahl, keine drei Chips — auf einer Fläche, die
  // sonst zu vier Fünfteln leer stünde (Tims Rückmeldung 09.09.).
  const vorschlaege = (stadt.data ?? []).slice(0, 3);

  const waehlen = async (v: Vorschlag) => {
    setBusy(v.name);
    try {
      await api.post("/topics", { name: v.name, description: v.description });
      setGewaehlt((g) => [...g, v.name]);
      await qc.invalidateQueries({ queryKey: ["topics"] });
    } catch {
      toast.error("Das Thema ließ sich gerade nicht anlegen.");
    } finally {
      setBusy(null);
    }
  };

  return (
    <StepShell
      title="Eine Sache noch"
      lead="Ohne ein Thema oder ein Gremium hat Lotti keinen Anlass, sich je bei dir zu melden — dann bleibt Ratslotse eine Seite, an die du selbst denken musst."
      pose="point"
      footer={
        // EIN Weg hinaus, nicht zwei. Solange nichts gewählt ist, gibt es nur
        // den stillen Ausgang; der Hauptknopf erscheint, sobald es etwas zu
        // bestätigen gibt — und sagt dann, was er bestätigt.
        <div className="flex items-center justify-between gap-6">
          <span className="min-w-0 text-[12px] text-muted-foreground">
            {gewaehlt.length === 0
              ? "Kein Zwang — unter „Meine Themen“ geht es jederzeit."
              : gewaehlt.length === 1
                ? `„${gewaehlt[0]}“ ist angelegt.`
                : `${gewaehlt.length} Themen sind angelegt.`}
          </span>
          {gewaehlt.length === 0 ? (
            <button type="button" onClick={onDone}
              className="shrink-0 py-1 text-[13px] text-muted-foreground transition-colors hover:text-foreground">
              Später, ohne Thema
            </button>
          ) : (
            <Button onClick={onDone} disabled={busy !== null}>Fertig — Lotti meldet sich</Button>
          )}
        </div>
      }
    >
      <p className="text-[13px] text-muted-foreground">
        Drei Themen, in denen der Rat gerade wirklich entscheidet. Ein Tipp legt eines an — mit
        einer Beschreibung, die am Bestand geprüft ist.
      </p>
      {stadt.isPending ? (
        <div className="mt-3 flex items-center gap-2 text-[13px] text-muted-foreground">
          <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" /> Vorschläge werden geladen …
        </div>
      ) : vorschlaege.length === 0 ? (
        <p className="mt-3 text-[13px] text-muted-foreground">
          Unter „Meine Themen" legst du jederzeit eines an.
        </p>
      ) : (
        <ul className="mt-3 flex flex-col gap-2">
          {vorschlaege.map((v) => {
            const dran = gewaehlt.includes(v.name);
            const laeuft = busy === v.name;
            return (
              <li key={v.name} className={cn(
                "flex items-center gap-3 rounded-[12px] border px-3.5 py-3 transition-colors",
                dran ? "border-primary/30 bg-primary/[0.05]" : "border-border bg-card",
              )}>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-baseline gap-x-2">
                    <span className="text-[14px] font-semibold text-foreground">{v.name}</span>
                    {v.n > 0 && (
                      <span className="font-mono text-[10.5px] uppercase tracking-[0.08em] text-muted-foreground">
                        {v.n} {v.n === 1 ? "Beschluss" : "Beschlüsse"} im letzten Jahr
                      </span>
                    )}
                  </div>
                  {v.context && <p className="mt-0.5 truncate text-[12.5px] text-muted-foreground">{v.context}</p>}
                </div>
                {dran ? (
                  <span className="inline-flex shrink-0 items-center gap-1.5 text-[12.5px] font-medium text-primary">
                    <Check className="h-3.5 w-3.5" aria-hidden /> angelegt
                  </span>
                ) : (
                  <button type="button" disabled={busy !== null} onClick={() => void waehlen(v)}
                    className="inline-flex h-8 shrink-0 items-center gap-1.5 rounded-[10px] border border-primary/30 bg-primary/[0.04] px-3 text-[12.5px] font-semibold text-primary transition-colors hover:bg-primary/10 disabled:opacity-50">
                    {laeuft ? <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden /> : <Plus className="h-3.5 w-3.5" aria-hidden />}
                    Verfolgen
                  </button>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </StepShell>
  );
}

function SchrittPfad({ aktuell }: { aktuell: Step }) {
  const namen = [...SCHRITT_NAMEN, "Benachrichtigungen"];
  return (
    <ol aria-label="Schritte der Einrichtung" className="relative mt-8 hidden flex-col gap-3.5 lg:flex">
      {/* Der Faden hinter den Punkten — die Punkte decken ihn mit ihrer Fläche. */}
      <span aria-hidden className="absolute bottom-2 left-[7px] top-2 w-px bg-border" />
      {namen.map((name, i) => {
        const n = i + 1;
        const erledigt = n < aktuell;
        const dran = n === aktuell;
        return (
          <li key={name} aria-current={dran ? "step" : undefined}
            className={cn("relative flex items-center gap-3 text-[13px]",
              dran ? "font-semibold text-foreground" : "text-muted-foreground")}>
            <span className={cn(
              "flex h-[15px] w-[15px] shrink-0 items-center justify-center rounded-full",
              erledigt ? "bg-primary text-primary-foreground"
                : dran ? "border-2 border-primary bg-card shadow-[0_0_0_4px_hsl(var(--primary)/0.14)]"
                  : "border border-border bg-card",
            )}>
              {erledigt && <Check className="h-2.5 w-2.5" strokeWidth={3} />}
            </span>
            {name}
          </li>
        );
      })}
    </ol>
  );
}

function StepShell({ title, lead, pose, children, footer, mehr = "Mehr" }: {
  title: string;
  lead: string;
  pose: MascotPose;
  children: React.ReactNode;
  footer: React.ReactNode;
  /** Was die Pille über der Fußleiste verspricht, solange unten noch etwas liegt. */
  mehr?: string;
}) {
  const step = useContext(SchrittKontext);
  const blattRef = useRef<HTMLDivElement>(null);
  const rest = useScrollRestUnten(blattRef);
  // Die Pille lädt zum ersten Scrollen ein; wer einmal gescrollt hat, weiß
  // Bescheid — ab dann trägt der Ausblendrand allein den Hinweis.
  const pille = rest.verdeckt && rest.oben;
  const weiter = () => {
    const el = blattRef.current;
    if (!el) return;
    const ruhig = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    el.scrollBy({ top: Math.max(160, el.clientHeight * 0.7), behavior: ruhig ? "auto" : "smooth" });
  };
  return (
    <>
      {/* Liegt unter dem sichtbaren Teil noch etwas, läuft die letzte Zeile per
          Maske aus und eine Pille sagt, was noch kommt (Tim, 08.11.2026): Endete
          eine Kachel zufällig genau über der Fußleiste, sah die Auswahl fertig
          aus. Maske statt Farbverlauf (DESIGNSPRACHE § 6) — am Desktop liegt
          das Blatt auf `bg-card`, am Telefon auf `bg-background`. */}
      <div className="relative flex min-h-0 flex-1 flex-col">
        <div ref={blattRef} className={cn("min-h-0 flex-1 overflow-y-auto", rest.verdeckt && "gb-maske-unten")}>
          <div className={cn(SPALTE, "px-[18px] pt-5 lg:px-8 lg:pt-6")}>
            <div className={ZWEISPALTIG}>
              {/* Lotti steht neben der Frage, nicht darüber: Sie fragt, man
                  antwortet — das trägt den Ton des ganzen Flows. Am Desktop
                  rutscht sie über den Titel und wird größer, und die Frage bleibt
                  beim Scrollen stehen: Auf einem langen Schritt wie den Themen
                  verliert man sonst aus dem Blick, was gefragt war. */}
              {/* `lg:pb-6` wie die Inhaltsspalte daneben: Ist der Schritt kurz
                  (Benachrichtigungen), bestimmt DIESE Spalte die Höhe, und die
                  Schrittliste stieß ohne Abstand an die Linie der Fußleiste
                  (Tims Befund 08.11.2026: „sieht gequetscht aus"). */}
              <div className="lg:sticky lg:top-6 lg:self-start lg:pb-6">
                <div className="flex items-center gap-3 lg:block">
                  <Mascot pose={pose} decorative className="h-11 w-11 shrink-0 lg:mb-5 lg:h-24 lg:w-24" />
                  {/* `hyphens-none`: In der schmalen Spalte trennte der Browser die
                      Frage mitten im Wort („Worüber willst du Be-scheid wissen?").
                      Silbentrennung taugt für Fließtext, nicht für eine Überschrift
                      aus vier Wörtern — die soll am Wort umbrechen. */}
                  <h1 className="font-display text-xl font-extrabold leading-tight tracking-tight text-foreground [hyphens:none] lg:text-[26px]">{title}</h1>
                </div>
                <p className="mt-2.5 text-[13.5px] leading-relaxed text-muted-foreground lg:text-[14px]">{lead}</p>
                <SchrittPfad aktuell={step} />
              </div>
              {/* Reichlich Luft unten: Die Fußzeile liegt fest, der Inhalt
                  scrollt darunter durch — mit knappem Abstand endete die letzte
                  Zeile am Telefon mittendrin und sah kaputt aus statt scrollbar. */}
              <div className="mt-4 pb-8 lg:mt-0 lg:pb-6">{children}</div>
            </div>
          </div>
        </div>
        {/* Dasselbe Raster wie der Inhalt, damit die Pille am Desktop unter der
            Antwortspalte steht und nicht auf der Fuge zur Frage. Aus der
            Tab-Reihenfolge und dem Vorlesen heraus: Sie ersetzt nur das Scrollen,
            und wer per Tastatur oder Vorlesefunktion durchgeht, kommt ohnehin an
            jeder Kachel vorbei. */}
        <div aria-hidden className={cn(SPALTE, "pointer-events-none absolute inset-x-0 bottom-3 px-[18px] lg:px-8")}>
          <div className={ZWEISPALTIG}>
            <div className="hidden lg:block" />
            <div className="flex justify-center">
              <button type="button" tabIndex={-1} onClick={weiter}
                className={cn(
                  "inline-flex h-11 items-center gap-1.5 rounded-full border border-primary/30 bg-card px-4 text-[13px] font-medium text-primary shadow-lifted maus:h-9",
                  "transition-[opacity,transform] duration-fluss ease-out-strong motion-reduce:transition-none",
                  pille ? "pointer-events-auto opacity-100" : "translate-y-1 opacity-0",
                )}>
                {mehr}
                <ChevronDown className="h-4 w-4" aria-hidden />
              </button>
            </div>
          </div>
        </div>
      </div>
      {/* Die Fußleiste des Blatts: am Desktop mit Hairline nach oben, die
          Aktion rechts außen — ein Knopf über 650 px wäre keine Schaltfläche
          mehr, sondern ein Balken. Am Telefon wie gehabt unter dem Inhalt. */}
      <div className={cn(SPALTE, "px-[18px] pt-3 lg:border-t lg:border-border lg:px-8 lg:py-4")}>
        <div className="lg:flex lg:items-center lg:justify-end">{footer}</div>
      </div>
    </>
  );
}
