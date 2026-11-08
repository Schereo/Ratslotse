import { Suspense } from "react";
import { PotenzialView } from "@/components/wahlabend/potenzial/view";

// Das Wähler*innen-Potenzial für die Stichwahl (docs/plan-stichwahl-potenzial.md).
// Die Seite liest den Token aus `?k=` — ein Query-Parameter statt eines
// Pfadsegments (web/frontend/CLAUDE.md); dafür braucht Next eine
// Suspense-Grenze.
export default function PotenzialSeite() {
  return (
    <Suspense fallback={null}>
      <PotenzialView />
    </Suspense>
  );
}
