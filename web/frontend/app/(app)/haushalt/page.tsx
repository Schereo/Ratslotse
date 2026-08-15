"use client";

// /haushalt — Stadtfinanzen-Übersicht (Design H-01 Desktop / H-05 Mobil /
// H-06 Dunkel). Leserichtung: drei Kernzahlen → das Ersparte (die eigentliche
// Story) → Kern-Visual (Gegenbalken, Umschalter auf die 100-Euro-Ansicht) →
// Zeitreihe → Bereichskarten (Default-Sortierung Zuschussbedarf — so passiert
// der Brutto/Netto-Aha ohne Fußnote). Jede Karte trägt ihre Quelle.

import { useMemo, useState } from "react";
import Link from "next/link";
import { FileText } from "lucide-react";
import { Segmented } from "@/components/ui";
import { useFetch } from "@/lib/use-fetch";
import { Gegenbalken } from "@/components/haushalt/gegenbalken";
import { Steuereuro } from "@/components/haushalt/steuereuro";
import { Zeitreihe } from "@/components/haushalt/zeitreihe";
import { Sparkline } from "@/components/haushalt/sparkline";
import {
  BEREICH_INFO, HaushaltDaten, RUECKLAGE_MIO, RUECKLAGE_STAND,
  bereichSlug, bereiche, bereichsReihe, deMio, deckung, fehlendeJahre,
  jahreSortiert, mio, quellenLabel, summe,
} from "@/lib/haushalt";
import { cn } from "@/lib/utils";

function Kernzahl({ label, wert, hint, ton }: {
  label: string; wert: number | null; hint: string; ton?: "signal";
}) {
  return (
    <div className={cn(
      "rounded-2xl border bg-card p-4 shadow-sm",
      ton === "signal" ? "border-signal/40" : "border-border",
    )}>
      <p className={cn(
        "font-mono text-[10px] font-medium uppercase tracking-[0.11em]",
        ton === "signal" ? "text-signal" : "text-muted-foreground",
      )}>{label}</p>
      <p className={cn(
        "mt-1.5 font-display text-[26px] font-bold tracking-tight tabular-nums sm:text-3xl",
        ton === "signal" ? "text-signal" : "text-foreground",
      )}>
        {deMio(wert)}<span className="text-base font-semibold text-muted-foreground">&#8239;Mio.&nbsp;€</span>
      </p>
      <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{hint}</p>
    </div>
  );
}

/** Rücklagen-Hinweis (H-01): erklärt das Minus, statt es zu bewerten —
 *  Reichweite als offene Rechnung, ausgewiesen als solche. */
function RuecklagenHinweis({ defizit }: { defizit: number }) {
  if (defizit <= 0) return null;
  const stufen: { label: string; wert: number }[] = [];
  let rest = RUECKLAGE_MIO;
  let jahr = new Date().getFullYear();
  while (rest > 0 && stufen.length < 4) {
    stufen.push({ label: String(jahr), wert: rest });
    rest = Math.round((rest - defizit) * 10) / 10;
    jahr += 1;
  }
  const max = RUECKLAGE_MIO;
  return (
    <div className="flex flex-col gap-4 rounded-2xl border border-signal/40 border-l-[3px] border-l-signal bg-card p-4 shadow-sm sm:flex-row sm:items-center">
      <div className="min-w-0 flex-1">
        <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-signal">Das Ersparte der Stadt</p>
        <p className="mt-1.5 max-w-[74ch] text-sm leading-relaxed text-foreground/90">
          Das Minus wird aus der <strong>Rücklage von rund {RUECKLAGE_MIO}&#8239;Mio.&nbsp;€</strong> gedeckt.
          Bleibt es bei einem Minus in dieser Größe, ist die Rücklage in wenigen Jahren aufgebraucht.
          Was dann passiert, entscheidet der Rat — bisher gibt es dafür keinen Beschluss.
        </p>
        <p className="mt-2 text-[11.5px] text-muted-foreground">
          Rechnerische Reichweite, keine Prognose der Stadt. {RUECKLAGE_STAND}.
        </p>
      </div>
      <div className="w-full flex-none sm:w-[290px]">
        <div className="flex h-14 items-end gap-1.5">
          {stufen.map((s) => (
            <div key={s.label} className="flex flex-1 flex-col items-center gap-1">
              <div className="w-full rounded" style={{
                height: `${Math.max((s.wert / max) * 52, 4)}px`,
                background: `var(--hh-ein-${Math.min(stufen.indexOf(s) * 2, 6)})`,
              }} />
              <span className="font-mono text-[9.5px] text-muted-foreground">{s.label}</span>
            </div>
          ))}
          <div className="flex flex-1 flex-col items-center gap-1">
            <div className="hh-schraffur h-[9px] w-full rounded border border-dashed border-signal" />
            <span className="font-mono text-[9.5px] text-signal">{Number(stufen[stufen.length - 1]?.label ?? 0) + 1}</span>
          </div>
        </div>
        <p className="mt-1.5 text-[11px] leading-snug text-muted-foreground">
          {stufen.map((s) => deMio(s.wert)).join(" → ")} → <span className="font-semibold text-signal">aufgebraucht</span>,
          wenn das Minus bleibt.
        </p>
      </div>
    </div>
  );
}

export default function HaushaltPage() {
  const { data, loading } = useFetch<HaushaltDaten>("/council/haushalt");
  const jahre = useMemo(() => (data ? jahreSortiert(data) : []), [data]);
  const [jahr, setJahr] = useState<number | null>(null);
  const [visual, setVisual] = useState<"balken" | "euro">("balken");
  const [sortierung, setSortierung] = useState<"netto" | "brutto">("netto");
  const [alleBereiche, setAlleBereiche] = useState(false);

  const aktJahr = jahr ?? jahre[jahre.length - 1] ?? null;
  const zeilen = aktJahr && data ? data.jahre[String(aktJahr)] ?? [] : [];
  const gesamt = summe(zeilen);
  const einMio = mio(gesamt?.ertraege), ausMio = mio(gesamt?.aufwendungen);
  // Aus Rohwerten gerundet — 883,9 − 812,9 ergäbe 71,0, tatsächlich sind es 71,1.
  const defizit = gesamt?.ertraege != null && gesamt?.aufwendungen != null
    ? mio(gesamt.aufwendungen - gesamt.ertraege) : null;
  const luecken = fehlendeJahre(jahre);
  const quelle = aktJahr ? quellenLabel(zeilen, aktJahr) : null;

  const karten = useMemo(() => {
    const rows = bereiche(zeilen).map((z) => ({
      z,
      netto: -(mio(z.ergebnis) ?? 0),
      brutto: mio(z.aufwendungen) ?? 0,
      deckung: deckung(z),
    }));
    rows.sort((a, b) => (sortierung === "netto" ? b.netto - a.netto : b.brutto - a.brutto));
    return rows;
  }, [zeilen, sortierung]);

  if (loading || !data || !aktJahr) {
    return <div className="py-16 text-center text-sm text-muted-foreground">Haushalt wird geladen …</div>;
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Kopf: mobil führt ein Satz (H-05), Desktop Titel + Unterzeile (H-01). */}
      <div className="flex items-end justify-between gap-5">
        <div className="min-w-0">
          <p className="font-mono text-[10.5px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
            Stadtfinanzen Oldenburg
          </p>
          <h1 className="mt-1 font-display text-2xl font-bold tracking-tight sm:text-[27px]">
            Wohin fließt das Geld der Stadt?
          </h1>
          <p className="mt-1.5 max-w-[62ch] text-sm leading-relaxed text-muted-foreground">
            Der Haushalt ist der Plan, den der Rat beschließt: Was die Stadt im Jahr einnimmt und
            wofür sie es ausgibt. Hier steht er in ganzen Zahlen — mit Quelle an jeder Stelle.
          </p>
        </div>
        {quelle?.url && (
          <a href={quelle.url} target="_blank" rel="noopener noreferrer"
            className="hidden flex-none items-center gap-2 rounded-xl border border-border bg-card px-3 py-2 text-[12.5px] font-semibold text-primary shadow-sm desk:inline-flex">
            <FileText className="h-3.5 w-3.5" /> Quelle öffnen
          </a>
        )}
      </div>

      {/* Jahr-Umschalter — fehlende Jahre bleiben sichtbar (gestrichelt). */}
      <div className="flex flex-wrap items-center gap-2.5">
        <span className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">Haushaltsjahr</span>
        <div className="flex items-center gap-1 rounded-full border border-border bg-card p-1">
          {(() => {
            const alle: number[] = [];
            for (let y = jahre[0]; y <= jahre[jahre.length - 1]; y++) alle.push(y);
            return alle.map((y) =>
              jahre.includes(y) ? (
                <button key={y} type="button" onClick={() => setJahr(y)}
                  className={cn(
                    "rounded-full px-3 py-1 text-[12.5px]",
                    y === aktJahr ? "bg-primary font-semibold text-primary-foreground" : "text-foreground/75 hover:bg-accent",
                  )}>
                  {y}
                </button>
              ) : (
                <span key={y} title="Für dieses Jahr fehlen uns die Daten"
                  className="rounded-full border border-dashed border-border px-2.5 py-1 text-[12.5px] text-muted-foreground">
                  {y}
                </span>
              ));
          })()}
        </div>
        {luecken.length > 0 && (
          <span className="text-[11.5px] text-muted-foreground">
            Für {luecken.join(", ")} fehlen uns die Daten — die Zeitreihe zeigt die Lücke.
          </span>
        )}
      </div>

      {/* Kernzahlen */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <Kernzahl label="Nimmt die Stadt ein" wert={einMio}
          hint={`Steuern, Zuweisungen, Gebühren — geplant für ${aktJahr}`} />
        <Kernzahl label="Gibt die Stadt aus" wert={ausMio}
          hint="Personal, Leistungen, Zuschüsse, Gebäude" />
        {defizit != null && defizit > 0 ? (
          <Kernzahl label="Fehlt am Ende" wert={defizit} ton="signal"
            hint="Die Stadt plant mehr Ausgaben als Einnahmen — die Differenz kommt aus dem Ersparten." />
        ) : (
          <Kernzahl label="Bleibt übrig" wert={defizit != null ? -defizit : null}
            hint="Die Stadt plant mehr Einnahmen als Ausgaben." />
        )}
      </div>

      {defizit != null && <RuecklagenHinweis defizit={defizit} />}

      {/* Kern-Visual mit Umschalter Gegenbalken ↔ 100-Euro-Ansicht (H-03/H-04) */}
      <div className="rounded-2xl border border-border bg-card p-4 shadow-sm sm:p-5">
        <div className="mb-3 flex justify-end">
          <Segmented value={visual} onChange={setVisual} options={[
            { value: "balken", label: "Balken" },
            { value: "euro", label: "100-Euro-Ansicht" },
          ]} />
        </div>
        {visual === "balken"
          ? <Gegenbalken zeilen={zeilen} jahr={aktJahr} />
          : <Steuereuro zeilen={zeilen} jahr={aktJahr} />}
        {quelle && (
          <p className="mt-3 border-t border-dashed border-border pt-2.5 text-[11px] text-muted-foreground">
            Quelle: {quelle.url ? <a href={quelle.url} target="_blank" rel="noopener noreferrer" className="underline decoration-dotted">{quelle.text}</a> : quelle.text} · Ergebnishaushalt,
            ordentliche Erträge und Aufwendungen · Rundung auf eine Nachkommastelle.
          </p>
        )}
      </div>

      {/* Zeitreihe (H-07) */}
      <div className="rounded-2xl border border-border bg-card p-4 shadow-sm sm:p-5">
        <Zeitreihe daten={data} />
        <p className="mt-2.5 border-t border-dashed border-border pt-2.5 text-[11px] text-muted-foreground">
          Quelle: Beschlossene Haushaltspläne {jahre[0]}–{jahre[jahre.length - 1]}, Stadt Oldenburg · jeweils Planwerte, nicht Jahresabschluss.
        </p>
      </div>

      {/* Bereichskarten — Default nach Zuschussbedarf (der Aha passiert von selbst) */}
      <div>
        <div className="mb-2.5 flex items-baseline justify-between gap-3">
          <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
            Die Bereiche im Einzelnen
          </p>
          <Segmented value={sortierung} onChange={setSortierung} tone="primary" options={[
            { value: "netto", label: "nach Zuschussbedarf" },
            { value: "brutto", label: "nach Ausgaben" },
          ]} />
        </div>
        <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2 lg:grid-cols-3">
          {(alleBereiche ? karten : karten.slice(0, 6)).map(({ z, netto, brutto, deckung: d }) => {
            const reihe = bereichsReihe(data, z.bereich)
              .map((r) => ({ jahr: r.jahr, wert: -(mio(r.zeile.ergebnis) ?? 0) }));
            return (
              <Link key={z.bereich} href={`/haushalt/bereich?name=${bereichSlug(z.bereich)}`}
                className="rounded-xl border border-border bg-card p-3.5 shadow-sm transition-colors hover:border-primary/40">
                <div className="flex items-start justify-between gap-2.5">
                  <p className="text-[13px] font-bold leading-snug">{z.bereich}</p>
                  <Sparkline reihe={reihe} className="flex-none opacity-60" />
                </div>
                <p className="mt-2 font-display text-[21px] font-bold tracking-tight tabular-nums">
                  {sortierung === "netto" ? `−${deMio(netto)}` : deMio(brutto)}
                  <span className="text-xs font-semibold text-muted-foreground">&#8239;Mio.</span>
                </p>
                <p className="text-[11.5px] text-muted-foreground">
                  {sortierung === "netto" ? "kostet die Stadt unterm Strich" : "gibt der Bereich aus"}
                </p>
                {d != null && (
                  <>
                    <div className="mt-2.5 h-1.5 overflow-hidden rounded-full bg-muted">
                      <div className="h-full rounded-full" style={{ width: `${Math.min(d, 100)}%`, background: "var(--hh-ein-0)" }} />
                    </div>
                    <p className="mt-1.5 text-[11px] text-muted-foreground">
                      {d}&nbsp;% der Kosten deckt der Bereich selbst · {deMio(mio(z.aufwendungen))} Ausgaben
                    </p>
                  </>
                )}
              </Link>
            );
          })}
        </div>
        {karten.length > 6 && (
          <button type="button" onClick={() => setAlleBereiche((v) => !v)}
            className="mt-2.5 text-xs font-semibold text-primary">
            {alleBereiche ? "Weniger anzeigen" : `Alle ${karten.length} Bereiche ansehen`}
          </button>
        )}
      </div>

      {/* Kuratierter Erklärtext, wo vorhanden — Lotti-ruhig, keine Bewertung. */}
      {BEREICH_INFO[karten[0]?.z.bereich] && (
        <p className="max-w-[86ch] text-xs leading-relaxed text-muted-foreground">
          Übrigens: {BEREICH_INFO[karten[0].z.bereich]}
        </p>
      )}
    </div>
  );
}
