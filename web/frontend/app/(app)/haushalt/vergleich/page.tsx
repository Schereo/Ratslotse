"use client";

// /haushalt/vergleich — „Steht Oldenburg besser da als Osnabrück?"
//
// Diese Seite ist aus einer Absage entstanden. Der Entwurf sah einen breiten
// Städtevergleich vor: Ausgaben, Personal, Schulden je Einwohner, Stadt gegen
// Stadt. Die Prüfung hat ihn abgelehnt, und zwar nicht wegen fehlender Daten,
// sondern weil die Aussage nicht trägt — ein Vergleich von Kernhaushalten
// misst zuerst, wie weit eine Stadt ausgelagert hat.
//
// Statt die Seite zu streichen, zeigt sie jetzt beides: die wenigen Größen,
// die wirklich vergleichbar sind, und die Erklärung, warum die anderen es
// nicht sind. Der zweite Teil ist der wertvollere. Eine Leserin, die danach
// versteht, warum „Oldenburg gibt X je Kopf aus, Osnabrück Y" eine
// irreführende Zahl ist, hat mehr gewonnen als durch die Zahl selbst.
//
// Leserichtung: die Frage → was sich vergleichen lässt (Steuerkraft,
// Hebesätze, Steuereinnahmekraft) → warum die Ausgaben NICHT dazugehören,
// belegt aus dem eigenen Ratsinformationssystem → wen man überhaupt
// vergleichen würde → was hier bewusst fehlt → Quellen.
//
// DER BELEG IST DER KERN. Die Stadt Oldenburg hat diesen Vergleich 2018 auf
// Antrag der FDP-Fraktion selbst angestellt und im selben Dokument entwertet.
// Das ist die beste Quelle zum Fallstrick, die es geben kann: keine Meinung
// dieses Projekts, sondern die Kämmerei über ihre eigene Tabelle. Deshalb
// steht das Zitat wörtlich da, mit Verweis auf den Vorgang in unserem
// Bestand und auf beide Originaldokumente.
//
// KEINE BEWERTUNGSFARBEN (components/grafik/hantel.tsx) — hier besonders:
// Ob eine hohe Gewerbesteuer Stärke oder Abhängigkeit ist, ist die Frage,
// die die Seite offenlässt. Grün und Rot beantworteten sie ungefragt.

import Link from "next/link";
import { ArrowRight, ExternalLink, FileText } from "lucide-react";
import { useFetch } from "@/lib/use-fetch";
import { decisionHref } from "@/lib/routes";
import {
  AUSGLIEDERUNGEN_2018, Herkunft, ROLLEN, VergleichDaten, WOLFSBURG,
  ZITAT_VERWALTUNG, antragAnlage, antwortAnlage, balken, herkunftVon,
  juengstesJahr, platzVonOldenburg, reihe, steuerkraftJeEinwohner, change,
} from "@/lib/haushalt-vergleich";
import { Staedtevergleich, Zeitreihe } from "@/components/haushalt/staedtevergleich";
import { SlopePaar, type SlopePaarZeile } from "@/components/grafik/slope-paar";
import { Beleg, Quellenkontext, Quellenverzeichnis } from "@/components/haushalt/quelle";
import { LottiErklaert } from "@/components/haushalt/lotti-erklaert";
import { GlossaryText } from "@/components/glossary-text";
import { SchrittKicker, SchrittWeiter } from "@/components/haushalt/schritt-weiter";
import { SchrittPfad } from "@/components/haushalt/schritt-pfad";
import { Seitenbuehne, ZaehlZahl } from "@/components/haushalt/seitenbuehne";

const QUELLEN = ["lsn_finanzausgleich", "lsn_realsteuern", "vergleich_2018"] as const;

/** Wo eine Angabe im Dokument steht — dieselbe Bauart wie auf der
 *  Konzern-Seite: Abschnitt und Stand, sonst nichts.
 *
 *  Unsere Proben und ihr Messwert standen bis 16.08. daneben, auf dieser
 *  Seite gleich dreimal. Sie sind raus (DESIGNSPRACHE.md § 7) — sie laufen
 *  weiter, sie stehen in der Technik-Doku, aber sie sagen einer Leserin
 *  nichts über die Steuerkraft Oldenburgs. */
function Fundstelle({ h }: { h: Herkunft | null }) {
  if (!h?.citation) return null;
  return (
    <div className="mt-3 border-t border-dashed border-border pt-2.5">
      <p className="font-mono text-[9.5px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
        Woher diese Zahlen kommen
      </p>
      <p className="mt-1 max-w-[86ch] text-[11.5px] leading-relaxed text-muted-foreground">
        {h.citation}{h.stand ? ` · ${h.stand}` : ""}
      </p>
    </div>
  );
}

function Abschnitt({ kicker, zusatz, id, children }: {
  kicker: string; zusatz?: string; id?: string; children: React.ReactNode;
}) {
  // `@container`: Der Inhalt eines Abschnitts richtet seine Spaltenzahl am
  // eigenen Platz aus, nicht an der Fensterbreite — am Desktop liegt die Karte
  // neben der 240-px-Seitenleiste, auf dem iPad nicht (Designsprache §4).
  return (
    <section id={id} className="@container/section scroll-mt-20 rounded-2xl border border-border bg-card p-4 shadow-sm">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
          {kicker}
        </p>
        {zusatz && (
          <p className="font-mono text-[10px] tabular-nums text-muted-foreground">{zusatz}</p>
        )}
      </div>
      {children}
    </section>
  );
}

export default function VergleichSeite() {
  const { data, loading } = useFetch<VergleichDaten>("/council/haushalt/vergleich");

  if (loading) {
    return (
      <div className="flex flex-col gap-3">
        {[0, 1, 2].map((i) => (
          <div key={i} className="h-32 animate-pulse rounded-2xl border border-border bg-card" />
        ))}
      </div>
    );
  }
  if (!data) {
    return (
      <div className="rounded-2xl border border-border bg-card p-5 text-sm leading-relaxed text-muted-foreground">
        Der Städtevergleich lässt sich gerade nicht laden.{" "}
        <Link href="/haushalt" className="font-semibold text-primary">Zurück zum Haushalt</Link>
      </div>
    );
  }

  const skJahr = juengstesJahr(data, "steuerkraft");
  const rsJahr = juengstesJahr(data, "realsteuern");
  const steuerkraft = skJahr ? steuerkraftJeEinwohner(data, skJahr) : [];
  const grundsteuer = rsJahr ? balken(data, "realsteuern", "hebesatz_grundsteuer_b", rsJahr) : [];
  const einnahmekraft = rsJahr ? balken(data, "realsteuern", "steuereinnahmekraft_je_ew", rsJahr) : [];

  // Der Grundsteuer-Sprung (H3-07): Hebesatz vor und nach der Reform 2025 —
  // als Slope-Paar MIT Bruch-Marker, denn über die Reform hinweg sind die
  // Sätze nicht vergleichbar (neue Messbeträge, neue Basis). Nur wenn BEIDE
  // Jahrgänge im Bestand sind; sonst bleibt die Rangliste allein — geraten
  // wird kein Vorjahr.
  //
  // GEMESSEN WIRD AN DER KENNZAHL, NICHT AM JAHRGANG (Fund 17.08.). Vorher
  // stand hier `data.jahre.realsteuern.includes(rsJahr - 1)` — und die Liste
  // führt 2023, 2024, 2025, weil die Steuereinnahmekraft so weit zurückreicht.
  // Die HEBESÄTZE liegen aber nur für 2025 vor. Folge: `rsVorjahr` war 2024,
  // `grundsteuerVorher` leer, der Slope fiel auf die Rangliste zurück — und
  // Kicker („der Sprung zur Reform"), Zeitraum-Angabe („2024 → 2025") und der
  // Satz darunter („nicht automatisch teurer als 2024") versprachen weiter
  // einen Vergleich, den die Seite gar nicht zeigte. Jetzt entscheidet, ob
  // die Werte wirklich dastehen.
  const rsVorjahrKandidat = rsJahr != null
    && (data.jahre.realsteuern ?? []).includes(rsJahr - 1) ? rsJahr - 1 : null;
  const grundsteuerVorher = rsVorjahrKandidat != null
    ? balken(data, "realsteuern", "hebesatz_grundsteuer_b", rsVorjahrKandidat) : [];
  const rsVorjahr = grundsteuerVorher.length > 0 ? rsVorjahrKandidat : null;
  const sprungPaare: SlopePaarZeile[] = grundsteuer
    .flatMap((z): SlopePaarZeile[] => {
      const vorher = grundsteuerVorher.find((v) => v.schluessel === z.schluessel);
      return vorher ? [{
        label: z.name, vorher: vorher.wert, nachher: z.wert,
        hervorgehoben: z.ist_oldenburg,
      }] : [];
    })
    .sort((a, b) => b.vorher - a.vorher);
  const springer = sprungPaare.filter((p) => p.vorher !== p.nachher).length;
  const platz = platzVonOldenburg(steuerkraft);
  const oldenburg = steuerkraft.find((z) => z.ist_oldenburg);

  // Die Herkunft hängt an der Zeile, nicht an der Seite — beide Reihen haben
  // eine eigene (verschiedene Dateien, verschiedene Proben).
  const hSteuerkraft = herkunftVon(data,
    data.werte.find((w) => w.reihe === "steuerkraft")?.herkunft_id);
  const hRealsteuern = herkunftVon(data,
    data.werte.find((w) => w.reihe === "realsteuern")?.herkunft_id);

  const olReihe = reihe(data, "steuereinnahmekraft_je_ew", "403000");
  const wobReihe = reihe(data, "steuereinnahmekraft_je_ew", WOLFSBURG);

  const antwort = antwortAnlage(data.beleg);
  const antrag = antragAnlage(data.beleg);
  const hatZahlen = steuerkraft.length > 0 || grundsteuer.length > 0;

  return (
    <Quellenkontext schluessel={[...QUELLEN]}>
      <div className="flex flex-col gap-4">
        <div className="flex items-start justify-between gap-5">
          <div className="min-w-0">
            <SchrittKicker href="/haushalt/vergleich" />
            <h1 className="mt-1 font-display text-2xl font-bold tracking-tight sm:text-[27px]">
              Steht Oldenburg besser da als Osnabrück?
            </h1>
          </div>
          <SchrittPfad href="/haushalt/vergleich" />
        </div>

        {/* Die Bühne (H5-02/H5-09): der Rangplatz als die eine Zahl der
            Seite — dieselbe Rechnung wie der Satz an der Rangliste, zu der
            das Minibild (die Städte-Leiter) springt. Ohne Steuerkraft-Reihe
            keine Bühne: kein erfundener Platz. */}
        {platz != null && steuerkraft.length > 1 && skJahr && (
          <Seitenbuehne
            kicker="Kreisfreie Städte Niedersachsens"
            zahl={<>Platz <ZaehlZahl wert={platz} /> von {steuerkraft.length} bei
              der Steuerkraft</>}
            sub={`Steuerkraftmesszahl je Einwohner*in · Ausgleichsjahr ${skJahr} — unsere Pro-Kopf-Rechnung, keine amtliche Kennzahl`}
            minibild={{
              href: "#steuerkraft",
              label: "Städte-Leiter — Oldenburg markiert, klickt zur Rangliste",
              skizze: (() => {
                const werte = steuerkraft.map((z) => z.wert);
                const min = Math.min(...werte), max = Math.max(...werte);
                const pos = (w: number) => max > min ? 2 + ((w - min) / (max - min)) * 90 : 50;
                return (
                  <span className="relative block h-[18px]">
                    <span className="absolute inset-x-0 top-2 h-[2px]" style={{ background: "var(--sb-blass)" }} />
                    {steuerkraft.map((z) => z.ist_oldenburg ? (
                      <span key={z.schluessel} className="absolute top-[3px] h-3 w-3 rounded-full shadow-[0_0_0_3px_hsl(var(--primary)/0.18)]"
                        style={{ left: `${pos(z.wert)}%`, background: "var(--sb-voll)" }} />
                    ) : (
                      <span key={z.schluessel} className="absolute top-[5px] h-2 w-2 rounded-full"
                        style={{ left: `${pos(z.wert)}%`, background: "var(--sb-mittel)" }} />
                    ))}
                  </span>
                );
              })(),
            }}
          />
        )}

        {/* Einstiegstext unter der Bühne, kleiner (Tim, 26.08.). */}
        <p className="max-w-[76ch] text-[13px] leading-relaxed text-foreground/85">
          Bei Steuereinnahmen ist ein Vergleich möglich, weil die Werte nach einheitlichen
          Regeln ermittelt werden. Ausgaben lassen sich dagegen nur vergleichen, wenn Städte
          dieselben Aufgaben in ihren Kernhaushalten führen. Diese Seite erklärt beide Fälle.
        </p>

        {/* --- Teil 1: Was sich vergleichen lässt --- */}
        <LottiErklaert
          titel="Warum ausgerechnet Steuern?"
          text={"Steuern erhebt die Stadt selbst. Die Steuerkraft berechnet das Land für "
            + "alle Gemeinden nach derselben Formel. Dadurch sind diese Werte grundsätzlich "
            + "vergleichbar. Bei Ausgaben hängt der Wert dagegen davon ab, welche Aufgaben "
            + "im Kernhaushalt stehen und welche bei Eigenbetrieben oder Gesellschaften."}
        />

        {hatZahlen && skJahr && (
          <Abschnitt id="steuerkraft" kicker="Steuerkraft je Einwohner*in"
            zusatz={`Ausgleichsjahr ${skJahr} · alle acht kreisfreien Städte`}>
            <p className="mt-1.5 max-w-[76ch] text-[13px] leading-relaxed text-foreground/90">
              Die <GlossaryText text="Steuerkraftmesszahl" /> ist die Größe, mit der das
              Land bemisst, wie finanzstark eine Gemeinde ist.
              {oldenburg && platz === 1 && (
                <> Oldenburg liegt mit <strong>{Math.round(oldenburg.wert).toLocaleString("de-DE")}&nbsp;Euro
                je Einwohner*in</strong> an der <strong>Spitze aller acht kreisfreien Städte
                Niedersachsens</strong>.</>
              )}
              {oldenburg && platz !== null && platz > 1 && (
                <> Oldenburg steht mit <strong>{Math.round(oldenburg.wert).toLocaleString("de-DE")}&nbsp;Euro
                je Einwohner*in</strong> auf Platz {platz} von {steuerkraft.length}.</>
              )}
              <Beleg q="lsn_finanzausgleich" />
            </p>
            <div className="mt-3">
              <Staedtevergleich zeilen={steuerkraft} hinweisUnter100k />
            </div>
            <p className="mt-2.5 max-w-[86ch] text-[11.5px] leading-relaxed text-muted-foreground">
              Unsere Rechnung: Steuerkraftmesszahl geteilt durch die Einwohnerzahl, beide
              aus derselben Tabelle. Das Landesamt weist den Pro-Kopf-Wert nicht selbst aus —
              keine amtliche Kennzahl.
            </p>
            <Fundstelle h={hSteuerkraft} />
          </Abschnitt>
        )}

        {grundsteuer.length > 0 && rsJahr && (
          <Abschnitt
            // Der Kicker verspricht nur, was darunter auch steht: den Sprung,
            // solange beide Jahrgänge da sind — sonst schlicht den Hebesatz.
            kicker={rsVorjahr != null
              ? "Grundsteuer B — der Sprung zur Reform"
              : "Grundsteuer B — die Hebesätze"}
            zusatz={rsVorjahr != null ? `${rsVorjahr} → ${rsJahr}` : `${rsJahr}`}
          >
            <p className="mt-1.5 max-w-[76ch] text-[13px] leading-relaxed text-foreground/90">
              Der <GlossaryText text="Hebesatz" /> ist ein Ratsbeschluss und keine
              Bilanzgröße — er ist damit die am klarsten vergleichbare Zahl, die es im
              kommunalen Finanzwesen gibt.
              {sprungPaare.length > 0 && (
                <>
                  {" "}Mit der Reform {rsJahr} springt er in{" "}
                  <strong>
                    {springer === sprungPaare.length
                      ? `allen ${sprungPaare.length}`
                      : `${springer} von ${sprungPaare.length}`}
                  </strong>{" "}
                  kreisfreien Städten — kein Steuerbescheid: Mit der Reform gelten
                  neue Messbeträge, und viele Städte setzten den Hebesatz neu, um
                  aufs gleiche Aufkommen zu kommen.
                </>
              )}
              <Beleg q="lsn_realsteuern" />
            </p>
            <div className="mt-3">
              {sprungPaare.length > 0 && rsVorjahr != null ? (
                // H3-07: Slope mit Bruch-Marker. Der Marker gehört der
                // Komponente — ein Slope über den Systembruch ohne Label ist
                // dort nicht baubar.
                <SlopePaar
                  paare={sprungPaare}
                  vonLabel={`${rsVorjahr}`}
                  bisLabel={`${rsJahr} · Reform`}
                  bruchLabel={`ab ${rsJahr} neue Messbeträge`}
                  einheit="%"
                  beleg={<Beleg q="lsn_realsteuern" />}
                />
              ) : (
                <Staedtevergleich zeilen={grundsteuer} einheit="prozent" />
              )}
            </div>
            {/* Zwei Sätze für zwei Datenlagen. Der Bruch-Hinweis gehört an
                einen Bruch — steht nur ein Jahrgang da, ist die ehrliche
                Auskunft, dass der Vorher-Wert fehlt (Lücken bleiben sichtbar,
                nie stillschweigend). */}
            <p className="mt-2.5 max-w-[76ch] text-[11.5px] leading-relaxed text-muted-foreground">
              {rsVorjahr != null ? (
                <>
                  Über den Bruch hinweg sind die Sätze <strong>nicht</strong> vergleichbar:
                  Zum selben Zeitpunkt haben sich auch die Messbeträge geändert, auf die sie
                  angewendet werden. Ein höherer Satz {rsJahr} heißt deshalb nicht
                  automatisch „teurer als {rsVorjahr}" — er heißt zunächst nur:
                  neue Rechenbasis. Auch ein unveränderter Satz ist eine Entscheidung.
                </>
              ) : (
                <>
                  Das sind die Sätze <strong>nach</strong> der Grundsteuerreform. Ein
                  Vorher-Nachher steht hier nicht: Die Hebesätze liegen uns bisher nur aus
                  dem Realsteuervergleich {rsJahr} vor. Vergleichbar wären sie über die
                  Reform hinweg ohnehin nicht — zum selben Zeitpunkt haben sich auch die
                  Messbeträge geändert, auf die sie angewendet werden. Auch ein
                  unveränderter Satz ist eine Entscheidung.
                </>
              )}
            </p>
            <Fundstelle h={hRealsteuern} />
          </Abschnitt>
        )}

        {einnahmekraft.length > 0 && rsJahr && (
          <Abschnitt kicker="Steuereinnahmekraft je Einwohner*in" zusatz={`${rsJahr}`}>
            <p className="mt-1.5 max-w-[76ch] text-[13px] leading-relaxed text-foreground/90">
              Was am Ende tatsächlich hereinkommt — Realsteuern und die Anteile an
              Einkommen- und Umsatzsteuer, nach Abzug der Gewerbesteuerumlage.
              <Beleg q="lsn_realsteuern" />
            </p>
            <div className="mt-3">
              <Staedtevergleich zeilen={einnahmekraft} />
            </div>
            {olReihe.length > 1 && wobReihe.length > 1 && (
              <div className="mt-3.5 flex flex-col gap-1.5 rounded-xl border border-border bg-muted/30 p-3">
                <p className="max-w-[76ch] text-[12.5px] leading-relaxed text-foreground/90">
                  Ist eine hohe Gewerbesteuer ein Vorteil oder ein Risiko? Wolfsburg
                  beantwortet das eindrucksvoller als jede Erklärung — dort hängt sie an
                  einem einzigen Unternehmen.
                </p>
                <Zeitreihe titel="Oldenburg" punkte={olReihe}
                  change={change(olReihe)} />
                <Zeitreihe titel="Wolfsburg" punkte={wobReihe}
                  change={change(wobReihe)} />
              </div>
            )}
            <Fundstelle h={hRealsteuern} />
          </Abschnitt>
        )}

        {/* --- Teil 2: Der Kern — warum die Ausgaben fehlen --- */}
        <section className="@container/kern rounded-2xl border border-border border-l-[3px] border-l-signal bg-card p-4 shadow-sm">
          <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-signal">
            Warum hier keine Ausgaben stehen
          </p>
          <h2 className="mt-1.5 font-display text-lg font-bold tracking-tight">
            Der naheliegende Vergleich misst die falsche Sache
          </h2>
          {/* Argument links, Beleg rechts — statt untereinander. Vorher endete
              der Fließtext bei 623 px, während der Beleg-Kasten darunter die
              vollen 1104 px nahm: dieselbe Karte behauptete zwei verschiedene
              Textbreiten, und rechts neben dem Argument blieb die halbe Karte
              leer. Die Reihenfolge bleibt die des Arguments — erst die
              Herleitung, dann der Beleg, den sie ankündigt („Das müssen wir
              nicht selbst herleiten"); links-rechts ist genau diese Richtung.
              Die Zeile misst einspaltig 95 Zeichen (`76ch` × 1,26, s.
              DESIGNSPRACHE §4) und in der Spalte rund 78 — beides im
              Lesebereich. Schwelle am CONTAINER
              (Designsprache §4), nicht am Fenster: Bei 1024 px Fenster ist
              neben der Seitenleiste nur Platz für Spalten von 344 px. */}
          <div className="mt-2 grid items-start gap-x-8 gap-y-3.5 @5xl/kern:grid-cols-2">
            <div className="flex max-w-[76ch] flex-col gap-2.5 text-[13px] leading-relaxed text-foreground/90">
              <p>
                Die Ausgaben je Einwohner*in stehen in beiden Haushalten. Ein direkter
                Vergleich wäre trotzdem irreführend: <strong>Zunächst zeigt die Zahl,
                welche Aufgaben eine Stadt im Kernhaushalt führt</strong> — erst danach
                lässt sie Rückschlüsse auf die Leistungsausgaben zu.
              </p>
              <p>
                Oldenburg führt Gebäudewirtschaft, Abfallwirtschaft und Bäder als
                Eigenbetriebe, das Klinikum als eigene Anstalt. Diese Betriebe rechnen
                selbst ab; im Haushalt tauchen sie höchstens als Zuschusszeile auf. Von
                allem, was die Stadt insgesamt bewegt, stehen deshalb nur rund{" "}
                <strong>64 Prozent</strong> im Kernhaushalt — nachzulesen unter{" "}
                <Link href="/haushalt/konzern" className="font-semibold text-primary">
                  Der Konzern Stadt
                </Link>. In Osnabrück sind es knapp 48 Prozent, weil dort auch die
                Stadtwerke dazugehören. Wer beide Haushalte nebeneinanderlegt, vergleicht
                zuerst zwei Organisationsformen.
              </p>
              <p>
                Das müssen wir nicht selbst herleiten. <strong>Die Stadt Oldenburg hat
                exact diesen Vergleich schon einmal angestellt</strong> — und im selben
                Dokument entwertet.
              </p>
            </div>

            {/* Der Beleg aus dem eigenen Bestand. */}
            <div className="rounded-xl border border-border bg-muted/30 p-3.5">
              <p className="font-mono text-[9.5px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
                Aus dem Ratsinformationssystem · {data.beleg.template_number} · 2018
              </p>
              <p className="mt-1.5 max-w-[76ch] text-[13px] leading-relaxed text-foreground/90">
                Die FDP-Fraktion fragte im November 2018, wie sich die Personalquote
                Oldenburgs im Vergleich mit anderen Städten entwickelt habe. Die Verwaltung
                antwortete mit einer Tabelle über sieben Städte und neun Jahrgänge — und
                schrieb dazu:
                <Beleg q="vergleich_2018" />
              </p>
              {/* Wörtliches Zitat, deshalb in Anführungszeichen und als
                  blockquote — anders als Paraphrasen im Ratsgespräch, die
                  bewusst ohne Anführungszeichen kursiv stehen. */}
              <blockquote className="mt-2.5 border-l-2 border-primary/40 pl-3 text-[13.5px] font-medium leading-relaxed text-foreground">
                „{ZITAT_VERWALTUNG}“
              </blockquote>
              <p className="mt-2.5 max-w-[76ch] text-[13px] leading-relaxed text-foreground/90">
                Und dann führte sie auf, was in welcher Stadt überhaupt im Haushalt steht:
              </p>
              <ul className="mt-2 flex flex-col gap-1 text-[12.5px] leading-relaxed">
                {AUSGLIEDERUNGEN_2018.map((z) => (
                  <li key={z.stadt} className="flex gap-2">
                    <span className="w-[6.5rem] flex-none font-semibold">{z.stadt}</span>
                    <span className="text-muted-foreground">{z.was}</span>
                  </li>
                ))}
              </ul>
              <p className="mt-2.5 max-w-[76ch] text-[13px] leading-relaxed text-foreground/90">
                Osnabrück liegt in dieser Tabelle rund fünf Prozentpunkte unter Oldenburg —
                und führt drei Aufgabenblöcke weniger im Haushalt. Der „Unterschied“ war
                die Organisationsform.
              </p>

              {/* Die Verweise: erst der Vorgang bei uns, dann die Originale. */}
              <div className="mt-3 flex flex-col gap-1.5 border-t border-dashed border-border pt-2.5">
                {data.beleg.decision_id != null && (
                  <Link href={decisionHref(data.beleg.decision_id)}
                    className="group inline-flex items-center gap-1.5 text-[12.5px] font-semibold text-primary">
                    <FileText className="h-3.5 w-3.5 flex-none" />
                    Der Vorgang bei uns: {data.beleg.titel ?? data.beleg.template_number}
                    <ArrowRight size={13} strokeWidth={2}
                      className="transition-transform group-hover:translate-x-0.5" />
                  </Link>
                )}
                {antwort?.url && (
                  <a href={antwort.url} target="_blank" rel="noopener noreferrer"
                    className="inline-flex items-center gap-1.5 text-[12.5px] font-semibold text-primary">
                    <ExternalLink className="h-3.5 w-3.5 flex-none" />
                    Antwort der Verwaltung im Original (PDF)
                  </a>
                )}
                {antrag?.url && (
                  <a href={antrag.url} target="_blank" rel="noopener noreferrer"
                    className="inline-flex items-center gap-1.5 text-[12.5px] font-semibold text-primary">
                    <ExternalLink className="h-3.5 w-3.5 flex-none" />
                    Antrag der FDP-Fraktion im Original (PDF)
                  </a>
                )}
                {!data.beleg.anlagen.length && (
                  <a href={data.beleg.vorlage_url} target="_blank" rel="noopener noreferrer"
                    className="inline-flex items-center gap-1.5 text-[12.5px] font-semibold text-primary">
                    <ExternalLink className="h-3.5 w-3.5 flex-none" />
                    Vorlage {data.beleg.template_number} im Bürgerinformationssystem
                  </a>
                )}
              </div>
            </div>
          </div>

          {/* Steht UNTER beiden Spalten, nicht in einer: „Dieselbe Warnung"
              meint den Beleg daneben mit — der Satz muss also nach ihm
              gelesen werden, nicht neben ihm. Über die volle Kartenbreite
              läuft er trotzdem: Unter ihm kommt nichts mehr, der Deckel allein
              ließe den Kartenboden halb leer (Designsprache §4). */}
          <p className="mt-3.5 max-w-[76ch] text-[13px] leading-relaxed text-foreground/90 @3xl/kern:max-w-none @3xl/kern:columns-2 @3xl/kern:gap-x-8 @6xl/kern:columns-3">
            Dieselbe Warnung kommt von zwei weiteren Stellen. Das niedersächsische
            Innenministerium schreibt in seinem Runderlass vom 13.12.2017, Ausgliederungen
            und Fremdvergaben könnten „die Aussagekraft und Vergleichbarkeit der Kennzahlen
            beeinflussen und beeinträchtigen". Und das Statistische Bundesamt hält fest,
            die Vergleichbarkeit werde dadurch eingeschränkt, dass der Ausgliederungsprozess
            unterschiedlich weit fortgeschritten sei. Drei Instanzen, derselbe Befund.
          </p>
        </section>

        {/* --- Wen man überhaupt vergleichen würde --- */}
        <Abschnitt kicker="Wen man mit Oldenburg vergleichen würde">
          <p className="mt-1.5 max-w-[76ch] text-[13px] leading-relaxed text-foreground/90">
            Vergleichbar ist eine Stadt nicht, wenn ihre Zahlen ähnlich aussehen, sondern
            wenn sie dieselben Aufgaben trägt. Das tun die acht kreisfreien Städte
            Niedersachsens: Sozialhilfe, Jugendhilfe und die weiterführenden Schulen
            liegen bei ihnen selbst, und sie zahlen keine Kreisumlage. Drei davon sind
            als Maßstab besonders aufschlussreich.
          </p>
          {/* Drei Städte nebeneinander statt untereinander: Sie sind der
              Vergleich, um den es hier geht — parallele Fälle, die man
              gegeneinander liest, nicht nacheinander. Gestapelt standen sie
              als 400 px hohe Spalte in einer 1104 px breiten Karte. In drei
              Spalten sind es je rund 336 px, dieselbe Breite wie die
              Steckbrief-Karten unter „Woher das Geld kommt"; die Texte sind
              zwei bis drei Sätze und tragen das. Schwelle am CONTAINER
              (Designsprache §4). */}
          <ul className="mt-3 grid gap-x-6 gap-y-2.5 @5xl/section:grid-cols-3">
            {Object.entries(ROLLEN).map(([key, r]) => {
              const stadt = data.staedte.find((s) => s.schluessel === key);
              if (!stadt) return null;
              return (
                <li key={key} className="border-l-2 border-border pl-3">
                  <p className="text-[13px] font-bold">
                    {stadt.name}
                    <span className="ml-2 font-mono text-[9.5px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
                      {r.role}
                    </span>
                  </p>
                  <p className="mt-0.5 max-w-[72ch] text-[12.5px] leading-relaxed text-muted-foreground">
                    {r.text}
                  </p>
                </li>
              );
            })}
          </ul>
          <p className="mt-3 max-w-[76ch] text-[12.5px] leading-relaxed text-muted-foreground">
            <strong className="text-foreground/90">Hannover steht bewusst nicht dabei</strong>,
            obwohl der Gesamtabschluss der Stadt es seit Jahren danebenstellt. Die
            Landeshauptstadt trägt Sozialhilfe, Krankenhäuser, Abfallwirtschaft und die
            Berufsschulen nicht selbst — das macht die Region Hannover, wofür 2026 rund
            539 Millionen Euro Umlage abfließen. Damit würden zwei unterschiedliche
            Aufgabenpakete miteinander verglichen.
          </p>
        </Abschnitt>

        {/* --- Die Grenzen, als eigener Block statt als Kleingedrucktes --- */}
        <section className="@container rounded-2xl border border-border bg-card p-4 shadow-sm">
          <p className="font-mono text-[10px] font-medium uppercase tracking-[0.11em] text-muted-foreground">
            Was auf dieser Seite bewusst fehlt
          </p>
          {/* Zwei Spalten, sobald die Karte Platz hat (Designsprache §4): Der
              Deckel allein ließe hier rechts über 300 px leer, ohne dass die
              Zeile dadurch besser läge. In der Spalte sind es rund 70 Zeichen
              statt 95 — Fläche gefüllt UND kürzere Zeile. */}
          <ul className="mt-2 grid max-w-[76ch] list-disc grid-cols-1 gap-x-8 gap-y-1.5 pl-4 text-[13px] leading-relaxed text-foreground/90 @3xl:max-w-none @3xl:grid-cols-2">
            <li>
              <strong>Ausgaben, Personal und Schulden je Einwohner*in.</strong> Die Gründe
              stehen oben. Sie gelten auch dann, wenn die Zahlen sauber erhoben sind —
              präzise Zahlen ergeben hier trotzdem keinen gültigen Vergleich.
            </li>
            <li>
              <strong>Ein Vergleich ganzer Konzerne.</strong> Er läge nahe, weil er das
              Auslagerungsproblem aufhöbe. Nur veröffentlicht die amtliche Statistik
              Kern- und Extrahaushalte zusammen erst auf Landesebene, nie je Stadt — und
              fünf der sieben Vergleichsstädte haben seit Jahren gar keinen
              Gesamtabschluss vorgelegt, Braunschweig zuletzt für 2016.
            </li>
            <li>
              <strong>Städte außerhalb Niedersachsens.</strong> Finanzausgleich,
              Kreisumlage und die Zuständigkeit für Sozial- und Jugendhilfe sind
              Landesrecht. Jede Kennzahl bräuchte eine eigene Abgrenzungsprüfung.
            </li>
            <li>
              <strong>Eine gemeinsame Zeitreihe mit den Steuerkraft-Zahlen auf{" "}
              <Link href="/haushalt/steuer" className="font-semibold text-primary">
                Woher das Geld kommt
              </Link>.</strong> Beide Reihen nennen dieselben Beträge und tragen
              inzwischen auch dieselbe Jahresangabe: Der offene Datensatz der Stadt
              beschriftete sie ein Jahr zu früh — nachgewiesen an den eigenen Büchern
              der Stadt, in denen das Geld ein Jahr später als Ist verbucht ist —, und
              wir haben das korrigiert. Wir rechnen sie trotzdem nicht zusammen: Sie
              stammen aus zwei Veröffentlichungen, die sich in Nachträgen und
              Revisionen um kleine Beträge unterscheiden können.
            </li>
          </ul>
        </section>

        <Link href="/haushalt"
          className="group flex items-center gap-2 text-[13px] font-semibold text-primary">
          Zurück zur Übersicht über den Haushalt
          <ArrowRight size={14} strokeWidth={2}
            className="transition-transform group-hover:translate-x-0.5" />
        </Link>

        <SchrittWeiter href="/haushalt/vergleich" />

        <Quellenverzeichnis schluessel={[...QUELLEN]} />
      </div>
    </Quellenkontext>
  );
}
