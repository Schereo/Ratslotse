"use client";

import { useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { DetailSkeleton } from "@/components/ui";
import { karteHref } from "@/lib/routes";

/** `/viertel` ist seit dem Umzug (STADTKARTE-PLAN.md, Schritt 5) nur noch ein
 *  Einstieg: Mails, geteilte Links und die ausgelieferte iOS-App kennen die
 *  Adresse, die Tafel lebt unter `/karte?ort=…&v=…`.
 *
 *  Eine Weiterleitung im Browser, keine in `next.config.mjs`: Die gibt es im
 *  statischen Export nicht — und sie wäre ohnehin temporär, nie permanent
 *  (permanente Redirects kleben im Browser, s. Notiz Haushalts-Labor). Die
 *  Anmeldung regelt das App-Layout: `/viertel` steht seit dem Umzug nicht
 *  mehr in `OEFFENTLICHE_PFADE`, ohne Konto landet man mit `?weiter=` auf der
 *  Anmeldung und danach auf der Karte.
 */
export default function ViertelView() {
  const router = useRouter();
  const sp = useSearchParams();
  const id = sp.get("id");
  const v = Number(sp.get("v"));
  useEffect(() => {
    router.replace(karteHref(id, Number.isFinite(v) && v > 0 ? v : null));
  }, [router, id, v]);
  return <DetailSkeleton />;
}
