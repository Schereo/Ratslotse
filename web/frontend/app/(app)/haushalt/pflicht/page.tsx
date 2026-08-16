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
  HaushaltDaten, HaushaltZeile, ProdukteAntwort, SPIELRAUM_TEXT, Spielraum,
  bereiche, bereichSlug, betrag, deMio, jahreSortiert, mio, summe,
} from "@/lib/haushalt";
import { BereichSchluessel, bereichKanon } from "@/lib/haushalt-bereiche";
import {
  Abgleich, PFLICHT_ERKLAERUNG, PFLICHT_LABEL, PflichtStufe, SpielraumBefund,
  abgleich, pflichtFuer, spielraumBefunde,
} from "@/lib/haushalt-pflicht";
import { Anteilsbalken, AnteilsbalkenSchmal, type Anteil } from "@/components/haushalt/anteilsbalken";
import { Beleg, Quellenkontext, Quellenverzeichnis } from "@/components/haushalt/quelle";
import type { QuellenSchluessel } from "@/lib/haushalt-quellen";
import { LottiErklaert } from "@/components/haushalt/lotti-erklaert";
import { cn } from "@/lib/utils";

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

export default function PflichtPage() {
  const { data, loading } = useFetch<HaushaltDaten>("/council/haushalt");

  // Die Produktebene reicht nicht bis ins Planjahr — welches Jahr sie trägt,
  // sagt die Übersicht. Deshalb erst der zweite Aufruf, und nur wenn es
  // überhaupt eines gibt (`useFetch(null)` überspringt).
  const produktJahr = data?.produkt_jahre?.length ? Math.max(...data.produkt_jahre) : null;
  // Der erste Jahrgang kommt ebenfalls aus den Daten. „2018" als feste Zahl in
  // den Satz zu schreiben hieße, beim nächsten Nachzug still zu lügen.
  const produktVon = data?.produkt_jahre?.length ? Math.min(...data.produkt_jahre) : null;
  const { data: produktdaten } = useFetch<ProdukteAntwort>(
    produktJahr ? `/council/haushalt/produkte?jahr=${produktJahr}` : null,
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
  const jahr = jahre[jahre.length - 1];
  const zeilen = data.jahre[String(jahr)] ?? [];
  const gesamtzeile = summe(zeilen);
  const gesamtAus = mio(gesamtzeile?.aufwendungen) ?? 0;
  // Das geplante Minus als positive Zahl. Nur wenn beide Seiten dastehen —
  // eine Differenz aus einer fehlenden Zahl wäre erfunden.
  const defizit = gesamtzeile?.ertraege != null && gesamtzeile?.aufwendungen != null
    ? Math.max(0, mio(gesamtzeile.aufwendungen - gesamtzeile.ertraege) ?? 0)
    : 0;

  const rows: Zeile[] = bereiche(zeilen).map((z) => {
    const kanon = bereichKanon(z.bereich);
    const eintrag = pflichtFuer(z.bereich);
    const befund = kanon.schluessel ? befunde.get(kanon.schluessel) : undefined;
    return {
      z,
      aus: mio(z.aufwendungen) ?? 0,
      // Nur wenn BEIDE Seiten dastehen. Eine fehlende Ertragszeile als Null zu
      // lesen machte aus dem Zuschussbedarf den Bruttoaufwand — und damit aus
      // der Korrektur wieder den Fehler, den sie korrigiert.
      netto: z.aufwendungen != null && z.ertraege != null
        ? mio(z.aufwendungen - z.ertraege) : null,
      stufe: eintrag?.stufe ?? null,
      was: eintrag?.was ?? null,
      befund,
      urteil: eintrag ? abgleich(eintrag.stufe, befund) : "offen",
    };
  }).sort((a, b) => b.aus - a.aus);

  const groesster = rows[0]?.aus || 1;
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
    <Quellenkontext schluessel={QUELLEN} jahr={jahr}>
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-1.5 text-[11.5px] text-muted-foreground">
        <Link href="/haushalt" className="hover:text-foreground">Haushalt</Link>
        <ChevronRight className="h-3 w-3" />
        <span className="font-semibold text-foreground">Muss oder kann?</span>
      </div>

      <div>
        <h1 className="font-display text-2xl font-bold tracking-tight sm:text-[25px]">Muss oder kann?</h1>
        <p className="mt-2 max-w-[66ch] text-sm leading-relaxed text-foreground/90">
          Über einen großen Teil des Haushalts kann der Rat gar nicht frei entscheiden — Bundes-
          und Landesgesetze schreiben die Aufgaben vor. Hier steht, welcher Bereich wie viel
          Spielraum lässt, und wie die Stadt selbst das sieht.
        </p>
      </div>

      {/* Die Antwort im ersten Bild: der ganze Ausgabenplan in drei Teilen. */}
      <section className="rounded-2xl border border-border bg-card p-4 shadow-sm">
        <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
          <h2 className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
            Geplante Ausgaben {jahr}
          </h2>
          <p className="font-display text-[19px] font-bold tabular-nums">
            {deMio(gesamtAus)}<span className="ml-1 text-[12px] font-semibold text-muted-foreground">Mio.&nbsp;€</span>
            <Beleg q="plan" />
          </p>
        </div>
        <Anteilsbalken
          className="mt-3"
          segmente={segmente}
          gesamt={gesamtAus}
          hoehe={16}
          marke={defizit > 0 && gesamtAus > 0 ? {
            wert: defizit,
            label: `Der Strich markiert das geplante Minus: ${deMio(defizit)} Mio. €, `
              + `also ${((defizit / gesamtAus) * 100).toLocaleString("de-DE", { maximumFractionDigits: 1 })} % derselben Ausgaben.`,
          } : undefined}
        />
        <p className="mt-3 border-t border-border/60 pt-3 text-[12.5px] leading-relaxed text-foreground/85">
          {reichtNicht ? (
            <>
              <strong>Striche der Rat alles überwiegend Freiwillige, spart das nicht {deMio(freiwilligAus)} Mio. €.</strong>{" "}
              Die eigenen Erträge dieser Bereiche fielen mit weg; übrig bliebe ihr Zuschussbedarf von{" "}
              {deMio(freiwilligNetto)}&nbsp;Mio.&nbsp;€<Beleg q="plan" /> — rund{" "}
              {Math.round((freiwilligNetto / defizit) * 100)}&nbsp;% des geplanten Minus. Das ist kein
              Argument gegen Sparen, sondern gegen die Erwartung, dass es dort allein gelingt.
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
            <Beleg q="teilhaushalt" />.
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
          text={`Wir ordnen ganze Teilhaushalte ein, die Stadt beantwortet eine etwas andere Frage: nicht „muss es diese Aufgabe geben?“, sondern „lassen sich ihre Kosten beeinflussen?“. Dass beide Antworten auseinanderfallen, ist deshalb keine Panne — dort lohnt das Nachlesen am meisten.`}
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
              <BereichsZeile key={r.z.bereich} r={r} groesster={groesster} produktJahr={produktJahr} />
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
            <BereichsZeile key={r.z.bereich} r={r} groesster={groesster} produktJahr={produktJahr} />
          ))}
        </section>
      )}

      <p className="max-w-[86ch] text-[11.5px] leading-relaxed text-muted-foreground">
        <strong>Wie sicher ist diese Einordnung?</strong> Die Summen stammen aus dem beschlossenen
        Haushaltsplan. Die Zuordnung zu Pflicht und Kür ist dagegen eine{" "}
        <em>redaktionelle Einschätzung auf Ebene ganzer Teilhaushalte</em> — eine amtliche gibt es
        nicht, und in fast jedem Bereich steckt beides. Was die Stadt selbst angibt, steht bei jedem
        Bereich daneben; wo es unserer Einschätzung widerspricht, sagen wir das, statt die
        Einschätzung nachzuziehen. Genauer wird es je Aufgabe auf der{" "}
        <Link href="/haushalt/produkte" className="font-semibold text-primary">Produktebene</Link>.
      </p>

      <Quellenverzeichnis schluessel={QUELLEN} />
    </div>
    </Quellenkontext>
  );
}

/** Ein Teilhaushalt: was er kostet, wie wir ihn einordnen — und was die Stadt
 *  selbst zu seinen Aufgaben angibt. */
function BereichsZeile({ r, groesster, produktJahr }: {
  r: Zeile; groesster: number; produktJahr: number | null;
}) {
  const kanon = bereichKanon(r.z.bereich);
  const befund = r.befund;
  return (
    <div className="rounded-xl border border-border bg-card p-3.5 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-x-3 gap-y-1">
        <div className="min-w-0 flex-1">
          {/* `break-words`: „Personal/Organisation/Digitalisierung/IT" ist ein
              einziges Wort ohne Leerzeichen. Ohne Umbruchfreigabe lief es auf
              375 px in den Betrag hinein — Name und Zahl klebten ohne Lücke
              aneinander („…/IT47,2 Mio."). */}
          <Link
            href={`/haushalt/bereich?name=${bereichSlug(r.z.bereich)}`}
            className="text-[13px] font-bold leading-snug break-words hover:text-primary"
          >
            {kanon.name}
          </Link>
          {r.was ? (
            <p className="mt-1 text-[12px] leading-relaxed text-muted-foreground">{r.was}</p>
          ) : (
            <p className="mt-1 text-[12px] italic text-muted-foreground">Noch nicht eingeordnet</p>
          )}
        </div>
        <span className="flex-none font-display text-[17px] font-bold tabular-nums">
          {deMio(r.aus)}<span className="text-[11px] font-semibold text-muted-foreground">&#8239;Mio.</span>
        </span>
      </div>
      <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-muted">
        <div
          className="h-full rounded-full"
          style={{
            width: `${Math.min((r.aus / groesster) * 100, 100)}%`,
            background: r.stufe ? TON_STUFE[r.stufe] : TON_OFFEN,
          }}
        />
      </div>

      {produktJahr && (
        <div className="mt-3 border-t border-border/60 pt-2.5">
          <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
            <p className="font-mono text-[9.5px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
              Was die Stadt selbst angibt · Stand {produktJahr}
            </p>
            {r.urteil === "weicht" && (
              <span className="rounded-full bg-signal/10 px-2 py-0.5 text-[10.5px] font-semibold text-signal">
                weicht ab
              </span>
            )}
          </div>
          {befund && befund.dominant ? (
            <Selbstauskunft befund={befund} />
          ) : (
            <p className="mt-1.5 text-[12px] leading-relaxed text-muted-foreground">
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

function Selbstauskunft({ befund }: { befund: SpielraumBefund }) {
  const segmente: Anteil[] = [
    ...(["niedrig", "mittel", "hoch"] as Spielraum[]).map((s) => ({
      label: SPIELRAUM_TEXT[s].kurz, wert: befund.anteil[s], farbe: TON_SPIELRAUM[s],
    })),
    { label: "ohne Angabe", wert: befund.anteil.ohne, farbe: TON_OFFEN, offen: true },
  ];
  const dominant = befund.dominant!;
  const anteil = Math.round(befund.anteil[dominant] * 100);
  const groesste = befund.groesste;
  return (
    <>
      <AnteilsbalkenSchmal
        className="mt-2"
        segmente={segmente}
        gesamt={1}
        beschriftung={segmente
          .filter((s) => s.wert > 0)
          .map((s) => `${s.label} ${Math.round(s.wert * 100)} %`)
          .join(", ")}
      />
      <p className="mt-1.5 text-[12px] leading-relaxed text-foreground/85">
        Bei <strong className="tabular-nums">{anteil}&nbsp;%</strong> der Ausgaben dieses Bereichs
        sieht die Stadt <strong>{SPIELRAUM_TEXT[dominant].kurz}</strong> ({befund.produkte}{" "}
        {befund.produkte === 1 ? "Aufgabe" : "Aufgaben"}).
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
                {betrag(groesste.aufwendungen).wert}&nbsp;{betrag(groesste.aufwendungen).einheit}
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
    </>
  );
}
