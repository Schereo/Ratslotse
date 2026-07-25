"use client";

import { useEffect, useState } from "react";
import { Printer } from "lucide-react";
import { Button } from "@/components/ui";
import { isNativeApp } from "@/lib/platform";

/**
 * Druck-Knopf (Design 28a/W3). Das Druck-Stylesheet in `globals.css` räumt
 * Navigation, Kopf- und Fußzeile längst ab — es fehlte nur der Auslöser.
 *
 * In der nativen App gibt es keinen Druckdialog (WKWebView), dort erscheint der
 * Knopf gar nicht erst: ein Knopf, der nichts tut, ist schlimmer als keiner.
 */
export function PrintButton({ className, label = "Drucken" }: { className?: string; label?: string }) {
  // Erst nach dem Mount entscheiden: Der statische Export rendert auf dem
  // Server, wo Capacitor immer „nicht nativ" meldet — die Entscheidung im
  // Render würde in der App eine Hydration-Abweichung erzeugen.
  const [show, setShow] = useState(false);
  useEffect(() => {
    setShow(!isNativeApp() && typeof window.print === "function");
  }, []);
  if (!show) return null;
  return (
    <Button variant="secondary" size="sm" onClick={() => window.print()} className={className}>
      <Printer /> {label}
    </Button>
  );
}
