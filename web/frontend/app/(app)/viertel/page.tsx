import type { Metadata } from "next";
import { Suspense } from "react";
import { DetailSkeleton } from "@/components/ui";
import View from "./view";

export const metadata: Metadata = {
  title: "Mein Viertel",
  description: "Was sich in deinem Oldenburger Ortsbereich in den nächsten Jahren ändert — Vorhaben aus Beschlüssen des Stadtrats, gebündelt und geprüft.",
};

export default function Page() {
  return (
    <Suspense fallback={<DetailSkeleton />}>
      <View />
    </Suspense>
  );
}
