import { Suspense } from "react";
import { TippLive } from "@/components/tipp/live";

export default function TippLiveSeite() {
  return (
    <Suspense fallback={null}>
      <TippLive />
    </Suspense>
  );
}
