"use client";

// Der Investitionen-Explorer (Board H4-06) — „4.459 Vorhaben, durchsuchbar".
//
// Bis 08/2026 endete /haushalt/investitionen bei „Verkehr und Straßenbau:
// 10,5 Mio. €"; seit dem Vorhaben-Block beantwortet die Seite auch die Ebene
// darunter. H4-06 macht daraus den Explorer: Suche, Filter und eine
// Kachelfläche (<Treemap>, GB-08), in der die Fläche die Gesamtsumme ist —
// 1 mm² ist überall gleich viel Geld. Mobil ersetzt eine Rangliste mit
// Schiene die Kacheln (H4-A, in der Treemap-Komponente eingebaut).
//
// ZWEI KÄSTEN GEHÖREN VOR DIE ERGEBNISSE, nicht in eine Fußnote:
//
//  1. DER SCHULGEBÄUDE-KASTEN. „Wird meine Schule saniert?" ist die häufigste
//     Erwartung an diese Seite — und die Antwort steht NICHT in diesem
//     Programm: Sanierung und Neubau der Schulgebäude verantwortet der
//     Eigenbetrieb Gebäudewirtschaft und Hochbau mit eigenem Wirtschaftsplan.
//     Wer erst sucht und dann die Fußnote findet, hat fünf Minuten verloren.
//  2. DER PLANZAHLEN-KASTEN. Die Zahlen sind der Verwaltungsentwurf, Stand
//     der Einbringung — keine Beschlüsse. Und die Summen decken sich
//     absichtlich nicht mit dem Finanzhaushalt der Seite darüber
//     (aktivierbare Eigenleistungen — das Dokument sagt das selbst).
//
// WAS DIE QUELLE NICHT HERGIBT, bleibt draußen:
//
//  1. KEINE JAHRESRATEN. Gezeigt wird die Gesamtinvestitionssumme — was das
//     Vorhaben insgesamt kostet, über alle Jahre. Wie viel davon in welchem
//     Jahr fließt, steht zwar im PDF, ist aus dessen Textextrakt aber nicht
//     sicher zu holen (leere Zellen fallen ersatzlos weg). Deshalb trägt die
//     Kachelfläche auch KEINE Zeitachse — nur die Gesamtsumme trägt.
//  2. NICHT DIESELBE ZAHL WIE OBEN. Der Block darüber zeigt die Zahlungen
//     EINES Jahres aus dem Finanzhaushalt, dieser die Gesamtkosten über alle
//     Jahre aus dem Haushaltsplan. Beide stimmen, beide zählen Verschiedenes —
//     das Dokument sagt die Abweichung selbst an. Deshalb steht hier NIRGENDS
//     eine Differenz zwischen den beiden: Die Verbindung ist Navigation, keine
//     Rechnung.
//
// KEINE BEWERTUNGSFARBEN (components/grafik/hantel.tsx): Ein teures Vorhaben
// ist nicht „schlecht". Negative Beträge — Tilgungen, Zuschüsse von Land und
// Bund, Grundstücksverkäufe — bekommen deshalb auch kein Rot, sondern nur ein
// Vorzeichen und eine Erklärung; in der Kachelfläche können sie nicht
// auftauchen (eine Fläche kann „weniger als nichts" nicht zeigen — die
// Treemap sagt das selbst dazu).
//
// KEINE SELBSTVERGEWISSERUNG (DESIGNSPRACHE.md § 7): Dass die drei Proben des
// Dokuments aufgehen, steht in council/investitionsprogramm.py, in den Tests
// und im Beleg als Messwert — nicht als Absatz auf der Seite.

import { useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { ArrowUp, Search } from "lucide-react";
import { betrag } from "@/lib/haushalt";
import {
  ProgrammDaten, ProgrammZeile, anzahl, gesamtJahr, herkunftVon, suche,
  teilhaushaltSumme, teilhaushalte, vorhaben,
} from "@/lib/haushalt-investitionsprogramm";
import { rampenText } from "@/components/grafik/kachelflaeche";
import { Treemap, type TreemapKnoten } from "@/components/grafik/treemap";
import { Beleg } from "@/components/haushalt/quelle";

/** Eine Zeile der Vorhaben-Liste.
 *
 *  Der Balken misst am größten Vorhaben der Liste, nicht an deren
 *  Gesamtsumme: In „Verkehr und Straßenbau" steht ein 20-Mio.-Posten neben
 *  Vorhaben von 30.000 € — an der Gesamtsumme gemessen wäre alles außer dem
 *  ersten unsichtbar. Negative Vorhaben bekommen keinen Balken, sondern eine
 *  Marke: Eine Länge nach links wäre ein Bild, das etwas anderes behauptet
 *  („weniger als nichts"). */
function Zeile({ zeile, skala, bereichName }: {
  zeile: ProgrammZeile; skala: number;
  /** Bei bereichsübergreifenden Trefferlisten: wo das Vorhaben liegt. */
  bereichName?: string;
}) {
  const b = betrag(zeile.gesamtsumme);
  const breite = skala > 0 && zeile.gesamtsumme > 0
    ? Math.max(0.6, (zeile.gesamtsumme / skala) * 100)
    : 0;
  return (
    <li className="flex flex-col gap-1 py-2">
      <div className="flex items-baseline justify-between gap-3">
        <span className="min-w-0 text-[13px] font-medium">
          {zeile.bezeichnung}
          {bereichName && (
            <span className="ml-1.5 font-mono text-[9.5px] font-normal uppercase tracking-[0.09em] text-muted-foreground">
              {bereichName}
            </span>
          )}
        </span>
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

type Sortierung = "gesamtsumme" | "alpha";

export function Vorhaben({
  daten, year, gewaehlt, aufWaehlen, zurueckAnker, farbeVonThh, stufeVonThh,
}: {
  daten: ProgrammDaten | null;
  /** Der Jahrgang, den die Seite oben zeigt — Startwert des Filters. */
  year: number;
  /** Teilhaushaltsnummer, oder `null` für „alle Teilhaushalte". */
  gewaehlt: number | null;
  aufWaehlen: (thhNr: number | null) => void;
  /** Anker des Summen-Blocks — der Rückweg von der Maßnahme zur Summe. */
  zurueckAnker: string;
  /** EIN Farbschlüssel je Teilhaushalt für die ganze Seite — kommt von der
   *  Seite, damit Kachelfläche und Überblicksbalken denselben sprechen. */
  farbeVonThh: (thhNr: number) => string;
  /** Die Rampenstufe hinter dieser Farbe — daran hängt die Textfarbe auf der
   *  Kachel (`grafik/kachelflaeche.ts`, `rampenText`). */
  stufeVonThh: (thhNr: number) => number;
}) {
  // `?vorhaben=` und `?year=` — der Landeplatz für Links von außen.
  //
  // Von den Änderungslisten zum Finanzhaushalt (/haushalt/mitreden#streit)
  // führt seit 08/2026 ein Link auf die Nummer eines Vorhabens. Damit er
  // ankommt, muss der Explorer sein Suchwort aus der ADRESSE nehmen können
  // und nicht nur aus dem Eingabefeld — und das Jahr gleich mit: Die Nummer
  // gehört zu dem Jahrgang, in dem die Änderungsliste sie geändert hat.
  //
  // Als STARTWERT, nicht als gebundener Zustand: Wer nach dem Ankommen etwas
  // anderes sucht, soll nicht gegen die Adresse antippen. Die Adresse setzt
  // den Anfang, danach gehört das Feld der Leserin.
  const params = useSearchParams();
  const [wort, setWort] = useState(() => params.get("vorhaben") ?? "");
  const [sortierung, setSortierung] = useState<Sortierung>("gesamtsumme");
  // Der Explorer hat seinen eigenen Jahrgang-Filter (H4-06): Die beiden
  // Quellen der Seite reichen verschieden weit (Portal 2022–2025, Plan
  // 2019–2026) — wer 2019 sehen will, darf nicht am Jahr der Seite hängen.
  const [jahrWahl, setJahrWahl] = useState<number | null>(
    () => Number(params.get("year")) || null);
  const suchfeld = useRef<HTMLInputElement>(null);

  const jahre = useMemo(
    () => [...(daten?.jahre ?? [])].sort((a, b) => a - b), [daten]);
  const effJahr = jahrWahl != null && jahre.includes(jahrWahl) ? jahrWahl : year;

  const bereiche = useMemo(() => teilhaushalte(daten, effJahr), [daten, effJahr]);
  const treffer = useMemo(() => suche(daten, effJahr, wort), [daten, effJahr, wort]);
  const gesamt = gesamtJahr(daten, effJahr);
  const alleAnzahl = daten?.massnahmen.length ?? 0;

  const nameVon = useMemo(() => {
    const zu = new Map<number, string>();
    for (const b of bereiche) zu.set(b.thh_nr, b.bezeichnung);
    return (nr: number) => zu.get(nr) ?? `Teilhaushalt ${nr}`;
  }, [bereiche]);

  // `gewaehlt == null` heißt „alle Teilhaushalte": Der Explorer beginnt mit
  // dem ganzen Programm, nicht mit dem größten Bereich — die Kachelfläche
  // trägt die Übersicht, die Liste kommt erst mit einer Wahl oder der Suche.
  const aktiv = gewaehlt;
  const liste = useMemo(
    () => (aktiv != null ? vorhaben(daten, effJahr, aktiv) : []),
    [daten, effJahr, aktiv]);
  const summe = aktiv != null ? teilhaushaltSumme(daten, effJahr, aktiv) : null;
  const h = herkunftVon(daten, gesamt?.herkunft_id);

  const suchend = wort.trim().length >= 2;

  // Die Kachelfläche: alle Vorhaben des Jahrgangs (oder des gewählten
  // Bereichs), Schlüssel je Vorhaben, Gruppe = Teilhaushalt.
  const knoten: TreemapKnoten[] = useMemo(() => {
    const quelle = aktiv != null
      ? vorhaben(daten, effJahr, aktiv)
      : (daten?.massnahmen ?? []).filter((z) => z.year === effJahr);
    const zuName = (nr: number) => {
      const b = (daten?.teilhaushalte ?? []).find(
        (t) => t.year === effJahr && t.thh_nr === nr);
      return b?.bezeichnung ?? `Teilhaushalt ${nr}`;
    };
    return quelle.map((z) => ({
      key: `${z.thh_nr}-${z.code}`,
      name: z.bezeichnung,
      wert: z.gesamtsumme,
      gruppe: zuName(z.thh_nr),
      zusatz: aktiv == null ? zuName(z.thh_nr) : undefined,
    }));
  }, [daten, effJahr, aktiv]);
  const suchtreffer = useMemo(
    () => (suchend ? new Set(treffer.map((z) => `${z.thh_nr}-${z.code}`)) : undefined),
    [suchend, treffer]);

  const zeigen = useMemo(() => {
    const basis = suchend ? treffer : liste;
    return sortierung === "alpha"
      ? [...basis].sort((a, b) => a.bezeichnung.localeCompare(b.bezeichnung, "de"))
      : basis;
  }, [suchend, treffer, liste, sortierung]);
  // Einmal je Liste, nicht einmal je Zeile: Bei 565 Vorhaben wäre die
  // Berechnung im map() ein Quadrat.
  const massstab = zeigen.length
    ? Math.max(...zeigen.map((z) => z.gesamtsumme), 0)
    : 0;

  if (!bereiche.length) return null;

  return (
    <section
      id="vorhaben"
      className="rounded-2xl border border-border bg-card p-4 shadow-sm sm:p-5"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <h2 className="font-display text-[15.5px] font-bold tracking-tight">
          {alleAnzahl.toLocaleString("de-DE")} Vorhaben, durchsuchbar
        </h2>
        <span className="font-mono text-[9.5px] uppercase tracking-[0.11em] text-muted-foreground">
          Investitionsprogramm {jahre[0]}–{jahre[jahre.length - 1]}
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
          ref={suchfeld}
          type="search"
          value={wort}
          onChange={(e) => setWort(e.target.value)}
          placeholder={`In allen Vorhaben ${effJahr} suchen — „Kunstrasen“, „Feuerwehr“ …`}
          className="min-w-0 flex-1 bg-transparent text-[12.5px] outline-none placeholder:text-muted-foreground"
        />
      </label>

      {/* DER SCHULGEBÄUDE-KASTEN — VOR den Ergebnissen (H4-06): Er
          beantwortet die häufigste Suchabsicht, bevor jemand vergeblich
          sucht. Eine Grenze des Datensatzes, deshalb der gestrichelte Rand
          (Reichweiten-Konvention), kein Alarm. */}
      <div className="mt-3 rounded-xl border border-dashed border-border bg-muted/25 p-3">
        <p className="text-[12px] font-semibold leading-snug">Wo sind die Schulen?</p>
        <p className="mt-1 max-w-[86ch] text-[12px] leading-relaxed text-muted-foreground">
          Schul-Neubau und -Sanierung laufen beim Eigenbetrieb Gebäudewirtschaft
          und Hochbau — außerhalb dieses Programms, mit eigenem Wirtschaftsplan.
          Hier stehen für Schulen nur Ausstattungs-Kategorien und die
          berufsbildenden Schulen. Was der Rat zu einer bestimmten Schule
          beschlossen hat, findest du über die{" "}
          <Link href="/suche" className="font-semibold text-primary hover:underline">
            Suche
          </Link>{" "}
          in den Beschlüssen.
        </p>
      </div>

      {/* Die Filterzeile (H4-06): Jahrgang, Teilhaushalt, Sortierung. Native
          Selects statt eines Filter-Sheets — sie sind auf jedem Gerät und mit
          der Tastatur bedienbar, und drei Filter rechtfertigen kein Sheet. */}
      <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-2">
        {jahre.length > 1 && (
          <label className="flex items-center gap-1.5 text-[11.5px] text-muted-foreground">
            Jahrgang
            <select
              value={effJahr}
              onChange={(e) => setJahrWahl(Number(e.target.value))}
              className="rounded-lg border border-border bg-background px-2 py-1.5 text-[12px] text-foreground"
            >
              {jahre.map((j) => (
                <option key={j} value={j}>{j}</option>
              ))}
            </select>
          </label>
        )}
        <label className="flex min-w-0 items-center gap-1.5 text-[11.5px] text-muted-foreground">
          Bereich
          <select
            value={aktiv ?? ""}
            onChange={(e) => aufWaehlen(e.target.value === "" ? null : Number(e.target.value))}
            className="min-w-0 max-w-[240px] rounded-lg border border-border bg-background px-2 py-1.5 text-[12px] text-foreground"
          >
            <option value="">alle Teilhaushalte</option>
            {bereiche.map((b) => (
              <option key={b.thh_nr} value={b.thh_nr}>
                {b.bezeichnung} ({anzahl(daten, effJahr, b.thh_nr)})
              </option>
            ))}
          </select>
        </label>
        <label className="flex items-center gap-1.5 text-[11.5px] text-muted-foreground">
          Sortierung
          <select
            value={sortierung}
            onChange={(e) => setSortierung(e.target.value as Sortierung)}
            className="rounded-lg border border-border bg-background px-2 py-1.5 text-[12px] text-foreground"
          >
            <option value="gesamtsumme">Gesamtsumme</option>
            <option value="alpha">A–Z</option>
          </select>
        </label>
      </div>

      {/* Die Kachelfläche (GB-08): Fläche = Gesamtsumme, Farbe = Teilhaushalt,
          Suchtreffer per Umriss. Mobil rendert die Komponente stattdessen die
          Rangliste mit Schiene — gleiche Daten, gleiche Sortierung. */}
      <div className="mt-3.5">
        <Treemap
          knoten={knoten}
          farbe={(gruppe) => {
            const nr = bereiche.find((b) => b.bezeichnung === gruppe)?.thh_nr;
            return nr != null ? farbeVonThh(nr) : "var(--hh-aus-9)";
          }}
          // Bis 24.08. stand auf JEDER Kachel weißer Text. Am blassen Ende der
          // Ausgaben-Rampe (Stufe 3 aufwärts) war er damit unlesbar bis
          // unsichtbar — „Krippenausbau 2022" auf `--hh-aus-8` hielt 1,25 : 1.
          textFarbe={(gruppe) => {
            const nr = bereiche.find((b) => b.bezeichnung === gruppe)?.thh_nr;
            return rampenText("aus", nr != null ? stufeVonThh(nr) : 9);
          }}
          buendelnAb={12}
          treffer={suchtreffer}
          aufRest={() => suchfeld.current?.focus()}
          restHinweis="Die Masse der kleinen ist selbst eine Größe — ab hier übernimmt die Suche."
        />
      </div>

      {suchend ? (
        <p className="mt-3.5 text-[12px] text-muted-foreground">
          {treffer.length === 0
            ? `Kein Vorhaben ${effJahr} enthält „${wort.trim()}“.`
            : `${treffer.length} Vorhaben ${effJahr} — über alle Bereiche.`}
        </p>
      ) : summe && aktiv != null ? (
        // Die Summe des Bereichs steht als Zahl DES DOKUMENTS da, nicht als
        // unsere Addition der Liste darunter (die ergäbe dieselbe Zahl ein
        // zweites Mal — s. Kopf von lib/haushalt-investitionsprogramm.ts).
        <p className="mt-3.5 text-[12px] text-muted-foreground">
          {liste.length} Vorhaben · das Programm weist für „{nameVon(aktiv)}“{" "}
          <span className="font-semibold tabular-nums text-foreground">
            {betrag(summe.gesamtsumme).wert} {betrag(summe.gesamtsumme).einheit}
          </span>{" "}
          aus.<Beleg q="investitionsprogramm" />
        </p>
      ) : (
        <p className="mt-3.5 text-[12px] text-muted-foreground">
          Einen Bereich wählen oder suchen — dann stehen hier die einzelnen
          Vorhaben als Liste.
        </p>
      )}

      {/* Die Liste: Suchtreffer über alle Bereiche, sonst der gewählte
          Bereich. Ohne Wahl KEINE Liste — 4.459 Zeilen liest niemand, dafür
          sind Kachelfläche und Suche da. */}
      {(suchend || aktiv != null) && (
        <ul className="mt-1 divide-y divide-[color:var(--border)]">
          {zeigen.map((z) => (
            <Zeile
              key={`${z.thh_nr}-${z.code}`} zeile={z} skala={massstab}
              bereichName={suchend ? nameVon(z.thh_nr) : undefined}
            />
          ))}
        </ul>
      )}

      {/* DER PLANZAHLEN-KASTEN (H4-06): keine Beschlüsse, und absichtlich
          nicht dieselbe Summe wie der Finanzhaushalt darüber. */}
      <div className="mt-4 rounded-xl border border-dashed border-border bg-muted/25 p-3">
        <p className="text-[12px] font-semibold leading-snug">
          Planzahlen, keine Beschlüsse
        </p>
        <p className="mt-1 max-w-[86ch] text-[12px] leading-relaxed text-muted-foreground">
          Die Zahlen stammen aus dem Verwaltungsentwurf zum Zeitpunkt der Einbringung
          in den Rat. Spätere Änderungen aus den politischen Beratungen sind darin
          nicht enthalten; diese findest du unter{" "}
          <Link href="/haushalt/mitreden#streit" className="font-semibold text-primary hover:underline">
            Der Streit ums Geld
          </Link>{" "}
          . Die Summen stimmen nicht mit dem Finanzhaushalt weiter oben überein,
          weil das Investitionsprogramm auch aktivierbare Eigenleistungen enthält,
          für die kein Geld ausgezahlt wird. Angegeben ist je Vorhaben, was es{" "}
          <strong className="font-semibold text-foreground/85">insgesamt</strong>{" "}
          kosten soll — über alle Jahre, nicht nur {effJahr}; die
          Jahresaufteilung lässt sich aus dem Dokument nicht verlässlich
          auslesen, deshalb zeigen wir sie nicht.
        </p>
      </div>

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
