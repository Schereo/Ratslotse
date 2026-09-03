import { notFound } from "next/navigation";
import { HAUSHALT_FREI } from "@/lib/haushalt-frei";
import { FortschrittMerker } from "@/components/haushalt/fortschritt-merker";

// Umgebungs-Gate für den gesamten Haushalts-Bereich — die zwanzig Seiten
// unter /haushalt (die Übersicht und neunzehn Unterseiten) sind nur auf
// dev.ratslotse.de erreichbar (Begründung und Wirkungsweise:
// lib/haushalt-frei.ts).
//
// Bewusst als Layout und nicht je Seite: Zwanzig einzelne Gates wären zwanzig
// Gelegenheiten, eines zu vergessen — und die einundzwanzigste Seite käme
// ungeschützt dazu. Das Layout greift für alles, was unter diesem Pfad liegt,
// auch für später Hinzukommendes. Der Stellenplan (`/haushalt/personal`), die
// Schuldenzeitreihe (`/haushalt/schulden`) und die Kennzahlen
// (`/haushalt/indicators`) sind genau dieser Fall: alle drei 08/2026
// dazugekommen, ohne dass jemand das Gate anfassen musste.
//
// Der Bereich lebt INNERHALB von app/(app)/ und erbt damit dessen Layout
// (Navigation, Auth) — anders als die Kommunalwahl, die bewusst außerhalb
// liegt. Hier steht deshalb nur das Gate, keine Kopf- oder Fußzeile.
export default function HaushaltLayout({ children }: { children: React.ReactNode }) {
  if (!HAUSHALT_FREI) notFound();
  return (
    <>
      {/* Merkt sich besuchte Unterseiten für den Wegweiser-Lesestand — im
          Layout aus demselben Grund wie das Gate: einmal für alle Seiten. */}
      <FortschrittMerker />
      {children}
    </>
  );
}
