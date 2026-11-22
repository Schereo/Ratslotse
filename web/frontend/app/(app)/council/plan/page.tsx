import type { Metadata } from "next";
import View from "./view";

export const metadata: Metadata = {
  title: "Plan der Stadt",
  description: "Ein Plan der Stadt Oldenburg: Beschluss, Laufzeit, Berichte im Rat und die Beschlüsse dazu.",
};

export default function Page() {
  return <View />;
}
