import { Suspense } from "react";
import { WahlabendView } from "@/components/wahlabend/view";

// Die Seite liest Query-Parameter (?liste=, ?probe=) — dafür braucht Next
// eine Suspense-Grenze, sonst bricht `next build` beim Vorrendern ab.
export default function WahlabendSeite() {
  return (
    <Suspense fallback={null}>
      <WahlabendView />
    </Suspense>
  );
}
