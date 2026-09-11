import { Suspense } from "react";
import { TippView } from "@/components/tipp/view";

// Kein Query-Parameter nötig (ein Spiel, kein Code) — trotzdem eine
// Suspense-Grenze, weil die View den Cookie-Zustand erst nach dem Mount
// kennt und `useSearchParams` an anderer Stelle im Baum vorkommen kann
// (web/frontend/CLAUDE.md: statischer Export).
export default function TippSeite() {
  return (
    <Suspense fallback={null}>
      <TippView />
    </Suspense>
  );
}
