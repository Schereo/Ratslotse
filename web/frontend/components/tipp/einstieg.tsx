"use client";

// 1c — Einstieg nach dem QR-Scan: Name eingeben, drei Regeln in einem Satz,
// „Los geht's". Kein Konto, keine E-Mail — der Name ist alles, was diese
// Seite über die Person weiß.

import Link from "next/link";
import { useState } from "react";
import { apiUrl } from "@/lib/api";
import { kurzesDatum, mitRunde } from "@/lib/tipp";
import type { TippSetup } from "@/lib/tipp";
import { BrandMark } from "@/components/brand";
import { Mascot } from "@/components/mascot";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export function Einstieg({ setup, runde, lottiAnimiert, onBeigetreten }: {
  setup: TippSetup;
  runde: string | null;
  lottiAnimiert: boolean;
  onBeigetreten: () => void;
}) {
  // In einer Konto-Runde gibt es nichts einzutippen: Der Name steht im Profil,
  // und der Tipp hängt am Konto statt am Browser. Ohne diese Unterscheidung
  // stünde dort ein Feld, dessen Inhalt der Server verwirft.
  const mitKonto = !setup.public;
  const [name, setName] = useState("");
  const [fehler, setFehler] = useState<string | null>(null);
  const [sendet, setSendet] = useState(false);

  async function beitreten() {
    if (sendet) return;
    setFehler(null);
    setSendet(true);
    try {
      const res = await fetch(apiUrl(mitRunde("/tipp", runde)), {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: mitKonto ? null : name }),
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
        {/* Eine eigene Runde trägt ihren Namen im Kicker — wer über Vallys
            Link kommt, soll sehen, dass er in Vallys Kreis tippt. */}
        {setup.listed ? `${setup.election_title} · ${kurzesDatum(setup.election_date)}` : `${setup.title} · ${setup.election_title} · ${kurzesDatum(setup.election_date)}`}
      </p>
      <h1 className="mt-2 text-balance font-display text-[28px] font-bold leading-[1.1] tracking-tight">
        Wie geht die {setup.election_title} aus?
      </h1>
      <p className="mt-2.5 text-sm leading-relaxed text-muted-foreground">
        Verteile {setup.seats_total} Sitze auf {setup.parties.length} Wahllisten. Wenn du magst, tippe auch, wer wie viel Prozent bei der Oberbürgermeisterwahl (OB-Wahl) bekommt.
      </p>

      <form
        className="mt-5 w-full rounded-[14px] border border-border bg-card p-3.5 text-left"
        onSubmit={(e) => { e.preventDefault(); void beitreten(); }}
      >
        {mitKonto ? (
          <p className="text-[13px] leading-relaxed text-muted-foreground">
            Diese Runde läuft über dein Konto: In der Rangliste stehst du unter deinem Anzeigenamen, und dein Tipp
            ist auf jedem Gerät derselbe — ein Tipp je Konto.
          </p>
        ) : (
          <>
            <label htmlFor="tipp-name" className="block text-xs font-semibold text-muted-foreground">
              Dein Name in der Rangliste
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
              Dein Name ist für alle sichtbar. Du brauchst kein Konto und keine E-Mail-Adresse.
            </p>
          </>
        )}
        {fehler && <p className="mt-2 text-[11.5px] font-medium text-destructive">{fehler}</p>}

        <Button
          type="submit"
          variant="primary"
          disabled={(!mitKonto && name.trim().length < 2) || sendet}
          className="mt-3.5 h-[50px] w-full text-base"
        >
          {sendet ? "Einen Moment …" : "Jetzt mitmachen"}
        </Button>
      </form>

      {setup.shared_device && (
        // Geteiltes Gerät: Wer schon getippt hat, kommt hier wieder an —
        // ohne Cookie. Die Seite sagt, dass das so gehört, und zeigt den Weg
        // zur Rangliste, statt zu einem zweiten Beitritt zu verleiten.
        <p className="mt-3 w-full rounded-[10px] border border-dashed border-primary/30 px-3 py-2 text-[11.5px] leading-relaxed text-muted-foreground">
          Hier tippen mehrere Personen an einem Gerät. Schon getippt? Dein Tipp ist gespeichert —{" "}
          <Link href={mitRunde("/tipp/live", runde, "runde")} className="font-semibold text-primary underline-offset-2 hover:underline">zur Rangliste</Link>.
        </p>
      )}

      <div className="mt-4 grid w-full grid-cols-3 gap-2 text-left text-[11.5px] text-muted-foreground">
        <div className="rounded-[10px] bg-primary/5 p-2.5">
          <strong className="block text-[13px] text-foreground">bis ca. 20 Uhr</strong>
          Bis zur ersten Hochrechnung kannst du deinen Tipp ändern.
        </div>
        <div className="rounded-[10px] bg-primary/5 p-2.5">
          <strong className="block text-[13px] text-foreground">5 · 3 · 1</strong>
          Punkte je Liste: genau richtig, 1 oder 2 Sitze daneben
        </div>
        <div className="rounded-[10px] bg-primary/5 p-2.5">
          <strong className="block text-[13px] text-foreground">OB-Bonus</strong>
          bis zu 6 Punkte pro Person
        </div>
      </div>
    </div>
  );
}
