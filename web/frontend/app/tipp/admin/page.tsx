import { Suspense } from "react";
import { TippAdminView } from "@/components/tipp/admin-view";

export default function TippAdminSeite() {
  return (
    <Suspense fallback={null}>
      <TippAdminView />
    </Suspense>
  );
}
