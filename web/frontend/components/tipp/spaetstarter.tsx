"use client";

// 1f — Einstieg NACH Tipp-Schluss: Wer jetzt kommt, darf noch mitspielen,
// der Tipp läuft aber als „Nachgetippt HH:MM" — fair für alle, die vor dem
// Tipp-Schluss geraten haben. Zwei Wege: trotzdem tippen, oder nur zuschauen.

import Link from "next/link";
import { useState } from "react";
import { apiUrl } from "@/lib/api";
import { uhrzeitKurz } from "@/lib/tipp";
import type { TippSetup } from "@/lib/tipp";
import { BrandMark } from "@/components/brand";
import { Mascot } from "@/components/mascot";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export function Spaetstarter({ setup, lottiAnimiert, onBeigetreten }: {
  setup: TippSetup;
  lottiAnimiert: boolean;
  onBeigetreten: () => void;
}) {
  const [name, setName] = useState("");
  const [fehler, setFehler] = useState<string | null>(null);
  const [sendet, setSendet] = useState(false);

  const schlussZeit = uhrzeitKurz(setup.locked_at);
  const spaetSatz = setup.player_count > 0
    ? ` Schon ${setup.player_count} ${setup.player_count === 1 ? "Person hat" : "Leute haben"} mitgetippt.`
    : "";

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
    <div className="mx-auto flex min-h-[100dvh] max-w-md flex-col items-center px-5 pb-6 pt-[calc(env(safe-area-inset-top)+12px)] text-center">
      <div className="flex items-center gap-2 self-start">
        <BrandMark className="h-[26px] w-[26px]" />
        <span className="font-display text-base font-bold tracking-tight text-foreground">Ratslotse</span>
        <span className="text-xs text-muted-foreground">· Tippspiel</span>
      </div>

      <div className="mt-5">
        <Mascot pose="confused" regie={lottiAnimiert ? "ruhig" : "aus"} className="h-[88px] w-[88px]" decorative />
      </div>

      <h1 className="mt-3 text-balance font-display text-2xl font-bold leading-[1.1] tracking-tight">
        Die erste Hochrechnung ist schon da.
      </h1>
      <p className="mt-2.5 text-sm leading-relaxed text-muted-foreground">
        Tipp-Schluss war um <strong className="text-foreground">{schlussZeit ?? "kurz nach 18 Uhr"}</strong>. Du
        kannst trotzdem mitspielen — dein Tipp wird für alle sichtbar als{" "}
        <strong className="text-foreground">nachgetippt</strong> markiert.{spaetSatz}
      </p>

      <div className="mt-4.5 flex w-full items-start gap-2.5 rounded-[14px] border border-[#fde68a] bg-[#fffbeb] p-3.5 text-left">
        <span className="mt-0.5 flex-none rounded-full border border-[#fde68a] bg-white px-2 py-0.5 font-mono text-[10px] uppercase tracking-[0.08em] text-[#92400e]">
          Nachgetippt
        </span>
        <p className="text-[12.5px] leading-relaxed text-[#92400e]">
          So erscheint dein Name auf dem Scoreboard und in deinem Tipp. Fair für alle, die vor Tipp-Schluss geraten haben.
        </p>
      </div>

      <form
        className="mt-3.5 w-full rounded-[14px] border border-border bg-card p-3.5 text-left"
        onSubmit={(e) => { e.preventDefault(); void beitreten(); }}
      >
        <label htmlFor="tipp-name-spaet" className="block text-xs font-semibold text-muted-foreground">
          Dein Name
        </label>
        <Input
          id="tipp-name-spaet"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="z. B. Anna K."
          maxLength={30}
          autoFocus
          className="mt-2 h-[46px] text-base font-semibold"
        />
        {fehler && <p className="mt-2 text-[11.5px] font-medium text-destructive">{fehler}</p>}

        <Button type="submit" variant="primary" disabled={name.trim().length < 2 || sendet} className="mt-3.5 h-[50px] w-full text-base">
          {sendet ? "Einen Moment …" : "Trotzdem tippen"}
        </Button>
      </form>

      <Button asChild variant="ghost" className="mt-2 h-11 w-full text-sm">
        <Link href="/tipp/live">Nur zuschauen — zur Rangliste</Link>
      </Button>
    </div>
  );
}
