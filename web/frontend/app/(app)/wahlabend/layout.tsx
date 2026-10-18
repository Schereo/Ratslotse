import type { Metadata } from "next";
import { datumLang, holeWahl, istExport } from "@/lib/share-metadata";

// Der Wahlabend lebt seit 10/2026 IN der App-Hülle (wie /wahlen, s. dort):
// angemeldet mit Seitenleiste, ohne Konto in der PublicShell — die Pfade stehen
// in lib/public-routes.ts. Er hängt nicht am Umgebungs-Gate, sondern am
// Feature-Schalter `wahlabend` — die Seite soll am Wahlabend auf Prod laufen
// und danach ohne Deploy wieder dunkel werden können (kern/features.py).
//
// Titel und Beschreibung kommen seit 09/2026 aus der Wahl selbst
// (`/api/app-config`), nicht aus zwei Literalen hier: Sie stehen in jeder
// geteilten Vorschau und in jedem Suchtreffer, und beim nächsten Mal stünde
// dort sonst die Wahl von 2026.
export async function generateMetadata(): Promise<Metadata> {
  const wahl = istExport() ? null : await holeWahl();
  const name = wahl && wahl.kind === "council" ? wahl.short_title : "Ratswahl Oldenburg";
  const wann = wahl && wahl.kind === "council" ? ` am ${datumLang(wahl.date)}` : "";
  return {
    title: `Wahlabend — ${name} | Ratslotse`,
    description:
      `${name}${wann}: Auszählungsstand, Sitze je Liste und Wahlbereich, wer nach dem ` +
      "Kommunalwahlgesetz gerade im Rat wäre — aus den Open-Data-Zahlen der Stadt, live nachgerechnet.",
    openGraph: {
      type: "website",
      locale: "de_DE",
      siteName: "Ratslotse",
      title: `Wahlabend — ${name}`,
      description: "Auszählungsstand, Sitze und Kandidat*innen je Wahlbereich, live nachgerechnet.",
    },
  };
}

export default function WahlabendLayout({ children }: { children: React.ReactNode }) {
  return children;
}
