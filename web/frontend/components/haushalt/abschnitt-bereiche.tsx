"use client";

// „Was steckt hinter den Namen?" — der ERSTE Abschnitt von
// /haushalt/produkte.
//
// Bis zum 21.08.2026 die eigene Seite /haushalt/bereiche. Zusammengelegt mit
// „Was kostet eigentlich …?": Beide gehen denselben Baum hinunter — erst die
// zehn Teilhaushalte im Klartext, dann die einzelnen Aufgaben darin. Der
// Steckbrief eines einzelnen Bereichs (/haushalt/bereich) bleibt eine eigene
// Seite; er ist die dritte Ebene und hat bewusst keinen Schritt.

// /haushalt/bereiche — „Soziales", „Finanzmanagement": was heißt das eigentlich?
//
// Die Bereichsnamen sind die größte Verständnishürde des ganzen Haushalts.
// Sie stammen aus der Verwaltungsgliederung und beschreiben Zuständigkeiten,
// keine Sachen: „Finanzmanagement und Recht" klingt nach Buchhaltung, ist aber
// die Stelle, an der zwei Drittel aller Einnahmen der Stadt eingehen. Wer das
// nicht weiß, liest jede Übersicht falsch — der größte Balken der Einnahmen
// sieht dann aus, als erwirtschafte die Kämmerei ihn.
//
// Deshalb diese Seite: einmal alle Teilhaushalte, mit Betrag und einer Zeile
// Klartext, und der schwierigste Fall vorangestellt.
//
// Alle Texte kommen aus `lib/haushalt-bereiche.ts`, alle Zahlen aus
// `/api/council/haushalt`. Hier steht keine Zahl fest im Code.

import Link from "next/link";
import { ChevronRight, ArrowRight } from "lucide-react";
import { useFetch } from "@/lib/use-fetch";
import { Beleg } from "@/components/haushalt/quelle";
import { NamenKlartext } from "@/components/haushalt/namen-klartext";
import { LottiErklaert } from "@/components/haushalt/lotti-erklaert";
import { GlossaryText } from "@/components/glossary-text";
import { STEUERARTEN } from "@/lib/haushalt-steuern";
import { bereichSchluessel } from "@/lib/haushalt-bereiche";
import {
  HaushaltAuswahl, haushaltUrl, HaushaltZeile, bereichSlug, bereiche, deMio, jahreSortiert, mio,
} from "@/lib/haushalt";


/** Ein Posten, der im Finanzmanagement zentral eingeht — Betrag und Jahr aus
 *  den Daten, Titel und Stellschraube aus den Steuer-Steckbriefen.
 *
 *  Bewusst KEINE eigene Liste der Einnahmearten: Wer welche Stellschraube
 *  bedient, steht redaktionell schon in `lib/haushalt-steuern.ts` und wird von
 *  `/haushalt/einnahmen` und den Steckbriefen benutzt. Eine zweite Fassung
 *  hier wäre ein zweiter Stand derselben Aussage. */
type Posten = { slug: string; titel: string; wer: string; mioWert: number; jahr: number };

function zentralePosten(daten: Daten): Posten[] {
  const out: Posten[] = [];
  for (const s of STEUERARTEN) {
    if (s.datenArt) {
      const treffer = daten.steuern
        .filter((r) => r.art === s.datenArt && r.betrag != null)
        .sort((a, b) => a.jahr - b.jahr);
      const letzte = treffer[treffer.length - 1];
      if (letzte) {
        out.push({
          slug: s.slug, titel: s.titel, wer: s.stellschraube,
          mioWert: mio(letzte.betrag) ?? 0, jahr: letzte.jahr,
        });
      }
      continue;
    }
    // Die Schlüsselzuweisungen führt das Land in einem eigenen Datensatz.
    // „Gebühren und Beiträge" bleibt draußen, und zwar aus einem inhaltlichen
    // Grund: Gebühren gehen NICHT zentral ein, sondern bei dem Bereich, der
    // die Leistung erbringt. Sie hier aufzuführen wäre genau der Fehler, den
    // die Seite erklären will.
    if (s.slug === "schluesselzuweisungen") {
      const treffer = daten.steuerkraft
        .filter((r) => r.zuweisungen != null)
        .sort((a, b) => a.jahr - b.jahr);
      const letzte = treffer[treffer.length - 1];
      if (letzte) {
        out.push({
          slug: s.slug, titel: s.titel, wer: s.stellschraube,
          mioWert: mio(letzte.zuweisungen) ?? 0, jahr: letzte.jahr,
        });
      }
    }
  }
  return out.sort((a, b) => b.mioWert - a.mioWert);
}

/** Die Sonderkachel: warum bei „Finanzmanagement und Recht" so viel steht. */
function Finanzkachel({ z, daten, jahr }: {
  z: HaushaltZeile; daten: Daten; jahr: number;
}) {
  const ein = mio(z.ertraege) ?? 0;
  const aus = mio(z.aufwendungen) ?? 0;
  const posten = zentralePosten(daten);
  const istJahre = [...new Set(posten.map((p) => p.jahr))].sort();

  return (
    <div className="rounded-2xl border border-primary/20 bg-primary/[0.05] p-4 shadow-sm sm:p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h2 className="font-display text-[17px] font-bold tracking-tight">
          Der schwierigste Name: „Finanzmanagement und Recht“
        </h2>
        <span className="font-mono text-[10px] uppercase tracking-[0.09em] text-muted-foreground">
          {deMio(ein)}&#8239;Mio.&nbsp;€ Erträge · {deMio(aus)}&#8239;Mio.&nbsp;€ Aufwendungen<Beleg q="plan" />
        </span>
      </div>
      {/* Die Formulierung ist genau geprüft: Steuern liegen zu 100 % hier, die
          Zuwendungen aber nur zum Teil (2024: 115,4 von 179,1 Mio.; 46,4 Mio.
          buchen Soziales, 11,5 Mio. Jugend). „Alle Steuern und Zuweisungen"
          wäre also falsch — richtig ist „alle Steuern und die allgemeinen
          Zuweisungen des Landes". Dieselbe Fassung steht in `lib/haushalt.ts`. */}
      <p className="mt-2 max-w-[80ch] text-[13.5px] leading-relaxed text-foreground/90">
        Hier steht der Löwenanteil aller Einnahmen — nicht, weil die Kämmerei etwas
        erwirtschaftet, sondern weil <strong>alle Steuern und die allgemeinen Zuweisungen
        des Landes</strong> für die ganze Stadt zentral auf diesem Teilhaushalt verbucht
        werden. Aus diesem Topf werden dann die Bereiche bezahlt, die kein eigenes Geld
        einnehmen. Zweckgebundene Zuschüsse laufen dagegen bei dem Fachbereich auf, der
        sie bekommt — deshalb stehen sie hier nicht.
      </p>

      {posten.length > 0 && (
        <>
          <p className="mt-3.5 font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
            Was hier zentral eingeht
          </p>
          <div className="mt-2 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {posten.map((p) => (
              <Link key={p.slug} href={`/haushalt/steuer?art=${p.slug}`}
                className="group rounded-xl border border-border bg-card p-3 shadow-sm transition-colors hover:border-primary/40">
                <p className="flex items-center gap-1 text-[12.5px] font-bold leading-snug">
                  {p.titel}
                  <ChevronRight aria-hidden className="h-3.5 w-3.5 flex-none text-muted-foreground transition-transform group-hover:translate-x-0.5" />
                </p>
                <p className="mt-1.5 font-display text-[17px] font-bold tabular-nums">
                  {deMio(p.mioWert)}
                  <span className="ml-1 text-[11px] font-semibold text-muted-foreground">
                    Mio.&nbsp;€ · Ist {p.jahr}
                  </span>
                </p>
                <p className="mt-1 text-[11.5px] leading-relaxed text-muted-foreground">{p.wer}</p>
              </Link>
            ))}
            {/* Die letzte Kachel spannt die Zeile — aus demselben Grund wie
                der siebte Wegweiser-Schritt: Sieben gleich große Kacheln
                gehen in keiner Spaltenzahl auf, und eine einzelne in der
                letzten Zeile liest sich wie ein Nachtrag. Inhaltlich passt
                es ohnehin: Alle anderen sind Einnahmen, diese eine sind die
                Ausgaben des Bereichs. */}
            <div className="rounded-xl border border-border bg-card p-3 shadow-sm sm:col-span-2 lg:col-span-3">
              <p className="text-[12.5px] font-bold leading-snug">Und die Aufgaben selbst</p>
              <p className="mt-1.5 font-display text-[17px] font-bold tabular-nums">
                {deMio(aus)}
                <span className="ml-1 text-[11px] font-semibold text-muted-foreground">
                  Mio.&nbsp;€ · Plan {jahr}
                </span>
              </p>
              <p className="mt-1 text-[11.5px] leading-relaxed text-muted-foreground">
                Kämmerei, Stadtkasse, Steuerabteilung, Rechtsamt und die Zinsen der Stadt.
              </p>
            </div>
          </div>
          {/* Zwei Stände auf einer Kachel — das muss dranstehen. Die
              Einnahme-Posten sind abgerechnete Ist-Werte, der Bereichsbetrag
              ist der Plan des Kopfjahres. Sie summieren sich deshalb nicht
              auf die Ertragszeile, und wer nachrechnet, soll das vorher
              wissen statt hinterher. */}
          <p className="mt-2.5 text-[11.5px] leading-relaxed text-muted-foreground">
            Die Einnahmen oben sind abgerechnete Ist-Werte
            {istJahre.length ? ` (${istJahre.join(" und ")})` : ""}
            <Beleg q="steuern" /><Beleg q="steuerkraft" />, die {deMio(ein)}&nbsp;Mio.&nbsp;€
            daneben der Plan für {jahr}. Zwei verschiedene Stände: Sie addieren sich nicht
            zur Ertragszeile, und die Liste ist auch nicht vollständig — Zinsen,
            Konzessionsabgaben und weitere allgemeine Erträge sind nicht darunter.
          </p>
        </>
      )}

      <Link href={`/haushalt/bereich?name=${bereichSlug(z.bereich)}`}
        className="mt-3 inline-flex items-center gap-1.5 text-[12.5px] font-semibold text-primary">
        Diesen Bereich im Einzelnen
        <ArrowRight aria-hidden className="h-3.5 w-3.5" />
      </Link>
    </div>
  );
}

/** Was diese Seite rendert — und damit alles, was sie holt.
 *  Feldliste und Typ kommen aus derselben Zeile: Ein Zugriff auf ein
 *  nicht angefordertes Feld ist ein Fehler beim Bauen, kein leerer Block. */
const FELDER = ["jahre", "produkt_jahre", "steuern", "steuerkraft"] as const;

/** Der Ausschnitt, den diese Seite holt. */
type Daten = HaushaltAuswahl<typeof FELDER[number]>;

export function BereicheAbschnitt() {
  const { data, loading } = useFetch<Daten>(haushaltUrl(FELDER));

  if (loading || !data) {
    return <div className="py-16 text-center text-sm text-muted-foreground">Haushalt wird geladen …</div>;
  }
  const jahre = jahreSortiert(data);
  const jahr = jahre[jahre.length - 1];
  const zeilen = jahr ? data.jahre[String(jahr)] ?? [] : [];
  if (!jahr || !bereiche(zeilen).length) {
    return (
      <div className="py-16 text-center text-sm text-muted-foreground">
        Für den Haushalt liegen uns gerade keine Bereichszahlen vor.{" "}
        <Link href="/haushalt" className="font-semibold text-primary">Zur Übersicht</Link>
      </div>
    );
  }

  const finanzen = bereiche(zeilen).find((z) => bereichSchluessel(z.bereich) === "finanzen");
  const produktJahre = (data.produkt_jahre ?? []).slice().sort((a, b) => a - b);
  const produktBis = produktJahre[produktJahre.length - 1] ?? null;

  return (
      <div className="flex flex-col gap-4">
        <div>
          <p className="font-mono text-[10.5px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
            Die Teilhaushalte im Klartext
          </p>
          <h2 className="mt-1 font-display text-xl font-bold tracking-tight sm:text-[22px]">
            „Soziales“, „Finanzmanagement“ — was heißt das eigentlich?
          </h2>
          <p className="mt-2 max-w-[74ch] text-sm leading-relaxed text-muted-foreground">
            Der Haushalt ist in Teilhaushalte geteilt, und deren Namen stammen aus der
            Verwaltungsgliederung: Sie sagen, wer zuständig ist, nicht, worum es geht.
            Hier steht zu jedem eine Zeile, die man ohne Vorwissen lesen kann — und der
            schwierigste Fall gleich vorweg.
          </p>
        </div>

        {finanzen && <Finanzkachel z={finanzen} daten={data} jahr={jahr} />}

        <div className="rounded-2xl border border-border bg-card p-4 shadow-sm sm:p-5">
          <NamenKlartext zeilen={zeilen} jahr={jahr} />
          <p className="mt-3 border-t border-dashed border-border pt-2.5 text-[11.5px] leading-relaxed text-muted-foreground">
            Sortiert nach Größe (Ausgaben oder Kosten für die Stadt), nie nach der Nummer im
            Haushaltsplan<Beleg q="plan" />. „Aus dem allgemeinen Topf" ist der Zuschussbedarf:
            Ausgaben minus eigene Erträge des Bereichs. Die Beschreibungen sind redaktionell
            nach dem Vorbericht des Plans — keine amtliche Gliederung.
          </p>
        </div>

        {/* Bis 16.08. stand an dieser Stelle im Entwurf „die Produktebene ist
            noch nicht eingelesen". Sie ist es seit #500. Der Hinweis schickte
            Leute weg von genau der Seite, die ihre Frage beantwortet —
            deshalb steht hier der Link, und daneben der Jahresstempel, weil
            die Produktebene das Kopfjahr eben NICHT erreicht. */}
        {produktBis != null && (
          <div className="rounded-2xl border border-border bg-card p-4 shadow-sm">
            <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
              Eine Ebene tiefer
            </p>
            <p className="mt-1.5 max-w-[76ch] text-[13px] leading-relaxed text-foreground/90">
              Ein Teilhaushalt bündelt viele einzelne Aufgaben — Stadtarchiv, Feuerwehr,
              Schwimmbad. Was jede davon kostet, steht auf der Produktebene:
              Stand {produktBis}
              <Beleg q="teilhaushalt" />, für das Haushaltsjahr {jahr} gibt es sie noch nicht.
            </p>
            <Link href="/haushalt/produkte"
              className="mt-2 inline-flex items-center gap-1.5 text-[12.5px] font-semibold text-primary">
              Was kostet eigentlich …?
              <ArrowRight aria-hidden className="h-3.5 w-3.5" />
            </Link>
          </div>
        )}

        <LottiErklaert
          titel="Warum die Namen sich ändern"
          text={"Die Stadt schneidet ihre Teilhaushalte gelegentlich neu zu und benennt sie um, "
            + "ohne dass sich die Aufgaben dahinter ändern müssen. Teilhaushalt 9 hieß in sieben "
            + "Jahrgängen viermal verschieden. Wir zeigen deshalb immer die jüngste amtliche "
            + "Schreibweise — und ziehen keine Kurve über die Jahre, wo sich der Zuschnitt "
            + "wirklich geändert hat."}
        />

        <p className="max-w-[86ch] text-xs leading-relaxed text-muted-foreground">
          <GlossaryText text={"Übrigens: Ein Teilhaushalt ist kein eigener Geldbeutel. Alle "
            + "Einnahmen der Stadt landen zusammen in einer Kasse, und aus dieser einen Kasse "
            + "wird jede Aufgabe bezahlt — deshalb lässt sich nicht sagen, welche Einnahme "
            + "welche Ausgabe trägt."} />
        </p>

      </div>
  );
}
