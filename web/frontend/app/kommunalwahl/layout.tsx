import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { NachWahlStreifen } from "@/components/kommunalwahl/countdown";

// Der Wahlprogramm-Vergleich lebt bewusst AUSSERHALB von app/(app)/ — damit
// greift der Auth-Gate des App-Layouts gar nicht erst, wie bei /changelog
// (Bauplan §5.5). Kopf- und Fußzeile setzen die Seiten selbst (die Breadcrumb
// unterscheidet sich je Route); hier liegt nur, was wirklich allen gemeinsam
// ist: Metadata-Defaults und der Nach-der-Wahl-Streifen (§5.6).
//
// Umgebungs-Gate: Der Bereich ist nur auf dev.ratslotse.de freigeschaltet
// (Freunde-Zugang via Basic-Auth). Nur der Dev-Build setzt
// NEXT_PUBLIC_RATSLOTSE_ENV=dev (deploy-dev.yml); im Prod-Build ist die
// Konstante zur Build-Zeit false einkompiliert und jede /kommunalwahl-Route
// ein 404 — der Code darf deshalb gefahrlos mit Releases nach main fahren.
const KOMMUNALWAHL_FREI = process.env.NEXT_PUBLIC_RATSLOTSE_ENV === "dev";

// Als Funktion statt statischem Export, damit auch Titel/OG-Tags hinterm
// Gate bleiben — sonst trüge die 404-Seite auf Prod den Kommunalwahl-Titel.
export function generateMetadata(): Metadata {
  if (!KOMMUNALWAHL_FREI) return {};
  return metadataFrei;
}

const metadataFrei: Metadata = {
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
  if (!KOMMUNALWAHL_FREI) notFound();
  return (
    <div className="min-h-[100dvh] bg-background text-foreground">
      <NachWahlStreifen />
      {children}
    </div>
  );
}
