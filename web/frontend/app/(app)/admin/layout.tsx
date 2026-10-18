import type { Metadata } from "next";

/** Nur, um der Seite einen Namen zu geben: `page.tsx` ist eine
 *  Client-Komponente und kann kein `metadata` exportieren.
 *  `tests/test_seitentitel.py` hält, dass jede Seite einen eigenen Titel hat. */
export const metadata: Metadata = {
  title: "Admin",
  robots: { index: false },
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
