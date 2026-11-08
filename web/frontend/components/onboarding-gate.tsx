"use client";

import { useEffect, useRef, useState } from "react";
import dynamic from "next/dynamic";
import { usePathname } from "next/navigation";
import { useQuery } from "@tanstack/react-query";

import { useAuth } from "@/lib/auth";
import { SETUP_QUERY_KEY, holeSetupStand } from "@/lib/onboarding-setup";
import {
  ONBOARDING_DONE_EVENT, imAppBereich, isFlowDeciding, isUsable, setFlowDeciding,
} from "@/lib/onboarding-state";

/** Der Assistent selbst, erst wenn er dran ist. Solange sein Bündel lädt,
 *  deckt eine leere Fläche die Seite ab — sonst blitzte „Heute" auf, bevor
 *  der Assistent darüberfährt. */
const OnboardingFlow = dynamic(
  () => import("@/components/onboarding-flow").then((m) => m.OnboardingFlow),
  { ssr: false, loading: () => <div aria-hidden className="fixed inset-0 z-[var(--level-flaeche)] bg-background" /> },
);

/**
 * Das Tor zum Einrichtungs-Assistenten (Design 26a), im App-Layout.
 *
 * **Warum ein Tor.** Der Assistent ist groß und erscheint nur für neue Konten.
 * Bis 11/2026 hing er im Wurzel-Layout und kam so auf jede Seite, auch für
 * jedes fertig eingerichtete Konto und auf Seiten ohne Konto. Das Tor stellt
 * dieselbe Frage wie er (`/onboarding/setup`, derselbe Schlüssel, dieselben
 * Optionen) und holt ihn erst, wenn der Server `pending` meldet. Ab dann
 * bleibt er eingehängt und entscheidet alles Weitere selbst — wie vorher.
 *
 * **Bis dahin spricht das Tor für ihn.** Die Abzeichen fragen
 * `isOnboardingVisible()`, bevor sie feiern; solange die Antwort aussteht
 * (und solange das Bündel lädt), heißt das „gleich". Fällt die Antwort
 * „nicht dran" aus, gibt das Tor die geparkten Abzeichen frei — dasselbe
 * Ereignis, das vorher der Assistent geschickt hat.
 */
export function OnboardingGate() {
  const { user, loading } = useAuth();
  const pathname = usePathname();
  const nutzbar = isUsable(user);
  const setup = useQuery({
    queryKey: SETUP_QUERY_KEY,
    queryFn: holeSetupStand,
    enabled: nutzbar,
    staleTime: 60_000,
    retry: false,
  });
  const imBereich = imAppBereich(pathname);

  // Einmal geholt, bleibt er: Er merkt sich selbst, ob er in dieser Sitzung
  // schon fertig ist (die Antwort im Cache sagt dann noch `pending`).
  const [geholt, setGeholt] = useState(false);
  const geholtRef = useRef(geholt);
  geholtRef.current = geholt;
  useEffect(() => {
    if (geholt) return; // ab hier meldet der Assistent selbst
    // „Entscheidet noch", solange die Antwort fehlt — und bei `pending`, bis
    // der Assistent geladen ist und die Marke selbst übernimmt. Er findet sie
    // dann gesetzt und gibt sie frei, genau wie vorher in einem Stück.
    const dran = setup.data?.pending === true;
    const wartet = !loading && nutzbar && imBereich && (!setup.data || dran);
    const vorher = isFlowDeciding();
    setFlowDeciding(wartet);
    if (vorher && !wartet) window.dispatchEvent(new Event(ONBOARDING_DONE_EVENT));
    if (wartet && dran) setGeholt(true);
  }, [geholt, loading, nutzbar, imBereich, setup.data]);
  // Verlässt man das App-Layout, bevor er geholt war: nichts hängen lassen.
  useEffect(() => () => { if (!geholtRef.current) setFlowDeciding(false); }, []);

  return geholt ? <OnboardingFlow /> : null;
}
