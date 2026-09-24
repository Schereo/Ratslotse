import type { Metadata } from "next";
import { Suspense } from "react";
import { DetailSkeleton } from "@/components/ui";
import { SEITEN_POLSTER } from "@/lib/vollbreit";
import View from "./view";

export const metadata: Metadata = {
  title: "Mein Viertel",
  description: "Die Stadtkarte von Ratslotse: Was sich wo in Oldenburg ändert — Vorhaben, Bebauungspläne und Sperrungen je Ortsbereich, aus den Beschlüssen des Stadtrats und den Daten der Stadt.",
};

export default function Page() {
  return (
    <Suspense fallback={<div className={SEITEN_POLSTER}><DetailSkeleton /></div>}>
      <View />
    </Suspense>
  );
}
