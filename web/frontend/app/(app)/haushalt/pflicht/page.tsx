"use client";

// /haushalt/pflicht — „Muss oder kann?"
//
// Die Seite beantwortet eine Frage: Worüber kann der Rat überhaupt
// entscheiden? Sie hat sich am 16.08. in zwei Punkten geändert.
//
// ERSTENS ist die Gruppierung die Aussage. Vorher stand hier eine Filterleiste
// über einer flachen Liste aus 13 Karten: Wer wissen wollte, wie viel Pflicht
// im Haushalt steckt, musste dreimal filtern und im Kopf addieren. Jetzt
// stehen die Bereiche in drei Abschnitten, jeder mit seiner Summe, und darüber
// ein Balken, der die geplanten Aufwendungen in genau diese drei Teile zerlegt.
// Die Antwort steht damit im ersten Bild, nicht in der neunten Karte.
//
// ZWEITENS hat die Einordnung Boden bekommen. Die Produktebene (#500) trägt zu
// jeder einzelnen Aufgabe die Auftragsgrundlage im Wortlaut des Plans und die
// Selbstauskunft der Stadt zum Spielraum. Beides wird hier je Teilhaushalt
// zusammengefasst und gegen unsere redaktionelle Stufe gehalten. Wo beide
// auseinandergehen, sagt die Seite das — bei „Jugend und Familie" nennen wir
// Ausstattung und Betreuungsschlüssel gestaltbar, die Stadt sieht bei 95 % des
// Geldes „kaum Spielraum". Das ist der interessanteste Satz auf der Seite und
// wird deshalb nicht geglättet, sondern gezählt und ausgewiesen.
//
// Zwei Fallen, die hier eingebaut sind, damit sie nicht wiederkommen:
//
//  - BRUTTO IST NICHT NETTO. „47,1 Mio. freiwillig gegen 71,1 Mio. Defizit"
//    vergleicht Aufwendungen mit einem Saldo. Striche der Rat diese Bereiche,
//    fielen ihre eigenen Erträge mit weg — es bliebe der Zuschussbedarf von
//    43,0 Mio. Der Balken zeigt Aufwendungen und schreibt das dazu, der Satz
//    darunter rechnet mit dem Saldo.
//  - KEIN SATZ, DER NUR FÜR EIN JAHR STIMMT. „Selbst wenn der Rat alles
//    Freiwillige striche, bliebe ein Minus" gilt 2026 (43,0 < 71,1) und wäre
//    für 2024 falsch gewesen. Der Satz wird gerechnet und fällt weg, wenn er
//    nicht trägt.
//
// Zwei Jahre auf einer Seite: Der Plan reicht bis ins Kopfjahr, die
// Die Produktebene reicht nicht so weit wie der Plan — jede Aussage aus ihr
// trägt deshalb ihren Jahresstempel. Wie weit sie reicht, sagen die Daten
// selbst; hier stand bis 16.08. „endet 2023", was mit dem Nachziehen der
// Jahrgänge 2024/25 (#548) still falsch wurde.

import { useMemo } from "react";
import Link from "next/link";
import { ChevronRight, Scale } from "lucide-react";
import { useFetch } from "@/lib/use-fetch";
import {
  HaushaltAuswahl, haushaltUrl, HaushaltZeile, ProdukteAntwort, SPIELRAUM_TEXT, Spielraum,
  bereiche, bereichSlug, amount, deMio, jahreSortiert, mio, summe,
} from "@/lib/haushalt";
import { BereichSchluessel, bereichKanon } from "@/lib/haushalt-bereiche";
import {
  Abgleich, PFLICHT_ERKLAERUNG, PFLICHT_LABEL, PflichtStufe, SpielraumBefund,
  abgleich, pflichtFuer, spielraumBefunde,
} from "@/lib/haushalt-pflicht";
import { Anteilsbalken, type Anteil } from "@/components/haushalt/anteilsbalken";
import { Gegenbalken } from "@/components/grafik/gegenbalken";
import { Beleg, Quellenkontext, Quellenverzeichnis } from "@/components/haushalt/quelle";
import type { QuellenSchluessel } from "@/lib/haushalt-quellen";
import { LottiErklaert } from "@/components/haushalt/lotti-erklaert";
import { cn } from "@/lib/utils";
import { SchrittKicker, SchrittWeiter } from "@/components/haushalt/schritt-weiter";
import { SchrittPfad } from "@/components/haushalt/schritt-pfad";
import { Seitenbuehne, ZaehlZahl } from "@/components/haushalt/seitenbuehne";

const STUFEN: PflichtStufe[] = ["pflicht", "spielraum", "freiwillig"];
const QUELLEN: QuellenSchluessel[] = ["plan", "teilhaushalt"];

/** Beide Balken der Seite nehmen dieselben drei Stufen derselben
 *  Ausgabenrampe — nie Ampelfarben, ein Pflichtposten ist keine Note.
 *  „Pflicht" und „kaum Spielraum" bekommen das eine Ende der Rampe,
 *  „überwiegend freiwillig" und „viel Spielraum" das andere.
 *
 *  Was gleich bleibt, ist der ABSTAND zur Fläche, nicht die absolute
 *  Helligkeit: Die Rampe dreht mit dem Theme (hell hsl(211 34% 26%) → dunkel
 *  hsl(206 20% 82%)), damit der Balken auf beiden Untergründen trägt. Deshalb
 *  `--hh-aus-5` statt `-6` am schwachen Ende — `-6` liegt im Dunkelmodus nur
 *  neun Helligkeitspunkte über der Spurfarbe und verschwände in einem
 *  6-px-Balken fast. */
const TON_STUFE: Record<PflichtStufe, string> = {
  pflicht: "var(--hh-aus-0)",
  spielraum: "var(--hh-aus-3)",
  freiwillig: "var(--hh-aus-5)",
};
const TON_SPIELRAUM: Record<Spielraum, string> = {
  niedrig: "var(--hh-aus-0)",
  mittel: "var(--hh-aus-3)",
  hoch: "var(--hh-aus-5)",
};
/** Fehlende Angabe: bewusst NICHT aus der Rampe, sonst liest sie sich als
 *  vierte Stufe. Schraffiert nach der Lücken-Konvention. */
const TON_OFFEN = "hsl(var(--muted-foreground))";

/** Ab diesem Geld-Anteil zählt eine Spielraum-Stufe als eigene Aussage —
 *  dieselbe 10-%-Schwelle, ab der ein Gegenbalken-Segment eine Beschriftung
 *  tragen darf (GB-04). Erst wenn ZWEI Kategorien darüber liegen, ist die
 *  Selbstauskunft eine Verteilung und bekommt einen Balken; sonst trägt der
 *  Satz sie allein. Grund (Tims Befund 24.08.): 9 von 10 Bereichen sind zu
 *  ≥ 93 % EINE Stufe — der Balken war dort ein einfarbiger Streifen, der
 *  aussah wie ein Ladebalken und nichts sagte, was der Satz nicht sagt. */
const MISCHUNG_AB = 0.1;

type Zeile = {
  z: HaushaltZeile;
  /** Aufwendungen in Mio. € */
  aus: number;
  /** Aufwendungen − eigene Erträge in Mio. €: was der Bereich die Stadt kostet.
   *  `null`, wenn eine der beiden Seiten fehlt. */
  netto: number | null;
  stufe: PflichtStufe | null;
  was: string | null;
  befund: SpielraumBefund | undefined;
  urteil: Abgleich;
};

/** Was diese Seite rendert — und damit alles, was sie holt.
 *  Feldliste und Typ kommen aus derselben Zeile: Ein Zugriff auf ein
 *  nicht angefordertes Feld ist ein Fehler beim Bauen, kein leerer Block. */
const FELDER = ["jahre", "produkt_jahre"] as const;

export default function PflichtPage() {
  const { data, loading } = useFetch<HaushaltAuswahl<typeof FELDER[number]>>(haushaltUrl(FELDER));

  // Die Produktebene reicht nicht bis ins Planjahr — welches Jahr sie trägt,
  // sagt die Übersicht. Deshalb erst der zweite Aufruf, und nur wenn es
  // überhaupt eines gibt (`useFetch(null)` überspringt).
  const produktJahr = data?.produkt_jahre?.length ? Math.max(...data.produkt_jahre) : null;
  // Der erste Jahrgang kommt ebenfalls aus den Daten. „2018" als feste Zahl in
  // den Satz zu schreiben hieße, beim nächsten Nachzug still zu lügen.
  const produktVon = data?.produkt_jahre?.length ? Math.min(...data.produkt_jahre) : null;
  const { data: produktdaten } = useFetch<ProdukteAntwort>(
    produktJahr ? `/council/haushalt/produkte?year=${produktJahr}` : null,
  );

  const befunde = useMemo<Map<BereichSchluessel, SpielraumBefund>>(
    () => (produktdaten && produktJahr
      ? spielraumBefunde(produktdaten.produkte, produktJahr)
      : new Map()),
    [produktdaten, produktJahr],
  );

  if (loading || !data) {
    return <div className="py-16 text-center text-sm text-muted-foreground">Wird geladen …</div>;
  }

  const jahre = jahreSortiert(data);
  const year = jahre[jahre.length - 1];
  const zeilen = data.jahre[String(year)] ?? [];
  const gesamtzeile = summe(zeilen);
  const gesamtAus = mio(gesamtzeile?.expenses) ?? 0;
  // Das geplante Minus als positive Zahl. Nur wenn beide Seiten dastehen —
  // eine Differenz aus einer fehlenden Zahl wäre erfunden.
  const defizit = gesamtzeile?.revenues != null && gesamtzeile?.expenses != null
    ? Math.max(0, mio(gesamtzeile.expenses - gesamtzeile.revenues) ?? 0)
    : 0;

  const rows: Zeile[] = bereiche(zeilen).map((z) => {
    const kanon = bereichKanon(z.bereich);
    const eintrag = pflichtFuer(z.bereich);
    const befund = kanon.schluessel ? befunde.get(kanon.schluessel) : undefined;
    return {
      z,
      aus: mio(z.expenses) ?? 0,
      // Nur wenn BEIDE Seiten dastehen. Eine fehlende Ertragszeile als Null zu
      // lesen machte aus dem Zuschussbedarf den Bruttoaufwand — und damit aus
      // der Korrektur wieder den Fehler, den sie korrigiert.
      netto: z.expenses != null && z.revenues != null
        ? mio(z.expenses - z.revenues) : null,
      stufe: eintrag?.stufe ?? null,
      was: eintrag?.was ?? null,
      befund,
      urteil: eintrag ? abgleich(eintrag.stufe, befund) : "offen",
    };
  }).sort((a, b) => b.aus - a.aus);

  const proStufe = (s: PflichtStufe) => rows.filter((r) => r.stufe === s);
  const ohneStufe = rows.filter((r) => r.stufe === null);
  const summeAus = (rs: Zeile[]) => rs.reduce((n, r) => n + r.aus, 0);
  /** `null`, sobald einer Zeile die Ertragsseite fehlt — eine Teilsumme wäre
   *  keine Summe. */
  const summeNetto = (rs: Zeile[]) =>
    rs.length && rs.every((r) => r.netto != null)
      ? rs.reduce((n, r) => n + (r.netto ?? 0), 0) : null;

  const freiwillig = proStufe("freiwillig");
  const freiwilligAus = summeAus(freiwillig);
  // Was Streichen tatsächlich brächte: der Zuschussbedarf, nicht der Aufwand.
  // Die eigenen Erträge dieser Bereiche fielen mit weg.
  const freiwilligNetto = summeNetto(freiwillig);
  const reichtNicht = defizit > 0 && freiwilligNetto != null
    && freiwilligNetto > 0 && freiwilligNetto < defizit;

  // Reihenfolge im Balken: das Gestaltbare zuerst. Nicht aus Höflichkeit —
  // nur so beginnt das freiwillige Segment bei null und ist mit der
  // Defizit-Marke (ebenfalls von null gemessen) überhaupt vergleichbar.
  // Stünde es rechts außen, wären zwei Längen auf demselben Balken, die man
  // nicht aneinanderlegen kann.
  const segmente: Anteil[] = [
    ...[...STUFEN].reverse().map((s) => ({
      label: PFLICHT_LABEL[s], wert: summeAus(proStufe(s)), farbe: TON_STUFE[s],
    })),
    { label: "noch nicht eingeordnet", wert: summeAus(ohneStufe), farbe: TON_OFFEN, offen: true },
  ];

  // Der Abgleich — und ehrlich über den Nenner: Bereiche ohne Produktebene
  // sind kein Befund, weder in die eine noch in die andere Richtung. Gezählt
  // wird nur noch, wo beide Seiten AUSEINANDERGEHEN; die Gegenzahl („deckt")
  // war Selbstbestätigung und ist am 16.08. rausgefallen.
  const geprueft = rows.filter((r) => r.urteil !== "offen");
  const weicht = geprueft.filter((r) => r.urteil === "weicht");

  return (
    <Quellenkontext schluessel={QUELLEN} year={year}>
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-1.5 text-[11.5px] text-muted-foreground">
        <Link href="/haushalt" className="hover:text-foreground">Haushalt</Link>
        <ChevronRight className="h-3 w-3" />
        <span className="font-semibold text-foreground">Muss oder kann?</span>
      </div>

      <div className="flex items-start justify-between gap-5">
        <div className="min-w-0">
          <SchrittKicker href="/haushalt/pflicht" />
          <h1 className="mt-1 font-display text-2xl font-bold tracking-tight sm:text-[25px]">Muss oder kann?</h1>
        </div>
        <SchrittPfad href="/haushalt/pflicht" />
      </div>

      {/* Die Bühne (H5-02/H5-09): der Pflichtanteil als die eine Zahl der
          Seite — dieselbe Rechnung wie im Gegenbalken darunter, zu dem das
          Minibild springt. „Pflicht" heißt hier wie überall auf der Seite:
          Stufe „Pflicht" plus „Pflicht mit Spielraum". */}
      {gesamtAus > 0 && (() => {
        const pflichtProzent = ((summeAus(proStufe("pflicht"))
          + summeAus(proStufe("spielraum"))) / gesamtAus) * 100;
        const freiwilligProzent = (freiwilligAus / gesamtAus) * 100;
        return (
          <Seitenbuehne
            kicker={`Anteil an allen Ausgaben · Plan ${year}`}
            zahl={<><ZaehlZahl wert={pflichtProzent} nachkomma={0} />&#8239;% der Ausgaben
              sind Pflicht oder Pflicht mit Spielraum</>}
            sub={weicht.length > 0
              ? `bei ${weicht.length} von ${geprueft.length} Bereichen sieht die Verwaltung es selbst anders`
              : undefined}
            minibild={{
              href: "#ausgabenbild",
              label: "Gegenbalken — klickt zum ganzen Bild",
              skizze: (
                // Jede Zeile trägt ihr Label selbst (Tim, 26.08.: „viel zu
                // klein, ohne richtige Label") — drei nackte Striche sagten
                // nur dem etwas, der die Legende darunter mitlas.
                [
                  { text: "alle Ausgaben", breite: 100, ton: "var(--sb-blass)" },
                  { text: `Pflichtanteil · ${Math.round(pflichtProzent)} %`, breite: pflichtProzent, ton: "var(--sb-voll)" },
                  { text: `überwiegend freiwillig · ${Math.round(freiwilligProzent)} %`, breite: Math.max(freiwilligProzent, 2.5), ton: "var(--sb-mittel)" },
                ].map((z) => (
                  <span key={z.text} className="flex flex-col gap-[3px]">
                    <span className="text-[9.5px] leading-none text-muted-foreground">{z.text}</span>
                    <span className="block h-3 rounded-[4px]" style={{ width: `${z.breite}%`, background: z.ton }} />
                  </span>
                ))
              ),
            }}
          />
        );
      })()}

      {/* Einstiegstext unter der Bühne, kleiner (Tim, 26.08.) — der Kopf ist
          Titel + Bühne, die Erklärung folgt. */}
      <p className="max-w-[76ch] text-[13px] leading-relaxed text-foreground/85">
        Viele Aufgaben der Stadt sind durch Bundes- oder Landesrecht vorgeschrieben. Der Rat
        entscheidet dann nicht über das Ob, häufig aber noch über die konkrete Ausgestaltung.
        Hier siehst du, wie wir den Spielraum der Bereiche einordnen und wie die Stadt ihn
        selbst beschreibt.
      </p>

      {/* Die Antwort im ersten Bild: der ganze Ausgabenplan in drei Teilen. */}
      <section id="ausgabenbild" className="scroll-mt-20 rounded-2xl border border-border bg-card p-4 shadow-sm">
        <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
          <h2 className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
            Geplante Ausgaben {year}
          </h2>
          <p className="font-display text-[19px] font-bold tabular-nums">
            {deMio(gesamtAus)}<span className="ml-1 text-[12px] font-semibold text-muted-foreground">Mio.&nbsp;€</span>
            <Beleg q="plan" />
          </p>
        </div>
        {/* Der 100-%-Balken folgt seit H4-03 der Gegenbalken-Regel (GB-04,
            `components/grafik/`): Basis sichtbar angeschrieben, Beschriftung
            der Segmente in der Legende (unter 10 % nie im Balken), die
            Defizit-Marke als Signal-Strich mit Erklärsatz. */}
        <Gegenbalken
          className="mt-3"
          zeilen={[{ titel: `Alle Ausgaben ${year}`, segmente }]}
          basis={gesamtAus}
          marke={defizit > 0 && gesamtAus > 0 ? {
            wert: defizit,
            label: `Der Strich markiert das geplante Minus: ${deMio(defizit)} Mio. €, `
              + `also ${((defizit / gesamtAus) * 100).toLocaleString("de-DE", { maximumFractionDigits: 1 })} % derselben Ausgaben.`,
          } : undefined}
        />
        <p className="mt-3 border-t border-border/60 pt-3 text-[12.5px] leading-relaxed text-foreground/85">
          {reichtNicht ? (
            <>
              <strong>Würde der Rat alle überwiegend freiwilligen Bereiche vollständig streichen,
              entspräche die Entlastung nicht ihren gesamten Ausgaben von {deMio(freiwilligAus)} Mio. €.</strong>{" "}
              Auch ihre eigenen Erträge fielen weg; übrig bliebe ihr Zuschussbedarf von{" "}
              {deMio(freiwilligNetto)}&nbsp;Mio.&nbsp;€<Beleg q="plan" /> — rund{" "}
              {Math.round((freiwilligNetto / defizit) * 100)}&nbsp;% des geplanten Minus. Selbst
              vollständige Kürzungen in diesen Bereichen würden das Defizit also nicht allein ausgleichen.
            </>
          ) : (
            <>
              Der Balken zeigt <strong>Aufwendungen</strong>, das Minus ist ein <strong>Saldo</strong> — beides
              lässt sich nicht gegeneinander rechnen. Striche der Rat die überwiegend freiwilligen
              Bereiche, fielen ihre eigenen Erträge mit weg
              {freiwilligNetto != null ? (
                <>; übrig bliebe ihr Zuschussbedarf von{" "}
                {deMio(freiwilligNetto)}&nbsp;Mio.&nbsp;€<Beleg q="plan" />.</>
              ) : <>.</>}
            </>
          )}
        </p>
      </section>

      {/* Der Befund, den es vor der Produktebene nicht geben konnte.

          DIE ÜBEREINSTIMMUNGS-QUOTE IST AM 16.08. RAUSGEFLOGEN. Hier stand
          „Bei 6 von 9 Bereichen deckt sich das mit unserer Einordnung" — eine
          Zahl, die nur uns bestätigt: Sie sagt der Leserin nichts über den
          Haushalt, sondern über die Güte unserer Redaktion
          (DESIGNSPRACHE.md § 7). Die ABWEICHUNG ist das Gegenteil davon und
          bleibt deshalb, mitsamt ihrer Bezugsgröße: Wo unsere Stufe der
          Selbstauskunft der Stadt widerspricht, ist das eine echte Auskunft
          über die Aufgabe — und die interessanteste der Seite. Der Abgleich
          selbst läuft unverändert (`abgleich()` in `lib/haushalt-pflicht.ts`,
          Doku: „Die Einordnung ist redaktionell — aber nicht mehr
          ungeprüft"). */}
      {produktJahr && geprueft.length > 0 && (
        <section className="rounded-2xl border border-border bg-card p-4 shadow-sm">
          <div className="flex items-center gap-2">
            <Scale className="h-3.5 w-3.5 text-muted-foreground" />
            <h2 className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
              Die Selbstauskunft der Stadt · Stand {produktJahr}
            </h2>
          </div>
          <p className="mt-2 text-[13px] leading-relaxed text-foreground/90">
            Die Stadt gibt in den Teilhaushaltsplänen zu jeder Aufgabe selbst an, wie viel Spielraum
            sie bei ihr sieht; unten steht das an jeder Zeile neben unserer Einordnung
            <Beleg q="teilhaushalt" /> — <span aria-hidden="true">◇</span> ist ihre Angabe,{" "}
            <span aria-hidden="true">●</span> unsere Zuordnung, jede mit eigenem Marker, weil es
            zwei Quellen sind.
            {/* „weicht ab" statt „widerspricht": Welche der beiden Antworten
                die richtige ist, entscheidet die Seite nicht — sie beantworten
                zwei verschiedene Fragen (s. Lotti darunter). */}
            {weicht.length > 0 && (
              <> Bei <strong>{weicht.length} von {geprueft.length} Bereichen</strong> weicht
              diese Angabe von unserer Einordnung ab:{" "}
              {weicht.map((r) => bereichKanon(r.z.bereich).name).join(", ")}.</>
            )}
          </p>
          <p className="mt-1.5 text-[11.5px] leading-relaxed text-muted-foreground">
            Für {rows.length - geprueft.length} von {rows.length} Teilhaushalten gibt es keine Angabe:
            Die Produktebene reicht von {produktVon} bis {produktJahr} und deckt nicht jeden
            Teilhaushalt ab.
            {produktdaten?.abdeckung_prozent != null && (
              <> Die gefundenen Aufgaben erklären{" "}
              {produktdaten.abdeckung_prozent.toLocaleString("de-DE", { maximumFractionDigits: 1 })}
              &nbsp;% der für {produktJahr} geplanten Aufwendungen.</>
            )}{" "}
            Aufgabe für Aufgabe steht es auf der{" "}
            <Link href="/haushalt/produkte" className="font-semibold text-primary">Produktebene</Link>.
          </p>
        </section>
      )}

      {/* Warum die Antworten auseinandergehen — ohne die Zahl zu wiederholen:
          Die steht seit dem 16.08. im Befund darüber. Zweimal dieselbe Quote
          auf einem Bildschirm liest sich wie ein Beleg, den die Seite sich
          selbst ausstellt. Lotti erklärt hier den Mechanismus, nicht die
          Menge. */}
      {weicht.length > 0 && (
        <LottiErklaert
          titel="Zwei Antworten auf dieselbe Frage"
          text={`Unsere Einordnung und die Angabe der Stadt beantworten unterschiedliche Fragen. Wir fragen, ob eine Aufgabe verpflichtend ist. Die Stadt bewertet auf Produktebene, wie stark sich ihre Kosten beeinflussen lassen. Deshalb können beide Einschätzungen voneinander abweichen.`}
        />
      )}

      {STUFEN.map((s) => {
        const gruppe = proStufe(s);
        if (!gruppe.length) return null;
        const gruppeAus = summeAus(gruppe);
        return (
          <section key={s} className="flex flex-col gap-2">
            <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 pt-1">
              <h2 className="flex items-baseline gap-2 font-display text-[17px] font-bold tracking-tight">
                <span
                  aria-hidden="true"
                  className="h-2.5 w-2.5 flex-none translate-y-[1px] rounded-[3px]"
                  style={{ background: TON_STUFE[s] }}
                />
                {PFLICHT_LABEL[s]}
              </h2>
              <p className="text-[12.5px] tabular-nums text-muted-foreground">
                {gruppe.length} {gruppe.length === 1 ? "Bereich" : "Bereiche"} ·{" "}
                <strong className="text-foreground">{deMio(gruppeAus)}&#8239;Mio.&nbsp;€</strong> ·{" "}
                {gesamtAus > 0 ? ((gruppeAus / gesamtAus) * 100).toLocaleString("de-DE", { maximumFractionDigits: 1 }) : "—"}&nbsp;%
                <Beleg q="plan" />
              </p>
            </div>
            <p className="max-w-[74ch] text-[12.5px] leading-relaxed text-muted-foreground">
              {PFLICHT_ERKLAERUNG[s]}
            </p>
            {gruppe.map((r) => (
              <BereichsZeile key={r.z.bereich} r={r} gesamt={gesamtAus} produktJahr={produktJahr} />
            ))}
          </section>
        );
      })}

      {ohneStufe.length > 0 && (
        <section className="flex flex-col gap-2">
          <h2 className="pt-1 font-display text-[17px] font-bold tracking-tight">Noch nicht eingeordnet</h2>
          <p className="max-w-[74ch] text-[12.5px] leading-relaxed text-muted-foreground">
            Diese Bereiche stehen im Plan, aber nicht in unserer Zuordnung — vermutlich ein neuer
            oder umbenannter Teilhaushalt. Sie erscheinen hier, statt stillschweigend aus den
            Summen zu fallen.
          </p>
          {ohneStufe.map((r) => (
            <BereichsZeile key={r.z.bereich} r={r} gesamt={gesamtAus} produktJahr={produktJahr} />
          ))}
        </section>
      )}

      {/* Der Schlusshinweis stand bis 17.08. als nackter Absatz unter lauter
          Karten — 470 Zeichen am Stück, ohne Rahmen, ohne Kicker, als hätte
          ihn jemand vergessen einzuräumen. Er sagt zwei verschiedene Dinge
          (woher die Summen kommen, woher die Einordnung kommt) und steht
          deshalb jetzt als zwei Sätze in der Kartengrammatik der Seite. Kein
          Wort ist weggefallen. */}
      <section className="rounded-2xl border border-border bg-card p-4 shadow-sm">
        <h2 className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
          Wie sicher ist diese Einordnung?
        </h2>
        <p className="mt-2 max-w-[80ch] text-[12.5px] leading-relaxed text-foreground/85">
          Die Summen stammen aus dem beschlossenen Haushaltsplan<Beleg q="plan" />. Die Zuordnung
          zu Pflicht und Kür ist dagegen eine <em>redaktionelle Einschätzung auf Ebene ganzer
          Teilhaushalte</em> — eine amtliche gibt es nicht, und in fast jedem Bereich steckt beides.
        </p>
        <p className="mt-2 max-w-[80ch] text-[12.5px] leading-relaxed text-foreground/85">
          Was die Stadt selbst angibt, steht bei jedem Bereich daneben; wo es unserer Einschätzung
          widerspricht, sagen wir das, statt die Einschätzung nachzuziehen. Genauer wird es je
          Aufgabe auf der{" "}
          <Link href="/haushalt/produkte" className="font-semibold text-primary">Produktebene</Link>.
        </p>
      </section>

      <SchrittWeiter href="/haushalt/pflicht" />

      <Quellenverzeichnis schluessel={QUELLEN} />
    </div>
    </Quellenkontext>
  );
}

/** Die Doppel-Kennzeichnung (H4-03): „Muss oder kann?" hat auf dieser Seite
 *  zweierlei Quelle — die Selbstauskunft der Stadt aus den Teilhaushalts-
 *  plänen und unsere redaktionelle Zuordnung. Eine Farbe allein sagt nicht,
 *  WESSEN Urteil sie kodiert; deshalb tragen beide Antworten je einen
 *  eigenen Marker: ◇ (offen — die Angabe kommt von außen) für die Stadt,
 *  ● (gefüllt — unsere Setzung) für uns. Die Zeile steht auf jedem Gerät bei
 *  jedem Bereich und wird nie zusammengefasst — auch „keine Angabe" ist eine
 *  Auskunft. Reine Text-Marker, keine Farben: Es gibt nichts zu bewerten. */
function DoppelMarker({ stadt, wir }: { stadt: string | null; wir: string | null }) {
  return (
    <p className="mt-1.5 flex flex-wrap items-baseline gap-x-3.5 gap-y-0.5 font-mono text-[9.5px] font-medium uppercase tracking-[0.09em] text-muted-foreground">
      <span className="inline-flex items-baseline gap-1">
        <span aria-hidden="true" className="text-[11px]">◇</span>
        <span>
          <span className="sr-only">Selbstauskunft der </span>Stadt:{" "}
          <span className={cn("font-semibold", stadt ? "text-foreground/85" : "font-normal italic")}>
            {stadt ?? "keine Angabe"}
          </span>
        </span>
      </span>
      <span className="inline-flex items-baseline gap-1">
        <span aria-hidden="true" className="text-[11px]">●</span>
        <span>
          <span className="sr-only">unsere Zuordnung — </span>wir:{" "}
          <span className={cn("font-semibold", wir ? "text-foreground/85" : "font-normal italic")}>
            {wir ?? "noch offen"}
          </span>
        </span>
      </span>
    </p>
  );
}

/** Ein Teilhaushalt: was er kostet, wie wir ihn einordnen — und was die Stadt
 *  selbst zu seinen Aufgaben angibt.
 *
 *  AUFGERÄUMT AM 17.08., drei Dinge, jedes mit demselben Grund — dieselbe
 *  Auskunft stand mehrfach in derselben Karte:
 *
 *   1. Der Kicker „Was die Stadt selbst angibt · Stand 2025" ist weg. Er stand
 *      13 Mal auf der Seite und sagte, was zwei Zeilen tiefer im Satz noch
 *      einmal steht („… sieht die Stadt kaum Spielraum"). Der Jahresstempel
 *      geht dabei nicht verloren: Er wandert IN den Satz, also an die Aussage,
 *      zu der er gehört — der Kopf der Seite nennt ihn ohnehin.
 *   2. „weicht ab" steht jetzt oben an der Überschrift statt in der Mitte der
 *      Karte. Es ist die interessanteste Auskunft der Zeile und lag unter dem
 *      Betrag, wo man nicht danach sucht.
 *   3. Die beiden Balken sind auseinandergezogen. Sie sahen gleich aus und
 *      meinten Verschiedenes: der obere die Größe des Bereichs, der untere die
 *      Zusammensetzung seiner Aufgaben nach der Angabe der Stadt. Der untere
 *      trägt deshalb das ◇ des Doppelmarkers vorweg — dasselbe Zeichen, das
 *      zwei Zeilen höher „das kommt von der Stadt" bedeutet.
 *
 *  UND NOCH EINMAL AM 24.08. („irgendwie kann ich da schlecht irgendetwas
 *  ablesen", Tim) — das Auseinanderziehen hatte die Balken getrennt, aber
 *  keinen von beiden lesbar gemacht:
 *
 *   1. Der Größen-Balken maß „Anteil am größten Bereich" — ein Nenner, der
 *      nirgends auf der Seite stand. Jetzt misst er den Anteil an ALLEN
 *      geplanten Ausgaben des Jahres, und genau diese Zahl steht als Text
 *      an seinem Ende. Balkenlänge und Beschriftung sind dieselbe Zahl —
 *      erst das macht aus dem Streifen eine Auskunft (die Regel aus
 *      `anteilsbalken.tsx`: ein Anteil ohne Bezugsgröße ist kein Wert,
 *      sondern ein Gefühl). Nebeneffekt: Alle 13 Balken der Seite teilen
 *      jetzt EINEN Maßstab, auch über die Abschnitte hinweg.
 *   2. Der Selbstauskunft-Streifen ist weg, wo er nichts sagt — siehe
 *      `MISCHUNG_AB` und `<Selbstauskunft>`. */
function BereichsZeile({ r, gesamt, produktJahr }: {
  r: Zeile;
  /** Geplante Aufwendungen ALLER Bereiche in Mio. € — der eine Nenner. */
  gesamt: number;
  produktJahr: number | null;
}) {
  const kanon = bereichKanon(r.z.bereich);
  const befund = r.befund;
  const anteil = gesamt > 0 ? Math.min((r.aus / gesamt) * 100, 100) : 0;
  // Zwei Nachkommastellen erst unter 0,1 %: „0,05 %" (Stiftungen, 0,4 Mio.)
  // ist eine Auskunft, „0 %" neben einem sichtbaren Balken wäre ein
  // Widerspruch auf derselben Zeile.
  const anteilText = anteil.toLocaleString("de-DE", {
    maximumFractionDigits: anteil < 0.1 ? 2 : 1,
  });
  return (
    <div className="rounded-xl border border-border bg-card p-3.5 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-x-3 gap-y-1">
        <div className="min-w-0 flex-1">
          <span className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
            {/* `break-words` UND `min-w-0`: „Personal/Organisation/
                Digitalisierung/IT" ist ein einziges Wort ohne Leerzeichen. Ohne
                Umbruchfreigabe lief es auf 375 px in den Betrag hinein — Name
                und Zahl klebten ohne Lücke aneinander („…/IT47,2 Mio."). Als
                Flex-Element (seit das „weicht ab" danebensteht) reicht
                `break-words` allein nicht: Ein Flex-Kind schrumpft ohne
                `min-w-0` nicht unter seine längste unteilbare Stelle. */}
            <Link
              href={`/haushalt/bereich?name=${bereichSlug(r.z.bereich)}`}
              className="min-w-0 text-[13px] font-bold leading-snug break-words hover:text-primary"
            >
              {kanon.name}
            </Link>
            {r.urteil === "weicht" && (
              <span className="flex-none rounded-full bg-signal/10 px-2 py-0.5 text-[10.5px] font-semibold text-signal">
                weicht ab
              </span>
            )}
          </span>
          {r.was ? (
            <p className="mt-1 text-[12px] leading-relaxed text-muted-foreground">{r.was}</p>
          ) : (
            <p className="mt-1 text-[12px] italic text-muted-foreground">Noch nicht eingeordnet</p>
          )}
          <DoppelMarker
            stadt={befund?.dominant ? SPIELRAUM_TEXT[befund.dominant].kurz : null}
            wir={r.stufe ? PFLICHT_LABEL[r.stufe] : null}
          />
        </div>
        <span className="flex-none font-display text-[17px] font-bold tabular-nums">
          {deMio(r.aus)}<span className="text-[11px] font-semibold text-muted-foreground">&#8239;Mio.&nbsp;€</span>
        </span>
      </div>
      {/* Die Vergleichszeile nach RG-04 (Balken h 6 · Wert): Länge und
          angeschriebene Zahl sind DERSELBE Anteil an DEMSELBEN Nenner. Die
          Beschriftung hat eine feste Breite, damit die Spur in jeder Karte
          gleich lang ist — sonst wäre „20 %" nicht überall gleich viel
          Pixel und der Karten-übergreifende Vergleich gelogen. */}
      <div className="mt-2 flex items-center gap-2.5">
        <div aria-hidden="true" className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
          <div
            className="h-full rounded-full"
            style={{
              width: `${anteil}%`,
              // Sichtbar auch bei 0,05 % — ein verschwundener Balken läse
              // sich als „gibt es nicht".
              minWidth: 3,
              background: r.stufe ? TON_STUFE[r.stufe] : TON_OFFEN,
            }}
          />
        </div>
        <span className="w-[7.5rem] flex-none text-right text-[10.5px] leading-tight tabular-nums text-muted-foreground">
          {anteilText}&nbsp;% aller Ausgaben
        </span>
      </div>

      {/* Die Angabe der Stadt steht auf einer eigenen, abgesetzten Fläche.
          Vorher trennte sie nur eine Haarlinie vom Ausgabenbalken darüber —
          zwei Balken derselben Höhe und Farbfamilie direkt untereinander, die
          Verschiedenes messen (oben die Größe des Bereichs, unten die
          Zusammensetzung seiner Aufgaben). Die Fläche sagt: Ab hier spricht
          eine andere Quelle. */}
      {produktJahr && (
        <div className="mt-3 rounded-lg border border-border/70 bg-muted/40 p-2.5">
          {befund && befund.dominant ? (
            <Selbstauskunft befund={befund} year={produktJahr} />
          ) : (
            <p className="text-[12px] leading-relaxed text-muted-foreground">
              {befund
                ? `Die ${befund.produkte} Aufgaben dieses Bereichs tragen für ${produktJahr} keine eindeutige Angabe.`
                : `Für ${produktJahr} liegt kein auslesbarer Teilhaushaltsplan dieses Bereichs vor — die Produktebene deckt ihn nicht ab.`}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

/** Was die Stadt selbst angibt — als Satz, und nur dort als Grafik, wo eine
 *  Grafik etwas zu zeigen hat.
 *
 *  Bis 24.08. stand hier IMMER ein 6-px-Streifen. Der zeigte die
 *  Zusammensetzung der Angaben — aber 9 von 10 Bereichen sind zu ≥ 93 %
 *  EINE Stufe: ein einfarbiger Balken ohne Legende, der wie eine
 *  Fortschrittsanzeige aussah und exakt die Zahl wiederholte, die im Satz
 *  darunter schon stand. Jetzt gilt: Erst wenn die Angaben sich wirklich
 *  verteilen (`MISCHUNG_AB`), kommt der volle `<Anteilsbalken>` MIT Legende
 *  und Beträgen — bei „Klima/Umwelt/…" (29/48/23) ist genau das die
 *  Auskunft der Karte. Der Satz nennt dann keine eigene Quote mehr: Eine
 *  Mehrheit von 48 % als „die" Antwort auszugeben, während der Balken
 *  darüber drei zeigt, wäre die halbe Wahrheit in Fettdruck. */
function Selbstauskunft({ befund, year }: { befund: SpielraumBefund; year: number }) {
  const dominant = befund.dominant!;
  const anteil = Math.round(befund.anteil[dominant] * 100);
  const groesste = befund.groesste;
  const gemischt = (["niedrig", "mittel", "hoch", "ohne"] as const)
    .filter((s) => befund.anteil[s] >= MISCHUNG_AB).length >= 2;
  // Beträge statt nackter Prozente in der Legende: `anteil` ist normiert,
  // multipliziert mit dem Aufwand des Bereichs wird daraus wieder Geld —
  // der Anteilsbalken rechnet die Prozente selbst und schreibt beides an.
  const aufwandMio = befund.expense / 1e6;
  const segmente: Anteil[] = [
    ...(["niedrig", "mittel", "hoch"] as Spielraum[]).map((s) => ({
      label: SPIELRAUM_TEXT[s].kurz, wert: befund.anteil[s] * aufwandMio, farbe: TON_SPIELRAUM[s],
    })),
    { label: "ohne Angabe", wert: befund.anteil.ohne * aufwandMio, farbe: TON_OFFEN, offen: true },
  ];
  // Das ◇ klammert den ganzen Block: Es ist dasselbe Zeichen wie im
  // Doppelmarker und sagt in einem Glyph, wessen Antwort hier steht —
  // egal ob sie als Satz oder als Balken kommt.
  return (
    <div className="flex gap-2">
      <span aria-hidden="true" className="flex-none translate-y-[3px] text-[11px] leading-none text-muted-foreground">
        ◇
      </span>
      <div className="min-w-0 flex-1">
        {gemischt && (
          <Anteilsbalken className="mb-2" segmente={segmente} gesamt={aufwandMio} hoehe={10} />
        )}
        <p className="text-[12px] leading-relaxed text-foreground/85">
          {gemischt ? (
            <>
              Hier verteilen sich die Angaben der Stadt über mehrere Stufen
              ({befund.produkte} {befund.produkte === 1 ? "Aufgabe" : "Aufgaben"}, Stand {year}).
            </>
          ) : (
            <>
              Bei <strong className="tabular-nums">{anteil}&nbsp;%</strong> der Ausgaben dieses Bereichs
              sieht die Stadt <strong>{SPIELRAUM_TEXT[dominant].kurz}</strong> ({befund.produkte}{" "}
              {befund.produkte === 1 ? "Aufgabe" : "Aufgaben"}, Stand {year}).
            </>
          )}
          <Beleg q="teilhaushalt" />
        </p>
        {groesste?.auftragsgrundlage && (
          <details className="group mt-1.5">
            <summary className={cn(
              "cursor-pointer list-none text-[11.5px] font-semibold text-primary",
              "marker:content-none",
            )}>
              <span className="group-open:hidden">Worauf der größte Posten beruht</span>
              <span className="hidden group-open:inline">Weniger anzeigen</span>
            </summary>
            <div className="mt-1.5 rounded-lg border border-border bg-muted/40 p-2.5">
              <p className="text-[11.5px] font-semibold leading-snug">
                {groesste.produkt_name}
                <span className="ml-1.5 font-normal tabular-nums text-muted-foreground">
                  {amount(groesste.expenses).wert}&nbsp;{amount(groesste.expenses).einheit}
                </span>
              </p>
              {/* Wortlaut des Teilhaushaltsplans, ungekürzt: Die Rechtsgrundlagen
                  sind der Beleg dafür, ob eine Aufgabe von außen vorgegeben ist
                  oder auf einem Ratsbeschluss beruht — sie zu paraphrasieren
                  hieße, genau die Auskunft wegzuwerfen. */}
              <p className="mt-1 text-[11.5px] leading-relaxed text-muted-foreground">
                {groesste.auftragsgrundlage}
              </p>
              <Link
                href={`/haushalt/produkte?nr=${encodeURIComponent(groesste.produkt_nr)}`}
                className="mt-1.5 inline-block text-[11.5px] font-semibold text-primary"
              >
                Steckbrief dieser Aufgabe
              </Link>
            </div>
          </details>
        )}
      </div>
    </div>
  );
}
