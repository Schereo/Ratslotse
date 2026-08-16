"use client";

// „Die einzelnen Vorhaben" — der Block, der die Summenebene aufmacht.
//
// Bis 08/2026 endete /haushalt/investitionen bei „Verkehr und Straßenbau:
// 10,5 Mio. €", und der Kasten am Seitenende musste zugeben, dass die häufigste
// Frage an die Seite unbeantwortet bleibt. Dieser Block beantwortet sie, soweit
// die Quelle sie hergibt: Anlage 004 des Haushaltsplans führt jedes Vorhaben
// einzeln, mit Namen und Gesamtkosten.
//
// WAS DIE QUELLE NICHT HERGIBT, und was deshalb im Block steht statt in einer
// Fußnote:
//
//  1. KEINE JAHRESRATEN. Gezeigt wird die Gesamtinvestitionssumme — was das
//     Vorhaben insgesamt kostet, über alle Jahre. Wie viel davon in welchem
//     Jahr fließt, steht zwar im PDF, ist aus dessen Textextrakt aber nicht
//     sicher zu holen (leere Zellen fallen ersatzlos weg). Lieber eine Spalte,
//     die trägt, als fünf geratene.
//  2. KEINE SCHULGEBÄUDE. Der Teilhaushalt „Schule und Bildung" führt
//     Ausstattung und die berufsbildenden Schulen; Sanierung und Neubau der
//     Gebäude liegen beim Eigenbetrieb Gebäudewirtschaft und Hochbau.
//  3. NICHT DIESELBE ZAHL WIE OBEN. Der Block darüber zeigt die Zahlungen
//     EINES Jahres aus dem Finanzhaushalt, dieser die Gesamtkosten über alle
//     Jahre aus dem Haushaltsplan. Beide stimmen, beide zählen Verschiedenes —
//     das Dokument sagt die Abweichung selbst an. Deshalb steht hier NIRGENDS
//     eine Differenz zwischen den beiden: Die Verbindung ist Navigation, keine
//     Rechnung.
//
// KEINE BEWERTUNGSFARBEN (components/haushalt/hantel.tsx): Ein teures Vorhaben
// ist nicht „schlecht". Negative Beträge — Tilgungen, Zuschüsse von Land und
// Bund, Grundstücksverkäufe — bekommen deshalb auch kein Rot, sondern nur ein
// Vorzeichen und eine Erklärung.
//
// KEINE SELBSTVERGEWISSERUNG (DESIGNSPRACHE.md § 7): Dass die drei Proben des
// Dokuments aufgehen, steht in council/investitionsprogramm.py, in den Tests
// und im Beleg als Messwert — nicht als Absatz auf der Seite.

import { useMemo, useState } from "react";
import Link from "next/link";
import { ArrowUp, Search } from "lucide-react";
import { betrag } from "@/lib/haushalt";
import {
  ProgrammDaten, ProgrammZeile, anzahl, gesamtJahr, herkunftVon, suche,
  teilhaushaltSumme, teilhaushalte, vorhaben,
} from "@/lib/haushalt-investitionsprogramm";
import { cn } from "@/lib/utils";

/** Eine Zeile der Vorhaben-Liste.
 *
 *  Der Balken misst am größten Vorhaben des Bereichs, nicht an dessen
 *  Gesamtsumme: In „Verkehr und Straßenbau" steht ein 20-Mio.-Posten neben
 *  Vorhaben von 30.000 € — an der Gesamtsumme gemessen wäre alles außer dem
 *  ersten unsichtbar. Negative Vorhaben bekommen keinen Balken, sondern eine
 *  Marke: Eine Länge nach links wäre ein Bild, das etwas anderes behauptet
 *  („weniger als nichts"). */
function Zeile({ zeile, skala }: { zeile: ProgrammZeile; skala: number }) {
  const b = betrag(zeile.gesamtsumme);
  const breite = skala > 0 && zeile.gesamtsumme > 0
    ? Math.max(0.6, (zeile.gesamtsumme / skala) * 100)
    : 0;
  return (
    <li className="flex flex-col gap-1 py-2">
      <div className="flex items-baseline justify-between gap-3">
        <span className="min-w-0 text-[13px] font-medium">{zeile.bezeichnung}</span>
        <span className="flex-none font-display text-[14px] font-bold tabular-nums">
          {b.wert}
          <span className="ml-1 text-[10px] font-medium text-muted-foreground">
            {b.einheit}
          </span>
        </span>
      </div>
      {zeile.gesamtsumme >= 0 ? (
        <span className="block h-2 w-full overflow-hidden rounded-sm bg-muted/60">
          <span
            className="block h-full rounded-sm"
            style={{ width: `${breite}%`, background: "var(--hh-aus-2)" }}
          />
        </span>
      ) : (
        <span className="text-[10.5px] leading-relaxed text-muted-foreground">
          Steht mit Minus im Programm — Tilgung, Zuschuss von Land oder Bund,
          oder ein Verkauf.
        </span>
      )}
    </li>
  );
}

export function Vorhaben({
  daten, jahr, gewaehlt, aufWaehlen, zurueckAnker,
}: {
  daten: ProgrammDaten | null;
  jahr: number;
  /** Teilhaushaltsnummer, oder `null` für „noch keiner gewählt". */
  gewaehlt: number | null;
  aufWaehlen: (thhNr: number | null) => void;
  /** Anker des Summen-Blocks — der Rückweg von der Maßnahme zur Summe. */
  zurueckAnker: string;
}) {
  const [wort, setWort] = useState("");
  const bereiche = useMemo(() => teilhaushalte(daten, jahr), [daten, jahr]);
  const treffer = useMemo(() => suche(daten, jahr, wort), [daten, jahr, wort]);
  const gesamt = gesamtJahr(daten, jahr);

  // Ohne ausdrückliche Wahl der größte Bereich: Irgendetwas muss offen sein,
  // sonst ist der Block beim ersten Blick eine Reihe Knöpfe ohne Inhalt.
  const aktiv = gewaehlt ?? (bereiche.length ? bereiche[0].thh_nr : null);
  const liste = aktiv != null ? vorhaben(daten, jahr, aktiv) : [];
  const summe = aktiv != null ? teilhaushaltSumme(daten, jahr, aktiv) : null;
  const h = herkunftVon(daten, gesamt?.herkunft_id);

  if (!bereiche.length) return null;

  const suchend = wort.trim().length >= 2;
  const zeigen = suchend ? treffer : liste;
  // Einmal je Liste, nicht einmal je Zeile: Bei 565 Vorhaben wäre die
  // Berechnung im map() ein Quadrat.
  const massstab = zeigen.length
    ? Math.max(...zeigen.map((z) => z.gesamtsumme), 0)
    : 0;

  return (
    <section
      id="vorhaben"
      className="rounded-2xl border border-border bg-card p-4 shadow-sm sm:p-5"
    >
      <div className="flex items-baseline justify-between gap-3">
        <h2 className="font-display text-[15.5px] font-bold tracking-tight">
          Die einzelnen Vorhaben
        </h2>
        <span className="font-mono text-[9.5px] uppercase tracking-[0.11em] text-muted-foreground">
          Haushaltsplan {jahr}
        </span>
      </div>
      <p className="mt-1 max-w-[86ch] text-[12.5px] leading-relaxed text-foreground/90">
        Der Haushaltsplan führt jedes Vorhaben einzeln auf — mit Namen und mit
        dem, was es insgesamt kosten soll. Ein eigenes Dokument, nicht der
        Datensatz von oben: das Investitionsprogramm, Anlage 004.
      </p>

      {/* Suche zuerst: Wer hierherkommt, sucht meist etwas Bestimmtes und
          weiß nicht, in welchem Teilhaushalt es liegt. */}
      <label className="mt-3.5 flex items-center gap-2 rounded-lg border border-border bg-background px-3 py-2">
        <Search className="h-3.5 w-3.5 flex-none text-muted-foreground" />
        <input
          type="search"
          value={wort}
          onChange={(e) => setWort(e.target.value)}
          placeholder={`In allen Vorhaben ${jahr} suchen — „Kunstrasen“, „Feuerwehr“ …`}
          className="min-w-0 flex-1 bg-transparent text-[12.5px] outline-none placeholder:text-muted-foreground"
        />
      </label>

      {!suchend && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {bereiche.map((b) => (
            <button
              key={b.thh_nr}
              type="button"
              onClick={() => aufWaehlen(b.thh_nr)}
              className={cn(
                "rounded-full border px-2.5 py-1 text-[11.5px] transition-colors",
                b.thh_nr === aktiv
                  ? "border-transparent bg-foreground text-background"
                  : "border-border text-muted-foreground hover:text-foreground",
              )}
            >
              {b.bezeichnung}
              <span className="ml-1.5 tabular-nums opacity-70">
                {anzahl(daten, jahr, b.thh_nr)}
              </span>
            </button>
          ))}
        </div>
      )}

      {suchend ? (
        <p className="mt-3.5 text-[12px] text-muted-foreground">
          {treffer.length === 0
            ? `Kein Vorhaben ${jahr} enthält „${wort.trim()}“.`
            : `${treffer.length} ${treffer.length === 1 ? "Vorhaben" : "Vorhaben"} ${jahr} — über alle Bereiche.`}
        </p>
      ) : summe ? (
        // Die Summe des Bereichs steht als Zahl DES DOKUMENTS da, nicht als
        // unsere Addition der Liste darunter (die ergäbe dieselbe Zahl ein
        // zweites Mal — s. Kopf von lib/haushalt-investitionsprogramm.ts).
        <p className="mt-3.5 text-[12px] text-muted-foreground">
          {liste.length} Vorhaben · das Programm weist für diesen Bereich{" "}
          <span className="font-semibold tabular-nums text-foreground">
            {betrag(summe.gesamtsumme).wert} {betrag(summe.gesamtsumme).einheit}
          </span>{" "}
          aus.
        </p>
      ) : null}

      <ul className="mt-1 divide-y divide-[color:var(--border)]">
        {zeigen.map((z) => (
          <Zeile key={`${z.thh_nr}-${z.code}`} zeile={z} skala={massstab} />
        ))}
      </ul>

      <p className="mt-3.5 max-w-[86ch] text-[11.5px] leading-relaxed text-muted-foreground">
        Angegeben ist, was ein Vorhaben <strong className="font-semibold">insgesamt</strong>{" "}
        kosten soll — über alle Jahre, nicht nur {jahr}. Wie viel davon in
        welchem Jahr fließen soll, steht im Plan zwar daneben, lässt sich aus
        dem Dokument aber nicht verlässlich auslesen; deshalb zeigen wir es
        nicht.
      </p>
      <p className="mt-2 max-w-[86ch] text-[11.5px] leading-relaxed text-muted-foreground">
        Es ist der Entwurf der Verwaltung, Stand der Einbringung in den Rat. Was
        die Fraktionen in den Beratungen daran ändern, steht nicht darin — dafür
        ist{" "}
        <Link href="/haushalt/streit" className="text-primary hover:underline">
          Der Streit ums Geld
        </Link>{" "}
        die passende Seite.
      </p>

      {/* Der Rückweg. Von der Summe zur Maßnahme führt der Klick auf den
          Bereich oben; von der Maßnahme zurück führt dieser Link. */}
      <div className="mt-4 flex flex-wrap items-center justify-between gap-2 border-t border-dashed border-border pt-3">
        <a
          href={`#${zurueckAnker}`}
          onClick={() => aufWaehlen(null)}
          className="inline-flex items-center gap-1.5 text-[11.5px] text-primary hover:underline"
        >
          <ArrowUp className="h-3 w-3" />
          Zurück zu den Summen je Bereich
        </a>
        {h?.fundstelle && (
          <span className="text-[11px] text-muted-foreground">
            {h.stand}
          </span>
        )}
      </div>
    </section>
  );
}
