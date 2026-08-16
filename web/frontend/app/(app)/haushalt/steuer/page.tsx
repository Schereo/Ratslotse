"use client";

// /haushalt/steuer?art=… — Steuer-Steckbrief (Design H-10/H-11/H-12).
//
// Ein Template für zwei Extreme: eine Steuer, deren Hebesatz der Rat setzt
// (Gewerbesteuer), und eine Einnahme, bei der er gar nichts entscheidet
// (Schlüsselzuweisungen, Einkommensteueranteil). Die dritte Stufe bleibt
// deshalb immer stehen — bei „Nichts." nur gestrichelt und ohne Signal.
//
// Reihenfolge nach H-10: erst „Wer entscheidet was" (die Frage, mit der Leute
// kommen), dann die Ist-Kurve, dann Hebesatz-Historie und Überschlag.

import { Suspense, useMemo } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { ChevronRight, Search } from "lucide-react";
import { useFetch } from "@/lib/use-fetch";
import { HaushaltDaten, deMio } from "@/lib/haushalt";
import type { QuellenSchluessel } from "@/lib/haushalt-quellen";
import { STEUERARTEN, SPIELRAUM_LABEL, steuerartNachSlug } from "@/lib/haushalt-steuern";
import { Beleg, Quellenkontext, Quellenverzeichnis } from "@/components/haushalt/quelle";
import { LottiErklaert, LottiVergleich } from "@/components/haushalt/lotti-erklaert";
import { IstKurve } from "@/components/haushalt/ist-kurve";
import { GlossaryText } from "@/components/glossary-text";
import { cn } from "@/lib/utils";

function SteuerInner() {
  const slug = useSearchParams().get("art") ?? "gewerbesteuer";
  const { data, loading } = useFetch<HaushaltDaten>("/council/haushalt");
  const art = steuerartNachSlug(slug);

  const reihe = useMemo(() => {
    if (!data || !art?.datenArt) return [];
    return data.steuern
      .filter((s) => s.art === art.datenArt && s.betrag != null && s.betrag > 0)
      .map((s) => ({ jahr: s.jahr, betrag: s.betrag as number }))
      .sort((a, b) => a.jahr - b.jahr);
  }, [data, art]);

  if (!art) {
    return (
      <div className="py-16 text-center text-sm text-muted-foreground">
        Diese Einnahmeart kennen wir nicht.{" "}
        <Link href="/haushalt/einnahmen" className="font-semibold text-primary">Zur Übersicht</Link>
      </div>
    );
  }
  if (loading || !data) {
    return <div className="py-16 text-center text-sm text-muted-foreground">Steckbrief wird geladen …</div>;
  }

  // Schlüsselzuweisungen kommen aus der Steuerkraft-Tabelle, nicht aus den Steuern.
  const zuw = data.steuerkraft.filter((k) => k.zuweisungen != null);
  const istZuweisung = art.slug === "schluesselzuweisungen";
  const zuwReihe = istZuweisung
    ? zuw.map((k) => ({ jahr: k.jahr, betrag: k.zuweisungen as number }))
    : [];
  const anzeigeReihe = istZuweisung ? zuwReihe : reihe;
  const letzte = anzeigeReihe.at(-1);
  const gesamt = data.steuern.find((s) => s.jahr === letzte?.jahr && s.art === "insgesamt")?.betrag ?? null;
  const anteil = letzte && gesamt && !istZuweisung ? Math.round((letzte.betrag / gesamt) * 100) : null;
  const einwohner = data.einwohner?.einwohner ?? 0;

  // Ein Hebesatzpunkt, überschlagen aus dem Ist — bewusst als Überschlag
  // benannt. Nur wo Betrag und Hebesatz dieselbe Steuer meinen: Bei der
  // Grundsteuer tun sie das nicht (siehe `punktUnmoeglich`).
  const proPunkt = art.hebesatz && letzte && !art.punktUnmoeglich
    ? letzte.betrag / art.hebesatz : null;

  // Die Quellen dieser Seite in Lese-Reihenfolge — daraus zählt der Provider
  // die Fußnoten-Nummern.
  const quellen: QuellenSchluessel[] = istZuweisung
    ? ["steuerkraft", "plan"]
    : ["steuern", "hebesaetze"];

  return (
    <Quellenkontext schluessel={quellen}>
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-1.5 text-[11.5px] text-muted-foreground">
        <Link href="/haushalt" className="hover:text-foreground">Haushalt</Link>
        <ChevronRight className="h-3 w-3" />
        <Link href="/haushalt/einnahmen" className="hover:text-foreground">Woher das Geld kommt</Link>
        <ChevronRight className="h-3 w-3" />
        <span className="font-semibold text-foreground">{art.titel}</span>
      </div>

      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <h1 className="font-display text-2xl font-bold tracking-tight sm:text-[26px]">{art.titel}</h1>
          <p className="mt-2 max-w-[62ch] text-[15px] leading-relaxed text-foreground/90">
            <GlossaryText text={art.kurz} />
          </p>
        </div>
        {letzte && (
          <div className="w-full flex-none rounded-2xl border border-border bg-card p-4 shadow-sm sm:w-[210px]">
            <p className="font-mono text-[9.5px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
              {istZuweisung ? `Erhalten ${letzte.jahr}` : `Eingenommen ${letzte.jahr}`}
            </p>
            <p className="mt-1.5 font-display text-[27px] font-bold leading-none tracking-tight tabular-nums text-[color:var(--hh-ein-0)]">
              {deMio(letzte.betrag / 1e6)}
              <span className="text-sm font-semibold text-muted-foreground">&#8239;Mio.</span>
              <Beleg q={istZuweisung ? "steuerkraft" : "steuern"} />
            </p>
            {anteil != null && (
              <p className="mt-1.5 text-[11.5px] leading-relaxed text-muted-foreground">
                {anteil}&nbsp;% aller Steuereinnahmen ({deMio(gesamt! / 1e6)}&#8239;Mio.)
              </p>
            )}
          </div>
        )}
      </div>

      {/* Wer entscheidet was — das didaktische Herzstück (H-10). */}
      <div className="rounded-2xl border border-primary/20 bg-card p-4 shadow-sm">
        <div className="flex items-baseline justify-between gap-3">
          <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-primary">
            Wer entscheidet was
          </p>
          <span className="font-mono text-[10px] uppercase text-muted-foreground">
            Spielraum: {SPIELRAUM_LABEL[art.spielraum]}
          </span>
        </div>
        <div className="mt-3 grid gap-2 sm:grid-cols-3">
          {art.stufen.map((st) => (
            <div key={st.titel} className={cn(
              "rounded-xl border p-3",
              st.rat ? "border-signal/55 bg-signal/[0.06]" : "border-border bg-muted/30",
              !st.rat && st.wer.startsWith("Rat") && "border-dashed",
            )}>
              <span className={cn(
                "inline-flex rounded-full px-2 py-0.5 font-mono text-[9px] font-bold uppercase tracking-wide",
                st.rat ? "bg-signal text-signal-foreground" : "bg-muted text-muted-foreground",
              )}>
                {st.wer}
              </span>
              <p className="mt-2 text-[13px] font-bold leading-snug">{st.titel}</p>
              <p className="mt-1 text-xs leading-relaxed text-foreground/80">
                <GlossaryText text={st.text} />
              </p>
            </div>
          ))}
        </div>
        {art.beispiel && (
          <div className="mt-3 border-t border-border/60 pt-3">
            <p className="text-xs text-foreground/80">Beispiel:</p>
            <p className="mt-1.5 inline-block rounded-lg border border-border bg-muted/40 px-2.5 py-1.5 font-mono text-[12.5px]">
              {art.beispiel.rechnung}
            </p>
            <p className="mt-1.5 text-[11.5px] leading-relaxed text-muted-foreground">{art.beispiel.hinweis}</p>
          </div>
        )}
      </div>

      <LottiErklaert titel={art.lotti.titel} text={art.lotti.text} />

      {anzeigeReihe.length >= 2 && (
        <div className="rounded-2xl border border-border bg-card p-4 shadow-sm">
          <IstKurve reihe={anzeigeReihe} />
          <p className="mt-2.5 border-t border-dashed border-border pt-2.5 text-[11px] text-muted-foreground">
            Quelle {istZuweisung ? "Schlüsselzuweisungen" : "Steuereinnahmen"}: siehe Verzeichnis unten
            <Beleg q={istZuweisung ? "steuerkraft" : "steuern"} />
          </p>
        </div>
      )}

      {letzte && einwohner > 0 && (
        <LottiVergleich
          betragMio={letzte.betrag / 1e6}
          einwohner={einwohner}
          was={istZuweisung ? "vom Land" : `aus der ${art.titel}`}
        />
      )}

      {/* Hebesatz + Überschlag, nur wo der Rat wirklich eine Stellschraube hat. */}
      {art.hebesatz && (
        <div className="grid gap-3 lg:grid-cols-[1fr_310px]">
          <div className="rounded-2xl border border-border bg-card p-4 shadow-sm">
            <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
              Der Hebesatz im Rat
            </p>
            <div className="mt-3 space-y-3">
              <div className="rounded-xl bg-muted/40 p-3">
                <p className="font-mono text-[10px] uppercase tracking-wide text-muted-foreground">Bis 2025 · Rat</p>
                <p className="mt-1 text-[13px] font-semibold">
                  Hebesatz {art.hebesatz}&nbsp;%
                  <span className="font-normal text-muted-foreground"> — beschlossen mit der Haushaltssatzung</span>
                  <Beleg q="hebesaetze" />
                </p>
              </div>
              {art.slug === "gewerbesteuer" && (
                <div className="rounded-xl bg-primary/[0.06] p-3">
                  <div className="flex items-center justify-between gap-2">
                    <p className="font-mono text-[10px] uppercase tracking-wide text-primary">Haushalt 2026 · Rat</p>
                    <span className="rounded-full border border-[#fecaca] bg-[#fef2f2] px-2 py-0.5 text-[10.5px] font-semibold text-[#b91c1c]">
                      Abgelehnt
                    </span>
                  </div>
                  <p className="mt-1.5 text-[13px] font-semibold leading-snug">
                    Die Verwaltung schlug vor, die Hebesätze zu erhöhen. Der Rat lehnte ab.
                  </p>
                  <p className="mt-1.5 text-[11.5px] text-muted-foreground">
                    Genau hier entscheidet Kommunalpolitik über Einnahmen.
                  </p>
                </div>
              )}
            </div>
            {/* „aus zwei Stationen wird eine Treppe" stimmte nur bei der
                Gewerbesteuer: Nur sie trägt hier zwei Kästen, alle anderen
                Steckbriefe einen einzigen. */}
            <p className="mt-3 rounded-lg border border-dashed border-border p-2.5 text-[11.5px] leading-relaxed text-muted-foreground">
              Die Hebesätze früherer Jahre liegen uns noch nicht als Reihe vor — sobald wir sie
              haben, wird daraus eine Treppe über die Jahre. Wir schätzen sie nicht.
            </p>
          </div>

          {art.punktUnmoeglich && (
            <div className="rounded-2xl border border-dashed border-border bg-card p-4">
              <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
                Was brächte ein Punkt mehr?
              </p>
              {/* Kein Link ins Labor: Dort fehlt derselbe Regler aus demselben
                  Grund — ein Verweis verspräche, was die nächste Seite auch
                  nicht kann. */}
              <p className="mt-2 text-[12.5px] leading-relaxed text-foreground/80">
                {art.punktUnmoeglich}
              </p>
            </div>
          )}

          {proPunkt != null && (
            <div className="rounded-2xl border border-signal/40 bg-card p-4 shadow-sm">
              <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-signal">
                Was brächte ein Punkt mehr?
              </p>
              <p className="mt-2 font-display text-2xl font-bold tracking-tight tabular-nums">
                ≈ {deMio(proPunkt / 1e6)}
                <span className="text-sm font-semibold text-muted-foreground">&#8239;Mio.&nbsp;€</span>
              </p>
              <p className="mt-1.5 text-[12.5px] leading-relaxed text-foreground/80">
                Überschlagen: {deMio(letzte!.betrag / 1e6)}&#8239;Mio. bei {art.hebesatz} Punkten,
                geteilt durch {art.hebesatz}. <strong>Brutto</strong> — was davon in der Stadtkasse
                bleibt, ist weniger.
              </p>
              {/* „und Grundstückswerte" stand hier, solange die Karte auch bei
                  der Grundsteuer erschien — dort tut sie es nicht mehr. */}
              <p className="mt-2 text-[11px] leading-relaxed text-muted-foreground">
                Unsere Rechnung, keine amtliche Kennzahl: Sie unterstellt, dass die Gewinne der
                Unternehmen gleich bleiben — steigt der Hebesatz, kann sich auch daran etwas
                ändern.
              </p>
              <Link href="/haushalt/einnahmen"
                className="mt-2.5 inline-flex text-[12px] font-semibold text-primary">
                Alle Einnahmequellen ansehen →
              </Link>
            </div>
          )}
        </div>
      )}

      <div className="rounded-2xl border border-dashed border-border bg-card p-4">
        <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
          Dazu hat der Rat entschieden
        </p>
        <p className="mt-2 max-w-[70ch] text-[12.5px] leading-relaxed text-foreground/80">
          Die automatische Verknüpfung von Beschlüssen mit Einnahmearten bauen wir noch.
          Bis dahin findet die Suche, was der Rat dazu entschieden hat.
        </p>
        <Link href={`/council?q=${encodeURIComponent(art.titel)}`}
          className="mt-2.5 inline-flex items-center gap-1.5 text-xs font-semibold text-primary">
          <Search className="h-3.5 w-3.5" /> Beschlüsse zu „{art.titel}“ suchen
        </Link>
      </div>

      <div className="flex flex-wrap gap-2">
        {STEUERARTEN.filter((a) => a.slug !== art.slug).map((a) => (
          <Link key={a.slug} href={`/haushalt/steuer?art=${a.slug}`}
            className="rounded-full border border-border bg-card px-3 py-1.5 text-[11.5px] hover:border-primary/40">
            {a.titel}
          </Link>
        ))}
      </div>

      <Quellenverzeichnis schluessel={quellen} />
    </div>
    </Quellenkontext>
  );
}

export default function SteuerPage() {
  return (
    <Suspense fallback={<div className="py-16 text-center text-sm text-muted-foreground">Steckbrief wird geladen …</div>}>
      <SteuerInner />
    </Suspense>
  );
}
