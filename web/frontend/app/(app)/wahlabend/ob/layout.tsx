import type { Metadata } from "next";

// Der erste Wahlgang der OB-Wahl als eigene Seite. Bis 10/2026 stand er in
// der Übersicht /wahlen als einzige gelaufene Wahl ohne Link (Tims Befund
// 16.10.2026). Hülle wie /wahlabend, Feature-Schalter `wahlabend`.
export const metadata: Metadata = {
  title: "OB-Wahl 2026 in Oldenburg: Ergebnis des ersten Wahlgangs | Ratslotse",
  description:
    "Ergebnis des ersten Wahlgangs der Oldenburger Oberbürgermeisterwahl vom 13. September 2026: alle Kandidaturen mit Stimmen und Anteil.",
  openGraph: {
    type: "website",
    locale: "de_DE",
    siteName: "Ratslotse",
    title: "OB-Wahl 2026 in Oldenburg: Ergebnis des ersten Wahlgangs",
    description: "Alle Kandidaturen mit Stimmen und Anteil, und wer in die Stichwahl ging.",
  },
};

export default function ObLayout({ children }: { children: React.ReactNode }) {
  return children;
}
