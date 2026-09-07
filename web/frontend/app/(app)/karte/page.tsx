import type { Metadata } from "next";
import { Suspense } from "react";
import { DetailSkeleton } from "@/components/ui";
import View from "./view";

export const metadata: Metadata = {
  title: "Mein Viertel",
  description: "Die Stadtkarte von Ratslotse: Was sich wo in Oldenburg ändert — Vorhaben, Bebauungspläne und Sperrungen je Ortsbereich, aus den Beschlüssen des Stadtrats und den Daten der Stadt.",
};

export default function Page() {
  return (
    <Suspense fallback={<DetailSkeleton />}>
      <View />
    </Suspense>
  );
}
