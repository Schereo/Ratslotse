import type { Metadata } from "next";
import Link from "next/link";
import { Search, Sparkles, MapPin, BarChart3, Bell, Landmark, ArrowRight } from "lucide-react";
import { BrandMark } from "@/components/brand";
import { HeaderCTA } from "@/components/landing-cta";
import { NativeRedirect } from "@/components/native-redirect";
import { HeroCanvas } from "@/components/hero-canvas";
import { HeroMapFrame } from "@/components/hero-map-frame";
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
  { icon: Bell, title: "Benachrichtigungen", desc: "Lege Themen an und werde bei neuen Beschlüssen informiert — per Telegram oder E-Mail." },
  { icon: Landmark, title: "Amtliche Quelle", desc: "Direkt aus dem Ratsinformationssystem der Stadt Oldenburg, verlinkt zu den Originaldokumenten." },
];

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-background">
      <NativeRedirect />
      <header className="sticky top-0 z-30 border-b border-border bg-background/90 backdrop-blur">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-5 py-3.5">
          <Link href="/" className="flex items-center gap-2">
            <BrandMark />
            <span className="font-semibold text-foreground">Ratslotse</span>
          </Link>
          <HeaderCTA />
        </div>
      </header>

      <main>
        {/* Hero — text (server-rendered for SEO) + framed 3D Oldenburg map */}
        <section className="relative overflow-hidden">
          <HeroCanvas />
          <div className="relative z-10 mx-auto grid max-w-6xl items-center gap-10 px-5 py-16 sm:py-24 lg:grid-cols-2">
            <div className="text-center lg:text-left">
              <p className="text-sm font-medium text-primary">Stadtrat Oldenburg</p>
              <h1 className="mt-3 text-4xl font-bold tracking-tight text-foreground sm:text-5xl">
                Was beschließt eigentlich der Rat?
              </h1>
              <p className="mx-auto mt-5 max-w-xl text-lg leading-relaxed text-muted-foreground lg:mx-0">
                Ratslotse macht die Beschlüsse des Oldenburger Stadtrats durchsuchbar, vergleichbar und verständlich —
                mit KI-Fragen, Themen-Karten und Analysen. Aus der amtlichen Quelle, ohne PDF-Wälzen.
              </p>
              <div className="mt-8 flex flex-wrap items-center justify-center gap-3 lg:justify-start">
                <Link href="/register" className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-5 py-2.5 text-sm font-medium text-primary-foreground shadow-sm transition-opacity hover:opacity-90">
                  Kostenlos registrieren <ArrowRight className="h-4 w-4" />
                </Link>
                <Link href="/technik" className="inline-flex items-center rounded-lg border border-border bg-background/70 px-5 py-2.5 text-sm font-medium text-foreground backdrop-blur transition-colors hover:bg-muted">
                  Wie es funktioniert
                </Link>
              </div>
              <LiveStats />
            </div>
            <div className="hidden lg:block">
              <HeroMapFrame />
            </div>
          </div>
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
        <section className="mx-auto max-w-3xl px-5 py-16 text-center">
          <h2 className="text-2xl font-bold tracking-tight text-foreground">Bereit, reinzuschauen?</h2>
          <p className="mt-2 text-muted-foreground">Konto erstellen und den Rat durchsuchen — kostenlos.</p>
          <div className="mt-6 flex justify-center">
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
