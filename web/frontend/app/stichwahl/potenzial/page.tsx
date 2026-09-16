import { Suspense } from "react";
import { PotenzialView } from "@/components/wahlabend/potenzial/view";

// Das Wähler*innen-Potenzial für die Stichwahl (docs/plan-stichwahl-potenzial.md).
// Die Seite liest den Token aus `?k=` — ein Query-Parameter statt eines
// Pfadsegments, damit der statische Export der App-Hülle sie kennt; dafür
// braucht Next eine Suspense-Grenze (web/frontend/CLAUDE.md).
export default function PotenzialSeite() {
  return (
    <Suspense fallback={null}>
      <PotenzialView />
    </Suspense>
  );
}
