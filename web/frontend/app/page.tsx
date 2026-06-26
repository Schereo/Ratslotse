import type { Metadata } from "next";
import Link from "next/link";
import { Search, Sparkles, MapPin, BarChart3, Bell, Landmark } from "lucide-react";
import { BrandMark } from "@/components/brand";
import { HeaderCTA } from "@/components/landing-cta";
import { HeroSection } from "@/components/hero-section";
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
        {/* Hero (switchable a/b via ?hero= for the live comparison) */}
        <HeroSection />

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
          <div className="flex gap-4">
            <Link href="/technik" className="hover:text-foreground">Technik</Link>
            <Link href="/impressum" className="hover:text-foreground">Impressum</Link>
            <Link href="/datenschutz" className="hover:text-foreground">Datenschutz</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
