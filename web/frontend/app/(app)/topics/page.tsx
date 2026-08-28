import { Suspense } from "react";
import type { Metadata } from "next";
import { TopicsView } from "./view";

export const metadata: Metadata = {
  title: "Meine Themen",
  description:
    "Deine Suchaufträge an den Oldenburger Stadtrat — jede neue Sitzung wird "
    + "darauf geprüft, Treffer kommen per Mail oder Push.",
};

export default function TopicsPage() {
  // useSearchParams (Vorbefüllung ?neu=, Weiterleitung ?zeig=abos) braucht
  // eine Suspense-Grenze.
  return (
    <Suspense>
      <TopicsView />
    </Suspense>
  );
}
