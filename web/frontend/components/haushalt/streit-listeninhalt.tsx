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
// digital existiert, ist in aller Regel ihre Summenzeile in der
// Beschluss-Datei, mit dem Urheber daneben. Genau so steht es an der Karte;
// mehr wird nicht behauptet.
//
// EINE AUSNAHME, und sie ist der Grund für die Urheber-Marke an der Zeile:
// Die Beschluss-Datei zum Haushalt 2021 führt eine Spalte „Vorschlag von"
// je POSITION. Für diesen einen Jahrgang steht deshalb Zeile für Zeile da,
// was die Koalition ändern wollte — und der Kasten oben sagt das statt des
// „nur die Summe"-Satzes. Entschieden wird das an den Daten (`author` ist
// gefüllt), nicht an der Jahreszahl: Führt ein künftiges Dokument die Spalte
// wieder, stimmt der Text von selbst.
//
// AUSGEWOGENHEIT wie im ganzen Abschnitt: Reihenfolge ist das Verfahren
// (Verw. I → II → III → Beschluss), Parteifarben bleiben 8-px-Punkte,
// kombinierte Urheber („SPD/ CDU/ FDP") bekommen den neutralen Punkt —
// dieselbe Regel wie `<Fraktion>` in abschnitt-streit.tsx.

import { ChevronDown } from "lucide-react";
import {
  AenderungslistenDaten, ListeImJahr, deltaBetrag, listenFuerJahr,
  politikZeilen, positionenVon,
} from "@/lib/haushalt-aenderungslisten";
import { Beleg, Dokumentbeleg } from "@/components/haushalt/quelle";
import { BetragZelle, TextZelle, ZahlenTabelle } from "@/components/haushalt/zahlen-tabelle";
import { parteiDot } from "@/components/qa-bausteine";
import { cn } from "@/lib/utils";

const NEUTRAL = { bg: "hsl(209 18% 65%)", ring: false };

function UrheberMarke({ label, klein }: { label: string; klein?: boolean }) {
  const dot = label.includes("/") ? NEUTRAL : parteiDot(label);
  return (
    <span className={cn("inline-flex items-center gap-1.5 font-semibold",
      klein ? "text-[10px] text-muted-foreground" : "text-[12.5px] text-foreground")}>
      <span aria-hidden className={cn("flex-none rounded-full", klein ? "h-1.5 w-1.5" : "h-2 w-2")}
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

function ListenKarte({ liste, year }: { liste: ListeImJahr; year: number }) {
  // Der Urheber steht nur an der Zeile, wo er dort auch etwas unterscheidet:
  // Führt eine Liste durchgehend denselben, wiederholte die Marke nur den
  // Namen der Karte darüber. Genau eine Datei im Bestand führt mehrere
  // (der Beschluss 2021 mit Verw. I, Verw. II und der Koalitionsliste).
  const author = new Set(liste.zeilen.map((z) => z.author).filter(Boolean));
  const zeigeUrheber = author.size > 1;
  return (
    <details className="group border-t border-border/60 py-2.5 first:border-t-0 first:pt-0">
      <summary className="flex cursor-pointer list-none flex-wrap items-baseline gap-x-3 gap-y-1">
        <ChevronDown className="h-3.5 w-3.5 translate-y-0.5 text-muted-foreground transition-transform group-open:rotate-180" />
        <span className="text-[13px] font-semibold text-foreground">{liste.name}</span>
        <span className="font-mono text-[11px] tabular-nums text-muted-foreground">
          {liste.zeilen.length} Position{liste.zeilen.length === 1 ? "" : "en"} für {year}
          {zeigeUrheber && ` · von ${author.size} Vorschlagenden`}
        </span>
        {liste.balance && (
          <span className={cn("ml-auto whitespace-nowrap font-mono text-[11.5px] font-medium tabular-nums",
            liste.balance.balance < 0 ? "text-signal" : "text-foreground")}>
            Saldo {deltaBetrag(liste.balance.balance)}
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
          fuss={liste.balance && (
            <tr>
              <TextZelle className="border-t-border/60 py-2">
                <span className="text-[11.5px] font-semibold text-foreground">Summe der Liste</span>
                <span className={cn("ml-2 whitespace-nowrap font-mono text-[11px] font-medium tabular-nums",
                  liste.balance.balance < 0 ? "text-signal" : "text-muted-foreground")}>
                  Saldo {deltaBetrag(liste.balance.balance)}
                </span>
                <Beleg q="aenderungsliste" h={liste.herkunft} />
              </TextZelle>
              <BetragZelle euro={liste.balance.revenues} text={deltaBetrag(liste.balance.revenues)}
                label="Ertrag" className="border-t-border/60 py-2 font-medium" />
              <BetragZelle euro={liste.balance.expenses} text={deltaBetrag(liste.balance.expenses)}
                label="Aufwand" className="border-t-border/60 py-2 font-medium" />
            </tr>
          )}
        >
          {liste.zeilen.map((z) => (
            <tr key={z.seq}>
              <TextZelle>
                {z.label ? (
                  <span className="text-foreground/90">{z.label}</span>
                ) : (
                  // Rund 1 % der Zeilen: Die Bezeichnung wickelt im PDF so
                  // uneindeutig, dass die Nachlese sie liegen lässt — lieber
                  // eine benannte Lücke als ein Name von der falschen Zeile.
                  <span className="italic text-muted-foreground">Position {z.seq} (ohne lesbaren Namen)</span>
                )}
                <span className="ml-2 font-mono text-[10px] text-muted-foreground">
                  {z.sub_budget != null ? `THH ${String(z.sub_budget).padStart(2, "0")}` : "alle THH"}
                </span>
                {zeigeUrheber && z.author && (
                  <span className="ml-2 align-baseline">
                    <UrheberMarke label={z.author} klein />
                  </span>
                )}
                {z.explanation && (
                  <span className="mt-0.5 block max-w-[75ch] text-[11px] leading-relaxed text-muted-foreground">
                    {z.explanation}
                  </span>
                )}
              </TextZelle>
              <BetragZelle euro={z.revenue} text={deltaBetrag(z.revenue)} label="Ertrag" />
              <BetragZelle euro={z.expense} text={deltaBetrag(z.expense)} label="Aufwand" />
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

export function StreitListenInhalt({ daten, year }: {
  daten: AenderungslistenDaten | null;
  year: number | null;
}) {
  const listen = listenFuerJahr(daten, year);
  const politik = politikZeilen(daten, year);
  // Gilt der Satz „nur die Summe ist belegt" für diesen Jahrgang noch? Für
  // 2021 nicht: Dessen Beschluss-Datei nennt zu jeder Position, wer sie
  // vorschlug. Die Frage wird an den Daten entschieden, nicht am Jahr —
  // taucht die Spalte in einem künftigen Dokument wieder auf, stimmt der
  // Text von selbst.
  const mitPositionen = politik.some((s) => positionenVon(daten, s).length > 0);
  if (!year || (!listen.length && !politik.length)) return null;

  return (
    <div className="rounded-2xl border border-border bg-card p-4 shadow-sm">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <h2 className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
          Was in den Listen stand
        </h2>
        <span className="font-mono text-[10px] tabular-nums text-muted-foreground">
          Haushalt {year}
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
            {mitPositionen
              ? "Die Fraktionslisten — dieser Jahrgang nennt jede Position"
              : "Die Fraktionslisten — nur die Summe ist belegt"}
          </p>
          <div className="mt-1.5 flex flex-col gap-1.5">
            {politik.map((s) => {
              const eigene = positionenVon(daten, s);
              return (
                <p key={s.label} className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5">
                  <UrheberMarke label={s.label} />
                  <SummenWerte e={s.revenues} a={s.expenses} s={s.balance} />
                  {eigene.length > 0 && (
                    <span className="font-mono text-[11px] tabular-nums text-muted-foreground">
                      aus {eigene.length} Position{eigene.length === 1 ? "" : "en"}
                    </span>
                  )}
                  <Beleg q="aenderungsliste" h={daten ? daten.herkunft[String(s.herkunft_id)] ?? null : null} />
                </p>
              );
            })}
          </div>
          <p className="mt-2 max-w-[68ch] text-[11px] leading-relaxed text-muted-foreground">
            Die Listen der Fraktionen selbst wurden als Tischvorlagen verteilt und liegen
            nicht im Ratsinformationssystem — digital belegt ist ihre Summenzeile in der
            Beschluss-Datei des Finanzausschusses, mit dem Urheber daneben.{" "}
            {mitPositionen ? (
              <>
                Für {year} geht diese Datei weiter als alle anderen: Sie führt an
                <em> jeder</em> Position eine Spalte „Vorschlag von“ — was die Fraktionen
                wollten, steht deshalb unten in der Liste Zeile für Zeile, nicht nur als
                Summe. Dass die Zuordnung stimmt, rechnet sich nach: Die Positionen jedes
                Urhebers ergeben genau seine Summe hier oben.
              </>
            ) : (
              <>Was in den Fraktionslisten im Einzelnen stand, sagt für diesen Jahrgang
                kein Dokument.</>
            )}{" "}
            Minus beim Saldo heißt: Das geplante Jahresergebnis sinkt dadurch.
          </p>
        </div>
      )}

      {listen.length > 0 && (
        <div className="mt-3">
          {listen.map((l) => <ListenKarte key={l.schluessel} liste={l} year={year} />)}
        </div>
      )}
    </div>
  );
}
