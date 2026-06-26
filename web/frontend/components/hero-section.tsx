"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { ArrowRight } from "lucide-react";
import { HeroCanvas } from "@/components/hero-canvas";
import { HeroMap } from "@/components/hero-map";
import { LiveStats } from "@/components/live-stats";

const EYEBROW = "Stadtrat Oldenburg";
const TITLE = "Was beschließt eigentlich der Rat?";
const SUB =
  "Ratslotse macht die Beschlüsse des Oldenburger Stadtrats durchsuchbar, vergleichbar und verständlich — mit KI-Fragen, Themen-Karten und Analysen. Aus der amtlichen Quelle, ohne PDF-Wälzen.";

function Ctas({ center }: { center?: boolean }) {
  return (
    <div className={`mt-8 flex flex-wrap items-center gap-3 ${center ? "justify-center" : "justify-center lg:justify-start"}`}>
      <Link href="/register" className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-5 py-2.5 text-sm font-medium text-primary-foreground shadow-sm transition-opacity hover:opacity-90">
        Kostenlos registrieren <ArrowRight className="h-4 w-4" />
      </Link>
      <Link href="/technik" className="inline-flex items-center rounded-lg border border-border bg-background/70 px-5 py-2.5 text-sm font-medium text-foreground backdrop-blur transition-colors hover:bg-muted">
        Wie es funktioniert
      </Link>
    </div>
  );
}

// (a) 2-column: text left, framed rotating 3D map right.
function VariantA() {
  const [failed, setFailed] = useState(false);
  return (
    <section className="relative overflow-hidden">
      <HeroCanvas />
      <div className="relative z-10 mx-auto grid max-w-6xl items-center gap-10 px-5 py-16 sm:py-24 lg:grid-cols-2">
        <div className="text-center lg:text-left">
          <p className="text-sm font-medium text-primary">{EYEBROW}</p>
          <h1 className="mt-3 text-4xl font-bold tracking-tight text-foreground sm:text-5xl">{TITLE}</h1>
          <p className="mx-auto mt-5 max-w-xl text-lg leading-relaxed text-muted-foreground lg:mx-0">{SUB}</p>
          <Ctas />
          <LiveStats />
        </div>
        <div className="hidden lg:block">
          <div className="relative aspect-[4/3] overflow-hidden rounded-2xl border border-border bg-muted shadow-xl">
            {failed ? <HeroCanvas /> : <HeroMap onError={() => setFailed(true)} className="absolute inset-0 h-full w-full" />}
          </div>
        </div>
      </div>
    </section>
  );
}

// (b) full-bleed 3D map background, text overlaid with a readability gradient.
function VariantB() {
  const [failed, setFailed] = useState(false);
  return (
    <section className="relative overflow-hidden">
      <HeroCanvas />
      {!failed && <HeroMap onError={() => setFailed(true)} className="absolute inset-0 hidden h-full w-full md:block" />}
      <div className="pointer-events-none absolute inset-0 bg-gradient-to-b from-background/90 via-background/55 to-background/95" />
      <div className="relative z-10 mx-auto max-w-3xl px-5 py-20 text-center sm:py-28">
        <p className="text-sm font-medium text-primary">{EYEBROW}</p>
        <h1 className="mt-3 text-4xl font-bold tracking-tight text-foreground drop-shadow-sm sm:text-6xl">{TITLE}</h1>
        <p className="mx-auto mt-5 max-w-2xl text-lg leading-relaxed text-muted-foreground">{SUB}</p>
        <Ctas center />
        <LiveStats />
      </div>
    </section>
  );
}

function HeroInner() {
  const variant = useSearchParams().get("hero") === "b" ? "b" : "a";
  return variant === "b" ? <VariantB /> : <VariantA />;
}

export function HeroSection() {
  return (
    <Suspense fallback={<div className="h-[60vh]" />}>
      <HeroInner />
    </Suspense>
  );
}
