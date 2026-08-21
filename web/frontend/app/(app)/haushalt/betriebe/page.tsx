"use client";

// /haushalt/betriebe — der Haushalt neben dem Haushalt.
//
// Der Rat beschließt nicht nur den Stadthaushalt, sondern daneben die
// Wirtschaftspläne der Eigenbetriebe und städtischen Gesellschaften. Diese
// Seite zeigt sie. Sie steht in der Stufe „Der Rahmen", direkt hinter „Was
// machen die eigentlich?": Dort erfährt man, WAS die Betriebe tun — hier, was
// sie sich für das laufende Jahr vornehmen.
//
// DREI ENTSCHEIDUNGEN, die diese Seite trägt:
//
//  1. **Nicht addieren, und das laut sagen.** Der Eigenbetrieb
//     Gebäudewirtschaft vermietet der Stadt ihre eigenen Gebäude; seine
//     Erträge sind zu großen Teilen Aufwand des Kernhaushalts. Wer die Summen
//     nebeneinanderstellt und zusammenzählt, zählt dasselbe Geld zweimal.
//     Deshalb gibt es auf dieser Seite KEINE Gesamtsumme über alle Betriebe —
//     nicht als Auslassung, sondern als Aussage. Herausgerechnet wird die
//     Verflechtung erst im Gesamtabschluss (`/haushalt/konzern`).
//  2. **Leere Zellen bleiben leer.** Nur zwei der sechs Betriebe nennen
//     Erträge und Aufwendungen in prüfbarer Form. Bei den übrigen steht dort
//     ein Strich und daneben, warum — eine 0 wäre eine Behauptung.
//  3. **Die Beleglage steht an der Zahl.** Drei Fälle, die verschieden viel
//     wert sind: in der Anlage gegengeprüft, ausgeglichener Plan (die Null
//     lässt sich nicht gegenprüfen), oder Anlage ohne lesbaren Text. Ein
//     gemeinsames Häkchen für alle drei verspräche zu viel.

import { useMemo } from "react";
import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { useFetch } from "@/lib/use-fetch";
import {
  HaushaltAuswahl, WirtschaftsplanZeile, deMio, haushaltUrl, herkunftVon,
} from "@/lib/haushalt";
import type { QuellenSchluessel } from "@/lib/haushalt-quellen";
import type { Herkunft } from "@/lib/herkunft";
import {
  Beleg, Dokumentbeleg, Quellenkontext, Quellenverzeichnis,
} from "@/components/haushalt/quelle";
import { Zeitreihe } from "@/components/grafik/zeitreihe";
import type { JahrPunkt } from "@/components/grafik/daten";
import { LottiErklaert } from "@/components/haushalt/lotti-erklaert";
import { cn } from "@/lib/utils";

// `herkunft` ist hier PFLICHT und keine Zugabe: Ein Jahrgang besteht aus
// bis zu sieben Plänen von sieben Betrieben, und nur die `herkunft_id` der
// Zeile sagt, welches der sieben Papiere hinter DIESER Karte steht.
const FELDER = ["wirtschaftsplaene", "herkunft"] as const;
const QUELLEN: QuellenSchluessel[] = ["wirtschaftsplan"];



/** Was ein Betrieb tut — eine Zeile, damit die Zahl einen Gegenstand bekommt.
 *
 *  Redaktionell und bewusst kurz: Der ausführliche Auftrag steht im
 *  Beteiligungsbericht und damit auf `/haushalt/beteiligungen`. Hier genügt,
 *  was man wissen muss, um die Zahl daneben einzuordnen. */
const WAS_SIE_TUN: Record<string, string> = {
  egh: "Baut und unterhält die städtischen Gebäude — Schulen, Kitas, Rathäuser.",
  awb: "Müllabfuhr, Straßenreinigung und Winterdienst. Aus diesem Plan werden "
    + "die Abfallgebühren kalkuliert.",
  bbo: "Verwaltet das Bäder-Vermögen und verpachtet es an die "
    + "Betriebsgesellschaft; der laufende Betrieb liegt seit 2005 dort.",
  bbgo: "Betreibt die Bäder — OLantis und die übrigen Standorte.",
  stadion: "Betreibt das künftige Stadion.",
  stadion_planung: "Hat den Stadionbau geplant.",
  hafen: "Betrieb den Stadthafen — Liegeplätze, Anleger und Umschlag.",
};

/** Betriebe, die es nicht mehr gibt, mit dem Vorgang, der sie beendet hat.
 *
 *  Ohne diesen Satz sieht eine Reihe, die 2020 aufhört, aus wie eine Lücke in
 *  unseren Daten — und der ganze Bereich ist darauf gebaut, Lücken zu zeigen
 *  statt sie zu verstecken. Hier ist keine: Es gibt schlicht keinen dritten
 *  Wirtschaftsplan. Warum eine Reihe endet, steht in keiner Tabelle; nur DASS
 *  sie endet, ist aus den Daten ablesbar. Deshalb der Satz von Hand, und die
 *  Prüfung, ob er überhaupt gilt, aus den Daten. */
const ENDE: Record<string, string> = {
  hafen: "Diesen Eigenbetrieb gibt es nicht mehr: 2020 beschloss der Rat den "
    + "Rechtsformwechsel (Vorlage 20/0322) und die Auflösungssatzung "
    + "(20/0809). Zwei Wirtschaftspläne sind deshalb der ganze Bestand.",
};

/** Wie sicher die Zahl belegt ist. Die drei Lagen stehen so in der Datenbank
 *  (`council/wirtschaftsplan_kernzahl.BELEGLAGE`) — hier nur die Fassung für
 *  Leserinnen. */
const BELEGLAGE: Record<string, { kurz: string; lang: string }> = {
  wirtschaftsplan_kernzahl: {
    kurz: "Beschluss + Anlage",
    lang: "Die Zahl steht im Beschlusstext der Ratsvorlage und noch einmal in "
      + "der beigefügten Anlage — zwei getrennte Dokumente.",
  },
  wirtschaftsplan_erfolgsplan: {
    kurz: "Beschlusstext, nachgerechnet",
    lang: "Der Beschlusstext nennt Erträge, Aufwendungen und Ergebnis; die "
      + "Rechnung geht auf den Cent auf.",
  },
  wirtschaftsplan_spalten: {
    kurz: "Erfolgsplan, spaltenweise geprüft",
    lang: "Aus dem Erfolgsplan der Anlage. Erträge minus Aufwendungen ergibt "
      + "das Ergebnis — geprüft in jeder Spalte der Tabelle, nicht nur in der "
      + "gezeigten.",
  },
};

function beleg(proben: string): { kurz: string; lang: string } {
  for (const schluessel of Object.keys(BELEGLAGE)) {
    if (proben.includes(schluessel)) return BELEGLAGE[schluessel];
  }
  return { kurz: "geprüft", lang: "Die Rechenprobe dieser Zeile ist gelaufen." };
}

/** Ein Betrag in Mio. €, oder ein Strich mit Begründung. */
function Betrag({ wert, fehltWeil }: { wert: number | null; fehltWeil: string }) {
  if (wert == null) {
    return (
      <span className="text-muted-foreground" title={fehltWeil}>
        —<span className="sr-only"> {fehltWeil}</span>
      </span>
    );
  }
  return (
    <span className="tabular-nums">
      {deMio(wert / 1e6)}&#8239;Mio.&nbsp;€
    </span>
  );
}

/** Der Jahrgang, der die Karte trägt. EINE Fassung dieser Regel, weil die
 *  Nummerierung der Quellen dieselbe Zeile treffen muss wie die Anzeige —
 *  zwei Sortierungen driften, und dann trägt ein Chip die Nummer eines
 *  fremden Papiers. */
function juengsteZeile(zeilen: WirtschaftsplanZeile[]): WirtschaftsplanZeile {
  return [...zeilen].sort((a, b) => a.jahr - b.jahr)[zeilen.length - 1];
}

function BetriebsKarte({ zeilen, juengstesJahr, herkunftFuer }: {
  zeilen: WirtschaftsplanZeile[]; juengstesJahr: number;
  /** Die Suche, nicht das Ergebnis: WELCHE Zeile die jüngste ist, entscheidet
   *  diese Karte selbst (s. `nach` unten) — der Aufrufer wüsste es nur, wenn
   *  er dieselbe Sortierung noch einmal schriebe, und zwei Fassungen
   *  derselben Regel driften. */
  herkunftFuer: (id: number | null) => Herkunft | null;
}) {
  // Der jüngste Jahrgang trägt die Karte; die Reihe darunter ist die
  // Entwicklung. Sortiert wird hier und nicht im Vertrauen auf die API.
  const nach = [...zeilen].sort((a, b) => a.jahr - b.jahr);
  const letzte = juengsteZeile(zeilen);
  const b = beleg(letzte.proben);
  const reihe: JahrPunkt[] = nach.map((z) => ({ jahr: z.jahr, wert: z.ergebnis / 1e6 }));
  const zeigKurve = nach.length >= 3;

  return (
    <div className="rounded-2xl border border-border bg-card p-4 shadow-sm sm:p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <h3 className="font-display text-[15px] font-bold leading-tight">
          {letzte.betrieb_name}
        </h3>
        <span className="font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
          Plan {letzte.jahr}
        </span>
      </div>
      {WAS_SIE_TUN[letzte.betrieb] && (
        <p className="mt-1 max-w-[62ch] text-[12.5px] leading-relaxed text-foreground/80">
          {WAS_SIE_TUN[letzte.betrieb]}
        </p>
      )}
      {/* Nur zeigen, wenn die Reihe wirklich vor dem jüngsten Jahrgang des
          Bereichs endet — sonst stünde der Satz eines Tages an einer Karte,
          die längst weiterläuft. */}
      {ENDE[letzte.betrieb] && letzte.jahr < juengstesJahr && (
        <p className="mt-1.5 max-w-[62ch] border-l-2 border-border pl-2.5
                      text-[12px] leading-relaxed text-muted-foreground">
          {ENDE[letzte.betrieb]}
        </p>
      )}

      <dl className="mt-3 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-[13px]">
        <dt className="text-muted-foreground">Erträge</dt>
        <dd className="text-right font-semibold">
          <Betrag wert={letzte.ertraege}
            fehltWeil="Diese Quelle nennt nur das Jahresergebnis." />
        </dd>
        <dt className="text-muted-foreground">Aufwendungen</dt>
        <dd className="text-right font-semibold">
          <Betrag wert={letzte.aufwendungen}
            fehltWeil="Diese Quelle nennt nur das Jahresergebnis." />
        </dd>
        <dt className="border-t border-border pt-1 font-semibold">Ergebnis</dt>
        <dd className={cn(
          "border-t border-border pt-1 text-right font-display text-[15px] font-bold tabular-nums",
          // KEINE Bewertungsfarbe: Ein Minus beim Bäderbetrieb ist die
          // politische Entscheidung, Bäder zu bezuschussen, und kein Missstand
          // (dieselbe Regel wie im ganzen Bereich, s. grafik/hantel.tsx).
        )}>
          {deMio(letzte.ergebnis / 1e6)}&#8239;Mio.&nbsp;€
        </dd>
      </dl>

      {letzte.vermoegensplan != null && (
        <p className="mt-2 text-[12px] text-muted-foreground">
          Dazu ein Vermögensplan über {deMio(letzte.vermoegensplan / 1e6)}&#8239;Mio.&nbsp;€
          {letzte.verpflichtungen != null && (
            <> und Verpflichtungsermächtigungen über{" "}
              {deMio(letzte.verpflichtungen / 1e6)}&#8239;Mio.&nbsp;€, die künftige
              Jahre binden</>
          )}.
        </p>
      )}

      <div className="mt-2.5 border-t border-dashed border-border pt-2">
        <p className="text-[11.5px] leading-relaxed text-muted-foreground">
          <span className="font-semibold text-foreground">Beleg: {b.kurz}.</span>{" "}
          {b.lang}
          <Beleg q="wirtschaftsplan" h={herkunftFuer(letzte.herkunft_id)} />
          {letzte.entwurf_vom && ` · Stand des Verwaltungsentwurfs: ${letzte.entwurf_vom}`}
        </p>
        {/* Bis zum 21.08.2026 stand hier „Vorlage 25/0722" als toter Text —
            die Nummer des Papiers, aus dem die Zahl stammt, ohne Weg dorthin.
            Jetzt führt sie hin, und zwar je Betrieb woandershin. */}
        <Dokumentbeleg h={herkunftFuer(letzte.herkunft_id)}
          vorlageNr={letzte.vorlage_nr} />
      </div>

      {zeigKurve && (
        <div className="mt-3">
          <Zeitreihe
            reihe={reihe}
            einheit="Mio. €"
            nachkomma={2}
            titel="Jahresergebnis im Plan"
            ariaTitel={`Geplantes Jahresergebnis ${letzte.betrieb_name}, `
              + `${nach[0].jahr} bis ${letzte.jahr}, in Millionen Euro`}
          />
        </div>
      )}
      {!zeigKurve && nach.length > 1 && (
        <p className="mt-2 text-[12px] text-muted-foreground">
          Frühere Jahrgänge:{" "}
          {nach.slice(0, -1).map((z) => `${z.jahr}: ${deMio(z.ergebnis / 1e6)} Mio. €`)
            .join(" · ")}
        </p>
      )}
    </div>
  );
}

function BetriebeInner() {
  const { data, loading } = useFetch<HaushaltAuswahl<typeof FELDER[number]>>(
    haushaltUrl(FELDER));

  const nachBetrieb = useMemo(() => {
    const zeilen = data?.wirtschaftsplaene ?? [];
    const gruppen = new Map<string, WirtschaftsplanZeile[]>();
    for (const z of zeilen) {
      const liste = gruppen.get(z.betrieb) ?? [];
      liste.push(z);
      gruppen.set(z.betrieb, liste);
    }
    // Nach der Größe des jüngsten Ergebnisses sortiert — der Betrag, um den es
    // geht, nicht das Alphabet. Absteigend nach Betrag heißt: der größte
    // Zuschussbedarf steht oben.
    return [...gruppen.values()].sort((a, b) => {
      const gross = (l: WirtschaftsplanZeile[]) =>
        Math.abs(l[l.length - 1]?.ergebnis ?? 0);
      return gross(b) - gross(a);
    });
  }, [data]);

  // JEDER PLAN EINE EIGENE NUMMER. Über fünf Wirtschaftsplänen aus fünf
  // Betrieben stand „1 Quelle" — richtig nach der alten Regel (eine Nummer je
  // Quellenart) und trotzdem die falsche Auskunft (Tim, 21.08.2026). Hier ruht
  // jede Karte auf genau EINEM Papier, also verdient jedes seine Ziffer.
  //
  // Gesammelt wird aus den KARTEN, nicht aus dem Jahrgang: Den Stadthafen gibt
  // es seit 2020 nicht mehr, die Stadion-Planung endete 2024 — ihre Papiere
  // stehen in keiner Jahrgangsliste von 2026, ihre Karten aber sehr wohl auf
  // der Seite.
  const jeDokument = useMemo(() => {
    const urls = nachBetrieb
      .map((zeilen) => herkunftVon(data, juengsteZeile(zeilen).herkunft_id)?.url)
      .filter((u): u is string => !!u);
    return urls.length ? { wirtschaftsplan: urls } : {};
  }, [nachBetrieb, data]);

  if (loading || !data) {
    return (
      <div className="py-16 text-center text-sm text-muted-foreground">
        Wirtschaftspläne werden geladen …
      </div>
    );
  }
  if (!nachBetrieb.length) {
    return (
      <div className="py-16 text-center text-sm text-muted-foreground">
        Für diesen Bestand liegen uns noch keine Wirtschaftspläne vor.
      </div>
    );
  }

  const jahre = (data.wirtschaftsplaene ?? []).map((z) => z.jahr);
  const juengstes = Math.max(...jahre);
  const aeltestes = Math.min(...jahre);

  return (
    <Quellenkontext schluessel={QUELLEN} jeDokument={jeDokument} jahr={juengstes}>
      <div className="flex flex-col gap-4">
        <header>
          <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-primary">
            Stadtfinanzen Oldenburg · Schritt 13
          </p>
          <h1 className="mt-1 font-display text-2xl font-bold tracking-tight sm:text-3xl">
            Der Haushalt neben dem Haushalt
          </h1>
          <p className="mt-2 max-w-[68ch] text-[13.5px] leading-relaxed text-foreground/85">
            Der Rat beschließt nicht nur den Stadthaushalt. Daneben stehen die
            Wirtschaftspläne der Eigenbetriebe und städtischen Gesellschaften —
            eigene Rechnungen, in derselben Sitzung entschieden. Hier stehen
            {" "}{nachBetrieb.length} davon, für die Jahre {aeltestes} bis {juengstes}.
          </p>
        </header>

        {/* Der Kasten steht VOR den Zahlen und nicht als Fußnote darunter: Wer
            die Summen erst liest und dann erfährt, dass er sie nicht addieren
            darf, hat es schon getan. */}
        <div className="rounded-2xl border border-signal/40 bg-card p-4 shadow-sm">
          <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-signal">
            Diese Zahlen gehören nicht zum Stadthaushalt dazu
          </p>
          <p className="mt-2 max-w-[68ch] text-[13px] leading-relaxed text-foreground/85">
            Sie lassen sich mit ihm auch nicht zusammenzählen. Der Eigenbetrieb
            Gebäudewirtschaft vermietet der Stadt ihre eigenen Gebäude: Seine
            Erträge sind zu großen Teilen Aufwand des Kernhaushalts, und wer
            beides addiert, zählt dasselbe Geld zweimal. Deshalb steht auf
            dieser Seite keine Gesamtsumme. Wer wissen will, was die Stadt
            samt allen Betrieben umsetzt, findet das im Gesamtabschluss —
            dort ist die Verflechtung herausgerechnet.
          </p>
          <Link href="/haushalt/konzern"
            className="mt-2.5 inline-flex items-center gap-1 rounded-lg border border-border bg-card px-2.5 py-1 text-[12px] font-semibold text-primary shadow-sm">
            Zum Konzern Stadt <ArrowRight className="h-3 w-3" />
          </Link>
        </div>

        <div className="grid gap-4 lg:grid-cols-2">
          {nachBetrieb.map((zeilen) => (
            <BetriebsKarte key={zeilen[0].betrieb} zeilen={zeilen}
              juengstesJahr={juengstes}
              herkunftFuer={(id) => herkunftVon(data, id)} />
          ))}
        </div>

        <LottiErklaert
          titel="Warum manche Betriebe planmäßig Verlust machen"
          text="Ein Bad, das sich selbst trägt, gäbe es in Oldenburg nicht — Eintrittsgelder decken die Kosten eines Schwimmbads nirgendwo. Dass die Bäderbetriebsgesellschaft mit einem Minus plant, ist deshalb keine Panne, sondern die Entscheidung, Schwimmbäder anzubieten; die Stadt gleicht den Fehlbetrag aus. Beim Abfallwirtschaftsbetrieb ist es umgekehrt: Er finanziert sich aus Gebühren, die so kalkuliert werden, dass sie die Kosten decken — deshalb steht dort ein kleines Plus."
        />

        {/* Was die Seite NICHT zeigt — gezählt, nicht verschwiegen. */}
        <div className="rounded-2xl border border-dashed border-border bg-muted/40 p-4">
          <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
            Was hier fehlt
          </p>
          <ul className="mt-2 flex flex-col gap-1.5 text-[12.5px] leading-relaxed text-foreground/85">
            <li>
              <strong className="text-foreground">Der Eigenbetrieb Hafen.</strong>{" "}
              Von ihm liegen nur zwei Wirtschaftspläne vor, beide aus 2019 und
              2020, in einem Aufbau, den wir nicht gelesen haben. Zwei alte
              Jahrgänge sind uns einen eigenen Parser nicht wert — und geraten
              wird hier nichts.
            </li>
            <li>
              <strong className="text-foreground">Erträge und Aufwendungen der
                meisten Betriebe.</strong>{" "}
              Vier der sechs nennen im Beschluss nur das Jahresergebnis. Was
              dort ein Strich ist, steht in keiner Form da, die sich nachrechnen
              lässt.
            </li>
            <li>
              <strong className="text-foreground">Vier ältere Jahrgänge</strong>{" "}
              liegen nur als eingescanntes Papier vor, ohne lesbaren Text. Sie
              sind als solche vermerkt, falls sich das später ändern lässt.
            </li>
          </ul>
        </div>

        <Quellenverzeichnis schluessel={QUELLEN} />
      </div>
    </Quellenkontext>
  );
}

export default function BetriebePage() {
  return <BetriebeInner />;
}
