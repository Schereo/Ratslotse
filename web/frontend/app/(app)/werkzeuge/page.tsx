import type { Metadata } from "next";
import Link from "next/link";
import { ChevronRight, Landmark } from "lucide-react";
import { Card, PageHeader } from "@/components/ui";

export const metadata: Metadata = {
  title: "Werkzeuge",
  description: "Werkzeuge für die Arbeit im Rat der Stadt Oldenburg.",
};

/** Die Werkzeuge — eins je Karte. Kommt eins dazu, steht es hier. */
const WERKZEUGE = [
  {
    href: "/werkzeuge/mehrheiten",
    icon: Landmark,
    title: "Mehrheitsrechner",
    text: "Welche Fraktionen und Gruppen zusammen eine Mehrheit haben — im Rat, im "
      + "Verwaltungsausschuss und in jedem Fachausschuss. Mit „dabei“ und „ohne“ "
      + "eingrenzen.",
  },
];

export default function WerkzeugePage() {
  return (
    <div className="space-y-6">
      <PageHeader title="Werkzeuge" description="Für die Arbeit im Rat — sichtbar für Ratsmitglieder." />
      <div className="space-y-3">
        {WERKZEUGE.map((w) => (
          <Link key={w.href} href={w.href} className="block">
            <Card className="card-interactive flex h-full items-start gap-3 p-4">
              <span className="mt-0.5 flex h-9 w-9 flex-none items-center justify-center rounded-lg bg-primary/10 text-primary">
                <w.icon className="h-[18px] w-[18px]" aria-hidden />
              </span>
              <span className="min-w-0 flex-1">
                <span className="block font-display text-[16px] font-bold text-foreground">{w.title}</span>
                <span className="mt-1 block text-[13.5px] leading-relaxed text-muted-foreground">{w.text}</span>
              </span>
              <ChevronRight className="mt-1 h-4 w-4 flex-none text-muted-foreground" aria-hidden />
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}
