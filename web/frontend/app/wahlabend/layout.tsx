import type { Metadata } from "next";

// Der Wahlabend lebt wie /kommunalwahl und /changelog AUSSERHALB von app/(app)/:
// kein Konto-Gate, eigener Kopf. Anders als der Wahlprogramm-Vergleich hängt
// er nicht am Umgebungs-Gate, sondern am Feature-Schalter `wahlabend` — die
// Seite soll am 13.09.2026 auf Prod laufen und danach ohne Deploy wieder
// dunkel werden können (kern/features.py).
export const metadata: Metadata = {
  title: "Wahlabend — Ratswahl Oldenburg 2026 | Ratslotse",
  description:
    "Ratswahl Oldenburg am 13. September 2026: Auszählungsstand, Sitze je Liste und Wahlbereich, wer nach dem Kommunalwahlgesetz gerade im Rat wäre — aus den Open-Data-Zahlen der Stadt, live nachgerechnet.",
  openGraph: {
    type: "website",
    locale: "de_DE",
    siteName: "Ratslotse",
    title: "Wahlabend — Ratswahl Oldenburg 2026",
    description: "Auszählungsstand, Sitze und Kandidat*innen je Wahlbereich, live nachgerechnet.",
  },
};

export default function WahlabendLayout({ children }: { children: React.ReactNode }) {
  return <div className="min-h-[100dvh] bg-background text-foreground">{children}</div>;
}
