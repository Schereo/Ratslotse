"use client";

// „Was am Bauen geändert wurde" — der Finanzhaushalt im Streit-Abschnitt.
//
// Die Schwester-Karte zu `streit-listeninhalt.tsx`. Jene zeigt den
// ERGEBNIShaushalt: was die Stadt erwirtschaftet und verbraucht. Diese zeigt
// den FINANZhaushalt — was tatsächlich fließt, und vor allem, was investiert
// wird. Beide Listen entstehen im selben Verfahren und liegen als Anlage an
// derselben Vorlage; wer wissen will, was der Rat geändert hat, braucht
// beide.
//
// WARUM EINE EIGENE KARTE und nicht ein Umschalter in der bestehenden: Die
// beiden Haushalte beantworten verschiedene Fragen, und ein Umschalter legt
// nahe, es seien zwei Ansichten derselben Sache. Der Investitionsteil hat
// außerdem etwas, das der Ergebnisteil nicht hat — den Code des Vorhabens,
// an dem geschraubt wurde.
//
// DREI DINGE, DIE DIE KARTE NICHT TUT:
//
//  * **Sie summiert Ein- und Auszahlungen nicht gegeneinander.** Im
//    Finanzhaushalt sind das zwei Richtungen, keine zwei Vorzeichen: Eine
//    Einzahlung ist ein Zuschuss oder ein Verkauf, eine Auszahlung die
//    Investition selbst. Die Zusammenstellung des Dokuments bildet daraus
//    einen Saldo — der steht am Fuß der Liste, nicht in jeder Zeile.
//  * **Sie zeigt die Verpflichtungsermächtigungen nicht als Betrag der
//    Zeile.** Eine VE ist die Erlaubnis, künftige Jahre zu binden, kein Geld
//    dieses Jahres — sie zählt auch im Dokument nicht in den Saldo.
//  * **Sie führt keine Positionen ohne Beträge.** Ein Teil der Zeilen sind
//    reine Haushaltsvermerke: Text, den die Verwaltung in den Plan schreibt,
//    ohne dass sich eine Zahl ändert. In einer Liste „was geändert wurde"
//    behaupteten sie eine Änderung, die es nicht gibt (`fhhListenFuerJahr`
//    sortiert sie aus).

import { ChevronDown } from "lucide-react";
import {
  AenderungslistenDaten, FhhListeImJahr, deltaBetrag, fhhListenFuerJahr,
} from "@/lib/haushalt-aenderungslisten";
import { Beleg, Dokumentbeleg } from "@/components/haushalt/quelle";
import { BetragZelle, TextZelle, ZahlenTabelle } from "@/components/haushalt/zahlen-tabelle";
import { cn } from "@/lib/utils";

function ListenKarte({ liste, jahr }: { liste: FhhListeImJahr; jahr: number }) {
  const mitCode = liste.zeilen.filter((z) => z.produkt).length;
  return (
    <details className="group border-t border-border/60 py-2.5 first:border-t-0 first:pt-0">
      <summary className="flex cursor-pointer list-none flex-wrap items-baseline gap-x-3 gap-y-1">
        <ChevronDown className="h-3.5 w-3.5 translate-y-0.5 text-muted-foreground transition-transform group-open:rotate-180" />
        <span className="text-[13px] font-semibold text-foreground">{liste.name}</span>
        <span className="font-mono text-[11px] tabular-nums text-muted-foreground">
          {liste.zeilen.length} Position{liste.zeilen.length === 1 ? "" : "en"} für {jahr}
          {mitCode > 0 && ` · ${mitCode} mit Vorhaben-Nummer`}
        </span>
        {liste.saldo && (
          <span className={cn("ml-auto whitespace-nowrap font-mono text-[11.5px] font-medium tabular-nums",
            liste.saldo.saldo < 0 ? "text-signal" : "text-foreground")}>
            Saldo {deltaBetrag(liste.saldo.saldo)}
          </span>
        )}
      </summary>

      <div className="mt-2 pl-[26px]">
        <ZahlenTabelle
          className="mt-2"
          spalten={[
            { titel: "Vorhaben" },
            { titel: "Einzahlung", zahl: true },
            { titel: "Auszahlung", zahl: true },
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
              <BetragZelle euro={liste.saldo.einzahlungen} label="Einzahlung"
                text={deltaBetrag(liste.saldo.einzahlungen)}
                className="border-t-border/60 py-2 font-medium" />
              <BetragZelle euro={liste.saldo.auszahlungen} label="Auszahlung"
                text={deltaBetrag(liste.saldo.auszahlungen)}
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
                  <span className="italic text-muted-foreground">
                    Position {z.lfd} (ohne lesbaren Namen)
                  </span>
                )}
                {z.produkt && (
                  // Die Nummer des Vorhabens aus dem Investitionsprogramm.
                  // Sie steht hier als Kennung, nicht als Link: Die Suche auf
                  // „Was wird gebaut?" hält ihr Suchwort im Zustand, nicht in
                  // der Adresse — ein Sprung dorthin käme auf einer leeren
                  // Suche an. Wer die Nummer braucht, kann sie kopieren.
                  <span className="ml-2 font-mono text-[10px] text-muted-foreground">
                    {z.produkt}
                  </span>
                )}
                <span className="ml-2 font-mono text-[10px] text-muted-foreground">
                  {z.thh != null ? `THH ${String(z.thh).padStart(2, "0")}` : "alle THH"}
                </span>
                {z.seite_entwurf === "neu" && (
                  // „neu“ heißt: Diese Zeile stand im Entwurf noch gar nicht.
                  <span className="ml-2 rounded-full bg-muted px-1.5 py-px font-mono text-[9.5px] uppercase tracking-[0.08em] text-muted-foreground">
                    neu im Verfahren
                  </span>
                )}
                {z.erlaeuterung && (
                  <span className="mt-0.5 block max-w-[75ch] text-[11px] leading-relaxed text-muted-foreground">
                    {z.erlaeuterung}
                  </span>
                )}
                {z.ve != null && z.ve !== 0 && (
                  <span className="mt-0.5 block text-[10.5px] leading-relaxed text-muted-foreground">
                    Dazu eine Verpflichtungsermächtigung über{" "}
                    <span className="font-mono tabular-nums">{deltaBetrag(z.ve)}</span> —
                    die Erlaubnis, künftige Jahre zu binden. Sie ist kein Geld dieses
                    Jahres und zählt auch im Dokument nicht in den Saldo.
                  </span>
                )}
              </TextZelle>
              <BetragZelle euro={z.einzahlung} label="Einzahlung"
                text={deltaBetrag(z.einzahlung)} />
              <BetragZelle euro={z.auszahlung} label="Auszahlung"
                text={deltaBetrag(z.auszahlung)} />
            </tr>
          ))}
        </ZahlenTabelle>
        <div className="mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-1">
          <Dokumentbeleg h={liste.herkunft} />
        </div>
      </div>
    </details>
  );
}

export function StreitFinanzhaushalt({ daten, jahr }: {
  daten: AenderungslistenDaten | null;
  jahr: number | null;
}) {
  const listen = fhhListenFuerJahr(daten, jahr);
  if (!jahr || !listen.length) return null;

  return (
    <div className="rounded-2xl border border-border bg-card p-4 shadow-sm">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <h2 className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
          Was am Bauen geändert wurde
        </h2>
        <span className="font-mono text-[10px] tabular-nums text-muted-foreground">
          Haushalt {jahr}
        </span>
      </div>
      <p className="mt-1 max-w-[70ch] text-[12.5px] leading-relaxed text-muted-foreground">
        Der Haushalt hat zwei Teile, und beide werden im Verfahren geändert. Oben
        steht der Ergebnishaushalt — was die Stadt erwirtschaftet und verbraucht.
        Hier steht der Finanzhaushalt: was tatsächlich fließt, und vor allem, was
        investiert wird. Diese Listen sagen also, an welchen Vorhaben zwischen
        Entwurf und Beschluss geschraubt wurde.
      </p>
      <p className="mt-1.5 max-w-[70ch] text-[11px] leading-relaxed text-muted-foreground">
        Einzahlungen und Auszahlungen stehen nebeneinander, nicht gegeneinander:
        Eine Einzahlung ist ein Zuschuss oder ein Verkauf, eine Auszahlung die
        Investition selbst. Den Saldo daraus bildet das Dokument am Fuß der
        Liste, nicht in jeder Zeile.
      </p>

      <div className="mt-3">
        {listen.map((l) => <ListenKarte key={l.schluessel} liste={l} jahr={jahr} />)}
      </div>
    </div>
  );
}
