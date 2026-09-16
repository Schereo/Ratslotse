import type { Metadata } from "next";

// /stichwahl/… sind Werkzeuge, die es nur mit Link gibt: kein Knopf führt
// hierher, kein Suchindex soll sie kennen, die Sitemap nennt sie nicht
// (app/sitemap.ts). Der Schutz selbst sitzt im Backend — der Endpunkt
// antwortet ohne den Token wie für eine Adresse, die es nicht gibt.
export const metadata: Metadata = {
  title: "Stichwahl | Ratslotse",
  robots: { index: false, follow: false },
};

export default function StichwahlLayout({ children }: { children: React.ReactNode }) {
  return <div className="min-h-[100dvh] bg-background text-foreground">{children}</div>;
}
