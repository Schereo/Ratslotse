// /kommunalwahl/liste/[liste] — ein Programm im Profil (Design 3b).
// Identischer Aufbau für alle 9 Listen (Bauplan E4): gleiche Bauteile, gleiche
// Reihenfolge, gleicher Platz. Keine Liste bekommt etwas, das eine andere nicht bekommt.

import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Fingerabdruck } from "@/components/kommunalwahl/fingerabdruck";
import { QuellenCheck } from "@/components/kommunalwahl/quellen-check";
import { ThesenListe } from "@/components/kommunalwahl/these-liste";
import {
  Abschnitt,
  BswPill,
  FarbPunkt,
  KwCrumb,
  KwFuss,
  KwKopf,
  PraegnanzDots,
} from "@/components/kommunalwahl/ui";
import { fingerabdruck, listeProfil, sprachProfil, stand, vergleichsSlugs } from "@/lib/kommunalwahl";

export function generateStaticParams() {
  return vergleichsSlugs().map((liste) => ({ liste }));
}

export const dynamicParams = false;

export function generateMetadata({ params }: { params: { liste: string } }): Metadata {
  const p = listeProfil(params.liste);
  if (!p) return {};
  return {
    title: `${p.kurz} im Programm-Check`,
    description: `Was ${p.kurz} zur Ratswahl Oldenburg 2026 fordert: Kernpunkte, Positionen zu ${p.positionen} von 44 Thesen — jede Aussage mit Beleg im Original.`,
  };
}

export default function ListeSeite({ params }: { params: { liste: string } }) {
  const p = listeProfil(params.liste);
  if (!p) notFound();
  const abdruck = fingerabdruck(params.liste);
  const sprache = sprachProfil(params.liste);

  return (
    <>
      <KwKopf crumb={<KwCrumb teil={`Listen / ${p.kurz}`} />} />
      <main className="mx-auto w-full max-w-[1080px] px-4 pb-16 pt-9 sm:px-6 sm:pt-11 lg:px-10">
        {/* Kopf */}
        <div className="flex items-start gap-4 sm:gap-[18px]">
          <span
            aria-hidden
            className="kw-farbe h-10 w-10 flex-none rounded-xl sm:h-[52px] sm:w-[52px] sm:rounded-2xl"
            style={{ "--kw-f": p.farbe, "--kw-fd": p.farbeDunkel } as React.CSSProperties}
          />
          <div className="min-w-0">
            <h1 className="font-display text-[26px] font-bold leading-[1.05] tracking-tight sm:text-[40px]">
              {p.kurz}
            </h1>
            <p className="mt-1.5 text-xs text-muted-foreground sm:text-[13.5px]">
              {p.amtlich} · {p.typLabel} · {p.kandidaten} Kandidierende ·{" "}
              {p.wahlbereiche === 6 ? "alle 6 Wahlbereiche" : `${p.wahlbereiche} von 6 Wahlbereichen`}
            </p>
            {p.landesprogramm && (
              <p className="mt-2">
                <BswPill />
              </p>
            )}
          </div>
          <div className="ml-auto hidden flex-none flex-col items-end gap-1.5 lg:flex">
            <span className="text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground">
              Wo dieses Programm sein Gewicht legt
            </span>
            <Fingerabdruck felder={abdruck} />
          </div>
        </div>
        <div className="mt-4 flex flex-col gap-1.5 lg:hidden">
          <span className="text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground">
            Wo dieses Programm sein Gewicht legt
          </span>
          <Fingerabdruck felder={abdruck} />
        </div>

        {/* Quelle prominent */}
        <section className="mt-6 flex flex-col gap-5 rounded-[18px] border border-border bg-card p-5 sm:flex-row sm:items-center sm:p-6">
          <div className="min-w-0">
            <p className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground">Die Quelle</p>
            <p className="mt-1.5 max-w-[54ch] font-display text-[16px] font-bold leading-snug sm:text-[19px]">
              {p.quelle.titel ?? "—"}
            </p>
            <p className="mt-1 text-[12.5px] text-muted-foreground sm:text-[13px]">
              {p.quelle.format === "pdf" ? `PDF · ${p.quelle.seiten} Seiten` : "Website"}
              {p.quelle.domain && <> · {p.quelle.domain}</>}
              {p.quelle.seitenlink ? (
                <>
                  {" "}
                  · jede Seitenzahl auf dieser Seite springt per{" "}
                  <code className="text-[11.5px]">#page=N</code> hinein
                </>
              ) : (
                <> · ohne Seitenzahlen — Belege führen auf die Website</>
              )}
            </p>
            {p.quelle.standQuelle && (
              <p className="mt-1 text-xs text-muted-foreground">Beschlussstand: {p.quelle.standQuelle}</p>
            )}
            {p.quelle.hinweis && (
              <p className="mt-2 max-w-[80ch] text-xs leading-relaxed text-muted-foreground">
                <strong className="font-semibold text-foreground">Hinweis:</strong> {p.quelle.hinweis}
              </p>
            )}
          </div>
          <div className="flex flex-none flex-col items-start gap-2 sm:ml-auto sm:items-end sm:text-right">
            {p.quelle.url && (
              <a
                href={p.quelle.url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex rounded-xl bg-primary px-4 py-2 text-[13.5px] font-semibold text-primary-foreground"
              >
                Programm öffnen ↗
              </a>
            )}
            {p.quelle.pruefbar ? (
              <QuellenCheck slug={p.slug} stand={stand()} />
            ) : (
              <span className="max-w-[44ch] text-xs text-muted-foreground">
                Website statt PDF — Inhalte können sich ändern. Ausgewertet am {stand()}.
              </span>
            )}
          </div>
        </section>

        {/* Charakter + Kernpunkte */}
        <section className="mt-8 grid gap-8 md:grid-cols-[1.1fr_1fr]">
          <div>
            <Abschnitt titel="Wofür dieses Programm steht" />
            <p className="mt-3 text-sm leading-[1.7] text-muted-foreground [text-wrap:pretty]">{p.charakter}</p>
          </div>
          <div>
            <Abschnitt titel={`Die ${p.kernpunkte.length === 7 ? "sieben" : String(p.kernpunkte.length)} Kernpunkte`} />
            <div className="mt-3 flex flex-col gap-2">
              {p.kernpunkte.map((k, i) => (
                <div key={i} className="flex items-start gap-2.5">
                  <span className="inline-flex h-5 w-5 flex-none items-center justify-center rounded-md bg-primary/10 text-[11px] font-bold tabular-nums text-primary">
                    {i + 1}
                  </span>
                  <p className="text-[13px] leading-relaxed text-muted-foreground sm:text-[13.5px]">{k}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Fällt auf */}
        {p.besonderes.length > 0 && (
          <section className="mt-8">
            <Abschnitt titel="Fällt auf" neben="steht so in keinem anderen Programm" />
            <div className="mt-3 grid gap-2.5 sm:grid-cols-2">
              {p.besonderes.map((b, i) => (
                <div
                  key={i}
                  className="flex items-start gap-2.5 rounded-[13px] border border-dashed border-primary/40 bg-primary/[0.04] px-4 py-3"
                >
                  <span aria-hidden className="mt-0.5 flex-none text-[13px] text-primary">
                    ✦
                  </span>
                  <p className="text-[13px] leading-relaxed text-muted-foreground">{b}</p>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* Wie dieses Programm redet (Ausbau 08.08.) — Fakten über die Sprache */}
        {sprache && (
          <section className="mt-8">
            <Abschnitt
              titel="Wie dieses Programm redet"
              neben="Zahlen aus dem Volltext — keine Wertung"
            />
            <div className="mt-3 rounded-2xl border border-border bg-card p-5">
              <div className="flex flex-wrap gap-2">
                {[
                  [`${sprache.woerter.toLocaleString("de-DE")}`, "Wörter"],
                  [`Ø ${String(sprache.satzlaenge).replace(".", ",")}`, "Wörter pro Satz"],
                  [sprache.lixLabel, `Lesbarkeit (LIX ${sprache.lix})`],
                ].map(([wert, label]) => (
                  <span
                    key={label}
                    className="inline-flex items-baseline gap-1.5 rounded-full border border-border bg-background/60 px-3 py-1.5"
                  >
                    <span className="text-[13px] font-bold tabular-nums">{wert}</span>
                    <span className="text-[11px] text-muted-foreground">{label}</span>
                  </span>
                ))}
              </div>
              <p className="mt-4 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                Typische Begriffe — stehen hier deutlich häufiger als in den anderen Programmen
              </p>
              <div className="mt-2 flex flex-wrap items-baseline gap-x-2.5 gap-y-2">
                {sprache.begriffe.map((b) => (
                  <span
                    key={b.wort}
                    title={`${b.haeufigkeit}× im Programm`}
                    className="rounded-lg bg-primary/[0.07] px-2.5 py-1 font-medium text-foreground"
                    style={{ fontSize: `${12 + b.gewicht * 7}px` }}
                  >
                    {b.wort}
                  </span>
                ))}
              </div>
            </div>
          </section>
        )}

        {/* Positionen nach Themenfeld */}
        <section className="mt-8">
          <Abschnitt
            titel="Positionen nach Themenfeld"
            neben="Prägnanz ●●● = Schwerpunkt · „keine Aussage&#34; wird ausgewiesen, nicht weggelassen"
          />
          <div className="mt-3 flex flex-col gap-2">
            {p.themen.map((t, i) => (
              <details
                key={t.key}
                className="kw-details rounded-2xl border border-border bg-card px-4 py-3 sm:px-5"
                open={i === 0 && t.bullets.length > 0}
              >
                <summary className="outline-none focus-visible:ring-2 focus-visible:ring-ring">
                  <span className="flex items-center gap-2.5">
                    <span className="text-[13.5px] font-bold sm:text-[14.5px]">{t.label}</span>
                    <PraegnanzDots n={t.praegnanz} />
                    <span className="ml-auto text-xs tabular-nums text-muted-foreground">
                      {t.bullets.length === 0 ? "keine Aussage" : `${t.bullets.length} Forderungen`}
                    </span>
                    {t.bullets.length > 0 && (
                      <span aria-hidden className="kw-chevron text-[13px] text-muted-foreground">
                        ⌄
                      </span>
                    )}
                  </span>
                </summary>
                {t.bullets.length > 0 && (
                  <div className="mt-2.5 grid gap-x-8 gap-y-[7px] sm:grid-cols-2">
                    {t.bullets.map((b, j) => (
                      <div key={j} className="flex items-start gap-2">
                        <FarbPunkt farbe={p.farbe} farbeDunkel={p.farbeDunkel} size={5} className="mt-[7px]" />
                        <p className="text-[13px] leading-relaxed text-muted-foreground">{b}</p>
                      </div>
                    ))}
                    {t.seitenHref.length > 0 && (
                      <p className="text-xs text-muted-foreground sm:col-span-2">
                        Im Original:{" "}
                        {t.seitenHref.map((s, j) => (
                          <span key={s.seite}>
                            {j > 0 && " · "}
                            {s.href ? (
                              <a href={s.href} target="_blank" rel="noopener noreferrer" className="text-primary">
                                S. {s.seite} ↗
                              </a>
                            ) : (
                              `S. ${s.seite}`
                            )}
                          </span>
                        ))}
                      </p>
                    )}
                  </div>
                )}
              </details>
            ))}
          </div>
        </section>

        {/* Nah / Fern */}
        <section className="mt-8 grid gap-4 md:grid-cols-2">
          {(
            [
              ["Steht am nächsten bei", p.naechste, true],
              ["Am weitesten weg von", p.fernste, false],
            ] as const
          ).map(([titel, liste, nah]) => (
            <div key={titel} className="rounded-2xl border border-border bg-card p-4 sm:px-5">
              <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-muted-foreground">{titel}</p>
              {liste.map((q) => (
                <Link key={q.slug} href={`/kommunalwahl/liste/${q.slug}`} className="flex items-center gap-2 py-[5px]">
                  <FarbPunkt farbe={q.farbe} farbeDunkel={q.farbeDunkel} size={9} />
                  <span className="w-16 text-[13px] font-semibold">{q.kurz}</span>
                  <span className="inline-flex h-1.5 flex-1 overflow-hidden rounded-[3px] bg-foreground/[0.07]">
                    <span
                      className={`rounded-[3px] ${nah ? "bg-primary" : "bg-muted-foreground/50"}`}
                      style={{ width: `${q.wert}%` }}
                    />
                  </span>
                  <span className="text-[13px] font-bold tabular-nums">{q.wert}&thinsp;%</span>
                  <span className="text-[10.5px] tabular-nums text-muted-foreground">n={q.n}</span>
                </Link>
              ))}
            </div>
          ))}
        </section>

        {/* Alle 44 Thesen */}
        <section className="mt-8">
          <Abschnitt
            titel="Alle 44 Thesen"
            neben={`antippen → Belegzitat; ${p.positionen} mit Position, ${44 - p.positionen} ohne Aussage`}
          />
          <div className="mt-3">
            <ThesenListe thesen={p.thesen} />
          </div>
        </section>

        <KwFuss
          stand={stand()}
          links={[
            { href: "/kommunalwahl#programme", label: "Alle 9 Listen" },
            { href: "/kommunalwahl/methodik", label: "Methodik" },
          ]}
        />
      </main>
    </>
  );
}
