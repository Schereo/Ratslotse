import type { Metadata } from "next";
import { notFound } from "next/navigation";
import BeschlussradarView from "./view";

const BESCHLUSSRADAR_FREI = process.env.NEXT_PUBLIC_RATSLOTSE_ENV === "dev";

export function generateMetadata(): Metadata {
  if (!BESCHLUSSRADAR_FREI) return {};
  return {
    title: "Beschlussradar – Ratslotse",
    description:
      "Geplante, laufende und entschiedene Vorlagen des Oldenburger Stadtrats im Überblick.",
  };
}

export default function BeschlussradarPage() {
  if (!BESCHLUSSRADAR_FREI) notFound();
  return <BeschlussradarView />;
}
