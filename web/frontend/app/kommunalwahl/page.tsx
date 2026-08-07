// /kommunalwahl — der Überblick (Design 2a: „warm wie 1b, navigierbar wie 1c").
// Server Component; Daten kommen zur Bauzeit aus kommunalwahl/data.json.

import Link from "next/link";
import { Mascot } from "@/components/mascot";
import { CountdownBadge, CountdownKarte } from "@/components/kommunalwahl/countdown";
import { Fingerabdruck } from "@/components/kommunalwahl/fingerabdruck";
import { Landkarte } from "@/components/kommunalwahl/landkarte";
import { PositionsMatrix } from "@/components/kommunalwahl/matrix";
import {
  Abschnitt,
  BswPill,
  ENTDECKEN_HREF,
  FarbPunkt,
  KiKasten,
  KiPlakette,
  KwCrumb,
  KwFuss,
  KwKopf,
  REGISTER_HREF,
} from "@/components/kommunalwahl/ui";
import {
  alleinstellungen,
  datenlageBalken,
  fingerabdruck,
  kennzahlen,
  landkarte,
  listenKacheln,
  nahFern,
  ohneProgramm,
  stand,
  streitEinigkeit,
  themenKacheln,
} from "@/lib/kommunalwahl";
import { Glyph } from "@/components/kommunalwahl/ui";

const RAIL = [
  ["#stimmen", "Drei Stimmen"],
  ["#datenlage", "Datenlage"],
  ["#streit", "Streit & Einigkeit"],
  ["#allein", "Steht allein da"],
  ["#themen", "Themenfelder"],
  ["#programme", "Die 9 Programme"],
  ["#karte", "Die Karte der Nähe"],
  ["#naehe", "Wer steht wem nahe?"],
  ["#ohne", "Ohne Programm"],
  ["#methodik", "Methodik & KI"],
] as const;

/** Farbe eines Datenlage-Segments — Semantik aus dem Handoff (2a Punkt 5). */
function segmentKlasse(art: string): string {
  if (art === "voll") return "bg-primary";
  if (art === "landes") return "bg-amber-500";
  if (art === "kurz") return "bg-foreground/25";
  return "bg-foreground/10";
}

export default function KommunalwahlSeite() {
  const zahlen = kennzahlen();
  const balken = datenlageBalken();
  const { streit, einig } = streitEinigkeit();
  const themen = themenKacheln();
  const listen = listenKacheln();
  const paare = nahFern();
  const ohne = ohneProgramm();
  const allein = alleinstellungen(6);
  const karte = landkarte();

  return (
    <>
      <KwKopf crumb={<KwCrumb />} />

      {/* Hero */}
      <section className="flex flex-col items-center px-4 pt-7 text-center sm:px-6">
        <Mascot pose="wave" bob className="h-20 w-20 sm:h-[108px] sm:w-[108px]" />
        <div className="mt-2.5">
          <CountdownBadge />
        </div>
        <h1 className="mt-3.5 max-w-[720px] font-display text-[27px] font-bold leading-[1.08] tracking-tight [text-wrap:balance] sm:text-[46px]">
          Wahlprogramme, verständlich verglichen.
        </h1>
        <p className="mt-3.5 max-w-[620px] text-[14px] leading-relaxed text-muted-foreground sm:text-[16.5px]">
          Ratslotse hat alle Programme zur Ratswahl gelesen — und zeigt belegt, wo die Listen
          beieinanderstehen und wo nicht. Ohne Empfehlung. Jede Aussage führt ins Original.
        </p>
        <a
          href="#methodik"
          className="mt-3 inline-flex items-center gap-2 rounded-full border border-border bg-card px-3.5 py-1.5 text-[11px] text-muted-foreground sm:text-[12.5px]"
        >
          <KiPlakette />
          <span>
            Von KI ausgewertet, nicht redaktionell kuratiert —{" "}
            <strong className="font-semibold text-foreground">jede Aussage mit Beleg</strong> · Mehr dazu ↓
          </span>
        </a>
        <div className="mt-5 flex flex-wrap justify-center gap-2 sm:gap-2.5">
          {zahlen.map((k) => (
            <span
              key={k.label}
              className="inline-flex items-baseline gap-1.5 rounded-full border border-border bg-card px-3 py-1.5 sm:px-4 sm:py-2"
            >
              <span className="font-display text-[13px] font-bold tabular-nums sm:text-base">{k.wert}</span>
              <span className="text-[11px] text-muted-foreground sm:text-[12.5px]">{k.label}</span>
            </span>
          ))}
        </div>
      </section>

      {/* Zweispaltiges Gerüst: Rail + Inhalt */}
      <div className="mx-auto grid w-full max-w-[1280px] gap-11 px-4 pb-16 pt-9 sm:px-6 lg:grid-cols-[230px_1fr] lg:px-10">
        <aside className="hidden lg:block">
          <div className="sticky top-20 flex flex-col gap-0.5">
            <CountdownKarte />
            {RAIL.map(([href, label]) => (
              <a
                key={href}
                href={href}
                className="rounded-lg px-3 py-2 text-[13.5px] font-medium text-muted-foreground transition-colors hover:bg-primary/10 hover:text-primary"
              >
                {label}
              </a>
            ))}
            <div className="mt-3.5 rounded-[14px] border border-border bg-card p-4">
              <p className="text-[12.5px] leading-relaxed text-muted-foreground">
                <strong className="text-foreground">Neu hier?</strong> Ratslotse kann mehr als Wahlkampf:
                alle Beschlüsse des Rats, durchsuchbar und erklärt.
              </p>
              <a
                href={REGISTER_HREF}
                className="mt-2.5 inline-flex rounded-lg bg-primary px-3 py-1.5 text-xs font-semibold text-primary-foreground"
              >
                Kostenlos registrieren
              </a>
            </div>
          </div>
        </aside>

        <main className="min-w-0">
          {/* Drei Stimmen */}
          <section id="stimmen" className="scroll-mt-24">
            <div className="flex flex-col items-start gap-5 rounded-[20px] bg-primary p-6 text-primary-foreground sm:flex-row sm:items-center sm:p-7">
              <div>
                <p className="font-display text-[17px] font-bold sm:text-[21px]">Du hast drei Stimmen — nutz sie.</p>
                <p className="mt-2 max-w-[56ch] text-[13px] leading-relaxed text-primary-foreground/85 sm:text-sm">
                  Alle drei auf eine Person häufen (kumulieren) oder über Listen verteilen (panaschieren) —
                  beides geht. Mehr als drei Kreuze machen den Zettel ungültig. Wählen ab 16, auch
                  EU-Bürger:innen.
                </p>
              </div>
              <div className="flex flex-none items-center gap-4 sm:ml-auto">
                <div className="flex gap-1.5" aria-hidden>
                  {[1, 2].map((i) => (
                    <span
                      key={i}
                      className="inline-flex h-7 w-7 items-center justify-center rounded-md border-[1.5px] border-current text-sm font-bold"
                    >
                      ✕
                    </span>
                  ))}
                  <span className="inline-flex h-7 w-7 items-center justify-center rounded-md border-[1.5px] border-current/40 text-sm font-bold opacity-50">
                    ✕
                  </span>
                </div>
                <Mascot pose="celebrate" bob decorative className="hidden h-24 w-24 sm:block" />
              </div>
            </div>
          </section>

          {/* Datenlage */}
          <section id="datenlage" className="mt-5 scroll-mt-24">
            <details className="kw-details rounded-2xl border border-border bg-card px-5 py-4 sm:px-6">
              <summary className="outline-none focus-visible:ring-2 focus-visible:ring-ring">
                <span className="flex items-baseline gap-3">
                  <span className="font-display text-[17px] font-bold sm:text-xl">Datenlage: 8 von 16 mit Programm</span>
                  <span className="ml-auto text-[12.5px] font-semibold text-primary">Wer fehlt und warum ↓</span>
                </span>
                <span className="mt-3 flex gap-[3px]">
                  {balken.map((b) => (
                    <span key={b.slug} className={`h-2 flex-1 rounded-[3px] ${segmentKlasse(b.art)}`} />
                  ))}
                </span>
                <span className="mt-3 block max-w-[86ch] text-[13px] leading-relaxed text-muted-foreground sm:text-[13.5px]">
                  Verglichen werden die 8 Listen mit eigenem Kommunalwahlprogramm plus BSW — dessen
                  Landesprogramm nennt Oldenburg an keiner Stelle und trägt deshalb überall eine Markierung.
                  Die übrigen sieben stehen unten mit dem, was es gibt.
                </span>
              </summary>
              <div className="mt-4 grid gap-2.5 border-t border-border pt-4 sm:grid-cols-2">
                {ohne.map((l) => (
                  <details key={l.slug} className="kw-details rounded-xl border border-border bg-background/50 px-4 py-3">
                    <summary>
                      <span className="flex items-center gap-2">
                        <FarbPunkt farbe={l.farbe} farbeDunkel={l.farbeDunkel} size={9} />
                        <span className="text-[13.5px] font-bold">{l.kurz}</span>
                        <span className="text-[11px] text-muted-foreground">{l.kandidaten} Kandidierende</span>
                        <span className="ml-auto text-[11px] font-semibold text-primary">{l.artLabel}</span>
                      </span>
                      <span className="mt-1.5 block text-xs leading-relaxed text-muted-foreground">{l.begruendung}</span>
                      {l.protokoll && (
                        <span className="mt-1 block text-[11.5px] font-semibold text-primary">Was wir geprüft haben ⌄</span>
                      )}
                    </summary>
                    {l.protokoll && (
                      <p className="mt-2 border-t border-border/60 pt-2 text-[11.5px] leading-relaxed text-muted-foreground">
                        {l.protokoll}
                      </p>
                    )}
                  </details>
                ))}
              </div>
            </details>
          </section>

          {/* Streit & Einigkeit */}
          <section id="streit" className="mt-8 scroll-mt-24">
            <Abschnitt titel="Streit & Einigkeit — auf einen Blick" neben="Zelle antippen → Belegzitat mit Fundstelle" />
            <div className="mt-3.5">
              <PositionsMatrix zeilen={[...streit, ...einig]} mitLage />
            </div>
            <div className="mt-[18px] pt-4">
              <KiKasten />
            </div>
          </section>

          {/* Steht allein da — Positionen gegen alle anderen (Ausbau 08.08.) */}
          <section id="allein" className="mt-8 scroll-mt-24">
            <Abschnitt
              titel="Steht allein da"
              neben="Positionen, mit denen eine Liste gegen alle anderen steht — belegt"
            />
            <div className="mt-3.5 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {allein.map((a) => (
                <div key={`${a.id}-${a.marke.slug}`} className="flex flex-col rounded-[15px] border border-border bg-card px-4 py-3.5">
                  <span className="flex flex-wrap items-center gap-2">
                    <FarbPunkt farbe={a.marke.farbe} farbeDunkel={a.marke.farbeDunkel} size={10} />
                    <span className="text-[13.5px] font-bold">{a.marke.kurz}</span>
                    {a.marke.landesprogramm && <BswPill kompakt />}
                    <span
                      className={`ml-auto rounded-full px-2 py-0.5 text-[10.5px] font-semibold ${
                        a.art === "einzige_aussage"
                          ? "bg-secondary text-secondary-foreground"
                          : a.pos === 1
                            ? "bg-emerald-700/10 text-emerald-900 dark:bg-emerald-400/15 dark:text-emerald-300"
                            : "bg-red-700/10 text-red-900 dark:bg-red-400/15 dark:text-red-300"
                      }`}
                    >
                      {a.art === "einzige_aussage"
                        ? "als einzige mit Position"
                        : a.pos === 1
                          ? "als einzige dafür"
                          : "als einzige dagegen"}
                    </span>
                  </span>
                  <p className="mt-2 flex-1 text-[13px] font-semibold leading-snug [text-wrap:pretty]">
                    {a.these}
                  </p>
                  {a.dagegen.length > 0 && (
                    <p className="mt-2 flex flex-wrap items-center gap-1.5 text-[11px] text-muted-foreground">
                      <Glyph pos={a.pos === 1 ? -1 : 1} size={13} />
                      {a.dagegen.map((g) => g.kurz).join(", ")}
                      {a.teils.length > 0 && ` · teils: ${a.teils.map((g) => g.kurz).join(", ")}`}
                    </p>
                  )}
                  {a.beleg && (
                    <p className="mt-2 border-t border-border/60 pt-2 text-[11.5px] leading-relaxed text-muted-foreground">
                      »{a.beleg}«{" "}
                      {a.href && (
                        <a
                          href={a.href}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="whitespace-nowrap text-primary"
                        >
                          {a.seitenLabel} ↗
                        </a>
                      )}
                    </p>
                  )}
                </div>
              ))}
            </div>
          </section>

          {/* Themenfelder */}
          <section id="themen" className="mt-8 scroll-mt-24">
            <Abschnitt titel="Zwölf Themenfelder" neben="ein Thema wählen → alle Positionen nebeneinander, mit Beleg" />
            <div className="mt-3.5 grid grid-cols-2 gap-3 md:grid-cols-3">
              {themen.map((t) => (
                <Link
                  key={t.key}
                  href={`/kommunalwahl/thema/${t.key}`}
                  className="rounded-[15px] border border-border bg-card px-4 py-3.5 transition-colors hover:border-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  <p className="text-[13px] font-bold sm:text-[14.5px]">{t.label}</p>
                  <p className="mt-0.5 text-[11px] tabular-nums text-muted-foreground sm:text-[11.5px]">
                    {t.forderungen} Forderungen · {t.thesen} Thesen
                  </p>
                  <div className="mt-2 h-[5px] overflow-hidden rounded-[3px] bg-foreground/[0.07]">
                    <span className="block h-full rounded-[3px] bg-primary" style={{ width: `${t.anteil}%` }} />
                  </div>
                </Link>
              ))}
            </div>
          </section>

          {/* Die 9 Programme */}
          <section id="programme" className="mt-8 scroll-mt-24">
            <Abschnitt titel="Neun Programme im Profil" neben="gleiche Bauteile, gleiche Reihenfolge, gleicher Platz — für alle" />
            <div className="mt-3.5 grid gap-3 sm:grid-cols-2 md:grid-cols-3">
              {listen.map((l) => (
                <Link
                  key={l.slug}
                  href={`/kommunalwahl/liste/${l.slug}`}
                  className="flex flex-col rounded-[15px] border border-border bg-card px-4 py-4 transition-colors hover:border-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  <span className="flex items-center gap-2">
                    <FarbPunkt farbe={l.farbe} farbeDunkel={l.farbeDunkel} size={11} />
                    <span className="text-[15px] font-bold">{l.kurz}</span>
                    <span className="ml-auto text-[11px] text-muted-foreground">{l.typLabel}</span>
                  </span>
                  {l.einzeiler && (
                    <span className="mt-2 flex-1 text-xs leading-relaxed text-muted-foreground">{l.einzeiler}</span>
                  )}
                  {l.landesprogramm && (
                    <span className="mt-2 self-start">
                      <BswPill />
                    </span>
                  )}
                  {/* Themen-Fingerabdruck: wo dieses Programm sein Gewicht legt */}
                  <span className="mt-2.5">
                    <Fingerabdruck felder={fingerabdruck(l.slug)} mini />
                  </span>
                  <span className="mt-2.5 flex gap-2.5 border-t border-border/70 pt-2 text-[11px] tabular-nums text-muted-foreground">
                    <span>{l.kandidaten} Kand.</span>
                    <span>{l.quelleKurz}</span>
                    <span>{l.positionen}/44</span>
                    <span className="ml-auto font-semibold text-primary">Profil →</span>
                  </span>
                </Link>
              ))}
            </div>
          </section>

          {/* Die Karte der Nähe (Ausbau 08.08.) */}
          <section id="karte" className="mt-8 scroll-mt-24">
            <Abschnitt
              titel="Die Karte der Nähe"
              neben="alle 36 Paarabstände auf einmal — gerechnet aus den Positionen"
            />
            <div className="mt-3.5">
              <Landkarte punkte={karte.punkte} kanten={karte.kanten} />
            </div>
          </section>

          {/* Nähe + Ohne Programm */}
          <section id="naehe" className="mt-8 grid scroll-mt-24 gap-4 md:grid-cols-2">
            <div className="rounded-[18px] border border-border bg-card p-5 sm:p-6">
              <h2 className="font-display text-[17px] font-bold tracking-tight sm:text-[19px]">Wer steht wem nahe?</h2>
              <p className="mt-1 text-[12.5px] leading-relaxed text-muted-foreground">
                Übereinstimmung dort, wo sich beide äußern — nicht: gleiche Programme.
              </p>
              <div className="mt-2.5 flex flex-col">
                {paare.map((p) => (
                  <div key={`${p.a.slug}|${p.b.slug}`} className="flex items-center gap-2 py-[5px]">
                    <FarbPunkt farbe={p.a.farbe} farbeDunkel={p.a.farbeDunkel} size={8} />
                    <span className="w-12 text-[12px] font-semibold sm:w-14 sm:text-[12.5px]">{p.a.kurz}</span>
                    <FarbPunkt farbe={p.b.farbe} farbeDunkel={p.b.farbeDunkel} size={8} />
                    <span className="w-12 text-[12px] font-semibold sm:w-14 sm:text-[12.5px]">{p.b.kurz}</span>
                    <span className="inline-flex h-1.5 flex-1 overflow-hidden rounded-[3px] bg-foreground/[0.07]">
                      <span
                        className={`rounded-[3px] ${p.art === "nah" ? "bg-primary" : "bg-muted-foreground/50"}`}
                        style={{ width: `${p.wert}%` }}
                      />
                    </span>
                    <span className="w-10 text-right text-[12.5px] font-bold tabular-nums">{p.wert}&thinsp;%</span>
                    <span className="text-[10.5px] tabular-nums text-muted-foreground">n={p.n}</span>
                  </div>
                ))}
              </div>
              <Link href="/kommunalwahl/naehe" className="mt-2.5 inline-block text-xs font-semibold text-primary">
                Alle 36 Paare → /kommunalwahl/naehe
              </Link>
            </div>
            <div id="ohne" className="scroll-mt-24 rounded-[18px] border border-border bg-card p-5 sm:p-6">
              <h2 className="font-display text-[17px] font-bold tracking-tight sm:text-[19px]">
                Und die sieben ohne Programm?
              </h2>
              <p className="mt-1 text-[12.5px] leading-relaxed text-muted-foreground">
                Piraten, PGM und Die PARTEI haben keines veröffentlicht; vier weitere nur Stichpunkte oder
                ein Porträt. Was es gibt, steht in der Datenlage — samt Rechercheprotokoll.
              </p>
              <div className="mt-2.5 flex flex-col gap-1.5">
                {ohne.map((l) => (
                  <div key={l.slug} className="flex items-center gap-2 text-[12.5px]">
                    <FarbPunkt farbe={l.farbe} farbeDunkel={l.farbeDunkel} size={9} />
                    <span className="w-24 font-semibold sm:w-28">{l.kurz}</span>
                    <span className="truncate text-muted-foreground">{l.artLabel}</span>
                    <a href="#datenlage" className="ml-auto flex-none text-[11.5px] font-semibold text-primary">
                      Protokoll
                    </a>
                  </div>
                ))}
              </div>
            </div>
          </section>

          {/* Register-Block */}
          <section className="mt-8">
            <div className="flex flex-col items-center gap-5 rounded-[20px] border border-border bg-card p-6 text-center sm:flex-row sm:p-7 sm:text-left">
              <Mascot pose="celebrate" bob decorative className="h-[72px] w-[72px] flex-none sm:h-[92px] sm:w-[92px]" />
              <div>
                <h2 className="font-display text-[17px] font-bold tracking-tight sm:text-[21px]">
                  Das war der Wahl-Check. Ratslotse kann mehr.
                </h2>
                <p className="mt-1.5 max-w-[62ch] text-[13px] leading-relaxed text-muted-foreground sm:text-sm">
                  Was der neue Rat dann wirklich beschließt: durchsuchbar, verständlich erklärt, mit
                  Benachrichtigungen zu deinen Themen — kostenlos.
                </p>
              </div>
              <div className="flex flex-none flex-col gap-2.5 sm:ml-auto sm:flex-row">
                <a
                  href={REGISTER_HREF}
                  className="inline-flex justify-center rounded-xl bg-primary px-[18px] py-2.5 text-sm font-semibold text-primary-foreground"
                >
                  Kostenlos registrieren
                </a>
                <a
                  href={ENTDECKEN_HREF}
                  className="inline-flex justify-center rounded-xl border border-border bg-card px-[18px] py-2.5 text-sm font-semibold"
                >
                  Ratslotse entdecken
                </a>
              </div>
            </div>
          </section>

          <div id="methodik" className="scroll-mt-24">
            <KwFuss
              stand={stand()}
              links={[
                { href: "/kommunalwahl/methodik", label: "Methodik & Quellen" },
                { href: "/kommunalwahl/methodik#thesen", label: "Thesenkatalog (44)" },
              ]}
            />
          </div>
        </main>
      </div>
    </>
  );
}
