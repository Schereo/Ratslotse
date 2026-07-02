"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { MascotTip, type MascotPose } from "@/components/mascot";
import { cn } from "@/lib/utils";

/**
 * „Lotsen-Tipp" — ein täglich rotierender Feature-Hinweis von Lotti auf dem
 * Dashboard. Wegklicken blendet ihn für den Rest des Tages aus (localStorage);
 * am nächsten Tag kommt der nächste Tipp an die Reihe.
 */
type Tip = { pose: MascotPose; text: string; href?: string; label?: string };

const TIPS: Tip[] = [
  {
    pose: "wave",
    text: "Stell dir die Zustellung ein — Benachrichtigungen zu deinen Themen kommen per Telegram oder E-Mail.",
    href: "/account",
    label: "Zustellung einstellen",
  },
  {
    pose: "point",
    text: "Auf jeder Beschluss-Seite kannst du unter „In der Presse“ direkt bei NWZonline nach Berichten dazu suchen.",
  },
  {
    pose: "search",
    text: "Unter „Ähnliche Beschlüsse“ siehst du, was der Rat früher zum selben Thema entschieden hat.",
  },
  {
    pose: "celebrate",
    text: "Lege unter „Meine Themen“ Suchbegriffe an — ich melde mich, sobald es neue Beschlüsse dazu gibt.",
    href: "/topics",
    label: "Thema anlegen",
  },
  {
    pose: "point",
    text: "In der Analyse siehst du, wohin das Geld fließt — nach Themenfeld, Fraktion und Quartal.",
    href: "/council?tab=analysis",
    label: "Zur Analyse",
  },
  {
    pose: "search",
    text: "Die Themen-Karte zeigt, wo in Oldenburg der Rat gerade aktiv ist — mit KI-Beschreibung je Ort.",
    href: "/council?tab=themen",
    label: "Zur Karte",
  },
];

const HIDE_KEY = "ratslotse:lotsen-tipp-hidden";

export function LotsenTipp({ className }: { className?: string }) {
  const [tip, setTip] = useState<Tip | null>(null);

  useEffect(() => {
    const today = new Date().toISOString().slice(0, 10);
    try {
      if (localStorage.getItem(HIDE_KEY) === today) return;
    } catch {
      /* Storage gesperrt — Tipp trotzdem zeigen */
    }
    // Tageszähler statt Zufall: alle Nutzer sehen pro Tag denselben Tipp,
    // und über die Woche kommt jeder Tipp einmal dran.
    const day = Math.floor(Date.now() / 86_400_000);
    setTip(TIPS[day % TIPS.length]);
  }, []);

  const dismiss = () => {
    setTip(null);
    try {
      localStorage.setItem(HIDE_KEY, new Date().toISOString().slice(0, 10));
    } catch {
      /* ignore */
    }
  };

  if (!tip) return null;
  return (
    <MascotTip pose={tip.pose} title="Lotsen-Tipp" onDismiss={dismiss} className={cn(className)}>
      {tip.text}
      {tip.href && (
        <>
          {" "}
          <Link href={tip.href} className="font-medium text-primary hover:underline">
            {tip.label} →
          </Link>
        </>
      )}
    </MascotTip>
  );
}
