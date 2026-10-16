import { Suspense } from "react";
import { WahlenView } from "@/components/wahlen/view";

export default function WahlenSeite() {
  return (
    <Suspense fallback={null}>
      <WahlenView />
    </Suspense>
  );
}
