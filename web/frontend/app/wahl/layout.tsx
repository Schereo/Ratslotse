import type { Metadata } from "next";

// /wahl ist eine Weiterleitung, keine Seite — sie soll in keinem Suchindex
// landen (dort gehören /wahlen und die Wahlseiten selbst hin).
export const metadata: Metadata = {
  title: "Wahl | Ratslotse",
  robots: { index: false, follow: true },
};

export default function WahlLayout({ children }: { children: React.ReactNode }) {
  return <div className="min-h-[100dvh] bg-background text-foreground">{children}</div>;
}
