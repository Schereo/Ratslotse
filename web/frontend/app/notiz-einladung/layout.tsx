import type { Metadata } from "next";

/** Nur der Seitentitel — `page.tsx` ist eine Client-Komponente
 *  (`tests/test_seitentitel.py` hält, dass jede Seite einen eigenen hat). */
export const metadata: Metadata = {
  title: "Einladung zur gemeinsamen Notiz",
  description: "Einer gemeinsamen Notiz bei Ratslotse beitreten.",
  robots: { index: false, follow: false },
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
