import type { Metadata } from "next";
import Link from "next/link";
import { Search, Sparkles, MapPin, BarChart3, Bell, Landmark, ArrowRight } from "lucide-react";
import { Brand } from "@/components/brand";
import { SeasonalMascot } from "@/components/seasonal-mascot";
import { PeekingChick } from "@/components/peeking-chick";
import { LandingQaDemo } from "@/components/landing-qa-demo";
import { HeaderCTA } from "@/components/landing-cta";
import { NativeRedirect } from "@/components/native-redirect";
import { LiveStats } from "@/components/live-stats";
import { HeuteLeiste } from "@/components/heute-leiste";
import { SeasonalFamily } from "@/components/seasonal-mascot";
import { Reveal } from "@/components/reveal";
import { cn } from "@/lib/utils";

export const metadata: Metadata = {
  title: "Ratslotse — Oldenburger Ratsinformationen verständlich",
  description:
    "Beschlüsse des Oldenburger Stadtrats durchsuchen, KI-Fragen stellen, Themen auf der Karte sehen und Parteien, Personen und Finanzen analysieren. Aus dem amtlichen Ratsinformationssystem, verständlich aufbereitet.",
};

// Bento-Anordnung statt drei gleicher Spalten: `wide`-Karten spannen auf
// Desktop zwei Spalten (Zick-Zack 2-1 / 1-2 / 1-2), `hero` hebt das
// Killerfeature farblich heraus. RL-U08: jede Karte verlinkt auf ihr Ziel —
// der Login-Gate der App übernimmt, wenn noch kein Konto da ist.
const FEATURES = [
  { icon: Sparkles, title: "Frag den Rat", desc: "Stell eine Frage in normaler Sprache; die KI findet die passenden Beschlüsse und antwortet mit Quellen und Fußnoten.", href: "/council?tab=decisions&mode=fragen", wide: true, hero: true },
  { icon: Search, title: "Beschlüsse durchsuchen", desc: "Volltextsuche mit Filtern nach Fraktion, Themenfeld und Geldbeträgen — statt PDF-Wälzen.", href: "/council" },
  { icon: MapPin, title: "Themen & Karte", desc: "Orte, Straßen und Projekte mit KI-Beschreibung — und auf einer Stadtkarte, wo der Rat aktiv ist.", href: "/council?tab=themen" },
  { icon: BarChart3, title: "Analyse", desc: "Wer ist im Rat präsent, wo fließt das Geld, welche Themen bewegen — Parteien, Personen, Finanzen, Trends.", href: "/council?tab=analysis", wide: true },
  { icon: Landmark, title: "Amtliche Quelle", desc: "Direkt aus dem Ratsinformationssystem der Stadt Oldenburg, verlinkt zu den Originaldokumenten.", href: "/docs" },
  { icon: Bell, title: "Benachrichtigungen", desc: "Lege Themen an und werde bei neuen Beschlüssen informiert — per Push oder E-Mail, sobald der Rat entscheidet.", href: "/topics", wide: true },
];

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-background">
      <NativeRedirect />
      <PeekingChick />
      {/* Tastatur-Nutzer:innen springen direkt zum Inhalt (visuell versteckt bis fokussiert). */}
      <a
        href="#inhalt"
        className="sr-only focus:not-sr-only focus:absolute focus:left-3 focus:top-3 focus:z-50 focus:rounded-lg focus:bg-primary focus:px-4 focus:py-2 focus:text-sm focus:font-semibold focus:text-primary-foreground"
      >
        Zum Inhalt springen
      </a>
      <header className="sticky top-0 z-30 border-b border-border bg-background/90 backdrop-blur">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-5 py-3.5">
          <Link href="/">
            <Brand />
          </Link>
          <HeaderCTA />
        </div>
      </header>

      <HeuteLeiste />

      <main id="inhalt">
        {/* Hero — text (server-rendered for SEO) + Lotti-Familien-Hafenszene */}
        <section className="relative overflow-hidden">
          <div className="pointer-events-none absolute inset-0 bg-gradient-to-b from-sky-50 to-transparent dark:from-slate-900/40" aria-hidden />
          <div className="pointer-events-none absolute inset-0 bg-waves opacity-60" aria-hidden />
          <div className="relative z-10 mx-auto grid max-w-6xl items-center gap-12 px-5 py-16 sm:py-20 lg:grid-cols-2 lg:gap-10">
            <div className="text-center lg:text-left">
              <p className="inline-flex items-center gap-1.5 rounded-full border border-primary/20 bg-primary/10 px-3 py-1 text-xs font-semibold text-primary">
                Stadtrat Oldenburg
              </p>
              <h1 className="mt-4 hyphens-none text-balance font-display text-[40px] font-extrabold leading-[1.05] tracking-tight text-foreground sm:text-[52px] lg:text-[62px]">
                Was beschließt eigentlich der Rat?
              </h1>
              <p className="mx-auto mt-5 max-w-xl text-lg leading-relaxed text-muted-foreground lg:mx-0">
                Ratslotse macht die Beschlüsse des Oldenburger Stadtrats durchsuchbar, vergleichbar und verständlich —
                mit KI-Fragen, Themen-Karten und Analysen. Aus der amtlichen Quelle, ohne PDF-Wälzen.
              </p>
              <div className="mt-8 flex flex-wrap items-center justify-center gap-3 lg:justify-start">
                {/* DIE eine Signal-Handlung der Landing (RL-101). */}
                <Link href="/register" className="inline-flex items-center gap-1.5 rounded-xl bg-signal px-5 py-2.5 text-sm font-semibold text-signal-foreground shadow-[0_8px_22px_-10px_hsl(19_92%_45%/0.6)] transition-[opacity,transform] duration-200 ease-out-strong active:scale-[0.97] [@media(hover:hover)_and_(pointer:fine)]:hover:-translate-y-0.5 [@media(hover:hover)_and_(pointer:fine)]:hover:opacity-95">
                  Kostenlos registrieren <ArrowRight className="h-4 w-4" />
                </Link>
                {/* /docs ist die statische Technik-Doku außerhalb des App-Routers — plain <a>. */}
                <a href="/docs" className="inline-flex items-center rounded-xl border border-border bg-background/70 px-5 py-2.5 text-sm font-medium text-foreground backdrop-blur transition-colors hover:bg-muted">
                  Wie es funktioniert
                </a>
              </div>
              <LiveStats inline />
            </div>
            {/* Live-Demo als Hero-Beweis (RL-302): Lotti schwebt über der Karte,
                Badge „LIVE AUSPROBIEREN"; Autoplay + Sizer aus landing-qa-demo. */}
            <div className="relative mt-8 lg:mt-0">
              <SeasonalMascot pose="point" bob className="pointer-events-none absolute -top-14 right-16 z-10 h-[104px] w-[104px] sm:-top-16 sm:h-[116px] sm:w-[116px]" />
              <span className="absolute -top-3 left-5 z-10 rounded-full bg-signal px-3 py-1 font-mono text-[10px] font-semibold uppercase tracking-[0.14em] text-signal-foreground shadow-sm">
                Live ausprobieren
              </span>
              <LandingQaDemo />
            </div>
          </div>
        </section>

        {/* Familien-Fries: die Hafenszene weicht der Demo im Hero und wird zum
            ruhigen Band — Claim links, Lotti-Familie rechts (RL-302). */}
        <section className="border-y border-border bg-muted/20">
          <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-6 px-5 py-8">
            <p className="max-w-md text-balance font-display text-lg font-bold text-foreground">
              Die ganze Lotsen-Familie an Bord — damit Stadtpolitik kein Fachchinesisch bleibt.
            </p>
            <SeasonalFamily className="h-20 sm:h-24" />
          </div>
        </section>

        {/* Features — asymmetrisches Bento statt drei gleicher Spalten */}
        <section className="border-y border-border bg-muted/30">
          <div className="mx-auto max-w-5xl px-5 py-16">
            <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
              {FEATURES.map((f, i) => {
                const Icon = f.icon;
                const card = (
                  <div
                    className={cn(
                      "h-full rounded-xl border p-5 transition-[box-shadow,border-color] duration-200",
                      "[@media(hover:hover)_and_(pointer:fine)]:hover:border-primary/30 [@media(hover:hover)_and_(pointer:fine)]:hover:shadow-lifted",
                      f.hero
                        ? "border-primary/25 bg-gradient-to-br from-primary/[0.07] to-transparent"
                        : "border-border bg-background",
                    )}
                  >
                    <span
                      className={cn(
                        "flex h-10 w-10 items-center justify-center rounded-lg",
                        f.hero ? "bg-primary text-primary-foreground shadow-sm shadow-primary/30" : "bg-primary/10 text-primary",
                      )}
                    >
                      <Icon className="h-5 w-5" />
                    </span>
                    <h3 className="mt-3 font-semibold text-foreground">{f.title}</h3>
                    <p className="mt-1 max-w-prose text-sm leading-relaxed text-muted-foreground">{f.desc}</p>
                  </div>
                );
                const linkClass = "block h-full rounded-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2";
                return (
                  <Reveal key={f.title} delay={i * 80} className={f.wide ? "lg:col-span-2" : undefined}>
                    {/* /docs liegt außerhalb des App-Routers — plain <a>. */}
                    {f.href === "/docs"
                      ? <a href={f.href} className={linkClass}>{card}</a>
                      : <Link href={f.href} className={linkClass}>{card}</Link>}
                  </Reveal>
                );
              })}
            </div>
          </div>
        </section>

        {/* Closing CTA */}
        <section className="mx-auto max-w-3xl px-5 py-16">
          <div className="flex flex-col items-center gap-5 rounded-3xl border border-border bg-card p-8 text-center shadow-lifted sm:p-10">
            <SeasonalMascot pose="celebrate" className="h-24 w-24" />
            <div>
              <h2 className="text-2xl font-bold tracking-tight text-foreground">Bereit, reinzuschauen?</h2>
              <p className="mt-2 text-muted-foreground">Konto erstellen und den Rat durchsuchen — kostenlos.</p>
            </div>
            <HeaderCTA />
          </div>
        </section>
      </main>

      <footer className="border-t border-border">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-3 px-5 py-6 text-sm text-muted-foreground">
          <span>© Ratslotse — Ratsinformationen für Oldenburg</span>
          <div className="flex flex-wrap gap-4">
            <a href="/docs" className="hover:text-foreground">Technik-Doku</a>
            <Link href="/changelog" className="hover:text-foreground">Changelog</Link>
            <Link href="/impressum" className="hover:text-foreground">Impressum</Link>
            <Link href="/datenschutz" className="hover:text-foreground">Datenschutz</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
