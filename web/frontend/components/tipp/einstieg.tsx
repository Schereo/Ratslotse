"use client";

// 1c — Einstieg nach dem QR-Scan: Name eingeben, drei Regeln in einem Satz,
// „Los geht's". Kein Konto, keine E-Mail — der Name ist alles, was diese
// Seite über die Person weiß.

import { useState } from "react";
import { apiUrl } from "@/lib/api";
import type { TippSetup } from "@/lib/tipp";
import { BrandMark } from "@/components/brand";
import { Mascot } from "@/components/mascot";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export function Einstieg({ setup, lottiAnimiert, onBeigetreten }: {
  setup: TippSetup;
  lottiAnimiert: boolean;
  onBeigetreten: () => void;
}) {
  const [name, setName] = useState("");
  const [fehler, setFehler] = useState<string | null>(null);
  const [sendet, setSendet] = useState(false);

  async function beitreten() {
    if (sendet) return;
    setFehler(null);
    setSendet(true);
    try {
      const res = await fetch(apiUrl("/tipp"), {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        setFehler(typeof body?.detail === "string" ? body.detail : "Das hat nicht geklappt — versuch es noch einmal.");
        return;
      }
      onBeigetreten();
    } catch {
      setFehler("Keine Verbindung zum Server — versuch es noch einmal.");
    } finally {
      setSendet(false);
    }
  }

  return (
    <div className="mx-auto flex min-h-[100dvh] max-w-md flex-col items-center px-5 pb-7 pt-[calc(env(safe-area-inset-top)+12px)] text-center">
      <div className="flex items-center gap-2 self-start">
        <BrandMark className="h-[26px] w-[26px]" />
        <span className="font-display text-base font-bold tracking-tight text-foreground">Ratslotse</span>
        <span className="text-xs text-muted-foreground">· Tippspiel</span>
      </div>

      <div className="mt-5">
        <Mascot pose="wave" regie={lottiAnimiert ? "ruhig" : "aus"} className="h-24 w-24" decorative />
      </div>

      <p className="mt-3 font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-primary">
        Ratswahl Oldenburg · 13.09.2026
      </p>
      <h1 className="mt-2 text-balance font-display text-[28px] font-bold leading-[1.1] tracking-tight">
        Wer tippt den Rat am besten?
      </h1>
      <p className="mt-2.5 text-sm leading-relaxed text-muted-foreground">
        Verteile 52 Sitze auf 16 Listen. Wenn du magst, tippst du auch, wie viel Prozent die OB-Kandidaturen holen.
      </p>

      <form
        className="mt-5 w-full rounded-[14px] border border-border bg-card p-3.5 text-left"
        onSubmit={(e) => { e.preventDefault(); void beitreten(); }}
      >
        <label htmlFor="tipp-name" className="block text-xs font-semibold text-muted-foreground">
          Dein Name, wie er auf dem Scoreboard stehen soll
        </label>
        <Input
          id="tipp-name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="z. B. Anna K."
          maxLength={30}
          autoFocus
          className="mt-2 h-[46px] text-base font-semibold"
        />
        <p className="mt-2 text-[11.5px] text-muted-foreground">
          Öffentlich sichtbar im Raum. Kein Konto, keine E-Mail.
        </p>
        {fehler && <p className="mt-2 text-[11.5px] font-medium text-destructive">{fehler}</p>}

        <Button
          type="submit"
          variant="primary"
          disabled={name.trim().length < 2 || sendet}
          className="mt-3.5 h-[50px] w-full text-base"
        >
          {sendet ? "Einen Moment …" : "Los geht's — tippen"}
        </Button>
      </form>

      <div className="mt-4 grid w-full grid-cols-3 gap-2 text-left text-[11.5px] text-muted-foreground">
        <div className="rounded-[10px] bg-primary/5 p-2.5">
          <strong className="block text-[13px] text-foreground">bis ~20 Uhr</strong>
          Tippen bis zur ersten Hochrechnung, änderbar
        </div>
        <div className="rounded-[10px] bg-primary/5 p-2.5">
          <strong className="block text-[13px] text-foreground">5 · 3 · 1</strong>
          Punkte je Liste: exakt, ±1, ±2 Sitze
        </div>
        <div className="rounded-[10px] bg-primary/5 p-2.5">
          <strong className="block text-[13px] text-foreground">OB-Bonus</strong>
          bis 6 Punkte je Kandidatur
        </div>
      </div>
    </div>
  );
}
