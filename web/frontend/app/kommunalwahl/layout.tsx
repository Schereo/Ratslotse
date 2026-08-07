import type { Metadata } from "next";
import { NachWahlStreifen } from "@/components/kommunalwahl/countdown";

// Der Wahlprogramm-Vergleich lebt bewusst AUSSERHALB von app/(app)/ — damit
// greift der Auth-Gate des App-Layouts gar nicht erst, wie bei /changelog
// (Bauplan §5.5). Kopf- und Fußzeile setzen die Seiten selbst (die Breadcrumb
// unterscheidet sich je Route); hier liegt nur, was wirklich allen gemeinsam
// ist: Metadata-Defaults und der Nach-der-Wahl-Streifen (§5.6).

export const metadata: Metadata = {
  title: {
    default: "Kommunalwahl 2026 — Wahlprogramme im Vergleich | Ratslotse",
    template: "%s — Kommunalwahl 2026 | Ratslotse",
  },
  description:
    "Ratswahl Oldenburg am 13. September 2026: alle Wahlprogramme gelesen, 44 Thesen, jede Aussage mit Beleg und Link ins Original. Ohne Empfehlung.",
  openGraph: {
    type: "website",
    locale: "de_DE",
    siteName: "Ratslotse",
    title: "Kommunalwahl 2026 — Wahlprogramme, verständlich verglichen",
    description:
      "Wer steht wofür? Alle Programme zur Ratswahl Oldenburg, belegt und vergleichbar — von Ratslotse.",
  },
};

export default function KommunalwahlLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-[100dvh] bg-background text-foreground">
      <NachWahlStreifen />
      {children}
    </div>
  );
}
