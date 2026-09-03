import type { Metadata } from "next";
import { notFound } from "next/navigation";
import View from "./view";
import { PROBLEM_ANGEBOT } from "@/lib/probleme";
import { PROBLEME_FREI } from "@/lib/probleme-frei";

export const metadata: Metadata = {
  title: PROBLEM_ANGEBOT.name,
  description: "Kommunale Probleme in Oldenburg auf einer unabhängigen Ratslotse-Karte.",
};

export default function Page() {
  if (!PROBLEME_FREI) notFound();
  return <View />;
}
