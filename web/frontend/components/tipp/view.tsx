"use client";

// /tipp — Beitritt, Tippen, „Mein Tipp" (docs/plan-tippspiel-ratswahl.md).
//
// EIN Spiel, kein Code: Wer den QR-Link öffnet, gibt einen Namen ein und
// bekommt einen Cookie (`tipp_token`, HttpOnly) — die Identität ist der
// Cookie, kein Konto. Diese Datei ist die Zustandsmaschine, die entscheidet,
// welcher der vier Screens (1c–1f) gerade dran ist.
//
// Falle: `GET /api/tipp/me` antwortet 401, solange niemand beigetreten ist —
// das ist der NORMALFALL, nicht „Sitzung abgelaufen". `api.get()` würde auf
// jeden 401 (außer /auth/…) einen Toast „Sitzung abgelaufen" zeigen und den
// globalen Anmeldezustand zurücksetzen (lib/auth.tsx hängt am selben
// Handler). Deshalb hier ein eigener, roher Abruf statt des Wrappers —
// dieselbe Ausnahme wie bei Streams (web/frontend/CLAUDE.md).

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { apiUrl } from "@/lib/api";
import { useAppConfig, useFeature } from "@/lib/features";
import { mitRunde, probePfad, rundeAus } from "@/lib/tipp";
import type { TippMeins, TippSetup } from "@/lib/tipp";
import { BrandMark } from "@/components/brand";
import { Mascot } from "@/components/mascot";
import { Einstieg } from "./einstieg";
import { Spaetstarter } from "./spaetstarter";
import { Tippen } from "./tippen";
import { MeinTipp } from "./mein-tipp";

class SetupFehler extends Error {
  constructor(public readonly status: number) {
    super(`setup ${status}`);
  }
}

async function holeSetup(pfad: string): Promise<TippSetup> {
  const res = await fetch(apiUrl(pfad), { credentials: "include" });
  // 401 heißt hier: eine Konto-Runde, und niemand ist angemeldet — kein
  // Netzfehler, sondern eine Antwort, die die Seite erklären muss.
  if (!res.ok) throw new SetupFehler(res.status);
  return res.json();
}

/** `null` heißt „nicht beigetreten" — ein ganz normaler Zustand, kein Fehler. */
async function holeMeins(pfad: string): Promise<TippMeins | null> {
  const res = await fetch(apiUrl(pfad), { credentials: "include" });
  if (res.status === 401) return null;
  if (!res.ok) throw new Error("me");
  return res.json();
}

function Kopf() {
  return (
    <div className="flex items-center gap-2 self-start">
      <BrandMark className="h-[26px] w-[26px]" />
      <span className="font-display text-base font-bold tracking-tight text-foreground">Ratslotse</span>
      <span className="text-xs text-muted-foreground">· Tippspiel</span>
    </div>
  );
}

function Rahmen({ children }: { children: React.ReactNode }) {
  return (
    <div className="mx-auto flex min-h-[100dvh] max-w-md flex-col items-center px-5 pb-7 pt-[calc(env(safe-area-inset-top)+12px)] text-center">
      {children}
    </div>
  );
}

function NichtFreigeschaltet() {
  return (
    <Rahmen>
      <Kopf />
      <div className="mt-6">
        <Mascot pose="sleep" className="h-24 w-24" decorative />
      </div>
      <h1 className="mt-3 text-balance font-display text-2xl font-bold leading-tight tracking-tight">
        Das Tippspiel ist noch nicht freigeschaltet
      </h1>
      <p className="mt-2.5 text-sm leading-relaxed text-muted-foreground">
        Das Tippspiel startet rund um den Wahlabend. Schau später noch einmal vorbei.
      </p>
    </Rahmen>
  );
}

function KontoNoetig() {
  return (
    <Rahmen>
      <Kopf />
      <div className="mt-6">
        <Mascot pose="wave" className="h-24 w-24" decorative />
      </div>
      <h1 className="mt-3 text-balance font-display text-2xl font-bold leading-tight tracking-tight">
        Für dieses Tippspiel brauchst du ein Konto
      </h1>
      <p className="mt-2.5 text-sm leading-relaxed text-muted-foreground">
        Diese Runde läuft über Konten: ein Tipp je Person, auf jedem Gerät derselbe. Melde dich an oder registriere dich kostenlos.
      </p>
      <div className="mt-5 flex w-full flex-col gap-2">
        <Link href="/login" className="inline-flex h-[46px] items-center justify-center rounded-xl bg-primary text-sm font-semibold text-primary-foreground">Anmelden</Link>
        <Link href="/register" className="inline-flex h-[46px] items-center justify-center rounded-xl border border-border bg-card text-sm font-semibold text-foreground">Kostenlos registrieren</Link>
      </div>
    </Rahmen>
  );
}

function LadeSchirm() {
  // Erster Ladezustand — nichts steht schon da, das stehen bleiben könnte
  // (DESIGNSPRACHE §7): eine ruhige, sofort sichtbare Fläche statt Zucken.
  return (
    <Rahmen>
      <Kopf />
      <div className="mt-8 h-2 w-24 animate-pulse rounded-full bg-muted" />
    </Rahmen>
  );
}

export function TippView() {
  const { isLoading: configLaedt } = useAppConfig();
  const tippspielAn = useFeature("tippspiel");
  const queryClient = useQueryClient();
  const router = useRouter();
  const [lottiAnimiert, setLottiAnimiert] = useState(false);
  const [bearbeiten, setBearbeiten] = useState(false);
  useEffect(() => setLottiAnimiert(true), []);

  // `?probe=2021&counted=N` wie beim Wahlabend und auf dem Beamer: Damit
  // lässt sich der eigene Tipp (1e) gegen die Zahlen von 2021 durchspielen,
  // bevor es echte gibt.
  const params = useSearchParams();
  // `?runde=vally`: ein eigener Kreis mit eigenen Tipps und eigenem Cookie
  // (prediction/rounds.py). Die Hauptrunde hat keinen Parameter.
  const runde = rundeAus(params);
  const setupPfad = mitRunde("/tipp/setup", runde);
  const meinPfad = mitRunde(probePfad("/tipp/me", params.get("probe"), params.get("counted")), runde);

  const setupQuery = useQuery({ queryKey: ["tipp", "setup", runde], queryFn: () => holeSetup(setupPfad), enabled: !!tippspielAn });
  const meinsQuery = useQuery({
    queryKey: ["tipp", "me", meinPfad], queryFn: () => holeMeins(meinPfad), enabled: !!tippspielAn,
    // Erst nach dem Tipp-Schluss lohnt sich das Nachfragen — vorher ändert
    // sich am eigenen Stand nichts, solange niemand tippt.
    refetchInterval: (query) => (query.state.data?.locked ? 30_000 : false),
  });

  function aufFrisch() {
    queryClient.invalidateQueries({ queryKey: ["tipp"] });
  }

  // `/tipp` steht auf alten QR-Codes und Sharepics der Ratswahl. Ist diese
  // Runde zu und läuft eine andere (die Stichwahl), schickt der Server
  // Neue dorthin (`successor_path`). Wer hier schon mitgespielt hat (Cookie,
  // `meins` da), bleibt bei seinem Ergebnis — der Tipp gehört zu dieser Runde.
  const setup = setupQuery.data;
  const meins = meinsQuery.data;
  const weiterZu = setup?.locked && meins === null && setup.successor_path ? setup.successor_path : null;
  useEffect(() => {
    if (weiterZu) router.replace(weiterZu);
  }, [weiterZu, router]);

  // Geteiltes Gerät (Schalter je Runde, Admin): „Fertig — nächste Person"
  // löscht nur den Cookie, der Tipp bleibt. Danach antwortet `/tipp/me`
  // wieder 401, und die Zustandsmaschine landet von selbst beim Einstieg.
  async function weitergeben() {
    try {
      await fetch(apiUrl(mitRunde("/tipp/abmelden", runde)), { method: "POST", credentials: "include" });
    } catch {
      // Ohne Verbindung bleibt der Cookie — beim nächsten Versuch klappt es.
    }
    setBearbeiten(false);
    aufFrisch();
  }

  if (configLaedt) return null; // wie useFeature überall: lieber später als falsch
  if (!tippspielAn) return <NichtFreigeschaltet />;
  if (setupQuery.error instanceof SetupFehler && setupQuery.error.status === 401) return <KontoNoetig />;
  if (setupQuery.isLoading || meinsQuery.isLoading || !setup || meins === undefined || weiterZu) return <LadeSchirm />;

  if (!meins) {
    return setup.locked
      ? <Spaetstarter setup={setup} runde={runde} lottiAnimiert={lottiAnimiert} onBeigetreten={aufFrisch} />
      : <Einstieg setup={setup} runde={runde} lottiAnimiert={lottiAnimiert} onBeigetreten={aufFrisch} />;
  }
  // Nach Tipp-Schluss darf noch tippen, wer NACH dem Schluss beigetreten ist
  // und noch keinen Tipp hat (der Server lässt genau das zu, als „nachgetippt").
  // Ohne diese Klausel landete ein Spätstarter direkt bei „Mein Tipp" — mit
  // leerer Tabelle und ohne jeden Weg zum Formular.
  const darfTippen = !meins.locked || (meins.late_at !== null && !meins.has_tip);
  // Wer schon getippt hat, sieht die BESTÄTIGUNG (1e) — so sieht der Plan es
  // vor, und sie ist die Antwort auf „hat das geklappt?". Zurück ins Formular
  // geht es über „Tipp ändern", solange offen ist (Artboard 1d trägt dafür
  // seine „‹ Zurück"-Zeile).
  if (darfTippen && (!meins.has_tip || bearbeiten)) {
    return (
      <Tippen
        setup={setup} meins={meins} runde={runde}
        onGespeichert={() => { setBearbeiten(false); aufFrisch(); }}
        onZurueck={meins.has_tip ? () => setBearbeiten(false) : undefined}
      />
    );
  }
  return (
    <MeinTipp
      setup={setup} meins={meins} runde={runde}
      onAendern={darfTippen ? () => setBearbeiten(true) : undefined}
      onWeitergeben={setup.shared_device ? weitergeben : undefined}
    />
  );
}
