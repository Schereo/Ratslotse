// /kommunalwahl/check — der Thesen-Check (Design 4a–4c).
// Server-Hülle mit Metadata; die drei Phasen (Einstieg, Fragen, Ergebnis)
// laufen vollständig im Client — Antworten bleiben auf dem Gerät.

import type { Metadata } from "next";
import { ThesenCheck } from "@/components/kommunalwahl/check";
import { KwCrumb, KwKopf } from "@/components/kommunalwahl/ui";
import { checkDaten } from "@/lib/kommunalwahl";

export const metadata: Metadata = {
  title: "Thesen-Check",
  description:
    "Beantworte die 44 Thesen der Ratswahl Oldenburg 2026 und sieh, wie oft jede Liste mit dir übereinstimmt — Satz für Satz belegt, kein Wahltipp, Antworten bleiben auf deinem Gerät.",
};

export default function CheckSeite() {
  return (
    <>
      <KwKopf crumb={<KwCrumb teil="Thesen-Check" />} />
      <ThesenCheck daten={checkDaten()} />
    </>
  );
}
