"use client";

// „Was kostet eigentlich …?" — der ZWEITE Abschnitt von /haushalt/produkte.
//
// Bis zum 21.08.2026 die eigene Seite. Siehe den Kopf von
// `section-bereiche.tsx`.

// /haushalt/produkte — „Was kostet eigentlich …?"
//
// Die häufigste Bürgerfrage zum Haushalt ist keine nach Teilhaushalten,
// sondern nach einer konkreten Sache: das Stadtarchiv, die Feuerwehr, das
// Schwimmbad. Die Produktebene beantwortet genau das — und die Steckbriefe
// der Teilhaushaltspläne liefern dazu, was die Aufgabe umfasst, worauf sie
// beruht und wie viel Spielraum die Stadt bei ihr sieht.
//
// Zwei Dinge, die diese Seite NICHT tut:
// - Sie färbt nichts ein. Ein teures Produkt ist nicht schlecht, ein Produkt
//   ohne Spielraum nicht verdächtig (Designsprache: keine Bewertungsfarben im
//   Haushalt).
// - Sie reicht kein Verwaltungsdeutsch ungefiltert durch. „übertragender
//   Wirkungskreis" bekommt eine Erklärung (Glossar), „Grad der
//   Beeinflussbarkeit: niedrig" wird zu einem Satz, den man lesen kann.
//
// Query-Param statt dynamischem Segment (?nr=P10.111023): Der Capacitor-Export
// (output: export) kennt die Produktnummern zur Bauzeit nicht — dieselbe
// Konvention wie /haushalt/bereich?name= und /haushalt/steuer?art=.
//
// Gesucht und gefiltert wird SERVERSEITIG: Mit dem Steckbrief trägt jede der
// knapp 400 Zeilen mehrere hundert Zeichen Fließtext.
//
// DREI FELDER DES STECKBRIEFS SIND KEIN FLIESSTEXT (Umbau 17.08., dieselbe
// Einsicht wie beim Beteiligungs-Steckbrief):
//
//  * **„Was dahintersteckt"** ist bei 60 von 507 Produkten eine Aufzählung von
//    Leistungen — der Plan setzt je Zeile eine, beim Auslesen wird daraus ein
//    Absatz voller „ - " (bis 1.776 Zeichen ohne einen Umbruch, Klimaschutz
//    und Friedhöfe). Sie steht wieder als Liste. Bleibt der Text Prosa und ist
//    er länger als 420 Zeichen, ist bis zum ersten Satzende zu sehen und der
//    Rest hinter einem Auslöser: Gekürzt wird die DARSTELLUNG, nie der
//    Wortlaut (H4-A).
//  * **„Für wen"** ist dieselbe Aufzählung in klein und wird ebenso zerlegt —
//    hier NUR am Spiegelstrich, weil die Kommas innerhalb der Glieder stehen
//    („Privathaushalte, -personen").
//  * **„Worauf die Aufgabe beruht"** zählt Gesetze und Satzungen auf, getrennt
//    durch Komma, Semikolon oder Spiegelstrich; 278 von 515 Einträgen lassen
//    sich verlustfrei zerlegen und stehen als Liste.
//
// Getrennt wird immer nur an Zeichen, die die Quelle selbst setzt, und nie
// innerhalb von Klammern („EU-Richtlinien (FFH, WRRL, VRL)" bleibt eins).
// Scheitert eine der Proben — zu wenige Glieder, ein Glied über 130 Zeichen,
// oder bloße Paragraphen-Nummern wie „§§ 2 (3),17,18,42 …" —, bleibt der
// Absatz, wie er ist. Geraten wird nichts, und kein Wort ändert sich.

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import {
  Check, ChevronDown, ChevronRight, Building2, Scale, Search, X,
} from "lucide-react";
import { useFetch } from "@/lib/use-fetch";
import {
  HaushaltAuswahl, haushaltUrl, Produkt, ProdukteAntwort, SPIELRAUM_TEXT, Spielraum,
  bereichSlug, amount,
} from "@/lib/haushalt";
import type { QuellenSchluessel } from "@/lib/haushalt-quellen";
import { Beleg } from "@/components/haushalt/quelle";
import { LottiErklaert } from "@/components/haushalt/lotti-erklaert";
import { GlossaryText } from "@/components/glossary-text";
import { cn } from "@/lib/utils";

const STUFEN: Spielraum[] = ["niedrig", "mittel", "hoch"];

/** Zuschussbedarf in Euro — was das Produkt die Stadt unterm Strich kostet.
 *  `result` ist negativ, wenn es zuschussbedürftig ist. */
function netto(p: Produkt): number {
  return -(p.result ?? 0);
}

/** Aufeinanderfolgende Jahre zu Spannen bündeln: [2019, 2020, 2022] →
 *  „2019–2020, 2022". */
function jahresspannen(years: number[]): string {
  const sortiert = [...years].sort((a, b) => a - b);
  const teile: string[] = [];
  let von = sortiert[0], bis = sortiert[0];
  for (const j of sortiert.slice(1)) {
    if (j === bis + 1) { bis = j; continue; }
    teile.push(von === bis ? String(von) : `${von}–${bis}`);
    von = bis = j;
  }
  if (von != null) teile.push(von === bis ? String(von) : `${von}–${bis}`);
  return teile.join(", ");
}

/** Abdeckungs-Badge (H4-04): Nicht jedes Jahr deckt jeden Teilhaushalt —
 *  ein Produkt, das erst ab 2021 vorliegt, sagt das, statt wie eine
 *  durchgehende Reihe auszusehen.
 *
 *  Vollständige Abdeckung ist die unauffällige Auskunft und verschwindet in
 *  der Trefferliste auf schmalen Karten (`knapp`); die LÜCKE bleibt immer
 *  sichtbar — Lücken zeigen geht vor (H4-A). Kein Signal-Orange: Eine Lücke
 *  im Bestand ist die Lücken-Konvention (gestrichelt), keine Abweichung des
 *  Produkts. */
function AbdeckungsBadge({ years, alle, knapp }: {
  years?: number[]; alle: number[]; knapp?: boolean;
}) {
  // Mit nur einem Jahrgang im Bestand gäbe es nichts abzudecken.
  if (!years?.length || alle.length < 2) return null;
  const fehlt = alle.filter((j) => !years.includes(j));
  if (!fehlt.length) {
    return (
      <span className={cn(
        "items-center gap-1 rounded border border-border px-1.5 py-0.5 font-mono text-[9.5px] font-medium uppercase tracking-[0.08em] text-muted-foreground",
        knapp ? "hidden @2xl/treffer:inline-flex" : "inline-flex",
      )}>
        <Check aria-hidden className="h-3 w-3" />
        {Math.min(...alle)}–{Math.max(...alle)}
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 rounded border border-dashed border-border px-1.5 py-0.5 font-mono text-[9.5px] font-medium uppercase tracking-[0.08em] text-muted-foreground">
      ohne {jahresspannen(fehlt)}
    </span>
  );
}

/** Bigramme eines Suchbegriffs — der „Ähnlich klingen"-Vergleich des
 *  Leerzustands. Bewusst reine Zeichenähnlichkeit (Dice über Bigramme),
 *  keine Semantik: Für „Feuerwer" findet sie die Feuerwehr, für „Zoo"
 *  findet sie ehrlich nichts — dann bleibt der Satz, dass Produkte wie im
 *  Haushaltsplan heißen. */
function bigramme(s: string): Set<string> {
  const out = new Set<string>();
  for (const wort of s.toLowerCase().replace(/[^a-zäöüß0-9]+/g, " ").trim().split(/\s+/)) {
    for (let i = 0; i < wort.length - 1; i++) out.add(wort.slice(i, i + 2));
  }
  return out;
}

function aehnlichkeit(a: Set<string>, b: Set<string>): number {
  if (!a.size || !b.size) return 0;
  let gemeinsam = 0;
  for (const g of a) if (b.has(g)) gemeinsam += 1;
  return (2 * gemeinsam) / (a.size + b.size);
}

/** Eine Zeile der Trefferliste. Der Balken zeigt den Anteil am teuersten
 *  Treffer — Hafenblau, nicht Ampelfarben: teuer ist keine Note. */
function Treffer({ p, max, aktiv, alleJahre, eingebettet = false }: {
  p: Produkt; max: number; aktiv: boolean; alleJahre: number[];
  /** Sitzt die Karte im gemeinsamen Rahmen mit ihrem Steckbrief? Dann bringt
   *  sie keinen eigenen mit — sonst stünden zwei Kästen ineinander. */
  eingebettet?: boolean;
}) {
  const n = netto(p);
  const b = amount(Math.abs(n));
  return (
    <Link
      href={`/haushalt/produkte?nr=${encodeURIComponent(p.product_no)}`}
      // `scroll={false}`: Ein Produkt zu öffnen ist kein Seitenwechsel — es
      // ändert nur `?nr=`. Mit dem Vorgabeverhalten sprang der Browser an den
      // Anfang der Seite, und wer in einer Liste von 400 Zeilen weit unten
      // gesucht hatte, fand sich oben wieder und musste alles wiederfinden
      // (Tims Befund 18.08.2026). Gescrollt wird jetzt gar nicht mehr: Der
      // Steckbrief klappt direkt unter dieser Karte auf (`SteckbriefKarte`).
      scroll={false}
      className={cn(
        // `min-w-0`: Ein Rasterkind ist von Haus aus `min-width: auto` und
        // damit so breit wie sein längster Produktname — auf 375 px schob die
        // Karte die ganze Seite 64 px nach rechts. Erst damit greift das
        // `truncate` der Zeilen darin.
        "group block min-w-0 p-3 transition-colors",
        // Eingebettet trägt den Rahmen die Hülle drumherum — die Karte ist
        // dann der KOPF einer geöffneten Karte und kein Kasten für sich.
        eingebettet
          ? "rounded-t-xl"
          : cn("rounded-xl border border-border bg-card shadow-sm hover:border-primary/40",
               aktiv && "border-primary/50 bg-primary/[0.04]"),
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <p className="truncate text-[13.5px] font-semibold leading-snug">{p.product_name}</p>
          <p className="mt-0.5 truncate font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
            {p.product_no}{p.office ? ` · ${p.office}` : ""}
          </p>
        </div>
        <span className="flex-none text-right">
          <span className="block font-display text-[15px] font-bold leading-none tabular-nums">
            {n < 0 && "+"}{b.wert}
          </span>
          <span className="mt-0.5 block font-mono text-[9.5px] uppercase text-muted-foreground">
            {b.unit}
          </span>
        </span>
      </div>
      <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-muted">
        <div className="h-full rounded-full bg-primary/60"
          style={{ width: `${Math.max((Math.abs(n) / max) * 100, 1.5)}%` }} />
      </div>
      {(p.controllability || (p.years && alleJahre.length > 1)) && (
        <p className="mt-2 flex flex-wrap items-center justify-between gap-x-3 gap-y-1 text-[11.5px] text-muted-foreground">
          <span>
            {p.controllability && (
              <>Spielraum der Stadt: <span className="font-semibold text-foreground/80">
                {SPIELRAUM_TEXT[p.controllability].kurz}
              </span></>
            )}
          </span>
          <AbdeckungsBadge years={p.years} alle={alleJahre} knapp />
        </p>
      )}
    </Link>
  );
}

/** Die Vorschau einer Produktbeschreibung: bis zu einem SATZENDE, nie mitten
 *  im Satz.
 *
 *  Bewusst nicht `absatzVorschau` aus dem Beteiligungs-Steckbrief: Die schneidet
 *  notfalls am letzten Leerzeichen vor der Grenze, weil die Berichtstexte dort
 *  Zeilenumbrüche mitbringen. Produktbeschreibungen haben keine — der Schnitt
 *  landete bei „…des zusammenhängenden europäischen ökologischen Netzes" und
 *  las sich wie ein abgerissener Text. Hier gilt: das letzte Satzende vor der
 *  Grenze, sonst das erste danach, und wenn keins in Reichweite liegt, bleibt
 *  der ganze Absatz stehen. */
function satzVorschau(text: string, grenze = 420): { kopf: string; rest: string } {
  const glatt = text.replace(/\s+/g, " ").trim();
  if (glatt.length <= grenze) return { kopf: glatt, rest: "" };
  // Satzenden: Punkt/Ausrufe-/Fragezeichen, dem ein Großbuchstabe folgt.
  const enden: number[] = [];
  const suche = /[.!?]\s+(?=[A-ZÄÖÜ„])/g;
  for (let t = suche.exec(glatt); t; t = suche.exec(glatt)) enden.push(t.index + 1);
  const davor = [...enden].reverse().find((i) => i <= grenze && i >= grenze * 0.35);
  const danach = enden.find((i) => i > grenze && i <= grenze * 1.6);
  const schnitt = davor ?? danach;
  if (schnitt == null) return { kopf: glatt, rest: "" };
  return { kopf: glatt.slice(0, schnitt).trim(), rest: glatt.slice(schnitt).trim() };
}

/** Die Glieder einer Rechtsgrundlagen-Aufzählung — oder `null`, wenn der Text
 *  keine ist.
 *
 *  Getrennt wird an Komma, Semikolon und freistehendem Gedankenstrich —
 *  jeweils AUSSERHALB von Klammern: „EU-Richtlinien (FFH, WRRL, VRL)" bleibt
 *  ein Glied, und „-personen" oder „-eigentümer" trennt nichts, weil der
 *  Strich dort direkt am Wort klebt. Danach drei Proben, und jede darf die
 *  Zerlegung verwerfen — im Zweifel bleibt der Absatz stehen:
 *
 *   1. mindestens drei Glieder (zwei sind keine Liste, sondern ein Satz),
 *   2. kein Glied länger als 130 Zeichen (dann ist es Prosa mit Kommas —
 *      „Ratsbeschluss … vom 26.04.2021 - Ratsbeschluss Klimaschutz …"),
 *   3. mindestens vier Fünftel der Glieder enthalten ein Wort aus vier
 *      Buchstaben. Das fängt die Paragraphen-Ketten ab („§§ 2 (3),17,18,42,
 *      50,52a,55-60,1630 …"), die als 20 Einzelzeilen unlesbar wären. */
function rechtsgrundlagen(text: string): string[] | null {
  const glatt = text.replace(/\s+/g, " ").trim();
  const glieder: string[] = [];
  let tiefe = 0, akt = "";
  for (let i = 0; i < glatt.length; i += 1) {
    const z = glatt[i];
    if (z === "(") tiefe += 1;
    else if (z === ")") tiefe = Math.max(0, tiefe - 1);
    // Ein Gedankenstrich trennt nur mit Leerzeichen auf BEIDEN Seiten.
    const strich = /[-–—]/.test(z) && glatt[i - 1] === " " && glatt[i + 1] === " ";
    if ((z === "," || z === ";" || strich) && tiefe === 0) {
      glieder.push(akt.trim()); akt = "";
    } else akt += z;
  }
  if (akt.trim()) glieder.push(akt.trim());
  const teile = glieder.filter(Boolean);
  if (teile.length < 3) return null;
  if (teile.some((t) => t.length > 130)) return null;
  const mitWort = teile.filter((t) => /[A-Za-zÄÖÜäöüß]{4,}/.test(t)).length;
  if (mitWort < teile.length * 0.8) return null;
  return teile;
}

/** Eine Produktbeschreibung ist bei 60 von 507 Produkten in Wahrheit eine
 *  AUFZÄHLUNG: Der Plan setzt je Leistung eine Zeile mit Spiegelstrich, beim
 *  Auslesen wird daraus ein Absatz voller „ - ". Wo das erkennbar ist —
 *  mindestens zwei Spiegelstriche, jedes Glied mit Inhalt —, steht sie als
 *  Liste; sonst bleibt sie ein Absatz. Der Wortlaut ändert sich in keinem
 *  Fall, nur der Zeilenumbruch kommt zurück. */
function beschreibungsTeile(text: string): { einleitung: string; punkte: string[] } | null {
  const glatt = text.replace(/\s+/g, " ").trim();
  const trenner = /\s[-–—•]\s/g;
  const stellen = [...glatt.matchAll(trenner)];
  if (stellen.length < 2) return null;
  const erst = stellen[0].index ?? 0;
  const punkte = glatt.slice(erst).split(trenner).map((s) => s.trim()).filter(Boolean);
  if (punkte.length < 2 || punkte.some((p) => p.length < 8)) return null;
  return { einleitung: glatt.slice(0, erst).trim(), punkte };
}

/** „Was dahintersteckt" — Liste, wo eine ist, sonst Prosa mit Auslöser
 *  (dieselbe Form wie im Beteiligungs-Steckbrief). */
function Dahinter({ text, target_group }: { text: string; target_group?: string | null }) {
  const [offen, setOffen] = useState(false);
  const liste = useMemo(() => beschreibungsTeile(text), [text]);
  const { kopf, rest } = useMemo(() => satzVorschau(text), [text]);

  return (
    <div className="@container/steckbrief rounded-2xl border border-border bg-card p-4 shadow-sm">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
          Was dahintersteckt
        </p>
        {liste && (
          <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-muted-foreground">
            {liste.punkte.length} Leistungen
          </span>
        )}
      </div>

      {liste ? (
        <>
          {liste.einleitung && (
            <p className="mt-2 max-w-[70ch] text-[13.5px] leading-relaxed text-foreground/90">
              <GlossaryText text={liste.einleitung} />
            </p>
          )}
          {/* `text-[13px]` an der Liste, obwohl jedes `li` seine Größe selbst
              setzt: `ch` misst die Schrift SEINES Elements. Ohne die Angabe maß
              der Deckel die geerbten 16 px, und `74ch` waren 747 px statt 607 —
              114 Zeichen je Zeile statt 93 (DESIGNSPRACHE § 4).
              Zwei Spalten, sobald der Steckbrief Platz hat: Die Leistungsliste
              ist der Hauptinhalt dieser Karte, nicht ein Absatz neben einem
              Bild — hier ist der Deckel allein zu wenig. */}
          <ul className="mt-2 grid max-w-[74ch] grid-cols-1 gap-x-8 gap-y-1.5 text-[13px] @3xl/steckbrief:max-w-none @3xl/steckbrief:grid-cols-2">
            {liste.punkte.map((punkt, i) => (
              <li key={`${punkt.slice(0, 24)}-${i}`}
                className="flex items-baseline gap-2 text-[13px] leading-relaxed text-foreground/90">
                <span aria-hidden
                  className="mt-[6px] h-1 w-1 flex-none rounded-full bg-muted-foreground/60" />
                <span className="min-w-0"><GlossaryText text={punkt} /></span>
              </li>
            ))}
          </ul>
        </>
      ) : (
        <>
          <p className="mt-2 max-w-[70ch] text-[13.5px] leading-relaxed text-foreground/90">
            <GlossaryText text={kopf} />
          </p>
          {rest && (
            <>
              {offen && (
                <p className="mt-2 max-w-[70ch] text-[13.5px] leading-relaxed text-foreground/90">
                  <GlossaryText text={rest} />
                </p>
              )}
              <button type="button" onClick={() => setOffen(!offen)} aria-expanded={offen}
                className="mt-2 inline-flex min-h-[36px] items-center gap-1 text-[12.5px] font-semibold text-primary">
                {offen ? "Wortlaut einklappen" : "Ganzen Wortlaut zeigen"}
                <ChevronDown size={14} strokeWidth={2}
                  className={cn("transition-transform", offen && "rotate-180")} />
              </button>
            </>
          )}
        </>
      )}

      {target_group && <FuerWen text={target_group} />}
    </div>
  );
}

/** „Für wen": bei den großen Produkten dieselbe Aufzählung in Absatzform —
 *  „… unter anderem als: - Stadtverwaltung … - Privathaushalte, -personen
 *  - Mieterinnen und Mieter …". Als eine Zeile gelesen wirkt das wie ein Satz,
 *  der nicht aufhört.
 *
 *  Getrennt wird hier NUR am Spiegelstrich, nicht am Komma: Die Kommas stehen
 *  INNERHALB der Glieder („Privathaushalte, -personen"). Deshalb dieselbe
 *  Zerlegung wie bei der Beschreibung — kein Chip-Feld: ein Glied kann
 *  130 Zeichen lang sein, und das ist kein Chip mehr. */
function FuerWen({ text }: { text: string }) {
  const liste = useMemo(() => beschreibungsTeile(text), [text]);
  return (
    <div className="mt-3 border-t border-border/60 pt-2.5">
      <p className="font-mono text-[9.5px] font-medium uppercase tracking-[0.1em] text-muted-foreground">
        Für wen
      </p>
      {liste ? (
        <>
          {liste.einleitung && (
            <p className="mt-1 max-w-[74ch] text-[12.5px] leading-relaxed text-muted-foreground">
              <GlossaryText text={liste.einleitung} />
            </p>
          )}
          <ul className="mt-1.5 grid gap-x-6 gap-y-1 @2xl/steckbrief:grid-cols-2">
            {liste.punkte.map((g, i) => (
              <li key={`${g.slice(0, 24)}-${i}`}
                className="flex min-w-0 items-baseline gap-2 text-[12.5px] leading-snug text-muted-foreground">
                <span aria-hidden
                  className="mt-[3px] h-1 w-1 flex-none rounded-full bg-muted-foreground/60" />
                <span className="min-w-0"><GlossaryText text={g} /></span>
              </li>
            ))}
          </ul>
        </>
      ) : (
        <p className="mt-1 max-w-[74ch] text-[12.5px] leading-relaxed text-muted-foreground">
          <GlossaryText text={text} />
        </p>
      )}
    </div>
  );
}

/** Der Steckbrief eines Produkts — Kosten, Zuständigkeit, was drinsteckt,
 *  worauf es beruht, wie viel Spielraum. Fehlende Felder bleiben weg; eine
 *  Lücke wird nicht mit einer Vermutung gefüllt. */
function Steckbrief({ p, year, alleJahre }: { p: Produkt; year: number; alleJahre: number[] }) {
  const n = netto(p);
  const gross = amount(Math.abs(n));
  const aus = amount(p.expenses ?? 0);
  const ein = amount(p.revenues ?? 0);
  const spielraum = p.controllability ? SPIELRAUM_TEXT[p.controllability] : null;

  return (
    <div className="flex flex-col gap-4">
      <div>
        <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
          {p.product_no} · Haushaltsjahr {year}
        </p>
        <h2 className="mt-1 font-display text-[22px] font-bold leading-tight tracking-tight sm:text-2xl">
          {p.product_name}
        </h2>
        <div className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-[12px] text-muted-foreground">
          {p.office && (
            <span className="inline-flex items-center gap-1.5">
              <Building2 className="h-3.5 w-3.5" />{p.office}
            </span>
          )}
          {p.sub_budget_name && (
            <>
              <span aria-hidden>·</span>
              <Link href={`/haushalt/bereich?name=${bereichSlug(p.sub_budget_name)}`}
                className="font-semibold text-primary hover:underline">
                {p.sub_budget_name}
              </Link>
            </>
          )}
        </div>
      </div>

      {/* Kosten. Keine Bewertungsfarbe — der Betrag steht für sich. */}
      <div className="rounded-2xl border border-border bg-card p-4 shadow-sm">
        <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
          Was es die Stadt kostet
        </p>
        <p className="mt-1.5 font-display text-[30px] font-bold leading-none tracking-tight tabular-nums">
          {n < 0 && "+"}{gross.wert}
          <span className="text-base font-semibold text-muted-foreground">&#8239;{gross.unit}</span>
          <Beleg q="teilhaushalt" />
        </p>
        <p className="mt-2 max-w-[62ch] text-[12.5px] leading-relaxed text-foreground/85">
          {n > 0 ? (
            <>Für {year} sind <strong>{aus.wert}&#8239;{aus.unit}</strong> Aufwendungen
              geplant. Dem stehen <strong>{ein.wert}&#8239;{ein.unit}</strong> eigene
              Erträge gegenüber, etwa Gebühren oder Erstattungen. Den verbleibenden
              Zuschussbedarf finanziert der allgemeine Haushalt.</>
          ) : (
            <>Bei diesem Produkt übersteigen die geplanten eigenen Erträge von{" "}
              <strong>{ein.wert}&#8239;{ein.unit}</strong> die geplanten Aufwendungen
              von {aus.wert}&#8239;{aus.unit}.</>
          )}
        </p>
        {/* Zwei Ehrlichkeits-Zeilen, auf jedem Gerät (H4-04): Ist-Zahlen gibt
            es je Produkt NICHT — und wie weit das Produkt im Bestand
            zurückreicht, steht als Abdeckung dabei (in der Trefferliste
            trägt das nur der Lücken-Fall, hier immer). */}
        <p className="mt-2 border-t border-border/60 pt-2 text-[11.5px] leading-relaxed text-muted-foreground">
          Planzahlen: Was die Aufgabe tatsächlich gekostet hat, weist der Haushalt auf
          Produktebene nicht aus.
          {p.years && p.years.length > 0 && alleJahre.length > 1 && (() => {
            const fehlt = alleJahre.filter((j) => !p.years!.includes(j));
            return (
              <> Im Bestand liegt das Produkt für {jahresspannen(p.years)}
                {fehlt.length > 0 && <> — ohne {jahresspannen(fehlt)}, dort liegt der
                  Teilhaushaltsplan nicht auslesbar vor</>}.</>
            );
          })()}
        </p>
      </div>

      {p.short_description && (
        <Dahinter text={p.short_description} target_group={p.target_group} />
      )}

      {(spielraum || p.controllability_raw || p.scope) && (
        <div className="rounded-2xl border border-primary/20 bg-card p-4 shadow-sm">
          <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-primary">
            Wie viel Spielraum die Stadt hat
          </p>
          {spielraum ? (
            <>
              {/* Die Stufen als Skala, nicht als Ampel: gefüllt = diese Stufe.
                  Hafenblau, weil „kaum Spielraum" kein Missstand ist. */}
              <div className="mt-2.5 flex items-center gap-1.5" aria-hidden>
                {STUFEN.map((s) => (
                  <span key={s} className={cn(
                    "h-1.5 flex-1 rounded-full",
                    s === p.controllability ? "bg-primary" : "bg-muted",
                  )} />
                ))}
              </div>
              <p className="mt-2 text-[13.5px] font-semibold">{spielraum.kurz}</p>
              <p className="mt-1 max-w-[68ch] text-[12.5px] leading-relaxed text-foreground/85">
                {spielraum.lang}
              </p>
            </>
          ) : p.controllability_raw ? (
            <p className="mt-2 max-w-[68ch] text-[12.5px] leading-relaxed text-foreground/85">
              Der Plan gibt hier keine der drei Stufen an, sondern schreibt:{" "}
              <em>„{p.controllability_raw}"</em>. Diese Formulierung lässt sich keiner
              der drei Stufen eindeutig zuordnen.
            </p>
          ) : null}
          <p className="mt-2.5 border-t border-border/60 pt-2.5 text-[11.5px] leading-relaxed text-muted-foreground">
            Selbstauskunft der Stadt aus dem Teilhaushaltsplan
            {p.controllability && p.controllability_raw
              && p.controllability_raw.toLowerCase() !== p.controllability
              && <> (dort im Wortlaut „{p.controllability_raw}“)</>}
            {" "}— keine Bewertung von uns.<Beleg q="teilhaushalt" />
          </p>
          {p.scope && (
            <p className="mt-2 text-[12.5px] leading-relaxed text-foreground/85">
              <span className="font-semibold">Wirkungskreis: </span>
              <GlossaryText text={p.scope} />
            </p>
          )}
        </div>
      )}

      {p.legal_basis && (() => {
        const glieder = rechtsgrundlagen(p.legal_basis);
        return (
          <div className="@container/grundlage rounded-2xl border border-border bg-card p-4 shadow-sm">
            <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
              <p className="flex items-center gap-1.5 font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
                <Scale className="h-3.5 w-3.5" /> Worauf die Aufgabe beruht
              </p>
              {glieder && (
                <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-muted-foreground">
                  {glieder.length} Grundlagen
                </span>
              )}
            </div>
            {glieder ? (
              /* Zwei bis drei Spalten, wo der Platz da ist: Eine einspaltige
                 Liste aus 16 kurzen Zeilen ließe auf 1440 px rechts einen
                 Meter frei und wäre trotzdem länger als der Absatz vorher. */
              <ul className="mt-2.5 grid gap-x-6 gap-y-1.5 @2xl/grundlage:grid-cols-2 @5xl/grundlage:grid-cols-3">
                {glieder.map((g, i) => (
                  <li key={`${g}-${i}`}
                    className="flex min-w-0 items-baseline gap-2 text-[12.5px] leading-snug text-foreground/90">
                    <span aria-hidden
                      className="mt-[3px] h-1 w-1 flex-none rounded-full bg-muted-foreground/60" />
                    <span className="min-w-0">{g}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-2 max-w-[70ch] text-[13px] leading-relaxed text-foreground/90">
                {p.legal_basis}
              </p>
            )}
            <p className="mt-2.5 max-w-[70ch] border-t border-border/60 pt-2.5 text-[11.5px] leading-relaxed text-muted-foreground">
              Im Wortlaut des Teilhaushaltsplans — Gesetze, Satzungen und Verträge, aus denen
              sich die Aufgabe ergibt{glieder && <>; der Plan zählt sie in einer Zeile auf,
              hier steht je Eintrag eine Zeile</>}.<Beleg q="teilhaushalt" />
            </p>
          </div>
        );
      })()}

      <div className="rounded-2xl border border-dashed border-border bg-card p-4">
        <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
          Weiterlesen
        </p>
        <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1.5 text-[12.5px] font-semibold text-primary">
          <Link href={`/council?q=${encodeURIComponent(p.product_name.split(",")[0])}`}
            className="inline-flex items-center gap-1.5">
            <Search className="h-3.5 w-3.5" /> Beschlüsse dazu suchen
          </Link>
          {p.sub_budget_name && (
            <Link href={`/haushalt/bereich?name=${bereichSlug(p.sub_budget_name)}`}>
              Bereich „{p.sub_budget_name}“ ansehen →
            </Link>
          )}
        </div>
      </div>
    </div>
  );
}

/** Der aufgeklappte Teil einer Produktkarte — Kosten, Zuständigkeit, Wortlaut.
 *
 *  EINE KARTE, DIE SICH ÖFFNET, keine zweite darunter. Bis zum 18.08.2026
 *  stand der Steckbrief über der Liste, dann kurz als eigene Karte unter der
 *  angetippten — beides las sich, als sei ein neues Ding aufgetaucht. Jetzt
 *  liegen Kopf und Inhalt in EINER Hülle: derselbe Rahmen, derselbe Ton, eine
 *  Haarlinie dazwischen (Tims Befund 18.08.2026).
 *
 *  KEINE FOKUS-VERWALTUNG, und das ist der Gewinn dieser Anordnung: Weil der
 *  Steckbrief direkt hinter dem Kartenkopf im Dokument steht, liest eine
 *  Vorlesehilfe von selbst dort weiter. Solange er über der Liste hing,
 *  musste jemand den Fokus dorthin schieben — und Next setzt ihn bei jedem
 *  Routenwechsel wieder zurück, auch nach einem `setTimeout(0)`. Gemessen,
 *  dann verworfen. */
function SteckbriefTeil({ aktiv, year, alleJahre, aufSchliessen }: {
  aktiv: Produkt; year: number; alleJahre: number[]; aufSchliessen: () => void;
}) {
  return (
    <section
      aria-label={`Steckbrief ${aktiv.product_name}`}
      className="border-t border-primary/20 p-3.5 sm:p-4"
    >
      <div className="mb-3 flex items-center justify-between gap-3">
        <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-primary">
          Steckbrief
        </p>
        <button
          type="button"
          onClick={aufSchliessen}
          className="inline-flex items-center gap-1 text-[11.5px] font-semibold text-muted-foreground hover:text-foreground"
        >
          <X className="h-3.5 w-3.5" /> Schließen
        </button>
      </div>
      {/* `key`: Der Auslöser „Ganzen Wortlaut zeigen" gehört zu DIESEM
          Produkt — ohne Neuaufbau bliebe er beim Wechsel offen und zeigte
          den halben Text des nächsten. */}
      <Steckbrief key={aktiv.product_no} p={aktiv} year={year} alleJahre={alleJahre} />
    </section>
  );
}

export function ProdukteAbschnitt({ onBestand }: {
  /** Meldet den ungefilterten Bestand des angezeigten Jahres nach oben — die
   *  Seitenbühne im Kopf zeigt dieselbe Zahl wie der Satz dieses Abschnitts,
   *  aus derselben Antwort (H5-02: „gemessen aus denselben Loadern wie der
   *  Fließtext"). Aus den Facetten, nicht aus `treffer`: Die Facetten zählen
   *  das ganze Jahr, egal welcher Filter gerade gesetzt ist. */
  onBestand?: (b: {
    count: number;
    year: number;
    /** Die drei größten Aufgaben nach Zuschussbedarf — fürs Minibild der
     *  Bühne, mit echten Namen statt einer abstrakten Baum-Skizze
     *  (Tim, 26.08.). `wert` ist |netto| in Euro. */
    beispiele: { name: string; wert: number }[];
  } | null) => void;
} = {}) {
  const router = useRouter();
  const params = useSearchParams();
  const nr = params.get("nr") ?? "";


  const [suche, setSuche] = useState("");
  const [entprellt, setEntprellt] = useState("");
  const [office, setAmt] = useState("");
  const [spielraum, setSpielraum] = useState<Spielraum | "">("");

  // Getippt wird schnell, geladen wird langsam: Ohne Entprellung schickt jede
  // Taste eine Anfrage.
  useEffect(() => {
    const t = setTimeout(() => setEntprellt(suche), 250);
    return () => clearTimeout(t);
  }, [suche]);

  const uebersicht = useFetch<HaushaltAuswahl<typeof FELDER[number]>>(haushaltUrl(FELDER));
  // Jüngstes Jahr mit Produktebene. Die Liste kommt aus der Übersicht, damit
  // die Seite kein Jahr rät, das es nicht gibt.
  const year = useMemo(() => {
    const years = uebersicht.data?.product_years ?? [];
    return years.length ? Math.max(...years) : null;
  }, [uebersicht.data]);

  const abfrage = useMemo(() => {
    if (!year) return null;
    const p = new URLSearchParams({ year: String(year) });
    if (entprellt.trim()) p.set("q", entprellt.trim());
    if (office) p.set("office", office);
    if (spielraum) p.set("spielraum", spielraum);
    if (nr) p.set("nr", nr);
    return `/council/haushalt/produkte?${p}`;
  }, [year, entprellt, office, spielraum, nr]);

  const { data, loading } = useFetch<ProdukteAntwort>(abfrage);

  useEffect(() => {
    if (!onBestand) return;
    // `null` = entschieden nichts (kein Jahr, keine Produkte) — die Bühne
    // entfällt dann, statt ewig zu laden.
    if (!uebersicht.loading && year == null) { onBestand(null); return; }
    if (loading || !data || !year) return;
    // Nur der UNGEFILTERTE Stand wird gemeldet: Die Bühne beschreibt die
    // Seite, nicht die gerade getippte Suche — beim Filtern bleibt der
    // zuletzt gemeldete Bestand stehen.
    if (entprellt.trim() || office || spielraum) return;
    const count = (data.facetten?.aemter ?? []).reduce((s, a) => s + a.count, 0);
    const beispiele = [...data.produkte]
      .sort((a, b) => Math.abs(netto(b)) - Math.abs(netto(a)))
      .slice(0, 3)
      .map((pr) => ({ name: pr.product_name, wert: Math.abs(netto(pr)) }));
    onBestand(count > 0 ? { count, year, beispiele } : null);
  }, [onBestand, uebersicht.loading, loading, data, year, entprellt, office, spielraum]);

  // Leerzustand mit „Ähnlich klingen" (H4-04): Erst wenn die gefilterte
  // Suche wirklich leer ist, wird einmal die ungefilterte Liste geholt und
  // nach Zeichenähnlichkeit durchsucht. `useFetch(null)` überspringt — der
  // Hook läuft immer, die Anfrage nur im Leerfall.
  const leer = !loading && data != null && data.produkte.length === 0
    && entprellt.trim().length >= 2 && !office && !spielraum;
  const { data: alleDaten } = useFetch<ProdukteAntwort>(
    leer && year ? `/council/haushalt/produkte?year=${year}` : null);
  const vorschlaege = useMemo(() => {
    if (!leer || !alleDaten) return [];
    const q = bigramme(entprellt);
    return alleDaten.produkte
      .map((p) => ({ p, wert: aehnlichkeit(q, bigramme(p.product_name)) }))
      .filter((x) => x.wert >= 0.25)
      .sort((a, b) => b.wert - a.wert)
      .slice(0, 3)
      .map((x) => x.p);
  }, [leer, alleDaten, entprellt]);

  if (uebersicht.loading || (loading && !data)) {
    return <div className="py-16 text-center text-sm text-muted-foreground">Produkte werden geladen …</div>;
  }
  if (!year) {
    return (
      <div className="py-16 text-center text-sm text-muted-foreground">
        Für kein Jahr liegt die Produktebene ausgelesen vor.{" "}
        <Link href="/haushalt" className="font-semibold text-primary">Zur Übersicht</Link>
      </div>
    );
  }

  const produkte = data?.produkte ?? [];
  const alleJahre = data?.alle_jahre ?? uebersicht.data?.product_years ?? [];
  const maxWert = Math.max(...produkte.map((p) => Math.abs(netto(p))), 1);
  const gefiltert = Boolean(entprellt.trim() || office || spielraum);
  const aemter = data?.facetten?.aemter ?? [];
  const stufen = data?.facetten?.spielraum ?? {};
  const gesamt = aemter.reduce((s, a) => s + a.count, 0);
  const mitBeschreibung = data?.facetten?.mit_feld?.short_description ?? 0;
  const aktiv = data?.product ?? null;

  return (
      <div className="flex flex-col gap-4">
        <div className="@container/kopf">
          <h2 className="font-display text-xl font-bold tracking-tight sm:text-[22px]">
            Was kostet eigentlich …?
          </h2>
          {/* Zwei Absätze, zwei Spalten — dieselbe Stelle wie im Kopf von
              „Woher das Geld kommt": Aufhänger und Jahres-Hinweis standen
              untereinander und ließen rechts 493 von 1136 px leer, während
              die Lotti-Karte direkt darunter die volle Breite nahm. Die
              Zeilenlänge bleibt bei 68 Zeichen. Schwelle am CONTAINER
              (Designsprache §4), weil die Seitenleiste am Desktop 240 px vom
              Platz nimmt und dieselbe Fensterbreite auf dem iPad mehr hergibt. */}
          <div className="mt-2 grid gap-x-8 gap-y-2 @5xl/kopf:grid-cols-2">
            <p className="max-w-[68ch] text-[15px] leading-relaxed text-foreground/90">
              Der Haushalt gliedert die Arbeit der Stadt in <GlossaryText text="Produkte" />:
              einzelne Aufgaben mit eigener Nummer, Budget und zuständigem Amt. Hier stehen{" "}
              <strong>{gesamt}</strong> Produkte aus dem Haushaltsjahr {year} mit ihren
              geplanten Aufwendungen, Beschreibungen und der Einschätzung der Stadt zum
              finanziellen Spielraum.
            </p>
            {/* Der Jahres-Sprung stand bisher nur ganz unten im Abdeckungs-Block.
                Wer von der Übersicht kommt, hat dort ein späteres Planjahr
                gesehen und rechnet die Beträge hier sonst dagegen. */}
            <p className="max-w-[68ch] text-[12.5px] leading-relaxed text-muted-foreground">
              {year} ist das jüngste Jahr, für das die Teilhaushaltspläne maschinell auslesbar
              vorliegen — die Beträge lassen sich deshalb nicht mit denen der Übersicht
              verrechnen. Auch die Namen stehen im Wortlaut des Plans: Wir kürzen nichts ab,
              aber wir schreiben seine Abkürzungen auch nicht aus.
            </p>
          </div>
        </div>

        <LottiErklaert
          titel="Warum das interessant ist"
          text={"Bei vielen Produkten nennt die Stadt zusätzlich den Grad der "
            + "Beeinflussbarkeit. Damit beschreibt sie, wie stark sich die Kosten aus ihrer "
            + "Sicht verändern lassen. Diese Angabe hilft einzuordnen, wo der Rat "
            + "finanziellen Spielraum hat."}
        />

        {/* Suche + Filter */}
        <div className="rounded-2xl border border-border bg-card p-3.5 shadow-sm">
          <label className="relative block">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <input
              type="search"
              value={suche}
              onChange={(e) => setSuche(e.target.value)}
              placeholder="Archiv, Feuerwehr, Schwimmbad …"
              aria-label="Produkte durchsuchen"
              className="h-11 w-full rounded-xl border border-border bg-background pl-9 pr-3 text-[14px] outline-none transition-colors focus:border-primary/50"
            />
          </label>

          <div className="mt-2.5 grid gap-2 sm:grid-cols-2">
            <label className="block">
              <span className="mb-1 block font-mono text-[9.5px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
                Amt
              </span>
              <select value={office} onChange={(e) => setAmt(e.target.value)}
                className="h-9 w-full rounded-lg border border-border bg-background px-2 text-[12.5px] outline-none focus:border-primary/50">
                <option value="">Alle Ämter ({gesamt})</option>
                {aemter.map((a) => (
                  <option key={a.office} value={a.office}>{a.office} ({a.count})</option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="mb-1 block font-mono text-[9.5px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
                Spielraum der Stadt
              </span>
              <select value={spielraum} onChange={(e) => setSpielraum(e.target.value as Spielraum | "")}
                className="h-9 w-full rounded-lg border border-border bg-background px-2 text-[12.5px] outline-none focus:border-primary/50">
                <option value="">Egal</option>
                {STUFEN.map((s) => (
                  <option key={s} value={s} disabled={!stufen[s]}>
                    {SPIELRAUM_TEXT[s].kurz} ({stufen[s] ?? 0})
                  </option>
                ))}
              </select>
            </label>
          </div>

          <div className="mt-2.5 flex flex-wrap items-center justify-between gap-2 border-t border-border/60 pt-2.5">
            <p className="font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
              {produkte.length} {produkte.length === 1 ? "Treffer" : "Treffer"}
              {gefiltert && ` von ${gesamt}`} · sortiert nach Kosten
            </p>
            {gefiltert && (
              <button type="button"
                onClick={() => { setSuche(""); setAmt(""); setSpielraum(""); }}
                className="inline-flex items-center gap-1 text-[11.5px] font-semibold text-primary">
                <X className="h-3.5 w-3.5" /> Filter zurücksetzen
              </button>
            )}
          </div>
        </div>

        {nr && !aktiv && !loading && (
          <p className="rounded-xl border border-dashed border-border bg-card p-4 text-center text-[12.5px] text-muted-foreground">
            Ein Produkt mit der Nummer „{nr}“ liegt für {year} nicht vor.
          </p>
        )}

        {produkte.length ? (
          /* Spaltenzahl am Container, nicht am Fenster (Designsprache §4):
             Am Desktop liegt die Liste neben der Seitenleiste, auf dem iPad
             nicht — dieselbe Fensterbreite meint zwei Platzangebote. */
          <div className="@container/treffer">
            <div className="grid gap-2 @3xl/treffer:grid-cols-2">
              {produkte.map((p) => {
                const offen = !!aktiv && p.product_no === nr;
                // Geschlossen ist die Karte ein Rasterkind wie jedes andere.
                // Geöffnet wird sie zur Hülle: derselbe Rahmen um Kopf und
                // Steckbrief, im zweispaltigen Raster über die volle Breite.
                if (!offen) {
                  return (
                    <Treffer key={p.product_no} p={p} max={maxWert} aktiv={false}
                      alleJahre={alleJahre} />
                  );
                }
                return (
                  <div key={p.product_no}
                    className="overflow-hidden rounded-xl border border-primary/50 bg-primary/[0.04] shadow-sm @3xl/treffer:col-span-full">
                    <Treffer p={p} max={maxWert} aktiv alleJahre={alleJahre} eingebettet />
                    <SteckbriefTeil aktiv={aktiv} year={year} alleJahre={alleJahre}
                      aufSchliessen={() => router.push("/haushalt/produkte", { scroll: false })} />
                  </div>
                );
              })}
            </div>
          </div>
        ) : (
          /* Leerzustand (H4-04): Der Suchbegriff steht drin, ähnlich
             klingende Produktnamen sind antippbar — und der Satz, WARUM man
             nichts findet, bleibt auch ohne Vorschläge stehen. */
          <div className="rounded-2xl border-2 border-dashed border-border bg-muted/40 p-8 text-center">
            <p className="mx-auto max-w-[46ch] text-[13px] leading-relaxed text-foreground/80">
              {entprellt.trim()
                ? <>Zu <strong>„{entprellt.trim()}“</strong> finden wir kein Produkt.</>
                : <>Mit diesen Filtern bleibt kein Produkt übrig.</>}
            </p>
            {vorschlaege.length > 0 && (
              <div className="mx-auto mt-3 flex max-w-[62ch] flex-wrap items-center justify-center gap-1.5">
                <span className="text-[12px] text-muted-foreground">Ähnlich klingt:</span>
                {vorschlaege.map((p) => (
                  <button key={p.product_no} type="button" onClick={() => setSuche(p.product_name)}
                    className="rounded-full border border-primary/30 bg-card px-2.5 py-1 text-[12px] font-semibold text-primary transition-colors hover:border-primary/60">
                    {p.product_name}
                  </button>
                ))}
              </div>
            )}
            <p className="mx-auto mt-3 max-w-[46ch] text-[12px] leading-relaxed text-muted-foreground">
              Produkte heißen wie im Haushaltsplan — nicht immer wie im Alltag: Das
              Stadtarchiv steht dort als „Archivierung“.
            </p>
          </div>
        )}

        {/* Abdeckung ehrlich: was die Produktebene erklärt und was nicht. */}
        <div className="@container/abdeckung rounded-2xl border border-border bg-card p-4 shadow-sm">
          <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
            Wie vollständig das ist
          </p>
          {/* Zwei Angaben, zwei Spalten: „wie viel der Ausgaben" und „wie viele
              Steckbriefe" messen Verschiedenes und standen untereinander — die
              Karte blieb rechts auf 584 von 1136 px leer. Die Zeilenlänge
              bleibt bei 70 Zeichen (Designsprache §4); breiter zu setzen wäre
              schlechter zu lesen, nicht besser. */}
          <div className="mt-2 grid gap-x-8 gap-y-2 @5xl/abdeckung:grid-cols-2">
            <p className="max-w-[70ch] text-[12.5px] leading-relaxed text-foreground/85">
              {/* toLocaleString, nicht die nackte Zahl: Der Wert kam als 81.7
                  mit englischem Punkt auf die Seite — mitten in einem Text, der
                  sonst durchgehend Komma schreibt. */}
              {data?.abdeckung_prozent != null ? (
                <>Die {gesamt} Produkte erklären{" "}
                  <strong>{data.abdeckung_prozent.toLocaleString("de-DE", { maximumFractionDigits: 1 })}&nbsp;%</strong> der
                  für {year} geplanten Ausgaben.<Beleg q="plan" /> Nicht jeder Teilhaushalt liegt für
                  jedes Jahr als auslesbares Dokument vor — dies ist also ein Ausschnitt, kein
                  Vollbild.</>
              ) : (
                <>Nicht jeder Teilhaushalt liegt für jedes Jahr als auslesbares Dokument vor —
                  dies ist ein Ausschnitt, kein Vollbild.</>
              )}
            </p>
            <p className="max-w-[70ch] text-[12.5px] leading-relaxed text-foreground/85">
              Einen Steckbrief mit Kurzbeschreibung tragen <strong>{mitBeschreibung} von {gesamt}</strong>{" "}
              Produkten; die übrigen führt der Plan ohne Beschreibungstext. Wo ein Feld fehlt, steht
              hier nichts — wir füllen keine Lücke mit einer Vermutung.
            </p>
          </div>
        </div>

      </div>
  );
}

const FELDER = ["product_years"] as const;
