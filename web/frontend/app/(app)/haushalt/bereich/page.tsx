"use client";

// Teilhaushalt-Dossier (Design H-08, Empfehlung; die Vergleichstabelle aus
// H-09 als eigener Block). Dramaturgie wie die Beschluss-Seiten: eine These,
// dann Karte für Karte der Beleg — Brutto/Netto, Kostendeckung, Brutto-gegen-
// Netto-Umschalter (das Lehrstück), Was-steckt-drin, Entwicklung, Beschlüsse.
//
// Query-Param statt dynamischem Segment (/haushalt/bereich?name=…): Der
// Capacitor-Export (output: export) kennt die Bereichs-Slugs zur Bauzeit
// nicht — dieselbe Konvention wie die Beschluss-Seite (/council/decision?id=).

import { Suspense, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { ChevronRight, Search } from "lucide-react";
import { Segmented } from "@/components/ui";
import { useFetch } from "@/lib/use-fetch";
import {
  BEREICH_INFO, HaushaltDaten, HaushaltZeile, bereichSlug, bereiche,
  bereichsReihe, deMio, deckung, jahreSortiert, mio, quellenLabel,
} from "@/lib/haushalt";
import { Hantel } from "@/components/haushalt/hantel";
import { cn } from "@/lib/utils";

function BruttoNettoBlock({ z }: { z: HaushaltZeile }) {
  const aus = mio(z.aufwendungen) ?? 0;
  const ein = mio(z.ertraege) ?? 0;
  const netto = Math.round((ein - aus) * 10) / 10;
  const d = deckung(z);
  return (
    <div className="rounded-2xl border border-border bg-card p-4 shadow-sm">
      <p className="mb-3 font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
        Was rausgeht, was reinkommt
      </p>
      {[
        { label: "Ausgaben", breite: 100, farbe: "var(--hh-aus-0)", wert: deMio(aus), cls: "" },
        { label: "eigene Einnahmen", breite: aus > 0 ? (ein / aus) * 100 : 0, farbe: "var(--hh-ein-0)", wert: deMio(ein), cls: "text-[color:var(--hh-ein-0)]" },
      ].map((r) => (
        <div key={r.label} className="mb-2 flex items-center gap-2.5">
          <span className="w-24 flex-none text-xs text-foreground/80 sm:w-28">{r.label}</span>
          <div className="h-6 flex-1 overflow-hidden rounded bg-muted">
            <div className="h-full" style={{ width: `${Math.min(r.breite, 100)}%`, background: r.farbe }} />
          </div>
          <span className={cn("w-16 flex-none text-right font-display text-base font-bold tabular-nums", r.cls)}>{r.wert}</span>
        </div>
      ))}
      <div className="flex items-center gap-2.5">
        <span className="w-24 flex-none text-xs font-semibold sm:w-28">
          {netto < 0 ? "bleibt der Stadt" : "bleibt übrig"}
        </span>
        <div className="hh-schraffur flex h-6 flex-1 items-center rounded border border-signal/50 pl-2.5">
          <span className="text-[11px] font-semibold text-signal">
            {netto < 0 ? "aus allgemeinen Steuermitteln bezahlt" : "Überschuss des Bereichs"}
          </span>
        </div>
        <span className="w-16 flex-none text-right font-display text-base font-bold tabular-nums text-signal">{deMio(netto)}</span>
      </div>
      {d != null && (
        <div className="mt-3.5 flex items-center gap-4 border-t border-border/60 pt-3">
          <div className="flex h-14 w-14 flex-none items-center justify-center rounded-full"
            style={{ background: `conic-gradient(var(--hh-ein-0) 0 ${d}%, hsl(var(--muted)) ${d}% 100%)` }}>
            <span className="flex h-9 w-9 items-center justify-center rounded-full bg-card font-display text-[13px] font-bold">
              {d}<span className="text-[9px]">%</span>
            </span>
          </div>
          <p className="text-[12.5px] leading-relaxed text-foreground/90">
            <strong>Kostendeckungsgrad {d}&nbsp;%.</strong> Von 100 Euro Ausgaben holt der Bereich {d} Euro
            selbst herein — der Rest kommt aus Steuern und Zuweisungen, die zentral eingehen.
          </p>
        </div>
      )}
    </div>
  );
}

function BereichInner() {
  const slug = useSearchParams().get("name") ?? "";
  const { data, loading } = useFetch<HaushaltDaten>("/council/haushalt");
  const [ranking, setRanking] = useState<"netto" | "brutto">("netto");

  const jahre = useMemo(() => (data ? jahreSortiert(data) : []), [data]);
  const jahr = jahre[jahre.length - 1];
  const zeilen = data && jahr ? data.jahre[String(jahr)] ?? [] : [];
  const z = bereiche(zeilen).find((r) => bereichSlug(r.bereich) === slug);

  if (loading || !data) {
    return <div className="py-16 text-center text-sm text-muted-foreground">Haushalt wird geladen …</div>;
  }
  if (!z || !jahr) {
    return (
      <div className="py-16 text-center text-sm text-muted-foreground">
        Diesen Bereich kennen wir nicht. <Link href="/haushalt" className="font-semibold text-primary">Zur Übersicht</Link>
      </div>
    );
  }

  const netto = -(mio(z.ergebnis) ?? 0);
  const alle = bereiche(zeilen)
    .map((r) => ({ r, netto: -(mio(r.ergebnis) ?? 0), brutto: mio(r.aufwendungen) ?? 0, d: deckung(r) }))
    .sort((a, b) => (ranking === "netto" ? b.netto - a.netto : b.brutto - a.brutto));
  const rangNetto = [...alle].sort((a, b) => b.netto - a.netto).findIndex((x) => x.r.bereich === z.bereich) + 1;
  const bruttoTop = [...alle].sort((a, b) => b.brutto - a.brutto)[0];
  const reihe = bereichsReihe(data, z.bereich);
  const quelle = quellenLabel(zeilen, jahr);
  const info = BEREICH_INFO[z.bereich];
  const maxWert = Math.max(...alle.map((x) => (ranking === "netto" ? x.netto : x.brutto)), 1);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-1.5 text-[11.5px] text-muted-foreground">
        <Link href="/haushalt" className="hover:text-foreground">Haushalt {jahr}</Link>
        <ChevronRight className="h-3 w-3" />
        <span className="font-semibold text-foreground">{z.bereich}</span>
      </div>

      <div>
        <h1 className="font-display text-2xl font-bold tracking-tight sm:text-[25px]">{z.bereich}</h1>
        <p className="mt-2 max-w-[64ch] text-[15px] leading-relaxed text-foreground/90">
          {netto > 0 ? (
            rangNetto === 1 ? (
              <>Kein Bereich kostet die Stadt unterm Strich so viel wie dieser: <strong>{deMio(netto)}&#8239;Mio.&nbsp;€</strong> im
                Jahr {jahr}{bruttoTop.r.bereich !== z.bereich && <> — mehr als „{bruttoTop.r.bereich}", obwohl der brutto deutlich mehr ausgibt</>}.</>
            ) : (
              <>Unterm Strich kostet dieser Bereich die Stadt <strong>{deMio(netto)}&#8239;Mio.&nbsp;€</strong> im
                Jahr {jahr} — Platz {rangNetto} von {alle.length} nach Zuschussbedarf.</>
            )
          ) : (
            <>Dieser Bereich trägt sich {jahr} selbst — er nimmt <strong>{deMio(-netto)}&#8239;Mio.&nbsp;€</strong> mehr
              ein, als er ausgibt.</>
          )}
        </p>
      </div>

      <BruttoNettoBlock z={z} />

      {/* Brutto gegen Netto — der Umschalter IST das Lehrstück (H-08). */}
      <div className="rounded-2xl border border-border bg-card p-4 shadow-sm">
        <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
          Brutto gegen Netto · alle Bereiche
        </p>
        <p className="mb-3 mt-1 text-[12.5px] text-foreground/80">Umschalten dreht die Reihenfolge — und genau darin steckt der Punkt.</p>
        {/* Scrollzeile: „Kosten für die Stadt (netto)" ragte auf 375 px über
            den Bildschirmrand und ließ die ganze Seite horizontal wackeln. */}
        <div className="scrollbar-none -mx-1 mb-3 overflow-x-auto px-1">
          <Segmented value={ranking} onChange={setRanking} tone="primary" className="w-max" options={[
            { value: "brutto", label: "Ausgaben (brutto)" },
            { value: "netto", label: "Kosten für die Stadt (netto)" },
          ]} />
        </div>
        <div className="grid grid-cols-[minmax(110px,150px)_1fr_60px] items-center gap-x-2.5 gap-y-1.5 text-xs">
          {alle.slice(0, 6).map(({ r, netto: n, brutto: b }, i) => {
            const wert = ranking === "netto" ? n : b;
            const ich = r.bereich === z.bereich;
            return (
              <div key={r.bereich} className="contents">
                <span className={cn("truncate", ich && "font-bold")}>{r.bereich}</span>
                <div className="h-3.5 rounded-[3px] bg-muted">
                  <div className="h-full rounded-[3px]" style={{
                    width: `${Math.max((wert / maxWert) * 100, 2)}%`,
                    background: `var(--hh-ein-${Math.min(i, 6)})`,
                  }} />
                </div>
                <span className={cn("text-right tabular-nums", ich && "font-bold")}>{deMio(wert)}</span>
              </div>
            );
          })}
        </div>
        {bruttoTop.r.bereich !== [...alle].sort((a, b) => b.netto - a.netto)[0].r.bereich && (
          <p className="mt-3 rounded-lg bg-muted/60 p-2.5 text-xs leading-relaxed text-foreground/90">
            In der Brutto-Sicht steht {bruttoTop.r.bereich} mit {deMio(bruttoTop.brutto)}&#8239;Mio. an erster Stelle.
            Weil dort aber {deMio(mio(bruttoTop.r.ertraege))}&#8239;Mio. an Erstattungen und eigenen Einnahmen
            zurückfließen, bleibt {[...alle].sort((a, b) => b.netto - a.netto)[0].r.bereich} unterm Strich am teuersten.
          </p>
        )}
      </div>

      {info && (
        <div className="rounded-2xl border border-border bg-card p-4 shadow-sm">
          <p className="mb-2 font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">Was steckt drin</p>
          <p className="text-[13.5px] leading-relaxed text-foreground/90">{info}</p>
          <p className="mt-2.5 text-[11.5px] leading-relaxed text-muted-foreground">
            Redaktionelle Beschreibung nach dem Vorbericht des Haushaltsplans — keine amtliche Gliederung.
            Die Produktebene mit Einzelbeträgen lesen wir erst ein.
          </p>
        </div>
      )}

      {/* Geplant und geworden: nur wo für diesen Bereich ein Jahresabschluss
          ausgelesen ist. Der Name im Abschluss weicht leicht ab („Personal- u.
          Verwaltungsmanagement"), deshalb Vergleich über die ersten Wörter. */}
      {(() => {
        const norm = (t: string) => t.toLowerCase().replace(/[^a-zäöüß]+/g, " ").trim().split(" ")[0];
        const treffer = (data.ergebnisrechnung ?? []).filter(
          (p) => p.thh_nr != null && p.thh_name && norm(p.thh_name) === norm(z.bereich)
                 && (p.nr === 12 || p.nr === 20));
        const jahre = [...new Set(treffer.map((p) => p.jahr))].sort();
        if (!jahre.length) return null;
        const zeilen = jahre.map((j) => {
          const a = treffer.find((p) => p.jahr === j && p.nr === 20);
          return { label: String(j), plan: mio(a?.ansatz), ist: mio(a?.ergebnis) };
        }).filter((r) => r.plan != null && r.ist != null);
        if (!zeilen.length) return null;
        return (
          <div className="rounded-2xl border border-border bg-card p-4 shadow-sm">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
                Geplant und geworden
              </p>
              <Link href="/haushalt/plan-ist" className="text-[11.5px] font-semibold text-primary">
                Alle Bereiche vergleichen →
              </Link>
            </div>
            <p className="mb-3 mt-1.5 max-w-[70ch] text-[12.5px] leading-relaxed text-foreground/85">
              Ausgaben dieses Bereichs: was der Rat beschlossen hatte und was der Jahresabschluss
              am Ende ausweist.
            </p>
            <Hantel zeilen={zeilen} />
          </div>
        );
      })()}

      {/* Entwicklung — echte Reihe, sobald der Bereichsname über Jahre stabil ist. */}
      <div className="rounded-2xl border border-border bg-card p-4 shadow-sm">
        <div className="flex items-baseline justify-between">
          <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">Entwicklung des Bereichs</p>
          <span className="font-mono text-[10px] uppercase text-muted-foreground">
            {reihe.length >= 2 ? `${reihe[0].jahr}–${reihe[reihe.length - 1].jahr} · ${reihe.length} Jahre` : "Noch keine Reihe"}
          </span>
        </div>
        {reihe.length >= 2 ? (
          <div className="mt-3 grid grid-cols-[auto_1fr_auto_auto] items-center gap-x-3 gap-y-1 text-xs tabular-nums">
            {reihe.map(({ jahr: j, zeile }) => {
              const n = -(mio(zeile.ergebnis) ?? 0);
              const maxN = Math.max(...reihe.map((r) => Math.abs(mio(r.zeile.ergebnis) ?? 0)), 1);
              return (
                <div key={j} className="contents">
                  <span className="font-mono text-muted-foreground">{j}</span>
                  <div className="h-2.5 rounded-[3px] bg-muted">
                    <div className="h-full rounded-[3px]" style={{ width: `${(Math.abs(n) / maxN) * 100}%`, background: "var(--hh-ein-0)" }} />
                  </div>
                  <span className="text-right">{n > 0 ? `−${deMio(n)}` : `+${deMio(-n)}`}&#8239;Mio. netto</span>
                  <span className="text-right text-muted-foreground">{deMio(mio(zeile.aufwendungen))} Ausgaben</span>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="mt-3 rounded-xl border-2 border-dashed border-border bg-muted/40 p-5 text-center">
            <p className="mx-auto max-w-[52ch] text-[12.5px] leading-relaxed text-foreground/80">
              Für frühere Jahre führte der Haushaltsplan diesen Bereich unter anderem Zuschnitt —
              wir zeigen keine Kurve, bevor wir sie belegen können. Die Gesamtsummen gibt es:{" "}
              <Link href="/haushalt" className="font-semibold text-primary">Zeitreihe in der Übersicht</Link>.
            </p>
          </div>
        )}
        {reihe.length >= 2 && reihe.length < jahre.length && (
          <p className="mt-2.5 text-[11px] text-muted-foreground">
            Vor {reihe[0].jahr} führte der Plan den Bereich unter anderem Zuschnitt — die Reihe beginnt dort, wo der Name belegt ist.
          </p>
        )}
      </div>

      {/* Beschlüsse: Verknüpfung [folgt] — bis dahin der ehrliche Weg über die Suche. */}
      <div className="rounded-2xl border border-dashed border-border bg-card p-4">
        <div className="flex items-baseline justify-between">
          <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">Dazu hat der Rat entschieden</p>
          <span className="font-mono text-[10px] uppercase text-muted-foreground">Verknüpfung [folgt]</span>
        </div>
        <p className="mt-2 max-w-[70ch] text-[12.5px] leading-relaxed text-foreground/80">
          Die automatische Verknüpfung von Beschlüssen mit Teilhaushalten bauen wir noch.
          Bis dahin findet die Suche alles, was der Rat zu diesem Bereich entschieden hat.
        </p>
        <Link href={`/council?q=${encodeURIComponent(z.bereich.split("/")[0].split(",")[0])}`}
          className="mt-2.5 inline-flex items-center gap-1.5 text-xs font-semibold text-primary">
          <Search className="h-3.5 w-3.5" /> Beschlüsse zu „{z.bereich.split("/")[0].split(",")[0]}" suchen
        </Link>
      </div>

      <p className="border-t border-dashed border-border pt-2.5 text-[11px] text-muted-foreground">
        Quelle: {quelle.url ? <a href={quelle.url} target="_blank" rel="noopener noreferrer" className="underline decoration-dotted">{quelle.text}</a> : quelle.text} ·
        Teilhaushalt {z.bereich} · Ergebnishaushalt, ordentliche Erträge und Aufwendungen.
      </p>
    </div>
  );
}

export default function BereichPage() {
  // useSearchParams braucht eine Suspense-Grenze (Export-Konvention).
  return (
    <Suspense fallback={<div className="py-16 text-center text-sm text-muted-foreground">Haushalt wird geladen …</div>}>
      <BereichInner />
    </Suspense>
  );
}
