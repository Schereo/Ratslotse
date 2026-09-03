"use client";

import { notFound } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { darfHaushalt } from "@/lib/rechte";
import { Spinner } from "@/components/ui";
import { FortschrittMerker } from "@/components/haushalt/fortschritt-merker";

// Rechte-Gate für den gesamten Haushalts-Bereich — die zwanzig Seiten unter
// /haushalt (die Übersicht und neunzehn Unterseiten) sind Ratsmitgliedern und
// Admins vorbehalten (Recht `budget`, siehe lib/rechte.ts und kern/roles.py).
//
// Bewusst als Layout und nicht je Seite: Zwanzig einzelne Gates wären zwanzig
// Gelegenheiten, eines zu vergessen — und die einundzwanzigste Seite käme
// ungeschützt dazu. Das Layout greift für alles, was unter diesem Pfad liegt,
// auch für später Hinzukommendes.
//
// **Das hier ist die Höflichkeit, nicht die Sperre.** Die Sperre sitzt im
// Backend: Alle zwanzig `/api/council/budget…`-Routen verlangen dasselbe
// Recht, und `tests/test_rollen.py` hält das fest. Wer dieses Gate im Browser
// umgeht, bekommt zwanzig leere Seiten und zwanzig 403er — keine Daten. Ein
// Client-Gate allein wäre kein Schutz, sondern eine Bitte.
//
// Bis 09/2026 stand hier ein Umgebungs-Gate (`NEXT_PUBLIC_RATSLOTSE_ENV ===
// "dev"`), das den Bereich auf dev einsperrte. Es ist ersatzlos entfallen: Die
// Rolle leistet dasselbe, aber richtig herum — der Bereich fährt nach Prod und
// ist dort für die sichtbar, für die er gebaut ist.
//
// Der Bereich lebt INNERHALB von app/(app)/ und erbt damit dessen Layout
// (Navigation, Auth) — anders als die Kommunalwahl, die bewusst außerhalb
// liegt. Hier steht deshalb nur das Gate, keine Kopf- oder Fußzeile.
export default function HaushaltLayout({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();

  // Solange die Sitzung geladen wird, ist noch NICHTS entschieden. Ein
  // notFound() an dieser Stelle träfe jedes Ratsmitglied beim ersten Aufruf
  // (und beim Neuladen der Seite) — die Rechte kommen erst mit /auth/me.
  if (loading) {
    return (
      <div className="flex min-h-[50vh] items-center justify-center">
        <Spinner />
      </div>
    );
  }
  if (!darfHaushalt(user)) notFound();

  return (
    <>
      {/* Merkt sich besuchte Unterseiten für den Wegweiser-Lesestand — im
          Layout aus demselben Grund wie das Gate: einmal für alle Seiten. */}
      <FortschrittMerker />
      {children}
    </>
  );
}
