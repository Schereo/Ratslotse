import { Suspense } from "react";
import { TippView } from "@/components/tipp/view";

// Suspense-Grenze, weil die View `useSearchParams` liest (die Generalprobe
// `?probe=2021&counted=N`) und den Cookie-Zustand ohnehin erst nach dem
// Mount kennt — ohne die Grenze bricht der statische Export ab
// (web/frontend/CLAUDE.md).
export default function TippSeite() {
  return (
    <Suspense fallback={null}>
      <TippView />
    </Suspense>
  );
}
