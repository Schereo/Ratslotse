"use client";

// 1c — Einstieg nach dem QR-Scan: Name eingeben (und freiwillig die
// Parteizugehörigkeit), drei Regeln in einem Satz, „Los geht's". Kein
// Konto, keine E-Mail — Name und Partei sind alles, was diese Seite über die
// Person weiß.
//
// Die Texte hängen an der Wahlart (`tip_kind`): Bei einer Ratswahl werden
// Sitze verteilt, bei einer OB- oder Stichwahl Prozente getippt. Bis
// 19.09.2026 stand hier für jede Runde „Verteile 52 Sitze auf 16
// Wahllisten" — bei der Stichwahl wären das „0 Sitze auf 0 Wahllisten".

import Link from "next/link";
import { useState } from "react";
import { apiUrl } from "@/lib/api";
import { kandidaturenSatz, kurzesDatum, mitRunde } from "@/lib/tipp";
import type { TippSetup } from "@/lib/tipp";
import { BrandMark } from "@/components/brand";
import { Mascot } from "@/components/mascot";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ParteiAuswahl } from "./partei";

/** Der Hinweis unter dem Namensfeld — Tims Wunsch 19.09.2026: Die Leute
 *  sollen einander in der Rangliste wiedererkennen. Für Einstieg UND
 *  Spätstarter derselbe Satz. */
export function NamensHinweis() {
  return (
    <p className="mt-2 text-[11.5px] leading-relaxed text-muted-foreground">
      Bitte deinen richtigen Namen — so erkennen die anderen in der Rangliste, wer du bist.
      Er ist für alle sichtbar; ein Konto brauchst du nicht.
    </p>
  );
}

/** Die drei Regel-Kacheln unter dem Formular, je Wahlart. */
export function RegelKacheln({ setup }: { setup: TippSetup }) {
  const sitzwahl = setup.tip_kind === "seats";
  const kacheln = sitzwahl
    ? [
        ["bis ca. 20 Uhr", "Bis zur ersten Hochrechnung kannst du deinen Tipp ändern."],
        ["5 · 3 · 1", "Punkte je Liste: genau richtig, 1 oder 2 Sitze daneben"],
        ["OB-Bonus", "bis zu 6 Punkte pro Person, dazu 6 für die Wahlbeteiligung"],
      ]
    : [
        ["ab 18 Uhr", "Mit dem ersten Auszählungsstand endet die Tippfrist."],
        ["6 · 3 · 1", "Punkte je Kandidatur: höchstens 0,5 / 1,5 / 3 Prozentpunkte daneben"],
        ["Wahlbeteiligung", "bis zu 6 Punkte: 1 / 2,5 / 5 Punkte daneben"],
      ];
  return (
    <div className="mt-4 grid w-full grid-cols-3 gap-2 text-left text-[11.5px] text-muted-foreground">
      {kacheln.map(([stark, text]) => (
        <div key={stark} className="rounded-[10px] bg-primary/5 p-2.5">
          <strong className="block text-[13px] text-foreground">{stark}</strong>
          {text}
        </div>
      ))}
    </div>
  );
}

export function Einstieg({ setup, runde, lottiAnimiert, onBeigetreten }: {
  setup: TippSetup;
  runde: string | null;
  lottiAnimiert: boolean;
  onBeigetreten: () => void;
}) {
  // In einer Konto-Runde gibt es keinen Namen einzutippen: Der steht im
  // Profil, und der Tipp hängt am Konto statt am Browser. Die Partei bleibt
  // auch dort eine Frage — sie steht in keinem Profil.
  const mitKonto = !setup.public;
  const sitzwahl = setup.tip_kind === "seats";
  const [name, setName] = useState("");
  const [partei, setPartei] = useState("");
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
        body: JSON.stringify({ name: mitKonto ? null : name, party: partei || null }),
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
        {sitzwahl
          ? <>Verteile {setup.seats_total} Sitze auf {setup.parties.length} Wahllisten. Wenn du magst, tippe auch, wer wie viel Prozent bei der Oberbürgermeisterwahl (OB-Wahl) bekommt — und wie hoch die Wahlbeteiligung wird.</>
          : <>Tippe, wie viel Prozent {kandidaturenSatz(setup.mayor_candidates)} bekommen — und wie hoch die Wahlbeteiligung wird.</>}
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
              placeholder="z. B. Anna Kaiser"
              maxLength={30}
              autoFocus
              className="mt-2 h-[46px] text-base font-semibold"
            />
            <NamensHinweis />
          </>
        )}
        <ParteiAuswahl id="tipp-partei" optionen={setup.party_options} wert={partei} onChange={setPartei} className="mt-4" />
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

      <RegelKacheln setup={setup} />
    </div>
  );
}
