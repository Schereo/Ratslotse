import { Suspense } from "react";
import { StichwahlAnalyseView } from "@/components/wahlabend/analyse/view";

// Der bisherige private Link bleibt gültig. Die Seite erklärt jetzt
// stadtweite Wahlergebnisse; sie enthält keine Gebietsempfehlungen.
export default function StichwahlAnalyseSeite() {
  return <Suspense fallback={null}><StichwahlAnalyseView /></Suspense>;
}
