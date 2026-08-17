"use client";

// /haushalt/pruefung — „Was das Rechnungsprüfungsamt beanstandet".
//
// Der Haushalt ist ein Plan, der Jahresabschluss die Abrechnung — und der
// Schlussbericht des Rechnungsprüfungsamts ist die einzige regelmäßige,
// förmliche Kontrolle davon durch eine eigene Stelle. Er hängt als PDF an
// einer Ratsvorlage und wird dort nie wieder gelesen.
//
// Haltung dieser Seite, weil es um Beanstandungen gegen die eigene Verwaltung
// geht: nüchtern und belegt, nie anklagend.
// - Jede Feststellung mit Jahr, Textziffer, Seite und Deeplink. Wer nachlesen
//   will, muss es können.
// - Die Marken werden ERKLÄRT, nicht bewertet — mit dem Wortlaut aus der
//   Legende des jeweiligen Berichts. Ein Hinweis ist etwas anderes als eine
//   Beanstandung, und die große Mehrheit sind Hinweise. Das steht oben, nicht
//   im Kleingedruckten.
// - Keine Bewertungsfarben (siehe components/haushalt/marke.tsx). Die Matrix
//   markiert B/WB in Signal-Orange — als Abweichungs-KATEGORIE des Berichts
//   (GB-10), nicht als Urteil von uns.
// - Wo die Verwaltung geantwortet hat, steht die Antwort daneben.
//
// SEIT H3-05 IST DIE WIEDERHOLUNGS-MATRIX DAS BILD DER SEITE: Feststellung ×
// Jahr (<KettenMatrix>, GB-10), denn die Wiederholungen sind die Geschichte —
// was seit Jahren angemahnt wird, steht als Kette. Der Jahrgang 2024 fehlt
// ersatzlos (PDF ohne Zeichenzuordnung); dieser Satz gehört auf die Seite,
// und die Spalte bleibt trotzdem stehen — die Komponente erzwingt sie in
// jeder Zeile. Das Board ist zugleich der Dunkelmodus-Nachweis der Serie:
// alles hier rechnet in Theme-Tokens, keine Sonderfarbe.
//
// Leserichtung: Was ist das → wie viel ist es (Zähler-Trio) → was heißen die
// Marken → was steht seit Jahren offen (die Matrix) → Bericht für Bericht.

import { Suspense, useMemo } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { ChevronRight, ExternalLink } from "lucide-react";
import { useFetch } from "@/lib/use-fetch";
import {
  Feststellung, Kette, PruefberichtDaten, belegLink, markenZaehlen, markeRang,
  nachAbschnitt, wiederholungsketten,
} from "@/lib/haushalt-pruefung";
import type { QuellenSchluessel } from "@/lib/haushalt-quellen";
import { KettenMatrix, type MatrixKette } from "@/components/grafik/ketten-matrix";
import { LueckenFeld } from "@/components/grafik/luecken-feld";
import { Beleg, Quellenkontext, Quellenverzeichnis } from "@/components/haushalt/quelle";
import { LottiErklaert } from "@/components/haushalt/lotti-erklaert";
import { MarkePille } from "@/components/haushalt/marke";
import { cn } from "@/lib/utils";
import { SchrittWeiter } from "@/components/haushalt/schritt-weiter";

const QUELLEN: QuellenSchluessel[] = ["pruefbericht", "jahresabschluss"];

/** Wortlaut aus dem Bericht — bewusst als Zitatblock mit Randlinie, damit auf
 *  einen Blick klar ist, wo das Rechnungsprüfungsamt spricht und wo wir. */
function Wortlaut({ text, gedaempft = false }: { text: string; gedaempft?: boolean }) {
  return (
    <p className={cn(
      "border-l-2 pl-3 text-[13.5px] leading-relaxed",
      gedaempft ? "border-dashed border-border text-muted-foreground" : "border-border text-foreground/90",
    )}>
      {text}
    </p>
  );
}

/** Eine Feststellung mit allem, was zum Nachschlagen nötig ist. */
function FeststellungsZeile({ f, zeigeJahr = false }: { f: Feststellung; zeigeJahr?: boolean }) {
  const link = belegLink(f);
  return (
    <div className="flex flex-col gap-2 border-t border-border/60 pt-3 first:border-t-0 first:pt-0">
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
        <MarkePille marke={f.marke} name={f.marke_name} klein />
        <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-muted-foreground">
          {zeigeJahr && <>{f.jahr} · </>}
          Textziffer {f.textziffer}
          {f.seite != null && <> · Seite {f.seite}</>}
        </span>
      </div>
      <Wortlaut text={f.text} />
      {f.folgeabsatz && (
        <div className="pl-3">
          <p className="font-mono text-[9.5px] uppercase tracking-[0.1em] text-muted-foreground">
            Im Bericht direkt darauf
          </p>
          <div className="mt-1"><Wortlaut text={f.folgeabsatz} gedaempft /></div>
        </div>
      )}
      {link && (
        <a href={link} target="_blank" rel="noopener noreferrer"
          className="inline-flex items-center gap-1.5 pl-3 text-[11.5px] font-semibold text-primary">
          Im Schlussbericht {f.jahr} nachlesen
          <ExternalLink className="h-3 w-3" />
        </a>
      )}
    </div>
  );
}

/** Der Grund, warum ein Jahrgang fehlt — die eine Lücke des Bestands, als
 *  ganzer Satz (H3-05: „Dieser Satz gehört auf die Seite"). */
const LUECKEN_GRUND = "fehlt ersatzlos: Das PDF trägt keine Zeichenzuordnung, "
  + "eine zweite Kopie existiert nicht. Die Spalte bleibt trotzdem stehen — "
  + "als Lücke, nicht als Null.";

/** Die Wiederholungsketten in den Vertrag der <KettenMatrix> (GB-10)
 *  übersetzen: je Jahr höchstens eine Zelle, und zwar die SCHWERSTE Marke
 *  des Abschnitts in diesem Jahrgang (WB vor B vor K vor H). */
function alsMatrixKetten(ketten: Kette[], jahreAnzahl: number): MatrixKette[] {
  return ketten.map((k) => {
    const zellen: { jahr: number; marke: string }[] = [];
    for (const jahr of k.jahre) {
      const hier = k.eintraege.filter((f) => f.jahr === jahr)
        .sort((a, b) => markeRang(a.marke) - markeRang(b.marke));
      if (hier[0]) zellen.push({ jahr, marke: hier[0].marke });
    }
    return {
      key: k.schluessel,
      titel: k.titel,
      untertitel: `in ${k.beanstandet.length} von ${jahreAnzahl} Berichten beanstandet`
        + (k.beanstandet.length ? ` · zuletzt ${k.beanstandet.at(-1)}` : ""),
      zellen,
    };
  });
}

function PruefungInner() {
  const gewaehltesJahr = Number(useSearchParams().get("jahr")) || null;
  const { data, loading } = useFetch<PruefberichtDaten>("/council/haushalt/pruefberichte");

  const jahre = data?.jahre ?? [];
  const jahr = gewaehltesJahr && jahre.includes(gewaehltesJahr) ? gewaehltesJahr : jahre.at(-1) ?? null;
  const alle = useMemo(() => data?.feststellungen ?? [], [data]);
  const ketten = useMemo(() => wiederholungsketten(alle), [alle]);
  const matrixKetten = useMemo(
    () => alsMatrixKetten(ketten, jahre.length), [ketten, jahre.length]);
  const zahl = useMemo(() => markenZaehlen(alle), [alle]);
  const gruppen = useMemo(() => (jahr ? nachAbschnitt(alle, jahr) : []), [alle, jahr]);

  if (loading || !data) {
    return <div className="py-16 text-center text-sm text-muted-foreground">Wird geladen …</div>;
  }
  if (!jahr || !alle.length) {
    return (
      <div className="py-16 text-center text-sm text-muted-foreground">
        Für kein Jahr liegt bisher ein ausgelesener Schlussbericht vor.{" "}
        <Link href="/haushalt" className="font-semibold text-primary">Zur Übersicht</Link>
      </div>
    );
  }

  const marken = Object.keys(data.legende).sort((a, b) => markeRang(a) - markeRang(b));
  const hinweise = zahl["H"] ?? 0;
  const beanstandungen = zahl["B"] ?? 0;
  const wiederholt = zahl["WB"] ?? 0;

  return (
    <Quellenkontext schluessel={QUELLEN} jahr={jahr}>
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-1.5 text-[11.5px] text-muted-foreground">
        <Link href="/haushalt" className="hover:text-foreground">Haushalt</Link>
        <ChevronRight className="h-3 w-3" />
        <span className="font-semibold text-foreground">Die Prüfung</span>
      </div>

      <div>
        <p className="font-mono text-[10.5px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
          Rechnungsprüfungsamt · {jahre[0]}–{jahre.at(-1)}
        </p>
        {/* Die Überschrift wird gerechnet, nicht geschrieben — ein fester
            Satz wäre beim nächsten Jahrgang still falsch. */}
        <h1 className="mt-1 font-display text-2xl font-bold tracking-tight sm:text-[25px]">
          {alle.length} Feststellungen — {wiederholt} kehren Jahr für Jahr wieder
        </h1>
        <p className="mt-2 max-w-[68ch] text-sm leading-relaxed text-foreground/90">
          Jeder Jahresabschluss der Stadt wird geprüft — von einer eigenen Stelle, die dem Rat
          berichtet und nicht der Verwaltungsspitze untersteht. Ihre Befunde stehen in einem
          Schlussbericht, der als Anlage an einer Ratsvorlage hängt. Die Wiederholungen sind
          die Geschichte: Was seit Jahren angemahnt wird, steht hier als Kette — und der
          Wortlaut bleibt das Zentrum.
        </p>
      </div>

      {/* Wie viel ist es — das Zähler-Trio (H3-05), mobil als 3er-Raster
          (H4-09). Die drei Zahlen sind die Marken selbst: H, B und WB —
          erst darunter erklärt der Satz, was sie bedeuten. */}
      <div className="rounded-2xl border border-border bg-card p-4 shadow-sm">
        <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
          {jahre.length} geprüfte Jahresabschlüsse · {jahre[0]}–{jahre.at(-1)}
        </p>
        <div className="mt-2.5 grid grid-cols-3 gap-2">
          {([
            { wert: hinweise, name: "Hinweise" },
            { wert: beanstandungen, name: "Beanstandungen" },
            { wert: wiederholt, name: "wiederholt" },
          ] as const).map((t) => (
            <div key={t.name} className="rounded-xl bg-muted/45 px-3 py-2.5">
              <p className="font-display text-[26px] font-bold leading-none tracking-tight tabular-nums">
                {t.wert}
              </p>
              <p className="mt-1 text-[11.5px] leading-snug text-muted-foreground">{t.name}</p>
            </div>
          ))}
        </div>
        <p className="mt-3 max-w-[70ch] text-[13px] leading-relaxed text-foreground/90">
          In den Berichten stehen <strong>{alle.length} Feststellungen</strong>
          <Beleg q="pruefbericht" />. Die große Mehrheit sind Hinweise — Dinge, die künftig zu
          beachten sind. Eine Beanstandung meint einen bedeutsamen Mangel; „wiederholt" ist
          die eigene Aussage des Amts, dass ein Mangel aus einem Vorjahr noch nicht
          ausgeräumt war.
        </p>
        <div className="mt-3 flex flex-wrap gap-1.5 border-t border-border/60 pt-3">
          {marken.map((m) => (
            <span key={m} className="inline-flex items-baseline gap-1.5">
              <MarkePille marke={m} name={data.legende[m].name} />
              <span className="font-mono text-[11px] tabular-nums text-muted-foreground">
                {zahl[m] ?? 0}
              </span>
            </span>
          ))}
        </div>
      </div>

      {/* Die Marken erklären, nicht bewerten — mit dem Wortlaut des Berichts. */}
      <div className="rounded-2xl border border-border bg-card p-4 shadow-sm">
        <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
          Was die Marken am Seitenrand bedeuten
        </p>
        <dl className="mt-2.5 flex flex-col gap-2">
          {marken.map((m) => (
            <div key={m} className="flex flex-col gap-1 border-t border-border/60 pt-2 first:border-t-0 first:pt-0 sm:flex-row sm:items-baseline sm:gap-3">
              <dt className="flex-none"><MarkePille marke={m} name={data.legende[m].name} klein /></dt>
              <dd className="text-[12.5px] leading-relaxed text-muted-foreground">
                {data.legende[m].erlaeuterung ?? "—"}
              </dd>
            </div>
          ))}
        </dl>
        <p className="mt-3 text-[11px] leading-relaxed text-muted-foreground">
          Wortlaut aus den Vorbemerkungen der Berichte. Welche Marken ein Bericht führt, ist nicht
          in jedem Jahrgang gleich — der Schlussbericht 2023 erklärt keine Korrekturen mehr.
        </p>
      </div>

      <LottiErklaert
        titel="Wer hier eigentlich prüft"
        text="Das Rechnungsprüfungsamt gehört zur Stadt, arbeitet aber für den Rat und nicht für die Verwaltungsspitze. Es schaut jedes Jahr nach, ob der Jahresabschluss stimmt und ob nach den Regeln gewirtschaftet wurde. Ein Hinweis ist dabei kein Vorwurf, sondern eine Notiz für das nächste Mal — erst eine Beanstandung meint einen bedeutsamen Mangel."
      />

      {/* Die eigentliche Nachricht: was seit Jahren offen ist — als
          Wiederholungs-Matrix (GB-10). Kette antippen oder mit Enter öffnen
          zeigt den Wortlaut aller Feststellungen; die 2024-Lücke rendert die
          Komponente in jeder Zeile und als Satz darüber. */}
      {ketten.length > 0 ? (
        <div className="rounded-2xl border border-border bg-card p-4 shadow-sm">
          <div className="mb-1 flex flex-wrap items-baseline justify-between gap-2">
            <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
              Wiederholungs-Ketten · was über Jahre offen blieb
            </p>
            <span className="font-mono text-[10px] uppercase text-muted-foreground">
              {ketten.length} Themen · {jahre[0]}–{jahre.at(-1)}
            </span>
          </div>
          <p className="mb-3 max-w-[70ch] text-[12.5px] leading-relaxed text-muted-foreground">
            Hier steht nur, was das Rechnungsprüfungsamt selbst als <em>wiederholte</em>{" "}
            Beanstandung ausgewiesen hat — also seine eigene Aussage, dass ein Mangel aus einem
            Vorjahr noch offen war. Zugeordnet wird über den Abschnitt des Berichts; die
            Textziffern verschieben sich zwischen den Jahrgängen. Ein „erledigt/offen" kennt
            die Quelle nicht — die Kette endet, wo der Bericht nichts mehr vermerkt.
          </p>
          <KettenMatrix
            ketten={matrixKetten}
            jahre={jahre}
            lueckenJahre={data.ohne_bericht.map((j) => ({ jahr: j, grund: LUECKEN_GRUND }))}
            marken={data.legende}
            beleg={<Beleg q="pruefbericht" />}
            detail={(mk) => {
              const k = ketten.find((x) => x.schluessel === mk.key);
              if (!k) return null;
              return (
                <div className="flex flex-col gap-3 rounded-xl bg-muted/35 p-3">
                  {k.eintraege.map((f) => (
                    <FeststellungsZeile key={`${f.jahr}-${f.lfd}`} f={f} zeigeJahr />
                  ))}
                </div>
              );
            }}
          />
        </div>
      ) : (
        /* Ohne Ketten gäbe es keine Matrix — der Lücken-Satz bleibt trotzdem
           Pflicht auf der Seite (H4-09: auf jedem Gerät). */
        data.ohne_bericht.length > 0 && (
          <div className="flex flex-col gap-1.5">
            {data.ohne_bericht.map((j) => (
              <LueckenFeld key={j} label={String(j)} grund={LUECKEN_GRUND} />
            ))}
          </div>
        )
      )}

      {/* Bericht für Bericht */}
      <div className="flex flex-col gap-1.5">
        <span className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
          Geprüfter Jahresabschluss
        </span>
        <div className="scrollbar-none -mx-1 flex items-center gap-1 overflow-x-auto px-1 py-0.5">
          <div className="flex flex-none items-center gap-1 rounded-full border border-border bg-card p-1">
            {jahre.map((j) => (
              <Link key={j} href={`/haushalt/pruefung?jahr=${j}`} scroll={false}
                className={cn("rounded-full px-3 py-1 text-[12.5px]",
                  j === jahr ? "bg-primary font-semibold text-primary-foreground" : "text-foreground/75 hover:bg-accent")}>
                {j}
              </Link>
            ))}
          </div>
        </div>
      </div>

      <div className="rounded-2xl border border-border bg-card p-4 shadow-sm">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
            Schlussbericht zum Jahresabschluss {jahr}
          </p>
          <span className="font-mono text-[10px] uppercase text-muted-foreground">
            {alle.filter((f) => f.jahr === jahr).length} Feststellungen · {gruppen.length} Abschnitte
          </span>
        </div>
        <div className="mt-3 flex flex-col gap-4">
          {gruppen.map((g) => (
            <div key={g.textziffer} className="border-t border-border/60 pt-3 first:border-t-0 first:pt-0">
              <p className="font-display text-[14.5px] font-bold leading-snug tracking-tight">
                <span className="font-mono text-[11px] font-medium text-muted-foreground">{g.textziffer}</span>{" "}
                {g.abschnitt}
              </p>
              <div className="mt-2.5 flex flex-col gap-3">
                {g.eintraege.map((f) => <FeststellungsZeile key={f.lfd} f={f} />)}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Was hier fehlt und warum — plus, wie wörtlich der Text ist. Der
          Absatz begann bis 16.08. mit unserer Parser-Bedingung („Jede Marke
          muss in der Legende erklärt sein und unter einer Textziffer
          stehen"). Die Bedingung gilt weiter (`council/pruefberichte.py`,
          Doku: „Der Konsistenz-Check statt einer Rechenprobe"); auf der Seite
          war sie Selbstvergewisserung. Der fehlende Jahrgang dagegen ist eine
          echte Auskunft über die Datenlage und bleibt. DESIGNSPRACHE.md § 7. */}
      {/* Der 2024-Satz steht oben an der Matrix (LueckenFeld) — hier bleibt
          nur noch, wie wörtlich der Text ist. */}
      <p className="max-w-[86ch] text-[11.5px] leading-relaxed text-muted-foreground">
        Die Feststellungen stehen im Wortlaut des Berichts; Zeilenumbrüche des PDF-Textes sind
        zusammengezogen, sonst ist nichts verändert.
      </p>

      <SchrittWeiter href="/haushalt/pruefung" />

      <Quellenverzeichnis schluessel={QUELLEN} />
    </div>
    </Quellenkontext>
  );
}

export default function PruefungPage() {
  return (
    <Suspense fallback={<div className="py-16 text-center text-sm text-muted-foreground">Wird geladen …</div>}>
      <PruefungInner />
    </Suspense>
  );
}
