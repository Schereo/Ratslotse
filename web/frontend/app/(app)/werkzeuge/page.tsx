import type { Metadata } from "next";
import Link from "next/link";
import { ArrowRight, Check, Mail } from "lucide-react";
import { Button, Card, PageHeader } from "@/components/ui";
import { Mascot } from "@/components/mascot";
import { MehrheitenVorschau } from "@/components/werkzeuge/vorschau";
import { KONTAKT_EMAIL, KONTAKT_MAILTO } from "@/lib/kontakt";
import { vorschlagMailto } from "@/lib/werkzeuge";

export const metadata: Metadata = {
  title: "Werkzeuge",
  description: "Werkzeuge für die Arbeit im Rat der Stadt Oldenburg.",
};

/**
 * Die Übersicht der Werkzeuge (Tims Wunsch 22.11.2026): je Werkzeug eine
 * Karte mit einem kleinen Bild, was es tut, und dem Weg hinein — dahinter ein
 * Platz für das nächste, mit der Einladung, eines vorzuschlagen.
 *
 * Kommt ein Werkzeug dazu, steht es hier: Bild, Name, ein Satz, drei Punkte.
 */
const WERKZEUGE = [
  {
    href: "/werkzeuge/mehrheiten",
    bild: MehrheitenVorschau,
    title: "Mehrheitsrechner",
    text: "Mit welchen Fraktionen und Gruppen es für eine Mehrheit reicht.",
    punkte: [
      "Rat, Verwaltungsausschuss und jeder Fachausschuss",
      "Fraktionen auf „dabei“ oder „ohne“ setzen",
      "Zeigt, wer einer Auswahl noch zur Mehrheit fehlt",
    ],
  },
];

export default function WerkzeugePage() {
  return (
    <div className="space-y-6">
      <PageHeader title="Werkzeuge" description="Für die Arbeit im Rat — sichtbar für Ratsmitglieder." />
      <div className="@container">
        <div className="grid gap-4 @3xl:grid-cols-2 @6xl:grid-cols-3">
          {WERKZEUGE.map((w) => (
            <Link key={w.href} href={w.href} className="group block">
              <Card className="card-interactive flex h-full flex-col overflow-hidden">
                <div className="flex items-center justify-center border-b border-border/70 bg-primary/[0.04] px-6 pb-3 pt-5">
                  <w.bild className="w-full max-w-[250px]" />
                </div>
                <div className="flex flex-1 flex-col p-4 sm:p-5">
                  <h2 className="font-display text-[17px] font-bold text-foreground">{w.title}</h2>
                  <p className="mt-1 text-[14px] leading-relaxed text-muted-foreground">{w.text}</p>
                  <ul className="mt-3 space-y-1.5">
                    {w.punkte.map((p) => (
                      <li key={p} className="flex items-start gap-2 text-[13.5px] leading-snug text-foreground">
                        <Check className="mt-0.5 h-3.5 w-3.5 flex-none text-primary" aria-hidden />
                        {p}
                      </li>
                    ))}
                  </ul>
                  <span className="mt-auto inline-flex items-center gap-1 pt-4 text-sm font-medium text-primary">
                    Öffnen
                    <ArrowRight className="h-4 w-4 transition-transform duration-fluss group-hover:translate-x-0.5" aria-hidden />
                  </span>
                </div>
              </Card>
            </Link>
          ))}

          {/* Gestrichelt = noch nicht fertig (DESIGNSPRACHE § 4). */}
          <section
            aria-labelledby="werkzeug-vorschlagen"
            className="flex h-full flex-col items-center justify-center rounded-xl border border-dashed border-input bg-card/60 px-6 py-8 text-center"
          >
            <Mascot pose="point" decorative className="h-20 w-20" />
            <h2 id="werkzeug-vorschlagen" className="mt-2 font-display text-[17px] font-bold text-foreground">
              Weitere Werkzeuge folgen
            </h2>
            <p className="mt-1 max-w-sm text-[14px] leading-relaxed text-muted-foreground">
              Dir fehlt etwas für die Ratsarbeit — eine Auswertung, eine Übersicht, eine Rechenhilfe?
              Schreib uns, was dir helfen würde.
            </p>
            <Button asChild variant="secondary" className="mt-4">
              <a href={vorschlagMailto(KONTAKT_EMAIL)}>
                <Mail aria-hidden />
                Werkzeug vorschlagen
              </a>
            </Button>
            <p className="mt-2.5 text-xs text-muted-foreground">
              Per Mail an{" "}
              <a href={KONTAKT_MAILTO} className="text-primary underline-offset-2 hover:underline">{KONTAKT_EMAIL}</a>
            </p>
          </section>
        </div>
      </div>
    </div>
  );
}
