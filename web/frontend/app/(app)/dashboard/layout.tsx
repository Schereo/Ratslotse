import type { Metadata } from "next";

/**
 * Nur, um der Seite einen Namen zu geben.
 *
 * **Warum ein eigenes Layout.** `page.tsx` ist eine Client-Komponente und
 * kann kein `metadata` exportieren; ohne diese Datei trug der Tab den langen
 * Marketing-Titel aus dem Wurzel-Layout.
 *
 * **Und warum das über Kosmetik hinausgeht.** Die `h1` der Seite ist ein Gruß
 * mit dem Anzeigenamen („Moin, Ratsfrau!"). Lotti darf beides nicht sehen
 * (`lib/assistentin.ts::seitenUeberschrift`), schickt deshalb eine leere
 * Überschrift — und Fenster wie Backend fallen auf den Seitentitel zurück.
 * Der heißt damit hier genauso wie in `kern/knowledge.py` („Heute").
 */
export const metadata: Metadata = {
  title: "Heute",
  description: "Was seit dem letzten Besuch dazugekommen ist: neue Beschlüsse, "
    + "anstehende Sitzungen und was in den eigenen Vierteln passiert.",
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
