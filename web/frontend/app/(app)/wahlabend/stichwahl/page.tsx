import { Suspense } from "react";
import { StichwahlView } from "@/components/wahlabend/stichwahl";

// Wie /wahlabend: Die Seite liest Query-Parameter (?probe=, ?counted=), und
// dafür braucht Next eine Suspense-Grenze (web/frontend/CLAUDE.md).
export default function StichwahlSeite() {
  return (
    <Suspense fallback={null}>
      <StichwahlView />
    </Suspense>
  );
}
