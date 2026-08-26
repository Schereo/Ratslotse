"use client";

// „Was in den Listen stand" — die Inhalts-Ebene des Streit-Abschnitts.
//
// Bis zum 26.08.2026 endete der Streit-Abschnitt ehrlich bei „wer wollte
// ändern und kam damit durch" — der Inhalt der Listen lag als PDF ohne
// Volltext im RIS. Seit `council/aenderungslisten.py` die EHH-Listen liest
// (Position für Position, gegen die eigene Schlusssumme bewiesen), steht er
// hier: je Dokument die Positionen des Haushaltsjahrgangs, dazu die Summen
// der FRAKTIONSLISTEN aus den Beschluss-Dateien des Finanzausschusses.
//
// DIE GRENZE BLEIBT SICHTBAR: Die Fraktionslisten selbst sind Tischvorlagen
// und liegen in keinem Ratsinformationssystem-Dokument — was von ihnen
// digital existiert, ist ihre Summenzeile in der Beschluss-Datei, mit dem
// Urheber daneben. Genau so steht es an der Karte; mehr wird nicht behauptet.
//
// AUSGEWOGENHEIT wie im ganzen Abschnitt: Reihenfolge ist das Verfahren
// (Verw. I → II → III → Beschluss), Parteifarben bleiben 8-px-Punkte,
// kombinierte Urheber („SPD/ CDU/ FDP") bekommen den neutralen Punkt —
// dieselbe Regel wie `<Fraktion>` in abschnitt-streit.tsx.

import { ChevronDown } from "lucide-react";
import {
  AenderungslistenDaten, ListeImJahr, deltaBetrag, listenFuerJahr,
  politikZeilen,
} from "@/lib/haushalt-aenderungslisten";
import { Beleg, Dokumentbeleg } from "@/components/haushalt/quelle";
import { BetragZelle, TextZelle, ZahlenTabelle } from "@/components/haushalt/zahlen-tabelle";
import { parteiDot } from "@/components/qa-bausteine";
import { cn } from "@/lib/utils";

const NEUTRAL = { bg: "hsl(209 18% 65%)", ring: false };

function UrheberMarke({ label }: { label: string }) {
  const dot = label.includes("/") ? NEUTRAL : parteiDot(label);
  return (
    <span className="inline-flex items-center gap-1.5 text-[12.5px] font-semibold text-foreground">
      <span aria-hidden className="h-2 w-2 flex-none rounded-full"
        style={{
          background: dot.bg,
          boxShadow: dot.ring ? "inset 0 0 0 1px rgba(0,0,0,.15)" : undefined,
        }} />
      {label}
    </span>
  );
}

/** Drei Beträge einer Summenzeile — dieselbe Reihenfolge wie im Dokument. */
function SummenWerte({ e, a, s }: { e: number; a: number; s: number }) {
  return (
    <span className="font-mono text-[11.5px] tabular-nums text-muted-foreground">
      <span className="whitespace-nowrap">Erträge {deltaBetrag(e)}</span>
      {" · "}
      <span className="whitespace-nowrap">Aufwand {deltaBetrag(a)}</span>
      {" · "}
      <span className={cn("whitespace-nowrap font-medium",
        s < 0 ? "text-signal" : "text-foreground")}>
        Saldo {deltaBetrag(s)}
      </span>
    </span>
  );
}

function ListenKarte({ liste, jahr }: { liste: ListeImJahr; jahr: number }) {
  return (
    <details className="group border-t border-border/60 py-2.5 first:border-t-0 first:pt-0">
      <summary className="flex cursor-pointer list-none flex-wrap items-baseline gap-x-3 gap-y-1">
        <ChevronDown className="h-3.5 w-3.5 translate-y-0.5 text-muted-foreground transition-transform group-open:rotate-180" />
        <span className="text-[13px] font-semibold text-foreground">{liste.name}</span>
        <span className="font-mono text-[11px] tabular-nums text-muted-foreground">
          {liste.zeilen.length} Position{liste.zeilen.length === 1 ? "" : "en"} für {jahr}
        </span>
        {liste.saldo && (
          <span className={cn("ml-auto whitespace-nowrap font-mono text-[11.5px] font-medium tabular-nums",
            liste.saldo.saldo < 0 ? "text-signal" : "text-foreground")}>
            Saldo {deltaBetrag(liste.saldo.saldo)}
          </span>
        )}
      </summary>

      <div className="mt-2 pl-[26px]">
        {/* Echte <table> statt Grid je Zeile (zahlen-tabelle.tsx): EIN
            Spaltenraster, Spaltenlinien, klebender Kopf — und die Summe der
            Liste als Fußzeile, die die Spalten unten noch einmal ankert. */}
        <ZahlenTabelle
          className="mt-2"
          spalten={[
            { titel: "Position" },
            { titel: "Ertrag", zahl: true },
            { titel: "Aufwand", zahl: true },
          ]}
          fuss={liste.saldo && (
            <tr>
              <TextZelle className="border-t-border/60 py-2">
                <span className="text-[11.5px] font-semibold text-foreground">Summe der Liste</span>
                <span className={cn("ml-2 whitespace-nowrap font-mono text-[11px] font-medium tabular-nums",
                  liste.saldo.saldo < 0 ? "text-signal" : "text-muted-foreground")}>
                  Saldo {deltaBetrag(liste.saldo.saldo)}
                </span>
                <Beleg q="aenderungsliste" h={liste.herkunft} />
              </TextZelle>
              <BetragZelle euro={liste.saldo.ertraege} text={deltaBetrag(liste.saldo.ertraege)}
                className="border-t-border/60 py-2 font-medium" />
              <BetragZelle euro={liste.saldo.aufwendungen} text={deltaBetrag(liste.saldo.aufwendungen)}
                className="border-t-border/60 py-2 font-medium" />
            </tr>
          )}
        >
          {liste.zeilen.map((z) => (
            <tr key={z.lfd}>
              <TextZelle>
                {z.bezeichnung ? (
                  <span className="text-foreground/90">{z.bezeichnung}</span>
                ) : (
                  // Rund 1 % der Zeilen: Die Bezeichnung wickelt im PDF so
                  // uneindeutig, dass die Nachlese sie liegen lässt — lieber
                  // eine benannte Lücke als ein Name von der falschen Zeile.
                  <span className="italic text-muted-foreground">Position {z.lfd} (ohne lesbaren Namen)</span>
                )}
                <span className="ml-2 font-mono text-[10px] text-muted-foreground">
                  {z.thh != null ? `THH ${String(z.thh).padStart(2, "0")}` : "alle THH"}
                </span>
                {z.erlaeuterung && (
                  <span className="mt-0.5 block max-w-[75ch] text-[11px] leading-relaxed text-muted-foreground">
                    {z.erlaeuterung}
                  </span>
                )}
              </TextZelle>
              <BetragZelle euro={z.ertrag} text={deltaBetrag(z.ertrag)} />
              <BetragZelle euro={z.aufwand} text={deltaBetrag(z.aufwand)} />
            </tr>
          ))}
        </ZahlenTabelle>
        <div className="mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-1">
          {liste.bisPlanjahr && (
            <p className="text-[11px] leading-relaxed text-muted-foreground">
              Ändert auch die Finanzplanung bis {liste.bisPlanjahr} — die Beträge dafür
              stehen im Dokument je Planjahr einzeln.
            </p>
          )}
          <Dokumentbeleg h={liste.herkunft} />
        </div>
      </div>
    </details>
  );
}

export function StreitListenInhalt({ daten, jahr }: {
  daten: AenderungslistenDaten | null;
  jahr: number | null;
}) {
  const listen = listenFuerJahr(daten, jahr);
  const politik = politikZeilen(daten, jahr);
  if (!jahr || (!listen.length && !politik.length)) return null;

  return (
    <div className="rounded-2xl border border-border bg-card p-4 shadow-sm">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <h2 className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
          Was in den Listen stand
        </h2>
        <span className="font-mono text-[10px] tabular-nums text-muted-foreground">
          Haushalt {jahr}
        </span>
      </div>
      <p className="mt-1 max-w-[70ch] text-[12.5px] leading-relaxed text-muted-foreground">
        Die Änderungslisten der Verwaltung und die im Finanzausschuss beschlossenen
        Änderungen liegen als Dokumente vor — hier stehen ihre Positionen, Zeile für
        Zeile, samt der Erläuterung aus dem Dokument, was hinter jeder Änderung
        steckt. Jede Liste ging beim Einlesen gegen ihre eigene Schlusssumme auf;
        was nicht aufgeht, würde hier nicht stehen.
      </p>

      {politik.length > 0 && (
        <div className="mt-3 rounded-xl bg-muted/40 p-3">
          <p className="font-mono text-[9.5px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
            Die Fraktionslisten — nur die Summe ist belegt
          </p>
          <div className="mt-1.5 flex flex-col gap-1.5">
            {politik.map((s) => (
              <p key={s.label} className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5">
                <UrheberMarke label={s.label} />
                <SummenWerte e={s.ertraege} a={s.aufwendungen} s={s.saldo} />
                <Beleg q="aenderungsliste" h={daten ? daten.herkunft[String(s.herkunft_id)] ?? null : null} />
              </p>
            ))}
          </div>
          <p className="mt-2 max-w-[68ch] text-[11px] leading-relaxed text-muted-foreground">
            Die Listen der Fraktionen selbst wurden als Tischvorlagen verteilt und liegen
            nicht im Ratsinformationssystem — digital belegt ist ihre Summenzeile in der
            Beschluss-Datei des Finanzausschusses, mit dem Urheber daneben. Minus beim
            Saldo heißt: Das geplante Jahresergebnis sinkt dadurch.
          </p>
        </div>
      )}

      {listen.length > 0 && (
        <div className="mt-3">
          {listen.map((l) => <ListenKarte key={l.schluessel} liste={l} jahr={jahr} />)}
        </div>
      )}
    </div>
  );
}
