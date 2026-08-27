import type { Metadata } from "next";

/** Link-Vorschau für geteilte Detailseiten (Design 29a, P1).
 *
 *  Teilen ist die Kernhandlung der App — der `ShareButton` steckt überall.
 *  Trotzdem zeigte jeder geteilte Link denselben Werbetext: In einer
 *  Elterngruppe landeten fünf Beschlüsse als fünf identische Kacheln, und für
 *  Suchmaschinen war die Seite gar nicht auffindbar. Titel, Ergebnis, Gremium
 *  und Datum liegen im Backend bereit; hier werden sie in die Vorschau
 *  geschrieben.
 *
 *  Die Seiten der App arbeiten mit Query-Parametern (`?id=`) statt Pfad-
 *  Segmenten, damit der (app)-Bereich sauber statisch exportiert (siehe
 *  lib/routes.ts). `generateMetadata` darf `searchParams` deshalb NUR im
 *  Server-Build anfassen — im Export (MOBILE=1) würde jeder Zugriff die Seite
 *  dynamisch machen und den Build abbrechen. Darum steht in jeder Hülle die
 *  Kurzschluss-Zeile `if (istExport()) return {}`.
 */

/** Der native App-Build ist ein statischer Export ohne Server — dort gibt es
 *  keine Link-Vorschau zu bauen (und keine geben zu dürfen). */
export const istExport = () => process.env.MOBILE === "1";

export type VorschauArt = "decision" | "person" | "thema" | "sitzung" | "ort";

/** Backend-Origin für den Server-seitigen Abruf. Im Betrieb läuft das Frontend
 *  neben dem Backend auf demselben Host; `BACKEND_URL` ist dieselbe Variable,
 *  die auch next.config.mjs für die /api-Weiterleitung benutzt. */
const BACKEND = process.env.BACKEND_URL || "http://localhost:8000";

async function holeVorschau(art: VorschauArt, schluessel: string) {
  try {
    const res = await fetch(`${BACKEND}/api/council/preview/${art}/${encodeURIComponent(schluessel)}`, {
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

/** Fertige `Metadata` für eine geteilte Detailseite. Ohne Treffer bleibt es bei
 *  den Vorgaben aus dem Wurzel-Layout. */
export async function vorschauMetadata(
  art: VorschauArt,
  schluessel: string | undefined,
  pfad: string,
): Promise<Metadata> {
  if (istExport() || !schluessel) return {};
  const v = await holeVorschau(art, schluessel);
  if (!v) return {};
  return {
    title: v.title,
    description: v.description,
    alternates: { canonical: pfad },
    openGraph: { title: v.title, description: v.description, url: pfad, type: "article" },
    twitter: { card: "summary_large_image", title: v.title, description: v.description },
  };
}
