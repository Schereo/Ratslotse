import { notFound } from "next/navigation";
import { HAUSHALT_FREI } from "@/lib/haushalt-frei";

// Umgebungs-Gate für den gesamten Haushalts-Bereich — die vierzehn Seiten
// unter /haushalt sind nur auf dev.ratslotse.de erreichbar (Begründung und
// Wirkungsweise: lib/haushalt-frei.ts).
//
// Bewusst als Layout und nicht je Seite: Vierzehn einzelne Gates wären
// vierzehn Gelegenheiten, eines zu vergessen — und die fünfzehnte Seite käme
// ungeschützt dazu. Das Layout greift für alles, was unter diesem Pfad liegt,
// auch für später Hinzukommendes.
//
// Genau so ist es gekommen: `/haushalt/schulden` ist die vierzehnte Seite und
// hat kein eigenes Gate bekommen — sie brauchte keines.
//
// Der Bereich lebt INNERHALB von app/(app)/ und erbt damit dessen Layout
// (Navigation, Auth) — anders als die Kommunalwahl, die bewusst außerhalb
// liegt. Hier steht deshalb nur das Gate, keine Kopf- oder Fußzeile.
export default function HaushaltLayout({ children }: { children: React.ReactNode }) {
  if (!HAUSHALT_FREI) notFound();
  return <>{children}</>;
}
