// /kommunalwahl/thema/[thema] — ein Themenfeld quer über alle Listen (Design 3a).
//
// Anders als im (app)-Bereich sind das echte Pfadsegmente: die Menge ist zur
// Bauzeit bekannt (12 Themenfelder), generateStaticParams zählt sie auf, der
// statische Export läuft durch (Bauplan §5.3).

import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { PositionsMatrix } from "@/components/kommunalwahl/matrix";
import {
  Abschnitt,
  BswPill,
  FarbPunkt,
  KwCrumb,
  KwFuss,
  KwKopf,
  PraegnanzDots,
} from "@/components/kommunalwahl/ui";
import { stand, themaKeys, themaSeite } from "@/lib/kommunalwahl";

export function generateStaticParams() {
  return themaKeys().map((thema) => ({ thema }));
}

export const dynamicParams = false;

export function generateMetadata({ params }: { params: { thema: string } }): Metadata {
  const t = themaSeite(params.thema);
  if (!t) return {};
  return {
    title: t.label,
    description: `${t.label} zur Ratswahl Oldenburg 2026: ${t.forderungen} Forderungen aus 9 Programmen, ${t.thesen} Thesen — jede Position mit Beleg.`,
  };
}

export default function ThemaSeite({ params }: { params: { thema: string } }) {
  const t = themaSeite(params.thema);
  if (!t) notFound();

  return (
    <>
      <KwKopf crumb={<KwCrumb teil={`Themen / ${t.label}`} />} />
      <main className="mx-auto w-full max-w-[1080px] px-4 pb-16 pt-9 sm:px-6 sm:pt-11 lg:px-10">
        <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-primary sm:text-xs">
          Themenfeld · {t.thesen} Thesen · {t.forderungen} Forderungen · {t.mitKapitel} von 9 Listen mit
          eigenem Kapitel
        </p>
        <h1 className="mt-2 font-display text-[26px] font-bold leading-[1.08] tracking-tight sm:mt-2.5 sm:text-[42px]">
          {t.label}
        </h1>

        <section className="mt-8">
          <Abschnitt titel="Die Streitfragen" neben="Zelle antippen → Belegzitat mit Fundstelle" />
          <div className="mt-3.5">
            <PositionsMatrix zeilen={t.zeilen} mitHinweis />
          </div>
        </section>

        <section className="mt-9">
          <Abschnitt
            titel="Was die Listen konkret fordern"
            neben="Prägnanz ●●● = eigener Schwerpunkt · Seitenzahlen springen ins Original"
          />
          <div className="mt-3.5 flex flex-col gap-2.5">
            {t.forderungenJeListe.map((l, i) => (
              <details
                key={l.slug}
                className="kw-details rounded-2xl border border-border bg-card px-4 py-3 sm:px-5 sm:py-3.5"
                open={i === 0 && l.bullets.length > 0}
              >
                <summary className="outline-none focus-visible:ring-2 focus-visible:ring-ring">
                  <span className="flex flex-wrap items-center gap-2.5">
                    <FarbPunkt farbe={l.farbe} farbeDunkel={l.farbeDunkel} size={11} />
                    <span className="text-[14.5px] font-bold sm:text-[15.5px]">{l.kurz}</span>
                    {l.landesprogramm && <BswPill kompakt />}
                    <PraegnanzDots n={l.praegnanz} />
                    <span className="ml-auto text-xs tabular-nums text-muted-foreground">
                      {l.bullets.length === 0
                        ? "keine Aussage"
                        : `${l.bullets.length} Forderungen${l.seiten.length ? ` · S. ${l.seiten.join(", ")}` : ""}`}
                    </span>
                    {l.bullets.length > 0 && (
                      <span aria-hidden className="kw-chevron text-[13px] text-muted-foreground">
                        ⌄
                      </span>
                    )}
                  </span>
                </summary>
                {l.bullets.length > 0 && (
                  <div className="mt-3 grid gap-x-9 gap-y-2 sm:grid-cols-2">
                    {l.bullets.map((b, j) => (
                      <div key={j} className="flex items-start gap-2">
                        <FarbPunkt farbe={l.farbe} farbeDunkel={l.farbeDunkel} size={5} className="mt-[7px]" />
                        <p className="text-[13px] leading-relaxed text-muted-foreground">{b}</p>
                      </div>
                    ))}
                    {l.seitenHref.length > 0 && (
                      <p className="text-xs text-muted-foreground sm:col-span-2">
                        Im Original:{" "}
                        {l.seitenHref.map((s, j) => (
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

        <div className="mt-8 flex flex-wrap items-center gap-2.5">
          <span className="text-[13px] text-muted-foreground">Weiter:</span>
          <Link
            href={`/kommunalwahl/thema/${t.zurueck.key}`}
            className="inline-flex rounded-full border border-border bg-card px-3.5 py-1.5 text-[13px] font-semibold"
          >
            ← {t.zurueck.label}
          </Link>
          <Link
            href={`/kommunalwahl/thema/${t.weiter.key}`}
            className="inline-flex rounded-full border border-border bg-card px-3.5 py-1.5 text-[13px] font-semibold"
          >
            {t.weiter.label} →
          </Link>
          <Link href="/kommunalwahl" className="ml-auto text-[13px] font-medium text-primary">
            Zurück zum Überblick
          </Link>
        </div>

        <KwFuss stand={stand()} />
      </main>
    </>
  );
}
