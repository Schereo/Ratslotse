import type { Metadata } from "next";

/** Nur, um der Seite einen Namen zu geben: `page.tsx` ist eine
 *  Client-Komponente und kann kein `metadata` exportieren — bis 10/2026 trug
 *  der Tab deshalb den langen Titel aus dem Wurzel-Layout
 *  (s. `app/(app)/dashboard/layout.tsx`). `tests/test_seitentitel.py` hält,
 *  dass jede Seite einen eigenen Titel hat. */
export const metadata: Metadata = {
  title: "E-Mail bestätigen",
  description: "Die E-Mail-Adresse für Ratslotse bestätigen.",
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
