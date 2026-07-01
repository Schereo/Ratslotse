import * as React from "react";
import { Card } from "@/components/ui";
import { Mascot, type MascotPose } from "@/components/mascot";
import { BrandMark } from "@/components/brand";

/**
 * Gemeinsamer Rahmen der Auth-Seiten: Wellen-Hintergrund, Lotti hinter der
 * Kartenkante, Markenkopf. Hält Login/Registrierung/Passwort-Seiten konsistent.
 */
export function AuthShell({
  title,
  pose = "wave",
  children,
}: {
  title: string;
  pose?: MascotPose;
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-waves px-4 pb-12 pt-28">
      <div className="relative w-full max-w-sm">
        <Mascot pose={pose} className="pointer-events-none absolute -top-[5.65rem] left-1/2 h-24 w-24 -translate-x-1/2" />
        <Card className="relative w-full p-8 shadow-lifted">
          <div className="flex items-center gap-3">
            <BrandMark />
            <h1 className="text-2xl font-bold tracking-tight text-foreground">{title}</h1>
          </div>
          {children}
        </Card>
      </div>
    </div>
  );
}
