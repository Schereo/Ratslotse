import type { Metadata } from "next";
import { AbosView } from "./view";

export const metadata: Metadata = {
  title: "Ausschuss-Abos",
  description:
    "Gremien des Oldenburger Stadtrats abonnieren — Benachrichtigung, sobald "
    + "eine Tagesordnung veröffentlicht wird oder sich ändert.",
};

export default function AbosPage() {
  return <AbosView />;
}
