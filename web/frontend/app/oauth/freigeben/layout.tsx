import type { Metadata } from "next";

/** Titel der Freigabe-Seite; `page.tsx` ist eine Client-Komponente. Die Seite
 *  gehört in keine Suchmaschine — sie ist nur als Sprungziel eines Agenten da. */
export const metadata: Metadata = {
  title: "Agent verbinden",
  description: "Einem eigenen Agenten erlauben, die Ratsdaten bei Ratslotse zu lesen.",
  robots: { index: false, follow: false },
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
