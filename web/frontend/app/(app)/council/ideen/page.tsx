import type { Metadata } from "next";
import View from "./view";

// Derselbe Titel wie in `kern/knowledge.py` (Lottis Seitenwissen).
export const metadata: Metadata = {
  title: "Ideen aus anderen Städten",
  description: "Was andere Städte beschlossen haben und Oldenburg noch nicht — zum Weiterdenken.",
};

export default function Page() {
  return <View />;
}
