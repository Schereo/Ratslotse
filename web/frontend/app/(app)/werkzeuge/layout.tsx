"use client";

import { notFound } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { darfWerkzeuge } from "@/lib/rechte";
import { Spinner } from "@/components/ui";

// Rechte-Gate für den ganzen Bereich /werkzeuge — Ratsmitglieder und Admins
// (Recht `council_tools`, kern/roles.py). Als Layout aus demselben Grund wie
// beim Haushalt: Jedes künftige Werkzeug liegt darunter und ist gleich mit
// gesperrt.
//
// Höflichkeit, nicht Sperre: Die sitzt an `/api/tools/…`
// (tests/test_werkzeuge.py hält fest, dass jede Route das Recht verlangt).
export default function WerkzeugeLayout({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  // Erst entscheiden, wenn die Rechte da sind — sonst träfe das 404 jedes
  // Ratsmitglied beim Neuladen.
  if (loading) {
    return (
      <div className="flex min-h-[50vh] items-center justify-center">
        <Spinner />
      </div>
    );
  }
  if (!darfWerkzeuge(user)) notFound();
  return <>{children}</>;
}
