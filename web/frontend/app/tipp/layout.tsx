import type { Metadata } from "next";
import { holeWahl, istExport } from "@/lib/share-metadata";

// /tipp lebt wie /wahlabend AUSSERHALB von app/(app)/: kein Konto-Gate,
// eigener Kopf. Anders als der Wahlabend hängt es an einem EIGENEN
// Feature-Schalter (`tippspiel`, kern/features.py) — die Seite soll auch
// nach dem Wahlabend noch als Rückblick laufen können, unabhängig davon,
// wann der Wahlabend-Schalter selbst wieder abgeschaltet wird.
//
// Titel und Beschreibung kommen aus der Wahl (`/api/app-config`), nicht aus
// Literalen: „52 Sitze auf 16 Wahllisten" wäre beim nächsten Mal falsch, und
// die Zahl steht in jeder geteilten Vorschau.
export async function generateMetadata(): Promise<Metadata> {
  // Die Wahl im Fokus (`elections.focus`): Vor dem 27.09.2026 ist das die
  // Stichwahl, und dann wird nicht verteilt, sondern in Prozent getippt.
  const wahl = istExport() ? null : await holeWahl();
  const name = wahl?.short_title ?? "Ratswahl Oldenburg";
  const sitzwahl = !wahl || wahl.kind === "council";
  const beschreibung = sitzwahl
    ? `Wie geht die ${name} aus? Tippe die Sitzverteilung, auf Wunsch die OB-Wahl und die Wahlbeteiligung. `
    : `Wie geht die ${name} aus? Tippe die Prozente der Kandidaturen und die Wahlbeteiligung. `;
  return {
    title: `Tippspiel — ${name} | Ratslotse`,
    description: beschreibung + "Ohne Konto mitmachen und am Wahlabend die Rangliste verfolgen.",
    openGraph: {
      type: "website",
      locale: "de_DE",
      siteName: "Ratslotse",
      title: `Tippspiel — ${name}`,
      description: sitzwahl
        ? `Wie geht die ${name} aus? Verteile die Sitze auf die Wahllisten und mach ohne Konto mit.`
        : `Wie geht die ${name} aus? Tippe die Prozente und die Wahlbeteiligung — ohne Konto.`,
    },
  };
}

export default function TippLayout({ children }: { children: React.ReactNode }) {
  return <div className="min-h-[100dvh] bg-background text-foreground">{children}</div>;
}
