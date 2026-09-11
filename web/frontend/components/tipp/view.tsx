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

import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { apiUrl } from "@/lib/api";
import { useAppConfig, useFeature } from "@/lib/features";
import type { TippMeins, TippSetup } from "@/lib/tipp";
import { BrandMark } from "@/components/brand";
import { Mascot } from "@/components/mascot";
import { Einstieg } from "./einstieg";
import { Spaetstarter } from "./spaetstarter";
import { Tippen } from "./tippen";
import { MeinTipp } from "./mein-tipp";

async function holeSetup(): Promise<TippSetup> {
  const res = await fetch(apiUrl("/tipp/setup"), { credentials: "include" });
  if (!res.ok) throw new Error("setup");
  return res.json();
}

/** `null` heißt „nicht beigetreten" — ein ganz normaler Zustand, kein Fehler. */
async function holeMeins(): Promise<TippMeins | null> {
  const res = await fetch(apiUrl("/tipp/me"), { credentials: "include" });
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
        Das Tippspiel schläft noch
      </h1>
      <p className="mt-2.5 text-sm leading-relaxed text-muted-foreground">
        Es geht rund um den Wahlabend am 13. September los. Komm gern über den Link zurück, den du bekommen hast.
      </p>
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
  const { data: config, isLoading: configLaedt } = useAppConfig();
  const tippspielAn = useFeature("tippspiel");
  const queryClient = useQueryClient();
  const [lottiAnimiert, setLottiAnimiert] = useState(false);
  useEffect(() => setLottiAnimiert(true), []);

  const setupQuery = useQuery({ queryKey: ["tipp", "setup"], queryFn: holeSetup, enabled: !!tippspielAn });
  const meinsQuery = useQuery({
    queryKey: ["tipp", "me"], queryFn: holeMeins, enabled: !!tippspielAn,
    // Erst nach dem Tipp-Schluss lohnt sich das Nachfragen — vorher ändert
    // sich am eigenen Stand nichts, solange niemand tippt.
    refetchInterval: (query) => (query.state.data?.locked ? 30_000 : false),
  });

  function aufFrisch() {
    queryClient.invalidateQueries({ queryKey: ["tipp"] });
  }

  if (configLaedt) return null; // wie useFeature überall: lieber später als falsch
  if (!tippspielAn) return <NichtFreigeschaltet />;
  if (setupQuery.isLoading || meinsQuery.isLoading || !setupQuery.data) return <LadeSchirm />;

  const setup = setupQuery.data;
  const meins = meinsQuery.data;

  if (!meins) {
    return setup.locked
      ? <Spaetstarter setup={setup} lottiAnimiert={lottiAnimiert} onBeigetreten={aufFrisch} />
      : <Einstieg setup={setup} lottiAnimiert={lottiAnimiert} onBeigetreten={aufFrisch} />;
  }
  // Nach Tipp-Schluss darf noch tippen, wer NACH dem Schluss beigetreten ist
  // und noch keinen Tipp hat (der Server lässt genau das zu, als „nachgetippt").
  // Ohne diese Klausel landete ein Spätstarter direkt bei „Mein Tipp" — mit
  // leerer Tabelle und ohne jeden Weg zum Formular.
  const darfNochTippen = !meins.locked || (meins.late_at !== null && !meins.has_tip);
  if (darfNochTippen) {
    return <Tippen setup={setup} meins={meins} onGespeichert={aufFrisch} />;
  }
  return <MeinTipp setup={setup} meins={meins} />;
}
