"use client";

// 1d — Tippen: 52 Sitze auf 16 Listen verteilen, optional die OB-Wahl
// (Ratswahl) — oder die Prozente der Kandidaturen (OB-/Stichwahl). Dazu seit
// 19.09.2026 freiwillig die Wahlbeteiligung, bei jeder Wahlart. Der Rest
// wird live nachgeführt (segmentierte Leiste + Text); abgegeben wird erst
// auf Knopfdruck, und nur wenn die Summen stimmen.

import { useMemo, useState } from "react";
import { Check, ChevronLeft, Loader2 } from "lucide-react";
import { apiUrl } from "@/lib/api";
import {
  beteiligungAus,
  fehltText,
  mitRunde,
  prozentText,
  restObText,
  restObTon,
  restSitze,
  restSitzeText,
  restSitzeTon,
  restOb,
  tippSegmente,
} from "@/lib/tipp";
import type { TippMeins, TippSetup } from "@/lib/tipp";
import { Aufklapp } from "@/components/aufklapp";
import { Switch } from "@/components/ui/switch";

/** Ein `type="number"`-Feld ohne die nativen Auf/Ab-Pfeile.
 *
 *  `appearance-none` allein reicht NICHT — im Gegenteil: Safari zeichnet
 *  seinen Stepper gerade dann (Tims Bild vom 11.09.: die Pfeile standen
 *  neben der 17, in Chromium war dieselbe Seite sauber). Chromium blendet
 *  ihn über die beiden `-webkit-…-spin-button`-Pseudos aus, Firefox und
 *  Safari erst bei `appearance: textfield`. Deshalb alle Wege zusammen.
 *  `m-0` nimmt den Platz, den der Stepper auch unsichtbar noch reserviert
 *  — sonst steht die Zahl nicht mittig (der Befund vom 11.09. im Admin). */
const OHNE_PFEILE =
  "[appearance:textfield] [&::-webkit-inner-spin-button]:m-0 [&::-webkit-inner-spin-button]:appearance-none"
  + " [&::-webkit-outer-spin-button]:m-0 [&::-webkit-outer-spin-button]:appearance-none";

export function Tippen({ setup, meins, runde, onGespeichert, onZurueck }: {
  setup: TippSetup;
  meins: TippMeins;
  runde: string | null;
  /** Wird NACH dem Bestätigungs-Takt gerufen — der Aufrufer wechselt dann
   *  auf „Mein Tipp" (1e). */
  onGespeichert: () => void;
  /** Nur beim Ändern eines vorhandenen Tipps: zurück ohne zu speichern. */
  onZurueck?: () => void;
}) {
  // Ein neuer Tipp fängt bei NULL an — alle Sitze werden selbst verteilt.
  // Bis 13.09.2026 stand hier die Verteilung der Vorwahl als Vorschlag; wer
  // nur „Tipp abgeben" drückte, tippte damit unbemerkt das letzte Ergebnis
  // nach (Tims Befund). Ein Tipp soll eine Entscheidung sein, kein
  // Bestätigen. Die Zahl der Vorwahl steht weiter unter jeder Liste — als
  // Anhaltspunkt, nicht als Vorgabe.
  const [seats, setSeats] = useState<Record<string, number>>(() =>
    meins.has_tip
      ? Object.fromEntries(meins.seats.map((s) => [s.slug, s.tip]))
      : Object.fromEntries(setup.parties.map((p) => [p.slug, 0])),
  );
  // „seats" = Sitze verteilen (Ratswahl), „pct" = nur Prozente (OB- oder
  // Stichwahl). Die Antwort sagt es; die Komponente deutet keine Wahlart.
  const sitzwahl = setup.tip_kind === "seats";
  // Bei einer reinen Prozentwahl ist der Prozentteil kein Zusatz, sondern
  // das Spiel — der Schalter entfällt.
  const [obOffen, setObOffen] = useState(sitzwahl ? meins.has_mayor_tip : true);
  const [ob, setOb] = useState<Record<string, number>>(() =>
    Object.fromEntries(meins.mayor.map((m) => [m.slug, m.tip])),
  );
  // Die Wahlbeteiligung als Text, nicht als Zahl: Ein leeres Feld heißt
  // „nicht getippt" — eine 0 wäre ein Tipp, und ein schlechter.
  const [beteiligung, setBeteiligung] = useState(() =>
    meins.turnout ? meins.turnout.tip.toLocaleString("de-DE", { maximumFractionDigits: 1 }) : "",
  );
  const [sendet, setSendet] = useState(false);
  const [gespeichert, setGespeichert] = useState(false);
  const [fehler, setFehler] = useState<string | null>(null);

  const rest = restSitze(seats, setup.seats_total);
  const restText = restSitzeText(rest, setup.seats_total);
  const ton = restSitzeTon(rest);
  const segmente = useMemo(() => tippSegmente(seats, setup.parties, setup.seats_total), [seats, setup.parties, setup.seats_total]);

  const obRest = restOb(ob);
  const obTon = restObTon(obRest);
  // `fehlt` ist der Grund, warum nicht abgegeben werden kann — und zugleich
  // die Beschriftung des Knopfes. Eine Wahrheit statt zwei, die
  // auseinanderlaufen können.
  const fehlt = sitzwahl ? fehltText(rest, obOffen, obRest) : fehltText(0, true, obRest);
  const kannAbgeben = fehlt === null && !sendet && !gespeichert;

  function setzeSitz(slug: string, wert: number) {
    const geklemmt = Math.max(0, Math.min(setup.seats_total, Math.round(Number.isFinite(wert) ? wert : 0)));
    setSeats((s) => ({ ...s, [slug]: geklemmt }));
  }

  function setzeOb(slug: string, wert: number) {
    const geklemmt = Math.max(0, Math.min(100, Number.isFinite(wert) ? wert : 0));
    setOb((o) => ({ ...o, [slug]: geklemmt }));
  }

  async function abgeben() {
    if (!kannAbgeben) return;
    setSendet(true);
    setFehler(null);
    try {
      const res = await fetch(apiUrl(mitRunde("/tipp", runde)), {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ seats: sitzwahl ? seats : null, mayor: obOffen ? ob : null, turnout: beteiligungAus(beteiligung) }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        setFehler(typeof body?.detail === "string" ? body.detail : "Das hat nicht geklappt — versuch es noch einmal.");
        // 409 heißt: Der Tipp-Schluss ist gefallen, während hier noch getippt
        // wurde (die erste Hochrechnung setzt ihn von selbst). Dann ist das
        // Formular tot — nach dem Lesen der Meldung zurück auf „Mein Tipp",
        // wo der zuletzt gespeicherte Tipp steht.
        if (res.status === 409) setTimeout(onGespeichert, 2500);
        return;
      }
      // Der Bestätigungs-Takt: Der Knopf sagt „Gespeichert" und bleibt einen
      // Moment stehen, BEVOR die Ansicht wechselt. Ohne ihn sprang die Seite
      // sofort auf „Tipp aktualisieren" — man wusste nicht, ob der Tipp
      // angekommen war (Tims Befund 11.09.). 900 ms sind lang genug, um den
      // Haken zu sehen, und kurz genug, um nicht zu warten.
      setGespeichert(true);
      setTimeout(onGespeichert, 900);
    } catch {
      setFehler("Keine Verbindung zum Server — versuch es noch einmal.");
    } finally {
      setSendet(false);
    }
  }

  //: Der Knopf sagt immer, was gerade gilt: was noch fehlt, dass gerade
  //: gespeichert wird, dass es geklappt hat — oder was ein Druck täte.
  const knopfText = gespeichert
    ? "Gespeichert"
    : sendet
      ? "Speichert …"
      : fehlt ?? (meins.has_tip ? "Tipp aktualisieren" : "Tipp abgeben");

  return (
    <div className="mx-auto min-h-[100dvh] max-w-md pb-8">
      {onZurueck && (
        <div className="flex items-center justify-between px-4 pt-[calc(env(safe-area-inset-top)+10px)] text-[13px]">
          <button type="button" onClick={onZurueck} className="-ml-1 inline-flex items-center gap-0.5 rounded-md px-1 py-0.5 font-medium text-primary transition-colors hover:bg-accent">
            <ChevronLeft className="h-4 w-4" /> Zurück
          </button>
          <span className="text-muted-foreground">{meins.name} · Tipp ändern</span>
        </div>
      )}
      {sitzwahl && (
        <div className="sticky top-0 z-20 mx-4 mt-3 rounded-[14px] border border-border bg-card p-3 pt-[calc(env(safe-area-inset-top)+12px)] shadow-[0_1px_2px_rgba(0,0,0,0.04)]">
          <div className="flex items-baseline justify-between">
            <span className="font-display text-[17px] font-bold">Sitze im Rat</span>
            <span className={`font-mono text-xs ${ton === "ok" ? "text-emerald-600 dark:text-emerald-400" : "text-amber-700 dark:text-amber-400"}`}>
              {restText}
            </span>
          </div>
          <div className="mt-2 flex h-2 overflow-hidden rounded-full bg-muted">
            {segmente.map((s) => (
              <div key={s.slug} style={{ width: s.breite, background: s.farbe }} className="h-full transition-[width] duration-200" />
            ))}
          </div>
          <p className="mt-1.5 text-[11.5px] text-muted-foreground">
            Verteile insgesamt {setup.seats_total} Sitze. Mit 0 tippst du, dass diese Liste keinen Sitz bekommt.
          </p>
        </div>
      )}
      {meins.late_at !== null && (
        <p className="mx-4 mt-3 rounded-[10px] border border-amber-200 bg-amber-50 px-3 py-2 text-[12px] leading-relaxed text-amber-800 dark:border-amber-900/50 dark:bg-amber-900/20 dark:text-amber-200">
          Die Tippfrist ist vorbei. Dein Tipp wird als <strong>später abgegeben</strong> gekennzeichnet. {setup.late_scored ? "Er zählt bei der Platzierung mit." : "Er bekommt Punkte, aber keinen Platz in der Rangliste."}
        </p>
      )}

      <div className="mt-2 flex flex-col gap-1.5 px-4">
        {(sitzwahl ? setup.parties : []).map((p) => (
          <div key={p.slug} className="flex items-center gap-2.5 rounded-xl border border-border bg-card py-2 pl-3 pr-2">
            <span
              className="h-2 w-2 flex-none rounded-full shadow-[inset_0_0_0_1px_rgba(0,0,0,0.15)]"
              style={{ background: p.color }}
            />
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-semibold leading-tight">{p.short}</p>
              <p className="text-[11px] text-muted-foreground">
                {p.seats_previous !== null && setup.previous_label
                  ? `${setup.previous_label}: ${p.seats_previous}`
                  : "neu angetreten"}
              </p>
            </div>
            <button
              type="button"
              aria-label={`${p.short}: einen Sitz weniger`}
              onClick={() => setzeSitz(p.slug, (seats[p.slug] ?? 0) - 1)}
              className="flex h-11 w-11 flex-none items-center justify-center rounded-[10px] border border-border bg-primary/5 text-xl text-primary"
            >
              −
            </button>
            <input
              type="number"
              inputMode="numeric"
              aria-label={`Sitze für ${p.short}`}
              value={seats[p.slug] ?? 0}
              onChange={(e) => setzeSitz(p.slug, Number(e.target.value))}
              className={`h-11 w-[46px] flex-none rounded-[10px] border border-border bg-card text-center font-display text-lg font-bold text-foreground ${OHNE_PFEILE}`}
            />
            <button
              type="button"
              aria-label={`${p.short}: einen Sitz mehr`}
              onClick={() => setzeSitz(p.slug, (seats[p.slug] ?? 0) + 1)}
              className="flex h-11 w-11 flex-none items-center justify-center rounded-[10px] border border-border bg-primary/5 text-xl text-primary"
            >
              +
            </button>
          </div>
        ))}
      </div>

      <div className="mx-4 mt-4.5 rounded-[14px] border border-border bg-card p-3.5">
        <div className="flex items-center justify-between gap-2.5">
          <div>
            <p className="font-display text-base font-bold">
              {sitzwahl ? "OB-Wahl mittippen" : "Wer wird OB?"}
            </p>
            <p className="mt-0.5 text-xs text-muted-foreground">
              {sitzwahl ? "Freiwillig · bis zu 6 Bonuspunkte pro Person" : "Stimmenanteile in Prozent · bis zu 6 Punkte pro Person"}
            </p>
          </div>
          {/* Bei einer reinen Prozentwahl gibt es nichts zuzuschalten — der
              Block IST das Spiel. */}
          {sitzwahl && <Switch checked={obOffen} onCheckedChange={setObOffen} aria-label="OB-Wahl mittippen" />}
        </div>
        <Aufklapp offen={obOffen}>
          <div className="mt-3 flex flex-col gap-1.5">
            <div className="flex justify-between text-[11.5px] text-muted-foreground">
              <span>Stimmenanteile in %, insgesamt höchstens 100 %</span>
              <span className={`font-mono ${obTon === "ok" ? "text-emerald-600 dark:text-emerald-400" : "text-amber-700 dark:text-amber-400"}`}>
                {restObText(obRest)}
              </span>
            </div>
            {setup.mayor_candidates.map((o) => (
              <div key={o.slug} className="flex items-center gap-2.5 border-t border-muted py-1.5">
                <div className="min-w-0 flex-1">
                  <p className="truncate text-[13.5px] font-semibold">{o.name}</p>
                  {/* „vorgeschlagen von", nicht bloß der Listenname: Der
                      Stimmzettel lässt je Kandidatur genau eine Liste zu,
                      und wer dort steht, muss weder deren Mitglied sein noch
                      ihre einzige Unterstützung haben. */}
                  <p className="text-[11px] text-muted-foreground">
                    {o.party === "Einzelwahlvorschlag" ? o.party : `vorgeschlagen von ${o.party}`}
                  </p>
                </div>
                <div className="flex items-center gap-1">
                  <input
                    type="number"
                    inputMode="decimal"
                    step={0.5}
                    aria-label={`Prozent für ${o.name}`}
                    value={ob[o.slug] ?? 0}
                    onChange={(e) => setzeOb(o.slug, Number(e.target.value))}
                    className={`h-10 w-[58px] rounded-[10px] border border-border bg-card px-2 text-right font-display text-base font-bold text-foreground ${OHNE_PFEILE}`}
                  />
                  <span className="text-[13px] text-muted-foreground">%</span>
                </div>
              </div>
            ))}
          </div>
        </Aufklapp>
      </div>

      {/* Die Wahlbeteiligung — freiwillig, bei jeder Wahlart, ein Feld. Bei
          einer Stichwahl ist sie DIE Frage des Abends (zwei Kandidaturen,
          wenig zu verteilen), deshalb steht sie hier als eigene Karte und
          nicht als Zeile unter den Kandidaturen. */}
      <div className="mx-4 mt-3 rounded-[14px] border border-border bg-card p-3.5">
        <div className="flex items-center justify-between gap-3">
          <div className="min-w-0">
            <p className="font-display text-base font-bold">Wahlbeteiligung tippen</p>
            <p className="mt-0.5 text-xs text-muted-foreground">
              Freiwillig · bis zu 6 Punkte
              {setup.turnout_previous !== null && setup.turnout_previous_label
                ? ` · ${setup.turnout_previous_label}: ${prozentText(setup.turnout_previous)}`
                : ""}
            </p>
          </div>
          <div className="flex flex-none items-center gap-1">
            <input
              type="number"
              inputMode="decimal"
              step={0.5}
              min={0}
              max={100}
              aria-label="Wahlbeteiligung in Prozent"
              placeholder="z. B. 45"
              value={beteiligung}
              onChange={(e) => setBeteiligung(e.target.value)}
              className={`h-11 w-[72px] rounded-[10px] border border-border bg-card px-2 text-right font-display text-lg font-bold text-foreground placeholder:font-sans placeholder:text-sm placeholder:font-normal placeholder:text-muted-foreground ${OHNE_PFEILE}`}
            />
            <span className="text-[13px] text-muted-foreground">%</span>
          </div>
        </div>
      </div>

      {fehler && <p className="mx-4 mt-3 text-[12.5px] font-medium text-destructive">{fehler}</p>}

      <div className="sticky bottom-0 mt-4 bg-gradient-to-t from-background from-30% px-4 pb-[calc(env(safe-area-inset-bottom)+16px)] pt-4">
        <button
          type="button"
          disabled={!kannAbgeben}
          onClick={() => void abgeben()}
          className="flex h-[50px] w-full items-center justify-center gap-2 rounded-xl text-base font-semibold text-primary-foreground transition-[background-color,transform] duration-200 ease-out-strong active:scale-[0.98] disabled:cursor-not-allowed motion-reduce:transition-none"
          style={{
            background: gespeichert
              ? "hsl(152 60% 36%)"
              : kannAbgeben || sendet ? "hsl(var(--primary))" : "hsl(var(--muted-foreground) / 0.4)",
          }}
        >
          {sendet && <Loader2 className="h-[18px] w-[18px] animate-spin motion-reduce:animate-none" aria-hidden />}
          {gespeichert && <Check className="animate-fade-up h-[18px] w-[18px]" aria-hidden />}
          {knopfText}
        </button>
        <p className="mt-2 text-center text-[11.5px] text-muted-foreground">
          {meins.late_at !== null ? "Nach dem Abgeben kannst du deinen Tipp nicht mehr ändern." : setup.deadline_hint}
        </p>
      </div>
    </div>
  );
}
