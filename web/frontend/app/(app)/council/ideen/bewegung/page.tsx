import type { Metadata } from "next";
import View from "./view";

// Derselbe Titel wie in `kern/knowledge.py` (Lottis Seitenwissen).
export const metadata: Metadata = {
  title: "Eine Idee aus anderen Städten",
  description: "Eine Idee, die mehrere andere Räte beantragt oder beschlossen haben.",
};

export default function Page() {
  return <View />;
}
