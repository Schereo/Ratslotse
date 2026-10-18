import type { Metadata } from "next";

/** Nur, um der Übersicht einen Namen zu geben.
 *
 *  **Warum eine Routengruppe.** Das Layout darüber (`haushalt/layout.tsx`) ist
 *  das Rechte-Gate und damit eine Client-Komponente — es kann kein `metadata`
 *  exportieren, die Seite selbst auch nicht. Bis 10/2026 trug der Tab deshalb
 *  den langen Titel aus dem Wurzel-Layout. Die Gruppe `(uebersicht)` ändert
 *  die Adresse nicht (`/haushalt`), gibt der Seite aber ein eigenes
 *  Server-Layout. Der Titel ist derselbe wie in `kern/knowledge.py`;
 *  `tests/test_seitentitel.py` hält, dass jede Seite einen eigenen hat. */
export const metadata: Metadata = {
  title: "Haushalt — Übersicht",
  description: "Wofür Oldenburg sein Geld ausgibt und woher es kommt — aus Haushaltsplan und Jahresabschluss.",
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
