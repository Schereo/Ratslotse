import type { Metadata } from "next";
import View from "./view";

export const metadata: Metadata = {
  title: "Der neue Rat",
  description: "Wer nach der Ratswahl 2026 im Rat der Stadt Oldenburg sitzt — mit Liste, Wahlbereich und Personenstimmen.",
};

export default function Page() {
  return <View />;
}
