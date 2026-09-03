import type { Metadata } from "next";
import { serverApiUrl } from "@/lib/api";
import type { ApiAntwort } from "@/lib/vertrag";

/** Link-Vorschau für geteilte Detailseiten (Design 29a, P1).
 *
 *  Teilen ist die Kernhandlung der App — der `ShareButton` steckt überall.
 *  Trotzdem zeigte jeder geteilte Link denselben Werbetext: In einer
 *  Elterngruppe landeten fünf Beschlüsse als fünf identische Kacheln, und für
 *  Suchmaschinen war die Seite gar nicht auffindbar. Titel, Ergebnis, Gremium
 *  und Datum liegen im Backend bereit; hier werden sie in die Vorschau
 *  geschrieben.
 *
 *  Die Council-Seiten arbeiten mit Query-Parametern (`?id=`), damit der
 *  (app)-Bereich sauber statisch exportiert (siehe lib/routes.ts).
 *  `generateMetadata` darf `searchParams` deshalb NUR im Server-Build
 *  anfassen. Die kanonische Problem-Detailroute ist dagegen ein Pfadsegment;
 *  build-mobile.mjs nimmt sie aus dem Export, dessen Query-Adapter unter
 *  `/probleme?problem=` keine eigenen Metadaten erzeugt.
 */

/** Der native App-Build ist ein statischer Export ohne Server — dort gibt es
 *  keine Link-Vorschau zu bauen (und keine geben zu dürfen). */
export const istExport = () => process.env.MOBILE === "1";

export type VorschauArt = "decision" | "person" | "thema" | "sitzung" | "ort";

async function holeVorschau(art: VorschauArt, key: string) {
  try {
    const res = await fetch(serverApiUrl(`/council/preview/${art}/${encodeURIComponent(key)}`), {
      // Geteilte Links werden von Messengern oft im Schwarm abgerufen — eine
      // Viertelstunde Cache reicht völlig und hält die Last vom Backend fern.
      next: { revalidate: 900 },
    });
    if (!res.ok) return null;
    return (await res.json()) as { title: string; description: string };
  } catch {
    // Backend nicht erreichbar: lieber die allgemeine Vorschau als ein
    // kaputter Seitenaufruf — die Metadaten sind nie den Fehler wert.
    return null;
  }
}

/** Ausfallsichere Link-Vorschau für eine öffentliche Problemprojektion. */
export async function problemVorschauMetadata(
  problemId: number | null,
  pfad: string,
): Promise<Metadata> {
  let title = "Problem in Oldenburg — Ratslotse";
  let description = "Moderierte öffentliche Informationen zu einem Problem in Oldenburg.";
  let found = false;
  if (!istExport() && problemId !== null) {
    try {
      const response = await fetch(serverApiUrl(`/probleme/${problemId}`), {
        next: { revalidate: 900 },
      });
      if (response.ok) {
        const problem = await response.json() as ApiAntwort<"/probleme/{problem_id}">;
        title = `${problem.title} — Ratslotse`;
        description = problem.summary;
        found = true;
      }
    } catch {
      // Metadaten dürfen die öffentliche Seite nie unlesbar machen.
    }
  }
  return {
    title,
    description,
    alternates: { canonical: pfad },
    robots: found ? undefined : { index: false, follow: false },
    openGraph: { title, description, url: pfad, type: "article" },
    twitter: { card: "summary_large_image", title, description },
  };
}

/** Fertige `Metadata` für eine geteilte Detailseite. Ohne Treffer bleibt es bei
 *  den Vorgaben aus dem Wurzel-Layout. */
export async function vorschauMetadata(
  art: VorschauArt,
  key: string | undefined,
  pfad: string,
): Promise<Metadata> {
  if (istExport() || !key) return {};
  const v = await holeVorschau(art, key);
  if (!v) return {};
  return {
    title: v.title,
    description: v.description,
    alternates: { canonical: pfad },
    openGraph: { title: v.title, description: v.description, url: pfad, type: "article" },
    twitter: { card: "summary_large_image", title: v.title, description: v.description },
  };
}
