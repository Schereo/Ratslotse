import type { Metadata } from "next";
import Link from "next/link";
import { Search, Sparkles, MapPin, BarChart3, Bell, Landmark, ArrowRight } from "lucide-react";
import { Brand } from "@/components/brand";
import { SeasonalMascot } from "@/components/seasonal-mascot";
import { HeroScene } from "@/components/hero-scene";
import { PeekingChick } from "@/components/peeking-chick";
import { LandingQaDemo } from "@/components/landing-qa-demo";
import { HeaderCTA } from "@/components/landing-cta";
import { NativeRedirect } from "@/components/native-redirect";
import { LiveStats } from "@/components/live-stats";
import { Reveal } from "@/components/reveal";

export const metadata: Metadata = {
  title: "Ratslotse — Oldenburger Ratsinformationen verständlich",
  description:
    "Beschlüsse des Oldenburger Stadtrats durchsuchen, KI-Fragen stellen, Themen auf der Karte sehen und Parteien, Personen und Finanzen analysieren. Aus dem amtlichen Ratsinformationssystem, verständlich aufbereitet.",
};

const FEATURES = [
  { icon: Search, title: "Beschlüsse durchsuchen", desc: "Volltextsuche mit Filtern nach Fraktion, Themenfeld und Geldbeträgen — statt PDF-Wälzen." },
  { icon: Sparkles, title: "Frag den Rat", desc: "Stell eine Frage in normaler Sprache; die KI findet die passenden Beschlüsse und antwortet mit Quellen." },
  { icon: MapPin, title: "Themen & Karte", desc: "Orte, Straßen und Projekte mit KI-Beschreibung — und auf einer Stadtkarte, wo der Rat aktiv ist." },
  { icon: BarChart3, title: "Analyse", desc: "Wer ist im Rat präsent, wo fließt das Geld, welche Themen bewegen — Parteien, Personen, Finanzen, Trends." },
  { icon: Bell, title: "Benachrichtigungen", desc: "Lege Themen an und werde bei neuen Beschlüssen informiert — per Push oder E-Mail." },
  { icon: Landmark, title: "Amtliche Quelle", desc: "Direkt aus dem Ratsinformationssystem der Stadt Oldenburg, verlinkt zu den Originaldokumenten." },
];

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-background">
      <NativeRedirect />
      <PeekingChick />
      <header className="sticky top-0 z-30 border-b border-border bg-background/90 backdrop-blur">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-5 py-3.5">
          <Link href="/">
            <Brand />
          </Link>
          <HeaderCTA />
        </div>
      </header>

      <main>
        {/* Hero — text (server-rendered for SEO) + Lotti-Familien-Hafenszene */}
        <section className="relative overflow-hidden">
          <div className="pointer-events-none absolute inset-0 bg-gradient-to-b from-sky-50 to-transparent dark:from-slate-900/40" aria-hidden />
          <div className="pointer-events-none absolute inset-0 bg-waves opacity-60" aria-hidden />
          <div className="relative z-10 mx-auto grid max-w-6xl items-center gap-10 px-5 py-16 sm:py-24 lg:grid-cols-2">
            <div className="text-center lg:text-left">
              <SeasonalMascot pose="wave" bob className="mx-auto mb-5 h-24 w-24 lg:hidden" />
              <p className="inline-flex items-center gap-1.5 rounded-full border border-primary/20 bg-primary/10 px-3 py-1 text-xs font-semibold text-primary">
                Stadtrat Oldenburg
              </p>
              <h1 className="mt-4 text-4xl font-bold tracking-tight text-foreground sm:text-5xl">
                Was beschließt eigentlich der Rat?
              </h1>
              <p className="mx-auto mt-5 max-w-xl text-lg leading-relaxed text-muted-foreground lg:mx-0">
                Ratslotse macht die Beschlüsse des Oldenburger Stadtrats durchsuchbar, vergleichbar und verständlich —
                mit KI-Fragen, Themen-Karten und Analysen. Aus der amtlichen Quelle, ohne PDF-Wälzen.
              </p>
              <div className="mt-8 flex flex-wrap items-center justify-center gap-3 lg:justify-start">
                <Link href="/register" className="inline-flex items-center gap-1.5 rounded-xl bg-brand-gradient px-5 py-2.5 text-sm font-semibold text-primary-foreground shadow-lifted transition-all hover:-translate-y-0.5 hover:opacity-95">
                  Kostenlos registrieren <ArrowRight className="h-4 w-4" />
                </Link>
                <Link href="/technik" className="inline-flex items-center rounded-xl border border-border bg-background/70 px-5 py-2.5 text-sm font-medium text-foreground backdrop-blur transition-colors hover:bg-muted">
                  Wie es funktioniert
                </Link>
              </div>
              <LiveStats />
            </div>
            <div className="relative">
              <HeroScene />
            </div>
          </div>
        </section>

        {/* KI-Frage-Demo — das Killerfeature direkt zeigen statt nur beschreiben */}
        <section className="mx-auto max-w-3xl px-5 pb-16 pt-4">
          <div className="text-center">
            <h2 className="text-2xl font-bold tracking-tight text-foreground">Frag den Rat — in normaler Sprache</h2>
            <p className="mx-auto mt-2 max-w-xl text-muted-foreground">
              Die KI durchsucht alle Beschlüsse des Stadtrats und antwortet mit Quellen. So sieht das aus:
            </p>
          </div>
          <LandingQaDemo />
        </section>

        {/* Features */}
        <section className="border-y border-border bg-muted/30">
          <div className="mx-auto max-w-5xl px-5 py-16">
            <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
              {FEATURES.map((f, i) => {
                const Icon = f.icon;
                return (
                  <Reveal key={f.title} delay={i * 80}>
                    <div className="h-full rounded-xl border border-border bg-background p-5 transition-shadow hover:shadow-md">
                      <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
                        <Icon className="h-5 w-5" />
                      </span>
                      <h3 className="mt-3 font-semibold text-foreground">{f.title}</h3>
                      <p className="mt-1 text-sm leading-relaxed text-muted-foreground">{f.desc}</p>
                    </div>
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
            <Link href="/technik" className="hover:text-foreground">Technik</Link>
            <Link href="/changelog" className="hover:text-foreground">Changelog</Link>
            <Link href="/impressum" className="hover:text-foreground">Impressum</Link>
            <Link href="/datenschutz" className="hover:text-foreground">Datenschutz</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
